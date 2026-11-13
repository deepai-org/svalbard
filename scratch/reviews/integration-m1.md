# Integration check M1 (+M4): chip-level power delivery and supply noise

Date: 2026-11-13. Scope: `scratch/reviews/integration-plan.md` rows M1 and M4. Model and outputs: `scratch/integration/m1-pdn/`.
No design file was changed. Risk-register rows are proposed here (section 8) and not written into `spec/risk-register.md`.

## 1. Answers

| Question | Answer |
| --- | --- |
| How much decap, where? | The amount is set by the digital macro's charge per 78.125 MHz cycle, which the evidence bounds at 0.31–1.05 nC (24.5–81.8 mA). **3 nF is enough only at the 24.5 mA floor.** At the PWR-DIG requirement (60 mA, 0.77 nC) 3 nF leaves 219–294 mV pk-pk at the macro and 137–178 mV at core_bias and the LO/PLL island. About **6–8 nF in or directly at the macro** is needed for ≤ 100–135 mV pk-pk, or the digital current at 78.125 MHz must come down to ≤ 25–30 mA. Decap in the macro is 1.3–2× more effective than the same amount spread over the analog core. |
| Is the AP4-9 plan (MIM over blocks + macro fill) enough? | No at the stated minimum (1.7 nF MIM + 0.45 nF fill): 83 / 305 / 700 mV pk-pk at the macro (opt / nom / pess), \|Z\| 1.08–1.49 Ω peak (A2 target ≤ 1 Ω). The measured fillcap density is 0.541 fF/µm², so the macro's free rows give ≈ 0.45 nF, not the 1–3 nF assumed in AP4-8 and PDN-02. AP4-9 at 100 % (5.7 nF + 1 nF) gives 80 / 240 / 418 mV. It needs ≥ 1.5 nF more MOS decap at the macro to meet \|Z\| ≤ 1 Ω. |
| Is the bond allocation adequate? | For inductance and ring-level DC drop, yes (L_eff ≈ 0.5 nH, ring drop 15–44 mV of 117). For per-bond current and placement, marginal: there is no supply bond on the south edge (D2H row, 117 mA) or the north edge (digital macro). Bond 18 carries 63–79 mA and bond 64 carries 62–72 mA at the evidence currents against the 60 mA per-cell planning rating; one open supply bond raises a neighbour to 81–84 mA. The 8 COB strip capacitors are mandatory. |
| Which rails must be split? | (1) **QVCO/LO**: needs its own regulated rail; a dedicated bond alone gains only 9–13 dB. (2) **LNA ground**: the die VSS moves 0.3–15 mV rms against board ground at 2421.875 MHz, so the LNA must reference its own ground (AGND_RX / the downbonds), as A5 demanded. (3) **D2H driver rail**: a split removes D2H from the core rail (14–113 mV → 0.3–10 mV at the macro) and improves the RX spur by 16–18 dB, but only with its own ≥ 1 nF decap; optional. (4) Rings: keep behind pll_vreg2, never in bypass on the shared rail. |
| Which victims fail even with the planned decap? | QVCO (by 36–59 dB against −80 dBc), static IR at the rf / wired / pll island taps, RX spur at the LNA (−81…−49 dBm against −100 dBm), ring PLL in bypass mode (13–77 ps DJ), ring PLL regulated at the pessimistic end (6.3 ps against 5 ps). ADC and core_bias cannot be judged: no PSRR evidence exists. POR passes. |

## 2. Ranked findings

Three numbers separated by slashes are optimistic / nominal / pessimistic (section 4 defines the three sets).

### F1. Static IR: the 117 mV budget is spent before the island straps, and v6 has no strap plan (critical)

- v6 has no top-level supply grid. With a Metal5 strap grid at 8 % coverage per net (my nominal assumption), the drop from the source to the island switches plus the VSS rise is 102 mV at the evidence currents. The island switch adds 27–30 mV, so the rf, wired and pll islands are over 117 mV with a zero-length island strap.
- Coverage needed (nominal ring and bonds, evidence currents, `e1_static.py`):

