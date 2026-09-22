# Fast connected full-chip mathematical model

Run `OPENBLAS_NUM_THREADS=1 python3 projects/programmable_transceiver_platform/system_model/architecture_fast/acceptance.py`
from the repository root for the fresh common-model acceptance suite. It runs
twelve executables, checks one shared source snapshot and
records result digests in `evidence/fast-common-acceptance.json`. The report records the current selected-suite result; `complete_architecture` remains false with remaining scope listed.

The reusable model is `chip.py:TransceiverChip`. It accepts explicit output-stage
parameters and readout settling, shares the maintenance ADC/reference, and leaves
calibration/startup sequencing to its caller. `chip_check.py` verifies exact
preparation/capture equivalence to the earlier test composition in both modes.
Traffic and lifecycle scripts below are being migrated to this common entry;
the equivalence test alone does not transfer all older results automatically.

Run from the repository root:

```sh
OPENBLAS_NUM_THREADS=1 python3 projects/programmable_transceiver_platform/system_model/architecture_fast/run.py
```

The fresh result is `../../evidence/fast-whole-chip.json` (relative to this
folder). It contains source hashes, runtime, per-case traffic/accounting,
waveform quality and recovery results. A failed case fails the executable.
This is the architecture-level iteration entry point; do not run the hours-long
physical-node PLL screens merely to check end-to-end functionality.

One `OscillatorSupplyChip` instance connects:

- framed host input, burst descriptors, finite queues and playback deadlines;
- wired serializer, channel, transition-based receive clock recovery and return data;
- DAC quantization/holds, reconstruction and receive filters, RF mixing, ADC and return data;
- separate autonomous RF and wired oscillators, plus converter/sample timing;
- ADC/DAC reference charge and recovery, host-switching supply disturbances,
  supply-dependent gain and oscillator frequency;
- RF noise, gain/phase imbalance and saturation;
- configuration, readiness, reference-loss faulting, drain and mode reopening.

Both contract modes run all four data paths simultaneously: 1.25 Gb/s wired with
40 MS/s 12-bit I/Q words, and 2.5 Gb/s wired with 20 MS/s 8-bit I/Q words. Word
width is not a claim of converter ENOB. External FPGA protocols and modem remain
outside the chip. RF loopback tests exercise TX-to-RX continuity; independent
multicarrier input tests avoid relying solely on shared-LO loopback cancellation.
Each case tests reference loss and opposite-mode reacquisition on the same chip.

The first quarter of each RF record fits one external complex gain, frozen for
the remaining validation samples. The existing 10% corrected RMS screen is
unchanged. Assumed analog values and averaged PLL feedback make this a functional
mathematical architecture, not a proof of GF180 performance. On-chip calibration
accuracy, physical fractional-divider spurs, complete device noise, package and
layout effects remain refinement obligations. `complete_architecture` remains
false until those broader requirements have supporting evidence; passing this
runner establishes only its named connected functional scenarios.

Refine blocks against this fast reference, maintaining the same external traffic
and lifecycle contract. Keep detailed circuit tests separate and compare their
results to the explicit assumptions, rather than replacing the fast runner with
an increasingly slow transistor-like simulation.

The runner additionally samples the reconstructed TX envelope multiplied by its
own LO phase, using an external ideal probe with no feedback into the receiver.
It scores this waveform separately against the matched baseline, at identical
observation times. A held-out phase-inversion negative control must fail the
quality screen. This prevents shared-LO RX loopback cancellation from being the
only TX-quality evidence. Probe samples occur at ADC observation times; they do
not establish continuous-time emission masks or DAC-image suppression.

Run `python3 projects/programmable_transceiver_platform/system_model/architecture_fast/clock_noise.py`
for the connected RF-and-wired-clock-noise sensitivity check. It adds an assumed 20 kHz RMS
frequency-noise realization to each oscillator (eight tones, 250 kHz spacing;
RF seed 839, wired seed 840), keeps both wired directions active, and compares independently
observed TX and externally driven RX against the noise-free baseline. Both modes
must retain the same observation times and pass the unchanged quality gates.
This is a specified noise sensitivity, not a validated device-noise budget.

Run `python3 projects/programmable_transceiver_platform/system_model/architecture_fast/services.py`
for the service-composition check. `ServiceChip` combines the existing automatic
I/Q trim, diagnostics, receiver detection and sampled-clock service hierarchy
with the fast supply-coupled analog model. Four cases exercise both modes with
and without an assumed independent observation bound, actual ADC/reference
loading, exclusion of configuration during calibration, acquisition after
calibration and invalidation on reference loss. A fifth check cancels an in-flight
maintenance conversion and verifies exact result accounting. The controller
receives comparator decisions and ADC observations; residual truth is used only
by test assertions. No observation bound means no accuracy-valid claim.

