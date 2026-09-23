# Fast mathematical transceiver model

This is an executable functional prototype, not a completed transistor schematic
or proof of GF180 performance. Mathematical closure and the layout gate remain
open. The required product supports **RF or wired payload operation, not both
simultaneously**; see [the current policy](../../spec/exclusive-engine-policy.md).
Existing simultaneous-traffic runners are retained as optional stress tests.

## Model compositions

| Entry | Role | Important limits |
| --- | --- | --- |
| `chip.py:TransceiverChip` | Common calibrated RF/wired model | Historical concurrent operation; memoryless RF output approximation |
| `warm_chip.py:WarmTransceiverChip` | Adds coarse startup, finite recentering and warm retuning | Separate subclass; not automatically covered by common quality results |
| `../../verification/fast_loaded_output.py:LoadedOutputChip` | Finite output network shared by pad observation, calibration detector and RX loopback | Assumed passive RC network; no nonlinear driver current/supply limits |
| `../../verification/fast_exclusive_engine.py:ExclusiveEngineChip` | Loaded model with mutually exclusive payload admission/session enables | Inactive bias/clock shutdown and RTL implementation remain open |

The common model connects host framing and finite queues, wired serialization
and receive timing, ADC/DAC quantization and delay, RF mixing and filtering,
shared reference charge, supply coupling, sampled autonomous clocks, calibration,
diagnostics and managed lifecycle control. It does not instantiate external
FPGA modem, MAC or endpoint protocol logic.

The receiver defaults to a fifth-order Butterworth filter at 9.157407 MHz.
`rx_filter=None` explicitly selects the historical single-pole comparison.
RF output parameters and detector readout settling are constructor parameters.
Preparation/calibration belongs to the caller; creating a chip does not silently
calibrate it. A 12-bit transport word is not a claim of 12-bit converter ENOB.

`configure_rx_gain(gain)` selects 0.5, 1 or 2 without changing the filter
topology or its stored state. The serialized `configure_rx_gain` command maps
payloads 0/1/2 to those gains; other encodings reject. Changes require a disarmed
receiver with no active calibration or pending ADC/maintenance conversion.
The older combined `configure_rx` command includes single-pole bandwidth tuning
and remains unavailable with the selected multipole topology. This gain command
is a mathematical management interface; its pin-level RTL encoding is not yet
implemented. It models an ideal gain setting, not a qualified physical PGA.

## Run from the repository root

```sh
make transceiver-math-fast
python3 projects/programmable_transceiver_platform/verification/fast_exclusive_engine_check.py
python3 projects/programmable_transceiver_platform/verification/fast_exclusive_management_check.py
OPENBLAS_NUM_THREADS=1 python3 projects/programmable_transceiver_platform/verification/fast_loaded_traffic.py --exclusive
```

The loaded-traffic runner's `--exclusive` option selects RF before calibration
and uses the existing count-free RF duplex fixture in both rate profiles. It
checks ordered DAC input, ADC return data, bounded queues, conversion accounting,
loaded-output isolation at stop, and zero wired payload. Results are written to
`evidence/fast-exclusive-rf-traffic.json`; its status is authoritative. This is a
finite transport test with lossy stop, not RF quality or inactive clock/bias
shutdown qualification. Without the option, the historical four-path stress
fixture remains available.

Use `fast_loaded_traffic.py --power-gated` for the experimental powered
exclusive composition (`--exclusive` is implied). It additionally checks zero
wired-oscillator frequency and fixed phase throughout RF streaming. Its separate
report is `evidence/fast-powered-rf-traffic.json`. Oscillator shutdown and a timed
readiness guard do not yet model bias-current/supply transients or a physically
shared synthesizer.

Use `OPENBLAS_NUM_THREADS=1` for repeatable, economical simulation runs.
The common acceptance suite runs 12 executables / 38 case rows, checks shared
source snapshots and result digests, and writes
[fast-common-acceptance.json](../../evidence/fast-common-acceptance.json).
It covers continuous transport, external RF and nonlinear loopback quality,
calibration cancellation, diagnostics, receiver detection, overflow/restart,
transaction-level local operation, warm retuning and LO sideband integration.
These selected scenarios do not establish exhaustive architectural closure.

