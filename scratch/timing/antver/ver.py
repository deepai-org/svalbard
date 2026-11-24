"""Antenna 'sdA' estimator vs the KLayout deck. ver.py <block> <width> <off|on> [m5keep]
off: sdA nets get no diode (SD_MARGIN huge) -> deck violations give the deck ratio for nets the estimator flags.
on : normal build -> deck must be clean. DEBUG estimate per (net, level) in <tag>/debug.json."""
import sys, json, shutil, os
from pathlib import Path
T = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'); sys.path.insert(0, str(T)); sys.path.insert(0, str(T.parent))
import antenna_diodes as ad
import timing_flow as tf, gds_uniquify as gu, run_timing as rt
b, w, mode = sys.argv[1], float(sys.argv[2]), sys.argv[3]
H = Path(__file__).resolve().parent / f'{b}_{mode}'
if H.exists(): shutil.rmtree(H)
tf.SCRATCH = H / 'lay'; tf.GENERATED = H / 'gen'
shutil.copytree(T / 'generated' / 'fast', H / 'gen' / 'fast')
tf.gu = gu
ad.DEBUG = []
_orig = ad.requests_from_shapes
TERMS = []
def _wrap(shapes, terminals, *a, **k):
    TERMS.extend(terminals); return _orig(shapes, terminals, *a, **k)
ad.requests_from_shapes = _wrap
if mode == 'off': ad.SD_MARGIN = 1e9
kw = dict(max_row_width=w)
if len(sys.argv) > 4: kw['em'] = dict(m5_keep=[(12.25 + 70*k, 39.25 + 70*k) for k in range(8)])
if b in rt.PORT_ANTENNA_UM: kw['em'] = dict(kw.get('em') or {}, port_antenna_um=rt.PORT_ANTENNA_UM[b])
r = tf.build_layout(b, publish='never', **kw)
(H / 'terms.json').write_text(json.dumps(TERMS)); (H / 'debug.json').write_text(json.dumps([d for d in ad.DEBUG if d[4] > 0]))
print(json.dumps(dict(size=r['layout'].get('size_um'), diodes=len(r['layout'].get('antenna_diodes', [])), drc=r['drc_errors'],
    lvs=r['lvs'].get('unique_match'), pre=r['klayout'].get('precheck')), default=str)[:1500])
