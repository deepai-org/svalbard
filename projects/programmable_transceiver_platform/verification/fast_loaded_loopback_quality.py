"""Nonlinear internal loopback quality with independent TX observation."""
import argparse,hashlib,json,time,sys
from pathlib import Path
FAST=Path(__file__).resolve().parents[1]/'system_model/architecture_fast'
sys.path.insert(0,str(FAST))
from continuous_four_path import run
from fast_loaded_traffic import PreparedLoadedChip as PreparedChip,PreparedPoweredChip
from continuous_duplex import run as run_rf
from shared_tx_traffic import scenario
from rf_quality_screen import quality
from chip_model import decode_iq
from managed_resources import command


def simulate(mode,impaired,power_gated=False):
    chips=[]
    class Observed(PreparedPoweredChip if power_gated else PreparedChip):
        def __init__(self,**kwargs):
            options=dict(load_capacitance=0,output_parameters=dict(
                gain_imbalance_db=0.,phase_error_deg=0.,lo_feedthrough=0j,cubic=0.))
            if impaired:
                options=dict(load_capacitance=1e-12,dac_reference_load_capacitance=.2e-12,
                    return_charge_per_transition=50e-15,rf_hz_per_v=1e6,wire_hz_per_v=1e5,
                    rf_noise_rms_hz=20000,wire_noise_rms_hz=20000,noise_seed=839,
                    frontend=dict(gain_error=.03,phase_error=.03,saturation=.8,noise_rms=.001,seed=800))
            self.adc_analog=[]
            super().__init__(**options,**kwargs)
            assert command(self,'configure_rx_gain',2)['accepted']
            self.adc_analog.clear()
            self.tx_probe.clear();self.probe_times.clear()
            assert self.tx.rx_route=="loopback"
            chips.append(self)
        def quantize_adc(self,value):
            self.adc_analog.append(value)
            return super().quantize_adc(value)
    traffic=(run_rf if power_gated else run)(mode,True,True,chip_factory=Observed)
    if power_gated:
        assert chips[0].off_clock_checks>128
        assert not chips[0].wired_output and not chips[0].host_wire
        traffic['off_clock_checks']=chips[0].off_clock_checks
    c=chips[0];bits=12 if mode==0 else 8
    return [decode_iq(w,bits) for w in c.host_samples],c.tx_probe,c.probe_times,traffic,c.adc_analog[:len(c.host_samples)]


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    parser=argparse.ArgumentParser();parser.add_argument('--power-gated',action='store_true')
    args=parser.parse_args()
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(FAST.glob('*.py'))+[Path(__file__),p/'verification/fast_loaded_output.py',p/'verification/fast_loaded_traffic.py',p/'verification/fast_exclusive_engine.py']+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',power_gated=args.power_gated,source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Finite continuous-service record with timed lossy stop, not indefinite service bounds.',
                     'RX follows the nonlinear TX loopback; deterministic amplitude-varying stimulus, not wideband modulation.',
                     'Assumed device/noise parameters; no spectral mask or physical qualification.',
                     'Both baseline and impaired candidate use finite pad/monitor network, relative-gain calibration and the same 2x RX gain.',
                     'Independent TX observation is actual loaded pad voltage; no source reconstruction or normalization.',
                     'Pre-quantizer diagnostics include frontend/reference/recovery; they isolate quantization, not individual analog impairments.'])
    output=p/('evidence/fast-powered-loopback-quality.json' if args.power_gated else 'evidence/fast-loaded-loopback-quality.json')
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            rx0,tx0,t0,_,analog0=simulate(mode,False,args.power_gated)
            rx,tx,t,traffic,analog=simulate(mode,True,args.power_gated)
            assert t==t0 and len(rx)==len(rx0)
            rq=quality(rx0,rx);tq=quality(tx0,tx)
            diagnostics=dict(analog_rx_quality=quality(analog0,analog),
                baseline_quantization=quality(analog0,rx0),impaired_quantization=quality(analog,rx),
                baseline_adc_rms=(sum(abs(z)**2 for z in analog0)/len(analog0))**.5,
                impaired_adc_rms=(sum(abs(z)**2 for z in analog)/len(analog))**.5)
            report['cases'].append(dict(mode=mode,rx_quality=rq,tx_quality=tq,traffic=traffic,diagnostics=diagnostics));save()
            print(mode,rq['corrected_relative_rms'],tq['corrected_relative_rms'],flush=True)
            assert rq['screen_pass'] and tq['screen_pass']
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:
        report['elapsed_s']=time.monotonic()-start
        save()

if __name__=='__main__':main()
