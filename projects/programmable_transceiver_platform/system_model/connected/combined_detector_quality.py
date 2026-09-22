"""Public detector plus independent RF, converter loads and four-path traffic."""
import hashlib,json
from chip_model import P
from programmable_chip import ProgrammableChip
from wideband_clock_quality import simulate
from rf_quality_screen import quality

PROFILE_PATH=P/'spec/autonomous-top-profile.json'
PROFILE=json.loads(PROFILE_PATH.read_text())

class CombinedChip(ProgrammableChip):
    def configure(self,mode,time):
        super().configure(mode,time)
        self.advance(time+PROFILE['settle_s'])
        assert self.state=='active'
        self.detect_start(self.time,self.epoch)
        self.advance(time+PROFILE['detection_end_s'])
        assert self.detect_result(self.epoch)['decision']=='present'
        assert self.probe.drive is None

def main():
    rows=[]
    for mode in (0,1):
        settings=PROFILE['traffic']
        common=dict(experiment=PROFILE['experiment'],chip_class=CombinedChip,service_pauses={settings['pause_frame']:settings['pause_words']})
        baseline,times,reference=simulate(mode,False,chip_options=dict(
            load_capacitance=0,dac_reference_load_capacitance=0,probe_load_scale=0),**common)
        for sign in (-1,1):
            traffic,actual,measured=simulate(mode,True,sign=sign,
                blockers=PROFILE['blockers'],cubic=sign*PROFILE['cubic'],chip_options=dict(
                    **PROFILE['shared_reference'],
                    **{k:sign*v for k,v in PROFILE['coupling'].items()}),**common)
            assert times==actual
            ref=traffic['reference_metrics'];detect=traffic['receiver_detection']
            assert ref['conversions']>0 and ref['minimum_span_v']<1
            assert ref['dac_reference']['updates']>0 and ref['dac_reference']['charge_c']>0
            assert baseline['reference_metrics']['total_load_charge_c']==0
            assert detect['charge_c']>0 and detect['maximum_sensor_error_v']>0
            assert detect['drive_released'] and detect['result']['decision']=='present'
            assert len(traffic['service_pauses'])==1
            assert traffic['service_pauses'][0]['word_periods']==settings['pause_words']
            q=quality(reference,measured)
            assert q['screen_budget']==PROFILE['quality_budget_relative_rms']
            rows.append(dict(mode=mode,sign=sign,quality=q,traffic=traffic,reference_traffic=baseline))
            print('Mode',mode,'sign',sign,'combined relative RMS',q['corrected_relative_rms'],flush=True)
    passed=all(r['quality']['screen_pass'] for r in rows)
    report=dict(status='passed' if passed else 'failed',quality_pass=passed,
        profile=PROFILE,profile_sha256=hashlib.sha256(PROFILE_PATH.read_bytes()).hexdigest(),
        cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Detection precedes traffic because detection and wired TX share pads.',
        'Finite 32-frame run, one 16-word host pause and two signed assumed coupling points.',
        'Incremental held-out waveform error is not protocol EVM or silicon qualification.',
        'Converter references use aggregate charge impulses; clock noise and supply sensitivities are assumed.'])
    (P/'evidence/connected-combined-detector-quality.json').write_text(json.dumps(report,indent=2)+'\n')
    assert passed, 'Combined quality budget exceeded; inspect written evidence'

if __name__=='__main__':main()
