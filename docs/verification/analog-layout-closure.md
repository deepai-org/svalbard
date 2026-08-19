# Analog layout closure workflow

This guide records the repeatable workflow used for the GF180 wireline SerDes
cells. It is a practical pre-silicon method for turning behavioral intent into
a transistor schematic, generated physical layout, and reviewable extracted
evidence. It is not a substitute for provider signoff or measured silicon.

## 1. Freeze an executable intent contract

Write the electrical contract before selecting dimensions or drawing layout:

- exact port polarity, Boolean or continuous-time relationship, rate, and load;
- supply, temperature, process, passive, and input common-mode envelopes;
- minimum differential margin, gain, bandwidth, delay, noise, or impedance;
- current, voltage-headroom, and device-reliability bounds;
- programmable controls, safe endpoints, and the observable used to calibrate;
- conditions that are deliberately outside the qualified envelope.

Turn these into measurements in the testbench. A passing waveform image is not
an executable contract. Preserve failed out-of-envelope cases rather than
moving limits after seeing results.

Add a model-provenance contract beside the electrical one. Record which PDK
models, extraction deck, simulator, pad/package/channel models, and variation
dimensions support each claim. Public corner models can demonstrate that an
architecture is plausible and expose speed or headroom failures early; they do
not justify statistical yield, reliability, or foundry-signoff language. Check
the likely device-speed budget with those models before investing in detailed
layout, then repeat the budget with extracted loading as soon as one physical
signal-path unit exists.

Use a three-level requirement ladder:

- **Required envelope:** the actual constrained product/interface requirement.
- **Design envelope:** deliberately tighter internal targets, such as 25%
  overspeed, 1.5--2x required bandwidth, reduced input amplitude, doubled load,
  earlier settling, extra jitter/noise tolerance, and unused trim range.
- **Exploratory stress:** intentionally excessive cases that reveal failure
  mechanisms but are not required for qualification.

Keep architectural rates straight when applying guardband. A half-rate cell
serving a 2.5 GT/s stream receives decisions at 1.25 Gupdates/s; 1.5--1.75
Gupdates/s is a reasonable design target, while 2.5 Gupdates/s is a useful 2x
overspeed stress rather than the primary PVT contract. Record all three levels
so an aggressive failure is not mistaken for failure of the required function.

Do not turn "large margin" into indiscriminate area or current. Wider devices
add input and output capacitance, longer resistors add RC delay, larger current
consumes voltage headroom and worsens EM/IR, and a larger cell sees more process
and thermal gradient. Prefer explicit electrical guardbands and redundancy,
then size only where extracted evidence shows the limiting mechanism improves.
When several harsh dimensions are stacked, assign and record a separate
minimum functional margin instead of silently applying a nominal-amplitude
threshold to an intentionally degraded stimulus.

## 2. Close topology and polarity before optimization

Build the smallest real transistor circuit that expresses the intended
topology. First test truth, polarity, DC operating points, and a short nominal
transient. A clean but inverted result is a circuit error; do not compensate in
the checker.

Sweep the control that is expected to absorb silicon variation. Require a
contiguous electrically valid window and select the best code away from both
endpoints. Separately require that the realizable bank extends beyond the
performance target by the declared design guardband. A pair of codes that only
brackets the target proves interpolation, not useful tuning margin. One passing
trim code is evidence of a brittle nominal point, not calibration range. Use
finer codes only when the eventual bias or control generator can implement them,
and verify monotonicity in the polarity the controller will actually use.

## 3. Run schematic PVT as grouped calibration

Treat one process/passive/supply/temperature/common-mode combination as an
environment and all candidate control codes as its calibration search. Record:

- whether every simulation completed;
- the count and contiguous range of passing codes;
- the selected code and its distance from the trim rails;
- worst selected electrical margin, current, and headroom;
- the selected-code distribution across all environments.

Failure clustering is more useful than an aggregate percentage. Group failures
by temperature, process, passive corner, supply, and common-mode before changing
the circuit. For example, failures confined to hot corners with adequate DC
headroom usually point toward steering transconductance, while failures at low
supply with collapsed output common-mode indicate stack headroom.

When passive delay trimming approaches a target but loses oscillation as load
resistance falls, classify the failure as loop gain rather than frequency range.
Do not keep shaving the load. Separate signal-path and regenerative-tail
strengths and sweep them independently. Uniformly strengthening every device
often slows a ring because intrinsic and junction capacitance rise along with
transconductance; the extracted CML VCO work instead recovered the difficult
corner with asymmetric tail-current allocation.

