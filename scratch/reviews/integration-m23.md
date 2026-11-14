# Integration checks M2 (substrate coupling) and M3 (oscillator pulling, LO leakage, spurs)

Date: 2026-11-13. Scope: `scratch/reviews/integration-plan.md` rows M2 and M3. Work directory: `scratch/integration/m23-substrate-pulling/`.
No design file was changed. Demands for the re-pack are rows `INT23-*` in `scratch/reviews/interface-changes.md`. Risk rows are proposed in section 9 and not written into `spec/risk-register.md`.

Three values separated by slashes are optimistic / nominal / pessimistic. "Margin" is dB to the stated limit; negative fails.

## 1. Verdicts

| # | Mechanism | Verdict | Margin opt / nom / pess | What decides it |
|---|---|---|---|---|
| 1 | External LO pads (REF_IN, AUX_CLK) → RF_RX pads through bond-wire mutual inductance (LO leakage out of the antenna port, external-LO baseline mode) | **FAIL at 4 Vpp at every bound, independent of the floorplan**; at the 1.0 Vpp end of the CML window +3.5 / −4 / −14 dB | −8.5 / −16 / −26 dB against RF-RX-LOLEAK −57 dBm (4 Vpp) | Bond map: REF_IN pair is 0.89 mm from the RF_RX pair. Self-mixing DC stays inside the coarse trim (15 / 38 / 113 mV of ±250 mV). |
| 2 | Digital macro → bbfilter (in-band substrate noise × PGA gain) | **FAIL at PGA 42 dB (nominal and pessimistic); pass nominal at 24 dB** | 42 dB: +19 / −8 / −38 dB. 24 dB: +37 / +10 / −20 dB | 125–179 µm gap in v6; the in-band share of the macro bounce is an assumption (2 / 5 / 15 %), no data exists. |
| 3 | D2H lanes routed over or beside the converters, unshielded | **FAIL nominal over the ADC; fails pessimistic in the east corridor** | Over ADC: +14 / −15 / −48 dB. Corridor beside adc_q: +22 / −8 / −42 dB | Wire-to-substrate charge injection, 1.5 / 5 / 13 mA pk. A grounded metal shield under the lanes removes it. |
| 4 | Digital macro → dac_i / dac_q (22 µm gap, no rule exists) | Pass nominal, **fail pessimistic** | dac_i +33 / +12.5 / −7 dB (AP4-9 decap); +28 / +4 / −21 dB with the 0 nF that v6 places | TX spur at ±78.125 MHz in `tx_dac_direct` (no filter after the DAC). |
| 5 | QVCO: substrate and supply tones (digital 78.125 MHz, PA, rings) | Substrate: pass nominal at ≥ 800 µm from the macro in a tie sea; **pessimistic needs a grounded backside or deep n-well as well**. The 300 µm v6 rule gives −65 dBc. Supply: needs the separate regulated rail now in `spec/power-delivery.md` | −15 dB at 300 µm nominal; section 5 | QVCO is not placed in v6. 18.4 MHz/V on the substrate, 5.2 kHz per mV near f0 (extracted). |
| 6 | PA → QVCO injection pulling (VCO runs at the RF carrier) | Bond magnetic path: pass nominal, **marginal at the pessimistic bound**. Carrier-rate supply and substrate paths pass (≥ +15 dB). Envelope-rate supply pushing is M1's and needs the separate QVCO rail | Bond: +34 / +22.5 / −3 dB against a −35 dB EVM share (v6 seed position) | LO-01 is closed in the register on the rule "never run the VCO at f_RF"; the QVCO as built runs at f_RF. |
| 7 | Ring ↔ ring through the shared `pt_pll_vreg2` | **PASS at tt, regulated** (bypass is no longer an operating mode); corners not run | about +10 dB against 5 ps pk (upper bound 1.5 ps); measured output-to-output isolation −20…−27 dB, not the −30 dB estimated in PD36 | Section 7. |
| 8 | Digital macro → ADC I/Q through the substrate | Pass with the planned decap (**+1 dB at the pessimistic bound**); fails pessimistic with the 0 nF of v6 | adc_i +87 / +36 / +1 dB; 0 nF: +82 / +28 / −13 dB | 782 µm gap in v6. Aliases to 1.875 MHz when the converter clock is not host-derived. |
| 9 | pll_cdr ring (host-follow, RF mode) → adc_q / adc_i | Pass nominal, **fail pessimistic for adc_q** | adc_q +52 / +30 / −5 dB; adc_i +66 / +39 / +1 dB | 202 µm (adc_i) and 93 µm (adc_q) in v6. The 200 µm rule exists only for adc_i. |
| 9a | Forwarded wire clock route from AUX_CLK (3.1 mm, CP4-3) | Jitter from the macro: pass nominal, **fail pessimistic** if single-ended. Hand estimate | +15 / +2 / −8 dB against 5 ps | Section 7.1. Differential route passes. |
| 10 | Wired front end / wrx_cap → ADC, core_bias (wired mode) | Pass nominal, fail pessimistic; **pass by mode exclusion** if no converter runs in wired modes | adc_q +27 / +5 / −23 dB; core_bias +53 / +29 / −3 dB | wrx_cap is unplaced; required distance in section 4. |
| 11 | lo_mmd (2.4 GHz divider) → LNA, core_bias | LNA pass (+46 / +31 / +7 dB); core_bias pass nominal, −3 dB pessimistic | | lo_mmd abuts core_bias (76 µm) and sits 142 µm from the LNA in v6. |
| 12 | PA → LNA, ADC, bandgap through the substrate | **PASS**, ≥ +56 dB | | 1.8–3.2 mm in v6. SUB-07 can close on the substrate path. |
| 13 | LO → LNA from the on-chip QVCO (magnetic and substrate) | **PASS** | +17 / +22 / +9 dB against −57 dBm | Holds for a QVCO centre ≥ 1.3 mm from the west die edge. |
| 14 | PA → external-LO pads (bond coupling) | **PASS** | +55 / +41 / +22 dB against a −35 dB EVM share | 1.22 mm between the RF_TX and AUX_CLK pairs. |
| 15 | PA / LO subharmonics → ring PLLs (LO-03) | **PASS** | > +40 dB | 2.0–2.7 mm; the rings reject fundamental-rate supply tones. |
| 16 | Clock harmonics in 2.400–2.4835 GHz and on the baseband | 9 in-band lines in RF modes; 3 fail −100 dBm at the pessimistic bound by 15–31 dB (A5/M1 path). Table in section 8 | | Channel plan plus converter-clock choice. |

