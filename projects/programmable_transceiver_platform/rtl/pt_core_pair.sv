// Full exclusive streaming core with paired transport engines. External
// host clocks/words retain their 312.5 MHz contract; FIFO readers, framing
// and RF conversion run on actual related divide-by-two clocks.
module pt_core_pair #(parameter EGRESS_A=5,RF_IN_A=3,IQ_TX_DEPTH=12,IQ_RX_DEPTH=7)(input wire rst_n,enable,mode8,
 input wire host_tx_clk,host_rx_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,
 input wire[9:0]h2d_word,output wire[9:0]d2h_word,
 input wire[19:0]wire_rx_data,input wire wire_rx_valid,
 output wire[19:0]wire_tx_data,output wire wire_tx_valid,input wire wire_tx_request,
 input wire[23:0]rf_rx_sample,input wire rf_rx_valid,
 output wire[23:0]rf_tx_sample,output wire rf_tx_valid,input wire rf_tx_request,
 output wire[15:0]status,output wire wire_idle,rf_mute,input wire payload_iq);
 wire tx_clk,rx_clk;wire[19:0]d2h_pair,h2d_pair,unused_pair;wire[9:0]unused_word;
 pt_pair_word_boundary tx_boundary(host_tx_clk,rst_n,d2h_pair,d2h_word,10'd0,unused_pair,tx_clk);
 pt_pair_word_boundary rx_boundary(host_rx_clk,rst_n,20'd0,unused_word,h2d_word,h2d_pair,rx_clk);
 wire et,er,ewr,ewt,err,ert;
 pt_enable_release e0(tx_clk,rst_n,enable,et);pt_enable_release e1(rx_clk,rst_n,enable,er);
 pt_sync_bit e2(wire_rx_clk,rst_n,enable,ewr);pt_sync_bit e3(wire_tx_clk,rst_n,enable,ewt);
 pt_sync_bit e4(rf_rx_clk,rst_n,enable,err);pt_sync_bit e5(rf_tx_clk,rst_n,enable,ert);
 wire trst=rst_n&&et,rrst=rst_n&&er;
 wire[19:0]wr_head,iq_head;wire[6:0]wr_pairs;wire[4:0]iq_pairs;
 wire wr_pop,iq_pop,wr_empty,wr_full,wr_ov,wr_un;
 pt_async_fifo #(.W(20),.A(6),.REG_OUT(1)) wire_in(
  .wr_clk(wire_rx_clk),.rd_clk(tx_clk),.rst_n(trst),
  .din(wire_rx_data),.push(wire_rx_valid&&ewr&&!payload_iq),.pop(wr_pop),
  .dout(wr_head),.full(wr_full),.empty(wr_empty),.wr_count(),.rd_count(wr_pairs),
  .overflow(wr_ov),.underflow(wr_un));
 wire[23:0]rf_head;wire rf_empty,rf_full,rf_pop,rf_ov,rf_un;
 wire[23:0]compressed=mode8?{8'd0,rf_rx_sample[23:16],rf_rx_sample[11:4]}:rf_rx_sample;
 pt_async_fifo #(.W(24),.A(RF_IN_A),.REG_OUT(1)) rf_in(
  .wr_clk(rf_rx_clk),.rd_clk(tx_clk),.rst_n(trst),
  .din(compressed),.push(rf_rx_valid&&err&&payload_iq),.pop(rf_pop),
  .dout(rf_head),.full(rf_full),.empty(rf_empty),.wr_count(),.rd_count(),
  .overflow(rf_ov),.underflow(rf_un));
 wire[23:0]packed_pair;wire packed_valid,pack_ready,iq_full,iq_empty,iq_ov,iq_un;
 assign rf_pop=!rf_empty&&pack_ready;
 pt_pair_gearbox #(.PACK(1)) packer(tx_clk,trst,mode8,rf_head,!rf_empty,pack_ready,
  packed_pair,packed_valid,!iq_full);
 // The receive queue reserves its own spare pair so frame admission depends
 // only on the registered full flag, independently of downstream readiness.
 pt_sync_fifo #(.W(20),.A(4),.DEPTH(IQ_TX_DEPTH)) iq_in(tx_clk,trst,packed_valid&&!iq_full,iq_pop,
  packed_pair[19:0],iq_head,iq_full,iq_empty,iq_pairs,iq_ov,iq_un);
 pt_dense_pair_link_tx frame_tx(tx_clk,trst,payload_iq,wr_head,iq_head,wr_pairs,{2'd0,iq_pairs},
  4'd0,8'd0,wr_pop,iq_pop,d2h_pair);
 wire[19:0]received;wire[1:0]wire_words,iq_words;
 wire wire_ready,iq_ready,command_valid,rx_fault,locked;
 wire[3:0]opcode;wire[7:0]argument;
 pt_dense_pair_link_rx frame_rx(rx_clk,rrst,payload_iq,h2d_pair,wire_ready,iq_ready,
  received,wire_words,iq_words,command_valid,rx_fault,locked,opcode,argument);
 wire[19:0]wire_pair,iq_pair;wire wire_push,iq_push;
 pt_pair_collect collect_wire(rx_clk,rrst,received,wire_words,wire_pair,wire_push);
 pt_pair_collect collect_iq(rx_clk,rrst,received,iq_words,iq_pair,iq_push);
 wire wire_out_full,wire_out_empty,wire_out_ov,wire_out_un;wire[EGRESS_A:0]wire_out_count;
 reg wire_running,rf_running,wire_starved,rf_starved;
 reg idle_command,mute_command,command_fault;
 wire rx_fault_wire,rx_fault_rf,idle_sync,mute_sync;
 pt_sync_bit f0(wire_tx_clk,rst_n,rx_fault||command_fault,rx_fault_wire);
 pt_sync_bit f1(rf_tx_clk,rst_n,rx_fault||command_fault,rx_fault_rf);
 pt_sync_bit f2(wire_tx_clk,rst_n,idle_command,idle_sync);
 pt_sync_bit f3(rf_tx_clk,rst_n,mute_command,mute_sync);
 assign wire_ready=!wire_out_full;
 wire[23:0]egress_head;
 assign wire_tx_data=payload_iq?20'd0:egress_head[19:0];
 assign wire_tx_valid=wire_running&&!wire_out_empty&&!rx_fault_wire&&!wire_starved;
 assign wire_idle=!wire_tx_valid||idle_sync;
 localparam IQ_RX_A=IQ_RX_DEPTH<2?1:$clog2(IQ_RX_DEPTH);
 wire[19:0]iq_queue;wire iq_qfull,iq_qempty,iq_qov,iq_qun;
 wire unpack_ready,unpacked_valid,rf_out_full,rf_out_empty,rf_out_ov,rf_out_un;
 wire[23:0]unpacked_sample,rf_out_head;wire[EGRESS_A:0]rf_out_count;
 pt_sync_fifo #(.W(20),.A(IQ_RX_A),.DEPTH(IQ_RX_DEPTH)) iq_receive(
  .clk(rx_clk),.rst_n(rrst),.push(iq_push),.pop(!iq_qempty&&unpack_ready),
  .din(iq_pair),.dout(iq_queue),.full(iq_qfull),.empty(iq_qempty),
  .count(),.overflow(iq_qov),.underflow(iq_qun));
 assign iq_ready=!iq_qfull;
 pt_pair_gearbox #(.PACK(0)) unpacker(rx_clk,rrst,mode8,{4'd0,iq_queue},!iq_qempty,unpack_ready,
  unpacked_sample,unpacked_valid,!rf_out_full);
 // Exclusive ownership permits one storage bank. Owner changes occur only
 // while disabled; asynchronous disable holds both FIFO domains reset even
 // if the pair clock has stopped before the selected output clock changes.
 wire egress_clk,egress_full,egress_empty,egress_ov,egress_un;
 wire[EGRESS_A:0]egress_count;
