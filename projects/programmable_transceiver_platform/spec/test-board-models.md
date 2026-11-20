# Test-board models (predicted)

Current state, 2026-11-20. Packaging is fixed (MANDATE 6): the die sits on the wafer.space COB module; its 70-pin
board-to-board connector plugs into a larger **test board** that carries all test circuitry. Test boards are not
designed now; this file **predicts** what they will present wherever chip evidence depends on it, states the basis,
and gives one set of SPICE models that benches include: [`test-board/tb_models.spice`](test-board/tb_models.spice).
The COB part (bond, COB traces, via, mezzanine connector) stays in `package-channel.md` /
`package-channel-{rf,wired}.json`; these models start at the test-board side of the mated connector. Board
obligations remain in `board-requirements.md` (B*, BP-*, HL-B*). Model check: `scratch/obs-bringup/tbm/` (ngspice AC).

## 1. Assumed construction (basis for every number below)

4-layer FR4 (εr 4.2-4.5, tan δ 0.02), 50 Ω microstrip / 100 Ω differential over a solid ground (BP-5, BP-8),
0402/0201 passives, edge-launch SMA for bench access (B10). Signal parts within 10 mm of the connector (BP-3) is the
nominal placement P2; the qualification axis P1-P4 = connector + 2 / 10 / 30 / 50 mm (package-channel.md section 6).
No EM simulation and no measured data exist; the line loss is fitted to the package-channel placement sweep, which
itself is analytic. Confidence: line loss ±30 %, connector/via parasitics ±50 %.

## 2. HS wired pairs and RF lines beyond the connector

| Quantity | Model (`tb_line50`, `tb_land`, `tb_sma`, `tb_leg`) | Value |
|---|---|---|
| Loss per mm | α = 0.0195·√f + 0.00223·f dB/mm (f in GHz) | 0.025 dB/mm at 1.25 GHz, 0.036 at 2.45 GHz |
| Loss, 30 mm / 50 mm | at 0.81 GHz (2.7 Gb/s Nyq. half) / 1.25 / 1.62 (3.24 Gb/s Nyq.) / 2.45 GHz | 30 mm: 0.58 / 0.74 / 0.86 / 1.08 dB; 50 mm: 0.97 / 1.23 / 1.43 / 1.80 dB |
| Ladder accuracy | 10 lumped sections, loss set at `f0_ghz` | 48 mm: 1.21 dB at 1.25 GHz (fit 1.18), 1.95 dB at 2.45 GHz (fit 1.74; ladder adds ~0.2 dB, pessimistic) |
| Delay | εeff 3.3 | 6.06 ps/mm |
| Return loss of the board part | land 0.06 pF + via 0.3 nH / 0.1 pF; SMA 0.15 pF + 0.3 nH + 0.1 pF | ≥ 20 dB to 2.5 GHz estimated; the chip-side return loss is set by the COB and pad (package-channel.md section 3) |
| Crosstalk, pair to neighbour pair, 3w spacing, 30 mm coupled | estimate (no EM) | NEXT ≤ −35 dB, FEXT ≤ −40 dB to 2.5 GHz; COB crosstalk (−12 to −25 dB) dominates |

Wired benches: `tb_leg` per leg at `f0_ghz` = Nyquist of the rate (0.625 / 1.25 / 1.35 / 1.56 / 1.62 GHz for
1.25 / 2.5 / 2.7 / 3.125 / 3.24 Gb/s) + the AC-coupling capacitor (B22/B23) + 50 Ω instrument. RF benches: `f0_ghz`
= 2.45.

## 3. RF match network, external LNA, baluns, external LO

