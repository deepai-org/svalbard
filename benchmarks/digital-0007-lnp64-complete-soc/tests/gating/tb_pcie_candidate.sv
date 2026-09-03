`timescale 1ns/1ps

module test;
  localparam integer MAX_WORDS = 256;
  logic clk_200 = 0, clk_250 = 0, pipe_clk = 0;
  logic rst_n = 0, pcie_perst_n = 0;
  logic tck = 0, trst_n = 1, tms = 1, tdi = 0, tdo;
  logic [63:0] image [0:MAX_WORDS-1];
  integer image_words;
  string image_path;

  logic [15:0] root_txdata, endpoint_txdata;
  logic [1:0] root_txdatak, endpoint_txdatak;
  logic root_elec_idle, endpoint_elec_idle;
  logic endpoint_reset_n;
  logic endpoint_detect;
  logic pipe_phystatus = 0;
  logic [2:0] pipe_rxstatus = 0;
  logic detect_d = 0;
  logic [1:0] powerdown_d = 2'b11;
  logic [1:0] endpoint_powerdown;

  logic boot_done, boot_error;
  logic [3:0] core_alive;

  always #2.5 clk_200 = ~clk_200;
  always #2 clk_250 = ~clk_250;
  always #4 pipe_clk = ~pipe_clk;

  // Minimal Gen1 PIPE PHY sideband behavior. The pinned root model supplies
  // the decoded data/K stream; this logic supplies receiver detection and
  // completion indications for the fixed-rate x1 link.
  always @(posedge pipe_clk or negedge pcie_perst_n) begin
    if (!pcie_perst_n) begin
      pipe_phystatus <= 0;
      pipe_rxstatus <= 0;
      detect_d <= 0;
      powerdown_d <= 2'b11;
    end else begin
      pipe_phystatus <= 0;
      pipe_rxstatus <= 0;
      if (endpoint_detect && !detect_d) begin
        pipe_phystatus <= 1;
        pipe_rxstatus <= 3'b011; // receiver present
      end else if (endpoint_powerdown != powerdown_d) begin
        pipe_phystatus <= 1;
      end
      detect_d <= endpoint_detect;
      powerdown_d <= endpoint_powerdown;
    end
  end

  task automatic tap_cycle(input logic next_tms, input logic next_tdi,
                           output logic sampled_tdo);
    begin
      tms = next_tms; tdi = next_tdi;
      #20; tck = 1; #1; sampled_tdo = tdo; #19; tck = 0;
    end
  endtask

  task automatic tap_reset;
    logic ignored;
    integer i;
    begin
      for (i = 0; i < 6; i = i + 1) tap_cycle(1, 0, ignored);
      tap_cycle(0, 0, ignored);
    end
  endtask

  task automatic shift_ir(input logic [4:0] value);
    logic ignored;
    integer i;
    begin
      tap_cycle(1, 0, ignored); tap_cycle(1, 0, ignored);
      tap_cycle(0, 0, ignored); tap_cycle(0, 0, ignored);
      for (i = 0; i < 5; i = i + 1) tap_cycle(i == 4, value[i], ignored);
      tap_cycle(1, 0, ignored); tap_cycle(0, 0, ignored);
    end
  endtask

  task automatic shift_dr(input integer bits, input logic [511:0] tx,
                          output logic [511:0] rx);
    logic sample;
    integer i;
    begin
      rx = '0;
      tap_cycle(1, 0, sample); tap_cycle(0, 0, sample); tap_cycle(0, 0, sample);
      for (i = 0; i < bits; i = i + 1) begin
        tap_cycle(i == bits - 1, tx[i], sample); rx[i] = sample;
      end
      tap_cycle(1, 0, sample); tap_cycle(0, 0, sample);
    end
  endtask

  task automatic write_mem(input logic [63:0] address, input logic [63:0] value);
    logic [511:0] tx, rx;
    begin
      shift_ir(5'd7); tx = '0; tx[64] = 1; tx[63:0] = address;
      shift_dr(65, tx, rx);
      shift_ir(5'd8); tx = '0; tx[63:0] = value; shift_dr(64, tx, rx);
    end
  endtask

  task automatic write_reg(input logic [15:0] address, input logic [63:0] value);
    logic [511:0] tx, rx;
    begin
      shift_ir(5'd5); tx = '0; tx[16] = 1; tx[15:0] = address;
      shift_dr(17, tx, rx);
      shift_ir(5'd6); tx = '0; tx[63:0] = value; shift_dr(512, tx, rx);
    end
  endtask

  task automatic read_reg(input logic [15:0] address, output logic [63:0] value);
    logic [511:0] tx, rx;
    begin
      shift_ir(5'd5); tx = '0; tx[15:0] = address; shift_dr(17, tx, rx);
      shift_ir(5'd6); shift_dr(512, '0, rx); value = rx[63:0];
    end
  endtask

  logic [63:0] value;
  logic [511:0] tx, rx;
  integer i;
  initial begin
    if (!$value$plusargs("IMAGE=%s", image_path)) $fatal(1, "missing +IMAGE");
    if (!$value$plusargs("WORDS=%d", image_words) || image_words < 1 || image_words > MAX_WORDS)
      $fatal(1, "invalid +WORDS");
    $readmemh(image_path, image);
    #1 trst_n = 0;
    repeat (10) @(posedge clk_200);
    rst_n = 1; trst_n = 1;
    repeat (20) @(posedge clk_200);
    tap_reset();
    for (i = 0; i < image_words; i = i + 1)
      write_mem(64'h1000 + 8*i, image[i]);
    write_reg(16'h0040, 64'h1000);

    // Release the independent PCIe fundamental reset only after the endpoint
    // program and debug state are installed.
    pcie_perst_n = 1;
    shift_ir(5'd3); tx = '0; tx[0] = 1; shift_dr(1, tx, rx);

    value = 0;
    for (i = 0; i < 10000 && value == 0; i = i + 1) begin
      repeat (50) @(posedge clk_200);
      read_reg(16'h0042, value);
    end
    if (value !== 64'd2) $fatal(1, "PCIe workload stop cause %0d", value);
    read_reg(16'h0043, value);
    if (value !== 0) $fatal(1, "PCIe workload exit value %0d", value);
    $display("PCIE_SOC_PASS");
    repeat (2000) @(posedge clk_250);
    $finish;
  end

  initial begin
    #50ms $fatal(1, "PCIe candidate test timeout");
  end

  task Fatal;
    begin
      $fatal(1, "pcievhost fatal error");
    end
  endtask

  pcieVHostPipex1 #(.NodeNum(0), .EndPoint(0), .DataWidth(16), .Gen2Clk(0)) root (
    .pcieclk(clk_250), .pclk(pipe_clk), .nreset(rst_n && pcie_perst_n && endpoint_reset_n),
    .Gen2ClkSel(), .ClkOut(),
`ifdef VERILATOR
    .ElecIdleOut(root_elec_idle), .ElecIdleIn(endpoint_elec_idle),
