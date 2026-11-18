# Die fit (state of 2026-11-18)

Fixed die 3.932 x 5.122 mm = 20.140 mm2. Pad ring and seal band 7.368 mm2, core 3028 x 4218 um = 12.772 mm2.

**The design does not fit. As built it is 2.8-3.5 mm2 over (3.2-3.9 with the channels of what does not place).
With every assigned target met it is 1.5-2.0 over. It places completely only when every block is at its lower
bound, the debug pads are on provider cells, there is no decap bank and the digital macro is back at 2.81 mm2;
with the macro at the 3.65 mm2 it is at today, 0.16-0.90 mm2 stays out even then.** Routing and decap risks are
on top (section 4).

Work directory `die-fit/`. Ledger: `ledger.py` -> `ledger.md` (by master), `ledger.csv` (per instance, with the
lever of each row). Layout numbers: `meas/measure.py` -> `meas/measured.json`. Packer: `packer.py`, `fit.py`,
`variants.sh` -> `run/`. Overheads: `overheads.py` -> `overheads.json`. Rows for owners: `DF-1..12` in
`interface-changes.md`.

## 1. Ledger

One row per instance of `integration/top/pt_chip.conn` (241) plus 13 booked items that are not instances.
Every layout number is the KLayout bounding box of the GDS on disk, measured on 2026-11-18 (107 layouts, one
job, read-only); nothing is copied from earlier tables. Custom pads are booked at their occupied core intrusion
(lateral extent of drawn shapes per 50 um of depth beyond the 426 um ring band).

- **published**: layout in `analog/*/generated`.
- **as built**: the newest layout on disk that is meant to ship: a staged repack where one exists, else the
  published cell; an estimate where nothing is drawn.
- **target**: the assigned target (area pass 4 or owner), else as built.
- **lower bound**: for a drawn block, outline - empty - half of the remaining device-free area, never above
  the target. "Empty" = nothing drawn on any layer, 3 um clear, in pieces of 20 um or more; "device-free" = no
  COMP, Poly, n-well or MIM in such pieces (routing channels plus empty area). Spirals, pads and estimates keep
  their value unless a named lever removes them (`ledger.csv`, column `lever`).

| category | items | published | as built | target | lower bound |
|---|---:|---:|---:|---:|---:|
| digital macro | 1 | none routed | 3.648 E | 3.200 E | 2.814 |
| custom pads, occupied core intrusion | 11 | 2.443 (bounding boxes) | 2.037 | 1.934 | 1.394 |
| analog blocks in `pt_chip.conn` | 229 | 8.497 | 7.097 | 6.140 | 5.251 |
| booked, not instances | 13 | | 1.237 | 1.237 | 0.784 |
| **block demand** | 254 | | **14.020** | **12.512** | **10.243** |
| of it rows that contain an estimate (E) | | | 4.857 | 4.409 | 3.633 |
| core | | | 12.772 | 12.772 | 12.772 |
| **raw margin, before channels, corridors and scrap** | | | **-1.247** | **+0.260** | **+2.529** |

By status (as built): published 6.00 mm2, laid out but unpublished 7.01 (of it the macro 3.65), schematic or
generator only 0.84, missing 0.17.

### 1.1 Rows of 0.04 mm2 and more (all rows: `die-fit/ledger.md`)

P published, U laid out and unpublished, S schematic or generator only, M missing. E = the row contains an
estimate. mm2, summed over the instances of a master.

