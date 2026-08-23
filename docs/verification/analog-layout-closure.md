# Analog layout closure workflow

This guide records the repeatable workflow used for the GF180 wireline SerDes
cells. It is a practical pre-silicon method for turning behavioral intent into
an intended transistor/passive circuit, generated physical layout, and
reviewable extracted evidence. It is not a substitute for provider signoff or
measured silicon.

Closure is always relative to a named physical boundary. A leaf can be closed
while its parent remains only a schematic composition. Instantiating several
leaf PEX subcircuits in SPICE proves an electrical composition under the stated
interconnect model; it does not prove that a placed-and-routed parent exists.
Call a hierarchy physically closed only after its actual parent-owned routes,
ports, and shared resources pass DRC, unique pin-resolved LVS, full-RC
extraction, and the boundary-level electrical contract.

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

Keep circuit intent separate from layout strategy. The circuit contract says
which transistors and passives may be used, which topology or topology family
is intended, what can be programmed, and which behavior must hold. The layout
generator is free to optimize fingering, placement, matching pattern, routing,
and legal passive geometry only inside those constraints. If layout-driven
changes alter device count, connectivity, terminal order, or control semantics,
they are circuit revisions and must re-enter schematic verification rather than
being hidden as physical optimization.

SPICE and layout have different jobs in this loop. The intended schematic is
the source circuit for topology and pre-layout simulation; it is not generated
from the drawing. The layout generator realizes that circuit as legal geometry,
and extraction then generates a parasitic-rich SPICE view from the geometry.
Schematic SPICE can reject a bad circuit before layout, while post-layout SPICE
can reject a bad physical realization. Neither result substitutes for the
other, and extraction does not repair an electrically wrong schematic.

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
Derive that rate from an executable clocking diagram, not from the serial bit
rate by habit. In the present dual-edge PCIe receiver, the phase detector,
phase interpolator, slicer timing, and deserializer are half-rate boundaries.
A 2.5 GHz ring is therefore an architectural experiment; a 1.25 GHz clock with
both edges qualified is the required clock contract. Changing that clocking
choice changes every downstream aperture and phase relationship, so record it
as a system revision rather than quietly relaxing an oscillator target.

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

At a clock or data boundary, define function before defining amplitude. A
divider output with large differential swing can be a self-oscillation or a
wrong-rate lock. Measure the actual loaded input period and require the output
period, phase sequence, duty cycle, and late-period drift appropriate to the
intended function before applying swing or common-mode gates. Conversely, a
correct zero-crossing ratio at millivolt amplitude is not useful regeneration.
Both the functional relation and the electrical margins must pass in the same
case.

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

Once independent bias axes prove useful, they must become independent physical
ports and routes in every repeated child and complete parent. Regenerate and
extract that topology before crediting the extra degree of freedom. A focused
screen can establish that the mechanism closes a known corner, but it does not
inherit the original bank's other corners: rerun the combined physical members
over the complete environment set. Also budget the two realizable bias sources,
their resolution and settling, and a calibration mapping; two ideal voltage
sources in a testbench prove controllability, not an implemented controller.

Qualify the physical bias generator against the voltages the characterized
load actually needs. Require monotonic transfer, safe off and high endpoints,
a nearest realizable code within the load's allowed bias error for every
characterized control point, reference current or power, and worst-carry
settling into an extracted or conservatively bounded gate load. Record minimum
and maximum steps as diagnostics, but gate them only when the consumer really
requires a uniform or bounded increment. A minimum code step is not a
performance benefit by itself: rejecting a smaller step can discard improved
resolution. Conversely, an endpoint span alone can hide coarse unreachable
settings; the target-error contract catches that directly. If two DAC channels
are programmed independently, do not impose a complementary-sum invariant
merely because a convenient sweep drives one code upward and the other
downward. Record the environment-specific target-to-code map so system
calibration can search real hardware rather than ideal voltage-source values.
Derive the settling deadline from startup and lock sequencing with explicit
margin; do not promote a convenient transient stop time into a requirement.

