# Die-fit study (2026-11-14)

Question: can everything the chip now needs be placed, powered and routed on the fixed 3.932 x 5.122 mm die
(core 3028 x 4218 um = 12.772 mm2)? If not, by how much does it miss and what are the options?

Paper/script study. No circuit simulation, no design file changed. Work dir `scratch/reviews/die-fit/`.
Two light KLayout read-only measurements were run (one job, one thread each): Metal4/Metal5-free area of the staged
layouts (`m45free_staged.json`, controls reproduce area pass 4 to the last digit) and the real footprint of the USB and
wired-TX pads (`padnotch.json`).

STATUS: complete. Verdict in section 4, levers in section 5, reviewer's corrections in section 6.

## 1. Demand ledger

Files: `die-fit/ledger.py` (generator), `ledger.csv` (one row per instance of `pt_chip.conn`: 241 instances after
CP4-1/2/3 and the ten-island change, plus 14 booked items), `ledger.md` (per master, with source and confidence for
every number). This is ledger v2: the independent reviewer's corrections (section 6, `die-fit/review.md`) are applied.
The pre-review ledger and its packing runs are kept in `die-fit/run/v1/`.

Scenarios:
- **A** = published outlines only (git HEAD `generated/`). Never-built items at their estimate. The R8-ARCH second
  capture is booked on the published r6 master (0.956), because that is what "nothing staged publishes" means; with the
  0.29 compact reserve of record instead, A is 0.667 smaller.
- **B** = everything that is staged publishes as measured (bounding boxes of the staged GDS).
- **C** = every assigned repack target of area pass 4 is met, or the staged size where that is already smaller.
- **Cr** = C, but where the owner has declared a target unreachable or nothing backs it, the backed value is used
  (ADC 0.35 each instead of 0.33, `pt_detect` and the CDR ring unchanged, WMON pad as drawn). Added after the review.
- The digital macro is 2.814 mm2 in all of them: the digital owner states 2.45 is not reachable, and the macro still
  has to absorb the decode glue, 130 isolation AND2s, LO/CDR/USB control and decap row cells (cells 1.764 mm2 = 67.4 %).
- Decisions CP4-2 (polyphase deleted) and CP4-3 (WCLK_IN pads and receiver deleted) are applied in all, because the
  conn file already has them.

| category | items | A published | B staged | C target | Cr backed targets |
|---|---:|---:|---:|---:|---:|
| digital macro | 1 | 2.814 | 2.814 | 2.814 | 2.814 |
| custom pads (true occupied core intrusion) | 11 | 2.252 | 2.164 | 2.054 | 2.101 |
| analog blocks that v6 / area pass 4 placed (incl. all ten island switches) | 199 | 8.138 | 6.360 | 5.605 | 5.769 |
| in the conn, in no floorplan or never built | 30 | 0.810 | 0.810 | 0.810 | 0.810 |
| booked, not in the conn (R8-ARCH, tx8, decap bank, D2H strip, T-coil, never-built additions) | 14 | 1.838 | 1.197 | 1.197 | 1.197 |
| **total demand** | 255 | **15.851** | **13.345** | **12.480** | **12.690** |
| core | | 12.772 | 12.772 | 12.772 | 12.772 |
| **raw margin** (before channels, corridors, scrap, extra decap) | | **-3.079** | **-0.573** | **+0.292** | **+0.082** |

Confidence of scenario B: about 9.0 mm2 measured on published GDS/LEF (H), 3.6 mm2 measured on staged or v5 layouts
(M), 0.8 mm2 estimates (L). The largest estimate is the QVCO regulator.

### 1.1 What no floorplan had counted (scenario B, mm2)

| item | mm2 | source | confidence |
|---|---:|---|---|
| decap macro-edge bank (1.5 nF) | 0.390 | power-delivery.md 4.2 | M |
| characterization: three GSG probe frames 430 x 260 (`pt_char_rffet`, `_open`, `_short`) | 0.335 | char_rffet.lef | H |
| QVCO regulator `pt_lo_vreg` (never built; 30 mA, 50-59 dB, 7 nV/rtHz) | 0.300 (0.25-0.38) | `scratch/lo-ap4/vreg2/reg.py` device list (review R1; first estimate 0.12) | L |
| five more island switches (ten islands, 0.426 total against 0.236) | 0.190 | power-delivery.md 2, conn | H |
| characterization: `pt_char_atb`, `ro33`, `ro50`, `cmldiv` | 0.075 | LEF | H |
| LNA degeneration spirals x 2 | 0.050 | rf-lna-p NOTES | M |
| WMON pad: published cell is 302 um wide, floorplans book the undrawn 205 um B cell | 0.047 | util.json vs v5 floorplan | M |
| `pt_usb_txdrv` | 0.031 | USB-INTEGRATION.md | M |
| bias_ext, refvcm, txpad_bias (staged in `scratch/pads-core/bias/pub`), agnd_tie, VCM buffer, forwarded-clock repeaters | 0.032 | layouts / estimates | M/L |
| tx8 reserve overrun (serq8 built at 0.352, booking assumed 0.325) | 0.022 | wired_tx INTEGRATION.md 7 | L |
| 16 isolation clamps + 2 pull-downs left outside the macro | 0.016 | iso-placement.json | H |
| ptrim output stage (MW-14-FIX) | 0.015 | estimate | L |
| CTLE source follower x 2 (one per slicer bank) | 0.010 | wired_rx README Resume 9 | L |
| LNA tail source / gate R / damping, D-EXTCLK selector, FLL driver | 0.010 | review R12 allowance | L |
| RF-mode time base + H2D_CLK present detector (rest of the monitor is RTL) | 0.005 | review R11 | L |
| **sum** | **1.528** | | |

