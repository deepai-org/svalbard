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
contiguous passing window and select the best code away from both endpoints.
One passing trim code is evidence of a brittle nominal point, not calibration
range. Use finer codes only when the eventual bias or control generator can
actually implement them.

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

Choose device ordering to equalize both electrical function and route span. A
geometrically mirrored picture can still be electrically asymmetric when one
output joins inner devices and the other joins outer devices with unequal wire.

## 5. Generate layout from parameterized devices

Use the PDK's Magic parameterized cells for active devices and resistors, then
flatten only the intended top cell and add deterministic routing. Keep repeated
geometry in small Tcl procedures for rectangles, via stacks, terminal straps,
contacts, and ports. The generated MAG/GDS is disposable output; the Tcl source
is the editable design.

Do not rely on a via-stack helper blindly at route crossings. A stack to M5 also
contains M4, M3, M2, and M1 shapes. Any lower-metal route passing through that
location becomes electrically connected even if the visible top metals differ.

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

Commit and push at meaningful gates: schematic PVT closure, physical DRC/LVS
closure, and extracted/stress closure. Do not present a schematic checkpoint as
a finished macro or a core-only result as a complete PCIe interface.

## Remaining signoff boundary

This workflow produces disciplined public-model pre-silicon evidence. Final
analog-top freeze still requires provider-qualified models and reviews,
post-fill extraction, antenna/density/ERC, EM/IR and reliability analysis,
pad/ESD/package/channel closure, hierarchical and flattened verification,
independent correlation where practical, and measured-silicon correlation.
