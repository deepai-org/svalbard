# Three-capacitor PLL integration status

The local adapter exposes the VCO node and its time integral to oscillator
phase propagation while pump compliance uses the separate pump node. The
50 ns connection screen passes. Fresh-band transfer now preserves all three
capacitor charges, rejecting malformed, boundary and live-state overwrites.
This is not evidence of retune lifecycle or acquisition closure.

The acquisition screen runs the leading linear-resynthesis candidate at
2437 and 2412 MHz for 60 microseconds each, with the original second-order
integer-edge divider, seeded 20 kHz frequency noise, held quiet driver-rail
pull, and unchanged lock criteria. Its incremental report is
`evidence/three-cap-acquisition-screen.json`. A running report is not a pass.
It records source hashes and checks them at completion.

The reference Radau filter remains computationally expensive. A faster
propagator may be warranted after this initial dynamic result, but must
preserve separate capacitor states, compliance and integrated VCO phase.
Full coupled RF quality, rail interaction, acquisition history and lifecycle
remain required before selecting this filter for the full-chip model.

## First carrier result

The leading linear candidate completed 60 microseconds at 2437 MHz without
a compliance fault, but never qualified lock. Over 40–60 microseconds,
reference-edge phase standard deviation was 0.213322063 rad and peak instantaneous
frequency error was 2685531.688 Hz. All 381 recorded source hashes matched when
this first result was inspected. The 2412 MHz case is still running.

This candidate cannot be selected for the integrated chip. The small-signal
noise ranking did not predict acceptable fractional-edge behavior. The next
selection must balance divider ripple and noise suppression, retaining the
original qualification gates. This failure does not reject the entire
three-capacitor topology or establish physical feasibility.

## Completed two-carrier result

Both 60 microsecond cases completed with no compliance fault and no qualified
lock. At 2412 MHz, tail phase standard deviation was 0.195564297 rad and peak
instantaneous frequency error was 2519039.709 Hz. The process exited successfully
as a characterization run, not a passing qualification. All 381 source hashes
matched at completion and independent inspection.

The leading noise-only candidate is rejected at both fractional ratios.
Next work must improve the noise/ripple tradeoff and use edge-driven results
to select candidates before expensive full-chip validation.

## Corrected ranking and balanced candidate

The phase-unwrap branch correction reduced the linear search from 2979 to
645 qualifying candidates. Independent nodal closed-loop eigenvalues confirm
all 60 corrected frontier entries are stable in the averaged model; 18
historical frontier entries with falsely wrapped margins are unstable.
The original report is retained as historical evidence; new selection uses
`pll-filter-resynthesis-corrected.json`.

The balanced acquisition run selects minimum 4 MHz transimpedance among
corrected frontier candidates with at least 50 degrees sampled phase margin
and predicted noise below 0.035 rad. These are search heuristics, not relaxed
chip gates. The chosen crossover is 426923.631 Hz, predicted noise 0.032560837 rad,
and 4 MHz transimpedance 1664.964 ohms. Its two-carrier edge-driven test uses
the same 60 microsecond horizon, noise, rail pull and lock criteria.
`three-cap-balanced-acquisition-screen.json` records progress; running is
not passing, and component feasibility remains unqualified.

## Balanced candidate: first carrier

At 2437 MHz the revised candidate qualified lock at 14.425 microseconds,
recorded zero lock losses, and passed all 800 reference-edge lock observations
in the 40–60 microsecond window. Phase standard deviation was
0.046979237 rad and peak instantaneous frequency error was 206527.279 Hz.
The latter is output-frequency error; the existing lock gate tests frequency
after division, so these are not the same threshold. All 382 launch source
hashes match at this checkpoint. The 2412 MHz case remains running.

This is isolated clock evidence only. It does not establish RF pad quality,
inter-edge ripple, lifecycle closure or full-chip mathematical completion.

## Balanced two-carrier test complete

Both carriers pass the unchanged isolated sustained-lock check. At 2412 MHz,
lock qualified at 13.55 microseconds with zero subsequent losses; tail phase
standard deviation is 0.035174138 rad and peak output-frequency error is
209757.403 Hz. At 2437 MHz the corresponding phase deviation is
0.046979237 rad. The process exited zero and all 382 recorded source hashes
match. These are reference-edge samples with fixed rail pull, not complete
RF phase-noise spectra or EVM measurements.

