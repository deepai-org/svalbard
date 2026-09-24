"""Isolated canonical raw pad observation to ordered host-record experiment."""
import hashlib,json
from full_chip_model import make_chip
from protocol_pad import SharedWiredPad
from fast_loaded_output import P
def queue_controls():
    from diagnostic_tile_lifecycle import DiagnosticChip
    from resource_configuration import ResourceConfigurationCommands
    class Fixture(ResourceConfigurationCommands,DiagnosticChip):
     TILE_COMMANDS=DiagnosticChip.TILE_COMMANDS+ResourceConfigurationCommands.RESOURCE_COMMANDS
     def configure_record_return(self,enabled=True):
      if not self.permitted:raise ValueError('busy')
      self.selected=enabled
    for payload in (0,1,2,256):
     c=Fixture();c.permitted=True;c.selected=None
     token,apply,reply=c.submit('record_return_configure',0,c.epoch,c.rx_generation,payload)
     c.advance(apply-1e-12);assert c.selected is None
     r=c.read_reply(token,reply)
     assert r['accepted']==(payload in (0,1))
     assert c.selected==(bool(payload) if payload in (0,1) else None)
    for stale in (False,True):
     c=Fixture();c.permitted=True;c.selected=None
     token,apply,reply=c.submit('record_return_configure',0,c.epoch+int(stale),c.rx_generation,1)
     c.permitted=False
     r=c.read_reply(token,reply);assert not r['accepted'] and c.selected is None
    print('Passed six existing-queue dispatch/timing/rejection cases; recording callback only')

    # Actual composed chip permissions, without forcing readiness or clocks.
    c=make_chip()
    c.configure_resources(engine='wire',frame_words=8)
    c.configure_record_return()
    try:c.incoming_wire([1],c.time+1e-9)
    except ValueError as error:assert 'owns receive transport' in str(error)
    else:raise AssertionError('Serial traffic admitted into raw-record return')
    c.configure_record_return(enabled=False)
    c.require_wire_direction('rx')
    c.configure_resources(engine='wire',rx_enabled=False)
    try:c.start_wire_return(c.time+1e-9)
    except ValueError as error:assert 'RX disabled' in str(error)
    else:raise AssertionError('Disabled receive transport started')
    print('Passed actual composition receive-format ownership and RX-enable guards')

files=list((P/'system_model').rglob('*.py'))+list((P/'verification').glob('*.py'))+[P/'spec/contract.json']
hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
report=dict(status='running',source_sha256=hashes,full_chip_closure=False)
out=P/'evidence/record-return.json';out.write_text(json.dumps(report,indent=2)+'\n')
try:
 queue_controls()
 report['queue_and_ownership_controls']=True
 c=make_chip();c.configure_resources(engine='wire',line_rate_bps=480e6,frame_words=8,pad_path='bidirectional')
 pad=SharedWiredPad();c.analog_owner.pad_branch=pad;pad.configure('usb','device','hs',True)
 token,apply,reply=c.submit('record_return_configure',c.time,c.epoch,c.rx_generation,1)
 c.advance(apply-1e-12);assert not getattr(c,'record_return',False)
 c.advance(apply);assert c.record_return
 assert c.read_reply(token,reply)['accepted']
 print('Serialized raw-record selection passed',flush=True)
 try:c.observe_record('bit',1,c.time)
 except ValueError:pass
 else:raise AssertionError('Stopped observation admitted')
 c.configure(0,c.time)
 for _ in range(30):
  if c.state=='active':break
  c.advance(c.time+1e-6)
 assert c.state=='active',c.state
 print('Normal acquisition completed',c.time,flush=True)
 c.start_wire_return(c.time+4e-9);start=c.time+8e-9;ui=1/480e6
 levels=[(i+i//4)%2 for i in range(23)]
 for i,level in enumerate(levels):
  c.advance(start+i*ui);c.analog_owner.pad_branch.drive(peer='J' if level else 'K')
  c.advance(start+(i+.5)*ui);observation=c.analog_owner.pad_branch.observe()
  assert not observation['squelch']
  c.observe_record('bit',int(observation['j']),c.time)
 c.advance(start+len(levels)*ui);c.analog_owner.pad_branch.drive()
 c.advance(start+(len(levels)+.5)*ui)
 assert c.analog_owner.pad_branch.observe()['squelch']
 boundary=c.time;c.observe_record('event',7,boundary)
 c.advance(c.time+150e-9)
 received=[]
 for time,(kind,value,count) in c.host_records:
  if kind=='data':received.extend((value>>i)&1 for i in range(count))
 assert received==levels
 assert c.host_records[-1][1]==('event',7,0)
 assert [r[1][2] for r in c.host_records]==[10,10,3,0]
 assert c.time==c.analog_owner.time==c.analog_owner.host_bank.time
 # Inject a same-time internal producer overload: fault must stop the chip,
 # flush a partial word and prevent further host delivery. Not a pad-rate test.
 for value in range(15):c.observe_record('event',value,c.time)
 c.observe_record('bit',1,c.time)
 before=list(c.host_records)
 try:c.observe_record('event',99,c.time)
 except ValueError as error:assert 'overflow' in str(error)
 else:raise AssertionError('Full record queue did not fault')
 assert c.state=='draining'
 assert not c.record_source.records and c.record_source.valid_bits==0 and not c.record_return
 try:c.observe_record('event',8,c.time)
 except ValueError:pass
 else:raise AssertionError('Stopped event admitted')
 c.advance(c.time+20e-9);assert c.host_records==before
 # A fresh stopped instance checks resource-token and RX-enable guards.
 g=make_chip();g.configure_resources(engine='wire',frame_words=8,rx_enabled=False)
 try:g.configure_record_return()
 except ValueError:pass
 else:raise AssertionError('Disabled RX configured')
 g.configure_resources(engine='wire',frame_words=8);g.configure_record_return()
 g.configure_resources(engine='wire',frame_words=64)
 try:g.make_return_receiver()
 except ValueError:pass
 else:raise AssertionError('Stale raw decoder selected')
 assert all(hashlib.sha256((P/f).read_bytes()).hexdigest()==h for f,h in hashes.items())
 report.update(status='passed',overflow_stops_delivery=True,lifecycle_guards=True,records=c.host_records,event_latency_s=c.host_records[-1][0]-boundary,
   scope='Actual coupled pad voltage with prescribed sampling, canonical return scheduler and ideal host decoder; no CDR, physical capture or USB packet compliance')
 print('Ordered partial data and event delivered',flush=True)
except BaseException as error:report.update(status='failed',error=repr(error));raise
finally:out.write_text(json.dumps(report,indent=2)+'\n')
