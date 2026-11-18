# Shuttle acceptance flows (wafer.space Run 3, GF180MCU)

Current state only. Everything here runs on a **skeleton chip**: the real 1x1 pad ring, seal ring and ID cells, the
custom pad families, every block that has a GDS, and pin-only placeholders for the rest, with **no top-level wiring**.
The flows are ready for the real top; the numbers below are the skeleton's.

Work directory (not in git, large): `scratch/integration/signoff-run/` (`SIGNOFF_RUN` overrides). Machine rule: every
script runs one heavy job, at most 4 threads; run at most two at once.

## How to run

```
python3 skeleton/plan.py && ./kl.sh skeleton/build.py       # skel/pt_chip_skel.gds + manifest.json (seconds)
fill/run_fill.sh rf 2                                        # keep-out set none|must|rf|analog|allblocks -> fill/rf_filled.gds (2 min)
drc/run_all.sh fill/rf_filled.gds pt_chip_top skel_rf_filled # density, antenna, main deck (shuttle PDK deck, KLayout 0.30.9)
python3 drc/locate.py <run>/drc/<tag>/report.lyrdb.gz        # violations per rule and per block
precheck/run_precheck.sh <abs gds> pt_chip_top <new workdir> 4 && python3 precheck/summarise.py <workdir>   # the shuttle's own precheck
lvs/run_controls.sh                                          # LVS proof: routed fixture passes, three broken variants fail
python3 lvs/gen_netlist.py <run>/lvs/pt_chip_top.ref.spice   # reference netlist from integration/top/pt_chip.conn
./kl.sh lvs/top_lvs.py -rd gds=skel/pt_chip_skel.gds -rd top=pt_chip_top -rd ref=lvs/pt_chip_top.ref.spice \
        -rd out=lvs/skel -rd manifest=skel/manifest.json -rd flatten=retained_provider_ring -rd skip=digital   # 1 min
```

| Path | What |
|---|---|
| `env.sh`, `kl.sh` | tool image and PDK deck locations; KLayout batch wrapper |
| `skeleton/` | `plan.py` (what goes where), `build.py` (assembly), `floorplan-skel.json` (frozen packing used) |
| `fill/` | `run_fill.sh`, `keepout.py`, `keepouts.json` (keep-out policy by master, with the reason), `fill_in_blocks.py` |
| `drc/` | `run_drc.sh`, `run_all.sh`, `locate.py`, `count_lyrdb.py` |
| `lvs/` | `gen_netlist.py`, `top_lvs.py`, `fixture.py`, `run_controls.sh`, `pin_audit.py` |
| `precheck/` | `run_precheck.sh`, `summarise.py`, `NOTES.md` (environment, step list), `pdk-diff.md` (792ef67 vs f6eeac7) |

## Skeleton

- Base: `analog/pads/generated/packaging-assembly.gds` (provider ring, seal ring, QR / shuttle / project ID cells,
  marker). Die 3932 x 5122 um, top cell `pt_chip_top`.
- Floorplan: `skeleton/floorplan-skel.json`, a run of the die-fit packer on a copy (scenario B sizes, macro
  1716 x 1640, no decap bank, 6 um halo, reservations and the three RF-FET characterisation cells dropped, QVCO at its
  published 898 x 653). It is not a legal floorplan; it exists so that most blocks with a GDS are in.
- Pads: the eleven custom families at the die-fit positions, snapped along the edge onto the template's bond openings
  (golden mask of the precheck). All 74 openings are open, none extra.
- Digital macro: the AC1_R4 hardening (1716 x 1455) as a stand-in. Its pins are not the current macro's.
- A block is placed as real GDS if a published or staged GDS fits its rectangle, otherwise as a placeholder cell named
  like the master (outline on 0/0, one 2 x 2 um Metal4 pin per netlist pin).

Build of 2026-11-18: 205 placed cells = 65 published, 109 from scratch support directories (island switches, ATB
leaves, iso clamps, core bias, digital stand-in), 9 staged (adc_i/q, dac_i/q, clk_obs, lo_ext, lo_mmd_qdum, lo_obs,
wrx_cap; the Q converters use the I cell), 18 placeholders (agnd_tie, bias_ext, ctle, 7 iso_clamp_x4, 2 iso_pd, lna,
lna_ind_p, lo_vreg, ptrim, refvcm, txpad_bias), 4 reservations. **Left out, no room:** pll_tx, pll_cdr, lo_mmd,
term_buffer, lna_ind_n, lna_deg_p, lna_deg_n. Not in the floorplan at all: the three RF-FET characterisation cells,
steer_0..3. `lna` was real GDS in the morning builds and became a placeholder when `rf_rx/generated/lna.gds` changed size
under the open LNA redesign; the fill and DRC numbers below include the real LNA.

