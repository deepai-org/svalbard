# Independent review: pad_txpad candidate a11 (a10 + wide 3.3 V TERM_VCM disconnect, 2 x 64 x 24/0.28 = 3072 um)

Reviewer verdict: **GO with conditions.** Every declared limit is met. The exception is HBM 1 kV vdd+, which was already known to be open and has a written bound. The a10 F1 common-mode collapse is closed: the disconnect plus its wiring is 3.6 ohm at ss in the high-metal model.

One gap needs a decision outside the pad (F1). I ran the first bench that drives the real tail with the termination on. It shows the driver losing 9-23 % of its current at TERM_VCM = 1.65 V, and 25-34 % with a 25 ohm TERM_VCM source. Most of that loss is the system headroom budget, not the pad's metal. Even so, no limit covers it and no wired TX row has run it with this model.

Object:
- GDS: `sec/b/a11/pad_txpad.gds`, sha256 a52eec43...069e. The same sha appears in `r11/res.json`, `checks/a11/kldrc`, and the rail-site json.
- Models: a11_rh 31c52342 and a11_rt fecf675e. These are the shas recorded in every a11 bench json.
- Generator: `tx_pad_layout.py` sha 7ec89584.

Rebuilt here (outputs deleted, logs `rb11.log`, `rbdef.log`):
- a11 options: normalised GDS 44470454 = evidence GDS, schematic identical, DRC 0, LVS unique.
- Default path: normalised 3a706943 = `b/a4`, schematic identical.

## Findings
1. **HIGH (interface; condition before wired TX signs off): with the termination on, the driver tail is out of saturation and delivers 9-34 % less than its set current. No bench or limit covered this until now.**
   - Bench: `drvop.py` on a11_rh (sha 89554d1b, json `a11rh-drvop.json`):
     - MAIN_P = VDD, 21 mA set with the tb2 `out` bias.
     - Termination on at the in-window code of each corner: ss 13, tt 7, ff 4, ss/3.5 V 11.
     - TERM_VCM 1.65 V, either ideal or behind 25 ohm.
     - Far end either open (AC-coupled far end, long run) or 100 ohm differential.
     - Delivered current is I(TERM_VCM) minus the discharge-resistor current, measured with the driver off.
     - Reference is the same corner with the termination off and 50 ohm to VDD (`tb2 out`).

     | Corner | ref mA | open, ideal VCM | open, 25 ohm | 100 ohm far, ideal | 100 ohm far, 25 ohm | pad_p / SUM / tail V (open, ideal) |
     |---|---|---|---|---|---|---|
     | ss 32 3.15 | 18.00 | 14.66 (-18.6 %) | 12.72 (-29.3 %) | 15.61 (-13.3 %) | 13.55 (-24.7 %) | 0.91 / 0.52 / 0.32 |
     | tt 27 3.3 | 20.11 | 15.98 (-20.5 %) | 13.42 (-33.3 %) | 17.33 (-13.9 %) | 14.52 (-27.8 %) | 0.84 / 0.54 / 0.35 |
     | ff 22 3.35 | 20.34 | 17.09 (-16.0 %) | 14.07 (-30.8 %) | 18.51 (-9.0 %) | 15.26 (-25.0 %) | 0.81 / 0.56 / 0.38 |
     | ss 32 3.5 | 19.87 | 15.35 (-22.8 %) | 13.04 (-34.4 %) | 16.57 (-16.6 %) | 14.03 (-29.4 %) | 0.87 / 0.54 / 0.34 |

   - Cause:
     - The low pad sits at about TERM_VCM - I x 50 ohm, which is 0.8-1.0 V.
     - The 6 V cascode, the 3.3 V switch and the 20/1 tail then get about 0.3-0.4 V each, so the cascode and the tail are in triode.
     - The pad's own share is small. From the 0 / 25 ohm pair the sensitivity is about 6 mA/V. The disconnect (54-76 mV) costs about 0.3-0.45 mA. All of the pad metal together (about 0.15 V) costs about 1 mA, or 5 %.
     - The rest is the TERM_VCM level against the stack headroom: a system / wired TX budget item, not a pad defect.
   - With a 25 ohm source, TERM_VCM itself falls to 1.24-1.31 V. The termination buffer is not characterised for 21 mA sourcing: its `source-capacity-diagnostic/decision.json` says "Do not adopt", with the original error 0.20 V. So "ideal 2 ohm" in the wired TX benches (`INTEGRATION.md:113`) is optimistic.
   - Condition:
     - (a) Wired TX reruns its real-chain eye rows with the a11 R+C model, termination on, and a TERM_VCM source impedance that pads states for `tx_term_buffer`.
     - (b) If the current loss is not acceptable, the remedy is a TERM_VCM level or driver headroom decision (for example TERM_VCM about 2.0 V). If TERM_VCM changes, the pad must recheck its termination table and off-leak at the new level.
     - (c) Add this bench (or `drvop.py`) to the pad evidence set.