| Metal5 coverage per net | Sheet (Ω/sq) | Source → switch + VSS rise | Digital macro |
| ---: | ---: | ---: | ---: |
| 4 % | 1.50 | 172 mV | 88 mV |
| 8 % | 0.75 | 102 mV | 67 mV |
| 15 % | 0.40 | 67 mV | 50 mV |
| 25 % | 0.24 | 49 mV | 39 mV |
| 40 % | 0.15 | 39 mV | 32 mV |

- With 25 % coverage and a 30 mV switch, about 38 mV is left for the island strap. For the rfdriver (61.7 mA) that is ≤ 0.6 Ω: 200 µm of a 20 µm Metal5 strap, or 600 µm at 60 µm.
- v6 places the loads 0.6–4.1 mm (Manhattan) from their switches: rfdriver 1.29 mm, lna 1.76 mm, wiredtx 2.1 mm, USB pad 1.67 mm, pll_vreg2 4.1 mm. With a single 20–60 µm strap that gives:

| Tap | Island | mA | Total drop opt / nom / pess (mV) | Nominal split: to switch / switch / strap / VSS |
| --- | --- | ---: | --- | --- |
| rfdriver | rf | 61.7 | 139 / 277 / 488 | 63 / 30 / 159 / 24 |
| wiredtx | wired | 36.0 | 137 / 274 / 490 | 67 / 27 / 154 / 26 |
| lna | rf | 18.9 | 99 / 181 / 319 | 63 / 30 / 66 / 21 |
| usbhs | wired | 24.0 | 73 / 143 / 253 | 36 / 10 / 81 / 17 |
| clocktree | pll | 12.0 | 87 / 152 / 271 | 61 / 30 / 38 / 23 |
| slicer | wired | 16.1 | 79 / 135 / 243 | 67 / 27 / 22 / 19 |
| digital macro | raw | 81.8 | 40 / 67 / 118 | — |
| adc_i | conv | 5.7 | 39 / 65 / 110 | 22 / 6 / 18 / 20 |
| core_bias | raw | 1.0 | 24 / 31 / 42 | — |

- The strap numbers reflect the v6 placement (the placer scattered blocks and left 14 unplaced) and my strap-width assumption. They are a requirement on v7, not a prediction of silicon: each island's loads must abut its switch, and the grid needs ≥ 25 % top-metal coverage per net or equivalent.
- AP4-10(b), the core ring 2 × 25 µm → 2 × 12 µm, costs only 0.5–0.9 mV, because the provider ring rails (DVDD 124 µm, DVSS 101 µm on each of Metal3/4/5) carry the ring current. That holds only if those rails continue through the custom pad families, which I could not check (section 7).

### F2. Island and mode currents in block evidence exceed the switches and the ceilings (critical, found while collecting loads)

| Island | Switch design current | Budget allocation | With block evidence | What is missing from the budget |
| --- | ---: | ---: | ---: | --- |
| rf | 55 mA | 99.1 mA (rf_tx) | 99.1 mA | rfdriver 61.7 mA alone exceeds the switch; LNA stays warm in TX |
| pll | 60 mA | 56.2 mA | 103.2 mA | LO chain: QVCO 25 + lo_mmd 34 + lo_ext 16 + polyphase 2.8 mA, against rfpll 12 + quadrature 18.8 allocated |
| wired | 80 mA | 62.9 mA | 109.5 mA | pt_wrx_cap 46.6 mA extracted (19.8 schematic); it is in no budget and no island list |

- Mode totals with these currents: wired 344–347 mA (ceiling 292), rf_tx autonomous 351 mA (ceiling 240), rf_rx autonomous 295 mA (ceiling 240). At 3.35 V that is 1.15–1.18 W against the 0.98 W thermal design point.
- The rf-island figure depends on how much rfdriver current arrives through the RF_TX pad feed instead of the island rail. The rf_tx benches tie both to one node, so the split is not in evidence. At 80 % through the pads the rfdriver tap drop falls from 277 mV to under 186 mV.
- The LO chain has no island or rail of its own in `island_support`; the model puts it on the pll island, following `analog-architecture.json` (`quadrature`, `rfpll`).

### F3. Decap: the demand is 2–3× the 3 nF plan unless the digital current drops (critical)

Steady-state ripple from the macro's charge packets, wired mode (`e4_decap_req.py`). Hand check: pk-pk ≈ Q(1 − t_w/T)/C; 0.77 nC into 3.5 nF gives 180 mV before resonance gain.

