# Evidence index

This directory contains compact, tracked run manifests that identify evidence;
it does not contain raw waveforms, extracted databases, simulator work
directories, or other large generated artifacts.

## Contents

- [`runs/`](runs/) contains immutable JSON run manifests keyed by run ID.
- Block-local summaries, checkpoints, and reproduction commands remain beside
  the source block that owns the claim.
- Product-level interpretation belongs in the relevant project README or in
  [`docs/verification/`](../docs/verification/).

Use `python3 scripts/test_analog_evidence.py` to check the tracked analog
evidence contracts. A manifest records provenance; it does not make a passing
claim stronger than the physical and simulation boundary it names.
