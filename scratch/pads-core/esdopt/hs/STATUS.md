# esdopt/hs: pad_hspad with pad-site primary ESD diodes (OPTION A). NOT committed, NOT published.
Started 2026-11-18. Brief: published f6 vs A vs B vs hybrid. Plan change by agent message (pads owner, relaying a user
decision): architecture is OPTION A, option B dropped (not built, not benched), hybrid only as a paper note; A goes to a
publishable candidate. Nothing is copied to $P/analog/pads/generated/, nothing committed.

## Pass limits (declared before any run; not to be moved)
- Magic DRC 0; composer LVS match; read-back LVS on the GDS from disk "match uniquely" AND the RX_P/RX_N swap control fails;
  KLayout precheck main 0 / antenna 0; latch-up 0 um2 uncovered at 15 um.
- Legacy build (legacy leg, default options) XOR 0 against the published GDS.
- ESD, R+C model with return networks and ring model: bond pad |V| <= 8.0 V transient at 2 kV HBM (1.33 A) and 1 kV (0.67 A);
  no MOS gate over 8.0 V transient (6 V devices) / 5.0 V (3.3 V devices); 6.0 V / 3.63 V DC screen reported as a count (not a fail by itself);
  CDM-speed surrogate 1 / 2 / 3 A, 1 ns: bond pad <= 8.0 V (reported per amplitude). Typical and high-resistance metal.
  Cases: P+ / P- / N+ / N- vs VSS, the same vs VDD, P zapped against N grounded (both signs).
- Pad capacitance per leg <= 1.15 pF INCLUDING the under-rail term (published f6: 1.27-1.31 pF C-only + about 0.12 pF under-rail = already a miss).
  P/N imbalance <= 20 fF.
- Termination (cbench/ctab, R-aware, 23 corners): best code 95-105 ohm with code inside 2..13; one code 80-120 ohm; per-leg P-N <= 1.0 ohm.
- Die return loss at 2.4 GHz and through the COB channel: not worse than published f6 by more than 0.3 dB (f6: 8.40-8.64 / 6.14-6.20 dB typ).
- Receive loss not worse than f6 (1.5-1.7 dB typ) by more than 0.1 dB.
- Outline (-0.055, 0)-(492, 912.91) and pins unchanged; if a new pin (DVDD) is needed it is stated.
- Each bench: known-answer case and a failing negative control recorded before the real runs.

## Log
- Generator `$P/analog/pads/pad_site_primary.py` written (new file). Standalone test cell `../site/s1`: Magic DRC 0, netgen LVS match
  (5 nd2ps + 5 pd2nw), LVS control (one diode removed from the reference) fails with a property error, rail-cell check clean
  (`../site/railconn.py`), rail control (`../site/neg1`, DVDD landing allowed on DVSS band 126-133) reports WRONG BAND. `../site/READY.md` written.
- Composer `$P/analog/pads/hs_pad_compose.py`: new flags `--site-primary[=JSON]` and `--no-core-array` (default off = published geometry),
  `esd_overlays(..., core_array=True)`. `$P/analog/pads/protection_device_audit.py`: optional `ring_wells=()` argument (default = old behaviour).
