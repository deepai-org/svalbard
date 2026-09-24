# Clock ownership and sustained-rate obligations

**Current operating decision:** RF and wired payload operation are mutually exclusive on the same chip. Both capabilities remain required; additional physical resource sharing is encouraged. See the [exclusive-engine policy](exclusive-engine-policy.md), which supersedes simultaneous-operation requirements below. Model/RTL enforcement and resource rebudgeting remain implementation work.

The serial target set is 480 Mb/s, 1.25, 1.5, 1.62 and 2.5 Gb/s; RF
channel contexts serve HE20, Bluetooth, O-QPSK and chirp waveforms. Rate
selection and packet direction changes must preserve the ownership rules below.
Existing two-mode clock experiments do not implement this complete set.

The pin plan provides REF_IN, chip-forwarded D2H_CLK and FPGA-forwarded H2D_CLK.
RF and wired synthesis/recovery are independent engines sharing a reference and
control infrastructure. A forwarded host clock establishes capture timing; it
does not by itself make the host's payload production match a DAC or serializer.

| Boundary | Current intended owner | Required rate relationship |
| --- | --- | --- |
| Wired RX samples | Transition-driven CDR | Host consumes recovered data with bounded service gaps; host transport capacity exceeds incoming rate |
| RF ADC samples | Local sample-clock generation | D2H queues absorb bounded scheduling/CDC delay, not unlimited host stalls |
| Wired TX bits | Local wired TX synthesizer | Host symbol supply must follow that consumption rate, or explicit protocol-aware rate matching must exist externally |
| RF DAC samples | Local sample-clock generation | Host sample supply must follow that consumption rate, or an explicitly specified resampler/flow-control mechanism is required |
| D2H GPIO | Chip forwarded clock | Aggregate reserved slots must meet actual RX production rates |
| H2D GPIO | FPGA forwarded clock | Transport word rate may differ from payload rate; counts/padding permit unused slots but do not provide consumer feedback |

The current v2 metadata carries counts, sequence and limited commands, not
consumer credits or timestamps. Do not assume unallocated control bandwidth,
extra pins, arbitrary raw-bit insertion/deletion, or an implicit sample-rate
converter. The top coexistence mode has no spare scheduled payload slot.

For a constant payload rate error Δr, queue occupancy changes by Δr*t. A finite
queue or larger startup prefill cannot solve nonzero persistent mismatch.
Next choose and simulate an explicit sustainable mechanism: common-reference
payload pacing where its frequency relationships can be guaranteed, or accounted
feedback/status that controls external production. Quantify clock tolerances,
feedback latency and FIFO bounds before selecting the mechanism. Preserve both RF and wired capabilities in exclusive modes, with independently recovered wired RX timing where needed.

The connected model currently assumes source-matched TX consumption rates.
Its signed wired oscillator tests concern initial CDR error, not persistent
host/DAC mismatch. This obligation is open, not solved by those passing tests.

## Baseline candidate selected for mathematical implementation

Use chip-forwarded D2H word edges as the FPGA's payload-pacing reference. External
FPGA rational accumulators generate TX word/sample enables, independently of
payload bit values. At the lower profile generate wired words at1/2 and I/Q pairs
at4/25 of D2H word rate. At the higher profile use4/5 and8/125. The chip must
synthesize local wired-TX and DAC rates with those same average ratios. Independent
RF/wired oscillators remain; sharing a frequency reference does not mean sharing
one oscillator or recovered wired-RX clock.

This candidate needs no new pins, credits, padding data or raw-stream edits.
The host may use a separate H2D service clock, but its sample generation must
follow D2H pacing and its queues/CDC must meet service bounds. Current connected
implementation uses a common ideal host tick; separate H2D-clock verification is
still open. Host wrappers and actual chip clock synthesis must implement the
ratios before this is a hardware claim. A mode with intentionally independent
sample frequency, spread-spectrum TX or lost reference needs a separately
specified tracking mechanism/failure response; do not silently apply this model.

The pacing implementation verifies less than one sample of cumulative phase
quantization and exact counts over each denominator-length period. It removes
persistent rate error only under the stated common-reference clock-ratio premise.

## Separate host service-clock experiment

