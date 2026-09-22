"""FPGA-side payload enables derived from chip-forwarded clock edges."""
from fractions import Fraction

class RationalPacer:
    def __init__(self, numerator, denominator):
        assert 0<numerator<=denominator
        self.n=numerator;self.d=denominator
        self.phase=denominator-numerator
    def tick(self):
        self.phase+=self.n
        count,self.phase=divmod(self.phase,self.d)
        return count

# Per forwarded host word edge, not per clock cycle (DDR has two edges).
RATIOS={
 'ethernet_rf40_12':{'wire':(1,2),'iq':(4,25)},
 'pcie_rf20_8':{'wire':(4,5),'iq':(8,125)},
}

def controls():
    for mode in RATIOS.values():
        for n,d in mode.values():
            p=RationalPacer(n,d);count=0
            for k in range(10000):
                count+=p.tick()
                assert abs(Fraction(count)-Fraction((k+1)*n,d))<1
                if (k+1)%d==0:assert count==(k+1)*n//d
