"""Ideal-FPGA lifecycle through retained RF state and actual finite chip queues.
MAC intents use coded64-QAM DATA probes, NOT standard beacon/HE/TB packets.
Known training and ideal MAC/security are explicit; not router interoperability.
"""
import json
from copy import deepcopy
import math
import numpy as np
from scipy.signal import resample_poly,firwin
from he64_packet import source,receive,reference_evm,scalar_observer_evm
from wideband_packet import waveform_source,acquisition_source,acquire
from selected_rf import analog_filter,analog_hold_at,receive_frontend,receive_supply_reference,receive_gain_elasticity,receiver_lna_gain,receiver_pga_peak,selected_filter_cutoff,selected_tx_filter,validate_rf_configuration_identity
from rf_timing_command import encode_time
from rf_power_calibration import validate_tx_samples,AntennaTimingCalibration,validate_calibration
from behavioral import BehavioralChip,Assumptions
from design_definition import load_design
FS=37.6875e6

def pack(z):
    v=np.clip(np.rint(np.column_stack((z.real,z.imag))*512),-512,511).astype(np.int64)*4
    return (v[:,0]&4095)|((v[:,1]&4095)<<12)

def unpack(a):
    a=np.asarray(a,np.int64);i=a&4095;q=(a>>12)&4095
    return (np.where(i>=2048,i-4096,i)+1j*np.where(q>=2048,q-4096,q))/2048

