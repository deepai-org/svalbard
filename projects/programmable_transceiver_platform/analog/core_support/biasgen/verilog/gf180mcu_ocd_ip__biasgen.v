/* Behavioral verilog model for the current bias generator.
 * This model produces a real-valued output based on the circuit
 * function and digital inputs.
 */

module gf180mcu_ocd_ip__biasgen (
    `ifdef USE_POWER_PINS
	inout wire dvdd,
	inout wire dvss,
	inout wire avdd,		// analog 5.0V supply (named avdd
				// in the schematic, symbol and layout)
	inout wire avss,
    `endif 

    input wire ena,		// Circuit enable
    input wire ref_sel_vbg,	// Use bandgap to stabilize output
    input wire ref_sel_coarse,	// Coarse unit output (1uA)
    input wire ref_sel_fine,	// Fine unit output (50nA)

    input wire [2:0] bandgap_sink1,	// 1uA trimmable setting
    input wire [1:0] bandgap_sink2,	// 250nA trimmable setting
    input wire [2:0] voltgen_sink1,	// 1uA trimmable setting
    input wire [2:0] voltgen_sink2,	// 1uA trimmable setting
    input wire [4:0] voltgen_source,	// 1uA trimmable setting

    input wire [4:0] idac1_source,	// 1st iDAC output value setting
    input wire [4:0] idac2_source,	// 2nd iDAC output value setting

    input wire real ref_in,	// Reference, normally tied to avdd 
    input wire real vbg,	// Bandgap voltage in

    output wire real bandgap_sink1_ibias,	// bandgap 1uA sink bias
    output wire real bandgap_sink2_ibias,	// bandgap 250nA sink bias
    output wire real voltgen_sink1_ibias,	// voltgen 1st 1uA sink bias
    output wire real voltgen_sink2_ibias,	// voltgen 2nd 1uA sink bias
    output wire real voltgen_source_ibias,	// voltgen 1uA source bias
    output wire real idac1_source_ibias,	// 1st iDAC output current
    output wire real idac2_source_ibias		// 2nd iDAC output current
);

/* Circuit behavior:
 *
 * NOTE:  For validation, sink biases are set to negative values while
 * source biases are set to positive values.  The correct polarity can
 * then be checked at the target.
 */

wire [1:0] ref_set = {ref_sel_coarse, ref_sel_fine};
wire real srciunit;
wire real snkiunit;

/* The unit sink current is always (-)250nA, and drops linearly as ref_in
 * is moved toward ground (not that ref_in is nominally supposed to be at
 * the analog power supply of 5.0V).
 *
 * The unit source current is mirrored from the unit sink current when
 * ref_sel_vbg is not selected.  Otherwise, it depends on the coarse and
 * fine settings.  When both are zero, the unit source current is 250nA.
 * When coarse alone is set, the unit source current is 1uA.  When fine
 * alone is set, the unit source current is 50nA.  When both are set,
 * the unit source current is 333nA.
 */

localparam real NAN = 0.0/0.0;

/* Both unit currents are gated by "ena".
 *
 * A disabled generator sources and sinks nothing, so 0.0 is the right
 * off value and it propagates correctly:  every bias below is a trim
 * code times a unit current, so zeroing the unit zeroes all seven
 * outputs at once.
 *
 * An UNKNOWN enable must not produce that same 0.0.  Nothing downstream
 * could tell "the block is off" from "nobody has driven the enable
 * yet", and a bias of zero is exactly the value that makes an amplifier
 * model look quietly dead rather than broken.  So the third branch is
 * NaN, which propagates through the multiplications below and cannot be
 * mistaken for a real measurement.
 */
assign snkiunit = (ena === 1'b1) ? (-250e-9 * (ref_in / 5.0)) :
		  (ena === 1'b0) ? 0.0 : NAN;

/* The leading x-guard matters more here than the === alone:  without
 * it an unknown ref_set falls through the chain to the final 333e-9,
 * which is a perfectly plausible current and would be believed. */
assign srciunit = (ena === 1'b0) ? 0.0 :
	(^{ena, ref_sel_vbg, ref_set} === 1'bx) ? NAN :
	(ref_sel_vbg === 1'b0) ? -snkiunit :
	(ref_set === 2'b00) ? 250e-9 :
	(ref_set === 2'b01) ? 50e-9 :
	(ref_set === 2'b10) ? 1e-6 : 333e-9;

/* The bandgap works only on sink biases because otherwise it would
 * form a potentially unstable loop.  The 250nA sink comes from a
 * 2-bit iDAC which can produce 0, 250, 500, or 750nA.  The 1uA
 * sinks come from 3-bit iDACs which can produce 0 to 1.75uA in 250nA
 * steps.  The 1uA source is from a 5-bit iDAC so that it can reach
 * the target 1uA under any setting:  Standard, 0 to 7.75uA in 250nA
 * steps; Fine, 0 to 1.55uA in 50nA steps;  Coarse, 0 to 31uA in 1uA
 * steps.  Both, 0 to 10.33uA in 333nA steps. 
 *
 * The two main iDACs are configured exactly like the source above.
 */

/* NOTE on the integer-to-real conversion below.
 *
 * These were written as $bitstoreal(bandgap_sink1) and so on.  That is
 * not an integer-to-real conversion:  $bitstoreal reinterprets a 64-bit
 * IEEE-754 BIT PATTERN as a real, so handing it a 3- or 5-bit trim code
 * is doubly wrong --- it would give a meaningless value even if the
 * widths matched, and with a narrow argument iverilog fails with
 * "$bitstoreal requires a 64-bit argument", which inside the full design
 * showed up only as "vvp: vpi_get_value: Assertion `expr' failed".
 *
 * No conversion function is needed.  Verilog converts an integer vector
 * to real automatically when the other operand of an arithmetic
 * expression is real, so "bandgap_sink1 * snkiunit" does the right
 * thing:  the unsigned value of the trim code times the unit current.
 */
assign bandgap_sink1_ibias = bandgap_sink1 * snkiunit;
assign bandgap_sink2_ibias = bandgap_sink2 * snkiunit;
assign voltgen_sink1_ibias = voltgen_sink1 * snkiunit;
assign voltgen_sink2_ibias = voltgen_sink2 * snkiunit;
assign voltgen_source_ibias = voltgen_source * srciunit;
assign idac1_source_ibias = idac1_source * srciunit;
assign idac2_source_ibias = idac2_source * srciunit;

endmodule
