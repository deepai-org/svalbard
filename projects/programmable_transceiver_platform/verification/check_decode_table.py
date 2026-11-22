#!/usr/bin/env python3
"""Exhaustive decode check of the macro's static control ports against an INDEPENDENT table.
verification/decode_table/ was written by the independent reviewer of commit 3cff484 (scratch/reviews/dg6-review/q1):
model.py is a table derived from integration/chips/ctl_ports.txt and the analog owners' pin files, not from the RTL;
gen.py / run_q1.py force the register file's active fields in the real macro (every legal value of every field, 600
random configurations, all 128 fast-gain words: about 3650 vectors) and ana_q1.py compares every static c_* port.
Passes only with 0 mismatching ports. Runs the both-halves build and each chip view (PT_CHIP 3, 1, 2; on a chip only its
fields are driven and the ports with a consumer on that chip compared). About 3 minutes per view (iverilog)."""
import shutil, subprocess, sys, tempfile, os
from pathlib import Path
HERE = Path(__file__).resolve().parent / 'decode_table'
for chip in sys.argv[1:] or ['3', '1', '2']:      # PT_CHIP: both halves, pt_rf, pt_wired (split, D4)
  with tempfile.TemporaryDirectory() as t:
    for f in ('gen.py', 'model.py', 'run_q1.py', 'ana_q1.py'): shutil.copy(HERE / f, t)
    env = dict(os.environ, OMP_NUM_THREADS='1', PT_CHIP=chip, PT_PROJECT=str(HERE.parents[0] if HERE.name == 'verification' else HERE.parents[1]))
    r = subprocess.run([sys.executable, 'run_q1.py'], cwd=t, capture_output=True, text=True, env=env)
    if r.returncode: sys.exit(f'DECODE_TABLE_CHECK_FAIL: PT_CHIP={chip}: run\n' + (r.stdout + r.stderr)[-3000:])
    a = subprocess.run([sys.executable, 'ana_q1.py'], cwd=t, capture_output=True, text=True, env=env)
    print(f'PT_CHIP={chip}:', a.stdout.strip())
    if a.returncode or 'mismatching ports: 0' not in a.stdout: sys.exit(f'DECODE_TABLE_CHECK_FAIL: PT_CHIP={chip}')
print('DECODE_TABLE_CHECK_PASS')
