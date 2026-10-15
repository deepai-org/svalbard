"""Finite record-aware two-bank scheduling screen, not canonical integration."""
import hashlib,json,sys
from pathlib import Path
from collections import deque
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/connected'))
from bit_event_stream import BitEventStream
from bit_event_codec import snapshot_records,StreamingRecordReceiver


def run(length,phase,bit_period=1/480e6,word_hz=250e6):
    stream=BitEventStream(16);rx=StreamingRecordReceiver();pending=deque()
    bit_count=0;word_count=0;sequence=0;high_water=0;observed=[];event_times=[]
    # Repeated finite bursts; caller supplies generic boundaries, not USB EOP.
    bits=[(i*7+i//5)%2 for i in range(length)]
    source=[]
    for burst in range(40):
        start=phase+burst*(length+8)*bit_period
        source.extend((start+(i+1)*bit_period,'bit',b) for i,b in enumerate(bits))
        source.append((start+(length+1)*bit_period,'event',burst))
    index=0;clock=1/word_hz
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
    return dict(length_bits=length,phase_s=phase,word_hz=word_hz,high_water_records=high_water,
                maximum_event_latency_s=max(latencies),bits=bit_count)

def reply(receive_latency,phase,word_hz=312.5e6,read_phase=0.,fpga_s=40e-9):
    """Generic 23-bit reply through framed records, commit, CDC and playback."""
    import math
    from bit_event_codec import encode_records,pack_record_block,unpack_record_block
    from block_receiver_model import RecordBlockFIFO
    from bit_event_stream import RawBurstPlayback
    period=8/word_hz;origin=phase*period
    ready=receive_latency+fpga_s  # Assigned FPGA decision budget.
    snapshot=origin+math.ceil((ready-origin)/period)*period
    records=[('data',341,10,ready),('data',682,10,ready),('data',5,3,ready),('event',7,0,ready)]
    frame=encode_records(records,0);decoder=StreamingRecordReceiver();decoded=[]
    for word in frame:decoded.extend(decoder.feed(word))
    # Existing 84-bit format cannot combine whole words with a partial boundary.
    blocks=[pack_record_block(decoded[:2]),pack_record_block(decoded[2:])]
    collected=snapshot+period+7/word_hz
    commit=collected+16/word_hz
    fifo=RecordBlockFIFO();fifo.step(wr_edge=True,rd_edge=True);fifo.step(wr_edge=True,rd_edge=True)
    events={}
    for i,block in enumerate(blocks):events.setdefault(commit+i*period,{})['word']=block
    for i in range(math.ceil((commit+300e-9)/period)+1):events.setdefault((i+read_phase)*period,{})['read']=True
    bit_period=1/480e6
    for i in range(math.ceil((commit+300e-9)/bit_period)+1):events.setdefault((i+.99)*bit_period,{})['tick']=True
    playback=RawBurstPlayback();emitted=[];start=None
    for time,event in sorted(events.items()):
        # Consumer precedes same-time admission, matching conservative ownership.
        if event.get('tick'):
            value=playback.tick()
            if value is not None:
                if start is None:start=time
                emitted.append(value)
        result=fifo.step(wr_edge='word' in event,words=event.get('word'),
                         rd_edge=event.get('read',False),pop=event.get('read',False) and fifo.status()['rd_valid'])
        if result['written'] is False and 'word' in event:raise AssertionError('Reply block refused')
        if result['read'] is not None:playback.enqueue(unpack_record_block(result['read']))
    expected=[(341>>i)&1 for i in range(10)]+[(682>>i)&1 for i in range(10)]+[1,0,1]
    assert emitted==expected and playback.completed==1 and not playback.fault
    return dict(host_phase=phase,read_phase=read_phase,fpga_processing_s=fpga_s,receive_latency_s=receive_latency,reply_bits=len(emitted),
                commit_time_s=commit,playback_start_s=start,
                start_with_assigned_analog_allowance_s=start+34e-9,
                within_400ns_model_budget=start+34e-9<=400e-9,
                ordered_reply=True,record_blocks=len(blocks))


def reply_bound(word_hz=312.5e6):
    """Conditional all-phase sum; an event must fit the next receive snapshot."""
    frame=8/word_hz
    terms=dict(receive_snapshot_wait_s=frame,receive_bank_wait_s=frame,
        receive_frame_delivery_s=7/word_hz,fpga_capture_visibility_s=3/word_hz,
        fpga_decision_s=40e-9,reply_snapshot_wait_s=frame,reply_bank_wait_s=frame,
        reply_collection_s=7/word_hz,reply_commit_s=2*frame,
        h2d_visibility_s=3*frame,serializer_wait_s=1/480e6,analog_allowance_s=34e-9)
    total=sum(terms.values())
    return dict(terms=terms,bound_s=total,remaining_400ns_margin_s=400e-9-total,
        assumptions='Each direction has no older queued frame delaying this event/response. Event and preceding partial data fit one snapshot. FPGA response fits one eight-word frame. Two CDC record writes occur one block period apart, no stalls, reset released. Clocks remain at assigned rates. Visibility and analog allowances require physical implementation proof. Independent phase waits are summed; no favorable clock phase assumed.')


def main():
    rows=[]
    for rate in (250e6,312.5e6):
        for length in (1,9,10,11,23,240,4096):
            for fraction in (0.,.015625,.121875,.496875,.996875):
                phase=fraction*8/rate
                try:rows.append(dict(run(length,phase,word_hz=rate),delivered=True))
                except ValueError as error:
                    if 'overflow' not in str(error):raise
                    rows.append(dict(length_bits=length,phase_s=phase,word_hz=rate,delivered=False,fault=str(error)))
    assert all(r['delivered']==(r['length_bits']!=1) for r in rows)
    for rate in (250e6,312.5e6):
        try:run(4096,0,bit_period=1/2e9,word_hz=rate)
        except ValueError as error:assert 'overflow' in str(error)
        else:raise AssertionError('Overloaded producer did not fault')
    files=[Path(__file__),P/'verification/bit_event_codec.py',P/'verification/stream_codec.py',P/'verification/transport_model.py',P/'system_model/connected/bit_event_stream.py',P/'verification/block_receiver_model.py']
    latency=max(r['maximum_event_latency_s'] for r in rows if r['word_hz']==312.5e6 and r['delivered'])
    latency+=3/312.5e6  # Explicit assigned FPGA-side capture visibility.
    bound=reply_bound()
    reply_cases=[reply(latency,phase,read_phase=read_phase) for phase in (0.,.001,.25,.5,.999) for read_phase in (0.,.001,.25,.5,.999)]
    assert all(r['within_400ns_model_budget'] and r['start_with_assigned_analog_allowance_s']<=bound['bound_s'] for r in reply_cases)
    slow=reply(latency,0.,fpga_s=200e-9)
    assert not slow['within_400ns_model_budget']
    report=dict(status='screen_completed',cases=rows,reply_cases=reply_cases,conditional_phase_bound=bound,slow_fpga_control=slow,overload_rejected=True,full_chip_closure=False,
     source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
     limitations=['Prescribed 480 Mb/s samples; selected 312.5 Mword/s and comparison 250 Mword/s host. No CDR, CDC or electrical capture.',
     'Forty bursts per case, eight-bit-time gap; boundaries are external generic fixtures, not USB packet conformance.',
     'Two frame banks modeled by exact scheduling; no canonical scheduler or RTL integration.',
     'Reply cases chain the maximum observed receive latency plus assigned three-word FPGA visibility to a 23-bit generic response, assigned 40 ns FPGA decision, actual record coding, two-block commit delay, ideal pointer CDC, and playback. Assigned 34 ns analog allowance, no physical pad waveform, acquired clocks, USB EOP/packet decoding or full-chip coupling. Two 84-bit blocks required by boundary format; clocks and reset release prescribed.'])
    (P/'evidence/bit-event-schedule.json').write_text(json.dumps(report,indent=2)+'\n')
    for rate in (250e6,312.5e6):
        group=[r for r in rows if r['word_hz']==rate]
        print(rate,'Delivered',sum(r['delivered'] for r in group),'of',len(group),'max event latency',max(r.get('maximum_event_latency_s',0) for r in group))


if __name__=='__main__':main()
