"""Experimental payload ownership interlock on the loaded common-chip model.

Inactive analog clock/bias shutdown and pin-level management/RTL encoding remain
unimplemented. This adapter gates admission and actual session enables.
"""
import math
from types import MethodType
from fast_loaded_output import LoadedOutputChip
from autonomous_pll import AutonomousPLL
from rf_return_lifecycle import Receiver
from resource_configuration import ResourceConfigurationCommands

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
    def require_wire_direction(self,direction):
        if direction=='rx' and getattr(self,'record_return',False):
            raise ValueError('Raw record return owns receive transport')
        if getattr(self,'wired_pad_path','serial')!='serial':
            raise ValueError('Selected pad path lacks a serial traffic adapter')
        if not getattr(self,'wired_'+direction+'_enabled',True):
            raise ValueError('Wired direction disabled by configuration')

    def clock_required(self,engine):
        return engine==self.active_engine
    def configure(self,*args,**kwargs):
        if self.active_engine=='none':raise ValueError('Select payload engine before configuration')
        mode=args[0] if args else kwargs.get('mode')
        if self.host_frame_words==8 and mode!=0:
            raise ValueError('Short framing currently supports DDR125 only')
        return super().configure(*args,**kwargs)
    def descriptor(self,*args,**kwargs):
        self.require_engine('rf');return super().descriptor(*args,**kwargs)
    def accept_wire(self,*args,**kwargs):
        self.require_wire_direction('tx')
        self.require_engine('wire');return super().accept_wire(*args,**kwargs)
    def capture(self,*args,**kwargs):
        self.require_engine('rf');return super().capture(*args,**kwargs)
    def schedule(self,*args,**kwargs):
        self.require_engine('rf');return super().schedule(*args,**kwargs)
    def schedule_wire(self,*args,**kwargs):
        self.require_wire_direction('tx')
        self.require_engine('wire');return super().schedule_wire(*args,**kwargs)
    def incoming_wire(self,*args,**kwargs):
        self.require_wire_direction('rx')
        self.require_engine('wire');return super().incoming_wire(*args,**kwargs)
    def start_wire_return(self,start):
        self.require_engine('wire')
        if not getattr(self,'wired_rx_enabled',True):raise ValueError('Wired RX disabled')
        if (self.state!='active' or not math.isfinite(start) or start<=self.time or
                not math.isinf(self.next_return) or self.return_queue or self.return_frame):
            raise ValueError('Wired return requires active idle transport and future start')
        self.host_receiver=self.make_return_receiver()
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

