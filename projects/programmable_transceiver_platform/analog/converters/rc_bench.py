#!/usr/bin/env python3
"""Extracted key-metric runs of the published converters on the R+C netlist from rcext.py (one deck at a time).

  rc_bench.py fft <block> --net N --corner ss 32 3.15 --fs 40e6 [--n 64 --cycles 31 --amp 0.8] --tag T
  rc_bench.py dac <block> --net N --corner ss 32 3.15 [--codes -512,...] --tag T

fft: benches.adc_fft unchanged (coherent N-point sine, 2-way interleaved, ACQ code 0, CMOS clock, ideal VREF 1.0 V and
     VCM 1.65 V sources), reported raw and after the per-core offset/gain correction; plus conversions with no DONE in
     time ('missing_done') and the worst DONE time.
dac: benches.dac_deck + benches.dac_eval unchanged (codes held two 25 ns periods, 100 fF per output, endpoint fit).
Writes generated/<block>-rc-<tag>.json (netlist and bench sha256 inside). Limits are the benches' own (not changed):
ADC 'clean' 8-bit class; DAC static error <= 4 LSB (CLEAN_LSB, 10-bit codes), full scale +-1.0 V target.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / 'lib')]
import benches as B  # noqa: E402
import convkit as ck  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('kind', choices=['fft', 'dac'])
ap.add_argument('block')
ap.add_argument('--net', required=True)
ap.add_argument('--corner', nargs=3, default=['typical', '27', '3.3'])
ap.add_argument('--fs', type=float, default=40e6)
ap.add_argument('--n', type=int, default=64)
ap.add_argument('--cycles', type=int, default=31)
ap.add_argument('--amp', type=float, default=0.8)
ap.add_argument('--codes', default='-512,-384,-256,-128,-1,0,1,127,255,383,511')
ap.add_argument('--tag', required=True)
a = ap.parse_args()
top = f'pt_{a.block}'
corner = (a.corner[0], float(a.corner[1]), float(a.corner[2]))
W = HERE.parents[3] / 'scratch' / 'converters' / f'rc_{a.block}_{a.tag}'
if W.exists():
    shutil.rmtree(W)
W.mkdir(parents=True)
shutil.copy(a.net, W / 'ext.spice')
rec = dict(block=a.block, kind=a.kind, tag=a.tag, netlist=str(a.net), netlist_sha256=ck.sha256(a.net),
           bench_sha256=ck.sha256(HERE / 'benches.py'), gds_sha256=ck.sha256(HERE / 'generated' / f'{a.block}.gds'),
           corner=list(corner))
if a.kind == 'fft':
    m = B.adc_fft(W, 'ext.spice', top, corner=corner, n=a.n, cycles=a.cycles, period=1 / a.fs, acq=6e-9, amp=a.amp,
                  ilen=1, workers=1, chunk=16, acq_code=0)
    rec.update(m)
    print(a.tag, 'raw', m['raw'], 'corr', m.get('per_core_offset_gain_corrected'), 'missing', m['missing_done'],
          'tdone', m['t_done_ns_max'], flush=True)
else:
    codes = [int(x) for x in a.codes.split(',')]
    d = B.dac_deck('ext.spice', corner[0], corner[1], corner[2], top=top, codes=codes, period=25e-9)[0]
    r = ck.ngspice(W, 'tb.spice', d, timeout=30 * 3600)
    m = B.meas(r.stdout)
    ev = B.dac_eval(m, codes, len(codes))
    rec.update(rc=r.returncode, codes=codes, meas=m, eval=ev)
    if ev:
        err = ev['code_error_lsb']
        vals = [err[str(c)] + c for c in sorted(codes)]
        rec['monotonic_at_sampled_codes'] = all(x < y for x, y in zip(vals, vals[1:]))
        rec['max_abs_error_lsb'] = max(abs(v) for v in err.values())
    print(a.tag, r.returncode, json.dumps(ev), m.get('idd'), flush=True)
(HERE / 'generated' / f'{a.block}-rc-{a.tag}.json').write_text(json.dumps(rec, indent=1, default=str) + '\n')
shutil.rmtree(W, ignore_errors=True)
