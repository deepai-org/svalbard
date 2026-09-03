`timescale 1ns/1ps
module tb_uart_invalid_image;
  logic clk = 0, pipe_clk = 0, jtag_clk = 0, rst_n = 0, uart_rx = 1;
  logic boot_done, boot_error;
  logic [3:0] core_alive;

  always #2.5 clk = ~clk;
  always #4 pipe_clk = ~pipe_clk;
  always #20 jtag_clk = ~jtag_clk;

  task automatic uart_byte(input logic [7:0] value);
    integer bit_index;
    begin
      uart_rx = 0; #8681;
      for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1) begin
        uart_rx = value[bit_index]; #8681;
      end
      uart_rx = 1; #8681;
    end
  endtask

  lnp64_soc dut (
    .clk_200_i(clk), .rst_ni(rst_n), .boot_sel_i(2'b01),
    .uart_rx_i(uart_rx), .uart_tx_o(),
    .sd_clk_o(), .sd_cmd_o(), .sd_cmd_oe_o(), .sd_cmd_i(1'b1),
    .sd_dat_o(), .sd_dat_oe_o(), .sd_dat_i(4'hf),
    .sdram_clk_o(), .sdram_cke_o(), .sdram_cs_no(), .sdram_ras_no(),
    .sdram_cas_no(), .sdram_we_no(), .sdram_ba_o(), .sdram_addr_o(),
    .sdram_dqm_o(), .sdram_dq_o(), .sdram_dq_oe_o(), .sdram_dq_i(32'b0),
    .pipe_clk_125_i(pipe_clk), .pcie_perst_ni(rst_n),
    .pipe_rxdata_i(16'b0), .pipe_rxdatak_i(2'b0), .pipe_rxvalid_i(1'b0),
    .pipe_phystatus_i(1'b0), .pipe_rxelecidle_i(1'b1), .pipe_rxstatus_i(3'b0),
    .pipe_txdata_o(), .pipe_txdatak_o(), .pipe_txelecidle_o(),
    .pipe_powerdown_o(), .pipe_rate_o(), .pipe_reset_no(),
    .pipe_rxpolarity_o(), .pipe_txcompliance_o(), .pipe_txdetectrx_loopback_o(),
    .entropy_bit_i(1'b0), .entropy_valid_i(1'b0), .entropy_ready_o(),
    .jtag_tck_i(jtag_clk), .jtag_trst_ni(rst_n), .jtag_tms_i(1'b1),
    .jtag_tdi_i(1'b0), .jtag_tdo_o(), .boot_done_o(boot_done),
    .boot_error_o(boot_error), .core_alive_o(core_alive)
  );

  integer i;
  initial begin
    repeat (4) @(posedge clk);
    rst_n = 1;
    repeat (8) @(posedge clk);
    uart_byte(8'h4c); uart_byte(8'h4e); uart_byte(8'h50); uart_byte(8'h42);
    uart_byte(8'h40); uart_byte(8'h00); uart_byte(8'h00); uart_byte(8'h00);
    for (i = 0; i < 64; i = i + 1) uart_byte(8'h00);
    // CRC-32/ISO-HDLC of the 64 zero-byte image.
    uart_byte(8'h36); uart_byte(8'h63); uart_byte(8'h8d); uart_byte(8'h75);
    repeat (4096) @(posedge clk);
    if (!boot_error || boot_done || core_alive != 4'b0)
      $fatal(1, "invalid UART image was not rejected");
    $display("UART invalid-image gate: PASS");
    $finish;
  end
endmodule
