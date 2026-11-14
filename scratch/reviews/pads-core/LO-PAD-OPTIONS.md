# External-LO pad options against the RX LO-leak limit (INT23-1)

2026-11-14, pads owner sub-task. Facts and model numbers only; which signal gives way is not decided here.
Nothing in the project tree was changed. Script: `scratch/pads-core/bond/lo_pad_options.py` (python only, about 1 min),
numbers in `lo-pad-options.json`. Triples are optimistic / nominal / pessimistic bound of the M2/M3 model.

## 1. The model that produced "-16 dB", and the reproduced known answer

- Mutual inductance: `scratch/integration/m23-substrate-pulling/m3/mutual.py`, function `M_pair_pair(dy_die, image, ...)`
  (two `bond_loop()` filament loops, Neumann double integral `neumann()`, minus the image in the paddle via `mirror()`).
  Each pair is a closed loop: die-edge segment, wire N, finger-to-finger closure, wire P; 2.6 mm long, fingers 0.4 mm pitch,
  second pair's fingers fanned by `FAN = 1.55`. Bounds: pad pitch 120 / 150 / 300 um, loop height 0.15 / 0.25 / 0.35 mm,
  image yes / yes / **no**.
- Budget: `m3/pulling.py`, block "LO -> LNA leakage": `I_LOPAD` = 1 V pk per leg x w x (1.0 / 1.5 / 2.0 pF) =
  15.4 / 23.1 / 30.8 mA pk at 2.45 GHz (1 V pk per leg = 4 Vpp differential); EMF e = w M I; `dbm_from_emf` = available
  power of e behind 50 ohm. Limit: RF-RX-LOLEAK -57 dBm. PA -> LO: block "PA pair -> external-LO pair", EMF from
  `I_PA` 4 / 12 / 35 mA against a 2 V pk LO, 8 dB back-off, limit -35 dB EVM share.
- The published row used the grid point **dy = 900 um** (the 0.89 mm is the distance between the `pad_ref` and
  `pad_rf_rx` cell centres in `floorplan-v6.json`): M = 10 / 16.3 / 36.5 pH, so -48.5 / -40.8 / -31.3 dBm,
  margin -8.5 / **-16.2** / -25.7 dB.
- **Reuse:** `mutual.py` is imported unchanged. The five budget lines of `pulling.py` are copied verbatim (importing it
  would rerun it and rewrite `pulling.json`).
- **Reproduced:** 900 um: margin -8.5 / -16.2 / -25.7 dB (published -8.5 / -16 / -26). 1700 um: +12.1 / +3.3 / -11.4
  (published +12 / +3 / -11). PA -> LO at 1200 um: +55.2 / +40.9 / +22.5 (published +55 / +41 / +22). Within 0.3 dB.
- The bond openings are on a uniform 211 um pitch, so the wire-to-wire centre distances are 844 um (REF_IN to RF_RX) and
  1688 um (AUX_CLK to RF_RX), not 890 / 1740. All tables below use the opening centres. Today's map at 844 um:
  **-10.4 / -18.0 / -27.1 dB** (1.8 dB worse than published at nominal).
- Sensitivity only (not the published model): with the as-built pad pitch 211 um and fan 400/211 the 844 um case gives
  -11.3 / -17.4 / -21.8 dB. With 2.0 mm wires (near-end landing) instead of 2.6 mm: 2.3 to 2.8 dB better.

Limits of the model, all inherited: filaments with an assumed loop shape, no EM, no measured bond profile; magnetic
coupling only (**no capacitive term**, no finger/trace/connector coupling on the board); pairs between aggressor and
victim are not in it (neither as shields nor as relays); supply/ground bonds are not in it; the LNA source down-bond
loop is not in it; LO current is pad-capacitance current only. The pessimistic bound has no ground image.

## 2. West-edge slots (site properties; they do not change when signals move)

