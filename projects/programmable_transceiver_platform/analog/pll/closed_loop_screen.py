"""First actual transistor loop connection; short transient is not lock evidence."""
import hashlib, json, subprocess
from pathlib import Path
import numpy as np

def closed_loop_deck(base, split=False):
    if split:
        base = base.replace('/vco/ring_vco.spice', '/screen/pll/ring_vco_split.spice').replace('/screen/rf_rx_candidate.spice', '/screen/rf_rx_candidate_split.spice').replace('0 pt_rf_rx_candidate', '0 REGEN pt_rf_rx_candidate_split').replace('.control', 'VREGEN REGEN 0 1.08\n.control')
    assert base.count('VC CTRL 0 1.08') == 1
    extra = '.include /screen/pll/charge_pump.spice\n.include /screen/pll/loop_filter.spice\nIP BPCP 0 20u\nIN VDIV BNCP 20u\nXCP UP DN PUMP BPCP BNCP VDIV 0 pt_charge_pump\nVSENSE PUMP CTRL 0\nXFILT CTRL 0 pt_loop_filter\n.ic v(CTRL)=1.08 v(XFILT.Z)=1.08\n'
    d = base.replace('VC CTRL 0 1.08\n', '').replace('.control', extra + '.control')
    d = d.replace('/work/chain.dat', '/work/closed.dat').replace('v(UP) v(DN)\n', 'v(UP) v(DN) v(CTRL) v(XFILT.Z) i(VSENSE) v(REF)\n')
    return d

def measure_loop_windows(a, windows):
    rows = []
    for lo, hi in windows:
        w = a[(a[:, 0] >= lo * 1e-09) & (a[:, 0] <= hi * 1e-09)]
        t = w[:, 0]
        v = w[:, 1]
        i = np.where((v[:-1] < 0) & (v[1:] >= 0))[0]
        e = t[i] + (t[i + 1] - t[i]) * -v[i] / (v[i + 1] - v[i])
        rows.append(dict(window_ns=[lo, hi], vco_frequency_hz=float((len(e) - 1) / (e[-1] - e[0])) if len(e) > 3 else None, control_range_v=[float(w[:, 14].min()), float(w[:, 14].max())], control_mean_v=float(np.trapezoid(w[:, 14], t) / (t[-1] - t[0])), gate_range_v=[float(w[:, 10].min()), float(w[:, 10].max())]))
    return rows

def main(split=False):
    O = Path('/work')
    base = Path('/chain/chain.spice').read_text()
    d = closed_loop_deck(base, split=split)
    p = O / 'closed.spice'
    p.write_text(d)
    with (O / 'closed.log').open('w') as log:
        subprocess.run(['ngspice', '-b', str(p)], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=900)
    a = np.loadtxt(O / 'closed.dat', skiprows=1)
    assert a.shape[1] == 18 and np.isfinite(a).all() and (a[-1, 0] > 3.2e-07)
    rows = measure_loop_windows(a, ((100, 200), (220, 320)))
    r = dict(status='short_split_bias_closed_loop_not_lock_qualification' if split else 'short_closed_transistor_loop_not_lock_qualification', windows=rows, artifacts_sha256={s: hashlib.sha256((O / ('closed' + s)).read_bytes()).hexdigest() for s in ('.spice', '.dat', '.log')}, limitations=['321ns with precharged filter, seeded VCO and prebiased LNA; no cold startup.', 'Only a few reference cycles, no lock/acquisition/stability or phase-noise claim.', 'Actual divide128/PFD/pump/filter/VCO, but ideal external bias sources/reference/sampling clocks.', 'Filter values are preliminary; no PVT/mismatch or physical parasitics.'])
    (O / 'result.json').write_text(json.dumps(r, indent=2) + '\n')
    print(json.dumps(r, indent=2))
if __name__ == '__main__':
    main()
