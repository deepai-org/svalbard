"""Loaded fractional RF chain against an independently ideal tuned reference."""
import copy,hashlib,json
from chip_model import P
from programmable_chip import ProgrammableChip
from fractional_rf_chip import FractionalRFChip
from wideband_clock_quality import simulate
from rf_quality_screen import quality

PROFILE_PATH=P/'spec/fractional-top-profile.json'
PROFILE=json.loads(PROFILE_PATH.read_text())

def candidate(base,target):
    class TunedCandidate(base):
        def __init__(self,**kwargs):
            # This declared preparation interval exceeds the original fast-run
            # harness's20us host watchdog. Use the explicit candidate timeout.
            kwargs['watchdog_s']=PROFILE['watchdog_s']
            super().__init__(**kwargs)
            self.configure_rf_carrier(target)
        def configure(self,mode,time):
            super().configure(mode,time)
            self.advance(time+PROFILE['settle_s'])
            assert self.state=='active'
            self.detect_start(self.time,self.epoch)
            self.advance(time+PROFILE['detection_end_s'])
            assert self.detect_result(self.epoch)['decision']=='present'
    return TunedCandidate

def main():
    rows=[]
    for mode in (0,1):
        for target in PROFILE['carrier_targets_hz']:
            experiment=copy.deepcopy(PROFILE['experiment'])
            experiment['source_offset_hz']+=target-2.4e9
            common=dict(experiment=experiment,service_pauses={PROFILE['traffic']['pause_frame']:PROFILE['traffic']['pause_words']})
            baseline,times,reference=simulate(mode,False,chip_class=candidate(ProgrammableChip,target),
                chip_options=dict(load_capacitance=0,dac_reference_load_capacitance=0,probe_load_scale=0),**common)
            frame=PROFILE['blocker_frequency_reference']
            if frame not in ('configured_carrier','fixed_2p4GHz_frame'):raise ValueError('Unknown blocker frequency reference')
            shift=target-2.4e9 if frame=='configured_carrier' else 0.
            blockers=[(a,f+shift) for a,f in PROFILE['blockers']]
            traffic,actual,measured=simulate(mode,True,chip_class=candidate(FractionalRFChip,target),
                blockers=blockers,cubic=PROFILE['cubic'],
                chip_options=dict(rf_pulse_bandwidth_hz=PROFILE['rf_pulse_bandwidth_hz'],
                    **PROFILE['shared_reference'],**PROFILE['coupling']),**common)
            assert times==actual
            assert actual[-1]<(experiment['source_count']-1)/experiment['source_rate_hz']
            assert traffic['receiver_detection']['charge_c']>0
            assert traffic['reference_metrics']['dac_reference']['charge_c']>0
            q=quality(reference,measured)
            rows.append(dict(mode=mode,target_hz=target,blockers_in_model_frame=blockers,
                blockers_relative_to_carrier=[(a,f-(target-2.4e9)) for a,f in blockers],quality=q,traffic=traffic,reference_traffic=baseline))
            print(mode,target,q['corrected_relative_rms'],q['screen_pass'],flush=True)
    passed=all(r['quality']['screen_pass'] for r in rows)
    report=dict(status='passed' if passed else 'failed',cases=rows,
        profile=PROFILE,profile_sha256=hashlib.sha256(PROFILE_PATH.read_bytes()).hexdigest(),
        complete_architecture=False,physical_qualification=False,
        limitations=['Ideal tuned sampled-loop reference excludes deterministic fractional modulation, so it remains in measured error.',
        'Two carriers, one waveform/noise realization and positive coupling only; not complete channel/uncertainty coverage.',
        '100us declared host watchdog permits40us acquisition preparation; watchdog limits are not otherwise disabled.',
        '10% held-out waveform error is provisional, not a modem EVM or silicon specification.'])
    (P/'evidence/connected-fractional-wideband-quality.json').write_text(json.dumps(report,indent=2)+'\n')
    assert passed,'Fractional wideband candidate exceeds provisional quality budget'
if __name__=='__main__':main()