## 2. What is new against A1, A5 and M1

1. **A1 was one-sided.** It tied every surface cell that was not a victim to ground. With only block footprints tied (and no backside contact) the same pairs are 5–40 dB worse. Example, digital → adc_i on v6: −81.5 dB (dense ties, grounded back, victim tied) to −13.3 dB (sparse ties, floating back, floating probe). Distance alone buys about 10 dB per 0.5 mm on a floating-back, lightly tied die; a single narrow guard ring buys 3–7 dB.
2. **Backside contact is the largest single lever** (SUB-10): 20–45 dB at ≥ 0.5 mm. It is a board/assembly item (conductive die attach to the grounded paddle) and its contact to lightly doped p-silicon is not known to be ohmic. Both cases are reported everywhere.
3. **The frequency plan violates the closed rule LO-01.** The QVCO tunes 2.30–2.70 GHz and drives the mixers directly; the TX is direct-conversion with up to +9.5 dBm on chip at the same frequency.
4. **External-LO leakage through the bond wires** is larger than the conducted estimate in the register (−50…−65 dBm, IQ-01/XT-08) by 10–25 dB.
5. **`spec/package-channel.json` has a stale west pad order** (RF_TX next to AUX_CLK). The authoritative order in `contract.json` `bond_map_current` separates them by the BB_Q pair. The crosstalk table there must not be used for the west edge.
6. **The LO synthesizer is not instanced in any top netlist** (mode-walk MW-7). Every QVCO result here uses the block subcircuits directly and applies only once it is wired in.

## 3. Method and bench proofs

| Bench | Known answer | Result | Must-fail case |
|---|---|---|---|
| Substrate mesh (`m2/submesh.py`), 7-point resistive, 300 µm bulk | 1-D column 5.5 (exact); lateral divider 0.5; square-contact spreading resistance | exact; 0.50; 0.090 vs 0.118 half-space (finite slab with grounded back is lower, as expected) | Ground tie removed: the 0.5 check fails |
| Mesh convergence | 25 µm / 12 layers against the 50 µm / 6 layers used for sweeps | wrx_cap → ADC at 200 / 800 µm: bare −3.0 / −8.3 dB (fine) against −2.6 / −7.7 (coarse); grounded back −14.2 / −42.2 against −13.3 / −41.1; dense ties −15.7 / −43.5 against −12.0 / −39.0. The coarse mesh is 0.4–8 dB pessimistic | |
| Mutual inductance (`m3/mutual.py`), Neumann integral | Two coaxial loops, Maxwell closed form 220.657 pH | 220.654 pH (−0.001 %) | Orthogonal loops: 0.0 pH |
| Pulling measurement (`m3/adler_bench/bench.py`), ideal 2.4 GHz LC, Q 5 | Adler f_L = f0/(2Q)·I_inj/I_osc = 4.728 MHz | FM amplitude 4.754 MHz (+0.5 %); mean shift 0.300 vs 0.280 MHz; locks at 0.6 f_L (phase span 2·10⁻⁵ cycles) | 1.3 f_L does not lock (1.08 cycles slip); no injection: 0.2 kHz |
| Extracted QVCO r6b (`m3/qvco/`), RC-extracted, full-pessimistic tank, band 11, VTUNE 2.1 V | Adler with L 2.25 nH, V 1.42 V: 29.1 MHz/mA | 20.6 MHz/mA (0.71 of Adler: the quadrature coupling stiffens each core) | No injection: 2.1 kHz floor |
| Two extracted rings (`m3a/`) | Separate ideal supplies must show no pulling | Pull below 14 kHz at the clean line (k = 3), 27–48 kHz at k = 4, 8; k = 1, 2 read 65–128 kHz from bias drift in a 160 ns window (floor, not pulling) | 1 kΩ between ring-loop nodes of the two rings: locks (phase span 0.018 cycles). A 5 Ω shared supply and 3 kΩ / 300 Ω on a node outside the loop did not lock, so they are not valid controls |

Substrate mesh knobs, all reported two-sided: backside floating or grounded; ties dense (every non-victim cell, the A1 assumption) or sparse (block footprints and pad ring only, 0.3 of a full tie); surface layer ×1 or ×3 conductance; victim read as a floating probe (upper bound) or with its own taps to an ideal quiet ground. Voltage ratios do not depend on resistivity. Transimpedances scale with ρ = 5 / 10 / 30 Ω·cm; GF180 does not publish the value.

