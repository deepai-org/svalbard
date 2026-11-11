# Whole-chip power and resource allocation

`analog-architecture.json:resource_policy`, per-block `resource_allocation` and
`resource_totals` own the allocation. `contract.json` owns assembly terminals
and physical services. The [pad implementation](../analog/pads/README.md) owns
physical connectivity and circuit evidence. Where a block has extracted
evidence, its allocation is the measured current and about 1.25–1.5× its
measured area; otherwise it is a planning requirement. `area_reallocation_log`
records every move between blocks.

## Implementation allocation

| Area group | Ceiling (mm²) |
| --- | ---: |
| converters | 1.30 |
| digital | 1.65 |
| memory | 0.85 |
| reserve | 1.71 |
| rf | 3.00 |
| timing | 1.67 |
| wired | 2.74 |

The core ceiling is 12.92 mm². All wired and RF blocks retain fabricated area
while inactive. Area freed by consolidation and measured layouts is booked to
debug cells, debug-pad protection and reserve
(`tapeout-readiness.json:reserve_area_mm2`). The 1 nF supply decoupling needs
its own area, because the digital macro uses flip-flop arrays rather than SRAM
macros that MIM could sit over. The separate 100 pF
reference reservoir belongs to the 0.148 mm² reference-buffer allocation.
At the conservative 0.9 fF/µm² planning density, 1 nF alone needs 1.111 mm² of
plates before routing. Density, overhead and impedance need physical checking.

## Reconciled mode currents (2026-11-09)

`spec/budgets/power_budget.py` produces `spec/budgets/power-budget.json` and is the only
source of mode totals. Run with `--check` to make it fail on a ceiling violation. It sums
the per-block `current_budget_ma` in `analog-architecture.json` and applies each branch
override once. These totals match `resource_totals.current_ma`.

The previous `tapeout-readiness.json:current_envelope_ma` values (236.27 / 244.55 /
260.96 / 247.39 mA) cannot be reproduced from any recorded derivation, so this script
supersedes them. Wired and USB were +16.14 mA against the per-block sum.

Two blocks are still allocations, not measurements. The script substitutes the only
evidence that exists for each:

| Block | Allocation | Evidence | Basis |
|---|---:|---:|---|
| digital | 19.5 (RF) / 36.5 (wired) mA | **207.2 mA** upper bound; 24.5 mA lower bound (clock pins only) | `digital-hardening-evidence.json` `power__total` 0.684 W: OpenROAD, vectorless, nom tt, every SDC clock at target, no mode gating, stale RTL. `clock-power-screen.json` gives the lower bound. |
| hostio | 110 mA | 95.2 mA typical; **116.8 mA** at the 8 pF Artix load | `host-power-allocation-screen.json` and `artix-load-power-screen.json`: alternating data, two-pad extrapolation with allowances, nominal. |

Mode totals in mA. The "with requirement" column holds digital to PWR-DIG
(≤ 60 mA wired/USB, ≤ 40 mA RF) and RF host IO to PWR-HOST-RF (div2):

| Case | Ceiling | Allocation | Evidence bound | With requirement | Margin (with requirement) |
| --- | ---: | ---: | ---: | ---: | ---: |
| RF, external clock (primary first-die RF) | 240 | 224.09 | 418.60 | 193.00 | +47.0 |
| RF, autonomous synthesis | 240 | 253.02 | 447.53 | 221.93 | +18.1 |
| Wired, on-chip PLL | 292 | 244.82 | 422.33 | 275.14 | +16.9 |
| Wired, external clock (`WCLK_IN`/`REF_IN`) | 292 | 248.05 | 425.56 | 278.37 | +13.6 |
| Wired, TMDS | 292 | 224.82 | 402.33 | 255.14 | +36.9 |
| USB | 292 | 231.25 | 408.76 | 261.57 | +30.4 |
| Stopped | 292 | 4.62 | 4.62 | 4.62 | — |

