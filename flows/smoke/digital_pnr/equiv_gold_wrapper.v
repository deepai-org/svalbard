module gold_wrapper (
    input wire clk,
    input wire rst,
    output wire [3:0] count
);
    counter gold (.clk(clk), .rst(rst), .count(count));
endmodule
