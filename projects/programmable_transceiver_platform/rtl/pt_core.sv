// Full companion digital streaming datapath. Parallel AFE ports are macro boundaries.
module pt_core #(parameter STREAM_V2=1)(input wire rst_n,enable,mode8,
 input wire host_tx_clk,host_rx_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,
 input wire[9:0]h2d_word,output wire[9:0]d2h_word,
 input wire[9:0]wire_rx_data,input wire wire_rx_valid,
 output wire[9:0]wire_tx_data,output wire wire_tx_valid,input wire wire_tx_request,
 input wire[23:0]rf_rx_sample,input wire rf_rx_valid,
 output wire[23:0]rf_tx_sample,output wire rf_tx_valid,input wire rf_tx_request,
 output wire[15:0]status,output wire wire_idle,rf_mute);
 wire et,er,ewr,ewt,err,ert;
 pt_sync_bit e0(host_tx_clk,rst_n,enable,et);pt_sync_bit e1(host_rx_clk,rst_n,enable,er);
 pt_sync_bit e2(wire_rx_clk,rst_n,enable,ewr);pt_sync_bit e3(wire_tx_clk,rst_n,enable,ewt);
 pt_sync_bit e4(rf_rx_clk,rst_n,enable,err);pt_sync_bit e5(rf_tx_clk,rst_n,enable,ert);
 wire trst=rst_n&&et,rrst=rst_n&&er;
 // Shared FIFO reset asserts when disabled; FIFO synchronizes release at both ends.
 wire wrrst=rst_n&&ewr,wtrst=rst_n&&ewt,rfrst=rst_n&&err,rftrst=rst_n&&ert;
 wire[9:0]wr_head,iq_head;wire[6:0]wr_avail;wire[5:0]iq_avail;
 wire wr_pop,iq_pop,wr_empty,wr_full;wire wr_ov,wr_un;
 pt_async_fifo #(.W(10),.A(6)) wire_in(.wr_clk(wire_rx_clk),.rd_clk(host_tx_clk),.rst_n(rst_n&&enable),
 .din(wire_rx_data),.push(wire_rx_valid&&ewr),.pop(wr_pop),.dout(wr_head),.full(wr_full),.empty(wr_empty),.wr_count(),.rd_count(wr_avail),.overflow(wr_ov),.underflow(wr_un));
 wire[23:0]rf_head;wire rf_empty,rf_full,rf_pop,rf_ov,rf_un;
 wire[23:0]compressed=mode8?{8'b0,rf_rx_sample[23:16],rf_rx_sample[11:4]}:rf_rx_sample;
 pt_async_fifo #(.W(24),.A(4)) rf_in(.wr_clk(rf_rx_clk),.rd_clk(host_tx_clk),.rst_n(rst_n&&enable),
 .din(compressed),.push(rf_rx_valid&&err),.pop(rf_pop),.dout(rf_head),.full(rf_full),.empty(rf_empty),.wr_count(),.rd_count(),.overflow(rf_ov),.underflow(rf_un));
 wire[9:0]packed_word;wire packed_valid,pack_ready,iq_full,iq_empty,iq_ov,iq_un;
 assign rf_pop=!rf_empty&&pack_ready;
 pt_pack packer(host_tx_clk,trst,mode8,rf_head,!rf_empty,pack_ready,packed_word,packed_valid,!iq_full);
 pt_sync_fifo #(.W(10),.A(5)) iq_in(host_tx_clk,trst,packed_valid&&!iq_full,iq_pop,packed_word,iq_head,iq_full,iq_empty,iq_avail,iq_ov,iq_un);
 wire[9:0]wire_out_word,iq_out_word;wire wire_out_valid,iq_out_valid,wire_out_ready,iq_out_ready;
 wire rx_fault,locked,command_valid;wire[3:0]opcode;wire[7:0]argument;
 generate if(STREAM_V2)begin:stream_v2
  pt_stream_link_tx frame_tx(host_tx_clk,trst,mode8,wr_head,iq_head,wr_avail,iq_avail,4'd0,8'd0,wr_pop,iq_pop,d2h_word);
  pt_stream_link_rx frame_rx(host_rx_clk,rrst,mode8,h2d_word,wire_out_ready,iq_out_ready,wire_out_word,
   wire_out_valid,iq_out_valid,command_valid,rx_fault,locked,opcode,argument);
  assign iq_out_word=wire_out_word;
 end else begin:stream_v1
  pt_frame_tx frame_tx(host_tx_clk,trst,mode8,wr_head,iq_head,wr_avail,iq_avail,wr_pop,iq_pop,d2h_word);
  pt_frame_rx frame_rx(host_rx_clk,rrst,mode8,h2d_word,wire_out_word,iq_out_word,wire_out_valid,iq_out_valid,
   wire_out_ready,iq_out_ready,rx_fault,locked,command_valid,opcode,argument);
 end endgenerate
 wire wire_out_full,wire_out_empty,wire_out_ov,wire_out_un;wire[7:0]wire_out_count;
 reg wire_running,rf_running,wire_starved,rf_starved;reg idle_command,mute_command,command_fault;
 wire rx_fault_wire,rx_fault_rf;
 pt_sync_bit f0(wire_tx_clk,rst_n,rx_fault||command_fault,rx_fault_wire);
 pt_sync_bit f1(rf_tx_clk,rst_n,rx_fault||command_fault,rx_fault_rf);
 wire idle_sync,mute_sync;
 pt_sync_bit f2(wire_tx_clk,rst_n,idle_command,idle_sync);pt_sync_bit f3(rf_tx_clk,rst_n,mute_command,mute_sync);
 assign wire_out_ready=!wire_out_full;
 pt_async_fifo #(.W(10),.A(7)) wire_out(.wr_clk(host_rx_clk),.rd_clk(wire_tx_clk),.rst_n(rst_n&&enable),
 .din(wire_out_word),.push(wire_out_valid),.pop(wire_tx_request&&wire_running&&!wire_out_empty),.dout(wire_tx_data),
 .full(wire_out_full),.empty(wire_out_empty),.wr_count(),.rd_count(wire_out_count),.overflow(wire_out_ov),.underflow(wire_out_un));
 assign wire_tx_valid=wire_running&&!wire_out_empty&&!rx_fault_wire&&!wire_starved;
 assign wire_idle=!wire_tx_valid||idle_sync;
 wire[23:0]unpacked_sample,rf_out_head;wire unpacked_valid,unpack_ready,rf_out_full,rf_out_empty,rf_out_ov,rf_out_un;
 wire[6:0]rf_out_count;
 // Quarantine release can contain back-to-back IQ words. Buffer before unpacking.
 wire[9:0]unpack_word;wire iq_qfull,iq_qempty,iq_qov,iq_qun;wire[5:0]iq_qcount;
 pt_sync_fifo #(.W(10),.A(5)) iq_receive(host_rx_clk,rrst,iq_out_valid,!iq_qempty&&unpack_ready,iq_out_word,
 unpack_word,iq_qfull,iq_qempty,iq_qcount,iq_qov,iq_qun);
 assign iq_out_ready=!iq_qfull;
 pt_unpack unpacker(host_rx_clk,rrst,mode8,unpack_word,!iq_qempty,unpack_ready,unpacked_sample,unpacked_valid,!rf_out_full);
 pt_async_fifo #(.W(24),.A(6)) rf_out(.wr_clk(host_rx_clk),.rd_clk(rf_tx_clk),.rst_n(rst_n&&enable),
 .din(unpacked_sample),.push(unpacked_valid&&!rf_out_full),.pop(rf_tx_request&&rf_running&&!rf_out_empty),.dout(rf_out_head),
 .full(rf_out_full),.empty(rf_out_empty),.wr_count(),.rd_count(rf_out_count),.overflow(rf_out_ov),.underflow(rf_out_un));
 assign rf_tx_sample=mode8?{rf_out_head[15:8],4'b0,rf_out_head[7:0],4'b0}:rf_out_head;
 assign rf_tx_valid=rf_running&&!rf_out_empty&&!rx_fault_rf&&!rf_starved;
 assign rf_mute=!rf_tx_valid||mute_sync;
 always @(posedge wire_tx_clk or negedge rst_n)begin
  if(!rst_n)begin wire_running<=0;wire_starved<=0;end
  else if(!ewt)begin wire_running<=0;wire_starved<=0;end
  else if(!wire_running&&wire_out_count>=32)wire_running<=1;
  else if(wire_running&&wire_tx_request&&wire_out_empty)wire_starved<=1;
 end
 always @(posedge rf_tx_clk or negedge rst_n)begin
  if(!rst_n)begin rf_running<=0;rf_starved<=0;end
  else if(!ert)begin rf_running<=0;rf_starved<=0;end
  else if(!rf_running&&rf_out_count>=8)rf_running<=1;
  else if(rf_running&&rf_tx_request&&rf_out_empty)rf_starved<=1;
 end
 always @(posedge host_rx_clk or negedge rst_n)begin
  if(!rst_n)begin idle_command<=0;mute_command<=0;command_fault<=0;end
  else if(!er)begin idle_command<=0;mute_command<=0;command_fault<=0;end
  else if(command_valid)case(opcode)
   0:begin end
   1:if(argument<=1)idle_command<=argument[0];else command_fault<=1;
   2:if(argument<=1)mute_command<=argument[0];else command_fault<=1;
   default:command_fault<=1;
  endcase
 end
 assign status={3'b0,rf_starved,wire_starved,command_fault,locked,rx_fault,
 rf_out_ov,wire_out_ov,iq_qov,iq_ov,rf_ov,wr_ov,(rf_un||wr_un||iq_un||iq_qun||rf_out_un||wire_out_un),enable};
endmodule
