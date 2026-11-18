# wtx_mux8 revision 3 layout (+ wtx8_aux): report of the layout sub-agent, 2026-11-18

Generator: `analog/wired_tx/wtx_mux8_layout.py` (one file; `mux8_layout.py`, `mux8_layout2.py`, `mux8.py` and `scratch/wired_tx/s12` were read, not edited, not imported).  Reference: flat `wtx_mux8.netlist()` as on disk at the time of the final build (with the 05:45 UTC change of `CHANGES.txt`: detector inverters on PH k, EXTF / EXTFB).  Nothing committed.

Everything in sections 1-5 was RUN by me on the final GDS unless a line says "read" or "not done".

## 1. Outline and area

| | revision 2 (`s12/layout/out2`, read) | revision 3 |
|---|---|---|
| outline | 291.0 x 148.34 um | **324.6 x 163.44 um** |
| area | 43167 um2 | **53053 um2** (+22.9 %) |
| slice (8 identical instances `wtx_mx_slice`) | 34.5 x 125.2 | 34.5 x 138.3 (same width: bus length unchanged) |
| left block | cap 10.5 um wide | leak column 4.8 + control rows 36 = 40.8 um wide |
| right of the last slice | 4.5 um (half VSS strap) | 7.8 um: the two AVG resistors (guard-ringed PCells) under the strap |
| load clusters | 23.14 um high | 25.14 um high (+1 um RL pad for via cuts, +1 um TOP plate, see EM) |
| free top corners (beside the clusters) | 2 x 97 x 23 um | 138.55 x 23.14 (left), 86.35 x 23.14 um (right)  ; the left one is crossed by the two header-gate feeds (Metal2, 0.4-1.6 um above the slices) and by the aux cell's three Metal4 tap wires |

Where the growth comes from: slice height +13.1 um (new NMOS-only trim strip 10.1 um under the gate row for the 4-bit trim (switches 1.3 / 2.6 / 5.2 / 10.4 um, MOS caps 3 / 6 / 12 / 24 x 1.0 um), +3 tracks in the `in` row (ENM / OVP / OVN / EXTFB run through), +2 tracks in the preM row (TGM / ENMI / EXTM run through), -1 track in the gate row); left block +30.3 um (run detector: pump switch chains, 8 MOS caps, 8 leak devices 0.3 / 50 um, sense inverters, RUN logic; enable logic ENMI / ENQI / TGM / EXTF / EXTM ...); right +3.3 um.

Floorplan (bottom = phase / stream edge, top = pad edge):
```
 +--- free corner ----+-- MAIN loads --+-- POST loads --+---- free corner ----+
 | L | control rows   | slice x 8 (phases 0 7 1 6 2 5 3 4)                 | R |
 +---+----------------+----------------------------------------------------+---+
 L = leak devices (4 diffusion lines under two poly plates on VDD), R = AVG_N / AVG_P resistors (heads under the bus ends)
 slice rows from the bottom: trim strip (NMOS only) / gate (POST stream gating + detector inverters DA, DB at the PH pin) /
   in (I0 = NAND(PH, EXTFB), I0b, I1, AOI21 U, V) / preM / preQ / stack with the four Metal5 buses
```

## 2. Checks on the final GDS

GDS: `scratch/wired_tx/s13/mux3/out/wtx_mux8.gds` = `analog/wired_tx/generated/fast/wtx_mux8.gds`, sha256:2071b74f41e9eadf2fd68b5d50355627baf944cb0431b8db16c03acc232f53e6, written by the analog image's Magic with `cif ostyle gdsii` (spec/block-deliverables.md, GDS export rule).  All lines below: that file copied into the fresh directory `mux3/verify`, `gds read`, DRC and extraction in separate Magic sessions (digital image), Netgen with the PDK setup (device parameters compared).

