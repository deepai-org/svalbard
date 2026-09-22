"""Timed packed resource writes and execution-time permission checks."""
import json
from chip_model import P,encode_iq
from timed_management import ManagedChip
from playback_memory_lifecycle import ready


def command(c,operation,payload=0):
    token,_,reply=c.submit(operation,c.time,c.epoch,c.rx_generation,payload)
    return c.read_reply(token,reply)


def run(mode):
    c=ManagedChip(watchdog_s=1e-3)
    # loopback, gain2, TX5MHz, RX10MHz: every setting fits in8 payload bits.
    packed=0|(2<<2)|(1<<4)|(2<<6)
    assert command(c,'configure_rx',packed)['accepted']
    assert c.rx_gain==2 and c.tx.rx_pole>c.tx.pole
    before=(c.rx_gain,c.tx.pole,c.tx.rx_pole)
    assert not command(c,'configure_rx',packed|(1<<8))['accepted']
    assert before==(c.rx_gain,c.tx.pole,c.tx.rx_pole)
    bits=12 if mode==0 else 8;words=[encode_iq(.2 if i%2 else -.1,bits) for i in range(32)]
    for i,word in enumerate(words):assert command(c,'write_playback',(i<<24)|word)['accepted']
    assert command(c,'select_playback',1)['accepted']
    assert command(c,'capture_enable',1)['accepted']
    assert command(c,'configure_mode',mode)['accepted'] and c.state=='active'
    start=c.time+100e-9;c.schedule(32,start);c.capture(32,start+10e-9)
    # Delivery while armed must reject mutation, even during ongoing conversion.
    reply=command(c,'write_playback',0)
    assert not reply['accepted'] and c.playback==words
    c.host_decoder.finish();assert c.host_samples==c.adc_words and len(c.adc_words)==32
    read=command(c,'read_capture',17);assert read['accepted'] and read['value']==c.adc_words[17]
    assert command(c,'stop')['accepted'] and c.state=='draining'
    assert not command(c,'ack_drain')['accepted']  # Host return abort must precede drain.
    assert command(c,'ack_abort')['accepted']
    epoch=c.epoch;reply=command(c,'ack_drain')
    assert reply['accepted'] and reply['value']==epoch+1 and c.state=='reset'
    return dict(mode=mode,rf_samples=32,read_capture=read['value'],new_epoch=c.epoch)


def race():
    c=ManagedChip(watchdog_s=50e-6)
    token,_,reply=c.submit('select_playback',0,c.epoch,c.rx_generation,1)
    ready(c,0)
    result=c.read_reply(token,reply)
    assert not result['accepted'] and not c.playback_selected
    return result


def main():
    rows=[run(m) for m in (0,1)];r=race()
    report=dict(status='passed',cases=rows,queued_while_disarmed_applied_while_armed=r,
        complete_architecture=False,physical_qualification=False,
        limitations=['Packed command payloads are candidate model encodings, not implemented register/RTL ABI.',
        'RF and wire sample scheduling still uses explicit testbench engine requests; autonomous run-length/continuous-mode controls remain open.',
        'LO/trim/calibration and full resource topology controls remain outside the timed command set.'])
    (P/'evidence/connected-managed-resources.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed both-mode timed resource programming/capture/recovery and execution-time arm race')

if __name__=='__main__':main()