Do not assume that additional active width can recover a routed speed miss.
In a retained full-RC parent deck, scaling input, latch, and tail devices over a
wide range increased current but reduced oscillation frequency in the limiting
hot environments. That result is diagnostic, not a new physical qualification:
it says that added device capacitance and the existing parent interconnect are
dominant enough that brute-force transconductance is the wrong lever. When this
happens, stop increasing width and compare structural alternatives: shorten the
regenerative loop, compact or integrate repeated stages, reduce high-swing
route length, remove unnecessary via-stack capacitance, or revise the stage
topology. Re-run the screen after each single-mechanism change, then realize the
winner as legal geometry.

Size an inverter chain from both ends, not only from the final load. A large
last stage can make the preceding stage the real bottleneck because its gate
capacitance is charged before any of the advertised output strength is useful.
In the dual-capture cell, a 16/8 um first inverter drove a 64/48 um output
inverter even though the external load was only 50 fF. Halving the last stage
reduced extracted parasitics from 2,202R/1,570C to 1,957R/1,400C and raised the
limiting 2.5-GT/s FF/hot captured differential from 0.289 V to 1.128 V at the
original 380 ps write pulse. Diagnose each internal transition in a tapered
chain; sometimes removing downstream width improves both speed and current.
Apply the change symmetrically, regenerate geometry, and replay the slower-rate
and PVT parent contracts because a faster internal node alone is not closure.

Search already-realizable controls jointly across an extracted producer,
optional restoring stage, and consumer before changing topology. Require a
contiguous passing region in that multidimensional control space, not an
isolated coordinate, and preserve enough distance from every control endpoint
for calibration error and drift. Stop a sweep when the intended lever moves the
limiting metric monotonically in the wrong direction; more current or gain in
one stage can reduce its input headroom, load the producer, or overdrive a
regenerative consumer. A programmable interface provides recoverable silicon
margin only when a system-visible observable and search procedure can select
the passing region.

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

Audit extracted coupling between every clock/output aggressor and nearby bias
or reference net, not just coupling between the differential rails. A route on
an adjacent metal can be electrically isolated yet broadside-coupled for its
full length. Move a high-impedance bias escape to an orthogonal or separated
track and compare the named coupling capacitors before and after regeneration;
then simulate it with the realizable bias-distribution impedance. An ideal
one-ohm testbench source can hide a layout coupling problem that a remote bias
tree will expose.

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

Make a physical boundary drawing before composing extracted children in a
system testbench. It must show child origins, pin layers, differential escape
tracks, every via-stack footprint on all intermediate metals, supply and bias
spines, startup/reset devices, and the parent port order. This catches a common
false milestone: a hierarchy whose leaf circuits work together in SPICE but
whose real parent routes have never been drawn or extracted. Build the smallest
useful parent first--for example, one oscillator band containing its repeated
delay cells, output buffer, and startup assist--then replicate that verified
macro at the bank level.

Treat a via stack as geometry on every intermediate metal, not as an abstract
change from its first to last layer. A gate route that rises at the same x/y as
a source contact can short through an otherwise invisible intermediate M3 or
M4 square even when its visible trunk is on M5. Before drawing a long upper-
metal route, escape the sensitive terminal on its existing low layer into a
reserved open channel, then rise. Likewise, do not extend terminal metal over
a guarded resistor merely to cure spacing: its guard metal may be the body/VSS
connection. Use the already-connected upper terminal layer and start the next
via stack there. DRC can accept both mistakes; pin-resolved LVS is the required
connectivity test.

For a short regenerative ring, prefer a folded column of repeated stages over
a wide row when that keeps each stage-to-stage connection local. Put adjacent
stages one pitch apart, escape both polarities on mirrored columns outside the
child guard rings, and run quiet supply/control spines on separately reserved
columns. The useful comparison is extracted parent resistance, capacitance,
and oscillation frequency—not bounding-box compactness. In the current GF180
work, replacing an approximately 800 um row-spanning feedback path with a
vertically folded parent materially reduced extracted routing resistance and
improved nominal speed; a visually compact row whose routes crossed child
interiors instead added capacitance and was slower. Compactness is valuable
only when it shortens the electrically sensitive path without creating new
crossings or dense via stacks.

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

