# Independent check: bond pad -> primary ESD diode resistance (pads, all custom families)

Checker run of 2026-11-18. Everything here is in `scratch/pads-core/esdcheck/`. Project and `hsfix*/` were only read.
Claim under test (from `hsfix/netres.py` only): "20-25 ohm typ of metal/via between bond pad and primary ESD diodes, through single cuts, in every custom pad family".

## Resistances used (read by me from the PDK in the container)
`/foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.tech`, extract section, style ngspice:
| | typ `variants ()` | high `(hrhc),(hrlc)` | low |
|---|---|---|---|
| Metal1-4 sheet | 90 mohm/sq | 104 | 76 |
| Metal5 sheet | 40 mohm/sq | 49 | 31 |
| via1 (m2c), via2 (m3c), via3, via4 per cut | 4.5 ohm | 15 ohm | 0 |
| n-diff / p-diff contact per cut | 6.3 / 5.2 ohm | 15 | 0 |
Cross-check: `libs.tech/ngspice/sm141064.ngspice` has `rsh_rm1..3 = 0.09` (+-0.012 corners), `rsh_tm9k = rsh_tm11k = 40e-3` (+-9e-3): metal sheets agree with Magic typ / high.
No design manual (pdf / rst) is in the PDK tree of the container (`find /foss/pdks -iname '*.pdf'` finds only IHP documents), and the ngspice models have no via model, so the
via values 4.5 / 15 ohm per cut are from the Magic tech file only. NOT cross-checked against the GF design manual.

## Verdict in one paragraph
The resistance is real. Three methods that share no code with `netres.py` (hand sum over the drawn segments, Magic `extresist`, and a 2D sheet/via solve I wrote from scratch) agree with each other
within 1.2 % on all 13 pad legs and with netres within 0.5 % wherever netres had a comparable number. Family by family the claim "20-25 ohm typ" is CONFIRMED for `pad_refpad`, `pad_wirepad`
and `pad_txpad` (22.9-27.5 ohm typ, 38-50 ohm high), is TOO LOW for `pad_hspad` (27.7-31.7 typ, 70-81 high: the netres figure 25.4 / 65.2 shorted the VSS diodes and the rail diodes together,
which no ESD polarity does) and for `pad_rf_pair`, `pad_rftxpad`, `pad_single_leg` (28.3-30.8 typ, 77-80 high; netres never surveyed them), and is REFUTED for `pad_tlp_flat` (0.44 typ / 0.73 high).
"Through single-cut vias" is only partly right: in refpad / wirepad / txpad one single Via2 carries 100 % and each diode has one Via1, together 5.9 of 25 ohm typ; the rest is long narrow metal
(4 um Metal2 riser 7.4 ohm, 8 um Metal4 2.8-6.3 ohm, 0.48 um Metal2 diode bar about 3 ohm). In hspad and the three RF cells four single cuts in series each carry 100 % (Via4, Via4, Via3, Via2)
plus the Via1 per diode: 19.4 of 28.7 ohm typ, 63.9 of 77 ohm high.
The return sides, which netres never looked at, add as much again (rail diodes -> clamp 12-20 ohm typ; VSS diode rings -> ring DVSS 27-50 ohm typ and clamp sources -> ring 19-39 ohm typ, through two 2 x 2 um stacks, 2 um Metal2 and single cuts).
At 1.33 A and at 0.67 A every family except the TLP site is far over 8.0 V from the pad-side term alone.

