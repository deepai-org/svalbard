# Review a13: pad_txpad (delta review against review-a12)

Reviewer verdict for PUBLICATION: **GO with conditions.**

a13 fixes what review-a12 F1 found: the single V2 cuts and the 0.4 um Metal2 straps are gone. No electrical or ESD result regressed, and the layout checks are clean.

The new EM screen `sec/em_check.py` does catch a12 and a seeded single cut. It is not complete, though. It only counts metal runs that carry at least 50 % of the path current, which is the netres `path_fraction` default. That hides one segment per resistor unit:
- the 0.46 um Metal2 landing bar at each resistor head carries the whole unit current;
- at code 2 this is **1.09-1.10x the 2.09 mA/um rating** on TU_x_B and TU_x_T1 (F1);
- the claimed "0 over, worst 0.84" is therefore not correct as stated.

The overrun is small, sits on a short segment, and falls to 0.99 at code 3. No corner's best code is below 3. So this does not block publication, but it must be fixed or explicitly accepted.

Reviewed GDS: `sec/b/a13/pad_txpad.gds`, sha256 72af3d5aa644e86aa7294650d86a53252553769abdcaa55a413b13ce709e46b7 (recomputed). em_check.py is 93226060, netres `sec/r13/res.json` 483511e6, and the models are a13_rh 3536551e, a13_rt 6f1b314c and a13_c 35eb7fcc, all recomputed.
- Rebuilding a13 with the STATUS command gives the same normalised GDS: 56d59369 for both.
- Generator `tx_pad_layout.py` is f4d70b81, and it is untracked in git.

Work done in this review (all files in this directory, one job at a time, OMP_NUM_THREADS=1):
- `lo13/`: netres on the 10 TU_* nets of a13 with `path_fraction` 0.02 (typ + high).
  - `lo13/res_j.json`: the same run with `netres_jloc.py`, a local copy of netres that also records where the density peaks are.
- `a12/` + `r12/`: a12 rebuilt with the STATUS a12 command, netres on TU_* / TERM_VCM / TERM_VCM_BUS, then em_check.
- `seed/`: the a13 GDS with 5 of the 6 V2 cuts of the TU_P_T1 array removed (`seed.py`), then netres + em_check.
- `dflt/`: the default-path rebuild. `a13/`: the a13 rebuild.
- ESD on a13_rh, all simulated: CDM 2 A vdd+ / vdd- / vss- (vss- with PULSE and with TB2_CDMSMOOTH), HBM 1 kV pp- / vss+ / vss- / vdd-. Outputs are `esd_a13-esd.json` and `esd_a13s-esd.json`, logs `esd.log` and `esd_s.log`.

## Findings

1. **MEDIUM (EM): the screen misses sub-50 % runs. The resistor-head Metal2 landing bar is over the rating at code 2.**
   - **Cause.** netres records `max_run_current_density_per_um` only for cross-sections carrying at least `path_fraction` (0.5) of the path current (`netres.py` lines 409-412).
     - A trim group of n parallel units sends 1/n of its current through each unit's own strap.
     - So B and T3 (8 units) report density 0.0, and every per-unit segment of T1 (2 units) or T2 (4 units) goes unchecked.
     - em_check.py treats a missing value as 0.
   - **Rerun at path_fraction 0.02** (`lo13/res.json`), worst code in 2..13, 10.5 mA per pad:

     | Net | Run ratio | Max density, mA/um | Run ratio over codes 0..15 |
     |---|---|---|---|
     | TU_x_B | **1.10** (high), 1.09 (typ) | 0.273 /um x 8.4 mA = 2.29 | 1.37 at code 0 |
     | TU_x_T1 | **1.09** | 1.082 /um x 2.1 mA = 2.27 | 1.09 |
     | TU_x_T2 | 0.91 | | 0.91 |
     | TU_x_T3 | 0.71 | | 0.71 |
     | TU_x_T0 | 0.57 | | 0.70 at code 1 |

   - **Location** (`lo13/res_j.json`). The peak is a horizontal Metal2 bar 0.46 um tall, for example TU_P_T1 at (102.26, 390.38) and TU_P_B at (128.28, 389.18).
     - The bar is the top of each resistor drop: M2 99.86..103.06 x 390.38..390.84 over the 3 V1 cuts at y 390.48.
     - The drop joins the bar at one end, so the first cross-section carries the whole unit current: fraction 0.498 for T1 and 0.1256 for B.
     - Unit current is 10.5 / (8 + code). It stays within 2.09 mA/um x 0.46 um = 0.96 mA only from code 3 up (0.955 mA, ratio 0.99).
     - Code 2 is in the declared window. ff/22/3.35 rt has codes 2-3 inside +-10 %, although no corner's best code is below 3 (termtab: rt 3..12, rh 3..13).
     - Every unit of every group has this bar.
   - **Per cut, the high corner is not the worst.** The typ corner per-cut fractions are about 5-7 % higher than high on every TU net (B 0.0476 vs 0.0444, T0 0.341 vs 0.336, T1 0.175 vs 0.170).
     - The cut ratios stay at or below 0.69 at codes 2..13, so nothing is over.
     - Still, "high = worst corner" does not hold for cuts.
   - **Codes.** em_check covers codes 2..13 only, but the 4-bit register can hold codes 0, 1, 14 and 15. Codes 14 and 15 lower every current. Codes 0 and 1 raise B (10.5 mA) and T0 (1.17 mA):
     - cuts: B 0.87, T0 0.69;
     - bar: 1.37 at code 0.
   - **Condition C1.** Do the following, then rerun netres on TU_*:
     - Make the head landing bar at least 0.6 um, preferably 1.0 um (at code 2, 1.05 mA needs at least 0.50 um), or join the drop to the middle of the cut row.
     - Make em_check run netres TU_* with `path_fraction` at most 1/(2 x 8), for example 0.02.
     - Take the max over typ and high.
     - Either screen codes 0..15 or have the digital clamp the code to 2..13 (state which).
   - Alternative: an explicit acceptance ruling for 1.10x on a segment about 1 um long. A short-length (Blech) argument is plausible, but the rating has no such credit.