Not booked, flagged: the 1.16 nF of island-local decap that power-delivery.md assumes "inside the blocks" (nobody has
shown it; exposure up to 0.29 mm2 if it has to be added outside); an external capacitor pad for the QVCO regulator.

### 1.2 Double counting and over-booking found

| item | effect mm2 | evidence |
|---|---:|---|
| USB pad (`pad_wirepad`) was booked as its bounding box 521 x 1435. Beyond a depth of 913 um only a 188 um wide attachment column exists; the other 333 x 523 um is empty in every layer | -0.174 | `padnotch.json` (the v5 floorplan had this notch; v6 and area pass 4 lost it) |
| TX pad (`pad_txpad`): column 139 um wide beyond 913 um; 342 x 312 um empty | -0.107 | `padnotch.json` |
| Consequence for lever AP4-6 (attachment repack): worth 0.063 mm2, not 0.19; most of the claimed saving was the notch | | |
| `steer_0..3` and the CML pre-drivers inside `tx8_rsv` are the same function (the pre-drivers replace them) | -0.035 | wired_tx INTEGRATION.md l.20 (review R6) |
| `h2d_gearbox_rsv` booked for nothing: the H2D capture flops are in the macro top rows | -0.031 (B), -0.093 (A) | interface-changes l.580, mode-walk l.484 (review R4) |
| `lc_load_rsv` 0.10 in v6 is the LNA tank coil pair: not added on top of `pt_lna_ind` | (not added) | v6 inventory note RC-16j |
| CP4 inventory total 13.74 counted 146 clamps outside the macro; 130 are now AND2 in the macro | -0.119 | conn commit 0006a99 |
| Supply/clock monitor booked as an analog block; `pt_monitor` is RTL in the macro | -0.015 | review R11 |
| Staged `pt_lo_mmd_qdum` + one `pt_lo_obs` fit the empty slot A inside the QVCO outline | -0.028, kept as a lever (section 5), not taken in the ledger: no one has placed them there | lo-ap4 NOTES l.54 (review R5) |

## 2. Supply, routing and decap overheads (derived, `die-fit/overheads.py`, `overheads.json`)

### 2.1 What the conn file asks the routing to carry

| class | nets | note |
|---|---:|---|
| static control from the macro (`c_*`, one wire per bit) | 531 | biggest consumers: slicer 89, core_bias 74, ptrim 40, bbfilter 36 + 36, wiredtx 21, vthdac 17, clockmux 16, lna 15 |
| status to the macro (`s_*`) | 11 | |
| other macro-to-analog signals (data words, clocks, codes) | 304 | capture 63, wired TX 43, ADC 25 + 25, DAC 11 + 11 |
| macro to pads (D2H 10 + clk, H2D 10 + clk, SPI, debug) | 38 | H2D abuts the macro; D2H runs the full core height to the south pad row |
| analog nets between instances | 269 | ring phase buses 29 (CDRPH, CKP, SLS, TXPH), bias currents 25, ATB tree 35, LO / RF differential 32, CDR votes 19, local 129 |
| supply nets | 18 | VDD, VSS, AGND_RX, VDD_LO, ten island rails, four ESD rails |

### 2.2 Routing demand measured on the packed floorplans

Wire length = for every macro net, Manhattan edge-to-edge distance macro to block; for analog nets, half-perimeter of
the instance centres. Track area = length x pitch: 0.56 um (minimum Metal2-4 pitch) or 1.12 um (double pitch) and three
double pitches per wire for ring phases, LO and the 3.1 mm forwarded clock (shielded pairs). A channel offers its
preferred-direction signal layer plus 30 % of Metal4/Metal5 (the rest of those two is grid, island straps and plates),
60 % routable: capacity = channel area x 0.78.

| floorplan | control mm | data/clock mm | analog mm | track area mm2, all minimum pitch | track area, data + analog at double pitch | channel area needed (min / double) | channel area the 10 um halo gives | endpoints on unplaced blocks (not counted) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B, densest packing | 511 | 337 + 34 (D2H) | 493 | 0.85 | 1.41 | 1.08 / 1.80 | 0.82 | 250 |
| C, densest packing | 491 | 438 + 34 | 511 | 0.93 | 1.58 | 1.19 / 2.03 | 0.87 | 179 |
| B, flow-first order | 694 | 352 + 34 | 363 | 0.88 | 1.37 | 1.13 / 1.76 | 0.93 | 230 |
| C, flow-first order | 738 | 364 + 34 | 401 | 0.93 | 1.46 | 1.20 / 1.87 | 0.94 | 218 |
| C + levers (`c-l6`, nearly everything placed) | 464 | 367 + 32 | 647 | 1.03 | 1.80 | 1.32 / 2.31 | 1.03 | 38 |

