// Generalized frequency counter / lock check (consolidation P3-7), standard cells. Replaces the
// former pt_pll_lock (status.pll_lock is reserved). One instance per debug.freq_count_{a,b} group.
//   * source: 1..6 select one of six clock inputs (tx_ring_fbck, cdr_ring_fbck, ring_osc,
//     vco_replica, aosc, lc_prescale); 0 = off (counter disabled, state cleared). The select is a
//     plain clock mux: it may only change while stopped (update: stopped); any change of the
//     captured select is also handled as a disable (state cleared, next window re-primes).
//   * source domain (timing rework 2026-11-10, CLOSE_R2 fc -10.6 ns at in-window ss): the only logic
//     at the source rate is a 4-flop Johnson counter (no adder; one inverter in its loop). Its MSB is a
//     divide-by-8 clock that steps two Gray counters of the eight-count blocks: ha on its falling edge
//     (block wrap, Johnson code 0) and hb on its rising edge (mid-block, code 4). Their incrementers
//     run at <= 1/8 of the source rate.
//   * reference domain: every bit is two-flop synchronized (Johnson and Gray codes change one bit per
//     step). The edge count is N = 8*k + L with L the decoded Johnson code: ha = k is used while L is
//     in 2..5 (ha last changed >= 2 source periods earlier), hb (= k+1 for L 6..7, = k for L 0..1)
//     otherwise, so the selected block count is never sampled near its own update. A window
//     (256/1024/2048/4096 reference cycles, 13-bit LFSR timer) ends with a snapshot of the selected
//     Gray block count and signed L; FC_EVAL_DELAY reference cycles later the snapshot is converted,
//     differenced against the previous window and compared (pt_count_metrics, formally checked), and
//     the result registers load. Snapshot, fb_prev and the configuration capture are held stable for
//     that whole interval (multicycle path in integration/pt_digital_macro.sdc, checked by
//     sim/tb_pt_freq_count.sv `eval_window`).
//     Lock: |diff| <= tolerance for `count` consecutive windows; lost_lock: a window outside
//     tolerance while locked (sticky until source = off). The first window after enable only sets
//     the reference point. `locked_ref` is the reference-domain level (instance b drives the CDR
//     frequency-to-phase handover with it).
//   * configuration: the SCLK-domain fields are static except at register-file commits; they are
//     captured into the reference domain one cycle after the synchronized commit_toggle changes
//     (bus stable for >= 2 reference edges by then), not synchronized bit by bit.
//   * SCLK domain: req/ack handshake from a held register (no torn reads of the multi-bit values).
`default_nettype none
module pt_freq_count #(parameter integer CW = 18)(
    input  wire        rst_n,
    input  wire [2:0]  cfg_source,  // SCLK-domain, quasi-static
    input  wire [1:0]  cfg_window,  // 0: 256, 1: 1024, 2: 2048, 3: 4096 reference cycles
    input  wire [2:0]  cfg_tol,     // 0,1,2,4,8,16,32,64 counts
    input  wire [1:0]  cfg_count,   // 1,2,4,8 consecutive windows
    input  wire [15:0] cfg_target,  // expected source edges per window
    input  wire [5:0]  src,         // source clocks (code 1..6 -> src[0..5])
    input  wire        ref_clk,
    input  wire        sclk,
    output wire        locked_ref,  // reference domain
    output reg         locked,      // SCLK domain
    output reg         lost_lock,   // SCLK domain
    output reg  [13:0] diff,        // SCLK domain, two's complement, saturated
    output reg  [15:0] count,       // SCLK domain, saturating
    input  wire        commit_toggle // register-file commit toggle (SCLK domain level)
);
    localparam integer HW = CW - 3;           // block-count width
    localparam integer FC_EVAL_DELAY = 6;     // reference cycles from snapshot to result load
    wire en = cfg_source != 3'd0 && cfg_source <= 3'd6;
    // ---------------- source clock mux and source domain
    wire fb_clk = src[cfg_source == 3'd0 ? 3'd0 : cfg_source - 3'd1] & en;
    wire en_f;
    pt_sync_bit sf(.clk(fb_clk), .rst_n(rst_n), .d(en), .q(en_f));
    // Timing (TC6): en_f (x1 synchronizer flop, fanout 4) is re-registered into one kept copy per
    // Johnson flop (fanout 1 each); the counter starts one source cycle later (no effect: the first
    // window after enable only sets the reference point).
    wire [3:0] en_j;
    genvar gj;
    generate for (gj = 0; gj < 4; gj = gj + 1) begin : enrep
        pt_fc_rep r(.clk(fb_clk), .rst_n(rst_n), .d(en_f), .q(en_j[gj]));
    end endgenerate
    wire [3:0] fj;                             // Johnson: 0000,0001,0011,0111,1111,1110,1100,1000
    reg [2:0] fjl;
    always @(posedge fb_clk or negedge rst_n)
        if (!rst_n) fjl <= 3'd0;
        else begin
            if (en_j[0]) fjl[0] <= ~fj[3];
            if (en_j[1]) fjl[1] <= fjl[0];
            if (en_j[2]) fjl[2] <= fjl[1];
        end
    // fj[3] becomes blk_clk: a kept x4 source flop (pt_clock_dff), not a synthesized x1
    pt_clock_dff fjc(.clk(fb_clk), .rst_n(rst_n), .d(en_j[3] ? fjl[2] : fj[3]), .q(fj[3]));
    assign fj[2:0] = fjl;
    wire blk_clk;                              // source / 8; rises entering code 4, falls entering 0
    pt_clock_buf blk_clock_buf(.I(fj[3]), .Z(blk_clk));
    function automatic [CW-1:0] g2b(input [CW-1:0] g);
        integer distance; reg [CW-1:0] prefix;
        begin
            // Parallel prefix conversion bounds depth to ceil(log2(CW)).
            prefix = g;
            for (distance = 1; distance < CW; distance = distance * 2)
                prefix = prefix ^ (prefix >> distance);
            g2b = prefix;
        end
    endfunction
    function automatic [HW-1:0] gray_inc(input [HW-1:0] g);
        reg [CW-1:0] b;
        begin
            b = g2b({{(CW-HW){1'b0}}, g}) + 1'b1;
            gray_inc = b[HW-1:0] ^ (b[HW-1:0] >> 1);
        end
    endfunction
    reg [HW-1:0] ha, hb;                       // Gray block counts
    always @(negedge blk_clk or negedge rst_n) if (!rst_n) ha <= 0; else ha <= gray_inc(ha);
    always @(posedge blk_clk or negedge rst_n) if (!rst_n) hb <= 0; else hb <= gray_inc(hb);
    // ---------------- reference domain: configuration capture on commit
    wire ct_r;
    pt_sync_bit sct(.clk(ref_clk), .rst_n(rst_n), .d(commit_toggle), .q(ct_r));
    reg ct_d, cfg_loaded;
    // Timing (TC6, TC4 ref -3.66 ns: ct_r -> xnor -> cfg_loaded -> 26-flop enable chain): the load
    // decision is a REGISTER, replicated (kept) per group of <= 8 destinations. The capture happens
    // one reference cycle later than before (the bus is stable >= 2 edges before the toggle is seen).
    wire cfg_load_n = !cfg_loaded || ct_r != ct_d;
    wire [3:0] ld;
    genvar gl;
    generate for (gl = 0; gl < 4; gl = gl + 1) begin : ldrep
        pt_fc_rep r(.clk(ref_clk), .rst_n(rst_n), .d(cfg_load_n), .q(ld[gl]));
    end endgenerate
    reg [2:0]  cfg_src_r;                      // source (single-cycle restart path through `run`)
    reg [22:0] cfg_r;                          // {window, tol, count, target} (multicycle into the evaluation)
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin ct_d <= 1'b0; cfg_loaded <= 1'b0; cfg_src_r <= 3'd0; cfg_r <= 23'd0; end
        else begin
            ct_d <= ct_r;
            // After reset the configuration is static (reset defaults) until the first commit, whose
            // toggle is seen here >= 2 reference edges after the bus changed.
            if (ld[0]) begin cfg_src_r <= cfg_source; cfg_loaded <= 1'b1; cfg_r[22:16] <= {cfg_window, cfg_tol, cfg_count}; end
            if (ld[1]) cfg_r[15:10] <= cfg_target[15:10];
            if (ld[2]) cfg_r[9:5]   <= cfg_target[9:5];
            if (ld[3]) cfg_r[4:0]   <= cfg_target[4:0];
        end
    wire [2:0] src_cfg = cfg_src_r;
    wire en_r = cfg_loaded && src_cfg != 3'd0 && src_cfg <= 3'd6;
    reg [2:0] src_q; reg run; (* keep *) reg run_e;   // run_e: replica for the evaluation block (fanout)
    // `run` is registered (timing): a source change or disable clears the state one cycle later.
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin src_q <= 3'd0; run <= 1'b0; run_e <= 1'b0; end
        else begin src_q <= src_cfg; run <= en_r && src_q == src_cfg; run_e <= en_r && src_q == src_cfg; end
    // run_g: kept copy of run_e for the lock-decision registers (TC6 fanout split; identical value)
    wire run_g;
    pt_fc_rep rrun_g(.clk(ref_clk), .rst_n(rst_n), .d(en_r && src_q == src_cfg), .q(run_g));
    // ---------------- reference domain: synchronized source state
    (* async_reg = "true" *) reg [2*HW+3:0] s1, s2;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin s1 <= 0; s2 <= 0; end else begin s1 <= {fj, ha, hb}; s2 <= s1; end
    wire [3:0] js = s2[2*HW+3:2*HW];
    wire [HW-1:0] has = s2[2*HW-1:HW], hbs = s2[HW-1:0];
    reg [3:0] ls; reg use_a;                   // signed L (-2..5) and block-count select
    always @* begin
        use_a = 1'b0;
        case (js)
            4'b0000: ls = 4'd0;   4'b0001: ls = 4'd1;
            4'b0011: begin ls = 4'd2; use_a = 1'b1; end
            4'b0111: begin ls = 4'd3; use_a = 1'b1; end
            4'b1111: begin ls = 4'd4; use_a = 1'b1; end
            4'b1110: begin ls = 4'd5; use_a = 1'b1; end
            4'b1100: ls = 4'b1110;  // 6 - 8
            default: ls = 4'b1111;  // 1000: 7 - 8 (illegal Johnson codes only after an upset)
        endcase
    end
    // ---------------- window timer: 13-bit LFSR (x^13+x^4+x^3+x+1), period = window length
    wire [1:0] w = cfg_r[22:21];
    wire [12:0] seed = w == 2'd0 ? 13'h1388 : w == 2'd1 ? 13'h0018 : w == 2'd2 ? 13'h0099 : 13'h1598;
    reg [12:0] wl; reg tick;
    wire wl_fb = wl[12] ^ wl[3] ^ wl[2] ^ wl[0];
    wire [6:0] tol = cfg_r[20:18] == 3'd0 ? 7'd0 : (7'd1 << (cfg_r[20:18] - 3'd1));
    wire [3:0] need = 4'd1 << cfg_r[17:16];
    wire [15:0] target = cfg_r[15:0];
    // ---------------- snapshot and delayed evaluation
    reg [HW-1:0] snap_h; reg [3:0] snap_l; reg [CW-1:0] fb_prev; reg [2:0] ev_cnt;
    // ev_go: registered evaluation strobe
    reg primed, have_snap, cfg_fresh, ev_go; reg [3:0] good; reg r_locked, r_lost;
    // TC6 timing: the evaluation's decisions are registers computed from next-state values (pm =
    // primed && !cfg_fresh as they will be at the next edge) or from registers that cannot change in
    // the cycle before ev_go (gsat = good + 1 >= need, gne = good != need: good only changes at ev_go,
    // need only with a configuration load, which sets cfg_fresh and suppresses that evaluation).
    reg pm, gsat, gne, evp; reg [3:0] needm1, ginc;   // evp == ev_go && pm; ginc == good + 1   // needm1 = need - 1 (registered configuration)
    reg [13:0] r_diff; reg [15:0] r_count;
    wire [CW-1:0] snap_n = {g2b({{(CW-HW){1'b0}}, snap_h}), 3'b000} + {{(CW-4){snap_l[3]}}, snap_l};
    wire [CW-1:0] delta = snap_n - fb_prev;
    wire in_tol; wire [13:0] d_sat;
    pt_count_metrics #(.CW(CW)) metrics(delta, target, tol, in_tol, d_sat);
    wire [15:0] c_sat = |delta[CW-1:16] ? 16'hffff : delta[15:0];
    assign locked_ref = r_locked;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin
            wl <= 13'h1388; tick <= 1'b0; snap_h <= 0; snap_l <= 0; fb_prev <= 0; ev_cnt <= 0; ev_go <= 1'b0;
            primed <= 1'b0; have_snap <= 1'b0; cfg_fresh <= 1'b0;
            r_diff <= 0; r_count <= 0; pm <= 1'b0; evp <= 1'b0;
        end else if (!run_e) begin pm <= 1'b0; evp <= 1'b0;
            wl <= seed; tick <= 1'b0; ev_cnt <= 0; ev_go <= 1'b0; primed <= 1'b0; have_snap <= 1'b0; cfg_fresh <= 1'b0;
            r_diff <= 0; r_count <= 0;
        end else begin
            tick <= wl == 13'h1FFF;
            pm   <= (ev_go || primed) && !(ld[3] || (!tick && cfg_fresh));
            // evp: ev_go and pm as they will be at the next edge (same expressions, registered once)
            evp  <= (have_snap && !tick && ev_cnt == 3'd2) && (ev_go || primed) && !(ld[3] || (!tick && cfg_fresh));
            wl <= tick ? seed : {wl[11:0], wl_fb};
            // A configuration capture between snapshot and evaluation suppresses that window's metric
            // update (fb_prev still advances), so the target/tolerance/need paths are multicycle too.
            if (ld[3]) cfg_fresh <= 1'b1; else if (tick) cfg_fresh <= 1'b0;   // ld[3] == ld[0] (copies)
            if (tick) begin                    // window end: snapshot the selected block count and L
                snap_h <= use_a ? has : hbs;
                snap_l <= ls;
                have_snap <= 1'b1;
                ev_cnt <= FC_EVAL_DELAY[2:0] - 3'd1;
            end else if (ev_cnt != 3'd0) ev_cnt <= ev_cnt - 1'b1;
            ev_go <= have_snap && !tick && ev_cnt == 3'd2;  // high in the cycle where ev_cnt == 1
            if (ev_go) begin                               // evaluation (multicycle from snapshot)
                fb_prev <= snap_n;
                primed <= 1'b1;
                if (evp) begin                             // == pm (primed && !cfg_fresh) at this ev_go
                    r_diff <= d_sat;
                    r_count <= c_sat;
                end
            end
        end
    // lock decision registers (run_g copy; evp is only ever 1 in an ev_go cycle)
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin good <= 0; r_locked <= 1'b0; r_lost <= 1'b0; gsat <= 1'b0; gne <= 1'b0; needm1 <= 4'd0; ginc <= 4'd1; end
        else if (!run_g) begin good <= 0; r_locked <= 1'b0; r_lost <= 1'b0; gsat <= 1'b0; gne <= 1'b0; needm1 <= need - 4'd1; ginc <= 4'd1; end
        else begin
            ginc <= good + 1'b1;
            needm1 <= need - 4'd1;
            gsat <= good >= needm1; gne <= good != need;      // good + 1 >= need  <=>  good >= need - 1
            if (evp) begin
                if (in_tol) begin
                    if (gne) good <= ginc;
                    if (gsat) r_locked <= 1'b1;
                end else begin
                    good <= 0;
                    if (r_locked) r_lost <= 1'b1;
                    r_locked <= 1'b0;
                end
            end
        end
    // handshake into SCLK: publish after every result update (evaluation or clear) once no transfer is
    // pending. A `dirty` flag replaces the former 32-bit hold != cur compare (reference-clock timing).
    reg req, dirty, upd_d; wire ack_r;   // upd_d: results load at the edge after `upd`
    reg [31:0] hold;
    wire [31:0] cur = {r_count, r_lost, r_locked, r_diff};
    wire upd = !run || ev_go;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin req <= 1'b0; hold <= 32'd0; dirty <= 1'b0; end
        else begin
            if (req == ack_r && dirty) begin hold <= cur; req <= ~req; end
            // set after a result update; cleared when a publish takes the (by then stable) result
            if (upd_d) dirty <= 1'b1; else if (req == ack_r && dirty) dirty <= 1'b0;
        end
    always @(posedge ref_clk or negedge rst_n) if (!rst_n) upd_d <= 1'b0; else upd_d <= upd;

    // ---------------- SCLK domain
    wire req_s;
    pt_sync_bit sq(.clk(sclk), .rst_n(rst_n), .d(req), .q(req_s));
    reg ack;
    always @(posedge sclk or negedge rst_n)
        if (!rst_n) begin ack <= 1'b0; locked <= 1'b0; lost_lock <= 1'b0; diff <= 14'd0; count <= 16'd0; end
        else if (req_s != ack) begin ack <= req_s; {count, lost_lock, locked, diff} <= hold; end
    pt_sync_bit sa(.clk(ref_clk), .rst_n(rst_n), .d(ack), .q(ack_r));
endmodule

// Replicated control flop (fanout split), kept so identical copies are not merged.
`ifndef FORMAL
(* keep_hierarchy = "yes" *)
`endif
module pt_fc_rep(input wire clk, rst_n, d, output reg q);
    always @(posedge clk or negedge rst_n) if (!rst_n) q <= 1'b0; else q <= d;
endmodule

// Compare the observed count against target-relative bounds in parallel.
// This removes the wide subtraction from ahead of both limit decisions;
// only the low fourteen difference bits are needed when no limit is hit.
module pt_count_metrics #(parameter CW=18)(input wire[CW-1:0]value,
 input wire[15:0]target,input wire[6:0]tolerance,
 output wire in_range,output wire[13:0]difference);
 // A seven-bit tolerance crosses at most one boundary between the upper
 // counts. Decode those cases alongside the short low-bit subtraction.
 wire[7:0]low_delta={1'b0,value[6:0]}-{1'b0,target[6:0]};
 wire[6:0]negative_low=-low_delta[6:0];
 wire[CW-8:0]value_high=value[CW-1:7];
 wire[CW-8:0]target_high={{(CW-16){1'b0}},target[15:7]};
 wire same_high=value_high==target_high;
 wire[CW-7:0]raised_target_high={1'b0,target_high}+1'b1;
 wire above_high={1'b0,value_high}==raised_target_high;
 // Widen before incrementing so the largest source count cannot wrap to
 // zero and appear adjacent to a zero target.
 wire[CW-7:0]raised_high={1'b0,value_high}+1'b1;
 wire below_high=raised_high=={1'b0,target_high};
 wire same_range=(low_delta[7]?negative_low:low_delta[6:0])<=tolerance;
 assign in_range=(same_high&&same_range)||
                 (above_high&&low_delta[7]&&low_delta[6:0]<=tolerance)||
                 (below_high&&!low_delta[7]&&(|low_delta[6:0])&&negative_low<=tolerance);
 wire[16:0]sat_low={1'b0,target}-17'd8192;
 wire[16:0]sat_high={1'b0,target}+17'd8191;
 wire[13:0]low_difference=value[13:0]-target[13:0];
 assign difference=value>sat_high?14'h1fff:
                   !sat_low[16]&&value<sat_low[15:0]?14'h2000:low_difference;
`ifdef FORMAL
 wire signed[CW+1:0]reference=$signed({2'b0,value})-$signed({{(CW-14){1'b0}},target});
 wire signed[CW+1:0]signed_tol=$signed({{(CW-5){1'b0}},tolerance});
 wire reference_within=(reference>=-signed_tol)&&(reference<=signed_tol);
 wire[13:0]reference_difference=reference>8191?14'h1fff:reference< -8192?14'h2000:reference[13:0];
 always @*begin
  assert(in_range==reference_within);
  assert(difference==reference_difference);
 end
`endif
endmodule
`default_nettype wire
