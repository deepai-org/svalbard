# Transceiver consolidation audit

Project-wide consolidation is **in progress**. The current pass began with 2,969
tracked project files; ignored simulator logs/caches are not maintained source.
Source, distinct failure cases, implementation requirements and immutable
historical provenance must survive consolidation. Passing a refactor check does
not establish chip feasibility.

## Documentation ownership

| Owner | Content |
| --- | --- |
| Project README | Intended capabilities, scope and navigation |
| `system_model/architecture_fast/README.md` | Active commands, coverage and limitations |
| `spec/risk-priorities.md` | Current work priorities |
| `spec/mathematical-closure.json` | Mathematical completion gates |
| `spec/schematic-implementation.json` | Transistor implementation inventory |
| `spec/analog-design-workflow.md` | Behavioral → schematic → extraction workflow and reusable lessons |
| `spec/exclusive-engine-policy.md` | Generic configuration, sharing and RF/wired exclusivity |
| `docs/diagrams/generate_block_diagram.py` | Editable diagram source |
| `evidence/history-index.json` | Recovery of removed historical files |

The 608-line three-cap PLL journal is summarized around model invariants,
failures, conditional results and calibration uncertainty, with its full original
linked in Git.
The 2,672-line pass876 journal is replaced by a historical requirement/evidence
summary linking to its complete immutable Git version; stale live-run notices
are removed, and trigger/lossless-stop contract gaps remain explicit.
The fast-feasibility and executable-schematic notes are merged into the analog
workflow. Three rail startup/checkpoint/solver notes are merged into
`spec/power-partition.md`; their numerical history is a compact results table
with reproduction commands, analyzer failure rules and a complete Git record. Model guides and priorities no longer duplicate
chronological experiment logs. Specialist timing, RF, electrical and transport
requirements retain their owners. The v1 transport note remains explicitly
historical because CRC/quarantine behavior differs from streaming v2.

The Artix load baseline and weak-drive note are merged into
`spec/host-driver-selection.md`, retaining reports, reproduction commands,
threshold conventions, current tables and waveform archive hashes. Stale
concurrent-payload wording is aligned with exclusive RF/wired operation.

The connected architecture journal is replaced with model-layer navigation,
current specification owners and supporting-regression semantics. Its complete
pass-by-pass history is recovery-indexed and linked immutably; stale running-job
claims no longer appear as current guidance. Distinct fixed-laboratory and
carrier-relative blocker results remain explicitly distinguished.

The analog workflow handoff/performance narrative now keeps reusable solver,
video-reuse and stage-boundary rules, links the active command guide, and archives
historical run status/measurements. The six-family primitive plan and complete
schematic-before-layout gate remain intact.

The connected directory README now links the active guide and architecture map
instead of duplicating its pass-674–687 journal. The full journal is recovery-indexed;
old session notices in reference/ADC notes are explicitly historical.

The TX sensitivity/calibration journal is organized by lifecycle contracts,
observer limitations, analytic error bounds and scoped numerical evidence.
Superseded next-step lists move to immutable history; negative results and
independent-observation requirements remain explicit.

## Shared implementations and validation

