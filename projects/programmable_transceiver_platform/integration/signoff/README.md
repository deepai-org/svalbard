# Shuttle acceptance flows (wafer.space Run 3, GF180MCU)

Current state only. Fill, full-chip DRC, top-level LVS and the shuttle's own precheck, run on the assembled routed chip
that `../assembly` writes (`scratch/integration/assembly-<chip>/chip/pt_chip_top.gds` and `chip/manifest.json`). Every
script takes the chip from `SIGNOFF_CHIP=rf|wired`; the run directory is the assembly run (`SIGNOFF_RUN` overrides).
Machine rule: one heavy job per script, at most 4 threads, at most two heavy jobs at once.

## How to run

The assembly flow calls these as stages (`../assembly/run.sh <chip> drc | lvs | fill | precheck`). By hand:

```
export SIGNOFF_CHIP=rf
fill/run_fill.sh rf 2 chip/pt_chip_top.gds                     # keep-out set none|must|rf|analog|allblocks -> fill/rf_filled.gds
drc/run_all.sh chip/pt_chip_top.gds pt_chip_top chip            # density, antenna, main deck (shuttle deck, KLayout 0.30.9)
python3 drc/locate.py <run>/drc/<tag>/report.lyrdb.gz           # violations per rule and per block (manifest, cell_owner.json)
python3 lvs/gen_netlist.py <run>/lvs/pt_chip_top.ref.spice --chip $SIGNOFF_CHIP
./kl.sh lvs/top_lvs.py -rd gds=chip/pt_chip_top.gds -rd top=pt_chip_top -rd ref=lvs/pt_chip_top.ref.spice -rd out=lvs/chip \
        -rd manifest=chip/manifest.json -rd flatten=retained_provider_ring,pt_pdn,pt_top_wiring,VIA_*
precheck/run_precheck.sh <abs filled gds> pt_chip_top <new workdir> 4 && python3 precheck/summarise.py <workdir>
```

| Path | What |
|---|---|
| `env.sh`, `kl.sh` | tool image and PDK deck locations; KLayout 0.30.9 batch wrapper (mounts the run directory as `/run`) |
| `fill/` | `run_fill.sh` (shuttle PDK `fill_all.rb`, unmodified), `keepout.py` + `keepouts.json` (marker boxes by master), `fill_in_blocks.py` |
| `drc/` | `run_drc.sh` (one deck selection), `run_all.sh` (density, antenna, main), `locate.py`, `count_lyrdb.py` |
| `lvs/` | `gen_netlist.py` (reference from the chip conn, black boxes), `top_lvs.py` (metal extraction, compare by topology and by name), `fixture.py` + `run_controls.sh` (routed-fixture proof with three broken variants) |
| `precheck/` | `run_precheck.sh` (live shuttle precheck), `summarise.py`, block-level matrix scripts (`block_drc.py`, `block_lvs.py`, `deck_negctl.py`, `gds_cell_xor.py`, `lib_compare.py`, `model_compare.py`, `magic_drc.tcl`) |

## Signoff harness (merge gate, MANDATE 8)

