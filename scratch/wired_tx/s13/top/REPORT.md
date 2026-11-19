# pt_wiredtx8 block top layout, pass 2: state 2026-11-19

Generator `analog/wired_tx/pt_wiredtx8_layout.py`. Reference: `wtx8_top.netlist()`, which includes `XPB wtx8_phbuf`, the PS nets, FROT = 2, and `XDEC wtx8_decap` with n = 686 (the generator wrote that value). Children come from `generated/fast`:
- `wtx_ser8d` was read only and not rebuilt.
- `wtx_mux8` and `wtx8_aux` were rebuilt today (see section 8).

I ran every check below on the final GDS read back from disk. Nothing is committed.

## 1. Outline, area, seam

| part | um | um2 |
|---|---|---|
| **bounding box** | **744.12 x 400.56** | **298065** (0.298 mm2; pass 1: 350674) |
| used outline (L shape, the top right corner is not part of the block) | (0,0) (744.12,0) (744.12,236.12) (598.7,236.12) (598.7,400.56) (0,400.56) | **274152** |
| free top right corner | x 598.7..744.12, y 236.12..400.56 | 23913 |
| wtx_ser8d (bottom) | 744.12 x 197.68 | 147098 |
| **seam** (all top-level signal wiring, rails, phase buffers) | **744.12 x 38.44** (y 197.68..236.12; pass 1: 110.14) | 28604 |
| wtx_mux8, origin (242.1, 236.12) | 324.6 x 164.44 | 53377 |
| wtx8_aux side cell, origin (171.3, 236.12) | as the aux report | |
| decap: 14 rows x 49 = 686 NMOS 8 / 2 um, box x 28.0..169.3, y 237.12..390.56 | | 10976 of gate |
| supply bars (Metal5), y 214.02..400.56 | VSS 0.5..12.5 and 584.2..598.2; VDD 14.0..26.0 and 568.7..582.7 | |

The seam is 38.44 um, inside the 40 um limit:

```
 y um
 236.12          mux / aux bottom edge (their signal pins: Metal3)
 229.52..234.52  VDD rail, Metal4 || Metal2, 5 um
 221.42..230.12  phase buffers wtx8_phbuf (cell 9.92 x 8.7 um): cell VDD rail on the VDD rail's lower edge, cell VSS rail in the VSS rail
 214.02..228.52  VSS rail, Metal4 || Metal2, 14.5 um (over each buffer the Metal2 stops 8.0 um up; Metal4 is continuous)
 213.02          PH0..PH7 pin pads (Metal5 1.2 um), straight under the mux PH pins
 203.18..        PS sub-zone: PS k Metal4 tracks with a VSS track between neighbours (5 PS tracks, 6 VSS)
 198.68          zone B: Metal4 F0..F7, SERQ (5 tracks, 0.84 um); in the same height, 18 Metal2 tracks (0.72 um) for the control nets
 197.68          top edge of wtx_ser8d
```

What changed from the WIP layout to reach this:
- The buffers moved out of zone B into the rail band.
- The Metal2 rail is cut only above each buffer cell.
- The control ports now leave on the left or the right edge, whichever gives fewer Metal2 tracks (31 down to 18). The Metal2 tracks pass under the mux.
- The gap above ser8d went from 2.4 to 1.0 um.

## 2. Checks on the final GDS

GDS: `generated/fast/pt_wiredtx8.gds` (sha256:9414183aeff017d913069bf08c9dd7638116edda477dbe7f410ac4f9f1eade82). It was exported with the analog image and read back in the fresh directory `top/verify`.

| check | result |
|---|---|
| Magic DRC `drc(full)` | **0** |
| KLayout DRC (`sak-drc.sh -k`, gf180mcuD) | **0** |
| Netgen LVS vs `wtx8_top.netlist()` (hierarchical; phase buffers and decap flattened at top level) | **Final result: Circuits match uniquely.** |
| negative control: PH0 / PH1 swapped at the mux (XMUX line) | FAILS as required (Top level cell failed pin matching) |
| negative control: stream rotation off by one (FROT 3) | FAILS as required (Netlists do not match) |
| negative control: OVP / OVN swapped at the mux | FAILS as required (Netlists do not match) |
| negative control: buffer outputs PS0 / PS1 swapped at ser8d (XSER line) | FAILS as required (Netlists do not match) |
| Magic `antennacheck` | violations **0** |
| flat C netlist: port order = `wtx8_top.PORTS` | True; 1662 child substrate nodes moved to VSS by `fix_vsubs`, none left |

The negative controls are changed reference netlists, not changed layouts. No separate KLayout antenna deck was run.

## 3. Phase nets: what the ring sees

