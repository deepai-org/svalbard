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
- `system_model/architecture_fast/acceptance.py`: selected functional baseline.
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