Next: compose this candidate with the existing finite-reference, driver-rail
feedback and RF pad-quality test. Check coarse acquisition and live retuning
first. The Radau reference filter may require a separately verified faster
propagator before lengthy full-chip runs. Full-chip closure, transistor
schematic closure and layout remain outstanding.

## Independent resistor thermal-noise audit

The candidate ranking explicitly omits resistor noise. The independent
`verification/three_cap_thermal_noise.py` uses three-node admittance analysis,
separate Norton sources for R and R3, and the same averaged fine-loop feedback
(100 µA pump, 200 MHz/V VCO gain, 2437/40 division). It does not change the
390 sources recorded by the still-running coupled test.

At 300 K, the resistor-only estimate is 0.0076243 rad RMS over 100 Hz–10 MHz,
equivalent to 0.49793 ps at 2.437 GHz. Extending to 1 kHz–100 MHz gives
0.0076363 rad. The open-loop passive equilibrium integral matches
kT(1/C3 − 1/Ctotal) within 7.92 ppm, checking source normalization and the
conserved common-charge mode. Doubling frequency-grid density meets a 1e-5
relative convergence check. Evidence: `evidence/three-cap-thermal-noise.json`.

This is neither a total noise budget nor a chip qualification. Sampled-loop
aliasing, fractional mixing, pump, VCO, reference, bias and buffer noise remain
outside this calculation. Centering switches are assumed open. The ongoing
coupled test does not gain this noise contribution retroactively. Future
noise closure must include it without double-counting any existing noise terms.

## First coupled three-cap result: mode 1 passes the existing screen

The coupled run completed with exit code zero. Its launch manifest reports
passed and all 390 recorded source hashes independently match. The report
`connected-limited-rail20-pad-quality-mode1-three-cap-phase-diagnostic.json`
records TX corrected relative RMS 0.0970898261 and RX 0.0744576397, below the
unchanged 0.10 gates. TX uses 544 fit and 1632 held-out samples; RX uses 33 fit
and 99 held-out samples. Original two-cap mode-1 TX was 0.1167460772.

This supports keeping the candidate for further tests, not whole-chip closure.
The traffic window is only 6.5536 µs, the TX margin is 0.291 percentage points,
and this run does not include the separate resistor thermal-noise estimate.
It does not prove standards compliance, PDK performance, variation tolerance,
live retuning, or calibration accuracy. The report retains calibration records
with accuracy unverified; a passed RF quality screen must not overwrite that.
Next test is the same coupled fixture in mode 0, preserving gates and models.

## Independent component and tuning-load sensitivity screen

`verification/three_cap_sensitivity.py` and
`evidence/three-cap-sensitivity.json` screen the balanced candidate using an
averaged linear loop at 2437 MHz. All 128 independent ±10% endpoint combinations
of five passive values, pump current and VCO gain are evaluated at each of five
added VTUNE loads (0, 0.25, 0.5, 1 and 2 pF). These are exploratory stress bounds,
not PDK corners, measured parasitics, or yield estimates. An independent nodal
solve cross-checks the transfer function at three frequencies for every case.

All 640 cases have stable closed-loop poles. Nominal interpolated phase margin
is 50.233 degrees (the earlier coarser frequency-grid estimate was 50.310).
Worst margin across component endpoints is 41.846 degrees with no added load,
39.388 degrees at 1 pF, and 37.130 degrees at 2 pF. The maximum response to the
existing eight finite frequency-disturbance tones grows from 0.03660 rad to
0.03859 rad over these loads. This is not total phase noise or an RF quality
result. Added capacitance reduces 4 MHz transimpedance while degrading damping:
ripple filtering alone is therefore an insufficient selection criterion.

Next priorities after the pending nominal mode-0 coupled run: edge-driven tests
of stressed component/loading cases, realistic tuning/sense-input capacitance
and trim coverage, and complete noise integration. Do not infer lock or EVM
from stable averaged poles. The running mode-0 experiment's 390 model source
hashes were independently checked unchanged after this separate audit.

## Edge-driven follow-up: weakest linear stress case

