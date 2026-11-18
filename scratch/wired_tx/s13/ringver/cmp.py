"""Phase spacing of the TX ring: laid-out version (extracted pll_ring_core, XC0b gate on ENB, layout of 11 Nov) against
the committed ring cell (e7b4d14: XC0b gate on P1), the latter as the same extracted netlist with that one gate moved
(parasitics of the old layout = best estimate; no layout of the committed cell exists for pt_pll_ring_core).
    python3 cmp.py           -> ringver/cmp.json"""
import sys, json, re
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 's12'))
import chain as CH
from chain import R
ORIG = R.RING
OLD = ORIG.read_text()
pat = r'^(X59 N1) ENB (VSS VSS nfet_03v3 .*w=0\.5u l=0\.28u)$'
assert len(re.findall(pat, OLD, re.M)) == 1
NEW = re.sub(pat, r'\1 P1 \2', OLD, flags=re.M)
(HERE / 'ring_committed.ext.spice').write_text(NEW)
T = json.loads((HERE.parent.parent / 's12' / 'tune.json').read_text())
out = {}
for key in ('ss_32_2.69_0_390.6_0', 'typical_27_2.95_0_390.6_0', 'ff_22_3.01_0_390.6_0', 'ss_32_2.69_0_390.6_1', 'ss_32_2.69_0_337.5_0'):
    corner, temp, vring, band, f, pess = key.split('_'); vc = T[key]['vctrl']
    for ver, path in (('layout', ORIG), ('committed', HERE / 'ring_committed.ext.spice')):
        R.RING = Path(path)
        r = R.cal(corner, int(temp), float(vring), int(band), [vc], pess=bool(int(pess)), work=HERE / f'w_{ver}')[vc]
        out[f'{key}|{ver}'] = dict(vctrl=vc, f_mhz=r.get('f_mhz'), slot_err_ps=r.get('slot_err_ps'), duty=r.get('duty'))
        print(key, ver, r.get('f_mhz'), r.get('slot_err_ps'), flush=True)
        (HERE / 'cmp.json').write_text(json.dumps(out, indent=1))