Use the schematic hierarchy and physical hierarchy as one interface contract.
Give each parent a single canonical pin order, instantiate the same child
subcircuits used to generate the layout, and reject wrappers that silently
rename, swap, or omit differential terminals. An LVS match against a convenient
alternate schematic is not evidence for the circuit that is later simulated.

Keep generator helper names out of the layout tool's command namespace. A Tcl
procedure named after a built-in command can make an otherwise sound generator
fail only when that command is reached. Use narrow names such as `make_port`,
run a minimal generation smoke test before the expensive physical flow, and
make the preflight verify that every declared source and wrapper is present and
executable.

Use a second layout database/viewer when it adds complementary evidence. KLayout
is useful in batch mode for deterministic GDS/OASIS reads, hierarchy and layer
inspection, renders, XOR/diff, net tracing, and custom geometry checks. In the
current GF180 flow it renders the emitted GDS and makes generator variants easy
to compare; Magic and Netgen remain the project DRC/LVS authorities until a
reviewed GF180 KLayout deck is added. None of these project checks is provider
signoff. Do not call two tools independent when
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

Do not infer a resized PCell terminal from its old center coordinate. Inspect
the emitted geometry or query its ports, then express terminal locations as a
function of the dimensions. The GF180 MOS cap used by the VCO, for example,
moves its contacted diffusion approximately with `L/2` plus a fixed enclosure;
a fixed hand strap was legal at short lengths and landed beside the wrong edge
at longer lengths. Even the corrected strap can enter a reserved signal column
for only a middle range of lengths, so parameterize placement or use a
segmented cap array as well as parameterizing the strap. A generator's legal
domain is the intersection of PCell legality, route-corridor legality, and LVS
identity—not merely the PDK device's numeric parameter range.

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

Treat the parent power grid as an analog signal path. A narrow parent supply
route can pass DRC and unique LVS yet add enough extracted resistance to
collapse a downstream limiter or divider at a slow/high-temperature corner.
Use short wide upper-metal overlays, continuous child-port overlap, legal via
arrays, and explicit branch continuity; then re-run the complete parent PEX.
DRC proves geometry and LVS proves topology, but neither proves that the
delivered voltage/current preserves the calibrated operating window. Compare
internal rails and function before and after a PDN revision so an apparent
device-bias fix is not masking route resistance.

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

Resolve differential polarity at the circuit/layout boundary explicitly. If a
symmetric stage is functionally polarity-insensitive, the physical ordering may
legitimately invert its named pair, but the intended schematic, port contract,
and downstream phase convention must be updated to describe that connectivity.
Re-run unique pin-resolved LVS and electrical verification; do not hide a swap
in measurement code or rely on graph symmetry to make ambiguous pins pass.

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

Bind the electrical result to the exact physical result. The checked summary
should contain hashes of the generator sources, intended schematic, emitted
layout or its deterministic physical report, and the precise PEX file included
by the simulator. The physical checker and electrical checker must agree on the
PEX hash. Copying or regenerating a similarly named extraction between those
steps creates an unreviewable identity gap even when both checks pass.

Require that identity for every extracted leaf in a composed simulation. Small
converters, restorers, bias cells, and clock helpers are not incidental plumbing:
each needs a passing physical record whose PEX hash matches the bytes actually
included by the parent test. Leaf DRC/LVS evidence without this hash join proves
that some legal layout existed, not that the simulated composition used it.

When a calibrated geometry would invalidate existing evidence, version the
physical macro instead of silently replacing it. Keep the old schematic, PEX,
physical record, and scoped claim immutable; give the revised circuit and PEX
subcircuit a new cell name. This makes regressions and improvements comparable
and prevents a new source hash from retroactively breaking an earlier release.

Preserve the exact extracted deck used by a composition run. Some extraction
tools embed timestamps or other nondeterministic metadata, so regenerating
unchanged geometry can change the byte hash. Do not weaken equality checks or
silently substitute the new file. Either archive the checked deck with its
physical result, or introduce and review an explicit canonicalization step that
removes only proven-nonsemantic fields before hashing. A semantic comparison is
useful as an additional diagnostic, but it does not identify the bytes a
simulator actually included.

