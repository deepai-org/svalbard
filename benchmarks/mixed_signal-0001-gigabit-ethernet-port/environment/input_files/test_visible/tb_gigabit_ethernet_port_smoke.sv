`timescale 1ns/1ps

module tb_gigabit_ethernet_port_smoke;
  import gigabit_ethernet_port_pkg::*;
  logic clk_125_i = 1'b0;
  logic refclk_i = 1'b0;
  logic rst_ni = 1'b0;
  logic [DATA_W-1:0] tx_data_i = '0;
  logic tx_valid_i = 1'b0;
  logic tx_ready_o;
  logic tx_last_i = 1'b0;
  logic tx_user_i = 1'b0;
  logic [DATA_W-1:0] rx_data_o;
  logic rx_valid_o;
  logic rx_ready_i = 1'b1;
  logic rx_last_o;
  logic rx_user_o;
  logic [CTRL_W-1:0] control_i = '0;
  logic [CTRL_W-1:0] status_o;
  logic [COUNTER_W-1:0] tx_frame_count_o;
  logic [COUNTER_W-1:0] rx_frame_count_o;
  logic [COUNTER_W-1:0] error_count_o;
  logic [9:0] phy_tx_code_o;
  logic [9:0] phy_rx_code_i = '0;
  logic phy_tx_enable_o;
  logic phy_reset_no;
  logic phy_rx_code_valid_i = 1'b0;
  logic phy_lock_i = 1'b1;

  byte unsigned frame [0:59];
  integer received = 0;
  integer cycles = 0;

  always #4 clk_125_i = ~clk_125_i;
  always #4 refclk_i = ~refclk_i;

  gigabit_ethernet_port dut (.*);

  always @(posedge clk_125_i) begin
    cycles <= cycles + 1;
    if (rx_valid_o && rx_ready_i) begin
      if (received >= 60)
        $fatal(1, "visible smoke emitted extra receive bytes");
      if (rx_data_o !== frame[received])
        $fatal(1, "visible smoke RX mismatch index=%0d got=%02x exp=%02x",
               received, rx_data_o, frame[received]);
      if (rx_user_o)
        $fatal(1, "visible smoke marked a clean loopback frame bad");
      if (rx_last_o !== (received == 59))
        $fatal(1, "visible smoke RX last mismatch index=%0d", received);
      received <= received + 1;
    end
    if (cycles > 20000)
      $fatal(1, "visible smoke timed out");
  end

  task automatic send_byte(input byte unsigned value, input logic last);
    integer wait_cycles;
    begin
      @(negedge clk_125_i);
      tx_data_i = value;
      tx_last_i = last;
      tx_valid_i = 1'b1;
      wait_cycles = 0;
      do begin
        @(posedge clk_125_i);
        wait_cycles = wait_cycles + 1;
        if (wait_cycles > 128)
          $fatal(1, "visible smoke TX backpressure did not clear");
      end while (!tx_ready_o);
      @(negedge clk_125_i);
      tx_valid_i = 1'b0;
      tx_last_i = 1'b0;
    end
  endtask

  initial begin
    for (integer i = 0; i < 60; i = i + 1)
      frame[i] = i[7:0] * 8'd37 + 8'd11;

    repeat (8) @(posedge clk_125_i);
    if (phy_reset_no !== 1'b0)
      $fatal(1, "PHY reset output was not asserted during reset");
    @(negedge clk_125_i);
    rst_ni = 1'b1;
    control_i[CTRL_ENABLE_BIT] = 1'b1;
    control_i[CTRL_LOOPBACK_LSB +: 2] = LOOPBACK_DIGITAL;
    control_i[CTRL_SWING_LSB +: 3] = 3'd3;
    control_i[CTRL_THRESHOLD_LSB +: 3] = 3'd3;
    control_i[CTRL_BIAS_LSB +: 4] = 4'd7;
    control_i[CTRL_CDR_LSB +: 3] = 3'd3;

    for (integer i = 0; i < 60; i = i + 1)
      send_byte(frame[i], i == 59);

    while (received < 60)
      @(posedge clk_125_i);
    repeat (4) @(posedge clk_125_i);
    if (tx_frame_count_o < 1 || rx_frame_count_o < 1 || error_count_o != 0)
      $fatal(1, "visible smoke counter contract failed");
    if ((^status_o) === 1'bx || (^phy_tx_code_o) === 1'bx ||
        phy_tx_enable_o === 1'bx)
      $fatal(1, "visible smoke observed unknown status/PHY outputs");
    if (!status_o[STATUS_ENABLED_BIT] || !status_o[STATUS_PHY_LOCK_BIT] ||
        !status_o[STATUS_LINK_UP_BIT] || !status_o[STATUS_CONFIG_DONE_BIT] ||
        status_o[STATUS_FAULT_BIT])
      $fatal(1, "visible smoke status contract failed");
    $display("gigabit ethernet visible RTL smoke: PASS");
    $finish;
  end
endmodule
