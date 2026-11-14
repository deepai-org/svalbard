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
//    (Registered evaluation: the pulse starts 9 reference cycles after fc_upd.)
//    After fll_done the loop is silent (the phase loop may sit thousands of ppm from the
//    reference: SSC, line offset) and only restarts when |diff| > cfg_fll_loss (0 = never).
//    Hand-over = freq_ok, selected by cfg_freq_src: 0 fll_done, 1 s_pll_cdr_lock (pfd_mode = 1,
//    ring on its own PFD), 2 fc_locked (the existing cdr_freq_locked level), 3 forced.
//    Manual: each change of cfg_fll_man_trig gives one pulse of (cfg_fll_man_len << cfg_fll_shift)
//    reference cycles on FUP (cfg_fll_man_dir = 1) or FDN, in every mode.
// 2. Phase picker (wire_rx_clk domain, full rate only: cfg_pick_auto). Early/late over the 20-bit
//    half of DX that EW belongs to (cfg_ew_half), accumulated over words; |acc| > cfg_pick_thr
//    steps PSEL by one phase (late -> PSEL - 1), then waits cfg_pick_hold + 3 words (3 = the extra
//    pipeline words between the capture and the accumulator, see PICK_FLUSH). The 3 -> 4 step is
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
    // Timing structure (slow cells: about 1 ns per logic level, ref_clk 10 ns, wire_rx_clk 12.3 ns).
    // Every flop sees a small cone; wide arithmetic is cut into registered pieces:
    //   * FLL: fc_diff is captured with fc_upd and evaluated in free-running registered stages
    //     (magnitude, tolerance / loss compares, shift, saturation) while the strobe travels down a
    //     delay line; the decision is taken 7 reference cycles after fc_upd and a pulse starts 2
    //     cycles after the decision (the same number of cycles long as before). The pulse timer is a
    //     16-bit down counter in four digits with registered "digit is zero" flags.
    //   * word domain: per position flags -> counts per five positions -> differences -> sums
    //     (el_sum is 2 words later than a single adder tree would give), then el_x registered, the
    //     accumulator added in two halves, the threshold compared in registered pieces and the PSEL
    //     step taken from registered decisions: the picker reacts 5 words later to the same el_sum.
    //     The hold-off after a step is cfg_pick_hold + PICK_FLUSH words so that the same number of
    //     words measured with the old phase is discarded as before. st_slip_cnt counts a tag one
    //     word after it is sent. Word qualification uses the bad-word flag one word later.
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
    // frun: the loop may run (0 = disabled or restart; everything below is cleared one cycle later)
    reg frun, me_q;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin
            frun <= 1'b0; me_q <= 1'b0;
        end else if (!en_s || kick) begin
            frun <= 1'b0; me_q <= 1'b0;
        end else begin
            frun <= 1'b1; me_q <= man_edge;
        end

    // -------- evaluation of one counter result, free running on the captured value
    wire        a_up  = fc_diff[13] ^ cfg_fll_inv;          // ring slow -> FUP
    reg         fu0, up0;                                   // fc_upd, direction: registered at the input
    reg [13:0]  fd0;                                        // fc_diff captured with fc_upd
    reg [4:0]   evd;                                        // strobe delay line
    reg [2:0]   nz;                                         // fd0[4k+3:4k] != 0
    reg [12:0]  mag;                                        // |fd0|, saturated
    reg         th, tg1, te1, tg0, in_tol_q, out_loss_q;
    reg [15:0]  sa, len;                                    // mag << shift, saturated
    reg [3:0]   lz;                                         // len digit == 0
    reg         a_is1;                                      // len == 1
    // digit of -x: a bit flips when any lower bit (low = in a lower digit) is set
    function automatic [3:0] magn(input [3:0] x, input neg, input low);
        magn = x ^ ({4{neg}} & {low | x[2] | x[1] | x[0], low | x[1] | x[0], low | x[0], low});
    endfunction
    wire        fneg = fd0[13];
    wire        fmin = fneg && !fd0[12] && nz == 3'd0;      // -8192: magnitude saturates
    wire        out_loss = cfg_fll_loss != 12'd0 && mag > {1'b0, cfg_fll_loss};
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin
            fu0 <= 1'b0; up0 <= 1'b0; fd0 <= 14'd0; evd <= 5'd0; nz <= 3'd0; mag <= 13'd0;
            th <= 1'b0; tg1 <= 1'b0; te1 <= 1'b0; tg0 <= 1'b0; in_tol_q <= 1'b0; out_loss_q <= 1'b0;
            sa <= 16'd0; len <= 16'd0; lz <= 4'd0; a_is1 <= 1'b0;
        end else begin
            fu0 <= fc_upd;                                              // cycle 1 (fc_upd = cycle 0)
            if (fc_upd) begin fd0 <= fc_diff; up0 <= a_up; end
            evd <= {evd[3:0], fu0};
            nz  <= {|fd0[11:8], |fd0[7:4], |fd0[3:0]};                  // cycle 2
            mag <= fmin ? 13'h1fff :                                    // cycle 3
                   {fd0[12] ^ (fneg & |nz), magn(fd0[11:8], fneg, nz[1] | nz[0]),
                    magn(fd0[7:4], fneg, nz[0]), magn(fd0[3:0], fneg, 1'b0)};
            th  <= |mag[12:8];                                          // cycle 4
            tg1 <= mag[7:4] >  cfg_fll_tol[7:4];
            te1 <= mag[7:4] == cfg_fll_tol[7:4];
            tg0 <= mag[3:0] >  cfg_fll_tol[3:0];
            out_loss_q <= out_loss;
            sa  <= {3'd0, mag} << cfg_fll_shift[1:0];
            in_tol_q <= !(th || tg1 || (te1 && tg0));                   // cycle 5: mag <= cfg_fll_tol
            len <= !cfg_fll_shift[2] ? sa : |sa[15:12] ? 16'hffff : {sa[11:0], 4'd0};
            lz  <= {len[15:12] == 4'd0, len[11:8] == 4'd0, len[7:4] == 4'd0, len[3:0] == 4'd0};  // 6
            a_is1 <= lz[3] && lz[2] && lz[1] && len[3:0] == 4'd1;       // cycle 7
        end
    wire [15:0] m_len = {8'd0, cfg_fll_man_len} << cfg_fll_shift;      // static
    wire [3:0]  m_z   = {m_len[15:12] == 4'd0, m_len[11:8] == 4'd0, m_len[7:4] == 4'd0, m_len[3:0] == 4'd0};
    wire        m_nz  = m_len != 16'd0;
    wire        m_is1 = m_len == 16'd1;

    // -------- state: one flop per state (none = off); fst is the st_state code
    reg        son, s_idle, s_wait, s_pulse, s_settle, s_done;
    wire [2:0] fst = {s_settle | s_done, s_wait | s_pulse, s_idle | s_pulse | s_done};
    reg        good, man_pend, d_man, sarm, ld_m, ld_a;
    // decisions, registered one cycle ahead: d_tw to the wait state (settled / frequency lost),
    // d_lw leave it (d_done or d_pulse), d_gc clear good (d_pulse or d_lost)
    reg        d_tw, d_lw, d_acc, d_lost, d_good, d_done, d_pulse, d_gc;
    // pulse timer: pc counts the remaining cycles, pz[k] = digit k is 0, plast = pc is 1 (only
    // ever set in the pulse state)
    reg [15:0] pc;
    reg [3:0]  pz;
    reg        plast;
    reg [7:0]  wnx;                                         // st_fll_win + 1, saturated
    // decisions (cycle 6; nothing can change the state before they are used in cycle 7: a manual
    // request that is pending or arriving cancels them). d_man: the pending manual request is
    // served in the next cycle (never in the pulse state: a running pulse ends first).
    wire ev_ok = evd[4] && !man_pend && !me_q;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin
            d_tw <= 1'b0; d_lw <= 1'b0; d_acc <= 1'b0; d_lost <= 1'b0; d_good <= 1'b0; d_done <= 1'b0;
            d_pulse <= 1'b0; d_gc <= 1'b0; d_man <= 1'b0; sarm <= 1'b0; wnx <= 8'd0;
        end else begin
            d_man   <= frun && man_pend && !d_man && !s_pulse;
            // the window that contains a pulse (or the start) is discarded: only a result whose
            // own strobe was seen in the settle state ends it
            sarm    <= s_settle && (sarm || fu0);
            d_tw    <= ev_ok && ((s_settle && sarm) || (s_done && out_loss_q));
            d_lw    <= ev_ok && s_wait && (!in_tol_q || good);
            d_acc   <= ev_ok && (s_wait || s_done);
            d_lost  <= ev_ok && s_done && out_loss_q;
            d_good  <= ev_ok && s_wait && in_tol_q;
            d_done  <= ev_ok && s_wait && in_tol_q && good;
            d_pulse <= ev_ok && s_wait && !in_tol_q;
            d_gc    <= ev_ok && ((s_wait && !in_tol_q) || (s_done && out_loss_q));
            wnx     <= &st_fll_win ? 8'hff : st_fll_win + 8'd1;
        end

    // man_pend / d_man are only set with son = 1; good and st_fll_done are 0 in the pulse state
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin
            son <= 1'b0; s_idle <= 1'b0; s_wait <= 1'b0; s_pulse <= 1'b0; s_settle <= 1'b0; s_done <= 1'b0;
            good <= 1'b0; man_pend <= 1'b0; ld_m <= 1'b0; ld_a <= 1'b0;
            st_fll_done <= 1'b0; st_fll_lost <= 1'b0;
        end else if (!frun) begin
            son <= 1'b0; s_idle <= 1'b0; s_wait <= 1'b0; s_pulse <= 1'b0; s_settle <= 1'b0; s_done <= 1'b0;
            good <= 1'b0; man_pend <= 1'b0; ld_m <= 1'b0; ld_a <= 1'b0;
            st_fll_done <= 1'b0; st_fll_lost <= 1'b0;
        end else begin
            son <= 1'b1; ld_m <= 1'b0; ld_a <= 1'b0;
            if (d_man) begin                                    // manual pulse, any mode
                man_pend <= 1'b0; st_fll_done <= 1'b0; good <= 1'b0;
                if (m_nz) begin
                    s_idle <= 1'b0; s_wait <= 1'b0; s_settle <= 1'b0; s_done <= 1'b0;
                    s_pulse <= 1'b1; ld_m <= 1'b1;
                end
            end else if (!cfg_fll_auto) begin
                s_wait <= 1'b0; s_settle <= 1'b0; s_done <= 1'b0; st_fll_done <= 1'b0; good <= 1'b0;
                if (!s_pulse || plast) begin s_pulse <= 1'b0; s_idle <= 1'b1; end
            end else begin
                if (!son || s_idle) begin s_idle <= 1'b0; s_settle <= 1'b1; end
                if (plast) begin s_pulse <= 1'b0; s_settle <= 1'b1; end      // last cycle of the pulse
                if (d_tw) begin s_settle <= 1'b0; s_done <= 1'b0; s_wait <= 1'b1; end
                if (d_lw) s_wait <= 1'b0;
                if (d_done) begin s_done <= 1'b1; st_fll_done <= 1'b1; end
                if (d_pulse) begin s_pulse <= 1'b1; ld_a <= 1'b1; end
                if (d_lost) begin st_fll_done <= 1'b0; st_fll_lost <= 1'b1; end
                if (d_good) good <= 1'b1;
                if (d_gc) good <= 1'b0;
            end
            if (me_q) man_pend <= 1'b1;
        end

    // status of the accepted windows
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin st_fll_err <= 14'd0; st_fll_win <= 8'd0; end
        else if (!frun) begin st_fll_err <= 14'd0; st_fll_win <= 8'd0; end
        else if (d_acc) begin st_fll_err <= fd0; st_fll_win <= wnx; end

    // pulse: the first cycle in the pulse state (ld_m / ld_a) loads the timer and raises the
    // output; it falls after the cycle in which the timer is 1 (plast). pc / pz run free otherwise.
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin c_cdr_fup <= 1'b0; c_cdr_fdn <= 1'b0; end
        else if (!frun) begin c_cdr_fup <= 1'b0; c_cdr_fdn <= 1'b0; end
        else if (ld_m) begin
            c_cdr_fup <= cfg_fll_man_dir; c_cdr_fdn <= !cfg_fll_man_dir;
        end else if (ld_a) begin
            c_cdr_fup <= up0; c_cdr_fdn <= !up0;
        end else if (plast) begin
            c_cdr_fup <= 1'b0; c_cdr_fdn <= 1'b0;
        end
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin pc <= 16'd0; pz <= 4'd0; plast <= 1'b0; end
        else if (ld_m) begin pc <= m_len; pz <= m_z; plast <= s_pulse && m_is1; end
        else if (ld_a) begin pc <= len; pz <= lz; plast <= s_pulse && a_is1; end
        else begin
            pc[3:0] <= pc[3:0] - 4'd1;
            pz[0]   <= pc[3:0] == 4'd1;
            if (pz[0]) begin pc[7:4] <= pc[7:4] - 4'd1; pz[1] <= pc[7:4] == 4'd1; end
            if (pz[0] && pz[1]) begin pc[11:8] <= pc[11:8] - 4'd1; pz[2] <= pc[11:8] == 4'd1; end
            if (pz[0] && pz[1] && pz[2]) begin pc[15:12] <= pc[15:12] - 4'd1; pz[3] <= pc[15:12] == 4'd1; end
            plast   <= s_pulse && pc[3:0] == 4'd2 && pz[1] && pz[2] && pz[3];
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

    localparam [4:0] PICK_FLUSH = 5'd3;        // extra words of pipeline between the pins and the accumulator

    function automatic [2:0] cnt5(input [4:0] a);
        cnt5 = {2'd0, a[0]} + {2'd0, a[1]} + {2'd0, a[2]} + {2'd0, a[3]} + {2'd0, a[4]};
    endfunction
    function automatic [3:0] sub3(input [2:0] a, input [2:0] b);     // a - b, two's complement
        sub3 = {1'b0, a} - {1'b0, b};
    endfunction

    // stage 0: per position i (d[i], e[i], d[i+1]) straight from the capture pins. The 21st data
    // bit closes edge 19 (first half: DX[20]); for the second half it is not in this word, so
    // position 19 is neutralised by repeating DX[39] as the closing data bit AND as the edge sample
    // (no transition, no violation).
    wire [20:0] d_in = cfg_ew_half ? {wire_rx_data[39], wire_rx_data[39:20]} : wire_rx_data[20:0];
    wire [19:0] e_in = cfg_ew_half ? {wire_rx_data[39], wire_rx_edge[18:0]} : wire_rx_edge;
    wire [19:0] p_tr = d_in[19:0] ^ d_in[20:1];                    // data transition
    reg [19:0] f_late, f_early, f_viol;
    reg        stk;
    reg [3:0]  pv;                             // pipeline / synchronizer flush after release
    wire       rdy = pv[3];
    // stage 1: counts per five positions; stage 2: late - early per group, violations per pair;
    // stage 3: pairs / word violations; stage 4: word total
    reg [2:0]  c_l0, c_l1, c_l2, c_l3, c_e0, c_e1, c_e2, c_e3, c_v0, c_v1, c_v2, c_v3;
    reg [3:0]  g_d0, g_d1, g_d2, g_d3, g_va, g_vb;
    reg [4:0]  h_d0, h_d1;
    reg [5:0]  el_sum;                         // late - early, two's complement
    // configuration and status synchronizers
    reg [1:0]  pa_sy, fk_sy, sp_sy, sm_sy;
    reg [2:0]  tp_sy, tm_sy;
    reg [2:0]  ms1, ms2, ms3;
    reg        ms_eq;
    reg [1:0]  vm1, vm2, vm3, vm_q;
    wire       man_p = rdy && (tp_sy[2] ^ tp_sy[1]);
    wire       man_m = rdy && (tm_sy[2] ^ tm_sy[1]);
    // picker
    reg [4:0]  hold;
    reg        hold_nz;                        // hold != 0
    wire [5:0] el_x  = cfg_pick_inv ? ~el_sum + 6'd1 : el_sum;
    reg [5:0]  el_xq;
    reg [3:0]  a_lo;                           // accumulator, low half (one word ahead of st_pick_acc)
    reg        a_c;                            // its carry
    reg [1:0]  a_eh;                           // el_xq[5:4] for the high half
    wire [4:0] a_los = {1'b0, a_lo} + {1'b0, el_xq[3:0]};
    wire [7:0] thr_p = {2'b00, cfg_pick_thr};  // static
    wire [7:0] thr_n = 8'd0 - thr_p;
    reg        k_dg, k_de, k_dl, k_ug, k_ue, k_ul;                 // st_pick_acc against +thr / -thr, by halves
    reg        go_dn, go_up;                   // late: sample earlier / early: sample later
    // accumulator and decisions are cleared while the picker is off, holds off or steps
    wire       pclr = !rdy || !pa_sy[1] || hold_nz || go_dn || go_up;
    // signal detect
    reg [3:0]  run;
    reg [15:0] gcnt;
    reg [2:0]  gf;                             // gcnt digit k == 15
    reg [2:0]  bcnt;
    reg        bad_q;
    wire [3:0] need_m1 = (4'd1 << cfg_loss_exp) - 4'd1;

    always @(posedge wire_rx_clk or negedge wrst_n)
        if (!wrst_n) begin
            f_late <= 20'd0; f_early <= 20'd0; f_viol <= 20'd0; stk <= 1'b0; pv <= 4'd0;
            c_l0 <= 3'd0; c_l1 <= 3'd0; c_l2 <= 3'd0; c_l3 <= 3'd0;
            c_e0 <= 3'd0; c_e1 <= 3'd0; c_e2 <= 3'd0; c_e3 <= 3'd0;
            c_v0 <= 3'd0; c_v1 <= 3'd0; c_v2 <= 3'd0; c_v3 <= 3'd0;
            g_d0 <= 4'd0; g_d1 <= 4'd0; g_d2 <= 4'd0; g_d3 <= 4'd0; g_va <= 4'd0; g_vb <= 4'd0;
            h_d0 <= 5'd0; h_d1 <= 5'd0; el_sum <= 6'd0; st_viol <= 5'd0;
            pa_sy <= 2'd0; fk_sy <= 2'd0; sp_sy <= 2'd0; sm_sy <= 2'd0; tp_sy <= 3'd0; tm_sy <= 3'd0;
            ms1 <= 3'd0; ms2 <= 3'd0; ms3 <= 3'd0; ms_eq <= 1'b0;
            vm1 <= 2'd0; vm2 <= 2'd0; vm3 <= 2'd0; vm_q <= 2'd0;
            hold <= 5'd0; hold_nz <= 1'b0; el_xq <= 6'd0; a_lo <= 4'd0; a_c <= 1'b0; a_eh <= 2'd0;
            st_pick_acc <= 8'd0;
            k_dg <= 1'b0; k_de <= 1'b0; k_dl <= 1'b0; k_ug <= 1'b0; k_ue <= 1'b0; k_ul <= 1'b0;
            go_dn <= 1'b0; go_up <= 1'b0;
            c_wrx_cap_psel <= 3'd0; c_wrx_cap_slipp <= 1'b0; c_wrx_cap_slipm <= 1'b0;
            st_slip_cnt <= 8'd0; st_slp_seen <= 1'b0; st_slm_seen <= 1'b0;
            run <= 4'd0; st_idle <= 1'b0; gcnt <= 16'd0; gf <= 3'd0; bcnt <= 3'd0; bad_q <= 1'b0;
            st_sig_ok <= 1'b0;
            wire_rx_valid <= 1'b0;
        end else begin
            pv <= {pv[2:0], 1'b1};
            // ---- stage 0
            f_late  <= p_tr & ~(e_in ^ d_in[20:1]);        // edge sample shows the new bit: late
            f_early <= p_tr &  (e_in ^ d_in[20:1]);
            f_viol  <= ~p_tr & (e_in ^ d_in[19:0]);        // equal neighbours, edge sample differs
            stk <= wire_rx_data == 40'd0 || wire_rx_data == {40{1'b1}};
            // ---- stage 1: four groups of five positions
            c_l0 <= cnt5(f_late[4:0]);    c_e0 <= cnt5(f_early[4:0]);    c_v0 <= cnt5(f_viol[4:0]);
            c_l1 <= cnt5(f_late[9:5]);    c_e1 <= cnt5(f_early[9:5]);    c_v1 <= cnt5(f_viol[9:5]);
            c_l2 <= cnt5(f_late[14:10]);  c_e2 <= cnt5(f_early[14:10]);  c_v2 <= cnt5(f_viol[14:10]);
            c_l3 <= cnt5(f_late[19:15]);  c_e3 <= cnt5(f_early[19:15]);  c_v3 <= cnt5(f_viol[19:15]);
            // ---- stage 2
            g_d0 <= sub3(c_l0, c_e0); g_d1 <= sub3(c_l1, c_e1);
            g_d2 <= sub3(c_l2, c_e2); g_d3 <= sub3(c_l3, c_e3);
            g_va <= {1'b0, c_v0} + {1'b0, c_v1};
            g_vb <= {1'b0, c_v2} + {1'b0, c_v3};
            // ---- stage 3
            h_d0 <= {g_d0[3], g_d0} + {g_d1[3], g_d1};
            h_d1 <= {g_d2[3], g_d2} + {g_d3[3], g_d3};
            st_viol <= {1'b0, g_va} + {1'b0, g_vb};
            // ---- stage 4: word total
            el_sum <= {h_d0[4], h_d0} + {h_d1[4], h_d1};
            // ---- synchronizers
            pa_sy <= {pa_sy[0], cfg_pick_auto};
            fk_sy <= {fk_sy[0], st_freq_ok};
            sp_sy <= {sp_sy[0], s_wrx_slp};
            sm_sy <= {sm_sy[0], s_wrx_slm};
            tp_sy <= {tp_sy[1:0], cfg_man_slipp_trig};
            tm_sy <= {tm_sy[1:0], cfg_man_slipm_trig};
            ms1 <= cfg_man_psel; ms2 <= ms1; ms3 <= ms2; ms_eq <= ms1 == ms2;
            vm1 <= cfg_valid_mode; vm2 <= vm1; vm3 <= vm2;
            if (vm2 == vm3) vm_q <= vm3;
            if (sp_sy[1]) st_slp_seen <= 1'b1;
            if (sm_sy[1]) st_slm_seen <= 1'b1;
            // ---- phase picker: accumulate (two halves), compare, decide
            el_xq <= el_x;
            if (pclr) begin
                a_lo <= 4'd0; a_c <= 1'b0; a_eh <= 2'd0; st_pick_acc <= 8'd0;
                go_dn <= 1'b0; go_up <= 1'b0;
            end else begin
                a_lo <= a_los[3:0]; a_c <= a_los[4]; a_eh <= el_xq[5:4];
                st_pick_acc[3:0] <= a_lo;
                st_pick_acc[7:4] <= st_pick_acc[7:4] + {a_eh[1], a_eh[1], a_eh} + {3'd0, a_c};
                go_dn <= k_dg || (k_de && k_dl);            // st_pick_acc >  cfg_pick_thr
                go_up <= k_ug || (k_ue && k_ul);            // st_pick_acc < -cfg_pick_thr
            end
            k_dg <= $signed(st_pick_acc[7:4]) > $signed(thr_p[7:4]);
            k_de <= st_pick_acc[7:4] == thr_p[7:4];
            k_dl <= st_pick_acc[3:0] > thr_p[3:0];
            k_ug <= $signed(st_pick_acc[7:4]) < $signed(thr_n[7:4]);
            k_ue <= st_pick_acc[7:4] == thr_n[7:4];
            k_ul <= st_pick_acc[3:0] < thr_n[3:0];
            // ---- phase picker: PSEL, slip tags, hold-off
            c_wrx_cap_slipp <= 1'b0;
            c_wrx_cap_slipm <= 1'b0;
            if (c_wrx_cap_slipp || c_wrx_cap_slipm) st_slip_cnt <= st_slip_cnt + 8'd1;
            if (!rdy) begin
                hold <= 5'd0; hold_nz <= 1'b0;
            end else if (!pa_sy[1]) begin                   // manual
                hold <= 5'd0; hold_nz <= 1'b0;
                if (ms_eq) c_wrx_cap_psel <= ms3;
                c_wrx_cap_slipp <= man_p;
                c_wrx_cap_slipm <= man_m && !man_p;
            end else if (hold_nz) begin
                hold <= hold - 5'd1; hold_nz <= hold != 5'd1;
            end else if (go_dn) begin
                c_wrx_cap_psel  <= c_wrx_cap_psel - 3'd1;
                c_wrx_cap_slipm <= c_wrx_cap_psel == 3'd4;
                hold <= {1'b0, cfg_pick_hold} + PICK_FLUSH; hold_nz <= 1'b1;
            end else if (go_up) begin
                c_wrx_cap_psel  <= c_wrx_cap_psel + 3'd1;
                c_wrx_cap_slipp <= c_wrx_cap_psel == 3'd3;
                hold <= {1'b0, cfg_pick_hold} + PICK_FLUSH; hold_nz <= 1'b1;
            end
            // ---- signal detect and word qualification
            if (!stk) run <= 4'd0; else if (run != 4'hf) run <= run + 4'd1;
            st_idle <= cfg_idle_words != 4'd0 && run >= cfg_idle_words;
            bad_q   <= st_viol > cfg_viol_thr || st_idle;
            if (!rdy) begin
                gcnt <= 16'd0; gf <= 3'd0; bcnt <= 3'd0; st_sig_ok <= 1'b0;
            end else if (bad_q) begin
                gcnt <= 16'd0; gf <= 3'd0;
                if (st_sig_ok) begin
                    if ({1'b0, bcnt} >= need_m1) begin st_sig_ok <= 1'b0; bcnt <= 3'd0; end
                    else bcnt <= bcnt + 3'd1;
                end
            end else begin
                bcnt <= 3'd0;
                if (!st_sig_ok) begin
                    if (gcnt[cfg_lock_exp]) st_sig_ok <= 1'b1;
                    // good-word count in four digits with registered "digit is 15" flags
                    gcnt[3:0] <= gcnt[3:0] + 4'd1;
                    gf[0]     <= gcnt[3:0] == 4'd14;
                    if (gf[0]) begin gcnt[7:4] <= gcnt[7:4] + 4'd1; gf[1] <= gcnt[7:4] == 4'd14; end
                    if (gf[0] && gf[1]) begin gcnt[11:8] <= gcnt[11:8] + 4'd1; gf[2] <= gcnt[11:8] == 4'd14; end
                    if (gf[0] && gf[1] && gf[2]) gcnt[15:12] <= gcnt[15:12] + 4'd1;
                end
            end
            wire_rx_valid <= rdy && (vm_q == 2'd0 ? st_sig_ok && fk_sy[1] :
                                     vm_q == 2'd1 ? fk_sy[1] : vm_q == 2'd2);
        end
endmodule
`default_nettype wire
