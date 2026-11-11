# Model-uncertainty audit (MOD-00)

Date: 2026-11-11. This audit covers whether the GF180MCU (gf180mcuD) device and passive data can be trusted at our frequencies, and where a model error would break a block on silicon.

Sources:
- the frozen PDK `scratch/digital-closure/frozen-pdk/gf180mcuD/libs.tech/ngspice/`;
- `gf180-device-speed-evidence.md`;
- block READMEs and evidence JSON.

Method: no new tooling and no new simulator runs. The sensitivities below are first-order scaling of the existing extracted results, with the parameter values stated.

**Stress cases.** Speed uses the evidence ranges, low end:
- nfet_03v3 fT 12 GHz at ss. The model gives 17.5, so this is −31 %.
- pfet_03v3 fT 4 GHz.
- 5 V/6 V devices fT 6.6 GHz.
- fmax 22 GHz.

fT is comparatively well bounded: it rests on a DC-exact model, physical capacitances and a 19 GHz silicon anchor. The larger unknowns are noise, passives, Rg, fringe C, mismatch and corners.

## 1. What the PDK provides vs what we use

| Data item | What the PDK has | How we use it | Rating |
|---|---|---|---|
| MOSFET DC (Idsat, Vth, corners ss/ff/sf/fs) | BSIM4. Matches the foundry targets exactly (E1/E2). | Everywhere | **validated** (DC only) |
| MOSFET capacitances (Cgg, Cgd) | Physical values, but `cf=0` (no gate fringe) and cgso/cgdo of 0.10 fF/µm | All speed-critical blocks | **plausible**. The missing fringe adds roughly +10–20 % Cgd/Cgs. Magic extraction adds wiring C but not the gate-to-contact fringe. |
| fT / fmax | Not a model parameter. fT is implied by C and gm. | LNA, mixer, PA, CML, sampler | **plausible**: 12–20 GHz (ss). fmax is unknown until Rg is added. |
| Gate resistance / NQS | `rgatemod=0` on every card. No Rg and no NQS. | Explicit Rg is used only in the QVCO/LO-CML benches and the characterization cells | **unknown**. Rg = 60–150 Ω per 10 µm (estimate). It is missing from the LNA, mixer, PA, CTLE, slicer, wired TX and pll_vreg benches. |
| Thermal noise at RF | `tnoimod=0` (charge-based BSIM default). No induced gate noise. | LNA NF, mixer NF, VCO PN | **unknown**. An independent GF180 LNA project (E19) suspects the noise parameters. |
| Flicker noise | `fnoimod=1`. noia/noib/noic, with a `noise_corner` switch `fnoicor` that raises noia about 11× (nfet_03v3 3.2e41 → 3.5e42) and pfet_06v0 by 330×. | Baseband/TIA (5–9 MHz IF), VCO close-in PN, bandgap | **plausible** (the foundry supplies a corner). We do not know whether any bench runs `fnoicor=1`. |
| Mismatch | `fets_mm`: Pelgrom, nfet_03v3 A_Vt 7.15 mV·µm and A_β 0.70 %·µm. Separate `*_stat` and `statistical` global MC libs, plus res/MIM/BJT stat libs. | **No block has run a mismatch MC** | **plausible** model, **unused** |
| MOS varactor | `cap_nmos/pmos_03v3(_b)`: a pure tanh C(V) capacitor. **No series R, no Q, no frequency dependence.** | QVCO tuning (`qvco.spice:90-99`) plus 2 Ω per side added by hand | **unknown** for Q. C(V) is plausible. |
| MIM | `cap_mim_*`: area plus sidewall C, TC, VC and corners (`mim_corner`). No plate or contact R, no bottom-plate parasitic. | LNA coupling, QVCO bands, refbuf 100 pF, ADC | **plausible** for C. **Unknown** for R and the bottom-plate parasitic, which matters only for the RF bank Q. |
| Inductor | **None in the PDK.** | Our `spiral.py`: Mohan L plus FastHenry, Yue-Wong substrate. **Substrate resistivity is not published** (we assume 8–20 Ω·cm). | **unknown**. L is plausible within ±10 %; Q is unknown (model 8.5, our low-Q case 4.6–5.2). |
| Pad / ESD C | No model. Values come from extracted pad cells: RX pad 2.35 pF, ATB pad about 2.4 pF. | CTLE return loss, wired TX, LO pads, LNA input | **plausible** for the extracted metal. **Unknown** for the ESD junction C and its voltage dependence. |
| Poly gate Rsh, substrate | Not used. Rsh is assumed at 7–8 Ω/sq. | Rg estimates, inductor Q | **unknown** |
| Corners | ss/ff/sf/fs plus TT, derived from DC targets | All blocks | **plausible** for DC. **Unknown** whether the corners bound the C and noise spread. |

