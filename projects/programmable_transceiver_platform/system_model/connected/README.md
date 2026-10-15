# Supporting circuit and timing models

The [active model guide](../architecture_fast/README.md) owns current commands,
coverage and limitations. The [architecture inventory](../../spec/analog-architecture.json)
owns the planned chip; this directory does not define another architecture.

Retain reusable numerical primitives and explicitly scoped experiments here.
Simplified and deliberately adverse inputs are valid, but a superseded chip
composition is not a substitute for current-design verification. The retired managed-chip and concurrent RF/wired lifecycle trees are removed.
Importing a shared module does not establish that its entire test suite matches
the current design.

`shared_supply_lifecycle.py` contains independent passive-supply equations and
numerical controls. `reference_sample_clock.py` checks bounded clock-edge
forecast and commit behavior. Their standalone commands do not construct a
chip, qualify physical pads, or prove joined RF/wired operation. The obsolete
aggregate architecture runner is removed; use the current bounded regression
and selected lifecycle commands in the active guide.

The [closure inventory](../../spec/mathematical-closure.json) and
[current priorities](../../spec/risk-priorities.md) own completion decisions.
Stored historical results retain their original assumptions and provenance;
source changes require review or rerun, never a replacement hash alone.
