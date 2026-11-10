#!/usr/bin/env python3
"""Exercise related-clock pair/word boundaries and both training phases.

The pin-side ten-bit bus stays at 312.5 MHz, with a 156.25 MHz pair engine
on each side. Distinct capture phases and startup offsets exercise both
word alignments. This is functional RTL, not generated-clock physical STA.
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
    sources = [PROJECT/'sim/tb_dense_pair_link.sv', PROJECT/'rtl/pt_dense_pair_link.sv',
               PROJECT/'rtl/pt_dense_pair.sv', PROJECT/'rtl/pt_dense_header.sv']
    subprocess.run(['iverilog', '-g2012', '-I', str(PROJECT/'rtl'), '-s', 'tb_dense_pair_link',
                    '-o', str(out/'bench.vvp'), *map(str, sources)], check=True, capture_output=True)
    cases = []
    for owner in (0, 1):
        for offset in (0, 1):
            for phase in (0.2, 0.8, 1.6, 2.4, 3.0):
                case = out/f'owner-{owner}-offset-{offset}-phase-{phase}'
                case.mkdir(exist_ok=True)
                run = subprocess.run(['vvp', str(out/'bench.vvp'), f'+OWNER={owner}',
                                      f'+OFFSET={offset}', f'+PHASE={phase}'], cwd=case,
                                     capture_output=True, text=True)
                (case/'simulation.log').write_text(run.stdout+run.stderr)
                assert run.returncode == 0, (case, run.stdout, run.stderr)
                words, frames, popped = map(int, (case/'result.txt').read_text().split())
                cases.append(dict(owner=owner, capture_offset_words=offset, phase_ns=phase,
                                  received_words=words, frames=frames, source_pairs=popped))
    result = dict(status='pass', word_period_ns=3.2, engine_period_ns=6.4, cases=cases,
                  scope='paired link and word boundary RTL; no main hierarchy or physical STA closure',
                  source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sources+[Path(__file__).resolve()]})
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(status='pass', cases=len(cases),
                          received_words=sum(c['received_words'] for c in cases))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/dense-pair-link')
    check(parser.parse_args().output_dir.resolve())
