# Parallel internal datapath candidate, pass 55

The current 10-bit word-rate digital core fails global-route-estimated setup by more than 11 ns at a 3.2 ns host-word period. More placement legality or a narrow supply/temperature agreement does not remove that gap. Explore an 80-bit, eight-word internal transport beat while preserving both existing external profiles, all frame bits, 50 terminals and the full wired/RF companion scope. This is a candidate architecture, not an implemented replacement or a speed claim.

## Current exclusive-owner model

The mathematical block receiver now takes the same fixed `owner='wire'` or
`owner='iq'` setting as the scalar codec. All 59 payload slots belong to that
owner; no extra header field, package terminal or simultaneous RF/wired use is
introduced. The legacy split schedule remains an explicit comparison default.
Owner is fixed when constructing the receiver; live switching is not supported.

`verification/check_block_receiver.py` compares both host modes and 2/4/8-word
blocks against the scalar decoder. It covers every 0–59 exclusive count, the
legacy count combinations, all 50 single header-bit corruptions and protected
metadata that illegally requests inactive-owner payload. Invalid headers produce
no effects and latch fault. The eight-word exclusive case can emit **eight words
to one destination per beat**, replacing the lower legacy peaks quoted below.

This removes a model scheduling inconsistency; it does not migrate the block RTL
or make its storage/CDC/physical timing pass. Before main-model integration, use
one fixed-block transaction with a valid count up to eight, retain partial words,
and account for collection, two-stage commit, actual queue capacity and CDC
latency. The behavioral whole-chip transport now optionally collects H2D words into
eight-word beats and commits each atomically two host block periods later. D2H
staging and decoder/command effects remain unintegrated. Optional H2D CDC
visibility now follows the checked fixed-block FIFO model. No timing closure is claimed by scalar/vector
content equivalence.

### Live H2D staging check

`BehavioralChip.transfer(tx_word_observer=...)` exposes each actual consumed
word and its absolute consumption time after staging/CDC. The observer binds
for the stream lifetime, receives prefill as actually consumed, and receives
nothing on an immediate underflow. A +100 ppm H2D/40 MHz CDC test checks exact
timing, consumed-bit accounting and uninterrupted versus 3+13-frame equivalence.
`EmittedWordChannel` now attaches an ideal-cadence ten-bit serializer, the
existing one-pole channel and an external CDR to that boundary. Sampling beyond
elapsed or supplied history is refused; forecasts do not commit receiver state.
Two 64-frame runs with ±100 ppm initial receiver error recover 3,276 words,
with 3,076 scored words error-free after a 200-word diagnostic guard. Tests
also preserve split-run equality and reject a discontinuous launch cadence.
Histories are diagnostic storage, not on-chip buffers. The 31-test codec suite
passes. This remains TX-only with prescribed serializer timing, not autonomous
clock, standard framing, simultaneous RX or physical qualification.

`BehavioralChip.transfer(host_block_words=8)` retains one collection beat and
up to three pending entries (including same-time arrival before commit). It
preserves the frame count snapshot at word zero. Host charge occurs at the pin
word event; destination FIFO bits become visible only at block commit. A block
that does not fit faults without partial acceptance. At equal times, converter
consumption precedes commit. Pending blocks persist across transfer chunks; stop
reports staged bits separately from destination FIFO bits. No extra switching
charge or physical CDC behavior is inferred from these registered stages.

At 2.5 Gb/s with the high host rate, an 80-bit initial fill survives the former
immediate-word delivery but underflows at 32 ns with staging, before any block
commits. A larger fill survives; this is a latency requirement exposed by the
model, not a reduction of line-rate goals. `host_block_staging_controls()` checks
this negative control, ordered payload, chunk equivalence, atomic capacity failure,
stop accounting and timed RF conversion. Whole-chip closure still needs D2H
staging/crossing, complete clock/reset envelopes, actual command semantics and
physical boundary timing. The optional scalar path remains a comparison.

### Checked mathematical block CDC semantics

`verification/block_receiver_model.py:BlockFIFO` models the existing eight-entry
block FIFO with two receiving-clock pointer stages and per-domain two-edge reset
release. Every accepted block advances the pointer once regardless of valid-word
count. Simultaneous edges sample the same pre-edge pointer state. Full and empty
are derived from synchronized remote pointers, so freed capacity and newly written
data do not become visible immediately. Invalid accepted counts fault without
occupying storage; reset assertion flushes both domains together.