- The allowance used before was 10 % of block area = 0.855 mm2. Derived need: **1.1-1.3 mm2 if every wire is at minimum
  pitch, 1.8-2.3 mm2 with data, clocks and analog at double pitch.** The 20 um channels of the packer (10 um halo per
  block, the v6 rule) supply 0.8-1.0 mm2, plus the two fixed corridors below. So the old allowance was 0.25-0.45 mm2
  too small at best, and shrinking the halo is not a lever unless wiring goes over blocks.
- The 531 static control wires are the largest single item (about 0.5 m). They are DC signals: they can cross over the
  decap bank, the pad attachment columns and blocks that leave Metal3 free. That is where the missing channel area has
  to come from; no block states today which layers it leaves free for through-routing.
- Fixed corridors, placed as obstacles in the packer: D2H / ADC-data / SPI north-south corridor 46.5 um x 2784 um =
  **0.129 mm2** (v5 `rsv_corridor_s`, dropped without replacement in v6) and the external-LO G-S-G-S-G legs along the
  REF / AUX_CLK pad tips, 49 x 875 um = **0.043 mm2**. The forwarded wire clock (3.1 mm, shielded pair, about 7 um wide)
  fits in the channels.
- Side-pin blocks: the stacked `pad_hspad` puts RX_P/RX_N and its controls on a side edge: a 32 um channel beside the
  pad (0.016 mm2, booked as part of the pad obstacle). The compact `pt_ptrim` has 56 pins on one edge: 32 um added to
  its width. The LO cells have their ports on the top edge in Metal5 (inside the halo).

### 2.3 Power grid and island straps

- G1 asks for 30 % of Metal4 and of Metal5 (15 % per net) over the whole analog core, blocks included: 3.0 mm2 per layer.
- Measured Metal4/Metal5-free area (>= 20 um tiles) over the outlines, scenario B: 2.16 mm2 of 7.98 mm2 (27 %); 2.31 mm2
  of outlines have no measurement (core_bias, switches, never-built cells, probe frames). Blocks that cannot give 30 %
  push **0.28 mm2** of straps into the channels (measured blocks only; up to 0.98 mm2 if the unmeasured blocks give
  nothing). The channels can carry 0.28 mm2 on Metal4/Metal5; they cannot carry 0.98 mm2 and signals as well. G3 (a ring
  of equal cross-section around every block that uses Metal4/Metal5) is therefore affordable only for the measured set;
  each unmeasured block has to state that the mesh may cross it.
- Island straps (G6: Metal5 width >= 0.47 um per mA per 100 um). power-delivery.md assumes each block within about
  500 um of its switch, about 0.3 mm2 of Metal5 in total. In the packed floorplans the same rule gives **3.6-6.5 mm2**
  of Metal5, which does not exist. Causes, all structural (they appear in every run):
  1. `lod` switch at pad 74 (south-west corner) but `lo_ext` has to sit at the REF / AUX_CLK pad tips, 1.0-5.7 mm away
     (62-368 um of strap for 13.7 mA), and `lo_mmd` has to touch the QVCO tank, which sits at the `lo` switch (pad 64,
     2.1 mm from pad 74).
  2. `pll` switch at pad 35 (north-east) but both rings have to sit at the capture / ptrim (south-east) and at the wired
     TX: 2.0-4.1 mm, 94-198 um of strap each.
  3. `wired_tx`: within 600 um of pad 26 the ring edge is covered by the USB and TX pads; the nearest free ring edge
     puts the switch 520-750 um from `pt_wiredtx` (the 500 um rule is relaxed in every run) and 1.1-2.5 mm from the USB
     driver.
  4. `debug`: its loads are spread over the die by nature (clk_obs, vco_replica, rx_aux_clk 2-4 mm from one switch).
  5. `wired_rx` / `wired_cap` share the 273 um of ring edge below the HS pad; ctle and slicer land 2.3-2.8 mm away
     whenever the south-east corner is full.
- Consequence: the supply rules, not only signal flow, force each island to be compact around its switch. Packing in
  that order costs 0.6 mm2 more scrap than the densest packing (section 3). The G4 pad assignment of `lod`, `pll` and
  `wired_tx` needs another look by the power-delivery owner before a v7 floorplan.

### 2.4 Decap: what fits over the blocks after the repacks

Plan (power-delivery.md 4.2): 5.4 nF = row fill 0.45 + bond-site tiles 0.45 + grid MIM 3.0 (2.0 minimum) + bank 1.5 +
island-local 1.16 (in the model). The grid MIM needs 1.05 mm2 of plate for 2.0 nF and 1.58 mm2 for 3.0 nF, on outlines
whose Metal4/Metal5 are free. Measured free area (>= 20 um tiles, 3 um keep-off, same method as area pass 4; the two
control cells reproduce `m45free.json` exactly):

| | A published | B staged | C targets |
|---|---:|---:|---:|
| free Metal4/Metal5 over analog outlines, spirals excluded (mm2) | 2.84 (area pass 4: 2.86) | **1.88** | **1.34** (estimate: free area shrinks one for one with the outline) |
| share of it that 2.0 nF of plates needs | 37 % | 56 % | 78 % |
| share that 3.0 nF needs | 56 % | 84 % | 118 % (impossible) |
| usable if plates stay off half of the ADC, bbfilter, LNA, mixer, loop-filter and refbuf area (mm2) | 2.25 | 1.36 | 1.04 |
| plate capacitance at 55 % coverage of the usable area (nF) | 2.4 | **1.4** | **1.1** |

