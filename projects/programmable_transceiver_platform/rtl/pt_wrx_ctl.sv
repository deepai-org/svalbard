// Wired-RX CDR control plane (rows MW-10, MW-11, MW-12, MW-35, D-CDRCTL), standard cells.
// Replaces analog/wired_rx/rtl/pt_wrx_cdr_loop.sv (retired pins freq_hold / bb_up / bb_dn / bb_gain)
// against the PUBLISHED pins bound in integration/top/pt_chip.conn:
//   pt_cdr.FUP/FDN            <- c_cdr_fup / c_cdr_fdn          (reference domain, level pulses)
//   pt_wrx_cap.PSEL[2:0]      <- c_wrx_cap_psel                 (wire_rx_clk domain)
//   pt_wrx_cap.SLIPP/SLIPM    <- c_wrx_cap_slipp / _slipm       (wire_rx_clk domain, slip TAGS)
//   pt_wrx_cap.DX/EW/WCLK40   -> wire_rx_data / wire_rx_edge / wire_rx_clk (r6 capture, D-CAP)
//   pt_wrx_cap.SLP/SLM        -> s_wrx_slp / s_wrx_slm ; pt_pll_ring(cdr).LOCK -> s_pll_cdr_lock
//
// 1. Frequency loop (reference domain). AC-3 pt_cdr has no hand-over: the ring PFD is held
//    (pfd_mode = 0) and FUP/FDN steer the integral node until the ring is inside the capture range
//    of the per-bit votes (interface-changes AC3-W1: |error| <= ~1000 ppm), then stop. The error
//    is the SIGNED result of frequency counter b (pt_freq_count, source cdr_ring_fbck): fc_diff
//    (r_diff, counts per window, + = ring fast) with a one-cycle strobe fc_upd per evaluated window.
//    pt_freq_count exports only the level locked_ref today, which has no sign: fc_diff / fc_upd are
//    two new reference-domain outputs it must provide. Per accepted window: |diff| <= cfg_fll_tol
//    twice in a row -> fll_done; otherwise one pulse of (|diff| << cfg_fll_shift) reference cycles
//    on FDN (ring fast) or FUP (ring slow); the window that contains a pulse is discarded.
//    After fll_done the loop is silent (the phase loop may sit thousands of ppm from the
//    reference: SSC, line offset) and only restarts when |diff| > cfg_fll_loss (0 = never).
//    Hand-over = freq_ok, selected by cfg_freq_src: 0 fll_done, 1 s_pll_cdr_lock (pfd_mode = 1,
//    ring on its own PFD), 2 fc_locked (the existing cdr_freq_locked level), 3 forced.
//    Manual: each change of cfg_fll_man_trig gives one pulse of (cfg_fll_man_len << cfg_fll_shift)
//    reference cycles on FUP (cfg_fll_man_dir = 1) or FDN, in every mode.
// 2. Phase picker (wire_rx_clk domain, full rate only: cfg_pick_auto). Early/late over the 20-bit
//    half of DX that EW belongs to (cfg_ew_half), accumulated over words; |acc| > cfg_pick_thr
//    steps PSEL by one phase (late -> PSEL - 1), then waits cfg_pick_hold words. The 3 -> 4 step is
//    tagged with SLIPP and 4 -> 3 with SLIPM (the capture only pipes these tags to SLP/SLM; the bit
//    duplicate / skip itself follows from the PSEL step). cfg_pick_auto = 0: PSEL = cfg_man_psel
//    and each change of cfg_man_slipp_trig / cfg_man_slipm_trig gives one tag pulse.
// 3. Word qualification. Everything in the wire_rx_clk domain is asynchronously reset from a
//    reference-domain flop (wrun) whenever the block is disabled, restarted (cfg_restart change)
//    or wire_rx_clk stops (no edge of wire_rx_clk/4 for 64 reference cycles), so wire_rx_valid
//    and PSEL fall without a word clock and every restart re-qualifies. There is no restart or
//    slip input on the published capture for quarter / half rate: alignment there is the
//    downstream comma aligner's. Signal detect (MW-35) is what the words allow: per word, the
//    number of positions where two equal neighbouring data bits disagree with the edge sample
//    between them (noise, wrong sampling phase, CDR slipping) and all-equal words (stuck slicer).
//    wire_rx_valid = freq_ok & 2^cfg_lock_exp consecutive good words, lost after 2^cfg_loss_exp
//    consecutive bad words (cfg_valid_mode 0), or freq_ok only (1), forced 1 (2), forced 0 (3).
//    An electrical-idle input that resolves to random data with clean edges cannot be told from
//    data here: that needs an amplitude detector on the HS pair (FR-3; none exists).
// Reset and cfg_en = 0: every output 0. Configuration inputs are static levels (SPI domain);
// single-bit modes and triggers are synchronized here, multi-bit values marked "static" in the
// port list must only change while cfg_en = 0 (or a transient wrong decision is accepted).
`default_nettype none
module pt_wrx_ctl (
    input  wire        ref_clk,
    input  wire        wire_rx_clk,          // WCLK40 from the capture, may stop
    input  wire        rst_n,
    // ---------------- configuration (static levels)
    input  wire        cfg_en,
    input  wire        cfg_restart,          // any change: restart FLL and word qualification
    input  wire [1:0]  cfg_freq_src,         // 0 FLL done, 1 s_pll_cdr_lock, 2 fc_locked, 3 forced
    input  wire        cfg_fll_auto,
    input  wire        cfg_fll_inv,          // swaps FUP/FDN of the automatic loop
    input  wire [2:0]  cfg_fll_shift,        // pulse length = counts << shift reference cycles
    input  wire [7:0]  cfg_fll_tol,          // counts
    input  wire [11:0] cfg_fll_loss,         // counts, 0 = never re-acquire
    input  wire        cfg_fll_man_trig,     // any change: one manual pulse
    input  wire        cfg_fll_man_dir,      // 1 FUP, 0 FDN
    input  wire [7:0]  cfg_fll_man_len,
    input  wire        cfg_pick_auto,
    input  wire        cfg_pick_inv,
    input  wire [5:0]  cfg_pick_thr,
    input  wire [3:0]  cfg_pick_hold,
    input  wire [2:0]  cfg_man_psel,
    input  wire        cfg_man_slipp_trig,   // any change: one SLIPP tag (manual picker only)
    input  wire        cfg_man_slipm_trig,
    input  wire        cfg_ew_half,          // EW belongs to DX[19:0] (0) or DX[39:20] (1)
    input  wire [4:0]  cfg_viol_thr,         // word is bad when violations > thr
    input  wire [3:0]  cfg_idle_words,       // all-equal words in a row -> idle; 0 = off
    input  wire [3:0]  cfg_lock_exp,
    input  wire [1:0]  cfg_loss_exp,
    input  wire [1:0]  cfg_valid_mode,
    // ---------------- frequency counter b (reference domain)
    input  wire        fc_upd,
    input  wire [13:0] fc_diff,
    input  wire        fc_locked,
    // ---------------- analog status (asynchronous)
    input  wire        s_pll_cdr_lock,
    input  wire        s_wrx_slp,
    input  wire        s_wrx_slm,
    // ---------------- capture words (wire_rx_clk domain)
    input  wire [39:0] wire_rx_data,
    input  wire [19:0] wire_rx_edge,
    // ---------------- controls to the analog blocks
    output reg         c_cdr_fup,            // reference domain
    output reg         c_cdr_fdn,
    output reg  [2:0]  c_wrx_cap_psel,       // wire_rx_clk domain
    output reg         c_wrx_cap_slipp,
    output reg         c_wrx_cap_slipm,
    output reg         wire_rx_valid,        // wire_rx_clk domain
    // ---------------- status, reference domain
    output reg  [2:0]  st_state,             // 0 off 1 manual 2 wait 3 pulse 4 settle 5 fll done
                                             // 6 freq_ok, words not qualified 7 locked
    output reg         st_fll_done,
    output reg         st_fll_lost,          // sticky until disable / restart
    output reg         st_freq_ok,
    output reg         st_wclk_alive,
    output reg  [13:0] st_fll_err,           // last accepted fc_diff
    output reg  [7:0]  st_fll_win,           // accepted windows, saturating
    // ---------------- status, wire_rx_clk domain (cleared when that domain is reset)
    output reg         st_sig_ok,
    output reg         st_idle,
    output reg  [4:0]  st_viol,              // violations in the last word
    output reg  [7:0]  st_pick_acc,          // early/late accumulator, two's complement
    output reg  [7:0]  st_slip_cnt,          // slip tags sent, wraps
    output reg         st_slp_seen,          // capture SLP / SLM seen at a wire_rx_clk edge
    output reg         st_slm_seen
);
    // =====================================================================================
    // reference domain
    // =====================================================================================
    reg [1:0] en_sy, pl_sy, lk_sy;
    reg [2:0] rs_sy, mt_sy, al_sy;
    reg [1:0] wdiv;                            // wire_rx_clk / 4, free running
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin
            en_sy <= 2'd0; pl_sy <= 2'd0; lk_sy <= 2'd0; rs_sy <= 3'd0; mt_sy <= 3'd0; al_sy <= 3'd0;
        end else begin
            en_sy <= {en_sy[0], cfg_en};
            pl_sy <= {pl_sy[0], s_pll_cdr_lock};
            lk_sy <= {lk_sy[0], wire_rx_valid};
            rs_sy <= {rs_sy[1:0], cfg_restart};
            mt_sy <= {mt_sy[1:0], cfg_fll_man_trig};
            al_sy <= {al_sy[1:0], wdiv[1]};
        end
    wire en_s     = en_sy[1];
    wire kick     = rs_sy[2] ^ rs_sy[1];
    wire man_edge = mt_sy[2] ^ mt_sy[1];
    wire w_edge   = al_sy[2] ^ al_sy[1];

    // word clock alive: two edges of wire_rx_clk/4 less than 64 reference cycles apart
    reg [5:0] acnt;
    reg       wrun;                            // asynchronous reset source of the word domain
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin acnt <= 6'd0; st_wclk_alive <= 1'b0; wrun <= 1'b0; end
        else begin
            if (w_edge) begin
                acnt <= 6'd63;
                if (acnt != 6'd0) st_wclk_alive <= 1'b1;
            end else if (acnt != 6'd0) acnt <= acnt - 6'd1;
            else st_wclk_alive <= 1'b0;
            wrun <= en_s && st_wclk_alive && !kick;
        end

    // ---------------- FLL
    localparam [2:0] F_OFF = 3'd0, F_IDLE = 3'd1, F_WAIT = 3'd2, F_PULSE = 3'd3, F_SETTLE = 3'd4,
                     F_DONE = 3'd5;
    reg [2:0]  fst;
    reg [15:0] pcnt;
    reg        good, man_pend;
    wire [12:0] mag = fc_diff == 14'h2000 ? 13'h1fff :
                      fc_diff[13] ? ~fc_diff[12:0] + 13'd1 : fc_diff[12:0];
    wire        in_tol   = mag <= {5'd0, cfg_fll_tol};
    wire        out_loss = cfg_fll_loss != 12'd0 && mag > {1'b0, cfg_fll_loss};
    wire [19:0] a_sh  = {7'd0, mag} << cfg_fll_shift;
    wire [15:0] a_len = |a_sh[19:16] ? 16'hffff : a_sh[15:0];
    wire [15:0] m_len = {8'd0, cfg_fll_man_len} << cfg_fll_shift;
    wire        a_up  = fc_diff[13] ^ cfg_fll_inv;          // ring slow -> FUP
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin
            fst <= F_OFF; pcnt <= 16'd0; good <= 1'b0; man_pend <= 1'b0;
            c_cdr_fup <= 1'b0; c_cdr_fdn <= 1'b0;
            st_fll_done <= 1'b0; st_fll_lost <= 1'b0; st_fll_err <= 14'd0; st_fll_win <= 8'd0;
        end else if (!en_s || kick) begin
            fst <= F_OFF; pcnt <= 16'd0; good <= 1'b0; man_pend <= 1'b0;
            c_cdr_fup <= 1'b0; c_cdr_fdn <= 1'b0;
            st_fll_done <= 1'b0; st_fll_lost <= 1'b0; st_fll_err <= 14'd0; st_fll_win <= 8'd0;
        end else begin
            case (fst)
                F_OFF: fst <= cfg_fll_auto ? F_SETTLE : F_IDLE;
                F_PULSE:
                    if (pcnt == 16'd0) begin
                        c_cdr_fup <= 1'b0; c_cdr_fdn <= 1'b0;
                        fst <= cfg_fll_auto ? F_SETTLE : F_IDLE;
                    end else pcnt <= pcnt - 16'd1;
                default:
                    if (man_pend) begin                     // manual pulse, any mode
                        man_pend <= 1'b0; st_fll_done <= 1'b0; good <= 1'b0;
                        if (m_len != 16'd0) begin
                            c_cdr_fup <= cfg_fll_man_dir; c_cdr_fdn <= !cfg_fll_man_dir;
                            pcnt <= m_len - 16'd1; fst <= F_PULSE;
                        end
                    end else if (!cfg_fll_auto) begin
                        fst <= F_IDLE; st_fll_done <= 1'b0; good <= 1'b0;
                    end else if (fst == F_IDLE) fst <= F_SETTLE;
                    else if (fc_upd) begin
                        if (fst == F_SETTLE) fst <= F_WAIT;  // window with a pulse or start-up
                        else begin
                            st_fll_err <= fc_diff;
                            if (st_fll_win != 8'hff) st_fll_win <= st_fll_win + 8'd1;
                            if (fst == F_DONE) begin
                                if (out_loss) begin
                                    st_fll_done <= 1'b0; st_fll_lost <= 1'b1; good <= 1'b0;
                                    fst <= F_WAIT;
                                end
                            end else if (in_tol) begin
                                good <= 1'b1;
                                if (good) begin st_fll_done <= 1'b1; fst <= F_DONE; end
                            end else begin
                                good <= 1'b0;
                                c_cdr_fup <= a_up; c_cdr_fdn <= !a_up;
                                pcnt <= a_len - 16'd1; fst <= F_PULSE;
                            end
                        end
                    end
            endcase
            if (man_edge) man_pend <= 1'b1;
        end

    // ---------------- hand-over level and state readback
    wire fsel = cfg_freq_src == 2'd0 ? st_fll_done :
                cfg_freq_src == 2'd1 ? pl_sy[1] :
                cfg_freq_src == 2'd2 ? fc_locked : 1'b1;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin st_freq_ok <= 1'b0; st_state <= 3'd0; end
        else begin
            st_freq_ok <= en_s && !kick && fsel;
            st_state   <= !en_s ? 3'd0 : lk_sy[1] ? 3'd7 : st_freq_ok ? 3'd6 : fst;
        end

    // =====================================================================================
    // word domain (wire_rx_clk)
    // =====================================================================================
    always @(posedge wire_rx_clk or negedge rst_n)
        if (!rst_n) wdiv <= 2'd0; else wdiv <= wdiv + 2'd1;
    reg [1:0] wrs;                             // reset release synchronizer
    always @(posedge wire_rx_clk or negedge wrun)
        if (!wrun) wrs <= 2'd0; else wrs <= {wrs[0], 1'b1};
    wire wrst_n = wrs[1];

    // early/late and violations of five positions: d[i], e[i], d[i+1]
    function automatic [6:0] grp(input [5:0] d, input [4:0] e);
        integer i; reg [3:0] el; reg [2:0] v;
        begin
            el = 4'd0; v = 3'd0;
            for (i = 0; i < 5; i = i + 1)
                if (d[i] != d[i + 1]) begin
                    if (e[i] == d[i + 1]) el = el + 4'd1;   // edge sample shows the new bit: late
                    else el = el - 4'd1;                    // early
                end else if (e[i] != d[i]) v = v + 3'd1;
            grp = {el, v};
        end
    endfunction

    // stage 0: input registers. The 21st data bit closes edge 19 (first half: DX[20]); for the
    // second half it is not in this word, so position 19 is neutralised by repeating DX[39] as the
    // closing data bit AND as the edge sample (no transition, no violation).
    wire [20:0] d_in = cfg_ew_half ? {wire_rx_data[39], wire_rx_data[39:20]} : wire_rx_data[20:0];
    wire [19:0] e_in = cfg_ew_half ? {wire_rx_data[39], wire_rx_edge[18:0]} : wire_rx_edge;
    reg [20:0] d1;
    reg [19:0] e1;
    reg        stk;
    reg [3:0]  pv;                             // pipeline / synchronizer flush after release
    wire       rdy = pv[3];
    // stage 1 / 2
    reg [3:0]  g_el0, g_el1, g_el2, g_el3;
    reg [2:0]  g_v0, g_v1, g_v2, g_v3;
    reg [5:0]  el_sum;                         // late - early, two's complement
    wire [6:0] g0 = grp(d1[5:0],   e1[4:0]);
    wire [6:0] g1 = grp(d1[10:5],  e1[9:5]);
    wire [6:0] g2 = grp(d1[15:10], e1[14:10]);
    wire [6:0] g3 = grp(d1[20:15], e1[19:15]);
    // configuration and status synchronizers
    reg [1:0]  pa_sy, fk_sy, sp_sy, sm_sy;
    reg [2:0]  tp_sy, tm_sy;
    reg [2:0]  ms1, ms2, ms3;
    reg [1:0]  vm1, vm2, vm3, vm_q;
    wire       man_p = rdy && (tp_sy[2] ^ tp_sy[1]);
    wire       man_m = rdy && (tm_sy[2] ^ tm_sy[1]);
    // picker
    reg [3:0]  hold;
    wire [5:0] el_x  = cfg_pick_inv ? ~el_sum + 6'd1 : el_sum;
    wire [7:0] acc_n = st_pick_acc + {{2{el_x[5]}}, el_x};
    wire [7:0] acc_m = ~acc_n + 8'd1;
    wire       step_dn = !acc_n[7] && acc_n[6:0] > {1'b0, cfg_pick_thr};   // late: sample earlier
    wire       step_up =  acc_n[7] && acc_m[6:0] > {1'b0, cfg_pick_thr};   // early: sample later
    // signal detect
    reg [3:0]  run;
    reg [15:0] gcnt;
    reg [2:0]  bcnt;
    wire       bad = st_viol > cfg_viol_thr || st_idle;
    wire [3:0] need_m1 = (4'd1 << cfg_loss_exp) - 4'd1;

    always @(posedge wire_rx_clk or negedge wrst_n)
        if (!wrst_n) begin
            d1 <= 21'd0; e1 <= 20'd0; stk <= 1'b0; pv <= 4'd0;
            g_el0 <= 4'd0; g_el1 <= 4'd0; g_el2 <= 4'd0; g_el3 <= 4'd0;
            g_v0 <= 3'd0; g_v1 <= 3'd0; g_v2 <= 3'd0; g_v3 <= 3'd0;
            el_sum <= 6'd0; st_viol <= 5'd0;
            pa_sy <= 2'd0; fk_sy <= 2'd0; sp_sy <= 2'd0; sm_sy <= 2'd0; tp_sy <= 3'd0; tm_sy <= 3'd0;
            ms1 <= 3'd0; ms2 <= 3'd0; ms3 <= 3'd0; vm1 <= 2'd0; vm2 <= 2'd0; vm3 <= 2'd0; vm_q <= 2'd0;
            hold <= 4'd0; st_pick_acc <= 8'd0;
            c_wrx_cap_psel <= 3'd0; c_wrx_cap_slipp <= 1'b0; c_wrx_cap_slipm <= 1'b0;
            st_slip_cnt <= 8'd0; st_slp_seen <= 1'b0; st_slm_seen <= 1'b0;
            run <= 4'd0; st_idle <= 1'b0; gcnt <= 16'd0; bcnt <= 3'd0; st_sig_ok <= 1'b0;
            wire_rx_valid <= 1'b0;
        end else begin
            pv <= {pv[2:0], 1'b1};
            // ---- stage 0
            d1  <= d_in;
            e1  <= e_in;
            stk <= wire_rx_data == 40'd0 || wire_rx_data == {40{1'b1}};
            // ---- stage 1: four groups of five positions
            g_el0 <= g0[6:3]; g_v0 <= g0[2:0];
            g_el1 <= g1[6:3]; g_v1 <= g1[2:0];
            g_el2 <= g2[6:3]; g_v2 <= g2[2:0];
            g_el3 <= g3[6:3]; g_v3 <= g3[2:0];
            // ---- stage 2: word totals
            el_sum  <= {{2{g_el0[3]}}, g_el0} + {{2{g_el1[3]}}, g_el1}
                     + {{2{g_el2[3]}}, g_el2} + {{2{g_el3[3]}}, g_el3};
            st_viol <= {2'd0, g_v0} + {2'd0, g_v1} + {2'd0, g_v2} + {2'd0, g_v3};
            // ---- synchronizers
            pa_sy <= {pa_sy[0], cfg_pick_auto};
            fk_sy <= {fk_sy[0], st_freq_ok};
            sp_sy <= {sp_sy[0], s_wrx_slp};
            sm_sy <= {sm_sy[0], s_wrx_slm};
            tp_sy <= {tp_sy[1:0], cfg_man_slipp_trig};
            tm_sy <= {tm_sy[1:0], cfg_man_slipm_trig};
            ms1 <= cfg_man_psel; ms2 <= ms1; ms3 <= ms2;
            vm1 <= cfg_valid_mode; vm2 <= vm1; vm3 <= vm2;
            if (vm2 == vm3) vm_q <= vm3;
            if (sp_sy[1]) st_slp_seen <= 1'b1;
            if (sm_sy[1]) st_slm_seen <= 1'b1;
            // ---- phase picker
            c_wrx_cap_slipp <= 1'b0;
            c_wrx_cap_slipm <= 1'b0;
            if (!rdy) begin
                hold <= 4'd0; st_pick_acc <= 8'd0;
            end else if (!pa_sy[1]) begin                   // manual
                hold <= 4'd0; st_pick_acc <= 8'd0;
                if (ms2 == ms3) c_wrx_cap_psel <= ms3;
                c_wrx_cap_slipp <= man_p;
                c_wrx_cap_slipm <= man_m && !man_p;
                if (man_p || man_m) st_slip_cnt <= st_slip_cnt + 8'd1;
            end else if (hold != 4'd0) begin
                hold <= hold - 4'd1; st_pick_acc <= 8'd0;
            end else if (step_dn) begin
                c_wrx_cap_psel  <= c_wrx_cap_psel - 3'd1;
                c_wrx_cap_slipm <= c_wrx_cap_psel == 3'd4;
                if (c_wrx_cap_psel == 3'd4) st_slip_cnt <= st_slip_cnt + 8'd1;
                hold <= cfg_pick_hold; st_pick_acc <= 8'd0;
            end else if (step_up) begin
                c_wrx_cap_psel  <= c_wrx_cap_psel + 3'd1;
                c_wrx_cap_slipp <= c_wrx_cap_psel == 3'd3;
                if (c_wrx_cap_psel == 3'd3) st_slip_cnt <= st_slip_cnt + 8'd1;
                hold <= cfg_pick_hold; st_pick_acc <= 8'd0;
            end else st_pick_acc <= acc_n;
            // ---- signal detect and word qualification
            if (!stk) run <= 4'd0; else if (run != 4'hf) run <= run + 4'd1;
            st_idle <= cfg_idle_words != 4'd0 && run >= cfg_idle_words;
            if (!rdy) begin
                gcnt <= 16'd0; bcnt <= 3'd0; st_sig_ok <= 1'b0;
            end else if (bad) begin
                gcnt <= 16'd0;
                if (st_sig_ok) begin
                    if ({1'b0, bcnt} >= need_m1) begin st_sig_ok <= 1'b0; bcnt <= 3'd0; end
                    else bcnt <= bcnt + 3'd1;
                end
            end else begin
                bcnt <= 3'd0;
                if (!st_sig_ok) begin
                    if (gcnt[cfg_lock_exp]) st_sig_ok <= 1'b1; else gcnt <= gcnt + 16'd1;
                end
            end
            wire_rx_valid <= rdy && (vm_q == 2'd0 ? st_sig_ok && fk_sy[1] :
                                     vm_q == 2'd1 ? fk_sy[1] : vm_q == 2'd2);
        end
endmodule
`default_nettype wire
