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
| `spec/fpga-host-screen.md` | FPGA frequency/bandwidth and native-GPIO electrical evidence; shared host closure work |
| `spec/power-partition.md` | Supply allocation, coupled load budgets and pinned PDNSim load interpretation |
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

The separate signal-path and supply-path notes are merged into host-driver selection
as complete historical experiments, preserving numerical results, archive hashes,
reproduction commands and incomplete-simulation limits. Current power ownership
and priorities remain linked separately.

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

The separate loaded-pad observation note is merged into the RF isolation owner,
retaining its exact frame transform, source/load normalization, state and timestamp
requirements. Navigation now links the owning section; the original is recoverable.

The RF isolation journal now owns continuous-load, carrier-coordinate and pad-observer
contracts in one place, with scoped evidence for each model stage. Superseded next
steps and running-session notices remain only in its immutable historical version.

The clock-ownership note consolidates repeated converter-clock planning and
scheduler updates into one contract and scoped evidence table. Legacy timing,
optional reference-clock integration and the cancelled RF acquisition remain
distinct; common-reference pacing no longer incorrectly says the separate host
service-clock experiment is still absent. Original history is recovery-indexed.

The OpenSERDES and TT07 ADC inspections now live in the open-design survey;
commit-pinned sources and technical caveats are retained, and stale live-experiment
wording points to current priorities. Original review files are recovery-indexed.

Native GPIO Liberty and transistor-transient screens now live in the FPGA host
feasibility guide. Numerical evidence, commands, provenance and limitations are
retained; repeated closure lists become one checklist, and historical one-pair
allocation/drive choices point to their current owners. The pinned PDNSim
restriction now lives with power allocation. All three originals are recoverable
from the history index; the roadmap link points to the merged GPIO section.

The finite-counter observation contract now lives with its coarse-retuning
consumer in `spec/coarse-retune-contract.md`. Counter resolution, latency, wrap
and cancellation bounds remain intact alongside the separate passive-centering
and rollback obligations. Navigation uses one owner; the original counter note
is recovery-indexed.

The uncertainty-envelope policy and full stress table now live in
`spec/feasibility-gates.md`, alongside the evidence categories they constrain.
Both adverse directions, correlated/interior cases, calibration coverage and
unknown-bound rules remain explicit; earlier simulation statuses are labeled
historical. The separate note is recovery-indexed and navigation updated.

## Shared implementations and validation

