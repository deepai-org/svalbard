# package-channel regeneration and south-signal facts (pads owner, 2026-11-14)

Python only, no simulation, nothing in the project tree or in `scratch/cob/` was edited, nothing committed.
All files are in `scratch/pads-core/spec/`. Tags: [BOARD] run-1 board file via `scratch/cob/raw.json`, [GDS]
`analog/pads/generated/provider-sites.json`, [FP] `floorplan-v6.json`, [CALC] computed here, [ASSUMED].

## 0. Results in short

- `package-channel.new.json` is ready to copy over `spec/package-channel.json`. Same schema, all 13 top-level keys kept,
  one key added (`bond_map_notes`). 56 pins.
- The north-edge bug is real and proven from coordinates: all 16 north signals were on the mirror bond (n -> 92 - n).
  It changes the per-pin H2D numbers and the H2D group spread (27.0 -> 23.8 ps). No consumer script read a north pin.
- Option L1 changes more than the west pin rows: the `lo` section moves, because REF_IN now sits on two short traces.
  Board I/Q phase offset grows from about -10 deg to -17/-19 deg (unterminated, 0.7-1.0 pF); REF_IN intra-pair skew
  improves from -14.7 to +0.4 ps and BB_Q inherits the -14.7 ps.
- One statement in the brief is wrong: provider sites `inputs[0..11]` run **north to south**, not south to north
  (`inputs[0]` y = 4565.5 um, `inputs[11]` y = 1400.5 um [GDS]). The north-to-south order given in the brief is right.
- South signal to move to east `bidir[17]`: **HOST_CS_N (bond 14)** first, **RESET_N (bond 2)** runner-up. Section 5.

## 1. Final site -> signal list (all 74 bonds in `site_list.md`)

West, north to south (L1 checked against `contract.json` `bond_map_current` and LO-PAD-OPTIONS option b: only REF_IN /
REF_IN_N and BB_Q_P / BB_Q_N change sites, P stays on the higher index):

| Site | Bond | Contact | Signal | In `bond_map_current` today |
|---|---|---|---|---|
| inputs[0] | 55 | 27 | RF_TX_N | RF_TX_N |
| inputs[1] | 56 | 26 | RF_TX_P | RF_TX_P |
| inputs[2] | 59 | 23 | **REF_IN_N** | BB_Q_N |
| inputs[3] | 60 | 22 | **REF_IN** | BB_Q_P |
| inputs[4] | 61 | 21 | AUX_CLK_N | AUX_CLK_N |
| inputs[5] | 62 | 20 | AUX_CLK_P | AUX_CLK_P |
| inputs[6] | 65 | 17 | **BB_Q_N** | REF_IN_N |
| inputs[7] | 66 | 16 | **BB_Q_P** | REF_IN |
| inputs[8] | 67 | 15 | BB_I_N | BB_I_N |
| inputs[9] | 68 | 14 | BB_I_P | BB_I_P |
| inputs[10] | 69 | 13 | RF_RX_N | RF_RX_N |
| inputs[11] | 70 | 12 | RF_RX_P | RF_RX_P |
| two extra openings beside RF_RX | none | none | AGND_RX (note only, no finger) | LNA_SRC_P / LNA_SRC_N |

East, south to north: bidir[14] 20 / c60 WIRE_RX_N; bidir[15] 21 / c59 WIRE_RX_P; **bidir[16] 22 / c58 POR_BYPASS (strap,
`in_c`)**; **bidir[17] 23 / c57 SPARE_E17 (held)**; bidir[18] 24 / c56 USB_DN; bidir[19] 25 / c55 USB_DP; bidir[20] 28 / c52
WIRE_TX_N; bidir[21] 29 / c51 WIRE_TX_P; bidir[22] 30 / c50 WTX_EXT_P; bidir[23] 31 / c49 WTX_EXT_N; bidir[24] 32 / c48 WMON;
bidir[25] 33 / c47 TLP_TEST.

North, east to west (bond order): bidir[26..33] = H2D_D[0..7] on bonds 38..45 (contacts 43..36); dvss_pads[4] bond 46;
bidir[34] H2D_CLK 47 / c35; bidir[35] H2D_D[8] 48 / c34; bidir[36] H2D_D[9] 49 / c33; bidir[37] CLK_OBS 50 / c32;
bidir[38] DBG_OBS0 51 / c31; bidir[39] DBG_OBS1 52 / c30; analog[0] ATB0 53 / c29; analog[1] ATB1 54 / c28.