## Published GDS analysed (sha256, first 12)
```
ae89311095ff stress-safe-families/reference/combined.gds
4e4b9d9285f5 stress-safe-families/wired-receive-usb/combined.gds
ae75af97dc76 stress-safe-families/wired-transmit/combined.gds
5b7c598e6c32 stress-safe-families/wired-receive-hs/pad_hspad.gds
9c37d9b8fdd6 stress-safe-families/rf-pair/pad.gds
098f17ff11ed stress-safe-families/rf-tx/pad.gds
3431a26e82dd stress-safe-families/single-leg/pad.gds
7c718d9aa1dc tlp-site/pad_tlp_flat.gds
```
Protection network embedded: refpad, txpad, rf_pair, rftxpad, single_leg have 4 nd2ps + 4 pd2nw per pad (the `network-gc` macro per README section 3); hspad and wirepad have 4 + 8 (`network-gc-d2`).
All seven have the same 18 clamp MOS diffusion islands between ESD_RAIL and VSS (14 of 19.88 x 53.6 um, 4 of 50 x 24.76 um). I analysed the copies embedded in the family GDS; I did not
byte-compare them with `network-gc/network.gds` or run the standalone network cells. `pad_tlp_flat` has no network: 4 + 4 diodes straight on a Metal2 riser, to VSS and VDD bars.

## Methods
- **Net tracing** (`trace.py`, mine): KLayout regions, Metal1..5 and Via1..4, flood from the pin label. Via4 cuts that land on a MIM top plate (75/0) are excluded (my first version shorted
  ESD_RAIL to VSS through the coupling MIMs; found because the two labels gave the same net, fixed, hspad pad nets rerun). Check on the trace: every pad net carries exactly the diode contacts
  the netlists say (4 x 106 nd, 4 or 8 x 106 pd) and the same Via1 count netres reports (9 on refpad).
- **M1, hand** (`handcalc.py`, segment table in `handcalc_segments.txt`): I read every segment of the path off the listings (`dnet.py`, `path.py`, `clipshow.py`), wrote length / width
  squares and cut counts into a table and summed series / parallel. No field solve. The four diodes of a row hang on a 0.48 um Metal2 bar, so that part is a ladder.
  Single-via crowding in the 12 um bars is not in the hand sum. rftxpad and single_leg reuse the rf_pair segment list (their traced nets have identical areas, boxes and cut counts).
- **M2a, Magic `extresist`** (`mkext.py`, `ext.tcl`, `mext.sh`, `rsolve.py`; Magic 8.3 in the container, `extract style ngspice()` and `ngspice(hrhc)`): run on the traced pad net (metal and
  vias only, pad plate clipped at depth 60) with port labels at the bond end and on each diode's Metal1 plate. Magic then resolves it (300-1500 resistors). Its `.res.ext` contains one copy
  of the network per port alias; I solve only the copy named after the net (solving the whole file would put the copies in parallel and halve the answer; the control below shows that pitfall).
  The node-to-node arithmetic on Magic's resistor list is a plain nodal solve.
  On the real cell with the diode devices Magic does not resolve the pad net (`ext_real.tcl` on `pad_tlp_flat`: "Nets output: 1", only VSS is written, PAD stays lumped), which is what the
  previous designer saw. That run does confirm Magic's own connectivity: PAD joins exactly D0-D3 cathodes and D4-D7 anodes.
- **M2b, own 2D solve** (`solve.py`, written without reading `netres.py`): exact tensor grid on all polygon coordinates, <= 0.5 um step, one resistor of R_cut per drawn cut, terminals contracted
  to one node. Gives the split by layer and the current in every via group. For the big return nets: 1 um step and each cut lumped at its centre (`--lumpvia`; on the refpad pad net this changes 24.96 to 24.97).
- Terminals: bond end = the pad plate edge (depth 60-65.3, all four metals); diode end = all contacts of the four (or eight) diodes of one polarity shorted. Contact resistance (6.3 / 5.2 ohm
  per cut, 106 cuts per diode: 0.06 ohm) and the diode's own resistance are not included. With the contacts shorted the Metal1 plate drops out; a uniform current along the 25 um plate adds about
  0.06 ohm (0.24 ohm per diode, hand estimate, in the hand column).

