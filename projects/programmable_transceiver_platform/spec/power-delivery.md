# Power delivery: budget, islands, grid, decap, rails, bonds (pt_rf and pt_wired)

The requirement the floorplans, the blocks and the boards of the two chips are checked against. Demands on other owners
are rows `PD2-*` and `PDS-*` in `scratch/reviews/interface-changes.md`; risks are in [risk-register.md](risk-register.md).
Numbers written `a / b / c` are optimistic / nominal / pessimistic. Model: `scratch/integration/m1-pdn/` (one model,
chip parameter; section 9). Budget: `spec/budgets/power_budget.py --reconcile [rf|wired]`.

Each chip has one external supply. The provider ring joins all supply bonds into one net and all ground bonds into
another. The switched islands hang off the ring; the digital macro, the host pads and the always-on core (POR, bias,
oscillator, reference receiver) are on the raw ring. Operating window 3.15-3.35 V at the die; slow dies may be trimmed
up to a 3.50 V setpoint.

## 0. Status

| Item | pt_rf | pt_wired |
| --- | --- | --- |
| Islands (`spec/chips.json`) | rf_rx, rf_tx, lod, lo, pll, conv, debug | wired_rx, wired_cap, wired_tx, pll, debug |
| Bonds (`integration/chips/<chip>/bond_map.txt`) | 10 supply, 19 ground | 10 supply, 17 ground |
| Mode ceilings (digital at PWR-DIG) | Pass; DXe +6.6 mA, DXa +5.6. At the area-scaled macro (62.6 mA) TXe, TXa, DXe, DXa exceed by 3.5-17 mA | Pass against 430 mA (thermal-set, section 1.1), POST on: W 410 (+20), U 364 (+66); W at the area-scaled macro +2.6, at 81.8 mA -1.9 |
| Island switches | Pass, 7 masters, 0.289 mm2 | Pass with **two `isw_wired` in parallel on wired_tx**; 6 masters, 0.303 mm2 |
| Static drop (117 mV) | Pass: worst 94.3 mV (`lo_mmd`), 96.0 at 81.8 mA | Pass: worst 109.0 mV (`wrx_cap`), 109.2 at 81.8 mA |
| Decap | 5.40 nF as packed | 5.41 nF as packed |
| Macro ripple, limit 150 mV pk-pk | Pass only two-phase: 97 mV at 40 mA residual 0.15; single-phase 212 mV fails | Pass only two-phase, no margin: 148 mV at 60 mA residual 0.15; single-phase 313 mV fails |
| RQ-3 / RQ-3a (rf_rx) | Pass on the supply side (section 5) | n/a |
| QVCO regulator | Requirement for -60 dBc per tone: 33 dB at 78.125 MHz single-phase, 27 dB two-phase (section 6.1) | n/a |
| Ring PLL (regulated, limit 5 ps) | 7.3 ps single-phase (miss), 4.3 ps two-phase | 5.0 ps single-phase (at the limit), 1.7 ps two-phase |
| Bond EM (125 mA per cell, 85 C) | Pass: worst 42 mA | Pass: worst 97.5 mA (`dvdd_pads[0]`) |
| Supply rejection evidence | Missing for every victim (PD2-14..19) | same |
| Supply trim | 3.50 V setpoint stack-up and reliability not evaluated | same |

## 1. Budget against block evidence

Source: `spec/budgets/power_budget.py --reconcile` (row table per chip, sources per row; `power-budget.json`
`pd2_reconciliation.<chip>`). "Worst" is the worst value inside the window (tt/ss/ff, 22-32 C, 3.15-3.35 V). Views:
ext extracted, sch schematic, est no bench, lim owner's limit. Cases: pt_rf RX / TX / DX (RF receive / transmit /
duplex; e = external LO, a = on-chip LO); pt_wired W (2.5-3.125 Gb/s, on-chip PLL), U (USB HS), T (TMDS TX only).

**Digital macro per chip.** One RTL, two configurations. The macro current is the measured both-halves figure (72.09 mA
nominal, AC1_R4 vectorless; 81.79 mA worst, CLOSE_R2) scaled by the synthesized cell area of each configuration against
the both-halves build: pt_rf 1.053 / 1.375 = 0.766 (55.2 / 62.6 mA), pt_wired 1.299 / 1.375 = 0.945 (68.1 / 77.3 mA).
Same RTL, clocks and density, so current is taken proportional to cells. The unscaled 81.79 mA stays as the pessimistic
bound and is carried as its own column in every static result. Host IO is 95.2 mA typical, 116.8 mA at 8 pF, halved in
RF modes (PWR-HOST-RF).

Mode totals (mA), worst in-window analog:

| Chip | Case | Analog worst | Total, digital area-scaled | Total, digital 81.8 | Total, digital at PWR-DIG | Board feed | Ceiling | Margin at PWR-DIG | Margin at 81.8 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pt_rf | RXe | 94.7 | 215.8 | 234.9 | 193.2 | 0 | 260 | +66.8 | +25.1 |
| pt_rf | RXa | 175.7 | 296.7 | 315.9 | 274.1 | 0 | 340 | +65.9 | +24.1 |
| pt_rf | TXe | 142.4 | 263.5 | 282.6 | 240.8 | 37.5 | 260 | +19.2 | -22.6 |
| pt_rf | TXa | 223.4 | 344.4 | 363.6 | 321.8 | 37.5 | 340 | +18.2 | -23.6 |
| pt_rf | DXe | 155.0 | 276.1 | 295.2 | 253.4 | 37.5 | 260 | +6.6 | -35.2 |
| pt_rf | DXa | 236.0 | 357.0 | 376.2 | 334.4 | 37.5 | 340 | +5.6 | -36.2 |
| pt_wired | W | 233.3 | 427.4 | 431.9 | 410.1 | 0 | 430 | +19.9 | -1.9 |
| pt_wired | U | 186.7 | 380.8 | 385.4 | 363.6 | 0 | 430 | +66.4 | +44.6 |
| pt_wired | T | 79.0 | 273.1 | 277.6 | 255.8 | 0 | 430 | +174.2 | +152.4 |

Requirements (traced in `performance-requirements.json`; IDs in [power-partition.md](power-partition.md)):

- **PWR-MODE-CEIL:** total current per chip, including the 37.5 mA rfdriver board feed, within 430 mA (pt_wired, POST
  allowed), 260 mA (pt_rf, external LO), 340 mA (pt_rf, on-chip LO) at worst in-window analog currents, digital at PWR-DIG.
  What the pt_wired value protects: section 1.1.
- **PWR-DIG-WIRED / PWR-DIG-RF:** macro <= 60 mA (pt_wired) and <= 40 mA (pt_rf), unused domains clock-gated, signed off
  with activity-annotated power per chip. pt_rf at its area-scaled 62.6 mA exceeds the TX and DX ceilings by 3.5-17 mA.
