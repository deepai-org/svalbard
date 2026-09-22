"""Actual engine ownership exposed through delayed management transactions."""
import json
from chip_model import P
from managed_local_run import prepared
from managed_resources import command
from resource_inventory import RESOURCES,OWNERS,resource_word
from timed_management import ManagedChip


def run(mode):
    c=prepared(mode)
    assert command(c,'resource_count')['value']==6
    assert command(c,'resource_status',1)['value']&255==3
    assert command(c,'resource_status',3)['value']&255==3
    before=(c.playback_selected,c.play_index,list(c.playback))
    try:c.descriptor(32)
    except ValueError:pass
    else:raise AssertionError('Host stole playback DAC')
    assert before==(c.playback_selected,c.play_index,c.playback)
    # Schedule sufficiently far ahead that slow management sees the reservation.
    c.schedule(32,c.time+50e-6);c.capture(32,c.time+50e-6)
    for index in range(4):assert resource_word(c,index)&256
    response=command(c,'resource_status',0)
    assert response['accepted'] and response['value']&256
    c.advance(c.time+55e-6);c.host_decoder.finish()
    assert c.host_samples==c.adc_words and len(c.adc_words)==32
    for index in range(4):assert not resource_word(c,index)&256
    # The response remains a snapshot of apply time, even after the run finishes.
    assert response['value']&256
    assert not command(c,'resource_status',6)['accepted']
    assert not command(c,'select_playback',0)['accepted']
    return dict(mode=mode,scheduled_adc_snapshot=response['value'],completed_samples=32,
        playback_host_conflict_rejected=True,ownership_retained_while_armed=True)


def cancellation(mode):
    c=prepared(mode)
    c.incoming_wire([0x155]*128,c.time)
    start=c.time+100e-9
    c.schedule(32,start);c.capture(32,start)
    c.advance(start+5e-9)
    assert c.adc_pending and c.dac_pending
    assert resource_word(c,4)&256
    snapshot=[resource_word(c,i) for i in range(6)]
    c.quiesce(c.time,'resource lifecycle check')
    assert not c.live_rx.enabled
    assert not any(resource_word(c,i)&256 for i in range(6))
    assert c.adc_cancelled==c.dac_cancelled==1
    # Quiesce stops work, but configuration stays frozen until drain acknowledgement.
    assert all(resource_word(c,i)&512 for i in range(6))
    c.acknowledge_host_abort(c.epoch,c.time)
    c.acknowledge_drain(c.epoch,c.time)
    assert c.state=='reset'
    assert not any(resource_word(c,i)&512 for i in range(6))
    assert not command(c,'resource_status',4)['value']&256
    return dict(mode=mode,before=snapshot,cancelled_adc=1,cancelled_dac=1,
                disabled_receiver_not_busy=True)


def main():
    c=ManagedChip()
    assert command(c,'resource_count')['value']==len(RESOURCES)
    for index in range(len(RESOURCES)):
        assert command(c,'resource_status',index)['accepted']
    rows=[run(m) for m in (0,1)]
    report=dict(status='passed',cases=rows,cancellation=[cancellation(m) for m in (0,1)],resources=[dict(id=i,name=n,dependencies=d) for i,(n,d) in enumerate(RESOURCES)],
        owners=OWNERS,complete_architecture=False,physical_qualification=False,
        limitations=['Discovery covers six existing data/converter/memory engines, not all analog tiles or diagnostic allocations.',
        'Dependencies describe intended services; their names do not certify physical implementation or dynamic allocation.',
        'Flags distinguish configured owner, pending work and armed configuration freeze; not transistor power state.',
        'Model-management IDs and packed flags are provisional, not a frozen SPI hardware ABI.'])
    (P/'evidence/connected-resource-inventory.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed both-mode resource discovery, busy snapshots and playback/host conflict checks')

if __name__=='__main__':main()
