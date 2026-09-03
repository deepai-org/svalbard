`timescale 1ns/1ps
module tb_lnp64_soc_smoke;
  logic clk = 0;
  logic pipe_clk = 0;
  logic jtag_clk = 0;
  logic rst_n = 0;
  logic boot_error;
  logic boot_done;
  logic [3:0] core_alive;

  always #2.5 clk = ~clk;
  always #4 pipe_clk = ~pipe_clk;
  always #20 jtag_clk = ~jtag_clk;

  lnp64_soc dut (
    .clk_200_i(clk), .rst_ni(rst_n), .boot_sel_i(2'b11),
    .uart_rx_i(1'b1), .uart_tx_o(),
    .sd_clk_o(), .sd_cmd_o(), .sd_cmd_oe_o(), .sd_cmd_i(1'b1),
    .sd_dat_o(), .sd_dat_oe_o(), .sd_dat_i(4'hf),
    .sdram_clk_o(), .sdram_cke_o(), .sdram_cs_no(), .sdram_ras_no(),
    .sdram_cas_no(), .sdram_we_no(), .sdram_ba_o(), .sdram_addr_o(),
    .sdram_dqm_o(), .sdram_dq_o(), .sdram_dq_oe_o(), .sdram_dq_i(32'b0),
    .pipe_clk_125_i(pipe_clk), .pcie_perst_ni(rst_n),
    .pipe_rxdata_i(16'b0), .pipe_rxdatak_i(2'b0),
    .pipe_rxvalid_i(1'b0), .pipe_phystatus_i(1'b0), .pipe_rxelecidle_i(1'b1),
    .pipe_rxstatus_i(3'b0), .pipe_txdata_o(), .pipe_txdatak_o(),
    .pipe_txelecidle_o(), .pipe_powerdown_o(), .pipe_rate_o(), .pipe_reset_no(),
    .pipe_rxpolarity_o(), .pipe_txcompliance_o(), .pipe_txdetectrx_loopback_o(),
    .entropy_bit_i(1'b0), .entropy_valid_i(1'b0), .entropy_ready_o(),
    .jtag_tck_i(jtag_clk), .jtag_trst_ni(rst_n), .jtag_tms_i(1'b1),
    .jtag_tdi_i(1'b0), .jtag_tdo_o(),
    .boot_done_o(boot_done), .boot_error_o(boot_error), .core_alive_o(core_alive)
  );

  initial begin
    repeat (4) @(posedge clk);
    rst_n = 1;
    repeat (32) @(posedge clk);
    #1;
    if (!boot_error || boot_done || core_alive != 4'b0) begin
      $fatal(1, "reserved boot selection did not fail closed");
    end
    $display("visible reserved-boot smoke: PASS");
    $finish;
  end
endmodule
