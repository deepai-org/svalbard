# Candidate streaming transport v2

The framed path below serves bulk payload. USB response-critical operation
uses the direct-stream configuration on the same pins; RF profiles require
time-tagged bursts and channel readiness. These are host-interface obligations
on the existing pins, not permission to assume zero-latency FPGA responses.

This is the executable reference for replacing compulsory bulk CRC/quarantine. The framed path has an integrated RTL implementation; direct-stream mode still needs RTL integration. Legacy STREAM_V2=0 is a regression comparison, not another normative design. No chip area, timing or power saving is claimed before implementation and measurement. The current pin and exclusive RF/wired architecture are owned by analog-architecture.json.

## Interface format decision

Keep two encodings on the same physical buses: direct byte streaming for
response-critical bursts, and dense framed transport for sustained wired/IQ
traffic. SPI remains the independent configuration/recovery interface.

| Encoding | Payload capacity per direction | Consequence |
|---|---:|---|
| Direct bytes at selected 100 MHz SDR | 0.800 Gb/s before controls | Suitable bandwidth for the selected USB path; insufficient for maximum-rate I/Q or the fastest wired lane. |
| Hypothetical bytes at 312.5 Mword/s | 2.500 Gb/s before controls | No headroom for a 2.5 Gb/s lane, controls, credits or clock tolerance. |
| Dense 10-bit payload, 59/64 frame efficiency at 312.5 Mword/s | 2.880859375 Gb/s after frame overhead | Preserves sustained 2.5 Gb/s lane capacity with nominal headroom. |

Maximum 40 MS/s I/Q in the current two 12-bit transport words requires
0.960 Gb/s per active direction. RF/wired exclusivity does not remove either
mode's individual requirement. The direct-stream component model also assumes
USB direction exclusivity for credit returns; its timing proof must not be
applied to simultaneous full-duplex wired operation without additional work.

Reuse physical I/O, queues and recovery machinery. Change encoding only while
stopped, with output isolation, queue flush and coordinated training. Do not
raise GPIO speed, consume more pins or discard protection just to claim a single
format. These are two configurations of one chip, not alternate design versions.
`analog-architecture.json:host_transport_selection` owns this decision.

## Sustained-service admission

Admit configurations against the actual FPGA/board word rate, voltage standard,
loading and service schedule. The 312.5 Mword/s ceiling is a requirement, not a
promise for arbitrary GPIOs. The selected board target is 6 pF external load
per output; account for pad/package capacitance separately and consistently.

Compute useful service after headers, credits, control traffic and stalls.
The 59/64 capacity assumes every payload slot belongs to the active engine;
legacy mixed quotas cannot establish that capacity. Check both directions,
including simultaneous wired TX/RX. For each finite queue require adequate
average service and capacity for the maximum accumulated arrivals minus
departures over the admitted stall and clock-tolerance interval. Specify
prefill, maximum service interruption and fault response before launch.

Do not silently repeat/drop samples or line bits to conceal rate mismatch.
FPGA protocol rate matching may change only permitted symbols. Continuous
video needs shared average timing; received traffic follows recovered timing.
An unbounded host stall is incompatible with a continuous stream and finite
storage, regardless of spare nominal bandwidth.

Direct USB service additionally requires its bounded FPGA decision and CDC
latencies; dense throughput is not evidence for response deadlines. Reject an
unsupported board/configuration rather than silently weakening the protocol.

The behavioral resource adapter now accepts a per-direction `host_service`
envelope. `validate_host_service` checks the encoding/board rate ceiling,
recurring service reduction and finite backlog before changing resources.
Its rate-latency guarantee must hold over every backlogged interval; an average
stall percentage alone is insufficient. The supplied latency includes framing,
staging, CDC and bounded interruptions. Legacy fixtures omitting this envelope
remain unqualified. This check does not implement direct-stream dispatch or
prove physical service, and it must not be presented as either.

## Geometry and encoding

Each 64-word frame contains five header words at positions 0–4 and 59 scheduled payload positions 5–63. Words remain ten bits. The existing smooth weighted scheduler uses quotas 33 wired/25 IQ/one idle in the lower profile and 52 wired/seven IQ in the higher profile. Thus nominal capacities and reserved service rates are unchanged. This moves the existing five overhead slots to the beginning of the frame; it does not create extra bandwidth. Source word counts and bit packing retain their meanings.

The intended exclusive-owner allocation assigns all 59 payload positions to the
selected wired or I/Q stream. It keeps the same header, count widths, padding,
sequence and guard. The inactive source count must be zero. Owner selection is
stopped configuration shared with the FPGA; it is not a new protocol identifier
or an in-band automatic format detector. The legacy/exclusive selector is a
model comparison control, not a requirement for another silicon mode bit; the
intended final schedule follows the existing active-engine selection. Nominal payload capacity is 2.3046875
Gb/s at 250 Mword/s or 2.880859375 Gb/s at 312.5 Mword/s. Converter precision
and host clock selection are independent.

