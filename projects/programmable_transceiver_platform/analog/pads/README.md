# Shared IO-pad foundation and implementation status

The design uses one reusable protection/bond foundation with functional
attachments. Circuits and partial connected layouts exist for wired TX,
wired RX/USB, differential reference, RF RX and RF TX. **No family is qualified
for production.** Normal-signal protection release, stress coordination,
local safe controls and real RF/reference cores remain unfinished.

## Authoritative artifacts

`spec/analog-architecture.json` and `spec/contract.json` own requirements and
sites. `spec/schematic-implementation.json:io_pad_first_pass` owns sizing and
implementation acceptance. `design.build_integration_candidate()` resolves
selected devices; budgets must not be copied into independent bench defaults.

`generated/coverage.json` indexes canonical netlists, GDS, extraction, state
windows, source freshness and electrical findings. A named window is coverage,
not acceptance. `generated/selected-recipe-audit.json` compares selected
buffer/interlock device graphs with their physical extractions. A circuit
change requires affected evidence to be regenerated, not its hashes relabeled.

| Family | Implemented boundary | Principal reports in `generated/` |
| --- | --- | --- |
| Wired TX | 366-device protected pad, steering/TMDS, detection, terminations, extracted buffer and interlock | `wired-transmit-screen.json`, `wired-transmit-integration.json` |
| Wired RX/USB | 446-device protected network, discharge, divider/bypass, terminations, HS/FS drive and pulls | `wired-receive-usb-screen.json`, `wired-receive-usb-loading.json` |
| Differential reference | 175-device protection/bias network; receiver remains behavioral | `reference-clock-screen.json` |
| RF RX | 159-device protection network, steering diodes, isolated clamp rail, MIMs and bleed; LNA remains behavioral | `rf-receive-screen.json` |
| RF TX | Connected protection network; supply/current/headroom-limited behavioral driver | `rf-transmit-screen.json` |

Each family has extracted-capacitance SPICE, GDS, layout/extraction reports and
GDS round-trip checks. Do not add a budget-sized ideal capacitor on top of
extracted capacitance. RF/reference attached-core loading is an assumption,
not a transistor-level receiver or driver.

## Packaging and supply topology

Retain all provider bond positions and eighteen fixed power/ground sites.
The selected assembly is `generated/packaging-assembly.gds`: 3932 × 5122 µm,
74 golden-mask openings, native seal ring and provider ID placeholders.
The pinned board exposes 37 assigned signals through its connector mapping.
`packaging_audit.py` owns the pinned board/template identities and geometric
checks; passing these checks is not package electrical qualification.

The proposed landing points lie within the board copper with a 100 µm assumed
edge inset. Projected spans are 1.797–2.665 mm, maximum angle 43.994°, with no
proper projected crossings. Actual die thickness, loop profile, landing
tolerances and selected-run assembly rules remain unverified. Wire length and
inductance must not be inferred from projection alone.

`generated/retained-ring-connectivity.json` identifies one common supply net
and one common ground net across the retained ring. **Use one common external
supply source.** CORE/HOST/WIRE/RF/PLL site labels do not permit independent
external feeds. All on-chip loads, including host switching, sit behind package
impedance. Any local filtering/isolation requires an implemented branch.

`system_model/architecture_fast/power_distribution.py` owns the corresponding
retained-state RLC model. DC/AC/transient agreement with SPICE verifies its
mathematics, not physical impedances or noise. The package/damping resistance,
allocated 1 nF, ESR/ESL and current laws remain assumptions.

## Reusable foundation and attachment decisions

`circuits.py:foundation_devices` centralizes the local protection recipe used
by every family; `attachment` separates that replaceable foundation from all
functional devices. The existing isolated-rail primary macro and
provider bond geometry are the common physical foundation. Safe-state policy is
shared, but its physical supervisors and final disable circuits remain unfinished.
The five names describe use sites, not a requirement for five distinct cell designs.

