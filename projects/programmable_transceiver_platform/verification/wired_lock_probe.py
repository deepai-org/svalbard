"""Attribute wired readiness failures without changing the lock criterion.

Compare the receiver's four-point linear crossing estimates with independently
solved voltage roots on the SAME detected brackets. This is an offline diagnostic:
exact roots and source bits do not enter the original receiver's feedback.
"""
import hashlib
from copy import deepcopy
import json
import math
from pathlib import Path
import numpy as np
from scipy.optimize import brentq
import baseline_envelope as b
from selected_rf import DeliveredClock
from wired_envelope import physical_receiver,causal_receiver_envelope

P=Path(__file__).resolve().parents[1]


from design_definition import load_design, Scenario


def trace_case(peer,edges,phase=-.35,ppm=-100.):
    bits=np.random.default_rng(9021).integers(0,2,2600).tolist()
    receiver=physical_receiver(bits,2.5e9,phase,ppm,100e-12,2.7e-12,peer,source_edges_s=edges,crossing_mode="linear")
    observations=[];base=type(receiver)
    class TracedReceiver(base):
        def voltage(self,time_ui):
            voltage=super().voltage(time_ui)
            observations.append((self.bit_index,float(time_ui),float(voltage)))
            return voltage
    receiver.__class__=TracedReceiver
    decisions=[];qualified=[]
    receiver.bit_observer=lambda bit,ready:(decisions.append(bit),qualified.append(ready))
    for word in range(240):receiver.forecast(word);receiver.consume(word)
    probe=physical_receiver(bits,2.5e9,phase,ppm,100e-12,2.7e-12,peer,source_edges_s=edges,crossing_mode="linear")
    noise=np.random.default_rng(421);crossings=[]
    for previous,current in zip(observations,observations[1:]):
        _,left,vl=previous;i,right,vr=current
        if vl*vr>=0:continue
        linear=left+(right-left)*(-vl)/(vr-vl)
        root=brentq(probe.voltage,left,right,xtol=1e-9)
        timestamp_noise=float(noise.normal(0,5e-12*2.5e9))
        sample_time=receiver.sample_observations[i][0]
        error=(sample_time-linear+timestamp_noise)%1-.5
        root_error=(sample_time-root+timestamp_noise)%1-.5
        crossings.append(dict(bit=i,linear_crossing_ui=linear,root_crossing_ui=root,
            interpolation_error_ui=linear-root,detector_noise_ui=timestamp_noise,
            actual_loop_error_ui=error,root_at_same_sample_error_ui=root_error))
    assert len(crossings)==receiver.detected_edges
    np.testing.assert_allclose([abs(c['actual_loop_error_ui']) for c in crossings[-64:]],list(receiver.edge_errors),atol=1e-11,rtol=0.)
    lag=min(range(-3,4),key=lambda lag:sum(decisions[i]!=bits[i+lag] for i in range(600,1200)))
    held=[c for c in crossings if 1200<=c['bit']<2400]
    interpolation=np.array([c['interpolation_error_ui'] for c in held])
    violations=[c for c in held if abs(c['actual_loop_error_ui'])>=.1]
    margins=[receiver.sample_observations[i][3]*(1 if bits[i+lag] else -1) for i in range(1200,2400)]
    return dict(deepcopy(peer.get('probe_context',{})),initial_phase_ui=phase,initial_ppm=ppm,heldout_errors=sum(decisions[i]!=bits[i+lag] for i in range(1200,2400)),
        heldout_minimum_signed_voltage_v=min(margins),heldout_qualified_fraction=sum(qualified[1200:])/1200,
        final_timing_qualified=receiver.timing_qualified,heldout_detected_crossings=len(held),
        interpolation_error_rms_ps=float(np.sqrt(np.mean(interpolation**2))/2.5e9*1e12),
        interpolation_error_abs_peak_ps=float(max(abs(interpolation))/2.5e9*1e12),
        heldout_loop_violations=len(violations),
        root_errors_above_same_limit_at_original_samples=sum(abs(c['root_at_same_sample_error_ui'])>=.1 for c in held),
        violations=violations,
        scope='Offline roots inside brackets already detected by the original receiver. The root-based errors retain the original sampling trajectory and detector-noise samples; they do not predict a retimed feedback loop. No extra-crossing, BER, protocol-mask or physical phase-detector qualification.')



