`timescale 1ns/1ps

module counter_scan_tb;
    reg clk = 1'b0;
    reg rst = 1'b1;
    reg scan_enable_0 = 1'b0;
    reg scan_in_0 = 1'b0;
    wire scan_out_0;
    wire [3:0] count;
    reg [3:0] shifted_out;
    reg [3:0] expected_count;
    integer index;
`ifdef USE_POWER_PINS
    supply1 VDD;
    supply0 VSS;
`endif

    counter dut (
        .clk(clk),
        .rst(rst),
        .count(count),
        .scan_enable_0(scan_enable_0),
        .scan_in_0(scan_in_0),
        .scan_out_0(scan_out_0)
`ifdef USE_POWER_PINS
        ,.VDD(VDD)
        ,.VSS(VSS)
`endif
    );

    always #5 clk = ~clk;

    task shift_bit(input bit value);
        begin
            scan_in_0 = value;
            @(posedge clk);
            #1;
        end
    endtask

    initial begin
        repeat (2) @(posedge clk);
        #1;
        if (count !== 4'h0) begin
            $fatal(1, "scan netlist failed functional reset: %h", count);
        end
        rst = 1'b0;
        scan_enable_0 = 1'b1;
        shift_bit(1'b1);
        shift_bit(1'b0);
        shift_bit(1'b1);
        shift_bit(1'b0);
        for (index = 3; index >= 0; index = index - 1) begin
            shifted_out[index] = scan_out_0;
            shift_bit(1'b0);
        end
        if (shifted_out !== 4'b1010) begin
            $fatal(1, "scan chain mismatch: shifted_out=%b", shifted_out);
        end
        scan_enable_0 = 1'b0;
        expected_count = count + 4'h1;
        @(posedge clk);
        #1;
        if (count !== expected_count) begin
            $fatal(1, "scan netlist failed functional handoff: expected=%h observed=%h", expected_count, count);
        end
        $display("stitched scan simulation: PASS");
        $finish;
    end
endmodule
