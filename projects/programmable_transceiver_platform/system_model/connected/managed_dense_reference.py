"""Finite reference current ceilings in the complete managed analog candidate."""
from managed_unified_reference import ManagedUnifiedReferenceChip
from dense_limited_driver import DenseLimitedDriver

class ManagedDenseReferenceChip(ManagedUnifiedReferenceChip):
    def __init__(self,reference_source_limit_a=150e-6,reference_sink_limit_a=150e-6,**kwargs):
        super().__init__(**kwargs)
        old=self.loaded_tx.driver
        if old.time!=0:raise ValueError('Driver replacement requires initial state')
        new=DenseLimitedDriver(network=old.network,law=old.law,rail_r=old.r,rail_c=old.c,
            minimum_rail_v=old.minimum_rail_v,detector=old.detector,reference=old.reference,
            reference_bias_a=old.reference_bias,reference_efficiency=old.reference_efficiency,
            source_limit_a=reference_source_limit_a,sink_limit_a=reference_sink_limit_a)
        new.network=old.network
        self.loaded_tx.driver=new
