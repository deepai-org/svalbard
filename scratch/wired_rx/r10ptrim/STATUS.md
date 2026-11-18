# r10ptrim: pt_ptrim redesign for the real clock loads (MW-14) + compact layout (AP4-1) -- sub-agent status

Started 2026-11-14.  Nothing here is published; nothing in W/generated/ is touched.  All ngspice through
`scratch/wired_rx/slot.sh` (1 slot).  Scripts in this directory: pinload.py (static pin C), bench.py (bench library + CLI).

## 1. Loads (re-measured 2026-11-14)  -- DONE
Static sum over the flattened C-only Magic extraction (pinload.py; wiring = every extracted C with one terminal on the pin
net, gate = W*L*4.37 fF/um2 + 2*W*0.30 fF/um for every gate on the net; no S/D on any CKP net):

| pin | capture r7c wiring / gate (um W) | slicer wiring / gate (um W) | sum fF |
|---|---|---|---|
| CKP0 | 597.3 / 160.5 (88) | 98.4 / 109.4 (60) | 965.6 |
| CKP1 | 194.8 / 21.9 (12) | 76.9 / 94.8 (52) | 388.4 |
| CKP2 | 260.3 / 43.8 (24) | 62.7 / 94.8 (52) | 461.6 |
| CKP3 | 188.6 / 21.9 (12) | 62.8 / 94.8 (52) | 368.1 |
| CKP4 | 223.7 / 43.8 (24) | 115.9 / 94.8 (52) | 478.2 |
| CKP5 | 206.0 / 21.9 (12) | 111.1 / 94.8 (52) | 433.8 |
| CKP6 | 199.3 / 21.9 (12) | 104.7 / 94.8 (52) | 420.7 |
| CKP7 | 192.0 / 21.9 (12) | 93.9 / 94.8 (52) | 402.7 |

* Sources: scratch/wired_rx/r7cap/r7c/gen/wrx_cap.ext.spice (r7d scratch/wired_rx/r10cap/r7d/gen/wrx_cap.ext.spice gives
  IDENTICAL CKP numbers), W/generated/slicer.ext.spice.  Records: pin_cap_r7c.json, pin_cap_r7d.json, pin_slicer.json.
  Same as r9 (965 / 371-482): the r7c/r7d capture did not change the CKP wiring.
* Capture CKP0 = the capture's main clock: 30 gates (16 n x 2 um, 14 p x 4 um) in wc_front0 (14), wc_front1 (12), wc_ctl (2),
  wc_pd (2); wiring 597 fF = top 163.5 + front1 145.8 + front0 127.1 + pd 81.3 + ctl 79.5.  CKP1..7: 4-8 gates, wiring 189-260 fF
  (of which 36-50 fF is CKPi-to-CKPj coupling inside wc_front1).
* Also on CKP0 at chip level (integration/top/decisions.md D-WORDCLK): `wordclk_rx.CK` (one NAND input, 4 um of gate +
  wiring, ~15-20 fF; tap PH0-vs-CKP0 still open in PINS.md).  Counted as +20 fF on CKP0.
* Top-level route bound (ring -> ptrim -> slicer + capture): no chip-top floorplan fixes these blocks yet, so this is an
  ASSUMPTION: LOW = 30 fF, 0 ohm (ptrim abutting both consumers, ~100-150 um per phase); HIGH = 150 fF with 40 ohm in
  series (about 600-700 um of >= 1 um wide upper metal to the far consumer; a 0.4 um Metal2 route of that length would be
  ~135 ohm and is NOT covered).  Ring -> ptrim input route: 30 ohm / 60 fF (the wired TX realring bench value) for the
  MW-31 benches.  Assembly must keep the CKP routes inside the HIGH bound and matched (row ASM below).

## Bench proof (bench.py) -- DONE
* Known answer reproduced (r9ptrim/load.json new_tt_hi: r9 compact extraction, 965 fF..., 150 fF route, tt, 625 MHz):
  code 0 CKP0 0.584-2.742 V (known 0.58-2.74), delays 642.05 / 554.29 / 576.95 ps (642.2 / 554.3 / 576.9), 13.00 mA (13.0);
  code 31 606.43 / 642.37 / 654.39 (606.7 / 642.3 / 654.4).  Log repro.log.
* Negative controls fail as they must: ptrim_en = 0 -> no edges, outputs 0 V; CKP0 load removed -> 392 ps instead of 642 ps.

