"""Experimental TX detector sampled through the existing maintenance ADC path."""
from tx_power_detector import PowerDetector
from loaded_tx_chip import LoadedTxChip
from detector_readout_settling import sample_shared_detector, read_shared_detector

class SharedAdcDetector(PowerDetector):
    signed_observations=True
    def __init__(self,sample,**kwargs):
        super().__init__(**kwargs);self.sample=sample
    def request(self):
        if self.pending is not None:raise ValueError('ADC busy')
        power,invalid=self.sample(self.value,self.time)
        self.pending=(self.time+self.latency,self.epoch,power,invalid)
    read=read_shared_detector

class SharedAdcLoadedTxChip(LoadedTxChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.tx_adc_samples=0
        detector=SharedAdcDetector(self._sample_detector,bits=12,latency=self.adc_latency)
        self.tx_detector=detector;self.loaded_tx.detector=detector;self.tx_cal.detector=detector
    _sample_detector=sample_shared_detector
    def execute_management(self,operation,payload,time):
        if operation=='tx_cal_start' and (self.adc_pending or self.maintenance_pending is not None):
            raise ValueError('Existing ADC conversion pending')
        if operation=='resource_status' and payload==0 and self.tx_cal.busy:
            return dict(value=11|256|1024)
        return super().execute_management(operation,payload,time)
    def capture(self,*args,**kwargs):
        if self.tx_cal.busy:raise ValueError('TX calibration owns shared ADC')
        return super().capture(*args,**kwargs)
