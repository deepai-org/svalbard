# Supporting connected models and historical experiments

For current work, use the [active model guide](../architecture_fast/README.md).
The compositions and pass-number notes below are supporting historical evidence,
not the current project status. [ARCHITECTURE.md](ARCHITECTURE.md) describes this
earlier connected implementation.
`python3 projects/programmable_transceiver_platform/system_model/connected/run_architecture.py`
runs the connected regression suite and writes a fresh hashed evidence manifest.
The historical notes below are retained; a passing suite is not full architecture closure.

## Historical status (pass 674)

The executable connects host framing and finite queues, paced DAC/serializer
consumption, wired channel and transition-based clock recovery, RF DAC holds,
TX/RX filters, frequency translation, ADC quantization and return transport.
External-host pilot estimation and QPSK decisions use returned ADC words.
Separate reset tests cover partial-word discard, clock reacquisition and abstract
host status. The sections below are chronological implementation notes; earlier
missing features and two-frame prefill claims are superseded by later results.
Current TX prefill is three frames.

Run the modulated end-to-end cases:

```
python3 projects/programmable_transceiver_platform/system_model/connected/chip_model.py --modulated
python3 projects/programmable_transceiver_platform/system_model/connected/chip_model.py --modulated --iq-error-sign -1 --iq-phase-sign 1
python3 projects/programmable_transceiver_platform/system_model/connected/chip_model.py --modulated --iq-error-sign 1 --iq-phase-sign -1
```

Each run checks both modes, two attenuations and three LO offsets: 1,536 scored
QPSK symbols, zero decision errors. Normalized symbol RMS error ranges from
4.16–12.34% balanced, 10.50–29.92% for gain/phase mismatch (-10%,+5 degrees),
and 11.09–33.62% for (+10%,-5 degrees). These errors use the frozen pilot fit
and ideal unit-energy QPSK symbols; there is no test-tail refitting. They are not
Wi-Fi EVM measurements. Synthetic controls verify zero error and the exact RMS
and peak errors from one inverted symbol.

**Architecture completion remains false.** Remaining acceptance work includes
arbitrary burst flush, connected mode/reset propagation through all state,
nonideal startup/readiness, clock noise and wander, converter dynamics,
nonlinearity/noise/blockers, full-bandwidth waveforms, and shared supply/loading.
Existing separate reset tests do not establish full-chip reset behavior.
Physical feasibility, area and package coupling require additional evidence.
Prioritize RF waveform fidelity/calibration and autonomous timing; noiseless
quadrant decisions alone are too weak an acceptance test.

## Implementation history

Run from the repository root:

```
python3 projects/programmable_transceiver_platform/system_model/connected/chip_model.py
```

This is the single connected architecture model under construction. The first
increment transports actual RF-envelope sample words and wired test bits through
both physical host directions concurrently on one host-word timeline. Modes,
converter widths and rates come from contract.json; framing uses stream_codec.py.
Continuous LSB-first packing crosses sample/transport boundaries without padding.
The external host partner consumes RX data and supplies independent TX data.

The report is evidence/connected-platform.json. Checks cover payload order and
identity, conservation including untransmitted partial words, quantization error,
finite queue occupancy and delivery latency. The model intentionally exposes an
incomplete final I/Q sample when a finite stimulus stops inside a transport word;
it does not silently pad or claim complete burst delivery.

Not yet a fully working architecture: add paced DAC/serializer sinks with FIFO
underflow checks; autonomous recovered clocks and independent clock domains;
RF gain/filter/mixer and finite converter dynamics; reset/reconfiguration and
calibration; shared supply and uncertain loading. Ideal identities at analog
boundaries do not demonstrate RF or wireline physical feasibility. The present
frame builder also omits the RTL staging delay. Retain these gaps in the report
until executable checks cover them. Existing fast screens are supporting tools,
not substitutes for this connected model.

## Paced transmit sinks

The next increment merges actual sample arrivals with exact rational consumption
deadlines for the DAC and ten-bit serializer input. A late arrival cannot satisfy
an earlier deadline; clocks do not stall to conceal underflows. Arrival exactly
at a deadline is available by explicit convention. A fixed two-frame prefill
passes both modes; zero-prefill negative controls fail as expected.

The main stimulus is now625 frames, chosen to end on complete sample/transport
boundaries in both contract modes. Every generated sample is consumed and all
queues drain. This does not solve arbitrary burst truncation: the partial-word
issue described above still needs a flush/length contract. No padding is added.
TX event consumption is present, but DAC hold/reconstruction and individual
serializer-bit channel behavior remain to be connected. Rates are still matched;
independent-clock drift and actual frame-pipeline latency remain open.

## RF envelope dynamics

