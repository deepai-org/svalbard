# Selectable HCLK timing and full-duty event/capture fixture

This is a deliberately narrow schematic prerequisite for the PCIe pulse-path
blocker.  It asks whether a static one-bit control can choose between two
**full-swing**, HCLK-derived end states before narrow-pulse formation, then
drive the existing 650-fF WRITE load through the same five-stage output taper.
The selector is a complementary transmission gate followed by two CMOS
restoring stages.  The code therefore changes a real circuit state, but no
disabled device touches the `WPN` or `WRITE` narrow-event nets.

It is not a full pulse-generator replacement and it does not reuse an ideal
delay source.  In particular it does **not** establish physical geometry,
PEX, the SENSE-to-WRITE timing relationship, the capture-clock bridge, CDR
function, calibration algorithm, or PCIe compliance.

Run the bounded PVT/code screen with:

```sh
./run_hclk_window_probe.sh
```

The screen uses the five declared public-PDK environments (TT, FF/cold,
FF/hot, SS/hot, SS/cold), two static control codes, and four realizable
START-restorer strengths around one selectable-epoch topology. It accepts an environment only when at
least one selected state has a 100--220 ps WRITE pulse, 80--650 ps delay from
the HCLK falling edge, logic rails within 250 mV of their supplies, a valid
`WPN` low, and no more than 75 mA average supply current.

## Retained rejected families

[`hclk_window_baseline_rejection.json`](hclk_window_baseline_rejection.json)
records the 40-case baseline screen.  All candidates restored `WPN` and
WRITE rails at 11.7--19.5 mA, but none covered a PVT environment.  The closest
code (`x4`, `SEL=1`) gave 278.45 ps at TT, 188.49 ps at FF/cold but one UI late,
294.41 ps at FF/hot, 307.87 ps at SS/hot, and 274.47 ps at SS/cold.  Its pulse
is already 265--299 ps at the detector/window boundary, so the excess arises
upstream of the taper.  The next candidate must retard the common START state
or otherwise shorten this **full-swing** timing separation by roughly
45--80 ps while retaining a selected code and all-corner rail recovery.

That is a necessary schematic refinement only.  A candidate that clears it
must still be laid out, DRC/LVS checked, RC extracted, and composed with the
actual capture boundary before it changes PCIe status.

## First contract-driven refinement

The probe now reads [`hclk_window_contract.json`](hclk_window_contract.json)
rather than hard-coding its candidates, environments and thresholds in the
runner.  The same contract binds the semantic instances between HCLK, the
restored `START`, selected `END`, detector `WIN`, and `WPN`.  Its focused unit
test proves that the earlier raw-`S0A` detector bypass and a selector-polarity
swap both fail before SPICE is launched.

Candidate coverage is also fail-closed: a `candidate_id` denotes one circuit
that would be fixed at fabrication, while only its static code may vary after
fabrication.  Results from different transistor choices can no longer be
combined across PVT to manufacture a false calibration pass.

The first four-candidate campaign is retained in
[`restored_start_screen_result.json`](restored_start_screen_result.json).  A
quarter-strength restored START with the x4 selected END covers four of five
environments using its real code.  At FF/cold, both codes have valid
104.19/140.81-ps widths and full rails, but arrive only 21.98/22.21 ps after
the HCLK falling edge versus the declared 80-ps minimum.  This candidate is
therefore rejected before layout.

The fixed common-epoch sweep in
[`common_epoch_delay_rejection.json`](common_epoch_delay_rejection.json) then
proved that one delay strength cannot satisfy both FF/cold's 80-ps minimum and
SS/hot's 650-ps maximum. The first coherent fast/short versus delayed/long
selector in
[`selectable_epoch_initial_result.json`](selectable_epoch_initial_result.json)
covered four environments and missed only SS/hot width by 16.46 ps. These are
falsification records, not candidate passes.

## Current result

[`selectable_epoch_qualified_result.json`](selectable_epoch_qualified_result.json)
records the resulting 40-case bounded screen. One physically fixed candidate,
`epoch_slow_1x_tg_1x_start_0p85x`, covers 5/5 environments using its realized
one-bit code. Selected WRITE widths are 108.05--192.00 ps, selected HCLK-fall
to-WRITE delays are 137.89--647.22 ps, and average currents are 12.77--17.12
mA. FF/cold and FF/hot select the delayed/long state; SS/hot selects the
fast/short state.