- **PWR-HOST-RF:** RF modes run the host link at div2.
- **PWR-DROP:** <= 117 mV from the source (3.3 V - 1 %) to any block tap (section 4).
- **PWR-THERM:** junction 22-32 C across the stopped-to-maximum step (section 1.1).

### 1.1 What the pt_wired ceiling protects

The ceiling is not a physical limit by itself; it stands for the tightest of four. Checked at W = 410 mA (POST on, digital
at PWR-DIG) and at 432 mA (worst analog, digital 81.8 mA, host 8 pF):

| Limit | Source | Value at 410 / 432 mA | Binds at |
| --- | --- | --- | --- |
| Junction 22-32 C across the stopped (15 mW) to maximum step, 2 C plate tolerance: 8 C span | MANDATE 2, B2a | P = 3.35 V x I + 51 mW (TMDS pad and RX divider dissipation, `power_budget.py`): 1.42 / 1.50 W; needs theta(junction-plate) <= 5.7 / 5.4 C/W | **430 mA at 5.42 C/W (3.35 V); 5.19 C/W at the 3.50 V trim setpoint.** B2a requires <= 5.2 C/W |
| Theta, bounded | `package-channel.md` 2 (cold finger through 0.3 mm of 3 W/m K gel: about 5 C/W + 1-2 spreading; bottom path through the paddle vias 35-45 C/W, connector on the back); `wafer-space-answers.md` (250 um die, conductive epoxy not confirmed, 4.0 x 5.2 mm GND paddle, 6 vias) | low 5.0 C/W (gel only), high 7.0 C/W (gel + spreading); free air 40-100 C/W | at 7 C/W the 8 C span holds only 1.14 W = 326 mA: the B2a cold finger at <= 5.2 C/W is required for any ceiling above 326 mA |
| Supply cell / bond EM, 125 mA per cell at 85 C (six Metal2 strips, 60 um, DRM 2.09 mA/um) | section 3 | worst supply bond 97.5 mA (78 %); one open supply bond (`dvdd_pads[1]`): 120.6 mA on `dvdd_pads[0]` (96 %); one open ground bond: 86.6 mA | about 445 mA total with one open bond; not binding at 430 |
| Provider rails (DVDD 124 um, Metal3/4/5) | DRM 14.2 | ring segment current below the worst bond current: < 0.2 mA/um | no |
| Wire | section 3 | 0.8 mil Al, 11.5 K rise at 87.5 mA, about 23 K at 120 mA | no |
| Board regulator | B2a (>= 0.45 A at the sense point) | 0.41 / 0.43 A | 450 mA (margin 40 mA at PWR-DIG) |

So the binding limit is thermal (PWR-THERM with the B2a plate): 430 mA, 4.9 % above W with POST on. POST is allowed. W at
the unscaled 81.8 mA macro (432 mA) is 1.9 mA over and needs 5.40 C/W, inside B2a's 5.2; it is the digital PWR-DIG
requirement that keeps it under. With one open supply bond the static IR budget is missed (126.9 mV at `wrx_cap`) while EM
still holds: an open bond is a yield / bring-up case, not an operating point. The 3.50 V trim setpoint on a slow die sits
exactly at B2a (5.19 C/W).

Carried as estimates or limits (1.25 x in the switch sizing): `pt_wiredtx8` and its POST and pad tail (WT40, block not
published, no ff run), `pll_tx` ring core, `pll_misc`, `lo_mmd_qdum`, QVCO buffer, `lo_pfdcp`, `lo_vreg`, `rxselect`,
`pt_ptrim`, CTLE followers, the LNA (owner limit), ADC/DAC corner currents, USB worst values. On pt_rf the TX ring and
the CDR ring both run in the RF cases (split D1, D2).

## 2. Islands and switches

Sizing rule: design current of an island = sum of the worst in-window currents of its blocks, with 1.25 x on every
estimate or limit and on the rfdriver die-rail share (39.3 %). At that current the full-RC worst-corner drop must be
<= 20 mV and the current must not exceed the design current of the master (n masters in parallel: n x current,
Ron / n, n x area). Masters (`analog/island_support`): `isw_wired` 80 mA / 0.2484 ohm / 0.0641 mm2, `isw_rf` 55 / 0.3007 /
0.0500, `isw_debug` 40 / 0.3878 / 0.0370, `isw_conv` 30 / 0.4807 / 0.0320 (published); `isw_pll` 60 / 0.2877 / 0.0530
(verified, not published).

| Chip | Island | Worst (mA) | Design (mA) | Case | Master | n | Capacity (mA) | Drop at design (mV) | Area (mm2) | Smallest single master that passes |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| pt_rf | rf_rx | 38.2 | 43.6 | RXe | isw_rf | 1 | 55 | 13.1 | 0.0500 | isw_rf |
| pt_rf | rf_tx | 26.3 | 32.3 | DXa | isw_debug | 1 | 40 | 12.5 | 0.0370 | isw_debug |
| pt_rf | lod | 70.6 | 74.1 | RXa | isw_wired | 1 | 80 | 18.4 | 0.0641 | isw_wired |
| pt_rf | lo | 27.5 | 28.1 | DXa | isw_conv | 1 | 30 | 13.5 | 0.0320 | isw_conv |
| pt_rf | pll | 27.6 | 30.7 | RXe | isw_debug | 1 | 40 | 11.9 | 0.0370 | isw_debug |
| pt_rf | conv | 18.7 | 18.7 | DXe | isw_conv | 1 | 30 | 9.0 | 0.0320 | isw_conv |
| pt_rf | debug | 40.0 | 40.0 | rule | isw_debug | 1 | 40 | 15.5 | 0.0370 | isw_debug |
| pt_wired | wired_rx | 28.7 | 30.9 | W | isw_debug | 1 | 40 | 12.0 | 0.0370 | isw_debug |
| pt_wired | wired_cap | 67.6 | 72.9 | W | isw_wired | 1 | 80 | 18.1 | 0.0641 | isw_wired |
| pt_wired | wired_tx | 105.0 | 131.2 | W | **isw_wired** | **2** | 160 | 16.3 | 0.1282 | none |
| pt_wired | pll | 26.4 | 29.4 | W | isw_debug | 1 | 40 | 11.4 | 0.0370 | isw_conv (29.4 of 30 mA: no margin, not taken) |
| pt_wired | debug | 40.0 | 40.0 | rule | isw_debug | 1 | 40 | 15.5 | 0.0370 | isw_debug |

Switch area: pt_rf 0.289 mm2, pt_wired 0.303 mm2.

