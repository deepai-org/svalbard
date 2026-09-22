"""Prototype exact voltage/phase/charge propagation in a fixed compliance region.

Not a drop-in solver: work/loss integrals and certified boundary detection remain
required. Runs independently of the live coupled model and does not modify it.
"""
import copy
import hashlib
import json
import sys
import time
from pathlib import Path
import numpy as np
from scipy.linalg import expm
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/connected'))
from three_cap_resistor_noise import ResistorNoiseFilter
from three_cap_retuning_clock import BALANCED_FILTER


def exact_step(model, stop, command):
    dt=stop-model.time
    r,cf,cs,r3,c3=model.r,model.cf,model.cs,model.r3,model.c3
    # Valid only while staying in the initial affine pump-compliance region.
    factor=(model.limit-np.sign(command)*model.state[0])/model.headroom if command else 1.
    slope=-abs(command)/model.headroom if 0 < factor < 1 else 0.
    offset=command*model.limit/model.headroom if 0 < factor < 1 else command*np.clip(factor,0,1)
    a=np.zeros((5,5))
    a[0,:3]=[(slope-1/r-1/r3)/cf,1/(r*cf),1/(r3*cf)]
    a[1,:3]=[1/(r*cs),-1/(r*cs),0]
    a[2,:3]=[1/(r3*c3),0,-1/(r3*c3)]
    a[3,2]=1
    a[4,0]=slope
    if model.center_enabled:
        if command: raise ValueError('Centering requires held pump')
        a[:3,:3]-=np.eye(3)/model.center_tau
    affine=np.zeros((6,6));affine[:5,:5]=a
    affine[0,5]=offset/cf;affine[4,5]=offset
    e=expm(affine*dt)
    result=e[:5,:5]@model.state[:5]+e[:5,5]
    b=np.zeros((5,2));b[:3]=[[1/cf,1/cf],[-1/cs,0],[0,-1/c3]]
    frequency=model.noise_frequency
    q=np.linalg.solve(2j*np.pi*frequency[:,None,None]*np.eye(5)-a,
                      np.broadcast_to(b,(len(frequency),5,2)))
    q=np.sum(q*(model.noise_amplitude.T*np.exp(1j*model.noise_phase.T))[:,None,:],axis=2)
    phase=np.exp(2j*np.pi*frequency*model.time)
    result+=np.real(np.sum(phase[:,None]*(np.exp(2j*np.pi*frequency*dt)[:,None]*q-q@e[:5,:5].T),axis=0))
    return result


def main():
    cases=[]
    for name,initial,command,center in [
        ('held',[.03,-.01,.015],0.,False),
        ('up',[.03,-.01,.015],100e-6,False),
        ('down',[.03,-.01,.015],-100e-6,False),
        ('centering',[.03,-.01,.015],0.,True),
        ('positive_compliance',[.95,.95,.95],100e-6,False),
        ('negative_compliance',[-.95,-.95,-.95],-100e-6,False)]:
        for duration in (1e-9,10e-9):
            model=ResistorNoiseFilter(noise_bins=128,**BALANCED_FILTER)
            model.state[:3]=initial;model.time=120e-6;model.center_enabled=center
            stop=model.time+duration
            start=time.perf_counter();predicted=exact_step(model,stop,command)
            exact_seconds=time.perf_counter()-start
            reference=copy.copy(model)
            start=time.perf_counter();reference.advance(stop,command,max_step=.5e-9)
            reference_seconds=time.perf_counter()-start
            error=abs(predicted-reference.state[:5])
            assert max(error[:3])<1e-9 and error[3]<1e-17 and error[4]<1e-19, error
            # Check these fixtures stay away from both voltage and region limits.
            path=np.array([exact_step(model,model.time+duration*f,command)[:3] for f in np.linspace(0,1,33)])
            assert np.max(abs(path))<model.limit
            if 'compliance' in name:
                factor=(model.limit-np.sign(command)*path[:,0])/model.headroom
                assert np.all((factor>0)&(factor<1))
            elif command:
                assert np.all((model.limit-np.sign(command)*path[:,0])/model.headroom>1)
            cases.append(dict(case=name,duration_s=duration,max_voltage_error_v=float(max(error[:3])),
                phase_integral_error_vs=float(error[3]),pump_charge_error_c=float(error[4]),
                exact_seconds=exact_seconds,reference_seconds=reference_seconds))
    report=dict(status='fixed_region_state_propagation_verified',cases=cases,
        limitations=['Not integrated into chip; live solver unchanged.',
                     'Missing source-work and dissipation integration.',
                     'Sampled fixture boundary checks are not certified event detection.',
                     'No compliance-region crossing or full-chip speedup claim.'],
        source_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__),P/'system_model/connected/three_cap_resistor_noise.py',
             P/'system_model/connected/three_cap_filter.py',P/'system_model/connected/three_cap_centering.py')})
    (P/'evidence/thermal-filter-exact-step-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),max_voltage_error_v=max(r['max_voltage_error_v'] for r in cases),
        median_step_speed_ratio=float(np.median([r['reference_seconds']/r['exact_seconds'] for r in cases]))),indent=2))

if __name__=='__main__':main()
