# PDK 792ef67 (shuttle precheck) versus f6eeac7 (project): what differs and what it does to our data

Date 2026-11-18. Extends `scratch/reviews/signoff-gap.md` section 4 (deck diff, density stage) and does not repeat it.
Evidence labels: **[RUN]** run here and read; **[READ]** read in the files; **[INF]** inferred.

Trees compared: gf180mcuD of open_pdks f6eeac7 (1.0.605) as it sits in the project analog image
(`sha256:bd7a702b…`, `/foss/pdks/gf180mcuD`) and of 792ef67 (1.0.616) fetched with ciel inside the precheck's own
nix shell (`NOTES.md`). Method: sha256 of every file in both trees, then per group a text diff, a geometric
comparison or a simulation. Scripts are in this directory; raw outputs in `scratch/integration/signoff-run/pc/`
(`diff/changes.txt` = full added/removed/changed list, `diff/xor/*.json`, `diff/models/model_compare.json`,
`blocks/*.json`).

## Result in one paragraph

Nothing the project has simulated, placed or extracted changes under the shuttle's PDK and tools. Device models:
one syntactic change, numerically without effect (0.0000 % on every measured quantity). Standard cells and IO
cells: all 1424 GDS cells geometrically identical, all 42 liberty files identical apart from comments. On ten
published blocks, KLayout main and antenna decks and Magic DRC give 0 violations under all four tool/deck
combinations; on four blocks Magic extraction, netgen LVS and the KLayout LVS deck give the same devices under both
sets. What does differ and matters for the top: (1) the density deck's DCF.1a (known, signoff-gap finding 1) and the
fill scripts that go with it; (2) **KLayout 0.30.12 in deep mode counts some COMP rules differently from 0.30.9**
(DF.14 tap distance, DF.16, DF.19 on the PDK's own test layout), so a 0.30.9 result on the top is not a prediction
of the precheck's count for those rules; (3) DF.11 is re-implemented and flags fewer cases; (4) the KLayout LVS
deck was rewritten in parts but still does not see our MIM capacitors.

## 1. File-level diff by group **[RUN]**

Counts: files added / removed / changed / identical (792ef67 relative to f6eeac7).

| Group | + | − | Δ | = | Substance |
|---|---|---|---|---|---|
| `libs.tech/klayout` DRC decks | 130 | 0 | 5 | rest | Added: `drc/testing/` (unit layouts + golden lyrdb, pytest). Changed rule files: `density.rb` (new **DCF.1a**: COMP-free area ≥ 20 µm must carry dummy COMP, keep-out NDMY/RES_MK/Pad/IND_MK and 1–2 µm rings on Nwell/DNWELL/LVPWELL/Dualgate edges), `comp.rb` (**DF.11** now `(ncomp.edges & pcomp.edges).with_length(nil, 0.3 µm)` instead of the width of COMP interacting with butted NCOMP), `contact.rb` (**CO.5a/CO.5b** enclosure measured against Nplus/Pplus instead of a derived butted-COMP layer), `dummy_comp.rb`, `geom.rb` (comments). `antenna.rb`, `gf180mcu.drc`, options: identical |
| `libs.tech/klayout` LVS decks | 281 | 2 | 8 | | Added: `lvs/testing/`. `gf180mcu.lvs`: new option **`check_ports`, default true** (turns `top_lvl_pins` on and fails the run on missing/inconsistent top ports), `$input` now required outside the GUI. `diode_extraction.lvs`: recognition layers of every diode moved in from the removed `diode_derivations.lvs` / `diode_connections.lvs` and rewritten (LV/MV split by Dualgate, common exclude list, sc_diode with separate terminals). `mimcap_connections.lvs`: `metal2_con` instead of `metal2`, extra `via2_cap`–`metal3_con` connect. `general_connections.lvs`: top via/label connects use `top_via_n_cap`, `top_metal_con`. `mos_extraction.lvs` / `mos_derivations.lvs`: 10 V LDMOS extracted as `dmos4` with distinct S and D regions. `custom_classes.lvs`: comments |
| `libs.tech/klayout` fill scripts | 0 | 0 | 3 | 1 | `fill_comp.rb`, `fill_poly2.rb`, `fill_metal.rb`: existing dummy shapes are read and respected (spacing DCF.2a / DPF.2a / DM.2a,c to them); new switch `no_scribe_line` (scribe margin 26 µm → 0); `space_to_Pad` 7 → 5 µm; the fill cell is always created (no reuse of an existing cell of that name); **COMP and Poly2 fill no longer skip the gaps between COMP closer than 20 µm** (old `COMP_20um_spacing` removed), which is what DCF.1a needs: the f6eeac7 script cannot clear DCF.1a (the 10 residual items of signoff-gap finding 1), the 792ef67 one is written to. `fill_all.rb` identical |
| `libs.tech/klayout` `.lyp` / `.lyt` / `.map` | 0 | 0 | 0 | 3 | identical (sha256) |
| `libs.tech/klayout` PCells | 0 | 1 | 11 | | `cells/*.py`: explicit `default=` removed from enum parameters (volt, bulk, mim_option, metal_level, res_type, via layers), `via_generator.layout` now required, `_patches.py` (gdsfactory 9 shim) removed. Seal ring (`sealring_cells/`): `pya` → `klayout.db`, shape test via `dpolygon`; the drawing code is otherwise identical line for line (0 differing lines after the rename). No geometry constant changed **[READ]**; PCells were not regenerated here |
| `libs.tech/magic` | 0 | 0 | 4 | 1 | `gf180mcuD.tech`: version string; 10 new paint rules (mv diffusion/tap types flip with nwell/pwell); GDS output: NPLUS/PPLUS of resistors become templayers OR-ed into the main implant layers (the `grow 180 / shrink 180 / close` post-processing is gone); `FILLOBS` now written as NDMY 111/5 with mask hints (was commented out) and read back as `fillobs`; `ignore CAPDEF`, `ignore FILLOBS` removed from GDS input. `gf180mcuD.tcl`: `cap_mim_2p0fF` generator defaults `val 50.0 carea 25.0 cperi 20.0` → `val 54.516 carea 1.99 cperi 0.2383`; `lmax` removed from `pfet_05v0` (0.545) and `nfet_05v0` (0.695) defaults. `.magicrc`, `-GDS.tech`: build path / version only. DRC section of the tech file: unchanged |
| `libs.tech/netgen` | 0 | 0 | 2 | 0 | `setup.tcl` = `gf180mcuD_setup.tcl`: added ignore/parallel rules for `gf180mcu_ocd_sc_*` fill and decap cells (a library we do not use); whitespace. Nothing for fd_sc, fd_io or primitives |
| `libs.tech/ngspice` | 0 | 1 | 2 | 6 | `sm141064.ngspice` = `sm141064.spice`: 9 × `.model fox_sub c cox=8.85e-05` → `.model fox_sub c cj=8.85e-05` (the substrate capacitor inside npolyf_u, ppolyf_u, npolyf_s, ppolyf_s, ppolyf_u_1k, ppolyf_u_2k, ppolyf_u_1k_6p0, ppolyf_u_2k_6p0, ppolyf_u_3k). No other line differs. `design.ngspice`, `sm141064_mim`, `smbb000149`: identical. Removed: an empty `.spiceinit`. `xyce/`: same single change |
| `libs.tech/librelane` | 4 | 0 | 3 | 29 | `config.tcl`: `RCX_RULES*` → `RCX_RULESETS` dict (same three files); pre-route `LAYERS_RC` resistance Metal2 3.859e-4 → 2.256e-4, Metal3 2.067e-4 → 2.256e-4, Metal4 1.686e-4 → 2.256e-4, Metal5 7.928e-5 → 5.855e-5; `VIAS_R` nominal 4.23 → 4.5 Ω (4.23 kept for min). Both sc `config.tcl`: `SYNTH_CLOCKGATE_TIE_LO "TE"`. OpenRCX rule files identical. New library directory `gf180mcu_ocd_sc_rt12t3v3` (config only). These are estimation inputs of a LibreLane run with this PDK, not sign-off data |
| `libs.tech/xschem`, `qflow`, `xyce` | 85 | 0 | 83+2 | | xschem symbols and test schematics; not used by the project flow; not examined beyond the list |
| `libs.ref/gf180mcu_fd_sc_mcu7t5v0` | 0 | 0 | 474 | 8 | GDS: all 230 cells XOR-identical. `.lib` (15): identical after removing comments/whitespace (a licence comment added per cell). `mag`, `maglef` (229 each): timestamp line only. LEF, techlef, CDL, spice, verilog: identical |
| `libs.ref/gf180mcu_fd_sc_mcu9t5v0` | 0 | 0 | 474 | 8 | same: 230 cells XOR-identical, 15 `.lib` identical in content |
| `libs.ref/gf180mcu_fd_io` | 0 | 0 | 990 | 39 | `gf180mcu_fd_io.gds`: all 962 cells XOR-identical; `gf180mcu_ef_io.gds` byte-identical. `.lib` (12): identical in content. `mag`/`maglef`: timestamps only. LEF, CDL, spice, verilog: identical |
| `libs.ref/gf180mcu_fd_pr` | 0 | 0 | 24 | 11 | GDS (11) byte-identical; `mag`: timestamps only |
| `libs.ref/gf180mcu_fd_ip_sram` | 0 | 0 | 2394 | 83 | GDS, CDL, spice, `.lib`: identical. LEF (4) and maglef: ~970 Via2 obstruction rectangles added per macro, VDD/VSS pin shapes on via layers; `sram64x8…__blackbox_pp.v` gains `inout VDD, VSS`. Not used by the project |
| libraries present in only one | — | — | — | — | none: both trees hold exactly the same five `libs.ref` libraries (the `ocd`, `as`, `osu`, `efuse` libraries named in nodeinfo are in neither ciel default set) |

Source commits (nodeinfo): `gf180mcu_fd_pr` b6866b8 → 5e4be87, `gf180mcu_fd_pv` e766ad1 → a561909; `fd_sc_mcu7t5v0`
0ef8889, `fd_sc_mcu9t5v0`, `fd_io` 40cdef6 unchanged, which is consistent with the XOR result.

## 2. Device models **[RUN]** (`model_compare.py`, ngspice 47 of the project sim image, 27 °C)

The only change is `cox=` → `cj=` on the poly-resistor substrate capacitor model. ngspice 47 accepts both as the same
area capacitance: the capacitor is present with the same value under both files (it is not silently dropped by the
old spelling). Fixed-bias comparison, both model sets, tt / ss / ff (with `res_*` and `mimcap_*` corners):

| Quantity | tt | ss | ff | 792ef67 − f6eeac7 |
|---|---|---|---|---|
| nfet_03v3 10/0.28, Vgs 1.2, Vds 1.65: Id µA / gm µS | 684.73 / 1703.2 | 452.26 / 1395.7 | 975.02 / 2000.1 | 0.0000 % |
| pfet_03v3 10/0.28, same bias: Id / gm | 174.91 / 618.66 | 93.147 / 447.83 | 291.15 / 797.67 | 0.0000 % |
| nfet_06v0 10/0.7, Vgs 1.5, Vds 3.0: Id / gm | 418.19 / 794.3 | 262.06 / 607.3 | 617.74 / 985.3 | 0.0000 % |
| pfet_06v0 10/0.55, same bias: Id / gm | 116.88 / 298.16 | 62.260 / 204.82 | 194.25 / 399.9 | 0.0000 % |
| ppolyf_u_1k 1 × 10 µm: R Ω | 10459.1 | 12516.2 | 8401.88 | 0.0000 % |
| ppolyf_u_1k 2 × 20 µm: C to substrate fF (1 MHz) | 3.4876 | 3.4876 | 3.4876 | 0.0000 % |
| cap_mim_2f0_m4m5_noshield 10 × 10 µm: C fF | 208.54 | 229.39 | 187.68 | 0.0000 % |

All values are equal to the printed digits. No block simulation was rerun: with a model file that differs in one
alias and gives identical device values there is nothing for a rerun to show **[INF]**. Not tested: a simulator
other than ngspice 46/47 (Xyce gets the same edit; the old Xyce file had `level=1` + `cox`).

## 3. Cells the project instantiates **[RUN]**

- Provider IO (`integration/pt_provider_io.sv` and the pad generators/netlists under `analog/pads/`):
  `gf180mcu_fd_io__bi_24t`, `__bi_t`, `__in_c`, `__in_s`, `__asig_5p0`, `__dvdd`, `__dvss`, `__cor`, `__fill1`,
  `__fill5`, `__fill10`. All present in both PDKs; **none changed** (GDS XOR empty for the cell and every subcell,
  LEF/CDL/spice/verilog byte-identical, liberty identical in content).
- 5 V standard cells (grep of the project netlists, tcl and configs: 47 real `gf180mcu_fd_sc_mcu7t5v0__*` cells,
  among them and2_1, and3_1, and4_1, antenna, aoi21_1, buf_1/2/4/8, clkbuf_2/4/8/16, clkinv_1, dffnrnq_1, dffq_1,
  dffrnq_1/4, dffsnq_1, dlya_1, dlyb_1, dlyc_1, endcap, fill_1/2, fillcap_4/8/16/32/64, filltie, icgtp_2, mux2_1/2,
  nand2_1/3_1/4_1, nor2_1/3_1/4_1, oai21_1/211_1/31_1, or2_1, tieh, tiel, xor2_1): **none changed**, same evidence.
  The 9-track library is not referenced by the project.
- The project's digital timing uses its own re-characterised corners (`verification/digital_hardening/liberty`,
  3.15–3.35 V), built from the cell SPICE netlists and the device models; both inputs are unchanged, so those
  liberty files do not need rebuilding for the PDK change **[INF from 1–2]**.

