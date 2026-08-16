module counter_tb;
    logic clk = 1'b0;
    logic rst = 1'b1;
    logic [3:0] count;

    counter dut (
        .clk(clk),
        .rst(rst),
        .count(count)
    );

    always #5 clk = ~clk;

    initial begin
        repeat (2) @(posedge clk);
        rst <= 1'b0;
        for (int expected = 1; expected <= 15; expected++) begin
            @(posedge clk);
            #1;
            if (count !== expected[3:0]) begin
                $fatal(1, "counter mismatch: expected %0d, observed %0d", expected, count);
            end
        end
        $display("digital simulation: PASS");
        $finish;
    end
endmodule
