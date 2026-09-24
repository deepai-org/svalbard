"""Matched amplitude comparison; no scoring of incomplete simulation output."""
import hashlib, json, math
from pathlib import Path
import numpy as np

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
from check_sar_sampler_amplitude import sampler_frames

def main():
    R = Path(__file__).resolve().parents[3]
    P = R / 'projects/programmable_transceiver_platform'
    rows = []
    for label, amplitude, source in [('400', 0.4, 'sar-reference-clamped'), ('100', 0.1, 'sar-amplitude-bank1')]:
        B = R / f'scratch/transceiver-sar-driver-damping-{label}-prepared'
        W = R / f'scratch/transceiver-sar-driver-damping-{label}'
        m = json.loads((B / 'manifest.json').read_text())
        assert sha(B / 'baseline.spice') == m['artifacts_sha256']['baseline.spice']
        s = (B / 'baseline.spice').read_text()
        cell = (P / 'analog/adc/sample_driver_headroom.spice').read_text().replace('RC X Z 100', 'RC X Z 2k').rstrip()
        assert s.count(cell) == 1
        s = s.replace(cell, '.include /screen/adc/sample_driver_headroom.spice')
        assert s == (R / ('scratch/transceiver-' + source + '-prepared/baseline.spice')).read_text()
        row = dict(amplitude_v=amplitude, completed=False, status='pending', preparation_sha256=sha(B / 'manifest.json'))
        if (W / 'result.json').exists():
            r = json.loads((W / 'result.json').read_text())
            assert r['sources_before'] == r['sources_after'] and sha(W / 'baseline.spice') == sha(B / 'baseline.spice')
            for ext, d in r['artifacts_sha256'].items():
                assert sha(W / ('baseline' + ext)) == d
            errors = [l for l in (W / 'baseline.log').read_text().splitlines() if any((k in l.lower() for k in ('warning', 'error', 'aborted', 'timestep too small')))]
            row.update(status='terminal', returncode=r['returncode'], timed_out=r['timed_out'], errors=errors)
            if r['returncode'] == 0 and (not r['timed_out']) and (not errors):
                with (W / 'baseline.dat').open() as f:
                    h = f.readline().lower().split()
                a = np.loadtxt(W / 'baseline.dat', skiprows=1)
                frames = sampler_frames(a, h, amplitude)
                row.update(completed=True, frames=frames, waveform_sha256=sha(W / 'baseline.dat'), result_sha256=sha(W / 'result.json'))
        donor = R / ('scratch/transceiver-' + source)
        dr = json.loads((donor / 'result.json').read_text())
        assert dr['returncode'] == 0 and (not dr['timed_out'])
        assert sha(donor / 'baseline.dat') == dr['artifacts_sha256']['.dat']
        with (donor / 'baseline.dat').open() as f:
            dh = f.readline().lower().split()
        da = np.loadtxt(donor / 'baseline.dat', skiprows=1)
        dt = da[:, 0]
        reference = []
        for hold, target in [(70, amplitude), (120, -amplitude), (170, amplitude)]:

            def dv(n, ns):
                return float(np.interp(ns * 1e-09, dt, da[:, dh.index('v(' + n + ')')]))
            bits = [dv('d' + str(k), hold + 39) for k in range(8)]
            assert all((v < 0.33 or v > 2.97 for v in bits))
            code = sum((int(v > 1.65) * 2 ** k for k, v in enumerate(bits)))
            reference.append(dict(hold_ns=hold, final_code=code, code_error=code - math.floor(128 - 128 * target), held_error_at_clock_v=dv('hp', hold + 0.5) - dv('hn', hold + 0.5) - target))
        row['baseline_frames'] = reference
        row['baseline_waveform_sha256'] = sha(donor / 'baseline.dat')
        rows.append(row)
    out = dict(completed=all((r['completed'] for r in rows)), adopted=False, cases=rows, limitations=['Nominal ideal rails and ideal clocks; two amplitudes do not qualify a transfer curve.', 'Correct selected final codes can coexist with offset, settling and input-history errors.'])
    (P / 'evidence/sar-driver-damping.json').write_text(json.dumps(out, indent=2) + '\n')
    for r in rows:
        print(r['amplitude_v'], r['status'], [f['final_code'] for f in r.get('frames', [])])
if __name__ == '__main__':
    main()
