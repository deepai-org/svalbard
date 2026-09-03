module lnp64_sram_64x4096_1rw (
    input logic clk_i, input logic en_i, input logic we_i,
    input logic [11:0] addr_i, input logic [63:0] wdata_i,
    input logic [7:0] wmask_i, output logic [63:0] rdata_o
);
  logic [63:0] mem [0:4095];
  integer lane;
  always_ff @(posedge clk_i) if (en_i) begin
    if (we_i) begin
      for (lane = 0; lane < 8; lane++) if (wmask_i[lane])
        mem[addr_i][lane*8 +: 8] <= wdata_i[lane*8 +: 8];
    end else begin
      rdata_o <= mem[addr_i];
    end
  end
endmodule

module lnp64_sram_512x1024_1rw (
    input logic clk_i, input logic en_i, input logic we_i,
    input logic [9:0] addr_i, input logic [511:0] wdata_i,
    input logic [63:0] wmask_i, output logic [511:0] rdata_o
);
  logic [511:0] mem [0:1023];
  integer lane;
  always_ff @(posedge clk_i) if (en_i) begin
    if (we_i) begin
      for (lane = 0; lane < 64; lane++) if (wmask_i[lane])
        mem[addr_i][lane*8 +: 8] <= wdata_i[lane*8 +: 8];
    end else begin
      rdata_o <= mem[addr_i];
    end
  end
endmodule
