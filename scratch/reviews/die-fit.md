# Die-fit study (2026-11-14)

Question: can everything the chip now needs be placed, powered and routed on the fixed 3.932 x 5.122 mm die
(core 3028 x 4218 um = 12.772 mm2)? If not, by how much does it miss and what are the options?

Paper/script study. No circuit simulation, no design file changed. Work dir `scratch/reviews/die-fit/`.
Two light KLayout read-only measurements were run (one job, one thread each): Metal4/Metal5-free area of the staged
layouts (`m45free_staged.json`, controls reproduce area pass 4 to the last digit) and the real footprint of the USB and
wired-TX pads (`padnotch.json`).

STATUS: sections 1 and 2 final except for the reviewer's corrections; sections 3-5 are being filled as the packing runs finish.

## 1. Demand ledger

Files: `die-fit/ledger.py` (generator), `ledger.csv` (one row per instance of `pt_chip.conn` at commit 4790054: 241
instances after CP4-1/2/3 and the ten-island change, plus 14 booked items), `ledger.md` (per master, with source and
confidence for every number).

Scenarios:
- **A** = published outlines only. Never-built items at their estimate. The R8-ARCH second capture is booked on the
  published r6 master (0.956), because that is what "nothing staged publishes" means.
- **B** = everything that is staged publishes as measured (bounding boxes of the staged GDS).
- **C** = every assigned repack target of area pass 4 is met, or the staged size where that is already smaller.
- The digital macro is 2.814 mm2 in all three: the digital owner states 2.45 is not reachable, and the macro still has
  to absorb the decode glue, 130 isolation AND2s, LO/CDR/USB control and decap row cells (cells 1.764 mm2 = 67.4 % today).
- Decisions CP4-2 (polyphase deleted) and CP4-3 (WCLK_IN pads and receiver deleted) are applied in all three, because
  the conn file already has them.

| category | items | A published | B staged | C target |
|---|---:|---:|---:|---:|
| digital macro | 1 | 2.814 | 2.814 | 2.814 |
| custom pads (true occupied core intrusion) | 11 | 2.252 | 2.164 | 2.054 |
| analog blocks that v6 / area pass 4 placed (incl. all ten island switches) | 196 | 8.042 | 6.371 | 5.629 |
| in the conn, in no floorplan or never built | 33 | 0.645 | 0.645 | 0.645 |
| booked, not in the conn (R8-ARCH, tx8, decap bank, gearboxes, T-coil, never-built additions) | 14 | 1.936 | 1.233 | 1.209 |
| **total demand** | 255 | **15.688** | **13.226** | **12.351** |
| core | | 12.772 | 12.772 | 12.772 |
| **raw margin** (before channels, corridors, scrap, extra decap) | | **-2.916** | **-0.454** | **+0.421** |

Confidence split of scenario B: 9.05 mm2 measured on published GDS/LEF (H), 3.57 mm2 measured on staged or v5 layouts
(M), 0.61 mm2 estimates (L).

### 1.1 What no floorplan had counted (scenario B, mm2)

| item | mm2 | source | confidence |
|---|---:|---|---|
| decap macro-edge bank (1.5 nF) | 0.390 | power-delivery.md 4.2 | M |
| characterization: three GSG probe frames 430 x 260 (`pt_char_rffet`, `_open`, `_short`) | 0.335 | char_rffet.lef | H |
| five more island switches (ten islands, 0.426 total against 0.236) | 0.190 | power-delivery.md 2, conn | H |
| QVCO regulator `pt_lo_vreg` (never built; 30 mA, 50-59 dB, 7 nV/rtHz) | 0.120 (0.08-0.25) | estimate from `pt_pll_vreg2` | L |
| characterization: `pt_char_atb`, `ro33`, `ro50`, `cmldiv` | 0.075 | LEF | H |
| LNA degeneration spirals x 2 | 0.050 | rf-lna-p NOTES | M |
| WMON pad: published cell is 302 um wide, floorplans book the undrawn 205 um B cell | 0.047 | util.json vs v5 floorplan | M |
| `pt_usb_txdrv` | 0.031 | USB-INTEGRATION.md | M |
| tx8 reserve overrun (serq8 built at 0.352, booking assumed 0.325) | 0.022 | wired_tx INTEGRATION.md 7 | L |
| supply/clock monitor (D-FAULT; 0 if `fault` is made in the macro, CP4-11) | 0.020 | CP4 estimate | L |
| 16 isolation clamps + 2 pull-downs left outside the macro | 0.016 | iso-placement.json | H |
| ptrim output stage (MW-14-FIX) | 0.015 | estimate | L |
| CTLE source follower x 2 (one per slicer bank) | 0.010 | wired_rx README Resume 9 | L |
| bias_ext, refvcm, txpad_bias, agnd_tie, VCM buffer, forwarded-clock repeaters | 0.023 | estimates | L |
| **sum** | **1.344** | | |

### 1.2 Double counting and over-booking found in the earlier floorplans

| item | effect | evidence |
|---|---:|---|
| USB pad (`pad_wirepad`) booked as its bounding box 521 x 1435. Beyond a depth of 913 um only a 188 um wide attachment column exists; the other 333 x 523 um is empty in every layer | -0.174 | `padnotch.json` (v5 floorplan had this notch, v6 and area pass 4 lost it) |
| TX pad (`pad_txpad`): column 139 um wide beyond 913 um; 342 x 312 um empty | -0.107 | `padnotch.json` |
| Consequence for lever AP4-6 (attachment repack): worth 0.063 mm2, not 0.19, because most of the "saving" was the notch | | |
| `lc_load_rsv` 0.10 in v6 is the LNA tank coil pair: must not be added to `pt_lna_ind` | (not added) | v6 inventory note RC-16j |
| Capture B in `r8arch_rsv` assumed the 0.29 compact master while capture A was still booked at 0.956; today neither is publishable | (A books both at 0.956) | wired_rx README Resume 9 |
| CP4 inventory total 13.74 counted 146 clamps outside the macro (0.135); 130 are now AND2 in the macro | -0.119 | conn commit 0006a99 |
| CP4 inventory counted pads as full-width x (depth - 442); the core starts at 452 and the wirepad/txpad are L-shaped | see above | |

Reviewer corrections to this ledger: section 6.

## 2. Supply, routing and decap overheads (derived)

(filled in below)
