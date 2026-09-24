"""Common fast chip with scheduled startup-only coarse acquisition.

Adapted from connected/coarse_startup_lifecycle.py; warm recentering is separate.
"""
from chip import TransceiverChip
from coarse_clock import CoarseSampledClock
from coarse_acquisition import CoarseAcquisition, advance_coarse, execute_coarse_management

class CoarseTransceiverChip(TransceiverChip):
    RF_PLL_CLASS=CoarseSampledClock
    COARSE_CLASS=CoarseAcquisition
    TILE_COMMANDS=TransceiverChip.TILE_COMMANDS+('rf_coarse_start','rf_coarse_status','rf_coarse_abort')
    def __init__(self,coarse_noise_bound_hz=0.,coarse_counter_ages=(0,0),**kwargs):
        self.coarse=None
        super().__init__(**kwargs)
        self.coarse=self.COARSE_CLASS(self.rf_pll,span_bound_hz=450e6,fine_margin_hz=144e6,noise_bound_hz=coarse_noise_bound_hz,counter_ages=coarse_counter_ages,snapshot_latency_s=2*self.control_period)
        declared_peak=self.rf_pll.bank_base+11*self.rf_pll.bank_step+self.rf_pll.kvco*self.rf_pll.rail+self.rf_pll.frequency_noise.bound_hz
        if declared_peak>self.coarse.counter.frequency_ceiling_hz:
            raise ValueError('Configured oscillator envelope exceeds finite-counter contract')
    def _tx_clock_ready(self):
        return self.coarse is not None and self.coarse.qualified and super()._tx_clock_ready()
    def _require_target_free(self):
        if self.coarse is not None and self.coarse.busy:raise ValueError('Coarse search owns shared sequencer')
        return super()._require_target_free()
    def quiet(self):
        return (self.coarse is None or not self.coarse.busy and self.time>=self.rf_pll.bank_settled_at) and super().quiet()
    def configure(self,mode,time):
        if self.clock_required('rf') and not self.coarse.qualified:
            raise ValueError('Coarse frequency search must qualify before RF mode acquisition')
        return super().configure(mode,time)
    def configure_rf_carrier(self,frequency_hz):
        self._require_target_free()
        if not self.coarse.qualified or frequency_hz!=self.coarse.target:
            raise ValueError('Experimental coarse profile requires startup search for this carrier')
        return super().configure_rf_carrier(frequency_hz)
    def execute_management(self,operation,payload,time):
        return execute_coarse_management(self,operation,payload,time,11,super().execute_management)
    def quiesce(self,time,reason):
        if self.coarse is not None:self.coarse.cancel(time)
        return super().quiesce(time,reason)
    def set_reference(self,present,time):
        held=self.rf_pll.hold_voltage
        result=super().set_reference(present,time)
        if not present:self.coarse.cancel(time)
        elif not self.coarse.qualified:
            self.rf_pll.set_reference(False,time)
            # Reference admission must not change the still-held analog control.
            self.rf_pll.hold_voltage=held
            self.install_segment(self.rf_pll.frequency_hz-self.rf_carrier,check=False)
        return result
    def advance(self,time):
        return advance_coarse(self,time,super().advance)
