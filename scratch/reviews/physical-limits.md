# Physical-limit checks: spec owner (host link, wired CDR/pads, power, thermal)

MANDATE.md allows a miss only when GF180MCU makes it physically impossible. For every
item in my scope that someone might call impossible, this file gives the quantitative
check. **Result: none of them is shown to be a physical limit. L1 and L2 are model-based estimates pending extracted simulation (see caveats), not proof of feasibility.** Each has a design route, recorded in
`projects/programmable_transceiver_platform/spec/interface-architecture-changes.md`.
All checks use the narrow envelope only: Tj 22–32 °C, rail 3.15–3.35 V, process corners.

## L1. Device speed (nfet_03v3 / pfet_03v3 fT): model-based estimate, not proof

Netlists are in `scratch/reviews/physical-limits/ft_typical.sp` and `ft_ss32.sp`:
- open_pdks gf180mcuD frozen copy, `sm141064.ngspice`
- W = 10 µm, L = 0.28 µm, |VDS| = 1.65 V
- AC current gain = 1 crossing (intrinsic; no wiring or junction load)

| |VGS| (V) | n tt 27 °C | n ss 32 °C | p tt 27 °C | p ss 32 °C |
|---:|---:|---:|---:|---:|
| 1.0 | 19.5 GHz | 13.8 GHz | 5.9 GHz | 3.3 GHz |
| 1.2 | 22.7 GHz | 17.5 GHz | 8.4 GHz | 6.0 GHz |
| 1.5 | 24.8 GHz | 20.0 GHz | 11.0 GHz | 8.7 GHz |

What the rates need:
- 2.5 Gb/s NRZ needs about 0.7 × 2.5 = 1.75 GHz of front-end bandwidth.
- A loaded CML stage reaches about fT/4 to fT/6 (fanout plus wiring): 2.9–4.4 GHz at ss/32 °C, which is ≥ 1.7× the requirement.
- A quarter-rate sampler only has to decide at 625 MHz (L2).

**No limit is shown at the model level; this is not proof.** The extracted failures (TX 4:1 mux, `pt_wrx_cap`, slicer at ss) come from topology and layout: generic-layout routing is about 3× slow (performance-review §1d).

**Caveats for L1 and L2.** These are estimates, and feasibility is **pending extracted simulation** of the real sampler, CML driver and 4:1 mux at ss in the narrow envelope (22–32 °C, 3.15–3.35 V).
- The gf180mcuD BSIM models are not RF-validated.
- The models use rgatemod=0, so there is no gate resistance and fmax is not modeled.
- The figures are intrinsic, with no layout parasitics.
- VGS = 1.2 V is a high overdrive. At realistic CML and sampler current densities, ss fT is about 7–14 GHz.
- The fT/4–6 loaded-stage factor and the k = 4 regeneration factor are rules of thumb.

## L2. Sampler regeneration at quarter or half rate: model-based estimate, not proof

StrongARM regeneration time constant: τ ≈ C_node/g_m ≈ k/(2π fT), with k ≈ 4 for self- plus latch loading.
- At ss/32 °C, VGS = 1.2 V: τ ≈ 4/(2π × 17.5 GHz) = 36 ps.
- Resolving 1 mV to 1.6 V takes ln(1600) × τ = 7.4 × 36 = 270 ps.
- Available time is half a ring period: 800 ps at 625 MHz, 617 ps at 810 MHz. The ratio is ≥ 2.3.

**Estimate only.** At fT = 7 GHz, τ ≈ 91 ps and resolution takes ≈ 675 ps, which exceeds 617 ps at 810 MHz. Half-rate 810 MHz feasibility is therefore open until extracted simulation.

## L3. Return loss with pad capacitance (Bode–Fano)

Model: 50 Ω termination in parallel with C. The Bode–Fano bound is ∫₀^∞ ln(1/|Γ|) dω ≤ π/(RC).
- C = 2.35 pF (RX pad today): π/RC = 2.674 × 10¹⁰ rad/s. Spread uniformly over 0–1.25 GHz (7.854 × 10⁹ rad/s), that allows ln(1/|Γ|) ≤ 3.40, i.e. **RL ≤ 29.6 dB**.
- C = 2.71 pF (TX pad): RL ≤ 25.7 dB.

