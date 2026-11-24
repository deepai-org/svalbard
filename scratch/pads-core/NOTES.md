# Pads + core-support owner: resume file (current state, 2026-11-24)

`$P` = projects/programmable_transceiver_platform. Work dir scratch/pads-core/. Load rule: <= 3 heavy jobs incl. sub-agents,
OMP_NUM_THREADS=1. Delete intermediates once a result is published or abandoned (git is the archive).
Read first: scratch/reviews/MANDATE.md (1, 4a, 8), rows PC-72..79 in scratch/reviews/interface-changes.md.

## Decisions in force
- ESD option A (PC-27): primary diodes inside the pad site, tied to the ring rails; back-feed sequenced by the board (B53).
  RF_TX has no up-diode. Centre tap / any DC on WIRE_TX <= VDD + 0.45 V (PC-68, B54).
- A pad family is checked on the provider rail cell: `$P/analog/pads/rail_site_check.py`.
- The site after `pad_hspad` must hold a provider cell (PC-78).

## State per family (all published on option-A cells, PC-77)
| Family | Published | Open |
|---|---|---|
| `pad_txpad` | a16 bd54a8fd (PC-73) | full-chain 100BASE-TX anchor after wired TX's pump exists; CDM/HBM vdd+ bounded only; 9 fF pad-C margin |
| `pad_wirepad` (USB) | b7 303a9772 (PC-76) | review conditions C1-C4, HS level uncalibrated, CDM margin 0.34 V |
| `pad_hspad` | a6 ddcaaf79 | SATA2 return loss (PC-47) |
| `pad_refpad` | a1 b5533ab3 | CDM 2 A high metal 8.73 V |
| `pad_rf_pair` / `pad_single_leg` / `pad_rftxpad` | r3 / s2 818c2c3c, rftxpad t8 cc895025 | pad C bench, single_leg ESD runs, independent review, rftxpad up path (pair-shared RC clamp), rebuild drift 17.4 um2/site |

Rail-site check 2026-11-24, all eight families: PASS (main 0, antenna 0), `railcheck/out/` (PC-79).
pad_wire_tx `DNV*/DPV*.SUB` nets joining VSS in chip LVS are the diode legs' substrate taps: intended.

pad_txpad a16p (2026-11-24, PC-80): core pins widened/spread by `$P/analog/pads/tx_top_pins.py` (GDS sha bded3185).

## Next (2026-11-24 night)
Rule: every pad publish runs block_drc.py --cfg L --checks magic (shuttle Magic script); all eight families are at 0 (PC-86).
1. Assembly's precheck when it posts (pt_rf, pt_wired); re-abstraction of rftxpad t8, txpad a16p, rf_pair r4, wirepad b7v, hspad a6m.
2. RF answers: RF TX match with +0.40 pF/leg (PC-81b); RF RX LNA rerun with rf_pair 0.80 pF/leg (PC-84a).
3. SATA2 return loss: skipped (coordinator).
