"""Integer-reference full-chip candidate with reference-sampled RF/wired loops."""
from integer_clock_lifecycle import IntegerClockChip
from sampled_pll import SampledPLL


class SampledClockChip(IntegerClockChip):
    WIRE_PLL_CLASS=SampledPLL
    RF_PLL_CLASS=SampledPLL
