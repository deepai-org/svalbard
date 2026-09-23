"""Common fast chip with scheduled startup-only coarse acquisition.

Adapted from connected/coarse_startup_lifecycle.py; warm recentering is separate.
"""
import math
from chip import TransceiverChip
from coarse_clock import CoarseSampledClock
from coarse_acquisition import CoarseAcquisition

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
        if operation=='rf_coarse_start':
            self._require_target_free()
            if not self.quiet():raise ValueError('Coarse startup requires quiet reset state')
            self.coarse.start(time,payload,self.epoch);return {}
        if operation=='rf_coarse_abort':
            if payload:raise ValueError('Reserved coarse abort payload')
            self.coarse.cancel(time);return {}
        if operation=='rf_coarse_status':
            if payload:raise ValueError('Reserved coarse status payload')
            states=('idle','settle','measure','commit','done','failed','cancelled','start_wait','end_wait')
            return dict(value=states.index(self.coarse.state)|(int(self.coarse.busy)<<8)|(int(self.coarse.qualified)<<9)|(self.rf_pll.bank_code<<16))
        if operation=='resource_count':
            if payload:raise ValueError('Reserved resource-count payload')
            return dict(value=11)
        if operation=='resource_status' and (payload==9 or payload==8 and self.coarse.busy):
            owner=10 if self.coarse.busy else 0
            return dict(value=owner|(int(self.coarse.busy)<<8)|(int(bool(owner))<<10))
        return super().execute_management(operation,payload,time)
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
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid coarse chip time')
        while self.time<time:
            event=self.coarse.next_event if self.coarse is not None and self.coarse.next_event is not None else math.inf
            command=self.command_events[0][0] if self.command_events else math.inf
            end=min(time,event,command)
            super().advance(end)
            if self.coarse is not None and self.coarse.busy and self.coarse.next_event==self.time:
                self.coarse.step(self.time,self.epoch,self.reference)
                if self.coarse.qualified:self.rf_target_hz=self.coarse.target
                self.install_segment(self.rf_pll.frequency_hz-self.rf_carrier,check=False)
        super().advance(time)
