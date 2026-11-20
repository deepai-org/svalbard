# Independent review: pad_hspad candidate a6 (2026-11-20)

Object: `sec/build/a6/pad_hspad.gds` sha256 07b6800d73eab73e31acb0ce7756436e37e999d3e707adf486b0e5ec7b226953 (built 22:00:10, unchanged since;
every check / model / bench below is newer and reads that path). Leg `sec/build/leg7` (`--lb=4.2 --sec='{"up":[1,1],"dvdd_w":3.0,"ring":true}'`).
Limits used: STATUS.md "Pass limits" + "Declared before the a5 queue" + the binding rulings in the brief (RX = 3.3 V oxide, 5.0 V; CDM at 2 A with 1 nF; C +0.15 pF/leg).
Designer's a6 result text was not read before this verdict.

## Verdict: GO with conditions
All declared limits at the requirement points pass on the exact GDS, with working negative controls, and the default build reproduces
the published cell. The CDM 2 A / 1 nF pass rests on an unsourced provider-ring resistance; at 2x that value it fails (finding 1).

## Findings
1. **MAJOR - CDM margin depends on an unsourced ring model.** `esd2.py` ring RN/RF = 0.10/0.30 ohm (typ), 0.125/0.375 (high); stated as an
   ASSUMPTION in the docstring, not in `spec/design-assumptions.md` (MANDATE 3: value, source, pessimistic bound). "high" is only +25 %.
   Reviewer rerun, CDM 2 A, 1 nF, high metal, P-N: declared ring -> worst gate 7.31 V (reproduces the json), diode rev 10.73 V, RX 4.11 V;
   ring 0.25/0.75 ohm -> worst gate **8.33 V, 15 switches over 8.0 V (E1 FAIL)**, nd2ps reverse **11.79 V > 11 V (E3 FAIL)**, RX-VSS 4.94 V (0.06 V from 5.0).
   Evidence: `review-a6/rev_cdm2_high_PN.json`, `review-a6/rev_cdm2_x2ring_PN.json`, `review-a6/esd_rev.py`.
   Condition: derive ring R (DVDD and DVSS bands, site to nearest dvdd/dvss cell) from the provider ring extraction, enter it with a pessimistic bound,
   rerun the CDM 2 A 1 nF matrix (high metal) at that bound.
2. **MINOR - thin E3 margin at the requirement point.** CDM 2 A 1 nF high: primary nd2ps reverse 10.47-10.73 V against the model bv 11 V (0.27 V);
   the model's own breakdown is helping clamp, so the number is bv-model dependent. `sec/esd/a6rh_cdie.json`.
3. **MINOR - ESD bench is typical devices / 27 C only** (diode Rs, bv and clamp corners not swept). Not a declared limit; noted as optimism.
4. **MINOR - receiver input surrogate.** RX load is nfet_06v0 16/0.7 x6 at the deck top level (not in the E1 device scan); the real input is pfet_03v3.
   Judged instead by RX-VSS / RX-VDD node voltages against 5.0 V, which bounds Vgs/Vgd of the real pfet as long as its source/body sit near VDD. Acceptable; gate C differs slightly.
5. **INFO - current density.** CDM 2 A 1 nF high P-N: site diodes 375 mA each (7.2 mA/um perimeter); the 50 secondary 1x1 um pd2nw carry 127 mA in total
   (each < 28 mA, < 7 mA/um). Not a concern at 1 ns. `review-a6/rev_cdm2_high_PN.json`.
6. **INFO - generator changed after the designer's repro record.** `sec/repro.txt` names hs_leg_layout.py d85fda3f; the tree has 7be4a1f6 (21:59, a6 `ring` option).
   Reviewer re-ran with the current generators: default leg (`--lb=4.2`, no `--sec`) normalised sha 144da01fe9770de3 == build/leg5; no-flag composition with
   the published leg (hsfix leg4) XOR vs published pad_hspad.gds **0.0 um2**. `review-a6/legdef.log`, `review-a6/def4.log` (GDS deleted after the check). Default path PASS.
   (One unguarded line in the default TU loop, `if not tx1-.2 <= x0+.6*dd <= tx2+.2: continue`, did not change the default output.)
