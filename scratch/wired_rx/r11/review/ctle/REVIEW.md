# Independent review: pt_ctle r4 and pt_rxselect r2 (staged, unpublished)

Reviewer: independent agent, 2026-11-18. Read-only on `projects/` and `scratch/wired_rx/r10ctle`; nothing committed.
Work directory `scratch/wired_rx/r11/review/ctle/` (scripts `rb.py`, `rbq.py`, `rv.py`; logs `*.log`; results `res/`).
Paths below: P = `projects/programmable_transceiver_platform`, W = `P/analog/wired_rx`, S = `scratch/wired_rx/r10ctle`.

STATUS OF THIS FILE: sections 1-6 written 07:05 UTC; section 7 (late results) is appended as the last queued
jobs finish. Where a section says "section 7", the number had not returned when the section was written.

## 1. Verdict

| Cell | Verdict | In one line |
|---|---|---|
| `pt_ctle` r4 | **NO-GO to publish today.** The layout is not the reason. | The amplifier core loses 3.5-7.6 dB on a die whose poly resistance is high once the bias is trimmed to 10 uA as the bias README prescribes; every chain result predates the pad republication (PC-22); R+C extraction is absent. |
| `pt_rxselect` r2 | **GO with conditions**, but it cannot be published alone. | The cell is small, clean and matches its schematic. Its port list drops `CTLE_P/N`, so it only makes sense together with `pt_ctle` r4. |

What would turn `pt_ctle` r4 into GO, without touching the GDS if the first item is answered by a bias policy:

1. Close finding F1 (bias current x load resistance): either a written bias rule for the wired island that keeps
   I x R nominal (see F1 for candidates) with the gating cases rerun under it at resistor cross-corners, or a
   circuit change (then a new layout and this review again).
2. Rerun the gating chain cases with the valid pad model `physical-r-typ.spice` and its bounds (F2).
3. R+C extraction of the cell and the sf / fs corners, as the evidence audit now requires (section 5).
4. Fix the LVS pass criterion before the publish run writes records (F3).
5. Record the deep n-well dependence against INT-30 with the numbers of F5.

Conditions for `pt_rxselect` r2: publish in the same change as `pt_ctle` r4 with the rebind of `pt_chip.conn`,
`PINS.md`, `sims.py` and `chip_assembly/netlist.py`; R+C extraction and sf / fs for the direct path; LVS record
that states "no property errors"; the decode rule of F8 written into the mode table.

## 2. Findings, ranked

Severity: H = blocks publication or invalidates stored evidence; M = must be fixed or accepted in writing;
L = record it.

### F1 (H). The core's operating point depends on IBIAS x R_load, and the documented bias trim removes the tracking

Where: `W/netlists.py` `ctle()` lines 289-304 (IBIAS -> x2.5 -> x100 tails, 2.5 mA per side), loads
`CTLE_RL_*` = 480 ohm of `ppolyf_u_1k` plus a 21 um switch, nodes `cp` / `cn`; follower and sink behind them.

Mechanism: `cp` common mode = I_tail x (R_load + R_switch). The input pair's drain-source voltage is
V(in) + Vsg - V(cp). At the HS_VBIAS of 0.98 V the pair has 60-330 mV above its saturation voltage at nominal
I x R and goes into triode when I x R rises by 5-20 %, depending on the MOS corner. Nothing regulates `cp`.
The same core is in the published r3; r4 adds that the SL common mode follows `cp`.

Why it matters now: `P/analog/core_support/README.md` says the bias generator's current follows the poly
resistor (7.5-12 uA untrimmed) and is trimmed per die to 10 uA (`idac2_source` = round(100 uA / I_meas)).
Untrimmed, I is proportional to 1/R and I x R_load stays nominal. Trimmed to an absolute 10 uA, a die with
+20 % poly resistance has +20 % on `cp`. The benches hide this: they feed IBIAS through 260 k from the rail
(8.1-9.7 uA), which happens to be close to the untrimmed tracking value at the slow-resistor corner.

My runs (extracted staged cell, old pad + package + sampler bank as in `ch10.py`, code 0, gain source-EMF/2 -> SL
at 1.25 GHz; "pair" = Vds / Vdsat of an input-pair finger; `opac_a.log`, `opac_b.log`, `bias2.log`):

| MOS / resistor / supply | bench bias (260 k) | ideal 10 uA | 10.5 uA | 11 uA | 12 uA |
|---|---|---|---|---|---|
| tt / typ / 3.30 | +1.99 dB, pair 0.86/0.55, SL 0.46 V | +2.14, 0.76/0.58, SL 0.55 | - | - | -2.20, 0.56/0.67, SL 0.79 |
| ss / slow / 3.15 | +2.03, 0.93/0.55, SL 0.41 | +1.5..+2.4 (two runs), 0.69/0.62, SL 0.64 | +0.24, 0.63/0.64 | -1.92 | -5.34, SL 0.88 |
| ss / slow / 3.50 | +2.52, SL 0.58 | +1.1..+2.0, 0.68/0.63, SL 0.66 | -0.41 | -2.81 | -6.88, SL 0.94 |
| ff / fast / 3.35 | +0.73, SL 0.43 | +0.88, 0.85/0.54, SL 0.46 | - | - | +0.68, SL 0.64 |
| sf / typ / 3.15 | +0.58, SL 0.31 | +1.02, 0.64/0.57, SL 0.47 | - | - | -6.32 |
| fs / typ / 3.15 | +2.29, SL 0.49 | +2.79, 0.91/0.60, SL 0.61 | - | - | +1.56, SL 0.83 |
| **tt / slow (+20 %) / 3.30** | - | **-1.32**, 0.53/0.60, SL 0.79 | -4.27 | -7.06 | - |
| **ff / slow / 3.35** | - | **-6.74**, 0.40/0.60, SL 0.94 | -9.64 | - | - |
| **sf / slow / 3.15** | +1.69 (8.3 uA), SL 0.46 | **-5.38**, 0.44/0.61, SL 0.70 | -8.22 | - | - |
| sf / slow / 3.35 | +1.81 at 8.3 uA | -6.19 | -9.09 | - | - |

