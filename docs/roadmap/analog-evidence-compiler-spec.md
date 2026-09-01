# Product-first analog evidence plan

- Status: active product roadmap; long-range architecture reference
- Date: 2026-08-31
- Working name: `aec` (a label for narrowly scoped helpers, not a current
  standalone compiler deliverable)
- Initial process target: GF180MCU
- Initial applications: PCIe Gen1 wireline PHY and 2.4 GHz Wi-Fi radio
- Delivery strategy: integration-first over reviewed open-source components

For the executable current-state inventory, commands, and active product
gates, see [analog evidence tooling overview](../verification/analog-evidence-tooling-overview.md).

## 1. Purpose

The deliverable is not an analog compiler. The deliverables are a physically
verified PCIe interface and a Wi-Fi receiver/transmitter path with an honest
model and measurement boundary. This document permits a small evidence toolchain
only when it gets one of those products through its next physical decision.

The current toolchain starts with the repository's SPICE/layout generators,
native DRC/LVS/PEX runners, focused checkers, and immutable result records. A
new helper is justified only if it removes a repeated, observed product cost:
for example, lost source/PEX identity, manual PVT scheduling, ambiguous failed
internal nodes, or an unlabelled RF model boundary. It is not justified merely
because it resembles part of a future compiler.

At the point a promoted product claim needs it, the toolchain should turn an
intended transistor/passive circuit, physical constraints, and a system-level
behavioral contract into:

1. a manufacturable physical implementation;
2. calibration and test mechanisms needed to make that implementation robust;
3. executable verification across every declared environment; and
4. a content-addressed evidence package stating exactly what is proven, failed,
   assumed, bounded, or unavailable.

The toolchain is successful only when it shortens the complete
circuit-to-evidence loop for PCIe or Wi-Fi. Its success metrics are product
closure milestones, not language features, supported operation counts,
generated-layout counts, or framework completeness. `aec` work that does not
unblock an active chip claim is deferred.

The existing whole-interface Aether source at
`projects/pcie_gen1_endpoint/analog/pcie_gen1_x1.aether` is an example front-end
contract. The rest of this document records desired evidence semantics and a
possible future architecture. **Only Section 17 authorizes active implementation
work.** Sections 4--16 are checklists for deciding whether a product claim is
sound; they are not a backlog to implement a language, solver, optimizer,
router, or service.

AEC is not a ground-up replacement for the open analog ecosystem. If a narrow
gap repeatedly blocks a product claim, it may supply that one missing semantic,
identity, calibration, hierarchy, or claim-refinement function while adapting
reviewed upstream projects. It must not become a parallel product.

Normative terms **MUST**, **SHOULD**, and **MAY** describe required, preferred,
and optional behavior for a claim that is being promoted. They do not authorize
proactive implementation of a general capability.

## 2. Product boundary

### 2.1 Claim capabilities, only when a product gate needs them

The product toolchain MUST support the following only to the extent required by
the active PCIe or Wi-Fi gate:

- transistor, passive, behavioral, package, channel, and thermal models;
- user-selected circuits and bounded topology families;
- transistor sizing, fingering, matching-array construction, placement,
  routing, supply distribution, guard structures, and legal fill planning;
- schematic, estimated-parasitic, extracted-RC, post-fill, package/channel,
  and selected multi-physics verification boundaries;
- joint search over physical parameters and realizable calibration controls;
- hierarchy, assume/guarantee composition, and routed-parent verification;
- exact, interval-valued, sampled, random, and stochastic-process uncertainty;
- automatic failure localization and ranked candidate remedies;
- deterministic builds, cache identity, immutable evidence, and claim tracking;
- both time-domain wireline circuits and frequency-domain/RF circuits.

### 2.2 Not an active deliverable

Version 1 MUST NOT claim unrestricted synthesis from prose into an invented
analog topology. It starts from an intended circuit, a library topology, or an
explicitly bounded topology family. It MAY later search among reviewed topology
families.

The compiler MUST NOT:

- invent probability distributions for missing fabrication data;
- convert public pre-silicon models into unsupported yield, compliance,
  interoperability, ESD, lifetime, or regulatory claims;
- treat DRC, LVS, schematic simulation, or leaf-level PEX as interchangeable;
- hide a failed case by changing a requirement after observing the result;
- call a schematic composition a routed physical parent;
- accept an ideal voltage source, ideal bias, or simulator-selected trim code as
  an implemented calibration mechanism;
- silently modify circuit connectivity as a layout optimization;
- fork or reimplement a suitable upstream capability without a recorded
  semantic, technical, licensing, or maintenance reason;
- replace provider signoff or measured silicon.

## 3. Governing principles

### 3.1 One top-level contract

The top-level application contract owns link or radio performance, power, area,
startup, calibration, diagnostics, and model assumptions. The compiler owns
budget partition unless the user freezes a budget explicitly.

For PCIe, this permits a joint trade between transmitter swing/emphasis,
channel loss, receiver gain, sampling margin, PLL jitter, and CDR tracking. For
Wi-Fi, it permits a joint trade between LNA noise, mixer gain, converter range,
baseband processing gain, oscillator phase noise, PA linearity, external filter,
and antenna/matching loss.

Leaf contracts are necessary implementation interfaces, but they MUST refine
the composed contract rather than replace it.

### 3.2 Intended circuit plus intended behavior

Circuit intent and performance intent are independent inputs:

- Circuit intent defines allowed devices, connectivity, topology choices,
  polarity, state, programmable elements, and forbidden transformations.
- Performance intent defines function, environments, hard predicates,
  guardbands, objectives, confidence, and acceptable estimator error.

The physical optimizer MAY change sizes, multiplicities, device ordering,
legal passive geometry, placement, and routing inside declared degrees of
freedom. A change to device count, connectivity, state, terminal order, control
meaning, or topology MUST create a circuit revision and repeat schematic
verification.

### 3.3 Evidence is a compilation output

Every emitted claim MUST be joined to hashes of the exact circuit source,
physical source, generated layout, extraction, models, testbench, simulator,
measurement implementation, and result. A result with an incomplete identity
chain is diagnostic data, not release evidence.

### 3.4 Verification is relative to models

Every proof statement MUST name its model domain. Unknown but bounded behavior
is verified adversarially over intervals. Statistically distributed behavior is
verified statistically only when the distribution has approved provenance.
Unavailable behavior remains an explicit open obligation and SHOULD cause the
compiler to propose silicon test structures and observables.

### 3.5 Integration-first architecture

The initial architecture assigns narrow responsibilities to existing projects:

