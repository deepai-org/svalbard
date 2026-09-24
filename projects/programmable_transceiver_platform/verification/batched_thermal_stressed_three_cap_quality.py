"""Coupled stressed quality with physical-node finite-band resistor noise."""
from pathlib import Path
from stressed_three_cap_quality import (
    StressedClock as BaseClock, StressedChip as BaseChip, launch,
    P, RANKING, stress, case, scales, values,
)
from thermal_filter_long_clock_comparison import BatchedFilter as ResistorNoiseFilter

class StressedClock(BaseClock):
    NOISE_FILTER = ResistorNoiseFilter

class StressedChip(BaseChip):
    RF_CLOCK_CLASS = StressedClock

if __name__ == '__main__':
    launch(StressedChip, prefix='batched-thermal-', entrypoint=__file__,
           extra_sources=Path(__file__).parent.glob("thermal_filter*.py"))
