# wtx_ser8d rebuild, session 13 (layout sub-agent, 2026-11-18)

## 0. Session 15 (2026-11-20): Metal5 / supply change for ASM-8 (current state; sections 1-8 describe the s13 build)

Only Metal5 / supply changed (`ser8d_macro.py`: `channels()`, `bars()`, `supply_em()`, `_engine()`, `write_m5_plan()`);
devices, `HOPS` (as found in the file: `{0:(6,), 1:(7,), 2:(0,), 3:(0,), 4:(6,2), 5:(7,3), 6:(6,4), 7:(7,5)}`), row plan and
Metal1-4 routing rules untouched (the engine re-places Metal5 trunk columns around the keep-outs, so Metal4 track ends move).
- **Grid channels** (Metal5-free over the full height, block x = ser8d x): 207-228, 242-263, 382-403, 417-438, 557-578, 592-613 um
  (21 um = 16 um grid strap + 2 x 2.5 um cut; axes 217.5 / 252.5 / 392.5 / 427.5 / 567.5 / 602.5 = 7.5 + 35 k, k = 6, 7, 11, 12, 16, 17).
- **VSS bars** (block VSS trunks): x 335-345, 405-415, 475-485, y 0 - 197.18, Via4 arrays (0.56 um pitch) on every VSS power track (432 cuts).
- **Supply straps**: 18 pairs (VDD x, VSS x + 3) at 23.5 + 35 k (was 19 at 40 um), the 3 pairs under the bars dropped;
  `strap_cuts` on (6 Via4 per strap / power-track crossing, was 1).
- The engine (`analog/timing/layout_engine.py`, not ours) has no option for these: `_engine()` patches three anchors of
  `generate` at run time (raises if the source changes). Owner of the engine may want `m5_keep`, `strap_x0`, `m5_bars` as real options.
- Outline unchanged 744.12 x 197.68 um. Pins: same ports, top edge; PH / F x moved by up to 6 / 24 um (F5).
- Checks from disk (`verify.py v`, GDS = generated/fast): Magic DRC 0, KLayout DRC 0, LVS `Circuits match uniquely`,
  no-diode reference fails as expected, 4 negative controls fail (fswap, hopclk, prop, dswap); 39 antenna diodes;
  antenna also clean in the block top (Magic antenna 0 on pt_wiredtx8).
- ser8d logic IR (block mesh, 60 mA, `s13/top/ir`): VDD 20.6 mV (was 21.05), VSS 11.4 mV (was 17.4); high R 35.6 / 22.4 (was 37.1 / 30.3).
- Timing evidence: `rc.py` rerun (`rcx/wtx_ser8d.rc.spice`, copied to generated/fast: 1546 R, 13779 C, 2434 X, 39 D, ports ok).
  `ctab.py` -> `ctab_s15.json`. **Compared to `ctab_final.json` the hop plan also differs** (HOPS was edited after s13: streams 2, 3
  single hop at phase 0, R3_0 gone), so hop-clock C moved by the plan: Q0 +52, Q1 -31, Q6 -13, Q7 -25 fF. Wiring-only effect
  (dry runs, same HOPS, with / without the plan): Q4 +22 um (+3.7 fF), Q0 +13 um, F5 +33 um (+2.9 fF), F4 +3.9 fF, B5_0 +3.2 fF,
  PH 21.2-24.5 fF (spread 3.3, was 3.1), all other hop nets within +-3.3 fF. **No timing simulation was run**: the set-up change
  is not measured; at <= 4 fF on Q / B / R nets it is expected well under 10 ps, but this is not shown. Owner's bench to confirm.

Hop plan built: `HOPS = {"0": [6], "1": [7], "2": [7], "3": [6, 1], "4": [6, 2], "5": [7, 3], "6": [6, 4], "7": [7, 5]}` (stream -> hop clock phases), as found in
`analog/wired_tx/ser8d_macro.py` at build time. **`HOPS-FINAL.txt` did not exist when this was finished; the build uses
what is in `ser8d_macro.py`.** If the table changes: rerun section 7 (build 8 s, verification about 1 min); `rows()` is derived
from `HOPS` and was dry-run for 1 hop and 2 hops on every stream (same outline).

Everything below was RUN in this session unless marked "read" or "not built".

## 1. Result

