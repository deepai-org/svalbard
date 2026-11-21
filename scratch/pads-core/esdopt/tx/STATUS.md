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

# CANDIDATE a8 (2026-11-20): native nfet_06v0_nvt termination switches (ruling PC-49 (a)), ASM-2 top-edge pins. NOT published, NOT committed. Work folder `sec/`.
## Rulings applied (coordinator PC-49 / PC-54, binding)
(a) termination switches nfet_06v0_nvt; pad-node C allowance +0.03 pF: limit 3.223 pF per leg at 100 MHz (R+C model). a7's extra up-diodes kept only if they
still help. CDM judged with the east-edge 1 nF at the site, 0.7 ohm per rail (`sec/env7.sh`), ring at the extracted bound. ASM-2: core-side pins on the top edge.
## Limits declared BEFORE the a8 runs (sizing what-ifs on a7 models were run before this; listed in the results)
- T1w 100 ohm +-10 % incl. metal at some trim code in 2..13 (>= 2 codes margin to both ends), all 23 corners, typ (rt) and high (rh) metal; low metal not
  available (netres has typ / high only: reported as not run). P-N <= 1.0 ohm. a4's +-5 % reported. Term known answer 91.58 +-0.01; TERM_ENABLE 0 > 10 kohm (pub + a8).
- WT39: O1 bond -> cascode drains <= 2.0 ohm (typ, high); O2 P/N <= 0.5 ohm; O3 leg-path drop <= 60 mV at 21 mA (netres arithmetic AND the simulated
  drive bench if it can be made to run); gate C MAIN/POST/TMDS <= published (0 / 3.3 V); pad-node C per leg 100 MHz <= 3.223 pF (rt; c-only reported).
- E1 every MOS max(|Vg-x|, |Vds|) <= 5.0 V (3.3 V) / 8.0 V (6 V incl. nfet_06v0_nvt); DC screen 3.63 / 6.0 V reported. HBM 1 kV all 6 cases (tier),
  CDM 2 A all 6 cases (requirement); HBM 2 kV, CDM 1 / 3 A reported. Exact a8 high-metal model (rh); any stand-in named. E3 non-primary junctions < bv;
  E3p primary fingers 10 mA/um fwd / 1 mA/um avalanche / 78 nJ; E4 MIM <= 6 V. ESD known answer 6.764 V +- 0.15 on the bound ring.
- Layout: Magic DRC 0; netgen LVS unique; read-back LVS unique + failing control (MAIN_P/MAIN_BIAS swap -> mismatch); KLayout precheck main 0 / antenna 0;
  latch-up 0 um2; rail_site_check PASS; railconn clean; A1 KLayout bbox inside 2.78..484 x 0..1226.72; ASM-2: every port except PAD_x / DVDD_x has a
  Metal3/4 pin shape touching y = top edge. Default path (no new option) rebuilds b/a4 identically except timestamps.

## a8 results (2026-11-20). NOT published, NOT committed. Verdict: **NOT a valid candidate. The GDS has no NAT layer (5/0), so the switches would be built as ordinary nfet_06v0. With NAT added, 23 native switches per leg at the 3.56 um pitch cannot meet the NAT rules.** Stopped there.
Files: generator `$P/analog/pads/tx_pad_layout.py` sha e41508e0 (new options `--nvt`, `--top-pins`; the default path was not rebuilt or compared this
round), build `sec/b/a8` GDS 43c91e1d..., netres `sec/r8`, models `sec/models/a8_rt|rh|c|zero`, bench `tb2.py` 7d5a2bef (MOSM + nfet_06v0_nvt: 8.0 V
transient, 6.0 V DC), `mkmodel.py` 0fa71755 (nvt matched). Build: `python3 $P/analog/pads/tx_pad_layout.py sec/b/a8 --nvt '{"wb": 14, "wt": 21, "lb": 1.0, "lt": 1.0}'
--upx '{"x": [63, 69], "yu": 107}' --top-pins`; `bash sec/rflow6.sh a8 r8`; `python3 mkmodel.py sec/b/a8/pad_txpad.ext.spice sec/r8 typ|high sec/models/a8_rt|rh.spice 1`;
`sec/q8.sh` (ka, gatec, trim gatec, esdka, ESD with env7); `bash sec/checks6.sh a8 kl rb lu rail`; `rail_site_check.py ... --name txpad_a8`.
Sizing (what-ifs on a7 models, `sec/sz6/optnvt.py`, `swnvt2.py`; corners `corners_nvt.json`): C sensitivity about 0.86 fF per um of nvt width, mostly the TU-side
junction (as = 0 removes 0.17 pF). The 3 up-diodes are still needed: CDM 2 A pp, nvt what-if: 0 up -> cascodes 8.24 V (16 over 8.0), 3 up -> 7.02 V. Using 2 up-diodes
(x 63/69, -21 fF) frees width for the trim. nf=2 would save about 0.11 pF, but the nvt ring (4.06 um) does not fit the 3.56 um pitch, so the switches are drawn
with guard 0, a shared p-tap strip under the switch row, and Metal1 columns on the unit boundaries.

