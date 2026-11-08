// Closed-loop behavioural test of pt_wrx_cdr_loop (word domain) with models of the analog loop and
// of the pt_wrx_cap capture block:
//   * RX ring VCO: f = F_LOCK + KVCO*(vctrl - VC_LOCK); 8 phases at k/8 of the period.
//     freq_hold=0: ring = F_LOCK (ideal reference lock).  The hand-over may add HOLD_STEP_PPM.
//   * pt_pll_ring loop filter: C2 on VCTRL, R + C1 to ground; pt_cdr bang-bang pump +/-IBB (x2 with
//     bb_gain) plus ILEAK, integrated once per ring cycle.
//   * Slicer: ideal sampler at each phase edge.
//   * pt_wrx_cap: per ring cycle the mode's data/edge samples are appended to the word being built
//     (full rate: phase psel_q / psel_q+4, psel_q = the loop's psel latched when the word starts,
//     together with the slip flags, which come back with that word); a word every 20 bits, then
//     word_clk rises.
//   * Line: PRBS7 at UI*(1+ppm(t)), ppm(t) = PPM + SSC triangle 0..SSC_PPM at SSC_HZ.
// The recovered stream rx_word is PRBS-checked after CHECK_FROM_UI (or 10000 UI after fll_done):
// a word flagged slip +1 drops its first bit; slip -1 re-synchronises the checker (one bit missing).
`timescale 1ps/1fs
module tb_pt_wrx_cdr_loop;
    parameter integer BPC   = 4;          // bits per ring cycle: 1, 2, 4
    parameter real UI_PS    = 400.0;
    parameter real PPM      = 0.0;
    parameter real SSC_PPM  = 0.0;
    parameter real SSC_HZ   = 31.5e3;
    parameter integer NUI   = 60000;
    parameter integer CHECK_FROM_UI = 30000;
    parameter real KVCO     = 0.64e9;     // Hz/V (extracted pll_ring + pt_cdr)
    parameter real VC_LOCK  = 1.15;
    parameter real R_F      = 20.0e3;
    parameter real C1_F     = 9.0e-12;
    parameter real C2_F     = 1.0e-12;
    parameter real IBB      = 50.0e-9;
    parameter real ILEAK    = 0.0;
    parameter integer ACQ_WORDS = 64;
    parameter real PHASE0   = 0.37;
    parameter integer BB_INVERT = 0;
    parameter real HOLD_STEP_PPM = 0.0;
    parameter integer FLL_EN = 0;
    parameter integer FLL_WIN = 7;
    parameter integer FLL_SHIFT = 4;
    parameter integer FLL_TOL = 1;
    parameter integer FLL_BOOST = 0;      // 1 hurt half rate (behavioural), see README
    parameter integer PICK_HYST = 2;

    real F_LOCK; initial F_LOCK = 1.0e12 / (UI_PS * BPC);

    reg rst_n = 0, cfg_en = 0, word_clk = 0;
    reg [19:0] dw = 0, ew = 0;
    reg cs_p = 0, cs_m = 0;
    wire freq_hold, bb_up, bb_dn, bb_gain, fll_done, slip_p, slip_m, rx_slip_p, rx_slip_m, rx_valid;
    wire [15:0] fll_err; wire [2:0] psel; wire [19:0] rx_word; wire [7:0] early_count, late_count;
    reg ref_clk = 0;
    always #(UI_PS * BPC * 8.0) ref_clk = ~ref_clk;
    pt_wrx_cdr_loop dut(.word_clk(word_clk), .rst_n(rst_n), .data_word(dw), .edge_word(ew), .cap_slip_p(cs_p),
        .cap_slip_m(cs_m), .cfg_en(cfg_en), .cfg_raw(1'b0),
        .cfg_bits_per_cycle(BPC == 4 ? 2'd2 : BPC == 2 ? 2'd1 : 2'd0), .cfg_acq_words(ACQ_WORDS[15:0]),
        .cfg_bb_invert(BB_INVERT[0]), .cfg_pick_hyst(PICK_HYST[3:0]), .ref_clk(ref_clk), .cfg_fll_en(FLL_EN[0]),
        .cfg_fll_win(FLL_WIN[3:0]), .cfg_fll_shift(FLL_SHIFT[2:0]), .cfg_fll_tol(FLL_TOL[7:0]), .cfg_bb_gain(1'b0),
        .cfg_fll_boost(FLL_BOOST[0]), .freq_hold(freq_hold), .bb_up(bb_up), .bb_dn(bb_dn), .bb_gain(bb_gain),
        .fll_done(fll_done), .fll_err(fll_err), .psel(psel), .slip_p(slip_p), .slip_m(slip_m), .rx_word(rx_word),
        .rx_slip_p(rx_slip_p), .rx_slip_m(rx_slip_m), .rx_valid(rx_valid), .early_count(early_count),
        .late_count(late_count));

    // PRBS7 line
    reg [6:0] lfsr = 7'h5A;
    reg line_bits [0:NUI+256];
    integer i;
    initial for (i = 0; i <= NUI + 256; i = i + 1) begin
        line_bits[i] = lfsr[6];
        lfsr = {lfsr[5:0], lfsr[6] ^ lfsr[5]};
    end
    real lt = 0.0, lphase = 0.0;
    function real ppm_at(input real t_ps);
        real x;
        begin
            if (SSC_PPM == 0.0) ppm_at = PPM;
            else begin
                x = t_ps * 1e-12 * SSC_HZ; x = x - $floor(x);
                ppm_at = PPM + SSC_PPM * (x < 0.5 ? 2.0 * x : 2.0 - 2.0 * x);
            end
        end
    endfunction
    function reg line_at(input real t_ps);
        integer kk;
        begin
            if (t_ps > lt) begin
                lphase = lphase + (t_ps - lt) / UI_PS * (1.0 + ppm_at(t_ps) * 1e-6);
                lt = t_ps;
            end
            kk = $rtoi(lphase + PHASE0 + (t_ps - lt) / UI_PS);
            line_at = (kk < 0) ? 1'b0 : line_bits[kk];
        end
    endfunction

    // analog loop + capture model, one ring cycle per iteration
    real vc, v1, f, tr, ic, h, tc;
    integer sub, j, fill;
    reg [7:0] smp, smp_prev;
    reg [19:0] wd, we;
    reg [2:0] psel_q;
    reg sp_q, sm_q;
    integer t_fll_done = -1;
    initial begin vc = VC_LOCK; v1 = VC_LOCK; fill = 0; psel_q = 0; sp_q = 0; sm_q = 0; end
    always begin
        f = freq_hold ? F_LOCK + KVCO * (vc - VC_LOCK) : F_LOCK;
        if (!freq_hold) begin
            vc = VC_LOCK + HOLD_STEP_PPM * 1e-6 * F_LOCK / KVCO; v1 = vc;
        end
        tr = 1.0e12 / f;
        tc = $realtime;
        smp_prev = smp;
        for (j = 0; j < 8; j = j + 1) smp[j] = line_at(tc + j * tr / 8.0);
        if (fill == 0) begin psel_q = psel; sp_q = slip_p; sm_q = slip_m; end   // shadow at word start
        case (BPC)
            4: begin
                for (j = 0; j < 4; j = j + 1) begin wd[fill + j] = smp[2 * j]; we[fill + j] = smp[2 * j + 1]; end
                fill = fill + 4;
            end
            2: begin
                wd[fill] = smp[0]; wd[fill + 1] = smp[4]; we[fill] = smp[2]; we[fill + 1] = smp[6];
                fill = fill + 2;
            end
            default: begin
                // pt_wrx_cap: data from phase psel of this cycle (psel 0..3) or of the previous cycle
                // (4..7); edge = half a UI after the data
                wd[fill] = (psel_q < 4) ? smp[psel_q] : smp_prev[psel_q]; we[fill] = smp[(psel_q + 4) % 8];
                fill = fill + 1;
            end
        endcase
        #(tr / 2.0);
        if (fill == 20) begin
            dw = wd; ew = we; cs_p = sp_q; cs_m = sm_q; fill = 0;
            word_clk = 1;
        end
        #(tr / 2.0);
        word_clk = 0;
        if (freq_hold) begin
            ic = ((bb_up ? IBB : 0.0) - (bb_dn ? IBB : 0.0)) * (bb_gain ? 2.0 : 1.0) + ILEAK;
            h = tr * 1e-12 / 4.0;
            for (sub = 0; sub < 4; sub = sub + 1) begin
                vc = vc + h * (ic - (vc - v1) / R_F) / C2_F;
                v1 = v1 + h * ((vc - v1) / R_F) / C1_F;
            end
        end
    end
    always @(posedge fll_done) t_fll_done = $rtoi($realtime / UI_PS);

    // checker: checking starts at CHECK_FROM_UI, or 10000 UI after fll_done if later
    reg [6:0] hist = 0; integer nbits = 0, nerr = 0, k2, first_err_ui = -1, nslip_p = 0, nslip_m = 0, resync = 0;
    reg start_ok = 0, checking = 0;
    initial #(CHECK_FROM_UI * UI_PS) start_ok = 1;
    real fmax_err = 0.0, ferr;
    always @(posedge word_clk) #1 if (rx_valid) begin
        if (!checking && start_ok && (!FLL_EN || BPC == 1 || (fll_done && $realtime > (t_fll_done + 10000) * UI_PS))) begin
            checking = 1; nerr = 0; nbits = 0; resync = 7;
        end
        if (rx_slip_p) nslip_p = nslip_p + 1;
        if (rx_slip_m) begin nslip_m = nslip_m + 1; resync = 7; end
        for (k2 = (rx_slip_p ? 1 : 0); k2 < 20; k2 = k2 + 1) begin
            if (checking && resync == 0 && rx_word[k2] !== (hist[6] ^ hist[5])) begin
                nerr = nerr + 1; if (first_err_ui < 0) first_err_ui = $rtoi($realtime / UI_PS);
            end
            if (resync > 0) resync = resync - 1;
            hist = {hist[5:0], rx_word[k2]};
            nbits = nbits + 1;
        end
        if (checking) begin
            ferr = (1.0e12 / UI_PS / BPC) * (1.0 + ppm_at($realtime) * 1e-6);
            ferr = (freq_hold ? F_LOCK + KVCO * (vc - VC_LOCK) : F_LOCK) / ferr - 1.0;
            if (ferr < 0) ferr = -ferr;
            if (BPC != 1 && ferr > fmax_err) fmax_err = ferr;
        end
    end

    initial begin
        #(200 * UI_PS) rst_n = 1;      // spans several reference cycles (reference-domain reset)
        #(20 * UI_PS) cfg_en = 1;
        #((NUI - 300) * UI_PS);
        $display("RESULT bpc=%0d ui_ps=%0.1f ppm=%0.1f ssc_ppm=%0.1f kvco=%0.3g hold_step_ppm=%0.0f ileak_nA=%0.1f fll_en=%0d fll_done_ui=%0d fll_err_words=%0d bits_checked=%0d errors=%0d first_err_ui=%0d slips_p=%0d slips_m=%0d hold=%0d vctrl=%0.4f max_freq_err_ppm=%0.1f psel=%0d",
                 BPC, UI_PS, PPM, SSC_PPM, KVCO, HOLD_STEP_PPM, ILEAK * 1e9, FLL_EN, t_fll_done, $signed(fll_err),
                 checking ? nbits : 0, nerr, first_err_ui, nslip_p, nslip_m, freq_hold, vc, fmax_err * 1e6, psel);
        if (checking && nerr == 0 && nbits > 1000) $display("PASS"); else $display("FAIL");
        $finish;
    end
endmodule
