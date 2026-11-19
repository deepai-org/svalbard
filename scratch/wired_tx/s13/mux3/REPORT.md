# wtx_mux8 revision 3 layout (+ wtx8_aux): state 2026-11-19 (session 14)

Generator: `analog/wired_tx/wtx_mux8_layout.py`; reference: flat `wtx_mux8.netlist()` (schematic `analog/wired_tx/wtx_mux8.py`).  Session-14 changes, all in the current GDS:
* **run detector input stage with hysteresis** per phase (DH1 PH -> XH, keeper DK XS -> XH, DH2 XH -> XS, then DA XS -> XE, DB XE -> XD; DC thresholds VL 0.47-1.12 V, VH 1.63-2.33 V over tt / ss / ff / sf / fs, 0 / 85 C, 2.97 / 3.63 V, `s14/ilk/hyst.log`): a phase at mid level, or a stalled ring with a small residual swing, leaves XE / XD static and no pump moves charge (was: XE / XD near mid level, pumps leaking DN up, RUN stuck high at ff).
* **I0 k = NAND(PH k, RUNI)**, RUNI = buffered RUN (inverter GXFI now on RUNB; it was !EXTF): with RUN = 0 every X k is held high (slices off) and the phase-input chain I0 / I0b is out of its crowbar region whatever the phase levels (was 5.4-8.1 mA at mid level).  TGM = ENMI & RUNI (same truth table as before wherever ENMI = 1).
* **trim pins TR k_b on the RIGHT edge** (Metal4), 32 tracks over the gate / in rows; outline unchanged.
Interlock rows on the extracted netlist: `s14/ilk/` (section 9).  Nothing committed.

Everything in sections 1-5 was RUN on the final GDS read back from disk.

## 1. Outline and area

| | revision 2 (`s12/layout/out2`, read) | revision 3 |
|---|---|---|
| outline | 291.0 x 148.34 um | **324.6 x 164.44 um** |
| area | 43167 um2 | **53377 um2** (+23.7 %) |
| slice (8 identical instances `wtx_mx_slice`) | 34.5 x 125.2 | 34.5 x 138.3 (same width: bus length unchanged) |
| left block | cap 10.5 um wide | leak column 4.8 + control rows 36 = 40.8 um wide |
| right of the last slice | 4.5 um (half VSS strap) | 7.8 um: the two AVG resistors (guard-ringed PCells) under the strap |
| load clusters | 23.14 um high | 25.14 um high (+1 um RL pad for via cuts, +1 um TOP plate, see EM) |
| free top corners (beside the clusters) | 2 x 97 x 23 um | 138.55 x 24.14 (left), 86.35 x 24.14 um (right); the left one is crossed by the two header-gate feeds (Metal2, 0.4-1.6 um above the slices) and holds the aux cell's tap row |
| gate row (detector input stage + POST stream gating) | | 31.2 um of the 34.5 um slice width (was 27.5 with two detector inverters) |

Where the growth against revision 2 comes from: slice height +13.1 um (NMOS-only trim strip 10.1 um under the gate row for the 4-bit trim (switches 1.3 / 2.6 / 5.2 / 10.4 um, MOS caps 3 / 6 / 12 / 24 x 1.0 um), +3 tracks in the `in` row (ENM / OVP / OVN / RUNI run through), +2 tracks in the preM row (TGM / ENMI / EXTM run through), -1 track in the gate row); left block +30.3 um (run detector: pump switch chains, 8 MOS caps, 8 leak devices 0.3 / 50 um, sense inverters, RUN logic; enable logic ENMI / ENQI / TGM / EXTF / EXTM ...); right +3.3 um; header rail +1 um.  The session-14 detector stage (3 more inverters per phase, 20.8 um2 of gate in all) fits the existing gate row: no area change.

