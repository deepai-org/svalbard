# AP4-5 LO/timing repack (LO/timing owner, 2026-11-13)

Work dir `scratch/lo-ap4/`. Published files only in `analog/timing/` (row plans `lo_rows.py`, engine option, `generated/`).

## Ownership check (git status at start)
- `analog/timing/fastcells.py` (uncommitted): wired RX resume 7 (2026-11-12), `ct_ring9` asymmetric reset `ASYM_RESET` (interface row RING-ASYM). Complete as an edit (self-consistent, documented in the comment), but it is wired RX's and its ring is being requalified: not touched, not committed by me.
- `analog/pll_vreg/pll_vreg.py` (uncommitted, 2026-11-11): one-line bench port fix for the r9d `pt_pll_ring` `BAND` port (`VR VR 0`). Wired RX / pll_vreg owner's; not touched.
- `pt_pll_ring_core`: created and maintained by wired RX (AC3-W13/W14, RINGAREA), shares `ct_ring9` with the CDR ring that is being changed (r9v committed, r9w uncommitted). The published `generated/pll_ring_core.*` is r9d (2026-11-11) and is older than the current ring cell. **Not repacked here.** Row AP4-5c asks wired RX to apply the same two levers when it republishes the ring (dry-run numbers below).

## Method (same netlists, no device change)
`layout_engine.generate` gives every net of a row one private Metal4 track in a channel above the row, and the outline is the bounding box of the rows. Two levers:
1. rows of similar device height share a row / rows are balanced to one width (lo_mmd had 110-200 um rows beside 379 um rows);
2. `over_cell` per row (new: a set of row indices): tracks over the devices in rows without MIM capacitors.
Row plans: `analog/timing/lo_rows.py` (`plan(block, 'r4' | 'ap4')`); the `r4` plans reproduce the published outlines exactly in dry runs (lo_ext 324.05 x 481.88, clk_obs16 197.68 x 469.84, lo_mmd_qdum 218.68 x 156.7, lo_obs 202.34 x 86.49).
Also fixed: `timing_flow.build_layout` copied macro `.mag` files into `generated/fast/` before the publish gate (a write into generated/ on a failing layout). Removed; the staged copy is published by `publish_stage()`.

## Finding: tank wiring load of the published lo_mmd (not an area item)
The published `pt_lo_mmd` has its AC-coupling caps in the bottom row of a 955 um tall cell and the LP/LN ports at the top edge: 0.9 mm Metal5 trunks on the I tank.
Extracted wiring C on the tank nets (C-only hierarchical / flat RC):
| cell | LP fF | LN fF |
|---|---|---|
| lo_mmd published (C-only hier / flat RC) | 141.9 / 200.7 | 91.3 / 125.9 |
| lo_mmd_qdum published (C-only hier) | 22.1 | 30.5 |
| lo_mmd ap4 final (C-only hier / flat RC) | 12.4 / 22.8 | 8.3 / 18.6 |
| lo_mmd_qdum ap4 final (C-only hier) | 6.3 | 2.8 |
| lo_obs published / ap4 (C-only hier) | 28.3 -> 7.1 | 22.9 -> 10.5 |
Published pair: the I tank carried ~100-170 fF more wiring than the Q tank and 50-75 fF more on LP than LN. Staged pair: about 6 fF per node more on I than on Q (of order 1.5-2 deg by the 2.2 deg per 7.5 fF sensitivity; could be trimmed further by giving the dummy the same track length), LP 4 fF heavier than LN in both cells. The QVCO extracted benches (`qvco_r5.py`, cl = 230 fF lo_ext load) contain neither the MMD nor the dummy load: **the tank-load change has never been simulated on the tank** (review C4; needs QVCO RC + lo_ext + lo_mmd + qdum + both lo_obs, published and staged).
Iterations: ap4a (caps in the bottom row): LN 18.6 fF to the N2 program-bit trunk -> rejected. ap4b/c (caps top row, pins 56-115 um apart) -> replaced by the trunk pair `TANK_PAIR` (LP/LN 4.8 um apart, same in both cells). Review: one short trunk of another net sits between the pair in each cell; coupling of LP/LN to switching CMOS nets <= 0.1 fF (was 11.8 fF to EN).

## Keep-out analysis for the QVCO corners (`keepout/ko.py`, `ko2.py`; `qvco/geo.py`, `lab.py`)
**Geometry (published `generated/lcvco/pt_lc_qvco5.gds`, bbox x -344..504, y -249.12..378.8 = 848 x 627.9 um):**
two 300 um spirals top-left / top-right (outer-turn metal bottom edge at y = 78.8; the spiral cell bbox reaches 58.8 only at
the feed stub near the core), core between them, aux (bias/PRE/ATB, x -229.1..390.1, y -249..-27) under the core.
Empty in every layer: bottom-left corner x -344..-232, y -249..58 and bottom-right corner x 393..504, same y.
Top-level tank ports IP/IN/QP/QN (Metal4) are at x = -206, y = -19.1..-22.7, i.e. 27 um from the bottom-left corner.

**Rule (LO owner, 2026-11-13; gf180mcuD has no inductor or inductor keep-out rule, so this is derived, not a PDK rule):**
1. no metal, poly or active of another cell within **25 um (one turn width) of the outer-turn metal** of either spiral, and nothing over a spiral or its feeds;
2. a neighbouring cell may sit beyond that, and must not enclose a spiral (no ring around it);
3. limits fixed before the runs: the neighbour may change the spiral by |dL/L| <= 0.2 % and dQ/Q >= -2 % at 2.45 GHz (L model range is +-15 %, a band step ~1.5 %, the pessimistic Q already 4).

