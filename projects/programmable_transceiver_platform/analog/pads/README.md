# Parametric IO-pad implementation

**First pass in progress.** One reusable pad foundation serves functional
attachments. The five current use-site families have generated circuits,
connected layouts, extracted capacitance and retained-network state screens.
Protection-to-core coordination and physical local safe-state control remain incomplete.
A completed transient or matching device graph is not a performance, reliability
or fabrication-readiness verdict.

## Packaging is the first implementation gate

The normative requirements are in `spec/contract.json:assembly_policy.packaging_gate`.
`packaging_audit.py` and `generated/packaging-audit.json` check a pinned provider
board and the actual partial routed assembly. Public sources were checked on
2026-10-18; future-run board delivery is not inferred from a repository design.

The [provider template](https://github.com/wafer-space/gf180mcu-project-template/blob/33e4b5ecc9faac82787fa7cb205f08377e27b912/README.md)
permits changing signal-pad types while retaining bond positions and power/ground
assignments. The pinned Run 2 board exposes the 74 die sites through 70 connector
contacts. All 37 assigned signals map to connector contacts and the eighteen
power/ground sites match. North and west template lists must be reversed when
walking counterclockwise around the die; the audit derives that order from
physical coordinates instead of concatenating the four configuration lists.
All die grounds join on the board. Distinct PCB supply labels do not prove
independent on-chip rails.

**The selected packaging assembly passes the pinned upstream size, pad-mask
and test-ID insertion checks.** `generated/packaging-assembly.gds` contains the
corrected native ring, the existing custom pads and attached core, real provider
ID macros and the actual PDK seal ring. Its bounds are (0,0)–(3932,5122), all 74
bond openings match the golden mask, and the four required ID cells occupy the
provider locations. The ID test used `TEST0000` only in a scratch output; the
selected artifact keeps the template placeholders for later provider assignment.

`assembly.py --placement-only` preserves fractional horizontal spacing in the
installed placer and regenerates filler rows, then performs placement/local
rail checks without the separate legacy electrical-estimation stage.
`packaging_assembly.py` replaces the retained ring and inserts real ID macros;
a polygon comparison checks that the core region is unchanged. The installed
PDK `sealring.py` adds the real seal structure. `packaging_audit.py` consumes the
aligned placement report and final layout inspection. This is the selected
assembly path; intermediate ring/core files remain build inputs, not alternate
production designs. Full-ring electrical continuity, integrated DRC/LVS, density,
antenna, final assigned ID and board/bond performance remain unverified.

The [published wire rules](https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs/blob/5cb466897372ac6c9df03142287858c1c8b1c9a7/run-1/wirebonding/README.md)
are run-specific evidence: no crossing; angle at most 45 degrees; actual length
below 3 mm and at least max(1 mm, twice die thickness); no mask in the bonding
area. The centred-die projection to Run 2 landing centres spans 2.197–2.991 mm,
with maximum projected angle 38.71 degrees. Actual landing locations within the
1 mm PCB pads, loop height and die thickness are not established. The upper
projection leaves almost no length allowance for a loop; choose and verify the
actual bond locations before treating this as buildable or assigning GHz
package performance. Pin-map agreement is not a bond-wire or RF signoff.

## Reusable foundation and attachment decisions

`circuits.py:foundation_devices` centralizes the local protection recipe used
by every family; `attachment` separates that replaceable foundation from all
functional devices. The refactor leaves the five existing generated schematic
graphs byte-for-byte unchanged. The existing isolated-rail primary macro and
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

## Authoritative artifacts

`design.py` resolves requirements and pad sites from
`spec/analog-architecture.json` and `spec/contract.json`. Preferred integration sizing is selected by
`spec/schematic-implementation.json:io_pad_first_pass.generation_parameters`
and consumed by `design.build_integration_candidate()`. Device primitives remain
in the circuit generators; electrical budgets must not be copied into a second
configuration. `generated/selected-recipe-audit.json` verifies the selected
buffer/interlock device graphs against their existing physical extractions. The buffer layout
generator now defaults to this shared selection and bounded internal routing;
explicit sizing arguments remain available for experiments. A default rebuild
passes local DRC and GDS graph checks and reproduces the selected core
extraction up to capacitor ordering.
Primary protection, core discharge and compensation are composed by their
layout generators; the recipe builder alone does not create a complete pad. Never add a budget-sized ideal capacitor on top of extracted
physical capacitance.

`generated/coverage.json` indexes each canonical extracted netlist, GDS, layout
report and state screen. Its `integrated_model_inventory` separately checks:

- Required state-window names resolved from the shared design, including brownout.
  All five families now name brownout. TX brownout was recovered by postprocessing
  its saved waveform; original simulation source hashes remain unchanged. A named
  window alone does not establish safe behavior.
- Published netlist bytes against the recorded simulation input.
- Source freshness.
- Exported-GDS device connectivity against that exact netlist.

The same coverage report's `electrical_findings` surfaces recorded RX loading
and RF TX tone-power misses separately from lifecycle coverage. It preserves
reference startup as an observation without inventing a ready deadline, and
keeps missing core-survival limits and physical safe controls unresolved for
every family. Read these findings together with source freshness and the
existing TX/RF power-budget sections; they are not whole-family acceptance.

Generator edits can stale the recorded source hashes; inspect the current
inventory rather than treating older successful runs as a fresh rebuild. Reset is a prescribed
control condition; RX/USB uses a behavioral control guard, not an implemented
supervisor. Alternate protection,
matching and fault-injection experiments do not replace canonical artifacts.

| Canonical family | Circuit and attached boundary | Principal evidence |
| --- | --- | --- |
| Wired TX | 366-device protected pad; full main/postcursor/TMDS, detection and termination network; connected extracted buffer/interlock | `wired-transmit-screen.json`, `-integration.json`, `-lifecycle.spice` |
| Wired RX/USB | 446-device protected network with physical core discharge; divider/bypass, terminations, HS/FS drive and pulls | `wired-receive-usb-screen.json`, `-loading.json` |
| Differential reference | 175-device primary protection and bias network; receiver remains an explicit `refinput` boundary | `reference-clock-screen.json`, `-terminated-screen.json` |
| RF RX | Connected 159-device protection network: steering diodes, isolated-rail clamp, MIMs and physical bleed; finite LNA boundary | `rf-receive-screen.json`, `-route-resistance.json` |
| RF TX | Same connected protection network; supply-connected, current/headroom-limited driver boundary | `rf-transmit-screen.json`, `-route-resistance.json` |

Report names above are relative to `generated/`. Each family also has a
`-extracted-c.spice`, `.gds`, `.png`, `-layout.json`, `-extraction.json` and
`-gds-roundtrip.json`. The RF/reference core boundaries are not transistor-level
LNA, driver or clock-receiver implementations.

## Circuit decisions and remaining controls

Every inactive branch remains physically attached. Reconfiguration changes
controls, not the circuit or external storage network.

Wired TX shares output cascodes across steering branches. The canonical
retained-state fixture connects the extracted protected pad, compensated
common-mode buffer and mode interlock, driven by actual sequencing RTL.
It retains one external differential load through active, reset, disabled,
unpowered and reconfiguration states. Source-termination readiness is a finite
behavioral detector; other modes assume readiness. Serializer and bias
translations remain ideal. See the current wired-TX integration section for
settling evidence and physical implementation gaps.

Wired RX/USB uses back-to-back high-side PMOS devices with floating wells,
passive gate restoration and supply-gated pull-down paths. FS-low requests are
qualified against termination common mode; this is not complete mode exclusion.
High-side gate controls use 6 V NMOS devices because a retained request can
outlive supply collapse. TX detection/termination enable inverters likewise use
6 V devices. The high-speed steering path is unchanged.

`receive-control-screen.json` demonstrates why supply-qualified disable is
needed: stale requests cause several-mA brownout backfeed. Prescribed disable
removes positive return current in that sampled window, but does not eliminate
collapse displacement charge. `receive-*-terminal-exposure.json` and
`wired-transmit*-terminal-exposure.json` inventory internal MOS terminal
voltages. These measurements do not establish oxide lifetime or safe sequencing.

`generated/receive-local-qualification-screen.json` connects the extracted
RX/USB pad and shared reduced PDN to a behavioral local-rail validity detector
and sticky fault. It uses the shared monitor's 2.5–3.6 V window. With assumed
1 ns filter/capture time constants, high-side enables turn off during brownout
and remain off after supply recovery. The 3 µs run does not satisfy the shared
20 µs requalification guard and never rearms. It starts already qualified;
cold start, explicit rearm, sensor accuracy, latency and physical control power
are not demonstrated. This establishes a useful integration boundary, not
supervisor circuitry or safe independent power sequencing.

`generated/receive-discharge-screen.json` separates receiver isolation from
stored-charge removal. With a powered peer and local supply off, a stale bypass
request leaves RX nodes near 2.3 V. Qualifying the request turns the switch off,
but the modeled high-impedance core retains about 1.8 V. A 100 kΩ core-side
bleed hypothesis discharges that node in the sampled window. That fixture's
approximately 3 V powered peer is adverse for serial bypass; its active DC
shift is not a valid serial-performance verdict.

`generated/receive-bleed-tradeoff-screen.json` separately checks bypass at
1.65 V common mode with the shared 50 fF/leg core load. At 1.25 GHz, a
330 kΩ core-side bleed adds approximately 0.022 dB pad-to-core loss relative
to the 1 GΩ fixture and shifts DC by about 1.09 mV. A 1 MΩ bleed adds
approximately 0.007 dB and shifts DC by 0.36 mV. In the retained powered-peer
transient, their sampled off-state receiver maxima are respectively about
0.84 µV and 2.84 mV. These support a discharge path as a plausible solution;
they do not establish an acceptable core stress threshold. Specify both switch
isolation and attached-core discharge/tolerance. The first-pass attached-core
model now uses the physical approximately 329 kΩ candidate below; noise,
corners, common-mode range, discharge deadlines and transient stress remain
unqualified.

A physical discharge candidate is retained in `generated/receiver-core-bleed/`.
The existing parametric high-R poly generator, with four 80 µm fingers,
produces about 329 kΩ in an 8.54 × 83.27 µm envelope per leg. Its exported
GDS passes scoped DRC and preserves the extracted resistor. Connecting two
extracted instances to the RX model gives approximately 0.070 dB additional
pad-to-core loss at 1.25 GHz relative to the near-open baseline (rather than
0.022 dB for ideal 330 kΩ), and an off-window maximum of about 0.89 µV.
`receive_core_layout.py` assembles these primitives into the connected
`generated/receiver-core-discharge/` macro with RX_P/RX_N and a common return.
Exported-GDS DRC passes; extraction checks both resistor dimensions and body
connections. The macro occupies approximately 1,964 µm² including local return
routes. `receive_core.py` uses this exact extracted macro in canonical RX/USB
lifecycle, branch and loading fixtures, in addition to shared core capacitance.
The canonical RX GDS now places and connects this macro; extracted connecting
capacitance is included. Distributed route resistance remains absent. In the short
40–47 ns unpowered window, receiver voltage is still approximately 1.1–1.3 V;
this is discharge over time, not immediate supply-bounded protection.

`receive_controls.py` generates a protocol-independent behavioral control
boundary using the shared supply-valid window. It rejects divider/bypass,
differential/shunt, same-leg FS high/low, and incompatible HS/FS drive requests;
valid HS drive with shunt termination and FS drive with passive pulls remain
available. A conflict disables all generated switch enables. Reset, local
supply validity and external qualification also gate those enables.
`receive-control-exclusion-screen.json` verifies all 16,384 Boolean request
combinations and connects the boundary to the exact extracted RX/USB pad with
retained board loading, injected conflict and reset. The standard `receive_screen.py` lifecycle now connects this guard, exercises
an explicit reset input and checks an injected same-leg high/low conflict.
Raw DC branch fixtures and the stale-enable transient deliberately bypass the
guard to characterize pad devices and faults. The guard has no transistor
layout yet and does not implement sticky fault storage, comparator accuracy,
asynchronous hazard control or break-before-make timing. Lifecycle QUALIFIED
remains prescribed rather than a proven supervisor output.

`receive_integrated.py` rebuilds the canonical protected RX/USB family through
`run_first_pass.py --families wired_receive_usb`. It consumes the shared FS
sizing (14 µm PMOS fingers, 2 × 3.5 µm series resistors) and primary placement,
generates the base, attaches the physical discharge macro and primary protection,
and checks the full 446-device layout/model. Local DRC/device correspondence,
retained-state tests and joint provider-placement checks pass. Numerical anchors
on capacitor-only metal are declared and DC initialization fallback is rejected.
The complete allocated union is 283,003 µm² within the 290,000 µm² wirepad
reservation, including protection and discharge geometry.

Canonical `wired-receive-usb-integration.json`, `-assembly-screen.json`,
`-gds-roundtrip.json`, `-screen.json` and `-loading.json` record this implementation.
Serial-bypass loading is approximately 2.764/2.637 pF per leg at 1 GHz: one leg
still exceeds the shared 2.7 pF allocation. FS-high output resistance remains
approximately 45 Ω. `receive_core.py` detects embedded discharge resistors and
adds no duplicate instances. Publication does not establish safe core stress,
physical control sequencing, trim/slew behavior, whole-ring device LVS or ESD
qualification. Older RX family revisions live in Git history.

`termination_buffer.py`, `termination_buffer_layout.py` and
`termination_compensation_layout.py` now provide a connected buffer candidate
with 205 MOS devices, one poly resistor and one MIM capacitor. Its current
physical model, GDS, inspected render and retained-network deck are in
`generated/termination-buffer-candidate/compensated/`. Local DRC, the intended
207-device graph, physical export audit and exported-GDS checks pass. The
`gated-core/` directory is its transistor-core input component. Shared
load-current trunks are 8 µm wide; individual accesses and total current
capacity remain unqualified. The physical compensation resistor measures
about 19.1 Ω nominally, rather than assuming the earlier ideal 30 Ω probe;
the approximately 3 pF MIM and connecting capacitance are extracted. Bias
passives, pad-to-buffer routing, full-chip placement and area funding remain
open. No duplicate ideal compensation is added to this physical model.

`termination_buffer_connected.py` uses the same selected external load in
every lifecycle state. Its differential load comes from the shared architecture;
the powered-pullup alternative remains an adverse serial-load probe. With the
physical compensation and differential load, the completed run records about
1.676–1.758 V in the sampled active-main window and 1.697–1.711 V in main/post,
against a nominal 1.65 V target. Reconfiguration reaches about 1.915 V.
Sampled reset draw is 1.95 mA with the lower-impedance divider hypothesis;
sampled unpowered supply return reaches 151 µA. These include bias/passive
and transient effects, not a measured static leakage specification. Reference
comparison is not a regulation requirement while the buffer is disabled.

The candidate is not adopted. Resetting the gain node low improves charging
relative to high reset, but loaded startup/settling remains unresolved.
`precharge-screen.json` extends only PWL events at/after 60 ns by 40 ns,
retaining clocks, edge slopes, devices and external loading. The resulting
42 ns precharge reaches within 0.63 mV of reference immediately before
termination connects, but turn-on then produces about 404 mV sampled main
reference error. Longer precharge alone is not a solution; loaded response
must be addressed separately. The
prescribed 2 ns precharge is a fixture assumption, not a demonstrated startup
deadline or buffer-ready guarantee. Resolve startup/readiness, loaded loop
response, current limiting and terminal stress before replacing the canonical
behavioral boundary. Enable qualification still uses behavioral TX_VALID;
autonomous reset/brownout sensing is not implemented. Earlier standalone and
ungated reports are scoped comparison evidence, not additional normative
buffer implementations.

Still required: implemented reset/brownout qualification, conflicting-control
exclusion, trim/slew controls, actual termination-buffer circuitry, and attached
core tolerance to retained charge and excursions outside its supply rails.

The separate `transmit_source_headroom.py` DC check uses an ideal TERM_VCM
to distinguish pad compliance from buffer response. With the same extracted
TX/protection network and shared 100 Ω differential load, the 8 mA main
setting draws about 8.05 mA incremental drive at 1.65 V common-mode source.
The 24 mA aligned maximum main/post setting draws only 20.07 mA; no sampled
source voltage from 1.2 to 2.8 V reaches 95% of that target. These currents
subtract the same enabled-termination, driver-off bias load. The report is
`generated/wired-primary-protection/source-headroom-screen.json`. External
pullup calibration does not establish this internal-termination combination.
This is a bias-transfer/compliance result, not proof that the setting is
unreachable. `transmit_loaded_calibration.py` adds zero-volt tail-current
sensors and calibrates both branches together under the actual internal load.
The original devices reach approximately 15.98/7.99 mA, but MAIN requires a
3.175 V bias on a 3.3 V supply. The preferred candidate doubles MAIN/POST tail
fingers while retaining TMDS tails, pad cascodes and termination topology.

`generated/wired-primary-protection/double-tails/` holds that connected
366-device layout and its exact tested model. DRC, device LVS and independent
physical graph checks pass; its render has been inspected. Loaded calibration
reaches 16.07/7.99 mA at MAIN/POST biases 1.680/1.125 V. Nominal 1 GHz odd-mode
loading is about 2.688 pF/leg disabled and 2.675 pF/leg in main mode, against
2.7 pF; detection remains over budget at about 3.80 pF. The allocated union is
240,640 µm² against the unfunded 180,000 µm² allowance. This candidate is not
canonical: the integrated 16+8 mA buffer lifecycle completes but still exhibits
roughly 1.02–1.11 V common mode in sampled active windows. Buffer capability,
loading margin, provider placement, area funding and protection remain open.
The PMOS pad-complement and fourfold-tail probes are not selected: the former
requires raised common-mode voltage and the latter exceeds the loading budget.

Repeated extraction reordered capacitor records without changing the circuit.
`extraction_order_check.py` requires every non-capacitor line and every
capacitor endpoint/value record to agree; injected value/device changes are
rejected. Publication retains the exact electrically tested netlist bytes and
links them to the new physical extraction through this check and the independent
device/well audit. It does not silently refresh an old electrical result.
Existing external-source termination remains a separate architectural path,
still requiring its own loaded checks.

## Protection architecture

The selected wired TX uses an isolated protection rail attached to the full
four-tail branch network. `wired_protection_layout.py` generates its connections
and checks the streamed device graph; `transmit_integrated.py` rebuilds and
publishes the 366-device layout and connected lifecycle model. The pad occupies
240,640 µm² within its 250,000 µm² reservation and preserves the provider bond
openings. Buffer/interlock placement is not included in that reservation.

Protection is a first-pass topology, not a survival claim. Earlier diagnostic
pulse experiments exposed excessive core-facing voltage; neither scoped DRC/LVS
nor the new nominal lifecycle closes clamp trigger, core-stress or discharge
current capacity. A feed-forward capacitor experiment is not part of the
selected physical layout. The current no-injection power-down trace also reaches
approximately −0.742 V at the pad. Resolve the protection/core voltage contract
before interpreting any of these excursions as acceptable.

The connected RF replacement is in `generated/protected-rf-pair/`. It contains:

- Parametric lower/upper steering junctions with explicit substrate connections.
- An isolated protection rail, avoiding direct steering into functional VDD.
- A native-clamp-derived transistor network with physical MIM timing/storage
  capacitors and a physical approximately 10 MΩ bleed resistor.
- Actual bond corridors, rail/return routes and 3×3 via arrays at the macro's
  rail/return ports.

The generators are `protection_layout.py`, `protection_array.py`,
`clamp_layout.py`, `protection_bleed.py`, `protection_network.py` and
`protection_pad.py`. The same diode primitives serve both RF directions.
Native geometry reuse does not transfer an ESD rating to this design.

The connected RF design is now canonical, with 24 µm bond corridors and
12 µm transverse/outer routes. `rf_integrated.py` rebuilds layout, audits, routed
RX/TX lifecycles, maximum-gain TX and pulse checks; `rf_publish.py` verifies and
publishes them after provider assembly. `run_first_pass.py` preserves this
selection on rebuild. Canonical models use their `*-route-resistance.json`
overlays; the generic `wire-resistance.json` now points to those connected RF reports
and no longer applies four-device route formulas to canonical RF. The
`rf-pad-base/` directory retains the small-pad regression-test component only. `rf-integrated-screen.json` and
`rf-assembly-screen.json` identify the adopted build. Adoption does not resolve
the measured core stress or narrow TX margin. The supporting experiments in
`generated/wide-route-rf-candidate/` are not another normative family model.
`protected_assembly.py` reproducibly stages all current families with this RF
candidate and runs placement plus local rail connectivity checks;
`assembly-screen.json` records the combined result. Its measured allocation is approximately 123,842 µm² per pair. The shared
architecture now reserves 130,000 µm² per RF pair, transferring 140,000 µm²
from unused reserve without changing the total die budget. The existing
clamp/array/bleed macro envelopes alone occupy approximately 62,415 µm²;
placement cleanup alone cannot meet the former 60,000 µm² allowance.
`area-decision.json` records this decision. All five canonical families have been rebuilt against the revised budget.
The connected RF replacement has also been regenerated: `generation-screen.json`
records completed RF RX/TX lifecycle screens, area fit and the mandatory device
and well-capacitance audits. Routed-loss and pulse screens are also refreshed against this candidate;
provider placement and local native-rail checks have also been refreshed using
all current canonical families plus the connected RF candidate; electrical parameters have not changed. The existing `protected-rf-pair/` is evidence for the earlier
narrow-route implementation, not a second normative design.

| Current evidence | What it establishes / remaining limitation |
| --- | --- |
| `independent-device-audit.json` | All 159 MOS/resistor/steering-diode/MIM records match the physical extractor. Checks include bodies, diode polarity/area/perimeter and ordered MIM terminals/dimensions. Injected polarity, diode-area, MIM-terminal and MIM-size faults are detected. The explicit well replacement agrees with the eight isolated array wells (569.45 µm², 470.72 µm); 68.33 fF of linear area capacitance is removed and other extracted capacitors are unchanged. Well-polarity, area and double-counting faults are detected. Nonlinear-model accuracy and protection survival remain unqualified. |
| `screen-summary.json` | Scoped DRC and device checks; Approximately −1.34 dBm at nominal gain and +0.16 dBm at maximum modeled gain with high metal resistance. Small margin; no modulation or complete PVT acceptance. |
| `placement-audit.json`, `native-rail-screen.json` | Provider bond openings preserved with the current integrated RX and RF layouts; no unexpected metal overlaps; local native-ground connectivity and protection isolation pass. Earlier fault-injection evidence remains separate. Whole-ring hookup, core placement and integrated signoff remain open. |
| `pulse-screen.json` | With the same routed network, unpowered ±100 mA diagnostic pulses reach about +4.54/−1.00 V core-to-local-return; positive local-return movement reaches 0.261 V. Primary protection does not establish a supply-bounded core interface. |
| `trigger-diagnostic.json`, `autonomous-trigger-screen.json` | Ideal timely gate assist demonstrates trigger sensitivity. Direct RC-node PMOS assist provides negligible benefit and is rejected. Neither establishes safe core protection. |
| `feedforward-mim/` | A generated, round-trip-checked MIM adds about 5,256 µm² before integration routing. Its extracted model reduces the positive core peak to 3.952 V and retains +0.158 dBm tone output. It is not placed in the pad or adopted. |
| `cold-start-screen.json`, `recovery-envelope.json`, `guard-burst-screen.json`, `startup-reproduction.json` | Early cold-start loading recovers within the shared 20 µs guard in the tested quiet-bias fixture. A following RF burst reaches about +0.225 dBm with feed-forward. Silent peer/PWL source differ from continuous-tone tests; other ramps, active peers and autonomous readiness remain open. |

All table paths are relative to `generated/wide-route-rf-candidate/`. Source
hashes and assumptions belong to each report; current helper code does not
retroactively validate historical experiments. Diagnostic pulses are not
standardized ESD waveforms. Thermal behavior, contact/current capacity, avalanche
and actual core survival are unqualified.

Do not spend further first-pass effort on small coupling-capacitor or diode-width
sweeps: existing `rf-external-match-screen.json`, `rf-load-match-screen.json` and
`protection-junction-width-screen.json` do not close protection coordination.
The useful next decision is the complete protection-to-core circuit and its
voltage contract, applied across the required pad families.

The buffer source-capacity diagnostic in
`generated/termination-buffer-candidate/source-capacity-diagnostic/` separates
source-stage and output-isolation limits. At nominal DC over the shared ±24 mA
load range, the original extracted buffer has 199 mV maximum reference error;
an ideal isolation bypass still leaves 177 mV. Doubling the source fingers alone
leaves 68 mV, while doubling them and adding a floating-well PMOS isolation
complement reduces error to 5.4 mV. The connected 249-device hypothesis still drops to approximately 1.12–1.32 V
in sampled high-drive windows and reaches 2.34 V during reconfiguration, despite
settling near 1.65 V before load connection. Do not adopt it from DC results:
feedback dynamics and loaded settling remain unresolved. The added-device
routing/well parasitics, power-off safety and area are also unverified.
`lifecycle.json` and `lifecycle.spice` retain this counterexample with the same
external differential load through all states.

The source-capacity candidate now also has a connected 249-device compensated
layout in `source-capacity-diagnostic/compensated/` under the buffer candidate
directory. Local DRC, intended/exported graphs and GDS round-trip checks pass;
the rendered geometry was inspected. Its extracted standalone load-step test
settles within 5.4 mV at ±24 mA but swings approximately 0.71–3.80 V during
load transitions. Sustained current capability is plausible at this nominal
point; transient response and terminal safety are not closed.

`source-capacity-diagnostic/compensated/transient-tradeoff.json` compares
compensation and current-ramp hypotheses on this extracted base. Reducing MIM
area to one tenth leaves substantial late oscillation; quadrupling it reduces
output extrema to approximately 0.93–3.19 V but does not close the error. A 10 ns
load-current ramp with original compensation gives approximately 1.23–3.03 V.
Neither is adopted. The ±24 mA reversal is an adverse standalone source/sink
test, not ordinary TX operation; retained-pad lifecycle results remain decisive.
The ramp controls load demand, not serial data-edge speed.

The canonical reference-clock model now contains the selected 175-device
primary-protection and bias network. `reference_integrated.py` regenerates its
base and combined layout from shared parameters, reruns both retained-network
reference fixtures, and checks joint provider placement before publication.
`run_first_pass.py --families reference_clock` uses this path. Canonical artifacts
are `generated/reference-clock-*`; earlier candidate evidence is superseded.
Odd-mode loading is approximately 0.572 pF/leg at 1 GHz and the allocated union
is 127,170 µm² within the 130,000 µm² reservation. Local DRC, independent device
checks, bond openings, metal-overlap and local-rail checks pass. The former 16 mV result came from a failed DC solve followed by ngspice
transient initialization, not demonstrated DC bias failure. A declared numerical
anchor on capacitor-only floating metal restores the DC solve near 1.644 V;
reference screens reject that fallback. An explicit carrier-free cold-start and
power-cycle envelope retains the same circuit and external network. With 10 nF
coupling, nominal one-percent bias settling takes about 5.22 ms. Clock readiness
must follow actual bias/clock validity, not just the 20 µs supervisor guard.
The numerical anchor is not a fabricated resistor; physical clock reception
and readiness detection remain unqualified.
The same correction now applies to canonical RF screens and the selected
protected TX transition/hold replays. All reruns reject transient operating-point
fallback; the TX replays retain converged feedback and the 68 ns loaded hold.
RF power remains about −1.34 dBm at nominal gain and +0.16 dBm at maximum gain.
The diagnostic core pulse extremes remain approximately +4.54/−1.00 V, so
protection is still unqualified. See `generated/initialization-audit.json`.
Legacy wired fixtures and arbitrary floating-metal initial charge still need
review; the new checks do not retroactively validate historical runs.
Whole-core fit, distributed route resistance, core protection and the physical
receiver remain open.


All five current primary-protection candidates now pass a joint provider
placement check: bond openings match, no unexpected retained/custom metal
collisions remain, and local native-rail checks pass. Evidence is in
`generated/primary-protection-assembly/`. This is not whole-ring device LVS or
whole-core fit. `area-allocation.json` charges the identical candidate GDS to
current shared reservations: TX 250,000, RX/USB 290,000 and reference 130,000 µm².
The 250,000 µm² transfer from reserve leaves 460,000 µm² unassigned after existing
allocations, with the total die budget unchanged. Earlier report ceilings and
source hashes remain historical evidence, not a new electrical rerun. RX loading,
TX buffer dynamics, protection coordination and physical controls remain open.

The selected connected RF design has been freshly rebuilt and republished
against the current shared configuration. `rf-integrated-screen.json` and
`rf-assembly-screen.json` bind the new extraction, retained-state runs and
combined provider placement. Nominal/maximum-drive high-resistance outputs are
approximately −1.34/+0.16 dBm; diagnostic core pulse extrema remain approximately
+4.54/−1.00 V. These results preserve the RF power-margin and protection gaps.
The focused route regression now checks the selected full protection topology
in all three resistance corners, retaining every extracted device and capacitor.
Older four-device pad artifacts are not the selected RF regression target.

RX/USB loading attribution now uses the canonical protected physical model in
`wired-receive-usb-loading.json`, with the same documented numerical DC anchor.
The branch accounting retains protection and inactive paths. Use that report to
reduce loading without silently removing a required branch or weakening the
protection network.

## Current wired-TX integration

The working integration combines the protected 366-device TX pad, the
88-device thick-oxide static interlock, and a compensated buffer with a
1,280 µm source-PMOS bank. The reference-reset buffer variant has 282 devices
and is the current startup experiment. These are generated/extracted candidates;
the canonical family publication still needs integration and acceptance. Do not
read an earlier thin-oxide or smaller-buffer report as current coverage.

| Component | Current evidence | Unfinished work |
| --- | --- | --- |
| Static interlock | `transmit-control-candidate/thick-logic/`: local DRC, device graph/GDS round trip and 256 static cases pass. All devices are 6 V types; measured maximum absolute Vgd/Vgs is 4.151/4.095 V. | Physical request sequencing, actual serializer/bias fanout, supply supervision, terminal-current/reliability checks and core placement. |
| Buffer | `termination-buffer-candidate/source-headroom/`: stronger source bank reduces connected MAIN+POST DC error from 49.08 to 5.50 mV. | Loaded transients, compensation stability, current limiting, power-off behavior and area/current allocation. |
| Startup reset | `source-headroom/reference-reset/`: resetting GAIN toward REF lowers precharge peak from 2.652 to 1.818 V, retaining 5.52 mV DC error. | Unpowered TERM_VCM reaches −0.245 V; reference loading and terminal stress remain open. Rail-high reset was rejected for slow startup and worse power-off coupling. |
| Transaction sequencer | `rtl/pt_tx_pad_sequence.sv`; RTL checks in `tx_pad_sequence_tb.sv` pass. | Synthesis/layout, detector implementation, physical clock/count budget and mixed-signal convergence. |

Paths in the table are relative to `generated/` unless otherwise stated. Local
layout checks and completed simulations do not establish safe-state acceptance.
The buffer core alone reserves 157,650 µm² before compensation versus the
termination block's 150,000 µm² allowance; buffer/control funding and placement
are not closed. Connected DC supply draw is approximately 31.9–34.5 mA including
TX/control and prototype bias dividers. Prototype divider power must not be
mistaken for disabled-buffer leakage.

The sequencer snapshots a command only when command_ready is high. It removes
qualification, waits PRE_CYCLES, applies the captured request, waits POST_CYCLES
and precharge readiness, then enables the analog path. Buffer precharge is
independent of qualification. It keeps the load applied during startup settling
and asserts traffic_ready only after LOAD_CYCLES consecutive good samples under
load. A bad sample restarts that dwell. After traffic is ready, lost readiness
faults/disables and requires an explicit new command. Reset or invalid local
supply asynchronously disables; release and ordinary inputs require synchronized
integration. A stalled readiness wait currently requires reset to abort.

For the thick-oxide interlock, prescribed 4 ns pre/post blanking removes overlap
above 2.31 V at the tested 50/500 fF loads; 2 ns fails at 50 fF. These are nominal
experiments, not guaranteed hardware delays. Detector latency, clock period,
fanout, skew and analog conduction must determine the implemented cycle counts.
The serializer must define benign startup activity before traffic_ready.

The readiness observer uses shared `txpad.parameters.termination_readiness`:
±16.5 mV about BUF_REF, a modeled 1 ns filter and 0.99 assertion threshold.
These are first-pass allocations, not characterized comparator performance.
Offset, loading, supply current and physical detector layout remain absent.
Readiness applies to source termination; it is not a detector-mode criterion.
With prescribed readiness, the reference-reset circuit still reports 44.43 ns
of premature loaded traffic readiness. DC accuracy is not startup acceptance.

`transmit_sequence_connected.py --ready-data` performs sampled waveform feedback:
the preceding analog detector trace drives actual RTL, whose outputs drive the
next full extracted TX/interlock/buffer run. The same external network remains
connected throughout. A completed iteration is not closed-loop proof: require
unchanged feedback samples, accepted commands, qualified mode coverage and final
disable. The driver now obeys command_ready; reports include actual request values
in each timestamped window. Historical window names alone never establish mode
coverage. Current convergence evidence is linked from
`spec/schematic-implementation.json` under transaction_sequencer.feedback_iteration.
The fixed observation interval must not be confused with a protocol deadline.
The current retained-network replay converges at all 75 feedback samples,
exercises all four modes through traffic-ready, and reaches final disable, with
zero observed loaded traffic-ready time while the modeled detector is unready.
This is a transition check: TMDS has 1 ns of traffic-ready dwell; MAIN, MAIN+POST
and detection each have 4 ns. A separate `--scenario hold-main-post` replay
starts directly in MAIN+POST, reaches traffic-ready, and holds for 68 ns before
disable, with converged feedback and maximum 14.12 mV reference error against
the 16.5 mV allocation. See `reference-reset/loaded-hold/decision.json` beneath
the buffer source-headroom evidence. This extends nominal repetitive-data
coverage; longer operation, variation and other loaded configurations remain.
Only source-termination readiness is measured; other modes assume readiness.
Published observation windows use timestamps because command handshakes can
move the actual mode beyond a nominal window.

`transmit_fixture.py` builds the selected TX composition from shared
`io_pad_first_pass.tx_integration_fixture` parameters. A verified source manifest
binds it to the exact pad, buffer, interlock and specifications. The replay now
records pad voltages and currents in active, disabled, reset, unpowered and
reconfiguration states. These are observations, not electrical acceptance:
the retained 100 Ω differential load is not a TMDS pull-up receiver. TMDS mode
coverage does not establish TMDS compatibility. The power-down trace reaches
−0.742 V at a pad; protection/core voltage limits and transient current capacity
remain unresolved. Supply return includes stored charge, not just leakage.
The builder joins extracted circuits, not a placed/routed combined macro;
serializer, bias translations and readiness detection still include ideal
boundaries.

`transmit_integrated.py` now regenerates the selected four-tail TX pad and
attached primary protection from shared sizing/placement parameters, checks
extracted connectivity and scoped layout rules, renders the layout, and builds
the full pad/buffer/interlock fixture against that newly extracted pad. The normal `run_first_pass.py` entry point uses this generator, requires
converged readiness and complete retained-state coverage, and publishes this
model after checking provider placement.

The readiness replay accepts its own compact JSON report as `--ready-data`;
its recorded boolean detector samples are an initial guess, never acceptance.
The new analog simulation must independently agree with every sampled value.
This removes the need to retain a large waveform solely to reproduce the next
iteration. The scenario and exact sample schedule are checked before use.

The canonical `wired-transmit-loading.json` now measures the regenerated pad
at the shared lifecycle bias settings, with all branches attached and strict
operating-point checks. At 1 GHz, odd-mode disabled loading is 2.6846/2.6880 pF
per leg against 2.7 pF; detection is 3.7864/3.7993 pF and exceeds that allocation.
Other tested configurations stay below it. These independent biased AC probes
use stiff controls and pad voltage sources; they do not include package loss,
finite core impedance, retained charge or a data eye. They supplement the
connected lifecycle. The normal build regenerates this loading report; fresh
loaded-current calibration remains outstanding.

`wired-transmit-loaded-current.json` checks the selected shared biases with the
actual extracted buffer, interlock, source termination and retained differential
load, using zero-volt tail-current sensors. No bias is retuned for this check.
MAIN alone delivers about 20.72 mA versus the 16 mA maximum setting. With POST
enabled, one static steering state delivers approximately 19.80/8.89 mA; the
other reaches 16.04/7.98 mA versus 16/8 mA. These are a current-regulation gap,
not passing calibration. Buffer DC reference error stays below 5.43 mV, showing
why readiness alone does not prove output-current fidelity. The source-terminated
current source needs headroom/output-resistance improvement or a demonstrated
control strategy across data states. DC probes do not replace switching tests.

The optional `transmit_loaded_dc.py --probe-headroom` diagnostic keeps the
same extracted network and samples MAIN bias from 1.3 to 1.8 V, with the selected
POST bias fixed. At a 1.65 V reference, the best sampled MAIN setting still has
10.3% worst-state error. Raising the reference divider target to 1.8–2.2 V does
not resolve it: the buffer output stalls around 1.70–1.75 V, while best sampled
MAIN error remains about 9%. `wired-transmit-headroom-probe.json` records these
explicit overrides; none is selected as the design. This excludes a simple
reference-divider adjustment within the tested range, not all possible bias
settings or architectures. Prioritize current-source headroom/output resistance
and buffer output range together; do not tune a single steering state and claim
full branch-current accuracy.

The folded-tail candidate addresses this current-source gap. It uses 32 parallel
20 µm/1 µm fingers per MAIN/POST unit at diagnostic biases 0.873/0.802 V.
`folded_tail.py` builds the shared-diffusion bank and checks its streamed GDS;
`layout.py --external-primary --serial-tail-units 32 --folded-tails` places the
banks and all other branches, then `wired_protection_layout.py` attaches primary
protection. Parent routing supplies net labels; instantiated child copies omit
redundant labels while preserving geometry and standalone bank ports.

The complete 814-device layout occupies 239,060 µm² within 250,000 µm². Scoped
DRC, LVS, independent physical graph auditing and joint provider placement pass;
the rendered layout was inspected. Full-extraction DC errors stay below 1.5%
for MAIN-only and both MAIN+POST states; buffer reference error stays below
4.2 mV. Current sensing includes both source/drain orientations of all 512 tail
devices. `generated/tx-folded-tail/full-pad/` contains the candidate model and
evidence. Disabled odd-mode loading is 2.577/2.587 pF per leg at 1 GHz; detection
is 3.547/3.568 pF and remains over the 2.7 pF allocation. AC probes use stiff
controls and do not establish switching or protection safety.

The connected active-bias probe (`full-pad/bias-loading.json`) measures about
25.5 pF at MAIN_BIAS and 21.4 pF at POST_BIAS at 1 MHz. Ideal bias translations
therefore hide meaningful drive and settling requirements. Evaluate finite bias
drivers and precharging the references before steering enable; do not infer
bias readiness from the common-mode buffer detector alone.

The 300 ns retained-state replay now has a verified feedback fixed point:
feeding its completed detector samples through the actual RTL reproduces all
20 control events exactly. All modes reach traffic-ready, final disable is
observed, and loaded traffic-ready while the detector is unready is zero.
`full-pad/feedback-closure.json` records this alongside the 17 raw sample
mismatches against the preceding iteration; those differences do not change
controls within this fixture. `transmit_feedback_closure.py` rejects changed
controls and stale inputs, avoiding another expensive analog run only when the
same deterministic circuit inputs are proven. The normal TX builder uses this
check; identical events do not prove sustained operation or physical detectors.

`transmit_loaded_dc.py --probe-bias-driver` now tests finite 200 Ω and 1 kΩ
reference-drive resistance, with and without 40 ns precharge, in both static
steering states. The full extracted circuit and external differential network
remain connected. At 200 Ω, both tail currents enter the ±3% band within
14.8–25.8 ns after enable and remain there through the observation window;
peak bias-source current is about 4.15/3.81 mA. Three of four 1 kΩ cases fail
the 80 ns post-enable settling window. Precharge does not eliminate steering
kickback or common-mode settling. `full-pad/bias-driver-screen.json` records
these cases. This motivates a roughly 200 Ω drive target and explicit settling
qualification, not a claim that an actual driver meets it. The probe starts
with supply and termination regulation established, uses static data, and does
not charge ideal reference-source power to VDD. A subsequent 300 ns lifecycle probe with 200 Ω MAIN/POST bias drive
completed but retained four sampled feedback mismatches, beginning at 145 ns;
it does not establish closed-loop lifecycle acceptance. The fixture builder
exposes this diagnostic through `bias_resistance_ohm`; it leaves the canonical
selection unchanged. Full finite-driver lifecycle, supply/current accounting
and physical implementation remain open.

This candidate is not the canonical selection. Finite bias-driver behavior and the physical bias/control implementation
remain adoption gates; the nominal ideal-bias lifecycle is now closed. The earlier hybrid
DC probes and oversized direct-replication experiment are diagnostic evidence,
not alternative normative pad designs. Full regenerated layout evidence takes
precedence over those sizing estimates.

The TX lifecycle measures both remaining ideal-source energy and actual macro
supply currents. `wired-transmit-screen.json:ideal_driver_burden` separates
positive delivered, absorbed and net energy; `macro_supply_currents` uses
zero-volt supply probes at top-level macro ports. Means are time-weighted over
traffic-ready intervals, excluding gaps. Ideal-source energy is not silently
charged to VDD or treated as recoverable energy. Independent ideal command
sources and physical upstream driver losses remain outside this accounting.

The current MAIN+POST window draws approximately 92.4 mA: 57.6 mA in steering
drivers, 32.9 mA in the termination buffer and 2.0 mA in top-level bias circuitry.
The interlock contribution is negligible in this window. The driver and buffer
alone exceed their respective 36 mA and 8 mA block allocations. The WIRE supply
allocation is 96 mA; adding the other wire blocks' approximately 34.6 mA allocations to this
measured TX burden gives an approximately 127 mA planning screen. This is a real design-budget
conflict, not a measured package-current limit or a sustained-current result.
`coverage.json:wired_tx_macro_power` derives that comparison from the shared
architecture and contract. Reduce the TX drive/buffer burden or explicitly
redesign the power allocation and distribution; do not hide it by increasing
budgets without a whole-system check.

The selected TX fixture now inserts six copies of the extracted
`steering-buffer/physical.spice` between upstream data gating and the MAIN,
POST and TMDS steering gates. Each copy is a 34-device, four-stage noninverting
CMOS chain; output charge and discharge currents therefore flow through real
PDK transistors connected to VDD/VSS. `generation_parameters.tx_steering_buffer`
owns the sizing recipe. `steering_buffer.py --output-dir <new-directory>`
regenerates the selected circuit and layout; the normal TX integration build
also regenerates it and uses that fresh extraction in the connected fixture. The same generic layout generator checks DRC,
extracted connectivity and the exported GDS graph. The six measured macro
rectangles total approximately 114603 µm² and reserve 140000 µm² inside wired TX,
in addition to the interlock's 60000 µm²; 100000 µm² remains for other wired-TX
implementation. All six macros now have named placements beside the wired-TX pad, with
provider-core containment, envelope-clearance and same-layer collision checks.
Six output-to-pad routes are now generated separately from the placement stage;
supply and other signal hookups remain incomplete. Upstream data gating, bias drivers and buffer-enable drive remain explicit
boundaries; steering-buffer insertion does not complete the whole control path. The
current connected run reaches every mode and reproduces identical RTL control
events when its measured readiness is fed back. One raw detector sample differs
but does not change any control event; `wired-transmit-feedback-closure.json`
therefore establishes nominal sampled-control closure. This does not establish
physical detector behavior, sustained timing or acceptable power.

The same fixture builder also supports `external_network="split_pullup"`:
two receiver-side resistors and an independent supply use the shared TMDS
50 Ω / 3.3 V parameters. The resistor/peer supply network remains connected
through all states; no chip circuitry or protocol-specific pad variant is
substituted. `wired-transmit-pullup-screen.json` exercises reset, power-off,
brownout, reconfiguration and a 68 ns continuous TMDS ready interval with the
same extracted drivers and pad. Active peer draw averages approximately
9.98 mA against the shared 10 mA target; pad differential peaks reach about
±0.456 V. Its separate closure report establishes sampled-control consistency
for the requested hold scenario, not coverage of every wired mode on this load.
Power-off and transition windows still show rail-return currents and pad
excursions. No core-survival, steady leakage, eye-mask or HDMI compliance claim
follows from this nominal load case. The differential-load lifecycle remains
the all-mode case; the two reports exercise one selected chip with different
retained external networks.

The same builder also supports `external_network="ac_coupled"`, retaining
one shared-fixture coupling capacitor per leg and a split remote termination
at the shared nominal common-mode voltage. The remote bias stays powered
through chip rail loss. The physical TX, buffer and interlock are unchanged;
capacitor charge evolves continuously from the initial DC operating point.
The lifecycle observer records receiver common-mode/differential voltage and
coupling-capacitor voltage separately from chip-side pad voltage. This boundary
is needed because AC coupling blocks steady DC but still transfers power and
mode-change transients. A short lifecycle does not establish long-run baseline
wander, receiver survival or protocol compliance.

`generated/wired-transmit-ac-coupled-screen.json` records the first 300 ns
open-loop RTL replay through this network, with all mode/state windows reached.
Receiver common mode reaches about 2.47 V during reconfiguration and remains
about 2.03–2.30 V during the active MAIN window, despite the remote 1.65 V bias.
The 100 nF coupling capacitors retain approximately −1.65 V from the initial
operating point. This is a startup/transition exposure, not settled data or a
receiver-survival verdict. TMDS/detection windows in this generic sequence are
stress configurations, not claims that those interfaces operate through this
AC network. Sampled analog feedback closure is not established for this run.

**Design consequence:** local termination readiness must not be interpreted as
remote receiver readiness. Startup, wake and mode changes need a defined
common-mode settling/training interval at the system boundary before payload
acceptance. The host must coordinate that interval with the external receiver;
the chip cannot infer remote capacitor charge from its local buffer detector.
A cold/discharged capacitor case and sustained operation are still needed to
bound that interval. Do not invent a fixed delay from this short transient or
change the local detector threshold to hide the remote excursion.

RF TX now accounts for the shared 28 mA active bias-current floor in addition
to observing output-branch currents. The extra behavioral rail draw fills only
the difference between the floor and sourced output current, avoiding double
counting. It is an assigned biased-driver model, not measured transistor bias
or a physical bias circuit. Its instantaneous compensation must not be used as
proof of supply-noise rejection or an accurate RF ripple spectrum. Disabled
zero draw is likewise behavioral; reverse junctions and real bias shutdown
remain unimplemented. Nominal and maximum-gain retained-state screens, including
held-enable faults, preserve the signal results (about −1.34 and +0.16 dBm at
high route resistance) while now drawing the assigned 28 mA when active.

The RF pad driver now consumes `rfdriver.supply_gain_model` for its command
amplitude, retaining the one-pole state through disabled and power-off windows.
Previously this shared response was absent from the pad bench. Its behavioral
RC state is mathematical, not a proposed physical capacitor or bias circuit;
output-stage current/headroom and rail-dependent conductance remain separate
boundary assumptions. The response matches the shared analytic transfer law
at 61 frequencies from 1 kHz to 1 GHz (maximum complex error below 3e-16).
Signal-path bandwidth and physical bias startup remain unimplemented.

This correction leaves initial nominal tone power at about −1.34 dBm but lowers
the post-shutdown reactivated window to about −2.97 dBm. Maximum-gain results
must likewise be assessed separately before and after rail recovery in the
published reports. **Re-enable is not RF readiness:** this 80 ns stress fixture
deliberately bypasses the architecture's existing 20 µs cold-start guard and
bias/reference qualification. It therefore does not demonstrate a missing
architectural guard or a failure of normal guarded startup. The remaining gap
is connecting and validating those readiness controls against the attached
circuits. Warm direction changes keep bias/reference valid and use the separate
H2D guard; they must not be modeled as rail shutdown followed by cold startup.
Do not reset mathematical state or recalibrate input amplitude to hide recovery.
Neither this short exposure nor the assigned gain law establishes physical
bias startup or a worst-case recovery time.

`generated/rf-transmit-startup-screen.json` now exercises the selected routed pad
with that existing 20 µs guard, retained shared gain state and a quiet external
peer followed by a 2.4 GHz burst. At maximum gain it produces about +0.23 dBm,
meeting the tone target, with command supply-gain recovered to 1.0. This supports
keeping the current startup policy for the assigned model. The guard is imposed
by the fixture, not a connected supervisor; the gain law through zero supply is
an explicit extrapolation. Physical readiness, modulated performance and warm
turnaround still require their own evidence. The nominal-gain power miss remains.

The shared RF-domain allocations total 53 mA in warm RF operation against the
contract's 48 mA domain allocation. `coverage.json:rf_supply_planning` exposes
this independently of the whole-chip current ceiling. Neither number is a
measured bond-wire rating. The current-accounting audit also applies the shared
TMDS branch override: its active steering buffers consume about 30.3 mA in the
short all-mode window against the TMDS block's 16 mA allocation. They must not
be hidden under the unrelated normal wired-TX allocation. These supply and
power gaps join protection/core coordination and actual RF core loading as
first-pass integration decisions; no allocation has been increased to hide them.

## First-pass implementation closure

The first pass must connect the selected circuits, their generated layouts and
their retained-state models. Later silicon characterization and certified ESD
ratings are separate evidence requirements; they must not be claimed from these
simulations or turned into an endless prerequisite for drawing the first pass.
Unimplemented circuitry remains a first-pass gap even when a behavioral boundary
predicts acceptable performance.

Prioritize cross-family integration decisions before further operating-point
optimization. The remaining work is not just parameter tuning:

| Priority / shared risk | Present evidence and gap | First-pass decision gate |
| --- | --- | --- |
| 1. Protection compatible with the attached core | Primary protection is physically present, but diagnostic RF pulses still reach roughly +4.54/−1.00 V at the core boundary. Survival and discharge-current capacity are unqualified. | Specify allowed voltage/current versus duration for each attached core and choose a coordinated protection/isolation circuit. Check normal signal loading and powered/unpowered exposure together. Do not interpret diagnostic pulses as an ESD rating. |
| 2. Safe behavior without an already-working host | Reset, brownout and readiness still depend partly on prescribed or behavioral controls. Independently powered host operation has recorded substantial backfeed and is unsupported without isolation/sequencing. | Implement local disable, power-domain crossings and readiness sufficient to keep every connected branch safe through startup, rail loss and mode changes. Retain the external network and account for stored energy. |
| 3. Real pad-to-core interfaces | RF LNA/driver and reference receiver remain explicit behavioral boundaries; TX bias and serializer drive remain idealized. Extracted TX buffer/interlock and steering macros have area reservations and checked placements; six steering output routes are generated, while supply/control/buffer routing remains incomplete. Connected TX current exceeds current planning allocations; RF domain allocations also exceed their domain budget. | Assign physical implementations and power/loading budgets to the interfaces that determine pad operation. Decide whether the complete circuits fit and meet headroom before optimizing individual bias values. |
| 4. Whole-ring and package integration | Provider openings and local geometry/connectivity checks pass. Attached TX macro clearance is checked, but full-core integration, full-ring device LVS, distributed returns/coupling and full-bank switching are incomplete. | Preserve provider-compatible bond sites, place/fund attached macros, connect the complete supply/return network and evaluate bounded package loading and host switching on that same assembly. Local DRC is not this gate. |
| 5. Representative electrical capability | The all-mode 100 Ω TX fixture is supplemented by an independently powered split-pull-up hold case; nominal current and feedback are demonstrated, but electrical/protection acceptance remains open. RX bypass loading exceeds its budget on one leg; RF TX power margin is narrow; reference startup is millisecond-scale with the retained external bias capacitor. | Exercise representative DC-coupled, AC-coupled, USB bidirectional, RF and reference interfaces with their actual external networks and acceptance limits. Include sustained operation and transitions; distinguish failed limits from missing evidence. |

The next milestone is an integrated pad-to-core design decision across these
five gates. Start by specifying each attached circuit's normal signal envelope,
allowed transient exposure, off-state behavior and power/loading allowance.
Use those same interfaces to decide whether the protection, local controls and
supply/return topology can coexist with the required bandwidth. Unknown core
limits remain explicit assumptions, not demonstrated survival limits.

Make a keep/change/unresolved decision for each family, supported by the
existing evidence and only the additional representative checks needed to
resolve that decision. Power-budget conflicts require a circuit or allocation
decision with whole-chip accounting; a larger numerical allowance alone is not
a resolution. Preserve provider-compatible bonding and account for external
components together with their interconnects. Defer further bias, capacitance
and geometry sweeps unless their result can change one of these decisions.

### Current first-pass decisions

Keep the five pad families and provider-compatible bond geometry. The next
implementation changes must follow these decisions across families:

- **Protection:** keep the isolated primary protection rail; coordinate a
  core-side secondary network with the actual input/output devices. Do not
  divert primary discharge into a functional supply rail. RF and reference
  interfaces require low-loading secondary treatment; a large generic series
  isolation switch is not selected without a bandwidth/loading demonstration.
  DC-coupled wired interfaces must preserve their required external levels;
  external AC coupling is not a universal protection substitute.
- **Local safety:** use local rail qualification and reset-dominant disable,
  with passive default-off paths at the final enables/bias controls. Keep
  break-before-make sequencing separate from static conflict exclusion. A
  supervisor must remain effective during collapse, or passive device paths
  must enforce the safe state after it stops operating. Independently powered
  host GPIO requires external isolation or enforced board sequencing until
  its backfeed path is resolved. These are implementation requirements, not
  claims that the existing ideal supervisor has become a physical circuit.
- **Power:** retain measured macro current and the RF driver bias floor in
  accounting. Do not reclaim warm RF bias merely because RX and TX data are
  exclusive; turnaround depends on it. Decide driver/buffer efficiency and
  the complete supply/return capacity before increasing allocations. External
  decoupling can reduce ripple but cannot eliminate average-current demand.
- **Routing:** preserve primary-tap topology, size both bond escapes and
  internal current buses, and include return paths. Equal drawn P/N lengths
  alone do not establish matched resistance, capacitance or delay. The new TX
  resistance overlay is an initial diagnostic, not the final interconnect.
- **Acceptance:** use the same selected pad with its actual peer network for
  every lifecycle state. The differential-load TMDS window only exercises
  controls; TMDS acceptance needs the independently powered pull-up fixture.
  USB needs bidirectional turnaround and pull/termination handoff; RF needs
  modulated performance with the real core; the clock input needs jitter and
  actual bias readiness. Keep failing electrical limits visible even when
  control feedback converges.

RF/reference attached capacitances now come from their shared architecture
blocks rather than hard-coded bench constants. The selected assumption remains
100 fF per leg. `generated/rf-core-loading-sensitivity.json` records a maximum-gain
RF TX comparison at high route resistance: 100 and 500 fF per leg produce about
+0.163 and +0.146 dBm respectively in the active tone window. The larger value
is an explicit sensitivity case, not a characterized bound. This small change
does not justify another capacitance sweep: actual driver bandwidth, impedance,
protection exposure and bias behavior are still missing, and the absolute power
margin remains narrow. Neither case establishes modulated RF performance.

The current-carrying TX buses also need explicit physical sizing. The former
uniform 0.44 µm non-supply trunks made the long `TERM_P_R`/`TERM_N_R` trunks
approximately 54/57 Ω end-to-end at the PDK nominal M5 sheet value, before via
and transverse losses. Those are trunk estimates, not a complete termination
impedance, but they invalidate treating this wiring as ideal. The selected
layout now assigns 8 µm to those two trunks, `TERM_VCM` and both pad trunks,
through `io_pad_first_pass.layout_parameters.wired_transmit`. The generator
validates names, spacing allocation and bank fit; other signal widths remain
unchanged. `coverage.json:wired_tx_current_bus_estimate` compares selected and
published widths and reports the same geometry/sheet calculation for the actual
published layout. Distributed resistance must still enter the connected model.
Do not accept a capacitor-only result as a wired impedance or timing verdict.
The widened protected layout retains 366 devices, passes local DRC and device
connectivity, fits the existing pad reservation, and reaches sampled readiness
closure in the connected lifecycle. Its disabled odd-mode loading is about
2.706/2.713 pF per leg against 2.7 pF; one active MAIN leg also exceeds that
allocation, and the existing detection-loading miss remains. These are recorded
failures, not waived budgets. Widening addresses a large resistance omission;
it does not complete impedance, current-capacity or timing qualification.
A branched signal-metal estimate is implemented in `wired_tx_route.py`.
It separates the common bond lead, core connection and primary-protection arm,
preserving every extracted device. At nominal sheet resistance, bond-to-core
metal contributes approximately 8.34 Ω (P) and 11.67 Ω (N), before vias and
internal core buses. This asymmetry requires a connected electrical check;
the widened M5 trunks alone do not establish acceptable total resistance.
The overlay places extracted linear capacitance at the core endpoint, keeps
physical steering diodes on the primary arm, and omits return-path resistance.
It is a diagnostic approximation, not distributed extraction or an accepted
replacement for the canonical pad model.
The connected 300 ns open-loop replay is recorded in
`generated/wired-transmit-branched-route-screen.json`. MAIN and MAIN+POST
show approximately ±0.437 V and ±0.517 V differential extrema respectively,
but these extrema are not eye or compliance results. All requested modes are
reached; the prescribed controller also claims readiness without the loaded
analog detector for about 40.95 ns. Two subsequent sampled-feedback iterations do not establish closure: the
first has zero premature-ready duration but incomplete mode coverage; the second
reaches all modes but records about 31.98 ns premature readiness and changes
controls again. This is unresolved waveform-relaxation/control behavior, not
proof that the physical circuit must oscillate. The unpowered pad reaches about
−0.656 V; core-survival limits and physical local controls remain unresolved.
This is evidence for completing routing and safe-state integration, not a
passing family verdict or a reason to relax the readiness limit.

The canonical all-mode lifecycle and loading reports are rebuilt for these
widths. Supplemental split-pull-up and AC-coupled TX reports predate this geometry
change and require refresh before being used as current electrical evidence;
their topology/control lessons do not substitute for that rerun.

The canonical wired TX also misses its intended current settings in connected
static checks. A compact folded-tail candidate improves those currents and fits
the pad reservation, but is not selected: finite bias drive and physical control
implementation remain open. Treat this as a subordinate part of the pad-to-core
interface decision, not the organizing priority for all pad work.

A useful stopping point is one integrated first-pass pad system with explicit
core contracts, implemented safe states, a buildable ring and representative
electrical acceptance results. It is not a collection of individually tuned
pads. Resolve or explicitly bound each gate above before adding protocol-specific
variants or more small probes. A named lifecycle window or a completed transient
is coverage, not acceptance. `generated/coverage.json` remains incomplete until
the circuit/model and layout gaps are closed; later silicon characterization
and protection qualification remain separate requirements.

The selected attached TX macros are accounted separately from the pad cell.
`core_area.py` reads the selected model paths, verifies layout/model hashes and
measures their actual GDS bounding rectangles. The buffer occupies approximately
155658 µm²: reserve 175000 µm² inside a 200000 µm² termination block. The interlock
occupies approximately 48100 µm²: reserve 60000 µm² inside the existing 300000 µm²
wired-TX block. Increasing termination by 50000 µm² transfers that amount from
reserve without increasing the total die budget; contract and architecture area
groups agree. `generated/attached-core-area.json` records the geometry check.
These reservations do not establish placement, routing clearance, bias-passive
fit or funding of the remaining monitor/control circuitry. In particular the
buffer is roughly 1.12 mm long in its current generated arrangement.

Passing `--assembly` to `core_area.py` also places the selected GDS macros into
the audited pad assembly using shared placement parameters. The buffer is
rotated horizontally above/left of wired TX; the interlock is immediately left
of it. The generator checks provider-core containment, 20 µm envelope clearance
from the custom pads/other macro, and actual same-layer metal collisions against
the native ring and existing instances. `generated/attached-core-placement.svg`
is an envelope preview, not a wiring diagram; `attached-core-assembly.oas` holds
the actual macro instances. The six named steering instances are included in the same placement. These
are unrouted in this intermediate placement artifact. Area-only rebuilds
intentionally do not claim placement evidence.

Add `--route-steering` to generate the selected six output connections in
`attached-core-steering-routed.oas`, with the report and preview in
`attached-core-steering-routing.json` and `.svg`. Shared
`io_pad_first_pass.steering_output_routing` sets the channels, widths and escape
spacing. The generator resolves actual transformed GDS port labels, lands on
the corresponding M5 conductors, and uses M4/M5 routes with via4 transitions.
It rejects unintended intersections with existing metal or other routes and
checks exported route metal and preserved bond openings. P/N drawn lengths are
matched; differing bends/vias mean this is not matched RC or timing evidence.

`rail_connectivity.py --steering` extracts the complete TX macro cluster and
adjacent native pad geometry from that routed assembly. The drawing-only
extraction uses metal and vias, with MIM contacts handled separately; labels
locate probes but cannot join disconnected metal. The current
`attached-core-steering-connectivity.json` confirms all six intended connections,
separation between outputs and absence of connections to the other checked ports.
A removed landing via and a bridge between MAIN outputs are both detected.
The campaign leaves the canonical geometry unchanged. Whole-ring connectivity
outside the cluster remains unverified; the existing full-assembly intersection
check is a different, weaker check and must not be described as ring LVS.

This advances physical integration, but **does not complete the assembly**:
buffer, interlock, supply/return, bias and upstream-data hookups remain open.
Spacing DRC, complete device/supply connectivity and routed transient timing still need to
be checked before these wires can replace ideal connections in the electrical
model. The routing preview shows paths over macro envelopes, not full mask detail.

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
`generated/custom-assembly-candidate.oas` and its renders are the canonical
geometric assembly. Full-ring device LVS, integrated signoff, package returns,
full-bank switching and core clearance remain open.

The canonical TX retained waveform includes approximately 8.24 ns below the
shared supply-valid threshold and above 0.1 V, including a 1.5 V plateau.
Postprocessing records zero traffic-ready and buffer-enable, but a pad minimum
of about −0.726 V and termination-enable maximum of about 0.476 V. These are
exposures requiring protection/control coordination, not proof of damage or
proof of isolation. `transmit_sequence_connected.refresh_brownout()` validates
the saved deck and architecture hashes before reanalysis; the report preserves
original simulation provenance separately from postprocessing provenance.

## Host and power boundary

`retained_screen.py` retains representative host/input/reset cells, all eighteen
native supply pads, finite feed/bond impedance and board/local decoupling.
The default host shares the upstream board supply with the chip. An independently
powered host remains unsupported without validated external isolation/sequencing:
the recorded off-state backfeed is approximately 81.6 mA. Commanded OE-low reset
is not a proven supervisor, and representative switching is not full-bank SSO.
Large source-return currents during power-down include stored decoupling charge;
they must not be mislabeled as static leakage.

`generated/receive-shared-pdn-screen.json` connects the extracted RX/USB pad
to the shared reduced feed/package/decoupling network for a 3 µs probe. During
the sampled upstream 1.5 V command, the local rail is only about 0.54–1.15 V;
stale enables cause approximately 3 mA backfeed while prescribed disable
removes positive backfeed in that window. Controls must respond to local rail
state, not upstream command alone. This reduced network omits native supply
cells and assumes a bidirectional ideal upstream source; its roughly 20.8 A
peak returned charge current is not evidence that a real regulator can absorb
that transient. It is not a replacement for the retained native-supply fixture.


## Reproduction

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

Focused generators/screens expose `--help`. `analog_screen.py` supports external
reference termination, RF coupling capacitance and a lossy series-inductor probe.
`protection_pulse.py` and `terminal_exposure.py` consume existing retained-network
fixtures and exact physical models; they do not supply ESD or reliability limits.
`receive_bleed.py` likewise requires the exact extracted RX model and a qualified
3 µs retained-peer fixture with the documented 1.95–2.205 µs off window. It
checks rail and bypass disable in that window, sweeps all four core resistances
through the same external network, and separately measures nominal bypass DC
and 1.25 GHz transfer. It does not select a physical discharge resistor.

`rf_startup.py` consumes an exact integrated model and existing lifecycle
fixture, derives the guard and drive amplitude from shared parameters, and
runs quiet bias startup followed by a resolved RF burst without resetting
stored state. It requires and preserves the shared command supply-gain response
when replacing the carrier with its guarded burst. It keeps passive components attached and declares its silent
external-peer assumption. `wide-route-rf-candidate/startup-reproduction.json`
records a 64/128-sample-per-cycle resolution comparison for this bench.

The next integration decision is the protection topology and its core-facing
voltage contract, followed by implemented safe-state controls. Keep these open
in `coverage.json`; passing test counts are not a measure of completeness.
