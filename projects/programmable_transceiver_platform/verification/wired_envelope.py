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
        if 'bit_drive_scale' in impairment:
            scale=np.asarray(impairment['bit_drive_scale'],float)
            if scale.shape!=self.signs.shape or np.any(~np.isfinite(scale)) or np.any(scale<0):raise ValueError('One finite nonnegative drive scale per bit required')
            self.signs*=scale
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
            motion=None
            if impairment.get('bound_aperture_motion',False):
                limit=impairment.get('holdover_ui',64)+2
                table=[aperture_motion_bound(impairment.get('delay_tones',()),n/rate) for n in range(limit+1)]
                maximum=2*sum(t['delay_peak_s'] for t in impairment.get('delay_tones',()))
                def motion(elapsed):
                    index=math.ceil(elapsed*rate)
                    return table[index] if index<=limit else maximum
            super().__init__(bits,rate,phase,ppm,
                             holdover_ui=impairment.get('holdover_ui',64),
                             holdover_residual_ppm=impairment.get('holdover_residual_ppm',50.),
                             frequency_correction_limit_ppm=impairment.get('frequency_correction_limit_ppm',7000.),
                             holdover_frequency_slew_ppm_s=impairment.get('holdover_frequency_slew_ppm_s',330e6),
                             phase_gain=impairment.get('phase_gain',.15),
                             frequency_gain=impairment.get('frequency_gain',.0002),
                             frequency_slope_gain=impairment.get('frequency_slope_gain',0.),
                             detector_noise_rms_s=impairment.get('detector_noise_rms_s',5e-12),
                             detector_model=impairment.get('detector_model','timestamp_fixture'),
                             detector_phase_bins=impairment.get('detector_phase_bins',24),
                             detector_phase_span_ui=impairment.get('detector_phase_span_ui',.375),
                             large_error_phase_gain=impairment.get('large_error_phase_gain',0.),
                             phase_error_threshold_ui=impairment.get('phase_error_threshold_ui',.03125),
                             detector_window_ui=impairment.get('detector_window_ui',0.),
                             gap_frequency_boost=impairment.get('gap_frequency_boost',1.),
                             gap_frequency_boost_after_ui=impairment.get('gap_frequency_boost_after_ui',64),
                             detector_wide_window_ui=impairment.get('detector_wide_window_ui',0.),
                             detector_widen_after_ui=impairment.get('detector_widen_after_ui',64),
                             frequency_window_ui=impairment.get('frequency_window_ui',0),
                             frequency_average_gain=impairment.get('frequency_average_gain',1.),
                             frequency_fit=impairment.get('frequency_fit','interval'),
                             frequency_fit_hop_ui=impairment.get('frequency_fit_hop_ui',0),
                             periodic_clock_compute_delay_s=impairment.get('periodic_clock_compute_delay_s'),
                             periodic_observation_link=impairment.get('periodic_observation_link'),
                             period_control_lsb_ppm=impairment.get('period_control_lsb_ppm',0.),
                             phase_control_steps=impairment.get('phase_control_steps',0),
                             edge_time_bound_s=impairment.get('edge_time_bound_s'),aperture_motion_bound_s=motion)
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
            # Immutable stimulus arrays permit exact batched phase-bank queries.
            self._bank_bits=np.asarray(self.bits,dtype=float)*2-1
            self._bank_channel=np.asarray(self.channel_states)
            self._bank_ctle=None if self.ctle is None else np.asarray(self.ctle[2])
            self._bank_delay=np.asarray([(2*math.pi*x['frequency_hz']/self.rate,x['delay_peak_s'],x['delay_phase_rad']) for x in impairment.get('delay_tones',[])],float).reshape(-1,3)
            self._bank_rail=np.asarray([(2*math.pi*x['frequency_hz']/self.rate,x['clock_rail_voltage_peak_v'],x['voltage_phase_rad']) for x in impairment.get('rail_tones',[])],float).reshape(-1,3)

        def phase_bank_voltages(self,times):
            q=self.impairment
            if self.driver_waveform is not None or 'delay_at_s' in q or 'rail_at_s' in q:
                return super().phase_bank_voltages(times)
            nominal=np.asarray(times,float)
            displacement=math.sqrt(2)*q['jitter_rms_s']*np.sin(2*math.pi*q['jitter_hz']*nominal/self.rate)
            tones=self._bank_delay
            if len(tones):displacement+=np.cos(nominal[:,None]*tones[:,0]+tones[:,2])@tones[:,1]
            actual=nominal+displacement*self.rate
            index=(np.floor(actual).astype(int) if self.source_edges is None else np.searchsorted(self.source_edges,actual/self.rate,side='right')-1)
            if np.any(index>=len(self.bits)) and not hold_final_level:raise ValueError('Finite fixture exhausted')
            valid=index>=0;index=np.clip(index,0,len(self.bits))
            drive=self._bank_bits[np.minimum(index,len(self.bits)-1)]
            dt=((actual-index)/self.rate if self.source_edges is None else actual/self.rate-self.source_edges[index])
            scale=q.get('signal_scale',1.)
            if 'rail_dc_v' in q:
                tones=self._bank_rail
                rail=np.full(len(actual),q['rail_dc_v'])
                if len(tones):rail+=np.cos(actual[:,None]*tones[:,0]+tones[:,2])@tones[:,1]
                self.rail_observations.extend(rail[valid].tolist())
                scale=scale*rail/q['rail_dc_v']
            if self.ctle is not None:
                taus,weights,_=self.ctle
                filtered=np.sum(weights*(drive[:,None]+(self._bank_ctle[index]-drive[:,None])*np.exp(-dt[:,None]/taus)),axis=1)
            else:
                current,voltage=self._bank_channel[index].T
                a=self.driver_tau;b=self.load_tau
                ea=np.exp(-dt/a);eb=np.exp(-dt/b)
                kernel=(dt/b)*eb if abs(a-b)<1e-8*b else a/(a-b)*(ea-eb)
                filtered=drive+(voltage-drive)*eb+(current-drive)*kernel
            signal=.4*scale*filtered
            observed=signal+q['offset_v']+math.sqrt(2)*q['noise_rms_v']*np.sin(2*math.pi*173e6*nominal/self.rate+.71)
            signal=np.where(valid,signal,0.);observed=np.where(valid,observed,0.)
            self.sample_observations[self.bit_index]=(float(nominal[-1]),float(actual[-1]),float(signal[-1]),float(observed[-1]))
            return observed

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
            if 'delay_at_s' in q:displacement+=float(q['delay_at_s'](nominal_ui/self.rate))
            displacement+=sum(t['delay_peak_s']*math.cos(2*math.pi*t['frequency_hz']*nominal_ui/self.rate+t['delay_phase_rad']) for t in q.get('delay_tones',[]))
            time_ui+=float(displacement)*self.rate
            if time_ui<0 and self.source_edges is None:
                self.sample_observations[self.bit_index]=(nominal_ui,time_ui,0.,0.)
                return 0.
            if self.source_edges is None:index=math.floor(time_ui)
            else:
                index=int(np.searchsorted(self.source_edges,time_ui/self.rate,side='right'))-1
                if index<0:
                    self.sample_observations[self.bit_index]=(nominal_ui,time_ui,0.,0.)
                    return 0.
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
                if 'rail_at_s' in q:rail=float(q['rail_at_s'](nominal_ui/self.rate))
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