## Result 1: bond pad -> pad-side diode terminals (all diodes of one polarity in parallel), ohm typ / high
| cell, leg | diodes | M1 hand typ / high | M2a Magic extresist typ / high | M2b own 2D solve typ / high | netres typ / high |
|---|---|---|---|---|---|
| pad_refpad P | to VSS (nd2ps) | 25.0 / 46.8 | 24.87 / 46.73 | 24.96 / 46.87 | 25.00 / 46.91 |
| pad_refpad P | to rail (pd2nw) | 25.0 / 46.8 | 24.87 / 46.73 | 24.96 / 46.85 | 25.00 / 46.91 |
| pad_refpad N | to VSS (nd2ps) | 24.8 / 46.7 | 24.73 / 46.58 | 24.81 / 46.67 | 24.87 / 46.76 |
| pad_refpad N | to rail (pd2nw) | 26.6 / 48.8 | 26.53 / 48.66 | 26.61 / 48.75 | 26.66 / 48.84 |
| pad_wirepad P | to VSS (nd2ps) | 26.3 / 48.4 | 26.22 / 48.29 | 26.30 / 48.38 | 26.34 / 48.46 |
| pad_wirepad P | to rail (pd2nw) | 22.9 / 38.4 | 22.87 / 38.34 | 22.93 / 38.43 | 22.99 / 38.51 |
| pad_wirepad N | to VSS (nd2ps) | 26.2 / 48.2 | 26.08 / 48.14 | 26.17 / 48.21 | 26.22 / 48.32 |
| pad_wirepad N | to rail (pd2nw) | 23.9 / 39.5 | 23.88 / 39.42 | 23.95 / 39.48 | 24.01 / 39.59 |
| pad_txpad P | to VSS (nd2ps) | 25.9 / 47.9 | 25.77 / 47.77 | 25.85 / 47.87 | 25.91 / 47.96 |
| pad_txpad P | to rail (pd2nw) | 25.9 / 47.9 | 25.77 / 47.77 | 25.86 / 47.88 | 25.90 / 47.95 |
| pad_txpad N | to VSS (nd2ps) | 25.7 / 47.7 | 25.63 / 47.62 | 25.72 / 47.71 | 25.77 / 47.81 |
| pad_txpad N | to rail (pd2nw) | 27.5 / 49.8 | 27.43 / 49.7 | 27.52 / 49.81 | 27.56 / 49.87 |
| pad_hspad P | to VSS (nd2ps) | 31.0 / 80.0 | 31.09 / 79.92 | 31.27 / 80.27 | 25.39 / 65.23 (*) |
| pad_hspad P | to rail (pd2nw) | 27.7 / 70.0 | 27.74 / 69.97 | 27.91 / 70.04 | 25.39 / 65.23 (*) |
| pad_hspad N | to VSS (nd2ps) | 31.5 / 80.5 | 31.44 / 80.44 | 31.74 / 80.96 | 26.32 / 66.34 (*) |
| pad_hspad N | to rail (pd2nw) | 29.3 / 71.8 | 29.24 / 71.72 | 29.53 / 72.03 | 26.32 / 66.34 (*) |
| pad_rf_pair P | to VSS (nd2ps) | 28.4 / 76.9 | 28.33 / 76.85 | 28.65 / 77.24 | not surveyed |
| pad_rf_pair P | to rail (pd2nw) | 28.4 / 76.9 | 28.33 / 76.85 | 28.65 / 77.24 | not surveyed |
| pad_rf_pair N | to VSS (nd2ps) | 28.8 / 77.3 | 28.68 / 77.26 | 29.00 / 77.79 | not surveyed |
| pad_rf_pair N | to rail (pd2nw) | 30.6 / 79.4 | 30.48 / 79.34 | 30.80 / 79.88 | not surveyed |
| pad_rftxpad P | to VSS (nd2ps) | 28.4 / 76.9 | 28.33 / 76.85 | 28.65 / 77.24 | not surveyed |
| pad_rftxpad P | to rail (pd2nw) | 28.4 / 76.9 | 28.33 / 76.85 | 28.65 / 77.24 | not surveyed |
| pad_rftxpad N | to VSS (nd2ps) | 28.8 / 77.3 | 28.68 / 77.26 | 29.00 / 77.79 | not surveyed |
| pad_rftxpad N | to rail (pd2nw) | 30.6 / 79.4 | 30.48 / 79.34 | 30.80 / 79.88 | not surveyed |
| pad_single_leg P | to VSS (nd2ps) | 28.4 / 76.9 | 28.33 / 76.85 | 28.65 / 77.24 | not surveyed |
| pad_single_leg P | to rail (pd2nw) | 28.4 / 76.9 | 28.33 / 76.85 | 28.65 / 77.24 | not surveyed |
| pad_tlp_flat PAD | to VSS / to VDD | 0.43 / 0.72 | 0.46 / 0.80 | 0.44 / 0.73 | not surveyed |
(*) netres `published_pad.json` "bond|diodes" for hspad is all 12 diodes of the leg shorted together. My solver with the same grouping gives 25.41 / 65.28 (P) and 26.35 / 66.57 (N), Magic 25.15 / 64.90
and 26.06 / 66.01: the tool is right, the grouping is not a physical ESD case. For usb, tx and reference netres grouped by polarity and agrees with me.