| check | result |
|---|---|
| Magic DRC `drc(full)` | **0** |
| KLayout DRC (`sak-drc.sh -k`, same file) | **0** (ran: True) |
| LVS vs flat `wtx_mux8.netlist()` | **Final result: Circuits match uniquely.**  Number of devices: 894 |Number of devices: 894; Number of nets: 492 |Number of nets: 492; property errors: 0 |
| negative control: one finger of XMPM_3 on MAIN_P instead of MAIN_N | FAILS as required: Final result: Top level cell failed pin matching. |
| negative control: F2 / F3 swapped at the AOI21 U of slices 2 and 3 | FAILS as required: Final result: Top level cell failed pin matching. |
| negative control: one finger of I1 of slice 0 10 % wider | FAILS as required: Final result: Circuits match uniquely. / Property errors were found. |
| negative control: TR5_0 / TR5_1 swapped at their switches | FAILS as required: Final result: Top level cell failed pin matching. |
| antenna (review L3): Magic `antennacheck` after extraction of the read-back GDS | ran: True, violations: **0** (log `out/wtx_mux8-antenna.txt`) |
| port order of the extracted netlists | C netlist = `wtx_mux8.PORTS`: True; R+C netlist: True |

Not run: a separate KLayout antenna deck (I found no call for it in the wired_tx flow; `sak-drc.sh -k` reported no ANT rule).  All gate-only input pins (PH, F, TR, ENM, ENP, POL, EN_MAIN, EN_POST, EXT, OVP, OVN) are covered by the Magic check above.

## 3. Wiring capacitance (flat C netlist of the read-back GDS, ground + coupling, no device C)

| net | revision 2 (read) | revision 3 | change | largest partners (revision 3) |
|---|---|---|---|---|
| MAIN_P | 109.0 fF | **108.8 fF** | -0.2 | slice S nodes 32.8, VSS 29.9, POST_P 15.4, MAIN_N 11.5, POST_N 9.6 |
| MAIN_N | 98.1 fF | **100.0 fF** | +1.9 | VSS 37.2, slice S nodes 30.6, MAIN_P 11.5, other 11.3, POST_P 4.8 |
| POST_P | 117.4 fF | **118.8 fF** | +1.4 | VSS 38.3, slice S nodes 28.5, POST_N 23.8, MAIN_P 15.4, other 7.1 |
| POST_N | 122.8 fF | **122.2 fF** | -0.6 | VSS 47.5, slice S nodes 28.3, POST_P 23.8, MAIN_P 9.6, other 8.4 |

Against revision 2: MAIN_P -0.2, MAIN_N +1.9, POST_P +1.4, POST_N -0.6 fF, although the metal is now sized for 26 mA instead of 20 mA (section 4): the buses are tapered (2.5 um at the ends, up to 4.55 um beside the taps, widened away from the complement), the MAIN cluster is centred, and the drain columns carry wide Metal2 only on the half where the current leaves.  **Miss of "must not grow": MAIN_N +1.9 fF, POST_P +1.4 fF.**  Included in MAIN_P / MAIN_N: the AVG resistor head, via stack and 0.6 um bus finger (3.0 um for MAIN_N, 6.5 um for MAIN_P; unequal by 3.5 um of 0.6 um Metal5 because the two resistors cannot share an x), and the two 8.2 um Metal2 stubs to the tap landing (section 6; +0.2 / +0.5 fF).

Per slice, min / max over the eight slices (fF):

