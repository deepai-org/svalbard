# Independent review: `pad_tlp_flat` Metal2-riser fix (2026-11-14)

Subject: `scratch/pads-core/tlp/pad_tlp_flat.gds` (sha256 `3238bcef…ca2f`) vs published `analog/pads/generated/tlp-site/pad_tlp_flat.gds` (`81be4cbc…c024`).
Scripts and logs: `review/chk.py`, `review/chk.log`, `review/short.py`, `review/short.log`, `review/rb/`, `review/rb_*.out`.

## Verdict: GO with conditions

The short is fixed and the cell can be placed over `5LM_METAL_RAIL` without touching any provider shape. Two things the
fix introduced need action: the VSS port sits on the half that is joined to the ESD-carrying half only through a weak link
(F1), and the 6 um riser is now co-limiting for failure current and is a large part of the measured on-resistance (F2).

## Findings

1. **F1 (condition, assembly + recommended cell change): the two VSS halves are joined only for LVS, not for current.**
   Metal2 alone: left bar (9-37 x 90-109.5, the four nd2ps anodes, 44 via1) and right bar (45-69 x 104.5-109.5, the pd2nw
   substrate rings, 20 via1) are separate polygons. They join through 4 via1 (x 36.2) -> Metal1 bridge 11.7 x 3.8 um ->
   8 via1 (x 46.2/46.9) -> a **0.7 um wide, 9.5 um long Metal2 neck** (x 45-45.7, y 95-104.5). [CALC] 4.5/4 + 2.6 sq x 0.09 +
   4.5/8 + 13.6 sq x 0.09 = about 3.1 ohm, and the neck has 1/8.6 of the riser cross-section.
   The only VSS label/port is at (60.2, 107.2), on the right half. The whole PAD->VSS (nd2ps) current is on the left half.
   A strap made only at the port would put the full negative-polarity TLP current through the neck and four vias.
   Condition: the assembly must strap **both** halves to ring DVSS directly (both lie under the DVSS Metal3 band, depth
   70-117; left bar 28 x 5 um plus 21 x 19.5 um is available for Via2). Better: move the VSS label to the left bar
   (or label both) and widen the right drop; the old cell had one continuous 5 um bar.
2. **F2 (condition on the measurement plan; recommended cell change): riser is co-limiting and dominates Ron.**
   PAD path: bond Metal2 plate (ends at depth 65.325) -> single Metal2 strip 6.0 um wide, 45.2 um to the PAD bar (110.5)
   -> PAD bar 61 x 11 um -> 8 x 11 via1. No vias in the riser (it is the bond plate's own Metal2; the bond stack has
   6464 Via2/Via3/Via4 each, 560 Via2 over the riser's x range). Narrowest width on the PAD path: 6.0 um, one layer.
   - Resistance [CALC]: 45.2/6 = 7.5 sq x 90 mohm/sq (Magic tech `gf180mcuD.tech` line 3342, `resist (allm2)/metal2 90`,
     nominal) = **0.68 ohm** (designer 0.8 counts from y = 55 inside the bond plate; old Metal3 riser 4.5 sq = 0.41 ohm).
     That is 40-60 % of the 1.2-1.7 ohm pad-to-rail value the site is meant to calibrate, on a nominal sheet value, and
     it rises with self-heating during the pulse, so a fixed subtraction is only good at low current.
   - Current capacity [CALC, estimate, no PDK pulse data]: Metal2 thickness 0.55 um (tech line 3281) -> 3.3 um2. The diode
     PAD fingers are Metal1 0.77 um wide x 0.55 um, 25 um long, with via1 only on the upper 11 um, so about half of each
     diode's current crosses one finger section: 8 x 0.77 = 6.2 um equivalent. Riser and diode fingers therefore reach
     the same current density at the same pad current (adiabatic Al estimate about 6e7 A/cm2 at 100 ns = about 2 A).
     In the old cell the riser (10 um Metal3) had 1.6x the finger section. So an It2 near or above about 2 A at 100 ns
     cannot be attributed to the diodes; the riser may open first. VF-TLP (1-5 ns, 3 A) is not affected.
   - Recommended: widen the riser. The ring has no Metal2, so below the diode rows (depth 66-89) it can be tens of um
     wide, and in the gap it can be about 13 um if the left VSS bar ends at x = 30. That gives about 0.25 ohm.
     If not changed: add to the README plan "Ron includes about 0.7 ohm riser (nominal, +-20 %, heats); 100 ns It2 is a
     lower bound limited by metal at about 2 A [estimate]".
3. **F3 (note, unchanged from old cell): VDD bar is boxed in.** VDD Metal2 (46.2-69 x 98.5-104.2) lies under ring DVSS;
   DVDD starts at depth 118. VSS bar and PAD bar close it off up to x = 69, so the assembly strap has to leave on Metal2
   through x 69-75 to depth >= 118. Its resistance enters the "VDD grounded" measurements. 24 via1 on VDD (6 per diode).
4. **F4 (bookkeeping): the generator's own LVS step did not run** (`lvs.txt.log`: docker image
   `sha256:9253a51f…` not present), so `tlp_site.py` did not finish and wrote no `lvs.txt`; the LVS evidence is the
   read-back run. `kl_block_drc_blocks.json` has **no TLP entry** and `inventory.py` has no TLP family, so the gate does
   not cover the cell.
