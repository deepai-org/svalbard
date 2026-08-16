`timescale 1ns/1ps

module counter_scan_tb;
    reg clk = 1'b0;
    reg rst = 1'b1;
    reg scan_enable_0 = 1'b0;
    reg scan_in_0 = 1'b0;
    wire scan_out_0;
    wire [3:0] count;

    counter dut (
        .clk(clk),
        .rst(rst),
        .count(count),
        .scan_enable_0(scan_enable_0),
        .scan_in_0(scan_in_0),
        .scan_out_0(scan_out_0)
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
        if (count !== 4'ha || scan_out_0 !== 1'b1) begin
            $fatal(1, "scan chain mismatch: count=%h scan_out=%b", count, scan_out_0);
        end
        scan_enable_0 = 1'b0;
        @(posedge clk);
        #1;
        if (count !== 4'hb) begin
            $fatal(1, "scan netlist failed functional handoff: %h", count);
        end
        $display("stitched scan simulation: PASS");
        $finish;
    end
endmodule
