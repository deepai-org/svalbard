# GF180 1x1 Tensor Tile Plan

## Objective

Build a flexible, tileable neural-network inference accelerator for one
wafer.space 1x1 GF180MCU die. Each accelerator die is paired with one to three
closely coupled HyperRAM devices. The same ASIC supports a network-rich
six-link configuration with one or two memories and a memory-rich four-link
configuration with a third memory. The architecture supports every installed
population from one through 1,000 known-good dies in 2D or 3D organizations.

The design should accelerate common CNN, transformer, diffusion, recurrent,
and dense inference workloads. It should support INT4/INT8, FP4/FP8, and
FP16/BF16 operation without paying the area cost of a full FP32 floating-point
FMA in every processing element.

## Fixed constraints

- Die: wafer.space GF180MCU 1x1 slot.
- Die dimensions: 3.932 x 5.122 mm, or 20.140 mm2.
- Area inside the pad ring: 12.902 mm2.
- Signal I/O budget: 50 pins, excluding power and ground.
- Maximum per-pin signaling rate: 200 Mbit/s. DDR interfaces use clocks at or
  below 100 MHz; the internal compute clock is not exported to a pad.
- Memory I/O domain: 3.3 V, using the same wafer.space pad family and supply
  practice demonstrated by the silicon-proven KianV chip. Before schematic
  freeze, record the exact pad model, allowed DVDD range, package connection,
  and signoff corner supplied or approved by wafer.space; the external
  memories share that nominal rail.
- One mandatory and up to two optional closely coupled, board-mounted 3 V x8
  HyperRAM devices per accelerator die. One device is a fully supported
  product configuration, not merely a bring-up mode. Two memories preserve
  all six links; fitting a third memory selects the four-link memory-rich
  board personality.
- The minimum complete accelerator system is one tensor die, one HyperRAM,
  one service-chain termination, a reference clock, reset, and required power.
  It does not require another tensor die or a second HyperRAM.
- Four always-available nearest-neighbor cluster ports. Two additional ports
  share pads with the third memory byte lane and are available whenever that
  memory is absent. This supports 2D memory-rich and 3D network-rich systems.
- Multi-chip operation uses coarse tensor tiles and independent die clocks,
  not a cycle-synchronous systolic array spanning package boundaries.

If the 50-pin limit includes power and ground, the interface allocation in
this plan must be reduced before implementation.

## Silicon-proven KianV baseline

KianV is not merely an area estimate: the design in the companion `kianv`
repository was fabricated in this wafer.space GF180MCU 1x1 slot and boots
NetBSD and Linux on physical silicon. Its submitted artifact is pinned by the
`GF180MCU_Tapeout_Dec2025` tag at commit
`1892792dd2e77df37443cabf0e69320b08492827`. The complete pinned physical flow
has also been reproduced locally to a signoff-clean, though geometrically
different, GDS. The submitted GDS is the silicon-proven reference; the local
rerun establishes that the tool and PDK flow is reproducible, not that the
rerouted geometry has itself been fabricated.

The proven implementation provides this physical reference:

| Physical use | Area |
| --- | ---: |
| Functional standard cells | 3.081 mm2 |
| Cache SRAM macros | 4.397 mm2 |
| Pads and pad spacers | 5.271 mm2 |
| Filler cells | 4.708 mm2 |
| Tap and endcap cells | 0.770 mm2 |
| Die ID and artwork | 0.082 mm2 |
| Unoccupied geometric area | 1.826 mm2 |

KianV contains 7.479 mm2 of functional standard-cell-plus-SRAM area. Its 21
GF180 512x8 SRAM macros occupy 4.397 mm2, or approximately 0.2094 mm2 per
512-byte macro.

The accelerator should remain close to this demonstrated physical envelope.
Unlike KianV, its dominant logic should consist of regular, registered,
nearest-neighbor datapaths rather than associative TLBs and distributed CPU
control. This should make its routing more regular even if it performs more
arithmetic.

### Preserve the proven shell

Treat the KianV tapeout as a controlled baseline and minimize changes outside
the accelerator's required functional differences. Reuse, with hash-bound
provenance wherever possible:

- the 1x1 slot definition, die outline, pad-cell family, power and ground pad
  cells, pad-ring construction, corners, spacers, and physical-only cells;
- the power-grid strategy, metal stack, tap/endcap rules, SRAM macro views,
  macro integration conventions, and antenna/DRC/LVS handling;
- the pinned PDK and LibreLane environment, release scripts, signoff stages,
  final-view archive, and provenance checks; and
- KianV's reset-safe pad-output-disable convention unless a reviewed interface
  requirement demands a change.

Do not casually modernize or replace a working physical-flow component. Every
intentional difference from the silicon-proven top-level and flow must appear
in a machine-readable delta inventory with its reason, affected views, and
specific verification evidence. Keep an unmodified KianV control run available
so a tool, PDK, or configuration change can be distinguished from a tensor-RTL
effect.

The concentrated new-silicon verification scope is:

1. HyperRAM's RWDS-strobed DDR capture, bidirectional turnaround, and higher
   interface rate relative to KianV's external-memory interface.
2. The greater number of concurrently active memory, torus, and service pads.
3. The tensor array's larger and more correlated internal current steps.
4. Independent link/memory/core clock domains, stopped-clock operation, and
   reset-epoch recovery.
5. The new immutable bootstrap, service-chain, and virtual test-access path.

KianV materially reduces fabrication-flow, pad-integration, macro-integration,
and basic package-interface uncertainty. It does not by itself close the five
deltas above, so those retain explicit pre-tapeout and bring-up gates.

## Recommended implementation

| Resource | Target |
| --- | ---: |
| SRAM | 10 KiB in 20 proven 512x8 macros |
| Tensor array | 8 x 10, with 80 base lanes |
| INT4/FP4 issue width | 160 MACs per cycle |
| INT8/FP8 issue width | 80 MACs per cycle |
| Fast block-BF16 issue width | 80 MACs per cycle |
| Strict BF16/FP16 issue width | 10-20 MACs per cycle |
| Functional compute floor | 80-100 MHz |
| Routed compute optimization target | 200 MHz |
| Internal compute stretch target | 300 MHz |
| Memory, torus, and service clock | At most 100 MHz DDR |
| External memory | One required plus up to two optional ISSI x8 HyperRAMs |
| External memory capacity | 64, 128, or 192 MiB |
| External memory bandwidth | 200, 400, or 600 MB/s raw |
| Cluster links | Four always; six when the third memory is absent |
| Host/service link | Two-bit DDR normally; one-bit fallback with U2 |
| Full-cluster host target | 10 GB/s network-rich; 12.5 GB/s memory-rich |
| Controller | Descriptor-driven tensor microsequencer |

### Nominal peak throughput

| Format | 100 MHz | 200 MHz | 300 MHz stretch |
| --- | ---: | ---: | ---: |
| INT4/FP4 | 16 GMAC/s | 32 GMAC/s | 48 GMAC/s |
| INT8/FP8 | 8 GMAC/s | 16 GMAC/s | 24 GMAC/s |
| Fast block-BF16 | 8 GMAC/s | 16 GMAC/s | 24 GMAC/s |
| Strict BF16/FP16 | 1-2 GMAC/s | 2-4 GMAC/s | 3-6 GMAC/s |

These are compute ceilings, not workload claims. External-memory and link
rates do not rise with the core clock, so 200-300 MHz primarily benefits
reused tensor tiles, convolution, batched GEMM, and operations resident in
on-chip SRAM. Streaming batch-one decode remains bandwidth-bound.

Structured 2:4 sparsity may provide up to twice the effective throughput only
when the decoder compacts useful work into the lanes. Merely masking zero
multiplications saves power but does not increase throughput.

### Generated implementation variants

The RTL must generate three lane counts from the same verified design:

| Variant | Base lanes | SRAM | Purpose |
| --- | ---: | ---: | --- |
| Conservative | 64 | 10 KiB | Low-risk fallback |
| Baseline | 80 | 10 KiB | First floorplan and preferred tapeout |
| Stretch | 96 | 10 KiB | Use only if area, power, and routing permit |

The baseline is not selected by extrapolating the smallest PE. It remains the
baseline only after full-array synthesis, SRAM integration, clock-tree
insertion, routing, and power analysis.

## Area budget

| Component | Functional area estimate |
| --- | ---: |
| Twenty SRAM macros | 4.19 mm2 |
| 80-lane tensor array | 1.35-1.80 mm2 |
| Vector, online reduction, and special-function unit | 0.40-0.58 mm2 |
| DMA, packed-format, and SRAM controllers | 0.30-0.45 mm2 |
| Six-capable/four-active router and link logic | 0.32-0.52 mm2 |
| Tensor microsequencer | 0.08-0.15 mm2 |
| Clock, test, and miscellaneous glue | 0.20-0.35 mm2 |
| Total functional area | 6.84-8.04 mm2 |

The virtual-TAP, scan-cell delta, boundary control, shared BIST, and minimal
trigger/trace allowance is included in the clock/test/glue row; it is not an
additional area budget layered on top of the total.