The existing block-receiver checker now compares this model directly against
`pt_block_fifo`/`pt_async_fifo` RTL over 2,400 event ticks, including unrelated and
coincident edges, a stopped read clock, invalid counts and three resets. An
independent transaction scoreboard checks ordering (260 accepted writes and 252
reads; resets discard queued entries). This checks ideal digital edge semantics,
not metastability, skew, memory implementation or independent reset safety.
`transfer(host_block_words=8, host_cdc_read_hz=40e6)` now inserts this crossing
between staged commit and destination bit-queue visibility. The destination clock
and fractional phase are explicit assumptions. Write/read edges that coincide
use one pre-edge snapshot; the write clock runs even for empty payload beats.
A nonempty commit refused by full CDC storage faults the continuous source. The
read side waits until an entire block fits in the destination queue. Collection,
pipeline, crossing and destination bits have separate conserved accounting; stop
discards the remaining bits explicitly. The bit-queue enqueue represents a
functional unpacker, not a timing-qualified variable-width hardware gearbox.

At 2.5 Gb/s, 40 MHz destination service passes three tested phases with exact
payload order and transfer-chunk equivalence. A 31.25 MHz service clock underflows:
partial blocks consume read cycles, so 80 times the clock rate overstates useful
payload service. A separate stalled-consumer case fills all eight crossing entries
and reports `host_cdc_full`. Timed loaded-PLL GFSK also passes through the crossing
at 5.9704% EVM with exact split equivalence. These finite fixtures do not establish
arbitrary-phase/drift closure, CDC physical margins or the extra clock's power.
D2H staging/crossing and actual command effects remain open.

### Storage and clock budget reconciliation

The current live H2D option has a 2,048-bit destination queue plus modeled
capacity for one eight-word collection beat, three pending beat entries and eight
crossing entries. At 80 payload bits plus four valid-count bits per entry, the
additional representable storage is 1,008 bits (960 payload + 48 count), giving
3,056 bits including the destination queue. This is a model-capacity inventory,
not an exact flop count: the simultaneous-event pending entry may share physical
collection/stage registers. Header/control, pointers, reset, D2H and gearbox
implementation storage are not included. Do not silently assign all of it to the
old 2,048-bit queue budget.

The existing mapped block FIFO (eight 84-bit entries plus control) has 707 flops
and 76,568.576 µm² of standard-cell area, about 9.01% of the 850,000 µm² memory
allocation. Its RTL, mapping artifacts and Liberty fingerprints were checked
before reuse; no new synthesis or layout was performed. This one block's cell
area does not establish the complete memory/digital fit or placed utilization.

`report_block_fifo_mapping.py --lib <original-liberty>` now derives clock-pin
loads from that mapped netlist and its exact original library. At nominal 3.3 V,
690 write-clocked flops present 2.199204 pF and 17 read-clocked flops present
0.056882 pF. Q=C·V gives 7.2573732 pC and 0.1877106 pC per respective rising
edge. At 31.25/39.0625 MHz write service and 40 MHz read service, their pin-only
supply estimates are 0.773194/0.960299 mW. These exclude internal cell power,
clock drivers/wires, data activity and rail transfer; they are conditional
nominal calculations, not a physical power guarantee.

`timed_cdc_host` remains the uncharged comparison. The `cdc_charge_0.0`,
`cdc_charge_0.1` and `cdc_charge_1.0` cases now inject these actual write/read
clock-edge charges into the live shared rail and PLL with explicit 0/10/100%
effective coupling. They give 5.97039/5.96952/5.97026% EVM respectively for the
same 1,024-bit GFSK fixture; full coupling injects 328.397 nC and retains exact
split-run samples and accounting. Small nonmonotonic differences do not establish
an improving trend or an operating envelope. The unchanged 10% screen remains.
An independent RC impulse sum checks edge charge/voltage accounting. This closes
only active FIFO clock-pin charging: internal cell power, clock-tree wires and
buffers, destination gearbox, and startup/parked clock lifetime remain missing.
The zero-coupling case is a control, not the selected physical implementation.

### USB deadline consequence

The wider path cannot inherit the older short-frame USB turnaround result.
Replacing its four-word combined CDC allowance with H2D three-edge visibility at
40 MHz and adding two commit beats gives 462.67/408.27 ns partial bounds at the
two host rates, against the model's 400 ns limit. D2H crossing is still absent.
This is a failed conservative budget argument, not proof that every response is
late. Actual packet-end/control/response composition and reduction of existing
buffering latency are required before claiming this architecture supports USB.

## Rate and latency accounting

| Words per internal beat | Internal width | Low-profile clock | High-profile clock | High-profile period |
| --- | --- | --- | --- | --- |
| 2 | 20 bits | 125 MHz | 156.25 MHz | 6.4 ns |
| 4 | 40 bits | 62.5 MHz | 78.125 MHz | 12.8 ns |
| 8 | 80 bits | 31.25 MHz | 39.0625 MHz | 25.6 ns |