Measured examples: ADC 0.300 -> 0.208 mm2 free, DAC 0.138 -> 0.092, `lo_mmd` 0.119 -> 0.015, capture 0.344 -> 0.081,
`pt_cdr` 0.055 -> 0, `lo_ext` 0.028 -> 0.010, `clk_obs16` 0.

- **The repacks eat the decap.** Every repack removes Metal4/Metal5-free area almost one for one. The 3.0 nF grid-MIM
  target is gone in B and C, and the 2.0 nF minimum needs plates over 56-78 % of everything that is left, including
  over the ADC inputs and the loop filter. Realistic: 1.1-1.4 nF.
- To still reach the plan's 5.4 nF, the missing 0.6-0.9 nF (against the 2.0 nF minimum) or 1.6-1.9 nF (against the
  3.0 nF target) has to become stacked tiles at 3.9-4.2 fF/um2: **+0.15 to +0.47 mm2** on top of the 0.39 mm2 bank.
  Otherwise the total is 3.5-3.9 nF, which power-delivery.md 4.3 places "between the lines: good for neither".
- Also unverified: the 1.16 nF "island-local, inside the blocks" (up to 0.29 mm2 if it is not there).

### 2.5 Fill

No core area, but two limits on the floorplan (signoff-gap.md): a fill keep-out costs about 1.2 points of Metal1 /
Metal2 density per mm2 excluded, so keep-outs fit over the spirals and oscillators (QVCO 0.53, four LNA spirals with
their 25 um ring 0.25, T-coil 0.07, rings 0.25: about 1.1 mm2, 1.3 points) but not over all 8 mm2 of analog (30 %
limit). And the denser the packing, the fewer open channels remain to carry the density; the bank tiles help. DCF.1a
needs NDMY / IND_MK markers on every spiral: owner work, no area.

## 3. Packing attempt (`die-fit/packer.py`, `fit.py`, results in `die-fit/run/`)

### 3.1 The packer

Replaces the seeded greedy spiral of v6 / area pass 4. Constructive packer on a 2 um occupancy bitmap: for every block,
**every** lattice position of both orientations is tested with a summed-area table (so a hole that exists cannot be
missed), hard constraints are applied as masks, and the feasible position with the lowest cost is taken. Cost = weighted
Manhattan gap to the already placed partners (signal flow and island switch) + a weak pull to the island's region -
0.6 x contact length (touching-perimeter rule, which is what keeps scrap low).

- Fixed: the eleven custom pads at their bond sites with their true shapes (L-shaped USB and TX pads, staged stacked
  HS pad with its side-pin channel), the D2H strip, the TX T-coil reserve, the two corridors of 2.2.
- Digital macro: 2.814 mm2 at the north edge, aspect ratio and x position searched (1716 x 1640 and 2024 x 1390 in
  the final runs; 1500 x 1876 as well in the pre-review runs, never the best).
- Never relaxed: 10 um halo per block (25 um around spirals, 4 um around leaf cells), the 23 keep-away rules of v6
  (digital to ADC 210 um, to LNA 1000 um, to QVCO 300 um; rings to QVCO 500 um; PA to LNA / ADC; capture to ADC 200 um ...).
- Relaxed only if nothing else is feasible, and then reported: island switch within 150 um of the core ring and
  600 um along the ring from its supply pad (G4); blocks above 20 mA within 500 um of their switch (G6).
- Decap bank: 26 tiles of 125 x 120 um that must lie within 250 um of the macro.
- Search: three placement orders (area-descending; giants then flow list; flow list first) per macro shape; the two
  baselines also with random order jitter (12 trials), the variants 6 trials. The best run is the one with the least unplaced area, then fewest relaxations, then
  lowest flow cost. One thread, 9 s per trial.

Self-checks (`python3 packer.py`, all pass; log `run/selftest.log`):

| case | by hand | packer |
|---|---|---|
| four 50 x 50 in 100 x 100 | exact fit, scrap 0 | 4 placed, free 0 |
| three 80 x 40 in 120 x 80 | fits only if one is rotated to 40 x 80 | 3 placed (one rotated), free 0 |
| 100 x 40 and 40 x 60 in the L left by a fixed 60 x 60 obstacle | exact fit | 2 placed, free 0 |
| five 50 x 50 in 100 x 100 (over-full by area) | one must stay out | 4 placed, 1 reported unplaced |
| two 60 x 60 in 100 x 100 (area fits, geometry does not) | only one fits | 1 placed, 1 unplaced, free 6400 |
| two 20 x 20 that must be 55 apart, strip 100 long / 80 long | possible (max 60) / impossible (max 40) | placed 60 apart / unplaced "keep-away" |
| load that cannot be within 5 of its switch | must be placed with the violation named | placed, relaxation recorded |

Every chip run is also checked by an independent pairwise rectangle test (no overlap, all inside the core): no errors.

### 3.2 Results (ledger v2)

"Blocks to place" excludes pads, macro and fixed reserves. "Unplaced" is what does not fit; "usable" is free area that
can still take a block of 60 um or more.

