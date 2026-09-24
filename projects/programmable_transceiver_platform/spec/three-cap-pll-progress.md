# Three-capacitor PLL: retained findings and evidence

This is a historical research summary, not the active project schedule.
[The complete experiment journal](https://github.com/deepai-org/svalbard/blob/32aa5622d72b53d566cd8ed5100b2a67e1818b99/projects/programmable_transceiver_platform/spec/three-cap-pll-progress.md)
preserves all intermediate measurements, failures, parameter choices and source
snapshot qualifications. Current priorities and completion gates belong in
[risk-priorities.md](risk-priorities.md) and
[mathematical-closure.json](mathematical-closure.json).

## Model contract

Keep pump, slow and VCO capacitor states distinct. Pump compliance senses the
pump node; oscillator phase uses the VCO-node voltage integral. Preserve charge
across allowed band transfers, reject malformed or live-state overwrites, and
commit state only after a successful solve. A fast propagator must preserve
these quantities and failure behavior, not merely reproduce an endpoint voltage.
Finite driver/reference loads, acquisition history, calibration and retuning
remain part of integration. Isolated filter or clock success is not chip closure.

## Evidence and limits

| Finding | Evidence / boundary |
| --- | --- |
| Leading small-signal candidate failed acquisition | Both 60 us, 2412/2437 MHz cases completed without qualified lock. Linear noise ranking alone was insufficient. See `evidence/three-cap-acquisition-screen.json` and the historical journal. |
| Balanced candidate passed isolated two-carrier lock tests | Reference-edge phase deviations were about 0.0352/0.0470 rad under assumed noise and held rail pull; these are not total phase-noise spectra or EVM. |
| Resistor thermal-noise normalization checked | `evidence/three-cap-thermal-noise.json`: about 0.00762 rad RMS over 100 Hz–10 MHz at 300 K, with equilibrium/convergence checks. Omits pump/VCO/reference/buffer noise, sampled aliasing and fractional mixing. |
| Nominal coupled quality can pass while calibration uncertainty remains open | A fixture observation bound cannot be promoted to a physical guarantee. See `evidence/calibration-observation-budget.json`. |
| Stressed resistor-noise mode-1 run passed narrowly | `evidence/thermal-stressed-three-cap-quality-mode1-launch.json`: TX 9.7300707%, RX 5.8541343% against the provisional 10% screen. One finite noise realization and exploratory component stress, not a PDK corner or worst-case bound. |
| Accelerated solver matched that run's final quality metrics | `evidence/thermal-full-chip-solver-comparison.json`: TX difference 1.8074e-9 absolute, RX exact. Does not establish trajectory/corner equivalence. |

The retained failure of the first candidate does not reject the entire topology.
Conversely, later conditional passes do not establish GF180 device noise,
physical power, tuning coverage, yield, or package interaction.

## Calibration interpretation

The coupled fixtures assumed 1 mV RMS independent Gaussian component noise and
a 1 mV residual tolerance. A 300 uV observation bound is not a hard bound on that
noise. Keep quantizer half-LSB and other systematic uncertainties separate from
averagable random error; gain/reference error, settling, drift and correlation
must be budgeted. Statistical confidence is not deterministic validity.

`connected/calibration_statistics.py` evaluates fixed observation windows with
declared noise, gain bounds and systematic error. Stale, incomplete, clipped,
nonquiet or unbudgeted observations cannot qualify. Confidence applies to each
predetermined window; retries need a combined failure-probability policy.
Repeated shared-converter implementations and their later evidence are recorded
in the historical journal; their existence does not characterize physical errors.

## Maintained implementation and checks

The three-node filter and clock families live under `system_model/connected`.
Thermal regression and clock comparisons share
`verification/thermal_filter_batched_regression.py` and
`verification/thermal_filter_clock_comparison.py`; their local/long entry points
retain different guard and observation-window choices. See the
[consolidation audit](../docs/consolidation.md) for refactor validation.

Use the [active model guide](../system_model/architecture_fast/README.md) for
normal iteration. Expensive isolated/coupled thermal runs are targeted supporting
checks, not the default loop. No process described in the old journal should be
assumed still running; verify an actual process handle before continuing it.
