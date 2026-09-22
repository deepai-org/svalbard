"""Timed local converter start command with atomic multi-engine scheduling."""
import json,math
from chip_model import P,encode_iq
from timed_management import ManagedChip
from managed_resources import command


def prepared(mode,timing_ticks=None):
    c=ManagedChip(watchdog_s=1e-3,adc_latency_s=40e-9,dac_latency_s=20e-9)
    for i in range(32):
        assert command(c,'write_playback',(i<<24)|encode_iq(.3 if i%2 else -.2,12 if mode==0 else 8))['accepted']
    assert command(c,'select_playback',1)['accepted']
    assert command(c,'capture_enable',1)['accepted']
    if timing_ticks is not None:
        assert command(c,'configure_local_timing',timing_ticks & 0xffff)['accepted']
    assert command(c,'configure_mode',mode)['accepted']
    return c


def run(mode):
    c=prepared(mode);payload=3|(32<<2)|(4<<18)
    token,apply_time,reply_time=c.submit('start_local',c.time,c.epoch,c.rx_generation,payload)
    c.advance(apply_time-1e-12)
    assert c.remaining==c.adc_left==0 and c.tx.consumed==0
    c.advance(apply_time)
    assert c.remaining==c.adc_left==32 and c.tx.consumed==0
    assert c.next_sample>apply_time and c.next_adc>apply_time
    reply=c.read_reply(token,reply_time);assert reply['accepted']
    c.host_decoder.finish()
    assert c.tx.consumed==32 and c.host_samples==c.adc_words and len(c.adc_words)==32
    assert c.capture_bank.done and c.dac_accounting()['pending']==c.adc_accounting()['pending']==0
    assert command(c,'status')['capture_done']
    before=c.tx.consumed
    assert not command(c,'start_local',payload)['accepted']
    assert c.tx.consumed==before and math.isinf(c.next_sample)
    return dict(mode=mode,reply=reply,played=32,captured=32)


def atomic_failure(mode):
    c=prepared(mode)
    # Existing capture is scheduled far ahead. A combined request can schedule TX
    # in the staged object, but must reject RX busy without committing either.
    c.capture(32,c.time+100e-6);old=(c.next_sample,c.next_adc,c.remaining,c.adc_left,c.play_index)
    result=command(c,'start_local',3|(32<<2)|(4<<18))
    assert not result['accepted']
    assert old==(c.next_sample,c.next_adc,c.remaining,c.adc_left,c.play_index)
    assert c.tx.consumed==0 and c.adc_sampled==0
    return dict(mode=mode,rejected=result['reason'],tx_started=False)


def main():
    rows=[run(m) for m in (0,1)];failures=[atomic_failure(m) for m in (0,1)]
    report=dict(status='passed',cases=rows,atomic_rejection_cases=failures,complete_architecture=False,physical_qualification=False,
        contract=['Payload:bits1:0 TX/RX direction mask,bits17:2 sample count,bits31:18 start delay in control-clock periods.',
        'Current local memory operation requires32 samples; selected TX/RX clocks start from command execution time plus the declared delay.',
        'Both selected engines are preflighted together; rejection commits no scheduling state.'],
        limitations=['Finite32-sample local-memory operation only; continuous streaming/run-stop controls remain open.',
        'RX defaults to10ns after TX; configure_local_timing selects a signed control-period offset. General trigger routing remains open.',
        'Staging relies on schedule/capture methods assigning new timing/codec objects without advancing shared analog state.',
        'Packed operation still requires multiword hardware management implementation.'])
    (P/'evidence/connected-managed-local-run.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed both-mode command-only local runs and atomic busy-direction rejection cases')

if __name__=='__main__':main()