| Consolidated family | Implementation | Validation and limits |
| --- | --- | --- |
| RF blocker/load/signed quality runners | `verification/fast_rf_quality.py --variant blockers\|load\|signed` | Earlier migration: all eight serialized case records identical; 231 lines replaced by 101 |
| Detector sampling/read helpers | `system_model/connected/detector_readout_settling.py` | Earlier migration: exact recovery records, ODE checks at 5/20/500 ns with max error 4.95e-14; imports reduced from 121 to 92 at that snapshot |
| Host voltage/capture/sized-driver checks | `verification/host_capture_check.py` | Distinct reports and electrical limits retained |
| Bit/event and record controls | `verification/test_bit_event_codec.py`, `record_return_check.py` | Distinct rejection and integration cases retained |
| Fast/detailed coarse event advancement | `system_model/connected/coarse_acquisition.py:advance_coarse` | Original event-loop ASTs identical; controlled no-controller/idle/busy cases preserve command/event ordering, target updates, repeated-time calls and invalid-time rejection; parent advancement stays model-specific; detailed TX calibration regression passes with byte-identical prior report; fast coarse startup also passes both modes with identical prior fields except provenance/time |
| Commit/prefix RX corner reports | `verification/report_block_rx_commit_corners.py` | All ten retained corner results and report paths identical except source hashes; mapped-netlist hash, nominal consistency and slow-corner rejection checks preserved; no timing rerun |
| Direct/self-biased LO sine runners | `analog/quadrature/lo_sine_speed.py` | All four decks and non-provenance fixture reports identical; include-scanner AST unchanged (scanner bypassed only in the fixture); explicit bias and coupling-network options; no SPICE rerun |
| Loaded-receiver/interstage LO replays | `analog/quadrature/lo_receiver_replay.py` | Both full specialized execution ASTs identical except added wrapper provenance; distinct stems, 7,200/14,400-second timeout contracts and failure artifacts retained; no long SPICE run launched |
| Sampling-driver operating-point pair | `analog/adc/sample_driver_op.py` | Both full specialized execution ASTs identical, including probe list, measured-vector validation and circuit hashes; original/headroom device alternatives retained |
| Fixed/scaled CDAC step pair | `analog/adc/cdac_step_screen.py` | Both full specialized execution ASTs identical, including generated decks, waveform shape checks, statuses and limitations; distinct switch sizing retained; no SPICE rerun |
| Early/strong SAR mask-frame runners | `analog/adc/sar8_early_mask_frames_screen.py` | Both full specialized experiment/report ASTs identical; distinct mask circuits and status labels retained, shared pulse helpers unchanged; no SPICE rerun |
| Reference impedance and pulse replay pairs | `analog/reference/pair_impedance_compare.py`, `pair_step_screen.py` | All four specialized execution ASTs identical except added pulse-wrapper provenance; long-mirror/hybrid labels and baseline/hybrid parent selection retained; no SPICE rerun |
| Two reference-buffer DC sweeps | `analog/reference/buffer_dc_screen.py` | Both specialized runner ASTs identical, including all signed load/scale/target sweeps and report construction; circuit variants unchanged |
| Two reference load-range replays | `analog/reference/pair_hybrid_load_dc.py` | Full execution ASTs identical after substituting original solver-control strings, except added wrapper provenance; source before/after checks retained; no SPICE rerun |
| Channel/internal VCO pulse checkers | `verification/check_vco_channel_kick.py` | Both retained fine-step three-case sets yield identical complete reports and paths; injection-node validation, source/artifact checks and ordinal-edge comparison retained; no SPICE rerun |
| Two reference-step checkers | `verification/check_reference_hybrid_step.py` | Reprocessing both retained four-case waveform sets produces identical complete reports and output paths; parent-deck, source/artifact integrity and completion/recovery checks retained |
| NMOS/PMOS baseband swing runners | `analog/bb_swing_screen.py` | All 24 decks and non-provenance report fields identical with controlled waveform data, including harmonic/window and gain-compression measurements; circuit choices preserved; no SPICE rerun |
| NMOS/PMOS baseband gain runners | `analog/bb_gain_screen.py` | All 18 decks and non-provenance report fields identical under controlled simulator fixture; PMOS bias, ground-referenced loads and circuit selection explicit; shared/entry-point hashes retained; no SPICE rerun |
| Two CDAC driver runners | `analog/adc/cdac_driver_screen.py` | Specialized execution ASTs identical for normal/small driver, including deck generation, status and report fields; actual circuit variants retained |
| Two CDAC convergence runners | `analog/adc/cdac_probe_convergence.py` | Execution ASTs identical apart from added wrapper source hash; distinct reltol-only/full tolerances, fresh directories, replay assertions and timeout handling retained; no SPICE rerun |
| Three SAR decision-loop runners | `analog/adc/sar8_closed_screen.py` | Closed/buffered/fast controlled old/new execution gives byte-identical decks and reports for all 12 cases; simulator invocation contract, timing windows and limitations preserved; no SPICE rerun |
| Three ADC sampling-driver runners | `analog/adc/sample_driver_screen.py` | Nominal/headroom/long-mirror specialized runner ASTs match originals, including deck literals, simulator arguments, status and report construction; circuit files unchanged; no SPICE rerun |
| Three RF tone projections | `analog/rf_measure.py` | Original ASTs identical; nonuniform-sample reference error 2.92e-9; no transistor rerun |
| Five PLL include walkers | `analog/pll/spice_dependencies.py` | Equal nested/cyclic/duplicate include discovery and missing-file rejection against old implementation |
| Two seeded thermal regressions | `verification/thermal_filter_batched_regression.py` | Both 120-case suites pass; rerunning original Git source with current dependencies gives exactly equal numerical reports; older saved reports differ by up to 4e-13 V in error metrics |
| Three thermal clock comparisons | `verification/thermal_filter_clock_comparison.py --variant reference\|local\|long` | Exact state/time/route equality across 12 signed/zero command steps; full acquisition not rerun |
| Three RX mapping reports | `verification/block_rx_mapping_report.py` | Retained mapping inputs yield identical non-hash report fields for mask/rank/prefix; nine corrupted-log cases rejected; distinct setup-sign expectations and source manifests retained; no physical mapping rerun |
| Mask/rank/prefix/pipe RX testbenches | `verification/block_rx_checks.py` | Original three specialized ASTs match; all four pass 21,219-cycle Icarus simulation and Yosys checks; four mutations rejected per mask/rank/prefix and three for pipe |
| Four block RX vector generators | `verification/block_rx_vectors.py` | Exact equality of all 21,219 rows / 924,971 bytes; variant RTL, mutations and synthesis unchanged |
| Pad carrier/calibration fixtures | `system_model/connected/pad_quality_fixture.py` | Four carrier-class and three calibration-helper ASTs identical; 24 unused copied imports removed; limited-rail failure diagnostics remain separate |
| Unified/guarded pad quality | `system_model/connected/unified_pad_quality.py` | Both variant-specialized function bodies match original ASTs; guarded source/sink limits, chip types, report paths and limitations retained |
| Limited/dense reference calibration | `system_model/connected/managed_limited_calibration_screen.py` | Substituting each chip class and report name reproduces the complete original function-body AST; physical models unchanged |
| Fast/detailed TX calibration lifecycle | `system_model/connected/tx_calibration_services.py` | Fifteen shared methods; every original method AST preserved, including distinct clock-readiness and monitor overrides; both compositions construct, report resources and reject unqualified calibration starts; fast dynamic lifecycle passes both widths, ownership/commit and in-flight cancellation in 8.7 s, with identical prior report fields except hashes/time; detailed coarse-loop lifecycle also passes with byte-identical prior evidence |
| Scalar/vector phase calibration | `system_model/connected/phase_loaded_calibration_screen.py` | Complete experiment and report-construction ASTs identical after model substitution; vector screen retains saved scalar comparison and 1e-12 endpoint tolerance; no analog rerun |
| Pulse/autonomous combined RF quality | `system_model/connected/combined_detector_quality.py` | Both complete specialized runner ASTs and preparation classes match originals; pulse-only source-duration assertion, profile hashes, report paths and limitations retained; no analog rerun |
| Three unified-monitor screens | `system_model/connected/unified_monitor_transport_screen.py` | Controlled-fixture equality of full command/timing traces and serialized reports for transport/ordered/trained variants; real analog runs not repeated |
| Coarse/warm RF quality runners | `system_model/architecture_fast/coarse_quality.py` | Distinct preparation class ASTs unchanged; warm mode/impairment routing verified; full analog quality runs not rerun |
| Narrow/wideband loopback runner | `system_model/architecture_fast/loopback_quality.py` | Controlled-adapter equivalence for both converter modes and impairment choices; full coupled RF quality not rerun |
| Focused RF/video SVGs | `docs/diagrams/generate_block_diagram.py` | Removed invisible copies of other sheets: 585,684 → 23,997 bytes combined; both native-resolution renders pixel-identical, full-chip SVG byte-identical |
| Fourteen RTL container launchers | `verification/run_rtl_check.sh` | Byte-identical Docker argument arrays for every wrapper |
| 182 analog container launchers | `verification/run_analog_check.sh` | Byte-identical arguments for 30 reusable-directory, 13 fresh-directory and 85 baseline-mounted variants (40 RF-reference, 26 basic, 19 Wi-Fi-mounted); mkdir behavior, baseline paths and mount order preserved; 29 named single-CPU prepared replays also preserve fresh directories and baseline argument. Added eight divider-chain, seven paired-input and ten Wi-Fi-source callers; all 182 caller command arrays rechecked after the extension; invalid paths rejected |

