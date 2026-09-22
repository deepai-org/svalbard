"""Entry-state guard for the finite-current unified solver candidate.

Kept separate while source-frozen calibration runs use LimitedCoupledDriver.
Consolidate this guard with that solver before selecting the final candidate.
"""
import math
from limited_coupled_driver import LimitedCoupledDriver

class GuardedLimitedDriver(LimitedCoupledDriver):
    def advance(self,time,command,**kwargs):
        if not math.isfinite(self.rail_v) or self.rail_v<=self.minimum_rail_v:
            raise ValueError('Initial driver rail outside declared model')
        if self.reference is not None:
            voltage=self.reference.voltage
            if not math.isfinite(voltage) or voltage<=.1:
                raise ValueError('Initial reference outside declared model')
        return super().advance(time,command,**kwargs)
