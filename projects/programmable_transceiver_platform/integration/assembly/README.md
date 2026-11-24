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
| Detailed-route violations (20 iterations); baselines 467 / 742 (rf), 1035 / 2919 (wired) | **164** (109 shorts: lna_deg_n placeholder 27, atb1_leaf18/29 35, grid 7; 55 spacing) — QVCO r8, pin-moved RF pads, orientation fixed; OpenROAD antenna check 0 | **~2400** on the option-B placement (power delivery 4.1c/d: switch pair on the east edge, pt_wiredtx8 west of it, RAIL_wired_tx Metal5 bar merged with the switches' VISL Metal5, LVS clean on that net): 1707 shorts + 946 spacing at 16 um straps, 1585 + 798 at 22 um in MC/ME/SE with the 14 decap tiles fixed inboard of pad_hs_rx. 1548 of the shorts are VSS hooks and 539 wire_tx_data in the field round pt_wiredtx8. The previous placement routed with 183 but fails IR. **Open: ASM-8** (wrx_cap / ptrim / pt_wiredtx8 free Metal5, with wired RX / TX after 2026-11-24) is the durable fix for IR and routability; straps are not iterated further |
| pt_wiredtx8 grid ties | | VSS landings 4 of 6, channel tabs 3 of 6 (the others sit on VDD axes, untied by design); 10 old pins unconnected until the conn binds the new cell |
| Shuttle precheck (pt_rf, filled, 2026-11-21; layout of the QVCO-r8 run, west pins still mirrored) | **exit 1**. Pad mask, ID, structure, zero-area 0, Magic DRC 0. KLayout DRC **1155**: provider ring at the custom pad sites 620 (V3.1 / V3.2a / V4.1 / V4.2a, SO-1, pads) + inside the pad cells 285 (same via stacks, SO-1) = 905 pads; top wiring 216 (assembly; many at x = 52 um, the mirrored west-pin routes); grid 7 (assembly); inside blocks 13 (atb_leaf_s 7, isw 2, core_bias 2, cdr 2) + 2 placeholder lo_vreg. Antenna **89**: top nets 51 + at atb_leaf_s gates 16 + others (assembly: jumpers next run); adc_i 7 (converters, known); txmix 6, clk_obs 3, clockmux 1. Density 5 DCF.1a inside blocks | not run |
| Density after fill | not run | every global rule passes; 48 DCF.1a inside blocks |
| LVS (black boxes, by name; first run) | 572 match, 150 short+internal | 741 match, 138 short |

Ruling (2026-11-21): on pt_wired the macro sits at x0 = 951 with 12 um clearance to `pad_ref` and `pad_wire_tx` (the 1740 um between them; accepted for
that corner; digital is asked for a ~40 um narrower outline).
Agreed, not yet built (no GDS staged): `pt_ptrim` r12 goes R0 with x0 = 313.05 (mod 70) so a grid VSS Metal5 strap lies on
its VSS Metal4 strap (block x 186.7-191.7, Via4 full height); that strap is 10.5 um wide over ptrim (16 um would reach
VDD_WIRE_SW); grid VDD never lands on the block.
Picked up: QVCO r8 (ASM-1) on pt_rf; staged pad cells with core-edge pins (`common.STAGED_PADS`: txpad a12, wirepad b7,
pin-moved rf_pair / rftxpad / single_leg / hspad) on pt_wired; pt_rf reroute with them pending. `pad_refpad` not yet moved. Open: V4.2a / M4.1 / MT.1 in the grid, full precheck.
Owner rows ASM-1..9 in `scratch/reviews/interface-changes.md`.

## Known violations (current)

- **Island rails** other than RAIL_wired_tx are routed nets 1.0 um wide (`route.tcl` WIDE class): far below their
  19-75 mA design currents (spec/power-delivery.md section 2): EM and IR fail. Island strap regions (`ISLAND_STRAPS=1`
  in `kl_place.py`) fragment on today's floorplan (loads 1.8-3.3 mm apart, straps cut by blocks' own Metal4/5);
  decision pending on clustering loads / more switches per island.
