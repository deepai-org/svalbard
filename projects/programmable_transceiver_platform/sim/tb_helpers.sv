`timescale 1ns/1ps
module tb_helpers;
 reg clk=0,rst=1,start=0;always #5 clk=~clk;
 wire[11:0]trial;wire busy,done;
 pt_calibrator dut(clk,rst,start,trial>12'd1739,trial,busy,done);
 wire[9:0]word;reg step=0;reg[30:0]reference=31'h7fffffff;integer n,b;
 pt_prbs generator(clk,rst,step,word);
 initial begin
  #1;rst=0;#20;rst=1;
  @(negedge clk);start=1;
  wait(done);if(trial!==1739)$fatal(1,"calibration %d",trial);
  for(n=0;n<100;n=n+1)begin
   @(negedge clk);
   for(b=0;b<10;b=b+1)begin
    if(word[b]!==reference[30])$fatal(1,"PRBS mismatch");
    reference={reference[29:0],reference[30]^reference[27]};
   end
   step=1;@(posedge clk);#1;step=0;
  end
  $display("HELPERS_PASS");$finish;
 end
 initial begin #50000;$fatal(1,"timeout");end
endmodule
