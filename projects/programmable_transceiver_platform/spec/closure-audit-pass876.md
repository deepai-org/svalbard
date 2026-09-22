# Mathematical closure audit — pass876

The full objective remains: complete the connected mathematical chip, then a
working transistor-level schematic, then begin layout. Passing an aggregate
suite proves only its declared scenarios. The new107-scenario run is pending;
its predecessor passed80 scenarios. Do not change hashed model/profile inputs
while this run is active.

## Requirements and current evidence

| Obligation | Current evidence | Still needed |
|---|---|---|
| RF and wired paths on one timeline | Fractional wideband four-path experiment, autonomous wired RX, finite converters and host framing | Promote a single declared implementation/profile and run its lifecycle/concurrency tests; avoid relying on the historical PlatformChip profile |
| Autonomous clock services and RF tuning | Both pulse loops integrated; shaped integer feedback on1MHz RF grid; two tuned noisy wideband channels pass | More ratios/initial conditions, fractional recovery/retune, and declared noise/supply failure envelopes |
| Bounded supported transport | Finite and count-free RX/TX tests, atomic dual start, explicit overflow/underrun and epoch abort | Continuous operation with the fractional candidate, persistent rate mismatch/service envelopes, independent host control agreement |
| Programmable analog/diagnostic resources | Weighted gm/C tile, monitor sources, ADC allocation and timed state-preserving control | Trim-to-analog response and calibration observation/control connected to actual model state |
| Calibration with isolation | Pin plan requires shared sequencer/local trim storage and quiet-window handling; existing RTL has a calibration helper | Model its actuators and observations without oracle feedback; show range, resolution, convergence, residual error and rejection/ownership rules |
| Failure, reset and mode changes | Detector rearm, monitor validity, transport abort, integer pulse mode recovery | Apply the same tests to the shaped fractional candidate, including failed acquisition and stale configuration |
| Uncertainty/margin | Explicit assumptions, signed rail tests and retained failed divider/bandwidth/interference cases | Delineate supported mathematical parameter ranges from exploratory stresses; physical characterization remains a later obligation |
| Reproducibility | Fresh-report/quality gates and all candidate profiles now hashed | Verify completion, every report/log hash and unchanged source snapshot after the live aggregate finishes |

The implementation_profile in mathematical-closure.json still points to the old
profile, and its chronological remaining-work paragraphs contain superseded
statements. Consolidate that inventory from current evidence after the snapshot
run ends; do not interpret old text as proof that newly implemented functions
are still absent, or erase genuine remaining obligations.

## Scope traceability

The explicit connected-model acceptance in fast-feasibility-workflow.md includes
RF/wired end-to-end behavior, autonomous acquisition, bounded queues, reset/mode
changes, configuration and calibration. The pin plan specifies local trim and
calibration isolation. Those are core remaining obligations.

Trigger routing and lossless stream stopping occur in the accumulated closure
backlog, but the inspected pin/macro contracts do not yet define their source,
terminal assignment or host handshake. They remain unresolved design contracts;
this audit does not silently remove them or claim the current abort stop is a
lossless stop. Resolve the intended interfaces before inventing extra pins or
calling an unimplemented trigger function complete.

Optional coding/filtering helpers in the pin plan should be treated according to
their declared optional/bypass contracts. External modem, MAC and PCIe endpoint
logic remains outside the analog/PHY chip as agreed with the user.

## Next implementation priority after the frozen run

Connect calibration to a concrete local analog actuator and an owned observation
path, with an explicit quiet-window contract. Reuse the current detector/monitor
and timed-management mechanisms where applicable. Verify convergence on held-out
observations and preserve other domains' settings; a mathematical trim command
which directly reads hidden error is not calibration evidence.

Physical jitter/noise, actual converter performance, GF180 parameter uncertainty,
power/package coexistence and area are still unqualified. The user allows a
narrow controlled voltage/temperature window, but that does not establish process
or mismatch bounds. Full mathematical closure does not by itself prove silicon
feasibility, and no new layout should precede the connected transistor schematic.

## Scratch calibration evidence — pass877

While the aggregate snapshot remains frozen, a prototype in
/tmp/svalbard-calibration-pass877 models a12-bit monotonic offset actuator,
first-order settling and comparator-only MSB-first search with the RTL helper's
nine-clock observation spacing. Five in-range offset cases settle within one
assumed trim step; two out-of-range cases saturate and report a range limitation.
A2mV comparator bias leaves about2.1mV residual despite apparent convergence.

A second search with reversed comparator inputs, followed by an upward-rounded
average of the two lower-bound codes, cancels fixed comparator bias in15 tested
combinations. The rounding avoids adding an extra downward half-step bias.
Out-of-range searches restore the original code. Held-out residual measurements
are test oracles only; the controller receives comparator decisions, not hidden
offset parameters.

Exact scratch sources and reports are preserved as evidence/staged-calibration-*
(text copies for source files). This code is not yet in the common chip or the
aggregate source snapshot. Its range, monotonicity, settling, invariant comparator
bias and ideal input reversal are assumptions. Switch offsets/noise, observation
ownership, timed sequencing and independent ADC verification remain open.

### Calibration sensitivity: settling and observation-switch mismatch

The staged 120-case sensitivity sweep varies five target offsets, actuator time constants from 20 ns to 1 us, input-referred switch mismatch (0, 0.25, 2 mV), and comparison spacing (225 ns or 12 us). Source and all measurements are preserved in `evidence/staged-calibration-sensitivity_check.py.txt` and `evidence/staged-calibration-sensitivity-report.json`. These are characterization cases, not a claimed operating distribution or measured silicon statistics.

87 cases exceed one trim LSB, and none raises the endpoint/range flag. The original 225 ns spacing is therefore not a robust accuracy contract over these assumed settling constants. With 12 us spacing and zero switch mismatch, all 20 offset/time-constant cases meet one LSB (worst residual 61.1 uV). Longer settling does not cure observation-path error: a 2 mV input-referred switch mismatch leaves up to 2.015 mV residual even though both searches converge and no endpoint flag is raised.

Reversal cancels an invariant comparator offset but cannot distinguish the target offset from an offset that reverses with the target input. Repeating the same observation is not independent verification. Next implementation must expose programmable settling, quiet ownership, and validity separately from completion; residual accuracy needs an independent observation path with an explicit uncertainty budget. The ideal residual oracle used by this test must never become a controller input. No transistor or layout closure is implied.

### Independent calibration validity contract

A staged verifier now distinguishes `done`, `range_limited`, `accuracy` (verified / failed / unverified), and `valid`. It consumes only a separate residual observation and its declared error bound. A complete residual interval must lie inside tolerance before validity is asserted; overlap remains unverified. Missing uncertainty, stale epochs, lack of quiet ownership, and incomplete calibration cannot produce validity.

The independent-observer sweep covers 540 combinations of the previous plant offsets/settling/switch errors, 8/12/14-bit ideal quantizers, and observer offsets at -20/0/+20 uV. Tolerance is one 12-bit trim LSB (~122 uV). No case falsely verifies or falsely rejects against the independent truth oracle. Per resolution: 8-bit gives 0 verified / 60 failed / 120 unverified; 12-bit and 14-bit each give 48 verified / 120 failed / 12 unverified. Six lifecycle/missing-data negative controls all withhold validity. Source and complete evidence are `evidence/staged-calibration-verification*.{txt,json}`.

This exposes a further architecture requirement: coarse monitoring cannot certify fine trim merely by averaging repeated deterministic codes. Even higher resolution does not remove uncertainty at the acceptance boundary. The assumed independent 20 uV observer error budget has no physical qualification yet. Connecting a real ADC observation requires accounting for its own offset, reference error, loading, and switch topology; sharing the faulty calibration observation path would invalidate the independence assumption. These staged blocks are not yet connected to the full-chip scheduler.

### Calibration residual through connected ADC and host transport

A staged subclass now routes the settled trim output through the existing exclusive diagnostic receiver path, finite-latency ADC, framing, and host decoder. The comparator controller advances the chip clock for each trial; it never reads the independent residual. Four cases cover both operating modes with 0/2 mV calibration-switch mismatch; each returns eight exact transported ADC words. Evidence: `staged-calibration-chip-observation-report.json` and `staged-calibration-chip_observation_check.py.txt`.

This uses the actual ADC codec range, unlike the earlier ideal 0.5 V observer experiment. With the model's +/-1 V range, mode 0 has a 244 uV half-LSB; adding the assumed 20 uV observer offset gives +/-264 uV uncertainty even for a zero code. Thus it cannot certify a 122 uV trim tolerance. Mode 0 does detect the 2 mV error as failed; mode 1's 8-bit converter reports zero even for that error and correctly remains unverified. No case falsely claims calibration validity.

Required next decisions: select justified verification gain/range or a separate fine observer, account for observer offset/reference loading, then integrate timed calibration ownership and epoch invalidation. The staged experiment disables reference loading and assumes an independent zero-input observation route; serialized calibration commands and lifecycle recovery are still absent. This is connected mathematical evidence, not analog circuit qualification.

### Gain-assisted residual observation feasibility

A 1170-case codec-level sweep now bounds residual intervals with +/-2% gain error and +/-20 uV input-referred observer offset, including both residual polarities and saturation. It uses actual IQ codec quantization. Every non-saturated interval contains the independent truth; no decision falsely verifies or rejects. Saturated codes explicitly remain unverified.

For residuals of 0 or +/-60 uV, all 27 tested gain/offset-error combinations verify at gain 64 in 12-bit mode, and gain 128 in 8-bit mode. Smaller gains leave some or all cases uncertain. This is a possible verification route, not a selected/qualified circuit: gain 64 leaves only +/-15.6 mV nominal headroom and gain 128 only +/-7.8 mV. An initial low-gain range check and independently bounded offset/reference/settling are necessary before relying on fine observations. The 122 uV criterion remains a trim-resolution experiment, not a derived whole-chip RF performance requirement. Evidence: staged-calibration-gain-observer-report.json and staged-calibration-gain_observer_check.py.txt.

### Refocus: derive residual tolerance from useful signal quality

An 80-case offset/level/resolution sweep uses the existing held-out quality metric, without fitting away DC. Coherent unquantized cases agree with sqrt(2)*per-channel-offset / signal-amplitude to 1e-12. With 2 mV offset in both I and Q, 12-bit waveform error is approximately 28.0%, 9.4%, 2.8%, and 0.94% at respective complex amplitudes 10, 30, 100, and 300 mV. Thus even a visibly uncorrected offset can pass the provisional 10% screen at higher levels and fail badly at low levels. Exact results and assumptions are preserved in staged-calibration-offset-budget-report.json.

Do not add a gain-128 precision observer merely to satisfy the arbitrary one-trim-LSB experiment. First establish the minimum post-gain useful signal and allocate total distortion between DC, clock, noise, and nonlinear conversion. For a hypothetical 1% DC allocation at 30 mV complex amplitude, equal I/Q residuals must each be <=212 uV; the same allocation at 10 mV requires <=70.7 uV. These examples are not adopted requirements. Current full-chain errors already consume much of the provisional 10% screen. Calibration lifecycle and independent validity remain necessary, but precision circuitry should follow this system budget.

### Timed calibration controller staged

The staged event-driven controller executes two 12-step polarity searches, programmable settling before every comparison and after final trim, and a separate independent-observation phase. It rejects busy starts and stale observations, rolls back saved trim on cancellation, stops pending comparisons, and invalidates completed validity on epoch changes. Quiet ownership is a required caller input, not yet an integrated resource arbiter.

Twelve cases compare six offsets under one-shot versus 173-way time subdivision with the prior comparator-only algorithm. Endpoint exhaustion retains the old trim and fails validity. Additional checks cover epoch loss, quiet loss, saved-code rollback, no comparisons after abort, stale generation rejection, busy-start rejection and completed-result epoch invalidation. Evidence is staged-calibration-timed-report.json with preserved controller/test sources. The observation fixture still uses an ideal residual plus declared uncertainty; ADC-backed observation and serialized command integration remain.

### Calibration commands connected to chip management

The staged ManagedCalibrationChip subclass merges comparator events with the existing command scheduler and exposes serialized cal_start/cal_status/cal_abort. A completed 24-comparison search remains busy in observation-wait and never silently asserts valid. Tests exercise start/status/abort through real command delivery, reject mode/monitor mutation and duplicate starts while busy, restore saved trim on abort, then permit mode configuration and reject calibration while armed. The 480-clock comparison-spacing fixture gives 12 us per comparison. Evidence: staged-calibration-managed-report.json and corresponding preserved source/test files.

Remaining: the controller must schedule its independent ADC measurement, retain ownership through its conversion, release/restore diagnostic routing correctly, and expose live resource discovery. Direct API bypasses and every affected analog target configuration still need an ownership audit. Current fixed target, tolerance, and quiet predicate are staged fixtures, not a completed calibration architecture.

### Calibration ownership audit

Nine direct public mutation/scheduling paths now reject while calibration owns its target: RX route, filters, RF input, LO settings, carrier, diagnostic selection, ADC capture, DAC scheduling and mode configuration. Tests assert rejection leaves trim code, generation, scheduled comparison, route, gain and diagnostic selection unchanged. Calibration owner 9 is exposed on resource 8 and shared ADC resource 0 while busy; resource_count is 9. Comparison spacing now follows configured control_period rather than a hardcoded 40 MHz assumption.

The audit exposed and fixed two staged gaps: the disarmed acquisition interval is not a safe calibration-start window, and reference loss while reset does not invoke the normal active-chip quiesce path. Start now requires reset with reference present, and explicit reference loss cancels/rolls back in that state. Tests also exercise restart after reference restoration and resource release after abort. These checks use a 20 MHz control-clock configuration. Evidence: staged-calibration-ownership-report.json and preserved source. ADC verification integration remains pending; this does not prove a physical quiet window or protect arbitrary mutation of internal Python objects.

### Automatic quiet ADC verification

The staged AutomaticCalibrationChip schedules one 12-bit maintenance observation on a future control-clock edge after the trim settles. It reuses convert_adc, including frontend transfer, converter reference loading, ADC recovery and quantization. A separate bounded one-entry result sink waits the configured ADC latency. Normal RF and host streaming remain disarmed; calibration owns the converter until verification or cancellation. The total input-referred observation uncertainty must be explicitly supplied; absent a bound, completion is unverified. No plant truth enters the verification decision.

Four cases combine one-shot/61-way time subdivision and missing/300 uV declared error bounds, using 1 pF reference loading and 300 ns ADC latency. Exact observation traces agree across subdivision; each case records one real reference-load impulse and one quantized ADC conversion. A 10 us conversion interrupted by reference loss is cancelled and counted, with trim rollback and no result publication. Evidence: staged-calibration-automatic-report.json and source/test snapshots. The independent zero-input route and 12-bit maintenance selection are proposed architecture; the 300 uV bound and 1 mV tolerance remain test assumptions, not silicon-qualified requirements.

The same trim actuator is now inserted at the normal RF I-channel post-filter ADC input in the staged subclass. An independent 200 mV DC source returns 270.020 mV before calibration and 200.195 mV after calibration through the normal eight-sample ADC/framed host path. Thus the controller changes a real signal-path parameter rather than only its private fixture. Diagnostic tile selection bypasses this RF target. Evidence: staged-calibration-target-report.json; this is one additive I-offset target with ideal reference loading, not full I/Q/gain/LO calibration.

### Maintenance result recovery and status visibility

Recovery tests now cancel a 20 us maintenance conversion through both a serialized cal_abort and direct chip quiesce. The latter follows the real host-abort/drain acknowledgement before restarting in a new epoch. Both paths restore the original trim, count the old conversion cancelled, and permit exactly one new result after a fresh calibration. Advancing beyond the old completion deadline cannot publish that old result. Final accounting is two samples, one completion, one cancellation, zero pending.