Aggressor amplitudes come from M1 (`scratch/reviews/integration-m1.md`): macro rail ripple 80 / 240 / 418 mV pk-pk with the AP4-9 decap and 150 / 620 / 2070 mV with the 0 nF that v6 places; half is taken on the ground side, so the substrate bounce at the macro is 20 / 60 / 105 mV pk (37 / 155 / 520 mV at 0 nF). Die VSS at 2421.875 MHz: 0.34 / 3.0 / 14.7 mV rms.

Victim rejection of substrate bounce is **assumed, not extracted**: ADC and DAC 40 / 30 / 20 dB, bbfilter 40 / 35 / 30 dB, bandgap 30 / 25 / 20 dB, LNA 38 / 35 / 33 dB (8 dB pad divider plus the A5 common-mode rejection). The only victim gain taken from an extracted netlist is the QVCO (section 5).

## 4. M2: substrate

### 4.1 v6 transfer matrix (`m2/v6_matrix_h50.json`)

dB from a 1 V bounce on the aggressor footprint to the worst 10 % of the victim footprint. Each cell: floating probe / victim tied.

| Aggressor → victim (v6 edge gap) | Sparse ties, floating back, ×3 skin (pessimistic) | Dense ties, floating back (nominal) | Dense ties, grounded back (optimistic) |
|---|---|---|---|
| digital → adc_i (782 µm) | −13.3 / −29.7 | −19.8 / −49.8 | −48.0 / −81.5 |
| digital → bbfilter_i (125 µm) | −2.8 / −6.8 | −6.0 / −16.8 | −11.4 / −20.8 |
| digital → dac_i (22 µm) | −1.3 / −2.6 | −2.2 / −7.2 | −3.6 / −8.1 |
| digital → lna (1422 µm) | −28.0 / −50.9 | −46.4 / −81.0 | −98.6 / −137.5 |
| digital → core_bias (2208 µm) | −36.8 / −74.0 | −57.4 / −114.2 | −132.8 / −204.0 |
| pll_cdr → adc_q (93 µm) | −4.8 / −9.3 | −9.4 / −21.8 | −14.5 / −25.9 |
| pll_cdr → adc_i (202 µm) | −9.5 / −15.5 | −18.5 / −31.3 | −28.9 / −40.4 |
| wired front end → adc_q (25 µm) | −1.6 / −4.9 | −2.8 / −12.9 | −6.1 / −14.9 |
| wired front end → core_bias | −10.2 / −17.4 | −17.7 / −33.3 | −30.1 / −42.8 |
| lo_mmd → lna (142 µm) | −3.2 / −6.7 | −8.6 / −17.4 | −13.4 / −20.8 |
| lo_mmd → core_bias (76 µm) | −1.8 / −3.2 | −3.1 / −8.0 | −4.3 / −8.6 |
| rfdriver → lna (2377 µm) | −62.6 / −80.6 | −96.9 / −123.2 | −182.2 / −213.9 |
| rfdriver → adc_i (1765 µm) | −52.6 / −70.5 | −75.2 / −106.6 | −141.3 / −181.0 |
| rfdriver → dac_i (22 µm) | −8.1 / −10.4 | −13.8 / −21.9 | −17.1 / −24.7 |

### 4.2 Budget on v6 (`m2/budget_v6.json`)

| Aggressor → victim | Limit | Bounce at the victim (mV pk) | Margin (dB) | Verdict |
|---|---|---|---|---|
| digital 78.125 MHz → adc_i, AP4-9 decap | 0.25 LSB (0.39 mV) | 0.002 / 0.19 / 3.4 | +87 / +36 / +1 | Pass |
| same, 0 nF as placed in v6 | 0.25 LSB | 0.003 / 0.50 / 17 | +82 / +28 / −13 | Fail pessimistic |
| digital → adc_q, AP4-9 | 0.25 LSB | 0 / 0.002 / 0.15 | ≥ +28 | Pass |
| digital → core_bias | 1 mV on VBG | 0 / 0 / 0.02 | ≥ +54 | Pass |
| digital → dac_i, AP4-9 | −40 dBr at ±78 MHz | 7.9 / 26 / 78 | +33 / +12.5 / −7 | Fail pessimistic |
| digital → dac_i, 0 nF | −40 dBr | 15 / 68 / 385 | +28 / +4 / −21 | Fail pessimistic |
| digital in-band → bbfilter_i, PGA 42 dB | 0.25 LSB at the ADC | 0.04 / 0.43 / 7.3 | +19 / −8 / −38 | **Fail** |
| same, PGA 24 dB | 0.25 LSB | same | +37 / +10 / −20 | Fail pessimistic |
| digital 2421.875 MHz → lna (substrate only) | −100 dBm | 0 / 0.0004 / 0.059 | +132 / +54 / +8 | Pass (the ground path of M1 dominates) |
| pll_cdr ring → adc_q | 0.25 LSB | 0.10 / 0.41 / 6.9 | +52 / +30 / −5 | Fail pessimistic |
| pll_cdr ring → adc_i | 0.25 LSB | 0.02 / 0.14 / 3.4 | +66 / +39 / +1 | Pass |
| wired front end → adc_q (wired mode) | 0.25 LSB | 1.8 / 6.8 / 57 | +27 / +5 / −23 | Fail pessimistic |
| wired front end → core_bias | 1 mV on VBG | 0.07 / 0.65 / 13.5 | +53 / +29 / −3 | Fail pessimistic |
| lo_mmd → lna | LO at RF_RX ≤ −57 dBm | 0.18 / 0.67 / 9.2 | +46 / +31 / +7 | Pass |
| lo_mmd → core_bias | 1 mV on VBG | 0.74 / 2.0 / 13.8 | +33 / +19 / −3 | Fail pessimistic |
| rfdriver, pad_rf_tx → lna | TX→RX isolation ≥ 30 dB | ≤ 0.002 | ≥ +117 | Pass |
| rfdriver → adc_i, core_bias | 0.25 LSB, 1 mV | ≤ 0.006 | ≥ +56 | Pass |
| rfdriver → dac_i | −40 dBr | 0.03 / 0.24 / 6.0 | ≥ +15 | Pass |
| D2H lanes over the ADCs (unshielded) → adc_i | 0.25 LSB | 7.6 / 67 / 1006 | +14 / −15 / −48 | **Fail** |
| D2H lanes, east corridor → adc_q | 0.25 LSB | 3.1 / 30 / 507 | +22 / −8 / −42 | **Fail** |
| D2H lanes, east corridor → pll_cdr | (ring supply/ground) | 7.1 / 55 / 721 | | Not judged: adds ring jitter |