The connected model now schedules D2H reference edges and H2D service edges as
separate rational-time events. Host payload enables still count D2H edges; H2D
frames use their own word index, frequency and phase. Eight complete-path cases
cover both modes, H2D±100ppm and0/one-third-reference-tick phase. Finite delivery,
TX consumption and RF-command timing pass. This is a queue-level CDC abstraction:
reference-domain items become visible at the next service event without a modeled
synchronizer delay. Physical CDC latency/metastability and prolonged host stalls
remain open; exact analog/reference ratios are still assumed.

## Recovered raw-stream timing information

The recovered-clock path cannot promise unlimited transition-free payloads. In
current noiseless adapter tests,327680 constant bits corrupt later changing data,
while equally long randomized payloads with maximum runs5 or64bits preserve all
words at both line rates and both tested initial offset signs. These tests do not
establish a safe run limit or validate protocol encoding.

Make transition density an external encoding/application obligation for recovered
raw-stream mode. The chip must not silently insert transition bits into supplied
raw payloads or consume unbudgeted coding bandwidth. Protocol-specific validation
must use actual legal symbols and account for training, idle, fault and recovery
behavior. Separately referenced sampling, if offered, needs its own explicit
phase/frequency requirements; it is not a universal substitute for CDR.

## Integer-reference candidate (pass 831)

The connected IntegerClockChip candidate uses the existing40MHz reference divided
by four for the wired PLL. Feedback counts125 and250 provide1.25GHz and2.5GHz;
the RF synthesizer retains40MHz comparison and count60 for2.4GHz. This avoids
intentional fractional count modulation without extra pins or changed host pacing.
Reference reset counts actual future input edges. Lock thresholds retain their
absolute-time and relative-frequency meaning, with eight slower qualification
observations. Exact divider counts and noisy four-path operation pass, while the
10MHz loop's averaged-detector approximation and physical divider/noise behavior
remain limitations. Historical40MHz fractional-ratio reports remain separate.


## Serial rate and RF channel services

**Rate-independent serial service.** Explicit target rates are 480 Mb/s,
   1.25, 1.5, 1.62 and 2.5 Gb/s; FS/LS use slow line-state timing. Select dividers,
   oscillator banks, loop settings and gear ratios independently of host clocks.
   Do not interpolate from the existing two profile IDs or assume a fixed 2.5 GHz
   VCO can divide to every rate. Evaluate a retunable TX synthesizer with local
   division; preserve independent RX CDR for simultaneous SATA/PCIe/Ethernet TX/RX.
   Include SSC generation where needed and SSC reception in the timing budget.

**RF channel contexts.** Store bounded per-channel divider/bank, gain, DC/IQ
   trim and filter settings in the existing configuration memory. Preload the
   next context, atomically commit and time-stamp readiness. Full coarse search
   and recalibration on every Bluetooth hop is not acceptable. Retained trims
   need temperature/supply/age validity rules; failed lock or stale trim blocks TX.


## Executable profile rate selection

`ProtocolService.select` installs the profile line rate independently of the
legacy host/sample mode. `WholeChip.configure` uses that rate for its channel;
`AutonomousWireChip.make_serializer` derives the actual PLL ratio from it, and
`TimedChip.schedule_wire` uses channel rate rather than a hardcoded two-mode rate.
Default configurations retain their original rates. SATA is 1.5 Gb/s and DP RBR
is 1.62 Gb/s. DP source/sink admission rejects the opposite payload direction.

The regression acquires a copy of that PLL and clocks six words through the
existing phase-driven serializer at each rate with frozen rail forcing. This
is a clock/channel reduction, not canonical coupled acquisition or independent
RX CDR verification. SATA envelope generation/detection is tested separately;
DP AUX/training/SSC and SATA OOB-to-data peer operation remain open.


USB clock reuse must keep the selected reference/sampling resources warm between
packets. Evaluate the existing wired PLL at 2.4 GHz with a /5 timing branch rather
than adding a USB PLL. The existing sampling/phase-selection/CDR architecture
must acquire a burst within the HS SYNC detection budget; restarting full clock
acquisition on every packet is not acceptable. This topology is proposed; the
current USB pad tests still use prescribed bit times, not a working burst CDR.