Floorplan (bottom = phase / stream edge, top = pad edge):
```
 +--- free corner ----+-- MAIN loads --+-- POST loads --+---- free corner ----+
 | L | control rows   | slice x 8 (phases 0 7 1 6 2 5 3 4)                 | R |
 +---+----------------+----------------------------------------------------+---+
 L = leak devices (4 diffusion lines under two poly plates on VDD), R = AVG_N / AVG_P resistors (heads under the bus ends)
 slice rows from the bottom: trim strip (NMOS only) / gate (POST stream gating + detector input stage DH1 DK DH2 DA DB at
   the PH pin) / in (I0 = NAND(PH, RUNI), I0b, I1, AOI21 U, V) / preM / preQ / stack with the four Metal5 buses
 pins: PH k, F k, controls, RUN, AVG_P / AVG_N on the bottom edge (Metal3); TR k_b on the right edge (Metal4, y 18.88..42.64,
   pitch 0.72 um, a gap at 23.2..25.36 for the VDD via stacks of the in row); MAIN / POST risers and header VDD on the top edge
```

## 2. Checks on the final GDS

GDS: `scratch/wired_tx/s13/mux3/out/wtx_mux8.gds` = `analog/wired_tx/generated/fast/wtx_mux8.gds`, sha256:e70f6d1995d27ef8228b2f518b1a005a3745ba6d79e2274f837a585cd8359498, written by the analog image's Magic with `cif ostyle gdsii` (spec/block-deliverables.md, GDS export rule).  All lines below: that file copied into the fresh directory `mux3/verify`, `gds read`, DRC and extraction in separate Magic sessions (digital image), Netgen with the PDK setup (device parameters compared).

| check | result |
|---|---|
| Magic DRC `drc(full)` | **0** |
| KLayout DRC (`sak-drc.sh -k`, same file) | **0** (ran: True) |
| LVS vs flat `wtx_mux8.netlist()` | **Final result: Circuits match uniquely.**  Number of devices: 942 / 942; Number of nets: 508 / 508; property errors: 0 |
| negative control: one finger of XMPM_3 on MAIN_P instead of MAIN_N | FAILS as required: Final result: Top level cell failed pin matching. |
| negative control: F2 / F3 swapped at the AOI21 U of slices 2 and 3 | FAILS as required: Final result: Top level cell failed pin matching. |
| negative control: one finger of I1 of slice 0 10 % wider | FAILS as required: Final result: Circuits match uniquely. / Property errors were found. |
| negative control: TR5_0 / TR5_1 swapped at their switches | FAILS as required: Final result: Top level cell failed pin matching. |
| negative control: keeper DK3 of the detector input stage driven from XE3 instead of XS3 | FAILS as required: Final result: Top level cell failed pin matching. |
| antenna (review L3): Magic `antennacheck` after extraction of the read-back GDS | ran: True, violations: **0** (log `out/wtx_mux8-antenna.txt`) |
| port order of the extracted netlists | C netlist = `wtx_mux8.PORTS`: True; R+C netlist: True |

Not run: a separate KLayout antenna deck (I found no call for it in the wired_tx flow; `sak-drc.sh -k` reported no ANT rule).  All gate-only input pins (PH, F, TR, ENM, ENP, POL, EN_MAIN, EN_POST, EXT, OVP, OVN) are covered by the Magic check above.

## 3. Wiring capacitance (flat C netlist of the read-back GDS, ground + coupling, no device C)

| net | revision 2 (read) | revision 3 | change | largest partners (revision 3) |
|---|---|---|---|---|
| MAIN_P | 109.0 fF | **109.4 fF** | +0.4 | slice S nodes 32.8, VSS 29.9, POST_P 15.4, MAIN_N 11.5, POST_N 9.6 |
| MAIN_N | 98.1 fF | **100.6 fF** | +2.5 | VSS 37.2, slice S nodes 30.6, MAIN_P 11.5, other 11.3, POST_P 4.8 |
| POST_P | 117.4 fF | **119.3 fF** | +1.9 | VSS 38.3, slice S nodes 28.5, POST_N 23.8, MAIN_P 15.4, other 7.1 |
| POST_N | 122.8 fF | **122.8 fF** | 0.0 | VSS 47.5, slice S nodes 28.3, POST_P 23.8, MAIN_P 9.6, other 8.4 |

