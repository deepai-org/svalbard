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

The selected source now keeps the fall detector's strong active-low NAND state
and feeds it directly into `SB1`. This removes the detector output inverter,
`SB0`, and the over-delayed extra pair while retaining a static-CMOS state and
the existing SENSE/BOOST consumers. Required PEX probes come from the versioned
contract, so removed topology nodes can no longer create a false incomplete
result.

The complete 40-case schematic campaign in
[`event_capture_schematic_result.json`](event_capture_schematic_result.json)
passes 5/5 environments with 15 valid codes. FF/cold selects
`sense1_interval1_epoch0`; SS/hot has both SENSE-control settings at
`interval0_epoch0`; TT, FF/hot, and SS/cold each have four alternatives. The
exact source is SHA-256 `eae37c75...`.

The generated 192-device, 303.7-um-wide event/bridge macro is zero-DRC,
uniquely LVS-equivalent, and extracts to 4,886 resistors plus 3,577 capacitors.
Its exact identities and public-model boundaries are retained in
[`event_capture_physical_result.json`](event_capture_physical_result.json),
with the review render in [`event_capture_layout.png`](event_capture_layout.png).

This is still not five-corner electrical closure. The targeted eight-case
exact PEX replay in
[`event_capture_pex_result.json`](event_capture_pex_result.json) passes TT with
`sense1_interval0_epoch0` and covers no SS/hot code; capture polarity passes
all eight cases. The failure has moved forward: at SS/hot `HSN` now makes a
0.753--2.945 V active-low transition, but loaded `SB1` peaks at only
1.100--1.195 V and never crosses. That is stronger evidence than the prior
explicit-delay checkpoint, where `HSN` did not switch at all.

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
The active-low state supersedes that explicit-delay checkpoint because it
retains one exact TT pass with 16 fewer devices and advances the SS/hot first
failure. Two bounded followups are also closed. Strengthening `SB1` while
shrinking BOOST increased detector loading, lost TT BOOST rail, and passed 0/8
PEX cases. A separate BOOST predriver then lost SS/hot in the schematic cube
and was rejected before layout. Exact identities and diagnostics are retained
in [`active_low_nand_state_result.json`](active_low_nand_state_result.json).
Another local inverter or taper sweep is not authorized by this evidence.

The next contention-free regenerative experiment is also complete and
rejected. A cross-coupled NAND set/reset state with edge-specific reset and a
bounded SENSE rise assist reaches 12/40 schematic passes with one realizable
code in all five environments. Its 208-device, 303.7-um-wide generated macro
is zero-DRC, unique-LVS, and extracts to 5,610 resistors plus 4,170 capacitors.
Exact PEX nevertheless passes 0/8 targeted TT/SS-hot cases. At TT the latch
restores `SB1` to 2.739--2.785 V, but BOOST peaks at only 2.894--2.918 V. At
SS/hot `HSN` spans 0.681--2.935 V while latch feedback leaves `SB1` below
0.961 V and SENSE never switches. All eight cases still capture the expected
polarity, separating data-path integrity from event-state failure. The exact
schematic campaigns, physical source/PEX/results, and review render are
retained in [`regenerative_state_rejection.json`](regenerative_state_rejection.json)
and [`event_capture_rejected_regenerative`](event_capture_rejected_regenerative).
This closes a local NAND-latch strength/reset/SENSE-edge branch; the next
architecture must merge state into the capture cell or change the event-state
device family rather than tune this latch locally.

The selected active-low source has also been connected directly to the exact
routed regenerative RX/capture parent, removing the earlier 350-fF SENSE and
BOOST proxy loads. At TT the frontend and Q/QB resolve with more than 3.05 V
differential magnitude; the sole rail miss is odd BOOST at 3.03362 V versus a
3.05 V conservative threshold. At SS/hot `SB1` reaches at most 1.17102 V and
SENSE stays between 2.864 and 2.895 V, so the resolved static Q state is not a
capture event. The hash-bound focused checkpoint is
[`event_lane_focused_result.json`](event_lane_focused_result.json). It sharpens
the boundary but does not promote the source.