RX now samples the exact zero-state response of a hypothetical10MHz one-pole
filter to the external1MHz tone, then quantizes and transports it. This analytic
tone fixture includes startup but is not yet an arbitrary-waveform RX solver.
TX reconstructed words drive DAC holds at the checked consumption deadlines;
a separate10MHz one-pole filter propagates each hold analytically. The report
separates quantization error from the intended filtering response. Neither pole
is fitted to silicon. DC startup and hold-subdivision invariance controls pass.
Mixers remain ideal; gain/noise/nonlinearity and uncertain bandwidth sweeps remain.

## Wired channel connection

Both wired directions now serialize LSB-first through a stateful one-pole NRZ
channel. RX exposes a word to host transport only after its complete ten-bit
arrival interval, avoiding advance access to serial data. TX uses words supplied
at the verified serializer consumption deadlines. Prescribed mid-bit sampling
recovers words, which must match the external source/host payload exactly.

Bandwidth is hypothetically equal to bit rate. Constant-input analytic response,
sign symmetry and a deliberately bandwidth-starved alternating-pattern failure
control pass. This is not recovered timing: CDR/acquisition, unknown initial
word alignment, jitter and independent clock rates still need implementation.

## Recovered-clock adapter preparation

`python3 projects/programmable_transceiver_platform/system_model/connected/recovered_clock.py`
checks an adapter around the existing transition-driven PI clock tracker. Channel
crossings are now calculated analytically instead of from a fine waveform grid.
Both rates pass ±0.3UI initial phase and ±100ppm initial period tests with no
errors or missing clock indices after a1024-bit acquisition interval. Only
received crossings enter feedback. The fixed discard interval is not a lock
detector, and index alignment is not word framing. This adapter is not yet in the
host path; next connect recovered words at their actual final-bit observation
times, with explicit training/framing rather than a truth-derived alignment.

## Recovered RX connected to host transport

Wired RX now uses framed_words:1024 training bits followed by an explicit64-bit
marker and payload. Marker detection scans received bits without using true
symbol indices. Recovered words enter the host queue at the observed final-bit
time, rounded only by the host event tick. Training precedes active payload t=0;
that origin subtraction is testbench bookkeeping, not recovery feedback.

Both modes pass complete payload delivery with initial+0.3UI/+100ppm oscillator
error. The training/marker is an experimental link convention, not Ethernet or
PCIe protocol framing. Prefix acquisition is not yet overlapped with RF startup,
and loss-of-lock/retraining are absent. External wired TX test receiver still
uses prescribed sampling. The complete-architecture flag remains false.

## Framing reset and failure behavior

The connected receiver now feeds each recovered bit through Framer. SEARCH
withholds payload until the observed marker, PAYLOAD emits complete ten-bit
words, and2048 observed bits without acquisition latch FAULT. Only explicit
reset clears fault and partial words. Controls cover missing/corrupted markers,
fault latching, reset and partial-word discard; complete link tests still pass.
This observed-bit budget is not a wall-clock timeout and cannot detect a silent
clock. It also is not loss-of-lock detection during payload. Those functions,
automatic retraining and protocol-specific alignment remain separate work.

Run `chip_model.py --clock-sweep` for eight complete connected cases: both modes,
±0.3UI initial wired clock phase and ±100ppm initial oscillator period. The report
is evidence/connected-platform-clock-sweep.json. Unlike the earlier adapter-only
screen, each case includes marker acquisition, recovered-word availability,
host framing alongside RF traffic, and paced TX sinks. All eight pass finite
payload and timing checks. Initial oscillator error is corrected by the tracker;
it is not a test of persistent independent host/DAC rate mismatch.

## Snapshot staging correction

Transport now sends the previous frame's captured payload snapshot, matching the
staging contract instead of preparing and transmitting in the same frame. This
invalidates the earlier two-frame-prefill conclusion: it underflows IQ in both
modes. Three-frame prefill passes nominal complete-path tests and is now used.
The old two-frame setting remains a measured negative control. Remaining packer,
CDC and implementation pipeline delays still need modeling. Earlier clock-sweep
reports predate this correction; their source hashes identify that scope.

RF sample encoding now matches the transport's signed two's-complement8/12-bit
contract, with explicit negative/zero/clipping vectors. Earlier offset-binary
round-trip checks could not reveal that shared encoder/decoder mistake. Both
nominal and clock-sweep tests now use signed encoding and corrected frame staging.
See ../../spec/clock-rate-ownership.md for the unresolved sustained-rate contract.

## Validated RF mute commands reach DAC behavior

The host snapshots RF-mute and unmute commands at frames100 and200. After the
modeled staging frame, Receiver accepts them at header word4 of frames101/201.
The mathematical DAC applies the latest accepted setting at its next sample
boundary, consuming queued samples continuously but substituting zero while
muted. Reconstruction filter state continues, so RF output decays rather than
jumping instantly to zero. A corrupted mute header is rejected before any command
is emitted. Complete nominal tests pass in both modes.