This composition passed in about 16 seconds. Its richer inherited clock/service
hierarchy changes the candidate: the earlier four-path quality results do not
automatically transfer. The follow-on traffic check below now provides that evidence for two cases.
Remaining diagnostic/continuous-service controls still need qualification on
this composition before adopting it as the common entry point.

The follow-on executable `service_traffic.py` runs calibration before four-path
traffic, with independent RF input, shared reference/supply loading, both noisy
oscillators and opposite-mode reference recovery. It uses `traffic.py`, a small
fork of the sustained-traffic harness that allows preparation at nonzero chip
time and a fixed 10 us startup interval. Detailed-run source files remain frozen.
Unlike the simpler averaged-clock fixture, sampled-clock disturbances may move
observation times. This test compares the original sample sequence without
resampling or time alignment and reports the maximum timestamp displacement;
timing error therefore remains in the measured waveform error. The external
complex-gain fit and 10% held-out quality threshold are unchanged.

The service-traffic check passes both modes: RX corrected RMS 4.641% / 6.624%,
independent TX 1.366% / 1.056%, with intact wired payloads and reference recovery.
See `../../evidence/fast-service-traffic.json` for runtime, source hashes and
actual sample-time displacement. In these passing cases displacement is zero;
the initial timestamp mismatch disappeared after fixing startup duration, so
it was acquisition scheduling rather than demonstrated ADC aperture jitter.
Calibration validity remains unverified.

`service_pauses.py` checks host-to-chip service gaps on the calibrated/noisy
composition. Both modes tolerate a 16-word-period pause at frame 8 while wired
TX and ADC capture continue; RF RX/TX quality remains below the unchanged 10%
screen. A 256-word-period gap instead produces a DAC-underflow quiesce event in
both modes. These are selected finite pause cases, not a general service bound;
the independent host-return direction is not paused. Results and source hashes
are in `../../evidence/fast-service-pauses.json`.

`carrier_retune.py` checks warm 2.412-to-2.437 GHz retuning in mode 0 and the
reverse in mode 1 on the service composition. Both preserve oscillator phase
and filter state, invalidate lock, reacquire, and pass subsequent independent
RF/four-path traffic and reference-loss recovery. RX error is 4.392% / 5.841%;
independent TX error is 1.390% / 1.055%. The source follows the requested carrier
with the same 250 kHz residual offset. This is averaged fractional feedback,
not an integer-divider spur test or a full tuning-range qualification. The
retune occurs while quiet after RX trim; carrier-dependent trim accuracy and TX
calibration remain open. See `../../evidence/fast-carrier-retune.json`.

`tx_services_check.py` verifies `FastTxServiceChip`, which adds the existing
timed TX probe/power-detector/correction sequence to `ServiceChip`. The adapter
is a fork of `connected/tx_calibration_chip.py` using sampled-clock lock instead
of the detailed coarse-bank clock prerequisite; frozen detailed sources are
untouched. Both 12-bit and 8-bit correction modes pass ownership, stale-commit,
reference-loss invalidation and in-flight detector cancellation checks. The
start-readiness check occurs at execution time: a serialized command may arrive
after clock acquisition, so submission before lock does not imply rejection.

This adds actual finite-bandwidth detector integration, quantized observations
and a committed DAC correction, but uses an independent detector ADC. The
shared-ADC observation path, external output nonlinearity in the fast TX probe,
and four-path traffic with the correction enabled must be connected/requalified
before claiming TX-chain closure. Results: `../../evidence/fast-tx-services.json`.

`tx_traffic.py` now runs RX trim and timed TX calibration before both-mode
four-path traffic. The independent TX probe applies the same I/Q imbalance,
LO leakage and cubic compression used by the detector, then the actual LO
rotation. Its reference uses zero output-stage distortion, with the same timed
calibration schedule. Both modes pass: RX 3.722% / 5.839%, independent TX
1.630% / 1.961%. The source/noise/reference assumptions remain explicit.
Calibration-service tests were rerun after fixing the exact zero-envelope
representation at the detector input. Results: `../../evidence/fast-tx-traffic.json`.

This establishes finite traffic after committed TX correction, not the
improvement attributable to correction alone. Shared detector-ADC loading,
nonlinear internal loopback, loaded output impedance and emission masks remain
open. Reference recovery reacquires clocks but does not restore expired TX
calibration; a new TX calibration is required before admitting more TX data.

