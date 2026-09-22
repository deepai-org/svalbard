# Candidate streaming transport v2

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
