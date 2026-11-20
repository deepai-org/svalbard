# Independent review: pad_txpad candidate a8 (merged native nfet_06v0_nvt termination switches, top-edge pins)
Reviewer verdict: **NO-GO as submitted.** It becomes GO with conditions once F1 is resolved (an interface/ruling decision, not a respin) and F2 is closed.

Object: `sec/b/a8/pad_txpad.gds`, sha256 07721a33...f080 (raw). Same sha in layout-info, r8/res.json (netres → models), kldrc.json, railsite.
Models `sec/models/a8_r{t,h}.spice` were built from r8 (built 21:25, GDS 21:24). Nothing was rebuilt after them.
Generator `$P/analog/pads/tx_pad_layout.py` (untracked). I rebuilt with it here:
- default path: normalised sha 3a706943... = `b/a4`, schematic identical.
- a8 options (`--upx {"x":[63,69],"yu":107} --nvt {"wb":21,"wt":23.5,"l":1.8,"lb":2.4,"lt":1.0,"merged":true} --top-pins`): normalised sha 90996695... = evidence GDS, schematic identical.
I deleted my rebuild outputs afterwards.

## Findings
1. **HIGH: the termination cannot be turned off when TERM_VCM is at 0 V.** Native switches conduct at Vgs = 0.
   - The designer's negative control (`a8rt-term-off.json`, > 1e10 ohm) holds TERM_VCM at an ideal 1.65 V, so the switches see Vgs = -1.65 V.
   - Wired TX documents TERM_VCM = VSS for the TMDS-style fallback with the termination off (`$P/analog/wired_tx/INTEGRATION.md:113`). The pad also has its own TERM_DISCHARGE resistor to VSS.
   - Rerun on the a8_rt model with TERM_ENABLE = 0, all trim bits 0, TERM_VCM = 0 V and the pads at 0.5 to 2.9 V: each pad sinks **1.5 mA at tt, 6.3 mA at fs, 9.6 to 10 mA at ff (32 C)**. With TERM_VCM at 1.65 V the same bench gives < 1 nA (`off_vcm.py`, `off_vcm0.py`).
   - Device-level check (`nvt/`, one leg's 520 um at Vg = Vs = 0, Vd = 2.3 V): 1.3 mA tt, 9.2 mA ff, 5.7 mA fs. At Vgs = -0.5 V it drops to nA-uA.
   - Condition: either a binding interface rule that TERM_VCM stays >= ~1 V whenever the pad is in use with the termination off (WT39/INTEGRATION change, and remove TMDS-with-VCM-at-VSS), or switches that turn off at Vgs = 0. Also state the power-down and unpowered behaviour.
2. **HIGH: CDM 2 A, pad negative vs VSS, has not been evaluated.**
   - The designer's run stops at t = 2.205 ns: the pulse starts at 2.0 ns, rises in 0.2 ns, then has a 1 ns flat top. The run therefore ends at the end of the rise and never reaches the flat top.
   - I reran it with tb2 copied as-is (`tb2r.py`, env7): it fails at the same point after all three retry option sets (`esd1.log`).
   - Its 4.10 V and "all MOS < 1 V" are not a result. The physics suggests a benign case (forward nd2ps diodes), but the requirement is "CDM 2 A all 6 cases". Needs a converging run (e.g. a smaller timestep at the rise, or a different integration method), or an explicit ruling.
3. **MEDIUM: the termination margin at ss / 3.15 V / 32 C / high metal is zero.** Code 13 is the only code within +-10 % (105.15 ohm, +5.2 %).
   - Codes 11 to 15 give 117.4 / 111.1 / 105.2 / 100.0 / 95.2 ohm. Code 13 is exactly the edge of the declared 2..13 window, so it passes on the letter with no slack.
   - The a4 +-5 % check (reported only) has no code in 2..13 at this corner (14 and 15 pass it).
   - The spread is driven by the native switch: code 2 spans 120 ohm (ff) to 253 ohm (ss). Temperature is covered only at 22 / 32 C (as declared). Any hotter or colder corner, or Vt mismatch, eats the margin.
4. **MEDIUM: the E3 check (non-primary junctions < bv) passes vacuously.**
   - All 26 diodes in the model are primary (SVDD/SVSS), so `worst_rev_v` = 0 in every run.
   - MOS drain/source-to-bulk junctions (nvt drains up to ~6.5 to 6.9 V during CDM 2 A) are not checked against a bv.
5. **LOW: the read-back LVS negative control is real, but its verdict prints FAIL.**
   - `swap.py` swapped 3 labels (1 MAIN_P and 2 MAIN_BIAS; the top-edge pins add the second MAIN_BIAS label).
   - netgen gives a mismatch ("Top level cell failed pin matching", unique False), which is the expected signature.
   - `rbverdict.py` only accepts the string "swapped 2". Fix it to accept >= 2, or record the label count.
6. **LOW: O1 depends on the metric.** The effective parallel bond-to-cascode resistance from the 21 mA drop is 1.40 ohm (typ) / 1.77 ohm (high), a PASS.
   - Point-to-point per unit is 1.70 to 2.01 ohm typ and 2.92 to 3.30 ohm high (`r8/netres.log`), so the farthest unit is over 2.0 ohm.
   - The a4 used the same effective metric. State it explicitly.
7. **LOW: the trim-branch metal is thin.** TU_x_T0/T1 run through 0.4 um Metal2 with 2 single-cut vias, 38.9 ohm high metal.
   - This is in the model and so in the termination numbers. It is a robustness/EM note only.
8. **INFO: limits moved, but by binding rulings and not by the designer.** Each change is traceable to PC-49 / WT39:
   - T1: +-5 % → +-10 % incl. metal (the +-5 % is now only reported).
   - Pad-node C: 3.193 → 3.223 pF.
   - CDM decap: 1 nF at the site, 1.4 ohm loop = 0.7 ohm per rail. Implemented as Cdie RD-DIEX + 1.4 ohm DIEX-RS, which matches the ruling.
   - Primary diode density is normalised by pj = 51.8 um (perimeter), as in `../ring/REPORT.md`.

Verified OK:
- NAT and DUALGATE on the evidence GDS (`natchk.py`): 10 NAT polygons, exactly 46 gates inside NAT (= the 46 nvt fingers, w 21 / 23.5, l 1.8). NAT outside DUALGATE: 0. NAT overlapping NWELL: 0.
- The KLayout main deck ran NAT.1 to NAT.12 ("nat has 10 polygons"), main 0 / antenna 0.
- The read-back extraction finds the 46 nvt devices and the census is equal, so NAT is effective in the GDS.
- Magic DRC 0, LVS unique. Latch-up 0 um2 at 15 um. rail_site PASS, railconn rc 0.
- A1 bbox (KLayout) 3.5..285 x 0..692.26: inside the outline. Core pins sit at y 691.76 to 691.86 (top edge).
- Known answers: termination 91.577 (expected 91.58), ESD 6.747 V (6.764 +- 0.15).

## Limit table (my numbers, recomputed from the json)
| Limit | Value | Result |
|---|---|---|
| T1w 100 ohm +-10 %, code in 2..13, 23 corners, rt | every corner has >= 2 codes; ss_32_3.15: codes 12-13 | PASS |
| T1w, same, rh | every corner >= 1 code; ss_32_3.15: only code 13 (105.15) | PASS, 0 margin (F3) |
| a4 +-5 % (reported) | rh ss_32_3.15: no code in 2..13 | MISS (info) |
| P-N <= 1.0 ohm | 0.40 to 0.47 | PASS |
| TERM_ENABLE 0 > 10 kohm, TERM_VCM 1.65 V | >= 1.47e10 | PASS |
| TERM_ENABLE 0, TERM_VCM 0 V (my run) | 1.5 to 10 mA per pad | **FAIL (F1)** |
| Pad-node C at 100 MHz <= 3.223 pF (rt) | 3.062 (c-only 2.973) | PASS |
| Gate C MAIN/POST/TMDS <= published | 0.30 / 0.30 / 0.29 vs 0.49 / 0.43 / 0.40 pF | PASS |
| O1 <= 2.0 ohm (effective) typ / high | 1.40 / 1.77 | PASS (F6) |
| O2 P/N <= 0.5 ohm | equal (netres) | PASS |
| O3 <= 60 mV at 21 mA typ / high | 37.6 / 53.9 mV | PASS |
| HBM 1 kV, 6 cases: 6 V <= 8.0, 3.3 V <= 5.0 | 6 V max 4.36 V; 3.3 V max 0.81 V | PASS |
| CDM 2 A, 5 complete cases | 6 V max 7.28 V (pp, 0.72 V margin); 3.3 V 0.84 V | PASS |
| CDM 2 A vss:neg | incomplete at 2.205 ns (reproduced) | **NOT EVALUATED (F2)** |
| HBM 2 kV (reported) | 5.74 V | PASS |
| CDM 1 A (reported) | 5.05 V | PASS |
| CDM 3 A (reported) | 9.59 V | MISS (info) |
| Primary diodes 10 mA/um fwd / 1 mA/um aval / 78 nJ | 5.00 / 0.053 / 18.6 nJ (HBM 2 kV) | PASS |
| E3 non-primary junctions | none in the model | VACUOUS (F4) |
| Layout / DRC / LVS / NAT / LU / A1 / ASM-2 / default path | see "Verified OK" | PASS |

Files written by this review (in this folder): `off_vcm*.py`, `nvt/*.sp`, `natchk.py`, `tb2r.py`, `esd1.log`, `bench/r_cdm2vssneg/` (raw data deleted), `dflt.log`, `a8.log`, `a8/` (small files only).