Multiplying each internal width by its clock preserves the external 2.5/3.125 Gbit/s host bandwidth per direction. The 64-word frame divides exactly into all three beat sizes. Collection alone delays a word by zero through B−1 external word periods. For B=8 this is up to 28 ns in the low profile and 22.4 ns in the high profile. Metadata becomes available after word seven instead of word four, adding 12/9.6 ns of collection delay before any processing or clock-domain application. Gearbox handoff, pipeline latency, source drift and output reserialization costs are additional; PCIe command/data latency is not qualified.

The 80-bit candidate offers a longer nominal logic period than the current measured critical paths, but vector decoding, storage, loading, clocks and pin conversion all change. Existing slack cannot be transferred to the new architecture. The 40-bit alternative's 12.8 ns period cannot be assumed sufficient merely by dividing the clock in half twice.

## Executable receive scheduling

`verification/block_receiver_model.py` accepts aligned 2/4/8-word blocks. It assembles protected metadata across blocks, validates it before effects, and selects each source's payload lanes using their rank within the block and the remaining count before that block. Outputs carry lane indices to preserve relative command/data ordering. Counts update once per block. It does not call the scalar receiver to produce its outputs.

The independent scalar comparison covers all 1,308 legal count pairs for each beat width, continuous sequence wraps, and every single-bit corruption of the 50-bit header in each mode/width. Corrupt metadata emits no effects and latches a fault. This does not prove all multibit cases, RTL equivalence, reset-domain behavior or clock timing.

At eight words per beat, individual maxima are five wired and four IQ payload words in the low profile, and seven wired and one IQ word in the high profile. Low-profile maxima need not occur in the same beat; a beat always has at most eight words total. Existing single-enqueue FIFOs cannot accept these vectors directly. Local storage needs multiple enqueue/dequeue support, banking or block storage with counts and residual handling.

## CDC and physical obligations

Do not advance an ordinary Gray-coded pointer by a variable multiword count. Multiple pointer bits can then change in one source update, defeating the existing one-step CDC reasoning. Use fixed block-sized storage transactions with pointer increments of one block, carry partial words locally, and explicitly define valid counts/ownership for partial blocks if supported. A block FIFO count is not interchangeable with the existing word count. Prove empty/full, simultaneous operation, reset, partial-block flushing and end-to-end ordering before integration.

Widening only the host side is insufficient: the wired FIFO input/output domains also fail their 4 ns checks. The analog serializer/deserializer boundary would need a compatible wider parallel interface or a verified fast local gearbox. For example, eight 10-bit wired symbols imply an 80-bit boundary at 31.25 MHz for 2.5 Gbit/s, or 15.625 MHz for 1.25 Gbit/s. These are on-chip macro connections, not extra package pins. Word alignment, electrical idle, receiver detection, CDR/SSC handling and control latency still require explicit design.

The host physical macro must perform actual DDR capture/launch and block assembly at the external rates. No standard-cell clock divider, inferred high-speed shift register or combinationally gated clock is assumed to solve that. Clock phase generation, source-synchronous margins, CDC constraints, reset/training alignment and safe clock stopping remain implementation obligations. The eight-word startup prefix happens to divide into these beat widths but does not establish physical alignment.

TX frame membership must retain a defined count-snapshot epoch. Moving count capture to the end of a collected beat silently changes which source words belong in a frame. Model TX snapshots and gearbox buffering explicitly before replacing the existing transmitter. Fast controls may need a separately bounded path if batching delay is incompatible with the selected protocol.

Next implement and verify one fixed-block CDC/storage path, then the vector RX engine, before selecting the whole-core rewrite. Measure mapped/placed area, switching/clock load and latency rather than assuming that a wider/slower core is smaller or lower power. The existing RTL remains the tested comparison; no current full-chip capability or target rate is reduced.

## Standalone block CDC foundation (pass 56)

`rtl/pt_block_fifo.sv` stores eight transactions, each containing eight ten-bit
words and a four-bit valid-word count. Valid words occupy lanes 0 through count−1;
unused lanes are transported unchanged but have no payload meaning. Counts 1–8
are legal. Each valid/ready write handshake with an illegal count is discarded,
sets a sticky write-domain fault, and consumes no FIFO entry. Fault does not halt
later traffic. A producer must hold requests while not ready; a consumer takes
one complete block on read-valid/read-ready. Output data is unspecified when
read-valid is low. There is no partial-block read or per-word occupancy output.

The existing asynchronous FIFO stores all 84 bits atomically and increments its
Gray pointer by exactly one block per accepted transaction. As corrected in pass 57, the wrapper gates handshakes with the actual
per-domain storage reset-release signals. There is only one release synchronizer
per domain; a separately synchronized copy is unsafe. Both clock domains must share reset assertion; reset
flushes queued blocks and the fault. Independent resets are unsupported. Physical
reset recovery/removal and synchronization remain implementation obligations.