Use a modified full-RC deck only as a bounded candidate screen. Preserve every
extracted routing resistor and capacitor, and when changing active width also
scale explicit source/drain area and perimeter parameters. Such a deck answers
"which legal geometry should be regenerated next?"; it is not PEX for the new
geometry and cannot close a corner. Never interpolate below a DRC-proven PCell
limit. Regenerate the parameterized layout and repeat DRC, unique LVS, and
full-RC extraction before admitting a candidate to a qualified bank.

## 4. Plan the physical topology before writing geometry

Draw a coordinate and layer plan for devices, sensitive nodes, crossings, and
ports. The recurring arrangement for current-steering cells is:

1. matched loads directly above their drain/output nodes;
2. interdigitated or equal-centroid switching devices below the loads;
3. the shared-source node short, wide, and local;
4. the tail device directly below the switching pair;
5. differential inputs and outputs on matched upper-metal routes;
6. explicit body connections, dense substrate/well contacts, and a guard ring;
7. wide supply rails and via arrays at every current-carrying transition.

Treat matching context as geometry, not only equal `W/L`.  Put correlated
devices into one compact interdigitated or common-centroid array, add the PDK's
legal dummy fingers at both array edges, keep active members equally distant
from well/guard boundaries, and equalize contact count and orientation.  Use
multifinger devices where extracted junction capacitance and gate resistance
improve, but measure the benefit because diffusion sharing depends on the exact
PCell topology.  Put differential routes side by side on the same layers with
matched bends, via stacks, neighbors, and shielding; equal drawn length on
different metals is not matched parasitic context.

Plan density before final extraction.  Distribute substrate/well taps through
large interiors, reserve symmetric quiet regions for intentional fill, and keep
floating fill away from high-impedance nodes where the deck permits.  Local
bias/reference decoupling must be symmetrically placed and explicitly simulated;
extra MOS capacitance is not automatically benign.  Re-run DRC/LVS/PEX after
dummy, tap, decap, or fill insertion because all four can alter connectivity or
sensitive-node capacitance.

Choose device ordering to equalize both electrical function and route span. A
geometrically mirrored picture can still be electrically asymmetric when one
output joins inner devices and the other joins outer devices with unequal wire.

Plan repeated analog hierarchy with the same care as a matched device array. A
many-to-one clock selector should use a balanced full tree, padding unused
leaves with electrically defined spares when the real leaf count is not a power
of two. Every usable source then crosses the same number and type of selector
stages; a ragged tree quietly creates source-dependent delay, loss, loading, and
jitter. Make each parent sit over the center of its children, reserve distinct
inter-level routing channels, and keep every spare input at a defined quiet
voltage. The extra cells cost area and static current, so include them in the
top-level budget instead of treating balance as free.

## 5. Generate layout from parameterized devices

Use the PDK's Magic parameterized cells for active devices and resistors, then
flatten only the intended top cell and add deterministic routing. Keep repeated
geometry in small Tcl procedures for rectangles, via stacks, terminal straps,
contacts, and ports. The generated MAG/GDS is disposable output; the Tcl source
is the editable design.

Keep stream hierarchy names independent of filesystem paths. In Magic, save the
cell by its legal relative cell name while writing MAG/GDS artifacts to the
working directory separately; an absolute `save` target can leak slashes and
temporary-directory names into the GDS top-cell name even when DRC and LVS pass.
Run a machine-readable off-grid, zero-area, cell-name, and pin-label precheck on
the emitted stream before treating it as an integration macro.

Set the layout tool's coordinate units before issuing any hierarchical
placement. A generator can otherwise interpret intended micron coordinates in
internal database units, overlap every child, and produce thousands of errors
whose apparent cause is misleading. At the parent level, do not assume that a
label alone creates connectivity: paint parent-owned conductor that overlaps
the child port, place the label on that conductor, and prove the resulting pin
order with unique LVS. Keep the repeated child cell immutable; correct assembly
routing in the parent rather than editing fifteen nominally identical copies.

Keep generator helper names out of the layout tool's command namespace. A Tcl
procedure named after a built-in command can make an otherwise sound generator
fail only when that command is reached. Use narrow names such as `make_port`,
run a minimal generation smoke test before the expensive physical flow, and
make the preflight verify that every declared source and wrapper is present and
executable.

Use a second layout database/viewer when it adds independent evidence. KLayout
is useful in batch mode for deterministic GDS/OASIS reads, hierarchy and layer
inspection, renders, XOR/diff, net tracing, and custom geometry checks. In the
current GF180 flow it renders the emitted GDS and makes generator variants easy
to compare; Magic and Netgen remain the qualified DRC/LVS authorities until a
reviewed GF180 KLayout deck is added. Do not call two tools independent when
they merely wrap the same rule deck or extraction result.

