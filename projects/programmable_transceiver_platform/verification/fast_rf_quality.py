"""Independent RF quality during calibrated continuous four-path traffic."""
import argparse,hashlib,json,time,sys
from pathlib import Path
FAST=Path(__file__).resolve().parents[1]/'system_model/architecture_fast'
sys.path.insert(0,str(FAST))
from continuous_four_path import run
from continuous_duplex import PreparedChip
from shared_tx_traffic import scenario
from rf_modulated_quality import Multicarrier
from rf_quality_screen import quality
from chip_model import decode_iq


PROFILE=FAST.parents[1]/'spec/mathematical-top-profile.json'

def simulate(mode,impaired,sign=1,variant="signed"):
    use_profile=variant!='blockers'
    profile=json.loads(PROFILE.read_text())
    chips=[]
    class Observed(PreparedChip):
        def __init__(self,**kwargs):
            period=1/(40e6 if mode==0 else 20e6)
            if use_profile:kwargs['dac_latency_s']=profile['converter_latency_periods']['dac']*period
            if use_profile:kwargs['adc_latency_s']=profile['converter_latency_periods']['adc']*period
            options=dict(load_capacitance=0,output_parameters=dict(
                gain_imbalance_db=0.,phase_error_deg=0.,lo_feedthrough=0j,cubic=0.))
            if impaired:
                options=dict(load_capacitance=1e-12,dac_reference_load_capacitance=profile['shared_reference']['dac_load_f'] if use_profile else .2e-12,
                    return_charge_per_transition=50e-15,rf_hz_per_v=1e6,wire_hz_per_v=1e5,
                    rf_noise_rms_hz=20000,wire_noise_rms_hz=20000,noise_seed=839,
                    frontend=dict(gain_error=.03,phase_error=.03,saturation=.8,noise_rms=.001,seed=800))
            if impaired and variant=='signed':
                coupling=profile['signed_coupling']
                options.update(coupling_per_v=sign*coupling['rx_gain_per_v'],
                    dac_coupling_per_v=sign*coupling['dac_gain_per_v'],
                    wire_phase_ui_per_v=sign*coupling['wired_phase_ui_per_v'],
                    rf_hz_per_v=sign*1e6,wire_hz_per_v=sign*1e5)
                options['frontend'].update(gain_error=sign*coupling['iq_gain_error'],
                    phase_error=sign*coupling['iq_phase_error_rad'])
            super().__init__(**options,**kwargs)
            self.tx_probe.clear();self.probe_times.clear()
            self.external_source(Multicarrier(seed=828)(4096,40e6),self.time,25e-9,offset_hz=250e3)
            if impaired:
                self.tx.rf_cubic=sign*profile['signed_coupling']['rf_cubic']
                self.tx.rf_blockers=((.1,20e6),(.1,30e6))
            chips.append(self)
    traffic=run(mode,True,True,chip_factory=Observed)
    c=chips[0];bits=12 if mode==0 else 8
    if variant=='signed':
        traffic['supply_reference']=dict(reference=c.reference_metrics(),
            rail_minimum_v=c.supply.minimum,rx_gain_min=c.gain_min,rx_gain_max=c.gain_max,
            dac_gain_min=c.dac_gain_min,dac_gain_max=c.dac_gain_max,
            wire_sensitivity_ui_per_v=c.wire_sensitivity)
    return [decode_iq(w,bits) for w in c.host_samples],c.tx_probe,c.probe_times,traffic


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--variant',choices=('blockers','load','signed'),required=True)
    variant=parser.parse_args().variant
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(FAST.glob('*.py'))+[Path(__file__),PROFILE]+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Finite continuous-service record with timed lossy stop, not indefinite service bounds.',
                     'RX is wideband multicarrier; TX uses deterministic amplitude-varying transport stimulus.',
                     'Assumed device/noise parameters; no spectral mask or physical qualification.',
                     'Two 0.1-amplitude blockers at 20/30 MHz in fixed 2.4 GHz envelope frame; signed cubic coefficient +/-0.05.',
                     'Selected nominal carrier only; arbitrary blocker/carrier placement remains unqualified.',
                     'Profile DAC reference load 2 pF and ADC/DAC latency 2/1.5 sample periods; signed converter-gain/wired-phase coupling from profile; oscillator supply sensitivities also signed. Other assumptions retain the fast blocker fixture.'])
    names={'blockers':'fast-blocker-quality.json','load':'fast-profile-load-quality.json','signed':'fast-signed-coupling-quality.json'}
    output=p/'evidence'/names[variant]
    previous=json.loads(output.read_text())['cases'] if output.exists() else None
    report['variant']=variant
    report['limitations']=['Historical simultaneous-traffic stress fixture, not an exclusive-mode requirement.','Selected nominal carrier and assumed noise/loading; no physical qualification.','blockers: fast timing/load; load: profile timing/load; signed: profile timing/load and both coupling signs.']
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            rx0,tx0,t0,_=simulate(mode,False,variant=variant)
            for sign in ((-1,1) if variant=='signed' else (1,)):
                rx,tx,t,traffic=simulate(mode,True,sign,variant)
                assert t==t0 and len(rx)==len(rx0)
                rq=quality(rx0,rx);tq=quality(tx0,tx)
                row=dict(mode=mode,rx_quality=rq,tx_quality=tq,traffic=traffic)
                if variant=='signed':row['sign']=sign
                report['cases'].append(row);save()
                print(mode,sign,rq['corrected_relative_rms'],tq['corrected_relative_rms'],flush=True)
                assert rq['screen_pass'] and tq['screen_pass']
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        if previous is not None:
            assert json.loads(json.dumps(report['cases']))==previous,'Refactor changed case results'
            report['previous_cases_equal']=True
            report['previous_cases_sha256']=hashlib.sha256(json.dumps(previous,sort_keys=True).encode()).hexdigest()
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
