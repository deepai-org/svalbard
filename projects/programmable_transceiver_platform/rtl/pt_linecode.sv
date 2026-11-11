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
// Pipeline (three quad clocks): (1) the window {din, previous quad} is barrel-shifted by the
// registered offset and searched for commas; (2) decode; (3) repack. The quad whose commas change
// the offset was shifted with the old one and is not delivered.
module pt_lc_rx(input wire clk, rst_n, en, input wire [39:0] din, input wire din_valid,
    output wire [39:0] dout, output wire dout_valid, output reg aligned, code_error);
`include "pt_linecode_tables.svh"
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
        else if (!en) begin s1v <= 1'b0; hit <= 10'd0; end
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
    // ---- stage 2: decode four symbols
    reg [35:0] dec_n; reg bad_n;
    integer s;
    reg [5:0] c6; reg [3:0] c4, d4r, dk; reg [4:0] x; reg k28, kk, ok;
    always @* begin
        bad_n = 1'b0;
        for (s = 0; s < 4; s = s + 1) begin
            c6 = sym[10*s +: 6]; c4 = sym[10*s+6 +: 4]; kk = 1'b0;
            k28 = c6 == 6'b111100 || c6 == 6'b000011;
            {ok, x} = lc_d6(c6);
            dk = lc_dk4(c6 == 6'b111100 ? c4 : ~c4);
            d4r = lc_d4(c4);
            if (k28) begin
                dec_n[9*s +: 9] = dk[3] ? {1'b1, dk[2:0], 5'd28} : 9'h100;
                bad_n = bad_n | !dk[3];
            end else if (!ok || !d4r[3]) begin
                dec_n[9*s +: 9] = 9'h100; bad_n = 1'b1;
            end else begin
                kk = (c4 == 4'b1110 || c4 == 4'b0001) && (x == 5'd23 || x == 5'd27 || x == 5'd29 || x == 5'd30);
                dec_n[9*s +: 9] = {kk, d4r[2:0], x};
            end
        end
    end
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
            dec <= 36'd0; bad <= 1'b0; v2 <= 1'b0;
        end else if (!en) begin R <= 72'd0; koh <= 10'd1; emit <= 1'b0; aligned <= 1'b0; cand_v <= 1'b0; v2 <= 1'b0; end
        else begin
            if (adopt) begin off <= hit_off; aligned <= 1'b1; cand_v <= 1'b0; end
            else if (s1v && |hit && aligned && hit_off == off) cand_v <= 1'b0;
            else if (s1v && |hit) begin cand <= hit_off; cand_v <= 1'b1; end
            v2 <= deliver; bad <= bad_n;
            if (deliver) dec <= dec_n;
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
    wire advB = sAv && (!q_valid || take);
    // u-derived flags and one-hot insert positions are registers (computed from the next u), so no
    // compare on u sits in front of the 72-bit insert fanout (AC-1 ss32 timing at 12.3 ns).
    reg uge36, ult72; reg [8:0] oh_n, oh_a;   // oh_n[i]: u == 4i; oh_a[i]: u == 4i + 36
    wire advA = uge36 && (!sAv || advB);
    assign pop = en && head_valid && (advA ? ult72 : !uge36);
    wire [6:0] u_next = u - (advA ? 7'd36 : 7'd0) + (pop ? 7'd40 : 7'd0);
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
    wire [71:0] kept = advA ? {36'd0, ures[71:36]} : ures;
    reg [71:0] ins_a, ins_n;   // head inserted at u - 36 (after advA) or at u
    integer i;
    always @* begin
        ins_a = 72'd0; ins_n = 72'd0;
        for (i = 0; i < 9; i = i + 1) begin
            ins_a = ins_a | ({72{oh_a[i]}} & ({32'd0, head} << (4*i)));
            ins_n = ins_n | ({72{oh_n[i]}} & ({32'd0, head} << (4*i)));
        end
    end
    // stage A: per-symbol running disparity from the flags
    wire [3:0] f = {flip_of(ures[35:27]), flip_of(ures[26:18]), flip_of(ures[17:9]), flip_of(ures[8:0])};
    wire [3:0] r_at = {rdn ^ f[0] ^ f[1] ^ f[2], rdn ^ f[0] ^ f[1], rdn ^ f[0], rdn};
    // stage B: four independent encoders
    wire [39:0] enc = {lc_enc3(sA[35:27], rdA[3], dA[12], dA[13], dA[14], dA[15]),
                       lc_enc3(sA[26:18], rdA[2], dA[8], dA[9], dA[10], dA[11]),
                       lc_enc3(sA[17:9], rdA[1], dA[4], dA[5], dA[6], dA[7]),
                       lc_enc3(sA[8:0], rdA[0], dA[0], dA[1], dA[2], dA[3])};
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin ures <= 72'd0; u <= 7'd0; uge36 <= 1'b0; ult72 <= 1'b1; oh_n <= 9'd1; oh_a <= 9'd0; sA <= 36'd0; dA <= 16'd0; rdA <= 4'b1111; sAv <= 1'b0; rdn <= 1'b1; q <= 40'd0; q_valid <= 1'b0; end
        else if (!en) begin ures <= 72'd0; u <= 7'd0; uge36 <= 1'b0; ult72 <= 1'b1; oh_n <= 9'd1; oh_a <= 9'd0; sAv <= 1'b0; rdn <= 1'b1; q_valid <= 1'b0; end
        else begin
            ures <= kept | (pop ? (advA ? ins_a : ins_n) : 72'd0);
            u <= u_next;
            case ({advA, pop})
                2'b00: {uge36, ult72, oh_n, oh_a} <= fl_00;
                2'b01: {uge36, ult72, oh_n, oh_a} <= fl_01;
                2'b10: {uge36, ult72, oh_n, oh_a} <= fl_10;
                default: {uge36, ult72, oh_n, oh_a} <= fl_11;
            endcase
            if (advA) begin sA <= ures[35:0]; rdA <= r_at; rdn <= rdn ^ (^f);
                dA <= {dec_of(ures[35:27]), dec_of(ures[26:18]), dec_of(ures[17:9]), dec_of(ures[8:0])}; end
            sAv <= advA || (sAv && !advB);
            if (advB) q <= enc;
            q_valid <= advB || (q_valid && !take);
        end
endmodule
`default_nettype wire