def aperture_motion_bound(delay_tones, elapsed_s):
    """Phase-independent maximum movement over any interval up to elapsed_s.

    A sinusoid with peak A and frequency f moves by at most
    2*A*sin(min(pi*f*T, pi/2)) for any separation <= T. Summing
    these maxima is conservative for arbitrary relative tone phases.
    This bounds only the supplied spectrum, not omitted noise or transients.
    """
    if not math.isfinite(elapsed_s) or elapsed_s<0:
        raise ValueError('Finite nonnegative elapsed time required')
    total=0.
    for tone in delay_tones:
        frequency=tone['frequency_hz'];amplitude=tone['delay_peak_s']
        if not math.isfinite(frequency) or frequency<=0 or not math.isfinite(amplitude) or amplitude<0:
            raise ValueError('Positive finite tone frequency and nonnegative peak required')
        total+=2*amplitude*math.sin(min(math.pi*frequency*elapsed_s,math.pi/2))
    return total


def holdover_phase_budget(*,rate,gap_ui,initial_phase_ui,timestamp_bound_s,
                          residual_ppm,slew_ppm_s,delay_tones,correction_ui=0.,limit_ui=.25):
    """Inverse requirement screen, not a receiver or a bound on missing noise."""
    values=(rate,gap_ui,initial_phase_ui,timestamp_bound_s,residual_ppm,slew_ppm_s,correction_ui,limit_ui)
    if not all(math.isfinite(x) for x in values) or rate<=0 or limit_ui<=0 or min(values[1:-1])<0:
        raise ValueError('Finite nonnegative budgets and positive rate/limit required')
    elapsed=gap_ui/rate
    components=dict(initial_phase_ui=initial_phase_ui,timestamp_ui=timestamp_bound_s*rate,
        aperture_motion_ui=aperture_motion_bound(delay_tones,elapsed)*rate,
        residual_drift_ui=gap_ui*residual_ppm*1e-6,
        slew_drift_ui=.5*rate*slew_ppm_s*1e-6*elapsed**2,
        correction_ui=correction_ui)
    total=sum(components.values())
    without_residual=total-components['residual_drift_ui']
    return dict(components=components,total_ui=total,margin_ui=limit_ui-total,
        admitted=total<limit_ui,
        residual_ceiling_ppm=None if gap_ui==0 else (limit_ui-without_residual)/gap_ui*1e6,
        scope='Independent allocated bounds summed conservatively; negative residual ceiling means other allocations already exhaust the budget. No physical feasibility, correlations, or protocol acceptance inferred.')


