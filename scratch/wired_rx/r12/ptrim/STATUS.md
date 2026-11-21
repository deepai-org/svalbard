# r12/ptrim: pt_ptrim r12 for the RX ring pt_pll_ring r12 (TIM-17, TIM-19, WR11-5) -- sub-agent status

Started 2026-11-20.  Base: staged r10 "l8" (scratch/wired_rx/r10ptrim/final/gen, W/ptrim.spice, W/netlists.ptrim()).
Staging only here; analog/wired_rx/generated/ is not written.  Every ngspice / Magic job through ../../slot.sh.
Ring: /home/ubuntu/svalbard/scratch/timing/ring12/rx_r12.ext.spice (C-only extraction, flat; the ring stays C-only in
every bench here: stated, not R-aware).

## 0. Gates (declared 2026-11-20 BEFORE any r12 result; not to be relaxed)
Definitions.  Bench = cal.py pattern: the r12 ring (open loop, VCTRL searched to f0 +-0.5 %, settled run) drives the ptrim
through 30 ohm + 63 fF per phase (63 fF + the ptrim input ~54 fF = the 117 fF per phase of TIM-19), ptrim into the lumped
real consumer loads (r10 bench.PIN, +20 fF wordclk on CKP0, route LOW); one settled period of v(PH0..7) at the ptrim pins
is replayed as periodic PWL into the DUT (r10 ringreal.py / rr2.py method).  Position = CKPk rising VDD/2 crossing against
the k*T/8 grid, common offset free.
Points (28): corners tt/27/3.30, ss/32/3.15, ss/32/3.50, ff/22/3.35, sf/27/3.15, fs/27/3.15, slow-pessimistic (r7slicer
pess.py on the ptrim netlist, lumped loads x1.15, ss/32/3.15, ring waveform = the nominal ss/3.15 ring: the ring is not
pessimised) x rates 480 / 625 / 675 / 810 MHz.  Ring supply VRING as timing ring12 (tt 2.95, ss315 2.69, ss350 3.02,
ff 3.01, sf/fs 2.82); 480 MHz on band 0, the others band 1.
* G1 coverage: need = (max - min of the eight CKP code-0 positions measured in the bench) + 4 ps sampler-path spread
  (TIM-19) + 10 ps die-mismatch allowance (ASSUMPTION, not simulated: no Monte Carlo in this flow); range = the smallest
  channel's (code 31 - code 0) position change in the same bench.  PASS iff range >= 1.25 x need at every point.
* G2 residual: with the solved codes, measured in a run WITH those codes, peak-to-peak of the eight CKP rising positions
  <= 3.0 deg of the ring period (AC-3).
* G3 monotonic / step: real-ring code curve monotonic at every point (9-point curve 0,4,..,28,31); full 32-code curve
  monotonic with max step <= 1.0 deg at f with the ideal 50 % source at ss/3.15/810, ss/3.50/810, pess ss/3.15/810,
  tt/625, ff/810 (r10 C2), and with the real ring table at ss/3.15/810.
* G4 r10 criteria C1 (levels), C4 (duty 45-55 %, change <= 3 % of T over the codes), C5 (20-80 % <= 150 ps) with the ideal
  source at the G3 sweep points, unchanged from r10.
* G5 current: supply current at the solved codes not above l8's at its own solved codes in the same bench, at ss/3.15/810,
  ss/3.50/810 and pess ss/3.15/810 ("do not increase").  Code-0 and all-31 currents reported (no limit).
* G6 layout: Magic DRC 0 (cells + top), KLayout precheck main 0 and antenna 0; LVS of the GDS READ BACK FROM DISK against
  W/ptrim.spice (= netlists.ptrim().emit()): "Circuits match uniquely" AND no property errors; negative controls (one
  device width +10 nm; one gate moved to another net) must both fail.
* G7 R+C: Magic extresist on the flattened read-back GDS with `extresist tolerance 0`, `extresist simplify off`, C
  cthresh 0 (RCOV.md recipe).  Coverage reported = resisted nets / non-supply nets with more than one tile (and supply
  handling stated).  Declared threshold: 100 % of the clock-path nets (PHk, tnk, tak, tbk, CKPk, tc*) of every channel
  either resisted or single-tile; overall resisted share reported.  The G1/G2/G3 tables are produced on the R+C netlist.

## 1. Log
* G6 addition (2026-11-20, coordinator rule ASM-8, received before any r12 layout result): Metal5 kept free (VSS / VDD straps
  Metal4 only, pins on Metal4; the chip grid lands with via4).  Reported: Metal5 area used (um2, % of outline) - must be 0 -
  and whether Metal4 crosses grid strap positions.