Set an implementation limit of approximately 3.5 mm2 for functional standard
cells. If the 80-lane build exceeds that limit or routes poorly, use the
unchanged 64-lane variant. Do not recover area by silently deleting numeric
behavior or data-movement features required by the programming model.

### Arithmetic plausibility check

KianV's complete 32x32 multiplier occupies approximately 0.092 mm2. Although
multiplier area does not scale perfectly with operand width, quadratic scaling
suggests that 80 bare 8x8 multipliers would occupy roughly:

```text
80 x 0.092 / 16 = 0.46 mm2
```

Registers, accumulators, muxes, format handling, and clocking are expected to
expand the complete array to approximately 1.35-1.80 mm2. This quadratic
multiplier scaling is only a plausibility check, not an area model.

## Processing element

Each base lane should provide:

- One signed/unsigned 8-bit multiplier, splittable into two 4-bit operations.
- A local weight register and partial-sum accumulator.
- INT4, INT8, FP4, and FP8 input handling.
- Saturation, configurable rounding, and zero detection.
- Row- or lane-group clock enables for inactive and zero-valued work.
- Local nearest-neighbor systolic forwarding.

Groups of four base lanes cooperate for strict FP16/BF16 multiplication and
FP32 accumulation. The implementation target is 10-20 strict results per
cycle, not an assumed 24 results per cycle: BF16's eight-bit significand maps
more naturally onto the base multiplier than FP16's eleven-bit significand,
and FP32 accumulation may require additional cycles. Fast BF16 operation uses
a shared block exponent and bounded wide fixed-point accumulation. FP16 input
and output are required, but full-rate fast FP16 is not a baseline claim.

Split the inner datapath so unpacking and multiplication do not share a cycle
with final saturation, normalization, and format conversion. If the
multiply-accumulate feedback path cannot meet 80 MHz after routing, add
interleaved accumulator contexts rather than lengthening the critical path.

Strict mode should provide deliberate NaN and infinity behavior. Subnormal
support may be optional, with an explicit flush-to-zero mode.

The same lanes expose three scheduled organizations without duplicating the
multiplier array:

- a tiled GEMM/convolution organization with local systolic forwarding;
- a GEMV/decode organization that retains an activation vector, broadcasts
  its elements, streams packed weights once, and keeps output accumulators
  local; and
- a vector/reduction organization for irregular tails and fused post-ops.

Clock-gate lane groups independently in GEMV mode: a memory stream should not
toggle all 80 lanes merely because the array exists.

## Vector and special-function unit

A roughly 16-lane vector unit should provide reusable primitives for
operations poorly suited to the systolic array:

- Bias and residual addition.
- ReLU, Leaky ReLU, clamp, and pooling.
- GELU and sigmoid approximations.
- Sum, maximum, and dot-product reductions.
- Online maximum, exponential-sum, and rescaled weighted-vector accumulation.
- Reciprocal and reciprocal square root.
- Quantization, saturation, and datatype conversion.
- Pairwise permutation and rotation.
- Gather/scatter assistance and mixture-of-experts routing.

Expensive transcendental functions should use small lookup tables followed by
low-order interpolation rather than general arithmetic implementations. Build
LayerNorm, RMSNorm, softmax, RoPE, GELU, and sigmoid from these shared
reduction, reciprocal, square-root, exponential, multiply-add, and permutation
primitives instead of implementing a separate fixed-function block for each
operation.

The online primitives must support a one-pass attention schedule without
hard-wiring the unit to transformers: streaming records update a running
maximum, normalization sum, and weighted accumulator without materializing
the score vector. The same operations remain usable for log-sum-exp,
normalization, weighted pooling, streaming statistics, and similarity search.

## On-chip SRAM

The known KianV macros make large SRAM allocations expensive:

| Usable capacity | Macros | Macro area |
| --- | ---: | ---: |
| 4 KiB | 8 | 1.68 mm2 |
| 8 KiB | 16 | 3.35 mm2 |
| 10 KiB | 20 | 4.19 mm2 |
| 12 KiB | 24 | 5.03 mm2 |
| 16 KiB | 32 | 6.70 mm2 |
| 24 KiB | 48 | 10.05 mm2 |

The recommended 10 KiB uses almost the same macro footprint as KianV. It has
suggested reset-time roles, but no permanent capacity partition:

| Purpose | Capacity |
| --- | ---: |
| Activation ping-pong buffers | 3 KiB |
| Weight ping-pong buffers | 3 KiB |
| Partial sums and vector scratch | 3 KiB |
| Network and command queues | 1 KiB |

All 20 macros should be separately banked, and descriptors should repartition
their roles per operation. GEMV/decode mode may devote nearly all available
capacity to the activation vector, quantization metadata, double-buffered
compressed streams, and output accumulators. Distributed PE accumulator
registers provide additional local state.

Ten KiB is the baseline rather than twelve: four additional macros would cost
approximately 0.838 mm2 for only twenty percent more capacity. Use 12 KiB only
if the completed 80- or 96-lane floorplan contains suitable macro-shaped space
without degrading timing or routing. All lane-count variants retain the same
10 KiB baseline so they preserve identical data-movement behavior.

Treat SRAM port conflicts as an architectural verification target. Weight
loading, activation loading, partial-sum traffic, vector access, and torus DMA
must have a conflict-free schedule for every advertised operation. Capacity
alone is not sufficient.

Operator fusion is mandatory. Intermediate activations should remain on-chip
through sequences such as:

```text
matrix multiply -> bias -> residual -> activation -> quantization
```

## External memory interface

Use one to three **ISSI IS66WVH64M8DBLL-166B1LI** devices. U0 is the minimum
complete configuration, U0+U1 is the network-rich default, and adding U2
selects the memory-rich board personality. This is an active 512-Mbit
(64 MiB), x8 HyperRAM in a 24-ball 6 x 8 mm TFBGA. It operates from 2.7-3.6 V
and is currently available in single quantities from authorized distributors.
Do not base the first board on an obsolete part, a factory-contact-only part,
or a 1.8 V-only x16 device.

The procurement baseline was checked on 2026-09-04: Mouser listed more than
1,600 immediately available and DigiKey listed 480 tray parts. Availability
must be checked again before schematic freeze, and an engineering quantity
should be purchased before the PCB footprint and controller are frozen.

