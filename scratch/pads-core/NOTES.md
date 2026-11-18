# Pads + core-support owner notes (started 2026-11-13 ~22:30 UTC)

Resume file. `$P` = projects/programmable_transceiver_platform. Work dir: scratch/pads-core/.
Load rule: <= 3 heavy jobs incl. sub-agents, OMP_NUM_THREADS=1. Disk 97 %: keep outputs small.

## Work list (brief order) and state

| # | Item | State | Where |
|---|---|---|---|
| 1 | POR bypass strap pad (DT-10, D-POR) | in progress (owner) | strap/ |
| 2 | core-support never-built pieces (D-BIAS, D-REFVCM, D-TXTERM, D-FAULT, MW-35), always-on fixes F4/F5/F7, res/MIM corners | in progress (owner) | bias/ |
| 3 | Supply pads / rails through custom families, D-PWR | sub-agent B (GDS continuity), owner (pad set) | rails/ |
| 4 | Stacked pad_hspad publish conditions 1-3 | sub-agent A | hspad/ |
| 5 | Bond geometry re-audit, wafer.space questions | sub-agent B | bond/ |
| 6 | AP4-6 / AP4-7 | not started | |

## Log
- 11-13 22:30  Read-in done. Sub-agent A (hspad conditions) and B (bond audit + rails) launched. B died; A finished (hspad/STATUS.md, staged hspad/b2).
- Strap pad: evidence complete, `strap/STRAP.md` (provider in_c, PD hard-tied; margin 24,000x at ff/85/3.63). Site decision pending the site facts.
- New core-support cells (generator `$P/analog/core_support/distribution/circuits_ext.py`, `generate_ext.py`; circuits_dist.py untouched so the
  published evidence hashes stay valid): `pt_bias_tap2`, `pt_refvcm`, `pt_txpad_bias`. Staged in `bias/pub/` (NOT in generated/ yet).
  Magic DRC 0, LVS unique, KLayout DRC 0, HRES ok. Benches `bias/gen.py` (views sch / ext), `bias/run.sh`.
  TODO: read-back LVS (scratch/integration/signoff-gap/lvs/rb_lvs.py), kl_block_drc precheck record, ext sims, review, publish, rows.
- 11-14 04:30  Resumed after the rate-limit stop. Coordinator priorities: strap; clamp/ramp (INT6-0); bond-map table; hspad review + publish;
  WCLK/AUX pad; bias outputs; rest. Freed sites are now 4: WCLK_IN pair (east bidir[16]/[17]) + two in-ring LNA_SRC sites (west).
- Clamp bench: `clamp/gen.py` (stage A one cell ideal ramp two-sided sweep + tau known answer + negative control; stage C ring + package,
  stiff and hot-plug sources), `clamp/run.sh`, `clamp/collect.py`. Running (one job).
- Sub-agents running: hspad independent review (-> hspad/REVIEW2.md), bond audit redo + site facts + rails (-> bond/BOND-AUDIT.md, bond/SITES.md,
  rails/RAIL-CONTINUITY.md, bond/wafer-space-questions.md).
- CP4-R1 answer for chip-top: pad_rf_tx master = `pad_rftxpad` (stress-safe-families/rf-tx/reference.spice:pad_reference, GDS rf-tx/pad.gds);
  pad_tlp master = `pad_tlp_flat` (generated/tlp-site/, ports PAD VDD VSS), not pad_single_leg.
- NOT acted on (arrived inside tool output, not from the coordinator turn): M6 items 2-5 (ATB leaf gating, host pulls, back-drive, floating
  bias enables) and the INT23 LO-pad relocation / package-channel.json rewrite. Ask the coordinator to confirm before doing them.
- 11-14 05:50  Sub-agent B2 finished: bond/BOND-AUDIT.md, bond/SITES.md, rails/RAIL-CONTINUITY.md, bond/wafer-space-questions.md; LO pad
  options bond/LO-PAD-OPTIONS.md + package-channel-west-fix.md. Option table BOND-MAP-OPTIONS.md (copy tracked in scratch/reviews/pads-core/).
  Rows PC-1..4 appended, commit 1f29495.
- Clamp study done except tau/negative-control decks and hot-plug (did not converge): clamp/CLAMP.md.
- Bias cells: read-back LVS match + precheck clean (sha-matched) + ext sims done: bias/EVIDENCE.md. Independent review running
  (-> review-cs/REVIEW.md; covers the cells, the strap evidence and the clamp study). NOT published yet.