This specifies a candidate mathematical application rule, not physical CDC or
hardware command latency. It does not implement mode changes, calibration,
acknowledgements, or a complete radio transmit sequencing protocol.

## Finite transmit buffering

Paced sinks now enforce capacities derived from the provisional2048-bit egress
budget, rounded down to whole samples/words. Full queues reject arrivals and
record overflow; underflows remain explicit. Accounting checks include consumed,
remaining and rejected samples. Both nominal connected modes pass with zero
FIFO faults. These provisional capacities are not physical memory allocation.

The same sink implementation has signed drift controls:10000 uniform arrivals,
eight-sample capacity and four-period prefill. A−1000ppm consumer produces six
overflows, a+1000ppm consumer six underflows before input ends, and matched rates
produce neither. This deliberately small stress fixture is not a full-chip drift
sweep or an accepted oscillator tolerance. It verifies that the model exposes
persistent rate mismatch instead of masking it with unlimited storage.

## Delayed reference-to-H2D visibility

`--visibility-cycles` sets the number of H2D service periods before reference-paced
payload enables become visible to the host framing queue (default2). Flooring
uses exact rational time, including before the first visible reference edge.
All eight host-clock offset cases pass with this delay, retaining finite egress
and fixed three-frame prefill. The report identifies the delay explicitly.

This is an abstract fixed visibility delay, not a synchronizer design or a bound
on metastability. Return-path CDC and variable per-event delays remain absent.

## RF conversion-chain loopback observation

Actual host-delivered, paced and mute-controlled DAC values now drive an external
RF envelope loopback: TX reconstruction pole → external attenuation → RX pole →
ADC quantization. Equal10MHz poles are integrated as a continuous cascade, not by
holding the first filter's sampled endpoint. ADC observations are at DAC hold ends.
Amplitude transmission0.25 and1 pass combined DAC/ADC quantization error bounds
against the filtered ideal source. DC cascade and hold-subdivision controls pass.

These returned ADC samples are not yet injected into D2H; its simultaneous RX
stream still uses the independent tone fixture. External attenuation is a test
connection, not modeled on-die leakage. Independent LO phase/frequency, noise,
nonlinearity and asynchronous ADC phase remain absent.

## RF loopback returns to the host

Loopback ADC words now enter a staged D2H replay at their actual hold-end sample
times, alongside the recovered wired stream. Host framing, continuous I/Q packing,
1024-bit provisional per-source ingress limits, ordering and complete queue drain
are checked. This closes the feed-forward host→H2D→DAC→TX filter→external path→
RX filter→ADC→D2H→host graph for both nominal modes and both attenuation settings.

The second transport evaluation is a feed-forward DAG replay at absolute times:
no future sample may enter a queue early. It does not model shared supply coupling
or feedback from returned data into the transmitter. Snapshot/codec behavior is
shared, but additional RTL pipeline and CDC delays remain abstractions.

LO offset now acts continuously between the TX and RX filters, with0/±100kHz
scenarios. The report distinguishes converter error against the appropriate
mismatched analog chain from total error against the zero-offset intended signal.
Large latter errors are expected without external carrier correction. No RF
frequency-recovery or modem-compliance claim follows from transport success.

## External pilot calibration example

Actual returned ADC words now feed an external-host estimator. It uses the known
1MHz pilot during samples64–255 to estimate frequency offset and complex gain,
then scores a disjoint last1024-sample interval without refitting. No true LO
parameter enters estimation. Signed clean-tone controls and a changed-tail failure
control pass. This demonstrates one bounded calibration use of the companion;
it is not on-chip modem logic or general Wi-Fi synchronization/EVM validation.

Session now enforces configuration/readiness before streaming and freezes mode
while armed. Engine faults are separate so a wired reset need not reset the radio.
Wired readiness is tied to the observed marker before the payload epoch. RF lock
and host training remain explicit ideal inputs. Lifecycle controls pass, but
midstream reset propagation through every queue/filter and automatic retraining
are not yet modeled. This is not a completed startup implementation.

The main entry point is now `chip_model.py`; the former name shadowed Python's
standard-library platform module. `holdover_screen.py` tests constant input runs
followed by changing data:640/40960bits pass the selected noiseless cases, while
327680bits corrupt the tail with unchanged word count. This is a detected limit,
not a maximum-safe-run specification. Transition-free data provides no new phase
observations; application timing/encoding assumptions must be explicit.