`shared_tx_traffic.py` extends the corrected-output composition with the existing
shared I-ADC detector sampler and finite detector-readout settling. Both modes
pass RX/TX calibration followed by four-path traffic and reference recovery:
RX 3.771% / 5.985%, independently observed TX 1.667% / 2.141%.
The detector uses the actual 12-bit maintenance transfer/reference, an assumed
power-to-voltage scale, 20 ns readout settling and 30 ns shared conversion latency.
The test checks exact reference-conversion counts: two RX trim observations,
each TX calibration probe, then every RF capture sample. It does not qualify the
physical mux, observation accuracy, detector scaling or ADC aperture noise.
Evidence: `../../evidence/fast-shared-tx-traffic.json`.

`shared_tx_recovery.py` qualifies selected cancellation/restart boundaries on
`SharedOutputChip` in both modes. A nonzero pending detector conversion is
cancelled by reference loss without resetting detector/readout charge; no stale
result or extra reference sample survives. RX capture/calibration cannot steal
the ADC during TX calibration. A fresh sequence commits after reference return;
a subsequent RF retune invalidates that correction and rejects TX admission
until recalibration. These exact-boundary ownership checks do not cover every
serialized command race. Evidence: `../../evidence/fast-shared-tx-recovery.json`.

`diagnostics.py` checks internal rail/reference monitor routing through the
diagnostic tile, shared ADC and host transport on `SharedOutputChip`. Both modes
return all 64 capture words intact, and advancing the same interval in one or
137 pieces produces identical codes/update counts and matching analog state.
The monitor buffer is still idealized; this is not physical mux isolation or
peak capture qualification. See `../../evidence/fast-diagnostics.json`.

`continuous_rx.py` checks count-free reception, timed start, stop and forced
host-return overflow on `SharedOutputChip`, followed by opposite-mode restart
and a second stop/drain on each same instance. All four cases pass. The test
keeps multipole reconstruction intact and selects independent RX through the
external-source route; it does not invoke incompatible single-pole tuning.
Host and ADC traces persist across epochs, so restarted payload comparisons use
separate trace offsets to exclude data deliberately discarded by the prior
abort. This validates selected finite continuous-RX intervals, not indefinite
service bounds, graceful drain, or continuous four-path coexistence.
Evidence: `../../evidence/fast-continuous-rx.json`.

`continuous_duplex.py` checks count-free RF TX/RX after RX trim and shared-ADC
TX calibration. Both modes pass timed stop and host-starvation/underflow cases,
with exact source order at the correction input, intact RX transport, bounded
observed queues and DAC accounting. Because correction changes physical DAC
values, raw payloads are compared at the actual pre-correction apply call, not
against corrected analog held values. This is finite matched-rate RF duplex;
continuous simultaneous wired operation and waveform quality under this service
pattern remain open. Stop still discards pending data. Evidence:
`../../evidence/fast-continuous-duplex.json`.

`continuous_four_path.py` adds count-free wired transmit and a finite 4096-word
external wired source to the calibrated continuous RF duplex test. Both modes
pass timed stop and host-starvation shutdown with all four paths active. Wired
TX/RX payload prefixes match exactly, RF correction-input order and ADC host
transport match, and conversion/wired accounting checks pass. This is finite
matched-rate coexistence evidence; noise/quality sensitivity under this traffic
pattern, general service bounds and lossless stopping remain open. Evidence:
`../../evidence/fast-continuous-four-path.json`.

`continuous_quality.py` measures independent RX and TX quality during the
calibrated continuous four-path timed-stop scenario. Both modes pass with
assumed noise on both oscillators, analog imbalance/noise, shared reference
loading and supply coupling: RX 4.046% / 5.974%, TX 1.346% / 2.204%.
Observation times match exactly without realignment. RX uses an independent
multicarrier source; TX retains the amplitude-varying transport stimulus rather
than a multicarrier emission-mask fixture. This is finite quality/coexistence
evidence, not indefinite service or physical performance qualification.
Evidence: `../../evidence/fast-continuous-quality.json`.

`receiver_detect.py` requalifies supply-coupled wired receiver detection on the
shared-ADC composition during RF capture. Both modes classify the nominal load
as present and release the probe drive. Zero probe-load controls remove supply
charge; enabled loading perturbs RF samples by about 0.00445 normalized units.
Halving the probe integration step changes samples by only about 6.02e-6, and
integrated charge agrees within the existing 2% bound. Probe stimulus and driver
mapping remain assumptions; this does not qualify absent/ambiguous termination
boundaries or physical receiver-detection compliance. Evidence:
`../../evidence/fast-receiver-detect-supply.json`.