- [ISSI datasheet](https://www.issi.com/WW/pdf/66-67WVH64M8DALL-BLL.pdf)
- [Mouser order page](https://www.mouser.com/ProductDetail/ISSI/IS66WVH64M8DBLL-166B1LI)
- [DigiKey order page](https://www.digikey.com/en/products/detail/issi-integrated-silicon-solution-inc/IS66WVH64M8DBLL-166B1LI/24617503)

Run each selected device at no more than a 100 MHz clock even though this
speed grade permits a higher maximum. DDR data then switches at 200 Mbit/s
per pin, exactly at the project limit. Two devices operated in lockstep form
a logical x16 memory. Three form an x24 memory. The supported capacities and
raw bandwidths are 64 MiB/200 MB/s, 128 MiB/400 MB/s, and 192 MiB/600 MB/s.

The always-present U0/U1 memory group uses 20 ASIC signal pins:

```text
16  DQ[15:0], split as one byte per memory device
 2  RWDS[1:0], one per memory device
 1  shared single-ended CK
 1  shared CS#
```

The 3 V part uses a single-ended clock, so no CK# pin is allocated. Commands
and addresses travel in-band. All populated devices receive the same CS#,
address, and command phases, while separate RWDS signals allow every byte lane
to be captured and checked independently. The controller treats the memories
as byte lanes of one striped interface. Tie every memory RESET# ball to the
board-level system reset net; that net already enters the ASIC as a host
control signal and therefore does not consume another ASIC output pin.

Before schematic freeze, verify the chosen pad's VIH, VIL, VOH, VOL, drive,
and bidirectional turnaround against the HyperRAM limits at 2.97, 3.3, and
3.63 V I/O corners. This is a signoff requirement, not an assumption derived
only from nominal supply compatibility.

Designate the DQ[7:0]/RWDS[0] device as mandatory U0 and the
DQ[15:8]/RWDS[1] device as optional U1. The immutable bootstrap controller
defaults to U0-only x8 operation after reset, exposing 64 MiB at up to
200 MB/s raw bandwidth. It enables x16 operation only after host
configuration and a passing U1 lane test, then exposes 128 MiB at up to
400 MB/s raw bandwidth.

U2 uses DQ[23:16] on the eight pads otherwise assigned to the positive and
negative Z-link groups, plus RWDS[2] on one otherwise second-width service
pad. It shares CK and CS# with U0/U1. A board wires these pads either as U2 or
as their network-rich functions; firmware may not switch the electrical board
personality while operating. Immutable straps or safe bootstrap configuration
select the personality before any shared-pad output-enable becomes active.

When U1 or U2 is absent, its ASIC inputs are disabled or held at defined
values and its output drivers remain inactive. U2 is enabled only after its
own lane test passes, producing 192 MiB at up to 600 MB/s raw. Software
discovers memory width, capacity, measured rate, service width, and live-link
set through immutable capability registers. Descriptors and DMA addresses use
the same byte-addressed programming model in x8, x16, and x24 modes. A cluster
may mix memory populations and board personalities; scheduling uses each
die's reported resources.

Independent per-device commands are not a requirement; recovering two chip-
select pins is more valuable at the 1,000-chip target because it preserves six
neighbors in the two-memory personality and four in the three-memory one.

Make CK programmable from the host-visible debug registers. Required initial
settings are 10, 25, 50, and 100 MHz, with 5 MHz included if transaction
timing permits. HyperRAM has no ordinary SDRAM-style refresh command burden,
but CS# low has a specified maximum duration; therefore slow operation must
use short bursts and deassert CS# between transactions. The controller must
calculate its legal slowest clock from the selected latency and maximum CS#
low-time specifications instead of assuming it can pause indefinitely
mid-command.
Bring-up begins at 10 MHz with conservative fixed latency, then advances to
25, 50, and 100 MHz after register readback and walking-bit memory tests pass.

Two-hundred-megabit-per-second GF180 I/O has been achieved by existing users,
so this is a design target rather than an experimental process assumption.
The selected pad cell, attached memory, loading, package or board trace,
source-synchronous capture window, and corner timing must nevertheless be
validated together before the protocol is frozen.

At full speed the controller should favor long bursts and overlap memory
transfers with computation. Sustained-bandwidth objectives are 150-180 MB/s
for x8, 300-360 MB/s for x16, and 450-540 MB/s for x24.

## Dual-personality fifty-pin allocation

| Interface | Network-rich | Memory-rich |
| --- | ---: | ---: |
| U0 plus optional U1 HyperRAM | 20 | 20 |
| U2 DQ and RWDS | - | 9 |
| Torus links | 24: six ports | 16: four ports |
| Service data, reference clock, and reset | 6 | 4 |
| Spare or inactive shared pads | 0 | 1 |
| Total | 50 | 50 |

In network-rich mode the host/control pins are two service-chain receive pins,
two service-chain transmit pins, one continuously driven reference clock, and
global reset. At 100 MHz DDR each two-bit hop carries 50 MB/s without exceeding
200 Mbit/s per pin.

In memory-rich mode U2 consumes the two Z-link data groups and one of the four
service data pads. The service chain uses one receive and one transmit pad plus
the same reference clock and reset, carrying 25 MB/s at 100 MHz DDR. The
remaining shared pad is held inactive or used only for a reviewed static strap
or diagnostic function. All bootstrap and virtual test operations remain
available at the narrower width.

Packets enter a short chain from a board controller, are consumed or forwarded
by each die, and return from the final die to the controller.

Every hop is point-to-point and retimed; this avoids a high-capacitance
multidrop bus. The service chain carries commands, completions, bulk data,
debug, boot, coordinate enumeration, and telemetry independently of the
torus. A board controller or FPGA terminates both ends of every chain. The
reference clock may come from a buffered plane clock tree, but each clock
branch and data hop must be analyzed with its actual load and skew.

Boundary scan and manufacturing test must reuse the host signals or be entered
through a reset-time mode sequence rather than require dedicated pads. The
memory-rich spare is not required for functional or manufacturing coverage.

## Slow-clock and single-step contract

Every digital block and every chip-to-chip or host-visible protocol must work
with a continuously variable clock and in manual-step operation. Do not use
dynamic logic, minimum-frequency assumptions, fixed wall-clock delays, or an
internal PLL that prevents operation from a slowly pulsed external reference.
All generated clocks use reviewed glitch-free clock muxes or integrated clock
gates and preserve required minimum high and low pulse widths.

The tensor datapath is an independent clock domain architected for up to a
300 MHz post-route stretch bin. Memory, torus, and service pads remain at or
below 100 MHz DDR. Elastic queues and explicit CDC boundaries decouple those
rates, allowing one, two, or three tensor cycles per I/O cycle. A 300 MHz
internal clock requires a wafer.space-approved, characterized multiplier or
oscillator. It must have a glitch-free bypass to the external reference and
may not be required for boot, test, low-speed operation, or correctness. If no
such IP is available, first silicon remains externally clocked at no more than
the verified pad rate and the 300 MHz architecture is evaluated only as a
timing target.

Do not require SRAM macros, the router, or the descriptor controller to close
at 300 MHz merely to advertise the compute bin. SRAM-bank front ends prefetch
into local operand and accumulator staging registers; reuse-capable schedules
then execute multiple tensor cycles per SRAM or I/O cycle. If a workload
cannot reuse staged data, its claimed throughput remains at the supplying
memory domain's measured rate.

The immutable debug controller provides these operations independently for
the tensor/vector core, DMA and memory controller, torus router, and service-
chain forwarding domains:

```text
RUN
HALT_AT_SAFE_BOUNDARY
STEP_EDGE
STEP_CYCLE
STEP_N_CYCLES
RUN_UNTIL_EVENT
READ_STATE
```

Required divided-clock points are 100, 50, 25, 10, 5, and 1 MHz. Below that,
an external controller may issue individual clock edges separated by an
arbitrary interval, provided each pulse meets minimum width. Reset release,
clock-domain handshakes, credits, packet framing, arbitration, and error
handling must behave correctly when either side stops for an indefinite
period.

Protocol timeouts and watchdogs are programmable in protocol events or local
active-clock cycles, not an assumed real-time frequency. They can be disabled
in debug mode. A stopped neighbor therefore causes backpressure and visible
status, not state corruption or an unrecoverable timeout cascade. Debug
registers expose current state, outstanding credits, FIFO contents or heads,
last transmitted and received headers, CRC state, retry count, and halt
reason.

### CDC and reset contract

Treat stoppable clocks as an architectural property, not an unusual debug
condition. Bulk data crosses clock domains through asynchronous FIFOs with
Gray-coded pointers. Control crossings use persistent level, toggle, or
request/acknowledge handshakes; do not send unacknowledged one-cycle pulses
into another domain.

Reset asserts asynchronously where required for safety and deasserts
synchronously within each receiving domain. Every independently reset packet,
credit, DMA, and completion path carries or derives a reset epoch so stale
state from before reset cannot be accepted after restart. Link initialization
begins without assumed credits and explicitly exchanges readiness before
payload traffic.

Formal safety properties must hold even when any participating clock stops
forever. Liveness properties may assume only that the clocks and peer needed
for progress eventually resume. Verify all relative clock phases, independent
reset orderings, FIFO-full and FIFO-empty boundaries, reset during
backpressure, and halt immediately before and after each handshake event.

The service-chain reference clock is controlled by the board controller, so
the bootstrap protocol itself can be run at 1 MHz or advanced edge by edge.
The always-available bootstrap block can remain running while all other
domains are halted. A torus transmitter similarly holds its pins stable while
stopped and advances its source-synchronous strobe only on an explicit link
step; the receiver must tolerate arbitrary gaps between edges.

HyperRAM is the unavoidable exception to indefinite mid-transaction pause.
Its maximum CS# low time means the external wire transaction cannot remain
half-finished forever. The memory controller is still instruction-stepable,
but `HALT_AT_SAFE_BOUNDARY` stops only with CS# deasserted. When a debug step
launches a memory request, a small atomic transaction sequencer completes the
command and selected short burst at a legal programmable clock, deasserts
CS#, captures the result and trace, and halts again. Thus requests, responses,
and controller states can be inspected one at a time without violating the
memory's electrical protocol.

Generate a reviewed legal-transaction table from the selected HyperRAM
datasheet for every supported debug clock. Each entry fixes initial latency,
maximum burst length, turnaround, recovery, and maximum CS# assertion for the
required voltage and temperature range. Unsupported clock/latency/burst
combinations must be rejected by hardware rather than attempted. The atomic
sequencer exposes the complete command, captured RWDS behavior, returned data,
cycle count, and termination reason after every stepped transaction.

## JTAG-equivalent service transport

Do not allocate a separate physical JTAG port. The retimed service chain is
the mandatory transport for every function that would ordinarily require
JTAG, boundary scan, or a dedicated debug module. Each die exposes a
packet-addressed virtual test-access port implemented in the immutable
bootstrap/service block. It is reachable at wafer probe, on a standalone
board, and at any enumerated chain slot without initialized HyperRAM,
microcode, tensor logic, or torus links.

The virtual test-access port must provide equivalents of:

- `IDCODE`, implementation revision, manufacturing identifier, and status.
- `BYPASS` and transparent service forwarding through an unselected die.
- `SAMPLE/PRELOAD`, `EXTEST`, `INTEST`, `CLAMP`, and `HIGHZ` for digital pads.
- Internal scan-chain selection, shift, capture, and update.
- SRAM BIST, repair-status readout where supported, and retention tests.
- HyperRAM controller test, pad loopback, and programmable external patterns.
- Torus and service-link PRBS, loopback, error injection, and counter access.
- Clock-domain selection, safe halt, edge/cycle stepping, and reset control.
- Architectural and implementation register access.
- On-chip SRAM and external-memory reads and writes.
- DMA and descriptor breakpoints, run-until-event triggers, and trace readout.
- Test-result collection, failure localization, and per-state capture.

Boundary-scan cells surround all appropriate digital signal pads. Entering a
test mode first forces memory, torus, and non-transport outputs to declared
safe values so scan shifting cannot create contention or unintended
transactions. The service pads actively carrying the test protocol remain
under immutable transport control and are tested separately by link loopback
and end-to-end patterns. Capture and update are separate explicit operations,
and test clocks may be advanced one edge at a time.

Service packets carry virtual instruction, selected data register or scan
chain, bit count, shift payload, and expected response metadata. Long scan
operations stream through bounded buffers rather than requiring an entire
scan vector on-chip. Addressed operations select one die; broadcast capture
or update is permitted only where deterministic response collection and
electrical safety are defined.

IEEE 1149.1 pin-level compatibility is not required at the ASIC pads. When
standard laboratory or production software is useful, the board controller
or FPGA presents a conventional JTAG TAP externally and translates TAP
instructions and scan shifts into service-chain packets. Define and publish
that translation with the scan description and boundary-scan register so the
ASIC is usable with ordinary test automation instead of proprietary manual
commands.

### Debug and test implementation limits

Implement JTAG-equivalent behavior as a thin command layer over the service
transport and bootstrap resources already required for normal operation. Do
not instantiate a second packet engine, physical TAP, debug CPU, or duplicate
register file. The incremental virtual-TAP, boundary-control, BIST, trigger,
and scan-cell overhead targets no more than 0.10 mm2 of functional standard-
cell area. Any result above 0.15 mm2 requires an explicit design review and
feature reduction before accepting more area.

Apply these minimization rules:

- Reuse the immutable service decoder, response formatter, clock-step
  controller, and register-access path for all virtual-TAP operations.
- Use characterized scan-capable library flops where scan is required; do not
  shadow or duplicate ordinary architectural state for debug capture.
- Reorder and partition scan chains after placement to minimize wire length.
  Scan shifting is a test mode and is not required to meet the functional
  compute clock.
- Reuse pad input, output-enable, and test controls where the selected I/O
  cells provide them. Place any unavoidable boundary-test mux on the core
  side and include it in the 200 Mbit/s interface timing path.
- Use one shared small LFSR, MISR/comparator, address generator, and result
  register for SRAM, HyperRAM, pad, and link tests. Test resources sequentially
  rather than duplicating a BIST engine per macro or port.
- Keep only a few always-available last-event, last-header, error, and state
  registers plus a maximum four-entry bootstrap trace. Deeper trace uses a
  temporarily reserved bank of the existing on-chip SRAM after that SRAM has
  passed BIST, or streams immediately over the service chain.
- Limit baseline hardware triggers to two shared address, descriptor, or event
  comparators. More elaborate trigger matching belongs in the board FPGA or
  a later revision.
- Clock-gate scan, BIST, trace, and trigger logic completely in ordinary
  functional mode except for the immutable service endpoint and required
  status latches.
- Decode test entry only in the immutable endpoint using an explicit reset-
  time sequence. Accidental functional traffic must not enable scan clocks or
  override pad directions.

Debug and test logic may not reduce an advertised compute, memory, torus, or
service-chain clock or bandwidth. If boundary or scan insertion creates a new
functional critical path, first restructure the test connection or trim trace
and trigger features; do not silently lower the product target. Preserve
basic boundary scan, internal scan access, BIST, clock stepping, and bootstrap
recovery ahead of optional trace depth or sophisticated breakpoints.

## Thousand-chip interconnect

### Physical topology

Support two first-class physical organizations with the same router, command
ABI, and software discovery:

- **Network-rich:** one or two memories, six ports, and a 3D mesh or torus. A
  full regular system is 10 x 10 x 10.
- **Memory-rich:** three memories, four ports, and a 2D mesh or torus. A full
  regular system may be 25 x 40 or another board-convenient factorization.

A port consists of three bidirectional DDR data pins and one bidirectional
source-synchronous strobe. At 200 Mbit/s per data pin, each physical link
carries 600 Mbit/s, or 75 MB/s, in its selected direction. Six active ports
provide 450 MB/s of aggregate edge bandwidth; four provide 300 MB/s. The
memory-rich personality intentionally exchanges two network ports for a third
memory byte lane and 600 MB/s raw attached-memory bandwidth.

This follows the proven nearest-neighbor 3D organization used by large TPU
systems; Google documents that torus-connected slices generally outperform
the corresponding open mesh. Because all three dimensions here are equal,
use the ordinary symmetric torus rather than an asymmetric twisted topology.

- [Google TPU v4 3D mesh and torus documentation](https://cloud.google.com/tpu/docs/v4#3d_mesh_and_3d_torus)

For representative complete tori:

| Property | Network-rich 10x10x10 | Memory-rich 25x40 |
| --- | ---: | ---: |
| Dies | 1,000 | 1,000 |
| Physical links | 3,000 | 2,000 |
| Degree per die | 6 | 4 |
| Maximum shortest path | 15 hops | 32 hops |
| Mean shortest path | Approximately 7.5 hops | Approximately 16 hops |
| Minimum bisection | 200 links/15 GB/s | 50 links/3.75 GB/s |

A binary hypercube is not the baseline. The nearest size is 1,024 nodes and
requires ten physical neighbor links per node. Its shorter paths do not
justify the extra pads, serializers, connectors, and nonlocal wiring. The 2D
memory-rich topology has longer paths and lower bisection than the 3D option,
but is well matched to row broadcasts, column reductions, CNN partitions, and
matrix sub-block layouts while providing 50% more local memory bandwidth.

A practical network-rich assembly is ten planes of 10 x 10 dies, with X/Y
links on each plane and Z links across a backplane. A memory-rich assembly is
a rectangular 2D board or a cable-connected arrangement of 2D subplanes whose
logical row and column rings remain point-to-point. Board design must never
create multidrop clock or data nets.

### Scale-independent operating contract

The same silicon, RTL, command ABI, and host software must operate for every
installed population `1 <= N <= 1000`. Only known-good dies are wired into a
system; this requirement does not assume 1,000 physical positions containing
dead nodes. Cluster participation is optional: local tensor, vector, DMA,
HyperRAM, and host operations must never depend on a live network port.

At boot, writable topology registers define:

- X, Y, and Z coordinate and extent.
- Whether each dimension is open, wrapped as a torus, or absent.
- Enable, neighbor-valid, and direction state for every physical port.
- Rectangular partition origin and extent.
- Service-chain identifier and slot, plus collective-group membership.

An extent of one removes that dimension from routing and collectives. An
absent port consumes no credits, cannot block reset or command completion, and
is held in a low-power safe state. Collective operations over a one-member
group complete locally; dimensions of extent one are skipped rather than
emitting packets.

Required validated configurations include:

| Dies | Preferred topology | Purpose |
| ---: | --- | --- |
| 1 | 1 x 1 x 1 | Standalone bring-up and useful accelerator |
| 2 | 2 x 1 x 1 mesh | Link validation |
| 4 | 2 x 2 x 1 mesh or torus | Planar routing and collectives |
| 8 | 2 x 4 plane or 2 x 2 x 2 | 2D and 3D validation |
| 16-64 | Rectangular 2D/3D partition | Board and software development |
| 100 | 10 x 10 x 1 plane | Production plane qualification |
| 900 | 30 x 30 or 10 x 10 x 9 torus | Regular reduced cluster |
| 1,000 | 25 x 40 or 10 x 10 x 10 torus | Full target system |

For a population that factors into a reasonably balanced `X * Y = N` or
`X * Y * Z = N`, wire a regular rectangular mesh or torus matching its board
personality. For example, 900 dies form either a 30 x 30 or 10 x 10 x 9 torus
with no dummy nodes and no holes.

Some values of N do not have useful two- or three-factor decompositions. For
those, pack all dies contiguously into an appropriate near-rectangular or
near-cubic coordinate envelope and truncate only the final plane and row. The
resulting boundary-ragged mesh
must remain functional through per-port neighbor-valid bits and topology-
supplied routes; it may have less uniform collective performance than a
regular torus. Do not require powered dummy dies to complete an address grid.

Torus wrapping is independently selectable per complete dimension or ring,
allowing a system to begin as an open mesh and add available wrap cables
later. The runtime receives the discovered physical graph and forms regular
rectangular partitions wherever possible. It uses explicit routes and
topology-derived collective trees only at ragged boundaries.

In standalone mode, the host controller connects to both ends of the local
service-chain port, loads descriptors and data into attached HyperRAM, and
receives completions without performing torus discovery. At the 50 MB/s
network-rich service rate, loading 64 or 128 MiB takes approximately 1.34 or
2.68 seconds before overhead. At the 25 MB/s memory-rich service rate, loading
192 MiB takes approximately 8.05 seconds. Network registers and collective
commands remain available but are not required. This makes a one-die,
one-HyperRAM board a complete, useful product rather than merely a cluster
test fixture.

### Link and router behavior

All dies run from independent local clocks. Every port therefore terminates
in a source-synchronous receive block and a small elastic clock-domain
crossing buffer. No cluster-wide low-skew clock is required.

The six-capable wormhole router, with four ports active in memory-rich mode,
must provide:

- Short packets with destination coordinates, length, traffic class,
  sequence, and end-to-end operation identifiers.
- Burst-oriented half-duplex arbitration so useful payloads amortize link
  turnaround; opposite physical ports can transmit and receive concurrently.
- Per-packet CRC, link-local retry, timeout, duplicate suppression, and
  counters for corrected and uncorrected failures.
- Credit flow control with bounded shallow buffers. Buffer size and maximum
  packet length must be chosen together so a receiver can guarantee progress
  without relying on a large store-and-forward RAM.
- Deterministic shortest-path XY or XYZ routing as the escape path. Wraparound
  uses dateline virtual channels so cyclic credit dependencies cannot
  deadlock.
- A separate control/collective traffic class that cannot be starved by bulk
  tensor transfers.
- Optional minimal adaptive routing among equally short directions only after
  the deterministic escape path has been proven.
- Direct memory-to-network, network-to-SRAM, and network-to-vector-unit DMA.

The normal router should use coordinate arithmetic rather than a 1,000-entry
routing table. A compact source-route escape mode allows the host to route
around a known failed link or die. Links can be disabled individually, and
wraparound can be disabled to form rectangular meshes or cluster partitions.

### Collectives and scheduling

Implement collectives as first-class DMA operations rather than thousands of
host-issued point-to-point copies:

- Dimension-ordered broadcast and multicast.
- Streaming reduce-scatter followed by all-gather for all-reduce.
- X-, then Y-, then optional Z-ring phases for large messages.
- Tree reduction for short latency-sensitive messages.
- Nearest-neighbor halo exchange.
- Barriers scoped to a rectangular partition, not necessarily all 1,000
  dies.

Reduction data should stream through the existing vector arithmetic and back
to the outgoing DMA path without a round trip through external HyperRAM.
Collective chunks must be large enough to amortize packet headers and
half-duplex turnarounds, while double buffering overlaps each communication
phase with tensor work.

Separate dies cooperate at tensor-block granularity. They do not extend the
internal systolic array cycle by cycle across package links. Supported
scaling modes include pipeline, tensor, expert, sequence/context, and data
parallelism. The compiler must map the most communication-intensive model
dimension onto physically adjacent dies and use the 2D or 3D partition shape
that minimizes the relevant collective surface. Matrix-vector and attention
schedules should exploit row broadcasts and column reductions in either
personality rather than requiring an LLM-only network protocol.

### Parallel host/service chains, discovery, and serviceability

Every die belongs to a retimed service chain. Chain length is a board and
system choice, not an RTL limit.
The protocol uses at least ten-bit chain-slot, discovered-length, and hop-limit
fields so a valid implementation can contain any length from one through all
1,000 dies. Enumeration determines the installed length before ordinary
traffic begins.

For an N-die system using nominal chain length L, the controller count is
`ceil(N / L)` and the final chain may be shorter. Five dies is the recommended
network-rich full-cluster operating point because it provides 10 GB/s aggregate
ingress with 200 controller endpoints. Memory-rich service is half as wide, so
two-die chains are recommended when rapid loading of all 192 MiB per die
matters. Neither length is enforced by the chip.
A plane controller or FPGA terminates both ends of each selected chain, and
the plane controllers feed the cluster through an implementation-specific
higher-bandwidth system interface.

The resulting host limits are:

| Configuration | Example chains | Network-rich | Memory-rich |
| --- | ---: | ---: | ---: |
| Standalone die | 1 one-die chain | 50 MB/s | 25 MB/s |
| 100-die plane | 20 five-die chains | 1 GB/s | 0.5 GB/s |
| 1,000 dies | 200 five-die chains | 10 GB/s | 5 GB/s |
| 1,000 memory-rich dies | 500 two-die chains | - | 12.5 GB/s |

At 100 MHz DDR, a chain carries 50 MB/s with two-bit service and 25 MB/s with
one-bit service regardless of length because every hop is retimed and packets
pipeline. Aggregate host bandwidth and loading time depend on width and
length. For 1,000 network-rich dies with uniform chains:

| Nominal length | Chain count | Aggregate bandwidth | Full 125 GiB load |
| ---: | ---: | ---: | ---: |
| 1 | 1,000 | 50 GB/s | approximately 2.7 s |
| 5 | 200 | 10 GB/s | approximately 13.4 s |
| 10 | 100 | 5 GB/s | approximately 26.8 s |
| 20 | 50 | 2.5 GB/s | approximately 53.7 s |
| 100 | 10 | 0.5 GB/s | approximately 4.5 min |
| 1,000 | 1 | 50 MB/s | approximately 44.7 min |

These are raw transfer times using 125 GiB. A fully populated memory-rich
cluster contains 187.5 GiB and has half the per-chain rate; its recommended
500 two-die chains provide 12.5 GB/s raw and a roughly 16.1-second ideal fill.
Protocol and placement overhead increase every value. Longer chains also
increase command latency and the number of dies affected by a forwarding
failure, but they remain functionally valid.

A completely empty 125 GiB network-rich cluster can therefore be filled in
about 12.5 seconds at the theoretical aggregate rate. The 187.5 GiB
memory-rich configuration reaches a similar target only with shorter chains
and more parallel controllers. Practical targets are under 20 seconds for
network-rich and under 25 seconds for memory-rich.

Host software stripes weights, activations, and KV-cache state directly to
the service chain containing each destination. Bulk loading does not traverse
the torus. Packets are forwarded hop by hop while unrelated chains operate in
parallel; a die consumes packets addressed to its chain slot and forwards all
others without a HyperRAM round trip.

The service protocol uses framed packets with chain and slot identifiers,
target coordinates, memory or register address, length, operation, sequence
number, and CRC. It provides credits, explicit completion, retry, timeout,
and reserved control slots. Large payload packets amortize framing; control
packets receive bounded latency. A token-based arbiter prevents multiple dies
from injecting responses into the same return opportunity.

The immutable bootstrap controller forwards packets before external memory or
writable microcode is available. During enumeration, the plane controller
sends each chain its physical origin and direction. Each die latches the next
slot and coordinate, increments the enumeration packet, and forwards it. The
controller verifies the returned count and coordinate before enabling bulk
traffic.

Make the two receive and two transmit pad pairs electrically bidirectional so
the complete chain can be reversed in service mode. Because the controller
is wired to both ends, it can reach the healthy segments on either side of a
non-forwarding die. Memory-rich mode selects one receive and one transmit pad
from this set before U2 is enabled. The torus remains the fallback path for redistributing
boot data or commands around a broken service chain.

Manufacture and test the system incrementally as one die, configurable two-,
five-, and ten-die service chains at both widths, a two-die torus link, a 2 x 2
plane, a 2 x 2 x 2 cube, a 10 x 10 plane, and finally both full tori. Simulate much
longer service chains even if the first boards do not populate them. Per-link
error counters, PRBS/test-pattern mode, loopback, coordinate readback, and
partition-wide memory tests are mandatory.

## Data movement and command model

The DMA engine should support:

- Multidimensional strided transfers.
- Transpose and layout conversion while moving data.
- Circular buffers and automatic double buffering.
- Limited gather/scatter for embeddings.
- Weight and activation multicast.
- Centralized 2:4 and block-sparse decoding before lane assignment.
- Packed two-per-byte INT4/FP4, group-scale, zero-point, compact 2:4, bank-level
  zero-run, and lightweight weight decompression.
- Head-major, sequence-major, and interleaved K/V circular layouts with
  per-head or per-block FP8/INT8 and optional INT4 scaling.
- Concurrent memory, compute, and network operations.

Do not duplicate variable-length decoders in every PE. The DMA and SRAM-bank
front ends compact useful work, while the tensor array receives regular
lane-ready operands and masks. This avoids lane imbalance and keeps decoding
out of the array's critical paths.

The host submits coarse commands rather than scalar instructions:

```text
MATMUL
MATVEC
CONV2D
STREAMING_WEIGHTED_REDUCE
ONLINE_ATTENTION
REDUCE
NORMALIZE
ELEMENTWISE
LAYOUT_TRANSFORM
SEND_TILE
RECEIVE_TILE
MULTICAST
ALL_REDUCE
REDUCE_SCATTER
ALL_GATHER
BARRIER
```

Descriptors contain addresses, shapes, strides, formats, quantization state,
fusion operations, 2D/3D chip and partition coordinates, collective axes, and
operation identifiers. The small controller handles sequencing and uncommon
cases, not tensor inner loops.

### Controller baseline

Use a descriptor-driven microsequencer with nested-loop address generators,
dependency and event bits, a small writable microcode store, command and
completion queues, and performance counters. Do not include a resident RV32E
core in the baseline. It may be added later only if demonstrated workloads
need control flow that the descriptor engine cannot express economically.

A small immutable bootstrap controller must operate before writable
microcode, external memory, or the torus is initialized. It brings up the
service chain at a conservative clock, exposes identification and diagnostic
registers, tests HyperRAM, loads microcode with checksum verification, then
enables normal descriptors. The bootstrap block must also forward service-
chain packets while the main controller is stopped. A die isolated by a
service-chain failure can enter the same process from a boot packet received
over a validated torus link.

Keep bootstrap and service forwarding structurally simpler than the main
microsequencer and independent of writable state wherever practical. The
immutable path must provide:

- Bidirectional service-chain forwarding and enumeration.
- Conservative clock selection, domain halt, stepping, and reset control.
- Identification, status, and unrestricted diagnostic-register access.
- Scan-chain access and manufacturing-test mode entry.
- SRAM BIST, HyperRAM test, pad loopback, and torus PRBS/loopback control.
- Isolation of any torus port or main functional block.
- A reset-time escape sequence that always returns the die to bootstrap mode.

Verify the bootstrap/service block independently with exhaustive or formal
state-transition checks appropriate to its size. Its basic forwarding,
inspection, clocking, and test functions must not depend on successful
HyperRAM initialization, loaded microcode, or a functioning tensor array.

## Workload expectations

The tile should accelerate:

- Dense and batched matrix multiplication.
- Ordinary, grouped, depthwise, and pointwise convolution.
- Transformer attention and feed-forward layers.
- CNNs, vision transformers, and U-Nets.
- Diffusion inference.
- RNN and LSTM inference.
- Layer normalization, softmax, pooling, and common activations.
- Sparse and mixture-of-experts inference with appropriate scheduling.

Expected weak cases are full training, FP32-heavy scientific models, highly
dynamic graphs, and large random embedding lookups. Batch-one LLM decoding
remains bandwidth-bound but is a supported workload rather than a structural
misfit because GEMV, packed weights, quantized KV, and online attention avoid
avoidable traffic.

At approximately 320 MB/s sustained external bandwidth in network-rich x16
mode, memory supplies about 320 million new FP8 weights/s or 640 million packed
FP4 weights/s. Memory-rich x24 mode raises those figures to approximately
450-540 million FP8 or 900-1,080 million packed FP4 weights/s. The
array therefore requires substantial reuse to approach peak throughput.
Convolution, batched GEMM, and transformer prefill can provide that reuse;
batch-one transformer decoding is normally bandwidth-bound.

Examples of full-weight-sweep ceilings are:

| Local model or shard | Weight bytes | x16 at 320 MB/s | x24 at 480 MB/s |
| --- | ---: | ---: | ---: |
| 100M parameters at FP4 | 50 MB | 6.4/s | 9.6/s |
| 100M parameters at FP8 | 100 MB | 3.2/s | 4.8/s |
| 256M parameters at FP4 | 128 MB | 2.5/s | 3.75/s |
| 128M parameters at BF16 | 256 MB | 1.25/s | 1.88/s |

### Balanced-tile LLM envelope

LLM decoding is not the organizing purpose of the chip, but it is an explicit
design workload. For a 1,000-die memory-rich system, 450-540 GB/s expected
aggregate sustained memory bandwidth gives a 32-billion-parameter W4 model
with group scales and alignment, estimated at 17-20 GB, a pure weight-stream
ceiling of roughly 22-32 tokens/s. As an illustrative KV case, 64 layers,
eight 128-element KV heads, 32K context, and one-byte KV elements add about
4.3 GB of reads per generated token, reducing the memory-only ceiling to
roughly 19-25 tokens/s.

Those are rooflines, not forecasts. The balanced router, sequential layer
barriers, HyperRAM efficiency, vector work, quantization overhead, and KV
layout remain. Use 8-16 tokens/s as the initial architecture-model objective
for a well-quantized 32B model at moderate context, and report context length,
weight/KV formats, memory utilization, collective time, and numerical quality
with every result. No tapeout decision depends on achieving this workload
objective.

### Full-cluster envelope

One thousand baseline dies provide the following theoretical envelope before
yield loss, spares, protocol overhead, thermal throttling, or partitioning:

| Cluster resource | Network-rich | Memory-rich |
| --- | ---: | ---: |
| FP4/INT4 peak at 100/300 MHz | 16/48 TMAC/s | 16/48 TMAC/s |
| FP8/INT8/fast-BF16 at 100/300 MHz | 8/24 TMAC/s | 8/24 TMAC/s |
| Strict BF16/FP16 at 100/300 MHz | 1-2/3-6 TMAC/s | 1-2/3-6 TMAC/s |
| Attached-memory bandwidth | 400 GB/s raw | 600 GB/s raw |
| Attached-memory capacity | 125 GiB | 187.5 GiB |
| Representative torus bisection | 15 GB/s raw | 3.75 GB/s raw |
| Recommended parallel host ingress | 10 GB/s raw | 12.5 GB/s raw |

A regular 900-die cluster retains exactly 90% of the maximum system's local
resources without irregular routing: use 10 x 10 x 9 network-rich or 30 x 30
memory-rich wiring.

| 900-die resource | Network-rich | Memory-rich |
| --- | ---: | ---: |
| FP4/INT4 peak at 100 MHz | 14.4 TMAC/s | 14.4 TMAC/s |
| FP8/INT8/fast-BF16 at 100 MHz | 7.2 TMAC/s | 7.2 TMAC/s |
| Attached-memory bandwidth | 360 GB/s raw | 540 GB/s raw |
| Attached-memory capacity | 112.5 GiB | 168.75 GiB |
| Parallel host ingress, recommended chains | 9 GB/s | 11.25 GB/s |

U0 versus U0+U1 population does not change compute or network functionality.
A cluster using only mandatory U0 on every die has:

| Population | Capacity | Raw local-memory bandwidth |
| ---: | ---: | ---: |
| 1 die | 64 MiB | 200 MB/s |
| 900 dies | 56.25 GiB | 180 GB/s aggregate |
| 1,000 dies | 62.5 GiB | 200 GB/s aggregate |

Adding U1 doubles those capacity and bandwidth values without changing the
ASIC, torus wiring, command ABI, or numerical behavior. Adding U2 produces the
memory-rich x24 values while selecting four links and the one-bit service path.

The 125 GiB network-rich figure can hold at most approximately 268 billion packed FP4,
134 billion FP8, or 67 billion BF16 parameters if no capacity is reserved for
activations, KV cache, descriptors, or redundancy. Real usable model sizes
will be smaller. Memory-rich capacity is 50% larger.

Network bisection is the cluster's most important scaling constraint,
especially in memory-rich mode.
The software contract must therefore favor weight-stationary shards, expert
locality, large fused tensor blocks, and hierarchical collectives. A workload
that exchanges every intermediate activation globally will not scale well
merely because aggregate arithmetic is high. Performance claims for the
1,000-die system must report both single-die utilization and time spent in
network collectives.

## Physical-design strategy

Arrange SRAM banks symmetrically around the tensor array so their consumers
are nearby:

```text
             weight and input SRAM banks
       +------+------+------+------+
       |                            |
 SRAM  |      8 x 10 tensor array  | SRAM
 banks |                            | banks
       | vector unit    DMA/router |
       +------+------+------+------+
          accumulator/output banks
```

Pipeline every PE boundary and keep multiplier-to-accumulator paths local.
Close the first complete routed design at 80-100 MHz, then optimize the
independent compute domain toward 200 MHz. Attempt 300 MHz only after the
baseline floorplan meets area, electrical, power, clock-source, and CDC
requirements. Floating-point normalization
and format conversion remain outside the innermost accumulator feedback path
or operate over multiple cycles.

Track routed wire length, buffer insertion, maximum transition, capacitance,
fanout, and slow-corner setup timing from the first floorplanned build. The
regular array should be easier to route than KianV's MMU-heavy CPU, but this
must be demonstrated rather than assumed.

### Power and clocking

Treat power delivery and simultaneous switching as first-class sizing limits,
not late signoff checks. Estimate activity with representative dense, sparse,
vector, and torus workloads; analyze dynamic and leakage power, package supply
impedance, IR drop, and electromigration for every lane-count variant.

Clock-gate inactive PE rows or lane groups, SRAM banks, numeric-format logic,
the vector unit, and torus ports. Avoid hundreds of independently gated lane
clocks unless analysis demonstrates a net benefit after clock-tree insertion.
Do not require true power gating in first silicon: power switches, isolation,
retention, and extra power domains add disproportionate physical and
verification risk.

At cluster scale, regulate and monitor power per 10 x 10 plane or smaller
serviceable group. Support staged power-up, clock enable, memory test, and
work dispatch so 1,000 dies do not create a single simultaneous inrush or
switching step. The full-system power and cooling budget must be derived from
measured packaged-die boards in both x16/six-link and x24/four-link
personalities before committing to the final
1,000-die enclosure; multiplying a pre-layout logic estimate is not an
acceptable thermal design method.

### Simultaneous-switching signoff

Use the measured KianV board and silicon behavior, its actual I/O supply, and
its extracted/submitted pad-ring data as the first correlation point for the
electrical model. Reproduce a KianV-like switching case before extrapolating
to the tensor tile. The tensor analysis then adds only the incremental cases:
HyperRAM DDR strobes and turnaround, four or six active torus ports, one- or
two-bit service traffic, U2 pad multiplexing, and correlated compute-array
enable. This prevents an
uncorrelated generic package model from silently replacing available silicon
evidence.

Do not infer simultaneous-switching safety merely from the 200 Mbit/s rate or
from correct timing on one isolated pad. Edge rate, drive strength, package
inductance, return paths, and the number and placement of concurrently
switching outputs determine the actual risk; operating less frequently does
not necessarily reduce the disturbance from an individual edge.

Build legal worst-case vectors for memory writes, memory turnaround, all
torus transmitters, service-chain traffic, and coincident interface activity.
Evaluate them with the best available extracted pad, supply-grid, package,
board, load, and decoupling models across required voltage and temperature
corners. Measure or bound supply and ground bounce, crosstalk, receiver noise
margin, edge and duty-cycle distortion, and timing displacement.

Select mitigations only from those results. Candidate mitigations include pad
drive and slew selection, package and pin ordering, additional return paths or
decoupling, source-series termination, and limited launch scheduling between
independent interfaces. None is a frozen architectural requirement until the
electrical analysis demonstrates that it is necessary and that it preserves
the required protocol timing. If a mitigation reduces usable bandwidth, all
performance tables and workload models must use the reduced measured rate.

#### Conservative decoupling baseline

Use on-die decoupling to reduce supply-transient risk, but do not introduce an
uncharacterized capacitor structure or optional process mask merely to obtain
more nominal capacitance. The first-silicon baseline uses the characterized
`gf180mcu_fd_sc_mcu7t5v0__fillcap_4`, `_8`, `_16`, `_32`, and `_64` cells in
legal standard-cell rows. Explicit MIM or custom MOS capacitors remain outside
the baseline unless extracted analysis shows they are required, wafer.space
confirms the process option, and their models, DRC, LVS, reliability, startup,
and routing effects are reviewed.

Apply library fill-cap cells in this order:

1. Preserve candidate row space near the memory-interface logic, each torus
   interface group, the service-chain endpoint, and nearby supply connections.
2. After functional placement and an initial route/congestion estimate,
   replace suitable ordinary filler and unused row sites with the largest
   legal fill-cap cells that do not obstruct signal or power routing.
3. Connect a fill-cap only to the voltage domain and well configuration for
   which that cell is characterized. Do not assume a core-rail cell can be
   attached to a separately supplied I/O rail.
4. Extract the power network and compare no-added-decap, distributed-decap,
   and interface-localized-decap cases using the legal worst-case switching
   vectors.
5. Select the smallest characterized insertion that passes the supply-noise
   and receiver-margin requirements with documented margin.

Final decap quantity is an analysis result rather than a fixed capacitance or
placement percentage. Check leakage, power-up current, rail settling and
resonance, electromigration, density, antenna rules, DRC, LVS, and interaction
with pad/ESD structures after insertion. On-die decap supplements rather than
replaces package power/ground connections and nearby board capacitors.

The placement flow must preserve ordinary filler as a fallback and generate
both fill-cap-enabled and fill-cap-disabled netlists or views for comparison.
If the public models cannot establish that a proposed I/O-rail capacitor is
safe and effective, omit that structure from first silicon and address the
remaining risk through characterized pads, packaging, board layout, or a
lower verified interface mode.

### Incremental first-silicon bring-up

Bring up only one delta from KianV at a time. At reset, all tensor, memory, and
torus output enables remain inactive except the minimum service response. Use
this order, retaining the last passing configuration after any failure:

1. Establish the reference clock, reset, service forwarding, identification,
   static pad control, and virtual test access with every other block held.
2. Enable U0 alone at the lowest legal HyperRAM transaction clock and fixed
   latency. Run register readback, walking-bit, checkerboard, address, and
   pseudorandom tests before increasing its rate.
3. Qualify U1 independently, then repeat the same tests in lockstep x16 mode.
   Qualify U2 and x24 mode on the memory-rich board, including safe shared-pad
   selection and one-bit service. Any optional-memory failure must leave a
   lower-width complete product usable.
4. Enable and externally loop back one torus port at a time, first slowly and
   then at each advertised rate; test pairs, all four always-present ports,
   and finally all six ports on a network-rich board.
5. Enable tensor lanes in small banks while memory and links are quiescent,
   then characterize progressively larger simultaneous lane wakeups.
6. Combine compute, memory, torus, and service traffic incrementally until
   the legal worst-case concurrency patterns pass.

The characterization board must expose I/O and core rail-current measurement,
clock/RWDS and representative link probing, short point-to-point U0 routing,
and optional source-series-resistor footprints. Firmware must expose per-
interface drive, slew, rate, test pattern, CRC/error count, retry count, and
last-failure state through the immutable service path. These controls are
bring-up and recovery mechanisms; production defaults are frozen only after
the characterized passing window is known.

## Development stages

Before changing the functional design, archive and hash the silicon-proven
KianV top-level inputs, submitted final views, local reproduced final views,
tool/PDK lock files, and signoff reports. Generate the initial machine-readable
delta inventory and run the unchanged control flow after any change to shared
physical scripts or configuration.

1. Define tensor formats, accumulator semantics, exception behavior, and the
   command descriptor ABI.
2. Implement and verify one base processing element in every numeric mode.
3. Build a small 2x2 array and verify forwarding, stalls, accumulation, and
   mode grouping.
4. Implement the immutable bootstrap controller and descriptor
   microsequencer. Verify cold boot through the retimed service chain and an
   in-band torus boot packet, then prove that representative CNN and
   transformer schedules do not require a resident CPU. Independently verify
   bootstrap forwarding, inspection, clock/reset control, test entry, and
   recovery without initialized HyperRAM or writable microcode. Implement the
   virtual test-access port, boundary-scan register, internal scan transport,
   and FPGA JTAG-to-service bridge before relying on the service chain as the
   only physical test interface. Measure incremental area and functional-path
   timing with and without scan/debug insertion; reduce optional trace or
   trigger features if the limits in this plan are exceeded.
5. Generate and characterize 64-, 80-, and 96-lane variants with the same
   10 KiB memory architecture. Treat 80 lanes as the baseline.
6. Implement the banked SRAM subsystem with executable behavioral models and
   foundry-macro bindings. Prove conflict-free schedules for advertised fused
   operations.
7. Add centralized packed-format and sparse decoding, GEMV activation
   broadcast/local accumulation, the general online weighted-reduction
   primitives, the vector unit, DMA engine, and operator fusion. Verify
   one-pass attention as a schedule over general primitives rather than a
   fixed transformer-only datapath.
8. Add one source-synchronous link and verify a two-die connection. Then add
   the complete six-capable/four-active torus router, dateline virtual
   channels, multicast, streaming reductions, CRC/retry, and link diagnostics.
   Prove freedom from
   protocol deadlock under arbitrary legal backpressure.
9. Integrate the 50-pin pad interface and asynchronous clock crossings around
   the IS66WVH64M8DBLL-166B1LI timing model. Verify one-device x8 and
   two-device x16 and three-device x24 modes at safe low-speed points and at
   10, 25, 50, and 100 MHz, including reset-default U0 operation, absent
   optional devices, U1/U2 qualification, shared-pad safety, both service
   widths, runtime capability reporting, and mixed-personality clusters.
   Verify one-, two-, five-, and ten-die service chains at 1, 5, 10, 25, 50,
   and 100 MHz, including reversal, enumeration, CRC/retry, and bulk DMA.
   Simulate chains through 1,000 dies and close I/O timing at the demonstrated
   200 Mbit/s pin rate.
10. Verify halt, edge-step, cycle-step, and run-until-event behavior in every
    clock domain and protocol state. Inject indefinitely stopped neighbors,
    disabled timeouts, full FIFOs, reset at every legal boundary, and
    HyperRAM atomic-burst stepping. Compare traces against continuous-clock
    execution.
11. Place and route the complete 80-lane baseline at 80-100 MHz by specializing
    the pinned KianV physical flow rather than constructing a second flow.
    Review the generated delta inventory, compare floorplan, pad ring, PDN,
    macro integration, routing, and signoff reports against the unchanged
    KianV control. Optimize the independent tensor clock toward 200 MHz and
    attempt 300 MHz only with a characterized, bypassable clock source; keep
    every external interface at its separately verified rate.
12. Run representative activity-based power, IR-drop, electromigration,
    package-current, timing, slew, capacitance, fanout, DRC, and LVS checks.
    Analyze legal worst-case simultaneous-switching patterns with extracted
    pad/package/board assumptions. Generate ordinary-filler and
    library-fill-cap candidates from the same placed design, verify every
    fill-cap cell's rail and well connection, and compare their extracted
    transient behavior. Select the smallest passing insertion, then repeat
    timing, IR-drop, electromigration, rail-settling, resonance, DRC, and LVS
    checks. Select and reverify all other mitigations from the same evidence.
    Do not introduce MIM, custom MOS capacitance, or an optional process mask
    in this stage without a separately reviewed change to the first-silicon
    baseline.
13. Place and route the unchanged 64-lane fallback. Attempt the 96-lane and
    300 MHz stretch goals only after the 80-lane baseline passes its acceptance
    gates.
14. Validate single- and small-multi-chip execution in RTL simulation using
    CNN, transformer prefill, transformer decode, normalization, and
    collective communication traces before final signoff. Run the required
    1-, 2-, 4-, 8-, 16-to-64-, 100-, and 900-die topology matrix with absent
    links, extent-one dimensions, and independently enabled wraparound.
    Property-test topology generation, reachability, and command completion
    for every integer population from 1 through 1,000, including prime and
    boundary-ragged populations.
15. Run the same traces in cycle-accurate 25 x 40 memory-rich and 10 x 10 x 10
    network-rich workload models. Measure link utilization, queue occupancy,
    bisection traffic,
    collective time, load balance, and behavior with failed links or dies.
    The model and compiler mapping must exist before freezing the router.

### Tapeout acceptance gates

Tape out the largest generated variant that satisfies all of these conditions
without waivers that obscure first-silicon risk:

- No more than approximately 3.5 mm2 of functional standard-cell area.
- Routed compute setup closure at 80 MHz across required corners; 100 MHz
  preferred. The release records separate 100, 200, and attempted 300 MHz
  compute bins without changing the fixed I/O rates.
- Conflict-free SRAM schedules at the advertised sustained issue rates.
- Demonstrated 200 Mbit/s source-synchronous I/O timing with the selected
  pads, IS66WVH64M8DBLL-166B1LI memory, loading, and board or package
  assumptions, plus passing low-speed x8, x16, and x24 bring-up modes on their
  intended boards.
- Demonstrated reversible, discovered-length one- and two-bit service-chain
  operation from 1 MHz through 100 MHz DDR. One-, two-, five-, and ten-die
  hardware or gate-level configurations and longer simulated configurations
  must include enumeration, concurrent traffic, and direct host-to-HyperRAM
  DMA.
- Acceptable activity-based power, IR drop, electromigration, and package
  current for dense operation.
- Clean required physical verification and reviewed electrical violations.
- The fabrication release identifies the silicon-proven KianV tag and
  submitted GDS, the pinned locally reproduced control flow, and a complete
  machine-readable inventory of every tensor-tile change to the inherited
  top-level, constraints, pad ring, PDN, macro integration, scripts, PDK, and
  signoff configuration. Unexplained shared-flow drift blocks release.
- Correct strict and fast numerical behavior against the declared reference
  models.
- No throughput claim based solely on masked zeros; sparse uplift must be
  demonstrated with compacted lane work.
- Proven torus deadlock freedom and bounded control-message progress under
  arbitrary legal data traffic and link turnaround.
- A modeled 1,000-die workload suite that demonstrates useful scaling for the
  intended CNN, transformer, diffusion, and expert-parallel mappings and
  reports collective overhead explicitly.
- Successful boot, coordinate discovery, partitioning, quarantine, and
  workload completion with representative single-link and single-die faults.
- Standalone completion of the compute, memory, DMA, interrupt, and debug
  acceptance suite with every network port absent or disabled.
- The minimum one-tensor-die, one-U0-HyperRAM system cold-boots in x8 mode and
  completes that standalone suite with U1 and U2 physically absent. Adding a
  passing U1 enables x16 operation; adding a passing U2 on a memory-rich board
  enables x24, four-link, one-bit-service operation without changing command
  semantics. Mixed x8/x16/x24 clusters schedule correctly from reported
  capabilities.
- Shared pads remain high-impedance until immutable personality selection is
  complete. Network-rich boards never enable U2 functions, memory-rich boards
  never enable the two overlaid Z links, and invalid or contradictory strap
  states fail safe with every shared output disabled.
- Identical application descriptors produce equivalent numerical results in
  standalone, rectangular-mesh, partial-torus, and full-torus configurations;
  only placement and collective decomposition may differ.
- The supported wiring generator produces a connected graph for every
  installed population from 1 through 1,000. Each generated system completes
  point-to-point traffic and constructs valid collective groups without
  powered dummy nodes. Regular 30 x 30 and 25 x 40 2D systems and 10 x 10 x 9
  and 10 x 10 x 10 3D systems remain on the coordinate-routing fast path.
- All internal protocols and host/torus links pass manual edge- and
  cycle-stepping tests with arbitrary pauses. HyperRAM requests pass the
  documented safe-boundary and atomic-transaction stepping tests.
- CDC and reset safety properties hold with any clock stopped indefinitely;
  conditional liveness holds when only the clocks and peers required for
  progress eventually resume. Reset epochs prevent acceptance of stale
  credits, packets, DMA responses, and completions.
- A missing, unlocked, or failed internal high-speed clock source cannot block
  boot, service, test, or functional operation from the divided external
  reference. Clock-source bypass and switching are verified across reset,
  halt, and every legal CDC state. No advertised 200/300 MHz compute bin is
  released without routed all-corner timing for that bin.
- The immutable bootstrap/service path provides forwarding, inspection,
  clock/reset control, scan entry, SRAM BIST, memory test, and pad/link
  loopback without working HyperRAM, writable microcode, or tensor logic.
- Wafer-probe and packaged-part tests can execute virtual `IDCODE`, `BYPASS`,
  boundary `SAMPLE/PRELOAD` and `EXTEST`, internal scan, memory BIST, clock
  stepping, and pad/link diagnostics exclusively through the service pads.
  Publish the boundary register, scan descriptions, test vectors, achieved
  stuck-at and transition-fault coverage, and the FPGA JTAG translation.
- JTAG-equivalent additions beyond the required service/bootstrap datapath
  target at most 0.10 mm2 and may not exceed 0.15 mm2 without redesign. Scan
  and boundary insertion do not reduce any advertised functional clock or
  interface bandwidth; optional trace and trigger features are removed first
  if either constraint is missed.
- Extracted simultaneous-switching analysis passes receiver noise margin,
  supply/ground disturbance, and interface timing requirements for every
  advertised bandwidth mode. Any required throttling is reflected in the
  advertised rates rather than hidden in an implementation waiver.
- The pad/package electrical model first reproduces or conservatively bounds
  an observed KianV operating case, then passes the incremental tensor cases:
  HyperRAM DDR/turnaround in x8/x16/x24 modes, all legal four-/six-port and
  one-/two-bit-service concurrency, compute-array wakeup, and their legal
  coincidences. Record the actual KianV and tensor-board
  I/O supplies, pad control settings, loads, termination, and package model.
- First silicon uses only library-provided fill-cap cells for intentional
  on-die decoupling unless a separately approved exception documents the
  process option and closes modeling, reliability, startup, DRC, and LVS.
  The signoff record identifies every inserted fill-cap type, count, voltage
  domain, and placement region; compares extracted ordinary-filler and
  fill-cap cases; and demonstrates that the selected insertion is the
  smallest evaluated configuration that passes with margin. No unverified
  core-rail capacitor is connected to an I/O rail.
- A 200-chain network-rich model loads a fully sharded 125 GiB image in under
  20 seconds. A 500-chain memory-rich model loads 187.5 GiB in under 25
  seconds. Neither uses the torus data plane.

## Tapeout recommendation

The preferred first-silicon target is:

> An 80-lane, 8 x 10 mixed-precision tensor tile with 10 KiB of dynamically
> banked proven GF180 SRAM; general GEMM/convolution, GEMV/decode, and online
> weighted-reduction organizations; and 16 GMAC/s FP4 or 8 GMAC/s
> FP8/fast-BF16 at the 100 MHz functional target. The independent compute
> domain is optimized toward 200 MHz with a 300 MHz post-route stretch bin,
> while every pad remains at or below 100 MHz DDR. The same die supports a
> network-rich x16/128 MiB/400 MB/s/six-link personality and a memory-rich
> x24/192 MiB/600 MB/s/four-link personality. One U0 memory, narrow service,
> and no live network remain a complete minimum product.

The minimum complete product is the same tensor die with only mandatory U0:
64 MiB and 200 MB/s raw memory bandwidth, one service-chain termination, and
all torus ports disabled. U1, U2, and additional tensor dies increase capacity,
bandwidth, and compute scale without defining a different ASIC.

This design deliberately follows KianV's demonstrated macro and functional
area envelope. It replaces KianV's irregular MMU/TLB/global-control routing
with registered local arithmetic. The same source generates a 64-lane fallback
and a 96-lane stretch variant, but the balanced 80-lane organization is the
planned implementation.
