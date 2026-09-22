"""Integer-N candidate: divide the shared40MHz reference by four for wired PLL."""
from noisy_oscillator_lifecycle import NoisyOscillatorChip


class IntegerClockChip(NoisyOscillatorChip):
    def __init__(self,**kwargs):
        if 'wire_reference_divider' in kwargs:raise ValueError('Integer candidate owns wired reference division')
        super().__init__(wire_reference_divider=4,**kwargs)