This is deliberately only a necessary source-level pass. SS/hot has just
2.78 ps margin to the proxy epoch ceiling, and the probe does not contain the
real SENSE path or extracted consumers. The next gate composes this exact
candidate with SENSE, checks non-overlap and actual SENSE-to-WRITE timing over
5/5 environments, and authorizes layout only if that stronger contract passes.

## Full SENSE/WRITE composition

The same command now also compiles the manifest-selected WRITE circuit with
the authoritative SENSE/BOOST path and its 350-fF/350-fF/650-fF boundaries.
[`sense_write_composition_contract.json`](sense_write_composition_contract.json)
checks SENSE and WRITE widths, SENSE-to-WRITE delay, non-overlap, rails, and
current per physically fixed joint candidate. Its structural test rejects a
bypassed SENSE-tail stage before simulation.

This stronger gate rejects the one-bit architecture before layout. The
baseline, fixed SENSE-tail, selectable SENSE-tail, upstream `SB1` assist, and
joint epoch sweeps are retained as separate falsification records. Final-edge
SENSE control repairs SS/hot and reaches 4/5 environments. A longer WRITE epoch
then repairs FF/cold, but the same setting violates FF/hot delay and dead time.
The exact final result is
[`joint_sense_write_epoch_rejection.json`](joint_sense_write_epoch_rejection.json).

The next circuit needs two orthogonal static controls: interval/edge code 1 for
both FF environments, plus a separate long/short epoch bit that distinguishes
FF/cold from FF/hot. This is a bounded architectural change, not permission for
another unconstrained sizing sweep or physical implementation.

## Two-bit composed qualification

The restored hierarchical selector now implements that separation without a
three-way pass node: `ESEL` chooses short/long full-swing epoch and restores it,
then `SEL` chooses raw SS/hot timing or the restored epoch. Four fixed extra-
delay strengths all pass the 80-case leaf campaign and the 80-case composed
campaign. The selected `extra_2x` candidate is retained in
[`dual_control_composed_qualified_result.json`](dual_control_composed_qualified_result.json).

Its selected SENSE widths are 473.15--595.02 ps, WRITE widths are
127.32--193.28 ps, SENSE-to-WRITE delays are 569.80--646.61 ps, dead times are
52.36--97.64 ps, and current is at most 29.66 mA. This clears the declared
schematic gate and authorizes physical implementation of that exact candidate
only. It is not PEX or capture closure.

## Exact physical implementation and extracted rejection

[`compile_selected_physical_source.py`](compile_selected_physical_source.py)
now resolves the selected manifest identities into one checked-in dual-phase
SPICE source. The conditional 64-um SENSE pull-down is explicitly lowered into
two matched 8-um x 4-finger banks: the GF180 LVS model distinguishes those
banks, so an implicit 8-finger physical fold is not treated as interchangeable
IR. The layout generator also classifies routes from flattened phase ownership,
not instance-name prefixes; this caught and removed a DRC-clean short between
the even and odd internal WPN nets.

`./run_selected_physical.sh` regenerates that exact source and layout, renders
it, and runs native Magic DRC, Netgen LVS, full-RC extraction, then the selected
dual-phase PVT contract. The physical-legality checkpoint in
[`selected_physical_legality_result.json`](selected_physical_legality_result.json)
is zero-DRC, uniquely LVS-equivalent at 224 logical devices, and extracts to
5,780 resistors plus 4,083 capacitors.

That is not timing closure. The same verifier covers 5/5 environments on the
exact generated schematic, as recorded in
[`selected_schematic_replay_result.json`](selected_schematic_replay_result.json),
but 0/5 on full-RC PEX. The retained
[`selected_pex_failure_result.json`](selected_pex_failure_result.json) shows
that WRITE fails its high-rail criterion in all 40 phase/case observations;
SENSE width, dead time, WRITE timing, and slow/hot regeneration also fail. At
SS/hot the loaded WRITE outputs never cross midrail. The next revision is an
RC-localized regenerated layout/circuit change, not a widened contract or a
capture integration attempt.

## Hierarchy-aware lowering and escalation

