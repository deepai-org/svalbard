# Design and documentation ownership

Maintain one normative design, updated in place. Requirements, model behavior,
implementation and diagrams must agree; missing implementations are explicit
open gates. Configuration binding does not prove physical feasibility.

| Owner | Content |
| --- | --- |
| `spec/analog-architecture.json` | Blocks, connections, generic controls and allocations |
| `spec/contract.json` | External interfaces and application requirements |
| `spec/block-diagram.md` and `docs/diagrams/` | Human-readable architecture and generated diagrams |
| `spec/risk-priorities.md` | Current decisions, unresolved risks and external reuse candidates |
| `spec/mathematical-closure.json` | Mathematical completion criteria and scoped evidence |
| `spec/schematic-implementation.json` and `analog/pads/README.md` | Circuit implementation coverage and physical gaps |
| `system_model/architecture_fast/README.md` | Active commands and model boundaries |
| Topic specifications | Timing, transport, power, analog workflow and electrical requirements |

Update the existing owner instead of adding experiment journals. Keep evidence
needed to reproduce a current requirement, unresolved failure or independent
negative control, with its exact assumptions and source hashes. Do not refresh
hashes without rerunning the affected check. Keep temporary logs and waveforms
outside maintained source. Simplified and deliberately adverse fixtures must
identify their deviations from the selected design.