Next structural task: separate the reusable chip from test preparation. Current
`OutputChip`/`SharedOutputChip` inherit helpers that perform TX calibration when
an external source is installed, and select an ideal output fixture from a load
option. These are testbench conveniences, not intended chip behavior. Extract
an explicit common model with independent preparation and baseline parameters
before calling it the stable full-chip entry point.

Extraction evidence: `../../evidence/fast-common-chip.json`. Four cases match
calibration fits, ADC host words, independent TX probe records and reference
charge exactly. Source installation leaves time/calibration unchanged; reference
load no longer implicitly selects output distortion.

The continuous four-path transport and quality runners now instantiate
`TransceiverChip` through explicit test preparation. Ideal output parameters
are supplied by the quality baseline, independently of reference loading, and
external input uses the normal source API. Fresh runs pass all four stop/starve
cases and both noisy quality cases; their complete case records match the prior
composition exactly. Old results and changed source files are preserved under
`evidence/common-chip-migration-before`. Migration comparison:
`../../evidence/fast-common-migration.json`. Other lifecycle/resource runners
still need migration and a fresh aggregate; this is not complete closure.

Recovery, diagnostics, receiver detection and continuous RX are now migrated
to `TransceiverChip`; their twelve case records match the prior composition
exactly. Old sources/results are retained in
`evidence/common-chip-resource-migration-before`. The fresh common acceptance
includes those migrated checks plus continuous four-path transport and quality.

`local_mode.py:LocalTransceiverChip` selects the existing management-only routing
profile on the common chip. `local_mode_check.py` passes both modes using timed
management commands for RX/TX calibration, 32-word playback writes, capture arm,
local start, all capture reads, stop and drain. Slow readout survives without
streaming watchdog service, with zero high-speed data transitions/return ticks.
This covers the MCU-style management-only transaction model; it does not prove
SPI electrical edges, register RTL/CDC, or runtime switching between profiles.
Evidence: `../../evidence/fast-local-mode.json`. This new check is not yet in the
previous six-executable aggregate snapshot.

`tuning_envelope.py` exercises nine selected targets from 2.3 through 2.5 GHz,
first ascending without noise and then descending with the assumed 20 kHz RMS
oscillator-frequency noise. All 18 warm retunes preserve phase/filter state,
invalidate previous TX calibration and are locked at the end of the 20 us
observation interval. Out-of-range/nonfinite requests leave state unchanged.
This is sampled averaged-feedback acquisition evidence, not a full-grid sweep,
continuous-lock guarantee, fractional-spur qualification or waveform-quality
screen across the band. Evidence: `../../evidence/fast-tuning-envelope.json`.

`tuning_margin.py` exposes a real fast-model range limitation: a 0.5% lower
free-running VCO frequency or 5% lower tuning gain makes 2.5 GHz unreachable,
while 2.412 GHz still locks. The checker passes by confirming these failures,
not by claiming the upper-band design passes variation. Under exploratory
+/-10% free-frequency and gain variation and a +/-0.8 V fine-control target,
static coarse tuning must reach at least -90.4 MHz and +282.4 MHz relative to
the nominal 2.304 GHz free frequency, with overlapping fine ranges. These are
mathematical coverage requirements, not a fabricated bank characterization.
The common fast model needs a finite coarse-bank/acquisition refinement before
upper-band variation can be qualified. Evidence: `../../evidence/fast-tuning-margin.json`.

`coarse_clock.py` adds a startup-only sampled-clock adapter for the existing
counter-driven `CoarseAcquisition` sequencer: 16 monotonic 30 MHz bank codes,
200 ns exponential settling, finite 12-bit snapshots, prescaling, observation
windows and snapshot latency. Startup holds fine control at its declared zero
initial condition; handoff rephases the digital divider while preserving
oscillator phase. It does not implement warm analog recentering.

`coarse_clock_check.py` passes eight 2.3/2.5 GHz startup cases including the
previously unreachable perturbations and exploratory +/-10% free-frequency /
-10% tuning-gain cases. Maximum final fine-control magnitude is 0.636 V, below
the unchanged 0.8 V design target. The controller consumes counter observations,
not oscillator parameters. The bank values remain assumptions; the adapter is
not yet connected to full-chip sequencing or qualified for noise/physical bank
behavior. Evidence: `../../evidence/fast-coarse-clock.json`.

`coarse_chip.py:CoarseTransceiverChip` connects the startup-only sampled coarse
clock to the common management/event scheduler. It gates mode activation and
TX calibration on coarse qualification and PLL lock, and reserves calibration
resources while searching. `coarse_chip_check.py` passes both modes at 2.5 GHz
with the previously failing -0.5% free-frequency shift, followed by RX/TX
calibration and exact 32-word RF capture transport. The standalone eight-case
clock sweep was rerun after adding bank-settling deadline tracking. Evidence:
`../../evidence/fast-coarse-chip.json` and `../../evidence/fast-coarse-clock.json`.
Full four-path quality, startup cancellation and warm recentering on this
composition still require qualification; it is not yet the default acceptance
model. No physical bank range, settling or phase noise is established.

