"""pt_lo_vtdet trip points: VTUNE ramp 2.3 -> VDD -> 2.3 V (20 us each way), DET rise / fall thresholds, supply current.
usage: bench.py [netlist]  -> results.json (one ngspice at a time)"""
import sys, json
from pathlib import Path
T = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'
sys.path.insert(0, T)
import timing_flow as tf
H = Path(__file__).resolve().parent
net = Path(sys.argv[1] if len(sys.argv) > 1 else H / 'lo_vtdet.spice').resolve()
TEMP = dict(tt=27, ss=32, ff=22, sf=27, fs=27)
res = []
for c in ('tt', 'ss', 'ff', 'sf', 'fs'):
    for v in (3.15, 3.5):
        wd = H / 'runs' / f'{c}_{v}'; wd.mkdir(parents=True, exist_ok=True)
        (wd / 'timing_cells.spice').write_text(Path(T, 'timing_cells.spice').read_text()); (wd / 'dut.spice').write_text(net.read_text())
        d = tf.header(c, TEMP[c]) + f""".include timing_cells.spice
.include dut.spice
VDD vdd 0 {v}
VEN en 0 {v}
VT vt 0 pwl(0 2.3 20u {v} 40u 2.3)
X1 vt en det vdd 0 pt_lo_vtdet
.tran 10n 40u
.measure tran vup find v(vt) when v(det)={v / 2} rise=1
.measure tran vdn find v(vt) when v(det)={v / 2} fall=1
.measure tran idd avg i(VDD) from=1u to=5u
.end
"""
        m = tf.ngspice(wd, 'vt', d)
        r = dict(corner=c, vdd=v, v_up=m.get('vup'), v_down=m.get('vdn'), hyst_mv=((m['vup'] - m['vdn']) * 1e3 if 'vup' in m and 'vdn' in m else None),
                 v_up_below_vdd_mv=((v - m['vup']) * 1e3 if 'vup' in m else None), idd_ua=-m.get('idd', 0) * 1e6, errors=m['_errors'][:2])
        print(r, flush=True); res.append(r)
(H / 'results.json').write_text(json.dumps(res, indent=1))
