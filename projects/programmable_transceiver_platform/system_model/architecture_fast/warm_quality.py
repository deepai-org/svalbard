"""Independent RF quality during calibrated continuous four-path traffic."""
import hashlib,json,time
from pathlib import Path
from continuous_four_path import run
from warm_chip import WarmTransceiverChip
from managed_resources import command
from shared_tx_traffic import scenario
from external_rf_lifecycle import ExternalChip
from rf_modulated_quality import Multicarrier
from rf_quality_screen import quality
from chip_model import decode_iq


class PreparedChip(WarmTransceiverChip):
    def __init__(self,initial_mode=0,**kwargs):
        super().__init__(rf_free_offset=.96*.995-1,coarse_noise_bound_hz=80000.,**kwargs)
        assert command(self,"rf_coarse_start",2437000000)["accepted"]
        self.advance(self.time+35e-6)
        first=command(self,'tx_cal_start');assert first['accepted']
        self.advance(self.time+25e-6)
        assert command(self,'tx_cal_commit',first['value'])['accepted']
        assert command(self,'configure_mode',initial_mode)['accepted']
        assert command(self,'stop')['accepted']
        assert command(self,'ack_abort')['accepted'] and command(self,'ack_drain')['accepted']
        assert command(self,'detect_rearm')['accepted']
        assert command(self,"rf_coarse_start",2500000000)["accepted"]
        self.advance(self.time+35e-6)
        assert self.coarse.qualified and self.rf_pll.locked
        for target in (0,1):
            assert command(self,'cal_start',48|(target<<16))['accepted']
            self.advance(self.time+40e-6)
        start=command(self,'tx_cal_start');assert start['accepted']
        self.advance(self.time+25e-6)
        assert command(self,'tx_cal_commit',start['value'])['accepted']
        self.applied_inputs=[]
        original=self.tx.apply_sample
        def observed(value,time):
            original(value,time)
            self.applied_inputs.append(value)
        self.tx.apply_sample=observed

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
            super().__init__(initial_mode=mode,**options,**kwargs)
            self.tx_probe.clear();self.probe_times.clear()
            self.external_source(Multicarrier(seed=828)(4096,40e6),self.time,25e-9,offset_hz=100250e3)
            chips.append(self)
    traffic=run(mode,True,True,chip_factory=Observed)
    traffic['coarse_bank_code']=chips[0].rf_pll.bank_code
    traffic['coarse_measurements']=chips[0].coarse.history
    c=chips[0];bits=12 if mode==0 else 8
    return [decode_iq(w,bits) for w in c.host_samples],c.tx_probe,c.probe_times,traffic


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Finite continuous-service record with timed lossy stop, not indefinite service bounds.',
                     'RX is wideband multicarrier; TX uses deterministic amplitude-varying transport stimulus.',
                     'Assumed coarse bank/device/noise parameters; no spectral mask or physical qualification.',
                     '2.5 GHz and -0.5% free-frequency case; warm 2.437-to-2.5 GHz transition; other tuning histories remain open.'])
    output=p/'evidence/fast-warm-quality.json'
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
