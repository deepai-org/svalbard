`timescale 1ns/1ps
// Output register for pt_adc_i / pt_adc_q (v2). The SAR loop itself is custom
// 3.3 V transistor logic in circuits.py (sar_core); this std-cell macro only
// registers the result when the 10th decision completes.
//   bp[k]  : P-side decision latch of decision k (k=0 MSB), held until sample
//   done   : decision 9 captured (custom logic), low while sampling
//   code_tc: native 10-bit two's complement; done_o = done & en
module adc_code_reg (
    input  wire [9:0] bp,
    input  wire       done,
    input  wire       en,
    output reg  [9:0] code_tc,
    output reg        overload,
    output wire       done_o
);
    wire [9:0] ob = {bp[0], bp[1], bp[2], bp[3], bp[4], bp[5], bp[6], bp[7], bp[8], bp[9]};
    always @(posedge done or negedge en) begin
        if (!en) begin
            code_tc  <= 10'b0;
            overload <= 1'b0;
        end else begin
            code_tc  <= {~ob[9], ob[8:0]};
            overload <= (&ob) | ~(|ob);
        end
    end
    // done_o is not re-registered: the transport samples it through a
    // two-stage synchronizer, far slower than the register's clock-to-Q.
    assign done_o = done & en;
endmodule
