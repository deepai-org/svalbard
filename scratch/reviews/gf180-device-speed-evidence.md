# GF180MCU (gf180mcuD) device speed: evidence, derivations, feasibility

Date: 2026-11-09. Scope: nfet_03v3 / pfet_03v3 (L = 0.28 um), plus a 5 V and 6 V check. Operating window 22–32 °C junction, 3.15–3.35 V.
This is a read-only review. No project files were changed. Sim decks are in the session scratchpad (`.../scratchpad/s/`).

## 0. Bottom line

| Quantity (W = 10 um, L = 0.28 um, VDS = 1.65 V) | ss / 32 °C | tt / 27 °C | Confidence |
|---|---|---|---|
| nfet_03v3 intrinsic fT, model (VGS = 1.2 V) | 17.1–17.5 GHz | 22.2–22.7 GHz | high that this is what the model says |
| **nfet_03v3 fT, best estimate (device, de-embedded)** | **16 GHz (range 12–20)** | **20 GHz (range 16–25)** | medium |
| nfet_03v3 effective fT in a laid-out small-device circuit (wiring + junction loading) | 11–13 GHz | 14–16 GHz | medium |
| **nfet_03v3 fmax, best estimate (fingered, Wf ≤ 2 um, gate contacted on both sides)** | **30 GHz (range 22–38)** | **37 GHz (range 28–45)** | low to medium |
| pfet_03v3 fT, model (VGS = −1.2 V) | 6.0 GHz | 8.4–8.6 GHz | high that this is what the model says |
| **pfet_03v3 fT, best estimate** | **5.5 GHz (range 4–7)**; about 11 GHz at \|VGS\| = 2.2 V | **8 GHz (range 6–10)** | medium |
| pfet_03v3 fmax, best estimate | 12–18 GHz | 16–24 GHz | low |
| nfet_05v0 (L = 0.6) / nfet_06v0 (L = 0.7) fT, model, VGS = 1.5 V, VDS = 3 V | 8.5 / 6.6 GHz | 12.0 / 9.2 GHz | medium |
| pfet_06v0 (L = 0.5) fT, model | 2.9 GHz | 4.6 GHz | medium |

Verdicts (section 5):

- **Quarter-rate sampler at 625 MHz:** feasible with comfortable margin.
- **Sampler at 810 MHz:** feasible with roughly 8 τ of regeneration time at ss. Use the layout rules in section 6.
- **Half-rate 2.5 Gb/s (1.25 GHz clock) StrongARM:** marginal, about 5 τ. Not recommended.
- **2.5 Gb/s CML:** internal stages have more than 2× bandwidth margin. The output stage is limited by pad and ESD capacitance, not by fT. The final serializer stage must be CML or mux-based, not static CMOS.
- **2.4 GHz radio:**
  - Single-stage cascode LNA: 10–14 dB gain is realistic. A gain of 20 dB or more needs two stages.
  - PA: realistic at about 0–8 dBm with low efficiency. Do not plan above about 10 dBm.

## 1. Evidence table

