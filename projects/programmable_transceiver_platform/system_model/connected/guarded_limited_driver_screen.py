"""Invalid starting voltages reject transactionally; valid recovery remains."""
import json,pickle
from chip_model import P
from managed_unified_reference import CoupledReference
from guarded_limited_driver import GuardedLimitedDriver

def main():
    cases=[]
    for voltage in (.09,.1,float('nan'),float('inf')):
        r=CoupledReference(resistance=50.,driver_v_per_v=.05)
        d=GuardedLimitedDriver(reference=r);r.voltage=voltage
        before=pickle.dumps(d)
        for end in (0.,100e-9):
            try:d.advance(end,0j)
            except ValueError:pass
            else:raise AssertionError('Invalid reference initial state admitted')
            assert pickle.dumps(d)==before
        cases.append(str(voltage))
    r=CoupledReference(resistance=50.,driver_v_per_v=.05)
    d=GuardedLimitedDriver(reference=r);r.voltage=.11
    d.advance(100e-9,0j);assert r.voltage>.11 and r.time==d.time
    report=dict(status='passed',rejected_initial_reference_v=cases,valid_recovery_v=r.voltage,
        limitations=['Guard is a separate integration candidate while older runs remain frozen.',
        'Entry-state checks do not prove all inter-event trajectories remain in the model envelope.'])
    (P/'evidence/connected-guarded-limited-driver.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