| Consolidated family | Implementation | Validation and limits |
| --- | --- | --- |
| Shared/rail-budget pad-quality screens | `system_model/connected/shared_pad_quality.py:main` | Twenty controlled mode/variant/scenario comparisons preserve preparation callbacks, traffic options, trace payloads, report fields/paths, time/record alignment and TX/RX failure gates. Distinct chip classes, phase versus rail diagnostics and limitations retained; full traffic not rerun. |
| Five LO chain analysis modes | `analog/quadrature/lo_sine_speed.py:main` | Nine decks and ten success/nonzero-return report/command scenarios match for DC, AC, direct sine, self-biased sine and mixer-loaded sine. Thirty original/refactored checks preserve source-change, missing-include and timeout rejection; cyclic include traversal, AC operating-point hash and wrapper/shared provenance retained. No SPICE rerun. |
| LO self-bias/mixer waveform checkers | `verification/check_lo_selfbias_sine.py:main` | Shared artifact and edge analysis retains different deck-reconstruction assertions and qualification limits; two retained waveform reports, eight incomplete/pending/warning comparisons and 24 original/refactored source/hash/deck/header/finite/time-order rejection checks match. |
| Partial/measured-load reference balance | `verification/analyze_reference_partial_balance.py:main` | Accepted partial-waveform report matches; both analyzers reject the retained loaded waveform because its reproduction gate fails. An isolated loaded-path calculation fixture matches, without changing accepted evidence. Sixteen original/refactored metadata/hash/contract rejection checks and pending-input exit behavior match; loaded report adds shared-source provenance. |
| Baseband bypass/amplitude comparisons | `verification/compare_bb_bypass.py:main` | Shared provenance, fit selection and physical-power/headroom analysis retain distinct reservoir-removal versus amplitude normalization, gain fields and qualification limits. Both retained-waveform reports match; sixteen original/refactored checks reject incomplete fits, incorrect audit hashes, corrupted waveforms and unintended deck changes. |
| Finite/nonbinding rail-budget models | `system_model/connected/managed_rail_budget.py:ManagedRailBudgetChip` | Four actual old/new construction and first-fault-report comparisons match, including explicit current-limit/resistance overrides. Sixteen invalid-resistance checks reject zero, negative, infinite and NaN inputs. The finite-limit subclass retains 150 uA defaults and its own report prefix; no traffic rerun. |
| Feedback/unified-reference calibration screens | `system_model/connected/managed_feedback_calibration_screen.py:main` | Controlled callbacks preserve both complete command/advance/calibration/report sequences; 16 original/refactored negative scenarios preserve acquisition, validity, sample count, charge, detector identity and resource guards. Distinct chip classes and coupling limitations retained; full acquisition/calibration not rerun. |
| ADC reference topology/sizing frame screens | `analog/adc/reference_hybrid_screen.py:main` | Three decks and nine success/timeout/nonzero-exit scenarios preserve manifests, change lists, reports and commands except shared-source provenance. Forty original/refactored checks reject parent/deck/source corruption, wrong include/output anchors and incorrect target-device geometry. Hybrid, doubled-output and long-mirror transformations remain distinct; no SPICE rerun. |
| Four SAR frame/masking modes | `analog/adc/sar8_early_mask_frames_screen.py:main` | Eight decks and four reports/command sequences match original unmasked, track-mask, early-mask and strong-mask runners. Seventy-two original/refactored checks preserve missing-control-source and simulator failure rejection. Pulse timing, source replacement cardinality, masking nodes/cells, artifact hashes and limitations retained; no SPICE rerun. |
| Three VCO charge-injection runners | `analog/pll/vco_charge_kick.py:main` | Eighteen coarse/fine success/timeout/nonzero-exit cases preserve decks, manifests, reports and simulator settings except added shared-source provenance. Fifty-two original/refactored rejection checks preserve parent hash, required nodes/devices, source and deck integrity; output, internal-stage and channel-terminal pulses remain distinct. No SPICE rerun. |
| Output/internal/channel VCO crossing checkers | `verification/check_vco_channel_kick.py:main` | Four retained waveform reports match (coarse/fine output, fine internal and channel); eight warning/pending-record comparisons and 32 original/refactored corrupt hash/node/source/deck rejection checks match. Pulse normalization, ordinal edge matching, time windows and incomplete-run behavior retained. |
| Seeded closed-loop duration/integrator screens | `analog/pll/closed_loop_extended_screen.py:main` | Three generated decks and reports match controlled waveform fixtures, including saved vectors, short/long observation windows, Gear2 options/caveat, simulator arguments and timeouts. Thirty original/refactored checks preserve column/finite/horizon/template/simulator rejection. No SPICE rerun or lock qualification. |
| Clamped and passive-filter PFD/pump screens | `analog/pll/pfd_pump_screen.py:main` | Six generated decks and both controlled waveform reports match, including 7/17-cycle normalization, clamped versus precharged filter nodes and distinct source hashes. Twelve original/refactored checks preserve column/finite/simulator rejection; simulator arguments and timeouts match. No SPICE rerun. |
| Three baseband noise artifact checkers | `verification/check_bb_noise.py:main` | All three retained waveform reports and output paths match; 42 original/refactored rejection checks cover artifact hashes, source changes, case order, simulator status, model excerpts, error logs and unintended deck changes. Common-mode and enlarged-input circuit comparisons remain variant-specific. |
| RF LO, IF-capacitance and prebias comparisons | `verification/analyze_rf_lo_controls.py:main` | All three reports match on retained waveforms; 12 original/refactored checks reject changed waveform hashes and unintended circuit changes. Paired subtraction, continuous/held gains, four-sample windows, variant-only residual metric, normalization rules and qualification limits retained. |
| Three PLL stress/noise quality runners | `verification/stressed_three_cap_quality.py:launch`, shared `StressedClock` | Actual 100 ns chip states match the original for deterministic, resistor-noise and batched-noise variants. All 24 controlled mode/report cases preserve output paths, tags, pass/failure handling and source-change invalidation; wrapper/shared hashes retained. Full traffic not rerun. |
| Four baseband feedback/gain screens | `analog/baseband/feedback_gain_screen.py:main` | Nine generated decks, manifests and reports match with both successful and failing simulator return codes; 24 original/refactored checks reject changed decks, changed sources and missing includes. Programmable selector voltages, feedback-node probes, enlarged input devices, common-mode/feedback sweeps and source provenance retained. No SPICE rerun. |
| Shared/split and ideal/buffered RX screens | `analog/rx_split_screen.py:main` | Eight generated decks and both numerical reports match the original runners using controlled synthetic waveforms; 16 original/refactored checks reject malformed columns, nonfinite samples, truncated horizons and simulator failure. Circuit choices, separate LO current, source hashes and limitations retained; buffered report adds shared-runner provenance. No SPICE rerun. |
| RF blocker/load/signed quality runners | `verification/fast_rf_quality.py --variant blockers\|load\|signed` | Earlier migration: all eight serialized case records identical; 231 lines replaced by 101 |
| Detector sampling/read helpers | `system_model/connected/detector_readout_settling.py` | Earlier migration: exact recovery records, ODE checks at 5/20/500 ns with max error 4.95e-14; imports reduced from 121 to 92 at that snapshot |
| Host voltage/capture/sized-driver checks | `verification/host_capture_check.py` | Distinct reports and electrical limits retained |
| Bit/event and record controls | `verification/test_bit_event_codec.py`, `record_return_check.py` | Distinct rejection and integration cases retained |
| Fast/detailed coarse event advancement | `system_model/connected/coarse_acquisition.py:advance_coarse` | Original event-loop ASTs identical; controlled no-controller/idle/busy cases preserve command/event ordering, target updates, repeated-time calls and invalid-time rejection; parent advancement stays model-specific; detailed TX calibration regression passes with byte-identical prior report; fast coarse startup also passes both modes with identical prior fields except provenance/time |
| Reference impedance/load output-device variants | `analog/reference/pair_impedance_compare.py`, `pair_hybrid_load_probe.py` | Four complete specialized sweep/report ASTs match except added wrapper provenance. Distinct baseline inclusion, doubled high-output-device change/assertion, 120-second timeout, sweep controls, parent/artifact integrity and report fields retained; no SPICE rerun. |
| Half-tail/wide-input reference checks | `verification/check_reference_half_tail.py` | Both complete specialized checker ASTs match; retained waveform reports and output paths are identical. Device-change cardinality/replacement checks and diagnostic limitations remain variant-specific. |
| Two baseband noise runners | `analog/baseband/noise_receiver_cm.py` | Both full experiment ASTs specialize exactly apart from added shared-runner provenance. Resistor calibration, noise-corner/contributor settings and enlarged-input geometry assertions retained; no SPICE rerun. |
| Two CDAC prediction comparisons | `system_model/cdac_prediction_fixture.py` | Exact waveform-loading/comparison AST extracted; two-sign controlled waveform metrics and all four full/coarse response inputs match. Modified waveform hash rejected. Series-RC and modal passive-fit electrical models/independent controls remain separate and unchanged; shared comparison hash added to reports; no electrical simulation rerun. |
| Ideal/autonomous RF sampled-chain sweeps | `analog/rf_autonomous_chain_screen.py:sampled_chain` | Common preparation/sweep/fit AST retained; four controlled decks and all sweep/fit outputs match exactly. Ideal LO loading, CLI controls, report status and limitations stay separate; shared runner hash added to ideal report. No SPICE rerun. |
| Guarded/batched thermal benchmarks | `verification/thermal_filter_guard_benchmark.py` | Original numerical-loop ASTs identical; actual old/new three-step-size runs for both integrators preserve numerical results and route counts. Machine timing and source provenance excluded from comparison; wrapper/shared hashes retained. |
| Fast/detailed sustained traffic | `system_model/connected/sustained_lifecycle.py` | Shared validation, traffic and report ASTs identical; separate original startup ASTs retained via callback. Twelve actual old/new cases preserve complete reports and all advance/feed events across both modes, matched/unmatched rates, nonzero preparation, service-clock offsets, pauses and fractional visibility lag; four run 84 frames. Detailed clock-intervention behavior preserved structurally, not newly exercised. Existing source manifests cover both modules. |
| Seven reference DC experiment fixtures | `analog/reference/pair_dc_fixture.py` | Exact original ASTs for seven bias decks/include scanners, six device-probe lists and five target-sweep loops. Nested/cyclic/duplicate include hashes and missing-file rejection match; four controlled decks/reports match and both deck-mutation controls reject. Distinct circuit modifications and common-mode/target-only sweeps remain explicit; shared helper included in source hashes; no SPICE rerun. |
| Two reference-impedance checkers | `verification/check_reference_pair_impedance.py` | Full specialized experiment/report ASTs identical; both retained four-case waveform sets produce identical complete reports and output paths. Hybrid/long-mirror cases, hash/header checks and limitations remain distinct. |
| Two loaded receiver/ADC replay runners | `analog/integration/rx_adc_event_offsets.py` | Full specialized execution ASTs identical except added in-band wrapper provenance. Distinct prepared waveform paths, fresh output directories, 10,800-second timeout/failure recording, horizon metadata and source/artifact integrity retained; no SPICE run launched. |
| Seven STA report extractors | `verification/timing_log.py` | Shared ordered path records and minimum domain/group slacks; experiment-specific error, completeness, timing, electrical, provenance and equivalence gates stay in callers. Thirteen retained-input report cases match except source provenance; thirteen corrupted-log cases reject; the six RX variants also retain all 30 threshold/error controls. No STA rerun. |
| Six RX mapping launchers | `verification/run_block_rx_mapping.sh` | Baseline/mask/rank/prefix/pipe/commit retain byte-identical mkdir and complete Docker arguments, including the inner synthesis script; invalid variant rejected. Shared launcher included in new report provenance. No mapping rerun. |
| Six RX timing constraint copies | `verification/block_rx_timing_constraints.tcl` | Six nominal and ten corner Tcl command traces identical; physical generator's constraint body byte-identical. All consumers reviewed, including text-transforming corner/physical generators. Nine retained-input reports identical except source hashes; manifests include shared constraints. No physical timing rerun. |
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
| Six RX mapping reports | `verification/block_rx_mapping_report.py` | Baseline/pipe/mask/rank/prefix/commit retained inputs yield identical non-hash report fields; 30 altered-log cases preserve error/electrical/unconstrained rejection and variant thresholds, including baseline <−8 ns and positive prefix/commit setup. Source manifests retain variant files and shared helpers; no physical mapping rerun |
| Mask/rank/prefix/pipe RX testbenches | `verification/block_rx_checks.py` | Original three specialized ASTs match; all four pass 21,219-cycle Icarus simulation and Yosys checks; four mutations rejected per mask/rank/prefix and three for pipe |
| Baseline/pipelined/commit RX stimulus sequence | `verification/block_rx_vectors.py:receiver_stimulus` | Three original loop ASTs identical; byte-identical generated vectors: 21,202 / 1,006,540 bytes baseline, 21,219 / 924,971 bytes pipelined, 21,254 / 925,926 bytes commit. Distinct cycle latency, pending-beat handling, flush and commit-stage negative cases retained; RTL and simulation commands unchanged. |
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
| Nineteen RF/PLL/RX fixed-mount launchers | `verification/run_rf_loop_check.sh` | Ninety-five exact mkdir/Docker argument comparisons cover normal and preflight modes, positional argument forwarding/ignoring, quotes, spaces, shell characters and empty arguments. RX v2 output directories and argument rewriting, fixed pulse/PWL/reference mounts, fresh/reusable directories, image/resources and the internal-kick output exception retained. Shell syntax passes; no containers launched. |
| 224 analog container launchers | `verification/run_analog_check.sh` | All 224 mkdir/Docker argument arrays match after the latest extension. Fresh/reusable directories, mount order/read-only inputs, named containers, CPU/memory limits, prepared replay arguments and image retained. Eight added callers cover damping, autonomous prepared LO with CID files, measured-LO inputs and wired PDK environment/fixtures. Shell syntax passes; no containers launched. |

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