cal_trim exposes the applied code through management. cal_status now exposes range-limited, failed-accuracy and unverified-accuracy flags separately from busy/valid; a missing observer error bound is visible to the host as unverified. Direct quiesce clears the maintenance slot immediately. Evidence: staged-calibration-recovery-report.json and preserved recovery test/updated module sources. Calibration remains staged outside the aggregate snapshot until its running regression ends.

### Calibration composed with fractional pulse clock candidate

A staged subclass combines AutomaticCalibrationChip and FractionalRFChip using the normal cooperative class hierarchy. Calibration, independent ADC verification, carrier retuning, autonomous acquisition and eight-sample host delivery pass for mode 0 at 2412 MHz and mode 1 at 2437 MHz. The actual RF clock object is ShapedRFClock, not the older sampled-PLL implementation. The trim remains applied to the normal receive path; reference loading and 30 ns conversion latency remain enabled. Evidence: staged-calibration-fractional-calibration-report.json and test source. This is a two-case integration smoke check; full combined-profile quality and recovery coverage still need to run on this unified candidate.

### Shared sequencer calibrates distinct I and Q targets

The staged controller now selects either post-filter offset actuator using cal_start payload bit 16 (low 16 bits retain comparison spacing). Each target has its own trim state; one sequencer/comparator/ADC allocation is shared. The selected ADC component is used for independent verification, cal_trim reads either target, and status identifies the selected target. Calibrating one target leaves the other's code unchanged. Both offsets are inserted into the normal receive path; diagnostics bypass these RF targets.

At initial offsets +70 mV I / -30 mV Q, serial calibration produces codes 1474 and 2293. Both-mode tests with shaped fractional clocks (2412/2437 MHz), reference loading and ADC latency then transport 64 samples of an independent 250 kHz complex tone. Held-out gain/phase-corrected waveform errors are 1.048% and 3.045%, below the existing provisional 10% screen. An offline negative control adding the original offsets back fails at 31.0% and 63.4%; it is explicitly not a fresh uncalibrated-chip simulation. Evidence: staged-calibration-iq-target-report.json and test source.

These narrow coherent-tone cases do not replace the combined wideband/noise/traffic test. ADC uncertainty and the 1 mV calibration tolerance remain declared fixtures. Full physical observer/trim qualification is still required after mathematical architecture closure.

### Aggregate terminal verification and code promotion

The pass876 process exited successfully: all 107 registered scenarios passed, all 702 source hashes match the initial snapshot, and all 107 report/log pairs match their recorded hashes. Its report is archived as connected-architecture-pass876-baseline.json. This does not include subsequently promoted calibration modules.

The staged combined wideband run also exited successfully. Its source checkpoint remained unchanged. After actual I/Q calibration and autonomous acquisition, 32-frame four-path traffic delivered 328/132 RF samples per direction and 1024/1638 wired words per direction for modes 0/1. Waveform error was 8.4134% / 8.5811%, below the unchanged 10% provisional screen. Source_count was explicitly extended to 8000 to cover real calibration time; all analog state was retained. Calibration accuracy itself remained unverified because no justified observer bound was supplied.

Six calibration model modules and six focused screens are now promoted into system_model/connected, including CalibratedFractionalChip. Focused verification is running. The mathematical closure inventory has been consolidated with every former remaining-work paragraph preserved as historical_notes_before_calibration; all ten requirement groups remain partial. The new candidate/profile relationship and still-unresolved interfaces are explicit.

All six promoted screens subsequently passed; their shared code snapshot remained unchanged, and every report/log hash was verified in calibration-promotion-verification.json. The runner now registers 113 scenarios. No fresh full aggregate has yet included the new calibration source set. Next priority is full lifecycle/continuous operation on CalibratedFractionalChip and a declared operating envelope.

### Unified-candidate continuous traffic and reference recovery

Six new lifecycle cases pass directly on CalibratedFractionalChip: continuous framed duplex with managed stop and deliberate host-starvation underrun in each mode, plus noisy reference-loss/drain/retune/opposite-mode recovery in both directions. Continuous cases validate exact played DAC values, ADC return-prefix integrity, bounded observed queues and pipeline accounting; both converters and RF pulse clocks are exercised. Reference recovery retains trim codes but invalidates the calibration accuracy claim, preserves oscillator phase progression without reference, then reacquires both loops and delivers 16 RF samples plus a wired word after the mode/carrier change.

Evidence: connected-calibrated-lifecycle.json and calibrated-lifecycle.log. The existing continuous traffic helper now accepts a chip factory and preparation interval; its original defaults are unchanged. The runner registers 114 scenarios. Remaining: longer/variable service envelopes, retune/lock-failure boundaries, trigger and graceful-stop contracts, and broader operating ranges; the finite run is not an infinite-duration FIFO or physical timing proof.

### RF startup sensitivity: range versus acquisition

The 54-case fractional startup screen completed with 42 sustained qualifications and 12 unqualified cases. All 12 are outside the assumed VCO tuning span: a -8% free-frequency offset (2.208 GHz) cannot reach 2437 or 2500 MHz with 200 MHz/V gain and +/-1 V control. Every tested inside-span combination acquired by 40 us and stayed qualified through 60 us. Phase and finite-noise variation did not repair a missing tuning range. These are exploratory model parameters, not measured GF180 corners.

Evidence: connected-fractional-startup.json and fractional-startup.log. The full 201-point nominal carrier sweep is still running. A coarse VCO bank with observable search/settling is the next justified architecture improvement if broad free-frequency uncertainty is retained; merely setting hidden free frequency per carrier would not demonstrate autonomous acquisition. See fractional-tuning-envelope.md.

### Full RF grid exposes ratio-dependent qualification holes

The 201-target nominal grid finished with unchanged captured sources: 195 sustained qualifications, six unqualified targets (2313, 2329, 2353, 2369, 2393, 2409 MHz). Three of those never lock; three briefly qualify and then lose lock, which would fault the full chip. No model compliance exception occurs. All six have denominator-40 feedback patterns and reference-edge frequency error above 4000 Hz (worst 4431 Hz), despite small phase error. This is separate from the 12 outside-span startup cases and refutes broad nominal tuning-range qualification at the current 350 kHz bandwidth.

Preserved connected-fractional-grid.json, fractional-grid.log, fractional-grid-run.json and the exact original screen source. A lower-bandwidth comparison at 325/300 kHz is running on those six targets plus four controls, with lock thresholds and acquisition deadline unchanged. Do not narrow the accepted carrier grid or declare it supported merely because two prior channels pass. Coarse range extension remains a second clock-architecture obligation.

The targeted lower-bandwidth comparison completed: both 325/300 kHz retain qualification for all ten failure/control targets, with worst tail frequency errors 3578/2567 Hz respectively. Lock limits and 40 us deadline were unchanged. Next is full-grid and combined RF quality at 300 kHz before adopting it. Three characterization screens are registered (117 total); their successful execution preserves unqualified operating points rather than claiming every point meets requirements.

### 300 kHz combined RF quality and counted coarse acquisition

The calibrated combined wideband test at 300 kHz finished successfully: 6.4989% / 6.7451% error in modes 0/1, with the same provisional 10% limit and calibration, detector, reference loads, blockers, oscillator noise and four-path traffic retained. The 201-target acquisition screen at this bandwidth remains running. Evidence: connected-calibration-wideband-300k.json and calibration-wideband-300k.log; prior 350 kHz reports remain intact.

An independent staged coarse-bank prototype uses only counts of divide-by-16 oscillator edges over a 2 us window, with an explicit 8 MHz quantization bound. A binary search selects among 16 assumed 25 MHz bank steps; it never reads the hidden free frequency. Bank changes preserve oscillator phase and loop-filter charge while the pump is held. All nine tested target/free-frequency combinations then acquire with the real 300 kHz fractional pulse loop, including the formerly unreachable -8% cases at 2437/2500 MHz. A deliberately insufficient 1.9 GHz free-frequency case is rejected, restores the old bank, and leaves the pump held.

This prototype is initial-acquisition-only with a centered filter. Its ideal monotonic bank, instantaneous frequency step, 2 us guard and stationary count-bound assumptions are unqualified; switch transients, drift/noise, live retuning and full-chip management ownership still need work. Evidence: staged-coarse-vco-report.json and exact source/test snapshots.

The 300 kHz full-grid run finished with 201/201 sustained qualifications. Together with the passing calibrated wideband comparison, this justifies adopting 300 kHz in FractionalRFChip and fractional-top-profile.json. The old default source/profile and 350 kHz failures are preserved. The older startup sensitivity screen is now explicitly pinned to 350 kHz so its historical meaning does not silently change. The runner registers 119 scenarios. Unified lifecycle revalidation at the new default is running.

All six unified continuous/reference-recovery cases pass at the new 300 kHz default. Evidence and source hashes are recorded in calibrated-lifecycle-300k-verification.json, with the actual report and log retained. The older 350 kHz lifecycle report was archived before replacement.

### Coarse bank: explicit settling and bounded counter observation

A staged bank model now adds a first-order coarse-frequency transient to both instantaneous VCO frequency and its exact phase integral. Writes preserve phase/filter charge and, for this settling model, instantaneous frequency. Closed-form response, 73-way time subdivision and nonmutating edge forecasts agree. The forecast bounds the entire coarse-bank frequency range rather than ignoring the transient.

Search uncertainty now includes integer-count quantization, the declared maximum transient's average over the measurement window, a supplied bounded noise amplitude and final settling residue. It reads only counter values; it does not inspect true frequency. Initial-centered-filter readiness is an explicit lifecycle flag, and renewed coarse acquisition after fine-loop operation is rejected. The initial-only restriction remains; it is not a hidden zero-voltage oracle for the controller.

Nine noisy cases combine 50/200/800 ns bank settling with 2300/2437/2500 MHz targets from the previously problematic -8% free frequency. Guards are max(2 us,8*tau_bound). Every observed frequency interval contains the independently checked steady bank frequency. All selected banks then acquire the actual 300 kHz fractional pulse loop by 40 us and retain qualification through 60 us without phase/filter reset. Evidence: staged-coarse-vco-settling-report.json and exact source/test snapshots. The bounds, monotonic bank and settling law are assumptions, not physical qualification; full-chip management integration is next.

### Coarse tuning integrated into timed management

CoarseStartupChip is an experimental extension of the calibrated fractional candidate. Its RF pump starts held with a centered filter; rf_coarse_start/status/abort run through existing serialized management. A nonblocking controller schedules bank settling and prescaled-count windows, shares ownership with I/Q calibration, and releases the fine PLL only after bounded coarse acceptance. RF_CLOCK_CLASS permits this clock implementation without changing the default ShapedRFClock behavior.

Both-mode startup cases from -8% free frequency pass at 2437/2500 MHz, then acquire both RF/wired clocks and transport 16 RF samples plus a wired word. Ownership, abort/rollback, no events after abort, reference-loss cancellation, restored-reference hold, restart, active-state rejection and stale-epoch queued-start tests pass. The stale-command fixture initially jumped directly to a future quiesce time; it now advances the scheduler before quiescing, as the internal quiesce API requires.

Evidence: connected-coarse-startup.json / connected-coarse-recovery.json and matching logs. 121 scenarios are registered. This remains startup-only: live coarse recentering/retuning, finite-width counter/CDC observation semantics, broader bank uncertainty and combined RF quality are not closed. It does not replace the main CalibratedFractionalChip entry until those restrictions are resolved.

### Finite coarse counter and coherent observation delivery

CoarseAcquisition now receives coherent 12-bit modulo snapshots of the /16 oscillator count. Start/end captures each have a separate two-control-cycle publication state and generation-tagged pending value. Current/previous-count freshness choices add one count of difference uncertainty to floor-count quantization, giving a conservative 16 MHz counter term for a 2 us gate. Counter-window validation prevents multiwrap ambiguity within the declared 3 GHz ceiling; configured oscillator envelopes above that ceiling are rejected. Invalid modular intervals fail the search, restore the bank and hold the pump.

Tests pass 80 arithmetic wrap cases and four full-chip endpoint-age combinations. Each integrated search includes an actual wrap between its captured endpoints and subsequently reaches fine lock; the final case uses a 20 MHz control clock to verify latency follows control_period. Cancellation between capture and publication discards the pending value. An injected inconsistent snapshot produces failure/rollback without release. Existing startup/recovery screens also pass after introducing the finite pipeline and quiet-window settling gate. Evidence: connected-coarse-counter.json, coarse-counter-final.log and coarse_*-finite-counter.log.

The runner registers 122 scenarios. The capture/CDC freshness and frequency bounds remain explicit assumptions requiring implementation validation; this is not a metastability qualification. See coarse-counter-contract.md. Live coarse recentering/retuning and full combined RF quality remain higher-priority gaps.

### Coarse-profile combined RF quality and passive recentering

The pending combined test finished: both modes pass after real counted coarse
search, I/Q calibration, loaded references, blockers, frequency noise and four-path
traffic. Relative RMS errors are 6.7617% (2412 MHz) and 9.8485% (2437 MHz), with
-8% free-frequency offset and the unchanged provisional 10% limit. The second
case has only 0.1515 percentage points of margin. This is two operating points,
not full-envelope closure. Preserve that narrow margin as a next risk priority.
Evidence: connected-coarse-wideband.json and coarse-wideband.log.

recenter_filter.py now models two finite passive shunts on the fine-loop capacitor
nodes. It preserves voltage and oscillator phase at switch closure; charge leaves
through the shunts and energy dissipates rather than being numerically reset.
A 12-times-declared-RC guard bounds residual voltage for subsequent counted bank
selection. Eight independent KCL/RK4 cases vary capacitor ratio, initial polarity
and RC time constant, checking both voltages, integrated voltage, drained charge
and resistor energy against the exact model. Time subdivision, energy accounting,
and invalid/aborted guard tests also pass. Two actual fractional-loop sequences
retune 2437→2500 and 2500→2300 MHz, acquiring within 40 us and holding through
60 us after bank selection. Evidence: connected-passive-recenter.json and
passive-recenter.log. Post-run artifact hashes are retained separately and are
not represented as a before/after full-suite source capture.

The matched shunt RC law, 400 ns bound, passive center and tuning law are explicit
assumptions. Common-mode rail work, switch charge injection and transistor bounds
remain unqualified. This is still a standalone retune sequence: integrating the
centering deadline, cancellation and recovery into full-chip management is next.
124 scenarios are registered; the last full aggregate remains pass876 (107).

### Full-chip managed warm coarse retuning

CoarseRetuningChip now connects finite passive recentering to quiet-state managed
carrier changes. The centering deadline owns the shared sequencer, status exposes
state 9, and the residual-voltage bound contributes to counter-search uncertainty.
Cancellation opens the shunts without resetting analog state and restores the
previous bank with settling; interrupted centering cannot qualify a new search.

Both modes pass initial acquisition, warm 2437→2500 / 2500→2300 MHz retunes,
fine-lock reacquisition and 16 RF samples plus a wired word. Tests also check
active/invalid-target rejection, exact switch continuity, calibration exclusion,
centering status, command abort, reference loss during centering, and successful
restart after the interrupted guard. The original startup screen also passes
after the factory extension; it retains the startup-only controller by default.

Three retained fixture failure logs record omitted receiver-detection rearm,
a serialized conflict command that advanced beyond the guard, and an invalid
drain acknowledgement while already reset. The final screen uses existing rearm
management, direct apply for the exact centering instant, and asserts the reset
state after quiet-window reference loss. No lock or quality threshold was relaxed.

