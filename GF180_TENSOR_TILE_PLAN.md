# GF180 1x1 Tensor Tile Plan

## Objective

Build a flexible, tileable neural-network inference accelerator for one
wafer.space 1x1 GF180MCU die. Each accelerator die is paired with its own
external memory and can be connected to neighboring accelerator dies.

The design should accelerate common CNN, transformer, diffusion, recurrent,
and dense inference workloads. It should support INT4/INT8, FP4/FP8, and
FP16/BF16 operation without paying the area cost of a full FP32 floating-point
FMA in every processing element.

## Fixed constraints

- Die: wafer.space GF180MCU 1x1 slot.
- Die dimensions: 3.932 x 5.122 mm, or 20.140 mm2.
- Area inside the pad ring: 12.902 mm2.
- Signal I/O budget: 50 pins, excluding power and ground.
- Maximum per-pin signaling rate: 200 Mbit/s or a 200 MHz
  source-synchronous clock.
- One closely coupled external memory per accelerator die.
- Multi-chip operation must use coarse tensor tiles, not a cycle-synchronous
  systolic array spanning package boundaries.

If the 50-pin limit includes power and ground, the interface allocation in
this plan must be reduced before implementation.

## KianV physical reference

KianV provides a known routed design on the same die:

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

## Recommended implementation

| Resource | Target |
| --- | ---: |
| SRAM | 10 KiB in 20 proven 512x8 macros |
| Tensor array | 8 x 16, with 128 base lanes |
| INT4/FP4 issue width | 256 MACs per cycle |
| INT8/FP8 issue width | 128 MACs per cycle |
| Fast block-BF16/FP16 issue width | 128 MACs per cycle |
| Strict BF16/FP16 issue width | 32 MACs per cycle |
| Initial compute clock | 100 MHz |
| Stretch compute clock | 125 MHz |
| External memory bandwidth | Approximately 400 MB/s raw |
| Neighbor links | Four 4-bit, 100 MB/s half-duplex links |
| Controller | Tiny RV32E core or tensor microsequencer |

### Nominal peak throughput

| Format | 100 MHz | 125 MHz |
| --- | ---: | ---: |
| INT4/FP4 | 25.6 GMAC/s | 32.0 GMAC/s |
| INT8/FP8 | 12.8 GMAC/s | 16.0 GMAC/s |
| Fast block-BF16/FP16 | 12.8 GMAC/s | 16.0 GMAC/s |
| Strict BF16/FP16 | 3.2 GMAC/s | 4.0 GMAC/s |

Structured 2:4 sparsity may provide up to twice the effective throughput when
the workload and encoding allow skipped work.

## Area budget

| Component | Functional area estimate |
| --- | ---: |
| Twenty SRAM macros | 4.19 mm2 |
| 128-lane tensor array | 2.0-2.5 mm2 |
| Vector and special-function unit | 0.35-0.55 mm2 |
| DMA and SRAM controllers | 0.25-0.40 mm2 |
| Mesh router and link logic | 0.20-0.35 mm2 |
| RV32E controller or microsequencer | 0.10-0.20 mm2 |
| Clock, test, and miscellaneous glue | 0.20-0.35 mm2 |
| Total functional area | 7.3-8.5 mm2 |

Set an implementation limit of approximately 3.5 mm2 for functional standard
cells. If synthesis exceeds that limit or routing becomes congested, reduce
the array from 128 to 96 base lanes before sacrificing SRAM or physical
margin.

### Arithmetic plausibility check

KianV's complete 32x32 multiplier occupies approximately 0.092 mm2. Although
multiplier area does not scale perfectly with operand width, quadratic scaling
suggests that 128 bare 8x8 multipliers would occupy roughly:

```text
128 x 0.092 / 16 = 0.74 mm2
```

Registers, accumulators, muxes, format handling, and clocking are expected to
expand the complete array to approximately 2.0-2.5 mm2.

## Processing element

Each base lane should provide:

