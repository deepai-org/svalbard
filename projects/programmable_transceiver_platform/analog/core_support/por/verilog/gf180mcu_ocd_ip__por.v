// SPDX-FileCopyrightText: 2026 Open Circuit Design, LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// SPDX-License-Identifier: Apache-2.0
//
// Originally adapted from the Efabless Caravel project;  the behaviour
// below has since been rewritten against this circuit's own schematic.
// SPDX-FileCopyrightText: 2020 Efabless Corporation

`default_nettype none
`timescale 1ns/1ps

/*
 * Behavioural model of the power-on reset.
 *
 * THE CIRCUIT.  An amplifier forces the voltage across a resistor to
 * match a reference, which sets a small, supply-insensitive trickle
 * current.  That current charges XC1 (a 10u x 10u MIM cap, m=36) and the
 * capacitor voltage feeds an INVERTING Schmitt trigger, whose hysteresis
 * gives glitch tolerance on a very slow ramp.  So while vcap is low the
 * Schmitt output is HIGH, and it falls once vcap crosses the threshold.
 *
 * PORT NAMES AND POLARITY come from the schematic, which is the
 * authority here --- it and the layout have passed LVS.  From the
 * netlist:
 *
 *     x2  vdd3v3 vcap por_unbuf vss      por_3v3_schmitt_inv
 *     x5  ... por_unbuf por   buff_12  ->  por  =  por_unbuf
 *     x6  ... net8      por_unbuf inv_4 -> net8 = ~por_unbuf
 *     x3  ... net8      porb  buff_12  ->  porb = ~por_unbuf
 *
 * so por_unbuf follows por (both ACTIVE HIGH) and porb is its inverse.
 * An earlier version of this model called the pin "porb_u" and made it
 * follow porb, which was inverted with respect to the circuit.
 *
 * "ena" IS A REAL INPUT, not decoration.  In por_amp it is the gate of
 * XM5, an nFET in series with the differential pair's tail current:
 *
 *     diff pair sources -> nc -> XM5 (gate = ena) -> net2 -> XM6 -> vss
 *
 * (the node called "nc" is that tail node, not a no-connect).  With ena
 * low the tail current is cut, the amplifier cannot establish the
 * trickle current, vcap never charges, and THE CHIP NEVER LEAVES RESET.
 * It is a test input, exposed as a top level pin on this block (the
 * netlist marks it "ena:I" and gives it its own ESD diode, D1), so the
 * PARENT has to tie it --- chipalooza_frame does, to the 3.3 V supply.
 * Modelling it matters precisely because a mis-tie is silent and fatal,
 * and because being tied to the supply makes a rising ena equivalent to
 * a power-on.
 * That is what this model triggers on.  Note that this does NOT make
 * ena a reset input:  once the circuit has released, toggling ena will
 * not produce another pulse, because the capacitor stays charged.  See
 * the discussion of the one-way trickle current below.
 *
 * DELAY.  The real circuit is set for about 40 ms.  Simulating that is
 * not useful, so POR_DELAY_NS is deliberately many orders of magnitude
 * shorter;  override it per instance if a testbench needs a different
 * value.  Nothing about the chip's behaviour should depend on the
 * absolute number, and a test that does is testing this parameter
 * rather than the design.
 *
 * NOTE on port ORDER.  The schematic orders the pins
 *     vdd3v3 ena por_unbuf vss porb por
 * interleaving the supplies with the signals, which cannot be written
 * with a single `ifdef guard.  The supplies are grouped here instead,
 * matching every other IP model in this project.  Order is immaterial:
 * the design connects these by name, and netgen matches pins by name.
 */

module gf180mcu_ocd_ip__por #(
    /* Simulation reset width, in nanoseconds.  Silicon is ~40 ms. */
    parameter real POR_DELAY_NS = 1000.0
) (
`ifdef USE_POWER_PINS
    inout wire vdd3v3,
    inout wire vss,
`endif
    input  wire ena,		// amplifier enable;  tied to vdd3v3 in layout
    output wire por,		// reset, active HIGH
    output wire porb,		// reset, active LOW
    output wire por_unbuf	// unbuffered por;  same polarity as por
);

    /* "Running" means the circuit can actually charge its capacitor:
     * the supply is up and the tail current is enabled.
     *
     * An UNKNOWN ena counts as not running, deliberately.  The safe and
     * realistic answer to "nobody has driven the enable" is that the
     * amplifier has no tail current, so the part stays in reset --- and
     * a reset held asserted fails loudly, where an x propagated into
     * every flop in the design would fail confusingly.
     */
    wire powered;		/* the block has a supply at all */
    wire running;		/* ...and the amplifier is enabled */
`ifdef USE_POWER_PINS
    assign powered = (vdd3v3 === 1'b1);
`else
    assign powered = 1'b1;	/* no supply modelled: assume it is there */
