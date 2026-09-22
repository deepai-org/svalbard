"""Ingress and staged-word event screen using existing v2 slot schedule."""
import hashlib,json,sys
from fractions import Fraction
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'verification'))
from stream_codec import slots

def simulate(plan,source,rate,bits,word_rate,phase,frames=512):
    period=Fraction(bits)*word_rate/rate;arrival=phase*period
    queue=produced=sent=peak=0;prepared=active=0
    for tick in range(frames*len(plan)):
        while arrival<=tick:
            queue+=bits;produced+=bits;arrival+=period
        peak=max(peak,queue)
        if tick%len(plan)==0:
            assert active==0
            active=prepared
            prepared=min(plan.count(source),queue//10)
            queue-=10*prepared
        if plan[tick%len(plan)]==source and active:
            active-=1;sent+=10
        assert produced==queue+10*(prepared+active)+sent
    return dict(peak_ingress_bits=peak,produced_bits=produced,sent_bits=sent,
        pending_bits=queue+10*(prepared+active),planning_1024bit_ingress_exceeded=peak>1024)

path=P/'spec/contract.json';c=json.loads(path.read_text());rows=[]
for mode_index,mode in enumerate(c['modes']):
    plan=slots(mode_index);p=c['transport']['profiles'][mode['profile']]
    word_rate=Fraction(p['clock_hz']*p['edges'])*Fraction(9999,10000)
    for source in mode['sources']:
        rate=Fraction(source['rate_bps'])*Fraction(10001,10000)
        for phase in [Fraction(0),Fraction(1,4),Fraction(1,2),Fraction(3,4)]:
            rows.append(dict(mode=mode['id'],source=source['id'],phase=float(phase),
                **simulate(plan,source['id'],rate,source['sample_bits'],word_rate,phase)))
# Analytic conservation control: one 10-bit burst/tick, snapshot every4 ticks.
a=simulate(['x']*4,'x',Fraction(10),10,Fraction(1),Fraction(0),frames=4)
assert a['produced_bits']==160 and a['peak_ingress_bits']==40
report=dict(status='finite_ingress_screen_not_complete_transport',cases=rows,
    source_hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
    [path,Path(__file__),P/'verification/stream_codec.py',P/'verification/transport_model.py']},
    limitations=['Uses actual v2 slot plans, ideal valid-word handling and two staging banks.',
    '512 frames and four phases are finite cases, not exhaustive bounds.',
    'No receiver egress, payload ordering, CDC, host stalls or electrical timing.',
    '1024-bit threshold is a planning allocation, not verified RTL depth.',
    'Same per-direction rates; opposite directions do not share a queue.'])
(P/'evidence/fast-queue-screen.json').write_text(json.dumps(report,indent=2)+'\n')
print(len(rows),'cases; maximum ingress',max(r['peak_ingress_bits'] for r in rows),'bits')
