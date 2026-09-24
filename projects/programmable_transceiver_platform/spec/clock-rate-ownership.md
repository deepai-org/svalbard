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
converter. The historical fully occupied transport stress profile had no spare payload slot;
it does not authorize simultaneous RF/wired operation.

For a constant payload rate error Δr, queue occupancy changes by Δr*t. A finite
queue or larger startup prefill cannot solve nonzero persistent mismatch.
A sustainable mechanism requires common-reference
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
follow D2H pacing and its queues/CDC must meet service bounds. The original pacing
experiment used a common ideal host tick; the separate-service-clock experiment
below extends its queue-level coverage. Host wrappers and actual chip clock
synthesis must implement the ratios before this is a hardware claim. A mode with intentionally independent
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

## Converter-clock ownership and optional reference-clock candidate

The legacy `PhasedChip.capture/schedule` path in
`connected/loop_driven_edges.py` uses `LoopEdges` snapshots of a separate
`LinearClock`, not autonomous RF PLL noise or coupled-rail pulling. Explicit
`disturb_clock` invalidates deadlines, but carrier acquisition and waveform
quality do not thereby qualify converter aperture timing. Fixed nominal-grid
observation can expose supplied timing errors; it cannot supply a missing clock.

The optional `IntegratedTransceiverChip.enable_reference_converter_clock()` in
[fast_exclusive_engine.py](../verification/fast_exclusive_engine.py) installs
paired reference-derived clocks for managed local starts. Direct `schedule` and
`capture` remain legacy paths. This candidate is not the default or acquired-RF
quality-qualified merely because its bounded controls pass. Active commands and
coverage belong to the [model guide](../system_model/architecture_fast/README.md);
completion decisions belong to [closure gates](mathematical-closure.json).

### Reference edge and branch contract

Reuse 40 MHz REF_IN: each rising edge supplies 40 MS/s, alternate edges 20 MS/s.
RF carrier tuning stays independent; a 2.437 GHz carrier cannot supply these
sample rates through an integer divider. No extra sampling PLL is assumed.
For source edge r[k], solve t[k]=r[k]+d(V_PLL(t[k]))+j[k] against the analog
owner's forecast rail. Nominal buffer delay, supply sensitivity, bounded input
noise and any additional branch-delay mechanism need transistor qualification.
Require positive bounded propagation, monotonic edges and a justified slew bound
for a unique bracketed root. Never move an already committed conversion.

One source-edge count and retained divide-by-two phase own both branches. Evaluate
reference jitter once per physical edge, including when both branches use it.
Represent a nonnegative nominal branch delay below one 25 ns reference period
separately from buffer delay. Split signed RX/TX offsets into complete cycles and
residual branch delay; a signed 16-bit command field is not proof of an arbitrary
physical delay line. Preserve supported offsets, including negative and zero,
or reject the entire start atomically. The planned TX start is a lower bound
rounded to the common divider phase, not an exact absolute-time promise.

`TimedManagement.start_local` stages both directions before committing. TX-only
ignores a stored RX offset; RX-only plans from its own requested start; paired
operation preserves relative timing. A busy or invalid second direction must not
partially install clocks. Cover both rates, direction masks, simultaneous edges,
restart phase and inactive-clock preservation. The legacy default offset is 10 ns.
Host production must follow the same reference frequency, including its offset.

### Forecast, commit and cancellation contract

[reference_sample_clock.py](../system_model/connected/reference_sample_clock.py)
owns the edge primitive, paired planner and coordinator. Consumption commits each
edge, including the last, and leaves the next deadline unpublished. A branch may
not extrapolate an unrestricted future edge inside `step()`. The outer scheduler
forecasts only to an external-event horizon, publishes the earliest due proposals
(both if simultaneous), then commits timing and analog state together. Preserve
DAC consumption before same-time new host payload and existing pipeline accounting.

An interval ending before the edge leaves it pending; one starting after a missed
edge faults. Failed or changed forecasts clear old proposals, including failure
while validating a new horizon. Quiesce/reference loss cancels both branches and
pending conversions; readiness must be reacquired before explicit rearming.
Reference loss does not erase retained analog state; rearming policy must preserve
the declared reference-phase convention.

Piecewise-linear rail history must not be extrapolated. Near predicted edges,
refine interpolation and check half-grid convergence plus a fresh forecast ending
at the root. The endpoint coordinator instead obtains voltage directly from each
trial endpoint; at the current time return the committed rail without a zero-length
solve. Both approaches need a justified slew bound and active-RF cost/convergence
checks. A 1 fs numerical consistency tolerance is not physical jitter accuracy.

