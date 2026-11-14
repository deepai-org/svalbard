// Self-checking bench for rtl/pt_monitor.sv. Prints TB_PASS or TB_FAIL <n>.
// Run through verification/check_monitor.py (which also runs the mutants).
`timescale 1ns/1ps
`default_nettype none
module tb_pt_monitor;
    localparam real TICK = 20.8;          // mon_clk period (48 MHz)
    localparam integer LOSS = 64, QUAL = 2;
    reg rst_n = 0;
    reg mon_en = 1, ref_en = 1, in_en = 1;
    real ref_hp = 9.5, in_hp = 3.2;
    reg mon_clk = 0, ref_clk = 0, in_clk = 0;
    always begin #(TICK/2); if (mon_en) mon_clk = ~mon_clk; end
    always begin #(ref_hp); if (ref_en) ref_clk = ~ref_clk; end
    always begin #(in_hp);  if (in_en)  in_clk  = ~in_clk;  end

    reg rf_lock = 0, wire_lock = 0;
    reg [5:0] pgood = 0;
    reg rq_ref = 0, rq_in = 0, rq_rf = 0, rq_wire = 0;
    reg [5:0] rq_sup = 0;
    reg [11:0] loss = LOSS;
    reg [15:0] qualt = QUAL;
    reg clear = 0;
    wire fault, ready, cause_mon, ref_alive, in_alive, mon_dead;
    wire [9:0] cause, qualified;
    pt_monitor dut(
        .rst_n(rst_n), .mon_clk(mon_clk), .ref_clk(ref_clk), .in_clk(in_clk),
        .rf_lock(rf_lock), .wire_lock(wire_lock), .island_pgood(pgood), .supply_win_ok(6'd0),
        .cfg_require_reference(rq_ref), .cfg_require_input_clock(rq_in),
        .cfg_require_rf_lock(rq_rf), .cfg_require_wire_lock(rq_wire),
        .cfg_required_supply_mask(rq_sup), .cfg_loss_timeout_ticks(loss),
        .cfg_qualification_ticks(qualt), .clear_fault(clear),
        .fault(fault), .ready(ready), .cause(cause), .cause_mon_clk(cause_mon),
        .qualified(qualified), .ref_alive(ref_alive), .in_alive(in_alive), .mon_dead(mon_dead));

    integer errors = 0, checks = 0;
    task chk(input cond, input [8*64-1:0] msg);
        begin
            checks = checks + 1;
            if (cond !== 1'b1) begin
                errors = errors + 1;
                $display("FAIL @%0t: %0s (fault=%b ready=%b cause=%b cm=%b qual=%b)", $time, msg, fault, ready, cause, cause_mon, qualified);
            end
        end
    endtask
    task ticks(input integer n); begin #(n * TICK); end endtask
    localparam integer TQ = (QUAL + 1) * 64 + 16;   // qualification certainly done
    task do_clear; begin clear = 1; ticks(6); clear = 0; ticks(4); end endtask
    task disarm; begin rq_ref = 0; rq_in = 0; rq_rf = 0; rq_wire = 0; rq_sup = 0; ticks(6); end endtask
    // every fault path must stay quiet for n ticks
    task quiet(input integer n, input [8*64-1:0] msg);
        integer k;
        begin for (k = 0; k < n; k = k + 1) begin ticks(1); if (fault !== 1'b0) begin chk(1'b0, msg); k = n; end end chk(fault === 1'b0, msg); end
    endtask

    initial begin
        // ---- T1 reset: nothing armed, every input bad, clear toggled: never a fault
        #100 rst_n = 1;
        ref_en = 0; in_en = 0;
        quiet(400, "T1 reset default must not fault");
        do_clear;
        chk(fault === 1'b0 && cause === 10'd0 && ready === 1'b0, "T1 after clear");
        mon_en = 0; quiet(400, "T1 monitor clock dead, nothing armed"); mon_en = 1;
        ref_en = 1; in_en = 1; ticks(20);
        chk(ref_alive === 1'b1 && in_alive === 1'b1, "T1 alive flags");

        // ---- T2 reference: pending, qualification, loss timeout, sticky, cause, clear
        rq_ref = 1; ticks(8);
        chk(fault === 1'b1 && cause === 10'd0 && qualified[0] === 1'b0, "T2 pending holds fault");
        ticks(QUAL * 64 - 20);
        chk(qualified[0] === 1'b0 && fault === 1'b1, "T2 not qualified early");
        ticks(TQ - QUAL * 64 + 20);
        chk(qualified[0] === 1'b1 && fault === 1'b0 && ready === 1'b1, "T2 qualified");
        quiet(600, "T2 running reference must not fault");
        ref_en = 0;
        ticks(LOSS - 12);
        chk(fault === 1'b0, "T2 no trip before the timeout");
        ticks(24);
        chk(fault === 1'b1 && cause === 10'b1 && ready === 1'b0, "T2 trip after the timeout");
        ref_en = 1; ticks(TQ + 20);
        chk(qualified[0] === 1'b1, "T2 requalified");
        chk(fault === 1'b1 && cause === 10'b1, "T2 fault is sticky");
        do_clear;
        chk(fault === 1'b0 && cause === 10'd0 && ready === 1'b1, "T2 clear");
        // clear while the cause persists: cause clears, fault stays (pending)
        ref_en = 0; ticks(LOSS + 12);
        chk(fault === 1'b1 && cause === 10'b1, "T2b trip");
        do_clear;
        chk(cause === 10'd0 && fault === 1'b1, "T2b clear with reference absent keeps fault");
        ref_en = 1; ticks(TQ + 20);
        chk(fault === 1'b0 && ready === 1'b1, "T2b recovers without a second clear");
        // held clear level masks nothing
        clear = 1; ticks(10);
        ref_en = 0; ticks(LOSS + 12);
        chk(fault === 1'b1 && cause === 10'b1, "T2c held clear must not mask");
        clear = 0; ref_en = 1; ticks(TQ + 20); do_clear;
        chk(fault === 1'b0, "T2c clear");

        // ---- T3 slow but present reference (5 MHz: edge every 800 ns < 64 ticks)
        ref_hp = 100.0; ticks(20);
        quiet(2500, "T3 slow reference must not fault");
        chk(ready === 1'b1, "T3 ready");
        // the same clock against a 16-tick timeout is below the presence threshold
        disarm; loss = 16; rq_ref = 1; ticks(TQ + 200);
        chk(fault === 1'b1 && qualified[0] === 1'b0 && cause === 10'd0, "T3b too slow never qualifies");
        disarm; chk(fault === 1'b0, "T3b disarm releases");
        loss = LOSS; ref_hp = 9.5; ticks(20);

        // ---- T4 input clock
        rq_in = 1; ticks(TQ + 10);
        chk(fault === 1'b0 && qualified === 10'b10, "T4 qualified");
        quiet(300, "T4 running input clock");
        in_en = 0; ticks(LOSS - 12);
        chk(fault === 1'b0, "T4 no trip before the timeout");
        ticks(24);
        chk(fault === 1'b1 && cause === 10'b10, "T4 trip");
        in_en = 1; ticks(TQ + 20); do_clear;
        chk(fault === 1'b0, "T4 clear");
        disarm;

        // ---- T5 locks: not required = ignored; glitch shorter than the timeout; loss
        rf_lock = 0; wire_lock = 0;
        quiet(200, "T5 lock low but not required");
        rq_rf = 1; rq_wire = 1; ticks(TQ + 10);
        chk(fault === 1'b1 && qualified[3:2] === 2'b00, "T5 no lock: pending");
        rf_lock = 1; wire_lock = 1; ticks(TQ + 10);
        chk(fault === 1'b0 && qualified === 10'b1100, "T5 qualified");
        rf_lock = 0; ticks(LOSS - 12); rf_lock = 1; ticks(40);
        chk(fault === 1'b0, "T5 glitch shorter than the timeout");
        rf_lock = 0; ticks(LOSS + 12);
        chk(fault === 1'b1 && cause === 10'b0100, "T5 rf lock lost");
        rf_lock = 1; ticks(TQ + 20); do_clear;
        chk(fault === 1'b0, "T5 clear");
        wire_lock = 0; ticks(LOSS + 12);
        chk(fault === 1'b1 && cause === 10'b1000, "T5 wire lock lost");
        wire_lock = 1; ticks(TQ + 20); do_clear;
        chk(fault === 1'b0, "T5 clear 2");
        disarm;

        // ---- T6 supplies: pgood drop of a required island; unimplemented bit 3 ignored
        pgood = 6'b000000;
        rq_sup = 6'b001000; ticks(TQ);
        chk(fault === 1'b0 && ready === 1'b0, "T6 mask bit 3 has no hardware");
        rq_sup = 6'b010101; ticks(20);
        chk(fault === 1'b1 && cause === 10'd0, "T6 rails down: pending");
        pgood = 6'b010101; ticks(TQ + 10);
        chk(fault === 1'b0 && qualified === 10'b0101010000, "T6 qualified");
        pgood = 6'b010111; quiet(200, "T6 unrequired rail change");
        pgood = 6'b010001; ticks(LOSS - 12);
        chk(fault === 1'b0, "T6 no trip before the timeout");
        ticks(24);
        chk(fault === 1'b1 && cause === 10'b0001000000, "T6 pll rail dropped");
        pgood = 6'b010101; ticks(TQ + 20);
        chk(fault === 1'b1, "T6 sticky");
        do_clear; chk(fault === 1'b0 && cause === 10'd0, "T6 clear");
        disarm;

        // ---- T7 monitor clock absent
        rq_ref = 1; ticks(TQ + 10);
        chk(fault === 1'b0 && ready === 1'b1, "T7 qualified");
        mon_en = 0;
        ticks(150);
        chk(fault === 1'b0, "T7 no trip before 255 reference cycles");
        ticks(120);
        chk(fault === 1'b1 && cause_mon === 1'b1 && mon_dead === 1'b1 && ready === 1'b0, "T7 monitor clock lost");
        rq_ref = 0; #1;
        chk(fault === 1'b0, "T7 disarm releases fault without the monitor clock");
        rq_ref = 1; ticks(10);
        chk(fault === 1'b1, "T7 re-arm");
        clear = 1; ticks(6); clear = 0; ticks(10);
        chk(fault === 1'b1 && cause_mon === 1'b1, "T7 clear while still dead keeps fault");
        mon_en = 1; ticks(100);
        chk(mon_dead === 1'b0 && fault === 1'b1, "T7 sticky after the clock returns");
        do_clear;
        chk(fault === 1'b0 && cause_mon === 1'b0 && ready === 1'b1, "T7 clear");
        disarm;

        // ---- T8 reset clears everything
        rq_rf = 1; rf_lock = 1; ticks(TQ + 10); rf_lock = 0; ticks(LOSS + 12);
        chk(fault === 1'b1 && cause === 10'b0100, "T8 trip");
        rst_n = 0; #50; chk(cause === 10'd0 && qualified === 10'd0, "T8 reset clears"); rst_n = 1;
        disarm; quiet(100, "T8 after reset");

        if (errors == 0) $display("TB_PASS %0d checks", checks);
        else $display("TB_FAIL %0d of %0d checks", errors, checks);
        $finish;
    end
endmodule
`default_nettype wire
