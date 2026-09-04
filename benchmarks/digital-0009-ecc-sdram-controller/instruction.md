# SECDED SDR SDRAM controller

Implement `ecc_sdram_controller` as synthesizable SystemVerilog for GF180MCU.
The block accepts 64-bit memory requests, stores a 72-bit SECDED codeword in
three x32 SDR SDRAM locations, performs initialization and refresh, and reports
corrected and uncorrectable reads.

## Delivery

Copy the starter to `/app/output/rtl/ecc_sdram_controller.sv`. Keep the module
name, parameters, and ports unchanged. Run `make visible` from
`/app/input_files`.

## Interface

```systemverilog
module ecc_sdram_controller #(
  parameter int INIT_WAIT_CYCLES = 10000,
  parameter int REFRESH_CYCLES   = 780
) (
  input logic clk_i, input logic rst_ni,
  input logic req_valid_i, output logic req_ready_o,
  input logic req_write_i, input logic [21:0] req_addr_i,
  input logic [63:0] req_wdata_i, input logic [7:0] req_wstrb_i,
  output logic rsp_valid_o, input logic rsp_ready_i,
  output logic [63:0] rsp_rdata_o,
  output logic rsp_corrected_o, output logic rsp_uncorrectable_o,
  output logic init_done_o,
  output logic sdram_cke_o, output logic sdram_cs_no,
  output logic sdram_ras_no, output logic sdram_cas_no,
  output logic sdram_we_no, output logic [1:0] sdram_ba_o,
  output logic [12:0] sdram_a_o, output logic [3:0] sdram_dqm_o,
  inout wire [31:0] sdram_dq_io
);
```

The host address is a 64-bit logical-word index. The raw memory is exactly
64 MiB: four banks, 8192 rows, 512 x32 columns. Codeword physical word
`3*req_addr_i + beat`, for beat 0 through 2, maps as column `[8:0]`, bank
`[10:9]`, and row `[23:11]`. Bits 71:64 occupy beat 2 bits 7:0; its other bits
are written zero. This defines a 32 MiB logical memory and leaves the remaining
raw capacity unused.

## ECC and requests

Use extended Hamming SECDED. Place parity at one-based positions 1, 2, 4, 8,
16, 32, and 64 in the 71-bit Hamming word; fill other positions with data bits
0 through 63 in increasing order. Bit 71 is even overall parity across bits
0 through 70. This mapping is normative.

A request transfers when `req_valid_i && req_ready_o`. Exactly one response is
returned for every accepted request. A full write (`req_wstrb_i == 8'hff`)
encodes and writes three beats. A partial write first reads and corrects the old
word, merges selected little-endian byte lanes, then writes a fresh codeword.
If the old word has a double-bit error, the controller returns uncorrectable and
must not write. A read corrects every single-bit error, including a parity-bit
error, and reports `rsp_corrected_o`; a double-bit error reports
`rsp_uncorrectable_o`. Clean writes return a zero-data response with both flags
low. Responses remain stable under backpressure.

## SDR SDRAM protocol

`clk_i` and SDRAM run at 100 MHz. The controller uses burst length 1, sequential
burst type, CAS latency 2, two-cycle tRCD/tRP/tRFC/tWR minima, and auto-precharge
for accesses. After reset it holds CKE low for `INIT_WAIT_CYCLES`, then asserts
CKE and issues: NOP, PRECHARGE ALL, two AUTO REFRESH commands, and LOAD MODE
REGISTER. `init_done_o` rises only after this sequence. While initialized and
idle, issue AUTO REFRESH no later than `REFRESH_CYCLES` clocks after the prior
refresh. Host requests may be backpressured around refresh.

Commands use the standard active-low truth table. DQ is driven only for the
WRITE data cycle. DQM is zero for valid beats and all ones otherwise. Reset is
asynchronous active-low and returns immediately to the uninitialized state.

## Acceptance

The verifier uses an independent SDRAM model and ECC oracle. It checks init and
refresh timing, clean/full/partial accesses, all 72 single-bit error locations,
double-bit detection, row/bank boundaries, request and response backpressure,
and reset recovery. It then routes and times the unchanged controller using
`gf180mcu_fd_sc_mcu9t5v0` at `nom_ss_125C_4v50`. Eligibility requires mapped
agreement, zero route DRC errors, and nonnegative setup slack at 100 MHz.

Correctness and physical eligibility are hard gates. The verifier also reports
post-route timing and standard-cell area. Behavioral memories, simulation-only
shortcuts, latches, and modified interfaces fail.
