"""Experimental three-cap RF clock in the finite-reference coupled chip."""
from three_cap_retuning_clock import ThreeCapRetuningClock,BALANCED_FILTER
from three_cap_exact_centering import ExactCenteringFilter
from managed_limited_rail_budget import ManagedLimitedRailBudgetChip

class ExactCenteringRetuningClock(ThreeCapRetuningClock):
    def __init__(self,filter_values=None,**kwargs):
        super().__init__(filter_values=filter_values,**kwargs)
        self.filter=ExactCenteringFilter(**(BALANCED_FILTER if filter_values is None else filter_values))

class ThreeCapManagedChip(ManagedLimitedRailBudgetChip):
    RF_CLOCK_CLASS=ExactCenteringRetuningClock
