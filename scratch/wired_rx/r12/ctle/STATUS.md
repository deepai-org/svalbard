# r12/ctle: pt_ctle r5 (replica-bias CTLE), staged, NOT published (sub-agent of the wired RX owner, 2026-11-20)

Nothing is written to `analog/wired_rx/generated/`.  Tree files edited: `analog/wired_rx/netlists.py` (ctle() and CTLE_*
constants only) and `analog/wired_rx/ctle.spice` (regenerated).  Every ngspice / Magic job goes through `../../slot.sh`.

## Gates (written 2026-11-20 09:30 UTC, BEFORE any r5 simulation or layout; not to be relaxed)

Corner set (every gate below is evaluated on all of them unless stated):
MOS/temp/supply: tt/27/3.30, ss/32/3.15, ss/32/3.50, ff/22/3.35, sf/32/3.15, fs/32/3.15, ss-pessimistic/32/3.15
(r7slicer/pess.py on every extracted netlist: wiring C x1.15, Rg, +25 % device C).
Poly corner crossed with each MOS corner: res_typical, res_ss (ppolyf_u_1k +20 %), res_ff (-20 %) = 21 combinations.
(sf/fs have no PDK passive section of their own: the poly corner is set explicitly.)  IBIAS = ideal 10.0 uA sink (the
trimmed value of analog/core_support/README.md); additionally reported, not gating: 7.5 and 12 uA (untrimmed extremes) at tt.

Bench: r11/chain/rc11.py + r10ctle/ch10.py chain (TX 50 ohm/leg -> COB P2 -> pad_hspad a6 physical-r-typ.spice (DVDD
first port, tied to the bench 3.3 V node), termination code per corner as rc11.TCODE -> 20 fF HS route -> pt_ctle r5
R+C extraction -> SL: published extracted pt_slicer (ONE bank), staged rxselect r2 (off), wmon_sel (off), 30 fF route).
ALL chain numbers below are on the R+C netlist of the r5 layout (C-only only as a reported comparison).

G1 eye: T3 stimulus (120 mVppd, COB only, as rc11.py), 2.5, 3.125 and 3.24 Gb/s, every corner combination: eye at SL
   >= 60 mVppd AND contiguous width at >= 60 mV >= 0.25 UI.  Metric: peak-distortion eye from the chain AC (ch10.pda,
   best code of 0-7 by the ch10.pick rule).  Confirmation: the worst cell of each rate (lowest PDA eye) is rerun as a
   clocked transient (rc11.tran, ideal clocks); it must also show >= 60 mVppd, >= 0.25 UI and 0 bit errors.
   Negative control: 3 pF per SL leg on one confirmed cell must fail.
G2 SL common mode 0.38-0.66 V (chain operating point, code 0) at every corner combination.
G3 gain spread: chain gain source-EMF/2 -> SL at 1.25 GHz, code 0, max - min over all 21 combinations <= 2.0 dB.
   (Reported alongside: the spread at the best-eye code, and the spread without ss-pessimistic.)
G4 supply current of pt_ctle (own VDD pin) reported at every combination; compared with r4 (10.7 mA tt).  Not gating.
G5 EM: every via group / contact group carrying DC current: current per cut <= 0.58 mA (85 C limit used by wrx_flow)
   with the design current x1.3; checked from the R+C extraction's via/contact resistors and the DC operating point at
   the highest-current corner combination (currents x1.3), plus the flow's by-construction record.  Metal tracks: <= 2.09
   mA/um (Metal1-4), 4.5 mA/um (Metal5) x1.3, from the flow record.
G6 layout: Magic DRC 0; KLayout precheck main + antenna decks 0 via gds_uniquify.publish_checked (block alone, private dir);
   LVS from the GDS READ BACK FROM DISK: netgen "Circuits match uniquely" AND no "Property errors" (device parameters
   compared); a negative control with one device parameter changed in the reference must FAIL.
G7 R+C extraction: Magic extresist with `extresist simplify off` (tolerance 0) as r11/rc_ctle; report net coverage
   (nets with resistors / nets with a device terminal); known answer (R x1e-3 within 0.1 dB of C-only) and negative
   control (R x10 differs > 0.1 dB).  Wire-R audit with the declared thresholds of scratch/wired_tx/s14/rcov (wire R <
   5 % of driver Ron, or R*C < 2 ps); additionally for DC-current paths >= 0.25 mA: series wire R <= 5 ohm per path
   (r4: 10-31 ohm).  Failing nets are listed.
G8 loop: replica-bias loop stable: phase margin >= 45 deg (loop broken at the error-amplifier output, every corner
   combination at least at tt/typ, ss315/res_ss, ff/res_ff, sf/res_ss, fs/res_ff), and the power-up / enable transient
   settles without oscillation.  Input C: CTLE RX_P/N wiring + device C not larger than r4 (97.6 / 95.2 fF wiring).