def resolved_case(peer,edges,phase,ppm,substeps,exact):
    bits=np.random.default_rng(9021).integers(0,2,2600).tolist()
    rx=physical_receiver(bits,2.5e9,phase,ppm,100e-12,2.7e-12,peer,source_edges_s=edges,
        crossing_mode='root' if exact else 'linear',voltage_substeps=substeps)
    received=[];ready=[]
    rx.bit_observer=lambda bit,qualified:(received.append(bit),ready.append(qualified))
    for word in range(240):rx.forecast(word);rx.consume(word)
    lag=min(range(-3,4),key=lambda lag:sum(received[i]!=bits[i+lag] for i in range(600,1200)))
    return dict(deepcopy(peer.get('probe_context',{})),initial_phase_ui=phase,initial_ppm=ppm,substeps=substeps,exact_roots=exact,
        readiness=sum(ready[1200:])/1200,final_qualified=bool(rx.timing_qualified),
        detected_edges=rx.detected_edges,
        errors=sum(received[i]!=bits[i+lag] for i in range(1200,2400)),
        minimum_margin_v=min(rx.sample_observations[i][3]*(1 if bits[i+lag] else -1) for i in range(1200,2400)))


def probe_environment(contract,peak,*,engine='wire',carrier=2.5e9,internal_loads=(),
                      die_cap_f=None,sensitivity_ps_per_mv=.1,design=None):
    """Resolve the selected design and explicitly label circuit/probe departures."""
    design=b.design_for_contract(contract,design)
    if die_cap_f is not None:
        if not math.isfinite(die_cap_f) or die_cap_f<=0:raise ValueError('Positive local capacitance required')
        path='blocks.power.parameters.reduced_pdn_model.network.die_c'
        nominal=design.architecture['blocks']['power']['parameters']['reduced_pdn_model']['network']['die_c']
        if die_cap_f!=nominal:
            design=design.hypothetical(reason='Readiness mitigation: change local die decoupling',
                                       changes={path:die_cap_f})
    if not math.isfinite(sensitivity_ps_per_mv) or sensitivity_ps_per_mv<0:
        raise ValueError('Nonnegative finite supply-delay sensitivity required')
    settings=dict(engine=engine,direction='tx' if engine=='wire' else 'rx',reference_hz=carrier)
    if engine=='wire':settings['host_divider']=8
    else:
        settings.update(sample_divider=64,pga_gain_db=max(design.architecture['blocks']['pga_i']['parameters']['gain_db']))
    config=design.configure(**settings)
    scenario=Scenario(reference_peak_v=peak)
    original=b.configured_environment(config,scenario)
    # Explicit physical hypotheses: these pulse loads and supply-delay slope are
    # not inferred from the block inventory or claimed as characterized silicon.
    assumptions=dict(internal_switching_loads=[dict(load) for load in internal_loads],
        sensitivity_ps_per_mv=sensitivity_ps_per_mv,
        reason='Assigned switching-current and supply-delay sensitivity probe')
    original['internal_switching_loads']=assumptions['internal_switching_loads']
    context=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),scenario_stimuli=scenario.stimulus_record(),
        probe_assumptions=assumptions)
    environment,clock=b.reference_payload_environment(original,dict(link_r_ohm=1e-5),False,
        source_peak_v=peak,sensitivity_ps_per_mv=sensitivity_ps_per_mv)
    if environment is not None:environment['probe_context']=context
    return environment,dict(clock,**context)


def environment_for(contract,peak,offset,*,internal_loads=(),die_cap_f=None,sensitivity_ps_per_mv=.1,design=None):
    """Current differential clock path with explicit drive/load/sensitivity probes."""
    environment,_=probe_environment(contract,peak,internal_loads=internal_loads,die_cap_f=die_cap_f,
        sensitivity_ps_per_mv=sensitivity_ps_per_mv,design=design)
    if environment is None:raise ValueError('Reference clock rejected')
    return peer_for_environment(environment,offset)