- **wired_tx.** W = `pt_wiredtx8` 60 mA (53 at ss, x 1.13 for ff) + POST 24 + pad MAIN tail 21 = 105 mA worst, 131 mA
  design. One `isw_wired` carries 80 mA and drops 32.6 mV at 131 mA: fails. Two in parallel: 160 mA, 16.3 mV. With POST
  off (MAIN only): 81 / 101 mA design, still over one `isw_wired` (25.2 mV). `isw_wired` + `isw_debug` (120 mA, 0.151
  ohm) fails at 131 mA. A single larger master (>= 135 mA class, about 0.11 mm2) would do the same job in one cell; not
  designed. Area delta against the `isw_debug` the packer booked: +0.091 mm2.
- Every other master is already the smallest published one that passes; the only further lever is `isw_conv` on the
  pt_wired pll island (-0.005 mm2) at zero current margin, not taken.
- Enables (PD2-2): pt_rf `rf` = rf_rx + rf_tx + lod + lo, `pll`, `conv`, `debug`; pt_wired `wired` = wired_rx +
  wired_cap + wired_tx, `pll`, `debug`. PG to the register file is the AND of the group.
- Debug island rule on both chips: at most 40 mA of debug loads enabled at once.
- EM at 85 C (DRM 14.2): `isw_wired` at 74.1 mA: Metal3 stripes 1.14 mA/um (55 %); each of the two wired_tx masters
  carries 65.6 mA at design (equal sharing requires the two cells on one VISL bar with symmetric feeds). Hand
  calculation from the layout geometry.
- Soft start (`analog/island_support/pd2-softstart.json`): dip 0 mV, peak current 1.0 x load, EN to PG <= 8.4 us at the
  previous island loads; the two-master wired_tx and the new wired_tx load are not run.

## 3. Bonds

| Chip | Supply bonds | Ground bonds |
| --- | --- | --- |
| pt_rf | 8 provider (`dvdd_pads[0..5]`, `vdd_pads[0..1]`) + `inputs[3]` (rf_tx feed), `bidir[19]` (lo feed) | 10 provider + 9 on signal sites (`inputs[2,4,5]`, `bidir[14,15,17,18,22,25]`) |
| pt_wired | 8 provider + `inputs[0]`, `bidir[25]` (HS driver supply) | 10 provider + 7 on signal sites (`inputs[1,6,8,10,11]`, `bidir[17,22]`) |

- The bonds on signal sites are modelled as present: they are pending **D-SPLIT-SUPSITE**
  (`integration/chips/decisions.md`). A supply bond on a signal site has no COB 1 uF capacitor (8.1-8.7 nH to the first
  capacitor against 4.0-4.6 nH); the model gives it none.
- Per-cell rating at 85 C: 125 mA (six Metal2 strips, 60 um, 2.09 mA/um).
- Bond currents, worst case, pessimistic set with the macro at 81.8 mA (`e7_static.py`): pt_rf worst supply bond 41.8 mA
  (`dvdd_pads[2]`, DXa), ground 41.2 mA (`dvss_pads[4]`); pt_wired worst supply 97.5 mA (`dvdd_pads[0]`, W, 78 % of the
  rating), ground 77.8 mA (`dvss_pads[0]`). Ring drop 28.1 mV (pt_rf), 47.8 mV (pt_wired).

## 4. Supply grid and static drop

Budget: 117 mV DC from the source (3.267 V) to any block tap, supply drop plus ground rise, at the pessimistic set and
worst in-window currents.

| ID | Requirement | Value |
| --- | --- | --- |
| G1 | Raw VDD and VSS mesh over the whole analog core, over blocks too | Metal5 vertical and Metal4 horizontal straps, >= 15 % coverage per net on each layer (minimum that passes, section 4.1: pt_rf M4 10 / M5 13 %, pt_wired M4 12 / M5 15 %), 20 % wanted; via4 at every same-net crossing |
| G2 | Strap pattern | VDD and VSS straps paired, pair pitch <= 70 um (loop <= 0.4 nH per 250 um square) |
| G3 | Blocks that use Metal4 or Metal5 inside | VDD/VSS ring of the same cross-section around them; no mesh gap wider than 250 um |
| G4 | Island switch position | VDD edge bar within 150 um of the core ring, as the die-fit packing places them (`scratch/reviews/die-fit/run/<chip>/fit-s.json`, `switches`) |
| G5 | Island rails | Metal5 (or Metal5 + Metal4) from the VISL bar; <= 15 mV from the bar to any block supply pin at the worst current of all blocks on that pin |
| G6 | Switch-to-block strap width | Metal5 >= 0.47 um per mA per 100 um. At the packed distances (table below) several straps are wider than practical: move the switch or the block, or add a raw-VDD trunk (PDS-3) |
| G7 | Digital macro | Rings tied to the core ring along the north side and to the G1 mesh on the other sides at <= 80 um pitch (PD2-7) |
| G8 | Core ring | 2 x 25 um (may narrow to 2 x 12 um); provider rails uncut through every site |

Results (`e7_static.py chip=<chip>`; pess = pessimistic set and worst currents with the area-scaled macro; last column
the macro at 81.8 mA):

| Chip | Tap | Island | mA | Drop opt / nom / pess / pess-81.8 (mV) | Split: to switch / switch / strap / ground | Metal5 strap at the packed distance |
| --- | --- | --- | ---: | --- | --- | ---: |
| pt_rf | lo_mmd | lod | 34.8 | 53.5 / 61.9 / 94.3 / 96.0 | 34.0 / 21.9 / 15.0 / 23.5 | 154 um |
| pt_rf | lo_ext | lod | 13.7 | 52.4 / 61.2 / 91.6 / 94.0 | 34.0 / 21.9 / 15.0 / 20.7 | 123 um |
| pt_rf | qvco (regulator input) | lo | 25.0 | 51.3 / 58.5 / 77.4 / 78.6 | 28.0 / 16.5 / 15.0 / 17.9 | 60 um |
| pt_rf | rfdriver | rf_tx | 61.7 | 45.1 / 50.9 / 62.2 / 64.1 | 14.9 / 12.7 / 15.0 / 19.6 | 29 um |
| pt_rf | lna | rf_rx | 21.4 | 38.6 / 43.4 / 55.3 / 56.5 | 12.4 / 14.4 / 15.0 / 13.5 | 92 um |
| pt_rf | adc_q | conv | 6.3 | 38.0 / 42.6 / 54.4 / 55.6 | 13.2 / 11.2 / 15.0 / 15.0 | 63 um |
| pt_rf | pll_tx | pll | 10.2 | 29.8 / 33.1 / 50.6 / 52.3 | 14.4 / 13.4 / 15.0 / 7.9 | 29 um |
| pt_rf | digital macro | raw | 62.6 | 23.1 / 28.8 / 41.6 / 46.0 | ground 19.5 | |
| pt_wired | wrx_cap | wired_cap | 46.6 | 73.7 / 85.5 / 109.0 / 109.2 | 41.2 / 21.0 / 15.0 / 31.8 | **323 um** |
| pt_wired | ptrim | wired_cap | 21.0 | 68.1 / 79.1 / 103.7 / 103.9 | 41.2 / 21.0 / 15.0 / 26.5 | 96 um |
| pt_wired | pt_wiredtx8 (+POST) | wired_tx | 84.0 | 62.9 / 73.2 / 98.6 / 99.0 | 27.6 / 16.3 / 15.0 / 39.7 | **290 um** |
| pt_wired | slicer | wired_rx | 9.8 | 49.4 / 56.8 / 78.1 / 78.3 | 28.5 / 13.9 / 15.0 / 20.7 | 34 um |
| pt_wired | pll_tx | pll | 10.2 | 42.6 / 48.9 / 71.2 / 71.5 | 17.7 / 12.8 / 15.0 / 25.7 | 109 um |
| pt_wired | pll_cdr | pll | 10.2 | 41.5 / 47.6 / 69.5 / 69.9 | 17.7 / 12.8 / 15.0 / 24.0 | 161 um |
| pt_wired | digital macro | raw | 77.3 | 28.0 / 35.3 / 50.2 / 51.1 | ground 24.3 | |