| net | revision 2 (read) | revision 3 | note |
|---|---|---|---|
| X | 25.35 / 25.76 | 26.39 / 26.86 |  |
| XTM | 17.67 / 17.82 | 19.82 / 19.97 | XT of the MAIN bank |
| XTQ | 17.41 / 17.72 | 16.92 / 17.25 | XT of the POST bank |
| APM | 27.02 / 27.46 | 26.62 / 27.08 |  |
| ANM | 27.93 / 28.56 | 27.93 / 28.64 |  |
| APQ | 23.12 / 23.29 | 22.33 / 22.5 |  |
| ANQ | 20.17 / 20.39 | 19.99 / 20.28 |  |
| BM | 35.64 / 37.25 | 36.99 / 38.67 | B of the MAIN bank (ring wire, 2 slice pitches) |
| BQ | 34.02 / 35.79 | 33.19 / 35.06 |  |
| Y | 7.75 / 7.76 | 14.76 / 15.57 | +7 fF: one Metal3 column down to the trim strip |
| Z | 8.6 / 8.6 | 10.28 / 10.28 |  |
| EM | 8.7 / 8.9 | 9.23 / 9.38 |  |
| EQ | 8.67 / 8.78 | 8.76 / 8.81 |  |
| SM | 17.71 / 17.99 | 17.61 / 18.0 |  |
| SQ | 17.67 / 17.91 | 17.67 / 17.95 |  |
| UP | 23.88 / 28.31 | 24.4 / 29.09 |  |
| VP | 25.66 / 28.94 | 26.73 / 30.17 |  |
| PH | - | 10.85 / 11.01 | new label (pin column to DA and I0) |
| F | - | 11.51 / 12.39 |  |
| FB | - | 11.25 / 11.67 |  |
| XE | - | 40.41 / 57.81 | new: detector wire, full block length, equal Metal4 length for all |
| XD | - | 41.73 / 54.75 | new: same |

Other nets (fF): AVG_P 1.9, AVG_N 1.5, RUN 29.0, ENM 101.2, ENP 77.5, OVP 84.7, OVN 85.4, ENMI 94.9, header gates ENBM 49.8 / ENBQ 55.7, pump nodes DA0..3 5.1 / 5.3 / 5.5 / 5.9, DN0..3 11.4 / 13.3 / 15.4 / 15.7.

XE k / XD k carry 40-58 fF of wire (the schematic bench assumes 4 fF) on 0.5 / 1.0 um inverters: see QUESTIONS.md, item 1.

## 4. Electromigration

`wtx_mux8_layout.em_table(report, i_bank)`; `python3 wtx_mux8_layout.py em <mA>` prints it for another current without a rebuild.  Table for **26.0 mA** per bank (provisional bound).  Per-slice rows use the DC average i_bank / 8 (normal operation: 1/8 duty; EXT mode: all eight in parallel) and STATIC data (all current in one leg / one RL).  Limits: Metal1-4 2.09 mA/um, Metal5 4.5 mA/um, 0.58 mA per via cut, 85 C.