South: unchanged (bonds 1..17 as in SITES.md section 3).

`contract.json` `bond_map_current` still has the old west rows, WCLK_IN and LNA_SRC: not edited here.

## 2. North-edge bug: proof and reach

Proof (`north_proof.py`, no site-order list used): the 74 bond-opening centres [GDS] are paired by rank along each die edge
with the 74 fingers [BOARD] for each die orientation. Exactly one orientation puts all 10 ground sites on GND fingers and
all 8 supply sites on supply fingers (the others give 12 to 20 mismatches). Under it the old expression
`south + east + north + reversed(west)` is wrong on bonds 38-45 and 47-54 and right everywhere else; with north reversed
it is right on all 74. This equals `bond-audit.json`. `die_xy()` in the generator needed the matching sign change for
north. `channel_model.py` now asserts the order against `site_to_bond.json`.

Why nothing caught it: the only north supply or ground site is bond 46, the centre of the edge, so net-class checks pass
either way.

What it changed:

- `pins`: all 16 north entries (bond pad, board net, contact, trace lengths, via, connector L, spacing, sparams, xtalk).
- `intra_pair_and_group_skew.H2D_group`: max 7.44 -> 6.91 mm, clk 2.88 -> 2.91 mm, spread **27.0 -> 23.8 ps**.
- `xtalk_dB` corner pair: was H2D_D[0] - BB_Q_N, is ATB1 - RF_TX_N (bonds 54 / 55).
- `pulse_2p5G_and_312M.H2D_CLK`: 2.88 -> 2.91 mm of trace, eye 0.884 -> 0.883.
- Not changed: every south pin (D2H, SPI, RESET_N), D2H_group (22.5 ps), `supplies_grounds`, `pdn`, `host_ssn`, `thermal`.

Did anything rely on the wrong numbers?

- No script reads a north pin from the file (section 4).
- `spec/package-channel.md` line 68 and line 105 quote "H2D 27.0 ps" and "22-27 ps group spread": now 23.8 and 22-24.
  The statement that both clocks are on the shortest traces still holds (H2D_CLK 2.91 mm, shortest lane 2.88 mm).
- **Any carrier pinout taken from this file for H2D, CLK_OBS, DBG_OBS0/1 or ATB0/1 has the wrong connector contact**
  (for example H2D_D[0] is on contact 43, not 28; ATB0 on 29, not 42). I found no carrier netlist in the repository.
- `verification/audit_provider_cob.py` line 50 has the same expression, and its output
  `evidence/provider-cob-audit.json` lists the 11 H2D signals on the mirror bonds (H2D_D[0] bond 54 / contact 28,
  H2D_CLK 45 / 36). Only the script itself references that file. Not edited.

## 3. What changed in the file (old 2026-11-10 -> new)

Regression first: `merge.py check` rebuilds the current spec file from the old generator outputs in `scratch/cob/` and
gets an identical file, so the scripted merge is the same as the manual one. `lo.larger_padC` had no generator on disk;
`lo_bigc.py` reproduces the old values exactly with the old geometry, then recomputes.

Per-pin table, all 56 signals: `diff_pins.md`. Rows that changed:

