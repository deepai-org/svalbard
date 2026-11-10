# Package channel: wafer.space TT01 70-pin mezzanine COB

Status: analytic model, 2026-11-10. This is not an EM solve, and the connector values are estimates. Data: [package-channel.json](package-channel.json).
Scripts: `scratch/cob/` (`kparse.py`, `channel_model.py`, `placement.py`, `lo_sweep.py`, `lo_term.py`, `pdn_thermal.py`).
Risks: PKG-01..08 in `scratch/reviews/risk-register.md`. Demands: `scratch/reviews/interface-changes.md`, section "Package channel (TT01 COB)".

**Policy (user, 2026-11-10):** the package mostly changes *performance*, not feasibility. Off-chip passives stay useful.
So every external part is evaluated over a range of placements, and the chip must tolerate wherever the user puts them.
This adds a qualification axis, **passive placement tolerance** (§6).

## 1. Sources

| Item | Source |
|---|---|
| COB board (KiCad 10, 4 layers) | [run-1/1x1-cob/1x1-mezzanine.kicad_pcb @ 4f05ed1](https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs/blob/4f05ed1ea1994d8101a265d5d4f995bcea86d5a1/run-1/1x1-cob/1x1-mezzanine.kicad_pcb), sha256 `b0de95da…`, identical at HEAD `5cb4668` |
| Pad map, connector choice | [run-1/README.md](https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs/blob/main/run-1/README.md) |
| Wire-bond rules (< 3 mm, ≤ 45°, ≥ 1 mm) | [run-1/wirebonding/README.md](https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs/blob/main/run-1/wirebonding/README.md) |
| Example carrier boards | [run-1/motherboards](https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs/tree/main/run-1/motherboards) |
| Connector | HCTL HC-PBB40C-70DP-0.4V-02, [LCSC C19089236](https://www.lcsc.com/product-detail/C19089236.html), mate [C19089262](https://www.lcsc.com/product-detail/C19089262.html). 0.4 mm pitch, 2 × 35 contacts, 0.3 A/contact, 1.5–4 mm stack. **No S-parameters or crosstalk data are published.** |

No published S-parameters exist for the COB or the connector.

## 2. What the board actually is (extracted)

- **Size and stackup.** The board is 14 × 16 mm and 0.747 mm thick: F.Cu / 0.196 mm FR4 (εr 4.5, tan δ 0.02) / In1 / 0.23 mm core / In2 / 0.196 mm / B.Cu.
  In1 and In2 are solid GND. The F.Cu pour is excluded inside the finger ring.
- **Die paddle.** Pad 75 is 4.0 × 5.2 mm, tied to GND through 6 × 0.3 mm vias. The die (3.93 × 5.12 mm) fills it.
- **Bond fingers.** Each finger is 1.0 × 0.25 mm at 0.4 mm pitch. The N/S rows sit at ±4.7 mm and the E/W rows at ±4.3 mm.
  Wire length (planar × 1.1 + 0.15 mm loop) is **2.2–3.2 mm**, with a maximum angle of 41°. The table in the JSON gives every pin.
- **Traces.** All 56 signal traces are **0.1 mm wide, Z0 = 86.6 Ω, εeff 3.14 (5.9 ps/mm)**. Each runs F.Cu 0.9–3.5 mm, then 1 via (0.45/0.3 mm), then B.Cu 0.7–4.7 mm, for 2.9–7.4 mm in total.
  Minimum centre spacing is 0.20–0.40 mm (≈ 1–2 h).
- **Connector.** It sits on **B.Cu directly under the die**: pins 1–35 on one row, 36–70 on the other.
  GND is on contacts 10, 18, 25, 45, 53, 61 plus 4 shell tabs. Supplies (one contact each, 0.2 mm traces): VDD_IO_3 → 9, VDD_CORE_1 → 11, PWR_AUX_1 → 19, VDD_IO_2 → 24, VDD_IO_1 → 44, VDD_CORE_0 → 46, PWR_AUX_0 → 54, VDD_IO_0 → 62.
- **Passive strips.** These are 8 × **0201** footprints (C101–C108, "1 µF") on the back-side edge strips, one from each supply net to GND.
  **No footprint exists on any signal net.** A signal passive on the COB would only be a hand-reworked shunt part onto a 0.1 mm trace. Series parts would mean cutting a fixed trace, which is not allowed.
- **74 pads vs 70 contacts.** Each of the 56 signal sites and 8 supply sites has its own contact. The 10 die GND bonds land on one GND plane, which reaches 6 GND contacts and 4 tabs.
  **No functional signal loses its connector path.** The "4 unconnected" are GND bonds without a dedicated contact.

## 3. Channel per pin class (die pad → carrier 50 Ω)

Model chain: pad C → bond (0.83 nH/mm over In1, R_skin) → finger 0.08 pF → F microstrip → via (0.27–0.49 nH, 0.1 pF) → B microstrip → land 0.06 pF → connector (0.6 nH + distance-to-GND term, 0.85–1.22 nH; 0.25 pF) → 10 mm carrier line.

| Class (pins) | Bond mm | COB trace mm | IL interconnect 156 M / 1.25 G / 2.45 G (dB) | RL with die load at f_use | Neighbour XT at f_use (SE) |
|---|---|---|---|---|---|
| RF_RX (70/69) | 2.69/2.60 | 4.97/6.01 | 0.12 / 0.74 / 1.64 | 8.3 dB @2.45 G (0.5 pF ∥ 50 Ω, before match) | P/N −12 dB (pair) |
| RF_TX (60/59) | 2.60/2.69 | 3.12/3.06 | 0.11 / 0.61 / 1.40 | 8.5 dB @2.45 G (1 pF ∥ 50 Ω) | **→AUX_CLK_N −17.5 dB** |
| LO I = REF_IN (66/65) | 2.44/2.42 | 3.18/5.66 | 0.11 / 0.59 / 1.35 | 8.8 dB | →BB_I_N −18.9 dB |
| LO Q = AUX_CLK (62/61) | 2.47/2.53 | 5.22/5.46 | 0.12 / 0.72 / 1.58 | 7.3 dB | (RF_TX above) |
| WIRE_RX (21/20) | 2.79/2.90 | 5.20/5.34 | 0.12 / 0.77 / 1.71 | **10.0 dB @1.25 G** (2.35 pF, 50 Ω) | →WCLK_IN −23.5 dB @1.25 G |
| WIRE_TX (29/28) | 2.44/2.42 | 5.16/3.14 | 0.12 / 0.70 / 1.53 | 13.0 dB @1.25 G (1.8 pF) | →WTX_EXT −24.7 dB @1.25 G |
| WCLK_IN / WTX_EXT | 2.5–2.7 | 3.0–5.2 | 0.11 / 0.6–0.8 / 1.4–1.7 | 14.5–18 dB @1.25 G | — |
| Host D2H/H2D | 2.21–2.79 | 2.9–7.4 | 0.11–0.14 / 0.5–0.94 / — | unterminated CMOS | −42 dB @156 M |

**Step and pulse response.** Source is 50 Ω on the carrier; the die end is pad C ∥ on-die termination.

| Path | Rise 10–90 | Overshoot | ISI (Σ\|cursors\|/main) | Eye (1 − ISI) |
|---|---|---|---|---|
| WIRE_RX @2.5 Gb/s, 2.35 pF | 205 ps | 7.6 % | 0.088 | 0.95 |
| WIRE_RX @2.5 Gb/s, 1.6 pF (S7 target) | 185 ps | 8.2 % | 0.114 | 0.95 |
| WIRE_RX, old 1.5 nH-only model | 115 ps | 1.8 % | 0.032 | 0.975 |
| WIRE_TX @2.5 Gb/s | 190 ps | 7.4 % | 0.115 | 0.94 |
| D2H_CLK / H2D_CLK @312.5 Mb/s (4 pF, no termination) | 395 ps | 10 % | 0.21 | 0.88 |

The package alone costs ≈ 1 dB at the 1.25 GHz Nyquist plus a +7 % first post-cursor ringing at 2.5 Gb/s. It does not close the eye.
**Wired return loss is the binding package spec, not the eye.**

**Skew** (5.9 ps/mm). Intra-pair: REF_IN 14.7 ps, WCLK_IN 12.4, WTX_EXT 12.3, WIRE_TX 11.9, BB_I 10.2, RF_RX 6.1, AUX 1.4, WIRE_RX 0.8, RF_TX 0.4.
Host groups: D2H spread 22.5 ps, H2D 27.0 ps; both clocks are on the shortest traces.

## 4. Passive placement sweep

Places evaluated: **strip** (COB edge, shunt-only rework), **conn+2 mm**, and carrier **10 / 30 / 50 mm** of 50 Ω line.
Each match is a 2-element L-match (Q_L 40, Q_C 200), designed at 2.44 GHz.

| Part | strip | conn+2 mm | car 10 mm | car 30 mm | car 50 mm | Notes |
|---|---|---|---|---|---|---|
| RF_RX match (B18/B25): loss, dB (NF penalty) | 0.23 | 0.37 | 0.61 | 1.44 | 2.20 | RL ≥ 26.9 dB in band; ≥ 28.7 dB for ±0.3 mm bond, at every placement (die model 0.5 pF ∥ 200 Ω) |
| RF_RX unmatched (50 Ω straight in): loss, dB | 0.58 | 0.49 | 0.78 | 1.51 | 2.23 | A user with no match loses only 0.1–0.4 dB more than a matched one *for this die model* |
| RF_TX match/balun (B17): loss, dB (Pout penalty) | 0.22 | 0.26 | 0.72 | 1.50 | 2.30 | RL ≥ 25 dB in band, ≥ 23.7 dB for ±0.3 mm bond (die 1 pF ∥ 100 Ω per leg) |
| Ext. LO hybrid (B19): I/Q phase error at pads | — | −6 to −10° | same | same | same | Set by **COB asymmetry**, not distance; amplitude falls 0.5 dB from 2 to 50 mm |
| Ext. LO level (B3): pad / open-circuit, unterminated, pad C 4 pF | — | 0.48 | — | 0.43 | ≈0.40 | Old 1.5 nH model: 0.67. Pad C 0.7–2 pF gives 2.35–0.93 (resonant) |
| Wired AC-coupling caps (B22/B23) | n/a (series) | ✓ | ✓ | ✓ | ✓ | Series C carries no stub; carrier line IL @1.25 G 0.05/0.25/0.74/1.23 dB for 2/10/30/50 mm |
| Wired termination (on die) | — | — | — | — | — | RL @1.25 G: 2.35 pF → 9.0–10.3 dB (R 40–60 Ω); 1.6 pF → 10.7–16.0 dB; 1.0 pF → 11.1–20.0 dB |
| Reference XO (B23-3) | — | ✓ | ✓ | ✓ | ✓ | 25 MHz LVCMOS: COB adds < 0.15 dB; source-terminate at the XO |
| Decap (8 × 0201 strip vs carrier) | f_res 159 MHz, Z_pk 12.5 Ω | 126 MHz, 20 Ω | 119 MHz, 22.5 Ω | 107 MHz, 27.5 Ω | — | 1 nF on die, undamped. With 4 nF: 80/63/59 MHz, 3.1–6.9 Ω |

**Reading.** Every off-chip part still works at every placement. The cost is a smooth 0.2→2.3 dB from the strip to 50 mm for RF matching and balun parts.
Two things do not improve with closer passives:
- LO I/Q phase: set by the fixed COB lengths.
- PDN resonance: set by the bond and connector L.

Both need on-chip tolerance features (§5).

## 5. Plan re-evaluation (board items)

| Item | Verdict | Change |
|---|---|---|
| B17 RF_TX balun/match | still valid → **carrier** (≤ 10 mm preferred) | Pout −0.26…−2.3 dB vs placement. DC feed through the balun centre tap is unchanged. Per-pin model in sims. |
| B18/B25 RF_RX match/balun | still valid → **carrier**, π footprints kept | NF +0.37…+2.2 dB vs placement. Bond tolerance is not dominant with a ≈ 100–200 Ω input. |
| B3/B31 external LO level | valid, **window moves** | ≈ +2.5 dB source level if the pad load is ≈ 4 pF. B31 becomes mandatory. Owner rerun with this chain (PKG-05). |
| B19 LO hybrid | valid → carrier, **plus length compensation** | The COB alone gives 6–10° of I/Q error. The carrier must compensate (BP-2) and the chip must trim (D-LO-2). |
| B22/B23 AC coupling, termination | valid → carrier, any distance | RL 10.0 dB at 1.25 GHz is a 0 dB margin against PCIe RX ≥ 10 dB. The fix is on chip (pad C, R trim). |
| B23(4) "no series peaking L" | valid | Package L is already 3.3–4 nH per leg. |
| B13/B14/B15 board CDR, SerDes, mux | valid → carrier | They see the same COB channel. |
| HL-B1..B6 host link | valid, with notes | COB is 87 Ω for 3–7 mm (≈ 35 ps ≪ 760 ps edge) and needs no change. The COB adds 22–27 ps group spread, which the FPGA deskew (HL-B5) covers. HL-B4 bounce needs slew control (PKG-08). |
| B6/B6a bus switch | valid → carrier | Unchanged. |
| B23(3) crystal oscillator on REF_IN | valid → carrier, any distance | A passive crystal is not possible (no XO amplifier pins); keep the XO module. |
| Decap | strip **and** carrier | Populate all 8 strip caps; on-die damped decap is required (PKG-06). |
| B27 grounded die attach | valid, already met | The paddle is GND with 6 vias; the attach must be conductive epoxy. |
| B28 opaque cover | valid | Use the top-side cold finger. |
| B2a/B29 plate under die | **must change** | The connector occupies the back side. Use a top-side cold finger (≈ 6–8 °C/W) or a per-mode set point with dwell (PKG-07). |
| B30 bond 1.5 ± 0.2 mm | **cannot be met as written** | Fixed ring: 2.2–3.2 mm. Becomes "record the actual lengths" (PKG-01). |
| B32 AGND_RX return | valid, **reinterpreted** | If adopted on a spare site, it gets its own trace and contact (≈ 6 nH). It is an LF Kelvin return to the carrier GND at the RF connector, not an RF ground. |
| 70 vs 74 | no loss | No functional signal loses a connector path. |

## 6. Qualification axis: passive placement tolerance

Every RF, LO, wired and PDN claim is qualified at the placement points P0 (strip, if the part can be shunt-reworked), P1 (connector + 2 mm), P2 (+10 mm), P3 (+30 mm) and P4 (+50 mm).
Also qualified: no part at all, where an on-chip fallback exists.
At P1–P4 the bond spread is ±0.3 mm and the pad C spread is ±20 %.

| Axis criterion | Requirement |
|---|---|
| RX NF | spec + placement loss (§4), ≤ +1.5 dB at P3, with the on-chip trim re-centred |
| TX Pout | spec − placement loss, ≤ −1.5 dB at P3 |
| LO on-level at mixers | in window at P1–P4 using only on-chip termination/trim and the B31 level; I/Q ≤ 3° after on-chip trim |
| Wired RX RL | ≥ 10 dB to 1.25 GHz with on-die R trim at P1–P4; ≥ 8 dB at 2.5 GHz |
| Wired eye | BER-1e-12 eye with CTLE/de-emphasis at P1–P4 plus the standard's reference channel |
| PDN | Z_die ≤ 2 Ω from 30 to 400 MHz with strip caps populated, and ≤ 3 Ω with none |
