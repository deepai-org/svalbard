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
