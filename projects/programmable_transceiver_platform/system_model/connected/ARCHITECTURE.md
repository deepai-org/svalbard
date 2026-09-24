# Connected mathematical model layers

These modules supply detailed clock, RF, converter, transport and lifecycle
models used by the current transceiver work. Start with the
[active whole-chip guide](../architecture_fast/README.md) for the fast iteration
command, coverage and current limitations. The [model overview](../README.md)
explains how the behavioral and coupled compositions relate.

RF and wired payloads are **exclusive per die**. Earlier four-path concurrent
experiments remain useful stress cases; they do not impose simultaneous RF/wired
operation on the design. Protocol logic and modem processing remain external.
Chip controls select generic resources and numeric configurations.

## Model responsibilities

| Area | Source / authoritative specification |
| --- | --- |
| Framed host payload, queues and persistent lifecycle | [chip model](chip_model.py), [whole-chip lifecycle](whole_chip_lifecycle.py), [streaming transport](../../spec/streaming-transport-v2.md) |
| Autonomous clocks, divider/PFD/filter and rate ownership | [clock ownership](../../spec/clock-rate-ownership.md), [coarse search and retuning](../../spec/coarse-retune-contract.md) |
| RF mixing, carrier coordinates, blockers and waveform scoring | [frequency coordinates](../../spec/rf-frequency-coordinates.md), [RF quadrature budget](../../spec/rf-quadrature-budget.md) |
| TX calibration, resource admission and cancellation | [shared lifecycle](tx_calibration_services.py), [detailed adapter](tx_calibration_chip.py), [monitor ADC gap](../../spec/tx-detector-shared-adc-gap.md) |
| Loaded TX output, isolation, observation and retained analog state | [output isolation](../../spec/tx-output-isolation.md), [pad observation](../../spec/tx-output-isolation.md#loaded-pad-observation), [unified state](../../spec/unified-analog-state.md) |
| Converter references, shared rails and uncertain coupling | [power partition](../../spec/power-partition.md), [uncertainty envelope](../../spec/feasibility-gates.md#required-treatment-of-unknowns) |
| Wired receiver detection and analog stimulus ownership | [receiver-detect model](../../spec/receiver-detect-model.md) |

Reset, stop, reference loss and retuning must invalidate stale digital work
without erasing physical charge or phase. Clearing queues alone does not establish
safe recovery: host drain/epoch coordination, clock readiness and current
calibration still matter. Shared-resource ownership must cover pending work,
not only the active command. The linked specifications own the detailed contracts.

An assumed independent monitor ADC is not proof of shared I-ADC integration.
Complex-envelope waveform quality is not protocol compliance; held-out scoring
and an independent reference are necessary to avoid cancelling candidate errors.
Uncertain supply/package models are assumptions to sweep, not physical evidence.

## Supporting regression

The detailed suite is an explicit supporting run, not the default fast loop:

```sh
python3 projects/programmable_transceiver_platform/system_model/connected/run_architecture.py
```

[The runner](run_architecture.py) owns the scenario list. It executes fresh checks
and records source/result hashes and logs in
[the aggregate report](../../evidence/connected-architecture-suite.json).
Assertions must remain enabled. Inspect both report status and per-case results;
a process exit alone does not establish acceptance. An older aggregate is not
fresh evidence for changed sources. This suite includes detailed experiments
that may run much longer than the behavioral regression.

The [closure inventory](../../spec/mathematical-closure.json) owns completion gates,
and [risk priorities](../../spec/risk-priorities.md) owns current work priorities.
Neither successful transport nor isolated quality screens establish one fully
verified chip. Full mathematical closure, transistor feasibility, layout/package
performance and standards compliance remain distinct requirements.

## Historical experiment record

The former pass-by-pass journal, through pass 875, is preserved in its
[complete immutable Git version](https://github.com/deepai-org/svalbard/blob/3d06e6263892b2e6755c9f6a6e6d5bf7da4dc678/projects/programmable_transceiver_platform/system_model/connected/ARCHITECTURE.md). It includes the original reset
negative controls, intermediate assumptions, measurements, failed candidates,
source/report names and historical closure lists. Its progress and running-job
statements describe that snapshot, not current execution state.

In particular, fixed-laboratory blockers and carrier-relative blockers are
different experiments. The archived 38.92–42.00% fixed-laboratory errors are not
superseded by the later 7.381–8.031% translated-blocker result. Historical
concurrent-stream and startup-only candidates are likewise not interchangeable
with the current exclusive-mode architecture. Use the current specifications
above for design requirements and the archived journal to interpret old results.
