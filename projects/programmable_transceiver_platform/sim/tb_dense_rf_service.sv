`timescale 1ns/1ps
module tb_dense_rf_service;
 parameter MODE8=0;
 parameter HOST_BURST=0;
 parameter real RF_PHASE=0.0;
 // Host word clock half period: 1.6 ns full rate (312.5 MHz), 3.2 ns the reduced div2 rate
 // that RF modes use (spec AC-4 PWR-HOST-RF; core clock 39.06 MHz < 40 MS/s).
 parameter real HOST_HALF=1.6;
 reg hclk=0,rclk=0,tclk=0,wclk=0,rst_n=1,en=0,source_on=0;
 reg peer_tx_reset=1,peer_rx_reset=1;
 always #(HOST_HALF) hclk=~hclk;
 always #8 wclk=~wclk;
 initial begin #(RF_PHASE);forever #12.5 rclk=~rclk;end
 initial begin #(RF_PHASE+0.7);forever #12.5 tclk=~tclk;end
 reg[23:0]samples[0:9999];reg[9:0]words[0:23999];
 integer produced=0,taken=0,tx_samples=0,rx_samples=0;
 // One full 59-word host frame at startup, then sixteen sample periods
 // without additional host production before continuous 40 MS/s resumes.
 // The finite FPGA source queue may hold 128 words in this burst fixture.
 wire[31:0]host_produced=HOST_BURST?((MODE8?37:25)+(produced>16?produced-16:0)):produced;
 wire[31:0]queued=host_produced*(MODE8?16:24)/10-taken;
 wire[5:0]source_count=queued>63?63:queued[5:0];
 wire source_pop,unused_pop;wire[9:0]h2d,d2h,peer_data;
 wire peer_wv,peer_qv,peer_cv,peer_fault,peer_locked;
 wire[3:0]peer_op;wire[7:0]peer_arg;
 pt_dense_link_tx peer_tx(hclk,peer_tx_reset,1'b1,10'd0,words[taken],7'd0,source_count,
  4'd0,8'd0,unused_pop,source_pop,h2d);
 pt_dense_link_rx peer_rx(hclk,peer_rx_reset,1'b1,d2h,1'b1,1'b1,peer_data,
  peer_wv,peer_qv,peer_cv,peer_fault,peer_locked,peer_op,peer_arg);
 wire[23:0]tx_sample;wire tx_valid,rf_mute,wire_valid,wire_idle;
 wire[39:0]wire_data;wire[15:0]status;
 pt_transport_harness core(.rst_n(rst_n),.enable(en),.mode8(1'(MODE8)),
  .hclk(hclk),.wire_rx_clk(wclk),.wire_tx_clk(wclk),
  .rf_rx_clk(rclk),.rf_tx_clk(tclk),.h2d_word(h2d),.d2h_word(d2h),
  .wire_rx_data(40'hffffffffff),.wire_rx_valid(source_on),.wire_tx_data(wire_data),
  .wire_tx_valid(wire_valid),.wire_tx_request(1'b1),
  .rf_rx_sample(samples[produced]),.rf_rx_valid(source_on),.rf_tx_sample(tx_sample),
  .rf_tx_valid(tx_valid),.rf_tx_request(1'b1),.status(status),
  .wire_idle(wire_idle),.rf_mute(rf_mute),.payload_iq(1'b1));
 function automatic[23:0]quantized(input[23:0]value);
 begin quantized=MODE8?{value[23:16],4'd0,value[11:4],4'd0}:value;end endfunction
 function automatic[23:0]compressed(input[23:0]value);
 begin compressed=MODE8?{8'd0,value[23:16],value[11:4]}:value;end endfunction
 always @(posedge rclk)if(source_on)produced<=produced+1;
 always @(posedge tclk)if(tx_valid)begin
  if(tx_sample!==quantized(samples[tx_samples]))
   $fatal(1,"RF TX sample %d got %h expected %h",tx_samples,tx_sample,quantized(samples[tx_samples]));
  tx_samples=tx_samples+1;
 end
 reg[63:0]bits=0;integer bit_count=0;
 always @(posedge hclk)begin
  if(HOST_BURST&&peer_tx_reset)$fwrite(trace,"%h\n",h2d);
  if(source_pop)begin
   if(taken>=host_produced*(MODE8?16:24)/10)$fatal(1,"FPGA RF source underflow");
   taken<=taken+1;
  end
  if(unused_pop||peer_wv||wire_valid)$fatal(1,"Inactive wire engine consumed data");
  if(peer_qv)begin
   bits=bits|(64'(peer_data)<<bit_count);bit_count=bit_count+10;
   if(bit_count>=(MODE8?16:24))begin
    if((bits& (MODE8?64'hffff:64'hffffff))!==64'(compressed(samples[rx_samples])))
     $fatal(1,"RF RX sample %d got %h expected %h",rx_samples,bits,compressed(samples[rx_samples]));
    bits=bits>>(MODE8?16:24);bit_count=bit_count-(MODE8?16:24);rx_samples=rx_samples+1;
   end
  end
  if((status&16'h1dfe)!=0||peer_fault||queued>(HOST_BURST?128:63))
   $fatal(1,"RF queue/link fault time=%t status=%h queued=%d peer=%b",$time,status,queued,peer_fault);
 end
 integer trace;
 initial begin
  if(HOST_BURST)trace=$fopen("h2d-words.txt","w");
  $readmemh("samples.hex",samples);$readmemh("words.hex",words);
  #1;rst_n=0;peer_tx_reset=0;peer_rx_reset=0;
  #100;rst_n=1;peer_rx_reset=1;
  @(negedge hclk)en=1;
  #100;@(negedge hclk)begin source_on=1;peer_tx_reset=1;end
  #200000;
  if(tx_samples<7900||rx_samples<7900||!peer_locked||!status[9])$fatal(1,"Insufficient RF service");
  if(HOST_BURST)$fclose(trace);
  $display("DENSE_RF_PASS mode8=%d host_half=%f phase=%f burst=%d tx_samples=%d rx_samples=%d status=%h",MODE8,HOST_HALF,RF_PHASE,HOST_BURST,tx_samples,rx_samples,status);
  $finish;
 end
endmodule
