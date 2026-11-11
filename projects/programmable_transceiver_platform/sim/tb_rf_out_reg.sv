`timescale 1ns/1ps
// pt_rf_out_reg (bypass): random producer valid / port request. Every sample the producer hands over
// (req_core && in_valid) must leave the port (request && valid) exactly once, in order
module tb_rf_out_reg;
 reg clk=0,rst_n=0,in_valid=0,request=0;reg[23:0]cnt=0;
 wire req_core,valid,mute;wire[23:0]sample;
 wire[23:0]in_sample=in_valid?cnt:24'd0;
 pt_rf_out_reg dut(.clk(clk),.rst_n(rst_n),.halfband(1'b0),.in_sample(in_sample),.in_valid(in_valid),.in_mute(1'b0),
  .req_core(req_core),.sample(sample),.valid(valid),.mute(mute),.request(request));
 always #5 clk=!clk;
 integer i,taken=0,sent=0;reg[23:0]expect_s=0;
 initial begin
  #22 rst_n=1;
  for(i=0;i<200000;i=i+1)begin
   @(negedge clk);
   in_valid=$random%4!=0; request=$random%3!=0;
   @(posedge clk);
   if(request&&valid)begin
    if(sample!==expect_s)begin $display("RF_OUT_FAIL got %h expected %h",sample,expect_s);$finish;end
    expect_s=expect_s+1;sent=sent+1;end
   if(req_core&&in_valid)begin cnt=cnt+1;taken=taken+1;end
  end
  if(taken-sent>1||sent<100000)begin $display("RF_OUT_FAIL taken %0d sent %0d",taken,sent);$finish;end
  $display("RF_OUT_PASS taken=%0d sent=%0d",taken,sent);$finish;
 end
endmodule
