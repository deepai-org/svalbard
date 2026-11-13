# LO frequency-loop lock simulation: adversarial audit (2026-11-11, read-only)

Scope: the running "extracted lock" run `scratch/lo/r4_loop/sim/lock_g_kv120_x_tt27.spice` (ngspice PID 3941625, started 20:14),
the earlier `lock_bd_kv{40,120}_x_tt27` runs (README "lock in <= 29 us"), `lock_xmmd_kv120_x_tt27` (2 us),
`lcvco/run_loop.py` (deck generator and `analyse_lock`), `lcvco/loop_tl.json`, `lcvco/loop_design.{py,json}` (r4 jitter), README round 4.
No sims were run for this audit. All numbers below come from the files cited.

## Verdict

* The running deck **cannot show acquisition**. It starts with zero frequency error, VTUNE preset to the exact
  value that gives N*fref, and a phase offset copied from the previous run's static offset. So it starts already locked.
  The VCO is a behavioural B-source, not the QVCO. The PFD/CP netlist is superseded: the block was re-laid out at 21:37, after launch,
  and it has no LO18 ICP scaling. N=62 at 3.1 GHz is outside the guaranteed 2.30-2.70 GHz band.
  The deck runs one corner (tt/27 C/3.3 V) at a single Kv (120 MHz/V), with no fractional-N.
* **Stop or restart?** Don't restart this deck in any form. At ~7 us/h it reaches 15 us around 22:20 (10.85 us at 21:45). Letting it
  finish is harmless: one process, ~6.5 GB peak of its 8 GB limit. Its result may only be cited as "extracted MMD+PFD/CP(r-old)+LF holds a pre-aligned
  integer-N lock at tt without slips". It is not lock or acquisition evidence. If CPU is needed, kill it; nothing is lost.