## Log
- 09:30-10:40 schematic study (v/sch, w1, w2; chain AC code 0, 21 combos, ideal 10 uA, termination code per combo from tcode.py): replica loop holds SL CM 0.438-0.556 V (w2); code-0 gain at 1.25 GHz spread 3.75 dB (sqrt(R) of gm*R_L + MOS corners: G3 likely to fail); w2 = sink 3x wider (F6, follower gain) + EA pair 20/0.5; ssp315 3.24 Gb/s T3 PDA 111-115 mV (schematic). Owner note: R+C netlists only via r11 mkrc.py + per-net C cross-check.
- 11:10 wrx_flow isolated-well primitive (iso NMOS) shorts VDD_WIRE_SW to VSS with 1 or 2 fingers (w 5/8/10 um), clean with >= 3 (bis/): replica follower = 3 x 3.34 um. Flow defect to report to owner (not edited).

## r5 staged (stage/ctle/gen, NOT published) - results 2026-11-20
Design: replica-bias loop (netlists.ctle r5).  Error amp (PMOS pair 2x20/0.5, diode loads, 20 uA tail from IBIAS) drives the existing
tail-bias diode so that a 1/6 replica half circuit (7 tail fingers, 1 input finger 16/0.28 gated at 0.30 VDD, one 1x3.6 um load strip,
follower 3x3.34/0.28 in its own isolated well, 2 sink fingers) holds its follower output at 0.15 VDD (poly divider, 20 x 10 kohm units).
Loads 6 x 1x3.6 um (600 ohm) straight to VSS (load switches removed: r4's 21-23 ohm load return and its over-limit Via4 are gone).
Sinks 3x wider (18/0.5 fingers; review F6). Tails 42/side. IBIAS only biases the error amp.
Layout: 203.45 x 510.88 um = 103 939 um2 (r4 203.40 x 423.59 = 86 158; +17 781 um2).  Magic DRC 0; publish_checked main 0 / antenna 0;
GDS read back (sha be4dd97c...): Magic DRC 0, netgen unique, no property errors.  LVS negative controls (stage/ctle/gen/ctle-lvs-negative-control.json):
L of the na diode, W of the tail-bias nfet, W of all tails -> property errors, detected.  NOT detected: W 20 -> 20.5 um on ONE of 21 parallel
tail instances (netgen merges parallel devices) - limitation of the check.
Flow defect found: wrx_flow isolated-well primitive shorts VDD_WIRE_SW to VSS with 1 or 2 fingers (bis/ test cells), clean with >= 3.
R+C (G7): extresist tolerance 0 / simplify off, built with r11 mkrc.py (C-only caps verbatim). 3487 R on 90 nets. Coverage 88 / 112 nets with a
device terminal (24 without = poly-to-poly series links of the divider and Rs ladder incl. vgr/vref: single-tile nets). Per-net C R+C / C-only
= 1.0000 (max dev 1e-6). Known answer R x1e-3: within 0.027 dB of C-only (tt, codes 0/7). Negative control R x10: 18.8 dB. PASS.
Wire-R audit (wire only, terminal stubs zeroed; max / mean over terminals): sp 26.2 / 9.1, src 21.0 / 8.5, cp/cn 21.6 / 8.0, CTLE_P 10.2 / 4.5,
CTLE_N 11.2 / 4.9, VDD 35.6 / 8.3, VSS 32.7 / 9.7, RX_P 30.2 / 27.2 ohm.  DC-path <= 5 ohm: FAIL (means improved vs r4 12.6 / 9.8; maxima not).
R+C vs C-only at tt: -0.72 dB at 1.25 GHz, static SL offset 11.3 mV (r4 R+C: 5-7 mV) - worse.
G8 loop (R+C, injection at the tail-bias nfet gate): DC loop gain 16-22 dB, unity 9.9-21 MHz, phase margin 69.9-87.7 deg, gain margin
16-25 dB (tt@t, ss315@s, ff@f, sf@s, fs@f, ssp315@f, ss350@f): PASS.  Enable / power-up transient NOT run.
G5 EM (op at ss350@f, highest current): load-strip terminals carry 0.57 mA actual (0.74 mA with x1.3) vs 0.58 mA/cut: FAIL by the x1.3 rule
(at res_ff the tail current is ~25 % above the design value the flow sized for). One VSS element 0.574 ohm carries 7.45 mA (0.95 mA/cut if it is
a single via layer; geometry not resolved). Via-current check from the R+C netlist is a heuristic (same-location resistors), not a layer-resolved audit.

Gate table (R+C, chain PDA eye T3 best code, eye mVppd / width UI; code-0 gain at 1.25 GHz; SL CM; CTLE supply mA): see table in res/rc/ (ac.json, pick.json)
| combo | g1.25G c0 dB | SL CM V | SL offset mV | I mA | 2.5 Gb/s | 3.125 Gb/s | 3.24 Gb/s |
|---|---|---|---|---|---|---|---|
| tt@t | 0.71 | 0.507 | 11.3 | 11.36 | 131.9 / 0.625 | 114.9 / 0.500 | 108.7 / 0.438 |
| tt@s | 0.60 | 0.530 | 9.9 | 9.37 | 137.8 / 0.562 | 105.8 / 0.438 | 96.6 / 0.438 |
| tt@f | -0.06 | 0.473 | 13.1 | 14.38 | 115.8 / 0.625 | 111.6 / 0.500 | 108.3 / 0.438 |
| ss315@t | -0.49 | 0.465 | 11.9 | 12.44 | 124.7 / 0.562 | 97.8 / 0.438 | 91.2 / 0.438 |
| ss315@s | -0.24 | 0.492 | 10.5 | 10.23 | 130.7 / 0.562 | 90.9 / 0.438 | 82.7 / 0.375 |
| ss315@f | -1.05 | 0.416 | 13.4 | 15.73 | 112.3 / 0.562 | 99.8 / 0.438 | 95.2 / 0.438 |
| ss350@t | -0.57 | 0.522 | 12.3 | 12.87 | 122.5 / 0.562 | 98.4 / 0.438 | 92.0 / 0.438 |
| ss350@s | -0.28 | 0.548 | 10.8 | 10.58 | 131.6 / 0.562 | 92.5 / 0.438 | 84.2 / 0.375 |
| ss350@f | -1.53 | 0.481 | 14.0 | 16.33 | 105.0 / 0.562 | 95.4 / 0.438 | 91.0 / 0.375 |
| ff@t | 1.67 | 0.529 | 10.5 | 10.24 | 137.0 / 0.688 | 126.7 / 0.562 | 121.9 / 0.500 |
| ff@s | 1.52 | 0.548 | 9.2 | 8.46 | 142.4 / 0.625 | 122.6 / 0.500 | 113.8 / 0.500 |
| ff@f | 0.93 | 0.500 | 12.2 | 12.95 | 121.8 / 0.688 | 120.6 / 0.562 | 118.9 / 0.500 |
| sf@t | -1.31 | 0.475 | 11.4 | 12.06 | 111.3 / 0.625 | 94.3 / 0.438 | 88.2 / 0.438 |
| sf@s | -0.62 | 0.499 | 10.1 | 9.93 | 123.9 / 0.562 | 93.3 / 0.438 | 86.4 / 0.438 |
| sf@f | -2.40 | 0.439 | 12.7 | 15.28 | 95.2 / 0.562 | 87.7 / 0.438 | 84.4 / 0.438 |
| fs@t | 0.76 | 0.489 | 10.3 | 10.47 | 132.0 / 0.625 | 115.7 / 0.500 | 108.9 / 0.438 |
| fs@s | 0.91 | 0.512 | 9.0 | 8.64 | 140.2 / 0.625 | 107.9 / 0.500 | 98.2 / 0.438 |
| fs@f | 0.14 | 0.456 | 11.9 | 13.24 | 117.2 / 0.625 | 112.0 / 0.500 | 108.7 / 0.500 |
| ssp315@t | -2.83 | 0.465 | 11.9 | 12.44 | 100.8 / 0.500 | 59.0 / 0.000 FAIL | 52.7 / 0.000 FAIL |
| ssp315@s | -2.88 | 0.492 | 10.5 | 10.23 | 94.2 / 0.438 | 47.4 / 0.000 FAIL | 40.7 / 0.000 FAIL |
| ssp315@f | -3.00 | 0.416 | 13.4 | 15.73 | 101.5 / 0.500 | 68.5 / 0.312 | 62.9 / 0.188 FAIL |
G2 SL CM 0.416-0.548 V: PASS.  G3 code-0 gain spread 4.67 dB (-3.00 ssp315@f ... +1.67 ff@t; 4.07 dB without ssp): FAIL.  G1: FAIL at ssp315
3.125 / 3.24 Gb/s (40.7-68.5 mV); every other cell passes.  G4 current 8.5-16.3 mA (r4 at ideal 10 uA: 11.9-12.1); res_ff corners exceed the
12.5 mA budget.
G1 confirmation (clocked transient, ideal clocks, R+C, worst 2.5 Gb/s cell ssp315@s, T3, code 0): eye 76.5 mVppd / 0.35 UI but 1 bit error / 112
-> FAIL (PDA said 94.2 mV: transient 18 mV lower, slicer kickback). Negative control (3 pF per SL leg): 13.9 mV, 27 errors -> fails as required.
3.125 / 3.24 Gb/s worst cells already fail on PDA; no transient run.  sf / fs aperture records do not exist (only ssp needed here); aperture
of the MOS corner reused for every poly corner (slicer property).
NOT run: enable / power-up transient of the loop; IBIAS 7.5 / 12 uA; ssp350; R+C high/low metal styles; direct/bypass modes with R+C;
hot-carrier / reliability at 3.5 V.  No independent review.

## Open / next levers (owner decides)
1. ssp 3.125/3.24 eye (41-69 mV) and gain spread: bandwidth at cp/SL under pessimistic C; R+C costs 0.7 dB; r5 sinks 3x wider add SL C.
2. EM: 12 load strips of 1 x 7.2 um (half the current per terminal) and resolve the VSS 7.45 mA group; size currents for res_ff (+25 %).
3. DC-path wire R: needs wrx_flow width options (outside this sub-agent's edit scope).
4. Static SL offset 11 mV (R+C): P/N supply-return asymmetry; within sampler trim but larger than r4.
5. Supply current at res_ff 14-16 mA: lower vref (0.14 VDD) would trade SL CM margin for current.
