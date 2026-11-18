`timescale 1ns/1ps
// IX-11 fast in-band slicer thresholds (opcode 5 = VTH_A, opcode 6 = VTH_B; spec/streaming-transport-v2.md
// "Commands") end to end through the pad-edge host link and the 40-bit core (pt_transport_harness).
// IQ=0 (wired ownership): each command loads its code and raises its override flag, without a link or command
//   fault; a second command replaces the code; disable clears both overrides and restores mid-scale.
// IQ=1 (I/Q ownership): the commands are context-illegal and must fault, leaving the thresholds untouched.
// PAY=1 (wired ownership only): the peer sends full wired frames (40 payload words each) and the wired TX side
//   drains them, so the commands ride on payload-carrying frames.
// Every reserved opcode (3, 7..15) must fault. Prints FAST_VTH_PASS.
// Not covered here: the override mux to the DAC pins (pt_ctl_decode) and the IX-11 latency / update-rate numbers.
module tb_fast_vth;
 parameter IQ=0;
 parameter PAY=0;
 parameter real HOST_HALF=1.6;
 reg hclk=0,rclk=0,wclk=0,rst_n=1,en=0,peer_tx_reset=1;
 always #(HOST_HALF) hclk=~hclk;
 always #8 wclk=~wclk;
 always #12.5 rclk=~rclk;
 reg[3:0]op=0;reg[7:0]arg=0;
 wire[9:0]h2d,d2h;wire up,qp;
 reg[9:0]wd=0;always @(posedge hclk)if(up)wd<=wd+1'b1;
 pt_dense_link_tx peer_tx(hclk,peer_tx_reset,PAY?1'(IQ):1'b1,wd,10'd0,PAY?7'd40:7'd0,6'd0,op,arg,up,qp,h2d);
 wire[15:0]status;
 pt_transport_harness core(.rst_n(rst_n),.enable(en),.mode8(1'b0),
  .hclk(hclk),.wire_rx_clk(wclk),.wire_tx_clk(wclk),.rf_rx_clk(rclk),.rf_tx_clk(rclk),.h2d_word(h2d),.d2h_word(d2h),
  .wire_rx_data(40'd0),.wire_rx_valid(1'b0),.wire_tx_data(),.wire_tx_valid(),.wire_tx_request(1'(PAY)),
  .rf_rx_sample(24'd0),.rf_rx_valid(1'b0),.rf_tx_sample(),.rf_tx_valid(),
  .rf_tx_request(1'b0),.status(status),.wire_idle(),.rf_mute(),.payload_iq(1'(IQ)),
  .rx_gain(),.rx_gain_active());
 integer errors=0,rop;
 wire faulted=core.core.rx_fault||core.core.command_fault;
 task send(input[3:0]o,input[7:0]a);begin
  @(negedge hclk);while(!peer_tx.payload.phase[55])@(negedge hclk);
  op=o;arg=a;@(negedge hclk);@(negedge hclk);op=0;arg=0;
  #2000;
 end endtask
 task bring_up;begin
  en=0;peer_tx_reset=0;#200;rst_n=0;#100;rst_n=1;
  @(negedge hclk)en=1;
  #100;@(negedge hclk)peer_tx_reset=1;
  #20000;
  if(faulted)begin errors=errors+1;$display("ERROR fault before any command");end
  if(core.core.vth_fast!==2'b00||core.core.vth_a!==8'd128||core.core.vth_b!==8'd128)begin
   errors=errors+1;$display("ERROR thresholds not at their reset state");end
 end endtask
 initial begin
  #1;bring_up;
  if(IQ==0)begin
   send(4'd5,8'h5a);
   if(core.core.vth_fast!==2'b01||core.core.vth_a!==8'h5a||core.core.vth_b!==8'd128)begin
    errors=errors+1;$display("ERROR opcode 5: fast %b a %h b %h",core.core.vth_fast,core.core.vth_a,core.core.vth_b);end
   send(4'd6,8'hc3);
   if(core.core.vth_fast!==2'b11||core.core.vth_a!==8'h5a||core.core.vth_b!==8'hc3)begin
    errors=errors+1;$display("ERROR opcode 6: fast %b a %h b %h",core.core.vth_fast,core.core.vth_a,core.core.vth_b);end
   send(4'd5,8'h00);send(4'd6,8'hff);
   if(core.core.vth_a!==8'h00||core.core.vth_b!==8'hff)begin errors=errors+1;$display("ERROR second load");end
   if(faulted)begin errors=errors+1;$display("ERROR fault after legal threshold commands (rx %b cmd %b)",core.core.rx_fault,core.core.command_fault);end
   // disable drops the overrides
   @(negedge hclk)en=0;#500;
   if(core.core.vth_fast!==2'b00||core.core.vth_a!==8'd128||core.core.vth_b!==8'd128)begin
    errors=errors+1;$display("ERROR overrides survive disable");end
   // reserved opcodes fault
   for(rop=3;rop<16;rop=rop+1)if(rop==3||rop>=7)begin
    bring_up;send(rop[3:0],8'h00);
    if(!faulted)begin errors=errors+1;$display("ERROR reserved opcode %0d accepted",rop);end
   end
  end else begin
   send(4'd5,8'h5a);
   if(!faulted)begin errors=errors+1;$display("ERROR opcode 5 accepted in I/Q ownership");end
   if(core.core.vth_fast!==2'b00||core.core.vth_a!==8'd128)begin errors=errors+1;$display("ERROR threshold changed in I/Q ownership");end
   bring_up;send(4'd6,8'h5a);
   if(!faulted)begin errors=errors+1;$display("ERROR opcode 6 accepted in I/Q ownership");end
   if(core.core.vth_fast!==2'b00||core.core.vth_b!==8'd128)begin errors=errors+1;$display("ERROR threshold changed in I/Q ownership");end
  end
  if(errors==0)$display("FAST_VTH_PASS iq=%0d",IQ);else $display("FAST_VTH_FAIL %0d",errors);
  $finish;
 end
 initial begin #1500000;$display("FAST_VTH_FAIL timeout");$finish;end
endmodule