**Reading the table.**
- On allocations alone, every case except autonomous RF fits.
- On evidence, every mode is over its ceiling by 110–208 mA, because the digital macro's only post-route power number is 5.7× its allocation.
- The evidence-bound digital number is pessimistic: it is vectorless, every clock runs at the SDC target, and nothing is gated. It is still the only number on record.
- The AC-1 gearbox halves the core clock ([interface-architecture-changes.md](interface-architecture-changes.md)), which makes these requirements plausible:
  - **PWR-DIG-WIRED** ≤ 60 mA and **PWR-DIG-RF** ≤ 40 mA, with unused domains clock-gated.
  - Signoff by SAIF-annotated power from the dense-service simulations.
  - **PWR-HOST-RF**: RF modes run `debug.host_link.rate=div2`.
    **Full-rate exception (GX-2 host-fed 80 MS/s TX, 12-bit):** H2D may run at full rate when `rf_tx_clk` = 80 MHz with the interpolator bypassed; D2H stays at div2 or lower, which needs HB-4 `d2h_rate`. H2D inputs cost the chip no driver current, so the hostio budget is unchanged. Without HB-4, the mode uses MODE8 samples at div2 (1.28 of 1.44 Gb/s; RF-HT40-TX). Full rate on D2H in RF modes is not allowed.
- The 8 pF host load leaves hostio 6.8 mA over its 110 mA allocation. The budget carries the evidence value.

External-clock RF is the qualified primary RF case. Autonomous RF exceeding the
240 mA envelope is accepted as a known limit of the separately qualified
autonomous mode.

Apply clock/TMDS branch overrides exactly once and only to their selected
blocks. External RF timing uses the passive external I/Q LO through `lo_ext` (0.19 mA,
booked on the `quadrature` slot), charges no clock receiver for the LO, and
replaces the shared PLL's (`rfpll`) 12 mA with the `host_follow` ring PLL plus
prescaler (5.26 mA); input,
quadrature/distribution and warm analog loads remain charged. Autonomous RF
needs a circuit saving or separately qualified envelope. No unused margin is
claimed for the external-clock RF case.

Each shared baseband filter (`bbfilter`, booked on `rxfilter_i/q`; it carries the
merged TX filter and PGA) has 3.77 mA and 0.4934 mm², so the pair has 7.54 mA and
0.9868 mm². `txfilter_i/q` and `pga_i/q` are charged nothing. A conditional
paired RX sizing estimate of 7.251 mA does not establish area/noise/headroom
fit. DACs each reserve 2 mA including 1 mA provisional support. Count global
clock-tree and local switching capacitance once, not in both budgets.

## Supply-drop and thermal budget (envelope, 2026-11-09)

Computed by `spec/budgets/power_budget.py`. This replaces the tapeout-plan figure computed at 250 mA.

The available drop is the minimum source voltage (3.3 V − 1 % = 3.267 V) minus the minimum die rail (3.15 V), which is **117 mV**. Contributions:
- **Board**, from regulator sense to the COB pads: 20 mΩ. This is requirement B2a.
- **Bonds**: 0.1 Ω each, 8 supply ∥ 10 return. A 4.44× unequal-share derating reproduces the plan's 25 mV at 250 mA, giving 0.100 Ω effective.
- **On-die ring and grid**: 0.1 Ω planning allocation, not yet extracted.
- **Worst island switch**: full-RC extracted at design current. The wired island is 19.87 mV at 80 mA.

| Case (worst mode) | I max | Board | Bonds | Grid | Island switch | Total | Margin to 117 mV |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Allocation (autonomous RF) | 253.0 mA | 5.1 | 25.3 | 25.3 | 19.9 | 75.5 mV | +41.5 mV |
| Evidence bound | 447.5 mA | 9.0 | 44.7 | 44.8 | 19.9 | 118.3 mV | **−1.3 mV** |
| With PWR-DIG (wired, external clock) | 278.4 mA | 5.6 | 27.8 | 27.8 | 19.9 | 81.1 mV | +35.9 mV |