## Current converter-clock integration gap

The selected `make_chip` composition still resolves ADC/DAC scheduling through
`PhasedChip.capture/schedule` in `connected/loop_driven_edges.py`. `LoopEdges`
snapshots `self.clock`, the separate `LinearClock` initialized by
`LockedChip.configure`; it does not integrate `self.rf_pll` or the coupled PLL
supply trajectory. Explicit `disturb_clock` invalidates pending deadlines, but
ordinary autonomous RF noise and rail pulling do not enter this sample-clock
state. Thus carrier-clock acquisition and finite RF quality do not qualify
converter aperture jitter or supply-dependent sample timing.

The independent-RX quality checker now also uses a fixed nominal sample grid,
which can detect supplied timing errors. Passing that observer cannot create a
missing physical timing mechanism.

### Selected next implementation: reference buffer and divide-by-two

Reuse the existing 40 MHz reference: every rising reference edge supplies the
40 MS/s mode; alternate edges supply 20 MS/s. No extra sampling PLL is needed
for these two rates, and RF carrier tuning remains independent. A tunable
2.437 GHz RF carrier cannot supply these rates through an integer divider.

Represent the reference distribution/buffer with a nominal propagation delay,
supply-dependent delay and explicitly bounded input timing noise. For reference
edge `r[k]`, solve `t[k] = r[k] + d(V_PLL(t[k])) + j[k]` against the same forecast
rail trajectory used by the analog owner. Delay coefficients and noise remain
hypotheses until transistor verification. Require positive bounded delay and
monotonic edges; reject a root outside its declared bracket or one crossing an
already committed edge. Do not retrospectively shift a conversion.

The scheduler must split a forecast at the earliest pending converter edge,
recompute if its rail trajectory changes, and commit edge/analog state together.
One shared reference-edge count owns ADC and DAC timing; explicit branch delay
can express their configured relative offset. Divide-by-two phase is retained
while the reference stays present, rather than restarted independently at each
capture. Start commands arm the next eligible edge after their delay guard.
Reference loss cancels pending conversions through the existing stop path;
reacquisition requires renewed readiness before arming. Host pacing must use
this same reference frequency, including its specified offset.

Before promotion, compare zero-sensitivity behavior with the existing cadence,
verify analytic constant-rail and ramp-delay roots, and test both modes with
supply steps, bounded jitter, reference loss and near-edge interventions.
The existing `clock_disturbance_lifecycle.py` passes four active retiming and two
causal-edge fault cases on its legacy linear model. Preserve those invariants,
but do not treat them as validation of this unimplemented reference-buffer path.

The candidate `connected/reference_sample_clock.py` now implements this bounded
edge primitive with separate forecast/commit operations. Its executable controls
cover 128 nominal edges across both divisors, analytic affine-rail roots, 32
bounded-jitter edges, stale forecast rejection and cancellation on reference
loss. Failed forecasts invalidate earlier proposals. A declared rail-slew bound
ensures a unique edge root; the caller must establish that bound for its actual
continuous trajectory. `forecast_trajectory` now consumes the analog owner's piecewise-linear delta
history, derives its slew bound and refuses extrapolation. An interval ending
before the edge leaves it pending; an interval beginning after a missed edge
faults. Analytic partial-horizon/ramp checks pass. A read-only probe of the
canonical PLL rail over 25–30 ns predicts an edge at 26.003882 ns without
changing chip state. Full-chip scheduler integration, common ADC/DAC branch
handling, reference-loss propagation and parameter qualification remain open.

`reference_sample_clock.py --coupled-controls` now checks four cases (16 edges)
with host toggles 0.5 ns after the reference edge, close to its buffered output.
The unchanged 1 fs numerical consistency threshold fails at 500, 125 and 31.25 ps
rail grids (first failing residuals 7.86, 2.57 and 1.25 fs). A 7.8125 ps grid
passes all cases with maximum residual below 0.089 fs. The diagnostic defaults
to this finer grid; `--rail-step-ns` reproduces the failing coarse cases.
Earlier settled-rail tests remain historical evidence, not near-edge coverage.
The candidate `refine_converter_edge` now checks both half-grid edge convergence
and a fresh analog forecast ending at the proposed edge before returning a
pending proposal. An analytic affine-rail control passes. A canonical inactive-RF
probe with a host transition at 25.5 ns converged after four refinements to a
15.625 ps grid: edge 26.0046756954 ns, committed endpoint residual -0.247 fs,
and half-grid edge change 0.350 fs, below the unchanged 1 fs numerical tolerance.
This is one switching probe, not converter activity or full scheduler integration.