The D2H rows treat the lane capacitance to substrate (0.9–2.4 pF for 12 lanes × 2.55 mm) as a current source of 1.5 / 5 / 13 mA pk. At the pessimistic end the source is no longer stiff, so the 0.5–1 V figures are upper bounds; the conclusion (fails without a shield) does not depend on them.

### 4.3 Required distance and guarding (`m2/sweep_h50_*.json`)

Transfer in dB with the victim tied (floating probe is 5–10 dB worse). d is the edge gap.

**wrx_cap (660 × 1450 µm) → ADC**

| d (µm) | Bare, floating back | Narrow rings on both | Wide strapped rings on both | Dense tie sea | Bare, grounded back | Wide rings, grounded back |
|---|---|---|---|---|---|---|
| 100 | −8.4 | | | −10.9 | −12.8 | |
| 200 | −10.8 | −13.6 | −17.7 | −17.3 | −18.1 | −26.5 |
| 300 | −12.6 | −17.8 | −23.5 | −22.5 | −22.8 | −36.8 |
| 500 | −15.4 | −21.5 | −28.9 | −31.6 | −32.1 | −48.4 |
| 800 | −18.9 | −25.6 | −33.8 | −44.8 | −45.9 | −62.5 |
| 1200 | −23.2 | −30.1 | −38.6 | −62.0 | −64.4 | −81.1 |
| 2000 | −31.3 | −38.4 | −47.0 | −96.2 | −101.6 | −118.3 |

Needed: −8 dB nominal (30 mV bounce, 30 dB rejection), −28 dB pessimistic (100 mV, 20 dB). The 200 µm rule in v6 passes nominal only. The pessimistic bound needs 500 µm with wide rings, 420 µm in a dense tie sea, or 400 µm with a grounded backside.

**Digital macro (1640 × 1700 µm) → QVCO**

| d (µm) | Bare, floating back | Wide rings on both | Dense tie sea | Bare, grounded back | Wide rings, grounded back |
|---|---|---|---|---|---|
| 200 | −10.0 | −17.5 | −17.2 | −17.7 | −26.6 |
| 300 | −11.6 | −23.0 | −22.2 | −22.4 | −36.8 |
| 500 | −14.3 | −28.1 | −31.3 | −31.7 | −48.3 |
| 800 | −17.8 | −32.8 | −44.2 | −45.6 | −62.3 |
| 1200 | −22.1 | −37.5 | −61.3 | −64.1 | −80.8 |

**Small aggressor (ring 210 × 800 µm, PA 200 × 480 µm) → QVCO**

| d (µm) | Bare, floating back | Wide rings on both | Dense tie sea | Bare, grounded back | Wide rings, grounded back |
|---|---|---|---|---|---|
| 200 | −13.5 | −23.6 | −23.4 | −22.3 | −31.9 |
| 300 | −15.5 | −29.4 | −29.0 | −26.7 | −42.3 |
| 500 | −18.6 | −35.0 | −38.7 | −36.2 | −54.5 |
| 800 | −22.4 | −39.5 | −52.5 | −50.5 | −68.3 |
| 1200 | −26.9 | −44.4 | −70.3 | −69.8 | −87.5 |
| 2000 | −35.2 | −52.9 | −105.3 | −107.6 | −125.1 |

Deep n-well under a victim's NMOS adds a series junction capacitance. For a 100 × 100 µm pocket (1–2 pF) against a few-ohm pocket tie this is ≥ 40 dB at 78 MHz and about 20 dB at 2.4 GHz. It is the only option that reaches the pessimistic bounds for bbfilter and dac_i without moving them.

## 5. QVCO as a victim (extracted `pt_lc_qvco5` r6b)

RC-extracted r6b, full-pessimistic tank (ss, 32 °C, 3.15 V), band 11, VTUNE 2.1 V, 2417.17 MHz, 1.42 V pk differential. The substrate node carries all NMOS bulks, all extracted wire capacitance to VSS and both spiral substrate legs (pessimistic lumping).

| Stimulus | Result | Meaning |
|---|---|---|
| 100 µA differential into the I tank at f0 + 50 MHz | FM 2064 kHz | 20.6 MHz of lock range per mA (0.71 × Adler) |
| 50 mV substrate tone at f0 + 50 MHz | FM 260 kHz | 5.2 kHz per mV |
| 10 mV VDD tone at f0 + 50 MHz | FM 23.8 kHz | 2.4 kHz per mV |
| +50 mV DC on the substrate | +0.92 MHz | 18.4 MHz/V quasi-static (supply pushing is −60 MHz/V) |
| none | 2.1 kHz | floor |

