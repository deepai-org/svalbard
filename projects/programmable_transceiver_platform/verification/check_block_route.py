import pathlib,subprocess,sys
sys.path.insert(0,'/src/verification')
from stream_codec import slots
out=pathlib.Path('/out');rows=[];cases=0
for mode in (0,1):
 plan=slots(mode)
 for wc in range(plan.count('wire')+1):
  for qc in range(plan.count('iq')+1):
   cases+=1;left={'wire':wc,'iq':qc}
   for beat in range(8):
    words=[((beat*8+i)*13+wc*3+qc*7)&1023 for i in range(8)]
    packed=sum(w<<(10*i) for i,w in enumerate(words))
    before=left.copy();selected={'wire':[],'iq':[]}
    # Independent scalar slot consumption, preserving per-source ordering.
    for i,w in enumerate(words):
     source=plan[beat*8+i]
     if source in left and left[source]:
      selected[source].append(w);left[source]-=1
    outputs=[sum(w<<(10*i) for i,w in enumerate(selected[s])) for s in ('wire','iq')]
    for allow in (0,1):
     vals=[mode,allow,beat,packed,before['wire'],before['iq'],outputs[0] if allow else 0,outputs[1] if allow else 0,len(selected['wire']) if allow else 0,len(selected['iq']) if allow else 0,left['wire'] if allow else before['wire'],left['iq'] if allow else before['iq']]
     rows.append(' '.join(f'{v:x}' for v in vals)+'\n')
   assert left=={'wire':0,'iq':0}
assert cases==1308
(out/'vectors.txt').write_text(''.join(rows))
(out/'test.sv').write_text('''module tb;
reg mode8,allow_payload;reg[2:0]beat;reg[79:0]words;reg[5:0]left_wire,left_iq;
wire[79:0]wire_words,iq_words;wire[3:0]wire_count,iq_count;wire[5:0]next_wire,next_iq;
reg[79:0]ew,eq;reg[3:0]cw,cq;reg[5:0]nw,nq;integer f,r,n;
pt_block_route dut(.*);
initial begin f=$fopen("/out/vectors.txt","r");n=0;
while(!$feof(f))begin
r=$fscanf(f,"%h %h %h %h %h %h %h %h %h %h %h %h\\n",mode8,allow_payload,beat,words,left_wire,left_iq,ew,eq,cw,cq,nw,nq);
if(r!=12)$fatal(1,"vector");#1;
if({wire_words,iq_words,wire_count,iq_count,next_wire,next_iq}!=={ew,eq,cw,cq,nw,nq})$fatal(1,"route mismatch %0d",n);
n=n+1;end
if(n!=20928)$fatal(1,"coverage");$display("PASS 20928 beat vectors, 1308 count pairs, both allow states");$finish;end
endmodule
''')
rtl=['/src/rtl/pt_lane_compact.sv','/src/rtl/pt_block_route.sv']
def run(files,name):
 exe=str(out/name);subprocess.run(['iverilog','-g2012','-I/src/rtl','-s','tb','-o',exe,*files,str(out/'test.sv')],check=True)
 return subprocess.run(['vvp',exe],capture_output=True,text=True)
r=run(rtl,'test');assert r.returncode==0,r.stdout+r.stderr;print(r.stdout)
s=pathlib.Path(rtl[1]).read_text();assert s.count('pos-2')==1
(out/'bad.sv').write_text(s.replace('pos-2','pos-1'))
r=run([rtl[0],str(out/'bad.sv')],'bad');assert r.returncode!=0 and 'route mismatch' in r.stdout
print('PASS schedule-offset mutation rejected')
subprocess.run(['yosys','-Q','-T','-p','read_verilog -sv -I/src/rtl /src/rtl/pt_lane_compact.sv /src/rtl/pt_block_route.sv; synth -top pt_block_route; check -assert'],stdout=(out/'synthesis.log').open('w'),check=True)