Production integration needs local interpolation refinement around predicted
edges rather than assuming the existing 0.5 ns forecast grid is sufficient.
These are numerical residuals, not physical jitter accuracy. ADC/DAC operations
are still absent from this coordinator diagnostic.

### Integration constraints from the existing command path

`TimedManagement.start_local` stages a shallow candidate chip, then schedules
TX and RX before committing either. `configure_local_timing` accepts a signed
16-bit control-period RX offset; the current default is 10 ns. Independently
rounding both starts to reference edges would silently erase or change this
behavior. The reference-clock candidate is therefore not a drop-in replacement.

Implement common reference counting with explicit branch timing, preserving the
requested relative offset when supported. Separate complete reference cycles
from residual branch delay; any residual-delay mechanism and its usable range
need a stated mathematical model and later circuit implementation. Reject
unsupported combinations atomically rather than reporting acceptance and
rounding their timing. The existing wide signed field is not evidence for an
arbitrarily precise physical delay line. Both positive and negative offsets,
simultaneous edges, restart/divide-by-two phase, and a busy second direction
must be covered by the integrated regression.

The candidate `ReferenceSampleClock` now represents an explicit nonnegative
nominal branch delay below one 40 MHz reference period, separately from its
supply-sensitive buffer delay. Local controls pass 32 paired ADC/DAC-like edges
with a 10 ns relative delay across divide-by-one and divide-by-two, plus invalid
delay rejection. This is an assumed delay element, not a physical implementation
or integrated timing-command acceptance. The pure `plan_converter_pair` helper now decomposes signed offsets into whole
reference cycles and nonnegative residual delay, returning fresh pending branches
only after both timing plans validate. Fifty-six paired edges across seven signed
or zero offsets and both dividers preserve the nominal relative timing; past RX
source edges, nonfuture starts and invalid dividers reject. The requested TX start
is explicitly a lower bound rounded to the common divider phase, not an exact
absolute-time promise. This semantic difference must be addressed when wiring
management commands. Live common-counter/reference-loss ownership, branch-delay
variation and atomic installation in the actual scheduler remain open.

The parent converter loops call `sample_clock.step()` / `adc_clock.step()`
immediately after consumption. A supply-dependent replacement cannot predict
an unrestricted future edge there: leave the next edge pending, make the outer
analog scheduler forecast its bounded interval, and publish the deadline only
when that interval brackets it. When a forecast root shortens the analog step,
recompute the trajectory to that endpoint and verify consistency before
committing; discard stale proposals after intervening load/control events.
Retain the conservative same-time ordering of DAC consumption before new host
payload and the existing ADC/DAC pipeline cancellation/accounting invariants.

The converter lifecycle now dispatches consumption through `converter_consumed`:
forecast-driven clocks commit every consumed edge, including the last, and leave
the next deadline unpublished for the outer forecast coordinator. Quiescing stops
both branch clocks and invalidates their proposals. Existing prescribed clocks
retain their stepping behavior. Two actual `ReturnChip` controls cover final-edge
commit and cancellation with samples remaining; six legacy TX/RX lifecycle cases
pass. Canonical scheduling still selects the old clocks: this hook alone does not
close supply-coupled converter timing or install reference-loss coordination.