- Builds (leg `../../hsfix/build/leg4`, `./build.sh leg4 <name> <flags>`, about 15 s each):
  - `build/a1` = f6 + site primaries (core network kept): DRC 0, LVS match. PAD wiring C (cell alone, `padcap.py`) P 625.1 / N 609.5 fF (f6 540.6 / 525.1).
  - `build/a2` = site primaries, shell diode array deleted, array-only overlays not drawn: first try DRC 7 + LVS mismatch (the network's rail bleed
    hung on the array's Metal3 rail bus through a Via2 at (130, 458.77)); fixed with a 16 um Metal3 stub of that bus. Now DRC 0, LVS match,
    wiring C P 481.0 / N 462.9 fF.
- DECISION (before any ESD run): candidate = a2 (core array REMOVED). Reason: a1 adds 5 + 5 junctions and 85 fF of wiring per pad on top of f6
  (about +0.3 pF against a budget that f6 already misses); with the primaries at the pad the array behind the 4 ohm neck carries almost no current.
  The isolated rail, its RC clamp and gate-coupled shunt stay in the shell with no pad diode on them (dead; removing them needs a shell regeneration).
  a1 is kept as a built fallback; it gets no evidence runs unless a2 fails the internal-device limits.
- R extraction a2 (`./rflow_a.sh a2 leg4` -> `res/a2.json`, `res/a2_tu.json`, models `models/a2_r_{typ,high}.spice`), ohm typ / high:
  bond -> site down-diodes 0.183 / 0.507; bond -> site up-diodes 0.707 / 1.125 (8 um neck from the plate to y 106; 7 Via1 per finger);
  VSS landings -> nd2ps anodes 0.048 / 0.155; DVDD landings -> pd2nw n-wells 0.089 / 0.284 (per site, both sites equal);
  bond -> heads P 6.946 / 9.039, N 6.671 / 8.798 (f6 6.82 / 6.79 typ); bond -> feed P 5.29, N 5.91.
  Return networks are IN the model (VSS__aP/N, DVDD__kP/N nodes); the ring side is the bench's ring model (`esd.py` docstring).
- ESD bench `esd.py` proven: resistor 2 ohm instead of the pad -> 2.781 V at 2 kV (analytic 2.1 ohm x 1.3243 A = 2.781), 2.100 V at 1 A CDM.
  Simulator notes: the provider clamp's MOS capacitor (behavioural C) does not start with the supply ring at exactly 0 V in ngspice 46 / 47;
  a 1 uA kick into the ring from t = 0 fixes it (0.3 pC). The cells' DVDD-DVSS decoupling MOS capacitor is left out (pessimistic).
  First real runs a2 typ 2 kV: P+VSS pad 6.21 V (ring DVDD-DVSS 3.77 V at the site), P-VSS 3.54 V.
- ESD negative control (`esd/a2rt_nosite.json`, the 20 site diodes stripped from the model): P+VSS 29.9 kV, P-VSS 27.7 V at 2 kV -> the bench fails a cell without primaries.
- RUNNING (background, sequential): `./q1.sh a2` = ESD matrix typ + high (`esd/a2rt.json`, `esd/a2rh.json`), `./checks_a.sh a2` (-> `checks/a2/`),
  default-path builds `alegacy` / `af6` + XOR (`default-xor.txt`). Then `./q2.sh a2` (termination corners, AC / receive path, under-rail C). Progress in `q1.progress`, `q2.progress`.
  To resume after an interruption: rerun the same script; `esd.py` skips the cases already complete in its json.

## Options B and hybrid (not built; numbers only)
- B (isolated rail kept, wide neck): dropped by the plan change. On record from `../../hsfix2/STATUS.md`: Metal2 neck R = 32 ohm um / width, 5.1 fF per um of width in the cell
  extraction and about 15 fF per um against the ring rails (to be replaced by the measured figure from `checks/f6/railcap.txt`). 2 kV at 8.0 V needs bond -> diodes + return of
  about 1.9 ohm against 5.2-6.0 + 2.1-3.1 + 0.5-0.8 ohm in f6: even a zero-ohm neck (-4.0 ohm) leaves 3.8-5.9 ohm, so B also needs the core-side trunks,
  the VSS return and the rail path rebuilt; the neck alone at 0.5 ohm is 64 um wide = +285 fF in the cell and about +0.8 pF under the rails per pad.
- Hybrid (down-diodes in the site, up path on the isolated rail in the core): negative zaps as in A; positive zaps unchanged from f6 (through the neck: 11.6-12.2 V at
  the bond pad at 2 kV before the return is added). It does NOT give the same protection as A, so it is not pursued (plan change: mention only if equal protection).
  Its only merit is no pad diode to DVDD (no back-feed).

## State after queue 1 on a2 (2026-11-18 07:36) and two new inputs (agent messages from the pads owner)
- a2 results (superseded by a3 below, kept): `esd/a2rt.json`, `esd/a2rh.json` (HBM rows complete; CDM rows against the rails did not start: fixed in `esd.py`, ring kick 10 ps),
  `checks/a2/` (read-back LVS match vs the simulated netlist AND vs the composer schematic; RX swap fails; reference with one site diode removed fails on properties;
  KLayout 0 / 0; latch-up 0 um2 at 15 um; `railconn` clean; with the rail cell PAD_P 679.5 / PAD_N 661.5 fF wiring against 481.0 / 462.9 cell alone = 198.5 fF under-rail).
  a2 typ 2 kV: P/N vs VSS +6.21 / -3.54 V, vs VDD +4.53 / -5.48 V, pad-to-pad 9.75 V (worst gate 5.77 V); 1 kV: 4.9 / 2.25 / 2.74 / 4.72 / 6.36 V.
- `default-xor.txt`: default R-fixed composition (no flags) XOR 0 against `../../hsfix/build/f6` = the PUBLISHED GDS (sha 8c8e2533, identical files).
  The legacy-leg composition no longer XORs to 0 against the published GDS because the published cell IS f6 since commit 25d17bd0 (59020 um2 = the f6 changes); not a regression of this work.
- Input 1 (wired RX owner): no floating overlay pieces (f6 has 41 `**FLOATING` lines); pad C no higher than published, series metal bond -> RX matters more than C;
  re-centre the termination with two codes of margin including low-resistance metal.  Input 2: pad placed on the provider rail cell must add no precheck violation.
- a2 / a3 have 1 `**FLOATING` line (f6: 41): `m2_2279_124800#`, a Metal2 piece of the shared shell at about (11.4, 624) in the canonical clamp; it is inside the shell GDS, not in the top cell: reported, not removed.
- NEW composer options: `--esd-opt=JSON` (`neck_m1`: Metal1 under both necks with Via1 arrays; `p_trunk_m5_to`). Leg generator: `--lb= / --lt=` (defaults unchanged).
- Leg `build/leg5` = `hs_leg_layout.py --lb=4.2` (base unit poly 2.6 -> 4.2 um, trim unchanged 1.0): chosen BEFORE the run from the f6 table with a two-resistor unit model
  (requirement lb 3.59 .. 5.04 for crossing codes 4 .. 11 over low-ff .. high-ss). Leg log identical in kind to leg4 (DRC 0, LVS match, same 20 PP.2 leg-level KLayout notes).
- CANDIDATE `build/a3` = `./build.sh leg5 a3 --site-primary --no-core-array '--esd-opt={"neck_m1": true, "p_trunk_m5_to": 282}'`: DRC 0, LVS match, 1 floating line.
  R (ohm typ; `res/a3.json`, low `res/a3_low.json`): bond -> heads P 4.75 / N 4.88 (f6 6.82 / 6.79; low 3.28 / 3.35), bond -> feed 3.09 / 4.11, bond -> site up 0.60, down 0.18.
  Wiring C cell alone P 552.4 / N 532.7 fF (a2 481.0 / 462.9; f6 540.6 / 525.1).
- Termination a3 (`bench/a3r{l,t,h}-term.json`, `ctab.py`): 100 ohm crossing code low 4.2-9.0, typ 4.8-9.7, high 5.8-10.9 (window 2..13: two codes of margin at both ends in all three);
  best code 95-105 ohm and P-N <= 1 ohm PASS in all three; single code 80-120: typ code 7 84.3-118.8 PASS, high code 8 86.4-118.4 PASS, LOW code 7 79.5-114.0 = MISS by 0.5 ohm
  (code step 7 %, window head-room 4.8 %: with less corner-independent metal in series the spread ratio rose from 1.38 to 1.41-1.43). lb not touched after seeing this.
- RUNNING: `./q3.sh a3 leg5` (ESD control + matrix typ / high, CDM also with 1 nF die capacitance, rail-only DRC baseline, `checks_a.sh a3` incl. pad-on-rail precheck and floating count, then `q2.sh a3`). Progress `q3.progress`.
- a3 results (complete, superseded by a4 only because the GDS changed; numbers expected to carry over): `esd/a3r{t,h}.json`, `esd/a3r{t,h}_cdie.json`, `checks/a3/`, `bench/a3*`.
  a3 pad-on-rail precheck (`checks/a3/kldrc_rail`): 132 = V3.1 36, V4.1 36, V3.2a 30, V4.2a 30, ALL at the shell's own VSS ring stacks (9-11, 77-79) and (220-222, 77-79),
  each counted in three cells; rail-only composite `checks/railonly` CLEAN; none at the pad-site primaries (they have no Via3 / Via4). The published cell has the same stacks.
  FIX in the composer (site-primary mode): the stacks lose Via3 / Via4 / Metal4 / Metal5 (76 shapes); Metal2 / Via2 / Metal3 stay, VSS reaches the ring through the site landings.
- P/N balance: a3 (`p_trunk_m5_to` 282) reads 22 fF P-N on the AC bench (declared limit 20): trial builds gave wiring P-N 19.7 fF (282) / 15.0 fF (183, default). FINAL = default 183
  (costs about 0.45 ohm on the P leg only).
- Under-rail capacitance MEASURED (Magic, rail cells over the cell at x 0 and 211): f6 159.9 fF per pad (the 0.12 pF on record was an estimate), a3 206.1 fF.
- FINAL CANDIDATE `build/a4` = `./build.sh leg5 a4 --site-primary --no-core-array '--esd-opt={"neck_m1": true}'`; RUNNING `./q3.sh a4 leg5` (build, R extraction incl. low metal, everything else). Progress `q3.progress`, `q2.progress`.

# FINAL: candidate a4 (2026-11-18/19), evidence complete, NOT published, NOT committed
`build/a4/pad_hspad.gds` sha256 286715686f0c7c7dec766ac00ed9337b3b7987ad4a87ed81dab2269090f19001, `physical.spice` db7a4a1c..., leg `build/leg5/pt_hs_leg.gds` 145109eb... (`--lb=4.2`),
models `models/a4_r_{low,typ,high}.spice` 2f7c0ffb / 56f421f8 / 86175218 (+ `_rail` variants with 206.05 fF per pad under-rail).
Generators: pad_site_primary.py 5ff82d2a..., hs_pad_compose.py fa37ee49..., hs_leg_layout.py fc9c763a..., protection_device_audit.py 2b6745db...
Command: `./build.sh leg5 a4 --site-primary --no-core-array '--esd-opt={"neck_m1": true}'`; everything else by `./q3.sh a4 leg5` (all rerun on this GDS).
- Layout: Magic DRC 0, composer LVS match, device audit match; read-back LVS match vs simulated netlist and vs composer schematic (`checks/a4/rb/{pos,sch}`), controls fail
  (`neg` RX swap: netlists do not match; `neg2` one site diode missing: property error); KLayout precheck 0 / 0 (`checks/a4/kldrc`); latch-up 0 um2 at 15 um (`checks/a4/lu.json`);
  pad ON the rail cells: connectivity clean (`railconn.txt`), precheck main 0 / antenna 0 (`checks/a4/kldrc_rail`; rail-only `checks/railonly` 0; a3 with the shell's ring stacks: 132);
  floating lines 1 (shell piece m2_2279_124800#). Outline (-0.055, 0)-(492, 912.91) and all pins unchanged; NEW label / port DVDD (Metal3 at (57.75, 141.4) and (268.75, 141.4)).
  Default composer paths: R-fixed no-flag build XOR 0 vs the published GDS; legacy-leg build XOR 0 vs `../../hsfix/build/flegacy6` (`default-xor.txt`).
- R (ohm typ / high / low): bond -> heads P 5.24 / 7.16 / 3.68, N 4.88 / 6.81 / 3.35; bond -> site down-diodes 0.18 / 0.51, up-diodes 0.60 / 1.04; VSS landings -> anodes 0.048 / 0.155; DVDD landings -> n-wells 0.089 / 0.284.
- ESD (`esd/a4r{t,h}.json`, `esd/a4r{t,h}_cdie.json`, `esdtab.py`): see the table in the final report. Misses: pad-to-pad 2 kV 9.61 V typ / 11.10 V high against the declared 8.0 V bond-pad limit
  (no device over its transient limit: worst gate 5.78 / 6.63 V, worst diode reverse 6.16 / 7.12 V); 25 MOS over the 6.0 V DC screen at 2 kV with high metal (6.46-6.63 V);
  CDM surrogate: positive against VSS 8.67 / 12.23 / 13.60 V at 1 / 2 / 3 A without die capacitance (5.65 / 9.54 / 12.38 V with 1 nF), 25 termination switches over 8.0 V from 1 A (2 A with 1 nF).
- Termination (`term-table-a4.txt`): crossing codes low 4.3-9.0, typ 4.9-9.8, high 5.8-11.0; best code 95.6-103.8 ohm, P-N <= 0.36 ohm; single code typ 7: 84.8-119.2, high 9: 82.0-111.8, LOW 7: 79.9-114.4 = MISS by 0.1 ohm.
- AC (`bench/a4*-ac.json`, `-rxpath.json`): see final report. P/N 10.9 fF.
- Not done: independent review; f6 through the new ESD bench (f6 column is read from its records); ss / ff device corners in the ESD matrix (typical 27 C only); mismatch; assembly-level extraction beyond the two rail cells;
  mirrored placement (`--mirror`) of the pad-on-rail check; `rail_site_check.py` did not exist when the queue ended (own composite used); shell regeneration to delete the dead isolated rail / clamps and the array feed stubs.

# REVIEW AND RESOLUTION (pads owner, 2026-11-19): a4 NOT published
Independent review `review-a4/REVIEW.md` (fresh agent, artefacts only): NO-GO against the declared limits. Layout evidence confirmed on the exact GDS
(sha, LVS controls fail, precheck 0/0 alone and on the rail cell, `rail_site_check.py` PASS, latch-up 0, default XOR 0). Generator shas re-checked
after the 08:00 mtime touch: identical to the record (5ff82d2a / fa37ee49 / fc9c763a / 2b6745db), so the provenance finding is closed.
Misses: (1) pad-to-pad 2 kV at the bond pad, (2) CDM surrogate (25 termination switches over 8.0 V from 1 A without die capacitance, from 2 A with 1 nF),
(3) pad C incl. under-rail 1.26-1.32 pF vs 1.15 (and +37 fF over the published cell, against wired RX's "not above published"), (4) single-code
termination at low metal by 0.1 ohm. New: RX_P reaches 4.65 V (2 kV HBM) / 6.1 V (CDM 1 A) above VSS behind the MIM; the consumer (CTLE input) oxide is not in the bench.

## Pad-to-pad 2 kV: judged at the devices (owner's judgement; the declared bond-pad figure stays a recorded miss)
Basis: 8.0 V is the 6 V-oxide transient limit (`spec/design-assumptions.md`, "Gate oxide transient limit"). The bond pad and its plate carry no thin
oxide; every device with a terminal on the pad nets is in the bench's device check. Worst gate 5.78 V typ / 6.63 V high metal (limit 8.0), worst diode
reverse 6.16 / 7.12 V (model breakdown nd2ps_06v0 bv 11 V, pd2nw_06v0 bv 10.5 V; sm141064.ngspice), MIM 3.87 / 4.60 V (limit 6 V). So pad-to-pad HBM
passes at the devices with 1.4 V of oxide margin at high metal. Condition: the receiver input behind RX_P/N must be added (finding 5).
Reaching 8.0 V at the bond pad: what-if `whatif/` (site diodes scaled in the a4 typ model, finger metal not added = optimistic): x1.6 (8 fingers per row)
P+N 7.95 V, x2.0 7.38 V. The site holds at most 5 fingers per row beside the 8 um neck (`pad_site_primary.py`), and each extra finger costs about 20-28 fF
per leg; "lower finger resistance" is the same trade (diode series resistance and junction C both scale with area).

## CDM surrogate
What-if at 1 A, no die capacitance: x1.6 fingers P+VSS 8.01 V, termination switches 7.61 V (0 over 8.0); x2.0 7.79 V / 7.40 V; pad-to-pad stays 9.9-10.3 V
because the provider ring itself rises to 5.3 V DVDD-DVSS in 1 ns without die capacitance. With 1 nF on the ring (the die carries 5.4 nF of decap, D9)
5 fingers pass at 1 A (pad 5.65 V, worst gate 5.42 V) and fail at 2 A. The published f6 on the same bench (`esd/f6rt.json`): bond pad far higher
(2 kV P+N 22.8 V, P+VSS 11.9 V; CDM 1 A P+N 18.5 V) but its termination switches stay at 5.2 V at CDM 1 A because the core diode array sits next to
them; a4 removed that array, i.e. the local secondary clamp of the switches.
The current a 250 V CDM event drives into this bare die is not established in the repo (open: PAD-11 / README item 3).

## What would make it a GO (not done; each costs capacitance or needs a ruling)
- Secondary protection next to the termination switches (the a1 variant keeps the core array: about +0.3 pF per leg), or gate-follows-drain coupling
  of the switch gates (leg redesign), and the receiver input in the bench.
- Or: rulings that (a) pad-to-pad is judged at the devices, (b) CDM is judged with die capacitance, (c) the required CDM current, and (d) a C budget
  above published for option A (wired RX).

# CANDIDATE a5: local secondary clamp (coordinator rulings on PC-36), 2026-11-19. NOT published, NOT committed.
Work folder `sec/`. Rulings (binding): (a) pad-to-pad HBM judged at the DEVICES incl. the receiver input RX_P/N, bond pad = information;
(b) CDM judged with 1 nF on the ring (`--cdie 1n`), requirement 2 A, 1 A / 3 A reported; (c) core diode array NOT restored, small local
secondary at the termination switches (and RX if needed) to DVDD / VSS; C budget +0.15 pF per leg over the published cell like for like.

## Declared before the a5 queue (limits; not to be moved)
- Layout: Magic DRC 0; composer LVS match + device audit; read-back LVS "match uniquely" vs simulated netlist and composer schematic, with
  failing controls (RX swap; one site diode missing; one SECONDARY diode missing); KLayout precheck main 0 / antenna 0 with a failing control
  (copy + 0.1 um Metal1 sliver); latch-up 0 um2 uncovered at 15 um with a failing control (copy + isolated NMOS); `rail_site_check.py` PASS
  and its `--selftest`; pad-on-rail precheck 0 / 0, railconn clean; floating lines <= 1 (the shell piece).
- Default paths: no-flag build XOR 0 vs published; the a4 command rebuilds build/a4 byte-identical except GDS timestamps (normalised sha);
  default leg (`--lb=4.2`, no `--sec`) identical to build/leg5 the same way. Outline (-0.055, 0)-(492, 912.91) and pins as a4 (port DVDD as a4).
- ESD, `sec/esd2.py` = ../esd.py + receiver input gate on RX_P/N (nfet_06v0 16/0.7 x 6, gate RX, D/S/B local VSS; the CTLE input pair of
  analog/wired_rx/netlists.py is pfet_03v3 16 um x 6, so 3.3 V is the REAL oxide there) and read-out RX - local VSS / RX - core VDD.
  HBM 2 kV and 1 kV, all 10 cases, typical and high metal; CDM 1 / 2 / 3 A with 1 nF (typ, high), CDM without 1 nF reported:
  E1 no MOS gate over 8.0 V (6 V) / 5.0 V (3.3 V) transient; E2 receiver RX - VSS and RX - VDD <= 8.0 V (6 V oxide; 5.0 V reported as the
  3.3 V sensitivity); E3 junction reverse below the model bv (nd2ps_06v0 11 V, pd2nw_06v0 10.5 V); E4 MIM <= 6.0 V; E5 bond pad <= 8.0 V
  for the VSS / VDD cases at HBM (pad-to-pad and CDM bond pad = information). Requirement points: HBM 2 kV, CDM 2 A with 1 nF.
  Controls: toy 2 ohm known answer; site diodes stripped (must fail); SECONDARY diodes stripped at CDM 2 A 1 nF high metal (must fail E1).
- C: per-leg c_leg of the `_rail` model (typ metal, every AC corner) <= f6rt_rail c_leg of the same corner + 0.150 pF; P/N <= 20 fF;
  read-out control ctest (+100 fF on P). High / low metal `_rail` reported.
- Termination T-A..T-D (cbench / ctab, low / typ / high), return loss and receive loss as declared above (like for like: `_rail` vs f6rt_rail,
  no-rail vs f6rt); receive loss with high metal vs f6rh (now run) reported.
Sizing (model level, a4 high model + diodes at the 50 switch drains, lumped DVDD route, `sec/mkcand.py`, `sec/size.sh`, `sec/esd/sz_*.json`):
  base a4 + rx gate: CDM 2 A 1 nF high P+VSS switch gate 10.07 V (25 over 8.0); RX - VSS max 4.72 V (HBM P+N high), RX fine without diodes;
  negative zaps fine (the switch's own drain junction). pd2nw at each drain: 4 um2 / 2 ohm: 5.54 / 5.79 V (P+VSS / P+N); 2 um2 / 5 ohm 6.29 / 6.54;
  1 um2 / 2 ohm 6.53 / 6.78. Chosen 2 um2 (w 1 x l 2), no nd2ps, no RX diodes. Trial build on extracted R (DVDD route + in-leg trunk:
  land -> all cathodes 5.5 / 9.3 ohm typ / high): CDM 2 A 1 nF high P+N worst gate 7.27 V; termination typ T-A..T-D PASS (code 8: 81.0-113.0).
Generator changes (all behind options, defaults unchanged): `hs_leg_layout.py --sec=JSON` (diode row between switch and resistor rows,
port DVDD outermost in the bank, Via2 / Via3 / jumper reinforcement of the split TU nets), `hs_pad_compose.py --sec` (legs' DVDD joined
across the channel, DVDD route down the left of the P leg and the N-site column to the site DVDD bar, VSS strap moved to y 406.5 below the
taller leg). Command: `sec/q_s.sh a5 leg6 '{"up": [1, 2]}'` (leg, build, R, ESD, checks, benches; progress `sec/q.progress`).
- 2026-11-19 ~20:10 UTC FIRST a5 BUILD SUPERSEDED (results kept in `sec/r1/`, GDS deleted; queue stopped after the ESD matrix): CDM 2 A with 1 nF,
  HIGH metal, P-N: 11 termination switches of the N leg at up to 8.05 V (E1 MISS); typ 7.20 V; all HBM cases PASS (worst gate 5.41 V high).
  Cause: the N leg's diodes were fed through both legs' 2 um DVDD trunks and 2 Via3 cuts per leg (land -> N cathodes up to 59.7 ohm high);
  the trial had been checked on P-leg cases only. Change (before the re-run, limits unchanged): leg `"dvdd_w": 3.0`; composer DVDD
  reinforcement beside the legs (Metal4 x 311.5 .. trunk, Metal5 y 419-735.5 with Via4 array, Metal3 stubs + Via3 arrays at both
  track / trunk junctions). Trial on the extracted model (land -> all cathodes 4.68 ohm high, per cathode 28-40): CDM 2 A 1 nF high
  P-N 6.92 / N+VSS 6.67 / P+VSS 6.52 / P+N 6.77 V. Re-run: `sec/q_s.sh a5 leg6 '{"up": [1, 2], "dvdd_w": 3.0}'`.

## CANDIDATE a5 RESULTS (2026-11-19, queue 20:10-21:54 UTC, all on the exact GDS). NOT published, NOT committed.
GDS `sec/build/a5/pad_hspad.gds` sha256 3e23359ee382e468a0ed7e896c86a95f1022dcef1e5ce13a76765c31284902b0 (timestamp-normalised a96449539cfbc64f);
physical.spice 1ada18f7; leg `sec/build/leg6/pt_hs_leg.gds` 123fd946; models a5_r_{typ,high,low} 595ca861 / c3b5bdf0 / 1427b22c,
_rail a5bb205c / 9ac436c1 / f81163a1, ctest 51121f71. Generators: hs_pad_compose.py d00f1f37, hs_leg_layout.py d85fda3f, pad_site_primary.py 5ff82d2a
(unchanged), protection_device_audit.py 2b6745db (unchanged).
Commands: `sec/q_s.sh a5 leg6 '{"up": [1, 2], "dvdd_w": 3.0}'` = leg `hs_leg_layout.py --lb=4.2 --sec=...`, `sec/build.sh leg6 a5 --site-primary
--no-core-array '--esd-opt={"neck_m1": true}' --sec`, `sec/rflow_s.sh`, `sec/esd2.py` (matrix), `sec/checks_s.sh`, `sec/q2_s.sh`. Table: `sec/a5tab.py a5`.

| Limit | a5 number | Result |
|---|---|---|
| Magic DRC / composer LVS / device audit | 0 / match / match | PASS |
| Read-back LVS pos / sch, 554 devices | match / match | PASS |
| Controls: RX swap / site diode missing / secondary diode missing | mismatch / mismatch / mismatch | PASS (fail as required) |
| KLayout precheck cell / on rail cells | 0/0 / 0/0; control (sliver) M1.1 + DF.14_LV reported | PASS |
| Latch-up uncovered at 15 um | 0.0 um2; control (isolated nmos) 6.4 um2 | PASS |
| rail_site_check.py / --selftest / railconn | PASS / OK (clean, V3.1 FAIL, REFUSED) / clean | PASS |
| Floating lines <= 1 | 51 (shell piece + 50 Metal1 rings of the new diodes: gencell outer p-sub ring drawn with glc/grc 0 = no contacts) | **MISS** (fix: glc 1 grc 1 in hs_leg_layout _gen6, not re-run) |
| Default no-flag XOR vs published / a4 rebuild / default leg | 0.0 / normalised == build/a4 / normalised == leg5 (`sec/repro.txt`) | PASS |
| Outline / pins | (-0.055,0)-(492,912.91), pins as a4 (port DVDD) | PASS |
| E1 MOS gate, HBM 2 kV all cases typ / high | 5.05 / 5.19 V, 0 over 8.0 (a4: 5.78 / 6.63) | PASS |
| E1 HBM 1 kV typ / high | 4.43 / 4.52 V | PASS |
| E1 CDM 2 A with 1 nF typ / high (requirement) | 6.34 / 6.92 V, 0 over (a4: 25 over, 8.9 / 10.3 V) | PASS |
| E1 CDM 1 A / 3 A with 1 nF typ, high | 4.03 / 7.88; 4.43 / 8.04 (6 over, P-N) | 1 A PASS, 3 A high MISS (report) |
| E2 receiver RX-VSS / RX-VDD, HBM 2 kV and CDM 2 A 1 nF (6 V oxide 8.0) | 4.69 V (HBM P+N high) / 4.11 V | PASS |
| E2 3.3 V sensitivity (5.0 V; the real CTLE input is pfet_03v3) | HBM 4.69, CDM 2 A 1 nF 4.11, CDM 3 A 1 nF 4.84; without 1 nF CDM 1 A 6.26 | PASS at the requirement points (0.31 V margin) |
| E3 junction reverse < bv (nd2ps 11 / pd2nw 10.5) | HBM 6.87; CDM 2 A 1 nF high 10.69 (site nd2ps, P-N) | PASS (0.31 V margin); 3 A 12.7 MISS (report) |
| E4 MIM <= 6 V | HBM 3.84, CDM 2 A 1 nF 5.06 | PASS |
| E5 bond pad vs VSS/VDD HBM 2 kV | 5.88 typ / 6.77 high | PASS |
| Bond pad pad-to-pad HBM 2 kV (info) | 9.42 / 10.86 V | info |
| CDM bond pad 2 A 1 nF (info) | 9.25 / 10.54 V vs rail; 14.1 / 16.2 pad-to-pad | info |
| CDM without die C (info) | 2 A: 25 switches at up to 9.3 V | info (ring rises without decap) |
| ESD controls: toy 2 ohm / site stripped / secondary stripped | 2.781 V / 29.3 kV / 10.07 & 10.32 V, 25 over (fails) | PASS |
| C per leg, _rail typ, <= f6rt_rail + 0.150 pF per corner | 1.332-1.356 pF, max +0.093 pF (high +0.044, low +0.126) | PASS |
| P/N imbalance <= 20 fF; ctest +100 fF reads | 5.3 fF (high 6.2); 105 fF | PASS |
| Termination T-A..T-D low / typ / high | all PASS; T-D low code 7 80.2-114.7, typ code 8 81.1-113.0, high code 9 85.0-114.8 | PASS (a4 low miss cleared) |
| Die RL 2.4 GHz not worse than f6 by > 0.3 dB (per corner, like for like) | _rail: worse by up to 0.67 dB (6.91-7.22 vs 7.36-7.65); no rail: 0.49 dB | **MISS** |
| COB RL same rule | _rail worse by up to 0.31 dB; no rail 0.15 dB | **MISS** by 0.01 (rail) |
| Receive loss not worse than f6 + 0.1 dB | typ 1.23-1.32 vs 1.59-1.68 dB; high 1.75-1.88 vs f6rh 2.06-2.15 | PASS |

Notes: first a5 build superseded (N leg 8.05 V at CDM 2 A 1 nF high, `sec/r1/`). The site-diode-stripped control also strips the 50
secondaries (the strip rule matches any cathode on a DVDD node): still fails as required. Not run: ss/ff device corners and hot in ESD;
DVDD route resistance beyond the cell (ring assumed as esd.py); per-finger current density; f6 through the new ESD bench; a rebuild
with the floating-ring fix; low-metal ESD. Review blockers: floating rings (hygiene, one-line fix + full re-run), RL miss (needs a ruling or
a lower-C diode/route: the in-leg diode row, jumpers and DVDD trunk cost ~0.4 dB die RL vs a4).