`verification/three_cap_stressed_acquisition.py` completed successfully; results
are in `evidence/three-cap-stressed-acquisition-screen.json`. The tested case is
the weakest linear-margin combination from the exploratory sensitivity screen:
R, Cf and R3 +10%, Cs -10%, C3 +10% plus 2 pF tuning load, pump current and VCO
gain +10%. This is a stress fixture, not a foundry-qualified process corner.

Both fractional carriers completed 60 us with all 800 final-window observations
locked, zero lock losses and no compliance faults. At 2437 MHz, first lock was
14.425 us and final-window phase standard deviation 0.050664 rad; peak sampled
frequency error was 196227 Hz. At 2412 MHz, first lock was 12.55 us, phase standard
deviation 0.036397 rad, and peak sampled frequency error 155015 Hz. The original
divided-reference frequency criterion and lock qualification are unchanged.

The process exited zero; all 390 model source hashes and the test script hash
were independently verified at completion. This strengthens isolated acquisition
evidence under loading/component stress, but does not prove stressed RF quality,
full noise performance, integrated retuning, or process yield. Reference-edge
sampling does not capture all inter-edge ripple. The nominal coupled mode-0
quality test remains running; preserve its model sources until completion.

## Second coupled three-cap result: mode 0 passes the existing screen

The mode-0 process exited zero. `three-cap-pad-quality-mode0-launch.json` records
passed status and matching source hashes; an independent completion check also
matched all 390 model sources. The report is
`connected-limited-rail20-pad-quality-mode0-three-cap-phase-diagnostic.json`.

TX held-out relative RMS error is 0.0956959492 (9.5696%), using 544 fitting and
1632 validation samples. RX error is 0.0594026031 (5.9403%), using 82 fitting and
246 validation samples. Both retain the original 10% limit and gain-range gate.
The traffic window is 8.192 us, with 328 RF samples and 1024 wired words in each
direction, matched reference traffic, no underflows or discards, and no ADC clips.
Finite supply/reference loading, integer-edge fractional division and seeded
frequency disturbances remain enabled. Nine shared-ADC samples and nine
maintenance observations are recorded. The result is a mathematical screen,
not a standards-compliance measurement or transistor qualification.

Both nominal modes now pass this coupled quality screen, with only 0.4304 and
0.2910 percentage points of TX margin for modes 0 and 1 respectively. The
resistor-only thermal-noise estimate was not injected into either run. Complete
noise, component/loading variation in coupled traffic, integrated retuning,
and calibration accuracy remain open. In particular both mode-0 calibration
records explicitly report `valid: false`, with accuracy unverified because an
independent observation or error bound is missing. The quality-screen pass must
not override that status or be promoted to full-chip closure. Next model work
should address these missing qualification paths; transistor schematic closure
and layout remain later stages of the unchanged full-chip objective.

## Calibration observation uncertainty is not closed by a nominal quality pass

`verification/calibration_observation_budget.py` reads both completed coupled
reports. Their frontend has 1 mV RMS independent Gaussian noise per component,
while the calibration controller requests a 1 mV residual tolerance. The older
300 uV observation bound is a fixture assumption: Gaussian noise alone lies
inside that interval only 23.58% of the time, before quantization or other error.
Do not set that bound on the coupled chip merely to make validity turn true.

The budget evidence keeps a 12-bit quantizer half-LSB (244.14 uV) as systematic
uncertainty, rather than assuming it averages away. At unity gain/reference,
known stationary independent noise, and near-zero measured residual, at least
19 samples would be needed for an exploratory 99.9% confidence interval narrower
than 1 mV. This is optimistic: actual gain/reference uncertainty, settling,
supply error, drift and correlation must also be included. Gaussian confidence
must remain explicitly statistical and must not be reported as a hard bound.
Next calibration implementation work should add repeated observations through
the existing shared converter ownership/timing path and an explicit statistical
qualification result, while retaining unverified status when its assumptions
are absent. No calibration status or acceptance gate was changed by this audit.

## Fixed-window statistical residual assessment implemented

`system_model/connected/calibration_statistics.py` now evaluates a predetermined
observation window using declared independent Gaussian noise, positive bounded
observation gain and bounded systematic error. Quantization uncertainty can be
included in the systematic term without assuming it averages away. Incomplete,
stale, clipped, nonquiet or unbudgeted observations cannot qualify. The result
separates `statistical_pass` from deterministic `valid`, which remains false;
it does not silently turn a probabilistic interval into a hard guarantee.

