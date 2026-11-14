# Die-fit ledger: independent review (2026-11-14)

Read-only review of `ledger.py` / `ledger.csv` / `ledger.md` (conn commit 4790054). No simulation, no layout tool.
Paths are relative to the repo root; `$P` = `projects/programmable_transceiver_platform`; IC = `scratch/reviews/interface-changes.md`.
Corrections are mm2 added to (+) or removed from (-) the ledger totals A / B / C.

## Findings

| ID | Sev | What is wrong | Evidence | A | B | C |
|---|---|---|---|---:|---:|---:|
| R1 | HIGH | `pt_lo_vreg` 0.12 is not defensible. The LO owner's regulator schematic of today has pass devices 120 x 100 um (L 1.8) + 240 x 100 um (L 2.7), 62 MOS-cap units of 40 x 40 um, 90 poly resistors of 100 um. Bare devices are about 0.24 mm2 (pass 0.12, caps 0.10, R 0.015); at the `pt_pll_vreg2` utilisation (0.63) that is 0.38. Proposed 0.30 (range 0.25-0.38). It still fails 59 dB at 78.125 MHz without an external capacitor, which would also need a pad site. | `scratch/lo-ap4/vreg2/reg.py:9-15,89-90`; `scratch/lo-ap4/vreg2/table.log` (FAIL lines); `scratch/area-pass-4/util.json` (pll_vreg2 dev2 109k / outline 173k); `$P/spec/power-delivery.md:343-362` | +0.180 | +0.180 | +0.180 |
| R2 | HIGH (C) | ADC target 0.33 each is carried in C although the owner missed it by 0.12 and names only two levers left: -0.03 (two attempts failed) and -0.07 (generator rewrite, full requalification). Best reachable is 0.35 each; with only the first lever 0.42. | IC:1376 (AP4-4a, end of row); `scratch/converters-ap4/NOTES.md:70-74,81` | 0 | 0 | +0.040 (floor; +0.180 likely) |
| R3 | MED | RF RX "published" figures are not what is published. `pt_lna` 24,763 exists nowhere today: HEAD is 78,352 (309.3 x 253.3), the working-tree `generated/` is 42,921 and is declared not committable. `pt_rxmix_i/q` HEAD is 76,238 each (35,442 is uncommitted, evidence stale). `pt_bb_tap` HEAD is 9,978 (19,511 is uncommitted), three instances. Marked conf H. | `git show HEAD:$P/analog/rf_rx/generated/{lna,rxmix_i,bb_tap}-layout.json` vs working tree; `scratch/rf-lna-p/NOTES.md:118-120,128`; util.json is dated 13 Nov 08:43, lna.gds 18:47 | +0.107 (+0.018 if working-tree `generated/` counts as published) | 0 | 0 |
| R4 | MED | `h2d_gearbox_rsv` is booked for nothing. The H2D capture flops are in the macro top rows; the reserve is "an empty reserve, nothing is needed there". The W7-GEAR label is wrong: W7-GEAR is the wired RX 20->40 gear, which moved into the macro. | IC:580; `scratch/reviews/mode-walk.md:484`; IC:1043 | -0.093 | -0.031 | -0.031 |
| R5 | MED | Double count in B and C: staged `pt_lo_mmd_qdum` (19,124) and one `pt_lo_obs` (9,022) sit in slot A inside the QVCO outline, which is booked whole (532,476). The ledger note says "fits QVCO slot A" but still adds them. The second `lo_obs` (slot B, route not accepted yet) is left booked. | `scratch/lo-ap4/NOTES.md:54-55`; IC:1427 (AP4-5b) | 0 | -0.028 | -0.028 |
| R6 | MED | Double count: `tx8_rsv` includes the two CML pre-drivers, which replace the four steering buffers `steer_0..3` (4 x 8,677), also booked. In C, `steer_4/5` (inputs tied to VSS, X5) are still booked. | `$P/analog/wired_tx/INTEGRATION.md:19-20`; IC:1215 (AP4-2); `$P/integration/top/decisions.md` D-TMDS | -0.035 | -0.035 | -0.052 |
| R7 | MED (C) | `pt_pll_ring` C = 0.127 is not an assigned target. The assigned 0.115 is declared unreachable; 0.127 is a hypothetical core ECO, not started; the owner's row to assembly says "Keep 0.167". | IC:1344 (AP4-1-RING); `$P/analog/wired_rx/README.md:1342-1345` | 0 | 0 | +0.040 |
| R8 | MED | A books `r8arch_capture_b` on the r6 master (0.956). R8-ARCH is defined as a second instance of the r7 capture; no floorplan or decision ever booked r6 for it (reserve of record 0.43 total, "Confirmed"). This is 0.667 of the -2.9 headline. It is a definition choice (stated in die-fit.md), not an arithmetic error: report A both ways. | IC:1054 (R8-ARCH); `scratch/reviews/area-pass-4.md:57-64` | -0.667 (optional) | 0 | 0 |
| R9 | LOW | `pt_wrx_cap` target 290,000 is below the staged r7c (293,813, grown by the timing fix); no lever exists for the difference. Two instances (A and B capture). | `$P/analog/wired_rx/README.md:1472-1474`; `m45free_staged.json` | 0 | 0 | +0.008 |
| R10 | LOW | Three "never built, estimate" rows have staged layouts (DRC 0, LVS unique): `pt_refvcm` 7,443 (ledger 3,000), `pt_txpad_bias` 12,524 (3,000), `pt_bias_tap2` 2,218 per cell, two cells for the three D-BIAS outputs (ledger `pt_bias_ext` 9,000). Confidence becomes M. | `scratch/pads-core/bias/pub/*-layout.json`; `scratch/pads-core/NOTES.md:20-22` | +0.009 | +0.009 | +0.009 |
| R11 | LOW | `supply_clock_monitor` 0.020 in A/B overlaps the macro: `pt_monitor` already exists as RTL (146 flops). What remains outside is only what CP4-11's conditions ask for (a time base in RF modes, an H2D_CLK present detector): about 0.005, in C too (C has 0). | `scratch/digital-timing-close/NOTES.md:445`; `scratch/reviews/consolidation-pass-4.md` section 7.1 (CP4-11) | -0.015 | -0.015 | +0.005 |
| R12 | LOW | Unbooked small items named by owners: LNA tail current source (18 mA), 15 ohm gate R and a common-mode damping network (ledger note says "still to add", no area); phase / external-clock selector in front of `ptrim` and `pt_wiredtx` (D-EXTCLK, a build demand if the fallback is kept); FLL / FUP-FDN driver location (D-CDRCTL: macro or wired-island cells). Allowance 0.010. | `scratch/rf-lna-p/NOTES.md:171-176,187`; `$P/integration/top/decisions.md` D-EXTCLK, D-CDRCTL | +0.010 | +0.010 | +0.010 |

