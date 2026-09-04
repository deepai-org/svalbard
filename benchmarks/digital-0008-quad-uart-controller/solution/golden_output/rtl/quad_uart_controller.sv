module uart_channel (
  input  logic        clk_i,
  input  logic        rst_ni,
  input  logic        enable_i,
  input  logic [15:0] baud_div_i,
  input  logic [7:0]  tx_data_i,
  input  logic        tx_valid_i,
  output logic        tx_ready_o,
  output logic [7:0]  rx_data_o,
  output logic        rx_valid_o,
  input  logic        rx_ready_i,
  input  logic        uart_rx_i,
  output logic        uart_tx_o,
  input  logic        error_clear_i,
  output logic        framing_error_o,
  output logic        overrun_error_o
);
  logic [7:0] tx_mem [0:7];
  logic [2:0] tx_wr_ptr, tx_rd_ptr;
  logic [3:0] tx_count;
  logic       tx_active;
  logic [3:0] tx_bit;
  logic [7:0] tx_shift;
  logic [15:0] tx_div, tx_timer;

  logic [7:0] rx_mem [0:7];
  logic [2:0] rx_wr_ptr, rx_rd_ptr;
  logic [3:0] rx_count;
  logic       rx_meta, rx_sync, rx_active;
  logic [3:0] rx_bit;
  logic [7:0] rx_shift;
  logic [15:0] rx_div, rx_timer;

  wire tx_push = tx_valid_i && tx_ready_o;
  wire tx_pop = enable_i && !tx_active && (tx_count != 0);
  wire rx_pop = rx_valid_o && rx_ready_i;
  wire rx_stop = rx_active && (rx_timer == 0) && (rx_bit == 9);
  wire rx_good = rx_stop && rx_sync;
  wire rx_store = rx_good && ((rx_count != 8) || rx_pop);

  always_comb begin
    tx_ready_o = rst_ni && enable_i && (tx_count != 8);
    rx_valid_o = rst_ni && (rx_count != 0);
    rx_data_o = rx_mem[rx_rd_ptr];
    if (!rst_ni || !enable_i || !tx_active)
      uart_tx_o = 1'b1;
    else if (tx_bit == 0)
      uart_tx_o = 1'b0;
    else if (tx_bit <= 8)
      uart_tx_o = tx_shift[tx_bit-1];
    else
      uart_tx_o = 1'b1;
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      tx_wr_ptr <= 0;
      tx_rd_ptr <= 0;
      tx_count <= 0;
    end else begin
      if (tx_push) begin
        tx_mem[tx_wr_ptr] <= tx_data_i;
        tx_wr_ptr <= tx_wr_ptr + 1'b1;
      end
      if (tx_pop)
        tx_rd_ptr <= tx_rd_ptr + 1'b1;
      case ({tx_push, tx_pop})
        2'b10: tx_count <= tx_count + 1'b1;
        2'b01: tx_count <= tx_count - 1'b1;
        default: tx_count <= tx_count;
      endcase
    end
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      tx_active <= 0;
      tx_bit <= 0;
      tx_shift <= 0;
      tx_div <= 4;
      tx_timer <= 0;
    end else if (!enable_i) begin
      tx_active <= 0;
      tx_bit <= 0;
      tx_timer <= 0;
    end else if (!tx_active) begin
      if (tx_pop) begin
        tx_active <= 1;
        tx_bit <= 0;
        tx_shift <= tx_mem[tx_rd_ptr];
        tx_div <= baud_div_i;
        tx_timer <= baud_div_i - 1'b1;
      end
    end else if (tx_timer != 0) begin
      tx_timer <= tx_timer - 1'b1;
    end else if (tx_bit == 9) begin
      tx_active <= 0;
      tx_bit <= 0;
    end else begin
      tx_bit <= tx_bit + 1'b1;
      tx_timer <= tx_div - 1'b1;
    end
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rx_meta <= 1;
      rx_sync <= 1;
    end else begin
      rx_meta <= uart_rx_i;
      rx_sync <= rx_meta;
    end
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rx_active <= 0;
      rx_bit <= 0;
      rx_shift <= 0;
      rx_div <= 4;
      rx_timer <= 0;
    end else if (!enable_i) begin
      rx_active <= 0;
      rx_bit <= 0;
      rx_timer <= 0;
    end else if (!rx_active) begin
      if (!rx_sync) begin
        rx_active <= 1;
        rx_bit <= 0;
        rx_div <= baud_div_i;
        rx_timer <= (baud_div_i >> 1) - 1'b1;
      end
    end else if (rx_timer != 0) begin
      rx_timer <= rx_timer - 1'b1;
    end else if (rx_bit == 0) begin
      if (rx_sync)
        rx_active <= 0;
      else begin
        rx_bit <= 1;
        rx_timer <= rx_div - 1'b1;
      end
    end else if (rx_bit <= 8) begin
      rx_shift[rx_bit-1] <= rx_sync;
      rx_bit <= rx_bit + 1'b1;
      rx_timer <= rx_div - 1'b1;
    end else begin
      rx_active <= 0;
      rx_bit <= 0;
    end
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rx_wr_ptr <= 0;
      rx_rd_ptr <= 0;
      rx_count <= 0;
    end else begin
      if (rx_store) begin
        rx_mem[rx_wr_ptr] <= rx_shift;
        rx_wr_ptr <= rx_wr_ptr + 1'b1;
      end
      if (rx_pop)
        rx_rd_ptr <= rx_rd_ptr + 1'b1;
      case ({rx_store, rx_pop})
        2'b10: rx_count <= rx_count + 1'b1;
        2'b01: rx_count <= rx_count - 1'b1;
        default: rx_count <= rx_count;
      endcase
    end
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      framing_error_o <= 0;
      overrun_error_o <= 0;
    end else begin
      if (error_clear_i) begin
        framing_error_o <= 0;
        overrun_error_o <= 0;
      end
      if (rx_stop && !rx_sync)
        framing_error_o <= 1;
      if (rx_good && !rx_store)
        overrun_error_o <= 1;
    end
  end
endmodule

module quad_uart_controller (
  input logic clk_i, input logic rst_ni, input logic [3:0] enable_i,
  input logic [63:0] baud_div_i, input logic [31:0] tx_data_i,
  input logic [3:0] tx_valid_i, output logic [3:0] tx_ready_o,
  output logic [31:0] rx_data_o, output logic [3:0] rx_valid_o,
  input logic [3:0] rx_ready_i, input logic [3:0] uart_rx_i,
  output logic [3:0] uart_tx_o, input logic [3:0] error_clear_i,
  output logic [3:0] framing_error_o, output logic [3:0] overrun_error_o
);
  genvar c;
  generate for (c = 0; c < 4; c = c + 1) begin : g_uart
    uart_channel channel (
      .clk_i, .rst_ni, .enable_i(enable_i[c]),
      .baud_div_i(baud_div_i[c*16 +: 16]),
      .tx_data_i(tx_data_i[c*8 +: 8]), .tx_valid_i(tx_valid_i[c]),
      .tx_ready_o(tx_ready_o[c]), .rx_data_o(rx_data_o[c*8 +: 8]),
      .rx_valid_o(rx_valid_o[c]), .rx_ready_i(rx_ready_i[c]),
      .uart_rx_i(uart_rx_i[c]), .uart_tx_o(uart_tx_o[c]),
      .error_clear_i(error_clear_i[c]),
      .framing_error_o(framing_error_o[c]),
      .overrun_error_o(overrun_error_o[c])
    );
  end endgenerate
endmodule
