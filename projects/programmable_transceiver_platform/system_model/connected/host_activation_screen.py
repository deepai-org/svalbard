"""Activation monitor controls plus real-chip incomplete-start/recovery guards."""
import json,random
from chip_model import P,encode
from host_activation import HostActivation
from host_activation_chip import HostActivationChip
from managed_resources import command

def reject(f):
 try:f()
 except ValueError:return
 raise AssertionError('Invalid activation accepted')
def main():
 rows=[]
 for mode in (0,1):
    a=HostActivation();a.start(mode,0,4);rng=random.Random(1941)
    for frame in range(64):
        words=encode(mode,[],[],frame);words[5:]=[rng.randrange(1024) for _ in words[5:]]
        for i,w in enumerate(words):a.feed(w,(frame*64+i+1)*a.period,4)
    assert a.state=='ready' and a.ready(a.last,4)
    assert not a.ready(a.last,5) and not a.ready(a.last+65*a.period,4)
    rows.append(dict(mode=mode,words=a.words,transitions=a.transitions))
    low=HostActivation();low.start(mode,0,0)
    words=encode(mode,[],[],0)
    for i,w in enumerate(words[:-1]):low.feed(w,(i+1)*low.period,0)
    reject(lambda:low.feed(words[-1],64*low.period,0))
    payload=HostActivation();payload.start(mode,0,0);words=encode(mode,[],[7],0)
    for i,w in enumerate(words[:4]):payload.feed(w,(i+1)*payload.period,0)
    reject(lambda:payload.feed(words[4],5*payload.period,0))
    gap=HostActivation();gap.start(mode,0,0)
    reject(lambda:gap.start(mode,0,0));reject(lambda:gap.feed(0,0,1))
    gap.feed(words[0],gap.period,0)
    reject(lambda:gap.feed(words[1],3*gap.period,0))
    c=HostActivationChip(rf_fast_fraction=.35,watchdog_s=1e-3)
    assert command(c,'rf_coarse_start',2437000000)['accepted'];c.advance(c.time+35e-6)
    assert command(c,'configure_mode',mode)['accepted'];c.advance(c.time+40e-6)
    assert c.state=='active'
    reject(lambda:c.descriptor(16));reject(lambda:c.capture(16,c.time+1e-6))
    reject(lambda:c.accept_wire(7));reject(lambda:c.schedule_wire(1,c.time+1e-6))
    assert command(c,'host_train_start')['accepted']
    assert c.execute_management('host_train_status',0,c.time)['value']&255==1
    start=c.time;words=encode(mode,[],[],0)
    for i,w in enumerate(words[:16]):c.feed(w,c.epoch,start+(i+1)*c.host_activation.period)
    assert c.host_activation.words==16;reject(lambda:c.descriptor(16))
    if mode==0:
        deadline=c.host_activation.deadline;c.advance(deadline+1e-9)
        assert any(event[:2]==['quiesce','host training clock timeout'] and event[-1]==deadline for event in c.events)
    else:c.set_reference(False,c.time)
    assert c.state=='draining' and c.host_activation.state=='failed'
    assert c.tx.accepted==0 and c.wire_consumed==0
    c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
    assert not c.host_activation.ready(c.time,c.epoch)
 report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
    controls=['both-mode 64-frame counting','low switching rejection','payload rejection','stale epoch','clock gap','duplicate arm',
      'untrained RF/wired start rejection','partial training rejection','exact timeout deadline','reference loss','drain does not restore qualification'],
    limitations=['Per-edge timestamps are a mathematical timing contract, not a implemented on-chip time-to-digital monitor.',
      'Activity thresholds and idle-validity window are provisional; full noise/load and pause/recovery envelopes remain open.',
      'Experimental streaming-only candidate; SPI-only capture uses separate existing architecture and is not promoted here.'])
 (P/'evidence/connected-host-activation.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Passed activation counting, negative controls, timed abort and real-chip start gates')
if __name__=='__main__':main()
