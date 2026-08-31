# Analog Evidence Compiler specification

- Status: proposed implementation specification
- Date: 2026-08-31
- Working name: `aec`
- Initial process target: GF180MCU
- Initial applications: PCIe Gen1 wireline PHY and 2.4 GHz Wi-Fi radio
- Delivery strategy: integration-first over reviewed open-source components

## 1. Purpose

Build a compiler and verifier that turns an intended transistor/passive circuit,
physical constraints, and a system-level behavioral contract into:

1. a manufacturable physical implementation;
2. calibration and test mechanisms needed to make that implementation robust;
3. executable verification across every declared environment; and
4. a content-addressed evidence package stating exactly what is proven, failed,
   assumed, bounded, or unavailable.

The compiler is successful only when it shortens the complete circuit-to-evidence
loop. Automatic placement without extracted verification is not sufficient, and
a large simulation launcher without physical synthesis is not sufficient.
Its success metrics are PCIe and Wi-Fi closure milestones, not language
features, supported operation counts, generated-layout counts, or framework
completeness. AEC work that does not unblock an active chip claim is deferred.

The existing whole-interface Aether source at
`projects/pcie_gen1_endpoint/analog/pcie_gen1_x1.aether` is an example front-end
contract. This specification defines the system required to execute such a
contract. The front-end syntax may evolve; its semantics and evidence rules are
the stable interface.

AEC is not a ground-up replacement for the open analog ecosystem. Its primary
job is to supply the missing system semantics, identity, optimization,
calibration, hierarchy, and claim-refinement layer while adapting reviewed
upstream projects for circuit representation, characterization, physical
synthesis, and deterministic EDA evidence.

Normative terms **MUST**, **SHOULD**, and **MAY** describe required, preferred,
and optional behavior respectively.

## 2. Product boundary

### 2.1 In scope

The compiler MUST support:

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

### 2.2 Not initially in scope

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

### Slice 0: thin upstream evaluation

- Pin OpenADA, Cascode, CACE, OpenFASoC/gLayout, and ALIGN revisions in an
  evaluation manifest; do not vendor or fork them yet.
- Run one tiny public fixture for each claimed capability and record what is
  implemented versus roadmap-only.
- Map one existing Svalbard pulse result into an OpenADA-compatible or AEC
  wrapper envelope without changing its source bytes or verdict.
- Test whether Cascode can losslessly represent one existing transistor leaf and
  bench. Stop the language integration if it creates a second source of truth.

Exit criterion: a short adoption report chooses, rejects, or defers each
upstream with a reproducing command and a concrete PCIe/Wi-Fi use. No production
design work waits for this report.

### Slice 1: finish the PCIe clock/capture boundary

- Keep the current SPICE/layout generators and focused PEX runners working.
- Automate only the repeated work already observed: exact input identity,
  environment/profile scheduling, internal-stage measurements, first failing
  threshold, RC/supply counterfactuals, and concise comparison of candidates.
- Use that loop to close the pulse generator over the full required PVT/profile
  set rather than building a general optimizer first.
- Generate the actual converter + pulse + regenerative-capture parent with
  parent-owned signal, supply, substrate, and bias routes.
- Run DRC, unique LVS, PEX, and the composed capture contract. Import operation
  evidence through OpenADA where supported and retain the existing checked
  result format elsewhere.

Exit criterion: the PCIe parent is physically real and either passes its exact
declared environments or has a machine-localized blocker that requires new
device/model authority rather than more manual log archaeology.

### Slice 2: build the Wi-Fi RF risk macro

- Freeze a modest 2.4 GHz 802.11b front-end boundary and external passive,
  crystal, package, and antenna assumptions.
- Build only the RF characterization structures and first active macro needed
  to answer GF180 feasibility: transistor/de-embedding structures plus a
  probeable LNA/mixer or VCO path with external-LO/IQ fallback.
- Use CACE for ordinary PVT/Monte Carlo campaigns it can express; use explicit
  RF/EM runners for S-parameters, noise, linearity, passivity, causality, and
  matching-network composition.
- Generate layout with the smallest qualified choice among gLayout/OpenFASoC,
  ALIGN, and a block-specific generator. Exact DRC/LVS/PEX/EM evidence remains
  authoritative regardless of generator.

Exit criterion: the macro has a reproducible evidence package that either
supports the next integrated Wi-Fi receiver step or identifies the specific
provider/silicon characterization missing from GF180.

### Slice 3: extract only proven shared tooling

- Compare the two completed vertical slices and promote only mechanisms used by
  both: artifact identity, resource-bounded parallel jobs, model validity,
  semantic measurement bindings, claim dependencies, and physical-boundary
  labels.
- Introduce a Rust core only for a demonstrated correctness, concurrency,
  geometry, or scale bottleneck. Keep Python orchestration otherwise.
- Upstream generally useful operation profiles, fixtures, generators, or fixes
  when their project accepts the required semantics.
- Add calibration-controller generation, broader optimization, and contract
  refinement incrementally as the next PCIe or Wi-Fi block demands them.

Exit criterion: the shared layer demonstrably reduces elapsed engineering work
or prevents a previously observed false claim in both projects.

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