Slot = one 2-site pad cell position. P sits on the higher `inputs[]` index in every slot. Lengths/angles from
`bond-audit.json` (C = finger-centre landing, N = near end; limits < 3 mm, <= 45 deg, >= 1 mm, no crossing). Trace lengths
and contacts from the `pins` table of `spec/package-channel.json` keyed by bond pad (F.Cu + B.Cu), skew at 5.93 ps/mm as
in that file. 1 ps = 0.88 deg at 2.45 GHz.

| Slot | Bonds P/N | Sites | Today | Contacts P/N | L C (mm) | Angle C | L N (mm) | Angle N | Trace P/N (mm) | Board skew P-N |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 56/55 | inputs[1]/[0] | RF_TX | 26/27 | 2.881/2.991 | 33.9/36.9 | 2.543/2.665 | 38.4/41.6 | 5.68/5.39 | +1.7 ps |
| B | 60/59 | inputs[3]/[2] | BB_Q | 22/23 | 2.539/2.608 | 19.6/23.5 | 2.156/2.236 | 22.5/27.0 | 3.12/3.06 | +0.4 ps |
| C | 62/61 | inputs[5]/[4] | AUX_CLK | 20/21 | 2.438/2.482 | 11.2/15.5 | 2.042/2.091 | 12.7/17.7 | 5.22/5.46 | -1.4 ps |
| D | 66/65 | inputs[7]/[6] | REF_IN | 16/17 | 2.409/2.394 | 6.8/2.3 | 2.009/1.993 | 7.4/2.0 | 3.18/5.66 | **-14.7 ps (13 deg)** |
| E | 68/67 | inputs[9]/[8] | BB_I | 14/15 | 2.482/2.438 | 15.5/11.2 | 2.091/2.042 | 17.7/12.7 | 3.37/5.09 | -10.2 ps |
| F | 70/69 | inputs[11]/[10] | RF_RX | 12/13 | 2.608/2.539 | 23.5/19.6 | 2.236/2.156 | 27.0/22.5 | 4.97/6.01 | -6.2 ps |
| East | 22/23 | bidir[16]/[17] | free | 58/57 | 2.608/2.539 | 23.5/19.6 | 2.236/2.156 | 27.0/22.5 | 3.12/5.21 | -12.4 ps (11 deg) |

- Between A and B: GND bond 57, VDD_IO_2 bond 58. Between C and D: GND bond 63, PWR_AUX_1 bond 64. Below F: GND bond 71.
  B-C, D-E and E-F are directly adjacent (422 um centre to centre).
- **Every option below only renames wires that exist today, so every bond stays legal** with the audit's margins (worst
  moved wire: slot A, 2.991 mm, 9 um of margin, as today for RF_TX). W-A / W-B are not used by any option.
- Cell outlines (`floorplan-v6.json`): the refpad cell is 401 um tall against 310 um for rf-pair and reaches 94 um further
  north. Checked for slots B to E: 18 um to the next cell, as today. At slot A it would end at chip y 4721; clearance to
  the north-west corner was not checked.
- `lo_ext` and the QVCO are unplaced in v6 (in the `failures` list), so routes are given to the mixers. Manhattan length
  from the pad cell's inner edge to the RX mixer midpoint / TX mixer midpoint / `pll_cdr` centre (wire-clock consumer):
  A 3.0 / 1.9 / 4.6 mm, B 2.2 / 1.1 / 3.8, C 1.8 / 0.7 / 3.4, D 0.9 / 0.6 / 2.5, E 0.5 / 1.0 / 2.1, F 0.4 / 1.4 / 1.7,
  East 2.0 / 3.1 / 0.45.

## 3. Coupling against distance (one LO pair, model unchanged)