Compatibility entry points preserve existing commands where needed. Thermal
variants retain their guard choice, 100/2,400-step horizons, separate reports and
800-sample long-run lock-tail check; the stressed runner's local-guard import
behavior remains compatible. Loopback variants retain seeded stimuli, impairment
parameters, acceptance assertions and separate report paths. Coarse/warm quality
checks share simulation/report plumbing while retaining their different clock
preparation, calibration histories, limitations and report names. Unified-monitor
variants retain their different selection order and optional host conditioning.
Their historical shared output filename is preserved; run them separately when
comparing results to avoid overwriting that report.

The thermal comparison excludes only source hashes when comparing reports;
case fields, routes, error metrics, limitations and status all match the freshly
executed original. Thus the observed difference from old saved reports is not
introduced by this refactor under the tested environment.

Receiver RTL execution used installed Icarus/Yosys with only container absolute
paths remapped to temporary local directories. It validates the shared checker
and current RTL, not equivalence of local tool versions to the pinned container
or physical timing. Temporary products were removed after each check.

New provenance manifests include shared helpers; original evidence hashes are
never rewritten to qualify refactored source. Container image digests, resource
limits, mount order/permissions and output locations are preserved. Launchers
with different preparation or mounts remain separate until individually reviewed.

## Historical recovery