def timestamp_tail_budget(*,bound_s,deterministic_s,noise_rms_s,tail_probability):
    """Conservative per-observation Gaussian tail allocation, not a BER proof."""
    from scipy.special import ndtri
    if (not all(math.isfinite(v) for v in (bound_s,deterministic_s,noise_rms_s,tail_probability))
            or bound_s<=0 or deterministic_s<0 or noise_rms_s<0 or not 0<tail_probability<1):
        raise ValueError('Finite timing allowances and probability in (0,1) required')
    margin=bound_s-deterministic_s
    sigma_multiple=-float(ndtri(tail_probability/2))
    exceedance=(1. if margin<0 else 0. if noise_rms_s==0 else
                math.erfc(margin/(math.sqrt(2)*noise_rms_s)))
    return dict(random_allowance_s=margin,sigma_multiple=sigma_multiple,
        maximum_noise_rms_s=max(0.,margin)/sigma_multiple,
        modeled_tail_probability=exceedance,
        admitted=margin>=0 and exceedance<=tail_probability,
        scope='Worst bounded deterministic offset plus zero-mean Gaussian random error. No measured tail law, correlated-error coverage, lifetime guarantee or conversion to link BER. Other timestamp contributors must fit these same allocations.')


def gap_phase_audit(observations, actual_sample_ui, *, rate, source_edges_s=None, nominal_sample_ui=None, scored_start_bit=0):
    """Offline drift audit; source phase never enters receiver feedback.

    Follow actual (aperture-displaced) sample times relative to the last
    qualified transition. Include the returning-transition sample before
    starting a new gap. Check every sampled point, not only net endpoint drift.
    The initial detector error and assigned uncertainty remain model assumptions.
    """
    import numpy as np
    times=np.asarray(actual_sample_ui,float)
    if len(times)!=len(observations) or not np.all(np.isfinite(times)):
        raise ValueError('One finite actual sample time per committed observation')
    nominal=times if nominal_sample_ui is None else np.asarray(nominal_sample_ui,float)
    if nominal.shape!=times.shape or not np.all(np.isfinite(nominal)):
        raise ValueError('One finite nominal sample time per observation required')
    if type(scored_start_bit) is not int or scored_start_bit<0:
        raise ValueError('Nonnegative integer scoring start required')
    phase=(times if source_edges_s is None else
           np.interp(times/rate,source_edges_s,np.arange(len(source_edges_s))))
    anchor=None;peak=0.;violations=0;long_gaps=[];current=None
    peak_sample=None;scored_peak=0.;scored_peak_sample=None;scored_violations=0
    violation_gaps=dict(shorter_than_16_ui=0,at_least_16_ui=0)
    def finish():
        if current is not None and current['elapsed_ui']>=16:
            long_gaps.append(dict(current))
    for i, observation in enumerate(observations):
        if anchor is not None:
            elapsed=int(observation['bit_index'])-anchor['bit']
            drift=float(phase[i]-anchor['phase']-elapsed)
            bound=anchor['initial_bound']+abs(drift)
            detail=dict(bit_index=int(observation['bit_index']),anchor_bit=anchor['bit'],elapsed_ui=elapsed,
                initial_bound_ui=anchor['initial_bound'],signed_drift_ui=drift,bound_ui=bound,
                nominal_clock_drift_ui=float(nominal[i]-nominal[anchor['index']]-elapsed),
                aperture_change_ui=float((times[i]-nominal[i])-(times[anchor['index']]-nominal[anchor['index']])),
                source_phase_warp_ui=float(phase[i]-anchor['phase']-(times[i]-times[anchor['index']])),
                receiver_qualified=observation['qualified'])
            if bound>peak:peak=bound;peak_sample=detail
            violations+=int(bound>=.25)
            if observation['bit_index']>=scored_start_bit:
                if bound>scored_peak:scored_peak=bound;scored_peak_sample=detail
                scored_violations+=int(bound>=.25)
                if bound>=.25:
                    violation_gaps['shorter_than_16_ui' if elapsed<16 else 'at_least_16_ui']+=1
            current['elapsed_ui']=elapsed
            current['peak_drift_ui']=max(current['peak_drift_ui'],abs(drift))
            current['peak_bound_ui']=max(current['peak_bound_ui'],bound)
        if observation['transition']:
            finish();anchor=current=None
            if observation['qualified']:
                anchor=dict(bit=int(observation['bit_index']),index=i,phase=phase[i],
                    initial_bound=observation['holdover_phase_bound_ui'])
                current=dict(start_bit=anchor['bit'],elapsed_ui=0,
                    peak_drift_ui=0.,peak_bound_ui=anchor['initial_bound'])
    finish()
    return dict(peak_bound_ui=peak,samples_outside_quarter_ui=violations,
                long_gaps=long_gaps,peak_sample=peak_sample,scored_start_bit=scored_start_bit,
                scored_peak_bound_ui=scored_peak,scored_peak_sample=scored_peak_sample,
                scored_samples_outside_quarter_ui=scored_violations,scored_violation_gap_counts=violation_gaps,
                aperture_attribution_available=nominal_sample_ui is not None,
                attribution_scope='Signed algebraic components at the worst recorded sample; not independent noise powers or causal intervention results.',
                scope='Independent source-phase versus actual sample-phase drift; initial receiver phase budget including its assigned edge uncertainty. Sampled extrema, not a continuous-time or physical jitter-mask proof.')


