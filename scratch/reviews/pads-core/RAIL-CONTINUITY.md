# Provider ring rails through the custom pad families (INT1-11)

2026-11-14. KLayout python on GDS only; no DRC deck, no simulation. Nothing in the project tree was changed.
Scripts and data in `scratch/pads-core/rails/`: `rails2.py` / `rails2.json` (mini-assembly of the v6 pad set, previous
agent, re-read and kept), `rails4.py` / `rails4.json` (site ties, corners, each family alone, assembled v5 chip, controls),
`rails5.py` / `rails5.json` (which custom net touches the ring), `inspect1.py`, `rails3.py` (earlier probes).
Everything below is **measured in GDS** unless marked [CALC] or [REPORT].

## Answer to INT1-11

The provider ring rails are continuous at full width through every custom pad family that the assembly places today:
`rf-pair`, `rf-tx`, `reference`, `wired-receive-usb`, `wired-transmit`, `wired-receive-hs` (published and the staged
stacked b2), `single-leg`. This holds on the published cells placed on the retained ring at the v6 sites, and on the
last assembled chip GDS (v5 run2), on all four edges and round all four corners: DVDD 124.0 um, DVSS 101.39 um, VDD 14.0 um
and VSS 14.0 um on each of Metal3, Metal4 and Metal5, no gap and no neck anywhere. The reason is structural: the assembly
replaces the provider IO cell under each custom site with the provider rail cell `5LM_METAL_RAIL`, and the custom cells
put no Metal3/4/5 of their own in the ring depth except one 2 x 2 um stack per site that ties their VSS to the ring DVSS.
So AP4-10(b) can rely on the ring. **One exception, not yet assembled: the TLP site cell (`pad_tlp_flat`, planned for
`bidir[25]`) shorts its pad to DVSS and DVDD when it is placed over the rail cell**, which is what `kl_assemble.py` would do.
It needs a cell change or a ring cut before it goes into an assembly. There is no assembled v6 GDS; v6 exists as a floorplan.

## 1. Layers and rail bands

- Layer numbers from `/foss/pdks/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map` and the LVS deck
  `lvs/rule_decks/layers_definitions.lvs`: Metal2 36/0, Via2 38/0, Metal3 42/0, Via3 40/0, Metal4 46/0, Via4 41/0,
  Metal5 81/0, Pad 37/0 (labels on datatype 10).
- The ring rails are on **Metal3, Metal4 and Metal5 only**. `5LM_METAL_RAIL` has no Metal2 and no Via2 (37,232 Via3 and
  37,232 Via4 per 75 um cell). Provider IO cells use Metal2 inside the cell, not as ring bands. So "Metal2..Metal5" in the
  question reduces to Metal3..Metal5.