`verification/calibration_statistics_screen.py` passed negative controls and
40,000 synthetic windows spanning zero, near-tolerance and failing residuals,
gain endpoints and systematic bias endpoints. Coverage counts were 10000,
10000, 9994 and 10000 out of 10000 respectively; no 3 mV residual was qualified
against the 1 mV tolerance. This validates the mathematical assessment under
its assumptions, not the physical budget. A 64-sample zero-mean fixture with
1 mV RMS noise, half-LSB systematic error and gain [0.95, 1.05] has a 99.9%
residual interval of approximately ±0.690 mV. These remain explicit fixtures.

Repeated shared-ADC sampling, epoch/ownership cancellation over the whole
window, and reporting through the integrated controller are not yet connected.
Confidence is per predetermined window; retries require an explicit combined
failure-probability policy. Existing completed coupled evidence used the prior
390-file model snapshot; this newly added module is a subsequent model revision.

## Repeated maintenance ADC observation path

`StatisticalCalibrationMixin` in `statistical_calibration_lifecycle.py` adds an
opt-in fixed observation window to the existing maintenance converter path.
`AutomaticCalibrationChip` now exposes an observation hook and schedules another
reference-derived sample edge immediately when the observation remains pending.
The original single-observation path is unchanged by default and its existing
regression passed.

`verification/statistical_calibration_lifecycle_screen.py` passed 64-conversion
windows under one versus 173 advance calls with identical traces. All 64 samples
load the reference, use the existing converter transfer/latency, and remain out
of normal ADC/host traffic queues. Loss of reference after partial collection,
with another conversion in flight, cancels that conversion, clears collected
samples, restores the saved trim and preserves accounting. The final result
retains deterministic valid=false while exposing statistical qualification.

The policy is opt-in and its uncertainty values remain fixtures. This lifecycle
screen does not inject frontend noise; the separate statistical screen covers
synthetic Gaussian windows. Full coupled integration, explicit host statistical
status reporting, and physical uncertainty budgets remain unverified. No old
coupled result is attributed to these new sources.

## Statistical status and full-chip composition

The opt-in statistical calibration mixin now exposes model-level `cal_status`
bit 13 for statistical qualification and bit 14 for statistical failure. Bit 9
retains its hard-bound validity meaning. Bit 12 remains asserted whenever that
hard-bound validity is unverified, including after statistical qualification.
These are proposed protocol additions; corresponding RTL is not yet implemented.
Lifecycle tests read status through actual management commands after success,
cancellation and missing-assumption results. Cancellation accounting remains
recorded separately from the subsequent missing-assumption fixture.

`StatisticalThreeCapChip` composes the observation mixin with the existing finite
reference/driver three-cap chip. Construction, method-resolution routing to the
observation hook, and advancement to 100 ns passed, recorded in
`statistical-three-cap-connection.json`. That check does not execute calibration
or traffic and must not be treated as full coupled qualification. Statistical
policy remains disabled by default; no unsupported physical budget is installed.

### Repeated calibration: coupled mode 1 completed

The repeated-observation coupled mode-1 run exited successfully. Independent
post-run verification matched all 393 connected-model source hashes, the test
script hash and the result digest in
`statistical-three-cap-quality-mode1-launch.json`.
The unchanged 10% corrected-relative-RMS gates passed: TX
0.09426249821052962 (544 fit / 1632 validation samples), RX
0.07341897134632823 (33 fit / 99 validation samples).
Maintenance accounting is 128 sampled / 128 completed / zero cancelled or pending;
each I/Q target completed its predetermined 64 observations. Both records retain
`valid=false`, `statistical_pass=false`, and `accuracy=unverified` because the
physical observation assumptions and uncertainty budget remain unvalidated.
This establishes nominal mode-1 integration of repeated observations, not
calibration accuracy, complete noise/variation coverage, or transistor closure.
The next regression is the identical repeated-observation policy in mode 0.

### Repeated calibration: coupled mode 0 completed

