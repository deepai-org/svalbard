module quad_uart_controller (
  input logic clk_i, input logic rst_ni, input logic [3:0] enable_i,
  input logic [63:0] baud_div_i, input logic [31:0] tx_data_i,
  input logic [3:0] tx_valid_i, output logic [3:0] tx_ready_o,
  output logic [31:0] rx_data_o, output logic [3:0] rx_valid_o,
  input logic [3:0] rx_ready_i, input logic [3:0] uart_rx_i,
  output logic [3:0] uart_tx_o, input logic [3:0] error_clear_i,
  output logic [3:0] framing_error_o, output logic [3:0] overrun_error_o
);
  assign tx_ready_o = enable_i;
  assign uart_tx_o = 4'hf;
  assign rx_data_o = 0;
  assign rx_valid_o = 0;
  assign framing_error_o = 0;
  assign overrun_error_o = 0;
endmodule