| Added decap | In/at the macro: pk-pk at macro (mV) | Same, at core_bias | Spread over analog core: at macro | D2H pk-pk at macro |
| ---: | --- | --- | --- | --- |
| 0 (v6 as placed) | 150 / 620 / 2074 | 116 / 424 / 1187 | 150 / 620 / 2074 | 37 / 174 / 676 |
| 1 nF | 118 / 417 / 830 | 94 / 295 / 471 | 125 / 495 / 1306 | 30 / 136 / 317 |
| 3 nF | 68 / 219 / 361 | 49 / 137 / 183 | 74 / 294 / 772 | 13 / 45 / 96 |
| 4 nF | 63 / 190 / 272 | 44 / 118 / 139 | 72 / 285 / 714 | 10 / 35 / 69 |
| 6 nF | 57 / 134 / 170 | 40 / 87 / 90 | 78 / 280 / 619 | 7 / 23 / 44 |
| 8 nF | 45 / 95 / 123 | 33 / 64 / 65 | 78 / 235 / 533 | 5 / 18 / 34 |
| 12 nF | 26 / 58 / 82 | 20 / 39 / 41 | 49 / 166 / 436 | 3 / 12 / 23 |

- Charge per cycle: 0.31 nC (24.5 mA clock-pin floor) / 0.77 nC (60 mA requirement) / 1.05 nC (81.8 mA vectorless). A2 used 0.25–0.47 nC, which is why it reported 72–83 mV.
- The "0 nF" rows are a linear-model bound; a real macro would slow down before the rail collapsed by volts.
- No dynamic-ripple limit exists for the macro. STA runs at a fixed 3.3 V. This needs a number (I suggest ≤ 150 mV pk-pk, ±2.3 %) and a matching timing derate.
- Area: 6 nF at the stacked 4.33 fF/µm² is 1.39 mm²; at MOS-only 2.33 fF/µm² it is 2.6 mm². Neither fits v6. The cheaper lever is charge per cycle: clock gating by mode, and skewing the hword/hcore launch phases so the packets do not coincide.

### F4. Anti-resonance: 0.5–1.5 nF lands on 156.25 MHz; 6–8 nF lands on 78.125 MHz; Q is low (M4)

Impedance seen by the macro (`e2_impedance.py`), strip caps populated unless noted:

| Decap plan | Anti-resonance (MHz) | \|Z\| peak (Ω) | Q | \|Z\| at 78.125 | at 156.25 | at 312.5 | at 625 | at 2400 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| none | 174 / 195 / 245 | 1.07 / 1.55 / 2.57 | 1.8 | 0.31–0.64 | 0.98–1.27 | 0.44–1.85 | 0.29–0.85 | 0.32–0.68 |
| none, no strip caps | 149 / 161 / 195 | 1.31 / 2.03 / 3.60 | 2.0–2.2 | 0.44–0.87 | 1.27–2.42 | 0.40–1.49 | 0.28–0.81 | 0.32–0.67 |
| 1 nF MOS spread | 143 / 149 / 156 | 1.05 / 1.40 / 1.91 | 2.0–2.4 | 0.34–0.71 | **0.95–1.91** | 0.29–0.77 | 0.22–0.52 | 0.24–0.49 |
| 3 nF MOS spread | 110 / 106 / 106 | 0.92 / 1.08 / 1.28 | 1.5–2.6 | 0.43–0.88 | 0.41–0.85 | 0.20–0.49 | 0.17–0.35 | 0.19–0.43 |
| 3 nF MOS spread, no strip caps | 94 / 87 / 84 | 1.05 / 1.33 / 1.65 | 1.8–2.6 | **0.75–1.57** | 0.34–0.75 | 0.20–0.47 | 0.17–0.34 | 0.19–0.43 |
| 3 nF MOS at the macro | 110 / 102 / 81 | 0.74 / 0.74 / 0.76 | 0.9–2.0 | 0.44–0.76 | 0.37–0.40 | 0.14–0.17 | 0.08–0.09 | 0.05 |
| 3 nF MIM spread | 110 / 106 / 106 | 1.09 / 1.26 / 1.44 | 1.8–2.8 | 0.44–0.90 | 0.41–0.85 | 0.19–0.48 | 0.17–0.29 | 0.12–0.33 |
| AP4-9 low (1.7 nF MIM + 0.45 nF fill) | 123 / 118 / 118 | 1.08 / 1.29 / 1.49 | 1.8–2.9 | 0.39–0.83 | 0.58–0.98 | 0.21–0.42 | 0.16–0.24 | 0.10–0.20 |
| AP4-9 high (5.7 nF MIM + 1.0 nF fill) | 84 / 78 / 75 | 0.76 / 0.78 / 0.85 | 1.2–2.6 | **0.70–0.84** | 0.21–0.40 | 0.14–0.22 | 0.08–0.15 | 0.08–0.12 |
| AP4-9 low + 1.5 nF MOS at the macro | 106 / 98 / 91 | 0.87 / 0.93 / 0.95 | 1.3–2.4 | 0.48–0.90 | 0.33–0.43 | 0.14–0.20 | 0.09–0.11 | 0.06–0.07 |

