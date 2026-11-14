// Supply / clock monitor, digital half (D-FAULT). Produces the macro `fault` level (fault only
// releases the transmit paths; SPI is not affected).
//
// Requirements (index i in every 10-bit status vector):
//   0 reference clock present   (cfg_require_reference,   watchdog on ref_clk)
//   1 input clock present       (cfg_require_input_clock, watchdog on in_clk)
//   2 rf lock                   (cfg_require_rf_lock,     level rf_lock)
//   3 wire lock                 (cfg_require_wire_lock,   level wire_lock)
//   4+k supply k, k = 0..5      (cfg_required_supply_mask[k]; k = island index: 0 wired, 1 rf,
//                                2 pll, 3 reserved (no switch), 4 conv, 5 debug)
// A supply is good when island_pgood[k] is 1 (bits in PGOOD_IMPL) and supply_win_ok[k] is 1 (bits
// in WIN_IMPL: analog window comparators that do not exist yet, WIN_IMPL = 0). A mask bit with
// neither source has no hardware and is ignored (the register file must reject it).
//
// Behaviour (mon_clk domain; one tick = one mon_clk cycle):
//   * A requirement that is armed but not qualified is "pending" and holds fault = 1 (no cause).
//     It qualifies when every pending requirement has been good without interruption for
//     cfg_qualification_ticks units of 64 ticks (Q..Q+1 units). One shared timer.
//   * A qualified requirement that is bad for cfg_loss_timeout_ticks ticks trips: its cause bit
//     is set (sticky) and it becomes pending again (it requalifies by itself when good again).
//     Clocks: no edge of the divided watched clock for the timeout (one timer per clock; the timer
//     runs on mon_clk, never on the watched clock). Levels (locks, supplies): one shared timer,
//     which starts with the first bad level; a second level that goes bad later trips with it.
//   * cause bits are cleared by a rising edge of clear_fault (static SPI level, synchronized here;
//     write 1, then 0). A held 1 masks nothing; a trip in the same cycle wins.
//   * fault = arm_any & (any cause | any pending | mon_clk lost). arm_any is the combinational OR
//     of the SPI-domain requirement bits: with every requirement written 0, fault is 0 without any
//     clock. After reset nothing is armed and fault = 0.
//   * mon_clk absent: a ref_clk-domain watchdog (255 ref cycles without an edge of mon_clk/64)
//     sets mon_dead; mon_dead while armed sets the sticky cause_mon_clk and fault. With mon_clk AND
//     ref_clk both absent nothing can be detected: fault keeps its last value (arm_any still
//     releases it).
// Configuration rule: cfg_loss_timeout_ticks and cfg_qualification_ticks are used unsynchronized;
// they may change only in a commit whose previous requirement bits were all 0. The time-base select
// of mon_clk (monitor.config.timebase, a plain clock mux in rtl/pt_digital_macro.sv) is stricter:
// the commit that changes it must ALSO leave every requirement bit 0; the new time base must be
// running; then pulse clear_fault; then arm in a later commit. (A requirement written 0 loses its
// arm / qualified state without a clock, so re-arming always re-qualifies.) Requirement bits should
// be changed through all-0 while a fault is asserted: arm_any is a combinational OR and a 1 -> 1
// swap of bits can glitch fault low for a gate delay (review F5).
// Clock limits: watched-clock edge spacing (2^(DIVW-1) cycles) must exceed one mon_clk period and
// stay below the loss timeout; ref_clk >= 4 MHz for the mon_clk watchdog (with the oscillator), and
// 255 ref_clk periods must exceed 32 mon_clk periods (the heartbeat pre[5]) for any time base.
//
// Time base (mon_clk is selected outside this module; nothing here depends on which one it is):
//   0  always-on oscillator, 40..60 MHz. Not available while an RF payload runs (the register
//      file holds the oscillator off: spur risk).
//   1  transport core clock / 2: 39.06 MHz at the full host rate (25.6 ns per tick), 51.2 / 102.4 ns
//      per tick at the reduced host rates. Every tick-counted time scales with it.
//      * Requirement 1 (H2D_CLK present) is then watched from a ring-derived clock: in host-follow
//        the ring free-runs when H2D_CLK disappears, so mon_clk keeps running and the loss is
//        detected.
//      * Loss of the time base itself is only detected while ref_clk runs (the ref_clk-domain
//        watchdog below). With an external LO on the REF pads there is no ref_clk: a stopped core
//        clock is then undetectable in RTL (every mon_clk-domain flop, fault_m included, keeps its
//        value). An analog clock-present detector is requested from pads / core-support for that
//        case; it has no port here yet.
//      * Limits with this time base: in_clk (H2D_CLK, DDR = 4 in_clk cycles per tick): in_div
//        toggles every 2 ticks at every host rate (frequency-locked, any phase: fine). With the
//        SDR forwarded clock (8 in_clk cycles per tick) it toggles every tick exactly, which is the
//        edge of the first limit above: raise IN_DIVW to 5 before arming requirement 1 in that mode.
//        ref_clk: 4 ref periods > 1 tick needs ref_clk < 156 / 78 / 39 MHz at host rate /1 /2 /4;
//        the watchdog needs ref_clk < 311 / 155 / 77 MHz (255 ref periods > 32 ticks).
`default_nettype none
module pt_monitor #(
    parameter integer LW = 12,                 // loss-timeout width
    parameter integer QW = 16,                 // qualification width (units of 64 ticks)
    parameter [5:0]   PGOOD_IMPL = 6'b110111,  // supplies with an island_pgood flag
    parameter [5:0]   WIN_IMPL   = 6'b000000,  // supplies with a window comparator (none built)
    parameter integer REF_DIVW = 3,            // ref_clk watchdog divider: edge every 4 cycles
    parameter integer IN_DIVW  = 4             // in_clk watchdog divider: edge every 8 cycles
)(
    input  wire          rst_n,
    input  wire          mon_clk,       // time base: always-on oscillator (40..60 MHz) or core clock / 2
    input  wire          ref_clk,       // watched; also clocks the mon_clk watchdog
    input  wire          in_clk,        // watched
    input  wire          rf_lock,       // asynchronous levels
    input  wire          wire_lock,
    input  wire [5:0]    island_pgood,
    input  wire [5:0]    supply_win_ok, // future analog window comparators (see WIN_IMPL)
    // SPI-domain static levels
    input  wire          cfg_require_reference,
    input  wire          cfg_require_input_clock,
    input  wire          cfg_require_rf_lock,
    input  wire          cfg_require_wire_lock,
    input  wire [5:0]    cfg_required_supply_mask,
    input  wire [LW-1:0] cfg_loss_timeout_ticks,
    input  wire [QW-1:0] cfg_qualification_ticks,
    input  wire          clear_fault,
    output wire          fault,         // asynchronous level
    output wire          ready,         // armed, everything qualified, no fault
    output wire [9:0]    cause,         // mon_clk domain, sticky
    output wire          cause_mon_clk, // ref_clk domain, sticky
    output wire [9:0]    qualified,     // mon_clk domain, live
    output wire          ref_alive,     // mon_clk domain, live
    output wire          in_alive,      // mon_clk domain, live
    output wire          mon_dead       // ref_clk domain, live
);
    localparam [9:0] IMPL = {PGOOD_IMPL | WIN_IMPL, 4'b1111};
    wire [9:0] req = {cfg_required_supply_mask, cfg_require_wire_lock, cfg_require_rf_lock,
                      cfg_require_input_clock, cfg_require_reference};
    wire arm_any = |(req & IMPL);

    // ---------------- watched domains: dividers only
    reg [REF_DIVW-1:0] ref_div;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) ref_div <= {REF_DIVW{1'b0}}; else ref_div <= ref_div + 1'b1;
    reg [IN_DIVW-1:0] in_div;
    always @(posedge in_clk or negedge rst_n)
        if (!rst_n) in_div <= {IN_DIVW{1'b0}}; else in_div <= in_div + 1'b1;

    // ---------------- mon_clk domain
    wire ref_t, in_t, rf_s, wire_s, clr_s;
    pt_sync_bit s_ref(.clk(mon_clk), .rst_n(rst_n), .d(ref_div[REF_DIVW-1]), .q(ref_t));
    pt_sync_bit s_in (.clk(mon_clk), .rst_n(rst_n), .d(in_div[IN_DIVW-1]),   .q(in_t));
    pt_sync_bit s_rf (.clk(mon_clk), .rst_n(rst_n), .d(rf_lock),             .q(rf_s));
    pt_sync_bit s_wl (.clk(mon_clk), .rst_n(rst_n), .d(wire_lock),           .q(wire_s));
    pt_sync_bit s_clr(.clk(mon_clk), .rst_n(rst_n), .d(clear_fault),         .q(clr_s));

    reg ref_t_d, in_t_d, clr_d;
    reg [5:0] pre;                    // free-running /64: qualification unit, heartbeat to ref_clk
    reg pre_tick;                     // pre == 63, registered (decoded one tick ahead)
    always @(posedge mon_clk or negedge rst_n)
        if (!rst_n) begin ref_t_d <= 1'b0; in_t_d <= 1'b0; clr_d <= 1'b0; pre <= 6'd0; pre_tick <= 1'b0; end
        else begin
            ref_t_d <= ref_t; in_t_d <= in_t; clr_d <= clr_s; pre <= pre + 6'd1; pre_tick <= pre == 6'd62;
        end
    wire clr = clr_s & ~clr_d;

    // clock-presence watchdogs. Timing (16 ns mon_clk, slow cells): the timers are free-running
    // saturating counters, so the timeout compare ends in the alive flop only and never enables
    // the increment (the flags fall in the same cycle as before).
    reg [LW-1:0] rcnt, icnt;
    reg ref_alive_q, in_alive_q;
    always @(posedge mon_clk or negedge rst_n)
        if (!rst_n) begin rcnt <= {LW{1'b0}}; icnt <= {LW{1'b0}}; end
        else begin
            if (ref_t ^ ref_t_d) rcnt <= {LW{1'b0}}; else if (!(&rcnt)) rcnt <= rcnt + 1'b1;
            if (in_t ^ in_t_d)   icnt <= {LW{1'b0}}; else if (!(&icnt)) icnt <= icnt + 1'b1;
        end
    always @(posedge mon_clk or negedge rst_n) // ref watchdog timer
        if (!rst_n) ref_alive_q <= 1'b0;
        else if (ref_t ^ ref_t_d) ref_alive_q <= 1'b1;
        else if (rcnt >= cfg_loss_timeout_ticks) ref_alive_q <= 1'b0;
    always @(posedge mon_clk or negedge rst_n) // in watchdog timer
        if (!rst_n) in_alive_q <= 1'b0;
        else if (in_t ^ in_t_d) in_alive_q <= 1'b1;
        else if (icnt >= cfg_loss_timeout_ticks) in_alive_q <= 1'b0;
    assign ref_alive = ref_alive_q;
    assign in_alive  = in_alive_q;

    // requirement state
    wire [9:0] arm_s, g, qual, trip;
    wire       q_done, q_run, lvl_exp;
    reg        q_done_q;              // q_done, one tick later (still gated by q_run where it is used)
    assign g[0] = ref_alive_q;
    assign g[1] = in_alive_q;
    assign g[2] = rf_s;
    assign g[3] = wire_s;
    assign trip[1:0] = qual[1:0] & ~g[1:0];
    assign trip[9:2] = qual[9:2] & ~g[9:2] & {8{lvl_exp}};
    genvar i;
    generate
        for (i = 0; i < 6; i = i + 1) begin : sup
            if (IMPL[4+i]) begin : on
                wire raw = (PGOOD_IMPL[i] ? island_pgood[i] : 1'b1) & (WIN_IMPL[i] ? supply_win_ok[i] : 1'b1);
                pt_sync_bit s(.clk(mon_clk), .rst_n(rst_n), .d(raw), .q(g[4+i]));
            end else begin : off
                assign g[4+i] = 1'b0;
            end
        end
        for (i = 0; i < 10; i = i + 1) begin : rq
            if (IMPL[i]) begin : on
                // r7 (independent review of the time base, F1): a requirement bit written 0 clears its synchronized
                // arm level and its qualified flag ASYNCHRONOUSLY, so a requirement that was disarmed while the monitor
                // clock was stopped (RF payload on time base 0, or before a time-base change) can never come back
                // "already qualified": after re-arming it is pending (fault) until it has qualified on the running
                // clock. Release (req 0 -> 1) is re-timed by the synchronizer sa; q has D = 0 while arm_s is 0.
                wire rq_rst_n = rst_n & req[i];
                pt_sync_bit sa(.clk(mon_clk), .rst_n(rq_rst_n), .d(req[i]), .q(arm_s[i]));
                reg q, c;
                always @(posedge mon_clk or negedge rq_rst_n)
                    if (!rq_rst_n) q <= 1'b0;
                    else q <= arm_s[i] & ((q & ~trip[i]) | (~q & q_done_q & q_run));
                always @(posedge mon_clk or negedge rst_n)
                    if (!rst_n) c <= 1'b0;
                    else c <= (c & ~clr) | trip[i];
                assign qual[i] = q;
                assign cause[i] = c;
            end else begin : off
                assign arm_s[i] = 1'b0;
                assign qual[i] = 1'b0;
                assign cause[i] = 1'b0;
            end
        end
    endgenerate
    assign qualified = qual;

    // shared qualification timer
    wire [9:0] unq = arm_s & ~qual;
    // Timing: the QW-bit compare ends in the flop q_done_q and nothing else; the requirement flops
    // and the timer restart use q_done_q (qualification completes one tick later; an interruption
    // in that tick still cancels it through q_run). qcnt only changes at a pre_tick and q_done is
    // only non-zero at the next one, 64 ticks later.
    assign q_run = (|unq) & (&(g | ~unq));
    reg [QW-1:0] qcnt;
    assign q_done = q_run & pre_tick & (qcnt >= cfg_qualification_ticks);
    always @(posedge mon_clk or negedge rst_n)
        if (!rst_n) begin qcnt <= {QW{1'b0}}; q_done_q <= 1'b0; end
        else begin
            q_done_q <= q_done;
            if (!q_run || q_done_q) qcnt <= {QW{1'b0}};
            else if (pre_tick) qcnt <= qcnt + 1'b1;
        end

    // shared loss timer of the level requirements
    wire lvl_bad = |(qual[9:2] & ~g[9:2]);
    // Timing: the expiry is a flop (lx_q = "the timer value of the coming tick is >= the timeout",
    // compared one tick ahead against the static timeout - 1), so lvl_exp is in the same tick as
    // before and the compare does not run into the trip / cause / restart logic.
    reg [LW-1:0] lcnt;
    reg          lx_q;
    wire          loss_z  = cfg_loss_timeout_ticks == {LW{1'b0}};
    wire [LW-1:0] loss_m1 = cfg_loss_timeout_ticks - 1'b1;          // static
    assign lvl_exp = lvl_bad & lx_q;
    always @(posedge mon_clk or negedge rst_n)
        if (!rst_n) begin lcnt <= {LW{1'b0}}; lx_q <= 1'b0; end
        else if (!lvl_bad || lvl_exp) begin lcnt <= {LW{1'b0}}; lx_q <= loss_z; end
        else begin lcnt <= lcnt + 1'b1; lx_q <= loss_z | (lcnt >= loss_m1); end

    reg fault_m, ready_m;
    always @(posedge mon_clk or negedge rst_n)
        if (!rst_n) begin fault_m <= 1'b0; ready_m <= 1'b0; end
        else begin
            fault_m <= (|cause) | (|unq);
            ready_m <= (|arm_s) & ~(|cause) & ~(|unq);
        end

    // ---------------- ref_clk domain: watchdog on mon_clk
    wire hb_s, arm_r, clr_rs;
    pt_sync_bit r_hb (.clk(ref_clk), .rst_n(rst_n), .d(pre[5]),      .q(hb_s));
    pt_sync_bit r_arm(.clk(ref_clk), .rst_n(rst_n), .d(arm_any),     .q(arm_r));
    pt_sync_bit r_clr(.clk(ref_clk), .rst_n(rst_n), .d(clear_fault), .q(clr_rs));
    reg hb_d, clr_rd, mon_dead_q, mon_lost;
    reg [7:0] mcnt;
    always @(posedge ref_clk or negedge rst_n)
        if (!rst_n) begin
            hb_d <= 1'b0; clr_rd <= 1'b0; mon_dead_q <= 1'b0; mon_lost <= 1'b0; mcnt <= 8'd0;
        end else begin
            hb_d <= hb_s; clr_rd <= clr_rs;
            if (hb_s ^ hb_d) begin mcnt <= 8'd0; mon_dead_q <= 1'b0; end
            else if (&mcnt) mon_dead_q <= 1'b1;
            else mcnt <= mcnt + 8'd1;
            mon_lost <= (mon_lost & ~(clr_rs & ~clr_rd)) | (mon_dead_q & arm_r);
        end
    assign mon_dead = mon_dead_q;
    assign cause_mon_clk = mon_lost;

    // kept gate: the SDC cuts timing through fault_gate.ag/Z (asynchronous level, see pt_cells.sv pt_async_gate)
    pt_async_gate fault_gate(.a(arm_any), .b(fault_m | mon_lost), .y(fault));
    assign ready = arm_any & ready_m & ~mon_lost;
endmodule
`default_nettype wire
