# r10detect STATUS (pt_detect r10 candidate q27) — current state, 2026-11-18

NOT published, NOT committed, W/generated untouched.  Candidate: `stage/q27` (schematic `sch/detect8.spice` = `W/detect.spice`
= what `W/netlists.py detect()` emits, sha256 bb19eecc...; GDS sha256 0eb9541b...; C-only extraction sha256 b4d42ad3...).
The log of 2026-11-14 (mechanism study, earlier variants) is in `STATUS-2026-11-14.md`.

## Verdict: q27 is NOT ready to publish
1. Supply and ground are single 0.44 um Metal5 trunks over the 541 um cell height (R-aware finding, two independent tools):
   pin to each PMOS source 21-90 ohm (median 50), pin to each NMOS source 22-87 ohm (median 47) at typical metal, 63-147 ohm at
   the high-metal bound.  Static effect measured (lower bound): squelch -2.5 %, disconnect -1.1 / +0.9 % with a 12 mV pos/neg
   split, HS signal detect +4.7 / +7.9 %; 46 mV of rail drop at the reference mirror with only the 1.8 mA static current.  The
   clocked R-aware bench does not converge, so the full-current number does not exist.
2. ss-pessimistic 3.15 V fails gating (disconnect fires at 525 mV at CM 0.36 / 0.5 V: 3.6 % / 10.4 %, limit 2 %; start-up
   glitch ends at 106 ns, TEN is 100 ns).  ss-pessimistic 3.50 V (code 10) fails harder: 9-30 % at every common mode.  The supply trim does NOT rescue it.
   At both pessimistic supplies DIFF_POS is still high at 106 ns with 60 mV applied (end of the guard window; the true end was
   not measured), so the squelch ramp threshold could not be read; pessimistic squelch gating was not run.
3. C1(a) disconnect schematic -> extracted +5.2 % (pos) against the declared +-5 %.
4. C6 fails at CM 2.5 V with the real USB pad (pad bypass switch clips RX at 2.0 V tt / 1.8 V ss); read from the 2026-11-14 run.
5. C7 has no transient on the real chain; the tap resistors exist in no cell.
6. USB HS bench with the real pad aborts (pad model, not the solver); 9 of 13 corners, sf / fs, optimistic bound not run.

## Files
- common.py (runner), bench.py (block benches; 2026-11-18: guard window starts at TEN, glitch_end_* reported, cmhs= / per= /
  sfx= options, waveform deleted after analysis), tab.py (criteria table from res/v27*.json), evid.py (draft evidence record)
- static.py (clock-stopped preamp-balance thresholds; the only bench that runs on the R-aware netlist), rcfix.py, rnet.py,
  rcprobe.py (convergence probes), verify27.py (layout re-verification from disk)
- hssd2.py (C7 on the real chain, new R-aware pad model, tap on SL; only y and ac modes have run), hssd.py (obsolete: pad tap)
- usbd4.py (USB pad + COB; options mode=div, src=ideal, meth=, asym=, noload=, tend=)
- runq3.sh + queue3.txt (one slot.sh call per line; finished, QEND3 set), queue3.dropped.txt = the NOT RUN list
- res/v27.json, v27p.json (reruns of 2026-11-18), static_tt.json, static_ss315.json, hssd2_y.json, hssd2_ac.json,
  usbd4_v27.json; res/q27*.json, r31.json, b8*.json, extra_q27.json, term8.json, usbd4_q27.json = 2026-11-14, read only
- stage/q27/gen: detect.gds/.mag/.ext.spice (C-only), detect_pess / detect_opt (bounds), detect.rc.ext.spice (Magic extresist,
  R on 40 of 364 nets, capacitance double-counted: 11.1 pF against 5.9 pF), detect.rcb.ext.spice (same, bulk terminals on the pin
  node), detect-evidence-draft.json; stage/q27/verify (layout re-verification), stage/q27/rc, stage/q27/netres

## Criteria (written before any r10 run; not to be relaxed)
- C1 parasitic robustness (tt/27/3.3, CM 0.2, ramp thresholds, mean of pos/neg):
  squelch moves < +-10 % and disconnect < +-5 % (tighter than the +-10 % asked: its window is only +-8.7 %)
  (a) schematic -> extracted, (b) all extracted C x0.7 and x1.5 vs x1.0, (c) between two different layouts
  (different column count).  Ramp resolution: 3.3 mV (squelch), 5.6 mV (disconnect), 0.8 mV (HS SD).