| Centre distance (um) | M (pH) | Leak at RF_RX, 4 Vpp (dBm) | Margin to -57 dBm | Margin at 1 Vpp | Self-mixing DC (mV, trim +-250) | PA -> LO margin to -35 dB (LO 4 Vpp) | same, LO 1 Vpp | EMF on a neighbour pair at this distance (mV pk) |
|---|---|---|---|---|---|---|---|---|
| 422 | 108 / 143 / 262 | -27.9 / -21.9 / -14.1 | -29 / -35 / -43 | -17 / -23 / -31 | 167 / 331 / 808 | +25.6 / +13.6 / **-1.0** | +13.5 / +1.6 / -13.0 | 25.6 / 50.8 / 124 |
| 844 | 12.4 / 20.0 / 42.9 | -46.6 / -39.0 / -29.9 | -10.4 / -18.0 / -27.1 | +1.7 / -6.0 / -15.1 | 19 / 46 / 132 | +44.3 / +30.7 / +14.8 | +32.3 / +18.7 / +2.7 | 2.9 / 7.1 / 20.3 |
| 1266 | 2.9 / 5.1 / 15.3 | -59.2 / -50.8 / -38.8 | +2.2 / -6.2 / -18.2 | +14.3 / +5.9 / -6.1 | 4.5 / 12 / 47 | +57.0 / +42.5 / +23.7 | +44.9 / +30.5 / +11.7 | 0.7 / 1.8 / 7.2 |
| 1688 | 0.96 / 1.76 / 7.2 | -68.9 / -60.1 / -45.4 | +11.9 / +3.1 / -11.6 | +23.9 / +15.1 / +0.4 | 1.5 / 4.1 / 22 | +66.6 / +51.8 / +30.3 | +54.5 / +39.7 / +18.3 | |
| 2110 | 0.40 / 0.73 / 3.9 | -76.6 / -67.7 / -50.7 | +19.6 / +10.7 / -6.3 | +31.6 / +22.8 / +5.7 | 0.6 / 1.7 / 12 | +74.3 / +59.4 / +35.6 | +62.3 / +47.4 / +23.5 | |
| 2532 | 0.19 / 0.35 / 2.4 | -83.0 / -74.2 / -55.1 | +26.0 / +17.2 / -1.9 | +38.0 / +29.2 / +10.1 | 0.3 / 0.8 / 7 | +80.7 / +65.9 / +40.0 | | |
| 2954 | 0.10 / 0.18 / 1.5 | -88.5 / -79.7 / -58.9 | +31.5 / +22.7 / +1.9 | +43.5 / +34.8 / +13.9 | 0.2 / 0.4 / 5 | +86.2 / +71.4 / +43.7 | | |
| East 22/23, opposite RF_RX (extension, see 4d) | 0.02 / 0.03 / 0.34 | -102 / -97 / -72 | +45 / +40 / +15 | | | | | |

A single pair passes at nominal from 1688 um and passes at the pessimistic bound only at 2954 um (the far end of the edge).
The PA -> LO margin loses 12 dB when the LO is lowered from 4 Vpp to 1 Vpp (the phase error is EMF / LO amplitude).

## 4. Options

Order is written north to south, slots A B C D E F. "I+Q" is the power sum of both LO legs into RF_RX (they are in
quadrature, so the sign of either does not matter). Pass/fail is against -57 dBm at 4 Vpp.

