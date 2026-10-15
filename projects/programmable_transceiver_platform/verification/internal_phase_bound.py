"""Independent host/timing/core origins: finite-tone voltage and edge bounds."""
import argparse
import math
import hashlib
import json
import numpy as np
import baseline_envelope as b
from reference_input_probe import environment_port, differential_source_peak, reference_source_skew, probe_source_hashes
from selected_rf import clock_supply_sensitivity,clock_supply_delay_pole,reference_acceptance_parameters


from design_definition import load_design,Scenario


def phase_environment(design,mode,carrier,inductance,esl,resistance,scale):
    power=design.architecture['blocks']['power']['parameters']
    if resistance!=power['reduced_pdn_model']['network']['package_r']:
        design=design.hypothetical(reason='Phase-bound feed-resistance experiment',changes={
            'blocks.power.parameters.reduced_pdn_model.network.package_r':resistance})
    settings=dict(engine=mode,direction='rx',reference_hz=carrier)
    if mode=='rf':settings.update(sample_divider=64,pga_gain_db=max(design.architecture['blocks']['pga_i']['parameters']['gain_db']))
    else:settings['host_divider']=8
    config=design.configure(**settings)
    scenario=Scenario();overrides={}
    if inductance!=power['shared_return_l_h']:overrides['package_return_inductance_h']=inductance
    if esl!=power['reduced_pdn_model']['network']['die_esl']:overrides['die_decoupling_esl_h']=esl
    if overrides:scenario=scenario.override(reason='Phase-bound package uncertainty',**overrides)
    environment=b.configured_environment(config,scenario)
    loads=[dict(owner='timing',mean_a=.010*scale,event_hz=carrier/16,tau_s=.2e-9,harmonics=64),
           dict(owner='core',mean_a=.020*scale,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
    context=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),probe_assumptions=dict(internal_switching_loads=loads,
            source_differential_v=differential_source_peak(environment),
            source_leg_skew_s=reference_source_skew(environment,0.),
            threshold_v=reference_acceptance_parameters(environment)['threshold_v'],
            supply_delay_ps_per_mv=clock_supply_sensitivity(environment),
            supply_delay_pole_hz=clock_supply_delay_pole(environment),
            source_origins='Independent groups; preserve intra-source port correlation'))
    return environment,context,loads


def phase_host_groups(environment):
    """Separate correlated directions using the same owned transition charge."""
    host=b.partitioned_host_sources(environment);d2h=b.partitioned_d2h_sources(environment)
    h2d={f:host.get(f,np.zeros(5,complex))-d2h.get(f,np.zeros(5,complex))
         for f in set(host)|set(d2h)}
    return d2h,h2d


def source_extrema(tones, samples=8192, *, fundamental_hz=None):
    """Periodic linear interpolation enclosure: error <= max|v''| dt² / 8."""
    tones=[(f,v) for f,v in tones if abs(v)>1e-18]
    if not tones:return dict(lower_v=0.,upper_v=0.,interpolation_error_v=0.)
    if fundamental_hz is None:
        assert all(abs(f-round(f))<1e-6 for f,v in tones)
        fundamental=math.gcd(*(round(f) for f,v in tones))
    else:
        fundamental=float(fundamental_hz)
        if not math.isfinite(fundamental) or fundamental<=0 or any(abs(f/fundamental-round(f/fundamental))>1e-9 for f,v in tones):
            raise ValueError('Positive common harmonic fundamental required')
    dt=1/(fundamental*samples);t=np.arange(samples)*dt
    wave=sum(np.real(v*np.exp(2j*np.pi*f*t)) for f,v in tones)
    error=sum((2*np.pi*f)**2*abs(v) for f,v in tones)*dt**2/8
    return dict(lower_v=float(min(wave)-error),upper_v=float(max(wave)+error),
                interpolation_error_v=float(error))


