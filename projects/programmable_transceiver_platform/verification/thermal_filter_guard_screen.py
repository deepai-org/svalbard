"""Conservative fixed-region guard for the independent exact-step prototype.

Bounds hold up to the first boundary encounter: inside the voltage domain each
resistor voltage is at most 2*limit, pump magnitude at most abs(command), and
thermal currents at most the sum of their tone amplitudes. Thus a step shorter
than every distance/rate bound cannot encounter a boundary. Floating-point
arithmetic is not a formal interval proof; an explicit voltage cushion is used.
"""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
from thermal_filter_energy_screen import energy_step
from thermal_filter_exact_step_screen import exact_step,ResistorNoiseFilter,BALANCED_FILTER
P=Path(__file__).resolve().parents[1]


def safe_region(model,stop,command):
    dt=stop-model.time
    if not np.isfinite(dt) or dt<0 or not np.isfinite(command):
        raise ValueError('Invalid interval')
    if model.center_enabled and command:
        raise ValueError('Centering requires held pump')
    v=model.state[:3];limit=model.limit
    if not np.all(np.isfinite(model.state)) or max(abs(v))>=limit:
        raise ValueError('Invalid initial state')
    j1,j3=np.sum(model.noise_amplitude,axis=1)
    rates=np.array([(abs(command)+2*limit/model.r+2*limit/model.r3+j1+j3)/model.cf,
                    (2*limit/model.r+j1)/model.cs,
                    (2*limit/model.r3+j3)/model.c3])
    if model.center_enabled:rates+=limit/model.center_tau
    cushion=1e-10*max(1.,limit)
    if np.any(abs(v)+rates*dt+cushion>=limit):return False
    if command:
        signed=np.sign(command)*v[0]
        if abs(signed-(limit-model.headroom))<=rates[0]*dt+cushion:return False
    return True


def guarded_step(model,stop,command):
    if not safe_region(model,stop,command):
        result=copy.copy(model);result.advance(stop,command)
        return result,'radau_boundary_fallback'
    candidate=copy.copy(model)
    low=energy_step(model,stop,command,8)
    high=energy_step(model,stop,command,16)
    # Quadrature agreement is an empirical check, not a universal error proof.
    if max(abs(low-high))>1e-24:
        candidate.advance(stop,command)
        return candidate,'radau_quadrature_fallback'
    candidate.state[:5]=exact_step(model,stop,command)
    candidate.state[5:7]=high;candidate.time=stop
    return candidate,'analytic'


def main():
    rows=[]
    for name,voltage,command,dt,center in [
        ('interior',.01,100e-6,1e-9,False),
        ('held',.01,0.,1e-9,False),
        ('centering',.01,0.,1e-9,True),
        ('positive_rolloff',.95,100e-6,.1e-9,False),
        ('negative_rolloff',-.95,-100e-6,.1e-9,False),
        ('positive_rolloff_long',.95,100e-6,1e-9,False),
        ('negative_rolloff_long',-.95,-100e-6,1e-9,False),
        ('cross_positive',.8999,100e-6,1e-9,False),
        ('cross_negative',-.8999,-100e-6,1e-9,False),
        ('exact_knee',.9,100e-6,1e-9,False),
        ('long_step',.01,100e-6,50e-9,False)]:
        m=ResistorNoiseFilter(noise_bins=128,**BALANCED_FILTER)
        m.state[:3]=voltage;m.time=120e-6;m.center_enabled=center
        before=m.state.copy();stop=m.time+dt
        result,route=guarded_step(m,stop,command)
        reference=copy.copy(m);reference.advance(stop,command,max_step=.25e-9)
        error=abs(result.state-reference.state)
        assert max(error[:3])<1e-9 and error[3]<1e-17 and error[4]<1e-19
        assert max(error[5:])<1e-22
        assert np.array_equal(m.state,before) and m.time==120e-6
        if name.startswith('cross'):
            assert route=='radau_boundary_fallback'
            assert abs(result.state[0])>.9
        if name in ('interior','held','centering','positive_rolloff','negative_rolloff'):
            assert route=='analytic'
        if name in ('exact_knee','long_step','positive_rolloff_long','negative_rolloff_long'):assert route=='radau_boundary_fallback'
        rows.append(dict(case=name,route=route,max_voltage_error_v=float(max(error[:3])),
                         max_energy_accounting_error_j=float(max(error[5:]))))
    m=ResistorNoiseFilter(noise_bins=128,**BALANCED_FILTER)
    m.state[:3]=.99999;before=m.state.copy()
    assert not safe_region(m,1e-9,100e-6)
    # Guard rejection alone is expected near a rail; do not require the bounded
    # pump to cross it. Original solver retains responsibility for that case.
    assert np.array_equal(m.state,before)
    files=[Path(__file__),P/'verification/thermal_filter_energy_screen.py',
           P/'verification/thermal_filter_exact_step_screen.py']
    files+=list((P/'system_model/connected').glob('three_cap*.py'))
    report=dict(status='conservative_boundary_guard_fixtures_passed',rows=rows,
        limitations=['Prototype only, not connected chip integration.',
                     'Analytical bounds evaluated in floating point, not formal interval arithmetic.',
                     'Quadrature convergence remains empirical; no full-chip speedup demonstrated.'],
        source_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (P/'evidence/thermal-filter-guard-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