Against revision 2: MAIN_P +0.4, MAIN_N +2.5, POST_P +1.9, POST_N 0.0 fF (unchanged by the session-14 changes), although the metal is now sized for 26 mA instead of 20 mA (section 4): the buses are tapered (2.5 um at the ends, up to 4.55 um beside the taps, widened away from the complement), the MAIN cluster is centred, and the drain columns carry wide Metal2 only on the half where the current leaves.  **Miss of "must not grow": MAIN_P +0.4, MAIN_N +2.5 fF, POST_P +1.9 fF.**  Included in MAIN_P / MAIN_N: the AVG resistor head, via stack and 0.6 um bus finger (3.0 um for MAIN_N, 6.5 um for MAIN_P; unequal by 3.5 um of 0.6 um Metal5 because the two resistors cannot share an x), and the two 8.2 um Metal2 stubs to the tap landing (section 6; +0.2 / +0.5 fF).

Per slice, min / max over the eight slices (fF):

| net | revision 2 (read) | revision 3 | note |
|---|---|---|---|
| X | 25.35 / 25.76 | 26.5 / 27.35 |  |
| XTM | 17.67 / 17.82 | 19.87 / 19.99 | XT of the MAIN bank |
| XTQ | 17.41 / 17.72 | 16.93 / 17.26 | XT of the POST bank |
| APM | 27.02 / 27.46 | 26.56 / 27.03 |  |
| ANM | 27.93 / 28.56 | 27.71 / 28.29 |  |
| APQ | 23.12 / 23.29 | 22.33 / 22.51 |  |
| ANQ | 20.17 / 20.39 | 19.97 / 20.29 |  |
| BM | 35.64 / 37.25 | 37.05 / 38.74 | B of the MAIN bank (ring wire, 2 slice pitches) |
| BQ | 34.02 / 35.79 | 33.21 / 35.08 |  |
| Y | 7.75 / 7.76 | 16.94 / 17.76 | +9 fF: one Metal3 column down to the trim strip, the TR columns / tracks beside it |
| Z | 8.6 / 8.6 | 10.34 / 10.57 |  |
| EM | 8.7 / 8.9 | 9.23 / 9.39 |  |
| EQ | 8.67 / 8.78 | 8.76 / 8.81 |  |
| SM | 17.71 / 17.99 | 17.61 / 18.0 |  |
| SQ | 17.67 / 17.91 | 17.67 / 17.95 |  |
| UP | 23.88 / 28.31 | 27.32 / 31.76 |  |
| VP | 25.66 / 28.94 | 26.64 / 30.8 |  |
| PH | - | 10.95 / 11.79 | pin column to the detector input stage DH1 and I0 |
| F | - | 12.33 / 13.06 |  |
| FB | - | 12.33 / 13.04 |  |
| XE | - | 42.21 / 59.62 | new: detector wire, full block length, equal Metal4 length for all |
| XD | - | 47.21 / 56.14 | new: same |

Other nets (fF): TOPM 21.7, TOPQ 23.1, TOP2M 61.9, TOP2Q 61.9, AVG_P 1.9, AVG_N 1.5, RUN 29.2, ENM 104.2, ENP 79.6, OVP 86.9, OVN 88.4, ENMI 95.2, ENBM 49.9, ENBQ 55.8, DA0 5.1, DN0 11.4, DA1 5.3, DN1 13.3, DA2 5.5, DN2 15.4, DA3 5.9, DN3 15.7.  Trim nets TR k_b: Metal4 24.6..279.8 um from the slice to the right edge (static).

XE k / XD k carry 42-60 fF of wire (the schematic bench assumes 4 fF) on 0.5 / 1.0 um inverters; the interlock rows of section 9 use the extracted netlist.

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

