"""pt_lo_pfdcp (published, extracted) charge-pump UP current vs VTUNE: FB held low, REF clocked (UP latched on),
VTUNE swept 2.2 V -> VDD by a source; ceiling = VTUNE where |I_up| falls to 80 % of its value at 1.6 V.
ICP = 3 (100 uA, the operating code). usage: bench.py [ibias_dir: sink|source]"""
import sys, json, shutil
from pathlib import Path
T = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'
sys.path.insert(0, T)
import timing_flow as tf
H = Path(__file__).resolve().parent
d = sys.argv[1] if len(sys.argv) > 1 else 'sink'
TEMP = dict(tt=27, ss=32, ff=22, sf=27, fs=27)
res = []
for c in ('tt', 'ss', 'ff', 'sf', 'fs'):
    for v in (3.15, 3.5):
        wd = H / 'runs' / f'{c}_{v}_{d}'; wd.mkdir(parents=True, exist_ok=True)
        shutil.copy(Path(T) / 'generated/lo_pfdcp.ext.spice', wd / 'dut.spice')
        xs = [round(2.2 + 0.05 * k, 3) for k in range(int(round((v - 0.05 - 2.2) / 0.05)) + 1)]
        pw = ['0 1.6', '155u 1.6'] + [f'{(156 + 2 * k) * 1e-6:.6g} {x} {(158 + 2 * k) * 1e-6 - 1e-8:.8g} {x}' for k, x in enumerate(xs)]
        pwl, tend = ' '.join(pw), f'{(158 + 2 * len(xs)) * 1e-6:.6g}'
        ib = 'IB ib 0 10u' if d == 'sink' else 'IB 0 ib 10u'
        mc = {'tt': 'typical'}.get(c, c) if c in ('tt', 'ss', 'ff') else 'typical'
        deck = tf.header(c, TEMP[c]) + f'.lib {tf.MODELS}/sm141064.ngspice mimcap_{mc}\n.lib {tf.MODELS}/sm141064.ngspice moscap_{mc}\n' + f""".include dut.spice
VDD vdd 0 {v}
VEN en 0 {v}
VPRE pre 0 0
VFB fb 0 0
VREF ref 0 pulse(0 {v} 150u 0.2n 0.2n 9.8n 20n)
VI0 i0 0 {v}
VI1 i1 0 {v}
{ib}
VVT vt 0 pwl({pwl})
X1 ref fb en pre ib vt vdd 0 i0 i1 pt_lo_pfdcp
.tran 1n {tend}
.measure tran i16 avg i(VVT) from=153u to=154u
""" + ''.join(f'.measure tran i_{int(round(x * 100))} avg i(VVT) from={(156 + 2 * k + 1) * 1e-6:.6g} to={(156 + 2 * k + 2) * 1e-6:.6g}\n' for k, x in enumerate(xs)) + '.end\n'
        m = tf.ngspice(wd, 'cp', deck)
        i0 = m.get('i16')
        pts = sorted((int(k[2:]) / 100, val) for k, val in m.items() if k.startswith('i_') and k[2:].isdigit())
        ceil = next((x for x, val in pts if i0 and abs(val) < 0.8 * abs(i0)), None)
        r = dict(corner=c, vdd=v, i_up_1v6_ua=(i0 * 1e6 if i0 is not None else None), ceiling_80pct_v=ceil, below_vdd_mv=((v - ceil) * 1e3 if ceil else None),
                 curve=[(x, round(val * 1e6, 1)) for x, val in pts], errors=m['_errors'][:2])
        print({k: r[k] for k in r if k != 'curve'}, flush=True); res.append(r)
        if c == 'tt' and v == 3.15 and not i0:
            break
(H / f'results_{d}.json').write_text(json.dumps(res, indent=1))