Mode 0 exited successfully with 64 observations per I/Q calibration target.
Independent post-run verification matched all 393 connected-model source hashes,
the wrapper hash and result digest in `statistical-three-cap-quality-mode0-launch.json`.
Maintenance accounting was 128 sampled, 128 completed, zero cancelled and zero pending.
Both calibration records remain explicitly unverified; repeated observations do not
establish the missing physical uncertainty budget.

Corrected TX relative RMS was 0.09524730054194543 (9.525%), with 544 fit and
1632 validation samples; corrected RX relative RMS was 0.058190530944620907
(5.819%), with 82 fit and 246 validation samples. Both unchanged 10% screening
gates passed. Together with completed mode 1, this supports repeated-observation
integration in both nominal coupled modes. It does not establish full-noise,
variation, retune/recovery, transistor or layout closure. The TX margin remains
small; coupled noise and loading sensitivity remain priority risks.

### Coupled mode 1: exploratory worst-damping stress completed

The stressed repeated-calibration run exited 0. Independent post-run checks
matched every source/input hash and the result digest in
`stressed-three-cap-quality-mode1-launch.json`. The stress uses the previously
ranked worst linear-margin component endpoint and adds 2 pF at VTUNE; it is not
a validated PDK corner. Corrected TX RMS error was 0.099773848117563 (9.9774%),
with 544 fit and 1632 validation samples. Corrected RX RMS error was
0.06265516185111737 (6.2655%), with 33 fit and 99 validation samples.
Both unchanged 10% gates pass, but TX has only 0.0226 percentage points of
margin. This is effectively a marginal candidate, not robust quality closure.
Calibration uncertainty remains unverified and full physical noise is absent.
Next prioritize additional noise sensitivity and improved TX/PLL margin;
retain this stress as a regression rather than relaxing its gate.

### Finite-window resistor-noise sensitivity

`verification/resistor_noise_window_screen.py` evaluates stationary linear
closed-loop phase response for the stressed component values, using the same
128-tone resistor spectrum. Across 128 seeds and a representative 6.5536 us
window, mean-removed phase RMS ranges from 0.004914 to 0.011968 rad; the
5th/median/95th percentiles are 0.005904/0.008309/0.010416 rad. Seed 1249 gives
0.007393 rad. Doubling temporal sampling from 2048 to 4096 changes every
reported seed RMS by less than 1.08e-8 rad. The independent complex nodal
transfer matches the existing PSD helper. Source hashes and results are in
`evidence/resistor-noise-window-screen.json`.

This establishes substantial realization sensitivity over short windows, not
coupled-chip failure probability. The stationary window is not aligned with
actual traffic; mean subtraction does not reproduce the chip's fitted complex
gain, and nonlinear fractional-clock effects are excluded. A single coupled
thermal-noise pass will therefore remain insufficient for noise-margin closure.
The running coupled test is unchanged by this independent audit.

### Exact finite-tone propagation prototype

`verification/thermal_filter_exact_step_screen.py` independently propagates
three voltages, integrated VCO-control voltage, and pump charge using a matrix
exponential and complex sinusoidal particular solutions. It preserves the
128-tone forcing and the affine pump-current law within a fixed compliance
region. Twelve fixtures cover held, up, down, centering, and both pump-compliance
polarities at 1 ns and 10 ns, beginning at an absolute time of 120 us.
Against the existing Radau solver, maximum node-voltage disagreement was
3.997e-15 V. Phase-integral and pump-charge tolerances also passed. The median
measured per-step timing ratio was approximately 39.6; this is a small-fixture
benchmark, not a full-chip speedup result.

The prototype is deliberately outside the connected model and has not changed
the running thermal-noise test. It lacks source-work/dissipation propagation,
certified compliance-boundary detection, and region-crossing handling. Sampled
fixture paths only check that these particular comparisons stay in one region.
Those obligations must be resolved before substituting it for Radau. Results
and source hashes: `evidence/thermal-filter-exact-step-screen.json`.

### Prototype energy-accounting fixtures

