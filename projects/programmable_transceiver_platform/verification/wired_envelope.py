"""Generic NRZ electrical/timing envelope, not interface compliance or CDR proof."""
import math


def step_response(t, switch_tau, load_tau):
    if t<=0:return 0.
    if abs(switch_tau-load_tau)<1e-8*load_tau:
        return 1-math.exp(-t/load_tau)*(1+t/load_tau)
    return 1-(load_tau*math.exp(-t/load_tau)-switch_tau*math.exp(-t/switch_tau))/(load_tau-switch_tau)


def history_margin(rate, sample_s, switch_tau, load_tau, postcursor=0., history=64):
    """Worst signed voltage for all independent previous NRZ symbols.

    Peak-normalized one-tap TX emphasis costs steady-state amplitude. Absolute
    pulse-response coefficients bound every binary history; remaining tail is
    charged conservatively. This is stronger than one PRBS/alternating pattern.
    """
    if (not all(math.isfinite(v) for v in (rate,sample_s,switch_tau,load_tau,postcursor))
            or min(rate,switch_tau,load_tau)<=0 or not 0<sample_s<1/rate
            or not 0<=postcursor<1 or type(history) is not int or history<2):
        raise ValueError('Valid channel, sampling point and finite history required')
    step=lambda t:step_response(t,switch_tau,load_tau)
    raw=[step(sample_s)]
    for k in range(1,history):raw.append(step(sample_s+k/rate)-step(sample_s+(k-1)/rate))
    taps=[raw[0]/(1+postcursor)]+[(raw[k]-postcursor*raw[k-1])/(1+postcursor) for k in range(1,history)]
    tail=((1-step(sample_s+(history-1)/rate))+
          postcursor*(1-step(sample_s+(history-2)/rate)))/(1+postcursor)
    return dict(normalized_margin=taps[0]-sum(abs(v) for v in taps[1:])-tail,
                tail_bound=tail,coefficients=taps)


def wired_operating_envelopes(contract):
    rates={}
    for p in contract['protocol_profiles']:
        if p['engine']=='wire':rates.setdefault(float(p['line_rate_bps']),[]).append(p['id'])
    for rate,label in [(1.485e9/1.001,'fractional_video_and_hd_sdi'),
                       (742.5e6,'lower_video'),(742.5e6/1.001,'fractional_lower_video')]:
        rates.setdefault(rate,[]).append(label)
    cases=[]
    for rate,targets in sorted(rates.items()):
        for cap in (1e-12,2e-12,3e-12):
            for tau in (50e-12,100e-12,200e-12):
                for jitter in (2e-12,5e-12,10e-12):
                    half_window=.05/rate+7*jitter
                    for emphasis in (0.,.25,.5):
                        if half_window>=.5/rate:
                            margin=-1.;offset=None
                        else:
                            samples=[.5/rate-half_window+2*half_window*i/20 for i in range(21)]
                            values=[history_margin(rate,t,tau,50*cap,emphasis)['normalized_margin'] for t in samples]
                            index=min(range(len(values)),key=values.__getitem__)
                            margin=values[index];offset=samples[index]*rate
                        phase_options=[]
                        for center in (.5,.65,.8):
                            if center/rate-half_window<=0 or center/rate+half_window>=1/rate:continue
                            points=[center/rate-half_window+2*half_window*i/20 for i in range(21)]
                            phase_options.append((min(history_margin(rate,t,tau,50*cap,emphasis)['normalized_margin'] for t in points),center))
                        best,best_phase=max(phase_options) if phase_options else (-1.,None)
                        cases.append(dict(rate_bps=rate,targets=targets,pad_cap_f=cap,
                            selected_phase_ui=best_phase,phase_adjusted_minimum_signed_sample_v=.4*best,
                            phase_adjusted_diagnostic_pass=.4*best>=.1,
                            switch_tau_s=tau,relative_jitter_rms_s=jitter,postcursor=emphasis,
                            worst_sample_offset_ui=offset,minimum_signed_sample_v=.4*margin,
                            diagnostic_pass=.4*margin>=.1,
                            steady_state_drive_fraction=(1-emphasis)/(1+emphasis)))
    return dict(status='conditional_linear_nrz_envelope',cases=cases,
        assumptions=['400 mV differential peak, 50 ohm per-pole equivalent load, 100 mV signed decision threshold: hypotheses, not protocol masks.',
            'Two real poles: driver response and pad RC. Physical bandwidth stays fixed across line rates.',
            'Timing window includes 0.05 UI deterministic peak plus seven times assigned relative random RMS; not a BER guarantee.',
            'Binary history bound is analytic; timing window sampled at 21 points, not proven continuous-time eye minimum.',
            'Phase-adjusted comparison selects among 0.5/0.65/0.8 UI within the current bit; optimistic receiver phase control, not demonstrated CDR.',
            'TX postcursor preserves peak drive and costs DC/long-run swing; not free equalization.'],
        unresolved=['CDR acquisition, correlated jitter and receiver aperture',
            'protocol-specific common mode, swing, termination, idle and startup',
            'distributed channel/package response and disabled USB loading',
            'TX current/headroom, actual equalizer circuit and full power',
            'multi-chip clock alignment, sustained host service and interoperability'])


