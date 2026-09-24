# Supporting connected models

Use the [active whole-chip guide](../architecture_fast/README.md) for current
commands, coverage and limitations. [ARCHITECTURE.md](ARCHITECTURE.md) maps the
supporting model layers to their authoritative specifications and explains the
detailed regression. [The model overview](../README.md) describes the relationship
between behavioral and coupled compositions.

This directory contains shared implementation layers and scoped experiments.
Earlier modules remain dependencies of current compositions; historical names
alone do not make them obsolete. Concurrent four-path fixtures are optional
stress tests under the accepted exclusive RF/wired payload policy.

For specific experiments, the [connected runner](run_architecture.py) owns the
scenario list and expected report paths. Its passing checks do not establish
whole-chip closure, transistor performance or standards compliance. Consult the
[closure inventory](../../spec/mathematical-closure.json) and
[current priorities](../../spec/risk-priorities.md) for those decisions.

The former pass-674–687 journal, including original commands, pilot-calibration
examples, measurements and limitations, is preserved in its
[complete immutable Git snapshot](https://github.com/deepai-org/svalbard/blob/3d06e6263892b2e6755c9f6a6e6d5bf7da4dc678/projects/programmable_transceiver_platform/system_model/connected/README.md).
Its prefill, running-container and next-step statements are historical; use the
current source and guides above for present behavior. In particular, the journal's
QPSK/multicarrier fixtures and assumed ADC noise/reference-memory sweeps are
scoped numerical experiments, not Wi-Fi qualification or characterized ADC noise.