Flags without a correction (the reader should know, the number is not mine to set):

- `pt_detect` C = 0.09: assigned target, but the layout-only repack failed and the owner's row says "Keep 0.173" until a threshold
  redesign that is not started (IC:1345). C carries 0.083 with no layout behind it.
- `pad_single_leg` C = 0.0998 rests on the undrawn 205 um cell (`inventory.py:151` uses `single_leg_b`, no such GDS). AP4-7's assigned
  lever is the provider `asig_5p0` pad; the B cell is the fallback named for BB_Q. 0.047 with no layout behind it.
- Island-local decap, 1.16 nF (50-250 pF per island), is assumed "inside the blocks" (`power-delivery.md:287`). Nobody has shown the
  blocks hold it. If not, it is up to 0.29 mm2 of MOS decap or more Metal4/Metal5 plate that the grid MIM also wants.
- `d2h_gearbox_rsv` (0.0315): the macro launches DDR itself (D-D2H). The strip is only justified as the hand-placed D2H output block /
  pad repeaters (`SESSION-STATE.md` line "Coordinator decision for D2H"). Keep, but rename; it is not W7-GEAR.
- `pt_char_ro33` vs `ring_osc`: not the same cell (ro33 = NAND + 10 inverters + TSPC /4, 54 devices; `ring_osc` 58 devices,
  165-255 MHz), CP4-R4 still unanswered. 0.0095 either way.
- `pt_ptrim` B/C = 0.026 + 0.015 output stage = 0.041; the owner asks assembly to book <= 0.05 (IC:1341). Inside the stated bound.
- `pt_lna_ind` B = 35.7k each is the present coil; the owner's next step is the 57.2k coil (C). B is "as staged", so it stands, but B
  is 0.043 below the plan of record for the tank.

## Net correction per scenario

| | ledger total | correction | corrected total | raw margin (core 12.772) |
|---|---:|---:|---:|---:|
| A (R8 not applied) | 15.688 | +0.163 | 15.851 | -3.079 |
| A (R8 applied: capture B on the r7 reserve) | 15.688 | -0.504 | 15.184 | -2.412 |
| B | 13.226 | +0.090 | 13.316 | -0.544 |
| C (ADC at the 0.35 floor) | 12.351 | +0.181 | 12.532 | +0.240 |
| C (ADC 0.42, detect stays 0.173) | 12.351 | +0.404 | 12.755 | +0.017 |