This allocation is now an explicit codec/live-model candidate:
`slots/encode/Receiver(..., owner="wire"|"iq")` selects it. Omitting `owner`
retains the legacy allocation above for current RTL comparisons. Short USB
frames retain three wired payload words; short I/Q framing rejects. The fast
chip uses `configure_transport("exclusive")` while stopped, and the live RF
helper accepts independent `host_mode=0|1` and
`transport_allocation="exclusive"`. Connected RF observers now select this allocation by default; low-level
compatibility controls, RTL migration and independent host agreement remain open. Do not claim the wider internal datapath or its
physical timing is implemented by changing the frame schedule.

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

The receiver must be armed before the finite TX prefix. If no full match arrives in 1,024 receiving clock edges, acquisition faults; a complete match on the last edge wins. The nominal budget is 4.096 µs or 3.2768 µs at the two host word rates. This counter cannot detect a stopped input clock. A management-oscillator-domain clock-presence watchdog remains required; REF_IN may itself be absent. Late-joining receivers may miss the prefix and require coordinated restart; no silent resynchronization is promised. An arbitrary incoming stream can imitate any finite preamble; this is an expected-startup protocol, not an adversarial or statistical acquisition guarantee.

The mathematical raw-record candidate now includes an external FPGA
`TrainedRecordReceiver` using that same preamble and 1,024-edge acquisition
limit, plus an independently timed, configurable clock-presence watchdog
(100 ns in the focused fixture). Clock loss faults the receiver even with no
incoming edges. Resumed words cannot clear the fault; explicit coordinated
arming and a complete new preamble are required. Tests stop at every one of
64 frame positions and reject stale continuation before restarting. A complete
preamble on acquisition edge 1,024 wins; a word exactly at the watchdog deadline
wins when processed before the independent timer event. This is a mathematical
receiver test, not physical clock detection or connected source-bank flushing.
Startup and steady clock-loss timeouts must differ when management starts the
link. The existing serialized management model takes 6.45 us to apply an idle
20 MHz SPI request and 12.85 us to finish its reply. Arming a 100 ns watchdog
at submission therefore faults before the preamble; arming after the reply
misses the finite preamble. The external `TrainedRecordReceiver` now accepts a
separate bounded startup wait. A 20 us example permits the idle transaction;
after the first word edge, the 100 ns active timeout applies immediately.
No clock at all still faults at the startup deadline. The startup budget must
also include already queued commands and control-phase uncertainty; 20 us is
not sufficient for every allowed four-command queue. This parameter belongs
to the external FPGA receiver, not a chip protocol profile. A focused composition now dispatches a candidate `restart_raw_return` callback
through the existing management scheduler, including its epoch fence and reply
visibility. With zero/three preceding commands and two control phases, an
external 60 us startup window covers the tested command application (nominally
6.45/45 us). The FPGA receiver remains armed from submission, with no rearm at
application. Source flush, preamble, fresh payload and accepted reply pass;
stale-epoch restart is rejected without restarting the source. This is a named
command fixture, not an allocated SPI opcode or RTL control implementation.
Complete control encoding, reset acknowledgment and interrupted-command handling
remain open.

The source must discard old queued/prepared data during the coordinated restart;
receiver rearming alone cannot establish a fresh epoch.

### Selected bridge recovery sequence

Use one outstanding recovery operation at a time. The independent management
oscillator domain owns the state; SPI transports requests and reads stable
responses. `pt_control.enable` is not a flush acknowledgment. The existing
128-bit behavioral management transaction is not the RTL's 32-bit SPI ABI;
its timing must not be used as evidence for an encoded RTL recovery command.
The candidate encoding below replaces that callback-only contract; RTL integration
and coherent physical mailbox implementation remain gaps.

| State | Required action and acknowledgment condition |
| --- | --- |
| Running → stopping | A host request or sticky transport/watchdog fault disables new publication. Assert pad-safe output independently of host clocks; invalidate FPGA packet/parser state and pacing credits. No new response can be authorized from a partial packet. |
| Stopping → reset held | Assert reset to both ends of each chip block FIFO, all pending commit/return frames, packer residuals, raw capture/playback queues and boundary state. Do not wait for a missing host clock to assert reset. FPGA separately holds its ingress, frame builder and parser in reset. |
| Reset held | Management may report reset asserted and pad safe, but must not report trained, ready or reset released. Asynchronous assertion makes stale storage inaccessible; it does not prove that each clock domain has resumed. |
| Reset held → training | With clocks present, each local domain synchronously releases reset and returns an acknowledgment after its release pipeline. Synchronize those acknowledgments back to management. Keep payload gated. A missing acknowledgment times out to a sticky fault. |
| Training → ready | Arm both receivers before either finite preamble. Both directions must report trained and a valid first header. Clear old sequence counters and establish the new epoch; no payload from a previous epoch survives. |
| Ready → running | Explicit run authorization for the acknowledged epoch enables publication. FPGA pacing must establish a fresh counter baseline and observe progress. Any fault before run invalidates ready. |

#### Recovery mailbox encoding

Use the existing mode-0, MSB-first `command8/address8/data16` SPI transaction
(`0x80` write, `0x00` read). Reserve these candidate addresses, currently absent
from `pt_control`; do not treat them as implemented hardware registers:

