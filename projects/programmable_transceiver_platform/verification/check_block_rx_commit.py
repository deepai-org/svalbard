import pathlib,sys,subprocess
sys.path.insert(0,'/src/verification')
from block_rx_vectors import receiver_vectors
out=pathlib.Path('/out')
rows=receiver_vectors(latency=2)
(out/'vectors.txt').write_text(''.join(rows));n=len(rows)
(out/'test.sv').write_text('''module tb;
reg clk=0,rst_n,mode8,in_valid,wire_ready,iq_ready,command_ready;reg[79:0]words;
wire[79:0]wire_words,iq_words;wire[3:0]wire_count,iq_count;wire wire_valid,iq_valid,command_valid,fault;wire[3:0]opcode;wire[7:0]argument;
integer f,r,n;reg reset;reg[79:0]ew,eq;reg[3:0]cw,cq,op;reg wv,qv,cv,ef;reg[7:0]arg;
pt_block_rx_commit dut(.*);
initial begin f=$fopen("/out/vectors.txt","r");n=0;
while(!$feof(f))begin
r=$fscanf(f,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\\n",reset,mode8,in_valid,wire_ready,iq_ready,command_ready,words,ew,eq,cw,cq,wv,qv,cv,op,arg,ef);
if(r!=17)$fatal(1,"vector");rst_n=!reset;#1;
if({wire_words,iq_words,wire_count,iq_count,wire_valid,iq_valid,command_valid,opcode,argument}!=={ew,eq,cw,cq,wv,qv,cv,op,arg})$fatal(1,"RX effects %0d",n);
clk=1;#1;if(fault!==ef)$fatal(1,"RX fault %0d",n);clk=0;#1;n=n+1;end
$display("PASS RX cycles=%0d",n);$finish;end endmodule
''')
rtl=['/src/rtl/'+f for f in ('pt_lane_compact.sv','pt_block_route_prefix.sv','pt_block_header.sv','pt_block_rx_commit.sv')]
def run(files,name):
 exe=str(out/name);subprocess.run(['iverilog','-g2012','-I/src/rtl','-s','tb','-o',exe,*files,str(out/'test.sv')],check=True)
 return subprocess.run(['vvp',exe],capture_output=True,text=True)
r=run(rtl,'test');assert r.returncode==0,r.stdout+r.stderr;assert f'cycles={n}' in r.stdout;print(r.stdout)
s=pathlib.Path(rtl[-1]).read_text()
for name,old,new in [
 ('capacity','output_good&&capacity','output_good'),
 ('command','&&(!output_first||command_ready)',''),
 ('valid','!fault&&output_valid&&output_good','!fault&&stage_valid&&output_good'),
 ('mask','mask_for(mode8,input_beat,',"mask_for(mode8,3'(input_beat+1),")]:
 assert old in s
 (out/(name+'.sv')).write_text(s.replace(old,new))
 r=run(rtl[:-1]+[str(out/(name+'.sv'))],name)
 assert r.returncode!=0 and ('RX effects' in r.stdout or 'RX fault' in r.stdout),(name,r.stdout)
 print('PASS mutation rejected:',name)
subprocess.run(['yosys','-Q','-T','-p','read_verilog -sv -I/src/rtl '+' '.join(rtl)+'; synth -top pt_block_rx_commit; check -assert'],stdout=(out/'synthesis.log').open('w'),check=True)
