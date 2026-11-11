#!/usr/bin/env python3
"""pt_pll_vreg2 on its extracted layout, with the unchanged pll_vreg.py benches.
The benches drive a 6-port `pt_pll_vreg`; this wraps the 8-port dual cell so that VOUT = one output under test
and the other output carries a 7 mA DC load (the other ring) with both BYP pins tied to the bench BYP.
    PLL_VREG_WORK=<dir> PLL_VREG2_EXT=<ext.spice> python3 pll_vreg2_ext.py <part> [out]
part: sch (DC, PSRR 5 corners, start-up, bypass) | tt | ss | ff (ring at 78 MHz, 60 mV; ff at VCTRL 1.1 V)
out:  cdr (default: the open-loop follower, worst case) | tx (the follower inside the OTA loop)"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pll_vreg as pv  # noqa: E402

EXT = Path(os.environ.get('PLL_VREG2_EXT', str(HERE / 'generated/pt_pll_vreg2.ext.spice')))
OUT = sys.argv[2] if len(sys.argv) > 2 else 'cdr'


def ext_netlist(p=None, name='pt_pll_vreg'):
    a, b = ('VOUT', 'VOTHER') if OUT == 'tx' else ('VOTHER', 'VOUT')
    return EXT.read_text() + (f'.subckt {name} VIN VOUT VSS BYP ATB_OUT ATB_G\n'
                              f'XD VIN {a} {b} VSS BYP BYP ATB_OUT ATB_G pt_pll_vreg2\nIOTHER VOTHER VSS 7m\n.ends {name}\n')


pv.netlist = ext_netlist
_run = pv.run


def _run_v2(sub, n, text, outvec):
    # the shared gate sits one level down in the wrapper (x1.xd.VG)
    return _run(sub, n, text.replace('x1.VG', 'x1.xd.VG'), outvec.replace('x1.VG', 'x1.xd.VG'))


pv.run = _run_v2


def main(part):
    W = pv.W
    tag = f'v2{OUT}'
    out = dict(model=str(EXT), output=OUT)
    if part == 'sch':
        out['dc'] = {f'{c}_{t}_{vin}_{il}': pv.dc(c, t, vin, il, tag=tag) for c, t in
                     (('typical', 27), ('ss', 32), ('ff', 22), ('ss', 22), ('ff', 32)) for vin in (3.05, 3.25, 3.35) for il in (3, 8)}
        out['psrr'] = {f'{c}_{t}': pv.psrr(c, t, 3.15, 6, tag=tag) for c, t in
                       (('typical', 27), ('ss', 32), ('ff', 22), ('ss', 22), ('ff', 32))}
        out['startup'] = {f'{c}_{t}': [pv.startup(c, t, r) for r in ('1u', '10u')] for c, t in (('typical', 27), ('ss', 32), ('ff', 22))}
        out['bypass'] = {f'{c}_{t}': pv.dc(c, t, 3.05, 8, byp=1, tag=tag) for c, t in (('typical', 27), ('ss', 32), ('ff', 22))}
    else:
        c, t, vct = {'tt': ('typical', 27, 1.5), 'ss': ('ss', 32, 1.5), 'ff': ('ff', 22, 1.1)}[part]
        out['ring'] = pv.ring_ripple(c, t, 3.25, 0.06, 78.125e6, 0, vct=vct)
    (W / f'v2-{OUT}-{part}.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != 'dc'})[:1500])


if __name__ == '__main__':
    main(sys.argv[1])
