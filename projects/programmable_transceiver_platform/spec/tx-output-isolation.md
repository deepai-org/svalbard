# RF output isolation candidate

The managed TX observer previously applied the modulator and LO-feedthrough law
without any output enable. `connected-tx-output-isolation-audit.json` records
quiet calibration peak0.217225 and immediate post-stop magnitude0.201824 in
normalized envelope units. After10us, both stop and reference-loss cases settle
to0.002499999 LO feedthrough. Digital queue cancellation does not isolate RF.

`IsolatedTxCalibrationChip` is an experimental mathematical composition. Its
output isolation follows dg/dt=(g_target−g)/tau with assumed20ns time constant,
on amplitude1 and off amplitude0.001. A valid first DAC completion requests on;
quiesce requests off. The control state is continuous at switching and the RF
reconstruction state is retained. Finite bursts hold the last DAC code until
explicit stop. These parameters are sensitivity assumptions, not device evidence.

The output observer applies g to the complete modulated envelope, including
modeled LO feedthrough. Internal calibration observes the signal upstream of the
isolation stage. Therefore this candidate cannot calibrate the isolation stage
or pad-side transfer. The pad-side monitor in the block diagram is a different
proposed topology; selecting between them or adding a selectable observation
path remains an architectural requirement, with loading, area and resource costs.
No perfect termination or extra RF switch is silently assumed in the hardware.

Closure requires measured/bounded off transmission, additive leakage bypassing
the isolation element, on-state impedance and gain, switching charge/supply
transients, driver bias and startup settling, calibration isolation, loading,
recovery reopening and independent full-chain waveform quality. A power detector
cannot establish RF phase quality. No new pins or physical area proof follows
from this mathematical candidate.


## Managed isolated TX recovery — 2026-09-21

IsolatedTxCalibrationChip now has an executable composition with ManagedTxHostChip
in isolated_tx_recovery_screen.py. Both0→1 and1→0 reference-loss recoveries pass
coarse reacquisition, fresh TX calibration, stale-generation rejection and host
retraining. Before and after recovery, the gate remains disabled until the first
valid DAC completion. At that exact boundary its transfer remains0.001, then
follows the declared20ns exponential toward unity; no instantaneous enable jump
or reconstruction-state reset is introduced. Reference loss closes the request
while retaining gate charge and reconstruction state.

Evidence: connected-isolated-tx-recovery.json (two recovery directions, four
sampled onset trajectories). Targeted run exited0; prior isolation source hashes
still match their manifest. Registered the screen without claiming a full-suite
rerun. This is a noiseless finite lifecycle test with internal sample injection,
not full-chain modulation quality, simultaneous wired traffic, physical isolation
or monitor/loading closure. Next bring isolation into the loaded independent
waveform check and resolve the detector's pre-/post-isolation topology.


## Loaded isolated TX waveform composition — 2026-09-21

Promoted the experimental managed isolation composition to a reusable class
(not a default candidate) and added --output-isolation to the independent TX
waveform harness. Mode0 and mode1 both pass with fraction0.30, managed host,
relative TX correction, gain/offset/curvature detector readout and the existing
loaded/noisy profile. TX errors are7.3425% and8.5900%; mode1 RX is6.5963%.
Mode0/1 out-of-band-to-in-band finite-record ratios are−41.884/−38.363dB;
these are not protocol masks. Both launch manifests verify unchanged source
hashes and terminal successful reports. The reusable class also passes both
opposite-mode recovery directions again after refactoring.

The standard quality metric fits the first quarter and validates the remainder.
A separate recorded-mode1 onset analysis therefore reports first100ns,
200ns and1us errors. Isolation-only waveform increments are3.544%,1.358%
and0.720% RMS relative to ideal energy. Late-gain-referenced first100ns error
is8.349%; this retrospective diagnostic is not causal acquisition or a new
startup pass gate. Observation cadence can miss instantaneous peaks.

Dividing the mode1 output by its recorded isolation transfer reproduces the
previous ungated trace within1.11e−16. That is a useful integration control,
but also demonstrates the model still lacks isolation loading/current feedback.
The pre-isolation detector cannot establish pad-side transfer. Next prioritize
that topology and loading/resource closure over additional nominal gate tests.
Reports: connected-isolated-tx-wideband-mode{0,1}.json and
connected-isolated-tx-onset-mode1.json. Runner now registers164 cases; no full
aggregate is claimed. Historical failure profiles and all partial closure
statuses remain. No transistor/layout milestone is claimed.