- The loop inductance is about 0.5 nH (0.4–0.65), so the anti-resonance sits at 156.25 MHz with 0.5–1.5 nF added (\|Z\| 0.95–1.9 Ω there), between the clock lines with 2–4 nF, and at 78.125 MHz with 6–8 nF (0.53–0.73 Ω). The pk-pk ripple still falls with more decap (F3) because the characteristic impedance falls, but the 78 MHz line does not improve between 3 and 8 nF.
- Q is 0.9–2.9 in every case, including MIM-only. PDN-03's condition "add damping if Q > 3" is not triggered. The damping comes from the MOS decap ESR (τ = 152 ps), the grid and the bonds; it disappears if the decap is MIM-only on a much stiffer grid than modelled.
- A2's target (\|Z\| ≤ 1 Ω, 20–200 MHz) is met only by 3 nF at the macro, AP4-9 high, or AP4-9 low + 1.5 nF at the macro. PKG-06 (≤ 2 Ω, 50–400 MHz) is met by every plan with strip caps except "none" at the pessimistic end (2.57 Ω). Without strip caps the limit is 3 Ω; "none" reaches 3.6 Ω.
- Wired ring band (600–810 MHz) and 2.4 GHz: no anti-resonance; \|Z\| 0.08–0.85 Ω. The grid inductance above 1 GHz is an assumption (section 7).

### F5. QVCO: fails on the shared pll-island rail in every case; a dedicated bond is not enough (critical)

Pushing −59.7 MHz/V at 2.417 GHz (`scratch/lo/r5_pn/qs.json`). Spur = 20·log10(K·V/2f). Ripple at the QVCO tap and the result, 3 nF spread (AP4-9 low is within 1 dB):

| Mode | Rail ripple rms (mV) | Worst spur (dBc) and line | PSRR needed for −80 dBc | Supply jitter (ps rms; headroom 0.46) |
| --- | --- | --- | --- | --- |
| rf_rx autonomous | 21 / 42 / 96 | −43.9 / −37.4 / −29.8, digital 78.125 MHz | 36 / 43 / 50 dB | 0.85 / 1.67 / 3.78 |
| rf_tx autonomous | 17 / 39 / 94 | −43.9 / −31.4 / −20.6, PA envelope at 1 MHz (nom, pess) | 36 / 49 / 59 dB | 0.85 / 2.99 / 9.66 |
| wired (LO off; shown for the rail) | 17 / 54 / 93 | −43.9 / −33.8 / −29.8 | — | — |