`ifdef SYNTHESIS
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__mux2_1 egress_clock_mux(
  .I0(wire_tx_clk),.I1(rf_tx_clk),.S(payload_iq),.Z(egress_clk));
`else
 assign egress_clk=payload_iq?rf_tx_clk:wire_tx_clk;
`endif
 wire egress_push=payload_iq?(unpacked_valid&&!egress_full):wire_push;
 wire egress_pop=payload_iq?(rf_tx_request&&rf_running&&!egress_empty):
                               (wire_tx_request&&wire_running&&!egress_empty);
 pt_async_fifo #(.W(24),.A(EGRESS_A),.REG_OUT(1)) egress(
  .wr_clk(rx_clk),.rd_clk(egress_clk),.rst_n(rrst),
  .din(payload_iq?unpacked_sample:{4'd0,wire_pair}),.push(egress_push),.pop(egress_pop),
  .dout(egress_head),.full(egress_full),.empty(egress_empty),.wr_count(),.rd_count(egress_count),
  .overflow(egress_ov),.underflow(egress_un));
 assign wire_out_full=!payload_iq&&egress_full;
 assign wire_out_empty=payload_iq||egress_empty;
 assign wire_out_count=payload_iq?0:egress_count;
 assign wire_out_ov=!payload_iq&&egress_ov;
 assign wire_out_un=!payload_iq&&egress_un;
 assign rf_out_full=payload_iq&&egress_full;
 assign rf_out_empty=!payload_iq||egress_empty;
 assign rf_out_count=payload_iq?egress_count:0;
 assign rf_out_ov=payload_iq&&egress_ov;
 assign rf_out_un=payload_iq&&egress_un;
 assign rf_out_head=payload_iq?egress_head:24'd0;
 assign rf_tx_sample=mode8?{rf_out_head[15:8],4'd0,rf_out_head[7:0],4'd0}:rf_out_head;
 assign rf_tx_valid=rf_running&&!rf_out_empty&&!rx_fault_rf&&!rf_starved;
 assign rf_mute=!rf_tx_valid||mute_sync;
 always @(posedge wire_tx_clk or negedge rst_n)begin
  if(!rst_n)begin wire_running<=0;wire_starved<=0;end
  else if(!ewt)begin wire_running<=0;wire_starved<=0;end
  else if(!wire_running&&wire_out_count>=16)wire_running<=1;
  else if(wire_running&&wire_tx_request&&wire_out_empty)wire_starved<=1;
 end
 always @(posedge rf_tx_clk or negedge rst_n)begin
  if(!rst_n)begin rf_running<=0;rf_starved<=0;end
  else if(!ert)begin rf_running<=0;rf_starved<=0;end
  else if(!rf_running&&rf_out_count>=8)rf_running<=1;
  else if(rf_running&&rf_tx_request&&rf_out_empty)rf_starved<=1;
 end
 always @(posedge rx_clk or negedge rst_n)begin
  if(!rst_n)begin idle_command<=0;mute_command<=0;command_fault<=0;end
  else if(!er)begin idle_command<=0;mute_command<=0;command_fault<=0;end
  else if(command_valid)case(opcode)
   0:begin end
   1:if(argument<=1)idle_command<=argument[0];else command_fault<=1;
   2:if(argument<=1)mute_command<=argument[0];else command_fault<=1;
   default:command_fault<=1;
  endcase
 end
 assign status={3'd0,rf_starved,wire_starved,command_fault,locked,rx_fault,
  rf_out_ov,wire_out_ov,iq_qov,iq_ov,rf_ov,wr_ov,(rf_un||wr_un||iq_un||iq_qun||rf_out_un||wire_out_un),enable};
endmodule

`ifdef SYNTHESIS
(* blackbox *) module gf180mcu_fd_sc_mcu7t5v0__mux2_1(
 input wire I0,I1,S,output wire Z);
endmodule
`endif