## 4. Published blocks under both versions **[RUN]** (`block_drc.py`, `blocks.json`)

Configurations: **P** = KLayout 0.30.9 + deck f6eeac7, Magic 8.3.623 + tech f6eeac7 (project); **L** = KLayout
0.30.12 + deck 792ef67, Magic 8.3.677 + tech 792ef67 (live binaries, native); **X1** = deck 792ef67 on KLayout
0.30.9; **X2** = deck f6eeac7 on KLayout 0.30.12. KLayout arguments as the precheck: `decks=all,-antenna,-density,-cup`
(main) and `decks=antenna`, `variant=gf180mcuD`, `workers=1`, `threads=4`, deep mode. Magic as LibreLane's
`drc.tcl` with the precheck's flatglob list (`magic_drc.tcl`). GDS copied out of `analog/` at the sha256 recorded in
`blocks/<name>.json`.

Violations (total; every per-rule list is empty where the total is 0):

| Block (top cell) | P main / ant / Magic | X1 main / ant | X2 main / ant | L main / ant / Magic |
|---|---|---|---|---|
| lna (`pt_lna`) | 0 / 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 / 0 |
| rxmix_i (`pt_rxmix_i`) | 0 / 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 / 0 |
| pll_ring (`pt_pll_ring`) | 0 / 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 / 0 |
| QVCO (`pt_lc_qvco5`) | 0 / 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 / 0 |
| adc_q (`pt_adc_q`) | 0 / 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 / 0 |
| cdr (`pt_cdr`) | 0 / 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 / 0 |
| wiredtx (`pt_wiredtx`) | 0 / 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 / 0 |
| pad hspad (`pad_hspad`) | 0 / 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 / 0 |
| aosc (`pt_aosc`) | 0 / 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 / 0 |
| hsbias (`pt_wtx_hsbias`, the only published bias GDS) | 0 / 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 / 0 |

