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


def causal_receiver_envelope(*, impaired=False):
    """Existing sampled feedback loop against physical-time two-pole channels.

    Source bits are available only to the voltage fixture and offline scoreboard,
    never to loop control. Fixed-lag alignment is learned on a separate interval.
    """
    import numpy as np
    from behavioral import RecoveredWordSource
    from wired_blocks import CurrentSwitchChannel

    class Receiver(RecoveredWordSource):
        def __init__(self,bits,rate,phase,ppm,tau,cap,impairment):
            super().__init__(bits,rate,phase,ppm)
            self.driver_tau=tau;self.load_tau=50*cap
            self.impairment=impairment
            self.sample_observations={}
            channel=CurrentSwitchChannel(rate,switch_tau_s=tau,load_tau_s=self.load_tau)
            self.channel_states=[]
            for bit in bits:
                self.channel_states.append((channel.current_state,channel.state))
                channel.advance_state(1 if bit else -1,1/rate)

        def voltage(self,time_ui):
            nominal_ui=time_ui
            q=self.impairment
            # Continuous aperture displacement: all four analog observations
            # move, while the controller retains its nominal clock labels.
            displacement=math.sqrt(2)*q['jitter_rms_s']*math.sin(2*math.pi*q['jitter_hz']*time_ui/self.rate)
            time_ui+=displacement*self.rate
            if time_ui<0:return 0.
            index=math.floor(time_ui)
            if index>=len(self.bits):raise ValueError('Finite fixture exhausted')
            current,voltage=self.channel_states[index]
            drive=1 if self.bits[index] else -1
            dt=(time_ui-index)/self.rate;a=self.driver_tau;b=self.load_tau
            ea=math.exp(-dt/a);eb=math.exp(-dt/b)
            kernel=(dt/b)*eb if abs(a-b)<1e-8*b else a/(a-b)*(ea-eb)
            signal=.4*(drive+(voltage-drive)*eb+(current-drive)*kernel)
            disturbance=q['offset_v']+math.sqrt(2)*q['noise_rms_v']*math.sin(2*math.pi*173e6*nominal_ui/self.rate+.71)
            observed=signal+disturbance
            # Last observation at each bit_index is the actual data decision;
            # preceding observations belong to the crossing detector. This is
            # diagnostic fixture storage, not a controller input.
            self.sample_observations[self.bit_index]=(nominal_ui,time_ui,signal,observed)
            return observed

    bits=np.random.default_rng(9021).integers(0,2,2600).tolist()
    rows=[]
    scenarios=[dict(name='baseline',jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.)]
    if impaired:
        scenarios += [dict(name='cleaner_aperture_same_voltage',jitter_rms_s=2e-12,jitter_hz=25e6,noise_rms_v=.01,offset_v=.02),
                      dict(name='moderate_aperture_voltage',jitter_rms_s=10e-12,jitter_hz=25e6,noise_rms_v=.01,offset_v=.02),
                      dict(name='adverse_aperture_voltage',jitter_rms_s=50e-12,jitter_hz=100e6,noise_rms_v=.02,offset_v=.04)]
    for impairment in scenarios:
        for cap,tau in ((1e-12,50e-12),(2e-12,100e-12),(2e-12,200e-12)):
            for phase in (-.35,.35):
                for ppm in (-100.,100.):
                    rx=Receiver(bits,2.5e9,phase,ppm,tau,cap,impairment)
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
                        heldout_bits=1200,heldout_errors=errors,
                        heldout_qualified_fraction=sum(qualified[1200:])/1200,
                        final_timing_qualified=rx.timing_qualified,
                        final_phase_ui=rx.phase,first_qualified_bit=rx.first_qualified_bit))
    return dict(cases=rows,status='causal_receiver_conditional_screen',
        assumptions=['Existing four-observation feedback receiver with its assigned 5 ps IID detector timestamp noise.',
            'Fixed physical two-pole channel, 400 mV differential peak, zero voltage decision threshold.',
            'Random NRZ fixture; independent held-out scoreboard interval; no source labels reach the controller.',
            'Optional sinusoidal aperture jitter moves analog observation times; sinusoidal voltage noise plus DC offset precedes decisions. Assigned stresses, not measured spectra.'],
        unresolved=['Detector timestamp noise is not transmitter or sampling-clock jitter.',
            'Zero decision errors do not establish the 100 mV envelope threshold, BER or protocol compliance.',
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