`make transceiver-block-fifo` checks unrelated 10 ns/14 ns clocks, random legal
and illegal counts, full backpressure, empty reads, many wraps, a reset during
traffic and final drain against an independent transaction queue. All eight legal
counts occur at least 100 times. Source Gray transitions are checked for at most
one changed bit. Two deliberately faulty variants (overwritten count metadata and
admission of invalid counts) must fail the scoreboard. Queued blocks are
flushed by the midstream reset; accepted/received totals therefore
need not match, while the final post-reset drain must match exactly.

This is a standalone candidate, not integrated transport. Fixed simulation clocks
are finite functional evidence, not metastability/Gray-bus-skew qualification,
all-clock-ratio verification, physical dual-clock-memory signoff or timing/area
closure. Physical reset distribution still requires recovery/removal analysis; sharing
the release signal removes the logical disagreement but does not establish
physical reset timing.
Further integration must explicitly account for partial-block fill latency and
word counts; block occupancy cannot replace the transport's payload word counts.

### Receiving register screen (pass 59)

The separate `verification/pt_block_fifo_capture.sv` fixture samples all 84 output
bits on a read handshake. It adds 84 unreset data registers; captured data has no
meaning before the first read. There is no additional queue handshake or change
to the candidate FIFO. Its timing fixture uses 4 ns illustrative input/output
budgets and a 25.6 ns block period, and screens all capture bits by mapped endpoint
connectivity. The nominal read-domain paths pass. Storage-to-capture propagation
is also measured, but its 25.6 ns max-delay allocation is provisional. Derive the
minimum write-to-capture stability interval and read-to-reuse interval under
arbitrary phase, synchronizer delay, stalls and reset before treating this as a
qualified asynchronous bundled-data crossing. The following passes supply the
logical derivation and nominal hold screen; routed delay/skew and hold
constraints remain required. Positive nominal slack alone is insufficient.

### Block FIFO stability windows (passes 60–61)

This derives logical bounds from the actual two-stage pointer synchronizers in
`rtl/pt_fifo.sv`. It applies after coordinated reset release and assumes coherent,
causal pointer observations: a destination sees an old or newer published pointer,
never an invented value or a pointer going backwards. Gray-bus physical skew,
synchronizer resolution/MTBF and reset behavior must establish those assumptions.
A finite digital simulation cannot do so.

#### Publication

Let W be the edge that writes a slot and advances the write pointer. Let R1 be
the first read edge at which stage 1 samples that published pointer or a later
one. R2 transfers that observation to stage 2. Transfer decisions at R2 still
use the old stage-2 value; R3 is the earliest edge that may consume the new slot.
Thus W-to-capture is at least two read periods, with the infimum approached when
W is immediately before R1. Stalls and later pointer visibility increase the
interval. Slots farther behind the head are older; batching pointer observations
does not permit a read before the observation traverses both stages.

With variable periods, use the minimum possible sum of the two intervening read
periods, including jitter and operating limits, not twice an average period.
A 25.6 ns constant read period gives a logical 51.2 ns floor. The provisional
25.6 ns storage-path allocation in pass 59 therefore leaves logical room, but
is not signoff: bound data launch/propagation, setup, physical clock uncertainty
and margin against the actual minimum interval. The consumer must capture only
on `rd_valid && rd_ready`, and no bypass of synchronization is allowed.

#### Storage reuse

A consumed slot is freed at read edge R. The read pointer must pass writer stages
1 and 2 before a write decision can use the freed capacity. The earliest reuse
is at least two write periods after R, by the same pre-edge decision argument.
This bound applies to storage overwrite, not to output hold. The current slot
selection changes immediately after R as `rb` advances, even while its old
storage data remains untouched. Pointer-to-output mux contamination delay and
capture-clock skew therefore need a conventional same-domain minimum-delay/hold
check. Delayed reuse cannot substitute for it. Read-valid/enable changes also
need hold analysis, as does the receiving register's feedback path.

#### Executable evidence and limits

`make transceiver-block-windows` enumerates 188 cases over six period pairs,
every integer relative phase for each pair, and two random seeds. It models
pre-edge simultaneous decisions, eight slots, producer/consumer stalls,
additional coherent stage-1 visibility delays, pointer wraps using unbounded
logical sequence numbers, and coordinated reset flushes. It checks ordering,
occupancy, publication age and reuse age for 294,021 reads and 292,439 reuses.
The smallest sampled intervals are 2.032258 read periods and 2.04 write periods;
these finite observed minima do not replace the analytic two-period bound.
A one-stage negative control fails the publication-window assertion.

This model is not RTL equivalence. It abstracts binary sequence numbers rather
than simulating analog synchronizer resolution or Gray-bit propagation. Its
reset flush discards transactions and inserts blank intervals; it does not
qualify reset release hardware. Real metastability may yield more than a clean
one-cycle delay, so the observation assumptions require physical justification.
Next check minimum-delay paths and constrain Gray-pointer skew/max delay in the
placed implementation; retain CDC correctness as unproven until those checks and
appropriate formal/RTL evidence agree.

