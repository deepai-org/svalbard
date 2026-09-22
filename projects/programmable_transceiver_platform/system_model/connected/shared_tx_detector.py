"""Experimental TX detector sampled through the existing maintenance ADC path."""
from tx_power_detector import PowerDetector
from loaded_tx_chip import LoadedTxChip
from chip_model import decode_iq

class SharedAdcDetector(PowerDetector):
    signed_observations=True
    def __init__(self,sample,**kwargs):
        super().__init__(**kwargs);self.sample=sample
    def request(self):
        if self.pending is not None:raise ValueError('ADC busy')
        power,invalid=self.sample(self.value,self.time)
        self.pending=(self.time+self.latency,self.epoch,power,invalid)
    def read(self):
        if self.pending is None or self.time<self.pending[0]:raise ValueError('ADC result not ready')
        _,epoch,power,invalid=self.pending;self.pending=None
        if epoch!=self.epoch:raise ValueError('Stale ADC result')
        return dict(epoch=epoch,power=power,overflow=invalid)

class SharedAdcLoadedTxChip(LoadedTxChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.tx_adc_samples=0
        detector=SharedAdcDetector(self._sample_detector,bits=12,latency=self.adc_latency)
        self.tx_detector=detector;self.loaded_tx.detector=detector;self.tx_cal.detector=detector
    def _sample_detector(self,power,time):
        if time!=self.time or time!=self.tx.time:raise ValueError('ADC sample time mismatch')
        if not self.tx_cal.busy or not self.quiet() or self.adc_pending or self.maintenance_pending is not None:
            raise ValueError('Shared ADC not exclusively available')
        # Declared analog scaling: detector fullscale -> +0.8 normalized ADC input.
        scale=.8/self.tx_detector.fullscale
        had=hasattr(self,'bits');previous=getattr(self,'bits',None)
        clipped=self.adc_diagnostics['clipped_samples'];self.bits=12
        try:word=self.convert_adc(complex(power*scale,0.))
        finally:
            if had:self.bits=previous
            else:del self.bits
        value=decode_iq(word,12).real/scale
        self.tx_adc_samples+=1
        invalid=(power<0 or power>self.tx_detector.fullscale or
                 self.adc_diagnostics['clipped_samples']>clipped)
        return value,invalid
    def execute_management(self,operation,payload,time):
        if operation=='tx_cal_start' and (self.adc_pending or self.maintenance_pending is not None):
            raise ValueError('Existing ADC conversion pending')
        if operation=='resource_status' and payload==0 and self.tx_cal.busy:
            return dict(value=11|256|1024)
        return super().execute_management(operation,payload,time)
    def capture(self,*args,**kwargs):
        if self.tx_cal.busy:raise ValueError('TX calibration owns shared ADC')
        return super().capture(*args,**kwargs)
