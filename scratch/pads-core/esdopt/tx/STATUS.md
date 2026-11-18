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