Evidence: connected-coarse-retune.json, coarse-retune.log and post-run artifact
hashes in coarse-retune-verification.json. See coarse-retune-contract.md. There
are 125 registered scenarios; the last aggregate remains pass876 with 107 cases.
Recovered full-chain RF quality, wider uncertainty coverage and physical circuit
qualification remain open. The experimental candidate is not yet the main entry.

### Independent receive quality after warm retuning

The new composed warm-retune screen passes both modes: 2500→2412 MHz gives
6.0879% relative RMS receive error, and 2300→2437 MHz gives 7.1533%, with the
unchanged provisional 10% bound. Both ideal and impaired models use an identical
200 us warm prelude, initial acquisition, quiesce/drain, target retune, I/Q
recalibration and final acquisition/detection. Matched timestamps and source
coverage are asserted. The impaired run retains -8% free-frequency offset,
counted coarse selection, passive recentering, blockers/cubic response, spectral
clock noise, shared-reference and detection loading, and four-path host traffic.
Analog state is never cleared to obtain the result.

Evidence: connected-retuned-wideband.json, retuned-wideband.log and post-run
artifact hashes. The old 9.85% coarse-startup point remains valid evidence of
weak margin: the new test samples different waveform/noise phases and is not
an isolated A/B demonstration of improvement. Calibration is rerun after the
retune; retained calibration accuracy is not claimed.

Coverage review also found that the combined metric observes RX ADC words;
TX assertions establish transport/accounting and no underflow, not independent
RF output waveform/spectral quality. Add that observation on the same composed
candidate before treating all four analog paths as qualified. Source locations:
wideband_clock_quality.simulate, sustained_lifecycle.run and rf_cascade_state.
There are 126 registered scenarios; no new aggregate replaces pass876.

### Independent TX observation exposes a clock-quality failure

A nonloading observer evaluates the actual held/reconstructed DAC envelope and
copied oscillator phase against an independent nominal carrier. It does not use
the RX LO, so shared-LO cancellation cannot conceal TX phase error. Analytical
phase, decay, forecast nonmutation, receiver-phase independence, known in/out-band
tones and nonuniform-grid rejection all pass.

Both composed candidate modes fail the unchanged provisional 10% incremental
TX waveform screen: 10.3707% and 12.5872%. A repeat with recorded component
substitution gives phase-only errors 10.3585% / 12.5952% and baseband-only errors
0.7316% / 0.4908% after gain correction. This locates the observed error in the
LO phase term; it does not yet distinguish divider ripple, intrinsic assumed
frequency noise, or supply pulling. Next vary these independently while retaining
the complete candidate and unchanged quality threshold.

Finite-burst Hann out-of-channel/in-channel power is -25.11 / -13.26 dB, close to
the ideal-path -25.15 / -13.27 dB. This separate reconstruction/source-window issue
must not be hidden by incremental error against the same ideal filter. The metric
integrates outside ±10 MHz to observation Nyquist; no protocol mask is claimed.
Both paths retain host quantization. TX mixer/driver nonlinearities, IQ mismatch,
LO leakage and a justified emission requirement remain to be implemented.

Evidence: connected-tx-wideband.json, connected-tx-observer.json, matching logs and
post-run hashes in tx-observation-verification.json. Original failure report/log
and source snapshots are preserved. The initial reporter used status=passed with
quality_pass=false and process exit 1; the current reporter now consistently sets
status=failed. The failure was not waived: the aggregate registers the TX quality
screen as a strict gate. There are 128 scenarios; a fresh full suite cannot pass
until this failure is resolved. The historical pass876 aggregate is not current
qualification.

### TX clock isolation and filter-response diagnosis

Mode-1 matched experiments give 12.59% error with both forcing terms, 4.09% with
RF frequency noise removed, 8.71% with RF supply pulling removed, and 1.69% with
both removed. All select coarse bank 15. The combined failing gate is unchanged;
these are isolation experiments, not reduced qualification requirements.
Evidence: tx-clock-isolation.json and connected-tx-{no-noise,no-pulling,quiet-clock}.

An averaged analysis uses the actual filter impedance
Z(s)=(1+s R Cs)/(s(Cf+Cs)(1+s/p)), p=(Cf+Cs)/(R Cf Cs), and loop gain
Icp Kvco Z(s)/(N s). At the current 300 kHz gain setting and Cf/(Cf+Cs)=0.5,
it predicts ~12.95 degrees phase margin and 4.53 peak sensitivity. Reducing the
fraction to 0.25 gives ~34.70 degrees and 1.84 peak sensitivity. This is a circuit
parameter change preserving total capacitance and low-frequency PI gains, not a
reduction in assumed noise. Sampled delay, compliance and fractional spurs are
absent from that approximation and require actual pulse-loop tests.

A staged 2437 MHz pulse-loop screen qualifies fractions 0.5, 0.35 and 0.25;
0.2 does not acquire. The 0.25 case first qualifies at 9.675 us and holds through
60 us. A full two-mode TX quality run at 0.25 is now running with original noise,
loading and supply coupling retained. Constructor parameters expose the trial
fraction; the main default remains 0.5 pending tuning-grid, RX and lifecycle
requalification. Evidence: connected-pll-filter-response.json, staged-filter-lock
report/log/source. No new aggregate is claimed.

The full quarter-fraction TX run subsequently failed before reporting waveform
quality: mode 0 quiesced on RF oscillator lock loss at 202.05 us. Preserve
connected-tx-filter-quarter-failure.json and its traceback log. Its 201-target
grid remains running. The averaged response improvement and one initial lock
case did not establish full-chip qualification. A 0.35-fraction two-mode TX trial
is now running with the same forcing and unchanged lock/quality thresholds.
The runner has 129 scenarios, including the averaged filter-response screen;
the main independent TX quality gate remains failed at the default fraction.

### Filter trials finish; preserve acquisition versus waveform distinctions

At 300 kHz, fraction 0.25 retains qualification at 187/201 nominal carriers.
Fourteen failures have reference-edge frequency error above 4 kHz despite small
phase errors. Fraction 0.35 qualifies all 201 nominal carriers, but its composed
TX waveform errors are 8.9474% / 11.3752%, so it is not a replacement default.
The additional fraction-0.25 / 250-kHz full-chip trial retains lock through both
traffic cases but gives 9.3193% / 11.3165% error. No limit is relaxed.

A separate 12-case staged screen combines two carriers, six filter settings and
the declared 20-kHz RMS finite frequency noise. All maintain reference-edge lock;
phase-only errors are ~4.2–5.1%. This is not a substitute for supply-coupled full
traffic, nor an intra-reference waveform qualification.

TX screens now preserve complex output, baseband, rotation and time arrays in
compressed NPZ files. tx_trace_diagnostics.py performs offline analysis without
rerunning analog dynamics. On the quarter/250-kHz traces, an exact orthogonal
error decomposition gives training-to-validation gain shifts of 8.50% / 10.82%
and within-validation residuals of 3.83% / 3.33%. Their squared sum equals the
original held-out error squared. The held-out fitted gain is an oracle diagnostic,
not a permitted replacement for training or a passing gate. A training-only
linear frequency fit worsens mode 0 rather than repairing it. Investigate burst
startup/load transients and calibration-window sensitivity; do not simply remove
the gain shift in postprocessing. This complements the prior noise/pulling
isolation results and may justify an explicit supply-isolation or startup design.

Evidence: both fractional-grid trial reports/logs, both TX filter trial reports,
staged-clock-filter-candidates source/report/log, saved traces and their phase
reports. Post-run hashes are in filter-trial-verification.json. All runs above
are terminal. The default remains 0.5 at 300 kHz; strict TX qualification is still
failed, and the 129-scenario aggregate has not been rerun.

### Matched host-preconditioning experiment identifies startup-load sensitivity

Saved traces were plotted and visually inspected against the actual training
window and first nonzero TX envelope. Repeating phase structure remains beyond
startup; the problem is not simply a constant carrier offset. The plot source,
PNG and numerical bins are retained as tx_phase_window_plot.py and
 tx-startup-phase-windows.{png,json}. Optional plotting dependencies are isolated
in a temporary virtual environment, not added to the simulation requirements.

On the 0.35/300-kHz candidate at 2437 MHz, equal 20-us extensions give 11.5969% TX
error after quiet waiting and 9.3428% after valid empty host frames. Both retain
the same noise/forcing and start observations at the same time. The switching
prelude sends 64 complete zero-allocation frames with pseudorandom ignored slots,
wraps sequence to zero, and verifies unchanged RF/wired sample consumption.
Observed supply-event count increases by exactly 4096; both select bank 15 and
retain the same maximum modeled RF pull (~79.6 kHz). No analog state is reset,
and observer-only prelude records are excluded from the measured burst.

This is evidence of host-activity startup sensitivity, not authorization to drop
cold-start qualification or silently require a warm link. A controlled host-link
activation sequence or explicit supply-isolation design must be implemented and
checked across modes, startup/recovery/idle transitions and noise phases before
promotion. Neither the default filter nor quality/lock limits are changed.
Evidence: connected-tx-host-{quiet,switching}.json, matching logs, saved traces,
phase diagnostics and tx-host-preconditioning-comparison.json. Source/artifact
hashes are retained in tx-preconditioning-verification.json. Both runs are
terminal; no fresh aggregate pass is claimed. See tx-waveform-diagnostics.md.

### Counted host activation and expanded startup timing

Additional conditioned tests pass: mode 0 at 8.0944%, and mode 1 delayed by
1/2/3 us at 4.0804% / 4.3396% / 4.8815%. The earlier mode-1 zero-offset result
of 9.3428% remains the worst of these finite points. No arbitrary seed/activity
or phase envelope is inferred.

HostActivationChip now adds explicit management arm/status/abort and a 64-frame
monitor. RF/wired starts reject before qualification. Tests pass low-activity,
payload, stale-epoch, duplicate-arm and clock-gap rejection, partial-start guards,
exact timeout quiescence, reference loss and drain-without-requalification.
The modeled per-edge timing check and activity/idle bounds are provisional, not
an implemented physical timing monitor. This is a streaming candidate; it does
not replace the SPI-only path or the main candidate.

Both-mode independent TX tests with the controller reproduce 8.0944% / 9.3428%.
Saved output arrays and times are exactly equal to the corresponding unguarded
preconditioning fixtures, demonstrating that the controller introduces no hidden
analog reset or waveform correction. See connected-host-activation.json,
connected-tx-managed-host.json, matching logs and host-activation-comparison.json.
A new run requires both RX and TX quality on the same composed candidate; it is
still running. 130 scenarios are registered; no aggregate pass is claimed.
Contract: host-activation-candidate.md. Main defaults and cold-start failure
records remain unchanged pending broader qualification and a realizable monitor.

The composed RX/TX run is now terminal and passes both gates: mode 0 TX/RX
8.0944% / 7.7492%; mode 1 TX/RX
9.3428% / 6.9680%. Both use the counted host activation, coarse tuning,
I/Q calibration and full declared loading/noise/traffic. Evidence is
connected-managed-host-duplex-quality.json and matching log; post-run hashes are
in managed-host-verification.json. The runner registers this strict dual-quality
case (131 scenarios total). This finite candidate pass does not remove the old
cold-start failure, establish the physical monitor, or qualify TX emission images.

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

## Live corrected TX output integration — 2026-09-21 (run pending)

Added an optional live output profile to the independent-carrier quality harness.
The candidate corrects actual DAC sample values at their selected bit width before
physical DAC transfer and reconstruction. Independent TX observation then applies
0.25 dB gain imbalance, 2 degree phase error, 0.0025 normalized LO feedthrough and
cubic coefficient 0.06 to the live baseband/clock state. The matched ideal path
has reconstruction but neither these output impairments nor correction. RX/TX
quality thresholds are unchanged. Existing observer controls pass.

Mode1 full traffic run launched with managed host activation, 0.35 fast-capacitor
fraction and elliptic reconstruction. Session56695 and log
/tmp/svalbard-live-tx-output-mode1.log identify the run; inspect terminal status
and report before claiming success. Source hashes are retained in
live-tx-output-run-source.json. This pending run is not registered as a passed
aggregate case.

Calibration coefficients currently come from independent instantaneous noiseless
fixture probes, with finite coefficient precision. This isolates the live sample
and output integration; it does not replace managed finite-time calibration.
Output distortion is a one-way observation stage without supply/load feedback
or physical RF isolation. Existing phase/baseband diagnostic substitutions omit
output-stage distortion and are not an additive error decomposition of this run.

## Live output result and nonlinear detector expansion — 2026-09-21

Mode1 live corrected output-stage run completed successfully with unchanged limits:
TX 9.4876%, RX 6.9680%, finite-burst out/in ±10 MHz power −38.5704 dB.
All recorded launch source hashes match current source. This is the separate
ideal-measurement calibration fixture, not the managed finite-detector candidate.
Mode0 equivalent run is active under session18333, log
/tmp/svalbard-live-tx-output-mode0.log; no mode0 result is claimed yet.

Added `tx_output_terms.py`: exact exponential expansion of the widely-linear
modulator, leakage and cubic envelope. This permits the finite-bandwidth power
detector to observe the same nonlinear model without stepping an RF carrier.
Independent pointwise waveform and numerical detector quadrature checks pass:
maximum waveform disagreement 1.67e-16, detector error 1.73e-15; 17-way temporal
subdivision differs 7.63e-17. The tested reconstruction transient expands to70
terms. No truncation/rounded pole merging is used.

The polynomial remains valid only within the declared weak-compression envelope;
this expansion does not establish that bound for arbitrary stimuli. Managed
nonlinear calibration, monitor loading and physical RF output qualification
remain open. The high-risk full-chip clock margin is still narrow despite the
passing mode1 fixture case.

Mode0 run is now terminal: passed. TX error 0.08287673262159817, RX error 0.07746139202997078, out/in power -42.71368219412758 dB. Both live fixture cases are complete; managed finite-detector integration remains open.

## Managed nonlinear TX quality integration — 2026-09-21 (pending)

Joined managed TX calibration with host activation and live independent output
observation. Finite detector probes now include the same cubic output expansion
as the live output stage. Both-mode managed command/activation regression passes
after this substitution (log /tmp/svalbard-nonlinear-managed-calibration.log).

First quality attempt terminated before traffic: calibration was still settling
at25 us after submission because serialized start delivery consumes about6.45 us
before the18.9 us sequence. Preserved failure log at
/tmp/svalbard-managed-tx-quality-mode1-short-window.log. Revised preparation uses
an equal50 us window for ideal and actual, checks ready at30 us, and allows the
serialized commit/reply to finish. Extended independent RF source to14000 samples
to cover the longer preparation; no signal-quality thresholds changed.

Revised run session16204 is active; log /tmp/svalbard-managed-tx-quality-mode1.log.
Source hashes and launch state are in managed-tx-quality-launch.json. No live
managed quality pass is claimed until terminal results are inspected. Independent
monitor ADC, RF output isolation, detector uncertainty/loading and residual
verification remain incomplete even if this finite quality case passes.

## Managed mode1 quality and resource-discovery gap — 2026-09-21

The revised managed finite-detector quality run is terminal and passes: TX error
4.6576%, finite-burst out/in power −38.5487 dB; RX also passes (see report).
The additional50 us preparation changes the oscillator trajectory, so this is
not evidence that calibration alone improved the earlier9.49% result. Preserve
matched-timing comparison before attributing the improvement. Mode0 managed
quality remains untested.

A separate ownership audit found that resource discovery reported the DAC idle
while TX calibration was actively driving probes. Preserved that negative result
in connected-tx-resource-audit-before.json. Added owner11 for TX calibration on
DAC resource1, sequencer8 and newly explicit power-monitor resource10; experimental
resource count is11. This makes the assumed independent monitor ADC visible;
it does not justify its area/power or resolve sharing with the I ADC. The quality
result predates this reporting-only patch and its launch hashes remain preserved.