| Address | Access | Meaning |
| --- | --- | --- |
| `0x30` | Write | Expected 16-bit epoch shadow |
| `0x31` | Write | 16-bit request tag shadow |
| `0x32` | Write | 0 discard uncommitted shadow; 1 stop/flush, 2 release/train, 3 run; all other values invalid |
| `0x34` | Read | Completed response tag |
| `0x35` | Read | Completed response epoch |
| `0x36` | Read | Bit 15 valid, bit 14 pending; result bits 1:0: success, stale epoch, illegal state, timeout |

Both shadow fields must be freshly written before commit. Clock 32 commits one
immutable request bank, matching `pt_spi`; fewer clocks do not write, extra
clocks do not repeat the write. A pending request blocks all three writes.
COMMIT=0 clears only uncommitted shadow fields and never cancels a pending action.
Cross a publication toggle through two management-clock stages while holding the bank;
return a stable response bank through two SCLK stages. Pending includes that
return crossing. Response fields remain stable until the next accepted commit.
Read status before tag/epoch; allow only one SPI master and one outstanding
request. Software must match tag and epoch, never infer success from zero reads.

Retrying the last completed tag with exactly the same fields returns its cached
response without executing again. Different fields with that tag are rejected.
Tags must not be reused for another operation during a session. Reset before
tag/epoch wrap; an older noncached request is not an idempotent retry. The backend
must validate expected epoch before any state change and complete only the
request it accepted. Invalid/busy writes leave the previous response intact;
a caller cannot treat that previous response as acknowledgment of a new tag.

`verification/recovery_mailbox.py` models transaction atomicity, both ideal
publication crossings and response identity. It does not implement pad safety,
domain reset acknowledgments, backend state transitions or electrical SPI.
Three writes require 96 SCLK periods (4.8 µs at 20 MHz), plus reference crossing
and actual operation time; response polling adds its own transactions. No USB
packet response depends on this management path.

Each response must identify the submitted request and its epoch. A successful
stop/flush establishes one new epoch; retries of the same request must return
the cached outcome rather than incrementing it again. An old-epoch train/run
request is rejected. An interrupted SPI transfer cannot partially apply a
request. Do not reuse an epoch after wrap while stale commands may exist;
require a coordinated full-session reset first. Reading a response is not a
request acknowledgment unless the response identifier matches.

Reset-held, reset-released, trained and running are distinct observable states.
A stopped host clock may leave the bridge safely reset-held indefinitely; it
must not produce a false ready acknowledgment. Loss of the management reference
requires the fail-safe reset/output path, not a software timeout in that domain.
The FPGA may restart a failed protocol transaction only after the complete
sequence; diagnostic preambles do not stand in for target-protocol retraining.

This sequence selects recovery behavior, not a claimed implementation. Closure
requires the same operation to traverse the encoded SPI mailbox, actual domain
reset acknowledgments, both transport paths and FPGA adapter. Existing callback
and isolated watchdog tests prove only their own portions of this sequence.


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
The selected electrical composition can attach the pad branch to the coupled
supply solver; local drive and external peer-source energy must be accounted
separately. Standalone pad controls do not establish that joined composition.
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

**The 339.67 ns comparison does not qualify the newer block/CDC candidate.**
`usb_framed_turnaround(h2d_commit_words=16, h2d_cdc_hz=40e6)` replaces the old
combined four-word CDC allowance with the H2D crossing's three-read-edge visibility
bound and adds the two registered commit beats. The resulting partial bounds are
462.67 ns at 250 Mword/s and 408.27 ns at 312.5 Mword/s. Both exceed the unchanged
400 ns model budget. D2H crossing and further physical margins are still omitted.
The behavioral USB check preserves these as explicit budget failures. They show
that the inherited conservative argument no longer closes, not that all actual
transactions fail or that USB is impossible. Trace actual packet-end to response
start through the intended buffers/control path before selecting a latency fix.

For the selected DDR156 candidate, the H2D control destination is word rate /8
(39.0625 MHz). Assigning three destination cycles to H2D and three word-rate
cycles to FPGA D2H visibility gives 368.47 ns **only with no additional commit
beats**, leaving 31.53 ns for all omitted costs. Keeping the older 16-word commit
allowance instead gives 419.67 ns and fails the 400 ns model budget. The DDR125
comparison already takes 431.67 ns without those commit beats. These arithmetic comparisons do not demonstrate a zero-cost commit path or
physical FPGA timing. Current executable USB timing checks are in
`verification/test_usb_selected_timing.py`. Before claiming USB feasibility, implement
and trace the actual commit/capture pipeline, account for all omitted delays,
and retain the same packet response limit.
The block-host candidate actually schedules commit at collection end plus
16 word periods (`BehavioralChip.transfer`); that allowance is not merely an
unused historical number. At DDR156 it is 51.2 ns. A five-phase event trace of
`BlockFIFO` then observes 51.2–76.8 ns destination visibility at word rate /8,
for up to 128 ns after collection. Reset release is assumed complete. Thus this
candidate must retain the commit cost in its budget. Either shorten the actual
pipeline while preserving header validation and ownership, or demonstrate a
less conservative complete response schedule; deleting the allowance is not a
valid timing fix. This trace is not a full packet response measurement.

No built-in-hub or cable extension is borrowed for the local chip/FPGA budget.
Longer FPGA decisions and queue stalls are tested as failures. This is not a
peer-compliance result. The older 100 ns stress example is not a USB requirement
and is superseded as a design decision by this short-frame comparison.