`reset_retraining.py` now exercises a reset after37 observed payload bits: it
retains three completed wired words, discards the seven-bit partial word, then
reacquires a fresh marker and256 new words. Independent RF sample traffic crosses
the same D2H staging/codec throughout. Both modes preserve all accepted data.
This resets framing only; CDR/channel state, analog RF continuity and host-visible
epoch/status signaling remain outside the test.

`reset_retraining.py --reset-clock` additionally restarts the timing tracker with
opposite phase/period offsets while preserving the channel's continuous state.
Before-reset samples are checked bit-for-bit and time-for-time against the
uninterrupted prefix. Both modes reacquire and preserve complete accepted words
and concurrent RF samples. Analog oscillator reset and host-visible epoch/fault
reporting are not covered by this mathematical reset.

Reset tests now expose a coherent abstract sideband snapshot: saturating epoch,
last reset's cumulative accepted-word boundary, discarded partial bits and an
overflow flag. The host can distinguish pre/post-reset words without changing
stream payloads, provided complete accepted words drain losslessly and the count
origin is shared. Missing multiple epochs leaves ambiguous earlier boundaries;
last-event status is not an event log. SPI register mapping, snapshot CDC and RTL
still require implementation before this becomes a hardware interface claim.


### Pass 675 — attribute RF waveform error without hiding it

Previous turn: progress. Added an orthogonal projection of corrected QPSK
onto known held-out symbols, separating constant complex-gain bias from
nonscalar distortion. This is a truth-assisted diagnostic only; operational
pilot fitting and symbol decisions are unchanged. Error energy must equal
scalar-bias energy plus residual energy. Analytic uniform-gain and inverted-
symbol controls pass. Both modes pass balanced and (+10%,-5 degree) mismatch
runs, 12 scenarios/run, zero symbol errors; the full waveform error remains.

connected-platform-modulated.json: scalar-bias RMS 0.037785–0.123379; nonscalar residual RMS 0.000008–0.021825.

connected-platform-iq-gain-1-phase--1.json: scalar-bias RMS 0.000740–0.316997; nonscalar residual RMS 0.108061–0.116980.

The balanced case is dominated by scalar bias: a 1MHz tone's fitted gain/phase
is not automatically appropriate for settled QPSK symbol centers after the
filters. Mismatch also leaves a larger nonscalar residual. Next test a separate
known-symbol calibration preamble with frozen parameters and disjoint scoring,
then widen waveform bandwidth and add clock/noise stresses. The diagnostic
projection itself must never be reported as achieved receiver performance.
Autonomous LO container verified live; no restart or physical result claimed.
Architecture completion and layout gates remain open/incomplete.


### Pass 676 — frozen known-symbol calibration

Previous turn: progress. Reserved 64 known QPSK symbols before the 128 scored
symbols for an external-host scalar calibration. Frequency correction remains
frozen from the initial tone. Training and scoring indices are disjoint; both
modes' training starts after mute release, verified against reported events.
Analytic controls establish correction of a persistent scalar change and that
changes confined to scored data cannot change the calibration coefficients.
The latter change remains visible as error rather than being silently refitted.

connected-platform-modulated.json: calibrated held-out RMS 0.000021–0.022551; symbol errors 0.

connected-platform-iq-gain-1-phase--1.json: calibrated held-out RMS 0.111717–0.118636; symbol errors 0.

Both end-to-end modes pass transport and conversion checks in the balanced and
(+10%,-5 degree) scenarios. This calibration uses received sample words and
known preamble symbols; it assumes supplied symbol timing and reserves training
airtime. It is external FPGA functionality, not added chip modem logic. It
does not estimate the I/Q matrix, correct frequency-estimate drift, or establish
full-bandwidth Wi-Fi performance. Next priority: model frequency/image imbalance
separately before assuming a static post-derotation correction can fix it.
Autonomous LO container remains live. No tapeout or layout gate advanced.


### Pass 677 — verify I/Q correction ordering

Previous turn: progress. Added connected/iq_rotation_screen.py and evidence/
connected-iq-rotation.json. Independently derived y=a*z+b*conjugate(z) matches
the real I/Q matrix for both independent gain and phase signs. After frequency
correction, the image becomes b*conjugate(x)*exp(-j*2*omega*t), so its effective
coefficient rotates at twice the offset. A fixed post-derotation matrix is the
wrong general correction model. Disjoint training/scoring on synthetic QPSK
confirms approximately 11% residual at either signed 100kHz offset, despite
exact recovery at zero offset. An exact known-parameter inverse before frequency
correction recovers all 12 cases to floating-point precision (maximum RMS
3.34e-16). This is an ordering/control result, not a fitted receiver result.

Next estimator should identify direct and image terms before derotation, or
include the rotating conjugate basis. Keep estimates frozen for held-out tests
and test wrong/no calibration controls. Do not claim this synthetic memoryless
result solves filter mismatch, nonlinearities, clock noise, or RF bandwidth.
The connected waveform remains a narrow QPSK fixture; expand bandwidth after
this structural calibration issue, rather than indefinitely polishing it.
Autonomous LO container verified live. No circuit/layout gate advanced.


