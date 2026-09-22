import pathlib,random,subprocess
src=pathlib.Path('/src');out=pathlib.Path('/out');rng=random.Random(7001)
rows=[]
for mask in range(256):
 for trial in range(32):
  words=([0]*8 if trial==0 else [1023]*8 if trial==1 else list(range(8)) if trial==2 else [rng.randrange(1024) for _ in range(8)])
  chosen=[w for i,w in enumerate(words) if mask&(1<<i)]
  bits=sum(w<<(10*i) for i,w in enumerate(words))
  expected=sum(w<<(10*i) for i,w in enumerate(chosen))
  rows.append(f'{bits:020x} {mask:02x} {expected:020x} {len(chosen):x}\n')
(out/'vectors.txt').write_text(''.join(rows))
(out/'test.sv').write_text('''module tb;
reg[79:0] words;reg[7:0]selected;wire[79:0]packed_words;wire[3:0]word_count;
reg[79:0]expected;reg[3:0]count;integer fd,n,r;
pt_lane_compact dut(.*);
initial begin
 fd=$fopen("/out/vectors.txt","r");n=0;
 while(!$feof(fd))begin
  r=$fscanf(fd,"%h %h %h %h\\n",words,selected,expected,count);
  if(r!=4)$fatal(1,"bad vector");
  #1;
  if(packed_words!==expected||word_count!==count)$fatal(1,"compaction mismatch %0d",n);
  n=n+1;
 end
 if(n!=8192)$fatal(1,"coverage");
 $display("PASS 8192 vectors, all 256 masks, ordered lanes, zero padding");$finish;
end
endmodule
''')
def run(rtl,name):
 exe=str(out/name)
 subprocess.run(['iverilog','-g2012','-s','tb','-o',exe,str(rtl),str(out/'test.sv')],check=True)
 return subprocess.run(['vvp',exe],text=True,capture_output=True)
r=run(src/'rtl/pt_lane_compact.sv','test');assert r.returncode==0,r.stdout+r.stderr;print(r.stdout)
s=(src/'rtl/pt_lane_compact.sv').read_text();assert s.count('words[lane*10 +: 10]')==1
(out/'bad.sv').write_text(s.replace('words[lane*10 +: 10]','words[(7-lane)*10 +: 10]'))
r=run(out/'bad.sv','bad');assert r.returncode!=0 and 'compaction mismatch' in r.stdout
print('PASS reversed source-lane negative control rejected')
subprocess.run(['yosys','-Q','-T','-p','read_verilog -sv /src/rtl/pt_lane_compact.sv; synth -top pt_lane_compact; check -assert; stat'],stdout=(out/'synthesis.log').open('w'),check=True)