- Allowed raw ripple for −80 dBc: 3.4 µV at 1 MHz, 260 µV at 78.125 MHz, 520 µV at 156.25 MHz (peak).
- **Conflict:** LO20 item 5 states "≤ −80 dBc equivalent: ≤ 30 µV tone at 1 MHz". With −60 MHz/V a 30 µV tone at 1 MHz gives −61 dBc. If 30 µV is the intended limit, the needed PSRR is 19 dB lower (17–40 dB). The LO owner should state which one holds.
- PA envelope: the supply-current variation of the rfdriver with the modulation envelope is not in evidence. I assumed 5 / 15 / 30 % of 61.7 mA at 1–20 MHz. It couples through the shared bond and ring resistance (about 0.1 Ω), so decap does not help. PA turn-on also shifts the QVCO rail by 4.9 / 7.2 / 11.6 mV, a 0.3–0.7 MHz pull before any regulator.
- Dedicated supply bond for the pll/LO island (pad 64, no ring connection, ground still shared): spur −52.5 / −46.7 / −34.9 dBc in RX, jitter 0.34 / 0.79 / 2.59 ps. Gain 9 / 9 / 5 dB. The island's 250 pF against one 2.2 nH bond resonates near 170–215 MHz, so the pessimistic end barely improves.
- Requirement: an on-die regulator or active filter for the QVCO (22–25 mA) with ≥ 50 dB at 1 MHz and ≥ 45 dB at 78–156 MHz (or ≥ 30 dB if the 30 µV limit holds), plus a Kelvin ground. A passive RC cannot do it: 50 dB at 1 MHz with 4 Ω (100 mV at 25 mA) needs 13 µF.

### F6. RX spur through the shared ground (confirms A5, larger than A5)

- In RF modes D2H runs at div2, so its comb and the macro's both sit on 78.125 MHz multiples. The 31st harmonic is 2421.875 MHz.
- Die VSS at the LNA against board ground at that line: 0.34 / 3.0 / 14.7 mV rms, dominated by D2H return current in the ground bonds. With the 25 dB rejection A5 assumed: −81 / −62 / −49 dBm input-referred against the −100 dBm spec (2.24 µV rms). A5 reported −88…−69 dBm for the macro alone.
- A split D2H rail (own 2 supply + 3 ground bonds): −99 / −79 / −63 dBm.
- Needed rejection from die VSS to the LNA input: 44–76 dB. The LNA's ground-injection gain is not in evidence (RF-RX-PSRR unverified), so this cannot be closed here.
- The amplitude at the 31st harmonic uses a spectral envelope and an assumed grid inductance; treat it as ±10 dB.

### F7. Ring PLLs: regulated passes at nominal, bypass mode fails

Wired mode, 3 nF spread, using the extracted pll_vreg2 sensitivities (0.045 ps/mV at 78 MHz, falling as f⁻² above):

| Ring supply | DJ pk (ps) | Limit |
| --- | --- | --- |
| Regulated | 1.07 / 3.51 / 6.28 | < 5 ps |
| Regulated, pll island on its own bond | 0.57 / 2.23 / 4.50 | < 5 ps |
| Regulated, strip caps missing | 1.67 / 5.91 / 10.5 | < 5 ps |
| Bypass (BYP = 1) | 13 / 43 / 77 | 20 ps (0.05 UI at 2.5 Gb/s) |

- The pll_vreg README says the ss ring at 810 MHz needs ≥ 3.02 V and therefore bypass. On this rail bypass costs 43 ps at nominal, so ss/810 MHz has no usable supply configuration as it stands.
- pll_vreg2 PSRR is not in evidence above 200 MHz for the extracted cell at 312 MHz and 600–810 MHz, where wrx_cap and wiredtx (46.6 + 37.5 mA at 625 MHz) inject on the neighbouring wired island.

### F8. ADC: digital lines alias in band; no PSRR evidence to close it

- The 78.125 MHz line aliases to 1.875 MHz at 40 MS/s, and 156.25 MHz to 3.75 MHz. On the conv island rail (refbuf tap, 3 nF): 16 / 32–48 / 67–80 mV for the worst aliasing line.
- For a −60 dBFS spur (FS ±0.87 V) the reference buffer and comparator need 25 / 32–35 / 38–39 dB of supply rejection at 78–156 MHz (28–43 dB with AP4-9 low). refbuf PSRR and comparator supply sensitivity are not in evidence (converters README, MOD-13).
- A frequency-plan fix exists: an ADC clock at 39.0625 MHz (78.125/2) puts every digital harmonic at DC or Nyquist.

### F9. D2H simultaneous switching on the common ring

- Host rail ripple from D2H, 3 nF: 20 / 106 / 391 mV pk-pk (wired, 156.25 MHz). Ground bounce of the host row against board ground: 19 / 155 / 718 mV pk-pk; decap does not change it (it is ground-bond inductance). PKG-08 estimated 189–486 mV. The slow-slew and drive limits in PKG-08 and PDN-01 stand.
- Splitting the host rail without giving it decap is worse than the common ring: the split rail has only the pad-ring capacitance and rings by 0.28–12 V in the linear model.

