# Analog design and verification workflow

Complete the whole-chip mathematical model, then the connected transistor and
passive schematic, then layout/extraction with the same requirements. The
parametric pad first pass is the authorized scoped exception: its circuits and
layouts may proceed while whole-chip behavioral gaps remain. Transmission-line
geometry and shielding follow at layout. Preserve the full programmable RF/wired
companion scope.

## Primitive-library architecture for schematic and layout work

Build the programmable transceiver's analog
implementation on a small, customizable, simulation-characterized library of
six primitive families: **NMOS, PMOS, resistor, capacitor, diode/junction, and
interconnect**. These are families, not six universal device models. Each
process-supported device flavor or passive construction retains its own model
and legal geometry range. Add a supported bipolar device or inductor only if
an actual circuit requires it; do not force an unsuitable transistor substitute.

Use the pinned public GF180 PDK as the device-model and geometry foundation.
Reuse its models rather than inventing replacement device physics. Separate
PDK predictions, our simulation evidence, and uncharacterized physical behavior;
repeated simulation cannot supply missing foundry or package data.

The implementation hierarchy is:

```text
Pinned PDK models and legal geometries
  -> parameterized primitive families and characterization records
  -> reusable, expandable transistor circuit generators
  -> connected full-chip transistor schematic
  -> layout generated from the same instance parameters
  -> extraction and rerun of the same circuit acceptance tests
```

For each primitive, retain:

- Named terminals, units, model identity, supported parameters and validity
  bounds. Parameters include transistor width/length/fingers/multiplicity,
  passive dimensions and construction, and interconnect layer/geometry.
  A requested resistance or capacitance must resolve to a realizable geometry.
- Reproducible characterization fixtures and compact results over the needed
  geometry, bias, frequency, loading, temperature and supply ranges. Prioritize
  the chip's agreed narrow operating window and explicitly bounded uncertainty.
- Relevant current/voltage behavior, small-signal response, noise, leakage and
  parasitics where the public models support them. Record unavailable effects
  and bounds explicitly; do not claim measured accuracy from model agreement.
- Both a SPICE implementation and, where useful, a faster mathematical view
  with checked approximation error and applicability limits. Cache results by
  device parameters, PDK revision, simulator/settings and fixture revision.
- A future layout view using the same instance parameters, with connectivity,
  matching and placement constraints. Interconnect estimates before layout
  become geometry-specific extracted resistance/capacitance/coupling, and
  inductance where required, after routing.

Current mirrors, differential pairs, switches, latches, filters, converters and
clock circuits are compositions of these primitives, not opaque substitutes for
them. Keep their transistor connections inspectable. Distinguish generation-time
sizing from runtime programmability: programmable gain, bias, tuning or routing
requires explicit switches, arrays and control circuitry in the schematic.

Build and characterize the primitive configurations needed by the highest-risk
circuits first; an exhaustive library over every legal geometry is not a
prerequisite. Consolidate existing circuits and fixtures into this hierarchy
incrementally, preserving useful evidence rather than restarting working blocks.
Device characterization does not replace assembled-block and full-chip tests
for startup, feedback stability, phase noise, signal quality, shared loading,
matching and mode transitions. Public statistical models are used only within
their documented scope; missing correlations remain uncertainties.

The sequence remains mathematical model closure, then verified connected
transistor schematic, then layout/extraction. This architecture is a plan, not
a claim that the primitive library or transistor schematic is complete, and it
does not authorize other block layouts before the schematic gate is satisfied.

## Choose work by architectural risk

Prioritize connected clock quality, complete RF conversion and pad/package/power
coexistence. A run should decide a current requirement, failure cause or circuit
choice. Do not optimize a convenient parameter while its connected interface is
missing. Use the [issue register](risk-priorities.md#open-issue-register) and
[pad gates](../analog/pads/README.md#completion-gates) to select work.

## Model and circuit contract

Before a run, identify the selected configuration, terminals/reference planes,
source/load/bias network, units, initial state, measured outputs and acceptance
limits. Retain disabled branches and external stored charge. State exactly which
sources, controls and observations remain ideal. Runtime configuration needs
physical switches/arrays/control circuits; editing a device size is not a runtime
setting.

Use the shared design to obtain budgets and settings. Independent numerical
examples and adverse/simplified cases must declare deviations. Never add the
same parasitic as both extracted geometry and a budget-sized ideal capacitor.
Physical limits, assumed budgets and numerical tolerances are different inputs.

## Fast-to-detailed execution

1. Check dimensions, DC bias/headroom, current and area arithmetic first.
2. Use mathematical blocks and short targeted operating-point/AC/transient
   checks to locate the decisive failure boundary.
3. Connect actual PDK devices with finite sources, loads, controls and supplies.
   Verify startup, shutdown, signal quality, timing and accepted uncertainty.
4. Complete the connected schematic before broad layout work. Generate physical
   views from the same parameters, extract parasitics, and rerun the same tests.
5. Use long transient/statistical campaigns only when required to decide an
   open gate; short deterministic success is not rare-event qualification.

A simulation must reach its requested observation window. Solver exit status,
convergence, timestep/grid sensitivity and physical acceptance are separate
checks. Check bias after changing initialization. An imposed initial condition
cannot prove cold startup. Diagnose model discontinuities, unphysical sources
and timestep error before interpreting a failure as silicon impossibility.

## Retained-state and physical checks

Keep supply/return, reference charge, filter memory, oscillator phase and FIFO
state through transitions. Do not reset a subsystem to make a reply or recovery
pass. Observe internal terminal stress, current paths and common-mode behavior
as well as the output. External passives include interconnect, ESR/ESL and loss.
Calibrate off chip where practical; include measurement uncertainty and finite
control/host latency in the model.

DRC checks geometry, LVS checks device connectivity, extraction estimates
parasitics and transient analysis tests behavior. None substitutes for another
or for ESD/reliability qualification. Use exported-GDS connectivity and device
checks to catch layer-marker, body/well and multiplicity errors. RF inductance,
substrate coupling and package effects require explicitly justified models.

## Reproducibility and stopping criteria

Pin PDK, model and simulator identities. Record source hashes, exact settings,
commands, result scope and failed/missing gates. Cache by inputs and tool versions;
do not refresh fingerprints without rerunning. Keep large waveforms, logs and
exploratory outputs in scratch; retain only evidence needed by the current design.

Finish a work unit with a keep/change/unresolved decision in the existing owner,
corrected code/tests where needed and a clean commit. A useful stopping point
can include unresolved physical risks; it must not label assumed behavior as
implemented or hide an acceptance failure behind a passing assertion.
