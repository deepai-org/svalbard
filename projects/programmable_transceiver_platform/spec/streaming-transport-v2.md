# Candidate streaming transport v2

The framed path below serves bulk payload. USB response-critical operation also
uses a proposed short-frame configuration of this same transport; RF profiles require
time-tagged bursts and channel readiness. These are host-interface obligations
on the existing pins, not permission to assume zero-latency FPGA responses.

This is the executable reference for replacing compulsory bulk CRC/quarantine. As of pass 28, this is the default integrated RTL transport. V1 remains available through compile-time parameter STREAM_V2=0. No chip area, timing or power saving is claimed before implementation and measurement. All 50 terminals and both full-rate wired/RF profiles are retained.

## Geometry and encoding

Each 64-word frame contains five header words at positions 0–4 and 59 scheduled payload positions 5–63. Words remain ten bits. The existing smooth weighted scheduler uses quotas 33 wired/25 IQ/one idle in the lower profile and 52 wired/seven IQ in the higher profile. Thus nominal capacities and reserved service rates are unchanged. This moves the existing five overhead slots to the beginning of the frame; it does not create extra bandwidth. Source word counts and bit packing retain their meanings.

Metadata has 30 data bits: wired count [5:0], IQ count [11:6], sequence [17:12], opcode [21:18], argument [29:22]. Use shortened extended Hamming **for detection only**: positions 1–36 have parity at 1,2,4,8,16,32, and the 30 data bits occupy the other positions in ascending order, least significant first. Each parity subset has even parity. Bit 36 of the encoded integer is overall even parity across those 36 positions. Integer bits 37–39 contain constant tag 101. Words 0–3 transmit the encoded integer in ten-bit chunks, least significant chunk first. Word 4 is fixed guard 0x2d3.

This affine code has minimum distance four: it detects every one-, two- or three-bit change within the 50 header bits. **Do not correct single-bit syndromes:** correction could turn a triple error into accepted wrong metadata. Four-bit errors can be undetected; e.g. the codewords for zero wired count and one wired count differ by four bits. This is not authentication, burst-error immunity or an adequate BER argument by itself. The fixed tag/guard is not proof of acquisition: payload can mimic it.

## Acceptance and release

Before any frame effect, validate tag, parity, guard, expected sequence, per-source count bounds and command legality. Commands presently supported are no-op with argument zero, wired-idle 0/1 and RF-mute 0/1. Reserved opcodes/arguments fail. In the reference, successful validation emits a command event at word 4. Payload is released as its scheduled words arrive, starting at word 5, with no whole-frame retention. Hardware command/application latency must be specified separately, including direction, acknowledgement and CDC; this reference event is not a timing guarantee.

Consume only the first advertised count of each source's reserved slots. Remaining slots are padding; packing residuals span frames as before. A detected metadata, sequence or range error latches fault. Reset/retraining is required to resume. The reference assumes word/frame alignment and starts sequence zero; acquisition, timeout, epoch and lost-clock handling are not implemented. A six-bit sequence cannot distinguish loss of exactly 64 frames. Word insertion/deletion and correlated errors can release wrong payload before a later metadata failure. No retrospective retraction is possible.

Raw payload corruption is intentionally not detected by this transport. External protocol checks may detect some resulting packet errors, but raw SDR samples and all PHY/control cases are not automatically covered. Train/test both host directions with PRBS, qualify actual timing/BER at the permitted operating envelope and define application error budgets. Metadata protection alone is not host-link qualification.

## Evidence and next implementation step

`make transceiver-stream-codec` tests every one-/two-/three-bit header corruption (20,875 patterns), all 1,308 legal count pairs across the two profiles, sequence wrap/loss, legal-codeword semantic errors, fault/reset behavior, immediate payload release and the intentional payload/four-bit-header error limitations. The parity encoder uses an explicit affine XOR construction; basis checks confirm linear composition. This is aligned reference-code evidence, not RTL/CDC/physical signoff.

