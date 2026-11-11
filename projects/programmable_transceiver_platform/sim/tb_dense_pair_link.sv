`timescale 1ns/1ps
// AC-1 link loopback: quad framer -> pad-edge D2H (XOR-prefix 4:1 gearbox, DDR launch, forwarded
// clock) -> pins -> pad-edge H2D (DDR capture, 1:4 gearbox, quad FIFO) of a second host link on an
// independently phased clock -> quad deframer with four-rotation training acquisition. The capture
// host link is released 0..3 word periods later relative to the launch host link (both before
// the framers), so every word rotation of the quad stream is exercised; the capture clock phase
// and both pin modes (DDR, SDR) are swept.
module tb_dense_pair_link;
 reg wc=0,rc=0,tx_rst=1,rx_rst=1,launch_rst=1,capture_rst=1,owner=0,mode_sdr=0;
 real phase;integer capture_offset;
 wire tc,rcc;wire[39:0]tx_quad,rx_quad,data;
 // host DDR clocks (link_clk) = word clock / 2; the word clocks drive the SDR forwarded clock
 reg wd=0,rd=0;always @(posedge wc)wd<=~wd;always @(posedge rc)rd<=~rd;
 wire[9:0]pins;wire pin_clk,oe,wp,qp,cv,fault,locked;
 wire[2:0]wcount,qcount;wire[3:0]opcode;wire[7:0]argument;
 integer source_quad=0,received=0,commands=0,cycles=0,fo,k;
 function automatic[9:0]sample(input integer index);begin sample=(index*37+19)%1024;end endfunction
 wire[39:0]source={sample(4*source_quad+3),sample(4*source_quad+2),sample(4*source_quad+1),sample(4*source_quad)};
 pt_host_link launch(.rst_n(launch_rst),.mode({1'b0,mode_sdr}),.d2h_enable(1'b1),.h2d_clk(1'b0),.h2d_pin(10'd0),.link_clk(wd),.word_clk(wc),
  .core_clk(tc),.core_rst_n(),.h2d_quad(),.d2h_quad(tx_quad),.d2h_pin(pins),.d2h_clk_pin(pin_clk),.d2h_stagger(1'b0),.d2h_oe(oe),.h2d_overflow(),.h2d_underflow());
 // DDR: the forwarded clock is edge-aligned (produced like the data); the receiver (FPGA model here)
 // centres it with a quarter-period (half-word) delay. SDR: the inverted word clock, already mid-word.
 wire #(1.6) pin_clk_centred=pin_clk;
 wire rx_pin_clk=mode_sdr?pin_clk:pin_clk_centred;
 pt_host_link capture(.rst_n(capture_rst),.mode({1'b0,mode_sdr}),.d2h_enable(1'b0),.h2d_clk(rx_pin_clk),.h2d_pin(pins),.link_clk(rd),.word_clk(rc),
  .core_clk(rcc),.core_rst_n(),.h2d_quad(rx_quad),.d2h_quad(40'd0),.d2h_pin(),.d2h_clk_pin(),.d2h_stagger(1'b0),.d2h_oe(),.h2d_overflow(),.h2d_underflow());
 pt_quad_link_tx tx(tc,tx_rst,owner,source,source,6'd32,6'd32,4'd0,8'd0,wp,qp,tx_quad,1'b0,7'd0,1'b0,6'd0,7'd0,);
 pt_quad_link_rx rx(rcc,rx_rst,owner,rx_quad,1'b1,1'b1,data,wcount,qcount,cv,fault,locked,opcode,argument);
 always #1.6 wc=~wc;
 initial begin
  if(!$value$plusargs("PHASE=%f",phase))phase=0.8;
  if(!$value$plusargs("OFFSET=%d",capture_offset))capture_offset=0;
  if(!$value$plusargs("OWNER=%d",owner))owner=0;
  if(!$value$plusargs("SDR=%d",mode_sdr))mode_sdr=0;
  #(phase);forever #1.6 rc=~rc;
 end
 always @(posedge tc)if(tx_rst)begin
  if((owner&&wp)||(!owner&&qp))$fatal(1,"Inactive source popped");
  if(wp||qp)source_quad<=source_quad+1;
 end
 always @(posedge rcc)if(rx_rst)begin
  cycles=cycles+1;
  if(capture.h2d.overflow||capture.h2d.underflow)$fatal(1,"H2D quad FIFO over/underflow");
  if(fault)$fatal(1,"Quad link fault, phase=%f offset=%d owner=%d sdr=%d",phase,capture_offset,owner,mode_sdr);
  if((owner&&wcount)||(!owner&&qcount))$fatal(1,"Inactive destination accepted");
  if(cv)begin
   if(opcode||argument)$fatal(1,"Incorrect command");
   commands=commands+1;
  end
  for(k=0;k<4;k=k+1)if(k<wcount+qcount)begin
   if(data[10*k+:10]!==sample(received))$fatal(1,"Payload mismatch at %d",received);
   received=received+1;
  end
  if(commands==200)begin
   if(!locked||received<11000)$fatal(1,"Insufficient link traffic");
   fo=$fopen("result.txt","w");$fwrite(fo,"%d %d %d %d\n",received,commands,source_quad,capture.h2d.wb);$fclose(fo);
   $display("PASS quad link loopback: %d words %d frames rotation %d",received,commands,rx.rotation);$finish;
  end
  if(cycles>4000)$fatal(1,"Link failed to acquire/progress");
 end
 initial begin
  #0.1;tx_rst=0;rx_rst=0;launch_rst=0;capture_rst=0;
  #1.9;launch_rst=1;
  #(60.0+capture_offset*3.2);capture_rst=1;
  #(100.0-capture_offset*3.2);rx_rst=1;
  #40.0;tx_rst=1;
 end
 initial begin #60000;$fatal(1,"Quad link timeout");end
endmodule