Allowed tone at the QVCO for −80 dBc: 0.85 mV at 78.125 MHz on the substrate (18.4 MHz/V; the varactor well adds about −85 dBc per mV by hand estimate), 0.26 mV at 78.125 MHz on the rail, 0.38 mV on the substrate for an RF line 10 MHz from the carrier, 0.63 mV for the ring's 4th harmonic at 2500 MHz. For the PA (co-frequency, −35 dB EVM share): 21 mV on the substrate, 46 mV on the rail.

| Aggressor | Bounce at the aggressor (mV pk) | Transfer needed | Meets it at |
|---|---|---|---|
| Macro, 78.125 MHz | 20 / 60 / 105 | −27 / −37 / −42 dB | 800 µm in a tie sea (−44 dB) nominal. Pessimistic: 800 µm plus grounded backside (−46 dB), or deep n-well under the QVCO NMOS. 300 µm (the v6 rule) gives −22 dB, a −65 dBc spur at nominal. |
| Macro, 2421.875 MHz line, carrier 10 MHz away | 0.5 / 4.2 / 20.8 | +2 / −21 / −35 dB | covered by the row above |
| Ring 4th harmonic (2500 MHz) | 0.05 / 0.2 / 1 (estimate) | none / none / −4 dB | ≥ 100 µm; keep the 500 µm rule (+15 dB) |
| PA ground and RF_TX pads at f0 | 2 / 8 / 30 | none | any distance ≥ 100 µm |

Supply: M1 finds the shared rail fails by 36–59 dB; `spec/power-delivery.md` now gives the QVCO its own regulated rail with ≥ 50 dB. That closes the nominal case and leaves −9 dB at the pessimistic bound (INT1-6). The substrate is then the larger path unless the keep-away above is met.

Not covered by these runs: the real tank loads (`lo_mmd` puts 201 / 126 fF on the I tank against 22 / 31 fF on the Q dummy) and the fill found in the spirals (tank wire C 1464 → 2678–2884 fF, signoff-gap). Both lower the swing and unbalance the tanks, which raises every sensitivity above; the size is not known.

## 6. M3b: PA pulling of the QVCO

**Frequency plan.** QVCO range 2.30–2.70 GHz (r5/r6b, RF-QVCO-RANGE), I/Q taken from the two tanks, `lo_ext` internal mode to the mixer gates, no divider in the LO path (`lo_mmd` is the PLL feedback divider). TX is direct conversion; the rfdriver delivers +5.1 dBm linear and +9.5 dBm saturated at the carrier. So the PA output sits on the VCO frequency and carries the modulation. Risk LO-01 ("run the VCO at 2× or 4/3× f_RF, never at f_RF") is marked closed; the built QVCO does not follow it.

**Model.** An injection equivalent to a series EMF e in the tank gives a one-sided lock range f_L = 0.71·f0·e/(2·V_tank) (Adler; Q cancels; 0.71 from the extracted-QVCO run). The injection is co-frequency and modulated, so above the 300 kHz loop bandwidth the VCO integrates it: θ_rms = Δf_rms/√(B·f_c) with B = 10 MHz (HE20), 8 dB back-off. Limit: a −35 dB EVM share (RF-WIFI-EVM is −27 dB at MCS7), which is f_L ≤ 109 kHz peak, e ≤ 179 µV, an injection 78 dB below the tank swing. Constant-envelope modes see a static phase offset only.

**Path 1, RF_TX bond pair → tank spirals (magnetic).** Bond current 4 / 12 / 35 mA pk (load current only … plus the pad-capacitance current that circulates through the board choke). M from the Neumann integral with and without the image in the paddle. Spiral centre dx from the west die edge, dy along the edge from the RF_TX pads:

| dx (µm) | dy (µm) | M (pH) | f_L peak (kHz) | EVM share (dB) | Margin to −35 dB |
|---|---|---|---|---|---|
| 1300 | 0 | 0.14 / 0.16 / 0.16 | 7.6 / 25 / 73 | −58 / −48 / −38.5 | +23 / +13 / +3.5 |
| 1300 | 1000 | 0.10 / 0.12 / 0.30 | 5.5 / 20 / 142 | −61 / −50 / −33 | +26 / +15 / −2 |
| 1300 | 2000 (v6 seed) | 0.04 / 0.05 / 0.33 | 2.1 / 8.2 / 152 | −69 / −57.5 / −32 | +34 / +22.5 / −3 |
| 1700 | 1000 | 0.045 / 0.053 / 0.086 | 2.4 / 8.5 / 40 | −68 / −57 / −44 | +33 / +22 / +9 |
| 2200 | 1000 | 0.018 / 0.021 / 0.027 | 0.9 / 3.3 / 13 | −76 / −65 / −54 | +41 / +30 / +19 |
| 3000 | 2000 | 0.004 / 0.005 / 0.003 | 0.2 / 0.8 / 2.3 | −90 / −78 / −69 | ≥ +34 |

The pessimistic column has no ground-plane image and is not monotonic in distance. With the image (the die sits on a grounded 4 × 5.2 mm paddle) every position ≥ 1.3 mm from the edge passes by ≥ 13 dB. Demand: QVCO spiral centres ≥ 1.7 mm from the west die edge and ≥ 1.0 mm along the edge from the RF_TX pads (passes at the pessimistic bound with +9 dB).