#### Nominal minimum-delay evidence (pass 61)

The pass-59 receiving-register fixture now has a separate hold screen. It uses
zero earliest `rd_ready` arrival, 0.5 ns input transition and 5 fF capture-output
loads. All 84 capture endpoints are covered for pointer, feedback, ready and
read-domain path classes. Nominal minimum slack is 1.1485 ns, limited by ready;
pointer and feedback minima are 3.0055 ns and 1.2647 ns. The explicit uncertainty
sensitivity test reduces slack one-for-one and intentionally fails at 5 ns.
This only establishes a nominal unplaced baseline. Do not use these values as
minimum silicon delay bounds: fast cells, load/slew changes, local variation,
clock-tree skew and routed hold analysis remain required. This check also does
not turn the asynchronous storage-data path into an ordinary same-clock path.

### Two-entry receiving buffer (pass 65)

`rtl/pt_block_elastic.sv` wraps the candidate eight-entry asynchronous block FIFO
with a two-entry, 84-bit-per-entry synchronous FIFO in the read domain. This is
an actual candidate receiving stage, not an assumed external launch delay.
The asynchronous FIFO's read-ready is `local_active && !full`; `full` is registered.
External downstream ready affects the local synchronous FIFO's next state, not
combinational acceptance from asynchronous storage. This removes that particular
external-ready path to the CDC capture register without relaxing a constraint.

The wrapper preserves ordering and valid-word counts, including partial blocks.
Invalid-count handling remains in the upstream block FIFO. Both storage stages
flush on shared reset. The local buffer uses its own synchronized reset release,
and that exact release gates both its upstream ready and downstream valid, so it
cannot acknowledge data while its storage remains reset. A later upstream release
only postpones transfers; it need not match the local release cycle.

Total storage is ten blocks; the extra two entries cost 168 data bits plus control.
There is no empty fall-through: a newly accepted local block becomes available
after its capture edge. A full buffer cannot accept a replacement on the same edge
as a pop, but becomes available the next cycle. With one resident entry, concurrent
push/pop sustains one block per cycle. No claim of zero bubbles after arbitrary
full/stall transitions is made. Downstream readout is still a local mux; its timing
and the full-flag launch path must be physically checked.

The generated test reuses the independent block transaction scoreboard with
asynchronous clocks, delayed reset releases, illegal counts and random stalls,
then saturates the producer and consumer. It observes 1,071 consecutive reads.
A deliberately corrupted stored payload fails the scoreboard. This is finite
RTL simulation, not CDC/metastability proof, mapping equivalence or timing closure.
The original integrated transport and prior timing fixtures are unchanged; next
map this stage and measure the actual registered-capacity path before adoption.

### Registered ingress candidate (pass 69)

`pt_block_staged` adds one 84-bit holding register and valid state ahead of
`pt_block_elastic`. Its local synchronized reset release gates acceptance and
resets that same state. An empty ingress may accept before the downstream CDC
has released reset; it then holds the block until downstream ready. These releases
need not coincide. Ingress ready is `active && (!held_valid || next_ready)`.
An occupied entry can transfer and be replaced on the same edge, preserving
one-block-per-cycle throughput. When blocked, data/count/valid remain held.

Invalid accepted counts are discarded and faulted in the ingress domain. They
cannot overwrite a blocked valid entry because readiness is low. When an old
entry is transferred and an invalid new request arrives on that edge, the old
transfer completes, the holding valid clears, and the fault latches. Shared reset
flushes all stages. The full chain stores up to eleven blocks: one ingress, eight
CDC entries and two receiving entries. The ingress adds at least one write-clock
edge before CDC insertion; protocol latency must be updated before integration.

This is a candidate launch structure, not proof that the entire external interface
meets timing. The upstream block assembler must drive the holding register under
a real timing contract. Ready still has a combinational return path to that source,
and downstream `rd_ready` remains input-driven. A source/capture path cannot be
qualified simply by moving the unconstrained boundary outward. Mapping, CTS and
end-to-end source/consumer timing remain necessary. No default transport changes.

### Ordered lane compaction (pass 70)

`pt_lane_compact` is a combinational eight-by-ten-bit primitive. `selected[i]`
selects lane i, with lane zero earliest in stream order. The output packs selected
words into consecutive low lanes, preserves order, emits a four-bit count 0–8,
and zeros every unused lane. Zero-valued payload remains valid data; there is no
sentinel encoding. It has no clock, buffering, handshake or metadata validation.

The wider receiver must form masks after validating the header and clipping each
source's scheduled lanes to its remaining count. Wired and RF masks can both be
nonzero in one beat: instantiate separate compactors or prove a time-shared
implementation meets both outputs' service requirements. Do not silently serialize
the two sources through a single block-per-cycle resource. When a compactor emits
count zero, suppress the downstream block write; the block FIFO intentionally
rejects zero-length transactions. Nonzero outputs need storage/ready handling;
a combinational compactor cannot absorb backpressure or prevent a source overrun.