The initial cleanup removed 249 historical reports (4,917,955 bytes), verified
against commit `53f84a7`, and replaced a 1,198,095-byte README experiment journal.
The present pass additionally removed:

- Twelve before-migration snapshots: six copied runners and six reports,
  343,446 bytes; the migration comparison reports remain.
- Five exact duplicate calibration/aggregate snapshots, 169,800 bytes; historical
  audit links point to immutable Git versions, not mutable current reports.
- Two superseded workflow documents after merging their unique requirements.
- Two superseded host load/driver notes merged into driver selection.
- Two unreferenced TX before-fix snapshots: invisible DAC/monitor ownership and
  calibration surviving direct retarget. The index preserves these historical
  bugs explicitly; their current audit outputs are separate, non-equivalent results.

All 276 recovery records have unique paths and verified Git hashes/sizes. Use a
record's `recovery_commit` when present, otherwise the index-level default:

```sh
git show <commit>:projects/programmable_transceiver_platform/<indexed-path>
python3 projects/programmable_transceiver_platform/verification/check_history_index.py
```

`identical_at_removal_to` records equality at removal, not future equivalence.
Removal never changes a failed result to a pass. Static reference review cannot
rule out all dynamically constructed paths; restore the indexed artifact when
replaying a historical workflow that requires it.

## Retained equal-content experiment outputs

The remaining five exact-content groups are intentionally retained as independent
outputs, not silently aliased. They may diverge when their respective experiments
are rerun:

| Artifact group | Producer and reason to retain |
| --- | --- |
| `connected-limited-rail20-pad-quality-mode1[-phase-diagnostic].json` | `connected/limited_rail_budget_pad_quality.py` selects separate report names with `phase_diagnostics`; both recorded failures remain visible |
| Corresponding two `-traces.npz` files | Same runner selects separate waveform paths for diagnostic and baseline runs |
| Mode-0 managed-host / TX-managed-host / TX-warm trace files | `connected/tx_wideband_screen.py` derives trace names from each experiment's output name; report cases reference those paths |
| Mode-1 managed-host / TX-host-switching / TX-managed-host traces | Same parameterized runner, distinct host-conditioning experiments and report references |
| `lo-gap-state[-contiguous].json` | `verification/analyze_lo_gap_state.py --contiguous` compares storage-layout implementations; `compare_lo_gap_variants.py` consumes the contiguous result |