- LO pair: 1.2 um spacing reserved, VSS shields not drawn. Double-spacing class for clock / hs / rf nets off (pin windows).

## Island rail plan (coordinator ruling 2026-11-24; power owner review PDS-18 applied)

Scheme: one switch per island (power owner: option (c) not needed; isw_pll beside pll_vreg2), the island's loads
clustered round it in the floorplan (RF / HS signal-flow rules keep priority), a drawn Metal5 trunk (+ Metal4 where it must
cross Metal5-using blocks) from the switch's VISL bar, about 1 mA per um at the worst segment current, drawn drops onto
every load above about 1 mA, 1 um routed leaves for the rest. Currents: `spec/budgets/power-budget.json`
instance_worst_ma (per instance, with source), else pd2_reconciliation rows.

**pt_rf**

| Island | Switch | Bar loads (> 1 mA, worst mA) | Leaf loads (<= 1 mA) | Island mA | Trunk at 1 mA/um |
|---|---|---|---|---|---|
| conv | isw_conv | adc_i 6.3, adc_q 6.3, dac_i 2.3, dac_q 2.3, refbuf 1.6 | 3 | 18.9 | 19 um |
| debug | isw_debug | vco_replica 11.8, clk_obs 5.1, rx_aux_clk 5.1, bb_tap_i 1.0, bb_tap_q 1.0 | 10 | 24.7 | 25 um |
| lo | isw_lo | lo_vreg 27.5 | 1 | 27.6 | 28 um |
| lod | isw_lod | lo_mmd 34.8, lo_ext 13.7, lo_mmd_qdum 10.0, lo_obs 8.0, lo_obs_q 8.0, qvco 4.0 | 0 | 78.6 | 79 um |
| pll | isw_pll | pll_vreg2 20.9, prescale 2.4, prescale_hf 2.4, prescale_conv 2.4, cdr 2.0 | 5 | 30.6 | 31 um |
| rf_rx | isw_rf_rx | lna 21.4, bbfilter_i 5.3, bbfilter_q 5.3, rxmix_i 3.1, rxmix_q 3.1 | 2 | 38.4 | 38 um |
| rf_tx | isw_rf_tx | rfdriver 24.3, lo_txbuf 10.0, txmix_i 2.0, txmix_q 2.0, txsum 2.0 | 0 | 40.4 | 40 um |

**pt_wired**

| Island | Switch | Bar loads (> 1 mA, worst mA) | Leaf loads (<= 1 mA) | Island mA | Trunk at 1 mA/um |
|---|---|---|---|---|---|
| debug | isw_debug | vco_replica 11.8, clk_obs 5.1, rx_aux_clk 5.1, rx_wtx_ext 5.1, bb_tap_wmon 1.0 | 12 | 28.8 | 29 um |
| pll | isw_pll | pll_vreg2 20.9, prescale 2.4, prescale_hf 2.4, cdr 2.0, clockmux 1.6 | 12 | 29.4 | 29 um |
| wired_cap | isw_wired_cap | wrx_cap 46.6, ptrim 21.0, wordclk_rx 2.4 | 0 | 70.1 | 70 um |
| wired_rx | isw_wired_rx | slicer 9.8, ctle 5.3, detect 2.4, rxselect 2.0, termination 1.6 | 6 | 22.0 | 22 um |
| wired_tx | isw_wired_tx_a, isw_wired_tx_b | wiredtx 60.0, pad_wire_tx 21.0, usb_txdrv 20.0, term_buffer 2.0 | 10 | 103.6 | 104 um |

Flags (PDS-18): pt_rf lod island ~79 mA on an 80 mA master (tight); rf_tx 42.8 mA design against the 40 mA isw_debug
master until lo_txbuf is measured: room for an isw_rf (55 mA) footprint kept at the switch.
