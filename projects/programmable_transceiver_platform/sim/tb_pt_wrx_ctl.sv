// Self-checking bench for rtl/pt_wrx_ctl.sv (run by verification/check_wrx_ctl.py).
// Behavioural models (word rate only, no ring-rate events):
//   * ring: frequency error ring_ppm; FUP / FDN slew it by SLEW ppm per reference cycle.
//   * frequency counter b: FBCK = ring / 16 counted over FCWIN reference cycles, signed difference
//     to the target with a one-cycle strobe (the fc_diff / fc_upd inputs the DUT asks for).
//   * line: PRBS7 at line_ppm; line_mode 1 = noise (random samples), 2 = stuck low.
//   * capture: per wire_rx_clk cycle 40 data samples and 20 edge samples (half a UI later) of the
//     half EWH. A sample closer than ZONE UI to a bit boundary resolves at random to one of the two
//     neighbouring bits. Full rate: sampling phase from PSEL (0..3 = 0..+3/8 UI, 4..7 = -4/8..-1/8),
//     applied two words later, so 3 -> 4 repeats a bit and 4 -> 3 drops one. Quarter / half rate: a
//     bang-bang loop (the analog votes) moves phase and ring frequency every word; it holds about
//     +-2000 ppm, so it only locks after the FLL.
// Plusargs: +T=<mask> tests to run (bit n = test n), +STOP stop at the first error,
//           +EWH=<0|1> half of DX the edge word belongs to (model), +CEWH=<0|1> DUT cfg_ew_half.
`timescale 1ps/1ps
`default_nettype none
module tb_pt_wrx_ctl;
    localparam real SLEW = 35.0;       // ppm per reference cycle of FUP / FDN
    localparam real ZONE = 0.10;       // UI
    localparam real KPH  = 0.08;       // UI per word, bang-bang proportional
    localparam real KI   = 2.0;        // ppm per word, bang-bang integral
    localparam real FBR  = 0.78125;    // FBCK cycles per reference cycle (39.0625 / 50 MHz)

    reg ref_clk = 0, wclk = 0, rst_n = 0;
    always #10000 ref_clk = ~ref_clk;

    // ---------------- DUT
    reg        cfg_en, cfg_restart, cfg_fll_auto, cfg_fll_inv, cfg_fll_man_trig, cfg_fll_man_dir;
    reg [1:0]  cfg_freq_src, cfg_loss_exp, cfg_valid_mode;
    reg [2:0]  cfg_fll_shift, cfg_man_psel;
    reg [7:0]  cfg_fll_tol, cfg_fll_man_len;
    reg [11:0] cfg_fll_loss;
    reg        cfg_pick_auto, cfg_pick_inv, cfg_man_slipp_trig, cfg_man_slipm_trig, cfg_ew_half;
    reg [5:0]  cfg_pick_thr;
    reg [3:0]  cfg_pick_hold, cfg_idle_words, cfg_lock_exp;
    reg [4:0]  cfg_viol_thr;
    reg        fc_upd = 0, fc_locked = 0, s_pll_cdr_lock = 0, s_wrx_slp = 0, s_wrx_slm = 0;
    reg [13:0] fc_diff = 0;
    reg [39:0] wire_rx_data = 0;
    reg [19:0] wire_rx_edge = 0;
    wire       c_cdr_fup, c_cdr_fdn, c_wrx_cap_slipp, c_wrx_cap_slipm, wire_rx_valid;
    wire [2:0] c_wrx_cap_psel, st_state;
    wire       st_fll_done, st_fll_lost, st_freq_ok, st_wclk_alive, st_sig_ok, st_idle;
    wire       st_slp_seen, st_slm_seen;
    wire [13:0] st_fll_err;
    wire [7:0] st_fll_win, st_pick_acc, st_slip_cnt;
    wire [4:0] st_viol;
    pt_wrx_ctl dut (.ref_clk(ref_clk), .wire_rx_clk(wclk), .*);

    // ---------------- model state
    real    ring_ppm = 0.0, line_ppm = 0.0, base_f = 0.5;
    integer base_i = 0, line_mode = 0, seed = 1, fcwin = 4096;
    reg     wclk_run = 1, mode_full = 0, fc_run = 0, bb_en = 1;
    integer ewh = 0, cewh = 0;
    reg [126:0] prbs;
    integer errors = 0, stop = 0;
    // checker controls and counters
    reg     chk_valid = 1, expect_clean = 1, chk_pick = 0;
    integer clean_run = 0, fup_cyc = 0, fdn_cyc = 0, slipp_cyc = 0, slipm_cyc = 0, wraps = 0;
    reg     seen_pulse = 0, first_up = 0, valid_d = 0;
    reg [2:0] psel_d = 0, psel_q1 = 0, psel_q2 = 0;
    reg [7:0] slip_cnt_s = 0;
    reg     sp_q1 = 0, sp_q2 = 0, sm_q1 = 0, sm_q2 = 0;

    task fail(input [8*56:1] msg);
        begin
            errors = errors + 1;
            $display("ERROR t=%0t: %0s", $time, msg);
            if (stop) begin $display("FAIL errors=%0d", errors); $finish; end
        end
    endtask

    // ---------------- word clock (period follows the ring)
    real twclk;
    always begin
        if (wclk_run) begin
            twclk = 16000.0 * (1.0 - ring_ppm * 1e-6);
            wclk = 1; #(twclk / 2.0); wclk = 0; #(twclk / 2.0);
        end else begin wclk = 0; #1000; end
    end

    // ---------------- ring integral node and frequency counter (reference domain)
    real    fbph = 0.0;
    integer wcnt = 0, fb_cur = 0, fb_prev = 0, fb_d = 0;
    reg     primed = 0;
    always @(posedge ref_clk) begin
        if (c_cdr_fup) ring_ppm = ring_ppm + SLEW;
        if (c_cdr_fdn) ring_ppm = ring_ppm - SLEW;
        if (ring_ppm > 60000.0) ring_ppm = 60000.0;
        if (ring_ppm < -60000.0) ring_ppm = -60000.0;
        if (c_cdr_fup && c_cdr_fdn) fail("FUP and FDN both high");
        if (c_cdr_fup) fup_cyc = fup_cyc + 1;
        if (c_cdr_fdn) fdn_cyc = fdn_cyc + 1;
        if (!seen_pulse && (c_cdr_fup || c_cdr_fdn)) begin seen_pulse = 1; first_up = c_cdr_fup; end
        fc_upd <= 1'b0;
        if (!fc_run) begin wcnt = 0; fbph = 0.0; primed = 0; fc_locked <= 1'b0; end
        else begin
            fbph = fbph + FBR * (1.0 + ring_ppm * 1e-6);
            wcnt = wcnt + 1;
            if (wcnt >= fcwin) begin
                wcnt = 0;
                fb_cur = $rtoi($floor(fbph));
                if (primed) begin
                    fb_d = fb_cur - fb_prev - $rtoi(fcwin * FBR);
                    if (fb_d > 8191) fb_d = 8191;
                    if (fb_d < -8192) fb_d = -8192;
                    fc_diff <= fb_d[13:0];
                    fc_upd  <= 1'b1;
                    fc_locked <= fb_d >= -3 && fb_d <= 3;
                end
                fb_prev = fb_cur; primed = 1;
            end
        end
    end

    // ---------------- line and capture
    function lbit(input integer n);
        integer m;
        begin m = n % 127; if (m < 0) m = m + 127; lbit = prbs[m]; end
    endfunction
    task samp(input real tt, output reg v, output reg bad);
        integer n; real f;
        begin
            n = $rtoi($floor(tt)); f = tt - n; bad = 0;
            if (line_mode == 1) begin v = $random(seed); bad = 1; end
            else if (line_mode == 2) begin v = 0; bad = 1; end
            else if (f < ZONE) begin
                bad = 1; v = ($random(seed) & 1) ? lbit(base_i + n - 1) : lbit(base_i + n);
            end else if (f > 1.0 - ZONE) begin
                bad = 1; v = ($random(seed) & 1) ? lbit(base_i + n + 1) : lbit(base_i + n);
            end else v = lbit(base_i + n);
        end
    endtask

    reg [39:0] dx;
    reg [19:0] ew;
    reg        sv, sb, word_bad;
    real       delta, eff, ff, delta_q = 0.0;
    reg        fok_q = 0;
    integer    k, nn;
    always @(posedge wclk) begin
        // ---- checks on the DUT outputs as they are before this edge
        if (c_wrx_cap_slipp) slipp_cyc = slipp_cyc + 1;
        if (c_wrx_cap_slipm) slipm_cyc = slipm_cyc + 1;
        if (chk_pick) begin
            if (psel_d == 3'd3 && c_wrx_cap_psel == 3'd4) begin
                wraps = wraps + 1;
                if (!c_wrx_cap_slipp || c_wrx_cap_slipm) fail("3 -> 4 without SLIPP tag");
            end else if (psel_d == 3'd4 && c_wrx_cap_psel == 3'd3) begin
                wraps = wraps + 1;
                if (!c_wrx_cap_slipm || c_wrx_cap_slipp) fail("4 -> 3 without SLIPM tag");
            end else begin
                if (c_wrx_cap_slipp || c_wrx_cap_slipm) fail("slip tag without a wrap");
                if (c_wrx_cap_psel != psel_d && c_wrx_cap_psel != psel_d + 3'd1 &&
                    c_wrx_cap_psel != psel_d - 3'd1) fail("picker step larger than one phase");
            end
        end
        psel_d = c_wrx_cap_psel;
        slip_cnt_s = st_slip_cnt;                           // same instant as the wraps count
        // A rise seen here was clocked at the PREVIOUS word edge, so it is judged against the
        // frequency error and the frequency status of that edge (delta_q, fok_q), not against what
        // the test did to the ring afterwards (T8 kicks the ring right after valid rises).
        if (chk_valid && wire_rx_valid) begin
            if (!valid_d && clean_run < 32) fail("valid rose before 32 clean words");
            if (!valid_d && !mode_full && (delta_q > 2500e-6 || delta_q < -2500e-6))
                fail("valid rose with the ring off frequency");
            if (!valid_d && cfg_valid_mode == 2'd0 && !fok_q)
                fail("valid rose without freq_ok");
            if (expect_clean && word_bad) fail("bad word while valid");
        end
        valid_d = wire_rx_valid;
        delta = (line_ppm - ring_ppm) * 1e-6;
        delta_q = delta; fok_q = st_freq_ok;
        // ---- capture model: PSEL and the slip tags are taken two words later
        psel_q2 = psel_q1; psel_q1 = c_wrx_cap_psel;
        sp_q2 = sp_q1; sp_q1 = c_wrx_cap_slipp; sm_q2 = sm_q1; sm_q1 = c_wrx_cap_slipm;
        eff = !mode_full ? 0.0 : (psel_q2 < 4 ? psel_q2 : psel_q2 - 8.0) / 8.0;
        word_bad = 0;
        for (k = 0; k < 40; k = k + 1) begin
            samp(base_f + eff + k * (1.0 + delta), sv, sb);
            dx[k] = sv; if (sb) word_bad = 1;
        end
        for (k = 0; k < 20; k = k + 1) begin
            samp(base_f + eff + (ewh * 20 + k + 0.5) * (1.0 + delta), sv, sb);
            ew[k] = sv;
        end
        clean_run = word_bad ? 0 : clean_run + 1;
        base_f = base_f + 40.0 * (1.0 + delta);
        if (!mode_full && bb_en) begin
            ff = base_f - $floor(base_f);
            if (ff > 0.5) begin base_f = base_f - KPH; ring_ppm = ring_ppm + KI; end
            else begin base_f = base_f + KPH; ring_ppm = ring_ppm - KI; end
        end
        nn = $rtoi($floor(base_f));
        base_f = base_f - nn;
        base_i = (base_i + nn) % 127;
        wire_rx_data <= #1000 dx;
        wire_rx_edge <= #1000 ew;
        s_wrx_slp    <= #1000 sp_q2;
        s_wrx_slm    <= #1000 sm_q2;
    end

    // ---------------- helpers
    task cfg_zero;
        begin
            cfg_en = 0; cfg_restart = 0; cfg_freq_src = 0; cfg_fll_auto = 0; cfg_fll_inv = 0;
            cfg_fll_shift = 0; cfg_fll_tol = 0; cfg_fll_loss = 0; cfg_fll_man_trig = 0;
            cfg_fll_man_dir = 0; cfg_fll_man_len = 0; cfg_pick_auto = 0; cfg_pick_inv = 0;
            cfg_pick_thr = 0; cfg_pick_hold = 0; cfg_man_psel = 0; cfg_man_slipp_trig = 0;
            cfg_man_slipm_trig = 0; cfg_ew_half = cewh[0]; cfg_viol_thr = 0; cfg_idle_words = 0;
            cfg_lock_exp = 0; cfg_loss_exp = 0; cfg_valid_mode = 0;
        end
    endtask
    wire [63:0] all_out = {c_cdr_fup, c_cdr_fdn, c_wrx_cap_psel, c_wrx_cap_slipp, c_wrx_cap_slipm,
                           wire_rx_valid, st_state, st_fll_done, st_fll_lost, st_freq_ok,
                           st_wclk_alive, st_fll_err, st_fll_win, st_sig_ok, st_idle, st_viol,
                           st_pick_acc, st_slip_cnt, st_slp_seen, st_slm_seen};
    wire [7:0]  safe_out = {c_cdr_fup, c_cdr_fdn, c_wrx_cap_psel, c_wrx_cap_slipp, c_wrx_cap_slipm,
                            wire_rx_valid};
    task refs(input integer n); begin repeat (n) @(posedge ref_clk); #1; end endtask
    task words(input integer n); begin repeat (n) @(posedge wclk); #1; end endtask
    task new_case(input real rp, input real lp, input real ph, input reg full);
        begin
            rst_n = 0; cfg_zero; fc_run = 0; wclk_run = 1; line_mode = 0; bb_en = 1;
            chk_valid = 1; expect_clean = 1; chk_pick = 0; s_pll_cdr_lock = 0;
            ring_ppm = rp; line_ppm = lp; base_f = ph; mode_full = full; fcwin = 4096;
            refs(4);
            if (all_out !== 64'd0) fail("outputs not 0 in reset");
            #3000 rst_n = 1;
            refs(8);
            if (safe_out !== 8'd0) fail("control outputs not 0 after reset");
            ring_ppm = rp; base_f = ph; clean_run = 0; valid_d = 0;
            fup_cyc = 0; fdn_cyc = 0; slipp_cyc = 0; slipm_cyc = 0; wraps = 0; seen_pulse = 0;
        end
    endtask
    task cfg_auto;                                     // quarter / half rate with the FLL
        begin
            cfg_freq_src = 0; cfg_fll_auto = 1; cfg_fll_shift = 3; cfg_fll_tol = 3;
            cfg_viol_thr = 0; cfg_idle_words = 2; cfg_lock_exp = 10; cfg_loss_exp = 1;
            cfg_valid_mode = 0; fc_run = 1; cfg_en = 1;
        end
    endtask
    task wait_valid(input integer max_us, input reg want, output reg ok);
        integer n;
        begin
            n = 0;
            while (wire_rx_valid !== want && n < max_us * 50) begin @(posedge ref_clk); n = n + 1; end
            ok = wire_rx_valid === want;
        end
    endtask
    real rerr;
    task check_locked(input [8*24:1] name);
        begin
            refs(5000);                                // 100 us of steady state
            rerr = ring_ppm - line_ppm; if (rerr < 0) rerr = -rerr;
            $display("  %0s: ring %0.0f ppm, line %0.0f ppm, fup %0d fdn %0d cycles, windows %0d",
                     name, ring_ppm, line_ppm, fup_cyc, fdn_cyc, st_fll_win);
            if (!wire_rx_valid) fail("valid not held");
            if (rerr > 300.0) fail("ring not on the line frequency");
            if (st_state !== 3'd7) fail("st_state not 7 when locked");
            if (!st_freq_ok || !st_wclk_alive || !st_sig_ok) fail("status flags when locked");
        end
    endtask

    // ---------------- tests
    reg ok;
    integer i, tmask, c0, c1;
    initial begin
        // PRBS7 x^7 + x^6 + 1
        begin : mk
            reg [6:0] l; l = 7'h5a;
            for (i = 0; i < 127; i = i + 1) begin prbs[i] = l[6]; l = {l[5:0], l[6] ^ l[5]}; end
        end
        tmask = 32'hffff;
        if ($value$plusargs("T=%d", tmask)) ;
        if ($test$plusargs("STOP")) stop = 1;
        if ($value$plusargs("EWH=%d", ewh)) ;
        if ($value$plusargs("CEWH=%d", cewh)) ;
        cfg_zero;

        // ---- T0: reset values; disabled block ignores every input
        if (tmask[0]) begin
            $display("T0 reset / disabled");
            new_case(20000.0, 0.0, 0.0, 0);
            fcwin = 64; fc_run = 1; s_pll_cdr_lock = 1;
            cfg_fll_auto = 1; cfg_pick_auto = 1; cfg_freq_src = 3; cfg_valid_mode = 2;
            cfg_man_psel = 3'd5; cfg_fll_man_len = 8'd9;
            for (i = 0; i < 400; i = i + 1) begin
                refs(1);
                if (i == 100) cfg_fll_man_trig = 1;
                if (i == 200) cfg_man_slipp_trig = 1;
                if (safe_out !== 8'd0) fail("control output moved while cfg_en = 0");
            end
            if (st_state !== 3'd0 || st_freq_ok) fail("state not off while cfg_en = 0");
        end

        // ---- T1: manual mode
        if (tmask[1]) begin
            $display("T1 manual");
            new_case(0.0, 0.0, 0.5, 1); chk_valid = 0;
            cfg_freq_src = 3; cfg_valid_mode = 2; cfg_en = 1;
            refs(40);
            if (!wire_rx_valid || c_wrx_cap_psel !== 3'd0) fail("forced valid / psel 0");
            if (st_state !== 3'd7) fail("st_state with forced valid");
            cfg_man_psel = 3'd5; words(8);
            if (c_wrx_cap_psel !== 3'd5) fail("manual psel 5");
            cfg_man_psel = 3'd2; words(8);
            if (c_wrx_cap_psel !== 3'd2) fail("manual psel 2");
            if (slipp_cyc != 0 || slipm_cyc != 0 || st_slip_cnt !== 8'd0) fail("slip without trigger");
            cfg_man_slipp_trig = 1; words(10);
            if (slipp_cyc != 1 || slipm_cyc != 0 || st_slip_cnt !== 8'd1) fail("manual SLIPP pulse");
            if (!st_slp_seen || st_slm_seen) fail("SLP status");
            cfg_man_slipm_trig = 1; words(10);
            cfg_man_slipm_trig = 0; words(10);
            if (slipp_cyc != 1 || slipm_cyc != 2 || st_slip_cnt !== 8'd3) fail("manual SLIPM pulses");
            if (!st_slm_seen) fail("SLM status");
            cfg_valid_mode = 3; words(8);
            if (wire_rx_valid) fail("valid mode 3");
            cfg_valid_mode = 1; words(8);
            if (!wire_rx_valid) fail("valid mode 1");
            cfg_fll_shift = 2; cfg_fll_man_len = 5; cfg_fll_man_dir = 1;
            cfg_fll_man_trig = 1; refs(60);
            if (fup_cyc != 20 || fdn_cyc != 0) fail("manual FUP pulse length");
            cfg_fll_man_dir = 0; cfg_fll_man_trig = 0; refs(60);
            if (fup_cyc != 20 || fdn_cyc != 20) fail("manual FDN pulse length");
            cfg_fll_man_len = 0; cfg_fll_man_trig = 1; refs(60);
            if (fup_cyc != 20 || fdn_cyc != 20) fail("manual pulse of length 0");
            if (ring_ppm > 1.0 || ring_ppm < -1.0) fail("FUP / FDN not balanced in the model");
            cfg_en = 0; refs(6);
            if (safe_out !== 8'd0) fail("outputs not 0 after disable");
        end

        // ---- T2..T4: FLL acquisition then phase lock, three start conditions
        if (tmask[2]) begin
            $display("T2 acquire from +8000 ppm");
            new_case(8000.0, 0.0, 0.1, 0); cfg_auto;
            wait_valid(4000, 1, ok);
            if (!ok) fail("no lock from +8000 ppm");
            if (!seen_pulse || first_up) fail("first pulse must be FDN");
            if (!st_fll_done) fail("valid without fll_done");
            check_locked("T2");
        end
        if (tmask[3]) begin
            $display("T3 acquire from -12000 ppm, line +300 ppm");
            new_case(-12000.0, 300.0, 0.7, 0); cfg_auto;
            wait_valid(4000, 1, ok);
            if (!ok) fail("no lock from -12000 ppm");
            if (!seen_pulse || !first_up) fail("first pulse must be FUP");
            check_locked("T3");
        end
        if (tmask[4]) begin
            $display("T4 start on frequency");
            new_case(0.0, 0.0, 0.5, 0); cfg_auto;
            wait_valid(2000, 1, ok);
            if (!ok) fail("no lock from 0 ppm");
            check_locked("T4");
            if (fup_cyc != 0 || fdn_cyc != 0) fail("FLL pulsed although on frequency");
        end

        // ---- T5: full rate, phase picker from four start phases, both drift directions
        if (tmask[5]) begin
            for (i = 0; i < 4; i = i + 1) begin
                $display("T5.%0d full rate picker", i);
                new_case(0.0, i[0] ? -100.0 : 100.0, i == 0 ? 0.0 : i == 1 ? 0.3 : i == 2 ? 0.6 : 0.95, 1);
                cfg_freq_src = 1; s_pll_cdr_lock = 1; cfg_pick_auto = 1; cfg_pick_thr = 24;
                cfg_pick_hold = 4; cfg_lock_exp = 6; cfg_loss_exp = 1; chk_pick = 1; cfg_en = 1;
                wait_valid(1000, 1, ok);
                if (!ok) fail("picker: no valid");
                words(8000);
                $display("  psel %0d, wraps %0d, slip count %0d, slp %0d slm %0d", c_wrx_cap_psel,
                         wraps, st_slip_cnt, st_slp_seen, st_slm_seen);
                if (!wire_rx_valid) fail("picker: valid not held");
                if (wraps < 10) fail("picker did not follow the drift");
                if (slip_cnt_s !== wraps[7:0]) fail("slip count differs from the wraps");
                if (i[0] ? !st_slp_seen : !st_slm_seen) fail("capture slip flag not seen");
                if (fup_cyc != 0 || fdn_cyc != 0) fail("FLL pulse in pll-lock mode");
            end
        end

        // ---- T6: loss of signal (noise, stuck) and return
        if (tmask[6]) begin
            $display("T6 signal loss");
            new_case(0.0, 0.0, 0.5, 0);
            cfg_freq_src = 3; cfg_idle_words = 2; cfg_lock_exp = 6; cfg_loss_exp = 1; cfg_en = 1;
            wait_valid(200, 1, ok);
            if (!ok) fail("no valid before the loss test");
            expect_clean = 0; line_mode = 1; words(16);
            if (wire_rx_valid || st_sig_ok) fail("valid held on noise");
            words(300);
            if (wire_rx_valid) fail("valid returned on noise");
            line_mode = 0; wait_valid(200, 1, ok);
            if (!ok) fail("no valid after noise");
            line_mode = 2; words(16);
            if (wire_rx_valid || !st_idle) fail("valid held on a stuck line");
            line_mode = 0; wait_valid(200, 1, ok);
            if (!ok || st_idle) fail("no valid after idle");
        end

        // ---- T7: word clock stops and restarts
        if (tmask[7]) begin
            $display("T7 word clock stop");
            new_case(0.0, 0.0, 0.5, 1);
            cfg_freq_src = 3; cfg_man_psel = 3'd6; cfg_lock_exp = 4; cfg_en = 1;
            wait_valid(200, 1, ok);
            if (!ok || c_wrx_cap_psel !== 3'd6) fail("no valid before the clock stop");
            @(negedge wclk); wclk_run = 0;
            refs(80);
            if (wire_rx_valid || c_wrx_cap_psel !== 3'd0) fail("outputs held without a word clock");
            if (st_wclk_alive || st_state === 3'd7) fail("status held without a word clock");
            wclk_run = 1; wait_valid(200, 1, ok);
            if (!ok || c_wrx_cap_psel !== 3'd6) fail("no valid after the clock restart");
        end

        // ---- T8: frequency loss -> re-acquire; restart request
        if (tmask[8]) begin
            $display("T8 re-acquire / restart");
            new_case(0.0, 0.0, 0.5, 0); cfg_fll_loss = 12'd40; cfg_auto;
            wait_valid(2000, 1, ok);
            if (!ok) fail("no lock before the kick");
            expect_clean = 0; ring_ppm = ring_ppm + 20000.0;
            wait_valid(100, 0, ok);
            if (!ok) fail("valid held after a 20000 ppm kick");
            i = 0;
            while (!st_fll_lost && i < 20000) begin refs(1); i = i + 1; end
            if (!st_fll_lost || wire_rx_valid) fail("frequency loss not flagged");
            expect_clean = 1;
            wait_valid(4000, 1, ok);
            if (!ok) fail("no re-acquisition after the kick");
            check_locked("T8 kick");
            c0 = fup_cyc + fdn_cyc;
            cfg_restart = 1; refs(8);
            if (wire_rx_valid || st_fll_done || st_fll_lost) fail("restart did not clear");
            wait_valid(2000, 1, ok);
            if (!ok) fail("no lock after restart");
            check_locked("T8 restart");
        end

        // ---- T9: manual mode with the automatic loops off while everything else is live: frequency
        //      counter reporting a large error, line drifting through the sampling phases
        if (tmask[9]) begin
            $display("T9 manual, automatic loops off");
            new_case(15000.0, 200.0, 0.5, 1); chk_valid = 0;
            fcwin = 1024; fc_run = 1; cfg_fll_shift = 3; cfg_fll_tol = 3; cfg_fll_loss = 12'd40;
            cfg_pick_thr = 4; cfg_man_psel = 3'd3; cfg_freq_src = 0; cfg_en = 1;
            refs(6000); words(8);                           // five windows of +12 counts
            if (fup_cyc != 0 || fdn_cyc != 0) fail("FLL pulsed with cfg_fll_auto = 0");
            if (c_wrx_cap_psel !== 3'd3 || slipp_cyc != 0 || slipm_cyc != 0 || st_slip_cnt !== 8'd0)
                fail("picker moved with cfg_pick_auto = 0");
            if (st_pick_acc !== 8'd0) fail("picker accumulator runs in manual mode");
            if (st_fll_done || st_freq_ok || wire_rx_valid || st_state !== 3'd1)
                fail("manual mode: fll_done / freq_ok / valid / state");
            cfg_man_psel = 3'd4; words(8);                  // forced 3 -> 4: no automatic tag
            if (c_wrx_cap_psel !== 3'd4 || slipp_cyc != 0) fail("forced psel 4 / automatic tag");
            cfg_man_slipm_trig = 1; words(8);
            if (slipm_cyc != 1 || slipp_cyc != 0) fail("manual SLIPM pulse (T9)");
            cfg_fll_shift = 0; cfg_fll_man_len = 8'd200; cfg_fll_man_dir = 0;
            cfg_fll_man_trig = 1; refs(260);
            if (fdn_cyc != 200 || fup_cyc != 0) fail("manual FDN pulse (T9)");
            if (ring_ppm > 15000.0 - 200 * SLEW + 1.0 || ring_ppm < 15000.0 - 200 * SLEW - 1.0)
                fail("ring did not follow the manual pulse");
            refs(1000);
            if (fdn_cyc != 200 || fup_cyc != 0) fail("FLL pulsed after the manual pulse");
            cfg_freq_src = 3; cfg_valid_mode = 1; refs(40);  // forced hand-over level
            if (!wire_rx_valid || st_state !== 3'd7) fail("forced freq_ok in manual mode");
        end

        if (errors == 0) $display("PASS"); else $display("FAIL errors=%0d", errors);
        $finish;
    end
endmodule
`default_nettype wire