Timestamp removal may still be insufficient: the current extractor can reorder
parasitic elements and internal node names between unchanged runs. In that case,
promote one DRC/LVS-bound PEX to an immutable release input and make every
electrical run hash those exact bytes. Regenerate geometry separately to prove
that the generator still reaches zero DRC and unique LVS, and report both the
fresh extraction hash and simulated-release hash. Do not claim byte-deterministic
extraction when only the electrical topology appears equivalent.

For clocked dynamic cells, use an alternating-bit sequence and probe internal
nodes through reset, acquisition, regeneration, capture, and hold. A repeated
symbol can hide retained charge, while output-only samples cannot distinguish
an incorrect sense decision from a correct decision lost at the latch. Change
one physical mechanism at a time, regenerate DRC/LVS/PEX, and reject a larger
reset device when its added sensitive-node capacitance costs more evaluation
margin than its reset current gains.

For a half-rate serializer, separate three claims that a static `10` word can
otherwise blur: correct complementary clock selection, arbitrary changing-word
serialization with each lane updated only in its unselected aperture, and the
setup/hold window at the real loaded consumer. Re-run calibration at every
claimed serial rate. In the current GF180 work, a standalone mux comfortably
serialized the static word yet barely drove the real TX gate bank at 1.25 GT/s
and failed changing words at 2.5 GT/s; a schematic limiter and reused clock
restorers did not close the slow/hot environment. The robust fix was
architectural: merge clock-steered EVEN/ODD pairs into the output driver so the
large internal gate node disappears. The regenerated parent then passed exact
PEX at both rates. Prefer removing a parasitic boundary over adding cascaded
restoration, and preserve the failed composition as evidence for that choice.

Assign state retention to exactly one architectural stage. If the downstream
deserializer is already clocked, qualify the analog front end over an explicit
valid aperture and prove setup/hold composition there. Adding a second static
latch can turn a fast regenerated decision into a slower, parasitic-dominated
write path and create stale-decision feedback. The contract must say whether a
cell produces a held value or an aperture-qualified value; both are useful,
but they are not interchangeable.

For interleaved or dual-edge decisions, derive one validity interval per lane
from the exact extracted parent before assigning a shared conversion or write
clock. Opposite-edge decisions can have disjoint safe windows even when both
leaves pass with ideal stimuli. If no common interval exists, keep the clocks
independent through capture or retime each lane locally; changing a delay value
cannot repair an architectural non-overlap. Exercise changing data in both
lanes and sample each final retained output before claiming the composition.

Close every interface using the exact extracted producer and consumer, not an
ideal source on one side and a standalone load capacitor on the other. Measure
the producer's loaded amplitude, common mode, frequency or edge rate, startup,
and current while the consumer presents its real distributed nonlinear input
capacitance. A small loaded-frequency shift does not prove adequate drive: a
clock can retain its frequency while losing the amplitude or slew required for
downstream regeneration. Likewise, leaf PEX passes do not compose transitively;
the boundary needs its own environment-by-environment calibration result.

For an AC-coupled differential boundary, initialize the coupling capacitor from
the settled producer-minus-consumer common-mode difference for that environment.
A fixed fraction of VDD can inject a fictitious startup transient or hide a real
one as common mode moves across PVT. Label this initial state as a fixture
condition, never as a hardware trim unless a circuit actually controls it.

When a restoring chain crosses a unit-interval boundary, score integer latency
explicitly. Search a small bounded set of whole-UI alignments, require the raw
producer to hold signed margin for a declared interval, and leave a declared
settling interval before sampling the consumer. Normalize phase modulo one full
cycle. A link aligner can absorb a deterministic whole-UI delay; it cannot absorb
wrong polarity, data-dependent latency, or a fractional aperture failure.