### Where the ohms are (M1 segment list, typ)
`pad_refpad` P, either polarity, 25.0 ohm: Metal2 riser 4 x 330.7 um 7.44 | Via2 x9 + Via3 x9 1.00 | Metal4 8 x 330.5 um 3.72 | Via4 x9 0.50 | Metal5 8 x 84 um 0.42 | Via4 x9 0.50 |
Metal4 8 x 102 um 1.15 | Via3 x9 0.50 | Metal3 2 x 20 um 0.90 | **Via2 x1 4.50** | Metal2 bar 0.48 um with 4 x (**Via1 x1** + plate) 4.34.
wirepad and txpad are the same shell with a longer first Metal4 run (450.5 and 410.5 um); the N legs have a 340.7 um riser, a shorter Metal4 and a longer Metal3 (40 / 80 um).
`pad_rf_pair` P, 28.4 ohm: Metal2 riser 24 x 350.7 um 1.32 | Via2 x9 + Via3 x9 1.00 | Metal4 12 x 250.5 um 1.88 | **Via4 x1 4.50** | Metal5 12 x 64 um 0.21 | **Via4 x1 4.50** | Metal4 12 x 102 um 0.77 |
**Via3 x1 4.50** | Metal3 2 x 20 um 0.90 | **Via2 x1 4.50** | bar + 4 x **Via1 x1** 4.34. `pad_hspad` is this shell with an 8 um riser (3.95 ohm) and two rail-diode rows.
`pad_tlp_flat`, 0.43 ohm: Metal2 neck 50 x 23.6 um, 13 x 21.5 um, then an 11 um bar to the diodes (about 3.6 squares, 0.33 ohm) | Via1 x11 per diode, 44 in parallel 0.10.

### Single cuts in series on the path (M2b via currents)
| shell | cells | single cuts that carry 100 % | then | single-cut share typ / high |
|---|---|---|---|---|
| A | refpad, wirepad, txpad | 1 (the Via2 from the Metal3 trunk onto the diode bar; in wirepad the two rail rows share: 58-62 % / 38-42 %) | 1 Via1 per diode (45 / 26 / 17 / 12 % of the current) | 5.9 of 25 ohm / 18.9 of 47 ohm |
| B | hspad, rf_pair, rftxpad, single_leg | 4 (Via4 at the riser bar end, Via4 back down, Via3 onto the Metal3 trunk, Via2 onto the bar) | 1 Via1 per diode | 19.4 of 28.7 / 63.9 of 77 |
| TLP | pad_tlp_flat | 0 (Via1 x11 per diode) | | 0 |
1.33 A through one 0.26 um cut is far beyond any via current rule; whether the cut survives a 150 ns event I did not assess.

