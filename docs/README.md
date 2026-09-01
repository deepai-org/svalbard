# Documentation index

Use this directory for reviewed explanations and decisions. Executable source,
run wrappers, and block-local evidence stay beside the block that owns them.

## Architecture decisions

- [`adr/0001-pcie-software-only-verification.md`](adr/0001-pcie-software-only-verification.md)
  records the PCIe verification strategy.

## Roadmaps and governing inputs

- [`roadmap/analog-evidence-compiler-spec.md`](roadmap/analog-evidence-compiler-spec.md)
  is the product-first tooling roadmap.
- [`roadmap/g0_process_provider_eligibility.yaml`](roadmap/g0_process_provider_eligibility.yaml)
  records process/provider eligibility.
- [`roadmap/public_source_audit.yaml`](roadmap/public_source_audit.yaml) records
  the public-source audit.

## Verification and design guidance

- [`verification/pcie-analog-status.md`](verification/pcie-analog-status.md) is
  the current PCIe analog progress authority.
- [`verification/pcie-architecture-checkpoint.md`](verification/pcie-architecture-checkpoint.md)
  gives the system-level PCIe architecture review.
- [`verification/pcie-analog-speed-budget.md`](verification/pcie-analog-speed-budget.md)
  records the GF180 speed assumptions and budget.
- [`verification/analog-layout-closure.md`](verification/analog-layout-closure.md)
  is the reusable analog layout and evidence practice.
- [`verification/analog-evidence-tooling-overview.md`](verification/analog-evidence-tooling-overview.md)
  describes what the current tooling actually automates.

The remaining files in `verification/` are focused feasibility or canary
reports. `images/` contains review illustrations referenced by project and
block documentation; an image alone is not verification evidence.