Island switches at their actual peak allocation, rather than the 1.25× design current, have 4.4 mV (wired) to 9.1 mV (debug) of margin against their 20 mV target. The "0.13 mV" figure is the margin at 80 mA design current, not at the 62.86 mA load. Native supply-cell utilization under even sharing is 0.58 with PWR-DIG and 0.93 on the evidence bound (8 × 60 mA).

**Thermal.**
- P_max is 0.98 W with PWR-DIG and 1.55 W on the evidence bound. Both use 3.35 V × I_max and add 45 mW for TMDS driver plus clamp leakage and 6.5 mW for the RX level divider.
- Stopped power is 15 mW.
- A glob-top COB in still air (θJA of about 40–100 °C/W, class value, not measured) would rise 39–98 °C. **Free air cannot hold 27 ± 5 °C.**
- Mode switches are faster than any plate controller, so the 10 °C window minus ±2 °C control must absorb the whole stopped-to-max step. That requires θ(junction→temperature-controlled plate) ≤ **8.25 °C/W** with PWR-DIG, or 5.21 °C/W on the evidence bound.
- These limits are board requirement B2a. scratch/reviews/physical-limits.md L7 shows they are achievable.

Requirement IDs owned here (traced in `spec/performance-requirements.json`):
- **PWR-MODE-CEIL**: every primary mode stays within its ceiling (240 mA RF, 292 mA wired/USB).
- **PWR-DROP**: total drop from source to die is ≤ 117 mV, so the rail stays ≥ 3.15 V at a 3.267 V source.
- **PWR-THERM**: Tj stays within 22–32 °C across the stopped-to-max mode step.
- **PWR-DIG-WIRED**, **PWR-DIG-RF** and **PWR-HOST-RF**: as defined above.

## Common supply and return network

The retained native ring electrically joins all supply bonds and all ground
bonds into their respective common nets. Use one external supply source.
Named RF/PLL/HOST supply sites are allocation labels, not isolated feeds.
Local isolation must be an explicit realizable circuit with dropout, current,
stability, area and return-path accounting.

The selected common-ring model puts every chip load behind package impedance
and assigns 1 nF to the raw die supply. `architecture_fast/power_distribution.py`
resolves it from `blocks.power.parameters.local_distribution`. Its DC, AC and
retained-state transient agreement with SPICE validates equations only.
Package R/L, capacitor ESR/ESL, host spectra and currents remain assumptions.
An ideal independent ground or board-side placement of chip switching current
cannot qualify the common bonded topology.

Use the actual loaded DC rail in signal-quality/headroom calculations.
No capacitor can supply sustained load current. External SMD decoupling and
filtering are allowed, but package inductance still separates them from local
switching nodes. The provisional 0.25 nH shared-return target is not a measured
bond/package bound. Geometry, loop and coupling qualification remain open.

## Timing and signal-quality allocations for the selected blocks

Clock noise must include source, differential input conditioning, distribution,
quadrature, supply-induced delay and aperture error under one environment.
The selected aggregate supply-delay requirement is 0.0025 ps/mV; its sign,
frequency response and physical implementation remain unqualified. Common-mode
rejection does not remove individual pin excursions or mismatch-generated
differential noise.

Budget blocker-induced reciprocal mixing and supply modulation of both gain
and phase. A clean external oscillator does not eliminate receiver AM noise.
Use full spectra and correlations; adding separate peak magnitudes or RMS
figures without their phase/bandwidth assumptions is not a prediction.
External preselection must preserve wanted bandwidth and account for insertion
loss; an adjacent blocker cannot be assumed removable by an arbitrary filter.

