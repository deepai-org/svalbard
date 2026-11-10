# Host streaming transport

Two stopped-selected encodings share the ten-bit H2D/D2H pins: dense framed
transport for bulk wired/IQ payload, and direct bytes for response-critical
bursts. SPI is the independent configuration/recovery interface. Protocol
parsing, CRC/FEC and bulk storage belong to the FPGA. `host_transport_selection`
and `direct_stream_service` in `analog-architecture.json` own the selection.

## Sustained-service admission

Dense frames provide 59 payload words per 64 ten-bit words: 2.3046875 Gb/s at
250 Mword/s or 2.880859375 Gb/s at 312.5 Mword/s. Exclusive engine ownership
assigns all payload slots to wired or I/Q; inactive-source counts are zero.
Direct bytes at 100 MHz SDR provide 0.800 Gb/s before controls, sufficient for
the selected USB path but not maximum-rate I/Q or a 2.5 Gb/s serial lane.

Maximum 40 MS/s complex samples require 0.960 Gb/s for two 12-bit transport
values. Actual direct-LO rates derive from carrier/divider. Board GPIO rate,
load, voltage, stalls and both directions must be admitted explicitly; ordinary
GPIOs are not universally capable of the ceiling. The selected external output
load target is 6 pF, with pad/package capacitance accounted separately.

Finite queues require average service and a bound on accumulated arrivals minus
departures over every admitted interruption and clock-tolerance interval. Define
prefill and fault behavior before launch. Never repeat/drop samples or line
bits silently. A recurring average stall percentage is not a service guarantee.
`validate_host_service` checks a supplied per-direction rate/latency envelope;
it does not prove physical GPIO or CDC performance.

## Geometry and encoding

Frames have header words 0–4 and payload slots 5–63. `owner="wire"|"iq"` selects
exclusive ownership in the reference codec. Source counts describe complete
words; unadvertised slots are padding, and packing residuals span frames.
The RTL uses exclusive dense framing. Stopped-only
`digital.transport_config.payload_iq` selects wired (0) or I/Q (1); MODE8 still
selects I/Q sample width.

Metadata is 30 bits: wired count [5:0], IQ count [11:6], sequence [17:12],
opcode [21:18], argument [29:22]. Shortened extended Hamming is detection-only:
positions 1–36 have parity at 1,2,4,8,16,32; data occupies the other positions
in ascending order, least-significant first. Parity subsets are even. Encoded
integer bit36 is overall even parity, bits37–39 are tag101. Words0–3 send
least-significant ten-bit chunks first; word4 is guard0x2d3.

Validate parity, tag, guard, sequence, ownership, counts and command legality
before any frame effect. Never correct a syndrome: a triple error could become
accepted incorrect metadata. The code detects every one/two/three-bit header
change, but some four-bit changes are valid codewords. Tag/guard do not prove
acquisition because payload can imitate them. Six-bit sequence cannot distinguish
loss of exactly 64 frames.

After validation, payload is released as its scheduled words arrive without
receive-frame quarantine. A destination that cannot accept a word faults rather
than backpressuring a continuous source. Detected errors latch fault until
explicit reset/retraining. Corruption discovered later cannot retract released
payload. Payload has no transport CRC; protocol integrity is external and raw
samples require a separately qualified error budget.

## Implementation and command boundary

`pt_core` instantiates `pt_core_pair` and `pt_dense_pair_link_tx/rx`. Two chronological ten-bit words
are processed at 156.25 MHz; the external ten-bit word port stays at 312.5 MHz.
The receive side
validates metadata before releasing payload, rejecting nonzero inactive-source
counts. TX starts with an empty frame, then reserves available words near the
end of each preceding frame. It subtracts every still-advertised current-frame
word before reserving the next frame; no other consumer can drain that source.
Credit arithmetic and parity are pipelined before header publication. Payload
words come directly from the source FIFO on their advertised beats, with no
full-frame staging bank. Commands and counts share the same snapshot.

