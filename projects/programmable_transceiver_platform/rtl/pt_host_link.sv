// Host GPIO link logic (hostio, digital half), AC-1 pad-edge architecture
// (spec/interface-architecture-changes.md AC-1). The provider gf180mcu_fd_io
// pad cells (integration/pt_chip.sv pt_host_physical) own ESD, level, drive,
// slew and the PAD->Y receiver; everything clocked lives here, inside
// pt_digital_macro, in two small pad-edge regions.
//
// Clocking (transport rework 2026-11-10, in-window ss Liberty). In the
// characterized ss_032C_3v15 library a dffrnq_1 has 1.86 ns clk->Q and
// 0.84 ns setup, so no logic can run at 312.5 MHz with margin, and a
// half-cycle path at 156.25 MHz has <= 10 %. Hence:
//   * the macro receives the host DDR clock directly (host_word_clk input =
//     line/16, 156.25 MHz at 2.5 Gb/s; one ten-bit word per pin per EDGE);
//     pt_host_rate_clock selects /1 /2 /4 of it: link_clk (hddr).
//   hddr               D2H DDR launch + 4:1 gearbox (south region).
//   hcore = hddr/2     78.125 MHz: the 40-bit transport core (core_clk).
//   h2d_clk            forwarded H2D pin clock (DDR, = hddr rate): capture,
//                      1:4 gearbox, write side of the H2D quad FIFO (north).
//   * data never crosses between the rising and falling halves of a clock in
//     half a period: falling-edge registers take their data from registers
//     held for two periods (1.5-period multicycle, proven formally in
//     verification/formal/pt_d2h_gearbox_fv.sv / pt_h2d_gearbox_fv.sv). The
//     only half-period paths are one direct flop -> flop phase copy per four
//     to ten bits (no logic) and reset release into falling-edge flops, which
//     the design tolerates in either of the two possible edges.
//
// Word order on the pins is chronological; quad word 0 (earliest) is [9:0].
//
// D2H. The core hands one quad per hcore clock. A hcore register stores the
// running XOR prefix P_k = w_0 ^ ... ^ w_k of the word stream (P0..P3 of each
// quad, carried across quads). The pad pin is q_r ^ q_f where q_r (hddr
// rising) and q_f (hddr falling) hold consecutive prefixes, so each pin
// changes exactly once per word, by one flop toggling: no clock-as-data mux,
// no glitch and no logic in the fast flops' output paths.
// Forwarded D2H_CLK (DDR, modes 0): the same structure carrying 1,0,1,0:
// c_r toggles on every hddr rising edge and c_f copies it on the falling
// edge, so the pin is an hddr-rate clock whose edges are produced exactly like
// the data edges (EDGE-ALIGNED, like a DDR DQS; the FPGA centres it by its
// input delay / phase training, spec/fpga-host-screen.md "phase training").
// SDR (modes 1, 2): the inverted word clock (2 x hddr), gated glitch-free;
// it exists only at the reduced rates (div2 / div4), because the full-rate
// word clock would be 312.5 MHz, above the pad's f_max.
//
// H2D. Rising- and falling-edge capture on h2d_clk (DDR) or rising only
// (SDR); words are assembled into quads in the pin-clock domain and cross to
// hcore through an eight-quad Gray-pointer FIFO whose write enables are
// registered one clock ahead and replicated. The FPGA derives H2D from D2H, so
// the clocks are mesochronous and the FIFO absorbs phase only. The quad phase
// of the word stream is arbitrary; the transport receiver acquires all four
// word rotations. The receive path is NOT reset by ENABLE (the receiver must
// be armed before the peer's training prefix). Reset: D2H OE 0, data and
// forwarded clock 0.
`default_nettype none
module pt_host_link(
    input  wire        rst_n,
    input  wire [1:0]  mode,          // debug.host_link.mode: 0 DDR, 1 SDR, 2 SDR reduced
    input  wire        d2h_enable,    // hostio.controls.d2h_enable (SCLK domain, quasi-static)
    input  wire        h2d_clk,
    input  wire [9:0]  h2d_pin,
    input  wire        link_clk,      // hddr: host DDR clock after the reduced-rate select
    input  wire        word_clk,      // 2 x hddr word clock (SDR forwarded clock; reduced rates only)
    output wire        core_clk,      // hcore = hddr/2
    output wire        core_rst_n,    // rst_n released synchronously to hcore
    output wire [39:0] h2d_quad,      // core_clk domain register, one quad per clock (0 = idle/underflow)
    input  wire [39:0] d2h_quad,      // core_clk domain register
    output wire [9:0]  d2h_pin,
    output wire        d2h_clk_pin,
    input  wire        d2h_stagger,   // hostio.controls.d2h_stagger (HB-1, quasi-static): odd lanes late
    output wire        d2h_oe,
    output wire        h2d_overflow, h2d_underflow
);
    // ---------------- hddr-domain reset release, then the hcore divider. The
    // divider and the gearbox load phases leave reset on the same hddr edge.
    (* async_reg = "true" *) reg [1:0] drs;
    always @(posedge link_clk or negedge rst_n) if (!rst_n) drs <= 2'b00; else drs <= {drs[0], 1'b1};
    wire dr_n = drs[1];
    // The divider gets its own copy of the release flop (same edge as drs[1]): its recovery check at
    // 6.4 ns no longer rides on dr_n's gearbox fanout (run TC2A: -4.2 ns, divider RN).
    wire drs_c;   // kept copy (pt_rep_dff) so synthesis cannot merge it back into drs[1]
    pt_rep_dff drs_copy(.clk(link_clk), .rst_n(rst_n), .d(drs[0]), .q(drs_c));
    // TC11 (hddr, dr_n -> ~100 gearbox reset pins was the hddr recovery worst group): the gearbox's rising-
    // and falling-edge reset nets get their own kept release copies (same edge as drs[1]).
    wire drs_g, drs_ng;
    pt_rep_dff drs_gcopy(.clk(link_clk), .rst_n(rst_n), .d(drs[0]), .q(drs_g));
    pt_rep_dff drs_ngcopy(.clk(link_clk), .rst_n(rst_n), .d(drs[0]), .q(drs_ng));
    pt_host_divider divider(.clk(link_clk), .rst_n(drs_c), .core_clk(core_clk));
    (* async_reg = "true" *) reg [1:0] crs;
    always @(posedge core_clk or negedge rst_n) if (!rst_n) crs <= 2'b00; else crs <= {crs[0], 1'b1};
    assign core_rst_n = crs[1];

    // ---------------- D2H, core domain: enable gate and XOR prefix
    wire en_c;
    pt_sync_vec #(1) sen(.clk(core_clk), .rst_n(core_rst_n), .d(d2h_enable), .q(en_c));
    wire [39:0] w = en_c ? d2h_quad : 40'd0;
    reg  [39:0] prefix;
    wire [9:0]  carry = prefix[39:30];
    wire [9:0]  p0 = carry ^ w[9:0];
    wire [9:0]  p1 = carry ^ (w[9:0] ^ w[19:10]);
    wire [9:0]  p2 = (carry ^ w[9:0]) ^ (w[19:10] ^ w[29:20]);
    wire [9:0]  p3 = (carry ^ w[9:0]) ^ (w[19:10] ^ (w[29:20] ^ w[39:30]));
    always @(posedge core_clk or negedge core_rst_n)
        if (!core_rst_n) prefix <= 40'd0; else prefix <= {p3, p2, p1, p0};

    // ---------------- D2H, hddr domain: 4:1 gearbox, DDR launch, forwarded clock
    wire [1:0] mode_d; wire en_d;
    pt_sync_vec #(3) smd(.clk(link_clk), .rst_n(dr_n), .d({mode, d2h_enable}), .q({mode_d, en_d}));
    wire ddr_fwd; wire [9:0] d2h_launch;
    pt_d2h_gearbox gearbox(.ddr_clk(link_clk), .rst_n(drs_g), .nrst_n(drs_ng), .prefix(prefix), .clk_en(en_d && mode_d == 2'd0),
        .d2h_pin(d2h_launch), .clk_pin(ddr_fwd));
    // HB-1: two-group launch stagger (SSN). Odd lanes go through a fixed ~0.4-0.8 ns delay when
    // d2h_stagger=1; the even lanes and the forwarded clock are the early group. The FPGA per-bit
    // input delay absorbs the offset. Every lane passes one kept mux, so both groups match otherwise.
    genvar gl;
    generate for (gl = 0; gl < 10; gl = gl + 1) begin : stagger
        wire hio_z;
        pt_stagger lane(.I(d2h_launch[gl]), .S(d2h_stagger && (gl % 2 == 1)), .Z(hio_z));
`ifdef SYNTHESIS
        (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__buf_8 hio_ob(.I(hio_z), .Z(d2h_pin[gl]));
`else
        assign d2h_pin[gl] = hio_z;
`endif
    end endgenerate
    // SDR forwarded clock: inverted word clock, enable registered on its rising edge (the AND
    // output is low then, so it cannot glitch).
    reg en_sdr;
    always @(posedge word_clk or negedge rst_n)
        if (!rst_n) en_sdr <= 1'b0; else en_sdr <= en_d && mode_d != 2'd0;
    reg sdr_sel;   // quasi-static: mode changes only while stopped
    always @(posedge link_clk or negedge dr_n) if (!dr_n) sdr_sel <= 1'b0; else sdr_sel <= mode_d != 2'd0;
    wire hio_cz;
    pt_out_mux clk_out(.I0(ddr_fwd), .I1(~word_clk & en_sdr), .S(sdr_sel), .Z(hio_cz));
`ifdef SYNTHESIS
    (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__buf_8 hio_cob(.I(hio_cz), .Z(d2h_clk_pin));
`else
    assign d2h_clk_pin = hio_cz;
`endif
    assign d2h_oe = d2h_enable;

    // ---------------- H2D
    pt_h2d_gearbox h2d(.rst_n(rst_n), .mode(mode), .h2d_clk(h2d_clk), .h2d_pin(h2d_pin),
        .core_clk(core_clk), .core_rst_n(core_rst_n), .quad(h2d_quad), .overflow(h2d_overflow), .underflow(h2d_underflow));
endmodule

// hcore divider: one hddr toggle flop behind a kept root buffer (STA: generated clock hcore =
// hddr/2 at the buffer output). The first hddr edge after reset is an hcore rising edge.
module pt_host_divider(input wire clk, rst_n, output wire core_clk);
    wire c;
    pt_clock_dff cdiv(.clk(clk), .rst_n(rst_n), .d(~c), .q(c));
    pt_clock_buf core_root(.I(c), .Z(core_clk));
endmodule

// Local load-phase drivers: one flop per group of output bits, preserved across synthesis so the
// phase net never becomes one high-fanout tree. `load` is 1 before every hcore rising edge.
`ifndef FORMAL
(* keep_hierarchy = "yes" *)
`endif
module pt_ddr_phase(input wire clk, rst_n, output reg load);
    always @(posedge clk or negedge rst_n)
        if (!rst_n) load <= 1'b1; else load <= ~load;
endmodule

// Falling-edge phase copy: lp (rising, no reset, no logic before it except the reset gate) is
// sampled by the falling-edge flop nsel half a period later. This direct flop -> flop transfer is
// the only half-period path of a DDR group (no logic). nsel is 1 on the falling edges where the
// two-period data register `x` must be taken, 0 where the held copy is taken. After reset nsel is
// 0 and lp is 0 for one period; every register it selects between is still 0 then.
`ifndef FORMAL
(* keep_hierarchy = "yes" *)
`endif
module pt_ddr_nphase(input wire clk, rst_n, run, phase, output reg nsel);
    reg lp;
    always @(posedge clk) lp <= phase & run;
    always @(negedge clk or negedge rst_n) if (!rst_n) nsel <= 1'b0; else nsel <= lp;
endmodule

// Replicated control flop (write-enable fanout split), preserved across
// synthesis so identical copies are not merged.
`ifndef FORMAL
(* keep_hierarchy = "yes" *)
`endif
module pt_rep_dff(input wire clk, rst_n, d, output reg q);
    always @(posedge clk or negedge rst_n) if (!rst_n) q <= 1'b0; else q <= d;
endmodule


// D2H 4:1 gearbox + DDR launch (hddr domain). After reset the first hddr edge is an hcore edge
// (pt_host_divider) and `load` is 1 exactly before hcore edges (edge k below):
//   rise k   (load): x <= prefix quad P0..P3 (hcore register, unchanged for two hddr periods:
//                    2-period multicycle); q_r <= x.P2 of the previous quad
//   fall k+.5      : q_f <= f3   (P3 of the previous quad, held since rise k-1: 1.5 periods)
//   rise k+1       : q_r <= x.P0; f3 <= x.P3
//   fall k+1.5     : q_f <= x.P1 (x held since rise k: 1.5 periods)
// so the pin q_r ^ q_f steps P3'^P2', P0^P3', P1^P0, P2^P1, P3^P2, ... one word per hddr edge.
// The falling flops only ever take a register that has been stable for 1.5 periods (the other mux
// input changed half a period before, but is not selected): SDC multicycle 2 from x/f3 to q_f.
// Forwarded clock: c_r toggles on rising edges while enabled, c_f takes c_r on the falling edge
// (a direct phase copy, as pt_ddr_nphase), clk_pin = c_r ^ c_f: 1 after rising, 0 after falling.
module pt_d2h_gearbox(input wire ddr_clk, rst_n, nrst_n, input wire [39:0] prefix, input wire clk_en,
    output wire [9:0] d2h_pin, output wire clk_pin);
    // One load / nsel phase-flop pair per pin bit (timing 2026-11-11: per-2-bit groups had fanout 12
    // on `load`, TC4 hddr +0.004 ns against a 0.64 ns target).
    wire [9:0] load, nsel;
    reg run;   // 0 until the first hddr edge after reset
    always @(posedge ddr_clk or negedge rst_n) if (!rst_n) run <= 1'b0; else run <= 1'b1;
    genvar g;
    generate for (g = 0; g < 10; g = g + 1) begin : phases
        pt_ddr_phase phase(.clk(ddr_clk), .rst_n(rst_n), .load(load[g]));
        pt_ddr_nphase nphase(.clk(ddr_clk), .rst_n(nrst_n), .run(run), .phase(load[g]), .nsel(nsel[g]));
    end endgenerate
    reg [39:0] x;
    reg [9:0]  f3;
    integer b;
    always @(posedge ddr_clk or negedge rst_n)
        if (!rst_n) begin x <= 40'd0; f3 <= 10'd0; end
        else for (b = 0; b < 10; b = b + 1) begin
            if (load[b]) begin
                x[b] <= prefix[b]; x[b+10] <= prefix[b+10]; x[b+20] <= prefix[b+20]; x[b+30] <= prefix[b+30];
            end else f3[b] <= x[b+30];
        end
    // Launch stage (TC13): the rising (lr = q_r) and falling (lf = q_f) launch flops and the pin xor are
    // the hand-placed pt_hio_launch cells; only their D inputs are computed here.
    //   q_r <= load ? x.P2 : x.P0 (rising); q_f <= nsel ? x.P1 : f3 (falling)
    // nrst_n = rst_n in the macro; a separate port only so that formal can release the
    // falling-edge flops one falling edge late (the untimed half-period recovery case).
    wire [9:0] qr_d, qf_d;
    genvar gq;
    generate for (gq = 0; gq < 10; gq = gq + 1) begin : lq
        assign qr_d[gq] = load[gq] ? x[gq+20] : x[gq];
        assign qf_d[gq] = nsel[gq] ? x[gq+10] : f3[gq];
        pt_hio_launch l(.clk(ddr_clk), .rst_n(rst_n), .nrst_n(nrst_n), .dr(qr_d[gq]), .df(qf_d[gq]), .z(d2h_pin[gq]));
    end endgenerate
`ifdef FORMAL
    // 1.5-period multicycle into the falling flops (SDC: x/f3 -> q_f): on every falling edge the
    // selected register did not change on the rising edge half a period before.
    reg [39:0] f_xd; reg [9:0] f_f3d; reg [2:0] f_rises;
    always @(posedge ddr_clk) begin f_xd <= x; f_f3d <= f3; end
    always @(posedge ddr_clk or negedge rst_n) if (!rst_n) f_rises <= 3'd0; else if (f_rises != 3'd7) f_rises <= f_rises + 1'b1;
    always @(negedge ddr_clk) if (rst_n && nrst_n && f_rises >= 3'd2) begin
        assert(nsel == {10{nsel[0]}});
        if (nsel[0]) assert(x[19:10] == f_xd[19:10]); else assert(f3 == f_f3d);
    end
`endif
    // Forwarded clock (TC13): c_l toggles on rising edges while enabled (logic copy); the clock lane's
    // launch cells are the same pt_hio_launch as every data lane: lr takes c_l's next value on the
    // rising edge (= c_r), lf copies c_l on the falling edge (= c_f), clk_pin = lr ^ lf.
    reg c_l;
    wire c_n = clk_en ? ~c_l : c_l;
    always @(posedge ddr_clk or negedge rst_n) if (!rst_n) c_l <= 1'b0; else c_l <= c_n;
    pt_hio_launch lc(.clk(ddr_clk), .rst_n(rst_n), .nrst_n(nrst_n), .dr(c_n), .df(c_l), .z(clk_pin));
endmodule

// H2D capture, 1:4 gearbox and pin-clock -> hcore quad FIFO (8 entries: two synchronizer stages on
// each side hide about three quads of occupancy).
// DDR word order: a_j on rising edge j, b_j on the falling edge after it. Rising words go through
// rising-edge registers only (r, r1, r2, r3); falling words are captured by f on every falling edge
// and, on every other falling edge (nsel = 1), the pair {pin, f} = {b_(j+1), b_j} is copied into
// fh, which then holds for two periods. The quad {b_(j+1), a_(j+1), b_j, a_j} is written into the
// FIFO memory on the rising edge 1.5 periods after fh was written (`take`, SDC multicycle 2 from fh
// to host.h2d.mem), straight from r1/r2 and fh. SDR: rising-edge words only, {r, r1, r2, r3} on
// every fourth edge. The per-entry write enables are registered one clock ahead (the write edge is
// known from the phase counter).
module pt_h2d_gearbox(input wire rst_n, input wire [1:0] mode, input wire h2d_clk,
    input wire [9:0] h2d_pin, input wire core_clk, core_rst_n, output reg [39:0] quad,
    output reg overflow, underflow);
    // ---- pin-clock domain
    // TC13 pad-edge capture block (hand-placed, FIXED; see pt_cells.sv pt_hio_*): the pin clock enters
    // through cap_root (clkbuf_8 next to the pin), which clocks only the 30 pin-capture flops (r, f and
    // the upper half of fh) plus core_root, the root of the CTS tree for the rest of the domain. SDC:
    // h2d_pin (port) -> generated h2d_cap (cap_root) -> generated h2d (core_root). Every pin passes
    // one hio_ib clkbuf_8 and the capture flop's kept select (hio_m), so all capture paths are alike.
    wire cka, ckb;
    pt_clock_buf cap_root(.I(h2d_clk), .Z(cka));
    pt_clock_buf core_root(.I(cka), .Z(ckb));
    wire [9:0] hio_pin;
    genvar gp;
    generate for (gp = 0; gp < 10; gp = gp + 1) begin : ib
        pt_hio_ibuf b(.I(h2d_pin[gp]), .Z(hio_pin[gp]));
    end endgenerate
    (* async_reg = "true" *) reg [1:0] hrs;
    always @(posedge ckb or negedge rst_n) if (!rst_n) hrs <= 2'b00; else hrs <= {hrs[0], 1'b1};
    wire hr_n = hrs[1];
    wire [1:0] mode_h;
    pt_sync_vec #(2) smh(.clk(ckb), .rst_n(hr_n), .d(mode), .q(mode_h));
    wire ddr = mode_h == 2'd0;
    wire [9:0] r, f, fh_hi;
    reg [9:0]  r1, r2, r3;
    reg [9:0]  fh;                       // lower half of the falling-word pair (from f); upper half fhh
    wire [19:0] fhw = {fh_hi, fh};
    reg [1:0]  phase;
    reg        hrun;
    always @(posedge ckb or negedge hr_n) if (!hr_n) hrun <= 1'b0; else hrun <= 1'b1;
    // phase[0] is 1 before the rising edges that write a DDR quad (`take`); nsel copies it to the
    // falling edge before, i.e. fh is written 1.5 periods before every take.
    wire nsel; wire [4:0] nselg;   // nselg[g]: replicated copies for fh pin groups (fanout 4 each)
    pt_ddr_nphase hn0(.clk(ckb), .rst_n(hr_n), .run(hrun), .phase(~phase[0]), .nsel(nsel));
    genvar gn;
    generate for (gn = 0; gn < 5; gn = gn + 1) begin : hnr
        pt_ddr_nphase hn(.clk(ckb), .rst_n(hr_n), .run(hrun), .phase(~phase[0]), .nsel(nselg[gn]));
    end endgenerate
    // Falling-edge registers: their reset release may land on either of two falling edges (a
    // half-period recovery path, not timed); they only hold pin data, so either is equivalent.
    integer i;
    // Pin-data registers (f, fh, r..r3) are reset by rst_n itself, not by the synchronized hr_n: they
    // only hold pin words, so an asynchronous release is harmless, and hr_n's synchronous-release
    // fanout (recovery timing at 6.4 ns, run TC1 -3.0 ns) is left to the control registers.
    always @(negedge ckb or negedge rst_n)
        if (!rst_n) fh <= 10'd0;
        else for (i = 0; i < 10; i = i + 1) if (nselg[i/2]) fh[i] <= f[i];
    // pin capture: r (rising), f (falling), fhh = fh[19:10] (falling, pair enable)
    generate for (gp = 0; gp < 10; gp = gp + 1) begin : cap
        pt_hio_cap #(0) cr(.clk(cka), .rst_n(rst_n), .en(1'b1), .d(hio_pin[gp]), .q(r[gp]));
        pt_hio_cap #(1) cf(.clk(cka), .rst_n(rst_n), .en(1'b1), .d(hio_pin[gp]), .q(f[gp]));
    end endgenerate
    generate for (gp = 0; gp < 10; gp = gp + 1) begin : fhh
        pt_hio_cap #(1) c(.clk(cka), .rst_n(rst_n), .en(nselg[gp/2]), .d(hio_pin[gp]), .q(fh_hi[gp]));
    end endgenerate
    // Write side: one-hot pointer, per-entry enables registered one clock ahead (one flop per
    // entry, preserved); Gray pointer for the reader.
    reg  [7:0]  woh;
    wire [7:0]  we;                      // entry e write (copy 0; formal/overflow use)
    wire [4:0]  weg [0:7];               // weg[e][g]: replicated enable for bits 8g+7:8g (fanout 8)
    reg  [3:0]  wb, wg, rg1, rg2, wbn, wgn, wgnn;   // wbn/wgn: wb+1 and its Gray code, wgnn: Gray of wb+2 (precomputed)
    reg         wr_now;                      // a write happens at this edge (any we)
    reg  [39:0] mem [0:7];
    reg  [3:0]  rb, rgray, wg1, wg2;
    // full is a register evaluated on the next-state pointers (identical value; timing 2026-11-11)
    reg full;
    wire take = phase[0];
    wire done = ddr ? take : &phase;                       // a quad is written at this edge
    wire next_done = ddr ? !phase[0] : phase == 2'b10;     // ... at the next edge
    wire [39:0] wdata = ddr ? {fh_hi, r1, fh, r2} : {r, r1, r2, r3};
    wire any_we = wr_now;
    // full (timing 2026-11-11, h2d 6.4 ns): every candidate compare is a register, so full's own
    // input is a 4:1 select of registers by two registers. The candidates compare the write pointer
    // candidates against rg1 one cycle earlier (i.e. against rg2): full is conservative by one more
    // read-pointer synchronizer cycle. wr_full / wr_last are private copies of wr_now (now / last cycle).
    //   need now: (any_we ? wgn : wg) == g(rg2);  wg = wrote_last ? wgn_prev : wg_prev, wgn likewise
    wire wr_full; reg wr_last; reg c_wg, c_wgn, c_wgnn;   // vs g(rg1) last cycle: wg, wgn, wgnn
    pt_rep_dff wr_full_copy(.clk(ckb), .rst_n(hr_n), .d(next_done && !full), .q(wr_full));
    wire [3:0] rgx = {~rg1[3:2], rg1[1:0]};
    integer e, k;
    genvar ge;
    generate for (ge = 0; ge < 8; ge = ge + 1) begin : entries
        // five copies per entry, one per 8-bit slice (timing 2026-11-11: fanout 20 per copy gave a
        // 4-buffer chain, TC4 h2d -3.0 ns)
        genvar gs;
        for (gs = 0; gs < 5; gs = gs + 1) begin : slice
            pt_rep_dff enable(.clk(ckb), .rst_n(hr_n), .d(next_done && woh[ge] && !full), .q(weg[ge][gs]));
        end
        assign we[ge] = weg[ge][0];
    end endgenerate
    always @(posedge ckb or negedge rst_n)
        if (!rst_n) begin r1 <= 10'd0; r2 <= 10'd0; r3 <= 10'd0; end
        else begin r1 <= r; r2 <= r1; r3 <= r2; end
    always @(posedge ckb or negedge hr_n)
        if (!hr_n) begin
            phase <= 2'd0; wr_now <= 1'b0;
            woh <= 8'b00000001; wb <= 4'd0; wg <= 4'd0; wbn <= 4'd1; wgn <= 4'd1; wgnn <= 4'd3; wr_last <= 1'b0; c_wg <= 1'b0; c_wgn <= 1'b0; c_wgnn <= 1'b0; rg1 <= 4'd0; rg2 <= 4'd0; overflow <= 1'b0; full <= 1'b0;
        end else begin
            full <= wr_last ? (wr_full ? c_wgnn : c_wgn) : (wr_full ? c_wgn : c_wg);
            wr_last <= wr_now;   // a write happened at the previous edge
            c_wg <= wg == rgx; c_wgn <= wgn == rgx; c_wgnn <= wgnn == rgx;
            phase <= phase + 1'b1;
            rg1 <= rgray; rg2 <= rg1;
            if (done && !any_we && hrun) overflow <= 1'b1;   // a complete quad found no free entry
            wr_now <= next_done && !full;
            if (any_we) begin
                woh <= {woh[6:0], woh[7]};
                wb <= wbn; wg <= wgn; wbn <= wbn + 1'b1; wgn <= wgnn; wgnn <= (wbn + 2'd2) ^ ((wbn + 2'd2) >> 1);
            end
        end
`ifdef FORMAL
    // DDR word order and the 1.5-period multicycle fh -> mem (SDC): on every write edge fh did not
    // change on the falling edge half a period before, and the written quad is the four
    // chronological pin words {fall T-1.5, rise T-2, fall T-2.5, rise T-3}.
    reg [9:0] f_ra0, f_ra1, f_ra2, f_fb0, f_fb1, f_fb2; reg [19:0] f_fhd; reg [2:0] f_n;
    always @(posedge h2d_clk) begin f_ra0 <= h2d_pin; f_ra1 <= f_ra0; f_ra2 <= f_ra1; end
    always @(negedge h2d_clk) begin f_fb0 <= h2d_pin; f_fb1 <= f_fb0; f_fb2 <= f_fb1; f_fhd <= fhw; end
    always @(posedge ckb or negedge hr_n)
        if (!hr_n) f_n <= 3'd0;
        else begin
            if (f_n != 3'd7) f_n <= f_n + 1'b1;
            if (f_n >= 3'd5 && ddr && take) begin
                assert(fhw == f_fhd);
                assert(wdata == {f_fb1, f_ra1, f_fb2, f_ra2});
            end
            if (any_we) assert(done);
            // registered full candidates == the direct compare against the twice-synchronized pointer
            if (f_n >= 3'd2) assert((wr_last ? (wr_full ? c_wgnn : c_wgn) : (wr_full ? c_wgn : c_wg))
                                    == ((any_we ? wgn : wg) == {~rg2[3:2], rg2[1:0]}));
            assert(wr_full == wr_now);
            cover(f_n == 3'd7 && any_we && wdata != 40'd0);
        end
`endif
    always @(posedge ckb)
        for (e = 0; e < 8; e = e + 1)
            for (k = 0; k < 40; k = k + 1) if (weg[e][k/8]) mem[e][k] <= wdata[k];
    // ---- core domain: start after two quads, then one quad per clock
    reg run;
    wire [3:0] wbin = {wg2[3], ^wg2[3:2], ^wg2[3:1], ^wg2[3:0]};
    wire empty = rgray == wg2;
    wire [3:0] avail = wbin - rb;
    wire ctake = run && !empty;
    always @(posedge core_clk or negedge core_rst_n)
        if (!core_rst_n) begin rb <= 4'd0; rgray <= 4'd0; wg1 <= 4'd0; wg2 <= 4'd0; run <= 1'b0; quad <= 40'd0; underflow <= 1'b0; end
        else begin
            wg1 <= wg; wg2 <= wg1;
            if (!run && avail >= 4'd2) run <= 1'b1;
            quad <= ctake ? mem[rb[2:0]] : 40'd0;   // underflow: idle quad, flagged
            if (ctake) begin rb <= rb + 1'b1; rgray <= (rb + 1'b1) ^ ((rb + 1'b1) >> 1); end
            if (run && empty) underflow <= 1'b1;
        end
endmodule

// Reduced-rate fallback for the whole host transport (debug.host_link.rate):
// 0 = full (hddr = host DDR clock), 1 = /2, 2 or 3 = /4. The selected clock
// drives pt_host_link (DDR side) and, through its /2 divider, the transport
// core and every engine behind it, so the chip stays fully functional at 1/2
// or 1/4 throughput (the FPGA follows the forwarded D2H clock; the wired/RF
// line rates must be lowered to match through the clocktree dividers). The
// field is stopped-only: a change first holds the host link and transport
// core in reset (hold_n=0), switches the clock-select register while every
// destination is in reset, then releases. Runt pulses at the switch
// therefore only reach reset flops. STA constrains each setting as a
// separate mode (HOST_RATE_DIV in integration/pt_digital_macro.sdc); the
// select register is case-analysed. word_clk = 2 x out_clk for the SDR
// forwarded clock at the reduced rates (at full rate it equals clk).
module pt_host_rate_clock(input wire clk,rst_n,input wire[1:0]rate,
 output wire out_clk,word_clk,output reg hold_n);
 reg[1:0]div;   // div[0] = clk/2, div[1] = clk/4 (both 50 % duty, rising together)
 reg[1:0]cur;   // applied select: 0 full, 1 /2, 2 /4
 reg[1:0]gap;
 wire[1:0]rate_s;
 pt_sync_vec #(2) rate_sync(clk,rst_n,rate,rate_s);
 reg[1:0]want;   // normalized request, registered
 // Timing (2026-11-11, hword 6.4 ns; TC4 -1.9 ns from cur (clk-q 3.2 ns, fanout 6 incl. the clock
 // mux selects) -> want != cur -> gap): `cur` now only drives the clock muxes; the FSM uses its own
 // copy (cur_n = ~cur) and a registered compare ne = (want != ~cur_n), one cycle late. Effect: a rate change is
 // noticed one hword cycle later, and the release check at gap == 3 sees ne computed at gap == 2,
 // after cur_n was updated at gap == 1, so the sequence is otherwise unchanged.
 // cur_n is the logic copy stored inverted so synthesis cannot merge it with cur.
 reg[1:0]cur_n;reg ne;
 always @(posedge clk or negedge rst_n)
  if(!rst_n)div<=0;else div<=div+1'b1;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin cur<=0;cur_n<=2'b11;ne<=0;hold_n<=0;gap<=0;want<=0;end
  else begin want<=rate_s[1]?2'd2:rate_s;ne<=want!=~cur_n;
  if(hold_n)begin
   if(ne)begin hold_n<=0;gap<=0;end
  end else begin
   gap<=gap+1'b1;
   if(gap==1)begin cur<=want;cur_n<=~want;end
   if(gap==3&&!ne)hold_n<=1;
  end
  end
 end
 wire slow_clk;
`ifdef SYNTHESIS
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__mux2_2 rate_slow_mux(
  .I0(div[0]),.I1(div[1]),.S(cur[1]),.Z(slow_clk));
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__mux2_2 rate_clock_mux(
  .I0(clk),.I1(slow_clk),.S(cur != 2'd0),.Z(out_clk));
 (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__mux2_2 word_clock_mux(
  .I0(clk),.I1(div[0]),.S(cur[1]),.Z(word_clk));
`else
 assign slow_clk=cur[1] ? div[1] : div[0];
 assign out_clk=(cur != 2'd0) ? slow_clk : clk;
 assign word_clk=cur[1] ? div[0] : clk;
`endif
endmodule

`default_nettype wire