The canonical lifecycle now selects frame geometry through common receiver,
quota and encoder hooks. USB configuration selects eight words, DDR156 (DDR125 remains a comparison) and a
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

### Selected burst-acquisition boundary

The normative inventory now reserves eight parallel phase samplers and 32 UI
of history, with ordered replay and acknowledged handoff to the tracking CDR.
This supplies the previously missing acquisition/early-bit-retention mechanism;
canonical packet admission remains blocked until that mechanism and the actual
short-frame/CDC path are joined and their total response timing verified.

For the response-critical host rate, select the existing H2D clock as the
conditioned D2H clock source. Do not assume the 480 Mb/s line PLL and an integer
divider happen to supply the nominal DDR156 host rate. This introduces no extra
clock pin, but requires physical return-clock/capture calibration. The saved
latency failures above remain failures; a clock-source selection alone does not
remove their commit cost or prove turnaround.

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

The canonical `stream_codec.Receiver` now exposes this interpretation explicitly
with `raw_records=True`, eight-word exclusive wired geometry and `feed_records`.
It delegates the existing record decoder rather than defining another format.
The ordered-list interface preserves data followed by an event on one input word;
the legacy single-event `feed` API is rejected in record mode. Reset clears the
latched decoder fault and sequence. Ordinary word-stream semantics are unchanged;
record mode cannot be mixed with the legacy discontinuity opcode interpretation.
Both `TimedRecordReturn` and `TimedRecordPlayback` now use this canonical receiver
boundary. This closes the parser-selection gap only: their CDC/scheduling and
pad-event callbacks still need integration with `BehavioralChip` acquisition,
reference loss, STOP/epoch and actual burst sampling. Canonical USB packet
admission remains blocked until that composition exists.

The mathematical `RawBurstPlayback` candidate extends this same explicitly
selected record interpretation to transmit. Data records are raw physical line
levels in least-significant-bit-first order. A configured opaque boundary value
ends the burst and selects released output on the following serializer edge;
it does not encode or recognize USB packets. Storage is bounded to 2,048 data
bits and 16 boundary markers, with markers/control still needing common area
accounting. Underrun faults rather than repeating data; overflow rejects the
whole incoming batch and latches fault. Once faulted, ticks request released
output and queued data cannot restart transmission. The pad-driving integration
must also release immediately when an enqueue/tick exception signals a fault.

This is a modeled candidate, not a new supported RTL command. Explicit format
selection, timed admission/CDC, startup prefill, abort/epoch semantics and
response deadline remain open. Current pad checks preload framed records and
verify exact partial-word termination across consecutive bursts; they do not
establish connected response operation or packet compliance.

`test_bit_event_codec.py` consolidates queue, pad-observation, codec, corruption,
sequence-wrap, snapshot-boundary and stop/reset unit checks. Snapshot tests cover
lengths 0–90 and adjacent bursts; invalid partial boundaries consume no queue
records. `bit_event_schedule_check.py` exercises the finite two-bank schedule:
40 bursts at five phases for each length 9, 10, 11, 23, 240 and 4096 bits deliver
correctly at 480 Mb/s input for both host rates. Maximum observed event latency
is 83.934 ns at 250 Mword/s and 67.184 ns at the selected 312.5 Mword/s.
All five one-bit-burst cases overflow at each rate: one event per frame supports
31.25 or 39.0625 million events/s, below their 53.33 million boundaries/s demand.
The 2 Gb/s overload also faults at both rates. Raw payload capacity is
937.5 Mb/s at the comparison rate and 1.171875 Gb/s at the selected rate; adding one
payload tag per word would reduce it to an inadequate 468.75 Mb/s. These are
generic fixtures, not USB packet-conformance or turnaround evidence.

A generic reply composition now chains the selected receive-event fixture maximum
into a 23-bit response. It uses the existing record codec, two-block-period commit,
two 84-bit CDC entries (full words and partial boundary), and raw playback. Across
25 independent host/destination phase combinations, the latest sampled response
start including assigned three-word FPGA capture visibility and the 34 ns analog
allowance is 348.56 ns. A 200 ns
FPGA-processing control exceeds the 400 ns model budget. The nominal 40 ns FPGA
processing remains assigned. This is finite, generic event-to-reply evidence,
not USB packet or pad qualification; it keeps the raw-record candidate credible
without deleting the commit delay. Summing independent worst-phase waits gives 360.88 ns, leaving
39.12 ns against the assigned 400 ns budget. This conditional bound requires
no older queued frame, one-frame event and response, no CDC stalls, released
reset and fixed clock rates. It includes three word periods of FPGA capture
visibility, 40 ns FPGA work, two commit periods, three CDC periods and one
serializer period. Queue admission, physical timing uncertainty and analog
response must satisfy those assumptions before this can qualify a real reply.
Canonical integration remains open. Evidence stays in `evidence/bit-event-schedule.json`.

Current raw-record and USB integration checks live in `test_direct_stream.py`,
`test_usb_selected_timing.py`, `usb_selected_timing.py` and the selected lifecycle
runner. The former canonical raw-return composition used a superseded chip and
has been removed. Its reported observations cannot establish present pad-to-host
latency, electrical sampling, CDC or recovery. The finite scheduling primitive
above remains scoped evidence; it does not qualify the complete USB path.