Each PH k has the same geometry:
- the block pin: a Metal5 pad under the mux PH k pin;
- a 10.5 um Metal3 stub up to the mux pin, drawn 5.24 ohm (Metal3 0.4 um, 0.225 ohm/um);
- the first buffer inverter (2 / 4 um) on that stub.

| | PH0..PH7 |
|---|---|
| wire C, top-level wiring alone | 6.8..7.0 fF (spread 0.2 fF) |
| wire C, whole block (incl. the mux's internal phase wiring) | 17.6..17.8 fF (pass 1: 113.8..119.0 fF) |
| gate load added by the buffer | 2 + 4 um of gate, about 13 fF (2.2 fF/um estimate, not simulated) |

So the ring sees about 31 fF per phase plus the mux's own PH gates. Pass 1 was about 115 fF of wire alone.

## 4. PS (buffer to ser8d), F and SERQ nets

Each PS k runs as follows:
- from the buffer output, Metal3 down to its own Metal4 track;
- along the track (VSS track on both sides) to the ser8d PH pin;
- Metal5 down to that pin.

The PS nets are not equalised: the ser8d phase pins are spread over 650 um.

| k | PS Metal4 (um) | PS drawn R (ohm) | PS wire C top / block (fF) | F track (um) | F drawn R (ohm) | F wire C top / block (fF) |
|---|---|---|---|---|---|---|
| 0 | 199.9 | 50.4 | 43.4 / 66.4 | 262.1 | 59.0 | 36.6 / 49.7 |
| 1 | 167.2 | 42.8 | 37.0 / 56.6 | 26.5 | 6.0 | 11.6 / 33.4 |
| 2 | 146.2 | 37.8 | 33.1 / 54.2 | 224.2 | 50.4 | 39.2 / 62.3 |
| 3 | 124.0 | 33.1 | 30.0 / 51.9 | 303.9 | 68.4 | 50.8 / 71.6 |
| 4 | 63.7 | 18.8 | 18.8 / 40.9 | 234.2 | 52.7 | 43.5 / 65.1 |
| 5 | 98.9 | 27.2 | 24.8 / 47.0 | 86.1 | 19.4 | 17.4 / 36.9 |
| 6 | 259.1 | 63.0 | 52.5 / 74.6 | 42.6 | 9.6 | 12.4 / 32.7 |
| 7 | 419.3 | 99.7 | 80.3 / 103.3 | 270.1 | 60.8 | 41.4 / 60.9 |

SERQ: 183.4 um, 41.3 ohm.

The PS load ranges from 41 to 103 fF on a 6 / 12 um inverter. By my estimate that is roughly 0.1 ns of skew between the ser8d phases. This has not been simulated: the probe run (STATUS item 2) has to confirm the stream timing with the buffers in.

## 5. Block pins (port names for the bench = `wtx8_top.PORTS`, 124 ports, in this order)

```
PH0..PH7  D0..D39  WORD_CLK40  SER_EN IDLE IDLE_MODE WTX_EXT DX POST_POL EN_MAIN EN_POST ISLAND_OFF TAP_EN IBIAS
MAIN_CODE0..7  POST_CODE0..7  TR0_0..TR7_3 (TRk_b, k = slice, b = 0..3)
MAIN_P MAIN_N POST_P POST_N MAIN_BIAS POST_BIAS TAP_P TAP_N TX_RUN WTX_EXT_DATA ATB_NBIAS ATB_PBIAS ATB_AVGP ATB_AVGN VDD VSS
```

Pin positions (all are in `out/report.json` -> `pins`, as layer, x, y):
- **D0..D39, WORD_CLK40:** Metal5 on the bottom edge (y 0.5). These are ser8d's own port trunks continued down (`serm5/dcols.json`).
- **Left edge, Metal2, y 198.7..211:** SER_EN, IDLE, IDLE_MODE, WTX_EXT, DX, EN_MAIN, EN_POST, ISLAND_OFF, MAIN_CODE1..4, MAIN_CODE7, POST_CODE0..3, WTX_EXT_DATA.
- **Right edge, Metal2, same height band:** POST_POL, TX_RUN, TAP_EN, IBIAS, MAIN_CODE0, MAIN_CODE5, MAIN_CODE6, POST_CODE4..7, ATB_NBIAS, ATB_PBIAS, ATB_AVGP, ATB_AVGN.
- **Top edge (pad edge):**
  - MAIN_P / MAIN_N / POST_P / POST_N: the mux's Metal5 risers (x 392.25 / 418.25 / 444.75 / 463.75).
  - MAIN_BIAS / POST_BIAS: Metal4 at x 232.8 / 191.6, over the aux cell.
- **Left edge, Metal4:** TAP_P / TAP_N at y 389.42 / 390.32, above the decap rows.
- **PH0..PH7:** Metal5 pads at y 213.02, under the mux PH pins (x 285.25 / 354.25 / 423.25 / 492.25 / 526.75 / 457.75 / 388.75 / 319.75). The ring has to come over the mux or through the seam to reach them.
- **VDD / VSS:** the Metal5 bars (section 1), labelled 20 um below the top edge.
- **TR0_0..TR7_3: Metal3 pads inside the block** at y 199.28, straight under the mux trim pins (x 287.7..542.2). **They are not on the block boundary.** See section 9.

## 6. Supplies and electromigration

The rails are Metal4 || Metal2. The VSS rail is 14.5 um and the VDD rail 5 um.

What connects to them:
- ser8d's Metal5 straps run up into the rails (17 VSS, 16 VDD). A strap that would run into a phase pin pad, or under the other net's bar, stays inside ser8d.
- 11 + 11 Metal2-Metal4 stitches tie the two rail layers together.
- The mux's 9 VSS straps come down as 2.5 um necks. Its 8 logic VDD straps go straight into the VDD rail.
- Each header is fed from the VDD bars by a Metal5 strap along the top edge. Inside the mux the bank now passes under the output risers on Metal1-4 (mux EM rows: 32.9 / 39.3 %). This closes pass 1's open item about the header middle segment.

Currents:
- the two banks: 26 mA each;
- ser8d and all logic: 30 mA, of which 3 mA is the mux's logic.

The rail currents come from a 1-D model of each rail (`rail_currents`): the bars hold the rail at 0 V, and the loads sit at their strap positions.

| row | mA | um / cuts | mA/um / mA/cut | limit | margin |
|---|---|---|---|---|---|
| VSS bar left (Metal5) | 26.35 | 12 | 2.2 | 4.5 | 51.2 % |
| VSS bar right of the mux (Metal5) | 54.06 | 14 | 3.86 | 4.5 | 14.2 % |
| VDD bar left (Metal5; header bank + rail share) | 37.32 | 12 | 3.11 | 4.5 | 30.9 % |
| VDD bar right of the mux (Metal5; header bank + rail share) | 44.68 | 14 | 3.19 | 4.5 | 29.1 % |
| VSS rail (Metal4 + Metal2), largest current along it | 47.71 | 29 | 1.65 | 2.09 | 21.3 % |
| VDD rail (Metal4 + Metal2), largest current along it | 11.93 | 10 | 1.19 | 2.09 | 42.9 % |
| **VSS rail over a phase buffer (Metal4 14.5 + Metal2 8.0)** | 41.6 | 22.5 | 1.85 | 2.09 | **11.5 %** (worst) |
| VSS rail -> bar Via2-4 (per bar) | 54.06 | 650 | 0.083 | 0.58 | 85.7 % |
| VDD rail -> bar Via2-4 (per bar) | 18.68 | 200 | 0.093 | 0.58 | 83.9 % |
| header strap bar -> header (Metal5, whole bank) | 26.0 | 7.5 | 3.47 | 4.5 | 23.0 % |
| mux VSS neck (Metal5; two banks of two slices + 3 mA, as the mux table) | 9.5 | 2.5 | 3.8 | 4.5 | 15.6 % |
| mux VSS neck -> rail Via4 | 9.5 | 104 | 0.091 | 0.58 | 84.3 % |
| mux logic VDD strap (Metal5, 3 mA bound) | 3.0 | 5.0 | 0.6 | 4.5 | 86.7 % |
| ser8d VSS / VDD strap (Metal5 2 um) | 1.76 / 1.88 | 2.0 | 0.88 / 0.94 | 4.5 | 80.4 / 79.2 % |
| ser8d strap -> rail Via4 | 1.88 | 24 | 0.078 | 0.58 | 86.5 % |

The model puts the VSS current at the left : right bars at 26 : 54 mA. The right bars sit beside the mux and take most of its current, which is why they are 14 um wide.

## 7. Netlists

- **`generated/fast/pt_wiredtx8.ext.spice`** (sha256:23fa691a1809c05269d1c95a32bb1436c9a23704e355040eec561d7e392b0838):
  - one flat C-only netlist of the whole block;
  - port order `wtx8_top.PORTS`;
  - 2994 nfet, 2227 pfet, 10 poly resistors.
- **`generated/fast/pt_wiredtx8.rc.spice`** (sha256:093fdbec947efecca97ba4b588b2f94904efa215adcabb3aaa6764de7d9a9be3): the same netlist plus drawn resistance, added in two steps by `pt_wiredtx8_layout.add_rc`.
  1. **Mux-internal (new in pass 2):** `wtx_mux8_layout.add_wire_r` runs on the `XMUX/` nodes with the mux's own report. It adds 108 resistors:
     - the gate-line trunks X, XTM, XTQ, APM, ANM, APQ, ANQ of all eight slices (13.5 / 2.4 / 2.2 / 13.4 / 13.6 / 6.1 / 6.2 ohm);
     - the ring wires BM / BQ (30.2 / 24.5 ohm);
     - the Metal5 ladders of the four output buses, with a node per slice (`MAIN_P#k` ...), the tap node, and the strap to the pin.

     `add_rc` stops with an error if any trunk node is missing from the block netlist. All 72 are present.
  2. **Top level (`add_top_r`, 31 resistors):**
     - PH k: pin -> `PHk#m` (mux side), 5.24 ohm.
     - PS k: buffer -> `PSk#s` (ser8d side), with the resistances of section 4.
     - F k, SERQ: -> `#s` (ser8d side).
     - VDD / VSS: one lumped resistor per child, in ohm: VSS mux 0.342 / ser 0.406 / aux 1.489; VDD mux 0.849 / ser 0.962 / aux 1.317. These are coarse.

  Connectivity check on the file: every split node has devices on it, except the four bus tap nodes `#t`, which carry only resistors (as intended). It has not been simulated.
- **`generated/fast/pt_wiredtx8.lvs.spice`** (sha256:c1be2d3e6779ccead3218b6fc9bc64c682cc6bea92e6cc879583ac7b4f135ed9): hierarchical LVS netlist of the read-back GDS.
- **`generated/fast/pt_wiredtx8.spice`:** the intended netlist, regenerated with `python3 wtx8_top.py` (decap n = 686).

## 8. Children rebuilt today

| child | what was run | result |
|---|---|---|
| `wtx_mux8` (WIP header feed under the risers, now verified) | `wtx_mux8_layout.py` | 324.6 x 164.44 um. Magic DRC 0, KLayout 0, LVS unique, 4 / 4 negative controls fail, antenna 0. EM worst: drain stub 13.6 %. Bus wire C 100.6 / 109.4 / 119.3 / 122.8 fF |
| `wtx8_aux` | `wtx8_aux_layout.py` | Magic DRC 0, KLayout 0, LVS unique, 2 / 2 negative controls fail |

## 9. Open items and what did not converge

- **Trim bits TR0_0..TR7_3 are not on the block boundary.**
  - They are Metal3 pads at the bottom of the seam under the mux, so nothing outside can reach them without crossing ser8d or the seam.
  - The mux has its trim pins on its bottom edge, so any route to an edge needs about 16-33 more horizontal tracks in the seam. I measured this with all 32 trims as Metal2 edge ports: 33 tracks, seam 47.9 um.
  - The real fix is a mux change: bring its trim pins out on its right side into the free corner.
  - This is your decision: (a) a seam of about 48 um with the trims on the edges, (b) the mux change, or (c) leave them as they are.
- **The PH pins are inside the block**, under the mux, as the brief asked: "at the pin row". The ring has to be routed to them.
- **PS loads are unequal** (41..103 fF); estimated skew is about 0.1 ns. The probe run has to confirm it.
- **Not done:** any simulation, Magic extresist on the block, a KLayout antenna deck, fill, and an independent review.
- **ser8d inputs:** I did not touch `wtx_ser8d` or its running re-verification (`s13/ser8d/v`). `serm5/dcols.json`, the trunk positions, was taken from the 06:01 GDS, which is still the published one. If ser8d changes, `dcols.json` has to be remade from a flattened ser8d (`serm5/f.tcl` + `m5.json`).

## 10. Reproduce

```
cd projects/programmable_transceiver_platform/analog/wired_tx
OMP_NUM_THREADS=1 python3 wtx_mux8_layout.py            # mux, verify, generated/fast
OMP_NUM_THREADS=1 python3 wtx8_aux_layout.py            # needs the mux report
OMP_NUM_THREADS=1 python3 pt_wiredtx8_layout.py         # about 40 s; writes DECAP n into wtx8_top.py if it differs
OMP_NUM_THREADS=1 python3 pt_wiredtx8_layout.py build   # layout + DRC / LVS in top/build only
python3 wtx8_top.py                                     # intended netlist generated/fast/pt_wiredtx8.spice
```

GDS hashes change with every run because of the time stamp.

The top generator reads:
- the mux / aux build directories (`s13/mux3/build`, the aux build directory);
- `s13/top/serm5/dcols.json`.

Keep those.