* Calibration (cal12.py, DUT = l8 C-only extraction, the r12 ptrim has the same NAND inputs): 24 tags (6 corners x 4 rates),
  every frequency within 0.5 % of f0; table wrap step <= 0.015 V (periodic).  Settling: last-six-period ptp 0.45-1.72 ps;
  cal.py's own 0.5 ps flag is met only by fs810 (TIM-19 used < 1.0 ps: 18 of 24 meet that; ff480 1.72, tt480 1.37,
  sf480 1.23, ss315480 1.17, ff625 1.15, fs675 1.07, ss350625 1.03 ps do not).  Stated, not hidden: about +-1 ps on positions.
* l8 baseline on the r12 ring (rr12.py, res/l8_*.json, 28 points): G2 residual passes everywhere (<= 0.85 deg), but G1 FAILS at
  11 of 28 points (ratio 0.99-1.25; worst ssp315 810 MHz: need 69.1 + 14 ps vs range 82.6 ps).  r10 would not have been enough.
* Decision (by numbers, pickfix.py on the l8 code curves): FIXED per-channel offsets, not widening.  FIX = [0,2,4,5,0,4,8,8]
  bit-4-type unit pairs (~2 LSB each), predicted worst G1 ratio 1.70 (ff480); [1,3,5,6,0,5,9,9] predicted 1.72 but widens
  the block by 9.9 um (channel 0 row), so the variant with channel 0 at 0 was taken.  Widening was not pursued: >= 100 ps at
  <= 1 deg step needs a 6th bit (ports + register change) and more trim C (current).
  Fixed units are laid out as wide fingers (n units -> W n x 0.595 / n x 0.6 um, split at 4.8 um), same cap/switch W ratio.
* Layout (final12.py -> final/): Magic DRC 0, KLayout precheck main 0 / antenna 0, LVS unique without property errors from
  the GDS read back (vs W/ptrim.spice), negative controls fail (width +10 nm -> property errors; gate moved -> pin mismatch).
  200.11 x 235.2 um = r10 outline, area delta 0.  Metal5 area 0 (STRAP_M5 = False, straps Metal4 only, pins on Metal4);
  Metal4 = 2448 um2 at x 184.3-198.5 um, full height (ptrim_en strap + VSS / VDD straps).
* R+C (rc12.py -> rc/final/): extresist tolerance 0 / simplify off, supplies resisted too; 10 882 resistors on 159 nets;
  non-supply nets resisted 157 / 173 (90.8 %), the 16 others are single-tile NAND series nodes; clock-path nets 116 / 116
  resisted (G7 PASS); per-net C rc vs C-only 0.999999-1.000001 (mkrc.py: C-only capacitors, the extresist C not used).
* 1st coverage queue failed: ngspice out of memory on the flat R+C netlist (all node vectors kept).  savefix.py: `save` only
  the written vectors; queue restarted.
* C cross-check (ccheck.py, coordinator rule): 1359 coupling pairs ratio 0.999999-1.000002, 0 pairs only in the R+C netlist; 175 nets 0.999999-1.000001 (rc/final/ccheck.json).

