"""Exact accumulator-controlled integer cycle counts for a rational divider."""
from fractions import Fraction


class DividerSequence:
    def __init__(self,ratio):
        self.ratio=Fraction(str(ratio)) if isinstance(ratio,float) else Fraction(ratio)
        if self.ratio<1:raise ValueError('Divider ratio must be at least one')
        self.remainder=0;self.total_cycles=0;self.edges=0

    def step(self):
        count,self.remainder=divmod(self.remainder+self.ratio.numerator,self.ratio.denominator)
        self.total_cycles+=count;self.edges+=1
        return count

    @property
    def cycle_error(self):
        return Fraction(self.total_cycles)-self.edges*self.ratio
