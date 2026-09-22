"""Independent wideband receive quality with autonomous clocks and four-path traffic."""
import json
from chip_model import P,decode_iq
from sampled_clock_lifecycle import SampledClockChip
from rf_modulated_quality import Multicarrier
from rf_selectivity_screen import butterworth_order
from rf_quality_screen import quality
from sustained_lifecycle import run

class SettledChip(SampledClockChip):
    def configure(self,mode,time):
        super().configure(mode,time)
        self.advance(time+8e-6)
        assert self.state=='active'


EXPERIMENT_DEFAULTS={'source_seed': 839, 'source_count': 1200, 'source_rate_hz': 40000000.0, 'source_offset_hz': 250000.0, 'tx_seed': 840, 'frames': 32, 'filter_pass_hz': 8000000.0, 'filter_stop_hz': 20000000.0, 'filter_pass_db': 1, 'filter_stop_db': 30, 'rf_noise_rms_hz': 20000, 'wire_noise_rms_hz': 10000, 'rf_hz_per_v': 1000000.0, 'wire_hz_per_v': 1000000.0, 'adc_latency_s': 3e-08, 'dac_latency_s': 2e-08, 'charge_per_transition': 1e-13, 'return_charge_per_transition': 5e-14, 'gain_error': 0.03, 'phase_error': 0.03, 'saturation': 0.8, 'noise_rms': 0.001, 'frontend_seed': 839, 'envelope_limit': 1.5}

def simulate(mode,impaired,sign=1,blockers=(),cubic=0.,chip_class=SettledChip,chip_options=None,service_pauses=None,experiment=None):
    settings=dict(EXPERIMENT_DEFAULTS)
    if experiment is not None:
        if set(experiment)!=set(settings):raise ValueError('Experiment must specify exactly the declared settings')
        settings.update(experiment)
    chips=[];wave=Multicarrier(seed=settings['source_seed'])
    source=wave(settings['source_count'],settings['source_rate_hz'])
    order,cutoff=butterworth_order(*(settings[k] for k in ('filter_pass_hz','filter_stop_hz','filter_pass_db','filter_stop_db')))
    def factory(**kwargs):
        c=chip_class(**(chip_options or {}),rf_noise_rms_hz=settings['rf_noise_rms_hz'] if impaired else 0,
            wire_noise_rms_hz=settings['wire_noise_rms_hz'] if impaired else 0,
            rf_hz_per_v=sign*settings['rf_hz_per_v'] if impaired else 0,wire_hz_per_v=sign*settings['wire_hz_per_v'] if impaired else 0,
            adc_latency_s=settings['adc_latency_s'],dac_latency_s=settings['dac_latency_s'],
            charge_per_transition=settings['charge_per_transition'],return_charge_per_transition=settings['return_charge_per_transition'],
            frontend=dict(gain_error=sign*settings['gain_error'],phase_error=sign*settings['phase_error'],saturation=settings['saturation'],noise_rms=settings['noise_rms'],seed=settings['frontend_seed']) if impaired else {},
            **kwargs)
        c.tx.set_butterworth(order,cutoff)
        c.external_source(source,0,1/settings['source_rate_hz'],offset_hz=settings['source_offset_hz'])
        if impaired:c.configure_rf_input(blockers,cubic,envelope_limit=settings['envelope_limit'])
        chips.append(c);return c
    traffic=run(mode,0,frames=settings['frames'],chip_factory=factory,matched_reference=True,host_ppm=0,
                waveform=Multicarrier(seed=settings['tx_seed']),service_pauses=service_pauses)
    c=chips[0]
    traffic['experiment']=settings
    traffic['external_waveform']=wave.metadata
    traffic['oscillator_supply']=c.reference_metrics()['oscillator_supply']
    if hasattr(c,'probe_supply_charge'):
        traffic['receiver_detection']=dict(result=c.detect_result(c.epoch),
            charge_c=c.probe_supply_charge,minimum_gain=c.probe_minimum_gain,
            maximum_sensor_error_v=c.probe_maximum_sensor_error,
            drive_released=c.probe.drive is None)
    assert c.external_updates>400
    assert c.oscillator_supply_events>0 if impaired else c.oscillator_supply_events==0
    return traffic,c.sample_times,[decode_iq(w,c.bits) for w in c.adc_words] if impaired else c.analog_samples


def main():
    rows=[]
    for mode in (0,1):
        baseline,times,reference=simulate(mode,False)
        traffic,actual,measured=simulate(mode,True)
        assert times==actual
        q=quality(reference,measured)
        rows.append(dict(mode=mode,quality=q,traffic=traffic,reference_traffic=baseline))
        print('Mode',mode,'relative RMS',q['corrected_relative_rms'],'passes',q['screen_pass'],flush=True)
    report=dict(status='passed',cases=rows,quality_pass=all(r['quality']['screen_pass'] for r in rows),
        complete_architecture=False,physical_qualification=False,
        limitations=['32-frame finite traffic, one external waveform seed and one positive coupling point.',
        'Ideal comparison retains the same analog filter and carrier offset; quality is incremental held-out error, not modem EVM.',
        'RF20kHz/wired10kHz RMS frequency noise and1MHz/V supply sensitivity are assumed, not PDK-calibrated.',
        'Clock noise is a finite spectral realization; charge-pump pulse loop, fractional-N spurs, blockers and full uncertainty sweep remain open.'])
    (P/'evidence/connected-wideband-clock-quality.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
