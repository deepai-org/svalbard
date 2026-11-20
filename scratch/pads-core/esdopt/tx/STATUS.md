# esdopt/tx: pad_txpad rework (UNPUBLISHED candidate). Started 2026-11-18. Nothing committed, nothing in generated/.

## Scope (as it stands)
- Brief: trimmed termination, output-path resistance fix, 0.6x MAIN switch as generator option (default OFF),
  ESD variants A (site diodes to ring rails) and B (isolated rail, wide neck), full R+C evidence.
- Scope change received mid-task from agent a07714b3f18166709 ("user decision relayed by the coordinator"):
  option A only, DROP variant B, one candidate to a publishable state. Not verifiable from here; followed
  because it only removes work. Report it in the final message.
- Wired TX row addressed to pads: NOT arrived at start (WT38 is the ring-version row). Sizing uses the brief's
  DEFAULTS until a row appears (re-check before fixing sizes and before the final message).

## Limits declared BEFORE any run
- T1 differential termination 100 ohm +-5 % (95..105) at some trim code, with >= 2 codes of margin to both
  ends of the range, at tt/ss/ff/sf/fs x 22/32 C x 3.15/3.35 V and ss 3.50 V (23 corners), typ and high metal.
- T2 P leg - N leg <= 1.0 ohm at that code.
- O1 bond pad -> output cascode drains <= 2.0 ohm per leg, typ and high; O2 P/N within 0.5 ohm.
- O3 metal drop of the whole leg path (pad + SUM + TAIL + cell VSS to its ring landing) <= 60 mV at 21 mA.
- E1 HBM 1 kV (tier) and 2 kV (reported), CDM surrogate 1/2/3 A 1 ns: 3.3 V devices <= 5.0 V transient,
  6 V devices <= 8.0 V; DC screens 3.63 / 6.0 V reported.
- L1 Magic DRC 0; L2 read-back LVS unique + failing control; L3 KLayout main 0 / antenna 0; L4 latch-up 0 um2.
- A1 outline inside 2.78..484 x 0..1226.72, area <= 300,000 um2.
- Bench proofs: published C-only termination 91.58 ohm at tt (txr/), TERM_ENABLE=0 > 10 kohm as negative control.

## Log
- Generator written: `$P/analog/pads/tx_pad_layout.py` (NEW file; nothing existing edited so far). One flat Magic cell
  `pad_txpad`: driver (8 unit tiles, hand placed), two termination legs (8 base 2x2.8/20, 15 trim 2x1.0/12, nfet_03v3
  0.28 switches, gates TERM_ENABLE_LOCAL / TERM_TRIM0..3), site primaries (pad_tlp_flat pattern at Y=146, via2 landings
  on ring M3 DVSS 126-133 / DVDD 134-149), 30 um M2 neck, convkit control cell `pt_tx_ctl`. NO network macro / ESD_RAIL.
  Build: `SVALBARD_PAD_IMAGE=sha256:b6027... python3 $P/analog/pads/tx_pad_layout.py scratch/pads-core/esdopt/tx/b/<name>`
  (`--part drv|leg|ctl` for pieces, about 1-2 min each).
- Presize (schematic + lumped metal, `presize/presize.py`): Nb 8 / Lb 2.8 / Wb 20 / Lt 1.0 / Wt 12 -> 100 ohm at codes about 3.3..9.6.
- b/a1: Magic DRC 0 (drc(full)), netgen LVS "Circuits match uniquely" vs generator schematic (297 devices), no shorts.
- Site cell: READY.md of esdopt/site appeared after my site was already drawn and clean; its generator allows only 3
  fingers beside a 24 um neck and is KLayout-side. Mine = TLP pattern (4 + 4 fingers) in the Magic flow. Use its
  railasm.py / railconn.py to check under the rail cell.
- NEXT: netres via txr/mkspec.py on b/a1 GDS -> O1/O3; then termination bench; rb_lvs, kl_block_drc, lu; ESD benches.
- Tools here: `rflow.sh <build> <rdir>` (mkspec + fixspec + netres), `paths.py`, `mkmodel.py` (R+C model with site islands and
  ring ports DVSS_P/N), `tb2.py` (ka / term / esd / esdnc), `checks.sh <build> [kl rb lu rail]`, `drcsum.py`.
- Bench proof (RUN): `tb2.py ka` -> published C-only 91.577 ohm at tt (expected 91.58), ss 152.1, ff 57.7 = txr; negative
  control TERM_ENABLE 0 -> 674.8 kohm. PASS.
- b/a1 (units 8 x 2.8/20 + 15 x 1.0/12): O1 1.37 typ / 1.76 high ohm, P = N; O3 39.0 / 56.4 mV at 21 mA: PASS.
  Termination with R: 100 ohm at code 5.1 tt, 8.8 ss, 3.1 ff, but the LSB is 8-10 % of the leg at low codes: T1 at risk.
  -> resized: base 8 x (2 x 2.0 um, 20/0.28), trim 15 x (2 x 2.8 um, 12/0.28): LSB about 5 %.
