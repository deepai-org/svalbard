`timescale 1ns/1ps
// USB HS in the macro (macro batch 2026-11-28), end to end through the real host link and pt_core:
//   FPGA H2D words -> host link -> egress -> pt_rep4_tx -> wire_tx_data (USB-02 x4 bit repetition)
//   and the DIG-03 turnaround gate (pt_core ta_mode / ta_go).
// A: hs_repeat, free running: every valid line quad is ten source bits x4, in order (bit 0 first), no gap or repeat.
// B: hs_repeat + turnaround: a staged packet of 24 ten-bit words (6 quads = 240 USB bits) stays in the bank, the line
//    stays idle (no valid quad, wire_idle = 1) for 4 us without ta_go (negative), then one ta_go sends exactly the 240
//    bits x4 and the line goes idle again with no starvation flag; a second packet works the same way.
// C (negative control): the x4 checker applied to the same source without hs_repeat must fail.
// Prints USB_HS_PASS.
module tb_usb_hs;
 reg hclk=0,wclk=0,rclk=0,rst_n=1,en=0,peer_tx_reset=1,peer_rx_reset=1;
 always #1.6 hclk=~hclk;
 initial begin #1.3;forever #10.4 wclk=~wclk;end   // WORD_CLK40 48 MHz (1.92 Gb/s line = 480 Mb/s x4)
 always #12.5 rclk=~rclk;
 function automatic[9:0]src_word(input integer w);src_word=10'((w*389+77)^(w>>3));endfunction
 integer errors=0;
 // ---- three cores: A (repeat), B (repeat + turnaround), C (no repeat)
 integer produced[0:2],taken[0:2];
 wire[9:0]h2d[0:2],d2h[0:2];wire[39:0]txd[0:2];wire txv[0:2],idle[0:2];wire[15:0]st[0:2];
 genvar g;
 generate for(g=0;g<3;g=g+1)begin:c
  wire pop,unused_pop;wire[31:0]q=produced[g]-taken[g];wire[6:0]cnt=q>127?127:q[6:0];
  pt_dense_link_tx peer_tx(hclk,peer_tx_reset,1'b0,src_word(taken[g]),10'd0,cnt,6'd0,4'd0,8'd0,pop,unused_pop,h2d[g]);
  always @(posedge hclk)if(pop)taken[g]<=taken[g]+1;
  pt_transport_harness #(.HS_REPEAT(g!=2),.TA_MODE(g==1)) h(.rst_n(rst_n),.enable(en),.mode8(1'b0),.hclk(hclk),
   .wire_rx_clk(wclk),.wire_tx_clk(wclk),.rf_rx_clk(rclk),.rf_tx_clk(rclk),
   .h2d_word(h2d[g]),.d2h_word(d2h[g]),.wire_rx_data(40'd0),.wire_rx_valid(1'b0),
   .wire_tx_data(txd[g]),.wire_tx_valid(txv[g]),.wire_tx_request(1'b1),
   .rf_rx_sample(24'd0),.rf_rx_valid(1'b0),.rf_tx_sample(),.rf_tx_valid(),
   .rf_tx_request(1'b0),.status(st[g]),.wire_idle(idle[g]),.rf_mute(),.payload_iq(1'b0),.rx_gain(),.rx_gain_active());
 end endgenerate
 // serializer model (as tb_digital_prbs): the word taken at a rising edge (valid && request) is D0..D19 sampled at
 // that edge and D20..D39 half a period later
 reg[19:0]lo[0:2];reg tv[0:2];integer bitpos[0:2],quads[0:2],bad[0:2],k;
 initial for(k=0;k<3;k=k+1)begin bitpos[k]=-1;quads[k]=0;bad[k]=0;produced[k]=0;taken[k]=0;end
 function automatic sbit(input integer b);reg[9:0]w;begin w=src_word(b/10);sbit=w[b%10];end endfunction
 task automatic check_quad(input integer i,input[39:0]q);integer j,s;begin
  // the first valid quad fixes the bit position: find s with q = bits s..s+9 x4
  if(bitpos[i]<0)begin
   for(s=0;s<4000&&bitpos[i]<0;s=s+10)begin
    bitpos[i]=s;for(j=0;j<40;j=j+1)if(q[j]!==sbit(s+j/4))bitpos[i]=-1;
   end
   if(bitpos[i]<0)begin bad[i]=bad[i]+1;bitpos[i]=0;end
  end else for(j=0;j<40;j=j+1)if(q[j]!==sbit(bitpos[i]+j/4))begin bad[i]=bad[i]+1;j=40;end
  bitpos[i]=bitpos[i]+10;quads[i]=quads[i]+1;
 end endtask
 always @(posedge wclk)for(k=0;k<3;k=k+1)begin lo[k]<=txd[k][19:0];tv[k]<=txv[k]&&!idle[k];end
 always @(negedge wclk)for(k=0;k<3;k=k+1)if(tv[k])check_quad(k,{txd[k][39:20],lo[k]});
 integer q0,i,n;reg pace=0;
 always @(posedge wclk)if(pace)begin produced[0]<=produced[0]+1;produced[2]<=produced[2]+4;end   // drain rates: 1 / 4 words per word clock
 initial begin
  #1;rst_n=0;peer_tx_reset=0;peer_rx_reset=0;
  #100;rst_n=1;peer_rx_reset=1;
  @(negedge hclk)en=1;
  #100;@(negedge hclk)begin peer_tx_reset=1;produced[1]=24;pace=1;end
  // B: staged, no release for 4 us
  #4000;
  if(quads[1]!=0)begin errors=errors+1;$display("ERROR B: %0d quads left before ta_go",quads[1]);end
  if(!idle[1])begin errors=errors+1;$display("ERROR B: line not idle while held");end
  if(c[1].h.ta_running)begin errors=errors+1;$display("ERROR B: running before ta_go");end
  $display("B: held 4 us with 24 words staged: quads %0d, idle %b (taken by the link %0d)",quads[1],idle[1],taken[1]);
  for(n=0;n<2;n=n+1)begin
   q0=quads[1];@(posedge wclk);#1 c[1].h.ta_go=1;@(posedge wclk);#1 c[1].h.ta_go=0;
   repeat(60)@(posedge wclk);
   if(quads[1]-q0!=24)begin errors=errors+1;$display("ERROR B packet %0d: %0d line quads after ta_go, expected 24 (6 quads x4)",n,quads[1]-q0);end
   else $display("B packet %0d: 24 line quads = 240 USB bits x4 after one ta_go",n);
   if(!idle[1]||c[1].h.ta_running)begin errors=errors+1;$display("ERROR B: not idle after the packet");end
   if(st[1][11:10]!=0)begin errors=errors+1;$display("ERROR B: starved flag %b",st[1][11:10]);end
   if(n==0)begin produced[1]=48;repeat(200)@(posedge wclk);
    if(quads[1]-q0!=24)begin errors=errors+1;$display("ERROR B: second packet left before ta_go");end end
  end
  #20000;
  if(quads[0]<200||bad[0]!=0)begin errors=errors+1;$display("ERROR A: %0d quads, %0d bad",quads[0],bad[0]);end
  else $display("A: %0d line quads, every one = 10 source bits x4 in order",quads[0]);
  if(bad[1]!=0)begin errors=errors+1;$display("ERROR B: %0d bad quads",bad[1]);end
  if(bad[2]==0)begin errors=errors+1;$display("ERROR C negative control: x4 check passed without hs_repeat");end
  else $display("C negative control: without hs_repeat the x4 check fails (%0d of %0d quads)",bad[2],quads[2]);
  if(errors==0)$display("USB_HS_PASS");else $display("USB_HS_FAIL %0d",errors);
  $finish;
 end
endmodule
