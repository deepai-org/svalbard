# Die-fit study (2026-11-14)

Question: can everything the chip now needs be placed, powered and routed on the fixed 3.932 x 5.122 mm die
(core 3028 x 4218 um = 12.772 mm2)? If not, by how much does it miss and what are the options?

Paper/script study. No circuit simulation, no design file changed. Work dir `scratch/reviews/die-fit/`.
Two light KLayout read-only measurements were run (one job, one thread each): Metal4/Metal5-free area of the staged
layouts (`m45free_staged.json`, controls reproduce area pass 4 to the last digit) and the real footprint of the USB and
wired-TX pads (`padnotch.json`).

STATUS: ledger v2 (reviewer's corrections applied) is final; sections 2-5 are being filled as the packing runs finish.

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

## 2. Supply, routing and decap overheads (derived)

(filled in below)
