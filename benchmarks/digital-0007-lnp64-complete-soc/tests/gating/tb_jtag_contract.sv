`timescale 1ns/1ps
module tb_jtag_contract;
  logic clk = 0, tck = 0, pipe_clk = 0;
  logic rst_n = 0, trst_n = 1, tms = 1, tdi = 0, tdo;
  logic boot_done, boot_error;
  logic [3:0] core_alive;

  always #2.5 clk = ~clk;
  always #4 pipe_clk = ~pipe_clk;

  task automatic tap_cycle(input logic next_tms, input logic next_tdi,
                           output logic sampled_tdo);
    begin
      tms = next_tms;
      tdi = next_tdi;
      #20; tck = 1;
      #1; sampled_tdo = tdo;
      #19; tck = 0;
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
      tap_cycle(1, 0, ignored); // Select-DR
      tap_cycle(1, 0, ignored); // Select-IR
      tap_cycle(0, 0, ignored); // Capture-IR
      tap_cycle(0, 0, ignored); // Shift-IR
      for (i = 0; i < 5; i = i + 1)
        tap_cycle(i == 4, value[i], ignored);
      tap_cycle(1, 0, ignored); // Update-IR
      tap_cycle(0, 0, ignored); // Idle
    end
  endtask

  task automatic shift_dr(input integer bits, input logic [511:0] tx,
                          output logic [511:0] rx);
    logic sample;
    integer i;
    begin
      rx = '0;
      tap_cycle(1, 0, sample); // Select-DR
      tap_cycle(0, 0, sample); // Capture-DR
      tap_cycle(0, 0, sample); // Shift-DR
      for (i = 0; i < bits; i = i + 1) begin
        tap_cycle(i == bits - 1, tx[i], sample);
        rx[i] = sample;
      end
      tap_cycle(1, 0, sample); // Update-DR
      tap_cycle(0, 0, sample); // Idle
    end
  endtask

  task automatic select_ir(input logic [4:0] instruction);
    begin
      shift_ir(instruction);
    end
  endtask

  logic [511:0] rx;
  logic [511:0] tx;
  integer target;
  initial begin
    #1 trst_n = 0;
    repeat (4) @(posedge clk);
    rst_n = 1;
    trst_n = 1;
    repeat (8) @(posedge clk);
    tap_reset();

    select_ir(5'd1); // IDCODE
    shift_dr(32, '0, rx);
    if (rx[31:0] !== 32'h0e64964d) $fatal(1, "JTAG IDCODE mismatch");

    select_ir(5'd9); // STATUS
    shift_dr(32, '0, rx);
    if (rx[0] !== 1'b1 || rx[3] !== 1'b0 || rx[7:4] !== 4'b0)
      $fatal(1, "JTAG reset target is not halted and clean: %h", rx[31:0]);

    // Every core/context pair is a distinct resident debug target. Store a
    // different value in r3 through each selection, then read all 16 back.
    for (target = 0; target < 16; target = target + 1) begin
      select_ir(5'd4); // CORESEL: {context, core}
      tx = '0; tx[3:0] = target[3:0];
      shift_dr(4, tx, rx);
      select_ir(5'd9);
      shift_dr(32, '0, rx);
      if (rx[0] !== 1'b1 || rx[3] !== 1'b0 || rx[7:4] !== target[3:0])
        $fatal(1, "JTAG 4x4 target selection mismatch");
      select_ir(5'd5);
      tx = '0; tx[16] = 1; tx[15:0] = 16'h0003;
      shift_dr(17, tx, rx);
      select_ir(5'd6);
      tx = '0; tx[63:0] = 64'h4c4e_5036_3400_0000 + target;
      shift_dr(512, tx, rx);
    end
    for (target = 0; target < 16; target = target + 1) begin
      select_ir(5'd4);
      tx = '0; tx[3:0] = target[3:0];
      shift_dr(4, tx, rx);
      select_ir(5'd5);
      tx = '0; tx[15:0] = 16'h0003;
      shift_dr(17, tx, rx);
      select_ir(5'd6);
      shift_dr(512, '0, rx);
      if (rx[63:0] !== 64'h4c4e_5036_3400_0000 + target)
        $fatal(1, "JTAG resident-context state aliases another target");
    end

    // Restore the architectural adapter's selected target.
    select_ir(5'd4);
    shift_dr(4, '0, rx);

    select_ir(5'd5); // REGADDR: arm write to r3
    tx = '0; tx[16] = 1; tx[15:0] = 16'h0003;
    shift_dr(17, tx, rx);
    select_ir(5'd6); // REGDATA
    tx = '0; tx[63:0] = 64'h1357_9bdf_2468_ace0;
    shift_dr(512, tx, rx);
    select_ir(5'd5);
    tx = '0; tx[15:0] = 16'h0003;
    shift_dr(17, tx, rx);
    select_ir(5'd6);
    shift_dr(512, '0, rx);
    if (rx !== {{448{1'b0}}, 64'h1357_9bdf_2468_ace0})
      $fatal(1, "JTAG register read/write mismatch");

    select_ir(5'd7); // MEMADDR: arm write to JTAG data mapping
    tx = '0; tx[64] = 1; tx[63:0] = 64'h0000_0000_0001_0000;
    shift_dr(65, tx, rx);
    select_ir(5'd8); // MEMDATA
    tx = '0; tx[63:0] = 64'hfeed_face_cafe_beef;
    shift_dr(64, tx, rx);
    select_ir(5'd7);
    tx = '0; tx[63:0] = 64'h0000_0000_0001_0000;
    shift_dr(65, tx, rx);
    select_ir(5'd8);
    shift_dr(64, '0, rx);
    if (rx[63:0] !== 64'hfeed_face_cafe_beef)
      $fatal(1, "JTAG memory read/write mismatch");

    $display("JTAG architectural adapter: PASS");
    $finish;
  end

  lnp64_soc dut (
    .clk_200_i(clk), .rst_ni(rst_n), .boot_sel_i(2'b10),
    .uart_rx_i(1'b1), .uart_tx_o(),
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
    .jtag_tck_i(tck), .jtag_trst_ni(trst_n), .jtag_tms_i(tms),
    .jtag_tdi_i(tdi), .jtag_tdo_o(tdo), .boot_done_o(boot_done),
    .boot_error_o(boot_error), .core_alive_o(core_alive)
  );
endmodule
