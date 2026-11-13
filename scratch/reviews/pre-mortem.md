# Pre-mortem: ways this chip dies or is useless that the risk register does not track

Date: 2026-11-13. Reviewer brought in cold. Scope: outside-view checks only. Not redone here (other
agents): always-on block audit, power-up/isolation, end-to-end mode walk, PDN model, substrate/pulling.

Evidence labels: **[RUN]** I ran something and read the result; **[READ]** read in a repo artefact
(not a README); **[WEB]** web research on wafer.space on 2026-11-13 (sub-agent, source URLs in section 4);
**[INF]** inferred, not verified.

Work dir `scratch/reviews/pre-mortem/`:
- `check_evidence_freshness.py` -> `freshness.json` (all 51 evidence files, all 61 KLayout DRC records)
- `kl_gds_census.py` -> `gds-census.json` (206 block GDS: dbu, layers, forbidden layers, 5 nm grid, density, wide metal)

No design file was modified. Nothing here has been entered in `spec/risk-register.md`; proposed IDs are
given so the coordinator can add the rows (MANDATE "one risk register").

## 1. Headline

The register (224 rows) is thorough on circuit physics and thin on everything that happens between
"each block is clean" and "wafer.space accepts a GDS that matches what was simulated, and somebody can
bond it and talk to it". The most likely failure is not an exotic analog effect. It is one of:

1. the only announced shuttle closes in about 33 days and nobody is tracking the date;
2. the GDS that ships was never the object that was LVS'd, filled or simulated;
3. the package cannot physically provide what the newest LNA assumes.

## 2. Top 15 (ranked by likelihood x severity, untracked or materially under-tracked)

L = likelihood, S = severity (H/M/L). "Dead" = no data out; "useless" = works but cannot meet its purpose.

