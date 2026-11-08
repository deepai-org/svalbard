# Supporting circuit and timing models

The [active model guide](../architecture_fast/README.md) owns current commands,
coverage and limitations. The [architecture inventory](../../spec/analog-architecture.json)
owns the planned chip; this directory does not define another architecture.

Reusable numerical primitives and explicitly scoped experiments live here.
Simplified and deliberately adverse inputs are valid. Importing a shared module
does not establish that an entire test suite matches the current design.

`shared_supply_lifecycle.py` contains independent passive-supply equations and
numerical controls. `reference_sample_clock.py` checks bounded clock-edge
forecast and commit behavior. Their standalone commands do not construct a
chip or qualify physical pads. Use the bounded regression and selected
lifecycle commands in the active guide for integration work.

The [closure inventory](../../spec/mathematical-closure.json) and
[current priorities](../../spec/risk-priorities.md) own completion decisions.
Reports retain their exact assumptions and provenance; source changes require
review or rerun, never a replacement hash alone.
