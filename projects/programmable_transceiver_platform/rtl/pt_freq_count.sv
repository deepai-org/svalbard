// Generalized frequency counter / lock check (consolidation P3-7), standard cells. Replaces the
// former pt_pll_lock (status.pll_lock is reserved). One instance per debug.freq_count_{a,b} group.
//   * source: 1..6 select one of six clock inputs (tx_ring_fbck, cdr_ring_fbck, ring_osc,
//     vco_replica, aosc, lc_prescale); 0 = off (counter disabled, state cleared). The select is a
//     plain clock mux: it may only change while stopped (update: stopped); any change of the
//     synchronized select is also handled as a disable (state cleared, next window re-primes).
//   * source domain: free-running Gray-coded counter (one bit changes per edge).
//   * reference domain: window = 256/1024/2048/4096 reference cycles; two-flop synchronizer of the
//     Gray count, converted to binary; per window count = edges in the window (mod 2^CW, exact while
//     < 2^CW), diff = count - target. Lock: |diff| <= tolerance for `count` consecutive windows;
//     lost_lock: a window outside tolerance while locked (sticky until source = off). The first window
//     after enable only sets the reference point. `locked_ref` is the reference-domain level (instance b
//     drives the CDR frequency-to-phase handover with it).
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
    output reg  [15:0] count        // SCLK domain, saturating
);
    wire en = cfg_source != 3'd0 && cfg_source <= 3'd6;
    // ---------------- source clock mux and source domain
    wire fb_clk = src[cfg_source == 3'd0 ? 3'd0 : cfg_source - 3'd1] & en;
    wire en_f;
    pt_sync_bit sf(.clk(fb_clk), .rst_n(rst_n), .d(en), .q(en_f));
    reg [CW-1:0] fb_bin, fb_gray;
    always @(posedge fb_clk or negedge rst_n)
        if (!rst_n) begin fb_bin <= 0; fb_gray <= 0; end
        else if (en_f) begin fb_bin <= fb_bin + 1'b1; fb_gray <= (fb_bin + 1'b1) ^ ((fb_bin + 1'b1) >> 1); end
    // ---------------- reference domain
    wire [26:0] cfg_r;
    pt_sync_vec #(27) scr(.clk(ref_clk), .rst_n(rst_n), .d({en, cfg_source, cfg_window, cfg_tol, cfg_count, cfg_target}), .q(cfg_r));
    wire en_r = cfg_r[26];
    reg [2:0] src_q;
    always @(posedge ref_clk or negedge rst_n) if (!rst_n) src_q <= 3'd0; else src_q <= cfg_r[25:23];
    wire run = en_r && src_q == cfg_r[25:23];
    (* async_reg = "true" *) reg [CW-1:0] g1, g2;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin g1 <= 0; g2 <= 0; end else begin g1 <= fb_gray; g2 <= g1; end
    function automatic [CW-1:0] g2b(input [CW-1:0] g);
        integer distance; reg [CW-1:0] prefix;
        begin
            // Parallel prefix conversion bounds depth to ceil(log2(CW)).
            // The serial suffix recurrence became a long physical XOR path
            // from synchronized Gray state to fbq[0] at the 100 MHz reference.
            prefix = g;
            for (distance = 1; distance < CW; distance = distance * 2)
                prefix = prefix ^ (prefix >> distance);
            g2b = prefix;
        end
    endfunction
    wire [1:0] w = cfg_r[22:21];
    wire [12:0] wlen = w == 2'd0 ? 13'd256 : w == 2'd1 ? 13'd1024 : w == 2'd2 ? 13'd2048 : 13'd4096;
    wire [6:0] tol = cfg_r[20:18] == 3'd0 ? 7'd0 : (7'd1 << (cfg_r[20:18] - 3'd1));
    wire [3:0] need = 4'd1 << cfg_r[17:16];
    wire [15:0] target = cfg_r[15:0];
    // Pipelined evaluation (timing): fbq = binary of the synchronized Gray count (registered); at the
    // window end delta_q = fbq - fb_prev is registered and evaluated on the next reference clock.
    reg [12:0] wc; reg [CW-1:0] fb_prev, fbq, delta_q; reg primed, eval; reg [3:0] good; reg r_locked, r_lost;
    reg [13:0] r_diff; reg [15:0] r_count;
    always @(posedge ref_clk or negedge rst_n) if (!rst_n) fbq <= 0; else fbq <= g2b(g2);
    wire in_tol;wire[13:0]d_sat;
    pt_count_metrics #(.CW(CW)) metrics(delta_q,target,tol,in_tol,d_sat);
    wire [15:0] c_sat = |delta_q[CW-1:16] ? 16'hffff : delta_q[15:0];
    assign locked_ref = r_locked;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin
            wc <= 0; fb_prev <= 0; delta_q <= 0; primed <= 1'b0; eval <= 1'b0; good <= 0; r_locked <= 1'b0;
            r_lost <= 1'b0; r_diff <= 0; r_count <= 0;
        end else if (!run) begin
            wc <= 0; primed <= 1'b0; eval <= 1'b0; good <= 0; r_locked <= 1'b0; r_lost <= 1'b0; r_diff <= 0; r_count <= 0;
        end else begin
            eval <= 1'b0;
            if (wc == wlen - 1'b1) begin
                wc <= 0;
                fb_prev <= fbq;
                delta_q <= fbq - fb_prev;
                primed <= 1'b1;
                eval <= primed;
            end else wc <= wc + 1'b1;
            if (eval) begin
                r_diff <= d_sat;
                r_count <= c_sat;
                if (in_tol) begin
                    if (good != need) good <= good + 1'b1;
                    if (good + 1'b1 >= need) r_locked <= 1'b1;
                end else begin
                    good <= 0;
                    if (r_locked) r_lost <= 1'b1;
                    r_locked <= 1'b0;
                end
            end
        end
    // handshake into SCLK: publish whenever the published value differs and no transfer is pending
    reg req; wire ack_r;
    reg [31:0] hold;
    wire [31:0] cur = {r_count, r_lost, r_locked, r_diff};
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin req <= 1'b0; hold <= 32'd0; end
        else if (req == ack_r && hold != cur) begin hold <= cur; req <= ~req; end
    // ---------------- SCLK domain
    wire req_s;
    pt_sync_bit sq(.clk(sclk), .rst_n(rst_n), .d(req), .q(req_s));
    reg ack;
    always @(posedge sclk or negedge rst_n)
        if (!rst_n) begin ack <= 1'b0; locked <= 1'b0; lost_lock <= 1'b0; diff <= 14'd0; count <= 16'd0; end
        else if (req_s != ack) begin ack <= req_s; {count, lost_lock, locked, diff} <= hold; end
    pt_sync_bit sa(.clk(ref_clk), .rst_n(rst_n), .d(ack), .q(ack_r));
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