2. **CONDITION (EM current basis; interface): 10.5 mA per pad is the DC-balanced average at MAIN 21 mA with POST at 0.** All em_check margins scale linearly with it.
   - `wired_tx/INTEGRATION.md:52-53` and `README.md:99` say MAIN and POST are each an 8-bit DAC with an LSB of about 83 uA. So POST can add up to about 21 mA more pad current.
   - A static or long-run-length state puts the whole tail current in one leg. With the far end terminated that is about 3/4 of the tail: 15.75 mA in that leg's resistors at 21 mA. With the far end open it is all 21 mA.
   - At 15.75 mA DC, the fixed a13 worst case (0.84 at 10.5) becomes 1.26. The TERM_VCM pin path (0.58 at 21 mA) and the bus (0.65 at 21 mA) exceed the rating at a total CM current of about 36 / 32 mA.
   - **Condition C2.** Wired TX or the register map declares the ceiling:
     - time-average per-leg current at most 10.5 mA;
     - MAIN + POST at most 21 mA at the pad;
     - no long-term static drive at max code with the termination on (or accept it as a duty-cycle exception).
     - Otherwise, rerun the screen at the real maximum.
   - Driver-side nets are fine on the same res.json: SUM_*, MAIN_TAIL_*, PAD_P/N -> SUM, and VSS are all at or below 0.30 of the rating at 2.625 mA per slice. That is a static 21 mA in one leg, typ and high. PAD bond -> res at 21 mA is 0.77. The `nmos:` path on PAD_P/N with single cuts is the DETECT device (X110, w = 4 um), with no DC.

3. **VERIFIED: the screen flags a12 and a seeded single cut.**
   - a12 was rebuilt from the STATUS a12 command (`a12/`, DRC 0, LVS unique). em_check on it gives **10 paths over**: all 10 TU_* nets, worst 3.74 (TU_x_B per cut). Values: T1 2.10 mA through a single cut (3.62) and 5.25 mA/um (2.51); T0 1.65 / 1.14; T2 3.02 / 2.10; T3 2.33. These match review-a12 F1.
   - STATUS says 44 paths over on a12. I get 10, because the screen reads only TU_* (one path each), the TERM_VCM_BUS paths from TERM_VCM, and TERM_VCM. The 44 is not reproduced, so STATUS should be corrected.
   - Seed: 5 of the 6 V2 cuts removed at TU_P_T1 (100.49-101.27, 383.87-385.17). netres reports a single cut V2 at (100.62, 385.04) at fraction 1.0. em_check gives OVER 1, 3.62, exit 1.
   - Limit: the a12 rebuild cannot be byte-compared with the deleted a12 GDS (4fbb84f4). It reproduces the a12 F1 numbers exactly.

4. **My view on 0.84 of the 85 C rating at the worst code and corner together.** Acceptable once F1 is fixed and C2 is declared.
   - The number stacks several worst cases at once: high (thin) metal, the least-favourable code at the window edge, MAIN at full scale, 85 C, and a DRM rating that already includes a lifetime margin.
   - A 16 % margin on top of that is normal practice.
   - It is not acceptable as a claim while the real worst case is 1.10 (F1), or if the per-leg average can exceed 10.5 mA (F2). There, 0.84 becomes 1.26.