Prefer one repeated unit geometry inside a matching array when programmable
tail current can express the required ratio. Besides reducing systematic
mismatch, this prevents mixed-size parameterized cells from quietly moving
their generated terminal/contact geometry relative to hand-authored straps.
If mixed geometry is necessary, derive contacts from cell bounds or explicit
ports and prove each device class with LVS before routing the full array.

Treat every PCell dimension as a geometry dependency, not just a SPICE value.
Derive terminal straps, gate contacts, source returns, route clearances, and
labels from the same parameters or from queried PCell ports. A transistor can
remain electrically legal while a hand-authored strap lands on the wrong part
of its resized terminal. Before a broad simulation, generate a small legal-value
sweep and run DRC on every point. In the current GF180 capacitor geometry, for
example, the smallest attempted interpolation violated local metal rules while
nearby larger values were clean; a numerically plausible parameter is not proof
that the PCell plus surrounding route is manufacturable.

Do not rely on a via-stack helper blindly at route crossings. A stack to M5 also
contains M4, M3, M2, and M1 shapes. Any lower-metal route passing through that
location becomes electrically connected even if the visible top metals differ.
This applies equally to power stacks inside a reused child: inspect all metal
shapes in the landing, not merely the child's advertised top-layer terminal,
before routing a parent bus across it.

Merge or separate neighboring upper-metal transition pads deliberately. Two
same-net pads that nearly touch can leave a narrow spacing notch which is still
a DRC error; overlapping them into one legal shape is often cleaner. Different
nets need independently allocated escape columns and spacing on every layer in
their stacks. A rendered top-metal picture alone cannot establish either fact.

Allocate vertical escape columns with net awareness, not only global spacing.
Repeated terminals on the same net should reuse a nearby legal escape when that
keeps their low-metal terminal straps local. Otherwise a globally unique-column
allocator eventually pushes late devices far from their terminals; the long
horizontal straps can cross or merge unrelated same-row nets even though every
individual via landing is legal. Reserve body-tap columns first and permit a
second forced supply escape only where current density requires it.

## 6. Close DRC and LVS incrementally

Run Magic generation, DRC, and LVS after the first complete route. Interpret
LVS structurally:

- a missing port usually means it was shorted to another labeled net;
- fewer extracted nets than schematic nets means an unintended join;
- a signal net with source/drain fanout usually crossed a local analog node;
- correct device counts with wrong nets usually means routing, not sizing;
- swapped differential pins may be a true polarity error or unresolved circuit
  symmetry; require a unique pin-name-resolved match.

Read the extracted SPICE netlist to identify the exact signal now attached to a
tail, source, drain, or gate. Move the offending track or transition to a layer
and coordinate that does not cross another stack. Re-run both DRC and LVS after
every connectivity edit. The physical gate is zero DRC errors and a unique LVS
match, not merely equal device counts.

## 7. Extract distributed RC and re-simulate the actual cell

Perform coupled full-RC extraction with a documented resistance threshold.
Check the extracted subcircuit pin order and count the generated resistors and
capacitors. Start with the nominal truth/timing sweep; if polarity, settling, or
the calibrated window changes materially, fix layout before running a full
matrix.

Then repeat the same grouped PVT search against the extracted netlist. Cache
reuse must include a SHA-256 of every externally included DUT netlist; comparing
only the testbench text can silently reuse stale simulations after a layout or
schematic change.

For clocked dynamic cells, use an alternating-bit sequence and probe internal
nodes through reset, acquisition, regeneration, capture, and hold. A repeated
symbol can hide retained charge, while output-only samples cannot distinguish
an incorrect sense decision from a correct decision lost at the latch. Change
one physical mechanism at a time, regenerate DRC/LVS/PEX, and reject a larger
reset device when its added sensitive-node capacitance costs more evaluation
margin than its reset current gains.

Assign state retention to exactly one architectural stage. If the downstream
deserializer is already clocked, qualify the analog front end over an explicit
valid aperture and prove setup/hold composition there. Adding a second static
latch can turn a fast regenerated decision into a slower, parasitic-dominated
write path and create stale-decision feedback. The contract must say whether a
cell produces a held value or an aperture-qualified value; both are useful,
but they are not interchangeable.

