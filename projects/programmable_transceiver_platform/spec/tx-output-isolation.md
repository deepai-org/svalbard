# RF output isolation and loaded-network contract

This note owns the output network, retained charge, carrier coordinates and
pad observation. [TX calibration](tx-output-stage-sensitivity.md) owns fitting
and observability; [shared-ADC integration](tx-detector-shared-adc-gap.md) owns
monitor allocation. Use [current priorities](risk-priorities.md) and
[closure gates](mathematical-closure.json) for completion decisions. The evidence
below describes successive experimental models, not qualified RF hardware.

## Electrical and lifecycle requirements

Digital queue cancellation does not isolate RF. Held DAC values and LO
feedthrough can persist after stop. Apply isolation to the complete output,
including leakage, while retaining reconstruction and electrical state. A valid
first DAC completion requests enable; stop/reference loss requests disable.
Recovery requires coarse reacquisition, fresh calibration, current generation
and host retraining before reopening. A finite burst holds its final DAC code
until explicitly stopped; opening must not be an instantaneous voltage reset.

The early scalar candidate uses dg/dt=(g_target−g)/tau with assumed tau=20 ns,
on amplitude 1 and off amplitude 0.001. It provides a lifecycle control, not a
physical isolation specification: it lacks load/current feedback. Its upstream
calibration detector cannot measure pad-side transfer. A pad-side observer sees
reduced signal during isolation; moving or selecting the tap requires an explicit
loading, noise, area and resource model. No ideal termination or extra RF switch
is implicit in the design.

The loaded candidate uses RMS Thevenin source envelopes and a four-node network:
internal driver, pad, detector and switched dummy-resistor top. Finite source and
load resistances, monitor tap/input loading, and both switches' off conductance
and parallel feedthrough capacitance matter. A dummy load may preserve the
calibration operating point but cannot track an arbitrary external load.
Its RF dissipation is not the chip's DC consumption.

For piecewise conductance G and fixed capacitor matrix C, propagate
C dv/dt + (G+jωC)v = b without resetting node voltages on switch changes.
Retain the dummy resistor behind its switch. Check independent KCL, resistor
loss, real-power/energy balance, capacitor continuity, interval subdivision and
long-time settling. Break-before-make and overlap are distinct load histories;
no switch timing requirement follows from a single exploratory trajectory.

Feed the actual continuous monitor voltage into the finite square-law detector,
and observe the pad voltage from the **same** network state. Exponential source
terms plus retained homogeneous modes support exact interval propagation;
reject ill-conditioned modal bases and resonant source representations. An ADC
request captures the then-current result: switching during conversion must not
rewrite that captured code. Keep detector evolution active outside calibration.

Advance the network before every change to its held reconstruction/modulator
source, including probe writes, DAC completions, reset and release. An outer
advance spanning several DAC events must split at each event. Reconcile source
normalization with the live TX envelope; do not silently normalize monitor gain.
Keep calibrated and ideal-reference paths under matched passive loading.

## Oscillator coordinates and independent observation

A network reframe at its current time is a coordinate operation, not a physical
frequency jump: rotate voltages and source amplitudes by exp(−j delta), and shift
source exponential rates by −j(new_omega−old_omega). Preserve C and stored energy.
Alternatively retain a fixed network carrier and force it with the physical LO
phase trajectory, including physical retuning. Changing only a frequency
parameter gives the wrong answer.

Piecewise-linear unwrapped phase forcing must advance source coefficients across
each subinterval and split at oscillator charge-pump transitions and external
supply/control changes. Forecasts must leave the complete oscillator state
unchanged. Reject a clock already advanced past the source interval rather than
inventing discarded phase history. Midpoint residuals are diagnostics, not a
global waveform-error bound; retain independent step-convergence checks.

### Loaded pad observation

The implementation in
[loaded_pad_observer.py](../system_model/connected/loaded_pad_observer.py) reads
complex RMS pad voltage in the network's fixed frame (2.412 GHz in the original
candidate). The source already includes physical LO and branch phase. At an
independent observation carrier f_obs, use

    v_observed(t) = v_pad(t) * exp(j*2*pi*(f_network - f_obs)*t)