`coarse_cancel.py` found and fixed a reference-return bug in the fast coarse
adapter: temporarily admitting reference feedback replaced the held fine-control
voltage before coarse qualification. The adapter now preserves the held voltage
and refreshes the RF segment while the fine loop stays held. Cancellation at
settle, start-snapshot wait, measure, end-snapshot wait and commit all pass:
pending snapshots are discarded, generations advance, oscillator phase and
instantaneous bank frequency stay continuous, and restart qualifies/locks.
Both integrated mode-startup tests were rerun and pass after the fix. Evidence:
`../../evidence/fast-coarse-cancel.json` and `../../evidence/fast-coarse-chip.json`.
These exact-event tests do not qualify warm analog recentering or arbitrary CDC.

`coarse_quality.py` now qualifies continuous four-path timed-stop quality after
managed coarse acquisition at 2.5 GHz with -0.5% free-running frequency. Both
modes pass with assumed oscillator noise, analog impairments and shared loading:
RX 4.305% / 5.733%, independently observed TX 1.332% / 2.052%. Coarse selection
uses counter observations with an explicit 80 kHz frequency-noise bound. The
RF source tracks the requested carrier with a residual 250 kHz offset. This
recovers the formerly unreachable case without changing the 10% quality gate;
physical bank characterization, warm recentering and full-range quality remain
open. Evidence: `../../evidence/fast-coarse-quality.json`.

`warm_clock.py` adds timed fine-control centering before coarse acquisition.
Held control and integrator state decay with an assumed 200 ns time constant
for 12 time constants; handoff retains the residual instead of zeroing analog
state. The acquisition error bound includes worst-case residual tuning pull.
`warm_clock_check.py` passes 2.5 -> 2.3 -> 2.437 GHz acquisition/lock, exact
one-time-constant control decay, phase continuity and mid-centering cancellation
without charge erasure. The centering state must still be connected to common
chip management/readiness, then checked with four-path traffic. This is a
one-pole abstraction, not a physical shunt, switch injection or noise model.
Evidence: `../../evidence/fast-warm-clock.json`.

`warm_chip.py:WarmTransceiverChip` integrates finite centering with common-chip
coarse commands and reports the centering status explicitly. A successful coarse
start invalidates committed TX calibration even within the same epoch.
`warm_chip_check.py` passes both modes: initial 2.437 GHz acquisition, quiet
retune to 2.5 GHz, recalibration/capture/stop/drain, then retune to 2.412 GHz and
repeat on the same chip. Live retuning and stale calibration commits reject;
all four 32-word capture records transport exactly. This is lifecycle evidence,
not post-retune four-path RF quality or physical bank/centering qualification.
Evidence: `../../evidence/fast-warm-chip.json`.

`warm_quality.py` passes both-mode continuous four-path RF quality after an
initial calibrated active 2.437 GHz session, stop/drain, explicit detector rearm,
finite centering/coarse retune to 2.5 GHz and fresh RX/TX calibration. With the
-0.5% free-frequency fixture and assumed oscillator noise/shared loading, RX
error is 4.311% / 6.139% and independently observed TX 1.384% / 2.053%.
The initial test correctly rejected wired scheduling while the detector remained
aborted; the test now executes `detect_rearm` rather than bypassing that gate.
This qualifies the selected warm history, not all tuning transitions, physical
switch behavior or emission masks. Evidence: `../../evidence/fast-warm-quality.json`.

`output_loopback.py` provides an explicit adapter that inserts the same modulator
imbalance, LO leakage and cubic output compression used by the TX observer into
the internal loopback RF envelope before RX mixing/filtering. It leaves external
RX routing on the original path. `output_loopback_check.py` verifies three
constant-DAC transient durations against independent numerical quadrature and
37-piece subdivision: maximum quadrature disagreement is 2.11e-15 normalized
amplitude. This adapter is not yet installed by default or qualified through
full-chip traffic. Output loading and out-of-envelope harmonics remain absent.
Evidence: `../../evidence/fast-output-loopback.json`.

The common `TransceiverChip` now installs nonlinear output loopback by default.
`loopback_chip_check.py` confirms output distortion changes loopback ADC samples
(about 0.00110 normalized analog difference in the fixture), while external RX
samples remain exactly unchanged. The calibrated continuous four-path transport
runner was rerun: both-mode stop and starvation cases pass with the new path.
This transport regression does not replace a fresh loopback waveform-quality
screen or whole-suite snapshot. Historical aggregate results predate this
signal-path change. Evidence: `../../evidence/fast-loopback-chip.json` and
`../../evidence/fast-continuous-four-path.json`.

