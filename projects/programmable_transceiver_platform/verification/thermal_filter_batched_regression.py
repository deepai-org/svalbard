"""Independent seeded guard/trajectory regression; no full-chip claim."""
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
import numpy as np
from thermal_filter_batched import batched_step
from thermal_filter_guard_screen import ResistorNoiseFilter,BALANCED_FILTER
P=Path(__file__).resolve().parents[1]


def main(*,local_guard=False):
    import thermal_filter_batched
    from thermal_filter_guard_screen import safe_region as reference_guard
    from thermal_filter_local_guard import safe_region as local_region
    thermal_filter_batched.safe_region=local_region if local_guard else reference_guard
    rng=np.random.default_rng(3347);routes=Counter();errors=[];fixtures=[]
    for i in range(120):
        values={k:v*rng.uniform(.9,1.1) for k,v in BALANCED_FILTER.items()}
        values['c3']+=rng.uniform(0,2e-12)
        m=ResistorNoiseFilter(noise_bins=128,noise_seed=1000+i,**values)
        center=(i%6==0);m.center_enabled=center
        command=0. if center else float(rng.choice([-110e-6,0.,110e-6]))
        m.state[:3]=rng.uniform(-.7,.7,3)
        if i%6==1 and command:
            m.state[:3]=np.sign(command)*.95
        if i%6==2 and command:
            m.state[:3]=np.sign(command)*.8999
        m.time=float(rng.uniform(0,1e-3))
        duration=float(rng.choice([.1e-9,1e-9,10e-9]))
        stop=m.time+duration;initial=m.state.copy()
        out,route=batched_step(m,stop,command);routes[route]+=1
        ref=copy.copy(m);ref.advance(stop,command,max_step=.25e-9)
        error=abs(out.state-ref.state);errors.append(error)
        assert max(error[:3])<1e-9 and error[3]<1e-17 and error[4]<1e-19, (i,error)
        assert max(error[5:])<1e-22, (i,error)
        assert np.array_equal(initial,m.state)
        # Split advancement checks absolute-time noise phase and state continuity.
        mid=m.time+(stop-m.time)/2
        first,_=batched_step(m,mid,command)
        split,_=batched_step(first,stop,command)
        delta=abs(split.state-out.state)
        assert max(delta[:3])<1e-9 and delta[3]<1e-17 and delta[4]<1e-19
        assert max(delta[5:])<1e-22
        fixtures.append(dict(case=i,center=center,command_a=command,duration_s=duration,route=route,
                             max_voltage_error_v=float(max(error[:3])),
                             partition_voltage_error_v=float(max(delta[:3]))))
    assert routes['analytic']>0 and routes['radau_boundary_fallback']>0
    maxima=np.max(errors,axis=0).tolist()
    files=[Path(__file__)]+[P/'verification'/f for f in ('thermal_filter_batched.py','thermal_filter_guard_screen.py',
        'thermal_filter_local_guard.py','thermal_filter_local_guard_regression.py',
        'thermal_filter_energy_screen.py','thermal_filter_exact_step_screen.py')]
    files+=list((P/'system_model/connected').glob('three_cap*.py'))
    report=dict(status='seeded_batched_regression_passed',seed=3347,cases=fixtures,routes=dict(routes),
        max_state_errors=maxima,
        limitations=['Synthetic short steps, not autonomous PLL or full-chip traffic.',
                     'Exploratory component variation is not a foundry-qualified corner set.',
                     'Quadrature check is empirical; guard uses floating-point analytical bounds.'],
        source_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (P/'evidence'/('thermal-filter-local-guard-regression.json' if local_guard else 'thermal-filter-batched-regression.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),routes=dict(routes),max_state_errors=maxima),indent=2))

if __name__=='__main__':main()
