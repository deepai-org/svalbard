"""Staged receiver-detect ownership in the actual timed resource interface."""
import json,hashlib
from pathlib import Path
from receiver_detect_managed_adapter import ManagedDetectChip
from managed_resources import command
from chip_model import P

class ResourceDetectChip(ManagedDetectChip):
    def execute_management(self,operation,payload,time):
        if operation=='resource_count':
            if payload:raise ValueError('Reserved resource-count payload')
            return dict(value=7)
        if operation=='resource_status' and payload in (5,6):
            self.probe.advance(time)
            active=self.probe.state in ('probing','releasing')
            blocked=self.probe.state not in ('idle','ready')
            if payload==5 and not blocked:return super().execute_management(operation,payload,time)
            # Owner7 = detection. Bit11 exposes a TX interlock separately from
            # bit8 (actual probing/release activity), including aborted/fault state.
            return dict(value=7|(int(active)<<8)|(int(self.session.armed)<<9)|(1<<10)|(int(blocked)<<11))
        return super().execute_management(operation,payload,time)


def run(mode,index,chip_class=ResourceDetectChip):
    c=chip_class(watchdog_s=100e-6);c.configure(mode,0);c.advance(8e-6)
    assert command(c,'resource_count')['value']==7
    token,apply,reply=c.submit('resource_status',c.time,c.epoch,c.rx_generation,index)
    c.advance(apply-50e-9);c.detect_start(c.time,c.epoch)
    c.advance(apply)
    snapshot=c.read_reply(token,reply)
    assert snapshot['accepted'] and snapshot['value']&255==7
    assert snapshot['value']&256 and snapshot['value']&2048
    assert c.probe.state=='ready'  # Reply preserves the earlier busy snapshot.
    released=command(c,'resource_status',5)['value']
    assert released&255==6 and not released&2048
    c.detect_start(c.time,c.epoch);c.set_reference(False,c.time)
    stopped=c.execute_management('resource_status',5,c.time)['value']
    assert stopped&255==7 and stopped&2048 and not stopped&256
    epoch=c.epoch;c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    assert command(c,'detect_rearm')['accepted']
    assert not command(c,'resource_status',5)['value']&2048
    assert not command(c,'resource_status',7)['accepted']
    return dict(mode=mode,resource_id=index,busy_snapshot=snapshot['value'],aborted_snapshot=stopped,
        released_owner=6,rearm_clears_interlock=True)


def main():
    rows=[run(m,i) for m in (0,1) for i in (5,6)]
    report=dict(status='passed',staged_adapter=True,physical_qualification=False,cases=rows,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        dependencies={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('receiver_detect_managed_adapter.py','receiver_detect_chip_adapter.py','receiver_detect_rearm_screen.py','receiver_detect_probe_sequence.py','receiver_detect_release_screen.py','receiver_detect_load_screen.py')},
        contract=['Resource6 is receiver detector; owner7 is detection; bit11 is TX interlock, distinct from active busy bit8.',
        'Aborted/faulted probes retain a TX interlock with no active stimulus until explicit recovery.'],
        limitations=['Staged provisional discovery ABI; must be promoted with the detector before claiming main-model capability.',
        'Supply-current coupling and full load/sensor uncertainty remain open.'])
    (P/'evidence/receiver-detect-resource-adapter.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed four timed ownership snapshots, release, abort interlock and explicit recovery cases')

if __name__=='__main__':main()
