# Shuttle acceptance flows (wafer.space Run 3, GF180MCU)

Current state only. Everything here runs on a **skeleton chip**: the real 1x1 pad ring, seal ring and ID cells, the
custom pad families, every block that has a GDS, and pin-only placeholders for the rest, with **no top-level wiring**.
The flows are ready for the real top; the numbers below are the skeleton's.

Work directory per chip (not in git, large): `scratch/integration/signoff-run-<chip>/` (`SIGNOFF_RUN` overrides); every
script takes the chip from `SIGNOFF_CHIP=rf|wired`. The precheck tool tree stays shared (`scratch/integration/signoff-run/pc`,
`PC_ENV`). Machine rule: every script runs one heavy job, at most 4 threads; run at most two at once.

## How to run

```
export SIGNOFF_CHIP=rf                                       # or wired
python3 skeleton/from_fit.py $SIGNOFF_CHIP <die-fit run json> # freeze a packing as skeleton/floorplan-<chip>.json
python3 skeleton/plan.py && ./kl.sh skeleton/build.py       # skel/pt_chip_skel.gds + manifest.json (seconds)
fill/run_fill.sh rf 2                                        # keep-out set none|must|rf|analog|allblocks -> fill/rf_filled.gds (2 min)
drc/run_drc.sh fill/rf_filled.gds pt_chip_top density skel_rf_filled_density   # one deck selection (density, antenna, main)
drc/run_all.sh fill/rf_filled.gds pt_chip_top skel_rf_filled # density, antenna, main deck (shuttle PDK deck, KLayout 0.30.9)
python3 drc/locate.py <run>/drc/<tag>/report.lyrdb.gz        # violations per rule and per block
precheck/run_precheck.sh <abs gds> pt_chip_top <new workdir> 4 && python3 precheck/summarise.py <workdir>   # the shuttle's own precheck
lvs/run_controls.sh                                          # LVS proof: routed fixture passes, three broken variants fail
python3 lvs/gen_netlist.py <run>/lvs/pt_chip_top.ref.spice --chip $SIGNOFF_CHIP   # reference netlist from the chip conn
./kl.sh lvs/top_lvs.py -rd gds=skel/pt_chip_skel.gds -rd top=pt_chip_top -rd ref=lvs/pt_chip_top.ref.spice \
        -rd out=lvs/skel -rd manifest=skel/manifest.json -rd flatten=retained_provider_ring -rd skip=digital   # 1 min
```

| Path | What |
|---|---|
| `env.sh`, `kl.sh` | tool image and PDK deck locations; KLayout batch wrapper |
| `skeleton/` | `from_fit.py` (freeze a die-fit packing), `plan.py` (what goes where), `build.py` (assembly), `floorplan-<chip>.json` (frozen packing per chip) |
| `fill/` | `run_fill.sh`, `keepout.py`, `keepouts.json` (keep-out policy by master, with the reason), `fill_in_blocks.py` |
| `drc/` | `run_drc.sh`, `run_all.sh`, `locate.py`, `count_lyrdb.py` |
| `lvs/` | `gen_netlist.py`, `top_lvs.py`, `fixture.py`, `run_controls.sh`, `pin_audit.py` |
| `precheck/` | `run_precheck.sh`, `summarise.py`, `NOTES.md` (environment, step list), `pdk-diff.md` (792ef67 vs f6eeac7) |

## Skeleton

- Base: `analog/pads/generated/packaging-assembly.gds` (provider ring, seal ring, QR / shuttle / project ID cells,
  marker). Die 3932 x 5122 um, top cell `pt_chip_top`.
- Floorplan per chip: `skeleton/floorplan-<chip>.json`, the as-built (S) packing of the chip's die-fit run
  (`scratch/reviews/die-fit/run/<chip>/fit-s.json`, frozen with `skeleton/from_fit.py`): macro at the synthesized outline,
  decap bank and tiles, 10 um halo. Every block of the chip conn is placed; it is not a legal floorplan (no wiring).
