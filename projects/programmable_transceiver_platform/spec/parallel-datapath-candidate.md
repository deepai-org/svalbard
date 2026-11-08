# Parallel internal datapath implementation

The selected host interface and control semantics belong to
[streaming transport](streaming-transport-v2.md). This document describes reusable
wide-datapath implementation blocks and their remaining integration obligations.
The mathematical model is not a timing-qualified digital implementation.

## Required structure

The word-rate digital implementation misses its 3.2 ns setup target by more than
11 ns in global-route-estimated timing. Narrow voltage/temperature operation does
not remove that measured gap. An eight-word, 80-bit internal beat preserves
external word throughput while giving 25.6 ns per beat at 312.5 Mword/s, or
32 ns at 250 Mword/s. DDR capture/launch, serializer/deserializer boundaries and
gearboxes still need actual high-speed circuits and physical timing closure.

RF and wired payload ownership is exclusive. The mathematical block receiver
accepts fixed `owner='wire'` or `owner='iq'`; all 59 frame payload slots belong to
that owner. A beat may deliver eight words to one destination. Ownership changes
require a stopped/reinitialized stream. The block RTL has not completed migration
to the selected transport's exclusive schedule and full command set.

Do not infer USB turnaround from this dense-frame path. The selected USB path is
the 100 MHz direct byte stream documented in the transport owner. Its modeled
342.25 ns response is conditional on the 120 ns external-FPGA decision allowance;
full RTL and physical timing remain unqualified.

## Reusable implementation

- `block_receiver_model.py` assembles protected headers, validates metadata before
  effects, and routes aligned 2/4/8-word beats by payload rank and remaining count.
  Invalid metadata emits no effects and latches a fault.
- `pt_block_rx_commit` separates header capture, payload routing and output
  commit. Accepted input commits two block clocks later while accepting one beat
  per clock. Command and nonempty payload destinations commit atomically according
  to current readiness. Refused commit invalidates younger work and requires reset;
  speculative routing counts cannot survive recovery.
- `BlockFIFO` models eight fixed-block entries with two receiving-clock pointer
  stages and two-edge per-domain reset release. Simultaneous edges use the same
  pre-edge state. Invalid accepted counts fault without occupying storage.
- The optional behavioral H2D block path retains collection, pending stages, CDC
  and destination occupancy separately. A block commits atomically or faults.
  Chunked execution retains pending state; STOP accounts for discarded data.

Do not increment an ordinary Gray-coded FIFO pointer by a variable word count.
Advance once per fixed-block transaction and carry valid-word counts locally.
Prove full/empty, partial blocks, concurrent operations and reset before reuse.
A common reset in a functional test does not establish independent-reset safety.

The mapped eight-entry FIFO contains 707 flops and 76,568.576 µm² of cell area,
about 9.01% of the 0.85 mm² memory allowance. Its 690 write-clocked and 17
read-clocked flops present 2.199204 pF and 0.056882 pF clock-pin load in the scoped
nominal mapping. These exclude clock trees, internal power, routing and complete
system storage. They are estimates for a reusable block, not a chip fit result.

## Integration obligations

1. Implement both H2D and D2H staging, commands, actual queue depths and boundary
   timing using the selected transport. Preserve frame count-snapshot epochs.
2. Include collection, two-stage commit, CDC visibility, partial-block service and
   source drift in end-to-end latency. Width times clock is only a capacity ceiling.
3. Account for all storage. The optional H2D model represents 2,048 destination
   bits plus 1,008 bits of collection/pipeline/crossing capacity. Headers, pointers,
   reset and D2H storage are additional; physical registers may share capacity only
   when an implementation demonstrates it.
4. Establish DDR phase alignment, training, reset, clock stopping and analog
   serializer/deserializer gearboxes. Wider host logic alone cannot fix wired-side
   word-clock timing failures.
5. Close mapped/placed timing, CDC constraints, power, area and interface latency.
   Scalar/vector equivalence and ideal-edge RTL comparisons establish functional
   behavior only.

Keep the selected byte-stream interface and all per-engine throughput requirements.
Implementation alternatives may be scoped tests; they do not define extra chip
interfaces or independently qualify any protocol.
