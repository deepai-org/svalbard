// Timing fixture, not integrated chip RTL. Capture every accepted read block.
module pt_block_fifo_capture(
 input wire wr_clk,rd_clk,rst_n,
 input wire [79:0]wr_data,input wire[3:0]wr_words,
 input wire wr_valid,output wire wr_ready,input wire rd_ready,
 output wire rd_valid,output wire wr_fault,output reg[83:0]captured);
 wire[79:0]rd_data;wire[3:0]rd_words;
 pt_block_fifo fifo(.*);
 // No reset needed: captured has meaning only after an accepted read.
 always @(posedge rd_clk)if(rd_valid&&rd_ready)captured<={rd_words,rd_data};
endmodule