**Source:** FastHenry (the deck generator of `lcvco/spiral.py`), spiral + the neighbour modelled as shorted closed Metal5 rings around the cell outline (the largest eddy-current loops its power straps and guard rings can form), `Zeff = Z11 - Z1k Zkk^-1 Zk1`:
| case | gap um | dL/L | dQ/Q | M (outer ring) pH |
|---|---|---|---|---|
| slot cell 100 x 290 under the outer third, 1 ring | 5 | -0.0033 % | -0.052 % | 11.1 |
| same, 3 nested rings | 5 | -0.0038 % | -0.050 % | 11.1 |
| same, 1 / 3 rings | 25 | -0.0008 / -0.0010 % | -0.012 % | 5.5 |
| same, 1 / 3 rings | 50 | -0.0003 / -0.0004 % | -0.004 % | 3.2 |
| 110 x 250 centred under the spiral (not a real placement) | 25 | -0.017 % | -0.24 % | 23.7 |
| 300 x 250 full width under the spiral (not a real placement) | 25 | -0.053 % | -0.67 % | 52.1 |
All pass with 110-250x margin at the rule distance (Z12 and Z21 from FastHenry differ by 7 %, so the margin is not sharper than that; no case in the set can fail and there is no known-answer mutual-inductance check: review D); even a full-width cell at 25 um passes. The magnetic keep-out is therefore not what limits the corners; the 25 um rule is kept as a round distance with margin for what the ring model leaves out (substrate eddy return under the cell, model error).
**Not covered by this analysis (stated, not hidden):** substrate/supply injection from a switching neighbour into the tank. lo_obs (CML /2, TSPC /4, CMOS driver into ~2 pF at LO/8) and the dummy prescaler are LO-coherent, so their component at the LO frequency is a static phase/amplitude offset; but their supply/substrate currents have lines at every multiple of LO/8 (lo_obs) and LO/2 (dummy), i.e. sidebands at +-306 MHz and multiples, which LO21 limits to -57...-60 dBc and nothing here quantifies. lo_obs is a debug block (EN = 0 in normal operation; the Q-side copy is always off). Also not covered: electric coupling from the outer turn (25 um away) and from the tank routes, fill exclusion, supply-strap routing, and the tank-route parasitics and I/Q route matching, which are the real cost of placing cells there. Integration-plan substrate check applies as for any block next to the QVCO.

**Slot A (bottom-left, next to the tank ports):** x -344..-233, y -249.12..53.8 (QVCO coordinates) = **111 x 302.9 um, 0.0336 mm2**. Fits `pt_lo_mmd_qdum` ap4 (99.98 x 194.68) + `pt_lo_obs` ap4 (98.4 x 93.09) stacked (287.8 um + spacing).
**Slot B (bottom-right):** x 393.1..504, same y, 0.0336 mm2: 600 um from the tank ports, so not for tank-connected cells; usable for the second (disabled, Q-side) lo_obs only if its tank route is acceptable, otherwise for decap/bias.

## Runs
(see the tables at the end)

## Re-prioritisation (coordinator messages, 2026-11-13 ~21:45 and ~21:52)
Mode-walk (MW-1/2/7/19/20/30) and supply-model (INT1-2/6/8) findings outrank the small repacks. Order now:
1. MW-20 joint LO -> mixer bench (`mw20/joint.py`), then LO drive fix or a demand on rf_rx.
2. MW-7 pin list: `analog/timing/LO-INTEGRATION.md` (written). MW-1, MW-2/19 answered there and in rows MW-1a, MW-2a, CM-1, MW-7a.
3. INT1-6: limit corrected (LO21), ring regulator measured at the QVCO load and found insufficient (LO22, `vreg/q.py`), currents LO23, INT1-8a.
4. lo_mmd + lo_mmd_qdum repack continues (does not touch lo_ext). **lo_ext, clk_obs16, lo_obs repacks are staged and clean (DRC/LVS/KLayout) but NOT bench-qualified and NOT published**: lo_ext is the cell MW-20 may change, so repacking it now would be wasted.
Found on the way: LO24 (lock time = 6-7 x R*C2 of the loop filter, `lock/lock_rc.py`), LO25 (pfdcp preset VDD/2 vs 2.1 V).

## lo_mmd old vs new, flat RC extraction (`mmd_bench.py`, `mmd/old`, `mmd/new`; incomplete because of the throttle)
Same deck and criterion as rung 4a. ss/32/3.15, 0.4 V per leg, cm 1.52 V, N = 50: **published divides to 3.6 GHz and fails at 3.8; staged ap4 divides to 3.4 GHz and fails at 3.6** (measured ratio 51.96). The repack costs about 0.2 GHz of maximum input frequency at the pessimistic corner (margin over the 3.1 GHz ff tank top: 16 % -> 10 %; over the guaranteed 2.70 GHz: 33 % -> 26 %). All nine rung-4a cases agree old/new (8 pass, the 20 mV must-fail fails), supply current equal within 0.3 mA, FB edge 175 ps earlier.
Not yet run on the staged cell: amplitude sweep, the README 2.98 / 3.1 GHz N = 32/64/98/126 set, supply pair.
**Independent review (`review/REVIEW.md`): layout clean and the same circuit (reviewer re-ran DRC 0 and LVS unique on the staged GDS), publishing NO-GO today** (bench set incomplete, corner coverage, no qdum bench, tank load never simulated). So lo_mmd / lo_mmd_qdum stay staged.