The ≥ 10 dB requirement (WR-PCIE-RL) is therefore reachable with matching:
- T-coil: L = R²C = 5.9 nH per leg; or
- a protection variant with C ≤ 1.6 pF and no matching (|Γ| = 0.30, 10.5 dB).

**Not a limit.** The 6.6–7.6 dB in the review is the unmatched 50 Ω ∥ C value.

## L4. Host link pad rate

Liberty, bi_24t fast-slew DDR at 6 pF:
- output f_max 222.8 MHz tt and 177.9 MHz at ss_125C/2.97 V, which is slower than any in-envelope point;
- input f_max 193.2 MHz tt.

Required: 156.25 MHz (312.5 Mb/s/pin). **Not a limit** for outputs, with ≥ 13.9 % margin even at an out-of-envelope corner. The in-envelope input number still has to be characterized.

Capacity: 10 pins × 312.5 Mb/s × 59/64 = 2.881 Gb/s, which is ≥ 1.152 × 2.5 Gb/s. **PCIe fits without new pads.** The earlier "does not fit" applied only to 2× FPGA oversampling.

## L5. Digital core frequency

After the AC-1 gearbox, the core needs 78.125 MHz (12.8 ns) and the wired boundary needs 62.5 MHz (16 ns).

Evidence: the routed macro reaches 65.3 MHz on the host word path at tt with no pipelining (FREEZE1, stale). A GF180 7-track flop-to-flop path with about 8 logic levels takes about 4–5 ns at tt, so 12.8 ns allows ≥ 2.5× derating for ss and routing.

**Not a limit.** The shortfall is mux depth and placement over the 1.8 mm macro.

## L6. Supply-cell current

Per `spec/budgets/power-budget.json`, the worst primary case with the digital requirement is wired with an external clock at 278.4 mA. The pad cells provide 8 supply cells × 60 mA = 480 mA, so even-share utilization is 0.58. This leaves room for a 1.7× share imbalance.

Only the evidence-bound case (447.5 mA vectorless digital, 0.93 utilization) approaches the limit. That case is closed by PWR-DIG, not by physics.

**Not a limit.**

## L7. Thermal

P_max = 0.98 W (with PWR-DIG) at 3.35 V, including TMDS and divider dissipation.

Holding Tj within 22–32 °C with ±2 °C control needs θ(junction→controlled plate) ≤ 8.25 °C/W. A 3.93 × 5.12 mm die on a thermal-via COB pad has:
- silicon spreading below 1 °C/W;
- a die-attach epoxy layer of 25 µm at about 1.5 W/mK over 20 mm², about 0.8 °C/W;
- FR4 with a via array of about 30 vias of 0.3 mm, about 3–5 °C/W, or a copper coin below 1 °C/W.

**Not a limit.** It is a board requirement (B2a).

## Items outside my scope

These were not assessed here: RF TX 0 dBm OFDM, autonomous LC LO, ADC 40 MS/s and RX NF. Their owners must make their own entries.

## TX output (rf_tx owner, 2026-11-09): no physical-limit claim

The remaining TX gap (HE20 MCS7 EVM -27 dB reached at -1.0 dBm mean instead of 0 dBm, after 1 dB balun loss) is
**not** a GF180 physical limit, so none is claimed. Evidence that it is closable: the extracted driver alone delivers
+9.0 dBm Psat into the board network (generated/rf_tx-sim-ext.json drv_match_a600), while the full chain saturates at
+5.9 dBm; the ~3 dB loss sits between txmix/txsum and the driver input in the extracted chain (schematic chain: +8.7).
Class-A bound with the board DC feed at 3.3 V: per-leg swing ~0.9-1.2 V and ~18 mA fundamental per leg give
+10..+12 dBm at the pads, consistent with the coordinator's +5..+8 (3.3 V) / ~+10 dBm (6 V cascode) guidance.

## RX (RF RX chain owner, analog/rf_rx): NF ≤ 6 dB and Wi-Fi sensitivity without a board LNA

**Not a physical limit. It is an open design gap (not met in this pass).**

- Device: nfet_03v3 fT is about 16 GHz at ss/32 °C, so f/fT = 0.15 at 2.4 GHz.
  - The classical minimum is Fmin ≈ 1 + 2.3·(f/fT)·√(γδ(1−|c|²)/5) and stays below 1.5 dB.
  - Published inductively degenerated and noise-cancelling 0.18 µm LNAs reach 2.5–4 dB.
  - The PDK noise models are flagged suspect (E19), so add about ±1 dB of model uncertainty.
