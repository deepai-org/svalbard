"""Clamped-input comparator clock charge diagnostic, not floating-node error."""
import argparse, hashlib, json, subprocess
from pathlib import Path
import numpy as np

def run_cases(R, P, W, cases, files):
    image = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    hashes = {str(p.relative_to(R)): sha(p) for p in files}
    subprocess.run(['docker', 'run', '--rm', '--platform', 'linux/arm64', '--network', 'none', '--cpus', '1', '--memory', '2g', '--entrypoint', '/bin/bash', '-v', f'{P}/analog:/screen:ro', '-v', f'{R}/ip/blocks/analog/wifi_80211b:/wifi:ro', '-v', f'{W}:/work', '--workdir', '/work', image, '-lc', 'for deck in *.spice; do ngspice -b "$deck" > "${deck%.spice}.log" 2>&1 || exit 1; done'], check=True, capture_output=True)
    assert hashes == {str(p.relative_to(R)): sha(p) for p in files}
    arrays = {}
    for c in cases:
        name = c['name']
        log = (W / (name + '.log')).read_text().lower()
        assert 'ngspice-46 done' in log and (not any((x in log for x in ['warning', 'error', 'aborted'])))
        a = np.loadtxt(W / (name + '.dat'), skiprows=1)
        assert a.shape[1] == 6 and a[-1, 0] >= 8e-09 and np.isfinite(a).all()
        arrays[name] = a
        c['artifacts_sha256'] = {ext: sha(W / (name + ext)) for ext in ['.spice', '.log', '.dat']}
    return (image, hashes, arrays)

def main():
    R = Path(__file__).resolve().parents[3]
    P = R / 'projects/programmable_transceiver_platform'
    parser = argparse.ArgumentParser()
    parser.add_argument('--fine', action='store_true')
    args = parser.parse_args()
    tag = 'adc-kickback-fine' if args.fine else 'adc-kickback'
    W = R / ('scratch/transceiver-' + tag)
    W.mkdir()
    base = (P / 'analog/adc/top_load.spice').read_text()
    cases = []
    for diff in [-0.4, -0.001, 0.001, 0.4]:
        for clocked in [False, True]:
            name = f'd{diff:g}_clk{int(clocked)}'
            s = base
            s = s.replace('DC 1.65 AC .5\n', f'DC {1.65 + diff / 2:.12g}\n').replace('DC 1.65 AC .5 180', f'DC {1.65 - diff / 2:.12g}')
            s = s.replace('VIP IP 0 1.65', f'VIP IP 0 {1.65 + diff / 2:.12g}').replace('VIN IN 0 1.65', f'VIN IN 0 {1.65 - diff / 2:.12g}')
            if clocked:
                s = s.replace('VC CLK 0 0', 'VC CLK 0 PWL(0 0 2n 0 2.1n 3.3 5n 3.3 5.1n 0)')
            s = s.replace('ac dec 3 1meg 1g', 'tran 1p 8n 0 1p' if args.fine else 'tran 2p 8n 0 2p').replace('wrdata /work/load.dat i(VP) i(VN) i(VU)', f'wrdata /work/{name}.dat i(VP) i(VN) v(QP) v(QN) v(CLK)')
            (W / (name + '.spice')).write_text(s)
            cases.append(dict(name=name, differential_v=diff, clocked=clocked))
    files = [P / 'analog/adc/top_load.spice', P / 'analog/adc/comparator.spice', R / 'ip/blocks/analog/wifi_80211b/rf_if_transmission_gate/rf_if_transmission_gate.spice']
    image, hashes, arrays = run_cases(R, P, W, cases, files)
    rows = []
    for diff in [-0.4, -0.001, 0.001, 0.4]:
        a = arrays[f'd{diff:g}_clk1']
        b = arrays[f'd{diff:g}_clk0']
        lo, hi = (2e-09, 4.9e-09)
        t = np.r_[lo, a[(a[:, 0] > lo) & (a[:, 0] < hi), 0], hi]
        current = np.column_stack([np.interp(t, a[:, 0], a[:, col]) - np.interp(t, b[:, 0], b[:, col]) for col in [1, 2]])
        charge = np.trapezoid(current, t, axis=0)
        rows.append(dict(differential_v=diff, window_ns=[2, 4.9], source_charge_c=charge.tolist(), differential_source_charge_c=float(charge[0] - charge[1]), peak_differential_current_a=float(np.max(abs(current[:, 0] - current[:, 1]))), output_difference_v=float(np.interp(4.9e-09, a[:, 0], a[:, 3] - a[:, 4]))))
    report = dict(status='clamped_input_clock_charge_only', image=image, source_sha256=hashes, cases=cases, results=rows, limitations=['Ideal sources clamp input voltage; charge is not an observed floating-CDAC voltage error.', 'Reset-only subtraction retains clock-driven charge but does not identify individual device contributions.', 'Nominal bias and one clock slew; no noise, mismatch, extracted coupling or timestep convergence qualification.'])
    (P / 'evidence' / (tag + '-clamped.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(rows, indent=2))
if __name__ == '__main__':
    main()