`verification/thermal_filter_energy_screen.py` now integrates pump-plus-thermal
source work and resistor-plus-centering dissipation along the exact fixed-region
state trajectory. Twelve short-step cases match Radau work/loss to within
5.73e-28 J, conserve stored energy to within 3.53e-26 J, and produce nonnegative
incremental dissipation. Increasing Gauss-Legendre order from 8 to 16 changes
work/loss by at most 6.27e-27 J. This is fixture evidence, not a general error
bound for arbitrary steps. Boundary/crossing support and full-chip integration
remain outstanding. The connected model and live experiment are unchanged.
Evidence: `evidence/thermal-filter-energy-screen.json`.

### Conservative boundary guard prototype

`verification/thermal_filter_guard_screen.py` bounds every node's absolute
slew using the maximum pump current, 2*limit resistor voltage drops, summed
thermal-tone amplitudes, and optional centering conductance. A step is eligible
for analytic propagation only when these bounds keep it strictly inside both
the voltage domain and its starting pump-compliance region. Uncertain steps
use the original Radau solver on a copy; quadrature disagreement also falls back.
The bounds use floating point with a voltage cushion, not formal interval arithmetic.

Eleven fixtures passed: interior, held, centering, both compliance polarities,
both actual compliance-knee crossings, exact knee, and conservative long-step
fallbacks. The initial test expected 1 ns rolloff steps to use the fast path;
the guard correctly rejected that expectation. Those cases remain as fallback
regressions, with separate 0.1 ns cases exercising the analytic rolloff path.
Maximum voltage disagreement against a finer-step reference was 1.11e-13 V.
Original model state is preserved. Quadrature convergence remains empirical;
full-chip integration and an end-to-end performance measurement are outstanding.
Evidence: `evidence/thermal-filter-guard-screen.json`. Live chip sources unchanged.

### Complete guarded prototype benchmark: do not integrate yet

`verification/thermal_filter_guard_benchmark.py` compares 100 sequential pump
commands at each of 0.1, 1, and 10 ns, including voltage/phase/charge, work/loss,
and boundary/fallback overhead. All repeated-state comparisons passed; maximum
voltage difference was 2.99e-16 V and energy-accounting difference 1.97e-27 J.
However the complete prototype is **slower**, with reference/prototype timing
ratios 0.131 and 0.405 at the two shortest intervals. All 10 ns steps fell back
to Radau, giving approximately equal runtime. The earlier ~40x isolated-state
benchmark does not translate into useful integrated acceleration.

Do not substitute this prototype into the chip model yet. Repeated matrix
exponentials/resolvent solves at each power-quadrature point are avoidable;
cache the fixed-region decomposition and batch trajectory evaluation before
reconsidering integration. The coarse global guard also limits long-step use.
Evidence: `evidence/thermal-filter-guard-benchmark.json`. This negative result
changes the next action; correctness alone does not justify a slower solver.

### Batched trajectory prototype benchmark

`verification/thermal_filter_batched.py` diagonalizes the capacitance-weighted
symmetric three-node conductance matrix once per step. It evaluates finite-tone
voltage and integrated-voltage trajectories in batches for power quadrature,
using stable entire-function expressions near the conserved-charge eigenvalue.
The existing conservative boundary guard and Radau fallback remain in effect.

`verification/thermal_filter_batched_benchmark.py` passed identical 100-step
command sequences at 0.1, 1, and 10 ns. Full-step reference/prototype timing
ratios were 1.08, 3.45, and 1.01 respectively; the 10 ns case used only fallback.
Maximum voltage error was 7.60e-16 V, integrated-voltage error 2.57e-23 V*s,
and energy-accounting error 1.94e-27 J. This resolves the measured quadrature
implementation overhead for the 1 ns fixture, not full-chip runtime or all
compliance/centering cases. Broader regression is required before integration.
Evidence: `evidence/thermal-filter-batched-benchmark.json`. Live sources untouched.

### Batched prototype seeded regression

`verification/thermal_filter_batched_regression.py` passed 120 seeded short-step
fixtures with exploratory +/-10% passive changes, 0–2 pF additional VTUNE load,
different thermal-noise phases, absolute start times up to 1 ms, held/positive/
negative pump commands, centering, and compliance-near initial states. Seventy-one
steps used analytic propagation; 49 used boundary fallback. Every case also
passed one-step versus two-half-step state comparisons and preserved the source
object. Against finer-step Radau, maximum node-voltage error was 2.82e-14 V,
integrated-voltage error 5.78e-22 V*s, and energy-accounting error 2.43e-26 J.
Evidence: `evidence/thermal-filter-batched-regression.json`.

