# Design assumptions: ground-truth data

Risk bucket 1 is **wrong ground-truth data**. Bad design is bucket 2, tracked in `risk-register.md`. This page lists every external number the design relies on.

- **Pessimistic** is the value to design or sign off against. It is deliberately conservative: worse than the low end of the best-estimate range where the evidence is weak.
- **Verified only at** names the blocks whose evidence uses the value-used (nominal or optimistic) figure rather than the pessimistic one. Those blocks are open items.
- Details are in `scratch/reviews/model-uncertainty-audit.md` and `scratch/reviews/gf180-device-speed-evidence.md`. The package figures come from `package-channel.md`.

Confidence: **H** means foundry-characterized or measured; **M** means physics plus an analogous silicon result; **L** means estimate or assumption only.

## Devices (gf180mcuD)

| Item | Value used | Best estimate | Source | Conf. | Pessimistic | Verified only at value-used / nominal |
|---|---|---|---|---|---|---|
| nfet_03v3 DC (Idsat, Vth) per corner | PDK model | = model | PDK vs foundry targets (E1/E2) | H | ss corner | — |
| nfet_03v3 fT, ss/32 °C | 17.5 GHz (model) | 16 GHz (12–20) | model; Xu thesis 19 GHz silicon | M | **11 GHz** | LNA, mixers, PA, CTLE, slicer, wired TX, pll_ring: no fT derate anywhere |
| pfet_03v3 fT, ss | 6.0 GHz | 5.5 (4–7) | model, scaling | M | **3.5 GHz** | ring/CMOS clock paths |
| nfet_05v0/06v0 fT, ss | 8.5 / 6.6 GHz | 6.6–8.5 | model | M | **5.5 GHz** | PA cascode, standard-cell timing (Liberty is H) |
| fmax (fingered, Wf ≤ 2 µm) | not modelled (rgatemod=0, so effectively infinite) | 30 GHz (22–38) ss | Rg analysis, E6 | L–M | **20 GHz** | all RF blocks except the QVCO |
| Gate R + NQS input R | 0 Ω (none) | 60–150 Ω per 10 µm device | analysis; poly Rsh assumed 7–8 Ω/sq | L | **200 Ω per 10 µm** | LNA, mixers, PA, CTLE, slicer, wired TX, pll_vreg (Rg only in QVCO/LO-CML and char cells) |
| Gate fringe / extra Cgs, Cgd | cf=0, cgso 0.10 fF/µm | +10–20 % Cgg | model card, FO4 vs Liberty (1.3–1.45×) | M | **+25 % device C**, plus 1.45× derate on unextracted nodes | pll_ring 810 MHz (5–13 % margin), slicer 810 MHz |
| Wiring C | Magic C-only extraction | extraction ±10 % | tech file | M | **+15 % on extracted C**, plus wire R | most blocks: C-only extraction, no R |
| Thermal noise at RF | BSIM tnoimod=0, no induced gate noise | +0.5–1 dB NF vs model | E19 (independent LNA project suspects the PDK noise) | L | **+1.5 dB on simulated NF** | LNA, mixer/TIA, QVCO phase noise |
| Flicker noise | `fnoicor=0` (typical) | between typ and the noise corner | PDK `noise_corner` | M | **`fnoicor=1`** (noia ×11 nfet; pfet_06v0 ×330) | TIA/baseband, QVCO close-in, bandgap: no bench is known to use the noise corner |
| Mismatch A_Vt nfet_03v3 | not simulated | 7.15 mV·µm (PDK fets_mm) | PDK | M | **14 mV·µm (2×)** | slicer offset trim, ADC comparator, DAC sources, mixer offset: no MC run |
| Mismatch A_β | not simulated | 0.70 %·µm | PDK | M | **1.4 %·µm** | DAC linearity, bias mirrors |
| Corners bound the spread | ss/ff/sf/fs from DC targets | true for DC; unknown for C and noise | PDK | M | corners **plus** the C and noise derates above | all |
| PNP (bandgap) | PDK model | ±20 % Is/beta | PDK | M | ±30 %, so about ±8 mV VBG | bandgap (trim covers it) |
| Poly resistor spread | PDK corners ±20 % | ±20 % | PDK | H | ±25 % | bias (idac2 trim covers it) |

## Passives

| Item | Value used | Best estimate | Source | Conf. | Pessimistic | Verified only at value-used / nominal |
|---|---|---|---|---|---|---|
| Spiral inductor L (`pt_spiral`) | 2.65–2.91 nH | ±10 % | own model (Mohan + FastHenry); **the PDK has no inductor model** | M | **±15 %** | QVCO verified with L ±10 % only |
| Spiral Q at 2.45 GHz | 8.5–10.3 | 5–9 | own model; substrate resistivity unpublished (8–20 Ω·cm assumed) | L | **Q = 4** | QVCO start-up (low-Q case 4.6–5.2; high bands already fail) |
| MOS varactor C(V) | PDK tanh C(V) | ±10 % | PDK | M | ±15 % | QVCO tuning range |
| MOS varactor Q | infinite in the model; we add 2 Ω per side | Q 10–30 at 2.4 GHz | **no PDK data** | L | **Q = 8** | QVCO |
| MIM C density | 1.5/2.0 fF/µm² ± PDK corner | = PDK | PDK | H | PDK corner | — |
| MIM series R / bottom-plate parasitic | 0 (none in the model) | 1–3 Ω; bottom plate 5–10 % of C | typical | L | **5 Ω; 15 %** | QVCO band bank, refbuf 100 pF, LNA coupling |
| Pad + ESD C, wired RX | 2.35 pF (extracted metal + clamp) | 2.0–2.6 pF | extraction | M | **2.8 pF** | CTLE return loss (already fails at 2.35 pF) |
| Pad + ESD C, wired TX | 1.8 pF | 1.6–2.2 | extraction | M | **2.3 pF** | wired TX eye (core only, at 1.8 pF) |
| Pad C, RF_RX / RF_TX | 0.5 / 1.0 pF | ±20 % | extraction | M | **+30 %** | LNA match, PA match |
| Pad C, LO / REF | per pad cell | ±20 % | extraction | M | +30 % (moves the COB resonance; PKG-05) | external LO amplitude |
| ESD junction C voltage dependence | none modelled | ±20 % over swing | none | L | ±30 % | wired TX/RX linearity |

