# TX output-stage and calibration evidence

This note owns TX correction, independent waveform diagnostics, observer
limitations and fit-error requirements.
[Output isolation](tx-output-isolation.md) owns the loaded output network;
[shared-ADC integration](tx-detector-shared-adc-gap.md) owns monitor allocation.
[Current priorities](risk-priorities.md) and [closure gates](mathematical-closure.json)
own the next work and completion decisions. Historical numerical screens below
are scoped model evidence, not transistor qualification or standards compliance.

## Calibration and lifecycle contract

Nine independent DC I/Q probes identify quadratic power coefficients H and h.
Inverse-Cholesky whitening and offset −H⁻¹h require a nonsingular,
positive-orientation affine mixer, adequate conditioning, bounded coefficients
and actuator headroom. Coefficients use 12 fractional bits in the candidate;
other tested precisions are experiment settings. Compression is not inverted.
Power-only fitting leaves absolute phase ambiguous. Training may resolve a
constant complex rotation, but held-out waveform samples must not enter the fit.

Apply the matrix and offset at the paired DAC-code boundary, before transfer
and gain. Check both components' headroom before committing either code; retain
8/10/12-bit quantization and reconstruction DC-gain normalization. Installing
correction must not erase filter state. Reset holds zero DAC input: suppressing
LO leakage additionally needs physical mixer/driver isolation.

Finite detector settling and delayed, saturation-flagged ADC observations are
part of the sequence. Capture and publication are distinct events. Abort cancels
pending results by epoch while retaining analog charge. Nine probes use 18
scheduled events; a separate quiet commit must match epoch and generation.
The committed flag denotes sequencing success, not verified analog accuracy.

The [shared TX lifecycle](../system_model/connected/tx_calibration_services.py)
retains resource ownership, queued-command splitting, atomic correction commit
and cancellation. Clock readiness stays composition-specific: detailed coarse
qualification is not interchangeable with a sampled-clock assumption. RF TX
queue admission, descriptors, scheduling and pending DAC completion require
current calibration and clock readiness. Independent RX/wired configuration must
not require TX calibration. Reference loss, retargeting and relevant analog
changes invalidate calibration; active invalidation uses fault/drain semantics,
which may interrupt other streams rather than promising independent TX recovery.

## What the observers cannot certify

Power probes cannot distinguish I/Q conjugation or amplitude-dependent phase
errors. Power verification therefore reports `waveform_verified=false` even
when radial-power bounds pass. A shared-LO loopback can cancel common phase error;
an inverse RX mismatch can conceal TX distortion. Keep independent nominal-carrier
observation as the full-chain mathematical qualification instrument. External
coherent instrumentation can use the existing RF pins; no additional on-chip
reference receiver or package terminals are assumed.

Normalized waveform error can hide incorrect absolute gain and actuator overrange.
Independently bound monitor transfer and transmit amplitude/headroom, or use
relative I/Q correction with separately managed overall gain. Unknown TX gain
and unknown monitor gain cannot be independently identified by that fit. Oracle
tap-ratio normalization is a diagnostic control, not an on-chip measurement.

## Independent transmit observation and failure diagnostics