### Pass 678 — estimate rotating image from reserved symbols

Previous turn: progress. External-host estimator now fits direct and rotating
conjugate coefficients using only the same 64 reserved symbols. Frequency stays
frozen from the initial pilot; held-out samples never update coefficients.
Invertibility and training rank are checked. Original uncorrected/scalar scores
remain visible alongside image-corrected scores. Analytic controls verify exact
zero-offset image recovery and invariance of fitted coefficients to changes
confined to held-out data; those changes still produce visible scoring errors.

connected-platform-modulated.json: image-calibrated RMS 0.000021–0.022883; errors 0; maximum basis condition 1.0111.

connected-platform-iq-gain-1-phase--1.json: image-calibrated RMS 0.014944–0.032330; errors 0; maximum basis condition 1.0108.

Both modes pass connected transport/conversion checks. This tests balanced and
(+10%,-5 degree) mismatch only, both attenuation levels and all three LO offsets.
It does not establish robustness to unseen mismatch, ill-conditioned training,
noise or time-varying impairments. Residual frequency bias from the tone fit can
still accumulate after calibration. Next broaden signal bandwidth and impairment
stresses rather than assuming narrow, settled QPSK symbols qualify the radio.
Autonomous LO container verified live; no restart. No physical gate advanced.


### Pass 679 — increase connected waveform bandwidth

Previous turn: progress. Added --symbol-samples 2/4/8 to the connected stimulus
and external-host estimator. Training and scoring keep fixed sample durations;
training symbol count therefore increases with rate. Both modes run through
unchanged DAC holds, two 10MHz poles, ADC and transport. Stress runs report
symbol errors rather than requiring favorable outcomes; payload/conversion
invariants remain asserted. Existing analytic calibration controls still pass.

ethernet_rf40_12, 10 Msymbol/s: maximum calibrated RMS 0.013719, symbol errors 0.

pcie_rf20_8, 5 Msymbol/s: maximum calibrated RMS 0.022408, symbol errors 0.

ethernet_rf40_12, 20 Msymbol/s: maximum calibrated RMS 0.204119, symbol errors 0.

pcie_rf20_8, 10 Msymbol/s: maximum calibrated RMS 0.027329, symbol errors 0.

Evidence: connected-platform-symbols-{2,4}-gain-0-phase-None.json. This is
unshaped QPSK with supplied timing, not a spectrally compliant Wi-Fi waveform.
Increasing symbol rate alone does not establish occupied-channel bandwidth,
OFDM performance or noise tolerance. No equalizer is fitted beyond the existing
memoryless direct/image coefficients. Next isolate pulse-memory distortion
from frequency bias and test a bandwidth-defined waveform before claiming the
RF budget supports 20MHz operation. Autonomous LO container remains live.
Architecture completion and physical gates remain unproven.


### Pass 680 — bandwidth-defined multicarrier RF screen

Previous turn: progress. Added connected/multicarrier_screen.py using the same
DAC/ADC codec and exact two-pole held-input RF response. Fifty-two active
subcarriers extend to +/-8.125MHz at 312.5kHz spacing; cyclic prefix is 0.8us.
A fixed 0.18 complex RMS scale avoids per-record peak normalization. Peaks stay
below clipping. Eight training blocks fit per-bin response; 30 disjoint blocks
(1,560 QPSK symbols/case) are scored without refitting. FFT identity and a
held-out-only sign-inversion control pass; all four cases have zero errors.

At 20MS/s, 8 bits/component: normalized RMS error is 8.55% at attenuation
0.25 and 2.64% at unity. At 40MS/s, 12 bits/component: 0.398% and 0.120%.
Minimum measured normalized response is approximately 0.67–0.69 and 0.58,
respectively. These are sampled hold/filter responses, not continuous-time
filter measurements. Rates and resolutions change together, so this comparison
does not isolate the effect of either parameter. Evidence is
evidence/connected-multicarrier-screen.json.

This is a supporting RF screen, not yet integrated host/wired concurrency.
Finite rectangular multicarrier blocks have sidelobes; active-bin span does not
prove a spectral mask. No Wi-Fi compliance, noise, LO error, I/Q imbalance or
achieved converter resolution is implied. Next connect this waveform through
the host path and stress noise/headroom; do not substitute favorable 12-bit
math results for the unresolved physical ADC. Autonomous LO verified live.
No physical/layout gate advanced.


### Pass 681 — multicarrier ADC return with concurrent wired recovery