class _RailDrivenChannel:
    """Exact linear response to NRZ multiplied by a continuous rail spectrum.

    A particular sinusoidal solution plus the homogeneous state transition
    avoids GHz time stepping. State persists across actual source boundaries.
    The assigned drive/rail sensitivity remains a requirement, not device data.
    """
    def __init__(self,bits,edges,driver_tau,load_tau,impairment):
        import numpy as np
        self.edges=np.asarray(edges,float);self.signs=np.where(bits,1.,-1.)
        taus=[driver_tau,load_tau]
        if any(not math.isfinite(t) or t<=0 for t in taus):raise ValueError('Positive finite driver/load poles required')
        self.output=np.array([0.,1.])
        if 'ctle_zero_s' in impairment:
            zero=impairment['ctle_zero_s'];pole=impairment['ctle_pole_s']
            if not 0<pole<zero or not math.isfinite(zero):
                raise ValueError('Finite CTLE zero time constant above positive pole required')
            taus.append(pole);self.output=np.array([0.,zero/pole,1-zero/pole])
        a=-np.diag(1/np.asarray(taus))
        for i in range(1,len(taus)):a[i,i-1]=1/taus[i]
        b=np.zeros(len(taus));b[0]=1/taus[0]
        self.a=a
        eigenvalues,vectors=np.linalg.eig(a)
        eigenvalues=np.real_if_close(eigenvalues);vectors=np.real_if_close(vectors)
        # Repeated/near-coincident poles use a matrix exponential rather than
        # an ill-conditioned modal subtraction. The normal path is three modes.
        self.modal=None if (np.iscomplexobj(eigenvalues) or np.iscomplexobj(vectors) or
                           np.linalg.cond(vectors)>1e6) else (eigenvalues,vectors,np.linalg.inv(vectors))
        rail=impairment['rail_dc_v']
        if not math.isfinite(rail) or rail<=0:raise ValueError('Positive finite TX rail required')
        tones=impairment['rail_tones']
        if any(not all(math.isfinite(t[k]) for k in ('frequency_hz','clock_rail_voltage_peak_v','voltage_phase_rad'))
               or t['frequency_hz']<=0 or t['clock_rail_voltage_peak_v']<0 for t in tones):
            raise ValueError('Finite positive-frequency rail tones required')
        self.omega=2*np.pi*np.array([t['frequency_hz'] for t in tones])
        phasors=np.array([t['clock_rail_voltage_peak_v']/rail*np.exp(1j*t['voltage_phase_rad']) for t in tones])
        self.response=np.array([np.linalg.solve(1j*w*np.eye(len(taus))-a,b)*v
                               for w,v in zip(self.omega,phasors)],complex).reshape(-1,len(taus))
        self.dc=np.ones(len(taus))
        self.particular_edges=np.array([self.particular(t) for t in self.edges])
        state=np.zeros(len(taus));self.states=[state.copy()]
        for i,sign in enumerate(self.signs):
            state=sign*self.particular_edges[i+1]+self.transition(
                self.edges[i+1]-self.edges[i],state-sign*self.particular_edges[i])
            self.states.append(state.copy())

    def particular(self,time):
        import numpy as np
        return self.dc+np.real(np.exp(1j*self.omega*time)@self.response)

    def transition(self,duration,state):
        import numpy as np
        if self.modal is None:
            # Scaled Taylor plus squaring avoids divided differences of
            # nearly identical exponentials. At norm <= 0.5, 32 terms put
            # truncation far below double-precision roundoff for this 2/3-state
            # system; independent augmented-state tests cover the limit.
            matrix=self.a*duration;norm=float(np.linalg.norm(matrix,np.inf))
            squarings=max(0,math.ceil(math.log2(norm/.5))) if norm else 0
            matrix=matrix/(2.**squarings)
            term=np.eye(len(state));transition=term.copy()
            for k in range(1,33):
                term=term@matrix/k;transition+=term
            for _ in range(squarings):transition=transition@transition
            return transition@state
        values,vectors,inverse=self.modal
        return vectors@(np.exp(values*duration)*(inverse@state))

    def value(self,index,time):
        sign=self.signs[min(index,len(self.signs)-1)]
        state=sign*self.particular(time)+self.transition(time-self.edges[index],
            self.states[index]-sign*self.particular_edges[index])
        return float(self.output@state)