`pad_composition.py` composes exactly one extracted primary macro with complete
functional attachments. It compares separate wired cells, a simple wired union,
a wired candidate sharing the RX termination bank, lean RF/reference inputs,
and a universal candidate. Every disabled functional branch remains attached.
The shared-bank candidate retains the TX VCM discharge path and independently
namespaced controls; only the explicitly replaced termination bank is removed.
A shared cell design would still need separate physical instances wherever
simultaneous independent lanes are required.

The current comparison is in `generated/pad-composition-comparison.json`:

| Composition | Disabled / RX-bypass loading at 1 GHz, worst leg | Decision |
| --- | --- | --- |
| Separate wired TX / RX-USB | 1.802 / 1.155 pF disabled; RX bypass 1.416 pF | Keep specialized selected attachments |
| Wired union | 2.655 / 2.917 pF | Do not select; bypass exceeds 2.7 pF allocation |
| Wired shared termination | 2.478 / 2.740 pF | Co-design experiment; still exceeds allocation before new routing |
| Lean RF receive + reference | 0.504 pF disabled | Promising shared input structure; retain lean attachments |
| Universal populated attachments | 2.958 / 3.220 pF | Do not select; exceeds RF 1 pF and wired 2.7 pF allocations |

These numbers are **comparison-model values**, not replacements for the
canonical extracted layouts. The primary macro includes extracted capacitance;
functional attachments include device junction geometry but not their new
routing, package or shared returns. RF and clock cores remain the shared assumed
capacitive loads, and the wired receiver uses its shared output-load allocation.
The universal candidate contains all currently implemented attachments, not
invented complete RF transistor cores. Its present failure does not prove that
all possible co-designed universal pads are impossible.

The screen also measures linear source-to-pad transfer from the same 50 ohm
differential source and DC peer/supply/bias currents with supplies on and off.
Sharing the RX termination bank changes the incremental common-mode resistance
near 1.65 V from about 46.65 to 56.49 ohms per leg in this schematic fixture;
loading reduction alone does not preserve wired capability. The populated
reference bias returns about 63 microamps to its ideal VCM source at a 3.3 V
peer input with the chip off. That source's physical ability to absorb charge
remains unproven. Neither a low VDD backfeed number nor a small AC loss proves
safe shutdown, low receiver noise, low distortion or a compliant data eye.

**Selection rule:** share the foundation now; merge functional attachments only
when the same populated candidate meets loading, impedance/signal quality and
retained-network off-state requirements. Do not erase disabled devices, waive
budgets, or use a passing simplified input load to claim missing cores complete.
No pin-count or package change follows from this code consolidation.

### Upstream reuse boundary

