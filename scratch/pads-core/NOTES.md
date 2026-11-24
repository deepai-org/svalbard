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
| `pad_rf_pair` / `pad_single_leg` / `pad_rftxpad` | r3 / s2 818c2c3c, rftxpad t7 c7a5a564 | pad C bench, single_leg ESD runs, independent review, rftxpad up path (pair-shared RC clamp), rebuild drift 17.4 um2/site |

Rail-site check 2026-11-24, all eight families: PASS (main 0, antenna 0), `railcheck/out/` (PC-79).
pad_wire_tx `DNV*/DPV*.SUB` nets joining VSS in chip LVS are the diode legs' substrate taps: intended.

pad_txpad a16p (2026-11-24, PC-80): core pins widened/spread by `$P/analog/pads/tx_top_pins.py` (GDS sha bded3185).

## Next (ranked, coordinator 2026-11-24)
1. rftxpad t7 published (PC-81, `$P/analog/pads/rftx_band.py`): HBM 1 kV / CDM 1 A pass; open: CDM 2 A (12.5 V) and pad C
   +0.38 pF (limit +0.3) -> answers from RF TX / coordinator; t3 variant (strip) closes CDM 2 A at +0.44 pF more.
2. rf-shell evidence: pad C bench, single_leg ESD (two-pad model), independent review.
3. Act on assembly's next pt_rf precheck.
4. USB b7 conditions C1-C4. SATA2 return loss: skipped for now (coordinator).
