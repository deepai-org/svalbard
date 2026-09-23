"""Startup-only finite coarse bank adapter for the fast sampled PLL."""
import math
import run as architecture
from sampled_pll import SampledPLL

class CoarseSampledClock(SampledPLL):
    def __init__(self,bank_step_hz=30e6,bank_tau_s=200e-9,**kwargs):
        if not math.isfinite(bank_step_hz) or bank_step_hz<=0 or not math.isfinite(bank_tau_s) or bank_tau_s<=0:
            raise ValueError('Invalid bank parameters')
        self.bank_step=bank_step_hz;self.bank_tau=bank_tau_s
        self.bank_code=4;self.bank_amplitude=0.;self.bank_epoch=0.
        super().__init__(**kwargs)
        self.bank_base=self.free_hz;self.bank_settled_at=0.
        self.set_reference(False,0.)
        # Startup-only initial condition: uncharged fine filter and centered hold.
        self.hold_voltage=0.
        self.coarse_initial_ready=True
    def rail_frequency(self,time):
        return super().rail_frequency(time)+self.bank_amplitude*math.exp(-(time-self.bank_epoch)/self.bank_tau)
    def minimum_extra_rail_frequency(self):
        return min(0.,self.bank_amplitude*math.exp(-(self.time-self.bank_epoch)/self.bank_tau))
    def write_bank(self,time,code,guard):
        if self.present or type(code) is not int or not 0<=code<=15:
            raise ValueError('Bank write requires held loop and 4-bit code')
        self.advance(time)
        old=self.free_hz+self.bank_amplitude*math.exp(-(time-self.bank_epoch)/self.bank_tau)
        self.free_hz=self.bank_base+(code-4)*self.bank_step
        self.bank_amplitude=old-self.free_hz;self.bank_epoch=time;self.bank_code=code
        self.bank_settled_at=time+guard
        self.good=0;self.locked=False
    def counter(self,time,prescale):
        self.advance(time)
        return math.floor(self.output_phase_cycles/prescale)
    def retarget(self,time,target):
        self.advance(time);phase=self.output_phase_cycles
        self.divider=target/40e6
        # Rephase the digital divider, preserving physical oscillator phase.
        self.error=math.remainder(self.error,1.)
        self.detector_error=max(-.5,min(.5,self.error))
        self.phase_offset=phase-self.divider*(self.reference_hz*self.time-self.error)
        self.good=0;self.locked=False
