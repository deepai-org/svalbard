"""Shared ADC candidate with finite isolated detector readout bandwidth."""
from detector_readout_settling import SettlingDetector
from shared_tx_detector import SharedAdcDetector
from shared_phase_loaded_tx import SharedPhaseLoadedTxChip

class BufferedSharedDetector(SettlingDetector):
    signed_observations=True
    read=SharedAdcDetector.read
    def __init__(self,sample,**kwargs):
        super().__init__(**kwargs);self.sample=sample
    def request(self):
        if self.pending is not None:raise ValueError('ADC busy')
        power,invalid=self.sample(self.readout_value,self.time)
        self.pending=(self.time+self.latency,self.epoch,power,invalid)

class BufferedSharedPhaseChip(SharedPhaseLoadedTxChip):
    def __init__(self,readout_tau_s=20e-9,**kwargs):
        super().__init__(**kwargs)
        old=self.tx_detector
        if old.time!=0 or old.pending is not None:raise ValueError('Detector replacement must precede startup')
        detector=BufferedSharedDetector(self._sample_detector,readout_tau_s=readout_tau_s,
            tau=1/old.pole,bits=old.bits,fullscale=old.fullscale,latency=old.latency)
        self.tx_detector=detector;self.loaded_tx.detector=detector;self.tx_cal.detector=detector
