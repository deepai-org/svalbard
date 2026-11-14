# wafer.space answers: consequences for the pads (pads owner sub-task, 2026-11-14)

STATUS: COMPLETE (all eight sections and the owner list). Analysis only: python and KLayout-python, no circuit simulation,
nothing in the project tree edited, nothing committed. To resume or re-run: every script is beside this file and is
re-runnable (`python3 -I wire.py`, `python3 -I plan.py`, `python3 -I diodes.py`; the census with
`MEM=10g scratch/pads-core/dock.sh 'python3 /work/ws/esd_census.py [gds ...]'`).

Tags: **[GDS]** measured with KLayout on GDS; **[NET]** read from a netlist; **[BOARD]** from the parsed run-2 board
(`../bond/board-run2.json`) or `spec/package-channel.json` (run-1 board, same fingers and contacts); **[ANS]** from
`scratch/reviews/wafer-space-answers.md` with its confidence (P / T / S / I); **[CALC]** computed here from those;
**[ASSUMED]** an assumption of this report; **[REPORT]** quoted from an earlier report, not re-derived.

Files here: `wire.py` -> `bond-wire.json`, `wire-table.md`; `plan.py` -> `plan.json`; `diodes.py` -> `diodes.json`;
`esd_census.py` -> `layer-census-blocks.json` (238 GDS files), `layer-census-chip-v5.json`, `census-table.md`, logs
`census.log`, `census-chip.log`; `control.py` (census negative control); `merge_bond_wire.py`.

## 0. Findings in short

1. **LNA ground:** a signal site turned into a ground pad (a) does not work: its return through trace, connector and carrier
   is 4.9-7.5 nH, which resonates with the pad capacitance at 3.1-5.0 GHz; at 2.42 GHz it gives -10 to +4 dB (no isolation,
   possibly gain). The only form that isolates is (b), ground site 71 (`vss_pads[1]`, next to RF_RX_P) on its own net:
   1.9-3.5 nH, 8-20 dB from the pad alone (11-17 dB at nominal L), falling to 0 dB when the total AGND_RX-to-VSS capacitance reaches about
   0.8 pF. It costs the die-VSS bond nearest the LNA. **Recommendation: no split in the pad ring (c); runner-up (b) at
   bond 71, only if rf_rx shows the condition in section 1.6. (a) is rejected.** Confidence: medium (lumped divider, no extraction).
2. **POR strap:** needs nothing from the assembler; the tester reads GOOD on it.
3. **P2:** DC benefit is real but smaller with the real wire (D2H ring drop 18.2 -> 14.3 mV per 100 mA with 0.8 mil Al);
   dynamic benefit is nil (path 8.1-8.7 nH against 4.0-4.6 nH for a real supply finger; all supply paths in parallel
   0.54 -> 0.51 nH). **Recommendation: drop P2, keep `bidir[17]` as a bonded provider spare.** No signal sits on a supply finger (0 of 74).
4. **Bonds:** with a 250 um die the four corner-adjacent bonds 18 / 37 / 55 / 74 are 3.05 mm of wire for finger-centre
   landing (plan 2.991 mm). A 0.1 mm shift breaks the 3 mm plan limit on 8 bonds (centre landing) or the 45 deg limit on
   4 to 8 bonds (near-end landing). Wire resistance is 0.21-0.28 ohm (Al), about twice the 0.13 ohm assumed so far.
   Current capability is not a concern: 87.5 mA is 26 % of the MIL-M-38510 design limit (0.34 A) and a clamp event uses 1 % of the fusing I2t.
5. **Bond tester:** every one of the 56 signal pads has a junction diode from ground to the pad (pad negative), so a
   negative-current test reads GOOD everywhere. A positive-current test (pad to supply) would read OPEN on 21 custom pads,
   because they steer into an isolated rail. The polarity is not published. All eight supply pins are one net on this die (8 uF seen from each).
6. **ESD implant 24/0: zero shapes** in all 238 GDS files checked, in the provider IO cells of the PDK, in the retained
   provider ring and in the assembled v5 chip. No device in our GDS, and no provider cell, draws it. Its absence from the
   mask set changes nothing for this die. No DRC rule requires it.
7. **DNWELL** is used in one block (`rf_tx/rfdriver`); **NAT** only in `pll_vreg`; **SAB** is everywhere, on poly resistors
   only in our cells and on MOS drains only inside the provider IO cells.
8. Do not draw the two west openings.

## 1. LNA ground without extra wires

### 1.1 What is fixed

- One 74-wire layout, no custom diagram, no down-bond, no double bond, no extra wire [ANS, T]. The two west extra openings
  (W-A, W-B) cannot be bonded. All GND fingers are one board net; the paddle is GND [BOARD].
- West sites, north to south, with bond numbers [BOARD + GDS, `../spec/site_list.md`]: `dvdd[3]` 58, `dvss[5]` 57 are at the
  north end; near RF_RX: `inputs[6]` 65 BB_Q_N, `inputs[7]` 66 BB_Q_P, `inputs[8]` 67 BB_I_N, `inputs[9]` 68 BB_I_P,
  `inputs[10]` 69 RF_RX_N, `inputs[11]` 70 RF_RX_P, `vss_pads[1]` 71 GND, `vdd_pads[1]` 72 VDD_CORE_1, `dvss_pads[7]` 73 GND,
  `dvdd_pads[5]` 74 VDD_IO_3. Pitch 211 um. LNA outline 950..1072 x 1418..1621 um (`floorplan-v6.json`).

### 1.2 Model (state of each term)

- Frequency 2.42 GHz. The split is treated as a divider: die VSS noise drives AGND_RX through C (AGND_RX to die VSS);
  AGND_RX returns to board ground through L. V(AGND_RX) / V(die VSS) = XL / |XC - XL|, lossless [CALC]. Negative dB = isolation.
- C at the pad: pad and escape to die VSS 0.15-0.30 pF [REPORT PC-19, an estimate, not extracted] + clamp 56 fF
  [REPORT PC-19, simulated] = 0.206-0.356 pF, |XC| = 319-185 ohm. **The LNA's own capacitance from AGND_RX to die VSS and
  to the substrate is not included and is not known** (the published `pt_lna` has no DNWELL [GDS], so its NMOS bodies are
  in the common substrate).
- Bond inductance: `bond-wire.json` (section 4): 0.874 nH/mm x 3-D length nominal; min / max as defined there [CALC].
- COB trace: 0.1 mm microstrip, Z0 86.6 ohm, eeff 3.14 [BOARD] -> 0.512 nH/mm [CALC]; trace lengths, via and connector
  inductance per pin from `spec/package-channel.json` [BOARD + its estimates; the connector L has no published data].
- Carrier contact to ground via: 0.3-0.6 nH [ASSUMED]. GND finger to the board ground (run-2 pour 0.15 mm from the finger,
  or a via to In1): 0.1-0.3 nH [ASSUMED].

### 1.3 Candidates

| Cand. | Site (bond) | Today | To RF_RX_P / RF_RX_N pad (um) | To LNA outline (um) | Bond plan C / N (mm) | Bond L min / nom / max (nH) | Other terms (nH) | Return L min / nom / max (nH) | Z at 2.42 GHz (ohm) | Pad-only divider, C 0.206 / 0.356 pF at nominal L (range over L) | Series resonance with pad C (GHz) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| (a) | `inputs[9]` (68), contact 14 | BB_I_P | 422 / 211 | 914 | 2.482 / 2.091 | 1.62 / 2.23 / 2.91 | trace 3.37 mm = 1.72; via 0.47; connector 1.15; carrier 0.3-0.6 | 5.27 / 6.03 / 6.86 | 80 / 92 / 104 | -7.9 / -0.1 dB (-9.5 .. +2.3) | 3.2-4.8 |
| (a) | `inputs[8]` (67), contact 15 | BB_I_N | 633 / 422 | 983 | 2.438 / 2.042 | 1.58 / 2.19 / 2.85 | trace 5.09 mm = 2.61; via 0.35; connector 1.08; carrier 0.3-0.6 | 5.91 / 6.67 / 7.48 | 90 / 101 / 114 | -6.6 / +1.7 dB (-8.1 .. +4.1) | 3.1-4.6 |
| (a) | both BB_I sites in parallel | BB_I pair | | | | | | 3.17 nom | 48 | -7.3 / +0.7 dB (pad C doubles) | 3.4-4.4 |
| (a) | `inputs[7]` (66), contact 16 | BB_Q_P | 844 / 633 | 1088 | 2.409 / 2.009 | 1.56 / 2.17 / 2.82 | trace 3.18 mm = 1.63; via 0.41; connector 0.99; carrier 0.3-0.6 | 4.88 / 5.64 / 6.44 | 74 / 86 / 98 | -8.7 / -1.2 dB (-10.4 .. +1.0) | 3.3-5.0 |
| (a) | `inputs[6]` (65), contact 17 | BB_Q_N | 1055 / 844 | 1221 | 2.394 / 1.993 | 1.55 / 2.15 / 2.80 | trace 5.66 mm = 2.90; via 0.37; connector 0.85; carrier 0.3-0.6 | 5.96 / 6.71 / 7.51 | 91 / 102 / 114 | -6.6 / +1.8 dB (-8.0 .. +4.2) | 3.1-4.5 |
| (b) | `vss_pads[1]` (71), GND finger | die VSS bond | 211 / 422 | 921 | 2.689 / 2.327 | 1.79 / 2.40 / 3.16 | finger to plane 0.1-0.3 | 1.89 / 2.60 / 3.46 | 29 / 40 / 53 | **-17.0 / -11.3 dB** (-20.1 .. -8.0) | 4.5-8.1 |
| (b) | `dvss_pads[7]` (73), GND finger | die VSS bond | 633 / 844 | 1104 | 2.881 / 2.543 | 1.95 / 2.57 / 3.40 | finger to plane 0.1-0.3 | 2.05 / 2.77 / 3.70 | 31 / 42 / 56 | -16.4 / -10.6 dB (-19.3 .. -7.2) | 4.4-7.7 |
| (b) | 71 and 73 both | two VSS bonds | | | | | | 1.34 nom | 20 | -16.7 / -11.0 dB (no gain: pad C doubles) | 5.2-6.8 |
| (b) | `dvss_pads[6]` (63), GND finger | die VSS bond | 1477 / 1266 | 1541 | 2.409 / 2.009 | 1.56 / 2.17 / 2.82 | finger to plane 0.1-0.3 | 1.66 / 2.37 / 3.12 | 25 / 36 / 47 | -17.9 / -12.3 dB (-21.3 .. -9.2); 1.3-1.5 mm of on-die route to the LNA not included | 4.8-8.6 |
| (c) | none | | | | | | | | | 0 dB by definition; die VSS through 10 bonds, 0.23 nH in parallel (3.5 ohm) | |

All [CALC] from [BOARD] / [GDS] inputs; `plan.json` `lna_ground_candidates`.

Sensitivity of the best candidate (bond 71, nominal 2.60 nH) to the **total** AGND_RX-to-VSS capacitance, i.e. pad plus
whatever the LNA adds [CALC]:

| Total C (pF) | 0.20 | 0.36 | 0.50 | 1.0 | 2.0 | 5.0 |
|---|---|---|---|---|---|---|
| Bond 71 as AGND_RX (2.60 nH) | -17.3 dB | -11.2 | -7.3 | +3.6 | +15.5 (resonance 2.2 GHz) | +3.5 |
| BB_I_P as AGND_RX (6.03 nH) | -8.3 dB | +0.1 | +7.2 | +11.0 | +3.9 | +1.3 |

