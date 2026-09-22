## Mode 1 signed calibration now commits; full traffic rerunning

The corrected noisy 2437 MHz preparation completed nine real shared-ADC probes
and serialized commit (session 95086, exit 0, source hashes unchanged). First
input power 9.34237e-7 produced signed decoded power -0.0001220703125 without
clipping, directly confirming the previous saturation misclassification. Full
mode 1 matched-pad TX/RX traffic is rerunning as session 66917. Do not promote
quality before its held-out result. The finite-readout candidate remains separate:
its local sweep shows that readiness can coexist with 17–30% static error when
readout settling is slow. Dwell/bandwidth qualification remains an integration task.

## Signed shared-ADC observations: corrected locally, integration rerun pending

Mode 1 preparation diagnosis terminated after one sample with detector-saturation
cancellation, zero accepted probe powers and no ADC clipping. The shared readout
incorrectly equated negative signed codes with saturation. The corrected path
retains signed measurements and explicitly enables signed quadratic fitting for
that detector only. Physical input overrange, ADC clipping, positive curvature,
conditioning and correction-range checks remain. Local signed-readout, fitting,
commit/overflow and existing sequence/cancellation screens pass. Preparation with
the original noisy 2437 MHz harness is rerunning (session 95086), recording input
power and signed decoded power per probe. Full mode 1 traffic remains unqualified.

## Shared-ADC mode 1 currently fails calibration preparation

The actual 2437 MHz mode 1 quality run cancels TX calibration before payload
traffic. The ideal branch finished; actual TX/RX quality is unmeasured. Source
hashes match the launch snapshot. Diagnose this integration failure before
promoting either supported-mode coverage or adding readout settling to the
integrated candidate. Possible causes must be distinguished using cancellation
reason, ADC clipping, probe powers and clock/ownership state, not by weakening
the quality gate. A preparation-only reproduction is running as session 14140.

The separate buffered detector settling model agrees with an independent ODE
at three assumed time constants. Reverse mux loading, kickback and physical
parameter qualification remain open. It does not close shared-converter quality.

## Actual loaded-pad mode0 quality now passes

Managed phase-aware network pad observation gives7.44% TX and5.99% RX error
against the unchanged10% gate, with frozen sources verified. Next qualify mode1
and shared-ADC/phase-aware composition; do not transfer this extra-ADC result to
the shared-resource architecture. Mux settling, active-driver/DC feedback and
retuned/recovered waveform quality remain key mathematical gaps. Runtime
optimizations are being equivalence-tested without simplifying the model.

## Phase-loaded managed calibration passes; independent pad quality is next

Managed calibration, three updates and reference-loss shutdown pass with the
actual LO driving the switched electrical network. Independent pad capture is
implemented and fixture-tested. Next run the real traffic/quality harness with
matched reference loading, then retuning/recovery. Detector ownership, driver DC
feedback and physical parameters remain open; no architecture closure is claimed.

## Loaded calibration now works locally; managed integration remains

Actual reconstruction and nonlinear modulator terms now drive the switched
network, timed power detector, relative calibration and corrected pad playback.
Local multitone error falls2.80%→0.50%/0.11% with10/12bit detector readings.
This uses one monitor/pad network state but an ideal carrier and prescribed
source. Next integrate exact update/switch boundaries with managed lifecycle,
resource ownership and noisy full-chain quality; physical parameters remain open.

## Switching the calibration load disturbs the driver envelope

A charge-retaining four-node RC model now includes both switches' off conductance
and capacitive feedthrough. In six declared cases,100ps break-before-make raises
internal amplitude from about0.518 to0.98; overlap avoids that rise but increases
loading. Connect this network to the detector and live output before promoting
isolation quality. Device charge injection, nonlinearities and package coupling
remain outside this exploratory model.

## Load-preserving calibration candidate needs switching dynamics

A nominal55ohm internal dummy keeps upstream calibration amplitude within0.011%
in the passive network and gives about61.5dB isolation with1fF feedthrough.
With10fF, isolation is only41.5dB; the declared load/resistor mismatch sweep
reaches15.4% amplitude error. Next model dummy-switch off capacitance, retained
charge and transition sequencing before live integration. No physical feasibility
or universal-load calibration claim follows from nominal matching.

## Isolation/loading assumptions now have a concrete failure boundary

