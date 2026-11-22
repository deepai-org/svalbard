// Self-checking bench for pt_lo_vtguard (rtl/pt_monitor.sv; row LO-DIG-1, DG9-LO-DIG-1). Run by verification/check_monitor.py
// (base must pass, its mutants must fail). REF_CLK 50 MHz. A reference model counts consecutive REF edges at which the
// synchronized DET is high with the synchronized preset low; vt_runaway must equal the model's sticky flag every cycle.
`timescale 1ns/1ps
`default_nettype none
module tb_lo_vtguard;
    reg rst_n = 0, ref_clk = 0, det = 0, preset = 0, clr = 0;
    wire vt_high, vt_runaway;
    pt_lo_vtguard #(.RUN_CYCLES(64)) dut(.rst_n(rst_n), .ref_clk(ref_clk), .det(det), .cfg_preset(preset), .clr_tgl(clr),
                                         .vt_high(vt_high), .vt_runaway(vt_runaway));
    always #10 ref_clk = ~ref_clk;
    integer errors = 0, checks = 0;
    task chk(input cond, input [511:0] msg);
        begin checks = checks + 1; if (cond !== 1'b1) begin errors = errors + 1; if (errors < 10) $display("FAIL t=%0t: %0s", $time, msg); end end
    endtask
    task refs(input integer n); begin repeat (n) @(posedge ref_clk); #1; end endtask
    // ---- reference model (same two-flop latency as the DUT's synchronizers)
    reg [1:0] d_s, p_s, c_s; reg c_d; integer run_m; reg sticky_m;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin d_s <= 0; p_s <= 0; c_s <= 0; c_d <= 0; run_m <= 0; sticky_m <= 0; end
        else begin
            d_s <= {d_s[0], det}; p_s <= {p_s[0], preset}; c_s <= {c_s[0], clr}; c_d <= c_s[1];
            if (!d_s[1] || p_s[1] || c_s[1] != c_d) run_m <= 0; else if (run_m < 64) run_m <= run_m + 1;
            if (c_s[1] != c_d) sticky_m <= 0; else if (run_m == 64) sticky_m <= 1;
        end
    always @(negedge ref_clk) if (rst_n) begin
        chk(vt_high === d_s[1], "vt_high is not the two-flop synchronized DET");
        chk(vt_runaway === sticky_m, "vt_runaway differs from the reference model");
    end
    integer i, n;
    initial begin
        refs(3); rst_n = 1; refs(3);
        // T1: DET high for about 61 synchronized cycles is not a runaway; >= 64 is (exact count: the model compare)
        det = 1; refs(2 + 60); det = 0; refs(4); chk(vt_runaway === 1'b0, "T1: 61 cycles set the runaway flag");
        det = 1; refs(2 + 70); chk(vt_runaway === 1'b1, "T1: >= 64 cycles did not set the runaway flag");
        det = 0; refs(10); chk(vt_runaway === 1'b1, "T1: the flag is not sticky");
        // T2: write-1-to-clear (toggle) clears it; vt_high stays live
        clr = ~clr; refs(5); chk(vt_runaway === 1'b0, "T2: clear did not clear");
        // T3: preset holds the count: VTUNE high during preset (band search) is not a runaway
        preset = 1; refs(3); det = 1; refs(200); chk(vt_runaway === 1'b0, "T3: runaway flagged while lo_preset = 1");
        preset = 0; refs(2 + 70); chk(vt_runaway === 1'b1, "T3: runaway after the preset release not flagged");
        // T4: a clear while the runaway persists: the flag comes back 64 cycles later
        clr = ~clr; refs(4); chk(vt_runaway === 1'b0, "T4: clear while running away");
        refs(70); chk(vt_runaway === 1'b1, "T4: persisting runaway not flagged again");
        det = 0; clr = ~clr; refs(5);
        // T5: random DET / preset / clear walk against the model (glitchy DET, short pulses)
        for (i = 0; i < 20000; i = i + 1) begin
            n = $urandom % 100;
            if (n < 3) det = ~det; else if (n == 3) preset = ~preset; else if (n == 4) clr = ~clr;
            if (n == 5) begin det = 1; preset = 0; refs(60 + $urandom % 10); end
            #(1 + $urandom % 19);
        end
        // T6: asynchronous reset clears the flag
        det = 1; preset = 0; refs(80); rst_n = 0; #1 chk(vt_runaway === 1'b0 && vt_high === 1'b0, "T6: reset");
        $display("checks %0d errors %0d", checks, errors);
        if (errors == 0) $display("TB_PASS"); else $display("TB_FAIL");
        $finish;
    end
endmodule
`default_nettype wire
