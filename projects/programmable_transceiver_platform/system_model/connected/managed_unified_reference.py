"""Managed driver/PLL candidate sharing the coupled ADC/DAC reference state."""
from driver_sensitive_reference import DriverSensitiveReference
from managed_driver_feedback import ManagedDriverFeedbackChip

class CoupledReference(DriverSensitiveReference):
    def advance(self,time):
        # Continuous state is owned by the common driver/network/rail ODE.
        # Sampling and DAC impulses may use it only at the solved boundary.
        if time!=self.time:raise ValueError('Reference must advance through coupled analog owner')

class ManagedUnifiedReferenceChip(ManagedDriverFeedbackChip):
    def __init__(self,driver_reference_v_per_v=.05,**kwargs):
        super().__init__(**kwargs)
        if not self.shared_dac_reference:raise ValueError('Unified candidate requires shared ADC/DAC reference')
        old=self.adc_reference
        if old.time!=0:raise ValueError('Reference replacement requires initial state')
        ref=CoupledReference(driver_v_per_v=driver_reference_v_per_v,
            resistance=old.r,capacitance=old.c,load_capacitance=old.load)
        ref.__dict__.update(old.__dict__)
        self.adc_reference=ref;self.dac_reference=ref;self.loaded_tx.driver.reference=ref