| item | n | status | W x H um, as built | published | as built | target | lower bound | empty / device-free |
|---|---:|---|---|---:|---:|---:|---:|---|
| `pt_digital_macro` | 1 | U E | 1716 x 2126 (failed global routing) | | 3.648 | 3.200 | 2.814 | |
| `pad_rf_pair` (RF_RX, BB_I, BB_Q, WTX_EXT) | 4 | P | 310 x 913 | 0.604 | 0.588 | 0.588 | 0.147 | |
| `pt_lc_qvco5` | 1 | P | 848 x 628 metal (bounding box 898 x 653 with keep-out) | 0.586 | 0.532 | 0.532 | 0.532 | spiral |
| `pt_adc_i`, `pt_adc_q` | 2 | U | 480.3 x 936.3 | 1.156 | 0.899 | 0.660 | 0.509 | 20 % / 67 % |
| `pt_lo_vreg` | 1 | U | 407.4 x 1081.6 | | 0.441 | 0.300 | 0.300 | 11 % / 29 % |
| decap macro-edge bank (1.5 nF) | 1 | S E | 26 tiles of 125 x 120 | | 0.390 | 0.390 | 0 | |
| `pad_refpad` (REF, AUX_CLK) | 2 | P | 401 x 913 | 0.391 | 0.343 | 0.343 | 0.343 | |
| `pad_wirepad` (USB) | 1 | P | 521 x 1435, L-shaped | 0.526 | 0.342 | 0.300 | 0.300 | |
| `pt_bbfilter_i`, `_q` | 2 | P | 586.3 x 583.1 | 0.684 | 0.684 | 0.460 | 0.391 | 25 % / 61 % |
| `pt_core_bias` | 1 | U | 925.6 x 326.0 | 0.302 | 0.302 | 0.180 | 0.163 | 26 % / 66 % |
| `pt_wrx_cap` | 1 | U | 1210.5 x 242.7 (r7c) | 0.956 | 0.294 | 0.294 | 0.253 | 5 % / 23 % |
| second capture for > 2.5 Gb/s receive | 1 | S E | as `pt_wrx_cap` | | 0.294 | 0.294 | 0.294 | |
| `pad_txpad` (WIRE_TX) | 1 | P | 481 x 1227, L-shaped | 0.385 | 0.268 | 0.247 | 0.247 | |
| `wtx_ser8d` (new transmit path) | 1 | U | 742.1 x 315.6 | | 0.234 | 0.234 | 0.171 | 7 % / 47 % |
| `pad_hspad` (WIRE_RX) | 1 | P | 492 x 913 | 0.240 | 0.209 | 0.209 | 0.209 | |
| `pt_lo_lf` | 1 | P | 402.8 x 482.0 | 0.194 | 0.194 | 0.194 | 0.149 | 1 % / 1 % |
| `isw_debug` x 5, `isw_wired` x 2, `isw_conv` x 2, `isw_rf` | 10 | P | 184-264 x 173-243 | 0.427 | 0.427 | 0.427 | 0.362 | 8-11 % / 20-24 % |
| `pt_detect` | 1 | P | 251.3 x 690.4 | 0.173 | 0.173 | 0.090 | 0.090 | 8 % / 71 % |
| `pt_pll_vreg2` | 1 | P | 445.4 x 389.4 | 0.173 | 0.173 | 0.173 | 0.146 | 7 % / 24 % |
| `pt_pll_ring` | 1 | P | 210.0 x 793.5 | 0.167 | 0.167 | 0.127 | 0.127 | 2 % / 43 % |
| `pad_rftxpad` | 1 | P | 310 x 913 | 0.151 | 0.147 | 0.147 | 0.147 | |
| `pt_lo_mmd` | 1 | U | 377.9 x 383.8 | 0.361 | 0.145 | 0.145 | 0.115 | 3 % / 38 % |
| `pad_single_leg` (WMON) | 1 | P | 302 x 913 | 0.147 | 0.140 | 0.100 | 0 | |
| `pt_lna_ind` | 2 | U | 260 x 266 | 0.138 | 0.138 | 0.138 | 0.138 | spiral |
| `pt_dac_i`, `_q` | 2 | U | 668.5 x 200.6 | 0.372 | 0.268 | 0.260 | 0.202 | 14 % / 35 % |
| `pt_lo_ext` | 1 | U | 343.1 x 387.7 | 0.155 | 0.133 | 0.120 | 0.098 | 8 % / 45 % |
| `pt_lo_pfdcp` | 1 | P | 257.0 x 482.9 | 0.124 | 0.124 | 0.124 | 0.096 | 4 % / 41 % |
| `pt_refbuf` | 1 | P | 391.0 x 299.5 | 0.117 | 0.117 | 0.117 | 0.084 | 24 % / 33 % |
| `pt_slicer` | 1 | P | 298.8 x 367.8 | 0.110 | 0.110 | 0.110 | 0.081 | 7 % / 47 % |
| second slicer bank | 1 | S E | as `pt_slicer` | | 0.110 | 0.110 | 0.110 | |
| `pt_rfdriver` | 1 | P | 475.8 x 203.5 | 0.097 | 0.097 | 0.097 | 0.075 | 5 % / 40 % |
| `pt_pll_ring_core` | 1 | P | 196.0 x 438.9 | 0.086 | 0.086 | 0.065 | 0.065 | 1 % / 37 % |
| `pt_cdr` | 1 | P | 259.3 x 319.8 | 0.083 | 0.083 | 0.083 | 0.076 | 0 % / 18 % |
| `pt_wiredtx` less its quarter-rate core | 1 | U E | 544 x 152 | 0.246 | 0.083 | 0.083 | 0.083 | |
| `term_buffer` | 1 | P | 156.8 x 479.6 | 0.075 | 0.075 | 0.045 | 0.037 | 24 % / 76 % |
| `pt_ctle` | 1 | U E | 194 x 354 (owner's number, not re-measured) | 0.133 | 0.069 | 0.069 | 0.069 | |
| TX T-coil reserve | 1 | M E | 570 x 120 | | 0.068 | 0.068 | 0.068 | |
| `pt_char_rffet`, `_open`, `_short` | 3 | P | 260 x 260 | 0.203 | 0.203 | 0.203 | 0.172 | probe frames |
| `pt_diff_clk_rx` | 3 | P | 198.0 x 112.8 | 0.067 | 0.067 | 0.067 | 0.054 | 0 % / 38 % |
| `atb_leaf_s` x 58, `atb_leaf_f` x 21 | 79 | P | 30.6 x 27.0, 30.8 x 35.3 | 0.071 | 0.071 | 0.071 | 0.071 | |
| `pt_bb_tap` | 3 | U | 99.1 x 196.9 | 0.059 | 0.059 | 0.059 | 0.046 | 4 % / 37 % |
| `pt_clk_obs16` | 1 | U | 127.5 x 414.5 | 0.092 | 0.053 | 0.053 | 0.053 | 0 % / 0 % |
| `pt_lna_deg` | 2 | S E | 140 um spiral, generator only | | 0.050 | 0.050 | 0.050 | |
| `pt_termination`, `tx_interlock` | 2 | P | 141 x 342, 139 x 345 | 0.096 | 0.096 | 0.078 | 0.067 | |
| `pt_ptrim` | 1 | U E | about 190 x 211 (redesign candidates) | 0.290 | 0.045 | 0.045 | 0.045 | |
| `wtx_mux8` (new transmit path) | 1 | U | 291.3 x 148.6 | | 0.043 | 0.043 | 0.043 | 8 % / 9 % |
| `atb_grp` x 7, `pt_lna` | 8 | P / U | 99 x 62, 220 x 195 | 0.086 | 0.086 | 0.086 | 0.078 | |

Estimates in the ledger (flag E), largest first: the digital macro (no routed result at any size for the
current RTL); the decap bank (cell published, bank not drawn); the second slicer, capture and blender for
receive above 2.5 Gb/s (0.44, architecture not designed); `pt_wiredtx` remainder (0.083: no block top of the
new transmitter exists; wired TX is 0.360 in all if the new path replaces the quarter-rate core, 0.524 if both
stay); `pt_ctle` staged size; T-coil reserve; `pt_lna_deg`; `pt_ptrim`; D2H output strip 0.031; CTLE followers,
LNA additions, VCM buffer, clock repeaters, RF-mode time base, `pt_agnd_tie` (0.033 together).

Differences against the ledger of 14 Nov that come from measuring instead of copying: `pt_lo_vreg` 0.441 (was
0.30), `pt_lna_ind` 0.069 each (was 0.036-0.050), `pt_bb_tap` 0.0195 each (was 0.010), `pt_refpad` occupied
0.171 each (was 0.195, the cell tapers), `pad_hspad` 0.209 (was 0.240), `pt_cdr` 0.083 published,
`pt_txpad_bias` 0.0099, `pt_refvcm` 0.0072, the QVCO bounding box (keep-out now inside the cell).

### 1.2 What is not block area

| item | mm2 | basis | estimate? |
|---|---:|---|---|
| pad ring and seal band (outside the core) | 7.368 | die - core; seal ring inside the 26 um edge band | no |
| pad-ring corners | 0 usable | measured on `provider-reference-ring.gds`: each 452 um corner is rail except one 99 x 99 um square and the die-edge band (`meas/ringfree.json`) | no |
| routing channels: 10 um halo on every block (25 um round spirals, 4 um round leaf cells) | 0.76-1.07 | packer, section 3 | derived |
| fixed corridors: D2H / ADC data / SPI north-south 46.5 um wide, external-LO legs 49 x 875 um | 0.172 (0.129 + 0.043) | placed as obstacles | E |
| pad side-pin channel (stacked `pad_hspad`), ptrim pin channel | 0.02 | in the pad obstacle / block width | E |
| decap, 5.4 nF plan: bank 0.390 in the ledger; grid MIM, row fill and bond-site tiles take no core area | 0.390 | `spec/power-delivery.md` 4.2 | E |
| fill keep-outs (QVCO, four LNA spirals, T-coil, rings, probe frames) | no core area; about 1.4 mm2 excluded from fill = 1.7 points of Metal1/Metal2 density | 1.2 points per mm2 (`signoff-gap.md`) | E |
| packing scrap (free slivers below 80 um) | 0.30-0.57 | packer | measured on the packings |

## 2. Packing

Constructive packer on a 2 um bitmap; every lattice position of both orientations is tested, hard constraints
are masks, cost = signal-flow and supply distance - contact length. Self-checks pass (`run/selftest.log`).
Three orderings per macro shape (area-descending; giants then flow list; flow list first) and two macro shapes
of equal area (1716 um and 2024 um wide; the host-link edge needs 1716 um).

Rules applied:
- Fixed: the custom pads at their bond sites with their true shapes, the macro on the north edge, the D2H
  strip, the T-coil reserve, the two corridors.
- Never relaxed: halo; the 23 keep-aways of the v6 floorplan (macro to ADC 210 um, to LNA 1000 um, to QVCO
  300 um; rings to QVCO 500 um; rfdriver to LNA and ADC; capture to ADC 200 um; ...); **QVCO placement rule
  of INT23**: spiral centres 1.7 mm or more from the west die edge and 1.0 mm or more along the edge from the
  RF_TX pads, applied to the cell edge as 1.5 mm and 0.8 mm.
- Relaxed only when nothing else is feasible, and reported: island switch within 150 um of the core ring and
  600 um along it from its supply pad (ten islands, G4); blocks above 20 mA within 500 um of their switch (G6).

Scenarios: **S** as built, **T** targets, **LB** lower bounds (LB also has BB_I, BB_Q, WMON and WTX_EXT pads
off the core and no decap bank). "Unplaced" is what does not fit; the first number is the densest packing
found, the second the flow-first ordering (signal flow and supply adjacency honoured first).

| run | scenario | macro mm2 | other options | core | to place | unplaced, densest | unplaced, flow-first | channels | free left / usable by a 60 um block |
|---|---|---:|---|---:|---:|---:|---:|---:|---|
| `s` | S | 3.65 | | 12.772 | 8.241 | **2.80** | **3.47** | 0.76 | 0.33 / 0 |
| `s-m32` | S | 3.20 | | 12.772 | 8.241 | 2.43 | 3.02 | 0.82 | 0.30 / 0 |
| `s-m28` | S | 2.81 | | 12.772 | 8.241 | 2.11 | 2.80 | 0.84 | 0.33 / 0 |
| `t` | T | 3.20 | | 12.772 | 7.284 | **1.46** | **2.00** | 0.88 | 0.38 / 0 |
| `t-m36` | T | 3.65 | | 12.772 | 7.284 | 1.80 | 2.53 | 0.84 | 0.32 / 0 |
| `t-m28` | T | 2.81 | | 12.772 | 7.284 | 1.12 | 1.82 | 0.93 | 0.32 / 0 |
| `t-l1` | T | 3.20 | BB_I, BB_Q, WMON on provider cells | 12.772 | 7.284 | 1.05 | 1.65 | 0.91 | 0.34 / 0 |
| `t-l2` | T | 3.20 | + no decap bank | 12.772 | 6.894 | 0.70 | 1.37 | 0.96 | 0.33 / 0 |
| `t-l3` | T | 3.20 | + core ring 2 x 25 -> 2 x 12 um | 13.299 | 6.894 | 0.44 | 1.17 | 1.02 | 0.41 / 0 |
| `t-l4` | T | 3.20 | + qdum and lo_obs inside the QVCO outline | 13.299 | 6.866 | **0.41** | **1.17** | 1.02 | 0.41 / 0 |
| `t-l4-m28` | T | 2.81 | same | 13.299 | 6.866 | 0.17 | 1.23 | 1.09 | 0.43 / 0 |
| `s-l4` | S | 3.65 | same four levers | 13.299 | 7.823 | 1.57 | 2.52 | 0.90 | 0.27 / 0 |
| `lb` | LB | 2.81 | | 12.772 | 5.942 | **0** | **0.42** | 1.07 | 0.97 / 0.47 |
| `lb-l3` | LB | 2.81 | core ring 2 x 12 um | 13.299 | 5.942 | 0 | 0.20 | 1.07 | 1.37 / 0.80 |
| `lb-m32` | LB | 3.20 | | 12.772 | 5.942 | 0.03 | 0.56 | 1.05 | 0.67 / 0.13 |
| `lb-m36` | LB | 3.65 | | 12.772 | 5.942 | 0.16 | 0.90 | 0.99 | 0.43 / 0.01 |

Images: `run/fit-<run>.png` for `s`, `t`, `lb`, `s-flow`, `t-flow`, `t-l4`, `lb-l3`, `lb-m36`. All runs: `run/summary.md`, `run/fit-<run>.json`.

Reading:
- The densest packings scatter the chains and are lower bounds on the shortfall, not buildable plans; the
  flow-first packings are what a floorplan that honours signal flow and supply distance looks like to this
  heuristic. A hand floorplan lands between the two.
- The unplaced area needs its own channels: add about 13 % (as built 3.2-3.9, targets 1.65-2.3).
- No keep-away rule fails in any run. The QVCO sits at x = 1617 um, 1.0 mm from its `lo` switch, in every
  run: the INT23 rule and the supply-pad rule G4 (switch at pad 64 on the west edge) cannot both hold. Strap
  need 135-150 um of Metal5 for 15 mV, or the switch moves inboard on a raw-VDD trunk.
- Also relaxed in most runs: `wtx_mux8` and `pt_ptrim` (no legal switch position within 500 um), `wrx_cap`
  and `rfdriver` in some.
- Macro: each 0.1 mm2 of macro costs 0.08-0.10 mm2 of unplaced area. Its aspect ratio is not a lever.

## 3. Routing, grid and decap on these packings (`overheads.json`)

| floorplan | control wire mm | data / clock mm | analog mm | channel area needed: all minimum pitch / data, clock and analog at double pitch | channel area the halo gives | endpoints on unplaced blocks (not counted) |
|---|---:|---:|---:|---:|---:|---:|
| `s` | 361 | 256 + 30 | 427 | 0.87 / 1.48 | 0.76 | 303 |
| `t` | 330 | 350 + 29 | 576 | 1.07 / 1.89 | 0.88 | 175 |
| `t-l4` | 410 | 283 + 30 | 591 | 1.14 / 1.99 | 1.02 | 73 |
| `lb` | 537 | 356 + 32 | 509 | 1.17 / 1.96 | 1.07 | 12 |
| `lb-l3` | 699 | 410 + 35 | 454 | 1.26 / 2.02 | 1.07 | 12 |

- Method as before: Manhattan lengths from the conn (531 static control bits, 304 data and clock nets, 269
  analog nets), track pitch 0.56 or 1.12 um, three double pitches for ring phases, LO and the forwarded clock;
  a channel offers one signal layer plus 30 % of Metal4/Metal5, 60 % routable.
- **The channels are 0.1-0.2 mm2 short at minimum pitch and 0.7-1.0 mm2 short at realistic pitch.** The
  difference has to cross blocks. Metal3-free area inside the outlines, measured: 3.3 mm2 as built, 2.5 with
  targets, 1.8 at the lower bounds. No block states today which layer may be crossed (DF-12).
- Grid and plates. Metal4/Metal5-free area over the block outlines, spirals excluded and half of the
  sensitive blocks' area unused: **1.93 mm2 as built, 1.34 with targets, 0.73 at the lower bounds: 2.0 / 1.4 /
  0.8 nF** of grid MIM at 55 % plate coverage, against the 2.0 nF minimum and 3.0 nF target of the decap plan.
  Blocks that cannot give the 30 % the grid asks for push 0.43 / 0.54 / 0.88 mm2 of straps into the channels.
- So the area levers and the decap plan work against each other: at the lower bounds the plan loses the bank
  (1.5 nF) and 1.2 nF of grid MIM, leaving about 2.9 nF of the 5.4 (if the 1.16 nF "inside the blocks" exists,
  which nobody has shown). `spec/power-delivery.md` 4.3 rates 2-3.5 nF as good for neither clock line.
  Replacing 1.2 nF by stacked tiles costs 0.30 mm2.

## 4. Shortfall

| mm2 | as built | targets met | targets + assembly and pad levers (`t-l4`) | lower bounds, macro 2.81 | lower bounds, macro 3.65 |
|---|---:|---:|---:|---:|---:|
| block demand | 14.02 | 12.51 | 11.69 | 10.24 | 11.08 |
| unplaced, densest to flow-first | 2.80-3.47 | 1.46-2.00 | 0.41-1.17 | 0-0.42 | 0.16-0.90 |
| **shortfall with the channels of the unplaced blocks** | **3.2-3.9** | **1.65-2.3** | **0.5-1.3** | **0-0.5** | **0.2-1.0** |
| not included: routing beyond the channels | 0.1-0.7 | 0.2-1.0 | 0.1-1.0 | 0.1-0.9 | same |
| not included: tiles for grid MIM the repacks remove | 0-0.25 | 0.15-0.40 | 0.15-0.40 + the bank | 0.30 + the bank | same |
| not included: island-local decap not shown to exist | 0-0.29 | 0-0.29 | 0-0.29 | 0-0.29 | same |

The earlier tally (0.03-0.18 short against targets, 0.65-0.73 against as built, after levers) no longer holds:
the macro grew from 2.81 to 3.20-3.65 (+0.39 to +0.83), the QVCO regulator is 0.44 as laid out, the LNA coils
are 0.069 each, and the QVCO rule is now applied. The polyphase deletion, the shared AUX clock pair and the
new transmit path (0.108 below the old booking) are in.

## 5. Where the area is: levers, ranked by as built minus lower bound

Sum of all ledger rows: 3.78 mm2 (row 3, the core ring, is core area and is not in that sum). "Invalidates" = verification that has to be rerun. Owner in brackets; rows `DF-n`
in `interface-changes.md` carry the hand-over.

| # | block or item | as built | lower bound | gain | lever | risk | invalidates |
|---|---|---:|---:|---:|---|---|---|
| 1 | digital macro [digital, DF-2] | 3.648 | 2.814 | 0.83 (0.45 to the target) | owner's list: clock buffers 0.136 and gain buffers 0.27 mm2 of cells, single-rank trims, duplicated per-mode logic; the congestion that failed r7c | no outline of the current RTL has routed: the lower bound is the last outline that routed with older RTL | nothing signed off yet; every later STA / hold / GLS run |
| 2 | BB_I, BB_Q, WMON pads on provider `asig_5p0` cells [pads, rf_rx, DF-6] | 0.434 | 0 | 0.43 (packer 0.41) | AP4-7: zero core intrusion | bandwidth and HBM of the provider cell on the fallback-RX and debug paths | bb_tap, fallback-RX, WMON benches; HBM screen of three pads |
| 3 | core ring 2 x 25 -> 2 x 12 um, core edge out by 36 um [assembly, power delivery] | | | 0.53 gross, 0.26 in the packer | AP4-10b, G8 | 0.5-0.9 mV more drop | EM at 85 C and the static-drop run |
| 4 | decap macro-edge bank [power delivery, DF-11] | 0.390 | 0 | 0.39 (packer 0.35) | no dedicated bank | decap 5.4 -> 3.9 nF or less; ripple limit 150 mV is already met without margin | decap response, ring-PLL and QVCO ripple tables |
| 5 | `pt_adc_i`, `_q` [converters, no owner, DF-9] | 0.899 | 0.509 | 0.39 (0.24 to the target) | staged cell is 67 % device-free: Metal3 channel bank (51 % of the old height), two 120 x 75 macro rows in a 408 um row, shared guard rings in the SAR logic | matching-critical rows must not move; the two cheaper attempts failed | ENOB, INL, EN = 0 current, every staged ADC run |
| 6 | `pt_bbfilter_i`, `_q` [rf_rx, DF-3] | 0.684 | 0.391 | 0.29 (0.22 to the target) | 25 % empty; MIM (0.034 each) over the amplifiers; abutted rows | coupling into the active-RC nodes | FS-2 extracted set, noise, DCOC |
| 7 | WTX_EXT pad [pads, wired TX; user decision OCP-2] | 0.147 | 0 | 0.15 | fallback input on the USB pads | loses USB HS transmit from external data | `wtx_ext_rx` bench on the USB pad model |
| 8 | `pt_lo_vreg` [LO, paused, DF-5] | 0.441 | 0.300 | 0.14 | requalify at the -60 dBc spur limit: smaller hold capacitors (47 % of the cell is COMP), second follower stage | rejection at 78.125 MHz without the external capacitor | regulator PSRR, noise, line step |
| 9 | `pt_core_bias` [core support, DF-10] | 0.302 | 0.163 | 0.14 | cells are 0.105 of the 0.302 composite: two abutted rows | shared infrastructure, no-dead-chip | composite LVS, bias observation, PD2-14 |
| 10 | RF probe frames [characterization] | 0.335 | 0.172 | **0.133 done** + 0.031 by stacking | 260 x 260 frames; one 260 x 660 column on shared ground pads | 200 um port spacing is near the minimum for facing GSG probes | none simulated; DRC / LVS redone |
| 11 | `pt_detect` [wired RX, DF-4] | 0.173 | 0.090 | 0.08 | 71 % device-free | layout-only repack moved the thresholds: needs the redesign | squelch / disconnect / OOB thresholds |
| 12 | island switches x 10 | 0.427 | 0.362 | 0.065 | 8-11 % empty at the edge bars | drop is at 18.4 of 20 mV | full-RC drop, EM, soft start |
| 13 | USB and TX pad attachment columns [pads] | 0.610 | 0.547 | 0.063 | AP4-6a: column 523 -> 300 um and 312 -> 160 um | pad requalification | HBM, pad capacitance, return loss |
| 14 | `wtx_ser8d` [wired TX, DF-7] | 0.234 | 0.171 | 0.063 | routing channels are 127 of 315 um of height | timing margin of the new path at ss | extracted eye table |
| 15 | `pt_lo_lf` [LO, paused] | 0.194 | 0.149 | 0.045 (0.12-0.15 with OCP-1) | MIM over the 490 pF MOS capacitor C2; or C2 on the carrier | DRC of MIM over the n-well capacitor; ground-difference spur if off chip | loop phase margin and noise |
| 16 | `pt_wrx_cap`, `pt_pll_ring`, `term_buffer`, `pt_lo_ext`, `pt_refbuf`, `pt_dac_i/q`, `pt_lo_mmd`, `pt_slicer`, `pt_lo_pfdcp`, `pt_pll_vreg2` | 1.61 | 1.24 | 0.37 (0.03-0.04 each) | measured device-free 23-76 %; refbuf: 0.055 of MIM beside the amplifier | per block | each block's extracted set |
| 17 | sharing (CP4-4, 7, 8, 10; QVCO corner slots; steering buffers; `tx_interlock`) | | | 0.12 | `wordclk` into the capture, one prescaler chain, two `obs_pre4` on ring FBCK, qdum + lo_obs in the QVCO outline | LO26 for the QVCO slots | small cells |
| 18 | everything else (below 0.02 each) | | | 0.18 | | | |

Not area in the ledger, but they decide whether the area is usable:
- Routing over blocks (section 3): without it the channels are 0.7-1.0 mm2 short.
- Halo 10 -> 6 um: 0.09-0.35 in the packer, and it takes the same amount out of the channels.
- Blocks under the pad ring or in its corners: nothing (section 1.2). ESD rows under the provider rail band of
  the custom pads (AP4-6b, 0.15-0.19) is a pad redesign and is not in any column.
- Duplicated bias, reference and DAC cells: consolidation pass 4 found 0.03 mm2; the masters are single
  instances of their function. The measured duplicates are small cells (three `pt_bb_tap`, three
  `pt_prescale`, six `pt_obs_pre4`, three `pt_diff_clk_rx`: 0.19 mm2 in all).

## 6. Done in this pass

- **RF probe frames** `pt_char_rffet`, `_open`, `_short`: 430 x 260 -> 260 x 260 um each, -0.133 mm2 (commit
  be37cc6). Port pad centres 200 um apart, ground rails inside the pad columns, pads and openings unchanged.
  On the GDS read back from disk: Magic DRC 0, KLayout DRC 0, DUT LVS unique after rename; OPEN keeps G, D,
  GND separate, SHORT merges them. Stack check (`rffet.py stack`) with a failing negative control. Independent
  review GO-with-conditions (`die-fit/rffet-review.md`): the two code and record conditions are closed; the
  third is an accepted risk for the user (probe spacing). Extracted pad capacitance unchanged within 0.5 fF;
  leads 62 um instead of 112 um.
- Nothing else was edited. Every other lever is in a block that has an owner, is paused (LO), or needs
  extracted reruns that were not started here (converters, core bias, island switches).

## 7. What does not fit even with every lever

- **The macro at 3.65 mm2.** With every block at its lower bound, four pads off the core and no decap bank,
  0.16 mm2 is still unplaced in the densest packing and 0.90 in the flow-first one; routing beyond the
  channels and decap replacement come on top. At 3.20 the densest packing just closes (0.03) and the
  flow-first one is 0.56 short. Only at 2.81 does the lower-bound set place with free area left (0.47-0.80
  mm2 usable).
- **Full decap plan and full repack together.** At the lower bounds the die holds about 2.9 nF of the 5.4 nF
  plan; restoring it costs 0.39 (bank) + 0.30 (tiles) mm2 that the lower-bound packing does not have unless
  the macro is at 2.81.
- **QVCO placement rule with the `lo` switch at pad 64.** Not an area miss: a rule conflict that every
  packing shows (section 2).
- The lower bounds themselves are a measured rule, not designs: 3.6 mm2 of the 10.24 is estimate rows, and
  the ADC (0.254 each), the baseband filter (0.196 each) and the core bias (0.163) have never been drawn at
  those sizes.

## 8. Limits

No GDS assembly, router or DRC of a floorplan; outlines are rectangles except the pads; wire lengths are
Manhattan estimates; the packer is a heuristic. The lower-bound rule (all empty area and half of the
device-free area recovered) is uniform and not block-specific. `pt_ctle`, `pt_ptrim`, `pt_lna_deg` and the
`pt_wiredtx` remainder are owners' numbers, not measured here. Metal-free areas for targets and lower bounds
are scaled from the as-built measurement one for one. Fill density with the keep-outs was not run.