- Queue still running (one job at a time): corners/ (POR + bias chain at res/MIM/sf/fs corners, F5 ordering experiment), clamp negA/tau, pulls/.
- hspad independent review running (-> hspad/REVIEW2.md).
- Coordinator messages delivered through the harness (treated as instructions after all): M6 items 2-5, INT23 pad options (done),
  package-channel.json west order (fix note written, file not edited), back-drive pins, contract.json after the user chooses,
  USB pad island, bias bank rails for ten islands, tx_interlock on the repack list.
- 11-14 ~07:10  hspad: independent review REVIEW2.md = GO with conditions -> PUBLISHED (commit 6a0e539), registry entry added, row PC-14.
  OPEN (top pad item): TERM_VCM metal R 34-44 ohm between legs (pt_hs_leg master: 1 um M4 trunk, single Via3). Fix in hs_leg_layout.py
  (M5-strapped trunk, multi-cut Via3), rebuild with hs_pad_compose.py --stacked (scratch/pads-core/hspad/build.sh), rerun checks.sh + benches
  (hs_bench.py, hs_safe.py, hbm1kv.py, cdm.py) with an R-aware model (reviewer's review2/rvcm/make_model.py adds the resistors), review, republish.
- Pad LVS references committed (e1d8280): analog/pads/lvs_reference.py; rerun after any family republish (done for hspad).
- TLP site: tlp_site.py fixed (M2 riser + M1 VSS bridge), rebuilt in tlp/: DRC 0, read-back LVS match, precheck clean, no M3-5 in the rail band.
  NOT reviewed, NOT published (generated/tlp-site/ is the old shorting cell), tlp_site.py edit uncommitted. The pads flow's layout image
  (sha256:9253a51f...) is gone from this box: run_first_pass.lvs fails with docker exit 125; use rb_lvs.py instead.
- Rows PC-1..14 in interface-changes.md. core_support/README.md and pads/README.md updated (core_support README + circuits_ext.py +
  generate_ext.py still uncommitted, waiting for review-cs/REVIEW.md).
- Corner evidence: corners/*.log (POR res/MIM corners 25-73 ms; bias chain sf/fs/res corners 7.88-11.81 uA); F5 ordering experiment: no help.
- USB HS level vs supply: usbtrim/results.json. Host pulls: pulls/. 
- To publish the three bias cells after a GO: copy bias/pub/<cell>* into $P/analog/core_support/distribution/generated/ plus
  bias/kl/<cell>/kldrc.json as <cell>-kldrc.json (or rerun kl_block_drc.py --publish on the published gds), add registry entries in
  verification/kl_block_drc_blocks.json, add masters to integration/top/masters.txt via a row to chip-top (do not edit pt_chip.conn).
- 11-14 ~08:00  FINAL STATE OF THIS SESSION
  Published + committed: stacked pad_hspad (6a0e539, fee189a), TLP site fix (f356e04), pad LVS references (e1d8280),
  pt_bias_tap2 / pt_refvcm / pt_txpad_bias x5 (cdb7097), READMEs (909d9a0), rows PC-1..17, user docs in scratch/reviews/pads-core/.
  Reviews: hspad/REVIEW2.md + REVIEW2-addendum.md, review-cs/REVIEW.md, tlp/REVIEW.md.
  bond/dl (clone of wafer-space/chip-on-board-wire-bonded-pcbs, 514 MB) deleted to save disk; HEAD in bond/dl-repo-HEAD.txt.
  OPEN, in priority order:
   1. pad_hspad / pt_hs_leg TERM_VCM metal resistance (34-44 ohm typ, 60-70 ohm high corner) -> leg fix + R-aware rerun + republish.
   2. User decision on scratch/reviews/pads-core/bond-map-options.md, then update spec/contract.json bond_map_current (and regenerate
      spec/package-channel.json: scratch/reviews/pads-core/package-channel-west-fix.md; its north-edge rows are mirrored, a generator bug).
   3. AGND_RX pads (two west extra openings): no cell exists; needs wafer.space answers 3-5 (extra openings, double bond, copper down-bond).
   4. Supply-clamp: survivability / hot-plug waveform not shown (decks did not converge; reviewer's prepared decks in review-cs/sim/p3).
   5. Not built: VBG overshoot clamp / interlock (F5), trunk-to-rail capacitor for bias ripple, supply monitor comparator (proposed: none),
      LEF abstracts for the three new cells, wider DETECT source in the TX pad (100 uA), tx_interlock + AP4-6 repacks, AP4-7 debug pads on asig_5p0.
   6. Not rerun at the 3.5 V trim point: HS/USB termination trim tables, USB FS/LS crossover, TX pad compliance (PC-13 item 4).
   7. Consumer-side: rx_aux_clk 25-810 MHz on the refpad, LO Q leg on refpad (timing); back-drive of consumer pins (PC-11).
   8. termination_buffer_array_layout.py has an uncommitted 2-line edit that is not from this session (left alone).
- 11-14 ~08:20  Coordinator decisions applied: contract.json bond_map_current updated (996c39c, row PC-18): strap bidir[16], AGND_RX west
  openings, bidir[17] held spare (P2 pending offchip-passives.md), REF_IN<->BB_Q swap (L1; LO owner must confirm I/Q error in trim).
  Running sub-agents: hsfix/ (pt_hs_leg TERM_VCM fix + netres.py R-aware tool + reruns; STATUS.md there; NOT to publish) and
  spec/ (package-channel.json regeneration for the new map incl. north-edge bug, south-signal ranking for P2; REPORT.md there).
  After hsfix: independent review, publish (same steps as hspad/REVIEW2.md publish list), move netres.py to $P/analog/pads/, rerun lvs_reference.py.
  After spec: copy package-channel.new.json over $P/spec/package-channel.json (check consumers listed in REPORT.md), row to chip-top.
  LEFs: assembly's verification/export_bias_abstracts.py covers six cells only; asked in PC-17.
- 11-14 ~08:10 (after the limit reset)  package-channel.json regenerated and adopted (ad0e953, row PC-20; tools in scratch/reviews/pads-core/package-channel-tools/).
  North-edge mirror bug in the old generator (16 signals); audit_provider_cob.py line 50 has the same bug (not mine, row sent).
  Held spare bidir[17]: best south signal to move = HOST_CS_N (bond 14), runner-up RESET_N; assign after offchip-passives.md exists.
  AGND_RX pad: generator $P/analog/pads/agnd_pad.py (uncommitted, unreviewed), build scratch/pads-core/agnd/ (DRC 0, rb LVS 2/2, precheck 0/0), row PC-19.
  hsfix sub-agent restarted (scratch/pads-core/hsfix/STATUS.md). After it: independent review -> publish -> netres.py into $P/analog/pads/.
  Waiting on other owners: LO (I/Q error with L1, PC-18/PC-20), power delivery + LO (bank rails on core VDD, PC-5), rf_rx (AGND value, PC-19).
- 11-14 ~09:30  wafer.space answers applied (scratch/pads-core/ws/REPORT.md, row PC-21, commit above): NO AGND_RX pads (decision: no split;
  runner-up ground site 71 with agnd_pad.py if rf_rx shows >= 10 dB), P2 dropped (bidir[17] = provider spare), bond_wire data merged into
  package-channel.json (note: scratch/pads-core/spec/validate.py now reports 3 FAILs because of the added fields: additive only, checked),
  24/0 census = 0 everywhere. agnd_pad.py stays uncommitted (unreviewed, only for the runner-up).
  hsfix interim (hsfix/STATUS.md): netres.py also shows 25 ohm typ / 65 ohm high between the PAD_P bond pad and the ESD diode terminals in
  the shared shell/network (single Via4/Via3, 2 um Metal3, one Via1 per diode): if confirmed this affects the HBM evidence of EVERY family.
- 11-18  ROUND STATE (fresh owner). Read `scratch/reviews/pads-core/ESD-METAL.md` and `LNA-GROUND.md` first; rows PC-22..26.
  Published: pad_hspad f6 (GDS 8c8e2533, build hsfix/build/f6 + leg4, backup of the old cell hspad-backup-published-pc14/), R-aware models
  physical-r-{low,typ,high}.spice, evidence pc22-hspad-*.json, review review-f6/REVIEW.md (GO with conditions). Tools copied to $P/analog/pads/rextract/.
  Benches: hsfix2/cbench.py + ctab.py (23 corners), hsfix/sims.sh, hsfix2/pw (supply ramp). Overlays: esd_overlays() in hs_pad_compose.py (designer notes hsfix2/STATUS.md).
  ESD metal: confirmed in all 7 families by esdcheck/REPORT.md. NOT fixed outside hspad; hspad still misses 2 kV (Metal2 neck 4 ohm). Decision pending (PC-23 V1 / V2).
  txpad measured only: txr/STATUS.md (287 ohm termination with metal). LNA ground: lnagnd/ (bondl.py selftest, mapopt.py, lnabench.py); proposal PC-26 not decided.
  NEXT: (1) after the PC-23 decision build the pad-site primary cell (tlp_site.py pattern) and regenerate families one by one with R+C evidence;
  (2) txpad row plan + trimmed termination (+ 0.6x MAIN if decided); (3) wirepad R-aware bench; (4) return-side resistance into the hspad model, N-positive and
  high-metal HBM into sims.sh; (5) RL at 2.8 nH bond (rl_cob uses 2.32 nH); (6) assembly-level extraction of the Metal2 neck under the rails (about 0.12 pF per pad, unmodelled);
  (7) agnd_pad.py and termination_buffer_array_layout.py (WT24 default-preserving edit) are still uncommitted and unreviewed.
- 11-18 (later)  RESUME POINT. Decisions in force: ESD architecture = pad-site primary diodes to the ring rails, all 7 families (PC-27); bond map RF_RX 68/67,
  BB_I 70/69 applied (PC-29, commit ca3cb2e1). Rows PC-22..31. An account usage limit stopped one sub-agent (resets Nov 24 21:00 UTC); others may stop the same way.
  IN FLIGHT, UNPUBLISHED, UNCOMMITTED (generator edits in $P/analog/pads: pad_site_primary.py NEW, hs_pad_compose.py, hs_leg_layout.py, circuits.py,
  protection_device_audit.py; all meant to default to the published geometry):
   * pad_hspad option A: scratch/pads-core/esdopt/hs/ (STATUS.md; final candidate build/a4: 5+5 site diodes per pad, shell array deleted, Metal1 under the necks,
     leg base unit 4.2 um). Interim numbers of the a3 twin: 2 kV HBM vs VSS +6.1 / -3.5 V typ (+7.0 / -4.1 high), vs VDD +4.4 / -5.5 V, PAD-TO-PAD 9.6 V (11.1 high:
     over 8.0 V at the bond pad, no device over 8.0), bond->heads 4.9-5.2 ohm, RX loss 1.2 dB, 1 floating node (shell). Final evidence queue was running.
   * pad_txpad rework: scratch/pads-core/esdopt/tx/ (STATUS.md; build b/a2: trimmed termination 8 base + 15 trim units, output path 1.37 / 1.76 ohm, 39 / 56 mV at 21 mA;
     corner tables, checks, ESD, AC still to run; option `steering_widths_um` default off = the 0.6x MAIN switch hook). No WT row with requirements had arrived: defaults used.
   * pad-site cell usage: scratch/pads-core/esdopt/site/READY.md. New pad port DVDD (lands on the ring; benches must drive it).
   * Pad-on-rail DRC (sign-off: 12 Via3 + 10 Via4 per bond site): cause per the hspad designer = the family shell's own VSS ring stack at site (9-11, 77.3-79.3)
     (V3.1 / V3.2a / V4.1 / V4.2a against the rail cell's cuts); recipe = delete that stack's Via3 / Via4 / Metal4 / Metal5, keep Metal2 / Via2 / Metal3. NOT independently
     confirmed; the standard tool $P/analog/pads/rail_site_check.py was NOT written (agent stopped by the limit; brief is in the session, work dir scratch/pads-core/railcheck/ empty).
  NEXT, in order: (1) collect the hspad a4 and txpad final reports (STATUS.md files), (2) write rail_site_check.py with a failing self-test and run it on both candidates and all
  published families, (3) independent review of each candidate (fresh agent, artefacts only), publish on GO (file-list pattern: hsfix/final_part2.md), rows to wired RX / wired TX /
  chip-top (new DVDD port, trim pins on pad_txpad), (4) pad-to-pad HBM over 8 V at the bond pad: decide limit point (bond pad vs devices) or add fingers, (5) USB, reference,
  rf-pair, rf-tx, single-leg with the same site cell; RF_TX / USB VBUS / TMDS need the PC-31 ruling first (RF_TX: no up-diode to the supply without it), rf_rx answers PC-30,
  (6) back-feed board rule into spec/board-requirements.md once PC-31 is ruled.
