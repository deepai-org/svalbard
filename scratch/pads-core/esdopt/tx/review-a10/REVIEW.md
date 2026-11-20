# Independent review: pad_txpad candidate a10 (a9 + 3.3 V TERM_VCM series disconnect)
Reviewer verdict: **NO-GO as submitted.** The a8 findings are closed. But the new disconnect puts about 30 to 48 ohm of common-mode resistance in series with TERM_VCM. The whole driver current returns through it, so the pad common mode collapses (F1). No declared limit covers this, and no bench exercised it.

Object: `sec/b/a10/pad_txpad.gds`, sha256 b9fa12a6...36bd. The same sha appears in r10/res.json, kldrc.json and lu.json.
Models: `sec/models/a10_rt` 1567699c, `a10_rh` 94c7eb4e. These are the shas recorded in every bench json.
Generator: `tx_pad_layout.py` sha 2046bd98. I rebuilt both paths here and then deleted the outputs:
- a10 options: normalised a7d9e015 = evidence GDS, schematic identical, DRC 0, LVS unique.
- Default path: normalised 3a706943 = `b/a4`, schematic identical.

## Findings
1. **HIGH: the disconnect (nfet_03v3, 8 x 12.5/0.28 = 100 um, gate TERM_ENABLE_LOCAL) carries the full DC tail current, and its on-resistance collapses the pad common mode.**
   - Bench: `cmdrop.py` on a10_rt. Termination on at code 8, TERM_VCM an ideal 1.65 V, DC current sinks at the pads (all current returns through TERM_VCM, as with a differentially terminated or AC-coupled far end).
   - Drop TERM_VCM to TERM_VCM_BUS at 21 mA:

     | Corner | Drop across the disconnect | Equivalent | Pads at 10.5 + 10.5 mA | Low pad at 21 mA on one side |
     |---|---|---|---|---|
     | ss / 32 C / 3.15 V | 1000 mV | 48 ohm | 0.07 V | -0.42 V |
     | tt / 27 C / 3.3 V | 736 mV | 35 ohm | 0.46 V | 0.06 V |
     | ff / 22 C / 3.35 V | 598 mV | 28 ohm | 0.69 V | 0.39 V |

   - Wired TX expects the common mode to "step up by I x 25 ohm, 0.2-0.5 V" (`INTEGRATION.md:139`) from a 2 ohm source. With the disconnect the step is 2 to 3 times that, and at ss the cascodes and switches have no headroom left. A real driver would lose current or eye amplitude rather than show negative pad voltages, but it fails either way.
   - Why the benches missed it:
     - `tb2 term` is differential (+-10 mV about the common mode), so the disconnect current cancels.
     - `tb2 out` runs with the termination off and 50 ohm to VDD.
     - The designer's own a9 note says "needs a CM-impedance limit". None was declared for a10.
   - Condition:
     - Declare a TERM_VCM common-mode limit, for example disconnect drop <= 50 mV at 21 mA at ss, or whatever wired TX accepts.
     - Then size the disconnect to meet it. Roughly 10x the width, or a 3.3 V transmission gate. Recheck pad C, ESD and leak.
     - Alternatively, drop the disconnect under WT51: keep `term_buffer` alive whenever the island is on, plus a ruling on the island-off state.
     - Either way, wired TX must rerun its pad=RC rows with the real common-mode path.
2. **MEDIUM (condition): CDM 2 A vdd+ is still incomplete.** Both PULSE runs (`a10p`, `a10c`) stop at 2.251 ns; smooth edges stop at 1.86 ns.
   - At the stop, the 2 A peak has been reached (primary diodes 5.0 mA/um, the same as vss+). MOS stress is at most 3.91 V (8.0 V limit), pad to local VSS is 4.78 V, and DVDD minus DVSS is 0.07 V.
   - Physics: the current returns directly into the zapped DVDD through the up-diodes, so the flat top is unlikely to add much stress. I judge it bounded with about 4 V margin.
   - This is not a completed run. The a9 "stand-in" that completed is not on disk any more (a9 benches deleted), so it cannot be checked.
   - Condition: a converged run, or an explicit ruling that accepts the bound, before publishing.
3. **LOW: the ff / 22 C / 3.35 V termination edge.** rt has only code 3 in window (97.3 ohm; code 2 above 110, code 4 below 90). rh has codes 3 and 4.
   - This is inherent to the step size. Codes run about 10 % per LSB at low codes, and the +-10 % window is 20 %, so it is always at least one code.
   - Code 3 has 3 codes of margin to the range end, and the window 2..13 still holds 1 code below it. PASS on the letter.
   - Not covered: low metal (no netres variant exists) and temperatures below 22 C. Both move toward code 2, which is still in the window. Acceptable.
