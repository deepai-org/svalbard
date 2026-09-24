"""Four-point tuning screen with actual divider/RF loading; not PLL qualification."""
import hashlib, json, subprocess
from pathlib import Path
import numpy as np

def main(split=False):
    O = Path('/work')
    base = Path('/chain/chain.spice').read_text()
    rows = []
    if split:
        base = base.replace('/vco/ring_vco.spice', '/screen/pll/ring_vco_split.spice').replace('/screen/rf_rx_candidate.spice', '/screen/rf_rx_candidate_split.spice').replace('0 pt_rf_rx_candidate', '0 REGEN pt_rf_rx_candidate_split').replace('.control', 'VREGEN REGEN 0 1.08\n.control')
    for control in (1.08, 1.16, 1.24, 1.3):
        name = f'v{control:g}'
        d = base.replace('VC CTRL 0 1.08', f'VC CTRL 0 {control}').replace('tran 2p 321n 0 2p uic', 'tran 2p 41n 0 2p uic').replace('/work/chain.dat', f'/work/{name}.dat')
        p = O / (name + '.spice')
        p.write_text(d)
        with (O / (name + '.log')).open('w') as log:
            subprocess.run(['ngspice', '-b', str(p)], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        a = np.loadtxt(O / (name + '.dat'), skiprows=1)
        assert np.isfinite(a).all() and a[-1, 0] > 4e-08
        w = a[(a[:, 0] >= 2e-08) & (a[:, 0] <= 4e-08)]
        t = w[:, 0]
        v = w[:, 1]
        i = np.where((v[:-1] < 0) & (v[1:] >= 0))[0]
        e = t[i] + (t[i + 1] - t[i]) * -v[i] / (v[i + 1] - v[i])
        assert len(e) > 40
        gate = [float(w[:, 10].min()), float(w[:, 10].max())]
        assert gate[0] > 1.4 and gate[1] < 1.6
        rows.append(dict(control_v=control, frequency_hz=float((len(e) - 1) / (e[-1] - e[0])), gate_range_v=gate, artifacts_sha256={s: hashlib.sha256((O / (name + s)).read_bytes()).hexdigest() for s in ('.spice', '.dat', '.log')}))
        print(json.dumps(rows[-1]), flush=True)
    r = dict(status='independent_regen_bias_tuning_screen_not_pll' if split else 'actual_divider_loaded_wide_vco_tuning_not_pll', **dict(regen_bias_v=1.08) if split else {}, cases=rows, slopes_hz_per_v=[(b['frequency_hz'] - a['frequency_hz']) / (b['control_v'] - a['control_v']) for a, b in zip(rows, rows[1:])], limitations=['Nominal seeded/prebiased RF hierarchy; no acquisition, phase noise or process/mismatch.', 'Four tuning points do not establish global monotonicity or a loop-stability model.', 'Actual mixer/buffer load but ideal biases/sample clocks; actual seven-stage divider/interface/PFD load.'])
    (O / 'result.json').write_text(json.dumps(r, indent=2) + '\n')
if __name__ == '__main__':
    main()