| | s12 build (old hop plan) | this build |
|---|---|---|
| outline (engine report) | 744.12 x 315.08 um | **744.12 x 197.68 um** |
| area | 0.2345 mm2 | **0.1471 mm2** (-37.3 %) |
| GDS bounding box read back by Magic | (not re-measured) | 1.5 0 743.62 198.18 (llx lly urx ury, um) |
| Magic DRC `drc(full)`, GDS read back from disk | 0 (read, s12 review) | **0** |
| KLayout DRC, `sak-drc.sh -k`, analog image (same flow as s12 `kl.py`) | 0 (read) | **0** (ran: True) |
| LVS, GDS from disk, fresh directory | unique (read) | **Circuits match uniquely** |
| antenna diodes added by the engine | 17 | 39 |
| transistors in the reference (lines) | 456 | 456 (netlist and sizes untouched) |

Target (height <= 240 um at the same width, or <= 0.18 mm2): **reached** (197.68 um, 0.147 mm2).
The same old row plan with the new hop table and the old channels would have been 744.12 x 317.24 um (dry run, row 0 of the lever table).

The mux edge is the TOP edge (y = 197.68): all 59 signal pins are M3-M5 stacks at y = 196.93, as in the s12 build.
PH and F pin x positions are in the tables of section 4 (PH pins sit over their own `wtx_qph`, 81 ... 731 um; F pins 131 ... 739 um).
They are not gathered into a 291-um window for `wtx_mux8`; the engine places a port trunk at the pin column, and gathering
them would add Metal4 length to the F nets. Say so if the mux needs them gathered (`em['trunk_at']` can do it).

## 2. LVS and negative controls (Netgen, digital image, GDS read back from disk into `v/`)

Layout netlist: `ext2spice lvs` of the GDS in an extraction-only Magic session (DRC in a separate session, s12 tool note).
Reference: `ser8d_macro.top_spice()` + the cell netlists `generated/fast/<cell>.spice` + the engine's antenna diodes
(lines `DANT*` from `generated/fast/wtx_ser8d.spice`). Hierarchical comparison: every cell class (wtx_qph, wtx_sreg5, wtx_q4ctlc,
wtx_q4ck, wtx_tspcb, wtx_tspcbx, wtx_div5r) is reported equivalent, top level 71 devices = 32 cell instances + 39 diodes (`v/lvs.txt`).
Device properties are compared (Netgen gf180mcuD setup); the property control below shows that a 10 % width error is caught.

| reference | Netgen final line |
|---|---|
| ref = top_spice() + cells + diodes | `Final result: Circuits match uniquely. .` |
| ref = top_spice() + cells, NO diodes (expected to differ by the diodes only) | `Final result: Top level cell failed pin matching.` |

The no-diode run differs by the diodes only: `v/lvs-nodiode.txt` line 239-240, `diode_nd2ps_03v3 (39) | (no matching element)`,
all cell classes equivalent, same net count (127).

| negative control (reference edited) | Netgen final line | verdict |
|---|---|---|
| neg_fswap (outputs of XH3_1 and XH4_1 swapped) | `Final result: Top level cell failed pin matching.` | FAIL (as required) |
| neg_hopclk (XH0_0 clocked by Q7 instead of Q6) | `Final result: Top level cell failed pin matching.` | FAIL (as required) |
| neg_prop (first nfet with w=2u in the reference: w 2u -> 2.2u; Netgen names the cell) | `Final result: Circuits match uniquely. . The following cells had property errors: wtx_qph` | FAIL (as required) |
| neg_dswap (XL0 data pins D0 / D8 swapped) | `Final result: Top level cell failed pin matching. The following cells had property errors: wtx_ser8d` | FAIL (as required) |

Note on the property control: Netgen prints "match uniquely" for the topology and then lists the cell with property errors;
that is its way of failing a parameter mismatch.

