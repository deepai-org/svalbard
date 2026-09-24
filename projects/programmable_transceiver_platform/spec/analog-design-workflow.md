# Analog schematic design and simulation workflow

Use this workflow for subsequent analog passes. Its purpose is to spend less time
on uninformative simulations and retain lessons that apply to other blocks.
It is a living procedure, not a claim that the current design is qualified.

The user-required sequence remains: complete and verify the connected transistor
schematic, then layout, extract and repeat the tests. Transmission-line geometry
and shielding are deferred. Preserve the full programmable RF/wired companion
scope. An easier isolated circuit is an experiment, not a replacement product.

## Active phase: whole-chip behavioral closure

User direction: focus on the whole-chip behavioral model until it is satisfactory.
Use `make transceiver-behavioral` and its source-hashed report as the primary
architecture loop. Connect lifecycle, both transport directions, waveform quality,
clock/error envelopes, power/area/pins and uncertainty sweeps in one behavioral
composition. Do not resume solver optimization, transistor implementation or
layout while those architecture gaps remain. Detailed existing models provide
selective parameter evidence, not mandatory per-scenario integration. A successful
assumption-based screen is not physical qualification or whole-chip completion.

## Primitive-library architecture for schematic and layout work

Adopted user decision, 2026-09-23: build the programmable transceiver's analog
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
does not authorize starting layout before the schematic gate is satisfied.

## 1. Choose the next uncertainty, not the next convenient parameter

### Keep the three completion gates distinct

Mathematical closure means the full intended chip operates in one connected
model across explicitly declared functional, loading, timing, noise and service
envelopes. It requires end-to-end acceptance tests, ownership/accounting,
failure/recovery behavior, and a complete allocation of modeled resources and
loads. A nominal short capture or an isolated block pass cannot close it.

It does **not** require proving every assumed circuit parameter in GF180 before
the transistor schematic phase begins. For each uncharacterized parameter,
declare the required value/range, units, owning block, effect on acceptance and
the later circuit test that must establish it. Mathematical results are
conditional on those assumptions. Unknown loads must have explicit assumptions
or sensitivity ranges; they cannot disappear from the model or count as zero.

The transistor schematic phase must then realize those contracts using the six
primitive families and check where the public PDK supports or contradicts them.
If circuit evidence misses a contract, revise the architecture/model and rerun
the affected chip tests. Layout and extraction subsequently test the physical
implementation. Keep physical uncertainty visible at every stage without making
silicon qualification a circular prerequisite for beginning circuit design.

### Everyday loop

Use one short experiment record, not a new planning document for every run:

1. **Select:** name the highest-risk unanswered circuit question and the retained
   baseline. Search the lessons below before choosing a change.
2. **Predict:** write the observation that would support or reject the change,
   measurement windows, and the cheapest useful test.
3. **Build and run:** modify the actual schematic, preserve the baseline, and use
   the existing runner and checker where their assumptions apply.
4. **Check and decide:** establish completion, valid bias and measurement validity
   before interpreting performance. Retain, reject, or leave the result unresolved.
5. **Teach the next pass:** save exact commands and evidence, then add or revise a
   transferable lesson only if something new was learned. Automate a repeated
   check when it saves work; keep circuit-specific conclusions scoped.

The durable outputs are the schematic, reproducible fixture/checker, evidence,
and a short decision record. These should let a later session continue without
reconstructing the reasoning from the entire conversation.

