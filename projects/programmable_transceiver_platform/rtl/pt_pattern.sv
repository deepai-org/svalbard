// Shared wired-link test pattern generator and seed-locking PRBS checker
// (spec/consolidation-pass.md P2-6). One design for TX and RX; it replaces the
// former analog/wired_tx/rtl/pt_wtx_pattern and the PRBS31-only pt_prbs.
//
// The line word is 10 bits, bit 0 first (integration/macro-contract.md "Wired word
// width"). The cores are width-generic; the chip uses them at W=20 (two line words
// per datapath update, word 0 = earlier in bits [9:0]) behind the 10<->20 gearboxes
// pt_pattern_tx / pt_pattern_rx at the end of this file. In the gearboxes the cores
// are clocked through an integrated clock gate (pt_clock_gate) that passes at most
// every other word-clock edge, so core-to-core paths are two-cycle (multicycle 2)
// paths of the word clock; see verification/run_p2_synth.sh. The cores' own `ce`
// inputs are tied 1 there (they remain for width-generic use and the W=10/16 tests).
//
// Bit-stream convention (shared with analog/wired_tx/sim_wiredtx.py prbs7_bits):
// Fibonacci LFSR, all-ones seed, each output bit is the newly generated bit
//   b = h[L-1] ^ h[T-1],  h = {h, b}     (h[0] = newest output bit)
// so the LFSR state is exactly the last L output bits. The checker exploits
// this: it seeds itself from the received bits and needs no word alignment.
//   cfg_mode 0 payload  word = data_in
//            1 PRBS7    x^7  + x^6  + 1
//            2 PRBS15   x^15 + x^14 + 1
//            3 PRBS31   x^31 + x^28 + 1
//            4 clock    1010... (bit 0 = 1), bit-rate/2 square wave
//            5 slow     W ones then W zeros, bit-rate/(2W) square wave (W=20 in the chip)
//            6 user     cfg_user every word
//            7 idle     all zero
`default_nettype none

module pt_pattern_gen #(parameter integer W=10)(
    input  wire         clk,
    input  wire         rst_n,      // async: history all ones, word 0, not primed
    input  wire         ce,         // clock enable for `step` (multicycle datapath)
    input  wire         step,       // advance to the next word (consumer took `word`)
    input  wire [2:0]   cfg_mode,   // static while running (change under reset)
    input  wire         cfg_invert, // invert the transmitted word (polarity check)
    input  wire [W-1:0] cfg_user,
    input  wire [W-1:0] data_in,
    input  wire         inject,     // pulse: flip bit 0 of the next generated word
    output reg  [W-1:0] word        // registered; first word loads on the first clock after reset
);
    reg  [30:0] h;                  // shared output history for all three polynomials
    reg         slow, primed, inj;

    wire        prbs = (cfg_mode == 3'd1) || (cfg_mode == 3'd2) || (cfg_mode == 3'd3);
    // Lockup guard after an illegal live mode change (all-zero history): force the
    // newest history bit to 1 (one flop, off the word path); at most one all-zero
    // word is emitted before the sequence resumes.
    wire        zero = cfg_mode == 3'd1 ? h[6:0] == 0 : cfg_mode == 3'd2 ? h[14:0] == 0 : h == 0;

    // Advance by W bits: {next history, W output bits (bit 0 first)}.
    function automatic [W+30:0] prbs_step(input [30:0] s, input [2:0] mode);
        reg [30:0] t; reg [W-1:0] o; reg b; integer i;
        begin
            t = s;
            for (i = 0; i < W; i = i + 1) begin
                case (mode)
                    3'd1:    b = t[6]  ^ t[5];
                    3'd2:    b = t[14] ^ t[13];
                    default: b = t[30] ^ t[27];
                endcase
                o[i] = b; t = {t[29:0], b};
            end
            prbs_step = {t, o};
        end
    endfunction

    function automatic [W-1:0] clock_word(input dummy);
        integer i;
        for (i = 0; i < W; i = i + 1) clock_word[i] = (i % 2) == 0;
    endfunction

    // Three fixed-polynomial networks then a mode mux (shallower than a mux per bit step).
    wire [W+30:0] n7 = prbs_step(h, 3'd1), n15 = prbs_step(h, 3'd2), n31 = prbs_step(h, 3'd3);
    wire [W+30:0] n = cfg_mode == 3'd1 ? n7 : cfg_mode == 3'd2 ? n15 : n31;
    reg  [W-1:0]  nx;
    always @* begin
        case (cfg_mode)
            3'd0:              nx = data_in;
            3'd1, 3'd2, 3'd3:  nx = n[W-1:0];
            3'd4:              nx = clock_word(1'b0);
            3'd5:              nx = slow ? {W{1'b1}} : {W{1'b0}};
            3'd6:              nx = cfg_user;
            default:           nx = {W{1'b0}};
        endcase
    end

    wire advance = (ce && step) || !primed;
    wire inj_now = inj || inject;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            h <= 31'h7fffffff; slow <= 1'b0; primed <= 1'b0; inj <= 1'b0; word <= {W{1'b0}};
        end else if (advance) begin
            primed <= 1'b1;
            if (prbs) h <= {n[W+30:W+1], n[W] | zero};
            slow <= ~slow;
            word <= (cfg_invert ? ~nx : nx) ^ {{(W-1){1'b0}}, inj_now};
            inj  <= 1'b0;
        end else begin
            inj <= inj_now;
        end
    end
endmodule

// Seed-locking PRBS checker. While unlocked the reference history is loaded from
// the received bits (any word alignment); LOCK_WORDS consecutive valid words that
// match the prediction from a non-zero history assert `locked`. While locked the
// reference free-runs, so each line bit error is counted exactly once (no error
// multiplication). UNLOCK_WORDS consecutive words containing errors (bit slip,
// pattern change, loss of signal) drop lock, set sticky `lost_lock` and reseed.
// Error counting (timing-driven): mismatch register -> popcount register -> a small
// pending accumulator `pend` -> the count, which steps by exactly one per `ce` cycle
// while errors are pending. `errors` is that count in binary and `errors_gray` the same
// count Gray-coded, so one bit changes per update and it can be sampled asynchronously.
// Both saturate at the maximum without wrapping. During bursts (up to W errors per
// word) the count lags and catches up when errors stop; if `pend` would overflow
// (sustained error rate above one per `ce` cycle) the count runs to saturation, i.e.
// it reports "at least the maximum" instead of a wrong exact value. `clear` (held >= 2
// clocks when ce toggles) resets everything at once, a multi-bit Gray change.
module pt_pattern_check #(parameter integer W=10, parameter integer CW=16,
                          parameter integer LOCK_WORDS=4, parameter integer UNLOCK_WORDS=4)(
    input  wire          clk,
    input  wire          rst_n,
    input  wire          ce,         // clock enable: every register updates only when ce
    input  wire          enable,     // 0: unlocked and idle (counters hold)
    input  wire          valid,      // data carries a received word
    input  wire [W-1:0]  data,       // data[0] received first
    input  wire [2:0]    cfg_mode,   // 1 PRBS7, 2 PRBS15, 3 PRBS31; other codes disable
    input  wire          cfg_invert, // expect an inverted stream
    input  wire          clear,      // synchronous: errors <= 0, lost_lock <= 0
    output reg           locked,
    output reg           lost_lock,  // sticky: lock was lost since the last clear
    output reg  [CW-1:0] errors,     // bit errors while locked (binary), saturating
    output reg  [CW-1:0] errors_gray // the same count, Gray-coded
);
    localparam integer QW = 8;       // pending-error accumulator width
    reg  [QW-1:0] pend;
    reg           ovf;               // pend overflowed: run the count to saturation
    wire [CW-1:0] errors_n = errors + 1'b1;
    // Saturation flag kept as a register (always equal to &errors: errors only changes by
    // clear, reset or the +1 step below), so the 16-bit AND is off the pend/step path.
    reg           at_max;
    localparam integer RW = 8;
    localparam integer PW = $clog2(W + 1);
    reg  [30:0]   h;
    reg  [RW-1:0] run, bad;
    reg  [W-1:0]  mism_q;            // mismatch bits of a counted word
    reg           mism_v;
    // Two-stage check (timing at W=40 / 62.5 MHz, 2026-11-10): stage 1 registers the word's mismatch
    // vector (mism_q) with its valid/nonzero flags; stage 2 decides lock, unlock and error counting
    // from the registered vector, one word later. The predictor (h) is updated in stage 1 from the
    // registered lock state, so a lock change takes effect one word later than before.
    reg           v1, nz1;
    wire          zero1 = mism_q == {W{1'b0}};

    function automatic [W+30:0] prbs_step(input [30:0] s, input [2:0] mode);
        reg [30:0] t; reg [W-1:0] o; reg b; integer i;
        begin
            t = s;
            for (i = 0; i < W; i = i + 1) begin
                case (mode)
                    3'd1:    b = t[6]  ^ t[5];
                    3'd2:    b = t[14] ^ t[13];
                    default: b = t[30] ^ t[27];
                endcase
                o[i] = b; t = {t[29:0], b};
            end
            prbs_step = {t, o};
        end
    endfunction
    function automatic [30:0] shift_in(input [30:0] s, input [W-1:0] r);
        reg [30:0] t; integer i;
        begin
            t = s;
            for (i = 0; i < W; i = i + 1) t = {t[29:0], r[i]};
            shift_in = t;
        end
    endfunction
    function automatic [CW:0] popcount(input [W-1:0] v);
        integer i;
        begin
            popcount = 0;
            for (i = 0; i < W; i = i + 1) popcount = popcount + v[i];
        end
    endfunction

    wire          on   = enable && (cfg_mode == 3'd1 || cfg_mode == 3'd2 || cfg_mode == 3'd3);
    wire [W-1:0]  r    = cfg_invert ? ~data : data;
    wire [W+30:0] p7   = prbs_step(h, 3'd1), p15 = prbs_step(h, 3'd2), p31 = prbs_step(h, 3'd3);
    wire [W+30:0] p    = cfg_mode == 3'd1 ? p7 : cfg_mode == 3'd2 ? p15 : p31;
    wire [W-1:0]  mism = r ^ p[W-1:0];
    wire          nz   = cfg_mode == 3'd1 ? h[6:0] != 0 : cfg_mode == 3'd2 ? h[14:0] != 0 : h != 0;
    wire          step_cnt = !at_max && (ovf || pend != 0);
    // Error popcount as a pipelined tree (AC-1 timing at 12.3 ns, ss32): stage P1 registers 5-bit group
    // counts of the mismatch vector, P2a pair sums, P2b their balanced sum, then the accumulator.
    // Errors are counted three words later than the lock decision; counts are unchanged.
    localparam integer NG = (W + 4) / 5;
    function automatic [2:0] pop5(input [4:0] v);
        pop5 = ({2'b0, v[0]} + {2'b0, v[1]}) + ({2'b0, v[2]} + {2'b0, v[3]}) + {2'b0, v[4]};
    endfunction
    reg  [3*NG-1:0] grp;             // group counts of the word flagged by mism_v (same edge)
    reg  [PW-1:0]   psum; reg psum_v;
    reg  [4*((NG+1)/2)-1:0] pair; reg pair_v;   // P2a: sums of group pairs (<= 10 each)
    wire [5*NG-1:0] mism_pad = {{(5*NG-W){1'b0}}, mism_q};
    integer gi, gs;   // separate loop variables per always block (a shared one breaks synthesis)
    localparam integer NP = (NG + 1) / 2;
    reg  [PW+2:0]   ptree [0:2*NP-2];
    always @* begin
        for (gi = 0; gi < NP; gi = gi + 1) ptree[NP-1+gi] = pair[4*gi+:4];
        for (gi = NP-2; gi >= 0; gi = gi - 1) ptree[gi] = ptree[2*gi+1] + ptree[2*gi+2];
    end
    // pend + psum - dec as four parallel candidates selected late by {psum_v, dec} (timing closure
    // 2026-11-11: the pend != 0 decision no longer sits in front of the adder; psum_m1 = psum - 1 is
    // registered with psum, psum >= 1 whenever psum_v; dec implies pend >= 1). Same values.
    reg  [PW-1:0] psum_m1;
    wire          dec    = step_cnt && !ovf;
    wire [QW:0]   s_p    = {1'b0, pend} + psum, s_pm1 = {1'b0, pend} + psum_m1;
    wire [QW:0]   s_m1   = {1'b0, pend} - 1'b1;
    wire [QW:0]   pend_sum = psum_v ? (dec ? s_pm1 : s_p) : (dec ? s_m1 : {1'b0, pend});

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            h <= 31'h7fffffff; run <= 0; bad <= 0; locked <= 1'b0; lost_lock <= 1'b0; errors <= 0;
            mism_q <= 0; grp <= 0; pair <= 0; pair_v <= 1'b0; psum <= 0; psum_m1 <= 0; psum_v <= 1'b0; mism_v <= 1'b0; pend <= 0; ovf <= 1'b0; errors_gray <= 0; at_max <= 1'b0;
            v1 <= 1'b0; nz1 <= 1'b0;
        end else if (ce) begin
            // stage 1: predictor update and mismatch vector of this word
            if (on && valid) h <= locked ? p[W+30:W] : shift_in(h, r);
            mism_q <= mism;
            v1     <= on && valid;
            nz1    <= nz;
            // stage 2: lock decisions on the previous word (mism_q)
            if (!on) begin
                locked <= 1'b0; run <= 0; bad <= 0;
            end else if (v1) begin
                if (!locked) begin
                    bad <= 0;
                    if (!(zero1 && nz1)) run <= 0;
                    else if (run == LOCK_WORDS - 1) begin locked <= 1'b1; run <= 0; end
                    else run <= run + 1'b1;
                end else begin
                    if (zero1) bad <= 0;
                    else if (bad == UNLOCK_WORDS - 1) begin
                        locked <= 1'b0; bad <= 0; run <= 0;
                    end else bad <= bad + 1'b1;
                end
            end
            // error count of a word checked while locked: flag and popcount of the same word (mism_q)
            mism_v <= on && v1 && locked && !zero1 && !clear;
            for (gs = 0; gs < NG; gs = gs + 1) grp[3*gs+:3] <= pop5(mism_pad[5*gs+:5]);
            for (gs = 0; gs < NP; gs = gs + 1)
                pair[4*gs+:4] <= {1'b0, grp[6*gs+:3]} + ((2*gs+1 < NG) ? {1'b0, grp[(6*gs+3)%(3*NG)+:3]} : 4'd0);
            pair_v <= mism_v && !clear;
            psum   <= ptree[0][PW-1:0];
            psum_m1 <= ptree[0][PW-1:0] - 1'b1;
            psum_v <= pair_v && !clear;
            if (clear) begin
                errors <= 0; lost_lock <= 1'b0; pend <= 0; ovf <= 1'b0; errors_gray <= 0; at_max <= 1'b0;
            end else begin
                if (step_cnt) begin errors <= errors_n; errors_gray <= errors_n ^ (errors_n >> 1); at_max <= &errors_n; end
                if (at_max) pend <= 0;
                else if (pend_sum[QW]) begin ovf <= 1'b1; pend <= 0; end
                else pend <= pend_sum[QW-1:0];
                if (on && v1 && locked && !zero1 && bad == UNLOCK_WORDS - 1) lost_lock <= 1'b1;
            end
        end
    end
endmodule

// ---------------------------------------------------------------------------
// N independent 2-flop synchronizers for quasi-static configuration bits.
module pt_sync_vec #(parameter integer N=1)(input wire clk, rst_n, input wire [N-1:0] d, output reg [N-1:0] q);
    (* async_reg = "true" *) reg [N-1:0] meta;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin meta <= {N{1'b0}}; q <= {N{1'b0}}; end else begin meta <= d; q <= meta; end
endmodule

// ---------------------------------------------------------------------------
// Integrated clock gate. Synthesis (yosys defines SYNTHESIS) instantiates the GF180
// latch-based cell gf180mcu_fd_sc_mcu7t5v0__icgtp_2 (read the liberty with
// `read_liberty -lib` first); simulation and lint use the equivalent behavioural
// model: enable latched while clk is low, gclk = clk & latched enable. In the
// behavioural model gclk rises in the same time step as clk (continuous assignment,
// before non-blocking updates), so gated and ungated flops sample consistently.
module pt_clock_gate(
    input  wire clk,
    input  wire en,        // sampled while clk is low; gclk pulses on the next clk high phase
    output wire gclk
);
`ifdef SYNTHESIS
    gf180mcu_fd_sc_mcu7t5v0__icgtp_2 icg(.TE(1'b0), .E(en), .CLK(clk), .Q(gclk));
`else
    reg en_l;
    always @(*) if (!clk) en_l = en;
    assign gclk = clk & en_l;
`endif
endmodule

// ---------------------------------------------------------------------------
// TX gearbox: one 10-bit line word per word clock from a 20-bit generator on a gated
// clock. `word` is a register (only flop clock-to-output reaches the analog
// serializer): the consumer takes it on a clock edge with `request`, and the next word
// is loaded at that edge. `hi` holds the second word of the current pair and the
// generator holds the next pair; the generator advances only when the second word
// is taken, so its gated clock pulses at most every other clock (multicycle 2).
// `word`, `hi` and the pair-phase flags run on a second gated clock (enable = word
// taken or initial load), so the request-dependent enable only reaches a clock-gate
// latch, not a 10-bit mux.
// Start-up: generator primes on clock 1, waits on clock 2, and on clock 3 the first
// pair is loaded and the generator advances; `ready` (valid) rises after clock 3.
// `inject` is a single-clock pulse in the clk domain; it is held pending and applied to
// the next generated pair's word 0.
module pt_pattern_tx #(parameter integer W=10)(
    input  wire         clk,
    input  wire         rst_n,
    input  wire         request,    // consumer takes `word` at this clock edge
    input  wire [2:0]   cfg_mode,   // as pt_pattern_gen; 0 (payload) sends zero here
    input  wire         cfg_invert,
    input  wire [W-1:0] cfg_user,   // sent as every line word in user mode
    input  wire         inject,     // pulse: flip bit 0 of the next generated pair's word 0
    output reg  [W-1:0] word,
    output wire         ready
);
    reg  [1:0]     st;               // 0 prime, 1 wait, 2 load, 3 running
    reg            ph, inj;          // ph: 1 = `word` is the second word of the pair
    reg            rdy, ld, sel_lo;  // decoded flags: running, load state, next word = pair[W-1:0]
    reg  [W-1:0]   hi;
    wire [2*W-1:0] pair;             // generator output: the next pair
    assign ready = rdy;
    wire take    = rdy && request;
    wire adv     = (st == 2'd0) || ld || (take && ph);
    wire wen     = ld || take;       // `word` loads (second clock gate: no enable mux on it)
    wire gclk, wclk;
    pt_clock_gate cg(.clk(clk), .en(adv), .gclk(gclk));
    pt_clock_gate cw(.clk(clk), .en(wen), .gclk(wclk));
    pt_pattern_gen #(.W(2*W)) gen(.clk(gclk), .rst_n(rst_n), .ce(1'b1), .step(1'b1), .cfg_mode(cfg_mode),
        .cfg_invert(cfg_invert), .cfg_user({cfg_user, cfg_user}), .data_in({(2*W){1'b0}}), .inject(inj),
        .word(pair));
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st <= 2'd0; inj <= 1'b0; rdy <= 1'b0; ld <= 1'b0;
        end else begin
            if (st != 2'd3) st <= st + 2'd1;
            ld  <= st == 2'd1;
            if (ld) rdy <= 1'b1;
            if (inject) inj <= 1'b1; else if (adv && st != 2'd0) inj <= 1'b0;
        end
    end
    // Word path on the `wen`-gated clock; its next value depends on flops only.
    always @(posedge wclk or negedge rst_n) begin
        if (!rst_n) begin
            ph <= 1'b0; hi <= {W{1'b0}}; word <= {W{1'b0}}; sel_lo <= 1'b1;
        end else begin
            word   <= sel_lo ? pair[W-1:0] : hi;
            if (sel_lo) hi <= pair[2*W-1:W];
            ph     <= !sel_lo;          // 1 while `word` holds the second word of its pair
            sel_lo <= !sel_lo;
        end
    end
endmodule

// RX gearbox + checker: collects valid 10-bit words into pairs (first word in bits
// [W-1:0]). The pair register d2/v2 and the 20-bit checker run on a clock gated by the
// free-running toggle `t` (every other clock edge). Pairs complete at most every
// other clock, so the single pair register p never overflows. Latency from the second
// word of a pair to the checker: 1 to 3 clocks. `clear` may be a single-clock pulse
// (held pending until the next gated edge) or a level.
module pt_pattern_rx #(parameter integer W=10, parameter integer CW=16)(
    input  wire          clk,
    input  wire          rst_n,
    input  wire          enable,
    input  wire          valid,
    input  wire [W-1:0]  data,
    input  wire [2:0]    cfg_mode,
    input  wire          cfg_invert,
    input  wire          clear,
    output wire          locked,
    output wire          lost_lock,
    output wire [CW-1:0] errors,
    output wire [CW-1:0] errors_gray
);
    reg           t, have0, pfull, v2, clr;
    reg [W-1:0]   w0;
    reg [2*W-1:0] p, d2;
    wire          gclk;
    pt_clock_gate cg(.clk(clk), .en(t), .gclk(gclk));
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            t <= 1'b0; have0 <= 1'b0; pfull <= 1'b0; w0 <= 0; p <= 0; clr <= 1'b0;
        end else begin
            t <= ~t;
            if (valid && have0) begin p <= {data, w0}; have0 <= 1'b0; end
            else if (valid) begin w0 <= data; have0 <= 1'b1; end
            if (valid && have0) pfull <= 1'b1; else if (t) pfull <= 1'b0;
            if (!enable) have0 <= 1'b0;
            if (clear) clr <= 1'b1; else if (t) clr <= 1'b0;
        end
    end
    always @(posedge gclk or negedge rst_n)
        if (!rst_n) begin d2 <= 0; v2 <= 1'b0; end
        else begin d2 <= p; v2 <= pfull; end
    pt_pattern_check #(.W(2*W), .CW(CW)) chk(.clk(gclk), .rst_n(rst_n), .ce(1'b1), .enable(enable), .valid(v2),
        .data(d2), .cfg_mode(cfg_mode), .cfg_invert(cfg_invert), .clear(clear || clr), .locked(locked),
        .lost_lock(lost_lock), .errors(errors), .errors_gray(errors_gray));
endmodule
`default_nettype wire