All 288 recovery records have unique paths and verified Git hashes/sizes. Use a
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
| `analog/adc/code_driver*.spice` | Same asymmetric three-inverter topology, but transistor widths differ (4/2 µm vs 1/0.5 µm). Retain these 11-line explicit circuits: `check_cdac_driver.py` asserts their exact sizing-only relation; the bit-6 experiment extracts the small-driver subcircuit by name. Parameterizing would add include/provenance and extraction dependencies for little reduction. Do not equate width changes with multiplicity scaling without PDK-model evidence. |
| `analog/adc/cdac8*.spice` | Fixed switches vs binary-weighted switch multiplicity alter loading and settling; retain those experiment settings. Ideal vs MIM capacitors are distinct physical assumptions. |
| `rtl/pt_block_rx_mask.sv`, `pt_block_rx_rank.sv`, `pt_block_rx_prefix.sv` | Control body now shared in `pt_block_rx_routed.vh`; wrappers select the original routing module. Preprocessed old/new RTL is identical except comments/whitespace. All three pass 21,219-cycle simulation, synthesis checks and four mutation controls. The pipe variant retains separate beat-based routing without captured slot masks. Mapping hash manifests include the shared body; mutations operate on preprocessed input. No new physical timing claim. |

Timing-report family review retains `report_timing.py`'s MET/VIOLATED-specific
slack grammar and register lookup, `report_global_route_timing.py`'s first valid
critical-register capture plus SPEF validation, `report_path_delay.py`'s first-path
selection and cell/net arc sum checks, and `report_block_fifo_mapping.py`'s
multiple-slack-per-path collection and optional asynchronous group. These differ
from the shared minimum-domain and single-slack path extractors. Their surrounding
placement, routing and equivalence checks are separate evidence contracts.