Return inductance that would be needed for a given isolation at 0.36 pF: 20 dB needs 1.09 nH, 44 dB needs 0.075 nH,
62 dB 0.010 nH, 76 dB 0.002 nH. No bond wire gives 44 dB; PC-19's statement that the pad gives a first 15-20 dB and the
LNA must supply the rest stands, with 11-17 dB as the corrected pad figure for the 0.8 mil wire.

### 1.4 (a) in detail: a west signal site as LNA ground

- Works mechanically with nothing from the assembler: standard site, standard wire, the carrier grounds the contact. The
  pad cell would be the staged `pad_agnd_flat` re-pitched to the template opening.
- Electrically it is the wrong tool at 2.4 GHz. The return is bond + 3.2-5.7 mm of 87 ohm trace + via + one connector
  contact + carrier via = 4.9-7.5 nH (74-114 ohm). With only the pad capacitance the divider is -10 .. +4 dB; with any
  realistic extra capacitance from the LNA (0.5-1 pF total) the series resonance moves onto the band and AGND_RX carries
  **more** noise than die VSS (+7 to +11 dB in the table above). Two sites in parallel do not help (the capacitance doubles too).
- What gives way: BB_I_P (bond 68, adjacent to RF_RX_N) = half of the BB_I debug pair (the pair becomes single-ended or is
  dropped); both BB_I sites = the whole I baseband debug pair. BB_Q sites are 633-1055 um from RF_RX and no better.
- Conditional variant: if wafer.space accepted a modified COB (same fingers, changed copper; "uncertain for Run 3" [ANS, T]),
  the finger of a signal site could be tied to the ground pour next to it and (a) would become equal to (b) without touching
  a ground site. That is a board question (follow-up 3), not something to plan on.

### 1.5 (b) in detail: a west ground site on its own on-die net

- Which site: **71 (`vss_pads[1]`)** is the only good one: 211 um from RF_RX_P, 921 um from the LNA outline, the same
  distance class as the retired W-A. 73 is 633 um away behind the VDD_CORE_1 pad 72; 63 is 1.3-1.5 mm away.
- Its finger is on the board ground plane, so the return is the bond plus the finger's ground connection: 1.9 / 2.6 / 3.5 nH.
- The cell at that site today, `gf180mcu_fd_io__dvss` [NET, PDK cdl]: ties the pad to DVSS (and, at the ring, VSS), and
  contains an RC-triggered clamp from DVDD to DVSS (`nfet_06v0`, W = 4 mm, 80 fingers, not a `_dss` device), a
  `diode_nd2ps_06v0` x4 from DVSS to DVDD and gate-oxide decoupling. The `dvdd` cell contains the same clamp. So the die has
  18 clamp cells; converting site 71 leaves 17 (-5.6 % of clamp width, 72 -> 68 mm).
- Replacement: the assembly's standard treatment of a custom site: provider cell swapped for the rail cell
  `5LM_METAL_RAIL`, custom pad placed on top. The ring then stays continuous at full width on Metal3-5 through the site
  (measured for every custom family in `RAIL-CONTINUITY.md`; `pad_agnd_flat` is Metal2-only in the rail bands by
  construction; to be re-measured after assembly). DVSS and VSS stay tied by the other 9 ground cells. Nothing replaces
  the clamp at that site, and nothing needs to (17 remain, the nearest at sites 72 and 73, 211 and 422 um away).
- What it costs:
  - one of the ten die-VSS bonds, and it is the one nearest the LNA and the RF_RX pads. All ten in parallel: 0.231 -> 0.255 nH
    (+10 %), 24.5 -> 27.1 mohm (Al) [CALC]. Locally the pair 71 || 73 (1.24 nH) becomes bond 73 alone (2.57 nH); the next
    ground bond is 63, 1.7 mm of ring north. The die-VSS noise the LNA sees through its other paths (below) can rise by up
    to 6 dB locally [CALC upper bound, not modelled with the ring]. The power-delivery numbers (0.34 / 3.0 / 14.6 mV) assume ten ground bonds.
  - the RF_RX pad network returns its ESD current to die VSS [REPORT PC-19]; its nearest ground bond moves from 211 um to
    633 um (+0.08 ohm of ring, about 0.1 V at 1.33 A: not significant).
  - the core-ring VSS strap that `kl_assemble.py` drops at each `dvss` cell (lines 314-315, `lef_pins`) disappears at this site: assembly change.
  - a new, unreviewed custom cell at a ground site, and the die-VSS noise model has to be re-run with nine bonds.
- Is changing a ground site's cell allowed? What is published [ANS]: "Do not change the number of pads on any side ... The
  VSS pads are shorted on the default breakout PCB. This is why you should not change any of the ground pins" (mole99, T);
  "just use the default pad structure (VSS, VDD are the only ones that need to be the same)" (anfroholic, T); people can
  "change power/ground pads or even make their own fully custom pads" (mole99, T); the precheck checks only that the
  template openings exist (P). Reading: the rule protects the board (the finger is ground, so the pad must be a ground).
  Site 71 would still be a pad at 0 V bonded to a GND finger; only its on-die net name differs. I judge it allowed, with
  confidence medium, and it should be confirmed in one sentence by email (follow-up 2). The bond tester cannot test GND pads individually, so it sees no difference.

### 1.6 What the RF RX owner gets, and the recommendation

- Requirement: 44 / 62 / 76 dB from die VSS to the LNA input (PD2-12). From the pad split: (a) -10 .. +4 dB; (b) at bond 71
  11-17 dB at nominal L (8-20 dB over the wire range) with pad capacitance only, less 0-6 dB for the lost VSS bond, and falling to 0 dB at about 0.8 pF total
  (series resonance at 2.42 GHz is at 1.66 pF for 2.6 nH). The remaining 30-65 dB must come from the LNA in every case.
- Two paths the split does not touch [NET, reasoning, not simulated]: (i) each RF_RX pad has four `diode_nd2ps_06v0`
  (4 x 22.5 um2) from die VSS directly to the pad, plus the pad plate over the substrate: die-VSS noise is injected onto
  both LNA inputs as common mode whatever the LNA's source node is tied to; (ii) the LNA's NMOS bodies are in the common
  substrate (no DNWELL in `pt_lna` [GDS]). Rejection of both is the LNA's differential symmetry, not the ground split.
- **Recommendation on technical merit: (c), no ground split in the pad ring.** It keeps the ground bond next to the LNA,
  needs no new cell and no rule interpretation, and gives up at most 11-17 dB that are not in evidence and are partly
  cancelled by the lost bond. The measures already listed in power-delivery 5.2 (slow D2H slew in RF modes, div4,
  2421.875 MHz out of the channel plan) and the LNA's own rejection (PD2-15) carry the requirement either way.
- **Runner-up: (b) at bond 71**, to be chosen only if rf_rx's extracted LNA (PD2-15) shows all three: total AGND_RX-to-VSS
  capacitance (pad + LNA + substrate) at or below about 0.4 pF; a net gain of at least 10 dB at the LNA input with ground
  bond 71 removed from die VSS; and the source-node path, not the pad-diode common-mode path, dominating. If chosen, one pad only (71); a second (73) adds nothing.
- **(a) is rejected**: no isolation at 2.42 GHz, a resonance near the band, and it costs half a debug pair.
- Confidence: the inductance terms are good to about +-25 % (connector and carrier terms are estimates); the pad
  capacitance is an estimate; the divider ignores loss, which would flatten the resonance but not change the sign of the conclusion for (a).

## 2. POR strap on east `bidir[16]`

- Standard template site, bond 22, standard wire to its own finger 22 (`/pad_21`), connector contact 58 [BOARD]. Plan
  2.608 mm / 23.5 deg centre landing, 2.236 mm / 27.0 deg near-end; 3-D 2.29 / 2.67 / 2.76 mm; 2.33 nH, 248 mohm (Al) [CALC].
  Passes every rule in all 27 shift cases of section 4. **Nothing is asked of the assembler.**
- The pad is bonded, so the unbonded-safe evidence (`STRAP.md`: pull-down 105-157 kohm holds a floating pad at 5-16 uV) is
  not needed for assembly; it still covers a failed bond and a carrier that leaves contact 58 open (strap = 0). Strap = 1:
  carrier jumper from contact 58 to 3.3 V (20-35 uA [REPORT]). The finger net has no component on the COB [BOARD].
- Bond test: `gf180mcu_fd_io__in_c` has `nfet_06v0_dss` drains from the pad to DVSS and `pfet_06v0_dss` drains to DVDD
  [NET, PDK cdl], i.e. a junction diode to ground and one to the supply. It reads GOOD like every provider input. The
  pull-down (PD tied to VDD) is off on an unpowered die. If the tester powers the die, the pull-down takes 3.2-4.8 uA at a
  0.5 V diode drop: at the 10 uA step the diode still carries 5.2-6.8 uA and its voltage is about 10-17 mV lower than on a
  pad without pull-down [CALC from the 105-157 kohm]; at 100 uA and 1 mA the effect is below 2 mV. Not abnormal unless the
  GOOD window is tighter than about 20 mV. Worth one line in the expected-result list (section 5).

## 3. Option P2 restated

P2: one south-edge signal (HOST_CS_N, bond 14, `bidir[10]`, contact 66) moves to east `bidir[17]` (bond 23, contact 57);
the south site becomes a `dvdd` supply bond. Its wire lands on finger 14, a **signal** finger: no capacitor on the COB, one
connector contact, fed from the carrier.

### 3.1 Supply fingers against a signal finger

- The eight supply nets each have one 1 uF 0201 on the back of the COB [BOARD, ANS P], 2.04-2.85 mm of trace from the
  finger (`supplies_grounds.f_mm`). Path from the die pad to that capacitor: bond 2.15-2.66 nH + trace 1.04-1.46 nH
  (0.512 nH/mm, an upper figure: the supply traces may be wider) + via 0.4 nH [ASSUMED] + capacitor 0.25-0.4 nH [ASSUMED]
  = **3.96-4.57 nH per supply bond, mean 4.35 nH**; all eight in parallel 0.543 nH [CALC].
- P2 bond at site 14: bond 2.21 nH + COB trace 6.59 mm = 3.37 nH + via 0.28 nH + connector contact 1.21 nH [BOARD
  estimates] + carrier capacitor with via and 2 mm of trace 1.0-1.6 nH [ASSUMED] = **8.1-8.7 nH**, about twice a real supply
  finger. Added in parallel: 0.543 -> 0.509-0.511 nH (-6 %). Dynamically P2 does nothing useful, which agrees with
  power-delivery section 6 ("host rail 226 to 218 mV, ground bounce 655 to 617 mV").
- DC resistance of the P2 path: bond 234 mohm (Al) + COB trace 65 mohm (0.1 mm x 17.5 um copper, 9.8 mohm/mm, no plating
  credit) + contact 40 mohm [ASSUMED] = 0.34 ohm, against 0.23-0.28 ohm for a supply bond plus a few tens of mohm.

### 3.2 DC benefit with the real wire

Ring model of `../bond/sites.py` (0.153 ohm/mm, the 11 D2H pads share the load), re-implemented in `plan.py`; the two
controls reproduce `sites.json` (15.1 and 10.8 mV per 100 mA at 0.13 ohm per bond) [CALC]:

| Bond wire | Today: worst D2H drop per 100 mA; shares of bonds 74 / 18 / 72 | With a supply bond at site 14 on its signal finger; share of bond 14 | Change |
|---|---|---|---|
| 0.13 ohm (old assumption) | 15.1 mV; 31.7 / 31.1 / 18.8 % | 10.8 mV; 37.4 % | -28 % |
| 0.8 mil Al, per-bond R 0.23-0.28 ohm | **18.2 mV**; 25.5 / 25.2 / 19.4 % | **14.3 mV**; 26.4 % | -21 % |
| 0.8 mil Au, 0.17-0.22 ohm | 16.9 mV; 27.3 / 27.1 / 19.7 % | 13.2 mV; 27.6 % | -22 % |

- Power-delivery's own numbers (section 6, its model, not re-run here): worst supply bond 87.5 -> 63.5 mA (pad 18), ring
  drop 28-45 mV -> 23-37 mV, worst tap 106 -> 101 mV. With the thicker-than-assumed wire resistance the bonds share more
  evenly, so the 87.5 mA is likely an over-estimate and the relief from P2 smaller than 24 mA; the drop **in** the worst
  bond wire itself, 87.5 mA x 0.28 ohm = 25 mV, is of the same size as the ring drop and should be in that model
  (which bond resistance it uses was not checked).
- Limits it relieves: the `dvdd` cell Metal2 rating, 125 mA at 85 C [REPORT]: 70 % -> 51 %. The wire itself is at 26 % of
  its design limit today (section 4). Nothing fails without P2.

### 3.3 Is it still worth doing?

- For: 4 mV per 100 mA less drop on the D2H row, the worst cell at 51 % instead of 70 % of its rating.
- Against: no dynamic benefit; a supply fed through one signal contact and 6.6 mm of 0.1 mm trace with no local capacitor;
  HOST_CS_N leaves the SPI group; the bond tester will treat finger 14 as a signal pad and meets the supply net there
  (a ground diode exists, but 8 uF hangs on it: at 10 uA it takes about 0.4 s to reach 0.5 V, so it may read abnormal,
  section 5); the carrier must supply contact 66.
- **Recommendation: drop P2.** Keep `bidir[17]` as a bonded provider spare (`bi_24t`), usable as a second debug pin
  (option P4). Runner-up: keep P2 only if power delivery, after re-running with 0.21-0.28 ohm bonds, still finds a bond or
  cell above about 80 % of its limit. Confidence: medium-high on the dynamic statement, medium on the DC split (simple ring model).

### 3.4 Reverse hazard: a signal on a supply finger

Checked all 74 against the board nets (`plan.json` `finger_class_check`) [BOARD + contract]: 56 signal sites on 56 signal
fingers (`/pad_n`), 10 ground sites on GND fingers, 8 supply sites on the 8 supply nets; **0 mismatches**. No signal in
the current map sees a 1 uF capacitor. POR_BYPASS (finger 22, `/pad_21`) and the spare (finger 23, `/pad_22`) are plain
signal nets. P2 would be the only deliberate cross (a supply on a signal finger).

## 4. Bond audit with the real numbers

### 4.1 Assumptions

| Item | Value | Tag |
|---|---|---|
| Wire | 0.8 mil = 20.3 um, AlSi 1 %, wedge (Run 1); gold of the same diameter as the alternative | [ANS, T]; Run 3 not decided |
| Resistivity | Al 3.0e-8 ohm m (AlSi 1 % 2.9-3.1e-8), Au 2.3e-8 -> 92.7 and 71.1 mohm/mm at 20-25 C | [ASSUMED] handbook values |
| Die | 250 um [ANS, T, Run 1] + attach 25 / 35 / 50 um [ASSUMED] | |
| Loop model | two straight segments: pad -> apex (h above the die face at fraction f of the plan span) -> finger surface (H = die + attach below the die face). min: h 0.10, f 0.25, H 0.275; nominal: h 0.15, f 0.25, H 0.285; max: h 0.30, f 0.35, H 0.300 mm | [ASSUMED]; loop height is not published |
| Lengths reported | min = near-end landing (0.1 mm inside the finger end) with the min loop; nom = finger-centre landing, nominal loop; max = finger-centre landing, max loop | |
| Inductance | nom = 0.2 l ln(4h/d) nH with h = 0.40 mm above the In1 plane = 0.874 nH/mm (the same formula gives the 0.83 nH/mm of the spec for a 25 um wire); min = h 0.22 mm (run-2 ground copper under the wire, 0.754 nH/mm) on the min length; max = partial self inductance 0.2 l (ln(4l/d) - 0.75) of the max length. No mutual coupling; the glob-top does not change L | [CALC] |
| Die placement | shift x, y in {-0.1, 0, +0.1} mm and rotation in {-1, 0, +1} deg about the die centre, 27 cases; fingers fixed | 0.1 mm from the task; the rotation is [ASSUMED] (1 deg = 56 um at a die corner) |
| Rules | no crossing; angle <= 45 deg; length < 3 mm; length >= max(1 mm, 2 x 0.25 mm) = 1 mm | [ANS, P] |

Plan geometry is `../bond/bond-audit.json` (pad opening centres from GDS, finger centres from the run-2 board), unchanged.
Under a shifted or rotated die the angle is taken against the board axis of the finger row.

### 4.2 Results [CALC]

- Nominal die position: plan 2.197-2.991 mm (centre), 1.797-2.665 mm (near-end); angle max 38.7 / 44.0 deg. 3-D nominal
  2.27-3.05 mm (centre), up to 2.73 mm (near-end); 3-D min 1.86 mm; 3-D max 3.12 mm.
  - **Centre landing: bonds 18, 37, 55, 74 are 3.048 mm of wire (over 3 mm by 0.05 mm) with the nominal loop**; with the
    high loop also 19, 36, 56, 73 (3.01-3.12 mm). In plan all 74 are under 3 mm (margin 9 um).
  - Near-end landing: no violation, margin to 3 mm 0.27 mm (3-D), margin to 45 deg 1.0 deg (bonds 1, 17, 38, 54).
  - Minimum length: shortest wire 1.80 mm plan against 1 mm; the 2 x die thickness rule (0.5 mm) never binds.
  - No crossing in any case, including all 27 shift cases.
- With die shift +-0.1 mm (no rotation):
  - centre landing: plan length >= 3 mm on **18, 19, 36, 37, 55, 56, 73, 74** (max 3.13 mm); 3-D >= 3 mm additionally on 1, 17, 38, 54;
  - near-end landing: angle > 45 deg on **1, 17, 38, 54** (max 47.3 deg); no length violation (max plan 2.81 mm).
- With shift and +-1 deg rotation: centre landing the same 12 bonds (max plan 3.139 mm); near-end landing angle > 45 deg
  also on 18, 37, 55, 74 (max 48.3 deg).
- So: no single landing rule passes a 0.1 mm placement error. A mixed rule nearly does: near-end landing on the eight
  long bonds (18, 19, 36, 37, 55, 56, 73, 74: plan <= 2.81 mm, wire <= 2.87 mm, angle <= 44.7 deg with shift alone, but
  45.7 deg on 18 / 37 / 55 / 74 once 1 deg of rotation is added) and centre landing on the four steep ones (1, 17, 38, 54:
  angle <= 42.6 deg, plan <= 2.965 mm, wire 3.01-3.02 mm, i.e. 0.02 mm over if the limit is wire length). A landing
  point between near end and centre for those four was not searched. Whether
  3 mm means plan or wire length, how the angle is taken, and whether the end-of-row pads are relaxed (the Discord review
  note relaxes the angle for pads 1, 24, 37, 60 on another footprint) is for wafer.space (follow-up 5). The bonder's vision
  aligns to the die, and the fingers are 1.0 mm long for this reason [ANS].
- Three of the eight supply bonds (18, 37, 74: VDD_IO_0 / 1 / 3) and three ground bonds (19, 36, 73) are among the marginal ones.

### 4.3 Electrical values

- L nominal 1.99-2.66 nH per bond (min 1.40, max 3.54 over the loop and landing range). R: Al 211-282 mohm nominal,
  Au 162-217 mohm. At 2.42 GHz the skin depth in Al is 1.8 um, so the RF resistance is about 2.9 x DC (0.6-0.8 ohm) [CALC].
- **The 0.13 ohm per bond used so far (`SITES.md`, labelled as 2.5 mm of 25 um gold) is half the real Al value.**
- Relation to `spec/package-channel.json`: its `bond_mm` is the generator's pad-centre plan estimate (uniform 211 um
  pitch on all edges), 0.17 mm shorter to 0.02 mm longer than the audited plan length (mean -0.02 mm); `bond_nH_0p83` and
  `bond_nH_1p0` are 0.83 and 1.0 nH/mm times that. `L_nH.nom` here is 0.04-0.19 nH above `bond_nH_0p83` (mean +0.15) and
  0.21-0.50 nH below `bond_nH_1p0` (mean -0.28). The existing two columns therefore still bracket the nominal value;
  `L_nH.max` (free-space partial inductance of the longest loop) lies above `bond_nH_1p0` by 0.3-0.7 nH.

### 4.4 Current capability [CALC, formulas cited]

| Quantity | 0.8 mil Al | 0.8 mil Au | Source / formula |
|---|---|---|---|
| Maximum design current, wire longer than 1 mm | **0.343 A** | **0.463 A** | MIL-M-38510 internal lead-wire rule (general specification, design and construction; paragraph number not checked here): I = K d^1.5, d in inches; K = 15,200 (Al), 20,500 (Au) |
| Same, wire <= 1 mm (not our case) | 0.497 A | 0.678 A | K = 22,000 / 30,000 |
| Preece fusing current, long wire in free air | 0.171 A | not in Preece's table (Cu 0.231 A) | I = a d^1.5, a = 7,585 (Al), 10,244 (Cu), d in inches. Lower bound only: it ignores conduction into the bond feet, which dominates for a 2-3 mm wire |
| DC to reach melting at mid-span, conduction along the wire only, 3.0 / 2.5 / 2.0 mm | 0.40 / 0.49 / 0.61 A | 0.63 / 0.75 / 0.94 A | dT = I2 rho l2 / (8 k A2), rho(T) linear, k = 220 / 315 W/mK; epoxy around the wire raises these values |
| DC for 100 K rise at mid-span, 3.0 / 2.5 / 2.0 mm | 0.23 / 0.28 / 0.35 A | 0.32 / 0.39 / 0.48 A | same; the glob-top limits the usable rise to about 100-150 K |
| Rise at 87.5 mA / 71 mA, 3 mm wire | 11.5 K / 7.5 K | 6.1 K / 4.0 K | same, no credit for the epoxy |
| I2t to the onset of melting (adiabatic) | 2.70e-3 A2 s | 5.04e-3 A2 s | A2 cv / (rho0 alpha) ln(1 + alpha dTm) |
| Fusing current, 1 us / 1 ms pulse | 52 A / 1.64 A | 71 A / 2.25 A | from I2t; the 1 ms value is conservative (heat spreads 0.3 mm in 1 ms) |

- Against the currents power delivery quotes: worst supply bond 87.5 mA = 26 % of the MIL design limit (Al), worst ground
  bond 71 mA = 21 %. The community figure in the answers file (350 mA fusing for 20 um Al) is the same number as the MIL limit.