- Margin at the worst tap: pt_rf 22.7 mV (19 %), pt_wired 8.0 mV (7 %) at 15 % coverage. pt_wired needs the 20 %
  coverage (G1 "wanted") for margin; not rerun at 20 %.
- The model sets every strap to exactly 15 mV (G5); the widths in the last column are what that costs at the packed
  distances. `wrx_cap` (1.5 mm from `isw_wired_cap`), `pt_wiredtx8` and `lo_mmd` / `lo_ext` need the switch moved
  toward the load or a raw-VDD trunk that is not in the model.

### 4.1 The grid as drawn (ASM-9)

The assembly draws the core ring at 2 x 14 um (Metal4 + Metal5) and the mesh at Metal4 7.3-7.8 % / Metal5 10.5-11.0 %
per net (pt_rf) and 8.0-8.5 % / 11.5-11.9 % (pt_wired) (`integration/assembly/README.md`). Checked with those values
(`scratch/integration/m1-pdn/asm9_drawn.py`): pessimistic set, worst currents, digital at the unscaled 81.8 mA (pt_wired
W 432 mA with POST on), all bonds and each single open supply bond. EM at 85 C: core ring 14 um x (2.09 + 4.5) mA/um =
92 mA per net; supply cell 125 mA.

| Chip | Grid M4 / M5 per net | Worst tap, all bonds (mV) | Worst tap, one open supply bond | Worst bond (mA), all / one open | Core ring current (mA) | Result |
| --- | --- | --- | --- | --- | ---: | --- |
| pt_rf | 7.3 / 10.5 % (drawn) | 125.6 `lo_mmd` (also `lo_mmd_qdum` 121.0, `lo_ext` 119.5) | 128.9 | 50.0 / 61.6 | 3.5 | **IR fails**; EM passes |
| pt_rf | 10 / 13 % | 109.8 | 113.1 | 46.0 / 55.2 | 2.9 | passes |
| pt_wired | 8.0 / 11.5 % (drawn) | 129.0 `wrx_cap` (also `ptrim` 120.7, `pt_wiredtx8` 118.9) | 149.1 (`dvdd_pads[0]` open) | 101.2 / **126.7** (`dvdd_pads[1]` open) | 6.1 | **IR fails; EM fails by 1.7 mA with one open bond** |
| pt_wired | 12 / 15 % | 114.0 | 132.4 (`dvdd_pads[0]` open), 119.7 (`dvdd_pads[1]`) | 98.7 / 122.9 | 5.5 | passes with all bonds |
| pt_wired | 15 / 15 % | 109.5 | 127.4 | 97.7 / 121.0 | 5.3 | passes with all bonds |

- **Required coverage per net: pt_rf Metal4 >= 10 %, Metal5 >= 13 %; pt_wired Metal4 >= 12 %, Metal5 >= 15 %** (G1).
- The core ring is not the limit: 2 x 14 um carries 3-6 mA (the provider rails carry the ring current); 2 x 25 um changes
  the worst tap by 0.1-0.4 mV. G8 stays at >= 2 x 12 um.
- With `dvdd_pads[0]` open, pt_wired misses 117 mV at any coverage up to 15 % (127 mV): an open bond is a yield /
  bring-up case, not an operating point; EM holds at >= 12 / 15 %.

### 4.2 pt_wired bonds with one open supply bond

Target: worst supply cell <= 106 mA (15 % margin to 125 mA) in every single-open-supply-bond case at W 432 mA with POST on
(grid at 12 / 15 %, `asm9_drawn.py`). The current bond map gives 122.9 mA (`dvdd_pads[0]` with `dvdd_pads[1]` open): both
east-bottom loads (`isw_wired_cap` and `isw_wired_rx`, 96 mA together) feed from `dvdd_pads[0]`. No east or south signal
site is free. Required (`out/wired/pds9_bonds.txt`):

- `bidir[22]` (east, between WIRE_TX and WTX_EXT, today the HS-driver ground) becomes a VDD bond (supply cell per
  D-SPLIT-SUPSITE); ground bonds 17 -> 16, supply 10 -> 11.
- `isw_wired_rx` moves from the south-east corner to the east edge gap beside `dvdd_pads[1]` (y about 2100-2420, between
  `pad_usb` and `isw_wired_tx`); its strap to the wired RX blocks grows (G5 still 15 mV).

| Case | Worst bond (mA) | Worst tap (mV) |
| --- | ---: | ---: |
| all bonds | 84.1 (`dvdd_pads[0]`) | 112.0 (`wrx_cap`) |
| `dvdd_pads[0]` open | 105.4 (`dvdd_pads[1]`) | 127.4 (open-bond case, not an operating point) |
| `dvdd_pads[1]` open | 104.4 (`dvdd_pads[0]`) | 116.9 |
| any other supply bond open | <= 90.1 | <= 113.5 |

Either change alone is not enough: `bidir[22]` to VDD gives 113.2 mA, moving `isw_wired_rx` alone 118.1 mA. Converting a
west ground site (`inputs[1]`) does nothing (122.5 mA).

## 5. Decap

### 5.1 The plan per chip, as packed (D9)

Full 5.4 nF on both chips (`scratch/reviews/die-fit/decap.json`, as built; positions from the packing):

