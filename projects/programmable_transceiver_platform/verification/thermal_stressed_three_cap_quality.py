"""Coupled stressed quality with physical-node finite-band resistor noise."""
from pathlib import Path
from stressed_three_cap_quality import (
    StressedClock as BaseClock, StressedChip as BaseChip, launch,
    P, RANKING, stress, case, scales, values,
)
from three_cap_resistor_noise import ResistorNoiseFilter

class StressedClock(BaseClock):
    NOISE_FILTER = ResistorNoiseFilter

class StressedChip(BaseChip):
    RF_CLOCK_CLASS = StressedClock

if __name__ == '__main__':
    launch(StressedChip, prefix='thermal-', entrypoint=__file__)
