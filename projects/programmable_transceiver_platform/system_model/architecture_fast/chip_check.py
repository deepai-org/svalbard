"""Explicit common-model preparation versus previously verified composition."""
import hashlib,json,time
from pathlib import Path
from chip import TransceiverChip
from shared_tx_traffic import SharedOutputChip,scenario
from managed_resources import command
IDEAL=dict(gain_imbalance_db=0.,phase_error_deg=0.,lo_feedthrough=0j,cubic=0.)

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Selected preparation/capture equivalence; full traffic suite still needs migration.',
                     'Output observer samples at ADC events; no emission mask or physical qualification.'])
    output=p/'evidence/fast-common-chip.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        a=TransceiverChip(load_capacitance=0);b=TransceiverChip(load_capacitance=1e-12)
        assert a.tx_output_parameters==b.tx_output_parameters
        a.external_source([.2+.1j],0.,1.,offset_hz=250e3)
        assert a.time==0 and a.tx_cal.state=='idle' and not a.tx_cal.valid and a.tx_adc_samples==0
        report['source_install_does_not_calibrate']=True
        report['reference_load_does_not_select_output_distortion']=True
        for mode in (0,1):
            for loaded in (False,True):
                options=dict(load_capacitance=1e-12 if loaded else 0,watchdog_s=1e-3)
                old=SharedOutputChip(**options)
                new=TransceiverChip(output_parameters=None if loaded else IDEAL,**options)
                for c in (old,new):c.advance(10e-6)
                old.external_source([.2+.1j],old.time,1.,offset_hz=250e3)
                reply=command(new,'tx_cal_start');assert reply['accepted']
                new.advance(new.time+25e-6)
                assert command(new,'tx_cal_commit',reply['value'])['accepted']
                new.tx_probe.clear();new.probe_times.clear()
                new.external_source([.2+.1j],new.time,1.,offset_hz=250e3)
                assert old.time==new.time and old.tx_cal.candidate==new.tx_cal.candidate
                assert old.tx_adc_samples==new.tx_adc_samples==9
                for c in (old,new):
                    c.configure(mode,c.time);c.advance(c.time+8e-6)
                    c.capture(32,c.time+100e-9);c.advance(c.time+4e-6);c.host_decoder.finish()
                    assert c.host_samples==c.adc_words and len(c.host_samples)==32
                assert old.host_samples==new.host_samples
                assert old.probe_times==new.probe_times and old.tx_probe==new.tx_probe
                assert old.adc_reference.charge==new.adc_reference.charge
                report['cases'].append(dict(mode=mode,loaded=loaded,exact_fit_and_waveform_match=True));save()
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()
    print('Common model extraction passed',report['elapsed_s'])

if __name__=='__main__':main()