- C2 thresholds at every corner (13 = tt/27/3.3 + {tt,ss,ff} x {22,32} x {3.15,3.35}; ss-pessimistic (r7slicer/pess.py)
  and optimistic bound; ss and ss-pess also at 3.50 V): ramp thresholds squelch 105-145 mV, disconnect 535-615 mV
  (USB windows 100-150 / 525-625 with 5 / 10 mV guard), pos/neg split < 10 mV (squelch) / 20 mV (disconnect).
  det_thr trim code may be the one stated for that supply (00 at 3.15-3.35 V unless stated; 10 at 3.50 V).
- C3 gating (same stimulus and limits as the published r7 tb_detect): squelch fires at 150 mV (fraction > 0.5 in
  12..64 ns) and is silent at 100 mV (hit fraction < 0.02 in 70..128 ns) at line CM -0.05 / 0.2 / 0.5 V; disconnect
  fires at 625 mV / silent at 525 mV at CM -0.05 / 0.2 / 0.36 / 0.5 V; FS line state J/K/SE0 (SE_P, SE_N, FS_DIFF);
  receiver detect (inject 60-160 uA, present leg slower); off (< 2 uA, outputs < 0.1 V).  TEN = 100 ns after det_en.
  The ss/22 and ss/32 3.15 V disconnect CM 0.5 V case must pass, or the minimum passing supply is stated
  (3.15 / 3.30 / 3.40 / 3.50 V).
- C4 supply current with det_en=1 (HS SD off) <= 4 mA (wired budget), stated with det_hs_en=1 as well.
- C5 layout: Magic DRC 0, LVS unique on the GDS read back from disk, KLayout precheck main 0 / antenna 0 run alone in
  its own work directory; area target <= 0.09 mm2.
- C6 FS/LS differential receiver (FS_DIFF): correct for |P-N| = 200 mV at CM 0.8 / 1.65 / 2.5 V at 12 Mb/s with
  det_clk 48 MHz, real source (pad_wirepad extraction), tt/ss/ff.
- C7 HS signal detect (SD_POS|SD_NEG): never fires on idle (noise/crosstalk <= 20 mVppd) and fires on PRBS data
  >= 100 mVppd at the pad at 1.25 and 3.24 Gb/s (through the channel loss), tt/ss/ff; decision rule and response
  time stated.  Threshold target 50-100 mVppd.

## Current state against the criteria (rerun 2026-11-18 unless marked "read")

det_thr code per supply: 3.15 V -> 01, 3.30 / 3.35 V -> 00, 3.50 V -> 10 (stated in the netlist docstring before the corner runs).
With code 00 at ss/32/3.15 disconnect gating fails (silent-at-525 violated, 23-51 %: read, 2026-11-14).

| corner (code) | bound | squelch +/- mV | disc +/- mV | SD +/- mV | C2 sq / dc | start glitch ns | C3 sq / dc / FS / rxdet / off | fire min / silent max | inject uA | I usb / hs-on mA | C4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| typical_27_3.3 | nom | 124.2 / 124.2 | 581.9 / 587.4 | 35.8 / 35.8 | pass / pass | 63.2 | pass / pass / pass / pass / pass | 0.997 / 0.0 | 120 | 3.24 / 4.12 | pass |
| ss_32_3.15_thr1 | nom | 124.6 / 124.7 | 577.4 / 583.0 | 36.0 / 35.9 | pass / pass | 83.7 | pass / pass / pass / pass / pass | 0.996 / 0.0 | 98 | 2.86 / 3.6 | pass |
| ss_32_3.5_thr2 | nom | 124.4 / 124.5 | 582.3 / 587.8 | 35.9 / 35.9 | pass / pass | 75.4 | pass / pass / pass / pass / pass | 0.998 / 0.0 | 115 | 3.12 / 3.95 | pass |
| ff_22_3.35 | nom | 127.1 / 127.2 | 592.6 / 598.3 | 36.6 / 36.6 | pass / pass | 50.7 | pass / pass / pass / pass / pass | 0.994 / 0.0 | 132 | 3.66 / 4.68 | pass |
| ss_32_3.15_thr1 | pess | None / None | 589.2 / 594.6 | 40.1 / 39.3 | FAIL / pass | 106.0 | not run / FAIL / not run / not run / not run | 0.998 / 0.104 | None | 3.08 / 3.82 | pass |
| ss_32_3.5_thr2 | pess | None / None | 583.1 / 593.9 | 36.8 / 36.8 | FAIL / pass | 106.0 | not run / FAIL / not run / not run / not run | 1.0 / 0.3 | None | 3.45 / 4.28 | pass |

