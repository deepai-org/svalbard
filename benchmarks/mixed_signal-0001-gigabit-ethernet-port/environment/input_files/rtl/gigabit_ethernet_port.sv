`timescale 1ns/1ps

module gigabit_ethernet_port (
  input  logic                 clk_125_i,
  input  logic                 refclk_i,
  input  logic                 rst_ni,

  input  logic [gigabit_ethernet_port_pkg::DATA_W-1:0] tx_data_i,
  input  logic                 tx_valid_i,
  output logic                 tx_ready_o,
  input  logic                 tx_last_i,
  input  logic                 tx_user_i,

  output logic [gigabit_ethernet_port_pkg::DATA_W-1:0] rx_data_o,
  output logic                 rx_valid_o,
  input  logic                 rx_ready_i,
  output logic                 rx_last_o,
  output logic                 rx_user_o,

  input  logic [gigabit_ethernet_port_pkg::CTRL_W-1:0] control_i,
  output logic [gigabit_ethernet_port_pkg::CTRL_W-1:0] status_o,
  output logic [gigabit_ethernet_port_pkg::COUNTER_W-1:0] tx_frame_count_o,
  output logic [gigabit_ethernet_port_pkg::COUNTER_W-1:0] rx_frame_count_o,
  output logic [gigabit_ethernet_port_pkg::COUNTER_W-1:0] error_count_o,

  output logic [9:0]           phy_tx_code_o,
  input  logic [9:0]           phy_rx_code_i,
  output logic                 phy_tx_enable_o,
  output logic                 phy_reset_no,
  input  logic                 phy_rx_code_valid_i,
  input  logic                 phy_lock_i
);

  // Candidate TODO: implement the complete MAC + PCS + PMA control boundary.
  // The transistor PHY is a separate required view bound by port_manifest.json.
  // This starter intentionally compiles but does not satisfy functional tests.
  assign tx_ready_o       = 1'b0;
  assign rx_data_o        = '0;
  assign rx_valid_o       = 1'b0;
  assign rx_last_o        = 1'b0;
  assign rx_user_o        = 1'b0;
  assign status_o         = '0;
  assign tx_frame_count_o = '0;
  assign rx_frame_count_o = '0;
  assign error_count_o    = '0;
  assign phy_tx_code_o    = '0;
  assign phy_tx_enable_o  = 1'b0;
  assign phy_reset_no     = rst_ni;

  logic _unused;
  assign _unused = &{1'b0, clk_125_i, refclk_i, tx_data_i, tx_valid_i,
                     tx_last_i, tx_user_i, rx_ready_i, control_i,
                     phy_rx_code_i, phy_rx_code_valid_i, phy_lock_i};
endmodule
