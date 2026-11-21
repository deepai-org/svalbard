# Review a16: pad_txpad (delta review against review-a13; a14/a15 read from STATUS)

**No publication verdict.** The coordinator put txpad publication on hold mid-review: at 100BASE-TX amplitude the leg saturates at about 26 mA with the cascode gate at VDD, and redesign follows. This file is the list of findings, plus the points the redesign must not break.

GDS reviewed: `sec/b/a16/pad_txpad.gds`, sha256 131af8696acc... (recomputed). Other shas, all recomputed:
- em_check.py c7b5ab5e
- netres `sec/r16/res.json` 83c2795b (it names the a16 GDS)
- models a16_rt 5e0a7322, a16_rh 0047a3d7, a16_c bdd207d5 (byte-identical to `b/a16/pad_txpad.ext.spice`)
- every a16 bench json `model_sha256` matches its model

Work done here: rebuilds, netres jobs, LVS control, off-leak and ESD reruns. Logs are `q.log`, `esd.log` and `esd_s.log`. Intermediate GDS, rebuild and bench directories were deleted.

## Findings

1. **MEDIUM (EM screen coverage): the PAD_P / PAD_N pad-side path to the resistor heads is not in em_check, and it misses B100.**
   - em_check screens TU_*, TERM_VCM_BUS and TERM_VCM only. It skips the pad net from bond to resistor heads, although that path carries the whole termination current.
   - netres on PAD_P / PAD_N (`lo/res.json`, path_fraction 0.02, typ + high) puts the peak at 0.0769 /um on a 13 um Metal2 trunk (x 31.5, y 125; mirror x 242.5).

     | Basis | Current | Density | Ratio | Verdict |
     |---|---|---|---|---|
     | A | 10.5 mA | | 0.39 | pass |
     | B | 15.75 mA | | 0.58 | pass |
     | C | 21 mA | | 0.77 | info |
     | A100 | 20 mA | | 0.74 | pass |
     | B100 | 30 mA | 2.31 mA/um | **1.10** | over the 1.0 limit |

   - So "B100 4 over" is incomplete: the pad trunk is over as well.
   - Not established: the per-unit pad-side (head A) straps. A unit carries up to I/8 at code 0, the case that drove review-a13 F1 on head B. My run to locate them gave no usable output and was stopped at the hold.
   - Redesign: add PAD_x bond->res to em_check, with per-unit current at code 0.
2. **INFO (EM screen correctness): verified.**
   - Codes 0..15, worse of typ / high, path_fraction 0.02 on TU_* / TERM_VCM*.
   - The basis numbers reproduce: A 0.44, B 0.66, C 0.88, A100 0.84, B100 1.26 (4 over: TU_x_B 1.24 / 1.26, TU_x_T1 1.02 / 1.03).
   - Bus superposition check (`bus/`): all P switches as one sink gives 0.0672 /um, the same as the per-group B path (0.0673). The per-group bus currents are not optimistic.
   - Seeded-fault control:
     - The current screen flags a12 (10 over, worst 4.79) and the a13 single-cut seed (3.62, 1 over).
     - Two single-cut seeds on a16 were not flagged, correctly: the TU_P_T1 drop Via2 array (6 cuts reduced to 1) and the TU_P_B Via2 array (10 reduced to 1). Both arrays are now redundant (parallel Metal3 / Metal4 drops), and netres reroutes the current; the worst cut ratio stays at or below 0.45.
     - So the control is valid on known-bad geometry, but no non-redundant a16 cut was found to seed.
3. **INFO (pad C): 3.2141 pF against 3.223 pF (rt, typ, 100 MHz, termination off). PASS by 8.9 fF (0.28 %).**
   - Reproduced from the json (model 5e0a7322). C-only is 3.1244 pF.
   - The margin is inside any reasonable extraction uncertainty. Treat it as no headroom: any added metal on PAD or TU nets (cascode / switch growth in the redesign) will break it.
4. **INFO (termination): PASS.**
   - 23 corners. Worst best-code deviation is rt 5.80 % and rh 4.42 %. P-N is -0.23 to -0.08 ohm.
   - Code margins at ±10 %:
     - ss/32/3.15: codes 11-14 (rt and rh)
     - ss/32/3.35: rt 10-12, rh 10-13
     - ff/22/3.35: codes 2-3 only (rt 106.5 / 94.2 ohm, rh 108.9 / 96.5 ohm)
   - The ff end is one code from the window edge.
   - At ±5 %, rt misses ff/22/3.35. This is as reported by pads, not a limit.
5. **INFO (CM1 / off): PASS.**
   - CM1 is 2.93-2.96 ohm (61.9-62.5 mV at 21.1 mA).
   - Off control is at least 9.98e9 ohm.
   - Off-leak was rerun here (`off-offleak.json`): at most 1e-5 mA over 5 corners.
