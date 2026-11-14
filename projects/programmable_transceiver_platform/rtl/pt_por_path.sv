// Reset path of the digital macro with two independent POR overrides (integration-plan G3 "no dead
// chip", interface row DT-10). Replaces `wire rst_n = reset_n_pad & (por_n | por_bypass);`.
// Rework 2026-11-14 after the independent review (scratch/reviews/por-path-review/REPORT.md, P1 P2 P4).
//
//   rst_n = reset_n_pad & (por_n | por_bypass | (ovr & key == KEY))          KEY = 16'hC3A5
//
//   por_bypass  FIRST path: static level of the input-only strap pad (pull-down, DNP jumper to VDD).
//   ovr, key    SECOND path, pad-free: 17 flops, all dffrnq class (asynchronous reset to 0; no set
//               flop, no latch). BOTH parts must be right, and they are written by different pins:
//     key[15:0] shift register, clock = SPI_SCLK rising, key <= {key[14:0], MOSI} (MSB first) ONLY
//               while RESET_N is low and SPI_CS_N is low; holds otherwise;
//               asynchronously cleared by  idle = SPI_CS_N high and SPI_MOSI low  alone ("dead-man").
//     ovr       one flop, clock = RESET_N rising, D = SPI_SCLK, asynchronously cleared by
//               idle, or RESET_N low and SPI_SCLK low (so D = 0 never has to be clocked in).
//   => the override is effective only after: 16 bits C3A5 clocked in with RESET_N low and CS_N low,
//      then a RESET_N rising edge that finds SCLK high, and only while the host never shows
//      "CS_N high, MOSI low" (the pulled default and the idle state of every ordinary host).
//   KEY is mixed (8 ones, 8 zeros): neither an all-0 nor an all-1 wake-up of the flops matches.
//   The zeros of the key can only be shifted with CS_N low (MOSI low with CS_N high is idle and
//   clears the register); the CS_N term in the shift enable makes that true for the ones too.
//   KEY ends in a 1 so that MOSI is already high when CS_N is raised after the last bit.
//   ovr_armed  = ovr & key == KEY: the override is in the reset path now (RESET_STATUS b3, live).
//   por_masked = POR asserted and overridden by either path (RESET_STATUS b4, live).
//
// RESCUE PROCEDURE (POR stuck low, strap unusable). All waits >= 1 us; one pin moves per step.
//  A bit-banged host (four GPIOs; the recommended way):
//   1. RESET_N low. (The die is in reset from here to step 6 whatever else happens.)
//   2. CS_N high, MOSI low, SCLK low: idle. Clears key and ovr: known start.
//   3. CS_N low. (MOSI still low.)
//   4. 16 bits 1100 0011 1010 0101 (0xC3A5, MSB first): set MOSI, wait, raise SCLK, wait, and for
//      bits 1..15 lower SCLK again. After the 16th rising edge LEAVE SCLK HIGH. MOSI is high (last bit).
//   5. CS_N high. (MOSI high, SCLK high, RESET_N low: not idle.)
//   6. RESET_N high. The die leaves reset here (rst_n rises once).
//   7. SCLK low.
//   8. Write RESET_STATUS = 0x0002 (clear rst_flag), then work normally with the rule of step 9.
//   9. OPERATION RULE: MOSI is high whenever CS_N is high. Per transaction: CS_N low, 32 Mode-0
//      clocks, after the last SCLK fall raise MOSI, >= 1 us later raise CS_N (MOSI LEADS CS_N BY
//      >= 1 us; simultaneous edges are not allowed), keep MOSI high until CS_N is low again.
//      Read RESET_STATUS regularly: rst_flag (b1) set again = the die went through a reset (dead-man
//      runt, RESET_N glitch): its registers are at reset values; repeat from step 1.
//  An ordinary SPI controller (hardware shifter) can replace the bit-banging only if ALL of this is
//  true for it, checked with a scope on the board: RESET_N is a GPIO; for step 4 it runs in Mode 3
//  (CPOL = 1, CPHA = 1: SCLK idles and ends HIGH, data sampled on rising edges) and sends the two
//  bytes C3 A5 in one CS_N-low frame; it HOLDS MOSI at the level of the last bit (high) when CS_N
//  rises and between frames, also while it is switched to Mode 0 after step 6 (no hi-Z, no return to
//  low: the pad pull-down would make "MOSI low, CS_N high" = idle = back to reset); in operation it
//  sends 40-clock frames = the 32-bit transaction followed by the byte 0xFF (pt_spi ignores clocks
//  after the 32nd; exactly one write: sim/tb_spi_csn_race.sv), so MOSI is high when CS_N rises.
//  A Mode-0 controller alone cannot key (SCLK is low at the RESET_N edge). A board pull-up on MOSI
//  is NOT a substitute (it would defeat the dead-man on every board).
//  Ending rescue mode: CS_N high with MOSI low once. Reset in rescue mode without re-keying: with
//  CS_N high and MOSI high raise SCLK, pulse RESET_N low, lower SCLK (key and ovr both survive).
//  A RESET_N low pulse during rescue operation ALWAYS resets the die cleanly (direct AND) and:
//   - SCLK high during the whole pulse, no SCLK rising edge with CS_N low in it: key and ovr survive,
//     the die runs again at the RESET_N rising edge (the "reset without re-keying" above);
//   - SCLK low at any time during the pulse (the normal bus state): ovr is cleared, the key survives;
//     the die stays in reset, statically. The host must re-arm: steps 1..7 (always right), or the
//     short form "SCLK high, RESET_N low, RESET_N high, SCLK low" with CS_N and MOSI kept high;
//   - an SCLK rising edge with CS_N low during the pulse: the key is shifted and lost: steps 1..7.
//  Normal boards never do any of this: the SPI pads pull to CS_N = 1, SCLK = 0, MOSI = 0
//  (pt_provider_io.sv), which is idle, and a Mode-0 host idles MOSI low at least once.
//
// Why a clear on a PIN level (the dead-man) and not just sampled bits: with RESET_N tied high and
// a healthy POR, nothing initialises the flops, and during the POR pulse the inputs (RESET_N = 1,
// por_n = 0) are exactly those of a rescued die in use. No logic can tell the two apart from RESET_N
// and por_n alone; only a pin level, or the improbability of the stored pattern, can. Both are used.
//
// Hazard table, re-derived for this structure (H = hazard, A = why it cannot happen / what remains).
// Bench: sim/tb_por_path.sv, verification/check_por_path.py (mutants, delayed-clock copy, yosys).
//  H1 self-reset (runt reset through a shared pad with a dead POR).
//     A: key, ovr and rst_n are functions of the six module inputs only, all of them input-only pad
//        levels or the POR output; nothing behind rst_n (register, debug mux, observation code,
//        MISO) is in the fan-in. The SPI pads are bi_24t with OE and A hard-tied to 0.
//  H2 POR silently removed because something drives a 1.
//     A: needs the 16-bit sequence under RESET_N low and CS_N low, then SCLK high at the RESET_N
//        edge: only a host that controls RESET_N and bit-bangs (or Mode 3) can do it. "All SPI pins
//        high at a RESET_N rising edge" (review P2: unconfigured FPGA with pull-ups, host idling
//        high) sets ovr but not the key: no effect, ovr_armed stays 0. The first idle state clears
//        both parts. With por_n = 1 the override has no effect at all.
//  H3 combinational loop through reset. A: no feedback: rst_n is an output only; the flops are not
//        reset or clocked by anything derived from rst_n; `yosys check -assert` is clean.
//  H4 reset glitch during normal SPI traffic.
//     A: healthy POR: por_n = 1 is the controlling input of the OR, rst_n = reset_n_pad, whatever
//        the 17 flops do. Dead POR, rescue mode: rst_n = reset_n_pad & ovr & match. With RESET_N
//        high the key cannot shift (enable needs RESET_N low) and ovr has no clock edge; with
//        RESET_N low rst_n is 0 whatever they do. The only event that changes key or ovr while
//        rst_n is high is the dead-man clear (H10), which clears all 17 flops: every flop moves 1 ->
//        0 at most once, match and ovr fall once, rst_n falls once and stays low. rst_n is a
//        read-once function of (reset_n_pad, por_n, por_bypass, ovr, match) and match an AND of 16
//        literals: no static hazard for single input changes in any tree mapping.
//  H5 RESET_N tied high, never a reset: the POR must count, flop wake-up state unknown (review P1).
//     A: flop state irrelevant when por_n = 1. While the POR is asserted, reset is released against
//        it in exactly ONE of the 2^17 storage states (key = C3A5 and ovr = 1), and then only if
//        the pins are not idle (CS_N low or MOSI high for the whole POR pulse) and RESET_N is high.
//        The bench enumerates all 2^17 states x 8 SPI pin states x RESET_N and asserts this set.
//        RESIDUAL (stated, not closed): a wake-up into that one state. For independent, unbiased
//        flops that is 2^-17 per power-up (2^-16 for the key, 1/2 for ovr); real flops are biased
//        and correlated (cell orientation, supply ramp), so the honest statement is "one fixed
//        17-bit pattern with 9 ones and 8 zeros in a fixed order, which no uniform wake-up
//        produces"; if a die's systematic wake-up pattern were exactly this one, that die would
//        show it at every power-up (visible: ovr_armed reads 1 until the first idle). It needs in
//        addition: RESET_N tied high, SPI pins not idle during the POR pulse, and it ends at the
//        first idle state. Dead POR + RESET_N tied high + no key: the die stays in reset.
//  H6 RESET_N low must always reset. A: AND with reset_n_pad as the last gate. After a RESET_N low
//        pulse the die is released only by por_n, the strap, or ovr & key (see the procedure for
//        which of the two survives a pulse).
//  H7 runt release at the RESET_N rising edge (old ovr = 1, new 0). A: while RESET_N is low ovr is
//        already 0 unless SCLK is 1, and then D = 1: the edge never clocks a 1 -> 0 change, and the
//        clear released at that edge always agrees with D (no recovery conflict). SCLK toggling
//        during keying (RESET_N low) clears ovr in every SCLK low phase: harmless and wanted, ovr
//        is set only by the RESET_N edge after the last bit, with SCLK held high (procedure step 4).
//        The bench runs a second time on a copy with a delayed ovr clock pin (review B1: D = 1'b1
//        is only distinguishable from D = SCLK with a clock-pin delay).
//  H8 RESET_N runt (shorter than the flop's minimum pulse width), or SCLK / CS_N / MOSI moving
//        within setup/hold/recovery of the RESET_N rising edge, or RESET_N / CS_N moving within
//        setup/hold of an SCLK rising edge (key enable). NOT closed by logic: the flop concerned
//        may go metastable or take either value. The RESET_N runt already is a partial reset
//        today (direct AND path); the board must drive RESET_N from a supervisor or a debounced
//        source and the rescue host keeps >= 1 us between pin changes. A key flop that resolves the
//        wrong way gives key != KEY = static reset, never a loop. On a healthy die the key holds
//        0 (cleared by every idle) and a RESET_N fall at an SCLK edge can only mix 0s with the
//        shifted 0s and one MOSI bit: it cannot produce KEY.
//  H9 accidental arming on a healthy die: needs the whole procedure; without effect until a
//        brownout; cleared by the first idle state; visible in RESET_STATUS (ovr_armed).
//  H10 dead-man runt in rescue mode (review P4): idle = CS_N & !MOSI is combinational from two pads;
//        a host that raises CS_N before MOSI is high, or bounces, puts a runt on the clear of all 17
//        flops. Any ONE of the 9 flops that hold a 1 (ovr and the eight 1-bits of the key) taking
//        the clear gives a clean, permanent reset; a clean miss gives no reset; only a flop that
//        goes metastable on the runt can put a runt on rst_n. Mitigation, not closure: Schmitt
//        inputs on SCLK, CS_N and MOSI (pt_provider_io.sv), MOSI leads CS_N by >= 1 us, rst_flag
//        cleared after keying and polled (procedure steps 8, 9).
//  H11 runt RELEASE while the flops are being cleared: from a state with ovr = 1 and a key that has
//        all the ones of KEY plus more (255 of the 2^17 states, the all-ones wake-up among them),
//        the 17 clears do not land at the same instant and the key can pass through KEY for a gate
//        delay. Only possible with por_n = 0, RESET_N high and non-idle pins BEFORE the first idle
//        state, i.e. a wake-up state or deliberate mis-keying; rst_n ends at 0 statically, so the
//        die is in reset afterwards as it must be (a short release inside an asserted reset, not
//        a short reset of a running die). The zero-delay bench does not model it. Accepted.
//  H12 ovr's idle clear is redundant at the outputs (idle also clears the key, so match falls).
//        It is kept on purpose: two flop groups, one clear each, both cleared by the dead-man.
//        The bench checks it white-box (dut.ovr), not at the outputs.
//
// Integration (macro owner): instantiate with the pad-level nets (reset_n_pad, por_n, por_bypass, the
// macro's spi_cs_n / spi_sclk / spi_mosi inputs) and nothing in between that a register can change;
// keep the hierarchy and the 17 flops (dont_touch: no merging, retiming, constant propagation or
// scan replacement). SDC, for the instance por_path in pt_digital_macro:
//  - no create_clock on reset_n_pad; por_path/ovr is an unclocked flop: unconstrained-endpoint waiver.
//  - por_path/key[15:0] are clocked by the SPI clock: keep their flop-to-flop hold checks
//    (key[i] -> key[i+1]); MOSI -> key[0] is an ordinary SPI input path.
//  - set_false_path -through por_path/rst_n (the ovr / key Q -> every flop's reset pin arc, setup,
//    hold, recovery and removal), -through por_path/ovr_armed and por_path/por_masked (live levels
//    read by the SPI), -from reset_n_pad / spi_cs_n to the key D pins (shift enable, static in every
//    legal use), and to the RN pins of the 17 flops (the dead-man clear: recovery/removal against
//    SCLK is covered by the >= 1 us rule of the procedure; on a healthy die the key holds 0).
`default_nettype none
// Re-review 2026-11-14 (scratch/reviews/por-path-review, condition C2): the module is kept as a hierarchy so that
// synthesis cannot remap the reset equation across the macro (a mux form selected by por_n would glitch on a POR edge).
(* keep_hierarchy *)
module pt_por_path(
 input  wire reset_n_pad, // RESET_N pad Y (in_c, pull-down)
 input  wire por_n,       // on-die POR, 0 = asserted
 input  wire por_bypass,  // strap pad Y, 1 = ignore the POR (first path)
 input  wire spi_cs_n,spi_sclk,spi_mosi, // SPI pad levels (pulled to 1 / 0 / 0)
 output wire rst_n,       // macro reset, 0 = reset
 output wire ovr_armed,   // second path effective: ovr set AND key matches (RESET_STATUS)
 output wire por_masked   // POR asserted but overridden by either path: running without a POR
);
 localparam [15:0] KEY=16'hC3A5;
 wire idle=spi_cs_n&~spi_mosi;
 wire kclr_n=~idle;
 wire oclr_n=~(idle|(~reset_n_pad&~spi_sclk));
 wire shift=~reset_n_pad&~spi_cs_n;
 reg [15:0] key;
 reg ovr;
 always @(posedge spi_sclk or negedge kclr_n)
  if(!kclr_n)key<=16'h0000;
  else if(shift)key<={key[14:0],spi_mosi};
 always @(posedge reset_n_pad or negedge oclr_n)
  if(!oclr_n)ovr<=1'b0;
  else ovr<=spi_sclk;
 wire match=key==KEY;
 wire armed=ovr&match;
 assign rst_n=reset_n_pad&(por_n|por_bypass|armed);
 assign ovr_armed=armed;
 assign por_masked=~por_n&(por_bypass|armed);
endmodule
`default_nettype wire
