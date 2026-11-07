# Process inputs

This directory records fabrication-process assumptions and locks. It contains
metadata and public-flow boundaries only, never an installed or restricted PDK.

## GF180

[`gf180/`](gf180/) contains:

- `process.lock` — the selected public process/PDK identity;
- `data_gaps.yaml` — physics and provider information that is unavailable or
  not qualified for current claims;
- `image_candidate.yaml` — the pinned candidate tool-image input.

Treat these files as shared inputs to every GF180 result. Simulator acceptance
of a model is not evidence that the model is valid outside its documented
geometry, bias, temperature, or frequency envelope.

The 2026-11-07 reuse audit found that `gf180/image_candidate.yaml` records
Open_PDKs 1.0.605; do not assume it predates the documented May–June 2026 analog
PCell fixes. That metadata is not an inspection of installed generator files.
The pad generator `projects/programmable_transceiver_platform/analog/pads/layout.py`
uses image ID `sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17`,
which was absent from the local Docker daemon at the audit. Rebuilding requires
recovering its reproducible image recipe/source identity and checking the PDK
contents against recorded evidence; do not silently replace it with a newer
image or equate it with `image_candidate.yaml`'s registry digest. Existing
recorded circuit results are not fresh reproductions while that dependency is
unavailable. This is a tooling gap, separate from provider acceptance or silicon
qualification.
