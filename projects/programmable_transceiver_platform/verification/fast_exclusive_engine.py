"""Experimental payload ownership interlock on the loaded common-chip model.

Inactive analog clock/bias shutdown and pin-level management/RTL encoding remain
unimplemented. This adapter gates admission and actual session enables.
"""
import math
from types import MethodType
from fast_loaded_output import LoadedOutputChip
from autonomous_pll import AutonomousPLL
from rf_return_lifecycle import Receiver

class ExclusiveEngineChip(LoadedOutputChip):
    TILE_COMMANDS=LoadedOutputChip.TILE_COMMANDS+('engine_select','engine_status','wire_return_start')
    def __init__(self,**kwargs):
        self.active_engine='none'
        super().__init__(**kwargs)
        enabled=self.session.enabled
        self.session.enabled=MethodType(lambda session,engine:
            engine==self.active_engine and enabled(engine),self.session)
    def select_engine(self,engine):
        if engine not in ('none','rf','wire'):raise ValueError('Invalid engine')
        if self.state!='reset' or self.session.armed or self.tx_cal.busy:
            raise ValueError('Engine selection requires stopped unarmed chip')
        if self.adc_pending or self.dac_pending or self.maintenance_pending is not None:
            raise ValueError('Pending conversion owns shared resources')
        if engine!=self.active_engine:
            self.tx_cal.cancel(self.time,'engine ownership changed')
            self.output_network.configure(False,True)
            self.active_engine=engine
    def require_engine(self,engine):
        if self.active_engine!=engine:raise ValueError('Inactive payload engine')
    def clock_required(self,engine):
        return engine==self.active_engine
    def configure(self,*args,**kwargs):
        if self.active_engine=='none':raise ValueError('Select payload engine before configuration')
        return super().configure(*args,**kwargs)
    def descriptor(self,*args,**kwargs):
        self.require_engine('rf');return super().descriptor(*args,**kwargs)
    def accept_wire(self,*args,**kwargs):
        self.require_engine('wire');return super().accept_wire(*args,**kwargs)
    def capture(self,*args,**kwargs):
        self.require_engine('rf');return super().capture(*args,**kwargs)
    def schedule(self,*args,**kwargs):
        self.require_engine('rf');return super().schedule(*args,**kwargs)
    def schedule_wire(self,*args,**kwargs):
        self.require_engine('wire');return super().schedule_wire(*args,**kwargs)
    def incoming_wire(self,*args,**kwargs):
        self.require_engine('wire');return super().incoming_wire(*args,**kwargs)
    def start_wire_return(self,start):
        self.require_engine('wire')
        if (self.state!='active' or not math.isfinite(start) or start<=self.time or
                not math.isinf(self.next_return) or self.return_queue or self.return_frame):
            raise ValueError('Wired return requires active idle transport and future start')
        self.host_receiver=Receiver(self.session.mode)
        self.return_sequence=0
        self.return_period=1/(250e6 if self.session.mode==0 else 312.5e6)
        self.next_return=start

    def execute_management(self,operation,payload,time):
        if operation=='wire_return_start':
            if not 1<=payload<=65535:raise ValueError('Return start delay must fit16 bits')
            self.start_wire_return(time+payload*self.control_period)
            return dict(value=payload)
        if operation=='engine_select':
            if payload not in (0,1,2):raise ValueError('Reserved engine selection')
            self.select_engine(('none','rf','wire')[payload])
            return dict(value=payload)
        if operation=='engine_status':
            if payload:raise ValueError('Reserved engine status bits')
            return dict(value=('none','rf','wire').index(self.active_engine))
        if operation in ('tx_cal_start','rx_stream_start','tx_stream_start','stream_start','start_local'):
            self.require_engine('rf')
        return super().execute_management(operation,payload,time)


