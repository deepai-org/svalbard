// Full companion digital streaming datapath. Parallel AFE ports are macro boundaries.
module pt_core(input wire rst_n,enable,mode8,
 input wire host_tx_clk,host_rx_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,
 input wire[9:0]h2d_word,output wire[9:0]d2h_word,
 input wire[19:0]wire_rx_data,input wire wire_rx_valid,     // 20-bit double words (P3-6), word 0 in [9:0]
 output wire[19:0]wire_tx_data,output wire wire_tx_valid,input wire wire_tx_request,
 input wire[23:0]rf_rx_sample,input wire rf_rx_valid,
 output wire[23:0]rf_tx_sample,output wire rf_tx_valid,input wire rf_tx_request,
 output wire[15:0]status,output wire wire_idle,rf_mute,input wire payload_iq);
 pt_core_pair paired_core(.*);
endmodule
