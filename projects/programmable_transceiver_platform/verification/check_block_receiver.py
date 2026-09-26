import hashlib,json
from pathlib import Path
from block_receiver_model import BlockReceiver
from stream_codec import Receiver,encode,slots,metadata
p=Path(__file__).resolve().parents[1];cases=[]
for mode in [0,1]:
 for owner in (None,'wire','iq'):
  plan=slots(mode,owner=owner)
  for width in [2,4,8]:
   wide=BlockReceiver(mode,width,owner=owner);scalar=Receiver(mode,owner=owner);frames=0;blocks=0;peak={'wire':0,'iq':0}
   for wc in range(plan.count('wire')+1):
    for qc in range(plan.count('iq')+1):
     words=encode(mode,[(i*37+frames)%1024 for i in range(wc)],[(i*51+frames)%1024 for i in range(qc)],frames%64,frames%3,0,owner=owner)
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
    bad=encode(mode,[1]*plan.count('wire'),[2]*plan.count('iq'),0,owner=owner);bad[bit//10]^=1<<(bit%10)
    rx=BlockReceiver(mode,width,owner=owner);effects=[]
    try:
     for start in range(0,64,width):effects+=rx.feed(bad[start:start+width])
    except ValueError:pass
    else:raise AssertionError('corrupt header accepted')
    assert rx.fault and not effects
    try:rx.feed([0]*width)
    except ValueError:pass
    else:raise AssertionError('fault not sticky')
   if owner is not None:
    # Construct protected but semantically illegal metadata independently of
    # encode(), which correctly refuses to create inactive-owner payload.
    bad=metadata(int(owner=='iq'),int(owner=='wire'),0)+[0]*59
    rx=BlockReceiver(mode,width,owner=owner);effects=[]
    try:
     for start in range(0,64,width):effects+=rx.feed(bad[start:start+width])
    except ValueError:pass
    else:raise AssertionError('inactive owner admitted')
    assert rx.fault and not effects
   cases.append({'mode':mode,'owner':owner,'words_per_block':width,'frames':frames,'blocks':blocks,'peak_payload_words_per_block':peak,
    'core_clock_mhz':(312.5 if mode else 250)/width,'block_period_ns':(3.2 if mode else 4)*width,
    'max_collection_delay_ns':(width-1)*(3.2 if mode else 4),
    'header_collection_delay_after_word4_ns':((4//width+1)*width-1-4)*(3.2 if mode else 4)})
def check_fifo_edges():
 import random,subprocess,tempfile
 from collections import deque
 from block_receiver_model import BlockFIFO
 rng=random.Random(714);model=BlockFIFO();queue=deque();checks=[];statements=[]
 writes=reads=resets=0;full_stalls=empty_stalls=coincident=invalid_accepted=0
 # Event ticks contain unrelated, coincident and stopped clocks. Reset occurs
 # during traffic; capture all expectations before simulator execution.
 for tick in range(2400):
  reset=tick in (0,937,1701)
  wr=(tick%3==0);rd=(tick%5==1 and not 200<tick<400)
  valid=rng.randrange(4)!=0;pop=rng.randrange(4)!=0
  count=rng.randrange(16);words=tuple(rng.randrange(1024) for _ in range(count)) if valid else None
  if reset:queue.clear();resets+=1
  before=model.status()
  if not reset:
   full_stalls+=int(wr and valid and model.wr_release==2 and not before['wr_ready'])
   empty_stalls+=int(rd and pop and model.rd_release==2 and not before['rd_valid'])
   coincident+=int(wr and rd)
   invalid_accepted+=int(wr and valid and before['wr_ready'] and not 1<=count<=8)
  result=model.step(wr_edge=wr,rd_edge=rd,words=words,pop=pop,reset=reset)
  if result['read'] is not None:
   assert queue and result['read']==queue.popleft();reads+=1
  if result['written']:queue.append(words);writes+=1
  status=model.status();checks.append(status)
  data=sum(w<<(10*i) for i,w in enumerate((words or ())[:8]))
  statements.append(f"wr_clk=0;rd_clk=0;rst_n={int(not reset)};wr_valid={int(valid)};rd_ready={int(pop)};wr_words=4'd{count};wr_data=80'h{data:020x};#1;wr_clk={int(wr)};rd_clk={int(rd)};#1;$display(\"EDGE %d %d %d %d %h\",wr_ready,rd_valid,wr_fault,rd_words,rd_data);")
 tb="""module check_edges;
 reg wr_clk=0,rd_clk=0,rst_n=1,wr_valid=0,rd_ready=0;
 reg [79:0] wr_data=0;reg[3:0]wr_words=0;
 wire wr_ready,rd_valid,wr_fault;wire[79:0]rd_data;wire[3:0]rd_words;
 pt_block_fifo dut(.*);
 initial begin
 """+'\n'.join(statements)+'\n$finish;end endmodule\n'
 with tempfile.TemporaryDirectory() as tmp:
  path=Path(tmp);(path/'tb.sv').write_text(tb)
  subprocess.run(['iverilog','-g2012','-s','check_edges','-o',str(path/'sim'),str(p/'rtl/pt_fifo.sv'),str(p/'rtl/pt_block_fifo.sv'),str(path/'tb.sv')],check=True,capture_output=True)
  output=subprocess.run(['vvp',str(path/'sim')],check=True,capture_output=True,text=True).stdout.splitlines()
 output=[line[5:] for line in output if line.startswith('EDGE ')]
 assert len(output)==len(checks),(len(output),len(checks),output[-3:])
 for index,(line,status) in enumerate(zip(output,checks)):
  ready,valid,fault,count,data=line.split()
  assert (int(ready),int(valid),int(fault))==(int(status['wr_ready']),int(status['rd_valid']),int(status['fault'])),(index,line,status)
  if status['rd_valid']:
   words=status['words'];assert int(count)==len(words)
   assert int(data,16)==sum(w<<(10*i) for i,w in enumerate(words)),(index,line,status)
 assert min(full_stalls,empty_stalls,coincident,invalid_accepted)>0
 return dict(events=len(checks),writes=writes,reads=reads,shared_resets=resets,
             full_stalls=full_stalls,empty_stalls=empty_stalls,coincident_edges=coincident,invalid_accepted=invalid_accepted,
             rtl_edge_equivalent=True,ordered_scoreboard=True,
             scope='Ideal digital synchronizers; excludes metastability, bus skew and independent reset domains')
fifo_edges=check_fifo_edges()
r={'scope':'Aligned RX content comparison plus block-FIFO digital CDC edge comparison against existing RTL; no physical timing or protocol-latency qualification',
 'fifo_edges':fifo_edges,'cases':cases,'checks':['All 1308 legacy count pairs and all 60 counts per exclusive owner/mode at each of three widths','Continuous sequence wraps and source ordering','All 50 single header-bit flips per mode/width/owner suppress effects and latch fault','Protected inactive-owner metadata faults before effects'],
 'source_sha256':{f:hashlib.sha256((p/'verification'/f).read_bytes()).hexdigest() for f in ['block_receiver_model.py','check_block_receiver.py','stream_codec.py','transport_model.py']},
 'limitations':['The FIFO CDC model is not yet integrated with whole-chip queue staging.','No bit/word alignment acquisition, source drift, backpressure or physical clock model.','Parallel outputs require multi-enqueue storage; existing single-word FIFOs cannot accept these blocks directly.','Collection delays exclude gearbox handoff, processing, CDC and output serialization.','Does not preserve scalar word-cycle event timing or validate end-to-end PCIe latency.']}
r['source_sha256'].update({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [p/'rtl/pt_fifo.sv',p/'rtl/pt_block_fifo.sv']})
(p/'evidence/block-receiver-model.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(cases=len(cases),fifo_edges=fifo_edges)))