## 2. DECISION A vs B: **B (channel 0 doubled from inv1 on, capture unchanged)**  -- 2026-11-14, schematic + real lumped loads
Bench: decide.py / decide.json / decide.log.  Schematic devices (r9 proposal sizes: NAND 4/4, inv1 2/4, inv2 12/24, inv3 32/64,
28 fF on tn as extracted in r9), real pin loads of section 1 (+20 fF wordclk on CKP0), route LOW 30 fF unless stated,
tt/27/3.3, ss/32/3.15, ss/32/3.50, ff/22/3.35 at 480 / 625 / 810 MHz, codes 0 and 31.
* P  = r9 proposal, 8 identical channels.          B  = channel 0 inv2, inv3 x2 only.     B3 = channel 0 inv1, inv2, inv3 x2.
* B3d = B3 + a dummy inv1 gate (2/4 um MOS capacitors) on tn of channels 1..7 (so every tn sees the same gate load).
* A  = 8 identical channels, capture CKP0 pin cut to a CKP1-like front load (slicer 207.8 + capture front 216.7 + buffer gate
  32 fF = 456 fF) and a local buffer (4/8 -> 16/32, schematic) driving the other 541 fF inside the capture.

CKP0 skew = CKP0 rise delay - mean(CKP1..7), code 0, ps (625 MHz; 480 and 810 MHz agree within 1 ps):

| | tt | ss 3.15 | ss 3.50 | ff | with capture CKP0 load x0.7 / x1.3 (tt; ss 3.15) | route HIGH (tt) |
|---|---|---|---|---|---|---|
| P | +62.2 | +77.3 | +70.3 | +52.5 | +37 / +87; +47 / +108 | +66.6 |
| B | +118.7 | +136.6 | +131.6 | +100.7 | worse than P (inv1 2/4 cannot drive 24/48) | |
| B3 | +13.5 | +16.8 | +15.8 | +11.2 | +0.7 / +26; +0.8 / +33 | +15.2 |
| **B3d** | **-2.9** | **-3.6** | **-3.3** | **-2.5** | **-15.7 / +9.8; -19.7 / +12.2** | -1.2 |
| A | +8.0 | +10.0 | +9.1 | +6.8 | +0.7 / +15.3; +0.9 / +19.1 | +8.7 |

| (625 MHz) | spread of all 8 code-0 delays tt / ss3.15 / ss3.50 / ff | range (code 31 - code 0) | usable = range - spread | CKP0 20-80 % rise tt / ss3.15 (route HIGH) | CKP1 | mA code 0 / 31 (tt) |
|---|---|---|---|---|---|---|
| P | 68 / 85 / 77 / 58 ps | 107-125 ps | 38-49 ps (< 50) | 173 / 212 (223 / 263) ps | 84 / 103 | 16.2 / 17.7 |
| B3d | 12.5 / 15.6 / 14.2 / 10.5 | 106-121 | 95-107 | 97 / 118 (139 / 160) | 84 / 103 | 17.2 / 18.7 |
| A | 14.2 / 17.7 / 16.1 / 11.9 | 107-125 | 95-109 | 100 / 122 (132 / 157) | 84 / 103 | 15.2 / 16.7 (+ the capture buffer, ~1.5-2 mA) |

* Levels: every candidate rail to rail at 480 / 625 (lo <= 0.00 V, hi >= VDD - 0.01).  Currents at tt, code 0 / 31:
  B3d 13.2 / 14.4 mA (480), 17.2 / 18.7 (625), 22.2 / 24.0 (810); A 11.7 / 12.8, 15.2 / 16.7, 19.7 / 21.5 plus its buffer.
* Cost of A to the capture: the capture-internal main clock (everything that is on CKP0 today except the front rank)
  moves LATER against the CKP1..7-clocked front flops and against LDE by the buffer delay: 263 ps tt, 334 ps ss/3.15,
  305 ps ss/3.50, 219 ps ff (187-382 ps with the buffered load x0.7 / x1.3; this buffer is not optimized, ~150-250 ps is
  the realistic floor for 541 fF).  That is 0.15-0.27 T at 810 MHz taken from the hold side of every front -> CK hand-off,
  a new CKP0 distribution in wc_front / top, and a full capture re-qualification (r7c/r7d is nearly qualified; the
  LDE-vs-CKP0 window that failed at lde60 would move as well).
* Cost of B: none to the capture.  ptrim channel 0 is a second row cell (2 x inv1 / ta units / inv2 / inv3), channels 1..7
  get a dummy gate on tn; +1.0 mA (625 MHz).  Residual CKP0 skew -3 ps nominal, -20..+12 ps if the capture CKP0 wiring
  lands 30 % off: 5-15 % of the trim range, absorbed by the per-phase trim code (which exists to do exactly that).
