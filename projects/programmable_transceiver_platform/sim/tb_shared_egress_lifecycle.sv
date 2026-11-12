`timescale 1ns/1ps
// Shared egress lifecycle (stopped-clock disable / re-enable, wired <-> RF owner changes) with VARYING
// data and a sequence check (review TC12: the constant-word version could not see lost, duplicated or
// stale words). The peer sends a running counter on the wired lane and a known word list on the RF
// lane; every word the peer pops after a (re)start is queued, and each output must be exactly the
// next queued data: wired quads = four consecutive popped words (LSB word first), RF samples = the
// next 24 bits of the popped-word bit stream (LSB first, as check_dense_rf_service.py packs it).
module tb_shared_egress_lifecycle;
 reg hclk=0,wclk=0,rclk=0,h_run=1,r_run=1,rst_n=1,en=0,owner=0;
 reg peer_reset=1,wire_request=0,rf_request=0;
 always #1.6 if(h_run)hclk=~hclk;
 always #8 wclk=~wclk;
 always #12.5 if(r_run)rclk=~rclk;
 // peer sources: wired counter, RF word list (pseudo-random, distinct from the counter)
 reg[9:0]wctr=10'h001;reg[9:0]rf_words[0:4095];integer rtaken=0,i;
 initial for(i=0;i<4096;i=i+1)rf_words[i]=10'((i*467+123)^(i>>3));
 // RF source rate: the FPGA produces 24 bits per RF sample period (40 MS/s), as tb_dense_rf_service; the
 // peer may only send words that exist (an unlimited source overruns the RF ingress: rx_fault).
 integer rf_prod=0,rf_base=0;
 always @(posedge rclk)if(owner&&checking)rf_prod<=rf_prod+1;
 wire[31:0]rf_avail=rf_prod*24/10-(rtaken-rf_base);
 wire[5:0]rf_count=rf_avail>63?6'd63:rf_avail[5:0];
 wire[9:0]h2d,d2h;wire wp,qp;
 pt_dense_link_tx peer(hclk,peer_reset,owner,wctr,rf_words[rtaken[11:0]],7'd59,rf_count,
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
 // reference queues of popped words (cleared at every restart; a pop before the restart is flushed
 // with the owner reset and never reaches the outputs of the next owner)
 reg[9:0]wq[0:65535];integer wq_wr=0,wq_rd=0;
 reg[9:0]rq[0:65535];integer rq_wr=0,rq_rd=0;
 reg[63:0]rbits=0;integer rbit_n=0;
 always @(posedge hclk)begin
  if(wp)begin wq[wq_wr]=wctr;wq_wr=wq_wr+1;wctr<=wctr+1'b1;end
  if(qp)begin rq[rq_wr]=rf_words[rtaken[11:0]];rq_wr=rq_wr+1;rtaken<=rtaken+1;end
 end
 integer wquads=0,rsamples=0,phase=0;reg checking=0;
 // wired output check: valid sampled on the rising edge, data on the following falling edge (as the
 // wired serializer interface: pt_core wired TX output stage)
 reg wv_r=0;always @(posedge wclk)wv_r<=checking&&wire_valid;
 always @(negedge wclk)if(checking&&wv_r)begin
  if(owner)$fatal(1,"Wired output valid while the RF lane owns the storage");
  if(wq_wr-wq_rd<4)$fatal(1,"Wired quad %0d with only %0d popped words outstanding (stale/duplicated data %h)",wquads,wq_wr-wq_rd,wire_data);
  if(wire_data!=={wq[wq_rd+3],wq[wq_rd+2],wq[wq_rd+1],wq[wq_rd]})
   $fatal(1,"Wired quad %0d (phase %0d) got %h expected %h",wquads,phase,wire_data,{wq[wq_rd+3],wq[wq_rd+2],wq[wq_rd+1],wq[wq_rd]});
  wq_rd=wq_rd+4;wquads=wquads+1;
 end
 // RF output check
 always @(posedge rclk)if(checking&&rf_valid)begin
  if(!owner)$fatal(1,"RF output valid while the wired lane owns the storage");
  while(rbit_n<24)begin
   if(rq_rd>=rq_wr)$fatal(1,"RF sample %0d with no popped data outstanding (stale %h)",rsamples,rf_data);
   rbits=rbits|(64'(rq[rq_rd])<<rbit_n);rbit_n=rbit_n+10;rq_rd=rq_rd+1;
  end
  if(rf_data!==rbits[23:0])$fatal(1,"RF sample %0d (phase %0d) got %h expected %h",rsamples,phase,rf_data,rbits[23:0]);
  rbits=rbits>>24;rbit_n=rbit_n-24;rsamples=rsamples+1;
 end
 task automatic reset_refs;
 begin wq_wr=0;wq_rd=0;rq_wr=0;rq_rd=0;rbits=0;rbit_n=0;rf_prod=0;rf_base=rtaken;end endtask
 task automatic stop_and_disable;
 begin
  checking=0;
  @(negedge hclk);h_run=0;peer_reset=0;
  #1;en=0;
  // The host/pair clocks are stopped: reset must still flush immediately.
  #1;if(wire_valid||rf_valid||status[9])$fatal(1,"Disable failed with stopped host clock wv=%b rv=%b st=%h",wire_valid,rf_valid,status);
 end endtask
 task automatic restart;
 begin
  #100;en=1;
  #100;if(wire_valid||rf_valid)$fatal(1,"Stale output appeared before host clock restart");
  reset_refs();checking=1;
  h_run=1;
  #100;@(negedge hclk);peer_reset=1;
 end endtask
 task automatic run_until(input integer wq_n,input integer rs_n);
 begin
  fork : w
   begin wait(wquads>=wq_n&&rsamples>=rs_n);disable w;end
   begin #60000;$fatal(1,"Phase %0d timeout: %0d wired quads, %0d RF samples",phase,wquads,rsamples);end
  join
 end endtask
 initial begin
  #1;rst_n=0;peer_reset=0;
  #100;rst_n=1;en=1;reset_refs();checking=1;wire_request=1;
  #100;@(negedge hclk);peer_reset=1;
  phase=1;run_until(24,0);
  stop_and_disable();owner=1;wire_request=0;rf_request=1;
  phase=2;restart();run_until(24,24);
  @(negedge rclk);r_run=0;
  stop_and_disable();owner=0;wire_request=1;rf_request=0;
  phase=3;restart();run_until(48,24);
  // a second RF period after a wired period with the RF clock left stopped until after re-enable
  stop_and_disable();owner=1;wire_request=0;rf_request=1;
  phase=4;restart();#400;r_run=1;run_until(48,48);
  if(status&16'h1dfe)$fatal(1,"Lifecycle fault %h",status);
  $display("SHARED_EGRESS_LIFECYCLE_PASS varying-data sequence check: %0d wired quads, %0d RF samples over 4 phases (stopped-host disable, stopped-RF mux change, both owner resets)",wquads,rsamples);
  $finish;
 end
endmodule