def peer_for_environment(environment,offset):
    bound='design_provenance' in environment or 'inventory_current_report' in environment
    config=environment.get('resolved_configuration')
    if bound or config is not None:
        if (not isinstance(config,dict) or config.get('engine')!='wire'
                or config.get('direction') not in ('tx','duplex')
                or config.get('line_rate_bps')!=2.5e9 or config.get('reference_hz')!=2.5e9):
            raise ValueError('Wired readiness peer requires a resolved 2.5 Gb/s TX configuration')
        provenance=environment.get('design_provenance')
        if not isinstance(provenance,dict) or not provenance or any(config.get(k)!=v for k,v in provenance.items()):
            raise ValueError('Wired peer configuration conflicts with environment provenance')
        context=environment.get('probe_context')
        if (not isinstance(context,dict) or context.get('design_provenance')!=provenance
                or context.get('resolved_configuration')!=config):
            raise ValueError('Wired peer requires matching probe context')
    origin=offset/2.5e9;ideal=np.arange(2601)/2.5e9;absolute=origin+ideal
    edges=absolute+DeliveredClock(environment).crossing_error(absolute,2.5e9)-origin
    rail=environment['ledger']['local_payload_clock_core_rail_v']
    peer=dict(name='readiness_attribution',delay_tones=[],signal_scale=rail/b.wired_gain_reference(environment),rail_dc_v=rail,
        rail_tones=[dict(t,voltage_phase_rad=t['voltage_phase_rad']+2*math.pi*t['frequency_hz']*origin) for t in environment['host_spectrum']['tones']],
        rail_modulation_location='driver',ctle_zero_s=200e-12,ctle_pole_s=80e-12,
        jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=.01,offset_v=.02)
    if 'probe_context' in environment:peer['probe_context']=deepcopy(environment['probe_context'])
    return peer,edges,ideal


def internal_load_campaign(contract, *, design=None):
    design=b.design_for_contract(contract,design)
    rows=[]
    for scale in (0.,.5,1.):
        loads=[dict(owner='timing',mean_a=.010*scale,event_hz=156.25e6,tau_s=.2e-9,harmonics=64),
               dict(owner='core',mean_a=.020*scale,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)] if scale else []
        for offset in (0,4,8,12):
            peer,edges,_=environment_for(contract,.75,offset,internal_loads=loads,design=design)
            for phase in (-.35,.35):
                for ppm in (-100.,100.):
                    result=resolved_case(peer,edges,phase,ppm,4,True)
                    refinement=resolved_case(peer,edges,phase,ppm,16,True) if offset==0 and phase==-.35 and ppm==-100. else None
                    rows.append(dict(load_scale=scale,launch_offset_ui=offset,loads=loads,result=result,numerical_refinement=refinement))
            print('internal load',scale,offset,flush=True)
    return dict(cases=rows,scope='2.5 Gb/s, 0.75 V source, current 0.25 nH package target, current wired inventory allocation. 64-harmonic assigned core/timing pulses affect source clock edges and TX driver rail before channel filtering. Independent receiver retains CTLE, 5 ps timestamp noise and 64-edge/0.1 UI readiness. Four nominal launch phases and four initial receiver corners per load; no BER, asynchronous-current phase or physical detector qualification.')


