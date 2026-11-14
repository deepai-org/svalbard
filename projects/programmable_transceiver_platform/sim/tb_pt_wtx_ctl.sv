// Self-checking bench for rtl/pt_wtx_ctl.sv. Run by verification/check_wtx_ctl.py (base must pass, mutants must fail).
// REF_CLK 50 MHz (20 ns). wire_tx_clk is modelled as pt_wiredtx WORD_CLK40: low while SER_EN = 0, running after it.
`timescale 1ns/1ps
`default_nettype none
module tb_pt_wtx_ctl;
    localparam real    TREF = 20.0;
    localparam integer PRE = 2, POST = 8, LOAD = 42, TMO = 100, OFFC = 16;
    reg rst_n = 0, ref_clk = 0, ref_run = 1;   // reset asserted from time zero
    reg island_on_wired = 0, island_on_pll = 0, vreg_tx_ok = 0, fault = 0, fc_tx_in_tol = 0, txpad_ready = 1;
    reg cfg_ring_en = 0; reg [1:0] cfg_ring_n = 0; reg cfg_ring_band = 1; reg [7:0] cfg_ring_lock_time = 8'd3;
    reg [1:0] cfg_ring_ready_sel = 0, cfg_wtx_state = 0, cfg_rate_mode = 0, cfg_branch = 0;
    reg cfg_idle = 1, cfg_wtx_ext = 0, cfg_post_pol = 0; reg [7:0] cfg_post_code = 0; reg cfg_term_req = 0, cfg_stage_tmds = 0;
    wire c_pll_tx_en, c_pll_tx_n4, c_pll_tx_n8, c_pll_tx_band, c_wiredtx_ser_en, c_wiredtx_mode_h, c_wiredtx_mode_f;
    wire c_wiredtx_bias_en, c_txpad_req_main, c_txpad_req_post, c_txpad_req_detect, c_txpad_req_term;
    wire [1:0] c_wtxfb_branch, c_wtxfb_state; wire c_wtxfb_idle, c_wtxfb_stage_tmds;
    wire wire_tx_request, wire_tx_up, tx_ring_ready, st_seq_fault; wire [2:0] st_state;
    reg wclk = 0; real whalf = 8.0;
    wire wire_tx_clk = wclk & c_wiredtx_ser_en;

    pt_wtx_ctl #(.REF_PS(20000), .PAD_PRE_CYCLES(PRE), .PAD_POST_CYCLES(POST), .PAD_LOAD_CYCLES(LOAD),
                 .PAD_TIMEOUT_CYCLES(TMO), .OFF_CYCLES(OFFC)) dut(.*);

    always #(TREF/2) if (ref_run) ref_clk = ~ref_clk; else ref_clk = 1'b0;
    always begin
        wait (c_wiredtx_ser_en === 1'b1);
        #3.7;                                   // arbitrary phase against REF_CLK
        while (c_wiredtx_ser_en === 1'b1) begin wclk = 1; #(whalf); wclk = 0; #(whalf); end
    end

    integer errors = 0, checks = 0;
    task chk(input cond, input [639:0] msg);
        begin checks = checks + 1; if (cond !== 1'b1) begin errors = errors + 1; $display("ERROR t=%0t: %0s", $time, msg); end end
    endtask

    // ---------------------------------------------------------------- event bookkeeping
    real t_ring_up = 0, t_ser_up = 0, t_ser_dn = 0, t_main_up = 0, t_main_dn = 0, t_req_up = 0, t_req_dn = 0, t_rdy_up = 0;
    integer w_since_ser = 0, w_since_req_dn = 0;
    reg chk_timer = 1;     // SER_EN must come >= the lock time after the ring enable (timer mode)
    reg orderly = 0;       // a commanded (not forced) shutdown is in progress: reverse-order checks apply
    wire [31:0] lock_cycles = (cfg_ring_lock_time + 1) * 64;
    always @(posedge c_pll_tx_en) t_ring_up = $realtime;
    always @(posedge tx_ring_ready) t_rdy_up = $realtime;
    always @(posedge wire_tx_clk) begin
        w_since_ser = w_since_ser + 1;
        if (!wire_tx_request) w_since_req_dn = w_since_req_dn + 1;
    end
    always @(posedge c_wiredtx_ser_en) begin
        t_ser_up = $realtime; w_since_ser = 0;
        chk(tx_ring_ready === 1'b1, "SER_EN rose without tx_ring_ready");
        chk(c_pll_tx_en === 1'b1, "SER_EN rose with the ring disabled");
        if (chk_timer) chk($realtime - t_ring_up >= lock_cycles * TREF, "SER_EN rose before the ring lock time");
        chk(c_txpad_req_main === 1'b0 && wire_tx_request === 1'b0, "SER_EN rose with MAIN requested or data requested");
    end
    always @(negedge c_wiredtx_ser_en) begin
        t_ser_dn = $realtime;
        if (orderly) begin
            chk(c_txpad_req_main === 1'b0, "orderly stop: SER_EN fell with MAIN still requested");
            chk($realtime - t_main_dn >= OFFC * TREF, "orderly stop: SER_EN fell < OFF_CYCLES after the pad request");
        end
    end
    always @(posedge c_txpad_req_main) begin
        t_main_up = $realtime;
        if (!cfg_wtx_ext) begin
            chk(c_wiredtx_ser_en === 1'b1, "MAIN requested with the serializer stopped (not wtx_ext)");
            chk(w_since_ser >= 8, "MAIN requested before 8 word clocks after SER_EN");
        end
    end
    always @(negedge c_txpad_req_main) begin
        t_main_dn = $realtime;
        if (orderly) begin
            chk(wire_tx_request === 1'b0, "orderly stop: MAIN dropped with wire_tx_request high");
            chk(w_since_req_dn >= 8, "orderly stop: MAIN dropped < 8 word clocks after wire_tx_request");
        end
    end
    always @(posedge wire_tx_request) begin
        t_req_up = $realtime;
        chk(c_txpad_req_main === 1'b1 && c_wiredtx_ser_en === 1'b1, "wire_tx_request without MAIN and SER_EN");
        chk($realtime - t_main_up >= (POST + LOAD) * TREF, "wire_tx_request < pad settle time after MAIN");
        chk(w_since_ser >= 8, "wire_tx_request before the flush words");
        chk(wire_tx_up === 1'b1, "wire_tx_request without wire_tx_up");
    end
    always @(negedge wire_tx_request) begin t_req_dn = $realtime; w_since_req_dn = 0; end

    // ---------------------------------------------------------------- invariants, sampled every ns
    always #1 if (rst_n && $time > 100) begin
        chk(c_pll_tx_en === (cfg_ring_en & island_on_pll & vreg_tx_ok), "c_pll_tx_en equation");
        if (!island_on_pll) chk(c_pll_tx_en === 1'b0 && c_wiredtx_ser_en === 1'b0, "pll island off: ring or SER_EN on");
        if (!island_on_wired || fault)
            chk({c_txpad_req_main, c_txpad_req_post, c_txpad_req_detect, c_txpad_req_term, c_wiredtx_bias_en} === 5'd0,
                "pad request or bias enable with fault / wired island off");
        if (!island_on_wired || !c_pll_tx_en || cfg_wtx_ext) chk(c_wiredtx_ser_en === 1'b0, "SER_EN with island off / ring off / wtx_ext");
        if (c_wiredtx_ser_en) chk(tx_ring_ready === 1'b1 || !chk_timer, "SER_EN high without tx_ring_ready");
        chk(c_wiredtx_bias_en === (c_txpad_req_main | c_txpad_req_post | c_txpad_req_detect | c_txpad_req_term), "bias_en != OR of requests");
        chk(!(c_txpad_req_detect && (c_txpad_req_main || c_txpad_req_post || c_txpad_req_term)), "interlock conflict requested");
        chk(!(c_txpad_req_post && !c_txpad_req_main), "POST without MAIN");
        if (wire_tx_request) chk(c_wiredtx_ser_en === 1'b1, "wire_tx_request with SER_EN low");
        chk({c_wiredtx_mode_h, c_wiredtx_mode_f} === (cfg_rate_mode == 0 ? 2'b00 : cfg_rate_mode == 1 ? 2'b10 : cfg_rate_mode == 2 ? 2'b01 : 2'b00), "MODE_H/F decode");
        chk({c_pll_tx_n4, c_pll_tx_n8} === (cfg_ring_n == 2 ? 2'b10 : cfg_ring_n == 1 ? 2'b01 : 2'b00), "N4/N8 decode");
        chk(c_pll_tx_band === cfg_ring_band, "band");
        chk({c_wtxfb_branch, c_wtxfb_state, c_wtxfb_idle, c_wtxfb_stage_tmds} === {cfg_branch, cfg_wtx_state, cfg_idle, cfg_stage_tmds}, "wtxfb raw");
    end

    task refs(input integer n); begin repeat (n) @(posedge ref_clk); #1; end endtask
    task all_low(input [639:0] msg);
        chk({c_pll_tx_en, c_pll_tx_n4, c_pll_tx_n8, c_wiredtx_ser_en, c_wiredtx_mode_h, c_wiredtx_mode_f, c_wiredtx_bias_en,
             c_txpad_req_main, c_txpad_req_post, c_txpad_req_detect, c_txpad_req_term, wire_tx_request, wire_tx_up,
             tx_ring_ready, st_state, st_seq_fault} === 18'd0, msg);
    endtask
    // mission configuration: serial branch, post-cursor on, termination on, lock code 3 (256 cycles = 5.12 us)
    task mission; begin
        island_on_wired = 1; island_on_pll = 1; vreg_tx_ok = 1; cfg_ring_band = 1; cfg_ring_lock_time = 8'd3; cfg_ring_ready_sel = 0;
        cfg_branch = 2'd1; cfg_idle = 0; cfg_post_code = 8'd5; cfg_term_req = 1; cfg_wtx_state = 2'd2; cfg_ring_en = 1;
    end endtask
    task wait_run(input integer max_cycles, input [639:0] msg);
        integer k; begin
            k = 0; while (wire_tx_request !== 1'b1 && k < max_cycles) begin @(posedge ref_clk); k = k + 1; end
            #1 chk(wire_tx_request === 1'b1, msg);
        end
    endtask
    task wait_state(input [2:0] s, input integer max_cycles, input [639:0] msg);
        integer k; begin
            k = 0; while (st_state !== s && k < max_cycles) begin @(posedge ref_clk); k = k + 1; end
            #1 chk(st_state === s, msg);
        end
    endtask
    task stop_all; begin   // commanded stop, then ring off, everything at the register reset values
        orderly = 1; cfg_wtx_state = 0; wait_state(3'd0, 600, "stop: state machine did not reach OFF"); refs(20); orderly = 0;
        cfg_ring_en = 0; cfg_branch = 0; cfg_idle = 1; cfg_wtx_ext = 0; cfg_post_code = 0; cfg_post_pol = 0; cfg_term_req = 0;
        cfg_ring_ready_sel = 0; fc_tx_in_tol = 0; fault = 0; txpad_ready = 1;
        refs(160);   // a request change waits for a running pad transaction (<= PRE + TIMEOUT cycles)
        all_low("after stop_all: an output is not 0");
    end endtask

    integer i; real t0; reg e_main, e_post, e_det, e_term, e_ser, e_req;
    initial begin
        // ---- T0 reset values (register reset inputs: band 1, idle 1, everything else 0)
        #33 all_low("in reset: an output is not 0");
        chk(c_pll_tx_band === 1'b1 && c_wtxfb_idle === 1'b1 && c_wtxfb_branch === 2'd0 && c_wtxfb_state === 2'd0, "reset pass-through values");
        // sequential outputs stay 0 in reset whatever the configuration says
        mission; #40;
        chk({c_wiredtx_ser_en, c_txpad_req_main, c_txpad_req_post, c_txpad_req_detect, c_txpad_req_term, c_wiredtx_bias_en, wire_tx_request} === 7'd0,
            "in reset with a mission configuration: sequenced output not 0");
        cfg_ring_en = 0; cfg_wtx_state = 0; cfg_branch = 0; cfg_idle = 1; cfg_post_code = 0; cfg_term_req = 0;
        island_on_wired = 0; island_on_pll = 0; vreg_tx_ok = 0;
        #40 rst_n = 1; refs(20); all_low("after reset release: an output is not 0");

        // ---- T1 bring-up by timer, order and intervals
        t0 = $realtime; mission;
        wait_run(600, "T1: no wire_tx_request");
        chk(t_rdy_up - t_ring_up >= 256 * TREF && t_rdy_up - t_ring_up <= (256 + 8) * TREF, "T1: tx_ring_ready not (code+1)*64 cycles after the ring enable");
        chk(t_ser_up > t_rdy_up && t_main_up > t_ser_up && t_req_up > t_main_up, "T1: order ring -> ready -> SER_EN -> MAIN -> request");
        chk(c_txpad_req_post === 1'b1 && c_txpad_req_term === 1'b1 && c_txpad_req_detect === 1'b0 && c_wiredtx_bias_en === 1'b1, "T1: POST/TERM/bias");
        chk(st_state === 3'd3, "T1: state not RUN");
        $display("T1 bring-up (ns after ring enable): ready %0.0f  SER_EN %0.0f  MAIN %0.0f  wire_tx_request %0.0f",
                 t_rdy_up - t_ring_up, t_ser_up - t_ring_up, t_main_up - t_ring_up, t_req_up - t_ring_up);

        // ---- T2 register idle while running: data off, then pad off (power-down), serializer keeps running
        orderly = 1; cfg_idle = 1; refs(150);
        chk(wire_tx_request === 1'b0 && c_txpad_req_main === 1'b0 && c_txpad_req_post === 1'b0, "T2: idle did not drop request and MAIN/POST");
        chk(c_wiredtx_ser_en === 1'b1 && c_txpad_req_term === 1'b1 && st_state === 3'd2, "T2: SER_EN / TERM must stay in idle");
        chk(t_main_dn > t_req_dn, "T2: MAIN must drop after wire_tx_request");
        orderly = 0; cfg_idle = 0; wait_run(200, "T2: no restart after idle");

        // ---- T3 commanded shutdown (state active -> warm): reverse order, ring stays on
        orderly = 1; cfg_wtx_state = 2'd1; wait_state(3'd0, 600, "T3: no OFF");
        refs(4);
        chk(c_wiredtx_ser_en === 1'b0 && wire_tx_request === 1'b0 && c_txpad_req_main === 1'b0, "T3: outputs after stop");
        chk(t_req_dn < t_main_dn && t_main_dn < t_ser_dn, "T3: order request -> MAIN -> SER_EN");
        chk(c_pll_tx_en === 1'b1 && tx_ring_ready === 1'b1 && c_txpad_req_term === 1'b1, "T3: ring and TERM must stay");
        $display("T3 shutdown (ns): request->MAIN %0.0f  MAIN->SER_EN %0.0f", t_main_dn - t_req_dn, t_ser_dn - t_main_dn);
        orderly = 0;
        // restart with the ring already ready (slow word clock: 36 MHz)
        whalf = 13.9; chk_timer = 0; cfg_wtx_state = 2'd2; wait_run(300, "T3: no restart"); chk_timer = 1;
        stop_all; whalf = 8.0;

        // ---- T4 ready by frequency flag (sel 1: timer OR flag), long timer
        mission; cfg_ring_lock_time = 8'd255; cfg_ring_ready_sel = 2'd1; chk_timer = 0;
        refs(100); chk(tx_ring_ready === 1'b0 && c_wiredtx_ser_en === 1'b0, "T4: ready before flag or timer");
        fc_tx_in_tol = 1; refs(8); chk(tx_ring_ready === 1'b1, "T4: frequency flag did not give ready");
        wait_run(200, "T4: no run by frequency flag");
        stop_all;
        // sel 2 (flag only): a flag that was already high when the ring is enabled is stale and must not count
        fc_tx_in_tol = 1; mission; cfg_ring_lock_time = 8'd0; cfg_ring_ready_sel = 2'd2;
        refs(400); chk(tx_ring_ready === 1'b0 && c_wiredtx_ser_en === 1'b0, "T4: stale frequency flag accepted / timer used in sel 2");
        fc_tx_in_tol = 0; refs(10); fc_tx_in_tol = 1; wait_run(200, "T4: no run in sel 2");
        // flag lost in sel 2: commanded-style stop (reverse order)
        orderly = 1; fc_tx_in_tol = 0; wait_state(3'd0, 600, "T4: flag loss did not stop"); refs(4);
        chk(c_wiredtx_ser_en === 1'b0 && t_req_dn < t_main_dn && t_main_dn < t_ser_dn, "T4: flag loss order");
        orderly = 0; stop_all; chk_timer = 1;
        // sel 0 ignores the flag
        mission; cfg_ring_lock_time = 8'd7; fc_tx_in_tol = 0; refs(10); fc_tx_in_tol = 1; refs(300);
        chk(tx_ring_ready === 1'b0 && c_wiredtx_ser_en === 1'b0, "T4: sel 0 used the frequency flag");
        wait_run(600, "T4: no run by timer code 7");
        chk(t_rdy_up - t_ring_up >= 512 * TREF && t_rdy_up - t_ring_up <= 520 * TREF, "T4: code 7 lock time");
        stop_all;

        // ---- T5 override
        mission; cfg_ring_lock_time = 8'd255; cfg_ring_ready_sel = 2'd3; chk_timer = 0; refs(12);
        chk(tx_ring_ready === 1'b1, "T5: override did not give ready");
        wait_run(200, "T5: no run by override");
        // ring disabled by software while running: SER_EN low at once
        cfg_ring_en = 0; #1 chk(c_wiredtx_ser_en === 1'b0 && c_pll_tx_en === 1'b0 && wire_tx_request === 1'b0, "T5: ring disable did not stop SER_EN at once");
        refs(12); chk(c_txpad_req_main === 1'b0 && st_state === 3'd0 && tx_ring_ready === 1'b0, "T5: abort after ring disable");
        stop_all; chk_timer = 1;

        // ---- T6 fault and island forcing while running
        mission; wait_run(600, "T6: no run");
        fault = 1; #1 chk({c_txpad_req_main, c_txpad_req_post, c_txpad_req_detect, c_txpad_req_term, c_wiredtx_bias_en} === 5'd0, "T6: fault did not force the requests off at once");
        refs(12); chk(c_wiredtx_ser_en === 1'b0 && wire_tx_request === 1'b0 && st_state === 3'd0, "T6: fault did not stop the serializer");
        chk(c_pll_tx_en === 1'b1, "T6: fault must not disable the ring");
        fault = 0; chk_timer = 0; wait_run(300, "T6: no restart after fault"); chk_timer = 1;
        island_on_wired = 0; #1 chk({c_wiredtx_ser_en, c_txpad_req_main, c_txpad_req_post, c_txpad_req_term, c_wiredtx_bias_en, wire_tx_request} === 6'd0, "T6: wired island off");
        refs(12); island_on_wired = 1; chk_timer = 0; wait_run(300, "T6: no restart after wired island"); chk_timer = 1;
        island_on_pll = 0; #1 chk(c_pll_tx_en === 1'b0 && c_wiredtx_ser_en === 1'b0 && wire_tx_request === 1'b0, "T6: pll island off");
        refs(12); chk(tx_ring_ready === 1'b0 && c_txpad_req_main === 1'b0, "T6: ready / MAIN after pll island off");
        island_on_pll = 1; wait_run(600, "T6: no restart after pll island");   // timer check active again: full lock time
        vreg_tx_ok = 0; #1 chk(c_pll_tx_en === 1'b0 && c_wiredtx_ser_en === 1'b0, "T6: vreg hold");
        vreg_tx_ok = 1; wait_run(600, "T6: no restart after vreg hold");
        stop_all;

        // ---- T7 fallback (WT28): branch 2 + wtx_ext + active + !idle, REF_CLK stopped, pll island off, ring off
        island_on_wired = 1; ref_run = 0; #100;
        cfg_branch = 2'd2; cfg_wtx_ext = 1; cfg_wtx_state = 2'd2; cfg_idle = 0;
        #1 chk(c_txpad_req_main === 1'b1 && c_wiredtx_bias_en === 1'b1 && c_txpad_req_post === 1'b0 && c_wiredtx_ser_en === 1'b0, "T7: fallback request without a clock");
        cfg_post_pol = 1; #1 chk(c_txpad_req_post === 1'b1, "T7: fallback POST"); cfg_post_pol = 0;
        cfg_idle = 1; #1 chk(c_txpad_req_main === 1'b0, "T7: fallback idle"); cfg_idle = 0;
        cfg_wtx_state = 2'd1; #1 chk(c_txpad_req_main === 1'b0, "T7: fallback state"); cfg_wtx_state = 2'd2;
        cfg_branch = 2'd1; #1 chk(c_txpad_req_main === 1'b0, "T7: fallback needs branch 2 without a clock"); cfg_branch = 2'd2;
        fault = 1; #1 chk(c_txpad_req_main === 1'b0, "T7: fallback fault"); fault = 0;
        island_on_wired = 0; #1 chk(c_txpad_req_main === 1'b0, "T7: fallback island"); island_on_wired = 1;
        #1 chk(c_txpad_req_main === 1'b1, "T7: fallback request back");
        ref_run = 1; refs(100); chk(c_txpad_req_main === 1'b1 && c_wiredtx_ser_en === 1'b0, "T7: fallback with the clock running");
        // external data on the serial branch (clocked path), ring ready: MAIN on, serializer off
        mission; cfg_wtx_ext = 1; cfg_ring_lock_time = 8'd0; refs(200);
        chk(c_txpad_req_main === 1'b1 && c_wiredtx_ser_en === 1'b0 && wire_tx_request === 1'b0 && tx_ring_ready === 1'b1, "T7: wtx_ext on the serial branch");
        cfg_wtx_ext = 0; stop_all;

        // ---- T8 termination readiness never arrives: sequencer fault, no traffic; retry after a request change
        mission; txpad_ready = 0; refs(700);
        chk(st_seq_fault === 1'b1 && wire_tx_request === 1'b0 && c_txpad_req_main === 1'b0 && c_txpad_req_term === 1'b0, "T8: ready timeout");
        chk(c_wiredtx_ser_en === 1'b1, "T8: serializer should keep running");
        txpad_ready = 1; cfg_idle = 1; refs(30); cfg_idle = 0; wait_run(300, "T8: no retry"); chk(st_seq_fault === 1'b0, "T8: fault not cleared");
        stop_all;

        // ---- T9 steady-state truth table: branch x state x idle x wtx_ext x post_code x post_pol x term (512 rows)
        island_on_wired = 1; island_on_pll = 1; vreg_tx_ok = 1; cfg_ring_en = 1; cfg_ring_lock_time = 8'd0; chk_timer = 0;
        refs(100);
        for (i = 0; i < 512; i = i + 1) begin
            {cfg_term_req, cfg_post_pol, cfg_wtx_ext, cfg_idle, cfg_wtx_state, cfg_branch} = i[7:0];
            cfg_post_code = i[8] ? 8'h80 : 8'h00;
            refs(260);
            e_main = cfg_wtx_state == 2 && (cfg_branch == 1 || cfg_branch == 2) && !cfg_idle;
            e_post = e_main && (cfg_post_code != 0 || cfg_post_pol);
            e_det  = cfg_branch == 3;
            e_term = cfg_term_req && cfg_branch != 3;
            e_ser  = cfg_wtx_state == 2 && !cfg_wtx_ext;
            e_req  = e_main && e_ser;
            if ({c_txpad_req_main, c_txpad_req_post, c_txpad_req_detect, c_txpad_req_term, c_wiredtx_ser_en, wire_tx_request, c_wiredtx_bias_en}
                !== {e_main, e_post, e_det, e_term, e_ser, e_req, e_main | e_det | e_term})
                $display("  row %0d: got %b%b%b%b%b%b exp %b%b%b%b%b%b", i, c_txpad_req_main, c_txpad_req_post, c_txpad_req_detect,
                         c_txpad_req_term, c_wiredtx_ser_en, wire_tx_request, e_main, e_post, e_det, e_term, e_ser, e_req);
            chk({c_txpad_req_main, c_txpad_req_post, c_txpad_req_detect, c_txpad_req_term, c_wiredtx_ser_en, wire_tx_request, c_wiredtx_bias_en}
                === {e_main, e_post, e_det, e_term, e_ser, e_req, e_main | e_det | e_term}, "T9: steady-state table row");
        end
        chk_timer = 1; stop_all;
        // ---- T10 pure decodes, all codes (checked by the 1 ns invariants)
        for (i = 0; i < 32; i = i + 1) begin {cfg_ring_band, cfg_ring_n, cfg_rate_mode} = i[4:0]; cfg_stage_tmds = i[0]; #3; end
        cfg_ring_band = 1; cfg_ring_n = 0; cfg_rate_mode = 0; cfg_stage_tmds = 0; #3;

        $display("checks %0d errors %0d", checks, errors);
        if (errors == 0) begin $display("TB PASS"); $finish; end
        else begin $display("TB FAIL"); $fatal(1, "tb_pt_wtx_ctl failed"); end
    end
    initial begin #40_000_000; $display("TB FAIL (timeout)"); $fatal(1, "timeout"); end
endmodule
`default_nettype wire