A passive RF network with1fF across the isolation element misses the assumed60dB
attenuation at2.4GHz (about56dB). Upstream monitor power changes3.58× between
muted and connected-load states; a pad-side monitor loses its calibration signal.
This is an exploratory topology result, not a GF180 impossibility claim. Resolve
load-preserving calibration and parasitic feedthrough before promoting the prior
multiplicative isolation stage. Connect the chosen network to live detector/output
dynamics; account for power and observation resources explicitly.

## Isolation now passes finite loaded waveform checks; loading is next

The managed isolation candidate passes both-mode independent TX/RX quality
(TX7.34%/8.59%) and both opposite-mode recovery directions. These remain finite
assumed-parameter results. Its transfer has no loading/current feedback and its
upstream detector cannot characterize the pad path. Connect monitor/isolation
loading and resource allocation next; clock margin and uncertainty bounds remain
open. First100ns onset is characterized separately from the held-out quality gate.

## Output isolation is now an explicit model requirement

Actual managed RF observation exposes quiet calibration and residual LO after
stop. An experimental finite isolation stage passes connected calibration and
three shutdown causes, with assumed60dB off attenuation and20ns dynamics. It is
not a physical qualification or a promoted full-chain candidate. Its pre-isolation
detector cannot characterize the final pad path. Next resolve monitor/isolation
location and loading, then test startup/recovery and full-chain waveform quality.
The calibration uncertainty and autonomous-clock margin requirements below remain.

## Nonlinear calibration uncertainty is now explicit

The quantization-only affine bound is contradicted by the nonlinear detector
model. Analytic envelope bounds cover54 continuous probe measurements, but with
readout curvature0.2 the4us relative axis-spread bound remains13.07%; removing
curvature reduces it to1.15%. This is a conservative model certificate, not
measured RF error. Longer dwell alone is insufficient. Bound/characterize the
readout transfer before promoting managed commit to an accuracy certificate.
RF enable/isolation, connected monitor loading/resource allocation and clock
margin remain whole-chip closure priorities; no layout begins before schematic
closure. See the latest analytic-probe entry in closure-audit-pass876.md.

## Calibration measurement adequacy

Relative correction passes the live mode1 readout-error case at8.58% TX error,
but weak quantized probes can yield an invertible fit with14.6% local error.
Derive bounded fit uncertainty before treating coefficient commit as accurate;
monitor loading, RF isolation and full operating-envelope coverage remain open.

## Monitor gain and DAC headroom

A connected local loading/calibration experiment shows that ignoring monitor
attenuation overdrives output gain by33.6% and loses DAC headroom while normalized
quality still passes. Separate relative I/Q correction from absolute gain control,
or independently bound the monitor transfer. This now joins clock margin and RF
isolation as an unresolved full-chain requirement.

## Intermediate filter evidence

Fraction0.30 at300 kHz passes201/201 nominal tuning points and two managed TX/RX
quality cases. It is now an explicit experimental profile, not a default. Noise
seed/startup robustness, unified recovery, monitor loading and RF output isolation
remain required before promotion.

## Current matched-preparation RF evidence

Both managed modes pass the same readiness-poll profile, but mode1 TX error is
9.56% against10%; clock/startup trajectory sensitivity remains the leading margin
risk. Detector transfer checks now reject low-rail clipping, but readout uncertainty
and monitor loading are not integrated in these full-chip runs. RF isolation and
complete operating-envelope/recovery coverage remain open.

## Full-chain TX qualification priority

Frozen-trace controls prove shared-LO cancellation and TX/RX mismatch ambiguity.
Keep the independent nominal-carrier observer as qualification instrumentation.
Next integrate corrected DAC samples and the output-stage model into the live
full-chip quality run; internal calibration success alone cannot close RF quality.

## Calibration observability risk

Independent radial-power verification now has passing and failing controls, but
explicit phase-distortion/conjugation counterexamples pass power checks. A
coherent or external independent waveform observation is required for full TX
quality; shared-LO loopback must not hide oscillator error. Budget detector
precision and loading alongside this observation path.

## RF-specific admission update

TX calibration no longer blocks mode setup or RX capture. Both-mode admission
checks pass; residual verification, monitor ownership and already-scheduled TX
behavior on validity loss are the next integration risks.

## TX clock readiness and mode-width evidence

Managed calibration now requires coarse qualification plus PLL lock; activation
tests pass with 12-bit and 8-bit correction. Next replace the experimental
whole-mode calibration gate with per-resource RF TX admission, preserving wired
and receive-only operation. Audit direct mutation paths and add residual
verification before treating a committed fit as accurate.

