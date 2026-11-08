# Transceiver mathematical models

Start with the [active model guide](architecture_fast/README.md) for commands,
coverage and limitations, and the [project README](../README.md) for what the
platform aims to enable. Current priorities live in the
[risk list](../spec/risk-priorities.md); formal gates live in the
[closure inventory](../spec/mathematical-closure.json).

`architecture_fast/behavioral.py` is the active whole-chip architecture loop.
Current electrical integration uses `verification/baseline_envelope.py` and
`verification/selected_lifecycle.py` with the architecture inventory. Neither
has established full mathematical or physical closure. Shared implementation
layers live in `architecture_fast` and `connected`. Their presence alone does
not establish system closure.

Protocol names identify external fixtures; chip settings select generic
resources and compatible operating values. Reusable numerical primitives and
explicitly scoped experiments support the selected model.
