# Block FIFO stability windows (pass 60)

This derives logical bounds from the actual two-stage pointer synchronizers in
`rtl/pt_fifo.sv`. It applies after coordinated reset release and assumes coherent,
causal pointer observations: a destination sees an old or newer published pointer,
never an invented value or a pointer going backwards. Gray-bus physical skew,
synchronizer resolution/MTBF and reset behavior must establish those assumptions.
A finite digital simulation cannot do so.

## Publication

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

## Storage reuse

A consumed slot is freed at read edge R. The read pointer must pass writer stages
1 and 2 before a write decision can use the freed capacity. The earliest reuse
is at least two write periods after R, by the same pre-edge decision argument.
This bound applies to storage overwrite, not to output hold. The current slot
selection changes immediately after R as `rb` advances, even while its old
storage data remains untouched. Pointer-to-output mux contamination delay and
capture-clock skew therefore need a conventional same-domain minimum-delay/hold
check. Delayed reuse cannot substitute for it. Read-valid/enable changes also
need hold analysis, as does the receiving register's feedback path.

## Executable evidence and limits

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

## Nominal minimum-delay evidence (pass 61)

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