## Managed TX calibration integration gaps

The experimental managed candidate passes command ownership and reference-loss
cancellation. Before promoting it, resolve autonomous LO readiness in quiet
maintenance, monitor ADC ownership/loading, RF isolation, activation validity
gating and mode-dependent DAC width. These are exposed integration obligations,
not qualifications established by the command test.

## DAC correction integration update

Quantized paired DAC correction now passes local queue/filter/output checks at
8 and 12 bits. Full-chip clock margin remains unclosed. Prioritize finite-time
power observation and managed calibration ownership, plus explicit RF disable
for LO leakage on reset/idle. See [evidence](tx-output-stage-sensitivity.md).

## Latest calibration evidence

Power-only TX I/Q correction recovers the tested mode-1 margin with up to 2%
assumed monitor error, but cases fail at 5%. DAC-code actuation, detector fidelity
and managed calibration timing are now the immediate integration risks. Clock
error still consumes most of the waveform budget. See
[calibration evidence](tx-output-stage-sensitivity.md).

# Latest TX risk update

Mode 1 reconstructed TX has only 0.369 percentage points below the provisional
10% error threshold. Frozen output-stage trials fail with 0.25 dB I/Q imbalance
or 2 degree phase error. Prioritize residual calibration error and autonomous
clock margin alongside physical reconstruction-filter feasibility. See
[the measured sensitivity report](tx-output-stage-sensitivity.md).

# Risk-driven implementation priorities

## New highest-priority finding — independent TX quality fails

Independent nominal-carrier observation of the current composed candidate gives
10.37% / 12.59% incremental TX waveform error, exceeding the unchanged provisional
10% screen in both modes. Receive-quality and transport passes do not supersede
this evidence. Recorded-state substitution gives phase-only error 10.36% / 12.60% versus baseband-only 0.73% / 0.49% after gain correction. Mode-1 isolation gives 4.09% without RF noise, 8.71% without RF supply pulling and 1.69% with both removed (same bank). The actual equal-capacitor filter has an averaged 12.95-degree phase margin and 4.53 peak sensitivity. At 300 kHz, a 0.25 fast-capacitor fraction qualifies only 187/201 carriers and loses lock during full traffic. A 0.35 fraction qualifies all 201 carriers, but TX errors remain 8.95% / 11.38%. Lowering the quarter-fraction loop to 250 kHz retains traffic lock but yields 9.32% / 11.32%. No trial is adopted. Saved complex traces show a large training-to-validation phase/gain shift; investigate startup/load transients and estimator-window sensitivity while retaining the held-out quality gate. Defaults and full forcing assumptions remain unchanged. Do not loosen the threshold to promote the candidate.

A matched 20-us prelude on the 0.35/300-kHz candidate gives 11.60% TX error after quiet waiting versus 9.34% after valid zero-allocation host frames, at identical measurement time with unchanged forcing. This identifies startup-load sensitivity. Next evaluate an explicit host-link activation contract or circuit supply isolation across modes/recovery/noise phases; do not silently replace cold-start qualification with this one passing fixture.

An experimental HostActivationChip now enforces that startup rather than assuming it: counted valid empty frames, activity bounds, untrained-stream rejection, timeout and reference-loss invalidation all pass. Its TX results are 8.09% / 9.34%; three additional mode-1 startup phases give 4.08–4.88%. The timing checks still use ideal timestamps, so physical clock-monitor implementation and idle/pause/activity robustness remain open. Combined RX/TX qualification now passes both finite cases; broader lifecycle and monitor validation are still required before promotion; SPI-only operation remains part of the final scope.

Finite-burst Hann spectra give outside/inside ±10 MHz power ratios of -25.11 dB
and -13.26 dB. Ideal-path ratios are nearly identical (-25.15 / -13.27 dB), so
reconstruction/images and finite-window/source effects require attention even
if incremental error is repaired. These are integrated observations to host-rate
Nyquist, not a protocol mask or measured silicon spectrum. Mixer/driver output
nonlinearity, IQ mismatch and LO leakage also remain unmodeled.

Evidence: connected-tx-wideband-initial-failure.json and the matching failure log;
original observer and screen sources are archived. Observer analytical phase,
nonmutation, decay and known-tone spectral controls pass.


## Current decision point — 300 kHz loop and coarse tuning