2. **MEDIUM (EM; pre-existing, not introduced by a11, still open): the static TERM_DISCHARGE path runs 1.2-1.7 mA DC through single-cut vias and 0.38 um Metal1.**
   - netres `r11/res.json`, TERM_VCM high, path `pin|res`: narrowest 0.38 um M1 (x 104.6, y 678.4), single cuts V1 / V2 / V3 at fraction 1.0.
   - The current is 1.20 mA at ss and 1.68 mA at ff (cmdrop / drvop, driver off at 1.65 V).
   - The ratings used in this project (`wtx_mux8_layout.py:42`, DRM 14.2, 85 C) are 0.58 mA per cut and 2.09 mA/um. Against those, this path is 2.9x over per cut and about 4.4 mA/um in M1.
   - This was flagged by wired TX ("pads to confirm", `INTEGRATION.md:113`).
   - Condition: widen the strap and use multi-cut vias (or raise the resistor value) in the control cell, then rerun netres.
3. **LOW (EM, marginal): TERM_VCM_BUS shows a max run density of 0.100 /um per unit current** (netres, paths disconnect -> native switches).
   - At 21 mA that is 2.1 mA/um against 2.09 mA/um (Metal1-4, 85 C). netres does not name the run. The reported narrowest section (M2 10 um riser, fraction 0.50) is only about 1.05 mA/um.
   - The pin side is fine: 0.0209 /um, or 0.46 mA/um, and at most 0.35 mA per V3/V4 cut.
   - Condition: identify the 0.1 /um run. If it is a single-layer 10 um piece carrying the full current, widen it or stack it.
4. **MEDIUM (known open, condition): HBM 1 kV vdd+ stops at 5.05 ns** (both `a11p` and `a11c` runs), at a 0.26 V pad peak. The designer's written bound is the only evidence. The condition from review-a10 stands: a converged run, or an explicit ruling that accepts the bound.
5. **LOW: the latch-up evidence (`sec/checks/a11/lu.json`) names `sec/b/a11n/pad_txpad.gds`, a path that does not exist, and it records no sha.** I reran `lu.sh` on the evidence GDS (`lu.json` here) and got the same numbers: 0 um2 uncovered at 15 um, 1411.99 / 502.19 um2 at 5 / 10 um. Closed by my rerun. The designer should rerun from the right path.
6. **INFO: the termination was verified small-signal only.** Under the DC common-mode current the leg is about 6 % lower than its small-signal value (cmdrop, ss code 8: 64.4 ohm at 10.5 mA against 68.6 ohm). This is inside the +-10 % margin. It is stated so that wired TX does not double count it.
7. **INFO: review-a10 findings.**
   - F1 (the disconnect collapses the common mode): closed. CM1 is 3.60 ohm at ss/3.15/32 high metal (75.6 mV / 21 mA). My `drvop` run independently gives 3.66 ohm (53.6 mV at 14.66 mA).
   - F2 (CDM 2 A vdd+ incomplete): closed. It completes to 3.6 ns, MOS <= 3.92 V.
   - F3 (ff edge): unchanged and acceptable. rt has code 3 only (97.3 ohm). rh has codes 3-4.
   - F4 (off-leak json without model sha): closed. Every offleak json records fecf675e.
   - a8 findings: they stay closed (vss- CDM is complete, junctions are checked, the rb control is a real mismatch).