| Option | A B C D E F | REF_IN / AUX_CLK to RF_RX (um) | I leg margin (dB) | Q leg margin (dB) | I+Q margin (dB) | Verdict at 4 Vpp | Largest drive that passes (Vpp diff) | RF_TX to REF / AUX (um) | PA -> LO margin, I ; Q (dB) | LO pair to nearest BB pair (um): EMF there (mV pk) |
|---|---|---|---|---|---|---|---|---|---|---|
| **a** today | TX BBQ AUX REF BBI RX | 844 / 1688 | -10.4 / -18.0 / -27.1 | +11.9 / +3.1 / -11.6 | -10.4 / -18.0 / -27.3 | **fail / fail / fail** | 1.21 / 0.50 / 0.17 | 2110 / 1266 | +74 / +59 / +36 ; +57 / +42.5 / +24 | 422: 26 / 51 / 124 (both legs) |
| **b** REF_IN <-> BB_Q | TX REF AUX BBQ BBI RX | 2110 / 1688 | +19.6 / +10.7 / -6.3 | +11.9 / +3.1 / -11.6 | **+11.2 / +2.4 / -12.7** | pass / pass / fail | 4 / 4 / 0.92 | 844 / 1266 | +44 / +31 / +15 ; +57 / +42.5 / +24 | REF 1266: 0.7 / 1.8 / 7 ; AUX 844: 3 / 7 / 20 |
| **c** both LO pairs next to RF_TX, BB_I/BB_Q between | = b (AUX_CLK is already in slot C), or c2: TX AUX REF BBQ BBI RX | c2: 1688 / 2110 | +11.9 / +3.1 / -11.6 | +19.6 / +10.7 / -6.3 | +11.2 / +2.4 / -12.7 | pass / pass / fail | 4 / 4 / 0.92 | 1266 / 844 | +57 / +42.5 / +24 ; +44 / +31 / +15 | REF 844 ; AUX 1266 |
| **d1** AUX_CLK east, REF_IN at B, C empty | TX REF - BBQ BBI RX | 2110 / east | +19.6 / +10.7 / -6.3 | +45 / +40 / +15 | **+19.6 / +10.7 / -6.4** | pass / pass / fail | 4 / 4 / 1.92 | 844 / - | +44 / +31 / +15 | 1266: 0.7 / 1.8 / 7 |
| **d2** AUX_CLK east, REF_IN at C | TX BBQ REF - BBI RX | 1688 / east | +11.9 / +3.1 / -11.6 | +45 / +40 / +15 | +11.8 / +3.1 / -11.6 | pass / pass / fail | 4 / 4 / 1.05 | 1266 / - | +57 / +42.5 / +24 | 422: 26 / 51 / 124 |
| **d3** AUX_CLK east, REF_IN stays | TX BBQ - REF BBI RX | 844 / east | -10.4 / -18.0 / -27.1 | +45 / +40 / +15 | -10.4 / -18.0 / -27.1 | fail / fail / fail | 1.21 / 0.50 / 0.18 | 2110 / - | +74 / +59 / +36 | 422 |
| **e1** best with RF_RX and RF_TX fixed (24 orders) | = b / c2 (BB_I and BB_Q in either order) | | | | +11.2 / +2.4 / -12.7 | pass / pass / fail | | | | |
| **e2** best with RF_RX fixed at F, RF_TX free | REF AUX BB TX BB RX (or AUX REF ...) | 2954 / 2110 | +31.5 / +22.7 / +1.9 | +19.6 / +10.7 / -6.3 | +19.3 / +10.5 / -6.9 | pass / pass / fail | 4 / 4 / 1.80 | 2110 / 1266 | +74 / +59 / +36 ; +57 / +42.5 / +24 | 422 on one leg |
| **e3** best of all 720 | RX BB TX BB REF AUX (and 7 equivalents, e.g. RX TX BB BB REF AUX) | 2532 / 2954 | +26.0 / +17.2 / -1.9 | +31.5 / +22.7 / +1.9 | **+24.9 / +16.1 / -3.4** | pass / pass / fail | 4 / 4 / 2.69 | 1266 / 1688 | +57 / +42.5 / +24 ; +67 / +52 / +30 | 422 on one leg |

Search (e): all 720 pair orders, model unchanged. Constraints used: PA -> LO passes at the pessimistic bound for both
legs, and a strip of at least 630 um along the edge stays >= 1.0 mm from both the RF_TX and the RF_RX pair centres for
the QVCO spirals (INT23-2; the QVCO is unplaced, so the "region" is taken as that strip inside the core, 315 um spiral
half-width). 252 orders meet both. **No order of the 720 passes the pessimistic bound at 4 Vpp for I+Q** (216 pass the
optimistic bound, 96 the nominal). The model has no term for supply/ground bonds next to RF_RX or RF_TX, so it does not
say they matter; e1 keeps them anyway.

What each option changes:

