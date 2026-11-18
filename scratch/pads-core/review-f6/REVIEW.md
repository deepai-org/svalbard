# Independent review: pad_hspad candidate f6 (2026-11-18)

Reviewer got artefacts only. Written incrementally; the verdict is at the end. "RERAN" = I executed it; "READ" = I only read the owner's record.
Candidate GDS `scratch/pads-core/hsfix/build/f6/pad_hspad.gds` sha256 8c8e2533a57d5bc828ad382d658091080b1eb65da7163ad8aa4f50682530e22b.
Published GDS sha256 5b7c598e6c32...

## Q1 Provenance, DRC, LVS, precheck

- RERAN: `hs_leg_layout.py` (working tree, sha b670dc9c) into `review-f6/leg`, then `hs_pad_compose.py` (working tree, sha 54df77ab = the copy
  stored in the f6 build dir) into `review-f6/f6re` with the published shell and `network-gc-d2`.
  KLayout XOR (owner's `hsfix/xor.py`, texts ignored) rebuilt leg vs `build/leg4/pt_hs_leg.gds`: 0 um2; rebuilt pad vs candidate: 0 um2.
  The files are not byte-identical (204 differing bytes, GDS timestamps), so sha differs; geometry is identical.
  `physical.spice` of the rebuild equals the candidate's after sorting / renumbering the C lines (0 differing lines); `reference.spice` byte-identical.
  Rebuild reports Magic DRC 0, composer LVS match, device graph match, same bbox (-0.055, 0)-(492, 912.91).
- READ: KLayout precheck record `hsfix2/checks/kldrc/pad_hspad/kldrc.json` carries gds_sha256 8c8e2533..., main 0, antenna 0 (deep mode, variant D, KLayout 0.30.9).
- The read-back LVS records `hsfix2/checks/rb/{pos,neg}/result.json` carry the GDS PATH but NO sha256 (finding F7). Timestamps are consistent
  (GDS 05:23, records 05:25 / 05:26). RERAN the positive read-back LVS myself on the sha-checked GDS: "Circuits match uniquely", 508 / 508 devices,
  census exact (`review-f6/rb/pos/result.json`).
- Negative control READ: RX_P / RX_N label swap gives "Netlists do not match" (connectivity control). No parameter control existed; see below for mine.
- LVS reference: `hsfix2/checks/lvs-reference-f6.spice` equals the published `lvs-reference.spice` after exactly two substitutions
  (r_length 3.05u -> 2.6u on 20 devices, 2u -> 1u on 30 devices): `diff` of the sed-transformed published file against it is empty (RERAN).
  Device census of the reference: 20 x ppolyf_u 2/2.6, 30 x ppolyf_u 2/1.0, nothing else changed.
  Note: this reference is layout-derived (published extraction minus the model-only well diode), as for the published cell; the
  schematic-side check is the composer LVS + independent device audit (rebuild: match).
- Leg standalone: `layout-info.json` says `"pass": false` with 20 KLayout PP.2 violations on the leg alone (rebuild reproduces it). The composed
  cell is precheck-clean (marker merge in the composer). Same situation as the published flow as far as I can tell; recorded as F9 (low).

## Q2 R-aware model

- RERAN (own script, nodal solve on the `RNR*` resistors of `models/f6_r_{typ,high}.spice`, compared with `res/f6.json`):
  | pair | model typ | netres typ | model high | netres high |
  |---|---|---|---|---|
  | PAD_P bond -> 25 heads shorted | 6.823 | 6.824 | 8.928 | 8.928 |
  | PAD_N bond -> 25 heads shorted | 6.787 | 6.787 | 8.943 | 8.943 |
  | PAD_P / PAD_N bond -> diode node | 5.181 / 5.948 | 5.182 / 5.948 | 6.659 / 7.703 | 6.659 / 7.703 |
  | PAD_P / PAD_N bond -> feed | 5.169 / 6.028 | 5.169 / 6.028 | 6.358 / 7.471 | 6.359 / 7.471 |
  | PAD_P bond -> MIM bottom | 6.563 | 6.564 | 8.247 | 8.248 |
  | TERM_VCM pin -> P sources | 1.3677 | 1.3677 | 2.6601 | 2.6601 |
  | TERM_VCM P sources -> N sources | 1.0777 | 1.0777 | 1.7653 | 1.7653 |
  | RX_P pin -> MIM top | 38.82 | 38.86 | 84.87 | 84.89 |
  | RTU P0 / P2 / P13 / N24 | 6.736 / 16.207 / 14.619 / 16.626 | same in `f6_tu.json` | 14.43 / 44.98 / 33.34 / 35.66 | same |
  The insertion is faithful. No device terminal is left directly on the PAD_P, PAD_N, TERM_VCM, RX_P, RX_N port nodes (checked every X / D line).
- DC termination path: pad side (bond -> heads), TU nets (per unit), TERM_VCM (sources) all carry resistance. Left at zero: VSS, VDD, VBIAS, the five
  gate lines, ESD_RAIL. For the DC / low-frequency termination these carry no current (switch source is TERM_VCM, not VSS), so this is acceptable there.
  It is NOT acceptable for ESD (VSS and ESD_RAIL return, Q5) and it leaves the VSS pin -> leg tap resistance (15-16 ohm typ, 30 ohm high, one single
  cut, `res/f6.log` VSS rows) out of every AC bench (substrate / switch bulk reference); not assessed further.
- Model simplifications that matter elsewhere: all 12 diodes of a pad are tied to ONE node (no ESD polarity uses nd2ps and pd2nw together; netres
  itself gives bond -> 8 pd2nw 5.50 / 6.35 ohm typ P / N against 5.18 / 5.95 with all 12); every parasitic C stays on the bond-pad node.
- Dependence on a home-made tool: the candidate only meets its termination limits BECAUSE of the metal resistance netres reports (the C-only model
  fails, Q3). READ: `hsfix/val/check.txt` (analytic cases pass, includes a flagged-neck and a single-via case) and `esdcheck/REPORT.md` (hand sum, Magic
  extresist and an independent 2D solve agree with netres within 0.5 % on the PUBLISHED cells). No second-method check exists on the f6 geometry
  itself (hand sanity by me: Metal2 neck 8 x 355 um = 44.4 squares x 0.09 = 4.0 ohm of the 5.17 ohm bond -> feed: plausible).
- Hand estimate, tt 27 C 3.3 V, code 5 (10 base + 5 trim units per leg). Device values from my own single-device deck (`review-f6/ind/ind.py`,
  PDK models, RERAN): ppolyf_u 2 x 2.6 um 528.2 ohm, 2 x 1.0 um 240.9 ohm; nfet_06v0 20/0.7 on 175.0 ohm, 12/0.7 291.7 ohm (source at 0.4 V).
  Base unit 528.2 + 175.0 = 703.2, ten in parallel 70.3; trim unit 532.6, five in parallel 106.5; leg 42.35; differential 84.7 ohm
  (bench C-only model, code 5: 84.72). With metal: TU about 11.5 / 14.5 ohm per base / trim unit -> leg 43.24; + bond -> heads 6.82 + 6.79
  + TERM_VCM P -> N 1.08 = 101.2 ohm. Owner's bench f6rt: 101.78. My independent deck (one instance, +-10 mV, raw model, rshunt): 101.78.

## Q1 addendum: my parameter negative control
RERAN read-back LVS of the candidate GDS against the PUBLISHED reference (old lengths): status "mismatch", netgen "Property errors were found",
census differs exactly by 20 x (3.05 -> 2.6) and 30 x (2.0 -> 1.0) (`review-f6/rb/negpubref/result.json`). So the LVS flow does compare the resistor
lengths, and the candidate GDS really contains 2.6 / 1.0 um devices. (My first attempt at this run was spoiled by my own cleanup of its work
directory while it ran; rerun cleanly.)

## Q3 Termination

READ `hsfix2/bench/{f6rt,f6rh,f6c,pubc,pubrt,pubrh}-term.json`, RERAN `ctab.py` on them:
- f6rt (typ metal): T-A / T-B / T-C PASS at all 23 corners; 100 ohm falls at code 3.1 (ff 22 C 3.35 V) ... 8.2 (ss 32 C 3.15 V); T-D code 6: 82.0 ... 113.1 PASS.
- f6rh (high metal): PASS; code 4.3 ... 9.6; single code 7: 84.9 ... 114.0.
- f6c (C-only, i.e. zero metal resistance): T-A FAIL (ff 32 C 3.15 V: best code 2 = 94.8), T-B FAIL (ff: code 1), T-D FAIL (83.4 ... 123.0).
  The candidate is tuned to the metal resistance; without it the range is too low at ff.
- Published cell with resistance (pubrt / pubrh): no code reaches 100 ohm (141-154 ohm at code 15 typ metal, 212-225 high). The published C-only
  known answer (tt code 5 = 101.1) is reproduced by the bench (READ) and by my deck (101.12, RERAN).
- Negative control TERM_ENABLE = 0: 5.4e10 ohm (READ).
- Independent deck (RERAN, `review-f6/ind/ind.py`: one instance, raw model text, differential drive, .op per code): agrees with the owner's bench
  within 0.05 ohm at 9 points (tt / ss / ff / sf / fs, typ and high metal, C-only ff, 3.50 V trim).

Limits and timing: `cbench.py` / `ctab.py` mtime 04:51, f6 GDS 05:23, f6 term results 06:00-06:06: T-A..T-D predate the f6 runs. But the leg (all
termination devices) is `leg4` of 2026-11-14 and its termination results on f4 / f5 (5 corners) were known since then; unit lengths were iterated
against results (2.0 -> 2.6 um base "to centre the range", `hsfix/STATUS.md`). That is design iteration, not limit-following: the "2 codes margin"
rule (T-B) is in the 14 Nov notes before f4. T-A / T-C / T-D were written on 18 Nov with f5 results on the same leg in hand: formally before
the f6 runs, weak as a pre-registration. The limits themselves are reasonable (code step near 100 ohm is 5.5-6.5 %, so +-5 % is reachable whenever
T-B holds; +-20 % at the reset code is a loose but usual uncalibrated limit). T-C (1 ohm P - N) only sees metal asymmetry: no device mismatch is in any run.

Corner set against MANDATE 2 / 3 (what the owner's set lacks) and what I RERAN with the independent deck (`ind/sweep1.txt`):
| gap | my result | verdict |
|---|---|---|
| low-resistance metal (Magic `(lrhc),(lrlc)`: Metal1-4 76, Metal5 31 mohm/sq, vias 0) | netres rerun by me with a `low` corner (`review-f6/low/`, typ column reproduces the owner's numbers exactly; bond -> heads 5.15 / 5.10 ohm). ff 22 C 3.35 V: best code 2 = 104.0 ohm; ff 22 3.15: code 3; ff 32: code 3; tt: code 5; ss 32 3.15: code 7 | T-A, T-B PASS with ZERO margin at ff (code 2 is the limit) |
| VCM 0.3 / 0.5 V | low metal ff 22 3.35, VCM 0.3: code 2 = 102.7; high metal ss 32 3.15, VCM 0.5: code 10 = 100.5; tt typ metal: code 5 / 6 | PASS; VCM moves the code by about 0.5 |
| MOS corner split from resistor corner (ff MOS + res_ss, ss MOS + res_ff) | codes 4 ... 8, inside the ss / ff envelope | PASS, envelope corners are the declared ones |
| T-D with VCM range, typ metal, code 6 | 80.9 (ff 22 3.35, VCM 0.3) ... 115.8 (ss 32 3.15, VCM 0.5) | PASS, 0.9 ohm margin |
| T-D over the metal range (low ... high) | code 6: 76.9 ... 123.6; code 7: 72.4 ... 116.6 | no single reset code holds 80-120 over low ... high metal (not a declared limit: T-D is typ metal) |
| temperature outside the window (information) | ss 85 C 3.15 V high metal: code 11; ff 0 C 3.63 V low metal: code 2 | still inside 2 ... 13 |
| mismatch (unit resistors 2 x 1.0 um, 0.5 square, 25 % of the trim-unit resistance is head resistance: 240.9 ohm at 1.0 um vs 420.5 at 2.0 um) | NOT run by anyone | open |
| fast die trimmed below 3.15 V | not run | open (MANDATE allows trimming fast dies down) |

## Q4 Return loss with the chip-on-board model

Model (READ `scratch/pads-pd21/rl_cob.py`, `scratch/cob/channel_model.py`; RERAN its functions): die load -> bond wire (series R + L) -> 0.08 pF -> 1.17 mm
of 86.6 ohm microstrip -> via 0.36 nH + 0.10 pF -> 4.03 mm microstrip -> 0.06 pF -> connector 0.99 nH + 0.25 pF -> 10 mm 50 ohm line -> 50 ohm,
per leg, minimum over 0.1-1.25 GHz ("lo") and 1.25-2.5 GHz ("hi"). The ABCD orientation is right (die at the bond end; an empty chain returns the
plain die RL: checked). **The bond is 2.79 mm of wire at 0.832 nH/mm = 2.32 nH (wire diameter 25 um over a plane), not "about 2.8 nH" and not a
0.8 mil (20.3 um) wire.** With 0.8 mil: 2.44 nH; 2.8 nH would need 3.37 mm. Effect on the hi band (my run of the same chain with a C || R load):
2.32 nH 6.29 dB, 2.44 nH 6.15, 2.8 nH 5.74, 3.0 nH 5.52. The claim in the task text does not match the code; the bias is the same for published and candidate.

Numbers (owner's `hsfix/bench/*-ac.json` READ; my own AC deck `review-f6/ind/ac.py` RERAN reproduces f6rt / pubc / pubrt / f6c at tt to the last digit shown):
| model | code | R at 100 MHz | apparent C per leg 0.5 GHz (pF) | die RL 1.25 / 2.4 GHz (dB) | COB lo / hi, bond 0 (dB) |
|---|---|---|---|---|---|
| published, C-only (5 corners) | 5/8/8/3/2 | 96.7-103.3 | 1.132-1.151 | 13.0-13.4 / 7.96-8.29 | 14.1-15.5 / 5.99-6.13 |
| published, R typ | 15 | 128-153 | 1.00-1.05 | 10.6-12.6 / 7.77-8.82 | 13.6-18.1 / 7.35-7.63 |
| published, R high | 15 | 199-224 | 0.93-0.98 | 7.9-8.8 / 7.22-7.76 | 8.5-9.7 / 9.72-9.77 |
| candidate, C-only | 3/5/5/1/1 | 98.1-103.4 | **1.269-1.308** | 12.0-12.3 / 7.04-7.35 | 14.2-15.2 / 5.52-5.65 |
| candidate, R typ | 5/8/7/3/3 | 98.4-101.5 | 1.089-1.115 | 13.4-13.7 / 8.40-8.64 | 14.3-15.0 / 6.14-6.20 |
| candidate, R high | 7/10/9/4/4 | 97.2-101.5 | 1.043-1.055 | 13.9-14.1 / 8.89-9.06 | 14.0-14.9 / 6.25-6.38 |
| candidate, R low (mine; tt 5, ff 2, ss 7) | | 96.3-103.6 | 1.135-1.162 | 13.05-13.40 / 8.05-8.36 | 13.9-15.4 / 5.96-6.13 |
- Capacitance: the PHYSICAL capacitance per leg went UP by 12 % (C-only 1.148 -> 1.286 pF at tt; wiring C lines PAD_P 471.2 -> 540.6 fF, PAD_N 456.7 -> 525.1 fF,
  PAD_P : PAD_N mutual 28.2 -> 36.4 fF; my own sum of the Magic C lines, RERAN; the rest comes from the leg overlays and more off units). It is over the 1.15 pF budget of
  `spec/interface-requirements.md`. The 1.09-1.12 pF of the R-aware rows is Im(Y)/w seen through 5-9 ohm of series metal, which scales Im(Y) by about
  1 / (1 + Rs / Rterm)^2; it is not a smaller capacitor. The requirement behind the budget is die RL >= 8 dB at 2.4 GHz: met with resistance at low / typ / high
  metal (8.05 / 8.40 / 8.89 minimum), missed without it (7.04).
- Against the published C-only evidence the candidate with resistance is equal or slightly better (hi band +0.0 ... +0.25 dB; low metal -0.1 dB).
  Against the published cell WITH resistance the hi-band COB RL is 1.2-1.4 dB lower (typ) and 3.4 dB lower (high metal): the published cell
  sits at 128-224 ohm, which happens to help a package-limited band, and it pays with 10.6 dB at 1.25 GHz die RL (ss) and 2.4-4.2 dB RX loss.
- Not in any model: the Metal2 escape neck (8 um, unchanged: band XOR shows no change on it) under the ring rails, about 124 fF per pad (owner's
  Magic-coefficient estimate; my area check 8 x 283 x 0.93 x 59 aF = 124 fF). With +124 fF at the bond pad (mine): candidate R typ die RL 2.4 GHz 7.65 dB,
  COB hi 5.76; R low 7.61 / 5.57; published C-only 7.33 / 5.64; published R typ 7.48 / 6.83. So WR-SATA2-RL at the die is missed by BOTH cells once the neck is
  counted; the candidate is not the cause. The new 25 um VSS Metal2 strips also sit under the rails (VSS to rail C only, harmless).

## Q5 ESD and supply ramp

Gate exposure = largest |gate - terminal| on any 6 V device (owner's `exposure`), HBM 2 kV (1.33 A), unpowered. Owner's cases: PAD_P positive, PAD_N negative, typ metal only.
| model | case | tt 27 | ss 0 | ff 85 | bond-pad node peak | source |
|---|---|---|---|---|---|---|
| published C-only | P+ | 5.04 | 5.35 | 5.41 | same | READ ap4 json |
| candidate C-only | P+ | 5.04 | 5.35 | 5.41 | same | READ |
| published R typ | P+ | 23.4 | 23.8 | 23.1 (25 devices over 6.0) | 38.3-38.9 | READ |
| candidate R typ | P+ | 5.57 | 5.96 | 5.43 (0 over 6.0) | 11.6-12.2 | READ; tt RERAN by me: 5.57 / 11.82 |
| candidate R typ | **N+** | **6.44** | **6.83** | **6.18** (25 devices over 6.0) | 12.6-13.2 | RERAN (`review-f6/esd/hbm.py`, same deck builder), not in the owner's set |
| candidate R high | P+ | 6.10 | 6.50 | - | 13.8-14.2 | RERAN, not in the owner's set |
| candidate R high | **N+** | **7.21** | **7.60** | - | 15.2-15.6 | RERAN |
| candidate R typ / high | P- / N- | 0.95 | - | - | 10.3-13.2 | RERAN (devices clamp through the unit resistors) |
Why N is worse: the heads tap the pad net 0.47 ohm (typ) above the diode node on P but 1.12 ohm on N (0.87 / 1.70 high), from my solve of the model network
(feed -> diodes 0.92 vs 2.32 ohm in `res/f6.json`). The task says "P - N 0.04 ohm met" for bond -> heads; the ESD tap is not balanced.
CDM-speed surrogate (READ): C-only identical to published (4.80 / 6.98 / 9.03 V at 1 / 2 / 3 A); R typ pad node 9.99 / 17.3 / 24.6 V (published R typ 30 / 57 / 84).
HBM 1 kV (READ): candidate R typ pad node 6.8-7.3 V, exposure 4.4-4.7 V, 0 devices over 6.0 (P+ only).

No worse than published anywhere I looked: C-only peaks identical (P+), N- 3.48 vs 3.63 V; with resistance the candidate is 3 to 4 times lower on every row.

Return resistance, NOT in any simulation (READ `hsfix2/r2_f6.txt` = `res/f6_esd.json`), positive zap: pd2nw cathodes -> shunt clamp drains 0.46-0.60 typ / 1.0-1.3 high;
clamp sources -> ring VSS stacks 3.06 typ / 4.54 high (canonical clamp 4.57 / 6.87). Sum about 3.6 ohm typ, 5.7 ohm high; at 1.33 A: +4.8 V typ, +7.6 V high.
| 2 kV, gates referred to ring VSS | typ metal | high metal | limit |
|---|---|---|---|
| P+ exposure (tt ... ss 0) | 10.4 ... 10.8 V | 13.7 ... 14.1 V | 8.0 V transient (6.0 V screen) |
| N+ exposure (tt ... ss 0) | 11.2 ... 11.6 V | 14.8 ... 15.2 V | |
If the gate lines follow the leg's local VSS (tap at (138, 428), near the ring end of the return) rather than the ring, the Metal2 strips' share (about 0.6 ohm, 0.8 V)
drops out; still 9.5 V or more at typ. At 1 kV: about 4.5-5.2 + 2.4 = 6.9-7.6 V typ (inside 8.0), above 8 V at high metal.
**Plain statement: with pad-side resistance only the candidate stays under the 8.0 V transient limit at 2 kV (worst 7.60 V, N+, ss 0 C, high metal) but exceeds
the 6.0 V screen on PAD_N positive at typ metal and on both pads at high metal. With the VSS and ESD_RAIL return added by arithmetic it does NOT meet the 2 kV
tier (10-15 V against 8.0 V); 1 kV is met at typical metal only. The published cell is far worse (23 V before any return, 12-20 + 19-27 ohm of return).**
The owner's STATUS says the same about the resistance targets (T1 / T2 MISS, bond -> diodes 5.2-5.9 ohm against 1.0); the simulation table, read alone, looks like a pass.

Supply ramp (READ `hsfix2/pw/f6rt.log`, `pub.log`; finished 06:10 / 06:12; not rerun): 0 -> 3.35 V in 10 ns and 1 us (335 and 3.35 V/us, far faster than the 0.3 V/us
board rule), tt 27 / ff 32 / ss 22. VDD peak current candidate (R typ) 65.6 / 67.1 / 70.6 uA vs published (C-only) 64.6 / 66.1 / 69.6 uA at 10 ns; 5.0-7.5 uA at 1 us for both;
ESD_RAIL settles to 2.60-2.75 V in 44-75 us in both; pad disturbance <= 1.5 mV in both. No clamp conduction on VDD edges in either cell (the pad rail is not VDD).
No worse than published (+1.6 % peak current). The 3.63 V / 0 C / 85 C ramps are in the owner's safe set (READ: 18 / 18 complete, 0 devices over the screen, C-only and R typ).

## Q6 Layout change

RERAN `review-f6/geo/geo.py`, `geo2.py` (KLayout, flattened regions, published vs candidate):
- Outline identical (-0.055, 0)-(492, 912.91). All 14 pin labels identical in layer, text and position. No metal / via difference in the top 23 um, bottom 74 um,
  left 0.5 um, or the outermost 1.0 um of the side edge (pin stubs unchanged).
- Ring band y < 396: the only difference on any layer is Metal2 +10 938 um2: the two VSS strips widened from 8 um (x 6-14, 217-225) to 25 um (x 0.5-25.5,
  211.5-236.5). No Metal3 / 4 / 5 / Via2-4 change below y 396.2 (owner's `geo.txt` READ, mine RERAN). The PDK rail cell `5LM_METAL_RAIL` has no Metal2 (Metal1 frame,
  Metal3-5), so the strips do not collide with it. They now run 8 um from the pad necks (was 19.5 um) for 320 um, symmetric for P and N, and 0.5 um from
  the cell's left edge (was 6.0): chip-level DRC against the neighbour is still to be seen.
- Side edge: the new TERM_VCM Metal4 + Metal5 strap (30 um wide) reaches x 491.0, i.e. 1.0 um from the cell edge, over y 456-595 and 637-775. Quiet net; spacing only.
- Added metal: Metal1 +825, Metal2 +11 757, Metal3 +5 026, Metal4 +16 203, Metal5 +18 691 um2. Cell density Metal4 0.115 -> 0.151, Metal5 0.119 -> 0.160; the densest
  100 um window is unchanged (0.86 / 0.84, the bond pads). Metal5 wider than 30 um: unchanged area (bond pads). Metal3 has one new plate wider than 30 um
  (54 x 23.3 um link at (146-200, 722-745)); precheck main is clean on it. The precheck record covers the `main` and `antenna` decks only: no density deck on this cell.
- Capacitance (Magic C lines, my sum): PAD_P +69.4 fF, PAD_N +68.4 fF vs published (of it f5 -> f6: +58.3 / +57.4 as the owner states); P - N wiring imbalance 14.5 -> 15.5 fF;
  bench P - N at 0.5 GHz 15.3 -> 16.0 fF C-only, 16.4-18.3 fF with resistance (declared: not worse than 19). ESD_RAIL to pad 49 -> 57 / 45 -> 51 fF.
- Sensitive nodes: RX_P / RX_N wiring C 71.3 / 71.2 -> 74.3 / 74.5 fF, of which to TERM_VCM 3.6 / 3.7 -> 6.3 / 6.8 (the Metal4 trunk under the RX straps in the channel),
  to PAD 14.8 -> 16.1; still balanced within 0.5 fF. RX common / differential -50.4 dB (published C-only -51.5). TERM_VCM wiring C 248 -> 493 fF (helps).
- Antenna 0, latch-up 0 um2 uncovered at 15 um (READ, records name the f6 path; only the precheck record has the sha).
- Receive path: RX / PAD (bond pad node) -1.50 ... -1.60 dB at 100 MHz, -1.60 ... -1.70 at 2.4 GHz (R typ); -1.9 / -2.3 dB (R high); -1.2 / -1.3 dB (R low, mine).
  The published C-only model the wired RX benches bind says -0.3 dB; the published cell with resistance is -2.4 ... -2.9 / -2.8 ... -3.3 dB (typ) and -3.6 ... -5.7 (high).
  Cause: 5-9 ohm of pad-side metal sits inside the 50 ohm and the MIM taps behind it. RX pin -> MIM top is unchanged at 38.9 / 84.9 ohm with six single cuts.
- The wired RX default code is 0101 = 5 (`analog/wired_rx/sims.py`). With the candidate (R typ) code 5 gives 87.3 ... 120.8 ohm over the in-window corners; the T-D reset code is 6.

## Findings

| # | severity | finding | evidence | ran / read |
|---|---|---|---|---|
| F1 | HIGH | 2 kV HBM tier is not shown, and by arithmetic not met, once resistance is included. Owner's set lacks PAD_N positive and high metal: N+ puts 25 devices over the 6.0 V screen at typ metal (6.18-6.83 V), high metal 7.21-7.60 V; with the VSS / ESD_RAIL return (3.6 / 5.7 ohm) 10-15 V against 8.0 V. Still 3-4x better than the published cell. | `review-f6/esd/f6rt.json`, `f6rh.json`; `hsfix2/r2_f6.txt`; `hsfix/esd/*` | ran N+, high metal; read the rest; return by arithmetic |
| F2 | MEDIUM | Physical pad capacitance up 12 % (1.148 -> 1.286 pF per leg, C-only), over the 1.15 pF budget; the "1.09-1.12 pF" of the R-aware table is an apparent value. Die RL at 2.4 GHz >= 8 dB holds only with the metal resistance (8.05 low metal ... 9.06) and fails for both cells (7.3-7.7 dB) when the unmodelled 124 fF neck-to-rail C is added. | `hsfix/bench/*-ac.json`, `review-f6/ind/ac.txt` | ran own AC deck, read owner's |
| F3 | MEDIUM | The termination range is centred on netres' metal resistance: C-only fails T-A / T-B / T-D; low-resistance metal (missing from the owner's corners) passes with zero T-B margin (ff 22 C 3.35 V: code 2). No second-method resistance check on the f6 geometry (the esdcheck report covers published cells only). No mismatch run; trim resistor is 2 x 1.0 um (minimum length, 25 % head resistance). | `review-f6/ind/sweep1.txt`, `review-f6/low/`, `hsfix2/bench/f6c-term.json` | ran |
| F4 | MEDIUM | Consumers bind a C-only model. For this cell the C-only `physical.spice` is wrong in the direction that matters (84.7 ohm at the default code 5, RX loss -0.3 instead of -1.5 ... -2.3 dB, no TERM_VCM / pad resistance). Default code 5 gives up to 120.8 ohm (ss 32 C 3.15 V); T-D needs code 6. | `hsfix/table.py f6`, `analog/wired_rx/sims.py:66` | read, AC rerun at tt |
| F5 | MEDIUM | COB return-loss model uses a 2.32 nH bond (25 um wire), not about 2.8 nH / 0.8 mil; at 2.8 nH the hi band is about 0.55 dB lower (5.7 dB) for both cells. Against the published cell with resistance the candidate's hi-band COB RL is 1.2-1.4 dB lower (typ metal). | `scratch/pads-pd21/rl_cob.py`, `scratch/cob/channel_model.py` | ran the chain |
| F6 | LOW | R-aware model simplifications: 12 diodes of a pad on one node (bond -> 8 pd2nw is 0.3-0.4 ohm more than modelled), all parasitic C on the bond node, VSS / VDD / ESD_RAIL / gate lines at zero ohm (VSS pin -> leg taps 15-16 / 30 ohm through one cut). | `hsfix/make_rmodel.py`, `res/f6.log` | read; network solved |
| F7 | LOW | Read-back LVS and latch-up records carry the GDS path, not its sha256. The build is not byte-reproducible (timestamps): a rebuild has identical geometry but another sha. | `hsfix2/checks/rb/*/result.json`, `review-f6/rebuild-sha256.txt` | ran rebuild, XOR, LVS |
| F8 | LOW | T-A / T-C / T-D were written 18 Nov with the f5 termination results of the same leg known since 14 Nov (T-B is older). T-D holds at typ metal only; over low ... high metal no single code stays in 80-120 ohm (code 6: 76.9 ... 123.6). | file mtimes, `hsfix/STATUS.md`, `ind/sweep1.txt` | read / ran |
| F9 | LOW | Leg alone: KLayout PP.2 x 20, `"pass": false` in `layout-info.json` (same as the published leg per the owner's notes); composed cell clean. No density deck on the cell. Metal2 VSS strip 0.5 um and Metal4/5 strap 1.0 um from cell edges: assembly DRC not run. | `hsfix/build/leg4/layout-info.json`, `review-f6/geo/geo2.txt` | ran rebuild + geometry |

## Verdict: GO with conditions

The candidate is what the working-tree generators produce, is clean on every layout check I could repeat, keeps outline and pins, and is better than the published
cell wherever resistance is counted (the published cell cannot reach 100 ohm at any code and is 3-4x worse in every ESD row). It does not make anything worse except
physical pad capacitance (+12 %) and hi-band COB return loss against the mis-terminated published cell.

Conditions for publishing:
1. Do not claim the 2 kV tier. Publish the ESD table with PAD_N positive and high metal, and the return-resistance arithmetic (10-15 V against 8.0 V), as a stated miss
   (risk register ESD-02 / PAD-09), or put VSS and ESD_RAIL return into the model and rerun all four polarities at typ and high metal.
2. Publish the R-aware models (low, typ, high metal) as the simulation views next to `physical.spice`, and state in the README that the C-only netlist is not valid
   for termination, RX loss or ESD on this cell. Add the low-metal corner and VCM 0.3 / 0.5 V to the termination evidence (my numbers: pass, zero margin at ff / low metal).
3. Interface rows to the wired RX owner: RX / PAD -1.2 ... -2.3 dB, default code 6 instead of 5 (or accept 87-121 ohm at code 5), C per leg 1.27-1.31 pF plus about
   0.12 pF of neck not in any model, die RL 2.4 GHz 8.05-9.06 dB (7.6 dB with the neck).
4. Report the 1.15 pF budget as a miss or raise a budget request; do not quote the apparent 1.09-1.12 pF against it.
5. Publish the exact file (sha 8c8e2533...), not a rebuild, and add the sha to the LVS / latch-up records (my rerun on the sha-checked file: match, 508 / 508; parameter negative control fails as it should).
6. Correct the bond-wire statement of the return-loss evidence (2.32 nH modelled) or rerun at 2.8 nH.

## Not checked

- Any assembly-level run: chip DRC with neighbours, extraction of the neck under the rails, density with fill.
- A second-method resistance extraction on the f6 geometry; via resistance against the GF design manual; temperature of metal resistance; self-heating and
  current limits of cuts, the 0.48 um diode bars and the 2 x 1 um poly resistors during a zap (negative zaps push current through the termination units).
- ESD with return resistance in simulation; CDM beyond the owner's surrogate; HBM pad-to-pad and pad-to-VDD; 1 kV on PAD_N positive.
- Mismatch / Monte Carlo of the termination; ff below 3.15 V; noise; the HPF corner (read: unchanged 669-1068 kHz).
- The supply-ramp bench was read, not rerun; the owner's safe set, 1 kV HBM, CDM, latch-up and KLayout precheck were read, not rerun.
- `hs_leg_layout.py` edits were reviewed by diff and by rebuild only; I did not review `netres.py` line by line (reran it: typ numbers reproduce).
