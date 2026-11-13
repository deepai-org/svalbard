# RX robustness review: does the receiver work in real, noisy environments?

2026-11-10, branch `transceiver-risk-accepted-tapeout`. Analysis only: no block circuit or RTL was edited and no SPICE was run (the numbers are hand calculations on published or scratch evidence, flagged where assumed). Outputs:
- new requirements RF-RX-MAXIN … RF-COEX-PTA in `spec/interface-requirements.md` §2.2, with matching rows in `performance-requirements.json` (the checker passes, 116 rows)
- board requirements B33–B37
- risks RXR-01..12 (`physical-limits/analyses/rxr/rxr_outcomes.py`, register regenerated: 89 risks)
- demands RXR-D1..D7 in `interface-changes.md`

## Top gaps (in priority order)

1. **Max input level / pre-filter headroom (RXR-01, RF-RX-MAXIN: fails).** All gain before the channel filter is fixed except `gain_lo` (−3 dB) and the bypass (≈ −14 dB at NF ≈ 22 dB). The TIA clips at about **−34 dBm CW** (−20 dBm via bypass). The standards ask for −10 dBm (BLE) and −20 dBm mean (Wi-Fi OFDM, plus 10 dB crest). So we are **≈ 24 dB short**, and any phone or AP within about 1 m saturates the RX. Fix on chip with TIA feedback-R steps plus LNA attenuation (≥ 30 dB in ≤ 6 dB steps). This is small and conventional.
2. **AGC cannot settle inside the Wi-Fi L-STF (RXR-03, RF-RX-AGC: fails).** The fast gain command (opcode4) is specified but not in the RTL. A gain step over SPI takes ≈ 3.8 µs, so 2 steps take ≈ 7.6 µs against an 8 µs L-STF. Fix: implement opcode4 (RTL only).
3. **DC offset × PGA gain (RXR-02, RF-RX-DCOC: fails).** The only trim sits at the TIA, with an LSB of 7–10 mV. The residual of ≤ 4.5 mV is 8 / 16 / 65 % of ADC full scale at a PGA of 24 / 30 / 42 dB. The self-mixing offset also moves ≈ 20 mV with the RF level (37 % FS at 24 dB). Fix: a fine offset DAC after the PGA with a per-gain-code table, FPGA DC tracking, and low IF for the narrowband modes.
4. **Co-located cellular and 5 GHz blockers: no selectivity at all (RXR-04, RF-RX-COEX).** The LNA is wideband. A UE TX on B40/B41 gives +8…+13 dBm at the port, which is ≈ 45 dB past the headroom. Fix on the board: a BAW coexistence filter (B34), with its footprint on every carrier and populated in phone/gateway products.
5. **No pre-filter overload/RSSI visibility (RXR-09, RF-RX-OVLD: fails).** A blocker that clips the TIA but is filtered out never shows up in the ADC. Fix: two latched comparators per path, wired to a status bit and the stream flag.
6. **Missing specs on the board LO (RXR-06/11).** There is no phase-noise mask and no common-reference rule. Reciprocal mixing needs ≤ −107 dBc/Hz at 3 MHz and ≤ −120 at 40 MHz. B35 adds the mask and one ±10 ppm TCXO shared by the LO and the sample clock.
7. **Unverified at low IF (RXR-05).** Flicker below 2 MHz and IIP2 are both unverified. The NF is already +1.5 dB worse over 2–9 MHz than over 5–9 MHz. Running BLE/15.4/LoRa at a 1.5–3 MHz low IF costs no hardware.
8. **Self-spurs (SP-01/SUB-03, RF-RX-SPUR: fails today).** These are known and already demanded (AGND_RX, clock plan D10). The 40 MHz conv harmonics at 2400/2440/2480 MHz remain at −103…−84 dBm.

## Assumptions behind the numbers

- Chain: the scratch-selected **lna4_b** split-I/Q LNTA, `NOTES.md` (still unpublished). Chain NF 4.45 dB (5–9 MHz) / 5.97 dB (2–9 MHz) matched at the pad, chain voltage gain 41.7 dB to the TIA output. The published evidence is still the old LNA (12.1 dB NF, 28.9 dB gain).
- TIA linear swing assumed ±0.8 V diff pk (not simulated). The gain is referred to the matched 100 Ω input node. If the evidence's gain is EMF-referred, the max-input numbers move by up to 6 dB.
- ADC: 10-bit, ≈ 8 ENOB, FS ≈ ±0.87 V diff (converters README), 40 MS/s interleaved.
- PGA −6…42 dB in 3 dB steps; TIA offset DAC ≈ 8 mV/LSB, residual ≤ 4.5 mV (rf_rx README §7.1).
- Package/board: NF penalty 0.37/0.61/1.44/2.2 dB at P1–P4 (package-channel.md), balun ≤ 0.8 dB (B18), T/R switch 0.5 dB (B33), BAW 1.5–2.5 dB (B34).