The latest whole-module scan (at least 15 lines, literal values normalized)
found one retained pair: `adc/sar8_reference_compensated_screen.py` and
`adc/sar8_reference_output2_screen.py`. Each is a 22-line circuit-replacement
recipe. They use different parent provenance schemas, replacement circuit sets,
reversible source transformations and change descriptions. A parameterized
recipe would add configuration plumbing at comparable size; retain these
explicit short recipes. This is a reviewed maintenance tradeoff, not an assertion
that their text contains no repetition.

The sampled phase-detector note and three-cap PLL summary retain separate owners.
`sampled-loop-model.md` specifies a held phase measurement and continuous PI state,
including its exact two-state recurrence, local eigenvalue criterion and an
unstable negative case. `three-cap-pll-progress.md` specifies distinct pump/slow/VCO
capacitor states, compliance, charge preservation and coupled thermal/acquisition
limits. Neither contract can substitute for the other; merging their stability
claims would blur the model boundary.

## Current checks and remaining scope

The current full working-tree inventory covers 2,951 maintained project files:
1,104 evidence artifacts; 970 verification files; 502 model files; 278 analog
files; 39 specifications; 30 RTL files; 14 simulation files; eight diagram/docs
files; two integration files; and four root metadata/README files. Ignored
scratch products are excluded. The exact-content scan finds only the five
independent-output groups classified above; all local Markdown links resolve.


