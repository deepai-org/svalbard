# Independent re-review, pad_hspad a6: provider-ring condition (2026-11-20)

Scope: MAJOR condition of `../review-a6/REVIEW.md` (CDM 2 A / 1 nF pass rested on unsourced ring R). Return loss ignored (budget ruling).
Reviewer files: `rr.py` (esd3 deck, a6_r_high model sha 2f088962, --rxgate, 1 nF; scans all 74 diodes, site vs non-site; optional
`CDIE_AT` moves the 1 nF die cap to its own branch behind the near node), results `*.json` here. One ngspice at a time, OMP_NUM_THREADS=1.

## Verdict: NOT CLOSED
The ring resistance itself is now sourced and the bound is sound. But the CDM result is not governed by the ring-to-clamp
resistance; it is governed by the series path to the bench's 1 nF die capacitor, which esd3 hangs on the FAR node
(site -> 0.155/0.189 -> 0.46/0.57 -> 1 nF + 0.5 ohm). That placement is not sourced by the ring extraction, and the
pass does not survive moderate growth of that path (finding N1). The original condition (pass rests on an unsourced
series resistance) therefore still holds, moved from "ring R" to "path to the die capacitance".

## (1) Extraction - SOUND
- Rates recomputed by hand: DVSS 101.4 um/layer, M3/M4 90 mohm/sq, M5 40 -> 0.209 mohm/um typ; high 0.249. DVDD 0.171/0.203. Match.
- Bound arithmetic: site bidir[15] centre 1189.5 to dvdd0 centre 556.5 = 633 um; x high rate x 1.2 = 0.154 / 0.189 ohm.
  Far: dvss2 centre 2455.5 - 556.5 = 1899 um -> 0.463 / 0.567. Match the row.
- Known answer (108 um straight segment, 22.6 mohm) and two-terminal site14-15 check pass; note both use the same sheet
  values (tool check, not a rho check; `tech_checked: false` in netres out). INFO.
- 15 % discrepancy: long-window netres is lower because M1/M2 of provider/fill cells add parallel paths. The bound uses
  M3-5-only hand rate, farther site, farther near cell for both rails, x1.2: every simplification raises R. The bound bounds
  the ring R to the provider clamps. The near lumping also puts dvss1 (closer) at dvdd0: pessimistic.
- Lumping 12 far cells at dvss2 is optimistic for the 10 cells on other edges, but tested irrelevant: far clamps at 2 ohm
  with the cap kept at the bound position give gate 7.43 V, RX 4.87 V, nd2ps 10.87 V (`c046_f2_cdm_PN.json`): PASS.
- bond_map vs provider-sites.json disagree on which of bidir[14]/[15] is RX_P (designer noted). Irrelevant to the bound; should be reconciled. INFO.

## (2) esd3.py - CORRECT
Diff vs esd2 is only per-rail RINGV, FAR count, args, json fields. Default path reproduces esd2 (`ctl_esd2default.json`
7.313 V / 10.728 V = `sec/esd/a6rh_cdie.json`). Deck sha differs (829984 vs 2fe0ff), numbers identical; INFO.
Reviewer rerun at the bound, CDM P-N: 7.638 V gate, 11.061 V nd2ps, RX 4.44/4.27, MIM 5.29 V: reproduces `bound_cdm2.json`.

## (3) Limits at the bound (recomputed from json)
| case | gate (8.0) | RX-VSS / RX-VDD (5.0) | worst diode rev | MIM (6.0) |
|---|---|---|---|---|
| CDM 2 A, 8 VSS/VDD cases | max 7.26 | max 4.06 / 4.27 | 10.68 nd2ps (site) | max 5.29 |
| CDM 2 A P+N / P-N | 7.51 / 7.64 | 4.42 / 4.44, 4.27 | 11.05 / 11.06 nd2ps (site) | 5.22 / 5.29 |
| HBM 2 kV P+N / P-N | 5.43 / 5.44 | 4.88 / 4.87 (0.11 V margin) | 7.17 | 4.02 |
Non-protection junctions (not in the designer's json; reviewer scan, CDM P-N at the bound, 54 non-site diodes): max 5.54 V
(secondary pd2nw, DVDD__sP*) vs bv 10.5: PASS. All gates 0 over limit. At the stated bound: PASS everywhere (site nd2ps under the per-finger criterion).

## (4) Per-finger criterion - CORRECT, limit reasonably conservative
cur.py integrates the same esd3 deck/waveform; 5 fingers x 375 mA ~= 1.9 A per polarity, consistent with 2 A.
7.24 mA/um forward (72 % of 10), avalanche 0.05 mA/um at 11.06 V (5 % of 1), energy 2 nJ vs HBM 77 nJ. 10 mA/um forward
and 1 mA/um reverse at 100 ns without 1 ns credit are at or below the low end of published STI-diode It2 values; reasonable.
Caveat stays: literature, not foundry; CDM density 1.5x the HBM density; TLP/vf-TLP on the planned site is the real check.

## New findings
**N1 MAJOR - the 1 nF die-cap path is unsourced and load-bearing.** Reviewer sweep, CDM 2 A P-N, ring at the bound, 1 nF moved:
| 1 nF behind near node + | gate | RX-VSS | site nd2ps | non-site max |
|---|---|---|---|---|
| 0.46/0.57 (bench as is) | 7.64 | 4.44 | 11.06 | 5.54 |
| 1.0/1.0 | **8.17** (15 over) | **6.02** | 11.64 | 6.17 |
| 1.5/1.5 | **8.67** | **6.58** | 12.02 | 6.75 |
| far node 2/2 (clamps + cap) | **9.40** | **5.80** | 12.39 | 7.80 |
(`b_cdm_PN`, `c10_cdm_PN`, `c15_cdm_PN`, `f2_cdm_PN`, `f2_cdm_PpN` 9.30 V). Far clamps alone do not matter (finding (1)); the capacitor does.
power-delivery.md section 5.1 (pt_wired): bulk decap is on the macro west side / south edge and stacked tiles west / centre / NE corner;
only 0.26 nF of bond-site tiles (about 18 pF per site, tau 335 ps) sits under the provider rail at the sites. So >= 1 nF reachable from the
east hspad sites through <= ~0.6-0.75 ohm (plus 0.5 ohm ESR) is not shown and plausibly not true. To close: extract (or bound) the
resistance from bidir[15] to the nearest 1 nF of die decap via ring + core ring/grid incl. decap ESR, enter it as a design-assumption row,
and rerun CDM 2 A at that value; or show CDM passes with the cap at the bounded position. Without the 1 nF the case already fails (prior review: 9.57 V).
HBM is insensitive (far 2 ohm: gate 5.36, RX 3.25 V). Near clamps only (far + cap at 100 ohm): CDM gate 10.61 V, RX 8.42 V; HBM P+N gate 6.36, RX 4.83 V (`f100_*`). A run with the cap at 0.46/0.57 and far clamps at 100 ohm did not converge (not used).

**N2 INFO** - designer's E3 table lists only the worst diode; non-protection junctions were not shown separately. Reviewer scan above fills it (PASS).
