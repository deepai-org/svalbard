# Independent review of `offchip-passives.md` (2026-11-14)

Adversarial, read-only. Hand calculations and greps only; no simulation, no layout run. `P` =
`projects/programmable_transceiver_platform`. "Not verified" = I could not check it from the repo.

## 1. Verdicts

| item | claimed mm2 | verdict | mm2 I would book | main reason |
|---|---:|---|---:|---|
| OCP-1 loop-filter C2 off-chip | 0.14-0.15 | **survives with conditions** | 0.12-0.15 | electrically sound only as an ADJACENT provider pad pair; the section 6 pad allocation and pad option (a) both violate that |
| OCP-2 WTX_EXT on the USB pad | 0.151 | **broken as written, repairable** | 0.10-0.15 | termination kills the receiver's self-bias; "USB HS has no WTX_EXT path" is false; island crossing; WMON shares the deleted pad's protection macro |
| OCP-3 QVCO regulator passives off-chip | 0.10-0.15 | **broken** (step 1 pads and step 2) | 0 against the ledger | AUX_CLK is not idle and its Q-leg function breaks; G2 is a 0.14-0.29 uA node; the regulator is already laid out at 0.44 mm2, not 0.30 |
| OCP-4 USB FS/LS receivers in the FPGA | <= 0.01 | survives, not worth a row | 0 until the owner sizes it | arithmetic right; saving unquantified |
| OCP-5 ADC VCM capacitor on ATB0 | 0.003 | **broken** | 0 | 6.2 kohm of ATB switches in series; does not fix CNV-06; costs ATB0 in RX |
| OCP-6 REXT on a bias pad | 0 | **broken as described** | 0 | `pt_bias_ext` is not a resistor tap; ATB path adds 6 kohm uncontrolled |
| B-1 TX Thevenin termination on the COB | 0.06-0.09 | survives with conditions, L | 0.058 (C) / 0.088 (B) | pad C is 1.8-2.7 pF, not 1.5: resonance at 1.77 GHz; receiver-detect not checked |
| B-2 RX TERM_VCM by COB resistors | 0.01-0.02 | survives with conditions, L | <= 0.02 | loses the 4-bit trim; detect common-mode range not verified |
| 5.4 decap rejection | 0 | **rejection survives** | | board capacitance is behind the bond inductance; one competing use of freed sites noted |
| 5.2 termination rejection (case A) | 0 | **rejection survives** (stronger than stated) | | with the real TX pad C the resonance is at 1.2 GHz |
| 5.1 USB rejections | 0 | **rejection survives** | | 0.005 mm2 of passives; FS drivers are needed by HS (reset, resume) |
| 5.6 USB on WIRE_TX/RX (R-10), AUX on BB_Q (R-11) | 0 / 0.044 | **rejections survive** | | PD21 / PD45 numbers; 0.195 - 0.151 = 0.044 |
| 5.3 `pll_vreg2` gate capacitor (R-8) | 0.03 | rejection survives | | and the same objection applies to OCP-3 step 2, which the pass accepted |
| 5.5 RF inductors | 0 | rejection survives | | a custom pad pair (0.151) costs more than the spirals it would replace |

Net of this review: **OCP-1 + OCP-2 = 0.22-0.30 mm2 at best, OCP-3 = 0**, and the baseline is 0.14 mm2 worse than
the ledger because of the regulator (section 4.2).

## 2. OCP-1 (C2 to the carrier): survives with conditions

Arithmetic rechecked and correct: zero 1/(2 pi 10.38k x 489.6p) = 31.3 kHz; poles 2.81 MHz (R, C1) and 1.80 MHz
(R3, C3); bond resonance 1/(2 pi sqrt(16 nH x 470 pF)) = 58.0 MHz; spur 20 log(Kv V / 2 fm) = -51.4 / -35.6 dBc for
60 / 370 uV; -40 dB for 5 pF / 490 pF; leakage 10 nA -> 2 ps; 3.3 V x 10 fF / 490 pF = 67 uV. Topology confirmed in
`P/analog/timing/lo_lf.spice` (CP - R - X - C2 - VSS). The 5 pF stray is conservative (I get 1.5-2.5 pF from the
package-channel chain). Additional mechanisms I checked and found harmless: ring-DVDD ripple through the pad's upper
diode (about 1 pF) at 78 / 156 MHz gives < 0.3 uV at VTUNE (< -135 dBc); leakage up to 100 nA is still only -108 dBc at
50 MHz and 20 ps offset, so the 5 nA board requirement in B49 has 20x margin.

