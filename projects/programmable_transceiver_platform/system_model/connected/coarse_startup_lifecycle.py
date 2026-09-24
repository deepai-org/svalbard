"""Experimental startup-only coarse search integrated with shared management."""
from calibrated_fractional_chip import CalibratedFractionalChip
from coarse_vco_clock import CoarseVCOClock
from coarse_acquisition import CoarseAcquisition, advance_coarse, execute_coarse_management

class HeldCoarseClock(CoarseVCOClock):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.set_reference(False,0.)

class CoarseStartupChip(CalibratedFractionalChip):
    RF_CLOCK_CLASS=HeldCoarseClock
    COARSE_CLASS=CoarseAcquisition
    TILE_COMMANDS=CalibratedFractionalChip.TILE_COMMANDS+('rf_coarse_start','rf_coarse_status','rf_coarse_abort')
    def __init__(self,coarse_noise_bound_hz=0.,coarse_counter_ages=(0,0),**kwargs):
        self.coarse=None
        super().__init__(**kwargs)
        self.coarse=self.COARSE_CLASS(self.rf_pll,noise_bound_hz=coarse_noise_bound_hz,counter_ages=coarse_counter_ages,snapshot_latency_s=2*self.control_period)
        declared_peak=self.rf_pll.base_free+max(self.rf_pll.bank_hz)+self.rf_pll.gains.kvco*self.rf_pll.filter.limit+self.rf_pll.frequency_noise.bound_hz
        if declared_peak>self.coarse.counter.frequency_ceiling_hz:
            raise ValueError('Configured oscillator envelope exceeds finite-counter contract')
    def _require_target_free(self):
        if self.coarse is not None and self.coarse.busy:raise ValueError('Coarse search owns shared sequencer')
        return super()._require_target_free()
    def quiet(self):
        return (self.coarse is None or not self.coarse.busy and self.time>=self.rf_pll.bank_settled_at) and super().quiet()
    def configure(self,mode,time):
        if not self.coarse.qualified:raise ValueError('Coarse frequency search must qualify before mode acquisition')
        return super().configure(mode,time)
    def configure_rf_carrier(self,frequency_hz):
        self._require_target_free()
        if not self.coarse.qualified or frequency_hz!=self.coarse.target:
            raise ValueError('Experimental coarse profile requires startup search for this carrier')
        return super().configure_rf_carrier(frequency_hz)
    def execute_management(self,operation,payload,time):
        return execute_coarse_management(self,operation,payload,time,10,super().execute_management)
    def quiesce(self,time,reason):
        if self.coarse is not None:self.coarse.cancel(time)
        return super().quiesce(time,reason)
    def set_reference(self,present,time):
        result=super().set_reference(present,time)
        if not present:self.coarse.cancel(time)
        elif not self.coarse.qualified:self.rf_pll.set_reference(False,time)
        return result
    def advance(self,time):
        return advance_coarse(self,time,super().advance)
