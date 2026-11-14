# Current transceiver status and priorities

## Current status

The first die is a **risk-accepted, full-scope tapeout**: all 17 interfaces,
RF and wired, with RF and wired payloads mutually exclusive. The goal is a die
that is safe, diagnosable and has several routes to every function. The rules
are in [`tapeout-plan.md`](tapeout-plan.md). Per-block state against the four
tapeout tests (safe, clean, observable, fallback) is in
[`tapeout-readiness.json`](tapeout-readiness.json); run
`make transceiver-tapeout-readiness` for the summary. Shared-resource decisions
are in [`consolidation-pass.md`](consolidation-pass.md), and board obligations
are in [`board-requirements.md`](board-requirements.md).

The chip only has to work at **27 °C ±5 °C junction and 3.15–3.35 V at the
die**. Safety must hold from 0 to 3.63 V and 0 to 85 °C.

| Freeze stage | State |
| --- | --- |
| 1. Control and digital | Register file proven safe at reset (formal and simulation). Digital macro hardened: DRC, LVS and antenna clean, gate-level reset safety passes. Open: timing at target clock rates (53–72 MHz reached at tt against 125–156 MHz), and area 3.24 mm² against a 2.5 mm² allocation. |
| 2. Pads | All five custom pad families pass safe and clean with the stress-safe protection (worst pulse peak 5.895 V against 6.0 V). Debug-site protection is designed. Shared debug-pad buses are drawn at assembly. |
| 3. Blocks | Every fabricated block has DRC/LVS-clean layout and extracted simulation, except the wired CDR and the not-yet-designed characterization arrays. Performance shortfalls are recorded per block. |
| 4. Top-level assembly | Not started. |
| 5. Submission | Not started. |

Must-work core: POR plus board reset supervisor, bandgap-referenced biasgen
with per-island trunks, island power switches and isolation clamps, analog
test bus, pad protection, SPI register file and safe reset defaults. All pass
safe and clean; host I/O pad hookup is checked at assembly.

## Open-issue register

Risks and open issues, in priority (score) order, live only in [`risk-register.md`](risk-register.md).

## Current architecture decisions

- Keep the complete wired/RF target set and generic controls. Protocol recipes
  live in the FPGA; RF and wired payloads do not run simultaneously.
- RF LO baseline: passive external quadrature LO on `REF_IN`/`AUX_CLK` through
  `lo_ext`. Converter and host clocks come from a `pll_ring` locked to the
  FPGA-forwarded `H2D_CLK`.
- Wired clocking: `pll_ring` at 480–810 MHz with 1, 2 or 4 bits per ring cycle.
  The CDR is a dual-loop design on its own `pll_ring`, with 8× oversampling at
  full rate.
- One common external supply; every non-core island sits behind a default-off
  local switch with reverse-current blocking and core-boundary isolation
  clamps.
- Keep FPGA resampling, interpolation, protocol processing and bulk storage
  off chip. Sampling, sensitive feedback, protection and safe controls are
  local.

## Closure priorities

