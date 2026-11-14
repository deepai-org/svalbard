# REVIEW2 addendum: second independent check of the stacked `pad_hspad`

2026-11-14, first-assigned reviewer (not the designer, not the author of `REVIEW2.md`).

Status of this document. My session stalled for about two hours after my first LVS rerun (04:33 UTC). When it resumed (06:45),
another reviewer had written `REVIEW2.md` (06:38) and the owner had published the cell and committed it (6a0e539, 06:42).
I did not overwrite `REVIEW2.md` (the committed README and `SUPERSEDED.md` cite it). This file records what I reran
independently, where I confirm `REVIEW2.md`, and what I add. Reruns: `review2/lvs`, `review2/negrx`, `review2/negpad`,
`review2/negref`, `review2/kldrc/pad_hspad_review2`, `review2/r1`, `review2/bench/r1*`. Nothing in `b2/` or the project tree was modified by me.
One accident: my precheck run redirected into `review2/kldrc.log`, replacing the other reviewer's one-line log (their record
`review2/kldrc/pad_hspad/kldrc.json` is intact). RERAN = by me; READ = from artefacts.

## Verdict: GO with conditions (concur with REVIEW2); the publish that happened matches the reviewed artefacts

Open conditions, both already recorded by the owner: (a) before tapeout, fix the TERM_VCM path in `pt_hs_leg` and rerun with R
(row PC-14); (b) the floorplan must be regenerated for the new outline and side-edge pins. I add A1 (the resistance is worse at the
PDK high corner than the published text says) and A3 (the v6 floorplan now has a real overlap, not just zero clearance).

