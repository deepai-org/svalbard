# Bond geometry re-audit (pre-mortem item 14, proposed PKG-09)

2026-11-14, pads owner sub-task. Geometry only. Nothing in the project tree was changed.
Scripts: `scratch/pads-core/bond/bond_audit.py` (74 bonds, writes `bond-audit.json`), `sites.py` (free sites, `sites.json`),
`board_parse.py`, `maskscan.py`, `ring_scan.py` (text-only board parsing, run with `python3 -I`).
Tags: **[BOARD]** = parsed from the KiCad file at HEAD; **[GDS]** = measured on the Pad layer (37/0) with KLayout;
**[REPORT]** = read from an earlier report, not re-measured; **[CALC]** = computed here; **[ASSUMED]**.

## 1. Result

- **No violation of the published rules for the 74 bonds of the current map.** No crossing, max angle 38.7 deg (limit 45),
  max length 2.991 mm (limit < 3 mm), min length 2.197 mm (limit 1 mm). Finger-centre landing, planar. [CALC]
- **The numbers are the same as on 2026-10-18** (max 2.991 mm, 38.7 deg): largest difference 0.0003 mm / 0.013 deg. Reason:
  every custom pad family, the mirrored wired pads, the stacked `pad_hspad` (staged b2) and the TLP site keep their 60 x 60 um
  bond openings exactly on the provider template sites [GDS], and the board file did not change (same commit).
  What changed since October is which signal sits on which bond (27 bonds renamed or newly named, section 5), not the geometry.
- **Margin is thin where it was thin before:** 9 um of length on the four pairs next to the corners (bonds 18/37/55/74 at
  2.991 mm, finger-centre landing). With the landing moved to the near end of the finger the longest wire is 2.665 mm, but the
  largest angle rises to 44.0 deg (bonds 1/17/38/54), 1.0 deg of margin. One landing rule cannot give comfortable margin on both.
- **Die placement tolerance is not covered by the margin.** A die shifted by 0.1 mm breaks the 3 mm rule on bonds
  18/19/36/37/55/56/73/74 (max 3.131 mm, centre landing), or the 45 deg rule on bonds 1/17/38/54 (47.3 deg, near-end landing). [CALC]
- **Real (3-D) wire length is over 3 mm on the longest bonds for centre landing** if the rule is meant for wire length
  and not for the plan view: 3.03 / 3.05 / 3.07 / 3.10 mm for a 0.2 / 0.3 / 0.4 / 0.5 mm die. Near-end landing: 2.71 to 2.79 mm.
  Die thickness and loop shape are not published; see section 4.
- **The two "in-ring" extra sites were never placed in any GDS** and have no board finger; see `SITES.md`.

## 2. Which board applies

| Item | Value | Tag |
|---|---|---|
| Repository | `github.com/wafer-space/chip-on-board-wire-bonded-pcbs`, clone in `scratch/pads-core/bond/dl/repo` (shallow, main only) | |
| HEAD of the clone | `5cb466897372ac6c9df03142287858c1c8b1c9a7`, 2026-10-10, "fix clearance violation" | [BOARD] |
| Remote main today | same commit (`git ls-remote`, 2026-11-14). Nothing newer on main | [BOARD] |
| Commit used on 2026-10-18 | `5cb4668` (`packaging-audit.json`, board `run-2/1x1-cob/1x1-mezzanine.kicad_pcb`) | [REPORT] |
| Change since then | none: HEAD is that commit; run-2 board sha256 `8075f2df...` equals the one recorded in October | [BOARD] |
| Run-1 board cited by `spec/package-channel.json` (`4f05ed1`) | sha256 `b0de95da...` equals the run-1 file at HEAD: unchanged | [BOARD] |
| Runs in the repository | `run-1/` and `run-2/` only. No run-3 directory, no release tag ("unreleased", renders generated 2026-10-09) | [BOARD] |
| Other remote branches | `checking-14`, `demo-boards`, `larger-rails-on-panels`, `p5xp5`, `nextpcb-drc`, others. Not fetched, content unknown | |

