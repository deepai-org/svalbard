"""Finite record-aware two-bank scheduling screen, not canonical integration."""
import hashlib,json,sys
from pathlib import Path
from collections import deque
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/connected'))
from bit_event_stream import BitEventStream
from bit_event_codec import snapshot_records,StreamingRecordReceiver


def run(length,phase,bit_period=1/480e6):
    stream=BitEventStream(16);rx=StreamingRecordReceiver();pending=deque()
    bit_count=0;word_count=0;sequence=0;high_water=0;observed=[];event_times=[]
    # Repeated finite bursts; caller supplies generic boundaries, not USB EOP.
    bits=[(i*7+i//5)%2 for i in range(length)]
    source=[]
    for burst in range(40):
        start=phase+burst*(length+8)*bit_period
        source.extend((start+(i+1)*bit_period,'bit',b) for i,b in enumerate(bits))
        source.append((start+(length+1)*bit_period,'event',burst))
    index=0;clock=4e-9
    last=source[-1][0]+200e-9
    while word_count*clock<=last:
        now=word_count*clock
        # Source wins exact ties; all selected records must already exist.
        while index<len(source) and source[index][0]<=now:
            time,kind,value=source[index]
            if kind=='bit':stream.bit(value,time);bit_count+=1
            else:stream.event(value,time);event_times.append(time)
            high_water=max(high_water,len(stream.records));index+=1
        if word_count%8==0:
            frame=snapshot_records(stream,sequence);sequence=(sequence+1)%64
            # One bank is emitted while the next snapshot waits one frame.
            pending.extend((word_count+8+i,w) for i,w in enumerate(frame))
        if pending and pending[0][0]==word_count:
            _,word=pending.popleft()
            for record in rx.feed(word):observed.append((now,record))
        word_count+=1
    expected=[]
    for burst in range(40):
        expected.extend(('bit',b) for b in bits);expected.append(('event',burst))
    actual=[];latencies=[]
    for now,(kind,value,count) in observed:
        if kind=='data':actual.extend(('bit',(value>>i)&1) for i in range(count))
        else:actual.append(('event',value));latencies.append(now-event_times[value])
    assert actual==expected
    assert not stream.records and not stream.valid_bits
    return dict(length_bits=length,phase_s=phase,high_water_records=high_water,
                maximum_event_latency_s=max(latencies),bits=bit_count)

rows=[]
for length in (1,9,10,11,23,240,4096):
    for phase in (0,.5,3.9,15.9,31.9):
        try:rows.append(dict(run(length,phase*1e-9),delivered=True))
        except ValueError as error:
            if 'overflow' not in str(error):raise
            rows.append(dict(length_bits=length,phase_s=phase*1e-9,delivered=False,fault=str(error)))
assert all(r['delivered']==(r['length_bits']!=1) for r in rows)
# Explicit overload must fail, not silently discard data or events.
try:run(4096,0,bit_period=1/2e9)
except ValueError as error:assert 'overflow' in str(error)
else:raise AssertionError('Overloaded producer did not fault')
files=[Path(__file__),P/'verification/bit_event_codec.py',P/'verification/stream_codec.py',P/'verification/transport_model.py',P/'system_model/connected/bit_event_stream.py']
report=dict(status='screen_completed',cases=rows,overload_rejected=True,full_chip_closure=False,
 source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
 limitations=['Prescribed 480 Mb/s samples, 250 Mword/s host; no CDR, CDC or electrical capture.',
 'Forty bursts per case, eight-bit-time gap; boundaries are external generic fixtures, not USB packet conformance.',
 'Two frame banks modeled by exact scheduling; no canonical scheduler or RTL integration.'])
(P/'evidence/bit-event-schedule.json').write_text(json.dumps(report,indent=2)+'\n')
print('Delivered',sum(r['delivered'] for r in rows),'of',len(rows),'cases; max event latency',max(r.get('maximum_event_latency_s',0) for r in rows),'s')