The bounded device-family change is now also complete and rejected. A
contention-free dynamic state uses one `HSN`-controlled PMOS to set `SB1` and
one `HCLK`-controlled NMOS to reset it, eliminating static contention and
retaining the 192-device footprint. It passes 16/40 schematic cases covering
5/5 environments, and its generated 303.7-um-wide macro is zero-DRC,
unique-LVS, and 4,886R/3,577C extracted. Exact PEX is nevertheless 0/8. At
SS/hot, `HSN` makes a 0.412--2.963 V transition but `SB1` peaks at only
0.665--0.689 V, so neither SENSE nor BOOST switches. At TT `SB1` restores only
to 2.698--2.729 V and the controls miss the retained rail/phase contract.

A stronger two-case composition connects that exact event/bridge PEX directly
to the exact routed regenerative RX/capture parent. The frontend and Q/QB are
resolved in both cases, but neither passes the generated-control rails. The
SS/hot Q state is static initialization—there is no SENSE/BOOST event—so it is
not capture evidence. [`dynamic_state_rejection.json`](dynamic_state_rejection.json)
retains the identities and interpretation. This closes separate-state device
family substitution as well as local inverter/latch tuning. The next circuit
must merge the event state into the capture cell.

The first capture-integrated implementation is now an explicit physical
checkpoint, not a promotion. It replaces loaded `SB1` with a small dynamic
`ESTATE` node and gives SENSE and BOOST independent capture-local tapers. The
exact source hash `8cf5925d80d2016596e121a2ce5f50855b82fc4eaef490e04c4b939e66ee3a47`
passes 17/40 schematic cases with realizable settings in all five declared
environments. Its generated 208-device event/bridge parent is zero-DRC,
unique-LVS, and full-RC extracted. Targeted exact PEX remains 0/4, however.
At TT the state and tapers switch, but SENSE width/rail margins miss the
retained contract. At SS/hot `HSN` switches while `ESTATE` spans only about
0.7--2.4 V; its local tapers consequently lose full CMOS rails. Candidate-
specific extracted probes establish that first failure without pretending the
removed `SB1` node still exists.
The corresponding review render is [available here](../../../../../docs/images/pcie-event-capture-integrated-layout.png).

Two bounded regenerative corrections were rejected before layout because
they passed 0/8 focused schematic cases: a cross-coupled NAND state changed
overlap/release timing, and a weak static keeper delayed the dynamic edge.
Increasing both dynamic event devices retained 5/5 schematic programmability
but made extracted SS/hot contention worse by strengthening reset relative to
set; gating reset until `HSN` release also passed 0/8 schematically. Those
results close blind local latch/ratio/reset sweeps. The next physical iteration
must reduce and explicitly budget the state-to-local-driver route/load or
change the capture-owned event mechanism while preserving the proven event
timing.

A shared-predriver v2 then removes the duplicated first two local stages and
fans out only after a buffered `LSTATE` node. It retains 16/40 schematic
passes covering 5/5 environments and reduces the generated parent from 208 to
200 devices, 5,514 to 5,184 extracted resistors, and 4,114 to 3,855 extracted
capacitors while remaining zero-DRC and unique-LVS. Exact PEX is still 0/4,
but failure movement is measurable: at SS/hot `ESTATE` improves to about
0.37--2.50 V and `LCB` to 0.39--2.93 V before the combined fanout collapses
`LSTATE` high to 1.42--1.57 V. At TT the full chain switches; BOOST high rail
and selected-code timing remain outside the retained contract. Broadly sizing
both shared-driver devices and strengthening only its pull-up each reduced the
focused schematic campaign to 1/8 with no SS/hot code, so those local sizing
branches are rejected before layout. The byte-bound result is
[`capture_integrated_shared_predriver_checkpoint.json`](capture_integrated_shared_predriver_checkpoint.json),
with a [review render](../../../../../docs/images/pcie-event-capture-shared-predriver-layout.png).

