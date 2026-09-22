"""Counter-driven coarse startup for failed and exploratory tuning cases."""
import hashlib,json,time
from pathlib import Path
from coarse_clock import CoarseSampledClock,architecture
from coarse_acquisition import CoarseAcquisition

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=architecture.P;start=time.monotonic()
    files=list(architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Assumed monotonic 16-code 30 MHz bank and 200 ns settling.',
                     'Startup-only clock adapter; full-chip orchestration and warm recentering remain open.',
                     'Variation points are exploratory, not PDK corners; no phase-noise qualification.'])
    output=p/'evidence/fast-coarse-clock.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for free_scale,gain_scale in ((.995,1.),(1.,.95),(.9,.9),(1.1,.9)):
            for target in (2300000000,2500000000):
                pll=CoarseSampledClock(free_hz=2.304e9*free_scale,kvco_hz_per_v=200e6*gain_scale)
                acquisition=CoarseAcquisition(pll,span_bound_hz=450e6,fine_margin_hz=144e6)
                acquisition.start(0.,target,0)
                while acquisition.busy:
                    acquisition.step(acquisition.next_event,0,True)
                assert acquisition.qualified,acquisition.history
                acquired=pll.time;end=acquired+10e-6
                while pll.time<end:
                    pll.advance(min(pll.next_detector,end));pll.observe_lock()
                row=dict(free_scale=free_scale,kvco_scale=gain_scale,target_hz=target,
                    bank_code=pll.bank_code,coarse_acquisition_s=acquired,
                    fine_control_v=pll.control(),locked=pll.locked,measurements=acquisition.history)
                report['cases'].append(row);save()
                assert pll.locked and abs(pll.control())<.8,row
                print(free_scale,gain_scale,target,pll.bank_code,pll.control(),flush=True)
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
