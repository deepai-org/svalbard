`timescale 1ns/1ps
// Registered segmented decoder for pt_dac_i / pt_dac_q.
// code_tc = dac_*.code[11:2] (transport word truncated to the native 10 bits,
// two's complement). Stage 1 registers the offset-binary code (hold_zero
// forces mid-scale); stage 2 registers the 63 thermometer and 4 binary switch
// controls so every current cell switches on the same clock edge.
// sw[k]=1 steers cell k to OUTP. Disabled (en=0): everything reset, output
// switches open, all current steered to OUTN side (which is unpowered anyway).
module dac_logic (
    input  wire       clk,       // DAC_CLOCK after the local receiver
    input  wire       en,        // dac_*.config.enable AND state==active
    input  wire       hold_zero, // dac_*.config.hold_zero
    input  wire [9:0] code_tc,
    output reg  [62:0] th,       // thermometer cells (weight 16 LSB)
    output wire [62:0] thb,
    output reg  [3:0] bn,        // binary cells (weights 8,4,2,1)
    output wire [3:0] bnb,
    output wire       out_en,    // output isolation switches
    output wire       load_en_b  // active-low load header enable
);
    reg [9:0] ob;
    always @(posedge clk or negedge en) begin
        if (!en) ob <= 10'd512;
        else ob <= hold_zero ? 10'd512 : {~code_tc[9], code_tc[8:0]};
    end
    wire [5:0] msb = ob[9:4];
    reg [62:0] therm;
    integer i;
    always @(*) for (i = 0; i < 63; i = i + 1) therm[i] = (msb > i);
    always @(posedge clk or negedge en) begin
        if (!en) begin
            th <= 63'b0;
            bn <= 4'b0;
        end else begin
            th <= therm;
            bn <= ob[3:0];
        end
    end
    assign thb = ~th;
    assign bnb = ~bn;
    assign out_en = en;
    assign load_en_b = ~en;
endmodule