`make transceiver-lane-compact` tests 8,192 independent expected-output vectors,
all 256 masks with zero, all-one, lane-tagged and random payloads, and a reversed
source-order negative control. Structural synthesis succeeds. This does not prove
all payload bit combinations, optimized mapping or timing. The variable placement
network is only a first implementation; measure its mapped depth/area with the
header/count logic before committing the complete wide receiver.

### Eight-word schedule/count routing (pass 71)

`pt_block_route` takes beat index 0–7, mode, two six-bit remaining word counts,
an 80-bit beat and `allow_payload`. It emits two independently compacted ordered
blocks, their counts, and updated remaining counts. Each lane uses the existing
v2 schedule (legacy owner index = absolute position − 2), excludes positions 0–4,
and decrements only the corresponding nonzero remaining count. Both sources may
produce a block in one cycle. When disabled, both outputs/counts are zero and
remaining counts are unchanged. No state or side effect occurs inside this module.

For beat zero, the caller must supply counts from the validated header in that
same beat and assert allow only after all header checks pass. It must not use old
frame counts, release payload before validation or apply candidate next counts
unless the beat is committed. Later beats use committed remaining counts. Count
range validation, sequence checking, commands, acquisition, ready/capacity checks
and sticky fault behavior remain caller obligations. This primitive deliberately
does not invent a policy for a beat whose two source queues have different readiness.

The test compares against independent scalar slot consumption for all 1,308 legal
starting-count pairs in both modes, across every beat, with allow both enabled
and disabled: 20,928 vectors. It checks both packed payloads, counts and residual
counts, including zero/full quotas and the first/last beat. A one-slot schedule
offset mutation fails. Structural synthesis passes; variable prefix decrement and
compaction may still be too costly after mapping. No integrated receiver or physical
timing claim is made. Remaining-count inputs above legal quotas are outside the
validated caller contract and not tested as accepted frames.

### Parallel header validator (pass 72)

`pt_block_header` consumes the low 50 bits of the first eight-word beat: four
protected header words and the guard. It checks tag, extended-Hamming syndrome,
overall parity, guard, expected sequence, mode-specific source quotas and supported
command/argument combinations. It performs detection only, with no error correction.
Count and command outputs are zeroed when `good` is false. The caller must still
gate payload and command effects with `good`; zero-valued decoded fields do not
constitute validation. Later beats must not be reinterpreted as headers.

The combinational decoder has no fault latch, reset, acquisition or frame state.
It can feed beat-zero counts directly into `pt_block_route`, but the combined
header-validation/count/routing path needs timing measurement. If pipelined, hold
all same-beat payload until its header decision and preserve command/queue ordering.
Do not restore payload quarantine merely to simplify this connection.

The 51,510-vector check covers all 1,308 legal count pairs, 20,875 weight-1/2/3
corruptions in each mode around a chosen codeword, every expected sequence with
matching and mismatching received sequences, all 4,096 opcode/argument pairs per
mode, and explicit over-quota counts. Independent Python decoding supplies expected
results, including zero outputs on rejection. A missing-syndrome mutation fails;
structural synthesis passes. This is finite combinational RTL evidence, not a
formal proof over all headers, physical timing or integrated fault behavior.
The existing distance-four limitation remains: some four-bit changes produce a
valid different header. This primitive adds no payload CRC or stronger protection.

### Aligned wide receiver and beat commit (pass 73)

`pt_block_rx` joins header validation, both routing outputs and frame state. Reset
starts beat zero/sequence zero. The mode must remain fixed while active. Each
`in_valid` beat is eight already aligned words; an invalid cycle holds state and
emits no effects. There is no input ready or permission to stall a physical
continuous stream. A real gearbox must supply every beat or explicitly report loss.

At beat zero, validated header counts feed routing in the same combinational path.
A beat commits only if its header is valid (when applicable) and every nonempty
source output has destination readiness. Empty outputs do not require readiness.
On commit, nonempty source transfer strobes and data/counts are sampled at the
edge, next counts become state, beat advances and sequence increments at frame
wrap. The first beat also emits a command strobe and its fields on that edge.
As corrected in pass 74, first-beat commit also requires `command_ready`.
This promises command acceptance at that edge, not completed hardware application.

Any bad header or refused required output suppresses BOTH payload outputs and
any same-beat command, freezes frame/count state, and latches fault at the edge.
Subsequent beats have no effects until shared reset. This policy is atomic per
beat, not per frame: earlier committed beats cannot be recalled. It intentionally
differs from scalar word-by-word fault timing, where earlier words within the
failed beat might already have transferred. Ready must mean capacity for an entire
block and must not depend combinationally on these transfer strobes. Output words,
counts and command fields are zero when their beat is not committed.