| Signal | Old site / bond / contact | New site / bond / contact | Old F+B mm (ps) | New F+B mm (ps) | Bond mm | Cause |
|---|---|---|---|---|---|---|
| RF_TX_P | inputs[3] / 60 / 22 | inputs[1] / 56 / 26 | 3.12 (18.4) | 5.68 (33.6) | 2.60 -> 3.02 | stale entry fixed |
| RF_TX_N | inputs[2] / 59 / 23 | inputs[0] / 55 / 27 | 3.06 (18.1) | 5.39 (31.9) | 2.69 -> 3.16 | stale entry fixed |
| REF_IN | inputs[7] / 66 / 16 | inputs[3] / 60 / 22 | 3.18 (18.8) | 3.12 (18.4) | 2.44 -> 2.60 | L1 |
| REF_IN_N | inputs[6] / 65 / 17 | inputs[2] / 59 / 23 | 5.66 (33.5) | 3.06 (18.1) | 2.42 -> 2.69 | L1 |
| BB_Q_P | inputs[1] / 56 / 26 | inputs[7] / 66 / 16 | 5.68 (33.6) | 3.18 (18.8) | 3.02 -> 2.44 | stale entry + L1 |
| BB_Q_N | inputs[0] / 55 / 27 | inputs[6] / 65 / 17 | 5.39 (31.9) | 5.66 (33.5) | 3.16 -> 2.42 | stale entry + L1 |
| H2D_D[0] | bidir[26] / 54 / 28 | bidir[26] / 38 / 43 | 6.46 (38.2) | 6.00 (35.5) | 2.79 | north fix |
| H2D_D[1] | bidir[27] / 53 / 29 | bidir[27] / 39 / 42 | 7.40 (43.7) | 6.26 (37.0) | 2.67 | north fix |
| H2D_D[2] | bidir[28] / 52 / 30 | bidir[28] / 40 / 41 | 7.44 (44.0) | 6.91 (40.8) | 2.55 | north fix |
| H2D_D[3] | bidir[29] / 51 / 31 | bidir[29] / 41 / 40 | 6.59 (38.9) | 6.11 (36.1) | 2.45 | north fix |
| H2D_D[4] | bidir[30] / 50 / 32 | bidir[30] / 42 / 39 | 5.83 (34.5) | 5.55 (32.8) | 2.36 | north fix |
| H2D_D[5] | bidir[31] / 49 / 33 | bidir[31] / 43 / 38 | 5.12 (30.3) | 4.94 (29.2) | 2.29 | north fix |
| H2D_D[6] | bidir[32] / 48 / 34 | bidir[32] / 44 / 37 | 4.33 (25.6) | 4.34 (25.6) | 2.24 | north fix |
| H2D_D[7] | bidir[33] / 47 / 35 | bidir[33] / 45 / 36 | 2.91 (17.2) | 2.88 (17.0) | 2.21 | north fix |
| H2D_CLK | bidir[34] / 45 / 36 | bidir[34] / 47 / 35 | 2.88 (17.0) | 2.91 (17.2) | 2.21 | north fix |
| H2D_D[8] | bidir[35] / 44 / 37 | bidir[35] / 48 / 34 | 4.34 (25.6) | 4.33 (25.6) | 2.24 | north fix |
| H2D_D[9] | bidir[36] / 43 / 38 | bidir[36] / 49 / 33 | 4.94 (29.2) | 5.12 (30.3) | 2.29 | north fix |
| CLK_OBS | bidir[37] / 42 / 39 | bidir[37] / 50 / 32 | 5.55 (32.8) | 5.83 (34.5) | 2.36 | north fix |
| DBG_OBS0 | bidir[38] / 41 / 40 | bidir[38] / 51 / 31 | 6.11 (36.1) | 6.59 (38.9) | 2.45 | north fix |
| DBG_OBS1 | bidir[39] / 40 / 41 | bidir[39] / 52 / 30 | 6.91 (40.8) | 7.44 (44.0) | 2.55 | north fix |
| ATB0 | analog[0] / 39 / 42 | analog[0] / 53 / 29 | 6.26 (37.0) | 7.40 (43.7) | 2.67 | north fix |
| ATB1 | analog[1] / 38 / 43 | analog[1] / 54 / 28 | 6.00 (35.5) | 6.46 (38.2) | 2.79 | north fix |

Renamed, geometry unchanged (site, bond, contact, traces stay): WCLK_IN_P -> **POR_BYPASS** (bond 22, c58, cls `strap`);
WCLK_IN_N -> **SPARE_E17** (bond 23, c57, cls `spare`); WCLK_OBS -> **USB_DN** (24, c56, cls `usb`); WDBG_OBS -> **USB_DP**
(25, c55, cls `usb`); ESD_TEST -> **TLP_TEST** (33, c47, cls `test`). Their `sparams` change with the class pad C:
usb 2.35 pF (was 1.5), strap and spare 4.0 pF unterminated (were 1.0 pF with 50 ohm), test 1.5 pF (same).
The 4.0 pF for strap and spare is the provider-cell figure used for the other provider sites [ASSUMED]; the strap is
static, so its RF rows are bookkeeping only.

Unchanged rows (25 signals: south, WIRE_RX_N, WIRE_TX, WTX_EXT, RF_RX, AUX_CLK_P, BB_I_P): identical. WIRE_RX_P, WMON,
AUX_CLK_N and BB_I_N change only in the partner names of `xtalk_dB`.

Skew table (`intra_pair_and_group_skew`):