class IntegratedTransceiverChip(ResourceConfigurationCommands,PoweredExclusiveChip,WarmTransceiverChip):
    def __init__(self,*,rf_solver_method="Radau",reference_source_limit_a=150e-6,reference_sink_limit_a=150e-6,coupled_analog=False,wired_power_parameters=None,domain_supply=None,domain_minimum_v=None,domain_load=None,host_bank=None,**kwargs):
        if rf_solver_method not in ("Radau","BDF"):raise ValueError("Unsupported RF stiff solver")
        self.rf_solver_method=rf_solver_method
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
        self.domain_configuration=dict(domain_supply=domain_supply,domain_minimum_v=domain_minimum_v,domain_load=domain_load,host_bank=host_bank)
        if host_bank is not None:
            if not coupled_analog or domain_supply is None or self.return_q!=0:
                raise ValueError('Physical host requires coupled domains and no legacy return impulse')
            expected=[domain_supply.names.index('HOST_A')]*5+[domain_supply.names.index('HOST_B')]*6
            if list(host_bank.output_domain)!=expected:raise ValueError('Host output ownership must match 5/5 data plus clock split')
        if domain_supply is not None:
            if not coupled_analog:raise ValueError('Domain supplies require the coupled analog owner')
        self.wired_power_parameters=dict(peak_differential_v=.4,termination_ohm=100.,efficiency=.35,bias_a=.002)
        if wired_power_parameters is not None:
            if set(wired_power_parameters)!=set(self.wired_power_parameters):raise ValueError('Complete wired power parameters required')
            self.wired_power_parameters=dict(wired_power_parameters)
        if not all(math.isfinite(v) and v>0 for v in self.wired_power_parameters.values()) or self.wired_power_parameters['efficiency']>1:
            raise ValueError('Invalid wired power parameters')
        if coupled_analog:
            self.install_analog_owner(reference_source_limit_a,reference_sink_limit_a)

    def enable_reference_converter_clock(self,*,maximum_slew_v_per_s=1e9):
        """Candidate mathematical timing option; only managed local starts use it."""
        if self.session.armed or self.remaining or self.adc_left:
            raise ValueError('Converter clock selection requires stopped converters')
        if self.analog_owner is None or self.analog_owner.domains is None:
            raise ValueError('Reference converter clock requires coupled supply domains')
        if not math.isfinite(maximum_slew_v_per_s) or not 0<=maximum_slew_v_per_s<5e9:
            raise ValueError('Finite monotonic buffer slew envelope required')
        self.reference_converter_slew=maximum_slew_v_per_s

    def plan_local_converter_clocks(self,start,offset,flags):
        if not hasattr(self,'reference_converter_slew'):return
        from reference_sample_clock import plan_converter_pair
        if type(flags) is not int or flags not in (1,2,3):
            raise ValueError('Select TX, RX, or both converter directions')
        # A disabled branch must not impose a timing constraint. RX-only starts
        # use their own requested lower bound; paired starts retain relative timing.
        anchor=start+offset if flags==2 else start
        relative=offset if flags==3 else 0.
        tx,rx=plan_converter_pair(anchor,relative,now=self.time,
            divider=1 if self.session.mode==0 else 2)
        if flags&1:self.sample_clock=tx;self.next_sample=math.inf
        if flags&2:self.adc_clock=rx;self.next_adc=math.inf

    def configure_wire_interface(self,*,electrical='ac_differential',clock_source='embedded',word_reference_hz=None):
        """Generic stopped interface contract; detailed pad/PLL implementation open."""
        if self.state!='reset' or self.session.armed or self.active_engine!='wire':
            raise ValueError('Stopped wired owner required')
        if electrical not in ('ac_differential','dc_current_sink') or clock_source not in ('embedded','forwarded_word'):
            raise ValueError('Unsupported electrical or clock mode')
        if clock_source=='forwarded_word':
            if (word_reference_hz not in (74.25e6,148.5e6) or
                    self.wire_rate_override!=10*word_reference_hz):
                raise ValueError('Forwarded word reference must match ten-bit lane rate')
        elif word_reference_hz is not None:raise ValueError('Unexpected word reference')
        if getattr(self,'wire_interface',{}).get('electrical')=='dc_current_sink' and electrical!='dc_current_sink':
            self.retain_dc_pad()
        self.wire_interface=dict(electrical=electrical,clock_source=clock_source,
            word_reference_hz=word_reference_hz,detailed_pad_pll_qualified=False)
        self.wire_interface_generation=getattr(self,"wire_interface_generation",0)+1

    def pending_reference_converters(self):
        from reference_sample_clock import ReferenceSampleClock
        result=[]
        for name,deadline,remaining in (('sample_clock','next_sample',self.remaining),
                                        ('adc_clock','next_adc',self.adc_left)):
            clock=getattr(self,name,None)
            if remaining and isinstance(clock,ReferenceSampleClock):result.append((clock,deadline))
        return result

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
            sink_limit_a=sink_limit,rail_r=self.supply.r,rail_c=self.supply.c,**self.domain_configuration)
        self.output_network=self.analog_owner.network
        self.tx.rx_bank=self.analog_owner.rx_bank
        def supply_advance(supply,time):
            self.tx.advance(time)
            if supply.time!=time:raise ValueError('Supply clock mismatch')
        def supply_draw(supply,time,charge):
            if not math.isfinite(charge) or charge<0:raise ValueError('Invalid switching charge')
            supply.advance(time)
            if self.analog_owner.domains is not None:
                if charge:raise ValueError('Scalar charge cannot be assigned to physical domains')
                return
            rail=self.analog_owner.rail_v-charge/supply.c
            if rail<self.analog_owner.minimum_rail_v:raise ValueError('Switching charge exceeds rail envelope')
            self.analog_owner.impulse_energy_j+=.5*supply.c*(self.analog_owner.rail_v**2-rail**2)
            self.analog_owner.rail_v=rail
            supply.delta=rail-self.analog_owner.law.nominal_v
            supply.minimum=min(supply.minimum,supply.delta);supply.charge+=charge
        self.supply.advance=MethodType(supply_advance,self.supply)
        self.supply.draw=MethodType(supply_draw,self.supply)

    def host_supply_event(self,changed_bits,charge_per_transition,time,output=False):
        owner=getattr(self,'analog_owner',None)
        if owner is None or owner.domains is None:
            return super().host_supply_event(changed_bits,charge_per_transition,time,output=output)
        import numpy as np
        if type(changed_bits) is not int or not 0<=changed_bits<1024:
            raise ValueError('Domain host event must describe ten physical data pins')
        self.supply.advance(time)
        d=owner.domains
        if output and owner.host_bank is not None:
            if charge_per_transition:raise ValueError('Legacy output impulse would double count physical host')
            h=owner.host_bank
            word=self.previous_return_word^changed_bits
            drive=[bool(word&(1<<i)) for i in range(10)]+[not bool(h.drive[10])]
            h.advance(time,np.zeros(h.n),drive)
            self.supply_impulse(time,0.)
            return
        charges=np.zeros(len(d.names))
        charges[d.names.index('HOST_A')]=(changed_bits&31).bit_count()*charge_per_transition
        charges[d.names.index('HOST_B')]=((changed_bits>>5).bit_count()+1)*charge_per_transition
        after=d.voltage-charges/d.c
        if np.any(after<=owner.domain_floor):raise ValueError('Host switching exceeds domain voltage envelope')
        before=d.impulse_energy_j
        d.draw(time,charges)
        owner.impulse_energy_j+=d.impulse_energy_j-before
        if owner.host_bank is not None:owner.host_bank.state[:owner.host_bank.n]=d.voltage
        owner.domain_trajectories=d.trajectories
        owner.rail_trajectory=d.trajectories['RF']
        self.supply.charge+=float(np.sum(charges))
        # Only host capacitors jump; PLL/RF perturbations propagate continuously.
        self.supply_impulse(time,0.)

    def clock_supply_delta(self):
        owner=self.analog_owner
        if owner is not None and owner.domains is not None:
            d=owner.domains;i=owner.reference_domain
            return float(d.voltage[i]-d.nominal[i])
        return self.supply.delta

    def external_waveform_signal(self,time):
        import cmath
        start,w,carrier,amplitude=self.external_waveform
        return amplitude*w.value(time-start)*cmath.exp(2j*math.pi*(carrier-self.rf_carrier)*time)

    def install_external_waveform(self,waveform,carrier_hz,start=None,amplitude=.1):
        self.require_engine('rf')
        if self.session.armed or self.adc_pending or self.maintenance_pending is not None:
            raise ValueError('Waveform fixture installation requires unarmed receiver')
        start=self.time if start is None else start
        if (not all(math.isfinite(v) for v in (carrier_hz,start,amplitude)) or start<self.time
                or not 2.3e9<=carrier_hz<=2.5e9 or not 0<amplitude<=1):
            raise ValueError('External waveform envelope')
        self.external_waveform=(start,waveform,carrier_hz,amplitude)
        self.tx.rx_route='external_waveform'

    def retain_dc_pad(self):
        """Retain zero-drive DC pad decay independently of logical ownership."""
        import copy
        channel=getattr(self,'channel',None)
        serializer=getattr(self,'serializer',None)
        if channel is None or not hasattr(channel,'tail_state') or serializer is None:return
        if serializer.active or serializer.drive!=0.:
            raise ValueError('DC pad must be quiesced before detaching its owner')
        # Old serializer may still advance after selection. Retain an immutable
        # snapshot and a time origin, never two mutable owners of its history.
        if getattr(self,'dc_pad_residue',None) is None:
            self.dc_pad_residue=(copy.copy(channel),serializer.time)

    def retired_dc_pad(self,time):
        import copy
        residue=getattr(self,'dc_pad_residue',None)
        if residue is None:return None
        state,origin=residue
        if time<origin:raise ValueError('Retired pad queried before retained history')
        trial=copy.copy(state);trial.advance_state(0.,time-origin)
        return trial

    def configure(self,*args,**kwargs):
        result=super().configure(*args,**kwargs)
        if hasattr(self.channel,'tail_state') and getattr(self,'dc_pad_residue',None) is not None:
            retained=self.retired_dc_pad(self.time)
            for name in ('state','current_state','tail_state','common_drop_state'):
                setattr(self.channel,name,getattr(retained,name))
            self.dc_pad_residue=None
        return result

    def configure_analog_loads(self):
        owner=self.analog_owner
        owner.driver_enabled=self.rf_pll.powered
        parameters=self.wired_power_parameters
        enabled=(self.active_engine=='wire' and getattr(self,'wired_pad_path','serial')=='serial'
                 and getattr(self,'wired_tx_enabled',True))
        if getattr(self,'wire_interface',{}).get('electrical')=='dc_current_sink':
            # Output current is supplied by the remote receiver termination.
            # Only declared local bias belongs on this transmitter supply rail.
            # Forecast the held-command tail state across this analog interval.
            # Reject loss of compliance; do not invent saturated-device behavior.
            channel=getattr(self,'channel',None)
            if channel is not None and hasattr(channel,'tail_state') and self.serializer is not None:
                initial=channel.tail_state;target=abs(self.serializer.drive)
                origin=self.serializer.time;tau=channel.switch_tau_s
                tail=channel.tail_current_a
                owner.external_return_current=lambda time:tail*(target+(initial-target)*math.exp(-max(0.,time-origin)/tau))
                import copy
                snapshot=copy.copy(channel);held_drive=self.serializer.drive
                def guard(time,ground):
                    trial=copy.copy(snapshot)
                    trial.advance_state(held_drive,max(0.,time-origin))
                    return trial.pin_state(ground)['current_compliance_valid']
                owner.external_return_guard=guard
            else:
                owner.external_return_current=lambda time:0.
                owner.external_return_guard=lambda time,ground:True
            owner.extra_current=lambda time,rail:parameters['bias_a'] if enabled else 0.
            return
        if getattr(self,'dc_pad_residue',None) is not None:
            owner.external_return_current=lambda time:self.retired_dc_pad(time).tail_state*self.retired_dc_pad(time).tail_current_a
            owner.external_return_guard=lambda time,ground:self.retired_dc_pad(time).pin_state(ground)['current_compliance_valid']
        else:
            owner.external_return_current=lambda time:0.
            owner.external_return_guard=lambda time,ground:True
        drive=self.serializer.drive if self.serializer is not None else 0.
        voltage=parameters['peak_differential_v']*drive
        output_w=voltage*voltage/parameters['termination_ohm']
        # Regulated differential swing is assumed within the declared rail
        # envelope; output compliance and gate switching charge remain open.
        owner.extra_current=lambda time,rail:(parameters['bias_a']+output_w/(parameters['efficiency']*rail)) if enabled else 0.

    def wired_power_accounting(self):
        """Separate local rail consumption from remote termination power."""
        channel=getattr(self,'channel',None)
        if (getattr(self,'wire_interface',{}).get('electrical')!='dc_current_sink' or
                channel is None or not hasattr(channel,'pin_state')):
            raise ValueError('Configured DC current-sink channel required')
        host=self.analog_owner.host_bank
        external=channel.tail_current_a*channel.tail_state
        ground=host.currents(host.state,host.drive,external_return_a=external)[0]
        pins=channel.pin_state(ground)
        enabled=(self.active_engine=='wire' and self.wired_tx_enabled)
        rail=float(self.analog_owner.domains.voltage[self.analog_owner.wire_domain])
        local=self.wired_power_parameters['bias_a'] if enabled else 0.
        return dict(local_bias_current_a=local,local_bias_power_w=rail*local,
            external_termination_power_w=pins['termination_source_power_w'],
            external_return_current_a=pins['positive_sink_a']+pins['negative_sink_a'],
            transmitter_sink_heat_w=pins['sink_power_w'],
            termination_heat_w=pins['resistor_power_w'],
            return_current_coupled=True,pad_ground_feedback=True,nonlinear_current_feedback=False,
            ground_transfer_power_w=pins["ground_transfer_power_w"],thermal_model_coupled=False,
            receiver_termination_supply_coupled=False)

    def requires_rf_boundary_flush(self):
        return getattr(self,'analog_owner',None) is not None and bool(self.rf_hz_per_v or self.wire_hz_per_v)

    def rf_interval_end(self,end):
        if not self.requires_rf_boundary_flush():return end
        deadlines=[end]
        wave=getattr(self,'external_waveform',None)
        if wave is not None:
            start,w,carrier,amplitude=wave
            if self.time<start:deadlines.append(start)
            elif self.time<start+w.duration:
                index=math.floor((self.time-start)*w.sample_hz)+1
                boundary=start+index/w.sample_hz
                if boundary<=self.time+2*math.ulp(self.time):boundary=start+(index+1)/w.sample_hz
                deadlines.append(boundary)
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
        for clock,_ in self.pending_reference_converters():
            upper=clock.origin+clock.index*clock.period+clock.branch_delay+clock.bounds[1]
            if upper>self.time:deadlines.append(upper)
        return min(deadlines)

    def prepare_rf_interval(self,end):
        if not self.requires_rf_boundary_flush():return
        import cmath
        from driver_pll_feedback import forecast_trajectory_feedback,zero_rf_state
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
            elif state.rx_route=='external_waveform':signal=self.external_waveform_signal(t)
            elif state.rx_route=='external_tone':signal=state.external_amplitude*cmath.exp(2j*math.pi*state.external_frequency*t)
            else:signal=0j
            signal+=sum(a*cmath.exp(2j*math.pi*f*t) for a,f in state.rf_blockers)
            if (state.rf_cubic or state.rf_blockers) and abs(signal)>state.rf_envelope_limit:
                raise ValueError('Coupled RF input outside declared cubic-model range')
            signal+=state.rf_cubic*signal*abs(signal)**2
            return signal*cmath.exp(-1j*(phase+self.rf_rx_phase))
        quiet_rf=(self.rf_pll.powered and all(a==0 for a,_ in terms) and
            zero_rf_state(owner) and not state.rf_blockers and
            (state.rx_route in ('off','loopback') or
             (state.rx_route=='external_tone' and state.external_amplitude==0)))
        from autonomous_pll import SupplyTrajectory
        converters=self.pending_reference_converters()
        for refinement in range(12):
            converter_due=()
            if converters:
                from reference_sample_clock import forecast_converter_boundary
                def endpoint_voltage(t):
                    if t==self.time:local=owner
                    else:
                        local,_,_=forecast_trajectory_feedback(owner,self.rf_pll,t,
                            terms,self.rf_hz_per_v,.5e-9,receive_transform=receive,
                            inactive_rf=not self.rf_pll.powered,quiet_rf=quiet_rf,solver_method=self.rf_solver_method)
                    d=local.domains
                    return float(d.voltage[list(d.names).index('PLL')])
                end,converter_due=forecast_converter_boundary(
                    [branch for branch,_ in converters],endpoint_voltage,
                    start=self.time,end=end,maximum_slew_v_per_s=self.reference_converter_slew)
            candidate,clock,metrics=forecast_trajectory_feedback(owner,self.rf_pll,end,
                terms,self.rf_hz_per_v,.5e-9,receive_transform=receive,inactive_rf=not self.rf_pll.powered,quiet_rf=quiet_rf,solver_method=self.rf_solver_method)
            clock_rail=candidate.domain_trajectories["PLL"] if candidate.domains is not None else candidate.rail_trajectory
            forecast=None
            if self.BOUNDED_WIRE_CLOCK and self.wire_pll is not None:
                forecast=self.forecast_wire_edges(clock_rail,self.wire_hz_per_v)
                first=min(forecast['word_deadline'],forecast['bit_deadline'])
                if first==self.time:
                    # Service an already-due launch before any analog time passes.
                    point=SupplyTrajectory((self.time,),(self.clock_supply_delta(),))
                    self.commit_wire_forecast(point,self.wire_hz_per_v,forecast)
                    return self.time
                if first<end-8*math.ulp(end):
                    end=first
                    continue
                for key in ('word_deadline','bit_deadline'):
                    if abs(forecast[key]-end)<=8*math.ulp(end):forecast[key]=end
            self.rf_pll.set_supply_trajectory(clock.supply_trajectory,self.rf_hz_per_v)
            if forecast is not None:
                self.commit_wire_forecast(clock_rail,self.wire_hz_per_v,forecast)
            for branch,deadline in converters:
                proposal=next((p for b,p in converter_due if b is branch),None)
                setattr(self,deadline,proposal.time if proposal is not None else math.inf)
            self._analog_forecast=(self.time,end,candidate)
            self.feedback_intervals=getattr(self,'feedback_intervals',0)+1
            self.feedback_max_iterations=max(getattr(self,'feedback_max_iterations',0),metrics['iterations'])
            return end
        raise ValueError('Wired edge and analog forecast boundary did not converge')

    def make_serializer(self,time):
        result=super().make_serializer(time)
        if getattr(self,'analog_owner',None) is not None and self.BOUNDED_WIRE_CLOCK:
            from autonomous_pll import SupplyTrajectory
            self.wire_pll.set_supply_trajectory(SupplyTrajectory((time,),(self.clock_supply_delta(),)),self.wire_hz_per_v)
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
                pll.set_supply_trajectory(SupplyTrajectory((time,),(self.clock_supply_delta(),)),sensitivity)
        if self.BOUNDED_WIRE_CLOCK:
            if self.wire_remaining:self.next_wire=math.inf
            if self.serializer is not None and self.serializer.active:self.serializer.retime()
        self.oscillator_supply_events+=1

    RF_PLL_CLASS=SwitchableWarmClock
    TILE_COMMANDS=tuple(dict.fromkeys(PoweredExclusiveChip.TILE_COMMANDS+WarmTransceiverChip.TILE_COMMANDS+ResourceConfigurationCommands.RESOURCE_COMMANDS))

    def select_engine(self,engine):
        self._require_target_free()
        previous=self.active_engine
        pad=self.analog_owner.pad_branch
        if previous!=engine and pad is not None and (pad.local!='Z' or pad.peer!='Z'):
            raise ValueError('Release pad drivers before ownership transfer')
        super().select_engine(engine)
        if previous!=engine:
            if pad is not None:pad.configure('isolated')
            self.coarse.cancel(self.time)
            self.coarse.qualified=False
            self.resource_generation=getattr(self,'resource_generation',0)+1

    def execute_management(self,operation,payload,time):
        if operation=='rf_coarse_start':self.require_engine('rf')
        return super().execute_management(operation,payload,time)

    def configure_resources(self,*,engine,line_rate_bps=None,frame_words=64,
                            pad_path='serial',tx_enabled=True,rx_enabled=True):
        """Protocol-independent stopped hardware configuration; no protocol ID.

        Rate choices are modeled clock targets, not silicon qualification.
        Bidirectional pad packet admission remains unimplemented.
        """
        if (engine not in ('none','wire','rf') or frame_words not in (8,64) or
                pad_path not in ('serial','bidirectional') or
                type(tx_enabled) is not bool or type(rx_enabled) is not bool):
            raise ValueError('Unsupported resource configuration')
        if line_rate_bps is not None and line_rate_bps not in (480e6,1.25e9,1.5e9,1.62e9,2.5e9,.7425e9,1.485e9):
            raise ValueError('Unmodeled line clock target')
        if engine!='wire' and (line_rate_bps is not None or frame_words!=64 or pad_path!='serial'):
            raise ValueError('Wired resources require wired ownership')
        if self.state!='reset' or self.session.armed:raise ValueError('Stopped configuration required')
        pad=self.analog_owner.pad_branch
        if pad is not None and (pad.local!='Z' or pad.peer!='Z'):
            raise ValueError('Release pad drivers before reconfiguration')
        retiring=getattr(self,'wire_interface',{}).get('electrical')=='dc_current_sink'
        if retiring and self.serializer is not None and (self.serializer.active or self.serializer.drive!=0.):
            raise ValueError('DC pad must be quiesced before detaching its owner')
        self.select_engine(engine)
        if retiring:self.retain_dc_pad()
        if pad is not None:pad.configure('isolated')
        self.tx_cal.cancel(self.time,'resource configuration changed');self.coarse.qualified=False
        self.external_waveform=None;self.tx.rx_route='off'
        self.wire_rate_override=line_rate_bps;self.host_frame_words=frame_words
        self.wire_interface=dict(electrical="ac_differential",clock_source="embedded",word_reference_hz=None,detailed_pad_pll_qualified=False)
        self.wired_pad_path=pad_path
        self.wired_tx_enabled=tx_enabled;self.wired_rx_enabled=rx_enabled
        self.resource_generation=getattr(self,'resource_generation',0)+1
