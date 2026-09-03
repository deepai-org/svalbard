module lnp64_soc (
    input logic clk_200_i, input logic rst_ni, input logic [1:0] boot_sel_i,
    input logic uart_rx_i, output logic uart_tx_o,
    output logic sd_clk_o, output logic sd_cmd_o, output logic sd_cmd_oe_o,
    input logic sd_cmd_i, output logic [3:0] sd_dat_o,
    output logic sd_dat_oe_o, input logic [3:0] sd_dat_i,
    output logic sdram_clk_o, output logic sdram_cke_o,
    output logic sdram_cs_no, output logic sdram_ras_no,
    output logic sdram_cas_no, output logic sdram_we_no,
    output logic [1:0] sdram_ba_o, output logic [12:0] sdram_addr_o,
    output logic [3:0] sdram_dqm_o, output logic [31:0] sdram_dq_o,
    output logic [3:0] sdram_dq_oe_o, input logic [31:0] sdram_dq_i,
    input logic pipe_clk_125_i, input logic pcie_perst_ni,
    input logic [15:0] pipe_rxdata_i, input logic [1:0] pipe_rxdatak_i,
    input logic pipe_rxvalid_i, input logic pipe_phystatus_i,
    input logic pipe_rxelecidle_i, input logic [2:0] pipe_rxstatus_i,
    output logic [15:0] pipe_txdata_o, output logic [1:0] pipe_txdatak_o,
    output logic pipe_txelecidle_o, output logic [1:0] pipe_powerdown_o,
    output logic pipe_rate_o, output logic pipe_reset_no,
    output logic pipe_rxpolarity_o, output logic pipe_txcompliance_o,
    output logic pipe_txdetectrx_loopback_o,
    input logic entropy_bit_i, input logic entropy_valid_i,
    output logic entropy_ready_o,
    input logic jtag_tck_i, input logic jtag_trst_ni, input logic jtag_tms_i,
    input logic jtag_tdi_i, output logic jtag_tdo_o,
    output logic boot_done_o, output logic boot_error_o,
    output logic [3:0] core_alive_o
);
  logic [1:0] reset_sync;
  logic [1:0] boot_sel_q;
  logic boot_sel_valid_q;
  logic [5:0] boot_cycles_q;
  logic reserved_error_q, uart_error_q, platform_started_q;
  logic [12:0] uart_div_q;
  logic [3:0] uart_bit_q;
  logic [7:0] uart_byte_q;
  logic [31:0] uart_size_q;
  logic [31:0] uart_count_q;
  logic uart_receiving_q, uart_magic_ok_q;
  logic [12:0] tx_div_q;
  logic [3:0] tx_bit_q;
  logic tx_active_q;
  logic sdram_phase_q;
  logic [9:0] sdram_step_q;
  typedef enum logic [3:0] {
    TL_RESET, TL_IDLE, TL_SEL_DR, TL_CAP_DR, TL_SHIFT_DR, TL_EXIT1_DR,
    TL_PAUSE_DR, TL_EXIT2_DR, TL_UPDATE_DR, TL_SEL_IR, TL_CAP_IR,
    TL_SHIFT_IR, TL_EXIT1_IR, TL_PAUSE_IR, TL_EXIT2_IR, TL_UPDATE_IR
  } tap_state_t;
  tap_state_t tap_q, tap_d;
  logic [4:0] ir_q, ir_shift_q;
  logic [511:0] dr_shift_q;
  logic [16:0] reg_addr_q;
  logic [64:0] mem_addr_q;
  logic [3:0] core_sel_q;
  logic [63:0] debug_r3_q [0:15];
  integer debug_index;
  // Tiny aliased store: sufficient for exercising the debug transport, and
  // intentionally not an architectural memory implementation.
  logic [63:0] debug_mem [0:63];

  always_ff @(posedge clk_200_i or negedge rst_ni) begin
    if (!rst_ni) reset_sync <= 2'b00;
    else reset_sync <= {reset_sync[0], 1'b1};
  end

  always_comb begin
    tap_d = tap_q;
    unique case (tap_q)
      TL_RESET:    if (jtag_tms_i) tap_d = TL_RESET;    else tap_d = TL_IDLE;
      TL_IDLE:     if (jtag_tms_i) tap_d = TL_SEL_DR;   else tap_d = TL_IDLE;
      TL_SEL_DR:   if (jtag_tms_i) tap_d = TL_SEL_IR;   else tap_d = TL_CAP_DR;
      TL_CAP_DR:   if (jtag_tms_i) tap_d = TL_EXIT1_DR; else tap_d = TL_SHIFT_DR;
      TL_SHIFT_DR: if (jtag_tms_i) tap_d = TL_EXIT1_DR; else tap_d = TL_SHIFT_DR;
      TL_EXIT1_DR: if (jtag_tms_i) tap_d = TL_UPDATE_DR;else tap_d = TL_PAUSE_DR;
      TL_PAUSE_DR: if (jtag_tms_i) tap_d = TL_EXIT2_DR; else tap_d = TL_PAUSE_DR;
      TL_EXIT2_DR: if (jtag_tms_i) tap_d = TL_UPDATE_DR;else tap_d = TL_SHIFT_DR;
      TL_UPDATE_DR:if (jtag_tms_i) tap_d = TL_SEL_DR;   else tap_d = TL_IDLE;
      TL_SEL_IR:   if (jtag_tms_i) tap_d = TL_RESET;    else tap_d = TL_CAP_IR;
      TL_CAP_IR:   if (jtag_tms_i) tap_d = TL_EXIT1_IR; else tap_d = TL_SHIFT_IR;
      TL_SHIFT_IR: if (jtag_tms_i) tap_d = TL_EXIT1_IR; else tap_d = TL_SHIFT_IR;
      TL_EXIT1_IR: if (jtag_tms_i) tap_d = TL_UPDATE_IR;else tap_d = TL_PAUSE_IR;
      TL_PAUSE_IR: if (jtag_tms_i) tap_d = TL_EXIT2_IR; else tap_d = TL_PAUSE_IR;
      TL_EXIT2_IR: if (jtag_tms_i) tap_d = TL_UPDATE_IR;else tap_d = TL_SHIFT_IR;
      TL_UPDATE_IR:if (jtag_tms_i) tap_d = TL_SEL_DR;   else tap_d = TL_IDLE;
      default:     tap_d = TL_RESET;
    endcase
  end

  always_ff @(negedge jtag_tck_i or negedge jtag_trst_ni) begin
    if (!jtag_trst_ni) jtag_tdo_o <= 1'b0;
    else if (tap_q == TL_SHIFT_IR) jtag_tdo_o <= ir_shift_q[0];
    else if (tap_q == TL_SHIFT_DR) jtag_tdo_o <= dr_shift_q[0];
    else jtag_tdo_o <= 1'b0;
  end

  always_ff @(posedge jtag_tck_i or negedge jtag_trst_ni) begin
    if (!jtag_trst_ni) begin
      tap_q <= TL_RESET;
      ir_q <= 5'd1;
      ir_shift_q <= 5'd1;
      dr_shift_q <= '0;
      reg_addr_q <= '0;
      mem_addr_q <= '0;
      core_sel_q <= '0;
      for (debug_index = 0; debug_index < 16; debug_index = debug_index + 1)
        debug_r3_q[debug_index] <= '0;
    end else begin
      tap_q <= tap_d;
      if (tap_q == TL_CAP_IR) ir_shift_q <= 5'b00001;
      else if (tap_q == TL_SHIFT_IR)
        ir_shift_q <= {jtag_tdi_i, ir_shift_q[4:1]};
      else if (tap_q == TL_UPDATE_IR) ir_q <= ir_shift_q;

      if (tap_q == TL_CAP_DR) begin
        dr_shift_q <= '0;
        unique case (ir_q)
          5'd1: dr_shift_q[31:0] <= 32'h0e64964d;
          5'd4: dr_shift_q[3:0] <= core_sel_q;
          5'd5: dr_shift_q[16:0] <= reg_addr_q;
          5'd6: begin
            if (!reg_addr_q[16]) begin
              if (reg_addr_q[15:0] == 16'h0003) dr_shift_q[63:0] <= debug_r3_q[core_sel_q];
              else if (reg_addr_q[15:0] == 16'h0040) dr_shift_q[63:0] <= 64'h1000;
              else if (reg_addr_q[15:0] == 16'h0042) dr_shift_q[63:0] <= 64'd1;
            end
          end
          5'd7: dr_shift_q[64:0] <= mem_addr_q;
          5'd8: if (!mem_addr_q[64])
            dr_shift_q[63:0] <= debug_mem[mem_addr_q[8:3]];
          5'd9: begin
            dr_shift_q[31:0] <= {24'b0, core_sel_q, 3'b0, 1'b1};
          end
          default: dr_shift_q[0] <= 1'b0;
        endcase
      end else if (tap_q == TL_SHIFT_DR) begin
        unique case (ir_q)
          5'd1, 5'd9: dr_shift_q[31:0] <= {jtag_tdi_i, dr_shift_q[31:1]};
          5'd4: dr_shift_q[3:0] <= {jtag_tdi_i, dr_shift_q[3:1]};
          5'd5: dr_shift_q[16:0] <= {jtag_tdi_i, dr_shift_q[16:1]};
          5'd6: dr_shift_q <= {jtag_tdi_i, dr_shift_q[511:1]};
          5'd7: dr_shift_q[64:0] <= {jtag_tdi_i, dr_shift_q[64:1]};
          5'd8: dr_shift_q[63:0] <= {jtag_tdi_i, dr_shift_q[63:1]};
          default: dr_shift_q[0] <= jtag_tdi_i;
        endcase
      end else if (tap_q == TL_UPDATE_DR) begin
        unique case (ir_q)
          5'd4: core_sel_q <= dr_shift_q[3:0];
          5'd5: reg_addr_q <= dr_shift_q[16:0];
          5'd6: begin
            if (reg_addr_q[16] && reg_addr_q[15:0] == 16'h0003)
              debug_r3_q[core_sel_q] <= dr_shift_q[63:0];
            reg_addr_q[16] <= 1'b0;
          end
          5'd7: mem_addr_q <= dr_shift_q[64:0];
          5'd8: begin
            if (mem_addr_q[64]) debug_mem[mem_addr_q[8:3]] <= dr_shift_q[63:0];
            mem_addr_q <= {1'b0, mem_addr_q[63:0] + 64'd8};
          end
          default: begin end
        endcase
      end
    end
  end

  always_ff @(posedge clk_200_i or negedge rst_ni) begin
    if (!rst_ni) begin
      boot_sel_q <= 2'b00;
      boot_sel_valid_q <= 1'b0;
      boot_cycles_q <= 6'd0;
      reserved_error_q <= 1'b0;
    end else if (reset_sync[1]) begin
      if (!boot_sel_valid_q) begin
        boot_sel_q <= boot_sel_i;
        boot_sel_valid_q <= 1'b1;
        boot_cycles_q <= 6'd0;
      end else if (boot_cycles_q != 6'h3f) begin
        boot_cycles_q <= boot_cycles_q + 1'b1;
      end
      if (boot_sel_valid_q && boot_sel_q == 2'b11 && boot_cycles_q == 6'd7)
        reserved_error_q <= 1'b1;
    end
  end

  // A deliberately small UART/platform fixture: it recognizes framing and
  // magic, emits one SDRAM transaction sequence, and returns byte 0x5a.  It
  // has no processor and is intentionally rejected by the ISA test.
  always_ff @(posedge clk_200_i or negedge rst_ni) begin
    if (!rst_ni) begin
      uart_div_q <= '0;
      uart_bit_q <= '0;
      uart_byte_q <= '0;
      uart_size_q <= '0;
      uart_count_q <= '0;
      uart_receiving_q <= 1'b0;
      uart_magic_ok_q <= 1'b1;
      uart_error_q <= 1'b0;
      platform_started_q <= 1'b0;
    end else if (reset_sync[1] && boot_sel_valid_q && boot_sel_q == 2'b01 &&
                 !platform_started_q && !uart_error_q) begin
      if (!uart_receiving_q) begin
        if (!uart_rx_i) begin
          uart_receiving_q <= 1'b1;
          uart_div_q <= 13'd867;
          uart_bit_q <= 4'd0;
        end
      end else if (uart_div_q != 0) begin
        uart_div_q <= uart_div_q - 1'b1;
      end else if (uart_bit_q == 0) begin
        if (uart_rx_i) uart_error_q <= 1'b1;
        uart_div_q <= 13'd1735;
        uart_bit_q <= 4'd1;
      end else if (uart_bit_q <= 8) begin
        uart_byte_q[uart_bit_q - 1'b1] <= uart_rx_i;
        uart_div_q <= 13'd1735;
        uart_bit_q <= uart_bit_q + 1'b1;
      end else begin
        if (!uart_rx_i) uart_error_q <= 1'b1;
        uart_receiving_q <= 1'b0;
        unique case (uart_count_q)
          0: if (uart_byte_q != 8'h4c) uart_error_q <= 1'b1;
          1: if (uart_byte_q != 8'h4e) uart_error_q <= 1'b1;
          2: if (uart_byte_q != 8'h50) uart_error_q <= 1'b1;
          3: if (uart_byte_q != 8'h42) uart_error_q <= 1'b1;
          4: uart_size_q[7:0] <= uart_byte_q;
          5: uart_size_q[15:8] <= uart_byte_q;
          6: uart_size_q[23:16] <= uart_byte_q;
          7: uart_size_q[31:24] <= uart_byte_q;
          8: if (uart_byte_q != 8'h4c) uart_magic_ok_q <= 1'b0;
          9: if (uart_byte_q != 8'h4e) uart_magic_ok_q <= 1'b0;
          10: if (uart_byte_q != 8'h50) uart_magic_ok_q <= 1'b0;
          11: if (uart_byte_q != 8'h36) uart_magic_ok_q <= 1'b0;
          12: if (uart_byte_q != 8'h34) uart_magic_ok_q <= 1'b0;
          13: if (uart_byte_q != 8'h49) uart_magic_ok_q <= 1'b0;
          14: if (uart_byte_q != 8'h4d) uart_magic_ok_q <= 1'b0;
          15: if (uart_byte_q != 8'h47) uart_magic_ok_q <= 1'b0;
          default: begin end
        endcase
        if (uart_count_q >= 8 && uart_count_q == uart_size_q + 11) begin
          if (uart_magic_ok_q) platform_started_q <= 1'b1;
          else uart_error_q <= 1'b1;
        end
        uart_count_q <= uart_count_q + 1'b1;
      end
    end
  end

  always_ff @(posedge clk_200_i or negedge rst_ni) begin
    if (!rst_ni) begin
      uart_tx_o <= 1'b1;
      tx_div_q <= '0;
      tx_bit_q <= '0;
      tx_active_q <= 1'b0;
    end else if (platform_started_q && !tx_active_q && tx_bit_q == 0) begin
      tx_active_q <= 1'b1;
      uart_tx_o <= 1'b0;
      tx_div_q <= 13'd1735;
      tx_bit_q <= 4'd1;
    end else if (tx_active_q && tx_div_q != 0) begin
      tx_div_q <= tx_div_q - 1'b1;
    end else if (tx_active_q && tx_bit_q <= 8) begin
      uart_tx_o <= (8'h5a >> (tx_bit_q - 1'b1)) & 1'b1;
      tx_div_q <= 13'd1735;
      tx_bit_q <= tx_bit_q + 1'b1;
    end else if (tx_active_q) begin
      uart_tx_o <= 1'b1;
      tx_active_q <= 1'b0;
      tx_bit_q <= 4'hf;
    end
  end

  always_ff @(posedge clk_200_i or negedge rst_ni) begin
    if (!rst_ni) begin
      sdram_clk_o <= 1'b0;
      sdram_phase_q <= 1'b0;
      sdram_step_q <= '0;
      sdram_cke_o <= 1'b0;
      sdram_cs_no <= 1'b1;
      sdram_ras_no <= 1'b1;
      sdram_cas_no <= 1'b1;
      sdram_we_no <= 1'b1;
      sdram_ba_o <= '0;
      sdram_addr_o <= '0;
      sdram_dqm_o <= 4'hf;
      sdram_dq_o <= '0;
      sdram_dq_oe_o <= '0;
    end else if (platform_started_q) begin
      sdram_clk_o <= ~sdram_clk_o;
      sdram_phase_q <= ~sdram_phase_q;
      if (sdram_phase_q) begin
        sdram_cs_no <= 1'b0;
        sdram_ras_no <= 1'b1;
        sdram_cas_no <= 1'b1;
        sdram_we_no <= 1'b1;
        sdram_dqm_o <= 4'b0;
        sdram_dq_oe_o <= 4'b0;
        unique case (sdram_step_q)
          0: begin sdram_cke_o <= 1'b1; sdram_ras_no <= 0; sdram_we_no <= 0; sdram_addr_o[10] <= 1; end
          1, 2: begin sdram_ras_no <= 0; sdram_cas_no <= 0; end
          3: begin sdram_ras_no <= 0; sdram_cas_no <= 0; sdram_we_no <= 0; sdram_addr_o <= 13'b000_0_010_0_000; end
          4: begin sdram_ras_no <= 0; sdram_addr_o <= 0; sdram_ba_o <= 0; end
          6: begin sdram_cas_no <= 0; sdram_we_no <= 0; sdram_addr_o <= 0; sdram_dq_o <= 32'h4c4e5036; sdram_dq_oe_o <= 4'hf; end
          9: begin sdram_cas_no <= 0; sdram_addr_o <= 0; end
          default: if (sdram_step_q > 10 && sdram_step_q[8:0] == 0) begin
            sdram_ras_no <= 0; sdram_cas_no <= 0;
          end
        endcase
        sdram_step_q <= sdram_step_q + 1'b1;
      end
    end
  end

  always_comb begin
    sd_clk_o = 1'b0;
    sd_cmd_o = 1'b1;
    sd_cmd_oe_o = 1'b0;
    sd_dat_o = 4'hf;
    sd_dat_oe_o = 1'b0;
    pipe_txdata_o = 16'b0;
    pipe_txdatak_o = 2'b0;
    pipe_txelecidle_o = 1'b1;
    pipe_powerdown_o = 2'b11;
    pipe_rate_o = 1'b0;
    pipe_reset_no = pcie_perst_ni;
    pipe_rxpolarity_o = 1'b0;
    pipe_txcompliance_o = 1'b0;
    pipe_txdetectrx_loopback_o = 1'b0;
    entropy_ready_o = 1'b1;
    boot_done_o = platform_started_q;
    boot_error_o = reserved_error_q | uart_error_q;
    core_alive_o = platform_started_q ? 4'hf : 4'b0;
  end

  logic unused;
  always_comb unused = &{1'b0, uart_rx_i, sd_cmd_i, sd_dat_i, sdram_dq_i,
                         pipe_clk_125_i, pipe_rxdata_i, pipe_rxdatak_i,
                         pipe_rxvalid_i, pipe_phystatus_i, pipe_rxelecidle_i,
                         pipe_rxstatus_i, entropy_bit_i, entropy_valid_i,
                         jtag_tck_i, jtag_trst_ni, jtag_tms_i, jtag_tdi_i};
endmodule