Run times are similar between versions (main deck 5–23 s per block, antenna 2–7 s, Magic 0.4–4 s). Each main run
logs 217–218 "Executing rule" lines and ends with the deck's own `DRC RESULT: SUCCESS (0 violations)` (checked on aosc).

### Negative controls (`deck_negctl.py`), so that the zeros mean something

| Layout | Check | P | X1 | X2 | L | Reading |
|---|---|---|---|---|---|---|
| `adc_i.gds` (known bad, finding 6b) | antenna | 7 | 7 | 7 | 7 | ANT.16_i_ANT.5 × 7 everywhere; main deck 0 everywhere; Magic 0 / 0 |
| PDK unit layout `comp.gds`, `decks=comp`, deep (precheck mode) | total | 1488 | 1467 | 1519 | 1498 | differs by deck **and** by tool |
| | DF.11 | 46 | 25 | 46 | 25 | deck effect: the re-implemented rule flags 21 fewer |
| | DF.14_LV / DF.14_MV | 33 / 33 | 33 / 33 | 43 / 48 | 43 / 48 | **tool effect** (0.30.9 → 0.30.12) |
| | DF.16_LV / DF.16_MV / DF.19_MV | 26 / 26 / 26 | 26 / 26 / 26 | 28 / 28 / 28 | 28 / 28 / 28 | tool effect |
| same, `run_mode=flat` | total | 1550 | 1529 | 1550 | 1529 | tool versions agree; 1529 = the PDK's golden count |
| | DF.14_LV / DF.14_MV | 41 / 41 | 41 / 41 | 41 / 41 | 41 / 41 | |
| PDK unit layout `contact.gds`, `decks=contact`, deep | total | 498 | 498 | 498 | 498 | CO.5a/5b rewrite: same counts here |
| `comp.gds` | Magic DRC | 506 | — | — | 506 | same 6 messages and counts under 8.3.623/f6eeac7 and 8.3.677/792ef67 |

