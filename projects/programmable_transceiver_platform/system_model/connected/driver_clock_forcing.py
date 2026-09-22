"""Immutable held driver-rail pulling added to existing VCO spectral forcing.

Offset is deterministic, not additional random noise. Segment boundaries must
update it from the causal driver rail; no rail/PLL feedback loop is implied here.
"""
from dataclasses import dataclass
import math
from oscillator_noise import FrequencyNoise

@dataclass(frozen=True)
class DriverPulledSpectrum(FrequencyNoise):
    driver_offset_hz: float=0.
    def __post_init__(self):
        super().__post_init__()
        if not math.isfinite(self.driver_offset_hz):raise ValueError('Invalid driver frequency pull')
    @property
    def bound_hz(self):return super().bound_hz+abs(self.driver_offset_hz)
    def frequency(self,time):return super().frequency(time)+self.driver_offset_hz
    def phase_integral(self,start,end):
        return super().phase_integral(start,end)+self.driver_offset_hz*(end-start)