7. **INFO - leg standalone KLayout PP.2 x20** (`build/leg7.log`, pass:false) is identical in the default/published leg5; composed cell precheck is clean. Pre-existing.
8. **INFO - return loss (budget request, not judged).** Die RL at 2.4 GHz, `_rail` typ: a6 6.91-7.22 dB vs f6 7.36-7.65 dB, worst delta **0.67 dB** (ss_32_3.35), typ_27 0.43 dB;
   COB high-band 0.21-0.29 dB worse. Declared 0.3 dB: die miss, COB inside.
9. Models contain what they claim: `models/a6_r_{typ,high,low}.spice` = extracted a6 (50 switches, 50 secondary pd2nw on per-cathode nodes DVDD__s*, 10+10 site diodes,
   VSS__a / DVDD__k return resistors, distributed DVDD mesh: land->all cathodes 3.28/4.68 ohm typ/high, per cathode 10.9-17.1 / 28-40 ohm); ring and RX gate in the bench.
   Every ESD json's model_sha256 matches the file on disk; term/AC benches carry the model shas (045547de / e8402507 / 2f088962 / eadcf8d3).

## Limit table (reviewer numbers, recomputed from the jsons)
| Limit | a6 (reviewer) | Result |
|---|---|---|
| Magic DRC / composer LVS / device audit | 0 / match / match (`build/a6.log`) | PASS |
| Read-back LVS pos / sch (554 dev) | match uniquely / match uniquely | PASS |
| Controls RX swap / site diode / secondary diode | mismatch / property+census / pin+census | PASS (fail) |
| KLayout precheck cell / on rail | 0/0 / 0/0; sliver control 4 violations | PASS |
| Latch-up uncovered 15 um | 0.0 um2; control 6.4 um2 | PASS |
| rail_site_check + selftest, railconn | PASS / OK / clean | PASS |
| Floating lines | 1 (shell m2_2279_124800#) | PASS |
| No-flag XOR vs published | 0.0 um2 (reviewer rebuild) | PASS |
| Outline / pins | (-0.055,0)-(492,912.91), DVDD port as a4 | PASS |
| ESD known answer / site-strip / sec-strip controls | 2.781 V, 2.100 V / 29.2 kV / 10.32 V, 25 over | PASS |
| E1 HBM 2 kV & 1 kV, typ+high, 10 cases | worst gate 5.26 V (6 V oxide), 0 over | PASS |
| E2 RX (5.0 V, 3.3 V oxide) HBM 2 kV incl. pad-to-pad | max 4.69 V (P+N high) | PASS (0.31 V) |
| E5 bond pad HBM VSS/VDD cases | max 6.79 V | PASS |
| E1 CDM 2 A, 1 nF, typ / high | 6.72 / 7.31 V, 0 over | PASS (fails at 2x ring, F1) |
| E2 RX CDM 2 A 1 nF | max 4.11 V | PASS |
| E3 diode reverse (11 / 10.5 V) HBM / CDM 2 A 1 nF | 6.89 / 10.73 V (nd2ps) | PASS (thin, F2) |
| E4 MIM <= 6.0 V HBM / CDM 2 A 1 nF | 3.91 / 5.18 V | PASS |
| CDM without 1 nF / 3 A (information) | 2 A high: 9.57 V, 25 over; RX 7.54 V | reported |
| C per leg `_rail` typ vs f6 +0.150 pF | max +0.092 pF (ss_32_3.35); ctest +0.050 avg (=+100 fF on P) | PASS |
| P/N imbalance <= 20 fF | 5.5 fF | PASS |
| Termination T-A..T-D low/typ/high | PASS (code 7/8/9: 80.2-114.9 ohm); C-only control fails T-A/T-D | PASS |
| Receive loss vs f6 (+0.1 dB) | a6 0.20-0.34 dB better (typ, high, _rail) | PASS |
| Return loss die / COB (+0.3 dB) | 0.67 / 0.29 dB worse | die MISS (under budget request) |

Limits did not move relative to the a5 declaration.
