"""Driver supply-impedance experiment with finite reference current limits."""
from managed_rail_budget import ManagedRailBudgetChip

class ManagedLimitedRailBudgetChip(ManagedRailBudgetChip):
    REFERENCE_CURRENT_LIMIT_A = 150e-6
    FAULT_PREFIX = "limited-rail-budget"
