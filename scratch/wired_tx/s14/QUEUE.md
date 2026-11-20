# Session 14 block rows: state and pending queue (2026-11-19)

Nothing published. Tables: `python3 table14.py`. Stop all queues: `touch STOPQ` (each queue finishes its current job).

## Netlists (snapshots in chain/net/, SHA256 in chain/net/SHA256 and in every result)
* `pt_wiredtx8.full.rc.spice` sha256 3fe4721839c8...: Magic extresist, tolerance 0.001, simplify off, flat
  (`chain/extfull.py`, GDS snapshot sha 9414183aeff0...). 124 ports, identical names and order to the drawn netlist;
  5231 FETs + 39 diodes identical; R 139 -> 15539; nets with R 1101 / 1774 (62 %; all others are single-tile nets);
  XSER 550/550, XMUX 165/185, XAUX 3/3, top 145/147, unnamed 238/889. R-collapsed netlist vs drawn: netgen
  "Circuits match uniquely". Sim time +5 % vs drawn (1481 s vs 1413 s for 40 ns), so no reduction is used
  (`rmerge.py` series-merge < 0.5 ohm removes only 306 of 15539 R).
* `pt_wiredtx8.rc.spice` sha256 093fdbec947e...: the drawn-R netlist (t14 rows); only for the calibration-method proof.

## Open finding: run detector does not assert on the full netlist (ss pess. 3.15 V, ring layout-11Nov pess.)
TX_RUN stays 0, bank off, no output (45 ns run; drawn netlist: RUN at 30 ns). The detector's phase copies XE k
(0.5/1 um inverters, about 35 fF each, 20.6 fF of it coupling to the neighbouring copy) swing only about 2 V instead
of 3.3 V; the pumps DN k stall at 0.45 V. These causes were ruled out: resistance (all R set to 1 mOhm: identical),
diffusion areas (all ad/as/pd/ps 0: identical), integration (reltol 1e-4, trap: identical), dot node names, port order,
pess transform, DC fights (op points identical). Device lists, per-net C and coupling partners of XE k match the
drawn netlist within 1.3 fF. The exact difference between the two netlists is NOT yet found.
Because of this, all full-netlist rows below use `ilk_bypass` (XMUX.RUNB forced low inside the netlist,
diagnostic only; verified: gate swing 1.49 V, 56.7 mA). Every such row FAILS the interlock requirement as is.

## Queues (at most two of my simulations at a time)
* qA (`qA.jobs`, drawn netlist): calibration-method proof at ss pess.: c0 codes [0,1,3,3,4,5,3,7] -> injected
  +4 codes on TR3 -> codes found by c0.
* qB (`qB.jobs`, full netlist, ilk_bypass): block cal + rows pad=C and pad=RC-typ for ssp 3.15 / ss 3.24 / tt 3.24 /
  ss 2.7 V, all at 3.125 Gb/s, ring=layout-11Nov (pess. at ssp), codes from that condition's block cal.
* qC (`qC.jobs`, starts after qA via `chainAC.sh`): attribution rows at ssp: ideal phases (pad C / RT), S=0.6
  (pad C / RT), mux-bench codes on the full netlist (drawn-vs-full delta against t14_ssp3125_C).
* Pad option A: not published at queue start (only tx_rt / tx_rh / tx_zero in scratch/pads-core/txr/models).
  q14.py logs a NOTICE when a new model file appears; then add rows with pad_model 'TA' (set its path in
  chain/chain14.py) at S=1.0 and 0.6.

## Results so far (18:40 UTC)
* bcD_ssp_c0 (drawn netlist 093fdbec..., ss pess. 3.15 V, ring=layout-11Nov pess., pad=C, codes [0,1,3,3,4,5,3,7]):
  slot error ps DC method [17.4,-4.3,5.2,1.0,-3.2,2.6,4.6,-23.3], probes (XMUX.XS k.X fall edges)
  [16.6,-5.0,4.3,2.8,-3.3,4.6,3.7,-23.6] (agree <= 2 ps); worst 23.3 ps > 8: mux-bench codes do not carry to the block;
  next codes [1,0,3,2,3,5,2,6].
* bcF_ssp_c0 (full netlist 3fe47218..., same condition, ilk_bypass): DC [0.9,-5.2,5.1,-1.7,-2.1,4.0,3.0,-3.9], probes
  [1.4,-4.9,4.1,0.4,-2.3,5.6,2.3,-6.5]; worst 5.2 ps (within +/-8); next codes [0,1,4,3,4,5,3,7] (used by the ssp rows).
* Pending: bcD_ssp_inj (TR3 +4 codes, negative control: must show slot 2 about +58 ps / slot 3 about -58 ps and undo
  it), bcD_ssp_c1 (residual after the found codes), all rows of qB and qC.

## New block (commit 5d73aae8, hysteresis detector, NAND(PH, RUN), trim pins right edge) - added 20:4x UTC
* Snapshot chain/net2/ (GDS sha d595e0e8..., drawn rc ec4c2d3f...), full extraction `pt_wiredtx8.full.rc.spice`
  sha afe061ac9ea2... (chain/extfull2.py), 124 ports identical in name and order.
* qD (third slot): bcN_ssp_c0 (block cal, NO detector bypass) -> N_ssp315_C (ss pess. 3.125, pad=C).
  Acceptance: eye within 5 mV of F_ssp315_C (old full netlist; note that row has the detector bypassed).
  If the cal reports no zero crossing / no output, the new detector also fails to assert on the full extraction.