## Isolation / monitor electrical topology audit — 2026-09-21

Added a three-node RMS phasor network: finite source resistance → internal
node → Riso||Cfeed → loaded pad; monitor Rtap→Rin||Cin attaches upstream or at
the pad. Sixteen on/off topology cases at2412/2437MHz check independent KCL,
nonnegative resistor loss and RF real-power balance; a nearly disconnected
monitor also matches the independently solved series-network transfer.

With exploratory source/load50ohm, on resistance5ohm, off resistance1Mohm,
tap1kohm and detector10kohm||50fF, at2412MHz isolation is−79.66dB with zero
feedthrough capacitance,−56.03dB with1fF,−36.05dB with10fF and−22.10dB with50fF.
A bracketed solve records the capacitance ceiling for the prior assumed−60dB
transfer. The finite-envelope stage's0.001 off amplitude is therefore not a
qualified implementation parameter.

Changing output loading between on/off states changes upstream monitor power
by about3.58× even at negligible capacitive feedthrough. Pad-side monitor power
instead collapses with isolation. Thus an upstream calibration observer remains
usable but measures a different loaded operating point; a pad-side observer
cannot simply retain the prior quiet calibration SNR. Possible next circuit
choices include controlled source impedance or switched matched loading, each
requiring explicit power, loading and resource models rather than ideal gates.

Evidence: connected-rf-isolation-load.json. This is a static topology sensitivity
audit, not live integration or device/package extraction. RF delivered power is
not DC chip consumption. The full waveform profile does not yet contain this
network, so its passing isolation result remains conditional. Keep the earlier
failed-assumption evidence; next connect a chosen topology to continuous detector
and output dynamics. Runner registers165 cases; no full aggregate claimed.


## Switched dummy-load sensitivity — 2026-09-21

Extended the passive three-node network with an optional internal shunt dummy
resistance, including its current in independent KCL and its dissipation in
real-power balance. Existing isolation tests rerun unchanged. A72-case sweep
covers two carriers,1/10fF feedthrough,±10% dummy resistance and40/50/60ohm
external loads. All KCL and power checks pass.

Nominal total dummy resistance55ohm (including switch resistance) replaces the
nominal5ohm switch +50ohm load. Muted/on upstream monitor amplitude ratios are
0.99989–0.99997, versus the prior large load-disconnection change. Isolation is
about−61.5dB at1fF, but only−41.5dB at10fF. Worst calibration amplitude mismatch
across the declared sweep is15.42%; a fixed dummy does not track unknown loads.
Nominal dummy dissipation is0.00489W per squared volt of RMS Thevenin source
amplitude. This is an RF network normalization, not the chip DC budget.

Evidence: connected-rf-dummy-load.json. This supports a load-preserving topology
candidate but does not qualify switch capacitance, switching sequence, thermal
or supply dynamics, active driver load dependence or physical area. Dummy switch
off parasitics are absent and must be introduced before live integration. Next
connect a finite switching network and detector, retaining charge and testing
break-before-make and overlap behavior. Do not substitute ideal resistor switching
for the missing transistor implementation. Runner registers166 scenarios; no
full aggregate claimed and all mathematical closure groups remain partial.


## Charge-retaining switched RF load — 2026-09-21

Added a four-node complex-envelope RC model with fixed capacitor matrix and
piecewise conductance matrix: C dv/dt+(G+jωC)v=b. Internal driver, pad, detector
and dummy resistor top are separate nodes. Both output and dummy switches retain
parallel feedthrough capacitance and finite off conductance. Switch commands
change resistance without resetting voltages. Matrix-exponential propagation
retains state; the dummy resistor is behind its switch rather than disappearing.

Six cases cover1/10/50fF dummy feedthrough and100ps break-before-make or overlap.
Independent branch-reduced steady phasors, capacitor continuity, subdivision,
long-time settling and integrated source-minus-resistor energy balance pass.
The initial100ps steady-state comparison failed because the monitor had not
settled; the model was preserved and the asymptotic check moved to2ns. Switching
trajectories still use the100ps interval, with no claimed timing requirement.

Break-before-make produces internal peak0.977–0.981 versus initial amplitude
about0.518, while overlap does not exceed the initial amplitude in these cases.
This is a concrete source-envelope disturbance omitted by the former scalar gate.
No modem startup budget, peak-power rating or physical switching feasibility is
claimed. The model omits MOS gate-charge injection, nonlinear capacitance,
supply current and package inductance. Parameters remain exploratory.

