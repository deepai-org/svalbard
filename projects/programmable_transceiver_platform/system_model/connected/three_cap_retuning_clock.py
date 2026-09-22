"""Three-node filter with existing finite coarse-bank and recenter sequencing."""
from recenter_filter import RecenteringClock
from three_cap_centering import ThreeCapCenteringFilter
from three_cap_pll import ThreeCapRFClock

BALANCED_FILTER=dict(r=10184.271638275502,cf=2.1190014980784758e-11,
    cs=2.457626702372388e-10,r3=10063.455048665259,c3=1.2479232271147656e-12)

class ThreeCapRetuningClock(RecenteringClock):
    integral=ThreeCapRFClock.integral
    metrics=ThreeCapRFClock.metrics
    def __init__(self,filter_values=None,**kwargs):
        super().__init__(**kwargs)
        self.filter=ThreeCapCenteringFilter(**(BALANCED_FILTER if filter_values is None else filter_values))
        self.set_reference(False,0.)