## Managed mode0 failure and mode1 correction control — 2026-09-21

Mode0 managed quality attempt terminated at TX-calibration start: command applied
at162.15 us rejected the quiet/empty/qualified-lock admission condition. No mode0
waveform quality was measured. Preserved failure traceback and structured report;
do not treat the earlier separate fixture pass as a managed-calibration pass.
Next discriminate which readiness input failed and its time history, then define
bounded observable acquisition/wait behavior without relaxing lock thresholds.

The mode1 correction-bypass comparison is still active under session52020, log
/tmp/svalbard-managed-tx-uncorrected-mode1.log. It executes identical calibration
probes/commands and timing but deliberately bypasses only normal sample correction.
This is a diagnostic experiment, not a user profile. Comparison script checks
identical observation times, ideal waveform, experiment settings and measured
calibration before reporting errors and carrier differences. No comparison result
yet. Source hashes are in managed-tx-followup-launch.json.

Mode1 bypass comparison is now terminal: both runs pass, with identical times,
ideal waveform, measured calibration and actual carrier rotation arrays. Correction
reduces TX error from6.0416% to4.6576% in this matched experiment. This supports a
correction benefit for this finite case; it does not resolve mode0 readiness or
broader startup/noise/phase coverage.

## Mode0 readiness diagnosis and bounded polling — 2026-09-21

The exact failed setup was reproduced with read-only readiness snapshots. At
162.15 us execution, quiet/reference/coarse qualification were true and the DAC
queue empty; PLL lock was false. First sampled lock was169.55 us (0.5 us sampling
interval, not an exact crossing). Fractional retarget resets lock qualification;
a fixed early start is therefore insufficient in this noise/phase realization.

Added readiness bit10 to TX calibration status and a bounded serialized polling
preparation. Status does not authorize a later start: start still checks current
readiness at execution. Polling stops with timeout if readiness remains absent at
a completed poll after50 us; one management transaction can cross that boundary.
The overall matched ideal/actual preparation budget is100 us, checked explicitly.
Independent source length increased to18000 samples to cover that window.

Revised mode0 run session8539 is active, log
/tmp/svalbard-managed-tx-lockwait-mode0.log; launch hashes are recorded. Earlier
mode0 failure and mode1 timing profiles are preserved. No revised quality pass
is claimed before terminal results. This is bounded host preparation, not a
physical guarantee of PLL acquisition across parameter uncertainty.

## Readiness-poll mode0 terminal pass — 2026-09-21

Mode0 now completes managed calibration and full traffic under the100 us matched
preparation policy: TX error8.3222%, RX6.1928%, finite-burst out/in power−42.7035 dB.
Recorded launch source hashes match. Original rejected-start evidence remains.
A synthetic serialized-transport test of the actual preparation callback passes
missing-readiness timeout, execution-time start/commit rejection, unfinished-fit
rejection and overall budget overrun. These are policy checks, not physical clock
qualification. A slow transaction may finish a commit before the overall-budget
check rejects preparation; no traffic is then started, and rollback is not claimed.

Mode1 is being run under the same100 us polling policy, log
/tmp/svalbard-managed-tx-lockwait-mode1.log. Prior mode1 passes used a different
50 us preparation window and cannot substitute for this run. Internal monitor
loading/uncertainty, RF output isolation and broad operating-envelope closure
remain outstanding.

## Both-mode readiness policy and detector transfer — 2026-09-21

Mode1 under the same100 us preparation policy now passes with TX error9.5586%
and out/in power−38.5621 dB; RX also passes. Mode0 was8.3222% TX. This restores
consistent both-mode evidence but exposes how narrow clock/phase margin remains:
the earlier50 us mode1 profile yielded4.6576%, not a robust universal improvement.

Added optional detector-readout gain/offset/quadratic curvature following the
finite square-law filter. Both upper and lower rail crossings invalidate ADC
samples rather than silently clamping and fitting them. A27-case local assumed
transfer sweep rejects9 negative-offset cases; remaining independent multitone
errors span0.0930–0.2460%. This is a detector/calibration-only local check without
whole-chip clock error. Parameters are assumptions and the transfer model is not
yet wired into the full-chip candidate. Shared monitor loading and RF isolation
remain open. No full aggregate regression or mathematical closure is claimed.

## Managed clock-margin reassessment — 2026-09-21

Saved-trace orthogonal diagnostics show the100 us mode1 result has8.900% training
to validation complex-gain shift and3.488% within-validation residual. The earlier
50 us mode1 result has1.763% shift and4.311% residual. These use an oracle validation
gain only for diagnosis; qualification still uses training alone. Dominant finite
phase bins lie near0.43–0.57 MHz. They do not identify a device noise source.

A new averaged sensitivity calculation applies the exact declared eight250 kHz
spaced frequency-noise lines to the two-capacitor loop. Current0.35 fraction gives
0.04435 rad RMS, close to observed0.04395 rad phase RMS, but that agreement alone
is not causality or physical validation. Smaller fractions predict lower noise,
yet their prior acquisition failures remain constraints; do not optimize solely
for this averaged variance. Supply and fractional effects are excluded here.

Two live managed mode1 isolation runs launched with unchanged correction and
preparation: oscillator noise disabled (session70320, log
/tmp/svalbard-managed-tx-no-noise-mode1.log) and supply pulling disabled
(session45008, log /tmp/svalbard-managed-tx-no-pulling-mode1.log). Both were
confirmed live after launch. They are diagnostics, not relaxed qualified profiles;
inspect terminal evidence before attributing the remaining margin.

## Clock isolation terminal results and intermediate filter trial — 2026-09-21

Both mode1 isolation runs completed. With the same managed preparation and
correction, full forcing gives9.5586% TX error, oscillator-noise removal2.9387%,
and RF supply-pulling removal7.7132%. These controlled removals identify the
assumed oscillator-noise response as a high-value target; they are not additive
variance budgets and do not qualify zero-noise hardware. Reports and hashes are
consolidated in managed-tx-clock-isolation-summary.json.

Testing fast capacitor fraction0.30 at unchanged300 kHz loop design, between the
current0.35 and previously problematic0.25. Averaged phase margin improves from
24.17 to29.10 degrees, peak sensitivity2.528 to2.144, and predicted finite-noise
phase RMS0.04435 to0.03999 rad. These modest predicted gains need sampled-loop
and acquisition evidence. Full-noise managed mode1 quality is running in
session33634 (/tmp/svalbard-managed-tx-fraction30-mode1.log); independent201-point
nominal acquisition grid is session76206 (/tmp/svalbard-fractional-grid-fraction30.log).
No defaults changed, and neither trial is yet qualified.

Registered both existing0.35 managed readiness-poll quality cases in the unified
runner. This registers reproducible checks; no fresh aggregate pass is claimed.

## Intermediate filter result and closure inventory — 2026-09-21

Fraction0.30 mode1 full-noise managed run is terminal and passes: TX8.6509%,
RX6.5963%, out/in power−38.3602 dB. This improves on fraction0.35 TX9.5586%
in the tested trajectory but is not yet a robust tuning/uncertainty result.
The201-point nominal grid (session76206) remains active, last observed through
2380 MHz. Mode0 full-noise followup launched with log
/tmp/svalbard-managed-tx-fraction30-mode0.log. Defaults remain unchanged.

Reconciled mathematical-closure inventory with current managed evidence and
150 registered runner cases. All requirement groups remain partial; the last
verified full aggregate remains pass876. Recorded evidence hashes in
managed-tx-closure-audit.json. Remaining signal-quality margins, monitor budget,
output isolation and unified recovery cannot be inferred from local green checks.

## Direct retarget validity audit — 2026-09-21

A direct same-frequency carrier retarget resets divider/PLL qualification but
retains the TX calibration valid flag. After30 us reacquisition, TX admission
succeeds without a new calibration generation. The managed coarse-retune path
invalidates calibration, so direct and managed mutation policies are inconsistent.
Preserved the observed result in connected-tx-retune-validity-before.json.
This does not prove the static I/Q correction numerically changes after every
same-frequency retarget; it identifies missing explicit provenance policy.
Planned conservative rule: successful direct RF retarget invalidates calibration;
rejected operations must retain it. Keep in-flight quality sources frozen until
terminal before applying the patch.


Mode0 fraction0.30 quality is now terminal and passes: TX7.3866%, RX5.9864%.
Together with mode1 TX8.6509%, this improves the two tested trajectories, while
nominal grid session76206 remains active. No default filter change yet.

After the quality process completed, patched successful direct carrier retargets
to invalidate TX calibration. Regression passes: rejected unqualified retarget
preserves validity; accepted same-frequency retarget invalidates; later lock
recovery alone does not restore TX admission. Both prepatch and postpatch evidence
remain. This addresses that mutation path, not all configuration provenance.

## Intermediate filter nominal grid complete — 2026-09-21

Fraction0.30/300 kHz nominal grid completed:201/201 sustained qualifications,
no unqualified targets. Both previously terminal managed quality cases pass at
TX7.3866%/8.6509%. Recorded an explicitly unpromoted experimental profile with
report hashes in spec/experimental-managed-tx-profile.json. Default classes and
existing qualification limits are unchanged.

A staged12-case comparison now runs two carriers × three oscillator-noise seeds
× fractions0.35/0.30, session96911, log/tmp/svalbard-pll-fraction-seeds.log.
This isolates noisy acquisition and is not full-chip RF quality or broad PVT.
Reference-loss recovery, monitor loading and physical RF isolation still prevent
promotion to a closed whole-chip model.

Noise-seed comparison is terminal: 12/12 cases sustain qualification. See connected-pll-fraction-seeds.json for all outcomes; no full-chip/noise-envelope conclusion follows from this staged acquisition test.

## Combined candidate reference-loss recovery — 2026-09-21 (running)

Added a recovery test on ManagedTxHostChip at fraction0.30, with actual managed
coarse tuning, finite TX calibration, both host training modes and RF DAC/capture
activity. The0→1 direction completed: three DAC updates before loss and three
after recovery, no pending updates, new epoch1 and calibration generation4.
Nonzero reconstruction state (modal norm0.5611) survives the same-time reference
loss; old calibration commit rejects and host activation must be redone.

The1→0 direction remains in process session15151, log
/tmp/svalbard-managed-tx-recovery.log. Source hashes recorded in
managed-tx-recovery-run.json. No complete recovery pass until both directions
finish. This is a default-noise lifecycle fixture with direct internal sample
queue injection, not four-path post-recovery waveform quality or framed-payload
qualification. Physical RF isolation remains unproven despite DAC cancellation.

## Recovery terminal and managed detector readout — 2026-09-21

Combined managed recovery completed both0→1 and1→0 directions. Each produces
three DAC updates before and after reference loss, a new epoch, stale-commit
rejection and fresh host/calibration qualification. Nonzero filter modal norms
0.5611/0.5680 survive same-time reference loss. Report registered in runner;
noise-loaded waveform recovery remains untested.

Integrated optional detector readout gain/offset/curvature through constructor
options, retaining the original ideal transfer by default. A negative0.0002
normalized readout offset causes low-rail invalidation, managed cancellation,
cleared pending observation/held probe and rejected commit; targeted test passes.
Mode1 full-chain run with assumed gain1.1, offset+0.0002 and curvature+0.2 is
active under session6786, log/tmp/svalbard-managed-tx-readout-mode1.log.
It uses fraction0.30 and unchanged quality limits. These are explicit exploratory
transfer errors, not process-qualified worst cases. Detector RF loading and
supply feedback remain absent. Launch source hashes recorded separately.

## Detector uncertainty result and passive loading budget — 2026-09-21

Mode1 with explicit readout gain1.1, offset0.0002 and curvature0.2 completed and
passes at TX8.7985%, out/in power−38.4240 dB. Launch source hashes match. Fitted
baseband gain falls to0.8826; gain-normalized waveform success does not establish
absolute RF output amplitude or dynamic-range headroom.

Added a passive two-node RF pad/monitor model with finite source/load resistance,
series tap resistance, detector input resistance and retained input capacitance.
54 on/off/frequency/capacitance/resistance cases satisfy both-node KCL and real
power balance. At2.412 GHz,50-ohm source/load,1 kohm tap,50 fF input and10 kohm
enabled input, pad loss is0.08335 dB and detector/pad voltage-squared ratio0.56048.
With1 Gohm off input the remaining capacitance still gives0.07946 dB pad loss.
These are exploratory lumped values, not a circuit/package qualification.

The monitor transfer must be normalized or independently bounded before a fit can
interpret measured power as actual RF output. Bias power, package matching,
nonlinear RF detector admittance and live supply/output feedback remain absent.
Next connect this loading/measurement attenuation explicitly and test actuator
headroom rather than fitting away a hidden monitor gain.

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

## Relative I/Q gain policy — 2026-09-21

Added optional unit-determinant normalization of the I/Q correction matrix before
coefficient quantization. The offset estimate−H^-1 h already cancels scalar power
gain. This removes the otherwise unidentifiable common monitor gain from the
actuator matrix while preserving relative I/Q correction. Existing absolute-gain
policy remains the default; its finite-code regression still passes unchanged.

Local exact-power controls pass across monitor gains0.01,0.1,0.56048,1,10 with
identical quantized matrices, constant-offset immunity absent clipping, accepted
0.8+j0.8 sample and near nominal loaded-pad gain. An actual common transmitter
gain change remains uncorrected by design; absolute output regulation is still
an independent obligation. Finite ADC errors/curvature can break exact invariance.

The policy is now selectable in the managed sequencer and quality harness.
Mode1 full-chain run with finite detector, readout errors and relative correction
is active under session90773, log/tmp/svalbard-managed-tx-relative-mode1.log.
No live pass claimed yet. Monitor loading remains separately modeled, and this
policy does not establish absolute RF power or transistor feasibility.

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


## RF output isolation audit and experimental composition — 2026-09-21

Moved from calibration-fit refinement to the full RF output lifecycle. The
actual managed observer had no output-enable transfer: calibration probes reach
peak0.217225 normalized output, and stop/reference loss retain0.201824 immediate
output, decaying to0.002499999 LO feedthrough after10us. Digital stop alone did
not satisfy isolation. Failure evidence remains in connected-tx-output-isolation-audit.json.

Added experimental IsolatedTxCalibrationChip with finite first-order isolation
control,20ns assumed time constant, unit on transfer and0.001 off amplitude.
A valid first DAC completion opens the stage; quiesce closes it. Both analog
reconstruction and isolation state are retained. The common output observer
honors an optional pad transfer, preserving prior behavior for existing classes.
No full-chain profile or default candidate is promoted.

Connected calibration and three fault/stop causes (stop, reference loss,
calibration abort) pass. Calibration pad peak is0.000217225 and late output is
2.499999e−6 under the assumed attenuation. Checks assert immediate continuity,
finite exponential shutdown, nonzero leakage, unchanged filter charge and a
working internal detector. Local subdivision/retargeting and invalid-parameter
checks pass; existing TX observability counterexamples remain unchanged.
Evidence: connected-tx-output-isolation.json. Both new screens are registered;
no fresh full aggregate is claimed.

This candidate explicitly places the detector before isolation. That differs
from the diagram's pad-side monitor, so it cannot qualify final-stage gain,
loading or pad emissions. Resolve observation/isolation topology and connect
loading/current/resource use before promoting the composition. Recovery reopening,
onset waveform quality, additive bypass leakage, switching transients and
physical attenuation remain open. See spec/tx-output-isolation.md.


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


## Shared ADC detector prototype — 2026-09-21