* C only, flat, same style as `out2/wtx_mux8.ext.spice`: `generated/fast/wtx_mux8.ext.spice` (sha256:fb0decc59c3ebf2b807ffc9a44d93cd562cb4e69a854ae261bfb8f4b8548beaf); 904 nfet + 834 pfet fingers, 8 resistors; from the GDS read back (hierarchical extraction, `ext2spice hierarchy off`, `cthresh 0`).
* R + C, flat: `generated/fast/wtx_mux8.rc.spice` (sha256:625d01556774c4564c4ad60d7bcb7ad6fb534ef89c15296d89a08f25c659024f); Magic extresist in the analog image on the flattened read-back GDS (recipe of `s13/ser8d/rc.py`): 2328 resistors on 40 nets (long static / detector / trim nets and the header VDD pieces; the fast nets come back without resistors at every tolerance; the drawn lumps below are optimistic against a full extresist, `s14/rcov/RCOV.md`).  **Then `wtx_mux8_layout.add_wire_r` (documented in its docstring) adds the DRAWN resistance of the speed-critical wires, 108 resistors:** per slice one lumped resistor driver -> receivers on X, XT, AP, AN (both banks) and on the ring wires B (new node `<net>#g`, wiring C split half / half); per output bus one node per slice (`<bus>#<k>`), a Metal5 ladder with the drawn segment widths, the tap node, and the Metal3 || Metal4 strap to the RL / pin.  Lumped values (ohm, Metal1-4 0.09 and Metal5 0.04 ohm/sq from the Magic tech file):

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
* LVS netlist of the read-back GDS: `generated/fast/wtx_mux8.lvs.spice` (sha256:dd14fcc6c4c0645cc9b561d520d5cfa8311ccf4e6f4485a3cdb437662c9f8547).
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
| wtx_mux8.gds | sha256:e70f6d1995d27ef8228b2f518b1a005a3745ba6d79e2274f837a585cd8359498 |
| wtx_mux8.ext.spice | sha256:fb0decc59c3ebf2b807ffc9a44d93cd562cb4e69a854ae261bfb8f4b8548beaf |
| wtx_mux8.lvs.spice | sha256:dd14fcc6c4c0645cc9b561d520d5cfa8311ccf4e6f4485a3cdb437662c9f8547 |
| wtx_mux8.rc.spice | sha256:625d01556774c4564c4ad60d7bcb7ad6fb534ef89c15296d89a08f25c659024f |
| wtx8_aux.gds | sha256:e9ea2e3846bff33c4b9814ac55a26c3ba1d05108d3176858c957869c73b59bf8 |
| wtx8_aux.ext.spice | sha256:2b49df9a7bbe5d7171371454958f948f6fb7afef28cf68f2d32a53f452040a96 |
| wtx8_aux.lvs.spice | sha256:9b0a91e47edb7d0e683c527cb34b27f51d25052dff95503245e70def610f3550 |
| wtx8_aux.rc.spice | sha256:f51cb8fefe734ac23e6322e51a01219268a7239ec70ef4c7f1ada19ddce03862 |

No GDS added to git, nothing committed.  Raw output: `mux3/build`, `mux3/verify`, `mux3/rc`, `mux3/out/report.json` (all numbers of sections 1-5), `mux3/aux/{build,verify,rc,combo,out}`.

```
cd projects/programmable_transceiver_platform/analog/wired_tx
OMP_NUM_THREADS=1 python3 wtx_mux8_layout.py          # about 2 min: build, GDS, checks from disk, netlists, mux3/out/report.json, copy to generated/fast
OMP_NUM_THREADS=1 python3 wtx_mux8_layout.py em 24.3  # EM table for another bank current, no rebuild
OMP_NUM_THREADS=1 python3 wtx8_aux_layout.py          # after the mux (reads its report for the pair position); not rerun in session 14
python3 wtx_mux8.py                                   # schematic generated/fast/wtx_mux8.spice
```
This file is kept by hand (`mkreport.py` writes the session-13 text and is out of date).
Each script runs its containers one after the other (one heavy job at a time, `--cpus 1`, `OMP_NUM_THREADS=1`).

