"""Reuse transaction scoreboard, then require sustained read throughput."""
import pathlib,subprocess
src=pathlib.Path('/src');out=pathlib.Path('/out')
s=(src/'sim/tb_block_fifo.sv').read_text().replace('tb_block_fifo','tb_block_elastic').replace('pt_block_fifo dut','pt_block_elastic dut').replace('dut.storage','dut.fifo.storage')
s=s.replace('integer phase=0,cycles=0,i;', 'integer phase=0,cycles=0,i; integer streak=0,best=0;')
s=s.replace('old_rg=dut.fifo.storage.rg;', '''old_rg=dut.fifo.storage.rg;
  if(phase==3 && rd_valid&&rd_ready)begin streak=streak+1;if(streak>best)best=streak;end
  else streak=0;
  if(rst_n && (dut.receive_buffer.overflow || dut.receive_buffer.underflow))$fatal(1,"elastic buffer error");''')
s=s.replace('// Stop producer, drain all accepted blocks.', '''// Saturate the source and require uninterrupted one-block-per-read-cycle service.
  @(negedge wr_clk);force wr_valid=1;force wr_words=8;force rd_ready=1;phase=3;
  #15000;
  if(best<500)$fatal(1,"throughput bubble: best %0d",best);
  $display("PASS sustained block reads=%0d",best);
  // Stop producer, drain all accepted blocks.''')
(out/'test.sv').write_text(s)
rtl=[str(src/'rtl'/f) for f in ('pt_fifo.sv','pt_block_fifo.sv','pt_block_elastic.sv')]
def run(files,name):
 exe=str(out/name)
 subprocess.run(['iverilog','-g2012','-s','tb_block_elastic','-o',exe,*files,str(out/'test.sv')],check=True)
 return subprocess.run(['vvp',exe],text=True,capture_output=True)
r=run(rtl,'test');print(r.stdout);assert r.returncode==0,r.stderr
original=(src/'rtl/pt_block_elastic.sv').read_text()
assert original.count('.din({block_words,block_data})')==1
(out/'bad.sv').write_text(original.replace('.din({block_words,block_data})',".din({block_words,block_data ^ 80'd1})"))
r=run(rtl[:-1]+[str(out/'bad.sv')],'bad');assert r.returncode!=0 and 'block mismatch' in r.stdout
print('PASS corrupted elastic data rejected')