| run | scenario | options | core | blocks to place mm2 | placed | unplaced n / mm2 | channels (halo) | free left | of it usable >= 60 um | relaxed | macro | trials |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|
| b | B | baseline | 12.772 | 8.273 | 211 / 6.132 | 25 / **2.141** | 0.815 | 0.347 | 0.0 | wiredtx, ptrim | 2024 x 1390 | 12 |
| c | C | baseline | 12.772 | 7.518 | 214 / 6.171 | 20 / **1.347** | 0.874 | 0.363 | 0.0 | wiredtx | 2024 x 1390 | 12 |
| cr | CR | baseline | 12.772 | 7.681 | 214 / 6.071 | 20 / **1.61** | 0.86 | 0.43 | 0.024 | wrx_cap, wiredtx, lna, ptrim | 2024 x 1390 | 6 |
| b-flow | B | flow-first order only | 12.772 | 8.273 | 225 / 5.551 | 11 / **2.722** | 0.932 | 0.81 | 0.244 | rfdriver, wrx_cap, wiredtx | 2024 x 1390 | 6 |
| c-flow | C | flow-first order only | 12.772 | 7.518 | 224 / 5.572 | 10 / **1.947** | 0.94 | 0.895 | 0.304 | rfdriver, wrx_cap, wiredtx | 2024 x 1390 | 6 |
| b-h5 | B | halo 5 | 12.772 | 8.273 | 213 / 6.551 | 23 / **1.722** | 0.453 | 0.354 | 0.0 | wiredtx, lo_mmd, lna, ptrim | 2024 x 1390 | 6 |
| c-h5 | C | halo 5 | 12.772 | 7.518 | 220 / 6.475 | 14 / **1.043** | 0.487 | 0.51 | 0.0 | wrx_cap, lo_mmd, ptrim | 2024 x 1390 | 6 |
| c-l1 | C | debug pads on provider cells | 12.772 | 7.518 | 209 / 6.506 | 25 / **1.012** | 0.907 | 0.399 | 0.0 | wiredtx, ptrim | 2024 x 1390 | 6 |
| c-l2 | C | debug pads on provider cells, no bank | 12.772 | 7.128 | 186 / 6.452 | 22 / **0.676** | 0.95 | 0.433 | 0.0 | wiredtx, rfdriver, lna, ptrim | 1716 x 1640 | 6 |
| c-l3 | C | debug pads on provider cells, no bank, ring +36 | 13.299 | 7.128 | 199 / 6.812 | 9 / **0.316** | 1.001 | 0.403 | 0.0 | wiredtx, rfdriver, ptrim | 2024 x 1390 | 6 |
| c-l4 | C | halo 6, debug pads on provider cells, no bank, ring +36 | 13.299 | 7.128 | 205 / 6.904 | 3 / **0.224** | 0.66 | 0.706 | 0.161 | wiredtx, rfdriver, ptrim | 2024 x 1390 | 6 |
| c-l5 | C | halo 6, debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out | 13.299 | 6.905 | 204 / 6.837 | 2 / **0.068** | 0.68 | 0.769 | 0.136 | wiredtx, ptrim | 1716 x 1640 | 6 |
| c-l5-flow | C | halo 6, debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out, flow-first order only | 13.299 | 6.905 | 202 / 6.003 | 4 / **0.902** | 0.657 | 1.612 | 1.108 | wrx_cap, wiredtx | 2024 x 1390 | 6 |
| cr-l5 | CR | halo 6, debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out | 13.299 | 7.068 | 202 / 6.878 | 4 / **0.19** | 0.659 | 0.749 | 0.169 | wiredtx, ptrim | 1716 x 1640 | 6 |
| b-l5 | B | halo 6, debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out | 13.299 | 7.66 | 191 / 7.171 | 17 / **0.488** | 0.595 | 0.451 | 0.0 | wrx_cap, wiredtx, lo_mmd, lna, ptrim | 1716 x 1640 | 6 |
| c-l6 | C | debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out, qdum + lo_obs in the QVCO slot | 13.299 | 6.877 | 195 / 6.686 | 9 / **0.191** | 1.033 | 0.514 | 0.0 | wiredtx, ptrim | 1716 x 1640 | 6 |
| cr-l6 | CR | debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out, qdum + lo_obs in the QVCO slot | 13.299 | 7.04 | 195 / 6.779 | 9 / **0.261** | 1.005 | 0.431 | 0.014 | wiredtx, rfdriver, ptrim | 2024 x 1390 | 6 |
| b-l6 | B | debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out, qdum + lo_obs in the QVCO slot | 13.299 | 7.632 | 178 / 6.821 | 28 / **0.81** | 0.925 | 0.422 | 0.0 | wrx_cap, wiredtx, lo_mmd, ptrim | 1716 x 1640 | 6 |
| b-g500 | B | die +500 um tall | 14.286 | 8.273 | 222 / 7.06 | 14 / **1.214** | 0.956 | 0.769 | 0.161 | wrx_cap, wiredtx, lna, ptrim | 1716 x 1640 | 6 |
| b-g700 | B | die +700 um tall | 14.892 | 8.273 | 226 / 7.656 | 10 / **0.617** | 1.048 | 0.67 | 0.061 | wrx_cap, wiredtx, rfdriver, lna, ptrim | 1716 x 1640 | 6 |
| b-g900 | B | die +900 um tall | 15.497 | 8.273 | 230 / 8.044 | 6 / **0.229** | 1.088 | 0.833 | 0.267 | wrx_cap, wiredtx, lo_mmd, rfdriver, lna, ptrim | 1716 x 1640 | 6 |
| b-g1100 | B | die +1100 um tall | 16.103 | 8.273 | 236 / 8.273 | 0 / **0.0** | 1.158 | 1.105 | 0.412 | wrx_cap, wiredtx, lo_mmd, ptrim | 2024 x 1390 | 6 |