`signoff.sh <rf|wired> <ASM_RUN dir> [--all] [--collect-only] [--update-baseline [--provisional] --reason "..."]`
(also `ASM_RUN=<dir> ../assembly/run.sh <chip> signoff`, extra flags in `SIGNOFF_ARGS`). Runs or collects, cheap first,
and stops at the first fail unless `--all`: `check_top` (chips/check_top.py + `--selftest` on a `git archive` of HEAD),
`drt` (route.log), `macro_supply` (place.log), `check_conn` (check_conn.py, KH_CONN=1), `lvs_name` (top_lvs.py by name:
no short except a block's own unlabelled stripe of the same net, every reference instance bound), `padsup`
(check_padsup.py), `shortcheck` (kl_shortcheck.py, no drop cells), `chip_smoke` (gate: verification/chip_smoke/signoff_hook.sh --layout, bench wired from the GDS-extracted netlist, rerun when the GDS sha differs; `SIGNOFF_SMOKE=conn` for the quick conn mode, rerun when the netlist sha differs), `grid_conn` (scratch/integration/m1-pdn/grid_conn.py
with MACRONET=1: no VDD/VSS piece, every block fed, no floating piece with a supply pin, macro stripes on their net),
`density` (before fill, reported only), `antenna`, `drc_main` (deck counts by rule), `lvs_bb` (hook:
`lvs/run_top_lvs_bb.sh` when present, else `absent`). A result in the run is collected if newer than the GDS (DRC: same
sha256 in meta.txt), else the script reruns (one heavy job at a time); `--collect-only` makes a stale result a fail.

Output `<run>/signoff/signoff.json` and a table `check | status | value | source / why`; status pass / fail /
regressed / info / absent / not run. Gates fail outright; counts (drt, lvs_name kinds, antenna and drc_main by rule,
lvs_bb kinds) are compared with `baseline/<chip>.json`: above baseline = regressed, a nonzero class missing from the
baseline = fail (a baseline class may be a base rule such as `ANT.6`; the deck's `ANT.16_i_ANT.6` variants fold onto it). Exit 0 only if nothing fails or regresses. Baselines move only by `--update-baseline --reason`
(refused if a gate fails), committed by pathspec with that reason. `signoff_selftest.py <checked run>` is the harness's
known-answer and negative-control test (thirteen injected faults incl. chip_smoke (failed, or conn mode only) on a copy of a run, no tool runs).

## Fill and keep-outs

Fill = the shuttle PDK's `fill_all.rb` (792ef67) on the whole die. Keep-outs are top-level marker boxes over instances,
chosen by `keepouts.json`: PMNDMY (no dummy metal) on sensitive blocks, PMNDMY + IND_MK on inductors (no dummy COMP /
Poly2, exempt from DCF.1a). Whole-block NDMY is not usable (main-deck DE.3: one NDMY shape <= 15 000 um2; DE.4: 20 um
between them). Block owners should draw these markers in their own GDS (SO-2); the table is a stop-gap.

## LVS

`top_lvs.py` extracts Metal1-5, Via1-4 and the MIM top plate hierarchically through every cell on disk and keeps only
the pins of the black boxes (direct children of the top after flattening the ring, grid and router wiring). Reference:
`gen_netlist.py`, flat from the chip conn, one empty subckt per master with the published pin list. Compare (1)
topologically and (2) net by net by name with the manifest (open / short / internal / not checkable). It is black-box
connectivity on metal: no device-level full-chip LVS, the provider ring and macro are not bound (SO-4), substrate / well
ties are not extracted.

## Shuttle precheck (live, `precheck/run_precheck.sh`)

Environment, built here and run with the network off: gf180mcu-precheck 1.7.4 (main 9b4e7da), KLayout 0.30.12, Magic
8.3.677, netgen 1.5.323, LibreLane 3.1.0.dev3, PDK open_pdks 792ef67 (`gf180mcu_fd_pv` a561909, `gf180mcu_fd_pr` 5e4be87,
gf180mcuD only), from the flake's pinned nix closure, native aarch64, nothing compiled. Tree `scratch/integration/signoff-run/pc/`
(`precheck/` = git archive of 1.7.4, `pdk/` = ciel tree, `ex/` = wafer.space example layouts 8996810); docker volume
`signoff_nix` holds `/nix`, image `nixos/nix:2.28.3`. Rebuild (network only for these):

```
docker volume create signoff_nix
docker run --rm --cpus 4 -v signoff_nix:/nix -v $PC:/w -w /w/precheck nixos/nix:2.28.3 sh -c \
  'nix --extra-experimental-features "nix-command flakes" --accept-flake-config --option cores 4 --option max-jobs 2 \
   build .#devShells.aarch64-linux.default --out-link /nix/var/signoff-devshell'
docker run --rm --cpus 4 -v signoff_nix:/nix -v $PC:/w -w /w nixos/nix:2.28.3 /nix/var/signoff-devshell/entrypoint \
  ciel enable 792ef67037d74c8c51811eab3ce23cf793491296 --pdk-root /w/pdk --pdk-family gf180mcuD
git clone --depth 1 https://github.com/wafer-space/gf180mcu-example-layouts.git $PC/ex
```

The wrapper runs `precheck.py --slot 1x1 --cob --id DEADBEEF --workers 1 --threads N`, pinned to N cores (the density
and antenna steps ignore the thread count and would take every core otherwise). `PC_EXTRA` passes `--to / --from /
--skip <step>`. Do not edit the script while a run is going (bash reads it as it runs).

Steps (precheck 1.7.4 + LibreLane 3.1.0.dev3; "deferred" = the flow goes on and fails at the end):

| # | Step | Checks | Gating |
|---|---|---|---|
| 1 | ReadLayout | reads the layout; maps dummy layers xx/4 onto drawing (Poly2, Metal1-5; dummy COMP stays) | yes |
| 2-3 | CheckTopLevel, CheckSize | one top cell named as given; origin 0,0, dbu 0.001, no Via5 / MetalTop, GUARD_RING_MK present, bbox = slot | immediate |
| 4 | CheckPadMask (`--cob`) | every golden CoB pad opening fully open (extra openings allowed) | immediate |
| 5 | GenerateID | the four ID cells exist at their fixed places; refills them (QR, text, marker) | immediate |
| 7-8 | Density | PDK deck `density` (DCF.1a/b/d, PL.8, M1.4-M5.4, MT.3, MT30.7) | deferred |
| 9-10 | ZeroAreaPolygons | none on any layer | immediate |
| 11-12 | Antenna | PDK deck `antenna` | deferred |
| 13-14 | Magic DRC | full style; a non-zero count is a warning only | no |
| 15-16 | KLayout DRC | PDK deck `all,-antenna,-density,-cup`, variant D (MIM B, 5LM, 11K top metal) | deferred |
| 17 | WriteLayout | output with the ID inserted and fill merged | output |

Not in the flow: LVS, the `cup` deck, fill (the submitter fills), any check of the ID content.

PDK 792ef67 against the project's f6eeac7 (file diff, geometry XOR, model simulation, block matrix): nothing the project
has simulated, placed or extracted changes. Device models numerically identical; all 1424 library cells XOR-identical;
ten published blocks give 0 under both tool/deck pairs. What differs for the top: DCF.1a and its fill scripts; KLayout
0.30.12 in deep mode counts DF.14 / DF.16 / DF.19 differently from 0.30.9, so a 0.30.9 top result does not predict the
precheck's count for those rules (judge ships with the live binary); DF.11 is re-implemented; the LVS deck still does not
see our MIM capacitors. The example chip (positive control) passed density, zero-area, antenna and Magic DRC here; its
main deck was stopped unfinished.

## Current results

`pt_rf` precheck, 2026-11-21 (filled, layout of the QVCO-r8 run before the orientation fix): exit 1. Pad mask, ID,
structure, zero-area and Magic DRC pass; KLayout DRC 1155, antenna 89, density 5 x DCF.1a. Breakdown by source and owner:
`../assembly/README.md` (results table) and rows ASM-10, SO-1 in `scratch/reviews/interface-changes.md`. A precheck of the
current layout is running. `pt_wired`: fill + density only (every global rule passes, DCF.1a inside blocks).

## Known failures and gaps

1. Via3 / Via4 at every custom pad site, in the provider rail cell and in the pad shells (SO-1): pads, option-A rebuilds.
2. DCF.1a inside blocks (SO-3): block owners.
3. Block-internal DRC and antenna items (ASM-10): block owners.
4. LVS is black-box metal connectivity only; ring and macro not bound (SO-4).
5. Whether wafer.space accepts PMNDMY / IND_MK keep-outs is unanswered.
6. `PDK_LIVE` in `env.sh` points at the deck copy of the gap check (identical files); the complete 792ef67 tree is
   `scratch/integration/signoff-run/pc/pdk`. Nothing under `scratch/` survives a cleanup; the rebuild is above.