| row | mA | um or cuts | mA/um or mA/cut | limit | margin |
|---|---|---|---|---|---|
| drain column, half where it leaves (Metal1 0.23 + Metal2 UPW) | 1.625 | 0.93 | 1.75 | 2.09 | 16.4 % |
| drain column, far half (Metal1 0.23 + Metal2 UPN) | 0.812 | 0.63 | 1.29 | 2.09 | 38.3 % |
| drain column -> bus via stack (per level) | 1.625 | 4 | 0.406 | 0.58 | 30.0 % |
| drain stub to an upper bus (Metal4) | 1.625 | 0.9 | 1.81 | 2.09 | 13.6 % |
| S column (Metal1 0.23; static data: half of the slice current crosses the S bar) | 0.406 | 0.23 | 1.77 | 2.09 | 15.5 % |
| S bar (Metal1) | 1.625 | 1.2 | 1.35 | 2.09 | 35.2 % |
| stack VSS column above its Metal2 (Metal1 0.4) | 0.534 | 0.4 | 1.33 | 2.09 | 36.1 % |
| stack VSS column at the foot (Metal1 0.4 + Metal2 0.8) | 0.812 | 1.2 | 0.68 | 2.09 | 67.6 % |
| stack VSS rail per slice, two banks, to the two boundary straps (Metal1 + Metal2) | 3.705 | 4.8 | 0.77 | 2.09 | 63.1 % |
| VSS strap via stack on the stack rail (two banks of two slices + 3 mA logic) | 9.5 | 48 | 0.198 | 0.58 | 65.9 % |
| VSS Metal5 strap (two banks + 3 mA logic estimate) | 9.5 | 9.0 | 1.06 | 4.5 | 76.5 % |
| MAIN_N bus, worst segment (4/8 of the bank, Metal5) | 13.0 | 3.65 | 3.56 | 4.5 | 20.9 % |
| MAIN_N bus -> RL strap (Metal3 + Metal4) | 26.0 | 16.0 | 1.62 | 2.09 | 22.2 % |
| MAIN_N strap -> bus Via4 | 26.0 | 90 | 0.289 | 0.58 | 50.2 % |
| MAIN_P bus, worst segment (5/8 of the bank, Metal5) | 16.25 | 4.55 | 3.57 | 4.5 | 20.6 % |
| MAIN_P bus -> RL strap (Metal3 + Metal4) | 26.0 | 16.0 | 1.62 | 2.09 | 22.2 % |
| MAIN_P strap -> bus Via4 | 26.0 | 96 | 0.271 | 0.58 | 53.3 % |
| POST_P bus, worst segment (5/8 of the bank, Metal5) | 16.25 | 4.55 | 3.57 | 4.5 | 20.6 % |
| POST_P bus -> RL strap (Metal3 + Metal4) | 26.0 | 16.0 | 1.62 | 2.09 | 22.2 % |
| POST_P strap -> bus Via4 | 26.0 | 120 | 0.217 | 0.58 | 62.6 % |
| POST_N bus, worst segment (5/8 of the bank, Metal5) | 16.25 | 4.55 | 3.57 | 4.5 | 20.6 % |
| POST_N bus -> RL strap (Metal3 + Metal4) | 26.0 | 16.0 | 1.62 | 2.09 | 22.2 % |
| POST_N strap -> bus Via4 | 26.0 | 88 | 0.295 | 0.58 | 49.1 % |
| RL output pad Via2 / Via3 (per level) | 26.0 | 60 | 0.433 | 0.58 | 25.3 % |
| RL output pad Via1 | 26.0 | 72 | 0.361 | 0.58 | 37.7 % |
| RL heads (Metal1 + Metal2 tongue, one RL carries the bank: static data) | 26.0 | 19.74 | 1.32 | 2.09 | 37.0 % |
| TOP plate M, lateral (static data: one RL feeds the whole RCM width; Metal1-4) | 18.259 | 13.39 | 1.36 | 2.09 | 34.8 % |
| TOP plate Q, lateral (static data: one RL feeds the whole RCM width; Metal1-4) | 15.977 | 13.39 | 1.19 | 2.09 | 42.9 % |
| RCM heads / TOP2 plate (Metal1 + Metal2) | 26.0 | 79.74 | 0.33 | 2.09 | 84.4 % |
| header column (Metal1 + Metal2) | 1.04 | 1.2 | 0.87 | 2.09 | 58.5 % |
| header VDD rail at the top edge (Metal2-5; pins on Metal5) | 26.0 | 38.6 | 0.67 | 4.5 | 85.0 % |
| logic VDD Metal5 strap per slice (~3 mA estimate, not from simulation) | 3.0 | 5.0 | 0.6 | 4.5 | 86.7 % |
| logic rails (Metal1 + Metal2, ~1.5 mA per rail and slice estimate, two directions) | 0.75 | 1.2 | 0.62 | 2.09 | 70.1 % |

Worst row: drain stub to an upper bus (Metal4) (13.6 %); the table reaches zero margin at 30.1 mA per bank.  Rows that failed at 26 mA with the revision-2 geometry and were fixed: drain column (Metal2 0.6 -> 0.7 um on the leaving half, Metal1 counted in parallel), drain stub (0.8 -> 0.9 um), stack VSS column (Metal2 to 3 um up the finger), bus -> RL strap (6 -> 8 um wide, two layers), bus beside the taps (3.5 -> up to 4.55 um), RL pad vias (pad 1 um longer), and the TOP plate: with static data one RL feeds the whole 40 um RCM head, 70 % of the bank current runs sideways through the plate (about 2.3 mA/um in revision 2 at 20 mA by my reading of its generator; not in its table); it is now Metal1-4 and 1 um higher.  Not in the metal table: the poly resistors themselves (RL: bank current through 10 um of ppolyf_u); logic currents are estimates.