Implement a separate v2 RX that retains only the header, validates it before streaming, and checks readiness on every released word. Replace the v1 frame-quarantine stage only after independent reference-vs-RTL and fault-injection checks pass. TX may initially retain snapshot staging; its removal needs a separately verified streaming count/queue policy. Reuse existing CRC v1 as a comparison, not as a permanent mandatory cost. Recompute actual memory, clocks, latency, synthesis area, buffering, timing and current before accepting the new architecture.

## Standalone receiver RTL, pass 25

`rtl/pt_stream_rx.sv` implements the aligned receive path. It stores the 40 protected metadata bits, counters and command state, with no payload quarantine bank. Its schedule function may infer constant ROMs during elaboration; these are not payload storage. `wire_valid`/`iq_valid` are **transfer strobes**, gated by the corresponding readiness input, and sampled with `data=in_word` at the same rising edge. A destination that cannot accept an allocated word causes a sticky fault at that edge and receives no transfer. This continuous source cannot wait. Readiness must come from independently known capacity, not combinational dependence on these strobes. Command outputs are registered after word-4 validation. Payload begins on the following word's edge.

The module assumes a correctly aligned first header after reset and constant mode while armed. It has no training detector, timeout or CDC logic. Pass 28 connects it to `pt_core` through the startup wrapper; the following standalone tests remain useful independent checks. `make transceiver-stream-rx` generates vectors from the independent reference and checks 251,151 cycles, including all count pairs, all 20,875 header corruption patterns, sequence wrap, invalid metadata semantics, sticky/reset behavior, payload corruption and wired/IQ readiness failures. Structural elaboration also passes. Clock period in this simulation is arbitrary; no target-frequency claim follows.

## Standalone transmitter RTL, pass 26

`rtl/pt_stream_tx.sv` implements header protection and v2 slot placement while retaining two transmit staging banks. Frame zero after reset is empty. At word zero, it snapshots min(available count, quota) and the opcode/argument for the *following* frame. Source words are popped into the inactive bank during that frame's payload slots; bank and sequence advance at word 63. Header protection is evaluated from the active bank's stable metadata. This is continuous aligned operation, with no training preamble yet. FIFO counts must describe available complete words, with no competing consumer removing the reserved words; mode is fixed while armed.

Commands stay associated with the same snapshot as their payload even if the command inputs change later. The TX does not silently reinterpret illegal opcodes: it encodes the requested fields, and the receiver rejects unsupported semantics. Only supported commands are to be driven by the eventual controller. Snapshot latency remains one full frame; removing RX quarantine does not remove this TX latency. `make transceiver-stream-tx` checks every output word and pop against independent Python-generated expectations for 1,314 frames / 84,096 word cycles, including all legal count pairs, over-quota inputs, sequence wrap, padding and command changes after snapshot. Structural elaboration passes. No GHz or target-word-clock timing is established.

## Coordinated word-aligned startup, pass 27

`pt_stream_link_tx` holds its payload engine reset while sending eight ten-bit words: 3A5, 05A, 2D3, 12C, 369, 096, 21E, 1E1. The next word is frame-zero header word zero. No source FIFO is popped during training. `pt_stream_link_rx` searches for that exact sequence only while unlocked after explicit reset; repeated first-prefix words restart the match. After the eighth matching word, it releases its payload engine for the next clock edge. Once locked it never scans payload for training markers. Header faults remain sticky until reset. `locked` means the training sequence was seen, not that the first protected header has been accepted or the link is physically qualified.

The receiver must be armed before the finite TX prefix. If no full match arrives in 1,024 receiving clock edges, acquisition faults; a complete match on the last edge wins. The nominal budget is 4.096 µs or 3.2768 µs at the two host word rates. This counter cannot detect a stopped input clock. A reference-domain clock-presence watchdog remains required. Late-joining receivers may miss the prefix and require coordinated restart; no silent resynchronization is promised. An arbitrary incoming stream can imitate any finite preamble; this is an expected-startup protocol, not an adversarial or statistical acquisition guarantee.

The wrappers operate on already correctly assembled ten-bit words. They do not train DDR sampling phase, correct lane skew/bit slips, cross clock domains or qualify timing. The host-control/enable handshake must ensure word alignment and receiver-before-transmitter ordering. Shared physical core integration is still pending.