Images: `die-fit/run/fit-b.png` (scenario B), `fit-c.png` (scenario C), `fit-cr.png`, and one per variant
(`fit-c-l6.png` is the lever stack, `fit-b-g1100.png` the die at which B places).

Reading:
- **B does not fit: 25 blocks, 2.14 mm2, stay out, and the 0.35 mm2 left free is slivers below 80 um.** Unplaced in
  the best run: both captures (0.29 each), pll_vreg2, CDR ring, lo_mmd, a DAC, and smaller ones. With their channels
  the shortfall is 2.3 mm2.
- **C does not fit either: 20 blocks, 1.35 mm2** (1.5 with channels). Cr: 1.61 (1.75).
- The macro's aspect ratio is not a lever: best results for 1716 x 1640 and 2024 x 1390 differ by less than 0.1 mm2.
- Honouring signal flow and supply adjacency (flow-first order) leaves 0.6 mm2 more unplaced than the densest packing
  (B 2.72, C 1.95), because the pad-pinned chains fragment the space before the large blocks arrive. A hand floorplan
  will do better than this heuristic, but not for free: the densest packings above scatter the chains (slicer away from
  the HS pad, LNA placed last), so they are lower bounds on the shortfall, not buildable plans.
- Halving the channels (5 um halo) recovers only 0.3-0.4 mm2 and contradicts 2.2.

### 3.3 Binding constraints (what the packer ran into, in order of cost)

1. Area. Every baseline run ends with zero usable free area; nothing else matters until about 1.5-2.3 mm2 is found.
2. The east and west core edges are 48-50 % pad (2.04 and 2.11 mm of 4.22 mm); the pads reach 487 um into the core. All
   pad-pinned blocks compete for the 20 um to 500 um wide gaps between them.
3. Capture: two 1211 x 243 um cells that must sit near the slicers and the HS pad and at least 200 um from both ADCs.
   They are unplaced in most B runs for the keep-away, not for area.
4. Island switches: eight of ten are pinned to a 1.2 mm stretch of ring edge at their supply pad; `wired_tx` has no
   legal place within 500 um of its 37 mA load (relaxed in every run), `ptrim` / `wrx_cap` / `lna` / `lo_mmd` /
   `rfdriver` each lose the 500 um rule in some runs.
5. Digital keep-aways: LNA 1000 um from the macro, ADC 210 um, QVCO 300 um. With the macro on the north edge the whole
   RF RX front end has to live south of y = 2100 um on the west side, where `lod`, `rf_rx`, the bbfilters and the ADCs
   also want to be.
6. The decap bank occupies the first 130 um around the macro; that band was dead for the ADCs anyway, but not for
   the wired blocks and core_bias.
7. Spirals: six (QVCO, four LNA spirals, T-coil) with a 25 um ring; the four LNA spirals are the blocks most often left
   unplaced among the small ones, because they come late and need 190-290 um squares next to the LNA.

## 4. Verdict

**Not everything fits. The coordinator's "short by about 1.5 mm2 after all staged repacks" is too optimistic: with
everything staged published as measured (B) the die is short by 2.1-2.3 mm2 in the densest packing found, and by about
2.9 mm2 when signal flow and the supply rules are honoured. Even with every repack target met (C) it is short by
1.3-1.5 mm2.**

| mm2 | A published | B staged | C targets | Cr backed targets |
|---|---:|---:|---:|---:|
| core | 12.772 | 12.772 | 12.772 | 12.772 |
| ledger demand (section 1) | 15.851 | 13.345 | 12.480 | 12.690 |
| raw margin | -3.08 | -0.57 | +0.29 | +0.08 |
| channels: 10 um halo on every block (measured 13-14 % of placed block area) | -1.10 | -1.00 | -0.99 | -1.00 |
| fixed corridors (D2H north-south 0.129, LO legs 0.043) | -0.17 | -0.17 | -0.17 | -0.17 |
| macro halo, pad side-pin channels | -0.06 | -0.06 | -0.06 | -0.06 |
| packing scrap (measured, densest packing: slivers below 80 um) | -0.35 | -0.35 | -0.36 | -0.43 |
| **margin, arithmetic** | **-4.8** | **-2.15** | **-1.29** | **-1.58** |
| **shortfall, packer** (unplaced + its channels) | not run | **-2.3** | **-1.5** | **-1.75** |
| the same with flow-first order | | -2.9 | -2.1 | |
| not included above, risks: | | | | |
| routing beyond what the channels give (2.2) | | 0 to -0.8 | 0 to -1.0 | |
| decap: tiles to replace grid MIM that the repacks removed (2.4) | | -0.15 to -0.40 | -0.22 to -0.47 | |
| island-local decap not shown to exist | | 0 to -0.29 | 0 to -0.29 | |
| grid: unmeasured blocks that do not let the mesh cross | | Metal4/5 only, no core area | | |

Why it differs from the 1.5 mm2 tally: the tally did not have the QVCO regulator at its real size (+0.30), the
characterization cells (+0.41), the published WMON pad (+0.05), the corridors (+0.17) or measured scrap, and it did not
know that the pads were over-booked by 0.28.

