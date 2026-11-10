#!/usr/bin/env python3
"""Check shared storage owner changes with stopped host/output clocks."""
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
    sources = [PROJECT/'sim/tb_shared_egress_lifecycle.sv']+[PROJECT/'rtl'/name for name in
               ['pt_core.sv', 'pt_core_pair.sv', 'pt_pair_gearbox.sv', 'pt_dense_pair.sv',
                'pt_dense_pair_link.sv', 'pt_dense_header.sv', 'pt_fifo.sv']]+[PROJECT/'sim/reference/pt_dense_transport.sv']
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sources+[Path(__file__).resolve()]}
    subprocess.run(['iverilog', '-g2012', '-I', str(PROJECT/'rtl'), '-s', 'tb_shared_egress_lifecycle',
                    '-o', str(out/'bench.vvp'), *map(str, sources)], check=True, capture_output=True)
    run = subprocess.run(['vvp', str(out/'bench.vvp')], cwd=out, capture_output=True, text=True)
    (out/'simulation.log').write_text(run.stdout+run.stderr)
    assert run.returncode == 0 and 'SHARED_EGRESS_LIFECYCLE_PASS' in run.stdout, run.stdout+run.stderr
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    result = dict(status='pass', scope='stopped-clock disable/re-enable and wire/RF owner transitions in real RTL core',
                  source_hashes=hashes)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(run.stdout.strip())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/shared-egress-lifecycle')
    check(parser.parse_args().output_dir.resolve())
