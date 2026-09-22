`timescale 1ns/1ps
module tb_memory;
 reg rst=1,spi=0,rx=0,tx=0,write=0,ce=0,pe=0,valid=0,request=0;
 reg[4:0]idx=0;reg[23:0]data=0,sample=0;wire[23:0]captured,play;wire done,pv;
 always #7 spi=~spi;always #11 rx=~rx;always #13 tx=~tx;
 pt_memory dut(rst,spi,write,idx,data,captured,rx,tx,ce,pe,sample,valid,done,play,pv,request);
 integer n,seen=0;
 always @(posedge tx)if(pv&&request)begin
  if(play!==24'(seen*43+17))$fatal(1,"playback ordering");seen=seen+1;
 end
 initial begin
  #1;rst=0;#100;rst=1;
  pe=1;#100;if(pv)$fatal(1,"uninitialized playback enabled");pe=0;
  for(n=0;n<32;n=n+1)begin @(negedge spi);write=1;idx=n;data=n*43+17;@(posedge spi);#1;write=0;end
  pe=1;request=1;ce=1;#100;
  for(n=0;n<32;n=n+1)begin @(negedge rx);sample=n*71+9;valid=1;@(posedge rx);#1;valid=0;end
  wait(done);#100;
  for(n=0;n<32;n=n+1)begin idx=n;#1;if(captured!==24'(n*71+9))$fatal(1,"capture ordering");end
  #1000;if(seen!=32||pv)$fatal(1,"finite playback length");
  $display("MEMORY_PASS");$finish;
 end
 initial begin #20000;$fatal(1,"timeout");end
endmodule
