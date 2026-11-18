# r11: wired RX resume 11 (2026-11-18) - finish capture r7e, CTLE r4 / rxselect r2, ptrim r10, detect r10 to published state

Owner notes, kept current.  Sub-directories: ring/ (RX ring phase calibration), chain/ (real-chain bench), cap/ (capture extra cases),
review/ (independent review).  Sub-agents: r10ptrim (ptrim), r10detect (detect); their STATUS.md files are their resume points.
All ngspice through ../slot.sh (3 slots, FIFO), OMP_NUM_THREADS=1.

## State at start (read, not rerun)
- capture r7e staged in ../r10cap/r7e (tree capture.py = its source).  Gating cases pass EXCEPT ext_f480p0 (11 data / 13 edge errors,
  full rate psel 0) -> to diagnose.  Pessimistic ss 625 MHz fails at 3.15 and 3.50 V (slot-enable chain, architecture).  Not run: 675 / 810
  MHz, 3.50 V, ff at 625 / 810.
- CTLE r4 + rxselect r2 staged in ../r10ctle/stage/gen (tree netlists = staged schematics).  Chain table with IDEAL phases complete
  (closure10.py).  Not done: real clocks, capture joined, review, publish.
- ptrim: last layout ../r10ptrim/l6 (fails C2 at ss/3.15/810 MHz: 1.047 deg vs 1.0); netlists.ptrim() / ptrim.spice still r9.
- detect: candidate ../r10detect/stage/q27 (tree detect.spice = sch/detect8.spice); STATUS.md there is behind the logs.

## Pass limits for the r11 real-neighbour benches (written 2026-11-18 04:50 UTC, BEFORE any gating run; not to be relaxed)
Corners: tt/27/3.30, ss/32/3.15, ss/32/3.50, ff/22/3.35, ss-pessimistic (r7slicer/pess.py on every extracted netlist of the
wired RX; wiring C x1.15, Rg, +25 % device C) at 3.15 and 3.50 V.  Rates and the BUILT hardware mode (one sampler bank, 8 ring
phases): 0.48 Gb/s full rate ring 480 MHz; 1.25 half rate ring 625; 2.5 / 2.7 / 3.24 quarter rate ring 625 / 675 / 810.
Ring = extracted pt_pll_ring on its regulated supply (2.95 tt, 2.69 ss/3.15, 3.02 ss/3.50, 3.01 ff), phases as delivered at the
ptrim pins (ring/cal.json); pessimistic cells use the nominal-ss ring waveform (the ring is not pessimised: stated).