The 17,842-cycle test derives normal payload/commands by feeding the independent
scalar `Receiver` eight words at a time, then applies the specified atomic capacity
policy. It covers all 1,308 legal count pairs over continuous frames/sequence wrap,
invalid input cycles, all 50 single-header-bit corruptions per mode, all three
refusal combinations at every beat with full quotas, post-fault suppression,
restart, zero-payload readiness and a wrong starting sequence. A capacity-bypass
mutation fails. Structural synthesis passes. This is aligned finite RTL evidence,
not a complete acquisition/CDC/queue or command-application implementation. It
adds no CRC, replay, automatic resynchronization or physical timing guarantee.

### Command capacity participates in commit (pass 74)

The aligned RX now takes `command_ready`. Every first beat emits one command
record, including no-op, and therefore requires space in the command destination.
If command readiness is low, the first beat has no command or payload effects
and latches fault just as a refused required payload output does. The input stream
cannot pause or retry that beat. Later beats ignore command readiness. Zero-payload
frames still require command acceptance; idle input cycles require none.

This is a local synchronous handshake, not a CDC protocol or guarantee that RF
mute/wired-idle changes have already reached their physical destination. A future
command queue must generate ready from actual capacity independent of the RX
command strobe, retain ordered fields, and define application latency and failure
behavior. Do not tie command_ready high without an always-accepting implementation.

The expanded 21,202-cycle test includes all five supported opcode/argument pairs,
with and without payload, all eight wire/IQ/command readiness combinations in both
modes, command-ready low on subsequent beats and no silent restart after a fault.
Independent scalar decoding supplies command content; the separate beat policy
checks atomic refusal. Both whole-capacity and command-only bypass mutations fail.

### Separate header capture from routing (pass 76)

`pt_block_rx_pipe` retains the unpipelined candidate for comparison and adds a
single-beat input stage. At the input edge it captures the 80-bit beat, beat index,
header decision and decoded counts/command. An input-domain beat counter and
sequence counter advance only for incoming valid beats. Header sequence validation
therefore uses the incoming frame's sequence, including at back-to-back frame wrap.
Only beat zero uses the stored header decision/fields. Mode remains fixed while
active; this stage does not permit live mode switching.

The next edge commits the stored beat using CURRENT destination readiness and
committed remaining counts. The previous beat's count update supplies the next
beat after that edge. First-beat decoded counts replace old frame residuals.
An input bubble does not cancel the older pending beat. Command and both payload
streams retain atomic per-beat acceptance; refusal cannot stall the continuous
source, so it faults. On a failing commit, newly arriving younger work is discarded
and later effects are suppressed. Older committed work is not recalled. An invalid
younger header does not retroactively suppress an older valid pending beat.
Shared reset flushes the pending beat and both input and committed frame state.

This adds one block-clock latency to effects, nominally 32/25.6 ns for the two
profiles, while allowing one beat per clock. It stores one beat, not a frame, and
does not add CRC quarantine. Transfer strobes refer to stored output data, never
current input words. Readiness observed at arrival is irrelevant to the later
commit; actual queue capacity at commit is required.

The 21,219-cycle test uses scalar decoding delayed by an independently maintained
pending-beat model, then applies current readiness. It preserves earlier functional
coverage and explicitly changes command readiness between arrival and commit in
both directions. Reset flushes pending work, idle input cycles drain older work,
and continuous frames exercise sequence wrap. Capacity bypass, command-readiness
bypass and using live input valid instead of stored valid are all detected.
Structural synthesis passes. This is a candidate partition only; mapping must
show whether both pipeline stages meet timing before adoption.

### Capture schedule masks alongside the beat (pass 78)

`pt_block_rx_mask` is a separate candidate with the same one-beat latency and
commit policy as `pt_block_rx_pipe`. On each input capture it decodes two eight-bit
schedule masks from the incoming beat index and fixed mode, and stores them beside
the beat/header fields. The masks exclude positions 0–4 and are disjoint by the
existing owner schedule. They describe the stored beat, not the next incoming beat.
Input bubbles preserve association through the stored valid flag. Fault/reset
suppression means unreset mask data cannot authorize an output.

`pt_block_route_mask` clips these predecoded masks against remaining counts and
compacts both sources. It assumes disjoint header-excluding masks supplied by its
caller; it does not validate arbitrary user masks. Counts, header validity,
readiness and atomic commit remain in the existing stage. Thus schedule decoding
moves before the capture registers without increasing latency; a beat-zero count
mux and count/compaction logic still remain after them. Timing improvement is not
established until mapping, and the input schedule-decoding path must also be timed.

The 21,219-cycle delayed scalar reference still passes. Four mutations are rejected:
capacity bypass, command readiness bypass, live-valid substitution and capturing
the next beat's mask. Structural synthesis passes. No cycle-equivalence proof,
physical timing or integrated queues are claimed.

