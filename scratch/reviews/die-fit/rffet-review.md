# Review: RF FET probe frames shrunk to 260 x 260 um (pt_char_rffet, _open, _short)

Reviewer run of 2026-11-18. Inputs: the three published GDS files in
`projects/programmable_transceiver_platform/analog/characterization/generated/`, copied to
`scratch/reviews/die-fit/rffet-review-work/` and read back from disk. Nothing under `projects/` was edited,
the generator was not run.

**Verdict: GO-with-conditions.**
The layout is physically clean and does what the README says (DRC 0 on both decks, LVS with working negative
controls, OPEN/SHORT connectivity right, frames identical outside the DUT window, three-frame column clean with
five nets). No finding requires a layout change before use. Conditions:

1. Fix the stale 430 x 260 statements in three other files (finding 4) so the floorplan uses 67 600 um2, not 111 800 um2.
2. Either make `rffet.py stack` test what the README says it tests, or reword the README (finding 3).
3. Accept, knowingly, that port spacing is now at the practical minimum for facing GSG probes (finding 1); confirm
   against the probes and calibration substrate that will actually be used.

Recommended, not a condition: identical substrate taps in all three frames (finding 2).

## Findings, by severity

### 1. Medium (judgement): facing-probe spacing is now at the practical minimum
- Evidence (measured on GDS, `geom.txt`): signal pad centres 200.0 um apart (old 300), Metal5 pad edges 140.0 um apart
  (old 240), GLASS 50 x 50 um, so opening edges are 150 um apart. Pads and openings themselves are unchanged.
- Judgement: GSG tips skate toward the opposite probe on overtravel, so tip-to-tip distance in use is roughly
  150-180 um. Air coupling between the two probe tips is not shielded by the 1 um thick ground rails. The DUT is small
  (W = 10 um; |S12| from Cgd is of order -40 dB at 5 GHz), so probe crosstalk matters for S12, hence for fmax (Mason U)
  and Cgd; fT from h21 and Rg from Z11 are much less sensitive. OPEN subtracts the parallel coupling to first order
  only if probe placement is repeatable between DUT and OPEN.
- I recall vendor layout notes giving about 200 um as the minimum centre spacing for facing probes; I searched for the
  figure and could not confirm it, so treat it as unverified. A 200 um port spacing may match the thru length of common
  calibration substrates, which would be an advantage; also unverified.
- Not a defect of the layout. It is a margin that the change spent.

### 2. Medium (evidence + judgement, pre-existing, slightly worse now): OPEN and SHORT have no substrate tie
- Evidence: round-trip extraction of the OPEN gives GND and VSUBS as separate nodes joined only by 0.242 pF
  (old 0.319 pF, -24 %); SHORT 0.319 pF (old 0.405 pF). In the DUT the guard ring ties substrate to GND
  (extraction reports GND as the substrate node). Pad/lead capacitance to substrate is 38.2 fF (G) and 37.6 fF (D).
- Judgement: the return path of the pad-to-substrate capacitance differs between DUT (ohmic tap 100 um away plus
  capacitive) and OPEN (capacitive only), so OPEN does not reproduce the DUT pad admittance exactly. Above about
  1 GHz the capacitive path dominates in both and the error should be a few percent; it grows toward low frequency.
  Stacking the three frames on one ground helps (all share the DUT tap, 200 / 400 um away) but does not make the
  local substrate identical.
- Cheap fix if the frames are regenerated anyway: the same p+ tap ring (no FET) in OPEN and SHORT, or taps under the
  ground strips in all three.

### 3. Low-medium (evidence): the `stack` check does not test what the README claims
- README: `rffet.py stack` "checks Magic DRC 0 and that G and D of the DUT and of the OPEN stay separate nets on one
  common ground". The code only records the DRC count, the bounding box, the `.subckt` line (which has no ports) and a
  device count. It never looks at nets. A short between OPEN G and D, or DUT G and OPEN G, would not be flagged.
- `stack.json` reports `"devices": 7`. The real number is 5: `l[:1] in 'XM'` is true for empty lines.
- It runs on the `.mag` files with Magic 8.3.623, not on the published GDS.
- The claim itself is true (my re-derivation below), so this is a weakness of the regression check, not of the layout.