**Path 2, supply.** 2.4 kHz of lock range per mV of rail tone near f0 (extracted), so 46 mV is allowed. 61 % of the rfdriver current enters through the RF_TX pads from the board; the die rail carries the rest, almost all DC. A 5–10 % imbalance leaves 0.5–2 mA at f0 across 0.3–3 Ω, 0.15–6 mV: margin +50 / +30 / +18 dB even on a shared rail. A tone at 2·f0 on the rail or the tail node was not simulated. The envelope-rate pushing (PA current against modulation, −31 / −21 dBc on the shared rail) is M1's INT1-6 and needs the separate QVCO regulator.

**Path 3, substrate.** 21 mV is allowed at the QVCO. Pad and driver bounce of 2 / 8 / 30 mV at ≥ 500 µm arrives at ≤ 0.03 / 0.1 / 3.5 mV: margin ≥ +15 dB.

**Path 4, back through the LO chain** (PA input ← mixer drains ← commutator gates ← `lo_ext` CML ← QVCO buffers): hand estimate −118…−148 dB below the tank swing, against the −78 dB limit. Not simulated.

**PA or LO subharmonics into the rings (LO-03).** f_LO/4 = 600–621 MHz lies 0.7–4 % from the 625 MHz host-follow ring. PA substrate bounce reaches pll_cdr at −74 dB or lower (v6), and the rings do not respond to fundamental-rate supply tones (section 7). Pass, > 40 dB.

## 7. M3a: two extracted rings on one extracted `pt_pll_vreg2`

Both rings are the extracted `pt_pll_ring` (r9), open loop with fixed VCTRL; the regulator is the extracted `pt_pll_vreg2` with its gate held at the 7 mA operating point through its own 20 kΩ ATB_G leaf; the island rail is 2 Ω / 50 pF behind an ideal source. tt, 27 °C.

| Run | Rings (MHz), offset | Supply | Pull of ring A / B, kHz, at k × offset |
|---|---|---|---|
| Null (`f3`) | 668.0 / 689.0, 3.1 % | separate ideal | k1 70 / 65, k2 128 / 117, k3 10 / 14, k4 27 / 32, k8 48 / 38 |
| Regulated (`z3`) | 666.2 / 687.0, 3.1 % | vreg2, VOUT 2.84 V | k1 87 / 93, k2 132 / 99, k3 16 / 17, k4 698 / 503, k8 851 / 192 |
| Bypass (`b3`, information only) | 676.1 / 697.5, 3.2 % | vreg2 BYP | k1 72 / 72, k2 173 / 149, k3 20 / 20, k4 320 / 272, k8 384 / 311 |
| Null (`c_free`) | 1024.2 / 1033.5, 0.9 % | separate ideal | k2 11 / 10, k4 9 / 12, k8 2 / 4 |
| Bypass (`c_byp`) | 1069.6 / 1083.0, 1.3 % | vreg2 BYP | k2 29 / 26, k4 30 / 24, k8 5 / 21 |
| Shared 5 Ω node (`c_strong`) | 1021.4 / 1030.6, 0.9 % | one node, 14 mV pk-pk | k2 19 / 21, k4 5 / 8, k8 8 / 4 |
| Lock control (`d_lock3`) | 1024 / 1033 free | 1 kΩ between loop nodes | locks |

Reading:
- At k = 1, 2, 3 the regulated and bypass runs equal the null within 40 kHz. No pulling is resolved.
- The large k = 4 and k = 8 values of the 3.1 % runs are not ring-to-ring pulling: 4 × offset = 83.3 MHz is ring A's own f/8 divider line and 8 × offset its f/4 line (an unlucky choice of offset). They appear only on the regulator, so they are each ring's own divider current on its 1/gm supply. That is self-jitter (0.5–0.85 MHz of FM at f/8 and f/4, about 1–2 ps pk), already inside the ring's stand-alone jitter figures if those were taken on the regulator.
- Direct measurement of the coupling (`m3a/xrip.py`): ripple of one output seen on the other is −19.8 / −24.0 dB at the ring fundamental and −25.6 / −27.5 dB at 8 f (regulated), −12.2 dB and −28…−38 dB in bypass. PD36 estimated −30 dB. In absolute terms ring B puts 0.10 mV at its fundamental on ring A's supply.
- Upper bound on the lock range: 0.10 mV × 150 MHz/V (A3 static pushing, the most a tone can do) = 15 kHz, 22 ppm of 666 MHz. The 1 GHz bypass run gives ≤ 30 kHz at the clean k = 4 line.
- Closed loop: each PLL (2.6 MHz bandwidth) holds its own frequency, so the rings do not lock; the residue is a phase spur at the beat, ≤ f_L / 2.6 MHz = 5.8 mrad = 1.5 ps pk at 625 MHz against the 5 ps limit.

A 5 Ω shared supply did not lock the rings and neither did a resistor on a node outside the oscillation loop, so those were rejected as controls; the control that counts is the 1 kΩ tie between loop nodes, which locks. Two earlier regulated runs were discarded: a `.ic` on the regulator gate was not honoured and the output sat at 2.06 V.

### 7.1 Forwarded wire clock on the AUX_CLK pair (CP4-3), ~3.1 mm on-die route, ≤ 810 MHz

No extracted route exists; hand estimates.

