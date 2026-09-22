`timescale 1ns/1ps
// Cycle-exact comparison with retained pre-stage TX; reset at every frame phase.
module tb_tx_stage_compare;
 reg clk=0,rst_n=0,mode8=0;
 reg[9:0]wd=0,qd=0;reg[6:0]wc=0;reg[5:0]qc=0;reg[3:0]op=0;reg[7:0]arg=0;
 wire wp,qp,rwp,rqp;wire[9:0]word,rword;
 pt_stream_tx dut(clk,rst_n,mode8,wd,qd,wc,qc,op,arg,wp,qp,word);
 pt_stream_tx_reference refdut(clk,rst_n,mode8,wd,qd,wc,qc,op,arg,rwp,rqp,rword);
 integer m,phase,i,cycles=0;reg[31:0]rng=32'h82478139;
 task cycle;
 begin
  clk=0;
  rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);
  wd=rng[9:0];qd=rng[19:10];wc=rng[26:20];qc=rng[31:26];op=(rng[3:0]%3);arg=rng[7:0];
  #4;
  if(rst_n && {wp,qp,word}!=={rwp,rqp,rword})$fatal(1,"stage mismatch cycle %0d phase %0d",cycles,phase);
  clk=1;#4;cycles=cycles+1;
 end
 endtask
 initial begin
  for(m=0;m<2;m=m+1)begin
   mode8=m;
   for(phase=0;phase<64;phase=phase+1)begin
    rst_n=0;cycle();rst_n=1;
    // Fill both banks, then reset with each possible pending-write phase.
    for(i=0;i<256+phase;i=i+1)cycle();
    rst_n=0;cycle();rst_n=1;
    for(i=0;i<256;i=i+1)cycle();
   end
  end
  $display("TX_STAGE_COMPARE_PASS cycles=%0d reset_phases=128",cycles);$finish;
 end
endmodule
