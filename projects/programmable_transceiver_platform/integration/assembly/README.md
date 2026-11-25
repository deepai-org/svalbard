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

## Results and resume point (2026-11-25, flow 8a7cc92b)

| | `pt_rf` | `pt_wired` |
|---|---|---|
| Inputs | DG9-28 macro, ASM-16 diode cells (ATB PDS-23, converters PDS-24, RF ASM-16a), RF RX ASM-RF-2 cells | indicative only: wrx_cap r6 + old macro (11-23 LEF); real run waits for DG9-25 macro + wrx_cap r8 (TIM-35) |
| Floorplan | ASM-15 ruling: lna_deg_p 5 um from lna; isw_rf_tx_b (1876, 2994) and char_rffet placed by hard pass 2 (decap / ATB / iso give way, re-placed); decap ~3.7 nF (21/26 bank cells, 17-18/30 tiles), 0.83 nF within 500 um of the rf_rx loads | packer; clustering off |
| Route / LVS by name | 2 DRT; 801 match, no short, no open (VDD, VSS one net each; por internal label only) | 5 DRT; 971 match, no short; open pad_tlp VDD/VSS (not investigated), s_pg_wired_tx_b (digital) |
| Deck (shuttle 792ef67, `signoff/drc/run_drc.sh`) | main DRC 4 (M4.2b 2, V1.2a 2); antenna 182 (ANT.5 143: c_bbfilter_i_en, BIAS_rfdriver, ADCI_CODEB/OVL, CLK_OBS_DBG; ~39 inside blocks / pad ring, ~13 in the macro); full precheck last run on b98f21a6 (DRC 180, antenna 2483, Magic 0, density 0) | not run |

**Open items (ranked):** (1) pt_rf antenna tail: standard-cell antenna diodes (gf180mcu_fd_sc_mcu7t5v0__antenna) at the receivers of the
remaining nets (router jumpers no longer reduce ANT.5); in-block items to owners as a row. (2) last 4 pt_rf DRC. (3) pt_wired on DG9-25 +
r8, pad_tlp open, then precheck. (4) check_top both chips, push. (5) Island trunks (PDS-19/20; rf_tx trunk to isw_rf_tx_b), LO floorplan
(lo_ext -> lo_txbuf ~2.5 mm, rxmix_i/q apart; fit.py fixes positions), grid dead metal.

**Flow knobs added 2026-11-24/25 (common.py / kl_place.py / kl_abstract.py / route.tcl):** PIN_UP (por pins on own Metal4/5), labels that are
not conn pins stay obstruction, label pins by containment, PIN_GATE_UM2 = 0.4 + ANT_TIGHT nets (0.02 um2 receiver gates) for the router antenna
model, NOROT / PASS2 / HARD_NEXT_TO (partner, max gap) with decap / ATB / iso give-way and re-placement, PIN_WINDOWS (grid 3 um off signal
pins), ISLAND_BARS expose=True (bar = rail pin, switch VISL off the routed net), rel 'bbox' / 'pin:NAME', bar slots (MSLOT5.1), direct Via4
landings only with >= 4 cuts or a cut row on thin strips, hook slots only on ring-joined grid metal (Via4-sized overlaps) and never over a
block, ring filler / rail / CDNS cells and the IO strip blocked, wide-metal obstruction +0.5 um (M4.2b / MT.2b), MIM keep-out (FuseTop +
2.3 um) on Metal4, island switches Metal2-3 halo, DRT 64 iterations, second antenna pass, ISL_CLUSTER off by default.

**Gotchas:** a run's wait loop must read the run's own PID (route deletes routed.def, so file-age checks pass early); never start a second
run on a chip while its LVS / DRC reads chip/pt_chip_top.gds (LVS runs in an unnamed container: find it by its volume); the abstract stage
must rerun whenever any block GDS or the macro LEF changes (check timestamps vs masters.json); `kl_netprobe.py NET` (HALO=0) and
`kl_shortcheck.py [drop cells]` localise joins; antenna attribution: match deck polygons to routed.def segments (see this session's
scratch scripts); pt_rf decap total is an estimate from the power-delivery per-cell figures.

Tools: `kl_shortcheck.py [drop-cell ...]` (VDD/VSS one net, with cells removed: `pt_top_wiring`, `pt_direct_land`),
`kl_netprobe.py NET ...` (non-router shapes a routed net touches; `HALO=0` for overlaps only). Block pins in the abstract are
the label's own polygon; `common.PIN_UP` masters (por) also get their own Metal4/5 of the pin net. LVS (`signoff/lvs/top_lvs.py`)
merges reference nets through declared DC joins (LNA inductors, QVCO tank) when the layout shows them.

## Known violations (current)

- **Island rails** other than RAIL_wired_tx are routed nets 1.0 um wide (`route.tcl` WIDE class): far below their
  19-75 mA design currents (spec/power-delivery.md section 2): EM and IR fail. Island strap regions (`ISLAND_STRAPS=1`
  in `kl_place.py`) fragment on today's floorplan (loads 1.8-3.3 mm apart, straps cut by blocks' own Metal4/5);
  decision pending on clustering loads / more switches per island.
- LO pair: 1.2 um spacing (LOSH), VSS shields not drawn; LO nets not yet kept >= 200 um from LNA / spirals / RF pad / QVCO (ASM-RF-1). Double-spacing class for clock / hs / rf nets off (pin windows).

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
| rf_tx | isw_rf_tx (isw_wired master) | rfdriver 24.3, lo_txbuf 19.3, txmix_i 2.0, txmix_q 2.0, txsum 2.0 | 0 | 45.6 / 56.5 | 57 um |

**pt_wired**

| Island | Switch | Bar loads (> 1 mA, worst mA) | Leaf loads (<= 1 mA) | Island mA | Trunk at 1 mA/um |
|---|---|---|---|---|---|
| debug | isw_debug | vco_replica 11.8, clk_obs 5.1, rx_aux_clk 5.1, rx_wtx_ext 5.1, bb_tap_wmon 1.0 | 12 | 28.8 | 29 um |
| pll | isw_pll | pll_vreg2 20.9, prescale 2.4, prescale_hf 2.4, cdr 2.0, clockmux 1.6 | 12 | 29.4 | 29 um |
| wired_cap | isw_wired_cap | wrx_cap 46.6, ptrim 21.0, wordclk_rx 2.4 | 0 | 70.1 | 70 um |
| wired_rx | isw_wired_rx | slicer 9.8, ctle 5.3, detect 2.4, rxselect 2.0, termination 1.6 | 6 | 22.0 | 22 um |
| wired_tx | isw_wired_tx_a, isw_wired_tx_b | wiredtx 60.0, pad_wire_tx 21.0, usb_txdrv 20.0, term_buffer 2.0 | 10 | 103.6 | 104 um |

Currents are PDS-19 (power owner, 2026-11-24, worst / design mA from power-budget.json pd2_reconciliation); every trunk is
sized on the **design** figure: pt_rf rf_rx 43.6, rf_tx 56.5, lod 74.1 (keep the 79 um trunk), lo 28.1, pll 30.7, conv 18.7,
debug 40; pt_wired wired_cap 72.9, wired_tx 131.3 (2 x isw_wired), wired_rx 30.9, pll 29.4, debug 40. Where a table row is
lower than its PDS-19 design figure, the PDS-19 figure governs. lod and rf_tx run on isw_wired masters (CB8-16).
