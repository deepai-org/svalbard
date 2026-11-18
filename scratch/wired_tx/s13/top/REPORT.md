# pt_wiredtx8 block top layout: report of the layout sub-agent, 2026-11-18

Generator `analog/wired_tx/pt_wiredtx8_layout.py`; reference `wtx8_top.netlist()` (FROT = 2, with the new `wtx8_decap` instance).  Children as published in `generated/fast`: `wtx_ser8d` (not rebuilt, read), `wtx_mux8`, `wtx8_aux` (both rebuilt today, see `../mux3/REPORT.md`).  Everything below was run by me on the final GDS unless marked.  Nothing committed.

## 1. Outline and area

| part | um | um2 |
|---|---|---|
| **bounding box** | **744.12 x 471.26** | **350674** (0.351 mm2) |
| wtx_ser8d (bottom) | 744.12 x 197.68 | 147098 |
| seam (all top-level signal wiring and the supply rails) | 744.12 x 110.14 | 81957 |
| wtx_mux8, origin (242.1, 307.82) | 324.6 x 163.44 | 53053 |
| wtx8_aux side cell, origin (171.3, 307.82); its tap row lies inside the mux outline | 69.8 x 118.5 | 8271 |
| decap rows, box x 28.0..169.3, y 308.82..461.26 | | 21540 |
| four supply edge bars (above the seam) | 12 wide each | 9650 |
| **keep-free rectangle** x 568.7..716.12, y 308.32..462.06 | 147.42 x 153.74 | **22664** (0.0227 mm2) |
| used = bounding box - keep-free | | 328010 |

The keep-free rectangle (right of the mux) has no shape of this block on any layer; above it runs the POST header strap (Metal5, y 463.56..471.06), below it the seam.  About 0.008 mm2 of gaps around the mux / aux / decap are neither used nor offered.

**The seam is 110.1 um high (0.082 mm2): stated as a problem.**  From the bottom: zone B 21 Metal4 tracks (40 D pins of ser8d sit on its TOP edge and leave sideways, 8 F, SERQ, word clock), zone S 17 tracks (8 phase tracks + VSS between), the phase pins, zone M 33 tracks (two legs per phase, every leg between VSS tracks), zone T 36 um of supply rails with 45 Metal2 tracks under them (32 trim bits, 16 codes, statics).  Levers, not pulled (sizes are my estimates): ser8d data pins on its bottom edge (-18 um), phase nets without equal-C padding or with one VSS track per pair (-25 um), trim bits brought out on the mux side.

```
 y um
  471.26  top edge = pad edge: MAIN_P / MAIN_N / POST_N / POST_P risers of the mux (Metal5), header VDD straps (Metal5, 7.5 um)
  307.82  bottom edge of mux and aux side cell (their signal pins: Metal3)
  296.22  VDD rail Metal4 10 um            | zone T: Metal2 tracks of the nets that only have pins above
  270.22  VSS rail Metal4 25 um            |
  239.52  zone M: phase nets pin -> mux, out-and-back legs, 0.9 um pitch
  237.32  PH0..PH7 pins: Metal5 pads 1.2 um, x = 412 + 4 k
  218.92  zone S: phase nets pin -> ser8d, 1.0 um pitch
  200.08  zone B: Metal4 tracks, 0.84 um pitch
  197.68  top edge of wtx_ser8d (pins: Metal3-5 stacks)
```

Vertical wires in the seam: Metal3 from pins above, Metal5 from ser8d pins below (they cannot meet).  The mux is centred on the phase pin row (mux origin x 242.1; block centre 372).

## 2. Checks on the final GDS

`generated/fast/pt_wiredtx8.gds` (sha256:576e2161264f472c3b4f32169ed336a398c4d77bfb7df9945c0bff3570e615ac), analog-image export, read back in the fresh directory `top/verify`.

| check | result |
|---|---|
| Magic DRC `drc(full)` | **0** |
| KLayout DRC (`sak-drc.sh -k`) | **0** |
| LVS vs `wtx8_top.netlist()` (hierarchical, device parameters compared) | **Final result: Circuits match uniquely.**  top level: Number of devices: 4 |Number of devices: 4; Number of nets: 139 |Number of nets: 139; property errors 0 |
| negative control: PH0 / PH1 swapped at the mux | FAILS as required: Final result: Netlists do not match. |
| negative control: stream rotation off by one (FROT 3) | FAILS as required: Final result: Netlists do not match. |
| negative control: OVP / OVN swapped at the mux | FAILS as required: Final result: Netlists do not match. |
| Magic `antennacheck` (whole block, after extraction) | ran: True, violations **0** |
| flat C netlist: port order = `wtx8_top.PORTS` | True |

The three negative controls are changed REFERENCE netlists (the XMUX line), not changed layouts.  No separate KLayout antenna deck was run.