Reading: with the tracking (untrimmed) bias every corner I ran is fine. With the trimmed 10 uA a typical-MOS or
fast-MOS die with slow resistors loses 3.5 to 7.6 dB and its SL common mode leaves the 0.38-0.66 V range the
sampler was requalified for. The slow-MOS corner the author ran survives at 10 uA with 60-70 mV of margin and
loses 1.3-2 dB at +5 % (one trim step). The two ss values at 10 uA come from the same deck solved after a
different bias sequence (v(inp) differs by 3 mV): at this edge a few millivolts of imbalance move the gain by
almost 1 dB, which is itself part of the finding. Fast-resistor cross corners did not converge in my bench
(90-200 s limit); by the same arithmetic they are the benign direction (low `cp`, SL about 0.36 V).

The author's STATUS row CTLE-R4-BIAS does say "above 10 uA at ss is not verified". It does not say that the
resistor corner, not the bias current, is the governing variable, nor that the documented trim is the bad direction.
Resistor corners are a known open sweep (risk MOD-19).

Options, cheapest first:
- Bias rule for wired-RX modes: do not use the absolute trim; choose the `idac2` code per die so that the SL
  common mode, observed through `pt_wmon_sel` (CTLE taps = SL) on the WMON pad, sits at 0.45-0.55 V. This needs
  no layout change but is a per-mode bias code and must be written into the bring-up procedure; other blocks on
  the same root reference then run at that code too while the wired mode is active.
- Raise the input common mode. HS_VBIAS at 1.10 V gives ss/3.15: +2.50 dB at 10 uA, +2.32 at 10.5, +1.69 at
  11 uA (pair 0.81/0.61), but sf / slow resistor stays bad (-0.66 dB at 10 uA, -3.66 at 10.5), and at 1.2 V the
  tail runs out at ss/3.15 (0.41/0.38). So it helps and does not close it. HS_VBIAS is on the ATB, so it can
  be forced on a die for diagnosis. (1.2 V cross-corner rows: section 7.)
- Circuit: give the tails a local reference that tracks the load poly (or a `cp` common-mode loop), or design
  `cp` 250-300 mV lower. Layout change, new review.

Also true and smaller: the documented input window "CM 0.8-1.4 V" (`ctle.spice` header) does not hold at ss/3.15:
at 0.8 V the pair is in triode (-2.43 dB at 1.25 GHz against +2.4), at 1.4 V the tail is (0.27/0.38).

### F2 (H). Every stored chain result uses a pad model that is now declared invalid (PC-22)

`S/ch10.py` line 21 binds `.../wired-receive-hs/physical.spice` (sha 320c43d9, capacitance only, 103 ohm at code
5). PC-22 (interface-changes.md line 1650, published today) replaces it by `physical-r-typ / -high / -low.spice`:
100 ohm termination, 1.27-1.31 pF per leg, 1.5-1.7 dB more loss bond pad -> RX_P/N. All of `chain_ac.json`,
`chain_pda*.json`, `chain_tran.json`, `chain_rl.json`, `rel.json`, `whatif.json` are affected; `ac.json`
(25 ohm source, no pad) and `slicer.json` are not.

Expected effect, before my own numbers in section 7: about 1.5-1.7 dB less at SL at every rate. The stored
margins against the 60 mVppd / 0.25 UI limits that this can consume: 3.24 Gb/s T3 two banks at ss 72 / 71 mV
(0.33 UI); 2.7 Gb/s T3 two banks ss-pessimistic 74 / 72 mV (0.35 / 0.30 UI); 3.24 Gb/s T3 one bank
ss-pessimistic 83 mV. 1.25 and 2.5 Gb/s have 105-340 mV and should survive. The `padr=40` cells of the STATUS
(under-terminated pad raising the eye by 8-15 %) describe a pad that no longer exists and must not be quoted.

Must be rerun with the new model at code 6: chain AC all corners and codes (minutes), code pick, all gating
transients (48 cells, 2-5 min each), return loss, operating points. Add `-high` and `-low` at the corners that are
tight.

### F3 (H for the flow, no defect found in these two cells). `wrx_flow.lvs()` passes parameter errors

`W/wrx_flow.py` lines 647-659: `unique = 'Circuits match uniquely.' in text` and the final-result regex.
Netgen prints "Final result: Circuits match uniquely." followed by "Property errors were found." when a W, L,
resistor length or multiplier is wrong. My negative controls on the read-back extraction (`lvsall.log`,
`lay/<block>/<block>_neg_*.lvs.txt`):

