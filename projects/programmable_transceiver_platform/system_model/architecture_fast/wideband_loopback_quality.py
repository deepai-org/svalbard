"""Nonlinear internal loopback quality with independent TX observation."""
import hashlib,json,time
from pathlib import Path
from continuous_four_path import run as traffic_run
from functools import partial
from continuous_duplex import PreparedChip
from shared_tx_traffic import scenario
from external_rf_lifecycle import ExternalChip
from rf_modulated_quality import Multicarrier
from rf_quality_screen import quality
from chip_model import decode_iq


run=partial(traffic_run,waveform=Multicarrier(seed=804))

def simulate(mode,impaired):
    chips=[]
    class Observed(PreparedChip):
        def __init__(self,**kwargs):
            options=dict(load_capacitance=0,output_parameters=dict(
                gain_imbalance_db=0.,phase_error_deg=0.,lo_feedthrough=0j,cubic=0.))
            if impaired:
                options=dict(load_capacitance=1e-12,dac_reference_load_capacitance=.2e-12,
                    return_charge_per_transition=50e-15,rf_hz_per_v=1e6,wire_hz_per_v=1e5,
                    rf_noise_rms_hz=20000,wire_noise_rms_hz=20000,noise_seed=839,
                    frontend=dict(gain_error=.03,phase_error=.03,saturation=.8,noise_rms=.001,seed=800))
            super().__init__(**options,**kwargs)
            self.tx_probe.clear();self.probe_times.clear()
            assert self.tx.rx_route=="loopback"
            chips.append(self)
    traffic=run(mode,True,True,chip_factory=Observed)
    c=chips[0];bits=12 if mode==0 else 8
    return [decode_iq(w,bits) for w in c.host_samples],c.tx_probe,c.probe_times,traffic


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Finite continuous-service record with timed lossy stop, not indefinite service bounds.',
                     'RX follows nonlinear TX loopback driven by 50 QPSK subcarriers spanning +/-7.8125 MHz.',
                     'Assumed device/noise parameters; no spectral mask or physical qualification.'])
    output=p/'evidence/fast-wideband-loopback-quality.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            rx0,tx0,t0,_=simulate(mode,False)
            rx,tx,t,traffic=simulate(mode,True)
            assert t==t0 and len(rx)==len(rx0)
            rq=quality(rx0,rx);tq=quality(tx0,tx)
            report['cases'].append(dict(mode=mode,rx_quality=rq,tx_quality=tq,traffic=traffic));save()
            print(mode,rq['corrected_relative_rms'],tq['corrected_relative_rms'],flush=True)
            assert rq['screen_pass'] and tq['screen_pass']
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