## 5. Extracted netlists

* C only, flat, same style as `out2/wtx_mux8.ext.spice`: `generated/fast/wtx_mux8.ext.spice` (sha256:d23f014d7968a7c82a8ee4b8bdf0108b151553d3147622e7d7b44403d7e3bfe3); 880 nfet + 810 pfet fingers, 8 resistors; from the GDS read back (hierarchical extraction, `ext2spice hierarchy off`, `cthresh 0`).
* R + C, flat: `generated/fast/wtx_mux8.rc.spice` (sha256:dc2820070bcaff577d744ecbcb331a1fd3089f48a87c94f59e5594e61f0496a8); Magic extresist in the analog image on the flattened read-back GDS (recipe of `s13/ser8d/rc.py`): 2014 resistors on 25 nets (long static / detector nets and the header VDD pieces; the fast nets come back without resistors at every tolerance).  **Then `wtx_mux8_layout.add_wire_r` (documented in its docstring) adds the DRAWN resistance of the speed-critical wires, 108 resistors:** per slice one lumped resistor driver -> receivers on X, XT, AP, AN (both banks) and on the ring wires B (new node `<net>#g`, wiring C split half / half); per output bus one node per slice (`<bus>#<k>`), a Metal5 ladder with the drawn segment widths, the tap node, and the Metal3 || Metal4 strap to the RL / pin.  Lumped values (ohm, Metal1-4 0.09 and Metal5 0.04 ohm/sq from the Magic tech file):

  | wire | ohm |
  |---|---|
  | X driver -> gates (column, tracks) | 13.49 |
  | XTM driver -> gates (column, tracks) | 2.35 |
  | XTQ driver -> gates (column, tracks) | 2.22 |
  | APM driver -> gates (column, tracks) | 13.42 |
  | ANM driver -> gates (column, tracks) | 13.58 |
  | APQ driver -> gates (column, tracks) | 6.08 |
  | ANQ driver -> gates (column, tracks) | 6.24 |
  | BM driver -> gates (column, tracks, ring wire) | 30.16 |
  | BQ driver -> gates (column, tracks, ring wire) | 24.47 |
  | MAIN_N bus: segments between slice centres [0.552, 0.527, 0.44, 0.378, 0.44, 0.527, 0.552]; far ends -> tap [1.52, 1.9]; strap 0.174 | tap at x = 176.15 um |
  | MAIN_P bus: segments between slice centres [0.552, 0.527, 0.403, 0.341, 0.44, 0.527, 0.552]; far ends -> tap [1.08, 2.26]; strap 0.129 | tap at x = 150.15 um |
  | POST_P bus: segments between slice centres [0.552, 0.527, 0.44, 0.341, 0.303, 0.428, 0.552]; far ends -> tap [1.86, 1.28]; strap 0.084 | tap at x = 221.65 um |
  | POST_N bus: segments between slice centres [0.552, 0.527, 0.44, 0.341, 0.403, 0.527, 0.552]; far ends -> tap [1.86, 1.48]; strap 0.039 | tap at x = 202.65 um |
  Poly gate resistance is not added.  The flattened view names the two header VDD rails VDD_uq0 / VDD_uq1; they are merged into VDD by name.