- Pads: the chip's custom families at their `bond_map.txt` sites, snapped along the edge onto the template's bond
  openings (golden mask of the precheck). All 74 openings are open, none extra. The supply / ground bonds on signal sites
  keep the template's provider cell there (no supply cell yet: D-SPLIT-SUPSITE).
- Digital macro: the AC1_R4 hardening (1716 x 1455) is the only exported macro; it does not fit either chip outline and
  is a placeholder of the outline (no hardening of the chip configurations yet).
- A block is placed as real GDS if a published or staged GDS fits its rectangle, otherwise as a placeholder cell named
  like the master (outline on 0/0, one 2 x 2 um Metal4 pin per netlist pin). Decap bank and tiles are placeholders.

Builds of 2026-11-19 (`signoff-run-<chip>/skel/manifest.json`):

| | `pt_rf` | `pt_wired` |
|---|---|---|
| published / support (scratch) / staged GDS | 46 / 86 / 8 | 48 / 86 / 1 |
| placeholders: decap bank + tiles / others | 56 / 20 (digital, lna (its working-tree GDS changed size), lna_ind_p/n, lna_deg_p/n, lo_vreg, bias_ext, refvcm, 7 outside clamps, pd_clk_obs, booked items) | 69 / 20 (digital, ctle, ptrim, wiredtx, wtx_ser8d, wtx_mux8, bias_ext, refvcm, txpad_bias, 4 outside clamps, iso_wmon, pd_clk_obs, booked items) |
| left out / not in the floorplan | 0 / 0 | 0 / steer_0..3 (retire with the new transmit path) |

## Fill and density

Fill = the shuttle PDK's `fill_all.rb` (792ef67), unmodified, on the whole die (31 s on `pt_rf`, 97 s on `pt_wired`, 2
threads). Keep-outs are top-level marker boxes over instances, chosen by `keepouts.json`: **PMNDMY** (no dummy metal) on
sensitive blocks, **PMNDMY + IND_MK** on inductors (no dummy COMP / Poly2, exempt from DCF.1a). Whole-block **NDMY is
not usable**: main-deck rule DE.3 limits an NDMY shape to 15 000 um2 and DE.4 wants 20 um between them. The `rf` set
(inductors + LNA, mixers, PA, LO, rings) is the current policy: 19 instances / 1.86 mm2 on `pt_rf`, 5 / 0.38 on
`pt_wired`.

Density deck of the shuttle PDK on the filled skeletons (limits: COMP 25-70, Poly2 >= 14, metals >= 30), percent of the die:

| Chip | COMP | Poly2 | M1 | M2 | M3 | M4 | M5 | DCF.1a |
|---|---|---|---|---|---|---|---|---|
| `pt_rf` | 42.6 | 37.0 | 39.7 | 38.7 | 46.8 | 48.0 | 42.1 | 3: pt_pll_ring, pt_pll_ring_core, pt_vco_replica (1 each) |
| `pt_wired` | 43.5 | 39.3 | 43.8 | 39.9 | 47.2 | 48.1 | 41.4 | 29: pt_wrx_cap 17, pt_slicer 8, pt_vco_replica 2, pt_pll_ring 1, pt_pll_ring_core 1 |

Every global density rule passes on both chips. DCF.1a sits inside blocks (20-50 um wide bands of Poly2 wiring with no
COMP, where the filler cannot place dummy COMP): block owners (SO-3). `pt_wiredtx` is a placeholder in the `pt_wired`
skeleton (its new transmit path has no block top), so its DCF.1a items are not counted here.

The digital stand-in and the placeholders are filled like open area; the real chips will have less open area and more
drawn metal than this.

## DRC

Filled skeletons (`rf` set), shuttle deck 792ef67 on KLayout 0.30.9, 1 worker:

| Deck | `pt_rf` | `pt_wired` |
|---|---|---|
| density | 443 s: 3 x DCF.1a | 666 s: 29 x DCF.1a |
| antenna | 150 s: 0 | 443 s: 0 |
| main `all,-antenna,-density,-cup` | not run per chip (1.3 h each); see the precheck for `pt_rf` | not run per chip |