## 2. Results on the R+C netlist (rc/final/ptrim.rc.spice; the ring stays the C-only r12 extraction) -- 2026-11-21
Coverage table (res/r12_*.json; need = measured code-0 spread + 4 ps sampler + 10 ps mismatch allowance):
| point | need meas + 14 ps | range min ps | ratio (>= 1.25) | residual ps / deg (<= 3) | mono | codes | idd solved mA (l8 solved) | G1 | G2 |
|---|---|---|---|---|---|---|---|---|---|
| ff480 | 31.5 + 14 = 45.5 | 77.49 | 1.703 | 3.1 / 0.536 | True | [17, 5, 13, 15, 14, 8, 15, 18] | 21.403 (21.662) | PASS | PASS |
| ff625 | 12.32 + 14 = 26.32 | 76.95 | 2.924 | 1.16 / 0.261 | True | [25, 22, 25, 27, 27, 25, 27, 28] | 28.518 (27.658) | PASS | PASS |
| ff675 | 10.47 + 14 = 24.47 | 76.68 | 3.134 | 1.34 / 0.326 | True | [1, 0, 2, 3, 4, 2, 3, 3] | 28.949 (30.598) | PASS | PASS |
| ff810 | 11.97 + 14 = 25.97 | 75.12 | 2.893 | 1.9 / 0.554 | True | [0, 2, 1, 3, 5, 4, 3, 1] | 34.496 (35.524) | PASS | PASS |
| fs480 | 26.48 + 14 = 40.48 | 95.57 | 2.361 | 2.97 / 0.513 | True | [13, 6, 13, 12, 14, 12, 15, 15] | 19.129 (18.965) | PASS | PASS |
| fs625 | 11.88 + 14 = 25.88 | 94.15 | 3.638 | 2.43 / 0.547 | True | [27, 27, 26, 28, 30, 30, 30, 28] | 25.556 (25.332) | PASS | PASS |
| fs675 | 13.49 + 14 = 27.49 | 92.77 | 3.375 | 2.18 / 0.53 | True | [22, 23, 21, 23, 26, 26, 26, 23] | 27.258 (27.312) | PASS | PASS |
| fs810 | 18.79 + 14 = 32.79 | 86.82 | 2.648 | 2.34 / 0.682 | True | [15, 18, 15, 16, 21, 21, 21, 18] | 31.979 (32.868) | PASS | PASS |
| sf480 | 16.44 + 14 = 30.44 | 82.8 | 2.72 | 1.13 / 0.195 | True | [23, 21, 23, 26, 26, 22, 25, 28] | 19.618 (19.508) | PASS | PASS |
| sf625 | 16.63 + 14 = 30.63 | 81.31 | 2.655 | 1.62 / 0.364 | True | [16, 20, 17, 20, 22, 20, 20, 19] | 25.085 (24.892) | PASS | PASS |
| sf675 | 17.93 + 14 = 31.93 | 80.03 | 2.506 | 1.82 / 0.442 | True | [25, 30, 26, 28, 31, 30, 29, 28] | 27.481 (27.0) | PASS | PASS |
| sf810 | 22.28 + 14 = 36.28 | 74.44 | 2.052 | 1.4 / 0.408 | True | [16, 24, 19, 20, 25, 24, 23, 21] | 32.209 (32.97) | PASS | PASS |
| ss315480 | 13.89 + 14 = 27.89 | 103.65 | 3.716 | 2.01 / 0.347 | True | [10, 10, 10, 10, 14, 13, 13, 11] | 18.684 (19.085) | PASS | PASS |
| ss315625 | 22.36 + 14 = 36.36 | 98.76 | 2.716 | 1.76 / 0.396 | True | [0, 5, 1, 2, 7, 6, 5, 2] | 23.784 (24.508) | PASS | PASS |
| ss315675 | 24.87 + 14 = 38.87 | 95.58 | 2.459 | 1.83 / 0.445 | True | [18, 24, 20, 20, 26, 26, 25, 22] | 26.418 (26.6) | PASS | PASS |
| ss315810 | 33.46 + 14 = 47.46 | 76.22 | 1.606 | 1.74 / 0.507 | True | [1, 8, 5, 4, 12, 11, 12, 11] | 30.581 (31.491) | PASS | PASS |
| ss350480 | 13.85 + 14 = 27.85 | 97.85 | 3.513 | 2.24 / 0.387 | True | [2, 1, 3, 3, 5, 3, 5, 4] | 20.932 (21.696) | PASS | PASS |
| ss350625 | 18.05 + 14 = 32.05 | 95.02 | 2.965 | 1.65 / 0.371 | True | [0, 4, 1, 2, 6, 5, 4, 1] | 27.023 (27.654) | PASS | PASS |
| ss350675 | 20.14 + 14 = 34.14 | 93.02 | 2.725 | 2.26 / 0.549 | True | [8, 13, 9, 10, 15, 14, 13, 10] | 29.597 (30.564) | PASS | PASS |
| ss350810 | 27.16 + 14 = 41.16 | 81.53 | 1.981 | 1.38 / 0.402 | True | [19, 27, 23, 22, 29, 29, 29, 29] | 36.017 (35.854) | PASS | PASS |
| ssp315480 | 23.44 + 14 = 37.44 | 120.92 | 3.23 | 2.2 / 0.38 | True | [22, 22, 20, 21, 26, 24, 23, 22] | 22.541 (22.398) | PASS | PASS |
| ssp315625 | 27.92 + 14 = 41.92 | 107.22 | 2.558 | 1.9 / 0.428 | True | [24, 29, 25, 24, 31, 31, 30, 28] | 29.108 (28.822) | PASS | PASS |
| ssp315675 | 30.07 + 14 = 44.07 | 100.14 | 2.272 | 1.11 / 0.27 | True | [15, 21, 17, 16, 23, 23, 22, 20] | 30.827 (31.722) | PASS | PASS |
| ssp315810 | 34.62 + 14 = 48.62 | 58.3 | 1.199 | 1.06 / 0.309 | True | [7, 13, 10, 9, 18, 18, 21, 31] | 35.955 (37.168) | FAIL | PASS |
| tt480 | 23.5 + 14 = 37.5 | 87.62 | 2.337 | 2.67 / 0.461 | True | [27, 20, 26, 27, 28, 24, 28, 29] | 20.883 (20.628) | PASS | PASS |
| tt625 | 12.19 + 14 = 26.19 | 86.5 | 3.303 | 2.08 / 0.468 | True | [25, 26, 25, 27, 29, 28, 28, 27] | 27.017 (27.003) | PASS | PASS |
| tt675 | 13.73 + 14 = 27.73 | 85.51 | 3.084 | 1.91 / 0.464 | True | [10, 12, 10, 12, 15, 14, 13, 11] | 28.196 (28.861) | PASS | PASS |
| tt810 | 18.39 + 14 = 32.39 | 80.87 | 2.497 | 2.43 / 0.709 | True | [12, 17, 13, 14, 19, 18, 17, 15] | 33.772 (33.965) | PASS | PASS |

