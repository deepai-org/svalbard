"""Finite host-service gaps on the calibrated, noisy four-path composition."""
import functools
import hashlib
import json
import time
from pathlib import Path
import service_traffic as scenario
from rf_quality_screen import quality
from traffic import TrafficFault


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    start=time.monotonic();original=scenario.run
    p=scenario.architecture.P
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
                limitations=['Selected finite host pauses, not a general queue/service bound.',
                             'Host return remains independently serviced; pauses affect host-to-chip input.',
                             'Analog parameters and oscillator noise remain assumptions.'])
    output=p/'evidence/fast-service-pauses.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            scenario.run=original
            rx0,tx0,t0,_=scenario.simulate(mode,False)
            scenario.run=functools.partial(original,service_pauses={8:16})
            rx,tx,t,result=scenario.simulate(mode,True)
            assert t==t0
            rq=quality(rx0,rx);tq=quality(tx0,tx)
            assert rq['screen_pass'] and tq['screen_pass']
            pause=result['traffic']['service_pauses'][0]
            assert pause['wired_consumed']>0 and pause['adc_captured']>0
            scenario.run=functools.partial(original,service_pauses={8:256})
            try:scenario.simulate(mode,True)
            except TrafficFault as exc:
                fault=exc.event
                assert 'underrun' in str(fault).lower() or 'underflow' in str(fault).lower(),fault
            else:raise AssertionError('Excessive host gap did not fault')
            report['cases'].append(dict(mode=mode,rx_quality=rq,tx_quality=tq,
                finite_pause=result,excessive_pause_fault=fault))
            save();print(mode,rq['corrected_relative_rms'],tq['corrected_relative_rms'],fault,flush=True)
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:scenario.run=original;save()

if __name__=='__main__':main()