Run-1 against run-2 (both "1x1 mezzanine", 14 x 16 mm, 70-contact connector, footprint `waferspace_default_padring_v0.2`): [BOARD]

- 74 fingers: same positions (to 1 nm; run-2 stores 4.699999 for 4.7 on 8 fingers), same size 1.0 x 0.25 mm, same nets.
  N/S rows at +-4.7 mm, E/W rows at +-4.3 mm from the die centre, pitch 0.4 mm.
- Die paddle (pad 75): 4.0 x 5.2 mm, GND, in both. The die is 3.932 x 5.122 mm, so the paddle shows 34 / 39 um beside the die.
- Finger-to-connector-contact map: identical in both runs.
- Solder-mask opening of the footprint: one rectangle, 9.4 x 10.23 mm, in both. Everything inside is bare copper or bare board.
- **Difference:** the footprint is rotated 180 deg on the run-2 board, and the copper inside the finger ring differs.
  Run-1: GND copper reaches only 0.78 mm from the die edge (to 2.74 mm from centre on E/W, 3.31 to 3.38 on N/S), with signal
  vias and tracks between it and the fingers. Run-2: GND copper reaches to 3.65 mm from centre on E/W and 4.04 mm on N/S
  (0.15 mm short of the fingers), no vias inside the finger ring. This matters only for ground down-bonds (`SITES.md`).
- Which board the next shuttle uses is not stated anywhere in the repository. The run-1 README says pinouts, connector and
  footprint "are specific to this run and are expected to change in future runs". The audit uses run-2, the newest published.
  For the 74 standard bonds the answer is the same on run-1.

Wirebonding rules at HEAD, verbatim (`run-1/wirebonding/README.md`; run-2 has no rules text of its own): [BOARD]

> * **No wires may cross.**
> * **Wire angle must be not greater than 45°.**
> * **Maximum wire length must be less than 3 mm** — though a wire that long would already add a
>   significant amount of inductance, so keep them as short as practical.
> * **Minimum wire length is 1 mm from the die, or 2× the die thickness** (whichever is greater).
> * **No solder mask** is allowed in the area to be bonded.

Not published: die thickness, die-attach material, wire material and diameter, loop height, whether length means plan view
or wire length, where on the finger the wire lands, min bond-pad pitch, down-bonds, double bonds, die placement tolerance.

## 3. Pad centres used

- Site order and provider cells: `spec/contract.json` `provider_site_inventory`; signals: `bond_map_current` (west, east, north)
  and `candidate_signal_sites` only for the south/north host sites that `bond_map_current` declares unchanged.
- Bond-opening centres: `analog/pads/generated/provider-sites.json`, checked against three measurements: [GDS]
  - each published custom cell's Pad-layer openings, transformed with the `kl_assemble.py` transform of its v6 site
    (west M45, east R90, mirrored pads M135 at site + 286 um): 24 openings (26 checks, WIRE_RX in both hspad
    variants), all equal to a provider-site opening to 1 nm.
    Families: `rf-pair` (RF_RX, BB_I, BB_Q, WCLK_IN, WTX_EXT), `rf-tx`, `reference` (REF, AUX_CLK), `wired-receive-usb`,
    `wired-transmit` (mirrored), `wired-receive-hs` published and the staged stacked `scratch/pads-core/hspad/b2/pad_hspad.gds`
    (mirrored), `single-leg` (WMON), `tlp-site`. Every cell has its openings at x 7.5 to 67.5 (and 218.5 to 278.5), y 2 to 62 um;
  - a mini-assembly of the retained provider ring plus the published cells at the v6 sites (`rails2.py`): 74 openings, all
    60 x 60 um, all on a site, largest centre offset from the table 0.5 um;
  - the last assembled chip GDS, `scratch/chip-assembly-v5/run2/pt_chip_top.gds` (2026-11-11): 74 openings, same result.
