module gf180mcu_fd_ip_sram__sram512x8m8wm1 (
    input wire CLK, input wire CEN, input wire GWEN,
    input wire [7:0] WEN, input wire [8:0] A, input wire [7:0] D,
    output reg [7:0] Q, inout wire VDD, inout wire VSS
);
  reg [7:0] mem [0:511];
  integer bit_index;
  always @(posedge CLK) begin
    if (!CEN) begin
      if (!GWEN) begin
        for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1)
          if (!WEN[bit_index]) mem[A][bit_index] <= D[bit_index];
      end else begin
        Q <= mem[A];
      end
    end
  end
endmodule