| Entry | Old | New |
|---|---|---|
| REF_IN | P 3.18 / N 5.66 mm, -14.7 ps | P 3.12 / N 3.06 mm, **+0.4 ps** |
| BB_Q | P 5.68 / N 5.39 mm, +1.7 ps | P 3.18 / N 5.66 mm, **-14.7 ps** |
| RF_TX | P 3.12 / N 3.06 mm, +0.4 ps | P 5.68 / N 5.39 mm, **+1.7 ps** |
| WCLK_IN | -12.4 ps | removed |
| H2D_group | 2.88..7.44 mm, clk 2.88, 27.0 ps | 2.88..6.91 mm, clk 2.91, **23.8 ps** |
| D2H_group, RF_RX, AUX_CLK, WIRE_RX, WIRE_TX, WTX_EXT, BB_I | | unchanged |

Other sections that are signal dependent and were recomputed:

- `placement_sweep.rf_tx_match` (now on bond 56, 5.68 mm): matched loss strip 0.22 -> 0.22 dB, conn+2mm and beyond
  rise, e.g. car30mm 1.50 -> 1.71 dB; unmatched loss strip 0.55 -> 0.75 dB. `rf_rx_match` unchanged.
- `lo` (REF_IN now on bonds 60 / 59): I gain rises 3 to 5 % (1.0 pF, car30mm: 1.91 -> 2.01); **I/Q phase offset
  -10.0 -> -17.0 deg at 1.0 pF and -10.4 -> -18.7 deg at 0.7 pF** (R = 5 k), -6.0 -> -10.9 deg with 50 ohm; I/Q
  amplitude -0.26 -> -0.72 dB. Cause: the I pair is now 3.1 mm on both legs, the Q pair 5.2 / 5.5 mm. BP-2 asks the
  carrier to equalise I and Q delay, so the carrier now has to add about 2.25 mm (13 ps) to the I pair.
- `pulse_2p5G_and_312M`: WCLK_IN_P removed; H2D_CLK as above.
- `board-requirements.md` BP-2 lists "REF_IN P +2.5 mm, WCLK_IN P +2.1": after L1 REF_IN needs none and BB_Q P
  takes the 2.5 mm; WCLK_IN is gone. Not edited.

Kept as before, and still true of the model: adjacent-pin crosstalk only; `bond_mm` is the generator's estimate with
211 um pitch on all four edges (the north and south pitch is 180 um), 0.03 to 0.17 mm longer than BOND-AUDIT.

## 4. Consumers of `package-channel.json`

Scripts that load the file:

| Consumer | Reads | Affected by the new file? |
|---|---|---|
| `scratch/integration/m1-pdn/model.py` | `supplies_grounds` (bond pad, net, f_mm) | No: identical. Its comment "north E->W 38-54" is the correct order. |
| `scratch/integration/m6-powerup/sim/pu_bench.py` | `pdn` L_nH | No: identical. |
| `scratch/pads-core/bond/lo_pad_options.py` | `pins` by **bond pad** (traces, contact), west only | No: per-bond geometry on the west edge is unchanged. |
| `scratch/rfconv-owner/lna/cob.py`, `lna/placement.py` | `pins` RF_RX_P/N | No. |
| `scratch/rfconv-owner/tx/p2.py` (through `cob.py`) | `pins` RF_TX_P/N | **Yes**: it used the bond 60 / 59 geometry (3.1 mm of trace, bond 2.6 / 2.69); the real pins are 5.68 / 5.39 mm, bond 3.02 / 3.16. A rerun changes its result. |
| `scratch/pads-pd21/rl_cob.py` | `pins` WIRE_RX_P (default pin) | No. |

Not a reader of the file but of the same generator: `scratch/cob/placement.py` and `lo_*.py` read `scratch/cob/channel.json`,
which is still the old map. m23 (`scratch/integration/m23-substrate-pulling`) does not read either file.

Project files that quote numbers or names from it (text only, not edited):

- `spec/package-channel.md`: table rows "RF_TX (60/59)", "-> AUX_CLK_N -17.5 dB" (that neighbour is now REF_IN),
  "WCLK_IN / WTX_EXT", the skew line 67 (REF_IN 14.7, WCLK_IN 12.4, RF_TX 0.4), line 68 and 105 (H2D 27.0 ps), the
  RF_TX match row (0.22 / 0.26 / 0.72 / 1.50 / 2.30 dB).
