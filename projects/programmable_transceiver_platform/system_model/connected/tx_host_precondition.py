"""Diagnostic host activity prelude: real zero-allocation frames, no RF payload."""
import random,math
from chip_model import encode

def conditioner(kind,delay_s=0.):
 if not math.isfinite(delay_s) or delay_s<0:raise ValueError('Invalid prelude delay')
 if kind is None:
  if delay_s:raise ValueError('Delay requires an explicit prelude')
  return None
 if kind not in ('quiet','switching'):raise ValueError('Unknown host preconditioner')
 def prepare(c,mode):
    begin=c.time;end=begin+20e-6+delay_s
    if kind=='quiet':c.advance(end);return
    rate=250e6 if mode==0 else 312.5e6
    # 64 complete frames wrap sequence back to zero. Unallocated payload words
    # are ignored by the actual decoder but still exercise the physical bus model.
    start=end-4096/rate;c.advance(start)
    assert c.state=='active' and c.receiver.pos==0 and c.receiver.sequence==0
    before=(c.tx.accepted,c.wire_consumed,c.tx.consumed)
    if hasattr(c,'host_activation'):c.execute_management('host_train_start',0,c.time)
    c.tx_observe_enabled=False;rng=random.Random(1941)
    for frame in range(64):
        words=encode(mode,[],[],frame)
        words[5:]=[rng.randrange(1024) for _ in words[5:]]
        for i,word in enumerate(words):
            t=end if frame==63 and i==63 else start+(frame*64+i+1)/rate
            c.feed(word,c.epoch,t)
            assert c.state=='active'
    c.tx_observe_enabled=True
    assert c.time==end and c.receiver.pos==0 and c.receiver.sequence==0
    assert before==(c.tx.accepted,c.wire_consumed,c.tx.consumed)
 return prepare
