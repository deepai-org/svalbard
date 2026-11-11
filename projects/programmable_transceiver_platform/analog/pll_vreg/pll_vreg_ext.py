#!/usr/bin/env python3
"""pt_pll_vreg on the extracted layout (generated/pt_pll_vreg.ext.spice): the same DC, AC PSRR, start-up,
bypass and extracted-ring ripple benches as pll_vreg.py, with the drawn regulator instead of the schematic.
    PLL_VREG_WORK=<dir> python3 pll_vreg_ext.py [sch|ring]   (needs <dir>/sch/pll_ring.ext.spice)
Writes <dir>/ldo-ext.json and <dir>/ldo-ext-ring.json (copies go to evidence/)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pll_vreg as pv  # noqa: E402

import os  # noqa: E402
EXT = Path(os.environ.get('PLL_VREG_EXT', str(HERE / 'generated/pt_pll_vreg.ext.spice')))   # PD28: candidate override


def ext_netlist(p=None, name='pt_pll_vreg'):
    t = EXT.read_text()
    if name != 'pt_pll_vreg':
        t = t.replace('.subckt pt_pll_vreg ', f'.subckt {name} ', 1)
    return t


pv.netlist = ext_netlist


def main(part):
    W = pv.W
    if part == 'ring':
        out = {}
        for c, t, fm, byp in (('typical', 27, 78.125e6, 0), ('ss', 32, 78.125e6, 0), ('ff', 22, 78.125e6, 0),
                              ('typical', 27, 156.25e6, 0), ('typical', 27, 10e6, 0), ('typical', 27, 78.125e6, 1)):
            k = f'{c}_{t}_fm{fm/1e6:g}_byp{byp}'
            out[k] = pv.ring_ripple(c, t, 3.25, 0.06, fm, byp); print(k, out[k], flush=True)
            (W / 'ldo-ext-ring.json').write_text(json.dumps(dict(model=str(EXT), results=out), indent=1))
        return
    out = dict(model=str(EXT), dc={}, psrr={}, startup={}, bypass={})
    for c, t in (('typical', 27), ('ss', 32), ('ff', 22), ('ss', 22), ('ff', 32)):
        for vin in (3.05, 3.25, 3.35):
            for il in (3, 8):
                out['dc'][f'{c}_{t}_{vin}_{il}'] = pv.dc(c, t, vin, il, tag='x')
        out['psrr'][f'{c}_{t}'] = pv.psrr(c, t, 3.15, 6, tag='x')
        print(c, t, out['psrr'][f'{c}_{t}']['worst_10_200MHz_dB'], out['dc'][f'{c}_{t}_3.05_8'], flush=True)
        (W / 'ldo-ext.json').write_text(json.dumps(out, indent=1))
    for c, t in (('typical', 27), ('ss', 32), ('ff', 22)):
        out['startup'][f'{c}_{t}'] = [pv.startup(c, t, r) for r in ('1u', '10u')]
        out['bypass'][f'{c}_{t}'] = pv.dc(c, t, 3.05, 8, byp=1, tag='x')
        (W / 'ldo-ext.json').write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'sch')