5. Short fixed (confirmed). No other defect found.

## Checks and numbers

1. Rail geometry (own extraction from `packaging-assembly.gds`, `5LM_METAL_RAIL$2`, site `bidir[25].pad`, custom
   transform R90 = rail instance transform, so cell frame = rail frame, y = depth): Metal3/4/5 bands at x = 30: 70-117
   (DVSS), 118-125 (DVDD), 126-133, 134-197, ... Same as RAIL-CONTINUITY.md.
   - OLD: Metal3 overlap with the ring 504.4 um2, box 27-37 x 70-121.5; net extraction custom + ring: PAD = DVSS = DVDD
     on Metal3/4/5 (one cluster). Defect reproduced.
   - NEW: Metal3, Metal4, Metal5, Via2, Via3, Via4 overlap with the ring = 0.00 um2; nothing of those layers beyond
     depth 65.325. PAD, VSS, VDD, DVSS, DVDD are five separate nets. Control (synthetic Metal3 bar depth 110-121.5 added
     to NEW): DVSS = DVDD reported.
   - Bond stack: Metal2-Metal5 end at depth 65.325, pad opening 7.5-67.5 x 2-62, old = new; 4.675 um to the first band.
2. Provider shapes in the site window (whole ring, rail cell swapped in as `kl_assemble.py` does): no Metal2, Via1, Via2,
   Nwell, Nplus. Metal1 / COMP / Contact only as one strip at depth 65.49-66.44 (between bond and diodes); Pplus that
   strip plus 0.125 um slivers at the site edges. Custom Metal1 starts at 90.6, COMP at 95.9, cell x 3.5-71.5 inside
   the 0-75 site. Same-layer overlap 0 on every layer, no same-layer separation below 2.5 um. The riser crosses the
   provider Metal1/COMP strip on Metal2 only. Can be assembled.
3. Connectivity (metal + via only, no substrate): VSS label = left bar = left foot = bridge = right foot = right bar;
   riser = bond (Metal2 and Metal5) = PAD bar = PAD label; VDD separate. Left L-bar holds the 44 nd-anode via1.
   Via1: 188 (old 176): PAD 88, VSS left 44, VSS right 20, VDD 24, bridge 4 + 8. Metal2 spacings found: 0.3, 0.5,
   0.96, 1.0 um (rule 0.28, 0.3 to wide metal); riser to left bar 1.5, to right drop 0.5, PAD bar to VSS 1.0.
   Metal2 width minimum 0.7 um (the neck in F1; 0.4 only at via pads merged into bars).
4. Read-back LVS rerun (`review/rb/`): match, 8/8 devices, unique, extracted netlist identical to the designer's.
   Negative controls all rejected: all diodes' VDD/VSS swapped (pin matching failed), one pd2nw to VSS (pin matching
   failed), one nd2ps removed (census 7 vs 8 + property error). Precheck record `kl/pad_tlp/kldrc.json` gds_sha256 =
   sha256 of the GDS (`3238bcef…ca2f`), main 0 / antenna 0. Precheck not rerun by me.
5. Bbox unchanged (3.5, 0)-(71.5, 124.34). Labels unchanged: PAD (50.2, 118.2), VSS (60.2, 107.2), VDD (60.2, 101.2)
   on 36/10. README plan (PD48 "TLP site") still valid in method; needs the F1 and F2 statements.

## To publish (after F1 is at least recorded for assembly)

Copy to `analog/pads/generated/tlp-site/`:
- `pad_tlp_flat.gds`, `pad_tlp_flat.spice`, `reference.spice` (from `scratch/pads-core/tlp/`)
- `rb/pad_tlp/lvs.txt` as `lvs.txt`
- `kl/pad_tlp/kldrc.json` as `pad_tlp-kldrc.json` (existing file name). Its `gds` field points at scratch; cleaner is
  `kl_block_drc.py --name pad_tlp --gds <published gds> --top pad_tlp_flat --publish` after the copy.
Gate: `check_block_kldrc.py` looks for `<gds dir>/<registry name>-kldrc.json` and compares only sha256 and `clean`.
There is no TLP entry; add `"pad_tlp": {gds: …/tlp-site/pad_tlp_flat.gds, top: pad_tlp_flat, owner: pads}` so the
existing record name matches.