Sums: A = R1 +0.180, R3 +0.107, R4 -0.093, R6 -0.035, R10 +0.009, R11 -0.015, R12 +0.010.
B = R1 +0.180, R4 -0.031, R5 -0.028, R6 -0.035, R10 +0.009, R11 -0.015, R12 +0.010.
C = R1 +0.180, R2 +0.040, R4 -0.031, R5 -0.028, R6 -0.052, R7 +0.040, R9 +0.008, R10 +0.009, R11 +0.005, R12 +0.010.

The sign of each scenario does not change. C's raw margin roughly halves, and it is about zero once the ADC and detect targets
are read as the owners report them.

## Checked and found correct

Double counting (none found):
- LNA tank coil vs `pt_lna`: the coil is outside the cell (`tank_p/n` are pins, `$P/analog/rf_rx/lna.spice:8`; no inductor in the netlist).
- R8-ARCH items vs the conn: one `pt_slicer`, one `pt_wrx_cap`, one `pt_ptrim` in the conn; the 0.035 blender / PD8 booking already
  includes the ptrim 8 -> 16 channel growth (`scratch/wired_rx/r8arch/decision.md:39,60`).
- `ctle_follower` and `r8arch_ctle_follower_b` vs the staged CTLE: 68.7k + 5k = 73.7k against the owner's "plan on 200 x 370" (74.0k), IC:1346.
- `ptrim_output_stage` vs the staged ptrim: the staged cell is the unmodified circuit (README Resume 9 / PTRIM).
- Iso cells vs the macro: the conn already has CP4-1 applied; 18 cells outside (9 + 7 + 2), `MOVED_ISO` in ledger.py is unused.
- `pad_txpad` column vs `tx_interlock` / `term_buffer` / `tx_steer`: separate cells (pad netlist 576 devices, no interlock or buffer).
- Decap bank: its own core area per `power-delivery.md` 4.2; not inside any booked outline. Spiral keep-out is in `fit.py` (halo 25), not in the ledger.
- tx8 vs `pt_wiredtx`: `wtx_serq8` (767.6 x 458.8) replaces the `wtx_serq4c` core macro (0.158), IC:221, IC:1435.

Numbers against their source (all agree):
- `pad_single_leg`: published cell is 302.19 x 912.91 (util.json 275,877); WMON is bound to it; 302.2 x 486.91 = 147,144.
- Pad intrusion: rf_pair 310.06 x 486.91, refpad 401.22 x 486.91, hspad 478.06 x 685.25 and staged 492.06 x 486.91, wirepad
  254,824 + 98,092, txpad 235,268 + 43,465; AP4-6 targets (columns 300 / 160 um) reproduce 311,134 / 257,572 (IC:1219).
- `pt_cdr` 259.22 x 319.76 = 82,888 (`cdr-layout.json`, committed r13; util.json's 174,376 is the old cell, correctly not used).
- `pt_ptrim` staged 126.4 x 205.2; `pt_ctle` staged 194.2 x 353.9; `pt_wrx_cap` staged 1210.55 x 242.71.
- ADC staged 480.28 x 936.30 = 449,686; DAC staged 668.50 x 200.63 = 134,121 (`converters-ap4/NOTES.md:143`).
- LO staged: lo_mmd 377.92 x 383.76, qdum 97.98 x 195.18, lo_obs 96.4 x 93.59, clk_obs16 127.5 x 414.54, lo_ext 343.1 x 387.66.
- `pt_lna_deg` 25.2k (140 um, 2 turns), `pt_lna_ind` 35.7k staged / 57.2k target (`rf-lna-p/NOTES.md:159-164,189`).
- tx8: 0.352 - 0.158 + 0.028 = 0.222; published `pt_wiredtx` 246,188 (evidence 248,367).
- Island switches: 5 x 36,922 + 2 x 64,081 + 2 x 31,781 + 49,817 = 426,151 (`power-delivery.md` section 2: 0.427).
- Characterization LEF: atb 192.1 x 147.0, ro33 69.64 x 139.26, ro50 70.38 x 132.42, cmldiv 104.76 x 265.76, rffet 430 x 260 (x3).
- Decap bank 0.39 (0.9 nF MOS at 2.33 fF/um2 = 0.386); macro 1716 x 1640; `pt_usb_txdrv` 116.48 x 270.06; core_bias 925.65 x 326.04;
  T-coil reserve 570 x 120; `pt_wordclk` one instance is right (the TX word clock is inside `pt_wiredtx`).

Not checked: the staged GDS bounding boxes were read from `m45free_staged.json` and the owners' notes, not re-measured.
