// Standalone candidate: eight 10-bit words per CDC transaction, eight blocks.
// Count is payload metadata, never a pointer increment. Both domains reset together.
module pt_block_fifo(
 input wire wr_clk,rd_clk,rst_n,
 input wire [79:0] wr_data,input wire [3:0] wr_words,
 input wire wr_valid,output wire wr_ready,
 output wire [79:0] rd_data,output wire [3:0] rd_words,
 output wire rd_valid,input wire rd_ready,output reg wr_fault);
 wire wr_active,rd_active;
 wire full,empty;
 wire legal=(wr_words>=1 && wr_words<=8);
 // An invalid accepted request is discarded and faults; no storage is consumed.
 assign wr_ready=wr_active&&!full;
 assign rd_valid=rd_active&&!empty;
 always @(posedge wr_clk or negedge wr_active)
  if(!wr_active)wr_fault<=0;
  else if(wr_valid&&wr_ready&&!legal)wr_fault<=1;
 pt_async_fifo #(.W(84),.A(3)) storage(
  .wr_clk(wr_clk),.rd_clk(rd_clk),.rst_n(rst_n),
  .din({wr_words,wr_data}),.push(wr_valid&&wr_ready&&legal),
  .pop(rd_valid&&rd_ready),.dout({rd_words,rd_data}),
  .full(full),.empty(empty),.wr_active(wr_active),.rd_active(rd_active),.wr_count(),.rd_count(),.overflow(),.underflow());
endmodule
