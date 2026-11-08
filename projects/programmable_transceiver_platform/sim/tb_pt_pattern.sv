// Self-checking test of rtl/pt_pattern.sv (P2-6).
//  * cores: pt_pattern_gen modes against a bit-serial LFSR reference at W=16 (former
//    pt_wtx_pattern width), W=10 and W=20; step/hold, ce gating and error injection
//  * TX gearbox pt_pattern_tx: the consumed 10-bit line words (random request stalls)
//    equal the bit-serial reference in every PRBS mode; fixed patterns; inject
//  * RX gearbox + 20-bit checker pt_pattern_rx: lock at arbitrary bit alignment with
//    gappy and back-to-back valid, exact counting of injected single/double errors,
//    saturation, bit-slip loss/relock with sticky lost_lock, polarity, constant lines,
//    clear; Gray output changes at most one bit per clock, never wraps, converges
//  * loopback pt_pattern_tx -> pt_pattern_rx with random request/valid and injection
//  * lockup guard after a live PRBS31 -> PRBS7 change
`timescale 1ns/1ps
module tb_pt_pattern;
    reg clk = 0; always #2 clk = ~clk;
    integer errors = 0, i, k, b, n;

    // ---------------- cores
    reg g_rst_n = 0, g_step = 1, g_ce = 1, g_inv = 0, g_inject = 0;
    reg [2:0] g_mode = 3;
    wire [15:0] w16; wire [9:0] w10; wire [19:0] w20;
    pt_pattern_gen #(.W(16)) gen16(.clk(clk), .rst_n(g_rst_n), .ce(1'b1), .step(1'b1), .cfg_mode(g_mode), .cfg_invert(g_inv),
        .cfg_user(16'hC3A5), .data_in(16'h1234), .inject(1'b0), .word(w16));
    pt_pattern_gen #(.W(10)) gen10(.clk(clk), .rst_n(g_rst_n), .ce(g_ce), .step(g_step), .cfg_mode(g_mode), .cfg_invert(g_inv),
        .cfg_user(10'h2A5), .data_in(10'h123), .inject(g_inject), .word(w10));
    pt_pattern_gen #(.W(20)) gen20(.clk(clk), .rst_n(g_rst_n), .ce(1'b1), .step(1'b1), .cfg_mode(g_mode), .cfg_invert(g_inv),
        .cfg_user(20'hA52A5), .data_in(20'h12345), .inject(1'b0), .word(w20));

    // bit-serial reference: all-ones seed, b = r[L-1]^r[T-1], r = {r,b}
    reg [30:0] r; reg rb;
    function automatic [31:0] lt(input [2:0] m); lt = m == 1 ? {16'd7, 16'd6} : m == 2 ? {16'd15, 16'd14} : {16'd31, 16'd28}; endfunction
    task ref_bit(input [2:0] m); integer L, T; begin
        L = lt(m) >> 16; T = lt(m) & 16'hffff;
        rb = r[L-1] ^ r[T-1]; r = {r[29:0], rb};
    end endtask
    reg [15:0] e16; reg [9:0] e10; reg [19:0] e20;
    reg [30:0] r16, r10, r20;

    task gen_reset; begin @(negedge clk); g_rst_n = 0; @(negedge clk); g_rst_n = 1; end endtask

    task check_gen_prbs(input [2:0] m); begin
        g_mode = m; g_step = 1; g_ce = 1; gen_reset;
        r16 = {31{1'b1}}; r10 = r16; r20 = r16;
        for (k = 0; k < 300; k = k + 1) begin
            r = r16; for (b = 0; b < 16; b = b + 1) begin ref_bit(m); e16[b] = rb; end r16 = r;
            r = r10; for (b = 0; b < 10; b = b + 1) begin ref_bit(m); e10[b] = rb; end r10 = r;
            r = r20; for (b = 0; b < 20; b = b + 1) begin ref_bit(m); e20[b] = rb; end r20 = r;
            @(posedge clk); #0.5;
            if (w16 !== e16 || w10 !== e10 || w20 !== e20) begin errors = errors + 1;
                if (errors < 8) $display("core mode %0d word %0d: %h/%h %h/%h %h/%h", m, k, w16, e16, w10, e10, w20, e20); end
        end
    end endtask

    // ---------------- TX gearbox
    reg t_rst_n = 0, t_req = 0, t_inject = 0; reg [2:0] t_mode = 3; reg t_inv = 0;
    wire [9:0] t_word; wire t_ready;
    pt_pattern_tx #(.W(10)) tx(.clk(clk), .rst_n(t_rst_n), .request(t_req), .cfg_mode(t_mode), .cfg_invert(t_inv),
        .cfg_user(10'h2A5), .inject(t_inject), .word(t_word), .ready(t_ready));
    task tx_reset; begin @(negedge clk); t_rst_n = 0; t_req = 0; @(negedge clk); t_rst_n = 1; end endtask
    // consume `count` words with random stalls; compare with the bit-serial reference
    task check_tx(input [2:0] m, input integer count); integer taken, flip_at; begin
        t_mode = m; tx_reset; r = {31{1'b1}}; taken = 0;
        while (taken < count) begin
            @(negedge clk); t_req = $random & 1;
            if (t_req && t_ready) begin
                for (b = 0; b < 10; b = b + 1) begin ref_bit(m); e10[b] = rb; end
                if (t_word !== e10) begin errors = errors + 1; if (errors < 8) $display("tx mode %0d word %0d got %h exp %h", m, taken, t_word, e10); end
                taken = taken + 1;
            end
        end
        @(negedge clk); t_req = 0;
    end endtask

    // ---------------- RX gearbox + checker, driven by a line model
    reg c_en = 0, c_valid = 0, c_inv = 0, c_clear = 0, c_rst_n = 0; reg [2:0] c_mode = 3; reg [9:0] c_data = 0;
    wire c_lock, c_lost, s_lock, s_lost; wire [15:0] c_err, c_gray; wire [3:0] s_err, s_gray;
    pt_pattern_rx #(.W(10), .CW(16)) chk(.clk(clk), .rst_n(c_rst_n), .enable(c_en), .valid(c_valid), .data(c_data),
        .cfg_mode(c_mode), .cfg_invert(c_inv), .clear(c_clear), .locked(c_lock), .lost_lock(c_lost), .errors(c_err), .errors_gray(c_gray));
    pt_pattern_rx #(.W(10), .CW(4)) chk_sat(.clk(clk), .rst_n(c_rst_n), .enable(c_en), .valid(c_valid), .data(c_data),
        .cfg_mode(c_mode), .cfg_invert(c_inv), .clear(c_clear), .locked(s_lock), .lost_lock(s_lost), .errors(s_err), .errors_gray(s_gray));

    wire t_lock, t_lost; wire [9:0] t_err, t_gray;
    pt_pattern_rx #(.W(10), .CW(10)) chk10(.clk(clk), .rst_n(c_rst_n), .enable(c_en), .valid(c_valid), .data(c_data),
        .cfg_mode(c_mode), .cfg_invert(c_inv), .clear(c_clear), .locked(t_lock), .lost_lock(t_lost), .errors(t_err), .errors_gray(t_gray));
    // Gray monitor: one bit per clock at most (except across clear/reset), no wrap
    function automatic [15:0] g2b(input [15:0] g); integer j; begin
        g2b[15] = g[15]; for (j = 14; j >= 0; j = j - 1) g2b[j] = g2b[j+1] ^ g[j]; end endfunction
    function automatic integer ones16(input [15:0] v); integer j; begin
        ones16 = 0; for (j = 0; j < 16; j = j + 1) ones16 = ones16 + v[j]; end endfunction
    reg [15:0] gprev; reg [3:0] sprev; reg clr_d = 0; integer gray_bad = 0, gray_steps = 0;
    always @(posedge clk) begin
        #0.1;
        if (c_rst_n && !c_clear && !clr_d) begin
            if (ones16(c_gray ^ gprev) > 1 || ones16({12'd0, s_gray ^ sprev}) > 1) begin gray_bad = gray_bad + 1;
                if (gray_bad < 4) $display("gray step %h -> %h, sat %h -> %h at %0t", gprev, c_gray, sprev, s_gray, $time); end
            if (g2b(c_gray) < g2b(gprev)) gray_bad = gray_bad + 1;   // never backward, never wraps
            if (c_gray != gprev) gray_steps = gray_steps + 1;
        end
        gprev = c_gray; sprev = s_gray; clr_d = c_clear;
    end

    integer flips = 0, dflips = 0, wflips = 0; reg slip = 0, polarity = 0; integer gap = 1;
    task line_word(input [2:0] m); integer j; begin
        for (j = 0; j < 10; j = j + 1) begin
            if (slip && j == 4) begin ref_bit(m); slip = 0; end
            ref_bit(m); c_data[j] = rb ^ polarity;
        end
        if (flips > 0) begin c_data[3] = ~c_data[3]; flips = flips - 1; end
        if (dflips > 0) begin c_data[2] = ~c_data[2]; c_data[8] = ~c_data[8]; dflips = dflips - 1; end
        @(negedge clk); c_valid = 1; @(negedge clk); c_valid = 0;
        // gap: 0 = back-to-back valid, 1 = random gaps
        if (gap && ($random & 1)) repeat (1 + ($random & 3)) @(negedge clk);
    end endtask
    // back-to-back variant: keep valid high across words
    task line_words(input [2:0] m, input integer count); integer q; begin
        for (q = 0; q < count; q = q + 1) begin
            if (gap) line_word(m);
            else begin
                ref_word(m); c_valid = 1; @(negedge clk);
            end
        end
        c_valid = 0; repeat (8) @(negedge clk);
    end endtask
    task ref_word(input [2:0] m); integer j; begin
        for (j = 0; j < 10; j = j + 1) begin
            if (slip && j == 4) begin ref_bit(m); slip = 0; end
            ref_bit(m); c_data[j] = rb ^ polarity;
        end
        if (flips > 0) begin c_data[3] = ~c_data[3]; flips = flips - 1; end
        if (dflips > 0) begin c_data[2] = ~c_data[2]; c_data[8] = ~c_data[8]; dflips = dflips - 1; end
        if (wflips > 0) begin c_data = ~c_data; wflips = wflips - 1; end
    end endtask
    task chk_clear; begin @(negedge clk); c_clear = 1; repeat (2) @(negedge clk); c_clear = 0; end endtask
    task settle; begin repeat (200) @(negedge clk); end endtask   // count drains one per 2 clocks
    task wait_gray; integer w; begin
        w = 0; while (g2b(c_gray) != c_err && w < 2000) begin @(negedge clk); w = w + 1; end
        if (g2b(c_gray) != c_err) begin errors = errors + 1; $display("gray %h does not converge to %0d", c_gray, c_err); end
    end endtask

    task check_rx(input [2:0] m, input integer offset, input integer gapmode); integer lockat; begin
        gap = gapmode; c_mode = m; c_inv = 0; polarity = 0; flips = 0; dflips = 0; slip = 0; c_en = 1; chk_clear;
        r = {31{1'b1}};
        for (k = 0; k < offset; k = k + 1) ref_bit(m);   // arbitrary bit alignment
        lockat = -1;
        for (k = 0; k < 60 && lockat < 0; k = k + 1) begin line_words(m, 1); if (c_lock) lockat = k; end
        if (lockat < 0 || lockat > 16) begin errors = errors + 1; $display("mode %0d offset %0d: lock after %0d words", m, offset, lockat); end
        line_words(m, 400);
        if (!c_lock || c_err !== 0 || c_lost || c_gray !== 0) begin errors = errors + 1; $display("mode %0d clean run: lock %b err %0d lost %b", m, c_lock, c_err, c_lost); end
        for (n = 0; n < 37; n = n + 1) begin flips = 1; line_words(m, 7); end
        settle; if (s_err !== 4'hf) begin errors = errors + 1; $display("mode %0d saturation after 37: %0d", m, s_err); end
        for (n = 0; n < 5; n = n + 1) begin dflips = 1; line_words(m, 7); end
        settle;
        if (!c_lock || c_err !== 47 || c_lost) begin errors = errors + 1; $display("mode %0d 37 single + 5 double: lock %b err %0d lost %b", m, c_lock, c_err, c_lost); end
        wait_gray;
        if (s_err !== 4'hf || s_gray !== 4'b1000) begin errors = errors + 1; $display("mode %0d saturation %0d gray %b", m, s_err, s_gray); end
        slip = 1; line_words(m, 16);
        if (!c_lost) begin errors = errors + 1; $display("mode %0d slip: lost_lock not set", m); end
        line_words(m, 30);
        if (!c_lock) begin errors = errors + 1; $display("mode %0d no relock after slip", m); end
        chk_clear; line_words(m, 60); settle;
        if (!c_lock || c_err !== 0 || c_lost || c_gray !== 0) begin errors = errors + 1; $display("mode %0d after clear: lock %b err %0d lost %b", m, c_lock, c_err, c_lost); end
        c_en = 0; repeat (2) @(negedge clk); c_en = 1; polarity = 1;   // enable/clear act on ce: hold >= 2 clocks
        line_words(m, 80);
        if (c_lock) begin errors = errors + 1; $display("mode %0d locked to inverted stream", m); end
        c_inv = 1; chk_clear; line_words(m, 80); settle;
        if (!c_lock || c_err !== 0) begin errors = errors + 1; $display("mode %0d invert: lock %b err %0d", m, c_lock, c_err); end
        c_en = 0; c_inv = 0; polarity = 0; repeat (2) @(negedge clk);
    end endtask

    // ---------------- loopback TX -> RX
    reg lb = 0; reg [7:0] rnd;
    task loopback(input [2:0] m); integer injected; begin
        t_mode = m; c_mode = m; c_inv = 0; t_inv = 0; c_en = 1; tx_reset; chk_clear; injected = 0; lb = 1;
        for (k = 0; k < 4000; k = k + 1) begin
            @(negedge clk); rnd = $random;
            t_inject = (k % 97 == 50) && k > 300; if (t_inject) injected = injected + 1;
        end
        t_inject = 0; repeat (60) @(negedge clk); lb = 0; c_valid = 0; t_req = 0; settle; wait_gray;
        if (!c_lock || c_err !== injected || c_lost) begin errors = errors + 1;
            $display("loopback mode %0d: lock %b err %0d expected %0d lost %b", m, c_lock, c_err, injected, c_lost); end
        else $display("loopback mode %0d: %0d injected, %0d counted, gray %h", m, injected, c_err, c_gray);
        c_en = 0; repeat (2) @(negedge clk);
    end endtask
    // in loopback the checker receives exactly the words the TX consumer takes
    always @(*) if (lb) begin t_req = rnd[0] | rnd[1]; c_valid = t_req && t_ready; c_data = t_word; end

    initial begin
        #5 g_rst_n = 1; t_rst_n = 1; c_rst_n = 1;
        check_gen_prbs(1); check_gen_prbs(2); check_gen_prbs(3);
        // fixed patterns (former pt_wtx_pattern behaviour at W=16)
        g_mode = 0; gen_reset; @(posedge clk); #0.5 if (w16 !== 16'h1234 || w10 !== 10'h123) begin errors = errors + 1; $display("payload"); end
        g_mode = 4; @(posedge clk); @(posedge clk); #0.5 if (w16 !== 16'h5555 || w10 !== 10'h155 || w20 !== 20'h55555) begin errors = errors + 1; $display("clock"); end
        g_mode = 6; @(posedge clk); @(posedge clk); #0.5 if (w16 !== 16'hC3A5 || w10 !== 10'h2A5) begin errors = errors + 1; $display("user"); end
        g_inv = 1;  @(posedge clk); @(posedge clk); #0.5 if (w16 !== 16'h3C5A || w10 !== 10'h15A) begin errors = errors + 1; $display("invert"); end
        g_inv = 0; g_mode = 7; @(posedge clk); @(posedge clk); #0.5 if (w16 !== 0 || w10 !== 0) begin errors = errors + 1; $display("idle"); end
        g_mode = 5; @(posedge clk); #0.5 n = w16; @(posedge clk); #0.5
        if (!((n == 16'hFFFF && w16 == 0) || (n == 0 && w16 == 16'hFFFF))) begin errors = errors + 1; $display("slow"); end
        // step/ce hold and single-bit injection at W=10
        g_mode = 3; g_step = 0; gen_reset; r = {31{1'b1}};
        for (b = 0; b < 10; b = b + 1) begin ref_bit(3); e10[b] = rb; end
        repeat (5) @(posedge clk); #0.5 if (w10 !== e10) begin errors = errors + 1; $display("prime/hold %h %h", w10, e10); end
        @(negedge clk); g_inject = 1; @(negedge clk); g_inject = 0; repeat (3) @(negedge clk);
        if (w10 !== e10) begin errors = errors + 1; $display("inject applied without step"); end
        g_ce = 0; g_step = 1; repeat (3) @(negedge clk);
        if (w10 !== e10) begin errors = errors + 1; $display("advanced with ce=0"); end
        g_ce = 1; @(negedge clk); g_step = 0;
        for (b = 0; b < 10; b = b + 1) begin ref_bit(3); e10[b] = rb; end
        if (w10 !== (e10 ^ 10'h001)) begin errors = errors + 1; $display("inject %h %h", w10, e10); end
        g_step = 1; @(negedge clk); g_step = 0;
        for (b = 0; b < 10; b = b + 1) begin ref_bit(3); e10[b] = rb; end
        if (w10 !== e10) begin errors = errors + 1; $display("inject not single %h %h", w10, e10); end
        g_step = 1;
        // TX gearbox
        check_tx(1, 600); check_tx(2, 600); check_tx(3, 600);
        t_mode = 4; tx_reset; wait (t_ready); @(negedge clk); if (t_word !== 10'h155) begin errors = errors + 1; $display("tx clock %h", t_word); end
        t_mode = 6; tx_reset; wait (t_ready); @(negedge clk); t_req = 1; @(negedge clk); if (t_word !== 10'h2A5) begin errors = errors + 1; $display("tx user %h", t_word); end
        t_req = 0;
        t_mode = 3; tx_reset; r = {31{1'b1}}; @(negedge clk); t_inject = 1; @(negedge clk); t_inject = 0; wait (t_ready); @(negedge clk);
        for (k = 0; k < 6; k = k + 1) begin
            for (b = 0; b < 10; b = b + 1) begin ref_bit(3); e10[b] = rb; end
            if (t_word !== (k == 2 ? e10 ^ 10'h001 : e10)) begin errors = errors + 1; $display("tx inject word %0d %h %h", k, t_word, e10); end
            t_req = 1; @(negedge clk); t_req = 0;
        end
        // checker through the RX gearbox
        check_rx(3, 0, 1); check_rx(3, 7, 0); check_rx(2, 3, 1); check_rx(1, 5, 0); check_rx(1, 0, 1);
        // sustained errors above the drain rate (5 of every 10 words fully wrong, never 4
        // erroneous pairs in a row): lock holds, pend overflows, the count runs to saturation
        gap = 0; c_mode = 3; c_inv = 0; polarity = 0; c_en = 1; chk_clear; r = {31{1'b1}};
        line_words(3, 40);
        for (n = 0; n < 30; n = n + 1) begin wflips = 5; line_words(3, 10); end
        if (!c_lock || c_lost) begin errors = errors + 1; $display("overflow run lost lock"); end
        repeat (2600) @(negedge clk);
        if (t_err !== 10'h3ff || t_gray !== 10'h200 || c_err < 16'd1300 || !chk.chk.ovf) begin errors = errors + 1;
            $display("overflow: CW10 %0d gray %h, CW16 %0d ovf %b", t_err, t_gray, c_err, chk.chk.ovf); end
        else $display("pend overflow: CW=10 count saturated (gray %h), CW=16 count running to saturation (%0d)", t_gray, c_err);
        chk_clear; settle; if (c_err !== 0 || t_err !== 0 || chk.chk.ovf) begin errors = errors + 1; $display("clear after overflow"); end
        // single-clock clear pulses at both phases of the gated clock
        for (n = 0; n < 4; n = n + 1) begin
            line_words(3, 20); flips = 3; line_words(3, 20); settle;
            if (c_err !== 3) begin errors = errors + 1; $display("pre-clear count %0d", c_err); end
            repeat (n % 2 + (chk.t ? 1 : 0)) @(negedge clk); c_clear = 1; @(negedge clk); c_clear = 0; settle;   // phase n%2 of t
            if (c_err !== 0) begin errors = errors + 1; $display("single-clock clear (phase %0d) missed: %0d", n, c_err); end
        end
        c_en = 0; repeat (2) @(negedge clk); gap = 1;
        c_mode = 3; c_en = 1; c_inv = 0; chk_clear;
        for (k = 0; k < 100; k = k + 1) begin c_data = 0; @(negedge clk); c_valid = 1; @(negedge clk); c_valid = 0; end
        if (c_lock) begin errors = errors + 1; $display("locked to all-zero"); end
        for (k = 0; k < 100; k = k + 1) begin c_data = 10'h3ff; @(negedge clk); c_valid = 1; @(negedge clk); c_valid = 0; end
        if (c_lock) begin errors = errors + 1; $display("locked to all-one"); end
        c_mode = 4; for (k = 0; k < 20; k = k + 1) @(negedge clk);
        if (c_lock) begin errors = errors + 1; $display("non-PRBS mode locked"); end
        c_en = 0; c_valid = 0;
        loopback(1); loopback(2); loopback(3);
        // lockup guard: live PRBS31 -> PRBS7 change at an all-zero 7-bit history
        g_mode = 3; g_step = 1; gen_reset; n = 0;
        while (gen10.h[6:0] != 0 && n < 100000) begin @(posedge clk); n = n + 1; end
        #0.5 g_mode = 1; repeat (3) @(posedge clk); #0.5
        if (gen10.h[6:0] == 0) begin errors = errors + 1; $display("lockup guard: history stuck at zero"); end
        r = {24'd0, gen10.h[6:0]}; for (b = 0; b < 10; b = b + 1) begin ref_bit(1); e10[b] = rb; end
        @(posedge clk); #0.5 if (w10 !== e10) begin errors = errors + 1; $display("lockup guard: not a PRBS7 continuation"); end
        else $display("lockup guard: PRBS7 resumes after a zero history");
        if (gray_bad != 0) begin errors = errors + 1; $display("Gray monitor: %0d multi-bit/backward changes", gray_bad); end
        else $display("Gray monitor: %0d single-bit steps, 0 violations", gray_steps);
        if (errors == 0) $display("PATTERN_PASS"); else $display("PATTERN_FAIL %0d", errors);
        $finish;
    end
    initial begin #40000000; $display("PATTERN_FAIL timeout"); $finish; end
endmodule
