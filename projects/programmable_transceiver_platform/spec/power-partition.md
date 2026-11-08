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

| Configuration | Allocated current | Mode ceiling | Margin |
| --- | ---: | ---: | ---: |
| RF RX or TX, external clock | 224.09 mA | 240 mA | 15.91 mA |
| RF RX or TX, autonomous synthesis | 253.02 mA | 240 mA | −13.02 mA |
| Wired, base allocation | 244.82 mA | 292 mA | 47.18 mA |
| USB, base allocation | 231.25 mA | 292 mA | 60.75 mA |

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
