`timescale 1ns/1ps
module tb_shared_egress_lifecycle;
 reg hclk=0,wclk=0,rclk=0,h_run=1,r_run=1,rst_n=1,en=0,owner=0;
 reg peer_reset=1,wire_request=0,rf_request=0;
 reg[9:0]word=10'h2aa;
 always #1.6 if(h_run)hclk=~hclk;
 always #8 wclk=~wclk;
 always #12.5 if(r_run)rclk=~rclk;
 wire[9:0]h2d,d2h;wire wp,qp;
 pt_dense_link_tx peer(hclk,peer_reset,owner,word,word,7'd59,6'd59,
  4'd0,8'd0,wp,qp,h2d);
 wire[39:0]wire_data;wire wire_valid,wire_idle,rf_valid,rf_mute;
 wire[23:0]rf_data;wire[15:0]status;
 pt_transport_harness core(.rst_n(rst_n),.enable(en),.mode8(1'b0),
  .hclk(hclk),.wire_rx_clk(wclk),.wire_tx_clk(wclk),
  .rf_rx_clk(rclk),.rf_tx_clk(rclk),.h2d_word(h2d),.d2h_word(d2h),
  .wire_rx_data(40'd0),.wire_rx_valid(1'b0),.wire_tx_data(wire_data),
  .wire_tx_valid(wire_valid),.wire_tx_request(wire_request),
  .rf_rx_sample(24'd0),.rf_rx_valid(1'b0),.rf_tx_sample(rf_data),
  .rf_tx_valid(rf_valid),.rf_tx_request(rf_request),.status(status),
  .wire_idle(wire_idle),.rf_mute(rf_mute),.payload_iq(owner));
 task automatic stop_and_disable;
 begin
  @(negedge hclk);h_run=0;peer_reset=0;
  #1;en=0;
  // The host/pair clocks are stopped: reset must still flush immediately.
  #1;if(wire_valid||rf_valid||status[9])$fatal(1,"Disable failed with stopped host clock wv=%b rv=%b st=%h",wire_valid,rf_valid,status);
 end endtask
 task automatic restart;
 begin
  #100;en=1;
  #100;if(wire_valid||rf_valid)$fatal(1,"Stale output appeared before host clock restart");
  h_run=1;
  #100;@(negedge hclk);peer_reset=1;
 end endtask
 integer seen;
 initial begin
  #1;rst_n=0;peer_reset=0;
  #100;rst_n=1;en=1;
  #100;@(negedge hclk);peer_reset=1;
  wait(wire_valid);
  @(negedge wclk);if(wire_data!=={4{10'h2aa}})$fatal(1,"Initial wired data mismatch %h",wire_data);
  stop_and_disable();owner=1;word=10'h155;rf_request=1;
  restart();seen=0;
  while(seen<4)begin
   @(posedge rclk);if(rf_valid)begin
    if(rf_data!==24'h555555)$fatal(1,"Old owner data leaked into RF: %h",rf_data);
    seen=seen+1;
   end
  end
  @(negedge rclk);r_run=0;
  stop_and_disable();owner=0;word=10'h3a5;wire_request=1;rf_request=0;
  restart();seen=0;
  while(seen<4)begin
   @(posedge wclk);if(wire_valid)begin
    @(negedge wclk);if(wire_data!=={4{10'h3a5}})$fatal(1,"Old owner data leaked into wired: %h",wire_data);
    seen=seen+1;
   end
  end
  if(status&16'h1dfe)$fatal(1,"Lifecycle fault %h",status);
  $display("SHARED_EGRESS_LIFECYCLE_PASS stopped-host disable, stopped-RF mux change, both owner resets");
  $finish;
 end
 initial begin #20000;$fatal(1,"Lifecycle timeout");end
endmodule