### Resistance seen from the core tap (where the cell's devices and the core pin hang on the pad net), ohm typ / high to the diodes
The riser below the branch point carries the ESD current but no device sits on it, so the devices see less than the bond pad does:
refpad 17.1-18.9 / 37.8-39.9; wirepad 15.5-18.9 / 29.8-39.8; txpad 18.1-19.9 / 38.8-41.0; hspad 16.5-21.4 / 44.9-56.9; rf_pair, rftxpad (core pin) 19.6-23.2 / 54.8-58.9; single_leg 19.6 / 54.8.

## Result 2: return sides (M2b only, plus the hand checks below), ohm typ / high
"ring" = the cell's own VSS landings on ring DVSS: two 2 x 2 um Metal2-5 stacks at depth 77.3-79.3 (one in single_leg). "pin" = the cell's VSS pin on Metal5 (refpad, wirepad, txpad: top edge;
hspad: side edge at the leg). The RF cells have no VSS pin; their column is the VSS label point on the network's Metal3 trunk foot, not an external connection.
| cell | rail diodes' cathode rings -> clamp MOS drains (P, N) | VSS diodes' anode rings -> ring (P, N) | clamp MOS sources -> ring | ring -> pin | anode rings -> pin (P, N) | clamp sources -> pin |
|---|---|---|---|---|---|---|
| pad_refpad | 16.1 / 33.5, 19.7 / 37.7 | 45.2 / 90.7, 48.8 / 94.9 | 37.5 / 68.2 | 23.9 / 49.4 | 26.2 / 47.4, 29.8 / 51.5 | 18.5 / 24.9 |
| pad_wirepad | 12.0 / 22.6, 15.3 / 26.4 | 46.2 / 91.6, 49.8 / 95.7 | 38.5 / 69.1 | 27.2 / 53.1 | 29.1 / 50.9, 32.7 / 55.1 | 21.4 / 28.4 |
| pad_txpad | 16.1 / 33.5, 19.7 / 37.7 | 45.5 / 90.7, 49.1 / 94.8 | 37.8 / 68.2 | 26.2 / 51.8 | 27.3 / 48.7, 30.9 / 52.9 | 19.6 / 26.3 |
| pad_hspad | 12.0 / 22.6, 15.3 / 26.4 | 27.0 / 75.8, 30.6 / 80.0 | 19.4 / 53.5 | 52.3 / 99.2 | 54.2 / 103.6, 57.8 / 107.8 | 46.6 / 81.3 |
| pad_rf_pair, pad_rftxpad | 16.1 / 33.5, 19.7 / 37.7 | 27.0 / 75.9, 30.6 / 80.1 | 19.4 / 53.5 | (label) 17.7 / 52.6 | (label) 9.3 / 23.2, 12.9 / 27.4 | (label) 2.6 / 4.2 |
| pad_single_leg | 16.1 / 33.5 | 35.0 / 96.5 | 27.3 / 74.1 | (label) 25.7 / 73.2 | (label) 9.3 / 23.2 | (label) 2.6 / 4.2 |
| pad_tlp_flat | cathode rings -> VDD label on its Metal2 bar 0.22 / 0.67 | anode rings -> VSS label on its bar 0.13 / 0.38 | no clamp | strap is assembly work | | |
The same construction as on the pad side: one Via1 per diode ring, a 0.48 um Metal2 bar, one Via2 onto a 2 um Metal3 trunk.
Hand checks (refpad): rail side P = bar ladder with 20 um lead 5.84 + Via2 x1 4.50 + Metal3 2 x 64 um 2.88 + Via3 x9 + Via4 x9 1.00 + Metal5 8 x 271 um 1.36 = 15.6 (+ the Metal5 run to the
bank that I did not measure; solver 16.1). Ring -> pin = [Metal2 2 x 341.7 um 15.38 + Via2 x1 + Via3 x1 9.0 + stack 3 x 9 cuts 1.5 + Metal4 1 um x 22.7 um 2.04] parallel
[same with 188.3 um of the 1 um Metal4, 16.95] = 16.9, + shared Via4 x1 4.5 + Metal5 8 x 492 um 2.46 = 23.9 (solver 23.9).
The clamp sources reach the refpad VSS pin only through 14 ohm of Metal4 (a 4 um bar of 367 um at depth 413-417 and the 4 um feed before it).
Limits of this part: all 18 MOS islands are taken as the clamp and shorted at their contacts (no split between the gate-coupled bank and the RC clamp, no finger ballast); the ring itself and
whatever the assembly adds (straps to the VSS pin, core VSS grid) are not in a family GDS, so these are cell-level numbers.