- **a.** Nothing. QVCO strip: chip y 2506 to 3460.
- **b / c.** REF_IN moves to bonds 60/59 (contacts 22/23, nets `/pad_59`, `/pad_58`), BB_Q to bonds 66/65 (contacts 16/17).
  REF_IN bond 2.539 / 2.608 mm, 19.6 / 23.5 deg (was 2.409 / 2.394 mm). REF_IN board skew goes from -14.7 ps to +0.4 ps;
  BB_Q inherits the -14.7 ps. c2 puts AUX_CLK on 60/59 (+0.4 ps) and REF_IN on 62/61 (-1.4 ps, contacts 20/21).
  On-die I route to the RX mixers 0.9 -> 2.2 mm (b) or 1.8 mm (c2); to the TX mixers 0.6 -> 1.1 / 0.7 mm. The LO does not
  cross the die. RF_TX to the nearer LO pair drops from 1266 to 844 um (GND 57 and VDD_IO_2 58 lie between): PA -> LO
  still +15 dB at the pessimistic bound with a 4 Vpp LO, +2.7 dB with a 1 Vpp LO. RF_TX and QVCO strip unchanged.
  **The two LO pairs become direct neighbours (422 um, nothing between; today 844 um with bonds 63/64 between):** by
  the same EMF formula each leg induces 26 / 51 / 124 mV pk in the other against 2 V pk, i.e. 0.7 / 1.5 / 3.6 deg per leg,
  up to twice that as quadrature error (today 0.08 / 0.2 / 0.6 deg per leg). Static; not checked against the IQ trim.
  BB_Q and BB_I sit between LO and RF_RX; the BB pair next to RF_RX is then 844 um or more from an LO pair.
- **d.** AUX_CLK on bonds 22/23 (contacts 58/57, nets `/pad_21`, `/pad_22`; 2.608 / 2.539 mm, 23.5 / 19.6 deg, legal today as
  WCLK_IN). Board skew -12.4 ps (11 deg at 2.45 GHz) against -1.4 ps today. The pad is 3.8 mm from RF_RX on the
  opposite edge. The Q LO then has 2.0 mm (RX mixers) / 3.1 mm (TX mixers) of on-die route **across the die**, past
  `pll_cdr`, `isw_wired`, `lo_pfdcp` and beside `adc_q`, while the I leg has 0.4 to 2.2 mm from the west edge
  (integration-m23 section 7.1 rejects carrying the 2.4 GHz LO about 3 mm across the die). The forwarded wire clock
  gets shorter: 0.45 mm to `pll_cdr` against 3.4 mm from slot C. Uses both free east sites (the candidates for the POR
  strap / spare in `SITES.md`) and frees a west slot with fingers and contacts (C: bonds 62/61, contacts 20/21, or
  D: 16/17). Needs an east-edge (R90) placement of the AUX_CLK pad cell; `pad_wclk_in` (rf-pair) was the cell there.
  The east number is my extension of the model (same primitives, loop mirrored to the east edge, directly opposite), not
  a published case. d1 fixes the leak only if REF_IN also moves (d3 does nothing for the I leg).
- **e2.** RF_TX moves to slot D (bonds 66/65, contacts 16/17, 844 um from RF_RX), LO pairs to A and B. QVCO strip
  moves to chip y 3350 to 4355, which at x >= 1.7 mm is inside the digital macro outline of v6. `rfdriver`, `txsum`,
  TX mixers and the refpad cell at slot A (corner clearance unchecked) are floorplan work.
- **e3.** RF_RX moves to the north end (slot A, away from the LNA, GND bond 71 and the W-A / W-B placeholders), LO pairs
  to the south end, RF_TX to B or C (844 to 1266 um from RF_RX). QVCO strip chip y 767 to 2194 (or to 2616). This is a
  mirror of the whole RF floorplan.

Other paths asked for:

- **AUX_CLK as forwarded wire clock -> RF_RX:** the LNA is off in wired modes (no demand, integration-m23 7.1). For scale,
  1 V pk per leg at 810 MHz gives 19 dB less than the 2.45 GHz figures: -88 / -79 / -65 dBm at 1688 um (slot C),
  -96 / -87 / -70 dBm at 2110 um (slot B), below -120 dBm from the east sites.