def source_off_monitor(groups,threshold):
    """Adversarial peak-aligned periodic input through ideal divide-by-64."""
    from scipy.optimize import brentq
    from behavioral import ReferencePresence
    aligned=[]
    for group in groups:
        group=[(f,v) for f,v in group if abs(v)>1e-18]
        if not group:continue
        period=1/math.gcd(*(round(f) for f,v in group))
        grid=np.arange(8192)*period/8192
        values=sum(np.real(v*np.exp(2j*np.pi*f*grid)) for f,v in group)
        peak_time=grid[np.argmax(values)]
        aligned.extend((f,v*np.exp(2j*np.pi*f*peak_time)) for f,v in group)
    period=1/math.gcd(*(round(f) for f,v in aligned))
    def value(t):return sum(np.real(v*np.exp(2j*np.pi*f*t)) for f,v in aligned)-threshold
    roots=[];counts=[]
    for count in (4096,8192):
        grid=np.linspace(0.,period,count+1);wave=value(grid)
        brackets=np.flatnonzero((wave[:-1]<0)&(wave[1:]>=0))
        roots=[brentq(value,grid[i],grid[i+1],xtol=1e-20) for i in brackets]
        counts.append(len(roots))
    assert counts[0]==counts[1]
    raw=np.array([cycle*period+r for cycle in range(math.ceil(2e-6/period)) for r in roots])
    raw=raw[raw<2e-6];faults=[];qualified=[]
    for residue in range(64):
        edges=list(np.linspace(.9e-6,1e-6,5))+list(1e-6+raw[residue::64])
        monitor=ReferencePresence(edges,timeout_s=100e-9,monitor_tick_s=10e-9,required_edges=4)
        assert monitor.qualified(1e-6)
        fault=monitor.fault_between(1e-6,3e-6)
        faults.append(None if fault is None else fault-1e-6)
        qualified.append(any(monitor.qualified(t) for t in edges if t>=1.5e-6))
    return dict(threshold_v=threshold,source_period_s=period,root_counts_4096_8192=counts,
        source_off_rising_edges_per_period=len(roots),divider_residues=64,
        all_residues_detect_loss=all(t is not None for t in faults),
        latest_loss_detection_delay_s=max((t for t in faults if t is not None),default=None),
        any_late_false_qualification=any(qualified),
        scope='Peak-aligned H2D/core sources, periodic settled interference, root-localized sampled brackets, ideal modulo-64 counter. Five preceding healthy monitor edges, 100 ns timeout and 10 ns tick. Fixed monitor phase; no hysteresis, random noise, comparator chatter, metastability or physical divider behavior.')


