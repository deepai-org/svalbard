#!/usr/bin/env python3
"""Exercise the AC-1 quad link end to end through both pad-edge gearboxes.

Launch side: quad framer at host word clock / 4, XOR-prefix 4:1 gearbox and
DDR (or SDR) pin launch with forwarded clock. Capture side: a second host
link on an independently phased clock (DDR/SDR capture, 1:4 gearbox, quad
CDC FIFO) and the quad deframer with four-rotation training acquisition.
Release offsets and pin modes cover every word rotation of the quad stream.
Functional RTL only: no physical STA, pad or board timing.
(Make target name kept from the paired engine: transceiver-dense-pair-link.)
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]


def check(out):
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text('{"status":"incomplete"}\n')
    sources = [PROJECT/'sim/tb_dense_pair_link.sv']+[PROJECT/'rtl'/n for n in
               ['pt_quad_link.sv', 'pt_host_link.sv', 'pt_dense_header.sv', 'pt_fifo.sv', 'pt_cells.sv', 'pt_pattern.sv']]
    subprocess.run(['iverilog', '-g2012', '-I', str(PROJECT/'rtl'), '-s', 'tb_dense_pair_link',
                    '-o', str(out/'bench.vvp'), *map(str, sources)], check=True, capture_output=True)
    cases = []
    rotations = set()
    for owner in (0, 1):
        for sdr in (0, 1):
            for offset in (0, 1, 2, 3):
                for phase in (0.2, 0.8, 1.6, 2.4, 3.0):
                    case = out/f'owner-{owner}-sdr-{sdr}-offset-{offset}-phase-{phase}'
                    case.mkdir(exist_ok=True)
                    run = subprocess.run(['vvp', str(out/'bench.vvp'), f'+OWNER={owner}', f'+SDR={sdr}',
                                          f'+OFFSET={offset}', f'+PHASE={phase}'], cwd=case,
                                         capture_output=True, text=True)
                    (case/'simulation.log').write_text(run.stdout+run.stderr)
                    assert run.returncode == 0 and 'PASS quad link loopback' in run.stdout, (case, run.stdout, run.stderr)
                    words, frames, popped, _ = map(int, (case/'result.txt').read_text().split())
                    rotation = int(run.stdout.split('rotation')[1].split()[0])
                    rotations.add(rotation)
                    cases.append(dict(owner=owner, pin_mode='sdr' if sdr else 'ddr', capture_offset_words=offset,
                                      phase_ns=phase, received_words=words, frames=frames, source_quads=popped,
                                      rotation=rotation))
    assert rotations == {0, 1, 2, 3}, f'Not every word rotation exercised: {sorted(rotations)}'
    result = dict(status='pass', word_period_ns=3.2, ddr_period_ns=6.4, core_period_ns=12.8, cases=cases,
                  rotations_exercised=sorted(rotations),
                  scope='quad link through both pad-edge gearboxes (loopback); no physical STA or pad timing',
                  source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sources+[Path(__file__).resolve()]})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(status='pass', cases=len(cases), rotations=sorted(rotations),
                          received_words=sum(c['received_words'] for c in cases))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/dense-pair-link')
    check(parser.parse_args().output_dir.resolve())
