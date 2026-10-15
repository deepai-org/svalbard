"""Revert one candidate change at a time in the failed 2.4 GHz RF capture."""
import hashlib
import json
import baseline_envelope as b
from selected_rf import minimum_envelope_oversample
from wideband_packet import run_acquisition_case


from design_definition import load_design,Scenario
from feed_failure_probe import loaded_probe


def source_hashes():
    from reference_input_probe import probe_source_hashes
    hashes=probe_source_hashes()
    for name in ('verification/feed_rf_probe.py','verification/feed_failure_probe.py'):
        hashes[name]=hashlib.sha256((b.P/name).read_bytes()).hexdigest()
    return dict(sorted(hashes.items()))


def verify_sources(hashes):
    if source_hashes()!=hashes:
        raise RuntimeError('Sources changed during RF feed computation')


def feed_environment(design,resistance,scale,sensitivity):
    nominal=design.architecture['blocks']['power']['parameters']['reduced_pdn_model']['network']['package_r']
    if resistance!=nominal:
        design=design.hypothetical(reason='RF feed-resistance mitigation probe',
            changes={'blocks.power.parameters.reduced_pdn_model.network.package_r':resistance})
    config=design.configure(engine='rf',direction='rx',reference_hz=2.4e9,sample_divider=64,
        pga_gain_db=max(design.architecture['blocks']['pga_i']['parameters']['gain_db']))
    scenario=Scenario(wanted_dbm=-85.,blocker_dbm=-30.)
    raw=b.configured_environment(config,scenario)
    loads=[dict(owner=o,mean_a=m*scale,event_hz=f,tau_s=.2e-9,harmonics=64)
           for o,m,f in [('timing',.010,150e6),('core',.020,156.25e6)]]
    raw['internal_switching_loads']=loads
    environment,clock=loaded_probe(raw,supply_sign=-1.,sensitivity_ps_per_mv=sensitivity)
    context=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),scenario_stimuli=scenario.stimulus_record(),
        probe_assumptions=dict(internal_switching_loads=loads,sensitivity_ps_per_mv=sensitivity,supply_sign=-1.),
        clock=clock,status='clock_accepted' if environment is not None else clock.get('status','clock_rejected'))
    return environment,context


def main():
    p=b.P;design=load_design();c=design.contract
    hashes=source_hashes()
    rows=[]
    for label,resistance,scale,sensitivity in [('restore_feed',2.,2.,.0125),('restore_activity',1.,1.,.0125),('restore_sensitivity',1.,2.,.025)]:
        e,context=feed_environment(design,resistance,scale,sensitivity)
        if e is None:
            rows.append(dict(context,control=label));continue
        result=run_acquisition_case(e,431,start_sample=137,carrier_offset_hz=-120e3,transmit=True,oversample=minimum_envelope_oversample(e))
        rows.append(dict(context,control=label,local_feed_resistance_ohm=resistance,internal_pulse_scale=scale,sensitivity_ps_per_mv=sensitivity,rf=result))
        print(label,result['payload_correct'],result['raw_bit_errors'],flush=True)
    verify_sources(hashes)
    report=dict(design_provenance=design.provenance(),cases=rows,sources_sha256=hashes,
        scope='One-change reversions from failed candidate, 2.400 GHz, negative sensitivity, seed 431, same acquisition/blocker/causal SAR bench. Interactions remain possible; no factorial decomposition, valid HE PPDU or PER qualification.')
    b.write_evidence(p/'evidence/feed-rf-probe.json',json.loads(json.dumps(report,default=lambda x:x.item())))


