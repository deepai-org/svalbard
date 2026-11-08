`timescale 1ns/1ps
module tb_adc_code_reg;
    reg [9:0] bp = 0; reg done = 0, en = 0;
    wire [9:0] code_tc; wire overload, done_o;
    adc_code_reg dut(.bp(bp), .done(done), .en(en), .code_tc(code_tc), .overload(overload), .done_o(done_o));
    integer err = 0;
    initial begin
        #1 en = 1;
        bp = 10'b1000000000; #1 done = 1; #1;   // ob = 0000000001 -> code 1-512
        if ($signed(code_tc) !== -511 || done_o !== 1) begin err = err + 1; $display("FAIL a %0d", $signed(code_tc)); end
        done = 0; #1 if (done_o !== 0) begin err = err + 1; $display("FAIL done clear"); end
        bp = 10'b0000000001; #1 done = 1; #1;   // ob = 1000000000 -> code 0
        if (code_tc !== 0) begin err = err + 1; $display("FAIL b %0d", $signed(code_tc)); end
        bp = 10'b1111111111; done = 0; #1 done = 1; #1;
        if ($signed(code_tc) !== 511 || overload !== 1) begin err = err + 1; $display("FAIL c"); end
        en = 0; #1 if (code_tc !== 0 || done_o !== 0) begin err = err + 1; $display("FAIL clamp"); end
        if (err == 0) $display("PASS adc_code_reg"); $finish;
    end
endmodule