| Layer | Preferred upstream | AEC responsibility |
|---|---|---|
| Whole-system intent | Aether contract in this repository | Composition, ensembles, budgets, calibration, refinement |
| Circuit and bench language | [Cascode](https://github.com/daniellovell/cascode) | Import/export adapter and semantic extensions, not a competing low-level syntax by default |
| Deterministic EDA evidence | [OpenADA](https://github.com/simra-tech/OpenADA) | Compose operation evidence into hierarchical claims and fill unsupported profile gaps explicitly |
| Characterization campaigns | [CACE](https://github.com/efabless/cace) | Generate campaign intent, bind exact artifacts, and import checked results |
| Generator-based layout | [OpenFASoC/gLayout](https://github.com/idea-fasoc/OpenFASOC) | Supply topology/physical intent and verify emitted geometry |
| General constrained layout | [ALIGN](https://github.com/ALIGN-analoglayout/ALIGN-public) | Translate constraints, qualify PDK support, and verify emitted geometry |
| Full-chip flow reference | [IHP AMS chip template](https://github.com/iic-jku/ihp-sg13g2-ams-chip-template) | Reuse assembly, padframe, DRC/LVS/PEX, and release patterns where portable |
| Native tools | ngspice, Xyce, Magic, Netgen, KLayout, openEMS and later qualified solvers | Select through capability profiles and preserve native artifacts |

These are capability assignments, not unconditional dependencies. Every adapter
MUST pin an upstream revision, license, runtime, supported semantic subset, and
conformance fixtures. A roadmap feature in an upstream project is unavailable
until its exact revision passes an AEC fixture. In particular, Cascode's
topology-synthesis and physical-layout stages are currently roadmap concepts;
OpenADA's typed profiles are intentionally narrower than AEC's eventual
analysis set; and OpenFASoC, gLayout, and ALIGN support only qualified topology
and PDK domains.

OpenADA evidence envelopes SHOULD be retained intact inside Evidence IR rather
than normalized a second time. AEC adds system claim identity, hierarchy,
dependency/refinement edges, model scope, and release policy above that narrow
execution boundary. When OpenADA lacks an operation, AEC SHOULD first propose a
versioned upstream profile or an independently installable conforming provider.
A private adapter is permitted only as an explicitly scoped interim capability.

Cascode SHOULD be the first candidate representation for elaborated leaf
circuits and reusable benches. Aether remains the whole-system contract because
it must express quantified environments, shared conservation nodes, temporal
and ensemble measures, budget allocation, calibration, and application-level
guarantees beyond the present Cascode language. The integration study MUST
determine whether to compile an Aether circuit subset to Cascode, import linked
Cascode artifacts into Circuit IR, or support both without semantic duplication.

### 3.6 Product-first delivery rules

The following rules override architectural elegance:

1. Every tooling task MUST name the PCIe or Wi-Fi claim it unblocks and the
   manual step, runtime, error class, or evidence gap it removes.
2. New infrastructure MUST be exercised immediately on an active design. A
   synthetic example is useful for unit testing but cannot justify the work.
3. Prefer a thin adapter to an upstream project over a new framework. Prefer an
   existing repository script over an adapter until repetition or correctness
   risk makes the adapter worthwhile.
4. Preserve the current working flow as a fallback until the replacement
   reproduces its passing and failing evidence.
5. Generalize a mechanism only after it is needed by two real blocks or by both
   applications. The first implementation MAY be deliberately specific.
6. Stop or simplify a tool branch when it consumes more effort than the next
   direct circuit/layout experiment it was intended to save.
7. Do not implement unrestricted topology synthesis, a distributed service, a
   graphical IDE, or a new numerical solver before the two vertical slices in
   Section 17 pass their declared exits.

The semantic kernel in this document is a compatibility target and guardrail,
not a requirement to implement every abstraction before useful work resumes.
Initially, Aether MAY remain a reviewed specification, Cascode MAY remain an
external leaf format, and OpenADA/CACE MAY be invoked as pinned subprocesses
through their native JSON/filesystem contracts.

### 3.7 Implementation-language policy

Use the languages of the adopted components and minimize glue. The first
integration SHOULD use Python, schemas, and subprocess adapters because the
existing Svalbard flows, OpenADA, CACE, OpenFASoC, gLayout, and ALIGN are already
accessible that way. Cascode remains an external .NET tool behind a deterministic
artifact boundary.

Rust remains the preferred implementation language for a stable AEC core when
profiling or failure history demonstrates a need for stronger type enforcement,
parallel scheduling, geometry performance, or long-lived dependency identity.
Do not begin with a broad Rust rewrite. A Rust component is admitted only with
a real design fixture, a compatible serialized boundary, and a measured reason
that the smaller Python/upstream solution is inadequate.

### 3.8 Delivery order: chips first

AEC is a means of getting two products through their next physical-evidence
gate. It is not an independently funded platform. The active delivery order is:

| Priority | Product gate | Direct engineering work | Permitted supporting tooling | Done means |
|---|---|---|---|---|
| 1 | PCIe recovered-clock/capture boundary | Add one real selected pulse-control path, then rerun the already-real pulse/bridge/capture parent over its five PVT cases | Existing PVT runner, node probes, artifact identity, and PEX failure reports | A physical parent passes, or the first remaining failed physical predicate has a concrete circuit/model owner |
| 2 | Wi-Fi sampled-input boundary | Specify and screen one differential sampler with explicit charge-injection cancellation or bottom-plate timing; only lay it out after the schematic screen earns that work | Existing transient/PVT runner, hashes, and first-failure checker | The 0.25-V/320-MS/s/5-pF sampled-input interface passes extracted PVT, or the evidence forces a narrower frequency-plan decision |
| 3 | Shared only after repetition | Extract a helper only after it has removed the same failure mode in both tracks, or twice in one track | Small scripts/schemas with native files and commands retained as the source of truth | The helper demonstrably saves time or prevents an observed false claim without creating a second design flow |

The following are explicitly **not** current deliverables: a new language,
general topology synthesis, a universal optimizer/router, a GUI, a distributed
service, broad upstream tool surveys, or a Rust core. They become candidates
only when one of the two product gates above cannot proceed without them and a
smaller adapter or direct circuit experiment is demonstrably insufficient.

## 4. Input language and semantic kernel

The front end SHOULD retain the Aether concepts already exercised by the PCIe
contract. It MUST lower into the kernel below.

### 4.1 Quantities

A quantity has units and one value domain:

- exact scalar or trajectory;
- closed interval;
- finite enumerated set;
- characterized random variable;
- stochastic process; or
- unavailable value with a named acquisition obligation.

Unitless analog literals are invalid unless explicitly dimensionless. Corner
labels are selectors for model sets, not numeric probability distributions.

### 4.2 Conservation nodes

Connection adds equations: across quantities equalize and through quantities
sum to zero. Electrical, thermal, mechanical, optical, and future disciplines
use the same mechanism. Supply, ground, substrate, package, and thermal nodes
MUST remain connectable shared physics rather than testbench metadata.

### 4.3 Behaviors as relations

A component denotes a set of admissible trajectories over its ports and state.
The relation MAY be an equation, DAE, inclusion, SPICE subcircuit, S-parameter
network, table, RTL model, extracted netlist, or conservative abstraction.
Underspecification is legal and is required for assumptions and missing models.

### 4.4 Ensembles

An ensemble quantifies over process, voltage, temperature, mismatch, noise,
package, board, antenna, channel, activity, aging, and bounded model error.
Nested ensembles MUST distinguish correlated from independent variation.

### 4.5 Measures and estimators

A measure is a typed functional from trajectories or ensembles to quantities.
Its mathematical definition is separate from its estimators. Each estimator
MUST declare applicability, bias/error bounds, confidence calculation, runtime,
and required models.

Examples include BER, EVM, sensitivity, noise figure, gain, S-parameters,
phase noise, eye opening, settling margin, impedance, lock time, pulse width,
current, temperature, and EM margin.

### 4.6 Predicates, contracts, and refinement

Predicates include inequalities, structural constraints, and temporal logic
with quantitative robustness. Contracts contain assumptions and guarantees.
Parallel composition adds conservation equations and intersects behaviors.
Refinement requires the implementation to accept at least the contracted input
set and produce no behavior outside the guarantees.

Circular assume/guarantee relationships MUST be solved using a declared
conservative fixed-point method or by merging participants into one simulation
boundary. Loop breaking by an undocumented ideal source is forbidden.

### 4.7 Structural reflection

The language MUST quantify over hierarchy and structure, including every
matching group, sensitive node, device class, supply branch, port, calibration
control, and signal-path instance. This supports generated taps, guard rings,
probes, fill exclusions, DFT, and structural assertions without private tool
magic.

## 5. Intermediate representations

All representations MUST be versioned, serializable, inspectable, and stable
enough for semantic diffs.

### 5.1 Contract IR

Contains quantities, environments, measures, assumptions, guarantees,
objectives, model provenance, estimator policies, and allowed unresolved
obligations.

### 5.2 Circuit IR

Contains devices, parameters, connectivity, hierarchy, polarity, state,
matching groups, bias domains, control semantics, legal topology alternatives,
and parameter bounds. It is the single source for schematic SPICE, the LVS
reference, device manifests, and default internal probes.

### 5.3 Physical-intent IR

Contains placement relations, symmetry axes, common-centroid/interdigitation
patterns, dummy requirements, orientation, well/body domains, sensitive and
aggressor net classes, route constraints, current requirements, thermal intent,
fill intent, package interfaces, and allowed physical transformations.

### 5.4 Realized-physical IR

Contains exact geometry, hierarchy, ports, extracted connectivity, device
properties, parasitic networks, coupling, density, local supply paths, and a
mapping back to Circuit IR and Physical-intent IR objects.

### 5.5 Calibration IR

Contains physical controls, safe reset codes, legal transitions, monotonicity
or search assumptions, observables, search algorithms, stopping criteria,
retained state, startup order, fallback modes, and environment-to-passing-region
evidence.

### 5.6 Evidence IR

Contains claims, obligations, results, counterexamples, model scope,
dependencies, tool versions, hashes, commands, resource use, waivers, owners,
and expiration/invalidation rules.

### 5.7 Upstream representation policy

IRs are logical contracts, not necessarily new file formats. The first
implementation SHOULD map:

- Cascode linked artifacts and SPICE/device manifests into Circuit IR;
- OpenFASoC/gLayout/ALIGN constraints and outputs into Physical-intent and
  Realized-physical IR;
- CACE datasheets, campaign conditions, and results into Contract/Evidence IR;
- complete OpenADA request/result envelopes and native artifacts into Evidence
  IR; and
- existing Svalbard JSON checkpoints into the same claim graph without
  rewriting or weakening their historical meaning.

AEC MUST preserve each upstream artifact intact and add an adapter-versioned
semantic mapping. It MUST NOT create a second nominally authoritative copy of
the same circuit, measurement, or result merely to satisfy an internal schema.

## 6. Compiler pipeline

The default pipeline is:

1. Parse, type-check, and elaborate the top-level contract.
2. Resolve all required evidence, model provenance, and pinned upstream
   capability profiles.
3. Partition system budgets while preserving the composed guarantee.
4. Select a reviewed topology or elaborate the intended circuit.
5. Close DC operation, polarity, truth, startup, and basic stability.
6. Search schematic PVT and realizable calibration controls, using CACE when
   its campaign semantics cover the required measure and the existing focused
   runner otherwise.
7. Generate physical intent and candidate placement/routing through the
   smallest qualified backend or block-specific generator.
8. Run generator prechecks, DRC, property comparison, and pin-resolved LVS,
   retaining complete OpenADA evidence when a conforming profile exists.
9. Extract distributed RC/coupling and replay focused limiting cases.
10. Diagnose failures and iterate one declared mechanism at a time.
11. Run complete extracted environments and calibration searches.
12. Assemble real parent hierarchy and repeat physical/electrical closure.
13. Insert planned taps, decoupling, guard structures, and density fill.
14. Run post-fill extraction and required multi-physics/package analyses.
15. Check contract refinement and emit immutable artifacts and evidence.

Every stage MUST have explicit admission and exit predicates. Later evidence
cannot retroactively promote a failed earlier boundary without regenerating the
affected identity chain.

## 7. Physical synthesis requirements

### 7.1 Device generation

The compiler MUST use qualified PDK parameterized cells or reviewed generators.
It MUST know the legal parameter domain and derive contacts, straps, clearances,
and terminal access from realized geometry rather than stale coordinates.

### 7.2 Analog placement

The placer MUST understand:

- adjacency, symmetry, common centroid, interdigitation, and dummies;
- equal orientation, well-edge context, contact count, and thermal context;
- multifinger/shared-diffusion tradeoffs;
- short dynamic, regenerative, tail, RF, output, and high-impedance nodes;
- local load placement and compact current-return paths;
- guard rings, substrate/well taps, deep-well domains, and fill reservations;
- hierarchy-locality and package/pad proximity.

It MUST optimize extracted electrical cost, not bounding-box area alone.

### 7.3 Parasitic-aware routing

The router MUST distinguish differential, RF, regenerative, clock, bias,
large-signal aggressor, high-current, supply, substrate, and ordinary control
nets. Constraints include matched parasitic context, layer, length, via count,
coupling, shielding, resistance, current density, return path, and antenna rules.

Via stacks MUST occupy and be checked on every intermediate layer. The routing
database MUST reject unintended different-net conductor intersections before
DRC; DRC cannot infer intended connectivity.

### 7.4 Power, substrate, thermal, and fill

Power distribution is an analog signal path. The compiler MUST size rails and
via arrays from current envelopes, model local delivered voltage, and preserve
separate domains where required. It MUST realize explicit bodies, wells, taps,
guard rings, substrate collection, local decoupling, and thermal interfaces.

Fill MUST be planned before final closure. Post-fill DRC, LVS where applicable,
extraction, coupling, and performance replay are required.

### 7.5 RF and electromagnetic boundaries

For Wi-Fi and other distributed structures, the compiler MUST identify where
lumped PEX is insufficient. Pads, bond wires, package transitions, inductors,
transformers, antenna feeds, matching networks, filters, and transmission-line
routes MAY be delegated to an EM backend.

Each EM result MUST preserve stackup, materials, boundary conditions, ports,
meshing policy, frequency span, and solver identity. Imported networks MUST be
checked for passivity, causality, reciprocity where expected, convergence, and
sufficient bandwidth. The circuit and EM partition MUST prevent double-counting
the same parasitic geometry.

## 8. Verification engine

### 8.1 Boundary ladder

The verifier MUST name and track at least:

1. behavioral abstraction;
2. intended schematic;
3. schematic composition;
4. estimated-layout circuit;
5. extracted physical leaf;
6. routed extracted parent;
7. post-fill parent;
8. pad/package/board/channel or antenna composition;
9. provider-signoff candidate; and
10. measured silicon.

A claim at one boundary never implies a claim at a later boundary.

### 8.2 Multi-fidelity execution

The scheduler SHOULD use cheap models to reject candidates and full models to
qualify survivors. Cache keys MUST include every semantically relevant input,
including externally included DUTs, models, extraction, measurements, and tool
configuration.

OpenADA is the preferred native-operation evidence boundary where its pinned
profile covers the task. CACE is the preferred reusable characterization
campaign engine where its datasheet/testbench model expresses the contract.
AEC schedules and composes these operations; it does not reparse their native
logs into a competing pass/fail decision. Existing Svalbard runners remain
authoritative for analyses not yet covered, and SHOULD become conformance
fixtures for any replacement adapter.

Resource limits, timeouts, convergence status, and incomplete measures are
part of the result. A simulator exit without every required measure is a failed
or incomplete case, never a pass.

### 8.3 Required analysis classes

As applicable to the contract, the engine MUST orchestrate:

- operating point, DC transfer, AC, stability, and transient;
- periodic steady-state, phase noise, noise, and jitter;
- PVT, passive corners, load, common mode, and supply variation;
- mismatch/Monte Carlo only from approved statistical models;
- adversarial sweeps of interval-valued model uncertainty;
- package/channel/antenna S-parameter co-simulation;
- RF gain, noise figure, linearity, compression, EVM, spectral mask, LO leakage,
  image rejection, blocker, and sensitivity analyses;
- extracted PDN, simultaneous switching, substrate injection, and thermal;
- EM/IR, reliability, antenna, density/fill, and ERC checks;
- startup, sequencing, calibration, lock, loss, and recovery;
- fault injection and diagnostic/fallback survivability.

### 8.4 Estimator integrity

BER, EVM, rare-event, yield, and confidence claims MUST name the estimator and
its error/confidence contract. Extrapolated tails MUST be distinguishable from
brute-force samples and silicon counters. Independent solver/model correlation
is required for critical release measures when an appropriate independent path
exists.

## 9. Optimization and diagnosis

### 9.1 Search space

The optimizer MUST support continuous sizes, integer fingers, discrete device
and topology choices, placement/routing decisions, passive geometry, and
calibration codes. Hard constraints are never converted into undocumented soft
penalties.

Optimization SHOULD be hierarchical and surrogate-assisted. Full PEX is the
authority, but not every exploratory candidate requires full extraction.

### 9.2 Robust objectives

The primary feasibility objective is positive worst-case quantitative
robustness across the required ensemble. Area, power, nominal performance, and
design guardband are optimized only after hard feasibility, unless the user
explicitly requests a Pareto study.

The engine MUST report margin to control rails, contiguous passing-code regions,
and sensitivity to bounded unknowns. A single passing trim coordinate is not a
robust solution.

### 9.3 Failure localization

For a failed extracted case, the engine SHOULD automatically:

1. identify the first internal predicate or threshold that fails;
2. trace relevant signal, supply, and return paths through extraction;
3. compare schematic and PEX trajectories at aligned semantic nodes;
4. run bounded counterfactuals such as reduced route resistance, reduced
   parasitic capacitance, idealized local supply, or scaled device groups;
5. classify the failure as topology, polarity, headroom, drive/load, RC,
   coupling, supply delivery, pulse filtering, gain, noise, stability, model
   validity, or simulator incompleteness;
6. rank candidate remedies with predicted benefit, risk, and evidence level.

Counterfactual netlist edits are diagnostic only. A remedy qualifies only after
regenerated legal geometry, DRC, unique LVS, extraction, and contract replay.

## 10. Calibration synthesis

The compiler MUST treat calibration circuitry, controls, observables, storage,
and algorithms as part of the implementation.

For every calibration dimension it MUST establish:

- physical realizability and safe endpoints;
- code transfer and legal transition behavior;
- at least one observable correlated with the target margin;
- termination and bounded runtime of the search;
- a contiguous passing region with declared distance from rails;
- behavior under noise, mismatch, drift, and measurement error;
- retained code and reset/fallback behavior;
- a generated register map and controller implementation or executable
  reference algorithm.

Calibration selection SHOULD act on full-width states or slowly varying
parameters before a narrow time-domain event is formed. It MUST NOT assume that
a narrow pulse survives an unverified selector or restoration chain.

## 11. Hierarchy and system composition

The compiler MUST assemble actual physical parents. Parent generation includes
child origins, parent-owned signal routes, supply/substrate/thermal networks,
ports, bias distribution, reset, decoupling, guard structures, and fill intent.

Leaf evidence may discharge a parent obligation only when:

- the parent's assumptions are within the leaf's proven input/load domain;
- the exact simulated leaf bytes match the physical evidence identity;
- parent-owned interconnect and shared physics are modeled; and
- circular dependencies are conservatively resolved.

The system floorplan renderer MUST distinguish proposed, placed, routed,
extracted, and release-candidate boundaries visually and in metadata.

## 12. Model and uncertainty registry

Every model dimension MUST have one status:

- `provider_qualified`;
- `public_characterized`;
- `locally_measured`;
- `bounded_assumption`;
- `exploratory`; or
- `unavailable`.

The registry stores origin, version/hash, applicable devices/geometries,
frequency, bias, temperature, process, statistical meaning, known limitations,
and permitted claims.

When a required model is unavailable, compilation MUST either:

1. stop the affected release claim;
2. accept a user-approved conservative interval bound; or
3. emit a silicon characterization obligation with structures, ports,
   measurement plan, and the claims that measurement would unlock.

This is particularly important for GF180 2.4 GHz transistor behavior, passive
Q, substrate loss, pad/ESD bandwidth, package coupling, and PA reliability.

## 13. User interface

The minimum command interface SHOULD be:

```text
aec check      <contract>
aec elaborate  <contract> --emit-ir
aec explore    <contract> --boundary schematic
aec implement  <contract> --block <path>
aec diagnose   <result-or-claim>
aec compose    <contract> --parent <path>
aec verify     <contract> --boundary extracted-parent
aec evidence   <contract> --claim <name>
aec render     <contract> --boundary <name>
aec release    <contract> --candidate <id>
```

Every command MUST support a dry-run dependency/resource plan. Long runs MUST
have bounded CPU, memory, disk, and wall time, preserve partial diagnostics, and
avoid duplicating immutable large artifacts.

Human review remains a first-class stage. The UI SHOULD present semantic
schematics, parameter diffs, annotated layouts, matched-pair context, current
paths, coupling hot spots, waveform overlays, margin tables, calibration maps,
counterexamples, and claim dependency graphs.

## 14. Outputs

Depending on the requested boundary, the compiler emits:

- typed/elaborated contract and all IRs;
- schematic and extracted SPICE plus RF network models;
- parameterized physical source, GDS/OASIS, and rendered layout;
- DRC, LVS, property, extraction, ERC, fill, EM/IR, and reliability reports;
- simulation decks, raw outputs, checked summaries, and counterexamples;
- behavioral twins whose valid domains derive from transistor-level evidence;
- calibration controller, firmware/reference algorithm, code tables, register
  map, safe reset image, and startup sequence;
- floorplan, power intent, pad/package/board interface, and test structures;
- model/uncertainty manifest and unresolved characterization obligations;
- proof/claim manifest, exact reproduction commands, and artifact hashes.

Release artifacts MUST be immutable and content addressed. Regeneration that
changes bytes creates a new candidate even if semantic comparison finds no
known difference.

## 15. Application profiles

### 15.1 PCIe profile

The PCIe profile requires time-domain differential signaling, calibrated pulse
generation, samplers, CML/CMOS boundaries, PLL/CDR/phase interpolation,
termination, transmitter, shared bias, electrical idle, receiver detect, pads,
package/channel, and simultaneous TX/RX aggression.

Its first hard benchmark is the compact dual-edge pulse generator. Given its
intended circuit and contract, the compiler must preserve the exact extracted
TT pass, identify the FF/hot WRITE swing miss and SS/hot pulse-filtering failure,
and propose changes before local interval formation rather than blindly
enlarging the final driver.

Its first hierarchy benchmark is a real routed parent containing recovered-clock
converter, pulse generator, and regenerative capture gates with shared power,
substrate, bias, and extracted interconnect.

### 15.2 Wi-Fi profile

The initial Wi-Fi profile targets a crystal-referenced 2.4 GHz 802.11b SoC with
external passive matching, balun/filter, and supply decoupling. It requires RF
and baseband circuits, ADC/DAC interfaces, PLL/quadrature LO, PA, LNA, mixers,
filters/gain, antenna/package networks, digital calibration, and PHY/MAC
behavioral composition.

The compiler must co-optimize link-level sensitivity and transmit EVM/power
without pretending unavailable GF180 RF model accuracy is known. Early outputs
must include de-embedding, open/short/thru/load, transistor, passive, LNA, mixer,
VCO, and PA test structures plus external-LO and external-I/Q fallback paths.

## 16. Feasibility and research boundary

There is a credible path, but the deliverable is a progressively more capable
closure assistant rather than a complete solver for arbitrary analog design.

| Missing capability | Pragmatic attainable result | Classification |
|---|---|---|
| Whole-system contract and budget partition | Executable top-level constraints plus conservative human/LLM-proposed budgets checked by numerical search | Useful now; automatic partition is bounded research |
| Conservation-node and ensemble semantics | Reuse established across/through equations and explicit enumerated/interval/statistical environments | Straightforward engineering |
| Circuit/layout/calibration IR identity | Hash-joined upstream artifacts, semantic mappings, and invalidation edges | Straightforward engineering; highest priority |
| Joint topology/sizing/layout/control optimization | Hierarchical search: reviewed topology proposals, numerical sizing/control search, backend layout, exact verification | Useful with no global-optimum claim; continuing research |
| Automatic PEX failure localization | Semantic node maps, first-failure probes, RC counterfactuals, and ranked hypotheses | High-confidence near-term feature |
| Real routed-parent composition | Explicit macro placement, parent-owned routing, shared PDN/substrate, DRC/LVS/PEX | Existing tools prove feasibility; application engineering remains hard |
| Calibration hardware and algorithm synthesis | Generate searches/controllers for user-declared controls and observables; later propose new trim structures | Algorithm generation is near-term; hardware invention is research |
| RF/EM partitioning | Explicit reviewed ports, EM jobs, network qualification, and non-double-counted circuit import | Established engineering with process/model dependencies |
| Model validity and unavailable physics | Machine-enforced validity domains, bounds, stopped claims, and test-structure obligations | Straightforward tracking; missing physics itself cannot be compiled away |
| Claim refinement through package/system | Conservative assume/guarantee checks and merged simulation when abstraction is unsafe | Useful bounded calculus; complete nonlinear/stochastic proof is research |

The project MUST prefer a conservative incomplete answer over a broad unsound
one. `Unknown because RF transistor data is unavailable` is a successful tool
result when it prevents a false Wi-Fi claim and emits the exact characterization
structure needed to proceed.

## 17. Product-driven implementation plan

This is the authoritative active roadmap. Work elsewhere in this document is
permitted only if it is the smallest way to retire one of the gates below. The
decision order is always: make the direct circuit/layout experiment; add a thin
checker or adapter only when that experiment exposes repeated manual work or an
evidence error; then generalize only after the same need recurs in a second real
block or product.

### Slice 0: no standalone tool project

There is no proactive upstream-qualification milestone. Do not evaluate,
integrate, pin, wrap, fork, or port OpenADA, Cascode, CACE, OpenFASoC/gLayout,
or ALIGN merely to prepare for a future compiler.

Use one only when a named next PCIe or Wi-Fi gate cannot be closed with the
existing native flow. In that event, adopt the smallest capability that removes
the blocker, preserve the native source/artifacts as authoritative, exercise it
on that exact product case, and retain a one-page adoption note with the command
and result. Reject the adoption if it creates a second source of truth or costs
more than the direct product experiment it replaces.

Exit criterion: none. This section must never delay a circuit, layout, model,
or measurement decision in Slices 1 or 2.

### Slice 1: finish the PCIe clock/capture boundary

- Keep the current SPICE/layout generators and focused PEX runners working.
- Automate only the repeated work already observed: exact input identity,
  environment/profile scheduling, internal-stage measurements, first failing
  threshold, RC/supply counterfactuals, and concise comparison of candidates.

Execution order is deliberately narrow:

1. Make the pulse leaf's corner control physically effective at a full-swing
   state before the narrow interval is formed. The present `SEL0..SEL3` pins
   only terminate in physical load anchors, so static code sweeps are not a
   calibration result. A physical `SEL3` current-starved end-delay probe did
   change a real internal state but still produced only 50/62 mV WRITE at
   SS/hot; it is rejected and must not be enlarged. A subsequent full-swing
   `HCLK`-derived SEL2/SEL3 start/end configuration did create the required
   schematic `WPN` low crossing, and was zero-DRC/unique-LVS/full-RC
   extracted, but only passed TT: its selected SS/hot `WPN` stopped at
   272 mV and WRITE disappeared. It too is rejected. A subsequent 40-case
   necessary screen moved the selector entirely to full-swing HCLK end states
   before the local detector; it restored WRITE/WPN rails but achieved 0/5
   environment coverage because its detector interval remained 179--423 ps.
   Its closest code needs a 45--80 ps shorter full-state separation, so it is
   [rejected before layout](../../ip/blocks/analog/wireline_serdes/clock_pulse_hclk_window_probe/README.md),
   not a calibration claim. The first product-specific closure manifest then
   made candidate identity, code identity, environments, predicates and
   semantic START/END bindings executable. It retained a 4/5 restored-START
   result and then proved that no single common delay meets both FF/cold and
   SS/hot epoch bounds. A coherent one-bit fast/short versus delayed/long epoch
   family now covers 5/5 environments in this necessary schematic screen, with
   selected 108.05--192.00 ps WRITE widths and 137.89--647.22 ps proxy delays.
   Full SENSE/WRITE composition then rejected the one-bit architecture before
   layout. Final-edge SENSE control reached 4/5 and proved that FF/cold requires
   a long epoch while FF/hot needs a short epoch with the same interval code.
   The resulting restored two-bit hierarchy now passes both its 80-case leaf
   screen and 80-case composed SENSE/WRITE screen. The selected extra-2x
   candidate has at least 26.35 ps timing margin and at most 29.75 mA current.
   Physical implementation then separated SENSE assist, WRITE interval, and
   WRITE epoch into three controls and retained 5/5 schematic coverage. Its
   current 216-device layout is clean DRC, unique LVS, and full-RC extracted,
   but targeted TT/SS-hot PEX remains 0/2. Schema-v2 semantic paths now show
   TT rail degradation at selected `HBASE`/`START` and SS/hot interval-0
   degradation through `E0`/`EMUX` until odd-phase `END` stops crossing.
   Baseline-checked R/C counterfactuals and eight bounded schematic revisions
   reject local routing, taper depth, matched isolation, and final-driver
   strength as independent remedies. A retimed source now selects only
   full-duty epoch states, restores them into a `T0/T1/T2` chain, and preserves
   5/5 schematic coverage. Its 220-device layout is clean DRC/unique LVS and
   extracts to 5,494R/4,069C, but remains 0/2 at TT/SS-hot. Contract-derived
   localization proves that the full-swing states survive through `WIN/WPN`
   and that taper capacitance dominates the final WRITE collapse. Four-stage,
   lean six-stage, and simple NOR-latch output branches fail schematic gates.
   The bounded next step is therefore to transport independent full-duty
   set/reset events into a contention-free output state machine, or merge that
   state into the capture cell. Preserve the three controls, include an
   observable correlated with timing/drive margin and safe code endpoints, and
   use a bounded selection procedure. Do not build a general calibration
   synthesizer.
2. Use that one real control to repair the two exact extracted failures in the
   already physical pulse-to-bridge-to-direct-regenerative-capture boundary:
   FF/cold bridge-drive margin and SS/hot pulse reset. Preserve the current
   three passing corners and reject a candidate promptly when its TT replay or
   a known rail/reset predicate regresses. The rejected fixed 12-um final-NMOS
   enlargement is diagnostic evidence, not a candidate to revive. The newer
   full-duty event/bridge/capture boundary has since earned one TT exact-PEX
   pass. Its first intermediate single-inversion/NOR/isolation alternative is
   clean DRC, unique LVS, and 5,200R/3,863C extracted but passes 0/8 targeted
   cases: isolation delay loses TT and its roughly 1-V SS/hot detector pulse is
   not recognized. A lower-trip isolator covers only FF/cold schematically and
   is rejected before layout. A subsequent active-low NAND state removes two
   restoration stages, passes 15/40 schematic cases over 5/5 environments,
   and produces a 192-device, zero-DRC/unique-LVS, 4,886R/3,577C macro. It
   retains one TT exact-PEX pass and moves SS/hot failure to loaded `SB1` after
   a real `HSN` transition. Strength rebalance loses TT BOOST rail; a split
   BOOST path loses SS/hot schematically. This closes local
   delay/inverter/load-partition work; the next candidate must place the state
   in a contention-free regenerative element or the capture cell.
3. For each promising circuit revision, run the existing short sequence only:
   schematic measurement of the changed semantic nodes, regenerated legal
   layout, DRC, unique LVS, exact TT PEX, then the five-corner composed PEX
   screen. Record source/layout/PEX/testbench hashes and the first failed
   predicate. A profile scheduler or node-probe helper is allowed only if it
   removes this repeated work.
4. After the boundary passes its declared five-corner screen, route the actual
   converter + pulse + bridge + regenerative-capture parent with parent-owned
   signal, supply, substrate, and bias routes, then run DRC, unique LVS, PEX
   and the composed capture contract. PRBS/channel and CDR-loop work remain
   downstream of this gate; they must not obscure it.

OpenADA is imported only where it can carry a result unchanged; the checked
native result format remains authoritative elsewhere.

Exit criterion: the PCIe clock/capture parent is physically real and either
passes its exact declared environments with a realizable control/selection
mechanism or has one localized blocker that needs new device/model authority,
not more manual log archaeology.

### Slice 2: build the Wi-Fi RF risk macro

Current state: the first active macro is the routed 16-finger NFET LNA core at
[`ip/blocks/analog/wifi_80211b/rf_lna`](../../ip/blocks/analog/wifi_80211b/rf_lna).
Its current native flow has clean DRC and LVS and a full-RC PEX AC screen at
2.4 GHz over five public PVT environments using one fixed **external** 1.5 V
bias. A separate five-PVT narrowband noise screen at the same bias records a
worst bench-relative estimate of 10.283 dB. A second, independently routed
two-bank NFET switching-mixer core is DRC/LVS/PEX checked and produces a finite
100 MHz differential IF component across five PVT environments from an external
2.3 GHz complementary LO and a 2.4 GHz external RF source; the weakest screen
is -0.664 dB conversion. The first routed LNA/mixer parent is also zero-DRC,
uniquely LVS-matched and 219R/168C full-RC extracted; it passes the same five
PVT environments with -3.402 dB worst conversion through its parent-owned RF
route. These establish only bounded feasibility boundaries; those numbers do
not establish qualified RF noise, matching, linearity, package/antenna EM, an
on-die bias, or an 802.11 receiver. The next steps below are product gates, not
tool milestones.

The first die-side open/short/thru/load coupon at
[`ip/blocks/analog/wifi_80211b/rf_ostl_coupon`](../../ip/blocks/analog/wifi_80211b/rf_ostl_coupon)
is also zero-DRC, uniquely LVS-matched, and 2R/4C full-RC extracted. Its source
and measurement plan preserve the PDK's floating poly-body condition and name
the required 0.1--6 GHz wafer/OTSC measurements. It is a test artifact that
closes no RF-model-validity claim until measured network data, a reviewed
probe/pad/package boundary, and passivity/causality checks are available.

The companion active-device coupon at
[`ip/blocks/analog/wifi_80211b/rf_nfet_array_coupon`](../../ip/blocks/analog/wifi_80211b/rf_nfet_array_coupon)
is a 0-DRC, uniquely LVS-matched, 390R/72C full-RC extracted replica of the
LNA's exact sixteen 4-um/0.28-um NFET fingers. It deliberately captures the
array's device identity and measurement geometry, while reserving all RF-model,
noise, `fT`/`fMAX`, linearity, pad and package claims for a calibrated
bias-dependent wafer campaign plus the OSTL residual check.

The routed receive parent also now has a full-RC PEX fixed two-tone diagnostic
at the same five public PVT cases: a 1-mV 2.400-GHz desired tone and a 100-mV
2.425-GHz aggressor share the external 50-ohm source and a 2.300-GHz LO. The
desired 100-MHz component changes by no less than +0.065 dB, but the unfiltered
125-MHz aggressor component is no less than 39.872 dB larger. This is useful
failure localization, but it changes the next task: 100 and 125 MHz are too
close for a low-order on-die RC stage to remove tens of dB of aggression while
preserving a wide 802.11b channel. The selected next receiver boundary is a
real-IF ADC/DSP headroom-and-channel-filter path; a normal broad Wi-Fi RF
preselector remains required for out-of-band/package control but cannot claim
this 25 MHz separation. The product handoff is
[`channel_selectivity_boundary.yaml`](../../projects/wifi_nbiot_radio/analog/channel_selectivity_boundary.yaml)
and its byte-bound PEX input budget is
[`adc_dsp_selectivity_plan.json`](../../ip/blocks/analog/wifi_80211b/rf_rx_external_lo_parent/adc_dsp_selectivity_plan.json).

Execution order is likewise tied to the next receiver claim:

1. The receiver decision is frozen as a real-IF ADC/DSP path because a normal
   wide Wi-Fi RF preselector cannot honestly claim 25 MHz adjacent-tone
   separation. Use the existing PEX two-tone measurements only to hold the
   ADC full-scale/ENOB/sample-rate and digital-filter requirements accountable.
   The former 0.25-V differential-peak, 320-MS/s **sampled-input interface**
   with a 5-pF-per-leg future converter load is rejected before another switch
   layout: its 125-C six-sigma differential kT/C noise is 281 uV, above the
   30.5-uV quarter-LSB allocation before switching error. The first 0-DRC,
   unique-LVS 113R/86C NMOS-only
   implementation now completes all five full-RC corners but is explicitly
   rejected: its 177.891-mV worst aperture/hold error is 5,829 times the
   allocation, and its schematic baseline fails likewise. Do not tune it.
   A complementary-clocked simple transmission gate was then screened before
   layout and rejected: its best bounded high-IF sizing retains 79.206 mV worst
   aperture/hold error, while a deliberately easier 10-MHz/80-MS/s screen still
   retains 17.003 mV.  The next candidate must first bind an extracted IF
   driver and a hold capacitor meeting the thermal-only floor and acquisition
   resistance in `sampler_thermal_settling_budget.json`; then it must state its
   explicit charge-injection-cancellation or bottom-plate-sampling mechanism
   and control timing. Only then may it earn an extracted PVT screen for
   settling, hold error, clock feedthrough and input loading. A five-corner
   100-MHz push-pull output-stage coupon now shows that a bare inverter bank
   reaches 4.385 ohm even at 20-mm effective NMOS width in SS/hot (about
   232-mm linear-width extrapolation to the 0.379-ohm target). That bank's
   measured small-signal common gate load is already 78.009 pF at its DC trip
   point (903.394 pF under the same width extrapolation). The IF driver must
   therefore be a closed-loop multistage power buffer whose gate-drive
   distribution, power, stability, common mode, and linearity are explicit;
   do not lay out a switch-only solution. The thermal-floor 424.974-pF leg
   also makes the 1.45-ns, 0.25-LSB settling requirement a 989.056-MHz
   single-pole bandwidth and 36.636-mA full-scale-step-current requirement
   per leg before additional error sources. A ten-case raw-device
   drain-current/gate-current crossing screen does clear its deliberately
   limited necessary speed gate: its worst SS/hot PMOS is 8.037 GHz, or 8.126
   times the required bandwidth. It neither solves the 903-pF extrapolated
   output-bank gate load nor proves a feedback loop. The first actual feedback
   schematic, a five-stage inverter chain with equal direct resistive feedback,
   now fails every PVT step case (239.354 mV best error, 1.809 V common-mode
   error, and 3.156 A maximum average draw). It is rejected rather than tuned.
   The successor needs a compensated differential error amplifier, explicit
   CMFB, and current-limited class-AB or source-follower output stage with
   gate distribution. A follow-up ideal-bias source-follower primitive does
   pass 0.328 ohm worst output impedance at 20-mm effective NMOS width, but
   its one fixed all-corner bias draws up to 0.991 A per output and leaves
   155.777 mV common-mode error. It is a usable output-stage direction, not a
   driver solution. Do not reuse the
   PCIe CML error slicer: its extracted 40--150-mV window is hundreds of times
   coarser than the roughly 122-uV 12-bit code step. A failed sampler may justify
   a simplified frequency plan; it does not justify starting a generic ADC
   framework. Only after the interface passes should a bounded converter and
   fixed-point filter be built and composed. This is a product architecture
   decision, not an opportunity to build an RF optimizer or to call the current
   scalar budget an implemented receiver.
2. Preserve the OSTL and active-NFET coupons as tapeout/measurement obligations.
   When calibrated wafer data exists, bind the exact de-embedded S-parameters,
   noise and bias range into the model registry before promoting any RF gain,
   NF, linearity, matching, `fT`, or `fMAX` claim.
3. Add EM only at a defined distributed boundary--pads, package, antenna/match,
   inductors or long RF routing--and import a reviewed network without
   double-counting its parasitics. Do not run generic EM campaigns before a
   geometry and a decision they can change are available.
4. Add only one thin S-parameter import/validity check if the chosen network
   cannot be bound safely with the native deck. Use CACE for campaigns it
   directly represents and a qualified layout backend only if the block-specific
   generator cannot produce legal geometry. DRC/LVS/PEX/EM evidence remains
   authoritative regardless of the generator.

Exit criterion: the macro has a reproducible evidence package that either
supports the next integrated Wi-Fi receiver step or identifies the specific
provider/silicon characterization missing from GF180.

### Slice 3: extract only delivery-critical shared utilities

- Keep only utilities that are already on the direct delivery path: artifact
  identity/invalidation, resource-bounded PVT runners, declared measurements,
  first-failure reports, and model-validity labels.  They must run in the next
  PCIe or Wi-Fi experiment, with native source and artifacts still authoritative.
- Extract a shared helper after it prevents the same false claim or removes the
  same manual burden twice.  A one-off helper is allowed only when it is smaller
  than repeating the immediate product experiment and is deleted or absorbed if
  that experiment makes it unnecessary.
- Do not begin Rust, upstream qualification, generalized layout generation,
  calibration synthesis, or optimization work as a roadmap item.  Each becomes
  eligible only after a named chip gate cannot move without it and a smaller
  direct circuit/layout experiment is demonstrably insufficient.

Exit criterion: the shared layer demonstrably reduces elapsed engineering work
or prevents a previously observed false claim in both projects.

### Immediate execution policy

The PCIe clock/capture bench now removes ideal timing sources at its immediate
boundary. Its selected full-duty event/bridge schematic covers 5/5 public-model
environments, the generated macro is zero-DRC/unique-LVS/full-RC extracted,
and targeted exact PEX passes TT but not SS/hot; the latter is localized to an
over-delayed explicit SENSE detector state. Bounded intermediate-delay and
low-trip alternatives were rejected. The selected active-low NAND state
retains the TT pass with 16 fewer devices and advances SS/hot failure to loaded
`SB1`; strength and split-load followups do not improve coverage. The Wi-Fi
receiver has a byte-bound
ADC/DSP selectivity architecture, but its former 5-pF sampled-input boundary
is thermally infeasible for the stated 12-bit allocation, and both its physical
NMOS-only sampler and schematic simple transmission-gate screen are rejected.
An extracted IF driver/hold-capacitor boundary must now exist before a
bottom-plate or charge-cancellation layout is authorized. Until those two
product gates advance, the
repository is **not** building a general analog compiler.  The allowed shared
work is limited to an already-encountered defect in both products:

- source/layout/PEX/testbench/result identity and invalidation;
- resource-bounded, resumable PVT or characterization runners;
- semantic measurements and first-failure localization; and
- model-validity labels, measurement obligations, and parent-versus-leaf claim
  boundaries.

All other proposals need a one-line answer to: “Which active PCIe or Wi-Fi
gate does this retire before the next circuit experiment?” If there is no
answer, record it as deferred research rather than implementing it.

### Deferred until demanded by a chip milestone

- unrestricted natural-language or image-to-topology synthesis;
- a comprehensive new analog language implementation;
- distributed/cloud scheduling beyond one bounded workstation;
- a custom GUI or waveform database;
- a general-purpose analog router replacing all upstream backends;
- global-optimal joint analog synthesis; and
- formal proof over arbitrary nonlinear stochastic systems.

## 18. Acceptance criteria

The compiler is useful when all of the following are true:

1. A circuit and its layout/LVS/testbench cannot silently disagree.
2. A parameter change invalidates exactly the dependent evidence.
3. The system can generate a legal extracted candidate without hand-editing
   emitted geometry.
4. A failed waveform is localized to an actionable mechanism automatically.
5. Calibration results describe contiguous realizable regions and executable
   searches, not ideal-source coordinates.
6. A physical leaf and a physical parent are unambiguously different claims.
7. RF/EM and lumped-circuit domains meet at explicit, non-double-counted ports.
8. Missing fabrication data produces bounded assumptions or characterization
   obligations, never invented confidence.
9. PCIe and Wi-Fi use compatible contract/evidence semantics, artifact identity,
   and resource controls while remaining free to select different qualified
   physical and analysis backends.
10. A reviewer can reproduce every promoted claim from immutable inputs and can
    inspect every failed or waived obligation.
11. The PCIe clock/capture parent and Wi-Fi RF risk macro advance measurably
    sooner or with fewer repeated errors than they would under the retained
    manual flows.
12. Any compiler feature that fails to demonstrate such value can be removed
    without invalidating the native design sources or their evidence.

The success metric is not the number of compiler features or layouts generated.
It is delivery of physically composed PCIe and Wi-Fi silicon candidates with
less repeated human work, trustworthy evidence, and clearly bounded uncertainty.