What the DF.14 line means: in deep (hierarchical) mode, the mode the precheck runs, the two KLayout versions report
different numbers of markers for DF.14 (maximum distance NCOMP to substrate tap, 20 µm LV / 15 µm MV), DF.16 and
DF.19, and neither equals the flat count (33 and 43/48 against 41). In flat mode both versions agree with each
other and with the golden file. Whether the deep-mode difference is marker splitting or real misses/extras was not
resolved **[not done]**. Consequence: for these rules a clean 0.30.9 deep run of the chip top does not establish
the 0.30.12 deep count; the top must be judged with the live binary (`run_precheck.sh`), and a block that is clean
only in one mode deserves a flat-mode cross-check. On the ten blocks above both versions give 0.

### LVS / extraction under both versions (`block_lvs.py`)

| Block | Magic read-back devices P / L (reference) | census P = L | netgen vs published netlist, P / L | KLayout LVS deck devices P / L | per-model summary P = L |
|---|---|---|---|---|---|
| aosc | 34 / 34 (34) | identical | match uniquely / match uniquely | 34 / 34 | identical |
| lna | 981 / 981 (981) | identical | match uniquely / match uniquely | 957 / 957 | identical |
| pll_ring | 789 / 789 (789) | identical | match uniquely / match uniquely | 769 / 769 | identical |
| adc_q | 3735 / 3735 (3735) | identical | match uniquely / match uniquely | 3663 / 3663 | identical |

