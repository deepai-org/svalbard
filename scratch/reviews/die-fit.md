# Die-fit study (2026-11-14)

Question: can everything the chip now needs be placed, powered and routed on the fixed 3.932 x 5.122 mm die?
Paper/script study. No circuit simulation, no design file changed. Work dir: `scratch/reviews/die-fit/`.

STATUS: IN PROGRESS (written incrementally; sections below are filled as they are finished).

## 1. Demand ledger

Files: `die-fit/ledger.py` (generator), `ledger.csv` (one row per instance of `pt_chip.conn` at commit 4790054, plus the
booked items), `ledger.md` (per master, with source and confidence for every number).

Scenario definitions:
- **A** = published outlines only (never-built items at their estimate, R8-ARCH second capture on the published r6 master).
- **B** = everything that is staged publishes as measured (staged GDS bounding boxes, measured in `m45free_staged.json`).
- **C** = every assigned repack target of area pass 4 is met (or the staged size where that is already smaller);
  the digital macro stays 2.814 mm2 in all three (AP4-8's 2.45 mm2 is not reachable and the macro must absorb more).

(Totals and findings: see the final version of this section below once the reviewer pass is in.)