Added SharedAdcLoadedTxChip experimentally without modifying the in-flight quality
candidate. The detector's continuous analog state feeds a callback to the existing
ADC transfer/reference path, forced12-bit precision with normal mode restored.
Declared scaling maps detector fullscale to+0.8 normalized ADC input; no oracle
monitor-gain correction. No independent detector quantizer is used. Resource0
reports TX calibration owner11; capture conflicts and preexisting ADC pending
work reject. Resource10 remains the analog detector front end.

Managed coarse start/calibration/commit passes9 shared conversions, exactly9
reference samples and2.49326pC reference charge. Concurrent capture rejects and
ownership releases after commit. Actual powers/coefficients are recorded in
connected-shared-tx-detector.json. This is the non-phase loaded adapter; mux
settling/load, conversion cancellation, phase-aware combination and independent
pad quality remain unfinished. The earlier extra-ADC quality run remains live
(session17675), so no result is silently transferred to this topology.

Registration is deferred until the frozen quality run finishes. Current runner
still177 entries; no full-chip closure or physical resource proof claimed.


## Shared ADC in-flight cancellation — 2026-09-21

A reference-loss test interrupts a nonzero shared ADC conversion after four
samples. Pending result is removed, detector epoch advances0→1, ADC resource0
releases, and stale calibration commit rejects. Detector value0.0032840 and
network norm0.118264 are retained at the interruption boundary. Advancing past
the old conversion deadline creates no new conversion or reference charge and
cannot return the cancelled result.

The first test assumption incorrectly treated the serialized start reply as
preceding the second sample; SPI response time had already crossed it. The test
now waits for an actual pending conversion and checks that boundary, preserving
real transport timing. Evidence: connected-shared-tx-cancel.json. Recovery restart,
analog mux settling and phase-aware/shared-ADC full-chain quality remain open.

Mode0 loaded-pad quality remains running in session17675 with active CPU work;
no restart or quality verdict. New screen registration remains deferred until
that frozen-source run completes. Architecture remains partial.


## Shared ADC restart and network runtime profile — 2026-09-21

After cancellation during a nonzero conversion, reference restoration and fresh
coarse search permit a new TX calibration generation3. All9 new shared ADC
samples complete and commit; old generation1 remains rejected. Resource0 releases
and no pending result remains. Evidence: connected-shared-tx-restart.json. This
is quiet calibration restart, not active traffic recovery or phase-aware quality.

A separate100-step reconstruction/nonlinear-network profile (no changes to the
running waveform job) measured0.850s under cProfile. Detector power convolution
accounts for0.549s cumulative; network exponential response decomposition0.265s,
including6525 condition-number evaluations and6625 solves. The next runtime
improvement should preserve the exponential model and validate vectorized power
convolution/batched linear algebra against the current calculation, rather than
relaxing phase steps or dropping loading dynamics. Profile artifact:
evidence/loaded-network-profile.txt. These are instrumented local timings, not
an end-to-end speedup claim.

Original mode0 loaded-pad run remains live in session17675; no restart or quality
claim. Registration remains deferred to preserve its source snapshot.


## Fidelity-preserving detector vectorization candidate — 2026-09-21

Added separate VectorPowerDetector implementing the same exponential square-law
convolution with NumPy array operations. No rates/terms are dropped and no phase
step is relaxed.20 random size/time cases, coincident-pole independent quadrature,
ADC capture/abort checks and100 actual reconstruction/nonlinear-loaded-network
steps pass. Maximum physical-trace discrepancy is6.51e−19. Median74-term local
100-step times are0.959s scalar and0.0200s vector (~47.9×). This is a local
benchmark under current machine load, not a full-chip speedup claim.

Evidence: connected-vector-power-detector.json. Candidate remains separate;
whole-chain equivalence and integration remain required before promotion. Existing
loaded-pad quality job (session17675) continues on unchanged scalar code. Source
freeze is preserved; registration deferred until that run completes.


## Managed vector-detector equivalence — 2026-09-21

VectorDetectorMixin substitutes only the detector integration kernel, preserving
the detector object, request/read implementation and controller references. The
managed loaded-calibration test matches archived scalar probe codes, correction
coefficients, three DAC updates and pad endpoints (within1e−12). Evidence:
connected-vector-loaded-tx-chip.json. A separate full phase-aware calibration
comparison is now running; default candidates and the original loaded-pad quality
job remain unchanged. This is not yet full-chain speed/equivalence qualification.


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


## Vector kernel phase-aware equivalence completed — 2026-09-21

The vector phase-aware managed calibration test completed with unchanged launch
sources. It matches scalar probe codes, correction coefficients,157556 substeps,
4951 interior events, three DAC updates and pad endpoints within1e−12. Evidence:
connected-vector-phase-loaded-calibration.json. This supports using the kernel
in experimental compositions; it is not a whole-chain quality equivalence test.

SharedPhaseLoadedTxChip now combines shared ADC, LO forcing, retargetable loaded
network and host PHY. Its managed calibration/resource test is running in
session84313 with a frozen source manifest. No result is transferred from the
independent-converter candidate. Registration remains deferred while that run is
live; full architecture and physical closure remain unproven.


## Shared phase-aware pad quality harness launched — 2026-09-21

Added shared_pad_quality.py with selected mode0/1 and the combined shared ADC,
phase-aware, retargetable loaded network/host candidate. The ideal network carrier
matches the selected target while keeping identical passive elements and source
units. Shared ADC maintenance observations are preserved separately after TX
calibration; payload RX logs then start empty, without resetting analog state.
This prevents the9 calibration conversions from corrupting RX timestamp matching.

Mode1 is running in session13439 with frozen source hashes. Its tighter historical
quality margin makes this a useful discriminating test. Combined calibration
verification remains running separately in session84313. Neither result is yet
claimed; mux analog settling, DC feedback and retuned/recovered quality remain
open. Default candidates and thresholds are unchanged.

The combined calibration run has now completed/passed:9 shared conversions,
2.49326pC reference charge,118606 phase substeps and3557 interior events. Original
source hashes match. Evidence: connected-shared-phase-calibration.json. This
qualifies the tested calibration/resource composition, not the pending mode1
traffic quality run or analog mux behavior.

### Shared-ADC mode 1 preparation failure and readout settling

The full shared-pad mode 1 run (session 13439) terminated with exit 1:
ideal traffic completed, but actual TX calibration was `cancelled` at the
pre-traffic readiness assertion. All launch-record source hashes match. No
actual mode 1 traffic-quality result exists; this is a failing integration gate,
not a quality pass. `shared_calibration_diagnosis.py` reuses the actual quality
harness and records the cancellation reason, ADC diagnostics and probe powers,
stopping before payload traffic. Diagnostic run session 14140 is pending.

The separate detector/readout two-pole screen passed against an independent
coupled ODE at 5 ns, 20 ns and 500 ns readout time constants (maximum absolute
error 4.95e-14). It preserves readout state on abort. It is not connected to the
shared ADC sampling callback yet, rejects coincident poles, and excludes reverse
mux loading and ADC kickback. Resolve the existing calibration failure before
adding this impairment to the integrated candidate.

A new local signed-readout screen exercises the existing frontend and ADC
quantizer at zero input with 0.001 RMS noise: 4029/10000 readings are negative,
minimum -0.00390625, and none clips. Thus `value < 0` in the shared detector's
invalid predicate can misclassify ordinary signed measurement noise as detector
saturation. This is a demonstrated local semantics issue, not yet the proven
cause of the pending full-chip cancellation. Preserve signed observations when
investigating fitting; clipping negative readings would introduce a bias near
zero. Screen: `detector_signed_readout_screen.py`; report:
`connected-detector-signed-readout.json`.

### Signed measurement correction

Session 14140 completed: cancellation reason `detector saturated`, one shared
ADC sample, no accepted powers, zero ADC clipping. Preserved original report
`shared-calibration-mode1-diagnosis.json`. The local negative-readout evidence
motivated removing decoded-sign from the saturation predicate; physical detector
range and actual ADC clipping still reject. SharedAdcDetector explicitly declares
signed observations. The sequence passes that declaration to the quadratic fit,
which keeps signed observations without zero-clamping; other detector types keep
their nonnegative policy. Positive curvature, conditioning and correction actuator
range checks remain unchanged.

`signed_calibration_screen.py` passes signed-pedestal invariance, invalid curvature
and nonfinite rejection, physical range/clipping rejection, signed sequence commit
and overflow cancellation. The existing `tx_calibration_sequence_screen.py` also
passes all 18 events and cancellation boundaries. Mode 1 noisy preparation is
rerunning as session 95086 with per-probe input/decoded/invalid records and a frozen
source manifest. This does not yet establish full-traffic quality.

### Finite readout connected to a separate shared-ADC candidate

`BufferedSharedPhaseChip` replaces the detector before startup, joining the
existing loaded RF network, calibration controller and actual shared ADC callback
to one `BufferedSharedDetector`. ADC request samples the finite readout state,
not the upstream ideal detector capacitor. Signed observations, conversion latency,
epoch invalidation and shared resource semantics are retained. This separate
candidate does not modify the sources frozen for session 95086.

`buffered_shared_detector_screen.py` passes finite-state sampling, busy/early
result rejection, sampled-value retention through conversion latency, abort
retention of both analog states, shared-object identity and preservation of the
two-pole advance implementation (despite the parent vectorization mixin). At
100 ns with 500 ns readout tau, detector power is 0.0157388 while sampled readout
is 0.00159210, confirming the new state is actually selected. Full startup,
calibration accuracy and traffic with this adapter still require testing. Reverse
mux loading, ADC kickback and physical parameter qualification remain absent.

### Readout bandwidth versus calibration dwell: an accuracy failure boundary

The loaded nine-probe sequence now has a separate finite-readout sensitivity
screen, `buffered_calibration_settling_screen.py`. It uses actual local TX
reconstruction/modulator and switched monitor network, with a signed 12-bit
quantizer (not the full shared-reference ADC). All five cases reach `ready`,
but independent static phase-circle scoring finds corrected errors of 0.317%,
1.424%, 17.239% and 30.015% for readout tau 20 ns, 500 ns, 2 us and 10 us at
2 us dwell. Thus readiness/fit acceptance does not certify measurement accuracy.
At 2 us tau with 10 us dwell, error falls to 0.759%; total sequence duration
increases from 18.27 us to 90.27 us. The managed harness currently waits only
20 us, so a longer dwell requires an explicit lifecycle/timing budget change.

These are exploratory local/static results, not autonomous-LO waveform or
physical feasibility claims. Next integrate either a justified readout bandwidth
budget or configurable dwell plus appropriate completion handling; do not weaken
the unchanged 10% quality gate. Report: connected-buffered-calibration-settling.json.

### Corrected mode 1 preparation and commit pass

Session 95086 terminated exit 0; all source hashes match its launch record.
Nine shared-ADC probes completed and serialized commit was accepted. First
physical detector power 9.34236735e-7 decoded to -0.0001220703125 with no clipping,
confirming the signed-noise misclassification behind the earlier failure.
The corrected sequence preserves this observation in its fit; it is not clamped.
Full original mode 1 traffic/quality is now rerunning as session 66917, with a
new frozen record `shared-pad-quality-mode1-signed-launch.json`. The prior failed
launch/evidence is retained. No full mode 1 quality result is claimed yet.

### Programmable dwell candidate

`ProgrammableDwellChip` extends the buffered-readout candidate with a proposed
`tx_cal_dwell` management operation: 80..4000 control-clock ticks, default 80
(2 us at 40 MHz). Changes require quiet/free converters and reject mutation while
calibration owns the target. `DwellSequence` feeds this configured dwell into the
existing probe event scheduler. `calibrate_until_complete` polls serialized status
and commits by generation, with a bounded deadline instead of a fixed 20 us sleep.
Timeout reports failure to the caller; recovery/abort orchestration remains to test.

`programmable_dwell_screen.py` passes tick validation, busy rejection without
mutation, and a complete nine-probe local sequence at 400 ticks/10 us dwell,
90.27 us total. This is a candidate model ABI; actual serialized transactions,
clock-loss recovery, and buffered full-chip startup/quality remain unverified.
The ongoing mode 1 quality run (66917) uses the unchanged fixed-dwell candidate;
its snapshotted sources were not edited for this extension.

### Serialized dwell timeout/restart verification launched

The new polling helper now sends a real serialized `tx_cal_abort` if its own
started calibration exceeds the deadline. Readiness timeout before start does
not abort someone else's work. Cleanup may complete after the deadline because
it traverses SPI/control timing; a rejected cleanup is reported explicitly.

`managed_dwell_recovery_screen.py` is running as session 19211 with a source
manifest. It requests 400 ticks by actual management transport, rejects invalid
settings, acquires the autonomous RF clock, imposes a short calibration deadline,
then checks shared ADC release, retained detector/readout charge and a fresh
nine-probe generation/commit using the buffered candidate. No success is claimed
until termination. The mode 1 traffic run remains active as session 66917;
its original source hash snapshot still matches after these new-file additions.

### Whole-chip priority reassessment

Updated the authoritative mathematical-closure inventory for four-path integration,
RF chain, converter/reference, management lifecycle and coexistence. All ten groups
remain partial. Current integration is SharedPhaseLoadedTxChip; its finite-readout
and programmable-dwell extension is explicitly separate. Prior independent-monitor
mode0 passes do not transfer to shared ADC mode0. Both-mode quality, continuous
service, recovery/retune and SPI-only operation must converge on one candidate.

Beyond the running quality/recovery gates, the highest missing analog coupling is
active RF driver current/output impedance and its supply response: the electrical
load currently sees prescribed Thevenin forcing. Local passive-network and
readout accuracy do not bound that feedback. Reverse mux loading/kickback and
reference behavior remain part of converter closure. Physical parameter evidence
is deferred to transistor work; missing mathematical feedback/control paths are
not. No schematic/layout readiness or aggregate pass is inferred from this audit.

### RF driver boundary power accounting

Added a read-only RMS-envelope power observer for the actual switched network.
It separately reports ideal-source power, source-resistor loss, pad/monitor/dummy
losses, both switch losses, tap loss and stored-energy rate. The screen compares
explicit branch-loss sums against the matrix-state energy derivative across all
four switch configurations and 80 transient states; maximum balance residual is
2.78e-17 W. Rotating envelope coordinates preserves source power and energy rate.

A charged internal node can return energy to the ideal source: the declared local
case gives -1.8 mW source power with declining stored energy. This is not DC power
generation or a regenerative physical driver claim. The active-driver extension
must state whether returned energy is dissipated or returned to a rail, include
bias current and finite output impedance, and then connect supply feedback.
`rf_driver_power.py` is observation only; it does not yet implement that feedback.
Evidence: `connected-rf-driver-power.json`. No current/power/area qualification.

### Exploratory active-driver/DC supply operating point

`DriverSupplyLaw` adds assumed bias current, supply-scaled finite source swing
and a nonregenerative energy policy: Pdc = Vrail*Ibias + max(Prf,0)/efficiency;
returned RF energy increases local dissipation instead of creating rail current.
It solves Vrail = Vnom - Rrail*Idc using the actual switched network's steady
loaded source power, with a declared minimum rail and no mutation of network
state. Source resistance remains the existing 50 ohms.

The local screen passes zero-signal bias droop, zero rail resistance, power
balance, switch-load sensitivity, negative-RF-power dissipation and overload
rejection. At assumed3.3V/2mA/35%/100ohm rail, switch-state DC rails span
3.01653..3.09693V for the declared input. These are sensitivity assumptions,
not physical current or efficiency estimates. The next missing connection is
transient coupled rail/network evolution and oscillator/reference response;
this DC solver is not integrated into either running whole-chip candidate.
Evidence: `connected-rf-driver-supply.json`.