### 4. Low (evidence): stale 430 x 260 size elsewhere (not edited)
- `projects/programmable_transceiver_platform/spec/tapeout-readiness.json:2356` - "430 x 260 um each".
- `projects/programmable_transceiver_platform/integration/signoff/skeleton/floorplan-skel.json:2689, 2693, 2697` -
  area 111800 um2 (= 430 x 260) for each of the three cells; now 67 600. The same file lists the three cells under
  `"dropped"`.
- `scratch/reviews/interface-changes.md:279` (row CH2) - "each 430 x 260 um ... Total 0.335 mm2; ... DUT + OPEN
  (0.224 mm2)". Now 0.203 mm2 for three separate frames, 0.172 mm2 for the stacked column.
- No other hits in the project for 430 x 260 in any spelling (md, py, json, yaml, txt, csv, tcl, lef).

### 5. Low (evidence): the frame is not symmetric about y = 0 in Metal5, contrary to the docstring
- Metal5 mirrored about y = 0 differs by 144 um2: the source via stack adds a 12 x 6 um Metal5 tab at
  y = -86..-80 on the bottom strip only. GLASS is symmetric (XOR 0). Mirror about x = 0: Metal5, Metal4, GLASS identical.
- In the 60 um overlap band of two stacked frames: GLASS coincides exactly (XOR 0); the ground pads and the 28 um strip
  coincide exactly; what does not coincide is 1352 um2 of Metal5 (each frame's own rail stubs 4 x 20 x 16 um, plus the
  tab) and the upper frame's source stack on Metal3 (280 um2), Metal4 (240 um2), Via3, Via4, which lands under the
  lower frame's top strip. All of it is ground and DRC clean, so stacking is valid, but "coincident on every layer"
  is not literally true.
- Consequence for de-embedding in a column: DUT (bottom), OPEN (middle) and SHORT (top) see different neighbours and
  slightly different ground networks. Second order, judgement.

### 6. Low (evidence): slotting rule passes with zero margin on the pads
- Deck rule MSLOT5.1 exempts `(top metal AND pad opening) sized 5 um`. GLASS 50 um + 5 um = 60 um = the pad exactly
  (GLASS grown by 5.000 um is inside Metal5, by 5.001 um is not). Strips 28 um and rails 20 um are under the 30 um limit.
  Any later change that enlarges a pad or shrinks an opening trips MSLOT5.1.

### 7. Low (judgement, pre-existing): source lead
- Source and body reach ground only through one 4 um Metal3 lead, 74 um long, to the bottom strip. Series R and L in
  the common source, removed by SHORT to first order. The new rails are 30 um from the DUT on both sides; a symmetric
  source connection to them would be shorter. Optional.

### 8. Info
- netgen's `Final result: Circuits match uniquely.` is also printed when property errors exist. The record field
  `lvs` is therefore not discriminating; `lvs_unique` (which the helper derives with a property-error test) is.
- LVS merges the five fingers, so it checks total W = 10 um and L, not the finger count. Finger count confirmed on
  the GDS instead: 5 separate poly shapes.
- The device subcell carries one shape on layer 0/0 (7.28 x 4.54 um), old and new alike. Not examined further.

## What passed (evidence)

