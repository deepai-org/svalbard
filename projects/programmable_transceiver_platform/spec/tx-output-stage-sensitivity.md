# TX output-stage feasibility evidence

## TX reconstruction and output-stage sensitivity — 2026-09-21

The terminal reconstructed managed-host duplex run passes its two finite cases:
TX error 8.286% / 9.631%, with out/in ±10 MHz integrated power −43.148 / −38.956 dB.
The actual and ideal chains both contain a continuous-time four-pole elliptic
reconstruction core plus an explicit 80 MHz buffer pole. Independent state-space,
subdivision, continuity, reset retention and RX cascade checks pass. These results
are incremental waveform quality and finite-burst spectra, not protocol masks.
The filter core's highest pole-pair Q is about 5.78; achievable noise, tuning,
headroom, loading, area and power remain unqualified.

`tx_output_stage.py` adds a local-LO-frame memoryless I/Q imbalance, complex LO
feedthrough and cubic compression model. The analytical screen checks exact
wanted/image decomposition, carrier leakage, single-tone compression, two-tone
third-order products and invalid-domain rejection. Frozen full-chip output traces
supply the sensitivity stimulus; this does not yet couple driver loading or power
back into clocks or supplies. Trace hashes are recorded in the report.

Mode 1 fails the unchanged 10% waveform screen with 0.25 dB gain imbalance
(10.183%), 2 degree quadrature error (10.161%), or −30 dBc assumed LO feedthrough
(10.556%). The combined 0.25 dB / 2 degree / −40 dBc / 3% peak-compression trial
fails at 10.891%; mode 0 passes that trial at 9.111%. These are sensitivity
assumptions, not foundry predictions or guaranteed tolerance bounds. Gain/phase
calibration uses only the existing training portion; held-out samples remain held out.

Next priority: model realizable I/Q correction and its observation/quantization
error, then integrate the output stage into the live chip with explicit loading.
Clock/noise margin remains a parallel limiting factor. Default candidate and full
architecture closure are unchanged; no new aggregate suite pass is claimed.

## Power-only I/Q correction — 2026-09-21

Added `tx_iq_calibration.py` and its analytical / frozen-trace screen. Nine
independent DC I/Q probes identify the quadratic power response H and its linear
term h. The correction uses inverse Cholesky whitening and offset −H^-1 h,
quantized to 12 fractional bits, with explicit conditioning, coefficient range
and actuator-headroom rejection. No true mixer parameters or waveform validation
samples enter the fit. A power-only observation leaves absolute phase ambiguous;
the existing training-only complex-gain fit handles the remaining rotation.
This requires a nonsingular positive-orientation mixer. It is a proposed TX
calibration capability, separate from the implemented RX offset controller.

Exact affine-model controls recover a separate test tone to under 3 ppm at
20-bit coefficient precision. Rank-deficient probes, negative powers and a flat
response are rejected. The 144 sensitivity cases cover two full-chip trace modes,
8/10/12-bit monitor quantization, six bounded measurement-error amplitudes and
four fixed seeds. All cases through 2% power error pass the provisional 10%
waveform criterion; this finite sample is not an adversarial bound. Mode 1's
combined output-stage trial improves from 10.891% to 9.637–9.645% with quantization
alone. At 2% monitor error its tested maximum is 9.855%; at 5% it reaches 10.101%,
and at 10% it reaches 10.720%. Failures remain in the report.

The detector is assumed square-law and error is relative to maximum probe power,
not signal-relative at every probe. ADC full scale has 25% headroom. Detector
offset, curvature, frequency response, loading and supply feedback are unclosed.
Correction is currently applied to continuous baseband ahead of the modulator;
this does not establish finite-code DAC implementation, filter transient behavior,
calibration scheduling or host/control integration. Compression remains in the
output stage and is not inverted. No new whole-suite pass is claimed.

Next: implement the correction at the actual DAC-code boundary with paired I/Q
updates, quantization/headroom checks, filter settling and managed quiet ownership;
then integrate a finite-time power observation instead of a direct array fixture.

