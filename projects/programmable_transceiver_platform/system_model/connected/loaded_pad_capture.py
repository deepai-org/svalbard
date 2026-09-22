"""Capture actual loaded pad state after host events, without advancing analog state."""
from loaded_pad_observer import observe
import math

def captured(base,carrier_hz,instances,phase_diagnostics=False):
    class Captured(base):
        def __init__(self,**kwargs):
            self.pad_observations=[]
            self.phase_observations=[]
            super().__init__(**kwargs);instances.append(self)
        def feed(self,word,epoch,time):
            result=super().feed(word,epoch,time)
            if getattr(self,'tx_observe_enabled',True):
                value=observe(self.loaded_tx.network,self.time,carrier_hz)
                self.pad_observations.append((self.time,value))
                if phase_diagnostics:
                    pll=self.rf_pll
                    assert pll.time == self.time
                    self.phase_observations.append((self.time,
                        2*math.pi*(pll.output_phase_cycles-carrier_hz*self.time)+self.rf_tx_phase,
                        pll.frequency_hz,self.loaded_tx.driver.rail_v,
                        self.adc_reference.voltage))
            return result
    return Captured
