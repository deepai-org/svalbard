`timescale 1ns/1ps
// Functional queue admission at the specified clocks, before physical STA.
// FPGA queues are ideal finite external sources; chip CDC/FIFOs are real RTL.
module tb_dense_service;
 parameter real HOST_HALF=1.6, WIRE_PHASE=0.0;
 parameter EXPECT_REJECTION=0;
 parameter DEBUG=0;
 reg hclk=0,wclk=0,rclk=0,rst_n=1,en=0,peer_tx_reset=1,peer_rx_reset=1,source_on=0;
 always #(HOST_HALF)hclk=~hclk;
 initial begin #(WIRE_PHASE);forever #4 wclk=~wclk;end
 always #12.5 rclk=~rclk;
 integer produced=0,taken=0,tx_pairs=0,rx_words=0;
 reg[9:0]line_word=0,expected_tx=0,expected_rx=0;
 wire[9:0]source_data=10'(taken*37+19);
 wire[31:0]queued=produced-taken;
 wire[6:0]source_count=queued>127?127:queued[6:0];
 wire source_pop,unused_pop;wire[9:0]h2d,d2h,peer_data;
 wire peer_wv,peer_qv,peer_cv,peer_fault,peer_locked;wire[3:0]peer_op;wire[7:0]peer_arg;
 pt_dense_link_tx peer_tx(hclk,peer_tx_reset,1'b0,source_data,10'd0,source_count,6'd0,4'd0,8'd0,source_pop,unused_pop,h2d);
 pt_dense_link_rx peer_rx(hclk,peer_rx_reset,1'b0,d2h,1'b1,1'b1,peer_data,
  peer_wv,peer_qv,peer_cv,peer_fault,peer_locked,peer_op,peer_arg);
 wire[19:0]tx_data;wire tx_valid,wire_idle,rf_valid,rf_mute;wire[23:0]rf_sample;wire[15:0]status;
 pt_core core(.rst_n(rst_n),.enable(en),.mode8(1'b0),.host_tx_clk(hclk),.host_rx_clk(hclk),
  .wire_rx_clk(wclk),.wire_tx_clk(wclk),.rf_rx_clk(rclk),.rf_tx_clk(rclk),
  .h2d_word(h2d),.d2h_word(d2h),.wire_rx_data({line_word+10'd1,line_word}),.wire_rx_valid(source_on),
  .wire_tx_data(tx_data),.wire_tx_valid(tx_valid),.wire_tx_request(1'b1),
  .rf_rx_sample(24'hfedcba),.rf_rx_valid(source_on),.rf_tx_sample(rf_sample),.rf_tx_valid(rf_valid),
  .rf_tx_request(1'b1),.status(status),.wire_idle(wire_idle),.rf_mute(rf_mute),.payload_iq(1'b0));
 always @(posedge wclk)begin
  if(source_on)begin produced<=produced+2;line_word<=line_word+2;end
  if(tx_valid)begin
   if(tx_data!=={10'((expected_tx+1)*37+19),10'(expected_tx*37+19)})
    $fatal(1,"TX order pair=%0d got=%h expected index=%0d",tx_pairs,tx_data,expected_tx);
   expected_tx<=expected_tx+2;tx_pairs=tx_pairs+1;
  end
 end
 always @(posedge hclk)begin
  if(DEBUG&&en&&source_pop)
   $display("SERVICE_TRACE time=%0t produced=%0d d2h=%0d queued=%0d status=%h",$time,produced,rx_words,queued,status);
  if(source_pop)begin
   if(taken>=produced)$fatal(1,"FPGA source queue underflow");
   taken<=taken+1;
  end
  if(unused_pop||peer_qv)$fatal(1,"Inactive I/Q engine consumed or received data");
  if(peer_wv)begin
   if(rx_words&&peer_data!==expected_rx)$fatal(1,"RX order word=%0d got=%h expected=%h",rx_words,peer_data,expected_rx);
   expected_rx<=peer_data+1;rx_words=rx_words+1;
  end
  if((status&16'h1dfe)!=0||peer_fault||queued>127)begin
   if(EXPECT_REJECTION)begin $display("LOW_RATE_REJECTED time=%0t status=%h queued=%0d",$time,status,queued);$finish;end
   else $fatal(1,"Queue/link fault time=%0t status=%h queued=%0d peer=%b",$time,status,queued,peer_fault);
  end
 end
 initial begin
  #1;rst_n=0;peer_tx_reset=0;peer_rx_reset=0;
  #100;rst_n=1;peer_rx_reset=1;
  @(negedge hclk)en=1;
  #100;@(negedge hclk)begin source_on=1;peer_tx_reset=1;end
  #200000;
  if(EXPECT_REJECTION)$fatal(1,"Insufficient host rate was not rejected");
  if(tx_pairs<24000||rx_words<48000||!peer_locked||!status[9])$fatal(1,"Insufficient useful service");
  $display("DENSE_SERVICE_PASS host_half=%f phase=%f tx_pairs=%0d rx_words=%0d status=%h",HOST_HALF,WIRE_PHASE,tx_pairs,rx_words,status);
  $finish;
 end
endmodule