| Part | Model | Basis |
|---|---|---|
| RF_RX match (B18, **not met**) | L-match at the placement; loss 0.37 / 0.61 / 1.44 / 2.20 dB at P1-P4 for the 0.5 pF ∥ 200 Ω model | package-channel.md section 4; the real LNA input is not that model (RFR-11..14) |
| RF_TX feed + match + balun (B17) | 2.23 nH chokes, DC blocks, balun `tb_balun` il 0.8-1.0 dB, then `tb_leg`; loss 0.44 / 0.87 / 1.71 / 2.63 dB at P1-P4 | rf_tx README bench network; package-channel section 4 |
| External LNA (B5) | `tb_ext_lna`: 50 Ω, G ≥ 15 dB, NF ≤ 1.5 dB, bypass 0.5 dB | B5 |
| Balun 50:100 (B18/B19) | `tb_balun`: coupled inductors k 0.995, il_db 0.8 max, 0.2 pF per leg | B18 maximum loss |
| External LO (B3/B19/B31/B35) | `tb_ext_lo`: sine per leg from 50 Ω, 10 pF C0G, hybrid ±0.5 dB / ±3°, level vpp_oc settable ≥ 10 dB | B3, B19, B31; pad gain table package-channel section 4 (2.0-7.8 dB spread over pad C); I/Q −11° to −19° from fixed COB traces before BP-2 compensation |

## 4. Supply regulator and trim (B2, B37, B52)

`tb_supply`: LDO-class regulator with a trimmer, closed-loop output R 10 mΩ + 50 nH (loop about 100 kHz), 10 µF bulk,
per-contact 1 µF + 100 nF within 5 mm (BP-4), 0.4-0.5 nH plane to each mated supply contact, soft start `t_ss`.

| Quantity | Predicted | Basis / check |
|---|---|---|
| Setpoint range | 3.15-3.50 V by trimmer, ±1 % (B2) | |
| 3.50 V worst high | 3.50 × 1.01 + 1 mV ripple + 7 mV load-step overshoot + ≤ 20 mV soft-start overshoot = **3.563 V ≤ 3.63 V** (67 mV margin) | B2 budget; step = 0.1 A × √(50 nH / 10 µF) |
| Noise / ripple | ≤ 10 µV rms (10 Hz-100 kHz) LDO class; ≤ 1 mV rms 10 kHz-20 MHz at the contacts | B37 |
| Load step 100 mA (island enable) | ≈ 7 mV droop, settles in ≈ 10 µs | model above |
| Ramp | t_ss ≥ 11.7 µs at 3.50 V (≤ 0.3 V/µs) | B52 |

## 5. Decoupling reach through the connector (PKG-06)

The die sees the test board only through the eight mated supply contacts plus the COB's eight 1 µF. Above ~30 MHz
only on-die decap acts. With 4 nF on die the supply resonates at 54-80 MHz, 3.1-6.9 Ω undamped (package-channel
section 4, `pdn` in the json). The test board adds ≈ 0.5 nH per contact behind the connector: it changes the
resonance by < 5 %. **Nothing on the test board can fix the on-die resonance**; RQ-3 (≥ 3 nF, Q ≤ 3) stays an on-die
requirement.

## 6. Host link to a typical FPGA (HL-03, PKG-08)

`tb_host_line`: 22-33 Ω series at the driver, 50 Ω line ≤ 60 mm, receiver 8-10 pF (FPGA pin + B6 switch), HL-B2/B3.

| Item | Prediction | Status |
|---|---|---|
| Flight time 60 mm | 364 ps; ±2.5 mm match = ±15 ps (inside HL-D2H-BOARD 50 ps) | analytic |
| D2H budget at full rate | 400 + 160 + 100 + 200 + 150 + 50 ps + FPGA window 1000 ps = 2060 ps against the 3200 ps UI | interface-requirements 3.1; FPGA window *(verify)* per family |
| SSO | per chip on the real bond set (OBS-15, below) | computed |
| Rates | div4 bring-up, div2 with slow slew, full only fast slew + stagger (HL-B6, HL-RATE) | bring-up.md section 7 |

### Host ground bounce per chip (OBS-15)

