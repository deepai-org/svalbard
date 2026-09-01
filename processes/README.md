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