| Question | Estimate | Verdict |
|---|---|---|
| Jitter picked up from the digital macro (single-ended CMOS route, driver and receiver on different grounds; ground difference 20 / 60 / 105 mV pk at 78.125 MHz, edge 22 / 15 / 8 V/ns at the far end) | 0.9 / 4 / 13 ps pk | +15 / +2 / −8 dB against 5 ps. Pass nominal, fail pessimistic. |
| same, differential route regenerated at the wired island | ≥ 20 dB lower | Pass |
| Route as an aggressor in RF modes (AUX_CLK used as a 40 / 80 MHz converter clock; 0.45 pF, 3.3 V): 60th harmonic about 23 µA into the substrate along the route | 0.2–1.9 mV at 2.4 GHz under the route; QVCO spur −70…−50 dBc if the route passes within 200 µm of the tank; LNA 0.1–1.3 µV rms against 2.24 µV | Marginal; avoid by routing rule |
| Route taken from the pad net instead of from the `rx_aux_clk` output | 0.5 pF stub on the Q LO pad only (quadrature error) and 1–4.5 Vpp of 2.4 GHz carried 3.1 mm across the die | Must not be done |
| AUX_CLK bond pair → RF_RX pair at 810 MHz | wired mode, LNA off | No demand |

## 8. M3c and M3d: LO leakage, spur table

### 8.1 LO at the LNA input

| Path | LO at RF_RX (dBm) | Margin to −57 dBm | Self-mixing DC at the filter input (trim ±250 mV) |
|---|---|---|---|
| On-chip QVCO spirals → RF_RX bond pair, QVCO at dx 1300 µm, dy 0–1000 µm | −74 / −73 / −67 | +17 / +16 / +10 | 0.8 / 0.9 / 1.8 mV |
| same, QVCO at dx 1700 µm | −83 / −82 / −72 | +26 / +25 / +15 | ≤ 1.1 mV |
| QVCO / LO routes → LNA through the substrate (8 / 20 / 40 mV common-mode at the tank, QVCO ≥ 200 µm from the LNA) | ≤ −75 | ≥ +18 | < 1 mV |
| lo_mmd → LNA through the substrate (v6, 142 µm) | −103 / −88 / −64 | +46 / +31 / +7 | ≤ 1.5 mV |
| **External LO: REF_IN pair → RF_RX pair, 0.89 mm (bond map)** | **−48.5 / −41 / −31** | **−8.5 / −16 / −26** | 15 / 38 / 113 mV |
| External LO: AUX_CLK pair → RF_RX pair, 1.74 mm | −69 / −60 / −46 | +12 / +3 / −11 | 1.4 / 4 / 22 mV |
| Conducted through mixer and LNA (existing estimate, IQ-01/XT-08) | −65 … −50 | +8 … −7 | |

The die-1 baseline is external LO through the CML driver (`lo_mode` 3), qualified for 1.0–4.5 Vpp. The table is for 4 Vpp differential; leakage scales as 20·log(V/4 Vpp): at 1.0 Vpp it is −60.5 / −53 / −43 dBm (+3.5 / −4 / −14 dB), and it passes at nominal only below 0.63 Vpp, at the pessimistic bound below 0.2 Vpp.

External-LO assumptions: 1 V pk per leg at the pad, pad plus clamp plus load 1.0 / 1.5 / 2.0 pF, so 15 / 23 / 31 mA pk in each LO bond; M 10 / 16 / 36 pH (cross-check by the long-pair formula: 29 pH without the image, 12.6 pH with it). The BB_I bond pair lies between the two pairs and is not a shield. The LNA source down-bonds form a second loop of similar area and were not added.

The re-radiation limit fails in the external-LO baseline at every bound. The DC offset stays inside the coarse trim but takes 6 / 15 / 45 % of it, and it moves with the antenna match. Pad sites are fixed by the bond map, so no floorplan change helps. Options: (a) run the CML path at the bottom of its window (1.0 Vpp: 12 dB better, still −4 dB at nominal) and extend the window downward; (b) move REF_IN ≥ 1.7 mm (nominal) from RF_RX in the bond map; (c) waive RF-RX-LOLEAK for the external-LO bench mode and qualify it on the QVCO only.

### 8.2 Spur table (`m3/spurs.py`, `m3/spurs.json`)

Lines inside 2400–2483.5 MHz. Levels use the A5 shared-ground model unchanged; M1 gives −81 / −62 / −49 dBm for the 2421.875 MHz line with D2H included.

| f (MHz) | Source | n | Mode | Level best … worst (dBm) | Margin to −100 dBm (worst) |
|---|---|---|---|---|---|
| 2400.000 | converter clock 40 MHz (int/ref/aux) | 60 | RF | −103 … −84 | −16 |
| 2400.000 | converter clock 80 MHz | 30 | RF | −97 … −78 | −22 |
| 2400.000 | LO reference 50 MHz | 48 | RF | −120 … −101 | +1 |
| 2400.000 | ring 480 MHz | 5 | wired | −78 … −59 | −41 |
| 2400 + 20k | converter per-core 20 MHz | 120–124 | RF | −115 … −96 | −4 |
| 2421.875 | macro core 78.125 MHz | 31 | RF | −88 … −69 | −31 |
| 2421.875 | converter clock 78.125 MHz (ring/8) | 31 | RF | −97 … −78 | −22 |
| 2421.875, 2460.938 | converter clock 39.0625 MHz (ring/16) | 62, 63 | RF | −103 … −84 | −16 |
| 2421.875 | D2H 78.125 MHz DDR, slow / fast slew | 31 | RF | −133 … −114 / −123 … −104 | +14 / +4 |
| 2430.000 | ring 810 MHz; wrx_cap at 810 MHz | 3 | wired | −76 … −57; −66 … −47 | −43; −53 |
| 2437.500 | macro core 62.5 MHz (125 MHz host, GX-5) | 39 | RF | −90 … −71 | −29 |
| 2440, 2480 | converter clock 40 MHz (80 MHz: 2480 only) | 61, 62 (31) | RF | −103 … −84 (−98 … −79) | −16 (−21) |
| 2450.000 | LO reference 50 MHz | 49 | RF | −121 … −102 | +2 |
| 2432.7, 2480.4 | aosc 47.7 MHz (40–60 MHz over corners) | 51, 52 | off in RF by rule | −123 … −104 | +4 |