## 8. Open items, not done

* **Area**: the control block is 36 um wide because narrower ones did not find all Metal3 columns (28-34 um tried by the generator).  Levers, not pulled (my estimates): hand-packed control rows (about -6 um), DAC mirror rows without their unused NMOS half in the aux cell.
* **Output C**: MAIN_P / MAIN_N / POST_P are above revision 2 (section 3); with the tap attached MAIN_P +2.8 fF, MAIN_N +1.1 fF, the 1.7 fF difference unexplained (section 6).
* **R + C netlist**: extresist resists only the long static / detector / trim nets; the drawn resistance of buses, straps and gate-line trunks is added by a post-process (section 5) and is optimistic (`s14/rcov/RCOV.md`); poly gate resistance is not added.
* **wtx8_aux**: no EM table; not rebuilt in session 14.
* **Not run**: a KLayout antenna-only deck, fill, an independent review.  The EM logic-current rows are estimates.
* The three VDD islands of the mux (logic rails, MAIN header rail, POST header rail) are joined only by name in the cell; `pt_wiredtx8` joins them (`s13/top/REPORT.md`).
* Every device is built with the schematic width and length (LVS compares them; the width negative control fails on property errors).

## 9. Stopped-ring interlock on the extracted netlist (session 14)

Limits: `s14/ilk/LIMITS.md` (declared before the runs).  Bench `s14/ilk/ilk.py`, queue `s14/ilk/q2b.sh` (first row: n_stop_ssp, 500 ns), raw results `s14/ilk/q2.log` and `s14/ilk/runs/*/result.json`; netlist = `mux3/out/wtx_mux8.rc.spice` (this layout).

Limits (summary): every stopped / stalled state RUN < 0.3 V and bank current < 0.1 mA within 100 us; ramp: bank never above the single-path Metal1 limit and < 0.1 mA after the ramp; running ring 240 / 420 MHz at ff 0 C 3.63 V and ss pess. 85 C 2.97 V: RUN high, gate-level eye within 5 mV of the pre-fix extracted mux; negative control (detector output forced high) must keep the bank current.  Times from the stop (22 ns; stuck rows: stuck from t = 0, times from 22 ns).  "bank" = sum of the header currents (0 V sense sources); total = the whole mux supply current, which bounds the bank current from above.

| row (extracted R+C) | corner | RUN end (V) | RUN low after (ns) | bank < 0.1 mA after (ns) | bank end (mA) | total end (mA) | result |
|---|---|---|---|---|---|---|---|
| stop 11110000 | ssp | 0.00 | 228 | 232 | 0.000 | 0.001 | PASS |
| stop 11110000 | ff | 0.00 | 187 | 190 | 0.000 | 0.002 | PASS |
| all 0 | ssp | 0.00 | 232 | 236 | 0.000 | 0.002 | PASS |
| all 1 | ssp | 0.00 | 219 | 223 | 0.000 | 0.002 | PASS |
| all phases 1.35 V | ssp | 0.00 | 228 | 232 | 0.000 | 0.31 | PASS |
| all phases 1.35 V | ff | 0.00 | 190 | 193 | 0.000 | 0.73 | PASS (pre-fix: RUN 3.34 V, 8.1 mA) |
| 1.35 V + 0.3 V pp residual at 300 MHz | ssp | 0.00 | 235 | 239 | 0.000 | 0.32 | PASS |
| 1.35 V + 0.3 V pp residual at 300 MHz | ff | 0.00 | 189 | 191 | 0.000 | 0.74 | PASS |
| PH3 stuck high, others running | ssp | 0.00 | 230 | 234 | 0.000 | 1.16 (detector inputs still toggling) | PASS |
| PH5 stuck low, others running | ff | 0.00 | 190 | 192 | 0.000 | 1.41 (same) | PASS |
| supply ramp 0 -> 3.63 V in 12 us, 11110000, enables high | ffhot | 0.00 | never high | bank max 0.000 over the whole ramp | 0.000 | 0.001 | PASS |
| **negative control**: same netlist, the four devices gated by RUNB (DRI, GXFI) tied to VSS -> RUN / RUNI forced high; stop 11110000 | ssp | 3.15 | never | never | **9.79** | 9.80 | FAILS as required |

