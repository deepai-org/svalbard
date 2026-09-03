`ifndef LNP64_EXTERNAL_SRAM_BLACKBOX
(* blackbox *)
module gf180mcu_fd_ip_sram__sram512x8m8wm1 (
    input CLK, input CEN, input GWEN, input [7:0] WEN,
    input [8:0] A, input [7:0] D, output [7:0] Q
);
endmodule
`endif

module lnp64_sram_64x4096_1rw (
    input logic clk_i, input logic en_i, input logic we_i,
    input logic [11:0] addr_i, input logic [63:0] wdata_i,
    input logic [7:0] wmask_i, output logic [63:0] rdata_o
);
  logic [2:0] read_bank_q;
  wire [7:0] leaf_q [0:7][0:7];

  always_ff @(posedge clk_i)
    if (en_i && !we_i) read_bank_q <= addr_i[11:9];

  genvar bank, lane;
  generate
    for (bank = 0; bank < 8; bank = bank + 1) begin : g_bank
      for (lane = 0; lane < 8; lane = lane + 1) begin : g_lane
        (* keep *) gf180mcu_fd_ip_sram__sram512x8m8wm1 leaf (
          .CLK(clk_i),
          .CEN(~(en_i && addr_i[11:9] == bank[2:0])),
          .GWEN(~we_i),
          .WEN({8{~wmask_i[lane]}}),
          .A(addr_i[8:0]),
          .D(wdata_i[lane*8 +: 8]),
          .Q(leaf_q[bank][lane])
        );
      end
    end
    for (lane = 0; lane < 8; lane = lane + 1) begin : g_read
      always_comb rdata_o[lane*8 +: 8] = leaf_q[read_bank_q][lane];
    end
  endgenerate
endmodule

module lnp64_sram_512x1024_1rw (
    input logic clk_i, input logic en_i, input logic we_i,
    input logic [9:0] addr_i, input logic [511:0] wdata_i,
    input logic [63:0] wmask_i, output logic [511:0] rdata_o
);
  logic read_bank_q;
  wire [7:0] leaf_q [0:1][0:63];

  always_ff @(posedge clk_i)
    if (en_i && !we_i) read_bank_q <= addr_i[9];

  genvar bank, lane;
  generate
    for (bank = 0; bank < 2; bank = bank + 1) begin : g_bank
      for (lane = 0; lane < 64; lane = lane + 1) begin : g_lane
        (* keep *) gf180mcu_fd_ip_sram__sram512x8m8wm1 leaf (
          .CLK(clk_i),
          .CEN(~(en_i && addr_i[9] == bank[0])),
          .GWEN(~we_i),
          .WEN({8{~wmask_i[lane]}}),
          .A(addr_i[8:0]),
          .D(wdata_i[lane*8 +: 8]),
          .Q(leaf_q[bank][lane])
        );
      end
    end
    for (lane = 0; lane < 64; lane = lane + 1) begin : g_read
      always_comb rdata_o[lane*8 +: 8] = leaf_q[read_bank_q][lane];
    end
  endgenerate
endmodule
