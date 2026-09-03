`timescale 1ns/1ps

module test;
  logic clk_250 = 0, pipe_clk = 0;
  logic [15:0] down_data, up_data;
  logic [1:0] down_k, up_k;
  logic down_idle, up_idle;
  integer cycles = 0;
  wire reset_n = cycles > 20;

  always #2 clk_250 = ~clk_250;
  always #4 pipe_clk = ~pipe_clk;
  always @(posedge clk_250) begin
    cycles <= cycles + 1;
    if (cycles == 5_000_000) $fatal(1, "PCIe oracle self-test timeout");
  end

  task Fatal;
    begin
      $fatal(1, "pcievhost fatal error");
    end
  endtask

  pcieVHostPipex1 #(.NodeNum(0), .EndPoint(0), .DataWidth(16), .Gen2Clk(0)) root (
    .pcieclk(clk_250), .pclk(pipe_clk), .nreset(reset_n),
    .Gen2ClkSel(), .ClkOut(),
`ifdef VERILATOR
    .ElecIdleOut(down_idle), .ElecIdleIn(up_idle),
`endif
    .RxData(up_data), .RxDataK(up_k), .TxData(down_data), .TxDataK(down_k)
  );

  pcieVHostPipex1 #(.NodeNum(1), .EndPoint(1), .DataWidth(16), .Gen2Clk(0)) endpoint (
    .pcieclk(clk_250), .pclk(pipe_clk), .nreset(reset_n),
    .Gen2ClkSel(), .ClkOut(),
`ifdef VERILATOR
    .ElecIdleOut(up_idle), .ElecIdleIn(down_idle),
`endif
    .RxData(down_data), .RxDataK(down_k), .TxData(up_data), .TxDataK(up_k)
  );
endmodule
