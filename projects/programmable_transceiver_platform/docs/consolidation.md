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

## Shared implementations and validation

| Consolidated family | Implementation | Validation and limits |
| --- | --- | --- |
| RF blocker/load/signed quality runners | `verification/fast_rf_quality.py --variant blockers\|load\|signed` | Earlier migration: all eight serialized case records identical; 231 lines replaced by 101 |
| Detector sampling/read helpers | `system_model/connected/detector_readout_settling.py` | Earlier migration: exact recovery records, ODE checks at 5/20/500 ns with max error 4.95e-14; imports reduced from 121 to 92 at that snapshot |
| Host voltage/capture/sized-driver checks | `verification/host_capture_check.py` | Distinct reports and electrical limits retained |
| Bit/event and record controls | `verification/test_bit_event_codec.py`, `record_return_check.py` | Distinct rejection and integration cases retained |
| Three RF tone projections | `analog/rf_measure.py` | Original ASTs identical; nonuniform-sample reference error 2.92e-9; no transistor rerun |
| Five PLL include walkers | `analog/pll/spice_dependencies.py` | Equal nested/cyclic/duplicate include discovery and missing-file rejection against old implementation |
| Two seeded thermal regressions | `verification/thermal_filter_batched_regression.py` | Both 120-case suites pass; rerunning original Git source with current dependencies gives exactly equal numerical reports; older saved reports differ by up to 4e-13 V in error metrics |
| Three thermal clock comparisons | `verification/thermal_filter_clock_comparison.py --variant reference\|local\|long` | Exact state/time/route equality across 12 signed/zero command steps; full acquisition not rerun |
| Mask/rank/prefix/pipe RX testbenches | `verification/block_rx_checks.py` | Original three specialized ASTs match; all four pass 21,219-cycle Icarus simulation and Yosys checks; four mutations rejected per mask/rank/prefix and three for pipe |
| Four block RX vector generators | `verification/block_rx_vectors.py` | Exact equality of all 21,219 rows / 924,971 bytes; variant RTL, mutations and synthesis unchanged |
| Pad carrier/calibration fixtures | `system_model/connected/pad_quality_fixture.py` | Four carrier-class and three calibration-helper ASTs identical; 24 unused copied imports removed; limited-rail failure diagnostics remain separate |
| Unified/guarded pad quality | `system_model/connected/unified_pad_quality.py` | Both variant-specialized function bodies match original ASTs; guarded source/sink limits, chip types, report paths and limitations retained |
| Limited/dense reference calibration | `system_model/connected/managed_limited_calibration_screen.py` | Substituting each chip class and report name reproduces the complete original function-body AST; physical models unchanged |
| Three unified-monitor screens | `system_model/connected/unified_monitor_transport_screen.py` | Controlled-fixture equality of full command/timing traces and serialized reports for transport/ordered/trained variants; real analog runs not repeated |
| Coarse/warm RF quality runners | `system_model/architecture_fast/coarse_quality.py` | Distinct preparation class ASTs unchanged; warm mode/impairment routing verified; full analog quality runs not rerun |
| Narrow/wideband loopback runner | `system_model/architecture_fast/loopback_quality.py` | Controlled-adapter equivalence for both converter modes and impairment choices; full coupled RF quality not rerun |
| Fourteen RTL container launchers | `verification/run_rtl_check.sh` | Byte-identical Docker argument arrays for every wrapper |
| Forty-three analog container launchers | `verification/run_analog_check.sh` | Byte-identical arguments for 30 reusable-directory and 13 fresh-directory variants; mkdir behavior preserved; invalid paths rejected |

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

All 268 recovery records have unique paths and verified Git hashes/sizes. Use a
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

## Current checks and remaining scope

The behavioral regression passed in about 10.7 seconds (60 assumption scenarios,
23 numeric configurations). All seven bounded architecture checks passed:
protocol/signal paths, configuration, records, converter timing, converter
transport, calibration bounds and independent RF reference. These checks do not
qualify separately refactored legacy circuit/RTL experiments.

All fourteen refactored quality/calibration/monitor entry points import with
callable `main`; archive integrity and RF projection checks pass.
All 1,260 Python files parsed at the latest syntax sweep; changed launchers passed
`bash -n` and diff checks. The tracked-source scan found no exact duplicate
top-level Python function/class ASTs of eight or more lines after extraction.
A comment/whitespace-normalized scan found no identical SPICE or RTL sources
in the analog, RTL and simulation directories. This does not establish that
all circuit families are optimally factored. Neither result proves absence of near-duplicates, nested duplication or dynamic
dependency problems. Removed-path references in the repository plan were fixed.

Remaining work: review near-duplicate runners and specialized launchers, review non-identical historical evidence, consolidate overlapping
specialist notes, and audit analog/RTL/model families with representative
behavioral comparisons. Earlier dependency analysis found 179 reachable Python
files including 115 connected-model modules, so an old filename is not evidence
that a model can be removed. Analog circuits and RTL variants may represent
intentional alternatives. Do not collapse different equations, failure controls
or protocol semantics merely to reduce file count.