## Confirmed (RERAN)
| Check | Result |
|---|---|
| sha256 `b2/pad_hspad.gds` / `physical.spice` | 5b7c598e6c32a6aa487129d4a43db3173905ad6f6b7b20343d5e603750d3f679 / 320c43d90e70588592c72caa11f8cacf05ccc8f32429d5d6bc90c7345eabc74c |
| `b2/reference.spice` | sha d5608531, identical to the PD21 published reference |
| Magic `gds read` -> flatten -> DRC -> extract (pad image b6027809) | DRC 0; 508 devices, device lines identical to `b2/pad_hspad_flat.spice`; all 479 C pairs equal. So model 320c43d9 is from GDS 5b7c598e |
| netgen LVS vs `hs_reference` | Circuits match uniquely; no property errors; pin lists equivalent |
| Negative control 1: RX_P/RX_N labels swapped in the GDS | Netlists do not match |
| Negative control 2: PAD_P/PAD_N labels swapped in the GDS | Netlists do not match |
| Negative control 3: RX pins swapped on the two legs in the reference | Netlists do not match |
| KLayout precheck (`kl_block_drc.py`, 0.30.9, variant D, deep, threads 1) | main 0 / antenna 0, gds_sha256 5b7c598e |
| Extracted C | RX_P 71.30 / RX_N 71.16 fF (0.14), mutual 3.37; PAD_P - PAD_N wiring 14.55 fF |
| Geometry vs PD21 backup (7bf4d791) | outline (-0.055,0)-(492,912.91), nothing outside; pad openings XOR 0; ring band y < 426: Metal2/3/4 and Via2/3/4 XOR 0; Metal5 differs only in (294,414)-(339,426), 212 um2 |
| RX routes | each: Metal4 1.0 x 74.08 um, one Via4, Metal5 0.6 um strap 94.90 um2 to x 492; labels (491.5, 612.75) / (491.5, 618.75); no other Metal5 within 3 um |
| TERM_VCM net trace (my own script, `r1/trace-termvcm.txt`) | 25 units per leg with one Via1 + one Via2 each -> Metal3 rail 1 x 137.5 um per leg -> ONE Via3 per leg at (332.5, 474.64) / (332.5, 756.86) -> one Metal4 polygon 1 um wide, y 474.34-757.16 -> ONE Via4 at (332.5, 627.75) -> Metal5 1 um strap to x 492. Exactly as REVIEW2 section 4 |
| AC tt 27 C code 5, 3.3 V (`bench/r1ac5-ac.json`) | Rdiff 100.84 ohm, C/leg 1.148 pF, die RL 2.4 GHz 8.07 dB, COB 6.08 dB: equals the designer's number |
| What-if, typical R, trunk + 2 Via3 + pin strap (REVIEW2's model) | Rdiff 134.86 ohm, die RL 2.4 GHz 6.32 dB: reproduces REVIEW2 |

The designer's "~4 ohm" is wrong for the reason REVIEW2 gives: the differential termination current runs leg-to-leg through both
single Via3 and all 282 squares of the 1 um Metal4 trunk. It is neither a pure common-mode resistance nor a one-leg resistance:
13.8 ohm (P) and 11.6 ohm (N) of trunk plus one Via3 sit in series with each leg (adds to each leg's termination, 2.2 ohm
unbalance); only the Via4 + Metal5 pin strap (10.9 ohm) is common to both and affects common mode only. It is not in the netlist
(extraction is C-only), so no AC / termination / return-loss evidence sees it.

## Additional findings
A1. **[Before tapeout; text correction now] The 34-44 ohm figure is the typical corner only.** Source: PDK Magic tech
   `/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.tech` (sha f0c3a445, in the pad image), extract style `ngspice`: default variant Metal1-4 90 mohm/sq,
   Metal5 40, Via 4.5 ohm/cut; variants `(hrhc),(hrlc)`: Metal1-4 104, Metal5 49, **Via 15 ohm/cut**. REVIEW2's "high" case scaled the via
   to about 5.2 ohm. With the PDK high values the trunk is 29.4 ohm and the two Via3 are 30 ohm: 59 ohm between the legs before the
   Metal3 rails and the single Via1/Via2 per unit (roughly 10 ohm more). RERAN with trunk + Via3 + pin strap only (`r1/physical_trunk_pdkhigh.spice`):
   | Corner, code | Rdiff (ohm) | die RL 2.4 GHz (dB) |
   |---|---|---|
   | tt 27 C 3.3 V, code 5 | 159.4 | 5.41 |
   | tt, code 15 (lowest) | 117.9 | 6.24 |
   | ss 32 C 3.15 V, code 15 | 131.0 | 5.99 |
   So at high metal/via resistance even tt cannot be trimmed to 100 ohm (README and `SUPERSEDED.md` say "about 100 ohm at code 15 (tt)").
   The published text should say "34-44 ohm typical, about 60-70 ohm at the PDK high corner; no code reaches 100 ohm there". This
   raises the priority of the leg fix; it does not change the publish decision (the PD21 cell is worse by about 10 ohm).
A2. [Minor] RX_P / RX_N totals match, but the split does not: RX_N-VDD 8.14 fF vs RX_P-VDD 2.31 fF, RX_P-VSS 44.3 vs RX_N-VSS 38.5 fF
   (the VSS strap is next to RX_P, the VDD strap next to RX_N). VDD noise converts to differential through 5.8 fF into a ~30 ohm
   node: about -52 dB at 2.4 GHz, -79 dB at 100 MHz. Acceptable; "mirror-identical" holds for the routes, not for their neighbours.
A3. **[Blocking for assembly, not for the cell]** `scratch/chip-assembly-v6/run/floorplan-v6.json` still has `pad_hs_rx` at the PD21
   outline [2794.75, 749.0, 3906, 1227.055]. The published cell occupies [2993.09, 735.0, 3906, 1227.055] (mirrored east: chip = (3906 - y, 1227 - x)).
   `detect` is at [2776, 484, 3466.44, 735.26]: it now overlaps the pad cell by 0.26 um in y over x 2993-3466 (REVIEW2 says "touches").
   RX_P lands at chip (3293.25, 735.5), RX_N at (3287.25, 735.5), i.e. inside that overlap strip. v6 cannot be assembled with this cell as is.
A4. [Info] Post-publish check (RERAN 06:46): `wired-receive-hs/pad_hspad.gds` 5b7c598e, `physical.spice` 320c43d9, `reference.spice` d5608531;
   `pad_hspad-kldrc.json` has gds_sha256 5b7c598e, clean, `gds` = file name; `pad_hspad` is registered in `kl_block_drc_blocks.json`;
   `check_block_kldrc.py` prints `CLEAN pad_hspad main=0 antenna=0`. The checker as a whole still exits 1 (45/65) because of other blocks.
   The ten `ap4-hspad-*.json` files and the seven layout records are byte-identical to the staged ones. `lvs-reference.spice`
   (d8e34d25, from the owner's LVS-reference flow) was not reviewed by me.
A5. [Info] Supply trim: I did not rerun; REVIEW2's numbers (termination 52.0 / 50.8 / 50.1 ohm per leg at 3.3 / 3.5 / 3.63 V, safe set
   already at 3.63 V) are READ. Latch-up audit, HBM 2 kV / 1 kV and CDM surrogate: READ, all carry model sha 320c43d9, equal to PD21 within 0.001 V.

## Not done by me
Long HBM set, LU audit rerun, power-up bench, R extraction (none exists in this flow; all R figures are geometry x PDK sheet values).
