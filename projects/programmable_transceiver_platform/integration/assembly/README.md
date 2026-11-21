# Chip assembly (pt_rf, pt_wired)

Current state only. Full-chip layout of each chip on the wafer.space 1x1 die (3932 x 5122 um, 74-site provider ring):
legal floorplan on real geometry, power grid, top-level routing with OpenROAD, assembled GDS read back from disk by the
sign-off flows (`../signoff`). Re-runnable as blocks change; each run overwrites the previous one.

```
./run.sh <rf|wired>                       # abstract floorplan place route stream report  (about 1 h per chip)
./run.sh <rf|wired> drc | lvs | fill      # sign-off on chip/pt_chip_top.gds (shuttle decks, via ../signoff)
```

Run directory `scratch/integration/assembly-<chip>/` (not in git; `ASM_RUN` overrides). Tools: `tool.sh` runs the
LibreLane GF180 image (OpenROAD + KLayout python), network off, at most 4 threads, `OMP_NUM_THREADS=1`. Its containers are
named `asm-<chip>-<pid>`: stop a run only by that name (`docker kill asm-...`) or a recorded PID, never by a pattern match.

| Stage | Script | What it does | Outputs (run dir) |
|---|---|---|---|
| abstract | `kl_abstract.py` | Template ring + seal + ID cells; custom pad families placed with their bond openings exactly on the golden-mask openings of their `bond_map.txt` sites; provider `dvdd`/`dvss` cell at every signal site bonded VDD/VSS (D-SPLIT-SUPSITE, PC-35; kept provisionally, open as wafer.space question 15, COB tester behaviour); LEF abstract of every master that has a GDS | `ring.gds`, `pads.json` (real footprints), `masters.json`, `lef/` |
| floorplan | `floorplan.py` | die-fit packer (`scratch/reviews/die-fit/fit.py`, scenario S, its targets, keep-aways, INT23 QVCO rule, switch positions, decap plan) on the real pad footprints (+40 um for the core ring) and the GDS outlines; second pass for conn blocks the ledger does not book; independent overlap check | `floorplan.json`, `fit/fit-s.png` |
| place | `kl_place.py` | Places real GDS / placeholders (named like the master, pins on the side facing their nets), power grid, hook nets, DEF | `placed.gds`, `design.def`, `nets.json`, `place.json`, `lef/pt_pdn.lef` |
| route | `route.tcl` | FastRoute + TritonRoute, Metal2-Metal5 | `route/{groute,routed}.def`, `congestion.rpt`, `drt.rpt`, `route.log` |
| stream | `kl_stream.py` | Router wiring (DEF, PDK layer map) merged into the placed GDS | `chip/pt_chip_top.gds`, `chip/manifest.json`, `chip/cell_owner.json` |
| report | `report.py` | completion, wire length per net and class, congestion and floorplan pictures | `report/{route.json, floorplan.png, congestion.png}` |

## Rules the flow applies

- **Abstracts.** Pins = top-cell labels (Metal1-5 `xx/10`), the metal under the label within 25 um. Obstruction: whole
  outline on Metal1-3; drawn metal (2 um grid) on Metal4/5, so a top-level net may cross a block on Metal4/5 where it draws
  none; whole outline on all layers for the no-route-over set (`common.NO_OVER`: QVCO, LNA and its spirals, mixers, txsum,
  rfdriver, lo_ext, lo_mmd(+qdum), rings, ring_osc, vco_replica, T-coil; = fill keep-out set `rf`); a 2 um window round
  each pin is opened from the pin layer up (the drawn metal inside it stays an obstruction). A pin that is not on the block
  edge is reachable only from above, and in a no-route-over block not at all.
- **Placeholders** (no GDS: digital macro at the synthesis outline of `verification/digital_hardening/<chip>/config.json`,
  demand cells, decap bank and tiles): outline on 0/0, pins on Metal2 (N/S) / Metal3 (E/W) on the side facing the other
  ends of their net. Macro obstructs Metal1-4 (Metal5 free for the grid), decap Metal1-2, others Metal1-3.
- **Metal5 rule** (ASM-8): Metal5 is the top grid's; blocks draw it only as declared exceptions with a ring; top routing crosses a
  block on Metal4/5 only where it declares them free.
- **Power grid** (`spec/power-delivery.md` G1/G2/G8): core ring VDD outer / VSS inner, 2 x 14 um (provisional, ASM-9) on Metal4 + Metal5,
  following the free boundary round the pad families; VDD/VSS strap pairs at 70 um pitch, 10.5 um each, Metal4
  horizontal and Metal5 vertical, cut 2.5 um from any block Metal4/5, 8 um round no-route-over blocks, Metal4 cut over the
  macro; Via4 arrays at every same-net crossing; Metal2 stubs + Via2/Via3 from every supply cell into its ring. Block
  VDD/VSS pins reach the grid through hook nets (one 20 um slot of the nearest same-net strap each) that the router draws.