## 3. Phase nets PH0..PH7

Each net: Metal5 pin pad in the seam; pin -> mux on two Metal4 legs (out on one track, back on the next but one, Metal3 jumper) so that the drawn resistance pin -> mux pin is the same for all; pin -> ser8d on one Metal4 track lengthened by a dummy end to 331.0 um for all.  Every Metal4 leg lies between two VSS tracks (tied to each ser8d VSS strap they cross).

| net | wire C, top-level wiring alone (fF) | of which to VSS | to VDD | to each neighbour phase (largest two) | whole block, wire C (fF) | of which ser8d-internal | R pin -> mux (ohm, drawn) | R pin -> ser8d (ohm) | Metal4 to mux / to ser8d / dummy (um) |
|---|---|---|---|---|---|---|---|---|---|
| PH0 | **82.0** | 74.46 | 3.45 | PH1 0.73, PH2 0.1 | 116.7 | 8.24 | 44.46 | 78.15 | 128.8 / 331.0 / 0.0 |
| PH1 | **82.1** | 74.81 | 2.12 | PH2 1.05, PH0 0.73 | 116.8 | 8.35 | 44.45 | 56.91 | 130.9 / 331.0 / 94.4 |
| PH2 | **81.8** | 74.48 | 2.09 | PH1 1.05, PH3 0.95 | 113.8 | 8.37 | 44.46 | 37.56 | 133.0 / 331.0 / 180.4 |
| PH3 | **82.8** | 74.31 | 3.11 | PH4 0.99, PH2 0.95 | 118.5 | 8.31 | 44.45 | 17.94 | 135.1 / 331.0 / 267.6 |
| PH4 | **82.4** | 75.35 | 2.22 | PH3 0.99, PH5 0.93 | 115.4 | 8.42 | 44.46 | 9.84 | 137.4 / 331.0 / 303.6 |
| PH5 | **82.5** | 75.14 | 2.0 | PH6 1.09, PH4 0.93 | 115.8 | 9.73 | 44.45 | 30.0 | 139.5 / 331.0 / 214.0 |
| PH6 | **82.9** | 74.56 | 3.22 | PH7 1.14, PH5 1.09 | 116.1 | 8.46 | 44.47 | 49.62 | 141.6 / 331.0 / 126.8 |
| PH7 | **83.8** | 75.44 | 4.12 | PH6 1.14, PH1 0.2 | 119.0 | 9.42 | 44.46 | 69.24 | 143.8 / 331.0 / 39.6 |

* Top-level wiring: 81.8..83.8 fF, **spread 2.0 fF** (target 3).  Measured on the top-level shapes alone (children removed, same extraction).
* Whole block (top wiring + mux internal 10.9 fF each + ser8d internal + coupling to the children): 113.8..119.0 fF, spread 5.2 fF; the difference to the line above is mostly ser8d's own phase wiring, which differs by 5 fF between phases (12.3..17.3 fF to ser8d nets) and is not mine to change.
* Drawn resistance pin -> mux pin: 44.45..44.47 ohm, spread 0.04 % (limit 5 %); computed from lengths and sheet resistance (Metal3 / Metal4 0.4 um: 0.225 ohm/um, Metal5 0.44 um: 0.091 ohm/um), vias not counted (same number on every net).
* **Against the ring owner's 60 fF per phase in total: the wiring alone is 114..119 fF, about twice the whole budget before any gate is counted.**  331 um to ser8d (its phase pins are spread over 650 um) + about 135 um to the mux, each with a VSS track on both sides (0.18 fF/um).  What would cut it: no equal-C dummy ends (-40 % of the ser8d branch on average, then unequal), a wider gap to the shields (costs seam height), ser8d phase pins nearer its centre, or a buffer per phase at the pin.
* The pins are in the seam (Metal5 pads), not on a block edge: the ring has to come over the block.  They sit under the mux (x 412..440), 233 um below the top edge where the MAIN / POST risers end.

## 4. Stream nets F0..F7 and the other internal nets

| net | Metal4 track (um) | drawn R (ohm) | wire C top-level alone / whole block (fF) |
|---|---|---|---|
| F0 | 262.1 | 58.97 | 43.5 / 55.1 |
| F1 | 26.5 | 5.96 | 17.6 / 38.8 |
| F2 | 224.2 | 50.44 | 41.2 / 59.0 |
| F3 | 303.9 | 68.38 | 61.7 / 83.7 |
| F4 | 234.2 | 52.69 | 46.9 / 65.8 |
| F5 | 86.1 | 19.37 | 23.4 / 42.5 |
| F6 | 42.6 | 9.58 | 19.7 / 40.4 |
| F7 | 270.1 | 60.77 | 53.8 / 74.1 |