Do not scale every downstream pulse width merely because the serial UI shrinks.
Clock placement and repetition rate scale with the architecture, but a static
CMOS write cell still needs its extracted transistor-level write duration. In
the 2.5 GT/s capture composition, halving a previously qualified 380 ps write
pulse left one retained lane wrong even though both converter outputs were
strong. Keeping the physical write duration, and exposing sense width and
capture delay independently, allowed the slow-device cases to settle within
the 800 ps half-rate period. Keep acquisition width, delay, write width, setup,
hold, recurrence, and observation time as separate contracts; prove that their
actual pulses do not overlap the next half-rate cycle.

Measure every interleaved output relative to the event that owns that lane. In
the dual-edge receiver, scoring both outputs from the ODD event sampled the EVEN
lane after its next capture had already started and produced a false failure.
Event-relative measurements, not a shared convenient timestamp, are part of the
executable timing specification. After this correction and physical timing
calibration, the exact-PEX capture stack passed the five representative
environments under the declared combined channel, jitter, duty-cycle, and rail-
ripple stress; the numeric evidence belongs in the living status/results rather
than being frozen into this workflow.

If that boundary fails, first classify whether the producer collapses, the
consumer lacks regeneration, or the composed function locks incorrectly. Use
existing legal bias controls and one-mechanism retained-RC screens before
adding circuitry. Add a local limiting/restoring stage only after simpler
levers fail, then physically close it and qualify its input loading, output
amplitude and common mode, delay, current, and the downstream functional
relationship in one exact-PEX composition. An ideal-wire composition of
extracted children closes only that electrical boundary; the parent remains
open until child placement and parent-owned interconnect are DRC/LVS/PEX clean
and re-simulated.

Close a large signal path through successive physical parents, starting with
the shortest bandwidth-critical chain whose child interfaces are already
electrically qualified. Preserve natural internal nodes as explicit parent
probe ports when stage-by-stage scoring is needed; do not add long observation
stubs or active probe loads. In the current receive-spine closure, retaining the
amplifier and restorer differential nodes made the old contract directly
replayable after the amplifier, limiter, sampler, supplies, and their parent-
owned routes became one extraction. The simulator must include either that
parent PEX or its child PEX files, never both. Bind every retained historical
result to its old runner hash when teaching the runner about the new hierarchy,
then give the routed-parent result its own claim and evidence files.

Do not infer transformed child-pin coordinates from a MAG file by dividing its
database integers by an assumed micron scale. A child generated under a
different Magic unit convention can appear at twice its emitted GDS size even
though the parent transform itself is correct. Query the emitted hierarchy's
recursive GDS labels and conductive shapes with their actual transforms, then
verify the landing on every participating layer. A label identifies a net, not
a safe via site: in the rotated termination, the visible metal3 RXP label lay
under a metal4 enable route and seven metal5 enable trunks crossed the same
bus. A full stack at the label shorted controls despite correct-looking
coordinates. Escaping on the pin's native metal beyond the crossing bank and
changing only to the consumer's native layer produced the shorter symmetric
route and the unique LVS match. Preserve the failed LVS fragments because
their device fanout is often the fastest way to identify which hidden layer
was accidentally joined.

When interleaves expose separate physical clock ports, keep their phase controls
independent through parent validation. In the routed RX front end, a shared
converter schedule had no passing fast/hot overlap even though each leaf was
qualified. A bounded -50 ps ODD sense/regeneration deskew closed both converter
and final-capture margins while zero or opposite capture-only skew did not.
That result justifies a realizable deskew code; it does not justify an arbitrary
per-corner delay unless the clock generator, observable, and calibration search
are later implemented and extracted.

A downstream differential write port can present several large NMOS and PMOS
gate banks on each rail; this distributed nonlinear load is not equivalent to
the nominal explicit capacitor used in either leaf test. Size the retaining
latch and write branches as a contention ratio: weakening both latch polarities
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

Do not collapse those into a single pass bit. Keep evolving member counts,
corner counts, and measured extrema in machine-readable evidence and the
[living analog status](pcie-analog-status.md), rather than copying numbers into
this workflow where they become stale. For a concrete example, the checked-in
[VCO bank evidence](../../ip/blocks/analog/wireline_serdes/pll/vco_bank_result.json)
separates member legality from aggregate range, while the
[selector composition evidence](../../ip/blocks/analog/wireline_serdes/pll/selector_vco_composed_result.json)
and [selector-tree evidence](../../ip/blocks/analog/wireline_serdes/pll/selector_tree_result.json)
separate primitive isolation from hierarchy-level all-leaf and handoff checks.
None of those leaf or selector claims alone closes a physically routed
oscillator-bank boundary.

