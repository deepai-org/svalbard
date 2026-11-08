// Wired-RX CDR digital part, word domain (dual-loop CDR, no phase interpolator).
//
// Analog / fast-cell boundary (all ring-rate capture is in pt_wrx_cap, analog/wired_rx/capture.py):
//   * pt_wrx_cap turns the eight pt_slicer samples per ring cycle into 20-bit double words
//     data_word / edge_word (bit 0 = oldest), stable for one word and sampled here on word_clk rise
//     (pt_wordclk WORD_CLK, one word per 20 bits in every mode).
//       quarter (4 bits/ring cycle): data = phases 0,2,4,6, edge = 1,3,5,7
//       half    (2 bits/ring cycle): data = phases 0,4,       edge = 2,6
//       full    (1 bit /ring cycle): data = phase psel,       edge = psel+4
//   * psel / slip_p / slip_m go back to pt_wrx_cap (PSEL0..2, SLIPP, SLIPM); it applies psel from
//     the next word it starts and returns the slip with that word (cap_slip_p / cap_slip_m).
//   * pt_cdr (cdr.spice): freq_hold freezes the ring PLL's frequency loop; bb_up / bb_dn drive its
//     weak bang-bang pump on the PLL loop filter; bb_gain doubles that current.
//
// Modes (cfg_bits_per_cycle):
//   2 quarter, 1 half (1.25-2.97 Gb/s): dual loop.  Acquire (freq_hold=0) for cfg_acq_words words,
//      then freq_hold=1.  With cfg_fll_en=1 a frequency-locked step follows first: ring words are
//      counted over 5*2^cfg_fll_win reference cycles (expected 4*bpc*2^cfg_fll_win for the /16 ring
//      PLL) and bb_up/bb_dn are pulsed |error| << cfg_fll_shift words, once per window, until
//      |error| <= cfg_fll_tol (fll_done).  Then the bang-bang phase loop: one up/down decision per
//      word from the word's early/late majority.
//   0 full (480-810 Mb/s, USB HS bursts): the ring stays locked to the reference (freq_hold=0).  A
//      bang-bang phase picker moves psel by one phase (1/8 UI) when a word's early/late majority
//      exceeds cfg_pick_hyst, at most once per 3 words (the capture applies psel one word later).
//      psel only changes at word boundaries.  pt_wrx_cap takes data from phase psel of the current
//      ring cycle for psel 0..3 and of the previous cycle for psel 4..7 (edge = the sample half a UI
//      after the data), so the effective sampling phase runs -4..+3 eighths and 7 <-> 0 is seamless;
//      the wrap is at 3 <-> 4: 3 -> 4 makes the next word start with a duplicate of the previous
//      word's last bit (slip_p = +1 bit), 4 -> 3 skips one bit between the words (slip_m = -1 bit).  The slip flag travels with the affected word to the FPGA (rx_slip_*),
//      which absorbs it in its elastic buffer.
//   cfg_raw=1: no loop action; words pass through (fallback routes: external clock / FPGA).
`default_nettype none
module pt_wrx_cdr_loop (
    input  wire        word_clk,
    input  wire        rst_n,
    input  wire [19:0] data_word,
    input  wire [19:0] edge_word,
    input  wire        cap_slip_p,
    input  wire        cap_slip_m,
    input  wire        cfg_en,
    input  wire        cfg_raw,
    input  wire [1:0]  cfg_bits_per_cycle,   // 0 full, 1 half, 2 quarter
    input  wire [15:0] cfg_acq_words,
    input  wire        cfg_bb_invert,        // swaps bb_up/bb_dn and the picker direction (bring-up escape)
    input  wire [3:0]  cfg_pick_hyst,        // full rate: |early-late| needed to step psel
    input  wire        ref_clk,              // the RX ring PLL reference (ring = 16 x ref)
    input  wire        cfg_fll_en,
    input  wire [3:0]  cfg_fll_win,
    input  wire [2:0]  cfg_fll_shift,
    input  wire [7:0]  cfg_fll_tol,
    input  wire        cfg_bb_gain,
    input  wire        cfg_fll_boost,
    output reg         freq_hold,
    output reg         bb_up,
    output reg         bb_dn,
    output wire        bb_gain,
    output reg         fll_done,
    output reg  [15:0] fll_err,
    output reg  [2:0]  psel,
    output reg         slip_p,
    output reg         slip_m,
    output reg  [19:0] rx_word,
    output reg         rx_slip_p,
    output reg         rx_slip_m,
    output reg         rx_valid,
    output reg  [7:0]  early_count,
    output reg  [7:0]  late_count
);
    // ---------------- reset synchronizer (word domain)
    reg [1:0] rs;
    always @(posedge word_clk or negedge rst_n)
        if (!rst_n) rs <= 2'b00; else rs <= {rs[0], 1'b1};
    wire rst_q = rs[1];
    wire [1:0] mode = cfg_bits_per_cycle;

    // ---------------- early / late over the word's transitions (bit 0 oldest; edge k between data k, k+1)
    reg        prev_d, prev_e;
    integer    k;
    reg [4:0]  early_w, late_w;
    reg        a, e, bn;
    always @* begin
        early_w = 0; late_w = 0;
        for (k = 0; k < 20; k = k + 1) begin
            if (k == 0) begin a = prev_d; e = prev_e; end
            else begin a = data_word[k - 1]; e = edge_word[k - 1]; end
            bn = data_word[k];
            if (a != bn) begin
                if (e == bn) late_w = late_w + 1; else early_w = early_w + 1;
            end
        end
    end
    wire late_maj  = (late_w > early_w) ^ (cfg_bb_invert & (late_w != early_w));
    wire early_maj = (early_w > late_w) ^ (cfg_bb_invert & (late_w != early_w));
    wire [4:0] el_diff = (late_w > early_w) ? late_w - early_w : early_w - late_w;

    // ---------------- reference-domain FLL window (toggles every 5 * 2^cfg_fll_win reference cycles)
    reg [1:0]  ref_rs;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) ref_rs <= 2'b00; else ref_rs <= {ref_rs[0], 1'b1};
    reg [13:0] rcnt;
    reg        rtog;
    wire [13:0] rlast = (14'd5 << cfg_fll_win) - 14'd1;
    wire       rst_r = ref_rs[1];
    always @(posedge ref_clk or negedge rst_r)
        if (!rst_r) begin rcnt <= 0; rtog <= 0; end
        else if (rcnt >= rlast) begin rcnt <= 0; rtog <= ~rtog; end
        else rcnt <= rcnt + 14'd1;

    reg [15:0] acq;
    reg [2:0]  tsync;
    wire       wedge = tsync[2] ^ tsync[1];
    reg [15:0] wordcnt, wsnap;
    wire [15:0] wmeas = wordcnt - wsnap;
    wire [15:0] wexp = (mode == 2'd2 ? 16'd16 : 16'd8) << cfg_fll_win;
    wire [15:0] werr = wmeas - wexp;
    wire [15:0] wabs = werr[15] ? -werr : werr;
    localparam F_SKIP = 2'd0, F_MEAS = 2'd1, F_PULSE = 2'd2, F_DONE = 2'd3;
    reg [1:0]  fst;
    reg [15:0] pulse;
    reg        pdir;
    reg [1:0]  holdoff;               // full-rate picker: words to wait after a step
    assign bb_gain = cfg_bb_gain | (cfg_fll_boost & fll_done);

    always @(posedge word_clk or negedge rst_q)
        if (!rst_q) begin
            prev_d <= 0; prev_e <= 0; rx_word <= 0; rx_slip_p <= 0; rx_slip_m <= 0; rx_valid <= 0;
            early_count <= 0; late_count <= 0; acq <= 0; freq_hold <= 0; bb_up <= 0; bb_dn <= 0;
            tsync <= 0; wordcnt <= 0; wsnap <= 0; fst <= F_SKIP; pulse <= 0; pdir <= 0; fll_done <= 0; fll_err <= 0;
            psel <= 3'd0; slip_p <= 0; slip_m <= 0; holdoff <= 0;
        end else begin
            prev_d <= data_word[19]; prev_e <= edge_word[19];
            rx_word <= data_word; rx_slip_p <= cap_slip_p; rx_slip_m <= cap_slip_m; rx_valid <= cfg_en;
            early_count <= (early_count > 8'd235) ? 8'd255 : early_count + {3'd0, early_w};
            late_count  <= (late_count  > 8'd235) ? 8'd255 : late_count  + {3'd0, late_w};
            tsync <= {tsync[1:0], rtog};
            wordcnt <= wordcnt + 16'd1;
            if (wedge) wsnap <= wordcnt;
            slip_p <= 0; slip_m <= 0;
            if (!cfg_en || cfg_raw) begin
                acq <= 0; freq_hold <= 0; bb_up <= 0; bb_dn <= 0; fst <= F_SKIP; fll_done <= 0; holdoff <= 0;
            end else if (mode == 2'd0) begin
                // full rate: blind bang-bang phase picker, ring stays on the reference
                acq <= 0; freq_hold <= 0; bb_up <= 0; bb_dn <= 0; fst <= F_SKIP; fll_done <= 0;
                if (holdoff != 0) holdoff <= holdoff - 2'd1;
                else if (late_maj && el_diff > {1'b0, cfg_pick_hyst}) begin
                    psel <= psel - 3'd1; slip_m <= (psel == 3'd4); holdoff <= 2'd2;   // sample earlier
                end else if (early_maj && el_diff > {1'b0, cfg_pick_hyst}) begin
                    psel <= psel + 3'd1; slip_p <= (psel == 3'd3); holdoff <= 2'd2;   // sample later
                end
            end else if (acq < cfg_acq_words) begin
                acq <= acq + 16'd1; freq_hold <= 0; bb_up <= 0; bb_dn <= 0; fst <= F_SKIP; fll_done <= 0;
            end else begin
                freq_hold <= 1;
                if (cfg_fll_en && fst != F_DONE) begin
                    bb_up <= 0; bb_dn <= 0;
                    case (fst)
                        F_SKIP:  if (wedge) fst <= F_MEAS;
                        F_MEAS:  if (wedge) begin
                                     fll_err <= werr;
                                     if (wabs <= {8'd0, cfg_fll_tol}) begin fst <= F_DONE; fll_done <= 1; end
                                     else begin
                                         fst <= F_PULSE; pdir <= ~werr[15];
                                         pulse <= (wabs > (16'hffff >> cfg_fll_shift)) ? 16'hffff : (wabs << cfg_fll_shift);
                                     end
                                 end
                        default: begin
                                     if (pulse == 0) fst <= F_MEAS;
                                     else begin
                                         pulse <= pulse - 16'd1;
                                         bb_dn <= pdir; bb_up <= ~pdir;
                                     end
                                 end
                    endcase
                end else begin
                    fll_done <= cfg_fll_en;
                    // early (clock ahead of the data) -> slow the ring (dn); late -> speed up (up)
                    bb_up <= late_maj;
                    bb_dn <= early_maj;
                end
            end
        end
endmodule
`default_nettype wire