The first physical lowering treated every nested group below `XWRITE` as the
same functional instance. That silently disabled the established placement
ordering and the final `XWB4` multi-access routing rules. The generator now
carries a wrapper-independent instance path, keeps the complete child in the
WRITE lane, and applies placement/routing rules to the actual child roots. A
regression test binds `XE__XWRITE__XWB4` back to `XWB4`.

The regenerated revision remains zero-DRC and uniquely LVS-equivalent. It
reduces the routing allocation from ten to eight tracks per phase and lowers
the extracted HEMUX, HBASE and WIN capacitances. WRITE amplitude improves
materially, including 3.073 V at the selected TT case and 2.105 V at the
representative SS/hot case. However, the complete PEX gate remains 0/5: WRITE
is now scheduled outside the SENSE-relative window, SENSE remains too narrow
in four environments, and SS/hot BOOST does not regenerate. The exact rejected
checkpoint is
[`hierarchy_lowering_physical_rejection.json`](hierarchy_lowering_physical_rejection.json).

[`localize_selected_pex.py`](localize_selected_pex.py) performs bounded
counterfactuals without changing devices: it can suppress capacitance or
near-zero resistance on named output, SENSE/BOOST, clock/control, and WRITE
state groups, and it repeats the byte-identical baseline as an integrity gate.
The retained repeat has zero numeric delta. Neither idealized WRITE RC nor
idealized SENSE/BOOST RC closes TT plus SS/hot, so further placement-only work
is not authorized. The diagnostic conclusion in
[`selected_pex_localization_result.json`](selected_pex_localization_result.json)
escalates to a circuit revision: separate SENSE edge assist from WRITE
interval/epoch control and derive BOOST from a restored full-width state.

## Three-control recovery and semantic first-failure probe

The recovery source now gives SENSE assist, WRITE interval, and WRITE epoch
three independent static controls. Its manifest also declares causal semantic
paths rather than leaving the runner to infer them from net names. The exact
40-case dual-phase schematic covers 5/5 environments with ten passing cases;
selected SENSE widths are 481.13--627.96 ps, WRITE widths are 127.33--193.28
ps, SENSE-rise-to-WRITE delays are 552.47--638.19 ps, and dead times are
10.23--79.91 ps.

`./run_recovery_physical_probe.sh` regenerates layout, DRC, LVS and PEX, then
measures both rail compliance and midrail transition propagation at the
manifest-declared internal stages. This distinction matters: a stage can
propagate a valid digital event without meeting the stricter external rail
contract. The first extracted recovery topology proved that `SB0` crossed at
SS/hot while its small `RB0` predriver peaked at only 1.46/1.38 V, below the
1.485 V switching level. A balanced predriver repaired that lost transition;
increasing its final pull-down improved BOOST but reloaded the predriver.

The retained topology removes that filter and drives BOOST directly from the
full-width `SB1` state. Its generated 216-device macro is zero-DRC, uniquely
LVS-matched, and the schema-v2 labeled extraction contains 5,900 resistors plus
4,369 capacitors. It remains 0/2 in the targeted TT and SS/hot PEX probe.
BOOST improves materially, but the shared `SB1` load regresses SENSE. The
representative SS/hot selected branch has 0.297/0.549 V SENSE lows and
2.214/1.646 V WRITE highs; its WRITE arrives only 202/367 ps after SENSE
rather than 500--700 ps. TT has no lost WRITE transition, but rail degradation
starts at selected `HBASE` and `START`; its interval-1 WRITE is 256--257 ps
wide and scheduled in the wrong epoch.

The manifest now binds every WRITE semantic stage explicitly, including the
nonuniform `DBG_EW_*`, `DBG_OW_*`, and `DBG_E_WPN` extracted labels. For each
active control path the result records both the first lost midrail transition
and the first strict rail-compliance failure. At SS/hot interval 0, `E0` and
`EMUX` lose rail margin before odd-phase `END` peaks at only 1.137 V and becomes
the first true transition loss. This distinguishes an event-source failure
from a final-load-only failure.

[`localize_recovery_pex.py`](localize_recovery_pex.py) repeats the exact
baseline and applies separate diagnostic-only R/C counterfactuals to declared
epoch, START, END, taper, and combined WRITE paths. The repeat is identical.
Near-zero resistance across the entire WRITE path improves summed WRITE-high
amplitude by 0.586 V but does not restore SS/hot `END`; removing all WRITE
capacitance changes epoch and width non-monotonically and also passes neither
representative case. Modified PEX is never treated as physical evidence.