| Reference changed | netgen | wrapper says |
|---|---|---|
| follower P body on VSS (the author's control) | failed pin matching | fail (correct) |
| follower outputs swapped | failed pin matching | fail (correct) |
| follower finger W 10 -> 9 um | match uniquely + property errors | **unique_match = True** |
| one load strip 2.88 -> 2.4 um | match + "parallel/series network does not match" | **True** |
| one sink device m = 2 -> 1 | match + property errors | **True** |
| rxselect clamp W 2 -> 1 um | match + property errors | **True** |
| rxselect: one gate terminal moved SL_P -> SL_N | failed pin matching | fail (correct) |

So the mandate's "device parameters compared" is done by netgen and then discarded by the wrapper; the author's
only negative control was a connectivity one and could not show it. For the two staged cells I read the reports
themselves: "Netlists match uniquely.", no property-error line, in the author's four reports and in mine. Every
other LVS record produced through this wrapper (all wrx_flow blocks, and `lay10.py`'s `lvs_mag` / `readback`
fields) deserves a grep for "Property errors". Fix: require the absence of that line, and keep one parameter
negative control per block.

### F4 (M). Evidence that is missing or does not cover what will be built

- **Built mode above 2.5 Gb/s.** The 05:35 amendment moved 2.7 / 3.24 Gb/s to an eighth-rate, two-bank
  architecture (R8-ARCH) that is not built, and removed the 675 / 810 MHz ring from the sampler gate S-G1. The
  owner's r11 plan is back on the built hardware (quarter rate, ring 675 / 810 MHz, one bank). For that mode r10
  holds two transients (`ssp315_3.24G_T3_b1` 82.6 mV, `tt_3.24G_T3_b1` 122 mV), run with eighth-rate ideal clocks,
  and no sampler result at those ring rates. The amendment was made after the 25 ohm AC table existed (05:30) and
  before the first chain transient (05:41) and sampler run; it tightened the CTLE's load and loosened the sampler's
  clock. It is labelled as an owner instruction and I take it as such.
- **Declared fail, reported as fail:** 3.24 Gb/s two banks at ss-pessimistic, T2 and T3, 3.15 and 3.50 V
  (49-69 mV, 1-2 errors). Not moved. Good.
- **Peaking gate passed by its letter only.** Gate: code-0 peaking <= 2 dB "at ff optimistic (flat setting must
  exist)": 1.83 dB there, but 2.02 ff, 2.39 tt, 2.45-2.60 ss, 2.35-2.50 ss-pessimistic (`chain_ac.json`,
  reproduced). The purpose in the bracket is missed at six of seven corners; the author says so (WRX-27).
- **Safety window not run for r4:** 0-3.63 V ramps, 0 and 85 C, power-up with enables high. Off-state current at
  ff is unverified (the operating point does not converge; mine ran > 6 minutes at ff/3.50 and was killed).
- **Not run at all:** mismatch / offset (see F9), noise, supply rejection, resistor corners (F1), R+C extraction,
  the 13-corner `run_family` matrix, `tb_ctle` with the real load, real clocks and capture (r11 is on it).
- **Nominal corners carry no gate resistance** (mandate section 3 asks for explicit Rg in high-speed sims); only
  the ss-pessimistic copies have it (200 ohm per 10 um, `r7slicer/pess.py`). The gating set includes
  ss-pessimistic, so this flatters tt / ss / ff by a few tenths of a dB and not the gate itself.
- **Bit-error check is lenient:** the output read phase is the best of 20 per run and the clock sits on the
  eye centre computed from the same AC data; 104-120 bits, no noise, no offset. Fine as a function check, not a
  margin.
- **Hashes:** only `chain_tran.json` carries netlist hashes (62 of 62 entries match the staged files and the old
  pad). `ac.json`, `chain_ac.json`, `chain_pda*.json`, `rel.json`, `whatif.json`, `chain_rl.json` carry none;
  `S/run/*.log` were partly overwritten by the `f2` variant (same tags). My reruns show the AC and operating-point
  rows do correspond to the staged netlists (section 4).
- **LVS negative-control record** (`ctle-lvs-negative-control.txt`, 05:13) predates the final build (05:20).
- **Declared-before-run claim:** STATUS.md is not in git and has one mtime (08:42), so the claim cannot be proven.
  The run timeline in `S/run/` is consistent with it (bench proofs 05:00, first transient 05:41, sampler runs
  after the amendment).

### F5 (M). Deep n-well: what depends on it

The two followers sit in isolated p-wells (body = source = SL), each in a DNWELL island tied to `VDD_WIRE_SW`.
Mandate section 3 / risk INT-30: DNWELL is in the PDK and the precheck deck but not confirmed in writing.

- With the option available: body effect removed. Against the same extraction with the follower bodies on VSS
  (my variant `net/ctle_nodnw.spice`, `whatif.log`): tt +1.99 -> +0.55 dB at 1.25 GHz, ss/3.15 +2.03 -> +0.63,
  ss-pessimistic +0.13 -> -1.06, ff +0.73 -> -0.64; SL common mode 50-90 mV lower (0.40 / 0.355 / 0.38 V, the ss
  value below the requalified 0.38 V). So DNWELL buys 1.2-1.5 dB. The owner's own `r11/nodnw` gives the same
  numbers. A follower without the island is therefore a working low-risk alternative at about 1.4 dB cost; the
  STATUS does not state it, which mandate section 1 asks for when something non-standard is used.