- `spec/board-requirements.md` BP-1 (per-pin chain: ranges still hold), BP-2 (see above), B17 (RF_TX loss vs placement).
- `spec/design-assumptions.md` line 62 (RF_RX path 4.97 / 6.01 mm: unchanged), `spec/power-delivery.md` line 466 (ground
  bond lengths not in the file: still true), `spec/risk-register.md` PKG-04/05, `analog/rf_rx/lna_match.py` comment
  (RF_RX: unchanged), `analog/timing/lo_ext_pad.py` and `analog/wired_tx/*` (cite the model, WIRE_TX unchanged),
  `verification/chip_assembly/inventory.py` line 410 (comment on the RF_TX slot).
- `analog/timing/lo_ext_pad.py` uses its own COB chain constants; with L1 the REF_IN chain is the short one (3.1 mm),
  so a rerun is due when L1 is adopted (PKG-05).

## 5. Task 2: which south signal should move to east `bidir[17]`

### 5.1 Common facts

- Target: `bidir[17]`, bond 23, opening at (3874.0, 1611.5) um [GDS], finger `/pad_22`, **contact 57**. COB: bond 2.60 mm,
  F 1.06 + B 4.15 = 5.21 mm, 30.8 ps, via 0.42 nH, connector 1.15 nH with 1.6 mm to the nearest ground contact [CALC].
- Neighbours: bond 22 POR_BYPASS (static), bond 24 USB_DN; WIRE_RX_P is two sites away (422 um, bond 21). Model coupling
  bond 23 -> USB_DN and -> POR_BYPASS: -41.3 dB at 156 MHz, -23.2 dB at 1.25 GHz. Non-adjacent pairs are not modelled.
- Supply and ground near the site: PWR_AUX_0 (bond 26) 633 um, VDD_IO_0 (bond 18) 1055 um, ground bonds 19 and 27 at
  844 um each. The south edge has one ground bond (9) for 16 signals, so the east site is not worse for return current
  on the die. On the die the ring is one supply net, so any provider cell works there.
- The digital macro is in the north half: outline x 1262..2978, y 3030..4670 [FP]. `pin_order.cfg` puts `reset_n_pad`,
  `por_bypass`, `d2h_*` and `spi_*` on its south edge; the D2H launch cells are hard-placed at macro x 636..846
  (chip x 1898..2108). The south pads are 2.65 mm below that edge. **So the on-die route to `bidir[17]` is not longer
  than today's route**: today 2.65 to 3.25 mm, to `bidir[17]` 2.0 mm straight Manhattan from the macro's south-east
  corner, or about 2.5 to 2.9 mm if the route stays west of the USB pad outline (x < 2468) [CALC on FP; routability
  not checked, pin x positions are not fixed].
- What the route passes instead: the wired-TX and USB pad outlines, the CDR ring (`pll_cdr`, 2182..2975 x 1370..1580)
  and `rxselect`. Today's route passes the ADCs and the D2H corridor.
- Supply benefit of the freed south site: SITES.md section 3, worst D2H drop per 100 mA, ideal bonds / 0.13 ohm per
  bond; today 11.0 / 15.1 mV. For D2H sites the SITES figure assumes that lane's load is gone; in P2 the lane keeps
  switching at the east site, so the real figure is slightly worse than listed.
- The worst supply bond in wired mode is bond 18 (87.5 mA, power-delivery section 6). A supply bond at 13 takes it to
  63.5 mA. Bonds 14 to 17 are on the same side, 180 to 720 um further from the centre; bond 2 is at the far end and
  mainly relieves bond 74. This is an inference from position: the power-delivery model was not rerun.
- Converting a south `bi_24t` site to `dvdd` feeds it through one signal contact with no capacitor footprint on the COB
  (SITES.md), and `contract.json` has `preserve_provider_power_ground_assignments: true`, which P2 changes by definition.

### 5.2 Per signal

On-die lengths are Manhattan lower bounds from the macro south edge to the pad cell [CALC]. "COB now" is F+B trace and
delay at the present contact; moving to contact 57 gives 5.21 mm / 30.8 ps.

