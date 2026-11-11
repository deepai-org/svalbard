// 2x halfband TX interpolator (SP-03 / RA-14 / RC-5): the host link carries 40 MS/s I/Q, the DACs
// update at 80 MS/s, so the ZOH image at fs - f is filtered on chip before the BB filter.
//   * halfband = 0 (digital.transport_config.tx_interp = bypass, reset): core_clk = clk_fast and the
//     samples pass through unchanged (combinational), exactly the pre-SP-03 behaviour.
//   * halfband = 1: clk_fast (rf_tx_clk) runs at 80 MHz; core_clk = clk_fast / 2 feeds the transport
//     core's RF TX side and pt_memory playback. Each core sample produces two DAC samples:
//     the sample itself and the halfband midpoint
//         mid = (9 (x1 + x2) - (x0 + x3) + 8) >> 4      (taps -1 0 9 16 9 0 -1, /16)
//     computed in the core domain (25 ns) on the DAC's 10 bits (rf_tx_sample[11:2] I, [23:14] Q;
//     two's complement), saturated, and interleaved at clk_fast. Invalid input cycles shift in zero,
//     so the output decays to the static all-zero bus the DAC sees when no sample is valid.
//   The select is stopped-only (the transport core is held in reset while it can change).
// Registers: 3 x 20 sample history, 2 x 22 pre-sums (x1 + x2 and x0 + x3 one cycle early),
// 20 midpoint, 20 output, 1 divider, 3 valid = 148 flip-flops.
`default_nettype none
module pt_interp2x(
    input  wire        rst_n,
    input  wire        clk_fast,    // rf_tx_clk
    input  wire        halfband,    // quasi-static mode select
    output wire        core_clk,    // clk_fast (bypass) or clk_fast / 2 (halfband)
    input  wire [23:0] in_sample,   // core_clk domain: {Q[11:0], I[11:0]}
    input  wire        in_valid,
    output wire [23:0] out_sample,  // clk_fast domain
    output wire        out_valid
);
    // ---------------- clocking
    reg div;
    always @(posedge clk_fast or negedge rst_n) if (!rst_n) div <= 1'b0; else div <= halfband ? ~div : 1'b0;
    wire half_clk;
    pt_clock_buf half_clock_buf(.I(div), .Z(half_clk));
    pt_clock_mux core_clock_mux(.I0(clk_fast), .I1(half_clk), .S(halfband), .Z(core_clk));
    // ---------------- core-domain FIR (one channel per call of the generate loop)
    wire [19:0] mid;
    reg  [19:0] x0, x1, x2, mid_q;
    reg  [2:0]  v;
    wire [19:0] xin = in_valid ? {in_sample[23:14], in_sample[11:2]} : 20'd0;
    genvar ch;
    generate for (ch = 0; ch < 2; ch = ch + 1) begin : lane
        reg signed [10:0] a, b;     // a = x1 + x2, b = x0 + x3 (registered one cycle early)
        wire signed [9:0] in_c = xin[10*ch +: 10];
        wire signed [9:0] c0 = x0[10*ch +: 10], c1 = x1[10*ch +: 10], c2 = x2[10*ch +: 10];
        always @(posedge core_clk or negedge rst_n)
            if (!rst_n) begin a <= 0; b <= 0; end
            else begin a <= c0 + c1; b <= in_c + c2; end
        // 9a - b + 8 = (a << 3) + a + ~b + 9, reduced by two carry-save levels, one 16-bit add.
        wire [15:0] t0 = {{2{a[10]}}, a, 3'b000}, t1 = {{5{a[10]}}, a}, t2 = ~{{5{b[10]}}, b};
        wire [15:0] s1 = t0 ^ t1 ^ t2;
        wire [15:0] k1 = {((t0 & t1) | (t0 & t2) | (t1 & t2)), 1'b0} & 16'hFFFE;
        wire [15:0] t3 = 16'd9;
        wire [15:0] s2 = s1 ^ k1 ^ t3;
        wire [15:0] k2 = {((s1 & k1) | (s1 & t3) | (k1 & t3)), 1'b0} & 16'hFFFE;
        wire signed [15:0] r = s2 + k2;
        wire signed [11:0] q = r[15:4];
        assign mid[10*ch +: 10] = (q > 12'sd511) ? 10'sd511 : (q < -12'sd512) ? -10'sd512 : q[9:0];
    end endgenerate
    always @(posedge core_clk or negedge rst_n)
        if (!rst_n) begin x0 <= 0; x1 <= 0; x2 <= 0; mid_q <= 0; v <= 0; end
        else begin x0 <= xin; x1 <= x0; x2 <= x1; mid_q <= mid; v <= {v[1:0], in_valid}; end
    // ---------------- clk_fast interleave: div = 1 in the first fast cycle after a core edge
    reg [19:0] y; reg yv;
    always @(posedge clk_fast or negedge rst_n)
        if (!rst_n) begin y <= 0; yv <= 1'b0; end
        else begin y <= div ? mid_q : x2; yv <= v[1] || v[2]; end
    wire [19:0] yo = yv ? y : 20'd0;
    assign out_sample = halfband ? {yo[19:10], 2'b00, yo[9:0], 2'b00} : in_sample;
    assign out_valid  = halfband ? yv : in_valid;
endmodule
`default_nettype wire