* LVS netlist of the read-back GDS: `generated/fast/wtx_mux8.lvs.spice` (sha256:3f059f4650081f7ffa8f487167acd7e2f95207e7c7860757e579b68889670292).
* Resistor body terminal (review M6), post-process `wtx_mux8_layout.fix_vsubs` (documented in its docstring): in the C netlist the six guard-ring-less ppolyf_u had their body on `XRLPQ/VSUBS`; 6 lines changed, 0 VSUBS left.  Before:
```
X1474 TOPM MAIN_P XRLPQ/VSUBS ppolyf_u r_width=10u r_length=3.4u
X1475 TOP2M TOPM XRLPQ/VSUBS ppolyf_u r_width=40u r_length=0.8u
X1476 TOPM MAIN_N XRLPQ/VSUBS ppolyf_u r_width=10u r_length=3.4u
X1477 TOP2Q TOPQ XRLPQ/VSUBS ppolyf_u r_width=40u r_length=0.8u
X1478 TOPQ POST_P XRLPQ/VSUBS ppolyf_u r_width=10u r_length=3.4u
X1479 TOPQ POST_N XRLPQ/VSUBS ppolyf_u r_width=10u r_length=3.4u
```
after (both AVG resistors are guard-ringed and come out on VSS by themselves):
```
X0 MAIN_N AVG_N VSS ppolyf_u_1k r_width=1u r_length=100u
X369 MAIN_P AVG_P VSS ppolyf_u_1k r_width=1u r_length=100u
X1474 TOPM MAIN_P VSS ppolyf_u r_width=10u r_length=3.4u
X1475 TOP2M TOPM VSS ppolyf_u r_width=40u r_length=0.8u
X1476 TOPM MAIN_N VSS ppolyf_u r_width=10u r_length=3.4u
X1477 TOP2Q TOPQ VSS ppolyf_u r_width=40u r_length=0.8u
X1478 TOPQ POST_P VSS ppolyf_u r_width=10u r_length=3.4u
X1479 TOPQ POST_N VSS ppolyf_u r_width=10u r_length=3.4u
```
  In the R + C netlist (flattened extraction) all eight resistors are on VSS without post-processing:
```
X204 MAIN_N#4 AVG_N VSS ppolyf_u_1k r_width=1u r_length=100u
X245 TOPQ POST_P VSS ppolyf_u r_width=10u r_length=3.4u
X670 TOP2M TOPM VSS ppolyf_u r_width=40u r_length=0.8u
X1045 TOPQ POST_N VSS ppolyf_u r_width=10u r_length=3.4u
X1339 TOP2Q TOPQ VSS ppolyf_u r_width=40u r_length=0.8u
X1456 MAIN_P#4 AVG_P VSS ppolyf_u_1k r_width=1u r_length=100u
X1464 TOPM MAIN_P VSS ppolyf_u r_width=10u r_length=3.4u
X1678 TOPM MAIN_N VSS ppolyf_u r_width=10u r_length=3.4u
```

## 6. wtx8_aux (reworked after the answers to QUESTIONS.md: two parts)

Generator: `analog/wired_tx/wtx8_aux_layout.py` (row compiler of `wtx_mux8_layout.py`, tracks solved automatically; reference `wtx8_top.aux_text()`).  One cell, two parts:

* **side cell** left of the mux, 1 um gap: glue, bias switch, the two DACs: **69.8 x 118.5 um = 8271 um2**, 6 rows (21.45, 17.45, 17.8, 21.8, 17.8, 21.8 um).  All its signal pins are Metal3 on its BOTTOM edge (like the mux), supplies are Metal1 || Metal2 bars on its left (VSS) and right (VDD) edge.
* **tap row** in the mux's free top-left corner beside the MAIN cluster (39.36 x 19.45 um row plus the two guard-ringed 15 kohm loads; box in mux coordinates x 90.61..138.33, y 140.5..160.68 um): TEN gates, tail TT / TTS, skewed inverters TK*, buffers TB*, loads.  The input pair sits between the two MAIN load resistors as before (centre x = 163.15, y = 145.7 um in the mux).  TD1 / TS / TD2 are three Metal4 wires of the same drawn length (65.4 um each, TS between the two), symmetric about the pair: they run as far over the MAIN_N load as over the MAIN_P load (dummy ends).  ATB_NBIAS, ON and TAP_EN come from the side cell on Metal5 / Metal4 across the corner.  TAP_P / TAP_N are Metal3 pads in the row.

For comparison: `layout_engine.generate` on the same netlist gave 112.6 x 424.3 um = 47 789 um2 (DRC 0, LVS unique; discarded).

