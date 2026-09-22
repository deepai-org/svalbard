"""Readout gain/offset/curvature following the finite power detector.

These impairments model detector readout/ADC transfer, not the square-law RF
front-end itself. Both rail crossings invalidate a measurement.
"""
import math
from tx_power_detector import PowerDetector

class ImpairedPowerDetector(PowerDetector):
    def __init__(self,*,gain=1.,offset=0.,curvature=0.,**kwargs):
        super().__init__(**kwargs)
        if not all(math.isfinite(x) for x in (gain,offset,curvature)) or gain<=0 or gain+min(0.,2*curvature)<=0:
            raise ValueError('Readout must be finite and monotonic over full scale')
        self.gain=gain;self.offset=offset;self.curvature=curvature
    def request(self):
        if self.pending is not None:raise ValueError('ADC busy')
        value=self.gain*self.value+self.offset+self.curvature*self.value**2/self.fullscale
        invalid=not 0<=value<=self.fullscale
        code=round(max(0.,min(self.fullscale,value))/self.fullscale*((1<<self.bits)-1))
        self.pending=(self.time+self.latency,self.epoch,code,invalid)