`endif
    .RxData(endpoint_txdata), .RxDataK(endpoint_txdatak),
    .TxData(root_txdata), .TxDataK(root_txdatak)
  );

  lnp64_soc dut (
    .clk_200_i(clk_200), .rst_ni(rst_n), .boot_sel_i(2'b10),
    .uart_rx_i(1'b1), .uart_tx_o(),
    .sd_clk_o(), .sd_cmd_o(), .sd_cmd_oe_o(), .sd_cmd_i(1'b1),
    .sd_dat_o(), .sd_dat_oe_o(), .sd_dat_i(4'hf),
    .sdram_clk_o(), .sdram_cke_o(), .sdram_cs_no(), .sdram_ras_no(),
    .sdram_cas_no(), .sdram_we_no(), .sdram_ba_o(), .sdram_addr_o(),
    .sdram_dqm_o(), .sdram_dq_o(), .sdram_dq_oe_o(), .sdram_dq_i(32'b0),
    .pipe_clk_125_i(pipe_clk), .pcie_perst_ni(pcie_perst_n),
    .pipe_rxdata_i(root_txdata), .pipe_rxdatak_i(root_txdatak),
    .pipe_rxvalid_i(!root_elec_idle), .pipe_phystatus_i(pipe_phystatus),
    .pipe_rxelecidle_i(root_elec_idle), .pipe_rxstatus_i(pipe_rxstatus),
    .pipe_txdata_o(endpoint_txdata), .pipe_txdatak_o(endpoint_txdatak),
    .pipe_txelecidle_o(endpoint_elec_idle), .pipe_powerdown_o(endpoint_powerdown),
    .pipe_rate_o(), .pipe_reset_no(endpoint_reset_n), .pipe_rxpolarity_o(),
    .pipe_txcompliance_o(), .pipe_txdetectrx_loopback_o(endpoint_detect),
    .entropy_bit_i(1'b0), .entropy_valid_i(1'b0), .entropy_ready_o(),
    .jtag_tck_i(tck), .jtag_trst_ni(trst_n), .jtag_tms_i(tms),
    .jtag_tdi_i(tdi), .jtag_tdo_o(tdo), .boot_done_o(boot_done),
    .boot_error_o(boot_error), .core_alive_o(core_alive)
  );
endmodule
