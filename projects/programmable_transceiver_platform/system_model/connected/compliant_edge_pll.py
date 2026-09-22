"""Actual PFD edges with a bounded compliance-dependent pump current."""
from edge_pump_pll import EdgePumpPLL
from compliant_pump_filter import CompliantPumpFilter


class CompliantEdgePLL(EdgePumpPLL):
    FILTER_CLASS=CompliantPumpFilter

    def __init__(self,headroom_v=.1,**kwargs):
        super().__init__(filter_kwargs=dict(headroom_v=headroom_v),**kwargs)
