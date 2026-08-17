module gate_wrapper (
    input wire clk,
    input wire rst,
    output wire [3:0] count
);
    wire scan_out;
    counter gate (
        .clk(clk),
        .rst(rst),
        .count(count),
        .scan_enable_0(1'b0),
        .scan_in_0(1'b0),
        .scan_out_0(scan_out)
    );
endmodule