| Signal | South site, bond, contact | Function, rate, edge sensitivity | Cell needed at `bidir[17]` | On-die route today -> to E17 (mm) | COB now (mm / ps) -> change at c57 | Group skew if moved | Freed site as supply: D2H drop per 100 mA |
|---|---|---|---|---|---|---|---|
| HOST_CS_N | bidir[10], 14, c66 | SPI select, input, one edge pair per transaction; level qualifier | `in_c` | 2.65 -> 2.0..2.5 | 6.59 / 38.9 -> -8.1 ps | none (SPI <= 5 MHz, 200 ns period) | 6.8 / 10.8 mV |
| RESET_N | rst_n_pad, 2, c7 | async reset, input, static; a glitch resets the chip | `in_c` (as today) | 3.21 -> 2.0..2.5 | 6.83 / 40.4 -> -9.6 ps | none | 6.9 / 11.1 mV |
| HOST_MOSI | bidir[12], 16, c64 | SPI data in, <= 5 Mb/s, sampled on SCLK | `in_c` | 2.90 -> 2.0..2.5 | 6.37 / 37.6 -> -6.8 ps | none | 8.3 / 12.1 mV |
| HOST_SCLK | bidir[11], 15, c65 | SPI clock, input, <= 5 MHz, edge sensitive; also the multi-chip video alignment marker (contract `multi_chip_video`) | `in_c` or `in_s` | 2.72 -> 2.0..2.5 | 6.97 / 41.2 -> -10.4 ps | none at 5 MHz | 7.5 / 11.5 mV |
| HOST_MISO | bidir[13], 17, c63 | SPI data out, <= 5 Mb/s, 3.3 V CMOS driver | `bi_t` / `bi_24t` | 3.08 -> 2.0..2.5 | 6.01 / 35.5 -> -4.7 ps | none | 9.0 / 12.7 mV |
| D2H_D[9] | bidir[9], 13, c67 | D2H DDR lane, 312.5 Mb/s, 3.2 ns UI | `bi_24t` | 3.23 -> 2.5..2.9 | 5.94 / 35.1 -> -4.3 ps | lane to clock +17.7 -> +13.4 ps; COB group spread stays 22.5 ps | 6.5 / 10.6 mV |
| D2H_D[8] | bidir[8], 12, c68 | same | `bi_24t` | similar | 5.27 / 31.1 -> -0.3 ps | +13.8 -> +13.4 ps; 22.5 ps | 5.6 / 9.8 mV |
| D2H_D[7] | bidir[7], 11, c69 | same | `bi_24t` | similar | 4.39 / 25.9 -> +4.9 ps | +8.6 -> +13.4 ps; 22.5 ps | 4.8 / 9.1 mV |
| D2H_D[6] | bidir[6], 10, c70 | same | `bi_24t` | similar | 2.93 / 17.3 -> +13.5 ps | -0.1 -> +13.4 ps; 22.4 ps | 4.0 / 8.4 mV |
| D2H_CLK | bidir[5], 8, c1 | forwarded clock, 156.25 MHz, reference of the group | `bi_24t` | similar | 2.94 / 17.4 -> +13.4 ps | every lane shifts by -13.4 ps against it | 2.6 / 7.2 mV |
| D2H_D[5..1] | bidir[4..0], 7..3, c2..c6 | D2H lanes | `bi_24t` | similar | 4.22..6.73 mm -> +5.9..-9.0 ps | spread 22.5 ps (19.2 ps if D[1] moves) | 3.0..6.5 / 7.6..10.9 mV |
| D2H_D[0] | clk_pad, 1, c8 | D2H lane on the `in_s` -> D2H substitution site | `bi_24t` | similar | 6.12 / 36.2 -> -5.4 ps | 22.5 ps | 8.6 / 12.7 mV |