Antenna diodes (39, `diode_nd2ps_03v3`, anode VSS, N+/Psub under the net's own wire), on nets:
D0 D1 D10 D11 D12 D13 D14 D15 D16 D17 D18 D19 D2 D20 D21 D22 D24 D25 D26 D27 D28 D29 D3 D30 D31 D32 D33 D34 D35 D36 D37 D38 D4 D5 D6 D7 D8 D9 SERQ.
38 are on the D inputs (their Metal5 trunks run to the top edge, 150-190 um; 0.36-0.72 um2 each), 1 on SERQ. D23 and D39 need none.
None on PH*, F*, hop clocks. Full lines with area / perimeter: `v/verify.json` (`antenna_diodes`).

Extracted port order = `ser8d_macro.PORTS` for the LVS netlist, the flat C-only netlist and the R+C netlist (checked by script).

## 3. Area: what each lever gave

Measured with geometry-only dry runs of `le.generate` (Magic stubbed: `levers.py`, output `levers.txt`); the dry run of the built
variant equals the built outline (197.68 um), so the model is exact for outline. Rows 5 is what was built and verified.

| # | variant | outline (um) | area (mm2) | comment |
|---|---|---|---|---|
| 0 | s12 row plan, channels above the rows (new hop table) | 744.12 x 317.24 | 0.2361 | baseline; channels 29 + 45 + 28 + 22 um |
| 1 | same rows, Metal4 tracks over the cells (`over_cell`) | 744.12 x 208.43 | 0.1551 | **-108.8 um**: the cells use Metal1/2 only (checked in the .mag files), so the tracks fit over them; only the P row (59 tracks, 33-um cells) keeps a 12-um channel |
| 2 | registers 4 + 4, one row hops + /5 divider + CK + CTL, P row on top | 744.12 x 197.18 | 0.1467 | **-11.3 um**: the 16-um hop flops no longer sit in 51-um register rows |
| 3 | = 2, hop groups under the BO end of their register column | same | same | no area; B wires 81-165 um instead of 84-319 um |
| 4 | = 3 + PH tracks first in the P row (`em track_first`) | same | same | no area; PH track+trunk length 37-44 um instead of 6-44 um |
| 5 | = 4 + PH / F / Q / hop-data trunks with free neighbour columns (`net_space` 0.02) | **744.12 x 197.68** | **0.1471** | +0.5 um; **built** |
| 6 | three rows | 939.12 x 157.86 | 0.1482 | not better in area, 195 um wider; not built |
| 7 | two P rows of four (P0-3, P4-7) with hops beside them | 732.99 x 187.82 | 0.1377 | -6 % more, but PH trunks 23-77 um (unequal by a row) and F0-4 / F5-7 unequal; rejected for the PH equality requirement; not built |
| 8 | = 5 without the D0..D39 trunks to the top edge | 744.12 x 197.68 | 0.1471 | **0 area**: port trunks are Metal5 over the array, not channel tracks. It would remove 6.3 mm of Metal5 and 38 of the 39 antenna diodes. The engine cannot put pins on another edge (`analog/timing/layout_engine.py` is outside my area); not built |
| 9 | = 5 with Metal4 track space 0.28 instead of 0.32 um | 744.12 x 195.32 | 0.1453 | -2.4 um; module constant of the engine, not a supported option; not built |

- `max_row_width`: no effect, the rows are explicit; the width is set by the eight `wtx_qph` in one row (743 um).
- Remaining height: two register rows of 51.45 um, the hop / divider row 40.2 um (`wtx_div5r` sets it), the P row 33.45 um + 12.1 um of channel, 1 um above and between rows, 2 um bottom and 1 um top margin.
- Cell area alone is about 0.099 mm2; the build is at 67 % utilisation.

## 4. Extracted wire capacitance (flat C-only extraction of the GDS read back, `cthresh 0`)

Total = sum of all extracted capacitors with a terminal on the net (wire + cell-internal metal on that net, **no device gate /
junction capacitance**, antenna diodes not included). Script `ctab.py`, data `ctab_final.json`; "s12 build" = the same
extraction run on the previous GDS (`prev/`, `ctab_prev.json`).

Phase inputs: 21.3 - 24.4 (spread 3.1) fF; s12 build 29.2 - 66.3 (spread 37.1) fF.

| net | wire C total (fF) | to VSS/VDD/substrate | coupling to signals | largest partner (fF) | s12 build total (fF) | pin x at top edge (um) |
|---|---|---|---|---|---|---|
| PH0 | 23.86 | 12.04 | 11.82 | G0 5.92 | 41.84 | 81.0 |
| PH45 | 23.92 | 9.16 | 14.76 | G1 5.93 | 58.98 | 179.4 |
| PH90 | 21.32 | 9.0 | 12.31 | G2 5.93 | 29.19 | 269.4 |
| PH135 | 23.67 | 8.94 | 14.73 | SERQ 6.29 | 66.32 | 360.6 |
| PH180 | 22.32 | 10.14 | 12.18 | G4 5.94 | 58.34 | 455.4 |
| PH225 | 21.73 | 8.94 | 12.79 | G5 5.95 | 29.72 | 547.8 |
| PH270 | 22.55 | 10.17 | 12.38 | G6 5.98 | 58.7 | 640.2 |
| PH315 | 24.45 | 10.81 | 13.64 | G7 5.95 | 37.89 | 731.4 |

Outputs: 7.9 - 13.8 (spread 5.8) fF; s12 build 13.8 - 69.1 (spread 55.3) fF.

| net | wire C total (fF) | to VSS/VDD/substrate | coupling to signals | largest partner (fF) | s12 build total (fF) | pin x at top edge (um) |
|---|---|---|---|---|---|---|
| F0 | 11.41 | 8.6 | 2.81 | XH0_0/QN 1.17 | 50.26 | 131.4 |
| F1 | 9.48 | 4.57 | 4.92 | D37 1.23 | 69.11 | 351.0 |
| F2 | 12.35 | 4.39 | 7.96 | Q7 2.67 | 36.37 | 498.6 |
| F3 | 13.75 | 4.25 | 9.5 | D39 3.62 | 30.3 | 669.0 |
| F4 | 7.94 | 4.89 | 3.05 | XH4_1/QN 1.17 | 28.11 | 192.6 |
| F5 | 10.79 | 7.34 | 3.45 | XH5_1/QN 1.17 | 31.71 | 412.2 |
| F6 | 11.55 | 6.06 | 5.49 | Q4 1.94 | 13.79 | 559.8 |
| F7 | 9.98 | 3.96 | 6.02 | Q5 1.88 | 14.77 | 738.6 |

Hop clocks (output Q of `wtx_qph` k). The load is unequal by the hop plan itself: Q6 and Q7 each clock four first hops spread over
the row, Q1..Q5 one final hop each, Q0 none. Q1 is longer than Q2..Q5 because the final hop of stream 3 sits in the fourth column
(under its register), about 520 um of wire from P1 (dry-run length).

| net | wire C total (fF) | to VSS/VDD/substrate | coupling to signals | largest partner (fF) | s12 build total (fF) |
|---|---|---|---|---|---|
| Q0 | 9.84 | 4.14 | 5.7 | QW0 1.89 | 62.91 |
| Q1 | 40.29 | 14.82 | 25.47 | R3_0 3.46 | 81.52 |
| Q2 | 25.17 | 11.06 | 14.12 | QW2 1.89 | 37.8 |
| Q3 | 24.21 | 12.12 | 12.09 | R5_0 2.64 | 40.37 |
| Q4 | 26.84 | 10.93 | 15.91 | R6_0 2.71 | 124.92 |
| Q5 | 30.95 | 12.5 | 18.45 | R7_0 3.19 | 35.64 |
| Q6 | 95.06 | 29.93 | 65.13 | QRST 12.75 | 41.78 |
| Q7 | 86.78 | 44.93 | 41.85 | Q6 6.24 | 71.61 |

Hop data inputs (register outputs B k, inter-hop R k):

| net | wire C total (fF) | to VSS/VDD/substrate | coupling to signals | largest partner (fF) | s12 build total (fF) |
|---|---|---|---|---|---|
| B0_0 | 35.65 | 13.64 | 22.02 | Q6 5.72 | 27.52 |
| B1_0 | 34.2 | 12.05 | 22.15 | LDA 6.87 | 27.05 |
| B2_0 | 28.25 | 13.21 | 15.04 | D38 3.49 | 28.5 |
| B3_0 | 29.57 | 18.74 | 10.83 | R3_0 4.2 | 28.11 |
| B4_0 | 27.99 | 12.73 | 15.26 | QRST 3.2 | 30.29 |
| B5_0 | 24.97 | 14.88 | 10.1 | QRST 2.45 | 31.03 |
| B6_0 | 24.85 | 15.35 | 9.5 | XL6/BN 1.85 | 28.76 |
| B7_0 | 20.7 | 12.42 | 8.29 | Q7 1.89 | 28.14 |
| R3_0 | 17.86 | 6.14 | 11.72 | B3_0 4.2 | - |
| R4_0 | 14.35 | 6.39 | 7.96 | B4_0 2.4 | - |
| R5_0 | 13.82 | 6.3 | 7.52 | Q3 2.64 | - |
| R6_0 | 14.34 | 6.07 | 8.27 | Q4 2.71 | - |
| R7_0 | 14.74 | 6.03 | 8.71 | Q5 3.19 | - |

Others:

| net | wire C total (fF) | to VSS/VDD/substrate | coupling to signals | largest partner (fF) | s12 build total (fF) |
|---|---|---|---|---|---|
| QK0 | 580.83 | 331.32 | 249.51 | LDA 70.92 | 604.23 |
| QK1 | 593.65 | 325.3 | 268.35 | LDA 70.61 | 569.79 |
| QKN0 | 42.18 | 19.3 | 22.88 | QKN1 16.78 | - |
| QKN1 | 45.91 | 7.6 | 38.31 | QKN0 16.78 | - |
| QDN | 34.21 | 7.11 | 27.11 | QKN1 16.52 | - |
| QD | 101.18 | 35.22 | 65.96 | QK1 24.28 | - |
| LDA | 368.1 | 114.56 | 253.54 | QK0 70.92 | 467.63 |
| QRST | 850.48 | 466.33 | 384.15 | QK0 50.32 | 923.3 |
| DC | 48.54 | 7.19 | 41.35 | QRST 25.69 | - |
| SERQ | 471.99 | 302.24 | 169.75 | QRST 27.48 | - |
| WCKQ | 13.22 | 10.93 | 2.29 | XCTL/WCN 1.25 | - |

D0..D39 (min / mean / max): [49.5, 70.1, 86.6] fF; s12 build [30.1, 65.7, 109.2] fF (plus one antenna diode each on 38 of them now).

What changed the numbers: the first build of the new floorplan had F2 beside the Q7 trunk (10.0 fF), F1 / F3 beside D trunks (10.7 / 9.2 fF),
PH135 beside SERQ (10.0 fF), B1_0 beside LDA (17.0 fF); the free neighbour columns brought these to 2.7 / 1.2 / 3.6 / 6.3 / 6.9 fF.
Still coupled: PH k to the unused output G k of its own slice, 5.9 fF on every phase (equal, inside / beside the cell); Q6 to QRST 12.8 fF;
QK0 / QK1 to LDA 71 fF (inside `wtx_sreg5`, as before).

## 5. Extraction for simulation

| netlist | path | how | sha256 |
|---|---|---|---|
| C-only, hierarchical (same name and form as before; the bench `s12/chain.py` reads it) | `analog/wired_tx/generated/fast/wtx_ser8d.ext.spice` | generator (`ext2spice cthresh 0 rthresh 0`) | 730de14a1da3a85156a96eb1bd30258b3b0f51ed236154056b95ff95a7943ecc |
| C-only, flat, from the GDS read back | `scratch/wired_tx/s13/ser8d/v/wtx_ser8d.flatc.spice` | `verify.py` | ec4261de9e2136522dc8e40c59e394143d89589cc85d58e3a1eadcb914c15a6f |
| **R+C, flat** | `analog/wired_tx/generated/fast/wtx_ser8d.rc.spice` (copy of `scratch/wired_tx/s13/ser8d/rcx/wtx_ser8d.rc.spice`) | `rc.py`: Magic 8.3.678 of the analog image, `flatten`, `extract do resistance`, `extresist tolerance 10`, supplies ignored, `ext2spice extresist on`; recipe of `scratch/lo-ap4/rcx.py` | 6f5e2b3f05098a841a42a8d675bcd440d240a5f8a6868026eb84620dba8cef52 |

R+C extraction worked at the first attempt (the digital-image Magic 8.3.623 is recorded as crashing in extresist by the pads pilot
and the LO flow, so it was not tried there). Facts about the R+C netlist:
- 1560 resistors, 13863 capacitors, 2493 device lines + 39 diodes; the device multiset (model, w, l, ...) is identical to the flat
  C-only netlist (checked by script); subcircuit name `wtx_ser8d`, port order = `ser8d_macro.PORTS`; internal nets are named
  `XP6.Q` (dot), not `XP6/Q`.
- extresist wrote resistor networks for 114 of 1176 nets (those above its tolerance): D0..D39, SERQ, QK0, QK1, QRST, LDA, QD, DC,
  the hop clocks Q6, Q7 and Q1, and 64 register-internal nets. **PH*, F*, B*, Q0, Q2..Q5 have no extracted R** (lumped, as in the C-only netlist).
- VDD / VSS / substrate are not resisted (as in the LO recipe): no supply IR drop in this netlist.
- Known property of extresist (read in `analog/timing/lcvco/run_qvco_ext.py`): a poly gate contacted at one end is lumped as its
  full end-to-end R; that file divides gate-feeding R > 50 ohm by 3. Not applied here; the netlist is as Magic wrote it.
- Smoke test only (`smoke.py`): both the R+C and the C-only netlist load in ngspice (analog image, typical) and give the same operating
  point (all PH low, SERQ high: I(VDD) 11.2255 / 11.2256 mA, F0 = F7 = 3.3 V). **No transient / functional simulation was run by me.**

## 6. Changes to generators (not committed)

- `analog/wired_tx/ser8d_macro.py`: `ROWS` replaced by `rows()` (derived from `HOPS`, 1 or 2 hops per stream); `build_top()` passes
  `over_cell=True`, `em=dict(track_first=PH)`, `net_space` (0.02 um on PH, F, Q, hop data nets). `HOPS`, `top_instances()`, `top_spice()` untouched.
- `analog/wired_tx/serq4_macro.py`: `build_le(..., **gen_kw)` passes further options to `le.generate` (default none = unchanged for the other callers).
- Nothing outside `analog/wired_tx` and `scratch/wired_tx` was touched. `analog/timing/layout_engine.py` only read.
- `generated/fast/wtx_ser8d.*` overwritten by the generator (`.gds` and `.ext.spice` are git-ignored; `.rc.spice` is new and untracked).
  The s12 artefacts (GDS, ext, lvs, pins, check) are saved in `scratch/wired_tx/s13/ser8d/prev/`.

## 7. Reproduce

```
cd projects/programmable_transceiver_platform/analog/wired_tx
OMP_NUM_THREADS=1 python3 ser8d_macro.py                      # build -> generated/fast/wtx_ser8d.* (8 s)
cd ../../../../scratch/wired_tx/s13/ser8d
OMP_NUM_THREADS=1 python3 verify.py v                         # DRC, LVS, 4 negative controls, KLayout DRC -> v/verify.json
python3 ctab.py v/wtx_ser8d.flatc.spice ctab_final.json       # capacitance table
OMP_NUM_THREADS=1 python3 rc.py ../../../../projects/programmable_transceiver_platform/analog/wired_tx/generated/fast/wtx_ser8d.gds rcx
cp rcx/wtx_ser8d.rc.spice ../../../../projects/programmable_transceiver_platform/analog/wired_tx/generated/fast/
OMP_NUM_THREADS=1 python3 smoke.py                            # ngspice load / op
OMP_NUM_THREADS=1 python3 levers.py > levers.txt              # lever table (no Magic)
```
All docker jobs ran one at a time with `--cpus 1` except the generator's own Magic / Netgen calls (`layout_engine.docker_magic`, `--cpus 3`, 8 s in total).

## 8. sha256

| file | sha256 |
|---|---|
| `generated/fast/wtx_ser8d.gds` (verified GDS = `v/verify.json` gds_sha256 5fda2b2eaa94...) | 5fda2b2eaa94eba97d847106d51220727bf28d1623305e5bb5b8ccd8292595d2 |
| `generated/fast/wtx_ser8d.ext.spice` | 730de14a1da3a85156a96eb1bd30258b3b0f51ed236154056b95ff95a7943ecc |
| `generated/fast/wtx_ser8d.rc.spice` | 6f5e2b3f05098a841a42a8d675bcd440d240a5f8a6868026eb84620dba8cef52 |
| `generated/fast/wtx_ser8d.lvs.spice` (identical to the read-back `v/wtx_ser8d.lvs.spice`) | 3eda209dfe429814a6ac3c040750b145de12d9480c0ff72cfc99d302fc2ab12a |
| `generated/fast/wtx_ser8d.spice` | a59cdc1cb02a8310d75096a0e268779ae7c3b5baff9ec22ca887036bf67edf8c |
| `generated/fast/wtx_ser8d.mag` | 7405d678d6d69e17555fb649a093f83d543ee6822b446739aa638a155f10d2a7 |
| `generated/fast/wtx_ser8d.pins.json` | 829feabb940e020aed0ebd0364f1757324d8f7a5ffc5a1ca97512c431979a52a |
| `prev/wtx_ser8d.gds` (s12 build) | fe3f3b34fc48e10747fdee69371ed6eb5f6905f04c1b5ec2859df8d2b5f32f45 |

## 9. Not done / limits

- No simulation of the new hop plan with the new extraction (smoke test only). Timing margins are the owner's bench.
- KLayout run is exactly the call of the s12 review (`tools.klayout_drc` = `sak-drc.sh -k`, analog image). I did not check which rule tables
  that wrapper includes; no separate KLayout antenna run was made. Antenna is covered only by the engine's own diode planner.
- Pins stay on the top edge only (engine); F / PH pins are not gathered towards a 291-um mux window.
- Q hop clocks are unequal by the plan (table above); Q1 could be shortened by moving the final hop of stream 3 under P1 at the cost of a
  long R3_0 data wire. Not done.
