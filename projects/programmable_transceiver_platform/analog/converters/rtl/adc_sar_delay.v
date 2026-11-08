`timescale 1ns/1ps
// Delay element used by adc_sar_logic. Synthesis (SYNTH_CELLS defined)
// instantiates fixed gf180mcu_fd_sc_mcu7t5v0 delay cells that the flow must
// not resize or remove; RTL simulation uses a delay of the same nominal value
// (tt, 25C, 3.3V Liberty: dlya_1 0.53 ns, dlyb_1 1.23 ns, dlyc_1 2.28 ns). Every use in
// adc_sar_logic delays a level that is held much longer than the delay, so the
// inertial pulse filtering of real delay cells does not change the function.
module adc_sar_delay #(parameter KIND = 0) (input wire a, output wire z);
`ifdef SYNTH_CELLS
    generate
        if (KIND == 0) begin : g_a
            (* keep *) gf180mcu_fd_sc_mcu7t5v0__dlya_1 u0 (.I(a), .Z(z));
        end else if (KIND == 1) begin : g_b
            (* keep *) gf180mcu_fd_sc_mcu7t5v0__dlyb_1 u0 (.I(a), .Z(z));
        end else begin : g_c
            (* keep *) gf180mcu_fd_sc_mcu7t5v0__dlyc_1 u0 (.I(a), .Z(z));
        end
    endgenerate
`else
    assign #((KIND == 0) ? 0.53 : (KIND == 1) ? 1.23 : 2.28) z = a;
`endif
endmodule

// Explicit clock driver for the decision clock (no CTS in the macro flow).
module adc_sar_clkbuf (input wire a, output wire z);
`ifdef SYNTH_CELLS
    (* keep *) gf180mcu_fd_sc_mcu7t5v0__clkbuf_8 u0 (.I(a), .Z(z));
`else
    assign z = a;
`endif
endmodule
