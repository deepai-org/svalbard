"""Session-16 block calibration: ../s14/cal/blkcal.py unchanged (method in its docstring), on the s16 bench (chain16: netlist
fullfix16, ring route per job, default TIM-23 nominal 30 ohm + 75 fF).  Results in s16/cal/res/<tag>.json with route labels.
sf / fs use the tt LSB estimate (10.5 ps/code) for the code step.

    python3 cal16.py '{"tag":"c_ssp3125_0","corner":"ss","pess":true,"vdd":3.15,"rate":3.125e9,"codes":[...]}'
"""
import sys, json
from pathlib import Path
H = Path(__file__).resolve().parent
import chain16
sys.path.insert(0, str(H.parent / 's14' / 'cal'))
import blkcal
blkcal.HERE = H / 'cal'
blkcal.LSB.update(sf=10.5, fs=10.5)

if __name__ == '__main__':
    kw = chain16.setup(json.loads(sys.argv[1]))
    o = blkcal.run(**kw)
    o.update(route_ohm_F=list(chain16._route), net=str(kw['top_ext']), rate=kw.get('rate', 3.125e9), vdd=kw.get('vdd'), temp=kw.get('temp', 32))
    (H / 'cal' / 'res' / f'{o["tag"]}.json').write_text(json.dumps(o, indent=1))
