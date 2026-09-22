"""Monitor validity, held analog state and recovery through reference loss."""
import json
from chip_model import P
from programmable_chip import ProgrammableChip
from managed_resources import command

def run(mode):
    c=ProgrammableChip(watchdog_s=100e-6)
    assert command(c,'monitor_select',3)['accepted']
    assert not command(c,'monitor_status')['value']&256
    c.configure(mode,c.time);c.advance(c.time+8e-6)
    c.detect_start(c.time,c.epoch);c.advance(c.time+150e-9)
    assert c.monitor_last>0 and c.monitor_valid
    assert c.monitor_epoch==c.epoch
    held=c.tile.inputs;voltage=c.tile.voltage;count=c.monitor_updates
    c.set_reference(False,c.time)
    assert not c.monitor_valid and c.tile.voltage==voltage and c.tile.inputs==held
    c.advance(c.time+1e-6)
    assert c.monitor_updates==count and c.tile.inputs==held
    assert not command(c,'monitor_status')['value']&256
    epoch=c.epoch;c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    assert command(c,'detect_rearm')['accepted']
    c.set_reference(True,c.time);c.configure(1-mode,c.time)
    assert not c.monitor_valid
    c.advance(c.time+8e-6)
    assert c.monitor_valid and c.monitor_epoch==c.epoch and c.monitor_updates>count
    assert command(c,'monitor_status')['value']&256
    # New active probe must refresh the sampled local-pad observation.
    c.detect_start(c.time,c.epoch);c.advance(c.time+150e-9)
    assert c.monitor_last>0
    return dict(mode=mode,held_probe_v=held[0],updates_before_loss=count,
        updates_after_recovery=c.monitor_updates,epoch=c.epoch,valid_after_recovery=True)

def main():
    rows=[run(m) for m in (0,1)]
    (P/'evidence/connected-monitor-recovery.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Validity qualifies sampling epoch, not analog accuracy or freshness duration.',
        'Held buffer and tile capacitor survive digital shutdown; physical leakage is simplified.',
        'Nominal probe loads only; fixed monitor clock remains an assumed service.']),indent=2)+'\n')
    print('Passed probe monitoring, shutdown validity and opposite-mode recovery')
if __name__=='__main__':main()
