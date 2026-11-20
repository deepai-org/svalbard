# pt_wiredtx8 block top layout: state 2026-11-19 (session 14, trim pins on the mux's right side)

Generator `analog/wired_tx/pt_wiredtx8_layout.py`. Reference: `wtx8_top.netlist()`, which includes `XPB wtx8_phbuf`, the PS nets, FROT = 2, and `XDEC wtx8_decap` with n = 686. Children:
- `wtx_ser8d`: read only (generated/fast), not rebuilt.
- `wtx_mux8`: rebuilt in session 14 (interlock detector with hysteresis input stage, I0 gated by RUN, trim pins on its right side; `s13/mux3/REPORT.md`), from `s13/mux3/build`.
- `wtx8_aux`: unchanged (pass-2 build).

Every check below was run on the final GDS read back from disk (`top/verify`). Nothing is committed.

## 1. Outline, area, seam

| part | um | um2 |
|---|---|---|
| **bounding box** | **744.12 x 400.56** | **298065** (0.298 mm2) |
| used outline (L shape, the top right corner is not part of the block) | (0,0) (744.12,0) (744.12,236.12) (598.7,236.12) (598.7,400.56) (0,400.56) | **274152** (unchanged) |
| free top right corner | x 598.7..744.12, y 236.12..400.56 | 23913 |
| wtx_ser8d (bottom) | 744.12 x 197.68 | 147098 |
| **seam** (all top-level signal wiring, rails, phase buffers) | **744.12 x 38.44** (y 197.68..236.12) | 28604 |
| wtx_mux8, origin (242.1, 236.12) | 324.6 x 164.44 | 53377 |
| wtx8_aux side cell, origin (171.3, 236.12) | as the aux report | |
| decap: 14 rows x 49 = 686 NMOS 8 / 2 um, box x 28.0..169.3, y 237.12..390.56 | | 10976 of gate |
| supply bars (Metal5), y 214.02..400.56 | VSS 0.5..12.5 and 584.2..598.2; VDD 14.0..26.0 and 568.7..582.7 | |
| trim wires TR0_0..TR7_3 (Metal4, 0.4 um, y 255.0..278.76, x 566.7..598.7) | from the mux's right edge under the right-hand Metal5 bars to the block edge at the free corner, 32.2 um each | |

The seam is 38.44 um, inside the 40 um limit:

```
 y um
 236.12          mux / aux bottom edge (their signal pins: Metal3; the mux's trim pins are on its right side, not here)
 229.52..234.52  VDD rail, Metal4 || Metal2, 5 um
 221.42..230.12  phase buffers wtx8_phbuf (cell 9.92 x 8.7 um): cell VDD rail on the VDD rail's lower edge, cell VSS rail in the VSS rail
 214.02..228.52  VSS rail, Metal4 || Metal2, 14.5 um (over each buffer the Metal2 stops 8.0 um up; Metal4 is continuous)
 213.02          PH0..PH7 pin pads (Metal5 1.2 um), straight under the mux PH pins
 203.18..        PS sub-zone: PS k Metal4 tracks with a VSS track between neighbours (5 PS tracks, 6 VSS)
 198.68          zone B: Metal4 F0..F7, SERQ (5 tracks, 0.84 um); in the same height, 18 Metal2 tracks (0.72 um) for the control nets
 197.68          top edge of wtx_ser8d
```

How the seam fits: the buffers sit in the rail band; the Metal2 rail is cut only above each buffer cell; the control ports leave on the left or the right edge, whichever gives fewer Metal2 tracks (18), and the Metal2 tracks pass under the mux; the gap above ser8d is 1.0 um. The trim bits no longer enter the seam (section 5).

## 2. Checks on the final GDS

GDS: `s13/top/out/pt_wiredtx8.gds` (sha256:d595e0e8a523cd6fc9c3ebfe089f791b3484537b70f8f4acf1295ab9e160864a), exported with the analog image and read back in the fresh directory `top/verify`; copied unchanged to `generated/fast/pt_wiredtx8.gds` (see section 7).