Whole-domain series resistance plus small on-chip reservoirs is not a selected
isolation solution. Any proposed filter must meet attenuation and DC headroom
simultaneously, including common returns. Small local RC branches, external
networks and active regulation have different costs and must be evaluated at
the actual load and frequency.

## Enabled analog inventory and turnaround decision

Keep warm RF clocks/bias and the required RX/TX analog paths charged to both RF
directions. Mute suppresses output; it does not automatically remove standing
current. Parking bias is allowed only with an explicit longer readiness path.
RF/wired exclusivity does not eliminate host activity or simultaneous wired RX/TX.

A complete transition retains supply, filter, reference and converter state
through RX drain, DAC prefill, unmute, TX mute and RX recovery. Do not restart
from a quiet initial condition at every phase. Mute begins at the actual stop
or consumption event; an ideal fault cut remains a declared adverse assumption.
Ready requires valid timing and settled analog conditions.

For held-current perturbations, preserve passive-network modes and algebraic
feedthrough across continuation boundaries. Replace a forecast tail when new
activity arrives; do not add inherited state twice. Reject overlapping windows
or changed network parameters without an explicit state mapping. Charge
conservation alone does not establish adequate temporal resolution.

## Closed-loop converter and reference-load requirements

Acquisition R/C, SAR decisions, reset and reference recharge share the same
clock and supply state. Model signed high/low reservoir charge, switch/body
exchange and finite source/sink impedance. A grounded capacitor is not a
substitute for the switching-reference network.

The selected allocation is 3 ns acquisition, 20 ns conversion, 2 ns reset and
0.2 ns guard. Effective accuracy depends on amplitude, input common mode,
reference settling, noise, distortion, kickback and rare comparator decisions.
Ten-bit words do not establish ten effective bits. Positive finite-tone timing
margins do not qualify continuous uncertainty or a physical comparator.

## Host switching and wired electrical requirements

Host GPIO switching current, external pad charging and internal cell energy
are separate contributions. Use matched load/slew/drive settings when deriving
current and timing from Liberty; its internal-energy number is not the external
capacitor's charging energy. Apply the actual host spectrum to the common
supply and return paths. Assigned custom-driver savings require implementation.

USB acceptance includes HS driven voltage and quiet-pin disturbance, FS/LS
levels, termination/pull handoff and bidirectional response timing. The recorded
feed probe exceeds its 20 mV quiet guard. A lower average host rate does not
by itself establish safe return noise or electrical turnaround.

Wired equalization and clock recovery require useful eye margin and continuous
qualification under traffic and timing variation, not just zero errors in a
short sequence. Include termination currents supplied by external peers in
returns and die dissipation without counting them as internal supply current.
TMDS uses independently powered pull-ups and needs per-chip plus multi-chip
current, skew and ground accounting. External SDI drivers/equalizers and USB
VBUS power are board obligations.

## Storage placement policy

Keep packets, capture history, waveform storage and calibration computation on
the FPGA. On-chip storage serves bounded clock crossings, converter/serializer
service and short interruptions. `resource_policy.memory_bits` itemizes the
state within the 8192-bit cap and 0.85 mm² memory allocation. A smaller queue
requires an explicit service/occupancy proof and underrun/overflow behavior;
external storage cannot recover a missed sample or deadline.

## Acceptance and reproduction

Use one configuration for loading, source impedance, supply/return network,
clock sensitivity, converters and host switching. Evaluate local DC headroom,
transient current, noise and device-terminal stress in addition to averages.
Disabled branches retain loading and can remain exposed with local power off.

`verification/check_contract.py` checks planning invariants, not physical fit.
`verification/selected_revision_check.py --owner-current-gate` checks selected
mode accounting. The [model guide](../system_model/architecture_fast/README.md)
identifies joined payload and continuation checks. The [current issue register](risk-priorities.md#open-issue-register)
owns failures and missing proofs; exact configurations and fingerprints remain
in the evidence reports. Re-run affected cases after a design change.