The 300 kHz candidate passes all 201 nominal RF carrier targets and the calibrated
combined wideband cases at 6.50% / 6.75% error. It is now the default; prior 350 kHz
failures remain archived. All six unified continuous/recovery lifecycle cases also pass. Acquisition
coverage is broader than quality coverage, which still uses two carriers.

The next clock risk is free-frequency uncertainty outside the fine tuning span.
A staged 16-code coarse bank with counted /16 edges recovers nine tested cases,
including the formerly unreachable -8% examples. Settling-bounded search, timed management ownership and finite counter/CDC
observation semantics are now integrated in the experimental startup profile.
Combined coarse-profile RF quality now passes at 6.76% / 9.85%; the latter has only 0.15 percentage points of margin to the provisional 10% bound. Standalone passive recentering passes independent KCL/energy checks and two counted coarse/fine retunes. Its timed guard, cancellation and retry now pass in full-chip management with post-retune RF/wired transport. Warm-retune receive quality now passes at 6.09% / 7.15% after recalibration, at different waveform/noise phases. Preserve the near-limit startup case; its sensitivity and independent TX RF quality remain priorities before promotion. Do not infer GF180 yield or physical bank range
from these assumed models. RF level/blocker/noise envelopes and unresolved
trigger/graceful-stop contracts remain mathematical closure obligations.

The combined waveform-quality measurement is currently RX-focused. The sustained
harness proves TX sample consumption and no underflow, but does not measure RF
output error or unwanted spectrum. Independent TX envelope/spectral observation
on the same composed clock/DAC model is a separate high-priority closure task;
four-path traffic alone cannot qualify the transmit chain.

## Previous decision point — full RF tuning grid

The nominal 201-target grid exposes six acquisition/lock-continuity holes at
350 kHz loop bandwidth: 2313, 2329, 2353, 2369, 2393 and 2409 MHz. Prior two-channel
wideband success does not qualify the advertised MHz grid. Prioritize a filter/
divider solution and rerun independent waveform quality without relaxing lock
limits. A 325/300 kHz comparison is running on failures and controls.

Separately, 12 of 54 startup sensitivity cases are outside the assumed VCO
frequency span. An explicit coarse bank/search may be needed for that modeled
uncertainty; silently changing free frequency is not autonomous calibration.
These assumptions are not measured process corners. See fractional-tuning-envelope.md.

## Previous decision point — calibrated fractional candidate

The pass876 aggregate passed all 107 scenarios with 702 unchanged source hashes
and every report/log hash verified. A subsequently integrated candidate combines
pulse clocks, second-order fractional RF feedback and shared I/Q offset calibration.
The staged combined wideband test passes at 8.41% / 8.58% waveform error; the
six promoted focused screens have passed with verified source/report/log hashes. No full-chip closure is claimed.

The most important mathematical gaps now are the single candidate's complete
lifecycle/continuous-traffic coverage and a justified useful-signal/uncertainty
envelope. Calibration no longer lacks an actuator or command path, but its
independent observer bound is unknown. Completion without that bound reports
unverified accuracy. Avoid designing a precision observer around an arbitrary
one-trim-step requirement before allocating the RF error budget.

114 scenarios are now registered. Next: prioritize
longer service/clock envelopes and failure boundaries. Both-mode continuous
duplex and noisy reference-loss/opposite-mode retuning now pass on the unified
candidate, retaining trim codes and explicitly invalidating accuracy after reset. Define trigger and graceful-stop
contracts from actual interfaces; do not add undeclared pins. Broader clock
ratio/noise/supply and RF blocker/level envelopes remain necessary.

Physical clock noise, complete RF/converter performance and die/package/area
coexistence remain the highest silicon risks. These mathematical results do not
qualify them. Follow the agreed sequence: close the intended mathematical chip,
then transistor schematics and simulation, then layout and extraction.

## Historical decision point — pass 869

Both pulse loops now run in a common-chip candidate and finite wideband cases
pass. Actual fractional feedback is the clearest new failure: first-order divider
modulation achieves average frequency but fails lock qualification and creates
up to32ps RMS deterministic timing variation in the examined channels. Prioritize
noise shaping/filter interaction and independent RF quality before claiming
fine carrier tuning. Do not fix this by replacing integer divider events with
an average ratio or merely relaxing lock thresholds.