- Fired supply clamp: 18-24 A over 8 supply bonds for 1-3 us, 2.3-3 A per bond: 3 A for 3 us is 2.7e-5 A2 s = 1.0 % of
  the Al fusing I2t (0.5 % for Au); adiabatic rise 3.2 K (Al), 2.4 K (Au). Even all 24 A in one wire for 3 us is 313 K
  (Al) / 200 K (Au), below melting. **The wire survives the clamp event with a margin of about 100 in I2t.**
- Not covered: the bond heel and the pad metallisation (Metal2 strips, 125 mA per cell at 85 C [REPORT]) are the weaker
  elements at DC; nothing here changes that figure.

### 4.5 Table of all 74 bonds [CALC]

Plan length and angle for centre (C) and near-end (N) landing; 3-D min / nom / max as defined in 4.1; nominal 3-D for
both landings; L min / nom / max; R at nominal length; worst case over the 27 placement cases for each landing with the violations found.

| Bond | Side | Site | Signal | Plan C / N mm | Angle C / N | 3-D min / nom / max mm | 3-D nom C (N) | L min / nom / max nH | R Al / Au mohm (nom) | Shifted C: plan max / angle max / violations | Shifted N |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | S | clk_pad | D2H_D[0] | 2.815 / 2.498 | 38.7 / 44.0 | 2.54 / 2.87 / 2.96 | 2.87 (2.57) | 1.92 / 2.51 / 3.32 | 266 / 204 | 2.964 / 42.6 / 3D>=3mm | 2.652 / 48.3 / angle>45 |
| 2 | S | rst_n_pad | RESET_N | 2.683 / 2.350 | 35.0 / 40.1 | 2.40 / 2.75 / 2.83 | 2.75 (2.42) | 1.81 / 2.40 / 3.15 | 255 / 195 | 2.830 / 39.0 / - | 2.503 / 44.7 / - |
| 3 | S | bidir[0] | D2H_D[1] | 2.563 / 2.215 | 31.0 / 35.8 | 2.27 / 2.63 / 2.72 | 2.63 (2.29) | 1.71 / 2.30 / 3.01 | 244 / 187 | 2.708 / 35.1 / - | 2.366 / 40.6 / - |
| 4 | S | bidir[1] | D2H_D[2] | 2.457 / 2.094 | 26.6 / 30.9 | 2.15 / 2.53 / 2.62 | 2.53 (2.17) | 1.62 / 2.21 / 2.88 | 234 / 179 | 2.598 / 30.8 / - | 2.242 / 35.9 / - |
| 5 | S | bidir[2] | D2H_D[3] | 2.367 / 1.990 | 21.8 / 25.4 | 2.05 / 2.44 / 2.53 | 2.44 (2.07) | 1.54 / 2.13 / 2.77 | 226 / 173 | 2.503 / 26.1 / - | 2.133 / 30.6 / - |
| 6 | S | bidir[3] | D2H_D[4] | 2.294 / 1.906 | 16.7 / 19.4 | 1.96 / 2.37 / 2.46 | 2.37 (1.99) | 1.48 / 2.07 / 2.68 | 219 / 168 | 2.425 / 21.0 / - | 2.042 / 24.8 / - |
| 7 | S | bidir[4] | D2H_D[5] | 2.241 / 1.844 | 11.3 / 13.0 | 1.90 / 2.32 / 2.41 | 2.32 (1.93) | 1.44 / 2.02 / 2.62 | 215 / 165 | 2.364 / 15.6 / - | 1.972 / 18.3 / - |
| 8 | S | bidir[5] | D2H_CLK | 2.208 / 1.807 | 5.7 / 6.2 | 1.87 / 2.28 / 2.38 | 2.28 (1.90) | 1.41 / 2.00 / 2.58 | 212 / 162 | 2.323 / 9.8 / - | 1.924 / 11.3 / - |
| 9 | S | dvss_pads[0] | GND | 2.197 / 1.797 | 0.0 / 0.0 | 1.86 / 2.27 / 2.37 | 2.27 (1.89) | 1.40 / 1.99 / 2.56 | 211 / 162 | 2.302 / 3.9 / - | 1.901 / 4.0 / - |
| 10 | S | bidir[6] | D2H_D[6] | 2.208 / 1.808 | 5.7 / 6.2 | 1.87 / 2.28 / 2.38 | 2.28 (1.90) | 1.41 / 2.00 / 2.58 | 212 / 162 | 2.323 / 9.9 / - | 1.924 / 11.3 / - |
| 11 | S | bidir[7] | D2H_D[7] | 2.241 / 1.844 | 11.3 / 13.0 | 1.91 / 2.32 / 2.41 | 2.32 (1.93) | 1.44 / 2.02 / 2.62 | 215 / 165 | 2.364 / 15.6 / - | 1.972 / 18.3 / - |
| 12 | S | bidir[8] | D2H_D[8] | 2.294 / 1.906 | 16.7 / 19.5 | 1.96 / 2.37 / 2.46 | 2.37 (1.99) | 1.48 / 2.07 / 2.68 | 219 / 168 | 2.425 / 21.1 / - | 2.042 / 24.8 / - |
| 13 | S | bidir[9] | D2H_D[9] | 2.367 / 1.990 | 21.8 / 25.5 | 2.05 / 2.44 / 2.53 | 2.44 (2.07) | 1.54 / 2.13 / 2.77 | 226 / 173 | 2.504 / 26.2 / - | 2.133 / 30.7 / - |
| 14 | S | bidir[10] | HOST_CS_N | 2.457 / 2.094 | 26.6 / 30.9 | 2.15 / 2.53 / 2.62 | 2.53 (2.17) | 1.62 / 2.21 / 2.88 | 234 / 179 | 2.599 / 30.9 / - | 2.242 / 35.9 / - |
| 15 | S | bidir[11] | HOST_SCLK | 2.563 / 2.215 | 31.0 / 35.8 | 2.27 / 2.63 / 2.72 | 2.63 (2.29) | 1.71 / 2.30 / 3.01 | 244 / 187 | 2.709 / 35.2 / - | 2.367 / 40.6 / - |
| 16 | S | bidir[12] | HOST_MOSI | 2.683 / 2.351 | 35.0 / 40.1 | 2.40 / 2.75 / 2.83 | 2.75 (2.42) | 1.81 / 2.40 / 3.16 | 255 / 195 | 2.831 / 39.1 / - | 2.504 / 44.7 / - |
| 17 | S | bidir[13] | HOST_MISO | 2.815 / 2.498 | 38.7 / 44.0 | 2.54 / 2.88 / 2.96 | 2.88 (2.57) | 1.92 / 2.51 / 3.32 | 267 / 204 | 2.965 / 42.6 / 3D>=3mm | 2.653 / 48.3 / angle>45 |
| 18 | E | dvdd_pads[0] | VDD_IO_0 | 2.991 / 2.665 | 36.9 / 41.6 | 2.71 / 3.05 / 3.12 | 3.05 (2.73) | 2.04 / 2.66 / 3.54 | 282 / 217 | 3.139 / 40.5 / 3D>=3mm,plan>=3mm | 2.811 / 45.7 / angle>45 |
| 19 | E | dvss_pads[1] | GND | 2.881 / 2.543 | 33.9 / 38.4 | 2.59 / 2.94 / 3.02 | 2.94 (2.61) | 1.95 / 2.57 / 3.40 | 273 / 209 | 3.028 / 37.6 / 3D>=3mm,plan>=3mm | 2.688 / 42.7 / - |
| 20 | E | bidir[14] | WIRE_RX_N | 2.780 / 2.430 | 30.7 / 35.0 | 2.48 / 2.84 / 2.92 | 2.84 (2.50) | 1.87 / 2.48 / 3.28 | 263 / 202 | 2.925 / 34.4 / - | 2.574 / 39.3 / - |
| 21 | E | bidir[15] | WIRE_RX_P | 2.689 / 2.327 | 27.2 / 31.1 | 2.38 / 2.75 / 2.84 | 2.75 (2.40) | 1.79 / 2.40 / 3.16 | 255 / 196 | 2.830 / 31.0 / - | 2.468 / 35.6 / - |
| 22 | E | bidir[16] | POR_BYPASS | 2.608 / 2.235 | 23.5 / 27.0 | 2.29 / 2.67 / 2.76 | 2.67 (2.31) | 1.72 / 2.33 / 3.06 | 248 / 190 | 2.745 / 27.3 / - | 2.373 / 31.5 / - |
| 23 | E | bidir[17] | SPARE_E17 | 2.539 / 2.156 | 19.6 / 22.5 | 2.21 / 2.61 / 2.69 | 2.61 (2.23) | 1.66 / 2.28 / 2.98 | 241 / 185 | 2.671 / 23.4 / - | 2.290 / 27.1 / - |
| 24 | E | bidir[18] | USB_DN | 2.482 / 2.091 | 15.5 / 17.7 | 2.14 / 2.55 / 2.64 | 2.55 (2.17) | 1.62 / 2.23 / 2.91 | 236 / 181 | 2.609 / 19.2 / - | 2.220 / 22.3 / - |
| 25 | E | bidir[19] | USB_DP | 2.438 / 2.042 | 11.2 / 12.7 | 2.10 / 2.51 / 2.60 | 2.51 (2.12) | 1.58 / 2.19 / 2.85 | 232 / 178 | 2.559 / 14.9 / - | 2.164 / 17.1 / - |
| 26 | E | dvdd_pads[1] | PWR_AUX_0 | 2.409 / 2.009 | 6.8 / 7.4 | 2.06 / 2.48 / 2.57 | 2.48 (2.09) | 1.56 / 2.17 / 2.82 | 230 / 176 | 2.522 / 10.3 / - | 2.123 / 11.7 / - |
| 27 | E | dvss_pads[2] | GND | 2.394 / 1.993 | 2.3 / 2.0 | 2.05 / 2.46 / 2.56 | 2.46 (2.08) | 1.55 / 2.15 / 2.80 | 228 / 175 | 2.501 / 5.7 / - | 2.100 / 6.1 / - |
| 28 | E | bidir[20] | WIRE_TX_N | 2.394 / 1.993 | 2.3 / 2.0 | 2.05 / 2.46 / 2.56 | 2.46 (2.08) | 1.55 / 2.15 / 2.80 | 228 / 175 | 2.501 / 5.7 / - | 2.100 / 6.1 / - |
| 29 | E | bidir[21] | WIRE_TX_P | 2.409 / 2.009 | 6.8 / 7.4 | 2.06 / 2.48 / 2.57 | 2.48 (2.09) | 1.56 / 2.17 / 2.82 | 230 / 176 | 2.522 / 10.3 / - | 2.123 / 11.7 / - |
| 30 | E | bidir[22] | WTX_EXT_P | 2.438 / 2.042 | 11.2 / 12.7 | 2.10 / 2.51 / 2.60 | 2.51 (2.12) | 1.58 / 2.19 / 2.85 | 232 / 178 | 2.559 / 14.9 / - | 2.164 / 17.1 / - |
| 31 | E | bidir[23] | WTX_EXT_N | 2.482 / 2.091 | 15.5 / 17.7 | 2.14 / 2.55 / 2.64 | 2.55 (2.17) | 1.62 / 2.23 / 2.91 | 236 / 181 | 2.609 / 19.2 / - | 2.220 / 22.3 / - |
| 32 | E | bidir[24] | WMON | 2.539 / 2.156 | 19.6 / 22.5 | 2.21 / 2.61 / 2.69 | 2.61 (2.23) | 1.66 / 2.28 / 2.98 | 241 / 185 | 2.671 / 23.4 / - | 2.290 / 27.1 / - |
| 33 | E | bidir[25] | TLP_TEST | 2.608 / 2.235 | 23.5 / 27.0 | 2.29 / 2.67 / 2.76 | 2.67 (2.31) | 1.72 / 2.33 / 3.06 | 248 / 190 | 2.745 / 27.3 / - | 2.373 / 31.5 / - |
| 34 | E | vss_pads[0] | GND | 2.689 / 2.327 | 27.2 / 31.1 | 2.38 / 2.75 / 2.84 | 2.75 (2.40) | 1.79 / 2.40 / 3.16 | 255 / 196 | 2.830 / 31.0 / - | 2.468 / 35.6 / - |
| 35 | E | vdd_pads[0] | VDD_CORE_0 | 2.780 / 2.430 | 30.7 / 35.0 | 2.48 / 2.84 / 2.92 | 2.84 (2.50) | 1.87 / 2.48 / 3.28 | 263 / 202 | 2.925 / 34.4 / - | 2.574 / 39.3 / - |
| 36 | E | dvss_pads[3] | GND | 2.881 / 2.543 | 33.9 / 38.4 | 2.59 / 2.94 / 3.02 | 2.94 (2.61) | 1.95 / 2.57 / 3.40 | 273 / 209 | 3.028 / 37.6 / 3D>=3mm,plan>=3mm | 2.688 / 42.7 / - |
| 37 | E | dvdd_pads[2] | VDD_IO_1 | 2.991 / 2.665 | 36.9 / 41.6 | 2.71 / 3.05 / 3.12 | 3.05 (2.73) | 2.04 / 2.66 / 3.54 | 282 / 217 | 3.139 / 40.5 / 3D>=3mm,plan>=3mm | 2.811 / 45.7 / angle>45 |
| 38 | N | bidir[26] | H2D_D[0] | 2.815 / 2.498 | 38.7 / 44.0 | 2.54 / 2.88 / 2.96 | 2.88 (2.57) | 1.92 / 2.51 / 3.32 | 267 / 204 | 2.965 / 42.6 / 3D>=3mm | 2.653 / 48.3 / angle>45 |
| 39 | N | bidir[27] | H2D_D[1] | 2.683 / 2.351 | 35.0 / 40.1 | 2.40 / 2.75 / 2.83 | 2.75 (2.42) | 1.81 / 2.40 / 3.16 | 255 / 195 | 2.831 / 39.1 / - | 2.504 / 44.7 / - |
| 40 | N | bidir[28] | H2D_D[2] | 2.563 / 2.215 | 31.0 / 35.8 | 2.27 / 2.63 / 2.72 | 2.63 (2.29) | 1.71 / 2.30 / 3.01 | 244 / 187 | 2.709 / 35.2 / - | 2.367 / 40.6 / - |
| 41 | N | bidir[29] | H2D_D[3] | 2.457 / 2.094 | 26.6 / 30.9 | 2.15 / 2.53 / 2.62 | 2.53 (2.17) | 1.62 / 2.21 / 2.88 | 234 / 179 | 2.599 / 30.9 / - | 2.242 / 35.9 / - |
| 42 | N | bidir[30] | H2D_D[4] | 2.367 / 1.990 | 21.8 / 25.5 | 2.05 / 2.44 / 2.53 | 2.44 (2.07) | 1.54 / 2.13 / 2.77 | 226 / 173 | 2.504 / 26.2 / - | 2.133 / 30.7 / - |
| 43 | N | bidir[31] | H2D_D[5] | 2.294 / 1.906 | 16.7 / 19.5 | 1.96 / 2.37 / 2.46 | 2.37 (1.99) | 1.48 / 2.07 / 2.68 | 219 / 168 | 2.425 / 21.1 / - | 2.042 / 24.8 / - |
| 44 | N | bidir[32] | H2D_D[6] | 2.241 / 1.844 | 11.3 / 13.0 | 1.91 / 2.32 / 2.41 | 2.32 (1.93) | 1.44 / 2.02 / 2.62 | 215 / 165 | 2.364 / 15.6 / - | 1.972 / 18.3 / - |
| 45 | N | bidir[33] | H2D_D[7] | 2.208 / 1.808 | 5.7 / 6.2 | 1.87 / 2.28 / 2.38 | 2.28 (1.90) | 1.41 / 2.00 / 2.58 | 212 / 162 | 2.323 / 9.9 / - | 1.924 / 11.3 / - |
| 46 | N | dvss_pads[4] | GND | 2.197 / 1.797 | 0.0 / 0.0 | 1.86 / 2.27 / 2.37 | 2.27 (1.89) | 1.40 / 1.99 / 2.56 | 211 / 162 | 2.302 / 3.9 / - | 1.901 / 4.0 / - |
| 47 | N | bidir[34] | H2D_CLK | 2.208 / 1.807 | 5.7 / 6.2 | 1.87 / 2.28 / 2.38 | 2.28 (1.90) | 1.41 / 2.00 / 2.58 | 212 / 162 | 2.323 / 9.8 / - | 1.924 / 11.3 / - |
| 48 | N | bidir[35] | H2D_D[8] | 2.241 / 1.844 | 11.3 / 13.0 | 1.90 / 2.32 / 2.41 | 2.32 (1.93) | 1.44 / 2.02 / 2.62 | 215 / 165 | 2.364 / 15.6 / - | 1.972 / 18.3 / - |
| 49 | N | bidir[36] | H2D_D[9] | 2.294 / 1.906 | 16.7 / 19.4 | 1.96 / 2.37 / 2.46 | 2.37 (1.99) | 1.48 / 2.07 / 2.68 | 219 / 168 | 2.425 / 21.0 / - | 2.042 / 24.8 / - |
| 50 | N | bidir[37] | CLK_OBS | 2.367 / 1.990 | 21.8 / 25.4 | 2.05 / 2.44 / 2.53 | 2.44 (2.07) | 1.54 / 2.13 / 2.77 | 226 / 173 | 2.503 / 26.1 / - | 2.133 / 30.6 / - |
| 51 | N | bidir[38] | DBG_OBS0 | 2.457 / 2.094 | 26.6 / 30.9 | 2.15 / 2.53 / 2.62 | 2.53 (2.17) | 1.62 / 2.21 / 2.88 | 234 / 179 | 2.598 / 30.8 / - | 2.242 / 35.9 / - |
| 52 | N | bidir[39] | DBG_OBS1 | 2.563 / 2.215 | 31.0 / 35.8 | 2.27 / 2.63 / 2.72 | 2.63 (2.29) | 1.71 / 2.30 / 3.01 | 244 / 187 | 2.708 / 35.1 / - | 2.366 / 40.6 / - |
| 53 | N | analog[0] | ATB0 | 2.683 / 2.350 | 35.0 / 40.1 | 2.40 / 2.75 / 2.83 | 2.75 (2.42) | 1.81 / 2.40 / 3.15 | 255 / 195 | 2.830 / 39.0 / - | 2.503 / 44.7 / - |
| 54 | N | analog[1] | ATB1 | 2.815 / 2.498 | 38.7 / 44.0 | 2.54 / 2.87 / 2.96 | 2.87 (2.57) | 1.92 / 2.51 / 3.32 | 266 / 204 | 2.964 / 42.6 / 3D>=3mm | 2.652 / 48.3 / angle>45 |
| 55 | W | inputs[0] | RF_TX_N | 2.991 / 2.665 | 36.9 / 41.6 | 2.71 / 3.05 / 3.12 | 3.05 (2.73) | 2.04 / 2.66 / 3.54 | 282 / 217 | 3.139 / 40.5 / 3D>=3mm,plan>=3mm | 2.811 / 45.7 / angle>45 |
| 56 | W | inputs[1] | RF_TX_P | 2.881 / 2.543 | 33.9 / 38.4 | 2.59 / 2.94 / 3.02 | 2.94 (2.61) | 1.95 / 2.57 / 3.40 | 273 / 209 | 3.028 / 37.6 / 3D>=3mm,plan>=3mm | 2.688 / 42.7 / - |
| 57 | W | dvss_pads[5] | GND | 2.780 / 2.430 | 30.7 / 35.0 | 2.48 / 2.84 / 2.92 | 2.84 (2.50) | 1.87 / 2.48 / 3.28 | 263 / 202 | 2.925 / 34.4 / - | 2.574 / 39.3 / - |
| 58 | W | dvdd_pads[3] | VDD_IO_2 | 2.689 / 2.327 | 27.2 / 31.1 | 2.38 / 2.75 / 2.84 | 2.75 (2.40) | 1.79 / 2.40 / 3.16 | 255 / 196 | 2.830 / 31.0 / - | 2.468 / 35.6 / - |
| 59 | W | inputs[2] | REF_IN_N | 2.608 / 2.235 | 23.5 / 27.0 | 2.29 / 2.67 / 2.76 | 2.67 (2.31) | 1.72 / 2.33 / 3.06 | 248 / 190 | 2.745 / 27.3 / - | 2.373 / 31.5 / - |
| 60 | W | inputs[3] | REF_IN | 2.539 / 2.156 | 19.6 / 22.5 | 2.21 / 2.61 / 2.69 | 2.61 (2.23) | 1.66 / 2.28 / 2.98 | 241 / 185 | 2.671 / 23.4 / - | 2.290 / 27.1 / - |
| 61 | W | inputs[4] | AUX_CLK_N | 2.482 / 2.091 | 15.5 / 17.7 | 2.14 / 2.55 / 2.64 | 2.55 (2.17) | 1.62 / 2.23 / 2.91 | 236 / 181 | 2.609 / 19.2 / - | 2.220 / 22.3 / - |
| 62 | W | inputs[5] | AUX_CLK_P | 2.438 / 2.042 | 11.2 / 12.7 | 2.10 / 2.51 / 2.60 | 2.51 (2.12) | 1.58 / 2.19 / 2.85 | 232 / 178 | 2.559 / 14.9 / - | 2.164 / 17.1 / - |
| 63 | W | dvss_pads[6] | GND | 2.409 / 2.009 | 6.8 / 7.4 | 2.06 / 2.48 / 2.57 | 2.48 (2.09) | 1.56 / 2.17 / 2.82 | 230 / 176 | 2.522 / 10.3 / - | 2.123 / 11.7 / - |
| 64 | W | dvdd_pads[4] | PWR_AUX_1 | 2.394 / 1.993 | 2.3 / 2.0 | 2.05 / 2.46 / 2.56 | 2.46 (2.08) | 1.55 / 2.15 / 2.80 | 228 / 175 | 2.501 / 5.7 / - | 2.100 / 6.1 / - |
| 65 | W | inputs[6] | BB_Q_N | 2.394 / 1.993 | 2.3 / 2.0 | 2.05 / 2.46 / 2.56 | 2.46 (2.08) | 1.55 / 2.15 / 2.80 | 228 / 175 | 2.501 / 5.7 / - | 2.100 / 6.1 / - |
| 66 | W | inputs[7] | BB_Q_P | 2.409 / 2.009 | 6.8 / 7.4 | 2.06 / 2.48 / 2.57 | 2.48 (2.09) | 1.56 / 2.17 / 2.82 | 230 / 176 | 2.522 / 10.3 / - | 2.123 / 11.7 / - |
| 67 | W | inputs[8] | BB_I_N | 2.438 / 2.042 | 11.2 / 12.7 | 2.10 / 2.51 / 2.60 | 2.51 (2.12) | 1.58 / 2.19 / 2.85 | 232 / 178 | 2.559 / 14.9 / - | 2.164 / 17.1 / - |
| 68 | W | inputs[9] | BB_I_P | 2.482 / 2.091 | 15.5 / 17.7 | 2.14 / 2.55 / 2.64 | 2.55 (2.17) | 1.62 / 2.23 / 2.91 | 236 / 181 | 2.609 / 19.2 / - | 2.220 / 22.3 / - |
| 69 | W | inputs[10] | RF_RX_N | 2.539 / 2.156 | 19.6 / 22.5 | 2.21 / 2.61 / 2.69 | 2.61 (2.23) | 1.66 / 2.28 / 2.98 | 241 / 185 | 2.671 / 23.4 / - | 2.290 / 27.1 / - |
| 70 | W | inputs[11] | RF_RX_P | 2.608 / 2.235 | 23.5 / 27.0 | 2.29 / 2.67 / 2.76 | 2.67 (2.31) | 1.72 / 2.33 / 3.06 | 248 / 190 | 2.745 / 27.3 / - | 2.373 / 31.5 / - |
| 71 | W | vss_pads[1] | GND | 2.689 / 2.327 | 27.2 / 31.1 | 2.38 / 2.75 / 2.84 | 2.75 (2.40) | 1.79 / 2.40 / 3.16 | 255 / 196 | 2.830 / 31.0 / - | 2.468 / 35.6 / - |
| 72 | W | vdd_pads[1] | VDD_CORE_1 | 2.780 / 2.430 | 30.7 / 35.0 | 2.48 / 2.84 / 2.92 | 2.84 (2.50) | 1.87 / 2.48 / 3.28 | 263 / 202 | 2.925 / 34.4 / - | 2.574 / 39.3 / - |
| 73 | W | dvss_pads[7] | GND | 2.881 / 2.543 | 33.9 / 38.4 | 2.59 / 2.94 / 3.02 | 2.94 (2.61) | 1.95 / 2.57 / 3.40 | 273 / 209 | 3.028 / 37.6 / 3D>=3mm,plan>=3mm | 2.688 / 42.7 / - |
| 74 | W | dvdd_pads[5] | VDD_IO_3 | 2.991 / 2.665 | 36.9 / 41.6 | 2.71 / 3.05 / 3.12 | 3.05 (2.73) | 2.04 / 2.66 / 3.54 | 282 / 217 | 3.139 / 40.5 / 3D>=3mm,plan>=3mm | 2.811 / 45.7 / angle>45 |