**Not equal** (26..304 um): one straight track per stream from the ser8d pin to the mux slice that takes it (FROT = 2); I did not pad them.  They lie in zone B, below the lowest VSS track of zone S.  SERQ, ENM (to the mux ENM and ENP pins), EXT, OVP, OVN, ENMAIN_G, ENPOST_G run between aux and mux / ser8d on single tracks.

## 5. Block pins

`top/out/report.json` -> `pins` has every pin (layer, x, y).  45 on metal2 left; 22 on metal2 right; 23 on metal4 left; 20 on metal4 right; 12 on metal5 inside.
* left / right edge at seam height (track ends; Metal4 y 200.1..218.9, Metal2 y 270.2..307.8): D0..D39 (nearest side), WORD_CLK40, the 32 trim bits (left for the slices on the left half, right otherwise), codes, statics, IBIAS, MAIN_BIAS, POST_BIAS, ATB_*, TX_RUN, WTX_EXT_DATA.  MAIN_BIAS / POST_BIAS therefore leave on the left edge, not towards the pad: say if they should go to the top.
* TAP_P / TAP_N: Metal4 on the left edge at y = 458.82 / 459.72 (12 um below the top edge).
* PH0..PH7: Metal5 pads in the seam (section 3).  MAIN_P / MAIN_N / POST_P / POST_N: the mux risers on the top edge; nothing of the top level runs over them, the header straps end 1.0 um beside the outer risers (they must reach the header rail segments there), the bridge between the two headers is 8 um from the nearest riser.
* VDD / VSS: Metal5 bars 12 um wide on both sides, x [0.5, 12.5] / [14.0, 26.0] (left) and [718.12, 730.12] / [731.62, 743.62] (right), y 270.22..471.26 (they start above ser8d: its PH315 and F7 pins rise under the right-hand bars).

## 6. Supplies and electromigration

