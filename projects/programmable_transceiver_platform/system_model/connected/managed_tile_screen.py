"""Timed local-tile writes, apply-time snapshots and stale-epoch rejection."""
import json
from chip_model import P
from programmable_chip import ProgrammableChip
from managed_resources import command

def run(mode):
    c=ProgrammableChip(watchdog_s=100e-6)
    c.tile.drive(0,.02,0)
    token,apply,reply=c.submit('tile_configure',0,c.epoch,c.rx_generation,3|(2<<3)|64)
    c.advance(apply-1e-12);assert c.tile.weights==(1.,0.)
    assert c.read_reply(token,reply)['accepted']
    assert c.tile.weights==(.5,0.)
    assert command(c,'diagnostic_select',1)['accepted']
    old=c.tile.weights
    assert not command(c,'tile_configure',7)['accepted'] and c.tile.weights==old
    token,apply,reply=c.submit('tile_status',c.time,c.epoch,c.rx_generation)
    c.advance(apply)
    expected=int(c.tile.comparator)|2|4
    c.tile.discharge(c.time) # Physical event after snapshot must not rewrite reply.
    assert c.read_reply(token,reply)['value']==expected
    assert command(c,'tile_discharge')['accepted']
    c.configure(mode,c.time);c.advance(c.time+8e-6)
    c.capture(32,c.time+100e-9)
    assert not command(c,'diagnostic_select',0)['accepted'] and c.diagnostic_selected
    assert not command(c,'tile_discharge')['accepted']
    assert command(c,'tile_status')['accepted']
    stale,_,deadline=c.submit('diagnostic_select',c.time,c.epoch,c.rx_generation,0)
    c.set_reference(False,c.time);epoch=c.epoch
    c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    assert not c.read_reply(stale,deadline)['accepted'] and c.diagnostic_selected
    assert command(c,'diagnostic_select',0)['accepted']
    assert command(c,'resource_status',0)['value']&255==1
    return dict(mode=mode,status_snapshot=expected,armed_writes_rejected=True,stale_write_rejected=True,rf_owner_restored=True)

def main():
    rows=[run(m) for m in (0,1)]
    (P/'evidence/connected-managed-tile.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Named model commands are not a frozen hardware register ABI.',
        'Diagnostic inputs remain external held fixtures; physical monitor mux and triggers remain open.']),indent=2)+'\n')
    print('Passed timed tile management, snapshots, ownership and epoch fencing')
if __name__=='__main__':main()
