"""Independent resistor-only linear noise audit; does not mutate live models."""
import json
from pathlib import Path
import numpy as np

P = Path(__file__).resolve().parents[1]
K = 1.380649e-23

def spectrum(freq, values, temperature, closed, *, icp=100e-6, kvco=200e6, divider=2437/40):
    r, cf, cs, r3, c3 = (values[k] for k in ('r','cf','cs','r3','c3'))
    s = 2j*np.pi*freq
    y = np.zeros((len(freq),3,3),complex)
    y[:,0,0] = s*cf+1/r+1/r3
    y[:,1,1] = s*cs+1/r
    y[:,2,2] = s*c3+1/r3
    y[:,0,1] = y[:,1,0] = -1/r
    y[:,0,2] = y[:,2,0] = -1/r3
    if closed:
        y[:,0,2] += icp*kvco/divider/s
    # Each resistor's Norton current enters one node and leaves the other.
    b = np.array([[1,1],[-1,0],[0,-1]],float)
    z = np.linalg.solve(y, np.broadcast_to(b,(len(freq),3,2)))
    return np.abs(z[:,2,:])**2 * np.array([4*K*temperature/r,4*K*temperature/r3])

def main():
    launch=json.loads((P/'evidence/three-cap-pad-quality-mode1-launch.json').read_text())
    v=launch['filter_values']; t=300.
    # Passive equilibrium excludes conserved common charge; verify one-sided PSD
    # normalization against kT(1/C3 - 1/Ctotal), independently of PLL feedback.
    f=np.geomspace(1e-2,1e12,30000)
    integrate=np.trapezoid
    measured=float(integrate(spectrum(f,v,t,False).sum(axis=1),f))
    expected=K*t*(1/v['c3']-1/(v['cf']+v['cs']+v['c3']))
    assert abs(measured/expected-1)<1e-3
    bands=[]
    for low,high in [(100,1e7),(1e3,1e8),(1e4,1e7)]:
        estimates=[]
        for n in [4000,8000]:
            f=np.geomspace(low,high,n)
            phase=spectrum(f,v,t,True)*(200e6/f[:,None])**2
            each=integrate(phase,f,axis=0)
            estimates.append(float(np.sqrt(each.sum())))
        assert abs(estimates[1]/estimates[0]-1)<1e-5
        bands.append(dict(low_hz=low,high_hz=high,phase_rms_rad=estimates[1],
                          equivalent_time_rms_s=estimates[1]/(2*np.pi*2437e6),
                          resistor_phase_variance_rad2=each.tolist()))
    report=dict(status='resistor_only_linear_estimate',temperature_k=t,filter_values=v,
        equilibrium_check=dict(measured_v2=measured,expected_v2=expected,relative_error=measured/expected-1),
        bands=bands,limitations=['Averaged PLL feedback only; no sampled aliasing or fractional mixing.',
        'Omits pump, VCO, reference, buffer and bias noise; not total jitter or phase noise.',
        'Centering switches assumed open; leakage and device noise omitted.',
        'No PDK resistor excess-noise or parasitic qualification; no acceptance gate established.'])
    (P/'evidence/three-cap-thermal-noise.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