## Paired DAC-code correction — 2026-09-21

`RfTxState.apply_sample` now has an identity-by-default correction hook before
its physical DAC transfer and gain. `DacCorrection` applies the fitted 2×2 matrix
and offset to both components, checks headroom before committing either code,
and rounds to signed 8/10/12-bit samples. Offset is divided by reconstruction DC
gain so the settled modulator input receives the requested correction. It does
not erase reconstruction state. Coefficients are static; live updates are not
implicitly authorized or implemented.

The local connected queue → correction → DAC hold → elliptic reconstruction →
RF output-stage test uses 128 bias-settling samples followed by independent
multitone samples. At 12 bits / 40 MS/s, error falls from 7.593% to 0.0816%; at
8 bits / 20 MS/s, from 7.649% to 1.311%. This is local distortion against a
matched ideal reconstruction, not the full-chip noise/jitter budget. The test
checks paired overrange rejection preserves held code, consumed count and queued
sample, and same-time reset preserves every filter state. Prior cascade and TX
observer controls also pass after the default-preserving hook change.

Reset still sets held DAC input to zero. LO leakage therefore requires a separate
mixer/driver disable; calibration offsets must not silently become an idle or
reset behavior. The test assumes matched I/Q filters and does not include DAC
nonlinearity, host interference or autonomous clocks. Next closure work is a
finite-time detector and managed quiet/calibration/commit lifecycle, followed by
full-chip integration with the independently observed modulated output.

## Finite-time TX detector — 2026-09-21

Added continuous square-law detector convolution over the live reconstruction
filter exponential terms, including widely-linear I/Q mismatch and LO leakage.
The first-order detector retains charge across abort. ADC requests capture its
state and publish a quantized, saturation-flagged result only after 100 ns;
abort invalidates pending results with an epoch increment. Independent numerical
quadrature matches the analytic detector convolution within 1e-12. Early reads
and aborted reads reject.

With an assumed 200 ns detector time constant, 10-bit ADC and 0.1 normalized
power full scale, nine quantized DAC probes produce these local calibrated-tone
errors: 100 ns dwell 23.409%; 500 ns 2.679%; 2 us and 5 us both 0.0634%.
The 2 us dwell sequence takes 18.9 us including ADC latency. Filter charge is
retained between probes; coefficients use actual quantized probe values and
reconstruction DC gain. These are finite assumed cases, not settling bounds.

The model is still a local composition. Managed quiet ownership, output disable,
coefficient commit, detector loading/mismatch, cubic output distortion and
full-chip noise coexistence remain open. Calibration validation here uses a
separate tone with continuous correction, while finite-code actuation was tested
separately; their complete joined lifecycle is the next requirement. Neither
this screen nor previous local results establish full mathematical closure.

## Timed TX calibration controller — 2026-09-21

The local sequence now joins quantized probes, continuous reconstruction,
square-law detector settling, delayed ADC observations, fitting and atomic paired
DAC correction installation. Nine probes require 18 scheduled events. No
coefficient is installed before a separate current-generation/current-epoch quiet
commit. Sequence cancellation drops pending ADC results and releases the held
probe without erasing filter or detector charge. Tests cover cancellation before
any observation, during conversion, between probes, at the last conversion and
while awaiting commit. Stale generation, stale epoch and nonquiet commits reject;
a committed result loses validity after epoch change.

`tx_calibration_sequence_screen.py` passes. This remains local composition:
whole-chip scheduler integration, physical output isolation, observed residual
verification and actual shared-resource ownership are not yet implemented.
The controller's valid flag denotes successful coefficient commit, not proven
analog accuracy. Its static fit cannot establish detector or actuator fidelity.
Cancellation retains installed coefficient storage while invalidating its validity;
the future parent must enforce that validity before RF activation.

## Experimental managed TX calibration integration — 2026-09-21