- b/a2 = resized build: DRC 0, LVS match, O1 / O3 unchanged (r2/paths.json). circuits.py: option `steering_widths_um`
  added (default None; default netlist sha unchanged 3e84a990... / e0effc44... before and after).
- Self-check with resistors x 1e-6 / 1e-3 does NOT converge in ngspice (7050 resistors); use x 0.01 or compare c vs rt.
- Extra condition from agent a07714b3 (FLOATING nodes): a2 ext.spice has 0 nodes without a device (the 106 `**FLOATING`
  tags of the convkit-style export are on real internal nets: TU, SUM, TAIL, ctl nets; no anonymous node).
- RUNNING: term full corners rt / rh on a2. NEXT: checks.sh a2; esd benches; ac; out; idle.

## FINAL (2026-11-19) - candidate b/a4
- Candidate: b/a4, GDS sha256 ac5e6d1c0540b4fb2fdcaca158a592eea5812eb7a06da816c1b63a04fe1cf3ef. The current tx_pad_layout.py rebuilds it
  (all .mag and the schematic identical apart from timestamps). Correction to the hand-over: a4 differs from a3 by 3 extra up-diodes per pad
  (DQ*, pd2nw PAD->DVDD_x, second row, 4 down + 7 up per pad), not by a leg shift. The 1 um leg shift (54.18 -> 53.18) is a2 -> a3, together
  with the PP marker merge. Option `steering_widths_um` is off.
- Models (r4/ via rflow.sh a4 r4; res.json c142eb1d...): a4_rt 6f621377..., a4_rh c7c8e2b1..., a4_c (= ext.spice) 42dd6f1c...,
  a4_zero (x0.01 self-check) 522af795.... There is no low-metal model: netres.py knows only typ and high.
- a3 negative control: the rc was 0 because rb_lvs.py exits 0 on a mismatch, but the output really FAILED (status mismatch, pin matching).
  a2's negative control had crashed (missing swapped.gds) and read as a "fail". Fixed: checks.sh now judges with rbverdict.py
  (pos = match + unique; neg = 'swapped 2' + mismatch; crash = FAIL). a4: pos PASS, neg PASS (a real mismatch).

