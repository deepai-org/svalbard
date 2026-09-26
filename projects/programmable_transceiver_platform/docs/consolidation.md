# Documentation ownership and cleanup rules

Start with the [current status and priorities](../spec/risk-priorities.md).
The mathematical architecture remains incomplete. Passing regressions,
expected rejections and historical demonstrations must not be combined into a
chip-completeness score.

The active status page owns conclusions; the model guide owns execution;
the closure inventory retains exact configurations and scoped results.
Update these owners instead of appending another experiment journal.

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
| `spec/block-diagram.md` | Whole-chip block composition and diagram interpretation |
| `spec/clock-rate-ownership.md` | Clock-domain ownership, sustained-rate mismatch and forwarded-clock services |
| `spec/clock-startup-verification.md` | Transistor bias/reset/acquisition and physical lock-qualification obligations |
| `spec/coarse-retune-contract.md` | Fine-tuning envelope evidence, finite-counter observation and managed coarse retuning |
| `spec/host-activation-candidate.md` | Experimental counted host-activity qualification and promotion gates |
| `spec/host-driver-selection.md` | Host output-driver loading, impedance and shared-return experiments |
| `spec/parallel-datapath-candidate.md` | Wide internal datapath alternatives, block CDC stability and receiving pipelines |
| `spec/streaming-transport-v2.md` | Default protected-header transport, raw-record services and CRC partition rationale |
| `spec/transport-scheduling.md` | Historical v1 CRC/quarantine scheduling comparison; not the current transport contract |
| `spec/receiver-detect-model.md` | Wired impedance observation, detection lifecycle and its scoped model evidence |
| `spec/rf-frequency-coordinates.md` | RF frequency conventions, waveform/channel settings and observation coordinates |
| `spec/rf-quadrature-budget.md` | I/Q gain/phase image sensitivity and passive splitter evidence; not a receiver specification |
| `spec/sampled-loop-model.md` | Two-state sampled phase-detector/PI recurrence and stability checks |
| `spec/three-cap-pll-progress.md` | Historical three-node PLL findings, charge-state invariants and calibration limits |
| `spec/tx-output-isolation.md` | RF output network, retained charge, isolation and loaded-pad observation |
| `spec/tx-output-stage-sensitivity.md` | TX fitting, independent observers, calibration uncertainty and diagnostics |
| `spec/tx-detector-shared-adc-gap.md` | Detector routing, converter ownership, cancellation and shared-ADC integration |
| `spec/unified-analog-state.md` | Coupled driver/reference/network state and finite-current integration candidates |
| `spec/closure-audit-pass876.md` | Historical closure checkpoint with immutable full-journal recovery |
| `spec/open-high-speed-design-survey.md` | External design precedents and their process/performance limitations |
| `spec/feasibility-gates.md` | Physical feasibility criteria, adverse-bound policy and historical stress envelope |
| `spec/contract.json` | Machine-readable interface, limits, generic services and external protocol examples |
| `spec/mathematical-top-profile.json` | Original combined-model stimulus and loading assumptions, read by combined_platform |
| `spec/autonomous-top-profile.json` | Self-contained autonomous-clock combined experiment input |
| `spec/pulse-top-profile.json` | Self-contained pulse-loop combined experiment input |
| `spec/fractional-top-profile.json` | Self-contained fractional-clock/carrier-relative blocker experiment input |
| `spec/phase-loaded-candidate.json` | Descriptive phase-loaded candidate checkpoint and its unverified obligations |
| `spec/experimental-managed-tx-profile.json` | Descriptive managed-TX candidate settings, scoped evidence and outstanding work |
| `docs/diagrams/generate_block_diagram.py` | Editable diagram source |
| `evidence/history-index.json` | Recovery of removed historical files |

## Retention and consolidation

- Keep distinct equations, physical assumptions, failure controls and lifecycle
  semantics. Similar filenames or matching measurements do not prove duplication.
- Share implementation when the state and acceptance contracts agree. Validate
  refactors against the affected behavior, including relevant negative controls.
- Keep historical reports immutable. Source changes make their applicability
  uncertain until verified; a new unit-test pass does not refresh their hashes.
- Preserve entry points and provenance dependencies before removing files.
  Some historical sources are imported or hash-checked by active experiments.
- Keep generated diagrams under one generator. Keep simulator logs, caches and
  temporary sweeps outside maintained source.
- Archive superseded narrative through immutable Git recovery, not another
  maintained copy. Preserve unresolved failures in the current status owner.

## Historical audit and recovery

The [full earlier consolidation audit](https://github.com/deepai-org/svalbard/blob/b7ad8089fc1b6724dfb1ad1948ff0ba0219954fd/projects/programmable_transceiver_platform/docs/consolidation.md)
records implementation extractions, equivalence checks, reviewed exceptions,
file/import counts and historical validation. Those checks apply to their
recorded source versions, not automatically to today's worktree. Its completion
claim described that cleanup pass, not mathematical or physical chip closure.

[The recovery index](../evidence/history-index.json) records immutable commits,
byte sizes and SHA-256 hashes for archived material, including that audit.
Use its record-specific commit when present. Retained implementation families
include distinct FIFO wrappers, RF solvers, clock models and protocol fixtures;
the historical audit explains why they were not collapsed.

The current cleanup shortens the status page, active model guide and this audit.
It preserves source and regression cases. It does not claim that all repository
code has been deduplicated or that historical evidence has been rerun.