def physical_receiver(bits,rate,phase,ppm,tau,cap,impairment,*,hold_final_level=False,source_edges_s=None,crossing_mode="root",voltage_substeps=4):
    """Reusable physical-time voltage fixture feeding the causal sampled CDR.

    Source bits are confined to channel stimulus and offline scoring. Recovery
    and host logic see sampled decisions and timing qualification only.
    """
    import numpy as np
    from scipy.optimize import brentq
    from behavioral import RecoveredWordSource
    if crossing_mode not in ('linear','root') or type(voltage_substeps) is not int or voltage_substeps<4:
        raise ValueError('Supported crossing solver and at least four numerical subdivisions required')
    from wired_blocks import CurrentSwitchChannel

    class Receiver(RecoveredWordSource):
        def __init__(self,bits,rate,phase,ppm,tau,cap,impairment):
            super().__init__(bits,rate,phase,ppm)
            self.driver_tau=tau;self.load_tau=50*cap
            self.voltage_substeps=voltage_substeps
            self.impairment=impairment
            self.source_edges=None if source_edges_s is None else np.asarray(source_edges_s,float)
            if self.source_edges is not None and (self.source_edges.shape!=(len(bits)+1,) or
                    not np.all(np.isfinite(self.source_edges)) or np.any(np.diff(self.source_edges)<=0)):
                raise ValueError('One finite ordered source boundary per bit plus final boundary required')
            durations=np.full(len(bits),1/rate) if self.source_edges is None else np.diff(self.source_edges)
            self.sample_observations={}
            self.rail_observations=[]  # Diagnostic log shared across forecast snapshots.
            location=impairment.get('rail_modulation_location','receiver')
            if location not in ('receiver','driver'):raise ValueError('Rail modulation must belong to driver or receiver')
            self.driver_waveform=None
            if location=='driver':
                if 'rail_dc_v' not in impairment:raise ValueError('Driver modulation requires a rail spectrum')
                boundaries=np.arange(len(bits)+1)/rate if self.source_edges is None else self.source_edges
                self.driver_waveform=_RailDrivenChannel(bits,boundaries,tau,self.load_tau,impairment)
            self.ctle=None
            if 'ctle_zero_s' in impairment and self.driver_waveform is None:
                zero=impairment['ctle_zero_s'];pole=impairment['ctle_pole_s']
                if not 0<pole<zero or not math.isfinite(zero):
                    raise ValueError('Finite CTLE zero time constant above positive pole required')
                taus=np.array([tau,self.load_tau,pole])
                if min(abs(a-b) for i,a in enumerate(taus) for b in taus[i+1:])<1e-6*max(taus):
                    raise ValueError('Distinct fixture poles required for modal CTLE evaluation')
                # Partial fractions of (1+s*zero) / product(1+s*tau).
                # Each mode is a physical-time low-pass driven only by NRZ.
                weights=np.array([(1-zero/a)/np.prod([1-b/a for j,b in enumerate(taus) if j!=i])
                                  for i,a in enumerate(taus)])
                state=np.zeros(3);states=[]
                for bit,duration in zip(bits,durations):
                    decay=np.exp(-duration/taus)
                    states.append(state.copy());drive=1 if bit else -1
                    state=drive+(state-drive)*decay
                self.ctle=(taus,weights,states+[state.copy()])
            channel=CurrentSwitchChannel(rate,switch_tau_s=tau,load_tau_s=self.load_tau)
            self.channel_states=[]
            for bit,duration in zip(bits,durations):
                self.channel_states.append((channel.current_state,channel.state))
                channel.advance_state(1 if bit else -1,duration)
            self.channel_states.append((channel.current_state,channel.state))

        def locate_crossing(self,left,right,left_voltage,right_voltage):
            if crossing_mode=='linear':
                return super().locate_crossing(left,right,left_voltage,right_voltage)
            # A numerical waveform root, not an added physical sampling phase.
            # The base controller still adds its assigned detector noise once.
            edge=brentq(self.voltage,left,right,xtol=1e-9)
            self.voltage(right)  # Restore the diagnostic observation at the endpoint.
            return edge

        def voltage(self,time_ui):
            nominal_ui=time_ui
            q=self.impairment
            # Continuous aperture displacement: all four analog observations
            # move, while the controller retains its nominal clock labels.
            displacement=math.sqrt(2)*q['jitter_rms_s']*math.sin(2*math.pi*q['jitter_hz']*time_ui/self.rate)
            displacement+=sum(t['delay_peak_s']*math.cos(2*math.pi*t['frequency_hz']*nominal_ui/self.rate+t['delay_phase_rad']) for t in q.get('delay_tones',[]))
            time_ui+=float(displacement)*self.rate
            if time_ui<0 and self.source_edges is None:return 0.
            if self.source_edges is None:index=math.floor(time_ui)
            else:
                index=int(np.searchsorted(self.source_edges,time_ui/self.rate,side='right'))-1
                if index<0:return 0.
            if index>=len(self.bits):
                if not hold_final_level:raise ValueError('Finite fixture exhausted')
                index=len(self.bits)
            drive=1 if self.bits[min(index,len(self.bits)-1)] else -1
            dt=(time_ui-index)/self.rate if self.source_edges is None else time_ui/self.rate-self.source_edges[index]
            scale=q.get('signal_scale',1.)
            if 'rail_dc_v' in q:
                rail=q['rail_dc_v']+sum(t['clock_rail_voltage_peak_v']*math.cos(
                    2*math.pi*t['frequency_hz']*time_ui/self.rate+t['voltage_phase_rad'])
                    for t in q['rail_tones'])
                self.rail_observations.append(rail)
                if self.driver_waveform is None:scale*=rail/q['rail_dc_v']
            if self.driver_waveform is not None:
                signal=.4*scale*self.driver_waveform.value(index,time_ui/self.rate)
            elif self.ctle is not None:
                taus,weights,states=self.ctle
                filtered=float(weights@(drive+(states[index]-drive)*np.exp(-dt/taus)))
                signal=.4*scale*filtered
            else:
                current,voltage=self.channel_states[index]
                a=self.driver_tau;b=self.load_tau
                ea=math.exp(-dt/a);eb=math.exp(-dt/b)
                kernel=(dt/b)*eb if abs(a-b)<1e-8*b else a/(a-b)*(ea-eb)
                signal=.4*scale*(drive+(voltage-drive)*eb+(current-drive)*kernel)
            disturbance=q['offset_v']+math.sqrt(2)*q['noise_rms_v']*math.sin(2*math.pi*173e6*nominal_ui/self.rate+.71)
            observed=signal+disturbance
            # Last observation at each bit_index is the actual data decision;
            # preceding observations belong to the crossing detector. This is
            # diagnostic fixture storage, not a controller input.
            self.sample_observations[self.bit_index]=(nominal_ui,time_ui,signal,observed)
            return observed

    return Receiver(bits,rate,phase,ppm,tau,cap,impairment)


