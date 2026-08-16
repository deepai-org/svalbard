# ADR 0001: PCIe digital proof is software-only

- Status: accepted for project planning
- Date: 2026-08-16
- Scope: `project.pcie_gen1_endpoint`

## Decision

For this project, the edited `pcie_gen1_tapeout_plan.md` takes precedence over portfolio text in `plan.md` that requires FPGA hardware, real root complexes, protocol analyzers, or fabricated pre-submission fixtures.

The digital proof gate instead requires at least two independently implemented PCIe root-complex and transaction-layer software BFMs, formal properties, compiled RTL simulation, protocol assertions, coverage-guided constrained-random testing, mutation testing, and deterministic error injection. Review must establish implementation provenance and guard against common source or interpretation lineage.

Evaluation-board and fixture sources remain required and reviewable, but their fabrication is not a pre-submission dependency. Every result remains explicitly pre-silicon evidence and cannot support a measured compliance or interoperability claim.

## Consequences

The project specification and verification manifests must reject an external-hardware dependency. Portfolio summaries and generated gate reports must apply this recorded project exception instead of silently carrying the older hardware-peer requirement.
