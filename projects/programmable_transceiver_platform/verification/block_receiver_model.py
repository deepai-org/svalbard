"""Aligned parallel RX candidate: vector slot ranks, not a clocked implementation."""
from stream_codec import slots,unprotect,GUARD
class BlockReceiver:
 def __init__(self,mode,width):
  assert width in (2,4,8)
  self.width=width;self.plan=slots(mode);self.pos=0;self.seq=0;self.header=0;self.left={};self.fault=False
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