| Part | pt_rf (nF) | pt_wired (nF) | Where | Structure, loss |
| --- | ---: | ---: | --- | --- |
| Row fill | 0.34 | 0.43 | Free sites of the macro | `pt_decap50_*`, tau 60 ps |
| Bond-site tiles | 0.23 | 0.26 | Under the provider rail of the custom pad sites (12 / 14 sites) | `pt_decap_tile`, tau 335 ps |
| Grid MIM | 1.54 | 0.65 | Plates over the Metal4/Metal5-free block outlines (spirals excluded) | `cap_mim_2f0_m4m5_noshield`, 1.9 fF/um2 |
| Macro-edge bank | 1.50 | 1.50 | `decap_bank_00..25`: pt_rf along the south edge of the macro (y 3284-3404) and its west / east sides; pt_wired along the west side (x 972-1097) and the south edge (y 2980-3105) | `pt_decap_tile` + MIM, 60 / 40 % |
| Stacked tiles | 1.79 (0.447 mm2, 30 cells) | 2.57 (0.641 mm2, 43 cells) | `decap_tile_*` where the packer found room: pt_rf mostly on the west edge (x 452-577), around the ADCs and LNA (x 1250-1770); pt_wired on the west edge, around `core_bias` / `pll_cdr` (x 1000-1700, y 1900-2650) and the north-east corner | same as the bank |
| **Total** | **5.40** | **5.41** | | about 60 % of the capacitance lossy |

Island-local: the plan adds no capacitor on any island rail. The model carries 50-250 pF of block capacitance per island
at 0.3 ohm.

### 5.1a Decap reach of the CDM-sensitive pads (PC-43, PC-44)

