"""Linear stationary phase-noise window sensitivity, not coupled-chip closure."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from three_cap_thermal_noise import spectrum
P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P/'system_model/connected'))
from three_cap_resistor_noise import ResistorNoiseFilter


def main():
    source = P/'evidence/stressed-three-cap-quality-mode1-launch.json'
    launch = json.loads(source.read_text())
    v = launch['filter_values']
    ip = 100e-6*launch['gain_scales']['icp']
    kv = 200e6*launch['gain_scales']['kvco']
    model = ResistorNoiseFilter(noise_bins=128, **v)
    f = model.noise_frequency
    s = 2j*np.pi*f
    r, cf, cs, r3, c3 = (v[k] for k in ('r','cf','cs','r3','c3'))
    y = np.zeros((len(f),3,3), complex)
    y[:,0,0] = s*cf+1/r+1/r3
    y[:,1,1] = s*cs+1/r
    y[:,2,2] = s*c3+1/r3
    y[:,0,1] = y[:,1,0] = -1/r
    y[:,0,2] = -1/r3+ip*kv/(2437/40)/s
    y[:,2,0] = -1/r3
    z = np.linalg.solve(y, np.broadcast_to([[1,1],[-1,0],[0,-1]], (len(f),3,2)))[:,2,:]
    current_psd = np.array([4*1.380649e-23*300/r,4*1.380649e-23*300/r3])
    np.testing.assert_allclose(abs(z)**2*current_psd,
                               spectrum(f,v,300,True,icp=ip,kvco=kv), rtol=1e-12)
    transfer = z*kv/(1j*f[:,None])
    seeds = [1249]+list(range(128))
    coefficients = np.array([
        np.sum(model.noise_amplitude.T*np.exp(1j*np.random.default_rng(seed).uniform(0,2*np.pi,(2,128)).T)*transfer, axis=1)
        for seed in seeds])
    rows = []
    for count in (2048,4096):
        # Stationary linear response over a representative mode-1 traffic duration.
        times = (np.arange(count)+.5)*6.5536e-6/count
        phase = np.real(coefficients @ np.exp(2j*np.pi*f[:,None]*times))
        raw = np.sqrt(np.mean(phase**2,axis=1))
        centered = np.std(phase,axis=1)
        rows.append(dict(samples=count,seed1249_raw_rms_rad=float(raw[0]),
                         seed1249_mean_removed_rms_rad=float(centered[0]),
                         raw_quantiles_rad=np.quantile(raw[1:],[0,.05,.5,.95,1]).tolist(),
                         mean_removed_quantiles_rad=np.quantile(centered[1:],[0,.05,.5,.95,1]).tolist()))
        if count == 2048:
            previous = np.stack([raw,centered])
        else:
            max_change = float(np.max(abs(np.stack([raw,centered])-previous)))
            assert max_change < 1e-6
    report = dict(status='stationary_linear_window_sensitivity_measured',
        window_s=6.5536e-6, bins=128, seeds=seeds, rows=rows,
        sampling_max_rms_change_rad=max_change,
        limitations=['Stationary averaged PLL, not startup or nonlinear fractional clock.',
                     'Window starts at zero; not aligned to actual coupled traffic start.',
                     'Mean removal only approximates constant-phase correction, not fitted chip gain.',
                     'Seed quantiles are descriptive, not a yield estimate or confidence guarantee.',
                     'Resistor-only finite-band noise; no acceptance claim.'],
        source_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (source,Path(__file__),P/'verification/three_cap_thermal_noise.py',
                                 P/'system_model/connected/three_cap_resistor_noise.py')})
    (P/'evidence/resistor-noise-window-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(rows=rows,sampling_max_rms_change_rad=max_change),indent=2))

if __name__ == '__main__':
    main()