Evidence: connected-rf-switched-load.json. Next connect its continuous monitor
voltage to the finite detector and use the pad voltage in the live output path;
retain an explicit source/driver normalization and switching policy. Runner now
registers167 cases; no full aggregate or whole-chip closure claimed.


## Continuous loaded detector connection — 2026-09-21

Added rf_loaded_detector.py: exponential RMS Thevenin source terms drive the
four-node switched RC network, whose actual monitor-node exponential voltage
terms feed the finite square-law detector. Particular forced responses plus
retained homogeneous modes provide continuous pad/monitor trajectories without
assuming a unity tap or resetting network state. Ill-conditioned modal bases
and resonant source representations are rejected explicitly.

All four output/dummy switch combinations pass independent DOP853 voltage
integration and numerical detector convolution, with worst tested voltage error
7.35e−12 and detector error below3e−17. Subdividing the interval with correctly
advanced source coefficients preserves network and detector state. Switching
after an ADC request does not rewrite the captured code; the detector continues
evolving through conversion latency. Evidence: connected-rf-loaded-detector.json.

This connects the electrical load to the detector locally, not yet to managed
full-chip calibration or its output observer. Source amplitudes are explicitly
RMS Thevenin voltage envelopes; normalization must be reconciled with the live
TX envelope before integration. Nonlinear active-driver impedance, source supply
current, device charge injection and package coupling remain absent. Next drive
this composition from the existing reconstruction/modulator exponential terms,
then verify calibration and waveform quality with one shared network state.
Runner now registers168 cases; no full aggregate or closure is claimed.


## Loaded reconstruction/modulator calibration and pad playback — 2026-09-21

Connected the real Reconstruction/RfTxState exponential output through the
nonlinear IQ/leakage/cubic modulator to LoadedDetector. The timed calibration
sequencer writes quantized probes, waits for detector integration and ADC latency,
fits relative correction and commits actual DAC coefficients. Both monitor and
pad voltages arise from one retained electrical network; no hidden monitor-gain
normalization is used. After calibration, switching from dummy load to external
load preserves node voltages, and subsequent independent multitone playback is
observed at the loaded pad.

Two detector resolutions complete. Local corrected error is0.4991% at10bits
and0.1092% at12bits, versus2.8017% uncorrected. Evidence is characterized rather
than presented as a new protocol/architecture pass gate. Ideal/reference and
uncorrected paths use the same declared network.32 settling samples precede the
scored160-sample playback record; this does not certify switching/startup quality.
A zero ideal source exposed an empty exponential expansion; the adapter now
represents that correctly as an explicit zero term rather than rejecting it.

Evidence: connected-rf-loaded-calibration.json. This is the timed local sequence,
not managed full-chip command/resource/lifecycle integration. Carrier is ideal,
source is prescribed RMS Thevenin voltage, and active-driver supply/loading
feedback remains absent. Next transfer this shared network into the managed
candidate, preserving exact probe, DAC update and switching boundaries, then
rerun loaded/noisy quality and recovery. Runner registers169 scenarios; no fresh
aggregate and no transistor/layout milestone claimed.


## Managed loaded TX event integration — 2026-09-21

Introduced experimental LoadedTxChip. A pre-advance hook integrates the electrical
network/detector from the actual held reconstruction/modulator state before every
TX advance. This includes probe writes, DAC completion, reset and analog release.
The parent calibration monitor step is now overridable; default behavior remains
unchanged, while the loaded candidate avoids advancing its detector ahead of
intervening DAC events. The detector remains connected outside calibration.

Serialized coarse start, loaded calibration start/commit and mode activation pass.
One outer advance spans three DAC completions with network, detector and TX time
aligned. First update selects output load; reference loss selects dummy load while
preserving node voltage and immediately observed pad signal. Two microseconds
later pad magnitude is9.80e−7 versus0.04719 before stop. These are normalized
model values, not emission guarantees. Unsupported2437MHz retarget is rejected
before invalidating calibration. Actual loaded probe powers and correction are
recorded in connected-loaded-tx-chip.json.