6. **INFO (ESD on a16_rh, extraction changed by +109 fF on the pad since a13): every rerun case is at or below 8.0 V, with no junction over its bv.**
   - Rerun here:

     | Case | Result |
     |---|---|
     | CDM 2 A pp- | 7.28 V |
     | CDM 2 A vdd- | 0.99 V |
     | CDM 2 A vdd+ | 3.92 V, INCOMPLETE under PULSE (it was complete on a13); smooth-edge rerun stalled at t ≈ 0, so it is bounded only by the PULSE partial |
     | CDM 2 A vss- | COMPLETE with CDMSMOOTH, 0.99 V |
     | HBM 1 kV pp+ | 4.35 V |

   - From the pads queue: CDM vss+ 6.92 V and pp+ 7.27 V.
   - Junctions: at most 7.05 V against bv 10.5-11 V.
   - All match a13 within 0.01 V.
   - Minor: vdd+ is no longer a COMPLETE run.
7. **INFO (layout): PASS.**
   - Magic DRC 0; netgen unique; KLayout main + antenna 0 / 0; rail_site PASS; railconn clean.
   - Latch-up: 0.0 um2 uncovered at 15 um (lu.json names sec/b/a16).
   - Read-back LVS matches, and the MAIN_P/MAIN_BIAS swap control gives a mismatch.
   - **New control:** with only the PAD_P top-edge port label (46/10, y 699.26) moved onto the TERM_ENABLE trunk, read-back LVS gives *mismatch, "Top level cell failed pin matching"* (census equal). The top-edge PAD pins are checked ports.
   - The a16 rebuild normalises to 395dfda2 == sec/b/a16 (schematic identical). The default rebuild is 3a706943 == b/a4 (schematic identical).
8. **View on the PC-65 average basis for 100BASE-TX: the argument is sound in principle but is now overtaken.**
   - EM is an average-current (Black) mechanism. MLT-3 with scrambled idle keeps both legs active, so an average-plus-no-static-drive rule is a legitimate basis, as long as:
     - (a) the average is the real per-leg mean including any DC bias, not a half-amplitude guess;
     - (b) the static-drive rule is enforced in hardware or firmware, with a bounded timeout;
     - (c) the pad trunk (F1) and the per-unit head-A straps are screened as well.
   - Wired TX now reports a 16 mA average and 26-38 mA peak per leg.
     - On the average basis, 16 mA is below A100's 20 mA, so the average case passes with margin. That includes the pad trunk at 16 mA: 0.59.
     - The peaks only matter for static drive. At 38 mA static, the pad trunk would be 1.40, TU_x_B 1.60 and the bus 1.22.
     - So the no-static-drive rule becomes mandatory, not optional.

## The redesign must not break

- Pad C ≤ 3.223 pF. Only 9 fF is left; larger cascode / switch devices on the PAD node will likely exceed it, so budget it first.
- CDM 2 A pp± (7.27-7.28 V against 8.0 V). Larger 6 V devices on the pad change the CDM current split, so rerun all six cases.
- Termination code window: ff/22/3.35 has only codes 2-3, and ss/32/3.15 codes 11-14.
- The EM screen with the basis set to the real 100BASE-TX numbers, extended to PAD bond->res (F1) and to head A per unit.
- PAD_P / PAD_N top-edge ports and the LVS label-move control.
- Default path == a4 (3a706943).

## Limit table (a16)

| Limit | a16 | Result |
|---|---|---|
| EM A / B / C | 0.44 / 0.66 / 0.88 (TU / bus / pin); PAD trunk 0.39 / 0.58 / 0.77 | PASS |
| EM A100 (≤ 0.86) | 0.84 (TU_x_B); PAD trunk 0.74 | PASS |
| EM B100 (≤ 1.0) | TU_x_B 1.26, T1 1.03, **PAD trunk 1.10** (not in em_check) | MISS |
| Termination ±10 %, 23 corners | 5.80 / 4.42 %; P-N -0.23 to -0.08 ohm | PASS |
| Pad C ≤ 3.223 pF | 3.2141 (c 3.1244) | PASS, 8.9 fF |
| CM1 ≤ 5 ohm | 2.96 | PASS |
| Off / off-leak | ≥ 9.98e9 ohm / ≤ 1e-5 mA | PASS |
| CDM 2 A, six cases | ≤ 7.28 V; vdd+ partial at 3.92 V | PASS |
| HBM 1 kV pp+ | 4.35 V | PASS |
| DRC / KLayout / LVS + 2 controls / latch-up / rail_site | 0 / 0+0 / match + mismatch ×2 / 0.0 um2 / PASS | PASS |
| Rebuild a16 / default == a4 | 395dfda2 == / 3a706943 == | PASS |