After the accumulated source extractions, including the rail-budget hierarchy
and pad-quality runner changes, `make transceiver-math-fast` passed all
seven bounded architecture checks again: protocol/signal paths, generic
configuration, records, converter clock, converter transport, calibration bounds
and independent RF reference. The refreshed iteration/protocol reports retain
their original scope; this does not qualify legacy SPICE or physical timing.
A fresh Git-aware inventory confirms the counts above and the same five retained
equal-content output groups.

The behavioral regression passed in about 10.7 seconds (60 assumption scenarios,
23 numeric configurations). All seven bounded architecture checks passed:
protocol/signal paths, configuration, records, converter timing, converter
transport, calibration bounds and independent RF reference. These checks do not
qualify separately refactored legacy circuit/RTL experiments.

A project-wide static named-import audit of the 47 currently changed Python
providers checks 52 imported names. Every name remains declared, and provider
resolution has no ambiguous cases in this set. A follow-up module-alias scan finds
no attribute-access consumers of these changed providers. The identified dynamic
forms are reviewed separately: 12 `runpy.run_path` calls resolve to maintained
files and their 22 literal namespace-key uses remain declared; none targets a
currently changed provider. All nine configured receiver-detection module names
resolve with a declared `main`. The two AST-extraction checks actually pass:
LO crossing/weighted-mean controls and RF projection (relative error 2.92e-9).
These checks do not execute the retained `runpy` experiments or prove arbitrary
generated-code/container dependencies. Those loader targets remain necessary even
when conventional import searches find no consumers.