- Bands of the rail cell, depth from the pad-cell outer edge, identical on the three layers and on both cell edges
  (named from the cell's own Metal3 labels):

| Rail | Bands (depth um) | Sum per layer |
|---|---|---|
| DVSS | 70-85, 86-101, 102-117, 126-133, 198-205, 230-245, 286-293, 302-309, 326-333, 342-348.39 | 101.39 um |
| DVDD | 118-125, 134-149, 150-165, 166-181, 182-197, 206-213, 214-229, 262-269, 270-277, 278-285, 294-301, 334-341 | 124.0 um |
| VSS | 246-253, 318-325 | 14.0 um |
| VDD | 254-261, 310-317 | 14.0 um |

- Every supply site is a `gf180mcu_fd_io__dvdd` cell and every ground site a `gf180mcu_fd_io__dvss` cell (also the sites the
  template calls `vdd_pads` / `vss_pads`). Net extraction per site on the retained ring: each of the 8 supply pads is tied
  to DVDD **and** VDD, each of the 10 ground pads to DVSS **and** VSS. (The LEF agrees: `dvdd` has no VDD pin, `dvss` has no
  VSS pin.) On this die the ring is therefore two nets: supply = DVDD + VDD (138.0 um per layer) and ground = DVSS + VSS
  (115.39 um per layer). Signal cells (`bi_24t`, `in_c`, `in_s`, `asig_5p0`) tie their pad to no rail.

## 2. Per family

Method A (`rails4.py` B, `rails5.py`): the custom cell alone; every piece of its Metal3/4/5 that lies on a rail band, and the
custom net that piece belongs to (Metal2..Metal5 connectivity, with Via4 on MIM top plates excluded).
Method B (`rails2.py`): retained provider ring from `packaging-assembly.gds`, provider IO cell swapped for the rail cell at
every custom site exactly as `kl_assemble.py` does, published cell placed with the assembly transform (mirrored where the
assembly mirrors); band width profile along the edge and net extraction over the pad window.

| Family (GDS) | Used at (v6) | Custom Metal3/4/5 on the ring bands | DVDD | DVSS | VDD | VSS | Pad shorted to a rail |
|---|---|---|---|---|---|---|---|
| `rf-pair/pad.gds` | RF_RX, BB_I, BB_Q, WCLK_IN, WTX_EXT | own VSS on DVSS: 2 x 2 um stack at each site (x 9-11 and 220-222, depth 77.3-79.3) | continuous 124.0 | continuous 101.39 | continuous 14.0 | continuous 14.0 | no |
| `rf-tx/pad.gds` | RF_TX | same | continuous | continuous | continuous | continuous | no |
| `reference/combined.gds` | REF, AUX_CLK | same | continuous | continuous | continuous | continuous | no |
| `wired-receive-usb/combined.gds` | USB | same | continuous | continuous | continuous | continuous | no |
| `wired-transmit/combined.gds` | WIRE_TX (mirrored) | same | continuous | continuous | continuous | continuous | no |
| `wired-receive-hs/pad_hspad.gds` (published) | WIRE_RX (mirrored) | same | continuous | continuous | continuous | continuous | no |
| `scratch/pads-core/hspad/b2/pad_hspad.gds` (staged stacked) | WIRE_RX (mirrored) | same | continuous | continuous | continuous | continuous | no |
| `single-leg/pad.gds` | WMON | same, one stack | continuous | continuous | continuous | continuous | no |
| `tlp-site/pad_tlp_flat.gds` | `bidir[25]` (planned) | **PAD net**: Metal3 riser x 27-37, depth 70-121.5: 450 um2 on DVSS (70-117) and 35 um2 on DVDD (118-125) | **shorted to PAD and DVSS** | **shorted to PAD and DVDD** | continuous | continuous | **yes, to DVSS and DVDD** |

- "continuous" = the band is covered over its full width along the whole pad window on Metal3, Metal4 and Metal5
  (minimum covered width = band width), the net at one end of the window is the net at the other end, and no two rail
  names are merged other than DVDD with VDD or DVSS with VSS where a provider supply or ground cell lies in the window.
- The staged b2 cell was checked two ways: Method A directly, and against the area-pass-4 candidate that `rails2.py`
  placed: XOR of Metal2..Metal5 and Via2..Via4 over depth 0-360 um is 0.000 um2, bond openings identical.
- Compact cells used by the v5 assembly (`scratch/pad-compact/rf-pair`, `.../reference_clock`): same result as the
  published ones.
- The custom families reach the core over the ring on Metal2 (3,400 to 18,000 um2 of custom Metal2 in depth 66-350),
  which the rail cell leaves free. Their only Metal3/4/5 contact with the ring is the VSS stack: no custom net touches DVDD
  or VDD in the ring depth. The stack is 2 x 2 um; whether that is meant to carry current is a pad-design question, not a
  continuity one.
- Wide families lie over neighbouring sites (wirepad 524 um, txpad 484 um, hspad 492 um, single-leg 302 um against a
  75 or 286 um site span). In the assembled v5 GDS the custom cells' Metal1 and Metal2 have 0 um2 overlap with the provider
  ring cells' Metal1 and Metal2 inside the ring strip; the only same-layer overlaps are the VSS stacks.

### TLP site

`pad_tlp_flat` (68 x 124 um, ports PAD, VSS, VDD on Metal2 at depth 101-118) carries a 10 um wide Metal3 riser of the PAD net
from the pad plate to depth 121.5. The rail cell has DVSS Metal3 at 70-117 and DVDD Metal3 at 118-125 over the whole site
width. Placed over the rail cell, PAD, DVSS and DVDD become one net (confirmed two ways: `rails4.json` family test and the
`rails2.json` window of the mini-assembly, where the pad cluster equals the DVSS and DVDD cluster). PD48b asked for the cell
on `bidir[25]` with "VDD/VSS strapped to that site's ring rails"; `inventory.py` still has the single-leg ESD_TEST cell there
and `kl_assemble.py` has no TLP entry, so this has never been built. The v5 GDS, which has the single-leg at that site, is clean.
The two LNA_SRC placeholders in `floorplan-v6.json` have the TLP-site outline; a pad built on that pattern has the same problem.

## 3. Assembled ring

Latest assembled GDS: `scratch/chip-assembly-v5/run2/pt_chip_top.gds` (241 MB, 2026-11-11; `assembly.json` `ok` is false for
other reasons). It differs from v6 in the pad cells used (compact rf-pair / refpad, published side-by-side hspad, single-leg
ESD_TEST at `bidir[25]`), not in the ring. `scratch/chip-assembly-v6/` has no GDS.

Clipped to the ring strip (depth 0-352 um from the pad-cell edge), all geometry of the top cell included:

| Edge | Range along edge (um) | DVDD M3 / M4 / M5 | DVSS | VDD | VSS | Gaps | Necks |
|---|---|---|---|---|---|---|---|
| West | 382-4740 | 124.0 / 124.0 / 124.0 | 101.39 x 3 | 14.0 x 3 | 14.0 x 3 | 0 | 0 |
| East | 382-4740 | 124.0 x 3 | 101.39 x 3 | 14.0 x 3 | 14.0 x 3 | 0 | 0 |
| South | 382-3550 | 124.0 x 3 | 101.39 x 3 | 14.0 x 3 | 14.0 x 3 | 0 | 0 |
| North | 382-3550 | 124.0 x 3 | 101.39 x 3 | 14.0 x 3 | 14.0 x 3 | 0 | 0 |

- Net extraction over each of the 13 custom pad windows of v5: 0 end-to-end mismatches in 78 bands, no bond pad tied to a
  rail, rail names merged only as DVDD+VDD (windows of `pad_ref`, `pad_usb`, which include a `dvdd` cell) or DVSS+VSS
  (`pad_hs_rx`, `pad_wire_tx`, `pad_esd_test`, which include a `dvss` cell).
- Corners (retained ring, all four): each of the 78 bands is the same net on both sides of the corner and is continuous on
  its own layer round the corner. The width through the corner cell was not measured.
- `kl_assemble.py` does not cut the provider ring. What it cuts and re-straps around custom cells is its own core ring
  (VSS at depth 380-405, VDD at 411-436, Metal3 on N/S and Metal4 on E/W), which lies outside the provider cells and was
  not part of this check.
- The mini-assembly of the v6 pad set (`rails2.json`) gives the same table on all four edges, plus the TLP short.

## 4. Segments between supply and ground bonds, with resistance [CALC]

Sheet resistance: Metal3 90, Metal4 90, Metal5 40 mohm/sq, nominal, from the Magic tech file
`/foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.tech` lines 3341-3347 ("Resistances are in milliohms per square";
it cites 180MCU_YI-141-EP059-01_10). Three layers in parallel: 21.2 mohm/sq.
Supply ring (DVDD + VDD, 138.0 um): **0.153 ohm/mm**. Ground ring (DVSS + VSS, 115.39 um): **0.184 ohm/mm**.
(DVDD alone 0.171, DVSS alone 0.209, a 14 um VDD or VSS pair alone 1.51 ohm/mm.) Narrowest width in every segment equals the
full width, since nothing is necked. Corner legs are taken as an L path at mid-band depth (236 um from the die edge), which
overstates each corner by about 0.1 mm of path against a 45 degree chamfer. No temperature or corner spread applied.

Supply bonds (bond number, site, edge position):

| Segment | Passes | Length | Narrowest width per layer | R |
|---|---|---|---|---|
| 18 `dvdd_pads[0]` (E 556.5) -> 26 `dvdd_pads[1]` (E 2244.5) | hs_rx, E1/E2, usb | 1688 um | 138.0 um | 0.26 ohm |
| 26 -> 35 `vdd_pads[0]` (E 4143.5) | wire_tx, wtx_ext, wmon, TLP site | 1899 um | 138.0 | 0.29 |
| 35 -> 37 `dvdd_pads[2]` (E 4565.5) | | 422 um | 138.0 | 0.065 |
| 37 -> NE corner -> north edge -> NW corner -> 58 `dvdd_pads[3]` (W 3932.5) | whole north edge, rf_tx | 4734 um | 138.0 | 0.73 |
| 58 -> 64 `dvdd_pads[4]` (W 2666.5) | bb_q, aux_clk | 1266 um | 138.0 | 0.19 |
| 64 -> 72 `vdd_pads[1]` (W 978.5) | ref, bb_i, rf_rx, W-A/W-B | 1688 um | 138.0 | 0.26 |
| 72 -> 74 `dvdd_pads[5]` (W 556.5) | | 422 um | 138.0 | 0.065 |
| 74 -> SW corner -> south edge -> SE corner -> 18 | whole south edge (D2H, SPI, RESET_N) | 4101 um | 138.0 | 0.63 |

Ground bonds:

| Segment | Length | Narrowest width per layer | R |
|---|---|---|---|
| 9 `dvss_pads[0]` (S 1965.5) -> SE corner -> 19 `dvss_pads[1]` (E 767.5) | 2262 um | 115.39 um | 0.42 ohm |
| 19 -> 27 `dvss_pads[2]` (E 2455.5) | 1688 um | 115.39 | 0.31 |
| 27 -> 34 `vss_pads[0]` (E 3932.5) | 1477 um | 115.39 | 0.27 |
| 34 -> 36 `dvss_pads[3]` (E 4354.5) | 422 um | 115.39 | 0.077 |
| 36 -> NE corner -> 46 `dvss_pads[4]` (N 1965.5) | 2262 um | 115.39 | 0.42 |
| 46 -> NW corner -> 57 `dvss_pads[5]` (W 4143.5) | 2472 um | 115.39 | 0.45 |
| 57 -> 63 `dvss_pads[6]` (W 2877.5) | 1266 um | 115.39 | 0.23 |
| 63 -> 71 `vss_pads[1]` (W 1189.5) | 1688 um | 115.39 | 0.31 |
| 71 -> 73 `dvss_pads[7]` (W 767.5) | 422 um | 115.39 | 0.077 |
| 73 -> SW corner -> 9 | 2261 um | 115.39 | 0.42 |

The south and north edges have no supply bond and one ground bond each. The longest unfed supply stretches are the two that
contain those edges (0.63 and 0.73 ohm end to end, so at most 0.16 / 0.18 ohm from the mid-point to both ends in parallel).

## 5. Negative controls

- Band profile and net extraction on the assembled v5 west edge with a synthetic 5 um gap cut in every DVDD band at s = 2000 um:
  reported BROKEN (min width 0 of 124.0 on Metal3/4/5, 12 gaps per layer, two DVDD nets, 36 end-to-end mismatches); DVSS, VDD,
  VSS unchanged. With a 3 um remnant left in each band: reported NECKED (36.0 of 124.0 um).
- Same control in the mini-assembly (`rails2.json`): gap reported with its position (1506-1511 um), neck reported.
- Family test with a synthetic custom Metal3 bar over depth 110-130: reported as one custom net on DVSS and DVDD, short flagged.
- One false alarm found and removed during the work: with plain Metal4-Via4-Metal5 connectivity the custom cells' ESD_RAIL
  and VSS look like one net, because Via4 that lands on a MIM top plate (FuseTop 75/0) is not a Metal4 contact. `rails5.py`
  excludes those vias; ESD_RAIL and VSS are then separate, and the ring tie belongs to VSS. The ring-depth results
  are not affected (no MIM in the ring depth).

## 6. Limits

- Geometry and metal connectivity only. No DRC, no current density, no extraction with devices.
- v6 has no assembled GDS; the v6 statement rests on the published cells placed on the retained ring with the
  assembly's transforms. A new pad set (strap `in_c`, AGND_RX pads, TLP site) needs this check again after assembly:
  `rails4.py` section D runs on any `pt_chip_top.gds` in about 3.5 minutes.
- Corner width, and Metal2 / Metal1 collisions between custom cells and neighbouring provider cells for the stacked hspad
  and the TLP site (not in v5), were not measured.
- Sheet resistances are nominal values from the Magic tech file, not the foundry electrical spec table.
