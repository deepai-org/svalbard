/* Behavioral verilog model for the bandgap.
 * This model produces a real-valued output based on the circuit
 * function and digital inputs.
 */

module gf180mcu_ocd_ip__bandgap (
    `ifdef USE_POWER_PINS
	/* 3.3V domain only.  The IHP bandgap also had 5.0V vdd/vss pins;
	 * the GF cell does not (see the schematic symbol). */
	inout wire dvdd,
	inout wire dvss,
    `endif 

    input wire ena,		// Circuit enable
    input wire [15:0] trim,	// Thermometer code

    input wire real ibias1_250n,	// Current bias
    input wire real ibias2_1u,		// Current bias

    output wire real vbg		// Bandgap voltage out
);

/* Bias range check.
 *
 * The circuit behaviour has only been characterised with ibias1_250n at
 * -250 nA and ibias2_1u at -1 uA;  away from those the output below means
 * nothing, so a testbench that quietly supplies something else is
 * measuring a number the model is not entitled to produce.
 *
 * The check is a flag rather than a clamp or an error.  Clamping would
 * hide a misconnection, and $error would stop a run that may be
 * deliberately sweeping the trim.  bias_ok is readable from a testbench
 * (cocotb reads it directly), and the warning fires only while the
 * block is enabled, because an unbiased disabled bandgap is normal.
 *
 * NaN fails the check, which is intended:  every comparison against NaN
 * is false, so an unconnected bias reads as out of range rather than as
 * a pass.
 */
localparam real IBIAS1_NOM = -250e-9;
localparam real IBIAS2_NOM = -1e-6;
localparam real BIAS_TOL   = 0.10;	/* fractional, on each bias */

/* NOMINALS ARE NEGATIVE, so the "low" bound is the more negative one. */
wire bias1_ok = (ibias1_250n >= IBIAS1_NOM * (1.0 + BIAS_TOL)) &&
		(ibias1_250n <= IBIAS1_NOM * (1.0 - BIAS_TOL));
wire bias2_ok = (ibias2_1u    >= IBIAS2_NOM * (1.0 + BIAS_TOL)) &&
		(ibias2_1u    <= IBIAS2_NOM * (1.0 - BIAS_TOL));

wire bias_ok = bias1_ok & bias2_ok;

always @(bias_ok or ena) begin
    if ((ena === 1'b1) && (bias_ok !== 1'b1))
	$display("WARNING: %m at %0t: bandgap bias out of range: ibias1_250n = %g A (want %g +/-%0.0f%%), ibias2_1u = %g A (want %g)",
		 $time, ibias1_250n, IBIAS1_NOM, BIAS_TOL * 100.0,
		 ibias2_1u, IBIAS2_NOM);
end

/* Circuit behaviour:  the trim curve, straight from simulation.
 *
 * The trim is a 16-bit thermometer code, so the only thing that matters
 * is how many bits are set --- j, from 0 to 16.  That is seventeen
 * possible outputs, and all seventeen have been simulated, so this is a
 * lookup rather than a fit:  there is no interpolation to do and no
 * approximation error to carry.  Replace the numbers when the block is
 * re-characterised;  nothing else here needs to change.
 *
 * Characterised 2026-09-21, after the trim resistor chain was changed
 * from "ppolyf_u_1k" to "ppolyf_u".  With ppolyf_u_1k the trim covered a far wider
 * range than needed AND sat badly off-centre;  with ppolyf_u, and no other
 * change, the curve lands on the flattest part of the tempco at
 * EXACTLY half trim.  So j = 8 -> 1.231 V is the nominal setting, and
 * it is the middle of the code range rather than an arbitrary point.
 *
 * Shape:  asymptotically straight at high trim, rolling off at low
 * trim.  If a closed form is ever wanted in preference to the table,
 *     quadratic  1.18266 + 0.00497239*j + 0.000131321*j^2   (max 1.3 mV)
 *     linear     1.17741 + 0.00707353*j                     (max 6.6 mV)
 * The linear residuals are a systematic arch, worst at both endpoints
 * and +3 mV at half trim, which is the one place accuracy is wanted;
 * that is what the roll-off costs a straight line.
 *
 * NOTE this is a single-corner, single-temperature model.  The whole
 * point of the trim is tempco, and there is no temperature input here,
 * so these are nominal values only.
 */

