`timescale 1ns/1ps
// Checks that the registered decoder's weighted switch sum equals the
// offset-binary code two clocks after it is presented, and the reset clamp.
module tb_dac_logic;
    reg clk = 0, en = 0, hold_zero = 1;
    reg [9:0] code_tc = 0;
    wire [62:0] th, thb; wire [3:0] bn, bnb; wire out_en, load_en_b;
    dac_logic dut(.clk(clk), .en(en), .hold_zero(hold_zero), .code_tc(code_tc), .th(th), .thb(thb),
                  .bn(bn), .bnb(bnb), .out_en(out_en), .load_en_b(load_en_b));
    always #12.5 clk = ~clk;
    function integer weight(input [62:0] t, input [3:0] b);
        integer k, s; begin s = 0; for (k = 0; k < 63; k = k + 1) s = s + 16*t[k]; weight = s + b; end
    endfunction
    integer n, errors = 0, c;
    initial begin
        #30; if (th !== 0 || out_en !== 0 || load_en_b !== 1) begin errors = errors + 1; $display("FAIL reset clamp"); end
        en = 1; @(negedge clk); @(negedge clk); @(negedge clk);
        if (weight(th, bn) != 512) begin errors = errors + 1; $display("FAIL hold_zero %0d", weight(th,bn)); end
        hold_zero = 0;
        for (n = 0; n < 1024; n = n + 1) begin
            code_tc = n; @(negedge clk); @(negedge clk);
            c = (n ^ 512);
            if (weight(th, bn) != c || (thb !== ~th) || (bnb !== ~bn)) begin errors = errors + 1; if (errors < 5) $display("FAIL code %0d got %0d", n, weight(th,bn)); end
        end
        if (errors == 0) $display("PASS dac_logic (1024 codes)"); else $display("FAILURES %0d", errors);
        $finish;
    end
endmodule
