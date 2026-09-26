"""Aligned parallel RX candidate: vector slot ranks, not a clocked implementation."""
from stream_codec import slots,unprotect,GUARD
class BlockReceiver:
 def __init__(self,mode,width,*,owner=None):
  assert width in (2,4,8)
  self.width=width;self.plan=slots(mode,owner=owner);self.pos=0;self.seq=0;self.header=0;self.left={};self.fault=False
 def feed(self,words):
  if self.fault:raise ValueError('sticky fault')
  if len(words)!=self.width:raise ValueError('block width')
  start=self.pos;end=start+self.width;events=[]
  try:
   if any(not isinstance(w,int) or not 0<=w<1024 for w in words):raise ValueError('word range')
   if start==0:self.header=0
   for pos in range(start,min(end,4)):self.header|=words[pos-start]<<(10*pos)
   if start<=4<end:
    if words[4-start]!=GUARD:raise ValueError('guard')
    h=unprotect(self.header);wc,qc,seq,op,arg=h&63,(h>>6)&63,(h>>12)&63,(h>>18)&15,h>>22
    if seq!=self.seq or wc>self.plan.count('wire') or qc>self.plan.count('iq'):raise ValueError('metadata')
    if not ((op==0 and arg==0) or (op in (1,2) and arg in (0,1))):raise ValueError('command')
    self.left={'wire':wc,'iq':qc};events.append((4-start,('command',(op,arg))))
   # Rank each source's slots within the vector against the pre-block remaining count.
   for source in ['wire','iq']:
    lanes=[pos-start for pos in range(max(start,5),end) if self.plan[pos]==source]
    valid=lanes[:min(len(lanes),self.left.get(source,0))]
    events.extend((lane,(source,words[lane])) for lane in valid)
    if source in self.left:self.left[source]-=len(valid)
   self.pos=end%64
   if self.pos==0:self.seq=(self.seq+1)%64
   return sorted(events)
  except ValueError:
   self.fault=True;raise

class BlockFIFO:
 """Eight fixed-block CDC entries; ideal two-edge pointer synchronizers.

 step() applies simultaneous edges from a common pre-edge snapshot. Pointer
 values count blocks, never words. Physical metastability/skew is not modeled.
 """
 def __init__(self):self.reset()
 def reset(self):
  self.wr_release=self.rd_release=0
  self.wb=self.rb=0;self.rs=[0,0];self.ws=[0,0]
  self.memory=[None]*8;self.fault=False
 def status(self):
  return dict(wr_ready=self.wr_release==2 and (self.wb-self.rs[1])%16!=8,
              rd_valid=self.rd_release==2 and self.rb!=self.ws[1],
              words=self.memory[self.rb%8],fault=self.fault)
 def _valid_entry(self,words):
  if not isinstance(words,tuple) or any(type(w) is not int or not 0<=w<1024 for w in words):
   raise ValueError('Block words must be a tuple of ten-bit integers')
  return 1<=len(words)<=8
 def step(self,*,wr_edge=False,rd_edge=False,words=None,pop=False,reset=False):
  if reset:
   self.reset();return dict(written=False,read=None)
  valid=words is not None and self._valid_entry(words)
  old=self.status();wb,rb=self.wb,self.rb
  written=wr_edge and words is not None and old['wr_ready'] and valid
  read=old['words'] if rd_edge and pop and old['rd_valid'] else None
  if wr_edge:
   if self.wr_release==2:
    self.rs=[rb,self.rs[0]]
    if words is not None and old['wr_ready'] and not valid:self.fault=True
    if written:self.memory[wb%8]=words;self.wb=(wb+1)%16
   self.wr_release=min(2,self.wr_release+1)
  if rd_edge:
   if self.rd_release==2:
    self.ws=[wb,self.ws[0]]
    if read is not None:self.rb=(rb+1)%16
   self.rd_release=min(2,self.rd_release+1)
  return dict(written=bool(written),read=read)


class RecordBlockFIFO(BlockFIFO):
 """Same eight-entry CDC, proposed 84-bit raw data/event interpretation.

 Tags 1..8 retain packed ten-bit words. Tag 9 carries an opaque event and
 optional preceding partial word. Existing RTL does not implement tag 9.
 """
 def _valid_entry(self,words):
  from bit_event_codec import unpack_record_block
  unpack_record_block(words)
  return True