def paths(split=False):
    import numpy as np
    from unittest.mock import patch
    import selected_rf as rf
    p=b.P;design=load_design();c=design.contract
    hashes=source_hashes()
    e,context=feed_environment(design,1.,2.,.0125)
    if e is None:
        verify_sources(hashes)
        report=dict(context,cases=[],sources_sha256=hashes,
            scope='Input load/clock rejected before diagnostic phase-path interventions; no receiver evidence.')
        b.write_evidence(p/('evidence/feed-rf-split-paths.json' if split else 'evidence/feed-rf-paths.json'),report)
        return
    oversample=minimum_envelope_oversample(e);rows=[]
    controls=('source_noise_only_lo','source_noise_only_adc') if split else ('constant_reference_target','source_noise_only_clock')
    for control in controls:
        from contextlib import ExitStack
        with ExitStack() as stack:
            if split:
                import copy
                base=rf.DeliveredClock
                class IsolatedClock(base):
                    def phase(self,times):
                        return self.source.phase(times) if control=='source_noise_only_lo' else super().phase(times)
                    def crossing_error(self,ideal,carrier):
                        if control=='source_noise_only_adc':return self.source.crossing_error(ideal,carrier)
                        proxy=copy.copy(self)
                        proxy.phase=base.phase.__get__(proxy,base)
                        return base.crossing_error(proxy,ideal,carrier)
                original=base(e);isolated=IsolatedClock(e);probe=np.arange(1,33)/(2.4e9/64)
                if control=='source_noise_only_lo':
                    np.testing.assert_allclose(isolated.crossing_error(probe,2.4e9),original.crossing_error(probe,2.4e9),rtol=0,atol=1e-20)
                else:np.testing.assert_array_equal(isolated.phase(probe),original.phase(probe))
                stack.enter_context(patch.object(rf,'DeliveredClock',IsolatedClock))
            elif control=='constant_reference_target':
                stack.enter_context(patch.object(rf,'reference_at',side_effect=lambda environment,times:np.ones_like(times,dtype=float)))
            else:
                stack.enter_context(patch.object(rf.DeliveredClock,'phase',lambda self,times:self.source.phase(times)))
                stack.enter_context(patch.object(rf.DeliveredClock,'crossing_error',lambda self,ideal,carrier:self.source.crossing_error(ideal,carrier)))
            result=run_acquisition_case(e,431,start_sample=137,carrier_offset_hz=-120e3,transmit=True,oversample=oversample)
        rows.append(dict(context,control=control,rf=result))
        print(control,result['payload_correct'],result['raw_bit_errors'],flush=True)
    verify_sources(hashes)
    report=dict(design_provenance=design.provenance(),cases=rows,sources_sha256=hashes,scope='Failed 1 ohm/doubled-activity/0.0125 ps/mV 2.4 GHz candidate. Diagnostic interventions: constant reference target retains SAR internal reference dynamics; source-noise-only clock retains assigned source/input noise but removes periodic/load-derived edge phase at LO and sampling consumers. Rail waveforms and causal SAR load recomputation retained. Computed load-edge reports in clock intervention are unused diagnostics. Neither intervention is an implementable mitigation or compliance claim.')
    if split:report['scope']+=' Split controls remove power-coupled phase from only LO or only ADC sampling; assigned source/input phase noise remains. Unmodified consumer checked against original before each run. LO-only control explicitly preserves full phase in the ADC crossing root solve.'
    b.write_evidence(p/('evidence/feed-rf-split-paths.json' if split else 'evidence/feed-rf-paths.json'),json.loads(json.dumps(report,default=lambda x:x.item())))


def spectra():
    p=b.P;design=load_design();c=design.contract;rows=[]
    hashes=source_hashes()
    for label,resistance,scale in [('candidate',1.,2.),('restore_feed',2.,2.),('restore_activity',1.,1.)]:
        e,context=feed_environment(design,resistance,scale,.0125)
        if e is None:
            rows.append(dict(context,case=label));continue
        r=context['clock']
        tones=[]
        for t in e['host_spectrum']['tones']:
            f=t['frequency_hz'];alias=abs((f+18.75e6)%37.5e6-18.75e6)
            reference=next((a for frequency,a,phase in e['reference_fraction_tones'] if frequency==f),0.)
            tones.append(dict(frequency_hz=f,adc_folded_offset_hz=alias,rail_peak_v=t['clock_rail_voltage_peak_v'],reference_fraction_peak=reference,
                blocker_difference_offset_hz=abs(12e6-alias)))
        rows.append(dict(context,case=label,local_rail_dc_v=e['ledger']['local_payload_clock_core_rail_v'],
            tones=sorted(tones,key=lambda t:t['rail_peak_v'],reverse=True),clock=r['resolved_crossings']))
    verify_sources(hashes)
    report=dict(design_provenance=design.provenance(),cases=rows,sources_sha256=hashes,scope='Pre-SAR-feedback linear spectra, 2.400 GHz and 37.5 MS/s. Folded frequency locates possible sampled/reference effects, not their output amplitude. Individual tone magnitudes are not summed as independent powers. A blocker difference column is a candidate mixing location, not proof of conversion through the complete chain.')
    b.write_evidence(p/'evidence/feed-rf-spectra.json',json.loads(json.dumps(report,default=lambda x:x.item())))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--spectra',action='store_true');parser.add_argument('--paths',action='store_true');parser.add_argument('--split-paths',action='store_true')
    args=parser.parse_args()
    paths(True) if args.split_paths else paths() if args.paths else spectra() if args.spectra else main()