Bench A (chain/rc11.py tran): TX -> COB P2 -> pad_hspad extraction -> CTLE r4 -> SL -> extracted sampler bank, clocked by the
replayed ring phases through the extracted pt_ptrim into the real sampler clock pins + lumped capture clock-pin C.
Data phase = CDR-lock emulation (transitions on the mean edge-sampler instant, per-sampler aperture measured by `rc11.py ap`).
* A-EYE (as r10 C-EYE): eye at SL >= 60 mVppd at the best phase and >= 0.25 UI wide at 60 mVppd.
* A-INST (new): at EVERY data sampler's actual decision instant the eye is >= 60 mVppd, with >= 0.05 UI to each side still >= 60 mVppd.
* A-BER (as r10 C-BER): 0 wrong decisions on the data samplers over >= 100 decisions.
* Full rate (0.48): A-EYE, and >= 3 adjacent sampler phases error-free (>= 20 decisions each) with >= 60 mVppd at their instants.
* Stimuli: T3 = 120 mVppd TX, COB only (gating, every cell); T2 = 400 mVppd through the 6 dB-at-Nyquist channel (gating at tt, ss 3.15,
  ss-pess 3.15).  Pad: padr=40 (today's ~140 ohm termination) is the gating pad; padr=0 (intended 100 ohm) reported for sensitivity
  at tt / ss 3.15 / ss-pess 3.15, rates 1.25 / 2.5 / 3.24, T3.
* Trim codes: 'auto' (codes equalising the CKP spacing, solved on clock-only runs) is the gating case; all-zero codes reported at
  tt and ss 3.15, 2.5 and 3.24 Gb/s (what an uncalibrated die does).
* Clock-only gate (rc11.py clk): CKP low <= 0.1 VDD, high >= 0.9 VDD, duty 0.40-0.60 at the consumers (the ring's own duty passes
  through; ptrim C4 is judged on 50 % inputs by the ptrim bench), trim range covers the measured need (range_covers).
* Bench proof first: (1) clock=ideal reproduces the r10 cell tt 2.5 Gb/s T2 padr=0 (298 mV, 0.80 UI, 0 errors) within 5 %;
  (2) neg=sl3p (3 pF on SL) must fail A-EYE/A-BER; (3) neg=ph2 (one data phase 0.4 UI late) must fail A-INST or A-BER.

Bench B (capture with real sampler bank and real clocks; chain/rb11.py): ring replay -> ptrim -> extracted sampler bank + extracted
capture r7e; SL driven by an ideal 120 mVppd differential PRBS7 at the corner's SL common mode, placed by the same lock emulation.
* B-DATA: 0 data-word errors and 0 edge-word errors at the capture outputs over >= 150 (quarter) / 120 (half) / 60 (full) bits.
* B-PD: votes only on the legs used by the mode; no vote leg stuck.
* B-WSTB: one strobe per word.
* Negative control: one sampler output stuck must give errors.

Supply-trim rule: a cell that fails at ss/3.15 is rerun at 3.50 (and 3.30 / 3.40 if it then passes) and reported as
"rescued by trim" or "not rescued".

## Results log (keep current)
- 05:04 bench A proof (1): clock=ideal, tt 2.5 Gb/s T2 padr=0: 297.2 mV / 0.80 UI / 0 errors of 144 (r10: 298 / 0.80 / 0 of 120) -> reproduced.
- aperture (rc11.py ap) tt: 89-97 ps per sampler, slide-direction difference <= 10 ps (step 8 ps) -> bench self-consistent.
- nodnw/ (what-if, follower body on VSS, no DNWELL; staged extraction re-tied, linear estimates only): gain at 1.25 / 1.62 GHz
  tt +0.55 / -1.18 dB (isolated well +2.0 / 0.0), ss 3.15 +0.63 / -1.63 (+2.0 / -0.5), ss-pess -1.05 / -4.0 (+0.1 / -3.1);
  SL CM 0.40 V tt, 0.355 V ss (below the 0.38 V the sampler bank was verified at); PDA eye 2.5 Gb/s T3 105 / 113 / 111 mV,
  3.24 Gb/s T3 one bank 105 / 107 / 81 mV.  DNWELL is unconfirmed (INT-30): fallback exists at about -1.3 dB.
- ring cal (ring/cal.json): ss 3.15: 625 MHz pos errors to -66 ps, duty 0.56-0.57; 810 MHz reachable (VCTRL 1.79 of 2.69 V), duty 0.61-0.63.
- 05:33 capture r7e GDS READ BACK (cap/readback/readback.json): gds sha eff0b36d..., Magic DRC 0, netgen flat compare 4856 = 4856 devices,
  "Circuits match uniquely", 0 property errors; negative control (one pfet width 4 -> 4.1 um in the reference) -> "Property errors
  were found" (detected).  NOTE (from the ptrim sub-agent): layout_engine.netgen_lvs reports unique_match = True even WITH property
  errors; every verdict here is taken from the report text (match uniquely AND no "Property errors").
- 05:33 bench A, real clocks, tt 2.5 Gb/s T2 padr=0 (l6 ptrim, 400-point replay): 295.1 mV / 0.80 UI, eye at the sampler instants
  286 mV, margin 0.325 UI, 0 errors / 144; CKP position error after trim <= 1.5 ps with the real sampler bank (lumped pre-run: 1.6 ps
  spread).  Ideal-clock reference: 297.2 mV.  Run time 892 s -> replay table reduced to 100 points per period (NSUB = 4).
- capture ext_f480p0 (full rate, psel 0) diagnosis: first probe run lost (wrong vector names, 45 min); rerun started 05:33
  (cap/p0probe, an.py -> an.out).  Symptom from the stored waveform: word alignment correct, isolated single-bit pulses of the data
  are lost or moved by one bit (pattern dependent), psel 3 and 5 clean.
- chip-level extra loads on the ring phases NOT in the ring calibration: CDRPH[0] also feeds clockmux.WSI and prescale_hf.CK_IN,
  CDRPH[1] feeds obs_pre4_cdr.CK (PINS.md); sensitivity run to do (PH0 +50 fF, PH1 +30 fF).
- 05:40 bench A negative control (2) neg=sl3p: 55.3 mV, width 0, 10 errors / 112 -> FAILS as required.
- 05:50 bench A negative control (3) neg=ph2 (PH2 0.4 UI late, CKP2 +139 ps): DID NOT FAIL: eye at D1's instant 115.9 mV, margin
  0.05 UI (= the limit), 0 errors / 112.  Reason: at tt 2.5 Gb/s T2 the eye is 0.80 UI wide, so 0.4 UI off-centre is still inside it.
  The declared control was too weak; the bench is NOT yet proven able to fail on a clock-phase fault.  Added control neg=ph2x
  (PH2 0.5 UI late = on the data transition), queued; if that does not fail the A-INST / A-BER evaluation is wrong.
- 06:01 solver: `.option klu` on the capture bench B deck (12 ns): 103 s against 391 s.  All r11 decks now use it (rc11.KLU); the
  results before 06:02 (keys *_noklu, *_n400 in chain/tran.json) used the default solver and are the comparison points.
- 06:10 **Ring calibration was WRONG (found by the ptrim sub-agent, confirmed from its ringdiag.json): the 30 ns runs were not
  settled** (PH0 period 1503 ps at 30 ns, 1458 ps at 58 ns, still falling), so cal.json position errors were inflated (tt 625: span
  58.6 ps reported, about 38 ps on a settled cycle), the tables were not periodic (wrap step 3-88 ps) and VCTRL was biased.
  Everything derived from it is withdrawn: ring/unsettled/, chain/unsettled/ (clk.json, the real-clock rows of tran.json incl. the
  ph2 control).  cal.py now runs 160 ns, requires the last six periods within 0.5 ps and a periodic wrap; queue ring/jobs3.txt,
  DUT = final ptrim l8.  Ideal-clock rows and the aperture records are unaffected.
- 06:25 **capture full-rate mode (psel path) is a timing race, not a psel-0 bug** (cap/p0probe/an.out, r7e extracted, tt, ring 480 MHz,
  T = 2083 ps, times after the capture CK rise): octet O0 changes at 570-615 ps; the 8:1 phase mux output DF at 1273-1521 ps (700-900 ps
  of mux); lane at the bit pair 1868-2161 ps (rise) / 1930 ps (fall); the slot flop clocks at 1874-1887 ps.  Data and capture edge
  coincide, so each bit is taken from the current or the previous ring cycle depending on the data pattern: psel 0 gives 11 / 60
  data errors, psel 3 and 5 happen to land consistently.  Quarter and half rate do not use the mux and pass.  No sizing fix is
  robust over 480-810 MHz and corners; it needs the selected sample registered before the lanes (capture re-architecture, same
  revision as the slot-enable chain).  NOT fixed in r7e.  Work-around without analog change: receive 0.48 Gb/s in QUARTER mode at
  ring 480 MHz (the capture then delivers all eight samples per bit, DW + EW) and pick the phase in the digital macro.
  Consequence here: r7e fails a gating case of its own flow (ext_f480p0) -> not published by me; decision needed.
- 06:22 first settled ring point ss315 625 MHz: VCTRL 1.364 V (unsettled value 1.422 gave 673 MHz), position errors
  [0, -0.9, -23.9, -22.4, 0, -19.5, -43.1, -11.3] ps (span 43 ps; the withdrawn table said 66), duty 0.56-0.58.
- 06:40 **Coordinator: pad_hspad republished (PC-22); the capacitance-only pad model is invalid.**  All r10 chain results and my
  r11 rows so far used it.  rc11.py now binds analog/pads/.../wired-receive-hs/physical-r-typ.spice (R11_PAD=high|low for the
  metal bounds), termination code per corner from the pads record (tt 5, ss/3.15 8, ss/3.50 7, ff 3), AC cache in chain/ac_r<metal>,
  result keys *_pad<metal>.  The padr=40/0 sensitivity of the declared plan is replaced by typ / high metal.  New asks: (a) CTLE gain
  range at 3.125-3.24 Gb/s slow / pessimistic on this pad, (b) largest tolerable pad C (ESD fix may add 0.3-0.9 pF) -> padc.py /
  padc.json (linear estimate, extra C at the bond-pad node).  Audit rules for anything published: R+C extraction of our own cells,
  sf / fs corners.  Sub-agents and the CTLE reviewer told.
- 07:05 padc.json (new pad r-typ, LINEAR estimate, one bank; sent to the coordinator as interim): 3.24 Gb/s T3 eye mV / width UI at +0 pF:
  tt 108 / 0.50, ss 3.15 98 / 0.44, ss 3.50 108 / 0.44, ff 102 / 0.56, ss-pess 3.15 64 / 0.19 FAIL, ss-pess 3.50 71 / 0.31 (trim rescues).
  +0.9 pF per leg at the bond pad: tt 104 / 0.44, ss 89 / 0.375, ff 101 / 0.50; ss-pess 3.15: 3.125 Gb/s ok to +0.6 pF (67 / 0.25), fails
  +0.9; ss-pess 3.50: 3.24 Gb/s ok to +0.6 pF (66 / 0.25), fails +0.9.  CTLE peak codes add no absolute gain at 1.62 GHz.
- pad model physical-r-typ.spice needs `.option rshunt=1e13` (floating island m3_32896_117300#): row to pads.
- detect sub-agent (interim, unconfirmed): R-aware extraction of the staged detect shows ~50 ohm (up to 93) in the supply trunk and
  ~46 ohm in the ground trunk (single thin trunks of the wrx_flow house style over 541 um).  Same style is in rxselect, wmon_sel,
  termination, rxlevel, vthdac; CTLE r4 sized its DC paths.  R+C extraction of CTLE / rxselect still to do by me.
- 08:08 Slots are the bottleneck (six parties on three slots; a 6-minute job waits 10+ minutes).  Production cut to the essential
  cells: ring/jobs4.txt (tt810, ss350 810/625, ff 625/810) and chain/jobsR.txt (14 jobs).  NOT queued any more: 0.48 / 2.7 Gb/s
  rows except where already run, T2 at most corners, the all-zero-code rows, sf / fs, ss350 / ff at 480 and 675 MHz, most bench B
  cells.  The full lists remain in chain/jobsQ.txt and ring/jobs3.txt for a successor (`./runq2.sh jobsQ.txt`; stop with `touch STOP`).
- 07:56 ss315 3.24 Gb/s T3 (ring 810 MHz, real clocks, new pad): analog eye 87.5 mV / 0.35 UI, 79 mV at the sampler instants,
  margin 0.075 UI, but 36 wrong decisions of 110 on the data samplers -> FAIL.  CKP duty 0.60-0.63 at the samplers, trimmed spread
  5.5 ps, trim range 60.6 ps for a need of 54 ps.  The eye is open; the sampler bank does not deliver decisions at an 810 MHz
  ring at the slow corner (clock-to-output ~ one ring period).
- 08:20 **Independent review of pt_ctle r4 / pt_rxselect r2: NO-GO / GO with conditions** (review/ctle/REVIEW.md).  Blocking: (F1) the
  core's gain and SL common mode depend on IBIAS x load resistance; with the die's bias trimmed to an absolute 10 uA and the poly
  resistor at its slow corner the gain at 1.25 GHz falls to -1.3 dB (tt MOS), -5.4 dB (sf), -6.7 dB (ff) and SL CM leaves the
  0.38-0.66 V window; our benches tie the resistor corner to the MOS corner and feed IBIAS from a 260 k resistor, which hides it.
  (F2) all stored chain evidence is on the invalid pad model.  (F3) wrx_flow.lvs() accepts netgen property errors (both staged
  reports are clean of them).  Reviewer reran layout checks from the GDS (DRC 0, LVS unique, no property errors, precheck 0/0) and
  reproduced the stored AC / transient numbers.  -> CTLE r4 is NOT published.  rxselect r2 cannot go alone (port change).
- sub-agents told to wrap up; a slim independent review of capture r7e and of the r11 bench method is running (review/capture/).
- 08:30 **R+C extraction of pt_ctle r4 / pt_rxselect r2 done (rc_ctle/, sub-agent; typical metal, from the .mag, Magic extresist with
  `simplify off`, validated: devices equal, resistors x1e-3 reproduces C-only within 0.02 dB, x10 changes -13.8 dB, four hand sums
  within 4 %).**  C-only -> R+C on the new pad, chain gain at 1.25 GHz code 0: tt +0.69 -> +0.09 dB, ss315 -0.29 -> -0.94, ssp315
  -2.26 -> -3.09; SL CM +14..21 mV; new static SL offset 5-7 mV; linear eye 3.24 Gb/s T3: tt 108 -> 103, ss315 98 -> 87, ss350
  108 -> 93, ff 102 -> 98, ssp315 64 -> 53 mV (below the 60 mV limit).  Largest wires: load return cn_rl / cp_rl 23 / 21 ohm, follower
  source -> pin 10 / 11 ohm, tail -> pair 12.6 / 9.6 ohm, RX pin -> gates 31 / 25 ohm; rxselect pass path 41-54 ohm per leg
  (direct path -1.9 dB at 1.25 GHz).  A 3-cut Via4 on the load return carries 0.83 mA per cut (limit 0.58).  Layout needs wider
  load-return, follower-output, tail and input wiring before publication.  Note for detect: extresist without `simplify off`
  writes resistance on a minority of nets only (detect's run: 40 of 364 nets), so its R-aware netlist understates.

## State at the end of this session (2026-11-18 ~09:25 UTC) - RESUME HERE
**Nothing was published.**  Sources of the four staged candidates are committed (a13d1485, 7c071015); README, interface rows
WR11-1..8 committed (02543812, d81bda78).

Sub-agent final reports (their STATUS files are current): r10ptrim/STATUS.md (l8 final, staged in r10ptrim/final/gen; every case
run passes, 55 declared cases not run; R-aware high-metal run passes; needs review), r10detect/STATUS.md (q27: not publishable:
50 ohm supply trunks, pessimistic slow corner fails at 3.15 and 3.50 V, USB HS real pad and C7 not run), rc_ctle/STATUS.md (R+C
extraction of ctle / rxselect), review/ctle/REVIEW.md (NO-GO / GO with conditions), review/capture/REVIEW.md (GO with
conditions; bench critique).

Real-neighbour results (new pad r-typ, settled ring, ptrim final, C-only extraction of our cells; chain/tran.json, capb.json, clk.json):
| cell | result |
|---|---|
| tt 2.5 Gb/s T3 | 108.9 mV / 0.625 UI, at sampler instants 107.7 mV, margin 0.15 UI, 0 / 112: pass |
| tt 3.24 Gb/s T3 | 102.9 / 0.45, 89.3 mV, 0.10 UI, 0 / 112: pass |
| ss315 1.25 Gb/s T3 | 108.6 / 0.80, 102.8 mV, 0.30 UI, 0 / 108: pass |
| ss315 2.5 Gb/s T3 | 108.3 / 0.525, 93.1 mV, 0.10 UI, 0 / 112: pass |
| ss315 3.24 Gb/s T3 | 87.5 / 0.35, 79.0 mV, 0.075 UI, 36 / 110 wrong: FAIL |
| ss315 3.24 Gb/s T3, clock=ideal (control) | 82.9 / 0.35, 0 / 112: so the failure is the real clock (duty 0.60-0.63), not the eye or the bank at 810 MHz |
| ss350 3.24 Gb/s T3 | 90.0 / 0.40, 83.2 mV, 1 / 112 wrong: FAIL -> supply trim does NOT rescue (duty 0.575-0.592) |
| ssp315 2.5 Gb/s T3 | 93.7 / 0.425, 86.6 mV, 0.125 UI, 0 / 112: pass (capture alone fails at this bound) |
| bench B ss315 2.5 Gb/s rcs=1 | 200 bits, 0 data, 0 edge errors, votes ok: pass; control neg=s2: 21 errors: fails as required |
| clock solves | spread before / after trim, range: ss315 625: 48.0 / 2.0 ps, 96 ps; ss315 810: 54.0 / 5.5, 60.6; ssp315 625: 49.1 / 3.9, 104; tt 625: 40.5 / 1.8, 84; tt 810: 36.7 / 2.5, 79; ss350 810: 43.8 / 3.4, 77 |
Declared clock gate (duty 0.40-0.60 at the consumers): MISSED at ss315 810 MHz (0.597-0.631).

Known weaknesses of these benches (review/capture/REVIEW.md, accepted): data phase is placed on the linear-estimate eye centre, not
on the real crossings (sl_crossing_mean_ui in each record: -0.085 .. +0.128 UI) -> A-INST margins below 0.15 UI are not reliable;
A-BER reads at the best of 40 phases (decisions exist, not that the capture takes them); aperture step 8 ps, direction difference
up to 22 ps at ss-pess; KLU was compared with the default solver only on run time (the comparison job is in jobsQ.txt, not run);
ring tables tt480, tt675, ss315480, ff625 are flagged not settled (rc11 does not check the flag; none of them was used by a
reported cell); padc.json (linear) reads about 10 % high against the one transient; cap/p0probe/an.out was overwritten by a
traceback and the waveform deleted, so the tt full-rate timing numbers above have no file record (the reviewer's ff rerun and
the mechanism stand).  No clock-phase negative control has failed yet: neg=ph2m (0.45 UI) is queued in jobsS.txt.

NOT RUN (declared plan): 0.48 and 2.7 Gb/s cells, ff cells, ss350 at 2.5, ss-pess at 3.24 and at 3.50 V, T2 stimulus except the
ideal-clock proof, all-zero trim codes, sf / fs, high-metal pad, R+C netlists of our cells in the clocked chain, bench B beyond
ss315 2.5 Gb/s, PH0 / PH1 extra-load sensitivity.  Lists ready to run: chain/jobsQ.txt (full), ring/jobs3.txt; `./runq2.sh FILE`,
stop with `touch chain/STOP`.

Next steps in order: (1) ring owner on duty / spacing (WR11-2) - without it 2.7-3.24 Gb/s cannot close at the slow corner;
(2) equaliser r5: bias scheme + wide wiring, then R+C, resistor cross corners, sf / fs; (3) capture revision (lanes registered,
slot enables pipelined) or the decision to publish r7e as known-limited; (4) detect: wide trunks, pessimistic slow corner;
(5) ptrim: rest of the matrix + independent review, it is the closest to publishable; (6) fix the bench weaknesses above before
any pass from bench A is used for sign-off.

## Last results (09:36 UTC)
- neg=ph2m (PH2 0.45 UI late), tt 2.5 Gb/s T2: eye at D1's instant 84.8 mV, margin 0.025 UI (< 0.05) -> FAILS as required: the bench
  now has a failing clock-phase control (0.40 UI passed on the limit, 0.45 UI fails).
- ssp315 3.24 Gb/s T3: eye 57.9 mV, width 0, 42 / 108 wrong -> FAIL.  New: clock solve ssp315_810 (clk.json): with the real ring
  (duty 0.60-0.63) and pessimistic values pt_ptrim r10 at code 31 does not pull CKP low (low level 0.15-1.06 V, duty 0.69-0.86),
  "range" is negative, the solve picks codes [0, 26, 0, 0, 0, 31, 0, 0], trimmed spread 73.9 ps.  The ptrim sub-agent's
  pessimistic 810 MHz pass was with an ideal 50 % source.  -> ptrim r10 is not robust to the ring's duty at the pessimistic bound.
- Queues: all stopped, nothing of mine is running or queued.
