"""Declared integrated candidate: live wired PHY plus wideband RF and converter services."""
import hashlib,json
from chip_model import P,decode_iq
from wired_supply_lifecycle import SupplyWireChip
from rf_phase_lifecycle import trace
from rf_modulated_quality import Multicarrier
from rf_quality_screen import quality
from sustained_lifecycle import run

PROFILE=P/'spec/mathematical-top-profile.json'

class PlatformChip(SupplyWireChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.analog_samples=[];self.sample_times=[]
    def convert_adc(self,value):
        self.analog_samples.append(value);self.sample_times.append(self.tx.time)
        return super().convert_adc(value)


def simulate(profile,mode,sign,ideal):
    period=1/(40e6 if mode==0 else 20e6);chips=[]
    reference=profile['shared_reference'];coupling=profile['signed_coupling'];charge=profile['host_switching_charge_c']
    def factory(**kwargs):
        front={} if ideal else dict(profile['frontend'],gain_error=sign*coupling['iq_gain_error'],phase_error=sign*coupling['iq_phase_error_rad'])
        c=PlatformChip(adc_latency_s=profile['converter_latency_periods']['adc']*period,
            dac_latency_s=profile['converter_latency_periods']['dac']*period,
            resistance=reference['resistance_ohm'],capacitance=reference['capacitance_f'],
            load_capacitance=0 if ideal else reference['adc_load_f'],
            dac_reference_load_capacitance=0 if ideal else reference['dac_load_f'],shared_dac_reference=True,
            coupling_per_v=0 if ideal else sign*coupling['rx_gain_per_v'],
            dac_coupling_per_v=0 if ideal else sign*coupling['dac_gain_per_v'],
            wire_phase_ui_per_v=0 if ideal else sign*coupling['wired_phase_ui_per_v'],
            charge_per_transition=charge['h2d'],return_charge_per_transition=charge['d2h'],frontend=front,**kwargs)
        filt=profile['rf_filter'];c.tx.set_butterworth(filt['order'],filt['cutoff_hz'])
        if not ideal:
            c.configure_rf_input(profile['blockers'],sign*coupling['rf_cubic'],envelope_limit=1.5)
            scale=profile['rf_phase_fixture']['scale']
            c.schedule_lo([(t,a*scale,b*scale,f,g) for t,a,b,f,g in trace(False,profile['rf_phase_fixture']['seed'])])
        chips.append(c);return c
    settings=profile['traffic'];wave=Multicarrier(settings['waveform_seed'])
    row=run(mode,settings['source_ppm'],chip_factory=factory,matched_reference=True,host_ppm=settings['host_ppm'],
        disturbance_sign=sign,service_pauses={settings['pause_frame']:settings['pause_word_periods']},waveform=wave)
    c=chips[0];row['adc_pipeline']=c.adc_accounting();row['dac_pipeline']=c.dac_accounting()
    assert c.live_rx.done and c.detector.idle is False and not c.rx_idle_latched
    assert row['adc_pipeline']['pending']==row['dac_pipeline']['pending']==0
    assert c.dac_reference is c.adc_reference and c.dac_reference.dac_updates==c.tx.consumed
    return row,c.sample_times,c.analog_samples if ideal else [decode_iq(w,c.bits) for w in c.adc_words],wave.metadata


def main():
    profile=json.loads(PROFILE.read_text());rows=[]
    for mode in (0,1):
        for sign in (-1,1):
            print('Running combined mode',mode,'sign',sign,flush=True)
            baseline,t,reference,wave=simulate(profile,mode,sign,True)
            traffic,times,values,actual_wave=simulate(profile,mode,sign,False)
            assert times==t and wave==actual_wave
            q=quality(reference,values);assert q['screen_budget']==profile['quality_budget_relative_rms']
            rows.append(dict(mode=mode,sign=sign,quality=q,traffic=traffic,waveform=wave,
                             reference_adc_sha256=baseline['adc_sha256']))
            print('Completed',mode,sign,'quality',q['corrected_relative_rms'],'screen',q['screen_pass'],flush=True)
    report=dict(status='passed',profile=profile,profile_sha256=hashlib.sha256(PROFILE.read_bytes()).hexdigest(),cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['One declared candidate assembles implemented blocks; open_functions remain explicit architectural gaps.',
        'Signed points and one waveform seed do not prove an uncertainty envelope or physical feasibility.',
        'Quality includes ADC quantization relative to the matched ideal analog/filter path, not total modem EVM.',
        'Passing scenario execution does not override an individual RF quality-screen failure.'])
    (P/'evidence/connected-combined-platform.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