## Calibration proof (drawn netlist, ss pess.) - PASS
bcD_ssp_inj: TR3 +4 codes injected on top of c0. Measured slot 2 +52.7 ps and slot 3 -52.8 ps against bcD_ssp_c0, all other
slots within 1.2 ps (probes: +55.1 / -55.2). Implied LSB 13.2 ps/code (14.4 assumed). The codes it finds,
[0,0,2,2,3,4,2,5], equal c0's answer [1,0,3,2,3,5,2,6] minus a common 1, so the injection is removed exactly.
Wrong codes leave a measured residual of 58 ps; the negative control fails as it must.

## First priority row
F_ssp315_C (full netlist 3fe47218, ilk_bypass, ss pess. 3.15 V, 3.125 Gb/s, ring=layout-11Nov pess., pad=C, codes
[0,1,4,3,4,5,3,7]): far 0 errors / 440, eye 0.1735 V / 0.578 UI, 61.8 mA -> FAIL (eye < 0.200).
Drawn-netlist reference t14_ssp3125_C (mux-bench codes): 0.157 V / 0.547 UI.
(chain13's gate-node score shows 100 errors / H 0 and run@None: TX_RUN never rises with the bypass, so the scoring
grid starts from chain13's fallback time. Not investigated; the pass criterion is the far-end score only.)

## 2026-11-20: ROOT CAUSE of the detector stall on the full netlist = extraction artifact (substrate C over-counted)
* Bisection (det/mini.py: all elements touching XE0..7 from each netlist, ideal phases, seconds per run):
  full XE swing 2.1-2.5 V vs drawn 3.2-3.5 V reproduced; all C removed -> both 3.35 V (identical); XE-XE coupling removed ->
  still 2.55 vs 3.4; caps to VDD/VSS removed -> both 3.1-3.8 V (identical). So the difference is the substrate caps.
* In the full netlist those caps carry a trailing "; **FLOATING" comment (5 tokens), and my earlier per-net C sums
  skipped them. That is why "per-net C matched" was wrong.
* Magic evidence (chain/xk/pt_wiredtx8/pt_wiredtx8_flat.ext / .res.ext): node XMUX.XE0 substrate cap 10.38 fF; the
  extresist rnode caps of the same net sum to 36.3 fF (n2 11.9, n3 22.1 fF); ext2spice ALSO writes the root's lumped
  10.67 fF -> 47 fF + 6.25 fF to VDD = 53 fF vs 14.2 fF in the C-only / drawn extraction. Block-wide substrate C 23.1 pF
  (full) vs 9.5 pF (.ext node records); per-net median ratio 2.1, up to 12x (D inputs).
* Fix: chain/fixcap.py scales each net's substrate caps (root + sub-nodes, grouped by base name, '#' stripped) to its
  .ext node cap; R and coupling C unchanged. Proof: mini bench XE swing 2.95-3.48 V (drawn 2.52-3.52); full block, NO
  bypass, ss pess. 3.15 V: TX_RUN rises at 29.4 ns (drawn 30 ns), XE0 3.28 V pp, DN0 2.39 V, gate 1.52 V pp, 51.8 mA.
* Corrected netlists: chain/net/pt_wiredtx8.fullfix.rc.spice sha 1fddfc3a074b..., chain/net2/pt_wiredtx8.fullfix.rc.spice
  (new block 5d73aae8) sha 72ba3f88c428.... Magic sub-node numbering (.tN) differs run to run; the fix groups by base
  name, so it is independent of that.
* The rcov audit (s14/rcov, commit be6e0c04) used the same extresist flow: its C_net figures for resisted nets carry
  the same over-count (its R figures are unaffected). Its RC-based failures are therefore overstated.

## INVALID results (over-counted substrate C x2.4 AND detector bypassed): kept only as labelled pessimistic deltas
qB/qC/qD rows on net/pt_wiredtx8.full.rc.spice (3fe47218) and net2 full (afe061ac):
F_ssp315_C 0.1735 V / 0.578 UI, F_ssp315_RT 0.1048, F_ss324_C 0.3494 PASS, F_ss324_RT 0.2084 PASS, A_ssp315_C_ideal 0.1954,
A_ssp315_RT_ideal 0.1155, A_ssp315_C_S06 0.2527 PASS, A_ssp315_RT_S06 0.1883; cals bcF_ss324_c0 / bcF_tt324_c0 worst 27-29 ps
with mux-bench codes. N_ssp315_C / bcN_ssp_c0: detector stalled (same artifact). qB/qC killed 2026-11-20.

## Current queues (corrected netlists, detector live, no bypass)
* qE: bcX_ssp -> X_ssp315_C, X_ssp315_RT -> bcX_ss324 -> C, RT -> bcX_tt324 -> C, RT -> bcX_ss27 -> C, RT.
* qF: bcW_ssp (new block) -> W_ssp315_C (confirmation: within 5 mV of X_ssp315_C) -> Y_ ideal-phase C / RT (codes 0)
  -> Y_ S=0.6 RT / C (codes from bcX_ssp).
* chain/runs/sp_new_fix: 40 ns new-block run on the corrected netlist (look at TX_RUN in its wave.txt, then delete it).
* sp_new_fix (new block 5d73aae8, fullfix 72ba3f88..., ss pess. 3.15 V, no bypass): TX_RUN rises at 29.4 ns, gate 1.52 V pp,
  pad 0.62 V pp, 50.1 mA: the new hysteresis detector also asserts on the corrected full netlist. Waveform deleted.
* 2026-11-20 owner rule: at most TWO simulation jobs (qE + qF). Never start a third. Never read generated/fast/pt_wiredtx8.*
  (a layout worker is changing it); only the snapshots in chain/net and chain/net2.