The exact hashes and representative diagnostics are retained in
[`three_control_recovery_result.json`](three_control_recovery_result.json).
This is useful compiler-loop evidence--manifest elaboration, cheap schematic
promotion, deterministic physical lowering, and semantic failure movement--but
it is still a rejected pulse source.

Two follow-up physical experiments now bound that branch choice. A small
three-stage `SB1` isolation taper retains 5/5 schematic coverage and is
zero-DRC/unique-LVS at 224 devices, but SS/hot `RB0` falls only to 0.61--0.73 V
and `RB1` reaches only 1.50--1.85 V; the taper filters BOOST even though the
selected SENSE branch improves to 450.02 ps and 0.129 V low. A balanced 1.5x
shared-`SB1` driver plus stronger SENSE PMOS also retains 5/5 schematic
coverage and is zero-DRC/unique-LVS, but its extra upstream load reduces
extracted SS/hot `SB1` to 1.56--2.13 V and prevents most SENSE crossings. A 2x
driver had already been rejected schematically at 346--399 ps SENSE width.
Exact hashes are appended to the result JSON. These results close the local
BOOST/SENSE taper sweep.

The independent WRITE diagnostic is now complete as well. Eight bounded
schematic revisions cover matched strong START/END restoration, a four-stage
taper, their combination, identical two-stage detector-input isolation, and
three final-driver strength splits. None covers both TT and SS/hot; the best
retain only TT codes. Local drive was part of the implicit delay budget, so
strengthening it cannot be separated from retiming. This closes local routing,
taper, isolation, and final-driver sweeps. The next candidate must create
explicit full-swing event-delay states and retime them as a unit, then size the
detector and load drivers independently before regenerated DRC/LVS/PEX and
five-environment capture replay.

## Retimed full-swing event source

The next revision implements the authorized architectural change rather than
another local sizing sweep.  Epoch selection occurs only between continuous
full-duty HCLK states.  One restored state then feeds a compact `T0/T1/T2`
tap chain; interval selection chooses a full-swing tap before matched START and
END restorers and the local detector.  A decoded third long-epoch state is a
real circuit path, not an ideal testbench delay.  The independent SENSE,
interval, and epoch controls remain realizable static bits.

`./run_retimed_recovery_schematic.sh` reproduces source hash
`7ec5ca1c...` and covers 5/5 environments with eight passing control cases.
Selected SENSE widths are 481.13--591.34 ps, WRITE widths are
131.40--215.12 ps, SENSE-rise-to-WRITE delays are 595.89--627.90 ps, and dead
times are 4.55--126.62 ps.  This exact schematic, not a nearby sizing point,
earned physical lowering.

`./run_retimed_recovery_physical_probe.sh` generates a 220-device dual-phase
macro.  Native Magic DRC is clean, Netgen finds one LVS-equivalent solution,
and full-RC extraction contains 5,494 resistors and 4,069 capacitors.  The
targeted TT/SS-hot electrical replay remains 0/2.  Unlike the previous
topology, all SS/hot interval-0 event states through `WIN` and `WPN` cross and
reach 2.92--2.96 V and 2.86--2.88 V respectively; the loaded WRITE output then
peaks at only 1.10--1.46 V.  This localizes the new abstraction loss after
full-swing event formation.

The PEX localizer now derives node groups and representative cases from the
active contract instead of hard-coded historical labels.  Its exact baseline
repeat is identical.  Removing taper capacitance adds 6.097 V of summed
WRITE-high recovery across the six representative phase outputs, versus only
0.768 V for near-zero taper resistance, but no counterfactual passes all
required timing and rail predicates.  Modified PEX remains diagnostic only.

Three regenerated schematic branches bound the immediate remedy.  A literal
four-stage taper covers 0/5 and filters short intervals; a monotonic lower-C
six-stage taper reaches 4/5 but loses FF/hot rail; and an over-sized NOR-latch
output covers 0/5 because its both-asserted interval does not provide the
required deterministic reset.  The exact identities and hashes are in
[`retimed_recovery_result.json`](retimed_recovery_result.json).  The next
candidate should transport separate full-duty set/reset events into a
contention-free output state machine, or move that state into the capture
cell.  It should not propagate the final 100--220 ps WRITE pulse through
another large inverter taper.

