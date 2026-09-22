// Candidate block CDC with two receiving-domain elastic entries.
// Ready into the CDC FIFO depends only on registered local capacity.
module pt_block_elastic(
 input wire wr_clk,rd_clk,rst_n,
 input wire [79:0]wr_data,input wire[3:0]wr_words,
 input wire wr_valid,output wire wr_ready,
 output wire[79:0]rd_data,output wire[3:0]rd_words,
 output wire rd_valid,input wire rd_ready,output wire wr_fault);
 wire[79:0]block_data;wire[3:0]block_words;
 wire block_valid,block_ready,full,empty;
 (* async_reg="true" *) reg[1:0] release_read;
 always @(posedge rd_clk or negedge rst_n)
  if(!rst_n)release_read<=0;else release_read<={release_read[0],1'b1};
 wire active=release_read[1];
 assign block_ready=active&&!full;
 assign rd_valid=active&&!empty;
 pt_block_fifo fifo(.wr_clk(wr_clk),.rd_clk(rd_clk),.rst_n(rst_n),
  .wr_data(wr_data),.wr_words(wr_words),.wr_valid(wr_valid),.wr_ready(wr_ready),
  .rd_data(block_data),.rd_words(block_words),.rd_valid(block_valid),
  .rd_ready(block_ready),.wr_fault(wr_fault));
 pt_sync_fifo #(.W(84),.A(1)) receive_buffer(.clk(rd_clk),.rst_n(active),
  .push(block_valid&&block_ready),.pop(rd_valid&&rd_ready),
  .din({block_words,block_data}),.dout({rd_words,rd_data}),
  .full(full),.empty(empty),.count(),.overflow(),.underflow());
endmodule