All fourteen refactored quality/calibration/monitor entry points import with
callable `main`; archive integrity and RF projection checks pass.
All 1,267 Python files parsed at the latest syntax sweep; changed launchers passed
`bash -n` and diff checks. The latest complete working-tree scan found no exact duplicate Python function
or method ASTs of nine or more physical lines after extraction.
A comment/whitespace-normalized scan found no identical SPICE or RTL sources
in the analog, RTL and simulation directories. This does not establish that
all circuit families are optimally factored. Neither result proves absence of near-duplicates, nested duplication or dynamic
dependency problems. Removed-path references in the repository plan were fixed. The latest project-wide
Markdown link scan found no missing local targets.

The nested-statement scan initially found eleven repeated groups of at least
thirteen lines. After consolidation, the latest full scan finds no exact repeated
statement ASTs at that threshold. Smaller blocks and near-duplicates are not ruled
out; distinct circuit variants and experiments still require their own contracts.

A broader token-shingle screen found 36 candidate Python pairs at Jaccard similarity
≥0.8 (seven-token shingles, literals normalized, modules of at least 30 lines).
These are review candidates, not proof of interchangeable behavior. Reviewed
consolidations and validation scopes appear in the table above. The pad-quality
pair is now consolidated. The fresh scan finds only the one reviewed oracle
pair below; all initial candidates have a consolidation or retention disposition.

Retain `verification/lo_modulated_truncation.py` and `lo_multipole_truncation.py`
as explicit scalar-pole and fifth-order modal-sum oracles. Their filter cutoffs,
real versus complex-pole arithmetic, period coverage and approximation acceptance
checks differ: the first-order screen reports its approximation budget result,
while the fifth-order screen requires it to pass. Both already share the LO
fixture/sideband primitives. Factoring the remaining short setup/reporting around
one generalized solver would obscure the two reference equations and their
acceptance contracts. This is a reviewed maintenance choice, not a claim that
these files contain no repeated text. Broader family and dependency review
remains necessary beyond this similarity threshold.

The specialized launcher pass consolidates the remaining four repeated analog
mount patterns and the RX preflight pair. A fresh project-wide shell-body scan
(normalizing experiment directories, Python runner paths and whitespace;
excluding wrappers shorter than eight lines) finds no repeated bodies. This
checks those patterns only; it does not prove arbitrary shell equivalence. All
262 sibling shell-entrypoint references resolve.

The whole-module constant-normalized scan is complete with the explicit short-recipe
exception above. Remaining work: broader near-duplicate and dependency review,
specialized launchers, non-identical historical evidence, overlapping
specialist notes, and audit analog/RTL/model families with representative
behavioral comparisons. Earlier dependency analysis found 179 reachable Python
files including 115 connected-model modules, so an old filename is not evidence
that a model can be removed. Analog circuits and RTL variants may represent
intentional alternatives. Do not collapse different equations, failure controls
or protocol semantics merely to reduce file count.

The shorter-script review shares elastic/staged block FIFO scoreboard generation.
Original and refactored runners both pass Icarus simulation and reject their
respective corruption/overwrite mutations. Generated testbenches and mutated RTL
are byte-identical; simulator output agrees after normalizing temporary paths.
The expanded near-duplicate scan includes scripts of at least 20 lines; its
remaining candidates still require review.