- **LO -> BB pairs (debug baseband):** a 2.45 GHz EMF of 26 / 51 / 124 mV pk on a directly adjacent BB pair (today both
  BB pairs are adjacent to an LO pair), 3 / 7 / 20 mV at 844 um, 0.7 / 1.8 / 7 mV at 1266 um. It is far outside the
  baseband band and the model has no limit for it. Not modelled: rectification in the `bb_tap` output stage, and the BB
  pair acting as a relay toward RF_RX. Hand estimate of the relay for today's map (BB_I loop impedance >= 100 ohm
  assumed): about 14 dB below the direct REF_IN path; for b/c about 29 dB below the direct path.
- **RF_TX -> LO pair:** passes in every option above (table). It fails the pessimistic bound only if RF_TX is directly
  adjacent (422 um) to an LO pair, which the search excluded.

## 5. Bonding-level alternatives to moving pads (what the model credits)

| Mitigation | Credit in the model | Numbers |
|---|---|---|
| Distance | yes | Section 3. About 21 dB from 844 to 1688 um, 7.6 dB more to 2110 um (nominal). |
| Ground bond between the pairs | **none** (grounds are not in the model; integration-m23 states that the BB_I pair between is not a shield) | My extension, best case (one wire shorted to the plane at both ends, 2.2 nH): 6 to 8 dB for a wire midway at today's spacing (that site is BB_I; no free site there), 3 to 10 dB from the existing GND bond 63 for an LO pair at slot C, 2 to 3 dB at slot B. Not a published figure; a real ground bond returns through the die ground and is worth less. |
| Reversing P/N of one pair | **none** | Changes the sign of M only; the magnitude is the same. I and Q are in quadrature, so their contributions add in power for any sign. The model has no common-mode term. |
| Lower LO drive | yes, 20 log(V / 4 Vpp) | 1 Vpp: +12 dB. Today: -6 dB at nominal at 1 Vpp (844 um; published -4), passes below 0.50 / 0.17 Vpp (nominal / pessimistic). With b/c: passes at 4 Vpp nominal, needs <= 0.92 Vpp at the pessimistic bound. With d1: <= 1.9 Vpp. The window qualified today is 1.0 to 4.5 Vpp. Cost: PA -> LO margin falls by the same 12 dB. |
| Smaller LO pad capacitance | yes, linear in C | 1.0 / 1.5 / 2.0 pF is the bound spread: 3.5 dB from 1.5 to 1.0 pF. |
| Shorter / lower wires | yes | 2.0 mm instead of 2.6 mm: 2.3 to 2.8 dB. Loop height is part of the bounds (0.15 to 0.35 mm). |
| On-chip LO from the QVCO instead of external | yes (different path) | integration-m23 8.1: -74 / -73 / -67 dBm at RF_RX, margin +17 / +16 / +10 dB with the QVCO 1.3 mm from the west edge; +26 / +25 / +15 dB at 1.7 mm. No LO current in any bond. |
| Grounded paddle image | yes (the pessimistic bound drops it, together with a wider pad pitch and a higher loop) | At 1688 um: 1.76 pH nominal with the image, 7.2 pH pessimistic without. See the question added to `wafer-space-questions.md`. |

## 6. Not determined

- Capacitive and board-level coupling (fingers are 0.4 mm pitch, 1.0 mm long; traces; the mezzanine connector) are not
  in the model. `spec/package-channel.json` has adjacent-pin crosstalk only and its west order is stale
  (`package-channel-west-fix.md`).
- Bond loop shape, die thickness and attach are unpublished; the pessimistic bound stands until the paddle is known to be
  an effective image plane.
- `lo_ext` and the QVCO are unplaced in v6; route lengths are to the mixers.
- Whether the refpad cell fits slot A, and an east-edge variant of the AUX_CLK pad cell.
- The east-site and ground-wire numbers are extensions built from the model's primitives and have no published check.
