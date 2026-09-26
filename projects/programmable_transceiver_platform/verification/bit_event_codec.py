"""Generic raw-bit/event framing using existing protected metadata.

Eight-word mode preserves the original boundary-at-end encoding. In 64-word
mode one event may occur anywhere among the data words, so an event need not
waste the rest of a frame. Explicit candidate interpretation, not existing RTL.
"""
from stream_codec import metadata,unprotect,GUARD

def encode_records(records,sequence,frame_words=8):
    if frame_words not in (8,64):raise ValueError('Frame geometry')
    records=list(records);data=[];event=None;position=0;valid=0
    pending=False
    for kind,value,count,_ in records:
        if kind=='data':
            if pending or type(count) is not int or not 1<=count<=10 or type(value) is not int or not 0<=value<1<<count:raise ValueError('Data width/boundary')
            data.append(value);pending=count<10;valid=count
        elif kind=='event':
            if event is not None or count!=0 or type(value) is not int or not 0<=value<256:raise ValueError('Event')
            event=value;position=len(data);event_bits=valid if position else 11;pending=False
        else:raise ValueError('Record kind')
    if len(data)>frame_words-5 or pending:raise ValueError('Capacity/boundary')
    if frame_words==8 and event is not None and records[-1][0]!='event':raise ValueError('Data after boundary')
    header=metadata(len(data),position if event is not None else 0,sequence,event_bits if event is not None else 0,event or 0)
    if frame_words==8:
        header=metadata(len(data),valid,sequence,3 if event is not None else 0,event or 0)
    return header+data+[0]*(frame_words-5-len(data))

def _header(code,sequence,frame_words):
    h=unprotect(code);wc,qc,seq,op,arg=h&63,(h>>6)&63,(h>>12)&63,(h>>18)&15,h>>22
    if seq!=sequence or wc>frame_words-5:raise ValueError('Count/sequence')
    if frame_words==8:
        if op not in (0,3) or (op==0 and arg):raise ValueError('Header')
        if (wc==0 and qc!=0) or (wc and not 1<=qc<=10) or (op==0 and wc and qc!=10):raise ValueError('Valid-bit count')
        return wc,wc,qc,arg if op==3 else None
    if op==0:
        if qc or arg:raise ValueError('Empty event')
        return wc,0,10,None
    if (op==11 and qc!=0) or (1<=op<=10 and not 1<=qc<=wc) or op>11:raise ValueError('Event location/count')
    return wc,qc,op,arg

class StreamingRecordReceiver:
    def __init__(self,frame_words=8):
        if frame_words not in (8,64):raise ValueError('Frame geometry')
        self.frame_words=frame_words;self.reset()

    def reset(self):
        self.position=self.sequence=self.header=self.count=0;self.event=None;self.fault=False
    def feed(self,word):
        if self.fault:raise ValueError('Receiver fault')
        try:
            if type(word) is not int or not 0<=word<1024:raise ValueError('Word width')
            out=[];p=self.position
            if p<4:
                if p==0:self.header=0
                self.header|=word<<(10*p)
            elif p==4:
                if word!=GUARD:raise ValueError('Guard')
                self.count,self.event_at,self.event_bits,self.event=_header(self.header,self.sequence,self.frame_words)
                if self.event is not None and self.event_at==0:out.append(('event',self.event,0));self.event=None
            elif p-5<self.count:
                index=p-4;n=self.event_bits if self.event is not None and index==self.event_at else 10
                if word>=1<<n:raise ValueError('Partial padding')
                out.append(('data',word,n))
                if self.event is not None and index==self.event_at:out.append(('event',self.event,0));self.event=None
            self.position=(p+1)%self.frame_words
            if self.position==0:self.sequence=(self.sequence+1)%64
            return out
        except ValueError:self.fault=True;raise
    def finish(self):
        if self.fault or self.position:raise ValueError('Incomplete/faulted')