| # | Source | Number | Conditions | Confidence / relevance |
|---|---|---|---|---|
| E1 | GF180MCU PDK docs, "Model vs EP nominal target" (LV 2.5) — https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_2_5.html | nfet_03v3 Idsat 430 / 510 / 590 uA/um (ss/tt/ff), Vth0 0.73/0.63/0.53 V. pfet_03v3 Idsat −210/−250/−290 uA/um, Vth0 −0.85/−0.73/−0.61 V. Measured typical: 508 and −254.1 uA/um | W/L = 10/0.28, VGS = VDS = 3.3 V, Vth by max-gm at VD = 0.05 V | High. Foundry silicon target. |
| E2 | This review, ngspice with frozen sm141064.ngspice | Model Idsat 430.3 (ss) and 510.0 (tt) uA/um nfet, 210.6 / 250.3 pfet | same as E1, 25 °C | High. **The model is DC-calibrated exactly to E1.** Capacitances are not independently verified. |
| E3 | Model card (frozen PDK) `nfet_03v3.0` | toxe = 8.0 nm (pfet 7.9 nm), cgso = cgdo = 0.10 fF/um (pfet 0.124), cf = 0, rgatemod = 0, rdsw = 530 Ω·um, capmod = 2 | — | High (model content). rgatemod = 0 means no gate resistance or NQS input resistance. |
| E4 | This review, 2-port Y-parameter AC sim (ss/32 °C, VGS = 1.2 V, VDS = 1.65 V, W = 10 um) | gm 1.34–1.38 mS, Cgg 13.6–13.7 fF, Cgd 3.0 fF (0.30 fF/um), fT(h21) 17.1–17.5 GHz. tt/27: gm 1.70 mS, Cgg 13.0 fF, fT 22.2–22.7 GHz. pfet ss: gm 0.45 mS, Cgg 12.7 fF, fT 6.0 GHz; tt 8.4–8.6 GHz | nf = 1 and nf = 10, with AD/AS/PD/PS | High (model). Reproduces the 17.5 GHz basis in the brief. |
| E5 | This review, fmax from Mason's U with an external series Rg | nfet ss: fmax = 101 GHz at Rg = 40 Ω, 37.5 GHz at Rg = 150 Ω. tt: 112 / 43.7 GHz. Rg ≤ 5 Ω gives > 300 GHz (unphysical, because the model is lossless at the gate) | nf = 10 | Medium. Agrees with the analytic fmax = fT / (2·√(Rg(gds + 2π·fT·Cgd))) to within 5%. |
| E6 | H. Xu, Univ. of Florida PhD thesis, "Thick-gate-oxide MOS structures with sub-design-rule channel lengths" — https://ufdcimages.uflib.ufl.edu/uf/e0/01/75/13/00001/xu_h.pdf (sec. 4.2.2, Fig. 4-4) | **Measured** conventional 3.3 V thick-oxide nMOS: **fT peak 19 GHz, fmax peak 37.5 GHz** | VGS = 2.0 V, VDS = 3.0 V, pad-open de-embedded, HP8510C to 26 GHz. Foundry 0.13 um process, 3.3 V I/O device (Tox about 6.8 nm per the thesis model card). In that thesis's 0.18 um process the 3.3 V L_min is 0.35 um | **High-quality silicon anchor** for a 3.3 V, 7 nm-class thick-oxide device at L ≈ 0.35 um. GF180 uses 0.28 um, which is a little shorter, with Tox 8 nm, which is a little thicker. The two effects roughly cancel. |
| E7 | Same thesis, sec. 2.2 | 0.18 um foundry digital CMOS: 3.3 V thick-oxide nMOS L_min = 0.35 um | — | Context. GF180MCU's 0.28 um 3.3 V device is short for its class. |
| E8 | Search summary pointing to a 0.18 um analog/RF-CMOS paper, ResearchGate 224056379 — https://www.researchgate.net/publication/224056379 | RF-LDMOS that shares the 7 nm 3.3 V I/O gate oxide, L = 0.35 um: fT 43 GHz, fmax 76 GHz. Title: "32 GHz FT RF-LDMOS" | from the abstract snippet (page returned 403) | Low to medium. This is an upper bound for an RF-optimized device on 7 nm oxide, not a plain I/O FET. |
| E9 | Search summary: "thick oxide 0.30 um 3.3 V RF CMOS, 6.8 nm gate oxide" (GF RF CMOS context, search result list) | Tox 6.8 nm for 3.3 V RF CMOS | — | Low (snippet). Consistent with E6 and E3. |
| E10 | Search summary of a 0.18 um RF-CMOS reference (1.8 V thin oxide), e.g. "0.18 um foundry RF CMOS with 70 GHz fT" — https://vufind-test.katalog.k.utb.cz/... (search result) | 1.8 V core fT 45–70 GHz | thin oxide | Context only. Not applicable to 3.3 V. |
| E11 | OSTI, "RF characteristics of 0.18-um CMOS transistors" — https://www.osti.gov/etdeweb/biblio/20296290 | qualitative: peak fT/fmax at peak gm, fT better with fewer fingers, fmax dominated by gate resistance | — | Supports the layout rules. |
| E12 | GF180 Liberty (frozen PDK) `gf180mcu_fd_sc_mcu7t5v0` inv_1, self-consistent FO4 | tt_025C_3v30: rise 410 ps, fall 280 ps, **avg 345 ps**. ss_n40C_3v00: 474 ps avg. ss_125C_3v00: 660 ps avg. ff_n40C_3v60: 209 ps | Cin = 4.62 fF. **The cells use nfet_05v0 (L = 0.6) and pfet_05v0 (L = 0.5), not 3.3 V devices** (cell spice netlist) | High (foundry-characterized). Not directly a 3.3 V-device anchor. |
| E13 | This review, schematic FO4 chain of the same inv_1 (5 V devices) | tt/25/3.3 V: 235 ps avg. Matching the Liberty 345 ps needs about 7 fF extra per node (4 fF gives 299 ps, 7 fF gives 346 ps) | no layout parasitics | Medium. Layout parasitics cost about 1.45× on minimum-size logic. The model and the Liberty data are consistent. There is no sign of a model-vs-silicon gap, but the Liberty data was probably built from the same models plus extraction, so this check is partly circular. |
| E14 | This review, schematic FO4 with 3.3 V devices (Wn = 1 um, Wp = 2 um, real diffusion) | tt/27/3.3 V: 114 ps (125 ps with 2 fF/node). ss/32/3.15 V: 146 ps (160 ps with 2 fF/node) | — | Medium. Applying the E13 factor (1.3–1.45×) gives a **realistic 3.3 V FO4 of 190–210 ps at ss/32 °C** and 150–165 ps at tt. |
| E15 | Tiny Tapeout GF26a ring-osc PVT sensor — https://www.tinytapeout.com/chips/ttgf26a/tt_um_santhosh_ring_osc_gf | 7/11/15/21/31-stage inv_1 rings; no silicon numbers published | 5 V cells | No data yet. A future anchor if it is measured. |
| E16 | Search-summary result for a GF180 TRNG ring oscillator (search 1) | "Osc3 212.91 MHz, Osc5 124.27 MHz, Osc7 91.25 MHz, Osc9 71.78 MHz" | source page not identified, deliberately degraded oscillators | Low (unattributed). If 5 V cells are used, Osc3 at 213 MHz means 2.35 ns per 2·3 stages, about 780 ps per stage. That points to heavy loading or degradation, so it says nothing about the fT ceiling. |
| E17 | Efabless/Caravel discussion (search summary) — https://web.open-source-silicon.dev/t/562928/ | Caravel user clock tuned to a maximum of 214 MHz (not full speed, blamed on unsimulated parasitics). GPIO about 60 MHz | Caravel harness (SKY130 context in that thread) | Low. Mainly a reminder that unextracted parasitics have cost real projects. |
| E18 | ResearchGate, "Design and Test of OQPSK Modulator with GF180MCU" — https://www.researchgate.net/publication/380190298 | f_clk,max 97.9 MHz (from the search snippet) | digital, 5 V cells | Low. Digital only, and limited by the system. |
| E19 | rcyaon/cmos-lna (GF180, simulation only) — https://github.com/rcyaon/cmos-lna | Inductorless LNA, 9–21 dB across corners, 13 dB typical at 1.7 GHz. Authors suspect PDK FET/BJT noise-parameter problems | sim | Low. No silicon, but it flags the noise model as suspect. |
| E20 | 2AMLogic/gf180-pll — https://github.com/2AMLogic/gf180-pll | "Every number in this repository is simulation only" | — | No silicon. |
| E21 | SSCS Chipathon 2026 issue #143, GF180 2.4 GHz LC-VCO + CML divide-by-2 characterization chip — https://github.com/sscs-ose/sscs-chipathon-2026/issues/143 | pre-silicon | — | No silicon yet. Shows others are targeting 2.4 GHz CML in GF180. |
| E22 | SKY130 device-details page — https://skywater-pdk.readthedocs.io/en/main/rules/device-details.html | gives gate-delay data only, no fT/fmax tables. The fetched summary was garbled, so no numbers are used | — | No usable SKY130 measured-fT number was found. SKY130's RF FET cells (rf_nfet_01v8_*) exist with fixed layouts, but I found no published fT value to cite. |

