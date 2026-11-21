// Reference copy of pt_lc_rx before DG9-LC-RX (alignment decision in the same clock as the hit register),
// modules renamed *_ref, for the lock-step bench sim/tb_lc_rx_retime_equiv.sv (verification/check_linecode.py).
// Simulation only.
`default_nettype none
module pt_lc_rx_ref(input wire clk, rst_n, en, input wire [39:0] din, input wire din_valid,
    output wire [39:0] dout, output wire dout_valid, output reg aligned, code_error);
`include "pt_linecode_tables.svh"
    // en (stopped-only level: linecode && synchronized ENABLE && !payload_iq) is re-registered here
    // before its ~300-flop fanout (AC1_R4: the ENABLE synchronizer e2.q drove it as data, -12 ns).
    // TC13 r4 (wrx, en_r -> ~400 flops was -2.5 ns post-CTS): two kept replicas, one per control group
    // (stage 1 / stages 2-3), and the data-only registers (cur, sym, pb, pa, dec, bad) are no longer
    // gated: they are consumed only behind the valid chain (s1v, v2a, v2b, v2, emit), which the enable
    // still clears, so the delivered stream is unchanged.
    wire en_r, en_r2;
    pt_lc_en_rep_ref rep_r1(.clk(clk), .rst_n(rst_n), .d(en), .q(en_r));
    pt_lc_en_rep_ref rep_r2(.clk(clk), .rst_n(rst_n), .d(en), .q(en_r2));
    reg [39:0] cur;                 // previous input quad
    reg [3:0]  off;                 // adopted bit offset 0..9
    // ---- stage 1: window, comma search, barrel shift by the registered offset
    wire [79:0] wn = {din, cur};
    wire [9:0]  hit_n;
    genvar k, j;
    generate for (k = 0; k < 10; k = k + 1) begin : offsets
        wire [3:0] at;
        for (j = 0; j < 4; j = j + 1) begin : symbols
            assign at[j] = wn[k+10*j +: 10] == 10'b0101111100 || wn[k+10*j +: 10] == 10'b1010000011;
        end
        assign hit_n[k] = |at;
    end endgenerate
    reg [39:0] sym_n;
    always @* case (off)
        4'd0: sym_n = wn[39:0];  4'd1: sym_n = wn[40:1];  4'd2: sym_n = wn[41:2];  4'd3: sym_n = wn[42:3];
        4'd4: sym_n = wn[43:4];  4'd5: sym_n = wn[44:5];  4'd6: sym_n = wn[45:6];  4'd7: sym_n = wn[46:7];
        4'd8: sym_n = wn[47:8];  default: sym_n = wn[48:9];
    endcase
    reg [39:0] sym; reg [9:0] hit; reg s1v, s1ok;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin hit <= 10'd0; s1v <= 1'b0; s1ok <= 1'b0; end
        else if (!en_r) begin s1v <= 1'b0; hit <= 10'd0; end
        else begin
            s1v <= din_valid; s1ok <= aligned;
            if (din_valid) hit <= hit_n;
        end
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin cur <= 40'd0; sym <= 40'd0; end
        else if (din_valid) begin cur <= din; sym <= sym_n; end
    // offset decision on the registered hits (lowest hit offset)
    reg [3:0] hit_off;
    integer h;
    always @* begin hit_off = 4'd0; for (h = 9; h >= 0; h = h - 1) if (hit[h]) hit_off = h[3:0]; end
    reg [3:0] cand; reg cand_v;
    wire adopt = s1v && |hit && (!aligned || hit_off != off) && cand_v && cand == hit_off;
    wire deliver = s1v && s1ok && aligned && !adopt;
    // ---- stage 2: decode four symbols, split in two clocks (timing closure 2026-11-11, wrx at 12.3 ns):
    // 2a registers the per-symbol table lookups (k28, 5b/6b {ok, EDCBA}, K28 3b/4b, 3b/4b, the 4b group),
    // 2b assembles the 9-bit symbols and the error flag. One extra wire_rx_clk of latency; same symbols.
    // Timing 2026-11-11 (wrx, post-synthesis sym -> compare -> c4 mux -> dk table -> pa -3.0 ns): the
    // K28 3b/4b table is looked up on both polarities in parallel and the c6 == 111100 compare only
    // selects (kept 2:1); the Dx.A7/Kx.7 condition parts are decoded here too (kx: the 5b/6b data
    // value is 23/27/29/30, c4k: c4 is 1110 or 0001) so stage 2b is a short select.
    reg [75:0] pa;              // per symbol s: {k28, ok, x[4:0], dk[3:0], d4r[3:0], kx, c4k, 2'b0} at 19*s
    reg [35:0] dec_n; reg bad_n;
    integer s;
    reg [5:0] c6; reg [3:0] c4, d4r; reg [4:0] x; reg k28, ok, kx, c4k;
    reg [75:0] pa_n;
    // Timing TC9 (wrx, sym -> 5b/6b + 3b/4b tables -> pa): one more decode stage. 2a0 registers the raw
    // per-symbol lookups pb (k28, k28p, {ok, x}, dk on both polarities, d4r, c4k); 2a1 selects dk by k28p
    // and decodes kx into pa. One more wire_rx_clk of latency; same symbols.
    reg [83:0] pb, pb_n;        // per symbol s at 21*s: {k28, k28p, ok, x[4:0], dkp[3:0], dkn[3:0], d4r[3:0], c4k}
    wire [3:0] k28p_n;
    genvar sk;
    generate for (sk = 0; sk < 4; sk = sk + 1) begin : dkp
        pt_lc_is_k28p_ref eq(.a(sym[10*sk +: 6]), .z(k28p_n[sk]));
    end endgenerate
    always @* begin
        for (s = 0; s < 4; s = s + 1) begin
            c6 = sym[10*s +: 6]; c4 = sym[10*s+6 +: 4];
            k28 = c6 == 6'b111100 || c6 == 6'b000011;
            {ok, x} = lc_d6(c6);
            c4k = c4 == 4'b1110 || c4 == 4'b0001;
            d4r = lc_d4(c4);
            pb_n[21*s +: 21] = {k28, k28p_n[s], ok, x, lc_dk4(c4), lc_dk4(~c4), d4r, c4k};
        end
    end
    reg [3:0] ad4r, adkp, adkn; reg [4:0] ax; reg ak28, ak28p, aok, ac4k; integer sa;
    always @* begin
        for (sa = 0; sa < 4; sa = sa + 1) begin
            {ak28, ak28p, aok, ax, adkp, adkn, ad4r, ac4k} = pb[21*sa +: 21];
            pa_n[19*sa +: 19] = {ak28, aok, ax, ak28p ? adkp : adkn, ad4r,
                                 ax == 5'd23 || ax == 5'd27 || ax == 5'd29 || ax == 5'd30, ac4k, 2'b00};
        end
    end
    // (separate variables: two always @* blocks sharing temporaries retrigger each other forever)
    reg [3:0] bd4r, bdk; reg [4:0] bx; reg [1:0] bpad; reg bk28, bkk, bok, bkx, bc4k; integer t;
    always @* begin
        bad_n = 1'b0;
        for (t = 0; t < 4; t = t + 1) begin
            {bk28, bok, bx, bdk, bd4r, bkx, bc4k, bpad} = pa[19*t +: 19]; bkk = 1'b0;
            if (bk28) begin
                dec_n[9*t +: 9] = bdk[3] ? {1'b1, bdk[2:0], 5'd28} : 9'h100;
                bad_n = bad_n | !bdk[3];
            end else if (!bok || !bd4r[3]) begin
                dec_n[9*t +: 9] = 9'h100; bad_n = 1'b1;
            end else begin
                bkk = bc4k && bkx;
                dec_n[9*t +: 9] = {bkk, bd4r[2:0], bx};
            end
        end
    end
    reg v2a, v2b;
    reg [35:0] dec; reg bad, v2;
    // ---- stage 3: 36 -> 40 repacking. After this clock's emit the reservoir holds 4k bits
    // (k = 0..9, one-hot `koh`); a delivered group is inserted at bit 4k. Next state:
    // delivered and k >= 1: emit next clock, k-1; delivered and k = 0: k = 9; else unchanged.
    reg [71:0] R; reg [9:0] koh; reg emit;
    wire [71:0] kept = emit ? {40'd0, R[71:40]} : R;
    reg [71:0] ins;
    integer q;
    always @* begin
        ins = 72'd0;
        for (q = 0; q < 10; q = q + 1) if (koh[q]) ins = ins | ({36'd0, dec} << (4*q));
    end
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            R <= 72'd0; koh <= 10'd1; emit <= 1'b0; off <= 4'd0; aligned <= 1'b0; code_error <= 1'b0; cand <= 4'd0; cand_v <= 1'b0;
            v2 <= 1'b0; v2a <= 1'b0; v2b <= 1'b0;
        end else if (!en_r2) begin R <= 72'd0; koh <= 10'd1; emit <= 1'b0; aligned <= 1'b0; cand_v <= 1'b0; v2 <= 1'b0; v2a <= 1'b0; v2b <= 1'b0; end
        else begin
            if (adopt) begin off <= hit_off; aligned <= 1'b1; cand_v <= 1'b0; end
            else if (s1v && |hit && aligned && hit_off == off) cand_v <= 1'b0;
            else if (s1v && |hit) begin cand <= hit_off; cand_v <= 1'b1; end
            v2a <= deliver; v2b <= v2a; v2 <= v2b;
            R <= kept | (v2 ? ins : 72'd0);
            emit <= v2 && !koh[0];
            if (v2) koh <= {koh[0], koh[9:1]};   // k -> k-1, 0 -> 9
            if (v2 && bad) code_error <= 1'b1;
        end
    // data-only pipeline registers (see en_r above): consumed only in the clocks after a delivery
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin dec <= 36'd0; bad <= 1'b0; pa <= 76'd0; pb <= 84'd0; end
        else begin pb <= pb_n; pa <= pa_n; dec <= dec_n; bad <= bad_n; end
    assign dout = R[39:0];
    assign dout_valid = emit;
endmodule
module pt_lc_en_rep_ref(input wire clk, rst_n, d, output reg q);
    always @(posedge clk or negedge rst_n) if (!rst_n) q <= 1'b0; else q <= d;
endmodule
module pt_lc_is_k28p_ref(input wire [5:0] a, output wire z);   // a == 6'b111100
    assign z = a == 6'b111100;
endmodule
`default_nettype wire