- What limits this design is the **post-LNA noise**, not the devices. Measured with a switching
  proxy (schematic LNA + I/Q passive mixers + TIAs, 50 % LO, no board match):
  - RF→BB gain G = 21.9 dB.
  - I-TIA OTA noise gain NG = 18. The TIA sees about 1.2 kΩ from the LNA's 1 kΩ resistive load
    at RF, and the overlapping 50 % I/Q paths load each other.
  - With 7.1 nV/√Hz per OTA, F_ota ≈ 126 referred to the 100 Ω source. That alone is about
    21 dB NF unmatched.
  - Caveat: this proxy is about 4–5 dB more pessimistic than the prior transient-noise chain
    result (12.1 dB matched; the matched gain is +4.4 dB). It only shows the direction, not
    sign-off. Either way the OTA term dominates, and the LNA-only NF is 3.3 dB.
- For F_post ≤ 0.5 the chain needs G/NG ≥ 11, against 0.69 now (+24 dB). A realistic board
  match buys about 8 dB of voltage gain. The rest must come from a new LNA (LNTA) and mixer
  interface:
  - a high-gm current-mode LNTA with a high RF output impedance (cascode, no resistive load);
  - a 25 %-duty LO, so the I and Q paths do not overlap;
  - two stages per the coordinator guidance (≥ 20 dB).
  None of this is blocked by fT: gm/Cgs = 2π·16 GHz gives ≥ 6.7× at 2.4 GHz.
- The prior "ideal lossless L-match" also hid a large loss. Zin = 4.3 − j161 Ω (differential)
  needs a Q ≈ 4.6 match into 4.3 Ω. With board inductors of Q ≈ 40, the series loss is about
  4 Ω (differential), roughly the same as Re(Zin), so it costs about **+2.9 dB of NF before the
  balun** (+0.5–1 dB more). The on-chip route needs a real input impedance near 100 Ω
  differential.

### RX NF addendum (fork L, 2026-11-11): DSB ≤ 4.1 dB on-chip at the pessimistic values — not a physical limit, but not closable by the TIA

- Bench bug: `tb.ota_input_noise` overstated OTA en 2× (RC-16f). Corrected, the TIA is no longer dominant.
- Deterministic chain bench (scratch/rf-tia/chain2.py; published LNA RC-16e + mixers, extracted, Rg 150 Ω/10 µm in LNA and mixers, pad_rf_pair), F_DSB = ΣF_parts/(1 + image_src):

| Case (DSB dB) | tt/27/3.3 | ss/32/3.15 |
|---|---|---|
| published TIA, nominal noise | 3.59 | 4.29 |
| published TIA, `fnoicor=1` | 3.99 | 5.12 |
| proposed TIA (+2.22 mA), `fnoicor=1` | 3.27 | 3.99 |
| proposed, + induced-gate est. +0.75 dB on LNA | 3.96 | 4.63 |
| proposed, + design-assumptions +1.5 dB | 4.67 | 5.29 |
| **LNA alone (OTA = 0), +1.5 dB** | **4.40** | **4.77** |

- With the full +1.5 dB RF-noise derate the LNA term alone exceeds 4.1 dB, so the target needs LNA NF ≈ 0.7 dB lower at ss (simulated ≤ ≈ 2.6 dB at ss vs 3.27). Fmin of nfet_03v3 at 2.4 GHz (f/fT ≈ 0.15–0.2) is < 1.5 dB, so this is a design gap (LNA input-device gm / input network), not a physical limit.
- NF vs TIA current (ss, `fnoicor=1`, DSB): +0 mA 4.53 dB (load-L fix only) → +2.22 mA 3.99 dB. OTA term at +2.22 mA is 0.73 of 5.6 total; a further 2× (another +2.2 mA, exceeds the 4.6 mA duplex margin together) would buy ≈ 0.25 dB.

## Radio ADC / DAC (converters owner, 2026-11-10): no physical limit claimed