Use the [compact experiment record](../verification/experiment-template.md#compact-record-for-routine-passes)
for routine work. Expand only the fields needed to explain changed assumptions
or an ambiguous result. The accumulated speedup should come from reused fixtures,
automated measurements and avoided dead ends, not omitted verification.

### Make each repetition cheaper

Before writing another runner, identify the existing fixture, measurement and
failure signature it can reuse. Keep commands with the experiment record and
link the evidence from a transferable lesson. Do not copy long historical notes
into every new experiment.

After a substantive pass, ask what consumed effort without changing a decision:
model setup, convergence, simulation, waveform export, analysis or interpretation.
Improve that specific step when it is recurring. Record runtime and data size
for expensive fixtures so a reduced circuit can be judged as a practical speedup,
as well as a valid approximation.

A failed candidate needs a reason to retry: a changed hypothesis, boundary
condition, model or measurement. Repeatedly successful plumbing belongs in a
reusable runner/checker; uncertain circuit conclusions stay in scoped evidence.
Periodically verify that the retained baseline still reproduces after changing
shared tooling. Never obtain speed by silently weakening the original test.

### Resume checklist

1. Read `spec/schematic-implementation.json`, the latest relevant risk entry and
   the last experiment's evidence. Historical pass notes are not current job
   status or proof that a candidate was adopted.
2. Check any recorded live job before launching another. Inspect its process,
   log and artifacts; continue observing it if running. If the handle is gone,
   determine completion from the artifacts rather than automatically restarting.
3. Search this document and existing runners/checkers for the same failure or
   measurement. Identify the best verified baseline and its remaining idealities.
4. Fill the experiment template before changing the circuit. Start with the
   cheapest test whose result could change the design decision.

Keep a compact handoff in the pass note: selected circuit, runner and checker
commands (with working directory), output directory, live job/status if any,
last verified result, and next action. Do not use the length of the pass history
as a substitute for this state.

Read the implementation inventory and risk priorities. State one question and
what observation would change the next action. Identify the system requirement
it serves and the most credible alternative explanation of the current failure.
Use [the experiment template](../verification/experiment-template.md).

At each integration failure, and at least every five substantive passes, reassess
whole-chip risks: autonomous timing, complete RF RX/TX and converters, actual
bias/references, wired recovery, host interface, power and coexistence. Do not let
an endless sequence of ADC adjustments stand in for missing chip functionality.

Prefer a small experiment that distinguishes causes over a large parameter grid.
Do not tune to a single output code or sampling instant. Define evaluation windows,
loads and error measures before inspecting candidate results. If a numerical
acceptance limit is not yet allocated from the system requirement, report the
measurement as diagnostic; do not invent a passing threshold after the run.

## 2. Establish the circuit and model contract

Record ports, units, current directions, signal polarity, common mode, supply,
source/load impedance, clock timing, reset and initialization assumptions.
Separate implemented FET/passive circuits from ideal stimuli and missing blocks.

Before relying on a new PDK primitive, inspect its actual installed model and
verify essential behavior with a tiny test: units, geometry, multiplicity,
terminal order, corner selection and active/non-active coefficients. Model
presence does not establish availability of a fabrication option. PCell minima
are evidence about that implementation, not universal foundry rules.

For unknown loading or device behavior, test adverse scenarios in both directions
and interacting extremes where relevant. A convenient corner set is not a proven
bound on undisclosed fab behavior. Fixed temperature/supply does not remove
mismatch, process uncertainty, self-heating, noise or parasitics.

## 3. Diagnose cheaply before committing to long transients

Use the applicable checks in this order; oscillator and switching circuits may
need an appropriate dynamic operating state rather than a useful static one.

1. **Elaboration and DC:** connectivity, supply current, device VDS/VDSAT,
   overdrive, internal-node headroom, common-mode/output range and load compliance.
   Investigate gain/headroom failures before increasing device size.
2. **Small-signal behavior:** gain, loading, input/output impedance and relevant
   frequency peaks across operating points. Use a validated return-ratio or pole
   analysis when making stability claims. An AC plot alone does not prove stability.
3. **Large-signal behavior:** steps in both directions, overload/recovery,
   source/sink asymmetry, slew and settling over windows. Separate static error
   from dynamic error and from switching/turnoff disturbance.
4. **Connected behavior:** actual neighboring FET circuits and loads, repeated
   operations, reset/rearm, both input histories, timing uncertainty and power.
   Check physical analog state as well as digital decisions.
5. **Required quality and robustness:** transfer/linearity, noise/distortion,
   timing/jitter, operating modes, startup, variation and uncertain loading.
   Choose tests appropriate to the claim; deterministic transient residuals are
   not intrinsic noise or phase-noise evidence.

Preserve a matched baseline at each stage. A candidate that improves one metric
must carry its regressions and power/area costs into the next decision.

For regulation and settling comparisons, report both absolute error from the
required target and motion relative to each candidate's own settled operating
point. A changed DC offset can hide or exaggerate a dynamic improvement. Keep
the target-error requirement unchanged; offset subtraction is a diagnostic, not
a way to turn a failed requirement into a pass.

## 4. Keep the experiment controlled and reproducible

For new or revised runners, capture source, include/model and generated-deck hashes
before simulation, together with the pinned simulator/container, options, corners,
seeds, initial conditions and requested horizon. Check hashes afterward. Older
runners with weaker provenance remain labeled accordingly; this rule does not
retroactively strengthen their evidence.

Use a unique output directory. Preserve baseline and failed candidates. Change
only the declared circuit/fixture dimension. Verify that reversing the declared
change reproduces the baseline deck. When adding parameterization, first reproduce
the original parameter setting numerically; then compare alternatives.

Prefer a shared checker with explicit variants over copied checkers. Keep columns
and units named, with waveform shape/header checks before indexing. Extend a
shared runner only when repeated experiments establish a real common need; avoid
building a general framework before the circuit questions are understood.

Preflight models and fixture timing with cheap runs. Save the vectors needed to
diagnose bias, controls, actual switch gates/plates, supply and reference behavior.
Avoid saving every internal device over a long transient without a reason.

## 5. Treat simulator completion and physical success separately

Record process exit status, log errors, actual final simulation time, missing
vectors and finite-data checks. A process exit of zero is not a physical pass;
a partial waveform is not a completed run. Preserve failed evidence before
asserting a failed requirement. A checker must distinguish partial case coverage
from a completed test matrix and distinguish logic checks from analog accuracy.

For convergence failures, retain the exact failing circuit and time. Check
coincident source edges and initial state; reduce the circuit while preserving
the suspected interaction. Compare numerical methods or equivalent stimulus
representations without interpreting numerical damping as physical stability.
A reduced test that completes narrows the problem only within its retained scope.

Check exported time ordering explicitly. Distinguish backward time from repeated
printed timestamps: extremely close simulator steps can round to equal exported
times. Preserve and report the raw sequence; do not silently perturb times or
collapse differing samples. Derivatives and interpolation require an explicit
policy for repeated times. Compare simulator completion and the actual horizon
independently of this export diagnostic. The mixed-clock passive experiment
completed despite repeated printed timestamps near an active-fixture failure.

Poll the existing process handle. A timeout observing it is not permission to
restart it. Record whether a job is running, terminal or missing before taking
another action. Long simulations should not prevent independent useful work.

## 6. Measure where the circuit actually depends on accuracy

Examples: ADC references immediately before comparator evaluation; charge-pump
current integrated over complete cycles; physical switch gates and capacitor
plates rather than upstream logic rails; RF gain only after bias is valid.

Check reset release against the first real clock edges. Separate prebiased or
seeded operation from cold startup. Separate average frequency from phase lock
and jitter. Separate selected correct codes from transfer accuracy and ENOB.
Use continuous windows to detect a moving waveform that happens to cross the
right value at one chosen instant.

Derive acquisition and conversion budgets from the actual repeated clock edges,
not just the first frame. An unusually long startup track can hide a steady-state
settling failure. Compare driver outputs, tracking plates and held plates across
both transition directions before attributing an inaccurate code to the ADC core.
When adding device probes, verify that the observation-only replay preserves the
original outputs and check probe conventions against physical terminal voltages.

## 7. Close the pass and reuse what it taught us

Label evidence by what it establishes; these are separate claims, not a single
automatic ladder to qualification:

| Claim | Minimum supporting observation | Does not establish |
|---|---|---|
| Simulation completed | Valid vectors, terminal status and requested horizon | Circuit performance |
| Circuit effect observed | Controlled comparison and valid operating state | Root cause beyond the comparison |
| Requirement met in named cases | Predeclared limit, valid measurement and complete case coverage | Other corners, modes or uncertain loads |
| Connected behavior verified | Actual neighboring circuits and explicit remaining idealities | Whole-chip readiness |

Only promote a candidate after checking the relevant competing costs and
regressions. Preserve a rejected candidate's exact conditions and reason; retry
it only with an explicit new hypothesis. A successful diagnostic fixture may
remain useful even when its circuit is rejected.

Record: question, controlled change, verified observations, failed requirements,
limitations, candidate disposition and next discriminating test. Link the exact
artifact, not only a prose conclusion. Update the inventory when implementation
or its qualification status changes. Keep readiness false while required blocks
or evidence are absent.

Add a short transferable lesson below when an experiment exposes a new failure
mode. Revise an old lesson when evidence contradicts it. Promote a lesson into a
reusable check when the same mistake can recur; do not endlessly re-run unrelated
regressions after a local change.

## 8. Make the next pass cheaper

### Minimum useful pass

Keep the routine lightweight: one question, one controlled change, one reusable
measurement, and one decision. The experiment template is a checklist, not a
requirement to write a long report. Link existing model and fixture contracts
instead of copying them. A documentation-only pass needs no simulation.

Before a costly run, estimate runtime from the closest previous fixture and set
a diagnostic horizon long enough to observe the behavior being tested. Record
what would justify extending it. If the run cannot distinguish the proposed
explanations, improve the experiment before spending more simulation time.

At the periodic whole-chip review, check whether recent passes changed a design
decision or retired a risk. If they only reproduced a known symptom, change the
test or move to a more consequential uncertainty. Track progress through verified
requirements and removed ideal dependencies, not the number of simulations.

Keep reusable lessons in this document and circuit-specific results in evidence
and the implementation inventory. When a lesson changes the procedure, update
the relevant step above as well as recording its evidence below; otherwise it is
too easy to accumulate notes without improving the next run.

Before creating a fixture, search the evidence and lessons for the same topology,
failure symptom or measurement. Reuse a verified fixture and checker when their
model, interface and initialization assumptions still apply. State which assumptions
changed; a previously successful run is a baseline, not automatic qualification
of a new circuit.

Keep each pass's handoff short: current candidate, exact reproduction command,
evidence paths, unresolved failure and next discriminating test. Record elapsed
runtime and output size for expensive tests so a later pass can choose a cheap
screen before launching the full case. Preserve the smallest reproducer of a
failure alongside the connected circuit it came from.

Distinguish three outcomes when recording lessons: a demonstrated circuit effect,
a simulator or measurement artifact, and an unresolved hypothesis. Include the
conditions under which the observation holds. Do not turn a single successful
case into a general design rule or repeat a rejected change without identifying
new evidence or a changed assumption.

At the periodic whole-chip review, also review the workflow: which test changed
a design decision, which run added no information, and which repeated manual
check merits automation? Update this document and the experiment template in the
same pass. The aim is faster risk reduction, not a growing count of simulations.

## Lessons already demonstrated

### Find and reuse a test before building another

Use this short route through the existing reference-driver tests as a worked
example of the workflow. These are reusable diagnostic fixtures, not qualified
IP. Paths below are relative to this project; inspect a runner's output-directory
handling before executing it so earlier artifacts remain intact.

| Question | Existing runner in `verification/` | Checker in `verification/` |
|---|---|---|
| Is static target tracking or device compliance already wrong? | `run_reference_pair_target_dc.sh`, `run_reference_pair_device_dc.sh` | `check_reference_pair_target_dc.py`, `check_reference_pair_devices.py` |
| Does the actual compensated pair present a large dynamic impedance? | `run_reference_pair_impedance.sh` | `check_reference_pair_impedance.py` |
| How do both rails recover from positive and negative current demand? | `run_reference_pair_step.sh` | `check_reference_pair_step.py` |
| Does a promising static change survive the actual ADC switching load? | `run_reference_long_mirror_frames.sh` | `check_bit6_complement.py --reference-mirror` |

Before adapting one, confirm topology, compensation, reservoir, bias, initialization
and load match the intended baseline. In particular, the older untuned buffer
impedance screen is not interchangeable with the compensated paired-reference
screen. Reuse the measurement method, not an inherited conclusion.

For each repeatedly useful fixture, keep its circuit contract, reproduction
command, checker and known limitations together in its manifest or pass note.
Add a new index entry only when it saves a real search; keep raw experiment history
in evidence rather than expanding this procedure into a second chronological log.

### Static improvements must survive dynamic tests

Longer reference-amplifier mirror devices improved nominal DC target error, but
worsened impedance peaks and the actual ADC's worst decision-window reference
errors. The candidate was rejected. Use DC as an inexpensive rejection screen;
passing it earns a dynamic test, not adoption.
[DC comparison](../evidence/reference-long-mirror.json),
[impedance comparison](../evidence/reference-pair-impedance.json),
[connected rejection](../evidence/reference-long-mirror-frames.json).

The retained pair's bipolar current-step test also showed substantially slower
high-rail recovery than low-rail recovery. Separate each rail and demand direction
before choosing a topology change. This small-pulse observation does not establish
settling under the larger periodic CDAC load or prove a unique failure mechanism.
[Step response](../evidence/reference-pair-step.json).

| Observation | Reusable consequence | Evidence |
|---|---|---|
| UIC and a short RF run left a slow gate-bias network uncharged. | Validate bias before scoring gain; label prebias separately from startup. | [Schematic implementation gate](#schematic-implementation-gate) |
| The selected MIM model ignores `par`, and the assumed 20 fF unit was not supported by its inspected minimum cell. | Audit primitives and explicit replication before optimizing a circuit around their assumed values. | [MIM audit](../evidence/adc-mim-model-audit.json) |
| Correct SAR logic converted inaccurate held samples. | Audit analog acquisition and reference state independently of decision/capture checks. | [Connected capacitor cases](../evidence/adc-sar8-mim-frames-screen.json) |
| Nominal sample accuracy partly came from turnoff cancellation while the input was still moving. | Compare time windows, both histories and adverse loads; avoid one-instant optimization. | [Acquisition diagnostic](../evidence/adc-sar8-acquisition-diagnostic.json) |
| Larger amplifier geometry did not repair an input transistor losing saturation. | Inspect device OP and internal range before scaling current/area. | [Reference headroom](../evidence/reference-buffer-op-screen.json) |
| Reference drivers passed selected DC loads but had large AC impedance peaks and decision-time errors. | Require dynamic regulation and connected switching tests, not DC capacity alone. | [Impedance](../evidence/reference-driver-impedance.json), [decision windows](../evidence/adc-reference-decision-windows.json) |
| A larger reservoir shifted the peaks; series damping traded resonance against bypass impedance. | Track competing metrics; neither larger capacitance nor lower peak alone selects the design. | [Damping comparison](../evidence/reference-reservoir-damping.json) |
| Equal DAC output clamps hid finite-load transfer curvature. | Retest with output swing and actual load impedance before claiming linearity or choosing a dynamic fixture. | [Finite-load DAC audit](../evidence/current-dac-loaded-dc-screen.json) |
| A monotonic static DAC developed large major-carry glitches and driver current peaks. | Add actual digital drivers, skew and dynamic supply measurements before promoting a static converter result. | [Dynamic DAC](../evidence/current-dac-dynamic-screen.json), [timestep check](../evidence/current-dac-dynamic-fine-screen.json) |
| Nominally equivalent clock sources produced different solver outcomes in a reduced PFD test. | Check source representation and interface realism; waveform equivalence does not guarantee identical numerical behavior. Keep real feedback for autonomous qualification. | [Clock representation comparison](../evidence/pfd-matched-waveform-screen.json) |
| Reset/clock overlap selected a different PFD phase branch and apparent pump direction. | Verify startup event ordering before diagnosing a polarity error. | [Reset comparison](../evidence/pfd-reset-phase-screen.json) |

## Additional circuit lessons from passes 193–204

- A statically correct thermometer decoder produced transient extra/missing high
  cells even at zero input skew. Test actual decoder transitions and observe
  physical controls before inferring dynamic DAC performance from a DC sweep.
  [Evidence](../evidence/dac-segmented-decoder-hazards.json).
- Post-decoder registers isolated command skew in selected cases, but opposite
  polarity clock-to-output delay and unequal loads still created glitches. Carry
  capture latency explicitly in comparisons; never realign cells individually.
  [Evidence](../evidence/dac-registered-timing.json).
- Equal input loading removed accidental timing cancellation and worsened one
  direction. Equal Q/QB branch depth also worsened output error. Treat structural
  symmetry as a hypothesis to measure, not a performance guarantee; retain both
  directions, actual loads and the rejected candidates.
  [Equal-load experiment](../evidence/dac-segmented8-isolated.json),
  [complementary interface](../evidence/dac-segmented8-dual.json).
- A whole-record current maximum was dominated by startup. Report separate
  startup, idle and update windows, peak current and integrated charge/energy.
  Keep signed ideal-source charge return distinct from dissipated power.
  [Evidence](../evidence/dac-registered-timing.json).

## Connected RF lessons to reuse

| Observation | Next-time procedure | Evidence and limits |
|---|---|---|
| Stronger final LO drivers increased conversion while changing the loading seen by the LNA. | Measure source-to-output conversion, the actual RF-node amplitude, and driver power together; isolated block gains cannot simply be multiplied. | [Controlled driver comparison](../evidence/quadrature-lo-driver-comparison.json); nominal deterministic simulation only. |
| Halving mixer width reduced RF loading but slightly reduced end-to-end conversion. | Score the system metric after a loading improvement. Stop a size sweep when the proposed benefit is contradicted unless a new hypothesis warrants another test. | [Half-width comparison](../evidence/quadrature-half-comparison.json); does not select the best noise or linearity tradeoff. |
| Current sensing at a periodically switched RF port produced a useful tone-dependent loading measurement. | Declare current direction, validate the phasor fit with a known load, and retain the operating waveform and frequencies with the result. | [Interface loading](../evidence/quadrature-interface-loading.json); not a general linear time-invariant impedance model. |
| Adding the baseband filters left startup movement in the conversion fitting window and produced an apparent tone even in the no-tone control. | Run matched zero/tone histories, compare later windows, and extend the unchanged circuit's horizon before choosing a gain or I/Q balance result. | [201 ns conversion analysis](../evidence/bb-connected-conversion.json); [401 ns comparison](../evidence/bb-settling-comparison.json) reduces late-window sensitivity; it does not qualify startup or noise. |

## Current workflow debt

Some older runners hash inputs only after execution, use fixed waveform column
indices, or duplicate fixture construction. Improve these when touching the
relevant runner; do not silently claim older artifacts meet the stronger contract.
Before long autonomous-clock qualification, device/model noise coverage and an
appropriate phase-noise method still need resolution. Documentation and diagnostic
screens do not satisfy those missing implementation/evidence obligations.


### Source-event isolation lesson (pass 232)

A four-FET buffer aborted with an electrically separate pulsed source present;
changing only that separate source to DC allowed completion through the requested
800ns horizon. When diagnosing transient convergence, account for all timed
sources, including ones outside the active signal path: they can affect global
stepping. This is a demonstrated numerical sensitivity in this fixture, not a
proven simulator-internal mechanism or a physical repair. Never remove required
feedback to claim autonomous operation.
[Failing fixture](../evidence/buffer-only-breakpoint-screen.json),
[controlled comparison](../evidence/buffer-single-source-screen.json).


### Bidirectional switch probes (pass 235)

A switch finger's named drain/source can reverse their electrical roles across
an input sweep. Preserve signed terminal voltages and inspect the model's probe
convention before interpreting VGS-VTH, channel current sign or saturation.
A negative raw VGS-VTH is not by itself proof of cutoff in reverse operation.
Observation-only replay should reproduce the original circuit outputs; the TX
probe sweep does so bit-for-bit.
[Evidence](../evidence/tx-device-op-dc.json).


### Recheck every bias after changing initialization (pass 241)

Adding a seeded oscillator required UIC and removed operating-point initialization
from the entire connected TX fixture. Its DAC bias was still charging at40ns;
an ideal-clock UIC replay also lost signal. A startup change in one block can
invalidate the operating state of its neighbors. Verify each bias before scoring
connected gain, and use matched initialization controls before assigning cause.
[Evidence](../evidence/tx-startup-state.json).

### Noise attribution and exported scales (pass 297)

Use a known thermal-noise calibration before interpreting a new noise fixture.
When attributing device noise, sum power spectra from either aggregate devices or
their subcomponents, never both; check closure against the reported total at every
frequency. Integrate PSD, not amplitude spectral density. Detailed ngspice noise
reporting can change the implicit scalar scale column exported by `wrdata` while
leaving the named total-noise values unchanged. Read headers and compare the named
quantities rather than treating a changed scale as a circuit regression.
[Verified comparison and attribution](../evidence/bb-noise-contributors.json).

### Signed event offsets as a numerical discriminator (pass 307)

An electrically separate pulse shifted by either−1ps or+1ps allowed the same
buffer circuit to complete800ns where coincident nominal events failed663.2ns.
When testing suspected event collisions, preserve the actual circuit and test both
signs before changing transistor sizes or declaring a physical failure. This result
supports timing sensitivity in the retained fixture, not a universally safe phase
offset or an autonomous-loop repair. [Evidence](../evidence/buffer-event-offset.json).

### Model current orientation (pass 316)

The NMOS pump switch briefly reverses VDS; its reported id integrated without
orientation overstated net drain withdrawal by~4.36fC/cycle. Zero-volt terminal
sensors close KCL and show that orienting id by model VDS removes nearly all of
that cycle-integral discrepancy. Verify current conventions against terminals,
including reverse operation, before labeling a remainder displacement or missing
charge. Agreement over a full cycle does not prove instantaneous equivalence.
[Evidence](../evidence/pump-branch.json).

### Loaded acquisition and device evidence (passes 350–362)

- Moving the ADC fixture to the receiver's approximately 1.07 V common mode
  increased held-signal error despite valid digital decisions. Measure interface
  common mode and loaded settling before connecting blocks; isolated operation
  at another common mode does not establish compatibility.
- Advancing the first input transition recovered its code, but the actual steady
  schedule allows only 10 ns acquisition at 20 MS/s per channel. A first-frame
  improvement is not a throughput-preserving repair. Audit repeated source and
  clock edges before accepting a timing change.
- One driver leg lost tail headroom while the other retained headroom and still
  had substantial settling error. Use device operating points alongside dynamic
  output measurements; a VDS/VDSAT observation alone does not establish the cause
  or justify increasing bias. The probe replay reproduced original vectors
  bit-for-bit, supporting this comparison within the retained fixture.

[Schedule](../evidence/adc-fixture-schedule.json),
[settling comparison](../evidence/adc-cm-sampling-early.json),
[device observations](../evidence/adc-driver-devices.json).

### Reduced fixtures and measurement scope (passes 371–392)

- Validate a reduced circuit against its connected parent before tuning it. The
  static-CDAC driver fixture reproduced the first acquisition within 0.403 mV,
  then a resistor candidate improved the full ADC. Preserve both tests: a reduced
  model removes interactions that must return at integration.
- Use windows appropriate to the question. A candidate was worse over 8–9.9 ns
  but better near the intended 10 ns aperture. Report both; neither a favorable
  instant nor an overly broad window alone establishes timing tolerance. Actual
  sampler-edge tests include switching interactions absent from hypothetical
  observations of an always-on sampler.
- A failed all-vector reproduction check must remain failed. If a narrower
  diagnostic use is justified, record a separate audit of relevant analog nodes,
  decisions and timing, plus excluded claims and any criteria added afterward.
  Do not use scoped reference agreement to assert identical digital power.
- Replaying every saved current point creates new source breakpoints. A load
  replay failed initially, while a quantified first-picosecond interpolation
  completed a short test. Preserve the approximation and compare full rail
  trajectories before using the replay; numerical completion is insufficient.
- Reduced transistor count does not guarantee a faster simulation. Record runtime
  and breakpoint density before investing in a reduced fixture as a speedup.

[Reduced fixture](../evidence/adc-loaded-driver.json),
[actual edge comparison](../evidence/adc-sampler-edge-comparison.json),
[scoped replay audit](../evidence/adc-reference-reproduction-scope.json),
[source-startup test](../evidence/reference-load-startup.json).

### Isolate numerical tolerances before repeating a long run (pass 402)

Tightening three tolerances together caused the original ADC fixture to fail
at time zero while its instrumented version advanced. A matched1ns matrix
showed that abstol alone reproduced the failure; reltol-only and vntol-only
completed startup for both. Test individual numerical changes on the exact
retained circuits before another expensive history. Successful startup does
not establish accurate dynamics, and adding ideal current sensors can change
solver behavior even when their intended voltage drop is zero.
[Startup matrix](../evidence/cdac-probe-startup.json).

### Compare integrated demand as well as instantaneous peaks (pass 410)

In three completed CDAC probe histories, changing solver tolerances moved selected
peak currents by up to2.05mA while signed window charge changed by at most2.6fC.
Use native-grid peaks and explicit endpoint integration together when evaluating
switching demand; do not size a circuit solely from one exported maximum. This
is an observed sensitivity comparison, not a universal guarantee that integrated
charge converges. [Evidence](../evidence/cdac-current-sensitivity.json).

### Small-signal and pulse improvements still need actual neighbors

The hybrid high-reference input stage improved DC headroom, its impedance peak
and recovery from the selected signed current steps. Under the actual switched
dual-ADC load, however, worst high-reference target error increased from about
61.35 to 70.65 mV, and reference power increased by about 2.05 mW. It did not
replace the baseline. The DC offset also changed sign, so this does not establish
that every dynamic property worsened.

Use the cheap tests to select candidates for integration, then measure the
original system metrics again with actual neighboring circuits. Record absolute
target error, deviation from each circuit's own DC point, window motion and
power separately. A favorable isolated test remains useful evidence even when
the candidate fails the connected decision.
[DC](../evidence/reference-hybrid.json),
[impedance](../evidence/reference-hybrid-impedance.json),
[signed steps](../evidence/reference-hybrid-step.json),
[actual ADC load](../evidence/reference-hybrid-frames.json).

### Bound postprocessing memory as well as simulator memory

The selective-save PLL completed8.001us, but its4.3GB exported waveform exceeded
the4GB container's memory budget when the runner used `read_bytes()` for hashing.
The existing process completed after its post-simulation memory limit was raised;
no simulation restart was needed. Future runner and checker hashes stream chunks.
Budget export, hashing and analysis separately from ngspice's transient state.
A waveform file existing does not establish terminal provenance; wait for the
runner result and validate it. Preserve resource changes with the experiment.

### Use thresholds appropriate to the observed stage

The clean-sine LO experiment produced regular downstream pulses even though its
first inverter's MID node never crossed 1.65 V. Counting every internal node at
half supply would therefore falsely identify a failed stage. Inspect the next
stage's transfer behavior and retain analog voltage ranges alongside crossing
counts. A static switching point remains a diagnostic marker, not a complete
dynamic model.

The autonomous receiver also lost I-output crossings while the upstream ring
continued oscillating. Clean-sine tests, including a mixer load, did not reproduce
that failure. Keep the actual waveform, operating state and neighboring circuits
in the diagnostic path; isolated success does not clear the connected failure.
[Internal-stage example](../evidence/lo-sine-speed.json),
[autonomous upstream comparison](../evidence/latest-lo-upstream.json),
[mixer-loaded sine test](../evidence/lo-mixer-sine.json).

### Avoid repeated full-waveform copies during local measurements

The LO gap analysis repeatedly interpolated endpoints using strided columns of a
large waveform array. Storing columns contiguously once reduced postprocessing
from several minutes to seconds. Both complete parsed reports were exactly equal;
the original job was allowed to finish for comparison. Check array storage and
copying before reducing waveform resolution or weakening measurements to save
runtime. The optional contiguous mode in `analyze_lo_gap_state.py` preserves
samples, windows and formulas; budget its one-time allocation as well.

### Prefer an intact short simulation when replay changes analog state

Declare reproduction tolerances before evaluating a replay. Matching output bits
alone is insufficient: the SAR command replay matched decisions but missed held
nodes by1.49mV and rails by44uV, failing its10uV analog gate. Its intact shortened
full-SAR baseline reproduced exactly in the checked window. Use that fixture for
reference-circuit experiments rather than tuning a replay indefinitely. Keep
reduced-model validation local to its measured operating conditions and history.

## Fast-model handoff checkpoint

`verification/fast_schematic_handoff.py` now records current source/evidence
availability and hashes for all ten entries in `schematic-implementation.json`.
The audit finds the listed artifacts present, but no complete whole-chip analog
schematic. Artifact presence is not performance verification; historical source
identity must be checked at each circuit refinement.

The highest-risk abstraction mismatch is loaded LO delivery: existing autonomous
transistor evidence reports missing I-LO threshold crossings and reference spur,
whereas fast RF mixing assumes an ideal carrier. Before using its passing RF
quality as a circuit target, specify mixer-drive amplitude, duty, missing-edge
and supply/load tolerances and connect their consequences to the mathematical
RX/TX model. Preserve the separate replay improvement as diagnostic evidence;
it is not autonomous startup/noise closure. Reference/converter loading and
whole-chip transistor interconnection remain the next major handoff gaps.

Current audit: `evidence/fast-schematic-handoff.json`. The layout gate stays closed.


## Programmable protocol primitives

Implement these from the already selected six primitive families and shared
control services. A configurable block must still have bounded code ranges,
finite resolution, loading and power; mathematical configurability is not a
new ideal component exemption.

### RF-disabled forecast performance candidate

Live-process sampling places most observed time in the coupled Radau solve
and rail/PLL forecasting; the nonblocking profiler lost samples, so this is
hotspot evidence rather than a precise CPU allocation. Wired-only intervals
currently perform at least two RF phase-feedback solves even though the RF
oscillator, drive and receive input are disabled.

`verification/inactive_rf_feedback_check.py` compares a single-solve candidate
against that reference with identical ODE tolerances, 2/20 ns intervals, host
edges and nonzero stored network energy. Checked node/filter/rail/reference/
host/clock states agree within 1.5e-14 in these four cases, and the solve count
falls from two to one. All passive decay and shared supply loads remain in the
ODE. The expanded probe compares 154 numeric fields, including 22 energy/charge
fields, plus domain rail trajectories. Active-RF use and invalid intervals
reject, and injected solver failure preserves caller state. A guarded version
is now installed in the primary composition after the original control
regression passed. A matched serialized-configuration/finite RX-to-host
scenario has passed in both isolated copies. Source manifests were rechecked,
and all five reported functional outcomes agree, including actual acquisition
and eight causal received words at 1.62 Gb/s. Reports are preserved as
`evidence/resource-command-reference.json` and
`evidence/resource-command-optimized.json`. These are functional comparisons,
not full analog trajectory equivalence; the return observer decodes ideal words.
Fresh main-model coupled primitive and serialized record-return checks pass;
the longer post-integration control regression remains live.
Do not generalize this result to
active RF or replace a still-running reference simulation.

## Bounded architecture iteration

Use `make transceiver-math-fast` as the routine loop: analytical/envelope RF,
event-level transport/clock controls and interval uncertainty checks, bounded
at 30 seconds total. The result is reduced-model evidence, not closure of the
detailed coupled chip. Use short coupled transient windows to validate the
approximations at selected disturbances; do not repeat a full stiff startup
for every controller or configuration change. Full cold-start, sustained
traffic and coupled uncertainty remain explicit later verification gates.
Long coupled runs require `--detailed` and a specific unanswered question.

## TMDS reuse before new circuitry

For HDMI/DVI, first extend the existing wired current-steering driver, termination
switches, comparator/sampler and clock divider using the six primitive families.
Characterize the selectable DC sink/common-mode behavior and high-frequency
forwarded reference before adding any separate video analog macro. Keep encoding
and three-chip bonding in the FPGA; instantiate the same die three times. The
schematic/layout sequence and all per-die constraints remain unchanged.

[HDMI/DVI board and pin plan](../../../docs/roadmap/programmable-transceiver-pin-plan.md#hdmidvi-through-multiple-instances).

The bounded canonical forwarded-RX check is opt-in:
`timeout 15s env OPENBLAS_NUM_THREADS=1 python3 projects/programmable_transceiver_platform/verification/protocol_model_check.py --forwarded-lifecycle`.
It acquires at 2 us, receives eight 1.485 Gb/s words, returns them through the
existing host path and verifies reference-loss draining by 2.14 us. It writes
`evidence/protocol-forwarded-lifecycle.json`; it is separate from the default
architecture suite to preserve its runtime budget. Earlier diagnostic windows
were stopped at their 12/15-second limits and provide no completed traffic proof.

Profiling identified repeated stiff solves while RF states were exactly zero.
`forecast_inactive_rf` now chooses RK45 only when driver, RF network, RX filter
and detector state are exactly dormant and receive forcing is explicitly zero.
Any retained RF state selects Radau. A short explicit/implicit rail comparison
must agree within 1 nV; no tolerance loosening or active-RF solver replacement is
implied. This optimization preserves the dormant invariant subspace and does not
permit discarding residual charge during wired/RF transitions.

Use `--forwarded-lifecycle --forwarded-direction tx` on the same bounded command
for the complementary canonical TX check. After real coupled startup, one whole
64-word host frame supplies four opaque words, which pass through the finite TX
FIFO, forwarded PLL serializer and current-switch pad. The test requires exact
internal serializer output and no underflow/pending words, then removes reference
and verifies draining, stopped serialization and tail-current decay below 1 uA
after 1 ns. `evidence/protocol-forwarded-tx-lifecycle.json` records this finite
case. RX remains the default direction. Neither test qualifies a continuous
three-chip video link; TX's canonical observation is internal, supplemented by
the separately scoped independent-clock pad test.

### Closure scope clarification

Mathematical closure requires the complete intended PHY companion's connected
behavior and declared uncertainty envelope. Representative FPGA fixtures must
exercise actual signaling, framing/timing demands and recovery, but complete
MAC/endpoint stacks are external responsibilities, not missing on-chip engines.
Conversely, a host queue or waveform test alone cannot close chip clocks, pads,
converter paths or management lifecycle. Physical feasibility remains unknown
until transistor evidence constrains noise, speed, linearity and loading; that
is the next stage, not something a mathematical pass certifies. Complete the
full transistor schematic before layout. The machine-readable stage boundaries
in `mathematical-closure.json` classify these obligations without waiving the
existing requirements or moving missing chip behavior outside the project.

## Reduced-model validation and promotion

Use the active behavioral loop above for architecture decisions. The historical
`system_model/run_fast_suite.py` remains a supporting eleven-script collection
with report `evidence/fast-suite.json`; it is not the full-chip acceptance gate.
Use envelope/event/charge models to screen uncertainty, then short transistor
windows to characterize the parameters that change decisions, then connected
transistor verification. Preserve autonomous startup/noise runs where those are
the question; steady-state replay cannot substitute for acquisition evidence.

Each imported measurement needs its source hash, circuit revision, stimulus,
supply, temperature, bias, load, observation window and numerical resolution.
Keep assumed ranges separate. Validate reductions against held-out transistor
waveforms/operating points and check timestep or envelope-rate convergence.
Do not combine incompatible measurements into a purported characterized chain.
Derive required margins from bidirectional and combined adverse sweeps; report
clipping, distortion, timing and queue growth separately. Current risk ordering
belongs only in [risk-priorities.md](risk-priorities.md).

## Schematic implementation gate

After mathematical closure, assemble a hierarchical GF180 FET/passive schematic
covering the full analog chip. Include actual digital circuits where analog
timing/loading/control depends on them; larger digital functions may use RTL.
Behavioral fixtures support verification but cannot stand in for missing PLL,
ADC or CDR circuits to claim schematic completion. Existing layouts are reference
material; new layout follows complete schematic verification and then extraction.
Transmission-line geometry and shielding remain deferred to layout.

Verify bias/common mode at every boundary, cold startup separately from seeded
runs, physical clock swing/duty/phase, actual loading, power/current/area/throughput,
and process/mismatch/uncertain-load sensitivity. Reject invalid operating bias
before scoring signal quality: the historical pass124 1 Mohm/20 pF bias network
has a 20 us timescale, so a 301 ns UIC run left the LNA off.

`analog/rf_rx_candidate.spice` is an early oscillator/buffer/LNA/mixer/filter/switch
candidate with external bias/control/sample clocks, lacking full PLL, quadrature
and ADC implementation. Its operating-point and seeded-bias benches do not
prove cold startup, gain or noise. Likewise `pll_clock_path.spice` alone is a
VCO/restorer/divider path, and `phase_control_dac.spice` is not a radio converter.
Use [schematic-implementation.json](schematic-implementation.json) for the current
inventory; presence of a source file does not prove operation.

Historical reference-loading example: ideal references gave SAR codes 76/179/76
at ±0.4 V; actual references with the damped driver gave 77/179/76 versus an
original 78/178/78 baseline. At ±0.1 V both physical drivers gave 115/140/115.
These selected points in `evidence/sar-driver-physical.json` do not establish
transfer linearity, ENOB or selection of a production driver.