- One signed/unsigned 8-bit multiplier, splittable into two 4-bit operations.
- A local weight register and partial-sum accumulator.
- INT4, INT8, FP4, and FP8 input handling.
- Saturation, configurable rounding, and zero detection.
- Fine-grained clock gating for inactive and zero-valued lanes.
- Local nearest-neighbor systolic forwarding.

Groups of four base lanes cooperate for strict FP16/BF16 multiplication and
FP32 accumulation. Fast FP16/BF16 operation uses block scaling or a similarly
bounded wide fixed-point accumulation scheme. This keeps common formats
available without duplicating a large general floating-point accumulator in
every lane.

Strict mode should provide deliberate NaN and infinity behavior. Subnormal
support may be optional, with an explicit flush-to-zero mode.

## Vector and special-function unit

A roughly 16-lane vector unit should handle operations poorly suited to the
systolic array:

- Bias and residual addition.
- ReLU, Leaky ReLU, clamp, and pooling.
- GELU and sigmoid approximations.
- Sum, maximum, and dot-product reductions.
- Reciprocal and reciprocal square root.
- LayerNorm and RMSNorm.
- Softmax.
- Rotary positional embedding.
- Quantization, saturation, and datatype conversion.
- Gather/scatter assistance and mixture-of-experts routing.

Expensive transcendental functions should use small lookup tables followed by
low-order interpolation rather than general arithmetic implementations.

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

The recommended 10 KiB uses almost the same macro footprint as KianV and can
be divided initially as follows:

| Purpose | Capacity |
| --- | ---: |
| Activation ping-pong buffers | 3 KiB |
| Weight ping-pong buffers | 3 KiB |
| Partial sums and vector scratch | 3 KiB |
| Network and command queues | 1 KiB |

All 20 macros should be separately banked, and software should be able to
repartition their roles. Distributed PE accumulator registers provide
additional local state.

Operator fusion is mandatory. Intermediate activations should remain on-chip
through sequences such as:

```text
matrix multiply -> bias -> residual -> activation -> quantization
```

## External memory interface

Allocate approximately 22 signal pins to a 16-bit, HyperRAM-like interface:

```text
16  bidirectional data pins
 2  byte strobes or RWDS pins
 2  clock pins
 1  chip select
 1  reset
```

Operate it at either 200 MHz SDR or 100 MHz DDR. Both provide no more than 200
Mbit/s per data pin and approximately 400 MB/s raw bandwidth. Commands and
addresses should travel in-band to avoid a separate parallel address bus.

The controller should favor long bursts and overlap memory transfers with
computation. A realistic sustained-bandwidth objective is 300-360 MB/s.

## Fifty-pin allocation

| Interface | Pins |
| --- | ---: |
| Attached x16 memory | 22 |
| Four neighbor links | 20 |
| Host and control interface | 6 |
| Spare or test | 2 |
| Total | 50 |

The six host/control pins provide a four-wire SPI command/debug interface, a
reference clock, and global reset. The spare pins may become an interrupt and
test-mode signal.

## Multi-chip mesh

Each north, east, south, and west port receives four bidirectional data pins
and one source-synchronous strobe. At 200 Mbit/s per data pin, each port
provides 100 MB/s in its currently selected direction.

The mesh should implement:

- Packet framing and CRC/error detection.
- Credit-based flow control and virtual channels.
- Hardware multicast.
- Tree, ring, and nearest-neighbor reductions.
- Barriers and globally meaningful tile coordinates.
- Direct memory-to-network and network-to-SRAM DMA.

Separate dies must cooperate at tensor-block granularity. They should not try
to extend the internal systolic array cycle by cycle across package links.

Supported scaling modes include pipeline, tensor, expert, and data
parallelism.

## Data movement and command model

The DMA engine should support:

- Multidimensional strided transfers.
- Transpose and layout conversion while moving data.
- Circular buffers and automatic double buffering.
- Limited gather/scatter for embeddings.
- Weight and activation multicast.
- 2:4 and block-sparse decoding.
- Zero-run and lightweight weight decompression.
- Concurrent memory, compute, and network operations.