## Result 3: consequence at HBM 2 kV (1.33 A) and 1 kV (0.67 A), typical metal
Pad-side term only (the claim under test), on top of the capacitance-only peaks of README section 4. Limits 6.0 V (DC screen) and 8.0 V (transient).
| cell | C-only peak, README 4 (V) | R bond->diodes typ (ohm), min-max over legs and polarities | I x R at 1.33 A (V) | I x R at 0.67 A (V) | bond-pad total at 2 kV / 1 kV with the README peak (V) | R core tap->diodes typ (ohm) | tap total 2 kV / 1 kV (V) | allowed R for 8.0 V at 2 kV / 1 kV (ohm) |
|---|---|---|---|---|---|---|---|---|
| pad_refpad | 6.18-6.91 (2 kV) | 24.8-26.6 | 33-35 | 17-18 | 40-42 / n/a | 17.1-18.9 | 30-32 / n/a | 0.8 / n/a |
| pad_wirepad | <= 5.41 (2 kV) | 22.9-26.3 | 31-35 | 15-18 | 36-40 / n/a | 15.5-18.9 | 26-31 / n/a | 1.9 / n/a |
| pad_txpad | 4.52-4.70 (1 kV) | 25.7-27.5 | 34-37 | 17-18 | n/a / 22-23 | 18.1-19.9 | n/a / 17-18 | n/a / 4.9 |
| pad_hspad | <= 5.41 (2 kV), <= 4.67 (1 kV) | 27.9-31.7 | 37-42 | 19-21 | 43-48 / 23-26 | 16.5-21.4 | 27-34 / 16-19 | 1.9 / 5.0 |
| pad_rf_pair | 6.18-6.91 (2 kV) | 28.7-30.8 | 38-41 | 19-21 | 45-48 / n/a | 19.6-23.2 | 33-38 / n/a | 0.8 / n/a |
| pad_rftxpad | 4.52-4.70 (1 kV) | 28.7-30.8 | 38-41 | 19-21 | n/a / 24-25 | 19.6-23.2 | n/a / 18-20 | n/a / 4.9 |
| pad_single_leg | none in README 4 | 28.7-28.7 | 38-38 | 19-19 | n/a / n/a | 19.6-19.6 | n/a / n/a | n/a / n/a |

