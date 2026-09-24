# Whole-chip behavioral model

## Active workflow

From the repository root:

```sh
make transceiver-behavioral
```

[`behavioral.py`](behavioral.py) is the active architecture screen. It combines
sampled/envelope RF and event-driven wired/host behavior without integrating
transistor or oscillator waveforms. The recorded regression takes about ten
seconds; runtime varies. It writes
[`behavioral-system.json`](../../evidence/behavioral-system.json), including
source hashes, assumptions, scenario outcomes and missing coverage.

`status: passed` means the regression assertions—including negative controls—
passed. Read per-case `conditional_system_pass` and `coverage` for capability
status. `full_chip_closure` and physical qualification remain false.

## What is connected

| Part | Present behavior | Remaining boundary |
| --- | --- | --- |
| Configuration/lifecycle | Generic resource and numeric settings, exclusive RF/wire admission, startup guard, stop/reference-loss epochs, handovers | Startup guard is assumed; complete calibration, retune and recovery remain open |
| Host transport | Persistent directional finite queues, independent source/H2D/D2H events, actual payload packing, prefill, delayed occupancy feedback and chunk-equivalence checks | Feedback ABI/RTL and general service/stability envelope are unfinished |
| RF samples | Selectable sample rates and converter precision, persistent DAC/filter/mixer/ADC state, gain, carrier offset and impairment controls | Live host path and richer quality observer are not yet unified for all target fixtures |
| RF observation | Known-training timing/gain/carrier recovery, HE20 equalization/pilot tracking, GFSK prefix acquisition, held-out decisions | Synthetic fixtures do not establish standard packet acquisition or complete protocol support |
| Wired receive | Incremental channel/slicer/CDR words delivered through host queues at six rates from 1.25 to 2.5 Gb/s; common fast-channel time constant in seconds | Separate-screen initialization in holdover cases; continuous startup fixtures at 1.25/2.5 Gb/s use a fixed training guard, not a qualified lock detector |
| Video timing | Fractional/intermediate x10 references, sampled forwarded PLL checks and supporting lane-group model | Complete multi-chip payload, deskew, continuous FIFO and pad integration remain open |
| USB pads | Host/device pad lifecycle probes, NRZI/stuffing payload and contention controls; short-frame turnaround screen | Complete attach/reset/chirp negotiation and burst recovery are not established |
| Power | Configuration-dependent average current/droop plus RF ripple and assumed host-coupling screens | One dynamic supply/clock/RF composition, package and thermal envelopes remain open |

The suite includes 60 baseline assumption scenarios and 23 numeric configuration
cases. Numeric recipes use the planned fifth-order RX response; historical
one-pole comparisons are not substitutes for those results. Precision settings
are converter model choices, not measured ENOB. Numeric sideband controls are
behavioral candidates, not a finalized register ABI.

Eight continuous wired startup cases exercise ±0.35 UI initial phase and ±100 ppm
frequency error at 1.25/2.5 Gb/s. Each delivers 6,150 error-free scored bits after
a fixed 2,040-bit external training guard through the same channel/CDR/host state.
A provisional timing monitor qualifies 64 observed edges below 0.1 UI error
and revokes qualification after 64 transition-free bits. Silence and transition-loss
controls pass. After a +100 ppm source step during a 1,000-bit gap,
qualification and payload recover. A 10,000-bit gap also requalifies timing but
corrupts payload alignment; this negative control prevents treating timing
qualification as link readiness. This is bounded timing evidence; wrapped phase cannot detect
whole-bit slips, and protocol word lock and general acquisition remain open.

The model tests payload identity in connected 8/12-bit GFSK paths and wired
receive paths. Other quality screens use separate waveform projections. Passing
sample transport is insufficient evidence of RF quality, and a short passing
waveform is insufficient evidence of a sustained operating link.

## How to read quality evidence

The current numeric sweep contains conditional passes and failures. BLE 2M,
LoRa and several gain settings fail; BR and proprietary GFSK also have failing
combined cases despite passing their baseline quality screen. Consult the report
for exact settings and offset conditions instead of treating a protocol name as
a single pass/fail property.

HE20 evidence uses BPSK with trained equalization and pilot tracking. It does not
establish all Wi-Fi 6 modulation/coding modes. The provisional 10% quality screen
is an architectural budget, not a universal standards limit. Blocker, compression,
clock-gap and supply-coupling negative controls expose failure envelopes; their
parameters are hypotheses rather than measured GF180/package characteristics.

State persists across calls for the live RF/filter and transport paths. Separate
waveform diagnostics still have different scope. Keep these distinctions explicit
when adding tests; no single fixture currently proves the entire system.

## Optional supporting checks

```sh
# Longer, multi-seed RF robustness; outside the default iteration loop
python3 projects/programmable_transceiver_platform/system_model/architecture_fast/behavioral.py --burst-stress

# Bounded supporting numerical/architecture checks
make transceiver-math-fast

# Expensive coupled checks: use only for a specific unresolved question
python3 projects/programmable_transceiver_platform/verification/full_chip_check.py --detailed
```

The coupled constructor is
[`full_chip_model.make_chip`](../../verification/full_chip_model.py), model ID
`exclusive-coupled-domains-host-v1`. Its canonical diagnostics must use that
constructor; results from older subclasses do not qualify it automatically.
Supporting blocks include [`chip.py`](chip.py), [`warm_chip.py`](warm_chip.py),
[`lane_group.py`](../connected/lane_group.py),
[`protocol_signals.py`](../connected/protocol_signals.py) and
[`protocol_pad.py`](../connected/protocol_pad.py).
Do not run long coupled startup simulations as the default architecture loop.

## Requirements and ownership

- [Contract](../../spec/contract.json): configurations and external recipes.
- [Transport](../../spec/streaming-transport-v2.md): framing and service obligations.
- [Clock ownership](../../spec/clock-rate-ownership.md): timing conventions.
- [RF coordinates](../../spec/rf-frequency-coordinates.md): signal conventions.
- [Risk priorities](../../spec/risk-priorities.md): what to address next.
- [Closure inventory](../../spec/mathematical-closure.json): completion gates.

Keep experimental measurements in evidence reports and current conclusions in
these owners. Do not append chronological progress logs to this guide.
