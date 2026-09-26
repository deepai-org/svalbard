# Clock ownership and sustained-rate obligations

The [normative architecture and diagram](block-diagram.md) own selected functional
boundaries. Numerical studies below are conditional evidence, not frozen circuit
topologies or qualified component specifications.

Live numeric measurements below that predate the exclusive-allocation section
are historical legacy-schedule controls. The fresh behavioral report uses
exclusive allocation for connected RF observers; current conclusions are
consolidated in [risk priorities](risk-priorities.md).

**Current operating decision:** RF and wired payload operation are mutually exclusive on the same chip. Both capabilities remain required; additional physical resource sharing is encouraged. See the [exclusive-engine policy](exclusive-engine-policy.md), which supersedes simultaneous-operation requirements below. Model/RTL enforcement and resource rebudgeting remain implementation work.

## External timing sources are permitted

External oscillators, clock modules, synthesizers and RF LO sources are allowed
normal operating options under the
[clock allowance](../../../docs/roadmap/programmable-transceiver-pin-plan.md#external-oscillator-and-clock-allowance).
Autonomous on-chip synthesis is a configuration choice, not a universal product
requirement. Compare both architectures in the mathematical model. `REF_IN`
remains the existing allocation; RF injection, sample-clock derivation and
quadrature generation require explicit electrical/timing contracts. Additional
inputs require a pin-budget revision. External timing does not remove incoming
serial CDR, independent-clock rate matching or on-chip distribution noise.

## FPGA response-path clock selection

Use the FPGA-generated H2D DDR clock as the candidate fast parser/response
clock: `f_fpga = H2D_word_hz / 2` (nominally 156.25 MHz at the faster setting).
The eight-word frame builder is a synchronous enable every four FPGA cycles,
not an unrelated divided-clock domain. This is the selected mathematical
candidate to carry into bridge specification, not placed FPGA timing closure.

| Boundary | Candidate implementation obligation |
| --- | --- |
| Chip D2H pins → FPGA capture | Source-synchronous DDR capture, training and word/record validation in the received-clock domain. Physical eye and gearbox timing remain open. |
| Received records → FPGA parser | Stable dual-clock storage; synchronize publication/control into H2D clock domain. Model uses eight in-flight data records and two destination cycles after edge alignment; ordered packet-end visibility is also delayed. Real FIFO pointer/reset/CDC implementation remains required. |
| Parser → response/frame builder | Same H2D fabric clock, registered decision and prepared stable response; block-enable scheduling. No asynchronous command synchronizer is needed here. Final processing time is rounded up to whole fabric cycles. |
| FPGA frame builder → H2D pins | Synchronous packing/DDR output; existing frame snapshot and next-frame emission latency remains charged. |
| Chip H2D capture → engine | Existing staged block/engine crossing remains in the connected model; this FPGA clock choice does not remove or qualify that crossing. |

`fpga_ingress.clock_source='host_ddr'` derives frequency including H2D ppm;
independent `clock_hz`, nonzero processing phase and asynchronous return-command
cycles are rejected for this topology. The independent 100 MHz parser with a
two-cycle crossing to the block frame builder remains a failing comparison.
The candidate final pipeline allocates three cycles after all packet data and
the boundary are visible: (1) latch framing/PID/CRC verdict, (2) select a
previously prepared response descriptor, (3) register descriptor publication.
NRZI/destuff/running CRC work remains charged during ingress. This allocation
requires constant-size prepared responses; arbitrary application computation
cannot use it without additional latency. It is a behavioral cycle budget,
not implemented FPGA timing evidence.

`decision_cycles=3` explicitly overrides the historical 40 ns final-work budget;
the report suppresses that unused time value. It gives 370.833 ns worst latency
in 108 faster-host cases, versus 395.833 ns for the rounded 40 ns comparison.
The slower setting fails 100/108 three-cycle cases. Preserve both comparisons.
Before accepting the candidate, implement the pipeline and prove that capture,
decode, packet-end qualification, memory reads and publication fit the budget;
then derive bounds across phase and packet length. Do not silently shorten
logic delay merely because three cycles pass.

Recovery requirements are unchanged: a lost receive clock invalidates ingress
publication and parser packet state; no partial packet may authorize a response.
Stop/flush/retrain must establish a new epoch before forwarding data. The existing
wired model tests explicit epochs, but a shared RTL reset/acknowledgment sequence
for this FPGA adapter is still open. Clock switching is stopped configuration,
not a live response-path operation.

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

The active staged `BehavioralChip.transfer` now also offers
`tx_reference_pacing=True`: an external producer counts elapsed D2H edges and
uses the configured rational words-per-reference-edge ratio. H2D frames carry
eligible unsupplied words up to their slot capacity, without FIFO-occupancy
knowledge or future reference edges. The option rejects inconsistent declared
TX/D2H average rates and cannot combine with occupancy feedback. The connected
duplex fixture enables it with 1,024 prefill bits to cover startup service delay.

The default elapsed-time edge count assumes an uninterrupted D2H clock.
`tx_reference_ticks` instead accepts a monotonically increasing count of edges
actually observed by the external producer; its callback is bound for the stream
lifetime. The duplex clock-loss fixture uses the real return-transport edge
counter across halt/restart, not elapsed-time extrapolation. Stopping D2H also
removes TX pacing credits even if H2D and the serializer continue. The resulting
TX underflow and recovered RX are deliberately reported separately; see the
[connected failure and required coordinated recovery](risk-priorities.md).

At H2D −1,000 ppm, the old per-frame production rule underflows after 615,960
consumed bits. Reference pacing completes 1,048,580 bits over 2,048 frames,
with minimum destination occupancy 84 bits. A separate 256-frame duplex run
delivers 569 ordered RX frames with zero scored TX errors; 3+253 chunks match.
These finite results remove the demonstrated production-drift failure under
the shared-reference premise. They do not prove arbitrary stalls, physical
edge-counter/CDC implementation, oscillator drift outside that premise or
autonomous recovery. The earlier 512-bit prefill results remain historical.

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

Direct external GHz LO on REF_IN is incompatible with this simultaneous 40 MHz
reference assumption. The [clock envelope](clock-feasibility-envelope.md#converter-clock-ownership-under-direct-external-lo)
records a possible LO-divided variable-rate alternative; it is not installed in
this clock owner. Do not qualify direct-LO operation using a hidden ideal 40 MHz
source.

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

### Observable alignment and host recovery experiment

`behavioral.ObservedFrameAlignment` uses received bits and local timing status.
A configurable external-fixture marker starts a candidate; a complete frame is
held until its closing marker confirms alignment. Timing loss or a wrong marker
discards the candidate. Source bit indices and payload labels never enter the
readiness decision. This marker format is an experiment, not adopted on-chip
protocol logic or a finalized ABI. It does not detect arbitrary payload errors,
balanced slips or malicious/accidental marker imitation.

`AlignedHostSource` feeds confirmed words to the existing finite host queues via
RX-valid events. Invalid events advance the CDR without adding queue occupancy.
The output queue is bounded at 16 words; candidate-frame and marker-history
storage are additional costs requiring allocation and latency budgets. Overflow
faults rather than silently dropping confirmed words.

Placement limitation: this adapter strips 64 marker bits per 160 payload bits
**before** chip host queues, while the intended protocol recognizer belongs in
the external FPGA. At 2.5 Gb/s this supplies about 1.786 Gb/s of framed payload
rather than a 2.5 Gb/s raw stream. The test selects host mode 1, so this is not a
demonstrated capacity violation; it is a missing composition. A completion test
must carry raw recovered words and causally ordered timing-loss/requalification
status through the actual finite host transport, then run alignment and packet
holdback in the FPGA observer. It must reject stale/in-flight data on a fault
without reading CDR state directly. Standard comma/ordered-set recognition
remains an external fixture obligation; no marker recognizer is added to the chip.

A reuse check also rules out directly substituting the USB-oriented short-record
return path. With 312.5 Mword/s host service, 40 MHz publication, existing CDC,
coalescing and a bounded 128-record source queue, 65,536 bits at 480 Mb/s deliver
exactly. At 1.25 Gb/s the queue overflows after 21,419 supplied bits; at 2.5 Gb/s
after 2,369 bits. Three payload words per eight-word frame cap host payload at
1.171875 Gb/s (publication itself is capped at 1.2 Gb/s). The initial 4,096-bit
1.25 Gb/s trial fit in buffers; that was not sustained service evidence.

The next composition should reuse 64-word exclusive framing (2.880859 Gb/s
nominal payload at the same host rate) and the existing 80-bit bulk CDC path.
Ordered status and partial-word boundaries must fit its explicit metadata and
storage budget; assigning generic event semantics to reserved count encodings
requires codec/CDC verification and RTL migration. Do not route an uncounted
sideband directly from the CDR to the FPGA observer or use protocol markers to
reduce the traffic before the link.

Each callback session captures its generation, raw-word offset and time origin.
Stop/reference loss cancels adapter and host digital work. Old sessions remain
invalid after rearm; rearm requires the cached raw event to be retired while
inactive. Phase, frequency correction and channel history are never reset by
these operations. The disabled source advances through the restart guard before
a new host epoch begins; a guard alone cannot qualify frame delivery.

Evidence in `behavioral-system.json`:

- `observed_frame_alignment`: 0/1,000/10,000-bit gaps with a +100 ppm step;
  each releases 47 ordered 160-bit frames. Wrong-marker and timing-loss controls
  withhold unconfirmed data. Original raw-CDR misalignment remains a negative control.
- `aligned_host_delivery`: all three gaps at 200 ppm initial offset deliver
  47 frames through host queues. A 120-frame run equals 7/33/80 chunks in data,
  flow accounting and clock state. Fixed observation length includes trailing
  silence, so invalid-event totals need not grow with gap length.
- `aligned_reference_cancellation`: interruption with 170 host bits, 15 confirmed
  adapter words, 8 candidate bits and a cached CDR word flushes digital work;
  stale callbacks reject and physical state remains unchanged at cancellation.
- `aligned_reference_recovery`: the same CDR advances 52,000 bits while disabled
  and during the startup guard. Rearm leaves its state untouched; all four old
  callbacks and the old host epoch reject. The recovered host receives 1,399
  words, including 87 complete frames, matching independently scored payload.

These are bounded generic-framing results. Arbitrary interruption timing,
false-acquisition probability, standard encoding/alignment fixtures, explicit
noise/detector/holdover envelopes and final buffer/latency allocation remain
open. Reference-loss effects on physical clock parameters and RF stop/recovery
are separate model obligations; no physical or protocol qualification follows.

### Behavioral reference-presence watchdog

`behavioral.ReferencePresence` observes supplied external reference edges through
an assumed independent timer. The live RF event loop checks timeout before each
converter/host event and at frame end. Guard expiry alone cannot enable an
instrumented chip: four observed pulses are also required. A pulse on the timeout
tick wins the tie. Missing pulses latch a fault; explicit stop accounts pending
bits and permits rearming while preserving the RF core, rail and external pulse
history. The recovery test resumes the same objects after reference returns.

The representative 40 MHz trace loses pulses after 22 us and faults at 22.1 us,
after 21 live conversions. Split and unsplit calls match payload accounting and
RF/rail state. No-reference startup faults before future returning edges, and a
separate frame-end control catches timeout between the final host event and the
frame boundary. These controls are in `reference_presence_controls` and the
behavioral report's `reference_presence` field.

The 10 ns independent monitor timer, 100 ns timeout and free-running parked
converter behavior are explicit mathematical assumptions. Presence does not
measure reference frequency/phase quality, PLL lock or sample alignment. Legacy
unmonitored fixtures and physical oscillator response to missing reference
remain unqualified.

The wired source now separates event prediction from commitment. Forecasting a
word clones only its evolving CDR/noise state and buffers the received-bit
observations. CDR phase, noise history and alignment remain at the last committed
word until the receive event occurs. This fixes a one-word lookahead that could
otherwise change alignment and physical state beyond a timeout or frame end.
The channel stimulus remains external; this scheduler implements atomic words,
not subword interruption dynamics.

`wired_reference_presence` exercises the same missing-reference trace through
CDR, marker alignment and finite host queues. It faults at 22.1 us with 5,250
committed bits, retaining a prediction for the next event without committing it.
Split execution matches received data, queues and CDR state. Explicit stop,
disabled CDR evolution and rearm preserve the same channel/clock objects; 53
complete recovered frames match independently supplied payload. This extends
pulse-presence coverage to the wired path but does not establish autonomous PLL
quality, standard encoding or an arbitrary interruption envelope.

### Connected sampled LO qualification and RF phase

`ReferenceDrivenLO` uses the existing bounded sampled-detector PI/VCO equations.
It updates the held detector only at supplied external reference pulses. Inputs
must lie on the declared nominal reference grid; missing pulses are supported,
but reference jitter and changing reference frequency are not yet modeled here.
Qualification uses eight consecutive observations with detector phase below
0.01 reference cycle and finite-difference phase slope below 4 kHz. This uses
sampled detector measurements rather than the true instantaneous oscillator
frequency; measurement resolution/noise is still idealized.

`lo_clock_controls` disables the fixed startup guard: the nominal loop qualifies
at 1.175 us, a 0.2-reference-cycle phase disturbance faults at the next observed
pulse, and an out-of-tuning-range free frequency cannot admit data. Repeated
polling at one timestamp cannot advance qualification. Stop/recovery preserves
PLL integral/phase and the RF core. The missing-pulse case advances that same LO
to the host fault time, without fictitious detector updates during the gap.

The received RF envelope includes the LO residual phase `-2π × divider × error`
against an ideal independent carrier. Both host queues, DAC/filter/mixer/RX/ADC
and the independent GFSK observer remain in the path. `connected_lo_payload`
reports 5.18%/6.48% EVM with zero/100 kHz RMS added oscillator frequency noise,
retaining the earlier additive/IID phase budget and the 10% quality limit.
At 200 kHz, observed qualification fails after four conversions; transport stops.
The 100 kHz case is exactly invariant under split calls. These points use a single
seeded eight-tone 250 kHz–2 MHz spectrum, not a statistical noise envelope.

Converter event spacing is still fixed. Shared supply now drives the PLL VCO
through the causal passive rail trajectory described below. Reference timing
uncertainty, realistic detector measurements and full tuning/noise/lifecycle
coverage remain open. No physical clock feasibility or protocol compliance is
established by this connected mathematical result.

### Shared rail driving the sampled PLL

At each host/converter event, the LO receives an immutable snapshot of current
rail charge/current and the next known event horizon. Its VCO frequency queries
the exact RC/RLC relaxation inside that interval. Future charge events are not
included. The PLL phase therefore carries supply-induced pulling and feedback
correction, while instantaneous supply gain still affects RF conversion. The
old free-running rail phase is reported as a diagnostic but is not added again
when the PLL is attached.

`lo_supply_controls` independently checks the held-oscillator RC phase integral
at two maximum step sizes (maximum residual about 1.1e-9 rad), rejects a query
past the known horizon, checks non-vacuous double-count detection, and preserves
the same rail/PLL/RF objects across a finite recovery. Disabling rail phase/gain
coupling reproduces baseline delivered samples exactly.

The existing GFSK noise case with 5 nH inductance and 0.1 host coupling passes at
6.49% EVM. Full coupling faults from observed lock loss after six conversions;
minimum rail before that failure is about 3.054 V, above the 2.5 V model-range
floor. This distinguishes a clock-quality failure from supply undervoltage.
The passing coupled case is invariant under split calls. These finite points
retain declared oscillator and frontend noise; they are not a validated noise,
package or regulator envelope. These quality fixtures retain constant converter
cadence; separate paired-jitter controls below do not yet close quality under
timing uncertainty. Continuous bias loading and physical detector accuracy
remain gaps. H2D/header loads are now
available through the complete host-activity path below.

The paired full-coupling case with added oscillator frequency noise disabled
also loses qualification, after nine conversions. Uncoupled zero-noise GFSK
passes. This isolates a load-driven failure without requiring intrinsic LO
noise, while retaining frontend/converter noise and actual host switching.

### Load-driven qualification diagnosis

The report now records the detector phase, finite-difference frequency error and
both unchanged limits at the last loss of lock. Full-coupling GFSK at 0.5/1/2 MHz
PLL bandwidth fails after 21/6/6 conversions, respectively, before the 73-sample
zero-IQ prefix ends. Measured frequency errors are about 5.05/4.73/4.34 kHz,
versus the 4 kHz limit; phase errors remain below 0.00015 reference cycle versus
0.01 allowed. Altering loop bandwidth in that range does not close the case.

At 0.25 host coupling, loss occurs after 4,407 conversions (about 440 us of
traffic), so the failing envelope is not restricted to immediate activation.
0.5 coupling and full coupling with 5 MHz/V VCO sensitivity both fail after 47
conversions. Full coupling with zero VCO supply sensitivity passes at 6.50% EVM,
retaining supply-dependent RF gain, converter/frontend noise and host switching.
This isolates the modeled clock-supply path; zero sensitivity is not a proposed
physical implementation or a waiver of the failed cases.

### Exact held-detector intervals

Between detector updates, unsaturated integral control is linear in time.
`ReferenceDrivenLO._integrate` integrates that control, oscillator frequency,
finite-tone noise and the exact RC/RLC voltage integral directly. Bounds on
control endpoints and passive stored energy conservatively check that the
interval stays unsaturated with positive oscillator frequency. Intervals that
cross saturation retain the existing adaptive RK solver. No reference event,
load event, noise term or qualification threshold is removed.

`lo_integration_controls` compares the exact solution to RK for RC, RLC and
initially saturated cases; phase differences are below 7e-13 reference cycle in
those controls and lock observations match. A connected noisy RF/host/rail
comparison returns identical samples. A held-at-clamp case independently checks
phase and saturation duration. The solver selector is an analysis option, not
hardware configuration. These checks bound numerical behavior for the tested
cases and do not validate the assumed physical PLL or supply parameters.

### Complete non-feedback host switching

With `full_host_activity=True`, the event loop uses existing `stream_codec`
metadata/guard words, actual payload words and zero padding on both buses.
Quotas are snapshotted at frame start; payload callbacks are evaluated only at
their actual transfer events. H2D input switching uses independently declared
`input_transition_charge_c` for each data transition and each DDR clock edge.
This represents effective local receiver charge coupled to the modeled rail;
the external FPGA supplies line-capacitance charging. Receiver charge is not
silently derived from the output-pad capacitance assumption.

`host_activity_controls` decodes 320 words per direction in each converter format
through the existing receiver, checks payload order, independently sums switching
charge, checks split-call equality and latches an excessive-input-load fault.
For the coupled GFSK fixture, full activity with 0/0.3 pC input charge gives
6.48%/6.49% EVM. A 3 pC case loses lock after 101 conversions. The passing 0.3 pC
case has exact split-call sample/report equality. These are conditional load
points, not a validated local-capacitance or supply-isolation envelope.

The complete-activity path requires concrete payload sources and rejects the
proposed feedback header until its binary encoding is reconciled. Historical
partial-activity cases remain explicit controls. Required configurations must
ultimately use complete activity, including bounded continuous bias/current
loads, before the mathematical switching envelope can be called closed.

### Phase-independent bound for the declared LO spectrum

For a reference interval T and K = Kvco/divider, the unsaturated held-detector
state [phase error, integral voltage] has transition matrix
`A = [[1-K*(Kp*T+Ki*T²/2), -K*T], [Ki*T, 1]]`.
A frequency tone of complex amplitude F at angular frequency w contributes
`b = [-F*(exp(j*w*T)-1)/(j*w*divider), 0]`.
The steady response is `(exp(j*w*T)*I-A)^-1*b`; multiplying its phase component
by `(exp(j*w*T)-1)/T` gives the observed finite-difference frequency error.
Summing magnitudes bounds all independent tone phases. Stability, detector
phase and control-voltage bounds are checked before using this linear result.

`lo_noise_envelope_controls` gives 4,671.137 Hz for eight 50 kHz-amplitude tones
at 250 kHz spacing (100 kHz total RMS). The constructed worst-phase realization
matches the time-domain peak within 1e-5 Hz. Detector phase stays below 0.000624
reference cycle and control magnitude below 0.103 V, so the unsaturated model
is self-consistent. The unchanged frequency limit is 4,000 Hz; a live complete-host
RF test stops after 20 conversions with the same tones and supply pulling/gain
coupling disabled. The chosen phases depend only on clock equations, not payload.

The strict all-phase RMS ceiling for this fixed spectral shape is 85,632.259 Hz
in steady state with no supply or reference disturbance. It is not a guarantee
for other spectra, startup, finite detector accuracy or actual GF180 noise, and
is not silently substituted for the existing 100 kHz test assumption.

Complete-load 256-bit GFSK checks at two payload seeds and noise seeds 830/831
pass at 5.90–6.10% EVM. Seed 832 with -48/+48 kHz carrier offsets loses lock
after 269/150 conversions, before its requested 1,024-bit payload. These failures
and the constructed spectral case remain in the report; broader long-packet
and clock-noise envelopes are still required.

### Bounded startup observation reports

`live_rf_startup_controls` exercises an untunable LO and a reference cadence
outside the declared pulse-presence window through the same live RF entry.
Startup previously escaped as a generic active-stream precondition error. It
now returns a typed report containing stage, chip state, actual observation time,
clock status and zero converter/host counts. Unavailable detector frequency is
null, so pre-observation failures remain strict JSON.

The untunable case remains acquiring at the fixture's 20 us deadline; the model
does not fabricate a hardware timeout, reset or readiness. The too-slow reference
faults at 100 ns under the configured monitor assumption. Both reject payload
before queue prefill or switching; a nominal control still delivers samples.
The observation deadline is an external test limit, not a new SPI command or a
validated physical lock-time requirement.

The matched seed-830 1,024-bit controls now pass at -48/0/+48 kHz offsets:
6.013%/5.996%/6.090% EVM, zero bit errors. Acquisition parameters are recorded
explicitly and remain fitted only to the known diagnostic prefix. The estimated
carrier errors are about 1.43/1.48/-1.82 Hz in those cases. The zero-offset run
also checks a split halfway through the host observation, during the payload,
against uninterrupted delivery and final clock/supply/queue state.

These passes retain the same payload seed as the failed seed-832 offset cases;
changing the LO noise realization distinguishes the outcomes. They demonstrate
a bounded long-payload path, not a universal 100 kHz RMS noise allowance,
standard short-preamble acquisition or independently drifting remote sampling.

## Paired converter timing in the fast live path

The optional paired converter clock now schedules actual host-queue conversion
events with bounded prescribed jitter. Filters use the elapsed interval, and
carrier/blocker/ripple terms use those timestamps. At 0.5 ns peak sinusoidal
jitter, 5/10 MS/s 12-bit and 20 MS/s 8-bit finite live runs retain LO lock and
match exactly across a host-frame split with complete host switching and shared
rail loading enabled. Independent continuous state-space filter solutions and
uniform-grid equivalence pass. Those controls establish timing/transport behavior; the waveform checks below
add finite quality evidence. The 40 MS/s 8-bit paired-I/Q demand stops on underflow after
68 samples: 640 Mb/s exceeds its configured 341.797 Mb/s host allocation.

This extension uses a constant-supply clock buffer and one paired DAC/ADC event;
shared rail voltage does not yet alter converter delay. Separate ADC/DAC and
remote clocks, aperture effects, standard acquisition and timed fault recovery
remain open. Ordinary timed stop/idle/rearm now retains a chip-owned converter
clock as described below; bypassing it with uniform transport is rejected. The sampled held-drive RF
approximation and first-step nominal-interval convention remain unchanged.

Timed conversion now also reaches the trained GFSK and LoRa observers. With
0.5 ns peak, 1 MHz sinusoidal paired-clock jitter, the existing 100 kHz RMS
seed-830 LO spectrum, complete host activity, 0.1 output coupling, 0.3 pC input
transition charge and 5 nH feed inductance remain enabled. Declared frontend,
converter and IID phase noise are unchanged. At -48/0/+48 kHz carrier offsets,
1,024-bit GFSK measures 6.015/5.969/6.074% EVM with zero errors; the matching
zero-jitter timed-clock control measures 5.978% at zero offset. Four held-out
LoRa symbols measure 6.913/6.907/6.884% EVM with zero errors. The 10% quality
budget is unchanged. Both zero-offset waveform runs reproduce samples and
transport/clock/rail reports exactly across a mid-run host-frame split.

The observer sees delivered samples on its nominal sample coordinates, not
actual converter timestamps. It estimates timing/carrier/gain from the known
prefix only. These points use one jitter waveform and LO realization; they
neither bound arbitrary jitter nor supersede the existing adverse LO-phase
failures. Common DAC/ADC timing can conceal independent-clock error. Standard
packet acquisition, independent remote sampling, converter supply-delay
feedback, graceful drain, timed fault recovery and retuning remain required.

The prescribed paired clock is now owned by `BehavioralChip`, rather than a
one-shot observation closure. `attach_rf_timing` validates it while stopped;
`timed_rf_callbacks` binds host-relative event times to the current epoch while
retaining the original absolute clock origin. Ordinary `stop` parks the same
clock and RF core. Subsequent idle advancement commits each actual jittered
edge with zero input, evolving filter/RNG state and any attached rail/PLL.
Rearming keeps that history and the startup/lock guard; old callbacks reject
before committing an event. The queue discard semantics of `stop` are unchanged.

`timed_rf_lifecycle_controls` covers 5/10/20 MS/s (12/12/8 bits), including
complete host loads and the live PLL/rail in the latter two. A 3.173 us muted
interval produces 16/32/64 conversions. Independent replay verifies the quiet
case; split idle and resumed host transport agree, delivering 27/54/86 resumed
samples. Converter phase, filter state, original time origin and RNG history are
retained rather than reset. These are finite same-setting transport checks, not
post-restart standard packet-quality or calibration-validity qualification.

A finite reference trace also faults timed idle at the declared 30.1 us monitor
deadline. Timed fault recovery is deliberately unavailable: stop records that
recovery is required, and subsequent advance/resume/start reject. Missing
reference edges, held analog state without conversion, and physical recovery
must be modeled before enabling that path. Ordinary muted idle assumes the
converter reference continues. Graceful drain, power-gated idle, retuning and
RF/wired handover of this timed path remain open.

## Exclusive allocation and coupled clock qualification

Connected RF observers use all 59 payload slots for I/Q and an explicit host
mode independently of converter precision. Qualification and quality limits are
unchanged. The partial-load comparison at 0.25 coupling faults after 4,407
legacy conversions versus 47 exclusive conversions. Those loads omit D2H header
and padding transitions and H2D receiver charge; they are diagnostic controls.

`allocation_load_controls` now compares both schedules on the same GFSK/LO seed
with partial activity, complete D2H words, and complete D2H plus 0.3 pC local H2D
transition charge. With complete D2H words, legacy fails after 42 conversions and
exclusive after 367; adding that H2D charge retains those failure counts. Rail
minima remain above 3.20 V. This reverses the partial-load ordering and prevents
an unsupported conclusion that exclusive allocation is generally worse.

At that complete load, zero added oscillator frequency noise passes near 5.187%
EVM on both schedules. Zero supply-to-VCO pulling passes at 6.492%/6.489%.
These are labeled counterfactuals, not quieter oscillator or ideal isolation
design assumptions. Closed-loop RF output affects subsequent host words, so
these interventions do not provide an additive decomposition of charge or EVM.
Both original combined-noise/load cases still fail before payload delivery.

The scheduler releases advertised payload into its earliest assigned slots,
then pads. Slot timing matters, but no pacing redesign is justified by the
partial-load result alone. That matched matrix explicitly retains averaged clock charge. Complete-load
runs now use alternating clock rising edges by default, as described below;
finite edge shape, continuous bias, physical detector uncertainty and the shared
supply/noise envelope remain unqualified.

### Alternating forwarded-clock charge

`SharedRail(full_host_activity=True)` now charges the forwarded clock on every
other DDR word event, starting with a rising edge. `host_clock_phase=1` starts
with the falling edge instead; the event counter retains phase across calls.
An explicit `host_clock_phase=None` retains the old half-rise-per-word reduction
for matched historical controls. Partial-activity controls retain that reduction
by default. Initial phase is a fixture boundary condition, not a new chip register.

`host_clock_edge_controls` checks seven events against an independent RC pulse
sum, including odd-event charge counts. For 64 events the averaged and explicit
models have identical total clock charge but different rail voltage trajectories.
Both initial phases now reach the live host/RF/PLL path with full D2H/H2D word
activity. At 0.1 coupling both pass around 6.49% EVM. At 0.25 coupling the rising-
first phase faults after 367 conversions and falling-first after 687. The noise,
PLL qualification and 10% quality budget are unchanged. These finite cases are
not an all-phase/noise realization envelope.

Edges are still instantaneous lumped charge impulses. Driver current shape,
clock/data skew, initial output energy, clock gating during stopped/startup
operation, continuous bias and physical transfer must be bounded separately.
The new default improves the active-traffic model; it does not establish those
missing electrical or lifecycle behaviors.

### Raw return event-density limit

The draft 64-word record return has 59 data slots and one ordered event per
frame. Event boundaries terminate the useful payload; nominal 2.881 Gb/s
capacity therefore does not apply to arbitrary event density. At one boundary
per 997 bits, at least two frames are needed, limiting service to
`997 * 312.5e6 / 128 = 2.43408203125e9` bits/s. A bounded draft CDC experiment
confirms overflow at 2.5 Gb/s for three source phases. At boundaries every
4,093 bits, 65,536-bit trials pass exact raw-bit and event ordering at all
three phases. These finite trials include reset release and pointer latency,
but exclude CDR, FPGA alignment, physical CDC and RTL event-tag support.

The next integration must make the status-event service envelope explicit,
including what happens when timing repeatedly loses/reacquires qualification.
Do not suppress required events or assume unbounded storage to sustain data.
The proposed 84-bit event entry and 67-record host staging are candidates,
not a validated replacement for the existing implementation.

The implemented mathematical codec now has a revised 64-word interpretation:
`wc` is data count, `qc` is the number of data words preceding the event,
`op=1..10` is the valid-bit count of that preceding word, and `op=11` means an
event before all data (`qc=0`). `op=0` means no event and requires zero `qc/arg`.
`arg` carries the opaque event code. Data after the event may use the remaining
slots. Eight-word framing retains its original interpretation. This is a generic
transport selection, never a protocol ID. Current RTL does not implement it.

The revised bounded transport draft passes all 18 rate/phase/event-spacing
cases above, with a one-frame preparation stage and no same-edge read-to-output
shortcut. A 3.2 Gb/s overload still faults. Permanent codec tests independently
check 17,760 event locations/partial widths, wrap and malformed metadata; bulk
CDC integration and FPGA-side payload alignment remain next steps. The draft
uses both a prepared and an emitting frame bank in addition to record staging;
those banks must be included in the final storage and timing budget.

The bulk CDC candidate is now implemented as `TimedBulkRecordReturn`, reusing
`BlockFIFO` pointer/reset semantics through `RecordBlockFIFO`. The connected
`raw_host_alignment_controls` sends every recovered bit and timing-status change
through that path before external alignment. It delivers 47 correct frames in
each 0/1,000/10,000-bit-gap case with a frequency step; queue peaks are 23 source
records, seven CDC entries and 66 staging records. Source publication remains
word-atomic. Reference-loss/restart, actual standard framing, status-overload
recovery and the RTL/control-interface migration remain unqualified.

The same raw-return composition now checks a reference-pulse interruption:
an independent watchdog qualifies at 80 ns, loses presence at 1.88 us and
requalifies at 2.48 us. Ordered events traverse the retained queues and frame
banks; FPGA alignment discards its partial candidate and releases 39 correct
frames in each gap case. No CDR, channel, FIFO or host sequence reset is used.
Every source status event is compared with its serialized arrival, preserving
order and nonnegative latency. Already confirmed pre-loss data may arrive after
the physical loss; it remains earlier than the loss event in stream order.

This test assumes the host and 40 MHz publication clocks continue while the
monitored reference is absent. It does not establish behavior when those clocks
also stop. The clock ownership design must provide an independently sustained
fault-delivery path or specify external host timeout and explicit retraining;
an in-band loss event cannot be promised over a stopped transport clock.

The optional trained bulk-return path now models a coordinated host/publication
clock halt and explicit digital restart. During the 1.88–2.48 us interruption,
the independent FPGA watchdog faults and invalidates pending alignment; the
same CDR continues advancing. Restart explicitly counts and discards source
records/partial bits, CDC entries, staging, prepared and emitting frame state,
then sends the existing eight-word preamble before frame zero. Cold FIFO
release still requires its normal clock edges. One pending status event is
cancelled with the discarded epoch rather than falsely reported as delivered.
The three gap cases each deliver 33 correct ordered frames after combining
pre-loss and recovered traffic. Separate phase tests distinguish all-zero old
data from all-one new data and reject leakage across restart.

This is an explicit mathematical restart operation, not a demonstrated SPI
transaction or distributed reset implementation. Command delivery/acknowledgment,
restart latency, independent FPGA timer accuracy and safe physical clock/reset
release remain requirements. The fixture does not reset analog/CDR state or
infer readiness from transmitted payload. Actual protocol framing remains open.

## Raw playback pacing and storage bound

The external FPGA owns bulk payload storage. The short-frame playback fixture
uses a 60-bit token bucket replenished from the FPGA host clock at a nominal
480 Mb/s. It must not replenish from ideal chip simulation time: that silently
assumes perfect long-term rate matching. The model now scales replenishment by
`h2d_clock_ppm`; this is a declared clock offset, not occupancy feedback.

For independent clocks, any nonzero average arrival/service difference causes
unbounded accumulated surplus or deficit during a continuous stream. No finite
FIFO closes that problem. At 100 ppm of 480 Mb/s, drift is 48,000 bits/s. Even
128 bits of entirely available headroom would absorb only 2.67 ms of positive
drift; actual headroom is smaller because bursts and crossing jitter consume it.
Negative drift can underrun instead. These are conservation bounds, not measured
time-to-failure predictions.

The 128-bit candidate has finite-burst evidence only. Continuous use requires a
rate relationship derived from the chip clock or observable credit/occupancy
feedback, plus a bound on service gaps and in-flight blocks. USB packets may
instead use a maximum-burst-duration bound, including bit stuffing and initial
queue occupancy. Do not shrink the selected ledger allocation until that bound
and restart behavior are established. A larger buffer delays clock drift failure
but does not resolve it.

The connected USB fixture now also offers `reference_pacing=True` with
`host_pacing=True`: a 16-bit modulo counter of received D2H rising edges crosses
through two modeled FPGA fabric stages; differences replenish the same 60-bit
bucket at the configured serializer/D2H ratio. This reuses existing pins and
places counter/pacing state in the FPGA. It requires the chip D2H clock and
serializer to share a fixed long-term frequency ratio. It is not applicable to
an unrelated recovered RX clock without an explicitly valid relationship.

Implement the crossing as a source Gray counter with constrained bus skew and
destination synchronization, not an independently sampled binary bus. Counter
observations must be closer than one wrap (about 419 µs at 156.25 MHz / 312.5 Mword/s).
A receive-clock loss must stop new credits and trigger stop/flush/new epoch;
reset must clear counter baseline and pending credits together. `ObservedClockPacer` models two destination stages, a 16-cycle no-progress
watchdog and a maximum eight-source-edge change per observation. Wrap is legal;
larger jumps fault. Fault clears credits and remains sticky until explicit
`arm()`. Rearming establishes a new baseline and requires observed progress
before granting the bounded initial credit. Tests cover wrap conservation,
clock loss, resumed-clock rejection and explicit rearm. Source Gray logic,
metastability and coordinated bridge-wide stop/flush acknowledgment remain
unverified. A stopped FPGA clock additionally requires the chip-side watchdog. The 128-bit allocation still requires the burst/service bound.