def causal_receiver_envelope(*, impaired=False, timing_scenarios=None, channel_cases=None,source_edges_s=None,source_bits=None,crossing_mode="root",voltage_substeps=4,initial_conditions=None,phase_observation_sink=None,scored_start_bit=1200):
    """Existing sampled feedback loop against physical-time two-pole channels.

    Source bits are available only to the voltage fixture and offline scoreboard,
    never to loop control. Fixed-lag alignment is learned on a separate interval.
    """
    import numpy as np

    bits=np.random.default_rng(9021).integers(0,2,2600).tolist() if source_bits is None else list(source_bits)
    if len(bits)<2600 or any(bit not in (0,1) for bit in bits):
        raise ValueError('At least 2600 binary source bits required')
    stop=((len(bits)-200)//10)*10
    if type(scored_start_bit) is not int or not 1200<=scored_start_bit<stop:
        raise ValueError('Scoring must follow alignment training and precede record end')
    heldout=stop-scored_start_bit
    corners=((- .35,-100.),(-.35,100.),(.35,-100.),(.35,100.)) if initial_conditions is None else initial_conditions
    if not corners or any(not all(math.isfinite(x) for x in pair) or len(pair)!=2 for pair in corners):
        raise ValueError('Finite initial phase/ppm pairs required')
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
            if not math.isfinite(scale) or scale<=0:
                raise ValueError('Finite positive signal scale required')
            if any(not all(math.isfinite(t[k]) for k in ('frequency_hz','delay_peak_s','delay_phase_rad')) or t['frequency_hz']<=0 or t['delay_peak_s']<0 for t in tones):
                raise ValueError('Finite physical timing tones required')
            slope=sum(2*math.pi*t['frequency_hz']*abs(t['delay_peak_s']) for t in tones)
            if not math.isfinite(slope) or slope>=1:raise ValueError('Timing displacement cannot guarantee monotonic sampling')
            row=dict(name=scenario['name'],jitter_rms_s=0.,jitter_hz=25e6,
                     noise_rms_v=.01,offset_v=.02,delay_tones=tones,signal_scale=scale)
            for key in ('holdover_ui','holdover_residual_ppm','frequency_correction_limit_ppm',
                        'holdover_frequency_slew_ppm_s','phase_gain','frequency_gain','frequency_slope_gain','detector_noise_rms_s','detector_model','detector_phase_bins','detector_phase_span_ui','large_error_phase_gain','phase_error_threshold_ui','detector_window_ui','gap_frequency_boost','gap_frequency_boost_after_ui','detector_wide_window_ui','detector_widen_after_ui',
                        'frequency_window_ui','frequency_average_gain','frequency_fit','frequency_fit_hop_ui','periodic_clock_compute_delay_s','periodic_observation_link','period_control_lsb_ppm','phase_control_steps','acquisition_ui','edge_time_bound_s','bound_aperture_motion'):
                if key in scenario:row[key]=scenario[key]
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
    if phase_observation_sink is not None and len(scenarios)*len(channels)*len(corners)!=1:
        raise ValueError('Phase observation capture requires exactly one receiver case')
    for impairment in scenarios:
        for cap,tau in channels:
            for phase,ppm in corners:
                rx=physical_receiver(bits,2.5e9,phase,ppm,tau,cap,impairment,source_edges_s=source_edges_s,crossing_mode=crossing_mode,voltage_substeps=voltage_substeps)
                received=[];qualified=[]
                from receive_qualification import ReceiveQualification
                policy=ReceiveQualification(ui_s=1/2.5e9,
                    holdover_ui=impairment.get('holdover_ui',64),acquisition_ui=impairment.get('acquisition_ui',1024),count_recovered_edges=True)
                timing=[];first_policy_fault=None
                source_edges=None if source_edges_s is None else np.asarray(source_edges_s)
                def observe_timing(observation):
                    nonlocal first_policy_fault
                    verdict=policy.observe(observation['time_s'],
                        transition=observation['transition'],
                        phase_qualified=observation['qualified'],recovered_edge_count=observation['bit_index'])
                    if verdict.fault and first_policy_fault is None:
                        first_policy_fault=dict(reason=verdict.fault,
                            bit_index=observation['bit_index'],time_s=observation['time_s'])
                    measured=observation.get('observed_transition_ui')
                    if phase_observation_sink is not None and measured is not None:
                        phase_observation_sink(observation['bit_index'],measured)
                    # Independent diagnostic only. Source periods never enter
                    # loop feedback or the receive-policy decision above.
                    source_period_ui=1.
                    if source_edges is not None:
                        k=int(np.searchsorted(source_edges,observation['time_s'],side='right'))-1
                        k=max(0,min(k,len(source_edges)-2))
                        source_period_ui=(source_edges[k+1]-source_edges[k])*2.5e9
                    timing.append(dict(observation,
                        free_run_residual_ppm=(source_period_ui/observation['next_period_ui']-1)*1e6,
                        policy_valid=verdict.valid))
                rx.timing_observer=observe_timing
                rx.bit_observer=lambda bit,ready:(received.append(bit),qualified.append(ready))
                for i in range(stop//10):rx.forecast(i);rx.consume(i)
                # Train one constant integer alignment, then freeze it. No
                # time-varying relabeling that could hide slips in the test span.
                lag=min(range(-3,4),key=lambda lag:sum(received[i]!=bits[i+lag] for i in range(600,1200)))
                errors=sum(received[i]!=bits[i+lag] for i in range(scored_start_bit,stop))
                margins=[rx.sample_observations[i][3]*(1 if bits[i+lag] else -1) for i in range(scored_start_bit,stop)]
                controller=rx.periodic_clock_controller
                controller_report=None if controller is None else dict(state=controller.state,
                    activation_cycle=controller.activation_cycle,invalid_cycle=controller.invalid_cycle,
                    invalid_reason=controller.invalid_reason,observations=len(controller.observations),
                    compute_delay_s=controller.compute_delay_ui/rx.rate,fit=controller.fit,
                    maximum_observed_error_ui=controller.maximum_observed_error_ui,
                    locally_validated=controller.local_validated,
                    observation_history_owner='fpga' if controller.link is not None else 'unallocated',
                    observation_link=None if controller.link is None else dict(
                        sent_records=controller.link.sent_records,delivered_records=len(controller.link.fpga_observations),
                        peak_chip_queue_bits=controller.link.peak_queue_bits,queue_capacity_bits=controller.link.queue_bits,
                        fpga_history_bits=80*len(controller.link.fpga_observations),fault=controller.link.fault,
                        word_hz=controller.link.word_hz,word_bits=controller.link.word_bits,latency_s=controller.link.latency_ui/rx.rate,
                        coefficient_return_s=controller.link.return_ui/rx.rate))
                rows.append(dict(rate_bps=2.5e9,pad_cap_f=cap,switch_tau_s=tau,
                    scored_start_bit=scored_start_bit,pre_scored_qualified_bits=sum(qualified[:scored_start_bit]),
                    periodic_clock_controller=controller_report,
                    impairment=impairment,
                    heldout_minimum_signed_sample_v=float(min(margins)),
                heldout_minimum_actual_sample_interval_s=min((rx.sample_observations[i][1]-rx.sample_observations[i-1][1])/rx.rate for i in range(scored_start_bit+1,stop)),
                maximum_aperture_displacement_s=max(abs(v[1]-v[0])/rx.rate for v in rx.sample_observations.values()),
                    heldout_samples_below_100mv=sum(int(v<.1) for v in margins),
                    initial_phase_ui=phase,initial_ppm=ppm,scoreboard_fixed_lag_bits=lag,
                    observed_rail_interval_v=([min(rx.rail_observations),max(rx.rail_observations)] if rx.rail_observations else None),
                    rail_observations_outside_legacy_fixture=sum(not 2.5<=v<=3.6 for v in rx.rail_observations),
                    receive_policy_first_fault=first_policy_fault,
                    measured_gap_phase=gap_phase_audit(timing,
                        [rx.sample_observations[i][1] for i in range(stop)],
                        rate=rx.rate,source_edges_s=source_edges,scored_start_bit=scored_start_bit,
                        nominal_sample_ui=[rx.sample_observations[i][0] for i in range(stop)]),
                    heldout_policy_valid_fraction=sum(t['policy_valid'] for t in timing[scored_start_bit:])/heldout,
                    heldout_free_run_residual_abs_ppm_quantiles=np.quantile(
                        [abs(t['free_run_residual_ppm']) for t in timing[scored_start_bit:]], [0.5,.95,1.]).tolist(),
                    heldout_minimum_instantaneous_residual_margin_ppm=min(
                        t['instantaneous_residual_bound_ppm']-abs(t['free_run_residual_ppm']) for t in timing[scored_start_bit:]),
                    heldout_worst_residual_bound_sample={key:(None if isinstance(value,float) and not math.isfinite(value) else value)
                        for key,value in min(timing[scored_start_bit:],key=lambda t:t['instantaneous_residual_bound_ppm']-abs(t['free_run_residual_ppm'])).items()},
                    heldout_worst_residual_sample={key:(None if isinstance(value,float) and not math.isfinite(value) else value)
                        for key,value in max(timing[scored_start_bit:],key=lambda t:abs(t['free_run_residual_ppm'])).items()},
                    heldout_residual_violations_by_region={
                        'first_4096_scored_bits':sum(abs(t['free_run_residual_ppm'])>t['effective_holdover_residual_ppm'] for t in timing[scored_start_bit:scored_start_bit+4096]),
                        'later_bits':sum(abs(t['free_run_residual_ppm'])>t['effective_holdover_residual_ppm'] for t in timing[scored_start_bit+4096:]),
                        'inside_gap_at_least_16_ui':sum(t['gap_ui']>=16 and abs(t['free_run_residual_ppm'])>t['effective_holdover_residual_ppm'] for t in timing[scored_start_bit:])},
                    heldout_free_run_residual_above_50ppm=int(sum(abs(t['free_run_residual_ppm'])>50 for t in timing[scored_start_bit:])),
                    heldout_declared_residual_bound_violations=int(sum(
                        abs(t['free_run_residual_ppm'])>t['declared_holdover_residual_ppm'] for t in timing[scored_start_bit:])),
                    heldout_effective_residual_bound_violations=int(sum(
                        abs(t['free_run_residual_ppm'])>t['effective_holdover_residual_ppm'] for t in timing[scored_start_bit:])),
                    heldout_instantaneous_residual_bound_violations=int(sum(
                        abs(t['free_run_residual_ppm'])>t['instantaneous_residual_bound_ppm'] for t in timing[scored_start_bit:])),
                    qualified_instantaneous_residual_bound_violations=int(sum(
                        t['qualified'] and abs(t['free_run_residual_ppm'])>t['instantaneous_residual_bound_ppm'] for t in timing[scored_start_bit:])),
                    qualified_effective_residual_bound_violations=int(sum(
                        t['qualified'] and abs(t['free_run_residual_ppm'])>t['effective_holdover_residual_ppm'] for t in timing[scored_start_bit:])),
                    heldout_bits=heldout,heldout_errors=errors,
                    heldout_qualified_fraction=sum(qualified[scored_start_bit:])/heldout,
                    final_timing_qualified=rx.timing_qualified,
                    final_recent_edge_count=len(rx.edge_errors),
                    detector_model=rx.detector_model,phase_magnitude_observed=rx.detector_model=='timestamp_fixture',
                    phase_bound_observed=rx.detector_model in ('timestamp_fixture','phase_bank') or bool(rx.detector_window_ui),
                    final_recent_edge_max_error_ui=max(rx.edge_errors,default=None) if rx.detector_model=='timestamp_fixture' or rx.detector_window_ui else None,
                    qualification_losses=rx.qualification_losses,
                    final_phase_ui=rx.phase,final_frequency_correction_ppm=rx.correction*1e6,first_qualified_bit=rx.first_qualified_bit))
    return dict(cases=rows,status='causal_receiver_conditional_screen',
        crossing_solver=crossing_mode,numerical_voltage_substeps=voltage_substeps,
        readiness_rule='Unwindowed early/late mode has no phase-bound observation and never asserts qualified. Windowed early/late uses its observed phase bracket, never the true edge error; timestamp fixtures use detected magnitudes. Acquire on 64 detected transitions below0.1UI. Tracking uses latest detected error plus the larger of0.0625UI and the optional timestamp bound in UI, and gap times effective residual frequency plus integrated declared frequency slew, strictly below0.25UI and within the configured holdover count. Loss clears acquisition history. Residual-bound violations are independently reported; assigned model rule, not a protocol tolerance mask.',
        assumptions=['Timestamp fixtures use numerical voltage brackets with interpolation or roots; early/late mode uses previous DATA, boundary and current DATA voltage samples without roots. Detector noise is the per-case assigned RMS (legacy default5ps), applied to timestamps or boundary sampling respectively. Numerical subdivisions are not physical phase-count requirements.',
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
