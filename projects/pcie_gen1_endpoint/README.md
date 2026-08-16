# PCIe Gen1 endpoint

This project targets a GF180 PCIe Gen1 x1 endpoint for a constrained common-clock, short, low-loss channel. Its evidence is pre-silicon only: it must not be described as PCI-SIG compliant, interoperable, production-qualified, or yield-qualified without the corresponding measured and provider-accepted evidence.

The project-specific authority is [`pcie_gen1_tapeout_plan.md`](../../pcie_gen1_tapeout_plan.md), interpreted within the repository rules and gates in [`plan.md`](../../plan.md). Where the portfolio plan calls for FPGA or laboratory peers, the project-specific plan replaces that requirement with at least two independently implemented software BFMs, formal verification, compiled RTL simulation, constrained-random testing, mutation testing, and error injection.

Current state: pre-G0/G1. Unknown legal, provider, PDK, electrical, package, and channel inputs are explicit blockers and are not filled with assumed values.