4. **LOW: the off-leak json does not record the model sha** (`offleak.py` stores only the path). The values use 10 nA resolution (rounded to 1e-5 mA), which is adequate for the 1 uA limit.
5. **INFO: the a8 findings are closed.**
   - F1, the off-state leak with TERM_VCM at 0 V: < 0.01 uA per pad in all 5 corners, pads equal, 0.5-3.3 V. With the pads 1 V apart: <= 0.16 uA (ff 32 C). The disconnect is in the model as 8 x nfet_03v3 between TERM_VCM and TERM_VCM_BUS__*.
   - F2, CDM vss-: completes with TB2_CDMSMOOTH, MOS <= 0.99 V. The smooth/PULSE cross-check on vss+ gives 6.920 / 6.915 V.
   - F3, termination margin at ss / 32 C / 3.15 V high metal: codes 12 and 13 are in window (107.8 / 102.2); 14 and 15 are also in window.
   - F4, junction check: MOS junctions are now checked against bv (`junc_rev_max`). Worst is 7.1 V at CDM 2 A and 9.5 V at CDM 3 A, against 10 / 10.5 / 11 V. 0 over.
   - F5, the rbverdict check: now accepts >= 2 swapped labels. The negative control is a mismatch (pin matching), the positive is unique (315 = 315 devices).
   - F6 and F7 are unchanged (effective O1 metric stated; thin trim metal is in the model).
6. **INFO: limit movement.** The a10 declarations add the off-leak limit and the disconnect 5.0 V limit. They keep +-10 % with code 2..13 and code 12 at ss.
   - Nothing was loosened against the binding rulings.
   - The CDM decap is as ruled: 1 nF at the site, r_die 1.4 ohm total = 0.7 ohm per rail, ring at the extracted values.

## Limit table (recomputed from the bench json)
| Limit | Value | Result |
|---|---|---|
| Term +-10 %, code in 2..13, 23 corners, rt | worst best-code 4.24 %; ss_32_3.15 codes 11-13 | PASS |
| Term, rh | worst 4.18 %; ss_32_3.15 codes 12-13 | PASS |
| ff_22_3.35 edge | rt code 3 only; rh codes 3-4 | PASS (single code, F3) |
| P-N <= 1.0 ohm | -0.18 .. -0.09 | PASS |
| Off, TERM_VCM 1.65 V (term-off) | >= 1.27e10 ohm | PASS |
| Off leak, TERM_VCM 0 V / 1.65 V, pads equal | < 0.01 uA all corners | PASS |
| Off leak, pads 1 V apart | <= 0.16 uA | PASS |
| **TERM_VCM common-mode path at 21 mA (my run)** | **0.60-1.00 V across the disconnect; pads 0.07 V at ss** | **FAIL (F1, no declared limit)** |
| CDM 2 A vss+ / pp+ / pp- / vdd- | 6 V devices 6.92 / 7.27 / 7.29 / 0.99 V; n03 <= 0.89 V | PASS |
| CDM 2 A vss- (smooth) | <= 0.99 V, complete | PASS |
| CDM 2 A vdd+ | 3.91 V at the 2.251 ns stop, incomplete | BOUNDED, not run to completion (F2) |
| HBM 1 kV, 6 cases | 6 V <= 4.36 V; n03 <= 0.78 V | PASS |
| HBM 2 kV (report) | 5.73 V | PASS |
| CDM 1 A / 3 A (report) | 5.04 / 9.61 V (40 over at 3 A) | PASS / MISS (info) |
| Junctions < bv | 7.1 V (2 A) | PASS |
| Primary diodes 10 / 1 mA/um | 5.0 / 0.043 mA/um (CDM 2 A); HBM 2 kV 3.3 mA/um 18.6 nJ | PASS |
| Pad C <= 3.223 pF, gate C, O1 / O3 | taken from STATUS (ac / gatec / out json present, same model shas) | PASS (not recomputed) |
| Layout: DRC, LVS, rb pos/neg, KLayout 0/0 with NAT rules, LU 15 um 0, rail_site | from `sec/checks/a10` | PASS |
| Rebuild a10 / default = a4 | normalised sha match, schematics identical | PASS |

Files: `cmdrop.py`, `cmdrop.log`, `a10rt-cmdrop.json`, `rb10.log`, `rbdef.log` (rebuild outputs deleted).