- If the layer were silently not processed, the staged layout is not that alternative: the body ring of each
  follower is strapped to SL, so each SL leg would get a resistive path into the substrate through its p-taps
  (not modelled; my estimate is of the order of a kilohm) in every mode, including the USB direct path that
  shares SL, and the body effect returns. Degraded, probably not dead; unverified.
- The well junction is in the benches (`lib10.well_lines`: `diode_pw2dw`, 89.2 um2 / 39.9 um per side, matches
  the p-well rectangle in the primitive). Magic's extraction contains no DNWELL diode and leaves an unnamed node
  per island; tying those nodes to the rail changes nothing (tt row identical to 0.01 dB).
- The DNWELL-to-rail tie cannot be seen by LVS (the device has four terminals). A floating n-ring would pass.
  Node query on the GDS: see section 7.

### F6 (M). Follower sink runs in triode; the "mirror" does not set the current

`CTLE_SK` 60/0.5 um per side with the diode at Vgs 1.24-1.54 V: Vdsat 0.45-0.61 V against an SL common mode of
0.25-0.66 V. Sink Vds / Vdsat: tt 0.46/0.52, ff 0.43/0.51, sf 0.31/0.51, ss 0.41/0.51 (bench bias). Consequences:
the follower loses 1.1-2.6 dB instead of about 0.5 (sink conductance 1.2-4 mS against a follower gm of 8-11 mS),
that loss moves with the SL common mode, and rail noise on VSS / `fbias` reaches the SL common mode directly.
The author states the triode condition. A three times wider sink and diode (same ratio) would saturate at 0.3 V
for about 60 fF more on SL; not required for function.

### F7 (M). Reliability of the follower at the trimmed supply

Continuous Vds 2.5-3.0 V (3.24 V at ff/3.50 with low bias), Vgs about 1 V, 50 uA/um, L 0.28 um: close to the
worst hot-carrier bias; the PDK has no model. Below 3.63 V at every point I ran, as the author says
(WRX-25). Device voltages over a transient were not extracted by the author or by me; no node is bootstrapped.

### F8 (M). States that float or fight are left to the digital decode

