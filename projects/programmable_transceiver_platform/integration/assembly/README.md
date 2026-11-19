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
| abstract | `kl_abstract.py` | Template ring + seal + ID cells; custom pad families placed with their bond openings exactly on the golden-mask openings of their `bond_map.txt` sites; provider `dvdd`/`dvss` cell at every signal site bonded VDD/VSS (D-SPLIT-SUPSITE, PC-35); LEF abstract of every master that has a GDS | `ring.gds`, `pads.json` (real footprints), `masters.json`, `lef/` |
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
- **Power grid** (`spec/power-delivery.md` G1/G2/G8): core ring VDD outer / VSS inner, 2 x 14 um on Metal4 + Metal5,
  following the free boundary round the pad families; VDD/VSS strap pairs at 70 um pitch, 10.5 um each, Metal4
  horizontal and Metal5 vertical, cut 2.5 um from any block Metal4/5, 8 um round no-route-over blocks, Metal4 cut over the
  macro; Via4 arrays at every same-net crossing; Metal2 stubs + Via2/Via3 from every supply cell into its ring. Block
  VDD/VSS pins reach the grid through hook nets (one 20 um slot of the nearest same-net strap each) that the router draws.
- **Net classes** (`kl_place.cls`): island rails / regulator outputs 3 um wide; hooks 1.2 um; clock, high-speed and RF
  nets twice the minimum spacing (no drawn shields). Booked ledger items without a conn instance are Metal1-3 blockages.

## Results (latest run)

See the per-chip table at the end of this file (written by hand from `report/route.json` after each run).