Scenario A is 0.67 better if the R8-ARCH second capture is booked at the 0.29 reserve of record instead of the
published r6 master; it does not change the picture.

**For information only (the die is fixed):** scenario B places completely, densest packing, with four supply-distance
relaxations, when the die is 1.10 mm taller: **3.932 x 6.222 mm = 24.5 mm2 (+21 %)**, core 16.10 mm2
(`run/fit-b-g1100.json`; +0.9 mm leaves 0.23 mm2 out, +0.7 mm 0.62, +0.5 mm 1.21). With the flow-first order 0.79 mm2
is still out at +1.1 mm; extrapolated, a flow-honouring B needs about +1.5 mm (about 26 mm2). Scenario C by the same
slope (0.30 mm2 of core per 0.1 mm) needs about +0.5 mm (22.1 mm2); extrapolated, not run.

## 5. Remaining levers, ranked (sizes in core mm2; "packer" = measured on scenario C as cumulative runs)

| # | lever | size | packer: C unplaced | cost / condition | owner |
|---|---|---:|---:|---|---|
| | C baseline | | 1.35 | | |
| 1 | AP4-7: BB_I, BB_Q, WMON on provider `asig_5p0` cells (no core intrusion) | 0.40 (C), 0.45 (B) | 1.01 | debug / fallback-RX bandwidth and HBM screen on the provider cell; three provider sites | pads, rf_rx |
| 2 | no dedicated decap bank in the core | 0.39 | 0.68 | total decap 5.4 -> 3.9 nF or less (2.4); power-delivery.md says the plan already closes without margin; alternatives: 2.0 nF of 3.3 V tiles consolidated in the macro's free sites (digital routing does not converge at 66 % today), or bond-site tiles 0.45 -> 1.15 nF if the pad escapes move | power delivery, digital |
| 3 | AP4-10b core ring 2 x 25 -> 2 x 12 um (core edge out by 36 um) | 0.38 net of pad fronts (0.53 gross) | 0.32 | EM at 85 C and IR rerun; power-delivery.md G8 puts the cost at 0.5-0.9 mV | assembly, power delivery |
| 4 | characterization probe frames: OPEN and SHORT out of the core (0.224), or all three drawn tighter (430 x 260 -> about 300 x 200: 0.15) | 0.15-0.22 | 0.19 (with 5) | de-embedding accuracy of the fT/fmax measurement, or owner relayout; frames could also share one set of GND pads | characterization |
| 5 | QVCO corner slot A for staged `lo_mmd_qdum` + `lo_obs` (slot B for the second lo_obs) | 0.03-0.04 | (in the 0.19) | supply/substrate lines of LO-coherent neighbours at 25 um from the tank are not quantified (lo-ap4 NOTES) | LO, assembly |
| 6 | AP4-6b: ESD diode rows under the provider rail band of each custom bond | 0.15-0.19 | not run (pad redesign) | pad generator rework, full requalification (HBM, pad C, return loss) | pads |
| 7 | ADC SAR logic: abutted / shared guard rings | 0.07 each, 0.14 | B only (C already assumes 0.33) | generator rewrite, INL/ENOB re-extraction; the owner's two cheaper attempts failed | converters |
| 8 | X5: TMDS legs onto MAIN, delete steer_4/5 | 0.04 + 0.017 (the 0.017 is already in C) | | MAIN leg must tolerate the 3.3 V pull-up | wired TX, pads |
| 9 | AP4-6a pad attachment repack | 0.063 (was claimed 0.19; in C) | | generator rework, requalification | pads |
| 10 | WMON: draw the 205 um B cell (if lever 1 fails) | 0.047 (in C) | | new pad cell, requalification | pads |
| 11 | QVCO regulator: external capacitor instead of 62 on-chip cap units | up to 0.15 | | one pad site (none is spare) and a board part; or a relaxed spur limit (-61 instead of -80 dBc: power-delivery.md 5.1) | LO, user |
| 12 | halo 10 -> 6 um | 0.35 nominal, 0.09 in the packer | 0.32 -> 0.22 | contradicts 2.2: channels are already 0.25-0.45 mm2 short; only with wiring over blocks | assembly |
| 13 | macro aspect ratio | 0 | no effect | | |
| 14 | macro utilisation 67 -> 75 % | 0.29 | | not available: routing does not converge at 66 %, and the macro still gains glue, clamps and control | digital |
| 15 | MIM over blocks | no area | | a decap source, 1.1-1.4 nF after the repacks (2.4), not an area lever any more | power delivery |
| 16 | static control through local shift registers at the big consumers (slicer, core_bias, bbfilter, ptrim: 275 of 531 bits) | routing only: about a third of the channel need | | reverses "decode glue lives in the macro" for those blocks | digital, block owners |

Stack on C at the 10 um halo (levers 1-5, run `c-l6`): **0.19 mm2 still unplaced** in the densest packing, 0.83 in the
flow-first order. Adding 6 and 8 brings C to about zero, with no margin for the risks of section 4. On Cr the same
stack leaves 0.26, on B 0.81 (`cr-l6`, `b-l6`). B needs the whole B -> C step as well (ADC 0.45 -> 0.33, both
bbfilters, core_bias, detect, CDR ring, TX ring, term_buffer, pad attachments: 0.87) of which 0.21 is declared
unreachable by the owners (Cr).