Reuse an expensive unchanged qualification by hash when its scope still
matches; do not rerun it merely to place every case in one process invocation.
The composition checker must verify the source evidence hash, physical member
count and status, PEX-to-simulation identities, initial-condition policy,
environment-set equality, and exact expected case count before merging any
intervals. Require all physical PEX identities across old and new evidence to
be distinct. Raw extractor text can vary in harmless ordering or formatting
between runs, so bind every simulation to the exact PEX from its own run and
check repeated electrical cases semantically: classification, frequency,
drift, startup, current, and bounded numeric tolerance on printed measurements.

Evaluate a tuning bank as a set of realizable points, not as the numeric span
between its slowest and fastest passing samples. Within each physical member,
form intervals only between adjacent control settings that both pass all
electrical gates; merge overlapping intervals across members; then ask whether
the union continuously covers the required and design bands. A global minimum
below the target and a global maximum above it can still hide an unreachable
frequency hole. Preserve the selected member and control at each boundary so a
future calibration algorithm has an implementable mapping rather than an
existence claim.

After a candidate family closes, minimize the selected physical bank against
the same connected-interval contract. Enumerate subsets from smallest to
largest and accept the first whose realizable interval union covers the design
band in every environment; a global endpoint test is still insufficient. Keep
all rejected candidates as evidence, but do not pay their area, inactive
loading, power-gating state, selector depth, and calibration complexity in the
implementation. Re-run composition with the selected subset because removing
members changes routing and shared loading even when bare-bank coverage is
mathematically preserved.

Physical legality is necessary but orthogonal to electrical coverage. A bank
whose every complete parent is independently zero-DRC, uniquely LVS-matched,
and full-RC-extracted can still fail most PVT environments after parent-owned
feedback, supply, startup, and selector-load parasitics are included. Therefore
run the aggregate bank calibration against each complete parent PEX before
calling the coarse-member set closed. If coverage is lost only at this
boundary, retarget the physical architecture or member geometries; do not cite
the clean member count as evidence that the bank works.

When a complete physical bank misses one side of PVT, first ask whether the
requested rate belongs to the selected architecture. The folded full-rate VCO
parents showed that legal geometry and reduced interconnect can improve the
nominal result while slow-device/hot environments still remain fundamentally
below 2.5 GHz. Increasing active width then raised capacitance and did not
recover the corner. That combination is evidence to revisit the clocking
architecture or stage topology, not justification for extrapolating another
oversized member. Preserve the failed full-rate bank as falsification evidence
and qualify the architecturally correct half-rate bank independently.

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

At each composed boundary, maintain a claim matrix rather than a single
"validated" label. At minimum, distinguish topology/polarity, DRC, unique LVS,
PEX identity, nominal function, PVT calibration range, startup/reset, shutdown,
handoff, aggressor isolation, current/headroom, jitter/noise, and statistical or
model-validity limits. Mark unrun rows as unrun. A lower-level pass can be cited
as inherited evidence only when the parent preserves the relevant loading,
supply, substrate, temperature, and control assumptions.

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

### Simulation escalation ladder

Full-RC extracted SPICE is the central cell- and composition-level tool, not a
universal physics proof. Escalate only the structures and mechanisms for which
its lumped compact-model assumptions are weak:

1. **Compact-model SPICE:** DC, transient, AC, corners, startup, calibration,
   loading, and exact-RC post-layout composition. This remains the regression
   foundation because it can exercise the complete transistor circuit.
