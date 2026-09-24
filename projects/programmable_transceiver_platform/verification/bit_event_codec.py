"""Candidate short-frame bit/event mapping using existing protected metadata.

Explicit alternate interpretation, not accepted by the existing chip Receiver.
Block decoder is a verification oracle, not a proposed extra frame buffer.
"""
from stream_codec import metadata,unprotect,GUARD


def encode_records(records,sequence):
    records=list(records)
    if len(records)>4:raise ValueError('At most three data records and one event')
    data=[];event=None;last_bits=0
    for index,record in enumerate(records):
        kind,value,count,_=record
        if kind=='data':
            if event is not None or last_bits not in (0,10):raise ValueError('Data after boundary')
            if type(count) is not int or not 1<=count<=10 or type(value) is not int or not 0<=value<1<<count:
                raise ValueError('Data width')
            data.append(value);last_bits=count
        elif kind=='event':
            if event is not None or index!=len(records)-1 or count!=0 or type(value) is not int or not 0<=value<256:
                raise ValueError('Event placement/width')
            event=value
        else:raise ValueError('Record kind')
    if len(data)>3 or (last_bits not in (0,10) and event is None):raise ValueError('Frame boundary')
    # Short raw mode has no IQ slots: qc carries final-word valid-bit count.
    header=metadata(len(data),last_bits,sequence,3 if event is not None else 0,event or 0)
    return header+data+[0]*(3-len(data))


def _decode_header(code,sequence):
    h=unprotect(code)
    wc,qc,seq,op,arg=h&63,(h>>6)&63,(h>>12)&63,(h>>18)&15,h>>22
    if seq!=sequence or wc>3 or op not in (0,3) or (op==0 and arg):raise ValueError('Header')
    if (wc==0 and qc!=0) or (wc and not 1<=qc<=10) or (op==0 and wc and qc!=10):raise ValueError('Valid-bit count')
    return wc,qc,arg if op==3 else None


def decode_records(frame,sequence):
    if len(frame)!=8 or any(type(w) is not int or not 0<=w<1024 for w in frame):raise ValueError('Frame width')
    if frame[4]!=GUARD:raise ValueError('Guard')
    wc,qc,event=_decode_header(sum(frame[i]<<(10*i) for i in range(4)),sequence)
    result=[]
    for i in range(wc):
        count=qc if i==wc-1 else 10
        if frame[5+i]>=1<<count:raise ValueError('Nonzero invalid data bits')
        result.append(('data',frame[5+i],count))
    if event is not None:result.append(('event',event,0))
    return result


class StreamingRecordReceiver:
    """One word per call; no payload frame buffer, event follows final data."""
    def __init__(self):self.reset()

    def reset(self):
        self.position=0;self.sequence=0;self.header=0;self.fault=False
        self.remaining=0;self.final_bits=0;self.event=None

    def feed(self,word):
        if self.fault:raise ValueError('Receiver fault requires reset/retraining')
        try:
            if type(word) is not int or not 0<=word<1024:raise ValueError('Word width')
            result=[]
            if self.position<4:
                if self.position==0:self.header=0
                self.header|=word<<(10*self.position)
            elif self.position==4:
                if word!=GUARD:raise ValueError('Guard')
                wc,qc,self.event=_decode_header(self.header,self.sequence)
                self.remaining=wc;self.final_bits=qc
                if not wc and self.event is not None:
                    result.append(('event',self.event,0));self.event=None
            elif self.remaining:
                count=self.final_bits if self.remaining==1 else 10
                if word>=1<<count:raise ValueError('Nonzero invalid data bits')
                result.append(('data',word,count));self.remaining-=1
                if not self.remaining and self.event is not None:
                    result.append(('event',self.event,0));self.event=None
            self.position=(self.position+1)%8
            if self.position==0:self.sequence=(self.sequence+1)%64
            return result
        except ValueError:
            self.fault=True
            raise

    def finish(self):
        if self.fault or self.position:raise ValueError('Faulted or incomplete frame')


def snapshot_records(stream,sequence):
    """Drain one short-frame quota, preserving atomic partial-word boundaries."""
    if stream.fault:raise ValueError('Source stream fault requires reset')
    selected=[];data_count=0
    for record in stream.records:
        if record[0]=='event':
            selected.append(record);break
        if data_count==3:break
        selected.append(record);data_count+=1
    # Encoding validates before removing records, so a malformed boundary
    # cannot partially consume the queue. An adjacent event fits in metadata.
    frame=encode_records(selected,sequence)
    for _ in selected:stream.pop()
    return frame
