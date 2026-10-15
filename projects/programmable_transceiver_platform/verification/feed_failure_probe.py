"""Matched controls for the candidate's failing wired launch; no readiness changes."""
import hashlib
from copy import deepcopy
import json
import numpy as np
import baseline_envelope as b
from wired_lock_probe import peer_for_environment,resolved_case
from wired_envelope import physical_receiver
from design_definition import load_design, Scenario


def trace_readiness(peer,edges,noise_scale=1.):
    bits=np.random.default_rng(9021).integers(0,2,2600).tolist()
    rx=physical_receiver(bits,2.5e9,.35,-100.,100e-12,2.7e-12,peer,
        source_edges_s=edges,crossing_mode='root',voltage_substeps=4)
    observations=[];detector=[];generator=rx.rng
    class RecordedNoise:
        def normal(self,*args,**kwargs):
            noise=float(generator.normal(*args,**kwargs))*noise_scale
            geometric=(rx.detector_time_ui-rx.latest_crossing_ui)%1-.5
            total=(geometric+noise+.5)%1-.5
            detector.append(dict(bit=rx.bit_index,geometric_error_ui=float(geometric),
                detector_noise_ui=noise,total_error_ui=float(total)))
            return noise
    rx.rng=RecordedNoise()
    def observe(bit,ready):
        observations.append(dict(bit=rx.bit_index,ready=bool(ready),
            detected_edges=rx.detected_edges,recent_max_error_ui=max(rx.edge_errors,default=0.),
            latest_error_ui=rx.edge_errors[-1] if rx.edge_errors else None))
    rx.bit_observer=observe
    for word in range(240):rx._forecast_word();rx.consume(word)
    violations=[];last=0
    for row in observations:
        if row['detected_edges']!=last and row['latest_error_ui'] is not None and row['latest_error_ui']>=.1:
            violations.append(row)
        last=row['detected_edges']
    held=observations[1200:2400]
    return dict(deepcopy(peer.get('probe_context',{})),readiness=sum(x['ready'] for x in held)/1200,
        unready_bits=[x['bit'] for x in held if not x['ready']],
        threshold_exceedances=violations,noise_scale=noise_scale,
        detector_at_bit_2055=[x for x in detector if x['bit']==2055],
        heldout_peak_geometric_error_ui=max(abs(x['geometric_error_ui']) for x in detector if 1200<=x['bit']<2400),
        scope='Direct sequential receiver execution, compared with forecast/commit readiness. Latest error records may omit earlier crossings within a multi-crossing sample.')


def loaded_probe(raw, **options):
    """Record out-of-budget adversarial stimuli without relaxing the inventory."""
    try:
        return b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False,**options)
    except ValueError as error:
        if str(error)!='Internal pulse mean exceeds owner DC budget':raise
        return None,dict(status='load_rejected',reason=str(error))


def main(*,design=None):
    design=load_design() if design is None else design
    p=b.P;c=design.contract
    from reference_input_probe import probe_source_hashes
    hashes=probe_source_hashes()
    own_source='verification/feed_failure_probe.py'
    hashes[own_source]=hashlib.sha256((p/own_source).read_bytes()).hexdigest()
    rows=[]
    for resistance,scale in ((2.,1.),(1.,1.),(2.,2.),(1.,2.)):
        selected=design
        if resistance!=design.architecture['blocks']['power']['parameters']['reduced_pdn_model']['network']['package_r']:
            selected=design.hypothetical(reason='Matched feed-resistance mitigation experiment',
                changes={'blocks.power.parameters.reduced_pdn_model.network.package_r':resistance})
        config=selected.configure(engine='wire',direction='tx',reference_hz=2.5e9,host_divider=8)
        scenario=Scenario()
        raw=b.configured_environment(config,scenario)
        raw['internal_switching_loads']=[dict(owner=o,mean_a=m*scale,event_hz=156.25e6,tau_s=.2e-9,harmonics=64) for o,m in [('timing',.01),('core',.02)]]
        context=dict(design_provenance=selected.provenance(),resolved_configuration=config.record(),
            scenario_overrides=scenario.record(),probe_assumptions=dict(
                internal_switching_loads=raw['internal_switching_loads'],
                reason='Assigned internal-current pulse activity'))
        raw['probe_context']=context
        e,clock=loaded_probe(raw,supply_sign=1.)
        clock=dict(clock,**context)
        if e is None:
            rows.append(dict(local_feed_resistance_ohm=resistance,internal_pulse_scale=scale,
                             status='load_rejected' if clock.get('status')=='load_rejected' else 'clock_rejected',clock=clock))
            continue
        peer,edges,ideal=peer_for_environment(e,12)
        for control in ('joined','constant_clock','constant_driver_rail'):
            drive=ideal+float(np.mean(edges-ideal)) if control=='constant_clock' else edges
            channel=dict(peer,rail_tones=[]) if control=='constant_driver_rail' else peer
            result=resolved_case(channel,drive,.35,-100.,4,True)
            trace=trace_readiness(channel,drive) if control=='joined' else None
            if trace is not None:assert trace['readiness']==result['readiness']
            no_detector_noise=trace_readiness(channel,drive,0.) if control=='joined' else None
            rows.append(dict(local_feed_resistance_ohm=resistance,internal_pulse_scale=scale,control=control,result=result,trace=trace,no_detector_noise=no_detector_noise))
            print(resistance,scale,control,result['readiness'],flush=True)
    sensitivity_rows=[]
    # raw remains the matched 1 ohm / doubled-activity environment.
    for sensitivity in (.025,.0125,0.):
        sensitivity_context=dict(context,probe_assumptions=dict(context['probe_assumptions'],
            sensitivity_ps_per_mv=sensitivity,reason='Assigned current pulses and supply-delay sensitivity'))
        raw=dict(raw,probe_context=sensitivity_context)
        e,clock=loaded_probe(raw,supply_sign=1.,sensitivity_ps_per_mv=sensitivity)
        clock=dict(clock,**sensitivity_context)
        if e is None:
            sensitivity_rows.append(dict(sensitivity_ps_per_mv=sensitivity,
                                         status='load_rejected' if clock.get('status')=='load_rejected' else 'clock_rejected',clock=clock))
            continue
        peer,edges,_=peer_for_environment(e,12)
        result=resolved_case(peer,edges,.35,-100.,4,True)
        trace=trace_readiness(peer,edges)
        assert trace['readiness']==result['readiness']
        sensitivity_rows.append(dict(sensitivity_ps_per_mv=sensitivity,result=result,trace=trace,
            clock_status=clock["status"]))
        print('sensitivity',sensitivity,result['readiness'],flush=True)
    assert hashes=={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in hashes}
    b.write_evidence(p/'evidence/feed-failure-probe.json',dict(design_provenance=design.provenance(),cases=rows,sensitivity_controls=sensitivity_rows,sources_sha256=hashes,
        scope='Matched 2x2 feed/activity comparison at prescribed launch 12 UI, +0.35 UI peer phase, -100 ppm and positive supply-delay sign. Constant-clock and constant-driver-rail are diagnostic interventions, not implementable mitigations. Root-localized crossings, unchanged readiness, 1200 held-out bits. No full lifecycle, long BER or physical detector qualification.'))


if __name__=='__main__':main()