Apply the physical-frame conversion once. Do not multiply by oscillator phase
again, reconstruct output from DAC/filter state, or substitute a scalar isolation
transfer. Require network.time == chip.time at observation; reject stale times
and nonfinite times/carriers, and leave all analog/digital state unchanged.

Reference waveforms must declare the same RMS Thevenin-source normalization and
nominal passive network. The roughly one-half source-to-load voltage division
is physical loading. Report pad voltage and gain explicitly, without oracle
monitor-transfer normalization. Detector power establishes neither pad phase
nor absolute radiated power. Quality comparisons require aligned ideal/actual
timestamps, managed calibration and retained-state switching; scalar-isolation
results do not transfer automatically to this composition.

Test independently constructed frame conversion, pad-value sensitivity,
double-LO negative controls and complete nonmutation. Host-event capture must
preserve delivery with capture enabled or disabled. Full-chain error needs an
independent carrier reference; calibration success or retarget continuity alone
does not certify settled traffic quality. The scoped evidence below distinguishes
observer fixtures, retuning continuity and the completed mode0 loaded-pad run.
Historical pending-run notices are not current process status or additional
quality evidence.

## Scoped evidence

Reports below remain separate because they test different assumptions or stages.
The full original journal is linked below for all numerical details and the
historical implementation/registration sequence.

