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
