"""wtx8_casbias transient on the EXTRACTED cell (s18/casbias/wtx8_casbias.ext.spice, C-only, flat) or the schematic.
   python3 tran.py ext|sch corner temp vdd   ->  tran_<src>_<corner>_<temp>_<vdd>.json
Sequence (load 0.3 pF on CASCODE, no DC):  0-0.2 us unpowered (VDD 0, CB_EN 0);  VDD ramp 0 -> vdd 0.2-2.2 us with CB_EN 0;
CB_EN 1 at 3 us (start-up);  steady 5-6 us (ripple);  CB_EN 0 at 6 us;  1 at 7.5 us;  0 at 9.5 us;  VDD ramp down 10.5-11.5 us.
Known-answer / negative control: `neg` mode runs the same deck with the replica shunt removed (MR fingers deleted): the output
must then exceed the 4.6 V limit (the bench must be able to fail)."""
import json, os, re, subprocess, sys
from pathlib import Path
import numpy as np
M = '/home/ubuntu/svalbard/scratch/transceiver-pad-pdk/ngspice'
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EXT = REPO / 'scratch/wired_tx/s18/casbias/wtx8_casbias.ext.spice'
sys.path.insert(0, str(REPO / 'projects/programmable_transceiver_platform/analog/wired_tx'))


def run(src, corner, temp, vdd, neg=False):
    if src == 'ext':
        sub = EXT.read_text()
    else:
        import wtx8_casbias as C
        sub = C.netlist()
    if neg:
        n0 = len(re.findall(r'pfet_06v0', sub))
        sub = '\n'.join(l for l in sub.splitlines() if not (l.startswith('X') and ' VDD VDD CASCODE CASCODE pfet_06v0' in l))
        assert len(re.findall(r'pfet_06v0', sub)) == n0 - 5, 'negative control did not remove the five MR fingers'
    lib = {'tt': 'typical'}.get(corner, corner)
    tag = f'{src}_{corner}_{temp}_{vdd}' + ('_neg' if neg else '')
    d = f"""* wtx8_casbias transient {tag}
.include {M}/design.ngspice
.lib {M}/sm141064.ngspice {lib}
.temp {temp}
.option savecurrents=0 method=gear
{sub}
XCB CB_EN CASCODE VDD 0 wtx8_casbias
CL CASCODE 0 0.3p
VD VDD 0 PWL(0 0 0.2u 0 2.2u {vdd} 10.5u {vdd} 11.5u 0)
VE CB_EN 0 PWL(0 0 3u 0 3.001u {vdd} 6u {vdd} 6.001u 0 7.5u 0 7.501u {vdd} 9.5u {vdd} 9.501u 0)
.tran 0.1n 12u
.control
run
wrdata {tag}.txt v(CASCODE) v(VDD) i(VD)
.endc
.end
"""
    (HERE / f'{tag}.sp').write_text(d)
    r = subprocess.run(['ngspice', '-b', f'{tag}.sp'], cwd=HERE, capture_output=True, text=True, env=dict(os.environ, OMP_NUM_THREADS='1'))
    (HERE / f'{tag}.log').write_text(r.stdout[-4000:] + r.stderr[-4000:])
    a = np.loadtxt(HERE / f'{tag}.txt')
    t, vc, vd, idd = a[:, 0], a[:, 1], a[:, 3], a[:, 5]
    w = lambda x, y: (t >= x) & (t <= y)
    res = dict(tag=tag, unpowered_max_V=round(vc[w(0, 0.2e-6)].max(), 4),
               cb0_max_minus_vdd_mV=round(1e3 * max((vc - vd)[w(0, 3e-6)].max(), (vc - vd)[w(6.4e-6, 7.5e-6)].max(), (vc - vd)[w(9.9e-6, 10.5e-6)].max()), 1),
               cb0_after_toggle_settle_ns=None, powerdown_max_minus_vdd_mV=round(1e3 * (vc - vd)[w(10.5e-6, 12e-6)].max(), 1),
               ramp_max_minus_vdd_mV=round(1e3 * (vc - vd)[w(0.2e-6, 2.2e-6)].max(), 1),
               steady_V=round(vc[w(5e-6, 6e-6)].mean(), 4), ripple_mVpp=round(1e3 * np.ptp(vc[w(5e-6, 6e-6)]), 1),
               peak_V=round(vc.max(), 4), steady2_V=round(vc[w(9e-6, 9.5e-6)].mean(), 4),
               startup_ns=None, i_vdd_boost_uA=round(-1e6 * idd[w(5e-6, 6e-6)].mean(), 1), i_vdd_off_uA=round(-1e6 * idd[w(2.5e-6, 2.9e-6)].mean(), 2),
               after_off_V=round(vc[w(7.3e-6, 7.5e-6)].mean(), 4), vdd=vdd, end_V=round(vc[w(11.9e-6, 12e-6)].mean(), 3))
    m = w(6e-6, 7.5e-6)
    hi = np.where(vc[m] - vd[m] > 0.01)[0]
    res['cb0_after_toggle_settle_ns'] = round(1e9 * (t[m][hi[-1]] - 6e-6), 0) if len(hi) else 0.0
    m = w(3e-6, 6e-6)
    hit = np.where(vc[m] >= res['steady_V'] - 0.02)[0]
    res['startup_ns'] = round(1e9 * (t[m][hit[0]] - 3e-6), 0) if len(hit) else None
    (HERE / f'{tag}.json').write_text(json.dumps(res, indent=1))
    os.remove(HERE / f'{tag}.txt')
    return res


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), neg='neg' in sys.argv[5:])))