* G1: 27 / 28 PASS.  **FAIL at ssp315 810 MHz: ratio 1.199** (range 58.3 ps on channel 7 vs 1.25 x 48.6 = 60.8 ps).  Cause:
  under the real ring at the pessimistic bound the code curve of channels 6 / 7 (FIX 8 each) compresses (ch7 range 58.3,
  ch6 78.7; same channel with the ideal 50 % source: 86 ps).  Solve still succeeds there (codes [7,13,10,9,18,18,21,31],
  residual 0.31 deg), but ch7 sits at code 31: no margin on that channel at that bound.
  Hypothesis test (fixed tn load of ch6/7 moved to ta, netlist edit) did not complete; not rerun (coordinator: finish).
* G2: 28 / 28 PASS (residual 0.20-0.71 deg, measured with the solved codes).
* G3: real-ring 9-point curves monotonic at all 28 points; real-ring 32-code curve at ss315 810: monotonic, max step 0.98 deg
  (3.36 ps) PASS.  Ideal-source 32-code sweeps (sweep.json): ss315 810 0.954, ss350 810 0.921, tt625 0.722, ff810 0.840 deg
  PASS; **pess ss315 810 FAIL: 1.041 deg (ch0), C4 FAIL (duty 0.438 < 0.45), C5 FAIL (ch0 edge 153 ps > 150)**.
  Attribution: the same layout C-only + pess passes (0.968 deg, duty 0.455, 124 ps); R+C with ideal supplies (rc/nosup)
  passes C2 (0.997) and C5 (128 ps) but still fails C4 (duty 0.447).  So C2 / C5 come from supply-strap resistance (Metal4-only
  straps after ASM-8 removed Metal5; the bench feeds VDD / VSS at the single pin label at the top, the chip grid will land via4
  at ~70 um pitch, so the bench is pessimistic but this is not shown), C4 from signal-path R.  l8 was never simulated R+C at the
  pessimistic bound, so whether r10 fails the same way is NOT known.  Channels 0 and 4 (no fixed units) fail too: the misses are not
  caused by the offsets.
* C3 (r10 criterion "usable = range - spread of the eight code-0 delays with an ideal 50 % source", fails on every S_* sweep):
  with deliberate fixed offsets that spread IS the offset pattern (by design ~45-70 ps), so C3 no longer measures anything;
  it is a bench-definition limit, not a defect, and is not one of the gates of section 0.  Coverage is G1 on the real ring.
* G4 at the ideal-source points: C1 PASS everywhere; C4 / C5 PASS except pess ss315 810 (above).
* G5 current at the solved codes, r12 R+C vs l8 C-only (NOT like-for-like: l8 was not R+C-extracted): ss315 810 30.58 vs 31.49 mA
  PASS, pess ss315 810 35.96 vs 37.17 PASS, **ss350 810 36.02 vs 35.85 mA: +0.17 mA FAIL as declared**.  Range over the table
  18.7-36.0 mA; ideal-source code 0 / 31: ss315 810 30.2 / 31.7, ss350 810 34.3 / 36.3, pess 35.3 / 36.7 mA.
* G6 PASS (section 1 log); Metal5 0 um2 (0 % of 47 066 um2); Metal4 2448 um2 at x 184.3-198.5 um, full height (vertical straps:
  they cross any horizontal grid strap row; whether they cross grid strap positions depends on placement, not checked here).
* G7 PASS: clock-path nets 116 / 116 resisted, 157 / 173 non-supply nets (16 single-tile NAND series nodes), supplies resisted.
* Area: 200.11 x 235.2 um, identical to r10 (delta 0).  Ports and the 5-bit trim are unchanged; no register change.
## 3. Open
* G1 at ssp315 810 (ch6 / ch7 compression), pess C2 / C4 / C5 on R+C (supply straps / signal R), G5 +0.17 mA at ss350 810.
  Levers, not tried: wider Metal4 straps (block +~10 um) or modelling the grid via4 landing; fixed load on ta only on ch6/7;
  NAND PMOS of ch6/7 stronger.  Calibration settling up to 1.7 ps at 480 MHz.  Not reviewed.