### Rank-based count clipping (pass 80)

`pt_block_route_rank` replaces the serial remaining-count decrement chain. Each
scheduled lane compares its prefix population count against the original remaining
count. A source's consumed count is min(total scheduled lanes, remaining count)
when enabled, and residual count is computed by one subtraction. Prefix counts
depend on schedule bits only, not on the previous lane's count comparison. The
existing ordered compactor is reused. This changes dependency structure without
adding state, buffering or latency. Synthesis may still implement prefix additions
or compaction poorly; speed must be measured rather than inferred from the RTL.

`make transceiver-route-rank` proves the complete output tuple equivalent to
`pt_block_route_mask` with Yosys SAT for all binary inputs: both eight-bit masks,
all eighty data bits, both six-bit counts and allow. The proof does not assume
mask disjointness or legal frame quotas, and includes packed data, counts and
residual counts. Replacing a strict rank comparison with >= fails the proof.
This is combinational two-state equivalence, not X/reset or physical timing proof.

The separate `pt_block_rx_rank` candidate substitutes this router in the registered
mask pipeline. `make transceiver-block-rx-rank` passes 21,219 reference cycles and
the existing four mutations, with structural synthesis. Other candidates remain
unchanged. No mapped area/timing or whole-chip performance claim is made yet.

### Compact schedule first, trim count afterwards (pass 82)

`pt_block_route_prefix` uses each stored schedule mask directly in its compactor.
It computes accepted count as min(schedule population, remaining count), gated
by allow, and zeros packed output lanes at or above that accepted count. Remaining
counts are decremented once. Because count clipping always retains the first N
scheduled words, this is equivalent to clipping the mask before compaction. The
compactor's word-placement network now depends on schedule and payload only;
remaining count and allow drive only count selection and final lane masking.
No new registers, latency or queue behavior are introduced.

`make transceiver-route-prefix` proves the full output tuple equal to the original
serial mask router for every binary input, without assuming disjoint masks, legal
quotas or a particular payload. A <= boundary mutation that leaks one extra packed
lane fails the proof. `pt_block_rx_prefix` is a separate integrated candidate;
21,219 reference cycles and four fault/control mutations pass, as does structural
synthesis. Existing candidates remain unchanged. Formal equivalence does not
predict mapped depth, area or physical timing; those measurements are next.

### Separate routing from output commit (pass 85)

`pt_block_rx_commit` adds a second stage after the existing capture/header stage.
Routing computes packed payloads/counts and stores them with header validity,
first-beat indication and command fields. Destination capacity and final output
gating operate on those stored results in the following cycle. The accepted input
therefore commits two block clocks later, adding one cycle versus the prefix RX,
while preserving one incoming beat per cycle. Data is retained for two beats, not
quarantined for an entire frame.

Residual counts now describe planned routing, not committed output: they advance
when a valid stored beat routes, before downstream acceptance. If its eventual
commit fails, all younger in-flight work is invalidated, the sticky fault blocks
all further effects, and recovery requires reset of planning and commit state.
There is no rollback/replay mechanism. This is safe only with that fail-stop
policy; speculative residuals must never survive a restart or be used for external
accounting. An older valid beat may commit while a younger invalid header moves
through routing; the younger fault must not retract older work.

A command and both nonempty payload blocks still commit atomically using current
readiness. A first beat with invalid header or insufficient capacity faults at
its commit edge, not at arrival/routing. Input bubbles shift pending work through
the stages and emit no newly invented beat. Shared reset discards both stages.
Command-application and protocol latency budgets must include the total additional
64/51.2 ns at the nominal low/high block periods, plus all surrounding stages.

The 21,254-cycle reference maintains an independent two-entry pending-beat delay
and performs scalar decoding at commit. It includes all prior ordering/count
coverage plus explicit oldest-command refusal with younger work in flight and
reset with both stages occupied. Four mutations are detected: capacity bypass,
command bypass, wrong-stage valid and next-beat mask. Structural synthesis passes.
No stage timing, mapped equivalence or actual queue/CDC integration is claimed.

### Raw-record return grouping candidate

The connected request/reply model optionally groups D2H data before publishing a
FIFO entry. A lone record may wait one additional 40 MHz edge; a second record
or boundary permits publication immediately when FIFO space is available. This
uses the existing record queue and fixed-block FIFO, plus a one-edge hold state.
The bounded wait avoids indefinite latency for sparse data. Source preparation
and its timing remain a functional assumption. With external FPGA TX pacing,
this reduces long-burst return backlog; see the measured cases and remaining
400 ns misses in [risk priorities](risk-priorities.md). The ungrouped baseline
remains checked. No host format, extra terminal or protocol-specific command is
introduced by this scheduling option.