Continuous RX/TX and atomic starts now exist; triggers, calibration and lossless
stop remain functional gaps. Physical clock noise, RF/converter performance and
die/package coexistence remain unqualified, and transistor/layout work must
follow full mathematical functional closure.

## Historical decision point — pass 855

The autonomous profile now connects independent wideband reception, wired traffic,
shared converter references, detector supply feedback and host pauses. A common
ProgrammableChip entry now also contains the managed diagnostic tile; regressions
are verifying this integration. Do not confuse the experiment startup harness
with the actual chip controller or treat old PlatformChip evidence as current.

Highest remaining functional risks:

1. Continuous run/stop and trigger ownership still need real control semantics,
   bounded queues and fault/rearm behavior in the common entry.
2. Diagnostics need actual internal monitor sources and conversion scheduling;
   current tile inputs remain held fixtures. Calibration must act through the
   same timed resource interface rather than direct testbench mutation.
3. Clock abstraction remains a major gap: integrated sampled loops omit actual
   pulse and fractional-divider behavior demonstrated only in separate models.
4. Define operating envelopes and rejection/fault behavior for the common model.
   Passing finite nominal cases is not mathematical closure or physical margin.

Physical risk ranking is unchanged: autonomous clock quality, complete RF-chain
quality, converter/reference loading and package/die coexistence. The common
functional model is preparation for transistor work, not evidence that these
risks have been resolved.

## Historical decision point — pass 847

Stop treating additional isolated passing cases as architecture completion. The
largest remaining mathematical risk is integration divergence: the declared top
profile still instantiates an older chip, while autonomous clocks, managed tuning,
receiver detection and supply feedback live in newer variants. Consolidate one
explicit full-chip candidate and its supported concurrent modes. Preserve the
80-scenario pass842 baseline as historical evidence, not proof of new variants.

Priorities in order:

1. Connect the public detector/clock/control variant to the combined independent
   wideband quality profile, including converter reference loads and host pauses.
   Do not reuse common-LO loopback quality as independent radio evidence.
2. Complete actual control functions: continuous run/stop, trigger ownership,
   diagnostic converter allocation and trim/calibration mapping. Resource discovery
   currently exposes existing engine state; it is not the full analog resource graph.
3. Integrate a chosen clock abstraction consistently. Physical pulse-loop startup,
   fractional edge timing and RF phase noise remain high-risk refinements. Define
   the mathematical clock-service contract before further isolated loop tuning.
4. Bound declared operating/uncertainty envelopes and failure behavior. Receiver
   detection has a known small-coupling false-negative and unqualified arbitrary
   precharge. The local release monitor replaces an unobservable remote-state check,
   but finite passing cases are not continuous-envelope proof.

Circuit feasibility risks remain autonomous jitter/phase noise, useful complete RF
conversion quality, shared reference regulation and die/package coexistence. They
require transistor/extracted validation after functional mathematical closure;
missing functions cannot be deferred as merely uncertain device parameters.

## Historical decision point — pass 836

The simplified full-chip architecture is still incomplete. Prioritize connecting
missing carrier/tuning controls, calibration/resource ownership, continuous-run
and trigger behavior, and independent wideband RF quality in one current profile.
Use declared mathematical assumptions where transistor parameters are unknown;
do not defer missing functions to the schematic stage.

Compliance-limited standalone pump simulations qualify40/44 startup cases under
an assumed current law; four still miss the deadline. Physical timing quality,
pump nonidealities and full-chip integration remain high risks. Programmable
relative converter timing is now connected and tested, including atomic invalid
start rejection. This closes one control gap, not the whole management lifecycle.

## Historical decision point — pass 834

Actual reference/feedback-edge pump timing is now simulated. A slower loop acquires
selected cases within its ideal-current compliance range, but larger startup phase
still reaches that boundary at2.5GHz. The next priority is a bounded pump-current
law near compliance, followed by mismatch/reset delay and noise. Do not classify
boundary termination as physical acquisition failure: the current model explicitly
stops predicting there. Full-chip integration must preserve the longer acquisition
latency, and independent wideband quality remains unverified for this pulse loop.

## Historical decision point — pass 833

Explicit pump-filter pulses reveal compliance and ripple risks hidden by ideal PI.
Increasing shunt capacitance reduces peaks but adds a pole near loop bandwidth;
held-current and impulsive-detector stability predictions disagree in one tested
case. Highest next priority is actual reference/feedback-edge PFD pulse feedback
around the passive filter, followed by compliance-limited behavior. This is a
circuit/modeling problem, not evidence that the chip is impossible. Do not carry
forward the sampled ideal-PI stability result as physical loop qualification.
Shared-reference noise and independent wideband quality remain open afterward.