def mitigation_payload_campaign(contract, *, sensitivity=False,design=None):
    design=b.design_for_contract(contract,design)
    wired=[];rf=[]
    for cap,gain in ([(500e-12,.1),(500e-12,.025)] if sensitivity else [(500e-12,.1),(1e-9,.1)]):
        loads=[dict(owner='timing',mean_a=.010,event_hz=156.25e6,tau_s=.2e-9,harmonics=64),
               dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
        for offset in (0,4,8,12):
            peer,edges,_=environment_for(contract,.75,offset,internal_loads=loads,die_cap_f=cap,sensitivity_ps_per_mv=gain,design=design)
            for phase in (-.35,.35):
                for ppm in (-100.,100.):
                    wired.append(dict(die_cap_f=cap,sensitivity_ps_per_mv=gain,launch_offset_ui=offset,
                        result=resolved_case(peer,edges,phase,ppm,4,True)))
        print('Mitigation wired',cap,gain,flush=True)
        for carrier in (2.4e9,2.484e9):
            e,clock=probe_environment(contract,.75,engine='rf',carrier=carrier,
                internal_loads=[dict(loads[0],event_hz=carrier/16),loads[1]],
                die_cap_f=cap,sensitivity_ps_per_mv=gain,design=design)
            receiver=None if e is None else b.coupled_wideband_feedback(e,wanted_dbm=-85.,gain_db=b.receiver_inventory_options(e)['maximum_gain_db'],oversample=1024)
            rf.append(dict(die_cap_f=cap,sensitivity_ps_per_mv=gain,carrier_hz=carrier,clock=clock,receiver=receiver))
            print('Mitigation RF',cap,gain,carrier,flush=True)
    return dict(wired=wired,rf=rf,scope='Explicit capacitance and downstream sensitivity cases; positive sensitivity sign and zero relative internal pulse origin. Fixed 0.5 ohm ESR/200 pH ESL, 0.25 nH package target, 0.75 V source, full internal current pulse hypothesis and current RF/wired inventory allocations. Wired uses independent CTLE/CDR and four nominal launch phases/four receiver corners; RF uses the current PGA maximum, weak blocked known DATA and causal SAR/reference-load feedback at 20.48 GHz numerical rate. No realized capacitor area/parasitics, asynchronous pulse phases, BER, packet acquisition or protocol qualification. Mitigations are hypothetical, not selected or physically qualified.')


def resolution_campaign(contract, *, design=None):
    design=b.design_for_contract(contract,design)
    rows=[]
    for peak in (.5,.75,1.):
        for offset in range(0,16,2):
            peer,edges,_=environment_for(contract,peak,offset,design=design)
            for phase in (-.35,.35):
                for ppm in (-100.,100.):
                    controls=[resolved_case(peer,edges,phase,ppm,n,exact)
                        for n,exact in ((4,False),(16,False),(4,True))]
                    rows.append(dict(source_peak_v=peak,launch_offset_ui=offset,controls=controls))
            print('resolution',peak,offset,flush=True)
    return dict(cases=rows,scope='Same nominal eight launch phases and four peer corners at each source drive; original 5 ps timestamp noise, loop gains and 64-edge/0.1 UI rule retained. 16-substep and exact-within-bracket controls refine numerical voltage crossing estimates. They do not demonstrate physical detector precision, additional-crossing completeness, asynchronous phase coverage or BER.')


def run():
    from reference_input_probe import probe_source_hashes,verify_probe_sources
    hashes=probe_source_hashes()
    design=load_design();contract=design.contract;rows=[]
    for peak,offset in ((.5,0),(.75,12),(1.,4)):
        peer,edges,ideal=environment_for(contract,peak,offset,design=design)
        for constant in (False,True):
            driven=ideal+float(np.mean(edges-ideal)) if constant else edges
            traced=trace_case(peer,driven)
            # Verify that instrumentation preserves the authoritative receiver.
            reference=causal_receiver_envelope(timing_scenarios=[peer],channel_cases=((2.7e-12,100e-12),),source_edges_s=driven,crossing_mode="linear")['cases'][0]
            for key in ('heldout_errors','heldout_qualified_fraction','final_timing_qualified'):
                assert traced[key]==reference[key],(key,traced[key],reference[key])
            rows.append(dict(source_peak_v=peak,launch_offset_ui=offset,constant_clock=constant,trace=traced))
            print(peak,offset,constant,traced['heldout_qualified_fraction'],traced['heldout_loop_violations'],traced['interpolation_error_abs_peak_ps'],flush=True)
    resolution=resolution_campaign(contract,design=design)
    verify_probe_sources(hashes)
    return dict(design_provenance=design.provenance(),cases=rows,resolution=resolution,scope='Current 0.25 nH package target, current architecture wired allocation, 2.5 Gb/s TX into unchanged independent peer model. Three prescribed launch/drive points through the differential reference input and matched constant-mean-clock controls; one peer phase/ppm corner each. Original 64-edge/0.1 UI readiness rule retained.',
        sources_sha256=hashes)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--internal-loads',action='store_true',help='Run budgeted internal-current wired campaign')
    group.add_argument('--decoupling-payload',action='store_true')
    group.add_argument('--sensitivity-payload',action='store_true')
    args=parser.parse_args()
    if args.internal_loads or args.decoupling_payload or args.sensitivity_payload:
        from reference_input_probe import probe_source_hashes,verify_probe_sources
        hashes=probe_source_hashes()
        design=load_design();contract=design.contract
        report=internal_load_campaign(contract,design=design) if args.internal_loads else mitigation_payload_campaign(contract,sensitivity=args.sensitivity_payload,design=design)
        verify_probe_sources(hashes)
        report['sources_sha256']=hashes
        target=P/('evidence/sensitivity-payload.json' if args.sensitivity_payload else 'evidence/decoupling-payload.json' if args.decoupling_payload else 'evidence/wired-internal-load.json')
    else:
        report=run();target=P/'evidence/wired-lock-probe.json'
    target.write_text(json.dumps(report,indent=2)+'\n')