What does not hold:

1. **The pads.** The Kelvin argument needs X and its return on neighbouring bonds and one coplanar pair.
   - Section 6 allocates `LO_AGND` to AUX_CLK_P (west) and `LO_X` to an east provider site. Then C2 sits between
     contacts on opposite sides of the connector and each trace forms its own loop with the carrier plane. Hand
     estimate for PA return current under 20 mm of trace 0.1 mm above the plane: M about 0.06 nH, EMF at 18 mA /
     1 MHz about 7 uV in series with C2: **-70 dBc**, i.e. the -80 dBc basis fails at the pessimistic envelope
     (-86 dBc at 3 mA). Section 6 contradicts section 4 / B49 ("routed as a pair").
   - Option (a) puts X on east `bidir[17]` and the return on north ATB1: same split, and the return goes through the
     ATB path, which is `atb_pad` 0.59 k + `atb_grp` 1.17 k + force leaf 4.4 k = **6.2 kohm functional max**
     (`P/analog/island_support/README.md:253-258`). In series with C2 that takes R from 10.38 k to 16.6 k: zero
     31 -> 20 kHz, fc about 300 -> 480 kHz, phase margin 78 -> about 57 deg, with a PVT-dependent switch. The pass
     rejects "ATB as X" for exactly this bus and then uses it as the return. (a) also takes `bidir[17]`, which PC-18
     holds for supply option P2 (worst supply bond 87.5 -> 63.5 mA).
   - So only option (b) works, and it depends on OCP-2 freeing `bidir[22]/[23]`.
2. **Provider cell at those sites: not verified.** No `asig_5p0` has been placed at a `bidir` site; its leakage
   below VDD, pad capacitance and HBM clamp level are not in the repo (AP4-7 lists them as open). The only number,
   `atb-provider-pad-force.json`, is forward conduction at 3.63 V against a 3.15 V rail (27 nA tt, 3.7 uA ff/85 C).
3. **HBM.** CP carries 3.3 V charge-pump drains and the 6 V-rated C1 MIM; R x C1 = 57 ns is shorter than the HBM
   decay, so CP follows the X clamp (6-7 V in the proposal). Needs `hbm_core_screen.py`; a 3.3 V device on a pad
   net failed that screen everywhere else (PD29).
4. **Route resistance.** 3 mm of 1 um Metal2-4 is about 270 ohm per wire; X and return together add about 5 % to R,
   plus the 200 ohm series resistor (2 %). Acceptable, but it is not "100 ohm = 1 %".
5. **Area.** `pt_lo_lf` is at 0.95 utilisation (`area-pass-4.md:53`). The C2 marker is exactly 85 x 1600 um2 =
   0.136. Guaranteed: 0.136 - 0.02 channel = 0.116. The 0.14-0.15 needs the remaining 0.058 repacked to 0.02-0.03.

Conditions: adjacent provider pair `bidir[22]/[23]` (so OCP-2 must land first), no shared return with anything
else, wire R <= 300 ohm total, asig leakage <= 100 nA at 3.0 V / 85 C and HBM screen clean, user accepts that an RF
carrier without C2 has no on-chip LO.

## 3. OCP-2 (WTX_EXT on the USB pad): broken as written

1. **The termination kills the receiver.** `ct_rxin` is a DC-coupled inverter whose gate is the input
   (`P/analog/timing/generated/fast/ct_rxin.ext.spice:3-14`); it works only because the pad is high-impedance and the
   40 kohm feedback sets the gate to the inverter threshold. The proposal terminates with the USB pad's 45 ohm to
   `TERM_VCM` at 1.2 V or VSS. 45 ohm against 40 kohm pins the input 0.2-0.45 V (1.2 V) or 1.5 V (VSS) from
   threshold; B12 amplitude is 75-200 mV per leg. Dead at VSS, dead or duty-distorted at 1.2 V. It can only run with
   the termination off, as today on the rf pair. The 2.9 GHz pole calculation is then irrelevant.