### 5.1 Needs a user decision (not levers this study may take)

1. **The fixed die against full scope.** After every owner-level lever (1-10) scenario C closes at about zero and the
   backed-target scenario Cr is 0.1-0.3 short, before routing and decap risk. The die at which B fits is 24.5 mm2
   (section 4). Stated for information.
2. **Decap bank or ripple limit** (power-delivery.md decision 2, now sharper): the bank costs 0.39 mm2 and the repacks
   removed 1.6-1.9 nF of the grid MIM the plan relied on.
3. **OPEN / SHORT de-embedding frames in the core** (0.224): keep, shrink, or accept a less accurate device-speed
   measurement.
4. **Debug / fallback pads**: BB_I, BB_Q (also the fallback-RX path) and WMON on provider cells (lever 1) changes their
   bandwidth and protection; WTX_EXT pair + receiver + fallback control (0.18) is a pure fallback.
5. **Reserves for what is not demonstrated**: R8-ARCH second slicer + capture + blenders (0.44) and the eighth-rate TX
   reserve (0.22). Both are booked in full here because the mandate keeps the rates; neither is closed in simulation.
6. **QVCO regulator**: 0.30 mm2 on chip, or an external capacitor on a pad site that is not free, or a relaxed spur limit.
7. **Supply-pad assignment of `lod`, `pll`, `wired_tx`** (2.3): the floorplan cannot satisfy G4/G6 and signal flow
   together; either the islands are re-cut or longer straps (Metal5 that the grid also needs) are accepted.
8. **Channels**: route the 531 static control wires over blocks (owners must free a layer) or pay 0.25-0.45 mm2 more
   channel area than any floorplan so far has booked.

## 6. Independent review of the ledger (`die-fit/review.md`)

One reviewer (separate agent, read-only) tried to break ledger v1. The arithmetic and the no-double-count checks held
(pad intrusions, staged cells, tx8 sum, island switches 0.426, LEF sizes, decap bank). Corrections taken into v2:

| ID | finding | A | B | C |
|---|---|---:|---:|---:|
| R1 | `pt_lo_vreg` 0.12 not defensible: the LO owner's regulator schematic has about 0.24 mm2 of bare devices -> 0.30 (0.25-0.38) | +0.180 | +0.180 | +0.180 |
| R3 | RF RX "published" was the uncommitted working tree: HEAD is lna 78k, rxmix 76k each, bb_tap 10k | +0.107 | 0 | 0 |
| R4 | `h2d_gearbox_rsv` books nothing (H2D capture flops are in the macro top rows) | -0.093 | -0.031 | -0.031 |
| R6 | `steer_0..3` double counted with the CML pre-drivers in `tx8_rsv`; steer_4/5 unused | -0.035 | -0.035 | -0.052 |
| R9 | capture target 0.290 is below the staged r7c 0.294 (two instances) | 0 | 0 | +0.008 |
| R10 | refvcm, txpad_bias, bias taps have staged layouts (7.4k, 12.5k, 2 x 2.2k) | +0.009 | +0.009 | +0.009 |
| R11 | supply/clock monitor is RTL; only a time base and a clock-present detector stay outside | -0.015 | -0.015 | +0.005 |
| R12 | allowance for LNA tail / gate R / damping, D-EXTCLK selector, FLL driver | +0.010 | +0.010 | +0.010 |
| | **net** | **+0.163** | **+0.118** | **+0.129** |

Handled differently from the reviewer's proposal:
- R2 (ADC 0.33 unreachable, floor 0.35) and R7 (CDR ring 0.127 is not an assigned target), plus the flags on
  `pt_detect` 0.09 and the undrawn WMON cell: C is kept as defined ("all targets met") and scenario **Cr** was added
  with the backed values (+0.21 over C).
- R5 (qdum + lo_obs inside the QVCO outline, -0.028): kept as lever 5, not taken in the ledger, because nobody has
  placed them there and the coupling is not quantified.
- R8 (A books the second capture on r6): kept, stated as a definition with its size (0.667).
- Not corrected, flagged by the reviewer and repeated in 1.1: island-local decap 1.16 nF assumed inside the blocks;
  `d2h_gearbox_rsv` should be renamed (it is the hand-placed D2H output strip / pad repeaters).

## 7. Files

- `die-fit/ledger.py`, `ledger.csv`, `ledger.md`, `ledger.json`: the ledger (v2).
- `die-fit/m45free_staged.py/.json`, `padnotch.py/.json`: the two layout measurements.
- `die-fit/packer.py` (engine + self-checks), `fit.py` (chip scenarios, report, render), `variants.sh`, `runset.sh`.
- `die-fit/run/fit-<tag>.json/.png`, `run/summary.md`, `summary.json`; `run/v1/` pre-review B and C.
- `die-fit/overheads.py`, `overheads.json`: net counts, routing, grid and decap derivations.
- `die-fit/review.md`: the independent review.

Not done / limits: no GDS assembly, no router, no DRC; outlines are rectangles; wire lengths are Manhattan estimates;
the packer is a constructive heuristic (a lower bound on what a hand floorplan can place is not proven, only the area
arithmetic is); scenario A was not packed; the C-target Metal4/Metal5-free areas are estimates, B's are measured.