### Coupled driver/network/rail transient reference

`CoupledDriver` now integrates the four complex RF network voltages and rail
voltage together. The rail changes source swing; actual loaded source power
changes driver current; current changes the rail through its RC network. This
uses the declared nonregenerative driver law and existing 50-ohm output boundary.
It is a local stiff-ODE reference with a held command, not yet the full-chip
advance implementation.

`rf_driver_transient_screen.py` passes convergence to the independent DC root,
subdivision (1.67e-14 V network discrepancy), retained voltages across output/dummy
switching, and transactional undervoltage rejection. Final post-switch rail agrees
with the DC root within6.71e-13V. Under the illustrative assumptions, changing
from dummy-only to both loads lowers settled rail3.03750V→3.01653V. No physical
precision is inferred from numerical agreement. Next connect time-varying source,
clock/reference supply sensitivity and managed events, while checking solver
accuracy/runtime and retaining physical-parameter uncertainty.
Evidence: connected-rf-driver-transient.json.

### Time-varying driver/supply forcing

The coupled driver ODE now accepts a pure absolute-time envelope callback and an
explicit integration step bound. A +3/-7MHz two-tone screen compares subdivided
intervals and a 4x finer step bound/100x tighter tolerances: network discrepancies
are2.32e-13V/2.10e-13V and rail discrepancy3.11e-12V for this finite case. A held
initial-envelope control produces a different output, confirming live forcing.
Output/dummy switching retains voltages and rail before continuing. The existing
held-input/DC convergence regression still passes.

This is numerical reference evidence, not a universal error bound. Caller must
split discontinuities and choose a step bound resolving its forcing; callbacks
must not mutate state during solver forecasts. Actual reconstruction/LO source,
detector observations and full-chip supply feedback remain to connect. Both
integrated runs (66917/19211) retain their original code snapshots; this extension
is in files added afterward. Evidence: connected-rf-driver-modulation.json.

### Managed buffered dwell recovery passes

Session19211 terminated exit0 and every launch source hash matches. Serialized
400-tick dwell configuration, autonomous RF startup, deadline/serialized abort,
ADC release and fresh-generation calibration/commit all pass. Timeout retained
detector9.40727e-7 and readout0.000157140 after2samples; generation2 cancellation
was followed by generation3 with9new samples and a committed correction. The
run used295492phase substeps and finished at281.325us simulated time. This is
quiet calibration recovery, not host payload or post-recovery waveform quality.
Evidence: connected-managed-dwell-recovery.json and its verified launch manifest.

### Actual reconstruction connected to driver/supply feedback

`reconstructed_driver_supply.advance` captures the real current reconstruction
and nonlinear modulator exponential terms into a pure solver callback, advances
the coupled network/rail, then advances TX to the same boundary. Adaptive
forecasts do not advance the reconstruction. A12-update40MS/s local test passes
against split intervals and tighter integration, maximum network discrepancy
2.88e-11V. Supply droop and nonzero pad output are observed. This closes the local
source-segment connection only: autonomous LO, detector and shared whole-chip
rail/clock coupling remain absent. No protocol or physical claim.
Evidence: connected-reconstructed-driver-supply.json.

### Detector/readout inside coupled driver ODE

The coupled driver optionally integrates detector and readout states alongside
network voltages and rail. Its forcing is actual monitor-node magnitude squared,
not requested source power; sampling/latency/epoch state stays in the existing
buffered detector object. A constant operating-point analytical cascade check
agrees within1.31e-13, subdivision agrees, a captured result survives subsequent
load switching, and abort retains network/rail/both detector states. The existing
no-detector DC/transient regression still passes.

This joins source loading, rail current and physical monitor observation in one
local mathematical state. The callback in this screen is a local readout; actual
shared ADC/reference and autonomous PLL supply feedback remain integration work.
Reverse mux loading/kickback and physical parameter qualification remain absent.
Evidence: connected-coupled-driver-detector.json.

### Shared-ADC loaded-pad mode 1 quality passes

Session66917 terminated exit0. All launch source hashes match and the report hash
is recorded. Actual and ideal traffic complete; held-out TX error8.73936% and
RX6.38613% pass the unchanged10% gate (1632TX and99RX validation observations).
This verifies the signed-readout fix through the finite mode1 traffic harness.
It does not include finite readout/supply-driver extensions, mode0 shared-ADC
quality, continuous/recovery envelopes or protocol qualification.

### Coupled-driver local calibration passes sequence; static quality characterized

Nine timed probes through actual reconstruction/nonlinear modulator, coupled
network/rail, detector and finite readout complete and commit with a local12bit
quantizer. Independent static output probes include self-consistent supply
loading; error improves3.78168%→0.334489%. This remains separate from whole-chip
quality: autonomous LO, real shared reference/ownership and timed post-calibration
playback must still be integrated. Evidence: connected-coupled-driver-calibration.json.

### Shared mode0 quality and managed coupled-driver adapter

Launched full shared-ADC mode0 quality as session25454 with source manifest
shared-pad-quality-mode0-signed-launch.json. This uses the same existing candidate
as the verified mode1 run, without the new driver/readout extensions.

ManagedCoupledDriverChip now substitutes a coupled network/rail/detector adapter
behind the existing managed TX advance hook and phase-forcing path. The inherited
autonomous LO still determines source phase; the existing shared-ADC callback and
calibration object refer to the same detector. A100ns startup check passes100phase
segments, coherent chip/TX/driver/network/detector time, nonzero detector/readout,
and local bias droop to3.100004V, without falsely claiming calibration validity.

This is wiring evidence only. Driver rail remains local: return coupling to PLL,
reference and host domains is not integrated. Full RF acquisition/calibration and
traffic on this adapter remain untested, and implicit integration per phase
segment needs measured runtime/accuracy assessment before long runs.
Evidence: connected-managed-coupled-driver.json.

### Driver-to-clock forcing interface preserves existing disturbances

The clock set_supply interface replaces its single exponential rail term; using
it directly for driver feedback would erase host-switching rail forcing. Added
an immutable DriverPulledSpectrum carrying the original intrinsic spectral tones
plus a deterministic held frequency offset. It meets the existing clock forcing
type/bound contract and preserves positive-frequency checks.

The local test verifies offset integration, retained spectrum, additive bound,
unchanged phase/filter charge on installation, and unchanged host-rail forcing.
A-200kHz driver pull gives-0.0002cycle difference over1ns while the independent
host-rail term remains-27.145kHz. This is an interface building block, not closed
feedback: causal segment updates from actual driver rail and step-refinement
checks remain required. Evidence: connected-driver-clock-forcing.json.

### Local causal driver-rail/PLL feedback

advance_feedback now holds driver frequency pull from interval-start rail voltage,
forecasts actual PLL phase/pump events for that interval, drives the coupled RF
network/rail, and commits PLL advancement. The next interval uses the resulting
rail. Existing host-rail forcing and intrinsic spectral tones are preserved.
This is a local partitioned reference, not an integration into chip event ordering.

A50ns test with assumed1MHz/V sensitivity passes coupling-step refinement:
phase discrepancy versus0.25ns is2.24e-4,9.45e-5,3.12e-5cycles for2,1,0.5ns steps.
The finest result shifts phase-0.01013cycles versus zero coupling. These expose
finite-step error rather than claiming exact integration. Acquired lock, longer
noise/supply envelopes, modulation quality and managed full-chip/reference-domain
integration remain unverified. Evidence: connected-driver-pll-feedback.json.

### Atomic coupled-feedback advancement

The local feedback adapter previously could advance its driver through an early
phase substep before a later substep failed, while leaving the caller's PLL/TX
behind. It now stages driver/network/detector and PLL states and commits them
together only after the requested interval succeeds. Existing network/detector
object identities and callback ownership are preserved. PLL forecast failure is
checked explicitly rather than silently using a failed phase prediction.

A late-failure injection after successful early substeps leaves original driver
and PLL serialized state unchanged; a success commits aligned times and retains
network identity. The existing phase-step convergence screen also passes after
this change. This is a local transactional boundary, not managed recovery proof.
Evidence: connected-driver-feedback-transaction.json.

### Managed driver-to-RF-PLL feedback connected

ManagedDriverFeedbackChip overrides the existing TX network callback with the
transactional driver/PLL feedback step. It retains the declared RF TX phase offset,
requires oscillator history alignment, and preserves shared detector/network
object identities. Driver rail now causally pulls RF PLL phase in the managed
advance path, rather than only in a separate fixture.

A150ns startup/reference-loss test passes aligned chip/TX/PLL/network/detector
times, zero unintended ADC conversions, phase continuity at reference loss, and
cancelled calibration with no pending detector result. Coupling versus zero
sensitivity changes final phase-0.027899cycles with assumed1MHz/V. This is short
integration evidence, not acquired-lock/calibration/traffic qualification. Shared
converter reference and other rail domains remain separate; longer convergence,
source uncertainty and full lifecycle testing are required. Evidence:
connected-managed-driver-feedback.json.

### Full managed feedback acquisition/calibration launched

Measured existing startup/reference-loss screen runtime2.77s for two150ns cases;
this is a rough scaling indicator, not a full-run prediction. Launched
managed_feedback_calibration_screen.py as session5504 with frozen source hashes.
It uses actual coarse-search command transport,50us acquisition, readiness
polling, shared-ADC calibration/commit and checks reference loading/resource
release with driver-rail feedback into RF PLL. Solver fidelity and1ns coupling
step remain unchanged. A bounded150us calibration timeout reports failure rather
than claiming readiness. Mode0 quality continues separately as session25454.

No acquisition/calibration success is claimed until terminal verification.
Direct driver-rail/reference-voltage coupling and payload waveform quality remain
outside this new test even if it passes.

### Driver-sensitive converter reference candidate

DriverSensitiveReference adds a piecewise-linear driver-rail contribution to the
reference RC target while retaining existing ADC/DAC charge impulses and counters.
Rail-segment changes preserve reference voltage; future target/rail excursions
outside the declared model reject. Independent ODE comparison agrees within
1.18e-12V and subdivision agrees; zero sensitivity reproduces10ADC/10DAC updates
and total charge of the original reference model.

This is a local response primitive, not a live chip connection. Linear supply
sensitivity remains assumed; physical dropout/current limiting/PSRR dynamics and
reverse reference-current loading on the driver rail are absent. Integrating it
requires causal driver segments without sampling future rail state or resetting
reference charge. Evidence: connected-driver-reference.json.

### Actual driver trajectory connected to loaded reference

A local staged driver/reference adapter now solves driver-rail endpoints and
advances the reference with their piecewise-linear interpolation; ADC/DAC impulses
split intervals and retain their existing charge laws. A200ns two-tone test with
8ADC and8DAC events shows reference refinement discrepancies5.24e-7V at2ns and
1.27e-7V at1ns against0.25ns. Under assumed0.05V/V sensitivity, final reference is
0.962548V versus0.972126V with zero coupling; final driver rail3.053744V.

This closes a local feedforward connection only. Reference current does not load
the driver rail, and PLL/managed event integration remains separate. Numerical
refinement is not physical accuracy or a whole-chip operating guarantee.
Evidence: connected-driver-reference-connection.json.

### Reference buffer energy boundary verified

Reference buffer accounting now separates RC-source power, series-resistor loss,
reservoir energy rate and nonregenerative supply/bias draw. Source/sink/zero-error
cases balance and keep dissipated power nonnegative. Existing ADC impulse energy
matches V*Q-Q²/(2C) (4.73872e-13J for the declared sample). This makes explicit that
conversion charge is removed from the reference reservoir and subsequent buffer
replenishment draws supply energy; directly charging the same impulse to the
supply again would double-count it.

The accounting primitive is not yet a live rail load. Bias/efficiency remain
assumed, and amplifier headroom/current limiting/PSRR dynamics need refinement.
Evidence: connected-reference-buffer-power.json. Feedback acquisition run5504
has qualified coarse RF search and is continuing through calibration; mode0
quality run25454 remains active.

### Two-way reference-buffer/rail transient

ReferenceRail now integrates reference voltage and rail voltage together: rail
sets the reference target, buffer replenishment draws rail current, and converter
impulses remove reference charge without directly duplicating supply draw.
Analytical DC endpoints3.09V rail/0.9895V reference and subdivision checks pass.
An ADC event leaves rail continuous; subsequent replenishment lowers it to
3.089707V before recovery, preserving the sample count and reservoir charge.

This local test prescribes2mA other load. The final implementation must combine
actual nonlinear RF driver current, PLL forcing and reference into the same rail
state rather than stacking independent supply models. Bias/efficiency/PSRR are
assumed; dropout and current limits remain unmodeled. Evidence:
connected-reference-rail-feedback.json.

### Shared-ADC mode0 full finite traffic passes

Session25454 terminated exit0; all source hashes match and report hash is recorded.
Mode0 TX error7.53532% and RX6.05790% pass the unchanged10% gate with1632TX and
246RX validation observations. Together with mode1(8.73936%/6.38613%), both modes
now pass finite matched-pad/shared-ADC traffic on SharedPhaseLoadedTxChip.
The driver/readout/PLL/reference extensions remain separate and cannot inherit
this quality result. Continuous, retuned/recovered and SPI-only coverage on the
final composition and a fresh aggregate remain required.

### Managed driver/PLL feedback acquisition and calibration pass

Session5504 terminated exit0 after354.27s wall time,127.125us simulated time and
128300feedback steps. All launch source hashes match; report hash recorded.
Autonomous coarse acquisition, readiness polling, nine actual shared-ADC reads,
calibration commit and resource release pass. Shared reference charge increases
2.44442pC. Driver rail is3.099995V at completion. No payload waveform is scored.

Updated authoritative inventory with both-mode finite traffic results and this
separate feedback extension. Next consolidation must place nonlinear driver,
reference-buffer replenishment and reference voltage on one rail state; preserve
ADC/DAC impulse timing, object ownership and existing host/clock disturbances.
Then recheck managed calibration/recovery and both-mode payload quality. Do not
infer those properties from separate local passes. All ten groups remain partial.

### Driver and reference now share one rail ODE

CoupledDriver optionally integrates reference voltage alongside RF network,
detector/readout and rail. Actual reference-buffer current is subtracted from
that same rail; rail sets the reference target. Existing conversion impulses stay
on the reference reservoir. The PLL feedback staging now copies/commits reference
state while preserving the caller's reference identity.

The local unified screen passes zero-RF analytical DC endpoints, subdivision,
ADC/DAC impulse counts with continuous rail voltage, subsequent replenishment
droop and reference identity/time preservation through PLL feedback. The previous
transactional failure regression still passes. Managed converter-event ordering
is the next integration boundary; no prior whole-chip quality result transfers.
Evidence: connected-unified-driver-reference.json.

### Managed unified reference connected; acquisition/calibration launched

ManagedUnifiedReferenceChip binds ADC, DAC and coupled driver to one reference
object. Continuous reference advancement is restricted to the shared analog ODE;
converter kernels can sample/load it only at the solved timestamp. Short managed
advance/reference-loss checks plus direct ADC/DAC kernel calls pass, with retained
shared identity and counters. This is not scheduled converter traffic evidence.
The adapter explicitly requires shared-reference configuration.

Launched actual serialized acquisition/calibration with this candidate as
session55816 and froze source hashes. It must pass coarse qualification, timed
shared ADC sequence/commit, reference loading and resource release before further
promotion. No result is claimed yet. Evidence for the short boundary check:
connected-managed-unified-reference.json.

### Unified-state rollback and ownership regression

