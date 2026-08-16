`timescale 1ns/1ps

module counter_gate_tb;
    reg clk = 1'b0;
    reg rst = 1'b1;
    wire [3:0] count;
    supply1 VDD;
    supply0 VSS;
    integer expected;

    counter dut (
        .clk(clk),
        .rst(rst),
        .count(count),
        .VDD(VDD),
        .VSS(VSS)
    );

    always #5 clk = ~clk;

    initial begin
        repeat (2) @(posedge clk);
        #1;
        if (count !== 4'h0) begin
            $fatal(1, "counter failed powered-netlist reset: %h", count);
        end
        rst = 1'b0;
        for (expected = 1; expected <= 5; expected = expected + 1) begin
            @(posedge clk);
            #1;
            if (count !== expected[3:0]) begin
                $fatal(1, "counter mismatch: expected %h observed %h", expected[3:0], count);
            end
        end
        $display("powered gate simulation: PASS");
        $finish;
    end
endmodule