## Historical decision point — pass 832

Finite comparison cadence is now explicit. The candidate1MHz natural frequency
passes the sampled10MHz/40MHz models; a3MHz wired setting is unstable and rejected.
The next clock risk is the gap between held detector error and actual charge-pump
pulses: ripple, compliance and additional filter poles can change that conclusion.
Shared-reference noise and independent wideband quality also remain open. Keep
these limits distinct from the successful transport and local stability tests;
physical divider/VCO calibration remains later schematic work.

## Historical decision point — pass 831

Exact divider sequences expose pre-loop fractional count modulation. The new
integer-reference candidate avoids it using40MHz/4 for wired comparison and
125/250 feedback counts, with unchanged line rates and lock tolerances. Noisy
four-path traffic and aligned reference/reset tests pass. Next assess the lower
comparison rate's sampled detector/filter behavior and shared reference noise,
and evaluate independent wideband RF quality in the combined candidate. High-speed
divider circuitry, measured noise, carrier controls, receiver detect and converter
overload recovery remain unresolved at their respective abstraction levels.

## Historical decision point — pass 830

Finite spectral VCO noise now enters both autonomous loops before feedback
suppression and coexists with supply pulling. Reproducibility, RMS, analytic transfer,
independent RF response and noisy transport tests pass under declared assumptions.
Next address the average-only fractional divider and shared reference/phase-detector
noise, then evaluate the combined independent wideband RF quality envelope. Do not
substitute loopback cancellation or passing transport for that measurement. Actual
GF180 noise calibration remains a later physical task; missing functional controls,
receiver detect and converter overload recovery still block mathematical closure.

## Historical decision point — pass 829

Continuous host-switching supply history now drives both autonomous oscillators.
Analytic phase integrals, signed four-path traffic, independent RF response and
excessive-coupling lock failures pass. This closes the missing connection under an
assumed lumped rail, not the physical coexistence risk. Next add explicit oscillator
noise/divider behavior and measure independent wideband RF quality in the combined
candidate; do not infer it from common-LO loopback or unchanged coarse ADC codes.
Internal switching-current sources and separate domain/package impedances remain
missing. Carrier controls, receiver detect, calibration and converter overload
recovery are additional functional gaps before schematic closure.

## Historical decision point — pass 828

One autonomous RF synthesizer now drives both mixers in the complete managed
controller, independently of the wired PLL. Independent RF input and simultaneous
converter/wired traffic pass, and phase interpolation converges against an analytic
loop/filter calculation. Shared-LO loopback cancels common phase error, so retain
independent-source measurements for the risk assessment. Next connect actual
shared-supply dynamics to oscillator frequency and add explicit noise/divider
models, then quantify wideband RF quality under those assumptions. Carrier/band
programming, receiver detect, calibration and converter overload recovery remain
functional gaps. These assumed clock parameters do not establish GF180 timing.

## Historical decision point — pass 827

Autonomous wired TX now owns connected word and bit timing; both-mode four-path
traffic, signed reference offsets, acquisition rejection, phase/lock faults and
mode/reset continuity pass. Next connect independent autonomous RF LO state to
mixer phase and supply response, then measure signal quality under those clocks.
Preserve the declared combined profile as historical until this controller is
integrated and rerun. Fractional-divider modulation, stochastic phase noise and
physical VCO gain/range are still unresolved. Receiver detect, calibration,
converter overload recovery and remaining control paths also prevent closure.

## Historical decision point — pass 826

The verified62-scenario baseline passes with unchanged sources. Independent RF
input, wired swing/equalization, persistent analog state and timed local management
now have connected evidence. Autonomous clock ownership remains the highest
functional risk: a new bounded PFD/PI/VCO model and oscillator-driven serializer
adapter pass targeted tests, but full-chip scheduling and RF mixing are not yet
connected to them. Close that integration before treating assumed jitter/phase
budgets as autonomous timing evidence. Then evaluate independent-RF quality under
combined impairments, converter overload recovery and remaining programmable
control paths. Actual oscillator gain/range/noise, RF performance and package
coupling remain physical unknowns; no open-PDK evidence here closes those risks.

## Historical decision point — pass 815