| check | result |
|---|---|
| Magic DRC `drc(full)` | **0** |
| KLayout DRC (`sak-drc.sh -k`, gf180mcuD) | **0** |
| Netgen LVS vs `wtx8_top.netlist()` (hierarchical; phase buffers and decap flattened at top level) | **Final result: Circuits match uniquely.** (36 / 36 devices, 155 / 155 nets at top level, 0 property errors) |
| negative control: PH0 / PH1 swapped at the mux (XMUX line) | FAILS as required (Top level cell failed pin matching) |
| negative control: stream rotation off by one (FROT 3) | FAILS as required (Netlists do not match) |
| negative control: OVP / OVN swapped at the mux | FAILS as required (Netlists do not match) |
| negative control: buffer outputs PS0 / PS1 swapped at ser8d (XSER line) | FAILS as required (Netlists do not match) |
| negative control: trim pins TR6_0 / TR7_3 swapped at the mux (the new right-side Metal4 pins) | FAILS as required (Top level cell failed pin matching) |
| Magic `antennacheck` | violations **0** |
| flat C netlist: port order = `wtx8_top.PORTS` | True; 1678 child substrate nodes moved to VSS by `fix_vsubs`, none left; 3018 nfet, 2251 pfet, 10 poly resistors |

The negative controls are changed reference netlists, not changed layouts. No separate KLayout antenna deck was run.

## 3. Phase nets: what the ring sees

Each PH k has the same geometry:
- the block pin: a Metal5 pad under the mux PH k pin;
- a 10.5 um Metal3 stub up to the mux pin, drawn 5.24 ohm (Metal3 0.4 um, 0.225 ohm/um);
- the first buffer inverter (2 / 4 um) on that stub.

