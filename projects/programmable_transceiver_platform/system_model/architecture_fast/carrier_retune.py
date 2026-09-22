"""Warm averaged-ratio retuning followed by calibrated four-path traffic."""
import hashlib
import json
import time
from pathlib import Path
import service_traffic as scenario
from rf_quality_screen import quality
Original=scenario.ServiceChip

class RetunedChip(Original):
    initial_hz=2412000000
    target_hz=2437000000
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.configure_rf_carrier(self.initial_hz)
        self.retune_evidence=None
    def external_source(self,values,start,period,offset_hz=0.):
        # The scenario calls this after quiet I/Q calibration, before arming.
        p=self.rf_pll
        phase=p.output_phase_cycles;integral=p.integral
        assert p.locked,'Initial carrier must acquire before warm retuning'
        self.configure_rf_carrier(self.target_hz)
        phase_error=abs(p.output_phase_cycles-phase)
        assert phase_error<1e-9 and p.integral==integral
        assert not p.locked
        self.retune_evidence=dict(from_hz=self.initial_hz,to_hz=self.target_hz,
            time_s=self.time,phase_discontinuity_cycles=phase_error,
            filter_state_preserved=True,lock_invalidated=True)
        return super().external_source(values,start,period,
            offset_hz=offset_hz+self.target_hz-self.rf_carrier)


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    start=time.monotonic();p=scenario.architecture.P
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Average fractional feedback ratio; no physical divider sequence or fractional spurs.',
                     'Two warm tuning points, not full tuning-range or process qualification.',
                     'RF source follows requested carrier; residual 250 kHz offset stays unchanged.',
                     'TX calibration and carrier-dependent calibration accuracy remain open.'])
    output=p/'evidence/fast-carrier-retune.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    chips=[]
    class RecordedChip(RetunedChip):
        def __init__(self,**kwargs):
            super().__init__(**kwargs);chips.append(self)
    scenario.ServiceChip=RecordedChip
    try:
        for mode in (0,1):
            RecordedChip.initial_hz,RecordedChip.target_hz=((2412000000,2437000000) if mode==0 else (2437000000,2412000000))
            rx0,tx0,t0,_=scenario.simulate(mode,False)
            rx,tx,t,result=scenario.simulate(mode,True)
            assert t==t0
            rq=quality(rx0,rx);tq=quality(tx0,tx)
            result.update(mode=mode,retune=chips[-1].retune_evidence,rx_quality=rq,tx_quality=tq)
            report['cases'].append(result);save()
            print(mode,rq['corrected_relative_rms'],tq['corrected_relative_rms'],flush=True)
            assert rq['screen_pass'] and tq['screen_pass']
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:scenario.ServiceChip=Original;save()

if __name__=='__main__':main()
