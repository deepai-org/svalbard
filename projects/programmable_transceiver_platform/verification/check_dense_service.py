#!/usr/bin/env python3
"""Run real RTL FIFOs at 312.5 MHz host / 2.5 Gb/s wired and reject overload.

Clock phase sweep is functional evidence; cell delays, board skew, pauses and
clock-tolerance admission require separate timing/service qualification.
"""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess

PROJECT = Path(__file__).resolve().parents[1]
# AC-1 transport: pad-edge host link + 40-bit core (sim/pt_transport_harness.sv wraps both).
TRANSPORT_RTL = ['pt_host_link.sv', 'pt_core.sv', 'pt_quad_link.sv', 'pt_quad_gearbox.sv', 'pt_linecode.sv',
                 'pt_dense_header.sv', 'pt_fifo.sv', 'pt_cells.sv', 'pt_pattern.sv']
ROOT = PROJECT.parents[1]


def check(out):
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text('{"status":"incomplete"}\n')
    sources = [PROJECT/'sim/tb_dense_service.sv']+[PROJECT/'rtl'/name for name in
               TRANSPORT_RTL]+[PROJECT/'sim/pt_transport_harness.sv', PROJECT/'sim/reference/pt_dense_transport.sv']
    checked_sources = sources+[Path(__file__).resolve()]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in checked_sources}
    results = []
    for phase, half, reject in [(p, 1.6, False) for p in (0, .4, 1.2, 2.4, 3.1)]+[(0, 2.0, True)]:
        label = f'phase-{phase}-half-{half}'
        bench = out/(label+'.vvp')
        subprocess.run(['iverilog', '-g2012', '-I', str(PROJECT/'rtl'), '-s', 'tb_dense_service',
                        '-P', f'tb_dense_service.HOST_HALF={half}', '-P', f'tb_dense_service.WIRE_PHASE={phase}',
                        '-P', f'tb_dense_service.EXPECT_REJECTION={int(reject)}', '-o', str(bench), *map(str, sources)],
                       check=True, capture_output=True)
        run = subprocess.run(['vvp', str(bench)], capture_output=True, text=True)
        (out/(label+'.log')).write_text(run.stdout+run.stderr)
        assert run.returncode == 0, run.stdout+run.stderr
        marker = 'LOW_RATE_REJECTED' if reject else 'DENSE_SERVICE_PASS'
        assert marker in run.stdout, run.stdout
        results.append(dict(phase_ns=phase, host_word_mhz=500/half, expected_overload=reject,
                            result=run.stdout.splitlines()[0]))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items()), 'Sources changed during run'
    result = dict(status='pass', paired_engine=True, cases=results, scope='functional RTL nominal dense wired service',
                  excluded=['physical timing', 'board pads/skew', 'clock tolerance and host interruptions'],
                  source_hashes=hashes)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/dense-service')
    args = parser.parse_args()
    check(args.output_dir.resolve())