The wired ingress CDC FIFO is 64 pairs (1280 storage bits). The paired framer
counts complete FIFO pairs plus its held odd word before the 59-word clamp.
Its next-frame snapshot is pair beat24 of32 and subtracts all current-frame
reservations. A one-word guard payload can leave a held odd word across frame
boundaries; chronological order remains unchanged. The prior 32-pair FIFO
overflowed in the full-rate test. `make transceiver-dense-transport` checks 840
frames against the independent codec, including both owners and 112 negative
cases. `make transceiver-dense-service` runs both wired directions at 312.5 MHz
host / 2.5 Gb/s line for 200 µs at five clock phases, checking word order and
FIFO faults; a 250 MHz host case must reject overload. These are functional RTL
checks, not physical timing, clock-tolerance or interruption qualification.

`make transceiver-dense-pair` independently codec-checks the selected paired
engine: 720 frames, 235 odd-word carry cases and 114 corruption/refusal cases.
`transceiver-dense-pair-link` checks training, both word alignments and five
capture phases for both owners. The I/Q TX and RX queues hold twelve and seven
pairs. RX admission uses its registered full flag; downstream unpacker
readiness affects dequeue only.
RF ingress holds eight samples; a 32-entry, 24-bit egress FIFO is shared with
the wired owner. Its read clock selects the stopped owner's output clock;
disable asserts queue reset even while clocks are stopped, with synchronous
release after restart. Changing owners requires disable and a queue flush.
`transceiver-shared-egress-lifecycle` checks both transitions with stopped
host and output clocks. `transceiver-sync-fifo-depth` independently models
wrap, overflow, underflow and reset for the seven/twelve-entry conservative
queues, plus full replacement in the generic six-entry lookahead case. The nibble-based sample/pair converters accept and emit simultaneously; `transceiver-pair-gearbox` checks every occupancy with
backpressure/reset, and `transceiver-dense-rf-service` checks both directions
at 40 MS/s for both sample widths over five clock phases.
`transceiver-dense-rf-burst` also checks actual full 59-word H2D frames with
finite FPGA buffering and a bounded initial burst followed by 40 MS/s service.
These smaller queues do not establish an interruption or clock-drift allowance.

Fast launch uses local per-bit phase drivers and synchronized reset release.
`transceiver-pair-word-formal` proves coherent phases and the low-word capture
window. Only the twenty launch-pair registers have a two-word setup path;
fast word-register paths remain 3.2 ns. A kept GF180 clock buffer isolates
divider feedback from the engine clock tree. Full physical timing, storage
and area closure remain open.

Base commands are no-op(arg0), wired-idle(arg0/1) and RF-mute(arg0/1). Extensions
below are normative behavioral encodings, not all implemented in RTL. Reserved
or context-illegal commands fault. Direct-stream mode and additional metadata
still require model/RTL integration. The analytical service bound needs
reconciliation with the actual reservation lookahead and CDC latency before
it qualifies interruptions or clock tolerance.

## Coordinated word-aligned startup

The TX wrapper holds the payload engine reset while sending
`3A5 05A 2D3 12C 369 096 21E 1E1`, then starts frame0/header0. RX searches only
while unlocked after reset, with a 1024 receiving-edge acquisition timeout.
Once locked it never scans payload for training markers. Arm RX before TX;
a missed prefix requires coordinated restart. Seeing the prefix does not prove
header acceptance, DDR phase, lane alignment or physical timing.

An independent management-clock watchdog must detect a stopped host clock;
a counter clocked by that host cannot. Stop/isolate outputs, acknowledge domain
resets and queue flush, establish a new epoch, train both directions, then run
only after both sides qualify. Discard partial packet/sample/alignment state
on a fault. No stale epoch can rearm a lane.

### Recovery mailbox encoding


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

## Direct response-critical stream

USB uses 100 MHz SDR raw-byte service on the same ten-bit buses. Each beat has
eight chronological LSB-first bits, a data/control flag and even parity.
Controls: IDLE0, START1, END2, ABORT3; 0x11–0x17 announce 1–7 valid bits in the
next partial data beat followed by END; 0x40–0x5f return modulo-32 FIFO credits.
Parity/order/padding faults invalidate the stream. Change encoding only while
stopped with isolation, flush and coordinated training.

RX consumes at 100 MHz; TX FIFO/gearbox consumes at 240 MHz derived from the
480 MHz line clock. Price two synchronizer edges plus a consumer edge. TX
prefills four bytes, uses eight-entry credits and bounds returns to four host
cycles. FPGA must always accept RX; USB half-duplex leaves return service for
credits during TX. These assumptions do not qualify full-duplex wired traffic.