`loopback_quality.py` now verifies the common chip's nonlinear internal loopback
under calibrated continuous four-path traffic, assumed oscillator noise and
shared loading. Both modes pass the unchanged 10% screen: RX 3.973% / 7.653%,
independently observed TX 1.346% / 2.201%. TX observation remains separate to
avoid treating common-LO cancellation as sufficient transmit evidence. This
uses amplitude-varying transport data, not a wideband modulation/emission-mask
qualification. Evidence: `../../evidence/fast-loopback-quality.json`.

`wideband_loopback_quality.py` drives the nonlinear loopback with the existing
fixed-amplitude 50-QPSK-subcarrier fixture spanning +/-7.8125 MHz. The continuous
four-path harness now accepts an explicit waveform argument while retaining its
original default stimulus. Both modes pass unchanged quality gates with assumed
noise/loading: RX 3.662% / 5.677%, independent TX 1.437% / 1.768%. The lower
mode-1 error than the earlier transport pattern is stimulus-dependent evidence,
not a new worst-case bound. This is not Wi-Fi compliance or an emission-mask
measurement. Evidence: `../../evidence/fast-wideband-loopback-quality.json`.

`lo_drive.py` projects piecewise-constant normalized I/Q switching effectiveness
into desired conversion, conjugate image and DC coefficients. The analytic
square-wave/dropout and interval-subdivision checks in `lo_drive_check.py` pass.
Missing every eighth I cycle produces a 6.67% image-only relative RMS term;
missing every fourth produces 14.29%, already above the 10% screen under the
stated uncorrelated complex-signal assumption. Additional sidebands are reported
but excluded from that RMS estimate. This is not permission to tolerate any
particular dropout rate: actual gate-waveform-to-switching conversion, filtering,
noise and full-chip integration remain open. Evidence: `../../evidence/fast-lo-drive.json`.

`lo_mixer.py` connects projected desired/conjugate-image coefficients ahead of
the common chip's receiver filter integration. `lo_mixer_check.py` passes four
both-mode tone/capture cases for 1-in-8 and 1-in-4 missing-I-cycle fixtures:
filtered analog state agrees with the independent widely-linear projection to
1e-10, ADC words change, and all 64 words reach the host. The adapter is explicit,
not enabled by default. It includes only fundamental conversion terms; dropout
sidebands, DC feedthrough and transistor-drive mapping remain open. Evidence:
`../../evidence/fast-lo-mixer.json`.


## Current fast-baseline scope

The single acceptance command above now includes sustained simultaneous wired
TX/RX and RF TX/RX, external-input waveform quality, nonlinear wideband RF
loopback, calibration cancellation/resource ownership, diagnostics, receiver
detection, overflow/restart, transaction-level MCU-only capture, and warm coarse
retuning. The warm-retune test uses `WarmTransceiverChip`, a subclass of the common
model; this is not a claim that every configuration is tested in one scenario.
All executables must pass against the same source snapshot. Detailed pulse-loop
and transistor simulations remain separate refinements.

`lo_mixer.py` additionally accepts periodic desired/image coefficient sidebands.
`lo_drive.iq_sidebands` derives those coefficients from normalized switching
waveforms around both carrier signs. Absolute-time phase is preserved across
simulation events. `lo_sideband_check.py` checks Fourier projection against
interval-by-interval quadrature, receiver filtering against an independent
integral, event subdivision, and both-mode ADC/host propagation. The finite
sideband list is an explicit envelope truncation, not a transistor switching
model or a complete phase-noise spectrum. The default common chip remains ideal
in this particular LO-drive dimension until coefficients are explicitly supplied.

This is a working functional baseline for refinement, not completed feasibility
qualification. Unresolved items include physical parameter bounds, complete
configuration coverage, pin-level management/RTL agreement, output/package
loading and the connected transistor schematic. Passing the mathematical suite
does not open the layout gate.

The expanded snapshot passed all 12 executables (38 reported case rows) in 223.6 seconds. Source hashes and each result digest were verified. See `../../evidence/fast-common-acceptance.json`.

