import math,json,copy
from pathlib import Path
from chip_model import P
from recenter_filter import CenteringFilter,RecenteringClock
from coarse_acquisition import CoarseAcquisition

f=CenteringFilter(5000,40e-12,60e-12,voltage=.6)
f.w=-.2;f.initial_energy=f.energy
q0=f.cf*f.v+f.cs*f.w;f.center_enabled=True
split=copy.copy(f);f.advance(1e-6,0)
for i in range(1,98):split.advance(i*1e-6/97,0)
assert abs(f.v-split.v)<1e-14 and abs(f.w-split.w)<1e-14
assert abs(f.voltage_integral-split.voltage_integral)<1e-20
assert abs(f.energy-f.initial_energy+f.resistor_loss)<1e-24
assert abs(f.cf*f.v+f.cs*f.w-q0-f.center_charge)<1e-24
assert f.center_loss>0 and max(abs(f.v),abs(f.w))<=.6*math.exp(-5)
# Independent fixed-step RK4 integrates node KCL, shunt charge, and Joule loss.
# It does not use the closed-form eigenmodes in the implementation.
numerical=[]
for cf,cs in ((40e-12,60e-12),(90e-12,10e-12)):
 for v,w in ((.9,-.7),(-.8,.6)):
  for tau in (100e-9,400e-9):
   f=CenteringFilter(5000,cf,cs,voltage=v,center_tau_s=tau)
   f.w=w;f.initial_energy=f.energy;f.center_enabled=True
   dt=2e-6/20000;state=(v,w,0.,0.,0.)
   def rhs(z):
    a,b=z[:2];link=(a-b)/5000
    return (-link/cf-a/tau,link/cs-b/tau,a,
      -cf*a/tau-cs*b/tau,(a-b)**2/5000+cf*a*a/tau+cs*b*b/tau)
   for step in range(20000):
    a=rhs(state);b=rhs(tuple(y+dt*x/2 for y,x in zip(state,a)))
    c=rhs(tuple(y+dt*x/2 for y,x in zip(state,b)))
    e=rhs(tuple(y+dt*x for y,x in zip(state,c)))
    state=tuple(y+dt*(aa+2*bb+2*cc+ee)/6 for y,aa,bb,cc,ee in zip(state,a,b,c,e))
   f.advance(2e-6,0)
   expected=(f.v,f.w,f.voltage_integral,f.center_charge,f.resistor_loss)
   tolerances=(1e-11,1e-11,1e-17,1e-21,1e-21)
   errors=[abs(a-b) for a,b in zip(expected,state)]
   assert all(e<t for e,t in zip(errors,tolerances)),errors
   assert max(abs(f.v),abs(f.w))<=max(abs(v),abs(w))*math.exp(-2e-6/tau)
   numerical.append(dict(cf=cf,cs=cs,tau=tau,initial=[v,w],errors=errors))

def rejects(action):
 try:action()
 except ValueError:return
 raise AssertionError('Invalid centering operation accepted')

x=RecenteringClock(reference_hz=40e6,divider=60,free_hz=2.304e9,bandwidth_hz=300e3)
rejects(lambda:x.finish_center(0))
rejects(lambda:x.start_center(0,100e-9))
end=x.start_center(0)
rejects(lambda:x.finish_center(end/2))
rejects(lambda:x.start_center(0))
rejects(lambda:x.set_reference(True,0))
x.cancel_center(end/2)
assert not x.filter.center_enabled and not x.present and not x.coarse_initial_ready
rejects(lambda:CoarseAcquisition(x).start(x.time,2437000000,0))
end=x.start_center(x.time);x.finish_center(end)
assert x.coarse_initial_ready
rows=[]
for initial,target in ((2437000000,2500000000),(2500000000,2300000000)):
 p=RecenteringClock(reference_hz=40e6,divider=60,free_hz=2.304e9,bandwidth_hz=300e3)
 p.retarget(0,initial)
 for i in range(1,1601):p.advance(i/40e6);p.observe_lock()
 assert p.locked
 phase=p.phase;v0=p.filter.v;w0=p.filter.w;old_charge=p.integral
 deadline=p.start_center(p.time)
 assert p.phase==phase and p.integral==old_charge
 p.finish_center(deadline)
 assert p.phase>phase and max(abs(p.filter.v),abs(p.filter.w))<=p.center_voltage_bound
 residual=max(abs(p.filter.v),abs(p.filter.w))
 search=CoarseAcquisition(p)
 # The centered residual is separately bounded rather than rounded to zero.
 search.bound+=p.gains.kvco*p.center_voltage_bound
 search.start(p.time,target,0)
 while search.busy:
  t=search.next_event;p.advance(t);search.step(t,0,True)
 assert search.qualified
 start=p.time;first=None;losses=0;tail=True
 for i in range(1,2401):
  p.advance(start+i/40e6);was=p.locked;locked=p.observe_lock()
  if locked and first is None:first=p.time-start
  if was and not locked:losses+=1
  if i>=1600:tail=tail and locked
 assert first is not None and first<=40e-6 and losses==0 and tail
 rows.append(dict(initial_hz=initial,target_hz=target,initial_control_v=v0,initial_slow_v=w0,
   centered_residual_v=residual,declared_center_bound_v=p.center_voltage_bound,bank=p.bank_code,
   first_lock_s=first,center_metrics=p.filter.metrics()))
(P/'evidence/connected-passive-recenter.json').write_text(json.dumps(dict(status='passed',cases=rows,numerical_kcl_cases=numerical,
 negative_controls=['finish without start','understated RC bound','early release','duplicate start','pump during centering','aborted guard cannot qualify'],
 controls=['97-way subdivision','energy dissipation','charge conservation','continuous phase/voltage at switch closure'],
 limitations=['Two shunt RC constants assumed matched; 400ns upper bound is not a silicon result.',
 'Energy is relative to abstract fine-control center; shared-rail common-mode work is not qualified.',
 'Standalone retuning sequence, not full-chip management integration.']),indent=2)+'\n')
print('Passed passive recentering and two counted coarse/fine retunes')
