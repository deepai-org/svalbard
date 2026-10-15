# Documentation ownership and cleanup rules

Start with the [current status and priorities](../spec/risk-priorities.md).
The mathematical architecture remains incomplete. Passing regressions,
expected rejections and historical demonstrations must not be combined into a
chip-completeness score.

The active status page owns conclusions; the model guide owns execution;
the closure inventory retains exact configurations and scoped results.
Update these owners instead of appending another experiment journal.

## One current design

Maintain exactly one normative design, updated in place.
`spec/analog-architecture.json` owns block connectivity, controls and resource
allocations; `spec/contract.json` owns the interface contract. The block diagram
and topic specifications are synchronized views of that same design, not
independent revisions. Resolve any disagreement in these owners together.
Do not retain numbered architecture editions, superseded specifications or
previous-design snapshots in the working tree; recover them from Git history.
Evidence fixtures may retain the assumptions needed to reproduce a result, but
must state their scope and cannot define a competing design. An implementation
that lags the selected design is an open implementation gap, not another baseline.

Simulation consistency is audited by `verification/check_contract.py` under
`simulation_design_audit`; the model guide owns the role/binding table. There is
one planned design. Simplified assumptions and deliberately adverse cases are
valid exceptions; their parameters need not match the nominal chip. Superseded
integrated architectures must be migrated or deleted, rather than retained as
another baseline. Historical measurements may remain when they directly inform
current assumptions, with their original scope and provenance. They cannot be
presented as current-design acceptance. Do not silently change old evidence
hashes or treat a shared constructor as proof of a uniform baseline.

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
| `spec/analog-architecture.json` | Authoritative current block connectivity, controls and resource inventory |
| `spec/block-diagram.md` | Human-readable view of the current inventory and diagram interpretation |
| `spec/clock-rate-ownership.md` | Clock-domain ownership, sustained-rate mismatch and forwarded-clock services |
| `spec/clock-startup-verification.md` | Transistor bias/reset/acquisition and physical lock-qualification obligations |
| `spec/coarse-retune-contract.md` | Fine-tuning envelope evidence, finite-counter observation and managed coarse retuning |
| `spec/host-activation-candidate.md` | Experimental counted host-activity qualification and promotion gates |
| `spec/host-driver-selection.md` | Host output-driver loading, impedance and shared-return experiments |
| `spec/parallel-datapath-candidate.md` | Wide internal datapath alternatives, block CDC stability and receiving pipelines |
| `spec/streaming-transport-v2.md` | Default protected-header transport, raw-record services and CRC partition rationale |
| `spec/receiver-detect-model.md` | Wired impedance observation, detection lifecycle and its scoped model evidence |
| `spec/rf-frequency-coordinates.md` | RF frequency conventions, waveform/channel settings and observation coordinates |
| `spec/rf-quadrature-budget.md` | I/Q gain/phase image sensitivity and passive splitter evidence; not a receiver specification |
| `spec/sampled-loop-model.md` | Two-state sampled phase-detector/PI recurrence and stability checks |
| `spec/three-cap-pll-progress.md` | Historical three-node PLL findings, charge-state invariants and calibration limits |
| `spec/tx-output-isolation.md` | RF output network, retained charge, isolation and loaded-pad observation |
| `spec/tx-output-stage-sensitivity.md` | TX fitting, independent observers, calibration uncertainty and diagnostics |
| `spec/tx-detector-shared-adc-gap.md` | Detector routing, converter ownership, cancellation and shared-ADC integration |
| `spec/unified-analog-state.md` | Coupled driver/reference/network accounting and joined-evidence requirements |
| `spec/open-high-speed-design-survey.md` | External design precedents and their process/performance limitations |
| `spec/feasibility-gates.md` | Physical feasibility criteria, adverse-bound policy and historical stress envelope |
| `spec/contract.json` | Machine-readable interface, limits, generic services and external protocol examples |
| `spec/mathematical-top-profile.json` | Original combined-model stimulus and loading assumptions, read by combined_platform |
| `spec/autonomous-top-profile.json` | Self-contained autonomous-clock combined experiment input |
| `spec/pulse-top-profile.json` | Self-contained pulse-loop combined experiment input |
| `spec/fractional-top-profile.json` | Self-contained fractional-clock/carrier-relative blocker experiment input |
| `spec/phase-loaded-candidate.json` | Descriptive phase-loaded candidate checkpoint and its unverified obligations |
| `spec/experimental-managed-tx-profile.json` | Descriptive managed-TX candidate settings, scoped evidence and outstanding work |
| `docs/diagrams/generate_normative_diagram.py` | Generates the current architecture SVG and connection tables from the inventory |
| `docs/diagrams/generate_block_diagram.py` | Supporting circuit candidate sheets; not an alternate architecture |
| `evidence/history-index.json` | Recovery of removed historical files |

## Retention and consolidation

- Keep distinct equations, physical assumptions, failure controls and lifecycle
  semantics. Similar filenames or matching measurements do not prove duplication.
- Share implementation when the state and acceptance contracts agree. Validate
  refactors against the affected behavior, including relevant negative controls.
- Retain historical work only when it supports a current design assumption,
  unresolved failure, comparison needed for a decision, or active runtime /
  provenance dependency. Otherwise recover it from Git rather than maintain it
  in the working tree.
- Keep retained historical reports immutable. Source changes make their
  applicability uncertain until verified; a new unit-test pass does not refresh
  their hashes.
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

The current pruning removes 110 superseded reports, profiling dumps and narrative
files (3,154,282 bytes). Every removed file has been checked against its immutable
Git recovery record and SHA-256. Current requirements and scoped evidence stay in
the owners above; removed experiment journals are not maintained elsewhere.
Generated console logs belong in temporary directories; extended acceptance
prints its temporary log directory instead of repopulating evidence.

The streaming-v2 specification retains the CRC partition and open qualification
requirements, without obsolete migration instructions or superseded storage and
pin estimates. Legacy codecs remain only as regression comparisons.

Reference review cannot rule out dynamically constructed dependencies. Retain
model families needed by active runners, provenance checks, current assumptions
or unresolved failures; remove further families only after reviewing those
relationships. Historical results do not automatically qualify today's design.
