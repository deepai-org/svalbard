// Self-checking test of rtl/pt_clocktree_slow.sv (P2-10): /10 and /5 word
// divider, 64-cycle qualification (pass, lock loss, wrong ratio, unstable phase),
// deterministic launch at captured edge + launch_reference_count with exact
// 10*word + bit delay (both divider modes, several reference phases), arm
// refusal/abort, and the ceil(f/500 MHz) detector divider (period and duty).
`timescale 1ps/1ps
module tb_pt_clocktree_slow;
    integer errors = 0;
    // ---------------- clocks: TW = bit (or half-rate) period, reference = M*TW
    integer TW = 2000, M = 10, PHI = 700, ref_extra = 0, ref_jump = 0;
    reg wclk = 0, ref_clk = 0, run_ref = 0;
    always #(TW/2) wclk = ~wclk;
    integer ref_idx = 0; real t_ref [0:4095];
    initial begin : refgen
        forever begin
            if (!run_ref) begin ref_clk = 0; @(posedge run_ref); #(PHI); end
            ref_clk = 1; t_ref[ref_idx % 4096] = $realtime; ref_idx = ref_idx + 1;
            #(M*TW/2); ref_clk = 0; #(M*TW/2 + ref_extra + ((ref_idx % 29) == 0 ? ref_jump : 0));
        end
    end
    reg rst_n = 1, half = 0, lock = 0, marker = 0, arm = 0;
    reg [3:0] bitd = 0; reg [1:0] wordd = 0; reg [15:0] nref = 16;
    // detector clock
    integer TD = 400; reg dclk = 0; always #(TD/2) dclk = ~dclk;
    reg den = 0; reg [2:0] ddiv = 0; reg [21:0] rate = 1250000;
    wire word_clk, word_load, ser_run, bit_phase, qualified, armed, marker_seen, launched, arm_fault, det_clk;
    wire [2:0] det_div;
    pt_clocktree_slow dut(.rst_n(rst_n), .wclk(wclk), .cfg_half_rate(half), .cfg_bit_delay(bitd), .cfg_word_delay(wordd),
        .pll_lock(lock), .word_clk(word_clk), .word_load(word_load), .ser_run(ser_run), .bit_phase(bit_phase),
        .qualified(qualified), .ref_clk(ref_clk), .marker(marker), .cfg_sync_arm(arm), .cfg_ref_count(nref),
        .armed(armed), .marker_seen(marker_seen), .launched(launched), .arm_fault(arm_fault),
        .det_clk_in(dclk), .cfg_det_en(den), .cfg_det_div(ddiv), .cfg_rate_khz(rate), .det_div(det_div), .det_clk(det_clk));

    task fail(input [8*80-1:0] msg); begin errors = errors + 1; $display("FAIL %0s (t=%0t)", msg, $time); end endtask
    task restart; begin
        run_ref = 0; rst_n = 0; arm = 0; marker = 0; #(20*TW); rst_n = 1; #(3*TW); run_ref = 1; ref_idx = 0;
    end endtask

    // word divider period/duty over 12 words
    task check_divider; integer k, hi, lo, loads; begin
        hi = 0; lo = 0; loads = 0;
        @(posedge wclk); while (!word_load) @(posedge wclk);
        for (k = 0; k < 12*M; k = k + 1) begin
            @(posedge wclk); #1;
            if (word_load) loads = loads + 1;
            if (word_clk) hi = hi + 1; else lo = lo + 1;
        end
        if (loads != 12) fail("word_load count");
        if (hi != 12*(M == 10 ? 5 : 2)) begin fail("word_clk duty"); $display("  hi %0d lo %0d", hi, lo); end
    end endtask

    // qualification: returns reference edge index at which qualified rose (-1 if never in 100)
    integer qat;
    task wait_qual(input integer limit); integer start; begin
        qat = -1; start = ref_idx;
        while (qat < 0 && ref_idx - start < limit) begin @(posedge wclk); if (qualified) qat = ref_idx - start; end
    end endtask

    // launch: measure ser_run rise relative to reference edge E_c + N, in TW units
    integer ec, lat; real tl;
    task launch(input integer w, input integer b, input integer n); begin
        wordd = w; bitd = b; nref = n;
        @(negedge ref_clk); arm = 1; repeat (3) @(negedge ref_clk);
        if (!armed) fail("not armed");
        @(negedge ref_clk); marker = 1; ec = ref_idx;    // next reference edge (index ec) captures it
        wait (ser_run === 1'b1); tl = $realtime; #1 if (!word_load) fail("word zero not at ser_run");
        lat = (tl - t_ref[(ec + n) % 4096] + TW/2) / TW;  // rounded
        if (!launched || armed) fail("launched/armed status");
        marker = 0; arm = 0;
    end endtask

    integer k, l0, l0h, ph, i; reg [1:0] wv [0:5]; reg [3:0] bv [0:5]; integer nv [0:5];
    real t1, t2, t3;
    initial begin
        wv[0]=0; bv[0]=0; nv[0]=16;  wv[1]=0; bv[1]=1; nv[1]=4;  wv[2]=0; bv[2]=9; nv[2]=100;
        wv[3]=1; bv[3]=0; nv[3]=16;  wv[4]=2; bv[4]=7; nv[4]=5;  wv[5]=3; bv[5]=9; nv[5]=16;
        // ---- /10 divider and qualification
        half = 0; M = 10; lock = 1; restart;
        wait_qual(100);
        if (qat < 64 || qat > 67) begin fail("qualification time /10"); $display("  qualified after %0d reference edges", qat); end
        else $display("qualified after %0d reference edges (/10)", qat);
        check_divider;
        // TC6 timing pipeline: registered tz/ti decision (+1) and registered `qualified` (+1): 6 cycles (was 4)
        @(negedge wclk); lock = 0; repeat (6) @(posedge wclk); #1 if (qualified) fail("lock loss not seen within 6 cycles");
        lock = 1; wait_qual(100); if (qat < 64) fail("requalification");
        // arm refused while not qualified; abort when qualification drops while counting
        lock = 0; repeat (5) @(posedge wclk);
        @(negedge ref_clk); arm = 1; repeat (3) @(negedge ref_clk); if (armed) fail("armed while unqualified"); arm = 0;
        lock = 1; wait_qual(100);
        @(negedge ref_clk); arm = 1; repeat (3) @(negedge ref_clk); nref = 200; marker = 1; repeat (5) @(negedge ref_clk);
        lock = 0; repeat (8) @(negedge ref_clk); if (!arm_fault || ser_run || launched) fail("abort while counting");
        marker = 0; arm = 0; lock = 1;
        // ---- deterministic launch, several delays and reference phases
        for (ph = 0; ph < 3; ph = ph + 1) begin
            PHI = 300 + 600*ph; restart; wait_qual(100);
            for (i = 0; i < 6; i = i + 1) begin
                if (i > 0) begin rst_n = 0; #(5*TW); rst_n = 1; ref_idx = ref_idx; wait_qual(100); end
                launch(wv[i], bv[i], nv[i]);
                if (i == 0) l0 = lat;
                if (lat != l0 + 10*wv[i] + bv[i]) begin fail("launch latency"); $display("  phi %0d w %0d b %0d n %0d: %0d expected %0d", PHI, wv[i], bv[i], nv[i], lat, l0 + 10*wv[i] + bv[i]); end
                check_divider;
                if (!qualified) fail("qualification lost by launch re-phase");
            end
            if (l0 < 2 || l0 > 4) begin fail("absolute launch latency /10"); $display("  %0d", l0); end
            $display("/10 phase %0d ps: fixed launch latency %0d UI after edge E_c+N, delays 10w+b exact", PHI, l0);
        end
        // ---- wrong ratio and unstable phase never qualify
        PHI = 700; ref_extra = TW/2; restart; wait_qual(150); if (qat >= 0) fail("qualified with reference period 10.5 UI");
        ref_extra = 0; ref_jump = TW; restart; wait_qual(150); if (qat >= 0) fail("qualified with a phase jump every 29 edges");
        ref_jump = 0; M = 20; restart; wait_qual(150); if (qat >= 0) fail("qualified with reference period 20 UI"); M = 10;
        ref_jump = 0;
        // ---- /5 on the half-rate clock
        half = 1; M = 5; TW = 4000; restart;
        wait_qual(100);
        if (qat < 64 || qat > 67) begin fail("qualification time /5"); $display("  %0d", qat); end
        else $display("qualified after %0d reference edges (/5)", qat);
        check_divider;
        for (i = 0; i < 6; i = i + 1) begin
            if (i > 0) begin rst_n = 0; #(5*TW); rst_n = 1; wait_qual(100); end
            launch(wv[i], bv[i], nv[i]);
            if (i == 0) l0h = lat;
            if (lat != l0h + (10*wv[i] + bv[i]) / 2 || bit_phase !== bv[i][0]) begin
                fail("half-rate launch"); $display("  w %0d b %0d: %0d cycles, bit_phase %b", wv[i], bv[i], lat, bit_phase); end
            check_divider;
        end
        if (l0h < 2 || l0h > 4) begin fail("absolute launch latency /5"); $display("  %0d", l0h); end
        $display("/5 half-rate: fixed launch latency %0d cycles, (10w+b)/2 cycles + bit_phase exact", l0h);
        // ---- detector divider
        check_det(0, 480000, 1); check_det(0, 500000, 1); check_det(0, 500001, 2); check_det(0, 1000000, 2);
        check_det(0, 1250000, 3); check_det(0, 2000000, 4); check_det(0, 2000001, 5); check_det(0, 2500000, 5);
        check_det(3, 2500000, 3); check_det(7, 480000, 5);
        den = 0; repeat (6) @(posedge dclk); t1 = 0; for (k = 0; k < 20; k = k + 1) begin @(negedge dclk); if (det_clk) t1 = 1; end
        if (t1 != 0) fail("det_clk toggles while disabled");
        if (errors == 0) $display("CLOCKTREE_SLOW_PASS"); else $display("CLOCKTREE_SLOW_FAIL %0d", errors);
        $finish;
    end

    task check_det(input [2:0] d, input [21:0] r, input integer nexp); real per, hi; begin
        den = 0; ddiv = d; rate = r; repeat (6) @(posedge dclk); den = 1; repeat (12) @(posedge dclk);
        if (det_div != nexp) begin fail("detector N"); $display("  rate %0d div %0d: N %0d expected %0d", r, d, det_div, nexp); end
        @(posedge det_clk); t1 = $realtime; @(negedge det_clk); t2 = $realtime; @(posedge det_clk); t3 = $realtime;
        per = t3 - t1; hi = t2 - t1;
        if (per != nexp*TD || (nexp > 1 && hi != nexp*TD/2.0)) begin fail("detector period/duty"); $display("  N %0d period %0f high %0f", nexp, per, hi); end
        else $display("detector rate %0d kHz cfg %0d: N=%0d period %0.0f ps high %0.0f ps", r, d, nexp, per, hi);
    end endtask
    initial begin #400000000; $display("CLOCKTREE_SLOW_FAIL timeout"); $finish; end
endmodule