### 4.6 JSON fragment and merge

- `scratch/pads-core/ws/bond-wire.json`: `wire_assumptions`, `current` (the table of 4.4), and `bonds` keyed by bond pad
  number "1".."74" with `site`, `signal`, `contact`, `finger_net`, `plan_mm` {C, N}, `angle_deg` {C, N}, `length_3d_mm`
  {min, nom, max, nom_near_end}, `L_nH` {min, nom, max}, `R_mohm_Al` {min, nom, max}, `R_mohm_Au` {min, nom, max} and
  `with_die_shift` {C, N: plan_max_mm, len3d_nom_max_mm, angle_max_deg, violations}.
- Merge script `scratch/pads-core/ws/merge_bond_wire.py`: adds `bond_wire` to each of the 56 `pins` and the 18
  `supplies_grounds` entries (matched by `bond_pad`, with a site-name assertion), and one top-level key
  `bond_wire_assumptions`. No existing key is changed (tested on a scratch copy: the result minus the additions equals
  the current spec file; 74 bonds merged). This also puts ground-bond lengths into the file, which power-delivery
  section 6 lists as missing. **Not run on the spec file.** Command, from the repository root:

```
python3 -I scratch/pads-core/ws/merge_bond_wire.py \
  projects/programmable_transceiver_platform/spec/package-channel.json \
  scratch/pads-core/ws/bond-wire.json \
  projects/programmable_transceiver_platform/spec/package-channel.json
```

