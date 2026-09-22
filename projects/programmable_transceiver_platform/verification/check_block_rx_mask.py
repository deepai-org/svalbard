import pathlib,sys,subprocess
sys.path.insert(0,'/src/verification')
from stream_codec import Receiver,encode,slots
out=pathlib.Path('/out');rows=[];ref=None;fault=False;mode=0;pending=None

def cycle(words,valid=1,wr=1,qr=1,reset=0,cr=1):
 global ref,fault,pending
 if reset:ref=Receiver(mode);fault=False;pending=None
 ev=[]
 if not reset and pending is not None and not fault:
  try:
   for w in pending:
    event=ref.feed(w)
    if event:ev.append(event)
   if (any(s=='wire' for s,v in ev) and not wr) or (any(s=='iq' for s,v in ev) and not qr) or (any(s=='command' for s,v in ev) and not cr):raise ValueError('capacity')
  except ValueError:fault=True;ev=[]
 pending=list(words) if valid and not reset and not fault else None
 ws=[v for s,v in ev if s=='wire'];qs=[v for s,v in ev if s=='iq'];cmd=[v for s,v in ev if s=='command']
 values=[reset,mode,valid,wr,qr,cr,sum(w<<(10*i) for i,w in enumerate(words)),sum(w<<(10*i) for i,w in enumerate(ws)),sum(w<<(10*i) for i,w in enumerate(qs)),len(ws),len(qs),bool(ws),bool(qs),bool(cmd),cmd[0][0] if cmd else 0,cmd[0][1] if cmd else 0,fault]
 rows.append(' '.join(f'{int(v):x}' for v in values)+'\n')

def reset():cycle([0]*8,reset=1)
def frame(data,blocked=-1,wr=1,qr=1):
 for b in range(8):
  if b%3==0:cycle(data[b*8:b*8+8],valid=0,wr=0,qr=0)
  cycle(data[b*8:b*8+8],wr=wr if b==blocked else 1,qr=qr if b==blocked else 1)