Reference: [USB-IF electrical compliance, EL_22](https://www.usb.org/sites/default/files/USB%202%200%20Electrical%20Compliance%20Specification%28v1.07%29.pdf).


SATA OOB uses six nominal 160-UI bursts with 480-UI reset/init gaps or 160-UI wake
gaps at Gen1 rate. The envelope observer requires consecutive valid widths/gaps
and cannot distinguish electrically identical COMRESET/COMINIT without role.
Tolerance is a declared fixture, not a qualified standard acceptance window.
[Seagate SATA reference](https://www.seagate.com/support/disc/manuals/sata/sata_im.pdf)
and the [USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification)
remain the sources for eventual complete PHY timing tests.

### Host electrical capture remains a qualification gate

The current host-load and clock/package screens use the architecture inventory.
They do not establish a GPIO capture window. Pad drive, board load, propagated
clock/data skew, FPGA thresholds, setup/hold and continuous traffic must be
joined before claiming physical capture. The old fixed-current, dual-PLL host
voltage/capture runner and its results have been removed; they cannot qualify
the current chip. Standalone numerical solver checks remain separate from this
electrical timing obligation.

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

### Rate-dependent RF response prefill

The external response planner retains the usual 32 I/Q samples only when they
fit alongside the service-curve backlog in the existing 1,024-bit ingress FIFO.
It caps prefill to `floor((FIFO_bits - backlog_bits)/24)` samples and refuses
launch if that prefill cannot cover the backlog. This is a generic host policy,
not an on-chip BLE profile or a larger storage allocation.

At 37.90625 MS/s with the selected 312.5 Mword/s H2D service, the backlog bound
is 421 bits. Fixed 32-sample prefill would require 1,189 bits and reject launch;
25 samples require 600 + 421 = 1,021 bits. The existing timed-DAC fixture checks
complete playback and independent peer decoding at this rate. Actual CDC and
recurring host-service guarantees remain assumptions requiring implementation.

## CRC partition and remaining qualification

Streaming v2 is the default in `pt_core` and `pt_digital` (`STREAM_V2=1`),
and contract version 4 describes it. Payload CRC and full-frame quarantine are
absent from this path. A detection-only extended-Hamming header protects
scheduling metadata and fast commands. Legacy CRC v1 remains a compile-time
regression comparison, not mandatory hardware in the default build.

Ethernet FCS, PCIe packet CRC and Wi-Fi MAC FCS belong to the external FPGA
protocol implementation. [Intel's PIPE specification](https://www.intel.com/content/dam/doc/white-paper/usb3-phy-interface-pci-express-paper.pdf)
provides precedent for that partition; it does not make this interface
PIPE-compliant. [Analog Devices AN-1441](https://www.analog.com/en/resources/app-notes/an-1441.html)
provides a sample-interface calibration precedent, not GF180 performance evidence.

Payload errors are part of the host-link BER budget. Higher-layer checks do not
cover every raw sample, control action or ordered set; raw SDR data can contain
undetected errors. PRBS training does not guarantee error-free operation after
training. A checksum computed only at the FPGA cannot detect all intervening
D2H errors without chip-originated redundancy. Host-link BER qualification and
physical timing closure remain open.

Alignment/training, validity, FIFO fault detection, protected metadata and bounded
fast controls remain required. Removing receive quarantine does not eliminate
transmit staging or CDC/elastic buffering. Storage and physical pin allocations
are owned by the current contract and board plan, not historical migration
estimates. The superseded migration review and implementation measurements are
recoverable from Git history.

### Connected RF stopped-link watchdog control

The behavioral RF transfer can expose every emitted header, padding and payload
word with its timestamp through `host_word_observer`. A retained test connects
those words to the existing trained watchdog wrapper and ordinary I/Q decoder.
After an injected active clock-qualification fault stops the modeled link, the
independent 100 ns watchdog invalidates the external buffered candidate. Source
pending queues are discarded only by explicit stop; analog state is retained.
This is a stopped-link candidate with assumed initial alignment/training, not a
new status opcode or RTL clock-gating implementation. If the host clock continues
through an RF fault, this watchdog cannot detect it; ordered fault metadata and
its delivery latency remain an explicit integration requirement.

### Provisional running-clock discontinuity header

The mathematical candidate uses protected opcode 3, argument 1, zero wired/IQ
counts to force receiver fault at the next frame header. The default decoder and
RTL still reject this reserved command; `Receiver(..., fault_status=True)` gives
it the explicit discontinuity diagnosis. This is not an adopted RTL ABI.

After detection, finish any started header, replace the current frame's remaining
payload with invalid filler, then send the zero-count discontinuity header with
the normal sequence. `discontinuity_suffix` models those words. No pending source
sample is drained. The receiver must retain candidate packets until the maximum
fault-notification delay has elapsed: detection + crossing + serialization.
Serialization alone is at most 68 word periods (272 ns at 250 Mword/s or 217.6 ns
at 312.5 Mword/s), assuming the next scheduled host edge is available. The slow
frequency-count observer's detection delay is additional; it is not a fast phase
quality monitor. If the clock stops, use the independent watchdog instead.

Tests attach the suffix to actual emitted RF host words and cover all frame
positions/sequence wrap. They show external candidate invalidation, not physical
CDC timing, bounded healthy packet release, standard packet recognition or
coordinated recovery. Neither transport metadata nor filler may be interpreted
as a promise that previously returned payload remains valid.

The external `PacketHoldback` candidate gives completed receiver-validated packets
a finite word budget and explicit notification delay. Release is strictly after
the deadline, so a fault processed at that timestamp can still invalidate the
packet. Overflow faults and clears pending packets; coordinated restart remains
an external obligation. This is not an on-chip protocol block. At nominal
20 MS/s, 12-bit I/Q, a 1 ms detection bound plus 272 ns serialization requires
48,014 ten-bit words (about 60 kB packed) before packet-size/CDC/timing margins.
The active packet buffer is additional. Such storage must be charged to the
external FPGA, and the fault-detection bound must be established independently.

The notification bound is **not established for general RF faults**. A retained
count-observer counterexample remains acquired through a 10 us, +1000 ppm burst
that accumulates 24.12 oscillator cycles. The two-window frequency bound applies
to sustained errors only. Buffer sizing from that bound does not guarantee
transient rejection; a justified fast detector or independent packet-quality
rejection must cover those cases before holdback becomes a delivery guarantee.

Receiver waveform quality produces candidate bits, not verified packet delivery.
The mathematical GFSK observer now reports `candidate_payload_bits` and
`integrity_checked=False`. An external CRC test demonstrates the distinction:
a clean altered waveform can pass quality but fail its unchanged checksum.
Protocol integrity remains in the FPGA; no CRC engine or protocol profile is
added to the chip. Historical diagnostic reports using `delivered_payload_bits`
do not establish integrity or standard packet acceptance.


## Capability-wide service requirements

`verification/check_contract.py` derives `milestone_coverage.capabilities[].host_service`
from the existing operating-clock ledger. It covers all 17 intended interfaces;
no protocol selection is added to silicon. The ledger is the numerical owner,
so changing framing, clock division or allocation changes these requirements
instead of leaving copied capacity tables behind.

For selected external-LO RF, the **word rate is LO/16**, and the **physical DDR
clock is LO/32**: 150–155.25 Mword/s and 75–77.625 MHz over the selected LO range.
The obsolete faster return-clock alternative is no longer included as a selected
service point. I/Q demand is 24 bits per complex sample; the FPGA must choose a
sample divider with sufficient waveform bandwidth and perform any required
resampling. Lower-frequency direct RF has no selected tuning configuration;
external conversion must keep the on-chip frequency inside its qualified range.

Bulk capacity and queue closure are separate. For the 2.5 Gb/s lane, the selected
behavioral scheduler snapshots occupancy at slot zero and drains that quota in
the same frame. Its bound prices one full frame until the next snapshot, the
header, two assigned CDC words and word completion: 587 bits at the declared
±100 ppm extremes. Thirty-two 128-frame traces peak at 560 bits and preserve the
payload prefix, within the 1,024-bit planning allocation. A missed-service control
still overflows. The conditional one-off extra-gap budget is about 175 ns; this
is not permission for recurring stalls.

The older two-frame staging bound remains separately labeled at 1,099 bits. It
does not describe the selected same-frame scheduler and does not justify adding
storage. Actual RTL/CDC and any extra commit latency must establish the selected
service contract; the planning allocation is not a verified physical FIFO depth.
See `selected-lifecycle.json:wired_snapshot_service` and the clock ledger's
`selected_snapshot_d2h_service_bound` for the matched evidence and assumptions.

HDMI/DVI requirements remain per lane, with three separate chip/host-port
instances. USB host and device use the selected direct-stream service; legacy short-frame calculations remain diagnostic only;
that arithmetic does not price all event records or establish reply latency.
Every capability verdict remains unresolved until its electrical, timing,
quality and lifecycle evidence matches these same assumptions.

### Recovered wired data loss policy

A physical CDR source must distinguish initial acquisition from loss after
qualification. The selected policy is to latch the existing stream fault on
that later loss, stop payload release and require the FPGA to discard partial
protocol/alignment state and perform explicit stop/flush/rearm. Invalid startup
samples may be withheld before the first qualified word. Do not concatenate
separated qualified fragments and present them as continuous received data.
This policy uses existing fault/epoch recovery rather than adding a payload gap
encoding or on-chip protocol parser.

The mathematical transfer interface implements this as explicit
`fault_on_rx_loss=True`, with `rx_qualification_lost` reported through its fault
result. It is applied to CDR qualification, not arbitrary empty alignment queues
or intentionally sparse RF sample gates. `--ownership-wired-fail-closed` exercises
it on loaded encoded traffic. This does not prove physical fault notification
latency, serialized status encoding, RTL behavior or resumed protocol alignment.
The default false option remains available for scoped invalid-sample suppression
diagnostics; those do not qualify continuous wired service.

The existing `RXDiscontinuityFaultTests` regression now checks the complete
control-level STOP/rearm sequence after RX qualification loss: the old callback
and epoch are rejected, initial unqualified words in the new acquisition are
suppressed, and a distinct new payload arrives without old queue contents.
Both chunked and uninterrupted service reach the same original fault. This
establishes reusable generic recovery semantics; validity is scripted in this
regression. It does not close the joined loaded-CDR recovery, physical status
transport, FPGA response latency or protocol alignment requirements.

For loaded-CDR recovery, `RecoveredWordSource.discard_through(peer_time)` can
advance the same receiver while host payload is disabled. It retains phase,
qualification and noise state, discards due words, and leaves the first future
prediction uncommitted. It handles the already-committed pending word at a loss
fault. Peer time keeps its original origin; stimulus must cover the entire idle
interval or the operation rejects it. The existing joined 12,000-bit stimulus
covers only 4.8 us, shorter than the assigned 20 us restart, so it cannot establish
this recovery by replaying or resetting its waveform. The regression checks
state equivalence with continuous consumption. A second regression now uses an
80 us peer waveform through the loaded 100 ps driver/2.7 pF pad and selected
CTLE/CDR, including 100 ppm initial clock error, voltage disturbance and the
same injected drought. It executes the full assigned 20 us STOP/rearm interval,
advances the same receiver through more than 49,000 discarded bits, then checks
fresh delivered payload against accepted receiver decisions in a new epoch.
This proves transport continuity relative to the receiver, not independent BER
or protocol alignment. All three `RXDiscontinuityFaultTests` pass; reproduce with
`python3 -m unittest discover -s verification -p test_baseline_envelope.py -k RXDiscontinuityFaultTests`.
The recovery regression now takes its wired DC rail from `selected_environment`
and reuses `shared_supply_disturbance`, the same function as the joined RF/wired
lifecycle: −33 mV source offset, 9.6 mV peak at 10 MHz and fourfold timing
sensitivity. The disturbance continues through discarded data and rearm; all
three recovery tests pass. This remains a steady wired-load case, without the
retained RF/wired load-transition trajectory. The whole-chip lifecycle still
needs the extended peer history and this explicit status/rearm sequence. The
focused test now routes the fault through `StickyFaultPublication`, waits for
100 ns assigned publication and the next 10 us scheduled poll, then allows a
32-clock read at 25 MHz plus 1 us host service before STOP. `wait_faulted` advances
management time with payload and epoch frozen; the same CDR subsequently advances
through the entire delay and restart against the continuing peer waveform.
This is transaction-level publication, not electrical SPI or detector/CDC proof;
physical loss detection latency is not included in that focused test.

### Host-visible CDR fault boundary

The current RTL does not implement the mathematical CDR-loss notification.
`pt_core` accepts `wire_rx_valid`, which also covers initial acquisition, but has
no distinct CDR qualification-loss input. Its `rx_fault` status is the incoming
host-frame decoder fault. `pt_control` exposes the existing status at SPI 0x03;
that read cannot report a cause absent from the core. `RecoveryMailbox` models
requests/replies at 0x30–0x36, not unsolicited loss detection.

The selected requirement is a sticky post-acquisition loss indication retained
in a domain that survives recovered-clock loss, readable over existing management
transport and cleared only by acknowledged stop/flush. No new pin, protocol
profile or register encoding is selected by this requirement. Model the full
detection → publication → host observation → discard → recovery-command sequence
before claiming FPGA recovery. Its numerical latency remains open; pending host
payload must not become irrevocable while it can still be invalidated by delayed
notification. The contract's `epoch_recovery` service owns this requirement.

`verification/recovery_mailbox.py:fault_notification_budget` now makes the SPI
alternative quantitative without adding a register ABI. Its conservative bound
is detection + publication + maximum poll-start interval + 32/SCLK + host service.
Publication includes safe clock-domain visibility; poll spacing includes bus
contention. It deliberately waits for the next complete read instead of assuming
an in-flight read contains the new fault. Unbounded polling/service cannot give a
finite quarantine requirement.

An illustrative 25 MHz SPI, 10 us maximum poll interval, 100 ns detection,
100 ns publication and 1 us host service gives 12.48 us. At 2.5 Gb/s this is about
3.9 kB of FPGA raw-payload quarantine (the conservative floating-point ceiling
returns 3,901 bytes), before metadata, word rounding and protocol buffering.
No additional chip payload storage is assumed. These values are a service-budget
candidate, not selected physical timing; the loss detector and status publication
are still unimplemented in the selected bridge. The phase-sweep regression checks
poll scheduling and rejects overlapping polls or infinite service bounds.

`StickyFaultPublication` retains the first `(epoch, cause)` until an observed,
matching fault is acknowledged after a new-epoch STOP. It needs no subsequent
recovered-clock edge. Reads before the assigned publication delay see no fault;
stale acknowledgements and unobserved clears are rejected. This behavioral
snapshot deliberately leaves register encoding open and does not allocate chip
payload storage. It connects notification to the focused loaded recovery test;
the original RTL status gap and whole-chip integration requirement remain open.

## Current response-critical implementation requirement

The [direct-stream service](block-diagram.md#selected-response-critical-host-service)
is the selected USB path: 100 MHz SDR raw-byte/control/parity beats, finite CDC
and credits, with a 120 ns FPGA decision allowance and 342.25 ns response bound.
Framed transport remains for other configurations. Earlier short-frame results
in this document are scoped model evidence, not the selected USB implementation.
Physical qualification and full-chip/RTL integration remain open.

## Atomic RF gain metadata

On exclusive RF H2D frames, opcode4 with wc=qc=0 requests an atomic gain update.
Argument bits6:5 select LNA −6/0/10/20 dB; bits4:0 select matched I/Q PGA −6..42 dB
in 3 dB steps; bit7 is zero. Validate protected header, guard, sequence, ownership
and acquisition permission before committing. Permit one pending update only.

D2H opcode4 echoes gain; wc now reports 0..63 invalid/discarded complex sample
pairs, qc counts new-gain payload words. There is no wired payload under RF
ownership. Complete already-staged old-gain frames, discard stale samples at
commit, and invalidate settling samples. Restart I/Q packing at the gain-status
frame boundary; FPGA discards any old partial pair and advances its sample index
by wc before accepting new-gain samples. Count wc from the first pair not yet
completely delivered: it includes a discarded partial pair, if any. Do not add
another sample for that partial pair. A zero count with a partial pair is invalid. Bound pending stale samples to24pairs
for the fast service and reject fast updates whose total gap would exceed63.
No truncation of the gap count is allowed. Status has reserved next-frame
priority; ordinary management cannot extend the three-frame transport budget.
`verification/rf_gain_command.py` defines the encoding and FPGA-side
`GainSampleReceiver`, which consumes actual10-bit words, resets packing on
validated gain status and emits timestamped pairs/gaps. The Python stream
receiver accepts this only with explicit exclusive-RF opt-in. It assembles
initial snapshots and buffers their payload on the FPGA until all six
fragments validate. `BehavioralChip.arm_rf_gain_transition`
now accepts an already-delivered protected command and supplied settling count,
finishes announced old-frame words, discards actual stale/settling samples and
emits opcode4 before new-gain data through the existing finite queue. It rejects
an incomplete snapshot or another pending action. The commit index is the
zero-based RX event index, not the48-bit snapshot counter. Callers must price
H2D/CDC arrival and map indices explicitly. The Wi-Fi gain-feedback screen
connects this queue path to downstream PGA
settling and sample-driven host decisions, including snapshot-aware assembly.
H2D parsing remains represented by the charged delivery bound. The FPGA
controller gates one gain correction with short-training correlation; physical
settling, initial-gain overload/sensitivity tradeoffs and full HE acquisition
remain unqualified.
Legacy Receiver RTL still rejects opcode4.

Warm-hop sample epoch uses protected exclusive-RF opcode6 without payload. The
16-bit epoch occupies wc[5:0], qc[11:6] and the argument low nibble[15:12]. The
argument high nibble is3 for H2D arm,1 for D2H ready-for-ack and2 for H2D ack.
Normal transport sequence remains intact. Enforce direction/phase and expected
epoch; drain before epoch wrap. This command changes converter sample ownership,
not GPIO framing. `rf_gain_command.py` defines the complete metadata encoding.

## RF sample-time descriptors

The current inventory `rf_sample_timing` defines generic RF-only metadata
opcodes7 (H2D timed launch) and8 (D2H sample snapshot). Launch uses four
consecutive protected metadata-only frames,18bits per fragment: wc6 + qc6 +
argument low6; argument high2 is fragment index. Descriptor order is counter48,
epoch16, reserved8=zero. Reordered, stale or partial descriptors never arm output.

RX snapshots instead use six IQ-carrying frames,11timestamp bits per fragment:
wc6 + argument low5; argument high3 is fragment index0..5. qc retains the normal
IQ word count0..59. Counter48 + epoch16 + reserved2=zero names the first complex
pair in the first fragment frame, which starts fresh pair packing and must have
payload. FPGA assembles the timestamp while buffering its ordinary IQ payload.
Subsequent frames continue packing. Fast gain commands are admitted only after
snapshot completion; the FPGA waits for all six validated fragments before
issuing one. Reject an early fast gain command without changing gain, rather
than deferring its status beyond the promised three-frame command budget.
Gain-status metadata must not interrupt a snapshot. This avoids the FIFO overflow that a metadata-only timestamp pause
could cause. No extra on-chip sample storage is allocated.

Frame sequence advances normally. Existing wired and direct-byte meanings are
unchanged. `verification/rf_timing_command.py` is the reference encoding;
legacy receiver RTL does not implement these opcodes yet. BehavioralChip now
accepts a completed launch descriptor into an opt-in sample-event gate using
actual ingress occupancy; its caller must charge descriptor transport arrival.
Initial RX snapshot emission is integrated alongside actual IQ payload, with
finite FIFO occupancy and bit-exact payload checks. Resnapshot after
discontinuities and nonuniform converter timing remain open; the opt-in
service rejects delayed-RX clock providers rather than using them as TX clocks.
FPGA translates
converter-edge counts into antenna time with measured path delay. A launch
that misses its target or lacks16-pair prefill is canceled. No board-ready pin:
FPGA sequences external PA/antenna switch. Four launch fragments plus wait/stage
reserve cost six H2D frame periods. Snapshot completion takes six RX frames but
does not displace IQ payload; FPGA accounts the retrospective timestamp.
