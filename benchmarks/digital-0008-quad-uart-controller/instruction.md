# Four-channel UART controller

Implement `quad_uart_controller` as synthesizable SystemVerilog for GF180MCU.
The task is one complete, compact peripheral—not a UART sub-block.

## Delivery

Copy the starter to `/app/output/rtl/quad_uart_controller.sv` and modify only
that file. Keep the module name and ports unchanged. Run `make visible` from
`/app/input_files` for public simulation and GF180 feedback.

## Interface

```systemverilog
module quad_uart_controller (
  input  logic        clk_i,
  input  logic        rst_ni,
  input  logic [3:0]  enable_i,
  input  logic [63:0] baud_div_i,
  input  logic [31:0] tx_data_i,
  input  logic [3:0]  tx_valid_i,
  output logic [3:0]  tx_ready_o,
  output logic [31:0] rx_data_o,
  output logic [3:0]  rx_valid_o,
  input  logic [3:0]  rx_ready_i,
  input  logic [3:0]  uart_rx_i,
  output logic [3:0]  uart_tx_o,
  input  logic [3:0]  error_clear_i,
  output logic [3:0]  framing_error_o,
  output logic [3:0]  overrun_error_o
);
```

Channel `c` uses `baud_div_i[c*16 +: 16]`, `tx_data_i[c*8 +: 8]`, and
`rx_data_o[c*8 +: 8]`. A legal divisor is 4 through 65535 clock cycles per
serial bit and is sampled when a frame starts.

## Contract

Each channel is an independent 8N1 UART: one low start bit, eight data bits
least-significant bit first, and one high stop bit. TX and RX each have an
8-byte FIFO. Ready/valid transfers occur on a rising edge when both signals
are high. Ordering is exact and no accepted byte may be lost or duplicated.

TX holds high while idle or disabled. RX samples at bit centers. A low stop bit
discards that byte and sets `framing_error_o`. A valid byte arriving at a full
RX FIFO is dropped and sets `overrun_error_o`. Error flags are sticky;
`error_clear_i[c]` clears both flags unless a new error occurs on the same edge,
in which case the new error wins.

Reset is asynchronous active-low. It empties all FIFOs, aborts active frames,
clears errors, deasserts ready/valid, and drives TX high. Disabling a channel
aborts its current TX/RX frame and drives TX high; queued bytes remain.

## Acceptance

The verifier checks all channels separately and concurrently, distinct legal
divisors, FIFO limits and backpressure, framing and overrun recovery, and reset
and disable during frames. It then maps, routes, and times
the unchanged design with `gf180mcu_fd_sc_mcu9t5v0` at the
`nom_ss_125C_4v50` corner. Eligibility requires zero route DRC errors, mapped
simulation agreement, and nonnegative setup slack at 100 MHz.

Correctness and physical eligibility are hard gates. The verifier also reports
post-route timing and standard-cell area. Simulation-only code, inferred
latches, combinational loops, hidden precomputed answers, and modified
interfaces are rejected.
