# Pads + core-support owner: resume file (current state, 2026-11-19)

`$P` = projects/programmable_transceiver_platform. Work dir scratch/pads-core/. Load rule: <= 3 heavy jobs incl. sub-agents,
OMP_NUM_THREADS=1. Disk is tight: delete intermediates once a result is published or abandoned (git history is the archive).
Read first: scratch/reviews/MANDATE.md, SPLIT-PLAN.md, scratch/reviews/pads-core/ESD-METAL.md, LNA-GROUND.md, rows PC-27..36.

## Decisions in force
- ESD option A (PC-27): primary diodes inside the pad site, tied straight to the ring rails, all seven custom families; back-feed accepted,
  board sequences it (`$P/spec/board-requirements.md` B53). RF_TX gets no up-diode (swings above the supply).
- Pad evidence: R+C extraction including the return side; pad on the provider rail cell passes `$P/analog/pads/rail_site_check.py`.
- Targets: wired TX row WT39 for `pad_txpad`; RF pads +0.1 pF wanted / +0.3 pF limit (PC-30); wired RX: pad C not above published.

## State per family
| Family | State | Where |
|---|---|---|
| `pad_hspad` | option-A candidate a4 complete, independent review NO-GO; rulings asked (PC-36). Published cell unchanged (f6). | esdopt/hs/STATUS.md (last section), review-a4/ |
| `pad_txpad` | option-A candidate a4 (trimmed termination, output-path fix, 0.6x MAIN option off): evidence run by a sub-agent | esdopt/tx/STATUS.md |
| USB `pad_wirepad`, `pad_refpad`, `pad_rf_pair`, `pad_rftxpad`, `pad_single_leg` | not started under option A | site cell: esdopt/site/READY.md |
| all published families but `pad_tlp` | fail the precheck on the provider rail cell (66 Via3/Via4 items per site, shell VSS ring stacks); option-A rebuilds delete them | railcheck/out/*/site.json, PC-32 |

## Done this round (2026-11-19)
- `rail_site_check.py` with self-test (PC-32). Per-chip site resolution in `design.py` (D-SPLIT-PADGEN, PC-34).
- pt_wired AUX_CLK pair to east bidir[16]/[17], POR_BYPASS + one ground west (PC-33). D-SPLIT-SUPSITE answered locally, tester question
  15 in wafer-space-answers.md (PC-35). Back-feed rule B53.

## Next
1. After the PC-36 rulings: either publish hspad a4 (if (a)-(d) are accepted) or add local secondary protection at the termination switches.
2. `pad_txpad` a4: independent review (fresh agent, artefacts only), publish on GO, rows to wired TX / chip top (new DVDD port, trim pins).
3. Remaining five families with `pad_site_primary.py`; RF_TX: down-diodes in the site + a pair-shared RC clamp (PC-31 alternative).
4. After each publish: `lvs_reference.py`, delete the candidate builds and the superseded scratch (hsfix/, hsfix2/, hspad/ once hspad is republished).
5. Older open items: `$P/analog/pads/README.md` section 8.