A new transaction screen begins with an already charged ADC/DAC reference and a
pending detector conversion. Failure after early successful substeps preserves
all original serialized state and public identities. Success preserves pending
sample, reference charge/conversion counters and object identity while updating
all clocks coherently. Evidence: connected-unified-feedback-transaction.json.
The consolidated state/equation/ownership contract is now documented in
spec/unified-analog-state.md, explicitly separating this candidate from prior
both-mode traffic passes and retaining outstanding closure obligations.

### Shared-reference aperture ordering sensitivity

A local unified rail/reference sweep covers DAC update1ns before ADC, coincident
DAC-first,1ns after ADC, and coincident ADC-first. With the declared conversion
values/load, tie ordering changes normalized ADC I by0.00131997 (2.7033LSB at
12bits). Final coincident reference charge/rail agree across tie orders even
though captured ADC values differ, so final-state checks alone miss this effect.

Current source nesting places timed_lifecycle.complete_dac in the superclass
advance before rf_return_lifecycle samples ADC at the same timestamp. This is
an event convention, not physical aperture proof. Preserve it in scheduling
regressions and qualify finite skew/kickback, rather than silently switching
order to improve results. Evidence: connected-unified-aperture-order.json.

### Converter dispatcher tie ordering verified

An explicit exact-time tie fixture on the inherited PlaybackChip dispatcher
records DAC transfer before ADC sampling in both modes. A first attempt using
nominally coincident clock requests did not create an exact tie because actual
clock phases differ; the final fixture records the natural aperture separately
and explicitly injects the dispatcher boundary under test. This verifies software
ordering only, not physical timing or unified analog traffic. Evidence:
connected-converter-tie-order.json. Real finite-skew sensitivity remains required.

### Unified payload-quality harness prepared

unified_pad_quality.py selects ManagedUnifiedReferenceChip in the existing
matched-pad harness, retaining both mode targets,18000source samples,32-frame
profile, original impairment/noise/blocker/reference settings,100us preparation
window, host activation and unchanged10% held-out gate. The ideal branch remains
the original ideal carrier/modulator with the same passive pad network: driver
compression and coupled supply effects are not normalized away. Reports include
feedback-step count, actual driver rail and coupled reference voltage.

The new harness compiles; it has not run or passed. Wait for the ongoing unified
acquisition/calibration result before starting its long actual-traffic phase.
The older shared-ADC both-mode passes remain separate evidence, not a pass for
this candidate.

### Unified acquisition/calibration passes; full quality launched

Session55816 terminated exit0 after406.12s wall time,127.125us simulated time and
128300feedback steps. All launch source hashes match and report hash is recorded.
Coarse acquisition, actual9-sample shared-ADC calibration/commit and resource
release pass with reference-buffer replenishment current on the same driver rail
and driver-rail pulling of RF PLL. Reference charge increases2.41485pC; final rail
is3.089995V. This quiet run does not prove payload waveform quality.

Launched unchanged-criteria unified_pad_quality.py --mode0 as session58376 with
frozen source manifest unified-pad-quality-mode0-launch.json. The existing
both-mode shared-ADC quality evidence remains the baseline, not a substitute for
this new coupled candidate's result. No full architecture completion is claimed.

### Unified rail-envelope rejection verified

A new sweep checks both sides of the assumed2.5V rail floor using100ohm rail
resistance:2/6mA driver-bias cases advance to3.09/2.69V, while10/20mA cases reject.
Rejected solves preserve the entire charged reference and pending detector state.
The overloaded case also preserves driver plus PLL state through transactional
feedback advancement. Evidence: connected-unified-rail-failure.json.

These are declared numerical-domain limits, not GF180 current capability. Solver
rejection is not an on-chip brownout detector, detection latency or managed
fault/drain behavior; those must not be inferred from rollback. Unified mode0
quality session58376 has completed ideal traffic and is running actual traffic.

### Internal reference-monitor ownership check launched

The inherited reference monitor calls reference.advance(time). The unified
reference permits only an already solved timestamp, so monitoring must follow
coupled analog advancement and must not independently extrapolate state.
Launched unified_monitor_boundary_screen.py as session48212 with source snapshot:
serialized route selection/status, read-only current-time observation, rejected
future-time observation without mutation, and no false monitor validity or
converter activity during quiet startup. Active monitor cadence/transport remains
outside this boundary test. Unified payload run58376 continues unchanged.


### Unified monitor ownership and active transport follow-up

The quiet serialized reference-monitor boundary test completed successfully (session 48212). All 342 recorded source hashes were verified before marking its launch manifest terminal_passed. Current-time observation leaves reference state unchanged; a future-time read is rejected without mutation, and quiet status does not assert sample validity. This does not qualify active diagnostic transport. A new two-mode unified-monitor transport test is running as session 9606, exercising tile/ADC/host delivery and reference-loss invalidation. Unified mode-0 pad quality remains running as session 58376; no result is claimed. All mathematical closure groups remain partial.


### Unified reference repetitive-load sensitivity

New four-case local sweep completed (session 88888), with tolerance refinement below 2.6e-9. For 2 pF conversion load, a 4x reservoir increase improves minimum reference voltage but leaves sampled gain near 1.131. This is evidence to prioritize buffer drive and charge budgeting, not a signal-quality pass. See connected-unified-reference-envelope.json and unified-analog-state.md. Full quality session 58376 and active monitor transport session 9606 were polled and remain live.


### Reference drive budget and monitor setup correction

Reference drive budget completed with numerical refinement and independently checked fixed-rail recurrence (session 13073). Initial session 35650 incorrectly required the fixed-rail approximation to match a rippling coupled rail; the revised test checks the recurrence in its actual domain and reports approximation error. Active monitor session 9606 failed before traffic because coarse acquisition was omitted; original source hashes verified and terminal failure retained. Setup now performs real coarse acquisition before mode configure. No monitor-transport pass is claimed.


### Finite reference source/sink drive

Added current_limited_reference.py and its local energy/conversion screen. Session 3280 completed: 50 uA collapses the reference under the selected load, while 150/600 uA retain roughly 2.4/2.3 percent sample gain error. Energy and refinement checks pass; physical feasibility and unified integration remain open. Full quality 58376 and acquired monitor transport 24007 were polled and remain live. This is progress on an omitted constitutive limit, not full-chip closure.


### Finite-current law integrated into unified ODE

New ManagedLimitedReferenceChip preserves the shared analog objects and uses finite buffer current in the RF/network/reference/rail derivative. Short managed impulse and failure-rollback screen passed (19568). Acquisition/calibration running (74592), sources snapshotted. Existing baseline full quality 58376 and monitor transport 24007 remain live. No promotion to transistor/layout closure.


### Baseline equivalence and whole-chip risk reassessment

Nonbinding finite-reference limit exactly matches baseline network, detector, rail/reference and RF PLL states through four switch configurations and conversion impulses (33827, connected-limited-baseline-equivalence.json). Running handles 58376, 24007, 74592 all verified live. Refreshed stale RF/reference/coexistence closure rows; all ten groups remain partial. Current priority is results on the unified composition, then both-mode quality/lifecycle and bounded clock/host service; do not spend further turns tuning reference alone without integrated evidence. Wired load envelopes, sustained queue bounds and fresh aggregate remain required alongside RF work.


### Monitor acquisition resource interlock

24007 terminated: coarse start rejects monitor_route != 0 through CalibrationChip.quiet. Verified all launch source hashes; kept failure. New ordered test 6718 starts/qualifies coarse search before enabling monitor/diagnostic routes. No bypass of ownership checks and no transport pass claimed. Full quality 58376 and limited calibration 74592 remain running.


### Preflight caught missing host training

Static review of HostActivationChip.capture proves ordered monitor test 6718 would reject capture without host training. Its process was explicitly terminated (143), source hashes verified, and reason retained; this was not a timeout restart. New test 65541 performs real 64-frame switching training via the existing conditioner and asserts current-epoch readiness before capture. It retains coarse acquisition before monitor routing. Baseline full quality 58376 and finite-current calibration 74592 remain live.


### Reject invalid starting reference state

Reproduced final-only domain check admitting 0.09 V initial reference and committing recovery. Separate GuardedLimitedDriver rejects invalid initial reference transactionally; finite valid recovery remains. Guard integration into managed entry remains pending frozen runs, not claimed complete. Current runs 58376, 74592, 65541 verified live.


### Finite-current calibration verified; guarded mode1 quality

74592 passed acquisition and nine-observation shared ADC calibration; all 351 launch source hashes verified. New ManagedGuardedReferenceChip integrates entry-state guard. Full mode1 quality launch 68078 had duplicate resistance keyword from profile expansion; corrected to explicit post-expansion parameter override and launched 88046. Same traffic and held-out quality criteria retained. Baseline mode0 58376 and monitor 65541 remain live. No payload pass claimed.


### Unified mode0 traffic failed; initiating fault diagnosis

58376 terminal failed at 326.052 us: TrafficFault reporting host activation missing or expired. All 340 launch source hashes verified. No waveform quality pass/report was produced. HostActivationChip.feed first advances analog state; a preceding quiesce can invalidate host activation and the later host check can overwrite the final diagnostic. Do not infer root cause from the last event alone. New replay 9180 retains exact baseline traffic/parameters and records the first quiesce plus host/PLL/rail/calibration state before mutation. Guarded mode1 88046 passed ideal reference traffic and remains live; monitor 65541 reported coarse acquisition and remains live.


### Unified monitor mode0 integration evidence

Running session 65541 completed all mode0 assertions: 64 ADC words delivered exactly to host, 918 monitor updates, reference-loss invalidation. Source hashes still match launch snapshot. Stored partial stdout evidence in unified-monitor-trained-progress.json; mode1 and terminal report remain pending. This covers the baseline unified diagnostic route, not finite-current guarded full payload. Replay 9180 and guarded mode1 quality 88046 remain live.


### Measured solver overhead

Short guarded unified profiles completed: 2us simulated required 60.56 million calls / 34.3 profiled seconds. 100ns inner profile shows 58,575 numpy r_ indexing calls consuming 0.569s cumulative of 1.766s, mainly three derivative concatenations per RHS evaluation. Radau collocation dominates remaining work. Reports: unified-solver-short-profile.txt and unified-solver-inner-profile.txt. Next safe optimization candidate is fixed-size derivative-array assembly with identical equations/tolerances, verified against baseline including switch/impulse/rollback tests; do not loosen integration tolerances or replace PLL dynamics to gain speed. Active runs remain unchanged.


### Direct derivative assembly optimization

DenseLimitedDriver replaces three per-RHS numpy concatenations with one fixed-size array and slice assignments, retaining state order, equations, guards and solver tolerances. Four optional-reference/detector combinations across four switch states and overload rollback match baseline exactly; measured local speedup 1.15–1.35x (connected-dense-driver.json). ManagedDenseReferenceChip extends the comparison to the actual PLL feedback path; test 90652 passed with zero observed state difference and 1.31x indicative speedup (connected-managed-dense-equivalence.json). Active long-running test sources untouched. Consolidation and full-length equivalence remain before selecting the optimized solver.


### Two-mode unified reference-monitor transport passed

65541 completed both modes: 64 host-delivered ADC words each, 918/923 monitor updates, reference-loss invalidation. All recorded source hashes verified and terminal report hash retained. This qualifies finite baseline unified diagnostic transport, not guarded finite-current RF payload or monitor kickback/noise. Optimized full acquisition/calibration comparison is next; RF replay 9180 and guarded mode1 quality 88046 remain live.


### Optimized full acquisition/calibration comparison passed

14659 terminal passed. All launch source hashes verified. Exact equality with finite-current baseline for final time, feedback-step count, rail, nine-sample count, reference charge, correction structure and all probe powers. Reported elapsed time 330.1s versus 414.2s baseline (~1.25x), under uncontrolled concurrent load. See managed-dense-calibration-comparison.json. This permits subsequent tests to use the optimized candidate without changing model equations; full payload and trajectory equivalence are not established. Replay 9180 and guarded quality 88046 remain active.


### First fault is RF frequency-lock loss

9180 replay terminated and launch source hashes verified. First quiesce at326.05us is RF oscillator lock loss; host was ready (last edge2ns earlier) and calibration valid. Phase error reconstructed as -0.00010104 reference cycles, within0.01 limit. Present=true and good=0 identify frequency criterion failure under PulseClockService.observe_lock (output equivalent limit241.2kHz); exact frequency/filter not captured. Driver rail2.997849V is92.146mV below quiet calibrated3.089995V, reference0.949805V. Next test should quantify reduced rail impedance / oscillator pulling while retaining lock and RF quality limits. No sole-cause or full-quality claim. See unified-mode0-lock-diagnosis.json. Guarded mode1 88046 still live.


### Controlled driver rail impedance run

Launched mode0 rail_budget_pad_quality.py (38143): 20ohm versus failed baseline100ohm driver rail, same100pF rail reservoir and same lock/traffic/noise/reference parameters. Dense solver and nonbinding1A reference ceilings reproduce baseline equations; 100ns managed state comparison at100ohm is exact. 20ohm is an exploratory design requirement, not physical qualification. First fault instrumentation now records PLL frequency/error and lock-history tail. This isolates supply impedance from separate150uA-reference candidate (88046 still running). No result claimed before completion.


### Guarded mode1 payload completes but TX quality fails

88046 terminal failed quality; source hashes verified and report hash retained. Full traffic completed: TX14.8521% fails10% gate, RX6.96986% passes. Saved traces analyzed without refitting validation: exact squared-error decomposition is24.819% radial and75.181% angular; contributions7.3991% and12.8779% RMS. This prioritizes phase-sensitive clock/supply interactions but does not uniquely attribute error to PLL. No changed threshold or calibration fit. See connected-guarded-limited-pad-quality-mode1.json and guarded-mode1-tx-error-decomposition.json. Controlled rail20 mode0 run38143 remains active.


### Controlled finite-current mode1 rail comparison

Started limited_rail_budget_pad_quality mode1 (42822) after verified TX14.85% baseline failure. Changes driver rail100ohm→20ohm with same150uA source/sink reference limits,50ohm reference resistance, rail capacitance, clock lock thresholds, noise/traffic and10% quality gate. Initial-state parameter assertions confirm these retained values. Uses already compared dense derivative assembly; physical equations preserved. Fault artifact has separate name from unlimited-reference mode0 experiment38143. No payload pass claimed.


### TX failure waveform visualization

Rendered and visually inspected guarded-mode1-tx-failure.svg/png from saved failure traces. Original first-quarter gain retained; phase masked only near envelope nulls for visualization, with all samples retained in quality calculation. The phase trace shifts after training and remains mostly positive during validation; amplitude peaks show compression. This motivates checking load-transition settling as well as stationary phase noise, without moving the training window or refitting the failed gate. Plot generator uses stdlib SVG/numpy and rsvg-convert (matplotlib unavailable). Controlled rail tests remain live.

### Controlled 20-ohm rail, mode 0: traffic survives, TX quality still fails

Recovered the completed `connected-rail20-pad-quality-mode0.json` and traces after
session 38143 disappeared. No corresponding process remains. All 366 launch-source
hashes match; the launch manifest now records terminal failed quality and report
hash. The exit code was not recovered and is not inferred.

The nonbinding-reference candidate completes the original traffic where the
100-ohm baseline lost RF lock. TX held-out error is 10.6274% (fails the unchanged
10% gate); RX is 6.02173% (passes). Final driver rail is 3.2530491 V. This supports
lower rail impedance as a useful intervention but does not close integrated RF
quality or establish a physical supply implementation.