`make transceiver-stream-link` passes both profile simulations with preamble-prefix noise, normal traffic containing prefix-valued payload words, injected metadata corruption, suppressed transfers after fault, refusal to reacquire without reset, acquisition timeout and explicit restart. Both wrapper hierarchies elaborate structurally. Exact deadline behavior is implemented but not exhaustively tested at all starting phases; tests are synchronous functional evidence only.

## Receive schedule implementation update, pass 29

The integrated receiver now loads two 59-bit predecoded slot masks after the same word-4 metadata acceptance. Their low bits qualify payload transfers and they shift on each payload word. The schedule and interface timing are unchanged; no transfer can occur during header words because masks are reset or exhausted. The implementation adds no release latency. Functional vectors still cover all legal count combinations and metadata-error cases. Physical timing remains failed: header acceptance and schedule loading now form the worst reported host-RX setup path.

## Transmit bank-write staging, pass 37

The TX samples a payload word, its seven-bit destination bank/address and a valid bit on the original source-pop edge. It commits that saved word to the saved bank/address on the next edge. Source pop timing, frame output timing, count/command snapshots and quotas remain unchanged. The final word's commit crosses the frame boundary, so it must use the saved bank bit, not the new `active` value. The new frame emits its header first; the final payload slot is committed before its later read. Reset clears pending validity along with the existing bank reset, preventing a stale commit after restart.

This adds 18 state bits, but no external transport cycle. A retained pre-stage RTL comparison checks 69,824 cycles, including resets at each frame phase in both modes; independent codec vectors and integrated loopbacks also pass. This finite functional evidence does not prove physical timing, CDC behavior or whole-design equivalence.

## Transmit scheduling/count pipeline, pass 39

TX ownership is now registered one word ahead: at position `pos`, decode the legacy schedule at `pos-1` modulo 64 for the following v2 word. Legacy schedule entries outside 3–61 are idle, making all five header words and frame wrap non-popping. Reset initializes ownership to idle. This relies on the existing requirement that mode remains frozen while armed.

At word zero, capture raw source counts and mode alongside the existing command snapshot. At word one, clamp these saved counts to quotas and initialize the inactive-bank metadata and remaining counts. No live word-one count may affect the snapshot. There are no source pops before word five. This combines the pass-38 count-stage experiment with predecoded ownership; the count stage alone was not retained. Source pop timing and emitted frames remain cycle-identical in the finite reference comparisons. The bank-write stage from pass 37 remains in place.

## RF input packing stage, pass 40

The sample packer now has one 24-bit holding register and a valid bit before reservoir insertion. It accepts a sample when that register is empty or when its previous sample will be inserted on the same edge. Reservoir insertion still requires fewer than ten residual bits; complete output words take priority and remain stable under backpressure. A blocked output can leave one additional sample held, but cannot cause unbounded acceptance. Reset discards both held and reservoir data. Mode must remain fixed across the buffered samples, as already required while armed.

This separates asynchronous-FIFO readout from the variable insertion shift. It adds one host cycle to the first output on an initially empty, unstalled path, and changes source acceptance timing under backpressure. It does not promise cycle-identical frame membership near snapshot boundaries; packet/sample ordering and throughput are preserved in the finite tests. End-to-end latency and queue bounds must be requalified rather than inherited from the older implementation.

## Synchronous FIFO flags, pass 41

The two 32-word I/Q transport FIFOs retain their count, storage and boundary policy, but register full/empty flags. On accepted push only, full becomes `count==31` and empty clears; on accepted pop only, empty becomes `count==1` and full clears. With both accepted or neither accepted, count and flags hold. Reset sets count/full to zero and empty to one. Thus flags describe the post-edge occupancy without an additional externally visible cycle.

Acceptance still uses pre-edge flags: at full, simultaneous push/pop rejects the push, accepts the pop and latches overflow; at empty, it accepts the push, rejects the pop and latches underflow. There is no fall-through bypass or full-boundary replacement. This preserves existing behavior instead of silently changing the FIFO contract while optimizing timing. Asynchronous FIFO CDC logic is unchanged by this pass.