The comparison against [OCD I/O revision
6e0e354](https://github.com/RTimothyEdwards/gf180mcu_ocd_io/tree/6e0e354a78793339a4a004a6d9c08990d0eee3e4)
found that its `netlist/schematic/gf180mcu_ocd_io__dvdd.spice` has the same
seven clamp MOS connections, W/L, finger counts and multiplicities as our
`generated/protection-clamp/clamp-reference.spice`, after mapping `TIMING` to
`n8`. This was checked by parsing both netlists. Our passive implementation and
isolated-rail use differ; this is not full LVS or electrical equivalence.
Consequently, importing this upstream clamp does not introduce a new transistor
trigger topology that resolves the recorded release/stress failures.

The upstream `docs/analog.rst` explicitly requires secondary protection beside
attached input gates. Its suggested resistor/diode network is a starting point,
not a qualified GHz solution. Evaluate the actual receiver input capacitance,
noise, bandwidth and transient terminal stress together before selecting it.
The split-voltage I/O library also does not create separate bonded rails in our
already-connected retained ring.

For missing startup/bias/control circuits, use the pinned candidates and
acceptance boundaries in the [implementation reuse decisions](../../spec/risk-priorities.md#open-gf180-implementation-reuse-decisions).
A POR delay alone cannot implement fast brownout disable; a single high-side
PMOS switch cannot guarantee reverse-current blocking. Neither should be used
to mark the existing safe-state gaps closed.

## Current protection and shutdown decision

Keep the isolated primary protection rail and coordinate secondary protection
with the first exposed core devices. Do not send primary discharge into a
functional supply or assume AC coupling can replace DC-coupled pad protection.
No tested protection/control candidate meets all current acceptance gates.

| Gap | Evidence and required decision |
| --- | --- |
| Normal-signal release | The retained RX/USB pad sits near 1.55 V during brownout with an unloaded 3 V peer network; about 1.06 mA enters the isolated protection rail. Fix this functional loading failure without sacrificing protection. |
| Transient protection | Released-state 100 mA/2 ns diagnostic candidates still exceed the conservative gate screens. A clamp behind exposed USB isolation/bypass devices is insufficient. Observe all relevant Vgs/Vgd/Vds and discharge paths. |
| Autonomous disable | The junction-floor supervisor candidate trips around 2.625–2.7 V across fifteen corners but retains low-rail/overlap problems. Output discharge alone can exceed its 0.40 mA monitor allocation. It is not selected safety control. |
| Powered host | An independently powered host produces about 81.6 mA in the retained off-state fixture. External isolation or enforced board sequencing is required until qualified local isolation exists. |
| Actual control implementation | Use local-rail qualification, reset-dominant disable, passive default-off paths and break-before-make sequencing. Prescribed controls and ideal readiness are not physical supervisors. |

`generated/rail-supervisor-screen.json`, `rail_supervisor.py` and the terminal
exposure reports retain exact diagnostic conditions. The 3.63 V/6.0 V gate
screens are conservative [PDK DC reliability limits](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html),
not nanosecond damage thresholds. Unobserved terminals remain unknown.
The **2 kV HBM / 500 V CDM** project targets are not inherited ratings; pulse
simulation and board protection do not establish bare-chip ESD qualification.

## Electrical and physical integration gaps

| Area | Current state and acceptance boundary |
| --- | --- |
| Wired TX loading/impedance | Selected current trunks are 8 µm. Recorded disabled loading is about 2.706/2.713 pF against 2.7 pF; active and detection cases also have misses. Geometry-derived bond-to-core resistance is asymmetric (about 8.34/11.67 Ω before vias/internal buses). Full distributed impedance and current capacity remain open. |
| Wired TX controls/current | Extracted buffer/interlock, sequencing RTL and retained pad are connected in fixtures. Bias/serializer translation and readiness remain partly idealized; branched-route feedback does not establish readiness closure. Canonical static currents miss intended settings. |
| Wired RX/USB | Back-to-back high-side devices, restoration and physical discharge exist. Brownout controls, off-state gate stress, loading and bidirectional termination/pull handoff still need connected acceptance. |
| RF/reference | Real LNA, RF output stage and differential clock receiver are missing at the pad boundary. Tone power margin is narrow; millisecond-scale reference bias startup is not a ready deadline. Include modulated quality, noise, clock slew/jitter and peer exposure. |
| Attached core area/routing | Buffer/interlock reservations and six steering connections are checked. Supply/return, bias, buffer/interlock and upstream-data hookups, full-core clearance and routed timing remain incomplete. |
| Assembly signoff | Local DRC/device graphs and bond-mask checks do not establish integrated DRC/LVS, density, antenna, assigned IDs, electromigration, package coupling or full-bank switching. |

Warm RF bias remains in current accounting even when payload direction changes.
External decoupling cannot supply average current or eliminate package impedance.
Keep every disabled branch and the actual peer network attached in every
startup, active, reset, brownout, off and reconfiguration case. TMDS needs its
independently powered pull-ups; a differential resistor fixture is insufficient.

## Extraction and assembly rules

`circuits.py` / `wired_receive.py` drive SPICE and layout. `extract_audit.py`
independently reads actual device/body connections from Magic extraction.
The installed stock converter has exhibited body-connectivity errors, so its
output alone is not the simulation authority. Preserve the independent
extracted graph and device dimensions.

`gds_markers.py` restores missing HRES export enclosures from physical poly
geometry, including DUALGATE for MV high-R poly. `gds_roundtrip.py` reimports
actual GDS and checks DRC plus device types, dimensions and connectivity.
`run_first_pass.py` refuses publication on a failed round-trip check.

Physical well area/perimeter supplies nonlinear well-junction models. Remove
only the corresponding linear well-area capacitance to avoid double counting;
retain fringe/routing capacitance. The array audit bounds numerical uncertainty
from the printed precision of exported capacitor values.

`rail_connectivity.py` distinguishes MIM top-plate contacts from ordinary VIA4:
inside CAPM (75/0), the contact reaches the top plate rather than shorting the
Metal4 bottom plate through the dielectric. Labels are probed on their actual
metal layers. No connection is inferred merely from matching net names.

Distributed resistance is not included in the capacitance extraction.
`wire_resistance.py`, `rf_route.py` and `protected_rf_route.py` provide explicitly
scoped geometry-derived resistance sensitivity models. Lumped capacitance
placement, omitted access/via resistance and uncertain package parameters remain
limitations; these are not distributed PEX or RF signoff.

The provider reference has 74 physical sites, a 211 µm pair pitch, and 18 fixed
power/ground sites. Preserve absolute bond openings and native supply sites.
The assembly substitutes five custom pairs, restores native rail modules and
checks transformed openings, actual metal overlap and local ground connectivity.
`generated/packaging-assembly.gds` is the selected geometric assembly;
`generated/custom-assembly-candidate.oas` is an intermediate build input.
Full-ring device LVS, integrated signoff, package returns, full-bank switching
and core clearance remain open.

## Reproduction

The exact image ID in `layout.py` is not available locally. Restore its build
recipe and PDK identity before fresh layout claims; see
[process inputs](../../../../processes/README.md). Do not substitute an unrelated
image silently.

Use the image pinned in `layout.py`, the contract-pinned provider template and
unchanged PDK models copied from that image. Use new output directories to avoid
merging old geometry or accepting stale waveforms. Large waveforms stay in
scratch; publish compact netlists, layouts, images and scoped reports.

The recorded corrected ngspice47 build is described by
`generated/simulator-build.json`. Its capacitor-multiplier parser and forward
sidewall-diode charge fixes are retained as patch files in this directory;
`diode_model_check.py` documents the solver regression. Do not silently replace
this simulator with another binary when reproducing its results.

From the repository root, with those prerequisites available:

```sh
python3 projects/programmable_transceiver_platform/analog/pads/design.py --output scratch/transceiver-pad-inputs.json
python3 -m unittest discover -s projects/programmable_transceiver_platform/analog/pads -p test_design.py
PATH="$PWD/scratch/pad-diode-fixed-tools:$PATH" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 projects/programmable_transceiver_platform/analog/pads/run_first_pass.py --output-dir scratch/pad-pass --pdk-model-dir scratch/transceiver-pad-pdk/ngspice --publish-dir projects/programmable_transceiver_platform/analog/pads/generated
python3 projects/programmable_transceiver_platform/analog/pads/assembly.py --template scratch/pad-provider-template --output-dir scratch/pad-assembly --generated projects/programmable_transceiver_platform/analog/pads/generated --publish-dir projects/programmable_transceiver_platform/analog/pads/generated
```

## Completion gates

Finish the coordinated protection/core contract, implement safe controls and
real pad-to-core circuits, integrate the common ring and package, then pass
representative electrical lifecycles. Production additionally requires extracted
signoff and silicon/reliability qualification. Keep numerical failures and
missing evidence explicit; test counts do not measure pad completeness.
