"""Independent Python codec drives cycle-by-cycle RTL expectations."""
from pathlib import Path
import itertools
import json
from stream_codec import Receiver,encode,metadata,slots
out=Path('/out');count=0;cases=0
f=(out/'stream-vectors.txt').open('w')
def row(mode,reset,word,wr,qr,fault,kind,value):
    global count
    f.write(' '.join(f'{v:x}' for v in (mode,reset,word,wr,qr,fault,kind,value))+'\n');count+=1
def reset(mode):
    global cases
    row(mode,1,0,1,1,0,0,0);cases+=1
    return Receiver(mode)
def send(rx,mode,word,wr=1,qr=1):
    event=None
    try:event=rx.feed(word)
    except ValueError:pass
    if event and ((event[0]=='wire' and not wr) or (event[0]=='iq' and not qr)):
        rx.fault=True;event=None
    kind=0;value=0
    if event:
        kind={'wire':1,'iq':2,'command':3}[event[0]]
        value=(event[1][0]<<8)|event[1][1] if kind==3 else event[1]
    row(mode,0,word,wr,qr,int(rx.fault),kind,value)
for mode in (0,1):
    rx=reset(mode);seq=0
    for wc in range(slots(mode).count('wire')+1):
        for qc in range(slots(mode).count('iq')+1):
            frame=encode(mode,[(i*37+seq)%1024 for i in range(wc)],[(i*53+seq+511)%1024 for i in range(qc)],seq%64,seq%3,0 if seq%3==0 else seq%2)
            for w in frame:send(rx,mode,w)
            seq+=1
    # Payload corruption remains visible as data, not a link fault.
    rx=reset(mode);frame=encode(mode,[123],[456],0);frame[5]^=1
    for w in frame:send(rx,mode,w)
    # Refuse the final allocated word: a fault must suppress that output.
    rx=reset(mode);frame=encode(mode,[1]*slots(mode).count('wire'),[2]*slots(mode).count('iq'),0)
    for i,w in enumerate(frame):send(rx,mode,w,wr=int(i!=63))
    for _ in range(3):send(rx,mode,0)
    rx=reset(mode);first_iq=slots(mode).index('iq')
    for i,w in enumerate(frame):send(rx,mode,w,qr=int(i!=first_iq))
    for _ in range(3):send(rx,mode,0)
base=sum(w<<(10*i) for i,w in enumerate(metadata(17,6,0,1,1)))
for n in (1,2,3):
    for bits in itertools.combinations(range(50),n):
        rx=reset(1);bad=base^sum(1<<i for i in bits)
        for i in range(5):send(rx,1,(bad>>(10*i))&1023)
        send(rx,1,999);send(rx,1,777)
for fields in [(53,0,0,0,0),(0,8,0,0,0),(0,0,1,0,0),(0,0,0,3,0),(0,0,0,2,2)]:
    rx=reset(1)
    for w in metadata(*fields):send(rx,1,w)
    send(rx,1,888)
f.close()
(out/'stream-vectors.json').write_text(json.dumps({'cycles':count,'reset_cases':cases,'metadata_error_patterns':20875,'legal_count_pairs':1308},indent=2)+'\n')
print(f'Generated {count} checked cycles across {cases} reset cases')
