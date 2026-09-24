"""Count-free RX stop/overflow and opposite-mode restart on common composition."""
import hashlib
import json
import time
from pathlib import Path
from shared_tx_traffic import scenario
from chip import TransceiverChip as SharedOutputChip
from managed_resources import command
import continuous_receiver_screen as screen
from external_rf_lifecycle import ExternalChip


def run(mode,overflow=False):
    return screen.run(mode, overflow, configure_source=lambda c:
        ExternalChip.external_source(c, [.2+.1j], 0., 1., offset_hz=250e3))

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic();original=screen.ProgrammableChip
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Finite observation of count-free RX, not indefinite queue stability.',
                     'Stop/overflow use lossy epoch abort; graceful drain remains open.',
                     'Continuous TX and simultaneous continuous wired/RF operation are separate requirements.'])
    output=p/'evidence/fast-continuous-rx.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save();chips=[]
    class RecordedChip(SharedOutputChip):
        def __init__(self,**kwargs):super().__init__(**kwargs);chips.append(self)
    screen.ProgrammableChip=RecordedChip
    try:
        for mode in (0,1):
            for overflow in (False,True):
                result=run(mode,overflow)
                c=chips[-1];old_epoch=c.epoch
                c.configure(1-mode,c.time);c.advance(c.time+8e-6)
                adc_begin=len(c.adc_words);host_begin=len(c.host_samples)
                assert command(c,'rx_stream_start',8)['accepted']
                c.advance(c.time+10e-6)
                delivered=c.host_samples[host_begin:]
                assert c.state=='active' and len(delivered)>128
                assert delivered==c.adc_words[adc_begin:adc_begin+len(delivered)]
                count=len(delivered)
                assert command(c,'stop')['accepted']
                c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
                assert c.state=='reset' and c.epoch==old_epoch+1
                result.update(restarted_mode=1-mode,restarted_delivered=count,second_drain=True)
                report['cases'].append(result);save();print(mode,overflow,'passed',flush=True)
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:screen.ProgrammableChip=original;save()

if __name__=='__main__':main()