The submission gates and their current gaps are in [`tapeout-plan.md`](tapeout-plan.md#before-submission).

1. **Close the wired CDR and the external-clock fallback** on extracted
   netlists.
2. **Port wired TX and the slicer to compact cells** for quarter-rate and ss
   operation.
3. **Close digital timing and area** by pipelining or a documented
   reduced-rate operating point.
4. **Integrate observability:** wire every block's taps and status to the test
   bus and register file.
5. **Design the characterization arrays** (device replicas, resistor and MIM
   matching).
6. **Top-level assembly:** floorplan, ring, decap, full-chip DRC/LVS, package
   and bond checks, then the submission package.

## Evidence rules

A capability result must identify the configuration, stimulus, criterion,
outcome, source fingerprint and excluded coverage. Passing expected-rejection
tests are valuable but do not demonstrate the rejected capability. Source hashes
establish provenance; they do not establish performance. Preserve numerical
nonconvergence as a model problem, not a physical impossibility claim.

The [closure inventory](mathematical-closure.json) owns per-capability obligations;
[schematic implementation](schematic-implementation.json) owns circuit coverage.
Measured silicon, extracted simulation, schematic simulation and assigned
behavioral performance are different evidence classes. Missing RF data is
uncertainty, not proof that GF180 cannot meet a target.

## Adopted assumptions and uncertainty ranges

The ranges below are conditional engineering scenarios, **not confidence intervals,
foundry guarantees or process-wide bounds**. Do not automatically assign a reference
circuit's component values to a different transceiver topology. Unknown means
unknown; no finite physical uncertainty interval has been established for those entries.

| Quantity | Evidence / range to retain | Adopted modeling consequence |
| --- | --- | --- |
| Proven AFE performance | Measured amplifier 92 dB gain / 12.5 MHz bandwidth; ADC >30 MS/s functional, 4.27 ENOB and 41 dB SNR at 20 MS/s. These are separate observations with incomplete conditions. | Anchor achievable low-frequency analog operation. Do not promise precision at maximum rate or use this as GHz qualification. |
| Sampling capacitance | Reference overlap-only array 0.569–0.797 pF, nominal 0.666 pF; 1.5–3 pF were assigned loading stress cases. Fringe, coupling and real dynamic load are not bounded by that density interval. | Keep explicit acquisition R, C and time. Select transceiver component sizes separately; include loading beyond plate area. |
| Reference charge | Conditional nominal large/small switch overhead approximately 0.424/0.106 pC at 1.7 V reference span; large-switch extra charge approximately 0.250–0.513 pC across 0.5–2.3 V spans. | Model signed high/low reservoir charge, gate/body exchange, reset and persistence. Do not scale all demand by binary capacitor weight or fit it as grounded capacitance. |
| Reference delivery | Existing 10–1000 pF reservoir and 1–10 kΩ source cases are assigned stresses, not inferred silicon impedances. | Determine required source/sink current and impedance from the actual switching schedule. External decoupling does not bypass local package impedance. |
| Comparator/preamp interaction | Reference static gain falls 29–49% across 1.65 to 0.735 V input common mode at the tested biases. Nominal ±1 mV decisions succeed; noise/mismatch statistics remain unidentified. | Include common-mode trajectory and late-decision gain in converter budgets. Do not apply the percentage universally or treat successful decisions as ENOB. |
| ADC distortion and noise | Optional harmonic-compatible transfer ensemble; at HE20 axis peak 0.6, unquantized gain-corrected differences 0.28–2.31%. Separate 41 dB-SNR normalization scenarios predict 0.38–3.82% noise/signal RMS. | Preserve input normalization, noise bandwidth and nonlinear shape as independent assumptions. These examples are neither exhaustive bounds nor measured RF EVM; do not combine table noise and figure harmonics as one calibrated converter. |
| Analog pad capacitance | Public diode-model scenarios approximately 0.79–1.07 pF before routing/package; not measured RF S-parameters. | Include voltage-dependent protection plus routing and assembly networks. A zero Liberty capacitance is not an analog model. |
| Shared analog switch | Reference output switch approximately 199 Ω at one nominal operating point; no general resistance range established. | Budget switch R and node C together using the selected transceiver topology; this reference value is a sensitivity example only. |
| Clock quality and device speed | No measured GHz fT/fmax, oscillator phase-noise mask or aperture-jitter calibration recovered. Circuit-specific supply pushing around 65 MHz/V versus model assumption 10 MHz/V; neither bounds achievable rejection. | Retain both as sensitivity anchors, seek the permissible pushing/noise boundary, and compare autonomous versus supported external LO/clock operation. Do not substitute clean reference frequency for low output phase noise. |
| Complete RF chain | Receiver NF 6–15 dB and converter 6–9 ENOB at 20–40 MS/s are design scenarios, not measured GF180 ranges. Reference ADC's 4.27 ENOB is a cautionary result, not a process ceiling. | Sweep noise, gain, linearity and headroom jointly at declared signal levels; expose how much improvement each intended configuration requires. |
| Assembly and coexistence | 1–5 nH assembly examples are exploratory; actual package/substrate transfer and resonances remain unidentified. | Sweep complete return/matching/PDN networks, retaining active host switching in either RF or wired mode. External support and RF/wired exclusivity do not remove this coupling. |

Source conditions and limitations: [reference analysis](../verification/reference_afe/README.md).
No transceiver default is promoted to a measured value by these deductions.


## Upstream reuse

| Function | Source | Status |
| --- | --- | --- |
| POR | [Edwards `gf180mcu_ocd_ip__por`](https://github.com/RTimothyEdwards/gf180mcu_ocd_ip__por/tree/a6f16be7c509820f2bd50f7ac517edb58cf8a3f2), Apache-2.0 | Imported unmodified in `analog/core_support/por`. Cold start only; board supervisor covers the rest. |
| Bias generator and bandgap | [Edwards `gf180mcu_ocd_ip__biasgen`](https://github.com/RTimothyEdwards/gf180mcu_ocd_ip__biasgen/tree/96a93f811a10c0b63111a5bd862e3173300802d4), Apache-2.0 | Imported in `analog/core_support`, with two local patches (pin alignment, loop compensation) that should go upstream. |
| Pad protection | Provider bond and clamp geometry; [OCD I/O](https://github.com/RTimothyEdwards/gf180mcu_ocd_io/tree/6e0e354a78793339a4a004a6d9c08990d0eee3e4) as comparison | The custom pads add the stress-safe shunt and discharge resistor. Digital and test-bus pads use provider `gf180mcu_fd_io` cells. |
| Island power switches | [analog_switches](https://github.com/RTimothyEdwards/gf180mcu_ocd_ip__analog_switches/tree/c21d8c0fdd0ee3ca42f8cd496a55ed5afc3d88d1) as a topology reference | Not reused: its body-tied PMOS cannot block reverse current. `analog/island_support` uses a well-switched design. |
| SAR ADC | [gf180-sar-adc](https://github.com/2AMLogic/gf180-sar-adc/tree/54c206134ac047af27b49bd41763c94c39577848), Apache-2.0 | Topology reference only; no layout reused. |
| RF timing | [A01 RFIC workspace](https://github.com/Zachnad0/AUS-NZ-Track-A-RFIC-Workspace/tree/3b74fd559badf6729d5576458abdc528d4f0afa5) | Comparison reference for the LC VCO evaluation. |