`../../verification/lo_truncation_screen.py` compares retained LO sidebands with
an independent exact periodic switched-mixer/first-order-filter oracle. The
oracle integrates real RF times piecewise-constant complex switching drive,
including carrier harmonics, without a Fourier or time-step approximation.
For constant complex input, one missing I cycle per 8/16 cycles and a 10 MHz
filter, the 2.4 GHz fixtures improve from 0.698%/0.705% fundamental-only error
to 0.247%/0.236% with 7/15 sidebands on each side. These are approximation
errors relative to the impaired switched mixer, not total signal-quality errors.
At 80 MHz, residuals remain 7.29%/7.02%; explicit negative controls reject treating
that carrier/filter ratio as adequately represented by this envelope truncation.
This bounds the tested fixtures only, not arbitrary modulation or gate physics.
Evidence: `../../evidence/lo-truncation-screen.json`. The existing common acceptance
source snapshot is unchanged by this standalone verification addition.

The modulated follow-up `../../verification/lo_modulated_truncation.py` uses
50 fixed QPSK tones spanning +/-7.8125 MHz at a 2.4 GHz carrier and integrates
the switched RF/filter response exactly over each drive interval. Subdividing
intervals preserves common-time output to 1.77e-12 normalized amplitude. However,
the retained envelope fails the proposed 0.3% approximation budget at quarter-cycle
observation times: errors are 0.392%/0.382% for missing-I periods 8/16. Adding
midpoint observations changes RMS to 0.300%/0.292%, demonstrating observation-phase
sensitivity to omitted carrier ripple rather than a recursion error. The report
therefore records a failed approximation screen despite passed numerical checks.
The earlier constant-input 0.3% bound is not a general wideband bound. This fixed
multitone symbol is not a changing-symbol OFDM or ADC-aperture qualification;
next refinement should include aperture/filter rejection of carrier harmonics.
Evidence: `../../evidence/lo-modulated-truncation.json`.

The common chip now selects the intended fifth-order Butterworth receiver filter
with 9.157407 MHz cutoff, matching `spec/mathematical-top-profile.json`. Earlier
fast common-chip snapshots used a single 10 MHz pole; their transport evidence
does not qualify the intended selectivity. Constructor `rx_filter=None` retains
that historical diagnostic option explicitly. The current acceptance report
provides the rerun status for the new default. Analog filter realization and
parasitic high-frequency feedthrough remain unqualified.

`../../verification/lo_multipole_truncation.py` repeats the fixed 50-tone switched
RF comparison with that fifth-order filter, independently decomposed using
SciPy analog Butterworth coefficients/residues. For the one-in-eight missing-I
fixture, seven retained sidebands on each side give 2.263e-7 relative RMS
approximation error on both observation grids; subdivision disagreement is
1.82e-12 normalized amplitude. The unchanged 0.3% approximation screen passes.
This is ideal mathematical stopband rejection; transistor parasitic feedthrough,
filter noise/nonlinearity, ADC aperture and changing-symbol modulation remain
outside this check. Evidence: `../../evidence/lo-multipole-truncation.json`.

With the intended receiver filter installed, all 12 acceptance executables / 38 case rows pass in 240.8 seconds; source and result digests verified.

`../../verification/fast_blocker_quality.py` extends calibrated continuous
four-path RF quality with two 0.1-amplitude external blockers at +20/+30 MHz
in the fixed 2.4 GHz envelope frame and RF cubic coefficient +0.05 before the
receiver filter. It retains independent multicarrier input, oscillator noise,
shared converter/reference loading, supply coupling and independent TX observation.
Both modes use the existing 10% corrected-RMS quality gate. The evidence report
`../../evidence/fast-blocker-quality.json` records the result and full source hashes.
This selected nominal-carrier test is not arbitrary blocker tolerance, overload
recovery or a Wi-Fi interference-compliance claim. It is separate from the
12-executable common acceptance snapshot, whose model sources are unchanged.

The blocker run passed both modes: RX 3.940% / 5.266%, independently observed TX 1.351% / 2.201%. Source hashes verified; no quality gate relaxed.

`../../verification/fast_profile_load_quality.py` checks another historical
profile mismatch: common fast quality fixtures used a 0.2 pF DAC reference load
and 30/20 ns ADC/DAC latencies, whereas the declared profile specifies 2 pF and
2/1.5 sample periods. The new runner reads those values from the profile and
includes its digest in provenance, with the same loaded/noisy/blocker four-path
scenario. Baseline and impaired runs both use the profile timing. This is a
selected load/timing qualification, not a claim that every setting in the older
profile is now applied by default. The common model defaults and the original
fast quality fixtures remain explicit historical comparisons. Result:
`../../evidence/fast-profile-load-quality.json`.

The declared load/timing follow-up passes both modes: RX 3.940% / 5.470%, independently observed TX 1.358% / 2.213%, against unchanged 10% limits. Full source/profile hashes verified.