def decode_records(frame,sequence):
    if len(frame) not in (8,64):raise ValueError('Frame width')
    # Independent block oracle deliberately does not call streaming decoder.
    if any(type(w) is not int or not 0<=w<1024 for w in frame):raise ValueError('Word width')
    if frame[4]!=GUARD:raise ValueError('Guard')
    wc,pos,bits,event=_header(sum(frame[i]<<(10*i) for i in range(4)),sequence,len(frame))
    out=[]
    if event is not None and pos==0:out.append(('event',event,0))
    for i,word in enumerate(frame[5:5+wc],1):
        n=bits if event is not None and i==pos else 10
        if word>=1<<n:raise ValueError('Partial padding')
        out.append(('data',word,n))
        if event is not None and i==pos:out.append(('event',event,0))
    return out

def snapshot_records(stream,sequence,frame_words=8):
    if stream.fault:raise ValueError('Source fault')
    selected=[];count=0;event=False
    for record in stream.records:
        if record[0]=='event':
            if event:break
            selected.append(record);event=True
            if frame_words==8:break
        else:
            if count==frame_words-5 or (event and record[2]<10):break
            selected.append(record);count+=1
    frame=encode_records(selected,sequence,frame_words)
    for _ in selected:stream.pop()
    return frame


# Candidate interpretation of existing 80 data + 4 count bits; tag 9 is new.
def pack_record_block(records):
 records=list(records)
 if not records:raise ValueError('Empty block')
 if all(k=='data' and n==10 for k,v,n in records):
  if len(records)>8:raise ValueError('Capacity')
  if any(type(v) is not int or not 0<=v<1024 for k,v,n in records):raise ValueError('Data')
  return (len(records)<<80)|sum(v<<(10*i) for i,(k,v,n) in enumerate(records))
 if len(records)==1 and records[0][0]=='event':partial=0;count=0;event=records[0]
 elif len(records)==2 and records[0][0]=='data' and records[1][0]=='event':
  _,partial,count=records[0];event=records[1]
 else:raise ValueError('Boundary')
 if type(count) is not int or not 0<=count<=9 or type(partial) is not int or not 0<=partial<1<<count:raise ValueError('Partial')
 if event[2]!=0 or type(event[1]) is not int or not 0<=event[1]<256:raise ValueError('Event')
 return (9<<80)|event[1]|(count<<8)|(partial<<12)
def unpack_record_block(word):
 if type(word) is not int or not 0<=word<1<<84:raise ValueError('Width')
 tag=word>>80;payload=word&((1<<80)-1)
 if 1<=tag<=8:
  if payload>>(10*tag):raise ValueError('Padding')
  return [('data',(payload>>(10*i))&1023,10) for i in range(tag)]
 if tag!=9 or payload>>22:raise ValueError('Tag/padding')
 count=(payload>>8)&15;partial=(payload>>12)&1023
 if count>9 or partial>=1<<count:raise ValueError('Partial')
 return ([('data',partial,count)] if count else [])+[('event',payload&255,0)]