### Sensitivity with real board losses (item 9)

NF at the antenna = 4.45 + 0.61 (P2) + 0.8 (balun) + 0.5 (switch) + 2.0 (BAW) ≈ **8.4 dB** (6.4 dB without the BAW). The ADC penalty is 2.4 dB (performance-requirements basis).

| Mode | Noise BW | SNR needed (incl. impl.) | Sensitivity with BAW / without | Requirement | Margin with BAW |
|---|---|---|---|---|---|
| Wi-Fi MCS0 | 18.9 MHz (72.8 dB) | 7 dB | −83.4 / −85.4 dBm | −82 | **+1.4 dB** |
| Wi-Fi MCS7 | same | 28 dB | −62.4 / −64.4 dBm | −64 | **−1.6 dB** (fails with BAW; +0.4 without) |
| BLE 1M | 1 MHz | 11 dB | −94.6 dBm | −70 (target −90) | +24.6 dB |
| 802.15.4 | 2 MHz | 5 dB | −97.6 dBm | −85 | +12.6 dB |

Narrowband modes have ample margin even with every loss included. **Wi-Fi MCS7 is the one at risk** once a coex filter is fitted. RF-RX-NFSYS (≤ 8 dB) is therefore marginal. The lowest-risk recovery is a low-loss BAW/balun selection, or omitting B34 in bench products.

### Blocker and reciprocal-mixing budget (items 1, 2, 5)

The reciprocal-mixing limit is L(f) ≤ −(I/C) − 10·log(BW) − (SNR + 3 dB):

| Case | I/C | Offset | Limit L(f) |
|---|---|---|---|
| BLE 1M, ±3 MHz blocker | 27 dB | 3 MHz | −101 dBc/Hz |
| Wi-Fi ACR adjacent, MCS0 | 16 dB | 20 MHz | −97 |
| Wi-Fi non-adjacent | 32 dB | 40 MHz | −113 |
| BLE OOB −30 dBm vs −67 dBm wanted | 37 dB | ≥ 100 MHz | −111 |
| UE TX +13 dBm, no BAW | 80 dB | 50 MHz | −154 (impossible) → −114 with B34 |

Mask set in RF-RX-LOPN with ≥ 6 dB margin. RF-LO-JIT 1.05 ps rms is −35.8 dBc integrated, which is fine for MCS7.

In-band intermodulation: the BLE intermod test (−50 dBm tones at 3 and 6 MHz, wanted −64 dBm) needs IIP3 ≥ −38 dBm. A TIA-limited IIP3 of ≈ −24 dBm (P1dB + 10) passes, so RF-RX-IIP3's −10 dBm matters mainly for out-of-band cellular blockers, which B34 handles. IIP2 must be ≥ +47 dBm for a −30 dBm AM blocker at zero-IF.

## Review table

Verdict: OK / gap / missing requirement (MR). Fix class: [chip], [board], [FPGA], [RTL].