The original reconstructed-source TX observer forecasts a copy of the oscillator to the observation time and
rotates the actual reconstructed DAC envelope against an independent nominal
carrier. It never uses the receiver LO as its reference. That historical fixture
excludes mixer/driver nonlinearity, I/Q mismatch and LO leakage. The later loaded
network uses the [pad-observation contract](tx-output-isolation.md#loaded-pad-observation);
its physical LO phase is already in the pad state and must not be applied again.

The original strict incremental-quality screen fits one complex gain on the first quarter
of samples and evaluates the remaining samples without refitting. The provisional
10% limit is unchanged. A passed receive test or correct TX sample count cannot
replace this measurement. Its ideal comparison shares quantization and the
one-pole reconstruction response, so spectral quality must be checked separately.

New TX runs retain time, complex outputs, baseband and LO-rotation arrays in NPZ
files alongside their JSON report. Use `tx_trace_diagnostics.py TRACE --output
REPORT` for offline analysis. It decomposes the held-out error into a gain shift
between training and validation and residual error within validation. The latter
uses an oracle gain only for diagnosis; it cannot make a failed gate pass. The
sum of the two squared components is checked against the original error squared.
A training-only frequency fit is also diagnostic and is not applied by the gate.

`tx_phase_window_plot.py` renders the retained quarter-fraction / 250-kHz traces
with training and signal-onset boundaries. It requires NumPy and Matplotlib.
The plotted traces show repeatable phase structure as well as an initial shift;
this alone does not attribute every feature to a specific circuit mechanism.

The host-preconditioning experiment compares equal 20-us extensions: quiet wait
versus 64 valid zero-allocation host frames ending at the measurement boundary.
Unallocated payload slots contain a fixed pseudorandom pattern and are discarded
by the actual receiver. They exercise modeled pad switching without delivering
RF/wired data. All 64 sequence numbers wrap back to zero before the real burst.
Assertions check active state, frame alignment, and unchanged sample consumption.
The observer excludes prelude samples, but no analog or oscillator state is reset.
Only the input host bus is preconditioned; this is not a claim that all supplies,
DAC activity or return-bus activity are already at steady state.

Preconditioning remains a diagnostic fixture, not a required operational sequence
or an adopted workaround. Full qualification retains startup cases unless an
explicit implementation contract and its costs are justified and tested.

## Fit-error and settling bounds

For p=Dq+e with |e|≤ε, use |q̂−q|≤|pinv(D)|ε. Propagate Hessian uncertainty to
corrected-Gram eigenvalue intervals using the actual quantized actuator matrix.
Report robust positive definiteness, relative axis spread and residual offset
in monitor-scaled units. Matrix invertibility or an empirical ADC-code threshold
alone does not certify calibration accuracy, phase fidelity or absolute RF gain.

For a declared modal envelope |u(t)−u₀|≤B exp(−at), settling power error is bounded
by 2|u₀|B exp(−at)+B² exp(−2at). Cubic power deviation is bounded by
2kU(t)⁴+k²U(t)⁶, with U(t)=|u₀|+B exp(−at). Convolve through the detector pole,
including a stable coincident-pole limit, initial-state interval, readout curvature
and ADC rounding. Allocate model discrepancy as well as quantization error.
Retrospective maxima are diagnostics, not future uncertainty bounds.

These bounds assume an affine/square-law observation plus declared error terms.
Clipping, stochastic noise and uncertain input coordinates are not covered by the
historical analytic probe bound. Physical settling envelopes and readout transfer
must be established before using it as a managed accuracy gate. Longer dwell
cannot eliminate systematic curvature.

## Retained numerical evidence

| Scoped experiment | Result and limit |
| --- | --- |
| Reconstructed managed-host duplex | TX errors 8.286% / 9.631%; finite out/in ±10 MHz powers −43.148 / −38.956 dB. Four-pole elliptic core plus 80 MHz buffer pole, highest pole-pair Q≈5.78; not a protocol mask or realizability result. |
| Assumed output-stage sensitivity | Mode1 exceeds the unchanged 10% screen with 0.25 dB imbalance, 2° quadrature error or −30 dBc LO feedthrough; combined trial gives 10.891%. These are assumptions, not process tolerances. |
| Power-fit finite error sweep | Mode1 combined trial improves to 9.637–9.645% with quantization alone; tested 2% monitor error reaches 9.855%, 5% reaches 10.101%, 10% reaches 10.720%. Finite seeds are not adversarial bounds. |
| Local paired DAC correction | 12-bit/40 MS/s error 7.593%→0.0816%; 8-bit/20 MS/s 7.649%→1.311%. Matched ideal reconstruction comparison excludes full-chip noise/jitter. |
| Finite detector dwell | Assumed 200 ns detector pole, 10-bit ADC: 100 ns dwell gives 23.409%, 500 ns 2.679%, 2/5 µs 0.0634%. Nine 2 µs probes plus latency take 18.9 µs; not a general settling guarantee. |
| Observer counterexamples | Independent TX errors 8.286%/9.631% appear as 0.793%/0.531% through ideal shared-LO reception. Adding 0.3 rad common phase error raises independent errors to 26.250%/22.213% while shared-LO results stay unchanged. |
| Monitor/headroom | Ignoring tap transfer 0.56048 gives gain 1.33573 and rejects 0.8+j0.8 despite normalized quality passing. See [headroom report](../evidence/connected-tx-monitor-headroom.json). |
| Relative-gain / finite precision | One managed mode1 case gives 8.5836% TX error; this is not absolute-power regulation. A 10-bit monitor with gain 0.003 yields only two peak probe codes and 14.640% local error despite invertible fit. |
| Affine uncertainty | 512 sign corners per case check enclosures. At gain 0.56, quantization-only axis-spread bounds are 0.6376%/0.1629% at 10/12 bits. Nonlinear discrepancy 0.00419864 is 85.9× half-LSB, invalidating the quantization-only enclosure. |
| Nonlinear probe bound | Six histories/54 probes satisfy declared bounds; 12 quadrature comparisons include coincident poles. At 2 µs, axis-spread bounds are 14.18% with curvature 0.2 and 2.17% without; at 4 µs, 13.07%/1.15%. Neither 1 µs case certifies robust positive definiteness. See [probe-bound report](../evidence/connected-tx-probe-error-bound.json). |

The [complete immutable history](https://github.com/deepai-org/svalbard/blob/3d06e6263892b2e6755c9f6a6e6d5bf7da4dc678/projects/programmable_transceiver_platform/spec/tx-output-stage-sensitivity.md) preserves every original command/source
reference, measurement, limitation and intermediate policy, including policies
later replaced by TX-specific admission. It is historical evidence, not a current
backlog. Full waveform quality, loaded resource integration, noise, mismatch,
package effects and physical implementation remain separate qualification work.
