"""Framed RF burst faults propagate to the RF consumer, preserving wired flow."""
import hashlib,json,math
from pathlib import Path
from chip_model import P,encode,Receiver,encode_iq,decode_iq
from burst_codec import BurstEncoder,BurstDecoder
from rf_tx_state import RfTxState
from session import Session

class BurstIngress:
    def __init__(self,tx,bits,count):
        self.tx=tx;self.bits=bits;self.decoder=BurstDecoder(2*bits,count)
        self.first_fault=None
    def trip(self,time,reason):
        if self.first_fault is None:
            self.tx.reset(time)
            self.tx.session.trip('rf')
            self.first_fault=dict(time_s=time,reason=reason,
                samples_decoded=self.decoder.delivered,samples_consumed=self.tx.consumed)
    def feed(self,word,time):
        try:samples=self.decoder.feed(word)
        except ValueError as error:
            self.trip(time,str(error));return
        for sample in samples:self.tx.accept(decode_iq(sample,self.bits))
    def finish(self,time):
        try:self.decoder.finish()
        except ValueError as error:self.trip(time,str(error))

rows=[]
for mode,bits,rate in ((0,12,250e6),(1,8,312.5e6)):
    s=Session();s.configure(mode);s.host_ready=True;s.ready.update(rf=True,wire=True);s.arm()
    tx=RfTxState(s);ingress=BurstIngress(tx,bits,2)
    encoder=BurstEncoder(2*bits,2);words=[]
    for value in (.5,.25):words.extend(encoder.push(encode_iq(value,bits)))
    words.extend(encoder.finish())
    used=(4*bits)%10;assert used
    words[-1]|=1<<used  # Corrupt only padding; header remains valid.
    receiver=Receiver(mode);wire=[];first_played=False;filter_at_fault=None
    for tick,word in enumerate(encode(mode,[913,17,801],words,0)):
        event=receiver.feed(word)
        if event and event[0]=='iq':
            ingress.feed(event[1],tick/rate)
            if tx.queue and not first_played:
                tx.clock(tick/rate);first_played=True
            if ingress.first_fault and filter_at_fault is None:filter_at_fault=tx.filtered
        elif event and event[0]=='wire':
            assert s.enabled('wire');wire.append(event[1])
    assert wire==[913,17,801] and not receiver.fault
    assert ingress.first_fault and ingress.decoder.fault and s.fault['rf']
    assert tx.consumed==1 and tx.held==0 and not tx.queue
    assert abs(filter_at_fault)>0
    s.ready['rf']=True  # Readiness alone must not clear a latched session fault.
    assert not s.enabled('rf') and not tx.accept(.75)
    old_status=ingress.first_fault.copy()
    ingress.feed(0,64/rate);assert ingress.first_fault==old_status
    tx.advance(65/rate)
    expected=filter_at_fault*math.exp(-tx.pole*(65/rate-old_status['time_s']))
    assert abs(tx.filtered-expected)<1e-14
    rows.append(dict(mode=mode,fault=old_status,wired_words_preserved=len(wire),
        retained_filter_at_fault=filter_at_fault.real,accounting=tx.accounting()))
files=[Path(__file__),*[Path(__file__).with_name(n) for n in ('burst_codec.py','rf_tx_state.py','session.py','chip_model.py')],P/'verification/stream_codec.py',P/'verification/transport_model.py']
report=dict(cases=rows,status='passed',complete_architecture=False,
    source_hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
    limitations=['Fault-to-DAC mute is instantaneous in this behavioral adapter; physical CDC latency is not modeled.',
      'First-fault snapshot is abstract management state, not serialized host notification.',
      'One sample is intentionally consumed before late corruption; streaming delivery is not quarantined.',
      'Recovery and fresh descriptors still require an upstream drain/epoch contract.'])
(P/'evidence/connected-burst-fault.json').write_text(json.dumps(report,indent=2)+'\n')
print('Both framed RF fault cases preserve wired traffic, latch RF fault and retain analog decay')