Previous turn: progress. The multicarrier screen now obtains its mode rates from
the contract and routes actual quantized ADC words through return_samples, with
continuous bit packing, finite ingress limits, previous-frame staging and host
decoding. Concurrent wired payload passes transition-driven clock recovery and
marker framing before entering the same return transport. External equalization
and scoring consume decoded host words. All ADC pairs and wired words arrive
in order, queues drain and no payload differs.

pcie_rf20_8, attenuation 0.25: 3200 ADC pairs, 40000 wired words, peak ingress {'wire': 520, 'iq': 88} bits, maximum ADC delay 154.000 host ticks, RMS 0.085518.

pcie_rf20_8, attenuation 1: 3200 ADC pairs, 40000 wired words, peak ingress {'wire': 520, 'iq': 88} bits, maximum ADC delay 154.000 host ticks, RMS 0.026437.

ethernet_rf40_12, attenuation 0.25: 6400 ADC pairs, 20000 wired words, peak ingress {'wire': 320, 'iq': 272} bits, maximum ADC delay 140.750 host ticks, RMS 0.003980.

ethernet_rf40_12, attenuation 1: 6400 ADC pairs, 20000 wired words, peak ingress {'wire': 320, 'iq': 272} bits, maximum ADC delay 140.750 host ticks, RMS 0.001203.

RMS scores match the prior direct-ADC screen, as expected for bit-exact return.
The evidence source inventory includes transport, contract and timing dependencies.
This completes only the return-path integration: multicarrier H2D generation
still bypasses framing/pacing, and LO/noise/mismatch remain ideal in this screen.
Next add the actual host-to-DAC path without silently changing sample deadlines
or claiming full-chip closure. Autonomous LO container verified live. No
physical/layout gate advanced.


### Pass 682 — framed multicarrier host-to-DAC path

Previous turn: progress. Added optional decoded sample timestamps to the common
framing replay helper. The multicarrier host source now traverses framing,
previous-frame staging and chip decoding alongside wired TX words. Decoded RF
pairs feed finite DAC queues at exact rational consumption deadlines, with
three-frame prefill. The analog response uses actual DAC consumption times and
ADC return timestamps include this absolute delay. Both modes preserve every
TX sample with zero underflow/overflow; zero-prefill controls fail as expected.

pcie_rf20_8, attenuation 0.25: DAC FIFO peak 5 pairs; zero-prefill underflows 10; scored RMS 0.085518.

pcie_rf20_8, attenuation 1: DAC FIFO peak 5 pairs; zero-prefill underflows 10; scored RMS 0.026437.

ethernet_rf40_12, attenuation 0.25: DAC FIFO peak 11 pairs; zero-prefill underflows 23; scored RMS 0.003980.

ethernet_rf40_12, attenuation 1: DAC FIFO peak 11 pairs; zero-prefill underflows 23; scored RMS 0.001203.

Both RF directions are now framed in this multicarrier test. The reused helper
retains D2H-oriented field names internally; H2D data is explicitly reported as
host_transmit. This is shared-reference feed-forward replay, not independent
CDC or feedback simulation. Wired TX words are framed/decoded but not passed
through a serializer here; wired RX still uses transition-based recovery.
No mute/reset/acquisition/noise/LO-error qualification is claimed. Next add
noise/headroom stress to the bandwidth-defined chain and reassess priorities
against physical timing/converter evidence. Autonomous LO container verified
live; no physical/layout gate advanced.


### Pass 683 — ADC-input noise through the framed multicarrier chain

Previous turn: progress. Added --noise-rms with reproducible IID complex Gaussian
noise before ADC quantization. Its absolute RMS does not scale with external
attenuation; training and scoring both see noise, and coefficients stay frozen
for scoring. The same realization is reused for attenuation comparisons. Noise
power, clipping counts, symbol errors and full transport checks remain visible.
Re-ran zero noise plus 0.01 and 0.03 complex RMS in normalized component full-
scale units; these are sensitivity cases, not measured physical noise limits.

noise 0, pcie_rf20_8, attenuation 0.25: RMS 0.085518, symbol errors 0/1560, clipped pairs 0.

noise 0, pcie_rf20_8, attenuation 1: RMS 0.026437, symbol errors 0/1560, clipped pairs 0.

noise 0, ethernet_rf40_12, attenuation 0.25: RMS 0.003980, symbol errors 0/1560, clipped pairs 0.

noise 0, ethernet_rf40_12, attenuation 1: RMS 0.001203, symbol errors 0/1560, clipped pairs 0.

noise 0.01, pcie_rf20_8, attenuation 0.25: RMS 0.267394, symbol errors 0/1560, clipped pairs 0.

noise 0.01, pcie_rf20_8, attenuation 1: RMS 0.068151, symbol errors 0/1560, clipped pairs 0.

