`timescale 1ns/1ps
// IX-2 end to end: 3.125 Gb/s wired line (WORD_CLK40 = 78.125 MHz) with the on-chip 8b/10b offload,
// full host rate (312.5 Mword/s, host DDR clock 156.25 MHz), both directions at once:
//   FPGA H2D source -> pad-edge host link -> core egress -> pt_lc_tx (8b/10b encode) -> wire_tx_data
//   -> (line loopback, valid quads only) -> wire_rx_data -> pt_lc_rx (align, decode, repack) ->
//   ingress -> D2H frames -> FPGA receiver.
// The FPGA sends 9-bit symbols {K, byte} packed LSB-first into its ten-bit words at the line's
// payload rate (3.6 words per quad clock = 0.9 x 3.125 Gb/s = 2.8125 Gb/s, 97.6 % of the framed host
// capacity) with K28.5 every 16 symbols and must receive the identical symbol sequence back. Any
// FIFO over/underflow, starvation, link fault or code error fails. Prints LINECODE_STREAM_PASS.
module tb_linecode_stream;
 parameter real HOST_HALF=1.6, WIRE_HALF=6.4;
 parameter integer RUN_NS=120000;
 reg hclk=0,wclk=0,rclk=0,rst_n=1,en=0,peer_tx_reset=1,peer_rx_reset=1,source_on=0;
 always #(HOST_HALF)hclk=~hclk;
 initial begin #1.3;forever #(WIRE_HALF)wclk=~wclk;end
 always #12.5 rclk=~rclk;
 function automatic[8:0]sym(input integer i);
  begin sym=(i%16==0)?9'h1BC:9'(((i*73+11)%251)&8'hff); end endfunction
 // FPGA source words: bit stream of symbols 0,1,2,... cut into ten-bit words
 function automatic[9:0]src_word(input integer w);integer b,s,o;reg[9:0]v;begin
  v=0;for(b=0;b<10;b=b+1)begin s=(10*w+b)/9;o=(10*w+b)%9;v[b]=sym(s)>>o;end src_word=v;end endfunction
 integer produced=0,taken=0,acc=0;
 wire[31:0]queued=produced-taken;
 wire[6:0]source_count=queued>127?127:queued[6:0];
 wire source_pop,unused_pop;wire[9:0]h2d,d2h,peer_data;
 wire peer_wv,peer_qv,peer_cv,peer_fault,peer_locked;wire[3:0]peer_op;wire[7:0]peer_arg;
 pt_dense_link_tx peer_tx(hclk,peer_tx_reset,1'b0,src_word(taken),10'd0,source_count,6'd0,4'd0,8'd0,source_pop,unused_pop,h2d);
 pt_dense_link_rx peer_rx(hclk,peer_rx_reset,1'b0,d2h,1'b1,1'b1,peer_data,peer_wv,peer_qv,peer_cv,peer_fault,peer_locked,peer_op,peer_arg);
 wire[39:0]tx_data;wire tx_valid,wire_idle,rf_valid,rf_mute;wire[23:0]rf_sample;wire[15:0]status;
 // line loopback: the quad taken at a WORD_CLK40 rising edge (low half launched on the falling
 // edge before, high half on that rising edge) is presented to the receiver one quad clock later
 reg[39:0]line_q=0;reg line_v=0;reg[19:0]low_q;
 always @(negedge wclk)low_q<=tx_data[19:0];
 always @(posedge wclk)begin line_v<=tx_valid;line_q<={tx_data[39:20],low_q};end
 pt_transport_harness #(.LINECODE(1)) core(.rst_n(rst_n),.enable(en),.mode8(1'b0),.hclk(hclk),
  .wire_rx_clk(wclk),.wire_tx_clk(wclk),.rf_rx_clk(rclk),.rf_tx_clk(rclk),
  .h2d_word(h2d),.d2h_word(d2h),.wire_rx_data(line_q),.wire_rx_valid(line_v),
  .wire_tx_data(tx_data),.wire_tx_valid(tx_valid),.wire_tx_request(1'b1),
  .rf_rx_sample(24'd0),.rf_rx_valid(1'b0),.rf_tx_sample(rf_sample),.rf_tx_valid(rf_valid),
  .rf_tx_request(1'b0),.status(status),.wire_idle(wire_idle),.rf_mute(rf_mute),.payload_iq(1'b0),
  .rx_gain(),.rx_gain_active());
 // source pacing: 18 words per 5 quad clocks (3.6 words/clock)
 always @(posedge wclk)if(source_on)begin acc=acc+18;produced<=produced+acc/5;acc=acc%5;end
 always @(posedge hclk)if(source_pop)taken<=taken+1;
 // FPGA receiver: unpack 9-bit symbols, lock on the first K28.5, then compare
 reg[63:0]bits=0;integer nb=0,rx_syms=0,ref_i=-1,errors=0,m;reg[8:0]s;
 always @(posedge hclk)if(peer_wv)begin
  bits=bits|(64'(peer_data)<<nb);nb=nb+10;
  while(nb>=9)begin
   s=bits[8:0];bits=bits>>9;nb=nb-9;
   // lock: the first K28.5 is source symbol 16m; m is found from the symbol after it
   if(ref_i==-2)begin
    for(m=0;m<4096&&ref_i<0;m=m+1)if(sym(16*m+1)==s)ref_i=16*m+1;
    if(ref_i<0)begin errors=errors+1;$display("ERROR cannot place symbol %h",s);ref_i=-3;end
   end else if(ref_i==-1&&s==9'h1BC)ref_i=-2;
   else if(ref_i>=0)begin
    if(s!==sym(ref_i))begin errors=errors+1;if(errors<5)$display("ERROR symbol %0d got %h expected %h",ref_i,s,sym(ref_i));end
    ref_i=ref_i+1;rx_syms=rx_syms+1;
   end
   if(ref_i>0&&rx_syms==0)begin ref_i=ref_i+1;rx_syms=1;end   // the placing symbol itself
  end
 end
 always @(posedge hclk)if(source_on&&((status&16'h1dd6)!=0||peer_fault))begin
  errors=errors+1;$display("ERROR status %h fault %b at %t",status,peer_fault,$time);$finish;end
 initial begin
  #1;rst_n=0;peer_tx_reset=0;peer_rx_reset=0;
  #100;rst_n=1;peer_rx_reset=1;
  @(negedge hclk)en=1;
  #100;@(negedge hclk)begin source_on=1;peer_tx_reset=1;end
  #(RUN_NS);
  if(rx_syms<0.8*RUN_NS*0.3125)begin errors=errors+1;$display("ERROR only %0d symbols received",rx_syms);end
  if(!status[5])begin errors=errors+1;$display("ERROR 8b/10b receiver not aligned");end
  if(errors==0)$display("LINECODE_STREAM_PASS symbols=%0d host_words=%0d status=%h",rx_syms,taken,status);
  else $display("LINECODE_STREAM_FAIL %0d",errors);
  $finish;
 end
endmodule