The assigned FPGA decision allowance is 12 host cycles (120 ns). The connected
model's 342.25 ns reply bound has 57.75 ns margin against its 400 ns gate.
This is conditional timing evidence, not physical CDC or USB compliance.
The detailed budget is in [the architecture](block-diagram.md#selected-response-critical-host-service).

## Fault and delivery semantics

A qualified CDR losing validity faults the stream and suppresses further data.
Do not concatenate qualified fragments across the loss as continuous data.
Startup invalid samples can be withheld before first qualification. Recovery
requires explicit stop/flush/rearm and FPGA disposal of partial protocol state.

The modeled running-clock discontinuity uses opcode3,arg1 with zero counts at
the next header; it is opt-in in `Receiver(..., fault_status=True)` and not an
implemented RTL extension. Finish a started header, invalidate remaining payload
slots and send fault status with normal sequence. Serialization is at most
68 word periods if the host clock continues; detection and CDC are additional.
Use the independent watchdog if the clock stops.

Any FPGA packet holdback guarantee requires a demonstrated fault-detection
bound. Average-frequency qualification does not detect every transient phase
fault. Received candidate bits are not integrity-checked packet delivery.
No on-chip packet parser, payload CRC or packet RAM is implied.

## Capability-wide service requirements

All 17 interfaces are covered by the operating-clock ledger, not on-chip
protocol IDs. For carrier-derived RF return, physical D2H clock is LO/32 and
DDR words are LO/16: 75–78.125 MHz and 150–156.25 Mword/s over 2.4–2.5 GHz.
Stable-host hopping uses the separately selected host-follow clock source.
FPGA resampling follows the actual sample divider and new epoch.

The selected same-frame wired snapshot service has a conditional 587-bit
backlog bound within 1024 bits; RTL must demonstrate that schedule and latency.
Additional staging or recurring stalls need a new bound. Continuous Ethernet
and video require sustained rate matching; video has three independent lane
chips/ports plus common timing/alignment. USB host and device each require the
direct-service electrical and timing lifecycle.

## Atomic RF gain metadata


On exclusive RF H2D frames, opcode4 with wc=qc=0 requests an atomic gain update.
Argument bits6:5 select LNA −6/0/10/20 dB; bits4:0 select matched I/Q PGA −6..42 dB
in 3 dB steps; bit7 is zero. Validate protected header, guard, sequence, ownership
and acquisition permission before committing. Permit one pending update only.

D2H opcode4 echoes gain; wc supplies the low six bits and argument bit7 supplies bit6 of the
0..127 invalid/discarded complex sample-pair count, qc counts new-gain payload words. There is no wired payload under RF
ownership. Complete already-staged old-gain frames, discard stale samples at
commit, and invalidate settling samples. Restart I/Q packing at the gain-status
frame boundary; FPGA discards any old partial pair and advances its sample index
by the decoded gap before accepting new-gain samples. Count the decoded gap from the first pair not yet
completely delivered: it includes a discarded partial pair, if any. Do not add
another sample for that partial pair. A zero count with a partial pair is invalid. Bound pending stale samples to24pairs
for the fast service and reject fast updates whose total gap would exceed127.
No truncation of the gap count is allowed. Status has reserved next-frame
priority; ordinary management cannot extend the three-frame transport budget.
`verification/rf_gain_command.py` defines the encoding and FPGA-side
`GainSampleReceiver`, which consumes actual10-bit words, resets packing on
validated gain status and emits timestamped pairs/gaps. The Python stream
receiver accepts this only with explicit exclusive-RF opt-in. It assembles
initial snapshots and buffers their payload on the FPGA until all six
fragments validate. `BehavioralChip.arm_rf_gain_transition`
accepts an already-delivered protected command and supplied settling count,
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
The existing Receiver RTL does not implement opcode4.

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
existing receiver RTL does not implement these opcodes yet. BehavioralChip now
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

## Verification

`make transceiver-stream-codec`, `transceiver-dense-pair`,
`transceiver-dense-pair-link` and the wired/RF service checks exercise the
codec and selected RTL. The word-at-a-time FPGA peer lives in
`sim/reference/pt_dense_transport.sv`. The model
suite covers generic gain, epoch, sample-time and direct-stream behaviors with
explicit scope. These checks do not establish target-frequency timing, complete
RTL parity with the selected model, BER, pad behavior or physical recovery.