### F10. Bonds (M4)

- DC share at the evidence currents: worst supply bond 63 / 70 / 79 mA (pad 18, wired) and 62 / 66 / 72 mA (pad 64, rf_tx); worst ground bond 57–61 mA (pad 9). At the budget allocation: 49 / 56 / 64 mA. `power_budget.py` assumes 60 mA per supply cell and even sharing (utilisation 0.52–0.63); the real share is 1.5–1.8× the mean on the worst bond.
- One open supply bond: neighbour at 81–84 mA, ring drop +0.3 to +13 mV. The die still powers up.
- Two added supply/ground pairs on the south and north edges (from spare sites): worst supply bond 70 → 63 mA, worst ground bond 59 → 50 mA, ring drop −4.5 mV, macro drop −2.5 mV. Useful but small; the interior grid is the limiter.
- The ground-bond lengths are not in `package-channel.json` (f_mm is null); I used the supply-bond range.
- Strip capacitors: without them the anti-resonance drops by 15–20 % in frequency and every victim number is 1.2–1.5× worse (QVCO spur 5–7 dB worse). BP-4 is mandatory, not optional.
- LNA source downbonds (RC-16j) were not put into the RF bench here; see section 7.

### F11. Mode steps, POR, core_bias

- Envelope steps (digital clock enable in one clock cycle, D2H start, both together): static shift 3–32 mV at the macro, extra undershoot 0.3–4.8 mV there and 3.9–22.7 mV at core_bias, across no decap, 3 nF spread and AP4-9 low (`out/e5_steps.txt`). The per-cycle packet ripple of F3 dominates, not the mode step.
- Island enable: soft-start peak 62 mA over 2.6–4.6 µs × about 0.1–0.25 Ω gives 6–16 mV (hand estimate, consistent with the island_support "0 mV ring undershoot" with soft start).
- POR: no false trip. It needs ≥ 1 ms below about 1.0–1.5 V; the worst instantaneous rail at its tap with ≥ 1 nF is about 2.4 V at the pessimistic bound (838 mV droop bound on a 3.23 V static rail).
- core_bias: the mode-dependent static drop (24–42 mV) moves the trunk currents by 0.007–0.11 % (0.28–2.7 %/V): negligible. Its rail carries 49 / 137 / 183 mV pk-pk at 78 MHz with 3 nF at the macro. Bandgap and biasgen PSRR at these frequencies is not in evidence, so the effect on the 23 bias consumers is unknown.

## 3. What to change (ranked)

1. v7 floorplan: a real supply grid (≥ 25 % top-metal coverage per net or equivalent sheet ≤ 0.25 Ω/sq), every island's loads abutting its switch, island straps sized from the table in F1.
2. Reconcile the currents in F2: resize isw_rf (≥ 100 mA or confirm the pad-feed split), isw_pll or a separate LO rail (≥ 80 mA of LO chain), isw_wired (≥ 110 mA with wrx_cap), and the mode ceilings and thermal point.
3. Decap: put it at the macro. Either ≥ 6 nF there, or cut the 78.125 MHz charge per cycle to ≤ 0.35 nC and keep 3 nF there. Avoid a total of 0.5–1.5 nF. Use MOS (or series-damped) decap for at least half; keep AP4-9 MIM as a supplement for the analog islands.
4. QVCO: dedicated regulated rail and Kelvin ground (F5); settle the −80 dBc versus 30 µV conflict; get the rfdriver supply current against envelope from the rf_tx benches.
5. LNA ground reference separate from die VSS; D2H slow slew in RF modes; consider the D2H rail split with its own decap; keep 2421.875 MHz out of the channel plan.
6. Add a supply/ground pair on the south and north edges if two spare sites can be released.
7. Evidence to produce: bandgap/biasgen PSRR to 200 MHz, refbuf and comparator PSRR, LNA ground-injection gain, pll_vreg2 PSRR at 312 and 600–810 MHz, macro power per clock domain and its current pulse shape, wired RX supply-induced jitter.

## 4. Model and assumptions (two-sided)

