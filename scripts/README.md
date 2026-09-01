# Shared scripts

These are repository-wide helpers. Circuit-specific compilers, simulations,
and physical-flow wrappers stay beside the block that owns them.

| Script | Purpose |
|---|---|
| `validate.py` | Repository structure, graph, process, and audit checks |
| `run_analog_flow.sh` | Bounded container wrapper for analog flows |
| `test_analog_evidence.py` | Regression checks for analog evidence contracts |
| `analyze_pex_net.py` | Extracted-network inspection and failure localization |
| `test_analyze_pex_net.py` | Tests for the PEX network analyzer |
| `bfm_source_audit.py` | PCIe BFM source-independence audit |
| `bfm_history_audit.py` | PCIe BFM history/provenance audit |
| `image_lock.py` | Resolve and verify pinned container-image identities |
| `tool_artifacts.py` | Validate pinned tool artifact metadata |
| `verification_deps.py` | Verification dependency checks |

Prefer the root `Makefile` entry points when one exists. Scripts should remain
bounded, deterministic where practical, and free of machine-local paths.