Notes on the D2H lanes: the COB side is harmless (a lane at contact 57 sits inside the group's 17.3..39.8 ps range).
The cost is on the die and at the pad: the lane leaves the common launch-to-pad corridor, so its on-die delay no longer
tracks the other ten (budget HL-D2H-SKEW 400 ps for pad tco spread plus launch tree; the FPGA per-bit delay, >= 1.6 ns
range, can absorb a static offset); and a 3.3 V output with about 1 ns edges and 30 to 42 mA peak (`host_ssn`) then
switches at 312.5 Mb/s next to USB_DN and 422 um from the WIRE_RX_P bond, drawing its current from the east ring
between bonds 18 and 26, where bond 18 is already the worst-loaded supply bond. On-die wire delay was not computed (no
extraction, no simulation in this job).

### 5.3 Ranking

| Rank | Signal | Why | What it costs |
|---|---|---|---|
| 1 | **HOST_CS_N** (bond 14) | Input only, so no driver current or SSN at the east site; slow and level-type, a glitch with SCLK idle clocks nothing; its freed site is next to bond 13, the power-delivery option A position (6.8 / 10.8 mV against 6.5 / 10.6), on the bond 18 side; as a supply bond the wire is 2.46 mm at 26.6 deg (mirror of bond 4 in BOND-AUDIT) | SPI pins split over two connector sides (contact 57 against 63..65): 8 ps of 200 ns. The `spi_cs_n` macro pin wants to sit at the south-east corner. CS_N edges couple to USB_DN at -41 dB (about 30 mV from a 3.3 V edge, per transaction). `bidir[10]` becomes a `dvdd` cell |
| 2 | **RESET_N** (bond 2) | Static input; sits beside its partner POR_BYPASS on bonds 22 / 23 (`rst_n = reset_n_pad & (por_n \| por_bypass)`); on-die route gets shorter (3.2 -> 2.0..2.5 mm) | The freed site is at the west end: 6.9 / 11.1 mV, and it relieves bond 74, not bond 18. A glitch here resets the chip, and the route and bond run beside the CDR ring, the USB pad and USB_DN (same -41 dB). `rst_n_pad` is a named template site with a tie check in `kl_assemble.py` / `kl_checks.py`. Supply-bond wire 2.68 mm at 35 deg |
| 3 | HOST_MOSI (bond 16) | Input, slow | Weaker site: 8.3 / 12.1 mV |
| 4 | HOST_SCLK (bond 15) | Input, slow | Edge sensitive (a coupled glitch is a false clock); also the video alignment marker; 7.5 / 11.5 mV |
| 5 | HOST_MISO (bond 17) | Slow | Output driver on the east ring; corner site gives the least (9.0 / 12.7 mV) and the longest supply wire (2.82 mm, 38.7 deg) |
| 6 | D2H_D[9] (bond 13) | Best outer site among the lanes (6.5 / 10.6 mV) | 312.5 Mb/s 3.3 V aggressor beside USB and WIRE_RX, loads bond 18, leaves the launch corridor |
| 7 | D2H_D[6..8] (bonds 10..12) | Best supply positions (4.0..5.6 / 8.4..9.8 mV) | Same as rank 6; D[6] also moves +13.5 ps against the clock on the COB |
| last | D2H_CLK, D2H_D[0..5] | | Clock is the group reference; west-half lanes give less to bond 18 |

**Best: HOST_CS_N. Runner-up: RESET_N.** The gap between them is the site (bond 14 against bond 2) and the consequence
of a glitch. If the supply position matters more than everything else (bonds 10 to 12 give 8.4 to 9.8 mV against 10.8),
only a D2H lane delivers it, at the costs in rank 6 and 7.

Not determined: wired-mode current in bond 18 with a supply at bond 14 instead of 13 (power-delivery model rerun);
on-die route feasibility and delay to `bidir[17]`; coupling from bond 23 to WIRE_RX_P (non-adjacent, not in the model);
whether the assembler and the provider accept a supply bond on a signal finger (wafer-space-questions.md).

## 6. Files

| File | Content |
|---|---|
| `package-channel.new.json` | the file to copy to `spec/package-channel.json` |
| `channel_model.py` | corrected copy of `scratch/cob/channel_model.py` (north order, `die_xy` north, SIG map, classes) |
| `placement.py`, `lo_sweep.py`, `lo_term.py` | copies with paths changed, WCLK_IN pair removed |
| `lo_bigc.py` | recomputes `lo.larger_padC` (`lo_bigc.py old` checks it against the old file) |
| `merge.py` | scripted merge (`merge.py check` = regression against the current spec file) |
| `north_proof.py`, `site_to_bond.json` | coordinate proof of the bond numbering |
| `diff.py`, `diff_pins.md`, `site_list.md` | per-pin old/new table, 74-bond list |
| `channel.json`, `placement.json`, `lo_sweep.json`, `lo_term_skew.json`, `lo_bigC.json`, `*.log` | intermediate outputs |

To regenerate, one job at a time, from `scratch/pads-core/spec/`:
`python3 north_proof.py && python3 channel_model.py && python3 placement.py && python3 lo_sweep.py && python3 lo_term.py && python3 lo_bigc.py && python3 merge.py`