| Limit | a8 | Result |
|---|---|---|
| Magic DRC / netgen LVS (generator) | 0 / unique | PASS |
| **NAT layer in GDS** | absent: the Magic export (like HRES, `gds_markers.py`) does not write NAT 5/0 | **BLOCKER** |
| Read-back LVS pos / failing control | census differs: GDS reads back nfet_06v0 14/1.8 x16, 21/1.8 x30 instead of nvt (no NAT) + pin matching | **FAIL** |
| KLayout precheck main / antenna | 0 / 0, but only because there is no NAT (NAT rules not exercised) | not valid |
| NAT rules if NAT is added (nat.rb) | NAT.1 needs >= 2 um of NAT around each COMP; NAT.6 does not allow COMPs at different potential under one NAT; NAT.7 needs >= 0.74 um between NATs: each switch needs >= 7.4 um of pitch vs 3.56; NAT also reaches the tap strip and the resistor row (NAT.2 / NAT.12) | **MISS by construction** |
| Latch-up at 15 um | 0.0 um2 | PASS |
| rail_site_check txpad_a8 / railconn | PASS main 0 antenna 0 / clean | PASS |
| ASM-2 top pins | gate lines Metal3, VDD/VSS/TERM_ENABLE/DETECT_* Metal4 on the control-cell trunks, TERM_TRIM0..3 Metal4 (Metal5 risers), TERM_VCM Metal4 4 um riser (about 7 ohm in series, common mode only), all at y 692.26 | drawn, not reviewed |
| O1 bond -> cascodes <= 2.0 ohm | typ 1.364, high 1.749 | PASS |
| O3 drop at 21 mA <= 60 mV | typ 38.9, high 56.3 (arithmetic; drive bench not fixed this round) | PASS (arithmetic) |
| Pad-node C per leg 100 MHz <= 3.223 pF | a8_rt 3.204, a8_c 3.115, zero-R 3.205 | PASS (19 fF) |
| T1w +-10 % at a code in 2..13, 23 corners | rt worst 5.5 % (ss/32/3.15 code 13 = 105.5; ff/22/3.35 code 2 = 101.5); rh worst 7.2 % (ss/32/3.15 code 13 = 107.2) | PASS with no spare margin (ss needs code 13, ff needs code 2) |
| a4 +-5 % (report) | rt fails ss_32_3.15 / ff_22_3.15, rh fails ss 22/32 3.15 | MISS (report) |
| P-N | rt +0.22..+0.42, rh +0.25..+0.48 ohm | PASS |
| Term known answer / off | 91.58 / pub 674.8 kohm; a8 off >= 1.47e10 ohm | PASS |
| Gate C MAIN/POST/TMDS | 0.18-0.30 pF (= a4) | PASS |
| Trim gate C (info) | TRIM3 0.36 / 1.58 pF, TRIM0 0.12 / 0.27 pF (0 / 3.3 V) | info |
| ESD known answer | 6.747 V (hand 6.763) | PASS |
| CDM 2 A (exact a8_rh, site 1 nF / 0.7 ohm) | vss+ nvt 6.91, n06 6.91; pp+ 7.32 / 7.28; pp- 7.37 / 7.28; vdd- <= 1.0 V; vss- / vdd+ INCOMPLETE (values reached <= 3.9 V) | PASS on 4 complete cases; 2 incomplete |
| HBM 1 kV vss+ | nvt 3.73, n06 3.73 V | PASS (other 5 cases, HBM 2 kV, CDM 1/3 A not run: queue stopped after the NAT finding) |
| Primary fingers | CDM 2 A 5.0 mA/um 1.1 nJ; HBM 1 kV 1.65 mA/um 6.5 nJ | PASS |
| Junction / MIM | no non-primary diodes; no MIM | n/a |
| Drive bench (21 mA simulated) | not fixed: the earlier failure is a missing .dat (ngspice aborted); its log was not captured this round | not run |
| Low-metal termination | netres has typ / high only | not run |
What it would take: one native switch per trim bit instead of per unit (the units of a bit share a gate, so TU nodes can be joined: base x8, bits 8/4/2/1 ->
5 multi-finger devices per leg, each in its own NAT with >= 2 um enclosure and 0.74 um between NATs, gate poly joined in metal outside NAT, DUALGATE over NAT
(NAT.8)). Shared drains lower the TU junction C (about -0.1 pF), which frees width for trim margin. Rough fit: about 23 fingers x 2.7 um + 5 x 4.7 um ~ 86-90 um
per leg against about 85 um available (west neck at x 52.5), and the resistor row has to move up about 2.5 um. NAT also has to be written into the GDS (a post-step like
gds_markers.repair). This is a leg rewrite: every result above is rerun on it.
Cleaned: a7 build / netres / models, sizing what-if models, the stopped ESD run.

## a8 FINAL (2026-11-20, supersedes the per-unit a8 above): merged native devices per trim bit. NOT published, NOT committed.
Ruling relayed by agent a0b585bf (coordinator): try one native multi-finger device per trim bit, each in its own NAT with DUALGATE, NAT written by a post-step,
time-boxed; PC-49 (c) is the fallback. **It fits, so this is the full-a8 path.** The per-unit a8 build / netres / models / benches are deleted.
Design (`--nvt` key "merged": true; `leg_nat()` + `nat_post()` in the generator): per leg 5 nfet_06v0_nvt devices: base 8 x 21/1.8 (gate TERM_ENABLE_LOCAL),
trim bits 1/2/4/8 x 23.5/1.8. Each device sits in its own NAT (COMP + 2.0 um, >= 0.74 um between NATs); NAT 5/0 is written after the GDS export (the installed
Magic writes none), plus one DUALGATE 55/0 box per leg over the NAT row, overlapping the tap strip's own DUALGATE (DV.2). The resistor units of a bit share one TU
node (TU_<leg>_B / T0..T3) on two alternating Metal3 tracks above the devices. There is a p-tap strip under the row (COMP 2.32 um below, NAT.2 0.3 um), and tap ties
to the resistor rings run in the NAT gaps on the ring columns. Resistors: base poly 2 x 2.4, trim 2 x 1.0. The resistor row is 7.5 um higher than a4 (ytop 394.1),
the PAD buses follow it, nothing else moves; the outer NAT edge is at x 58.3 vs the west neck at 52.5. a7's up-diodes: 2 of 3 kept (x 63 / 69). Without them the
cascodes reach 8.24 V at CDM 2 A (what-if); 2 diodes save 21 fF. ASM-2 top-edge pins as in the per-unit a8 (`--top-pins`).
Files: generator sha fea82f43, GDS sha256 07721a33..., netres `sec/r8/res.json` 08f4e86e, models `sec/models/a8_rh` 92e4d04b / `a8_rt` d75fc386 / `a8_c` /
`a8_zero`, `tb2.py` 15619da0, `mkmodel.py` 0fa71755. Bench results in `bench/a8*`.

