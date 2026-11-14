// Self-checking bench for rtl/pt_usb.sv (run through verification/check_usb.py, which also runs the mutants).
// Prints "TB_PT_USB PASS" or "TB_PT_USB FAIL <n>".
`timescale 1ps/1ps
`default_nettype none
module tb_pt_usb;
    localparam integer TCK = 20834;          // 48 MHz
    localparam [1:0] J = 2'b01, K = 2'b10, SE0 = 2'b00, Z = 2'b11;

    reg rst_n = 0, island_on = 1, fault = 0;
    reg tx_clk = 0, rx_clk = 0;
    always #(TCK/2) tx_clk = ~tx_clk;
    initial begin #7000; forever #(TCK/2) rx_clk = ~rx_clk; end

    reg [1:0] cfg_branch = 0, cfg_force_sym = Z, cfg_bbm = 0;
    reg cfg_active = 0, cfg_hs_tx_en = 0, cfg_fs_drive_en = 0, cfg_hs_sym = 0, cfg_force_en = 0;
    reg cfg_ls_slow = 0, cfg_term_on = 0;
    reg [7:0] cfg_tx_div = 3, cfg_rx_div = 3, cfg_deb_se = 9;
    reg [39:0] tx_data = 0;
    reg tx_valid = 0, hs_tx_active = 0;
    reg cfg_rx_en = 0, cfg_rx_diff = 0, cfg_rx_echo = 0, cfg_ls = 0, cfg_thr_disc = 0;
    reg [4:0] cfg_rx_quiet = 8;
    reg [3:0] cfg_deb_diff = 1;
    wire tx_ready;
    wire hs_p, hs_n, fh_p, fh_n, fl_p, fl_n;
    wire usb_hs_en, usb_hs_drv, usb_fs_en, usb_tx_dp, usb_tx_dn, usb_tx_oe;
    wire st_tx_busy, st_tx_underrun, st_tx_blocked, st_tx_armed;
    wire [39:0] rx_data;
    wire rx_valid, st_rx_active, st_j, st_k, st_se0, st_se1, st_diff, st_squelch, st_disconnect;
    wire [1:0] st_line;

    // line: either an external stimulus or the pad model driven by the gates (loopback)
    reg loop = 0, ext_p = 0, ext_n = 0, ext_dpos = 0, ext_dneg = 0, diff_from_line = 1;
    reg pad_p = 1, pad_n = 0;
    wire gate_fs = fh_p | fh_n | fl_p | fl_n;
    wire gate_hs = hs_p | hs_n;
    always @(fh_p or fl_p or fh_n or fl_n) begin
        if (!(fh_p | fl_p | fh_n | fl_n)) begin pad_p = 1; pad_n = 0; end          // released: pull-up idle (full speed J)
        else begin
            if (fh_p) pad_p = 1; else if (fl_p) pad_p = 0;     // an undriven leg holds its level
            if (fh_n) pad_n = 1; else if (fl_n) pad_n = 0;
        end
    end
    wire line_p = loop ? pad_p : ext_p;
    wire line_n = loop ? pad_n : ext_n;
    wire det_dpos = diff_from_line ? (line_p & ~line_n) : ext_dpos;
    wire det_dneg = diff_from_line ? (line_n & ~line_p) : ext_dneg;

    pt_usb dut(
        .rst_n(rst_n), .island_on(island_on), .fault(fault), .tx_clk(tx_clk),
        .cfg_branch(cfg_branch), .cfg_active(cfg_active), .cfg_hs_tx_en(cfg_hs_tx_en),
        .cfg_fs_drive_en(cfg_fs_drive_en), .cfg_hs_sym(cfg_hs_sym), .cfg_force_en(cfg_force_en),
        .cfg_force_sym(cfg_force_sym), .cfg_ls_slow(cfg_ls_slow), .cfg_term_on(cfg_term_on),
        .cfg_tx_div(cfg_tx_div), .cfg_bbm(cfg_bbm), .tx_data(tx_data), .tx_valid(tx_valid), .tx_ready(tx_ready),
        .hs_tx_active(hs_tx_active),
        .c_usb_hs_p(hs_p), .c_usb_hs_n(hs_n), .c_usb_fs_high_p(fh_p), .c_usb_fs_high_n(fh_n),
        .c_usb_fs_low_p(fl_p), .c_usb_fs_low_n(fl_n),
        .usb_hs_en(usb_hs_en), .usb_hs_drv(usb_hs_drv), .usb_fs_en(usb_fs_en),
        .usb_tx_dp(usb_tx_dp), .usb_tx_dn(usb_tx_dn), .usb_tx_oe(usb_tx_oe),
        .st_tx_busy(st_tx_busy), .st_tx_underrun(st_tx_underrun), .st_tx_blocked(st_tx_blocked),
        .st_tx_armed(st_tx_armed),
        .rx_clk(rx_clk), .s_detect_diff_pos(det_dpos), .s_detect_diff_neg(det_dneg),
        .s_detect_se_p(line_p), .s_detect_se_n(line_n),
        .cfg_rx_en(cfg_rx_en), .cfg_rx_diff(cfg_rx_diff), .cfg_rx_echo(cfg_rx_echo), .cfg_ls(cfg_ls),
        .cfg_thr_disc(cfg_thr_disc), .cfg_rx_div(cfg_rx_div), .cfg_rx_quiet(cfg_rx_quiet),
        .cfg_deb_se(cfg_deb_se), .cfg_deb_diff(cfg_deb_diff),
        .rx_data(rx_data), .rx_valid(rx_valid), .st_rx_active(st_rx_active), .st_line(st_line),
        .st_j(st_j), .st_k(st_k), .st_se0(st_se0), .st_se1(st_se1), .st_diff(st_diff),
        .st_squelch(st_squelch), .st_disconnect(st_disconnect));

    integer errors = 0;
    task fail(input [8*64-1:0] msg);
        begin errors = errors + 1; if (errors <= 30) $display("  FAIL @%0t ps: %0s", $time, msg); end
    endtask
    task chk(input cond, input [8*64-1:0] msg); begin if (cond !== 1'b1) fail(msg); end endtask

    // ---------------- always-on safety checkers (these are the hard requirements)
    time t_fhp = 0, t_flp = 0, t_fhn = 0, t_fln = 0, t_fs = 0, t_hs = 0, t_fsen = 0, t_hsen = 0;
    integer min_gap = 1 << 30;                    // smallest observed high/low gap on one leg, ps
    wire [63:0] need = (1 + cfg_bbm) * TCK - 20;
    always @(negedge fh_p) t_fhp = $time;
    always @(negedge fl_p) t_flp = $time;
    always @(negedge fh_n) t_fhn = $time;
    always @(negedge fl_n) t_fln = $time;
    always @(negedge gate_fs) t_fs = $time;
    always @(negedge gate_hs) t_hs = $time;
    always @(negedge usb_fs_en) t_fsen = $time;
    always @(negedge usb_hs_en) t_hsen = $time;
    task leg(input other, input time t_other, input [8*64-1:0] msg);
        integer g;
        begin
            g = $time - 1 - t_other;
            if (g < min_gap) min_gap = g;
            if (other || g < need) fail(msg);
        end
    endtask
    always @(posedge fh_p) begin #1; leg(fl_p, t_flp, "D+ high side on without break after low side"); end
    always @(posedge fl_p) begin #1; leg(fh_p, t_fhp, "D+ low side on without break after high side"); end
    always @(posedge fh_n) begin #1; leg(fl_n, t_fln, "D- high side on without break after low side"); end
    always @(posedge fl_n) begin #1; leg(fh_n, t_fhn, "D- low side on without break after high side"); end
    always @(posedge gate_fs) begin #1; if (gate_hs || usb_hs_en || $time - 1 - t_hs < need) fail("FS gate on with / right after HS"); end
    always @(posedge gate_hs) begin #1; if (gate_fs || usb_fs_en || $time - 1 - t_fs < need) fail("HS gate on with / right after FS"); end
    always @(posedge usb_fs_en) begin #1; if (usb_hs_en || $time - 1 - t_hsen < need) fail("FS_EN with / right after HS_EN"); end
    always @(posedge usb_hs_en) begin #1; if (usb_fs_en || $time - 1 - t_fsen < need) fail("HS_EN with / right after FS_EN"); end
    wire any_drive = gate_fs | gate_hs | usb_hs_en | usb_hs_drv | usb_fs_en | usb_tx_dp | usb_tx_dn | usb_tx_oe;
    always @(any_drive or rst_n or fault or island_on) begin
        #2; if ((!rst_n || fault || !island_on) && any_drive !== 1'b0) fail("driver output not off under reset / fault / island off");
    end
    always @(negedge tx_clk) begin
        if (usb_tx_dp && usb_tx_dn) fail("SE1 requested from the pre-driver");
        if (fh_p && fh_n) fail("SE1 driven");
        if ((usb_tx_dp || usb_tx_dn) && !usb_tx_oe) fail("TX_D without TX_OE");
        if (usb_hs_drv && !usb_hs_en) fail("HS_DRV without HS_EN");
    end

    // ---------------- helpers
    reg [1:0] exp_sym [0:511];
    reg [1:0] rxs [0:1023];
    integer rx_n = 0, ri;
    always @(posedge rx_clk) if (rx_valid) begin
        for (ri = 0; ri < 20; ri = ri + 1) rxs[rx_n + ri] = rx_data[2*ri +: 2];
        rx_n = rx_n + 20;
    end
    task clks(input integer n); begin repeat (n) @(posedge tx_clk); #1; end endtask
    task send(input [39:0] q);
        begin
            tx_data = q; tx_valid = 1;
            @(negedge tx_clk); while (!tx_ready) @(negedge tx_clk);
            @(posedge tx_clk); #1; tx_valid = 0;
        end
    endtask
    task all_off(input [8*64-1:0] msg); begin chk(any_drive === 1'b0, msg); end endtask
    task cfg_off;
        begin
            cfg_branch = 0; cfg_active = 0; cfg_hs_tx_en = 0; cfg_fs_drive_en = 0; cfg_hs_sym = 0;
            cfg_force_en = 0; cfg_force_sym = Z; cfg_ls_slow = 0; cfg_term_on = 0; hs_tx_active = 0; clks(8);
        end
    endtask
    task cfg_fs(input [7:0] div, input [1:0] bbm);
        begin cfg_tx_div = div; cfg_bbm = bbm; cfg_branch = 2; cfg_active = 1; cfg_fs_drive_en = 1; clks(10); end
    endtask
    task cfg_hs(input [1:0] bbm);
        begin cfg_bbm = bbm; cfg_branch = 1; cfg_active = 1; cfg_hs_tx_en = 1; clks(10); end
    endtask
    task chk_fs_sym(input [1:0] s, input integer k);
        reg [3:0] e;
        begin
            case (s) J: e = 4'b1001; K: e = 4'b0110; SE0: e = 4'b0101; default: e = 4'b0000; endcase
            if ({fh_p, fl_p, fh_n, fl_n} !== e || gate_hs !== 1'b0) begin
                $display("  symbol %0d: expected %b, gates fh_p fl_p fh_n fl_n = %b%b%b%b", k, s, fh_p, fl_p, fh_n, fl_n);
                fail("FS gate pattern");
            end
            chk(usb_fs_en === 1'b1 && usb_hs_en === 1'b0, "FS_EN during FS stream");
            chk(usb_tx_oe === (s != Z) && usb_tx_dp === (s == J) && usb_tx_dn === (s == K), "pre-driver TX_DP/TX_DN/TX_OE");
        end
    endtask
    task chk_hs_sym(input [1:0] s, input integer k);
        begin
            if ({hs_p, hs_n} !== {s == J, s == K} || gate_fs !== 1'b0) begin
                $display("  symbol %0d: expected %b, gates hs_p hs_n = %b%b", k, s, hs_p, hs_n);
                fail("HS static gate pattern");
            end
            chk(usb_hs_en === 1'b1 && usb_fs_en === 1'b0 && usb_hs_drv === 1'b0, "HS_EN during HS symbol stream");
            chk(usb_tx_oe === (s != Z) && usb_tx_dp === (s == J) && usb_tx_dn === (s == K), "pre-driver levels (HS)");
        end
    endtask
    // send exp_sym[0..n-1] (padded with released symbols) and check every symbol on the gates
    integer sq, sk, ck;
    reg [39:0] sw;
    task run_tx(input integer n, input integer cyc, input hs);
        begin
            fork
                for (sq = 0; sq * 20 < n; sq = sq + 1) begin
                    for (sk = 0; sk < 20; sk = sk + 1) sw[2*sk +: 2] = (sq*20 + sk < n) ? exp_sym[sq*20 + sk] : Z;
                    send(sw);
                end
                begin
                    if (hs) wait (gate_hs); else wait (gate_fs);
                    for (ck = 0; ck <= n; ck = ck + 1) begin
                        #(cyc * TCK - TCK/2);
                        if (hs) chk_hs_sym(ck < n ? exp_sym[ck] : Z, ck); else chk_fs_sym(ck < n ? exp_sym[ck] : Z, ck);
                        #(TCK/2);
                    end
                end
            join
        end
    endtask
    // K J K J K J K K, pseudo-random J/K with runs <= 7, SE0 SE0 J
    integer pk, run;
    reg [15:0] lfsr;
    reg [1:0] ps;
    task pattern(input integer body, output integer n);
        begin
            for (pk = 0; pk < 8; pk = pk + 1) exp_sym[pk] = (pk == 7 || !pk[0]) ? K : J;
            ps = K; run = 2;
            for (pk = 8; pk < 8 + body; pk = pk + 1) begin
                lfsr = {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
                if (run == 7 || lfsr[0]) begin ps = ~ps; run = 1; end else run = run + 1;
                exp_sym[pk] = ps;
            end
            exp_sym[8 + body] = SE0; exp_sym[9 + body] = SE0; exp_sym[10 + body] = J;
            n = body + 11;
        end
    endtask
    // external line stimulus: bit period per ps; D+ changes skew ps before D- on a J/K crossover
    integer dk;
    reg [1:0] ds, dprev;
    task drive_line(input integer n, input integer per, input integer skew);
        begin
            dprev = J;
            for (dk = 0; dk < n; dk = dk + 1) begin
                ds = exp_sym[dk] == Z ? J : exp_sym[dk];
                if (ds[0] != dprev[0] && ds[1] != dprev[1] && skew > 0) begin
                    ext_p = ds[0]; #(skew); ext_n = ds[1]; #(per - skew);
                end else begin ext_p = ds[0]; ext_n = ds[1]; #(per); end
                dprev = ds;
            end
            ext_p = 1; ext_n = 0;
        end
    endtask
    integer xk;
    task chk_rx(input integer n, input [8*24-1:0] name);
        integer bad;
        begin
            bad = 0;
            if (rx_n < n || rx_n % 20 != 0 || rx_n > n + 20 + cfg_rx_quiet) bad = 1;
            for (xk = 0; xk < rx_n; xk = xk + 1)
                if (rxs[xk] !== (xk < n && exp_sym[xk] != Z ? exp_sym[xk] : J)) bad = bad + 1;
            if (bad != 0 || st_rx_active !== 1'b0) begin
                $display("  RX %0s: %0d symbols for %0d sent, %0d wrong, active=%b", name, rx_n, n, bad, st_rx_active);
                fail("RX recovery");
                for (xk = 0; xk < rx_n && xk < 60; xk = xk + 1) $write("%b/%b ", rxs[xk], exp_sym[xk]);
                $write("\n");
            end else $display("  RX %0s: %0d symbols recovered (%0d sent + idle)", name, rx_n, n);
        end
    endtask

    integer n, i, seen;
    initial begin
        lfsr = 16'hACE1;
        // ---- 1. reset values
        #(3 * TCK);
        all_off("1: outputs during reset");
        chk(rx_valid === 1'b0 && st_disconnect === 1'b0 && st_tx_armed === 1'b0, "1: status during reset");
        rst_n = 1; clks(8);
        all_off("1: outputs after reset with all fields 0");
        chk(st_tx_armed === 1'b1 && st_tx_blocked === 1'b0 && st_tx_underrun === 1'b0, "1: armed after reset");
        chk(tx_ready === 1'b0, "1: tx_ready while off");
        chk(st_squelch === 1'b1 && st_se0 === 1'b1, "1: line status with the detector outputs low");
        // enable fields alone must not drive anything (no symbols, no force)
        cfg_fs(3, 0); chk(usb_fs_en === 1'b1 && !gate_fs && !usb_tx_oe && tx_ready === 1'b1, "1: FS selected, idle = released");

        // ---- 2. FS stream: J/K/SE0/release on the gates, break-before-make 1 cycle then 3 cycles
        pattern(40, n);
        min_gap = 1 << 30; run_tx(n, 4, 0);
        chk(min_gap == TCK, "2: break-before-make gap is one tx_clk cycle at cfg_bbm = 0");
        chk(st_tx_underrun === 1'b0, "2: no underrun after a stream that ends released");
        $display("  FS stream %0d symbols at 4 clk/bit: gate patterns ok, measured BBM gap %0d ps", n, min_gap);
        cfg_off; cfg_fs(3, 2);
        min_gap = 1 << 30; run_tx(n, 4, 0);
        chk(min_gap == 3 * TCK, "2: break-before-make gap is three cycles at cfg_bbm = 2");
        $display("  FS stream, cfg_bbm = 2: measured BBM gap %0d ps", min_gap);
        // low speed timing (32 clk per bit)
        cfg_off; cfg_fs(31, 1); pattern(4, n); run_tx(n, 32, 0);
        // underrun: a quad that ends while still driving
        cfg_off; cfg_fs(3, 0);
        for (i = 0; i < 20; i = i + 1) exp_sym[i] = i[0] ? K : J;
        run_tx(20, 4, 0);
        clks(4); chk(st_tx_underrun === 1'b1 && !gate_fs, "2: underrun releases the line and is reported");
        cfg_off; chk(st_tx_underrun === 1'b0, "2: underrun cleared by fields = 0");

        // ---- 3. interlocks
        cfg_fs(3, 0); cfg_force_sym = J; cfg_force_en = 1; clks(6);
        chk({fh_p, fl_p, fh_n, fl_n} === 4'b1001, "3: forced J");
        cfg_force_sym = K; clks(6); chk({fh_p, fl_p, fh_n, fl_n} === 4'b0110, "3: forced K");
        cfg_force_sym = SE0; clks(6); chk({fh_p, fl_p, fh_n, fl_n} === 4'b0101, "3: forced SE0");
        cfg_force_sym = J; clks(6);
        // fault, between clock edges: off without a clock, stays off until the fields were 0
        #(TCK/3); fault = 1; #50; all_off("3: fault forces every output low asynchronously");
        clks(3); fault = 0; clks(12);
        all_off("3: no drive after fault release until re-armed");
        chk(st_tx_blocked === 1'b1 && st_tx_armed === 1'b0, "3: blocked / not armed after fault");
        cfg_force_en = 0; cfg_off; cfg_fs(3, 0); cfg_force_sym = J; cfg_force_en = 1; clks(6);
        chk({fh_p, fl_p, fh_n, fl_n} === 4'b1001, "3: drive again after re-arm");
        // island off
        #(TCK/4); island_on = 0; #50; all_off("3: island off forces every output low");
        clks(2); island_on = 1; clks(12); all_off("3: no drive after island on until re-armed");
        cfg_force_en = 0; cfg_off; cfg_fs(3, 0); cfg_force_sym = J; cfg_force_en = 1; clks(6);
        chk(gate_fs === 1'b1, "3: drive again after island re-arm");
        // reset
        #(TCK/5); rst_n = 0; #50; all_off("3: reset forces every output low"); clks(2); rst_n = 1; clks(12);
        all_off("3: no drive after reset with fields still set");
        cfg_force_en = 0; cfg_off; cfg_fs(3, 0); cfg_force_sym = J; cfg_force_en = 1; clks(6); chk(gate_fs === 1'b1, "3: drive after reset re-arm");
        // each enable field
        cfg_fs_drive_en = 0; clks(5); all_off("3: usbfs.drive_enable = 0"); cfg_fs_drive_en = 1; clks(8); chk(gate_fs === 1'b1, "3: drive_enable back");
        cfg_active = 0; clks(5); all_off("3: state != active"); cfg_active = 1; clks(8); chk(gate_fs === 1'b1, "3: active back");
        cfg_branch = 3; clks(5); all_off("3: branch code 3 = off"); cfg_branch = 2; clks(8);
        cfg_branch = 0; clks(5); all_off("3: branch off"); cfg_branch = 2; clks(8); chk(gate_fs === 1'b1, "3: branch back");
        // termination on refuses FS
        cfg_term_on = 1; clks(5); all_off("3: FS refused while the pad termination is on");
        chk(st_tx_blocked === 1'b1, "3: blocked flag (termination)"); cfg_term_on = 0; clks(8); chk(gate_fs === 1'b1, "3: FS back");
        // FS -> HS -> FS with both request sets present: never both, gap >= 1 + bbm (always-on checkers)
        cfg_bbm = 2; cfg_hs_tx_en = 1; clks(6);
        chk(gate_fs === 1'b1 && !usb_hs_en, "3: HS enable field does not disturb the FS branch");
        cfg_branch = 1; clks(12);
        chk(hs_p === 1'b1 && hs_n === 1'b0 && !gate_fs && usb_hs_en && !usb_fs_en, "3: HS static J after the branch change");
        cfg_force_sym = K; clks(4); chk(hs_n === 1'b1 && hs_p === 1'b0, "3: HS static K");
        cfg_force_sym = SE0; clks(4); chk(!gate_hs && usb_tx_oe, "3: HS static SE0 = both switches off");
        cfg_force_sym = J; clks(4);
        cfg_branch = 2; clks(12);
        chk({fh_p, fl_p, fh_n, fl_n} === 4'b1001 && !gate_hs && !usb_hs_en, "3: FS J after the branch change back");
        cfg_branch = 1; clks(12);
        // LS_SLOW refuses HS
        cfg_ls_slow = 1; clks(5); all_off("3: HS refused while LS_SLOW = 1"); cfg_ls_slow = 0; clks(8); chk(hs_p === 1'b1, "3: HS back");
        cfg_hs_tx_en = 0; clks(5); all_off("3: usbhs.tx_enable = 0");
        cfg_off;

        // ---- 4. HS: packet envelope and static symbol stream
        cfg_hs(0);
        chk(usb_hs_en === 1'b1 && !usb_hs_drv && !gate_hs && tx_ready === 1'b0, "4: HS selected, idle; quads are not taken in packet mode");
        hs_tx_active = 1; clks(2); chk(usb_hs_drv === 1'b1 && !gate_hs && !usb_tx_oe, "4: HS_DRV follows hs_tx_active");
        hs_tx_active = 0; clks(1); chk(usb_hs_drv === 1'b0, "4: HS_DRV off one cycle after hs_tx_active");
        cfg_hs_sym = 1; clks(6); hs_tx_active = 1; clks(3); chk(usb_hs_drv === 1'b0, "4: no HS_DRV in symbol mode"); hs_tx_active = 0;
        for (i = 0; i < 12; i = i + 1) exp_sym[i] = i == 5 ? SE0 : (i[0] ? J : K);
        run_tx(12, 4, 1);
        cfg_off;

        // ---- 5. line state, debounce, squelch, disconnect
        loop = 0; ext_p = 1; ext_n = 0; repeat (20) @(posedge rx_clk); #1;
        chk(st_j && !st_k && !st_se0 && !st_se1 && st_line === 2'b01, "5: J");
        ext_p = 0; repeat (6) @(posedge rx_clk); #1; ext_p = 1;        // SE0 glitch, 6 of the 10 needed samples
        seen = 0; repeat (20) begin @(posedge rx_clk); #1; if (!st_j) seen = 1; end
        chk(seen == 0, "5: a 6-sample SE0 glitch is debounced");
        ext_p = 0; repeat (9) @(posedge rx_clk); #1; chk(st_j === 1'b1, "5: SE0 not reported before the debounce time");
        repeat (6) @(posedge rx_clk); #1; chk(st_se0 === 1'b1 && !st_j, "5: SE0 reported after the debounce time");
        ext_n = 1; repeat (20) @(posedge rx_clk); #1; chk(st_k === 1'b1 && st_line === 2'b10, "5: K");
        cfg_ls = 1; #1; chk(st_j === 1'b1 && !st_k, "5: low speed: D- high is J"); cfg_ls = 0;
        ext_p = 1; repeat (20) @(posedge rx_clk); #1; chk(st_se1 === 1'b1, "5: SE1");
        ext_p = 0; ext_n = 0; diff_from_line = 0; repeat (20) @(posedge rx_clk); #1;
        chk(st_squelch === 1'b1 && !st_diff, "5: squelched");
        ext_dpos = 1; repeat (1) @(posedge rx_clk); #1; ext_dpos = 0;
        seen = 0; repeat (10) begin @(posedge rx_clk); #1; if (!st_squelch) seen = 1; end
        chk(seen == 0, "5: one-sample envelope glitch is debounced");
        fork
            repeat (30) begin ext_dpos = 1; ext_dneg = 0; #(3 * TCK); ext_dpos = 0; ext_dneg = 1; #(3 * TCK); end
            begin repeat (12) @(posedge rx_clk); #1; chk(!st_squelch && st_diff, "5: unsquelched on a toggling differential signal"); end
        join
        ext_dneg = 0; repeat (10) @(posedge rx_clk); #1; chk(st_squelch === 1'b1, "5: squelched again");
        // disconnect: threshold at the disconnect level, only counted while this chip transmits HS
        cfg_thr_disc = 1; ext_dpos = 1; repeat (10) @(posedge rx_clk); #1;
        chk(!st_squelch && !st_disconnect, "5: no squelch report at the disconnect threshold; no disconnect without HS transmit");
        ext_dpos = 0; cfg_hs(0); hs_tx_active = 1; clks(10);
        chk(!st_disconnect, "5: HS transmit below the disconnect threshold");
        ext_dpos = 1; clks(10); chk(st_disconnect === 1'b1, "5: disconnect");
        ext_dpos = 0; hs_tx_active = 0; clks(10); chk(st_disconnect === 1'b1, "5: disconnect is sticky");
        cfg_thr_disc = 0; clks(6); chk(!st_disconnect, "5: disconnect cleared with the threshold field");
        cfg_off; diff_from_line = 1;

        // ---- 6. RX recovery from the oversampled comparators
        ext_p = 1; ext_n = 0; cfg_rx_en = 1; cfg_rx_div = 3; repeat (30) @(posedge rx_clk);
        chk(rx_n == 0, "6: nothing recorded on an idle line");
        pattern(100, n);
        rx_n = 0; #3333; drive_line(n, 83333 + 833, 15000); #(40 * 83333); chk_rx(n, "FS +1.0% period, SE");
        rx_n = 0; #7777; drive_line(n, 83333 - 833, 15000); #(40 * 83333); chk_rx(n, "FS -1.0% period, SE");
        cfg_rx_diff = 1;
        rx_n = 0; #1234; drive_line(n, 83333 + 400, 9000); #(40 * 83333); chk_rx(n, "FS +0.5% period, DIFF");
        cfg_rx_diff = 0;
        cfg_rx_div = 31; pattern(40, n);
        for (i = 0; i < n; i = i + 1) if (exp_sym[i] == J || exp_sym[i] == K) exp_sym[i] = ~exp_sym[i];   // low speed polarity
        ext_p = 0; ext_n = 1; exp_sym[n] = Z;
        #(40 * 666667);
        rx_n = 0; n = n - 1;                      // (the closing J of full speed is K here; drop it, idle is D- high)
        begin : ls_rx
            integer good;
            // idle for the low-speed check is 10, so compare here instead of chk_rx
            dprev = K;
            for (dk = 0; dk < n; dk = dk + 1) begin
                ds = exp_sym[dk];
                if (ds[0] != dprev[0] && ds[1] != dprev[1]) begin ext_p = ds[0]; #(30000); ext_n = ds[1]; #(666667 + 10000 - 30000); end
                else begin ext_p = ds[0]; ext_n = ds[1]; #(666667 + 10000); end
                dprev = ds;
            end
            ext_p = 0; ext_n = 1; #(40 * 666667);
            good = (rx_n >= n) && (rx_n % 20 == 0) && !st_rx_active;
            for (xk = 0; xk < rx_n; xk = xk + 1) if (rxs[xk] !== (xk < n ? exp_sym[xk] : K)) good = 0;
            if (!good) begin $display("  RX LS: %0d symbols for %0d sent", rx_n, n); fail("RX recovery, low speed"); end
            else $display("  RX LS +1.5%% period: %0d symbols recovered (%0d sent + idle)", rx_n, n);
        end
        // disabled receiver records nothing
        cfg_rx_en = 0; cfg_rx_div = 3; ext_p = 1; ext_n = 0; repeat (10) @(posedge rx_clk); rx_n = 0;
        pattern(20, n); drive_line(n, 83333, 0); #(30 * 83333); chk(rx_n == 0, "6: receiver disabled");

        // ---- 7. loopback: TX symbols -> gates -> pad model -> comparators -> RX symbols
        loop = 1; cfg_rx_en = 1; cfg_rx_echo = 1; cfg_fs(3, 0); repeat (30) @(posedge rx_clk);
        pattern(60, n); rx_n = 0; run_tx(n, 4, 0); #(40 * 83333); chk_rx(n, "loopback (echo on)");
        cfg_rx_echo = 0; clks(8); rx_n = 0; run_tx(n, 4, 0); #(40 * 83333);
        chk(rx_n == 0, "7: own transmission is not recorded with echo off");
        cfg_off;

        if (errors == 0) $display("TB_PT_USB PASS");
        else $display("TB_PT_USB FAIL %0d", errors);
        $finish;
    end
    initial begin #2000000000; $display("TB_PT_USB FAIL timeout"); $finish; end
endmodule
`default_nettype wire
