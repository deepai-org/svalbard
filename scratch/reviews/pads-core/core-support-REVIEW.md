# Independent review: core-support cells, POR_BYPASS strap, supply-clamp study (2026-11-14)

Reviewer, not the designer. Nothing in the project tree or the designer's directories was modified.
My reruns: `review-cs/` (`rgen.py` decks, `rrun.sh`, `rcollect.py` -> `results.json`, logs in `sim/p1r p1n p2 p3`, LVS in `lvs/`).
Every number is marked **RERAN** (my run) or **READ** (designer's log / source, not rerun).
The batch was stopped on request before the clamp group finished; section 4 lists what was not run.

## Verdicts

| Item | Verdict | Publish as is? |
|---|---|---|
| `pt_bias_tap2` | GO with conditions | Yes, the cell. The top netlist binding is wrong for it (finding 1). |
| `pt_refvcm` | GO with conditions | Yes, with the pad-coupling condition written down (finding 3). |
| `pt_txpad_bias`, REF/BIAS dividers | GO | Yes. |
| `pt_txpad_bias`, detect bias (x10 mirror) | NO-GO as drawn | No. Regenerate with x5 or x6 (finding 2), or publish with the detect pins declared unusable and tied off. |
| POR_BYPASS strap evidence | GO with conditions | Yes, after the ramp claim is corrected (finding 5). |
| Clamp study | NO-GO on the margin statement | No. "Never fires at >= 3 us" is wrong (finding 6); the rule itself (>= 10 us) still holds in what I ran. |

## 1. Package 1: the three cells

### What I checked and it holds

- **Identity (RERAN).** sha256 of `bias/gds/*.gds` = `gunzip pub/*.gds.gz` = `kldrc.json` = `-layout.json`:
  tap2 `693572408d9f...`, refvcm `9f734d04f2ae...`, txpad_bias `27f11165c2e8...`. `bias/ext/*.spice` (what `run_ext` includes)
  is byte-identical to `pub/*.ext.spice`, whose hash is in the same `-layout.json` as the GDS hash.
- **Read-back LVS (RERAN, all three, absolute paths, `lvs/work/`).** match unique; census 10/10, 12/12, 49/49.
  My negative controls on `pt_txpad_bias`, all flagged: `PUP` gate polarity swapped (pin matching fails), one resistor
  1.8 um instead of 2 um (property error, census differs), `SWD`/`PDN` gates swapped (pin matching fails).
- **Designer decks (RERAN, 11 across the three cells incl. safety corners and both negative controls).** Bit-identical to the
  designer's logs (max relative difference 0). List in `rgen.py`.
- **Schematics (READ).** Only `nfet_03v3` / `pfet_03v3` / `ppolyf_u_1k`, all on 3.3 V island rails; NMOS bodies VSS, PMOS
  bodies VDD; every MOS and every `ppolyf_u_1k` is drawn with its own guard ring (`layoutlib` `guard 1`). No floating node in
  any enable state: disabled dividers discharge through their own resistors, `nd` has `PDN`, `DETECT_PBIAS` has `PUP`.
- **Precheck decks (READ).** main 0, antenna 0; the antenna rules did execute. This is block level only: the long EN
  routes do not exist yet. EN gate area is 3.4 um2 (5.9 um2 on `EN_DET`), same as the banks.
- **Supply ramp 0 -> 3.63 V in 1 us, enables low and high, ff/85 and ss/0 (RERAN, 12 decks).** No output exceeds its rail
  (max excess < 1e-13 V), no stuck state; final values equal the DC values. Tap output current peaks at 14.2 uA during the ramp.
- **Tap into the real consumer diodes (RERAN, 6 corners).** qvco `XNB` 1.44/1: 10.05-10.20 uA at 0.85-1.12 V.
  lo_pfdcp `XB1` 20/32 + 80 kohm: 10.04-10.19 uA at 1.47-1.94 V (0.2 % low at ss: compliance). Open consumer pin: output
  sits at the rail, 3-4 nA.
- **Tap rail off, bank on, EN high (RERAN).** 0 output, 0 back-drive.
- **`pt_txpad_bias` with the real gated termination buffer (RERAN, schematic buffer + 30 ohm / 3 pF compensation, 1 kohm + 10 pF load).**
  OUT is 7-8 mV below the fixture case at 5 corners (REF is 7.4 mV low at tt). Simultaneous enable: OUT within 2 % in
  1.4-2.0 ns, overshoot 1.70-1.88 V; the fixture overshoots more (1.70-2.09 V). The cell does not degrade the buffer.
- **Loading (RERAN).** 100 nA drawn from each node: REF -0.5 mV, BIAS -2.2 mV. Buffer inputs are gates (READ).
- **Cross enables (RERAN).** EN and EN_DET are independent. EN_DET = 1 with no bias current: detect source 0.15 nA (ff/85).
- **ESD (READ + RERAN).** `DETECT_PBIAS` reaches only the gate of the pad's `DETECT_x_SOURCE`; BUF_REF/BUF_BIAS reach only
  buffer gates; refpad `VCM` is behind 8 x 12.5 kohm per leg. None is on a bond net.
  HBM 2 kV positive on a refpad with `pt_refvcm` (unpowered) on VCM (RERAN, standard ngspice, not the pads image):
  pad peak 6.45 V (tt) / 6.91 V (ss/0), equal to the pads' own evidence; **VCM peak 1.54 / 1.49 V**. DC bound if the pad
  stayed at its peak: 6.9 x 80k/180k = 3.1 V. VCM carries gates and poly only, no junction. **No secondary clamp needed.**
  Negative HBM did not converge in my image (aborted at 6 ns, pad -2.1..-2.5 V); bound from the pads' -4.3 V is -1.9 V.

### Findings

1. **Blocking for integration, not for the cell: the tap must be on the bank's rail and `pt_chip.conn` binds it elsewhere.**
   `bias_ext` is bound `RAIL_pll~RAIL_lo` and `RAIL_wired~RAIL_wired_tx`; the banks sit on `RAIL_pll` and `RAIL_wired_rx`.
   - Bank rail off, tap rail on, trunk and EN on (RERAN): **108-160 uA into the qvco diode** (11-16x), 22-42 uA into lo_pfdcp.
     `RAIL_lo` (rf group) and `RAIL_pll` (pll group) have different enables, so this state is reachable.
   - Rail offset (RERAN): -50 mV -> -16 %, +50 mV -> +19 %, +/-100 mV -> -31 % / +37 %. Two island switches differ by this much.
   - Condition: tap VDD = the bank's rail, abutting; LO modes then need the pll island and trunk on. The conn also names a
     three-output `pt_bias_ext`; the staged cell is `pt_bias_tap2` (two instances needed), and `txpad_bias` has pins `EN`,
     `EN_DET`, `IBIAS_DET`, `DETECT_PBIAS` that the conn does not know. `IBIAS_DET` has no named source in the evidence.

2. **Blocking for the detect function: the x10 mirror has no headroom.** The pad's 4/2 um PMOS needs ~2.85 V of Vsg for
   100 uA, so `DETECT_PBIAS` is 0.455 V at tt and 0.17-0.20 V at ss; the NMOS mirror is in triode.
   - Designer's 82-93 uA at ss confirmed (RERAN). Added: **74 uA at ss/85/3.0 V**; supply sensitivity at ss/85 is 56 uA/V.
   - Ratio study, schematic variants (RERAN, 9 corners incl. ss/85/3.0 V, sf, fs, ff/0/3.63):

     | Mirror | Per-leg current, all corners | Lowest PBIAS |
     |---|---|---|
     | x10 (as drawn) | 73-101 uA | 0.14 V |
     | x8 | 70-81 uA | 0.20 V |
     | x6 | 58.7-60.8 uA | 0.37 V |
     | x5 | 49.3-50.8 uA | 0.54 V |
     | x4 | 39.6-40.7 uA | 0.72 V |

     x10 with a doubled reference PMOS gives exactly the x5 numbers at twice the supply current: no benefit.
   - Is 82-93 uA acceptable? For the detect measurement probably yes: the receiver-detect contract uses normalised responses
     and the architecture has a 6-bit current trim (READ). What is not acceptable is a current set by the supply instead
     of the reference. **Recommend x5 (or x6) and telling pads/detect the test current is 50 (60) uA.** One constant in `circuits_ext.py`.

3. **Not blocking, must be written down: `pt_refvcm` is not stiff against DC-coupled pads.** 40 kohm source against
   100 kohm strings (RERAN, tt):
   - one pair with both legs at 0 V: VCM 0.90 V; both at 3.3 V: 2.39 V;
   - single-ended 0/3.3 V CMOS clock on P, N at 0 V: VCM average 1.27 V (-0.37 V), ripple +/-123 mV at 10 MHz, +/-48 mV at 40 MHz;
     the other pair's pads follow the DC shift fully, with +/-5 mV of ripple;
   - complementary 0/3.3 V clock: no shift (1.648 V).
   Every pads bench drove VCM with an ideal source. Condition: both refpads AC-coupled or driven differentially about VDD/2.
   Also: with `RAIL_pll` off and a pad driven, a few uA flow through the header's drain diode into the dead rail (READ, not simulated).

4. **Not blocking: evidence hygiene.**
   - `bias/results.txt` is a Python traceback, not results. I regenerated the table from the designer's logs
     (`designer_collect/collect.txt`); it agrees with EVIDENCE.md.
   - `generate_ext.py` adds the `circuits_ext.py` hash after `-layout.json` is written, so the hash is not recorded.
   - Not done by anyone: Monte Carlo, R extraction, chip-level antenna on the EN routes.

## 2. Package 2: POR_BYPASS strap

Bench does what it says (READ): pin order `DVDD DVSS PAD PD PU VDD VSS Y` matches the PDK subckt; PD = VDD, PU = 0.
Six designer decks RERAN bit-identical (worst leakage, res_ss injection and threshold, 1 us ramp, both negative controls).
Arithmetic of the margin is right: 2.57 uA / 0.105 nA = 24,000.

5. **The ramp claim holds only with the assumed 2 pF on the pad.** (RERAN, my decks)

   | Ramp, pad capacitance | Peak pad | Y |
   |---|---|---|
   | 1 us, 2 pF (designer's case) | 0.31-0.39 V | stays low |
   | 0.1 us, 2 pF | 0.68-0.76 V | stays low (0.18-0.44 V peak) |
   | 1 us, 0.2 pF | 0.37-0.50 V | **goes high at ss/0, ss/85, fs/85** (1.5-1.7 V, above VDD/2); low at ff/85 |
   | 0.1 us, 0.2 pF | 1.16-1.29 V | **full rail at all four corners** |

   An unbonded pad is nearer 0.2 pF than 2 pF. "In every supply ramp Y stays at 0" must be restated with its condition.
   Not run: 0.2 pF at 3 / 10 / 100 us (the board-rule range) and the glitch width; decks are prepared in `rgen2.py`.
   Condition: either the reset logic tolerates `por_bypass` high during the ramp, or the 10 us rule is shown to cover 0.2 pF.

   Other points, not blocking:
   - The 24,000x is against model junction leakage only. Against a 1 uA datasheet-style leakage limit the margin is 2.5x to 0.4 V
     and 7x to the flip. Photocurrent on an unencapsulated die is not covered.
   - Neighbour edge of 3.15-3.63 V in 1 ns (RERAN): 100 fF coupling -> 0.11-0.13 V on the pad; 300 fF -> 0.30-0.36 V
     (three of four 300 fF runs aborted after the peak). Threshold >= 0.99 V: safe.
   - The negative control at tt/ss floats to 2.6 V on gmin-level currents; at ff/85 the floating pad sits at 4 mV and needs 0.75 nA
     to flip (READ). It shows the bench discriminates, not what a real floating pad does.
   - Most logs are older than the regenerated decks (22:33-22:42 vs 22:43); my six reruns match, so no evidence of drift.

## 3. Package 3: clamp study

6. **Blocking for the document: the clamp fires on ramps slower than 3 us.** Fine sweep, one `dvdd` cell, ideal ramp to 3.63 V,
   peak current in A (RERAN, 64 decks):

   | Corner | 2.0 | 2.2 | 2.4 | 2.6 | 2.8 | 3.0 | 3.5 | 4.0 us |
   |---|---|---|---|---|---|---|---|---|
   | sf/85, res_ss + moscap_ss | 0.84 | 0.84 | 0.84 | 0.84 | 0.84 | **0.84** | **0.64** | 0.0002 |
   | ff/0, res_ss + moscap_ss | 1.37 | 1.37 | 1.37 | 1.37 | 1.16 | 0.0004 | 0.0003 | 0.0003 |
   | ff/85, res_ss + moscap_ss | 1.18 | 1.18 | 1.18 | 1.18 | 1.06 | 0.0004 | 0.0003 | 0.0002 |
   | tt/27, res_ss + moscap_ss | 1.08 | 1.08 | 1.08 | 1.08 | 0.0003 | | | |
   | ss/0 (3.8 V) | 0.96 | 0.96 | 0.96 | 0.96 | 0.69 | 0.0002 | | |
   | ss/0 | 0.89 | 0.89 | 0.89 | 0.86 | 0.0002 | | | |
   | ss/85 | 0.79 | 0.79 | 0.79 | 0.78 | 0.0002 | | | |
   | fs/85, res_ss + moscap_ss | 1.12 | 0.0005 | | | | | | |

   - The designer never crossed sf with the slow RC. That combination fires fully at 3.0 us and partly at 3.5 us; 4.0 us is clean.
   - Against a 10 us full ramp the margin is **2.5x to the slowest clean case, 2.9x to the slowest firing case**, not >= 3.3x.
     Read as 10-90 % >= 10 us (12.5 us full swing) it is 3.1x / 3.6x.
   - The sweep is still not closed: sf/0 and ss with further-slowed RC were not run.
   - "Slow RC is the slow direction": supported for the pair. ff/85 with res_ff + moscap_ff does not fire at 2 us (READ);
     with res_ss + moscap_ss it fires to 2.8 us (RERAN). Which of R and C contributes was **not** separated: my tau decks did not run.
   - Ramp from a settled 1.5 V to 3.63 V in 1 us, ff/85 slow RC (RERAN): 0.37 mA, does not fire.

7. **Not blocking: evidence hygiene.** `clamp/results.txt` has empty tables (collect run from the wrong directory); the
   designer's numbers are in the logs and I regenerated the table (`designer_collect/clamp_collect.txt`, agrees with CLAMP.md).
   The `negA` decks carry a malformed multiplier (`m=0.0001.0`) and were never run; only one `tau` log exists (tt, 1.58 us).
   CLAMP.md points to negA rows that do not exist.

8. **Ring overshoot vs M6: not rerun; reasoning only (READ).** M6 feeds the die through 0.1 ohm + 2 nH and a 1 uF board
   capacitor (20 mohm, 1 nH) ahead of the same bond loop; the designer puts an ideal source at the board node. A soft source
   lets the rail collapse when 22 clamps (about 0.15 ohm together) turn on, and the bond inductance then rings the 1 nF die.
   M6's network is the project's own PDN model, so **"die rail <= 3.88 V" is the optimistic case and should not be quoted as the
   chip's behaviour**; 5.7-6.4 V stands until a rerun says otherwise.

### Rule wording

Write it as a slew limit, with the ramp time as the example. The clamp turns on when the rail gets about half a rail ahead
of a 1.6-2.6 us timer, so what matters is the rise within a few microseconds, from any starting level, not the 0-100 % time.
Proposed: **dV/dt <= 0.3 V/us at any point of any rise of the 3.3 V rail, including recovery from a dip
(equivalent: 10-90 % >= 10 us at 3.63 V); no hot-plug onto a live rail.** Worst simulated clean slew is 0.91 V/us
(4.0 us), worst firing slew 1.04 V/us (3.5 us): about 3x. Recommend >= 100 us as the design target for the regulator.
The "dips up to 1.5 V are harmless" statement is READ only; larger steps were not run.

## 4. Not run (batch stopped on request)

- Clamp: tau decks (res/moscap separately, temperature); 100 ns steps of 1.8-3.0 V; partial ramps from 1.0 V
  (three decks timed out at 600 s) and from 0.5 V (aborted at the initial timepoint); exponential rises (EXP source aborted
  at the initial timepoint; PWL versions prepared, not run); my no-capacitor negative control (aborted, <= 72 uA before the abort:
  inconclusive); reruns of five designer clamp decks; the ring with M6's source network; **all hot-plug cases**.
  So I have no hot-plug peak current, die-rail peak, time above 3.63 / 4.0 V or energy to report.
- Convergence note for whoever continues: every deck that starts with the rail flat (0 V, or settled at <= 1.0 V) fails or stalls
  at the first timepoint on the `cap_nmos_06v0` branch. The designer's 50 ns hot-plug has a 1 us flat start. Starting the edge
  at t = 0 is the first thing to try; I prepared such decks (`sim/p3/hot_*`, `ring_*`) but they did not run.
- Strap: 0.2 pF pad at 3 / 10 / 100 us and the Y glitch width.
- Cells: negative HBM on the refpad to completion; chip-level antenna; mismatch.