## MW-20 joint bench (`mw20/joint.py`): extracted pt_lo_ext (internal mode) into extracted rxmix_i / rxmix_q
Conversion gain re the 0/VDD square LO of the rf_rx benches, same deck: tt/27/3.3 -0.2 dB (tank 0.58 V) / -0.3 dB (0.40 V); ff/22/3.35 +0.3 dB; **ss/32/3.15 -8.0 dB (0.58 V) / -9.7 dB (0.40 V)** (LO swing 0.62 / 0.56 Vpp, peak Vgs 1.02 / 0.99 V). The reviewer's ideal-quad numbers (-4.6 ... -16 dB at tt) do not hold for the real mixer at tt, but the loss at ss is real and larger than the quad model's.
Variants (schematic lo_ext into the extracted mixers, ss, tank 0.58 V): XRC 18 um (published value) 13.51 dB, 36 um 15.12 dB, 72 um 15.76 dB (square 16.25 dB). Extraction costs most of that: published extracted 8.24 dB.
Candidate 1 (`cand/run`, XRC 72 um, published rows, 345.1 x 481.9): ss 12.96 dB. Candidate 2 (`cand/run2`, XRC 72 um, ap4 rows, 345.1 x 387.2, LO wiring 70 / 50 fF instead of 103 / 96): ss 13.54, tt 19.28, ff 20.85 dB (square 16.25 / 18.80 / 20.47).
Forced LO common mode (ATB_VB) at ss: candidate 2 at 2.45 V 15.20 dB, at 2.55 V 14.93 dB; published cell at 2.45 V 13.67 dB (from 8.24); published at tt with 2.55 V 17.52 dB (worse than unforced 18.62). So the ss loss is mostly the switching point, and the right level moves with the corner.
tb_lo_ext nom_int, tt, extracted: published 0.72 Vpp, 11.06 mA, Q-I 88.9 deg; candidate 2 1.01 Vpp, 15.55 mA, Q-I 88.8 deg.
The candidate is NOT qualified: no LO11 window, no 12 corners, no HBM, no external-mode runs. Source in `cand/src/lo_ext.spice` (published source untouched).

## How to resume
- lo_mmd bench: `python3 mmd_bench.py new rc/lo_mmd_new/pt_lo_mmd_flat.rc.spice cases_mmd_prio.json 1` (finished runs are cached in mmd/new/<run>/result.json); old side: `mmd/old` has 20 runs (README 16-case subset and the supply pair were not run on the old layout).
- staged layouts: `python3 lay.py <block> ap4`; published plans: `python3 lay.py <block> r4 --dry` must print the published outline.
- joint bench: `python3 mw20/joint.py <tag> <lo_ext netlist> <jobs> int:ss:0.58 ...`.
- throttle in force since 22:02 UTC: <= 3 sims, OMP_NUM_THREADS=1.