## 5. COB production test through the pad ESD diodes

What is published [ANS, T]: every COB goes on a bond tester (`szfate/BondTest72`); each signal pad's ESD diode is measured
at 10 uA, 100 uA and 1 mA and reported OPEN or GOOD; power pads are tested by the charging curve of their capacitor.
**The polarity of the test current, the reference node, the compliance voltage and whether the die is powered are not
published.** Both polarities are therefore given.

Junctions at the pad, from the netlists (`diodes.py` -> `diodes.json`) [NET]:

| Pads | Bonds | Cell | Ground -> pad junction (pad negative) | Pad -> supply junction (pad positive) | Negative-current test | Positive-current test |
|---|---|---|---|---|---|---|
| D2H / H2D lanes and clocks, SPI, CLK_OBS, DBG_OBS0/1, spare `bidir[17]` | 1, 3-8, 10-17, 23, 38-45, 47-52 (30) | provider `bi_24t` (`clk_pad`: `in_s`) | yes: `nfet_06v0_dss` drains to DVSS | yes: `pfet_06v0_dss` drains to DVDD | GOOD | GOOD if the tester returns the supply pins; otherwise it charges the 8 x 1 uF |
| RESET_N, POR_BYPASS | 2, 22 | provider `in_c` | yes | yes | GOOD (strap: section 2) | as above |
| ATB0, ATB1 | 53, 54 | provider `asig_5p0` | yes: `diode_nd2ps_06v0` x4, 150 um2 each | yes: `diode_pd2nw_06v0` x4 to DVDD | GOOD | as above |
| RF_RX P/N, BB_I P/N, BB_Q P/N, WTX_EXT P/N | 69, 70, 67, 68, 65, 66, 30, 31 | `rf-pair` | **yes: 4 x `diode_nd2ps_06v0` (22.5 um2 each), anode VSS, cathode pad** | no: 4 x `diode_pd2nw_06v0` go to the isolated ESD_RAIL (about 10 Mohm bleed to VSS [REPORT], shunt off at DC) | **GOOD** | **OPEN / abnormal** (pad follows the rail up to the compliance voltage) |
| RF_TX P/N | 55, 56 | `rf-tx` | yes, same | no (ESD_RAIL) | GOOD | OPEN / abnormal |
| REF_IN / REF_IN_N, AUX_CLK P/N | 59, 60, 61, 62 | `reference` | yes, same; plus 12.5 kohm (`ppolyf_u_1k`) from each pad to its bias node | no (ESD_RAIL) | GOOD | OPEN / abnormal, possibly a resistive reading through the bias path |
| USB_DP / USB_DN | 24, 25 | `wired-receive-usb` | yes, same; plus NMOS drains (bulk VSS) | no: 8 x `pd2nw` to ESD_RAIL; PMOS drains go to floating n-wells | GOOD | OPEN / abnormal |
| WIRE_TX P/N | 28, 29 | `wired-transmit` | yes, same; plus cascode NMOS drains (bulk VSS) | no (ESD_RAIL) | GOOD | OPEN / abnormal |
| WIRE_RX P/N | 20, 21 | `wired-receive-hs` (published and staged b2) | yes, same, directly on the pad; the 4.9 pF MIM is between pad and RX, not between pad and diode | no: 8 x `pd2nw` to ESD_RAIL | GOOD | OPEN / abnormal |
| WMON | 32 | `single-leg` | yes, same | no (ESD_RAIL) | GOOD | OPEN / abnormal |
| TLP_TEST | 33 | `tlp-site` | yes: 4 x `nd2ps` | **yes: 4 x `pd2nw` to VDD** (ring supply) | GOOD | GOOD, as a provider pad |
| 8 supply pins | 18, 26, 35, 37, 58, 64, 72, 74 | provider `dvdd` | (DVSS -> DVDD `nd2ps` x4 per cell, 18 cells) | | capacitor charging curve: **all eight supply pads are one net on this die** [REPORT RAIL-CONTINUITY], so each pin shows its own 1 uF plus the other seven through about 0.5-0.8 ohm (two bond wires and the ring), about 8 uF in total, unless the tester drives all supply pins together | |
| 10 ground pins | 9, 19, 27, 34, 36, 46, 57, 63, 71, 73 | provider `dvss` | shorted on the board: not testable one by one | | | |

- Answer to the question asked: **yes, every custom pad family has a direct junction diode from VSS to the pad**
  (`diode_nd2ps_06v0`, n+ in the p-substrate, four per pad, on the pad net itself, not behind a resistor or a MIM). A tester
  that pulls the pad below ground reads a forward diode at all three currents. No pad is AC-coupled or MIM-only as seen
  from the bond wire.
- A tester that pushes current into the pad towards the supply finds no diode to the supply on 21 custom bonds (all custom
  pads except the TLP site): the up-diodes end on an isolated rail. That is by design and must be declared.
- Diode voltage values were not simulated (no circuit simulation in this task); a 90 um2 n+/p-substrate diode at
  10 uA - 1 mA is a normal 0.5-0.75 V junction.
- Unbonded sites: none, once the two west openings are not drawn (section 8). All 74 template pads are bonded.
- If candidate (b) of section 1 were taken, site 71 stays on a GND finger: invisible to the tester. If (a) were taken, the
  converted signal pad shows a diode in both directions to ground (back-to-back clamp): GOOD in either polarity. If P2
  were taken, finger 14 is tested as a signal and meets the supply net with about 8 uF: likely abnormal (section 3.3).
- **What to tell wafer.space** (they already say custom pads need user-specified tests [ANS, mole99]): an expected-result
  list per bond: 56 signal pads have a ground diode (pad negative); only the 34 provider pads and bond 33 have a supply
  diode; bonds 20, 21, 24, 25, 28-32, 55, 56, 59-62, 65-70 have none by design; all eight supply pins are one net on the
  die; bond 22 has a 105-157 kohm pull-down when the die is powered. Ask which polarity and compliance the tester uses.
- What to change if the tester turns out to be positive-only: nothing in the pads (a pad-to-VDD diode would defeat the
  stress-safe isolated rail); the list above is the fix. This is a reporting risk, not a functional one.

## 6. ESD implant layer 24/0

### 6.1 Layer identity [GDS / PDK files in the pinned image]

`/foss/pdks/gf180mcuD/libs.tech/klayout/tech/gf180mcu.lyp`: `ESD 24/0`, `ESD_MK 24/5`, `SAB 49/0`, `DNWELL 12/0`,
`NAT 5/0`, `RES_MK 110/5`, `FuseTop 75/0`, `FuseWindow_D 96/1`. LVS deck `layers_definitions.lvs`: `esd = polygons(24, 0)`,
`esd_mk = polygons(24, 5)`, `sab = (49, 0)`, `dnwell = (12, 0)`, `nat = (5, 0)`, `resistor = (62, 0)` (high-res implant),
`res_mk = (110, 5)`, `fusetop = (75, 0)`, `cap_mk = (117, 5)`, `polyfuse = (220, 0)`, `plfuse = (125, 5)`, `via5 = (82, 0)`.
The implant (24/0) and the ESD marker (24/5) are different layers.

### 6.2 Census [GDS]