noise 0.01, ethernet_rf40_12, attenuation 0.25: RMS 0.187071, symbol errors 0/1560, clipped pairs 0.

noise 0.01, ethernet_rf40_12, attenuation 1: RMS 0.046505, symbol errors 0/1560, clipped pairs 0.

noise 0.03, pcie_rf20_8, attenuation 0.25: RMS 0.777569, symbol errors 274/1560, clipped pairs 0.

noise 0.03, pcie_rf20_8, attenuation 1: RMS 0.190203, symbol errors 0/1560, clipped pairs 0.

noise 0.03, ethernet_rf40_12, attenuation 0.25: RMS 0.571311, symbol errors 101/1560, clipped pairs 0.

noise 0.03, ethernet_rf40_12, attenuation 1: RMS 0.139992, symbol errors 0/1560, clipped pairs 0.

All transport/deadline checks pass. Noise degrades scored signal quality without
being hidden by payload identity. These single-seed finite records do not
establish BER, receiver sensitivity, noise figure or tolerance bounds. Identical
sample noise RMS at different sample rates is not identical analog noise PSD.
Next establish a physically interpretable input noise/bandwidth budget and
headroom stress, with uncertainty in either direction. Autonomous LO container
verified live at pass start; no restart or physical result claimed.


### Pass 684 — compare a consistent noise density across rates

Previous turn: progress. Added mutually exclusive --noise-density, specifying
the square root of complex two-sided PSD, flat over [-fs/2,fs/2]. Thus total
complex sample variance is density squared times fs, and each real component
has half that variance. With FFT spacing fixed, predicted demodulated noise
per active bin is unchanged between rates; this equality was verified to
1e-14. This removes an unfair sample-noise advantage in cross-rate comparisons.

pcie_rf20_8, attenuation 0.25: sample noise RMS 0.01000000, predicted FFT-bin noise RMS 0.05007710, calibrated RMS 0.267394, symbol errors 0.

pcie_rf20_8, attenuation 1: sample noise RMS 0.01000000, predicted FFT-bin noise RMS 0.05007710, calibrated RMS 0.068151, symbol errors 0.

ethernet_rf40_12, attenuation 0.25: sample noise RMS 0.01414214, predicted FFT-bin noise RMS 0.05007710, calibrated RMS 0.265477, symbol errors 0.

ethernet_rf40_12, attenuation 1: sample noise RMS 0.01414214, predicted FFT-bin noise RMS 0.05007710, calibrated RMS 0.065782, symbol errors 0.

Density was 2.2360679775e-6 normalized units/sqrt(Hz). If one normalized
component unit corresponds to V_FS volts, multiply this density by V_FS
for the square root of total complex voltage PSD; each component's two-sided
PSD is half the complex PSD. Do not equate normalized noise with dBm, noise
figure, or RF sensitivity without impedance, gain and voltage conventions.
The flat Nyquist model is an effective sampled noise assumption; physical
antialias filtering and aliased out-of-band noise still need representation.
Evidence: connected-multicarrier-density-2.23607e-06.json. Independent noise
realizations and changed resolution prevent isolating sample-rate effects
from these four records alone. Autonomous LO verified live. No gate advanced.


### Pass 685 — low-amplitude quantization and high-amplitude clipping

Previous turn: progress. Added --drive-rms with fixed waveform scaling, preserving
clipping instead of normalizing peaks away. DAC/ADC clipping counts use rounded
code bounds matching the signed codec, including the asymmetric positive rail.
Training sees the same impaired path; held-out correction stays frozen. Tested
0.03 and 0.6 complex RMS at both attenuations and modes without added noise.

drive 0.03, pcie_rf20_8, attenuation 0.25: DAC clipped 0 pairs, ADC clipped 0, RMS 0.495527, symbol errors 59/1560.

drive 0.03, pcie_rf20_8, attenuation 1: DAC clipped 0 pairs, ADC clipped 0, RMS 0.156679, symbol errors 0/1560.

drive 0.03, ethernet_rf40_12, attenuation 0.25: DAC clipped 0 pairs, ADC clipped 0, RMS 0.022751, symbol errors 0/1560.

drive 0.03, ethernet_rf40_12, attenuation 1: DAC clipped 0 pairs, ADC clipped 0, RMS 0.007109, symbol errors 0/1560.

drive 0.6, pcie_rf20_8, attenuation 0.25: DAC clipped 116 pairs, ADC clipped 0, RMS 0.061657, symbol errors 0/1560.

drive 0.6, pcie_rf20_8, attenuation 1: DAC clipped 116 pairs, ADC clipped 0, RMS 0.056752, symbol errors 0/1560.

drive 0.6, ethernet_rf40_12, attenuation 0.25: DAC clipped 234 pairs, ADC clipped 0, RMS 0.050212, symbol errors 0/1560.

