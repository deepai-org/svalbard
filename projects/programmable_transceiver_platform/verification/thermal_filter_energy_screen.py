"""Fixed-region analytic states plus independently integrated physical power."""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
from thermal_filter_exact_step_screen import exact_step, ResistorNoiseFilter, BALANCED_FILTER
P=Path(__file__).resolve().parents[1]


def energy_step(model,stop,command,order):
    nodes,weights=np.polynomial.legendre.leggauss(order)
    dt=stop-model.time
    powers=[]
    for fraction in (nodes+1)/2:
        t=model.time+dt*fraction
        v,w,u=exact_step(model,t,command)[:3]
        current=command*np.clip((model.limit-np.sign(command)*v)/model.headroom,0,1)
        j1,j3=model.thermal_currents(t)
        work=current*v+j1*(v-w)+j3*(v-u)
        loss=(v-w)**2/model.r+(v-u)**2/model.r3
        if model.center_enabled:
            loss+=(model.cf*v*v+model.cs*w*w+model.c3*u*u)/model.center_tau
        powers.append([work,loss])
    return model.state[5:7]+dt/2*(weights@np.array(powers))


def main():
    rows=[]
    for name,initial,command,center in [
        ('held',[.03,-.01,.015],0.,False),
        ('up',[.03,-.01,.015],100e-6,False),
        ('down',[.03,-.01,.015],-100e-6,False),
        ('centering',[.03,-.01,.015],0.,True),
        ('positive_compliance',[.95,.95,.95],100e-6,False),
        ('negative_compliance',[-.95,-.95,-.95],-100e-6,False)]:
        for dt in (1e-9,10e-9):
            m=ResistorNoiseFilter(noise_bins=128,**BALANCED_FILTER)
            m.state[:3]=initial;m.time=120e-6;m.center_enabled=center
            stop=m.time+dt
            ref=copy.copy(m);ref.advance(stop,command,max_step=.5e-9)
            a=energy_step(m,stop,command,8);b=energy_step(m,stop,command,16)
            states=exact_step(m,stop,command)
            energy=.5*np.dot([m.cf,m.cs,m.c3],states[:3]**2)
            residual=energy-m.energy-(b[0]-m.state[5])+(b[1]-m.state[6])
            error=float(max(abs(b-ref.state[5:7])))
            convergence=float(max(abs(a-b)))
            assert error<1e-22 and convergence<1e-22 and abs(residual)<1e-22
            assert b[1]>=m.state[6]
            rows.append(dict(case=name,duration_s=dt,max_work_loss_error_j=error,
                             quadrature_change_j=convergence,energy_residual_j=float(residual)))
    files=[Path(__file__),P/'verification/thermal_filter_exact_step_screen.py']
    files+=list((P/'system_model/connected').glob('three_cap*.py'))
    report=dict(status='fixed_region_energy_fixtures_verified',rows=rows,
        limitations=['No compliance-boundary detection or crossing support.',
                     'Quadrature orders verified only on these short-step fixtures.',
                     'No full-chip integration or runtime-speedup claim.'],
        source_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (P/'evidence/thermal-filter-energy-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(cases=len(rows),max_work_loss_error_j=max(x['max_work_loss_error_j'] for x in rows),
        max_energy_residual_j=max(abs(x['energy_residual_j']) for x in rows),
        max_quadrature_change_j=max(x['quadrature_change_j'] for x in rows)),indent=2))

if __name__=='__main__':main()