`endif
    assign running = powered && (ena === 1'b1);

    /* por_int is the state of the Schmitt output:  1 while vcap is
     * below the trip point, i.e. while reset is asserted. */
    reg por_int;

    initial por_int = 1'b1;	/* asserted before anything is driven */

    /* THE TRICKLE CURRENT IS ONE-WAY.  This is the single most important
     * fact about the circuit, and it is what makes the part a one-shot
     * rather than a brown-out detector:  the amplifier can only charge
     * XC1, never discharge it.  So what happens when power or ena is
     * removed depends entirely on whether the Schmitt has already
     * tripped, and the two cases are completely different.
     *
     * BEFORE the trip point (por_int still 1):  no charge has been
     * retained that matters, so removing the current source simply
     * leaves the cap low and reset stays asserted.  The delay restarts
     * from empty on the next power-up.  The "disable" is what makes
     * that true and is not optional --- without it a dip leaves the
     * pending "#POR_DELAY_NS" running, power returns, and the part comes
     * out of reset after a fraction of the specified time.  The
     * testbench checks this explicitly;  it caught exactly that bug.
     *
     * AFTER the trip point:  the cap is charged and nothing discharges
     * it except leakage, so the output does NOT return to reset.  It
     * holds, for a length of time that has not been simulated.  This
     * model therefore holds the output and says so once, rather than
     * inventing a re-assert that the circuit does not perform.
     *
     * THIS PART HAS NO BROWN-OUT DETECTION, BY DESIGN.  Its one job is
     * to hold the digital in reset for a fixed time long enough for any
     * supply to come up and stabilise, so that a package pin does not
     * have to be spent on a reset input.  A supply that sags and
     * recovers without the capacitor discharging produces NO new reset
     * pulse, and nothing in the design may rely on one.  A replacement
     * with real brown-out detection is expected;  the supply hooks here
     * exist so that it can drop in against the same tests.
     *
     * The capacitor discharge time is therefore NOT worth characterising
     * for this part:  once the supply is gone the whole chip is
     * non-functional, so there is no observer for the answer.  What the
     * model does instead is state the consequence that IS observable ---
     * that a power blip short enough to leave the cap charged brings
     * the part straight back up with no reset at all.
     *
     * Also not modelled:  partial charge.  Power removed part-way up
     * leaves the cap somewhere in between, so a real part would trip
     * early on the next power-up.  The model restarts the full delay.
     */
    reg warned;
    initial warned = 1'b0;

    always @(running) begin
	if (running !== 1'b1) begin
	    if (por_int === 1'b1) begin
		/* Never tripped:  hold in reset and recharge from empty. */
		disable por_oneshot;
	    end else if (warned !== 1'b1) begin
		warned <= 1'b1;
		$display("WARNING: %m at %0t: power or ena removed after the POR had released.  The capacitor stays charged, so this part produces NO new reset pulse when it comes back --- it has no brown-out detection by design.  Do not rely on one.", $time);
	    end
	end
    end

    /* The charging one-shot.  Written as a loop rather than an "initial"
     * block, because an initial fires once per SIMULATION and cocotb
     * runs an entire suite in one simulation.
     *
     * It is nonetheless a ONE-SHOT PER PART:  the trailing wait never
     * completes, so once the Schmitt has tripped this model will not
     * produce another reset pulse under any stimulus.  Neither will the
     * silicon, short of a power cycle long enough for the cap to leak
     * away.  A testbench that needs a fresh reset per test cannot get
     * one by toggling ena;  see the note in the header of the
     * testbench.
     */
    always begin : por_oneshot
	wait (running === 1'b1 && por_int === 1'b1);
	#(POR_DELAY_NS);
	por_int <= 1'b0;

	/* Park until something outside puts por_int back to 1.
	 *
	 * NOTHING IN THIS MODEL EVER DOES.  No stimulus on ena or the
	 * supply can re-arm the part, which is correct:  the trickle
	 * current is one-way and the capacitor stays charged.
	 *
	 * A TESTBENCH may deposit 1 here to model "unpowered long enough
	 * for the capacitor to leak away", which is how the silicon is
	 * actually reset and is the one thing this model cannot derive
	 * for itself, the discharge being uncharacterised.  cocotb needs
	 * that, because it runs a whole suite in one simulation and every
	 * test wants a fresh reset --- see verilog/dv/harness.py, which
	 * does exactly this and says so.
	 *
	 * Writing it as a wait rather than parking forever keeps the
	 * affordance visible and deliberate:  the re-arm is an explicit
	 * act by a testbench, not something the circuit offers.
	 */
	wait (por_int === 1'b1);
    end

    /* Buffering only;  see the netlist quoted in the header.
     *
     * With no supply every node sits at ground, so all three outputs
     * read 0 --- including por and porb SIMULTANEOUSLY, which is a
     * logically impossible pair and is exactly the point:  that
     * signature says "this block is unpowered", not "reset released".
     * porb reading 0 also happens to hold the digital in reset, which
     * is harmless, since the digital has no supply either.
     */
    assign por_unbuf = powered ? por_int  : 1'b0;
    assign por       = powered ? por_int  : 1'b0;
    assign porb      = powered ? ~por_int : 1'b0;

endmodule

`default_nettype wire