for mode in (0,1):
 reset();seq=0
 for wc in range(slots(mode).count('wire')+1):
  for qc in range(slots(mode).count('iq')+1):
   data=encode(mode,[(i*17+wc)&1023 for i in range(wc)],[(i*29+qc)&1023 for i in range(qc)],seq,2,1)
   frame(data);seq=(seq+1)%64
 for bit in range(50):
  reset();data=encode(mode,[1],[2],0);data[bit//10]^=1<<(bit%10);frame(data);frame(encode(mode,[],[],0))
 for b in range(8):
  for wr,qr in ((0,1),(1,0),(0,0)):
   reset();frame(encode(mode,[3]*slots(mode).count('wire'),[4]*slots(mode).count('iq'),0,1,1),b,wr,qr)
   frame(encode(mode,[],[],1))
 reset();frame(encode(mode,[],[],0),0,0,0) # No payload destination needed.
 reset();frame(encode(mode,[],[],1)) # Wrong initial sequence.
 # All supported commands, all three destination readiness bits, first beat.
 for op,arg in ((0,0),(1,0),(1,1),(2,0),(2,1)):
  for payload in (False,True):
   for readiness in range(8):
    reset();data=encode(mode,[3]*3 if payload else [],[4]*3 if payload else [],0,op,arg)
    cycle(data[:8],valid=0,wr=0,qr=0,cr=0)
    cycle(data[:8],wr=bool(readiness&1),qr=bool(readiness&2),cr=bool(readiness&4))
    for b in range(1,8):cycle(data[b*8:b*8+8],cr=0)
    # Readiness restored cannot silently resume a faulted receiver.
    frame(encode(mode,[],[],1))

# Explicit arrival-ready / commit-not-ready transition for a pending command.
for mode in (0,1):
 reset();data=encode(mode,[3]*3,[4]*3,0,2,1)
 cycle(data[:8],cr=1)
 cycle(data[8:16],cr=0)
 cycle(data[16:24],cr=1)
 reset();cycle(data[:8],cr=0)
 cycle(data[8:16],cr=1) # Arrival readiness must not reject the stored first beat.
 cycle([0]*8,valid=0)
cycle([0]*8,valid=0)
(out/'vectors.txt').write_text(''.join(rows));n=len(rows)
(out/'test.sv').write_text('''module tb;
reg clk=0,rst_n,mode8,in_valid,wire_ready,iq_ready,command_ready;reg[79:0]words;
wire[79:0]wire_words,iq_words;wire[3:0]wire_count,iq_count;wire wire_valid,iq_valid,command_valid,fault;wire[3:0]opcode;wire[7:0]argument;
integer f,r,n;reg reset;reg[79:0]ew,eq;reg[3:0]cw,cq,op;reg wv,qv,cv,ef;reg[7:0]arg;
pt_block_rx_mask dut(.*);
initial begin f=$fopen("/out/vectors.txt","r");n=0;
while(!$feof(f))begin
r=$fscanf(f,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\\n",reset,mode8,in_valid,wire_ready,iq_ready,command_ready,words,ew,eq,cw,cq,wv,qv,cv,op,arg,ef);
if(r!=17)$fatal(1,"vector");rst_n=!reset;#1;
if({wire_words,iq_words,wire_count,iq_count,wire_valid,iq_valid,command_valid,opcode,argument}!=={ew,eq,cw,cq,wv,qv,cv,op,arg})$fatal(1,"RX effects %0d",n);
clk=1;#1;if(fault!==ef)$fatal(1,"RX fault %0d",n);clk=0;#1;n=n+1;end
$display("PASS RX cycles=%0d",n);$finish;end endmodule
''')
rtl=['/src/rtl/'+f for f in ('pt_lane_compact.sv','pt_block_route_mask.sv','pt_block_header.sv','pt_block_rx_mask.sv')]
def run(files,name):
 exe=str(out/name);subprocess.run(['iverilog','-g2012','-I/src/rtl','-s','tb','-o',exe,*files,str(out/'test.sv')],check=True)
 return subprocess.run(['vvp',exe],capture_output=True,text=True)
r=run(rtl,'test');assert r.returncode==0,r.stdout+r.stderr;assert f'cycles={n}' in r.stdout;print(r.stdout)
s=pathlib.Path(rtl[-1]).read_text();assert s.count('allowed&&capacity')==1
(out/'bad.sv').write_text(s.replace('allowed&&capacity','allowed'))
r=run(rtl[:-1]+[str(out/'bad.sv')],'bad');assert r.returncode!=0 and 'RX effects' in r.stdout
print('PASS capacity-bypass mutation rejected')
assert s.count('&&(beat!=0||command_ready)')==1
(out/'bad_command.sv').write_text(s.replace('&&(beat!=0||command_ready)',''))
r=run(rtl[:-1]+[str(out/'bad_command.sv')],'bad_command');assert r.returncode!=0 and 'RX effects' in r.stdout
print('PASS command-readiness bypass rejected')
assert s.count('!fault&&stage_valid&&')==1
(out/'bad_stage.sv').write_text(s.replace('!fault&&stage_valid&&','!fault&&in_valid&&'))
r=run(rtl[:-1]+[str(out/'bad_stage.sv')],'bad_stage');assert r.returncode!=0 and ('RX effects' in r.stdout or 'RX fault' in r.stdout)
print('PASS live-valid instead of stored-valid mutation rejected')
assert s.count('mask_for(mode8,input_beat,')==2
(out/'bad_mask.sv').write_text(s.replace('mask_for(mode8,input_beat,', "mask_for(mode8,3'(input_beat+1),"))
r=run(rtl[:-1]+[str(out/'bad_mask.sv')],'bad_mask');assert r.returncode!=0 and 'RX effects' in r.stdout
print('PASS next-beat mask mutation rejected')



subprocess.run(['yosys','-Q','-T','-p','read_verilog -sv -I/src/rtl '+' '.join(rtl)+'; synth -top pt_block_rx_mask; check -assert'],stdout=(out/'synthesis.log').open('w'),check=True)
