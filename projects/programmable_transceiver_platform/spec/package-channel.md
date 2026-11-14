# Package channel: wafer.space 70-pin mezzanine chip-on-board

Analytic lumped / transmission-line model; not an EM solve. No S-parameters are published for
the board or the connector, so the connector values are estimates. All numbers are in
[package-channel.json](package-channel.json) (per pin: site, bond pad, board net, connector
contact, bond wire, traces, S-parameters, crosstalk). Generator: `scratch/pads-core/spec/`.
Board obligations that follow from it are in [board-requirements.md](board-requirements.md)
(BP-1..8); risks are PKG-* in [risk-register.md](risk-register.md).

The package mostly changes performance, not feasibility. Every external part is therefore
qualified over a range of placements (section 6), and the chip must tolerate wherever the
carrier puts it.

## 1. Sources

| Item | Source |
|---|---|
| COB board (KiCad, 4 layers) | [run-1/1x1-cob/1x1-mezzanine.kicad_pcb @ 4f05ed1](https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs/blob/4f05ed1ea1994d8101a265d5d4f995bcea86d5a1/run-1/1x1-cob/1x1-mezzanine.kicad_pcb), sha256 `b0de95da…` |
| Pad map, wire-bond rules, example carriers | [run-1](https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs/tree/main/run-1) (`README.md`, `wirebonding/README.md`, `motherboards/`) |
| Connector | HCTL HC-PBB40C-70DP-0.4V-02 ([LCSC C19089236](https://www.lcsc.com/product-detail/C19089236.html), mate C19089262): 0.4 mm pitch, 2 × 35 contacts, 0.3 A per contact, 1.5–4 mm stack |
| Assembly facts (wire, die thickness, fixed bond layout, glob-top) | `scratch/reviews/wafer-space-answers.md` |
| Audited bond lengths | `scratch/reviews/pads-core/BOND-AUDIT.md`, `wire-table.md` |

## 2. The board

- **Assembly.** One fixed 74-wire bond layout: no custom bonds, down-bonds, double bonds or
  extra wires, and extra pad openings on the die cannot be bonded. Wire is 0.8 mil (20.3 µm)
  aluminium, wedge bonded. The die is about 250 µm thick, attached on the ground paddle and
  covered with epoxy glob-top. A customer-modified board may not be accepted, so the
  unmodified board must work.
- **Size and stackup.** 14 × 16 mm, 0.747 mm thick: F.Cu / 0.196 mm FR4 (εr 4.5, tan δ 0.02) /
  In1 / 0.23 mm core / In2 / 0.196 mm / B.Cu. In1 and In2 are solid ground. The F.Cu pour is
  excluded inside the finger ring.
- **Die paddle.** 4.0 × 5.2 mm, ground, 6 × 0.3 mm vias. The 3.932 × 5.122 mm die fills it.
- **Bond fingers.** 1.0 × 0.25 mm at 0.4 mm pitch; north/south rows at ±4.7 mm, east/west rows
  at ±4.3 mm from the centre.
- **Traces.** All 56 signal traces are 0.1 mm wide, Z0 86.6 Ω, εeff 3.14 (5.9 ps/mm): front
  copper, one via, back copper, 2.9–7.4 mm in total.
- **Connector.** On the back side directly under the die. Ground on contacts 10, 18, 25, 45,
  53, 61 and four shell tabs. Supplies, one contact each: VDD_IO_3 → 9, VDD_CORE_1 → 11,
  PWR_AUX_1 → 19, VDD_IO_2 → 24, VDD_IO_1 → 44, VDD_CORE_0 → 46, PWR_AUX_0 → 54, VDD_IO_0 → 62.
- **Passives.** Eight 0201 footprints (C101–C108, 1 µF), one from each supply net to ground.
  **No footprint exists on any signal net.** The nearest signal passive is on the carrier:
  bond, 3–7 mm of trace, via and connector away (≥ 6.5 nH per leg on RF_RX).
- **74 pads, 70 contacts.** Each of the 56 signal sites and 8 supply sites has its own contact.
  The 10 ground bonds land on the one ground plane. No signal lacks a connector path.
- **Thermal.** The connector blocks the back side, so the bottom path is 35–45 °C/W. A
  top-side cold finger through 0.3 mm of 3 W/m·K gel gives about 5 °C/W plus 1–2 °C/W of
  spreading.

## 3. Bond map and channel per pin

West edge: `RF_RX_P/N` (bonds 70/69, contacts 12/13), `BB_I_P/N` (68/67, 14/15), `BB_Q_P/N`
(66/65, 16/17), `AUX_CLK_P/N` (62/61, 20/21), `REF_IN`/`REF_IN_N` (60/59, 22/23), `RF_TX_P/N`
(56/55, 26/27). East edge: `WIRE_RX_N/P` (20/21, 60/59), `POR_BYPASS` (22, 58), spare
`bidir[17]` (23, 57), `USB_DN/DP` (24/25, 56/55), `WIRE_TX_N/P` (28/29, 52/51), `WTX_EXT_P/N`
(30/31, 50/49), `WMON` (32, 48), `TLP_TEST` (33, 47). South: D2H, SPI, `RESET_N`. North: H2D,
`CLK_OBS`, `DBG_OBS0/1`, `ATB0/1`. The LNA has no pad of its own for ground: it uses die VSS.

Model chain: pad C → bond wire → finger 0.08 pF → front microstrip → via (0.26–0.49 nH,
0.1 pF) → back microstrip → land 0.06 pF → connector (0.85–1.22 nH, 0.25 pF) → carrier line.

**Bond wires** (all 74, `bond_wire` per pin; loop height, landing point and a die placement
shift of ±0.1 mm and ±1° varied):

| Quantity | Range over all bonds |
|---|---|
| 3-D length | 1.86–3.12 mm |
| Inductance, nominal (0.874 nH/mm, 0.40 mm above the ground plane) | 1.99–2.66 nH |
| Inductance, min / max of any bond | 1.40 / 3.54 nH |
| Resistance, aluminium | 211–290 mΩ |
| Largest wire angle | 44° |
| DC current for a 100 K rise, 3.0 mm aluminium wire | 0.233 A |

The S-parameter and crosstalk entries use the generator's plan length (2.21–3.16 mm) at
0.83 nH/mm.

| Class (bond pads) | Plan bond mm | Trace mm | Interconnect loss at 156 M / 1.25 G / 2.45 G (dB) | Return loss with the die load | Worst neighbour crosstalk |
|---|---|---|---|---|---|
| RF_RX (70/69) | 2.69 / 2.60 | 4.97 / 6.01 | 0.12 / 0.74 / 1.64 | 8.3 dB at 2.45 G (0.5 pF ∥ 50 Ω, before the match) | P to N −12 dB |
| RF_TX (56/55) | 3.02 / 3.16 | 5.68 / 5.39 | 0.13 / 0.80 / 1.78 | 6.7 dB at 2.45 G (1 pF ∥ 50 Ω) | → ATB1 −13.3 dB |
| LO I = REF_IN (60/59) | 2.60 / 2.69 | 3.12 / 3.06 | 0.11 / 0.61 / 1.40 | 8.5 dB at 2.45 G | → AUX_CLK_N −17.5 dB |
| LO Q = AUX_CLK (62/61) | 2.47 / 2.53 | 5.22 / 5.46 | 0.12 / 0.72 / 1.58 | 7.3 dB at 2.45 G | → REF_IN −17.6 dB |
| WIRE_RX (21/20) | 2.79 / 2.90 | 5.20 / 5.34 | 0.12 / 0.77 / 1.71 | 10.0 dB at 1.25 G for a 2.35 pF pad and 50 Ω | → POR_BYPASS −23.5 dB at 1.25 G |
| WIRE_TX (29/28) | 2.44 / 2.42 | 5.16 / 3.14 | 0.12 / 0.70 / 1.53 | 13.0 dB at 1.25 G (1.8 pF) | → WTX_EXT_P −24.7 dB at 1.25 G |
| WTX_EXT (30/31) | 2.47 / 2.53 | 3.04 / 5.12 | 0.11 / 0.60–0.74 / 1.40–1.61 | 15–18 dB at 1.25 G | → WMON −21.4 dB |
| Host D2H / H2D | 2.21–2.79 | 2.88–6.91 | 0.11–0.14 / — / — | unterminated CMOS | −24 dB at 1.25 G to the next lane |

The WIRE_RX entries in the JSON were computed with a 2.35 pF pad. The published `pad_hspad`
extracts at 1.11–1.16 pF per leg without metal resistance (`analog/pads/README.md`); the
table below gives return loss against pad capacitance.

| WIRE_RX return loss at 1.25 GHz (dB) | R 40 Ω | 45 | 50 | 55 | 60 |
|---|---|---|---|---|---|
| Pad 2.35 pF | 9.0 | 9.6 | 10.0 | 10.3 | 10.3 |
| Pad 1.6 pF | 10.7 | 12.1 | 13.5 | 14.8 | 16.0 |
| Pad 1.0 pF | 11.1 | 12.9 | 14.8 | 17.1 | 20.0 |

**Step and pulse response** (50 Ω source on the carrier; die end is pad C ∥ on-die termination):

| Path | Rise 10–90 % | Overshoot | ISI (Σ\|cursors\|/main) | Eye (1 − ISI) |
|---|---|---|---|---|
| WIRE_RX at 2.5 Gb/s, 2.35 pF | 205 ps | 7.6 % | 0.088 | 0.95 |
| WIRE_RX at 2.5 Gb/s, 1.6 pF | 185 ps | 8.2 % | 0.114 | 0.95 |
| WIRE_TX at 2.5 Gb/s | 190 ps | 7.4 % | 0.115 | 0.94 |
| WTX_EXT at 2.5 Gb/s | 160 ps | 12.7 % | 0.131 | 0.98 |
| D2H_CLK / H2D_CLK at 312.5 Mb/s (no termination) | 395 ps | 10 % | 0.21 | 0.88 |

The package costs about 1 dB at 1.25 GHz and a 7 % post-cursor at 2.5 Gb/s. It does not close
the eye; wired return loss is the binding package quantity. The pulse response has not been
computed at 2.7–3.24 Gb/s on this bond map.

**Skew** (5.9 ps/mm, P minus N): WIRE_TX +11.9 ps, WTX_EXT −12.3, BB_Q −14.7, BB_I −10.2,
RF_RX −6.1, RF_TX +1.7, AUX_CLK −1.4, WIRE_RX −0.8, REF_IN +0.4. Host groups: D2H spread
22.5 ps, H2D 23.8 ps; both clocks are on the shortest traces.

**Host simultaneous switching** (11 outputs): 486 mV ground bounce at 0.76 ns edges, 308 mV
at 1.0 ns, 189 mV at 1.4 ns; a two-group launch stagger halves it.

## 4. Passive placement sweep

Places: **strip** (COB edge; only as a hand-reworked shunt part, not available on an
unmodified board), **connector + 2 mm**, and **10 / 30 / 50 mm** of 50 Ω carrier line. Each
match is a two-element L-match designed at 2.44 GHz.

| Part | strip | conn + 2 mm | 10 mm | 30 mm | 50 mm | Notes |
|---|---|---|---|---|---|---|
| RF_RX match: loss, dB (noise-figure penalty) | 0.23 | 0.37 | 0.61 | 1.44 | 2.20 | Return loss ≥ 26.9 dB in band for a 0.5 pF ∥ 200 Ω die model. The real LNA input is not this model: B18 is not met |
| RF_RX unmatched (50 Ω straight in): loss, dB | 0.58 | 0.49 | 0.78 | 1.51 | 2.23 | |
| RF_TX match and balun: loss, dB (output-power penalty) | 0.22 | 0.44 | 0.87 | 1.71 | 2.63 | Return loss ≥ 22.8 dB in band (1 pF ∥ 100 Ω per leg) |
| Wired AC-coupling capacitors: carrier line loss at 1.25 GHz, dB | — | 0.05 | 0.25 | 0.74 | 1.23 | Series parts carry no stub |
| Supply decoupling: resonance / undamped peak with 1 nF on the die | 159 MHz, 12.5 Ω | 126 MHz, 20 Ω | 119 MHz, 22.5 Ω | 107 MHz, 27.5 Ω | — | With 4 nF on the die: 80 / 63 / 59 / 54 MHz, 3.1–6.9 Ω. The on-die plan is in [power-delivery.md](power-delivery.md) |

**External LO at the pads** (differential gain from the source's open-circuit voltage, 2.45 GHz,
30 mm of carrier line; connector + 2 mm is about 1 dB higher):

| Pad load | Unterminated | 200 Ω | 100 Ω | 50 Ω |
|---|---|---|---|---|
| 0.7 pF | 2.42 | 1.64 | 1.22 | 0.81 |
| 1.0 pF | 2.01 | 1.49 | 1.16 | 0.79 |
| 1.5 pF | 1.36 | 1.16 | 0.98 | 0.73 |
| 2.0 pF | 0.98 | 0.90 | 0.81 | 0.65 |
| Spread over pad C | 7.8 dB | 5.2 dB | 3.6 dB | 2.0 dB |

The fixed traces give an I/Q phase error of −11° to −19° at the pads (pad C 2.0 to 0.7 pF,
unterminated; −11° with 50 Ω), set by the board and not by the carrier distance.

Every off-chip part works at every placement, at a cost that grows smoothly from 0.2 to
2.6 dB between the strip and 50 mm. Two things do not improve with closer passives: the LO
I/Q phase (fixed trace lengths) and the supply resonance (bond and connector inductance).

## 5. What the chip must provide because of the package

- Programmable termination, matching and trim on every RF, LO and multi-Gb/s pin; wide-range
  equalisation; on-chip fallbacks where no passive can sit close.
- An LO input tolerant of the amplitude spread above and of the fixed I/Q phase error, with
  on-chip I/Q trim; the carrier compensates the trace lengths (BP-2).
- No bond in any degeneration or ground-return path that needs less than about 2 nH.
- On-die damped decoupling: the eight strip capacitors act below about 30 MHz.
- Supply bonds within their rating: the worst supply bond carries 87.5 mA in the
  power-delivery model (11.5 K rise on a 3 mm aluminium wire).

## 6. Qualification axis: passive placement tolerance

Every RF, LO, wired and supply claim is qualified at P1 (connector + 2 mm), P2 (+10 mm),
P3 (+30 mm) and P4 (+50 mm), and with no part at all where an on-chip fallback exists. At
each point the bond length varies by ±0.3 mm and the pad capacitance by ±20 %.

| Criterion | Requirement |
|---|---|
| RX noise figure | Spec plus the placement loss of section 4; ≤ +1.5 dB at P3 with the on-chip trim re-centred |
| TX output power | Spec minus the placement loss; ≤ −1.5 dB at P3 |
| LO level at the mixers | In window at P1–P4 using only on-chip termination and trim and the board level setting (B31); I/Q ≤ 3° after on-chip trim |
| Wired RX return loss | ≥ 10 dB to 1.25 GHz with on-die resistance trim at P1–P4; ≥ 8 dB at 2.5 GHz |
| Wired eye | BER 1e-12 eye with CTLE and de-emphasis at P1–P4 plus the standard's reference channel |
| Supply impedance | ≤ 2 Ω from 30 to 400 MHz at the die with the strip capacitors populated, ≤ 3 Ω with none |
