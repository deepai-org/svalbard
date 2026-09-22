"""First-order rational multi-modulus feedback with actual integer edge counts.

This deliberately exposes deterministic divider modulation rather than replacing
it with an averaged feedback ratio. It does not promise acceptable RF spurs.
"""
import copy
from fractions import Fraction
from compliant_edge_pll import CompliantEdgePLL

class DividerSequence:
    def __init__(self,ratio):
        self.ratio=Fraction(ratio);self.low=self.ratio.numerator//self.ratio.denominator
        if self.low<1:raise ValueError('Divider must be at least one')
        self.remainder=self.ratio.numerator%self.ratio.denominator
        self.accumulator=0;self.emitted=0;self.total=0
    def step(self):
        self.accumulator+=self.remainder
        carry,self.accumulator=divmod(self.accumulator,self.ratio.denominator)
        count=self.low+carry;self.emitted+=1;self.total+=count
        return count

class FractionalPulsePLL(CompliantEdgePLL):
    SEQUENCE_CLASS=DividerSequence
    def __init__(self,rate_hz=2412000000,reference_hz=40000000,free_offset=-.04,**kwargs):
        self.sequence=self.SEQUENCE_CLASS(Fraction(str(rate_hz))/Fraction(str(reference_hz)))
        nominal=self.sequence.low*reference_hz
        super().__init__(rate_hz=nominal,reference_hz=reference_hz,
            free_offset=rate_hz*(1+free_offset)/nominal-1,**kwargs)
        self.rate=rate_hz;self.divider=float(self.sequence.ratio)
        self.feedback_target=float(self.sequence.step())
    def feedback_interval(self):return self.sequence.step()
    def __copy__(self):
        clone=super().__copy__();clone.sequence=copy.copy(self.sequence)
        return clone