Columns: ramp thresholds pos / neg; C2 windows squelch 105-145, disconnect 535-615, split < 10 / 20 mV; start glitch = end of the last
wrong output after det_en (limit TEN = 100 ns; 106.0 = still high at the end of the guard window); fire min / silent max = worst gating fractions (limits > 0.5 / < 0.02).

- C1 (a) schematic -> extracted, tt: squelch 113.7 -> 124.2 (+9.2 %, pass), disconnect 552.9 -> 581.9 (+5.2 %, FAIL of +-5 %);
  schematic value read (res/b8.json, pos only), extracted rerun.  (b) C x0.7 / x1.5: squelch -2.7 / +2.9 %, disconnect -1.0 /
  +1.1 %, pass (read).  (c) second layout r31: 124.25 / 582.0, pass (read).  Reruns of (a)-(c) were queued and NOT run.
  Clock activity is part of the shift: clock-stopped C-only thresholds are 117.1 / 567.6 / 31.6 mV against 124.2 / 581.9 /
  35.8 mV clocked at 250 MHz.  Dependence on the det_clk frequency: NOT run.
- C2 / C3 / C4: table.  9 of the 13 corners, sf / fs, ff-optimistic: NOT run.
- C5 layout (verify27.py, stage/q27/verify/verify.json, all rerun from the files on disk): Magic DRC 0 (.mag and GDS read
  back), LVS unique from the .mag and from the GDS read back (443 = 443 devices, 229 = 229 nets, no property errors), three
  negative controls fail as required (gate net swapped: pin matching fails; W 12 -> 13 um: netlists do not match; resistor
  L 3 -> 3.5 um: property error), KLayout precheck main 0 / antenna 0 alone in stage/q27/verify/kl.  Outline 167.14 x 541.12 um
  = 90 443 um2: 443 um2 over the 0.09 mm2 target (miss); 48 % smaller than the published 251.3 x 690.4 = 173 498 um2.
- C6 (read, 2026-11-14, real pad in bypass mode): 0 errors / 45 at CM 0.8 and 1.65 V (tt, ss); 24 errors / 45 at CM 2.5 V
  (tt, ss): FAIL.  RX_P/N behind the pad's NMOS bypass switch stop at 2.02-2.06 V (tt/3.3) and 1.80-1.83 V (ss/3.15).  ff,
  the pad's divider mode and the ideal-source proof: NOT run.
- C7: no transient.  Done: tap admittance and chain AC (below).  hssd2.py is bound to the republished pad model
  (physical-r-typ.spice, PC-22); the AC numbers below were taken with the old capacitance-only pad model.
- USB HS with the real pad (usbd4.py hs): aborts at 132.62 ns (first crossing of the two lines) with gear, trapezoidal,
  shunts, KLU, loosened tolerances and an asymmetry aid; completes without the pad (src=ideal) and still aborts without the
  rxselect / wmon loads: the extracted pad_wirepad model in termination mode is the cause.  No R-aware model of pad_wirepad
  exists (only physical.spice).

