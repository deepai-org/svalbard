`timescale 1ns/1ps
// Asynchronous SAR sequencer for pt_adc_i / pt_adc_q (10-bit, monotonic
// downward switching, split CDAC). Synthesizable; delay elements are
// explicit gf180mcu_fd_sc_mcu7t5v0 delay-cell instances (see
// adc_sar_delay.v for the behavioral stand-in used by RTL simulation).
//
// Timing contract (all derived from the block's CMOS sample input):
//   sample=1 : acquisition. Registers held in reset, every CDAC bottom plate
//              at VREF (rp*=1, gp*=0), comparator held in reset (cmp_clk=0).
//              boot_on closes the bootstrapped input switches (input_test=0)
//              or vcm_top closes the top-plate VCM switches (input_test!=0).
//   sample 1->0: switches open. After tdly1 the diagnostic force (if any) is
//              released; after tdly2 the first comparison starts.
//   conversion: self-timed. Every rising edge of valid = dp|dn captures one
//              decision and the decided side's bottom plate falls to VSS. The
//              comparator stays latched until the registers update, is reset
//              for one delay cell (CDAC settling window) and then re-armed.
//   done      : high after the 10th decision until the next sample.
//
// Codes: code_tc is the native 10-bit value in two's complement (the
// transport word is {code_tc, 2'b00}); overload marks the two end codes.
module adc_sar_logic (
    input  wire       sample,     // CMOS sample clock, 1 = acquire
    input  wire       en,         // adc_*.config.enable AND state==active
    input  wire [1:0] input_test, // adc_*.config.input_test
    input  wire       dp,         // comparator: top P > top N (active high)
    input  wire       dn,         // comparator: top N > top P (active high)
    output wire       cmp_clk,    // 1 = comparator evaluates
    output wire       boot_on,    // bootstrapped input switch phase
    output wire       boot_onb,
    output wire       vcm_top,    // top-plate VCM switches (diagnostic)
    output wire       lsb_rst,    // LSB-array node reset to VCM
    output wire [8:0] gp,         // P bottom plate k -> VSS
    output wire [8:0] rp,         // P bottom plate k -> VREF
    output wire [8:0] gn,
    output wire [8:0] rn,
    output reg  [9:0] code_tc,
    output wire       done,
    output reg        overload
);
    wire trk = sample & en;
    wire rst_n = en & ~trk;

    // Delayed copies of the track phase (fall delayed, rise immediate).
    wire trk_dly1, trk_dly2;
    adc_sar_delay #(.KIND(0)) u_d1 (.a(trk), .z(trk_dly1));
    adc_sar_delay #(.KIND(0)) u_d2 (.a(trk_d1), .z(trk_dly2));
    wire trk_d1 = trk | trk_dly1;
    wire trk_d2 = trk_d1 | trk_dly2;

    // valid clocks every register. ph toggles with each captured decision;
    // the comparator is reset while ph and its delayed copy differ, which
    // happens one register delay after valid (the same instant the CDAC
    // bottom plates start to move) and lasts one delay cell: that delay is
    // the CDAC settling window before the next comparison. dlyc (2.3 ns): with
    // dlyb the extracted loop did not finish at ss/32C/3.15V (suspected: reset
    // pulse too short for the slow routed clock edges; see README).
    wire valid_raw = dp | dn;
    wire valid;
    adc_sar_clkbuf u_ck (.a(valid_raw), .z(valid));
    reg ph;
    wire ph_dly;
    adc_sar_delay #(.KIND(2)) u_dp (.a(ph), .z(ph_dly));

    // d[j]=1 once decision j (0 = MSB) has been captured.
    reg [9:0] d;
    reg [9:0] bp, bn;
    wire [9:0] prev = {d[8:0], 1'b1};

    always @(posedge valid or negedge rst_n) begin
        if (!rst_n) begin
            d  <= 10'b0;
            bp <= 10'b0;
            bn <= 10'b0;
            ph <= 1'b0;
        end else begin
            d  <= prev;
            bp <= bp | ({10{dp}} & prev & ~d);
            bn <= bn | ({10{dn}} & prev & ~d);
            ph <= ~ph;
        end
    end

    assign done = d[9];
    // Strong output driver: this net crosses the block to the comparator.
    wire cmp_clk_raw = en & ~(trk_d2 | d[9] | (ph ^ ph_dly));
    adc_sar_clkbuf u_cko (.a(cmp_clk_raw), .z(cmp_clk));

    assign boot_on  = trk & (input_test == 2'd0);
    assign boot_onb = ~boot_on;
    assign vcm_top  = trk & (input_test != 2'd0);
    assign lsb_rst  = trk;

    // Diagnostic +/-VREF/4: hold the weight-128 bottom plate of one side at
    // VSS while sampling VCM; its release to VREF after the top switch opens
    // raises that side by VREF*2/8.
    wire force_p = trk_d1 & (input_test == 2'd2);
    wire force_n = trk_d1 & (input_test == 2'd3);

    // Decision j (0..8) switches the weight 2^(8-j) capacitor (index 8-j).
    genvar k;
    generate
        for (k = 0; k < 9; k = k + 1) begin : g_bot
            wire fp = (k == 7) ? force_p : 1'b0;
            wire fn = (k == 7) ? force_n : 1'b0;
            assign gp[k] = bp[8-k] | fp;
            assign gn[k] = bn[8-k] | fn;
            assign rp[k] = ~gp[k];
            assign rn[k] = ~gn[k];
        end
    endgenerate

    // Output register: captured when the 10th decision completes.
    wire [9:0] ob = {bp[0], bp[1], bp[2], bp[3], bp[4], bp[5], bp[6], bp[7], bp[8], bp[9]};
    always @(posedge d[9] or negedge en) begin
        if (!en) begin
            code_tc  <= 10'b0;
            overload <= 1'b0;
        end else begin
            code_tc  <= {~ob[9], ob[8:0]};
            overload <= (&ob) | ~(|ob);
        end
    end
endmodule