Before RUN falls (190-240 ns) the stopped bank keeps up to 9.8-26 mA (largest: PH5 stuck low at ff, 26.0 mA), never above the running bank current of the same corner's design value (26 mA per bank, EM table section 4); after RUN = 0 no slice path carries current.

Running ring (ideal phases, PRBS7, no pad, 0.45 pF per output; pre-fix = `s13/ilk/mux_rc.spice`):

| corner | f ring | RUN min (V) new / pre-fix | gate amplitude pp (V) new / pre-fix | gate eye height (V) new / pre-fix | errors new / pre-fix | result |
|---|---|---|---|---|---|---|
| ff 0 C 3.63 V | 240 MHz | 3.59 / 3.59 | 0.187 / 0.187 | 0.0167 / 0.0169 (-0.2 mV) | 0 / 0 of 144 | PASS |
| ff 0 C 3.63 V | 420 MHz | 3.58 / 3.58 | 0.227 / 0.226 | 0.0203 / 0.0231 (-2.8 mV) | 0 / 0 of 168 | PASS |
| ss pess. 85 C 2.97 V | 240 MHz | 2.94 / 2.94 | 0.167 / 0.168 | closed / closed | 1 / 1 of 144 | RUN PASS; eye not measurable on this bench |
| ss pess. 85 C 2.97 V | 420 MHz | 2.93 / 2.93 | 0.191 / 0.196 | closed / closed | 4 / 3 of 168 | RUN PASS; eye not measurable on this bench |

The gate-level differential amplitude of the extracted mux on this no-pad bench is only 0.17-0.23 V pp for the pre-fix netlist too, so the gate eye is a weak measure (closed at ss for both); the comparison new / pre-fix agrees within 5 mV in amplitude everywhere and in eye height where it opens.  The real-chain eye (pad, channel) with the new netlist is not run.

Schematic checks (`s14/ilk/q1b.log`, same bench, wiring-C stand-ins): mid level / residual swing at ffcold, ff, ssp, sshot all RUN = 0 in 147-275 ns with bank 0 and total 0.24-0.89 mA; running 420 MHz sshot and 240 MHz ffcold RUN high, 0 errors; start-up without initial condition RUN rises at both; stop ff, stuck high / low, ramp: pass.

Pre-fix (`s13/ilk/mux_rc.spice`, same bench, current split by gate net, 100 ns after the stop at 1.35 V): ssp 5.39 mA = I0 NAND 2.26 + I0b inverter 2.83 + detector input inverters 0.29, bank 0.0004 mA, RUN still high at 120 ns (falls at 247 ns); ff 8.12 mA = I0 4.63 + I0b 2.87 + detector 0.58 (+0.03), bank 0.000 mA, RUN stays 3.34 V (XE0 2.74 V, XD0 0 V, DN 1.9-2.3 V: XE sits just below the rail, so the XE-gated pump PMOS leak through and beat the 0.3 / 50 um leak devices).  The 6 mA of the coordinator's run (streams still toggling) is therefore phase-input crowbar, not slice current: the slices are off because X = 0 or 3.3 V forces B or XT off.  Per slice 0.28-0.58 mA (I0) + 0.35 mA (I0b), through 4-8 um devices; no slice output path carries more than 0.0004 mA, far under the Metal1 limit.