## Protocol deadlines and local line events

**Local programmable line behavior.** A bounded sequence of levels, bits,
   bursts, gaps and output-enable states supports SATA OOB, USB chirp/reset/EOP,
   serial idle and training. Programmable envelope detectors work before CDR
   lock. No on-chip SATA link state machine or USB host controller is implied.

**Deadline-aware host service.** Reconfigure the existing transport to eight
words for USB: five unchanged protected metadata/guard words and three raw
payload words, using existing 125 MHz DDR clocks, source slots, queues and two
staging banks. Keep the normal 64-word mode for other profiles. This supersedes
the proposed separate streaming/event path. USB packet decisions and CRC remain
in FPGA; short frames reduce latency without another parallel interface or
on-chip protocol controller. Profile changes still occur only while stopped.


## Executable line and deadline models

`protocol_pad.py` models USB D+/D− as finite capacitances (including mutual and
disabled-branch capacitance), selectable terminations/pulls, FS/LS voltage drive,
HS current drive with compliance, external peer drive and contention rejection.
`ProtocolService.usb_hold` advances those pad states through the canonical ODE;
local current loads WIRE_A, while external source energy is accounted separately.
Reconfiguration requires both drivers released and preserves capacitor state.
This lumped model still lacks package transmission lines, qualified slew, ESD,
USB burst CDR and electrical compliance limits.

The standalone checks cover both host/device roles, attach/reset levels, HS
NRZI plus bit stuffing, release/squelch and contention. Coupled checks cover
both directions, rail droop and capacitor/source/dissipation conservation.
The same solver still owns the existing host output bank and supply return.
No USB negotiation state machine or packet transaction layer has been claimed.

`stream_codec.slots`, `encode` and `Receiver` now accept `frame_words=8`,
reusing the existing header protection, quota, sequence and fault logic. Three
raw wire slots replace the old RF/wired quota split. The existing scheduler and
queue simulator also run this geometry. Tests cover 130 frames per USB role,
sequence wrap, quota overflow, header corruption, four producer phases and a
65×65 response-phase sweep. Default 64-word callers remain unchanged.

`usb_framed_turnaround` bounds the actual two-bank staging structure: less than
one frame until snapshot, one frame until emission, and at most one frame until
the final word is delivered, in each direction. At 250 Mword/s, eight-word
frames provide 937.5 Mb/s raw payload capacity. With 40 ns FPGA processing,
34 ns combined electrical observation/turnaround, four CDC word times, four
queue word times and 20 USB bit times of packing, the bound is 339.67 ns.
This meets the ordinary USB-IF EL_22 8–192 HS bit-time window (16.67–400 ns)
with 60.33 ns remaining, conditional on those unqualified implementation budgets.
An explicit minimum-gap guard applies if a faster configuration could respond
too early. The same conservative staging bound fails for 64-word frames.

No built-in-hub or cable extension is borrowed for the local chip/FPGA budget.
Longer FPGA decisions and queue stalls are tested as failures. This is not a
peer-compliance result. The older 100 ns stress example is not a USB requirement
and is superseded as a design decision by this short-frame comparison.

The canonical lifecycle now selects frame geometry through common receiver,
quota and encoder hooks. USB configuration selects eight words, DDR125 and a
480 Mb/s synthesizer target; it enters acquisition without manufacturing lock.
The return scheduler and host activation monitor use the same geometry. Host
conditioning still requires 4096 word edges (512 short frames), preserving its
duration and provisional activity bounds. Stopped profile changes restore the
64-word geometry. Component tests cover timed return, sequence wrap, abort,
epoch acknowledgement, malformed headers and activation. Baseline 64-word
return/abort and activation checks still pass in both modes.

USB packet admission remains blocked on the canonical chip. A timed pad adapter
and HS burst recovery must connect line events to metadata with correct ordering
after the declared payload count and carry partial final words without corrupting
EOP or external FPGA CRC decisions. Canonical acquired active traffic, the actual
two-bank response schedule and RTL integration remain unverified. The current
timed return component is a functional scheduler, not evidence that the physical
CDC/staging latency budget is met. No new sideband pin or packet engine is selected.