The original tx_calibration_chip_screen also passes after monitor-hook refactoring.
This is an experimental integration milestone, not a restriction of the intended
chip: loaded-network retuning and LO phase/noise propagation remain required.
Only fixed2412MHz is currently supported by this adapter; it is not promoted to
the full quality candidate. Shared ADC ownership, active driver/DC feedback,
physical parameters and full host/wired quality remain open. Next integrate the
oscillator reference frame and retuning, then use the pad state in the independent
full-chain observer. Runner registers170 scenarios; no full aggregate claimed.


## Loaded network carrier-frame invariance — 2026-09-21

Added explicit network reframe(frequency, phase_delta) at current time. Voltage
coordinates rotate by exp(−j delta); the caller must rotate source amplitudes
identically and shift source rates by−j(new_omega−old_omega). The capacitor
matrix and physical state are retained. This is a coordinate operation, not a
physical oscillator frequency jump or an excuse to reset stored charge.

Three positive/negative-frequency-offset and pure-phase cases reproduce network
voltages within1.56e−17 and identical detector power. Capacitor energy remains
invariant. Negative controls that omit source transformation yield0.097–0.173
voltage discrepancy, demonstrating that a naive frequency-parameter update would
be wrong. Existing loaded-detector ODE/quadrature regression also passes.
Evidence: connected-rf-carrier-frame.json.

Managed LoadedTxChip remains explicitly fixed2412MHz. Next integrate actual
oscillator phase trajectories with bounded interpolation error, rather than
promoting coordinate equivalence as physical retuning/noise closure. Full-chain
observer, resource allocation, driver power and physical parameters remain open.
Runner registers171 scenarios; no full aggregate or schematic milestone claimed.


## Autonomous oscillator phase forcing of loaded network — 2026-09-21

Added piecewise-linear unwrapped phase forcing: exponential source amplitudes
rotate at each segment origin and source rates include the segment phase slope.
The network remains in its fixed carrier frame. A callback forecasts actual
ShapedRFClock phase with seeded20kHz frequency noise after40us evolution,
without changing the live oscillator time or phase.

Linear-phase forcing matches independently rate-shifted integration to1e−12.
A100ns noisy trajectory compares maximum requested steps4ns,1ns and0.25ns at
ten common observation times. The1ns versus0.25ns maximum voltage difference is
3.82e−7; detector difference1.83e−11. The4ns discrepancy is4.83e−7. Midpoint phase
residuals are recorded but are not error bounds; fine-grid residuals and modest
convergence improvement require event-boundary/precision investigation before
choosing a production step. No general interpolation guarantee is claimed.

Evidence: connected-rf-phase-forcing.json. This connects autonomous phase to the
loaded network locally; managed timing, external disturbance splitting, physical
retuning and independent full-chain waveform quality remain unfinished. Next
respect clock/control events explicitly and retain this convergence comparison
when integrating into LoadedTxChip. Runner registers172 scenarios; no aggregate,
whole-chip closure or transistor/layout milestone claimed.


## Event-aligned phase interpolation — 2026-09-21

Extended phase forcing with validated ordered breakpoints and correct source
coefficient advancement across every subinterval. A forecast oscillator supplies
its actual charge-pump transition times over the100ns test window. Full serialized
oscillator state, not just phase/time, remains unchanged by all forecasts.

Six aligned/unaligned step cases show that event splitting matters. Against the
event-aligned0.25ns reference, unaligned1ns maximum voltage discrepancy is8.96e−7;
aligned1ns is4.93e−9 (over180× smaller). Corresponding detector discrepancy is
1.78e−13 for aligned1ns. Linear-phase controls remain exact. Assertions retain
both the convergence limit and the discriminating improvement; no global error
bound or physical noise qualification is claimed. Midpoint phase residual remains
finite and is diagnostic only.

Evidence: connected-rf-phase-events.json. Use these transition boundaries when
connecting phase forcing to managed TX advancement; external supply/control
changes also require boundaries. This resolves the local event-interpolation
question, not full-chain noisy/retuning closure. Runner registers173 cases; no
full aggregate or schematic/layout milestone claimed.


## Phase-aware managed network adapter — 2026-09-21

Added PhaseLoadedTxChip using an overridable loaded-network forcing method.
Before each TX advance it forecasts the actual oscillator, splits at future
charge-pump transitions and applies phase relative to the fixed network carrier.
A guard rejects an oscillator already advanced beyond the network's source
interval; no discarded phase history is silently reconstructed. Forecasts do
not mutate the oscillator. The fixed-carrier admission guard remains for now.