Use a separately designed content-addressed report store if future space savings
justify changing these producers and consumers together. Symlinking writable
outputs could overwrite evidence from another experiment. Current equality is
not proof that their experiment configurations or future results are equivalent.

## Circuit-family review

| Family | Evidence and disposition |
| --- | --- |
| `analog/rx_iq_core.spice`, `rx_iq_split_core.spice`, `rx_iq_buffered_core.spice` | Shared-LNA vs two separate drain/source branches vs four physical LO buffers. Different input/LO loading is the experiment; retain distinct compositions. Buffered composition already includes the split core and LO-buffer subcircuits. |
| `analog/adc/code_driver*.spice` | Same asymmetric three-inverter topology, but transistor widths differ (4/2 µm vs 1/0.5 µm). Do not equate width changes with multiplicity scaling without PDK-model evidence. Possible parameterized-source consolidation remains to be assessed. |
| `analog/adc/cdac8*.spice` | Fixed switches vs binary-weighted switch multiplicity alter loading and settling; retain those experiment settings. Ideal vs MIM capacitors are distinct physical assumptions. |
| `rtl/pt_block_rx_mask.sv`, `pt_block_rx_rank.sv`, `pt_block_rx_prefix.sv` | Control body now shared in `pt_block_rx_routed.vh`; wrappers select the original routing module. Preprocessed old/new RTL is identical except comments/whitespace. All three pass 21,219-cycle simulation, synthesis checks and four mutation controls. The pipe variant retains separate beat-based routing without captured slot masks. Mapping hash manifests include the shared body; mutations operate on preprocessed input. No new physical timing claim. |

The final whole-module scan (at least 20 lines, literal values normalized)
found one retained pair: `adc/sar8_reference_compensated_screen.py` and
`adc/sar8_reference_output2_screen.py`. Each is a 22-line circuit-replacement
recipe. They use different parent provenance schemas, replacement circuit sets,
reversible source transformations and change descriptions. A parameterized
recipe would add configuration plumbing at comparable size; retain these
explicit short recipes. This is a reviewed maintenance tradeoff, not an assertion
that their text contains no repetition.

## Current checks and remaining scope

The current full working-tree inventory covers 2,956 maintained project files:
1,104 evidence artifacts; 967 verification files; 501 model files; 277 analog
files; 49 specifications; 30 RTL files; 14 simulation files; eight diagram/docs
files; two integration files; and four root metadata/README files. Ignored
scratch products are excluded. The exact-content scan finds only the five
independent-output groups classified above; all local Markdown links resolve.


The behavioral regression passed in about 10.7 seconds (60 assumption scenarios,
23 numeric configurations). All seven bounded architecture checks passed:
protocol/signal paths, configuration, records, converter timing, converter
transport, calibration bounds and independent RF reference. These checks do not
qualify separately refactored legacy circuit/RTL experiments.

All fourteen refactored quality/calibration/monitor entry points import with
callable `main`; archive integrity and RF projection checks pass.
All 1,264 Python files parsed at the latest syntax sweep; changed launchers passed
`bash -n` and diff checks. The latest complete working-tree scan found no exact duplicate Python function
or method ASTs of nine or more physical lines after extraction.
A comment/whitespace-normalized scan found no identical SPICE or RTL sources
in the analog, RTL and simulation directories. This does not establish that
all circuit families are optimally factored. Neither result proves absence of near-duplicates, nested duplication or dynamic
dependency problems. Removed-path references in the repository plan were fixed. The latest project-wide
Markdown link scan found no missing local targets.

The whole-module constant-normalized scan is complete with the explicit short-recipe
exception above. Remaining work: broader near-duplicate and dependency review,
specialized launchers, non-identical historical evidence, overlapping
specialist notes, and audit analog/RTL/model families with representative
behavioral comparisons. Earlier dependency analysis found 179 reachable Python
files including 115 connected-model modules, so an old filename is not evidence
that a model can be removed. Analog circuits and RTL variants may represent
intentional alternatives. Do not collapse different equations, failure controls
or protocol semantics merely to reduce file count.