| Limit | Result | Verdict |
| --- | --- | --- |
| T1 100 ohm +-5 % at some code, >= 2 codes margin, 23 corners, typ / high | rt 97.50..102.03 at codes 3..12; rh 97.46..102.60 at codes 3..12 | PASS |
| WT39 (2) +-10 % including metal, trimmable | contained in T1 | PASS |
| T2 / WT39 P-N <= 1.0 (WT39 2) ohm | rt +0.20..+0.36, rh +0.23..+0.42 | PASS |
| O1 bond -> cascode drains <= 2.0 ohm (shorted) | typ 1.367, high 1.752 (equal-split mean 1.397 / 1.770, max 1.841) | PASS |
| O2 P/N <= 0.5 ohm | 0.001 | PASS |
| O3 / WT39 (5) leg path drop <= 60 mV at 21 mA (pad+SUM+TAIL+VSS in the model) | typ 39.0, high 56.3 mV (netres arithmetic) | PASS (simulated drive bench `out` did not run: ngspice vector syntax error, as on a2) |
| WT39 (3) MAIN/POST gate C <= 0.45 pF and <= published | a4 MAIN 0.192/0.299, POST 0.190/0.297, TMDS 0.180/0.289 pF (gate 0 V / 3.3 V); published MAIN_P 0.382/0.492, MAIN_N 0.497/0.607, POST 0.322-0.513 | PASS |
| WT39 (4) pad-node C <= published | per leg at 100 MHz: a4_c 3.076, a4_rt 3.152, published C-only 3.193 pF | PASS (margin 0.04-0.12 pF) |
| Term bench proofs | known answer 91.577 (91.58); published TERM_ENABLE 0 674.8 kohm; a4 off >= 1.5e10 ohm | PASS |
| E1 HBM 1 kV, all 6 cases, without and with 1 nF ring | worst nfet_03v3 4.97 V ds (pp), nfet_06v0 5.11 V | PASS (pp: 0.03 V margin) |
| E1 HBM 2 kV (reported) | vss+ nfet_03v3 5.34 (5.63 with 1 nF); pp+/- 6.04 (6.49) V, 23 nfet_03v3 over 5.0 | MISS |
| E1 CDM 1 A | without 1 nF: vss+ 6.13, pp 6.88 V MISS; with 1 nF: all complete cases <= 4.73 V PASS | PASS with 1 nF |
| E1 CDM 2 A (coordinator's requirement point, with 1 nF) | vss+ nfet_03v3 6.71 V; pp nfet_03v3 7.87 V, nfet_06v0 8.13 V (16 over 8.0) | MISS |
| E1 CDM 3 A | vss+ 9.6, vdd+ 6.97, pp 11.4 V | MISS |
| ESD bench proofs | known answer 10 ohm cell 6.953 V (6.95); negative control without clamps 14.3 V, 23 + 17 devices over | PASS |
| L1 Magic DRC | 0 | PASS |
| L2 read-back LVS + failing control | unique match; swap MAIN_P/MAIN_BIAS -> mismatch | PASS |
| L3 KLayout main / antenna | 0 / 0 | PASS |
| rail_site_check txpad_final | main 0, antenna 0 | PASS |
| L4 latch-up | 0 um2 uncovered at 5-20 um | PASS |
| A1 outline 2.78..484 x 0..1226.72, area <= 300,000 | bbox 0..286 x 0..692.26 (198,000 um2): x min 0 < 2.78 | MISS (outline; check the site-origin convention) |

- ESD misses: the over-limit devices are the 23 nfet_03v3 0.28 termination switches of the zapped leg (TU_* to TERM_VCM, e.g. X262/X114/X17)
  and, at CDM >= 2 A pp/vss+, 16-17 nfet_06v0 (driver cascodes, X277/X250/X9). Coordinator's pattern (local secondary: series R + small diodes)
  was not applied; nothing was redesigned.
- Incomplete ESD runs (not judged): cdm:1/3:vss:neg without 1 nF; cdm:1/2/3:vdd:neg and cdm:1:vss:neg with 1 nF.
- Up-diodes (PC-31 item 4, back-feed): 7 pd2nw PAD_x -> DVDD_x per pad, landing straight on ring DVDD. A powered TMDS sink on an unpowered
  die forward-biases them and holds DVDD up. Reported only.
- Not run: low-metal corner (no netres variant), junction-breakdown and MIM checks (the bench audits only MOS), simulated output drive / idle bench,
  return-loss limit (no limit was declared; RL 8.0 dB at 1.25 GHz, 4.9 dB at 2.5 GHz is information only).
- Commands: `bash rflow.sh a4 r4`; `python3 mkmodel.py b/a4/pad_txpad.ext.spice r4 typ|high models/a4_rt|rh.spice 1`; `./final.sh` (ka, term rt/rh/off,
  ac, acpub, gatec, gatecpub, checks.sh a4 kl rb lu rail, rail_site_check.py --gds b/a4/pad_txpad.gds --top pad_txpad --name txpad_final
  --out checks/a4/railsite, esdka, esdnc, esd without/with TB2_CDIE=1e-9); `python3 termtab.py a4rt a4rh`; `python3 paths.py r4/res.json`.
  tb2.py additions: TB2_CDIE, esdka, gatec/gatecpub, acpub. Cleaned: a1/a2/a3 builds, r1/r2, a1/a2 models, benches and checks, raw sim folders.

# CANDIDATE a5 (2026-11-20): local secondary clamp at the termination switch drains. NOT published, NOT committed. Work folder `sec/`.
## Rulings applied (coordinator, binding)
HBM judged at the devices; CDM judged with 1 nF die decoupling at 2 A (1 / 3 A reported); ring = the extracted bound of ../ring/REPORT.md
(DVDD near 0.155, DVSS near 0.189, DVDD far 0.46, DVSS far 0.57 ohm; far group 5 dvdd + 7 dvss; corner cells left out as in ring/esd3.py),
1 nF at the far node behind 0.5 ohm (as esd3 / clamp gen.py); primary site diodes judged by peak current density / energy per finger against
10 mA/um forward, 1 mA/um avalanche, 78 nJ (ring/REPORT.md rating, literature, no CDM credit); every other junction reverse V < model bv
(nd2ps 11 V, pd2nw 10.5 V); MIM <= 6 V; WIRE_TX tier HBM 1 kV (2 kV reported).
## Limits declared BEFORE the a5 queue (a4 list above unchanged otherwise)
- E1 every MOS max(|Vg-x|, |Vds|) <= 5.0 V (3.3 V devices) / 8.0 V (6 V devices): HBM 1 kV all 6 cases (tier), CDM 2 A with 1 nF all 6 cases
  (requirement); HBM 2 kV, CDM 1 / 3 A with 1 nF reported. E3 secondary + other diodes reverse < bv. E3p primary fingers vs the rating.
  E4 MIM <= 6 V. Model: high metal (rh) R+C model of the exact GDS.
- WT39: O1 bond -> cascode drains <= 2.0 ohm (typ and high); T1 100 ohm +-10 % incl. metal trimmable (a4 T1 +-5 % kept as the stricter
  check); gate C MAIN/POST/TMDS <= published; pad-node C per leg at 100 MHz <= published 3.193 pF (rt and c models).
- Layout: Magic DRC 0; read-back LVS unique + failing control; KLayout precheck main 0 / antenna 0; latch-up 0 um2 at 15 um;
  rail_site_check PASS; railconn clean incl. the new DVDDS_P / DVDDS_N nets (DVDD bands only).
- Default path: no --sec rebuild normalised-GDS identical to b/a4.
- Bench proofs: ESD known answer on the new ring (10 ohm cell, hand 0.66667 x 0.99326 x (10 + 0.025 + 0.189) = 6.764 V, tolerance 0.15 V).

## a5 results (2026-11-20). NOT published, NOT committed. Verdict: does NOT meet the goal (E1 CDM 2 A and pad-node C miss).
Files: generator `$P/analog/pads/tx_pad_layout.py` sha abeb6d4e (option `--sec`, default path unchanged), build `sec/b/a5` (GDS sha256 abb772b2...,
timestamp-normalised f5d70398..., schematic 53231c60), netres `sec/r5/res.json` 93a9e9d5, models `sec/models/a5_rh` 4e87c0dd / `a5_rt` 6a612d05 /
`a5_c` e9be280a (= ext.spice), bench `tb2.py` 34b9090c. Layout: per leg a diode row (nwell strip, n+ tap, 23 p+ islands 0.8 x 1.5 um = 1.2 um2
diode_pd2nw_06v0 under each TU riser), DVDDS_P / DVDDS_N new ports landing on the ring DVDD sub-bands 206-341 inside each site; the leg grows 5.6 um.
### Ring bound ported into tb2.py (TB2_RINGV / TB2_FAR / TB2_RDS env; defaults = the old lumped ring, unchanged)
Near dvdd+dvss cell behind 0.155 / 0.189 ohm, far 5 dvdd + 7 dvss behind a further 0.46 / 0.57 ohm, corner cells left out, site landings 0.025 ohm,
1 nF at the far node behind 0.5 ohm. --sec cathode landings (DVDDS) have their own path DS -> near cell 0.32 ohm (= 0.155 x 124/60 um of band
width: the landing bands are separate strips that join only at the provider cells; assumption). New outputs per run: other-junction reverse V vs
bv, primary-finger peak mA/um forward/reverse and energy (savecurrents), MIM (the cell has none: 0 devices). Known answer on the new ring:
6.747 V vs hand 6.764 V PASS (`bench/sec_esdka_bound-esd.json`, `esdka_bound`).
Bench deviations (stated): a5 high R model stalls in ngspice at the CDM fall edge (3.69 ns) and in HBM tails -> CDM run to 3.6 ns (flat top
2.2-3.2 ns covered), HBM to 60 ns (peak at 5-7 ns), options abstol=1e-9 vntol=1e-4, per-attempt wall limit; retries recorded per run.
### a4 baseline at the bound (models/a4_rh, 1 nF; `bench/a4b_cdie-esd.json`)
HBM 1 kV: worst n03 4.91 V, n06 5.05 V (pp), PASS. HBM 2 kV: n03 6.30 V (23 over). CDM 2 A: vss+ n03 8.67 / n06 8.67 V; pp n03 9.18 / n06 9.27 V
(23 + 17 over) - worse than the old lumped ring (7.87 / 8.13) because the clamps sit behind the extracted R and the 1 nF behind 0.5 ohm + far R.
CDM 1 A: n03 5.90 V (23 over); 3 A: 12.0 V. Primary fingers: CDM 2 A 5.69 mA/um 1.3 nJ, 3 A 8.53 mA/um, HBM 2 kV 3.77 mA/um 55.5 nJ: inside
10 mA/um / 78 nJ. Negative runs: all complete except cdm:2:vss:neg and cdm:1:vss:neg (abort at 2.51 / 2.63 ns, after the 2.2 ns peak current;
values reached <= 1.0 V), also with the 3.6 ns stop and three option sets.
### Model-level sizing (before layout; a4_rh + 46 diodes, `sec/mkcand.py`)
| p+ area / route | CDM 2 A vss+ worst n03 | pad-node C (rt, 100 MHz) |
|---|---|---|
| none (a4) | 8.67 V | 3.152 pF |
| 0.45 um2 / 1.2 ohm | 6.44 V | 3.167 |
| 1.2 um2 / 1.2 ohm (chosen) | 5.73 V | 3.183 |
| 4 um2 / 0.5 ohm | 5.20 V | not run (~3.25 est.) |
Floor: the switch gate (TERM_TRIM, core-held) and TU sit across ring DVDD-DVSS, which itself rises 3.85-3.88 V at CDM 2 A; a DVDD-referenced
diode cannot hold TU below ~rail + Vf. No size meets 5.0 V; the 6 V cascodes (drain = pad) are not reachable by a secondary at all
(pad-VSS 9.5 V; bond->drain metal is 1.4 ohm, a secondary there would have to sink ~2 A).

| Limit | a5 | Result |
|---|---|---|
| Magic DRC | 0 | PASS |
| Read-back LVS pos / failing control (MAIN_P/MAIN_BIAS swap) | match unique / mismatch | PASS |
| KLayout precheck main / antenna | 0 / 0 (after an explicit Nplus box over the tap strips: Magic left 0.35 um NP.1 steps) | PASS |
| Latch-up uncovered at 15 um | 0.0 um2 | PASS |
| rail_site_check txpad_a5 | main 0, antenna 0 | PASS |
| railconn PAD/VSS/DVDD_P/N + DVDDS_P/N | clean; DVDDS on DVDD bands 206-334 only | PASS |
| Default path (no --sec) | normalised GDS 3a706943 == b/a4; .mag and schematic identical | PASS |
| A1 outline | GDS bbox (3.5, 0)-(285, 692.26) (KLayout), inside 2.78..484 x 0..1226.72 | PASS (see A1 note) |
| O1 bond -> cascode drains <= 2.0 ohm | typ 1.373, high 1.759 | PASS |
| T1 / WT39(2) 100 ohm, 23 corners, rt / rh | 97.63-102.15 / 97.61-102.78 at codes 3..12; P-N +0.19..+0.42 | PASS |
| Term known answer / off control | 91.577 / a5 off >= 1.26e10 ohm | PASS |
| Gate C MAIN/POST/TMDS vs published | 0.19/0.30 pF (unchanged from a4) vs 0.32-0.61 | PASS |
| Pad-node C per leg 100 MHz <= 3.193 pF | a5_c 3.126 (+0.050 vs a4), a5_rt 3.216 (+0.064) | **MISS** (rt by 0.023 pF) |
| E1 HBM 1 kV vss/vdd cases (exact a5 model) | n03 3.50, n06 4.31 V (a4 4.42 / 4.42) | PASS |
| E1 HBM 1 kV pp (stand-in: a4_rh + same diodes, the a5 model does not converge pp) | n03 4.23, n06 4.97 V (a4 4.91 / 5.05) | PASS (stand-in) |
| E1 HBM 2 kV (report) | vss/vdd n03 4.18, n06 5.65; pp stand-in n03 5.06 (8 over), n06 6.41 | report |
| E1 CDM 2 A 1 nF (requirement) | vss+ n03 5.55 (23 over), n06 8.32 (17 over); pp- n03 6.39 (23), n06 8.96 (17); pp+ stand-in 6.43 / 9.02 | **MISS** |
| E1 CDM 1 A / 3 A (report) | 1 A: n03 4.67, n06 5.87 PASS; 3 A: vss+/pp not converged on a5 | report |
| E3 secondary / other junctions < bv | max 6.20 V (pd2nw, bv 10.5), 0 over | PASS |
| E3p primary fingers | CDM 2 A 5.36 mA/um 1.2 nJ; 3 A 8.04 mA/um; HBM 2 kV 3.55 mA/um 20.9 nJ (limits 10 / 1 mA/um, 78 nJ) | PASS |
| E4 MIM <= 6 V | no MIM in the cell | n/a |
| ESD bench proofs | known answer 6.747 V (hand 6.764) | PASS |

Not run / not converged: a5 R model pad-to-pad cases (hbm:1/2:pp, cdm:2:pp:pos, cdm:3:pp) stop at the pulse start in ngspice (all option sets
tried); stand-in = `sec/models/sz_rh_1.2` (a4 R model + identical diodes, lumped 1.2 ohm route; `bench/szpp-esd.json`). Also incomplete on a5:
cdm:1:vdd:neg (3.2 ns), cdm:3:vss:+/-. HBM without 1 nF, ss/ff/hot ESD, low-metal ESD, typ-metal ESD, return loss, drive/idle bench (vector
syntax error, as a4), secondary-stripped control (the a4 baseline is the same cell without them).
A1 note: the published `2.78` is the measured bbox of the published combined.gds (Metal5 at x 2.78, the old core trunk bank edge
`edge=2.78` in layout.py / termination_buffer_layout.py); its allocation regions start at x 0. a4's "x min 0" came from the generator's
declared `bbox_um` [0, 0, 286, 692.26], not the GDS: KLayout reads a4 (3.5, 0)-(285, 692.26), inside. Limit not moved.
Commands: `python3 tx_pad_layout.py sec/b/a5 --sec '{"an": [0.8, 1.5]}'`; `bash sec/checks2.sh a5 kl rb lu rail`; `rail_site_check.py --gds sec/b/a5/pad_txpad.gds
--top pad_txpad --name txpad_a5 --out sec/checks/a5/railsite`; `bash sec/rflow2.sh a5 r5`; `python3 sec/mkmodel2.py b/a5/pad_txpad.ext.spice r5 typ|high models/a5_rt|rh.spice 1`;
`sec/q5.sh` (ka, term, ac, gatec, esdka), `sec/q5e.sh` / `sec/q5g.sh` / `sec/q5h.sh` (ESD with TB2_RINGV=0.155,0.189,0.46,0.57 TB2_FAR=5,7 TB2_CDIE=1e-9);
`python3 sec/esdtab.py <tag>`; `python3 termtab.py a5rt a5rh`; `python3 ../paths.py sec/r5/res.json`.
What it would take: the 3.3 V termination switches need TU held <= 5 V vs the core-held gate while the ring rail is ~3.9 V up: either a
VSS-referenced clamp at TU that does not conduct at 3.3 V signal levels (e.g. a stacked diode string or a GGNMOS, no PDK snapback model) or
6 V switches; the cascodes need the pad itself lower at CDM 2 A (stronger primary path / lower site DVDD route R 0.40 ohm / ring), i.e. a
ruling on primaries or the ring, not a secondary.

# CANDIDATE a6 (2026-11-20): 6 V termination switches, CDM with near-site decap. NOT published, NOT committed. Work folder `sec/`.
## Rulings applied (coordinator, binding; from the a6 brief)
(1) termination switches nfet_06v0 (static); their gate / junction C counted in the pad-node C and WT39 targets. (2) CDM judged with 1 nF of ring
decap behind <= 0.7 ohm (incl. its own series R) from the ring node at the pad site (bench: Cdie RD-RS 1 nF + 0.7 ohm, `TB2_CDIEAT=site`; no far
1 nF); ring otherwise at the extracted bound (0.155 / 0.189 / 0.46 / 0.57 ohm, far 5 + 7 cells). (3) if 6 V cascodes > 8.0 V at CDM 2 A: more primary
diode area in the site. (4) primary fingers 10 mA/um fwd / 1 mA/um avalanche / 78 nJ; other junctions reverse < model bv; gates 8.0 V (6 V) / 5.0 V
(3.3 V); WIRE_TX HBM 1 kV tier (2 kV reported); CDM 2 A requirement (1 / 3 A reported). a5 secondary diodes kept only if they still help.
## Limits declared BEFORE any a6 run
- E1 every MOS max(|Vg-x|, |Vds|) <= 5.0 V (3.3 V) / 8.0 V (6 V incl. the new termination switches): HBM 1 kV all 6 cases (tier), CDM 2 A all 6 cases
  with the near-site 1 nF (requirement); HBM 2 kV, CDM 1 / 3 A reported. E3 non-primary junctions reverse < bv. E3p primary fingers vs (4). E4 MIM <= 6 V.
  Model: high-metal R+C model (rh) of the exact a6 GDS for every case; any stand-in named per row.
- WT39: O1 bond -> cascode drains <= 2.0 ohm (typ, high); T1w 100 ohm +-10 % incl. metal at some trim code, 23 corners, typ + high metal (requirement);
  a4's T1 +-5 % with >= 2 codes margin kept as a reported stricter check; P-N <= 1.0 ohm; gate C MAIN/POST/TMDS <= published (0 V / 3.3 V);
  pad-node C per leg at 100 MHz <= published 3.193 pF (rt and c models; an excess is reported as a MISS, not waived). Trim-gate C reported (info).
- Layout: Magic DRC 0; read-back LVS unique + failing control (MAIN_P/MAIN_BIAS swap -> mismatch); KLayout precheck main 0 / antenna 0; latch-up 0 um2;
  rail_site_check PASS; A1 outline inside 2.78..484 x 0..1226.72 (KLayout bbox).
- Default path: generator without the new option rebuilds b/a4 identically except timestamps (normalised GDS / .mag / schematic).
- Bench proofs: term known answer 91.58 + TERM_ENABLE 0 negative control; ESD known answer on the bound ring (6.764 V +- 0.15).

## a6 results (2026-11-20). NOT published, NOT committed. Verdict: ESD / layout / O1 / gate C PASS; pad-node C MISS (large); T1 +-5 % (old stricter) MISS.
Files: generator `$P/analog/pads/tx_pad_layout.py` sha 7e06e082 (new option `--sw6`; `--sec` kept, unused), build `sec/b/a6` GDS sha256 ea424986...,
schematic 24fcc6c8, netres `sec/r6`, models `sec/models/a6_rt|a6_rh|a6_c|a6_zero`, bench `tb2.py` f1772f69 (adds TB2_CDIEAT=site / TB2_RDIE, TB2_GATEPINS).
Design (all behind --sw6; default path rebuild: normalised GDS 3a706943 == b/a4, .mag and schematic identical):
- 46 termination switches nfet_06v0 66/0.7 nf=1 (was 03v3 20 or 12/0.28); base poly 2 x 2.0 (unchanged), trim poly 2 x 1.0 (was 2.8).
  Why so big: at TERM_VCM 1.65 V the gate overdrive of a 6 V nfet is 0.1-0.3 V at ss / 3.15 V: Ron*W 50 kohm.um (03v3: 5 kohm.um), ss/ff spread 6x.
  Analytic + simulated sizing (`sec/sz6/opt*.py`, `corners.json`): ~1500 um of 6 V width per leg is the minimum for +-10 % trimmable.
- Leg row 46.5 um taller; driver + control cell moved up 46.5 um (cell 286 x 738.76, was 692.26; top pins move: integration note).
- pt_tx_ctl TERM_BUF_P 4 -> 40 um (the 4 um buffer dropped 80 mV into the bleed chain at ss; 6 V switch R doubled). Deviation from circuits.py sizes.
- Neck Metal3-5 stack over y 372..yb1 (the neck grew 46 um; restores O1 / O3).
- Primaries (ruling 3): what-if on a4 metal + 6 V switches at the new decap: CDM 2 A pp 8.12 V (16 cascodes over). +4 down only: 8.10 (no help);
  +2/+4/+6 up: 7.61/7.28/7.00. Chosen +3 pd2nw per pad (row at depth 107 right of the neck, DVDD landing on band 118-125, tap landing on DVSS 70-117).
- a5 secondary diodes dropped: the switch limit is now 8.0 V and TU never exceeds the pad (cascode drain) voltage; they cost C and convergence.

| Limit | a6 | Result |
|---|---|---|
| Magic DRC | 0 | PASS |
| Read-back LVS pos / failing control (MAIN_P/MAIN_BIAS swap) | unique match / mismatch | PASS |
| KLayout precheck main / antenna | 0 / 0 | PASS |
| Latch-up uncovered at 15 um | 0.0 um2 | PASS |
| rail_site_check txpad_a6; railconn PAD/VSS/DVDD | PASS; clean (DVDD bands 118/134/150/166/182) | PASS |
| Default path | identical to b/a4 | PASS |
| O1 bond -> 16 cascode drains <= 2.0 ohm | typ 1.354, high 1.734 (equal-split max 1.823) | PASS |
| O3 leg path drop at 21 mA <= 60 mV | typ 40.0, high 57.5 | PASS |
| WT39 T1w 100 ohm +-10 % trimmable, 23 corners | rt 93.90..105.41 (best codes 1..15), rh 94.28..105.66 (2..15); P-N +0.18..+0.42 | PASS (no code margin at ss/3.15 V: needs code 14-15) |
| a4 T1 +-5 % with 2 codes margin (reported) | rt fails ss 3.15, ff/fs 3.35; rh 7 corners | MISS (report) |
| Term known answer / off control | 91.577 / 674.8 kohm; a6 off >= 1.46e10 ohm | PASS |
| Gate C MAIN/POST/TMDS vs published | 0.18-0.30 pF (= a4) vs 0.32-0.61 | PASS |
| Trim gate C (info) | TERM_TRIM3 1.10 / 2.02 pF (a4 0.20 / 0.34), TRIM0 0.17 / 0.29 (a4 0.06 / 0.08) at 0 / 3.3 V | info: core drivers see 6x load |
| Pad-node C per leg 100 MHz <= 3.193 pF | a6_c 4.418, a6_rt 4.515 (a4 3.152); zero-R self-check 4.515 | **MISS by 1.32 pF** |
| Return loss (info) | 16.8 dB 100 MHz, 6.4 dB 1.25 GHz, 3.7 dB 2.5 GHz (a4: 8.0 / 4.9 at 1.25 / 2.5) | info |
| E1 HBM 1 kV (tier), 6 cases | n06 max 4.36 V, n03 0.69 V | PASS |
| E1 CDM 2 A, 1 nF at site / 0.7 ohm (requirement), 6 cases | vss+ n06 6.23, pp+/- 6.92 / 6.92, others <= 3.6 V; n03 <= 0.77 | PASS (1.08 V margin) |
| E1 HBM 2 kV (report) | n06 5.53 V | PASS |
| E1 CDM 1 A (report) | n06 4.33 V | PASS |
| E1 CDM 3 A (report) | vss+ 8.07, pp 8.87 V (31-32 n06 over) | MISS (report) |
| E3 other junctions < bv | no non-primary diodes in a6; MOS junctions covered by Vds | n/a |
| E3p primary fingers (10 mA/um, 1 mA/um, 78 nJ) | CDM 2 A 4.44 mA/um 0.9 nJ; 3 A 6.67; HBM 2 kV 2.94 mA/um 15.5 nJ; reverse 0 | PASS |
| E4 MIM | none | n/a |
| ESD bench proofs | known answer 6.747 V (hand 6.763) | PASS |
| ESD negative control (no ring clamps, cdm:2:vss:pos) | n06 7.09 V, 0 over | NOT discriminating: with 1 nF at the site the decap alone holds 2 A for 1 ns; the a4 no-clamp control (14.3 V) remains the clamp proof |
All ESD runs complete on the exact a6 high-metal model (no stand-in, no retries needed; CDM run to 3.6 ns, HBM to 60 ns as a5).
Model note: the 3 new up-diodes' ring side is the site island SVDD_x (netres pin boxes incl. the new 118-125 landing, `sec/fixspec3.py`).
Not run: low-metal, ss/ff ESD, drive / idle bench (vector syntax error as a4), TERM_ENABLE_LOCAL ramp / mismatch sensitivity of the 0.1-0.3 V overdrive.
Commands: `python3 $P/analog/pads/tx_pad_layout.py sec/b/a6 --sw6 '{"w": 66, "lb": 2.0, "lt": 1.0, "upx": [57, 63, 69], "yu": 107, "bufp": 40}'`;
`bash sec/rflow6.sh a6 r6`; `python3 mkmodel.py sec/b/a6/pad_txpad.ext.spice sec/r6 typ|high sec/models/a6_rt|rh.spice 1` (0.01 -> a6_zero);
`sec/q6.sh` (ka, term, ac, gatec, trim gatec, esdka, ESD matrix with `sec/env6.sh`, esdnc); `sec/c6.sh` (checks6.sh kl rb lu rail, rail_site_check, default rebuild);
`python3 sec/gdsnorm.py`; `python3 termtab.py a6rt a6rh`; `python3 paths.py sec/r6/res.json`. Cleaned: a5 build / netres / models / checks, sizing models, raw benches.
Options for the C miss (need a ruling): nfet_06v0_nvt (native) switches L 1.8: ~18 um per unit (414 um/leg vs 1518), analytic worst 4-5 %, est. C +0.3 pF
instead of +1.3 (still a miss by ~0.25); or a pumped gate for 6 V switches; or back to 03v3 switches with the a5 floor (CDM 2 A miss); or accept the C.

# CANDIDATE a7 (2026-11-20): 3.3 V termination switches (a4/a5 legs) + a6's 3 extra up-diodes per pad. NOT published, NOT committed. STOPPED at the screen.
Direction relayed by agent a0b585bf ("coordinator withdrew the 6 V switch ruling"); not verifiable from here, followed (it narrows work). a6 build, netres,
models, checks and benches deleted (a6 numbers stay in the section above). `--sw6` kept in the generator but out of the default path (marked abandoned).
Generator: new option `--upx '{"x": [57, 63, 69], "yu": 107}'` (default OFF). Build `sec/b/a7` (GDS d3d98ca8...), netres `sec/r7`, models `sec/models/a7_rt|rh|c`.
Bench: CDM decap per esd3.py SITECAP = 1 nF at the site, 0.7 ohm per rail (`sec/env7.sh`, TB2_CDIEAT=site TB2_RDIE=1.4 loop); new what-if env TB2_RGATE.
Limits: as declared for a6, with the termination switches back to 3.3 V (5.0 V) and pad-node C <= 3.193 pF (R+C) a hard limit.

| Limit | a7 | Result |
|---|---|---|
| Magic DRC / netgen LVS (generator) | 0 / unique match | PASS (KLayout, rb LVS, latch-up, rail_site NOT run: stopped at the screen) |
| O1 bond -> cascodes <= 2.0 ohm | typ 1.365, high 1.750 | PASS |
| O3 drop <= 60 mV at 21 mA | high 56.3 mV | PASS |
| Pad-node C per leg (rt, 100 MHz) <= 3.193 pF | 3.243 (a4 3.152 + 3 up-diodes) | **MISS by 0.050** |
| CDM 2 A vss+ (exact a7_rh) | 3.3 V switches 6.59 V (23 over), cascodes 6.59 V | **MISS** (switches) / PASS (cascodes) |
| CDM 2 A pp+ (exact a7_rh) | 3.3 V switches 6.97 V (23 over), cascodes 6.94 V | **MISS** / PASS |
| What-if: 20 kohm gate series R on TERM_TRIM pins | gate 6.05 V, but Vds 6.31 V (TU - TERM_VCM) | no fix: the stress is Vds of the off switch |
| What-if (last option): native nfet_06v0_nvt 18/1.8, poly 1.4 / 1.0 | pad C 3.221 pF (MISS by 0.028); CDM 2 A cascodes 6.98 V; nvt switches not in the bench audit (TU-VCM same as 03v3 case, ~6.3-7.0 V < 8.0) | C MISS; termination not simulated |
Why it is not "small": a series R in the drain path cannot lower TU (the off switch carries no current, TU follows the pad through its poly); the
pad sits 7.4-7.6 V above core VSS at 2 A; holding 5.0 V needs ~2.5 V less, more than a site can give (up-diodes: ~-0.15 V per finger pair,
each +28 fF while C already misses). Not run: term, gatec, HBM, CDM 1/3 A, negatives, layout checks on a7 (screen failed first).
Commands: `python3 $P/analog/pads/tx_pad_layout.py sec/b/a7 --upx '{"x": [57, 63, 69], "yu": 107}'`; `bash sec/rflow6.sh a7 r7`; `python3 mkmodel.py
sec/b/a7/pad_txpad.ext.spice sec/r7 typ|high sec/models/a7_rt|rh.spice 1`; `. sec/env7.sh; python3 tb2.py esd sec/models/a7_rh.spice <tag> cdm:2:vss:pos cdm:2:pp:pos`;
`python3 tb2.py ac sec/models/a7_rt.spice a7rt`; what-ifs `sec/sz6/swnvt.py`, `TB2_RGATE=20k`.
Needs a ruling: no tried combination meets 3.3 V switches <= 5.0 V at CDM 2 A AND pad C <= 3.193 pF. Choices: CDM 2 A for WIRE_TX judged against
1 A (a7 1 A not run; a4 1 A with near decap was <= 4.73 V); native switches with a C allowance of ~+0.03 pF (or drop the extra up-diodes and recheck
cascodes); or a VSS-referenced clamp at TU (PC-44 option b).
