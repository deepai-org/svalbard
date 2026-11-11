// IX-2 optional on-chip 8b/10b line-code offload at the wired boundary (interface-changes IX-2,
// WR-HL-LINECODE). With `en` (linecode, stopped-only) the host link carries decoded 9-bit symbols
// {K, HGFEDCBA} packed LSB-first into the ten-bit word stream (0.9 x line rate: 3.125 Gb/s needs
// 2.81 Gb/s of the 2.88 Gb/s framed host capacity), so 3.0/3.125 Gb/s wired rates fit the AC-1 link.
// Bit order as the transport: bit 0 of a ten-bit code group is `a` (first on the line). Reference
// model and code tables: verification/linecode_8b10b.py; check: verification/check_linecode.py.
`default_nettype none

// RX (wire_rx_clk): K28.5 (0011111010 / 1100000101, both disparities, full code group) alignment over
// all ten bit offsets of the 40-bit quad stream; a new offset is adopted only when two consecutive
// K28.5 events agree on it (a single false comma, e.g. after K28.7, cannot misalign the link);
// four parallel 10b->9b decoders, 36 -> 40 repacking. Invalid code groups decode to {K=1, 0x00}
// (not a valid control character) and, once aligned, set the sticky `code_error`. Running
// disparity is not checked (protocol checks belong to the FPGA).
// Pipeline (five quad clocks; decode split in three, 2026-11-11 / TC9): (1) the window {din, previous quad} is barrel-shifted by the
// registered offset and searched for commas; (2) decode; (3) repack. The quad whose commas change
// the offset was shifted with the old one and is not delivered.
module pt_lc_rx(input wire clk, rst_n, en, input wire [39:0] din, input wire din_valid,
    output wire [39:0] dout, output wire dout_valid, output reg aligned, code_error);
`include "pt_linecode_tables.svh"
    // en (stopped-only level: linecode && synchronized ENABLE && !payload_iq) is re-registered here
    // before its ~300-flop fanout (AC1_R4: the ENABLE synchronizer e2.q drove it as data, -12 ns).
    reg en_r;
    always @(posedge clk or negedge rst_n) if (!rst_n) en_r <= 1'b0; else en_r <= en;
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
        if (!rst_n) begin cur <= 40'd0; sym <= 40'd0; hit <= 10'd0; s1v <= 1'b0; s1ok <= 1'b0; end
        else if (!en_r) begin s1v <= 1'b0; hit <= 10'd0; end
        else begin
            s1v <= din_valid; s1ok <= aligned;
            if (din_valid) begin cur <= din; sym <= sym_n; hit <= hit_n; end
        end
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
        pt_lc_is_k28p eq(.a(sym[10*sk +: 6]), .z(k28p_n[sk]));
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
            dec <= 36'd0; bad <= 1'b0; v2 <= 1'b0; v2a <= 1'b0; v2b <= 1'b0; pa <= 76'd0; pb <= 84'd0;
        end else if (!en_r) begin R <= 72'd0; koh <= 10'd1; emit <= 1'b0; aligned <= 1'b0; cand_v <= 1'b0; v2 <= 1'b0; v2a <= 1'b0; v2b <= 1'b0; end
        else begin
            if (adopt) begin off <= hit_off; aligned <= 1'b1; cand_v <= 1'b0; end
            else if (s1v && |hit && aligned && hit_off == off) cand_v <= 1'b0;
            else if (s1v && |hit) begin cand <= hit_off; cand_v <= 1'b1; end
            v2a <= deliver; v2b <= v2a; v2 <= v2b; bad <= bad_n;
            pb <= pb_n; pa <= pa_n;     // unconditional: consumed only in the clocks after a delivery (v2a, v2)
            dec <= dec_n;
            R <= kept | (v2 ? ins : 72'd0);
            emit <= v2 && !koh[0];
            if (v2) koh <= {koh[0], koh[9:1]};   // k -> k-1, 0 -> 9
            if (v2 && bad) code_error <= 1'b1;
        end
    assign dout = R[39:0];
    assign dout_valid = emit;
endmodule

// TX (wire_tx_clk): 40 -> 36 unpacking of the egress head (FWFT), then two stages: (A) the 36-bit
// group is taken with the running disparity at each of its four symbols (a code group's disparity
// class does not depend on the disparity it is encoded with, so RD before symbol s is
// rd ^ u_0 ^ .. ^ u_(s-1), from cheap per-symbol flags); (B) four independent 9b->10b encoders.
// The encoded quad q is a registered FWFT head: `take` consumes it.
// Kept enable replica (identical copies must not be merged by synthesis).
`ifndef FORMAL
(* keep_hierarchy = "yes" *)
`endif
module pt_lc_en_rep(input wire clk, rst_n, d, output reg q);
    always @(posedge clk or negedge rst_n) if (!rst_n) q <= 1'b0; else q <= d;
endmodule

`ifndef FORMAL
(* keep_hierarchy = "yes" *)
`endif
module pt_lc_sel1(input wire s, a, b, output wire z);
    assign z = s ? b : a;
endmodule
// W-bit wrapper (flattened) of kept 1-bit selects: a parameterized kept module would survive
// synthesis as a $paramod instance, which the flow counts as an unmapped cell.
module pt_lc_sel2 #(parameter integer W=1)(input wire s, input wire [W-1:0] a, b, output wire [W-1:0] z);
    genvar i;
    generate for (i = 0; i < W; i = i + 1) begin : b_
        pt_lc_sel1 m(.s(s), .a(a[i]), .b(b[i]), .z(z[i]));
    end endgenerate
endmodule

`ifndef FORMAL
(* keep_hierarchy = "yes" *)
`endif
module pt_lc_is_k28p(input wire [5:0] a, output wire z);   // a == 6'b111100
    assign z = a == 6'b111100;
endmodule

module pt_lc_tx(input wire clk, rst_n, en, input wire [39:0] head, input wire head_valid,
    output wire pop, output reg [39:0] q, output reg q_valid, input wire take);
`include "pt_linecode_tables.svh"
    // 5b/6b sub-block unbalanced (D.00-02/04/08/15/16/23/24/27/29-31, K28); 3b/4b: x.0, x.4, x.7
    function automatic u6_of(input [8:0] v);
        case (v[4:0])
            5'd0, 5'd1, 5'd2, 5'd4, 5'd8, 5'd15, 5'd16, 5'd23, 5'd24, 5'd27, 5'd29, 5'd30, 5'd31: u6_of = 1'b1;
            default: u6_of = v[8] && v[4:0] == 5'd28;
        endcase
    endfunction
    function automatic flip_of(input [8:0] v);
        flip_of = u6_of(v) ^ (v[7:5] == 3'd0 || v[7:5] == 3'd4 || v[7:5] == 3'd7);
    endfunction
    // one group for a given RD (rn = RD-): the RD after the 6b block is rn ^ u6 (no popcount)
    function automatic [9:0] lc_enc2(input [8:0] v, input rn);
        reg k28, r1, a7;
        begin
            k28 = v[8] && v[4:0] == 5'd28;
            r1 = rn ^ u6_of(v);
            a7 = v[7:5] == 3'd7 && (v[8] || (r1 && (v[4:0] == 5'd17 || v[4:0] == 5'd18 || v[4:0] == 5'd20)) ||
                                    (!r1 && (v[4:0] == 5'd11 || v[4:0] == 5'd13 || v[4:0] == 5'd14)));
            lc_enc2 = {lc_e4(v[7:5], k28, a7, r1), lc_e6(v[4:0], k28, rn)};
        end
    endfunction
    // stage-B encoder with the symbol decodes (u6, K28, A7 sets) precomputed in stage A
    function automatic [9:0] lc_enc3(input [8:0] v, input rn, input u6, input k28, input s1, input s2);
        reg r1, a7;
        begin
            r1 = rn ^ u6;
            a7 = v[7:5] == 3'd7 && (v[8] || (r1 && s1) || (!r1 && s2));
            lc_enc3 = {lc_e4(v[7:5], k28, a7, r1), lc_e6(v[4:0], k28, rn)};
        end
    endfunction
    function automatic [3:0] dec_of(input [8:0] v);   // {s2, s1, k28, u6}
        dec_of = {v[4:0] == 5'd11 || v[4:0] == 5'd13 || v[4:0] == 5'd14,
                  v[4:0] == 5'd17 || v[4:0] == 5'd18 || v[4:0] == 5'd20,
                  v[8] && v[4:0] == 5'd28, u6_of(v)};
    endfunction
    // ---- unpack: reservoir ures holds u bits (multiple of 4, <= 72)
    reg [71:0] ures; reg [6:0] u;
    reg [35:0] sA; reg [3:0] rdA; reg sAv; reg rdn; reg [15:0] dA;   // rdn: RD- at the end of the groups taken so far
    // Encoded output: a two-entry queue (q = registered FWFT head, q2 behind it). Stage B advances
    // whenever the second slot is free, so advB / advA / pop are functions of registers only and the
    // consumer's late `take` steers just the 40-bit head reload (AC1_R4: take -> advB -> advA -> pop
    // -> one-hot flags was 16 levels, wtx -8.1 ns). The output stream is unchanged.
    reg [39:0] q2; reg qv2;
    wire advB = sAv && !qv2;
    // Stage P (timing TC9, wtx: ures -> flip / decode -> running-disparity XOR -> rdA / dA was the
    // worst wtx path): the group taken from ures is registered with its per-symbol flip flags and
    // decodes (sP / fP / dP); stage A then only XORs the registered flags into the running disparity.
    // One more WORD_CLK40 of latency, full throughput, the encoded stream is unchanged.
    reg [35:0] sP; reg [3:0] fP; reg [15:0] dP; reg sPv;
    wire advP2A = sPv && (!sAv || advB);
    // u-derived flags and one-hot insert positions are registers (computed from the next u), so no
    // compare on u sits in front of the 72-bit insert fanout (AC-1 ss32 timing at 12.3 ns).
    reg uge36, ult72; reg [8:0] oh_n, oh_a;   // oh_n[i]: u == 4i; oh_a[i]: u == 4i + 36
    wire advA = uge36 && (!sPv || advP2A);   // ures -> stage P
    // en (the synchronized ENABLE & linecode) is re-registered in three kept copies, one per register
    // group (timing 2026-11-11, wtx: e3.q -> en -> ~300 flops was -4.5 ns); every group sees the same
    // one-clock-later enable, so the stream is unchanged (it starts one WORD_CLK40 later).
    wire en_a, en_b, en_c;
    pt_lc_en_rep rep_a(.clk(clk), .rst_n(rst_n), .d(en), .q(en_a));
    pt_lc_en_rep rep_b(.clk(clk), .rst_n(rst_n), .d(en), .q(en_b));
    pt_lc_en_rep rep_c(.clk(clk), .rst_n(rst_n), .d(en), .q(en_c));
    // Input skid buffer (timing TC9, wtx: egress empty -> pop -> 72-bit insert / u adders through a long
    // buffer tree was -4.0 ns mid-PnR in TC8): the egress head enters a two-entry queue (hq = head entry,
    // hq1 behind it; hv / hf = one / two entries, registers). The egress take (pop) is head_valid && !hf,
    // registers only, and the wide insert fanout sees pop_i, a function of lc_tx registers only.
    // Full throughput; the symbol stream is unchanged (one or two WORD_CLK40 more latency).
    reg [39:0] hq, hq1; reg hv, hf;
    wire pop_i = en_a && hv && (advA ? ult72 : !uge36);
    assign pop = en_a && head_valid && !hf;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin hv <= 1'b0; hf <= 1'b0; hq <= 40'd0; hq1 <= 40'd0; end
        else if (!en_a) begin hv <= 1'b0; hf <= 1'b0; end
        else case ({pop_i, pop})
            2'b01: begin if (!hv) hq <= head; else hq1 <= head; hf <= hv; hv <= 1'b1; end
            2'b10: begin hq <= hq1; hv <= hf; hf <= 1'b0; end
            2'b11: begin if (hf) begin hq <= hq1; hq1 <= head; end else hq <= head; end
            default: ;
        endcase
    wire [6:0] u_p0, u_p1, u_next;   // u - 36 advA + 40 pop, alternatives from u only
    pt_lc_sel2 #(7) su_p0(.s(pop_i), .a(u), .b(u + 7'd40), .z(u_p0));
    pt_lc_sel2 #(7) su_p1(.s(pop_i), .a(u - 7'd36), .b(u + 7'd4), .z(u_p1));
    pt_lc_sel2 #(7) su_a (.s(advA), .a(u_p0), .b(u_p1), .z(u_next));
    // next flags for each of the four (advA, pop) cases, from registers only; the late advA / pop
    // only select (kept nets: synthesis must not fold the select back into the adders)
    function automatic [19:0] flags_of(input [6:0] v);
        integer m; begin
            flags_of[19] = v >= 7'd36; flags_of[18] = v < 7'd72;
            for (m = 0; m < 9; m = m + 1) begin flags_of[9+m] = v == 7'(4*m); flags_of[m] = v == 7'(4*m + 36); end
        end
    endfunction
    (* keep *) wire [19:0] fl_00 = flags_of(u), fl_01 = flags_of(u + 7'd40),
                           fl_10 = flags_of(u - 7'd36), fl_11 = flags_of(u + 7'd4);
    // the late advA / pop select through kept-hierarchy 2:1s (plain case/?: let synthesis share the
    // four adders/compares into one behind a u mux: post-synthesis egress_wtx sAv -> ... -> u adder)
    wire [19:0] fl_p0, fl_p1, fl_sel;
    pt_lc_sel2 #(20) s_p0(.s(pop_i), .a(fl_00), .b(fl_01), .z(fl_p0));
    pt_lc_sel2 #(20) s_p1(.s(pop_i), .a(fl_10), .b(fl_11), .z(fl_p1));
    pt_lc_sel2 #(20) s_a (.s(advA), .a(fl_p0), .b(fl_p1), .z(fl_sel));
    wire [71:0] kept = advA ? {36'd0, ures[71:36]} : ures;
    reg [71:0] ins_a, ins_n;   // head inserted at u - 36 (after advA) or at u
    integer i;
    always @* begin
        ins_a = 72'd0; ins_n = 72'd0;
        for (i = 0; i < 9; i = i + 1) begin
            ins_a = ins_a | ({72{oh_a[i]}} & ({32'd0, hq} << (4*i)));
            ins_n = ins_n | ({72{oh_n[i]}} & ({32'd0, hq} << (4*i)));
        end
    end
    // stage A: per-symbol running disparity from the flags
    wire [3:0] f = {flip_of(ures[35:27]), flip_of(ures[26:18]), flip_of(ures[17:9]), flip_of(ures[8:0])};
    wire [3:0] r_at = {rdn ^ fP[0] ^ fP[1] ^ fP[2], rdn ^ fP[0] ^ fP[1], rdn ^ fP[0], rdn};
    // stage B: four independent encoders
    // TC11 (wtx, sA -> encoder -> q -0.21 ns mid-PnR): the 3b/4b disparity r1 and the A7 decision are
    // registered in stage A (r1A / a7A, from the registered running disparity and decodes), so stage B is
    // the two table lookups only. Same code groups.
    reg [3:0] r1A, a7A;
    wire [3:0] r1_n, a7_n;
    genvar ga;
    generate for (ga = 0; ga < 4; ga = ga + 1) begin : a7p
        assign r1_n[ga] = r_at[ga] ^ dP[4*ga];
        assign a7_n[ga] = sP[9*ga+7 -: 3] == 3'd7 && (sP[9*ga+8] || (r1_n[ga] && dP[4*ga+2]) || (!r1_n[ga] && dP[4*ga+3]));
    end endgenerate
    function automatic [9:0] lc_enc4(input [8:0] v, input rn, input k28, input r1, input a7);
        lc_enc4 = {lc_e4(v[7:5], k28, a7, r1), lc_e6(v[4:0], k28, rn)};
    endfunction
    wire [39:0] enc = {lc_enc4(sA[35:27], rdA[3], dA[13], r1A[3], a7A[3]),
                       lc_enc4(sA[26:18], rdA[2], dA[9], r1A[2], a7A[2]),
                       lc_enc4(sA[17:9], rdA[1], dA[5], r1A[1], a7A[1]),
                       lc_enc4(sA[8:0], rdA[0], dA[1], r1A[0], a7A[0])};
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin ures <= 72'd0; u <= 7'd0; uge36 <= 1'b0; ult72 <= 1'b1; oh_n <= 9'd1; oh_a <= 9'd0; end
        else if (!en_a) begin ures <= 72'd0; u <= 7'd0; uge36 <= 1'b0; ult72 <= 1'b1; oh_n <= 9'd1; oh_a <= 9'd0; end
        else begin
            ures <= kept | (pop_i ? (advA ? ins_a : ins_n) : 72'd0);
            u <= u_next;
            {uge36, ult72, oh_n, oh_a} <= fl_sel;
        end
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin sA <= 36'd0; dA <= 16'd0; rdA <= 4'b1111; sAv <= 1'b0; rdn <= 1'b1;
            sP <= 36'd0; fP <= 4'd0; dP <= 16'd0; sPv <= 1'b0; r1A <= 4'd0; a7A <= 4'd0; end
        else if (!en_b) begin sAv <= 1'b0; rdn <= 1'b1; sPv <= 1'b0; end
        else begin
            if (advA) begin sP <= ures[35:0]; fP <= f;
                dP <= {dec_of(ures[35:27]), dec_of(ures[26:18]), dec_of(ures[17:9]), dec_of(ures[8:0])}; end
            sPv <= advA || (sPv && !advP2A);
            if (advP2A) begin sA <= sP; rdA <= r_at; rdn <= rdn ^ (^fP); dA <= dP; r1A <= r1_n; a7A <= a7_n; end
            sAv <= advP2A || (sAv && !advB);
        end
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin q <= 40'd0; q_valid <= 1'b0; q2 <= 40'd0; qv2 <= 1'b0; end
        else if (!en_c) begin q_valid <= 1'b0; qv2 <= 1'b0; end
        else begin
            if (q_valid && take) begin          // head consumed: second entry or the new group moves up
                if (qv2) q <= q2; else if (advB) q <= enc;
                q_valid <= qv2 || advB; qv2 <= 1'b0;
            end else if (!q_valid) begin        // (qv2 is 0 here)
                if (advB) q <= enc;
                q_valid <= advB;
            end else if (advB) begin            // head held, second slot free
                q2 <= enc; qv2 <= 1'b1;
            end
        end
endmodule
`default_nettype wire