| cell | positive zap, loop metal typ / high (ohm): pad->rail diodes + rail->clamp drains + clamp sources->ring landings | same, I x R at 1.33 / 0.67 A typ (V) | negative zap, loop metal typ / high (ohm): ring landings->VSS diode rings + diodes->pad | same, I x R at 1.33 / 0.67 A typ (V) |
|---|---|---|---|---|
| pad_refpad | 79-84 / 149-155 | 105-112 / 53-56 | 70-74 / 138-142 | 93-98 / 47-49 |
| pad_wirepad | 73-78 / 130-135 | 98-103 / 49-52 | 73-76 / 140-144 | 96-101 / 49-51 |
| pad_txpad | 80-85 / 150-156 | 106-113 / 53-57 | 71-75 / 139-143 | 95-99 / 48-50 |
| pad_hspad | 59-64 / 146-152 | 79-85 / 40-43 | 58-62 / 156-161 | 77-83 / 39-42 |
| pad_rf_pair | 64-70 / 164-171 | 85-93 / 43-47 | 56-60 / 153-158 | 74-79 / 37-40 |
| pad_rftxpad | 64-70 / 164-171 | 85-93 / 43-47 | 56-60 / 153-158 | 74-79 / 37-40 |
| pad_single_leg | 72-72 / 185-185 | 96-96 / 48-48 | 64-64 / 174-174 | 85-85 / 43-43 |
"n/a" = README section 4 gives no capacitance-only peak for that cell at that level; I x R alone is already over 8.0 V in every such case. The loop table assumes the ring landings are the
only VSS return; with the VSS pin taken instead, use the pin columns of Result 2 (refpad positive zap 25.0 + 16.1 + 18.5 = 59.6 ohm, negative 25.0 + 26.2 = 51.2 ohm).
Every family cell fails both limits at both levels, at the bond pad and at the core tap, with typical metal; the high corner is 1.7 to 2.7 times worse. To hold 8.0 V the pad-side
resistance would have to be 0.8-1.9 ohm at 2 kV and about 4.9 ohm at 1 kV. `pad_tlp_flat` adds 0.58 V at 1.33 A: fine, but it also means the TLP site will not show the family problem
(its on-resistance calibration contains 0.44 ohm of metal, the families 23-31 ohm plus the return).

## Control (can the methods refute?)
Statement tested: "the ring-side ESD_RAIL route of pad_refpad (Metal3 trunk foot, Via3 x9, Via4 x9, 8 um Metal5, 268 um) is also in the 20-25 ohm class". `ctrl.py`, `ctrl_rail.gds`.
M1 hand: 0.5 + 0.5 + 268 / 8 x 0.04 = 2.34 typ, 4.97 high. M2b: 2.36 / 5.00. M2a Magic: 5.00 high as a single resistor; at typ Magic writes no resistor network for this net (0 nets output).
REFUTED, as it should be. `pad_tlp_flat` (0.44 ohm, three methods) is a second case where the same procedure reports a low value.
Magic's second network copy in that control file (2.53 + 2.50 ohm branch beside the 5.00 ohm resistor) is the duplicate-copy behaviour mentioned under M2a.

## Not checked
- Via resistance against the GF design manual (not in the PDK tree); temperature (rm tc1 3.3e-3 / K) and self-heating during the pulse.
- Whether a single cut or the 0.48 um bar survives 1.33 A / 0.67 A for 150 ns.
- Magic on the return nets, and Magic on real layout with devices (it lumps; tried on `pad_tlp_flat`).
- The standalone `network`, `network-gc`, `network-gc-d2`, `network-shunt`, `shunt-v2` cells; the in-flight hspad fix (`hsfix/build/f5`); the assembled chip.
- 1 kV capacitance-only peaks for refpad, wirepad, rf_pair and 2 kV peaks for txpad, rftxpad (not in README section 4); single_leg has no number there.
- Diode and contact resistance, current sharing between diodes with their real I-V (the 45 / 26 / 17 / 12 % split is metal only).
- No transient simulation: Result 3 is I x R added to published peaks, not a rerun of the HBM benches.

## Ran versus read
Ran (container, one job at a time, OMP 1): the tracer on all 8 published GDS; M2a Magic on all 13 family pad legs, the TLP pad net and the control; M2b on the same plus the RAIL and VSS nets
of the seven families and the TLP bars; Magic on the real `pad_tlp_flat`. Hand: M1 for all legs (rftxpad / single_leg by identity with rf_pair), two return-side checks, the control.
Read only: the Magic tech file and ngspice model parameters, README sections 1-8, `hsfix/final_part2.md`, `hsfix/res/*.json` (for the comparison column), `RAIL-CONTINUITY.md`.
Not used to produce any number: `hsfix/netres.py`.
Files: `pad_table.md`, `conseq.md`, `ret_table.txt`, `handcalc_segments.txt`, `magic_pad*.log`, `ret_*.log`, `s_*.json` (per net: resistance, split by layer, via currents), scripts, traced pad nets `n_*.gds`.
