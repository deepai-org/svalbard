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
    def __init__(self,*,reference_source_limit_a=150e-6,reference_sink_limit_a=150e-6,coupled_analog=False,wired_power_parameters=None,**kwargs):
        from causal_reference_lifecycle import CurrentLimitedReference
        kwargs.setdefault('dac_reference_load_capacitance',2e-12)
        super().__init__(**kwargs)
        old=self.adc_reference
        if old.time!=0 or old.samples or old.dac_updates:
            raise ValueError('Reference replacement requires unenergized initial state')
        if self.dac_reference is not old:
            raise ValueError('Integrated candidate requires one shared converter reference')
        self.adc_reference=CurrentLimitedReference(resistance=old.r,capacitance=old.c,
            load_capacitance=old.load,source_limit_a=reference_source_limit_a,
            sink_limit_a=reference_sink_limit_a)
        self.dac_reference=self.adc_reference
        self.analog_owner=None
        self.wired_power_parameters=dict(peak_differential_v=.4,termination_ohm=100.,efficiency=.35,bias_a=.002)
        if wired_power_parameters is not None:
            if set(wired_power_parameters)!=set(self.wired_power_parameters):raise ValueError('Complete wired power parameters required')
            self.wired_power_parameters=dict(wired_power_parameters)
        if not all(math.isfinite(v) and v>0 for v in self.wired_power_parameters.values()) or self.wired_power_parameters['efficiency']>1:
            raise ValueError('Invalid wired power parameters')
        if coupled_analog:
            self.install_analog_owner(reference_source_limit_a,reference_sink_limit_a)

    def install_analog_owner(self,source_limit,sink_limit):
        from types import MethodType
        from driver_sensitive_reference import DriverSensitiveReference
        from limited_coupled_driver import LimitedCoupledDriver
        self.BOUNDED_WIRE_CLOCK=bool(self.wire_hz_per_v)
        if self.tx.rx_bank is None:raise ValueError('Coupled candidate requires multipole RX')
        old=self.adc_reference
        reference=DriverSensitiveReference(resistance=old.r,capacitance=old.c,load_capacitance=old.load)
        def reference_advance(ref,time):
            if time!=ref.time:raise ValueError('Reference must advance through coupled analog owner')
        reference.advance=MethodType(reference_advance,reference)
        self.adc_reference=self.dac_reference=reference
        self.analog_owner=LimitedCoupledDriver(network=self.output_network,detector=self.tx_detector,
            reference=reference,rx_bank=self.tx.rx_bank,source_limit_a=source_limit,
            sink_limit_a=sink_limit,rail_r=self.supply.r,rail_c=self.supply.c)
        self.output_network=self.analog_owner.network
        self.tx.rx_bank=self.analog_owner.rx_bank
        def supply_advance(supply,time):
            self.tx.advance(time)
            if supply.time!=time:raise ValueError('Supply clock mismatch')
        def supply_draw(supply,time,charge):
            if not math.isfinite(charge) or charge<0:raise ValueError('Invalid switching charge')
            supply.advance(time)
            rail=self.analog_owner.rail_v-charge/supply.c
            if rail<self.analog_owner.minimum_rail_v:raise ValueError('Switching charge exceeds rail envelope')
            self.analog_owner.impulse_energy_j+=.5*supply.c*(self.analog_owner.rail_v**2-rail**2)
            self.analog_owner.rail_v=rail
            supply.delta=rail-self.analog_owner.law.nominal_v
            supply.minimum=min(supply.minimum,supply.delta);supply.charge+=charge
        self.supply.advance=MethodType(supply_advance,self.supply)
        self.supply.draw=MethodType(supply_draw,self.supply)

    def configure_analog_loads(self):
        owner=self.analog_owner
        owner.driver_enabled=self.rf_pll.powered
        parameters=self.wired_power_parameters
        enabled=self.active_engine=='wire'
        drive=self.serializer.drive if self.serializer is not None else 0.
        voltage=parameters['peak_differential_v']*drive
        output_w=voltage*voltage/parameters['termination_ohm']
        # Regulated differential swing is assumed within the declared rail
        # envelope; output compliance and gate switching charge remain open.
        owner.extra_current=lambda time,rail:(parameters['bias_a']+output_w/(parameters['efficiency']*rail)) if enabled else 0.

    def requires_rf_boundary_flush(self):
        return getattr(self,'analog_owner',None) is not None and bool(self.rf_hz_per_v or self.wire_hz_per_v)

    def rf_interval_end(self,end):
        if not self.requires_rf_boundary_flush():return end
        deadlines=[end]
        if self.BOUNDED_WIRE_CLOCK and self.wire_remaining and self.wire_start_not_before is not None and self.wire_start_not_before>self.time:
            deadlines.append(self.wire_start_not_before)
        # Parent layers already split calibration/coarse/probe events. Include
        # lower-layer events before predicting any continuous clock/load state.
        for name in ('next_sample','next_wire','next_adc','next_return','next_detect','next_reference'):
            value=getattr(self,name,math.inf)
            if value>self.time:deadlines.append(value)
        for name in ('dac_pending','adc_pending','external_events','rx_events','lo_events','command_events'):
            queue=getattr(self,name,())
            if queue and queue[0][0]>self.time:deadlines.append(queue[0][0])
        if self.serializer is not None and self.serializer.deadline>self.time:
            deadlines.append(self.serializer.deadline)
        if self.live_rx is not None and self.live_rx.next_time()>self.time:
            deadlines.append(self.live_rx.next_time())
        if self.streaming_watchdog_enabled and self.state=='active':
            deadline=self.last_host+self.watchdog_s
            if deadline>self.time:deadlines.append(deadline)
            elif end>deadline:self.quiesce(self.time,'host watchdog')
        return min(deadlines)

    def prepare_rf_interval(self,end):
        if not self.requires_rf_boundary_flush():return
        import cmath
        from driver_pll_feedback import forecast_trajectory_feedback
        from tx_output_terms import output_terms
        owner=self.analog_owner
        self.configure_analog_loads()
        if self.tx.time!=self.time or owner.time!=self.time or self.rf_pll.time!=self.time:
            raise ValueError('Coupled RF scheduler clocks are not aligned')
        state=self.tx
        terms=[(a*cmath.exp(1j*self.rf_tx_phase),r) for a,r in
            output_terms(state.transmit_terms(),**self.tx_output_parameters)] or [(0j,0j)]
        if not self.rf_pll.powered:terms=[(0j,0j)]
        def receive(t,pad,phase):
            if not self.rf_pll.powered:return 0j
            if state.rx_route=='loopback':signal=pad
            elif state.rx_route=='external_tone':signal=state.external_amplitude*cmath.exp(2j*math.pi*state.external_frequency*t)
            else:signal=0j
            signal+=sum(a*cmath.exp(2j*math.pi*f*t) for a,f in state.rf_blockers)
            if (state.rf_cubic or state.rf_blockers) and abs(signal)>state.rf_envelope_limit:
                raise ValueError('Coupled RF input outside declared cubic-model range')
            signal+=state.rf_cubic*signal*abs(signal)**2
            return signal*cmath.exp(-1j*(phase+self.rf_rx_phase))
        from autonomous_pll import SupplyTrajectory
        for refinement in range(12):
            candidate,clock,metrics=forecast_trajectory_feedback(owner,self.rf_pll,end,
                terms,self.rf_hz_per_v,.5e-9,receive_transform=receive)
            forecast=None
            if self.BOUNDED_WIRE_CLOCK and self.wire_pll is not None:
                forecast=self.forecast_wire_edges(candidate.rail_trajectory,self.wire_hz_per_v)
                first=min(forecast['word_deadline'],forecast['bit_deadline'])
                if first==self.time:
                    # Service an already-due launch before any analog time passes.
                    point=SupplyTrajectory((self.time,),(self.supply.delta,))
                    self.commit_wire_forecast(point,self.wire_hz_per_v,forecast)
                    return self.time
                if first<end-8*math.ulp(end):
                    end=first
                    continue
                for key in ('word_deadline','bit_deadline'):
                    if abs(forecast[key]-end)<=8*math.ulp(end):forecast[key]=end
            self.rf_pll.set_supply_trajectory(clock.supply_trajectory,self.rf_hz_per_v)
            if forecast is not None:
                self.commit_wire_forecast(candidate.rail_trajectory,self.wire_hz_per_v,forecast)
            self._analog_forecast=(self.time,end,candidate)
            self.feedback_intervals=getattr(self,'feedback_intervals',0)+1
            self.feedback_max_iterations=max(getattr(self,'feedback_max_iterations',0),metrics['iterations'])
            return end
        raise ValueError('Wired edge and analog forecast boundary did not converge')

    def make_serializer(self,time):
        result=super().make_serializer(time)
        if getattr(self,'analog_owner',None) is not None and self.BOUNDED_WIRE_CLOCK:
            from autonomous_pll import SupplyTrajectory
            self.wire_pll.set_supply_trajectory(SupplyTrajectory((time,),(self.supply.delta,)),self.wire_hz_per_v)
        return result

    def supply_impulse(self,time,delta_v):
        if not self.requires_rf_boundary_flush():
            return super().supply_impulse(time,delta_v)
        from autonomous_pll import SupplyTrajectory
        from oscillator_supply_lifecycle import OscillatorSupplyChip
        super(OscillatorSupplyChip,self).supply_impulse(time,delta_v)
        # Finish the preceding phase trajectory, then install only the known
        # post-impulse point. The next forecast supplies its future history.
        for pll,sensitivity in ((self.rf_pll,self.rf_hz_per_v),(self.wire_pll,self.wire_hz_per_v)):
            if pll is not None:
                pll.advance(time)
                pll.set_supply_trajectory(SupplyTrajectory((time,),(self.supply.delta,)),sensitivity)
        if self.BOUNDED_WIRE_CLOCK:
            if self.wire_remaining:self.next_wire=math.inf
            if self.serializer is not None and self.serializer.active:self.serializer.retime()
        self.oscillator_supply_events+=1

    RF_PLL_CLASS=SwitchableWarmClock
    TILE_COMMANDS=tuple(dict.fromkeys(PoweredExclusiveChip.TILE_COMMANDS+WarmTransceiverChip.TILE_COMMANDS))

    def select_engine(self,engine):
        self._require_target_free()
        previous=self.active_engine
        super().select_engine(engine)
        if previous!=engine:
            self.coarse.cancel(self.time)
            self.coarse.qualified=False

    def execute_management(self,operation,payload,time):
        if operation=='rf_coarse_start':self.require_engine('rf')
        return super().execute_management(operation,payload,time)