| Check | Result |
|---|---|
| Magic DRC, `drc(full)`, GDS read back, hierarchical and flattened (Magic 8.3.678) | 0 / 0 / 0 for DUT / OPEN / SHORT |
| KLayout GF180MCU deck, variant gf180mcuD (5LM, 11K top), decks `all,-density` (antenna included, 176 decks), 1 thread | 0 / 0 / 0, rc 0 |
| LVS, DUT GDS read back vs `pt_char_rffet.spice` | match unique, no property errors, pins G D GND |
| Negative controls | w = 2.2u: property error (w 2e-06 vs 2.2e-06); 4 fingers: property error (w 1e-05 vs 8e-06); l = 0.30u: property error; G and D swapped: "Top level cell failed pin matching" |
| OPEN connectivity | Magic: ports G, D, GND, no devices. KLayout net tracing on metal: 3 nets, four ground pads + both rails on one |
| SHORT connectivity | Magic: single port GND. KLayout: 1 net containing all six pads |
| Pads | Metal5 60.0 x 60.0, GLASS 50.0 x 50.0, enclosure 5.0, six per frame |
| Pitch | G-S-G centres at y = -100, 0, +100 at x = -100 and +100 |
| Ground rails | 20.0 um wide at x = 30..50 and -50..-30; 20.0 um to the signal pads; Metal4 leads 4 um wide, cross under the rails with 80 um2 overlap each; gate and drain lead ends 12 um apart |
| Outline | 260 x 260 (old 430 x 260); LEF SIZE 260 x 260 |
| DUT vs OPEN vs SHORT | Metal5, Metal4, Via4, Via3, GLASS identical. All differences inside x = -10..10, y = -7..7 |
| Three-frame column at 200 um pitch, built from the published GDS | 260 x 660; Magic DRC 0 (hier and flat); KLayout 0; MSLOT5.1 remainder 0; 5 nets (DUT G, DUT D, OPEN G, OPEN D, one ground holding all eight ground pads, all rails and SHORT's G and D) by KLayout net tracing and by the Magic `.ext` node list; 5 devices |
| Record | `char_rffet-physical.json` gds_sha256 9e42f545...609c7c equals the file on disk; `rffet.py` hash in `char_speed-evidence.json` equals the file on disk |
| README | describes what was built (sizes, spacing, rails, 4.8 fF, 38.2 / 37.6 fF all reproduce) apart from finding 3 |

## Old vs new extracted parasitics (Magic, evidence)

| | old | new |
|---|---|---|
| OPEN G total | 42.5 fF to substrate | 38.2 fF to substrate + 4.8 fF to frame ground = 43.0 fF |
| OPEN D total | 41.9 fF to substrate | 37.6 fF + 4.8 fF = 42.4 fF |
| OPEN ground to substrate | 0.319 pF | 0.242 pF |
| SHORT ground to substrate | 0.405 pF | 0.319 pF |
| DUT G to GND | 45.23 fF | 45.49 fF |
| DUT D to GND | 43.61 fF | 44.06 fF |
| DUT G to D | 0.602 fF | 0.602 fF |
| Lead length outside the pad | 112 um | 62 um |

Judgement: shunt loading is unchanged within 1 %, part of it now goes to metal ground instead of lossy substrate, and
series lead R and L drop by about 45 %. The rail crossing adds a small shunt C mid-lead, which OPEN then SHORT handles
at these lengths. The rails between the ports should reduce on-wafer port-to-port coupling. On parasitics alone the
new frame is no worse than the old one. Magic does not extract pad-to-rail sidewall coupling at 20 um or pad-to-pad
coupling at 140 um; both are absorbed by OPEN.

## Not checked
- No electromagnetic simulation; no S-parameter simulation of DUT with OPEN/SHORT de-embedding; ground inductance not computed.
- Probe geometry against a specific probe model or calibration substrate (figures in finding 1 are from memory).
- Density and fill rules (deck `density` excluded); behaviour of the fill generator around the frames; chip-level placement, including how overlapping LEF outlines of a stacked column are handled by the assembler.
- The device PCell internals beyond DRC and LVS.
- `rffet.py layout/export/stack` were not re-run; the builder's `.mag` files were not re-verified, only the GDS.
- My first slotting emulation in `geom.txt` (section 1, "area wider than 30um") used the wrong `sized()` overload; ignore those lines, `mslot.txt` and the deck are the valid results.

## Files
- Work directory: `/home/ubuntu/svalbard/scratch/reviews/die-fit/rffet-review-work/`
  - `geom.py`, `geom.txt` - geometry, symmetry, frame XOR, stack band
  - `conn.py`, `conn.txt` - KLayout net tracing
  - `mslot.py`, `mslot.txt` - slotting re-derivation
  - `tools/run.sh` - Magic, netgen, KLayout commands; `tools/*-magic-drc.txt`, `tools/lvs_*.txt`, `tools/kl_*.log`, `tools/*.lyrdb`
  - `stack/rffet_stack.gds` - the column built from the published GDS
- Image: `hpretl/iic-osic-tools@sha256:89641950...8a3` (id `bd7a702bef0b`), one job at a time, 1 thread.