`TxCalibrationChip` now extends the coarse-retuning candidate with serialized
start/status/abort/commit commands, finite detector events, queued-command event
splitting, reconstruction state and paired coefficient installation. The targeted
screen passes: competing mode configuration and RX calibration reject while TX
calibration owns maintenance; an old generation cannot commit; current commit
succeeds; a restarted search cancels on reference loss and clears pending ADC work.
The default chip class is unchanged.

This is not yet an admissible full-chip calibration profile. It assumes an
independent power ADC and usable RF LO in quiet/reset maintenance. Actual clock
readiness, monitor resource mapping/loading, RF output isolation, correction
validity gating on subsequent RF activation and both-mode correction width must
be completed. Commit validates sequencing only, not independent residual accuracy.
No combined waveform or aggregate suite pass is claimed for this candidate.

## TX calibration clock and activation guards — 2026-09-21

The experimental managed candidate now rejects TX calibration start before both
counted coarse qualification and RF PLL lock. Commit and ongoing calibration
also require that clock readiness. Reference loss cancels immediately. The
updated command screen first verifies cold start rejection, then acquires the
real mathematical clock through managed coarse search before probing.

Mode configuration requires committed current calibration and clock readiness;
after configuration the DAC correction is rebuilt for the selected sample width.
Both mode0/12-bit and mode1/8-bit activation checks pass, including rejection of
mode activation before calibration. Managed coarse retuning and selected analog
configuration changes invalidate committed calibration. Direct configuration
mutation coverage still needs a comprehensive audit.

This experimental policy currently gates the whole mode, including wired-only
use, on TX calibration. That restriction must be replaced by per-resource RF TX
activation before promotion: independent wired, RF RX and MCU use remain required.
Successful coefficient commit still does not constitute a residual measurement.
The monitor's independent ADC, RF isolation and full output/supply coupling remain
unqualified. No complete traffic or aggregate-suite result is claimed here.

## RF TX-specific admission — 2026-09-21

Removed the experimental whole-mode calibration prerequisite. Mode configuration
now preserves independent RX/wired operation; RF TX descriptors, scheduling and
sample-queue admission require current-epoch committed calibration plus RF clock
readiness. A default-no-op queue admission callback covers framed and playback
samples that ultimately enter RfTxState.accept, without changing existing default
candidates. Both-mode screens configure successfully without TX calibration,
reject three transmit entry paths without queue/decoder mutation, and complete
eight RX captures each. The RX test uses the existing default source and proves
capture control independence, not external RF signal quality. Full wired traffic
has not been rerun for this candidate.

The finite-code correction regression still passes. Outstanding obligations:
residual verification, output isolation, monitor ownership/loading, complete
direct-mutation invalidation and already-scheduled transmit behavior on validity
loss. Admission alone must not be described as complete RF output safety or
whole-chip calibration closure.

## Queued TX invalidation — 2026-09-21

Active TX calibration abort now invokes existing whole-chip fault/drain recovery
instead of merely clearing the validity flag. Added a final validity/epoch/clock
check before completing pending DAC updates. The targeted three-case screen
passes: abort before sample consumption discards both queued samples; abort with
one consumed sample cancels its pending DAC conversion and discards the remaining
sample; an injected validity loss is caught at DAC completion with the same
accounting. No cancelled case applies a later DAC update. These tests use real
managed coarse acquisition, calibration and mode activation, then isolate the
abort application boundary (command latency is covered separately).

Fault/drain recovery interrupts other streams too; this is explicit fault
semantics, not independent TX-only recovery. Physical RF output isolation and LO
leakage suppression remain unproven. The tests do not establish nonzero filter
charge retention during an actively modulated abort; that obligation has local
filter evidence but still needs a joined active-output scenario. Full-chip
residual-quality verification and monitor resource integration remain priorities.

## Independent TX verification and observability limit — 2026-09-21

Added 33 independent verification probes (zero plus 16 rotated phases at each of
two radii) and conservative bounded-error radial-power assessment. Verification
uses no training-probe reuse or fitted postmeasurement gain. The corrected affine
fixture passes; uncorrected imbalance/leakage, large observer uncertainty and
radial nonlinearity reject. At normalized power full scale 0.1, quantization-only
8-bit verification fails the provisional leakage/error limits, while 10 and
12 bits pass with half-LSB uncertainty. Other detector errors still need budget.

