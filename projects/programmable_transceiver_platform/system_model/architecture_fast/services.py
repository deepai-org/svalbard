"""Connect timed calibration/diagnostics to the fast analog architecture."""
import hashlib
import json
import time
from pathlib import Path
import run as architecture
from calibration_adc_lifecycle import AutomaticCalibrationChip
from managed_resources import command

class ServiceChip(AutomaticCalibrationChip, architecture.ObservedChip):
    """Shared physical-state models; no controller access to residual truth."""
    pass


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    start=time.monotonic()
    files=list(architecture.D.glob('*.py'))+[Path(__file__),Path(architecture.__file__),architecture.P/'verification/stream_codec.py']
    hashes={str(f.relative_to(architecture.P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Static trim and observation-path parameters are assumptions.',
                     'A 300 uV observation bound is a test fixture, not a physical budget.',
                     'This service composition has not yet passed simultaneous four-path traffic.',
                     'Maintenance uses a separate one-slot result sink sharing ADC/reference.'])
    output=architecture.P/'evidence/fast-whole-chip-services.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            for bound in (None,.0003):
                c=ServiceChip(trim_offsets_v=(.07,-.045),observation_error_bound_v=bound,
                              load_capacitance=1e-12,adc_latency_s=300e-9,watchdog_s=1e-3)
                results=[]
                for target in (0,1):
                    assert command(c,'cal_start',48|(target<<16))['accepted']
                    # Configuration must not steal a target mid-search.
                    try:c.configure(mode,c.time)
                    except ValueError:pass
                    else:raise AssertionError('Configuration stole calibration ownership')
                    c.advance(c.time+40e-6)
                    assert c.cal.state=='done' and c.cal.valid==(bound is not None)
                    results.append(dict(c.cal.result))
                accounting=c.maintenance_accounting()
                assert accounting==dict(sampled=2,completed=2,cancelled=0,pending=0)
                assert c.adc_reference.samples==2 and c.adc_reference.charge>0
                assert not c.host_samples and not c.session.armed
                # Independent test oracle; never supplied to the search controller.
                residuals=[p.apply(c.time,0.) for p in c.trim_targets]
                assert max(map(abs,residuals))<.001
                c.configure(mode,c.time)
                c.advance(c.time+5e-6)
                assert c.state=='active' and c.rf_pll.locked and c.wire_pll.locked
                c.set_reference(False,c.time)
                assert not c.session.enabled('rf') and not c.session.enabled('wire')
                assert not c.cal.valid
                report['cases'].append(dict(mode=mode,observation_bound_v=bound,
                    calibration=results,residual_oracle_v=residuals,accounting=accounting,
                    reference_charge_c=c.adc_reference.charge,acquired_after_calibration=True,
                    reference_loss_invalidates=True))
                save()
        c=ServiceChip(adc_latency_s=10e-6,watchdog_s=1e-3)
        assert command(c,'cal_start',48)['accepted']
        while c.maintenance_pending is None:
            c.advance(min(c.cal.next_event if c.cal.next_event is not None else float('inf'),c.maintenance_next))
        c.set_reference(False,c.time+1e-6);c.advance(c.time+20e-6)
        assert c.cal.state=='cancelled' and c.trim.code==2048 and not c.maintenance_trace
        assert c.maintenance_accounting()==dict(sampled=1,completed=0,cancelled=1,pending=0)
        report['inflight_cancellation']=c.maintenance_accounting()
        assert all(hashlib.sha256((architecture.P/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()
    print('Fast connected calibration services passed',report['elapsed_s'])

if __name__=='__main__':main()
