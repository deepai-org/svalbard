module lnp64_soc (
    input  logic        clk_200_i,
    input  logic        rst_ni,
    input  logic [1:0]  boot_sel_i,

    input  logic        uart_rx_i,
    output logic        uart_tx_o,

    output logic        sd_clk_o,
    output logic        sd_cmd_o,
    output logic        sd_cmd_oe_o,
    input  logic        sd_cmd_i,
    output logic [3:0]  sd_dat_o,
    output logic        sd_dat_oe_o,
    input  logic [3:0]  sd_dat_i,

    output logic        sdram_clk_o,
    output logic        sdram_cke_o,
    output logic        sdram_cs_no,
    output logic        sdram_ras_no,
    output logic        sdram_cas_no,
    output logic        sdram_we_no,
    output logic [1:0]  sdram_ba_o,
    output logic [12:0] sdram_addr_o,
    output logic [3:0]  sdram_dqm_o,
    output logic [31:0] sdram_dq_o,
    output logic [3:0]  sdram_dq_oe_o,
    input  logic [31:0] sdram_dq_i,

    input  logic        pipe_clk_125_i,
    input  logic        pcie_perst_ni,
    input  logic [15:0] pipe_rxdata_i,
    input  logic [1:0]  pipe_rxdatak_i,
    input  logic        pipe_rxvalid_i,
    input  logic        pipe_phystatus_i,
    input  logic        pipe_rxelecidle_i,
    input  logic [2:0]  pipe_rxstatus_i,
    output logic [15:0] pipe_txdata_o,
    output logic [1:0]  pipe_txdatak_o,
    output logic        pipe_txelecidle_o,
    output logic [1:0]  pipe_powerdown_o,
    output logic        pipe_rate_o,
    output logic        pipe_reset_no,
    output logic        pipe_rxpolarity_o,
    output logic        pipe_txcompliance_o,
    output logic        pipe_txdetectrx_loopback_o,

    input  logic        entropy_bit_i,
    input  logic        entropy_valid_i,
    output logic        entropy_ready_o,

    input  logic        jtag_tck_i,
    input  logic        jtag_trst_ni,
    input  logic        jtag_tms_i,
    input  logic        jtag_tdi_i,
    output logic        jtag_tdo_o,

    output logic        boot_done_o,
    output logic        boot_error_o,
    output logic [3:0]  core_alive_o
);
  // Implement the complete SoC. The starter drives every external interface
  // to a safe inactive state and deliberately never completes boot.
  always_comb begin
    uart_tx_o = 1'b1;
    sd_clk_o = 1'b0;
    sd_cmd_o = 1'b1;
    sd_cmd_oe_o = 1'b0;
    sd_dat_o = 4'hf;
    sd_dat_oe_o = 1'b0;
    sdram_clk_o = 1'b0;
    sdram_cke_o = 1'b0;
    sdram_cs_no = 1'b1;
    sdram_ras_no = 1'b1;
    sdram_cas_no = 1'b1;
    sdram_we_no = 1'b1;
    sdram_ba_o = 2'b0;
    sdram_addr_o = 13'b0;
    sdram_dqm_o = 4'hf;
    sdram_dq_o = 32'b0;
    sdram_dq_oe_o = 4'b0;
    pipe_txdata_o = 16'b0;
    pipe_txdatak_o = 2'b0;
    pipe_txelecidle_o = 1'b1;
    pipe_powerdown_o = 2'b11;
    pipe_rate_o = 1'b0;
    pipe_reset_no = 1'b0;
    pipe_rxpolarity_o = 1'b0;
    pipe_txcompliance_o = 1'b0;
    pipe_txdetectrx_loopback_o = 1'b0;
    entropy_ready_o = 1'b0;
    jtag_tdo_o = 1'b0;
    boot_done_o = 1'b0 & clk_200_i;
    boot_error_o = 1'b0;
    core_alive_o = 4'b0;
  end
endmodule