- `rxselect_en` = 1, direct = 0, CTLE off, bypass off: nothing drives SL (author's WRX-29). No hardware interlock.
- `ctle_en` = 1 with `rxselect_en` = 0 (follower into the 2 um clamp) or with direct = 1 (follower into the USB
  line through the gate): current, no damage expected; numbers in section 7 if they converge.
- Bypass: RX common mode (0.98 V) lands on SL; the sampler's published plan at 1.0 V covers it. The follower then
  sits at Vgs -1 V, Vgd -VDD: within limits.
- No loop, no latch: the bias chain is open-loop mirrors with pull-downs when off.
These rules exist only as proposed row CTLE-R4-DIG in the STATUS; they are not in interface-changes.md.

### F9 (L). Matching of the differential path

Verified from my own extraction (identical to the staged one within 0.3 fF): RX_P / RX_N 97.6 / 95.2 fF,
`cp` / `cn` 65.4 / 65.4, CTLE_P / N 105.0 / 101.5, `sp` / src 437 / 410. Not in the author's symmetry record:
RX_N-CTLE_P 7.2 fF against RX_P-CTLE_N 2.2 fF; RX_P has 42 fF to the rail and 21 fF to ground where RX_N has
9 and 37; `ctle_en` couples 7.7 fF to CTLE_P and 9.8 fF to RX_N. All small against 0.65 pF on SL and 1.3 pF at the
pad. In `pt_rxselect` SL_P / SL_N carry 38.7 / 25.1 fF of wiring (2 % of the SL load). The two half circuits are
separate rows 51 um apart, not interdigitated; no offset or mismatch run exists. Hand estimate, unverified:
load strips (1.2-1.9 V of drop on 6 x 2.9 um2 of poly) and the 60 um followers give several millivolts sigma at
SL, which the sampler trim (+/-50 mV) has to absorb together with its own offset.

### F10 (L). Smaller points

- Magic prints 14 extraction warnings on the cell ("device missing 1 terminal; connecting remainder to VSS").
  They are the 14 low-frequency-zero MOS capacitors (source = drain = VSS), present since r3; LVS agrees. Neither
  the author's records nor the flow mention them.
- The chain decks produce singular-matrix warnings at every operating point (a floating node inside the old
  pad model, and the two DNWELL nodes). Results reproduce, but solutions depend on the path (F1, two values).
- `stage/gen/ctle-layout.json` records an older `netlists.py` hash; the emitted `ctle.spice` is identical
  (checked: regenerated text = file = recorded source hash).

## 3. Layout on disk against the claims (what I re-ran)

| Check | pt_ctle r4 | pt_rxselect r2 | Stored record |
|---|---|---|---|
| sha256 of the GDS | 469dd090...2af8 | 8f53c1a7...8c0b | equal in `*-layout.json`, `*-kldrc.json`, read-back record |
| Magic 8.3 (digital image) `gds read` -> DRC full | 0 | 0 | 0 / 0 (author used the analog image) |
| Extraction from the read-back | 315 devices + 8 diodes, 1410 C | 14 devices, 63 C | same device multiset, C within 0.3 fF |
| Netgen LVS, reference built by me from `W/*.spice` + flow diodes | match uniquely, no property errors | match uniquely, no property errors | same |
| My reference = staged `lvs_reference.spice` | sha 32360508 equal | sha b44b6212 equal | - |
| Negative controls | 2 connectivity fail; 3 parameter ones flagged by netgen | 1 / 1 | see F3 |
| KLayout precheck, main + antenna, private dir | 0 / 0 (733 rule executions) | 0 / 0 | 0 / 0 |
| Antenna diodes | 8 in layout and reference, none unplaced | none needed | same |

Not re-run: the layout generation itself, the full KLayout deck of the export step, fill, density.

Electromigration (records read and hand-checked, not extracted): tracks and trunks are sized from stated currents
x 1.3 against 2.09 mA/um (Metal1-4), 4.5 mA/um (Metal5), 0.58 mA/cut (P/spec/power-delivery.md). The currents I
measured stay inside the design values at nominal bias (follower 2.7-3.2 mA per side against 3.0 x 1.3; tails
about 2.8 mA against 2.5 x 1.3; supply 12.3 mA at ff/3.50 against trunks good for 14.9 / 15.3 mA). At 12 uA the
follower reaches 3.9 mA per side and the supply 14.7-15.0 mA: at the limit, no margin. The follower primitive
collects each drain / source strip on Metal1 + Metal2 into a 6 um Metal3 bus with eight escapes (0.4-0.5 mA each).
Device-internal Metal1 of the ordinary single-finger devices is unchecked, as the author says.

Wells and latch-up: each island is p-well 6.78 x 13.16 um inside a continuous 1 um n-tap ring (drawn N-well),
DNWELL 12.18 x 18.56 um, then a continuous 0.8 um p-tap ring 2.6 um outside the DNWELL. KLayout's DNWELL / LPW
rules are clean. The two islands are 51 um apart and share the rail potential.

## 4. Simulations re-run against stored numbers

All on the staged extraction, the same benches (`lib10` / `ch10` deck builders imported read-only), host ngspice-42.

| Case | Stored | Mine |
|---|---|---|
| chain AC tt code 0: 20 MHz / 625 MHz / 1.25 / 1.62 GHz, peak, SL CM, supply | +0.53 / +2.64 / +1.99 / +0.04, 2.92, 0.457 V, 10.69 mA | +0.53 / +2.64 / +1.99 / +0.04, 2.91, 0.457, 10.71 |
| ss/3.15 code 0 | +1.21 / +3.72 / +2.03 / -0.48, 0.407 V | +1.21 / +3.72 / +2.03 / -0.49, 0.407 |
| ss/3.50 code 0 | +1.78 / +4.14 / +2.52 / +0.06, 0.582 | +1.78 / +4.14 / +2.52 / +0.05, 0.582 |
| ff code 0 | -0.91 / +0.68 / +0.73 / -0.61, 0.431 | same to 0.01 dB |
| ss-pess 3.15 code 0 | +1.11 / +3.60 / +0.13 / -3.08 | +1.12 / +3.59 / +0.13 / -3.05 |
| ss-pess 3.50 code 0 | +1.70 / +4.04 / +0.65 / -2.54 | same |
| tt code 7 | -13.27 / +3.44 / +2.62 / +0.41 | same |
| operating points (`rel.json`), tt / ss / ff, bench bias and ideal 10 uA | e.g. ss/3.15 10 uA: SL 0.639, cp 1.862, 11.90 mA | 0.640, 1.861, 11.88 |
| transient tt 2.5 Gb/s T2 | 297.5 mV, 0.80 UI, 0 / 120, SL CM 0.461 | 297.5 mV, 0.80 UI, 0 / 120, 0.461 (154 s) |
| transient ss-pess 3.15, 2.5 Gb/s T3, bench bias | 124.0 mV, 0.55 UI, 0 / 120, SL CM 0.407 | not re-run |
| same with an ideal 10 uA (new) | - | 115.3 mV, 0.525 UI, 0 / 120, SL CM 0.639 |

New corners (not in the stored set), bench bias, 1.25 GHz: sf/3.15 +0.58 dB with SL at 0.31 V; sf/3.35 +1.27,
0.39 V; fs/3.15 +2.29, 0.49 V; fs/3.35 +2.87, 0.59 V. With 10 uA: SL 0.47 / 0.50 / 0.61 / 0.64 V.

## 5. Where metal resistance sits (for the R+C rerun)

The staged extraction is capacitance only (0 resistors in `ctle.ext.spice`). Estimates below use the extraction
file's own sheet values (90 mohm/sq Metal1-4, 40 mohm/sq Metal5), the widths in `ctle-em-widths.json` and the row
geometry in `ctle-layout.json` (trunks at x = 47-86 um, rows up to 200 um wide, pins on the top edge). They are
hand estimates, not extraction.

`pt_ctle`:
- **Supply rail to the tail rows (most important).** `VDD_WIRE_SW` tracks of rows 5-7 are 0.9 / 1.4 / 0.9 um wide
  and about 200 um long, fed from the trunk at one end: 13-20 ohm end to end with 1.4-2.3 mA distributed, so
  7-15 mV average, up to 30 mV at the far fingers. The tail fingers (Vov 0.35 V) lose about 3-8 % of current
  relative to the bias diode, which sits in a low-current row. P and N tail fingers alternate, so the differential
  error is small; the common current, hence `cp` and the SL common mode, shifts by that much. This goes the
  helpful way for F1 and must be in the numbers.
- **Ground of the sink / load-switch row.** `VSS` track of row 11, 7 um wide, 11 mA: about 15 mV at the far end
  against a diode in a quiet row: sink current about -4 %, load-switch sources lifted by the same.
- **Trunks.** `VDD_WIRE_SW` 3.3 um and `VSS` 3.4 um Metal5 over up to 200-380 um: 2.5-4.5 ohm, 30-55 mV at 12 mA
  between the pin and the lowest rows. Counts against the island's drop budget (117 mV for the whole grid).
- **Follower output to the pin (signal).** Metal3 bus, eight escapes, Metal4 track 1.9 um (about 5 ohm over
  100 um), Metal5 trunk 1.5 um over 90-140 um (2.5-4 ohm): 5-10 ohm in series with a follower output resistance of
  90-125 ohm into 0.65 pF: at most 0.2-0.3 dB at 1.6 GHz. The sinks hang on the same trunk in row 11, so the
  3 mA flows along it: 10-20 mV, no effect.
- **Input (signal).** RX_P/N trunk 0.44 um Metal5 from the top edge to rows 9 / 10 (about 140 um, 12 ohm) plus a
  0.4 um Metal4 track to six gate fingers (10-20 ohm), into about 0.15 pF of gate: pole above 20 GHz. In bypass
  mode the path is short (gate in row 11).
- **Gate resistance** of the 16 um pair fingers and 10 um follower fingers (contacted on one end): not in any
  extraction; the pessimistic copies add 200 ohm per 10 um.
- **Core nodes** `cp` / `cn`: local to one row on 1.6 um tracks, a few ohm against 480 ohm: below 1 % of gain.
- **Degeneration ladder** (`sp` / src tracks 0.4-0.7 um over the ladder row): a few ohm against 400 ohm at code 0:
  about 1 % of the code-0 low-frequency gain; nothing at the higher codes.

`pt_rxselect`: the direct path runs RX -> 0.4 um track / 0.44 um trunk -> 10/20 um gate -> SL, 10-20 ohm of metal
per side in series with the gate's on-resistance and the 45 ohm line. That is 10-20 % more series resistance on the
USB direct path (480 Mb/s; stored bandwidth 0.71-0.89 GHz with the powered-down CTLE on SL), worth extracting. In
CTLE mode the cell is a stub on SL and its metal resistance only sits in series with its own 25-39 fF.

An R+C rerun must therefore cover, in this order: operating points (tail and sink currents, `cp`, SL common mode)
at the corners of F1; chain AC at code 0 and 7; the direct path through `pt_rxselect`; supply drop pin to rows.

## 6. Interface items that are not written down (or only proposed in the STATUS)

1. **IBIAS:** value after trim, step (+/-5 %), and the rule of F1. The bias bank is an uncascoded 1:1 PMOS source,
   10.06-10.15 uA after trim, 7.5-12 uA before. Budget: supply 12.1 mA at 10 uA, 14.3-15.0 mA at 12 uA.
2. **SL common mode delivered:** 0.46-0.66 V over ss / tt / ff / sf / fs at 10 uA and nominal I x R; 0.25-0.36 V at
   7.5 uA; up to 0.79-0.94 V in the F1 cases. Sampler requalified for 0.38-0.66 V and 1.0 V only. Sampler offset
   trim must be calibrated at the operating common mode and absorbs the CTLE's offset.
3. **Pad:** bind `physical-r-typ.spice`, termination code 6; HS_VBIAS 0.95-1.01 V is at the low edge of what
   the pair wants at ss (F1); state its tolerance. HS_TERM_VCM and HS_VBIAS are ideal sources in every bench.
4. **Route budgets used:** SL <= 30 fF per leg (+60 fF to a second bank), HS_RX <= 20 fF per leg, lumped, no
   resistance. These are constraints for the assembly, not results.
5. **Decode rules** (F8) and the reset state; `EN_ctle` of the bias bank follows `c_ctle_en`, so in bypass with
   `ctle_en` = 1 the IBIAS pin sits at the rail (harmless, 3.5 V across one off switch).
6. **Observation:** `pt_wmon_sel`'s CTLE taps now look at SL (0.4-0.66 V) instead of 1.3-1.66 V; the WMON buffer
   owner should confirm its input range there. `atb_ctle_pbias` now also sets the follower current; connecting
   the ATB to it in mission mode disturbs both.
7. **Tree consistency:** `pt_chip.conn` lines 417-424, `PINS.md`, `sims.tb_ctle` / `tb_rxselect`,
   `chip_assembly/netlist.py`, the README still describe CTLE_P/N -> rxselect. Publishing the cells without them
   breaks the top-level checks.
8. **Deep n-well** islands on the switched island rail inside `pt_ctle` (INT-30); fill keep-out over the two
   matched rows and the islands is not declared.
9. **Two-bank load (R8-ARCH):** undecided (`CTLE_SF_N` = 2 variant exists with thin evidence).

## 7. Late results

### 7.1 Well ties (Magic node query on the GDS read back, `rbq2.log`)

Both islands: the n-tap ring (top and bottom bars probed) is on `VDD_WIRE_SW`; the drain bus is on
`VDD_WIRE_SW`; source buses on `CTLE_N` (island at y = 314-333 um) and `CTLE_P` (y = 365-384 um); gate bars on `cn`
/ `cp`. So the DNWELL is tied to the rail in the layout on disk. My probe points for the side bars, the body ring
and the outer p-guard ring missed their shapes; the body tie is covered by LVS (body = source net), the p-guard
ring's metal tie to VSS is not independently confirmed.

### 7.2 Mode states (`modes_tt.log`, old pad model, tt unless stated)

| State | CTLE supply | SL common mode | Note |
|---|---|---|---|
| CTLE on, `rxselect_en` = 0 (follower into the clamp) | 11.6 mA (bench bias), 13.1 mA (10 uA): +0.9..1.0 mA | 0.42 / 0.51 V | harmless |
| CTLE on, direct = 1 (follower into the 45 ohm USB lines at 0.2 V) | 12.0 / 14.1 mA: +1.3..2.1 mA | 0.39 / 0.46 V | harmless; corrupts the USB path |
| bypass | 20 uA at tt | 0.98 V | see F11 |
| USB direct, CTLE off, ff/3.50 and ss/3.50 (with a 1e11 ohm shunt option to get convergence) | below 5 nA | 0.20 V | HS input -> SL feedthrough -55 / -51 dB at 1.25 GHz |
| `rxselect_en` = 0, CTLE off, same corners | below 5 nA | 0 V | feedthrough -54 / -50 dB |

The tt off states without the shunt option, and the floating state, did not converge within 90 s in my bench. The
author's 7-18 uA off current and my 20 uA in bypass against "below 5 nA" with the shunt option suggests the
microamp figure is a floating-node artefact (`sp` settles at 1.35 V without the option, 0.75 V with it) rather than
leakage. Not resolved.

### F11 (M, new). Bypass mode loses 2-4 dB flat and 5-6.5 dB at 1.25 GHz behind the real pad

The STATUS quotes "bypass 0 dB, bandwidth 1.12 GHz" from the 25 ohm source bench (`ac.json`). Through the pad
(on-die coupling capacitor) the 0.65 pF of SL forms a capacitive divider: source-EMF/2 -> SL at 20 MHz / 1.25 GHz
is -3.0 / -5.9 dB at tt, -2.1 / -5.3 dB at ss/3.50, -4.2 / -6.5 dB at ff/3.50 (old pad model; the new one adds its
1.5-1.7 dB). Bypass is the fallback and observation path for the HS input, so its real level belongs in the
README and in the sampler's sensitivity budget.

### 7.3 Chain AC with the republished pad (`pad.log`; `physical-r-typ.spice`, termination code 6, one bank, code 0)

| Corner | old pad: 20 MHz / 1.25 / 1.62 GHz | new pad typ | new pad, other bound |
|---|---|---|---|
| ss/3.15, bench bias | +1.21 / +2.03 / -0.49 | -0.21 / +0.36 / -2.28 | - |
| ss/3.15, 10 uA | +1.9 / +2.4 / -0.1 | +0.49 / +0.68 / -1.88 | - |
| ss-pess 3.15, bench bias | +1.12 / +0.13 / -3.05 | -0.29 / -1.60 / -4.95 | high: -0.24 / -1.92 / -5.47 |
| ss-pess 3.15, 10 uA | +1.72 / +0.41 / -2.72 | +0.41 / -1.23 / -4.50 | high: +0.46 / -1.55 / -5.02 |
| ff/3.35, bench bias | -0.91 / +0.73 / -0.61 | -2.49 / -0.97 / -2.40 | low, 10 uA: -2.35 / -0.82 / -2.22 |
| sf / slow resistor / 3.15, 8.3 uA | +0.74 / +1.69 / -0.66 | +0.04 / +0.90 / -1.51 | - |
| sf / slow resistor / 3.15, 10 uA | -4.55 / -5.38 / -7.10 | -5.28 / -6.22 / -7.98 | - |

The new pad costs 1.4-1.6 dB at 20 MHz, 1.7 dB at 1.25 GHz and 1.8-1.9 dB at 1.62 GHz (2.0-2.4 dB at the high
metal bound), i.e. 18-24 % of amplitude. Applied to the stored eyes: the 71-74 mV cells (3.24 Gb/s T3 two banks at
ss/3.15 and ss/3.50; 2.7 Gb/s T3 two banks at ss-pessimistic) land at 56-61 mV, on or under the 60 mV limit; the
83 mV one-bank cell at 3.24 Gb/s ss-pessimistic lands near 66 mV. The tt deck with the new pad did not converge in
90 s in my bench (operating point), which the rerun will have to deal with.

### 7.4 Transients with the republished pad (`tran_c.log`, `tran_d.log`; ss-pessimistic 3.15 V, T3 = 120 mVppd, bench bias, code 0 picked from my own AC data with the new pad)

| Cell | Stored (old pad) | Mine (new pad typ, code 6) | Against 60 mVppd / 0.25 UI / 0 errors |
|---|---|---|---|
| 2.5 Gb/s, one bank | 124.0 mV, 0.55 UI, 0 / 120 | 99.9 mV, 0.45 UI, 0 / 120 (linear estimate 108.7) | pass |
| 3.24 Gb/s, one bank (the built load) | 82.6 mV, 0.375 UI, 0 / 104 | **64.3 mV, 0.20 UI**, 0 / 104 (linear 68.6 / 0.31) | **FAIL on eye width** |

So with the valid pad the one-bank 3.24 Gb/s cell at ss-pessimistic, which was the fallback reading of the STATUS
("with ONE bank at 3.24 Gb/s the linear estimate is 87 mV / 0.44 UI"), no longer meets the declared eye criterion.
The two-bank cells that passed at 71-74 mV were not rerun by me; by the 18-24 % amplitude loss they are at the
limit. This is two cells, not a requalification: the full matrix is the owner's rerun.

### 7.5 F1 again: raised input common mode, and the new pad (`vb.log`)

Gain at 1.25 GHz, code 0, old pad unless stated; pair = Vds / Vdsat.

| MOS / resistor / supply | HS_VBIAS | 9.5 uA | 10 uA | 10.5 uA | 11 uA |
|---|---|---|---|---|---|
| tt / slow / 3.30 | 0.98 V | +1.10 | -1.32 | -4.27 | -7.06 |
| tt / slow / 3.30 | 1.10 V | +2.80 | +2.02 (0.64/0.59) | +0.13 | -2.64 |
| tt / slow / 3.30 | 1.20 V | +3.36 | +3.12 (0.73/0.58) | +2.46 | +0.87 |
| sf / slow / 3.35 | 0.98 V | - | -6.19 | -9.09 | - |
| sf / slow / 3.35 | 1.10 V | - | -1.40 | -4.58 | - |
| sf / slow / 3.35 | 1.20 V | - | +1.78 (0.59/0.56) | -0.63 | - |
| ss / slow / 3.15 | 1.10 V | - | +2.50 | +2.32 | +1.69 |
| ss / slow / 3.15 | 1.20 V | - | +3.7 | +3.01 (tail 0.39/0.39) | +3.00 (tail 0.37/0.40) |
| tt / slow / 3.30, **new pad** | 0.98 V | +1.77 at 8.3 uA (tracking bias) | **-2.14** | - | - |

An input common mode of about 1.2 V recovers the trimmed-bias case at the corners I could run (worst +1.8 dB at
10 uA, -0.6 dB one trim step up at sf / slow resistor), with the tail at its edge at ss/3.15. The SL common mode
stays at 0.72-0.79 V on slow-resistor dies in any case, above the 0.66 V the sampler was requalified for. tt, ff/3.50,
fs and fast-resistor decks at 1.2 V did not converge within 90 s in my bench and are not covered. HS_VBIAS comes
from `pt_termination` (same owner), so this is a small netlist change there, not in `pt_ctle`; it does not
replace a bias rule.

## 8. What I could not verify

- Anything with R+C extraction; all resistance statements in section 5 are hand estimates.
- Electromigration from geometry (records and currents only); device-internal Metal1.
- The p-guard ring's metal tie to VSS and the side bars of the n-tap ring (probe points missed; top and bottom
  bars are on the rail).