- **ADC 40 MS/s:** met by 2-way time interleaving, not by a physical-limit waiver. Extracted, 12 envelope corners: worst conversion 39.1 ns (ss/32 °C/3.15 V) against a 44 ns per-core window. The extracted loop is wiring- and logic-bound, not device-bound: the StrongARM regenerates in 0.3–0.6 ns (tt) for large inputs, while each ~3 ns bit cycle (v2) was mostly handshake gates and routed wire. A single core at 40 MS/s would need about 20 ns per conversion at ss. With 10 decisions that is 2 ns per bit, or ~15 FO4 at ss. That is a layout/topology problem (generic row router, ~300 µm loop wires), not an fT limit (L1: nfet fT 14–20 GHz at ss).
- **ADC disabled input load** (233 fF against the 100 fF limit): not a physical limit. It comes from two cores' input routes on a 1.24 mm tall block. Shorter INP/INN routing, or a series isolation switch, would bring it down.
- **DAC static error and CM:** fixed by design (cascoded cells, CM loop). No limit is involved.

## txsum transimpedance 1000 Ω / Zin ≤ 100 Ω at 2.44 GHz (RFT-04, fork G rf-pwr, 2026-11-11): physical limit for any non-resonant load

- **Bound.** The summing node carries at least the rfdriver input capacitance, C_in = 246.5 fF per leg
  (extracted, driver on; `rf_tx-sim-ext.json` `cap_drv_in_on`). For any load without an inductor,
  |Z_T| ≤ 1/(ωC_node) ≤ 1/(2π·2.44 GHz·246.5 fF) = **265 Ω**, independent of topology: a common-gate /
  TIA front (needed for Zin ≤ 100 Ω) moves the same C onto its output node and hits the same bound.
  1000 Ω needs C_node ≤ 65 fF, i.e. a 3.8× smaller rfdriver input. The 1000 Ω / ≤100 Ω pair in
  `spec/analog-architecture.json` (`txsum.parameters`, "selected engineering allocation;
  implementation unqualified") is therefore unreachable as a resistive or active-RC summer.
- **Measured, extracted** (`scratch/rf-pwr/exp_rl_a.json`, txsum ext with the load resistor scaled,
  247 fF driver load): Z_T = 192 / 206 / 211 / 214 Ω for R_L ×1 / ×1.7 / ×2.2 / ×3.1 → asymptote
  1/(ωC) ≈ 217 Ω (C_node ≈ 300 fF incl. mixer-port and own wiring). Full matched chain (ext): pad
  +3.04 / +2.78 / +2.02 / +2.37 dBm at tt and −5.63 / −7.15 / −7.28 / −6.65 dBm at ss/32 °C/3.15 V.
  Raising R_L buys ≤ 1.2 dB of sum swing and **loses** output, because the 0.6–1 V extra drop moves
  the rfdriver input CM (2.83 → 2.16 V tt, 2.60 → 1.81 V ss).
- **Only a resonant load beats the bound:** L = 1/(ω²C) ≈ 14 nH per leg (Q ≥ 4.7 for R_p = 1 kΩ),
  ≈ 0.06 mm² per leg in GF180 top metal, ~0.12 mm² against the 0.0056 mm² txsum budget on an
  over-full die, with no PDK inductor model. Not physics-blocked, so not claimed as impossible; it
  is not pursued because the chain does not need it:
- **What the proxies protect is met.** Zin ≤ 100 Ω guards I/Q interaction: TX image rejection is
  52.4 dB extracted matched (RF-TX-IRR ≥ 35 dB, +17 dB margin) with Zin = 262 Ω. Transimpedance
  guards drive level: at ss the sum swing is 81 mV vs 87.7 mV tt (−0.7 dB) while the pad drops
  8.7 dB, so the RFT-01 ss output loss sits in the rfdriver, not in txsum.
- **Spec request:** replace the block numbers with the chain-derived ones (sum-node swing ≥ 75 mV
  pk diff at 0.3 V BB, TX IRR ≥ 35 dB) — interface-changes RF-PWR-2.

## RF_RX in-band match 2.40–2.4835 GHz (RX-MATCH, fork P rf-lna-p, 2026-11-11): Bode–Fano bound on the LNA input, and why bond/board tolerance must be trimmed per board

- **Bound.** The LNA input is a series R–C: Z = R − jX with input quality factor Q = X/R. For a lossless
  matching network of any order, Bode–Fano gives ∫ln(1/|Γ|)dω ≤ π·ω0/Q, so holding |S11| ≤ −10 dB
  (|Γ| = 0.316, ln 1/|Γ| = 1.15) over a fractional band B requires **Q ≤ π/(1.15·B)**. For 2.40–2.4835 GHz
  plus a ±5 MHz guard (B = 3.9 %) that is **Q ≤ 70** with an ideal infinite-order network; a practical
  3-section ladder reaches it only for Q ≲ 50.
- **The RC-16e LNA cannot be matched across the band by any network.** Extracted Zin ≈ 0.54 − j66 Ω
  (independent review) → Q ≈ 120; schematic + Rg ≈ 0.9 − j77 Ω → Q ≈ 90. Both exceed 70, so the
  reviewer's ±5 MHz −6.7 dB result is a physical consequence, not a tuning error. Most of X came from
  fixed pad-side capacitance (ct bank, 1.8 pF se path, MIM attenuator, dummy MIM: ~1.25 pF of the
  ~1.7 pF per leg), which raises Q by (Cd + Cfix)/Cd ≈ 3.8.
- **Fix (published, fork P):** CS pair 400 → 900 µm at the same current (replica 9 → 22.5 µm), coupling
  MIM 32 → 47 µm, se cap 30 → 11.6 µm, MIM attenuator replaced by gate-shunt switches. Extracted (+Rg
  150 Ω/10 µm + pad_rf_pair) **Q = 27 (ss) … 44 (ff)**; pessimistic (Rg 200, pad +30 %) 28 … 45. With a
  per-board 6-element ladder (0402 L ≤ 12 nH, C ≤ 20 pF) and ct held at 4…10, S11 ≤ −10.3 dB over
  the band at all 12 envelope corners (pessimistic ff −10.3 dB; tt −12.5, ss −14.4).
- **Price of lower Q (quantified, extracted, extpr):** the passive voltage gain of the match is
  ∝ √Q, so with the same 11.7 mA the band NF is tt 2.45–2.87 / ss 3.30–3.79 / ff 1.89–2.24 dB versus
  the RC-16e narrowband tt 2.85–2.98 / ss 2.98–3.13 dB at 2.400 GHz only (ss +0.6 dB, tt −0.3 dB).
  A wider device at the same current (e10, 3200 µm: Q 18) costs ss NF 6.6 dB: the trade is monotonic.
- **Bond-wire / board-part tolerance and on-chip trim (corrected after independent review, scratch/review-lna2).**
  The pad-side real part is only R/2 ≈ 0.6–0.9 Ω per leg; ±0.2 nH of bond is ±3.1 Ω of series reactance per leg.
  A *shunt* trim (the existing ct bank, or any shunt-C range/resolution) cannot absorb it, because it moves R and X
  together (one fixed network, all corners: −2.2 dB at ±0.2 nH). A *series* trim (switched bank on the coupling
  MIM) can absorb ±0.2 nH (reviewer: −9.6…−9.8 dB), but only at about **+1.5–2 dB NF** (0.3–0.4 Ω/leg of switch
  resistance against 0.6–0.9 Ω/leg), which is not affordable while the chain NF fails, so it is not used.
  Board-part tolerance (±5 %) is not absorbed by any single on-chip knob (≈ −6 dB best). **Board trimmers (user decision
  2026-11-12) tried, fork P:** with high-Q parts (L Q 60, trimmer Q 200) two or three build-time trimmers reach only ≈ −5 dB over
  corners × bond ±0.2 nH × parts ±5 %; with pessimistic part Q (L 20, trimmer 50) S11 ≤ −11.6 dB is met only because the part
  loss terminates the input (LNA NF 9.8–18.8 dB). Matching-network efficiency ≈ Q_part/(Q_part + Q_in): Q_in 27–45 against
  Q_L 20–60 loses 1.5–4.8 dB per lossy element. An input Q well below the part Q (≲ 10–15) is needed for a low-loss, tolerant match.
- **The only on-chip escape** is a real input resistance of ≥ ~25 Ω per leg generated noiselessly
  (common-gate / resistive feedback / source degeneration). Measured: a CCC common-gate + CS
  noise-cancelling variant at the same current has S11 −6…−17 dB broadband but NF 11–12 dB, because
  without the passive voltage gain the 50 Ω/leg mixer input dominates (needs ~5× the transconductance,
  ≳ 50 mA, to recover); bond-wire/inductive source degeneration of the present device raises R by only
  3–6 Ω (ωT_eff·Ls with the large fixed C) while costing 1.3–3.8 dB NF. Not pursued.