/* CHARACTERISED FOR GF180MCU 2026-10-28, from the SCHEMATIC netlist.
 *
 * Source:  the "bandgap_trim_curve" CACE parameter, which runs the tempco
 * testbench at all seventeen thermometer codes and reports vbg at 27 C.
 * Reproduce with
 *     cace gf180mcu_ocd_ip__bandgap.yaml -p bandgap_trim_curve \
 *          --source schematic
 * and transcribe vbg_27 for trim = 0 .. 16, in order, from
 * simulation_summary.csv.
 *
 * "--source schematic" IS DELIBERATE.  CACE defaults to --source best,
 * which prefers the RCX netlist now that the layout exists, so leaving it
 * off silently characterises something else.  The RCX view currently
 * disagrees with the schematic substantially:  vbg = 2.24 .. 2.66 V, and
 * the signed slope does not change sign anywhere in the trim range, so
 * the flat point is not reachable at all.
 *
 * THE CAUSE IS NOT ESTABLISHED.  It is most likely a real degradation
 * from the extracted parasitics rather than a netlist defect;  magic does
 * issue warnings during extraction around the bipolar emitters, which is
 * where to look first.  Note that when magic loses a resistor network it
 * falls back to the ideal case, which would make the extracted result
 * optimistic, not pessimistic --- so that alone does not explain this.
 *
 * Until that is understood, the schematic is the authority for this
 * table.  Re-characterise from the RCX netlist once it is trusted:  that
 * is the view that predicts silicon.
 *
 * The flat point lands at trim = 8, exactly half trim:  the signed slope
 * crosses zero between code 8 (-0.21 mV) and code 9 (+6.72 mV), and the
 * tempco at code 8 is 9.3 ppm/degC over -40 to 125 C.
 *
 * BANDGAP_TRIM_V in the harness chip's verilog/dv/harness.py duplicates
 * this table ON PURPOSE, so a test cannot agree with whatever the model
 * happens to say.  Both must be updated together.
 */
function real vbg_trimmed;
    input [4:0] jj;
    begin
	case (jj)
	    5'd0:  vbg_trimmed = 1.138;
	    5'd1:  vbg_trimmed = 1.140;
	    5'd2:  vbg_trimmed = 1.146;
	    5'd3:  vbg_trimmed = 1.155;
	    5'd4:  vbg_trimmed = 1.165;
	    5'd5:  vbg_trimmed = 1.176;
	    5'd6:  vbg_trimmed = 1.187;
	    5'd7:  vbg_trimmed = 1.199;
	    5'd8:  vbg_trimmed = 1.212;	/* nominal:  half trim */
	    5'd9:  vbg_trimmed = 1.225;
	    5'd10: vbg_trimmed = 1.239;
	    5'd11: vbg_trimmed = 1.254;
	    5'd12: vbg_trimmed = 1.269;
	    5'd13: vbg_trimmed = 1.286;
	    5'd14: vbg_trimmed = 1.303;
	    5'd15: vbg_trimmed = 1.322;
	    /* j cannot exceed 16:  the thermometer code is 16 bits wide,
	     * so the decoder saturates and every setting above 16 is the
	     * same physical setting. */
	    default: vbg_trimmed = 1.341;
	endcase
    end
endfunction

wire [4:0] j = $countones(trim);

localparam real NAN = 0.0/0.0;

assign vbg = (ena === 1'b1) ? vbg_trimmed(j) :
	     (ena === 1'b0) ? 0.0 : NAN;

endmodule