The main deck on the single-die skeleton found the pad via-array overlap (V3.1 / V4.1 / V3.2a / V4.2a at every custom pad
site on the provider rail cell, SO-1) and the seal-ring corner M4.2a; both are properties of the pad families and the
base ring and apply to both chips.

## LVS

`top_lvs.py` extracts Metal1-5, Via1-4 and the MIM top plate hierarchically through every cell of the GDS on disk and
keeps only the pins of the black boxes (every direct child of the top). Reference: `gen_netlist.py --chip <chip>`,
flat from the chip conn, one empty subckt per master with the published pin list. The routed-fixture proof
(`run_controls.sh`, positive control and three negative controls) has not been rerun on the per-chip skeletons: its
instance list (`FIXTURE`) names cells of both chips and needs a per-chip list first.

## Precheck

The shuttle's own flow runs here natively: gf180mcu-precheck 1.7.4, KLayout 0.30.12, Magic 8.3.677, LibreLane
3.1.0.dev3, PDK 792ef67, from the flake's pinned nix closure inside docker (`precheck/NOTES.md`: build, the 17 steps
and which are gating). `precheck/pdk-diff.md`: 792ef67 against the project's f6eeac7.

On the filled `pt_rf` skeleton (`--slot 1x1 --cob --id DEADBEEF --workers 1 --threads 4`, about 2 h 50 min, exit 1):
read / top cell / size / pad mask (74 openings) / ID cells pass; density 3 x DCF.1a (gating); zero-area 0; antenna 0;
Magic DRC 0; **KLayout DRC 5521** (gating). Most of them sit inside `pt_cdr` (r13, published; front-end and Metal1
rules CO.*, DF.*, NP.*, M1.2a) and `pt_diff_clk_rx`, two cells the single-die skeleton had left out; the rest are the
pad via-array overlap on the provider ring (SO-1). Owners: wired RX / timing for `pt_cdr`, timing for
`pt_diff_clk_rx` (block DRC with the shuttle deck). Summary: `precheck/summarise.py scratch/integration/signoff-run-rf/precheck`.

## Known failures and gaps

Would fail the precheck today (rows SO-1..7 in `scratch/reviews/interface-changes.md`):
1. Via3 / Via4 at every custom pad site (both chips), pads: SO-1.
2. DCF.1a inside blocks: `pt_rf` 3 (rings, vco_replica), `pt_wired` 29 (pt_wrx_cap, pt_slicer, rings, vco_replica; pt_wiredtx
   not yet in): SO-3.
3. M4.2a x 1 in the seal-ring corner of the base ring GDS (assembly: rebuild the ring from the current template).
4. DE.3 / DE.4 only if NDMY is drawn over whole blocks: SO-2.

Not done:
- No real top exists for either chip: no wiring, placeholders (decap bank and tiles, demand cells, the macro), the
  digital stand-in does not fit the chip outlines. Antenna = 0 and LVS say nothing about the routed chips.
- Supply / ground bonds on signal sites keep the template's signal cell (D-SPLIT-SUPSITE).
- LVS is black-box connectivity on metal. No device-level full-chip LVS (Magic + netgen through all blocks), no
  binding of the provider ring and macro (SO-4), substrate / well connections are not extracted, so supplies joined
  only through taps look open.
- Fill effect on circuits: only what fill lands where; no fill-aware extraction in this flow (signoff-gap has QVCO and
  ring numbers). Whether wafer.space accepts PMNDMY / IND_MK keep-outs is unanswered.
- The DF.14 / DF.16 / DF.19 difference between KLayout versions is not traced to markers.
- The example chip of wafer.space (positive control of the environment) passed density, zero-area, antenna and Magic
  DRC; its main KLayout DRC was stopped unfinished.
- `PDK_LIVE` in `env.sh` still points at the deck copy of the gap check (identical files); the complete 792ef67 tree
  is `scratch/integration/signoff-run/pc/pdk`. Nothing under `scratch/` survives a cleanup: `precheck/NOTES.md` has
  the rebuild commands.