## Fill and density

Fill = the shuttle PDK's `fill_all.rb` (792ef67), unmodified, on the whole die: 107-114 s with 2 threads, 0.9 GB.
Keep-outs are top-level marker boxes over instances, chosen by `keepouts.json`: **PMNDMY** (no dummy metal) on
sensitive blocks, **PMNDMY + IND_MK** on inductors (no dummy COMP / Poly2, exempt from DCF.1a). Whole-block **NDMY is
not usable**: main-deck rule DE.3 limits an NDMY shape to 15 000 um2 and DE.4 wants 20 um between them (blanket NDMY
gave 95 x DE.3, 1 x DE.4).

Density deck of the shuttle PDK (limits: COMP 25-70, Poly2 >= 14, metals >= 30), percent of the die:

| Keep-out set | blocks / mm2 | COMP | Poly2 | M1 | M2 | M3 | M4 | M5 | DCF.1a |
|---|---|---|---|---|---|---|---|---|---|
| no fill | - | 24.1 | 16.5 | 23.9 | 21.9 | 30.4 | 31.9 | 31.2 | 1317 (+ DCF.1b, M1.4, M2.4) |
| none (stock fill) | 0 | 41.7 | 34.2 | 39.6 | 36.2 | 44.4 | 46.1 | 42.2 | 34 |
| must: inductors | 3 / 0.79 | 40.8 | 33.0 | 38.8 | 35.4 | 43.6 | 45.3 | 41.7 | 35 |
| rf: + LNA, mixers, PA, LO, rings | 14 / 1.28 | 40.9 | 32.6 | 38.1 | 35.0 | 43.1 | 44.9 | 41.4 | 35 |
| analog: + converters, filters, bias, samplers, clocks | 34 / 4.63 | 35.7* | 27.1* | 34.7 | 31.9 | 40.4 | 42.0 | 38.6 | 17* |
| allblocks: everything but macro and pads | 189 / 6.34 | 33.8* | 24.4* | 32.5 | 30.2 | 38.8 | 40.5 | 37.4 | 0* |

`*` run with blanket NDMY (the first policy): COMP / Poly2 are lower bounds and DCF.1a is hidden by NDMY, which DE.3
forbids. The `rf` row is the current policy (PMNDMY, IND_MK on inductors); its metal columns equal the NDMY run.
Every set passes every global rule; Metal2 is the first to go (30.2 % with every block excluded, limit 30).
Dummy-rule decks (`dummy,dummy_exclude`: 42 rules DCF.*, DPF.*, DM*.*, DE.*) on the `rf` fill: **0** (669 s).

**DCF.1a after fill, 35 items, all inside four blocks** (20-50 um wide bands that hold Poly2 wiring and no COMP, so
the filler cannot place dummy COMP): pt_wrx_cap 17, pt_slicer 8, pt_wiredtx 8, pt_vco_replica 2.

What stock fill puts into the sensitive blocks (`fill_in_blocks.py`, dummy share of the block outline): QVCO 8-15 %
per layer (1186-2013 metal dummies per layer, 334 COMP, 303 Poly2 tiles), ADC 10-27 %, bbfilter 12-27 %, LNA 2-14 %,
mixers 4-14 %, rings/prescalers 4-25 %. Full table: `<run>/fill/fill_in_blocks.json`.

The digital stand-in and the placeholders are filled like open area; 7 blocks (1.0 mm2 or so) are missing. The real chip
will have less open area and more drawn metal than this.

## DRC

Filled skeleton (`rf` set, first policy), shuttle deck 792ef67 on KLayout 0.30.9, 1 worker:

| Deck | Time | Result |
|---|---|---|
| density | 466 s | 34 x DCF.1a (above) |
| antenna | 587 s | 0 |
| main `all,-antenna,-density,-cup` | 4558 s | 1593: V3.1 408, V4.1 408, V3.2a 340, V4.2a 340, DE.3 95, DE.4 1, M4.2a 1 |

- **Via3 / Via4 (1496):** 12 x V3.1/V4.1 and 10 x V3.2a/V4.2a per bond site, at all 34 sites where a custom pad family
  sits on the provider rail cell (`5LM_METAL_RAIL`). The family alone is clean and the unfilled skeleton gives the same
  1496, so it is the overlap: with the bond opening on the template mask the family's via arrays are 175 nm off the
  rail cell's (`skeleton/pad_align.py`).
