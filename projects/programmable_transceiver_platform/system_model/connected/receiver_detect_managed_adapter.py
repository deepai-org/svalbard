"""Staged named receiver-detection commands using existing transport/fences."""
import json,hashlib,math
from pathlib import Path
from receiver_detect_chip_adapter import DetectChip
from sampled_clock_lifecycle import SampledClockChip
from managed_resources import command
from receiver_detect_probe_sequence import reject
from chip_model import P

class ManagedDetectChip(DetectChip):
    COMMANDS=('detect_start','detect_status','detect_rearm')
    def submit(self,operation,time,expected_epoch,expected_generation,payload=0):
        if operation not in self.COMMANDS:return super().submit(operation,time,expected_epoch,expected_generation,payload)
        if payload:raise ValueError('Reserved detection payload')
        # Reuse the real serialized request/reply timing, capacity and fencing.
        token,apply,reply=super().submit('status',time,expected_epoch,expected_generation,0)
        for when,key,stage,data in self.command_events:
            if key==token and stage=='apply':data['operation']=operation;break
        else:raise AssertionError('Queued command missing')
        return token,apply,reply
    def execute_management(self,operation,payload,time):
        if operation not in self.COMMANDS:return super().execute_management(operation,payload,time)
        self.probe.advance(time)
        if operation=='detect_start':self.detect_start(time,self.epoch)
        elif operation=='detect_rearm':
            if self.state not in ('reset','active'):raise ValueError('Drain before detection recovery')
            busy=bool(self.wire_queue or self.wire_remaining or (self.serializer and self.serializer.active))
            self.probe.rearm(time,self.probe.epoch,busy)
            self.probe_chip_epoch=None
        else:
            states=('idle','probing','releasing','ready','aborted','fault')
            decision=0
            if self.probe.state=='ready' and self.probe_chip_epoch==self.epoch:
                decision={'present':1,'absent':2,'indeterminate':3}[self.probe.read(self.probe.epoch)['decision']]
            return dict(value=states.index(self.probe.state)|(decision<<8))
        return {}
    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid chip time')
        while self.time<time:
            end=min(time,self.probe.next_event,self.command_events[0][0] if self.command_events else math.inf)
            SampledClockChip.advance(self,end)
            self.probe.advance(end)
        SampledClockChip.advance(self,time);self.probe.advance(time)


def run(mode):
    c=ManagedDetectChip(watchdog_s=100e-6);c.configure(mode,0);c.advance(8e-6)
    token,apply,reply=c.submit('detect_start',c.time,c.epoch,c.rx_generation)
    c.advance(apply-1e-12);assert c.probe.state=='idle'
    c.advance(apply);assert c.probe.state=='probing'
    reject(lambda:c.read_reply(token,c.time))
    assert c.read_reply(token,reply)['accepted']
    result=command(c,'detect_status');assert result['value']>>8==1
    # Returned status is an immutable snapshot even after subsequent reset.
    saved=dict(result)
    # Queue a fresh start, then invalidate its epoch before execution.
    old,_,old_reply=c.submit('detect_start',c.time,c.epoch,c.rx_generation)
    c.set_reference(False,c.time);epoch=c.epoch
    c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    assert not c.read_reply(old,old_reply)['accepted']
    assert saved['value']>>8==1
    assert command(c,'detect_rearm')['accepted']
    assert c.probe.state=='idle' and c.probe.result is None
    assert command(c,'detect_status')['value']>>8==0
    c.set_reference(True,c.time);c.configure(1-mode,c.time);c.advance(c.time+8e-6)
    assert command(c,'detect_start')['accepted']
    assert command(c,'detect_status')['value']>>8==1
    return dict(mode=mode,start_applied_s=apply,status=saved,stale_command_rejected=True,
        reset_rearm_clears_result=True,other_mode_redetection=True)


def main():
    rows=[run(m) for m in (0,1)]
    report=dict(status='passed',staged_adapter=True,physical_qualification=False,cases=rows,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        dependencies={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('receiver_detect_chip_adapter.py','receiver_detect_rearm_screen.py','receiver_detect_probe_sequence.py','receiver_detect_release_screen.py','receiver_detect_load_screen.py')},
        limitations=['Staged named command adapter, not a frozen hardware register ABI or registered aggregate scenario.',
        'Probe source/sink load remains uncoupled from chip supply; resource-discovery integration remains pending.',
        'Nominal two-leg present load for these management tests; other decision cases were tested separately.'])
    (P/'evidence/receiver-detect-managed-adapter.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed both-mode timed detection commands, stale fencing and post-reset rearm/redetection')

if __name__=='__main__':main()