**What I did not find:** any measured fT/fmax, ring-oscillator frequency, SerDes, or LNA/PA silicon result on GF180MCU itself. I also found no GitHub issue on the gf180mcu-pdk repository about RF/fT accuracy (search returned only the issue index: https://www.github.com/google/gf180mcu-pdk/issues). The PDK electrical-spec pages (sheet resistance, Cox, https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs.html) render only as tables of contents through the fetcher, so the poly sheet resistance below is an assumed typical 0.18 um value and is not cited.

## 2. Derivations

### 2.1 fT from first principles

- Cox = ε_ox / t_ox = 3.45e-11 / 8e-9 = **4.31 fF/um²**.
- With L_eff ≈ 0.25 um, the intrinsic saturation Cgs ≈ (2/3)·Cox·W·L_eff = **7.2 fF** for W = 10 um.
- Overlap plus fringe is about 0.3 fF/um per side, so 3 fF per side. The sim gives Cgd = 3.0 fF.
- Expected total Cgg ≈ 13 fF. The model gives 13.7 fF. The capacitances are physically sensible, and the model is not optimistic on C.

Velocity-saturation ceiling:
- With v_sat ≈ 8e4 m/s, fT,int ≤ v_sat / (2π·L_eff) ≈ 51 GHz.
- Scaled by the intrinsic fraction Cgs,int / Cgg ≈ 0.53, the device ceiling is about **27 GHz**.
- Equivalently, the gm ceiling is W·Cox·v_sat = 3.4 mS. The model's 1.4–1.7 mS is 40–50% of that, which is typical once mobility degradation and Rs (rdsw = 530 Ω·um) are included.

Square-law check at ss:
- Vov = 0.48 V, μ_eff ≈ 300 cm²/Vs.
- 1.5·μ·Vov / (2π·L²) ≈ 55 GHz intrinsic.
- With the 0.53 capacitance fraction and partial velocity saturation, this gives about 18–22 GHz.

The theory brackets the simulated 17.5 GHz. Silicon (E6) gives 19 GHz peak for a comparable thick-oxide device at a higher VGS of 2.0 V. **A fT of 16 GHz at ss/32 °C for VGS ≈ 1.2–1.5 V is a defensible central value.** The downside risk is extra Cgd and Cgs fringe from contacts and M1, which the model's cf = 0 may leave out. That risk is about −10 to −20%, which sets the lower bound near 12–14 GHz.

pfet: the hole mobility ratio is about 1/3, and Idsat 210 vs 430 uA/um is about 0.49. The sim gives fT 6.0 GHz at |VGS| = 1.2 V (ss), rising to 11.7 GHz at 2.2 V. This is internally consistent.

### 2.2 Parasitics the model omits, and fmax

1. **Poly gate resistance.**
   - Assume silicided poly Rsh ≈ 7–8 Ω/sq (a typical 0.18 um value; not verified from GF docs).
   - Per finger: R = Rsh·Wf / (n·L) with n = 3 for one-side contact and n = 12 for two-side contact.
   - Wf = 2 um, one side: 7·2/(3·0.28) = 17 Ω per finger. Five fingers in parallel give 3.3 Ω, plus about 2–5 Ω of contacts and vias.
   - A single 10 um finger with one-side contact gives 83 Ω. That alone is enough to drop fmax below 50 GHz.
2. **Non-quasi-static channel (input) resistance.** R_i ≈ 1/(k·gm) with k ≈ 5–12. At gm = 1.34 mS this is **60–150 Ω for the whole 10 um device, whatever the fingering.** rgatemod = 0 leaves it out. For a well-fingered device it is the dominant fmax limit.
3. **Source resistance from contacts and wiring** beyond rdsw: a few Ω. It degrades gm by 5–10% in wide devices.
4. **Drain and source junctions:** Cdd = 10–12.5 fF for W = 10 um with real AD/AS. This is comparable to Cgg. It does not change fT, but it halves the bandwidth of every stage that drives its own drain plus a fanout.
5. **Wiring:** about 0.1–0.2 fF/um of M1–M3. The FO4 calibration (E13) shows about 7 fF per node for minimum logic.

fmax = fT / (2·√(Rg_tot·(gds + 2π·fT·Cgd))) at ss gives:

| Rg_tot | fmax (ss) |
|---|---|
| 40 Ω | 101 GHz (sim) |
| 80 Ω | about 55 GHz |
| 150 Ω | 37.5 GHz (sim; 36 GHz analytic) |

A realistic Rg_tot of 60–150 Ω, plus substrate and drain loss that the model does not represent, gives **fmax ≈ 22–38 GHz at ss and 28–45 GHz at tt**. The measured 37.5 GHz in E6 sits in this range.

### 2.3 Liberty and FO4 cross-check

- Liberty FO4 for the 5 V inv_1 is 345 ps at tt. Times nfet_05v0 fT (12 GHz, tt) that gives FO4·fT ≈ 4.1.
- 3.3 V schematic: 146 ps × 17.5 GHz ≈ 2.6. With the 1.45× parasitic factor: 210 ps × 17.5 ≈ 3.7.
- Rule of thumb: FO4·fT ≈ 3–4.5 (180 nm 1.8 V: about 75 ps × 50 GHz ≈ 3.7).

The data is self-consistent. The foundry-characterized cell delays do not indicate that the model overstates speed beyond the normal layout penalty. They do show that **the layout penalty is about 1.3–1.5× for small devices**. Use it as the derating for any circuit whose nodes are dominated by small devices and wiring: samplers, latches, dividers, and clock buffers.

## 3. Circuit-level sims (frozen PDK, schematic plus explicit loads)

| Circuit | ss / 32 °C / 3.15 V | tt / 27 °C / 3.3 V | Derated estimate (×1.3–1.5) |
|---|---|---|---|
| Cross-coupled latch, Wn = 4 um (nf = 2), Wp = 8 um (nf = 4), plus 10 fF per node (next stage and wiring), regeneration τ | **37 ps** | 30 ps | **48–55 ps at ss** |
| CML half-circuit, nfet W = 10 um (nf = 5), 0.46 mA, RL = 600 Ω, loaded by an identical next stage plus 10 fF | gain 0.80, **BW 7.4 GHz** | gain 0.99, BW 7.6 GHz | 4.5–5.5 GHz |
| FO4 inverter (3.3 V devices) | 146 ps | 114 ps | 190–210 / 150–165 ps |

The CML stage here has gain below 1 because gm·RL = 0.8. A real buffer uses about 1.5–2× the device width or RL = 800 Ω for gain ≥ 1.2, which brings the bandwidth down to about 4–5 GHz schematic and 3–4 GHz derated. That is still at least 1.7× the roughly 1.75 GHz (0.7 × bit rate) that 2.5 Gb/s NRZ needs.

## 4. Best estimates (repeated with rationale)

- **nfet_03v3 fT:**
  - ss/32 °C: 16 GHz (range 12–20) at VGS 1.2–1.5 V. The peak is about 20 GHz at VGS of about 2 V.
  - tt/27 °C: 20 GHz (range 16–25).
  - Anchored by the model's capacitances, the E1/E2 DC match, the E6 silicon anchor (19 GHz), and the theory.
- **nfet_03v3 fmax:**
  - ss: 30 GHz (range 22–38).
  - tt: 37 GHz (range 28–45).
  - Assumes multi-finger, Wf ≤ 2 um, gate strapped on both sides.
  - If the layout ignores this, a single wide finger can fall below 20 GHz.
- **pfet_03v3:**
  - fT ss 5.5 GHz (range 4–7) at |VGS| = 1.2 V; tt 8 GHz (range 6–10).
  - fmax about 12–18 GHz (ss) and 16–24 GHz (tt).
- **Effective in-circuit fT** for small, wiring-dominated devices: about 0.7× the device fT, so 11–13 GHz ss and 14–16 GHz tt.
- **5 V / 6 V devices:** fT 6–9 GHz (ss) and 9–12 GHz (tt). They are useful only as PA cascode or high-swing output devices, not in fast logic.

## 5. Implications

### 5.1 Sampler (StrongARM or latch) at 625–810 MHz

- Regeneration window: about half the clock period minus the integrate/reset phase (about 120–180 ps).
  - 810 MHz: 617 − 150 ≈ 470 ps ≈ **8.5–9.8 τ** at τ = 48–55 ps (ss, derated). Regeneration gain is e^8.5 ≈ 5000, so an input of 0.3 mV reaches full swing. **Feasible.** The margin is real but not large. Treat the ss sampler as a sign-off item that must be checked post-extraction.
  - 625 MHz: about 650 ps, or 12–13 τ. **Comfortable.**
  - 1.25 GHz half-rate for 2.5 Gb/s: 400 − 150 = 250 ps ≈ 5 τ, a gain of about 150. **Marginal.** Metastability and BER suffer, and any layout overrun breaks it. Avoid.
- Per-sampler clock buffers: the 810 MHz clock is about 6 FO4 per half period at ss (derated). Clock distribution in CMOS is fine. Edge rates of about 2 FO4 (about 400 ps, 20–80%) are acceptable.

### 5.2 2.5 Gb/s CML drivers

- UI = 400 ps ≈ 2 FO4 at ss. **Static-CMOS full-rate serialization is not feasible.** The last 2:1 mux and retiming must be CML, or a CML/CMOS mux clocked at 1.25 GHz with the select in CML. The quarter-rate (625 MHz) and half-rate CMOS stages before it are fine.
- Internal CML stages have 3–5 GHz derated bandwidth. That is feasible at about 0.4–1 mA per stage for small fanout.
- Output driver:
  - The 50 Ω double-terminated load (25 Ω) times the pad, ESD and driver drain capacitance (1.5–3 pF on GF180 I/O-class ESD) gives a pole at **2.1–4.2 GHz**.
  - The pad sets the limit, not the device. Keep ESD at or below about 1 pF on the high-speed pins, or accept about 1 dB of extra ISI and add 2-tap FFE.
  - At 8 mA tail (400 mVppd single-ended into 50 Ω), the driver pair needs W ≈ 150–200 um. Cgg is then about 250–300 fF, so the pre-driver must be a tapered CML chain of 2–3 stages, ratio about 3.

### 5.3 2.4 GHz LNA / PA

- fT/f ≈ 5–7 at ss (effective fT 12–16 GHz).
- Inductively degenerated cascode LNA: the voltage gain ≈ (fT/f)·(Q_L-limited R_load)/(2·Rs) works out to a realistic **10–14 dB power gain single-stage with on-chip inductors (Q ≈ 5–8)**. NF is about 2.5–4 dB (the noise model is suspect, E19). For 20 dB or more, use two stages or an LNA plus a gain stage after the mixer.
- An inductorless LNA at 2.4 GHz is limited to about 8–12 dB at ss (cf. E19, which reports 13 dB typical at 1.7 GHz).
- PA:
  - fmax/f ≈ 10–15 gives MAG in the high teens of dB, so gain is not the limit.
  - Output power is limited by breakdown and swing. With 3.3 V devices and a cascode on 3.3 V, expect about +5 to +8 dBm at roughly 15–25% drain efficiency with an on-chip match.
  - With a 6 V device cascode (fT 6–9 GHz at ss), a 2.4 GHz cascode top device still works (fT/f ≈ 3). That allows about +10 dBm.

## 6. Design choices that keep the design safe

1. **Architecture.**
   - Use quarter-rate (625 MHz) samplers for 2.5 Gb/s RX. Use 810 MHz only where unavoidable.
   - Do not use 1.25 GHz half-rate StrongARMs.
   - For TX, do the final 2:1 in CML and keep everything before it at quarter or half rate in CMOS.
2. **Bias for speed.** Bias nfets at VGS ≈ 1.2–1.6 V. That is about 100–200 uA/um at ss, near the gm/W knee. fT is within about 85% of peak there, and gm/Id is not wasted. Keep pfets out of signal paths that need more than about 2 GHz, or bias them at |VGS| ≥ 1.8 V.
3. **Layout for fmax/fT.**
   - Finger width ≤ 2 um (≤ 1–1.5 um for RF devices).
   - Gate contacts on both ends.
   - Shared source/drain diffusion, with an even finger count so the drain is in the middle.
   - Keep M1 overlap of the gate small.
   - Extract with RC and re-simulate with an explicit Rg model, adding Rg = Rsh·Wf/(12·L·nf) + 1/(5·gm) as an external resistor. The PDK model has rgatemod = 0, so it will not do this for you.
4. **Derating at sign-off.** Run pre-layout timing for samplers, latches, dividers and CML at ss/32 °C with τ and delays multiplied by 1.45, or run post-extraction only. Require ≥ 8 τ of regeneration at 810 MHz after extraction.
5. **Inductive peaking.** Use shunt peaking (m = 0.3–0.4) on the CML pre-driver and on the RX CTLE/VGA output. It gives a 1.4–1.7× bandwidth extension for small area, and the inductors already exist in the radio flow. For the TX output, minimize ESD and pad capacitance first. A T-coil is a stretch goal.
6. **Current densities.**
   - CML tail: about 50–80 uA/um of nfet width, which puts the device near peak fT at VGS − Vt ≈ 0.4–0.6 V.
   - Latch: sized so external load is no more than about the latch's own Cdd + Cgg.
   - LNA input: about 100–150 uA/um for best fT·gm/Id trade-off.
7. **Validation hooks on silicon (debuggability).**
   - Add a ring oscillator built from 3.3 V devices with an identical layout to the sampler latch.
   - Add a 5 V inv_1 ring to compare against the Liberty data.
   - Add a CML divide-by-2 self-oscillation test. Its self-resonance frequency directly measures effective fT.
   - Add an RF de-embeddable nfet pad structure (GSG plus open/short) if area allows.
   - These turn the uncertainty in this report into measurements on the first silicon.

## 7. Caveats

- No GF180MCU-specific RF silicon data was found. The fT/fmax silicon anchor (E6) is a comparable 3.3 V thick-oxide device from another foundry and a 0.13 um process.
- The model's DC behavior matches foundry targets (E1/E2). Its capacitances look physical but are unverified. Gate resistance and NQS effects are absent (rgatemod = 0).
- The poly sheet resistance (7–8 Ω/sq) is an assumed typical value. The GF180 electrical-spec pages could not be read.
- Sims were run with the machine at a load average of about 105, using minimal decks. The τ and bandwidth values are schematic-level, with explicit lumped loads.