def repack(a,n,m):
    bits=((np.asarray(a,np.int64)[:,None]>>np.arange(n))&1).ravel()
    return bits[:len(bits)//m*m].reshape(-1,m)@(1<<np.arange(m))

def resample_poly_validity(valid,up,down):
    """Conservative support mask for scipy's default centered FIR resampler.

    Include every input inside its 10*max(up,down) half-length, even zero
    coefficients. Outside-capture zero padding is known; invalid input samples
    contaminate neighboring outputs without deleting samples or shifting time.
    """
    valid=np.asarray(valid,bool)
    divisor=math.gcd(up,down);up//=divisor;down//=divisor
    half=10*max(up,down) if up!=down else 0
    centers=np.arange((len(valid)*up+down-1)//down)*down
    left=np.maximum(0,-np.floor_divide(-(centers-half),up))
    right=np.minimum(len(valid),np.floor_divide(centers+half,up)+1)
    prefix=np.r_[0,np.cumsum(~valid)]
    return prefix[right]==prefix[left]


def clock_warp(samples,ratio,*,taps=513):
    """Bandlimited numerical clock-rate conversion; FPGA implementation is assumed.

    ratio>1 means a faster source clock and a shorter physical waveform.
    The interpolation kernel is not claimed as a zero-latency implementation.
    """
    samples=np.asarray(samples,complex)
    if not math.isfinite(ratio) or ratio<=0:raise ValueError('Clock ratio')
    if ratio==1:return samples.copy()
    high=resample_poly(samples,8,1,window=firwin(taps,1/8,window=('kaiser',8)))
    positions=np.arange(math.ceil(len(samples)/ratio))*ratio*8
    # Four-point fractional interpolation avoids the outer-tone droop of
    # piecewise linear interpolation even after eightfold upsampling.
    index=np.floor(positions).astype(int);u=positions-index;v=np.pad(high,(1,2))
    return (-u*(u-1)*(u-2)/6*v[index]
            +(u+1)*(u-1)*(u-2)/2*v[index+1]
            -(u+1)*u*(u-2)/2*v[index+2]
            +(u+1)*u*(u-1)/6*v[index+3])


class PGAGainState:
    """Downstream gain state, reusable with event-driven native ADC sampling."""
    def __init__(self, *, gain_codes_db=None, lna_gain_db=20.):
        from rf_gain_command import PGA,LNA
        self.gain_codes_db=tuple(PGA) if gain_codes_db is None else tuple(gain_codes_db)
        if not self.gain_codes_db or any(g not in PGA for g in self.gain_codes_db):
            raise ValueError('Gain-state adapter requires supported nonempty PGA codes')
        if lna_gain_db not in LNA:raise ValueError('Unsupported preloaded LNA code')
        self.lna_gain_db=lna_gain_db
        self.time=0.;self.pga_db=28.;self.pga_updates=[];self.gain_invalid_intervals=[]
        self._gain_timing_inputs=dict(sample_hz=FS,d2h_words_hz=156.25e6,h2d_words_hz=312.5e6)

    def gain_timing(self):
        from timing_services import gain_feedback_bound
        return dict(inputs=dict(self._gain_timing_inputs),
                    scope="Framed transport bound; helper observation/settling terms are illustrative, not analog readiness.",
                    **gain_feedback_bound(**self._gain_timing_inputs))

    def pga_gain_at(self,times):
        times=np.asarray(times,float)
        gain=np.full_like(times,10**(self.pga_db/20))
        for commit,initial,target,tau in self.pga_updates:
            active=times>=commit
            gain[active]=target+(initial-target)*np.exp(-(times[active]-commit)/tau)
        return gain

    def plan_pga(self,gain_db,*,commit_s,tau_s,relative_error=.003):
        """Analog response to an admitted commit; command transport is separate.

        First-order gain settling hypothesis, no overshoot/offset/noise model.
        Preserve filter/LO history; do not reset at packet or processing chunks.
        """
        from rf_gain_command import PGA
        if gain_db not in self.gain_codes_db or not math.isfinite(commit_s) or commit_s<self.time:
            raise ValueError('Supported PGA code and nonpast commit required')
        if not math.isfinite(tau_s) or tau_s<=0:
            raise ValueError('Positive finite PGA settling constant required')
        if self.pga_updates and commit_s<=self.pga_updates[-1][0]:
            raise ValueError('PGA commits must be strictly ordered')
        if not math.isfinite(relative_error) or not 0<relative_error<1:
            raise ValueError('PGA relative settling error must be between zero and one')
        initial=float(self.pga_gain_at(np.array([commit_s]))[0])
        target=10**(gain_db/20)
        settling=tau_s*max(0.,math.log(max(abs(initial-target)/target/relative_error,1.)))
        return dict(initial_gain=initial,target_gain=target,tau_s=tau_s,
                    commit_s=commit_s,settling_s=settling,ready_s=commit_s+settling,
                    relative_error=relative_error,scope='First-order gain only; later commands supersede readiness.')

    def schedule_pga(self,gain_db,**kwargs):
        plan=self.plan_pga(gain_db,**kwargs)
        self.pga_updates.append((plan['commit_s'],plan['initial_gain'],
                                 plan['target_gain'],plan['tau_s']))
        return plan

    def schedule_gain_command(self,header,sequence,*,host_issue_s,tau_s,
                              stale_pairs=24,rf_owned=True,snapshot_complete=True):
        """Protected PGA-only command with bounded transport and analog status.

        Transport uses the declared worst-case frame/CDC bound, not a live RTL
        parser. The configured upstream gain is retained; LNA updates need their
        own filter-history recovery model. No payload truth chooses the gain.
        """
        from rf_gain_command import decode_gain,encode_gain
        if not snapshot_complete:raise ValueError('Fast gain command requires completed sample snapshot')
        command=decode_gain(header,sequence,rf_owned=rf_owned)
        if command['lna_db']!=self.lna_gain_db:raise ValueError('Preloaded LNA must remain at its configured gain')
        if not math.isfinite(host_issue_s) or host_issue_s<self.time:
            raise ValueError('Nonpast host command required')
        if type(stale_pairs) is not int or not 0<=stale_pairs<=24:
            raise ValueError('Stale pair bound')
        timing=self.gain_timing()['parts_s']
        arrival=host_issue_s+timing['command_transport']+timing['cdc_and_commit']
        commit_index=math.ceil(arrival*FS)
        plan=self.plan_pga(command['pga_db'],commit_s=commit_index/FS,tau_s=tau_s)
        ready_index=math.ceil(plan['ready_s']*FS)
        first_invalid=commit_index-stale_pairs
        # Encode before mutation: an overflow or invalid command cannot alter
        # gain, filter history or sample-validity state.
        status=encode_gain(self.lna_gain_db,command['pga_db'],sequence,
            invalid_pairs=ready_index-first_invalid,status=True)
        self.schedule_pga(command['pga_db'],commit_s=plan['commit_s'],tau_s=tau_s)
        self.gain_invalid_intervals.append((first_invalid,ready_index))
        return dict(**plan,host_issue_s=host_issue_s,status=status,
                    first_invalid_sample=first_invalid,first_valid_sample=ready_index,
                    transport_bound_s=timing['command_transport']+timing['cdc_and_commit'])

    def gain_valid_at(self,times):
        """Host validity for the declared native sample timeline; never compress time."""
        times=np.asarray(times,float)
        valid=np.ones(times.shape,dtype=bool)
        for first,end in self.gain_invalid_intervals:
            valid&=~((times>=first/FS)&(times<end/FS))
        return valid

class SharedRFPath(PGAGainState):
    def __init__(self, *, environment=None):
        if environment is not None:validate_rf_configuration_identity(environment)
        gains=None if environment is None else sorted(set(environment['receiver_parameters']['pga_i']['gain_db']) & set(environment['receiver_parameters']['pga_q']['gain_db']))
        super().__init__(gain_codes_db=gains,lna_gain_db=20. if environment is None else receiver_lna_gain(environment))
        self.frontend_parameters=dict(noise_figure_db=6.,input_iip3_dbm=0.,temperature_k=300.15,early_gain_db=20.)
        self.adc_enob=8.;self.pga_peak_limit_v=None;self.pga_clips=0
        self.receiver_context=dict(model_role='independent_normalized_rf_fixture')
        if environment is not None:
            config=environment['resolved_configuration']
            if config['engine']!='rf' or config['direction']!='rx' or config['sample_hz']!=FS:
                raise ValueError('Wi-Fi fixture requires matching RF RX sample configuration')
            rates=environment['transport_parameters']
            self._gain_timing_inputs=dict(sample_hz=config['sample_hz'],
                d2h_words_hz=rates['d2h_word_hz'],h2d_words_hz=rates['h2d_word_hz'])
            self.gain_timing() # Validate required rates before any waveform/state work.
            inventory=environment['receiver_parameters']
            for lane in ('adc_i','adc_q'):
                if (inventory[lane]['native_bits'],inventory[lane]['transport_bits'])!=(10,12):
                    raise ValueError('Wi-Fi receiver requires native 10-bit / transport 12-bit words')
            if inventory['adc_i']['enob_target']!=inventory['adc_q']['enob_target']:
                raise ValueError('Wi-Fi receiver requires matched assigned I/Q ENOB')
            self.adc_enob=inventory['adc_i']['enob_target']
            self.pga_peak_limit_v=receiver_pga_peak(environment)
            self.frontend_parameters=dict(noise_figure_db=inventory['lna']['noise_figure_db'],
                input_iip3_dbm=inventory['lna']['iip3_dbm'],
                temperature_k=environment['converter_parameters']['temperature_k'],
                early_gain_db=receiver_lna_gain(environment),
                gain_reference_v=receive_supply_reference(environment,'gain_reference_v'),
                gain_supply_elasticity=receive_gain_elasticity(environment))
            self.receiver_context=deepcopy(dict(design_provenance=environment['design_provenance'],
                resolved_configuration=config,frontend_parameters=dict(self.frontend_parameters),
                adc_enob=self.adc_enob,pga_nominal_peak_limit_v=self.pga_peak_limit_v,
                model_role='shared_receiver_allocations_with_prescribed_rail_and_phase'))
        self.phase_noise=None;self.shared_converter_clock=False;self.max_clock_error_s=0.
        self.dac_enob=10. if environment is None else environment['dac_noise_parameters']['enob'];self.dac_noise_rng=np.random.default_rng(9551)
        self.tx_cubic_coefficient=.02 # assigned normalized-envelope AM/AM hypothesis
        self.pa_phase_deg_at_p1db=0.
        self.pa_input_loss_db=0. # external TX-only attenuator; output loss retained
        self.pa_input_p1db_envelope=None # fixed board hypothesis, never per-packet normalization
        self.converter_phase_noise=None # additive divider/distribution phase at FS
        self.pga_updates=[];self.gain_invalid_intervals=[]
        self.max_tx_leak_filter_input_v=0.
        self.tx_to_rx_filter_coupling=0. # effective post-mixer V/V, not switch isolation
        self.tx_integrator_ratio=None;self.tx_family='tx_third_order';self.tx_cutoff_hz=18e6;self.external_loss_db=2.;self.wanted_dbm=-50.;self.blocker_dbm=-50.;self.pga_db=28. if environment is None else config['pga_gain_db'];self.blocker_offset_hz=12e6;self.blocker_wave=None;self.rx_cutoff_hz=9.53125e6;self.time=0.;self.rng=np.random.default_rng(901);self.states={'rx':None};self.clips=0;self.tx_edges=[0.];self.tx_values=[0j]
        self._filter_environment={} if environment is None else deepcopy({
            'design_provenance':environment['design_provenance'],
            'filter_parameters':environment['filter_parameters']})
        self.rx_cutoff_hz=selected_filter_cutoff(self._filter_environment,'rx',None,9.53125e6)
        self.tx_cutoff_hz=selected_filter_cutoff(self._filter_environment,'tx',None,18e6)
        self.tx_family,self.tx_order=selected_tx_filter(self._filter_environment)

    def filter_settings(self):
        return {direction+'_cutoff_hz':selected_filter_cutoff(self._filter_environment,
            direction,getattr(self,direction+'_cutoff_hz'),default)
            for direction,default in (('rx',9.53125e6),('tx',18e6))}

    def configure_clock_noise(self,*,colored=-115.,floor=-155.,seed=831,converter_jitter_ps=0.):
        """Assign one persistent LO/divider hypothesis for RX, idle and TX."""
        from oscillator_noise import PhaseNoise
        if not math.isfinite(converter_jitter_ps) or converter_jitter_ps<0:
            raise ValueError('Nonnegative finite converter jitter required')
        self.shared_converter_clock=True
        rng=np.random.default_rng(seed+10000)
        peak=2*math.pi*FS*converter_jitter_ps*1e-12/math.sqrt(2)
        self.converter_phase_noise=PhaseNoise(tuple((f,peak,float(rng.uniform(-math.pi,math.pi)))
            for f in (73e3,611e3,2.3e6,7.1e6)))
        self.phase_noise=PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=colored,
            floor_dbc_hz=floor,offset_band_hz=(1e3,8e6),bins=48,seed=seed)
        return dict(colored_at_100khz_dbc_hz=colored,floor_dbc_hz=floor,seed=seed,
            integrated_phase_rms_rad=math.sqrt(self.phase_noise.variance_rad2),
            converter_jitter_rms_ps=converter_jitter_ps,
            scope='Assigned finite LO spectrum plus four persistent converter-clock lines; '
            'shared ADC/DAC clock noise, not independently qualified branches or physical bounds.')

    def lo_phase_model(self):
        """One explicit fixture realization for mixing, timing and result records."""
        from oscillator_noise import PhaseNoise
        source=(self.phase_noise if self.phase_noise is not None else
                PhaseNoise(((1e6,.006,-math.pi/2),)))
        return source.plus(PhaseNoise(((31.25e6,.002,-math.pi/2),)))

    def converter_phase_model(self):
        from oscillator_noise import PhaseNoise
        # Ideal division preserves time error; additive converter phase is at FS.
        clock=PhaseNoise(tuple((f,a*FS/2412e6,p) for f,a,p in self.lo_phase_model().tones)
                         if self.shared_converter_clock else ())
        return clock if self.converter_phase_noise is None else clock.plus(self.converter_phase_noise)

    def clock_configuration(self):
        return dict(lo_hz=2412e6,converter_hz=FS,
            shared_converter_clock=bool(self.shared_converter_clock),
            lo_phase_tones=[list(tone) for tone in self.lo_phase_model().tones],
            converter_phase_tones=[list(tone) for tone in self.converter_phase_model().tones],
            tone_fields=['frequency_hz','peak_phase_rad','phase_rad'],
            phase_convention='peak_phase_rad * cos(2*pi*frequency_hz*t + phase_rad)',
            scope='Actual finite prescribed fixture realization, not characterized chip clock performance.')

    def clock_error(self,times):
        if not self.shared_converter_clock and self.converter_phase_noise is None:
            return np.zeros_like(np.asarray(times,float))
        clock=self.converter_phase_model()
        error=clock.crossing_error(times,FS)
        if len(error):self.max_clock_error_s=max(self.max_clock_error_s,float(max(abs(error))))
        return error

    def process(self,drive,direction,held_values=None):
        self.filter_settings()  # Reject illegal mutable settings before advancing retained state.
        drive=np.asarray(drive,complex);rate=80e6;t=self.time+np.arange(len(drive))/rate
        rails=3.3+.002*np.sin(2*np.pi*31.25e6*t)
        phase=self.lo_phase_model().phase(t)
        inputs={'rx':np.zeros(len(drive),complex),'tx':np.zeros(len(drive),complex)}
        if direction=='rx':
            envelope=None if self.blocker_wave is None else self.blocker_wave[np.rint(t*rate).astype(np.int64)%len(self.blocker_wave)]
            z,_=receive_frontend(drive,t,rails,phase,sample_hz=rate,wanted_dbm=self.wanted_dbm,blocker_dbm=self.blocker_dbm,noise_rng=self.rng,blocker_offset_hz=self.blocker_offset_hz,blocker_envelope=envelope,external_loss_db=self.external_loss_db,**self.frontend_parameters)
            inputs['rx']=z+.003*z.conj()
        elif direction=='tx':
            if held_values is None:raise ValueError('Actual DAC transitions required')
            held_values=np.asarray(held_values)
            if not math.isfinite(self.dac_enob) or not 0<self.dac_enob<=10:
                raise ValueError('DAC ENOB must be within native10-bit width')
            excess=math.sqrt(max(0.,((2/2**self.dac_enob)**2-(1/512)**2)/12))
            if excess:
                noise=self.dac_noise_rng.normal(size=(len(held_values),2))
                held_values=held_values+excess*(noise[:,0]+1j*noise[:,1])
            ideal=self.time+np.arange(len(held_values)+1)/FS
            edges=ideal+self.clock_error(ideal)
            if self.tx_edges[-1]==self.time:
                self.tx_edges.pop();self.tx_values.pop()
            self.tx_edges.extend(edges[:-1].tolist())
            self.tx_values.extend((held_values+.003*held_values.conj()).tolist())
            self.tx_edges.append(float(edges[-1]));self.tx_values.append(0j)
        elif direction!='idle':raise ValueError('Direction')
        # Optional effective leakage into the warm RX filter. It includes the
        # external coupling and RX conversion gain; no physical isolation claim.
        tx_analog=None
        if direction!='rx' or self.tx_to_rx_filter_coupling:
            tx_analog=analog_hold_at(self.tx_values,self.tx_edges,t,family=self.tx_family,
                cutoff_hz=self.tx_cutoff_hz,integrator_ratio=self.tx_integrator_ratio)
            tx_analog=tx_analog*(1-self.tx_cubic_coefficient*abs(tx_analog)**2)*(rails/3.3)*np.exp(1j*phase)
        if direction=='tx':
            noise=self.rng.normal(size=(len(tx_analog),2))
            tx_analog=tx_analog+.00025*(noise[:,0]+1j*noise[:,1])
        if tx_analog is not None and self.pa_input_p1db_envelope is not None:
            from rf_power_calibration import pa_compression
            if not math.isfinite(self.pa_input_loss_db) or self.pa_input_loss_db<0:
                raise ValueError('Finite nonnegative external TX attenuation required')
            tx_analog=pa_compression(tx_analog*10**(-self.pa_input_loss_db/20),input_p1db_envelope=self.pa_input_p1db_envelope,phase_deg_at_p1db=self.pa_phase_deg_at_p1db)
        if self.tx_to_rx_filter_coupling:
            if not math.isfinite(self.tx_to_rx_filter_coupling) or self.tx_to_rx_filter_coupling<0:
                raise ValueError('Finite nonnegative effective TX/RX coupling required')
            leakage=self.tx_to_rx_filter_coupling*tx_analog*np.exp(-1j*phase)
            if len(leakage):self.max_tx_leak_filter_input_v=max(self.max_tx_leak_filter_input_v,float(max(abs(leakage))))
            inputs['rx']+=leakage
        output={}
        for key,family,cutoff in [('rx','rx_finite_zero',self.rx_cutoff_hz)]:
            state={}
            output[key]=analog_filter(inputs[key],rate,family=family,cutoff_hz=cutoff,initial_state=self.states[key],state_capture=state)
            self.states[key]=state
        self.time+=len(drive)/rate
        if direction=='rx':return output['rx']*self.pga_gain_at(t)
        if direction=='idle':self.rng.normal(size=(len(tx_analog),2)) # retain existing noise stream timeline
        return tx_analog
    def idle(self,dt):
        if dt>0:self.process(np.zeros(max(1,round(dt*80e6)),complex),'idle')

class ClientBench:
    def __init__(self, *, design=None, pga_gain_db=None):
        from design_definition import load_design
        from baseline_envelope import configured_environment
        from selected_lifecycle import selected_transport_assumptions
        self.design=load_design() if design is None else design
        gains=self.design.architecture['blocks']['pga_i']['parameters']['gain_db']
        gains=sorted(set(gains)&set(self.design.architecture['blocks']['pga_q']['parameters']['gain_db']))
        gain=min(gains,key=lambda x:abs(x-28.)) if pga_gain_db is None else pga_gain_db
        self.configuration=self.design.configure(engine='rf',direction='rx',reference_hz=2412e6,
            sample_divider=64,pga_gain_db=gain)
        self.transport_environment=configured_environment(self.configuration)
        transport=self.design.contract['transport']
        if (transport['word_bits'],transport['frame_words'])!=(10,64):
            raise ValueError('Wi-Fi transport fixture requires 10-bit words and 64-word frames')
        self.queue_depth_bits=min(transport['scheduling']['ingress_bits_per_source'],
                                  transport['scheduling']['egress_bits_per_source'])
        rates=self.transport_environment['transport_parameters']
        self.h2d_word_hz=rates['h2d_word_hz'];self.d2h_word_hz=rates['d2h_word_hz']
        self.model_context=dict(design_provenance=self.design.provenance(),
            resolved_configuration=self.configuration.record(),
            model_role='shared_transport_with_simplified_rf_fixture',
            rf_fixture_scope='Retained normalized RF fixture: prescribed rail/phase, assigned converter noise and normalized TX nonlinearity; not the shared complete physical RF chain.')
        self.calibration_hardware_identity=('assumed-die','assumed-board','model-coefficients')
        self.tx_delay_bounds=(.4e-6,.4e-6)
        self.tx_iq_calibration=None
        self.tx_timing_validity=None;self.calibration_operating=None
        self.track_rx_pilot_cfo=self.transport_environment['fpga_tx_preparation']['received_pilot_frequency_update']
        self.data_whitening_seed=431 # diagnostic DATA mask, not a standards scrambler
        self.tx_resampler_span=self.transport_environment['fpga_tx_preparation']['polyphase_resampler_span'];self.tx_resampler_fraction_bits=self.transport_environment['fpga_tx_preparation']['polyphase_resampler_fraction_bits'];self.tx_preemphasis=None;self.couple_peer_clocks=False;self.mcs=7;self.rf=SharedRFPath(environment=self.transport_environment);self.rf.pga_db=gain;self.chip=BehavioralChip(selected_transport_assumptions(self.transport_environment))
        self.tx_preparation=deepcopy(self.transport_environment['fpga_tx_preparation'])
        self.tx_preparation_metadata=None
        if self.tx_preparation['wideband_correction_enabled']:
            from selected_rf import fpga_tx_filter_correction
            _,metadata=fpga_tx_filter_correction(np.zeros(1,complex),sample_hz=FS,
                filter_family=self.rf.tx_family,cutoff_hz=self.rf.tx_cutoff_hz,
                taps=self.tx_preparation['taps'],
                coefficient_fraction_bits=self.tx_preparation['coefficient_fraction_bits'])
            self.tx_preemphasis=(np.asarray(metadata['coefficients']),metadata['alignment_delay_s']*FS)
            self.tx_preparation_metadata=metadata
        self.selected_tx_correction=(None if self.tx_preemphasis is None else
            (tuple(self.tx_preemphasis[0]),self.tx_preemphasis[1]))
        self.selected_tx_filter=(self.rf.tx_family,self.rf.tx_cutoff_hz,self.rf.tx_integrator_ratio)
        c=self.chip;c.configure_transport('exclusive')
        filters=self.transport_environment['filter_parameters']
        ranges={direction:(max(filters[direction+'filter_'+lane]['cutoff_hz'][0] for lane in ('i','q')),
                           min(filters[direction+'filter_'+lane]['cutoff_hz'][1] for lane in ('i','q')))
                for direction in ('rx','tx')}
        c.configure_numeric(engine='rf',rf=dict(sample_hz=FS,sample_clock_source='external_lo',lo_hz=2412e6,
            lo_divider=64,filter_ranges=ranges,**self.rf.filter_settings()))
        c.start();c.advance(c.ready_at);self.origin=c.time
        c.enable_rf_direction_gate(initial='rx');c.enable_rf_sample_launch()
        self.rx_plan=(0,np.zeros(0,np.int64));self.rx_count=0;self.host_tx=[];self.tx_open=math.inf;self.rows=[];self.last_rx_air_end=None;self.peer_offset_hz=43000.;self.measured_cfo_hz=0.
        def rx(i):
            self.rx_count+=1;start,values=self.rx_plan
            return int(values[i-start]) if start<=i<start+len(values) else 0
        self.args=dict(mode=1,source_hz=FS,sample_bits=24,depth_bits=self.queue_depth_bits,directions=('rx','tx'),epoch=0,tx_prefill_bits=0,rx_source=rx,tx_source=lambda i:int(self.host_tx[i]),tx_host_enable=lambda t,i:t>=self.tx_open and i<len(self.host_tx))
    def context_record(self, direction='rx'):
        self.rf.filter_settings()
        configuration=self.design.configure(engine='rf',direction=direction,reference_hz=2412e6,
            sample_divider=64,**({'pga_gain_db':self.rf.pga_db} if direction=='rx' else {}))
        return deepcopy(dict(self.model_context,resolved_configuration=configuration.record(),
            scenario_overrides=self.transport_environment['scenario_overrides'],
            scenario_assumptions=self.transport_environment['scenario_assumptions'],
            operating_conditions=self.transport_environment['operating_conditions'],
            gain_feedback_timing=self.rf.gain_timing(),
            transport_fixture=dict(queue_depth_bits=self.queue_depth_bits,h2d_word_hz=self.h2d_word_hz,
                d2h_word_hz=self.d2h_word_hz,descriptor_h2d_words=384,descriptor_crossing_d2h_ticks=6,
                prefill_reserve_s=.7e-6,scope='Legacy framed transport fixture with the smaller shared planning queue allocation; not actual byte-interface RTL storage or measured command latency.'),
            receiver_allocation=dict({k:v for k,v in self.rf.receiver_context.items() if k!='resolved_configuration'},
                pga_gain_db=self.rf.pga_db,frontend_parameters=dict(self.rf.frontend_parameters),adc_enob=self.rf.adc_enob,
                pga_nominal_peak_limit_v=self.rf.pga_peak_limit_v),
            diagnostic_data_whitening_seed=self.data_whitening_seed,
            fpga_tx_preparation=self.tx_preparation_record(),
            rf_fixture_parameters=dict(clock_configuration=self.rf.clock_configuration(),dac_enob=self.rf.dac_enob,
                shared_design_dac_enob=self.design.architecture['model_assumptions']['paired_dac']['parameters']['enob'],
                normalized_tx_cubic=self.rf.tx_cubic_coefficient,tx_filter_family=self.rf.tx_family,
                tx_cutoff_hz=self.rf.tx_cutoff_hz,rx_cutoff_hz=self.rf.rx_cutoff_hz,
                prescribed_dc_rail_v=3.3,prescribed_rail_ripple_peak_v=.002,
                prescribed_rail_ripple_hz=31.25e6,
                wanted_dbm=self.rf.wanted_dbm,blocker_dbm=self.rf.blocker_dbm,
                external_loss_db=self.rf.external_loss_db,pga_gain_history=list(self.rf.pga_updates),
                note='DAC noise, normalized TX nonlinearity and prescribed rail/phase are explicit fixture assumptions, not complete shared-chain qualification.')))

    def tx_preparation_record(self):
        correction=(None if self.tx_preemphasis is None else
            (tuple(np.asarray(self.tx_preemphasis[0]).tolist()),self.tx_preemphasis[1]))
        selected=(correction==self.selected_tx_correction and
            (self.rf.tx_family,self.rf.tx_cutoff_hz,self.rf.tx_integrator_ratio)==self.selected_tx_filter)
        selected_interpolator=(self.tx_resampler_span==self.tx_preparation['polyphase_resampler_span'] and self.tx_resampler_fraction_bits==self.tx_preparation['polyphase_resampler_fraction_bits'])
        selected_frequency=(self.track_rx_pilot_cfo==self.tx_preparation['received_pilot_frequency_update'])
        return dict(selected_policy=deepcopy(self.tx_preparation),uses_selected_correction=selected,
            received_pilot_frequency_update=self.track_rx_pilot_cfo,
            resampler_span=self.tx_resampler_span,resampler_fraction_bits=self.tx_resampler_fraction_bits,
            resampler_lookahead_s=self.tx_resampler_span/20e6,
            uses_selected_interpolator=selected_interpolator,
            uses_selected_frequency_update=selected_frequency,
            diagnostic_override=not (selected and selected_interpolator and selected_frequency),
            coefficients=None if correction is None else list(correction[0]),
            alignment_delay_s=0. if correction is None else correction[1]/FS,
            scope='FPGA-owned full causal convolution with zero initial record history and flushed FIR tail. Delay is charged to launch, no gain renormalization; physical RF fixture simplifications remain explicit.')

    def tx_configuration_identity(self):
        # FPGA-owned record key derived from the configuration actually used by
        # this bench. No on-chip ID, storage, temperature sensor or protocol ID.
        correction=(None if self.tx_preemphasis is None else
            (tuple(np.asarray(self.tx_preemphasis[0]).tolist()),self.tx_preemphasis[1]))
        return (self.calibration_hardware_identity,FS,2412e6,
            self.rf.tx_family,self.rf.tx_cutoff_hz,self.rf.tx_integrator_ratio,
            self.rf.external_loss_db,self.rf.pa_input_loss_db,
            self.rf.pa_input_p1db_envelope,self.rf.pa_phase_deg_at_p1db,
            self.rf.tx_cubic_coefficient,self.rf.dac_enob,
            self.tx_resampler_span,self.tx_resampler_fraction_bits,correction)

    @property
    def tx_timing_context(self):
        return ('preamble-alignment',self.tx_configuration_identity(),self.tx_delay_bounds)

    @property
    def tx_iq_context(self):
        return ('flat-iq',self.tx_configuration_identity())

    def advance(self,end):
        r=self.chip.transfer(frames=max(1,math.ceil(end*max(self.h2d_word_hz,self.d2h_word_hz)/64)+1),until_s=end,**self.args)
        if r['fault']:raise ValueError('chip '+r['fault'])
    def receive_waveform(self,drive,*,tail_s=0.):
        """80MS/s antenna waveform through shared RF state and finite host queues."""
        self.rf.idle(max(0,self.chip.time-self.origin-self.rf.time))
        start_time=self.rf.time
        filtered=self.rf.process(drive,'rx')
        ticks=np.arange(math.ceil(len(filtered)*FS/80e6))/FS
        ticks+=self.rf.clock_error(start_time+ticks)
        grid=np.arange(len(filtered))/80e6
        native=np.interp(ticks,grid,filtered.real)+1j*np.interp(ticks,grid,filtered.imag)
        if self.rf.pga_peak_limit_v is not None:
            rail=3.3+.002*np.sin(2*np.pi*31.25e6*(start_time+ticks))
            headroom=self.rf.pga_peak_limit_v*rail/3.3
            self.rf.pga_clips+=int(np.sum((abs(native.real)>headroom)|(abs(native.imag)>headroom)))
            native=np.clip(native.real,-headroom,headroom)+1j*np.clip(native.imag,-headroom,headroom)
        noise=self.rf.rng.normal(size=(len(native),2))
        native+=math.sqrt(max(0.,2**(2-2*self.rf.adc_enob)-(1/512)**2)/12)*(noise[:,0]+1j*noise[:,1])
        self.rf.clips+=int(np.sum((abs(native.real)>1)|(abs(native.imag)>1)))
        values=pack(native)
        self.last_rx_air_end=self.rf.time-tail_s
        c=self.chip;start=c.stream['sample_index'] if c.stream else 0;before=self.rx_count
        self.rx_plan=(start,values)
        capture_end=start/FS+len(values)/FS
        self.advance(capture_end)
        # Wait for actual delivery of the final packed ADC pair. The old fixed
        # 2 us drain hid transport latency behind an unrelated fixture delay.
        # Keep the entire capture tail; neither decoding nor RX interpolation
        # gets access to samples before their host words have arrived.
        required_bits=(before+len(values))*24
        drain_deadline=capture_end+2e-6
        while len(c.stream['rx_words'])*10<required_bits:
            if c.time-self.origin>=drain_deadline:raise ValueError('RX delivery deadline')
            self.advance(min(drain_deadline,c.time-self.origin+1/self.d2h_word_hz))
        self.last_rx_delivery=dict(capture_tail_s=tail_s,
            capture_end_s=capture_end,
            host_ready_s=c.time-self.origin,
            transport_drain_s=c.time-self.origin-capture_end)
        delivered=unpack(repack(c.stream['rx_words'],10,24))[before:before+len(values)]
        if len(delivered)!=len(values):raise ValueError('RX not delivered')
        self.last_native_rx=delivered
        self.last_native_rx_valid=self.rf.gain_valid_at(start_time+ticks)
        self.last_rx_valid=resample_poly_validity(self.last_native_rx_valid,320,603)
        return resample_poly(delivered,320,603)
    def receive_intent(self,name,payload):
        wave=source(payload,mcs=self.mcs,whitening_seed=self.data_whitening_seed)
        ratio=1+self.peer_offset_hz/2412e6 if self.couple_peer_clocks else 1.
        _,drive=acquisition_source(wave,4,73,0.,tail_samples=16)
        drive=clock_warp(drive,ratio)
        drive*=np.exp(2j*np.pi*self.peer_offset_hz*np.arange(len(drive))/80e6)
        capture=self.receive_waveform(drive,tail_s=16/20e6/ratio);c=self.chip
        acquisition,corrected=acquire(capture,valid=self.last_rx_valid)
        if corrected is None:raise ValueError('Packet training not acquired')
        self.measured_cfo_hz=acquisition['estimated_cfo_hz']
        if self.couple_peer_clocks:
            if not np.all(self.last_native_rx_valid):
                raise ValueError('Gain validity through clock-rate correction is unqualified')
            # Conditional common-reference relation, not universally valid.
            capture=resample_poly(clock_warp(self.last_native_rx,1/(1+self.measured_cfo_hz/2412e6),taps=129),320,603)
            acquisition,corrected=acquire(capture)
            if corrected is None:raise ValueError('Rate-corrected acquisition failed')
        begin=acquisition['data_start_sample']
        if not self.couple_peer_clocks and not np.all(self.last_rx_valid[begin:begin+len(wave.samples)]):
            raise ValueError('Gain discontinuity inside diagnostic DATA')
        # Repeated LTF cross-power rejects uncorrelated noise bias. Frequency
        # correction precedes measurement; calibration uses this same statistic.
        ltf_power=float(np.real(np.vdot(corrected[begin-128:begin-64],corrected[begin-64:begin])))/64
        self.measured_ltf_power=ltf_power
        result=receive(corrected[begin:begin+len(wave.samples)],len(payload),timing_search=True,mcs=self.mcs,whitening_seed=self.data_whitening_seed)
        good=result['crc_ok'] and result['payload']==payload
        if self.track_rx_pilot_cfo and result['crc_ok'] and result['tail_pilot_frequency_offset_hz'] is not None:
            self.measured_cfo_hz=acquisition['estimated_cfo_hz']+result['tail_pilot_frequency_offset_hz']
        self.rows.append(dict(self.context_record('rx'),reference_evm=reference_evm(result,payload,mcs=self.mcs,whitening_seed=self.data_whitening_seed),preamble_cfo_hz=acquisition['estimated_cfo_hz'],intent=name,direction='rx',crc_ok=good,queue_high_bits=c.stream['high'],estimated_cfo_hz=self.measured_cfo_hz,cfo_error_hz=self.measured_cfo_hz-self.peer_offset_hz,acquisition_decision_sample=acquisition['decision_sample'],ltf_mean_square=ltf_power))
        if not good:raise ValueError('decode '+name)
    def transmit_intent(self,name,payload,*,decision_s=2e-6,gap_s=10e-6,amplitude=.12,samples20=None,decode_samples=None,timing_tolerance_s=.5/FS+1e-15):
        if not all(math.isfinite(x) and x>=0 for x in (decision_s,gap_s)):raise ValueError('Timing')
        if not math.isfinite(amplitude) or amplitude<=0:raise ValueError('TX amplitude')
        if self.couple_peer_clocks:
            # Price RX +TX 129-tap/8x interpolation at the native sample rate.
            decision_s+=2*9/FS
        if (samples20 is None)!=(decode_samples is None):raise ValueError('Waveform and decoder must be supplied together')
        samples=source(payload,mcs=self.mcs,whitening_seed=self.data_whitening_seed).samples if samples20 is None else np.asarray(samples20,complex)
        from rf_filter_tradeoff import tx_resampler_kernel
        kernel=tx_resampler_kernel(self.tx_resampler_span,fraction_bits=self.tx_resampler_fraction_bits)
        resampler_lookahead=self.tx_resampler_span/20e6
        # Centered offline interpolation requires future FPGA input samples.
        # Conservatively charge it after the host decision, before prefill.
        decision_s+=resampler_lookahead
        c=self.chip;native=resample_poly(amplitude*samples,603,320,window=kernel)
        if self.couple_peer_clocks:
            native=clock_warp(native,1+self.measured_cfo_hz/2412e6,taps=129)
        native*=np.exp(2j*np.pi*self.measured_cfo_hz*np.arange(len(native))/FS)
        waveform_delay=0.
        if self.tx_preemphasis is not None:
            coefficients,delay_samples=self.tx_preemphasis
            native=np.convolve(native,coefficients)
            waveform_delay=delay_samples/FS
        operating=(None if self.calibration_operating is None else
            dict(self.calibration_operating,now_s=c.time))
        if self.tx_iq_calibration is not None:
            native=self.tx_iq_calibration.correct(native,context=self.tx_iq_context,operating=operating)
        validate_tx_samples(native)
        native=np.pad(native,(0,(-len(native))%5));pairs=pack(native)
        current=c.time-self.origin;arrival=current+decision_s+384/self.h2d_word_hz+6/self.d2h_word_hz
        anchor=current if self.last_rx_air_end is None else self.last_rx_air_end
        timing=AntennaTimingCalibration(self.tx_timing_context,
            self.tx_delay_bounds[0]+waveform_delay,self.tx_delay_bounds[1]+waveform_delay,self.tx_timing_validity)
        schedule=timing.schedule(anchor+gap_s,sample_hz=FS,
            context=self.tx_timing_context,tolerance_s=timing_tolerance_s,operating=operating)
        target=schedule['counter'];launch=schedule['launch_s']
        if arrival>=launch-.7e-6:
            raise ValueError(f'Late response descriptor/prefill by {(arrival-(launch-.7e-6))*1e6:.6f} us')
        # FPGA preflight covers the entire scheduled waveform, not only
        # descriptor creation. Environmental intervals must cover this duration;
        # future temperature/supply are not predicted by this time-age check.
        end_s=self.origin+launch+len(pairs)/FS+self.tx_delay_bounds[1]
        future=None if operating is None else dict(operating,now_s=end_s)
        validate_calibration(timing.validity,context=self.tx_timing_context,operating=future)
        if self.tx_iq_calibration is not None:
            validate_calibration(self.tx_iq_calibration.validity,context=self.tx_iq_context,operating=future)
        self.tx_open=math.inf;self.host_tx.extend(repack(pairs,24,10).tolist())
        self.advance(arrival);c.arm_rf_sample_launch(encode_time(c.epoch%65536,target,0),0)
        self.tx_open=self.origin+launch-.7e-6
        c.schedule_rf_direction('tx',at_s=self.origin+launch-.5e-6,settle_s=.5e-6)
        stop=(target-1+len(pairs))/FS;c.schedule_rf_direction('rx',at_s=self.origin+stop,settle_s=.5e-6)
        before=len(c.stream.get('tx_samples',[]));self.advance(stop+1e-6)
        emitted=np.asarray(c.stream['tx_samples'][before:],np.int64)
        if not np.array_equal(emitted,pairs):raise ValueError('TX queue payload mismatch')
        self.rf.idle(max(0,launch-self.rf.time))
        ticks=np.arange(math.ceil(len(emitted)*80e6/FS))/80e6
        drive=unpack(emitted)[np.minimum((ticks*FS).astype(int),len(emitted)-1)]
        radiated=self.rf.process(drive,'tx',held_values=unpack(emitted))
        # Physical peer receiver uses its own LO; only the stimulus knows true offset.
        radiated*=np.exp(-2j*np.pi*self.peer_offset_hz*np.arange(len(radiated))/80e6)
        output_mean_square=float(np.mean(abs(radiated)**2))
        # Score packet alignment separately from the first emitted energy.
        # FIR precursors begin at launch; their duration is not free latency.
        if waveform_delay:
            # Ideal peer channel selection prevents DAC images aliasing into
            # the 20MS/s observer; emitted-energy scoring uses raw radiated.
            padded=np.pad(radiated,(2048,2048));bins=np.fft.fftfreq(len(padded),1/80e6)
            selected=np.fft.ifft(np.fft.fft(padded)*(abs(bins)<=10e6))[2048:-2048]
            high=resample_poly(selected,8,1);grid=np.arange(len(high))/640e6
            query=np.arange(math.ceil(len(radiated)/4))/20e6+waveform_delay
            observed=np.interp(query,grid,high.real)+1j*np.interp(query,grid,high.imag)
        else:
            observed=resample_poly(radiated,1,4)
        if self.couple_peer_clocks:
            observed=clock_warp(observed,1/(1+self.peer_offset_hz/2412e6))
        observed=observed[:len(samples)]
        result=receive(observed,len(payload),timing_search=True,mcs=self.mcs,whitening_seed=self.data_whitening_seed) if decode_samples is None else decode_samples(observed)
        good=result['crc_ok'] and result['payload']==payload
        self.rows.append(dict(self.context_record('tx'),calibration_validity_enforced=bool(self.tx_timing_validity is not None and (self.tx_iq_calibration is None or self.tx_iq_calibration.validity is not None)),antenna_packet_end_s=(schedule['earliest_s']+schedule['latest_s'])/2+len(samples)/20e6,intent=name,direction='tx',crc_ok=good,resampler_lookahead_s=resampler_lookahead,scalar_observer_evm=(scalar_observer_evm(observed,payload,mcs=self.mcs,whitening_seed=self.data_whitening_seed) if decode_samples is None else None),reference_evm=(reference_evm(result,payload,mcs=self.mcs,whitening_seed=self.data_whitening_seed) if decode_samples is None else None),peer_pilot_cfo_hz=result.get('pilot_frequency_offset_hz'),response_gap_s=(schedule['earliest_s']+schedule['latest_s'])/2-anchor,response_gap_bounds_s=[schedule['earliest_s']-anchor,schedule['latest_s']-anchor],dac_launch_gap_s=launch-anchor,waveform_delay_s=waveform_delay,precursor_energy_fraction=float(np.sum(abs(radiated[:round(waveform_delay*80e6)])**2)/max(np.sum(abs(radiated)**2),1e-30)),descriptor_arrival_s=arrival,prefill_margin_s=launch-.7e-6-arrival,queue_high_bits=c.stream['tx_high'],residual_cfo_hz=self.measured_cfo_hz-self.peer_offset_hz,output_mean_square=output_mean_square,amplitude=amplitude))
        if not good:raise ValueError('decode '+name)
        self.last_rx_air_end=None
        self.rf.idle(max(0,c.time-self.origin-self.rf.time))

def run(*,rx_loss_db=2.,design=None):
    bench=ClientBench(design=design);bench.rf.external_loss_db=rx_loss_db
    actions=[('rx','discovery',64),('tx','authentication_request',48),('rx','authentication_response',48),('tx','association_request',96),('rx','association_response',64),('tx','association_ack',14),('rx','HE_downlink',512),('tx','ACK',14),('tx','HE_uplink',512),('rx','Block_ACK',32),('rx','trigger',64),('tx','HE_TB_uplink',256),('rx','multi_station_Block_ACK',32)]
    for n,(direction,name,length) in enumerate(actions):
        payload=np.random.default_rng(100+n).integers(0,256,length,dtype=np.uint8).tobytes()
        getattr(bench,'receive_intent' if direction=='rx' else 'transmit_intent')(name,payload)
    return dict(bench.context_record(),scope=__doc__,rx_loss_db=rx_loss_db,completed=True,rows=bench.rows,epoch=bench.chip.epoch,adc_clipped_pairs=bench.rf.clips,pga_clipped_pairs=bench.rf.pga_clips,physical_qualification=False,remaining='Standard PLCP/HE fields and HE acquisition, trigger RU/calibrated power and residual CFO statistics, realistic PA/package spectra and spectral masks; legacy training acquisition and digital frequency correction are modeled, ideal MAC labels are not interoperability proof')
def blocker_screen(*,design=None):
    design=load_design() if design is None else design
    """Fixed-gain CW boundary, not standard adjacent-channel PER qualification."""
    from rf_power_calibration import ReceivePowerCalibration
    payload=bytes(range(256))
    reference=ClientBench(design=design);reference.rf.blocker_dbm=None
    reference.receive_intent('external_known_level',payload)
    calibration=ReceivePowerCalibration(('fixed_gain',),-50.,
        reference.measured_ltf_power,(-65.,-40.),.5)
    rows=[]
    for blocker in (None,-50.,-40.,-30.,-25.,-20.,-18.,-16.,-14.,-12.):
        b=ClientBench(design=design);b.rf.blocker_dbm=blocker
        row=dict(wanted_dbm=-50.,blocker_dbm=blocker,blocker_offset_hz=12e6)
        try:
            b.receive_intent('trigger_training_and_data',payload)
            estimate=calibration.estimate(b.measured_ltf_power,context=calibration.context)
            row.update(decoded=True,rssi_error_db=estimate+50.,
                       cfo_error_hz=b.rows[-1]['cfo_error_hz'])
        except ValueError as error:
            row.update(decoded=False,failure=str(error))
        row.update(b.context_record(),adc_clipped_pairs=b.rf.clips,pga_clipped_pairs=b.rf.pga_clips);rows.append(row)
    return dict(scope='One payload/seed, fixed gain, CW at+12MHz; not PER, '
                'standard WLAN blocker waveform or sensitivity qualification',rows=rows)

def gain_feedback_case(*,wanted_dbm=-65.,blocker_dbm=-40.,mcs=7,initial_pga_db=27,transmit=True,start_sample=73,carrier_offset_hz=43000.,design=None):
    """One observed-level PGA decision through finite transport and analog state.

    Fixed upstream RF/filter response is evaluated ahead; only the downstream
    PGA and ADC execute on source events. No future samples enter host control.
    A sliding short-training correlation gates one peak-based correction; this
    remains a diagnostic controller, not a qualified Wi-Fi AGC.
    """
    from rf_gain_command import GainSampleReceiver,encode_gain,PGA
    if initial_pga_db not in PGA:raise ValueError('Supported initial PGA code required')
    b=ClientBench(design=design,pga_gain_db=initial_pga_db);b.rf.pga_db=0.;b.rf.wanted_dbm=wanted_dbm;b.rf.blocker_dbm=blocker_dbm
    from ble_packet import receiver_pga_response
    gain_tau_s=receiver_pga_response(b.transport_environment)
    payload=np.random.default_rng(314).integers(0,256,512,dtype=np.uint8).tobytes()
    wave=source(payload,mcs=mcs,whitening_seed=b.data_whitening_seed)
    _,drive=acquisition_source(wave,4,start_sample,carrier_offset_hz,transmit=transmit,tail_samples=32)
    filtered=b.rf.process(drive,'rx')
    ticks=np.arange(math.ceil(len(filtered)*FS/80e6))/FS
    grid=np.arange(len(filtered))/80e6
    pre=np.interp(ticks,grid,filtered.real)+1j*np.interp(ticks,grid,filtered.imag)
    rng=np.random.default_rng(9011)
    noise=math.sqrt(max(0.,2**(2-2*b.rf.adc_enob)-(1/512)**2)/12)*(
        rng.normal(size=len(pre))+1j*rng.normal(size=len(pre)))
    gain=PGAGainState(gain_codes_db=b.rf.gain_codes_db,lna_gain_db=b.rf.lna_gain_db);gain.pga_db=initial_pga_db
    from wideband_packet import legacy_preamble
    training,_=legacy_preamble(oversample=8)
    period=np.r_[training[:128],training[0]]
    positions=(np.arange(60)[None,:]*160e6/FS+np.array([[0.]]))%128
    templates=np.interp(positions,np.arange(129),period.real)+1j*np.interp(positions,np.arange(129),period.imag)
    template_energy=np.sum(abs(templates)**2,axis=1)
    host=GainSampleReceiver();delivered={};history=[];decision=[];gaps=[]
    snapshot=[None];clipped=[0];clipped_after_gain=[0];pga_clipped_after_gain=[0]
    def adc(index):
        gain.time=index/FS
        z=pre[index]*gain.pga_gain_at(np.array([index/FS]))[0] if index<len(pre) else 0j
        if index<len(pre):
            rail=3.3+.002*math.sin(2*math.pi*31.25e6*index/FS)
            headroom=b.rf.pga_peak_limit_v*rail/3.3
            pga_clip=int(abs(z.real)>headroom or abs(z.imag)>headroom)
            b.rf.pga_clips+=pga_clip
            if decision and index>=decision[0]['ready_sample']:pga_clipped_after_gain[0]+=pga_clip
            z=complex(np.clip(z.real,-headroom,headroom),np.clip(z.imag,-headroom,headroom))+noise[index]
        clip=int(abs(z.real)>511/512 or abs(z.imag)>511/512)
        clipped[0]+=clip
        if decision and index>=decision[0]['ready_sample']:clipped_after_gain[0]+=clip
        return int(pack(np.array([z]))[0])
    def observe(time,word):
        event=host.feed(word)
        if event is None:return
        if event['kind']=='snapshot':
            snapshot[0]=event['counter']
            samples=event['samples']
        elif event['kind']=='sample':samples=[event]
        elif event['kind']=='gap':gaps.append(event);return
        else:return
        for sample in samples:
            index=sample['sample_index']-snapshot[0]
            delivered[index]=sample['value']
            history.append(complex(unpack([sample['value']])[0]))
        if decision or len(history)<60 or snapshot[0] is None:return
        values=np.asarray(history[-60:])
        score=float(max(abs(templates.conj()@values)**2/np.maximum(template_energy*np.vdot(values,values).real,1e-30)))
        if score<.6:return
        peak=float(max(max(abs(values.real)),max(abs(values.imag))))
        if peak<.003:return
        adjustment=3*math.floor(20*math.log10(.3/peak)/3)
        target=min(gain.gain_codes_db,key=lambda code:abs(code-(initial_pga_db+adjustment)))
        issue=time-b.origin+100e-9
        timing=b.rf.gain_timing()['parts_s']
        commit=math.ceil((issue+timing['command_transport']+timing['cdc_and_commit'])*FS)
        plan=gain.plan_pga(target,commit_s=commit/FS,tau_s=gain_tau_s)
        ready=math.ceil(plan['ready_s']*FS)
        header=encode_gain(gain.lna_gain_db,target,0)
        if target!=initial_pga_db:
            try:
                b.chip.arm_rf_gain_transition(header,0,commit_sample=commit,settling_samples=ready-commit)
            except ValueError as error:
                if str(error)!='Fast gain settling must leave room for24stale pairs':raise
                decision.append(dict(training_score=score,changed=False,requested_change=True,
                    observed_peak=peak,target_db=target,issue_s=issue,commit_sample=commit,
                    ready_sample=ready,settling_samples=ready-commit,admitted=False,
                    rejection=str(error)))
                return
            gain.schedule_pga(target,commit_s=commit/FS,tau_s=gain_tau_s)
        decision.append(dict(training_score=score,changed=target!=initial_pga_db,observed_peak=peak,target_db=target,issue_s=issue,
                             commit_sample=commit,ready_sample=ready))
    b.args['rx_source']=adc;b.args['host_word_observer']=observe
    b.advance(len(pre)/FS+2e-6)
    native=np.zeros(len(pre),complex);valid=np.zeros(len(pre),bool)
    for index,value in delivered.items():
        if 0<=index<len(pre):native[index]=unpack([value])[0];valid[index]=True
    observed=resample_poly(native,320,603)
    accepted=resample_poly_validity(valid,320,603)
    acquisition,corrected=acquire(observed,valid=accepted,coarse_window=32,coarse_plateau=16)
    context=b.context_record()
    context['resolved_configuration']=b.design.configure(engine='rf',direction='rx',reference_hz=2412e6,
        sample_divider=64,pga_gain_db=initial_pga_db).record()
    context['receiver_allocation']['pga_gain_db']=initial_pga_db
    context['rf_fixture_parameters']['pga_gain_history']=list(gain.pga_updates)
    result=dict(context,gain_response_tau_s=gain_tau_s,transmit=transmit,start_sample=start_sample,carrier_offset_hz=carrier_offset_hz,initial_pga_db=initial_pga_db,wanted_dbm=wanted_dbm,blocker_dbm=blocker_dbm,mcs=mcs,
                decision=decision,gaps=gaps,pga_clipped_pairs=b.rf.pga_clips,pga_clipped_after_gain=pga_clipped_after_gain[0],adc_clipped_pairs=clipped[0],adc_clipped_after_gain=clipped_after_gain[0],
                queue_high_bits=b.chip.stream['high'],decoded=False,
                acquisition=acquisition,invalid_native_pairs=int(sum(~valid)))
    rejected=[d for d in decision if d.get('admitted') is False]
    if rejected:
        result.update(status='gain_admission_rejected',failure=rejected[0]['rejection'],
                      gain_settled_before_ltf=False)
        return result
    if corrected is not None:
        begin=acquisition['data_start_sample'];end=begin+len(wave.samples)
        result['gain_settled_before_ltf']=all(d['ready_sample']/FS<=(begin-160)/20e6 for d in decision if d['changed'])
        if not result['gain_settled_before_ltf']:
            result['failure']='Gain did not settle before measured L-LTF boundary'
        elif end>len(accepted) or not np.all(accepted[begin:end]):
            result['failure']='Gain gap or missing samples in DATA'
        else:
            rx=receive(corrected[begin:end],len(payload),mcs=mcs,timing_search=True,whitening_seed=b.data_whitening_seed)
            result['decoded']=bool(rx['crc_ok'] and rx['payload']==payload)
            result['reference_evm']=reference_evm(rx,payload,mcs=mcs,whitening_seed=b.data_whitening_seed)
    return result


def gain_feedback_screen(*,design=None):
    design=load_design() if design is None else design
    return dict(scope='One sliding60-sample L-STF correlation (threshold0.6) gates a peak-based '
        'FPGA gain correction (0.3 component-peak target). Live finite RX queue, '
        'serialized snapshots/status, retained RF/filter and first-order PGA. FPGA acquisition uses32-sample correlation,16-sample plateau and two64-sample LTF checks. Native10-bit ADC with assigned8ENOB noise. '
        'Legacy training plus diagnostic HE-tone DATA, not complete HE packets/PER. '
        '100ns FPGA decision and bounded H2D/CDC delay are assumed; no analog '
        'overload recovery, measured settling or physical host timing proof.',
        rows=[gain_feedback_case(wanted_dbm=w,blocker_dbm=b,mcs=m,initial_pga_db=g,design=design)
              for g in (27,42) for m in (0,7) for w in (-50.,-65.,-75.,-85.) for b in (None,-40.)])


def sensitivity_screen(*,design=None):
    """Fixed supported gain settings; no oracle AGC or standards PER verdict."""
    design=load_design() if design is None else design
    payload=np.random.default_rng(149).integers(0,256,512,dtype=np.uint8).tobytes()
    rows=[]
    for mcs in (0,7):
        for wanted in (-50.,-65.,-75.,-85.):
            for gain in (27.,42.):
                for blocker in (None,-40.):
                    b=ClientBench(design=design);b.mcs=mcs;b.rf.wanted_dbm=wanted
                    b.rf.pga_db=gain;b.rf.blocker_dbm=blocker
                    row=dict(mcs=mcs,wanted_dbm=wanted,pga_db=gain,
                             blocker_dbm=blocker,blocker_offset_hz=12e6)
                    try:
                        b.receive_intent('sensitivity_requirement',payload)
                        row.update(decoded=True,reference_evm=b.rows[-1]['reference_evm'])
                    except ValueError as error:
                        row.update(decoded=False,failure=str(error))
                    row.update(b.context_record(),adc_clipped_pairs=b.rf.clips,pga_clipped_pairs=b.rf.pga_clips);rows.append(row)
    return dict(scope='One payload/noise realization per condition, supported fixed PGA codes; '
        'default assigned LO/supply, 6dB NF and 2dB external loss. No automatic gain selection, '
        'PER, standard blocker, pre-ADC stage overload or silicon sensitivity qualification.',rows=rows)


def modulated_blocker_screen(*,design=None):
    design=load_design() if design is None else design
    """Unwindowed diagnostic OFDM interferer, not a prescribed WLAN test signal."""
    payload=bytes(range(256))
    other=np.random.default_rng(847).integers(0,256,1024,dtype=np.uint8).tobytes()
    _,interferer=waveform_source(source(other),4)
    interferer/=np.sqrt(np.mean(abs(interferer)**2))
    rows=[]
    for cutoff in (9.53125e6,10.5e6):
        changes={}
        for lane in ('i','q'):
            path=f'blocks.rxfilter_{lane}.parameters.cutoff_hz'
            low,high=design.architecture['blocks']['rxfilter_'+lane]['parameters']['cutoff_hz']
            if not low<=cutoff<=high:
                changes[path]=[min(low,cutoff),max(high,cutoff)]
        case_design=(design.hypothetical(reason='Modulated blocker filter bandwidth experiment',
            changes=changes) if changes else design)
        for level in (-60.,-50.,-45.,-40.,-30.,-20.):
            b=ClientBench(design=case_design);b.rf.blocker_wave=interferer
            b.rf.blocker_offset_hz=20e6;b.rf.blocker_dbm=level;b.rf.rx_cutoff_hz=cutoff
            row=dict(cutoff_hz=cutoff,wanted_dbm=-50.,blocker_dbm=level)
            try:
                b.receive_intent('modulated_blocker',payload)
                row.update(decoded=True,cfo_error_hz=b.rows[-1]['cfo_error_hz'])
            except ValueError as error:
                row.update(decoded=False,failure=str(error))
            row.update(b.context_record(),adc_clipped_pairs=b.rf.clips,pga_clipped_pairs=b.rf.pga_clips);rows.append(row)
    return dict(scope='Independent repeating unit-RMS coded OFDM DATA at+20MHz; '
        'unwindowed packet edges and no transmitter mask qualification. '
        'One payload/seed; diagnostic failure is not a WLAN rejection limit.',rows=rows)

def phase_noise_screen(*,track_pilots=None,converter_jitter_ps=0.,tx_candidate=False,tx_cutoff_scale=1.,tx_calibration_scale=1.,resampler_span=None,dac_enob=None,integrator_ratio=None,amplitude=.08,resampler_fraction_bits=None,design=None):
    """Shared finite spectral LO realization; no phase truth reaches receiver."""
    design=load_design() if design is None else design
    from oscillator_noise import PhaseNoise
    if not math.isfinite(converter_jitter_ps) or converter_jitter_ps<0:
        raise ValueError('Nonnegative finite converter jitter required')
    if not math.isfinite(tx_cutoff_scale) or tx_cutoff_scale<=0:
        raise ValueError('Positive finite TX cutoff scale required')
    if not math.isfinite(tx_calibration_scale) or tx_calibration_scale<=0:
        raise ValueError('Positive finite TX calibration scale required')
    if not tx_candidate and (tx_cutoff_scale!=1. or tx_calibration_scale!=1. or integrator_ratio is not None):
        raise ValueError('TX cutoff scale requires candidate mode')
    policy=design.architecture['rf_interoperability']['fpga_tx_preparation']
    track_pilots=policy['received_pilot_frequency_update'] if track_pilots is None else track_pilots
    resampler_span=policy['polyphase_resampler_span'] if resampler_span is None else resampler_span
    resampler_fraction_bits=policy['polyphase_resampler_fraction_bits'] if resampler_fraction_bits is None else resampler_fraction_bits
    dac_enob=design.architecture['model_assumptions']['paired_dac']['parameters']['enob'] if dac_enob is None else dac_enob
    correction=None
    if tx_candidate:
        from rf_filter_tradeoff import tx_preemphasis_coefficients
        coefficients,delay,_=tx_preemphasis_coefficients(cutoff_hz=12e6*tx_calibration_scale,resampler_span=resampler_span,integrator_ratio=integrator_ratio,resampler_fraction_bits=resampler_fraction_bits)
        correction=(coefficients,delay)
    payload=np.random.default_rng(411).integers(0,256,1024,dtype=np.uint8).tobytes()
    rows=[]
    for colored,floor in ((-115.,-155.),(-105.,-150.),(-95.,-140.)):
        for seed in (831,832,833,834):
            b=ClientBench(design=design)
            if tx_candidate:
                b.rf.tx_family='rx_all_pole_control';b.rf.tx_cutoff_hz=12e6*tx_cutoff_scale
                b.tx_preemphasis=correction
            b.rf.dac_enob=dac_enob;b.rf.tx_integrator_ratio=integrator_ratio
            b.tx_resampler_span=resampler_span;b.tx_resampler_fraction_bits=resampler_fraction_bits
            b.track_rx_pilot_cfo=track_pilots
            b.rf.configure_clock_noise(colored=colored,floor=floor,seed=seed,
                converter_jitter_ps=converter_jitter_ps)
            row=dict(colored_at_100khz_dbc_hz=colored,floor_dbc_hz=floor,seed=seed,
                     integrated_phase_rms_rad=math.sqrt(b.rf.phase_noise.variance_rad2))
            try:
                b.receive_intent('phase_noise_request',payload)
                row['cfo_error_hz']=b.rows[-1]['cfo_error_hz']
                row['rx_reference_evm']=b.rows[-1]['reference_evm']
                b.transmit_intent('phase_noise_response',payload,amplitude=amplitude)
                row.update(decoded=True,resampler_lookahead_s=b.rows[-1]['resampler_lookahead_s'],descriptor_arrival_s=b.rows[-1]['descriptor_arrival_s'],response_gap_s=b.rows[-1]['response_gap_s'],tx_scalar_observer_evm=b.rows[-1]['scalar_observer_evm'],tx_reference_evm=b.rows[-1]['reference_evm'],queue_high_bits=b.rows[-1]['queue_high_bits'],
                           peer_pilot_cfo_hz=b.rows[-1]['peer_pilot_cfo_hz'])
            except ValueError as error:
                row.update(decoded=False,failure=str(error))
            row['maximum_clock_error_s']=b.rf.max_clock_error_s
            row.update(b.context_record(),pga_clipped_pairs=b.rf.pga_clips)
            rows.append(row)
    return dict(resampler_fraction_bits=resampler_fraction_bits,dac_enob=dac_enob,integrator_ratio=integrator_ratio,amplitude=amplitude,resampler_span=resampler_span,tx_calibration_scale=tx_calibration_scale,tx_candidate=tx_candidate,tx_cutoff_scale=tx_cutoff_scale,track_rx_pilot_cfo=track_pilots,converter_jitter_rms_ps=converter_jitter_ps,scope='MCS7 diagnostic DATA with legacy acquisition, 12 assigned finite-spectrum cases; '
        'one retained realization across RX, idle and TX, plus existing supply tone and RF impairments. '
        'Not measured GF180 spectra, standard HE packets, statistical CFO qualification or PER. '
        'ADC apertures and DAC edges use the same LO crossing error through ideal division; '
        'optional additive converter-clock phase uses four assigned persistent lines at the converter carrier; '
        'separate ADC/DAC branch noise and host-clock edge timing remain unmodeled here.',rows=rows)

def wifi_source_hashes():
    from reference_input_probe import probe_source_hashes
    from pathlib import Path
    import hashlib
    root=Path(__file__).resolve().parents[1]
    hashes=probe_source_hashes()
    for name in ('verification/wifi_client_exchange.py','verification/he64_packet.py',
                 'verification/rf_filter_tradeoff.py'):
        hashes[name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
    return hashes


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rx-loss-db',type=float,default=2.)
    parser.add_argument('--phase-noise-screen',action='store_true')
    parser.add_argument('--track-pilots',action=argparse.BooleanOptionalAction,default=None)
    parser.add_argument('--tx-candidate',action='store_true')
    parser.add_argument('--tx-cutoff-scale',type=float,default=1.)
    parser.add_argument('--tx-calibration-scale',type=float,default=1.)
    parser.add_argument('--resampler-span',type=int,help='Diagnostic interpolation span override; default uses selected FPGA policy')
    parser.add_argument('--resampler-fraction-bits',type=int)
    parser.add_argument('--dac-enob',type=float,help='Explicit diagnostic DAC noise override; default uses selected design')
    parser.add_argument('--integrator-ratio',type=float)
    parser.add_argument('--amplitude',type=float,default=.08)
    parser.add_argument('--converter-jitter-ps',type=float,default=0.)
    parser.add_argument('--sensitivity-screen',action='store_true')
    parser.add_argument('--gain-feedback-screen',action='store_true')
    parser.add_argument('--blocker-screen',action='store_true')
    parser.add_argument('--modulated-blocker-screen',action='store_true')
    args=parser.parse_args()
    hashes=wifi_source_hashes()
    design=load_design()
    if args.gain_feedback_screen:
        report=gain_feedback_screen(design=design)
    elif args.sensitivity_screen:
        report=sensitivity_screen(design=design)
    elif args.phase_noise_screen:
        report=phase_noise_screen(design=design,track_pilots=args.track_pilots,
            converter_jitter_ps=args.converter_jitter_ps,tx_candidate=args.tx_candidate,
            tx_cutoff_scale=args.tx_cutoff_scale,tx_calibration_scale=args.tx_calibration_scale,
            resampler_span=args.resampler_span,dac_enob=args.dac_enob,
            integrator_ratio=args.integrator_ratio,amplitude=args.amplitude,
            resampler_fraction_bits=args.resampler_fraction_bits)
    elif args.modulated_blocker_screen:
        report=modulated_blocker_screen(design=design)
    elif args.blocker_screen:
        report=blocker_screen(design=design)
    else:
        report=run(design=design,rx_loss_db=args.rx_loss_db)
    if hashes!=wifi_source_hashes():
        raise RuntimeError('Wi-Fi model sources changed during campaign')
    report.update(design_provenance=design.provenance(),sources_sha256=hashes)
    print(json.dumps(report,indent=2))