## Full-duty event/bridge/capture checkpoint

The narrow WRITE transport has now been removed from the immediate capture
boundary.  [`compile_event_capture_source.py`](compile_event_capture_source.py)
exports independent full-duty START and END states, and
[`compile_event_capture_physical_source.py`](compile_event_capture_physical_source.py)
lowers those states together with a direct-END complementary capture-clock
bridge.  The actual byte-bound direct-regenerative capture PEX is the load and
consumer in both schematic and extracted campaigns.

The selected source makes SENSE timing explicit with a local two-inverter
delay pair (`WP=2.1 um`, `WN=1.07 um`, two devices of each polarity per stage).
This replaced an accidental dependency on the placement and route of `XHSD2`.
The complete 40-case schematic campaign in
[`event_capture_schematic_result.json`](event_capture_schematic_result.json)
passes 5/5 environments with ten valid codes.  TT, FF/hot, SS/cold, and SS/hot
share `sense0_interval0_epoch1`; FF/cold has three valid alternatives.  The
source is SHA-256 `ce31c2f1...`.

The generated 208-device, 303.7-um-wide event/bridge macro is zero-DRC,
uniquely LVS-equivalent, and extracts to 4,964 resistors plus 3,713 capacitors.
Its exact identities and public-model boundaries are retained in
[`event_capture_physical_result.json`](event_capture_physical_result.json),
with the review render in [`event_capture_layout.png`](event_capture_layout.png).

This is not yet five-corner electrical closure.  The targeted eight-case exact
PEX replay in [`event_capture_pex_result.json`](event_capture_pex_result.json)
passes TT with `sense0_interval0_epoch1`, the first extracted pass for this
full-duty branch, but covers no SS/hot code.  Capture polarity passes all eight
cases.  At SS/hot, `HSDX` and the explicit `HSDY` state both cross, but their
separation is too large: `HSN` never switches and SENSE remains high.  The
next bounded experiment is an intermediate, strongly restored delay element
between the rejected adjacent/no-delay and full extra-pair implementations.
It is not another bridge enlargement, capture change, or relaxed threshold.

That experiment is now complete and rejected. A single restored inversion
plus a polarity-aware NOR retained 5/5 schematic coverage, and a two-inverter
isolation taper prevented the NOR output from directly driving the existing
SENSE chain. Its 204-device layout is zero-DRC, unique-LVS, and extracts to
5,200 resistors plus 3,863 capacitors. Exact PEX nevertheless passes 0/8
targeted cases. At TT the new stages all switch but their added delay violates
both phase predicates. At SS/hot the NOR output peaks at only 0.983--1.040 V,
the first isolator never recognizes it, and SENSE remains asserted.

A follow-up low-trip isolator was rejected before layout: its complete 40-case
schematic cube covers only FF/cold. The exact identities, physical hashes,
rail observations, and negative conclusion are retained in
[`intermediate_sense_delay_rejection.json`](intermediate_sense_delay_rejection.json).
The prior explicit-delay revision remains the selected reproducible checkpoint
because it retains the only exact-PEX pass. The next circuit experiment must
co-design event detection and restored-state timing; another scalar inverter
strength or trip-point sweep is not authorized by this evidence.

Two negative results matter to the physical compiler workflow.  First, a
compact selector reduced extracted parasitic count but lost SS/hot output-rail
margin.  Second, simply placing `XHSD2` beside its detector improved TT width
but removed route delay and eliminated SS/hot SENSE.  Causal placement is
necessary, but every timing quantity consumed by the circuit must also be an
explicit circuit/physical-intent object rather than an undocumented wire.
[`event_capture_candidate_comparison.json`](event_capture_candidate_comparison.json)
is the hash-bound summary of eight distinct schematic campaign identities;
[`summarize_event_capture_candidates.py`](summarize_event_capture_candidates.py)
regenerates the compact coverage table instead of relying on filenames or log
memory.  Its immutable inputs are retained under
[`event_capture_candidate_results`](event_capture_candidate_results).  Regenerate
it with:

```sh
python3 summarize_event_capture_candidates.py \
  --output event_capture_candidate_comparison.json \
  event_capture_candidate_results/*.json
```

It compares already generated candidates only and makes no optimality or
physical-closure claim.
