"""Shared-ADC TX calibration with finite readout settling and four-path traffic."""
import hashlib
import json
import time
from pathlib import Path
import service_traffic as scenario
from tx_traffic import OutputChip
from shared_tx_detector import SharedAdcLoadedTxChip
from buffered_shared_detector import BufferedSharedDetector
from rf_quality_screen import quality
Original=scenario.ServiceChip

class SharedOutputChip(OutputChip):
    def __init__(self,**kwargs):
        kwargs.setdefault("adc_latency_s",30e-9)
        super().__init__(**kwargs)
        self.tx_adc_samples=0
        detector=BufferedSharedDetector(self._sample_detector,readout_tau_s=20e-9,
            bits=12,latency=self.adc_latency)
        self.tx_detector=detector;self.tx_cal.detector=detector
    _sample_detector=SharedAdcLoadedTxChip._sample_detector
    def execute_management(self,operation,payload,time):
        if operation=='tx_cal_start' and (self.adc_pending or self.maintenance_pending is not None):
            raise ValueError('Existing ADC conversion pending')
        if operation=='resource_status' and payload==0 and self.tx_cal.busy:
            return dict(value=11|256|1024)
        return super().execute_management(operation,payload,time)
    def capture(self,*args,**kwargs):
        if self.tx_cal.busy:raise ValueError('TX calibration owns shared ADC')
        return super().capture(*args,**kwargs)

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    start=time.monotonic();p=scenario.architecture.P
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Shared ADC/reference with assumed detector-to-ADC scaling and 20 ns readout settling.',
                     'Output-stage distortion reaches independent TX probe; nonlinear internal loopback is not tested.',
                     'Finite memoryless cubic output model, no loaded-pad network or emission mask.',
                     'Assumed parameters; external frozen-gain quality screen remains provisional.'])
    output=p/'evidence/fast-shared-tx-traffic.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save();chips=[]
    class RecordedChip(SharedOutputChip):
        def __init__(self,**kwargs):super().__init__(**kwargs);chips.append(self)
    scenario.ServiceChip=RecordedChip
    try:
        for mode in (0,1):
            rx0,tx0,t0,_=scenario.simulate(mode,False)
            rx,tx,t,result=scenario.simulate(mode,True)
            assert t==t0
            rq=quality(rx0,rx);tq=quality(tx0,tx)
            result.update(mode=mode,rx_quality=rq,tx_quality=tq,tx_calibration=chips[-1].tx_calibration_record,
                tx_adc_samples=chips[-1].tx_adc_samples,reference_samples=chips[-1].adc_reference.samples)
            assert chips[-1].tx_adc_samples==result['tx_calibration']['probes']
            assert chips[-1].adc_reference.samples==2+chips[-1].tx_adc_samples+len(rx)
            report['cases'].append(result);save()
            print(mode,rq['corrected_relative_rms'],tq['corrected_relative_rms'],flush=True)
            assert rq['screen_pass'] and tq['screen_pass']
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:scenario.ServiceChip=Original;save()

if __name__=='__main__':main()