Method: frequency-domain nodal solver (`mna.py`), a 13 × 18 mesh per net over the core (252 × 248 µm tiles), the ring on the mesh boundary, 18 mutually coupled bonds, per-supply COB strip capacitor and connector path, carrier bulk, five island switches with island straps, block current sources at their v6 positions (unplaced blocks at their v6 seeds). Periodic aggressors are synthesised from their harmonics through the complex transfer impedance. "pess" in the bounce tables takes the pessimistic source and, per spectral line, the worst of the three network sets; "opt" takes the best; "nom" is nominal on nominal.

| Quantity | Low-impedance end | Nominal | High-impedance end | Source |
| --- | --- | --- | --- | --- |
| Bond inductance | 0.83 nH/mm | 0.92 | 1.00 | package-channel.json |
| Bond length (supply and ground) | 2.0 mm | 2.4 | 2.9 | signal-bond range; ground lengths not published |
| Adjacent-bond coupling k | 0.20 | 0.30 | 0.40 | partial-inductance estimate (0.37 at 0.3 mm / 2.5 mm) |
| Bond + pad resistance | 0.09 Ω | 0.12 | 0.15 | 25 µm Au, 2.0–2.9 mm |
| Metal5 / Metal1–4 sheet | 0.050 / 0.076 Ω/sq | 0.060 / 0.090 | 0.070 / 0.104 | tech LEF min / nom / max |
| Core grid coverage per net (Metal5) | 15 % | 8 % | 4 % | **assumed: v6 has no strap plan** |
| Macro grid coverage per net | 20 % | 12 % | 8 % | assumed |
| Grid loop inductance per tile | 0.10 nH | 0.20 | 0.40 | assumed |
| Provider ring rails through custom pads | 100 % | 33 % | 0 % | fill10 LEF widths; continuity unverified |
| Core VDD ring width at custom pads | 25 µm | 16 | 8 | v5 pdn-shapes.json (3–22 µm pieces) |
| Island switch Ron | 0.8× | 1.0× | 1.25× | island_support full-RC drop / design current |
| Island strap width (Metal5) | 60 µm | 30 | 20 | v5 used 10–30 µm bars |
| Macro intrinsic capacitance | 0.50 nF | 0.30 | 0.15 | estimate; A2 used 0.3–0.5 |
| Pad-ring intrinsic capacitance | 0.15 nF | 0.08 | 0.04 | estimate |
| Island decap (950 pF total) | 1.5× | 1.0× | 0.5× | island_support evidence |
| Strip capacitor mounted inductance | 1.2 nH | 1.8 | 2.6 | trace 2.0–2.9 mm + via + ESL |
| Finger → carrier inductance | 2.0 nH | 3.0 | 4.5 | trace + via + 0.85–1.2 nH contact |
| MOS decap time constant | 152 ps | | | decap sim-results (42 Ω × 3.63 pF at 100 MHz) |
| MIM time constant | 5 ps | | | assumed; no MIM ESR in evidence |
| Digital current, pulse base | 24.5 mA, 3 ns | 60 mA, 2.4 ns | 81.8 mA, 1.6 ns | clock-power-screen / PWR-DIG / hardening evidence; A2 pulse |
| D2H periodic content, edge | 0.16×, 1.4 ns | 0.5×, 1.0 ns | 1.0×, 0.76 ns | host screens, package-channel host_ssn |
| wrx_cap current, content at f_ring | 19.8 mA, 20 % | 46.6 mA, 50 % | 46.6 mA, 100 % | wrx_cap-evidence; content assumed |
| rfdriver envelope current | 5 % | 15 % | 30 % of 61.7 mA | **assumed** |

Supply topology used: all 8 supply bonds and all 10 ground bonds join on the die ring (power-partition.md). Supply bonds sit only on the west (4) and east (4) edges; ground bonds are west 4, east 4, south 1, north 1.

## 5. Bench proof