Method (`esd_census.py`): per cell own shapes on the layer, multiplied by the instance count under each top cell; drawn
area without merging. 238 files: every `.gds` / `.gds.gz` under `analog/` (all block `generated/` directories, the pad
families `stress-safe-families/*`, `network`, `network-gc`, `network-gc-d2`, `network-shunt`, `shunt-v2`, `rf-tx/shunt`,
`protection-primitives`, `tlp-site`, older and candidate cells, `core_support`), `verification/digital_hardening`, the
staged `scratch/pads-core/agnd/pad_agnd_flat.gds` and `hspad/b2/pad_hspad.gds`, the assembly's scratch masters
(`island-support-20261108-075605/layout`, `core-bias-routing-20261110-compact`, `pad-compact`), the PDK IO library
`/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_io/gds/gf180mcu_fd_io.gds`, and the provider ring the assembly actually reads
(`inventory.py` `BASE_RING_GDS` = `analog/pads/generated/packaging-assembly.gds`, plus `provider-reference-ring.gds`).
Separately the last assembled chip, `scratch/chip-assembly-v5/run2/pt_chip_top.gds`.

| Where | ESD 24/0 shapes / area | ESD_MK 24/5 | Cells that draw it |
|---|---|---|---|
| All 22 custom bond pads' cells (rf-pair, rf-tx, reference, wired-receive-usb, wired-receive-hs + staged b2, wired-transmit, single-leg, tlp-site), networks, shunts, primitives, staged AGND pad | **0 / 0** | 0 | none |
| Every other block GDS (rf_rx, rf_tx, converters, timing, wired_rx, wired_tx, pll_vreg, core_support, decap, island_support, characterization, bringup_control, digital decap) | **0 / 0** | 0 | none |
| PDK IO cells `gf180mcu_fd_io__bi_24t`, `bi_t`, `in_c`, `in_s` | **0 / 0** | 2 shapes, 6,716-7,214 um2 per cell | `comp018green_out_paddrv_16T` / `_24T` (marker only) |
| PDK IO cells `dvdd`, `dvss`, `asig_5p0`, `cor`, fillers, breakers | **0 / 0** | 0 | none |
| Retained provider ring `packaging-assembly.gds` | **0 / 0** | 88 shapes, 307,954 um2 | the same `paddrv` cells (44 IO cells) |
| Assembled chip v5 (`pt_chip_top`, 48 layers present) | **0: layer 24/0 does not exist in the file** | 60 shapes, 209,946 um2 | `comp018green_out_paddrv_*` (30 provider IO cells) |

- Also 0 in the v5 chip and in every block: Via5 (82/0), MetalTop (53/0), FuseWindow_D (96/1), POLYFUSE (220/0),
  PLFUSE (125/5), i.e. all layers the open precheck PR #49 would forbid.
- Negative control: a synthetic GDS with a 2 x 3 array of a cell holding one 24/0 box and one 12/0 box is reported as
  ESD 6 shapes / 300 um2 and DNWELL 6 / 2,400 um2 (`control.py`).
- The devices one might expect to carry it do not: the gate-coupled shunt bank is plain `nfet_06v0` (50 um fingers,
  L 0.7 um); the diodes are `diode_nd2ps_06v0` / `diode_pd2nw_06v0`; the provider pad drivers are `nfet_06v0_dss` /
  `pfet_06v0_dss`, which are salicide-block (SAB) devices under the ESD_MK marker, without the implant.

### 6.3 What the implant is for, and what its absence means