## Package, board, reference, environment

| Item | Value used | Best estimate | Source | Conf. | Pessimistic | Verified only at value-used / nominal |
|---|---|---|---|---|---|---|
| Bond wire L | 0.83 nH/mm × 2.2–3.2 mm | same ±20 % (loop height) | analytic, `package-channel.md` | M | **1.0 nH/mm, +0.5 mm length** | LO pad resonance (BW-02), wired RX/TX at 2.5 Gb/s |
| Bond-to-bond mutual L / C | 0.1 pF mutual C; mutual L missing | k 0.1–0.3 | analytic | L | **k = 0.3** | RF_TX → AUX_CLK coupling (BW-01) |
| COB trace (FR4 εr 4.5, tan δ 0.02) | analytic microstrip | ±10 % | KiCad stackup | M | εr 4.8, tan δ 0.025 | — |
| Via, land, finger parasitics | 0.27–0.49 nH, 0.06–0.1 pF | ±30 % | analytic | L | +50 % | wired 2.5 Gb/s eye |
| Connector (HC-PBB40C) | 0.85–1.22 nH, 0.25 pF | **no S-parameters published** | estimate | L | **2 nH, 0.5 pF** | everything above 1 GHz (MOD-11) |
| Carrier trace and board match parts | ideal / Q 30 match L, 1 dB balun | Q 20–40; balun 1–1.5 dB | datasheets (typical) | M | **Q 20, balun 2 dB, ±5 % parts** | PA output, LNA ideal-match NF (4.35 dB is with an **ideal** match) |
| Reference clock / crystal | ideal source in benches | board TCXO; spec B35 sets the LO PN mask | `board-requirements.md` | M | ±50 ppm, a spur at −60 dBc, jitter at spec limit | PLL/CDR benches use ideal clocks; slicer bench is open-loop with ideal clocks |
| External LO quality | ideal 0/3.3 V 50 % LO in mixer benches | B35 mask | board spec | M | B35 mask limit, 2 ° I/Q, 5 ps skew | RX mixers (ideal LO), PA (skew swept only) |
| Supply (performance) | 3.15–3.35 V | as specified | MANDATE | H | 3.15 V plus IR drop 50 mV plus ripple | blocks without PDN in their bench |
| Supply (safety) | 0–3.63 V | — | MANDATE | H | 3.63 V | — |
| Junction temperature (performance) | 22–32 °C | depends on board cooling | MANDATE; top-side cold finger 6–8 °C/W | M | **37 °C** (cooling set point error) | all performance checks stop at 32 °C |
| Junction temperature (safety) | 0–85 °C | — | MANDATE | H | 85 °C | — |
| RF TX macro-output -> DAC margin (digital timing, 2026-11-11) | 3.0 ns before the DAC's opposite (falling) rf_tx_clk edge at the macro clock pin (`RFTX_DAC_MARGIN` in `integration/pt_digital_macro.sdc`) | DAC capture flop setup ~0.4 ns at ss + macro-to-DAC route + clock arrival difference | estimate (no RF/assembly number yet) | L | **3.0 ns** = setup 0.6 + route 1.2 + clock arrival difference 1.2 | digital macro STA (rftx outputs); confirm with RF/assembly |
| Substrate resistivity | 8–20 Ω·cm assumed | unpublished | none | L | **5 Ω·cm** | inductor Q, substrate coupling (MOD-02) |

## Blocks verified only at nominal or optimistic values

| Block | Ground-truth values not yet stressed |
|---|---|
| LNA | Rg, RF noise, ideal board match, pad C |
| RX mixers / TIA | Rg, flicker corner, ideal LO |
| QVCO / LO | Q = 4, varactor Q, MIM R. It already misses 2.40 GHz at ss with L +10 %, before these are applied. |
| PA / rf_tx | fT/fmax low end, Rg, board match Q and balun loss |
| pll_ring / CDR | +25 % device C, fT 11 GHz (810 MHz at ss would fail), ideal reference |
| Slicer | 2× A_Vt, fT low end at 810 MHz, ideal clocks, kick-back C |
| CTLE | pad C 2.8 pF, connector without S-parameters |
| Wired TX | pad C 2.3 pF, connector 2 nH; block-level corner sweep not yet run |
| ADC / DAC | mismatch (no MC), flicker |
| pll_vreg | Rg-free amplifier, +25 % C (3 dB PSRR margin). Covered by bypass. |
| Bias / bandgap | flicker corner. Trim covers the DC errors. |