### Generic raw-bit/event transport candidate

`system_model/connected/bit_event_stream.py` owns the bounded raw-bit queue;
`verification/bit_event_codec.py` owns short-frame encoding, streaming decoding
and record-aware snapshots. The chip makes no protocol decisions. Ten-bit data
records precede opaque eight-bit events; an event atomically flushes a partial
word with its valid-bit count. Overflow faults until reset.

The existing protected metadata is reused in an explicitly selected transport
interpretation: `wc` counts 0–3 data words, unused `qc` gives the final word's
valid-bit count (zero without data, otherwise 1–10), operation 3 carries the
opaque event in `arg`, and operation 0 has no event. Partial final words require
an event; interior words contain ten bits. No extra payload tags or sideband
pins are added. Timestamps are not transmitted. The streaming decoder emits
data immediately and the event after the final data; event-only frames emit at
the guard. Consumers must accept two ordered records on the final data edge.
Malformed frames latch a fault, and prior payload cannot be retracted.

`test_bit_event_codec.py` consolidates queue, pad-observation, codec, corruption,
sequence-wrap, snapshot-boundary and stop/reset unit checks. Snapshot tests cover
lengths 0–90 and adjacent bursts; invalid partial boundaries consume no queue
records. `bit_event_schedule_check.py` exercises the finite two-bank schedule:
40 bursts at five phases for each length 9, 10, 11, 23, 240 and 4096 bits deliver
correctly at 480 Mb/s input and 250 Mword/s host, with maximum event latency
83.934 ns. All five one-bit-burst cases overflow: one event per 32 ns frame
supports 31.25 million events/s, below their 53.33 million boundaries/s demand.
The 2 Gb/s overload also faults. Peak raw capacity is 937.5 Mb/s; adding one
payload tag per word would reduce it to an inadequate 468.75 Mb/s. These are
generic fixtures, not USB packet-conformance or turnaround evidence.

The isolated guarded canonical candidate passes normal acquisition and returns
23 coupled pad-voltage observations as 10 + 10 + 3 bits, then an event at
35.04 ns latency. It rejects stopped observations, disabled RX and stale resource
generations, and flushes partial records on stop. Sampling is prescribed and host
decoding ideal. It also passes 13 coupled primitive regression groups and eight
legacy RF/wired return/abort component checks. Evidence owners are:

- `evidence/bit-event-schedule.json`: finite scheduling, including overloads.
- `evidence/record-return-serialized.json`: serialized, guarded coupled pad-to-return test.
- `evidence/record-integration-coupled-controls.json`: primitive regressions.
- `evidence/record-return-legacy-controls.json`: legacy component checks.