**Public evidence.**
- There is no GF180MCU RF silicon data (fT/fmax, ring oscillator, LNA, VCO) in the public record. The device-speed review (E15–E22) and the 2026 web searches agree on this.
- Others are only now taping out GF180 LC-VCO, PLL and LNA chips (Chipathon 2026 #143, 2AMLogic/gf180-pll, rcyaon/cmos-lna), all of them simulation-only.

## 2–3. Per block: sensitive parameters, the error that breaks spec, and coverage

In the "Covered?" column, **Y** means guardband plus trim/fallback cover the plausible error. **P** means partial coverage. **N** means a gap.

| Block | Most sensitive data | Current extracted margin | Error that breaks spec (first-order) | Guardband / trim / fallback | Covered? |
|---|---|---|---|---|---|
| **LNA** | Noise model (tnoimod, no gate noise), Rg (none simulated), pad/ESD C, board match | Already fails: gain −12.7 dB vs +20 dB; NF 14.3 dB unmatched and 4.35 dB with an ideal L-match vs 6 dB (RFR-01). The evidence may be stale. | Any error. With the ideal match the NF margin is 1.65 dB. Rg of 100 Ω on the input device adds about 0.5–1 dB NF (Rg/Rs ≈ 0.1–0.2 times the gm term). A gate-noise omission adds about 0.5–1 dB. Together they exceed the 1.65 dB margin. | ct0..2 shunt-C trim, `rt`, `se`, gain_lo; bypass `byp` with a board LNA (chain NF 3.2 dB) | **P**: the external LNA is the real cover. On-chip NF cannot be confirmed without a noise-calibrated structure. |
| **RX mixers** | Rg, LO waveform (rise time from fT), flicker corner of the TIA | Conversion gain 17.7–20.5 dB; offset after calibration ±4.5 mV vs ±10 mV | Flicker corner ×11 (`fnoicor=1`) on the TIA input pair inside the 2–9 MHz IF: unknown, not simulated. fT −31 % slows the LO edges; the passive quad is tolerant. | 5-bit offset DAC; TIA high-Z for external downconversion; bb_tap | **P**: run the TIA noise once with `fnoicor=1`. |
| **QVCO / LO** | Inductor L and Q (no PDK model), varactor Q (none in the model), fixed and wiring C, Rg | Extracted RC+G (v2rcg): ss band-0 top is **2.349 GHz, below the 2.40 GHz ISM bottom**. **Bands ≥12 do not start** with 2 Ω of wire. | f ∝ (LC)^-½: L +10 % gives −4.7 %, parasitic C +10 % gives about −3 %. **The range already misses at ss with L +10 % and low Q.** Start-up: varactor or MIM series R of a few Ω drops the tank Q below the gm margin, which is already lost at high bands. | 4-bit band bank, VTUNE 0.3–3.0 V, I/Q trim (planned); **external LO is the first-die baseline**; LO/8 on CLK_OBS | **N** for the autonomous LO: the range misses even before model error. **Y** via external LO (LO-04/05). |
| **PA / rf_tx** | fT and fmax (with Rg), 5/6 V device fT, board match | ss linear −2.8 to −5.6 dBm vs 0 dBm (**fails**); EVM −22.8 vs −27 dB | Gain scales with fT and fmax. 6 V cascode fT at 6.6 GHz gives fT/f ≈ 2.7, so a further −1 to −2 dB. No Rg was simulated (MOD-16). | 4-bit tail code, board match retune, external PA (+25 dB), PMOS bypass | **P**: power covered by the external PA; EVM/linearity has no model cover. |
| **CDR ring / pll_ring** | Wiring and fringe C (cf=0), fT | ss open-loop top 850–916 MHz vs 810 MHz: **5–13 % margin** | f ∝ 1/C. **Fringe C +10 % or fT at 12 GHz (−31 %) breaks 810 MHz at ss.** At tt (about 1.04–1.1 GHz) there is margin. | VCTRL 0.8–3.3 V; the replica covers 480–810 at all corners only per the model; external WCLK_IN (currently failing); 625 MHz quarter rate as the default | **P**: 810 MHz at ss is not covered; 625/480 MHz are. The replica VCTRL has no ATB, so it cannot be measured (INT-04). |
| **Samplers / slicer** | Latch τ (fT, node C, Rg), mismatch A_Vt, kick-back C | 0 errors to 3.6 Gb/s at every corner; fails at 4.0 Gb/s ss | τ ∝ C/gm. At 12 GHz τ is ×1.46, so 810 MHz goes from about 8.5 τ to about 5.8 τ (marginal). 3.6/4.0 Gb/s suggests about 10–25 % speed headroom at the 2.5–3.24 Gb/s use cases. Offset: σΔVt = 7.15/√(WL); for a latch pair of about 1 µm² that is about 7 mV. Systematic +14 mV ± 3σ (21 mV) gives −7…+35 mV, inside the trim range −23…+42 mV. **If A_Vt is 2× higher, it gives −28…+56 mV and falls outside the range.** | 4-bit per-phase trim (asymmetric); quarter-rate default | **P**: speed covered at 625 MHz. The offset is covered only if the Pelgrom data is right. No MC has been run (WRX-14). |
| **CTLE** | Pad/ESD C, tail headroom at ss, load C | Peaking 0.35–15.3 dB, codes 0–7; return loss already 8.4–9.8 dB vs 10 dB (WRX-04) | Pad C +20 % gives a further 1 dB of return loss and a lower pole. Peak frequency ∝ 1/C_load: +20 % C shifts the peak down about 17 %, which the 8 codes absorb. | 3-bit boost, bypass | **Y** for equalisation (code range). **N** for return loss, which is already failing. |
| **Wired TX CML/CMOS** | Pad/ESD C, pre-driver fT, cf=0 | Eye 227/400 ps at ss (core only) | Pad-limited pole at 2.1–4.2 GHz. Pad C +30 % costs about 10 % of the eye. The pre-driver has more than 2× bandwidth margin. | 8-bit MAIN/POST DACs (emphasis); TMDS mode; lower rates | **Y** for swing and emphasis. The block-level corner sweep has not been run. |
| **ADC** | Comparator offset (mismatch), MIM ratio and matching, pad C on the input | ENOB 8.0 (32-pt FFT, tt only) | MIM matching worse than 0.1 % (8b) is unlikely to break it. Comparator offset +7–14 codes is removed digitally. Speed margin at ss (16–20 MS/s per core) scales with fT. | Digital offset removal; external ADC via BB_I/Q | **P**: no MC and no INL; external fallback exists. |
| **DAC** | Current-source mismatch (A_β), output CM | Endpoint error about 10 LSB; CM 0.99–1.83 V over corners | Mismatch MC not run. gain_trim and offset_trim **have no analog effect**. | External DAC via BB pads; hold_zero | **N** on-chip (no working trim). **Y** via the external route. |
| **Bias / bandgap** | PNP model, poly R spread, flicker | VBG 1.204–1.220 V; outputs 7.5–12.1 µA before trim | ±20 % poly R is covered. A PNP Is/beta error of ±20 % gives about ±5 mV VBG. | bgap trim 1.138–1.341 V; idac2 per die; ATB0 VBG force | **Y**: trim range is about 10× the plausible model error. |
| **pll_vreg** | Pass-device gm, MOS-decap C/ESR, Rg-free amp | PSRR −23.1 dB vs 20 dB (3 dB margin) | A loop-pole shift from +20 % C or −31 % fT costs about 1–3 dB PSRR at 100–200 MHz, which consumes the margin. | BYP (reset = bypassed); ATB_G force | **Y**: bypass is the default. |

**Cross-cutting gaps.**
1. Rg is absent from every RF and high-speed bench except the LO and characterization cells.
2. No mismatch MC has been run on any block, although `fets_mm` exists.
3. No bench is known to use the `fnoicor=1` flicker corner.
4. The inductor and varactor Q have no foundry basis, and the substrate resistivity is unpublished.
5. Pad/ESD C is only extracted metal; no junction model.

## 4. On-die characterization: what exists and what to add

Existing structures (`analog/characterization/`):

| Structure | Area | Measures |
|---|---|---|
| `pt_char_ro33` | 0.010 mm² | 3.3 V gate delay |
| `pt_char_ro50` | 0.010 mm² | 5 V gate delay |
| `pt_char_cmldiv` | 0.029 mm² | effective fT |
| `pt_char_rffet` + OPEN/SHORT GSG | 0.335 mm² | fT, fmax, **Rg** |
| `pt_char_atb` | 0.029 mm² | I–V replicas plus poly-R and MIM matching pair |
| `vco_replica` | (in timing) | ring tuning curve |
| ESD_TEST pad | — | clamp I–V |

These already cover fT, Rg (via GSG) and C/R matching.

Open problems with the existing structures:
- The speed cells have **no CLK_OBS/ATB/enable codes yet** (INT-04), so they are unreadable.
- The convkit routing halves their speed sensitivity (MOD-14).

Missing items, in order of value per area:

| # | Add | Area | Calibrates |
|---|---|---|---|
| 1 | **Wire the existing speed cells and the vco_replica VCTRL to CLK_OBS/ATB codes** | about 0 (codes only) | Without this, the structures above give nothing. **Highest priority.** |
| 2 | **QVCO tank tap.** LO/8 on CLK_OBS already exists. Add a band-sweep procedure, plus an ATB tap on VTUNE and on the core tail current. f(band, VTUNE) at fixed L inverts to L·C. The start-up threshold current gives tank Q (inductor plus varactor). | about 0 to 0.005 mm² | Inductor L and Q, varactor C(V) and Q, from the real VCO. Cheaper than a standalone inductor test. |
| 3 | **Standalone spiral + varactor 1-port on the existing GSG frame.** Reuse the `pt_char_rffet` OPEN/SHORT de-embedding and swap the DUT for a 1-turn copy of `pt_spiral` (Q and L) or a varactor array. | about 0.11 mm² per site (430×260 µm) | Direct L/Q/substrate. **Only if area allows.** Item 2 gives most of the same information. |
| 4 | **Pad-C test.** One unbonded copy of the RX/LO pad on the ATB bus, measured by a ring oscillator or relaxation oscillator (cheap). Alternatively, difference-measure ATB pad charge with and without the pad. | about 0.01 mm² plus the pad site (none spare) | Pad and ESD C. Without a spare pad: an on-chip relaxation oscillator loaded by a pad-cell replica (no bond). |
| 5 | **Mismatch array.** 8–16 minimum-latch-size nfet pairs on the ATB, measured as ΔVgs at fixed I. | about 0.01 mm² | A_Vt for the slicer and ADC offset ranges |
| 6 | **Compact ro33 / cmldiv (MOD-14)** | about 0.02 mm² | Defer to die 2 per MOD-14 |

The total added is about 0.03 mm² without item 3, or about 0.14 mm² with it. Spare reserve is about 0.41–0.9 mm²; the two sources disagree.

Noise: no cheap on-die NF structure exists. Measure the LNA and mixer NF on the bench through the `byp` and `bb_tap` paths, and back-fit the noise parameters from that.

## 5. Recommendations (sign-off actions, no new tooling)

1. Add an explicit Rg of Rsh·Wf/(12·L·nf) + 1/(5·gm) to the LNA, mixer, PA, CTLE, slicer and wired-TX benches. Rerun one tt and one ss point each.
2. Run one MC (`fets_mm`, `sw_stat_mismatch=1`, 50 runs) on the slicer, the ADC comparator and the DAC sources. Check them against the trim ranges.
3. Run the TIA/mixer and VCO noise once with `fnoicor=1`.
4. Rerun the speed-critical cells once with Cgg/Cgd +15 %, an added cap per gate (cf=0 proxy), and the ss/12 GHz case: pll_ring at 810 MHz, slicer, CML. 810 MHz at ss is expected to fail, so confirm 625 MHz is the default and 810 MHz is "best effort, trimmed on die".
5. QVCO: recentre the bands so that the ss/L +10 %/low-Q case still covers 2.40–2.4835 GHz with 3 % or more margin, and fix the start-up at high bands. Until then the autonomous LO is not a deliverable; the external LO is.
6. Implement characterization items 1, 2, 4 and 5 (about 0.03 mm²). Take item 3 only if area remains after INT-04 closes.