- In GF180MCU the ESD implant is an optional extra implant for 5 V / 6 V NMOS used as snapback clamps (DRC: ESD.9 "only for
  5V/6V devices", ESD.7 "no ESD implant inside PCOMP", ESD.pl minimum gate length 0.8 um under it). Its usual purpose in
  such processes is to lower the drain junction breakdown, so that the parasitic bipolar triggers earlier and more
  uniformly, and to raise the failure current It2. That is general process knowledge, not something the open PDK
  documents or models: confidence medium.
- (i) Provider IO cells: they do not draw 24/0 [GDS], so the mask layer cannot contribute to their ESD behaviour as drawn.
  Their protection is SAB-ballasted `_dss` drivers plus the RC clamp in each `dvdd` / `dvss` cell (plain `nfet_06v0`,
  4 mm). Whatever HBM level these cells reach on wafer.space silicon, they reach it without the implant. No public HBM
  figure for them was found; the project "relies on the provider qualification for all provider pads" (README), and that
  reliance is neither helped nor hurt by this finding. Unknown that remains: whether GF's original qualification of this
  IO library used a mask flow that derives an implant from the ESD_MK marker; wafer.space says the layer is not in their stack either way.
- (ii) Custom pads: by design (README PD13 / PD21 / PD48, `esd-tiering.md`) the discharge path is forward-biased junction
  diodes (pad -> isolated ESD_RAIL through `diode_pd2nw_06v0`, VSS -> pad through `diode_nd2ps_06v0`), the gate-coupled
  6 V NMOS shunt from ESD_RAIL to VSS working as a MOS switch, and the RC clamp. In the published HBM surrogate runs the
  pad stays at 5.0-6.9 V [REPORT README], below the junction breakdown of 6 V devices, so **no path depends on snapback or
  avalanche breakdown, and none uses a device that the implant would modify**. Nothing draws 24/0, so the fabricated
  devices are exactly the ones simulated as far as this layer is concerned.
- Models [PDK `sm141064.ngspice`]: the string "esd" does not occur in the model file. `nfet_06v0_dss` / `pfet_06v0_dss`
  are sub-circuits of the same `nfet_06v0` / `pfet_06v0` model cards with `nplus_u` / `pplus_u` SAB resistors in series
  with drain and source (`d_sab` 3.78 / 2.78 um); there is no separate model card and no implant effect anywhere. Our
  custom-pad netlists contain no `_dss` device [NET]: `nfet_06v0`, `pfet_06v0`, `nfet_03v3`, `pfet_03v3`, the two diode
  models, poly resistors and MIM only. The simulations cover MOS conduction and diode forward drop; snapback is not
  modelled at all (already recorded in `esd-tiering.md`), with or without the implant.
- The LVS deck excludes anything under 24/0 from MOS, MOS-capacitor, diode and BJT recognition (`mos_exclude`,
  `diode_exclude` contain `esd`), and recognises the SAB MOS from `ESD_MK` (24/5), `SAB` and `LVS_Source`. A device drawn
  with the implant would not extract as a PDK device, which is consistent with nobody using it.

### 6.4 Conclusion per pad family

| Family / cell | Draws 24/0 | Relies on snapback or breakdown | Evidence (HBM-like sims, DRC, LVS) if the implant mask does not exist |
|---|---|---|---|
| `rf-pair` (RF_RX, BB_I, BB_Q, WTX_EXT) | no | no | **unaffected** |
| `rf-tx` | no | no | unaffected |
| `reference` (REF_IN, AUX_CLK) | no | no | unaffected |
| `wired-receive-usb` | no | no | unaffected |
| `wired-receive-hs` (published, staged b2) | no | no | unaffected |
| `wired-transmit` | no | no | unaffected |
| `single-leg` (WMON) | no | no | unaffected |
| `tlp-site` | no | no (diodes to the ring rails) | unaffected |
| `network`, `network-gc`, `network-gc-d2`, `network-shunt`, `shunt-v2`, `rf-tx/shunt`, primitives, staged `pad_agnd_flat` | no | no | unaffected |
| Provider IO cells (`bi_24t`, `in_c`, `in_s`, `asig_5p0`, `dvdd`, `dvss`) | no | the `_dss` drivers and the RC clamp can enter snapback in a real event; this is the provider's design | **unaffected by the mask question** (the layer is not drawn); absolute ESD level unknown, as before |

What stays unknown is unrelated to the layer: there is no silicon ESD data, the models have no snapback, and the plain
salicided `nfet_06v0` shunt has no ballast if it were ever driven into breakdown (the TLP site exists to measure this).

### 6.5 DRC side

- Rule deck `drc/rule_decks/esd.rb`: ESD.1-ESD.10 and ESD.pl all constrain existing 24/0 shapes (width, spacing, overlap
  of COMP, Dualgate coverage, LVS_IO coverage). **No rule requires the layer**, so its absence raises nothing.
- Other decks mention it only as an exclusion (efuse EF.18 / EF.20 keep-outs, off-grid check). The SAB rules that
  mention ESD use the marker: SB.12 ("overlap with Poly2 outside ESD_MK") and SB.16 (SAB on core transistors only under
  LVS_IO, OTP_MK or ESD_MK). Our cells have no SAB on any MOS (section 7), so SB.16 does not apply to them.
- The open precheck PR #49 forbids the layer named `ESD`. With 0 shapes on 24/0 the die passes it. If the check were
  written against 24/5 it would reject wafer.space's own template IO cells, so it must mean 24/0 [I]; one line in the email settles it (follow-up 6).

## 7. Deep n-well, SAB, NAT and the other optional layers [GDS]

Full per-file, per-top-cell table: `census-table.md` (109 rows; shapes / drawn area; for SAB what it lies on). Summary of
the published cells (older and candidate cells left out):

| Layer | Where it is used | Shapes / drawn area | Devices |
|---|---|---|---|
| **DNWELL 12/0** | `rf_tx/generated/rfdriver.gds` (`pt_rfdriver`) only | 2 shapes, 954.75 um2 | 48 NMOS gates (134 um2 of gate, 3.3 V: no Dualgate) inside the two wells, with 159 um2 of n-well ring. No other block, no pad, no provider cell. The assembled v5 chip has no 12/0 at all (it predates this driver) |
| **NAT 5/0** | `pll_vreg/generated/pt_pll_vreg.gds` (60 shapes, 47,299 um2), `pt_pll_vreg2.gds` (2, 41,092 um2), `pt_vreg_pass/pt_vreg_pass.gds` (1, 19,509 um2) | 63 / 107,901 um2 | `nfet_06v0_nvt` pass devices: 60 / 120 / 60 gates, all under Dualgate. Not in the v5 chip |
| **SAB 49/0** in our pad families | each family: 155-297 shapes, 36,600-40,900 um2 (hspad 37,186; wirepad 40,907; refpad 37,255; txpad 37,266; rf-pair / rf-tx / single-leg 36,626); `pt_hs_leg` 280 um2; `tlp-site` and the two primitives: none; staged AGND pad: none | | **poly resistors only**: 11,240-12,720 um2 of unsalicided poly (`ppolyf_u`, `ppolyf_u_1k`: bleed, RC trigger, ATB and discharge resistors); **0 gates touched, 0 um2 on COMP** |
| SAB in other blocks | rf_rx 17,174 um2 (bbfilter 6,710 each, bb_tap 1,261, lna 1,048, rxmix 722 each); timing 26,109; core_support 29,746; pll_vreg 13,728; wired_rx 3,637; rf_tx 1,764; wired_tx 1,548; converters 1,026; characterization 597 | | poly resistors only (0 gates, 0 COMP in every one) |
| SAB in the provider IO cells | `bi_24t` 38 shapes / 5,012 um2; `bi_t`, `in_c`, `in_s` 35-38 / 4,247-4,258 um2; `dvdd`, `dvss` 13 / 2,025 um2; `cor` 26 / 4,051 um2 | | `bi_*`, `in_*`: **20 MOS gates per cell (8 n, 12 p) with SAB on the drain** = the `nfet_06v0_dss` / `pfet_06v0_dss` pad drivers (`comp018green_out_drv_nleg_*`, `pmos_6p0_esd*`), 2,700-3,400 um2 of SAB on COMP, plus poly resistors; `dvdd` / `dvss` / `cor`: the RC-clamp poly resistors only |
| SAB, assembled v5 chip | 4,754 shapes, 693,517 um2, 99 owner cells | | as above |
| HRES 62/0 (`ppolyf_u_1k`) | pads 18,100-20,600 um2 per family; rf_rx 11,553; timing 15,998; core_support 15,844; pll_vreg 8,269; wired_rx 2,765; converters 649; rf_tx 500. v5 chip: 691 shapes, 251,792 um2 | | 1 kohm/sq poly resistors (option confirmed, [ANS, T/S]) |
| RES_MK 110/5 | with every resistor; v5 chip 4,352 shapes, 424,063 um2 | | marker |
| MIM: FuseTop 75/0 with CAP_MK 117/5 | pads 17,395-22,295 um2 per family (hspad 22,295 incl. the AC-coupling caps), `rf-tx/shunt` 16,200; rf_rx 95,388; converters 73,966; core_support 21,566; timing 18,651; characterization 6,400. v5 chip: 452 shapes, 573,225 um2 (incl. 20 `decap_mim_unit`) | | `cap_mim_2f0_m4m5_noshield` (option B, 2 fF/um2 [ANS, T/S]); MIM_L_MK 117/10: none |
| ESD_MK 24/5 | provider IO cells only (section 6) | | marker |
| GUARD_RING_MK 167/5 | seal ring in `packaging-assembly.gds` and the v5 chip, 1 shape | | required by PR #49 |
| Via5, MetalTop, FuseWindow_D, POLYFUSE / PLFUSE, LDMOS_XTOR, MVSD, MVPSD | none anywhere | 0 | |

Consequences for the email to wafer.space: the only uses of the options without an explicit statement are DNWELL (one RF
driver) and NAT (the PLL regulators' native pass devices); SAB is used exactly as in the provider cells (poly resistors),
never on a custom MOS; `_dss` devices occur only inside the provider cells.

## 8. Fill and pad openings

Every one of the 74 template sites carries its 60 x 60 um opening in the cells we place (provider cells and all custom
families; shown in `BOND-AUDIT.md` on the mini-assembly and on the v5 chip: 74 openings, largest centre offset 0.5 um), so
the precheck's golden-mask test (template openings must exist; extra ones "are fine" [ANS, P]) is met without the two west
openings. Since nothing beyond the 74 wires is bonded, the two extra west openings would be bare aluminium pads under the
glob-top with no function: an un-bonded, un-testable AGND net, 16.5 um from the RF_RX_P opening at the placeholder
position, a cell that does not exist in any floorplan, and one more thing for the fill, antenna and LVS runs to handle.
**Recommended now: do not draw them.** Consequences: none for the precheck, for the fill (the fill script treats the pad
ring as it does today), or for the bond tester (no unbonded pad remains); the two placeholders
(`pad_lna_src_p` / `pad_lna_src_n`, 124 x 68 um each) leave `floorplan-v6.json`; the staged `pad_agnd_flat` stays
unpublished and is only needed, re-pitched onto the template opening of site 71, if candidate (b) is ever chosen.

## For the owner: decisions and rows

### Proposed decisions

1. **LNA ground: no split in the pad ring (candidate (c)); runner-up (b), site 71 `vss_pads[1]` on its own net.** (a)
   rejected. Delete the two west extra openings. Condition under which the runner-up should replace (c): section 1.6.
   Confidence medium: lumped model, pad capacitance estimated, LNA capacitance unknown.
2. **P2: drop.** `bidir[17]` stays a bonded provider `bi_24t` spare (free for a debug signal). Runner-up: keep P2 if a
   power-delivery re-run with 0.21-0.28 ohm bonds still shows a bond or cell above about 80 % of its limit. Confidence medium.
3. **POR strap: as decided**, nothing to change.
4. **Bond landing:** ask wafer.space (below); internally record that the corner bonds are at or over 3 mm of wire for
   centre landing and that 0.1 mm of die shift breaks one rule in either landing model.
5. **Merge `bond-wire.json` into `spec/package-channel.json`** with the command in 4.6 (owner runs it).

### `spec/contract.json` `assembly_policy.bond_map_current`: proposed text (not edited here)

- `west`: delete the key `"extra pad openings beside RF_RX (no board finger)"`. If (c): add to `note`: "No AGND_RX pad:
  the COB bonds only the 74 template pads (wafer.space answers 2026-11-14); LNA ground is die VSS; rejection per PD2-15."
  If (b) instead: add `"vss_pads[1].pad": "AGND_RX (LNA ground, own on-die net; custom pad_agnd on the template opening;
  bond 71 to its GND finger; not tied to the ring DVSS/VSS except through the back-to-back clamp)"`.
- `east`: `"bidir[17].pad": "spare (provider bi_24t, bonded, contact 57); P2 dropped 2026-11-14 (no dynamic benefit, DC
  benefit 4 mV per 100 mA on the D2H row)"`.
- `retired`: add "AGND_RX extra openings W-A / W-B (not bondable: fixed 74-wire COB layout)" and, if dropped, "option P2".
- `sources`: add `scratch/pads-core/ws/REPORT.md`.

### Rows (text for `scratch/reviews/interface-changes.md`)

- **To rf_rx (supersedes PC-19 items a/b, amends PD2-12):** "The two AGND_RX down-bond pads cannot be bonded (COB: 74
  fixed wires, no down-bonds, no double bonds). Options with the 74 fingers: a signal site as ground returns through
  4.9-7.5 nH (trace, connector, carrier) and gives -10 to +4 dB at 2.42 GHz with pad capacitance alone, gain with more:
  rejected. Ground site 71 (`vss_pads[1]`, 211 um from RF_RX_P) on its own net returns through 1.9-3.5 nH and gives
  8-20 dB (11-17 dB at nominal L) with 0.21-0.36 pF, 7 dB at 0.5 pF, none above about 0.8 pF total AGND_RX-to-VSS capacitance, and removes
  the die-VSS bond nearest the LNA. Pads' recommendation: no split; the LNA takes die VSS. Each RF_RX pad already couples
  die VSS onto the input through its four ground diodes and pad plate, and `pt_lna` has no deep n-well. Needed from rf_rx
  (PD2-15): extracted AGND_RX-to-VSS capacitance and the rejection from die VSS with and without bond 71 as AGND_RX; if
  that shows at least 10 dB net, pads builds the site-71 cell."
- **To power delivery (amends section 5.2, section 6, PD2-12):** "(1) No AGND_RX bond exists; section 5.2's decision
  cannot be built as written; ten die-VSS bonds remain unless rf_rx asks for site 71 (then nine: 0.231 -> 0.255 nH in
  parallel, and bond 73 alone next to the LNA). (2) Bond wire is 0.8 mil AlSi: 211-282 mohm per bond (Au 162-217), not
  0.13 ohm; 87.5 mA drops 25 mV in bond 18; re-run `e7_static_v7.py` with the per-bond values in
  `scratch/pads-core/ws/bond-wire.json` (ground bonds included). (3) Wire limits: design maximum 0.34 A (Al), 0.46 A (Au);
  a clamp event of 3 A for 3 us per bond is 1 % of the fusing I2t. (4) P2: a supply bond on signal finger 14 has 8.1-8.7 nH
  to its first capacitor against 4.0-4.6 nH for a supply finger with its 0201; all supply paths 0.54 -> 0.51 nH; D2H ring drop
  18.2 -> 14.3 mV per 100 mA (Al). Pads proposes to drop P2. (5) The eight supply fingers each have 1 uF on the COB,
  about 2 mm from the finger: the PDN model should use bond + 1.0-1.5 nH of trace + via + capacitor per supply bond.
  (6) Converting site 71 would remove one of 18 RC clamp cells."
- **To chip-top / assembly:** "No pads at the two west extra openings: remove `pad_lna_src_p` / `pad_lna_src_n` from the
  floorplan; 74 openings exactly. `bidir[16]` = `pad_por_bypass` (`in_c`); `bidir[17]` keeps a provider `bi_24t`. No
  `dvdd` cell at `bidir[10]` (P2 dropped). ESD implant layer 24/0: 0 shapes in every published block and in the v5 chip;
  add a census of 24/0, 82/0, 53/0, 96/1, 220/0 = 0 to the assembly checks (`scratch/pads-core/ws/esd_census.py`).
  DNWELL appears only in `pt_rfdriver`, NAT only in `pll_vreg`. If site 71 is ever converted: `dvss` cell replaced by the
  rail cell plus `pad_agnd`, the core-ring VSS strap at that site goes, rail continuity to be re-measured."
- **To board / carrier:** "No change to the 74-finger COB is assumed. Contact 58 = POR_BYPASS strap (open or jumper to
  3.3 V). Contact 57 = spare signal. Contact 66 stays HOST_CS_N (P2 dropped). Supplies: 1 uF 0201 already on the COB per
  supply net; the carrier adds bulk and damping, not the first capacitor. Bond wires: 2.0-2.7 nH and 0.21-0.28 ohm each
  (Al). Production bond test: 21 custom pads have a ground diode only (list in section 5); all eight supply pins are one
  net on the die."
- **To integration / signoff:** "Precheck PR #49 (forbidden layers) is satisfied as the blocks stand; the open risk
  moves from 'our ESD cells may lose an implant' to 'none'. `spec/package-channel.json` can take per-bond 3-D length,
  L and R with `merge_bond_wire.py`."

### wafer.space follow-up questions that remain (short list for the email)

1. Bond test: which polarity, reference node and compliance voltage does the diode test use, and is the die powered?
   Can we supply an expected-result list (21 custom pads: ground diode only; eight supply pins common on the die)?
2. May the cell at a template GROUND site be a custom pad on its own on-die net, as long as the pad stays at 0 V on its
   GND finger (site 71)? (Only needed if the runner-up is chosen.)
3. Is a customer-modified 1x1 COB accepted for Run 3 (same outline, fingers, connector, passives area; changed ground
   copper near two fingers; extra 0201 / 0402 on the top)?
4. Wire for Run 3: aluminium or gold, diameter; loop height; die placement tolerance in x, y and rotation.
5. Are 3 mm and 45 deg plan-view limits, where on the 1.0 mm finger does the wire land, and are the end-of-row pads
   relaxed? (Corner bonds: 2.991 mm plan, 3.05 mm of wire at centre landing; 44.0 deg at near-end landing.)
6. Is it layer 24/0 (ESD implant) that is dropped, not 24/5 (ESD_MK)? Written confirmation of DNWELL (12/0) and NAT (5/0).
7. Final die thickness and die attach (conductive or not) for Run 3; glob-top material.
8. Current rating of a connector contact (HCTL HC-PBB40C-70DP-0.4V-02).
9. Do the stock `dvdd` / `dvss` cells tie all supply pads together on other customers' dies too, i.e. is an 8 uF
   charging curve on each supply pin a known pattern for the tester?

### Confidence summary

- Measured in GDS / netlists (high): sections 5 (junctions), 6.2, 7, the finger-class check, the plan geometry.
- Computed from published or measured inputs with stated assumptions (medium): wire lengths in 3-D, L, R, current
  capability, P2 numbers, the die-shift results (the rotation value is assumed).
- Estimates (low to medium): pad capacitance of an AGND pad, connector and carrier inductance, the divider as a
  predictor of LNA isolation, the tester's behaviour.
- From Discord statements that can change: wire type, die thickness, fixed bond layout, tester description.