| check (GDS `generated/fast/wtx8_aux.gds` read back from disk in `mux3/aux/verify`) | result |
|---|---|
| Magic DRC / KLayout DRC | **0 / 0** |
| LVS vs `wtx8_top.aux_text()` | **Final result: Circuits match uniquely.**  Number of devices: 197 |Number of devices: 197; Number of nets: 128 |Number of nets: 128; property errors 0 |
| negative control neg_dac_code_bits_swapped | FAILS as required: Final result: Top level cell failed pin matching. |
| negative control neg_glue_input_moved | FAILS as required: Final result: Top level cell failed pin matching. |
| Magic `antennacheck` | violations 0 |
| mux + aux placed together (`mux3/aux/combo`): Magic DRC / KLayout DRC | **0 / 0**; INP = MAIN_P: True, INN = MAIN_N: True |

**Added load on the outputs with the tap attached** (combined extraction against the mux alone): MAIN_P 108.8 -> 111.6 fF (**+2.8**), MAIN_N 100.0 -> 101.1 fF (**+1.1**), plus one 2 / 0.28 um gate each.  The coupling to the three tap wires is now equal (0.88 fF on MAIN_P, 0.88 fF on MAIN_N).  **The remaining 1.7 fF difference is NOT explained:** the combined extraction reports 2.0 fF more capacitance to substrate / VSS on MAIN_P than the mux-alone extraction and 0.3 fF more on MAIN_N, with a layout that is mirror-symmetric about the pair (stubs, gate pads, taps, wires).  I did not find a geometric cause; it may be an artefact of the deeper hierarchy.  Open item.

Tap nodes (wiring C, aux cell alone): **TD1 11.0 fF, TD2 13.0 fF** (was 37 fF each with the loads in the side cell), TS 15.5 fF.  TD1 / TD2 differ by 2.0 fF: same Metal4 length, but TD2 is the outer wire and its column in the row is longer.  Other nets (fF): ATB_NBIAS 48.4, ATB_PBIAS 71.0, MAIN_BIAS 34.7, POST_BIAS 39.4, EXT 22.4, ENM 4.3, OVP 6.5, OVN 6.3, TAP_P 2.3, TAP_N 2.4.

Extraction: `generated/fast/wtx8_aux.ext.spice` (C only, flat, ports = `wtx8_top.AUX_PORTS`: True), `wtx8_aux.rc.spice` (Magic extresist: 272 resistors on 7 nets), `wtx8_aux.lvs.spice`; pin coordinates in `mux3/aux/pins.json`.  Both loads have their body on VSS:
```
X0 VDD TD1 VSS ppolyf_u_1k r_width=1u r_length=15u
X1 VDD TD2 VSS ppolyf_u_1k r_width=1u r_length=15u
```
The cell has two VDD islands (side cell bar, tap row rail) and two VSS islands, joined by name inside the cell and by metal in `pt_wiredtx8`.  No EM table for this cell.


## 7. Files, hashes, how to reproduce

| file (`analog/wired_tx/generated/fast/`, copies in `scratch/wired_tx/s13/mux3/out` and `mux3/aux/out`) | sha256 |
|---|---|
| wtx_mux8.gds | sha256:80071be158bf17a49f2743a77f6ea13b3f82c9c3bb4a762e9599b0b836bfb38e |
| wtx_mux8.ext.spice | sha256:27fd866876dfd64c659c85d6c6659b2dc7fba1ccf24d6da85718ac5ed652af5c |
| wtx_mux8.lvs.spice | sha256:3f059f4650081f7ffa8f487167acd7e2f95207e7c7860757e579b68889670292 |
| wtx_mux8.rc.spice | sha256:385e5f97437533076b9c240ea2c5ef73b2ce075f9464222a7512043ba40e571b |
| wtx8_aux.gds | sha256:a21516192c667699da4c31ecaa4a9a265bf87126241f84eddedfce34dffefb9f |
| wtx8_aux.ext.spice | sha256:c187bc6f007dc7f41403c83c8c55943389212f509194e2bb97baec5dabd19216 |
| wtx8_aux.lvs.spice | sha256:33fe791a2a226487d0f588d3efbea8e0398b3796deaeca4d04213a75c7085b4f |
| wtx8_aux.rc.spice | sha256:1d3781d8e832c676c24fa6e193e1af67d6ad21116c8b0284024a4b4ddb21da9c |

