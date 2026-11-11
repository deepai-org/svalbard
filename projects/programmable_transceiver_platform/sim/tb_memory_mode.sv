// MEMORY v3 (AC-1 sharing S1): capture/playback through the shared transport banks, SPI only.
// The host clock is held at 0 for the whole bench (host link absent: the fallback case).
//  1. wired playback one-shot: quads 0..last leave on wire_tx_data in order, then valid drops;
//  2. wired playback loop: the sequence repeats;
//  3. wired capture: 28 lane quads fill the ingress bank, capture_done rises, the SPI peek port
//     returns quad i at index i, and later lane quads are not stored;
//  4. radio capture -> radio playback round trip: IQ samples packed into quads by the shared lane,
//     captured, written back as playback quads over the SPI port, and replayed through the
//     unpacker: exactly the 40 samples of the 24 egress quads are replayed, equal to the captured ones.
`timescale 1ns/1ps
module tb_memory_mode;
 reg rst_n=1,enable=0,payload_iq=0,wclk=0,rclk=0,fclk=0,sclk=1;
 reg cap=0,play=0,loop=0,we=0;reg[4:0]last=0,idx=0;reg[39:0]wd=0;
 reg[39:0]wire_rx_data=0;reg wire_rx_valid=0;reg[23:0]rf_rx_sample=0;reg rf_rx_valid=0;
 wire[39:0]wire_tx_data,d2h_quad,rdata;wire wire_tx_valid,rf_tx_valid,wire_idle,rf_mute,gact,done;
 wire[23:0]rf_tx_sample;wire[15:0]status;wire[6:0]gain;
 pt_core core(.rst_n(rst_n),.enable(enable),.mode8(1'b0),.host_clk(1'b0),
  .wire_rx_clk(wclk),.wire_tx_clk(wclk),.rf_rx_clk(rclk),.rf_tx_clk(fclk),
  .h2d_quad(40'd0),.d2h_quad(d2h_quad),.wire_rx_data(wire_rx_data),.wire_rx_valid(wire_rx_valid),
  .wire_tx_data(wire_tx_data),.wire_tx_valid(wire_tx_valid),.wire_tx_request(1'b1),
  .rf_rx_sample(rf_rx_sample),.rf_rx_valid(rf_rx_valid),.rf_tx_sample(rf_tx_sample),.rf_tx_valid(rf_tx_valid),
  .rf_tx_request(1'b1),.status(status),.wire_idle(wire_idle),.rf_mute(rf_mute),.payload_iq(payload_iq),
  .linecode(1'b0),.rx_gain(gain),.rx_gain_active(gact),
  .mem_capture(cap),.mem_play(play),.mem_loop(loop),.mem_last(last),.spi_clk(sclk),.mem_we(we),.mem_idx(idx),
  .mem_wdata(wd),.mem_rdata(rdata),.capture_done(done),
  .pat_sel(1'b0),.pat_word(40'd0),.pat_valid(1'b0),.pat_idle(1'b1),.wire_req_int());
 always #8 wclk=~wclk;
 always #12.5 rclk=~rclk;
 always #12.5 fclk=~fclk;
 integer errors=0,i,k,n,got;
 reg[39:0]q[0:27];reg[39:0]seen[0:255];reg[23:0]smp[0:63];reg[23:0]out[0:63];
 task spi_write(input[4:0]a,input[39:0]d);begin
  idx=a;wd=d;we=1;#50 sclk=0;#50 we=0;sclk=1;#20;end endtask
 task reset_all;begin enable=0;#200 rst_n=0;#100 rst_n=1;#100;end endtask
 // wired output, sampled like the serializer contract (tb_digital_wire40): the quad taken at a
 // rising edge is {high half after that edge, low half before it}
 integer nseen;reg wtake=0,wcol=0;reg[19:0]wlow;
 always @(posedge wclk)begin wtake<=wire_tx_valid;wlow<=wire_tx_data[19:0];end
 always @(negedge wclk)if(wcol&&wtake&&nseen<256)begin seen[nseen]={wire_tx_data[39:20],wlow};nseen=nseen+1;end
 task collect_wire(input integer cycles);begin nseen=0;wcol=1;repeat(cycles)@(posedge wclk);wcol=0;end endtask
 task check_sequence(input integer len,input integer reps);integer s,r,j,ok;begin
  s=-1;for(j=0;j<nseen&&s<0;j=j+1)if(seen[j]===q[0])s=j;
  if(s<0)begin errors=errors+1;$display("ERROR playback: first quad never sent (%0d valid quads)",nseen);end
  else begin ok=1;
   for(r=0;r<reps;r=r+1)for(j=0;j<len;j=j+1)
    if(s+r*len+j>=nseen||seen[s+r*len+j]!==q[j])ok=0;
   if(!ok)begin errors=errors+1;$display("ERROR playback: sequence mismatch (start %0d, %0d valid)",s,nseen);end
   if(reps==1&&nseen!=s+len)begin errors=errors+1;$display("ERROR one-shot: %0d valid quads after the last",nseen-s-len);end
  end end endtask
 initial begin
  #5 rst_n=0;#100 rst_n=1;
  // ---- 1. wired playback, one shot
  for(i=0;i<28;i=i+1)q[i]={$random,$random}&40'hffffffffff;
  play=1;last=5;loop=0;
  for(i=0;i<6;i=i+1)spi_write(i,q[i]);
  #100 enable=1;collect_wire(60);
  check_sequence(6,1);
  $display("wired playback one-shot: %0d valid quads",nseen);
  // ---- 2. wired playback, loop (bank contents survive disable)
  reset_all;loop=1;#100 enable=1;collect_wire(60);
  check_sequence(6,5);
  $display("wired playback loop: %0d valid quads",nseen);
  // ---- 3. wired capture
  reset_all;play=0;loop=0;cap=1;#100 enable=1;
  repeat(10)@(posedge wclk);
  for(i=0;i<34;i=i+1)begin @(negedge wclk);wire_rx_data=i<28?q[i]:~q[i%28];wire_rx_valid=1;end
  @(negedge wclk);wire_rx_valid=0;repeat(5)@(posedge wclk);
  if(!done)begin errors=errors+1;$display("ERROR capture: done not set");end
  got=0;for(i=0;i<28;i=i+1)begin idx=i;#20;if(rdata===q[i])got=got+1;end
  if(got!=28)begin errors=errors+1;$display("ERROR capture: %0d/28 quads read back",got);end
  $display("wired capture: done=%0d, %0d/28 quads via SPI peek",done,got);
  // ---- 4. radio capture -> playback round trip
  reset_all;payload_iq=1;cap=1;#100 enable=1;repeat(10)@(posedge rclk);
  for(i=0;i<64;i=i+1)begin smp[i]={$random}&24'hffffff;end
  for(i=0;i<64;i=i+1)begin @(negedge rclk);rf_rx_sample=smp[i];rf_rx_valid=1;end
  @(negedge rclk);rf_rx_valid=0;repeat(5)@(posedge rclk);
  if(!done)begin errors=errors+1;$display("ERROR radio capture: done not set");end
  for(i=0;i<28;i=i+1)begin idx=i;#20;q[i]=rdata;end
  enable=0;#200;cap=0;play=1;last=23;loop=0;
  for(i=0;i<24;i=i+1)spi_write(i,q[i]);
  #100 enable=1;n=0;
  repeat(200)begin @(posedge fclk);if(rf_tx_valid&&n<64)begin out[n]=rf_tx_sample;n=n+1;end end
  got=0;for(i=0;i<40;i=i+1)if(out[i]===smp[i])got=got+1;
  if(got!=40||n!=40)begin errors=errors+1;$display("ERROR radio round trip: %0d/40 samples match (%0d sent)",got,n);end
  $display("radio capture->playback: %0d samples replayed, %0d/40 match",n,got);
  if(errors==0)$display("MEMORY_MODE_PASS");else $display("MEMORY_MODE_FAIL %0d",errors);
  $finish;
 end
endmodule