- **DE.3 / DE.4 (96):** the blanket NDMY keep-outs of the first policy; gone with the current one.
- **M4.2a (1):** in the seal-ring corner at (4.0, 5.1), as delivered in the base ring GDS.
- No violation inside any analog block or the digital stand-in.

`locate.py` attributes by cell (the deck is hierarchical: a violation is reported in the cell it occurs in).

## LVS

`top_lvs.py` extracts Metal1-5, Via1-4 and the MIM top plate hierarchically through every cell of the GDS on disk and
keeps only the pins of the black boxes (every direct child of the top). A top wire on unlabelled block metal becomes a
nameless pin; two pins joined inside a block become one pin. It then compares twice: KLayout's netlist compare
(topological, black-box pins by name) and, with the manifest, net by net by name (open / short / internal).
Reference: `gen_netlist.py`, flat from `pt_chip.conn`, one empty subckt per master with the published pin list.

- Engine check on real routed data: `pt_core_bias_routed.gds` (37 leaf instances, 152 nets) against the routing
  flow's own schematic: match; with two nets swapped on one instance: 2 net mismatches.
- `run_controls.sh` (20 instances out of the skeleton GDS: 12 published cells, 3 support cells, 5 placeholders; 10
  multi-pin nets from the conn routed on Metal4/5 by `fixture.py`, 13 mm of wire): **positive control PASS** (139 nets,
  20 subcircuits match; 91 nets by name). **Negative controls all FAIL as required:** two nets swapped on
  `iso_cdr_up_0` (VDD / VSS) -> 2 nets open+short; one Via4 removed -> VSS open in 2 pieces; a Metal4 strap across
  `pt_aosc` -> VDD-VSS short.
- Skeleton (unrouted), 63 s: FAIL as it must. 1359 reference nets; 200 of 241 instances bound to a layout cell;
  24 + 12 nets match, 301 open, 871 have one bound pin only (other end in the digital macro or the pad ring), 4 open +
  short. Pin labels: 77 of 80 cells carry every netlist pin as a label in their top cell (`pin_audit.py`).

## Precheck

The shuttle's own flow runs here natively: gf180mcu-precheck 1.7.4, KLayout 0.30.12, Magic 8.3.677, LibreLane
3.1.0.dev3, PDK 792ef67, from the flake's pinned nix closure inside docker (`precheck/NOTES.md`: build, the 17 steps
and which are gating). `precheck/pdk-diff.md`: 792ef67 against the project's f6eeac7.

Run on the filled skeleton (`--slot 1x1 --cob --id DEADBEEF --workers 1 --threads 4`, about 2 h 55 min, exit 1):

| Step | Result | Time |
|---|---|---|
| read, top cell, size / dbu / Metal5 max / guard-ring marker, pad mask (74 openings), ID cells | pass | seconds |
| density (gating) | **34 x DCF.1a** | 7 min |
| zero-area polygons | 0 | 16 s |
| antenna (gating) | 0 | 42 min |
| Magic DRC (warning only) | 0 | 20 min |
| KLayout DRC (gating) | **1593**: V3.1 408, V4.1 408, V3.2a 340, V4.2a 340, DE.3 95, DE.4 1, M4.2a 1 | 1 h 43 min |

Per rule the same counts as the project's KLayout 0.30.9 with the shuttle deck on the same file. The precheck maps
dummy metal and poly onto the drawing layers before checking; that added nothing here.
PDK difference in short: 5 DRC rule files (DCF.1a new, DF.11, CO.5a/b re-implemented), fill scripts, LVS deck parts,
Magic tech paint/GDS rules; device models numerically identical; all 1424 library cells XOR-identical; 10 published
blocks 0 violations under project and shuttle tools and both cross combinations; 4 blocks extract to the same
devices. KLayout 0.30.12 and 0.30.9 disagree in hierarchical mode on DF.14 / DF.16 / DF.19 counts on the PDK's test
layout (not on our data so far).

## Known failures and gaps

Would fail the precheck today (rows SO-1..7 in `scratch/reviews/interface-changes.md`):
1. Via3 / Via4 at every custom pad site (1496), pads: SO-1.
2. DCF.1a inside pt_wrx_cap, pt_slicer, pt_wiredtx, pt_vco_replica (34-35): SO-3.
3. M4.2a x 1 in the seal-ring corner of the base ring GDS (assembly: rebuild the ring from the current template).
4. DE.3 / DE.4 only if NDMY is drawn over whole blocks: SO-2.

Not done:
- No real top exists: no wiring, 7 blocks do not fit, 18 placeholders, digital stand-in. Antenna = 0 and LVS say
  nothing about the routed chip.
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