| # | Item | Requirement | Evidence status | Quantified margin | Verdict | Lowest-risk fix | Owner |
|---|---|---|---|---|---|---|---|
| 1a | OOB cellular blockers (B40/B41/B7/B1/B3 UE TX) | MISSING → RF-RX-COEX, B34 | none | ≈ −45 dB without filter | MR + gap | [board] BAW coex filter B34 (35–45 dB, 1.5–2.5 dB IL) | board |
| 1b | Standard OOB blocking (BLE −30/−35 dBm) | RF-BLE-BLOCK | unverified | −35 dBm at 3 MHz offset vs ≈ −34 dBm TIA limit: ≈ 1 dB | gap | [chip] pre-filter gain steps (RXR-D1) | rf_rx |
| 1c | 5 GHz Wi-Fi / harmonic responses | MISSING → RF-RX-COEX | none | 2·LO response is double-balanced (≈ −30…−40 dBc); 5.15–5.85 GHz is outside 2·LO for LO ≤ 2.48 GHz; compression from +0 dBm at 5.5 GHz is the real issue | MR | [board] B34 ≥ 30 dB at 4.9–5.9 GHz | board |
| 1d | Front-end compression (LNA/TIA P1dB) | MISSING → RF-RX-MAXIN | not simulated | ≈ −34 dBm CW at high gain (estimate ±6 dB) | gap | [chip] RXR-D1 + 1 sim | rf_rx |
| 1e | Reciprocal mixing (LO phase noise) | MISSING → RF-RX-LOPN, B35 | none (external synth) | limits −97…−113 dBc/Hz; met by an LMX/ADF-class synth if specified | MR | [board] synth to B35 | board; timing |
| 2a | Max input (Wi-Fi −20, BLE −10, 15.4 −20 dBm) | MISSING → RF-RX-MAXIN | estimate | −24 dB (BLE, Wi-Fi), −14 dB (15.4); bypass −10/0 dB | **gap (top)** | [chip] TIA-R steps + LNA att (≥ 30 dB) | rf_rx; digital |
| 2b | Adjacent/alternate channel | RF-WIFI-ACR, RF-BLE-BLOCK | fails (ACR, pre-40 MS/s) / unverified | 40 MS/s ADC landed; pre-filter overload of alternate blockers 3–6 dB | gap | [chip] RXR-D1/D4; re-run ACR on 40 MS/s | converters; rf_rx |
| 2c | IIP3 | RF-RX-IIP3 | unverified | in-band need ≥ −38 dBm, estimate ≈ −24 dBm → OK in band; −10 dBm only with B34 for OOB | OK (est.) | 1 two-tone sim | rf_rx |
| 2d | IIP2 | MISSING → RF-RX-IIP2 | unverified | need ≥ +47 dBm | MR | [FPGA] low IF for narrowband; sim | rf_rx; FPGA |
| 2e | Pulsed blockers / saturation recovery (microwave oven) | MISSING → RF-RX-RECOV | not simulated | unknown | MR | sim; [FPGA] re-arm AGC on overload | rf_rx; FPGA |
| 3a | AGC gain range and steps | MISSING → RF-RX-AGC | PGA −6…42 / 3 dB extracted; pre-filter 3 dB | need ≥ 30 dB pre-filter: −27 dB short | **gap** | [chip] RXR-D1 | rf_rx |
| 3b | AGC loop latency (L-STF 8 µs, BLE preamble 8 µs) | MISSING → RF-RX-AGC | opcode4 spec only, not in RTL | SPI: ≈ 7.6 µs for 2 steps (−3.6 µs vs a 4 µs budget); opcode4 ≈ 4.8 µs | **gap** | [RTL] implement opcode4 | digital; FPGA |
| 3c | RSSI / power detection | RF-154-CCA (post-ADC only) | unverified | blind to out-of-channel blockers | gap | [chip] overload comparators + [FPGA] ADC RSSI | rf_rx; FPGA |
| 3d | ADC headroom / clip detection | MISSING → RF-RX-OVLD | ADC codes visible to FPGA | ADC clip: OK in FPGA; TIA clip: invisible | gap | [chip] RXR-D4 | rf_rx; digital |
| 4a | DC offset correction | MISSING → RF-RX-DCOC | static TIA cal, ≤ 4.5 mV residual | 65 % FS at PGA 42 dB; 16 % at 30 dB; dynamic 20 mV shift | **gap** | [chip] fine DAC after PGA; [FPGA] DC tracking, per-gain table | rf_rx; FPGA |
| 4b | LO leakage to antenna | RF-WIFI-LOLEAK (TX only) → RF-RX-LOLEAK | estimate −50…−65 dBm (IQ-01, XT-08) | 0–7 dB short at the pessimistic end vs −57 dBm | MR | A4 extraction; shields per XT-01 | rf_rx; assembly |
| 4c | Flicker for BLE/15.4 at zero/low IF | MISSING → RF-RX-FLICK | NF 2–9 MHz is +1.5 dB vs 5–9 MHz; < 2 MHz unmodelled | unknown | MR | [FPGA] low IF 1.5–3 MHz; NF-vs-IF sim | FPGA; rf_rx |
| 4d | IQ image rejection and calibration | RF-RX-IRR, RF-CS-IQ | meets (29 dB uncorrected, tt) | 35 dB after cal vs BLE image C/I −9 dB ⇒ ≥ 15 dB margin for low IF | OK | [FPGA] per-channel cal table | FPGA |
| 5a | Crystal ppm / AFC | RF-154-FTOL (TX); RX MISSING → RF-RX-FREF | none | ±100 ppm relative = ±245 kHz | MR | [board] one ±10 ppm TCXO (B35); [FPGA] CFO ±250 kHz + SFO | board; FPGA |
| 5b | LO integrated noise (EVM) | RF-LO-JIT | unverified | 1.05 ps ⇒ −35.8 dBc vs MCS7 ≈ −28 dB | OK if met | B35 | timing; board |
| 5c | LO pulling by own/nearby TX | LO-01 (n/a: external LO) | — | not applicable on first die (passive external LO) | OK | future LC LO at 2× f_RF | timing (future) |
| 5d | Hop settling (BT 625 µs slots, BLE, CS) | RF-CS-HOP, RF-154-TURN | unverified | warm hop 50 µs, CS 80 µs | covered | B35 synth settling | timing; board |
| 6a | TX/RX isolation and T/R switch | RF-TX-MUTE (fails); switch MISSING → B33 | none | with 25 dB switch: −25 dBm at RX during own 0 dBm TX (safe) | MR | [board] SPDT B33, FPGA-timed | board; FPGA |
| 6b | PTA / coex signalling | MISSING → RF-COEX-PTA | none | no chip pin needed | MR | [FPGA] 3-wire PTA | FPGA |
| 6c | Antenna diversity | RF-CS-ANT (N_AP = 1, FPGA switch) | unverified | — | OK (scoped) | [board] external switch | board; FPGA |
| 7a | Digital clock harmonics (SP-01) | MISSING → RF-RX-SPUR | A5: macro −88…−69, conv −103…−84 dBm | −12…+31 dB over the −100 dBm spec | gap (known, demanded) | AGND_RX pad + clock plan (D10) + conv-clock per channel | assembly; digital |
| 7b | Host-link SSN | PKG-08, SUB-03 | D2H slow slew < −113 dBm | ≥ 13 dB | OK | slew control (PKG-08) | digital |
| 7c | Board switching regulators | MISSING → RF-RX-PSRR, B37 | no RX PSRR evidence | unknown; 10 mV ripple at 30 dB PSRR ≈ 30 dB above the 1 MHz noise | MR | [board] LDO-clean supply B37; AC PSRR sim | board; rf_rx |
| 8a | Antenna-port ESD | MISSING → RF-RX-ESD, B36 (HBM per ESD-02) | 100 mA/2 ns screen, 0.105 V margin | IEC ±8 kV ≫ pad rating | MR | [board] low-C TVS B36 | board; pads |
| 8b | Overload damage (+10 dBm) | MISSING → RF-RX-ESD | estimate | ≈ 3.7 V gate peak vs ≈ 3.6 V: ≈ 0 margin | MR | +10 dBm transient sim; B36 / layout limiter if needed | rf_rx; pads |
| 8c | RX under supply noise | MISSING → RF-RX-PSRR | none (timing-only ripple screen) | unknown | MR | B37 + sim | rf_rx; board |
| 9a | Realistic NF incl. board | MISSING → RF-RX-NFSYS | scratch lna4_b 4.45 dB (unpublished) | 8.4 dB vs 8 dB (with BAW); MCS7 −1.6 dB | marginal | promote lna4_b; low-loss BAW/balun | rf_rx; board |
| 9b | Placement axis | B18/BP-3 | package-channel.md | +0.37…+2.2 dB P1–P4 | OK (≤ 10 mm) | BP-3 | board |
| 9c | Desense margin (spurs) | RF-RX-SPUR | A5 | see 7a | gap | as 7a | assembly |

## What was already covered and stays as is

RF-RX-IRR / RF-CS-IQ (image), RF-LO-JIT (integrated LO), RF-CS-HOP / RF-154-TURN (settling), PKG/BP-3 (placement), SP-01 / SUB-03 / AGND_RX and the D10 clock plan (spurs), LO-01 (no on-chip LO to pull on the first die), and RF-CS-ANT (diversity).

## Evidence actions (≤ 3 sims, rf_rx owner; RXR-D5)

1. Promoted lna4_b with the extracted mixers and TIA, at each gain state: P1dB, two-tone IIP3/IIP2, overload recovery after a −10 dBm pulse, and +10 dBm CW on the RF pad model (powered and unpowered).
2. Transient-noise NF versus IF over 10 kHz–10 MHz.
3. AC PSRR of the TIA plus filter.

These close RF-RX-MAXIN / IIP2 / RECOV / FLICK / ESD / PSRR, or convert them to fails with numbers.