"Census" is the flattened multiset of (model, W, L, nf, m, r_width, r_length, c_width, c_length, area, pj): it is
equal key for key between Magic 8.3.623/f6eeac7 and 8.3.677/792ef67, so no device count or parameter moves; no
property errors from netgen 1.5.316 or 1.5.323. The KLayout LVS deck, rewritten in its diode and MIM connection
parts, extracts exactly the same devices as before on these blocks, which also means it **still misses the MIM
capacitors and the n+/psub antenna diodes** (lna 24, pll_ring 20, adc_q 72 devices short of Magic): signoff-gap
finding 9 stands under 792ef67. The deck was run with the switches `run_lvs.py --variant=D --net_only` produces
(the runner itself needs python `docopt`, which the live shell lacks). The new `check_ports=true` default was left
at its default; with `net_only` it did not fail a run. Not exercised: a full KLayout LVS compare, where
`check_ports` would start to matter for tops without ports (`pt_lc_qvco5`, finding 6).

## 5. Does any published result change under the shuttle's version?

| Result class | Changes? | Basis |
|---|---|---|
| Block simulations (device models) | no | one alias edit, 0.0000 % on all compared quantities [RUN] |
| Digital timing (cells, liberty, LEF) | no | cells XOR-identical, liberty content identical, own liberty inputs unchanged [RUN] |
| Block KLayout DRC, antenna | no on the 10 sampled blocks (+ adc_i keeps its 7) | 4-way matrix [RUN]; the other 64 inventory GDS were not rerun |
| Block Magic DRC | no on the 10 sampled blocks | [RUN] |
| Block LVS / extraction | no on the 4 sampled blocks | [RUN] |
| Top-level density | yes: DCF.1a | signoff-gap finding 1 [READ], not rerun here |
| Top-level main DRC | open for DF.14 / DF.16 / DF.19 (tool) and DF.11 (deck) | unit-layout control [RUN]; the top itself was not run by me (owner runs the live precheck on the filled skeleton) |
| Magic PEX numbers | not compared numerically | the tech-file diff (section 1, complete) touches only version, paint, cifoutput and cifinput: the `extract` section is unchanged [RUN diff]; device census equal [RUN]; parasitic values under Magic 8.3.677 versus 8.3.623 were not compared |

## 6. Run versus read, and not done

- **Run:** tree hashing and grouping; text diffs of every changed file outside `xschem`; cell-by-cell XOR of the
  four cell GDS files (1424 cells) with KLayout 0.30.9; liberty normalised comparison (42 files); ngspice model
  comparison (6 runs); block DRC matrix (10 blocks × P/L/X1/X2 main + antenna, P/L Magic = 100 runs); negative
  controls (22 runs); extraction + netgen + KLayout LVS deck on 4 blocks under P and L.
- **Read only:** PCell and seal-ring python (no regeneration and XOR of generated devices), LibreLane config,
  Magic tech diff, LVS deck diff, SRAM LEF.
- **Not done:** the remaining 64 inventory GDS; the chip top under the live main deck; resolving the deep-mode
  DF.14 difference to individual markers; comparing Magic parasitic extraction values between the two Magic versions;
  Xyce.

## Files

`block_drc.py`, `magic_drc.tcl`, `blocks.json`, `deck_negctl.py`, `block_lvs.py` (imports the census helpers of
`scratch/integration/signoff-gap/lvs/rb_lvs.py` and `kl_lvs.py`), `gds_cell_xor.py`, `lib_compare.py`,
`model_compare.py`; environment and wrapper in `NOTES.md`.
