"""Independent observer phase, filter-decay, isolation and spectral controls."""
import math,json
from types import SimpleNamespace
from chip_model import P
from tx_envelope_observer import observe_tx,spectrum
from coarse_retune_lifecycle import HeldRetuningClock

p=HeldRetuningClock(reference_hz=40e6,divider=60,free_hz=2.304e9,bandwidth_hz=300e3)
tx=SimpleNamespace(time=0.,held=.2+.1j,filtered=.7-.2j,pole=2*math.pi*10e6)
c=SimpleNamespace(time=0.,tx=tx,rf_pll=p,rf_tx_phase=0.)
# Known carrier phase at time zero, independently evaluated as sin/cos.
angle=2*math.pi*math.remainder(p.output_phase_cycles,1.)
expected=tx.filtered*complex(math.cos(angle),math.sin(angle))
assert abs(observe_tx(c,2.4e9)-expected)<1e-14
# A nominal receiver-LO phase must have no effect on an independent observer.
c.rf_rx_phase=1.234;assert abs(observe_tx(c,2.4e9)-expected)<1e-14
before=(p.time,p.phase,p.filter.time,p.filter.v,p.filter.w,p.feedback_target,p.reference_index,tx.time,tx.filtered)
c.time=11e-9;y=observe_tx(c,2.4e9)
assert before==(p.time,p.phase,p.filter.time,p.filter.v,p.filter.w,p.feedback_target,p.reference_index,tx.time,tx.filtered)
expected_mag=abs(tx.held+(tx.filtered-tx.held)*math.exp(-tx.pole*c.time))
assert abs(abs(y)-expected_mag)<1e-14
c.rf_tx_phase=math.pi/2;assert abs(observe_tx(c,2.4e9)-1j*y)<1e-14
n=4000;fs=200e6;times=[i/fs for i in range(n)]
def tone(f):return [complex(math.cos(2*math.pi*f*t),math.sin(2*math.pi*f*t)) for t in times]
a=spectrum(times,tone(5e6));b=spectrum(times,tone(25e6))
assert a['outside_to_inside_db']<-80 and b['outside_to_inside_db']>80
bad=times.copy();bad[50]+=1e-9
try:spectrum(bad,tone(5e6))
except ValueError:pass
else:raise AssertionError('Nonuniform spectrum accepted')
(P/'evidence/connected-tx-observer.json').write_text(json.dumps(dict(status='passed',inband_control=a,outside_control=b,
 controls=['independent nominal carrier phase','receiver phase does not cancel TX phase','nonmutating oscillator forecast',
 'analytical reconstruction magnitude','TX phase rotation','known-tone spectrum','nonuniform-grid rejection']),indent=2)+'\n')
print('Passed TX observer phase, passive-decay, nonmutation and spectrum controls')