- **Net classes** (`kl_place.cls`): island rails / regulator outputs 3 um wide; hooks 1.2 um; clock, high-speed and RF
  nets twice the minimum spacing (no drawn shields). Booked ledger items without a conn instance are Metal1-3 blockages.

## Results (current: commit 21bbb5e5; pt_rf route 2026-11-20 10:34, pt_wired route 14:17, pt_rf DRC 2026-11-21)

| | `pt_rf` | `pt_wired` |
|---|---|---|
| Floorplan (`report/floorplan.png`) | all conn blocks placed, 0 overlaps, 0 keep-away fails; 40 um channels south / east of the macro; island blocks pulled to their switch | same; `isw_wired_rx` beside `dvdd_pads[1]` (PDS-9); `pt_wiredtx8` (staged, for instance `wiredtx`) R0 at cell x0 = 1493.75 (23.75 mod 70) |
| Grid straps (`strap_widths.json`) | 10.5 um everywhere: M4 7.5-8.0 %, M5 10.8-11.2 % per net (passes IR, PDS-8) | 16 um in ME / SE, 10.5 um elsewhere: M4 8.6-8.9 %, M5 12.1-12.7 %; ME 7.1-11.0 %, SE 10.1-12.6 % (below 12 %: own Metal4/5 of wrx_cap / ptrim / wired TX, ASM-8) |
| Nets routed (signal / clock / hs / rf / rail) | all | all |
| Hooks routed | 227 / 275 | 228 / 265 |
| Detailed-route violations (20 iterations); baselines 467 / 742 (rf), 1035 / 2919 (wired) | **164** (109 shorts: lna_deg_n placeholder 27, atb1_leaf18/29 35, grid 7; 55 spacing) — QVCO r8, pin-moved RF pads, orientation fixed; OpenROAD antenna check 0 | **1180** (664 shorts, 514 spacing; 920 of them in the 12 um gap between the macro's south-east corner and pad_wire_tx: the macro (x 951-2667) and pad_wire_tx (x 2679-3906) wall off the north-east pocket, so every net between that pocket and the rest crosses one 12 um channel: h2d_pin, RAIL_wired_tx / pll / debug, WTX_DX_DBG); OpenROAD antenna check 0 |
| pt_wiredtx8 grid ties | | VSS landings 4 of 6, channel tabs 3 of 6 (the others sit on VDD axes, untied by design); 10 old pins unconnected until the conn binds the new cell |
| Shuttle precheck (pt_rf, filled, 2026-11-21; layout of the QVCO-r8 run, west pins still mirrored) | **exit 1**. Pad mask, ID, structure, zero-area 0, Magic DRC 0. KLayout DRC **1155**: provider ring at the custom pad sites 620 (V3.1 / V3.2a / V4.1 / V4.2a, SO-1, pads) + inside the pad cells 285 (same via stacks, SO-1) = 905 pads; top wiring 216 (assembly; many at x = 52 um, the mirrored west-pin routes); grid 7 (assembly); inside blocks 13 (atb_leaf_s 7, isw 2, core_bias 2, cdr 2) + 2 placeholder lo_vreg. Antenna **89**: top nets 51 + at atb_leaf_s gates 16 + others (assembly: jumpers next run); adc_i 7 (converters, known); txmix 6, clk_obs 3, clockmux 1. Density 5 DCF.1a inside blocks | not run |
| Density after fill | not run | every global rule passes; 48 DCF.1a inside blocks |
| LVS (black boxes, by name; first run) | 572 match, 150 short+internal | 741 match, 138 short |

Ruling (2026-11-21): on pt_wired the macro sits at x0 = 951 with 12 um clearance to `pad_ref` and `pad_wire_tx` (the 1740 um between them; accepted for
that corner; digital is asked for a ~40 um narrower outline).
Picked up: QVCO r8 (ASM-1) on pt_rf; staged pad cells with core-edge pins (`common.STAGED_PADS`: txpad a12, wirepad b7,
pin-moved rf_pair / rftxpad / single_leg / hspad) on pt_wired; pt_rf reroute with them pending. `pad_refpad` not yet moved. Open: V4.2a / M4.1 / MT.1 in the grid, full precheck.
Owner rows ASM-1..9 in `scratch/reviews/interface-changes.md`.
