"""Finite passive recentering for all three PLL storage nodes."""
import math
from three_cap_pll import ThreeCapPLLFilter

class ThreeCapCenteringFilter(ThreeCapPLLFilter):
    def __init__(self,*args,center_tau_s=200e-9,**kwargs):
        if not math.isfinite(center_tau_s) or center_tau_s<=0:
            raise ValueError('Invalid centering RC constant')
        super().__init__(*args,**kwargs)
        self.center_tau=center_tau_s;self.center_enabled=False
    def rhs(self,t,y,command):
        result=super().rhs(t,y,command)
        if self.center_enabled:
            for i,c in enumerate((self.cf,self.cs,self.c3)):
                result[i]-=y[i]/self.center_tau
                result[6]+=c*y[i]*y[i]/self.center_tau
        return result
    def advance(self,time,command,max_step=1e-9):
        if self.center_enabled and command:
            raise ValueError('Centering requires held charge pump')
        return super().advance(time,command,max_step)
