# RF RX LNA closure, session Q (started 2026-11-18). Resume point for a successor.

Scratch: `scratch/rf-lna-q/` (scripts e1..eN, logs, `w/` work dirs). Predecessor: `scratch/rf-lna-p/NOTES.md`, review
`scratch/review-lna3/REPORT.md`.

## Pass limits (declared before the redesigned stage was simulated or laid out; not to be moved)
- Differential stability, every row: mu > 1, K > 1, min Re(Zin) with the real extracted mixers >= 1.0 ohm, 0.1-30 GHz (unchanged).
- Common-mode stability, every row: min Re(Zcm) >= 1.0 ohm, 0.1-30 GHz (unchanged, predecessor's limit). The LNA-disabled value
  (mode 'off') is reported next to it as the passive reference. A row that misses 1.0 ohm is a MISS even where the disabled
  network misses it too; such rows are labelled "passive floor" and go to the coordinator as a limit-definition request.
- Supply cases: (S1) no credit: supply/ground bond 0.25 / 1 / 2 nH, lossless, no decap; (S2) real PDN two-sided
  (spec/power-delivery.md): die decap 3-5.4 nF with 0.03-0.1 ohm, island switch 0.2-0.3 ohm, bond 0.25-1 nH, with and without
  100 / 500 pF on the island rail; (S3) undamped lossless island decap 100 / 500 pF and no die decap (predecessor's rows): kept
  as pass/fail rows, not downgraded.
- Currents: RX <= 19.0 mA, lobias <= 11.8 mA at EVERY envelope corner (12 corners), not only tt.
- Chain NF: on-chip <= 4.1 dB DSB (RF-RX-NFSYS 8 dB - 3.91 dB board budget) at tt, ss and the pessimistic view (extpp ss 32 C
  3.15 V), on the real COB channel with lossy carrier parts, with the LO as delivered (not the ideal square).
- LNA NF (band rows): <= 6.0 dB; extpp derated +1.5 dB <= 6.0 dB. S11 <= -10 dB over 2.395-2.4885 GHz.
- Layout: Magic DRC 0, KLayout DRC 0, LVS unique on the GDS read back from disk, with a failing negative control.
- Negative controls: CM bench must fail on the LNA with the tail AC-shorted to VSS, tank feed shorted to VDD, CM network open.

## What the half-done redesign (uncommitted diff found on 2026-11-18) was
- LNTA: pseudo-differential CS 450 um/leg, 10 ohm gate R, replica bias, cascode with current-steering attenuator, tank on two
  170 um spirals to VDD, 4-bit tank trim, bypass MIM, source pins for degeneration; benches moved to on-chip degeneration spirals.
- Sound: topology choice, on-chip degeneration, current-steering attenuator, benches (stability bench with real mixers, det chain).
- Not sound / unfinished: common mode (below); differential margin 0.61 ohm at ff with 10 ohm; tank trim bank far off centre for
  any larger coil; cascode "keep" switches were NMOS pass devices: the cascode gate clipped at VDD - Vth (vcas never applied);
  current 15.7-21.4 mA over corners (replica bias); board network unbuildable; evidence stale.

## Common-mode mechanism (e1-e5, e9, e10)
- Reproduced: extpr ff 32 C 3.35 V, extracted: Re(Zcm) -57 ohm at 1.12 GHz; schematic -108.
- Not the cascode gate, not the gate bias (e2: ideal AC grounds change nothing).
- Cause: the CM drain current of a pseudo-differential stage returns through the VDD and VSS bonds. Above the parallel resonance
  of the bond loop with the on-chip VDD-VSS capacitance (~10 pF from the mixers: 1.12 GHz at 2 x 1 nH) the chip ground moves
  against the board as a capacitive source impedance -> negative input resistance, up to where the on-chip degeneration
  (Ls/2) takes over (~2.3 GHz). Frequency and depth follow the bond L exactly (0.25 / 1 / 2 nH: 2.12 / 1.12 / 0.80 GHz).
- A tail alone leaves -Cgs*Ct/(gm*Cpad^2) ~ -2 ohm, flat in frequency (tail-node capacitance = capacitive degeneration).
- Fix = three parts, all needed (e3, e4): (1) tail current source (CM current small); (2) local return of the load current:
  tank centre tap `vtk` fed through ~12 ohm and returned to VSS by 20 pF, dump branch on vtk; (3) common-mode-only loss:
  0.3 pF from each RF pad to a common node, 60 ohm from there to VSS (differential: virtual ground, only pad C).
- Remaining by construction: an undamped lossless island decap without die decap (S3) still fails (-12 / -46 ohm at 0.34 / 0.16
  GHz); it passes with decap ESR >= 0.5 x sqrt(L/C) (100 pF: 2 ohm, 500 pF: 1 ohm) or with the real die decap behind the island
  switch. Passive floor above 16 GHz: 0.83-1.02 ohm (disabled LNA: 0.83).

## Design as implemented (netlists.py lna(), final layout L6: 60,752 um2, Magic DRC 0, KLayout 0, LVS unique)
- True differential pair: CS 450/0.28, gate R 12 ohm, degeneration spirals 0.47 nH to pin `tail`; cascoded tail (505/0.5 +
  252.5/0.28) mirrored x168 from the 100 uA reference; lobias adds reference width.  Gate CM: replica diode on 7 kohm.
- 25 ohm ppoly across each degeneration spiral (e12): removes the differential negative-resistance dip at 13 GHz far more
  cheaply than gate R (NF own 1.95 dB at 10 ohm + 30 ohm damper vs 2.45 dB at 22 ohm gate R, same margin).
- Tank: centre tap pin `vtk`, PMOS feed 400/0.28 (~12 ohm), 19 pF NMOS gate capacitor (6 units 12 x 20 x 3 um; a 20 pF MIM
  does not fit over the core), dump branch of the attenuator on vtk.  Coil 220 um / 4 t (2.01 nH; pess = Q 4, L -15 %: Rp 105).
  Trim bank 0.05 / 0.1 / 0.2 / 0.4 pF, switches 30 x 2^k (the old bank's off-state parasitics alone were 0.8 pF per leg).
- Cascode-gate "keep / dump" switches are PMOS (the NMOS ones clipped the cascode gate at VDD - Vth); vcas = 0.87 x VDD.
- CM loss network 0.2 pF per pad + 180 ohm (final, L6).  0.1 pF + 200 ohm (L5) left only 0.33 ohm of in-band CM margin with the
  real die decap; 0.3 pF + 60 ohm costs pad-side C: Re(Zpad) 7 instead of 9 ohm = 0.6 dB more channel loss (e14).
- 20 kohm across each mixer feed pair: two-port K was < 1 below 0.7 GHz on the first extracted layout (output port lossless
  when the mixers are off); with it K >= 5.
- Emission order matters for area: splitting input / output devices into two loops cost 6k um2 and was reverted.
- MIM sides 12.0 and 15.0 / 15.02 um fail the standalone PCell DRC in this flow; 12.02, 14.1, 16.0 pass.

## Results on the intermediate layout L5 (superseded by L6; L6 numbers are in scratch/rf_rx/close/*.json and lna-evidence.json)
- e13_L5: extpr ff lowr: K 5.6, mu > 1, Re_diff min 1.18 (30 GHz end), Re_cm 1.18 at 2.4 GHz, < 1 above 9 GHz (passive floor:
  the disabled LNA shows the same), 0.46 at 30 GHz.  tt: Zin 8.9-j85.8, gain +3.89 dB (ct 9), NF own 2.37 dB (ideal match);
  extpp ss: -3.27 dB, 3.77 dB; extpr ss: +1.9 dB, 2.85 dB.  Currents 17.7-18.5 mA RX, 10.8-11.5 mA lobias (schematic e6).
- Real channel (ch1.py, e14, e15): loss of channel + per-chip carrier match (pess part Q, connector + 2 mm) vs Re(Zpad):
  6.4 ohm 3.3 dB | 10 ohm 2.24 | 12.7 ohm 1.85 | 20 ohm 1.26 | 30 ohm 0.91 dB (10 mm: 5.0 / 3.5 / 2.9 / 2.0 / 1.4).  The bond +
  trace series loss (~4.4 ohm differential at Q 40-50) against a 9 ohm pad resistance is the floor: ~2.3 dB at tt.
  ngspice (lna_band, lossy ladder): tt S11 -11.4 dB, gain 1.25-1.55 dB, LNA NF incl. channel 3.52-3.75 dB; extpp ss: gain
  -5.8..-5.6 dB, NF 5.18-5.41 dB.  => chain 4.1 dB DSB cannot be met on this channel (LNA + channel alone is 3.5-3.75 dB at tt).
- Chain runs (e15 ... chain): 3 um transients take ~1 h each under load; json in e15_*.json.

## Coordinator message 2026-11-18 (evidence audit): done / open
- Sources committed (4488095); interface rows RQ-1..3 (pins tail / vtk, spirals, supply rule).
- sf / fs corners are in lna_close.py.  R+C extraction: not in the rf_rx flow (C-only) - open.

## Final layout L6 (2026-11-18), evidence scratch/rf_rx/close/*.json -> analog/rf_rx/generated/lna-evidence.json (lna_close.py)
- Currents, 20 corners (tt/ss/ff/sf/fs): RX 17.75-18.62 mA (limit 19.0), lobias 10.80-11.44 mA (11.8): PASS.  Off 1.2 / 7.3 nA.
- Stability 0.1-30 GHz, 56 active rows: mu >= 1.008, K >= 2.94.  Differential min Re 0.975-1.29 ohm, every minimum at 30 GHz
  (disabled LNA 0.83 ohm): 24 rows miss 1.0 by <= 0.025 ohm.  Common mode 0.43-0.58 ohm at 30 GHz (disabled 0.39): all rows MISS the
  1.0 ohm limit as written; below 8 GHz >= 1.4 ohm with the real PDN at RX bias.  S3 (undamped island decap): -3.8..-29.5 ohm: FAIL.
- Band on the real channel (connector + 2 mm, per-chip parts, pess part Q): S11 <= -10.8 dB; LNA NF incl. channel 3.3-4.4 dB over
  5 processes (limit 6.0: pass); extpp ss 5.3-5.6 dB (+1.5 derate = 7.1: FAIL); 10 mm: S11 -9.9 dB (FAIL), NF 4.2-4.3 dB tt.
  Loss in front of the LNA 2.4-2.7 dB.
- Read-back LVS from the GDS (rb_lvs.py): netgen unique with properties, 981 = 981 devices; census flags 8.667 vs 8.67 um on three
  resistor segments; negative control (gate R 82 -> 80 um) fails as required.
- Chain (L5 layout, 0.1 pF CM caps, ideal square LO, real channel): tt 6.27 dB DSB (LNA + channel 3.75 dB, TIA terms +2.5 dB,
  gain 34.0 dB); extpp ss 10.9 dB (gain 26.7 dB).  L6 chain runs: e15_*.json in this directory.
- Independent review 4 (reviewer scratch scratch/review-lna4/): NO-GO for publication in this state, no redesign needed for
  stability.  Findings to act on: (1) bench blind below 100 MHz: supply anti-resonance with the die decap gives Re(Zcm) -0.7..-12.7
  ohm at 45-100 MHz at ff with low-loss die decap and >= 1 nH per rail (lna_close.py stab_lf reproduces it); (2) duplex bias with the
  real PDN 0.74-0.88 ohm in band; (3) lever: halve / remove the degeneration spirals (+0.95..1.8 dB gain, same LNA + channel NF,
  frees up to 50k um2) - NOT done, needs a corner scan; (4) no secondary ESD clamp at the gate behind the 4.4 pF MIM, no HBM
  check; full rail on the 19 pF MOS capacitor whenever the island is on; (5) spiral mutual coupling unmodelled; C-only extraction.

## NEXT (order)
1. Degeneration inductance scan 0 / 0.12 / 0.24 / 0.47 nH over corners and views (gain, NF on the channel, S11, stability incl.
   stab_lf, compression); decide on the two 25.2k um2 spirals.
2. Supply anti-resonance: either more CM loss below 100 MHz (cannot come from 0.2 pF) or an interface requirement on the die
   decap (>= 3 nF with >= 0.1 ohm, <= 0.5 nH per rail) - quantify with stab_lf.
3. R+C extraction of the core (the LO flow has an extresist recipe: analog/timing/lcvco/run_qvco_r5_ext.py); EM / coupling of the
   four spirals; start-up transient; HBM check of the gate or a secondary clamp.
4. Chain NF: TIA size decision (x3: about -1.5 dB, +36k um2 per mixer), fallback external LNA through `byp`.
5. Bring characterize.py / summarize.py in line with lna_close.py (they still carry the pre-COB board network).

## Package model from the pads owner (PC-26; lna_close.py pkg, close/pkg.json, interface row RQ-5)
- LM.stability(pkg='A_nom' ...) uses scratch/reviews/pads-core/lna-bond-model.spice instead of the lumped bonds.  24 rows, ff:
  K >= 7.1, Re_diff >= 1.50, Re_cm >= 2.98 ohm 5 MHz-1 GHz (no negative resonance: 0.25 ohm per wire damps it), 0.55-0.59 at 30 GHz.
- Bounce -> differential input (lna_close.bounce): A -17.9 dB nominal, B -40.3 dB (with die decap; -29 without).  rf_rx asks for B.
- Pad C tolerance (close/pad_c_tolerance.json): +0.1 pF/leg = +0.15 dB NF, -0.27 dB gain; S11 fails above ~+0.4 pF.
- Chain NF on L6, real channel (connector + 2 mm), LO as delivered (tb.LO_REAL), small TIA: tt +-0.37 V 6.15 dB DSB (gain 31.2 dB);
  extpr ss 32 C 3.15 V +-0.26 V 8.11 dB (26.0 dB); extpp ss +-0.11 V 14.7 dB (13.8 dB).  Target 4.1 dB: MISS everywhere.
  Warning for reruns: pass the LO as tb.LO_REAL[name]; a bare string silently runs the ideal square LO.

## Round 2 (coordinator decisions 2026-11-18: site B, tail / vtk bound, RQ-3 / 3a accepted, 30 GHz rows stay as misses)
Final layout of this round (L8): 64,712 um2, DRC 0 / KLayout 0 / LVS unique, read-back unique (1016 devices). Evidence:
scratch/rf_rx/close/*.json -> generated/lna-evidence.json. Earlier stage outputs: scratch/rf_rx/close_L6, close_L7a, close_L7b.
- Item 1 (stability): the 45-100 MHz path was the gate-bias node vg (f1.py: only an AC ground on vg removes it; vcas, tail bias, pb
  do not). Filter 60 kohm + 4 pF NMOS cap on vg. CM network 0.27 pF / 95 ohm (150 ohm left 0.95 ohm at att 63). With the pads
  owner's coupled model, site B, 38 rows: K >= 3.0, diff >= 1.33, CM >= 1.10 ohm 5 MHz-8 GHz. Lossless lumped rails still fail at
  47 / 67 / 97 MHz (-4.3 / 0.0 / -13.8 ohm). Start-up transients pass (no ringing; tau 1.6 us monotone; first 4 us version in
  scratch/rf_rx/close_startup_4us.json failed its raw window on the settling drift only).
- Item 2 (degeneration): f2.py full / half / none over corners; none: +2.0-2.4 dB gain, same NF on the channel, stable, S11 -8.9..-9.9
  dB (f3.py: more gate R restores S11 but costs 0.2-0.6 dB NF) -> halved (100 um, 0.31 nH, 14.0k um2). IIP3 -11.0 dBm (tt, ideal match).
- Item 3 (chain): BENCH BUG found by helper A: tb._ladder_net bond nodes bqp / bqn = Q mixer outputs in chain decks; fixed (bwq*);
  all earlier chain NF numbers withdrawn. Corrected, L8: tt 6.02, ss 7.97, pess 14.9 dB DSB. TIA x2 ~ -0.8 dB (+16.7k um2 per mixer),
  x3 ~ -1.1 dB (+36.0k): estimates from f_parts. physical-limits.md RX-CHLOSS written.
- Item 4 (helper B, scratch/rf-rx-r2b/): bypass path: 18 dB loss pads -> mixers, system NF ~20 dB with a 15 dB external LNA: FAIL;
  external LNA in front of the active LNA is the path that meets 8 dB (3.9-6.2 dB estimate). LO leak site B: -55.2 dBm nominal into
  the matched port (limit -57), offset 17 / 58 / 135 mV vs DAC +-144 mV.
- Item 5: off-MOS clamps (4 um PMOS to VDD, NMOS to VSS) at g_p / g_n / bpc_p / bpc_n: HBM screen 1.0 V (was 5.3-6.4 V); vtk cap on
  nfet_06v0 (9 x 12 x 20 x 2 um). Cost: pad resistance 6.9 -> 6.1 ohm, loss 2.9 -> 3.2 dB, S11 ff -9.94 dB.
- Item 6: R+C: scratch/rf-lna-q/rc (Magic extresist, analog image): 1372 R, ports / devices match, DC point wrong (4.95 mA) - find
  the split net before using it (g1.py). Monte Carlo not started. Helper A: characterize.py / summarize.py / run_rf_rx.sh reworked,
  rxmix / bb_tap / chain / summary regenerated. Review 5 brief: scratch/review-lna5/BRIEF.md.
- NEXT: (1) R+C netlist debug; (2) Monte Carlo; (3) S11 ff and IIP3 misses: less pad-side C (pads ESD option A may give it back) or
  accept; (4) bypass path resize decision; (5) lumped-rail LF rows: more vg filtering does not remove the 0.9 nF + island case.

## Round 3 (pt_rf after the split, started 2026-11-19)
Declared before any run of this round (not to be moved):
- Ground model (analog/rf_rx/pkg_rf.py): known answer = the same model on the OLD map within 2 dB / 20 % of the pads owner's B model
  (bounce conversion / |Z(die VSS)|); negative control (RFNC, no coupling into the RX wires) below -80 dB.
- stab_rf (lna_close.py): limits of stab_b unchanged: mu > 1, K > 1, Re(Zdiff) >= 1.0, Re(Zcm) >= 1.0 ohm, 5 MHz-30 GHz, die-VSS
  referenced sources; the 5-8 GHz common-mode minimum is reported separately. OLD_* and LNA-off rows are same-bench references.
- R+C extraction: usable only if its DC supply current is within 2 % of the C-only extraction at tt and the four tail / bias node
  voltages within 20 mV; negative control: the C-only netlist with one bias resistor opened must fail the same comparison.
- IIP3 >= -10 dBm, S11 <= -10 dB, chain NF <= 4.1 dB DSB: limits as in round 1/2.
Results so far (round 3):
- Ground model (pkg_rf.py, generated/pkg-rf-check.json): known answer OLD vs pads B within 1.7 dB / 8 %; negative control -300 dB.
  pt_rf map vs old map, nominal, with 5.4 nF die decap: |Z(die VSS)| at 2.42 GHz 2.21 vs 2.64 ohm (0.145 vs 0.174 nH effective),
  bounce conversion -40.2 vs -38.6 dB. The nine extra VSS bonds sit on signal fingers (5.8 nH to board ground through the carrier):
  near-zero effect at RF. Only bond 71 is within 3 sites of RF_RX (unchanged). Dominant 2421.875 MHz aggressor is D2H (same on
  both chips), not the macro. No better ground-site choice exists (per-bond conversions of 59-62 are 0.002-0.008).
- stab_rf: identical to the OLD map within 0.01 ohm; the 5-8 GHz common-mode miss does not depend on the bond inductance.
- R+C: the DC error is REAL (layout): 0.3 um M2 tracks + single PCell escapes. Fixed partly in lna_layout.py (wide tracks, via
  arrays, per-strip taps, pt_lna only): 129,592 um2. Magic extresist breaks meshes into trees -> use lna_netres.py (pads mesh
  solver) -> generated/lna.rext.spice. Metal-aware: current 14.5-15.5 mA (C-only 18.2), tt NF 4.8-5.1, S11 -9.7 (FAIL).
  Remaining route R: src 7-8, tank 9-14, x 7-12, tailx 4.7 ohm -> needs a placement-level LNA layout (heavy devices adjacent).
- Coordinator lead (extresist writes R on a subset of nets): confirmed, `extresist tolerance 10` wrote 39-57 of 84 nets. Rerun with
  `extresist simplify off` (all 84 nets): old L8 GDS 4.18 mA (C-only 18.3) -> the old DC error is a real layout defect, not the
  partial extraction; new layout 15.4 mA, matching the mesh-solver view lna.rext.spice (15.2 mA) within 1.5 %, nodes within ~10 mV.
  Raw extresist capacitors are double-counted (wired RX finding): use extresist only for R; recipe now `simplify off`.
- Coordinator check (lumped vs full-coverage R): the evidence view rext is NOT hand-drawn. It is a mesh solve of Metal1-5 and
  every via cut; it omits contacts and the light nets. Compared against the full-coverage Magic extraction (simplify off, all 84
  nets, contacts included) with the limits declared above: supply current 15.23 vs 15.44 mA (-1.4 %, pass <= 2 %). Bias nodes
  differ by 7-18 mV (pass <= 20 mV). atb_vdcm differs by 47 mV and tailx by 41 mV: these are not like-for-like, because the
  observation node and the bare label node are on light / unsolved metal in rext. rext is the slightly pessimistic view (less
  current). The hand patch Rvtkport (1.85 ohm) existed only in the superseded rc3 netlist and is used nowhere.
- Coordinator check (extresist double-counts substrate C, ~2.4x): the metal-aware view generated/lna.rext.spice has the C-only
  extraction's capacitors verbatim. Checked: 2151 node pairs, 8.298 pF total, 0 pairs differing from lna.ext.spice; lna_netres.py
  adds resistors only. The extresist cross-check (scratch/rf_rx/rc4) was a DC operating point, where capacitance does not enter.
  Its raw netlist is not used for any AC, noise or transient row. If the full-extraction view is ever used for AC: apply
  scratch/wired_tx/s14/chain/fixcap.py first.