This improves confidence in a future solver substitution, but does not verify
an autonomous PLL, accumulated long-duration phase, or full-chip traffic. The
live coupled thermal-noise experiment and connected sources remain unchanged.

### Short autonomous-clock comparison completed

`verification/thermal_filter_clock_comparison.py` completed 100 reference periods
(2.5 us) of the same 2437 MHz fractional-clock acquisition using original and
batched resistor-noise filters. Physical integer divider/pump operation and
seeded oscillator/resistor noise were retained. Independent post-run source
hash verification passed. Lock decisions matched at all sampled reference edges;
maximum output phase difference was 2.73e-12 cycles, frequency difference
4.77e-6 Hz, and node-voltage difference 2.34e-14 V.

Reference runtime was 38.50 s versus 33.77 s for the batched prototype, a 1.14x
ratio. Committed filter steps recorded 27 analytic and 172 fallback operations;
forecast-copy work is not included in those counters. The observed runtime
benefit is modest because the global guard rejects most longer intervals.
This is a short acquisition comparison, not sustained lock, full-chip traffic,
retuning/centering integration, or complete noise qualification. The original
full-chip thermal-noise test remains unchanged and active. Evidence:
`evidence/thermal-filter-clock-comparison.json`.

### Local comparison-system boundary bound

`verification/thermal_filter_local_guard.py` uses the actual starting voltages
and the positive state-transition matrix of the fixed-region RC circuit to bound
all deviations during a step. Integrating exp(A*t) against the sum of absolute
initial derivative and bounded thermal forcing yields a componentwise monotone
radius. Analytic propagation is allowed only if that entire box avoids voltage
and pump-region boundaries. Floating-point evaluation retains a voltage cushion;
this is an analytical comparison bound, not a formal interval proof.

The same 120 seeded varied fixtures passed with 104 analytic steps and 16
fallbacks, versus 71/49 for the global bound. Maximum node-voltage disagreement
was 1.39e-14 V; split-step and all other state checks passed. Evidence:
`evidence/thermal-filter-local-guard-regression.json`. A separate short autonomous
clock comparison is now running via `thermal_filter_local_clock_comparison.py`.
Neither connected sources nor the original coupled thermal run were modified.

### Local-guard short clock comparison completed

The local-guard autonomous comparison passed all 100 reference-edge samples
and independently reverified its source hashes. Reference runtime was 38.73 s
versus 3.15 s with the batched/local-bound solver (12.31x ratio). All 199 committed
filter advances took the analytic path. Lock decisions matched; maximum phase
difference was 3.64e-12 cycles, frequency difference 8.45e-5 Hz, and node-voltage
difference 4.24e-13 V. Energy-accounting differences remained below 1.98e-24 J.
Evidence: `evidence/thermal-filter-local-clock-comparison.json`.

A 60 us isolated comparison has now been launched in
`verification/thermal_filter_long_clock_comparison.py`, retaining the same
reference trajectory and asserting lock throughout the last 800 reference
periods in both solvers. It will check accumulated phase and sustained behavior;
no result is claimed yet. The original full-chip thermal-noise run is unchanged.

### Long autonomous comparison passed; separate full-chip test launched

The 60 us original-versus-batched filter comparison completed successfully,
including identical lock decisions and sustained lock throughout the final 800
reference periods (20 us) for both solvers. Independent source-hash verification
passed. Maximum phase difference was 8.74e-11 cycles, frequency difference
0.000202 Hz, and node-voltage difference 1.01e-12 V. Reference runtime was
513.23 s versus 74.91 s (6.85x); all 4,799 committed batched-filter steps used
the analytic route. Evidence: `evidence/thermal-filter-long-clock-comparison.json`.
This remains one isolated nominal carrier/noise realization, not full-chip proof.

`verification/batched_thermal_stressed_three_cap_quality.py` now launches a
separate mode-1 stressed coupled run using that filter adapter, the same physical
noise and calibration policy, and the original quality/readiness gates. Its
100 ns construction/advance smoke check passed. Output uses the distinct
`three-cap-batched-thermal-stressed-repeated-cal` experiment tag and
`batched-thermal-stressed-three-cap-quality-mode1-launch.json` manifest, hashing
all connected sources plus the prototype helpers. The original reference run
continues untouched. Full-chip comparison and quality are pending.

