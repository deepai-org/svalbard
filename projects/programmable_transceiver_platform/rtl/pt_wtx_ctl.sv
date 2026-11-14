// Wired-TX launch / enable control for the REAL published cells (replaces the serializer model in
// pt_clocktree_slow: MW-15/16/17, D-CT, D-TMDS, D-PLLEN, WT25/26/28/30, TOP-17). Drives the "wired transmit"
// ports and the TX-ring rows of integration/top/ctl_ports.txt:
//   pll_tx (pt_pll_ring_core) EN / N4 / N8 / BAND, pt_wiredtx SER_EN / MODE_H / MODE_F, core_bias EN_wiredtx,
//   tx interlock REQ_MAIN / REQ_POST / REQ_DETECT / REQ_TERM, pt_wtx_fallback_control raw latch inputs,
//   and the transport's wire_tx_request (no analog producer: D-VALID, WT25(6)).
//
// Order (bring-up; reverse at shutdown).  Times: see the localparams / parameters below.
//   1. c_pll_tx_en  = ring_l.enable & island_on[pll] & vreg_tx_ok   (combinational; pt_vreg_seq is upstream)
//   2. tx_ring_ready: ring enabled for (lock_time + 1) * 64 REF cycles, or the FBCK frequency flag, or override
//   3. c_wiredtx_ser_en                      (serializer /5 and /2 dividers released; WORD_CLK40 starts)
//   4. FLUSH_WORDS (8) WORD_CLK40 periods    (WT25(5): the first 4 words are not guaranteed on the line)
//   5. pad branch requests through pt_tx_pad_sequence (PRE blank, POST, ready dwell)
//   6. wire_tx_request = 1 (wire_tx_clk domain): the transport may send payload
//   shutdown: wire_tx_request = 0 -> 8 WORD_CLK40 periods (drain) -> pad requests off -> OFF_CYCLES ->
//   SER_EN = 0.  The ring enable is the register field: software clears it after st_state reads 0.
// Immediate (asynchronous) forcing, no clock needed: fault or wired island off -> every pad request and the
// bias enable low; fault, wired island off, ring disabled (c_pll_tx_en = 0) or debug.wtx_ext -> SER_EN low;
// pll island off -> c_pll_tx_en low. The state machine then aborts to OFF and starts again from step 2.
// Fallback (WT28 / D-TMDS): branch == 2 & debug.wtx_ext & state == active & !idle requests MAIN (and POST)
// combinationally, so the external-data route works with REF_CLK missing and the pll island off.
// Word alignment: every SER_EN rise releases the serializer's own dividers at an arbitrary phase (WT25(2),
// first WORD_CLK40 period may be short). The macro's word boundary is whatever WORD_CLK40 (wire_tx_clk)
// says after the rise; nothing aligns it to REF_CLK, a marker or another chip (WT25(7)).
//
// Config inputs are SCLK-domain register levels ("static": change only while the consumer is stopped, except
// the state / idle / branch / wtx_ext / ring enable requests, which are the commands this block sequences).
// They are decoded to single bits, two-flop synchronized to REF_CLK and accepted only after three equal
// samples, so a multi-bit field change is taken as one event. REF_CLK domain; the three flops that make
// wire_tx_request are in the wire_tx_clk domain and are cleared asynchronously whenever SER_EN is low
// (wire_tx_clk is stopped then).
`default_nettype none
module pt_wtx_ctl #(
    parameter integer REF_PS              = 20000, // REF_CLK period (ps) for the PD40 bound checks in pt_tx_pad_sequence
    parameter integer PAD_PRE_CYCLES      = 2,     // old request held, traffic already off (interlock blanking >= 4 ns)
    parameter integer PAD_POST_CYCLES     = 8,     // request applied -> first readiness sample
    parameter integer PAD_LOAD_CYCLES     = 42,    // contiguous ready samples before traffic (PD40 >= 100 ns)
    parameter integer PAD_TIMEOUT_CYCLES  = 100,   // request applied -> traffic, else sequencer fault (PD40 >= 400 ns)
    parameter integer OFF_CYCLES          = 16     // pad requests low -> SER_EN low
)(
    input  wire       rst_n,
    input  wire       ref_clk,            // reference (the ring's REF); all timers count it
    input  wire       wire_tx_clk,        // pt_wiredtx WORD_CLK40 through the wired iso clamp; stopped while SER_EN = 0
    // levels from the macro
    input  wire       island_on_wired,    // island_on[0] (including wired_on_ext)
    input  wire       island_on_pll,      // island_on[2]
    input  wire       vreg_tx_ok,         // pt_vreg_seq.tx_ok
    input  wire       fault,              // forces every TX pad request off
    input  wire       fc_tx_in_tol,       // frequency counter on fc_src[0] (pll_tx.FBCK) in tolerance (pt_freq_count locked_ref)
    input  wire       txpad_ready,        // termination-buffer readiness (used only while TERM is requested); tie 1 if no detector
    // register fields
    input  wire       cfg_ring_en,        // ring_l.enable
    input  wire [1:0] cfg_ring_n,         // ring_l.n: 0 /16, 1 /8, 2 /4, 3 reserved (= /16)
    input  wire       cfg_ring_band,      // ring_l.band (reset 1)
    input  wire [7:0] cfg_ring_lock_time, // ring_l.lock_time: (code + 1) * 64 REF cycles
    input  wire [1:0] cfg_ring_ready_sel, // 0 timer, 1 timer OR frequency flag, 2 frequency flag only, 3 override (ready while enabled)
    input  wire [1:0] cfg_wtx_state,      // wiredtx.state.state (2 = active)
    input  wire [1:0] cfg_rate_mode,      // consolidation.wiredtx_stage.rate_mode: 0 x1, 1 x2, 2 x4, 3 reserved (= x1)
    input  wire [1:0] cfg_branch,         // txpad.config.branch: 0 off, 1 serial, 2 tmds, 3 detect
    input  wire       cfg_idle,           // wiredtx.idle.idle (reset 1)
    input  wire       cfg_wtx_ext,        // debug.wtx_ext.enable
    input  wire       cfg_post_pol,       // wiredtx.config.post_polarity
    input  wire [7:0] cfg_post_code,      // wiredtx.config.postcursor_code
    input  wire       cfg_term_req,       // new field: TX termination request
    input  wire       cfg_stage_tmds,     // consolidation.wiredtx_stage.stage
    // TX ring
    output wire       c_pll_tx_en, c_pll_tx_n4, c_pll_tx_n8, c_pll_tx_band,
    // serializer
    output wire       c_wiredtx_ser_en, c_wiredtx_mode_h, c_wiredtx_mode_f, c_wiredtx_bias_en,
    // interlock requests
    output wire       c_txpad_req_main, c_txpad_req_post, c_txpad_req_detect, c_txpad_req_term,
    // fallback control cell, raw
    output wire [1:0] c_wtxfb_branch, c_wtxfb_state,
    output wire       c_wtxfb_idle, c_wtxfb_stage_tmds,
    // to the transport (wire_tx_clk domain)
    output wire       wire_tx_request,    // 1: serializer running, flushed, MAIN branch live: a word is taken every WORD_CLK40
    output wire       wire_tx_up,         // 1: serializer running for >= FLUSH_WORDS word clocks (word clock valid)
    // status (ref_clk domain)
    output wire       tx_ring_ready,
    output wire [2:0] st_state,           // 0 off, 1 flush, 2 pad, 3 run, 4 drain, 5 pad-off
    output wire       st_seq_fault        // pt_tx_pad_sequence fault (ready timeout / ready lost); cleared by the next request change
);
    localparam [7:0] DRAIN_TIMEOUT = 8'd255;   // REF cycles; drain normally ends on the word-clock handshake

    // ------------------------------------------------------------------ pure decodes (static levels)
    wire d_act  = cfg_wtx_state == 2'd2;
    wire d_bser = cfg_branch == 2'd1 || cfg_branch == 2'd2;   // MAIN carries serial and (since X5) TMDS
    wire d_bdet = cfg_branch == 2'd3;
    wire d_pnz  = cfg_post_code != 8'd0 || cfg_post_pol;
    assign c_pll_tx_en      = cfg_ring_en & island_on_pll & vreg_tx_ok;
    assign c_pll_tx_n4      = cfg_ring_n == 2'd2;
    assign c_pll_tx_n8      = cfg_ring_n == 2'd1;
    assign c_pll_tx_band    = cfg_ring_band;
    assign c_wiredtx_mode_h = cfg_rate_mode == 2'd1;
    assign c_wiredtx_mode_f = cfg_rate_mode == 2'd2;
    assign c_wtxfb_branch   = cfg_branch;
    assign c_wtxfb_state    = cfg_wtx_state;
    assign c_wtxfb_idle     = cfg_idle;
    assign c_wtxfb_stage_tmds = cfg_stage_tmds;

    // ------------------------------------------------------------------ synchronizers, 3-sample filter
    localparam integer NV = 10;
    wire [NV-1:0] v_in = {txpad_ready, cfg_term_req, d_pnz, d_bdet, d_bser, cfg_idle, fault, island_on_wired, cfg_wtx_ext, d_act};
    wire [NV-1:0] v_s;
    genvar gi;
    generate for (gi = 0; gi < NV; gi = gi + 1) begin : g_sync
        pt_sync_bit s(.clk(ref_clk), .rst_n(rst_n), .d(v_in[gi]), .q(v_s[gi]));
    end endgenerate
    wire ron_s, fq_s, idle8_s;
    wire w_idle8;
    // Ring enable and "serializer may run" as reset synchronizers (async clear, two REF edges to release): a low
    // pulse shorter than a REF period is still seen, restarts the lock timer and aborts the launch.
    wire ring_arst_n = rst_n & c_pll_tx_en;
    wire ser_arst_n  = rst_n & c_pll_tx_en & island_on_wired & ~cfg_wtx_ext & ~fault;
    pt_sync_bit s_ron(.clk(ref_clk), .rst_n(ring_arst_n), .d(1'b1), .q(ron_s));
    wire ok_s;
    pt_sync_bit s_ok (.clk(ref_clk), .rst_n(ser_arst_n), .d(1'b1), .q(ok_s));
    pt_sync_bit s_fq (.clk(ref_clk), .rst_n(rst_n), .d(fc_tx_in_tol), .q(fq_s));
    pt_sync_bit s_i8 (.clk(ref_clk), .rst_n(rst_n), .d(w_idle8), .q(idle8_s));
    reg [NV-1:0] v_q, v_q2, f;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin v_q <= {NV{1'b0}}; v_q2 <= {NV{1'b0}}; f <= {NV{1'b0}}; end
        else begin
            v_q <= v_s; v_q2 <= v_q;
            if (v_s == v_q && v_q == v_q2) f <= v_q2;
        end
    wire f_act = f[0], f_ext = f[1], f_won = f[2], f_fault = f[3], f_idle = f[4], f_bser = f[5], f_bdet = f[6],
         f_pnz = f[7], f_term = f[8], f_rdy = f[9];

    // ------------------------------------------------------------------ tx_ring_ready
    // (lock_time + 1) * 64 REF cycles after the synchronized ring enable. Split 6 + 8 bits (no long carry chain).
    reg [5:0] lt_pre; reg lt_tick, lt_done, fq_arm, ring_rdy;
    reg lt_eq;   // lt_cnt == cfg_ring_lock_time, registered (r7 timing): lt_cnt moves only at a tick, 64 cycles before the next use
    reg [7:0] lt_cnt;
    wire fq_ok = fq_arm & fq_s;   // the flag must have been seen low since the ring was enabled (no stale flag)
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin lt_pre <= 6'd0; lt_tick <= 1'b0; lt_cnt <= 8'd0; lt_done <= 1'b0; fq_arm <= 1'b0; ring_rdy <= 1'b0; lt_eq <= 1'b0; end
        else if (!ron_s) begin lt_pre <= 6'd0; lt_tick <= 1'b0; lt_cnt <= 8'd0; lt_done <= 1'b0; fq_arm <= 1'b0; ring_rdy <= 1'b0; lt_eq <= 1'b0; end
        else begin
            lt_pre <= lt_pre + 6'd1; lt_tick <= lt_pre == 6'd62;
            lt_eq <= lt_cnt == cfg_ring_lock_time;
            if (lt_tick && !lt_done) begin
                if (lt_eq) lt_done <= 1'b1; else lt_cnt <= lt_cnt + 8'd1;
            end
            if (!fq_s) fq_arm <= 1'b1;
            case (cfg_ring_ready_sel)
                2'd0: ring_rdy <= lt_done;
                2'd1: ring_rdy <= lt_done | fq_ok;
                2'd2: ring_rdy <= fq_ok;
                default: ring_rdy <= 1'b1;
            endcase
        end
    assign tx_ring_ready = ring_rdy;

    // ------------------------------------------------------------------ pad requests: pt_tx_pad_sequence
    localparam [2:0] S_OFF = 3'd0, S_FLUSH = 3'd1, S_PAD = 3'd2, S_RUN = 3'd3, S_DRAIN = 3'd4, S_PADOFF = 3'd5;
    reg [2:0] state;
    wire pad_go = state == S_PAD || state == S_RUN || state == S_DRAIN;
    wire hold   = state == S_RUN || state == S_DRAIN;        // no pad change while payload may be on the line
    wire on_ok  = f_won & ~f_fault;
    // MAIN: serializer path needs the serializer up (pad_go); the external-data path (wtx_ext) does not.
    // branch == detect does not request MAIN (interlock conflict DETECT/MAIN, DETECT/TERM).
    wire w_main = f_act & f_bser & ~f_idle & (f_ext | pad_go) & on_ok;
    wire [4:0] want = {f_term & ~f_bdet & on_ok, f_bdet & on_ok, 1'b0, w_main & f_pnz, w_main};   // TERM DETECT TMDS POST MAIN
    reg  [4:0] want_r, committed;
    wire [4:0] seq_active;
    wire seq_cmd_ready, seq_traffic_ready, seq_fault, seq_qualified, seq_buffer_request;
    wire commit = seq_cmd_ready && !hold && want_r != committed;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin want_r <= 5'd0; committed <= 5'd0; end
        else begin want_r <= want; if (commit) committed <= want_r; end
    pt_tx_pad_sequence #(.PRE_CYCLES(PAD_PRE_CYCLES), .POST_CYCLES(PAD_POST_CYCLES), .LOAD_CYCLES(PAD_LOAD_CYCLES),
        .CLK_PS(REF_PS), .READY_TIMEOUT_CYCLES(PAD_TIMEOUT_CYCLES)) pad_seq(
        .clk(ref_clk), .rst_n(rst_n), .supply_ok(1'b1), .commit(commit), .request(want_r),
        .analog_ready(seq_active[4] ? f_rdy : 1'b1),   // as the pads replay (transmit_sequence_connected.py)
        .command_ready(seq_cmd_ready), .active_request(seq_active), .qualified(seq_qualified),
        .traffic_ready(seq_traffic_ready), .buffer_request(seq_buffer_request), .fault(seq_fault));
    assign st_seq_fault = seq_fault;
    wire pad_live = seq_traffic_ready && seq_active[0] && committed[0] && want_r == committed;
    wire pad_down = seq_cmd_ready && !seq_active[0] && !committed[0] && !want_r[0];

    // ------------------------------------------------------------------ launch state machine
    wire go    = f_act & ~f_ext & on_ok & ring_rdy;
    wire abort = f_fault | ~f_won | ~ron_s | f_ext | ~ok_s;
    reg ser_q, de_q, acked;
    reg [7:0] tmr;
    reg [2:0] state_n;
    always @* begin
        state_n = state;
        case (state)
            S_OFF:    if (go) state_n = S_FLUSH;
            S_FLUSH:  if (!go) state_n = S_OFF; else if (idle8_s) state_n = S_PAD;
            S_PAD:    if (!go) state_n = S_PADOFF; else if (pad_live) state_n = S_RUN;
            S_RUN:    if (!go || !pad_live) state_n = S_DRAIN;
            S_DRAIN:  if ((acked && idle8_s) || tmr == DRAIN_TIMEOUT) state_n = go ? S_PAD : S_PADOFF;
            S_PADOFF: if (pad_down && tmr == OFF_CYCLES - 1) state_n = S_OFF;
            default:  state_n = S_OFF;
        endcase
        if (abort) state_n = S_OFF;
    end
    // ser_q / de_q: dedicated flops (glitch-free levels), cleared asynchronously by the forcing terms so that
    // SER_EN cannot come back by itself after a short force pulse.
    always @(posedge ref_clk or negedge ser_arst_n)
        if (!ser_arst_n) begin ser_q <= 1'b0; de_q <= 1'b0; end
        else begin ser_q <= state_n != S_OFF; de_q <= state_n == S_RUN; end
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin state <= S_OFF; acked <= 1'b0; tmr <= 8'd0; end
        else begin
            state <= state_n;
            // acked: the wire_tx_clk domain has seen the data enable (its idle counter was cleared)
            if (state == S_RUN || state == S_DRAIN) begin if (!idle8_s) acked <= 1'b1; end else acked <= 1'b0;
            if (state == S_DRAIN) tmr <= tmr + 8'd1;
            else if (state == S_PADOFF && pad_down) tmr <= tmr + 8'd1;
            else tmr <= 8'd0;
        end
    assign st_state = state;

    // ------------------------------------------------------------------ pin equations
    wire gate_w = island_on_wired & ~fault;
    wire fb_req = cfg_branch == 2'd2 && cfg_wtx_ext && d_act && !cfg_idle;   // WT28 fallback request, no clock
    assign c_txpad_req_main   = (seq_active[0] | fb_req) & gate_w;
    assign c_txpad_req_post   = (seq_active[1] | (fb_req & d_pnz)) & gate_w;
    assign c_txpad_req_detect = seq_active[3] & gate_w;
    assign c_txpad_req_term   = seq_active[4] & gate_w;
    assign c_wiredtx_bias_en  = c_txpad_req_main | c_txpad_req_post | c_txpad_req_detect | c_txpad_req_term;
    assign c_wiredtx_ser_en   = ser_q & island_on_wired & c_pll_tx_en & ~cfg_wtx_ext;

    // ------------------------------------------------------------------ wire_tx_clk domain
    // Cleared asynchronously while SER_EN is low (the clock is stopped then); released by two WORD_CLK40 edges.
    wire w_rst_n;   // kept gate: the SDC cuts timing through w_rst_gate.ag/Z (release re-timed by w_rel / s_de)
    pt_async_gate w_rst_gate(.a(rst_n), .b(c_wiredtx_ser_en), .y(w_rst_n));
    reg [1:0] w_rel;
    reg [3:0] w_cnt;      // word clocks since release (or since the data enable fell) with no payload, saturating at 8
    reg w_req, w_up;
    wire w_de;
    pt_sync_bit s_de(.clk(wire_tx_clk), .rst_n(w_rst_n), .d(de_q), .q(w_de));
`ifndef SYNTHESIS
    // Simulation only: w_rst_n = rst_n & SER_EN is 0 from time zero when reset is asserted from time zero, so an
    // edge-sensitive model never sees the reset edge. On silicon the level clears the flops.
    initial begin w_rel = 2'd0; w_cnt = 4'd0; w_req = 1'b0; w_up = 1'b0; end
`endif
    always @(posedge wire_tx_clk or negedge w_rst_n)
        if (!w_rst_n) begin w_rel <= 2'd0; w_cnt <= 4'd0; w_req <= 1'b0; w_up <= 1'b0; end
        else begin
            w_rel <= {w_rel[0], 1'b1};
            if (!w_rel[1] || w_de) w_cnt <= 4'd0; else if (!w_cnt[3]) w_cnt <= w_cnt + 4'd1;
            w_req <= w_de & w_rel[1] & w_up;
            if (w_cnt[3]) w_up <= 1'b1;
        end
    assign w_idle8 = w_cnt[3];
    assign wire_tx_request = w_req;
    assign wire_tx_up = w_up;
endmodule
`default_nettype wire
