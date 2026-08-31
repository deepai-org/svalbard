# Analog Evidence Compiler specification

- Status: proposed implementation specification
- Date: 2026-08-31
- Working name: `aec`
- Initial process target: GF180MCU
- Initial applications: PCIe Gen1 wireline PHY and 2.4 GHz Wi-Fi radio

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

The existing whole-interface Aether source at
`projects/pcie_gen1_endpoint/analog/pcie_gen1_x1.aether` is an example front-end
contract. This specification defines the system required to execute such a
contract. The front-end syntax may evolve; its semantics and evidence rules are
the stable interface.

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

## 6. Compiler pipeline

The default pipeline is:

1. Parse, type-check, and elaborate the top-level contract.
2. Resolve all required evidence and model provenance.
3. Partition system budgets while preserving the composed guarantee.
4. Select a reviewed topology or elaborate the intended circuit.
5. Close DC operation, polarity, truth, startup, and basic stability.
6. Search schematic PVT and realizable calibration controls.
7. Generate physical intent and candidate placement/routing.
8. Run generator prechecks, DRC, property comparison, and pin-resolved LVS.
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

## 16. Implementation plan

### Phase 0: evidence runner

- Implement Contract IR and Evidence IR.
- Wrap existing SPICE, Magic, Netgen, extraction, KLayout rendering, and current
  simulation scripts behind deterministic adapters.
- Add content-addressed inputs, result schemas, resource limits, and claim
  invalidation.
- Ingest existing PCIe leaf evidence without changing its claims.

Exit criterion: one command reproduces and audits an existing physical leaf
checkpoint, or explains every identity gap preventing reproduction.

### Phase 1: circuit and diagnostic core

- Implement Circuit IR and generated schematic/LVS/device manifests.
- Implement typed measures, grouped environment/calibration search, semantic
  internal probes, and extracted RC counterfactual diagnosis.
- Use the PCIe pulse macro as the primary benchmark.

Exit criterion: the tool classifies the retained TT, FF/hot, and SS/hot pulse
results correctly and produces a useful ranked diagnosis without manual log
parsing.

### Phase 2: constrained physical synthesis

- Implement Physical-intent IR, matched placement primitives, device access,
  net-aware routing, supplies, taps/guards, and layout semantic checks.
- First support inverter chains, differential pairs, CML stages, current mirrors,
  resistor/capacitor banks, and simple RF transconductors.

Exit criterion: generated variants are DRC clean, uniquely pin-resolved LVS
matched, property checked, extractable, and deterministically mapped to Circuit
IR across a legal parameter sweep.

### Phase 3: calibration and parent assembly

- Implement Calibration IR and controller/reference-algorithm generation.
- Implement physical hierarchy, parent-owned routes, shared power/substrate,
  composed evidence, and boundary-aware floorplan rendering.

Exit criterion: converter + pulse + capture is one routed, DRC/LVS/PEX parent,
and every passing environment has a realizable calibration path and observable.

### Phase 4: RF/EM extension

- Add S-parameter quantities and measures, RF analyses, EM partitioning,
  passivity/causality checks, package/board matching networks, and model-domain
  enforcement.
- Generate Wi-Fi risk-macro test structures and fallback interfaces.

Exit criterion: an LNA/mixer/PLL or PA risk macro has a complete, honest evidence
package whose unsupported RF assumptions are machine-visible and cannot be
promoted to a product claim.

### Phase 5: joint system optimization

- Add contract-driven budget partition and hierarchical robust optimization.
- Add behavioral-twin generation with checked validity domains.
- Close progressively larger PCIe and Wi-Fi composed boundaries.

Exit criterion: the optimizer makes and records at least one legitimate
cross-block trade that improves a top-level guarantee and is confirmed in a
regenerated extracted physical parent.

## 17. Acceptance criteria

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
9. PCIe and Wi-Fi use the same kernel, evidence store, physical engine, and
   verification scheduler; application-specific behavior lives in contracts,
   measures, topology libraries, and model bundles.
10. A reviewer can reproduce every promoted claim from immutable inputs and can
    inspect every failed or waived obligation.

The long-term success metric is not the number of layouts generated. It is the
reduction in human time from a system contract to a physically composed,
calibratable design with trustworthy evidence and clearly bounded uncertainty.
