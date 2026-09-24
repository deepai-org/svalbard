// WIRE_RX is bidirectional for planned USB D+/D-; USB control/data macros remain unimplemented.
// 50-terminal integration skeleton. Black-box macros are obligations, not fabricated IP.
module pt_chip(
 input wire RESET_N,REF_IN,SPI_SCLK,SPI_CS_N,SPI_MOSI,output wire SPI_MISO,
 input wire[9:0]H2D,input wire H2D_CLK,output wire[9:0]D2H,output wire D2H_CLK,
 inout wire WIRE_RX_P,WIRE_RX_N,output wire WIRE_TX_P,WIRE_TX_N,
 input wire RF_RX_P,RF_RX_N,output wire RF_TX_P,RF_TX_N,
 inout wire VDD_CORE,VSS_CORE,VDD_HOST_A,VSS_HOST_A,VDD_HOST_B,VSS_HOST_B,
 VDD_WIRE_A,VSS_WIRE_A,VDD_WIRE_B,VSS_WIRE_B,VDD_RF,VSS_RF,VDD_PLL,VSS_PLL);
 wire rst_n,ref_clk,sclk,cs_n,mosi,miso,miso_oe;
 wire ht,hr,wr,wt,rr,rt,enable,mode8,wv,wvalid,wrequest,rv,rvalid,rrequest,idle,mute,above;
 wire[9:0]h2d,d2h,wire_rx,wire_tx;wire[23:0]rf_rx,rf_tx;
 wire[15:0]rf_trim,wire_trim,clock_trim,status;wire[11:0]trial;
 pt_host_physical host(RESET_N,REF_IN,SPI_SCLK,SPI_CS_N,SPI_MOSI,SPI_MISO,
 H2D,H2D_CLK,D2H,D2H_CLK,VDD_CORE,VSS_CORE,VDD_HOST_A,VSS_HOST_A,VDD_HOST_B,VSS_HOST_B,
 rst_n,ref_clk,sclk,cs_n,mosi,miso,miso_oe,ht,hr,h2d,d2h);
 pt_analog_physical analog(WIRE_RX_P,WIRE_RX_N,WIRE_TX_P,WIRE_TX_N,RF_RX_P,RF_RX_N,RF_TX_P,RF_TX_N,
 VDD_CORE,VSS_CORE,VDD_WIRE_A,VSS_WIRE_A,VDD_WIRE_B,VSS_WIRE_B,VDD_RF,VSS_RF,VDD_PLL,VSS_PLL,
 rst_n,ref_clk,enable,mode8,rf_trim,wire_trim,clock_trim,trial,above,
 ht,wr,wt,rr,rt,wire_rx,wv,wire_tx,wvalid,wrequest,idle,rf_rx,rv,rf_tx,rvalid,rrequest,mute);
 pt_digital digital(rst_n,ref_clk,sclk,cs_n,mosi,miso,miso_oe,ht,hr,wr,wt,rr,rt,
 h2d,d2h,wire_rx,wv,wire_tx,wvalid,idle,wrequest,rf_rx,rv,rf_tx,rvalid,mute,rrequest,
 enable,mode8,rf_trim,wire_trim,clock_trim,above,trial,status);
endmodule

// Must implement actual pads, level shifting, DDR capture/launch and clock phase alignment.
(* blackbox *) module pt_host_physical(
 input wire RESET_N,REF_IN,SPI_SCLK,SPI_CS_N,SPI_MOSI,output wire SPI_MISO,
 input wire[9:0]H2D,input wire H2D_CLK,output wire[9:0]D2H,output wire D2H_CLK,
 inout wire VDD_CORE,VSS_CORE,VDD_HOST_A,VSS_HOST_A,VDD_HOST_B,VSS_HOST_B,
 output wire rst_n,ref_clk,sclk,cs_n,mosi,input wire miso,miso_oe,host_tx_clk,
 output wire host_rx_clk,output wire[9:0]h2d_word,input wire[9:0]d2h_word);
endmodule

// Internal architecture and circuit implementation tracked in macro-contract.md.
(* blackbox *) module pt_analog_physical(
 inout wire WIRE_RX_P,WIRE_RX_N,output wire WIRE_TX_P,WIRE_TX_N,
 input wire RF_RX_P,RF_RX_N,output wire RF_TX_P,RF_TX_N,
 inout wire VDD_CORE,VSS_CORE,VDD_WIRE_A,VSS_WIRE_A,VDD_WIRE_B,VSS_WIRE_B,VDD_RF,VSS_RF,VDD_PLL,VSS_PLL,
 input wire rst_n,ref_clk,enable,mode8,input wire[15:0]rf_trim,wire_trim,clock_trim,
 input wire[11:0]calibration_trial,output wire calibration_above_target,
 output wire host_tx_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,
 output wire[9:0]wire_rx_data,output wire wire_rx_valid,input wire[9:0]wire_tx_data,
 input wire wire_tx_valid,output wire wire_tx_request,input wire wire_idle,
 output wire[23:0]rf_rx_sample,output wire rf_rx_valid,input wire[23:0]rf_tx_sample,
 input wire rf_tx_valid,output wire rf_tx_request,input wire rf_mute);
endmodule