A100ns startup/direct-probe test with seeded frequency noise passes at1ns and
0.25ns maximum steps. TX/network/detector/chip times align at every observation,
clock phase is identical across step choices, and maximum pad difference is
1.43e−12. This particular short startup trace has no additional interior pump
boundaries; the dedicated event-forcing test supplies that coverage. It does not
exercise calibration readiness, full traffic, retuning or settled lock quality.
Evidence: connected-phase-loaded-tx-chip.json.

Next run managed loaded calibration/recovery with this phase-aware adapter and
remove the carrier restriction only after physical-retarget/source-frame tests.
Then connect the independent full-chain observer to actual pad voltage. Resource
ownership, DC driver feedback and physical uncertainty remain unresolved. Runner
registers174 scenarios; no full aggregate or schematic/layout milestone claimed.


## Managed phase-loaded calibration completed — 2026-09-21

The existing long run completed successfully; it was never restarted. All
launch-recorded source hashes match. Actual phase-aware network calibration
commits, three DAC updates execute, and reference-loss shutdown retains charge
and closes the output path.157556 phase substeps and4951 interior event boundaries
were processed. Maximum sampled midpoint residual is0.00037461rad; this is not a
guaranteed waveform-error bound and whole-run step convergence remains open.
Pad magnitude changes0.04719082 before stop to9.80464e−7 after2us.
Evidence: connected-phase-loaded-calibration.json and terminal launch manifest.

Added read-only loaded pad observation and host-event capture. Tests cover physical
frame conversion, stale-time rejection, complete state nonmutation, pad-value
sensitivity and a double-LO negative control. Eight fixture host events preserve
delivery results and analog state while capturing actual pad voltages. Disabling
capture leaves delivery active. Evidence: connected-loaded-pad-observer.json and
connected-loaded-pad-capture.json. These are observer tests, not full-chain EVM.

Next compose this capture path with the real host/traffic quality harness,
retaining matched passive loading in the ideal reference. Retuning, recovery
reopening, shared ADC ownership, DC/active-driver coupling and physical uncertainty
remain unresolved. Candidate is experimental, not the default or full-chip closure.
Runner registers177 cases; no full aggregate or transistor/layout milestone claimed.


## Retunable loaded network coarse qualification — 2026-09-21

RetunableLoadedTxChip preserves the full managed coarse-qualification gate and
removes only the older fixed2412MHz target restriction. The network coordinate
frame stays fixed; physical LO phase supplies the changing carrier frequency.
A real managed2437MHz coarse search qualifies. Reapplying that qualified target
preserves oscillator phase, every network capacitor voltage and the observed
pad value at the control instant. Unqualified/invalid requests reject without
changing target or network state. Subsequent analog/clock times remain aligned.

Evidence: connected-retunable-loaded-tx.json, terminal exit0, launch source hashes
verified unchanged. This is acquisition/state-continuity evidence only; sustained
lock, calibrated recovery, both-mode traffic and post-retune quality remain open.
The mode0 loaded-pad quality run is still live (session17675) and has not been
restarted. New screens will be registered after it finishes to preserve its
launch-source snapshot; current runner still has177 entries.


## Actual loaded-pad full traffic mode0 quality passes — 2026-09-21

The original scalar mode0 run completed successfully, without restart. All
launch-recorded source hashes match. With matched passive loading in the ideal
reference, actual managed phase-loaded pad TX error is7.44323% and RX error
5.98506%, both below the unchanged provisional10% gate. Fitted TX gain magnitude
is0.945661. The observer uses actual pad voltage, not reconstructed source times
an assumed isolation scalar, and does not apply LO phase twice. The test retains
managed calibration, host activation, loaded/noisy traffic and nonlinear output.
Evidence: connected-loaded-pad-quality-mode0.json and frozen trace NPZ.

This closes one previously missing integration scenario, not the whole model.
Mode1, retuned/recovered quality, shared ADC conversion, analog mux behavior,
active-driver/DC supply feedback and physical parameter qualification remain open.
The passing candidate still uses its independent detector converter; its result
must not be transferred to the shared-ADC prototype without requalification.

A separate batch-solve candidate matches48 voltage comparisons across switch
states, phase-rate offsets and observation times. Local100-call median improves
0.1485→0.0263s (~5.65×), preserving modal/resonance guards. Evidence:
connected-batched-rf-response.json. Whole-chain substitution is not yet qualified.
The vector-detector phase-calibration comparison remains running(session89896);
registration is still deferred to preserve that launch snapshot.