def tx_current_margin(environment,rail_interval,opts,clock,frequencies=None):
    """Hypothetical added supply-current tone atop independent activity bounds."""
    if frequencies is None:
        frequencies=np.unique(np.r_[np.geomspace(1e3,5e9,161),environment['carrier_hz']/64,environment['carrier_hz']])
    rows=[];threshold=.035;amplitude=clock['carrier_amplitude_v']
    omega=2*np.pi*environment['carrier_hz']
    for frequency in frequencies:
        response=environment_port(float(frequency),environment,np.array([0.,-1.,0.,1.,0.]),**opts)
        rail_gain=abs(response['network'][1]-response['network'][3])
        input_gain=abs(response['effective']);leg_gain=abs(response['local'])
        delay_gain=rail_gain*abs(b.supply_delay_gain(clock_supply_sensitivity(environment),1.))/abs(1+1j*frequency/clock_supply_delay_pole(environment))
        def checks(current):
            noise=clock['input_peak_v']+current*input_gain
            slope=clock['input_slope_v_per_s']+current*2*np.pi*frequency*input_gain
            return dict(rail=bool(rail_interval[0]-current*rail_gain>=2.5 and rail_interval[1]+current*rail_gain<=3.6),
                input_legs=bool(max(clock['leg_bound_v']+current*leg_gain)<=.6),
                unique_edge=bool(threshold+noise<amplitude and omega*np.sqrt(max(0.,amplitude**2-(threshold+noise)**2))>slope),
                delay_monotonic=bool(clock['delay_slope']+current*2*np.pi*frequency*delay_gain<1))
        baseline=checks(0.);low=0.;high=.028
        if all(baseline.values()):
            if all(checks(high).values()):low=high
            else:
                for _ in range(48):
                    mid=(low+high)/2
                    if all(checks(mid).values()):low=mid
                    else:high=mid
        rows.append(dict(frequency_hz=float(frequency),maximum_sufficient_peak_current_a=float(low),
            baseline_checks=baseline,checks_at_7ma=checks(.007),
            next_boundary_failures=[k for k,v in checks(min(.028,low+1e-8)).items() if not v],
            rail_transfer_abs_ohm=float(rail_gain),input_transfer_abs_ohm=float(input_gain),
            added_delay_peak_at_limit_s=float(low*delay_gain)))
    worst=min(rows,key=lambda x:x['maximum_sufficient_peak_current_a'])
    return dict(cases=rows,minimum_sampled_allowance_a=worst['maximum_sufficient_peak_current_a'],
        most_restrictive_sampled_frequency_hz=worst['frequency_hz'],
        supply_delay_ps_per_mv=clock_supply_sensitivity(environment),
        supply_delay_pole_hz=clock_supply_delay_pole(environment),
        scope='One hypothetical zero-mean supply-current perturbation at a time at the shared local-supply/quiet-return port, atop the caller-provided activity bounds. The 28 mA search cap and 7 mA probe are explicit sensitivity inputs, not an allocated TX bias or a transistor peak-current rating. When called from the RX ADC screen this is an added disturbance, not simultaneous selected TX/RX operation. Includes +/-1% board voltage and arbitrary relative origins of retained baseline groups. 35 mV threshold, 0.6 V input-leg enclosure, shared supply-delay sensitivity and pole. Sufficient voltage/edge conditions only, not jitter/EVM/emissions acceptance. Frequency samples are not a continuum bound; simultaneous tones, reference recharge, switching steps, physical isolation and nonlinear response require a joined waveform test. Zero allowance may mean an already-inconclusive baseline, not physical impossibility.')


def adc_activity_allocation(environment):
    """ADC pair budget without borrowing other owners at the lumped node."""
    return b.adc_pair_current_allocation(environment)


