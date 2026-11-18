# Live shuttle precheck on this machine: notes

Date 2026-11-18. Evidence labels: **[RUN]** run here, **[READ]** read in source, **[INF]** inferred.

## Environment (what was built, how to rebuild)

Route that worked: **nix inside docker, native aarch64** (no emulation, no substitutes). Every binary is the one the
precheck flake pins; all 584 store paths came from the binary caches (`nix-cache.fossi-foundation.org`,
`cache.nixos.org`), nothing was compiled except 11 trivial wrapper derivations.

| Item | Value |
|---|---|
| precheck | `wafer-space/gf180mcu-precheck` tag 1.7.4 = main 9b4e7da (upstream main unchanged on 18 Nov, `git ls-remote`) |
| flake.lock | librelane 99148a9, nix-eda 8a8e673, nixpkgs 9b69646, ciel e180507, devshell 9e29c63 |
| KLayout | 0.30.12 (`klayout -v`), python `pya`/`klayout` 0.30.12 |
| Magic | 8.3.677 |
| netgen | 1.5.323 |
| LibreLane | 3.1.0.dev3 |
| Python | 3.13.13, `qrcode` 8.2 present, pillow 12.2.0; Ruby in KLayout 3.4.9 |
| ciel | 3.1.0 |
| PDK | open_pdks 792ef67 (1.0.616), `gf180mcu_fd_pv` a561909, `gf180mcu_fd_pr` 5e4be87; gf180mcuD only |
| not in the shell | ngspice, python `docopt` (so the PDK's `run_lvs.py` does not start there; the LVS deck itself does) |

Where things are (all outside git, under `scratch/integration/signoff-run/pc/` unless noted):

- docker volume `signoff_nix` = `/nix` (store + gc root `/nix/var/signoff-devshell`), image `nixos/nix:2.28.3` (arm64)
- `precheck/` = `git archive 1.7.4` of the clone in `scratch/integration/signoff-gap/dl/precheck-live`
- `pdk/` = ciel tree, variants A/B/C deleted; `ex/` = `gf180mcu-example-layouts` 8996810
- `diff/old/libs.tech` = f6eeac7 `libs.tech` copied out of the project image (for diffs and the cross runs)
- `ll/` = copies of the LibreLane step sources that were read; `runs/`, `blocks/` = results

Rebuild (network needed only for these three steps; every run afterwards is `--network none`):

```
docker volume create signoff_nix
docker run --rm --cpus 4 -v signoff_nix:/nix -v $PC:/w -w /w/precheck nixos/nix:2.28.3 sh -c \
  'nix --extra-experimental-features "nix-command flakes" --accept-flake-config --option cores 4 --option max-jobs 2 \
   build .#devShells.aarch64-linux.default --out-link /nix/var/signoff-devshell'
docker run --rm --cpus 4 -v signoff_nix:/nix -v $PC:/w -w /w nixos/nix:2.28.3 /nix/var/signoff-devshell/entrypoint \
  ciel enable 792ef67037d74c8c51811eab3ce23cf793491296 --pdk-root /w/pdk --pdk-family gf180mcuD   # as the Makefile
git clone --depth 1 https://github.com/wafer-space/gf180mcu-example-layouts.git $PC/ex
```

A command inside the shell: `.../entrypoint <cmd>` (the store is mounted read-only and the container runs as the
calling user in the wrapper). ciel downloads all four variants (3.6 GB); A, B and C were deleted by hand.

## Wrapper

```
run_precheck.sh <abs gds/oas> <topcell> <workdir> [threads=4]     # PC_ID PC_SLOT PC_COB PC_WORKERS PC_EXTRA PC_CPUSET
summarise.py <workdir> [--prune]                                  # summary.json + text table, per step and per rule
```

It runs `python3 precheck.py --input … --top … --slot 1x1 --cob --id DEADBEEF --workers 1 --threads N --dir <workdir>
--run-tag precheck --output <workdir>/out/<top>.oas` in the dev shell, network off, 4 cpus, pinned to 4 cores.
The pinning matters: LibreLane's density step passes `-rd thr=N` (the deck reads `threads`, not `thr`) and the
antenna step passes no thread count, so in both the deck falls back to `threads=max` = every visible core
**[RUN]** (the positive control, started before the pinning was added, shows `thr=32` in its COMMANDS file).
`PC_EXTRA="--to KLayout.Density"`, `--from`, `--skip Magic.DRC` select steps (precheck.py options).

## What the flow does, in order **[READ precheck.py 1.7.4 + LibreLane 3.1.0.dev3 `steps/klayout.py`, `steps/magic.py`, `steps/checker.py`, `scripts/magic/drc.tcl`; RUN on the example]**

`--cob` inserts step 4. "Deferred" = the flow goes on and fails at the end; "immediate" = stops there.

| # | Step id | What it does / checks | Deck, script, arguments | Pass criterion | Gating |
|---|---|---|---|---|---|
| 1 | KLayout.ReadLayout | prints SHA256 of the input; reads gds / gds.gz / oas and writes GDS. **Modifies:** dummy layers are mapped onto drawing layers: 30/4→30/0 (Poly2), 34/4→34/0, 36/4→36/0, 42/4→42/0, 46/4→46/0, 81/4→81/0 (Metal1–5). Dummy COMP 22/4 is left alone. Everything after this step, and the output file, sees metal and poly fill as real metal and poly | `scripts/klayout/read_layout.py` | readable | yes |
| 2 | KLayout.CheckTopLevel | exactly one top cell, named as `--top` (default: input file basename) | `check_top.py --top` | exit 0 | yes, immediate |
| 3 | KLayout.CheckSize | top bbox origin (0,0); dbu 0.001; no Via5 (82/0), no MetalTop (53/0); GUARD_RING_MK (167/5) present; bbox = slot size (1x1: 3932 × 5122 µm) | `check_size.py --slot` | exit 0 | yes, immediate |
| 4 | KLayout.CheckPadMask (`--cob`) | `Pad(37/0) AND mask XOR mask` empty: every golden CoB pad opening must be fully open; extra openings are allowed | `check_mask.drc`, `assets/golden_masks/mask_<slot>.gds` | XOR empty | yes, immediate |
| 5 | KLayout.GenerateID | `--cob`: cells `gf180mcu_ws_ip__qrcode_id`, `__shuttle_id`, `__project_id`, `__marker` must exist, one instance each, at (26,26)-(168.8,168.8), (26,175.6)-(85.5,371.1), (175.6,26)-(371.1,85.5) and the 245 µm square 36 µm inside the top-right corner; ID must be 8 characters. **Modifies:** the four cells are cleared and refilled: QR code of the ID (21×21 octagon pixels, Metal1–5), text of ID[0:4] and ID[4:8] on Metal1–5 with PR_bndry/PMNDMY/NDMY boxes, corner marker on Metal1–5; the generated cell bboxes must equal the placeholder bboxes. Writes without PCell context | `generate_id.py --id --cob`, `pcell_library/`, python `qrcode` | asserts | yes, immediate |
| 6 | KLayout.Render | PNG, 4096 px, oversampling 3 | LibreLane `render.py`, `assets/gf180mcu_render.lyp` | none | no |
| 7 | KLayout.Density | PDK deck, `-rd decks=density -rd variant=gf180mcuD -rd workers=W -rd thr=T` (T is ignored, see above). Rules in 792ef67: DCF.1a (new), DCF.1b, DCF.1d, PL.8, M1.4–M5.4, MT.3, MT30.7; the deck runs deep mode | `libs.tech/klayout/tech/drc/gf180mcu.drc` | metric `klayout__density_error__count` | — |
| 8 | Checker.KLayoutDensity | count must be 0 | | 0 | yes, deferred |
| 9 | KLayout.ZeroAreaPolygons | flat; every layer: raw polygons with area 0 | `zero_area.drc` | metric `klayout__zero_area_polygons__count` | — |
| 10 | Checker.KLayoutZeroAreaPolygons | count must be 0 | | 0 | yes, immediate |
| 11 | KLayout.Antenna | PDK deck, `-rd decks=antenna -rd variant=gf180mcuD -rd workers=W` (no thread count) | `gf180mcu.drc` | metric `klayout__antenna_error__count` | — |
| 12 | Checker.KLayoutAntenna | count must be 0 | | 0 | yes, deferred |
| 13 | Magic.DRC | `gds read` with `gds maskhints true`, `gds readonly true`, flatglob list from precheck.py (`*_CDNS_*`, fill cells, SRAM leaf cells), `drc style drc(full)`, `drc euclidean on`, `drc listall why` | LibreLane `scripts/magic/drc.tcl`, PDK magicrc/tech | metric `magic__drc_error__count` | — |
| 14 | Checker.MagicDRC | `ERROR_ON_MAGIC_DRC=False`: a non-zero count is a warning only | | — | **no** |
| 15 | KLayout.DRC | PDK deck, `-rd decks=all,-antenna,-density,-cup -rd variant=gf180mcuD -rd workers=W -rd threads=T` (variant D: MIM option B, 5LM, 11K top metal) | `gf180mcu.drc` | metric `klayout__drc_error__count` | — |
| 16 | Checker.KLayoutDRC | count must be 0 | | 0 | yes, deferred |
| 17 | KLayout.WriteLayout | writes the GDS of step 5 (ID inserted, fill merged onto drawing layers) to `--output` | `read_write.py` | — | output |

Not in the flow: LVS of any kind, the `cup` deck, the PDK fill (the submitter fills), any check of the ID content.
The Makefile's own defaults are `WORKERS=max THREADS=1 ID=DEADBEEF`; here `--workers 1 --threads 4` as instructed.

## Current state (2026-11-18)

Positive control **[RUN]**: `gf180mcu-example-layouts` 8996810, `5v/1x1/chip_top.oas` (2.4 MB, the smaller of the
two 1x1 examples; sha256 012305b7…690cf), `--slot 1x1 --cob --id DEADBEEF --workers 1 --threads 4`, live binaries.

| Step | Result | Time |
|---|---|---|
| ReadLayout, CheckTopLevel, CheckSize (3932 × 5122), CheckPadMask ("Pad mask matches"), GenerateID ("Inserted ID: DEADBEEF"), Render | pass | 2–9 s each |
| KLayout.Density + checker | 0 violations, pass | 11 min 00 s |
| ZeroAreaPolygons + checker | 0, pass | 22 s |
| KLayout.Antenna + checker | 0, pass | 51 min 32 s (one worker; the rules run serially) |
| Magic.DRC + checker (second run) | 0 violations ("Check for Magic DRC errors clear") | 31 min 21 s (5 min read-in) |
| KLayout.DRC (main deck), checker, WriteLayout | **not finished**: stopped by me after 31 min at 100 % of one core, still deriving layers after reading Metal1 (7.98 M Metal1 polygons, 19.9 M contacts; 0 of ~500 rules started) | — |

The first run (`runs/ex5v_1x1`) was stopped on the owner's instruction during Magic.DRC, after 68 min, to free the
job slot. The remaining steps were run again in `runs/ex5v_1x1_rest` with
`PC_EXTRA="--skip KLayout.Density KLayout.Antenna KLayout.Render"`; that run was stopped in the main KLayout DRC to
give the slot back. So the main deck has **not** been proven through LibreLane on a full chip here; the same binary,
deck and argument set ran to completion on eleven block GDS and two PDK unit layouts (`pdk-diff.md` section 4).
Expect the main deck on a filled 1x1 chip to take well over half an hour with one worker.

Timing guide for a full 1x1 chip on this box at 4 cpus, one worker: about 1 h before Magic DRC starts. `--workers`
above 1 parallelises the antenna and main decks by rule (the Makefile uses `max`); memory then scales with workers.

Known wrapper/summary behaviour: do not edit `run_precheck.sh` while a run is in progress (bash reads the script
as it goes; the first run lost its `exit_code` file that way). `summarise.py --prune` removes the intermediate GDS,
so `--from <step>` cannot be used in a pruned directory.

Block-level use of the same binaries (DRC matrix, LVS, model and cell comparison): `pdk-diff.md`.