Crucially, exact counterexamples pass power verification despite I/Q conjugation
or amplitude-dependent phase distortion. The result therefore always reports
waveform_verified=false. No power-only verification can establish RF modulation
quality against those failure modes. This changes the next priority: a coherent
observation or external independent waveform qualification must complement the
power detector, with receiver impairments and shared-LO cancellation explicitly
accounted. Do not promote committed coefficients or radial-power success to a
full-chain quality certificate.

These are synthetic independent-measurement controls, not yet timed integrated
verification. Public-PDK transistor uncertainties and monitor resource/area costs
remain open. Full-chip mathematical closure is still false.

## Independent coherent TX observation — 2026-09-21

Frozen reconstructed full-chip traces now have executable observability controls.
Independent TX errors 8.286% / 9.631% become only 0.793% / 0.531% in an ideal
zero-delay shared-LO receiver. Adding 0.3 rad sinusoidal common LO phase error
raises independent errors to 26.250% / 22.213%, while shared-LO results remain
unchanged. Coherent observation with an ideal receiver detects conjugation and
amplitude-dependent phase distortion missed by a power detector. A constructed
invertible TX mismatch followed by its inverse RX mismatch leaves the observed
cascade unchanged despite failed TX-alone quality. Unknown receiver response
therefore prevents separate TX identification from that loopback alone.

Architecture decision: retain independent nominal-carrier observation as the
full-chain mathematical qualification instrument. Internal power/loopback checks
are calibration aids with explicitly limited observability, not replacements for
that instrument. A future silicon prototype can use external coherent test
instrumentation through existing RF pins; no new on-chip reference receiver or
extra package terminals are assumed by this decision. Actual calibration
implementation and complete modulator/output/load integration remain unfinished.
The offline controls do not implement an RF tap or validate receiver loading.

Next highest-value integration: run corrected DAC samples through the actual
full-chip output-stage observer with autonomous clocks, rather than only through
local screens or frozen trace transforms. Keep independent receive-quality and
spectral checks and preserve failing cases.

## Monitor transfer calibration and headroom — 2026-09-21

Connected the assumed passive RF tap to finite settling/12-bit power ADC readings,
I/Q fitting and finite DAC correction in a local signal-path experiment. Ignoring
the detector/pad voltage-squared transfer0.56048 causes1.33573 output gain and
rejects the0.8+j0.8 DAC input due to headroom. The normalized waveform quality
screen still passes: it can hide this absolute-gain problem. Oracle tap-ratio
normalization gives1.00009 gain and accepts that input. Estimated ratio−10%/+10%
gives gains0.94853/1.04875, respectively. All samples used the same detector
observations; no validation waveform was used to fit correction coefficients.

This demonstrates a missing system requirement: independently bound monitor
transfer and absolute transmit amplitude/headroom before interpreting normalized
quality as sufficient. Oracle normalization is a control, not an available
on-chip measurement. Frequency-dependent loading, package/matching, detector bias
and supply feedback remain absent. A separate tap-ratio characterization or
relative-I/Q-only correction with separately managed overall gain must be selected;
the present calibration cannot identify unknown transmitter gain and unknown
monitor gain independently. Report: connected-tx-monitor-headroom.json.

## Relative policy live result and finite-resolution limit — 2026-09-21

Relative-gain managed mode1 with readout gain/offset/curvature is terminal and
passes: TX8.5836%, out/in power−38.3619 dB. The fitted baseband gain is0.9621,
versus0.8826 for absolute correction with the same readout impairments. Source
hashes match launch. This remains one finite full-chain case, not absolute-power
regulation or a detector uncertainty guarantee.

