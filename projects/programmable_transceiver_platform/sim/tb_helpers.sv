`timescale 1ns/1ps
module tb_helpers;
 reg clk=0,rst=1,start=0;always #5 clk=~clk;
 wire[11:0]trial;wire busy,done;
 pt_calibrator dut(clk,rst,start,trial>12'd1739,trial,busy,done);
 initial begin
  #1;rst=0;#20;rst=1;
  @(negedge clk);start=1;
  wait(done);if(trial!==1739)$fatal(1,"calibration %d",trial);
  // PRBS: sim/tb_pt_pattern.sv (make transceiver-pattern).
  $display("HELPERS_PASS");$finish;
 end
 initial begin #50000;$fatal(1,"timeout");end
endmodule