### User-directed speedrun: fast connected architecture entry point

Added `system_model/architecture_fast/run.py` and its README as the fast whole-chip
functional reference, using the existing averaged-clock `OscillatorSupplyChip`
composition rather than waiting for physical-node PLL integration. All eight
scored cases passed in 85.0 s: both contract modes, RF loopback and independent
multicarrier input, and both signs of assumed gain/phase/supply impairments.
All four data paths operate simultaneously. Corrected held-out RF waveform error
ranges from 3.699% to 6.379%, below the unchanged 10% screen. Each case exercises
reference-loss disabling and opposite-mode reacquisition on the same chip after
traffic. Payload/accounting, empty final queues and no TX underflows are checked.
Independent post-run source-hash validation passed. Evidence:
`evidence/fast-whole-chip.json`.

This is the executable functional mathematical reference, not closure of physical
noise, on-chip calibration accuracy, fractional-divider implementation or package
uncertainty. Assumptions and remaining refinements are explicit in its report.
An initial harness assertion incorrectly equated the session's armed flag with
path enable; the test now checks both actual enable gates after faulting. A stale
external-input API name from an older example was also corrected in the new
runner. Connected sources and both ongoing detailed thermal tests were untouched.

### Fast model independent TX observation

Added an external non-feedback probe of reconstructed TX envelope times its own
LO phase to the fast whole-chip runner. All eight cases passed separate TX and
RX quality screens, with identical baseline/actual observation times. TX corrected
RMS range was 0.457889%–0.942565%. Held-out phase-inversion controls fail as required.
The revised suite completed in 84.95 s and source hashes were independently
verified. Probe sampling does not establish emission masks or DAC-image rejection.
Evidence: `evidence/fast-whole-chip.json`.

### Fast connected RF oscillator-noise sensitivity

`system_model/architecture_fast/clock_noise.py` passed both operating modes with
an assumed 20 kHz RMS RF frequency-noise spectrum (eight lines at 250 kHz spacing,
seed 839), positive analog impairments and independent multicarrier input.
Independent TX corrected RMS was 1.856% / 1.883%; RX was 4.141% / 6.943% for
modes 0 / 1. Both wired directions, finite transport, and reference-loss/mode
recovery remained checked. Baseline and actual observation times matched exactly.
Post-run source hashes verified. Evidence: `evidence/fast-whole-chip-clock-noise.json`.
This adds connected stochastic-spectrum sensitivity to the fast reference, not
physical noise closure; wired oscillator noise and full budget remain open.

### Fast simultaneous oscillator-noise check

The fast connected model now perturbs both RF and wired oscillators with separate
20 kHz RMS finite frequency-noise realizations (seeds 839 and 840). Both modes
pass wired payload checks, reference-loss recovery, and the unchanged 10% RF
quality screen: RX 4.141% / 6.943%, independently probed TX 1.856% / 1.883%.
Evidence: `evidence/fast-whole-chip-clock-noise.json`, with verified source hashes.
These assumed spectra provide sensitivity evidence, not device characterization
or closure of the physical timing/noise budgets.

### Completed stressed resistor-noise full-chip mode-1 check

The original Radau coupled run completed and passed: independent TX corrected
RMS 9.7300707%, RX 5.8541343%, against the unchanged 10% screen. Source hashes
and result digest were independently verified from
`evidence/thermal-stressed-three-cap-quality-mode1-launch.json`.
This includes the exploratory passive/load/pump/Kvco stress and 300 K,
100 Hz–10 MHz, 128-tone resistor-noise realization with seed 1249. It is one
finite realization, not a worst-case noise bound or PDK corner. TX margin is
only 0.270 percentage points; calibration accuracy remains physically unverified.
The separately launched accelerated-solver comparison is still running.

The accelerated coupled mode-1 run has now completed. Both manifests and result
digests verify against current sources. TX corrected RMS differs from the
original Radau result by 1.8074e-9 absolute; RX matches exactly. See
`evidence/thermal-full-chip-solver-comparison.json`. This establishes agreement
of these final metrics for this case, not all internal trajectories or corners.