## Limit table (my numbers, recomputed from the a11 jsons unless marked)
| Limit | a11 | Result |
|---|---|---|
| Term 100 ohm +-10 %, code in 2..13, 23 corners, rt | worst best-code 4.24 % (fs 32 3.35), every corner in window | PASS |
| Same, rh | worst 4.19 % (ff 22 3.35); ss 32 3.15 codes 12-13 (14-15 also in window) | PASS |
| P-N <= 1.0 ohm | -0.42 .. -0.20 | PASS |
| Termination off (TERM_ENABLE 0) > 10 kohm | >= 1.0e10 ohm | PASS |
| Off leak at TERM_VCM 0 / 1.65 V, pads equal, < 0.01 uA | 0.00 (resolution 0.01 uA) in 5 corners | PASS (at the resolution) |
| Off leak with the pads 1 V apart | <= 0.16 uA (ff 32) | info |
| CM1 disconnect + wiring <= 5 ohm, ss high metal | 3.60 ohm (designer); 3.66 ohm (mine) | PASS |
| Pad C <= 3.223 pF / leg at 100 MHz (rt) | 3.076 pF (C-only 2.986) | PASS |
| Gate C MAIN/POST/TMDS | 0.19 / 0.30 pF at 0 / 3.3 V | PASS (against the published values, not recomputed) |
| O1 / O3 at 21 mA (rh, tt) | bond to cascode 35.7 mV; total 53.9 mV <= 60 | PASS |
| CDM 2 A, all 6 cases (PULSE; vss- smooth) | 6 V devices max 7.27 V (pp+) / 8.0; 3.3 V devices (incl. the disconnect) <= 0.84 V / 5.0; all complete | PASS |
| HBM 1 kV, 6 cases | 6 V <= 4.35 V; vdd+ stops at 5.05 ns | 5 PASS, vdd+ OPEN (F4) |
| HBM 2 kV (report) | 5.73 V | PASS |
| CDM 1 A / 3 A (report) | 5.04 V / 9.62 V (over 8.0 at 3 A) | PASS / MISS (info) |
| Junctions < bv | worst 7.1 V at 2 A (9.5 V at 3 A) | PASS |
| Primary diodes 10 / 1 mA/um | 5.00 / 0.043 mA/um (CDM 2 A); HBM 2 kV 3.31 mA/um, 18.6 nJ | PASS |
| ESD known answer (6.764 V +- 0.15) | 6.747 V | PASS |
| DRC / netgen LVS / rb pos + failing neg / KLayout 0/0 / rail_site / railconn | DRC 0, unique (rebuilt here); rbverdict pos PASS, neg mismatch; CLEAN 0/0; PASS; clean | PASS |
| Latch-up 15 um 0 um2 | 0.0 (my rerun on the evidence GDS) | PASS (F5) |
| Rebuild a11 / default = a4 | 44470454 / 3a706943 match, schematics identical | PASS |
| **Driver current with the termination on (no declared limit)** | -9 .. -23 % with an ideal VCM, -25 .. -34 % behind 25 ohm | **NOT COVERED (F1)** |
| **EM, TERM_DISCHARGE path (no declared limit)** | 1.2-1.7 mA per single cut, against 0.58 | **OVER (F2)** |

Files: `drvop.py`, `drvop.log`, `a11rh-drvop.json`, `lu.json`, `lu.log`, `rb11.log`, `rbdef.log` (rebuild and bench intermediates deleted).