- There is no assembled v6 GDS: `scratch/chip-assembly-v6/` holds a floorplan only (`floorplan-v6.json`).
- Mirrored pads: WIRE_RX_P bonds at `bidir[15]`, WIRE_RX_N at `bidir[14]`, WIRE_TX_P at `bidir[21]`, WIRE_TX_N at `bidir[20]`
  (`inventory.py` `MIRRORED_PADS`). The openings stay on the sites; only P and N swap.
- Die frame: die centred on the paddle, bond 1 = `clk_pad` (south-west), counter-clockwise, finger n takes bond n. [ASSUMED,
  checked by nets: the 10 ground sites meet GND fingers and the 8 supply sites meet VDD_IO / VDD_CORE / PWR_AUX fingers, 0 mismatches.]

## 4. Method and limits

- Length = straight distance in plan from the bond-opening centre to the landing point. Angle = angle between that line and
  the normal of the die edge the pad sits on. Crossing = proper intersection of two plan segments, all 2701 pairs.
- Two landing models, because the provider does not say where on the 1.0 x 0.25 mm finger the wire lands:
  **C** = finger centre (the 2026-10-18 "centre projection"); **N** = nearest point of the finger, 0.1 mm inside its edges
  (the October "proposed landing plan").
- Limits as published at HEAD: < 3 mm, <= 45 deg, >= max(1 mm, 2 x die thickness), no crossing.
- 3-D estimate [ASSUMED]: loop apex 0.15 mm above the die surface at 25 % of the span, board surface one die thickness below the
  die surface (die attach ignored). It adds 0.04 to 0.11 mm to the longest wire for 0.2 to 0.5 mm of die.
- The min-length rule holds for any die up to 1.10 mm thick (model C) or 0.90 mm (model N).
- Not modelled: finger plating keep-outs, capillary clearance to neighbouring wires (smallest plan spacing between two wires
  is 0.147 mm C, 0.138 mm N, bonds 16/17), loop sag.

## 5. Per-side worst cases

| Side | Model | Longest (bond, signal) | Margin to 3 mm | Largest angle (bond) | Margin to 45 deg | Shortest |
|---|---|---|---|---|---|---|
| South | C | 2.815 mm (17 HOST_MISO; 1 D2H_D[0] same) | 0.185 | 38.7 (17, 1) | 6.3 | 2.197 (9 GND) |
| South | N | 2.498 | 0.502 | 44.0 (17, 1) | 1.0 | 1.797 |
| East | C | 2.991 mm (18 VDD_IO_0; 37 VDD_IO_1 same) | 0.009 | 36.9 (18, 37) | 8.1 | 2.394 (27, 28) |
| East | N | 2.665 | 0.335 | 41.6 | 3.4 | 1.993 |
| North | C | 2.815 mm (38 H2D_D[0]; 54 ATB1 same) | 0.185 | 38.7 (38, 54) | 6.3 | 2.197 (46 GND) |
| North | N | 2.498 | 0.502 | 44.0 | 1.0 | 1.797 |
| West | C | 2.991 mm (55 RF_TX_N; 74 VDD_IO_3 same) | 0.009 | 36.9 (55, 74) | 8.1 | 2.394 (64, 65) |
| West | N | 2.665 | 0.335 | 41.6 | 3.4 | 1.993 |

Violations: none in either model at nominal die position. Crossings: none.

Comparison with 2026-10-18 [REPORT for the old values]: centre model then 2.197 to 2.991 mm, max 38.70 deg; now the same.
Landing plan then 1.797 to 2.665 mm, max 43.99 deg; model N now the same. Site order identical. Signals renamed on 27 bonds:
20/21 (WIRE_RX P/N swapped), 22/23 (WCLK_IN, now free), 24/25 (USB), 28/29 (WIRE_TX swapped), 30 to 33 (WTX_EXT, WMON, TLP),
50 to 54 (CLK_OBS, DBG_OBS0/1, ATB0/1), 55/56 (RF_TX, was REF_IN), 59/60 (BB_Q), 61/62 (AUX_CLK, was RF_TX), 65/66 (REF_IN),
67/68 (BB_I). `candidate_signal_sites` in `contract.json` is still the old map and still feeds `pads/design.py` and
`check_contract.py`; this audit does not use it for those sites.

