"""Integer-N pulse-loop adapter for the full-chip wired clock service.

Lock observation uses the chip's declared tolerances and comparison cadence.
Filter charge and absolute output-phase offset transfer across a divider band
change; fractional division and artificial phase-step disturbances are rejected.
"""
import math
from compliant_edge_pll import CompliantEdgePLL

class PulseClockService(CompliantEdgePLL):
    def __init__(self,reference_hz,divider,free_hz,bandwidth_hz=1e6,phase_cycles=.2,
                 lock_phase_cycles=.01,lock_frequency_hz=4000.,fast_fraction=.5):
        if divider!=int(divider):raise ValueError('Pulse service requires integer divider')
        rate=reference_hz*divider
        super().__init__(rate_hz=rate,reference_hz=reference_hz,free_offset=free_hz/rate-1,
            bandwidth_hz=bandwidth_hz,fast_fraction=fast_fraction,initial_phase_cycles=-phase_cycles*divider)
        self.phase_offset=0.;self.lock_phase=lock_phase_cycles;self.lock_frequency=lock_frequency_hz
    @property
    def reference_hz(self):return self.reference
    @property
    def output_phase_cycles(self):return self.phase+self.phase_offset
    @property
    def error(self):return math.remainder(-self.phase/self.divider,1.)
    @property
    def integral(self):return (self.filter.cf*self.filter.v,self.filter.cs*self.filter.w)
    @integral.setter
    def integral(self,charge):
        if self.filter.time or self.reference_history:raise ValueError('Charge transfer requires a fresh clock band')
        v=charge[0]/self.filter.cf;w=charge[1]/self.filter.cs
        if max(abs(v),abs(w))>self.filter.limit:raise ValueError('Transferred charge exceeds pump envelope')
        self.filter.v=v;self.filter.w=w
        self.filter.minimum=self.filter.maximum=v
        self.filter.initial_energy=self.filter.energy
    def initialize_reference(self,time,first_tick):
        if time!=self.time or first_tick<=time or not math.isfinite(first_tick):raise ValueError('Invalid pulse reference schedule')
        if self.filter.time!=time:
            if self.filter.time!=0 or self.reference_history:raise ValueError('Cannot rebase a live filter')
            self.filter.time=time
        self.reference_origin=first_tick-1/self.reference
        self.reference_index=1;self.next_reference=first_tick
        self.up=self.down=False;self.good=0;self.locked=False
    def advance(self,time):
        good,locked,first=self.good,self.locked,self.first_lock
        healthy=super().advance(time)
        self.good=good;self.locked=locked if healthy else False;self.first_lock=first
        if not healthy:raise ValueError('Pulse clock reached compliance fault')
        return healthy
    def observe_lock(self):
        valid=self.present and abs(self.error)<self.lock_phase and abs(self.frequency_hz/self.divider-self.reference)<self.lock_frequency
        self.good=self.good+1 if valid else 0;self.locked=self.good>=8
        if self.locked and self.first_lock is None:self.first_lock=self.time
        return self.locked
    def edge_time(self,target_phase):return super().edge_time(target_phase-self.phase_offset)
    def disturb(self,time,phase_cycles=0.,frequency_hz=0.):
        raise ValueError('Pulse clock uses physical supply/noise forcing; phase-step fixture unsupported')