def causal_receiver_envelope(*, impaired=False, timing_scenarios=None, channel_cases=None,source_edges_s=None,source_bits=None,crossing_mode="root",voltage_substeps=4):
    """Existing sampled feedback loop against physical-time two-pole channels.

    Source bits are available only to the voltage fixture and offline scoreboard,
    never to loop control. Fixed-lag alignment is learned on a separate interval.
    """
    import numpy as np

    bits=np.random.default_rng(9021).integers(0,2,2600).tolist() if source_bits is None else list(source_bits)
    if len(bits)!=2600 or any(bit not in (0,1) for bit in bits):
        raise ValueError('This fixed acquisition/held-out window requires 2600 binary source bits')
    rows=[]
    scenarios=[dict(name='baseline',jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.)]
    if impaired:
        scenarios += [dict(name='cleaner_aperture_same_voltage',jitter_rms_s=2e-12,jitter_hz=25e6,noise_rms_v=.01,offset_v=.02),
                      dict(name='moderate_aperture_voltage',jitter_rms_s=10e-12,jitter_hz=25e6,noise_rms_v=.01,offset_v=.02),
                      dict(name='adverse_aperture_voltage',jitter_rms_s=50e-12,jitter_hz=100e6,noise_rms_v=.02,offset_v=.04)]
    if timing_scenarios is not None:
        if impaired or not timing_scenarios:raise ValueError('Choose explicit timing scenarios or legacy impairment sweep')
        scenarios=[]
        for scenario in timing_scenarios:
            tones=scenario['delay_tones']
            scale=scenario.get('signal_scale',1.)
            if not math.isfinite(scale) or not 0<scale<=1:
                raise ValueError('Finite positive attenuating signal scale required')
            if any(not all(math.isfinite(t[k]) for k in ('frequency_hz','delay_peak_s','delay_phase_rad')) or t['frequency_hz']<=0 or t['delay_peak_s']<0 for t in tones):
                raise ValueError('Finite physical timing tones required')
            slope=sum(2*math.pi*t['frequency_hz']*abs(t['delay_peak_s']) for t in tones)
            if not math.isfinite(slope) or slope>=1:raise ValueError('Timing displacement cannot guarantee monotonic sampling')
            row=dict(name=scenario['name'],jitter_rms_s=0.,jitter_hz=25e6,
                     noise_rms_v=.01,offset_v=.02,delay_tones=tones,signal_scale=scale)
            if 'ctle_zero_s' in scenario:
                row.update(ctle_zero_s=scenario['ctle_zero_s'],ctle_pole_s=scenario['ctle_pole_s'])
            if 'rail_dc_v' in scenario:
                if not math.isfinite(scenario['rail_dc_v']) or scenario['rail_dc_v']<=0:
                    raise ValueError('Positive finite local rail required')
                rail_tones=scenario['rail_tones']
                for t in rail_tones:
                    if not all(math.isfinite(t[k]) for k in ('frequency_hz','clock_rail_voltage_peak_v','voltage_phase_rad')) or t['frequency_hz']<=0 or t['clock_rail_voltage_peak_v']<0:
                        raise ValueError('Finite nonnegative rail tones required')
                row.update(rail_dc_v=scenario['rail_dc_v'],rail_tones=rail_tones,
                    rail_modulation_location=scenario.get('rail_modulation_location','receiver'))
            scenarios.append(row)
    channels=((1e-12,50e-12),(2e-12,100e-12),(2e-12,200e-12)) if channel_cases is None else channel_cases
    if not channels or any(not math.isfinite(v) or v<=0 for pair in channels for v in pair):
        raise ValueError('Positive finite channel capacitance and response required')
    for impairment in scenarios:
        for cap,tau in channels:
            for phase in (-.35,.35):
                for ppm in (-100.,100.):
                    rx=physical_receiver(bits,2.5e9,phase,ppm,tau,cap,impairment,source_edges_s=source_edges_s,crossing_mode=crossing_mode,voltage_substeps=voltage_substeps)
                    received=[];qualified=[]
                    rx.bit_observer=lambda bit,ready:(received.append(bit),qualified.append(ready))
                    for i in range(240):rx.forecast(i);rx.consume(i)
                    # Train one constant integer alignment, then freeze it. No
                    # time-varying relabeling that could hide slips in the test span.
                    lag=min(range(-3,4),key=lambda lag:sum(received[i]!=bits[i+lag] for i in range(600,1200)))
                    errors=sum(received[i]!=bits[i+lag] for i in range(1200,2400))
                    margins=[rx.sample_observations[i][3]*(1 if bits[i+lag] else -1) for i in range(1200,2400)]
                    rows.append(dict(rate_bps=2.5e9,pad_cap_f=cap,switch_tau_s=tau,
                        impairment=impairment,
                        heldout_minimum_signed_sample_v=min(margins),
                    heldout_minimum_actual_sample_interval_s=min((rx.sample_observations[i][1]-rx.sample_observations[i-1][1])/rx.rate for i in range(1201,2400)),
                    maximum_aperture_displacement_s=max(abs(v[1]-v[0])/rx.rate for v in rx.sample_observations.values()),
                        heldout_samples_below_100mv=sum(v<.1 for v in margins),
                        initial_phase_ui=phase,initial_ppm=ppm,scoreboard_fixed_lag_bits=lag,
                        observed_rail_interval_v=([min(rx.rail_observations),max(rx.rail_observations)] if rx.rail_observations else None),
                        rail_observations_outside_legacy_fixture=sum(not 2.5<=v<=3.6 for v in rx.rail_observations),
                        heldout_bits=1200,heldout_errors=errors,
                        heldout_qualified_fraction=sum(qualified[1200:])/1200,
                        final_timing_qualified=rx.timing_qualified,
                        final_recent_edge_count=len(rx.edge_errors),
                        final_recent_edge_max_error_ui=max(rx.edge_errors,default=None),
                        qualification_losses=rx.qualification_losses,
                        final_phase_ui=rx.phase,first_qualified_bit=rx.first_qualified_bit))
    return dict(cases=rows,status='causal_receiver_conditional_screen',
        crossing_solver=crossing_mode,numerical_voltage_substeps=voltage_substeps,
        readiness_rule='64 recent detected transitions, each with absolute loop error below 0.1 UI; edge history clears after more than 64 transition-free observations. Assigned model rule, not a protocol tolerance mask.',
        assumptions=['Numerical voltage brackets with selectable linear interpolation or within-bracket roots; unchanged feedback and assigned 5 ps IID detector timestamp noise. Solver subdivisions are not physical phase-count requirements.',
            'Fixed physical two-pole channel, 400 mV nominal differential peak with optional declared amplitude scale, zero voltage decision threshold.',
            'Random NRZ fixture; independent held-out scoreboard interval; no source labels reach the controller.',
            'Sinusoidal or supplied multi-tone aperture displacement moves all analog observations; voltage noise plus DC offset precedes decisions. Supplied tones must guarantee monotonic time. Assigned stresses, not measured spectra.'],
        unresolved=['Detector timestamp noise is not transmitter or sampling-clock jitter.',
            'Zero decision errors do not establish the 100 mV envelope threshold, BER or protocol compliance.',
            'Optional rail-proportional gain is an assigned sensitivity. Driver placement propagates continuous forcing through channel/CTLE state; receiver placement scales the observed signal. Neither is a measured device law.',
            'Optional CTLE is a stable unity-DC lead transfer before the assigned output noise/offset; its gain bandwidth, added noise, internal swing and current still require circuit evidence.',
            'Physical detector, stochastic noise tails, SSC, longer runs and voltage/timing variation remain open.'])


