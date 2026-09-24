# Transceiver consolidation audit

## Findings and changes

The initial import contained 3,132 project files: 1,309 evidence artifacts,
945 verification files, 491 model files, 276 analog files, plus RTL, diagrams
and specifications. Much of this is accumulated research history rather than
necessary top-level entry points.

This consolidation replaces the 1,198,095-byte chronological README with a
short architecture/status/command index. It removes 249 historical evidence
artifacts (4,917,955 bytes) from the active tree and retains their paths, SHA-256
hashes and available outcomes in `evidence/history-index.json`. Every archived
hash was checked against its original Git object in commit `53f84a7`.
No history rewrite, compressed source bundle, or hidden archive is introduced.

Reports were selected only when their filename had no explicit reference in
tracked project text outside the former README; references outside the project
were also checked. Explicitly referenced evidence and recent fast-model reports
remain. This is conservative static analysis, not proof that a dynamically
constructed filename can never be used. Original content remains recoverable;
restore any artifact required by a historical replay from the indexed commit.

## Why source deletion is not yet justified

A conservative local Python import walk starting from all fast-model modules
and `verification/fast_*` entry points finds 179 reachable Python files,
including 115 modules under `system_model/connected`. The scan retains
all same-name matches and is not a complete dynamic dependency resolver.
The apparent old-model directory is therefore not disposable experiment output.
Deleting it would break the current model. Analog and RTL files are likewise
implementation work, not redundant reports.

Remaining structural problems are real: deep inherited experimental model
compositions; copied quality runners with slightly different fixtures; historical
claims embedded in large specification inventories; numerous standalone physical
experiments. These need refactoring around explicit common components and a
parameterized test suite, with behavioral comparisons, before source removal.
This pass does not claim that every retained file is necessary.

## Maintained entry points

- `README.md`: current project entry point, not an append-only experiment journal.
- `spec/exclusive-engine-policy.md`: current user operating decision.
- `system_model/architecture_fast/behavioral.py`: active whole-chip behavioral loop.
- `system_model/architecture_fast/acceptance.py`: supporting bounded numerical suite.
- `verification/fast_exclusive_engine_check.py` and
  `fast_exclusive_management_check.py`: experimental exclusive-mode checks.
- `spec/schematic-implementation.json`: transistor implementation inventory.
- `docs/diagrams/generate_block_diagram.py`: editable diagram source.
- `evidence/history-index.json`: recovery index, not replacement proof of closure.

New progress belongs in focused implementation/specification files and concise
result summaries. Do not add another numbered experiment narrative to README.

## RF quality runner consolidation

The blocker, profile-load and signed-coupling scenarios now share
`verification/fast_rf_quality.py --variant blockers|load|signed`. Their original
231 lines of duplicated fixture/runner code become one 101-line implementation.
The migration compares complete serialized case records, including waveform
quality, transport accounting and signed supply/reference diagnostics. JSON
normalization preserves tuples-as-arrays; it does not round numbers or loosen
quality gates. The original scripts remain in Git history after removal.
The fast-model README is now a focused composition/command/limitations guide
instead of a 608-line chronological journal.

All three consolidated variants passed (8 case rows total), with exact serialized case equality against the originals in Git. Source hashes were verified before removing the three superseded runners.

## Remove incidental model imports

The common chip previously imported a loaded-chip class solely to borrow its
shared-ADC sampling method, and imported a detector class from a module that
also imported an entire historical chip composition. The sampling/read helpers
and buffered detector now live in `connected/detector_readout_settling.py`;
legacy compositions import those same definitions. No circuit model was deleted.

A fresh `import chip` now loads 92 project modules instead of 121. The 29 removed
incidental imports include historical fractional/pulse PLL, coarse acquisition,
loaded-network and host-activation compositions. Explicit loaded-output adapters
still import the finite network they actually use.

Both shared-ADC recovery case records match the pre-refactor records exactly.
Moved helper ASTs are identical apart from function names. Independent detector
readout ODE checks pass at 5 ns, 20 ns and 500 ns settling constants (maximum
error 4.95e-14). The full common aggregate was not rerun for this extraction;
its previous source hashes are historical and must not be presented as fresh
qualification for this source snapshot.

Follow-up requalification after the helper extraction: all 12 common acceptance programs / 38 cases pass; all eight consolidated RF stress case records remain exactly equal. Loaded-loopback numerics and exclusive-engine/serialized-management checks also pass. The selected evidence audit verifies current source and result hashes. This supersedes the earlier note that the common aggregate had not yet been rerun.

## Documentation and diagnostic entry points

The three rail startup/checkpoint/solver notes are consolidated under historical
numerical diagnostics in `spec/power-partition.md`. The model-root README now
routes readers to the selected composition, shared implementation layers and
closure inventory; its original experiment journal remains linked in Git.

Host voltage and forwarded-clock capture checks share
`verification/host_capture_check.py`: default capture, `--voltage-screen`, and
`--sized-driver`. Their separate evidence reports and qualification limits remain.
Raw bit/event queue controls share `verification/test_bit_event_codec.py`;
serialized integration and rejection checks share `verification/record_return_check.py`.
These consolidations preserve distinct failure cases rather than replacing them
with one aggregate success claim. Historical source hashes describe the recorded
snapshot and are not rewritten after a refactor.

## Current documentation ownership

The project README presents capabilities and routes readers to authoritative
requirements. The model-root README is navigation; the fast-model README owns
commands, coverage and limitations. `spec/risk-priorities.md` owns current
priorities, and `spec/mathematical-closure.json` owns completion gates.

The fast-model and risk guides replace accumulated, contradictory progress
narratives with current summaries. Earlier model results remain in evidence
reports and implementation sources; this documentation edit supplies no new
qualification and does not change acceptance thresholds. Historical connected
notes are explicitly labeled. Detailed electrical, timing, pin and transport
requirements remain in their existing specialist specifications.
