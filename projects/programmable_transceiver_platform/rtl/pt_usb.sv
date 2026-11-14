// USB 2.0 on-die raw line interface (rows MW-18, D-USB, TOP-18). No protocol: packets, CRC, bit
// stuffing and NRZI stay in the FPGA; this block moves raw line symbols and owns the driver safety.
//
// What the artefacts fix (2026-11-13):
//   * pad_wirepad (analog/pads/wired_receive.py): HS_x = gate of the nfet series switch under the
//     HS_PBIAS current source of leg x (active high, per-bit data: the pad has NO serializer);
//     FS_HIGH_x = high-side driver of leg x on; FS_LOW_x = the 45 ohm shunt bank of leg x on
//     (shared with TERM_ENABLE, qualified by the pad's VCM_LOW_OK). All active high, 0 = off.
//   * HS data (480 Mb/s) cannot be toggled from standard cells. It runs through the existing wired
//     path: wire_tx_data quads -> pt_wiredtx (ring 480 MHz, quarter-rate core, x4 repetition, WT19)
//     -> CMD_MAIN_P/N -> pre-driver pt_usb_txdrv (analog/wired_tx/usbdrv.py, in progress) -> HS_P/N.
//     HS receive is rxselect direct -> slicer -> pt_wrx_cap -> wire_rx_data (existing ingress).
//     This block only makes the HS enables: usb_hs_en (branch) and usb_hs_drv (packet envelope).
//   * FS / LS (12 / 1.5 Mb/s) are fully served here: TX symbols at tx_clk / (cfg_tx_div + 1), RX by
//     oversampling the pt_detect comparators at rx_clk / (cfg_rx_div + 1) per bit.
//
// Symbols are two bits {dn, dp}, first on the line in the low bits of a 40-bit quad (20 symbols):
//   TX: 01 = D+ driven high / D- low, 10 = D- high / D+ low, 00 = SE0 (both low), 11 = released
//       (high-Z; SE1 is never driven).  RX: {SE_N, SE_P} at the bit centre (00 SE0, 11 SE1).
//
// Two output sets, bind one:
//   direct gates  c_usb_hs_p/n, c_usb_fs_high_p/n, c_usb_fs_low_p/n   (pt_chip.conn today; break-
//                 before-make of 1 + cfg_bbm tx_clk cycles per leg in RTL; HS only static levels)
//   pre-driver    usb_hs_en, usb_hs_drv, usb_fs_en, usb_tx_dp, usb_tx_dn, usb_tx_oe
//                 (pt_usb_txdrv HS_EN, HS_DRV, FS_EN, TX_DP, TX_DN, TX_OE; its own analog BBM)
//
// Interlocks. Every driver output is a flop with asynchronous clear on rst_n = 0, fault = 1 or
// island_on = 0 (no clock needed); release is synchronous and drive stays off until the request
// fields have been seen 0 once (re-arm). HS and FS are exclusive by construction: one branch decode,
// and each side may only turn on after the other side's flops have been 0 for 1 + cfg_bbm cycles.
// FS is refused while the pad termination is on (FS high side into the 45 ohm shunt), HS while
// LS_SLOW = 1 (pads PD41/PD47).
`default_nettype none

module pt_usb_sync(input wire clk, rst_n, d, output reg q);
    (* async_reg = "true" *) reg meta;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin meta <= 1'b0; q <= 1'b0; end else begin meta <= d; q <= meta; end
endmodule

// Level debounce: q follows d after d has been equal for n + 1 consecutive samples. The counter
// runs on (saturating) so that the compare with n only ends in q, not in the counter enable.
module pt_usb_debounce #(parameter integer W = 1, parameter integer CW = 8)(
    input  wire          clk, rst_n,
    input  wire [CW-1:0] n,
    input  wire [W-1:0]  d,
    output reg  [W-1:0]  q
);
    reg [W-1:0]  cand;
    reg [CW-1:0] cnt;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin cand <= {W{1'b0}}; q <= {W{1'b0}}; end
        else if (d != cand) cand <= d;
        else if (cnt == n) q <= cand;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) cnt <= {CW{1'b0}};
        else if (d != cand) cnt <= {CW{1'b0}};
        else if (!(&cnt)) cnt <= cnt + 1'b1;
endmodule

module pt_usb(
    input  wire        rst_n,            // asynchronous, active low
    input  wire        island_on,        // wired island powered and released (asynchronous level)
    input  wire        fault,            // asynchronous, active high: all drivers off
    // ---------------- transmit side, tx_clk (wire_tx_clk = WORD_CLK40; 48 MHz with the TX ring at 480 MHz)
    input  wire        tx_clk,
    input  wire [1:0]  cfg_branch,       // usbdrive.select.branch: 0 off, 1 hs, 2 fsls, 3 = off
    input  wire        cfg_active,       // usbdrive.state.state == active
    input  wire        cfg_hs_tx_en,     // usbhs.config.tx_enable
    input  wire        cfg_fs_drive_en,  // usbfs.config.drive_enable
    input  wire        cfg_hs_sym,       // HS branch: 1 = symbol stream drives the HS gates statically (chirp)
    input  wire        cfg_force_en,     // drive cfg_force_sym instead of the stream (calibration, chirp K)
    input  wire [1:0]  cfg_force_sym,    // {dn, dp}
    input  wire        cfg_ls_slow,      // usbfs.config.ls_slow (pad LS_SLOW)
    input  wire        cfg_term_on,      // pad TERM_ENABLE request (c_term_en)
    input  wire [7:0]  cfg_tx_div,       // tx_clk cycles per symbol - 1 (static)
    input  wire [1:0]  cfg_bbm,          // extra break-before-make cycles (static)
    input  wire [39:0] tx_data,          // 20 symbols, first in [1:0]
    input  wire        tx_valid,
    output wire        tx_ready,         // quad taken on tx_valid && tx_ready; a register (one-quad holding stage)
    input  wire        hs_tx_active,     // tx_clk domain: an HS packet is in the serializer (wire_tx_valid && !wire_idle)
    output wire        c_usb_hs_p, c_usb_hs_n,
    output wire        c_usb_fs_high_p, c_usb_fs_high_n, c_usb_fs_low_p, c_usb_fs_low_n,
    output wire        usb_hs_en, usb_hs_drv, usb_fs_en, usb_tx_dp, usb_tx_dn, usb_tx_oe,
    output wire        st_tx_busy,       // tx_clk domain levels
    output wire        st_tx_underrun,   // sticky until the request fields are 0
    output wire        st_tx_blocked,    // sticky: a drive request was refused by an interlock
    output wire        st_tx_armed,
    // ---------------- receive side, rx_clk
    input  wire        rx_clk,
    input  wire        s_detect_diff_pos, s_detect_diff_neg, s_detect_se_p, s_detect_se_n,   // asynchronous
    input  wire        cfg_rx_en,
    input  wire        cfg_rx_diff,      // 1: J/K from DIFF_POS/DIFF_NEG while a line is high, else {SE_N, SE_P}
    input  wire        cfg_rx_echo,      // 1: keep receiving while this chip drives
    input  wire        cfg_ls,           // low speed: J = D- high (status decode only)
    input  wire        cfg_thr_disc,     // detect threshold is at the disconnect level (detect.config thr == 3)
    input  wire [7:0]  cfg_rx_div,       // rx_clk cycles per bit - 1 (>= 3; static)
    input  wire [4:0]  cfg_rx_quiet,     // a burst ends after this many bits without a change (static)
    input  wire [7:0]  cfg_deb_se,       // line-state debounce, rx_clk samples - 1
    input  wire [3:0]  cfg_deb_diff,     // differential envelope debounce, rx_clk samples - 1
    output reg  [39:0] rx_data,          // 20 symbols, first in [1:0]; stable until the next rx_valid
    output reg         rx_valid,         // one rx_clk cycle per quad, no back-pressure
    output wire        st_rx_active,     // a burst is being recorded
    output wire [1:0]  st_line,          // debounced {SE_N, SE_P}
    output wire        st_j, st_k, st_se0, st_se1,
    output wire        st_diff,          // debounced DIFF_POS | DIFF_NEG
    output wire        st_squelch,       // 1 = no differential signal above the squelch threshold
    output reg         st_disconnect     // sticky: envelope over the disconnect threshold during HS transmit
);
    // =====================================================================================
    // Transmit domain
    // =====================================================================================
    wire kill_n = rst_n & island_on & ~fault;
    reg [4:0] trs;
    always @(posedge tx_clk or negedge kill_n)
        if (!kill_n) trs <= 5'd0; else trs <= {trs[3:0], 1'b1};
    wire t_rst_n = trs[1];
    wire t_cfg_ok = trs[4];   // the field synchronizers below hold real values again (re-arm may look at them)

    wire [1:0] branch_s;
    wire active_s, hs_tx_en_s, fs_en_s, hs_sym_s, force_s, ls_slow_s, term_on_s;
    pt_usb_sync y_b0(.clk(tx_clk), .rst_n(t_rst_n), .d(cfg_branch[0]),   .q(branch_s[0]));
    pt_usb_sync y_b1(.clk(tx_clk), .rst_n(t_rst_n), .d(cfg_branch[1]),   .q(branch_s[1]));
    pt_usb_sync y_ac(.clk(tx_clk), .rst_n(t_rst_n), .d(cfg_active),      .q(active_s));
    pt_usb_sync y_he(.clk(tx_clk), .rst_n(t_rst_n), .d(cfg_hs_tx_en),    .q(hs_tx_en_s));
    pt_usb_sync y_fe(.clk(tx_clk), .rst_n(t_rst_n), .d(cfg_fs_drive_en), .q(fs_en_s));
    pt_usb_sync y_hy(.clk(tx_clk), .rst_n(t_rst_n), .d(cfg_hs_sym),      .q(hs_sym_s));
    pt_usb_sync y_fo(.clk(tx_clk), .rst_n(t_rst_n), .d(cfg_force_en),    .q(force_s));
    pt_usb_sync y_ls(.clk(tx_clk), .rst_n(t_rst_n), .d(cfg_ls_slow),     .q(ls_slow_s));
    pt_usb_sync y_tm(.clk(tx_clk), .rst_n(t_rst_n), .d(cfg_term_on),     .q(term_on_s));

    wire req_fs = branch_s == 2'd2 && fs_en_s && active_s;
    wire req_hs = branch_s == 2'd1 && hs_tx_en_s && active_s;
    reg  armed, blocked, underrun;
    wire sel_fs = req_fs && armed && !term_on_s;
    wire sel_hs = req_hs && armed && !ls_slow_s;

    // driver flops
    reg fs_en_q, hs_en_q, hs_drv_q, oe_q, dp_q, dn_q;
    reg g_hs_p, g_hs_n, g_fh_p, g_fh_n, g_fl_p, g_fl_n;
    reg [1:0] age_fs, age_hs, age_fh_p, age_fh_n, age_fl_p, age_fl_n;   // cycles a group has been off (saturating)
    wire fs_any = fs_en_q | g_fh_p | g_fh_n | g_fl_p | g_fl_n;
    wire hs_any = hs_en_q | hs_drv_q | g_hs_p | g_hs_n;
    wire fs_clear = !fs_any && age_fs >= cfg_bbm;
    wire hs_clear = !hs_any && age_hs >= cfg_bbm;

    // symbol engine. Timing (wire_tx_clk, slow cells): tx_ready is a flop and a quad is taken into the
    // holding register hq (hv = full); the engine loads from hq, so nothing combinational hangs on
    // tx_ready / tx_valid / tx_data. The symbol-time compare and the symbol count are registered
    // flags (last_q: ph == cfg_tx_div in this cycle, nnz: nsym != 0), and the engine runs from eng,
    // one cycle behind eng_on (the driver flops keep their own direct gating by sel_fs / sel_hs).
    // A quad must be offered one cycle before the previous one ends (it is taken up to a whole quad
    // early); a quad taken in the cycle the engine is switched off is dropped with the engine state.
    reg [39:0] sh, hq;
    reg [4:0]  nsym;
    reg [7:0]  ph;
    reg [1:0]  cur;
    reg        busy, eng, hv, rdy_q, last_q, nnz;
    wire eng_on = (fs_en_q && sel_fs) || (hs_en_q && sel_hs && hs_sym_s);
    wire [7:0] div_m1 = cfg_tx_div - 8'd1;        // static
    wire       div_z  = cfg_tx_div == 8'd0;
    wire step = !busy || last_q;
    wire take = tx_valid && rdy_q;
    wire pop  = step && !nnz && hv;               // the engine loads the held quad (eng = 1)
    assign tx_ready = rdy_q;

    always @(posedge tx_clk or negedge t_rst_n)
        if (!t_rst_n) begin
            sh <= 40'd0; hq <= 40'd0; nsym <= 5'd0; ph <= 8'd0; cur <= 2'b11; busy <= 1'b0;
            eng <= 1'b0; hv <= 1'b0; rdy_q <= 1'b0; last_q <= 1'b0; nnz <= 1'b0;
            armed <= 1'b0; blocked <= 1'b0; underrun <= 1'b0;
        end else begin
            if (!req_fs && !req_hs) begin if (t_cfg_ok) armed <= 1'b1; blocked <= 1'b0; underrun <= 1'b0; end
            else if (!armed || (req_fs && term_on_s) || (req_hs && ls_slow_s)) blocked <= 1'b1;
            eng <= eng_on;
            if (take) hq <= tx_data;
            if (!eng) begin
                nsym <= 5'd0; nnz <= 1'b0; ph <= 8'd0; last_q <= div_z; cur <= 2'b11; busy <= 1'b0;
                hv <= 1'b0; rdy_q <= 1'b0;
            end else begin
                rdy_q <= pop || !(hv || take);    // = holding register empty in the next cycle
                if (take) hv <= 1'b1; else if (pop) hv <= 1'b0;
                if (step) begin
                    ph <= 8'd0; last_q <= div_z;
                    if (nnz) begin
                        cur <= sh[1:0]; sh <= {2'b11, sh[39:2]}; nsym <= nsym - 5'd1; nnz <= nsym != 5'd1;
                    end else if (hv) begin
                        cur <= hq[1:0]; sh <= {2'b11, hq[39:2]}; nsym <= 5'd19; nnz <= 1'b1; busy <= 1'b1;
                    end else begin
                        if (busy && cur != 2'b11) underrun <= 1'b1;   // ran dry while driving
                        cur <= 2'b11; busy <= 1'b0;
                    end
                end else begin ph <= ph + 8'd1; last_q <= ph == div_m1; end
            end
        end

    wire [1:0] sym = force_s ? cfg_force_sym : cur;
    wire s_oe = sym != 2'b11;
    wire s_dp = sym == 2'b01;
    wire s_dn = sym == 2'b10;
    wire fs_act = fs_en_q && sel_fs;                              // FS drivers may follow the symbol
    wire hs_act = hs_en_q && sel_hs && (hs_sym_s || force_s);     // HS static levels may follow the symbol

    always @(posedge tx_clk or negedge t_rst_n)
        if (!t_rst_n) begin
            fs_en_q <= 1'b0; hs_en_q <= 1'b0; hs_drv_q <= 1'b0; oe_q <= 1'b0; dp_q <= 1'b0; dn_q <= 1'b0;
            g_hs_p <= 1'b0; g_hs_n <= 1'b0; g_fh_p <= 1'b0; g_fh_n <= 1'b0; g_fl_p <= 1'b0; g_fl_n <= 1'b0;
            age_fs <= 2'd0; age_hs <= 2'd0; age_fh_p <= 2'd0; age_fh_n <= 2'd0; age_fl_p <= 2'd0; age_fl_n <= 2'd0;
        end else begin
            // branch enables: one side only after the other has been off for 1 + cfg_bbm cycles
            fs_en_q  <= sel_fs && hs_clear;
            hs_en_q  <= sel_hs && fs_clear;
            hs_drv_q <= hs_en_q && sel_hs && !hs_sym_s && !force_s && hs_tx_active;
            // pre-driver levels
            oe_q <= (fs_act || hs_act) && s_oe;
            dp_q <= (fs_act || hs_act) && s_dp;
            dn_q <= (fs_act || hs_act) && s_dn;
            // direct gates. A leg's driver turns on only after the opposite driver of that leg has
            // been off for 1 + cfg_bbm cycles (its flop is 0 and its age has reached cfg_bbm).
            g_fh_p <= fs_act && s_dp          && !g_fl_p && age_fl_p >= cfg_bbm;
            g_fl_p <= fs_act && s_oe && !s_dp && !g_fh_p && age_fh_p >= cfg_bbm;
            g_fh_n <= fs_act && s_dn          && !g_fl_n && age_fl_n >= cfg_bbm;
            g_fl_n <= fs_act && s_oe && !s_dn && !g_fh_n && age_fh_n >= cfg_bbm;
            g_hs_p <= hs_act && s_dp;
            g_hs_n <= hs_act && s_dn;
            age_fs   <= fs_any ? 2'd0 : (age_fs   == 2'd3 ? 2'd3 : age_fs   + 2'd1);
            age_hs   <= hs_any ? 2'd0 : (age_hs   == 2'd3 ? 2'd3 : age_hs   + 2'd1);
            age_fh_p <= g_fh_p ? 2'd0 : (age_fh_p == 2'd3 ? 2'd3 : age_fh_p + 2'd1);
            age_fh_n <= g_fh_n ? 2'd0 : (age_fh_n == 2'd3 ? 2'd3 : age_fh_n + 2'd1);
            age_fl_p <= g_fl_p ? 2'd0 : (age_fl_p == 2'd3 ? 2'd3 : age_fl_p + 2'd1);
            age_fl_n <= g_fl_n ? 2'd0 : (age_fl_n == 2'd3 ? 2'd3 : age_fl_n + 2'd1);
        end

    assign c_usb_hs_p = g_hs_p;       assign c_usb_hs_n = g_hs_n;
    assign c_usb_fs_high_p = g_fh_p;  assign c_usb_fs_high_n = g_fh_n;
    assign c_usb_fs_low_p = g_fl_p;   assign c_usb_fs_low_n = g_fl_n;
    assign usb_hs_en = hs_en_q;  assign usb_hs_drv = hs_drv_q;  assign usb_fs_en = fs_en_q;
    assign usb_tx_dp = dp_q;     assign usb_tx_dn = dn_q;       assign usb_tx_oe = oe_q;
    assign st_tx_busy = busy;    assign st_tx_underrun = underrun;
    assign st_tx_blocked = blocked;  assign st_tx_armed = armed;

    // =====================================================================================
    // Receive domain
    // =====================================================================================
    reg [1:0] rrs;
    always @(posedge rx_clk or negedge rst_n)
        if (!rst_n) rrs <= 2'b00; else rrs <= {rrs[0], 1'b1};
    wire r_rst_n = rrs[1];

    wire sp, sn, dpos, dneg, rx_en_s, isl_s, drv_s, hsdrv_s, thr_disc_s;
    pt_usb_sync z_sp(.clk(rx_clk), .rst_n(r_rst_n), .d(s_detect_se_p),     .q(sp));
    pt_usb_sync z_sn(.clk(rx_clk), .rst_n(r_rst_n), .d(s_detect_se_n),     .q(sn));
    pt_usb_sync z_dp(.clk(rx_clk), .rst_n(r_rst_n), .d(s_detect_diff_pos), .q(dpos));
    pt_usb_sync z_dn(.clk(rx_clk), .rst_n(r_rst_n), .d(s_detect_diff_neg), .q(dneg));
    pt_usb_sync z_en(.clk(rx_clk), .rst_n(r_rst_n), .d(cfg_rx_en),         .q(rx_en_s));
    pt_usb_sync z_is(.clk(rx_clk), .rst_n(r_rst_n), .d(island_on),         .q(isl_s));
    pt_usb_sync z_dr(.clk(rx_clk), .rst_n(r_rst_n), .d(oe_q | hs_drv_q),   .q(drv_s));
    pt_usb_sync z_hd(.clk(rx_clk), .rst_n(r_rst_n), .d(hs_drv_q),          .q(hsdrv_s));
    pt_usb_sync z_td(.clk(rx_clk), .rst_n(r_rst_n), .d(cfg_thr_disc),      .q(thr_disc_s));

    // line state
    wire [1:0] line_db;
    wire       diff_db;
    pt_usb_debounce #(.W(2), .CW(8)) db_se(.clk(rx_clk), .rst_n(r_rst_n), .n(cfg_deb_se), .d({sn, sp}), .q(line_db));
    pt_usb_debounce #(.W(1), .CW(4)) db_df(.clk(rx_clk), .rst_n(r_rst_n), .n(cfg_deb_diff), .d(dpos | dneg), .q(diff_db));
    assign st_line = line_db;
    assign st_se0  = line_db == 2'b00;
    assign st_se1  = line_db == 2'b11;
    assign st_j    = line_db == (cfg_ls ? 2'b10 : 2'b01);
    assign st_k    = line_db == (cfg_ls ? 2'b01 : 2'b10);
    assign st_diff = diff_db;
    assign st_squelch = !diff_db && !thr_disc_s;
    always @(posedge rx_clk or negedge r_rst_n)
        if (!r_rst_n) st_disconnect <= 1'b0;
        else if (!thr_disc_s) st_disconnect <= 1'b0;
        else if (diff_db && hsdrv_s) st_disconnect <= 1'b1;

    // oversampled symbol recovery: the bit phase restarts at a change of the line and the symbol is
    // taken half a bit later. A second change within (div + 1) / 4 samples of a restart (the other
    // leg of a J/K crossover, seen as a short SE0 / SE1) does not restart the phase again.
    // Timing (rx_clk = wire_rx_clk, slow cells): the selected sample is registered once more before
    // the change detect (raw_a) and the symbol strobe is registered (stb_q, with the sample and the
    // receive enable delayed alike: raw_d, ron_q), so rx_data / rx_valid are two rx_clk later than
    // without these stages and nothing else changes. The other
    // compares are registered flags computed one cycle ahead against static values: wrap
    // (rph == cfg_rx_div, from weq = the plain compare and wz = rph was just cleared), hold_nz
    // (hold != 0), f19 (fill == 19), sq_q (since + 1 >= cfg_rx_quiet).
    // sq_q follows since one cycle later: fine while two symbol strobes are never in consecutive
    // cycles (cfg_rx_div >= 1).
    wire [1:0] raw = (cfg_rx_diff && (sp || sn) && (dpos != dneg)) ? {dneg, dpos} : {sn, sp};
    wire rx_on = rx_en_s && isl_s && (!drv_s || cfg_rx_echo);
    wire [7:0] half = {1'b0, cfg_rx_div[7:1]} + {7'd0, cfg_rx_div[0]};   // (div + 1) / 2
    wire [7:0] rdiv_m1 = cfg_rx_div - 8'd1;       // static
    wire       rdiv_z  = cfg_rx_div == 8'd0;
    wire [7:0] hold0   = {1'b0, half[7:1]};
    wire       quiet_z = cfg_rx_quiet == 5'd0;
    reg [1:0]  raw_a, raw_q, raw_d, last;
    reg [7:0]  rph, hold;
    reg        primed, active, stb_q, weq, wz, hold_nz, f19, sq_q, ron_a, ron_q;
    reg [4:0]  since, fill;
    reg [39:0] rsh;
    wire stb     = rph == half;
    wire wrap    = wz ? rdiv_z : weq;             // rph == cfg_rx_div
    wire restart = raw_a != raw_q && !hold_nz;
    wire changed = raw_d != last;
    wire [4:0] since_i = since == 5'd31 ? 5'd31 : since + 5'd1;
    wire [4:0] since_n = changed ? 5'd0 : since_i;
    assign st_rx_active = active;

    always @(posedge rx_clk or negedge r_rst_n)
        if (!r_rst_n) begin
            raw_a <= 2'b00; raw_q <= 2'b00; raw_d <= 2'b00; last <= 2'b00; rph <= 8'd0; hold <= 8'd0; primed <= 1'b0; active <= 1'b0;
            stb_q <= 1'b0; weq <= 1'b0; wz <= 1'b0; hold_nz <= 1'b0; f19 <= 1'b0; sq_q <= 1'b0; ron_a <= 1'b0; ron_q <= 1'b0;
            since <= 5'd0; fill <= 5'd0; rsh <= 40'd0; rx_data <= 40'd0; rx_valid <= 1'b0;
        end else begin
            rx_valid <= 1'b0;
            raw_a <= raw;
            raw_q <= raw_a;
            raw_d <= raw_q;
            stb_q <= stb;
            ron_a <= rx_on;
            ron_q <= ron_a;
            sq_q  <= since_i >= cfg_rx_quiet;
            weq <= rph == rdiv_m1;
            wz  <= restart || wrap;
            if (restart || wrap) rph <= 8'd0; else rph <= rph + 8'd1;
            if (restart) begin hold <= hold0; hold_nz <= hold0 != 8'd0; end
            else if (hold_nz) begin hold <= hold - 8'd1; hold_nz <= hold != 8'd1; end
            if (!ron_q) begin
                primed <= 1'b0; active <= 1'b0; since <= 5'd0; fill <= 5'd0; f19 <= 1'b0;
            end else if (stb_q) begin
                last <= raw_d;
                if (!primed) begin primed <= 1'b1; since <= 5'd31; end
                else begin
                    since <= since_n;
                    if (active || changed) begin
                        active <= 1'b1;
                        rsh <= {raw_d, rsh[39:2]};
                        if (f19) begin
                            fill <= 5'd0; f19 <= 1'b0; rx_data <= {raw_d, rsh[39:2]}; rx_valid <= 1'b1;
                            if (changed ? quiet_z : sq_q) active <= 1'b0;   // bursts end on a quad boundary
                        end else begin fill <= fill + 5'd1; f19 <= fill == 5'd18; end
                    end
                end
            end
        end
endmodule
`default_nettype wire