drive 0.6, ethernet_rf40_12, attenuation 1: DAC clipped 234 pairs, ADC clipped 0, RMS 0.050206, symbol errors 0/1560.

Transport and DAC deadlines still pass. These two drive points bracket separate
quantization/headroom failures; they do not select an optimum operating level
or bound random waveform peaks. Actual analog compression can occur before
code saturation and remains unmodeled. The 12-bit mode remains an architectural
target, not established physical converter performance. Reassess next against
physical ADC/reference limits rather than optimizing ideal digital resolution.
Autonomous LO container verified live at approximately 7.113us of 8.001us;
its advancing log is evidence of progress, not a completed timing result.
No tapeout/layout gate advanced.


### Pass 686 — converter precision independent of transport width

Previous turn: progress. Added --adc-bits 4/6/8 as an ideal quantizer stress.
Quantized values are exactly re-encoded in the existing transport width;
sample rates, wire traffic, queue limits and DAC resolution remain unchanged.
Round-trip equality is asserted, and clipping counts use actual quantizer rails.
Both 6-bit and 8-bit tests pass all payload/deadline invariants.

ADC 6 bits, pcie_rf20_8, attenuation 0.25: RMS 0.319305, symbol errors 3/1560.

ADC 6 bits, pcie_rf20_8, attenuation 1: RMS 0.085518, symbol errors 0/1560.

ADC 6 bits, ethernet_rf40_12, attenuation 0.25: RMS 0.248104, symbol errors 1/1560.

ADC 6 bits, ethernet_rf40_12, attenuation 1: RMS 0.060341, symbol errors 0/1560.

ADC 8 bits, pcie_rf20_8, attenuation 0.25: RMS 0.085518, symbol errors 0/1560.

ADC 8 bits, pcie_rf20_8, attenuation 1: RMS 0.026437, symbol errors 0/1560.

ADC 8 bits, ethernet_rf40_12, attenuation 0.25: RMS 0.060341, symbol errors 0/1560.

ADC 8 bits, ethernet_rf40_12, attenuation 1: RMS 0.015222, symbol errors 0/1560.

These are resolution sensitivities, not models of physical SAR decision errors,
DNL/INL, reference memory or measured ENOB. Even 8-bit ideal conversion is not
qualified in hardware. The useful operating amplitude is intertwined with
converter accuracy and gain control; a 12-bit transport field proves neither.
Reassessed priority: finish the autonomous LO result when terminal; meanwhile
bring converter/reference uncertainty into the RF model before more favorable
modem demonstrations. Noise, clock phase noise and package coupling remain
unbounded physically. Autonomous LO container verified live. No gate advanced.


### Pass 687 — causal reference-memory sensitivity

Previous turn: progress. Added a hypothetical ADC reference-span state driven
by prior input transition magnitude, clipped at unit activity and relaxed with
a 50ns time constant. Current conversion uses the earlier state, then updates
it; no future input is consulted. Signed strength is bounded below unity in
magnitude, ensuring positive span. Zero-strength identity, analytic step/decay,
span bounds and future-input invariance controls pass. Both +/-0.1 strengths
run through quantization, framing, calibration and scoring.

strength -0.1, pcie_rf20_8, attenuation 0.25: span 0.990183–1.000000, RMS 0.085205, errors 0.

strength -0.1, pcie_rf20_8, attenuation 1: span 0.960732–1.000000, RMS 0.027135, errors 0.

strength -0.1, ethernet_rf40_12, attenuation 0.25: span 0.994598–1.000000, RMS 0.004008, errors 0.

strength -0.1, ethernet_rf40_12, attenuation 1: span 0.978392–1.000000, RMS 0.002845, errors 0.

strength 0.1, pcie_rf20_8, attenuation 0.25: span 1.000000–1.009817, RMS 0.084874, errors 0.

strength 0.1, pcie_rf20_8, attenuation 1: span 1.000000–1.039268, RMS 0.027058, errors 0.

strength 0.1, ethernet_rf40_12, attenuation 0.25: span 1.000000–1.005402, RMS 0.003900, errors 0.

strength 0.1, ethernet_rf40_12, attenuation 1: span 1.000000–1.021608, RMS 0.002847, errors 0.

The strength is an activity coupling, not a constant 10% reference error.
Observed spans above are the actual exercised excursions. This is not fitted
to transistor SAR data and does not model within-conversion bit decisions,
reference common mode, capacitor mismatch or signed charge injection. It is
a causal sensitivity axis; favorable results cannot validate the real ADC.
All payload/deadline checks pass. Next connect measured reference trajectories
to converter decision behavior rather than accumulating arbitrary stress knobs.
Autonomous LO verified live at 7.285us of 8.001us. No physical gate advanced.