class SwitchablePLL(AutonomousPLL):
    """Experimental stopped-VCO state with explicit loop-filter leakage.

    Not yet installed in ExclusiveEngineChip. Bias startup and shutdown-current
    transients are absent; off_tau_s is an assumption requiring circuit evidence.
    """
    def __init__(self,*,off_tau_s=1e-3,**kwargs):
        if not math.isfinite(off_tau_s) or off_tau_s<=0:
            raise ValueError('Positive finite off-state leakage time required')
        self.powered=True;self.off_tau_s=off_tau_s
        super().__init__(**kwargs)

    @property
    def frequency_hz(self):
        return super().frequency_hz if self.powered else 0.

    def advance(self,time):
        if self.powered:return super().advance(time)
        if not math.isfinite(time) or time<self.time:
            raise ValueError('PLL time must be finite and monotonic')
        dt=time-self.time
        # Advancing reference phase while holding output phase fixed.
        self.error+=self.reference_hz*dt
        decay=math.exp(-dt/self.off_tau_s)
        self.integral*=decay;self.hold_voltage*=decay
        self.time=time

    def set_power(self,powered,time):
        if not isinstance(powered,bool):raise ValueError('Boolean oscillator power required')
        self.advance(time)
        if powered==self.powered:return
        phase=self.output_phase_cycles
        if powered:
            # Reset divider phase representation, preserving physical VCO phase
            # and leaked filter charge. Lock must be established anew.
            self.error=math.remainder(self.error,1.)
            self.phase_offset=phase-self.divider*(self.reference_hz*self.time-self.error)
        self.powered=powered;self.good=0;self.locked=False

    def observe_lock(self):
        if not self.powered:
            self.good=0;self.locked=False;return False
        return super().observe_lock()

    def edge_time(self,target_phase):
        if not self.powered:raise ValueError('Stopped oscillator has no future edges')
        return super().edge_time(target_phase)


class PoweredExclusiveChip(ExclusiveEngineChip):
    """Experimental oscillator shutdown plus a timed bias-readiness guard.

    Bias current, supply transients and physical settling are not modeled by
    this guard. Both synthesizer instances remain; this is not a shared PLL.
    """
    RF_PLL_CLASS=SwitchablePLL
    WIRE_PLL_CLASS=SwitchablePLL

    def __init__(self,*,bias_settle_s=2e-6,**kwargs):
        if not math.isfinite(bias_settle_s) or bias_settle_s<=0:
            raise ValueError('Positive finite bias settling guard required')
        self.bias_settle_s=bias_settle_s;self.engine_ready_at=math.inf
        super().__init__(**kwargs)
        self.rf_pll.set_power(False,self.time)
        self.install_segment(-self.rf_carrier,check=False)

    def select_engine(self,engine):
        if self.cal.busy:raise ValueError('Calibration owns analog target')
        previous=self.active_engine
        super().select_engine(engine)
        if engine==previous:return
        # Parent has stopped/isolation preconditions and invalidates calibration.
        # Stop both before enabling the selected oscillator.
        for pll in (self.rf_pll,self.wire_pll):
            if pll is not None:pll.set_power(False,self.time)
        selected=self.rf_pll if engine=='rf' else self.wire_pll if engine=='wire' else None
        if selected is not None:selected.set_power(True,self.time)
        self.engine_ready_at=self.time+self.bias_settle_s if engine!='none' else math.inf
        self.install_segment(self.rf_pll.frequency_hz-self.rf_carrier,check=False)

    def make_serializer(self,time):
        result=super().make_serializer(time)
        self.wire_pll.set_power(self.active_engine=='wire',time)
        return result

    def clocks_ready(self):
        return self.time>=self.engine_ready_at and super().clocks_ready()

    def _tx_clock_ready(self):
        return self.active_engine=='rf' and self.time>=self.engine_ready_at and super()._tx_clock_ready()


# One composition for powered operation, finite output loading and RF retuning.
from warm_clock import WarmClock
from warm_chip import WarmTransceiverChip

class SwitchableWarmClock(SwitchablePLL,WarmClock):
    def set_power(self,powered,time):
        was_powered=self.powered
        super().set_power(powered,time)
        if powered and not was_powered:
            tick=(math.floor(time*self.reference_hz)+1)/self.reference_hz
            if tick<=time:tick+=1/self.reference_hz
            self.initialize_reference(time,tick)

class IntegratedTransceiverChip(PoweredExclusiveChip,WarmTransceiverChip):
    RF_PLL_CLASS=SwitchableWarmClock
    TILE_COMMANDS=tuple(dict.fromkeys(PoweredExclusiveChip.TILE_COMMANDS+WarmTransceiverChip.TILE_COMMANDS))

    def select_engine(self,engine):
        self._require_target_free()
        previous=self.active_engine
        super().select_engine(engine)
        if previous!=engine:self.coarse.cancel(self.time)

    def execute_management(self,operation,payload,time):
        if operation=='rf_coarse_start':self.require_engine('rf')
        return super().execute_management(operation,payload,time)