One VDD and one VSS net by metal: Metal4 rails across the block in the seam (VSS 25 um, VDD 10 um) into the four edge bars; ser8d's Metal5 straps continued up into the rails (18 of 19 pairs: the outermost strap on each side lies under the other net's bar and stays inside ser8d); the mux's nine VSS straps come down as 2.5 um necks placed clear of ser8d's VDD straps, its eight logic VDD straps go straight into the VDD rail; the two header rails (the mux's VDD islands 2 and 3) are fed by Metal5 straps along the top edge from the VDD bars and bridged; the aux side cell's bars and the tap row's rails are tied in.

Currents: 2 x 26 mA (banks, DC, static data) + 30 mA (ser8d and logic).

| row | mA | um or cuts | mA/um or mA/cut | limit | margin |
|---|---|---|---|---|---|
| VSS edge bar (Metal5; half of 2 banks + logic per side) | 41.0 | 12.0 | 3.42 | 4.5 | 24.1 % |
| VDD edge bar (Metal5; one header + half of the logic per side) | 41.0 | 12.0 | 3.42 | 4.5 | 24.1 % |
| VSS rail (Metal4), at a bar | 41.0 | 25.0 | 1.64 | 2.09 | 21.5 % |
| VDD rail (Metal4), at a bar | 15.0 | 10.0 | 1.5 | 2.09 | 28.2 % |
| VSS rail -> bar Via4 | 41.0 | 1034 | 0.04 | 0.58 | 93.2 % |
| VDD rail -> bar Via4 | 15.0 | 396 | 0.038 | 0.58 | 93.5 % |
| header strap bar -> MAIN / POST header (Metal5; the whole bank through one strap) | 26.0 | 7.5 | 3.47 | 4.5 | 23.0 % |
| mux VSS strap neck in the rails (Metal5; two banks of two slices + 3 mA logic, as the mux table) | 9.5 | 2.5 | 3.8 | 4.5 | 15.6 % |
| mux VSS neck -> rail Via4 | 9.5 | 188 | 0.051 | 0.58 | 91.3 % |
| mux logic VDD strap (Metal5, ~3 mA estimate) | 3.0 | 5.0 | 0.6 | 4.5 | 86.7 % |
| ser8d VSS strap (Metal5 2 um; 30 mA over 18 straps) | 1.67 | 2.0 | 0.83 | 4.5 | 81.5 % |
| ser8d VDD strap (Metal5 2 um; 30 mA over 18 straps) | 1.67 | 2.0 | 0.83 | 4.5 | 81.5 % |
| ser8d strap -> rail Via4 | 1.67 | 54 | 0.031 | 0.58 | 94.7 % |

Worst: mux VSS strap neck in the rails (Metal5; two banks of two slices + 3 mA logic, as the mux table) (15.6 %).  **Not covered, stated plainly:** each header rail is cut on Metal3-5 by its two output risers; the strap reaches the outer segment only, the middle segment hangs on the rail's own Metal1 + Metal2 under the risers (6 um, 12.5 mA at the limit) while most of the 26 mA (my estimate: about 85 %) has to pass there with static data.  It is clean only if the pad also feeds the mux's top-edge VDD pins (as revision 2 assumed), or if the mux gets Metal3 / Metal4 under the risers (which you ruled out at top level).  Your decision.

## 7. Decoupling

`wtx8_top.py` now has `DECAP = dict(w=8.0, l=2.0, n=637)`, `decap()` and the instance `XDEC VDD VSS wtx8_decap` in `top()` (the subckt text is emitted in front of the top subckt so that existing callers of `top()` keep working).  Layout: 13 rows x 49 fingers = **637 NMOS 8 / 2 um, gate on VDD, source = drain = bulk = VSS, 10192 um2 of gate**, left of the aux cell, strapped by the continued ser8d straps (three VDD / VSS pairs).  By my estimate about 44 pF at 4.3 fF/um2; the value the models give was not simulated.  The right-hand region is left free (section 1) instead of being filled.

## 8. Extracted netlists

* `generated/fast/pt_wiredtx8.ext.spice` (sha256:2df500b787c7f3c0623af71793367155e254a0f7f9ca21cdb7afa614f9893461): ONE flat C-only netlist of the whole block, port order `wtx8_top.PORTS`, 2881 nfet + 2163 pfet + 10 resistors, node names `XSER/...`, `XMUX/...`, `XAUX/...`.  1646 lines had a child substrate node (`.../VSUBS`) and were put on VSS by `fix_vsubs`; none left.  Not tried in `chain13.py`.
* `generated/fast/pt_wiredtx8.rc.spice` (sha256:dbee6d9a09739bb0ed44848b162c5deadd1fc6028cc6538b8d5eaf73a09934e7): the same netlist plus the DRAWN top-level resistance, 30 resistors, by `pt_wiredtx8_layout.add_top_r` (documented in its docstring): PH k split into pin / `#m` (mux side) / `#s` (ser8d side) with the resistances of section 3; F k: ser8d side behind the track resistance of section 4; VDD / VSS: one lumped resistor per child (ohm: {'VSS': {'mux': 0.388, 'ser': 0.446, 'aux': 1.535}, 'VDD': {'mux': 0.849, 'ser': 0.948, 'aux': 1.317}}; rail taken as distributed from both bars, straps in parallel; coarse).  **It does NOT contain the mux-internal bus / trunk resistance of `wtx_mux8.rc.spice`** (different node naming in the flat block netlist) and no Magic extresist was run on the block.
* `generated/fast/pt_wiredtx8.lvs.spice` (sha256:0bb6ffd84abcaa39e5303b447fd79aec195204133ff73360a77f15307dfba4f3): hierarchical LVS netlist of the read-back GDS.

## 9. Reproduce

```
cd projects/programmable_transceiver_platform/analog/wired_tx
OMP_NUM_THREADS=1 python3 wtx_mux8_layout.py        # 25 s
OMP_NUM_THREADS=1 python3 wtx8_aux_layout.py        # needs the mux report
OMP_NUM_THREADS=1 python3 pt_wiredtx8_layout.py     # 40 s; needs both reports and generated/fast/wtx_ser8d_mag; writes DECAP n into wtx8_top.py if it differs
python3 ../../../../scratch/wired_tx/s13/top/mkreport.py
```
GDS hashes change with every run (time stamp): regenerate the reports after a rebuild.

## 10. What failed, what is open

* Open: seam height (section 1); phase wiring C twice the ring budget (3); F nets unequal (4); header middle segments (6); PH pins inside the block; MAIN_BIAS / POST_BIAS on the left edge; the tap's unexplained 1.7 fF MAIN_P / MAIN_N difference (`../mux3/REPORT.md` section 6).
* Not done: any simulation; extresist on the block; KLayout antenna deck; fill; independent review; negative controls as changed layouts.
* On the way: the first decap rows were 9 um wider than computed and ran into the aux cell (415 DRC errors); edge bars first covered the PH315 / F7 risers of ser8d and shorted them to VSS (found by LVS); shield vias on a strap that was not continued left 54 Metal5 islands under minimum area; the output pin labels needed top-level metal to attach.  The first phase routing had the two legs of a net side by side: top-level C spread was 9 fF; with a VSS track between all legs it is 2 fF, at 7 um more seam.
* Files touched: new `pt_wiredtx8_layout.py`; `wtx8_top.py` (DECAP / decap() / top(), as asked); `wtx8_aux_layout.py` and `wtx_mux8_layout.py` (aux rework, `add_wire_r`); `generated/fast/pt_wiredtx8.{gds,ext.spice,rc.spice,lvs.spice}` and the rebuilt mux / aux artefacts.  `wtx_ser8d` and everything outside `analog/wired_tx` and `scratch/wired_tx`: read only.
