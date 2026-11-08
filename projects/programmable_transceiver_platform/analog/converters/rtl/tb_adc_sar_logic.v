// Behavioral closed-loop check of adc_sar_logic: ideal monotonic CDAC
// (weights 256..1 of 512 per side) and a comparator with fixed delays.
`timescale 1ns/1ps
module tb_adc_sar_logic;
    reg sample = 0, en = 0;
    reg [1:0] input_test = 0;
    reg dp = 0, dn = 0;
    wire cmp_clk, boot_on, boot_onb, vcm_top, lsb_rst, done, overload;
    wire [8:0] gp, rp, gn, rn;
    wire [9:0] code_tc;
    adc_sar_logic dut(.sample(sample), .en(en), .input_test(input_test), .dp(dp), .dn(dn),
        .cmp_clk(cmp_clk), .boot_on(boot_on), .boot_onb(boot_onb), .vcm_top(vcm_top),
        .lsb_rst(lsb_rst), .gp(gp), .rp(rp), .gn(gn), .rn(rn), .code_tc(code_tc),
        .done(done), .overload(overload));

    real vref = 1.0, vin_d = 0.0, vsp, vsn, vtp, vtn;
    integer k, errors = 0, trial;
    // Track/hold of the top plates.
    always @(*) if (boot_on) begin vsp = 1.65 + vin_d/2; vsn = 1.65 - vin_d/2; end
                else if (vcm_top) begin vsp = 1.65; vsn = 1.65; end
    function real side(input real vs, input [8:0] g, input real f);
        real v; integer i;
        begin
            v = vs;
            for (i = 0; i < 9; i = i + 1) if (g[i]) v = v - vref * (1 << i) / 512.0;
            side = v + f;
        end
    endfunction
    // Diagnostic force: bottom held low while sampling, released afterwards.
    reg [8:0] gp_s, gn_s;
    always @(negedge vcm_top) begin gp_s = gp; gn_s = gn; end
    always @(posedge vcm_top) begin gp_s = 0; gn_s = 0; end
    always @(posedge boot_on) begin gp_s = 0; gn_s = 0; end
    always @(*) begin
        vtp = side(vsp, gp, 0.0) + ((gp_s[7] & ~gp[7]) ? vref*128/512.0 : 0.0);
        vtn = side(vsn, gn, 0.0) + ((gn_s[7] & ~gn[7]) ? vref*128/512.0 : 0.0);
    end
    always @(posedge cmp_clk) begin #0.6; if (cmp_clk === 1'b1) begin if (vtp > vtn) dp = 1; else dn = 1; end end
    always @(cmp_clk) if (cmp_clk !== 1'b1) #0.4 begin dp = 0; dn = 0; end

    task convert(input real vd, input [1:0] t, input integer exp_code);
        integer got;
        begin
            vin_d = vd; input_test = t;
            sample = 1; #10; sample = 0;
            wait(done); #5;
            got = $signed(code_tc);
            if ((got - exp_code) > 1 || (exp_code - got) > 1) begin
                errors = errors + 1;
                $display("FAIL vin=%f test=%0d code=%0d exp_code=%0d", vd, t, got, exp_code);
            end else $display("ok   vin=%f test=%0d code=%0d exp_code=%0d ovl=%0d t_conv_done", vd, t, got, exp_code, overload);
            #20;
        end
    endtask
    real tstart, tdone;
    always @(negedge sample) tstart = $realtime;
    always @(posedge done) begin tdone = $realtime; $display("    conversion %0.2f ns after sample fall", tdone - tstart); end

    initial begin
        #1; en = 1; #1; sample = 1; #5; sample = 0; #20;
        convert(0.0, 0, 0);
        convert(0.5, 0, 256);
        convert(-0.5, 0, -256);
        convert(0.123, 0, 63);
        convert(-0.9, 0, -461);
        convert(0.999, 0, 511);
        convert(-1.2, 0, -512);
        convert(0.3, 1, 0);
        convert(0.3, 2, 128);
        convert(0.3, 3, -128);
        en = 0; #5;
        if (code_tc !== 0 || done !== 0 || cmp_clk !== 0 || gp !== 0 || rp !== 9'h1ff || boot_on !== 0)
            begin errors = errors + 1; $display("FAIL disabled state not clamped"); end
        else $display("ok   disabled state clamped");
        if (errors == 0) $display("PASS adc_sar_logic"); else $display("FAILURES %0d", errors);
        $finish;
    end
endmodule
