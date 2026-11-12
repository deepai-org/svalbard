# ESD tiering review (analysis only, 2026-11-12)

Scope: should each pin class keep the current 2 kV HBM / 500 V CDM target (ESD-02), or drop to 500 V–1 kV where that improves performance? No block files edited. Every saving below is a **first-order scaling estimate** from the published cells, not a simulation. Re-tuned cells must be re-run on `stress_safe_family_sims.py` and `hbm_core_screen.py` at the new level before any claim.

## 1. Industry basis (verified)
- **JEDEC JEP155 / Industry Council White Paper 1** (HBM/MM): HBM levels from 500 V to 2 kV are equally safe for manufacturing when basic ESD controls are in place. 2 kV gives no measurable field-return benefit over 500 V. [ESDA WP1](https://www.esda.org/standards/complimentary-downloads/view/1872), [JEP155B](https://www.scribd.com/document/507616416/JEP155B)
- **JEP157 / White Paper 2** (CDM): a minimum of 250 V CDM is safe with basic controls. Below that, the production site needs more detailed controls. [In Compliance: Industry Council](https://incompliancemag.com/esd-target-levels-the-industry-council/), [ESDA Council summary](https://esda.org/assets/News/TheIndustryCouncilonESD.pdf)
- JEP155/157 also say that high-speed and RF pins justifiably use lower levels.
- Component HBM is not system ESD. IEC 61000-4-2 is handled at the board (B36 TVS).

## 2. What the 2 kV design costs today (from the repo)
| Item | Value at 2 kV | Source |
|---|---|---|
| Primary steering diodes | 4+4 × 22.5 µm²/pad, **0.169–0.181 pF/pad** | pads README |
| network-gc-d2 extra up-row (hspad, USB v9) | **+0.14 pF/leg** (+0.12 precharged); pad 6.18–6.91 → 5.04–5.41 V | PD21, PD29 |
| HBM peak current | 1.33 A (2 kV/1.5 kΩ); 1 kV = 0.67 A; 500 V = 0.33 A | |
| Pad peak, no d2 | 6.18–6.91 V, rail 3.9–4.6 V → ≈ 1.2–1.7 Ω effective pad-to-rail | PD28 |
| GC shunt | nfet_06v0 bank + 2×90² µm MIM (≈ 32 pF), RC clamp 80×50 µm; ≈ 51,500 µm² per pad pair | README, PD13 |

**Scaling rules (estimates):**
- Option A: keep the clamp and drop the level. At 1 kV the pad peak is ≈ rail(~3.6–4.0) + 0.7 + 0.67 A × 1.2–1.7 Ω ≈ **5.1–5.8 V** with no d2. At 500 V it is ≈ **4.6–5.0 V**.
- Option B: keep the current density and shrink the diodes ∝ I. That removes the d2 row and 50 % (1 kV) or 75 % (500 V) of the primary-diode C at the same ~6.2–6.9 V pad peak. **Option B gives up the margin the core gates need.**
- Usable split at 1 kV: drop d2 (−0.14 pF), keep the primary diodes at full size, pad ≈ 5.1–5.8 V. Or shrink the primaries 30 % (≈ −0.05 pF) and accept ≈ 5.5–6.0 V.

## 3. Pin-class table (recommendation)
| Class | HBM / CDM target | C saved per leg (est.) | Performance gain (est.) | Keep or change |
|---|---|---|---|---|
| Supplies, grounds, rail clamps | **2 kV / 500 V** | 0 | Clamps are not in a signal path, so a lower level buys nothing | keep |
| Host-link LVCMOS (312.5 Mb/s) | **2 kV / 500 V** | ~0.2 pF, not needed | Timing has margin | keep |
| Debug / ATB / BB_I/Q / WMON | **2 kV / 500 V** | — | These are the most hand-probed pins (bench). bb_tap already passes at 4.87 V | keep |
| Clocks / REF_IN / AUX_CLK (2.4 GHz ext-LO fallback) | **1 kV / 250 V** | −0.14 (no d2; not fitted today) to −0.05 | REF/AUX pad C −0.05 pF moves the COB resonance (PKG-05) slightly. **Does not fix PD29(1)(2)**: lo_ext/diff_clk_rx 3.3 V devices see ≥ 5.1 V vs a 3.63 V screen | optional |
| RF_RX (LNA) | **2 kV / 500 V** (keep) | ≤ 0.09 | Zin 1.46 − j53.3 Ω (Q ≈ 36). 0.045 pF less diff shunt moves Q by ≈ 3–4 %: **≤ 0.1 dB NF, S11 unchanged within trim**. LNA already passes the PD29 screen (gate 0.94 V behind its MIM). This is the antenna pin | **keep 2 kV: no meaningful gain** |
| RF_TX (rftxpad) | **1 kV / 250 V** | −0.14 avoided (ESD-06 d2 fix) + ≈ −0.05 | **Closes ESD-06 at no C cost:** rfdriver cascode 6.18 V (ss/0, 2 kV) → est. 5.1–5.8 V < 6.0 V. Psat (+9.0 dBm driver, +5.9 chain): ≈ +0.1–0.2 dB less match loss vs the d2 fix. The ESD-04 onset (> 4.4 V) is unaffected | **change** |
| HS RX pair (pad_hspad) | **1 kV / 250 V** | −0.14 (d2) to −0.19 | 1.11–1.14 → ≈ 0.92–0.97 pF/leg. Die RL at 2.4 GHz 8.0–8.5 → **≈ 9.6–10.0 dB** (shunt-C formula reproduces 8.2 dB at 1.12 pF). COB 1.25–2.5 GHz stays package-limited (6.3 nH, PD26): ≈ +1 dB (5.7–6.5 → ~6.7–7.5 dB). The PD26 ladder is still needed for compliance | **change** |
| USB (wirepad v9) | **1 kV / 250 V** + board TVS mandatory | −0.14 (d2) to −0.19 | PD45 2.82–3.25 pF (1.65 V) / 3.57 (0.2 V) → ≈ 2.65–3.10 / 3.40 pF. **Still fails 2.7 pF at ss and at HS bias.** Most of the excess is the 6 V pad-side devices and the RX load, not ESD. PAD-03 still needs the USB budget re-derived (TDR / RL) | change; not a fix |
| WIRE_TX (txpad) | **1 kV / 250 V** | −0.14 to −0.19 | Disabled loading 2.706/2.713 → ≈ 2.52–2.57 pF (now under 2.7). Or spend the saving on the PD30 6 V TERM switch (+0.18/+0.29/+0.19 pF): **closes ESD-05 C-neutral**, though Rdiff(ss) 127 → 152 Ω remains | change |

**Area:** at 1 kV the GC shunt bank and steering diodes can drop to ~½ width. The MIM trigger cap is set by τ, not I, so it stays. Estimate ≈ 10–15k µm² per pad pair × 4 pairs (RF_TX, HS, USB, WIRE_TX) ≈ **0.04–0.06 mm²**. Only worth taking during a re-layout that happens anyway.

## 4. Core-gate HBM failures (PD29): what tiering does and does not buy
- **Does not fix:** cases (1)–(4) are 3.3 V devices (lo_ext, diff_clk_rx, detect TX-side) on a 3.63 V screen. Even at 500 V the pad sits at ≈ 4.6–5.0 V. The 6 V conversions or series-R + 6 V-clamp fixes remain mandatory. A lower level does not let any of them revert to 3.3 V devices.
- **Does buy:**
  - (5) rfdriver (6 V cascode, 6.18 V) clears without the +0.14 pF.
  - Every 6 V conversion gains ≈ 0.5–1 V of margin (5.04–5.41 V → ≈ 4.6–5.0 V at 1 kV with d2 kept, where C allows).
  - The series-R/MIM tracking networks (e.g. the bb_tap 100 kΩ + 128 fF) could shrink, but those are not on the critical path.
- **Questionable prior assumption:** the 3.63 V screen for a ~150 ns HBM transient is very conservative. GF180 3.3 V oxide transient breakdown is well above 3.63 V. A PDK-backed transient-oxide limit (for example 5.0 V for ≤ 200 ns) would collapse most of PD29 at any HBM level. Ask the spec owner to set this limit from PDK data rather than the DC Vmax. This is more valuable than tiering.

## 5. CDM
- **Target: 250 V CDM chip-wide** (JEP157), dropped from 500 V.
- CDM current depends on package/die capacitance, not on the HBM level. Shrinking the steering diodes for HBM reduces CDM headroom one-for-one. So **do not take Option B (shrink to the same density) below 1 kV.**
- Keep the local secondary clamps (6 V drain diodes, e.g. hspad RX→VDD/VSS 4 µm) at their current size. They are the CDM gate guard.
- ESD-01 (cross-domain VDD↔VISL) stays closed only if the domain-crossing diodes are not resized.
- This is COB: the bare die is handled at die-attach and wire-bond, which is the peak CDM exposure. The die is unencapsulated, so the assembly-house controls matter more than the package rating.

## 6. Fragility flags
1. **No silicon ESD data at all.** PD35 dropped the ESD_TEST/TLP pad, and every HBM number is a SPICE surrogate (patched ngspice, no snapback/TLP calibration). Lowering the target removes the margin that covered model error. Mitigation: restore a TLP test site (MOD-08 proposes ~0.01 mm²), or keep diode widths and only drop d2 (Option A).
2. **RF_RX and USB face connectors.** A 1 kV pin behind a connector without a TVS will fail in the field. B36 (antenna TVS ≤ 0.3 pF) and a USB TVS (≤ 0.5 pF, e.g. a USB2-HS-rated array) become **mandatory, not optional**.
3. Do not go below 500 V HBM / 250 V CDM on any pin. JEP155/157 basic-control safety ends there.
4. Mixed levels must be recorded in the datasheet/pin list. "2 kV" can no longer be stated chip-wide.

## 7. Handling requirements to add (board-requirements.md, bring-up docs)
- All handling, assembly and bring-up in an EPA compliant with ANSI/ESD S20.20 or IEC 61340-5-1 (covers ≥ 100 V HBM / ≥ 200 V CDM devices).
- Ionizers at die-attach and wire-bond; grounded tweezers/collets; no ungrounded bare-die handling. Ship dice in dissipative carriers.
- Wrist straps and grounded mats for every bench probe of debug/ATB/RF pins. Ground the probe and the coax shield before contacting RF_TX/RF_RX/HS pins.
- Board: populate the USB TVS and the antenna TVS/shunt-L (B36). Use connector-side TVS on the HS RX/WIRE_TX connectors, or hot-plug only when powered down. Use series resistors on external clock/REF sources where the B3 amplitude budget allows.
- Discharge cables (TDR/coax) before connecting to wired/RF pins (cable discharge event).

## 8. Blocks to re-tune (if accepted)
| Block | Change | Re-run |
|---|---|---|
| pads `rftxpad` | 1 kV target; do **not** add the ESD-06 d2 rows | hbm_core_screen `rf_tx_rfdriver` at 1 kV (expect ≤ 5.8 V); PA match/EVM |
| pads `hspad` | drop the `--extra-up-rows 1` | family sims at 1 kV (0.67 A); die/COB RL |
| pads `wirepad` (USB) | drop d2 | 1 kV screen (613 MOS); PD45 C; USB budget still open (PAD-03) |
| pads `txpad` | drop d2 or spend it on the PD30 6 V TERM switch | 1 kV screen (536 MOS); RL @1.25/2.4 GHz |
| spec | ESD-02 → tiered table above; transient-oxide screen limit | — |
| board | TVS + handling items in §7 | — |

**Net expected gains (est.):** hspad die RL +1.5 dB at 2.4 GHz; WIRE_TX back under 2.7 pF, or ESD-05 closed C-neutral; ESD-06 closed with no PA C; USB −0.15–0.19 pF (not enough on its own); RF_RX ≈ nothing, so keep 2 kV there.
