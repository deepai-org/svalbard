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

def slots(mode):
    if mode not in (0,1):raise ValueError('mode')
    return schedule({'wire':52,'iq':7} if mode else {'wire':33,'iq':25},control_slots=(0,1,2,3,4))

def metadata(wc,qc,seq,op=0,arg=0):
    if not (0<=wc<64 and 0<=qc<64 and 0<=seq<64 and 0<=op<16 and 0<=arg<256):raise ValueError('field range')
    c=protect(wc|(qc<<6)|(seq<<12)|(op<<18)|(arg<<22))
    return [(c>>(10*i))&1023 for i in range(4)]+[GUARD]

def encode(mode,wire,iq,seq,op=0,arg=0):
    plan=slots(mode)
    if len(wire)>plan.count('wire') or len(iq)>plan.count('iq'):raise ValueError('quota')
    if any(not 0<=w<1024 for w in [*wire,*iq]):raise ValueError('word range')
    result=metadata(len(wire),len(iq),seq,op,arg)
    queues={'wire':iter(wire),'iq':iter(iq)}
    result.extend(next(queues[s],0) if s in queues else 0 for s in plan[5:])
    return result

class Receiver:
    """One input word at a time. No payload quarantine; any error latches fault."""
    def __init__(self,mode):
        self.plan=slots(mode)
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
                if not ((op==0 and arg==0) or (op in (1,2) and arg in (0,1))):raise ValueError('command')
                self.left={'wire':wc,'iq':qc}
                event=('command',(op,arg))
            else:
                source=self.plan[self.pos]
                if self.left.get(source,0):
                    self.left[source]-=1;event=(source,word)
            self.pos=(self.pos+1)%64
            if self.pos==0:self.sequence=(self.sequence+1)%64
            return event
        except ValueError:
            self.fault=True
            raise