The host submits coarse commands rather than scalar instructions:

```text
MATMUL
CONV2D
REDUCE
NORMALIZE
ELEMENTWISE
LAYOUT_TRANSFORM
SEND_TILE
RECEIVE_TILE
```

Descriptors contain addresses, shapes, strides, formats, quantization state,
fusion operations, and chip-grid coordinates. The small controller handles
sequencing and uncommon cases, not tensor inner loops.

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
dynamic graphs, large random embedding lookups, and batch-one LLM decoding.

At approximately 320 MB/s sustained external bandwidth, the memory can supply
about 320 million new FP8 weights/s or 640 million packed FP4 weights/s. The
array therefore requires substantial reuse to approach peak throughput.
Convolution, batched GEMM, and transformer prefill can provide that reuse;
batch-one transformer decoding is normally bandwidth-bound.

Examples of full-weight-sweep ceilings at 320 MB/s are:

| Local model or shard | Weight bytes | Maximum sweeps per second |
| --- | ---: | ---: |
| 100M parameters at FP4 | 50 MB | approximately 6.4 |
| 100M parameters at FP8 | 100 MB | approximately 3.2 |
| 256M parameters at FP4 | 128 MB | approximately 2.5 |
| 128M parameters at BF16 | 256 MB | approximately 1.25 |

## Physical-design strategy

Arrange SRAM banks symmetrically around the tensor array so their consumers
are nearby:

```text
             weight and input SRAM banks
       +------+------+------+------+
       |                            |
 SRAM  |      8 x 16 tensor array  | SRAM
 banks |                            | banks
       | vector unit    DMA/router |
       +------+------+------+------+
          accumulator/output banks
```

Pipeline every PE boundary and keep multiplier-to-accumulator paths local. A
100 MHz clock provides a 10 ns cycle and is the initial signoff objective; 125
MHz provides 8 ns and is a stretch target. Floating-point normalization and
format conversion should remain outside the innermost accumulator feedback
path or operate over multiple cycles.

Track routed wire length, buffer insertion, maximum transition, capacitance,
fanout, and slow-corner setup timing from the first floorplanned build. The
regular array should be easier to route than KianV's MMU-heavy CPU, but this
must be demonstrated rather than assumed.

## Development stages

1. Define tensor formats, accumulator semantics, exception behavior, and the
   command descriptor ABI.
2. Implement and verify one base processing element in every numeric mode.
3. Build a small 2x2 array and verify forwarding, stalls, accumulation, and
   mode grouping.
4. Characterize 64-, 96-, and 128-lane synthesized variants against the
   3.5 mm2 functional-standard-cell limit.
5. Implement the banked SRAM subsystem with executable behavioral models and
   foundry-macro bindings.
6. Add the vector unit, DMA engine, and operator fusion.
7. Add one mesh port, then the complete four-port router and collectives.
8. Integrate the 50-pin pad interface and asynchronous clock crossings.
9. Place and route the 96- and 128-lane candidates using the KianV physical
   flow as the reference.
10. Choose 128 lanes only if timing, routing, electrical checks, and physical
    margin are credible; otherwise tape out the unchanged 96-lane variant.
11. Validate multi-chip execution in RTL simulation using transformer and CNN
    operator traces before final signoff.

## Tapeout recommendation

The preferred first-silicon target is:

> A 128-lane mixed-precision tensor tile with 10 KiB of proven GF180 SRAM,
> 25.6 GMAC/s FP4 and 12.8 GMAC/s FP8/BF16 at 100 MHz, a 16-bit 400 MB/s
> attached-memory interface, and four 100 MB/s neighbor links.

This design deliberately follows KianV's demonstrated macro and functional
area envelope. It replaces KianV's irregular MMU/TLB/global-control routing
with registered local arithmetic and retains a 96-lane fallback if the full
array does not close cleanly.