No GDS added to git, nothing committed.  Raw output: `mux3/build`, `mux3/verify`, `mux3/rc`, `mux3/out/report.json` (all numbers of sections 1-5), `mux3/aux/{build,verify,rc,combo,out}`.

```
cd projects/programmable_transceiver_platform/analog/wired_tx
OMP_NUM_THREADS=1 python3 wtx_mux8_layout.py          # 22 s: build, GDS, checks from disk, netlists, mux3/out/report.json
OMP_NUM_THREADS=1 python3 wtx_mux8_layout.py em 24.3  # EM table for another bank current, no rebuild
OMP_NUM_THREADS=1 python3 wtx8_aux_layout.py          # after the mux (reads its report for the pair position); not timed
python3 ../../../../scratch/wired_tx/s13/mux3/mkreport.py   # this file from the two report.json
```
Each script runs its containers one after the other (one heavy job at a time, `--cpus 1`, `OMP_NUM_THREADS=1`).

## 8. What failed, what was not done, what I changed outside the two generators

* **Area**: the mux grew 23 % (section 1); the control block is 36 um wide because narrower ones did not find all Metal3 columns (28-34 um tried by the generator and failed). Levers, not pulled, sizes are my estimates: hand-packed control rows (about -6 um), detector inverters and pump chains per slice (QUESTIONS.md 1), DAC mirror rows without their unused NMOS half in the aux cell.
* **Output C**: MAIN_N and POST_P are above revision 2 (section 3); with the tap attached MAIN_P +2.8 fF, MAIN_N +1.1 fF, the 1.7 fF difference unexplained (section 6).
* **R + C netlist of the mux**: extresist resists only the long static / detector nets; the drawn resistance of buses, straps and gate-line trunks is added by a post-process (section 5), poly gate resistance is not.
* **wtx8_aux**: no EM table.  The block top `pt_wiredtx8` is reported in `scratch/wired_tx/s13/top/REPORT.md`.
* **Not run**: any circuit simulation (the netlists are untested in `m9.py`; port order and device counts were checked), a KLayout antenna-only deck, fill, an independent review.  The EM logic-current rows are estimates.  `pt_wiredtx8` (top) has no layout: the six control nets from aux to the mux, the supplies of the two cells and the three VDD islands of the mux (logic rails, MAIN header rail, POST header rail: joined only by name, as in revision 2) are the parent's to wire.
* **Failures on the way that changed the flow** (all visible in the generator): the first GDS, written by the digital image's Magic, lost both ppolyf_u_1k on read-back (LVS 892 vs 894 devices, KLayout PP.9 / PRES.1 / PRES.5): the GDS now comes from the analog image as spec/block-deliverables.md requires and the 1k PCells keep their guard ring; an L-shaped tap contact area came back from the GDS with a CO.1 sliver (rail contact strip now stops before the pull-down zone); an extra VDD strap over the control block shorted three nets through its Metal3 pads (removed; found by LVS); the two header-gate feeds crossed (swapped; found by LVS); the revision-2 style EM check missed the sideways current in the TOP plate with static data.
* **Files touched besides the two new generators**: `generated/fast/wtx_mux8.{gds,ext.spice,rc.spice,lvs.spice}`, `generated/fast/wtx8_aux.{gds,ext.spice,rc.spice,lvs.spice}` (new or overwritten), and `generated/fast/wtx_mux8.spice`, which I regenerated twice with `python3 wtx_mux8.py` (it now holds the current revision-3 schematic).  `mux8.py`, `mux8_layout.py`, `mux8_layout2.py`, `wtx_mux8.py`, `wtx8_top.py`, `cells.py`, `scratch/wired_tx/s12` and everything of `wtx_ser8d`: read only.
* Schematic sizes: every device of both netlists was built with the schematic width and length (LVS compares them; the width negative control fails on "property errors"); no substitution was needed, so QUESTIONS.md holds design questions only.