Pass815 establishes a declared combined candidate profile with live wired CDR,
wideband RF, converter delays and shared references active together. Four signed
both-mode cases pass exact transport and the provisional RF screen at5.8–7.5%.
This reduces integration uncertainty for the selected assumptions. Highest remaining
functional risks are independent RF-source reception, autonomous RF/wired-TX clock
ownership, wired TX swing/EQ/receiver detect and timed hardware management mapping.
A new full regression is needed after the recent wired changes. Physical calibration
remains deferred until mathematical functional closure.

Pass811 preserves the live analog channel and external launches through digital
reset, with both-rate retraining and stale-word exclusion tests. Electrical
idle/detection and supply-to-CDR coupling are the next wired integration gaps.

Pass810 adds an opt-in live channel/CDR path with sustained four-path tests and
small/large interventions. Remaining priority is wired analog persistence across
reset, electrical idle/detection and supply-to-clock coupling; the large-step
case currently corrupts data without protocol-level slip reporting.

Pass809 reruns all46 registered scenarios successfully with unchanged source
hashes and verifies every evidence/log hash. ADC/DAC finite latency and shared
reference loading are integrated. Remaining highest functional risk is live wired
recovery under disturbances: the current RX adapter precomputes recovery from a
fixed waveform. Implement causal wired timing/idle/reset contracts next, alongside
remaining control visibility and converter diagnostics. This fresh suite proves
regression coverage, not mathematical completeness or physical feasibility.

Pass805 includes ADC quantization against an unquantized matched analog reference.
Signed mode1 combined errors are4.8–5.0% without RF phase disturbance,7.1–7.8%
with the tested phase sequence halved, and11.2–11.9% at original amplitude. ADC-only
error is3.04%. This identifies a conditional passing phase assumption without
changing bandwidth, blockers or the10% screen; it is not a physical PLL result.
Next establish independent-source reception and broader uncertainty, and return
to missing wired/control/converter functions rather than indefinitely tuning one
RF fixture. Historical failed conditions below remain valid evidence.

Mathematical closure still precedes schematic and layout. Combined RF/transport
simulation now exists, including blockers, LO phase events, finite-reference and
supply sensitivity. Correct code transport is insufficient: the new matched-path
quality screen measures25–27% corrected incremental waveform error under the
combined assumptions. Removing blockers reduces this to9.8–11.7%; removing phase
variation alone leaves23.6–24.5%. The provisional budget is10%, not a Wi-Fi limit.

Pass802 confirms18–20% error even with clearly out-of-band20/30MHz tones.
The10MHz blocker is at the nominal20MHz channel edge and cannot simply be
filtered away while claiming unchanged wanted bandwidth. A proposed8MHz/1dB
passband and20MHz/30dB stopband needs at least a fifth-order Butterworth filter;
pass803 implements it in the connected mathematical model. Error improves to
9.96%/11.51% in modes0/1 under positive-sign20/30MHz blockers. The first has
negligible margin and the second still fails. This is not a physical result.

Pass804 adds custom50-carrier QPSK spanning+/-7.8125MHz: corrected waveform
error is9.15%/12.26% in modes0/1 with the multipole filter. Thus mode1 remains
outside the provisional screen with wideband modulation too. Next resolve the
admissible phase/noise envelope and test independent-source reception, keeping
the current failing assumptions recorded.

Next RF priority is selectivity and a declared blocker/phase-noise envelope, with
held-out signal-quality evidence rather than ADC hash changes alone. Do not relax
the screen or redefine the waveform to conceal the failing assumptions. Filter
changes must preserve intended signal bandwidth and compare against a matched
ideal reference. The single-tone fixture must ultimately be extended to modulated
signals and independent RF sources. Resource/control/converter and wired timing
contracts remain parallel architectural gaps. Physical parameter calibration is
still deferred until the full mathematical architecture is complete.

## Historical decision point — pass 787

Follow the user's stage order: finish the full mathematical model, then the
whole transistor schematic, then begin layout. The explicit completion inventory
is [mathematical-closure.json](mathematical-closure.json), derived from the intended
block diagram, pin/rate contract and clock ownership. Assumed analog parameters
are acceptable for mathematical closure; absent intended functions are not.

Highest current integration risks:
1. Sustained rate ownership: independent persistent ppm mismatch eventually
   exhausts any finite queue. Existing finite runs do not close this obligation.