* The README claim "lock in <= 29 us" is **not supported** by the recorded results. It was also never validated against a known answer, and
  no bench can fail (see #3, #4).

## Ranked issues

### 1. Lock is faked by the initial conditions (invalidates the 7 h run as lock evidence)
* `sim/lock_g_kv120_x_tt27.spice:23`: `GPH ... cur={120e6*(v(vt)-1.667) + 0}` (df0 = 0) and `:29` `.ic v(dphi)=-10.49 v(vtune)=1.667 v(vt)=1.667 v(xl.m1_4826_18962#)=1.667`.
  The VCO therefore starts at exactly 62 x 50 MHz. The C2 node is precharged to the matching VTUNE.
* The phase preset is not arbitrary. The previous 2 us extracted-MMD run (`loop_tl.json` lock[2]) measured static offset −3404.6 ps,
  and −3404.6 ps x 3.1 GHz = −10.55 VCO cycles, which is about the −10.49 used. The run starts near its own equilibrium phase.
* Fix: start from the band-search hand-off. Use VTUNE at a preset (e.g. 1.65 V) with the VCO off-target by the worst residual band-search error
  (at least half a band step plus Kvco x preset error, i.e. several MHz to tens of MHz at the LO, both signs). Set dphi0 = 0, or random. Never take
  the start state from a previous run's result.

### 2. VCO and loads are behavioural; the "extracted lock" has no extracted VCO
* `lock_g...spice:24-25`: `BLP/BLN = 1.7 ± 0.5 sin(2π(3.1e9 t + v(dphi)))`, ideal voltage sources. `run_loop.py:275` says so ("BEHAVIOURAL VCO").
  Consequences:
  - No QVCO r5 netlist and no real Kvco(VTUNE) curve. Kv is constant 120 MHz/V, while r5 measures 38-122 MHz/V across VTUNE.
  - The VCO has no start-up.
  - MMD input loading and kickback into the tank are absent, and so is the LO driver/mixer load (an ideal source cannot be loaded).
  - The VTUNE-node load from the varactors is absent.
  - Swing (1.0 Vpp diff) and CM (1.7 V) are assumptions. They are not the extracted QVCO PESS amplitude and CM.
* `IB vdd ib 10u` is an ideal bias, and VDD is an ideal 3.3 V source (`:13-14`). No regulator, no supply noise, no shared-rail ripple.
* Fix: in the final rung, use the extracted `qvco5` (or at least its tabulated f(VTUNE, band) per corner, with the measured
  Kvco curve) plus the extracted `lo_ext` driver load on LOI/LOQ and the MMD on the tank. Keep a behavioural VCO only for the fast rungs.

### 3. Lock criterion is self-referential and has no pass/fail (`run_loop.py:315-346`)
* `spo = median(dt[-20:])`, and lock time is "last ref edge where |dt − spo| > 2° (LO)". By construction, the end of the run counts as "locked",
  whatever state it is in. A slipped, drifting or false-locked loop that is merely quiet in the last 0.4 us passes.
* There are no limits, no `pass` field and no check that `n_fb_edges == n_ref_edges` over a window (the cycle-slip and wrong-N detector). The bd runs report
  `freq_err_last1us_hz` of −4.5 kHz and −1.5 kHz, so the loop is still moving at the end. It was not called unsettled.
* `freq_err_last1us_hz` is computed from the behavioural `v(dphi)` node, not from FB edges. If the divider stalled, it would still read ~0.
* Fix: compare absolute FB vs REF edge timing against limits fixed in advance. Require phase error < X ps for at least 5 us, and require
  a constant spo over two disjoint late windows. Check that edge counts match per window and that the FB period equals 1/fref ± tol. Add a `pass` boolean.

### 4. "≤ 29 us" claim does not match the recorded data; bench never validated on a known answer
* `loop_tl.json` lock[0] (bd, Kv 40): t_lock_2deg = 38.8 us, t_lock_10ps = 35.6 us. lock[1] (bd, Kv 120): 37.2 / 33.0 us. Both are in a 40 us run,
  so 1-3 us of post-lock data feed a criterion defined by the last 0.4 us. No recorded number is ≤ 29 us.
* The behavioural model in `loop_design.py` (`ix5_hops`) settles a 78 MHz hop to 2° in 7.5-12 us. The transistor bench takes 33-39 us for a
  2 MHz offset. A 3-5x disagreement is unexplained. Part of the cause: the hop model uses the stale LO13 filter (fc 400 kHz, `loop_design.json["loop"]`),
  not the r4 one.
* No ideal known-answer case exists (ideal PFD/CP + ideal RC + ideal VCO/divider vs the analytic fc/PM step response). No deliberately broken case
  (dead VCO, wrong N, CP disabled) was shown to fail. `loop_tl.json` holds only the 3 lock entries above.

### 5. Blocks are stale or superseded vs the published layouts
| Block | Used by running sim | Published now | Status |
|---|---|---|---|
| PFD/CP | `sim/lk_pfdcp.spice` (20:14, 141 MOS) = `g/genF/lo_pfdcp.ext.spice` | `generated/lo_pfdcp.ext.spice` 21:37, 129 MOS; `lo_pfdcp.spice` edited 21:36 (LO18 ICP legs) | **stale** |
| MMD | `sim/lo_mmd.ext.spice` (rewritten 20:16, after launch) | `generated/lo_mmd.ext.spice` 17:21 | same netlist + `add_rg` gate R; current, but the on-disk file is not what ngspice read |
| LF | `sim/lk_lf.spice` | `generated/lo_lf.ext.spice` 20:11 | current (diff is only the `lf__` prefix) |
| VCO | B-source | `qvco5` r5 RC-extracted | not used |
* Provenance is broken: `lock_bd_*.spice` and `lock_xmmd_*.spice` all have mtime 20:16, but their logs and outputs are from 19:52-20:08. The bd deck on
  disk lacks the `moscap_typical` .lib line that `lk_lf.spice` (cap_nmos_03v3_b) needs, so it cannot be the deck that ran.
  Every sim shares the scratch `sim/` dir, and `stage()` rewrites shared includes while runs are in flight.
* Fix: one directory per run, with copied includes and their md5 values recorded in the result JSON.

### 6. Parasitics: C-only plus a synthetic gate R
* `lo_mmd.ext.spice` (sim copy): 3205 C, 17 R. All 17 R are `add_rg` gate resistors (15 Ω/µm·W, `run_loop.py:28-45`), not extracted wire R.
  `lk_pfdcp.spice`: 555 C, 21 R (same origin). `lk_lf.spice`: 0 parasitic R. README limitation 9: "C-only extraction".
* Effect: the 3 GHz CML /2 and the first 2/3 cells see no wire RC. The MMD "16/16 pass at ss" margin, MMD delay and divider jitter are optimistic.
  The interconnect R/C are bounded only on the "no R" side.
* Fix: RC extraction (Magic `extresist`) of `lo_mmd`, at least the CML front end, then rerun the MMD toggle check at ss/32/3.15 and 3.1 GHz.

### 7. Frequency plan of the sim isn't the operating one; Icp not as designed (LO18)
* N=62 (`VN0..4=1, VN5=0`, ratio 2·31), so the VCO runs at 3.1 GHz. The guaranteed band is 2.30-2.70 GHz; the operating range is 2.40-2.4835 GHz, ratio ~48-50.
  The loop design uses N=49 and LO18 uses N 44-56. A higher N lowers the loop gain by 49/62 (−2 dB), so PM and lock time aren't the shipping values in either direction.
* Integer-N only: no MASH. The design is fractional (`ix5_hops` N=48.04/49.6, step 2 VCO cycles), and the CP linearity and on-time effects of
  fractional-N (t_on 2.2 ns, which the jitter budget assumes) are untested.
* Icp is a fixed 100 µA. LO18 requires 100·min(1, 60/Kvco), i.e. 50 µA at Kv 120. The Kv=120 run therefore uses about 2x the intended loop gain.
* Filter values: the README/r4 filter (R 13.09 k, C1 6.96 p, C2 351 p, R3 10 k, C3 15.9 p) matches `lk_lf.spice` (ppolyf L 13.09 µm ≈ 13.09 kΩ; C2 = n-well MOS cap array).
  `loop_design.json["loop"]` still holds the LO13 values (22.1 k / 5.19 p / 67.2 p, fc 400 kHz), and the hop and lock-time numbers in that file use them.
  `run_loop.py:385` defaults C2 to 347 p, while the README says 351 p. Small, but the file is inconsistent.

### 8. Single-sided bounding (coordinator addition)
Everything in the lock bench is one point: tt / 27 °C / 3.3 V / res, mim and moscap typical. Kv is {40, 120} but only 120 with the extracted MMD. N is 62, VTUNE ≈ 1.67 V.
| Uncertain quantity | Side that hurts lock or PM | Covered? |
|---|---|---|
| Kvco | High (OPT ff/22/3.35 not bounded; LO18: PM 9° at 200 MHz/V with fixed Icp) and low (38 MHz/V, slow lock) | 40/120 behavioural only; no OPT |
| Icp ±20 %, CP mismatch | High Icp → PM; mismatch > 1.03 % outside VTUNE 0.8-2.5 V | 100 µA nominal; VTUNE ~1.67 only |
| C2 (MOS cap, voltage-dependent) | Low C2 at low VTUNE moves the zero up → lower PM | Only at 1.67 V; not at 0.8 / 2.5 V edges |
| R (ppolyf) / MIM C1, C3 corners | Low R lowers PM; high C3 raises the pole interaction | res/mim typical only |
| Parasitic C on CP/VT nodes | Low C → less filtering (spur); high C → PM | C-only, one value |
| Wire R | Slower MMD edges, lower toggle margin | Absent |
| Supply 3.15-3.35, temp 22-32 | ss/32/3.15 MMD and CP headroom; ff/22/3.35 Kvco | Not run |
| N | 44 (highest loop gain) and 56+ | 62 only |
Jitter budget (`loop_design.py:255-310`, `loop_design.json["r4"]`):
* CP noise uses the **schematic** fork-F tt value (−125.1 dBc/Hz @10 k, `R4F_FLICK_IMPR = 33.5`). The extracted `g/cp_noise_ext.json` gives −124.7 (tt) / −125.7 (ss) /
  **−123.4 (ff)**. The worst extracted corner is 1.7 dB worse than the value used. ff is also the high-Kvco corner.
* VCO PN: −112 dBc/Hz@1 MHz is called "pessimistic", but the only measurement is −114.6 (tt RC-extracted) with **no flicker upconversion**. The PESS
  PN point was still running, so −112 is an assumption, not a bound.
* Divider/PFD jitter 0.3 ps, XO −150 dBc/Hz and fracN on-time 2.2 ns are all assumed. None is measured on the extracted MMD/PFD. The extracted UPB
  pulse is 0.26-0.52 ns, against the 0.193 ns base used for scaling.
* The budget uses N=49 and Icp 100 µA at fc 250 kHz. It isn't re-run with LO18 Icp scaling at Kv 120, or at N 44/56.
* Headline 0.72-0.84 ps vs a 1.05 ps limit leaves 0.2-0.3 ps of margin. A +1.7 dB CP term plus real flicker upconversion could use up most of that.

### 9. Simulator settings (minor, but they matter for a 2° criterion)
* `.tran 2e-11 15u`, no TMAX. ngspice then caps the step at min(tstep, span/50) = 20 ps, i.e. ~16 points per 322 ps VCO period. This is adequate for the B-source.
  The MMD edges come from LTE control. `.option interp` writes resampled data, and the log warns "Interpolated raw file data!".
* `reltol=1e-3` on the `dphi` node at ~10.5 V allows ~0.0105 VCO cycles = 3.4 ps of Newton/LTE tolerance. That is larger than the 2° LO criterion (1.8 ps)
  and the 10 ps criterion is barely above it. Fix: keep dphi near 0 (subtract the preset in the expression) or scale it to mcycles, and set `reltol=1e-4` on this bench.
* 15 us is shorter than the measured bd settling (33-39 us). An honest acquisition run needs ≥ 60 us plus a ≥ 10 us hold window.
* No `.save`: every node is stored. Memory was 4.7 GB at 10.85 us, with an 8 GB container limit.

## Minimal validation ladder (recommended, replaces the 7 h run)
Same harness, `pass` booleans with limits fixed beforehand, one directory per run, include hashes recorded.
1. **Known answer, all ideal** (B-source PFD + ideal ±Icp switches, ideal R/C1/C2/R3/C3 at r4 values, behavioural VCO + divider, N 49, Kv 60): compare
   fc/PM (from a small step) and lock time with `loop_design.py` analytic and `hop_sim` at the **r4** filter. Seconds to ~1 min.
   **Must-fail cases:** dead VCO (Kv 0, df0 −5 MHz), wrong N (bench N ≠ assumed), CP disabled. All must report FAIL. ~1 min each.
2. Swap in the **extracted LF** (current `lo_lf.ext`): ~1-2 min.
3. Swap in the **current extracted PFD/CP** (21:37, with the ICP code set per LO18), behavioural divider: the bd bench, ~20-40 min for 60 us.
   Sweep df0 ±(worst band-search residual), Kv {38, 60, 122, OPT-max}, N {44, 49, 56}, VTUNE end state near 0.8 and 2.5 V,
   at tt/27/3.3, ss/32/3.15, ff/22/3.35, and res/mim/moscap corners. The ~4 parallel slots cap this; prioritize ff+Kvmax+N44 and ss+Kvmin+N56.
4. **Extracted MMD (RC)**: first an open-loop MMD bench at 2.4-2.5 GHz with the QVCO PESS swing/CM (minutes). Then one closed-loop acquisition at the
   worst case from rung 3, at ~7 us/h, i.e. 60-70 us ≈ 9-10 h. Run it only after rungs 1-3 pass.
5. Final: the extracted QVCO (or its corner f(VTUNE) tables) with the `lo_ext` load. Run one fractional-N case (MASH on) at the worst corner, for
   spurs and lock. Expect many hours. Use fractional-N on the behavioural-divider bench first.

## Files
* Running deck: `scratch/lo/r4_loop/sim/lock_g_kv120_x_tt27.spice` (log `.log`, output `.txt` not yet written). `scratch/lo/r4_loop/g/lock.log` is empty (0 B).
* Generator: `projects/programmable_transceiver_platform/analog/timing/lcvco/run_loop.py` (tb_lock 273-313, analyse_lock 315-346, run_lock 349-380).
* Results: `.../lcvco/loop_tl.json` ["lock"]; jitter: `.../lcvco/loop_design.py` 255-310, `loop_design.json["r4"]`; extracted CP noise `scratch/lo/r4_loop/g/cp_noise_ext.json`.