5. **INFO: no regressions.** Limit table below.
   - Every a13 bench json model_sha256 matches the current file. Checked: ac rt/c, term rt/rh/off, offleak, cmdrop, and the 4 queue ESD cases plus my 7.
   - **Rerunning the untouched ESD cases.** The layout change only touches the termination legs, which carry no ESD current (switches off), and adds 0.024 pF to the pad. The primary diodes, rails and bond-to-diode metal are unchanged. Rerunning was therefore not strictly needed.
     - Because a13_rh is a new extraction, I reran every remaining CDM 2 A case and four HBM cases. All match a12 within 0.01 V.
     - Not rerun: HBM vdd+, which stays BOUNDED as accepted in review-a12 F5, and CDM 1 A / 3 A.
   - The default path rebuilt here (`dflt/`) normalises to 3a706943, the same as b/a4. Its schematic is byte-identical.

## Limit table (a13)

| Limit | a13 | Result |
|---|---|---|
| EM TU straps, per cut (0.58 mA, typ+high, codes 2..13) | <= 0.69 (B typ); a12 3.74 | PASS |
| EM TU straps, per run (2.09 mA/um, all segments, path_fraction 0.02) | **1.10** (B, head bar 0.46 um) / 1.09 (T1) at code 2; 0.99 at code 3; 1.37 at code 0 | **OVER (F1)** |
| EM TU straps, runs at >= 50 % only (as em_check) | 0.84 (T1 1.2 um column) | (incomplete screen) |
| EM TERM_VCM bus / pin (21 mA) | 0.065 /um -> 0.65; pin 0.58 per cut | PASS (at 21 mA basis, F2) |
| EM driver nets (static 21 mA one leg) | <= 0.30; PAD bond->res 0.77 | PASS |
| Termination +-10 %, 23 corners rt / rh | worst 4.83 / 4.83 %; best code rt 3..12, rh 3..13; P-N -0.42..-0.18 ohm | PASS |
| Code margins | ss/32/3.15: rt 11-13, rh 11-13; ss/32/3.35: rt 10-12, rh 10-13; ff/22/3.35: rt 2-3, rh 3 only | PASS (ff rh single code, 99.3 ohm) |
| Termination off | >= 1.46e10 ohm diff | PASS |
| Off-leak, TERM_VCM 0 V | <= 0.00001 mA (5 corners) | PASS |
| Pad C <= 3.223 pF | rt 3.105, c 3.015 | PASS |
| CM1 <= 5 ohm (ss/32/3.15, rh) | 70.3 mV / 21 mA = 3.35 ohm; pads 0.928 / 0.924 V | PASS |
| CDM 2 A, MOS <= 8.0 V | vss+ 6.92, pp+ 7.27, pp- 7.27 (queue); vdd+ 3.92, vdd- 0.99, vss- 0.99 (tanh; PULSE incomplete as before) (rerun here) | PASS |
| HBM 1 kV | pp+ 4.35 (queue); pp- 4.35, vss+ 3.73, vss- 0.88, vdd- 0.88 (here); vdd+ bounded (a12 F5) | PASS |
| Magic DRC / KLayout DRC (main + antenna) | 0 / 0 + 0 (kldrc.json names a13 sha 72af3d5a) | PASS |
| LVS | netgen unique; rb_pos match, rb_neg control mismatch (expected) | PASS |
| rail_site_check | RAIL-SITE txpad_a13 PASS, main 0, antenna 0 | PASS |
| Latch-up | 0.0 um2 uncovered at 15 um (lu.json names sec/b/a13) | PASS |
| Default rebuild == a4 | normalised 3a706943 == b/a4 (rebuilt here) | PASS |
| a13 reproducible | rebuild normalises to 56d59369 == sec/b/a13 | PASS |

## Conditions for publication

- C1 (F1): widen or centre the resistor-head Metal2 landing bar (at least 0.6 um). Fix em_check: low `path_fraction` (sub-path runs), max over typ and high, codes 0..15 or a declared clamp. Rerun netres TU_*. The alternative is an explicit acceptance of 1.10x at code 2.
- C2 (F2): wired TX / the register map declares the EM current basis: per-leg average at most 10.5 mA, MAIN + POST at most 21 mA, and the static-drive policy. Otherwise rescreen at the real maximum.
- Carried over from review-a12 (interface, unchanged): wired TX acknowledges TERM_DISCHARGE 2 x 20 um and the a11 condition 1.
- STATUS: correct "a12 under the same screen: 44 paths over" to 10.