The remaining dynamic-CMOS fanout branch is now closed. Split second-stage
restoration preserves 16/40 schematic coverage and is physically legal, but
its doubled first-stage load moves SS/hot failure back to `LCB`. A four-stage
geometric taper restores switching through `LSTATE`, BOOST, and nearly through
SENSE while retaining 16/40 and 5/5 schematic coverage. Localized final
restoration then clears TT BOOST rail—the limiting TT BOOST high is 3.07252 V—
and retains 14/40 schematic passes over 5/5 environments. Its 208-device
parent is zero-DRC, unique-LVS, and 6,198R/4,578C extracted. Nevertheless, an
expanded eight-case exact PEX gate covering all four TT-admitted epoch-1 codes
and the sole SS/hot-admitted code passes 0/8. TT now fails SENSE width/timing;
at SS/hot `LSTATE` high is 2.385--2.537 V and `SDRV` high is only
2.075--2.475 V, leaving final SENSE rail and timing failures. More local taper
or ratio sweeping is not supported by this evidence. The next architecture
must use a different capture-owned event/clock primitive rather than transport
a dynamic CMOS state through a large fanout tree. The terminal byte-bound
record is
[`capture_integrated_final_restore_checkpoint.json`](capture_integrated_final_restore_checkpoint.json),
with a [review render](../../../../../docs/images/pcie-event-capture-final-restore-layout.png).

## Capture-owned state-free START assist

The next architecture removes the dynamic stored state entirely. The existing
restored full-duty `START` state now feeds two capture-local restoration stages
and the programmable SENSE/BOOST outputs; `END` remains independent and owns
only the later capture-clock edge. This makes SENSE invariant to the interval
choice and eliminates the high-fanout `ESTATE/LSTATE/SDRV` transport chain.

Revision v3 passes 18/40 schematic cases with realizable codes in all five
declared environments. Its 152-device, 303.7-um generated parent is zero-DRC,
uniquely LVS-equivalent, and extracts to 4,062 resistors plus 2,943 capacitors.
Targeted exact PEX improves from the dynamic family's 0/8 to 1/10: TT code
`sense1_interval0_epoch0` passes both phases into the exact capture PEX, with
509.73--510.82 ps SENSE width and 0.180--0.204 V SENSE low. All ten cases
still capture the expected polarity.

SS/hot does not close. The same code retains valid capture and timing
(627.86--638.36 ps SENSE width), but SENSE low is 0.965--1.032 V and BOOST
high is 2.723--2.738 V. A fourfold selectable pull-down and slightly stronger
BOOST follow-up repaired that local hot drive but eliminated every FF/hot
schematic code, so it was rejected before layout. Further remote final-ratio
search is not authorized. Direct composition with the actual routed
regenerative-lane consumer, rather than the 350-fF proxy, fails TT and SS/hot.
A bounded schematic consumer-local experiment adds two polarity-preserving
inverter stages at each SENSE/BOOST/CLK/CLKB boundary. It closes TT while
preserving the front end and expected capture polarity in both cases, but is
not yet a physical block.

The slow/hot failure is localized to lane-side SENSE. Its event-side low is
0.244--0.276 V, and the other three buffered interfaces pass, but SENSE at the
extracted consumer only falls to 1.662--1.822 V. The next change is therefore
a consumer-local SENSE driver/assertion-window solution followed by
routed-parent PEX, not another unconstrained remote driver sweep.

The buffer has now been physically lowered. Four bounded physical tapers were
used to distinguish output strength, source loading, and propagation depth.
The retained v4 is a 184-device, 356.0-um, zero-DRC, unique-LVS macro extracting
to 6,252 resistors and 4,521 capacitors. It preserves front-end and capture
polarity in TT and slow/hot but passes neither complete rail screen. TT is
close (SENSE low 0.306/0.332 V and odd high 2.987 V against a 250-mV screen);
slow/hot SENSE source falls to 0.422/0.462 V, its predriver rises only to
1.531/1.469 V, and the consumer falls only to 2.086/2.214 V. A four-stage
logical-effort variant improved source loading but lost the short event before
its final predriver. This closes the sizing experiment as negative evidence:
the next refinement must make assertion duration an explicit composed
contract, not enlarge the same interface again. The proxy
checkpoint is [`capture_state_free_checkpoint.json`](capture_state_free_checkpoint.json),
and the exact-consumer checkpoint is
[`capture_state_free_lane_consumer_checkpoint.json`](capture_state_free_lane_consumer_checkpoint.json),
with [unbuffered](../../../../../docs/images/pcie-event-capture-state-free-layout.png)
and [physical-buffer](../../../../../docs/images/pcie-event-capture-state-free-buffered-layout.png)
review renders.