Negative control [CALC]: bond 1 pad moved 0.4 mm along the edge: flagged (model C: length 3.081 mm and crossings with bonds 2
and 3; model N: angle 49.9 deg and the same crossings). Bond 30 pad moved 0.3 mm: flagged (crossing 29/30).

## 6. What could not be determined

- Board and rules for the next shuttle (run 3). Only run-1 and run-2 files exist; nothing says which is used.
- Die thickness, attach, loop, landing position, placement tolerance: the two tight margins (9 um, 1.0 deg) depend on them.
- Whether the assembler accepts a bond diagram that differs from the default (unbonded pads, extra pads, down-bonds).
- The clone is shallow, so the file history before `5cb4668` was not inspected; the October audit used the same commit.

## 7. All 74 bonds

L and angle in mm / deg. C = finger-centre landing, N = near-end landing. Contact = mezzanine connector contact. [CALC from BOARD + GDS]

| Bond | Side | Site | Signal | Finger net | Contact | L C | Ang C | L N | Ang N |
|---|---|---|---|---|---|---|---|---|---|
| 1 | S | clk_pad | D2H_D[0] | /pad_0 | 8 | 2.815 | 38.7 | 2.498 | 44.0 |
| 2 | S | rst_n_pad | RESET_N | /pad_1 | 7 | 2.683 | 35.0 | 2.350 | 40.1 |
| 3 | S | bidir[0] | D2H_D[1] | /pad_2 | 6 | 2.563 | 31.0 | 2.215 | 35.8 |
| 4 | S | bidir[1] | D2H_D[2] | /pad_3 | 5 | 2.457 | 26.6 | 2.094 | 30.9 |
| 5 | S | bidir[2] | D2H_D[3] | /pad_4 | 4 | 2.366 | 21.8 | 1.990 | 25.4 |
| 6 | S | bidir[3] | D2H_D[4] | /pad_5 | 3 | 2.294 | 16.7 | 1.906 | 19.4 |
| 7 | S | bidir[4] | D2H_D[5] | /pad_6 | 2 | 2.240 | 11.3 | 1.844 | 13.0 |
| 8 | S | bidir[5] | D2H_CLK | /pad_7 | 1 | 2.208 | 5.7 | 1.808 | 6.2 |
| 9 | S | dvss_pads[0] | - | GND | GND plane | 2.197 | 0.0 | 1.797 | 0.0 |
| 10 | S | bidir[6] | D2H_D[6] | /pad_9 | 70 | 2.208 | 5.7 | 1.808 | 6.2 |
| 11 | S | bidir[7] | D2H_D[7] | /pad_10 | 69 | 2.241 | 11.3 | 1.844 | 13.0 |
| 12 | S | bidir[8] | D2H_D[8] | /pad_11 | 68 | 2.294 | 16.7 | 1.906 | 19.5 |
| 13 | S | bidir[9] | D2H_D[9] | /pad_12 | 67 | 2.367 | 21.8 | 1.990 | 25.5 |
| 14 | S | bidir[10] | HOST_CS_N | /pad_13 | 66 | 2.457 | 26.6 | 2.094 | 30.9 |
| 15 | S | bidir[11] | HOST_SCLK | /pad_14 | 65 | 2.563 | 31.0 | 2.215 | 35.8 |
| 16 | S | bidir[12] | HOST_MOSI | /pad_15 | 64 | 2.683 | 35.0 | 2.351 | 40.1 |
| 17 | S | bidir[13] | HOST_MISO | /pad_16 | 63 | 2.815 | 38.7 | 2.498 | 44.0 |
| 18 | E | dvdd_pads[0] | - | VDD_IO_0 | 62 | 2.991 | 36.9 | 2.665 | 41.6 |
| 19 | E | dvss_pads[1] | - | GND | GND plane | 2.881 | 33.9 | 2.543 | 38.4 |
| 20 | E | bidir[14] | WIRE_RX_N | /pad_19 | 60 | 2.780 | 30.7 | 2.430 | 35.0 |
| 21 | E | bidir[15] | WIRE_RX_P | /pad_20 | 59 | 2.689 | 27.2 | 2.327 | 31.1 |
| 22 | E | bidir[16] | WCLK_IN_P | /pad_21 | 58 | 2.608 | 23.5 | 2.236 | 27.0 |
| 23 | E | bidir[17] | WCLK_IN_N | /pad_22 | 57 | 2.539 | 19.6 | 2.156 | 22.5 |
| 24 | E | bidir[18] | USB_DN | /pad_23 | 56 | 2.482 | 15.5 | 2.091 | 17.7 |
| 25 | E | bidir[19] | USB_DP | /pad_24 | 55 | 2.438 | 11.2 | 2.042 | 12.7 |
| 26 | E | dvdd_pads[1] | - | PWR_AUX_0 | 54 | 2.409 | 6.8 | 2.009 | 7.4 |
| 27 | E | dvss_pads[2] | - | GND | GND plane | 2.394 | 2.3 | 1.993 | 2.0 |
| 28 | E | bidir[20] | WIRE_TX_N | /pad_27 | 52 | 2.394 | 2.3 | 1.993 | 2.0 |
| 29 | E | bidir[21] | WIRE_TX_P | /pad_28 | 51 | 2.409 | 6.8 | 2.009 | 7.4 |
| 30 | E | bidir[22] | WTX_EXT_P | /pad_29 | 50 | 2.438 | 11.2 | 2.042 | 12.7 |
| 31 | E | bidir[23] | WTX_EXT_N | /pad_30 | 49 | 2.482 | 15.5 | 2.091 | 17.7 |
| 32 | E | bidir[24] | WMON | /pad_31 | 48 | 2.539 | 19.6 | 2.156 | 22.5 |
| 33 | E | bidir[25] | TLP/ESD test site | /pad_32 | 47 | 2.608 | 23.5 | 2.236 | 27.0 |
| 34 | E | vss_pads[0] | - | GND | GND plane | 2.689 | 27.2 | 2.327 | 31.1 |
| 35 | E | vdd_pads[0] | - | VDD_CORE_0 | 46 | 2.780 | 30.7 | 2.430 | 35.0 |
| 36 | E | dvss_pads[3] | - | GND | GND plane | 2.881 | 33.9 | 2.543 | 38.4 |
| 37 | E | dvdd_pads[2] | - | VDD_IO_1 | 44 | 2.991 | 36.9 | 2.665 | 41.6 |
| 38 | N | bidir[26] | H2D_D[0] | /pad_37 | 43 | 2.815 | 38.7 | 2.498 | 44.0 |
| 39 | N | bidir[27] | H2D_D[1] | /pad_38 | 42 | 2.683 | 35.0 | 2.351 | 40.1 |
| 40 | N | bidir[28] | H2D_D[2] | /pad_39 | 41 | 2.563 | 31.0 | 2.215 | 35.8 |
| 41 | N | bidir[29] | H2D_D[3] | /pad_40 | 40 | 2.457 | 26.6 | 2.094 | 30.9 |
| 42 | N | bidir[30] | H2D_D[4] | /pad_41 | 39 | 2.367 | 21.8 | 1.990 | 25.5 |
| 43 | N | bidir[31] | H2D_D[5] | /pad_42 | 38 | 2.294 | 16.7 | 1.906 | 19.5 |
| 44 | N | bidir[32] | H2D_D[6] | /pad_43 | 37 | 2.241 | 11.3 | 1.844 | 13.0 |
| 45 | N | bidir[33] | H2D_D[7] | /pad_44 | 36 | 2.208 | 5.7 | 1.808 | 6.2 |
| 46 | N | dvss_pads[4] | - | GND | GND plane | 2.197 | 0.0 | 1.797 | 0.0 |
| 47 | N | bidir[34] | H2D_CLK | /pad_46 | 35 | 2.208 | 5.7 | 1.808 | 6.2 |
| 48 | N | bidir[35] | H2D_D[8] | /pad_47 | 34 | 2.240 | 11.3 | 1.844 | 13.0 |
| 49 | N | bidir[36] | H2D_D[9] | /pad_48 | 33 | 2.294 | 16.7 | 1.906 | 19.4 |
| 50 | N | bidir[37] | CLK_OBS | /pad_49 | 32 | 2.366 | 21.8 | 1.990 | 25.4 |
| 51 | N | bidir[38] | DBG_OBS0 | /pad_50 | 31 | 2.457 | 26.6 | 2.094 | 30.9 |
| 52 | N | bidir[39] | DBG_OBS1 | /pad_51 | 30 | 2.563 | 31.0 | 2.215 | 35.8 |
| 53 | N | analog[0] | ATB0 | /pad_52 | 29 | 2.683 | 35.0 | 2.350 | 40.1 |
| 54 | N | analog[1] | ATB1 | /pad_53 | 28 | 2.815 | 38.7 | 2.498 | 44.0 |
| 55 | W | inputs[0] | RF_TX_N | /pad_54 | 27 | 2.991 | 36.9 | 2.665 | 41.6 |
| 56 | W | inputs[1] | RF_TX_P | /pad_55 | 26 | 2.881 | 33.9 | 2.543 | 38.4 |
| 57 | W | dvss_pads[5] | - | GND | GND plane | 2.780 | 30.7 | 2.430 | 35.0 |
| 58 | W | dvdd_pads[3] | - | VDD_IO_2 | 24 | 2.689 | 27.2 | 2.327 | 31.1 |
| 59 | W | inputs[2] | BB_Q_N | /pad_58 | 23 | 2.608 | 23.5 | 2.236 | 27.0 |
| 60 | W | inputs[3] | BB_Q_P | /pad_59 | 22 | 2.539 | 19.6 | 2.156 | 22.5 |
| 61 | W | inputs[4] | AUX_CLK_N | /pad_60 | 21 | 2.482 | 15.5 | 2.091 | 17.7 |
| 62 | W | inputs[5] | AUX_CLK_P | /pad_61 | 20 | 2.438 | 11.2 | 2.042 | 12.7 |
| 63 | W | dvss_pads[6] | - | GND | GND plane | 2.409 | 6.8 | 2.009 | 7.4 |
| 64 | W | dvdd_pads[4] | - | PWR_AUX_1 | 19 | 2.394 | 2.3 | 1.993 | 2.0 |
| 65 | W | inputs[6] | REF_IN_N | /pad_64 | 17 | 2.394 | 2.3 | 1.993 | 2.0 |
| 66 | W | inputs[7] | REF_IN | /pad_65 | 16 | 2.409 | 6.8 | 2.009 | 7.4 |
| 67 | W | inputs[8] | BB_I_N | /pad_66 | 15 | 2.438 | 11.2 | 2.042 | 12.7 |
| 68 | W | inputs[9] | BB_I_P | /pad_67 | 14 | 2.482 | 15.5 | 2.091 | 17.7 |
| 69 | W | inputs[10] | RF_RX_N | /pad_68 | 13 | 2.539 | 19.6 | 2.156 | 22.5 |
| 70 | W | inputs[11] | RF_RX_P | /pad_69 | 12 | 2.608 | 23.5 | 2.236 | 27.0 |
| 71 | W | vss_pads[1] | - | GND | GND plane | 2.689 | 27.2 | 2.327 | 31.1 |
| 72 | W | vdd_pads[1] | - | VDD_CORE_1 | 11 | 2.780 | 30.7 | 2.430 | 35.0 |
| 73 | W | dvss_pads[7] | - | GND | GND plane | 2.881 | 33.9 | 2.543 | 38.4 |
| 74 | W | dvdd_pads[5] | - | VDD_IO_3 | 9 | 2.991 | 36.9 | 2.665 | 41.6 |