## Rail resistance (R-aware)
- netres.py (pads owner's solver) on the GDS, stage/q27/netres/netres.log: VDD_WIRE_SW pin -> each PMOS source min 20.7 /
  median 49.7 / max 90.0 ohm (typ), 63 / 98 / 147 (high); all PMOS sources shorted: 5.2 ohm (typ), 9.2 (high).  VSS pin -> each
  NMOS source 22.3 / 47.4 / 87.2 ohm (typ), 65 / 95 / 143 (high); all shorted 5.3 / 9.2 ohm.  Narrowest on-path metal 0.44 um
  Metal5.  Magic extresist agrees (rnet.py: median 51 / max 93 ohm VDD, median 46 ohm VSS).
- Static bench (static.py; clock stopped, 1.8 mA; R on 40 of 364 nets; typical metal): LOWER BOUND.
  tt: squelch 117.1 / 117.2 -> 114.3 / 115.4 mV, disconnect 567.6 / 567.7 -> 561.3 / 573.1, SD 31.6 / 31.6 -> 33.1 / 34.1;
  ss/32/3.15 (code 01): 117.0 / 117.0 -> 114.4 / 115.4, 565.7 / 565.8 -> 559.6 / 570.0, 31.5 / 31.6 -> 32.8 / 33.7.
  Rail at the reference mirror 3.2537 V (46 mV drop); at the tails 3.254 V (squelch) to 3.2775 V (SD): up to 24 mV more
  |Vgs| on a tail than on the reference.
- Clocked transient on the R-aware netlist: aborts (timestep too small at the enable edge with trapezoidal, at the first
  clock edge with gear, with and without the substrate resistors, with cshunt); with KLU the operating point is singular
  and the run hung (killed after 40 min).  Not solved.
- Fix (not built): wrx_flow `currents=` sizing or explicit widening of the two Metal5 supply trunks to >= 4 um (<= 5.5 ohm
  end to end) or a second trunk on the opposite side strapped per row; reference mirror and the six tail groups on one
  local rail segment; then a full R+C extraction with `extresist simplify off` (method of scratch/wired_rx/r11/rc_ctle).

## HS signal detect tap (C7)
- Taps exist in no cell.  They must be two resistors AT the SL trunk (in pt_rxselect r2 or pt_ctle r4, both on SL, or a
  small tap cell on the route), not in pt_detect.
- Load on SL per leg, 5 kohm tap + 20 fF route + pt_detect HS input (tt, hssd2.py y): parallel-equivalent C 44 / 15 / 5.2 /
  3.6 fF and R 7.7 / 6.0 / 5.5 / 5.5 kohm at 312.5 / 625 / 1250 / 1620 MHz.  3 kohm: 77 / 33 / 11 / 7.3 fF, 7.0 / 4.3 / 3.6 /
  3.5 kohm.  10 kohm: 16 / 5.4 / 2.5 / 2.1 fF, 11.7 / 10.9 / 10.6 / 10.6 kohm.  Without a tap: 124 / 121 / 117 / 116 fF.
- Effect on the chain gain at SL (5 kohm; old pad model): -0.10 / -0.13 / -0.12 / -0.10 dB at 312.5 / 625 / 1250 / 1620 MHz
  (tt); -0.10 / -0.12 / -0.09 / -0.08 dB (ss-pessimistic 3.15).  Known answer in the same bench: +10 fF per leg costs 0.030 /
  0.044 dB at 1250 / 1620 MHz (tt).  Detect directly on SL: -0.38 / -0.52 dB (tt), -0.59 / -0.70 dB (ss-pess).
- Tap bandwidth SL -> detect input: 224 MHz (5 k), 356 MHz (3 k), 112 MHz (10 k).

## NOT RUN (queue3.dropped.txt, 67 lines)
9 of the 13 corners; sf / fs (8 corners); ff-optimistic; ss-pessimistic squelch / line state / receiver detect; every C7
transient (idle / data, 1.25 and 3.24 Gb/s, tt / ss / ff, high-metal pad, CTLE code 7, tap 3 k / 10 k) and its two negative
controls; USB HS real pad (aborts); FS ff, FS divider mode, FS ideal-source proof; C1 reruns (x0.7 / x1.5 / r31 / schematic);
schematic negative control of the gating bench (sch/detect8_neg.spice exists); det_clk frequency dependence; HS-input
common-mode sweep (0.4 / 0.6 V; all SD thresholds so far are at CM 1.0 V or 0.45 V static); clocked R-aware gating; Monte
Carlo.

## Resume
`cat queue3.dropped.txt >> queue3.txt; rm QEND3; nohup ./runq3.sh &` reruns the dropped list (one slot per line).  Before
that: fix the rails, re-extract R+C, and resolve the pad_wirepad convergence.
