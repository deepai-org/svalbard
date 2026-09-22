"""Coarse-search ownership, cancellation, reference loss and stale management."""
import json
from chip_model import P
from coarse_startup_lifecycle import CoarseStartupChip
from managed_resources import command

def main():
    c=CoarseStartupChip(rf_free_offset=-.08,watchdog_s=1e-3)
    assert command(c,'rf_coarse_start',2500000000)['accepted']
    owner=c.execute_management('resource_status',9,c.time)['value']
    shared=c.execute_management('resource_status',8,c.time)['value']
    assert owner&255==10 and owner&256 and shared==owner
    assert command(c,'rf_coarse_abort')['accepted']
    assert c.coarse.state=='cancelled' and c.rf_pll.bank_code==8 and not c.rf_pll.present
    before=len(c.coarse.history);c.advance(c.time+5e-6)
    assert len(c.coarse.history)==before and c.coarse.next_event is None
    assert command(c,'rf_coarse_start',2500000000)['accepted']
    c.set_reference(False,c.time+100e-9)
    assert c.coarse.state=='cancelled' and c.rf_pll.bank_code==8
    assert not command(c,'rf_coarse_start',2500000000)['accepted']
    c.set_reference(True,c.time)
    assert not c.rf_pll.present # External reference restored, fine loop still held.
    assert command(c,'rf_coarse_start',2500000000)['accepted'];c.advance(c.time+30e-6)
    assert c.coarse.qualified and c.rf_pll.present
    assert command(c,'configure_mode',1)['accepted'];c.advance(c.time+40e-6)
    assert c.state=='active' and c.rf_pll.locked
    assert not command(c,'rf_coarse_start',2437000000)['accepted']
    # Reject a pre-reset queued start at apply time, without any bank write.
    q=CoarseStartupChip(watchdog_s=1e-3)
    token,_,reply=q.submit('rf_coarse_start',0,q.epoch,q.rx_generation,2437000000)
    q.advance(1e-6);q.quiesce(q.time,'queued coarse reset')
    q.acknowledge_host_abort(q.epoch,q.time);q.acknowledge_drain(q.epoch,q.time)
    stale=q.read_reply(token,reply)
    assert not stale['accepted'] and q.rf_pll.bank_code==8 and not q.rf_pll.bank_writes
    report=dict(status='passed',owner_snapshot=owner,recovered_bank=c.rf_pll.bank_code,stale_reply=stale,
        controls=['shared sequencer ownership','command abort rollback','no post-abort count events','reference loss rollback',
                  'missing-reference start rejection','restore stays held until search completes','restart and fine acquisition','active search rejection','stale epoch start rejection'],
        complete_architecture=False,physical_qualification=False)
    (P/'evidence/connected-coarse-recovery.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed coarse cancellation, reference recovery, ownership and stale command checks')
if __name__=='__main__':main()
