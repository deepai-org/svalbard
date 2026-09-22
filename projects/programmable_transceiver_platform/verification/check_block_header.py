import pathlib,sys,itertools,subprocess
sys.path.insert(0,'/src/verification')
from stream_codec import metadata,unprotect,slots,GUARD
out=pathlib.Path('/out');rows=[]
def add(header,mode,seq):
 try:
  assert header>>40==GUARD
  d=unprotect(header&((1<<40)-1));wc=d&63;qc=(d>>6)&63;op=(d>>18)&15;arg=d>>22
  assert (d>>12)&63==seq
  assert wc<=slots(mode).count('wire') and qc<=slots(mode).count('iq')
  assert (op==0 and arg==0) or (op in (1,2) and arg in (0,1))
  result=(1<<24)|(wc<<18)|(qc<<12)|(op<<8)|arg
 except (ValueError,AssertionError):result=0
 rows.append(f'{header:x} {mode:x} {seq:x} {result:x}\n')
def encode(wc,qc,seq,op=0,arg=0):return sum(w<<(10*i) for i,w in enumerate(metadata(wc,qc,seq,op,arg)))
for mode in (0,1):
 for wc in range(slots(mode).count('wire')+1):
  for qc in range(slots(mode).count('iq')+1):
   seq=(wc+qc)%64;add(encode(wc,qc,seq),mode,seq)
 base=encode(1,1,19,2,1)
 for n in (1,2,3):
  for bits in itertools.combinations(range(50),n):add(base^sum(1<<b for b in bits),mode,19)
 for seq in range(64):
  add(encode(1,1,seq),mode,seq);add(encode(1,1,seq),mode,(seq+1)%64)
 for op in range(16):
  for arg in range(256):add(encode(1,1,0,op,arg),mode,0)
 for wc,qc in ((63,0),(0,63)):add(encode(wc,qc,0),mode,0)
(out/'vectors.txt').write_text(''.join(rows));n=len(rows)
(out/'test.sv').write_text('''module tb;
reg[49:0]header;reg mode8;reg[5:0]expected_seq;wire good;wire[5:0]wire_count,iq_count;wire[3:0]opcode;wire[7:0]argument;
reg[24:0]expected;integer f,r,n;
pt_block_header dut(.*);
initial begin f=$fopen("/out/vectors.txt","r");n=0;
while(!$feof(f))begin r=$fscanf(f,"%h %h %h %h\\n",header,mode8,expected_seq,expected);if(r!=4)$fatal(1,"vector");#1;
if({good,wire_count,iq_count,opcode,argument}!==expected)$fatal(1,"header mismatch %0d",n);n=n+1;end
$display("PASS header vectors=%0d",n);$finish;end endmodule
''')
def run(rtl,name):
 exe=str(out/name);subprocess.run(['iverilog','-g2012','-s','tb','-o',exe,str(rtl),str(out/'test.sv')],check=True)
 return subprocess.run(['vvp',exe],capture_output=True,text=True)
p=pathlib.Path('/src/rtl/pt_block_header.sv');r=run(p,'test');assert r.returncode==0,r.stdout+r.stderr;assert f'vectors={n}' in r.stdout;print(r.stdout)
s=p.read_text();assert s.count('syndrome==0&&')==1
(out/'bad.sv').write_text(s.replace('syndrome==0&&',''))
r=run(out/'bad.sv','bad');assert r.returncode!=0 and 'header mismatch' in r.stdout
print('PASS omitted-syndrome negative control rejected')
subprocess.run(['yosys','-Q','-T','-p','read_verilog -sv /src/rtl/pt_block_header.sv; synth -top pt_block_header; check -assert'],stdout=(out/'synthesis.log').open('w'),check=True)