| | PH0..PH7 |
|---|---|
| wire C, top-level wiring alone | 6.7..7.0 fF (spread 0.3 fF) |
| wire C, whole block (incl. the mux's internal phase wiring) | 17.8..18.6 fF |
| gate load added by the buffer | 2 + 4 um of gate, about 13 fF (2.2 fF/um estimate, not simulated) |

So the ring sees about 31 fF per phase plus the mux's own PH gates (I0 6 / 6 um; detector input DH1 1.0 / 1.8 um at L = 0.5 um).

## 4. PS (buffer to ser8d), F and SERQ nets

Each PS k runs as follows:
- from the buffer output, Metal3 down to its own Metal4 track;
- along the track (VSS track on both sides) to the ser8d PH pin;
- Metal5 down to that pin.

The PS nets are not equalised: the ser8d phase pins are spread over 650 um.

| k | PS Metal4 (um) | PS drawn R (ohm) | PS wire C top / block (fF) | F track (um) | F drawn R (ohm) | F wire C top / block (fF) |
|---|---|---|---|---|---|---|
| 0 | 199.9 | 50.4 | 43.4 / 66.4 | 262.1 | 59.0 | 36.4 / 49.5 |
| 1 | 167.2 | 42.8 | 36.7 / 56.3 | 26.5 | 6.0 | 11.3 / 33.1 |
| 2 | 146.2 | 37.8 | 32.5 / 53.6 | 224.2 | 50.4 | 37.9 / 60.8 |
| 3 | 124.0 | 33.1 | 29.5 / 51.3 | 303.9 | 68.4 | 49.8 / 70.5 |
| 4 | 63.7 | 18.8 | 18.4 / 40.6 | 234.2 | 52.7 | 42.6 / 64.5 |
| 5 | 98.9 | 27.2 | 24.3 / 46.6 | 86.1 | 19.4 | 17.2 / 37.1 |
| 6 | 259.1 | 63.0 | 51.7 / 73.8 | 42.6 | 9.6 | 12.2 / 33.2 |
| 7 | 419.3 | 99.7 | 79.2 / 102.3 | 270.1 | 60.8 | 40.8 / 60.7 |

SERQ: 183.4 um, 41.3 ohm.

The PS load ranges from 41 to 102 fF on a 6 / 12 um inverter. By my estimate that is roughly 0.1 ns of skew between the ser8d phases. This has not been simulated: the probe run (STATUS item 2) has to confirm the stream timing with the buffers in.

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
- **TR0_0..TR7_3: Metal4 on the block edge at the free top-right corner** (x 598.1, the inner vertical edge of the L outline, y 255.0..278.76, pitch 0.72 um). The mux brings them out on its right side (Metal4, 32 tracks over its gate / in rows); the block continues each one 32.2 um under the right-hand VDD / VSS Metal5 bars to the edge. Order from the bottom: track 8 b + p for bit b of the slice at position p (phase order 0 7 1 6 2 5 3 4), i.e. TR0_0 TR7_0 TR1_0 TR6_0 TR2_0 TR5_0 TR3_0 TR4_0 TR0_1 ...; exact y per pin in `out/report.json` -> `pins`.

## 6. Supplies and electromigration

The rails are Metal4 || Metal2. The VSS rail is 14.5 um and the VDD rail 5 um.

What connects to them:
- ser8d's Metal5 straps run up into the rails (17 VSS, 16 VDD). A strap that would run into a phase pin pad, or under the other net's bar, stays inside ser8d.
- 11 + 11 Metal2-Metal4 stitches tie the two rail layers together.
- The mux's 9 VSS straps come down as 2.5 um necks. Its 8 logic VDD straps go straight into the VDD rail.
- Each header is fed from the VDD bars by a Metal5 strap along the top edge. Inside the mux the bank passes under the output risers on Metal1-4 (mux EM rows: 32.9 / 39.3 %).

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

All four files are written to `s13/top/out` by the generator and copied unchanged to `generated/fast` (hashes identical).

- **`generated/fast/pt_wiredtx8.ext.spice`** (sha256:9a4ac15115696d473e3d71c8e09ab1e0b35a0fb31aa5b62bf221c4dc65a1f926):
  - one flat C-only netlist of the whole block;
  - port order `wtx8_top.PORTS`;
  - 3018 nfet, 2251 pfet, 10 poly resistors.
- **`generated/fast/pt_wiredtx8.rc.spice`** (sha256:ec4c2d3f9eee8802c71b3309dfb2463bd96565e1729ffdf942c5e324502a809d): the same netlist plus DRAWN resistance, added in two steps by `pt_wiredtx8_layout.add_rc` (the drawn lumps are optimistic against extresist, `s14/rcov/RCOV.md`).
  1. **Mux-internal:** `wtx_mux8_layout.add_wire_r` runs on the `XMUX/` nodes with the mux's own report. It adds 108 resistors:
     - the gate-line trunks X, XTM, XTQ, APM, ANM, APQ, ANQ of all eight slices (13.5 / 2.4 / 2.2 / 13.4 / 13.6 / 6.1 / 6.2 ohm);
     - the ring wires BM / BQ (30.2 / 24.5 ohm);
     - the Metal5 ladders of the four output buses, with a node per slice (`MAIN_P#k` ...), the tap node, and the strap to the pin.

     `add_rc` stops with an error if any trunk node is missing from the block netlist. All 72 are present.
  2. **Top level (`add_top_r`, 31 resistors):**
     - PH k: pin -> `PHk#m` (mux side), 5.24 ohm.
     - PS k: buffer -> `PSk#s` (ser8d side), with the resistances of section 4.
     - F k, SERQ: -> `#s` (ser8d side).
     - VDD / VSS: one lumped resistor per child, in ohm: VSS mux 0.342 / ser 0.406 / aux 1.489; VDD mux 0.849 / ser 0.962 / aux 1.317. These are coarse.

  Connectivity check on the file: every split node has devices on it, except the four bus tap nodes `#t`, which carry only resistors (as intended). Trim wires carry no added R (static nets). The session-14 netlist has not been simulated at block level.
- **`generated/fast/pt_wiredtx8.lvs.spice`** (sha256:6baeb34706f25e92b7f3f1d21d4c8de164c61fa15a25079414da5ff067b548ad): hierarchical LVS netlist of the read-back GDS.
- **`generated/fast/pt_wiredtx8.gds`** (sha256:d595e0e8a523cd6fc9c3ebfe089f791b3484537b70f8f4acf1295ab9e160864a).
- **`generated/fast/pt_wiredtx8.spice`:** the intended netlist, regenerated with `python3 wtx8_top.py` (decap n = 686; it includes the revision-3 mux schematic of `wtx_mux8.netlist()`).

## 8. Children

| child | state | result |
|---|---|---|
| `wtx_mux8` | rebuilt in session 14 (`wtx_mux8_layout.py`): detector input stage with hysteresis, I0 gated by RUN, trim pins on its right side | 324.6 x 164.44 um (unchanged). Magic DRC 0, KLayout 0, LVS unique, 5 / 5 negative controls fail, antenna 0. EM worst: drain stub 13.6 %. Bus wire C 100.6 / 109.4 / 119.3 / 122.8 fF (unchanged) |
| `wtx8_aux` | pass-2 build, unchanged | Magic DRC 0, KLayout 0, LVS unique, 2 / 2 negative controls fail |
| `wtx_ser8d` | read only | |

## 9. Open items

- **The PH pins are inside the block**, under the mux, as the brief asked: "at the pin row". The ring has to be routed to them.
- **PS loads are unequal** (41..102 fF); estimated skew is about 0.1 ns. The block-level real-chain rows have to confirm it.
- **Not done:** Magic extresist on the block, a KLayout antenna deck, fill, an independent review, any simulation of the session-14 block netlist.
- **ser8d inputs:** `wtx_ser8d` was not touched. `serm5/dcols.json`, the trunk positions, was taken from the 06:01 GDS, which is still the published one. If ser8d changes, `dcols.json` has to be remade from a flattened ser8d (`serm5/f.tcl` + `m5.json`).

## 10. Reproduce

```
cd projects/programmable_transceiver_platform/analog/wired_tx
OMP_NUM_THREADS=1 python3 wtx_mux8_layout.py            # mux, verify, generated/fast (session 14: run without the copy, s14/ilk/build_mux.py)
OMP_NUM_THREADS=1 python3 wtx8_aux_layout.py            # needs the mux report
OMP_NUM_THREADS=1 python3 pt_wiredtx8_layout.py         # about 40 s; writes DECAP n into wtx8_top.py if it differs
                                                        # (session 14: s14/ilk/build_top.py = the same without the copy to generated/fast)
OMP_NUM_THREADS=1 python3 pt_wiredtx8_layout.py build   # layout + DRC / LVS in top/build only
python3 wtx8_top.py                                     # intended netlist generated/fast/pt_wiredtx8.spice
```

GDS hashes change with every run because of the time stamp.

The top generator reads:
- the mux / aux build directories (`s13/mux3/build`, the aux build directory);
- `s13/top/serm5/dcols.json`.

Keep those.

## Supply grid (ASM-8), state 2026-11-20 (session 15)
**Exception hole reduced, not full 70 um channels.** Full channels at every grid axis (35 um) through `wtx_ser8d` were
tried (dry runs): with 16 um straps the trunks do not fit ("no free trunk column"); with 10.5 um straps they fit but the PH
trunks go from 38-46 to 41-76 um (phase equality lost) and half the ser8d strap pairs go. Instead `wtx_ser8d` keeps three
channel PAIRS (Metal5-free, y 0-197.68, 21 um = 16 um strap + 2 x 2.5 um): x 207-228 / 242-263, 382-403 / 417-438,
557-578 / 592-613 (axes 7.5 + 35 k). The Metal5 exception is then the block above y 197.68 plus the four ser8d pieces between
channels; widest piece 229 um (x -19.5 to 209.5 between grid strap edges), others 124 / 124 / 136 um; the upper part is
about 208 um tall (y 195-403). No 250 um square fits in the hole (G3). **Assembly: place pt_wiredtx8 unrotated with
x0 = 4.75 (mod 35) um** so the grid axes (core x0 + 15.25 + 35 k) hit the channel axes; the two channels of a pair carry
VDD and VSS, which one depends on x0 mod 70 (phase A: left channel VSS, B: right).
Block VDD is the switched island `RAIL_wired_tx`: grid VDD in a channel only passes over ser8d (no tie).
- **VSS trunks**: three 10 um Metal5 bars x 335-345 / 405-415 / 475-485 from the seam plate (top y 228.3) to the bottom edge
  (tie points `bottom_0..2`, y 0-1), half-way between the PH pads; Via4 to every ser8d VSS track and the zone-B VSS tracks.
- **VSS tabs**: 16 um Metal5 from the plate down to y 197.68 in the channels with no PH pad (x 209.5-225.5, 244.5-260.5,
  559.5-575.5, 594.5-610.5; ties `chanA_0`, `chanB_1`, `chanA_4`, `chanB_5`). The grid VSS strap of that channel ends 2.5 um
  below the tab and needs a hook to it (assembly). The middle channels (392.5 / 427.5) hold PH pads (PH6, PH2): no tab.
- Checks from disk: Magic 0, KLayout 0, Magic antenna 0, LVS unique, 5 negative controls fail. Outline unchanged 744.12 x 400.56.
IR at 60 mA, tie point to output stage (`ir/run.sh`, results `ir/phA|phB/*.json`; budget 6.6 mV):

| case | VDD | VSS | total | ser8d logic VDD / VSS |
|---|---|---|---|---|
| s14 (no trunks) nominal / high R | 3.67 / 7.60 | 11.15 / 14.67 | 14.8 / 22.3 | 21.05 / 17.4 ; 37.1 / 30.3 |
| trunks only, nominal / high R | 3.67 / 7.60 | 7.80 / 10.08 | 11.5 / 17.7 | 20.55 / 13.2 ; 35.6 / 24.7 |
| trunks + tabs, phase A nominal / high | 3.67 / 7.60 | 6.42 / 8.49 | **10.1 / 16.1 FAIL** | 20.55 / 11.45 ; 35.6 / 22.4 |
| trunks + tabs, phase B nominal / high | 3.67 / 7.60 | 6.18 / 8.20 | **9.9 / 15.8 FAIL** | 20.55 / 11.42 ; 35.6 / 22.4 |
| diagnostic: ideal tie along the whole plate | 3.67 | 1.93 | 5.6 | |

The earlier 6.4 mV estimate for three trunks was wrong: the trunks themselves (about 0.3 ohm over 214 um) carry the drop;
VSS needs a tie on the plate near x 280-560 (under the tails). Options (not done): a grid VSS tie into the plate from above
through the middle of the block (needs the mux area / a declared opening), moving PH2 / PH6 pads out of channels 392.5 / 427.5
so tabs fit there, or a bigger budget share from the power owner (WT43 asked to re-split ASM-9 at this tap).
EM (85 C limits): band cuts worst 51.5 % margin (seam plate), trunks 55.9 / 85 / 87 %, VDD 78 %; header strap end 23 % (table,
unchanged). The raster also flags VDD Metal4 -6.8 % (high R -29.6 %) at the T_main tie pixel (389.7, 398.5), the same
as before this change: a tie-edge artefact of the raster, the band cut there is 93 %; not re-examined.
PH0..7 remain Metal5 pads inside the block (no edge access).