| Report in `evidence/` | Finding and scope |
| --- | --- |
| `connected-tx-output-isolation-audit.json` | Unisolated quiet-calibration peak 0.217225, immediate post-stop magnitude 0.201824; stop/loss settles to 0.002499999 LO feedthrough after 10 µs. Normalized units, not emission measurements. |
| `connected-isolated-tx-recovery.json` | Both 0→1 and 1→0 recoveries retain analog state; enable stays at 0.001 at first valid DAC completion and subsequently rises with the assumed 20 ns pole. Noiseless lifecycle test with internal injection. |
| `connected-isolated-tx-wideband-mode{0,1}.json`, `connected-isolated-tx-onset-mode1.json` | Scalar-gate TX errors 7.3425%/8.5900%, mode1 RX 6.5963%; finite-record out/in ratios −41.884/−38.363 dB are not masks. Removing recorded scalar transfer reproduces the ungated trace within 1.11e−16, exposing missing loading feedback. First-100 ns isolation increment 3.544%; fitted late-gain onset error 8.349% is retrospective, not causal startup qualification. |
| `connected-rf-isolation-load.json` | Sixteen 2412/2437 MHz static topology cases. With exploratory 50 Ω source/load, 5 Ω on/1 MΩ off and 1 kΩ tap into 10 kΩ∥50 fF, isolation at 2412 MHz changes from −79.66 dB at zero feedthrough to −56.03/−36.05/−22.10 dB at 1/10/50 fF. Upstream monitor power changes about 3.58× with loading; the assumed −60 dB scalar is unqualified. |
| `connected-rf-dummy-load.json` | 72 static cases: nominal 55 Ω dummy gives muted/on monitor amplitude ratio 0.99989–0.99997, but ±10% dummy and 40/50/60 Ω loads yield up to 15.42% mismatch. Isolation approximately −61.5/−41.5 dB at 1/10 fF. Nominal dummy loss 0.00489 W per squared RMS source volt; dummy-switch off parasitics absent in this static stage. |
| `connected-rf-switched-load.json` | Six dynamic cases add both switches' parasitics. 100 ps break-before-make raises internal peak to 0.977–0.981 from about 0.518; overlap does not in these cases. The initial 100 ps steady-state assertion failed; asymptotic comparison uses 2 ns while switching trajectories retain 100 ps. No physical switch rating follows. |
| `connected-rf-loaded-detector.json` | All four switch combinations match independent DOP853 voltage integration and detector convolution: worst voltage error 7.35e−12, detector error <3e−17. Subdivision and conversion-latency capture retain state. Local composition, not full-chip qualification. |
| `connected-rf-loaded-calibration.json` | Timed local calibration/pad playback: corrected errors 0.4991% at 10 bits and 0.1092% at 12 bits versus 2.8017% uncorrected. Uses ideal carrier and prescribed source; 32 settling samples precede 160 scored samples, so startup is not qualified. Explicit zero-source expansion is supported. |
| `connected-loaded-tx-chip.json` | Managed calibration and three DAC completions align network/detector/TX times. Reference loss preserves instantaneous pad state, then magnitude falls from 0.04719 to 9.80e−7 after 2 µs. This adapter's 2412 MHz guard rejects 2437 MHz before invalidating calibration. |
| `connected-rf-carrier-frame.json` | Three coordinate-change cases agree within 1.56e−17 with identical power/energy; omitting source transformation gives 0.097–0.173 voltage discrepancy. Coordinate equivalence is not physical retuning evidence. |
| `connected-rf-phase-forcing.json` | Seeded 20 kHz frequency-noise forcing: 1 ns versus 0.25 ns maximum voltage difference 3.82e−7 over 100 ns; unaligned convergence was insufficient to select a production step. Linear-phase controls remain exact. |
| `connected-rf-phase-events.json` | Six step/alignment cases: splitting actual pump events improves 1 ns discrepancy against aligned 0.25 ns reference from 8.96e−7 to 4.93e−9 (>180×); detector discrepancy 1.78e−13. No general interpolation bound. |
| `connected-phase-loaded-tx-chip.json` | Short startup/probe comparison: 1 ns/0.25 ns pad difference 1.43e−12, aligned clocks/state. This trace contains no extra interior pump boundaries; the preceding event test supplies that coverage. |
| `connected-phase-loaded-calibration.json` | Managed calibration, three DAC updates and retained-charge loss shutdown complete with 157,556 phase substeps and 4,951 interior boundaries. Sampled midpoint residual 0.00037461 rad is not a guaranteed error bound; whole-run convergence remains separate. |
| `connected-loaded-pad-observer.json`, `connected-loaded-pad-capture.json` | Read-only frame/stale-time/state tests and eight host-event capture fixtures pass; these are observer tests, not full-chain EVM. |
| `connected-retunable-loaded-tx.json` | Real 2437 MHz coarse acquisition qualifies; reapplying qualified target preserves phase, capacitor voltages and instantaneous pad value. Invalid/unqualified requests reject without mutation. Acquisition/continuity does not prove sustained post-retune quality. |
| `connected-loaded-pad-quality-mode0.json` | Actual managed loaded-pad mode0 TX/RX errors 7.44323%/5.98506% meet the provisional 10% screen, with fitted TX gain 0.945661 and matched ideal loading. Independent detector converter remains in this composition; do not transfer the result to the shared-ADC prototype. This row makes no mode1/recovery claim. |
| `connected-batched-rf-response.json` | 48 voltage comparisons preserve modal/resonance guards; local 100-call median 0.1485→0.0263 s (~5.65×). Local equivalence alone does not qualify whole-chain substitution. |

## Physical closure still required

Bound off transmission and bypass leakage, on impedance/gain, active-driver
load dependence and bias/startup, switch charge injection/nonlinear capacitance,
supply/DC feedback, thermal effects, package inductance/coupling, monitor noise,
resource ownership and physical area. Confirm calibrated reopening, retuned
traffic, noise and waveform quality in each intended composition. Passive model
checks do not establish MOS feasibility, an emissions limit, extra available pins
or extracted layout performance. Current closure decisions stay with the linked
gates rather than the historical scenario counts or queued-session notices.

The [complete immutable experiment history](https://github.com/deepai-org/svalbard/blob/8bd7e601beba1b28d6bb0f4e092b1a76a5e2868c/projects/programmable_transceiver_platform/spec/tx-output-isolation.md)
preserves all original measurements, intermediate failures, implementation names
and historical next steps. Those steps and process notices are not a current
backlog or evidence of a running job.