2. **"USB HS has no WTX_EXT path today" is false.** USB HS data is `wiredtx.CMD_MAIN`
   (`P/analog/wired_tx/USB-INTEGRATION.md:14,30`), which is what DX feeds, and the only extracted USB HS transmit
   evidence was run through the external-data path (`USB-INTEGRATION.md:126-130`, `hs_ext_*_wtxext`). With OCP-2 the
   external data would enter on the pad it has to leave on. Lost: external-data fallback for USB HS TX. MANDATE
   l.159 keeps "fallback access on every carrier". User decision, not a free consequence.
3. **Island crossing.** `rx_wtx_ext` is on `RAIL_debug`; `pad_usb` is on `RAIL_wired_tx` and `URX_P/N` feeds
   wired_rx blocks (`P/integration/top/pt_chip.conn:218-219, 381-382, 416-424`). In normal USB use with the debug
   island off, the receiver's unpowered devices hang on the USB receive node. Move `rx_wtx_ext` to the wired island
   or require debug on.
4. **WMON loses its protection macro.** `pad_wmon` uses `ESD_RAIL_wtx_ext` (`pt_chip.conn:203-206`), and the
   scenario C target for WMON (0.0998) is the undrawn B cell that borrows the WTX_EXT pair's macro
   (`P/analog/pads/README.md:353-357`, ledger row `pad_wmon`). Without lever 1, deleting `pad_wtx_ext` returns WMON
   to 0.147: OCP-2 is worth **0.104, not 0.151**. With lever 1 (WMON on a provider cell) 0.151 holds.
5. **Wrong loading numbers.** With the bypass on (which the proposal needs) the pad is 2.08-3.37 pF, not 2.34-2.35
   (PD45 / PD47). The 2.7 pF limit quoted was replaced by 5.0 pF for USB (PD47), so that check passes; the error is
   in the proposal's favour. Bandwidth of the bypass path to 800 MHz (2 x 20 um transmission gate into about 1 pF of
   `rxselect` + `detect` + `wmon_sel` + the new receiver) is not in evidence; USB HS needs only 240 MHz.
6. **Self-bias leakage.** The pad now idles at about 1.5-1.65 V. The custom shunt is < 1 uA up to 1.65 V
   (`README.md:309-313`); 1 uA through 40 kohm is 40 mV of offset. Any DC path in `detect` / `rxselect` on `URX`
   adds to it. Not verified.
7. The receiver itself already fails from 0.5 Gb/s (TIM-08, `P/analog/wired_tx/INTEGRATION.md:24`; mode-walk 6.3).
   "0.5-1.6 Gb/s kept" rests on a block that does not work at any pad yet.
8. A plus the pass did not claim: behind the wirepad's bypass the receiver probably clears the PD29 HBM failure it
   has on the rf pair (6.91 V on a 3.3 V gate). Needs the rerun.

The alternative of putting WTX_EXT on the AUX_CLK pair (same receiver cell already there) is blocked: the forwarded
clock is on AUX and "both fallbacks run together" (`consolidation-pass-4.md:164,191`).

## 4. OCP-3 (QVCO regulator): broken

### 4.1 Step 1, `LO_CEXT` / `LO_AGND` on the AUX_CLK pair

- **AUX_CLK is not idle in RF modes with the on-chip LO.** It is a selectable source for the converter sample
  clock, the ring-PLL reference and the wire clock (`P/analog/timing/README.md:86-90`). The section 3 table marks it
  "-". A 10 uF on it removes the fallback clock input on that RF population.
- **External-LO Q leg.** A 3 mm PMOS adds about 3 pF to AUX_CLK_N and the NMOS 0.5 pF to AUX_CLK_P; the refpad
  class is about 0.5 pF today. 3.5 pF with 2.5 nH resonates at 1.7 GHz (1.06 GHz with 6.5 nH), below 2.45 GHz: that
  leg is past resonance (about -13 dB and inverted) while the other is near resonance. This is per leg inside one
  pair, not a level offset between pairs, so B31 / BP-7 cannot absorb it. The fallback LO breaks on the die, not on
  a population. PC-18 already has an open I/Q condition on these pairs.