2. Resource/control coverage: routing, capture/playback and diagnostics are in
   the intended architecture but not yet covered by the persistent model.
3. Analog/clock ordering: blocker processing and LO phase must enter at their
   correct points; sampled baseband noise is not RF frontend validation.
4. Combined uncertainty/recovery: test the complete configured model together,
   with signed coupling and timed control visibility, not only isolated knobs.

Physical RF timing and converter risks below remain real but are deferred during
mathematical closure. The RF replay previously described as live has completed:
10k bias restoration improved I-leg amplitude but still left12 weak cycles per
leg. No qualified autonomous remedy resulted. No new physical run is required
for this mathematical audit.


## Historical physical-risk assessment — pass 753

All three whole-platform feasibility questions remain **not established**.
Keep the full wired/RF companion, terminal/die limits, narrow operating-point
allowance and schematic-before-layout requirement. The current work is model
validation and failure isolation, not a tapeout implementation milestone.

| Priority | Current evidence | Next discriminating action | What it does not prove |
| --- | --- | --- | --- |
| Autonomous RF timing | RF-only buffer change avoids the globally modified feedback failure in a 1.001us seeded run, but 82–84 of 508 I-leg cycles fail diagnostic amplitude thresholds. | Replay reproduction passes; fixed common mode removes all weak cycles in the diagnostic window. Implement a realizable common-mode rejection/bias remedy on RF paths only, then test autonomously; ideal replay is not the remedy. | Cold start, long-term lock, mixer conversion quality, phase noise or yield. |
| Converter/reference fidelity | Frozen top-loading term survives independent amplitude and a known added-capacitance test. Nominal-rail causal SAR still misses one of six physical codes. | Second refinement completed:1.83uV probe reproduction, at most1.34uV preclock change, unchanged24 decisions. Full terminal probes now reproduce within3.41uV and close tested charge windows to0.0125fC. Build a causal model retaining feedback-gate/output-terminal dynamics and validate on a different stimulus; recorded KCL closure is not prediction. | Full ADC transfer, ENOB, noise, arbitrary code history or target 12-bit performance. |
| Connected mathematical architecture | Framed multicarrier paths and active RF reset/drain tests pass their scenarios. Timed finite bursts now pass256 near-capacity phase cases after fixing drain-horizon and same-time ordering bugs. | After the active physical checks, return to shared startup/reset/clock-loss propagation through every stateful block and queue. | One executable passing all modes and lifecycle scenarios; the separate screens are not full-chip closure. |
| Wired autonomous timing | Mathematical transition recovery works on declared patterns; long transition-free behavior has a demonstrated failure. | Retain transition-density contract; link physical detector/oscillator actuation to the integrated model and test acquisition/disturbances. | A physical autonomous CDR or protocol-compliant endpoint. |
| Die/package coexistence | No validated RF/package model or complete extracted die exists. | Maintain explicit supply/load/coupling uncertainty budgets; later test concurrent aggression once connected transistor blocks work. | That a narrow temperature/supply range bounds substrate/package effects. |

Current targeted RF simulation, verified live in pass767:
`transceiver-lo-bias-restoration` passed909ns of1001ns and remains running.
The independent100mV reference validation completed; frozen coefficients and
source/artifact hashes passed the scorer. All three conversion histories are
internally consistent, which is not an ADC accuracy qualification.

Full reference terminal KCL closure does not imply a predictive charge law.
Independent DC measurements show that terminal-minus-channel current includes
steady body current. Adding its nominal independently measured value to the
independent AC prediction reduces original high-rail maximum error1.947→0.464fC
and RMS1.192→0.170fC without fitting. Low-rail maximum changes0.0262→0.0305fC.
Fixed DC bias and measured voltage endpoints remain limitations.

The new100mV stimulus exposes frozen constant-model errors2.952/0.418fC
(high/low); frozen two-terminal errors3.039/0.0810fC. Independent AC+DC prediction now reduces new-stimulus high-rail max/RMS error
to0.558/0.183fC, while low-rail maximum slightly worsens to0.109fC. Next probe
independent drain/gate bias dependence over the observed envelope, then connect
causal rail dynamics. Do not fit away the independent validation discrepancy.

The connected suite now passes10 scenarios, including persistent lifecycle
mode changes/reference loss and drain epochs. The lifecycle screen still uses
arrival-paced consumption and coherent management events. It is not yet a
single independently paced full-chip simulation or physical clock model.
