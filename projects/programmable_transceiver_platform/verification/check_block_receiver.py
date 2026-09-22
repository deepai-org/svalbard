import hashlib,json
from pathlib import Path
from block_receiver_model import BlockReceiver
from stream_codec import Receiver,encode,slots
p=Path(__file__).resolve().parents[1];cases=[]
for mode in [0,1]:
 plan=slots(mode)
 for width in [2,4,8]:
  wide=BlockReceiver(mode,width);scalar=Receiver(mode);frames=0;blocks=0;peak={'wire':0,'iq':0}
  for wc in range(plan.count('wire')+1):
   for qc in range(plan.count('iq')+1):
    words=encode(mode,[(i*37+frames)%1024 for i in range(wc)],[(i*51+frames)%1024 for i in range(qc)],frames%64,frames%3,0)
    for start in range(0,64,width):
     expected=[]
     for lane,word in enumerate(words[start:start+width]):
      event=scalar.feed(word)
      if event:expected.append((lane,event))
     actual=wide.feed(words[start:start+width]);assert actual==expected
     for source in peak:peak[source]=max(peak[source],sum(e[0]==source for lane,e in actual))
     blocks+=1
    frames+=1
  for bit in range(50):
   bad=encode(mode,[1]*plan.count('wire'),[2]*plan.count('iq'),0);bad[bit//10]^=1<<(bit%10)
   rx=BlockReceiver(mode,width);effects=[]
   try:
    for start in range(0,64,width):effects+=rx.feed(bad[start:start+width])
   except ValueError:pass
   else:raise AssertionError('corrupt header accepted')
   assert rx.fault and not effects
   try:rx.feed([0]*width)
   except ValueError:pass
   else:raise AssertionError('fault not sticky')
  cases.append({'mode':mode,'words_per_block':width,'frames':frames,'blocks':blocks,'peak_payload_words_per_block':peak,
   'core_clock_mhz':(312.5 if mode else 250)/width,'block_period_ns':(3.2 if mode else 4)*width,
   'max_collection_delay_ns':(width-1)*(3.2 if mode else 4),
   'header_collection_delay_after_word4_ns':((4//width+1)*width-1-4)*(3.2 if mode else 4)})
r={'scope':'Aligned RX block algorithm/reference comparison; no RTL, gearbox, timing, CDC or protocol-latency qualification',
 'cases':cases,'checks':['All 1308 legal frame count pairs at each of three widths','Continuous sequence wraps and source ordering','All 50 single header-bit flips per mode/width suppress effects and latch fault'],
 'source_sha256':{f:hashlib.sha256((p/'verification'/f).read_bytes()).hexdigest() for f in ['block_receiver_model.py','check_block_receiver.py','stream_codec.py','transport_model.py']},
 'limitations':['No bit/word alignment acquisition, source drift, backpressure or physical clock model.','Parallel outputs require multi-enqueue storage; existing single-word FIFOs cannot accept these blocks directly.','Collection delays exclude gearbox handoff, processing, CDC and output serialization.','Does not preserve scalar word-cycle event timing or validate end-to-end PCIe latency.']}
(p/'evidence/block-receiver-model.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(cases,indent=2))
