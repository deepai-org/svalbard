"""Two cascaded integer accumulators with differentiated second carry.

For denominator D, carry1 = input/D + (old_error1-new_error1)/D.
The output carry1 + carry2 - previous_carry2 cancels first-stage error,
leaving a second difference of bounded second-stage error. All divider
intervals remain integers; no fractional oscillator edge is introduced.
"""
from fractional_pulse_pll import DividerSequence,FractionalPulsePLL

class SecondOrderSequence(DividerSequence):
    def __init__(self,ratio):
        super().__init__(ratio)
        if self.low<2:raise ValueError('Second-order divider needs positive minimum interval')
        self.second=0;self.previous_carry=0
    def step(self):
        denominator=self.ratio.denominator
        carry,self.accumulator=divmod(self.accumulator+self.remainder,denominator)
        second_carry,self.second=divmod(self.second+self.accumulator,denominator)
        count=self.low+carry+second_carry-self.previous_carry
        self.previous_carry=second_carry;self.emitted+=1;self.total+=count
        return count

class ShapedFractionalPLL(FractionalPulsePLL):
    SEQUENCE_CLASS=SecondOrderSequence
