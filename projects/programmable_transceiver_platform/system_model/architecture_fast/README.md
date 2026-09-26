# Whole-chip behavioral model

This guide owns execution and model boundaries. The
[current status table](../../spec/risk-priorities.md#current-status) owns current
conclusions. Exact configurations and retained results belong to
[the closure inventory](../../spec/mathematical-closure.json), especially
`active_workflow.three_demonstrations`. Do not append experiment history here.

## Active workflow

Finish the mathematical architecture before new schematic work. The active
priority is analog clocks, complete RF conversion and physical coexistence;
digital transport refinement is paused except where it constrains those paths.
Start with `python3 projects/programmable_transceiver_platform/verification/feasibility_bounds.py`
for the fast assumption audit. `fractional_pulse_screen.clock_filter_tradeoff_screen`
accepts `extra_frequency_tones` as `(offset_hz, frequency_deviation_peak_hz,
phase_rad)` triples for supply/noise susceptibility. These are declared stimuli,
not calibrated device spectra. Current conclusions and exact audit cases live
in the status owner and closure inventory.

Use focused checks for the current question; run the aggregate when integration
changes justify its cost. Supporting regression commands from the repository root:

```sh
make transceiver-behavioral
python3 -m unittest discover -s projects/programmable_transceiver_platform/verification -p test_bit_event_codec.py
python3 -m unittest discover -s projects/programmable_transceiver_platform/verification -p test_rf_mixer_phase.py
python3 -m unittest discover -s projects/programmable_transceiver_platform/verification -p test_counted_acquisition.py
```

The aggregate writes `evidence/behavioral-system.json`, with source hashes,
assumptions and excluded coverage. It does **not** automatically include every
focused demonstration below. A report generated before a source change remains
historical until rerun; the latest unit suite is not a substitute for it.

The active mitigation comparison is:

```sh
python3 projects/programmable_transceiver_platform/verification/robustness_envelope.py
python3 -m unittest discover -s projects/programmable_transceiver_platform/verification -p test_robustness_envelope.py
```

It reuses RF fixtures and converter/filter models, adds explicit external-LO
integer-divider settings, and optionally models finite FPGA resampling with
charged latency/storage. Desired failures are retained. This fast report does
not replace connected acquisition, dynamic supply or bridge recovery tests;
its clock/host/power checks are separate conditional budgets. The same report
also includes joined spectral receive-mixer/blocker/filter scenarios: phase
noise enters before filtering and common direct-LO phase perturbs ADC timestamps.
The host-PDN subsection now derives one supply-disturbance path from host
activity and a board/package network, including damping cost. A three-node
extension includes shared-return feedback; ground-to-signal/reference coupling,
substrate and complete multi-domain PDN closure remain open.

The report also includes a bounded diagnostic-intervention screen. Existing PGA
settings and stopped external-source replacement are compared using digitized
EVM/RMS and acquisition only. Equivalent post-gain sampler/converter noise is
retained as an ambiguous pair; no hidden model state is a diagnostic observable.
This does not qualify mixed faults, stage isolation or first-silicon procedures.

## How to read evidence

| Category | Meaning |
| --- | --- |
| Conditional demonstration | Declared configuration meets its specific acceptance criteria. |
| Expected rejection | The model correctly detects an injected fault or invalid input. |
| Known failure | A desired configuration misses a requirement. |
| Historical result | Retained result from another version or assumption set. |
| Not tested | No applicable evidence; absence of failure is not a pass. |

`status: passed` on a regression means its assertions passed, including expected
failures. Read per-case quality/deadline/flow results and coverage. Test counts
are not a completeness measure. Synthetic BPSK OFDM is not full Wi-Fi support;
raw NRZI/CRC packets are not a complete USB controller; diagnostic markers are
not standard wired startup. Do not transfer results between different clock,
noise, loading, transport or receiver assumptions.

## Choosing the next check

Choose a check because it resolves an architectural uncertainty or protects a
changed contract, not because it adds another passing case. Before running it,
state the requirement, selected configuration, assumed parameters and failure
criterion. Prefer one connected scenario with finite resources and recovery
over several isolated happy paths when it answers the same question.

Report desired-operation failures separately from successful fault detection.
Keep alternative assumptions separate; do not union their passes into one
claimed chip configuration. A local pass advances only its stated requirement.
Run broader integration when shared state, timing or interfaces change; avoid
repeating costly sweeps without a new question. Update current conclusions in
the status owner and exact evidence in the closure inventory, not in a new log.

## What is connected

`behavioral.py` joins event-driven transport and sampled/envelope analog models.
Persistent state, finite queues and chunk equivalence are important invariants.
Analog parameters and noise spectra remain declared assumptions.

- Host: directional framing/packing, staging, CDC candidates, pacing and epochs.
  Connected RF defaults to exclusive owner allocation and explicit host mode 0;
  low-level helpers and RTL retain legacy comparisons pending reconciliation.
- Wired: `RecoveredWordSource` observes voltages on its own receiver timeline.
  Four observations per interval estimate crossings; correction affects future
  samples. It no longer queries crossings by transmitted bit index. This is an
  ideal sampled detector, not qualified GF180 CDR hardware.
- RF: held DAC, filters, mixers, ADC, shared rail and optional actual pulse-loop
  history; independent external TX/RX observers and known-training recovery.
- USB: generic pad/events and record transports, with an incremental external
  FPGA parser. Protocol decisions and CRC remain external to the chip.
- Lifecycle: stopped configuration, explicit startup/stop, faults and epochs.
  Fixed guards and optional count qualification have different evidence scope.

## Focused wired demonstration

Import `behavioral` from this directory. Use:

```python
staged_wired_duplex(remote_clock_ppm=100., host_clock_ppm=-100.)
staged_wired_duplex(return_clock_gap=True)  # Retained TX-underflow control.
staged_wired_duplex(return_clock_gap=True, recover_tx=True,
                   rearm_delay_s=20e-6, framed_rearm=True)
```

The framed option explicitly changes resumed external source data to training
and diagnostic markers. Acceptance uses received bits and timing qualification;
expected payload is used only for scoring. `tx_word_errors` retains raw grouping
errors; `recovery.framed_payload_errors` scores released frames. Unframed delayed
rearm remains a distinct failure control. Serializer restart is phase-aligned;
serialized management and physical timing are not established.

`causal_compliance_cdr_screen()` adds the four-symbol PCIe Gen1 compliance
pattern from [PCI Express Base Specification 2.1, section 4.2.8](https://www.intel.com/content/dam/support/us/en/programmable/support-resources/fpga-wiki/asset03/pci-express-base-r2.1.pdf).
It tests ±100 ppm, four initial phases through ±3 UI, and an invalid constant-level
interruption. Readiness comes from causal recovered bits and pattern recognition.
It excludes host transport, SSC, link training and endpoint functionality; this
is a targeted receiver screen, not protocol compliance.

## Focused RF demonstration

`connected_tx_port(waveform='he20', ...)` drives an independent voltage observer.
`connected_tx_gfsk_port()` retains the historical GFSK comparison load.
Generic TX defaults to `complete_rail_load=True`, sharing the RX recipe's rail,
host activity and mapped FIFO clock-pin loads with mode-specific bias.

The selected TX configuration is:

```python
from behavioral import connected_tx_port
from tx_output_candidate import PARAMETERS
result = connected_tx_port(
    waveform='he20', payload_seed=977, tx_amplitude=.15,
    tx_voltage_scale=4.518, tx_substeps=16, bias_current_a=.037,
    observer_filter=dict(sample_hz=640e6, cutoff_hz=10e6, order=5),
    tx_output_parameters=PARAMETERS, wait_for_acquisition=True,
    tx_electrical_budget=dict(source_resistance_ohm=40.,
        load_resistance_ohm=50., driver_bias_current_a=.028,
        peak_current_limit_a=.028, headroom_per_rail_v=.3,
        differential=True))
```

Count acquisition preserves 500 µs per observation across reference rates and
requires two good windows. It measures average frequency, not phase quality.
Coupled startup runs can take minutes; do not repeat them for unrelated edits.

`connected_he20_payload` accepts independent remote timing, an input-referred
electrical budget, `pulse_bias_current_a`, and the same pulse-clock acquisition
flags. Its `pulse_complete_load` case is the selected RX composition. Exact RX
settings and launch time are retained under `rf_rx_continuous_bias` in the
inventory; source launch is not silently moved to follow receiver readiness.

`SampledRFStream(receive_source=callable)` uses physical-time envelopes with
retained converter timestamps. The local DAC continues independently. Optional
`capture_cache` dictionaries allow receiver-only reanalysis without rerunning
clock/host state; captures are analysis storage, not on-chip memory. Receiver
fitting must not consume expected payload. The external anti-alias filter does
not qualify the chip's emitted spectrum. Transport bit precision is not ENOB.

## Focused USB demonstration

```python
usb_observed_response(
    request_lengths=(8, 64, 512), usb_data_packet=True,
    host_pacing=True, coalesce_return=True,
    fpga_ingress=dict(clock_hz=100e6, bits_per_cycle=16,
        capacity_records=8, phase_cycles=.37, synchronizer_cycles=2))
usb_ingress_work_screen(processing_phases=(0., .37, .99),
                       service_widths=(16,), synchronizer_cycles=2)
```

Lengths are payload bits. `fpga_processing_s` is the final decision delay
(default 40 ns), additional to ingress work. Capacity includes queued and
in-service data records; overflow suppresses ACK. Synchronization charges
pointer/control visibility, including the boundary event, while payload is held.
Omitted synchronization/capacity options retain historical comparisons, not a
qualified implementation. `command_sync_cycles=2` adds clock-aligned publication into the eight-word
frame-builder domain. The independent-clock candidate fails the focused
exchange with that crossing; zero remains a historical comparison, not proof
of implementable synchronization.

The candidate `fpga_ingress=dict(clock_source='host_ddr', bits_per_cycle=16,
capacity_records=8, synchronizer_cycles=2)` derives processing frequency from
H2D DDR, including its ppm error. Response/frame construction shares this clock
with synchronous block enables; independent phase/frequency and nonzero
`command_sync_cycles` are rejected. Processing is rounded to complete clock
cycles. See [clock ownership](../../spec/clock-rate-ownership.md#fpga-response-path-clock-selection)
for implementation and recovery obligations. With the historical 40 ns final budget its faster-host margin is 4.167 ns.
Adding `decision_cycles=3` explicitly selects the proposed validate/select/publish
pipeline budget instead (29.167 ns finite margin); this is not implemented FPGA
timing or complete USB latency closure. The unused time budget reports null.

A late correct reply fails `meets_budget`. Parser framing/CRC checks do not
establish token/endpoint acceptance, transaction state, attach/reset/chirp,
causal USB CDR, metastability protection or placed FPGA timing.

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