def adc_activity_bounds(environment,base_interval,opts,base_clock):
    """Assigned missing ADC switching budget, distinct from reference recharge."""
    from converter_dynamics import adc_switching_sources
    p=b.environment_converter_parameters(environment);durations=np.asarray(p.bit_durations_s)
    starts=np.r_[0.,np.cumsum(durations[:-1])]
    events=np.r_[-p.acquisition_s,starts,starts+durations-p.comparator_s,sum(durations)]
    core_budget=environment['ledger']['owner_current_a']['core']
    # The electrical network lumps CORE and CONV at one node; that does not
    # authorize transferring DAC or reference current to the ADC pair.
    available=adc_activity_allocation(environment)
    non_adc_reserved=core_budget-available
    rows=[];tx_margin=None
    for divider in (64,256):
        rate=environment['carrier_hz']/divider
        assert 1/rate>=p.acquisition_s+sum(durations)+p.reset_control_s
        for tau in (.2e-9,.5e-9,1e-9):
            tones=[];input_peak=0.;input_slope=0.;leg_peak=np.zeros(2);delay_peak=0.;delay_slope=0.
            for f,injection in adc_switching_sources(sample_hz=rate,mean_a=1.,pulse_tau_s=tau,parameters=p).items():
                response=environment_port(f,environment,injection,**opts)
                tones.append((f,response['network'][1]-response['network'][3]))
                input_peak+=abs(response['effective']);input_slope+=2*np.pi*f*abs(response['effective'])
                leg_peak+=abs(response['local'])
                delay=abs(tones[-1][1])*abs(b.supply_delay_gain(clock_supply_sensitivity(environment),1.))/abs(1+1j*f/clock_supply_delay_pole(environment))
                delay_peak+=delay;delay_slope+=2*np.pi*f*delay
            bound=source_extrema(tones,fundamental_hz=rate)
            for rule in ('constant_mean_stress','fixed_charge_per_conversion'):
                for fast_mean in (.005,.010,available):
                    mean=fast_mean if rule=='constant_mean_stress' else fast_mean*64/divider
                    interval=[base_interval[0]+mean*bound['lower_v'],base_interval[1]+mean*bound['upper_v']]
                    noise=base_clock['input_peak_v']+mean*input_peak
                    slope=base_clock['input_slope_v_per_s']+mean*input_slope
                    amplitude=base_clock['carrier_amplitude_v'];omega=2*np.pi*environment['carrier_hz']
                    timing=[]
                    for threshold in (.020,.035):
                        exists=threshold+noise<amplitude
                        unique=bool(exists and omega*np.sqrt(max(0.,amplitude**2-(threshold+noise)**2))>slope)
                        shift=max(abs(np.arcsin((threshold+sign*noise)/amplitude)-np.arcsin(threshold/amplitude)) for sign in (-1,1))/omega if exists else None
                        timing.append(dict(threshold_v=threshold,unique_rising_edge_sufficient=unique,
                            deterministic_displacement_bound_s=None if shift is None else float(shift+base_clock['delay_peak_s']+mean*delay_peak)))
                    legs=base_clock['leg_bound_v']+mean*leg_peak
                    if divider==64 and tau==.2e-9 and rule=='fixed_charge_per_conversion' and fast_mean==available:
                        tx_margin=tx_current_margin(environment,interval,opts,dict(
                            input_peak_v=noise,input_slope_v_per_s=slope,carrier_amplitude_v=amplitude,
                            leg_bound_v=legs,delay_slope=base_clock['delay_slope']+mean*delay_slope))

                    rows.append(dict(clock_input_leg_bound_v=legs.tolist(),input_envelope_sufficient=bool(max(legs)<=.6),
                        clock_edge_bounds=timing,
                        downstream_delay_map_monotonic_sufficient=bool(base_clock['delay_slope']+mean*delay_slope<1),
                        sample_divider=divider,sample_hz=rate,event_count=len(events),pulse_tau_s=tau,
                        sample_rate_scaling=rule,fast_rate_reference_mean_a=fast_mean,
                        charge_per_conversion_c=mean/rate,
                        adc_switching_mean_a=mean,core_allocation_a=core_budget,
                        non_adc_reserved_a=non_adc_reserved,adc_pair_allocation_a=available,
                        core_budget_fits=bool(mean<=available+1e-15),
                        combined_phase_independent_rail_interval_v=interval,
                        assigned_fixture_enclosed=bool(interval[0]>=2.5 and interval[1]<=3.6)))
    return dict(cases=rows,tx_current_margin=tx_margin,scope='Missing ADC gate/comparator/acquisition/reset supply activity hypotheses. Equal charge per 22 paired-I/Q events using the existing SAR schedule, 128 gamma-pulse harmonics; mean replaces steady ADC current at the lumped CORE/CONV network node. Constant-mean low-rate controls intentionally increase charge per conversion; fixed-charge rows keep energy-per-conversion scaling at fixed supply. Neither law is measured. The current ADC pair allocation limits switching activity; all other CORE/CONV owners remain reserved, including DAC and reference current. Existing 20 mA core pulses remain an explicit activity hypothesis. Independent ADC origin added to existing arbitrary-phase rail enclosure including board tolerance. Not fitted transistor current, code-dependent charge, startup or noise; reference recharge AC is not added here. Clock bounds add ADC harmonic magnitudes to existing independent-source bounds, with shared supply-delay sensitivity and pole. Thresholds are 20 mV legacy and 35 mV worst positive candidate-offset corner. Edge displacement is a deterministic enclosure, not RMS jitter or RF phase-noise qualification. Pulse truncation and waveform shape remain uncertainties.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed-sweep",action="store_true")
    args=parser.parse_args()
    p=b.P
    hashes=probe_source_hashes()
    hashes['verification/internal_phase_bound.py']=hashlib.sha256((p/'verification/internal_phase_bound.py').read_bytes()).hexdigest()
    design=load_design();c=design.contract
    opts=c['physical_services']['external_clock_input']['input_model'];rows=[]
    cases=[(label,l,esl,r,scale) for label,l,esl in b.network_cases(design) for r in ((2.,1.,.5) if args.feed_sweep else (2.,)) for scale in ((1.,2.) if args.feed_sweep else (1.,))]
    for label,inductance,esl,local_r,scale in cases:
        for mode,carrier,word in [('rf',2.4e9,150e6),('rf',2.426e9,2.426e9/16),('rf',2.484e9,155.25e6),('wire',2.5e9,312.5e6)]:
            e,context,loads=phase_environment(design,mode,carrier,inductance,esl,local_r,scale)
            context.update(network_case=label,mode=mode,carrier_hz=carrier,
                           local_feed_resistance_ohm=local_r,internal_pulse_scale=scale)
            d2h,h2d=phase_host_groups(e)
            # Preserve correlations within each source's multi-port injection.
            # Only relative phase between independent source groups is discarded.
            try:
                groups=[d2h,h2d]+[b.internal_switching_sources([x],owner_current_a=e['inventory_current_a']) for x in loads]
            except ValueError as error:
                if str(error)!='Internal pulse mean exceeds owner DC budget':raise
                rows.append(dict(context,status='load_rejected',reason=str(error)));continue
            wanted=environment_port(carrier,e,np.zeros(5),source_diff=differential_source_peak(e),**opts)
            bound=abs(wanted['local']).copy();fixed=bound.copy()
            input_bound=0.;input_slope_bound=0.
            delay_bound=0.;delay_slope_bound=0.
            rail_bound=abs(wanted['network'][1]-wanted['network'][3])
            rail_groups=[[] for g in groups]
            input_groups=[[] for g in groups]
            source_rail=rail_bound
            gain=abs(b.supply_delay_gain(clock_supply_sensitivity(e),1.))
            returned_delay=rail_bound*gain/abs(1+1j*carrier/clock_supply_delay_pole(e))
            delay_bound+=returned_delay;delay_slope_bound+=2*np.pi*carrier*returned_delay
            for f in sorted(set().union(*(g.keys() for g in groups))):
                injections=[g.get(f,np.zeros(5,complex)) for g in groups]
                fixed+=abs(environment_port(f,e,sum(injections),**opts)['local'])
                for group_index,injection in enumerate(injections):
                    r=environment_port(f,e,injection,**opts)
                    bound+=abs(r['local'])
                    rail_phasor=r['network'][1]-r['network'][3]
                    rail_groups[group_index].append((f,rail_phasor))
                    input_groups[group_index].append((f,r['effective']))
                    rail=abs(rail_phasor)
                    rail_bound+=rail
                    input_bound+=abs(r['effective'])
                    input_slope_bound+=2*np.pi*f*abs(r['effective'])
                    delay=rail*gain/abs(1+1j*f/clock_supply_delay_pole(e))
                    delay_bound+=delay;delay_slope_bound+=2*np.pi*f*delay
            assert np.all(bound+1e-12>=fixed)
            amplitude=abs(wanted['effective']);threshold=reference_acceptance_parameters(e)['threshold_v'];omega=2*np.pi*carrier
            amplitude_ok=threshold+input_bound<amplitude
            slope_floor=omega*np.sqrt(amplitude**2-(threshold+input_bound)**2)-input_slope_bound if amplitude_ok else None
            shift=max(abs(np.arcsin((threshold+sign*input_bound)/amplitude)-np.arcsin(threshold/amplitude)) for sign in (-1,1))/omega if amplitude_ok else None
            timing=dict(effective_input_ac_bound_v=float(input_bound),
                rising_slope_lower_bound_v_per_s=None if slope_floor is None else float(slope_floor),
                unique_rising_edge_per_cycle_proven=bool(amplitude_ok and slope_floor>0),
                downstream_delay_derivative_bound=float(delay_slope_bound),
                downstream_time_map_monotonic_proven=bool(delay_slope_bound<1),
                deterministic_edge_displacement_bound_s=None if shift is None else float(shift+delay_bound))
            # LO-derived D2H/timing are absent; H2D and core continue. Preserve
            # each waveform internally while allowing independent source origins.
            off_extrema=[source_extrema(input_groups[i]) for i in (1,3)]
            off_interval=[sum(v['lower_v'] for v in off_extrema),sum(v['upper_v'] for v in off_extrema)]
            loss_detection=dict(source_off_effective_interval_v=off_interval,
                attainable_phase_aligned_peak_v=sum(v['upper_v']-v['interpolation_error_v'] for v in off_extrema),
                positive_threshold_20mv_margin_v=.020-off_interval[1],
                nominal_threshold_20mv_with_5mv_offset_margin_v=.015-off_interval[1],
                threshold_sweep=[dict(nominal_threshold_v=t,assigned_offset_bound_v=.005,
                    source_off_no_crossing_sufficient=t-.005>off_interval[1],
                    source_on_crossing_amplitude_sufficient=bool(t+.005+input_bound<amplitude),
                    source_on_unique_rising_edge_sufficient=bool(t+.005+input_bound<amplitude and omega*np.sqrt(max(0.,amplitude**2-(t+.005+input_bound)**2))>input_slope_bound))
                    for t in (.010,.015,.020,.025,.030,.040)],
                scope='Steady source-off H2D/core only, any independent origins, finite assigned spectra. Positive threshold, zero input DC offset except explicit hypothetical +/-5 mV comparator offset. No random noise, residual stop transient, threshold implementation, edge-rate qualification or watchdog behavior. Unique-edge test additionally applies the existing derivative bound with worst-case offset. Attainable aligned peak sums actual sampled maxima at independently selectable source origins; it excludes interpolation enclosure slack.')
            if label==b.BASELINE_PACKAGE_CASE and carrier==2.426e9 and local_r==2. and scale==1.:
                loss_detection['divided_monitor_controls']=[source_off_monitor([input_groups[i] for i in (1,3)],t) for t in (.015,.020,.025,.030,.035)]
            ledger=b.selected_dc_ledger(mode,e['network'],owner_current_a=e['inventory_current_a'])
            dc=ledger['local_payload_clock_core_rail_v'];drop=3.3-dc
            # Fixed-current linear screen, not a rail-dependent device model.
            interval=[dc-.033-rail_bound,dc+.033+rail_bound]
            source_window=[(2.5+drop+rail_bound)/.99,(3.6+drop-rail_bound)/1.01]
            extrema=[source_extrema(g) for g in rail_groups]
            refined=[dc-.033-source_rail+sum(g['lower_v'] for g in extrema),
                     dc+.033+source_rail+sum(g['upper_v'] for g in extrema)]
            assert refined[0]>=interval[0]-1e-6 and refined[1]<=interval[1]+1e-6
            # Scale only timing/core pulse activity; preserve their owner DC budgets.
            base_lower=dc-.033-source_rail+sum(g['lower_v'] for g in extrema[:2])
            base_upper=dc+.033+source_rail+sum(g['upper_v'] for g in extrema[:2])
            internal_lower=sum(g['lower_v'] for g in extrema[2:])
            internal_upper=sum(g['upper_v'] for g in extrema[2:])
            rail_scale=min((base_lower-2.5)/(-internal_lower),
                           (3.6-base_upper)/internal_upper)
            owner_scale=min(ledger['owner_current_a'][x['owner']]/x['mean_a'] for x in loads)
            double_interval=[base_lower+2/scale*internal_lower,base_upper+2/scale*internal_upper]
            # An added local DC burden also traverses feed and shared return.
            dc_resistance=e['network']['network']['feed_r']+e['network']['network']['package_r']+e['network']['return_r_ohm']
            variation=dict(rail_only_internal_pulse_scale_ceiling=float(rail_scale*scale),
                owner_budget_internal_pulse_scale_ceiling=float(owner_scale*scale),
                doubled_internal_pulses_rail_interval_v=double_interval,
                doubled_internal_pulses_rail_fixture_enclosed=bool(double_interval[0]>=2.5 and double_interval[1]<=3.6),
                additional_local_dc_current_to_legacy_floor_a=float((refined[0]-2.5)/dc_resistance),
                scope='Rail-only sensitivity diagnostic. Scaling replaces steady owner current with pulsed current; no extra DC within the owner budget. Does not qualify clock input, jitter, payload or altered pulse shape. Extra DC diagnostic is outside baseline allocations.')
            headroom=dict(load_variation=variation,sourcewise_rail_interval_v=refined,
                sourcewise_legacy_fixture_enclosed=bool(refined[0]>=2.5 and refined[1]<=3.6),
                sourcewise_extrema=extrema,board_supply_tolerance_fraction=.01,
                conservative_rail_interval_v=interval,
                legacy_fixture_v=[2.5,3.6],
                legacy_fixture_enclosed=bool(interval[0]>=2.5 and interval[1]<=3.6),
                nominal_source_window_for_legacy_fixture_v=source_window,
                source_window_exists=bool(source_window[0]<=source_window[1]),
                scope='Sufficient triangle enclosure at fixed current/linear transfer; outside enclosure is not an observed excursion. Source window is diagnostic, not authorization to raise supply or a device operating rating.')
            adc=adc_activity_bounds(e,refined,opts,dict(input_peak_v=input_bound,input_slope_v_per_s=input_slope_bound,carrier_amplitude_v=amplitude,delay_peak_s=delay_bound,delay_slope=delay_slope_bound,leg_bound_v=bound)) if label==b.BASELINE_PACKAGE_CASE and mode=='rf' and local_r==2. and scale==1. else None
            rows.append(dict(context,status='conditional_phase_bound',adc_activity=adc,
                current_allocation=e['inventory_current_report'],dc_ledger=ledger,headroom=headroom,timing=timing,source_loss_detection=loss_detection, fixed_origin_per_leg_bound_v=fixed.tolist(),
                arbitrary_source_origins_per_leg_bound_v=bound.tolist(),
                input_envelope_proven_for_all_source_origins=bool(max(bound)<=reference_acceptance_parameters(e)['leg_peak_limit_v']),
                arbitrary_source_origins_rail_ac_bound_v=float(rail_bound)))
    if hashes!={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in hashes}:
        raise RuntimeError('Sources changed during probe computation')
    report=dict(design_provenance=design.provenance(),cases=rows,sources_sha256=hashes,scope='Finite-tone linear-network bounds for any D2H/H2D/timing/core origins with fixed selected current spectra. Includes differential source return. Shared incremental per-leg screen; failed bound does not demonstrate violation. Timing uses sufficient amplitude/derivative inequalities, shared threshold and single-pole supply delay. Explicit legacy source-loss and ADC threshold sweeps remain comparison fixtures. No payload, random noise, SAR feedback, frequency drift or different activity spectra, physical bias or lifecycle qualification.')
    b.write_evidence(p/('evidence/local-feed-bound.json' if args.feed_sweep else 'evidence/internal-phase-bound.json'),report)
    for row in rows:print(row['network_case'],row['mode'],row['carrier_hz'],row.get('arbitrary_source_origins_per_leg_bound_v',row.get('reason')),flush=True)


if __name__=='__main__':
    main()
