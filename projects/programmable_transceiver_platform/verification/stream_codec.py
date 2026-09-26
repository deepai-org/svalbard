"""Candidate aligned streaming transport; metadata protected, payload unprotected."""
from transport_model import schedule

PARITY=(1,2,4,8,16,32)
DATA=tuple(p for p in range(1,37) if p not in PARITY)
TAG=0b101
GUARD=0x2d3

def protect(value):
    if not 0<=value<1<<30:raise ValueError('metadata width')
    code=sum(((value>>i)&1)<<(p-1) for i,p in enumerate(DATA))
    for parity in PARITY:
        bit=sum((code>>(p-1))&1 for p in range(1,37) if p&parity)&1
        code|=bit<<(parity-1)
    code|=(code.bit_count()&1)<<36
    return code|(TAG<<37)

def unprotect(code):
    if not 0<=code<1<<40 or code>>37!=TAG:raise ValueError('metadata tag')
    body=code&((1<<37)-1)
    syndrome=0
    for p in range(1,37):
        if body>>(p-1)&1:syndrome^=p
    if syndrome or body.bit_count()&1:raise ValueError('metadata parity')
    return sum(((body>>(p-1))&1)<<i for i,p in enumerate(DATA))

def slots(mode,frame_words=64,*,owner=None):
    if mode not in (0,1):raise ValueError('mode')
    if owner not in (None,'wire','iq'):raise ValueError('owner')
    if owner=='iq' and frame_words!=64:raise ValueError('Short framing requires wired ownership')
    if owner is not None and frame_words==64:
        return schedule({owner:59},control_slots=(0,1,2,3,4))
    if frame_words==8:return schedule({'wire':3},frame_words=8,control_slots=(0,1,2,3,4))
    if frame_words!=64:raise ValueError('Unsupported frame geometry')
    return schedule({'wire':52,'iq':7} if mode else {'wire':33,'iq':25},control_slots=(0,1,2,3,4))

def metadata(wc,qc,seq,op=0,arg=0):
    if not (0<=wc<64 and 0<=qc<64 and 0<=seq<64 and 0<=op<16 and 0<=arg<256):raise ValueError('field range')
    c=protect(wc|(qc<<6)|(seq<<12)|(op<<18)|(arg<<22))
    return [(c>>(10*i))&1023 for i in range(4)]+[GUARD]

def encode(mode,wire,iq,seq,op=0,arg=0,*,frame_words=64,owner=None):
    plan=slots(mode,frame_words,owner=owner)
    if len(wire)>plan.count('wire') or len(iq)>plan.count('iq'):raise ValueError('quota')
    if any(not 0<=w<1024 for w in [*wire,*iq]):raise ValueError('word range')
    result=metadata(len(wire),len(iq),seq,op,arg)
    queues={'wire':iter(wire),'iq':iter(iq)}
    result.extend(next(queues[s],0) if s in queues else 0 for s in plan[5:])
    return result

def discontinuity_suffix(next_word_index,current_header,frame_words=64):
    """Candidate running-clock abort: finish current frame, then fault header.

    Tail payload is invalid filler; the FPGA must hold candidates through the
    bounded fault-indication delay. This never drains additional source data.
    Opcode 3/argument 1 is provisional and intentionally rejected by legacy RX.
    """
    if type(next_word_index) is not int or next_word_index<0 or frame_words!=64:
        raise ValueError('Abort candidate requires a long aligned frame')
    frame,position=divmod(next_word_index,frame_words)
    if position and (len(current_header)!=5 or current_header[4]!=GUARD):
        raise ValueError('Current protected header required')
    tail=([current_header[i] if i<5 else 0 for i in range(position,frame_words)]
          if position else [])
    sequence=(frame+int(bool(position)))%64
    return tail+metadata(0,0,sequence,op=3,arg=1)

class Receiver:
    """One input word at a time. No payload quarantine; any error latches fault."""
    def __init__(self,mode,*,frame_words=64,owner=None,fault_status=False):
        if type(fault_status) is not bool:raise ValueError('Boolean fault status selection')
        self.fault_status=fault_status
        self.plan=slots(mode,frame_words,owner=owner)
        self.reset()
    def reset(self):
        self.pos=0;self.sequence=0;self.header=0;self.fault=False;self.left={}
    def feed(self,word):
        if self.fault:raise ValueError('receiver fault requires reset/retraining')
        try:
            if not isinstance(word,int) or not 0<=word<1024:raise ValueError('word range')
            event=None
            if self.pos<4:
                if self.pos==0:self.header=0
                self.header|=word<<(10*self.pos)
            elif self.pos==4:
                if word!=GUARD:raise ValueError('metadata guard')
                h=unprotect(self.header)
                wc,qc,seq,op,arg=h&63,(h>>6)&63,(h>>12)&63,(h>>18)&15,h>>22
                if seq!=self.sequence:raise ValueError('sequence')
                if wc>self.plan.count('wire') or qc>self.plan.count('iq'):raise ValueError('quota')
                if self.fault_status and op==3 and arg==1 and wc==qc==0:
                    raise ValueError('Remote stream discontinuity')
                if not ((op==0 and arg==0) or (op in (1,2) and arg in (0,1))):raise ValueError('command')
                self.left={'wire':wc,'iq':qc}
                event=('command',(op,arg))
            else:
                source=self.plan[self.pos]
                if self.left.get(source,0):
                    self.left[source]-=1;event=(source,word)
            self.pos=(self.pos+1)%len(self.plan)
            if self.pos==0:self.sequence=(self.sequence+1)%64
            return event
        except ValueError:
            self.fault=True
            raise


class PacketHoldback:
    """External FPGA completed-packet queue, with explicit finite word capacity.

    The caller supplies receiver-validated packets and a justified worst-case
    fault-notification delay from the final received word. This queue does not
    recognize packets, estimate clock health, or know transmitted payload.
    Equal-time faults win: release requires time strictly beyond the deadline.
    """
    def __init__(self,delay_s,capacity_words):
        import math
        from collections import deque
        if not math.isfinite(delay_s) or delay_s<0 or type(capacity_words) is not int or capacity_words<1:
            raise ValueError('Finite delay and positive packet capacity required')
        self.delay=delay_s;self.capacity=capacity_words;self.pending=deque()
        self.words=0;self.high_water=0;self.time=0.;self.fault=None

    def _time(self,time):
        import math
        if not math.isfinite(time) or time<self.time:raise ValueError('Monotonic packet observer time')
        self.time=time

    def invalidate(self,time,reason):
        self._time(time)
        discarded=self.words
        self.pending.clear();self.words=0;self.fault=str(reason)
        return discarded

    def submit(self,packet,time):
        self._time(time)
        if self.fault is not None:raise ValueError('Faulted packet observer requires coordinated restart')
        packet=tuple(packet)
        if not packet or any(type(word) is not int or not 0<=word<1024 for word in packet):
            raise ValueError('Nonempty ten-bit-word packet required')
        if self.words+len(packet)>self.capacity:
            self.invalidate(time,'Packet holdback capacity exceeded')
            raise ValueError(self.fault)
        self.pending.append((time+self.delay,packet));self.words+=len(packet)
        self.high_water=max(self.high_water,self.words)

    def advance(self,time):
        self._time(time)
        released=[]
        if self.fault is not None:return released
        while self.pending and time>self.pending[0][0]:
            _,packet=self.pending.popleft();self.words-=len(packet);released.append(packet)
        return released
