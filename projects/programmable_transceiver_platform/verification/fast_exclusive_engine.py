"""Experimental payload ownership interlock on the loaded common-chip model.

Inactive analog clock/bias shutdown and pin-level management/RTL encoding remain
unimplemented. This adapter gates admission and actual session enables.
"""
import math
from types import MethodType
from fast_loaded_output import LoadedOutputChip
from autonomous_pll import AutonomousPLL

class ExclusiveEngineChip(LoadedOutputChip):
    TILE_COMMANDS=LoadedOutputChip.TILE_COMMANDS+('engine_select','engine_status')
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
    def execute_management(self,operation,payload,time):
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