Close the interface using the composed extracted cells, not two standalone
load capacitors. A downstream differential write port can present several
large NMOS and PMOS gate banks on each rail; this distributed nonlinear load is
not equivalent to the nominal explicit capacitor used in either leaf test. If
the boundary fails, add a local restoring stage or rebudget fanout, then verify
its own extracted delay inside the aperture. Size the retaining latch and the
write branches as a contention ratio: weakening both latch polarities
symmetrically can improve writability without the skew caused by changing only
one polarity. Keep the measurement before the next capture opening so a late
pass cannot be caused by the following symbol.

When one fixed device size cannot close two physically distinct operating
regions, expose a small realizable trim before oversizing the whole path. The
trim must correspond to actual placed devices, have a defined selection
observable, and be verified at each mode boundary. Record mode selection as an
integration requirement rather than implying that a programmable device
calibrates itself.

For a physical tuning bank, preserve three different results in the evidence:

- **member legality:** every selectable tile is independently DRC clean, has a
  unique pin-resolved LVS match, and has its own full-RC extraction;
- **environment coverage:** at least one electrically valid member and control
  setting satisfies the required target in every declared environment;
- **bank margin:** the aggregate valid range reaches the separately declared
  low and high design limits, with useful distance from control and member
  endpoints.

Do not collapse those into a single pass bit. The current VCO example contains
one center tile plus eleven added variants: twelve physical layouts in total.
The eleven added variants are individually DRC clean, unique-LVS, and full-RC
extracted, and the aggregate bank closes 5/5 declared target environments with
full +/-2% frequency guardband in 5/5. These counts come from the checked-in
[VCO bank evidence](../../ip/blocks/analog/wireline_serdes/pll/vco_bank_result.json),
not from the earlier perturbed-deck screen. Keep evolving project counts in
machine-readable evidence and block status, not only in this workflow guide.
The physically extracted two-input selector primitive now has a safe
break-before-make transition and has been composed directly with two complete
extracted VCOs. The checked cases include powered-down and live-aggressor
neighbors, both selected branches, and startup of a newly selected ring; the
worst powered-down feedthrough is recorded in
[selector composition evidence](../../ip/blocks/analog/wireline_serdes/pll/selector_vco_composed_result.json).
That closes the primitive. The subsequent balanced twelve-used/four-spare tree
is also physically closed and passes its extracted all-leaf/PVT and full-depth
handoff contract; its checked result is
[selector-tree evidence](../../ip/blocks/analog/wireline_serdes/pll/selector_tree_result.json).
This still does not close the oscillator bank composition: the twelve extracted
VCOs, startup assists, power controls, and sequencing controller must be wired
to the tree and verified together.

Reuse a physically closed weighted-summing cell as a selector when its endpoint
controls truly shut off the unselected tail and its output stage isolates the
shared node. Qualify that role separately at the higher clock rate: keep the
unselected input toggling at a discriminating frequency, measure every selected
cycle rather than only average frequency, and search one bias code that passes
both branches and the complete input-common-mode envelope. During handoff,
require explicit nonoverlap and disable the restoring output stage in the dead
interval. A powered-down victim can still show a tiny capacitively injected
sinusoid with many zero crossings; judge isolation by absolute amplitude and
attenuation relative to the active clock, not by crossing count alone.

When composing selectors hierarchically, verify more than the root waveform.
Exercise every real leaf while all other leaves remain live at distinguishable
frequencies, cover representative PVT environments and the complete input
common-mode range, and measure accumulated swing, frequency error, cycle jitter,
and total current. Switch between leaves whose paths diverge at the root so the
handoff exercises every level. The controller must force all old-path stages
off before enabling the new path, including output buffers; independent analog
control pins are only hardware capability, not proof that forbidden overlap is
unreachable. Preserve physical-only DRC/LVS/PEX evidence separately from the
all-leaf extracted switching result so a simulation failure cannot be hidden by
a clean layout—or vice versa.

### Proven physical iteration ladder

Use this order when an extracted cell misses a corner:

1. reproduce the miss with the checked-in extracted cell and classify it as
   truth/polarity, headroom, loop gain, load, or range;
2. screen one mechanism at a time while retaining the original distributed RC;
3. reject parameter values outside a DRC-proven geometry interval;
4. make every affected layout coordinate depend on the chosen parameter;
5. regenerate each candidate and require DRC, unique LVS, and full-RC PEX;
6. simulate the repeated or composed extracted structure, not a lumped proxy;
7. report required-target coverage and design guardband independently; and
8. keep the screening result only as provenance for why the physical candidate
   was built, never as its qualification evidence.

## 8. Add stress dimensions in layers

After extracted PVT closure, add tests according to the block's physical risks:

- output load and load imbalance;
- minimum differential input and input common-mode;
- edge rate, skew, aperture displacement, jitter, and frequency;
- supply ripple over relevant frequencies and phases;
- crosstalk or simultaneous switching from neighboring blocks;
- startup, reset, sequencing, and calibration search behavior;
- bounded device/passive variation or mismatch only when the model is valid;
- pad, ESD, bond, package, board, and channel models when selected.

For an oscillator, compose the loop from repeated extracted delay tiles rather
than adding a lumped estimate of one tile's parasitics. Sweep only realizable
control values and require contiguous electrically valid codes, correct local
tuning polarity, both early and late period measurements, sustained
differential swing, bounded current, and a startup deadline. Record the valid
minimum and maximum frequency as well as the codes nearest the target. A target
bracket is useful calibration evidence; it is not a substitute for explicit
frequency headroom above and below the target.

A seeded initial condition proves attraction to the oscillating trajectory; it
does not prove autonomous startup. Separate three increasingly strong claims:

- **seeded trajectory:** a small `.ic` perturbation reaches stable oscillation;
- **deterministic assisted startup:** an extracted, physically placed actuator
  starts the ring during a real supply ramp without `.ic` or `uic`, then turns
  fully off before steady-state measurements; and
- **unassisted statistical startup:** valid device-noise and mismatch models
  demonstrate startup probability and time with a declared confidence.

For deterministic assistance, attach a symmetric matched device to each side
of one differential node so normal-operation loading is balanced. Exercise
both kick polarities, sweep pulse strength and timing, and verify the composed
full-RC ring plus assist over every declared startup environment. Measure the
startup deadline from the released kick, late-period drift, swing, current,
frequency loading, and residual off-state disturbance. A no-kick run is a
useful control but is not by itself statistical evidence: numerical asymmetry
can start a mathematically symmetric oscillator. The assist also needs reset
sequencing and a controller-visible completion or timeout contract.

Keep startup, supply pushing, phase noise/jitter, mismatch, safe bank selection,
and closed-loop PLL behavior as separate claims. Fit deliberate delay
capacitance from at least two DRC/LVS/PEX-clean physical points;
schematic-only capacitor scaling can miss routing delay by a large factor.
Treat loss of loop gain and missed frequency range as different failures: the
former needs restored transconductance/regeneration or less loading, while the
latter may need a different legal capacitance or load member. Re-extract either
change.

Use the same fixed selected code throughout one stress environment unless the
test is explicitly measuring recalibration. Otherwise the sweep can conceal a
dynamic failure behind per-case retuning.

## 9. Render and inspect the real GDS

Generate a full-resolution raster from the emitted GDS and inspect it after
major routing revisions. Annotate topology, dimensions, DRC/LVS state, and PEX
counts, but keep the drawing itself unobscured. Visual review catches long
sensitive nodes, remote tails, sparse contacts, nonlocal loads, and asymmetries
that netlist comparison intentionally ignores.

## 10. Make the evidence reproducible and bounded

Every committed flow should:

- use a digest-pinned native-architecture container and locked PDK;
- refuse heavy work below the repository and Docker free-space threshold;
- cap CPUs, memory, swap, PIDs, network access, and wall time;
- use `timeout --kill-after=30s` so a container cannot ignore the soft timeout;
- serialize heavy jobs with a lock;
- write generated decks, logs, PEX, GDS, and waveforms to scratch;
- retain failed scratch and delete successful intermediates only after copying a
  compact numeric summary and review image;
- bind summaries to source and result hashes;
- run repository validation before committing.

Use `scripts/run_analog_flow.sh` for the common host boundary. A block wrapper
declares only its source directory, timeout, CPU/RAM cap, container command,
and copied artifacts. The shared harness owns the digest-pinned image check,
minimum disk/RAM checks, exclusive heavy-job lock, read-only/networkless Docker
sandbox, bounded timeout, failure retention, and successful scratch cleanup.
Run `make analog-flow-preflight` to validate every declaration and the local
pinned image without launching simulation. Keep circuit-specific sequencing
inside the block's mounted `container_flow.sh`; the common harness must not
hide which analyses or signoff gates a block actually runs.

Commit and push at meaningful gates: schematic PVT closure, physical DRC/LVS
closure, and extracted/stress closure. Do not present a schematic checkpoint as
a finished macro or a core-only result as a complete PCIe interface.

## Remaining signoff boundary

This workflow produces disciplined public-model pre-silicon evidence. Final
analog-top freeze still requires provider-qualified models and reviews,
post-fill extraction, antenna/density/ERC, EM/IR and reliability analysis,
pad/ESD/package/channel closure, hierarchical and flattened verification,
independent correlation where practical, and measured-silicon correlation.
