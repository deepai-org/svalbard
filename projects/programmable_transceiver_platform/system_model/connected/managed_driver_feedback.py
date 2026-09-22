"""Managed TX callback with causal local driver-rail feedback into RF PLL."""
import math
import numpy as np
from managed_coupled_driver import ManagedCoupledDriverChip
from driver_pll_feedback import advance_feedback

class ManagedDriverFeedbackChip(ManagedCoupledDriverChip):
    def __init__(self,driver_hz_per_v=1e6,driver_coupling_step_s=1e-9,**kwargs):
        if not math.isfinite(driver_hz_per_v) or not math.isfinite(driver_coupling_step_s) or driver_coupling_step_s<=0:
            raise ValueError('Invalid driver feedback parameters')
        self.driver_hz_per_v=driver_hz_per_v;self.driver_coupling_step=driver_coupling_step_s
        self.driver_feedback_steps=0
        super().__init__(**kwargs)
    def _drive_loaded_network(self,time,terms):
        d=self.loaded_tx.driver
        if self.rf_pll.time>d.time:raise ValueError('PLL advanced beyond driver history')
        if self.rf_pll.time<d.time:
            if not self.rf_pll.advance(d.time):raise ValueError('PLL alignment failed')
        rotated=[(a*np.exp(1j*self.rf_tx_phase),p) for a,p in terms]
        count=advance_feedback(d,self.rf_pll,time,rotated,self.driver_hz_per_v,self.driver_coupling_step)
        self.driver_feedback_steps+=count