* **Recommendation: B (B3d form).**  Good enough on every metric where A is good, and the capture does not change.
* Seen in the same runs and NOT an A/B matter (both fail alike): at ss/32/3.15, 810 MHz, the trim range collapses
  (15-48 ps) and the duty reaches 0.68-0.72 at code 31 with these r9-proposal sizes: the NAND 4/4 cannot move the trim
  node at 810 MHz/ss; duty changes by 5-7 % of T over the code range even where it works (0.527 -> 0.575 tt 625).  Both are
  step 3 (stronger first stages, trim split over tn and ta).

## 3. Criteria (written 2026-11-14 BEFORE the redesign sweeps; not to be relaxed)  -- judged by sweep.py
All at the consumer pins (after the route model), ideal 50 % input phases unless stated, every code 0..31:
* C1 levels: every CKPk low <= 0.1 VDD and high >= 0.9 VDD at every code (overshoot beyond the rails is reported).
* C2 step / monotonic (unchanged from sims.ptrim_summary): per channel rising-edge delay monotonic in the code, max step <= 1.0 deg at f.
* C3 range: usable = min over channels (code 31 - code 0) - (max - min of the eight code-0 delays, real loads) >= 60 ps at ss
  (3.15 V and 3.50 V) and >= 50 ps at tt / ff.  Need = 50 ps ring phase spread (owner's number = 11.4 deg at 625 MHz) x 1.2 at ss.
  Reported in degrees too (the r9v ring measured 13.7 deg spread at ss / 848 MHz = 45 ps).
* C4 duty at VDD/2: 45-55 % at every code and a change over the code range <= 3 % of T.  Reason: slicer and capture were
  qualified with 50 % clocks and 60-100 ps edges only; 5 % of T (62 ps at 810 MHz) is about one such edge; the ring's own
  duty (0.52-0.63 measured for the TX ring, WT29) comes on top and is not ptrim's to fix.
* C5 edges: 20-80 % rise and fall <= 150 ps at every code.
* C6 MW-31 input (ring-like source: high level 0.9 x rail and down to 2.57 V, 150 ps edges, 30 ohm / 60 fF route):
  C1, C2 hold; delay shift, static current and output duty reported.
* C7 ptrim_en = 0: every CKP low, supply current reported (existing sims.tb_safe cases unchanged).
* Corners: tt/27/3.3 and the 12-corner set (typical, ss, ff) x (22, 32 C) x (3.15, 3.35 V) at 810 MHz and 625 MHz (existing
  bench set), 480 MHz at tt / ss / ff; ss also at 3.30 / 3.40 / 3.50 V (minimum passing supply); both route bounds; capture
  CKP0 load x0.7 / x1.3; ss-pessimistic (r7slicer/pess.py on ptrim AND consumers) and optimistic (opt.py) bounds.

## 4. Design history (condensed 2026-11-18; the full 2026-11-14 log is STATUS.2026-11-14.md)
* Capture candidate since 2026-11-14 05:40 is **r7e** (scratch/wired_rx/r10cap/r7e/gen/wrx_cap.ext.spice): CKP0 total 982.1 fF,
  CKP1..7 388.4 / 461.6 / 368.1 / 478.2 / 433.8 / 420.7 / 402.7 fF (pin_cap_r7e.json); bench.py PIN / CAPT use r7e.
  R8-ARCH (16 channels): not built; the row is a repeatable unit (owner note, not evaluated further).
* Topology (unchanged since l2): trim units split between tn (after the NAND) and ta (after inv1) so CKP rise and fall
  move alike; channel 0 with inv1 / inv2 / inv3 doubled and ta units twice as wide (option B3d), dummy inv1 gate on tn of
  channels 1..7.  NAND PMOS 6 um (duty centred), inv3 50/100 (C5 at the HIGH route bound).
* Layouts l1..l6 (2026-11-14): bit-weight tuning.  l6 passed tt 625 and ff 810 and FAILED C2 at ss/3.15/810 (1.047 deg at 3 -> 4).
  Cause (analysed 2026-11-18 from sweep.json): bits 0 / 1 are tn-only units, bits 2..4 are tn+ta pairs; the pairs weigh
  +4 % against the tn-only bits at ss and -3.5 % at ff, and bit 2 loses 0.65 ps of weight from low to high codes.
* l7 (2026-11-18, first of the two allowed tuning layouts): bit 0 / 1 unit W 1.11 / 1.25 -> 1.41 / 1.54, bit 3 / 4 0.505 / 0.55 ->
  0.545 / 0.605, channel-0 ta factor of bit 2 1.205 -> 1.24 (bit 2 stays at the 0.36 um minimum width).  ss/3.15/810 PASS
  (0.898 deg), ff 810 PASS, tt 625 PASS; pessimistic ss/3.15/810 FAIL C2 on channel 0 (1.047 deg at 15 -> 16; ch 1..7 0.995).
* **l8 (second and LAST tuning layout) = FINAL** (decision rule written before its runs, see 5.1): bit 0 / 1 W 1.27 / 1.47,
  bit 3 / 4 0.535 / 0.595, channel-0 ta factors bits 2 / 3 / 4 = 1.24 / 1.175 / 1.145.  ss/3.15/810 PASS 0.910 deg,
  pessimistic ss/3.15/810 PASS 0.968 deg (sweep.json l8_ss315_810, l8_pess_ss315_810).

## 5. Session 2026-11-18: current state
### 5.0 Limits declared 2026-11-18 04:46 UTC, BEFORE any real-ring trim solve was computed (not to be relaxed)
Real-ring bench (ringreal.py): the ring's v(ph0..7) at the ptrim pins (r11/ring/ph_<tag>.npz, copied to ringcal/) replayed
as periodic PWL sources into the extracted ptrim, lumped real loads; position of CKPk = rising VDD/2 crossing against
the ideal k*T/8 grid (common offset free).
* RR1 coverage: at every calibration tag a set of codes exists with no channel left at code 0 or 31 with more than one
  step of uncorrected error, i.e. (max - min of the eight code-0 positions) <= the smallest channel range (code 31 - code 0)
  measured in the same bench.  Margin (range - need) reported in ps.
* RR2 residual: with the best codes, peak-to-peak of the eight CKP rising-edge position errors <= 3.0 deg of the ring
  period (spec AC-3), measured in a simulation run WITH those codes (a fit prediction alone does not count).
  Reported in addition (no limit): the residual in steps, the falling-edge position spread and the output duty
  (the ring's duty passes through; C4 is declared for 50 % inputs only).
* RR3 reduced input high level (real waveforms): C1 holds at the codes run; supply-current, delay and duty difference against
  the ideal full-rail 50 % source at the same frequency are reported; the static current with every PH held at the
  ring's high level is reported (no limit declared: goes to the power budget).
* LVS verdict used in this session: netgen "Circuits match uniquely" AND no "Property errors" line (layout_engine.netgen_lvs
  returns unique_match = True also WITH property errors: proven 04:45 with a 10 nm width change in the reference).
* 05:27 l7 results (sweep.json l7_*): ss/3.15/810 PASS (max step 0.898 deg), ff 810 PASS (0.793 deg, min step 1.11 ps), tt 625 PASS;
  pessimistic bound at ss/3.15/810 FAILS C2 on channel 0 only (1.047 deg at 15 -> 16; channels 1..7 0.991-0.995 deg).
  Decision rule for the SECOND (last) tuning layout l8, written before it is simulated: l8 (bit 0 / 1 W 1.27 / 1.47, bit 3 / 4
  0.535 / 0.595, channel-0 ta factors 1.24 / 1.175 / 1.145) becomes final only if it passes C1..C5 at nominal ss/3.15/810 AND
  its pessimistic ss/3.15/810 maximum step is below l7's 1.047 deg; otherwise l7 stays final.  No further layouts either way.
* 05:48 l8 results: both conditions of the rule met -> **l8 is the final design**.  Ported: W/netlists.py ptrim() + PTRIM_*
  constants, W/ptrim.spice (= netlists.BLOCKS['ptrim']().emit()), W/ptrim_compact.py defaults.  final.py (the layout flow of
  step 3) rebuilt it from those defaults into final/: results in final/layout.json.  final/gen/ptrim.ext.spice and
  l8/gen/ptrim.ext.spice are the same circuit (canon.py: identical order-independent hash 904a0fd0...; Magic writes the
  capacitors in a different order), so the two l8_* sweeps count for the final extraction; everything later runs on final/gen.
  final_l7/ is the same flow for the l7 parameters (superseded, kept only as a record; delete when publishing).
### 5.4 RESULTS (state at 08:55 UTC 2026-11-18; queue stopped on the owner's request; nothing published, nothing committed)
Final design = l8.  Files changed in the tree: W/netlists.py (ptrim() + PTRIM_* constants only), W/ptrim.spice, W/ptrim_compact.py.
Staged: final/gen/ (ptrim.gds sha256 467a63e4..., ptrim.ext.spice f35d8a84..., ptrim.mag, ptrim.lvs.spice, ptrim-layout.json,
ptrim-kldrc.json, ptrim.ext-r-typ.spice / -r-high.spice (R-aware), ptrim-evidence.json = DRAFT record); table = evidence.txt.
* Layout (final.py, rerun for l8): Magic DRC 0; LVS unique without property errors from the .mag (macro netlist and W/ptrim.spice)
  and from the GDS read back from disk (DRC 0); negative controls fail (one bit-3 group +10 nm -> property errors; one inv1
  gate moved -> pin matching fails); KLayout precheck main 0 / antenna 0, alone in final/kl.  200.11 x 235.2 um = 47 066 um2
  (published cell 449.2 x 645.0 = 289 734 um2: -242 668 um2).  844 devices.
* Criteria, lumped real loads, ideal source (all rerun this session on the final extraction or its order-identical l8 twin):
  full 32-code PASS C1..C5: ss/3.15/810 0.910 deg, ss/3.50/810 0.884, tt/625 0.673, tt/810 0.840, ff/810 0.784,
  pessimistic ss/3.15/810 0.968, pessimistic ss/3.50/810 0.968, optimistic ff/810 0.761 (min step 1.04 ps).
  8-code only (C2 partial: carries 3->4, 7->8, 15->16): ss/3.15/625, ff/625 pass.
* Real consumers (slicer + capture r7e + wordclk): ss/3.15/810 code 0 only: PASS (levels -0.003 / 3.159 V, duty 0.487-0.489,
  edges 102 ps, CKP0 skew -3.7 ps, delays 4.5-7 ps shorter than lumped, 29.8 mA).  Code 31 and every other corner NOT RUN.
* R-aware (rmodel.py from netres.py on the final GDS; proof rcheck.json: R -> 1 mohm reproduces C-only within 0.04 ps, R x 10
  shifts 176 ps): high metal, ss/3.15/810, 32 codes PASS: max step 0.948 deg (C-only 0.910), edges 119.5 ps (105.3), code-0
  delay +13.5 ps (CKP0, far end of the strap) ... +4.9 ps (CKP7), spread 11.9 ps (10.6), levels 0.008 / 3.160 V.
  typ metal, pessimistic + high metal, other corners, droop waveforms: NOT RUN.
* Real ring, SETTLED tables (rr2.py; RR1 / RR2 all pass where run): ss315625 need 48.0 / range 96.1 / residual 1.82 ps (0.41 deg);
  ss315675 48.6 / 91.9 / 2.90 ps (0.71 deg); tt625 40.5 / 83.9 / 2.94 ps (0.66 deg); **ss315810 54.0 / 60.6 / 1.39 ps (0.41 deg):
  margin only 6.6 ps**.  Not run: ss315480, tt810/480/675, every ff and ss350 tag (12 of 16).
* Cause of the small range at ss/3.15/810 (diagnostic X_diag_*, ideal source): the ring's 63 % duty alone cuts the rising-edge
  range from 89 to 61-64 ps (tn does not recover in the short high phase); 2.69 V high level alone: range 93 ps, duty -2 %,
  current unchanged; slow edges alone: 87 ps.  CKP duty follows the ring (0.60-0.63 at ss/3.15/810): outside the 45-55 % the
  consumers were qualified with.  This is the open system risk.
* Input load per phase (inload.py, ss/3.15/810, 2.69 V swing): 49.6 fF (PH0 54.1 fF); static sum 53.6 / 58.2 fF (published cell
  241 / 128 fF).  Static current with every PH at 2.69 V: 0.01 uA.  ptrim_en = 0 (safe2.py, ff/3.35): outputs 1 mV, no edges, ~1 uA.
  safe.py (W/sims.tb_safe: 3.63 V, 0 / 85 C, stuck-on, unpowered) FAILS TO RUN on the hierarchical extraction: NOT RUN.
* NOT RUN (full list in evidence.txt / ptrim-evidence.json not_run and qm.dropped.jobs): sf / fs corners; route HIGH bound on l8;
  480 and 675 MHz ideal-source sweeps; 12-corner set at 810; capture CKP0 load x0.7 / x1.3; ss at 3.30 / 3.40 V; pessimistic /
  optimistic at 625 / 480; MW-31 synthetic source (C6; replaced by the ring replays that were run); R-aware typ / pessimistic.
### 5.1 How to resume
* Queue: `./runq2.sh qm` runs qm.jobs (priority order, every line takes its own slot); log qm.log.  Declared full matrix =
  qa.jobs + qb.jobs + qc.jobs (qual2.py); evidence.py lists whatever of it has no result as NOT RUN.
* Scripts: sweep.py (32-code / reduced sweeps, C1..C5), real.py (real consumers), ringreal.py (ring waveform replay),
  rr.sh (two-pass trim solve), rr1.py (single-pass trim check: solved codes + 0 + 31 in one deck), solve.py, inload.py
  (input load, static current), safe.py, final.py (layout flow), canon.py, evidence.py (draft record -> final/gen/ptrim-evidence.json).
### 5.2 Real-ring bench: proof and a finding on the calibration (06:10)
* ringreal.py proof (l6, tt625, code 0, owner's raw table): channels 1..7 reproduce cal.json's code-0 delays within 0.3-0.6 ps;
  channel 0 was 10 ps off.  Negative control (PH3 delayed 20 ps): CKP3 moved +20.00 ps, the others 0.00.  PASS as a bench.
* Cause of the channel-0 miss = **the owner's calibration is not in steady state** (ringdiag.py tt625, cal.deck() rerun for
  60 ns, ringdiag.json): PH0 period 2182 -> 1601 (20 ns) -> 1503 (30 ns) -> 1458 ps (58 ns), still falling.  cal.py takes the
  MEAN period of 18-30 ns: the table is not periodic (last cycle 3-88 ps shorter than the table, all 15 tags) and pos_err_ps
  carries a ramp (-gap * k / 8).  Per-cycle positions against the cycle's own period are stable (tt625: span 38 ps, not 58.6).
  Owner told 06:06 (SendMessage).  Work-around here: fixtab.py -> ringcal/phfix_<tag>.npz (table cut at PH0's own next crossing,
  scaled to 1/f0) and ringcal/phfix.json (corrected positions, spans 33-57 ps).  Uncertainty: about +-5 ps on positions (the
  period changes ~6 ps per cycle inside the owner's window; residual wrap step up to 0.19 V on a phase that is mid-edge at the
  wrap, i.e. PH4 falling).  EVERY real-ring result below uses these corrected tables and must be repeated on a settled calibration.
* Solver: all results use the docker ngspice of wrx_flow (default solver).  Host ngspice-42 + KLU (owner's tip) NOT used.
### 5.3 Additions required by the coordinator rule of 2026-11-18 (owner message 06:40), declared before any such run
* sf and fs corners, 32 C / 3.15 V, 810 and 625 MHz, full 32-code sweeps, criteria C1..C5 unchanged; C3 limit for sf / fs
  = 60 ps (the slow-corner number; sweep.py's judge applies 50 ps to non-ss corners, so C3 is re-judged against 60 in the
  evidence record).
* R-aware model of the clock path (CKPk output net, tb, VDD / VSS row rails and straps of inv2 / inv3) from the final GDS
  with analog/pads/rextract/netres.py, typ and high metal; gating cases repeated on it: ss/3.15/810, pess ss/3.15/810 (high
  metal), tt 625, ff 810 (typ metal); same criteria C1..C5, no new limits.  Reported: change against C-only in delay,
  edges, maximum step, range, and the supply droop at the output stage.
* 07:06 proof with a periodic table (rr_proof2_tt625_l6, phfix table): all EIGHT channels reproduce the calibration's code-0
  delays within 0.3 ps.  Owner withdrew the unsettled calibration (now r11/ring/unsettled/) and re-runs it settled (160 ns,
  own-period tables) into r11/ring/; fixtab.py copies those as ringcal/phset_<tag>.npz.  Settled vs drift-corrected positions:
  ss315625 within 1.6 ps, ss315480 within 4.3 ps, ss315810 within 8.6 ps (PH7).  Real-ring results are produced with rr2.py
  (9-point code curve + verification run in one call) on the SETTLED tables; one interim tag (ss315625) is kept for comparison.
* Finding (rr_ss315810, interim table): under the real ring waveform at ss/3.15/810 (ring duty 0.60-0.63, 2.69 V high level,
  ~200 ps edges) the code curve is compressive: range 62-66 ps instead of 89 ps with the ideal 50 % source; a 5-weight fit
  is off by 3 ps.  rr1.py (single pass) is therefore retired; rr2.py interpolates the measured curve.