Not in band: 2500.000 MHz = 4 × 625 (host-follow ring) = 16 × 156.25 = 32 × 78.125 = 8 × 312.5 = 5 × 500, which is 16.5 MHz above the band edge and 20 MHz from a 2480 MHz carrier. Rings at 625, 750, 742.5 and 741.76 MHz have no harmonic in the band.

Carrier-derived D2H (clock LO/32, words LO/16): the 32nd harmonic of the D2H clock is the LO itself on every channel. It is coherent, so it mixes to DC with a data-dependent amplitude: −133 … −114 dBm (slow slew), −123 … −104 dBm (fast slew). Pass with slow slew.

Baseband (the line couples into the bbfilter or ADC input and aliases):

| Converter clock | Asynchronous aggressor | Alias (MHz) |
|---|---|---|
| 40 or 80 MHz (int/ref/aux) | macro 78.125 MHz and D2H, n = 1…5 | 1.875, 3.75, 5.625, 7.5, 9.375 |
| 40 or 80 MHz | H2D 156.25 MHz clock, 312.5 Mword/s | 3.75, 7.5 |
| 40 MHz | host-follow ring 625 MHz, n = 3, 5 | 5.0 |
| 39.0625 or 78.125 MHz (host-follow) | every 78.125 / 156.25 / 312.5 / 625 MHz line | 0 (DC or Nyquist) |
| 39.0625 MHz | 125 MHz host and its 62.5 MHz core, 500 MHz ring | 7.8125 |

A host-derived converter clock (39.0625 / 78.125 MHz with the 156.25 MHz host) puts every digital line at DC. That is the same recommendation as INT1-9 and removes verdicts 8 and 9 for the aliasing part. With the 125 MHz host the converter clock must be 62.5 / 2ⁿ MHz for the same effect.

## 9. Proposed risk-register changes (not applied)

| ID | Change |
|---|---|
| LO-01 | Reopen. The closure rule is violated by the as-built QVCO. Evidence: section 6. |
| LO-02 | Close at tt on the simulated result (section 7); keep a corner run (ss/ff) as the residual. Record the measured −20…−27 dB isolation in PD36. |
| LO-03 | Close on the substrate and supply paths (section 6, last paragraph), conditional on rfdriver ≥ 1 mm from both rings. |
| SUB-01 | Keep demanded. The 210 µm floor is a nominal figure only; the pessimistic bound needs the AP4-9 decap and holds with +1 dB at 782 µm. |
| SUB-07 | Close for LNA, ADC, bandgap (≥ +56 dB). Add the dac_i adjacency (22 µm) as the remaining PA item: passes, +15 dB. |
| SUB-11 | Mesh reduced and run on v6; keep open until the victims' substrate gains are extracted (section 10). |
| XT-05 | Raise: 20 µm spacing is not enough for D2H lanes; a shield under the lanes is needed (section 4.2). |
| XT-08 / IQ-01 | Add the bond-coupled external-LO path (section 8.1). |
| new | Digital macro → dac_i / dac_q: no rule in v6; 22 µm. |
| new | Digital macro → bbfilter in-band coupling at high PGA gain. |
| new | `package-channel.json` west pad order is stale against `contract.json` `bond_map_current`. |

## 10. Not verified

- Substrate resistivity, the surface layer and the backside contact are unknown; all three are bounded, not measured.
- Victim rejection of substrate and ground bounce is assumed for the ADC, refbuf, DAC, bbfilter, bandgap and LNA. No extracted netlist separates the substrate from VSS (Magic merges them). Only the QVCO was simulated with a split substrate node.
- The in-band (< 10 MHz) share of the macro's bounce (2 / 5 / 15 %) is a guess; verdict 2 scales directly with it.
- QVCO: the n-well-to-substrate junction of the varactors is not in the extracted netlist (analytic estimate used); one corner only (ss, 32 °C, 3.15 V, full-pessimistic tank, band 11); the spiral substrate network is the single-π model, not EM.
- Mutual inductances are filament models of bonds whose loop shape is assumed; no EM, no measured bond profile. The LNA down-bond loop is not included.
- PA bond current: the circulating pad-capacitance current depends on the board match.
- The forwarded-clock route (section 7.1) is a hand estimate; there is no route to extract.
- A die supply trimmed up to 3.50 V on slow dies raises every swing by ≤ 0.6 dB; not rerun.
- Rings: open loop, tt only, 160–190 ns windows, two offsets; closed-loop pulling is derived from the open-loop injection strength, not simulated. The k = 4 and k = 8 beat lines of the regulated run coincide with the ring's own /8 and /4 divider lines and could not be separated.
- Spur levels reuse the A5 charge and ground-impedance figures; they are not re-derived.
- qvco, wrx_cap, refbuf, lo_ext and wiredtx are unplaced in v6; their rows are distance sweeps.
- 50 µm mesh for all sweeps (guard rings are one cell wide).