Quality checks need both fixed-carrier and nominal-cadence TX references. Anchor
only the first DAC update, then use declared cadence at receiver observation times.
Following all recorded update times can hide sample-clock distortion. Labels for
legacy snapshot timing and the reference-clock candidate are not qualification.

### Scoped converter-timing evidence

These are distinct controls, not interchangeable full-chip passes. Complete run
history, commands and intermediate measurements are preserved in the Git link below.

| Check | Result and limitation |
| --- | --- |
| Legacy disturbance lifecycle | Four active retiming and two causal-edge fault cases establish invariants for the old linear clock, not the reference-buffer path. |
| Edge primitive | 128 nominal edges across both dividers, analytic affine-rail roots, 32 bounded-jitter edges, stale-proposal and reference-loss controls. Failed forecasts invalidate prior proposals. |
| Read-only rail probe | Canonical 25–30 ns rail predicts 26.003882 ns without changing chip state; not scheduler/payload integration. |
| Near-edge interpolation | Four cases/16 edges with host transitions 0.5 ns after source edge. At 500/125/31.25 ps rail grids, first residuals 7.86/2.57/1.25 fs fail the unchanged 1 fs check. 7.8125 ps passes, max <0.089 fs; `--coupled-controls --rail-step-ns` retains coarse-grid reproduction. |
| Adaptive edge refinement | Inactive-RF probe converges after four refinements to 15.625 ps grid: edge 26.0046756954 ns, endpoint residual −0.247 fs, half-grid change 0.350 fs. One switching probe, not converter traffic. |
| Paired timing planner | 32 paired edges retain 10 ns delay; 56 edges across seven signed/zero offsets and both dividers retain nominal timing. Invalid delays/dividers, nonfuture starts and past RX source edges reject. Assumed delay element remains unqualified. |
| Consumption hook | Two actual `ReturnChip` controls cover final-edge commit and cancellation with samples remaining; six legacy TX/RX lifecycle cases pass. Hook alone does not select the new scheduler. |
| Forecast coordinator | Partial horizons, ordered/simultaneous branches, changed rail, reference loss and invalid horizon clear/preserve proposals as specified. Inactive-RF host-switching probe uses 11 endpoint evaluations within 40 ns, edge 26.0046759430 ns and residual 9.85e−22 s. The 1e9 V/s bound is assumed. |
| Optional scheduler installation | Real inactive-RF probe publishes TX, leaves RX pending, forecasts without advancing chip time and cancels both on stop. Managed-start planning covers offsets −60/−10/0/10/60 ns at both rates and all three direction masks without partial installation. Planning is not RF payload quality. |
| Detailed RF attempt | The noisy independent-RX acquisition with `--canonical --domain-rf-screen --host-bank-rf --rf-mode 1 --independent-rx --rf-noise-rms-hz 20000 --reference-converter-clock` was cancelled at the user's request for excessive runtime. All 453 launch hashes matched; **no payload result** was produced. Use short controls for iteration; promotion still requires explicit detailed quality evidence. |
| Independent cadence control | A validation-only 0.4-sample-period TX delay fails the nominal-cadence check even when an event-following reference accepts it. |
| Reduced connected payload | `--payload-controls` transfers 32 samples through real frames, DAC/ADC lifecycle, finite queues and return frames at both rates. Two further cases interrupt after nine conversions, cancel clocks/data and acknowledge abort/drain; one/three returned samples remain explicitly lossy-stop behavior. Four cases finish in under a second. Autonomous RF acquisition and nonlinear shared-rail feedback are omitted. |
| Rail and reference disturbance | A prescribed 50 mV, 1 MHz rail yields ≈10.06 ps nominal-grid deviation. Shared 100 ps reference injection preserves 10 ns branch separation; 101 ps rejects and clears the proposal. Combined sinusoidal jitter/rail payload controls reach ≈110.1 ps deviation and retain transport. These are sensitivity fixtures; the detailed candidate defaults to zero input jitter until its configuration path is extended. |

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

The [complete immutable clock-development history](https://github.com/deepai-org/svalbard/blob/8bd7e601beba1b28d6bb0f4e092b1a76a5e2868c/projects/programmable_transceiver_platform/spec/clock-rate-ownership.md) preserves the original implementation sequence and numerical details. Superseded next-step statements there are historical, not current completion claims.