The first assertion-duration synthesis experiment is also closed negative
evidence. A programmable transmission-gate enables either the direct state or
a full-cycle delayed replica, and a restored static OR/NOR path generates
SENSE. The byte-bound screen hashes each realizable schematic identity into
the exact lane PEX and preserves optional hierarchical node probes. Zero delay
passes TT but slow/hot SENSE high reaches only 1.401--1.406 V; one delay loses
the slow/hot reset interval entirely. The earlier direct stacked-PMOS NOR and
NAND-enable forms were rejected by the same probes before being retained.
[`capture_assertion_duration_screen.json`](capture_assertion_duration_screen.json)
records the surviving zero/one-delay comparison. A full-cycle replica is the
wrong semantic primitive: the next circuit must delay only the release edge
while retaining direct assertion and reset restoration.

That edge-selective experiment is now also closed. The composed contract
measures actual threshold crossings and requires each final 800-ps UI to spend
150--650 ps at both valid SENSE rails. A direct assertion path plus delayed
conditional pull-down preserves rail amplitude, front-end behavior, and
capture polarity in TT and slow/hot. Seven hold widths from 0.5 to 8 um and
both supported replica delays were bounded before layout. Every point passes
TT, but every slow/hot point has too little valid-high reset time. The best
point, delay-16/W0.5, supplies 224.3/225.9 ps valid low and 147.5/146.2 ps
valid high, missing the 150-ps reset contract by 2.5/3.8 ps. Delay 8 regresses
the high interval further. The exact records are
[`capture_edge_hold_best_screen.json`](capture_edge_hold_best_screen.json) and
[`capture_edge_hold_delay8_screen.json`](capture_edge_hold_delay8_screen.json).
No layout was generated for this failing candidate. The next primitive must
regenerate independently controlled set and reset events rather than trade the
two intervals through contention.

The resulting START/END SR primitive is the first version to close the limiting
schematic composition. Non-overlapping active-low SETB and RESETB windows from
the existing full-duty START and programmable END states drive a static NAND
latch; a four-stage taper isolates QB. With the longer-END control
`sense1_interval1_epoch0`, the selected circuit passes TT and slow/hot against
the exact lane PEX. A targeted fourfold SETB pull-down variant also passes the
same schematic gate and is recorded in
[`capture_start_end_sr_set_strength_screen.json`](capture_start_end_sr_set_strength_screen.json).

Physical extraction does not yet preserve that result. The retained v7 layout
puts START inversion beside its restorer, END inversion beside its restorer,
and SETB/RESETB/Q/QB together in the timing lane; only full-duty QB crosses to
the SENSE lane. The retained fourfold-SET experiment is a 232-device,
442.2-um parent, is zero-DRC, uniquely LVS-equivalent, and extracts to 6,948
resistors plus 5,069 capacitors. Exact composition remains 0/2. RESETB is
valid at slow/hot, and stronger SET drive improves SETB from 1.119/1.514 V to
0.342/0.582 V low, but QB reaches only 2.185/1.553 V high and final SENSE stays
low. Added SET capacitance also removes a complete TT valid-low interval.
The [physical record](capture_start_end_sr_physical.json),
[exact composition](capture_start_end_sr_lane_result.json), and
[review render](../../../../../docs/images/pcie-event-capture-start-end-sr-layout.png)
are retained. This closes routed narrow-SET transport as negative evidence.
The next circuit must put START/END-controlled write devices directly inside a
compact static latch so only full-duty states cross into the cell and no narrow
SETB or RESETB net is routed.

That local direct-write experiment is also closed before layout. Full-duty
START/END states and their local complements drive series write devices
directly on cross-coupled Q/QB, so no narrow set/reset net exists. A bounded
ratio progression proves that the state changes, then restores slow/hot QB to
2.983 V after PMOS skew. Threshold-crossing probes reveal the actual blocker:
with the longer END interval, QB is valid high for 210.5 ps at TT but only
79.2 ps at slow/hot. Epoch 1 gives 206.8/78.1 ps and does not change the
conclusion. Two-, three-, and four-stage tapers cannot repair a state interval
that already violates the 150-ps contract. Exact records are
[`capture_direct_write_sr_epoch0_screen.json`](capture_direct_write_sr_epoch0_screen.json)
and [`capture_direct_write_sr_epoch1_screen.json`](capture_direct_write_sr_epoch1_screen.json).

