# Whole-chip behavioral model

This guide owns execution and model boundaries. The
[current status table](../../spec/risk-priorities.md#current-status) owns current
conclusions. Completion criteria belong to
[the closure inventory](../../spec/mathematical-closure.json), under `milestone`
and `requirements`. Exact configurations and results belong to the scoped
evidence reports linked from the risk assessment. Do not append experiment history here.

Coverage is checked against all 17 entries in
`contract.generic_control_surface.external_interface_requirements`. The report
must include every target exactly once; adding a contract target without coverage
is an error. Custom GFSK/SDR and frequency-extension stretches explicitly report
missing evidence rather than inheriting HE20 results. Existing pad/transport
lifecycle fixtures are partial: `lifecycle_on_selected_shared_environment` remains
`not_demonstrated` until a matched selected-composition run establishes it.

## Do the tests use the same design?

`design_definition.load_design()` loads `spec/contract.json` and
`spec/analog-architecture.json` into an immutable, validated snapshot. Its
canonical-content fingerprint follows configured electrical environments and
results. Missing required inputs and nonfinite values fail explicitly.
A loader call alone does not prove an entire bench uses that snapshot. Convenience entry points accept a
contract without a snapshot only when it exactly matches the current shared
contract. Modified contracts require an explicit snapshot; the
factory no longer silently combines them with today's architecture. Independent
contract-only mathematical tests remain valid outside these integrated factories.

From `verification/`, the implemented RF packet adapter can be used as follows:

```python
from baseline_envelope import build_model
from design_definition import load_design, Scenario

design = load_design()
config = design.configure(engine="rf", direction="rx", reference_hz=2.426e9,
                          sample_divider=64, pga_gain_db=39)
scenario = Scenario(wanted_dbm=-80, blocker_dbm=-40, reference_peak_v=0.5,
                    assumptions={"temperature_c": 25})
result = build_model(config, scenario).receive(b"diagnostic payload")
```

The constructed adapter retains read-only configuration/scenario properties.
Its `seed`, `environment` and `clock` inspection properties return detached
snapshots; changing an inspection result cannot silently alter the constructed
chip or relabel its evidence. Use a new configuration/scenario to build another
model. The example above has been run through the actual chain: its conditional
clock admission and diagnostic payload decode succeed, with the reported
configuration independently reconstructed.

This adapter runs the existing coded wideband diagnostic with known training
and ideal packet boundaries. It rejects unusable clocks before decoding; it is
not a valid HE PPDU or a universal protocol receiver. Temperature affects RF
and converter thermal noise only, within the selected operating window; gain,
delay, phase-noise, leakage and current temperature coefficients are unmodeled.

Keep three kinds of inputs distinct:

- `design.configure(...)` validates hardware settings against the snapshot.
  The implemented topology is direct external high-frequency timing for RF
  RX/TX and wired operation. Derived rates and legal I/Q gain settings are
  checked; configuration validity does not establish performance.
- `scenario.override(reason=..., ...)` records package return inductance,
  die-decoupling ESL or host-load uncertainty. Unknown overrides fail.
- `design.hypothetical(reason=..., changes={...})` creates a separate circuit
  snapshot with a parent fingerprint and recorded block/device-model changes.
  It cannot silently expand the baseline PGA range. Design-backed RF paths
  require resolved settings; removing configuration cannot restore a default
  sample divider or permit a gain sweep outside the selected circuit. A 54 dB
  requirement experiment therefore owns a hypothetical design with that gain
  explicitly added, while primitive mathematical fixtures stay independent.

The shared-design configuration audit of the maintained test suite is **complete**. Intended-chip
tests use the immutable shared design; independent numerical examples and
declared simplified/adverse fixtures retain their separate scope. Parameter
binding, numerical convergence and physical feasibility remain separate claims.
This test audit does not qualify unexercised optional runner branches.

## Active workflow

Complete the shared mathematical model before new whole-chip schematic work;
the authorized pad implementation is a scoped exception. Prioritize connected
clock quality, RF conversion and pad/package/power constraints. Select a check
because it resolves a current requirement or protects a changed interface.

From the repository root:

```sh
# Planning invariants and coverage; successful execution is not chip acceptance.
python3 projects/programmable_transceiver_platform/verification/check_contract.py

# Aggregate behavioral report; writes evidence/behavioral-system.json.
make transceiver-behavioral

# Focused regressions for selected interfaces.
python3 -m unittest discover -s projects/programmable_transceiver_platform/verification -p test_rf_gain_command.py
python3 -m unittest discover -s projects/programmable_transceiver_platform/verification -p test_direct_stream.py
python3 -m unittest discover -s projects/programmable_transceiver_platform/analog/pads -p test_design.py

# Diagram/inventory consistency without rewriting artifacts.
python3 projects/programmable_transceiver_platform/docs/diagrams/generate_normative_diagram.py --check
```

Run the aggregate after integration changes that justify it; focused documentation
or isolated interface changes do not require every slow experiment. Reports must
identify exact source/configuration fingerprints. Do not restamp a stored report
after changing source, or use a passing unit test to refresh an unrelated campaign.

## What is connected

- `behavioral.py`: event-driven transport and sampled/envelope models, finite
  queues, persistent state, epochs and chunk-equivalence checks.
- `design_definition.py`: immutable shared design, legal numeric settings,
  declared scenarios and explicit hypothetical circuit changes.
- `verification/baseline_envelope.py`: loaded clocks, RF/wired paths, coupled
  supply/reference effects and configuration-bound adapters.
- `verification/selected_lifecycle.py`: retained RF/wired/USB state, startup,
  transitions, fault/recovery and calibration validity under declared forcing.
- `verification/selected_revision_check.py`: focused clock/input-envelope,
  resource-accounting and payload checks; sections have their own fingerprints.
- `verification/direct_stream.py`: finite-byte/credit/CDC response model;
  integration with all RTL and physical timing remains incomplete.
- `verification/rf_gain_command.py` and `rf_timing_command.py`: protected gain,
  sample-epoch, launch and snapshot encodings with external FPGA assembly.

The causal wired receiver estimates transitions on its own timeline and corrects
future sampling. It is not a physically qualified CDR. RF models include held
DAC, filters, mixers, ADC, source/clock effects and scoped feedback; independent
observers and known training do not constitute complete protocol interoperability.
USB protocol parsing/CRC and radio modem decisions belong to the external FPGA.

## Converter continuation interface

`BehavioralChip.configure_converter_input_test(i, q)` accepts the existing numeric
0..3 selections only while stopped. After startup, `bind_sar_converter` binds
those controls to the active RF epoch and the actual `paired_sar` recurrence.
The caller owns timestamps, reference/rail forcing and retained `final_state`;
this adapter does not synthesize sample clocks or automatically make converter
results part of the host stream. Old callbacks fail after STOP/restart. Tests
exercise zero, opposite quarter-reference inputs and normal input without clearing
analog state, and demonstrate that ratiometric codes cannot detect an absolute
reference scaling error. Extra diagnostic-source loading and charge injection
remain absent, so this is functional integration rather than a qualified BIST.

`verification/converter_dynamics.py:paired_sar` accepts `initial_state` from
the previous trace’s `final_state`. The JSON-compatible state retains analog
voltage state and RNG position at completed-conversion boundaries, checks
parameter compatibility, and rejects a restart without acquisition/reset time.
External gain-control state remains caller-owned. Optional `idle_step_s`
subdivides reference/DAC recovery through changing forcing across long idle
gaps; omitting it uses a midpoint approximation. The
`selected_lifecycle.py` retune fixture connects this state to package-derived
clock, rail and reference forcing. SAR reference-recharge current now feeds
back through fixed-reserve waveform relaxation; other ADC activity remains
prescribed. Mid-bit interruption, powered-down leakage and payload recovery
remain unmodeled in this fixture.

## How to read evidence

| Result | Interpretation |
| --- | --- |
| Conditional demonstration | This configuration meets the stated criterion under its explicit assumptions. |
| Expected rejection | The check correctly rejects a fault or unsupported case. |
| Known failure | A required operating case misses a criterion. |
| Inapplicable fingerprint/configuration | The report cannot qualify the current configuration without a matched rerun. |
| Not tested | Required evidence is absent. |

A report-level pass may include expected failures. Read per-case validity,
quality, deadline, flow and scope. Do not combine results from incompatible
power/clock/loading assumptions into a whole-chip claim. Analog parameters,
noise spectra and package properties remain hypotheses unless separately proven.
All 17 capability verdicts remain unresolved.

## Supporting numerical checks

`make transceiver-math-fast` runs bounded mathematical/architecture checks.
`verification/robustness_envelope.py` evaluates declared impairment/mitigation
scenarios. `verification/feasibility_bounds.py` audits assumptions. These are
supporting tools, not replacements for retained acquisition, control, payload
and recovery. Use their exact source assumptions when interpreting output.
Long RF stress campaigns and coupled oscillator startup runs are targeted
experiments; do not launch them without a question that needs their duration.

## Requirements and ownership

- [Current status and risks](../../spec/risk-priorities.md)
- [Completion criteria](../../spec/mathematical-closure.json)
- [Configuration contract](../../spec/contract.json)
- [Host transport](../../spec/streaming-transport-v2.md)
- [Clock ownership](../../spec/clock-rate-ownership.md)
- [RF frequency conventions](../../spec/rf-frequency-coordinates.md)
- [Pad implementation](../../analog/pads/README.md)

Keep current conclusions in these owners and exact reproducible results in scoped
evidence files. Keep large waveforms and transient experiment output in scratch.