class TrainedRecordReceiver:
    """External FPGA word receiver with an independently timed clock watchdog.

    Uses the existing eight-word training sequence. arm() is an explicit
    coordinated restart, not automatic resynchronization of a live stream.
    A coincident word wins the watchdog deadline when feed() is called first.
    Physical word alignment and source-side flushing remain caller obligations.
    """
    training=(0x3a5,0x05a,0x2d3,0x12c,0x369,0x096,0x21e,0x1e1)

    def __init__(self,frame_words=64,timeout_s=100e-9,startup_timeout_s=None,decoder=None):
        import math
        if not math.isfinite(timeout_s) or timeout_s<=0:raise ValueError('Positive watchdog timeout')
        if startup_timeout_s is None:startup_timeout_s=timeout_s
        if not math.isfinite(startup_timeout_s) or startup_timeout_s<=0:raise ValueError('Positive startup timeout')
        self.startup_timeout=startup_timeout_s
        self.decoder=StreamingRecordReceiver(frame_words) if decoder is None else decoder;self.timeout=timeout_s
        self.time=0.;self.arm(0.)

    def _check_time(self,time):
        import math
        if not math.isfinite(time) or time<self.time:raise ValueError('Monotonic host time')

    def arm(self,time):
        self._check_time(time);self.time=self.armed=time;self.last_edge=None
        self.decoder.reset();self.matched=self.edges=0;self.locked=False;self.fault=None

    def _fail(self,reason):
        self.fault=reason;self.locked=False
        self.decoder.reset()  # Drop partial metadata/payload state, stay faulted.

    def deadline(self):
        return self.armed+self.startup_timeout if self.last_edge is None else self.last_edge+self.timeout

    def advance(self,time):
        self._check_time(time)
        if self.fault is None and time>=self.deadline():self._fail('Host clock timeout')
        self.time=time

    def feed(self,word,time):
        self._check_time(time)
        if self.fault is not None:raise ValueError(self.fault)
        if self.last_edge is not None and time<=self.last_edge:raise ValueError('Strictly increasing word edges')
        if time>self.deadline():
            self._fail('Host clock timeout');self.time=time;raise ValueError(self.fault)
        if type(word) is not int or not 0<=word<1024:
            self._fail('Word width');raise ValueError(self.fault)
        self.last_edge=self.time=time
        if not self.locked:
            self.edges+=1
            self.matched=self.matched+1 if word==self.training[self.matched] else int(word==self.training[0])
            if self.matched==len(self.training):self.locked=True
            elif self.edges>=1024:
                self._fail('Training timeout');raise ValueError(self.fault)
            return []
        try:
            event=self.decoder.feed(word)
            return event if isinstance(event,list) else ([] if event is None else [event])
        except ValueError as error:
            self._fail(str(error));raise


class ObservedClockPacer:
    """External FPGA pacing from a source rising-edge counter.

    Ideal Gray-counter visibility through two destination stages. Source counts
    wrap at 16 bits. A destination-clock watchdog faults on stalled observation;
    it does not replace chip-side clock loss detection if the FPGA itself stops.
    arm() requires coordinated stop/flush and a new epoch outside this object.
    """
    def __init__(self,bits_per_edge,burst_bits=60,timeout_cycles=16,max_step=8):
        from fractions import Fraction
        self.ratio=Fraction(str(bits_per_edge))
        if self.ratio<=0 or type(burst_bits) is not int or burst_bits<1:
            raise ValueError('Positive pacing ratio and burst capacity required')
        if type(timeout_cycles) is not int or timeout_cycles<3 or type(max_step) is not int or not 1<=max_step<32768:
            raise ValueError('Bounded watchdog and counter step required')
        self.burst=burst_bits;self.timeout=timeout_cycles;self.max_step=max_step
        self.arm()

    def arm(self):
        self.stages=[None,None];self.previous=None;self.stalled=0
        self.tokens=0;self.ready=False;self.fault=None

    def _fail(self,reason):
        self.fault=reason;self.ready=False;self.tokens=0

    def tick(self,source_count):
        if type(source_count) is not int or not 0<=source_count<65536:
            raise ValueError('16-bit source edge count required')
        if self.fault:return
        self.stages=[source_count,self.stages[0]]
        observed=self.stages[1]
        if observed is None:return
        if self.previous is None:
            self.previous=observed;return
        step=(observed-self.previous)%65536;self.previous=observed
        if step>self.max_step:
            self._fail('Reference counter discontinuity');return
        if not step:
            self.stalled+=1
            if self.stalled>=self.timeout:self._fail('Reference clock timeout')
            return
        self.stalled=0
        if not self.ready:
            self.ready=True;self.tokens=self.burst
        else:self.tokens=min(self.burst,self.tokens+step*self.ratio)

    def take(self,bits):
        if type(bits) is not int or bits<0:raise ValueError('Nonnegative integer bit cost')
        if self.fault or not self.ready or bits>self.tokens:return False
        self.tokens-=bits
        return True
