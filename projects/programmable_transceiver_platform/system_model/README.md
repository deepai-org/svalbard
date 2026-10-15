# Transceiver mathematical models

Start with the [active model guide](architecture_fast/README.md) for commands,
coverage and limitations, and the [project README](../README.md) for what the
platform aims to enable. Current priorities live in the
[risk list](../spec/risk-priorities.md); formal gates live in the
[closure inventory](../spec/mathematical-closure.json).

`architecture_fast/behavioral.py` is the active whole-chip architecture loop.
Current electrical integration uses `verification/baseline_envelope.py` and
`verification/selected_lifecycle.py` with the architecture inventory. Neither
has established full mathematical or physical closure. The retired dual-synthesizer full-chip constructor and its integration runners
have been removed. Remaining shared modules must still be assessed against the
current architecture; their presence does not establish system closure.

`architecture_fast` and `connected` contain shared implementation layers.
Reusable circuit primitives and explicitly scoped experiments are retained;
superseded managed-chip lifecycle compositions have been removed. Protocol names identify external fixtures,
while chip settings select generic resources and compatible operating values.