`forecast_converter_boundary` coordinates pending branches within a supplied
external-event horizon, retaining only the earliest due proposals (both when
simultaneous). Its voltage callback forecasts directly to each trial endpoint,
avoiding coarse rail interpolation; at the current time the callback must return
the already committed rail rather than request a zero-length analog solve.
Local controls cover partial horizons, ordered branches and simultaneous edges.
They also cover a changed rail forecast invalidating both old proposals, paired
reference-loss cancellation without automatic rearming, and a rejected event
horizon invalidating prior proposals. The coordinator now clears proposals before
validating the new horizon, so a failed reforecast cannot leave a stale edge
available for consumption.
A canonical inactive-RF host-switching probe used 11 endpoint evaluations, none
past its 40 ns horizon, and found a 26.0046759430 ns edge with 9.85e-22 s committed
residual. The supplied 1e9 V/s slew bound is a diagnostic assumption; a production
coordinator needs a justified bound and active-RF cost/convergence checks.
The coordinator is not yet selected by the canonical scheduler.

### Candidate coupled-scheduler installation

`IntegratedTransceiverChip.enable_reference_converter_clock()` now opts managed
local starts into paired reference-derived clocks. The existing staged management
start installs both branches only after planning succeeds. The coupled scheduler
bounds intervals by pending converter brackets, resolves endpoints against its
actual rail/RF forecast, publishes only due deadlines, and lets converter
consumption commit the edge. Quiesce cancels pending branches. Direct `schedule`
and `capture` remain legacy paths; this candidate is not the default clock model.

A real scheduler probe with inactive RF published the 26.0046759430 ns TX edge,
left RX pending, kept chip time unchanged during forecasting, and cancelled both
on stop. The acquired, noisy independent-RX test was launched via
`fast_exclusive_engine_check.py --canonical --domain-rf-screen --host-bank-rf
--rf-mode 1 --independent-rx --rf-noise-rms-hz 20000 --reference-converter-clock`.
The run was cancelled during acquisition at the user's request because its
runtime is unsuitable for architecture iteration; its 453 launch hashes were
verified and its report is marked cancelled. It produced no payload result.
Use bounded controls and short coupled windows to develop this option. A later
explicit detailed run must pass quality checks before promotion. The 1e9 V/s slew envelope, nominal branch
delay and reference timing noise still require qualification.

Candidate planning audit: ten cases (both converter rates, RX offsets -60/-10/0/
10/60 ns) preserve the requested relative timing and leave the original chip's
clock attributes untouched while staging the candidate. A past RX edge rejects.
The disabled-direction rejection bug is fixed: TX-only ignores the stored RX
offset; RX-only plans from its own requested start; paired operation preserves
the relative offset. The bounded suite covers all three masks at both rates,
unchanged inactive clocks, and rejection without partial clock installation.
This verifies planning only; the cancelled acquired-RF run provides no payload
qualification for the candidate scheduler.

Quality acceptance now requires a nominal-cadence TX reference as well as the
fixed-carrier TX reference: using recorded DAC update times in the reference
alone can hide sample-clock distortion. The added check anchors only the first
update, then uses the declared rate while retaining receiver observation times.
A validation-only 0.4-sample-period TX delay is rejected by this check even though
the event-following reference accepts it. The quality report separately labels
legacy snapshot timing and the declared reference-clock candidate; neither label
qualifies reference jitter, branch-delay uncertainty or physical aperture timing.

### Reduced connected timing/transport check

`reference_sample_clock.py --payload-controls` now drives the existing
`ReturnChip` DAC/ADC lifecycle, finite queues and framed return with the paired
reference-clock coordinator at both sample rates. Each case transfers 32 samples
through real input frames, DAC consumption, ADC capture and output frames. The
prescribed 50 mV, 1 MHz sinusoidal rail produces about 10.06 ps deviation from a
first-edge-anchored nominal cadence, confirming the rail reaches sample timing.
Two additional cases interrupt after nine conversions at each rate. They verify
that reference loss cancels both clocks and queued conversions, emits no further
samples or return words, accounts for discarded TX data, and completes explicit
abort/drain acknowledgement. Partial return delivery is retained as lossy-stop
behavior (one/three samples delivered), not relabeled lossless. All four cases
complete in under a second and run in the bounded architecture suite.
This reduced connected check intentionally omits autonomous RF acquisition and
nonlinear shared-rail feedback; it does not promote the cancelled detailed run
or establish modem quality, calibrated analog parameters or physical feasibility.