No physical layout is warranted for this family. The accumulated evidence no
longer supports synthesizing another rail-to-rail 3.3-V SENSE pulse. The next
system boundary should remove that event and drive a revised regenerative
sampler directly from the existing full-duty complementary capture clocks,
retaining a separate BOOST only if exact composition proves it necessary.

That direct-clock boundary has now been screened against the exact extracted
event bridge and exact extracted RX/capture parent. The retained experiment
drives only the sampler precharge/base-evaluation gates from the full-duty
clock and leaves BOOST on its independent physical event net. Both TT and
slow/hot resolve the frontend and held outputs by 2.82 V or more of
differential magnitude, but the shared physical clock misses its rail
contract: TT spans only 0.332--3.046 V and slow/hot only 0.509--2.673 V.
This candidate is rejected before parent layout despite functional static-data
capture. The exact record is
[`capture_direct_clock_sampler_screen.json`](capture_direct_clock_sampler_screen.json),
and `--direct-sampler-clock` in
[`run_event_lane_composition.py`](run_event_lane_composition.py) makes the
load experiment repeatable. The next bounded experiment is a local sampler
clock buffer or a lower-clock-capacitance sampler; it must restore consumer
clock rails before any routed-parent claim.

A separated local fanout now passes that schematic insertion gate. Each phase
uses an 8x/16x two-inverter branch for sampler evaluation and independent
4x/8x branches for capture clock and complement; BOOST is an explicit static
high trim rather than a timing event. Inserted between the exact event PEX and
exact routed RX/capture PEX, this architecture passes both TT and slow/hot.
Slow/hot sampler clocks span -43 mV to 3.045 V, capture clocks span -70 mV to
3.055 V, sampler low/high rail-valid intervals are at least 206/327 ps, held
data differential is at least 2.801 V, and average current is 68.224 mA. TT
also passes, at 97.767 mA. The exact record is
[`capture_local_clock_fanout_screen.json`](capture_local_clock_fanout_screen.json).
This is an unrouted composition with schematic fanout devices, not a physical
fanout or routed-parent claim. The next gate is to lower the six local buffer
branches into a matched physical fanout, prove DRC/LVS/PEX, and replay these
same two cases with that extracted fanout before expanding to 5/5 PVT.

The v1 physical fanout is now retained as bounded negative evidence. Its 24
logical MOS instances (192 raw fingers) lower to a 104.6-um-wide generated
cell that is zero-DRC, uniquely LVS-equivalent, and extracts to 1,644
resistors plus 1,121 capacitors. The exact layout used for extraction is
[rendered here](../../../../../docs/images/pcie-local-clock-fanout-layout.png),
and [`local_clock_fanout_physical.json`](local_clock_fanout_physical.json)
binds its schematic, layout source, MAG, GDS, PEX, and image identities.

Replacing all six schematic branches with that exact PEX preserves a complete
TT pass and rail-level slow/hot clocks and data. It does not preserve the
slow/hot sampler interval: extracted fanout RC reduces valid-low time from at
least 206 ps schematically to 64.5/58.3 ps for even/odd, below the 150-ps
contract. Slow/hot still produces 2.904/2.817 V held differential magnitude,
so this is localized clock-edge loss rather than sampler data failure. The
exact composed record is
[`capture_local_clock_fanout_pex_screen.json`](capture_local_clock_fanout_pex_screen.json).
The next physical candidate should strengthen and compact only the 8x/16x
sampler branches; the 4x/8x capture/complement branches already meet rails.

Two negative results matter to the physical compiler workflow.  First, a
compact selector reduced extracted parasitic count but lost SS/hot output-rail
margin.  Second, simply placing `XHSD2` beside its detector improved TT width
but removed route delay and eliminated SS/hot SENSE.  Causal placement is
necessary, but every timing quantity consumed by the circuit must also be an
explicit circuit/physical-intent object rather than an undocumented wire.
[`event_capture_candidate_comparison.json`](event_capture_candidate_comparison.json)
is the hash-bound summary of eleven distinct schematic campaign identities;
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
