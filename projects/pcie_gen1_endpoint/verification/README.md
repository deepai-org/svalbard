# Verification strategy

The digital endpoint must be independent of the physical implementation and use common generated vectors and scoreboards across RTL, generated RTL, synthesis, real pad-cell models, the final gate netlist, and the post-layout netlist.

No external FPGA, root complex, protocol analyzer, or laboratory hardware is a completion dependency. At least two software BFMs with independently reviewed implementation provenance are required. The regression matrix must cover every scenario in `spec/spec.yaml`, formal protocol and safety properties, compiled simulation, assertions, coverage-guided constrained random tests, mutation testing, and deterministic error injection.

The digest-locked `make bfm-smoke` target now passes representative upstream self-tests for both candidate models under network-disabled resource limits. This qualifies acquisition and basic execution only; it is not evidence against the SVALBARD endpoint.

`bfm_candidates.yaml` records a provisionally independent pair. Their exact source archives and transitive source dependencies are checksum-locked in `dependencies.lock`; `make verification-deps-fetch` is the only networked acquisition step. Specification-interpretation independence, boundary adapters, scenario mapping, and endpoint-facing tests remain Gate G1 blockers.