Requirement: on pt_wired, >= 1 nF of die decap within 0.7 ohm (ring path plus the decap's own series resistance) of the
HS pad sites `bidir[14]`-`bidir[21]` (WIRE_RX, USB, WIRE_TX); the CDM protection of `pad_hspad` and `pad_txpad` was
qualified against that lumped 1 nF / 0.7 ohm. The same check is reported for the pt_rf RF and reference pads.

Method (`scratch/integration/m1-pdn/cdm_decap.py`): impedance between ring VDD and ring VSS at the pad site, bonds
removed (the board is not reached within a CDM event), plan as packed, mesh at the G1 requirement, ring from the
provider rails (0.20 / 0.25 mohm per um DVDD / DVSS, `design-assumptions.md`); fitted as series R-L-C at 20 / 60 MHz and at 150 / 450 MHz (the CDM band). Pessimistic set:

| Chip | Site | R at 60 MHz (ohm) | R at 450 MHz (ohm) | C reached (nF) | Loop L (nH) | Result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| pt_wired | bidir[14] WIRE_RX | 0.47 | 0.67 | 5.8 | 0.17 | pass, 4 % margin at 450 MHz |
| pt_wired | bidir[15] WIRE_RX | 0.46 | 0.63 | 5.8 | 0.16 | pass, 10 % margin at 450 MHz |
| pt_wired | bidir[18] USB | 0.43 | 0.54 | 5.8 | 0.14 | pass |
| pt_wired | bidir[21] WIRE_TX | 0.42 | 0.50 | 5.8 | 0.13 | pass |
| pt_wired | bidir[15], intrinsic only (negative control) | 0.53 | | 0.42 | 0.17 | miss, as it must |
| pt_rf | inputs[9] RF_RX | 0.34 | 0.42 | 6.1 | 0.12 | pass |
| pt_rf | inputs[1] RF_TX | 0.40 | 0.54 | 6.1 | 0.15 | pass |
| pt_rf | bidir[20] REF_IN | 0.40 | 0.47 | 6.1 | 0.13 | pass |

- pt_wired meets the requirement with the plan as packed, but only through the spread plan: the decap physically next to
  the east pads is the bond-site tiles (about 18 pF per site) and three tiles (`decap_tile_00`, `_01`, `_21`). The loop
  inductance of 0.13-0.17 nH is not in the pads' bench: at 2 A with a 200 ps edge it adds about 1.6 V. A 1 nF tile strip
  inboard of the east pad cells (x 2870-2990, y 950-3100) brings bidir[15] to 0.41 / 0.50 ohm and 0.14 / 0.08 nH (60 /
  450 MHz fits).
- **Placement requirement (pt_wired):** >= 1 nF of the tile structure (`pt_decap_tile` + MIM, >= 40 % MIM) inboard of the
  east pad cells between y 940 and 3110, tied to the core ring and the G1 mesh at that edge on both nets; area-neutral by
  moving about 1 nF (0.25 mm2, 17 tiles) from the west-edge tiles (`decap_tile_02`-`_11`, `_16`-`_18`).
- pt_rf: no pads row makes the RF or reference pads depend on die decap; with the plan they would meet the same rule.

### 5.1b pt_rf decap as the assembly floorplan holds it

`scratch/integration/assembly-rf/floorplan.json` places all 26 bank cells and 19 of the 30 tiles (`decap_tile_00`, `_16`,
`_21`-`_29` do not fit): **4.74 nF, 0.66 nF short of the 5.4 nF plan** (11 tiles, 0.165 mm2). Rerun on that floorplan
(`PDN_ASSEMBLY=1`, `out/rf/assembly_*.txt`):

| Check | Value | Result |
| --- | --- | --- |
| RQ-3a die decap >= 3 nF | 4.74 nF | pass |
| RQ-3a Q at the rf_rx rail | 1.9 / 2.0 / 1.8 | pass |
| RQ-3a loop seen from the rf_rx switch | 0.30 / 0.37 / 0.44 nH per rail | pass |
| No undamped >= 50 pF on the rf_rx rail | none added | pass |
| Macro, 40 mA, residual 0.15 / single-phase | 90 / 194 mV (f_ar 95 MHz, Q 2.3) | pass two-phase |
| QVCO rejection needed at 78.125 / 156.25 / 80 MHz | 32.1 (26.1 two-phase) / 22.4 / 13.1 dB | requirement of 6.1 unchanged within 1.1 dB |
| Static IR | 92.9 mV (94.3 at 81.8 mA) | pass |

The moved blocks (`lna`, `qvco` and the switches in the assembly placement) make up for the missing tiles here; every
check passes at 4.74 nF. D9 still books 5.4 nF: the assembly makes up 0.66 nF as tile + MIM (`pt_decap_tile` with MIM
above, >= 40 % MIM) on the raw grid within about 1 mm of the macro (south band, y 2900-3360, or the west edge x 452-577),
or as grid MIM plates (0.35 mm2 of Metal4 / Metal5 plate at 1.9 fF/um2) over block outlines once ASM-8 frees Metal5.

### 5.2 Macro ripple (`e8_decap.py`)

Case pt_rf DXa (D2H at div2), pt_wired W (D2H at 156.25 MHz). Limit 150 mV pk-pk at the macro (PD2-5). The two-phase
columns use the PWR-DIG current with the pessimistic pulse on the worst network; residual = what is left of the
78.125 MHz component (0.15 = 57.5 / 42.5 split, PD2-6).

| Chip | Plan | Macro pk-pk pess (area-scaled / 81.8 mA) | PWR-DIG: single / 60-40 / 0.15 / 0.1 / balanced | core_bias at 0.15 | D2H at macro / core_bias (pess) | f_ar opt / nom / pess (MHz) | Zpk pess (ohm) | Q pess |
| --- | --- | --- | --- | ---: | --- | --- | ---: | ---: |
| pt_rf | intrinsic only (negative control) | 1393 / 1819 | 889 / 563 / 543 / 524 / 485 | 512 | 1031 / 1083 | 198 / 223 / 274 | 4.24 | 3.9 |
| pt_rf | rows + bond sites only (negative control) | 887 / 1158 | 566 / 320 / 305 / 290 / 261 | 243 | 595 / 697 | 175 / 182 / 206 | 2.69 | 3.1 |
| pt_rf | **plan 5.4 nF** | 332 / 434 | **212 / 104 / 97 / 91 / 77** | 59 | 136 / 292 | 103 / 95 / 92 | 0.88 | 2.1 |
| pt_rf | plan x 0.7 | 351 / 458 | 224 / 123 / 117 / 111 / 99 | 87 | 170 / 324 | 117 / 112 / 108 | 1.11 | 2.3 |
| pt_rf | plan without grid MIM | 334 / 436 | 213 / 116 / 110 / 104 / 92 | 75 | 162 / 337 | 117 / 108 / 103 | 0.97 | 2.0 |
| pt_wired | intrinsic only (negative control) | 2330 / 2467 | 1809 / 1120 / 1078 / 1036 / 952 | 1012 | 1542 / 1539 | 252 / 274 / 349 | 4.59 | 3.6 |
| pt_wired | rows + bond sites only (negative control) | 1215 / 1286 | 944 / 496 / 469 / 442 / 387 | 430 | 534 / 519 | 198 / 206 / 214 | 2.50 | 2.8 |
| pt_wired | **plan 5.4 nF** | 403 / 427 | **313 / 157 / 148 / 138 / 119** | 87 | 109 / 124 | 108 / 99 / 92 | 0.86 | 2.0 |
| pt_wired | plan x 0.7 | 434 / 460 | 337 / 192 / 183 / 174 / 156 | 129 | 177 / 193 | 127 / 117 / 108 | 1.07 | 2.2 |
| pt_wired | plan x 1.3 | 376 / 398 | 292 / 140 / 131 / 121 / 102 | 70 | 76 / 90 | 95 / 88 / 81 | 0.72 | 1.7 |
| pt_wired | plan without tiles | 458 / 485 | 356 / 221 / 213 / 205 / 189 | 194 | 263 / 270 | 137 / 132 / 122 | 1.18 | 2.2 |

- Neither chip closes with a single-phase macro (pt_rf 212 mV, pt_wired 313 mV). Both close only with the two-phase launch
  of PD2-6: pt_rf with margin (97 mV), pt_wired without (148 mV at residual 0.15, 138 at 0.1; 183 mV with every part at
  0.7 x). The reference "8 nF MOS inside the macro" gives 72 / 114 mV single-phase; it is not buildable.
- The anti-resonance of both plans is at 92-108 MHz with Q 2.0-2.3, between 78.125 and 156.25 MHz (|Z| 0.69-0.74 ohm at
  78.125, 0.31-0.33 at 156.25, pess). The previous rule stands: keep at least one third of the raw-rail capacitance
  lossy (tiles, row cells); never add MIM without tiles on the same straps.
- The eight 1 uF COB capacitors are mandatory (BP-4).

### 5.3 Supply impedance at each island rail (`e11_islands.py`)

|Z| seen at the VISL node against the VSS mesh at the switch, 1 MHz-1 GHz, plan as packed, opt / nom / pess:

| Chip | Island | Peak |Z| (ohm) | f_ar (MHz) | Q | |Z| at 78.125 MHz | |Z| at 156.25 MHz |
| --- | --- | --- | --- | --- | --- | --- |
| pt_rf | rf_rx | 0.98 / 1.16 / 1.32 | 104 / 96 / 93 | 1.8 / 1.7 / 1.6 | 0.66 / 0.87 / 1.12 | 0.59 / 0.67 / 0.79 |
| pt_rf | rf_tx | 1.08 / 1.28 / 1.48 | 104 / 96 / 93 | 1.8 / 1.6 / 1.4 | 0.76 / 0.99 / 1.27 | 0.67 / 0.79 / 0.95 |
| pt_rf | lod | 1.13 / 1.35 / 1.57 | 104 / 96 / 93 | 1.5 / 1.5 / 1.3 | 0.81 / 1.06 / 1.37 | 0.74 / 0.88 / 1.04 |
| pt_rf | lo | 1.31 / 1.58 / 1.86 | 104 / 96 / 93 | 1.1 / 1.1 / broad | 0.98 / 1.28 / 1.64 | 0.93 / 1.11 / 1.34 |
| pt_rf | pll | 1.08 / 1.29 / 1.50 | 104 / 96 / 93 | 1.6 / 1.5 / 1.2 | 0.76 / 1.00 / 1.28 | 0.70 / 0.85 / 1.03 |
| pt_rf | conv | 1.16 / 1.38 / 1.59 | 104 / 96 / 93 | 1.6 / 1.5 / 1.3 | 0.83 / 1.08 / 1.37 | 0.75 / 0.89 / 1.07 |
| pt_rf | debug | 1.10 / 1.31 / 1.53 | 104 / 100 / 93 | 1.4 / 1.4 / 1.1 | 0.75 / 1.00 / 1.29 | 0.77 / 0.89 / 1.05 |
| pt_wired | wired_rx | 1.19 / 1.38 / 1.56 | 108 / 100 / 93 | 1.5 / 1.4 / 1.1 | 0.79 / 1.03 / 1.32 | 0.82 / 0.93 / 1.08 |
| pt_wired | wired_cap | 1.25 / 1.45 / 1.64 (1.90 at 1 GHz) | 108 / 100 / 93 | 1.5 / 1.3 / 1.1 | 0.85 / 1.10 / 1.40 | 0.86 / 0.98 / 1.13 |
| pt_wired | wired_tx | 0.91 / 1.04 / 1.15 | 108 / 100 / 93 | 1.9 / 1.9 / 1.7 | 0.55 / 0.72 / 0.93 | 0.55 / 0.60 / 0.68 |
| pt_wired | pll | 1.08 / 1.26 / 1.44 | 108 / 104 / 96 | 1.5 / 1.5 / 1.1 | 0.70 / 0.91 / 1.17 | 0.73 / 0.85 / 1.01 |
| pt_wired | debug | 1.04 / 1.23 / 1.41 | 108 / 100 / 93 | 1.7 / 1.5 / 1.4 | 0.67 / 0.90 / 1.17 | 0.70 / 0.78 / 0.90 |

The island rail sees the die anti-resonance through its switch resistance, which lowers Q and adds 0.2-0.5 ohm.

### 5.4 RQ-3 / RQ-3a on pt_rf

| Rule | Value | Result |
| --- | --- | --- |
| Die decap >= 3 nF | 5.40 nF | Pass |
| Anti-resonance Q <= 3 | 1.8 / 1.7 / 1.6 at the rf_rx rail; 2.3 / 2.0 / 2.1 at the macro | Pass |
| <= 0.5 nH per rail seen from the rf_rx switch | loop 0.61 / 0.73 / 0.88 nH (Im Z / w at 30 MHz with all die capacitance removed: bonds, package, COB capacitors), 0.30 / 0.37 / 0.44 nH per rail as loop / 2 | Pass, 12 % margin at the pessimistic set |
| No undamped capacitor >= 50 pF on the rf_rx rail | The plan adds none. Block-internal capacitance is the rf_rx owner's: any >= 50 pF needs >= 0.5 sqrt(L_loop / C) in series (1 ohm at 120 pF, 0.4 ohm at 500 pF) or must sit on the die-rail side of the switch | Pass for the supply plan |

- Negative control: intrinsic decap only gives Q 3.8 at the rail (pess): fails as it must.
- The per-rail split assumes symmetric supply and ground halves; the 19 ground bonds make the ground half smaller than
  the supply half, so the supply rail alone may be above 0.44 nH. Not separated in the model.
- The LNA common-mode resistance itself (RQ-3a's bench, `analog/rf_rx/lna_close.py stab_lf`) stays the rf_rx owner's
  check against these numbers.

## 6. Rails

### 6.1 QVCO: own regulated rail (VDD_LO), pt_rf

The QVCO, `lo_pfdcp` and the regulator sit on the `lo` island (`isw_conv`, 13.5 mV at 28.1 mA), fed from `bidir[19]`
(VDD bond on a signal site, pending D-SPLIT-SUPSITE). Regulator input, pessimistic: 3.19 V DC minimum (77-79 mV total
drop). Spur limit at the QVCO **-60 dBc per tone**, K = -59.7 MHz/V: allowed ripple at the QVCO = 2 f x 10^-3 / K
(2.62 mV at 78.125 MHz, 33.5 uV at 1 MHz). pt_rf has no wired blocks: the aggressors are the macro, D2H at div2, the ADCs,
the PA envelope. Ripple at the regulator input (`e9_victims.py chip=rf`, tap `qvco`, mV peak, opt / nom / pess) and the
rejection it needs; macro and D2H add at the same frequency:

| Line | Ripple, single-phase macro | Ripple, two-phase (0.15) | Allowed at the QVCO | Rejection needed (dB), single / two-phase, pess |
| --- | --- | --- | --- | --- |
| 1 MHz PA envelope (assumed 5 / 15 / 30 % of 61.7 mA) | 0.022 / 0.075 / 0.165 | same | 33.5 uV | 13.9 |
| 5-20 MHz PA envelope | 0.02-0.04 / 0.08-0.14 / 0.18-0.33 | same | 168-670 uV | 0.4 at 5 MHz, 0 above |
| 40 / 80 / 120 MHz ADC | 3.5 / 13.0 / 9.8 (pess) | same | 1.34 / 2.68 / 4.02 mV | 8.2 / 13.7 / 7.8 |
| 78.125 MHz macro + D2H | 17.2 / 48.3 / 113 | 5.7 / 21.4 / 56 | 2.62 mV | **32.7 / 26.6** |
| 156.25 MHz macro + D2H | 13.5 / 31.1 / 60.6 | same | 5.23 mV | 21.3 |
| 234-312 MHz | 29.7 / 27.7 (pess) | | 7.9-10.5 mV | 11.6 / 8.5 |
| 390-470 MHz | 17.5-18.9 (pess) | | 13-16 mV | 2.5 |

Regulator requirement (PD2-11, restated for pt_rf):

| Quantity | Requirement |
| --- | --- |
| Rejection, input to QVCO supply | >= 14 dB from 100 kHz to 2 MHz; >= 1 dB at 5 MHz; >= 33 dB at 78.125 MHz (27 dB with a two-phase macro); >= 14 dB at 80 MHz; >= 22 dB at 156.25 MHz; >= 12 dB at 234 MHz, 9 dB at 312 MHz, 3 dB at 390-470 MHz |
| Load | 30 mA (QVCO 25.0 worst + `lo_pfdcp` 1.5 + margin) |
| Input | 3.15 V DC minimum; 3.19 V at the pessimistic static drop |
| Dropout | set by the minimum VDD_LO at which the QVCO covers its range (LO owner) |
| Output noise | <= 7 nV/rtHz from 100 kHz to 1 MHz (LO-11) |
| Line step | PA turn-on and the RF enable group (one edge, 156 mA, 19 mV ring step): <= 0.1 mV at the output |
| Ground | QVCO and charge-pump returns star-connected at the regulator output capacitor, one tie to the VSS mesh |

- A `pt_pll_vreg`-class native follower (23-27 dB from 10 to 200 MHz, 0.31-0.50 V dropout) meets every line with a
  two-phase macro and every line but 78.125 MHz single-phase (needs 33 dB); its rejection below 10 MHz is not in evidence.
- The laid-out regulator (`pt_lo_vreg`, 0.44 mm2) is to be requalified against this table and shrunk.

### 6.2 LNA ground, pt_rf

- Die VSS at the LNA against board ground at 2421.875 MHz (31st harmonic of D2H div2): 241 / 2207 / 11195 uV rms with 19
  ground bonds; the LNA needs 41 / 60 / 74 dB of rejection from die VSS to its input for -100 dBm. In duplex the PA
  fundamental puts 1.5 / 5.9 / 17.8 mV rms on VSS (57 / 68 / 78 dB). Dedicated LNA ground bonds are now possible on pt_rf
  (split phase 4, pads owner); this model ties every ground bond to the common mesh.
- The rejection itself is not in evidence (PD2-15). Working set: D2H slow slew in RF modes, div4 where the payload allows,
  2421.875 MHz out of the channel plan.

### 6.3 Ring PLLs

Deterministic jitter from the ripple at the `pt_pll_vreg2` input (extracted sensitivity 0.045 ps/mV at 78 MHz, regulated;
limit 5 ps), opt / nom / pess:

| Chip | Single-phase macro | Two-phase (0.15) |
| --- | --- | --- |
| pt_rf (RXa) | 1.7 / 3.7 / **7.3** | 1.1 / 2.2 / 4.3 |
| pt_wired (W) | 0.9 / 2.8 / 5.0 | 0.3 / 1.0 / 1.7 |

Bypass (BYP = 1) is not an operating mode (PD2-13). In RF modes the D2H at 78.125 MHz carries 39 mV of the pt_rf input
ripple: D2H slow slew or div4 removes most of it.

### 6.4 ADC clock, pt_rf

Default 39.0625 MS/s in RF modes puts every 78.125 MHz multiple on DC. At 40 MS/s the worst aliasing line on the conv
island is the macro at 78.125 MHz: 12.5 / 29.2 / 61.7 mV, needing 23 / 31 / 37 dB of reference-buffer and comparator
supply rejection for a -60 dBFS spur (PD2-16). The ADCs' own conversion current puts 44-62 mV at 40-160 MHz on the
`adc_i` tap.

### 6.5 D2H rail

No split (common ring) on either chip. D2H at the macro / core_bias, pess: pt_rf 136 / 292 mV pk-pk (div2, 78.125 MHz),
pt_wired 109 / 124 mV (156.25 MHz). PD2-8 stands: slow slew and lowest drive by default, two-group stagger, div4 in RF
modes when the payload allows.

## 7. Supply ripple each block must tolerate

The 117 mV of section 4 is a DC budget; the ripple below sits on top of it. Differential rail at the tap, worst line in
each band, mV peak, pessimistic (`e9_victims.py`, plan as packed); single-phase / two-phase (0.15) macro:

| Chip | Tap (demand) | Case | 30-100 MHz | 100-200 MHz | 200-500 MHz | 0.5-1 GHz | 1-6 GHz | rms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pt_rf | core_bias (PD2-14) | RXa | 63 / 51 | 39 | 31 | 17 | 1.7 | 80 / 66 |
| pt_rf | refbuf (PD2-16) | RXa | 62 / 46 | 35 | 24 | 14 | 1.7 | 90 / 78 |
| pt_rf | adc_i (PD2-16) | RXa | 62 / 62 | 53 | 49 | 42 | 1.3 | 168 / 161 |
| pt_rf | lna rail (PD2-15) | RXa | 66 / 42 | 30 | 16 | 4.7 | 0.7 | 68 / 48 |
| pt_rf | qvco regulator input (PD2-11) | RXa | 67 / 46 | 31 | 17 | 8.1 | 1.7 | 71 / 52 |
| pt_rf | lo_mmd, VDD_LOD (PD2-11) | RXa | 71 / 46 | 31 | 17 | 6.3 | 82 (own 3 GHz) | 95 / 80 |
| pt_rf | pll_vreg2 input (PD2-17) | RXa | 76 / 39 | 31 | 18 | 8.4 | 1.7 | 74 / 48 |
| pt_rf | rfdriver | TXa | 77 / 42 | 32 | 20 | 9.4 | 47 (own 4.8 GHz) | 85 / 63 |
| pt_wired | core_bias (PD2-14) | W | 92 / 14 | 43 | 26 | | | 83 / 50 |
| pt_wired | slicer (PD2-19) | W | 73 / 11 | 49 | 71 | 43 | | 98 / 81 |
| pt_wired | pll_vreg2 input (PD2-17) | W | 82 / 12 | 43 | 26 | | | 80 / 52 |
| pt_wired | pt_wiredtx8 | W | 83 / 12 | 42 | 30 | | | 218 / 210 |
| pt_wired | wrx_cap | W | 75 / 11 | 48 | 63 | | | 232 / 226 |

Full line lists: `scratch/integration/m1-pdn/out/<chip>/e9_victims_{base,twophase}.txt`. For the victims the ripple is
given, not a pass or fail: the supply-rejection evidence is the demand (PD2-14..19).

## 8. Demands

- **PDS-1** (assembly, user): pt_wired wired_tx on two `isw_wired` in parallel (one VISL bar), +0.091 mm2 against the
  packed `isw_debug`.
- **PDS-2** (closed by PDS-6): pt_wired ceiling 430 mA, thermal-set.
- **PDS-9** (pads, assembly): `bidir[22]` to VDD and `isw_wired_rx` beside `dvdd_pads[1]` (section 4.2).
- **PDS-10** (assembly): 0.66 nF of pt_rf decap to make up (section 5.1b).
- **PDS-7** (assembly): 1 nF of tiles next to the pt_wired east HS pads (section 5.1a).
- **PDS-6** (board): B2a theta(junction-plate) <= 5.2 C/W is now binding for pt_wired; regulator >= 0.45 A leaves 20 mA.
- **PDS-3** (floorplan): straps wider than practical at the packed distances (`wrx_cap` 323 um, `pt_wiredtx8` 290 um,
  `lo_mmd` 154 um, `pll_cdr` on pt_wired 161 um).
- **PDS-4** (digital): two-phase launch (PD2-6) is required on both chips; on pt_wired without margin.
- **PDS-5** (LO owner): QVCO regulator against the section 6.1 table.

## 9. Evidence and regression

- `spec/budgets/power_budget.py --reconcile [rf|wired]`: sections 1 and 2; exits non-zero if an island exceeds 20 mV or
  its masters' current, or a case exceeds its ceiling at PWR-DIG. `--check` writes
  `power-budget.json` with `pd2_reconciliation.<chip>`.
- `scratch/integration/m1-pdn/run.sh rf|wired` runs, one job at a time: `sanity.py` (solver against hand answers and
  ngspice, failing negative case), `e0_sanity_model.py` (builder against a hand calculation with the chip's bond count;
  negative control no decap + one supply bond fails), `e7_static.py` (section 4, bonds), `e8_decap.py` (section 5.2;
  negative controls intrinsic-only and rows + bond sites only fail), `e9_victims.py` (sections 6-7, single- and
  two-phase), `e11_islands.py` (sections 5.3-5.4; intrinsic-only fails RQ-3a), `cdm_decap.py` (section 5.1a; intrinsic-only misses). Outputs `out/<chip>/`.
- Configuration: `chipcfg.py` reads the packing (`scratch/reviews/die-fit/run/<chip>/fit-s.json`), the decap split
  (`die-fit/decap.json`), the bond maps, `spec/chips.json` and `power_budget.py`; it holds nothing chip-specific of its own.
- Soft start: `analog/island_support/pd2_softstart.py`, `pd2-softstart.json`.

## 10. Not verified

- No layout of the grid, the MIM plates, the bank or the tile cells, and no DRC; sections 4 and 5 are requirements
  checked at their limits on a 13 x 18 mesh with the as-built packing, not extractions. The packing is the die-fit
  scenario S; owner floorplans will move switches, tiles and loads.
- The digital macro's current per chip: area-scaled, no per-chip power run; its pulse shape and two-phase split (PD2-6).
- `pt_wiredtx8` current (unpublished, ss only, ff by ratio), POST and pad tail on the island rail as WT40 states.
- The supply / ground bonds on signal sites (D-SPLIT-SUPSITE) are modelled as present; bond lengths are the supply-bond
  range for every bond, not the per-bond values of `package-channel.json`.
- The two-master wired_tx switch: current sharing, soft start and EM not run.
- The per-rail split of the loop inductance seen from the rf_rx switch.
- The rfdriver die-rail share (one bench) and the PA envelope current (assumption).
- Everything above 1 GHz is order-of-magnitude. Victim supply rejection (section 7).
- Supply ramps faster than 10 us fire the supply-pad clamps: board rule supply slew <= 0.3 V/us, no hot-plug.
- The 3.50 V trim setpoint; board ground plane ideal.