The historical transport profiles are 1.25 Gb/s wired with 40 MS/s 12-bit I/Q,
and 2.5 Gb/s wired with 20 MS/s 8-bit I/Q. Exclusive-mode bandwidth reallocation
is pending. Stop/abort explicitly accounts for discarded data; it is not a
lossless-stop guarantee. A finite FIFO cannot absorb persistent rate mismatch.

## Consolidated RF stress runner

```sh
OPENBLAS_NUM_THREADS=1 python3 projects/programmable_transceiver_platform/verification/fast_rf_quality.py --variant blockers
OPENBLAS_NUM_THREADS=1 python3 projects/programmable_transceiver_platform/verification/fast_rf_quality.py --variant load
OPENBLAS_NUM_THREADS=1 python3 projects/programmable_transceiver_platform/verification/fast_rf_quality.py --variant signed
```

| Variant | Additional conditions | Report |
| --- | --- | --- |
| `blockers` | +20/+30 MHz blockers at 0.1 amplitude, RF cubic distortion, noise/loading | `fast-blocker-quality.json` |
| `load` | Profile DAC reference load 2 pF; ADC/DAC delays 2/1.5 sample periods | `fast-profile-load-quality.json` |
| `signed` | Profile converter gain and wired-phase coupling in both signs; signed oscillator sensitivity | `fast-signed-coupling-quality.json` |

Each variant compares matched baseline/impaired runs. RX uses independent
multicarrier input; TX is observed separately. One complex gain is fitted on the
first quarter and frozen for held-out samples. The unchanged corrected RMS gate
is 10%. Passing selected assumed parameters is not Wi-Fi compliance, a spectral
mask, physical coupling qualification or a complete uncertainty bound.

## Loaded output and exclusive-mode work

The loaded adapter retains capacitor voltage through output/dummy switching and
propagates exponential source terms using the actual LO phase segment. Pad
observation reads node 1; calibration detects pre-isolation monitor node 2.
Loopback uses the same interval-start network modes as the detector and pad.
Independent stiff-ODE and subdivision checks validate that numerical connection.

Absolute-gain calibration rejects the attenuated monitor path. Explicit
`tx_relative_gain=True` permits relative I/Q fitting; it neither normalizes away
network attenuation nor proves absolute pad amplitude or calibration accuracy.

Relevant executable checks live in `../../verification/`:

- `fast_loaded_output_check.py`: independent pad transient and switch continuity.
- `fast_loaded_loopback_check.py`: simultaneous network/filter ODE comparison.
- `fast_loaded_calibration_check.py`: shared-ADC observation and gain semantics.
- `fast_loaded_traffic.py`: both-mode loaded four-path transport (historical stress).
- `fast_exclusive_engine_check.py`: selected-engine admission and stopped transitions.
- `fast_exclusive_management_check.py`: serialized selection/status and epoch fences.

Loaded waveform quality, full selected-engine duplex, per-mode calibration
validity, analog shutdown and shared-synthesizer implementation remain open.
The transaction model is not SPI-pin/CDC or RTL opcode verification.

## LO approximation and numerical checks

`lo_drive.py` projects normalized switching effectiveness into desired/image and
sideband terms. It does not map transistor gate voltage to switching efficiency.
`lo_mixer.py` applies these terms ahead of receiver filtering with absolute-time
phase. Independent quadrature, switched-mixer and ODE checks are retained in
`lo_*check.py` here and `lo_*truncation*.py` under `../../verification`.

The single-pole modulated approximation exceeded the proposed 0.3% error budget
at some observation phases. The intended fifth-order filter passes the tested
fixture. Neither result establishes physical high-frequency rejection: switch
feedthrough, filter parasitics, aperture and changing-symbol coverage remain open.

## Evidence and history

[Closure inventory](../../spec/mathematical-closure.json) tracks open requirements.
[Model audit](../../evidence/fast-model-audit.json) checks selected source/result
provenance; rerun `../../verification/fast_model_audit.py` when sources change.
A stale report remains historical evidence, not current qualification.

The previous 608-line chronological model README is preserved in Git commit
`de268da`. [Repository consolidation notes](../../docs/consolidation.md) explain
retention and recovery. Keep this page an entry point; put implementation
contracts in code/specifications and measured outcomes in focused reports.
