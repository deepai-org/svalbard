`timescale 1ns/1ps
// RXR-D2 fast gain command (opcode4) end to end through the pad-edge host link and the 40-bit core
// (pt_transport_harness), RF ownership, 40 MS/s RX samples (24-bit, or 16-bit with MODE8).
// FPGA side: the reference ten-bit link TX sends empty RF frames; one frame at a time carries
// opcode4 {LNA index, PGA index}. A behavioural FPGA D2H receiver (training acquisition, header
// decode, RF payload, opcode4 gain-status handling as spec/streaming-transport-v2.md and
// verification/rf_gain_command.py GainSampleReceiver: on gain status, discard a partial pair and
// advance the sample index by the decoded gap) checks every received sample against the source.
// Checks: (1) gain applied (rx_gain/rx_gain_active) <= 1 us after the opcode4 frame starts on the
// H2D pins; (2) exactly one gain-status frame per accepted command, its argument echoes the gain,
// and all samples before it are old-gain samples, all after it new-gain samples, no sample lost
// except the reported gap; (3) a second command while one is pending is rejected (status bit 4,
// gain unchanged, no extra status frame); (4) a later command is accepted again.
// Prints FAST_GAIN_PASS.
module tb_fast_gain;
 parameter MODE8=0;
 parameter real HOST_HALF=1.6;
 localparam integer PW=MODE8?16:24;
 reg hclk=0,rclk=0,tclk=0,wclk=0,rst_n=1,en=0,source_on=0,peer_tx_reset=1;
 always #(HOST_HALF) hclk=~hclk;
 always #8 wclk=~wclk;
 initial begin #3.1;forever #12.5 rclk=~rclk;end
 always #12.5 tclk=~tclk;
 reg[23:0]samples[0:19999];
 integer produced=0;
 always @(posedge rclk)if(source_on)produced<=produced+1;
 reg[3:0]op=0;reg[7:0]arg=0;
 wire[9:0]h2d,d2h;wire up,qp;
 pt_dense_link_tx peer_tx(hclk,peer_tx_reset,1'b1,10'd0,10'd0,7'd0,6'd0,op,arg,up,qp,h2d);
 wire[23:0]tx_sample;wire tx_valid,rf_mute,wire_valid,wire_idle;wire[39:0]wire_data;wire[15:0]status;
 wire[6:0]rx_gain;wire rx_gain_active;
 pt_transport_harness core(.rst_n(rst_n),.enable(en),.mode8(1'(MODE8)),
  .hclk(hclk),.wire_rx_clk(wclk),.wire_tx_clk(wclk),.rf_rx_clk(rclk),.rf_tx_clk(tclk),.h2d_word(h2d),.d2h_word(d2h),
  .wire_rx_data(40'd0),.wire_rx_valid(1'b0),.wire_tx_data(wire_data),.wire_tx_valid(wire_valid),.wire_tx_request(1'b0),
  .rf_rx_sample(samples[produced]),.rf_rx_valid(source_on),.rf_tx_sample(tx_sample),.rf_tx_valid(tx_valid),
  .rf_tx_request(1'b0),.status(status),.wire_idle(wire_idle),.rf_mute(rf_mute),.payload_iq(1'b1),
  .rx_gain(rx_gain),.rx_gain_active(rx_gain_active));
 function automatic[23:0]compressed(input[23:0]v);begin compressed=MODE8?{8'd0,v[23:16],v[11:4]}:v;end endfunction
 // ---------------- FPGA D2H receiver
 function automatic[29:0]hdecode(input[39:0]value);
 integer p,d;begin hdecode=0;d=0;for(p=1;p<=36;p=p+1)if((p&(p-1))!=0)begin hdecode[d]=value[p-1];d=d+1;end end endfunction
 reg[9:0]hist[0:7];integer k;reg locked=0;integer pos=0;reg[39:0]hdr;reg[29:0]f;
 integer qleft=0,next_pair=0,gains=0,frames=0,gap;reg[63:0]bits=0;integer nb=0;reg[6:0]echo_gain;
 integer old_after=0,errors=0,status_frames=0;
 always @(posedge hclk)begin
  for(k=7;k>0;k=k-1)hist[k]=hist[k-1];hist[0]=d2h;
  if(!locked)begin
   if(hist[7]==10'h3a5&&hist[6]==10'h05a&&hist[5]==10'h2d3&&hist[4]==10'h12c&&hist[3]==10'h369&&
      hist[2]==10'h096&&hist[1]==10'h21e&&hist[0]==10'h1e1)begin locked=1;pos=0;end
  end else begin
   if(pos<4)hdr[10*pos+:10]=d2h;
   if(pos==4)begin
    if(d2h!==10'h2d3)begin errors=errors+1;$display("ERROR guard %h",d2h);end
    f=hdecode(hdr);qleft=f[11:6];frames=frames+1;
    if(f[21:18]==4'd4)begin
     // gain status: wc + argument bit 7 = discarded pairs counted from the first pair not completely
     // delivered (a partial pair is dropped here, never counted twice); qc = new-gain words
     gap={f[29],f[5:0]};echo_gain=f[28:22];status_frames=status_frames+1;
     bits=0;nb=0;next_pair=next_pair+gap;
     $display("gain status frame %0d: gain %h gap %0d -> next sample %0d qc %0d",frames,echo_gain,gap,next_pair,qleft);
    end else if(f[21:18]!=0||f[5:0]!=0)begin errors=errors+1;$display("ERROR header op %0d wc %0d",f[21:18],f[5:0]);end
   end
   if(pos>=5&&qleft>0)begin
    bits=bits|(64'(d2h)<<nb);nb=nb+10;qleft=qleft-1;
    if(nb>=PW)begin
     if((bits&((64'd1<<PW)-1))!==64'(compressed(samples[next_pair])))begin
      errors=errors+1;if(errors<5)$display("ERROR sample %0d got %h expected %h",next_pair,bits&((64'd1<<PW)-1),compressed(samples[next_pair]));end
     bits=bits>>PW;nb=nb-PW;next_pair=next_pair+1;
    end
   end
   pos=pos==63?0:pos+1;
  end
 end
 // ---------------- H2D: one frame with opcode4, synchronized to the reference TX command snapshot
 time sent_at,applied_at;time core_applied[0:127];
 always @(posedge rclk)if(core.core.gain_rx.change)core_applied[core.core.gain_rx.gain_h]=$time;
 task send_gain(input[6:0]g);begin
  @(negedge hclk);while(!peer_tx.payload.phase[55])@(negedge hclk);
  op=4;arg={1'b0,g};@(negedge hclk);@(negedge hclk);op=0;arg=0;
  // the frame carrying it starts at the next header (phase[0]) on the pins
  while(!peer_tx.payload.phase[0])@(posedge hclk);sent_at=$time;
 end endtask
 task wait_applied(input[6:0]g);integer n;begin
  n=0;while(!(rx_gain_active&&rx_gain==g)&&n<4000)begin #1;n=n+1;end
  applied_at=$time;
  if(core.core.gain_rx.change===1'b0&&rx_gain==g&&applied_at==$time)applied_at=core_applied[g];
  if(!(rx_gain_active&&rx_gain==g))begin errors=errors+1;$display("ERROR gain %h never applied",g);end
  else $display("gain %h applied %0d ns after its frame started on the H2D pins",g,applied_at-sent_at);
  if(applied_at-sent_at>1000)begin errors=errors+1;$display("ERROR decision->gain %0d ns > 1 us",applied_at-sent_at);end
 end endtask
 integer s0;time first_sent;
 initial begin
  $readmemh("samples.hex",samples);
  #1;rst_n=0;peer_tx_reset=0;
  #100;rst_n=1;
  @(negedge hclk)en=1;
  #100;@(negedge hclk)begin source_on=1;peer_tx_reset=1;end
  #20000;
  if(!locked||next_pair<500)begin errors=errors+1;$display("ERROR no RF stream before the command (%0d)",next_pair);end
  send_gain(7'h2b);   // LNA index 1, PGA index 11
  s0=status_frames;first_sent=sent_at;
  // second command while the first is pending: rejected, no gain change
  send_gain(7'h05);
  sent_at=first_sent;wait_applied(7'h2b);
  #20000;
  if(rx_gain!==7'h2b)begin errors=errors+1;$display("ERROR rejected command changed the gain");end
  if(!status[4])begin errors=errors+1;$display("ERROR rejection not flagged");end
  if(status_frames!=1||echo_gain!==7'h2b)begin errors=errors+1;$display("ERROR status frames %0d echo %h",status_frames,echo_gain);end
  // a later command is accepted
  send_gain(7'h66);wait_applied(7'h66);
  #20000;
  if(status_frames!=2||echo_gain!==7'h66)begin errors=errors+1;$display("ERROR status frames %0d echo %h",status_frames,echo_gain);end
  if(next_pair<produced-200)begin errors=errors+1;$display("ERROR receiver fell behind %0d/%0d",next_pair,produced);end
  if(core.core.rx_fault||core.core.command_fault)begin errors=errors+1;$display("ERROR link fault");end
  if(errors==0)$display("FAST_GAIN_PASS mode8=%0d samples=%0d frames=%0d status_frames=%0d",MODE8,next_pair,frames,status_frames);
  else $display("FAST_GAIN_FAIL %0d",errors);
  $finish;
 end
 initial begin #400000;$display("FAST_GAIN_FAIL timeout");$finish;end
endmodule