New24-case local ADC-resolution/monitor-gain sweep shows exact-power scalar-gain
invariance is insufficient. At10 bits and monitor power gain0.003, the peak probe
is only2 ADC codes; fit remains invertible but independent waveform error is
14.640%. Other weak cases either reject or exceed a provisional2% correction-only
budget. At12 bits and gains≥0.3 tested local errors are below0.1%. Report preserves
all failures; no empirical code threshold is promoted as a guarantee.

Next derive a conservative fit-uncertainty bound from ADC quantization and declared
observer/model error, then gate calibration acceptance on that bound. Matrix
invertibility and a committed coefficient generation alone cannot certify accuracy.
The2% local budget is not a relaxed replacement for full-chip10% quality checks.

## Bounded affine-fit uncertainty — 2026-09-21

Implemented coefficient enclosure from p=Dq+e and |e|≤epsilon:
|qhat−q|≤|pinv(D)|epsilon. A Frobenius bound on Hessian error gives conservative
corrected-Gram eigenvalue intervals using the actual quantized actuator matrix.
The result reports positive-definiteness robustness, relative axis-spread bound
and residual offset bound in monitor-scaled amplitude units. It always reports
waveform_verified=false; the power fit cannot certify phase fidelity or absolute
RF gain.

Exhaustive512 sign corners per case verify the coefficient/eigenvalue enclosures.
The10-bit/gain0.003 case that previously fit with14.6% error fails robust positive
definiteness. At monitor gain0.56, quantization-only relative axis-spread bounds
are0.6376% at10 bits and0.1629% at12 bits. Increasing declared observation error
weakens the bounds. No empirical ADC-code threshold was substituted for this
calculation.

Bounds assume an affine modulator/square-law observation plus bounded per-probe
error. Quantization is only one contribution: detector readout curvature,
settling, RF compression, additive noise and input-coordinate uncertainty require
explicit allocations. Managed commit still denotes sequencing success, not an
accuracy certificate. Integrating a gate without those bounds would make an
unsupported claim; next quantify model discrepancy with independent probes.


## Analytic nonlinear probe error budget — 2026-09-21

The existing nonlinear-chain audit completed and reports affine discrepancy
0.00419864 against half-LSB 0.0000488759 (85.9×). Its quantization-only
corrected-Gram enclosure misses the true affine Gram. Retrospective observed
maxima are diagnostics, not bounds for future measurements.

Added tx_probe_error_bound.py: a declared modal envelope
|u(t)−u0| ≤ B exp(−a t) bounds settling power error by
2|u0|B exp(−a t)+B² exp(−2a t). The cubic power deviation is bounded by
2k U(t)^4+k² U(t)^6 with U(t)=|u0|+B exp(−a t).
Exact exponential convolution through the detector pole, initial-state interval,
readout curvature and ADC rounding produce per-probe affine-fit error intervals.
The bound has a stable coincident-pole limit. Gain and offset are fixed declared
parameters; offset belongs to the fitted polynomial. No clipped measurements,
stochastic noise or uncertain input coordinates are covered.

Six continuous nonlinear histories (three dwell times × curvature on/off),
54 probe measurements, satisfy their independently calculated bounds. Twelve
numerical-quadrature comparisons check settling integrals, including coincident
poles and long dwell. At2us the relative axis-spread bounds are14.18% with
curvature0.2 and2.17% without it; at4us,13.07% and1.15%. At1us neither case
certifies robust positive definiteness. These are conservative bounds, not
measured waveform error or physical parameter qualification.

Evidence: connected-tx-probe-error-bound.json. Both this check and the earlier
discrepancy audit are registered in run_architecture.py; no full aggregate run
is claimed. Model modal states provide the envelope and the initial detector
interval [0, fullscale] is checked for these histories. Physical envelopes and
readout transfer must be bounded independently before a managed accuracy gate
can be justified. Longer dwell alone does not remove systematic curvature.

Next system-level priority remains connecting RF enable/isolation and monitor
loading/resource use into the full chain; keep this explicit calibration error
allocation alongside clock quality, rather than substituting fit success for
whole-chip closure. No schematic or layout milestone has been claimed.
