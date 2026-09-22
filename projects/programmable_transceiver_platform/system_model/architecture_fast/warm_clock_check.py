"""Warm bank acquisition preserves phase and finite center-state evolution."""
import hashlib,json,math,time
from pathlib import Path
from warm_clock import WarmClock,WarmAcquisition
from coarse_clock import architecture

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=architecture.P;start=time.monotonic()
    files=list(architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Assumed one-pole control centering, not transistor shunt/charge-injection characterization.',
                     'Standalone clock/controller; full-chip warm handoff and waveform quality pending.'])
    output=p/'evidence/fast-warm-clock.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        pll=WarmClock(free_hz=2.304e9*.995)
        acq=WarmAcquisition(pll,span_bound_hz=450e6,fine_margin_hz=144e6)
        for target in (2500000000,2300000000,2437000000):
            phase=pll.output_phase_cycles
            acq.start(pll.time,target,0)
            assert pll.output_phase_cycles==phase
            initial=pll.hold_voltage;begin=pll.time
            pll.advance(begin+pll.center_tau)
            assert abs(pll.control()-initial/math.e)<1e-12
            while acq.busy:acq.step(acq.next_event,0,True)
            assert acq.qualified
            end=pll.time+10e-6
            while pll.time<end:pll.advance(min(pll.next_detector,end));pll.observe_lock()
            assert pll.locked and abs(pll.control())<.8
            report['cases'].append(dict(target_hz=target,bank_code=pll.bank_code,
                initial_center_voltage=initial,fine_control_v=pll.control(),locked=True));save()
        acq.start(pll.time,2412000000,0);pll.advance(pll.time+pll.center_tau)
        before=pll.control();phase=pll.output_phase_cycles;acq.cancel(pll.time)
        assert not acq.busy and not acq.qualified and pll.hold_voltage==before and pll.output_phase_cycles==phase
        report['center_cancellation_preserves_state']=True
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()
    print('Warm clock centering and retuning passed')
if __name__=='__main__':main()
