"""Timed management-only playback/capture with common RX/TX calibration."""
import hashlib,json,time
from pathlib import Path
from local_mode import LocalTransceiverChip
from shared_tx_traffic import scenario
from chip_model import encode_iq
from managed_resources import command


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Timed serialized management transactions, not SPI pin/CDC simulation.',
                     'Local RF playback/capture profile; wired streaming is disabled.',
                     'No arbitrary waveform memory depth or physical analog quality qualification.'])
    output=p/'evidence/fast-local-mode.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            c=LocalTransceiverChip(watchdog_s=20e-6)
            for target in (0,1):
                assert command(c,'cal_start',48|(target<<16))['accepted'];c.advance(c.time+40e-6)
            reply=command(c,'tx_cal_start');assert reply['accepted'];c.advance(c.time+25e-6)
            assert command(c,'tx_cal_commit',reply['value'])['accepted']
            bits=12 if mode==0 else 8
            words=[encode_iq(complex((i%7-3)/16,.1),bits) for i in range(32)]
            for i,word in enumerate(words):assert command(c,'write_playback',(i<<24)|word)['accepted']
            assert command(c,'select_playback',1)['accepted']
            assert command(c,'capture_enable',1)['accepted']
            assert command(c,'configure_mode',mode)['accepted']
            assert command(c,'start_local',3|(32<<2)|(8<<18))['accepted']
            c.advance(c.time+5e-6)
            assert c.capture_bank.done and c.tx.consumed==32
            assert not command(c,'write_playback',0)['accepted']
            captured=[]
            for i in range(32):
                r=command(c,'read_capture',i);assert r['accepted'];captured.append(r['value'])
                c.advance(c.time+10e-6)
            assert captured==c.adc_words and any(captured)
            assert c.state=='active' and c.return_ticks==0 and not c.host_samples
            assert not c.return_queue and not c.return_frame
            assert c.transitions==c.return_transitions==0
            assert command(c,'stop')['accepted']
            assert command(c,'ack_abort')['accepted'] and command(c,'ack_drain')['accepted']
            assert c.state=='reset'
            report['cases'].append(dict(mode=mode,captured=32,tx_consumed=c.tx.consumed,
                streaming_edges=0,slow_readout_survives_streaming_watchdog=True,drained=True));save()
            print(mode,'passed',flush=True)
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