`../../verification/fast_signed_coupling_quality.py` adds both signs of declared
RX/DAC gain sensitivity and wired sampling-phase sensitivity to the loaded,
blocked four-path scenario. RF/wired oscillator supply sensitivities and RF/IQ
errors are signed consistently. It retains the declared converter latencies
and 2 pF DAC reference load, and records reference droop, converter gain ranges
and actual wired clock impulses. Baselines are matched separately in each mode;
quality limits remain unchanged. Evidence:
`../../evidence/fast-signed-coupling-quality.json`. The four selected signed
points do not establish a general uncertainty envelope or physical coupling.

All four signed cases pass: worst RX 6.098%, worst independent TX 2.418%. Recorded reference droop, rail droop, DAC gain variation and wired clock impulses are nonzero in every case. Source/profile hashes verified.

## Current closure audit

Run `python3 projects/programmable_transceiver_platform/verification/fast_model_audit.py`
from the repository root to verify the common acceptance and three recent RF
stress reports against current source hashes/result digests. It also instantiates
the common chip to inspect selected composition properties. Current evidence is
fresh, but the common chip has no finite loaded TX network: its independent TX
observation and loopback still use a memoryless output-stage approximation.
Separate `connected/loaded_tx_chip.py` derivatives are not automatically evidence
for this composition. The next integration priority is a phase-aware finite
output network shared by calibration detection, loopback and independent pad
observation. Warm-clock composition, reference current limits and broader control
coverage also remain open. The audit records mathematical closure, schematic
completion and the layout gate as false; it does not infer completeness from a
passing regression. Evidence: `../../evidence/fast-model-audit.json`.

`../../verification/fast_loaded_output.py:LoadedOutputChip` starts the finite
output-network integration as an experimental common-chip subclass. It advances
a four-node switched RC network before every TX analog interval, drives it with
nonlinear output terms and the existing autonomous-LO phase segment, retains
capacitor voltage across output/dummy switching, and observes actual pad voltage
at ADC probe times. The default common model is unchanged. Calibration detection
and RX loopback still require connection to this same network.
`fast_loaded_output_check.py` compares a 30 ns modulated transient with independent
stiff real-coordinate Radau integration: maximum node error 1.69e-12, 37-piece
subdivision error 4.18e-17; switch voltage continuity and pad decay pass. This is
a direct analog adapter check, not full-chip capture/traffic qualification, and
uses an assumed passive network without driver current/supply limits.
Evidence: `../../evidence/fast-loaded-output.json`.

The experimental loaded-output adapter now advances the existing buffered shared
ADC detector from node 2 of the same finite network, at TX/DAC/LO event boundaries.
It disables the former ideal-source monitor advance to avoid duplicate or future
integration. The independent pad-transient check remains passing.
`../../verification/fast_loaded_calibration_check.py` verifies nine physical
monitor observations through the shared ADC: absolute-gain fitting rejects the
attenuated path and rejects commit; explicitly selected `tx_relative_gain=True`
reaches ready and commits. This preserves existing fit semantics rather than
normalizing away network loss. It does not prove calibration accuracy or absolute
pad amplitude. Loaded RX loopback and traffic remain the next integration work.
Evidence: `../../evidence/fast-loaded-calibration.json`.

The experimental loaded adapter now also drives receiver loopback from pad node 1
of that same network. It retains the interval-start exponential modes while the
network and detector advance, then uses those modes for receiver integration;
this prevents reading the future pad state as the start of the RX interval.
External RX routing retains its original path. The independent simultaneous
network-plus-filter Radau oracle in `fast_loaded_loopback_check.py` passes with
4.54e-14 RX error and 6.40e-17 subdivision error for differing TX/RX LO offsets.
Pad transient and shared-ADC calibration checks were rerun and pass. This closes
the adapter's three-path connection, not full-chip traffic, calibration accuracy
or nonlinear driver/current-limit qualification. Evidence:
`../../evidence/fast-loaded-loopback.json`.

`../../verification/fast_loaded_traffic.py` composes the loaded-output subclass
with the existing RX/TX calibration preparation and continuous four-path harness.
It explicitly requests relative-gain TX calibration, retains the same wired and
RF payload/accounting assertions, and checks pad observations, shared detector
ADC counts, output isolation on stop and network/detector/chip clock alignment.
This is a both-mode transport qualification; RF quality is a separate required
step. Current run status and provenance are in
`../../evidence/fast-loaded-traffic.json`.

Loaded-output four-path transport passed both modes with source hashes verified. Following the exclusive-engine design decision, this is historical optional stress evidence; RF-only/wired-only operation and transition enforcement are now the required integration direction. See `../../spec/exclusive-engine-policy.md`.