- **Series resistance.** The owner swept bond R 0.05 / 0.4 ohm only. A 1 ohm switch against a follower output of
  about 4 ohm limits the capacitor's benefit to 13 dB: 36.2 + 13 = 49.6 dB at 1 MHz at the operating points (limit
  50), and 78.125 MHz falls to about 39.5 dB against 40 (LO21 basis) at ff. Bond-to-core resistance of the refpad is
  not stated anywhere; the txpad family has 8.3 / 11.7 ohm (`pads/README.md:407`).
- **BYP mode.** VOUT is then VIN - 0.1 V = 3.2-3.5 V on a custom pad whose shunt draws 0.44 mA tt / 5.1 mA ff at
  3.3 V and up to 28.6 mA at 3.63 V (`README.md:309-313`) through a 30 mA island switch designed for 28.1 mA.
  "BYP mode unchanged" is wrong unless the pad switch opens in BYP.
- The west side has no provider analog site, and an east site is 3 mm from a 25 mA regulator output. `LO_CEXT` has
  no workable pad in this plan.

### 4.2 Step 2, gate capacitors on pads

- **G2 is not a 2.6 kohm node.** It is driven by an OTA with 2 x 0.14 uA tails, output limited to 0.29 uA, gm
  0.4 uS, integrating on 12.8 pF (`scratch/lo-ap4/vreg2/NOTES.md`, "Circuit"). With 100 nF: slew 2.9 V/s, start-up
  of the order of 1 s (today 2.4-5.3 ms), unity-gain frequency 145-285 Hz -> below 1 Hz. 10 nA of pad or board
  leakage is 25 mV at the OTA input, about 55 mV at VOUT; 0.3 uA stops the regulator. Changing only the filter
  resistor does not address this; it needs a new OTA.
- **The 35 dB per stage does not survive the route.** 3.9 ohm at the gate needs the 3 mm wire to be a few ohms
  (about 10 um of top metal per gate). At 1 um it is about 270 ohm against 227 ohm of Cgd: about 1 dB. If the 2.6 k
  is placed between pad and gate "for ESD", the gate sees only the on-die 10-20 pF: 20 / 9 = 7 dB per stage, worse
  than today's 21 dB. Without it a 6 V native gate is directly on a pad.
- **Resistors.** Only RF1 and RF2 (5.2 Mohm) go, of about 10.4 Mohm in the cell: about 0.03, not "nearly all of
  0.059".
- **Area baseline.** The regulator is no longer "never built": NOTES "Layout" gives the staged top cell as
  **407.16 x 1081.62 um = 0.440 mm2**, DRC 0, LVS unique. The ledger books 0.300. Removing 0.08 + 0.03 gives about
  0.33, still above the ledger. The "+ OCP-3" column in section 6 (-0.20 to -0.25) is unsupported, and every
  scenario is 0.14 worse than die-fit states until the cell is re-laid out.
- R-8 rejects the `pll_vreg2` gate capacitor for "a megohm node on a bond"; that is the same objection.

## 5. OCP-4, OCP-5, OCP-6

- **OCP-4.** 1 k x 8 pF = 8 ns and 45 || 1000 = 43.1 ohm (-4.3 %, only above 20 MHz) are right. The calibrated
  range is 41.35-49.06 ohm ("thin at ss"); -4 % at the low end is 39.6 ohm against 40.5. Saving is not measured.
  Survives as a note.
- **OCP-5.** The VCM problem (MW-6a, `interface-changes.md:1378`) is settling in about 5 ns from a 20 kohm source.
  A capacitor behind 6.2 kohm of ATB switches lowers the source to 4.7 kohm: still does not settle, so the booked
  buffer or an on-die capacitor stays. Saves nothing and occupies ATB0 in receive.
- **OCP-6.** `pt_bias_ext` is a bank of 10 uA bias outputs (`P/integration/top/decisions.md:12`), not an external
  resistor input. Through the ATB path a 12.1 k resistor has up to 6.2 k of switch in series, so +-1 % is not
  reachable. The existing SMU trim already gives about +-5 % (`P/analog/core_support/README.md:430-437`).

## 6. Case B

