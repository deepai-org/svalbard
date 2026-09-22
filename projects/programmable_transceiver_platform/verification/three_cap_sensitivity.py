"""Independent averaged-loop stress screen; bounds are not PDK statistics."""
import hashlib
import itertools
import json
from pathlib import Path
import numpy as np

P = Path(__file__).resolve().parents[1]

def metrics(v, load, icp, kvco):
    r, cf, cs, r3, c3 = (v[k] for k in ('r','cf','cs','r3','c3'))
    c3 += load
    n = 2437/40
    a, b = 1/r, 1/r3
    matrix = np.array([[-(a+b)/cf,a/cf,b/cf,-icp/cf],
        [a/cs,-a/cs,0,0],[b/c3,0,-b/c3,0],[0,0,kvco/n,0]])
    roots = np.linalg.eigvals(matrix)
    def z(s):
        return 1/(s*cf+s*cs/(1+s*r*cs)+s*c3/(1+s*r3*c3))/(1+s*r3*c3)
    # Independent nodal solution cross-checks the closed-form transimpedance.
    for hz in (1e3,4e5,4e6):
        ss=2j*np.pi*hz
        y=np.array([[ss*cf+a+b,-a,-b],[-a,ss*cs+a,0],[-b,0,ss*c3+b]])
        measured=np.linalg.solve(y,np.array([1.,0.,0.]))[2]
        assert np.isclose(measured,z(ss),rtol=1e-10,atol=1e-10)
    f = np.geomspace(100,1e9,6000)
    s = 2j*np.pi*f
    loop = icp*kvco/n*z(s)/s
    crosses = np.flatnonzero(np.diff((abs(loop)>1).astype(int)))
    assert len(crosses)==1
    i = crosses[0]
    fraction = -np.log(abs(loop[i])) / np.log(abs(loop[i+1])/abs(loop[i]))
    phase = np.unwrap(np.angle(loop))
    phase -= 2*np.pi*round((phase[0]+np.pi)/(2*np.pi))
    margin = 180+np.rad2deg(phase[i]+fraction*(phase[i+1]-phase[i]))
    cross = np.exp(np.log(f[i])+fraction*np.log(f[i+1]/f[i]))
    offsets = np.arange(1,9)*250e3
    sn = 2j*np.pi*offsets
    noise = np.sqrt(np.sum((10000/offsets*abs(1/(1+icp*kvco/n*z(sn)/sn)))**2/2))
    return dict(stable=bool(max(roots.real)<0),phase_margin_deg=float(margin),
        crossover_hz=float(cross),finite_tone_phase_rms_rad=float(noise),
        impedance_4mhz_ohm=float(abs(z(2j*np.pi*4e6))),
        slowest_pole_real_per_s=float(max(roots.real)))

def main():
    source=P/'evidence/three-cap-pad-quality-mode1-launch.json'
    nominal=json.loads(source.read_text())['filter_values']
    keys=list(nominal)
    rows=[]
    # Independent +/-10% endpoints deliberately stress correlation extremes.
    # They do not represent measured process corners or yield probabilities.
    for load in (0.,.25e-12,.5e-12,1e-12,2e-12):
        cases=[]
        for scales in itertools.product((.9,1.1),repeat=7):
            v={k:nominal[k]*scales[i] for i,k in enumerate(keys)}
            m=metrics(v,load,100e-6*scales[5],200e6*scales[6])
            cases.append(dict(scales=dict(zip(keys+['icp','kvco'],scales)),**m))
        worst=min(cases,key=lambda x:x['phase_margin_deg'])
        rows.append(dict(added_tuning_capacitance_f=load,case_count=len(cases),
            unstable_count=sum(not c['stable'] for c in cases),
            min_phase_margin_deg=worst['phase_margin_deg'],worst_margin_case=worst,
            max_finite_tone_phase_rms_rad=max(c['finite_tone_phase_rms_rad'] for c in cases),
            nominal_components=metrics(nominal,load,100e-6,200e6),cases=cases))
    report=dict(status='linear_sensitivity_evidence_only',carrier_hz=2437e6,
        input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        nominal_filter=nominal,independent_component_stress_fraction=.1,rows=rows,
        limitations=['Exploratory stress bounds, not GF180 process distributions or yield.',
          'Averaged loop omits integer-edge ripple, nonlinear pump compliance and acquisition.',
          'Added capacitance is a lumped tuning-node load only; no package or extracted model.',
          'Finite-tone disturbance response is not total phase noise or RF EVM.',
          'No acceptance threshold changed; requires coupled and transistor-level follow-up.'])
    (P/'evidence/three-cap-sensitivity.json').write_text(json.dumps(report,indent=2)+'\n')
    for row in rows:
        print(json.dumps({k:v for k,v in row.items() if k not in ('cases','worst_margin_case')}))

if __name__=='__main__':main()
