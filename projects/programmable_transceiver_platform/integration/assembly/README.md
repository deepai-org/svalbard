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

## Pre-route check (`preroute.sh`) and custom pad finalizer (`pad_cup.py`)

- `preroute.sh <chip>` (after place / lint, before route): one window per block and custom pad of `placed.gds`
  (bbox + 15 um) with everything the top level drew before routing (provider ring, `pt_pdn`, island bars, plates, landings,
  pads, neighbours), BEOL layers only (Metal2-5, Via2-5, Pad). Runs the signoff deck (shuttle 792ef67, rule decks
  `beol,-antenna,-density,-cup`) on the windows (`preroute_win.py build`), maps every marker back to chip coordinates and
  classes it (`preroute_win.py attr`): `context` (touches top-level metal or a second instance on the rule's layers; gated)
  or `internal` (the block alone; reported). Then `grid_conn.py` on `placed.gds` (`GC_GDS` / `GC_MAN`): every block / pad
  VDD / VSS pin on a pad-fed grid piece unless a router hook feeds it. `PREROUTE PASS` / `FAIL`; `PREROUTE_ACCEPT=<rules>`
  accepts classes; `only=<inst>` checks single windows in a few minutes. Output `$RUN/preroute/`.
- `preroute.sh <chip> selftest`: a clean window passes; the same window with a drawn Via4 overlap, Via3 overlap or
  Metal5 spacing fault fails; the published `pad_txpad` (PAD-16, `PAD_FIX=0`) fails.
- `pad_cup.py` is applied to every custom pad family when it is imported (`kl_abstract`, `kl_place`; `PAD_CUP=0` turns it
  off) and standalone (`python3 pad_cup.py in.gds out.gds`): under each Pad opening only the stock `Bondpad_5LM` stack
  (generator shapes cut out, stock plates and 0.26 um via arrays put back, best of 8 orientations), and no pad Via3 / Via4
  in the provider-ring rail band (pad-local y 69.5-348.9 um, the same in every pad site; PAD-16). Acceptance: precheck
  `cup_audit.py` (precheck-1128) clean on all 14 openings, KLayout-extracted netlist of each pad identical before / after.

## Results and resume point (2026-11-26)

| | `pt_rf` | `pt_wired` |
|---|---|---|
| Last verified (committed) | b1c40f20: 2 DRT; LVS by name 801 match, no short / open (VDD, VSS one net each); deck antenna 22 (ANT.6 13 `c_lo_mmd_en`, ANT.5 7 `PLL_TX_FBCK`, ANT.12 2 at isw_rf_rx / isw_pll), main DRC 3 (V1.2a 2 por VDD hook, M4.2b 1) | none on current inputs (last clean: 11-24, old macro + wrx_cap r6) |
| In progress (uncommitted, assembly agent 1) | DG9-29 macro with its Metal5 straps carried to the grid (`kl_place` macro supply, `macro supply OK` 19/19 VDD, 18+1 VSS); ME straps 15 um; SE lo_lf / qvco grid stitch (`common.GRID_STITCH`); antenna diodes on `PLL_TX_FBCK`, `c_lo_mmd_en`. Run 11-26: 2 DRT, no VDD/VSS short, KH-3 shorts gone (they came from a 400 um macro-strap reach and ME 21 um; now 100 um / 15 um); grid_conn MACRONET and deck pending | DG9-29 run 11-26: VDD-VSS short through router wiring (24 DRT: `ISO_wired_tx`, `s_pg_wired_tx_b` into the grid below isw_wired_tx_a/_b, `VDD__HK71`, RAIL_wired_tx at the bar edge); main DRC 6406 (Via3/Via4 rules in pad_txpad / wiredtx8 / bar), antenna 256. Next: rerun on DG9-30 (drop-in) and clear those shorts |

**Chip killers and owners:** PDS-25 #1 (macro supply never reached the grid) and #3 (grid coverage / stitch): this agent (assembly 1).
PDS-25 #2 (switch and heavy-load supply plates, island trunks, block mirroring / FACE_IN): assembly agent 2 (`island_trunks.py`, its rows).
KH-1 / KH-2 (macro `c_*` ports unwired, pad tie-offs, output pads; `check_conn.py`, the `check` stage): top-connectivity agent (rows KH-1..3).

**Open (assembly 1, ranked):** (1) commit pt_rf macro straps once grid_conn MACRONET=1 and the deck confirm; (2) pt_wired on DG9-30: the
router shorts at isw_wired_tx_a/_b, LVS, deck, precheck; (3) pt_rf last DRC (por hook V1.2a, one M4.2b) and antenna tail (ANT.12 owner TBD).

**Flow knobs (recent):** `ASM_RUN` is required (run.sh refuses the shared default dir); `PLATES=1`, `TRUNKS=1`, `FACE_IN=1` (island_trunks.py,
agent 2, off by default); `HOOK_W` (hook width, default 0.56); route stops when it writes no routed.def; second antenna pass after detailed
route, retried with `-no_pin_access` and kept only if it completes; `common.HOOK_SLOT_AVOID` (grid slots no hook takes: DRT-1231 after the
jumpers); `common.GRID_STITCH`; `common.ANT_DIODE` / `ANT_TIGHT`; macro supply straps (`MSTRAP_EXT` 30 um / `MSTRAP_W` 10 um, reach to the
first same-net vertical strap within 100 um) and the `macro supply OK / MACRO SUPPLY OPEN` check printed by place and repeated by `lvs`.

**Gotchas:** every agent uses its own `ASM_RUN` (a run without it once overwrote route/chip/lvs/drc of another agent's placement); several
agents share these scripts in one working tree, so commit your own hunks only (private index) and rebase first; check `df` before a heavy
cycle (the disk filled on 11-26 and jobs died); a run's wait loop must read the run's own PID; never start a second run on a chip while its
LVS / DRC reads chip/pt_chip_top.gds; the abstract stage must rerun whenever a block GDS or the macro LEF changes; `kl_shortcheck.py
[drop cells]` (drop `pt_top_wiring` to see if a short is router wiring) and `kl_netprobe.py NET` localise joins; grid_conn.py MACRONET=1
(scratch/integration/m1-pdn) audits macro stripes against the pad-fed grid.

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