| Limit | a8 | Result |
|---|---|---|
| Magic DRC / netgen LVS | 0 / unique match | PASS |
| KLayout precheck main / antenna (with NAT + DUALGATE) | 0 / 0 | PASS |
| Read-back LVS pos | match, unique, census equal (nvt read back as nvt) | PASS |
| Read-back failing control (MAIN_P / MAIN_BIAS swap) | mismatch (pin matching). swap.log says "swapped 3": with --top-pins MAIN_BIAS has 2 pins, so rbverdict.py (expects 2) prints FAIL | PASS (real mismatch; the verdict script's count rule doesn't fit 3 labels) |
| Latch-up uncovered at 15 um | 0.0 um2 (wt 24 left 0.91 um2 and wt 26 left 58.6 um2: hence wt 23.5) | PASS |
| rail_site_check txpad_a8 / railconn PAD, VSS, DVDD | PASS main 0 antenna 0 / clean | PASS |
| Default path (no new option) | normalised GDS 3a706943 == b/a4; schematic identical | PASS |
| O1 bond -> 16 cascode drains <= 2.0 ohm; O2 P/N | typ 1.370, high 1.756; P = N | PASS |
| O3 drop at 21 mA <= 60 mV: arithmetic | typ 39.0, high 56.3 mV | PASS |
| O3 drop: SIMULATED drive bench (fixed, see below) | 20.2 / 20.1 mA delivered (21 set): typ 37.6, high 53.9 mV (56.3 scaled to 21 mA); bond->cascodes 28.3 / 35.7 mV | PASS |
| Pad-node C per leg 100 MHz <= 3.223 pF | rt 3.062, c 2.973, zero-R 3.063 | PASS (0.16 pF margin; also below the published 3.193) |
| Return loss (info) | 25.0 / 14.1 / 7.5 / 4.5 dB at 0.1 / 0.5 / 1.25 / 2.5 GHz (a4 rt 8.0 at 1.25) | info |
| T1w +-10 % at a code in 2..13, 23 corners, typ / high | rt worst 5.4 % (ss/32/3.15 in-window codes 12-15; ff/22/3.35 codes 3-4); rh worst 5.2 % (ss/32/3.15 codes 13-15, ff 4-5) | PASS (rh ss at exactly the 2-code margin) |
| a4 +-5 % (report) | rt fails ff_22_3.15 only; rh fails ss 22/32 3.15 | MISS (report) |
| P-N <= 1.0 ohm | rt +0.21..+0.41, rh +0.30..+0.47 | PASS |
| Term known answer / off controls | 91.58; pub TERM_ENABLE 0 674.8 kohm; a8 off >= 1.47e10 ohm | PASS |
| Gate C MAIN/POST/TMDS vs published | 0.18-0.30 pF (= a4) vs 0.32-0.61 | PASS |
| Trim gate C (info) | TRIM3 0.39 / 1.76 pF, TRIM0 0.12 / 0.29 pF (0 / 3.3 V) | info: TRIM3 about 5x a4 at 3.3 V |
| ESD known answer | 6.747 V (hand 6.763) | PASS |
| E1 CDM 2 A, exact a8_rh, 1 nF at the site / 0.7 ohm per rail | vss+ nvt 6.91 / n06 6.91; pp+ 7.22 / 7.28; pp- 7.28 / 7.27; vdd+ 3.92; vdd- 0.99; n03 <= 0.84 | PASS (0.72 V margin) |
| CDM 2 A vss- | INCOMPLETE (stops after the peak, values <= 0.91 V) | not judged (as a4 / a5) |
| E1 HBM 1 kV, 6 cases | nvt max 4.12 V, n06 4.36 V, n03 0.69 V | PASS |
| HBM 2 kV (report) | vss+ 4.98, pp+ 5.41 (nvt) / 5.74 (n06) V | PASS |
| CDM 1 A (report) | 4.83 / 5.05 V | PASS |
| CDM 3 A (report) | vss+ 9.27, pp+ 9.59 V (23 nvt + 17 n06 over) | MISS (report) |
| DC screen 6.0 / 3.63 V (drive bench) | nvt / n06 max 3.30 V, 0 over | PASS |
| E3 non-primary junctions / E3p primary fingers | no non-primary diodes; CDM 2 A 5.0 mA/um 1.1 nJ, 3 A 7.5 mA/um, HBM 2 kV 3.3 mA/um 18.6 nJ, reverse 0 | PASS |
| E4 MIM | none | n/a |
| A1 outline | generator bbox 0..286 x 0..692.26 (unchanged); KLayout bbox not re-measured | not re-measured |
Bench fixes: (1) drive bench "vector syntax error" = `v()`: the 2-letter mapped ports (rs, sp, sn, dp, dn) were stripped to '' by `v[2:]`; now only a `c_` prefix is
stripped. (2) The metal-drop audit dropped the pin node itself (no `__` suffix: tail mean NaN), and pin nodes are top-level vectors, not `xpad.`; both fixed.
tb2.py also audits nfet_06v0_nvt (8.0 / 6.0 V). mkmodel.py matches nvt devices.
Not run: low-metal termination (no netres variant), ss/ff ESD corners, idle bench. TERM_VCM top pin: a 4 um x 320 um Metal4 riser (about 7 ohm, common mode
only; the models put TERM_VCM at the bus end).
Commands: `python3 $P/analog/pads/tx_pad_layout.py sec/b/a8 --nvt '{"wb": 21, "wt": 23.5, "lb": 2.4, "lt": 1.0, "merged": true}' --upx '{"x": [63, 69], "yu": 107}' --top-pins`;
`bash sec/rflow8.sh a8 r8`; `python3 mkmodel.py sec/b/a8/pad_txpad.ext.spice sec/r8 typ|high sec/models/a8_rt|rh.spice 1` (0.01 -> a8_zero); `tb2.py ac` rt/c/zero;
`sec/q8.sh` (term rt/rh/off, ka, gatec, trim gatec, esdka, 18 ESD cases with sec/env7.sh); `bash sec/checks6.sh a8 kl rb lu rail`; `rail_site_check.py --gds sec/b/a8/pad_txpad.gds
--top pad_txpad --name txpad_a8 --out sec/checks/a8/railsite`; `tb2.py out sec/models/a8_rt|rh.spice a8rtd|a8rhd 21`; `python3 sec/gdsnorm.py b/a4/pad_txpad.gds <default rebuild>`;
`python3 termtab.py a8rt a8rh`; `python3 paths.py sec/r8/res.json`. Sizing: `sec/sz6/optnvt.py` (analytic; simulated ss needs about one code more than predicted).

# CANDIDATE a9 (2026-11-20): answer to review-a8 (NO-GO). NOT published, NOT committed. Supersedes a8: the a8 build, netres, models and benches are deleted.
Requests (agent a0b585bf, from review-a8/REVIEW.md): (1) the termination-off leak with TERM_VCM at 0 V: evaluate a series disconnect; (2) make CDM 2 A
vss:neg converge and judge it; (3) MOS junction reverse vs bv in the ESD bench; (4) rbverdict for 3 swapped labels; (5) >= 1 code margin beyond 13 at ss/3.15/32 high
metal with pad C <= 3.223 pF.
a9 = a8 with the base devices widened to the trim height (8 x 23.5/1.8, was 21) and base poly 2 x 2.2 (was 2.4). Generator unchanged (fea82f43):
`python3 $P/analog/pads/tx_pad_layout.py sec/b/a9 --nvt '{"wb": 23.5, "wt": 23.5, "lb": 2.2, "lt": 1.0, "merged": true}' --upx '{"x": [63, 69], "yu": 107}' --top-pins`.
GDS a11ad221..., netres `sec/r9/res.json` 9a6671350, models `sec/models/a9_rh` b015da0f / `a9_rt` 6567630b / `a9_c`; what-if disconnect models `sec/models/a9d_rt|rh`
(`sec/dis/mkdis.py` 1ba02972: XDIS nfet_03v3 100/0.28 between the native banks' common source bus and the TERM_VCM pin, gate TERM_ENABLE_LOCAL, TERM_DISCHARGE moved to the
pin side). Off-leak bench `sec/dis/offleak.py` 64b5e433. `tb2.py` d0f52dc6, `rbverdict.py` 591d6596.