2. **Statistical circuit simulation:** global process plus local mismatch for
   offset, gain, trim coverage, oscillator startup/frequency, and yield. Use
   only provider-qualified statistical models and preserve sample count,
   estimator uncertainty, and random seeds. Fixed `FF/SS` corners do not prove
   matching yield; [GF's fixed-corner model guide](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/HV/HV_2_4.html)
   notes that those corners primarily bound static logic delay and cannot cover
   every analog sensitivity. Its separate
   [statistical-model guide](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_9_1.html)
   describes global manufacturing variation.
3. **Noise and timing-tail analysis:** device noise for receiver input-referred
   noise and slicer error, and periodic steady-state/phase-noise or sufficiently
   long transient-noise analysis for PLL/CDR jitter. Deterministic jitter and
   ripple injection are useful sensitivity tests, but they do not establish a
   random-jitter distribution or BER tail by themselves.
4. **2.5-D/3-D electromagnetic extraction:** solve pads, ESD structures,
   package/bond wires, long top-metal differential routes, inductors, and other
   electrically large or strongly coupled structures as frequency-dependent
   S-parameters or broadband equivalent circuits. Compose the passive model
   with the nonlinear transistor PEX in circuit simulation. For PCIe Gen1 the
   1.25-GHz Nyquist frequency is not the EM cutoff: edge harmonics, return-path
   discontinuities, mutual inductance, and resonances extend the required model
   bandwidth well above Nyquist.
5. **Power, substrate, and electrothermal analysis:** extracted transient PDN
   impedance and EM/IR for shared rails; substrate-network or field-solver
   coupling from the large-signal TX/clock blocks into the RX; and thermal maps
   fed back into temperature-dependent circuit models when self-heating or
   gradients are material. A uniform hot SPICE corner cannot represent a local
   TX-to-RX temperature gradient.
6. **Reliability and protection verification:** foundry current-density limits,
   via/contact current, voltage overstress, aging where qualified models exist,
   latch-up, antenna, density/fill, and ESD clamp/pad simulations plus the
   provider's structural checks. Re-extract after final fill. Functional SPICE
   success does not prove lifetime or protection robustness. Apply the actual
   temperature-dependent line and via limits from the
   [GF180 electromigration rules](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_2.html),
   not a generic current-density heuristic.
7. **Device/structure TCAD:** reserve drift-diffusion or higher-order device
   simulation for genuinely custom devices and poorly compact-modeled physics,
   such as a novel high-voltage/ESD structure, avalanche behavior, or unusual
   isolation. It is normally the wrong way to re-prove ordinary foundry MOSFETs:
   calibrated foundry compact models are faster and more relevant to circuit
   corners. TCAD without confidential process profiles can look more physical
   while being less accurate.

Close the loop with package/board measurements and silicon characterization.
No amount of pre-silicon model depth establishes model error outside the data
used to build the models. Treat simulation levels as complementary claims and
record which one supports each top-level guarantee; do not replace a missing
statistical, EM, or reliability result with a larger transient-SPICE margin.

For an oscillator, compose the loop from repeated extracted delay tiles rather
than adding a lumped estimate of one tile's parasitics. Sweep only realizable
control values and require contiguous electrically valid codes, correct local
tuning polarity, both early and late period measurements, sustained
differential swing, bounded current, and a startup deadline. Record the valid
minimum and maximum frequency as well as the codes nearest the target. A target
bracket is useful calibration evidence; it is not a substitute for explicit
frequency headroom above and below the target.

For oscillator supply/reference disturbance, measure consecutive output cycles
rather than only an average period before and after injection. Use the selected
realizable code for each PVT environment, compare every stressed cycle with a
same-environment baseline median, and separately gate maximum cycle
displacement, cycle peak-to-peak variation, and median-frequency pushing.
Exercise low-frequency ripple at multiple phases because a short transient sees
only part of its waveform, and include disturbance near important clock
harmonics or divider rates. Bind the stress result to both the exact parent PEX
and the PVT evidence that supplied its codes. Passing isolated ideal voltage-
source injection is a local sensitivity bound; it does not replace extracted
PDN, package, regulator, substrate-aggressor, or stochastic phase-noise work.

Generate and extract every coarse member as its own complete parent. Deliberate
capacitance changes move contacts, routes, and sometimes the legal placement
window; substituting one leaf model inside a retained parent PEX does not
capture those changes. Require zero DRC, unique LVS, and an exact PEX identity
for all members before launching the aggregate range sweep. Then test every
member/control/environment point without `.ic` or `uic`, using a real supply
ramp and the placed startup assist. A bank interval may be formed only between
adjacent passing controls from the same physical member; overlapping intervals
from different members can then be merged.

Expect the first routed regenerative-loop boundary to move the coarse-band
assignment. In the current VCO work, parent feedback and supply routing moved a
leaf-composed nominal ring far enough that it missed the 2.5 GHz contract even
though DRC and LVS were clean. Do not widen the acceptance band or increase a
control beyond its proven range. Select another already legal coarse geometry,
regenerate its devices and every geometry-dependent strap, update the intended
schematic, and repeat DRC/LVS/PEX. Parent interconnect is part of oscillator
design, not a parasitic correction applied after band selection.

When every legal coarse member shifts in the same direction at the complete
parent boundary, treat that as an architectural placement/routing result rather
than twelve independent sizing misses. Measure where extracted resistance and
capacitance accumulated, and compare the delay of parent-owned feedback and
stage-to-stage routes with the delay of the active tiles. Long detours on a
different upper metal can be worse despite lower sheet resistance because via
stacks, fringe capacitance, and total span also matter. Prefer a compact parent
floorplan that keeps the regenerative path local; choose routing from extracted
delay evidence, not from metal-number intuition.

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

Repeat startup at the first physically routed boundary that contains the whole
regenerative loop. A startup assist proven beside an electrically composed loop
is useful leaf evidence, but parent interconnect, output-buffer loading, power
spines, and selector input loading can change both loop gain and the initial
imbalance. At that boundary, ramp the real supplies without `.ic` or `uic`, test
both kick polarities, verify the assist releases, measure late steady state, and
command shutdown long enough to prove current and output activity decay to the
declared safe state.

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

At a composed analog boundary, gate both the producer output and the consumer's
declared input assumption. Correct final bits do not prove that an intermediate
contract has margin. In the lane work, the raw RX repeatedly drove the sampler
to correct rail-to-rail CMOS results while falling below the sampler's 200 mV
qualified input floor. The right response was a physical data restorer and a
new sampler-phase search, not lowering the floor.

Do not assume a limiter proven on a periodic clock is suitable for arbitrary
data. The extracted 7.5-um-load clock restorer produced large rails but retained
wrong-bit history on PRBS runs. A dedicated shorter-load cell had to be laid
out and extracted. Factor amplitude, polarity, settling, and aperture separately:
first verify port polarity, then sweep physical load, bias, and sampling phase,
and finally rerun the complete downstream chain. The first 3.6-um data restorer
closed the earlier boundary, while the combined slow/hot capture stack selected
a separately versioned 4.2-um physical variant for more restored margin. Preserve
both qualified variants and the failed reuse screens; they distinguish
insufficient gain from data-dependent settling and keep old evidence reproducible.

When process and passive corners push gain and bandwidth in opposite directions,
one global analog code may be the wrong contract. Require a contiguous passing
code window in each representative environment, choose an interior code, and
record the calibration table. This is legitimate programmability only if a
future observable and search algorithm can select the code on silicon; a
per-corner simulator choice alone is not a completed calibration system.

## 9. Render and inspect the real GDS

Generate a full-resolution raster from the emitted GDS and inspect it after
major routing revisions. Annotate topology, dimensions, DRC/LVS state, and PEX
counts, but keep the drawing itself unobscured. Visual review catches long
sensitive nodes, remote tails, sparse contacts, nonlocal loads, and asymmetries
that netlist comparison intentionally ignores.

Render during development as well as at the end. A quick image after placement,
after sensitive-net escape, and after supply routing often exposes unit mistakes,
overlapped hierarchy, excessive route span, or accidental asymmetry before an
expensive extraction. The final committed image must come from the same emitted
layout whose hashes and reports support the evidence.

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
- snapshot or hash the mounted sources before launch and reject the result if
  they change before completion; a read-only container bind does not stop the
  host from changing a script while the shell is still reading it;
- bind summaries to source and result hashes;
- cross-check the physical and simulation records against the same PEX hash;
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
