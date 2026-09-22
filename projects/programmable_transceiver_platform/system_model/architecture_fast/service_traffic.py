"""Independent RF quality and simultaneous wired traffic after timed I/Q trim."""
import hashlib
import json
import time
from pathlib import Path
import run as architecture
from services import ServiceChip
from traffic import run
from managed_resources import command
from chip_model import decode_iq
from rf_modulated_quality import Multicarrier
from rf_quality_screen import quality


def simulate(mode,impaired):
    chips=[];calibration=[]
    def factory(**kw):
        options=dict(load_capacitance=0)
        if impaired:
            options=dict(load_capacitance=1e-12,dac_reference_load_capacitance=.2e-12,
                return_charge_per_transition=50e-15,rf_hz_per_v=1e6,wire_hz_per_v=1e5,
                rf_noise_rms_hz=20000,wire_noise_rms_hz=20000,noise_seed=839,
                frontend=dict(gain_error=.03,phase_error=.03,saturation=.8,noise_rms=.001,seed=800))
        c=ServiceChip(trim_offsets_v=(.07,-.045),**options,**kw)
        chips.append(c);return c
    def prepare(c):
        for target in (0,1):
            assert command(c,'cal_start',48|(target<<16))['accepted']
            c.advance(c.time+40e-6)
            assert c.cal.state=='done' and not c.cal.valid
            calibration.append(dict(c.cal.result))
        assert c.maintenance_accounting()==dict(sampled=2,completed=2,cancelled=0,pending=0)
        c.tx_probe.clear();c.probe_times.clear()
        c.external_source(Multicarrier(seed=828)(1024,40e6),c.time,25e-9,offset_hz=250e3)
    traffic=run(mode,0,frames=16,chip_factory=factory,prepare=prepare,
                matched_reference=True,waveform=Multicarrier(seed=804),startup_settle_s=10e-6)
    c=chips[0]
    rx=[decode_iq(w,c.bits) for w in c.host_samples]
    c.set_reference(False,c.time)
    assert c.state=='draining' and not c.session.enabled('rf') and not c.session.enabled('wire')
    c.advance(c.time+1e-6)
    c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
    c.set_reference(True,c.time);c.configure(1-mode,c.time);c.advance(c.time+5e-6)
    assert c.state=='active' and c.rf_pll.locked and c.wire_pll.locked
    return rx,c.tx_probe,c.probe_times,dict(traffic=traffic,calibration=calibration,recovery=True)


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    start=time.monotonic()
    files=list(architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[architecture.P/'verification/stream_codec.py']
    hashes={str(f.relative_to(architecture.P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Assumed analog and oscillator-noise parameters; sampled PLL feedback.',
                     'Calibration completion does not establish physical accuracy validity.',
                     'Finite four-path records and external gain-fit quality screen, not protocol compliance.'])
    output=architecture.P/'evidence/fast-service-traffic.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            rx0,tx0,t0,_=simulate(mode,False)
            rx,tx,t,result=simulate(mode,True)
            assert len(t)==len(t0)
            # Compare original sample order: clock-induced timing error remains
            # in the waveform. No interpolation or phase/time alignment.
            skew=max(abs(a-b) for a,b in zip(t,t0))
            rq=quality(rx0,rx);tq=quality(tx0,tx)
            result.update(mode=mode,rx_quality=rq,tx_quality=tq,max_observation_displacement_s=skew)
            report['cases'].append(result);save()
            print(mode,rq['corrected_relative_rms'],tq['corrected_relative_rms'],flush=True)
            assert rq['screen_pass'] and tq['screen_pass']
        assert all(hashlib.sha256((architecture.P/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