def wired_resource_requirements(contract):
    """Inverse resource requirements, not a fabricated implementation estimate."""
    domains={d['id']:len(d['supply_pins'])*d['per_connection_budget_ma'] for d in contract['power']['domains']}
    rate=2.5e9;rail=3.3;tail=.008
    clock=[]
    for static_ma in (12.,24.,36.):
        remaining=(domains['PLL']-static_ma)*1e-3
        clock.append(dict(static_current_ma=static_ma,
            maximum_equivalent_full_swing_cap_f=max(0.,remaining)/(rail*rate),
            note='Equivalent capacitance includes activity and frequency ratios; all local clock loads counted once.'))
    driver=[]
    for tau in (50e-12,100e-12,200e-12):
        for internal_cap in (.1e-12,.5e-12,1e-12):
            gm=internal_cap/tau
            for efficiency in (5.,10.,15.):
                bias=gm/efficiency
                driver.append(dict(switch_tau_s=tau,internal_pole_cap_f=internal_cap,
                    assumed_gm_over_id_per_v=efficiency,required_effective_gm_s=gm,
                    conditional_single_pole_bias_ma=1000*bias,
                    wire_return_remaining_after_tail_and_this_pole_ma=domains['WIRE']-1000*(tail+bias)))
    return dict(status='inverse_constraints_not_implementation_fit',rate_bps=rate,
        domain_ceiling_ma=domains,termination_tail_current_ma=1000*tail,
        termination_source_power_w=rail*tail,
        clock_distribution=clock,driver_pole=driver,
        area_estimate_um2=None,pin_changes_verified=False,joint_fit_verified=False,
        accounting=['8 mA is one constant total differential tail, not 8 mA per output. With externally supplied terminations it loads chip returns, not necessarily WIRE supply pins; 26.4 mW is termination-source power, not all die dissipation.',
            'Pad charging is supplied by the termination/current-steering path: do not add C*V*f to the same tail as an independent current.',
            'Driver internal pole capacitance differs from the 1–3 pF pad load; tau=C/gm is a topology hypothesis, not a GF180 transistor speed law.',
            'Bias estimate prices only one effective pole. Level shifting, predrivers, serializer, RX, CDR, calibration and inactive leakage remain unpriced.',
            'PLL full-swing current uses I=Ceq*V*f at 2.5 GHz; reduced-swing circuits need their own static/dynamic model.',
            'Aggregate WIRE ceiling does not prove either 48 mA supply connection stays within its allocation.'],
        mitigation_dependencies=['Cleaner external timing does not replace the incoming-data RX CDR or eliminate on-chip additive aperture noise.',
            'Lower pad capacitance needs an ESD/pad/package/loading solution, not merely smaller gate capacitance.',
            'Faster driver pole increases required gm for unchanged internal capacitance; gm/Id, transit delay and parasitics need circuit evidence.',
            'No transistor width, device capacitance per area or physical topology is inferred from these equations. Area remains unknown.'])