The bounded coordinator also accepts deterministic reference-edge timing noise,
evaluated once per physical source edge for both branches. A shared 100 ps
injection preserves the nominal 10 ns branch separation; an out-of-bound 101 ps
injection rejects and clears the pending proposal. The reduced payload cases
now combine a 100 ps peak sinusoidal reference disturbance with the 50 mV rail
waveform and retain successful complete/aborted transport at both rates. Maximum
nominal-grid TX timing deviation is about 110.1 ps. This is a declared sensitivity
fixture, not a measured jitter budget or RF quality pass. The detailed candidate
still defaults to zero input jitter until its configuration path is extended.

## Forwarded word-clock configurations for multi-chip video

Add generic 74.25 and 148.5 MHz REF_IN word-reference configurations, producing
742.5 Mb/s and 1.485 Gb/s ten-bit lanes with x10 serial clocks. RF configuration
retains its existing reference plan. This needs a qualified high-frequency
reference input, x10 PLL/divider configuration, deterministic word boundaries
and phase/skew control. Those circuits are design obligations, not established
by the existing 40 MHz-reference model. External clock-pair conversion/fanout
and FPGA lane deskew coordinate three dies. Reduced `ForwardedLaneGroup` models
prescribed shared-clock noise, finite word deskew and fractional skew; a common
frequency alone never grants group readiness. Detailed clock implementation and
multi-chip recovery remain open.