The integration is now installed in the main composition: generic resource
commands, serialized raw-record selection, ordered return dispatch and guarded
RF-disabled forecasting. The temporary patch has been removed. The original
control run passed with its source manifest verified; its report and original
source manifest are [archived in Git](https://github.com/deepai-org/svalbard/blob/3300ae71e58f3b244b7d275ebe102b12edcd69dc/projects/programmable_transceiver_platform/evidence/canonical-controls-before-record-integration.json).

`verification/record_return_check.py` is the single integration entry point for
queue controls, receive-format ownership, serialized selection, coupled transfer,
configuration guards and overflow-to-drain behavior. Ordinary serial RX rejects
while raw-record return owns receive transport; disabled RX cannot start return.
Internal queue overflow stops the chip, flushes partial records and prevents
subsequent delivery. The isolated source-checked run passed; fresh main-model
integration, primitive and control regressions are running. Prescribed sampling
and ideal host decoding still leave burst CDR, CDC, physical capture, peer
operation and RTL open. Command fields belong in `integration/macro-contract.md`.

Reference: [USB-IF electrical compliance, EL_22](https://www.usb.org/sites/default/files/USB%202%200%20Electrical%20Compliance%20Specification%28v1.07%29.pdf).


SATA OOB uses six nominal 160-UI bursts with 480-UI reset/init gaps or 160-UI wake
gaps at Gen1 rate. The envelope observer requires consecutive valid widths/gaps
and cannot distinguish electrically identical COMRESET/COMINIT without role.
Tolerance is a declared fixture, not a qualified standard acceptance window.
[Seagate SATA reference](https://www.seagate.com/support/disc/manuals/sata/sata_im.pdf)
and the [USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification)
remain the sources for eventual complete PHY timing tests.

### Loaded host voltage observation

`verification/host_capture_check.py --voltage-screen` samples actual canonical host-output voltage
states after diagnostic launches, rather than decoding the ideal emitted word.
At 250 and 312.5 Mword/s, only one of four stress words is valid halfway through
a word under the explicit external-receiver hypothesis VIL=0.99 V, VIH=2.31 V.
All four are valid at three quarters of the word period; the minimum observed
logic margins there are approximately 442 mV and 67 mV respectively. These
are four-word sample margins, not worst-case timing or noise margins. The source-hashed
`host-voltage.json` records per-word minimum logic margins and forwarded-clock
voltage. This points to required sampling-phase qualification, not a certified
eye opening. No setup/hold, skew, package ringing, PVT or receiver clock-capture
model is included, and these stopped diagnostic launches do not prove acquired
traffic. Ideal host-word observers in other tests must retain that limitation.

The same screen now varies output capacitance by +20% and current limits by
−20%, separately and together, without changing pull resistance or switching
charge. These are uncertainty hypotheses, not PDK corners. At 312.5 Mword/s,
the combined 12 pF / 8 mA case cannot charge an initially low output to 2.31 V
within a 3.2 ns word: even the optimistic bound I·T/C is only 2.133 V.
Moving the sampling phase alone cannot fix that case. At 250 Mword/s, all four
combined-condition words pass at 90% of the period, with a minimum observed
90 mV margin; this late sample does not establish setup/hold margin.

Before selecting a host electrical implementation, constrain board/receiver
capacitance and qualify drive strength and forwarded-clock sampling together.
For the faster mode, 12 pF needs at least 8.663 mA merely to reach the assumed
high threshold at the end of the word, or 11.55 mA by three quarters of it.
These are necessary current/charge bounds, not sufficient design currents:
resistive settling, supply droop, skew and receiver timing still apply.
The model defaults and throughput targets remain unchanged pending that work.

`verification/host_capture_check.py` extends this check to the canonical
forwarded-clock voltage. It samples eight alternating all-bit words at 100 ps
spacing at 312.5 Mword/s, estimates each 1.65 V clock crossing, and intersects
the data-valid intervals relative to those crossings. Each interval reserves
0.2 ns per side for a hypothetical combined receiver timing/skew allowance.
The receiver would need to implement the resulting clock-relative delay;
crossing detection and phase adjustment are not supplied by this test.

The comparison retains nominal drive, the failing 12 pF / 8 mA rising-drive
condition, and a 12 pF / 12 mA rising-drive candidate. Falling limits scale by
the same factors. Increasing only the mathematical current limit leaves device
size, switching charge and pull resistance unqualified; a passing candidate
must be realized and rerun with those effects before it becomes a design choice.
The sampled intersection is not a continuous-time eye or full-pattern guarantee.

The source-hashed `evidence/host-capture.json` completes this finite comparison:
nominal has a common interval 0.950–1.350 ns after the clock crossing (400 ps);
the uncertain case has no common interval; the stronger candidate has
1.024–1.350 ns (approximately 326 ps). These intervals already include the
assumed 0.2 ns allowance per side. They are conditional external capture-delay
requirements, not a measured FPGA receiver capability or chip signoff.

The `--sized-driver` follow-up keeps 12 pF loading and 12 mA rising current,
but scales pull resistance by 1/1.5 and internal edge charge by 1.5, with a
second case at 3× edge charge. This represents a provisional 1.5× driver with
a 20% current derating, plus an extra switching-charge stress. The existing
coupled supply model consumes those edge charges; minimum sampled rail voltage
and consumed/pending switching charge are recorded with the capture windows in
`evidence/host-capture-sized.json`. The proportional sizing rule is an explicit
hypothesis to replace with transistor simulation, not an inferred PDK guarantee.

Both sized-driver cases complete with a sampled 400 ps common interval.
The minimum sampled rail is 3.030 V at 1.5× charge and 2.889 V at 3× charge;
consumed switching charge is respectively 0.924 nC and 1.848 nC. These values
use the coupled owner's charge accounting. The standalone host-bank internal
energy counter is not updated by this composition and must not be used here.

## Opaque multi-lane video transport

HDMI/DVI uses three separate chip host links, each carrying one pre-encoded
10-bit lane. Existing 64-word frames are retained: 720p60 uses 74.25 M words/s
versus 128.90625 M available in mode 0; 1080p60 uses 148.5 M versus 253.90625 M
in mode 1. Blank/control intervals still require symbols: no blanking bandwidth
is assumed free. FPGA rate matching, initial prefill and bounded inter-chip
word deskew must cover independent host framing. Shared reset alone is not a
serializer alignment guarantee. Loss or underflow of any lane invalidates the
whole link; rearm with a common epoch. Capacity checks do not qualify FIFO/CDC
or external GPIO timing. FPGA supplies all TMDS/HDMI semantics.

[HDMI/DVI board and pin plan](../../../docs/roadmap/programmable-transceiver-pin-plan.md#hdmidvi-through-multiple-instances).

The bounded video check now executes a continuous finite TX FIFO using actual
64-word encoder/decoder frames, rather than average-capacity arithmetic alone.
The candidate is 128 words deep with 64 words prefilled before group launch.
An external FPGA fractional quota accumulator emits the nominal lane word count
per frame. The test spans 256 frames, three initial consumer phases and ±100 ppm
consumer-rate error at both video rates. Empty launch, excessive positive drift
and excessive negative drift must respectively expose starvation and overflow.
This is a finite-window TX result: independent clocks drift indefinitely without
feedback. Sustained operation requires a common frequency source or measured
occupancy feedback. Asynchronous FIFO implementation and group
prefill/epoch enforcement remain open; this candidate is not an RTL depth mandate.

The same finite-lane model now checks RX independently: incoming words enter an
initially empty FIFO, each frame advertises only the occupancy observed at its
start, and actual payload slots remove those words while the host decoder checks
order. Arrivals during a frame wait for later headers; no future word is counted
in advance. Both video rates run 256 frames at three phases and ±100 ppm. The
reported conservation identity is produced = host-consumed + pending FIFO words.
One frame without payload service is tolerated; eight paused frames overflow the
128-word candidate, and a four-word FIFO also fails. Pauses retain framing and
represent withheld payload service, not stopped electrical host clocks. This
covers finite RX scheduling under ideal word capture. Clock-domain pointer
synchronization, physical host capture and simultaneous three-lane scheduling
remain open. TX and RX checks are separate simplex use cases.

An external TX rate-controller candidate now uses FIFO occupancy delayed by two
frames to adjust the next frame's fractional word quota, bounded by the existing
wire-slot quota. It never reads the actual consumer frequency or current FIFO
state. The proportional gain is 1/[4(delay+1)] words per occupancy-error word;
initial target occupancy is 64. At both video rates, 512-frame ±1% frequency-error
controls fail without feedback and pass with feedback, with observed occupancy
between 57 and 80 words. The deliberately large drift makes the finite test
sensitive to the controller rather than merely to the preload size.

The delayed observation is currently a model input, not serialized telemetry.
Its encoding, bandwidth, sequence/epoch, stale-report timeout and management
integration are open requirements before this can serve as the actual continuous
stream solution. Do not assume the chip already implements the report or add a
protocol-specific command. Common-frequency operation remains the preferred
initial board arrangement; the generic feedback candidate covers independent
clock operation only within its stated assumptions. Finite tests do not prove
unbounded-time stability or tolerance of arbitrary feedback latency.

## CRC partition rationale and migration history

The following review records the decision behind the default streaming-v2 path.
Its recommendation and migration obligations are historical; the final status
paragraph distinguishes the implemented default from remaining BER/timing work.

**Mandatory whole-payload transport CRC and quarantine are not inherent requirements of this analog/PHY companion.** They were introduced by the custom host-transport design in pass 3, not by a protocol requirement or a demonstrated host-link error budget. Further CRC optimization should not be prioritized until this architectural choice is resolved.

### Evidence and boundary

The existing CRC16 covers the local 64-word chip/FPGA transport frame, including its counts and commands. It is not Ethernet FCS, PCIe packet CRC, or a Wi-Fi MAC FCS. Those protocol functions belong to the external protocol implementation in the intended companion partition.

[Intel's PIPE specification](https://www.intel.com/content/dam/doc/white-paper/usb3-phy-interface-pci-express-paper.pdf), sections 5 and 6.14, describes data/control/status interfaces and explicitly identifies CRC as a higher-level Data Link function. That is evidence for an external-PHY partition, not proof our custom 50-pin interface is PIPE-compliant. [Analog Devices AN-1441](https://www.analog.com/en/resources/app-notes/an-1441.html) describes AD9361 sample-interface timing and PRBS-based interface calibration. This supports a calibrated streaming sample interface as a precedent, not equivalent GF180 electrical performance or a universal statement about all transceivers.

### Recommended revision

Use a deterministic streaming payload path without mandatory per-frame payload CRC or full-frame quarantine. Preserve explicit alignment/training, validity, FIFO underflow/overflow detection, sticky link-fault status, PRBS/loopback and measured timing margins. Protect the small scheduling metadata and fast-control messages separately; define the code/distance, invalid-message behavior and timing before implementation. Keep bulk configuration on the existing separate control path, with readback/appropriate transaction protection. Fast PHY controls still need a bounded hardware path.

Payload bit errors are then part of the host-link BER budget, as on many conventional raw PHY/sample interfaces. Higher-layer checks may detect resulting packet errors, but do not cover every raw sample, control action or ordered set. Raw SDR data can contain undetected errors. That tradeoff must be explicit, backed by host-link characterization and acceptable application error rates. PRBS training does not guarantee error-free operation after training. A CRC placed only in the FPGA cannot reconstruct a checksum of the original D2H data and detect all intervening link errors without some chip-originated redundancy.

A CRC may still be useful for diagnostics or protected low-rate transactions, but it should not dictate the full-speed datapath or require frame retention by default. Streaming CRC with retrospective error reporting would also avoid quarantine, but still costs fast-path logic and cannot retract a waveform already transmitted; it is a separate option, not the assumed solution.

### Original migration obligations (historical)

Do not simply delete the CRC comparison from current RTL: valid counts decide how raw bits are unpacked, and corrupted commands can change hardware behavior. Specify the replacement metadata protection and acquisition/error recovery first. Build a new codec/RTL path, update FPGA adapter/reference models, inject metadata/payload/control errors, and prove ordering, throughput, latency, reset and buffer bounds. Then measure area, timing and power again. Retain the current checked implementation as a comparison until the replacement works.

No measured savings are claimed. Removing CRC quarantine can eliminate receive frame retention and associated mux/control costs; transmit staging is separately required by the current count-snapshot format and does not automatically disappear. CDC/elastic buffering remains necessary. The 1,280 declared receive-bank bits are only a candidate saving, not all 8,576 declared memory bits. Whether CRC-free streaming satisfies every application is unresolved until an explicit error budget exists.

Current status (rechecked): streaming v2 is the default in `pt_core` and `pt_digital` (`STREAM_V2=1`), and contract version 4 describes it. Payload CRC/quarantine is absent from this path; a detection-only extended-Hamming header protects scheduling metadata and fast commands. Legacy CRC v1 remains a compile-time comparison, not mandatory hardware in the default build. Pass 28 in the [archived project journal](https://github.com/deepai-org/svalbard/blob/53f84a75542b80ff2611fc5eb785e680197a6bd9/projects/programmable_transceiver_platform/README.md) records integration tests and measured savings; the migration estimates above describe the original recommendation, not current implementation status. Host-link BER qualification and physical timing closure remain open. The full RF/wired rates, 50 terminals and one-slot target remain unchanged.