- Whether the foundry processes DNWELL (INT-30); the substrate path if it does not.
- Off-state and floating-state operating points without a convergence aid; the origin of the 7-20 uA "off" current.
- Fast-resistor cross corners, and tt / ff / fs at HS_VBIAS 1.2 V (no convergence in 90 s). The tt deck with the
  new pad model likewise.
- Mismatch / offset, noise, supply rejection, the safety window (0-3.63 V ramps, 0 / 85 C), hot-carrier lifetime.
- Transients beyond the three I ran (tt 2.5 Gb/s T2 old pad: reproduced; ss-pessimistic 2.5 and 3.24 Gb/s T3 new
  pad; ss-pessimistic 2.5 Gb/s T3 at 10 uA). The other 59 stored transients, the sampler requalification
  (`slicer.json`, 84 runs) and the what-if table were read, not rerun. Real clocks and capture: r11's work.
- That the pass criteria were written before the runs (file is not in git).
- The WMON buffer's input range at the new SL common mode; the published wired-RX blocks' LVS reports for hidden
  property errors (F3).

## 9. Shared-machine notes

Every ngspice, Magic, netgen and KLayout run went through `scratch/wired_rx/slot.sh`, one slot at a time,
OMP_NUM_THREADS=1. Deviations to state: several second-scale jobs were bundled into one slot call (netgen runs;
operating-point decks of a few seconds each; the two KLayout decks of one block). One of my operating-point jobs
(ff/3.50 off state) hung for about 7 minutes holding a slot before I killed it; after that a 90-200 s limit
was applied and about ten decks ran into it. Nothing was written under `projects/` or `scratch/wired_rx/r10ctle`.
Intermediate extractions, KLayout databases, netlist caches and waveforms were deleted; logs and `res/*.json` kept.