- `sanity.py`: DC divider exact; parallel RLC f0 159.4 MHz against 159.2 by hand, peak 1.708 Ω identical to the closed form and to ngspice (independent engine); coupled-bond pairs give L(1+k)/2 and 2L(1−k) exactly.
- `e0_sanity_model.py`: the full builder with an idealised grid and one 2 nF lump gives 159.4 MHz and 4.73 Ω against 159.7 MHz and 4.89 Ω by hand (L/8 + L/10); the DC rail matches to 10 µV.
- Negative control (no decap, one supply bond, pessimistic set): static rail 2.72 V, bond 297 mA, macro ripple 2.7 V pk-pk. **Fails**, as required.
- Passing reference (optimistic set, allocation currents, 4 nF at the macro): 3.156 V, 63 mV pk-pk, 50 mA per bond. Passes.
- Step synthesis checked on a hand RLC: static 6.0 mV exact; abrupt-step undershoot 16.8 mV against about 20 mV by the damped-LC formula.

## 6. Files

`scratch/integration/m1-pdn/`: `mna.py` (solver), `model.py` (geometry, parameters, netlist), `loads.py` (currents and spectra), `core.py` (taps, ports, decap plans), `sanity.py`, `e0_sanity_model.py`, `e1_static.py`, `e2_impedance.py`, `e3_bounce.py` (options `host_split=1`, `pll_split=1`, `strip=0`, `x_feed=0.8`), `e4_decap_req.py`, `e5_steps.py`, `e6_ring_bonds.py`, and `out/` (JSON and text results; the large `e1_static.json` and `e3_*.json` are on disk but not committed, and regenerate in minutes). Run each from that directory with `python3 <script>`.

## 7. Not verified

- The interior grid, island straps and block positions are assumptions on an unrouted floorplan that did not fit. F1 is a requirement, not an extraction.
- Whether the provider ring rails continue through the custom pad families (no KLayout or gdstk available outside the pinned image). This sets the pessimistic ring case and the safety of AP4-10(b).
- Grid inductance and everything above about 1 GHz (F6, the 2.4 GHz column in F4) is order-of-magnitude.
- The digital current pulse shape and its split between clock domains: no per-domain power or I(t) exists. This is the largest lever on F3.
- The rfdriver rail-versus-pad-feed split, and its envelope current.
- Victim sensitivities with no evidence: bandgap/biasgen PSRR, refbuf and comparator PSRR, LNA supply and ground gain, wired RX ps/mV, lo_mmd/lo_pfdcp/lo_ext ps/mV, pll_vreg2 above 200 MHz. For these the report gives the ripple and the rejection needed, not a pass/fail.
- M4's RF_RX part: the LNA source downbonds (Ls ± 0.2 nH and coupling to the RF_RX bonds) were not put into the LNA bench. RC-16n (2026-11-13) proposes withdrawing those downbonds, which would make this part moot. Also open: the conflict between 1.0 ± 0.2 nH (rf_rx README, RC-16j) and 0.5 nH with stability failing at 0.75 nH (`scratch/rf-lna-p/NOTES.md`).
- Ring-to-ring and ring-to-QVCO pulling through the rail (M3) and substrate (M2) are not in this model.
- E5 (mode steps) covers the average-current envelope only; the first packets after a clock start are bounded by the F3 pk-pk figures, not simulated as a start-up transient.
- The board ground plane is ideal; carrier placement P1–P4 was not swept.

## 8. Proposed risk-register rows (for the coordinator; not written to the register)

| ID | Risk | Status | Evidence |
| --- | --- | --- | --- |
| PDN-09 | No top-level supply grid in v6; static drop to island taps 117–277 mV nominal against 117 mV | open | this report F1 |
| PWR-10 | Island currents exceed switch design: rf 99 / 55 mA, pll 103 / 60 mA, wired 110 / 80 mA; wrx_cap and LO chain not in the budget | open | F2 |
| PDN-10 | Decap demand 6–8 nF at the macro at the 60 mA requirement; fillcap gives 0.45 nF, not 1–3 nF | open | F3 |
| LO-11 (update) | Needs ≥ 45–50 dB regulator PSRR; dedicated bond gains 9–13 dB only; PA-envelope pulling unquantified; 30 µV / −80 dBc conflict | demanded-mitigation | F5 |
| PKG-09 | Supply-bond current 63–79 mA on bond 18 / 64 against 60 mA per cell; no supply bond on the south and north edges | open | F10 |
| PDN-11 | Ring PLL bypass mode unusable on the shared rail (13–77 ps DJ); ss/810 MHz depends on it | open | F7 |