`rail20-mode0-tx-error-decomposition.json` preserves the original first-quarter
gain and all 1632 held-out samples. Exact squared-error decomposition gives
6.82554% radial RMS and 8.14582% angular RMS: 41.2494% and 58.7506% of total squared
error. Both matter; angular error alone does not identify the PLL as its source.
The finite-current mode-1 comparison remains a separate live experiment, session
42822. Do not mix its reference assumptions with this mode-0 result. Keep all
closure groups partial. Next decision should use its matched 100/20-ohm comparison
and investigate residual load-transition phase and envelope errors without
changing training windows or relaxing the gate.

### Residual error persists throughout the observed held-out burst

`rail-quality-temporal-diagnosis.json` partitions each saved held-out waveform
into three equal sample windows using its original first-quarter complex gain.
This is diagnostic only; no samples are dropped or gain recalibrated. In 20-ohm
mode 0 the three errors are 11.561%, 9.810%, and 10.003%, with weighted phase
offsets 4.786, 3.362, and 3.726 degrees. The 100-ohm finite-reference mode-1
baseline gives 14.471%, 17.017%, and 12.945%, with offsets 6.779, 8.120, and 6.071
degrees. Thus the failures cannot be described as a single isolated bad sample
or assumed to disappear after the first held-out window. The short record does
not distinguish stationary error from slower settling. Preserve the full gate;
use the pending matched mode-1 rail test before attributing the change to a
particular circuit. Session 42822 was polled and PID 3066618 remains running.

### Finite-current mode 1, 20-ohm rail: matched improvement, still failed

Session 42822 completed actual traffic and exited 1 at the unchanged quality
assertion. All 369 launch-source hashes verify. The manifest records terminal
failed quality, exit code and report hash. With the same finite 150-uA reference
limits and 50-ohm reference resistance, reducing the driver rail resistance from
100 to 20 ohms reduces TX error from 14.8521% to 11.6746%; RX improves from 6.96986%
to 6.42222%. Final driver rail is 3.2513401 V. Dense solver substitution has prior
local and calibration equivalence evidence, not a full-payload bitwise proof.

The original first-quarter gain and complete held-out sample set give radial
RMS 6.71468% and angular RMS 9.55037%, with angular error contributing 66.9199% of
squared error (`limited-rail20-mode1-tx-error-decomposition.json`). The unchanged
10% TX gate still fails. Lower impedance alone is insufficient in both observed
modes. Next isolate residual phase mechanisms using matched instrumentation of
PLL phase, driver rail, and analog pad phase during traffic; do not assume all
angular error originates in the oscillator or change the gain-training window.
Both long-running rail experiments are now terminal, so frozen-source constraints
can be released for subsequent implementation changes. Mathematical closure,
transistor schematic closure, and layout readiness remain unproven.

### Matched phase-observation replay launched

Added optional read-only phase diagnostics to `loaded_pad_capture.captured` and
an opt-in flag to the finite-reference rail quality harness. At each existing pad
observation it reads LO output phase in the target carrier frame (including RF TX
phase), LO frequency, driver rail and reference voltage. An assertion requires
PLL time to match observation time. No advance or correction is introduced.
Diagnostic results use separate filenames. Python compilation passed; full
observational equivalence is pending comparison with the previous saved trace.
Session 91116 runs mode 1 with `--phase-diagnostics`; launch manifest freezes all
connected Python sources. Preserve these sources until completion. This replay
is intended to locate phase error, not replace the unchanged quality gate.

### Phase replay: exact waveform reproduction identifies LO stability priority

Session 91116 completed traffic and exited 1 at the unchanged TX quality gate.
All 370 launch-source hashes verify. Diagnostic pad traces are exactly equal to
the original finite-current mode-1 20-ohm run, including identical compressed
trace hash. Observation introduced no change to the measured waveform.

`limited-rail20-mode1-phase-analysis.json` records original error 11.6746% and
instantaneous internal-LO derotation diagnostic error 6.76266%, with first-quarter
gain training retained. Across training and three held-out quarters, weighted LO
phase is 1.48619, 1.56925, 1.59254, 1.56758 rad; pad phase is 1.49536, 1.57516,
1.59816, 1.57902 rad. Their closely tracking movement supports prioritizing
actual autonomous LO phase stability over another blind driver change.
Observed rail spans roughly 3.22886–3.257999 V, reference minimum 0.989021 V.

Internal phase derotation is not available as an assumed receiver capability,
not an implemented circuit fix, and not a replacement acceptance gate. Analog
network memory also prevents unique causal decomposition through instantaneous
derotation. Next inspect the coupled PLL phase response to driver supply and
its fractional-divider/noise dynamics, then test a bounded physical loop or
supply-isolation intervention using the unchanged waveform gate. Do not remove
noise, substitute an ideal LO, or loosen lock/quality thresholds to claim closure.
Frozen source restriction from this replay is now released. Full mathematical
closure and all downstream schematic/layout milestones remain incomplete.

### Controlled loop-filter bandwidth intervention

Averaged finite-noise-line screening at 2437 MHz predicts phase RMS 0.039986 rad
at 300 kHz versus 0.026652 rad at 600 kHz. This excludes fractional spurs, supply
forcing and acquisition, so it motivates a test rather than a pass claim.
`pll-bandwidth-intervention-screen.json` records component values: at 600 kHz,
R=33.1398 kohm, Cf=6.92937 pF, Cs=16.1685 pF, with the same 100-uA pump and .3 fast
fraction. These remain unqualified physical assumptions.

The existing finite-reference quality harness now accepts an explicit bandwidth
option and records it, retaining 300 kHz as its default. Nondefault runs use unique
filenames. Session 17857 runs mode 1 at 600 kHz with phase diagnostics, keeping
20-ohm driver rail, 150-uA reference limits, input waveforms/noise, lock thresholds
and 10% quality gate unchanged. The launch manifest freezes source hashes. Do not
alter existing connected sources until this run completes and hashes verify.

### 600-kHz candidate fails calibration readiness before payload

Session 17857 terminated with exit 1: `RF calibration readiness timeout` in
`managed_tx_quality.calibration_window`. All 371 launch-source hashes match.
The manifest now records terminal_failed_readiness. This is a simulated 50-us
readiness deadline failure, not a tool observation timeout; no payload quality
result was produced. Do not promote the averaged noise prediction to success.

Source inspection shows readiness bit10 requires reference present, coarse
qualification, RF PLL locked, quiet state, empty TX queue and calibration not
busy. Final individual predicates were not captured. Therefore the evidence
cannot yet distinguish lost lock from another readiness condition. Next capture
these predicates plus PLL phase/frequency error and recent lock history at the
same failure boundary. Keep the deadline and lock limits unchanged; do not
restart this terminal run merely for additional waiting. A diagnostic replay
must explicitly add the missing observation and preserve the original failure.

### Readiness exception snapshot replay

The finite-reference quality harness now catches the existing preparation
TimeoutError only to record its state, then re-raises it. Captured predicates are
reference present, coarse qualified, PLL locked, quiet, TX queue empty and
calibration not busy. PLL phase/frequency errors, original limits, filter voltages,
rail/reference voltages and recent lock/event history accompany the snapshot.
No additional advance or management command is introduced. Python compilation
passed; runtime snapshot remains to be exercised.

Session 73462 repeats the exact 600-kHz mode-1 settings with this observation.
`limited-rail20-mode1-bw600k-readiness-launch.json` freezes sources. Preserve the
prior terminal-failure manifest; this is a diagnostic replay, not a timeout
extension. Do not edit recorded sources until this run terminates and hashes
verify. Full-chip mathematical and downstream milestones remain open.

### 600-kHz readiness root condition verified; intermediate filter launched

Session 73462 exited 1 with its readiness snapshot at 207.1 us. All 371 recorded
source hashes verify. Only PLL locked is false: reference, coarse qualification,
quiet state, empty queue and idle calibration all pass. In the final 32 lock
observations, 17 exceed the unchanged 4000-Hz reference-domain frequency-error
limit, with maximum absolute error 9626.43 Hz. Phase remains inside .01 cycles.
At the last instant frequency error is -3473.33 Hz and good count is only 5;
a passing instantaneous sample does not establish sustained qualification.
No PLL compliance fault is reported. Do not attribute the ripple uniquely to
fractional division or noise from this snapshot alone.

The 600-kHz setting is rejected for current readiness. Session 97524 tests the
intermediate 450-kHz setting with the same full traffic harness, noise, rail,
reference limits and readiness/quality thresholds. Averaged screening predicts
.031568-rad phase RMS and filter R=24.8549 kohm, Cf=12.3189 pF, Cs=28.7440 pF;
these are assumptions, not transistor proof. Phase and failure snapshots remain
enabled. The new launch manifest freezes existing connected sources until
completion. Mathematical closure remains incomplete.

### 450-kHz result rejects bandwidth-only fix

Session 97524 terminated with exit 1 at the same 207.1-us readiness timeout.
All 371 launch-source hashes verify. PLL locked is the only false readiness
predicate; no compliance fault is present. Four of the last 32 frequency samples
exceed the 4000-Hz reference-domain threshold (maximum 5162.925 Hz), versus 17
and 9626.428 Hz at 600 kHz. Final good count is 7; the shaped fractional clock
requires max(160,4*denominator)=160 consecutive comparisons for this ratio.
Phase error remains within its unchanged .01-cycle bound. No payload quality
result exists for this candidate.

Reassessment: bandwidth-only adjustment improves the averaged noise prediction
but worsens sampled frequency ripple enough to prevent qualification. Preserve
both failures and all original gates. Next use a cheaper isolated edge-driven
PLL screen to vary bandwidth AND fast/slow capacitor split, retaining finite
noise and checking sustained qualification alongside phase error. This screen
must retain the integer-edge fractional divider and charge-pump compliance;
it cannot replace the loaded full-chip run. Establish a candidate that survives
that screen before spending another full integrated preparation/traffic run.
No mathematical closure group is promoted by this failure diagnosis.

### Isolated edge-driven filter tradeoff screen launched

Session 61975 runs `pll_filter_tradeoff_screen.py`: nine combinations of
300/450/600-kHz bandwidth and .3/.5/.7 fast-capacitor fraction. The actual shaped
integer-edge divider and compliant charge-pump filter remain in use. The screen
retains the 4000-Hz reference-domain frequency limit, .01-cycle phase limit and
160-comparison sustained qualification. It records acquisition, lock losses,
40–60-us phase variation and passive component values.

The isolated start uses the declared free oscillator plus coarse bank15 offset,
20-kHz RMS finite spectral noise with seed839 and held quiet-rail frequency pull.
It does not recreate integrated startup, rail dynamics, RF loading or traffic;
results select candidates for full-chip validation, not replace it. Report
`pll-filter-tradeoff-screen.json` is written after each completed case and embeds
source hashes. Preserve recorded connected sources during this run.

The nine-case screen completed with exit0 and source hashes verified. Only
300-kHz fractions .3 and .5 sustained tail lock; .5 slightly worsens measured
phase standard deviation (.05505 versus .05349 rad). Every 450/600-kHz case fails
sustained qualification. Larger fast capacitance reduces peak frequency ripple
in several cases but does not establish a better qualifying candidate. The
edge-driven result contradicts a simple ranking by averaged noise-only RMS,
reinforcing the need to retain sampled fractional-divider dynamics. No candidate
from this grid justifies another full-chip quality run yet.

### Fractional-ratio diagnostic localizes wider-loop failure

Session 40306 completed eight isolated edge-driven controls; embedded source
hashes verified. At 450kHz, 2437MHz fractional operation fails sustained lock
with both zero and 20kHz imposed noise. Zero-noise phase standard deviation is
.0634024rad and peak frequency error368720Hz. Nearby 2440MHz integer operation
locks in both controls: noisy phase standard deviation .0317148rad, peak error
65804Hz; zero-noise ripple is near numerical precision. At300kHz fractional
zero/noisy phase deviations are .0255906/.0534924rad; integer noisy is .0400818rad.

This supports fractional-divider/pump ripple as the bandwidth bottleneck rather
than imposed oscillator noise alone. The integer control changes frequency3MHz
and does not satisfy the required fractional-carrier capability. Zero-noise
controls are diagnostic only. Next investigate suppression of fractional phase
quantization at the actual divider/PFD interface or a revised shaping sequence,
retaining integer physical edges, pump compliance, and the original noisy gates.
Do not claim that an ideal fractional edge or integer-only radio closes the goal.

### First-order divider alternative rejected across required carriers

Session28794 completed a12-case same-carrier sequence comparison with hashes
verified. Sequence class is now an explicit overridable class attribute; default
remains second-order. Both sequence implementations passed positive integer
interval and exact rational-average checks for both carriers. Existing second-order
mode1 baseline metrics reproduce the preceding isolated screen exactly.

First-order division slightly improves 2412MHz phase/ripple at300kHz but fails
2437MHz even at300kHz (phase std .084065 versus second-order .053492rad). Neither
sequence qualifies at450/600kHz across both carriers. This rejects switching to
first-order as a general solution. Keep second-order default. Future work should
address phase quantization ripple with a bounded physical compensation mechanism
or higher-order passive filtering, rather than narrowing supported carriers.
This isolated screen is not a full-chip acceptance result.

### Added passive pole: loaded nodal screen exposes stability cost

`pll_third_pole_screen.py` solves a real three-node topology: pump shunt Cf,
R-Cs branch, and R3-C3 branch whose capacitor node drives the VCO. This includes
loading on the original filter rather than multiplying by an unloaded RC pole.
The low-frequency total-capacitance limit was independently checked.

Twelve cases at nominal450kHz use C3=1/3/10pF and nominal added poles .5/1/2/4MHz.
The screen finds sampled phase margins from -14.23 to19.28degrees; strongest
ripple attenuation generally carries the worst margin. No tested addition is a
convincing drop-in candidate. This does not prove higher-order filtering cannot
work: the complete filter must be resynthesized for damping, and resistor/pump
noise and edge dynamics remain absent. Save this rejection before introducing
another full-chip circuit. Mathematical closure remains incomplete.

### Complete passive-filter linear resynthesis

`pll_filter_resynthesis.py` jointly searches R,Cf,Cs,R3,C3 over explicit exploratory
bounds (12000 deterministic draws). 2979 cases satisfy a provisional >=45-degree
sampled phase margin and 0.2–1.5MHz crossover range. The best noise-only point
predicts .01406rad with52.67degrees margin, but its4MHz transimpedance is17.83kohm;
noise-only ranking is not sufficient for divider-ripple suppression. The report
therefore retains the noise/ripple Pareto frontier for subsequent edge testing.

The closed-form loaded transimpedance was checked against independent three-node
matrix solves at three frequencies for the top10 points. This establishes
consistency of the linear network calculation only. All resistor noise, compliance,
sampled fractional ripple and startup checks remain open. No selected chip
configuration or closure gate is changed. Next implement the three-capacitor
network's continuous state and VCO-node integral in the edge-driven PLL, preserving
pump-node compliance and loading, before judging candidates from this frontier.

### Three-capacitor continuous filter implemented and locally checked

`three_cap_filter.py` implements loaded pump/slow/VCO nodes with separate
VCO-voltage integral, pump charge, source work and both resistor losses. The
compliance-dependent current law senses the pump node; the VCO node is separate.
Advance commits only after a successful solve; invalid initial states reject
without mutation. Copying preserves independent numeric state.

`three_cap_filter_screen.py` passes independent affine matrix-exponential
comparison (4.09e-15V difference), pulse/coast/reverse energy balance
(-4.69e-27J residual), half-step refinement (5.05e-15V), near-compliance current
rolloff/energy balance and invalid-state rejection. These are local model checks,
not a PLL or chip pass. Next connect the VCO-node value and integral to the
edge-driven oscillator while retaining pump-node compliance and charge transfer.
The current Radau implementation is a correctness reference; repeated edge
forecasting may require a verified faster affine propagator before long runs.