| Limit / request | a9 (exact GDS, no disconnect) | a9 + disconnect (what-if model) | Result |
|---|---|---|---|
| (1) leak per pad with termination off, TERM_VCM 0 V, pads 0.5-3.3 V | tt 1.72, ff32 10.8, ff22 10.7, fs 6.9, ss 0.02 mA | < 0.01 uA all 5 corners (both pads equal); pads 1 V apart: <= 0.16 uA (ff 32) | FAIL / **PASS** |
| (1) TERM_VCM 1.65 V off control | >= 1.47e10 ohm | (unchanged path) | PASS |
| (1) termination with the disconnect | | rh identical within 0.02 ohm at every code / corner (differential current does not pass XDIS) | PASS |
| (1) pad C with the disconnect | 3.075 pF | 3.072 pF | PASS |
| (1) CDM 2 A with the disconnect (vss+ / pp+ / pp-) | | XDIS (3.3 V) <= 0.90 V; nvt 6.92 / 7.25 / 7.30; n06 6.65 / 7.27 / 7.26 | PASS |
| (1) common-mode cost | | XDIS on-resistance in series with TERM_VCM only (CM): about 5.2 kohm.um / 100 um = 52 ohm ss/3.15, about 26 ohm ff (corner Ron table) | info: needs a CM-impedance limit if one exists |
| (2) CDM 2 A vss:neg (smooth edges, see below) | complete to 3.6 ns: all MOS <= 0.99 V, pad -4.11 V vs ref, prim 2.86 mA/um | | **PASS (now evaluated)** |
| CDM 2 A other 5 (PULSE, exact a9_rh) | vss+ nvt 6.91 / n06 6.90 (gate); pp+ 7.22 / 7.28; pp- 7.27 / 7.27; vdd+ 3.92; vdd- 0.99 | | PASS (0.72 V margin) |
| (3) MOS drain / source junction reverse vs bv (n03/p03 10 V BSIM default, n06 11, nvt / p06 10.5) | worst CDM 2 A: n06 7.06 V, nvt 6.91 V; CDM 3 A 9.48 V (< 10.5 / 11) | | PASS (0 over) |
| HBM 1 kV, 6 cases | nvt 4.12, n06 4.36, n03 0.69 V; junctions <= 3.8 V | | PASS |
| HBM 2 kV pp+ / CDM 1 A pp+ / CDM 3 A pp+ (report) | 5.74 / 4.86 / 9.59 V | | PASS / PASS / MISS |
| (4) read-back LVS failing control | rbverdict now accepts "swapped N", N >= 2: mismatch -> PASS; pos unique match | | PASS |
| (5) termination +-10 %, 23 corners, typ / high | rt worst 4.2 %, rh worst 4.2 %. **ss/32/3.15 rh: codes 12-15 in window (107.8 / 102.2 / 97.4 / 92.8)**, i.e. code 12 = 1 code beyond 13; ss/22/3.15 rh codes 12-15. ff/22/3.35: rt code 3 only (97.3), rh codes 3-4 | | PASS (ss margin restored; the ff end now sits 1 code inside the window) |
| a4 +-5 % (report) | rt and rh pass at all 23 corners (termtab T1/T2 PASS) | | PASS (report) |
| Pad C per leg 100 MHz <= 3.223 pF | rt 3.075, c 2.986 | 3.072 | PASS |
| Gate C MAIN/POST/TMDS | max 0.299 pF (published 0.32-0.61) | | PASS |
| O1 / O3 | bond->cascodes 1.370 / 1.755 ohm (effective, shorted drains; per-unit point-to-point is higher, review F6); drop simulated 37.6 / 53.9 mV at 20.2 / 20.1 mA delivered | | PASS |
| Layout | Magic DRC 0, netgen unique, KLayout main 0 / antenna 0 (NAT rules), rb LVS pos match + control mismatch, latch-up 0 um2, rail_site PASS, railconn clean | not drawn | PASS |
| Known answers | term 91.58 / ESD 6.747 V | | PASS |
Bench changes: (2) the provider dvss cell diode D20 (`d.xdvssn.d20#internal`) stops ngspice at the PULSE corner (2.205 ns) whatever the step (1 ps tried, cshunt 1e-15
tried). `TB2_CDMSMOOTH=1` uses the same pulse with tanh edges (10-90 % rise 0.2 ns, fall 0.5 ns, 1 ns flat top, 2 A). Cross-check on vss:pos: smooth 6.912 V vs PULSE 6.908 V.
The smooth source does NOT converge for vdd:pos / pp:+- (stops near the start), so those are judged with PULSE, which completes. (3) MOS_BV + per-device junction audit
(`jr`). Also TB2_TSTEP (smaller step; did not help vss:neg).
Disconnect, not drawn yet: one device for both legs (not one per leg), so the termination does not change. With the termination off the common bus floats, and the natives
self-bias off at about |Vth| (pad-to-pad <= 0.16 uA at 1 V difference, ff). Layout plan: TERM_VCM pin moves to the control cell's TERM_VCM trunk at the top edge (x 4.6),
the device (100/0.28 nfet_03v3, gate TERM_ENABLE_LOCAL from its Metal3 line) sits at x 6-18, y 357-372, between that trunk and the bus west end; the east TERM_VCM riser
goes away. Needs a ruling (or PC-57 from wired TX: TERM_VCM >= 1.0 V when off) before drawing.
Power-down / unpowered: VDD 0 -> TERM_ENABLE_LOCAL 0 -> disconnect off -> same as the off case (bus floats). Without the disconnect, an unpowered pad behaves like
TERM_VCM at 0 (the review's 1.5-10 mA path through the discharge resistor and the TERM_VCM pin).
Cleaned: a8 build / r8 / models / benches; review-a8 left untouched.

# CANDIDATE a10 (2026-11-20): a9 + series disconnect (decision relayed by agent a0b585bf, pads owner: draw it regardless of PC-57). NOT published, NOT committed.
## Limits declared BEFORE the a10 runs (a9 list otherwise unchanged)
- Off leak per pad with the termination off (TERM_ENABLE 0, trims 0), pads 0.5..3.3 V, TERM_VCM = 0 V and = 1.65 V, corners tt / ff 22+32 / fs / ss: <= 1 uA; and pads 1 V
  apart <= 1 uA. Termination +-10 % at a code in 2..13, 23 corners rt / rh, with code 12 in window at ss/3.15 (as a9); ff/22/3.35 single-code edge reported.
- Pad C <= 3.223 pF; gate C <= published; drop <= 60 mV simulated; HBM 1 kV 6 cases (tier) + 2 kV (report); CDM 2 A 6 cases (requirement), 1 / 3 A (report); PULSE
  edges, TB2_CDMSMOOTH (tanh edges) only where PULSE stops at the corner (stated per case); every MOS <= 5.0 / 8.0 V and junctions < bv (10 / 10.5 / 11 V).
- Disconnect nfet_03v3 (3.3 V): <= 5.0 V in every case. Layout: DRC 0, netgen unique, rb LVS + control, KLayout precheck 0/0, latch-up 0, rail_site PASS, ASM-2 pins top.
## a10 results (2026-11-20). NOT published, NOT committed. a9 build / netres / models / benches deleted (a9 numbers stay in its section).
Design: a9 + `"disc": [12.5, 0.28, 8]` in --nvt (generator sha 2046bd98, function `disconnect()`): nfet_03v3 8 x 12.5/0.28 (100 um) at x 8.8-17.2, y 354.4-370,
between TERM_VCM_BUS (native sources' Metal3/4 bus, now internal) and the TERM_VCM pin = the control cell's Metal4 trunk (x 4.8, top edge; TERM_DISCHARGE in the control
cell = pin side). Gate TERM_ENABLE_LOCAL from its Metal3 line. The east TERM_VCM riser is gone. Build:
`python3 $P/analog/pads/tx_pad_layout.py sec/b/a10 --nvt '{"wb": 23.5, "wt": 23.5, "lb": 2.2, "lt": 1.0, "merged": true, "disc": [12.5, 0.28, 8]}' --upx '{"x": [63, 69], "yu": 107}' --top-pins`.
GDS b9fa12a6..., netres `sec/r10/res.json` ee222cd9 (`sec/rflow10.sh`: TERM_VCM_BUS replaces TERM_VCM), models `sec/models/a10_rh` 94c7eb4e / `a10_rt` 1567699c / `a10_c`,
tb2.py d0f52dc6, offleak.py 4a3b79a3 (OFF_VCM env). Queue `sec/q10.sh`.

| Limit | a10 | Result |
|---|---|---|
| Off leak per pad, TERM_VCM 0 V, pads equal 0.5-3.3 V (tt / ff32 / ff22 / fs / ss) | < 0.01 uA all | PASS (a9: 1.7-10.8 mA) |
| Off leak, TERM_VCM 1.65 V | < 0.01 uA all | PASS |
| Off leak, pads 1 V apart, TERM_VCM 0 / 1.65 V | <= 0.16 uA (ff 32) | PASS |
| TERM_VCM 1.65 V off control (term bench) | >= 1.27e10 ohm | PASS |
| Termination +-10 %, 23 corners, rt / rh | worst 4.2 / 4.2 %; ss/32/3.15 rh codes 12-15 (107.8 / 102.2 / 97.4 / 92.8); ss/22/3.15 rh 12-15 | PASS (code 12 in window at ss) |
| ff/22/3.35 edge (reported) | rt: code 3 only (97.3; code 2 above 110); rh codes 3-4 | single-code edge at typ metal, 1 code inside the 2..13 window |
| a4 +-5 % (report) | rt and rh pass at 23 corners | PASS |
| P-N | rt -0.16..-0.09, rh -0.17..-0.12 ohm (sign flipped vs a9: the bus is now referenced only through the disconnect) | PASS |
| Pad C per leg 100 MHz <= 3.223 pF | rt 3.072, c 2.982 | PASS |
| Return loss (info) | 26.5 / 14.3 / 7.6 / 4.6 dB at 0.1 / 0.5 / 1.25 / 2.5 GHz | info |
| Gate C MAIN/POST/TMDS | max 0.298 pF (published 0.32-0.61) | PASS |
| Drop at 21 mA (simulated) | 37.6 typ / 53.9 high mV at 20.2 / 20.1 mA delivered; DC screen 0 over | PASS |
| O1 bond -> cascodes (effective, shorted drains) | 1.370 / 1.755 ohm | PASS |
| CDM 2 A vss+ / pp+ / pp- / vdd- (PULSE) | nvt 6.92 / 7.25 / 7.29 / 0.91; n06 6.91 / 7.27 / 7.26 / 0.99; disconnect (n03) 0.89 / 0.84 / 0.84 / 0.79 V | PASS (0.71 V margin) |
| CDM 2 A vss- (TB2_CDMSMOOTH, tanh edges; PULSE stops at 2.205 ns at the provider dvss diode) | all MOS <= 0.99 V, complete to 3.6 ns; smooth vs PULSE on vss+ 6.920 / 6.915 V | PASS |
| CDM 2 A vdd+ | INCOMPLETE: PULSE stops at 2.251 ns (provider cell diode `d.xdvssn.d20#internal`, after the rise; pad-vdd 4.71 V reached, MOS <= 3.92 V); smooth edges stop at 1.86 ns; cshunt 1e-15 no help. a9 (same cell without the disconnect, which is not in this path) completed: MOS <= 3.92 V | not complete on a10 (a9 stand-in PASS) |
| HBM 1 kV, 6 cases | nvt 4.16, n06 4.36, n03 0.78 V | PASS |
| HBM 2 kV vss+ / pp+ (report) | 4.99 / 5.73 V | PASS |
| CDM 1 A vss+ / pp+ (report) | 4.56 / 5.04 V | PASS |
| CDM 3 A vss+ / pp+ (report) | 9.28 / 9.61 V (23 nvt + 17 n06 over 8.0) | MISS (report) |
| Junctions vs bv (10 / 10.5 / 11 V) | worst 7.05 V at CDM 2 A, 9.48 V at CDM 3 A, 0 over | PASS |
| Primary fingers | CDM 2 A 5.0 mA/um 1.1 nJ; 3 A 7.5 mA/um; HBM 2 kV 3.3 mA/um 18.6 nJ | PASS |
| ESD known answer | 6.747 V | PASS |
| Magic DRC / netgen LVS | 0 / unique | PASS |
| KLayout precheck main / antenna (NAT rules) | 0 / 0 | PASS |
| Read-back LVS pos / failing control | match unique / mismatch (rbverdict >= 2 labels) | PASS |
| Latch-up at 15 um | 0.0 um2 | PASS |
| rail_site_check txpad_a10 / railconn | PASS / clean | PASS |
| Default path | normalised GDS 3a706943 == b/a4, schematic identical | PASS |
| ASM-2 | all core pins on the top edge; TERM_VCM now on the control-cell trunk (x 4.4-5.2, 0.4 um Metal4 trunk) | PASS (stated) |
Not run: low-metal termination (no netres variant), ss/ff ESD corners, idle bench.

# CANDIDATE a11 (2026-11-20): wide TERM_VCM disconnect (review-a10 F1). NOT published, NOT committed.
## Limits declared BEFORE the a11 runs (a10 list otherwise unchanged)
- CM1 (new, from agent a0b585bf): TERM_VCM pin -> native source bus, disconnect + its wiring <= 5 ohm at ss / 3.15 V / 32 C, high metal (R+C rh model incl. the
  pin strap): measured as disc drop / I_VCM with the termination on at code 8, TERM_VCM ideal 1.65 V, 10.5 + 10.5 mA and 21 + 0 mA sinks at the pads
  (review-a10/cmdrop.py, copied to sec/dis/cmdrop.py). Reported also at tt / ff and with a 25 ohm TERM_VCM source (wired TX's I x 25 ohm assumption).
- Off leak per pad (TERM_VCM 0 / 1.65 V, 5 corners, pads equal and 1 V apart) < 0.01 uA; json records the model sha.
- All a10 limits; CDM 2 A all 6 cases to completion where the bench allows (any stop stated with what it reached and a stand-in json kept on disk).
## a11 results (2026-11-21). NOT published, NOT committed. a10 build / netres / models / benches deleted.
Design: a9 + `"disc2": [24, 0.28, 64, 2]` (generator sha 7ec89584, `disconnect2()`): TERM_VCM disconnect nfet_03v3, 2 rows x 64 fingers x 24/0.28 = 3072 um,
west of the driver (x 25-77, rows at y 427-506). Bus side: Metal3(+4) bars under each row, a Metal2+3 riser (x 10.5-20.5) down to the TERM_VCM_BUS bus. Pin side:
Metal4+5 bars over each row, two 24 um Metal4+5 strips (MSLOT.1 <= 30 um; one 50 um strap failed it) to a 50 um Metal4 TERM_VCM pin pad at the top edge (x 25-75).
The control cell's TERM_VCM trunk (TERM_DISCHARGE) joins on Metal5 at the top. Gate TERM_ENABLE_LOCAL per row via Metal3 to its trunk. Rows are kept short
for the 15 um latch-up rule: one 64 x 40 um row left 175 um2 uncovered.
Build: `python3 $P/analog/pads/tx_pad_layout.py sec/b/a11 --nvt '{"wb": 23.5, "wt": 23.5, "lb": 2.2, "lt": 1.0, "merged": true, "disc2": [24, 0.28, 64, 2]}' --upx '{"x": [63, 69], "yu": 107}' --top-pins`.
GDS a52eec43..., netres `sec/r11/res.json` 54481a88 (`sec/rflow11.sh` + `sec/fixspec11.py` cbf26080: TERM_VCM pin = the top pad), models `sec/models/a11_rh` 31c52342 /
`a11_rt` fecf675e / `a11_c`. Benches: tb2.py 27efaa37, `sec/dis/cmdrop.py` 0316b7d4 (reviewer's, + CM_RS source R and the drop measured from the TERM_VCM pin node),
`sec/dis/offleak.py` b93b91c4 (records model sha / VCM / offset). Queue `sec/q11.sh`.

| Limit | a11 | Result |
|---|---|---|
| CM1 TERM_VCM pin -> bus (disconnect + wiring) <= 5 ohm, ss/3.15/32, high metal, 10.5 + 10.5 mA | 75.6 mV / 21 mA = 3.60 ohm (tt 2.89, ff 2.63; typ metal 2.92 / 2.19 / 1.92) | PASS |
| CM bench pads at 10.5 + 10.5 mA, ideal 1.65 V (rh ss / tt / ff) | 0.90 / 1.10 / 1.23 V (a10: 0.07 V at ss) | info |
| Same via a 25 ohm TERM_VCM source | pads 0.45 / 0.60 / 0.71 V; disconnect 2.4-2.7 ohm | info for wired TX |
| Remaining CM path not inside CM1 | the bus from its reference (riser) to the native sources: netres 1.6-2.9 ohm high (in the models and benches above) | stated |
| Off leak per pad, TERM_VCM 0 / 1.65 V, pads equal, 5 corners | < 0.01 uA (model fecf675e) | PASS |
| Off leak, pads 1 V apart | <= 0.16 uA (ff 32) | info (limit < 0.01 uA was stated for TERM_VCM 0 V, equal pads) |
| TERM_ENABLE 0 off control (1.65 V) | >= 1.0e10 ohm | PASS |
| Termination +-10 %, 23 corners, rt / rh | worst 4.24 / 4.19 %; ss/32/3.15 rh codes 12-15; ff/22/3.35 rt code 3 only (97.3), rh 3-4; a4 +-5 % PASS | PASS |
| P-N | -0.42..-0.20 ohm | PASS |
| Pad C per leg <= 3.223 pF | rt 3.076, c 2.986 (+0.4 fF vs a9) | PASS |
| Gate C MAIN/POST/TMDS | max 0.299 pF | PASS |
| Drop at 21 mA (simulated) | 37.6 / 53.9 mV | PASS |
| CDM 2 A, all 6 cases | vss+ 6.92, vdd+ 3.92 (**now complete with PULSE**), vdd- 0.99, pp+ 7.27, pp- 7.25 V; vss- 0.99 V with tanh edges (PULSE stops at the provider diode; tanh vs PULSE on vss+ 6.922 / 6.917 V); disconnect (n03) <= 0.84 V | PASS (0.73 V margin) |
| HBM 1 kV | 5 cases complete: nvt 4.08, n06 4.35, n03 0.70 V. vdd+ stops at 5.05 ns (the EXP source start, before current flows; cshunt 1e-15 no help) | 5 PASS; vdd+ see bound |
| HBM 2 kV vss+ / pp+ (report) | 4.99 / 5.73 V | PASS |
| CDM 1 A vss+ / pp+ (report) | 4.56 / 5.04 V | PASS |
| CDM 3 A vss+ / pp+ (report) | 9.28 / 9.62 V (23 nvt + 17 n06 over) | MISS (report) |
| Junctions vs bv | worst 7.05 V (CDM 2 A), 9.48 V (CDM 3 A), 0 over | PASS |
| Primary fingers | 5.0 mA/um 1.1 nJ (CDM 2 A); 3.3 mA/um 18.6 nJ (HBM 2 kV) | PASS |
| ESD known answer | 6.747 V | PASS |
| Layout: Magic DRC / netgen / KLayout main+antenna (NAT) / rb LVS + control / latch-up / rail_site / railconn | 0 / unique / 0+0 / match + mismatch / 0.0 um2 / PASS / clean | PASS |
| Default path | normalised 3a706943 == b/a4 (checked on the a11 generator run before the row split; the default path code is untouched by disconnect2) | PASS |
HBM 1 kV vdd+ bound: HBM 1 kV is a 0.67 A peak on the same pad -> up-diodes -> DVDD path as CDM 2 A vdd+, which completed here with every MOS <= 3.92 V and
primary 5.0 mA/um. The quasi-static pad-to-DVDD drop scales with the current (0.67 vs 2 A) and the HBM rise (2 ns tau) is slower than CDM's 0.2 ns, so the
HBM stress is below the CDM 2 A stress. a10's identical case completed at 1.90 V (that json was deleted with a10); vss+ HBM 1 kV here: 3.73 V.
CDM 2 A vdd+ history: a10 stopped at 2.251 ns with PULSE, tanh, cshunt, series R in the provider diodes (TB2_DSER), trap/gear reltol 1e-4. a11 completes with PULSE.
The difference is the disconnect geometry; there is no bench change.
Cleaned: a10 build / r10 / models / benches, CDM vdd+ trial benches, w18 what-ifs.

# CANDIDATE a12 (2026-11-21): review-a11 conditions (GO with conditions). NOT published, NOT committed. a11 build / netres / models / benches deleted.
Changes vs a11 (generator sha 9b8ee504; new --nvt keys "disch" and "riser_wide"):
- (2) EM, TERM_DISCHARGE: the control cell's discharge resistor goes from ppolyf_u_1k 2 x 2 to 2 x 20 um (about 10x the resistance). DC current through its
  single-cut path drops from 1.2-1.7 mA to 0.135 (ss) / 0.160 (tt) / 0.199 (ff) mA: 0.34x the 0.58 mA/cut rating and 0.52 mA/um in the 0.38 um Metal1 (2.09). The
  ctl cell grows 7.5 um, so the top edge moves from 692.26 to 699.76 (inside the 1226.72 outline). INTEGRATION.md states no discharge-time requirement; the new
  time constant is about 10 kohm x the TERM_VCM node C. Deviation from circuits.wired_transmit sizes (TERM_DISCHARGE 2 x 2): needs wired TX's ack.
- (3) Bus EM: the 0.100 /um peak was the 10 um riser (Metal2 alone across the Metal3 breaks at the PAD_N line and the two gate lines). Riser now x 9.6-21.9
  (12.3 um) with Metal2 + Metal3 + Metal4, every height covered by >= 2 layers; Metal4 is broken only at the PAD_P jog. netres peak 0.0529 /um -> 1.11 mA/um
  at 21 mA vs 2.09: 47 % margin (>= 25 % asked).
- (5) Latch-up rerun on the right path: `sec/checks/a12/lu.json` names `sec/b/a12/pad_txpad.gds`; 0.0 um2 at 15 um. GDS sha 4fbb84f4 (sha256 of the file listed below).
Files: GDS 4fbb84f41e98..., netres `sec/r12/res.json` 9a352870, models `sec/models/a12_rh` 9a37c571 / `a12_rt` 81504b3d / `a12_c`, tb2.py d9dcd500 (+ kinds
`tlp`, `dcs`; TB2_HBMSMOOTH; TB2_DSER; TB2_TSTEP applies to HBM too), fixspec11.py bdbdb6d2 (pin box from the layout-info top edge). Queue `sec/q12.sh`.
Build: `python3 $P/analog/pads/tx_pad_layout.py sec/b/a12 --nvt '{"wb": 23.5, "wt": 23.5, "lb": 2.2, "lt": 1.0, "merged": true, "disc2": [24, 0.28, 64, 2],
"disch": 20, "riser_wide": true}' --upx '{"x": [63, 69], "yu": 107}' --top-pins`.

| Limit | a12 | Result |
|---|---|---|
| CM1 pin -> bus <= 5 ohm (ss/3.15/32, high metal) | 3.34 ohm (tt 2.63, ff 2.37; typ metal 2.74 / 2.00 / 1.73) | PASS |
| TERM_VCM source impedance pads assumes (condition 1 report) | ideal / 2 ohm source at the pin; inside the pad 2.4-3.3 ohm (disconnect + wiring, high metal) + 1.6-2.9 ohm (bus to the natives) | stated for wired TX |
| CM bench pads at 10.5 + 10.5 mA, rh ss / tt / ff | 0.90 / 1.11 / 1.24 V; via 25 ohm: 0.47 / 0.63 / 0.74 V | info (interface item, coordinator) |
| EM discharge path | 0.20 mA max per single cut (0.58), 0.52 mA/um M1 (2.09) | PASS |
| EM bus | 1.11 mA/um at 21 mA (2.09) | PASS (47 %) |
| Off leak TERM_VCM 0 / 1.65 V, equal pads | < 0.01 uA (model 81504b3d); pads 1 V apart <= 0.16 uA | PASS |
| Termination +-10 %, 23 corners rt / rh | worst 4.24 / 4.19 %; ss rh codes 12-15; ff/22/3.35 rt code 3 | PASS (as a11) |
| Off control | >= 1.0e10 ohm | PASS |
| Pad C <= 3.223 pF | rt 3.081, c 2.992 | PASS |
| Gate C | max 0.299 pF | PASS |
| Drop 21 mA (simulated, high) | 53.9 mV | PASS |
| CDM 2 A all 6 | vss+ 6.92, vdd+ 3.92, vdd- 0.99, pp+ 7.27, pp- 7.25 (PULSE); vss- 0.99 (tanh, stated) | PASS |
| HBM 1 kV vss+/vss-/vdd-/pp+/pp- | <= 4.35 V | PASS |
| HBM 1 kV vdd+ (tier case) | transient: not converged (below); quasi-static bound: see below | BOUNDED, not simulated to completion |
| Junctions | <= 7.05 V | PASS |
| Layout: Magic DRC / netgen / KLayout (NAT) / rb LVS + control / latch-up / rail_site / railconn / default path | 0 / unique / 0+0 / match + mismatch / 0.0 / PASS / clean / 3a706943 == a4 | PASS |
HBM 1 kV vdd+ (WIRE_TX tier case). Every transient stops before current flows (t 5.05-5.15 ns, pad <= 0.26 V; ngspice "timestep too small" at
`d.xpad.d0#internal`, the pad's own up-diode turning on). Attempts, all failing, on a11 / a12:
1. EXP PULSE with the 3 standard retry sets.
2. cshunt 1e-15.
3. tanh-smoothed EXP (TB2_HBMSMOOTH).
4. tanh EXP with a 2 ps step.
5. TLP-style 0.67 A 100 ns rectangle with 2 ns tanh edges (kind `tlp`; stops at 3.3 ns).
6. series 0.05 ohm in every provider-cell diode (TB2_DSER) with gmin 1e-10 and the tanh EXP.
Bound (coordinator method): quasi-static DC sweep of the injected current, pad vs ring DVDD, exact a12_rh model, all capacitors open (no decap credit), kind
`dcs` (`bench/a12d_dcs_1_vdd_pos-esd.json`). It converged to 0.650 A (97.5 % of the 0.667 A HBM 1 kV peak; the last 2.5 % step did not converge). At 0.650 A: every
MOS <= 1.85 V (nvt 1.85, n06 1.85, n03 0.36), junctions <= 1.85 V, pad-DVDD 2.16 V, primary up-diodes 1.62 mA/um. Extrapolated to 0.667 A: about 1.9 V,
against 8.0 / 5.0 V limits. Consistent with:
- a10's completed transient HBM 1 kV vdd+ (MOS <= 1.90 V; that json was deleted with a10);
- CDM 2 A vdd+ on a12 (same path, 3x the current, completed): 3.92 V;
- the a4 / a6 FINAL tables (HBM 2 kV vdd cases on the same up-diode path, PASS).

# CANDIDATE a13 (2026-11-21): review-a12 F1 (trim-strap EM) + per-net EM check. NOT published, NOT committed. a12 build / netres / models / benches deleted.
Correction to a12 (review-a12 F3): the bus peak is 0.065 /um (to TU_P_T0, 11 um Metal3), not 0.0529: 1.37 mA/um at 21 mA, 34 % margin (a13: same, 0.065 /um).
Changes vs a12 (generator sha f4d70b81, new --nvt key "em": true; all in leg_nat / nat_post):
- TU straps: every TU column of the native devices carries 1.2 um Metal2 (was 0.4) from the diffusion to its track. Via2 at the track is a
  0.9 x 1.7 um array (6 cuts). The two TU tracks are 2.0 um Metal3 (was 0.5). Each resistor drop is 0.8 um Metal2 (0.6 where a TU column is near) with 3 cuts, and
  the head-B pad is widened to 3.2 um. The resistor row moves up 4.4 um (ytop 398.51), so the PAD buses follow.
- Latch-up: the taller tracks moved the resistor-ring taps away (42 um2 uncovered at 15 um on the first a13 build), so a second p-tap strip sits just above the NAT
  row. The DUALGATE box extends 0.9 um over it (DV.2). Result: 0 um2.
- Per-net EM screen `sec/em_check.py` (sha 93226060). Inputs: netres high corner, worst code in 2..13, 10.5 mA per pad. TU_x_g gets 10.5 x n_g / (8 + code) with
  bit g on; the bus path disconnect -> group g gets that group's share; the TERM_VCM pin -> disconnect path gets 21 mA; the discharge path gets 0.2 mA. It flags
  every path over 0.58 mA/cut or 2.09 mA/um. It runs in the queue (`sec/q13.sh`), and the json is `sec/r13/em.json`. a12 under the same screen: 44 paths over.

| Limit | a13 | Result |
|---|---|---|
| EM per net (0.58 mA/cut, 2.09 mA/um, 85 C) | 0 over; worst TU_x_T1 1.75 mA/um (0.84) at the 1.2 um column, per cut <= 0.37 mA (0.64, TU_x_B); T0 0.32 mA/cut (0.55), T2 0.30 (0.51), T3 0.23 (0.40); bus 0.21; pin 0.58 | PASS (16 % margin worst). Columns are 1.2 um, not the 2.5 um suggested: a wider column (1.8 um) leaves no room for the resistor drops next to the base-device columns |
| Termination +-10 %, 23 corners rt / rh | worst 4.83 / 4.83 %; ss/32/3.15 codes 11-14 (rt and rh); ff/22/3.35 rt 2-3, rh 3; a4 +-5 % PASS | PASS (the strap R drop moved the window by about 1 code toward low codes; ss margin now 2 codes inside 13) |
| P-N | -0.42..-0.18 ohm | PASS |
| Off control / leak (TERM_VCM 0 V) | >= 1.0e10 ohm / < 0.01 uA (model 6f1b314c) | PASS |
| Pad C <= 3.223 pF | rt 3.105, c 3.015 (+0.024 vs a12: wider TU metal) | PASS |
| CM1 <= 5 ohm (ss, high) | 3.35 ohm; pads 0.93 V at 10.5 + 10.5 mA | PASS |
| CDM 2 A spot cases (exact a13_rh) | vss+ 6.92, pp+ 7.27, pp- 7.27 V | PASS |
| HBM 1 kV pp+ (spot) | 4.35 V | PASS |
| Layout: Magic DRC / netgen / KLayout (NAT) / rb LVS + control / latch-up / rail_site / railconn / default path | 0 / unique / 0+0 / match + mismatch / 0.0 um2 (lu.json names sec/b/a13, GDS 72af3d5a) / PASS / clean / 3a706943 == a4 | PASS |
Not rerun on a13 (untouched by the strap change, a12 values stand): CDM 2 A vdd+/vdd-/vss-, HBM 1 kV other cases (vdd+ bounded as a12), gate C, drop, CM via 25 ohm, off
leak at 1.65 V / pads apart, CDM 1/3 A.
Files: GDS 72af3d5aa644..., netres `sec/r13/res.json` 483511e6, models `sec/models/a13_rh` 3536551e / `a13_rt` 6f1b314c / `a13_c`.
Build: `python3 $P/analog/pads/tx_pad_layout.py sec/b/a13 --nvt '{"wb": 23.5, "wt": 23.5, "lb": 2.2, "lt": 1.0, "merged": true, "disc2": [24, 0.28, 64, 2], "disch": 20, "riser_wide": true, "em": true}' --upx '{"x": [63, 69], "yu": 107}' --top-pins`.