### 1. The shuttle date is not in the project, and the design is weeks from a routable top
- **Evidence.** [WEB] wafer.space Run 3: purchase deadline 9 Dec 2026, precheck-clean GDS 16 Dec 2026
  (site data; the August announcement said 15/29 Dec, so confirm), "no extensions", no later run announced.
  [RUN] grep over `spec/`, `scratch/reviews/`, `NOTES.md`, `plan.md`, `risks.yaml`: no shuttle date, run
  number or deadline anywhere. INT-08 covers "weekly API limit stops", not the date.
  [READ] State today: `scratch/chip-assembly-v6/run/report-v6.json` raw margin -1.421 mm2, 14 blocks
  unplaced (3.50 mm2), 0 nF decap, no signal routing ever done (`spec/path-to-tapeout.md` "Not done: signal
  routing, block supply hookup, LO routing, full-chip LVS"); `pt_chip_full.spice` had 485 of 2613 ports
  unbound; `spec/performance-requirements.json` (2026-11-09): 4 meets / 12 marginal / 39 fails / 87
  unverified of 142; `spec/tapeout-readiness.json`: observable open on 33/33 chain blocks.
- **L/S.** H / H. Either the run is missed (next opportunity unknown) or an unverified top is pushed
  through precheck to make the date. Precheck only proves manufacturability, not function.
- **Cheapest decisive check.** Confirm the date and the next run with wafer.space (one message). Then
  write a dated back-plan: last day for block freeze, top routing, fill, full-chip DRC/LVS (the unrouted
  top already takes 50-73 min per KLayout run [READ] `scratch/chip-assembly-dev/drc*/`), precheck upload.
- **Owner.** User + coordinator. Proposed ID INT-25.

### 2. Density fill: required, absent, and it must go inside the analog blocks
- **Evidence.** [RUN] PDK deck `rule_decks/density.rb`: whole-die COMP 25-70 %, Poly2 >= 14 %, Metal1-5
  each >= 30 %. Precheck runs density as a gating step [WEB]. [READ] the 2026-11-10 precheck of the
  placed top (`scratch/chip-assembly-dev/precheck-run/runs/chip/05-klayout-density`): COMP 19.1 %, Poly2
  11.5 %, M1 19.2 %, M2 20.6 % (4 fails); M3-M5 pass at 30-33 %. [RUN] `gds-census.json`: area-weighted
  density over 7.9 mm2 of analog block GDS is COMP 9.3 %, Poly2 6.9 %, M1 2.9 %, M2 3.8 %; no analog block
  reaches 30 % M1 (max 29 %). The die is over-full, so there is no "elsewhere" to make up the average.
  [RUN] No fill step exists in `verification/chip_assembly/` or any flow (grep); the PDK ships
  `klayout/tech/scripts/fill_{comp,poly2,metal}.rb` but nothing calls them. All 61 block KLayout runs use
  `decks=all,-antenna,-density,-cup`.
- **What the register has.** MT-03 only asks for fill *exclusion* over RF/LO routes. That makes the
  density gap worse and says nothing about dummy COMP/Poly2, fill under the QVCO/LNA spirals (Q), fill
  capacitance on thin-margin nodes (pll_ring 5-13 %, QVCO band-hold 2.6 %), re-running DRC/LVS/extraction
  after fill, or who owns it. No block was ever extracted or simulated with fill.
- **L/S.** H / H (submission blocker; then a silent parasitic shift on the tightest nodes).
- **Cheapest decisive check.** Run the PDK `fill_all.rb` on the existing placed top
  (`scratch/chip-assembly-dev/pt_chip_top.gds`) with keep-outs only over spirals and matched arrays, then
  the density deck. One afternoon; it answers "can density be met at all with the exclusions we want".
  Then re-extract `pll_ring` and `qvco` with fill for the C delta.
- **Owner.** Assembly, with each block owner supplying keep-out markers. Proposed ID INT-26 (supersede MT-03 scope).

### 3. LVS was never run on the GDS that ships
- **Evidence.** [RUN] `analog/timing/layout_engine.py:608-611`, `analog/rf_rx/rfrx_flow.py:737-746`,
  `analog/rf_tx/layoutlib.py:538-541`, `analog/wired_rx/wrx_flow.py:376-386`: Magic `extract all` ->
  `ext2spice` on the in-memory `.mag` database, *then* `gds write`. Netgen compares that extraction to the
  schematic. No GDS read-back anywhere in rf_rx, rf_tx, timing, wired_rx, wired_tx, bringup_control
  (grep for `gds read`: 0 files each; pads, core_support, converters do read back). Only DRC sees the GDS.
- **Why it matters.** The project already hit this class once: INT-19, Magic export dropped the HRES
  marker and every high-res resistor was built at one third value; found by luck through a DRC rule. Any
  marker dropped on export that has no DRC signature (NAT in `pt_pll_vreg*`, DUALGATE in 69 GDS, SAB on the
  ESD `_dss` devices, FUSETOP on 59 GDS, V5_XTOR 112/1) changes the device the fab builds while LVS stays
  green. `layout_engine.py:592-596` also records that Magic 8.3.623 "was observed to drop" geometry when
  extracting after `gds write`.
- **L/S.** M / H (one wrong device class in bias, a pad or the POR is a dead chip).
- **Cheapest decisive check.** For each of the ~40 inventory GDS (`verification/chip_assembly/inventory.py`):
  Magic `gds read` -> extract -> netgen against the same schematic, or the PDK KLayout LVS deck
  (`libs.tech/klayout/tech/lvs`, a second independent extractor). Minutes per block. Make it a gate.
- **Owner.** Integration/signoff. Proposed ID MOD-18.

### 4. The new LNA needs a 0.5 nH source downbond that the TT01 board cannot provide
- **Evidence.** [READ] `analog/rf_rx/tb.py:223` `LNA_LS = 0.5e-9` "two short parallel downbonds",
  two-sided 0.35-0.65 nH; `scratch/rf-lna-p/NOTES.md:54`: stable at 0.35-0.65 nH, **FAIL at 0.75 nH
  (mu -1.02 at 12 GHz)**. [READ] `spec/package-channel.json` `board`: die paddle 4.0 x 5.2 mm under a
  3.932 x 5.122 mm die (34-39 um exposed per side, so no paddle downbond); bond fingers at +-4.3 mm
  (E/W), 74 fingers for 74 pads (no spare land); RF_RX bonds 2.60/2.69 mm = 2.2-2.7 nH. [WEB] Run-1
  bonding rules: wire 1-3 mm, <= 45 deg, no crossing; CoB needs the default 74-pad ring, extra pad
  openings allowed but no statement on extra bonds or downbonds.
- **Inference [INF].** The shortest ground return available is a ~2.3 mm wire to a neighbouring ground
  finger: about 1.9-2.3 nH single, roughly 1.1-1.3 nH for two in parallel. Both are above the 0.75 nH
  instability point. `spec/board-requirements.md` B18 also still uses "bond 1.5 nH +-0.2" for the RF
  input where the package file says 2.2-2.7 nH. Integration-plan M4 worries about coupling of the
  downbonds, not whether they can exist. RC-16j is in progress and uncommitted, so this is cheap to fix now.
- **L/S.** H / M (primary RX path oscillates or never matches; the bypass + board-LNA fallback survives).
- **Cheapest decisive check.** Ask wafer.space whether CoB assembly accepts a custom bond diagram with
  double bonds to an existing ground finger; re-run the existing stability screen at Ls = 1.0, 1.5, 2.0 nH.
  If it fails, degenerate on-chip (small spiral or none) and drop the two extra pads.
- **Owner.** RF RX + pads. Proposed ID RFR-12.

### 5. Digital hold is signed off with no on-chip variation and a self-made Liberty
- **Evidence.** [READ] `integration/pt_digital_macro.sdc:246-284`: one uniform derate on cell and wire,
  clock and data, early and late ("one global corner, not OCV"), 0.25 ns uncertainty.
  `evidence/digital-hardening-evidence.json` (CLOSE_R2): every corner used
  `gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib`; ff_window hold slack `ref` +0.043 ns, `sclk` +0.228 ns,
  `hpair_tx` +0.258 ns; clock skew worst-hold -1.41 ns. `verification/digital_hardening/sta_signoff.py:31-42`
  now uses self-characterised `char:ff_022C_3v35` / `ss_032C_3v15` libraries; the foundry
  `ff_n40C_3v60` / `ss_125C_3v00` libraries are explicitly "not timing". GLS has no SDF.
- **Why it matters.** Hold cannot be fixed by slowing a clock. The SPI/regfile domain is the root of the
  no-dead-chip plan and sits in the same 2.8 mm2 macro. A 5 % early/late split on a 1.4 ns clock path is
  ~70 ps, the size of the smallest slack; the self-characterised Liberty has no silicon or foundry
  cross-check. The register has DIG-01 (setup/rate) but no hold/OCV/Liberty-validity row.
- **L/S.** M / H (dead digital = dead chip).
- **Cheapest decisive check.** (a) Re-run signoff STA with `set_timing_derate -early 0.90 -late 1.10` on
  clock networks and require >= +0.3 ns hold in the sclk domain; (b) also run hold on the foundry
  `ff_n40C_3v60` library as a bound; (c) characterise the tt_025C_3v30 point with the same in-house flow
  and compare with the foundry file arc by arc.
- **Owner.** Digital. Proposed ID DIG-07.

### 6. There is no independent golden netlist for the chip, and no simulation crosses the analog/digital boundary
- **Evidence.** [RUN] `integration/pt_chip.sv` is 157 lines; `pt_analog_physical`, `pt_host_physical`,
  `pt_debug_physical` are `(* blackbox *)`. `integration/models/` contains only `core_bias`. The device-level
  chip netlist is generated by the assembler itself (`verification/chip_assembly/netlist.py` ->
  `pt_chip_full.spice`, 150 instances, 485 ports unbound at last run).
- **Why it matters.** Top-level LVS, when it exists, compares the layout with a netlist written by the
  same script that placed and wired it. A wrong bit-to-pin binding or an inverted enable among the 573
  `analog_cfg` bits is LVS-clean by construction. INT-22 lists mismatches found by hand; nothing would
  find the next one. (The mode-walk agent covers intent; this item is about the missing mechanical check.)
- **L/S.** M / H.
- **Cheapest decisive check.** Generate the binding table a second way, from `spec/register-map.json`
  plus each block's port list and reset-safe polarity, and diff it against `pt_chip_full.spice`. Then one
  Verilog sim with trivial behavioural stubs per analog block (enable/ISO/power-good only): write every
  register, assert the expected pin toggles and no other.
- **Owner.** Integration + digital. Proposed ID INT-27.

### 7. Three different PDK commits, an old KLayout, and an empty process lock
- **Evidence.** [RUN] Tool images: PDK open_pdks 1.0.605, commit `f6eeac7` (nodeinfo in the image), with
  `"gf180mcu_ws_klayout": "WS_KLAYOUT_COMMIT"` left as a placeholder. [READ] the local precheck clone
  (`scratch/chip-assembly-dev/precheck-run/Makefile`) pins `d658698`. [WEB] the live precheck and template
  pin `792ef67`, with a PDK-update PR open. [RUN] `processes/gf180/process.lock`: every field `null`,
  status "unresolved". KLayout 0.30.9 (analog image) and 0.30.7 (canary) against the 0.30.11 that fixed
  silently dropped violations in parallel DRC [WEB]; block runs use `workers=1` so they are probably
  unaffected [INF], but the local precheck ran `workers=4` and its antenna deck crashed in
  `ReportDatabase::save` [READ `precheck.log`], so **the antenna deck has never completed on a top**.
  The local precheck clone also has no ID-cell stage; the live one checks QR/shuttle/project/marker cells
  at fixed coordinates with `--cob` [WEB].
- **L/S.** M / M-H (61 "clean" verdicts may not hold on the submission deck, discovered in the last week).
- **Cheapest decisive check.** Pull the live precheck at its pinned PDK and KLayout, run it on the existing
  247 MB placed top and on five representative block GDS, diff rule counts against the local results.
  Fill in `process.lock`.
- **Owner.** Integration. Proposed ID INT-28 (INT-14 is the nearest existing row and names none of this).

### 8. Evidence staleness is the norm, not three blocks
- **Evidence.** [RUN] `freshness.json`: of 51 evidence files, **6 are fully fresh**, 43 cite at least one
  source whose hash no longer matches, 2 carry no hashes. `lna`, `rxmix_i`, `rxmix_q` evidence also cites
  a GDS/`.mag`/extracted netlist that is no longer the file on disk. Digital hardening evidence: 20 of 26
  RTL/flow sources changed and 4 cited RTL files no longer exist. All 61 KLayout DRC records do match the
  current GDS. [RUN] mtime check on the 40 inventory pairs: `clockmux`, `prescale`, `wordclk`, `polyphase`
  (GDS 33-46 h newer than the `.ext.spice` the assembly binds), `vco_replica`, `aosc`.
- **Caveat.** A changed generator hash does not prove the output changed (shared `layout_engine.py`,
  `convkit.py`, `netlists.py` edits fan out to every block). That is the point: nobody can tell which.
- **What the register has.** MOD-05 names digital, slicer, pll_ring and DAC. MOD-07 covers weak checks.
- **L/S.** H / M.
- **Cheapest decisive check.** Add `check_evidence_freshness.py` to the readiness gate; for the six
  timing blocks re-extract from the current GDS and diff device counts against the bound netlist.
- **Owner.** Integration (evidence audit, not yet restarted per SESSION-STATE). Fold into MOD-05.

### 9. The tapeout artefacts live on one nearly full disk and are not in git
- **Evidence.** [RUN] `.gitignore` ignores `*.gds` and `scratch/`; 12 GDS are tracked, ~200 block GDS and
  the 247 MB top are not. `scratch/` is 116 GB with 47 tracked files; SESSION-STATE lists live work there
  that is "uncommitted" (LNA redesign, pads PD47, digital run12). Root filesystem 96 % used, 36 GB free.
  About 130 dirty paths (78 modified, 54 untracked). `processes/README.md` already records one tool image that
  vanished from the local daemon and could not be rebuilt.
- **Why it matters.** `.mag` and netlists are tracked, so layouts are in principle regenerable, but not
  bit-identically and not without the exact image. A disk-full event during a flow run produces truncated
  GDS/JSON with a zero exit in several scripts (`|| true` in `run_digital_hardening.sh:82`).
- **L/S.** M / M-H (schedule loss at the worst time, or a truncated file reaching assembly).
- **Cheapest decisive check.** Snapshot `projects/.../generated` GDS plus the tool images off-box today;
  free or extend the disk; record a sha256 manifest of every inventory GDS in git.
- **Owner.** User/coordinator. Proposed ID INT-29.

### 10. Nothing exists on the far side of the connector, and no one is co-designing it
- **Evidence.** [RUN] No board design files, no FPGA constraints or gateware, no bring-up software in the
  repo (find for `*.kicad*`, `*.xdc`, firmware/gateware/bringup: only two verification scripts).
  `spec/board-requirements.md` has 45+ obligations (B1-B44), several of which only a real layout can
  confirm: remote-sense regulator, 23 bus switches at <= 3 pF, LO at +9 dBm per leg in quadrature, a
  temperature-controlled plate where the connector sits (PKG-07), trimmers. No NVM on the die [RUN grep]:
  every trim (bandgap, bias trunks, slicer offsets, USB HS bias, LNA ctrim) is reloaded by host software
  at each power-up from a board EEPROM that is not designed. No bring-up supply current limit is specified
  (integration-plan G1 mentions one; `board-requirements.md` has none).
- **Why it matters.** Item 4 is exactly the kind of error a board/assembly co-design loop catches before
  tapeout. HL-05 tracks dependence on FPGA gateware; nothing tracks the absence of the board.
- **L/S.** H / M (dies arrive in Q2 2027 and cannot be exercised; pin-level infeasibilities found late).
- **Cheapest decisive check.** A one-week paper carrier design: schematic + placement of the B-list around
  the 70-pin connector, and a pin-by-pin FPGA bank/voltage/clock-capable check. Deliverable is a list of
  B-items that cannot be built.
- **Owner.** New "board/bring-up" owner. Proposed ID BRD-02.

### 11. One MPW lot at an unknown corner, and the passes we have are tt passes
- **Evidence.** [RUN] Of the 16 rows in `performance-requirements.json` that are meets/marginal, about 10
  rest on tt-only or ideal-LO results (HL-H2D-MARGIN, four WR-*-TXSWING, RF-TX-POUT, RF-RX-IRR, RF-CS-IQ,
  RF-TX-IRR, RF-WIFI-LOLEAK). Known corner fails already recorded: QVCO ss top 2.349 GHz, slicer 2.5 Gb/s
  at ss, aosc at ss, pll_ring 810 MHz at ss. [WEB] No PCM/corner data is confirmed to ship with dies.
  [READ] The on-die process monitors (`char_ro33/ro50`, `vco_replica`) have no CLK_OBS/ATB codes (INT-04,
  CSP-01), so the lot corner cannot be read from the die either.
- **L/S.** M / M (a slow lot turns most primary routes off; without a corner readout it is undiagnosable).
- **Cheapest decisive check.** Ask wafer.space for Run 1/2 PCM or ring-oscillator data; wire one RO to
  CLK_OBS as a tier-1 item so die 1 reports its corner in the first hour.
- **Owner.** Coordinator + timing. Fold into INT-04 with a raised score.

### 12. Resistor, MIM and skew corners are not swept where they matter
- **Evidence.** [RUN] grep of flow sources (excluding generated): no `res_ss/res_ff` selection anywhere in
  `wired_rx` (termination, CTLE, vthdac), `rf_rx` (TIA, filter) or `core_support` (bandgap, biasgen, POR);
  no `mimcap_ss/ff` in `wired_rx`, `wired_tx`, `rf_tx`, `converters` DAC path, `pll_vreg`; `sf/fs` appear
  in 1-4 files per family. The PDK provides all of them (`res_typical/ss/ff`, `mimcap_*`, `sf`, `fs`,
  `statistical`, `fets_mm`). `design-assumptions.md` lists poly R +-20-25 % but only claims the bias trim
  covers it.
- **Why it matters.** RC time constants (filter corners, CTLE zero, POR delay, aosc) move with R x C
  together; MOS corners alone under-state the spread. The Edwards POR is the tier-1 block with a known
  slow-ramp weakness and it has only MOS corners.
- **L/S.** M / M.
- **Cheapest decisive check.** Add `res_{ss,ff}` x `mimcap_{ss,ff}` to the existing envelope sweep for
  POR, bandgap/biasgen, aosc, termination, bbfilter, CTLE. Existing benches, four extra corners each.
- **Owner.** Each block owner; core_support first. Proposed ID MOD-19.

### 13. Process options used but never confirmed with the shuttle
- **Evidence.** [RUN] Device census of generated netlists: `nfet_06v0_nvt` (native Vt, 360 lines; NAT
  layer in `pt_pll_vreg.gds`, `pt_pll_vreg2.gds`, `pt_vreg_pass.gds`), `nfet_06v0_dss` (ESD), DNWELL in
  `rfdriver.gds` only, `ppolyf_u_1k` (2100 lines), `cap_mim_2f0_m4m5_noshield` (846), `cap_nmos_03v3_b`.
  [WEB] gf180mcuD defines 5LM / 11K top / MIM under top metal / 1k poly; an open precheck PR adds an
  unsupported-layer check; no wafer.space statement found on native Vt, deep n-well or the fab MIM
  density. [RUN] Good news: no MetalTop (53/0) or Via5 (82/0) in any of 206 GDS; one MIM type everywhere.
- **L/S.** L / H (a missing implant silently changes the ring regulator pass device or PA isolation).
- **Cheapest decisive check.** One question to wafer.space listing NAT, DNWELL, SAB/dss, HRES 1k, MIM 2 fF.
- **Owner.** Pads/integration. Proposed ID INT-30.

### 14. Bond geometry was checked once, on a different board revision, before the bond map changed
- **Evidence.** [READ] `analog/pads/generated/packaging-audit.json`: checked 2026-10-18 against
  `run-2/1x1-cob` board rev `5cb4668`, provider template `33e4b5e`; `contract.json` pins template
  `0de7e39`; MANDATE says "Run 1, TT01"; the shuttle would be Run 3. Result then: max wire 2.991 mm, max
  angle 38.7 deg. [WEB] limits: < 3 mm, <= 45 deg, no crossing. Since then: PD22 bond map, mirrored
  wired pads (B24), stacked `pad_hspad`, TLP site, two LNA source pads. `contract.json`
  `candidate_signal_sites` is declared stale yet still drives `pads/design.py` and `check_contract.py`.
- **L/S.** M / M (assembly house refuses or re-maps the bond; 9 um of length margin).
- **Cheapest decisive check.** Re-run `packaging_audit.py` on the v6 pad centres against the Run 3 board
  file, adding the crossing and length rules; re-baseline `candidate_signal_sites`.
- **Owner.** Pads. Proposed ID PKG-09.

### 15. The "every failure yields data" premise is still unbuilt (tracked as INT-04 at score 12)
- **Evidence.** [RUN] `spec/tapeout-readiness.json`: `observable` is open on 33 of 33 chain blocks and 8
  of 12 core blocks; `fallback` open on 15 of 33. The tapeout plan's acceptance criterion is exactly
  these two tests.
- **Why it is here.** It is in the register, but scored below 60 other rows. With the die over-full by
  1.4-3.0 mm2, ATB leaves and observe taps are what gets cut last-minute. If they go, a partially working
  chip is indistinguishable from a dead one.
- **L/S.** H / H for usefulness of die 1.
- **Cheapest decisive check.** Per block, one line: ATB/CLK_OBS/DBG code, leaf placed in v6 (y/n),
  simulated (y/n). Refuse freeze of any block without it. Raise INT-04 to 20+.
- **Owner.** Coordinator.

## 3. Checklist (handled / assumed / absent)

**handled** = an artefact shows the check ran and passed; **assumed** = relied on, not shown;
**absent** = no artefact, no register row. "Tracked" = a register row exists (ID given).

### Shuttle / foundry submission
| Item | State | Basis |
|---|---|---|
| Slot size 3932 x 5122 um, origin, dbu 0.001 | handled | [WEB] standard 1x1; [READ] local precheck size stage passed; [RUN] all 206 GDS dbu 0.001 |
| Single top cell, name | handled | [READ] `pt_chip_top`, local precheck top stage passed |
| Seal ring / GUARD_RING_MK, GR.2 10 um | handled (old top) | [RUN] 167/5 present in `packaging-assembly.gds`; GR rules executed with 0 hits in `drc-v3.log`. Redo on v6+ |
| QR / shuttle / project ID / marker cells | assumed | Referenced in `pads/packaging_assembly.py`; local precheck clone has no ID stage; live one checks fixed coordinates [WEB] |
| CoB pad mask (74 pads, power/ground fixed) | handled (2026-11-10 top) | Local precheck stage 04 passed; not re-run since stacked hspad / TLP / LNA pads |
| Global density min/max | **absent** | Item 2 |
| Fill generation, fill keep-outs, post-fill verification | **absent** | Item 2 (MT-03 partial) |
| Wide-metal slotting (30 um) | handled at block level | [RUN] 55 GDS have >30 um metal (pads, MIM plates), all KLayout-clean incl. MSLOT; top v3 had MSLOT4.1/5.1 x2 open |
| Forbidden layers (MetalTop, Via5) | handled | [RUN] none in 206 GDS |
| Metal stack / MIM option consistent across blocks and sims | handled | [RUN] variant D in every DRC record; single MIM model; `mimcap_*` from the same PDK |
| Process options allowed (NAT, DNW, dss) | assumed | Item 13 |
| Manufacturing grid 5 nm | handled | [RUN] 0 off-grid vertices on COMP/Poly2/M1-M5 in 204 GDS (two >1 mm2 files skipped) |
| Signoff DRC deck (KLayout gates, Magic advisory) | handled in principle | [WEB]; [RUN] 61/61 block records clean and matching current GDS |
| Deck / PDK / KLayout version equals precheck's | **absent** | Item 7 |
| Antenna deck on a top | **absent** (crashed) | Item 7; AN-01 tracks the electrical risk only |
| Full-chip KLayout DRC | tracked, failing | 70,161 on unrouted v3 (INT-05, INT-13) |
| Max GDS size | assumed | Top is 247 MB; no limit found [WEB] |
| Submission deadline | **absent** | Item 1 |
| `processes/gf180/process.lock` | **absent** (all null) | Item 7 |

### PDK model validity
| Item | State | Basis |
|---|---|---|
| Device L/W inside model bins | handled | [RUN] 311 schematic netlists, ~67k MOS lines, 0 outside bins (nfet/pfet_03v3 L 0.28-50, 06v0 L >= 0.6/0.5, nvt L >= 1.8) |
| Temperature inside model range | handled | Models tnom 25; envelope 0-85 C |
| RF validity (Rg, NQS, induced gate noise, substrate network) | tracked | [RUN] rgatemod/acnqsmod/trnqsmod/rbodymod = 0 on all 196-198 cards; MOD-00/01, SUB-11 |
| Inductor model source, two-sided Q | tracked | Own Mohan + FastHenry, Q 4-10; MOD-03, LO-10 |
| Varactor / MIM Q, bottom plate | tracked | design-assumptions.md |
| Flicker corner (`fnoicor=1`) | tracked, partly used | [RUN] used in timing, baseband, lna benches only |
| Mismatch MC | tracked, mostly unused | [RUN] `fets_mm`/statistical referenced in adc, pads, rf_rx, wired_rx only; MOD-00, CNV-05 |
| Resistor / MIM / sf-fs corners | **absent** in several families | Item 12 |
| 6 V device rules | handled | [RUN] 06v0 devices at L 0.7 / 0.55-0.7; DRC clean |
| Deep n-well | handled / minimal | [RUN] only `rfdriver.gds`; DNW-01 open for others |
| Latch-up | tracked | LU-01 mitigated by manual audit; LU rules not in open deck |
| Self-characterised std-cell Liberty validity | **absent** | Item 5 |

### Whole-chip verification
| Item | State | Basis |
|---|---|---|
| Top-level DRC path | exists, slow but workable | 50-73 min per run on the unrouted top |
| Top-level LVS path | tracked, not run | INT-13, INT-20 |
| LVS on exported GDS per block | **absent** for 6 families | Item 3 |
| Independent top netlist | **absent** | Item 6 |
| Mixed-signal / control-path top simulation | **absent** | Item 6 |
| Top-level router for 2613 ports | assumed | No signal routing has ever been run (path-to-tapeout) |
| Device recognition under custom pads | tracked | INT-20 |

### Test and bring-up
| Item | State | Basis |
|---|---|---|
| Failure localisation via pins | tracked, unbuilt | Item 15 |
| What must work for any data out | other agents | always-on audit, M6 |
| POR override | fixed in macro, open at chip level | DT-10: `por_bypass` tied 0 in `pt_chip.sv` until a pad is bound |
| Board design | **absent** | Item 10 |
| FPGA plan / gateware | plan only | `spec/fpga-connection-plan.md`; HL-05 |
| Firmware / bring-up scripts | **absent** | Item 10 |
| Per-die calibration storage | **absent** on die | Item 10 (board EEPROM mentioned in B25 only) |
| RF measurement without the on-chip chain | handled on paper | BB taps, ext LO, `char_rffet` GSG (0.335 mm2, at risk in the area cut) |
| Supply sequencing | handled on paper | B26 power-before-drive, B1 supervisor |
| Bring-up current limit | **absent** | Item 10 |
| ESD handling for COB | tracked | MANDATE ESD tiering, RXR-07 |
| Bond geometry vs rules | stale | Item 14 |
| Downbonds | **infeasible as assumed** | Item 4 |
| Die thickness / backside | tracked | SUB-10 |

### System level
| Item | State | Basis |
|---|---|---|
| Link budgets with implementation loss | tracked | RFR-06, RXR-14, WRX-08 |
| Frequency-plan spurs | tracked | SP-01/02, SUB-03 |
| Reference requirements, pulling | tracked | B23, B35, LO-01, LO-11 |
| TX mask / emissions | tracked | RFT-03, EMI-02 (closed on analysis) |
| Blockers / duplex desense | tracked | RXR-04, RXR-12, SUB-07 |
| Thermal at 0.98 W on COB | tracked | TH-04, PKG-07 |
| HCI / TDDB / NBTI, ring ageing | **absent** (low) | [RUN] no HCI row; TDDB only as an ESD transient limit. Relevant to 3.3 V rings and LO-driven mixer gates; acceptable for a bench die, say so explicitly |

### Process and project process
| Item | State | Basis |
|---|---|---|
| Single-lot corner exposure | under-tracked | Item 11 |
| Blocks without fallback | tracked | 15/33 open in readiness |
| Evidence staleness (all blocks) | under-tracked | Item 8 |
| Uncommitted work / artefact custody | **absent** | Item 9 |
| GDS differs from simulated netlist | under-tracked | Items 3 and 8 |
| Duplicate / divergent shared cells | tracked | MOD-06 (115 name collisions); not re-measured here |
| Units / grid errors | handled | [RUN] dbu and 5 nm grid census |
| Schedule realism | **absent** | Item 1 |

## 4. wafer.space facts used (web, 2026-11-13)

Confidence as reported by the research pass; re-confirm anything marked M/U before relying on it.
- Slot 1x1 = 3932 x 5122 um incl. 26 um seal ring per side; user supplies the ring; exact bbox, origin 0,0 (H). `github.com/wafer-space/gf180mcu-precheck` `scripts/klayout/check_size.py`
- Precheck order: top cell, size, ID, density, zero-area, antenna, Magic DRC (advisory), KLayout DRC (gate), decks `all,-antenna,-density,-cup` (H). `precheck.py`
- ID cells with `--cob`: `gf180mcu_ws_ip__qrcode_id`, `__shuttle_id`, `__project_id`, `__marker` at fixed positions (H). `scripts/klayout/generate_id.py`
- gf180mcuD only; Via5 and MetalTop must be empty; PDK via Ciel at open_pdks `792ef67` (H).
- CoB requires the default 74-pad ring; power/ground pads fixed; extra pad openings allowed (H). Bond rules (Run 1): no crossing, <= 45 deg, 1-3 mm (H). `github.com/wafer-space/chip-on-board-wire-bonded-pcbs` `run-1/wirebonding/README.md`
- Run 3: purchase 9 Dec 2026, clean GDS 16 Dec 2026, dies about Q2 2027 (M; an earlier post said 15/29 Dec). `wafer-space.github.io` `_data/runs.yml`
- KLayout parallel DRC dropped violations before 0.30.11; GR.2 now enforced (H). Template issues #76, #77, #78.
- Unknown: density thresholds beyond the deck, max file size, native Vt / DNW support, downbonds, die thickness, PCM data (U).