## MW-20 in band (supersedes the 20 MHz numbers above for anything quoted)
Review REVIEW-mw20.md: the IF 20 MHz runs sit on the TIA roll-off and understate the loss (rf_rx owner's own bench: -3.2 dB at tt for a sine). Rerun at IF 5 MHz, 300-700 ns, current rf_rx mixers (`mw20/snap2`, no hib pin), `mw20/ib_pub`, `mw20/ib_cand2`; halves of the window agree to 0.01 dB:
square 22.53 / 22.48 / 21.74 dB (tt / ff / ss). Published: tt 19.19 (-3.3), ff 20.58 (-1.9), ss 11.95 (-9.8), ss 0.40 V 10.18 (-11.6), ss VB 2.45 V 18.31 (-3.4). Candidate 2: tt 21.06 (-1.5), ff 21.46 (-1.0), ss 17.90 (-3.8), ss 0.40 V 16.76 (-5.0), ss VB 2.45 V 20.12 (-1.6).
Reviewer's correction adopted: swing and centre are two levers of equal size at ss; "a common-mode problem, not a swing problem" was wrong.

# Round 7 (new owner context, 2026-11-14)

## Coordinator message 2026-11-14 (placement constraints from integration-m23, rows INT23-1..13)
The message was written for a packing attempt; the LO owner runs no packer (die-fit study / assembly do). LO-side consequences, to be carried in LO-INTEGRATION.md section "Placement constraints" and honoured by anything staged here:
- INT23-2: QVCO spiral centres >= 1.7 mm from the west die edge, >= 1.0 mm along the edge from RF_TX and RF_RX pad pairs; no spiral axis toward the RF pads. LO-01 (PA pulling) reopened: TX on the on-chip LO is "OFDM-limited until measured" unless placed so.
- INT23-3: QVCO >= 800 um from the digital macro with a continuous tie sea (pessimistic: also deep n-well under the QVCO NMOS or grounded backside: QVCO revision item, not done); rings/rfdriver >= 500 um; LNA >= 250 um; **VTUNE filter C3 at the QVCO, not at lo_lf** (lo_lf revision item with LO24 R trim).
- INT23-8: lo_mmd >= 300 um from the core_bias bandgap core. Slot A/B cells (lo_mmd_qdum, lo_obs) sit inside the QVCO outline, so they move with it.
- INT23-13: forwarded clock from rx_aux_clk output >= 300 um from spirals/tank nets.
- INT23-1: ext-LO bond leakage: option (a) needs the lo_mode 3 CML window extended down to <= 0.63 Vpp (0.2 Vpp pessimistic): handed to the lo_ext revision as a bench question.
Conflicts visible from the LO side (packer must resolve, not decided here): tank nets must be short (lo_ext, lo_mmd next to the QVCO tank ports; LO -> mixers short) while the QVCO must be 1.7 mm from the west edge where the RF pads and mixers are; lo_mmd must be at the tank ports but 300 um from core_bias.

## Sub-tasks running (each <= 1 sim; LO owner 1 sim)
- polyphase deletion (CP4-2): helper, no sims.
- lo_ext revision: `scratch/lo-ap4/loext3/NOTES.md`.
- QVCO regulator: `scratch/lo-ap4/vreg2/NOTES.md`.
- LO owner: item 1 QVCO real environment in `scratch/lo-ap4/q7/`.

## Coordinator message 2 (chip-top demand-area.md vs CP4 inventory)
Also written for the die-fit ledger, not an LO task. LO inputs to that ledger: `lo_vreg` is booked at 0.0815 mm2 in demand-area.md; the regulator as designed is ~0.40 mm2 (vreg2/NOTES.md), a 0.25 mm2 variant is being costed. `lo_obs_q` 0.0174 is the published outline; staged 0.0092 and it sits in QVCO slot A (inside the QVCO outline: not additional area). polyphase deleted (-0.039).

## Item 1: QVCO in its real environment (`q7/`)
Bench `q7/envq.py` (one dir per run): RC-extracted RF cell + spiral model as `scratch/lo/r5_pn/ext12.py`, plus (a) the QVCO core-top wiring the RF-cell extraction lacks (`q7/topc`: C-only extraction of pt_lc_qvco5_core minus the RF cell: +23/16/10/11 fF to ground on IP/IN/QP/QN and 23.3 fF mutual IP-IN, **IN-QP**, QP-QN: the four tank tracks run side by side in the order IP IN QP QN, so the I and Q tanks are coupled by 23 fF), (b) real loads: extracted pt_lo_ext (mode 2) on all four nodes, flat-RC pt_lo_mmd dividing on I, pt_lo_mmd_qdum on Q, pt_lo_obs on both (EN 0), (c) chip-top route C per node two-sided (0 / 40 fF).
Proven first: `c230` + top=0 reproduces ext12.json exactly (PF115 b0 vt3.0: 2.6474 GHz, 2.216 V, -87.87 deg, 23.01 mA); must-fail (IBIAS 0) reports no oscillation.
Limits (unchanged, fixed in round 5): top PF115 (ss/32/3.15, L+15 %, Q4, C x1.15) band 0 >= 2.558 GHz; bottom OPT85 (ff/22/3.35, L-15 %, C x0.9) band 15 <= 2.330 GHz; start: oscillates, >= 0.5 V diff peak, |Q-I| 90 +- 10.
Results, QVCO on the die supply (`q7/env.log`):
| case | staged loads (ap4 cells + lo_ext cand2) | published loads | old 230 fF bench |
|---|---|---|---|
| TT b8 vt1.65 | 2.284 GHz, Q-I -89.5, 2.26/2.23 V (I/Q), 24.6 mA, loads 49 mA, MMD ratio 48.01 | 2.255 GHz, **Q-I -98.7**, 2.11/2.31 V | - |
| top PF115 b0 vt3.0 (route 40) | **2.532 GHz FAIL (1.9 % margin)** | **2.488 GHz FAIL (0.2 %)**, Q-I -98.8 | 2.647 |
| bottom OPT85 b15 vt0.3 (route 0) | 2.300 GHz PASS (4.2 %) | 2.275 PASS | 2.338 (2.6 %) |
| start PF85 b15 vt0.3 | 0.736 V PASS | 0.621 / 0.695 V PASS (I/Q) | 0.907 |
| start PFULL b15 vt0.3 | 1.119 V | 0.998 / 1.126 V | 1.235 |
Reading: the real loads are about 290 fF per node heavier than the 230 fF assumed, so the whole range sits ~4 % lower: the LO-10 miss moved from the bottom (2.6 %) to the top (1.9 %). The published lo_mmd / dummy pair gives 9 deg of quadrature error and 9 % I/Q amplitude imbalance (LO26 confirmed); the staged pair gives 0.5 deg. The MMD divides on the real tank (ratio measured only where the window is valid).
Fill (SG-3): markers IND_MK 151/5 + PMNDMY 152/5 (NDMY cannot be used: DE.3 limits it to 15000 um2) over both spirals + 25 um (clipped to the outline), the RF cell and the tank-track channel; stock fill on the framed cell leaves 0 dummies in the marker; tank net C with fill 1463.9 -> 1469.1/1469.4 fF (+0.4 %; without markers 2678-2884). KLayout DRC 0. Assembly must keep the 25 um halo outside the outline (markers are clipped to the cell).
Top netlist + LVS (SG-5): `qvco_rf_layout.py asm 7 8` + `asmlvs 8`: top-level port labels, GDS read back, flat extraction, spirals as documented shorts (Magic marks the IP-IN / QP-QN shorts; reference written in the same form), netgen unique; two must-fail references fail. Staged in `scratch/lo/r4_qvco2/asm8`, in review (`review/REVIEW-qvco-asm8.md`).
Running: `q7/vq.log` (QVCO behind the regulator at 2.38 / 2.56 / 2.69 / 2.79 V, load decomposition).

## Item 4: lo_mmd regression: cause found
`mmd7/netcap.py` maps every extracted net to its schematic net through the device terminals. ap4 vs published: prescaler master internal nodes PM.T +20 fF (20 -> 40), PM.S +12, PM.H +11, master outputs PAN +17 / PAP +9, PQ +5..8, FB +31 (FB rise 127 -> 172 ps is just the longer FB port trunk). Cause: in ap4 the master shares the cap row with the 53 um bias resistors (row 67 um tall instead of 43), so every prescaler pin escape is 24 um longer, and the slave row has Metal4 tracks over the devices.
Fix `mmd7/lay7.py v7`: master + slave + caps + the short program-bit gates in the top row (43 um), tall bias and followers one row down, tank-rate nets on the first tracks (`em.track_first`): PM.T 20.1 (published 20.2), PQ +3, everything else lighter than published; 379.9 x 368.4 = 0.140 mm2 (ap4 0.146, published 0.361); DRC 0, LVS unique, KLayout clean. RC extraction `rc/lo_mmd_v7`; bench queued behind the QVCO runs (`mmd7/bench_first.log`, `bench_all.log`, results `mmd/v7.json`).

## Coordinator message 3 (digital macro 1.404 mm2 of cells; pack for 2.81 / 3.0 / 3.2 mm2)
Third message written for the die-fit / packing agent. The LO owner has no packer and keeps no area ledger; not acted on beyond this note. LO numbers for whoever packs are in the "areas" table of the final report (and AP4-5a / the new rows).

## Coordinator correction (2026-11-14): the three ledger/packing messages above were misrouted: disregard them
(The INT23 placement consequences listed under message 1 remain valid LO inputs.) LO findings to handle instead:
1. LO-01 reopened (QVCO runs at f_RF, PA +9.5 dBm): placement rule into LO-INTEGRATION.md; sensitivity with real loads + fill; 2 f0 tone on rail/tail (bench not built yet).
2. External-LO leak (INT23-1): minimum external drive after the lo_ext fix + whether bond-map option L1 (adjacent I/Q pairs, ~1.5 deg per leg) is within the I/Q trim: questions sent to the lo_ext agent.
3. Spur table: reference choices that avoid in-band lines (answer by arithmetic, row).
4. D-LOVREG: VDD_LO state per LO mode; simulate the forward path; fix by cell or rule.
5. PC-5 (bias bank rails and taps on core VDD): agree / object by row.
6. LO enables are on the rf island group (ctl_ports.txt): reflect in LO-INTEGRATION.md.
7. PC-7: AUX_CLK receiver 25-810 MHz with the 3.1 mm differential route: helper agent, `auxrx/NOTES.md`.

# 2026-11-20 (LO owner resume)
- lo_mmd v7 (`mmd7/`, flat RC): 30 bench cases. Divides to 3.8 GHz at ss/32/3.15 (published 3.6, ap4 3.4): the regression is fixed. Fails: ff/22/3.35 at 0.4 V per leg and CM 1.52 V, 2.40 GHz N=56 (divides by 33) and 2.30 GHz N=48 (27.2); published passes 2.40. At the ff tank CM 1.83 V it passes 2.40 GHz with 0.55 and 0.7 V per leg (real ff tank: 0.9 V per leg). Also ss 3.2 GHz: one slipped period in three (single period right); ss 0.1 V per leg fails (floor 0.15 V). Not publishable before the ff low-amplitude case is understood (lighter prescaler nodes -> higher self-oscillation; suspected).
- QVCO range vs removed fixed C: `q7/RESULTS-vq.md` (window 60-110 fF per node).
- QVCO top r8 ports to the west edge (ASM-1): committed; `scratch/lo/r4_qvco2/top9`, `asm9`. Independent review not done.

## 2026-11-20 later: coordinator rulings, capacitance fix, divider envelope
- fixcap (wired TX tooling defect): QVCO RF cell rft6 RC netlist has no FLOATING caps; tank-net C equals the C-only extraction (IP/IN/QP/QN 213.7/216.7/212.1/218.9 fF): not affected. lo_mmd flat RC netlists were: substrate C 4.82 -> 2.73 pF (v7), 4.78 -> 2.77 (ap4), 6.07 -> 3.96 (published). Corrected files `rc/lo_mmd_*/pt_lo_mmd_flat.rcfix.spice`. Every v7 result above and the q7 real-load QVCO runs used the uncorrected divider netlist: QVCO tank load from the divider is overstated (top of range pessimistic, by an unmeasured amount): rerun needed.
- Real-tank divider input (`q7`): ss weakest PF85 0.37 V per leg, CM 1.36; ff weakest FFW85 (new corner: ff/22/3.15, L-15 %, Q4, +5 ohm) 0.67 V per leg, CM 1.65 (f 2.280 GHz); ff OPT85 0.95 V, CM 1.83; max 1.13 V per leg (tt). Envelope with 20 % margin, per corner: ss >= 0.29 V; ff >= 0.54 V, CM 1.32-2.20; max 1.36 V.
- v7 with corrected C: ss 3.8 GHz N=50 pass; ff 0.54 V at CM 1.32 (2.30 / 2.40 GHz) and at 1.98 (2.30) pass. ff 0.4 V / 1.52 V is outside the ff envelope (fails with no FB output): DROPPED from the pass list per ruling 3, recorded here.
- Not yet run in the envelope: ss 0.29 V, tt, supply 3.50 V, frequency ends 2.2 / 2.75 GHz, 1.36 V amplitude, corrected-C rerun of the full v7 set. No publish, no review yet.
- lo_ext vs tank (ruling 1): the external-mode CML pair (XE1/XE2, gates on the pad MIMs) is already separate from the tank; the tank load in modes 2 and 3 is the internal pair of ct_locml (2 x 20 x 6 um /0.28 per side, ~183 fF per node). No isolation switch helps: the lever is shrinking that pair (tank swing >= 0.37 V per leg) as a new LO-owned cell (ct_* files belong to the wired owner), then re-bench mixer drive (LO-RX-2). Range target (ruling 1): >= 3 % margin both ends => about 220 fF per node off the top case and about 360 fF per node more band C at band 15 (estimate from the sens slopes); needs RF-cell relayout of the band bank.

## 2026-11-20: internal CML input-pair sizing (ruling: weakest tank swing + 20 % => design at 0.31 V per leg, CM 1.36, ss/32/3.15)
Schematic variants of revision n4 (`loext3/var/n5k*`: ct_locml copy with k of 20 input units per side kept, tail unchanged; joint3 into the extracted mixers, IF 5 MHz; square reference 21.74 dB):
| input units per side (6 um each) | gain dB | vs square | LO at mixer V (min-max) |
|---|---|---|---|
| 20 (n4) | 20.95 | -0.8 | 2.10-2.93 |
| 12 | 20.75 | -1.0 | 2.15-2.90 |
| 8 | 19.89 | -1.85 | 2.29-2.89 |
Gate C off the tank (estimate, not extracted): 12 units ~ -60 fF per node, 8 units ~ -90 fF. Neither reaches the ~220 fF the >= 3 % range target needs from fixed C, so the band-bank relayout must carry the rest (or the pair goes below 8 units at a larger mixer loss). Proposed: 12 units (then LO-RX-2 with extracted numbers). Schematic only: layout, extraction, tt/ff and external mode not run.

## 2026-11-20: range fix, round 1 (`q7/r9*`, RF-cell variants `scratch/lo/r4_qvco2/rft9*`)
Ruling: >= 3 % at both band ends at process/voltage corners with nominal L; >= 1 % at the pessimistic bounds (top >= 2.584 GHz, bottom <= 2.307 GHz).
All runs: v7 divider with corrected C (`fix` loads), 12-unit lo_ext pair and r8 port tracks modelled as -60 + 15 = -45 fF per tank node (estimates, not extracted), route 40 fF top / 0 bottom.
| RF cell | SS b0 vt3.0 (nominal L, >= 2.635) | FF/3.50 b15 vt0.3 (nominal L, <= 2.262) | PF115 top (>= 2.584) | OPT85 3.35 / 3.50 bottom (<= 2.307) |
|---|---|---|---|---|
| r6b as built (MIM 8.4, varactor 17) | 2.770 PASS (5.1 % over 2.635) | 2.123 PASS (6.1 % under 2.262) | 2.5546 FAIL (-1.1 %) | 2.3121 / 2.3123 FAIL |
| t9d: bank MIM 8.7 um (+7.3 % C) | - | - | 2.5505 FAIL | - / 2.2778 PASS (1.3 %) |
| t9e: MIM 8.7, varactor 15 | - | - | 2.5654 FAIL | - / 2.2978 PASS (0.4 %) |
(2.635 / 2.262 = the band limits 2.558 / 2.330 with the 3 % margin; sf/fs and the 3.15/3.50 V supply pairs not run yet.)
Reading: the nominal-L criterion is met with margin; the pessimistic bounds need a top/bottom ratio of 2.584/2.307 = 1.1201 and t9d gives 1.1197. Fewer varactor fingers narrow the ratio (drop it). To get >= 1 % at both pessimistic ends: a larger bank (MIM 9.0 um: layout shorts VDDCI/VDDCQ to IN in the generator today, to fix) AND an upward shift of about 1.5 % (spiral L -3 %, or ~75 fF per node less fixed C; the 8-unit pair gives only ~30 fF).
Generator: `qvco_rf_layout.py` takes QVCO_PARAMS (JSON) for size variants; CELL_H follows the MIM; default build reproduces r6b (t9z LVS unique).

## 2026-11-20: range fix round 2, all extracted (`q7/r10`, `q7/r11`; queue `q10.sh`)
RF cell rft9f (bank MIM 9.0 um, straps/Q origin moved out 1.2 um, LVS unique), lo_ext n6 extracted (12-unit internal pair; macro built in loext3/var/n6, layout loext3/lay/a6, DRC 0 / LVS unique / KLayout 0, 370 x 417.6 um), v7 divider fixcap, core-top C re-extracted with the r8 port tracks (`topc9f.json`: IP/IN/QP/QN to ground 28.4/18.1/10.7/24.3 fF, IP-IN / IN-QP / QP-QN mutual 33.9 fF each, was 23.3), route 40 fF top / 0 bottom, no fill (markers). sf/fs: MOS skewed, MIM/MOS-cap typical (no skewed libs).
| case | 3.15 V | 3.50 V | limit | result |
|---|---|---|---|---|
| top b0 vt3.0 TT / SS / FF / SF / FS (nominal L) | 2.752 / 2.716 / 2.792 / 2.733 / 2.771 | 2.728 / 2.692 / 2.766 / 2.708 / 2.749 | >= 2.635 (3 %) | PASS, worst SS 3.50 V +5.2 % |
| bottom b15 vt0.3 TT / SS / FF / SF / FS | 1.963 / 1.897 / 2.037 / 1.960 / 1.967 | 1.963 / 1.896 / 2.037 / 1.959 / 1.967 | <= 2.262 (3 %) | PASS, worst FF +12.6 % |
| top pessimistic PF115 | 2.4995 | 2.4827 | >= 2.571 (0.5 %) | **FAIL -2.9 % (3.50 V)** |
| bottom pessimistic OPT85 | 2.2184 | 2.2184 | <= 2.318 (0.5 %) | PASS +4.8 % |
Q-I -83.7 ... -88.6 deg everywhere (limit 90 +- 10); all start.
Decomposition at PF115 3.15 V (r11): rft6 + old core top + n6 lo_ext 2.5296 (the 12-unit pair gains ~nothing over cand2: the -60 fF hand estimate was wrong); + MIM 9.0 2.5175 (-0.48 %); + port tracks 2.4995 (-0.71 %, mostly the larger IP-IN / IN-QP / QP-QN mutuals); cand2 instead of n6 2.5013.
Conclusion: 0.5 % at the pessimistic top is not reachable without the spiral change. The range sits ~3.5 % low at the pessimistic ends while the bottom has 4.8 %: an upward shift of ~3.5 % (L about -7 %) gives about +0.6 % top / +1.3 % bottom (estimate). Cheaper partial levers: tank port tracks at wider spacing (recover part of the 0.7 %), bank back to 8.4 (+0.5 %).

## 2026-11-21: range fix round 3 = QVCO r9 candidate, all extracted (`q7/r12`, `q12.sh`)
Spiral 290 um (`sp290/`), bank MIM 9.0 (`scratch/lo/r4_qvco2/rft9f`), tank tracks spaced 3 um (core top `top9h`/`asm9h`, C `topc9g.json`: mutuals 11.5 fF), lo_ext n4 extracted (20-unit, `loext3/lay/a4`), v7 divider (fixcap s14 netlist: LP 11.5 fF light vs fixcap16; rerun of the pessimistic top on `r16` loads pending), route 40 / 0 fF.
| case | 3.15 V | 3.50 V | limit | margin (worst) |
|---|---|---|---|---|
| top TT / SS / FF / SF / FS | 2.884 / 2.845 / 2.926 / 2.864 / 2.903 | 2.858 / 2.820 / 2.899 / 2.837 / 2.880 | >= 2.635 | SS 3.50 V +7.0 % (vs 2.635), +10.2 % vs 2.558 |
| bottom TT / SS / FF / SF / FS | 2.045 / 1.976 / 2.123 / 2.041 / 2.048 | 2.045 / 1.974 / 2.123 / 2.041 / 2.048 | <= 2.262 | FF +6.1 % (vs 2.262), 8.9 % vs 2.330 |
| top pessimistic PF115 | 2.6246 | 2.6070 | >= 2.571 (0.5 %) | +1.9 % over 2.558 |
| bottom pessimistic OPT85 | 2.3104 | 2.3104 | <= 2.318 (0.5 %) | 0.84 % under 2.330 |
All start; Q-I -81.8 ... -87.4 deg (worst 8.2 deg off, PF115 3.50 V; limit +-10). PASS on all ruling criteria. Not yet: phase noise, Kvco/band overlap, mismatch, the fixcap16 rerun, review.
Cleanup 2026-11-21: superseded QVCO variants (asm1-8, asm9g, rft-rft5, rft9a-e/y/z, top2-6, top9f/g, auxf1-4), divider ap4 runs and netlists, lo_ext 12-unit variants, round-1/2 run dirs and all waveform dumps > 1 MB deleted (scratch/lo + scratch/lo-ap4: 5.1 GB -> 0.95 GB). Kept: rft6 / asm9 / top7 / top9 (published r8), rft9f / top9h / asm9h (candidate), loext3 n4 / a4, mmd7 + rc/lo_mmd_v7 + rc/lo_mmd_old, q7/r12, result JSONs.

## 2026-11-21: divider v7 envelope on the fixcap16 netlist (`mmd/v7f16`, cases `mmd7/cases_envelope.json`, `cases_env2.json`)
fixcap16 (C-only reference of the same GDS): ground C 6.52 -> 4.34 pF, 2209 dropped coupling pairs restored (+2.39 pF); LP 47.5 fF (s14-fixed netlist had 36).
PASS: 1.90 GHz everywhere (ss 0.29 V at CM 0.89 / 1.63, tt 0.5 V, ff/3.50 0.54 V at CM 1.32 / 2.2); 2.90 GHz at tt 0.5 V and ff/3.50 0.54 V; ff 2.90 GHz 1.36 V; tt 2.45 GHz 1.36 V; ff/3.35 2.30 / 2.40 GHz 0.54 V; ss 2.45 GHz 0.29 V; must-fail 0.02 V fails.
FAIL: ss/3.15 2.70 GHz 0.29 V (N 48), ss/3.15 2.90 GHz 0.29 V (53.99) and 0.87 V (52.67), ss/3.50 2.90 GHz 0.29 V (48.0), ss/3.15 3.8 GHz (no output; was a pass on the s14 netlist).
Reading: with the restored coupling the divider's maximum input frequency at ss/32 is between 2.45 and 2.70 GHz at low swing and below 2.9 GHz even at 0.87 V. The earlier "3.8 GHz at ss" was an artefact of the dropped coupling caps. v7 is NOT publishable. The published lo_mmd has not been checked with fixcap16 either (likely the same direction). Needed: a faster prescaler (CML /2 latch current or load R) or an operating-range ruling (LO 2.3-2.7 GHz per die + margin vs the full tank range 1.97-2.93 GHz).

## 2026-11-21: divider at the per-corner top of the QVCO range (ruling: full tank range + 5 %, real swing/CM from q7/r12)
Cases `mmd7/cases_top.json` (12: tt/ss/ff/sf/fs x 3.15/3.50 V at top-band f x 1.05, plus the pessimistic PF115 tops; swing = r12 diff peak / 2, CM = r12).
Published lo_mmd, fixcap16 netlist (ground 9.30 -> 6.97 pF, +3.07 pF coupling restored): FAIL ss/3.15 2.99 GHz (N 48.0), sf/3.15 3.01 GHz (48.0); 10 pass.
v7, fixcap16: FAIL ss/3.15 2.99 (51.8), ss/3.50 2.96 (48.0), sf/3.15 3.01 (57.2), PF115 ss/3.15 2.76 (48.0); 8 pass.
Prescaler current sensitivity on the extracted v7 (tails x1.5 / x2, loads /1.5 / /2: same swing, tank load unchanged, +1.3 / +2.6 mA): all four failing cases still FAIL, with larger miscounts (N 47.9-62.9). The prescaler latch current is not the limiter; which stage miscounts (prescaler, cell A 2/3 at f/2, the follower between them) is not yet identified (needs probed waveforms).

## 2026-11-21: divider probe, runaway guard, r9 rerun with the published divider
- Probe (published lo_mmd, fixcap16, ss/32/3.15, 2.987 GHz, 1.308 V per leg, CM 1.40; `mmd7/probe/`): prescaler master, slave and the K0 follower pair all toggle at exactly f/2 over 40 cycles (ratio 1.00003 / 1.00002 / 1.00004), amplitudes 1.26 / 1.38 / 0.73 V pp diff; FB ratio 48.01 instead of 50. So the prescaler works; the miscount is downstream (cell 0, the CML 2/3 at f/2 = 1.49 GHz, sized for <= 1.55 GHz schematic). Not a small fix (CML 2/3 cell redesign): the guard covers it.
- Verified divider maximum per corner (published, fixcap16, top-of-range cases, real swing): passes at the QVCO top + 5 % at tt, ff, fs (3.15 and 3.50 V), ss 3.50 V (2.96 GHz), sf 3.50 V (2.98); ss 3.15 V: passes 2.76 GHz (1.085 V), fails 2.99; sf 3.15 V: fails 3.01 (lower bound not bracketed).
- `pt_lo_vtdet` (staged `vtdet/lo_vtdet.spice`, bench `vtdet/bench.py`, schematic): trip VDD - 0.303 ... 0.341 V, hysteresis 93-106 mV, 31-64 uA, all of tt/ss/ff/sf/fs x 3.15/3.50 V (`vtdet/results.json`). Gate-only input. Note: the trip (2.85 V at 3.15 V) sits below the VTUNE 3.0 V used for the range runs: tuning above it is "top of band" and band search should land the lock below it; the digital filter (>= 64 ref cycles after preset release) makes it a fault flag, not a tuning limit. Not laid out yet.
- RTL row LO-DIG-1 sent (status bits, limit table, back-off-and-retry response).
- QVCO r9 rerun queued with the PUBLISHED lo_mmd (fixcap16) + published dummy (`q7/q17.sh`, loads `r17`): the r12 numbers assumed the v7/ap4 pair, whose tank wiring is much lighter.

## 2026-11-22: r9 with the published divider (r17) and the guard-limited VTUNE (r18)
Loads r17 = published lo_mmd (fixcap16) + published dummy + lo_ext n4 + staged lo_obs; spiral 290, bank 9.0, spaced tracks.
VTUNE 3.0 (r17): top TT/SS/FF/SF/FS 2.848/2.811/2.889/2.829/2.866 (3.15 V), 2.823/2.787/2.862/2.803/2.844 (3.50 V); bottom 2.031/1.962/2.107/2.027/2.034; PF115 2.591 / 2.575; OPT85 2.293 / 2.293. Q-I -86.9 ... -92.8 deg (published dummy matches the published divider: better quadrature than r12).
Guard (vtdet R1 20 um, rerun `vtdet/results.json`): trip VDD - 0.259 ... 0.292 V, hysteresis 82-93 mV, 31-64 uA. Usable VTUNE = trip - hysteresis - 100 mV lock margin = 2.69 V (3.15 V), 3.01 V (3.50 V).
Guard-limited (r18; VT 2.645 / 2.96 first pass, then 2.69 at 3.15 V): top b0 TT/SS/FF/SF/FS 2.819/2.784/2.858/2.799/2.839 (3.15 V, VT 2.645) and 2.820/2.783/2.858/2.799/2.841 (3.50 V): worst SS 2.783 = +5.6 % over 2.635 (3 % rule) PASS. Pessimistic top PF115: 2.5706 at VT 2.645 (0.49 %, at the limit) -> trip moved up 45 mV -> 2.5738 at VT 2.69 (+0.62 %, rule 0.5 %) PASS; 3.50 V 2.5720 at VT 2.96 (+0.55 %) PASS.
Band 7/8 overlap (largest bank step; f(b8, VT max) vs f(b7, 0.3 V)): TT 2.370 / 2.287 (+3.6 %), SS 2.315 / 2.225 (+4.1 %), FF 2.431 / 2.358 (+3.1 %), SF 2.359 / 2.281 (+3.4 %), FS 2.381 / 2.294 (+3.8 %), PF115 2.125 / 2.038 (+4.3 %), both supplies within 0.1 %: overlap at every corner. Other band transitions not simulated (binary bank, 7/8 is the largest step).
LO plan 2.400-2.4835 GHz (+-IF): inside [bottom, top] at every corner incl. pessimistic (2.293 ... 2.574 at the pessimistic ends) with band overlap. Bottom ends unchanged by the VTUNE limit (VTUNE 0.3 V).
Open: charge-pump VTUNE ceiling vs 2.69 V (not checked), phase noise, mismatch, review, publish.