Method: `scratch/obs-bringup/sso/sso.py <chip>` on the chip PDN model `scratch/integration/m1-pdn` (every bond of
`integration/chips/<chip>/bond_map.txt` at its provider bond centre with coupled bond inductance, provider ring rails
plus core ring, mesh, the as-built 5.4 nF decap plan, COB 1 µF on provider supply fingers, test board ideal beyond
the COB ground plane). The 11 D2H outputs switch at their own south sites (sin² current, peak dI/dt of the
package-channel table: 11 × 42 mA / 0.76 ns fast, 35 mA / 1.0 ns, 30 mA / 1.4 ns slow); victim = a quiet D2H/MISO
output = die VSS (quiet low) or die VDD (quiet high) at its site. Known answer: the same synthesis on a 0.8 nH lump
reproduces the old 486 mV; a 4× slower edge gives 4× less. Results `sso_rf.json`, `sso_wired.json`.

| Case (pess corner unless stated) | pt_rf low / high mV | pt_wired low / high mV |
|---|---|---|
| fast 0.76 ns, no stagger (nom corner) | 134 / 147 | 135 / 151 |
| fast 0.76 ns, no stagger | 185 / 202 | 185 / 204 |
| fast 0.76 ns, stagger | 139 / 158 | 139 / 160 |
| slow 1.4 ns, no stagger | 83 / 103 | 83 / 104 |
| fast, no stagger, VSS bonds on signal sites ignored (bound: their trace + connector path is not the COB plane) | 215 / 232 | 215 / 234 |
| control: no die decap, fast, no stagger | 200 / 307 | 201 / 365 |

The south edge has one ground bond (`dvss_pads[0]`) and no supply bond, but the return spreads through the provider
ring rails to all 20-29 VSS bonds and the die decap couples VDD and VSS; the effective return inductance is ~0.3 nH,
not the 0.8 nH lump. **Every rate passes HL-SSO (300 mV) on both chips**: full rate (fast slew, required by the eye)
185-234 mV unstaggered, 139-180 mV staggered; div2 / div4 with slow slew 83-113 mV. Push-out ≈ 0.23 V / 4.3 V/ns
≈ 55 ps < the 200 ps HL-D2H-SSO budget. No bond-map change is needed; the die decap is what holds the VDD side
(control row). Not modelled: the COB finger-to-plane via (~0.3 nH per ground bond, would add ≈ 15 %) and the
connector ground contacts that carry the line return.

## 7. Benches that assume something about the test board

| Bench (owner) | What it assumes | Matches this file? | Row |
|---|---|---|---|
| RF RX chain, `analog/rf_rx` `lna_match.channel_ladder` | COB channel + "carrier line", lossy parts fitted per chip | probably (same basis); should include `tb_leg` at P2 and P4 explicitly | TB-1 |
| RF TX README bench network | 2.23 nH chokes, ideal 200:50 balun + 1.0 dB pad, 50 Ω load, no carrier line | no carrier line: optimistic by 0.4-2.6 dB at P1-P4 | TB-2 |
| Wired TX real chain (`scratch/wired_tx/s12`, s13 pad matrix) | COB bond + "50 mm line" | line model not stated as lossy FR4: switch to `tb_leg` len 50 at the Nyquist f0 | TB-3 |
| Wired RX real neighbours (`scratch/wired_rx/r11`) | 120 mVppd source at the pad / channel | test-board loss (0.6-1.4 dB at 30-50 mm) before the COB must be in the source amplitude | TB-4 |
| External LO (`analog/timing` lo_ext, B3) | 3.0-4.0 Vpp open circuit, 1.5 nH bond, no carrier line | stale (B3 says so): requalify with `tb_ext_lo` + `tb_leg` + COB chain | TB-5 |
| Power delivery `scratch/integration/m1-pdn` | eight 1 µF COB caps, ideal supply beyond | consistent; add `tb_supply` for load steps and the 3.50 V case | TB-6 |
| Host-link pad screens (6-10 pF) and the package json `host_ssn` (486 mV) | lumped load, 0.8 nH lumped return | load matches; the 486 mV lump is superseded by section 6 (≤ 234 mV) | OBS-15 |
| USB HS amplitude (B11) | 45 Ω to ground per leg at the pad | test-board line + TVS (B46) not included | TB-7 |
| Core bias / bring-up fixtures (`check_chip_fallback`, `check_core_bias_observation`) | ideal SMU on ATB, ideal supply | acceptable for DC; supply ramp should use `tb_supply` t_ss | TB-6 |