- **B-1.** The TX pad is 1.80 pF (comparison model) to 2.71 pF (recorded), not 1.5 pF. With 2.7 pF and 3 nH the
  resonance is 1.77 GHz and peaking at 1.62 GHz is about +3 dB (Q 1.33); with 1.5 pF I reproduce +3.7 dB. A fixed
  Thevenin cannot be switched off: TMDS carriers must not fit it, and the TX-side receiver detect (`DETECT_ENABLE`)
  against a permanent 50 ohm to 1.65 V is not checked. On scenario C the gain is 0.058 (term_buffer is already at
  its 0.045 target), 0.088 on B. The COB is the provider's fixed board (MANDATE l.76-86: two strips, 8 x 0201,
  supply to GND only), so this needs a different COB, not only permission.
- **B-2.** Plausible for AC-coupled protocols; loses HS_TERM_TRIM and any calibration; `pt_detect` input range at
  0 V common mode not verified.

## 7. Rejections checked

- **Decap (5.4).** Agree. 0.77 nC = 60 mA x 12.8 ns and sqrt(0.5 nH / 5.4 nF) = 0.30 ohm check. Small
  inconsistency: 0.5 nH with 4.4-6 nF gives 107-92 MHz; the quoted 78-95 MHz is the power-delivery model, which has
  more inductance. Not examined by the pass: a freed provider site used as an extra supply or ground bond lowers L
  (one more of each is about -10 %), which is worth roughly 0.5 nF of bank (about 0.1 mm2) at equal sqrt(L/C). That
  competes with OCP-1 for `bidir[22]/[23]` and is option P2 for `bidir[17]`. Hand estimate only.
- **Terminations, case A (5.2).** 1.97 GHz, +9.3 dB at 1.6 GHz, +0.9 dB at 625 MHz reproduce. For TX with the real
  2.7 pF the resonance is 1.2 GHz, below Nyquist: the rejection is stronger than written.
- **USB (5.1).** Agree. I looked for a carrier split (FS/LS from the FPGA, HS-only on the die) to delete the FS
  drivers: HS reset and resume need FS levels on the same pins, so no.
- **R-10, R-11, RF (5.5).** Agree; numbers match PD21 / PD45 and the ledger.

## 8. Totals (section 6) and double counting

- No double count with die-fit lever 1: `variants.sh` removes `pad_bb_i, pad_bb_q, pad_wmon` only. No overlap with
  `consolidation-pass-4.md` or AP4 for `pt_lo_lf`.
- Sums reproduce: 0.191 - 0.29 = -0.10; 0.26 - 0.29 = -0.03; 0.81 - 0.29 = 0.52.
- **"Fits" is not shown.** In `c-l6` 0.514 mm2 is already free and the unplaced items are `detect` (0.090,
  geometry), `lna` (0.043, keep-away rules), `vco_replica`, ATB groups. The LNA is unplaced for a rule, not for
  area. The WTX_EXT hole (310 x 487 um, east edge) probably takes `detect`; the `pt_lo_lf` area is in the LO
  region. Needs the packer.
- Corrected stack on C after levers 1-5: 0.19 + 0.14 (regulator at 0.44) - 0.22..0.30 = **+0.03 to +0.11 short**,
  not -0.10; Cr +0.10 to +0.18; B about 0.65-0.73.
- Pads: OCP-2 frees two sites and OCP-1 uses both. Nothing is left for OCP-3, and `bidir[17]` stays available for
  P2.
- Section 2 total: I get 0.34-0.35 mm2 from `passive_area.csv` (MIM 0.183-0.189, resistor 0.020-0.026, MOS 0.136),
  not 0.33 / 0.167 / 0.011. Not material.
- Section 11 says rows OCP-1..6 are in `interface-changes.md`: there are none (grep count 0).

## 9. Missed

1. The regulator's real size (4.2). It is the largest number in this area and it moved the wrong way.
2. C2 can shrink on the die with no pad: MIM over the MOS capacitor (3.6 + 2.0 fF/um2) takes 0.136 to about 0.087,
   i.e. 0.04-0.05 mm2. `pt_lo_lf` has only 0.007 of MIM, so Metal4/5 above C2 is free. DRC of MIM over
   `cap_nmos_03v3_b` not verified. Lowering Icp to shrink C2 is not free: R is already about 13 nV/rtHz.
3. After lever 1, BB_I / BB_Q are four west provider analog pads idle in wired and USB modes. The pass did not list
   them; I found nothing large that is wired-only to put there (the `pll_vreg2` capacitor is needed in RF modes).
4. Supply-bond use of freed sites against decap area (section 7).
