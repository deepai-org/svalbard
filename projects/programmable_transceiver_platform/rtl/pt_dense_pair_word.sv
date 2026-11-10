// Integration screens for the pair engine and the fast word boundary.
// The pair clock is an actual divide-by-two clock, not a timing exception.
module pt_dense_pair_word_tx(input wire clk,rst_n,payload_iq,
 input wire[19:0]wire_data,iq_data,input wire[6:0]wire_pairs,iq_pairs,
 input wire[3:0]opcode,input wire[7:0]argument,
 output wire wire_pop,iq_pop,output wire[9:0]out_word);
 wire pair_clk;wire[19:0]pair,unused_pair;
 pt_pair_word_boundary boundary(clk,rst_n,pair,out_word,10'd0,unused_pair,pair_clk);
 pt_dense_pair_link_tx engine(pair_clk,rst_n,payload_iq,wire_data,iq_data,
  wire_pairs,iq_pairs,opcode,argument,wire_pop,iq_pop,pair);
endmodule

module pt_dense_pair_word_rx(input wire clk,rst_n,payload_iq,
 input wire[9:0]in_word,input wire wire_ready,iq_ready,
 output wire[19:0]data,output wire[1:0]wire_count,iq_count,
 output wire command_valid,fault,locked,
 output wire[3:0]opcode,output wire[7:0]argument);
 wire pair_clk;wire[19:0]pair;wire[9:0]unused_word;
 pt_pair_word_boundary boundary(clk,rst_n,20'd0,unused_word,in_word,pair,pair_clk);
 pt_dense_pair_link_rx engine(pair_clk,rst_n,payload_iq,pair,wire_ready,iq_ready,
  data,wire_count,iq_count,command_valid,fault,locked,opcode,argument);
endmodule