[HDMI/DVI board and pin plan](../../../docs/roadmap/programmable-transceiver-pin-plan.md#hdmidvi-through-multiple-instances).

The bounded HDMI/DVI test now couples a conservative forwarded-clock error budget
to the pad sampling phase. Its illustrative bounds are 10 ps reference error,
25 ps residual PLL error and 25 ps distribution skew, summed rather than RSS.
These are requirements to investigate, not GF180 measurements or a PLL simulation.
A nonzero integer-word launch error rejects alignment independently of the analog
phase budget. Divider reset, acquisition, cycle slips and independently disturbed
three-chip PLLs still require connected modeling before circuit qualification.

Dynamic forwarded-clock acquisition now reuses `SampledPLL` for three separate
x10 oscillators at each video word rate. Initial divided phases are −0.2, +0.13
and +0.35 cycles; free-running frequency offsets are −1%, 0 and +1%.
With assumed 200 MHz/V tuning sensitivity and 1 MHz loop bandwidth, the model
settles within the 25 ps per-lane / 50 ps pairwise limits after 4 us and remains
inside them across 32 reference comparisons. Halving integration steps checks
numerical stability; ±40% detuning must fail the same gate through tuning limits.
This is acquisition evidence only: the noiseless ideal detector/PI model produces
unrealistically small residual error. Retain the 25 ps residual timing allocation
for pad checks. Physical phase noise, pump mismatch/dead zone, integer-divider
reset phase, reference loss/relock and noisy phase excursions remain open.

The same acquisition model now feeds measured phase excursions into the two-leg
RC pad sampling check and board-level group admission. Independent per-die
finite-band frequency disturbances use eight lines from 250 kHz to 2 MHz,
20 kHz RMS and fixed distinct seeds. Across 128 reference periods sampled four
times per period, worst lane timing excursions are about 5.70 ps at 742.5 Mb/s
and 2.79 ps at 1.485 Gb/s. Including the assumed 10 ps reference and 25 ps board
skew gives minimum signed pad samples of about 399 and 360 mV at 2 pF.
A 20 MHz RMS negative control leaves the sampling interval and denies group
launch; reference loss also invalidates the launched group. These finite windows
and specified spectra do not establish BER, physical phase noise, cycle-slip
probability, live monitoring latency or reference reacquisition. Between-sample
extrema are not bounded. The circuit-derived noise spectrum remains missing.

Canonical serializer construction now consumes the generic forwarded-interface
setting: the wired PLL uses the selected 74.25/148.5 MHz reference and x10 ratio,
rather than silently retaining the legacy 40 MHz source. Reuse checks include
reference frequency as well as divider ratio, so changing between two x10 video
rates cannot reuse an old-rate oscillator. Reference comparisons use the shared
nominal input-edge grid; forwarded word launches choose the next ten-bit phase
boundary in both direct and bounded-forecast scheduling. Legacy embedded timing
retains its existing first-bit behavior. Canonical construction tests verify both
rates, serializer/PLL ownership and inactive RF clocks. These are construction
and scheduling checks, not acquired coupled payload qualification: board phase
origin, integer-divider reset implementation, analog pad selection and physical
word-boundary alignment still need end-to-end verification.

An independent forwarded-payload observer now copies the configured canonical
wired PLL, freezes its supply forcing, acquires for 4 us plus 32 reference
observations, and derives actual bit-launch times from oscillator phase crossings.
Those launches drive `CurrentSwitchChannel`; receiver samples use the nominal
board reference grid rather than transmitter launch times. The known board launch
epoch and zero phase-offset convention are explicit assumptions. At both rates,
16 opaque test words survive 20 kHz RMS prescribed frequency noise and 25 ps lane
skew, with minimum signed samples about 391/255 mV. The observed detector lock
flag is true; it is reported rather than overridden. A 0.7 UI lane-skew control
corrupts words. This joins configured PLL timing, finite driver settling and
independent sampling, but leaves real launch training, reference-distribution
noise, full-chip supply coupling, long-stream BER and three-lane traffic open.

The canonical receiver factory now selects `ForwardedReceiver` for forwarded
word-clock mode. It receives opaque ten-bit words through the finite current-switch
pad response, sampled on a prescribed reference grid with declared phase/rate
error. It does not insert the legacy 1024-bit training preamble or 64-bit test
marker, and does not run transition-tracking CDR. Word alignment is an external
precondition. Its equal-pole signal-energy observer uses an exact squared-response
integral for the existing idle-detector interface. Direct factory checks recover
16 words at each rate; an early-sampling control corrupts the payload. This is
receiver-construction/component evidence, not acquired canonical RX-to-host
traffic, real word-boundary training, or physical sampler qualification.

### Generic video and HD-SDI timing targets

The behavioral configuration now accepts numeric rate/reference settings separately
from the legacy enumerated resource word. Forwarded-word timing uses exactly x10
serialization over 74.25/1.001 through 148.5 MHz, including 85.5 and 108 MHz interior
points and both 1000/1001 endpoint variants. Each video data lane still occupies
one die; external clock conversion/fanout and FPGA deskew remain required.
HD-SDI targets 1.485 and 1.485/1.001 Gb/s with embedded-clock recovery and an
external 75-ohm coax driver/equalizer. FPGA logic supplies scrambling/framing.
Pathological patterns, jitter masks and actual PLL/CDR tuning bands remain open.
Numeric settings are behavioral sideband inputs: legacy command words and detailed
PLL models have NOT acquired arbitrary-rate support. Map these settings into
management registers and validate actual tuning bands before claiming integration.
No additional serial lane, pins or higher maximum video rate is proposed.

### Embedded-clock transition-gap requirement

The fast report now includes an explicit open-loop holdover screen at both HD-SDI
rates. With residual frequency error e, the kth local sampling edge drifts
`k*abs(e/(1+e))` transmitted UI. Initial phase uncertainty and an illustrative
seven-sigma jitter allowance consume the same eye budget. At +/-100 ppm,
1,000 transition-free bits consume about 0.1 UI of frequency drift; 10,000
consume about one UI and fail the assumed aperture at either selected rate.
These gap lengths are stress probes, not asserted SDI pathological-pattern limits.
The result requires a CDR design with an explicit residual-frequency/holdover
budget; line-rate support alone is insufficient. Transition-driven acquisition,
actual scrambler/pathological patterns, cycle slips and recovery remain open.
The holdover diagnostic does not upgrade HD-SDI to verified support.

The transition CDR diagnostic now samples an independently seeded 4,096-bit
payload after holdover, with correction events generated by its bit transitions.
The detector sees wrapped phase only. Stable-gap cases preserve every bit; the
100 ppm gap disturbance leaves a one-bit displacement and about half the bits
wrong even after wrapped phase settles again. Receiver readiness therefore must
combine timing lock with external framing/alignment validation; a phase-lock
indicator alone cannot authorize payload delivery after a suspected slip. This
is an ideal edge-event model, not a voltage comparator/eye or standards test.
