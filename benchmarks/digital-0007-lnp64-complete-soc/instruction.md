# IC-T8-001: Complete LNP64 system on chip

## Task

Implement `lnp64_soc`: a complete four-core, sixteen-context LNP64 SoC targeting
GF180MCU at 200 MHz. It must execute every active instruction and implement every
engine protocol and object class in the frozen LNP64 ISA. It must boot real
images, maintain coherent SMP state, enforce domain authority, and operate its
memory and device interfaces.

Do not submit an opcode demonstrator, emulator wrapper, single-core substitute,
or collection of disconnected accelerators. One synthesizable design must pass
the entire contract.

The participant-visible authorities are:

- `/app/input_files/spec/lnp64_isa.md` for architectural behavior;
- `/app/input_files/spec/isa_spec.json` for encodings and the instruction
  denominator;
- `/app/input_files/contract/soc_profile.json` for the platform, interfaces,
  clocks, memory map, and limits;
- `/app/input_files/contract/platform_devices.json` for reset authority,
  device profiles, software-visible registers, and JTAG scan behavior;
- `/app/input_files/contract/pdk.lock.json` for the physical toolchain;
- `/app/input_files/memory/sram_macros.json` for approved memory interfaces; and
- `/app/input_files/spec/boot_image.py` for the exact boot image and UART
  framing.

The verifier freezes the same source revision and owns the conformance outcomes,
coverage ledger, physical-flow contract, and reward calculation.

## Submission

Copy the starter RTL and integration manifest from `/app/input_files/`, then
write candidate files only below `/app/output/`:

```text
/app/output/rtl/lnp64_soc_pkg.sv
/app/output/rtl/lnp64_soc.sv
/app/output/rtl/*.sv
/app/output/integration/soc_manifest.json
```

Keep the `lnp64_soc` module name, port list, and package contract unchanged.
Additional RTL files are allowed. Submit synthesizable SystemVerilog only. The
release verifier supplies memory models, SDRAM, SD-card, UART, PIPE, JTAG, and
GF180MCU implementation fixtures. Generated results, tool binaries, PDK files,
encrypted RTL, DPI models, and precomputed test answers are not deliverables.
Simulator control or file I/O, tool-dependent branches, synthesis-exclusion
pragmas, hierarchy overrides, and candidate black boxes are forbidden.

## Machine contract

Implement four identical coherent cores. Each core holds four resident hardware
contexts. Every context has the complete architectural GPR, FPR, 512-bit vector,
mask, PCR, continuation, and domain state. Implement all 619 active instruction
identities. The three assigned-dark identities—`cap.weaken`, `cap.upgrade`, and
`window.faultable`—must return exactly `-UNSUPPORTED`.

The reference oracle runs one shared image set under `soc`, `bare`, and
`hosted-dev`; their normalized results are identical. Hardware therefore runs
each image once through the frozen JTAG flat-exec adapter and is compared with
that consensus result. Reachability is not correctness: every identity must
also pass its independent semantic oracle.

Implement the complete architectural substrate, including:

- epoch cells, capability tables, transfers, revocation, and reuse safety;
- gates, continuations, machine calls, cancellation, and fault delivery;
- endpoints, messages, waits, futexes, readiness, and work queues;
- mapping, paging, backing, DMA, interrupt, and memory-ordering protocols;
- domains, builders, views, placement, budgets, scheduling, and lifecycle;
- timers, the monotonic timebase, reservations, and bounded engine progress;
- typed objects, cursors, streams, service bindings, and device discovery;
- state capture, restore, live succession, debug, and architectural observation;
- scalar binary32/binary64 floating point; and
- the complete VLEN=512 vector and mask profile.

Construction is free. Hardwired logic, pipelines, sequencers, control stores,
and immutable microcode are all valid when their observable behavior matches the
ISA. Pageable software services and host emulation are not implementations of
mandatory engine behavior.

## Memory and I/O

The SoC uses the memory map and exact top-level signals in
`/app/input_files/contract/soc_profile.json` and
`/app/input_files/rtl/lnp64_soc.sv`.

The SoC maps 64 MiB of a 128 MiB physical, 32-bit, four-bank SDR SDRAM geometry
at 100 MHz with CAS 2, byte masks, refresh, and a verified 200-to-100-MHz
clock-domain crossing. The
fixed SRAM module interfaces in `/app/input_files/memory/` are available for
caches, register files, queues, and engine metadata. They run at no more than
50 MHz, so a core access takes at least four core cycles. The release verifier
replaces them with characterized, banked implementations of the pinned PDK's
512-by-8 SRAM. They are the only permitted physical black boxes.

The device set is mandatory:

- 4-bit SDHC;
- UART;
- PCIe Gen1 x1 endpoint transaction/data-link logic at a 16-bit, 125-MHz PIPE
  boundary, including BAR handling, MSI, bus-master DMA, and the LNP64 IOMMU;
- monotonic timer and event/interrupt fabric;
- a Hash_DRBG fed by the synchronous conditioned-entropy handshake;
- reset and clock control with boot straps; and
- JTAG debug with halt, resume, register access, and memory access.

The PCIe SerDes, analog PHY, and physical entropy source are outside the
boundary. The on-chip endpoint, DMA, requester identity, invalidation,
interrupt, IOMMU behavior, and DRBG are inside.

Top-level ports are logical, core-side pad interfaces. The pad ring, ESD,
level shifters, package parasitics, and board timing are outside this digital
benchmark.

## Boot

Boot ROM implements three selected paths:

- `boot_sel_i == 2'b00`: read the image from SDHC beginning at LBA 2048;
- `boot_sel_i == 2'b01`: receive the benchmark framed protocol over UART; and
- `boot_sel_i == 2'b10`: enter JTAG-halted state.

`2'b11` is reserved and must assert `boot_error_o` within 32 core cycles after
reset release. The 64-byte image header and UART framing are defined by
`/app/input_files/spec/boot_image.py`. ROM checks magic, version, RX/RW segment
bounds, address bounds, entry alignment, and CRC-32 before publishing the first
domain and transferring control. Invalid images never execute.
For JTAG boot, the reset-vector text window is a debug-writable SRAM alias, not
the immutable physical boot ROM.

## Physical contract

The verifier synthesizes and routes the complete submitted design with the
pinned GF180MCU option-D flow and benchmark SRAM abstracts. Eligibility requires:

- candidate hierarchy that elaborates without unresolved cells;
- no inferred latches or combinational loops;
- a completed routed design with zero detailed-routing DRC errors;
- no setup violations under the supplied multi-clock SDC, including the
  5.000-ns core clock, 100-MHz SDRAM clock, and 125-MHz PIPE clock; and
- reset, reserved-boot rejection, and JTAG IDCODE/status checks on the
  unmodified mapped netlist.

There is no maximum area or pin-count gate. Area, power, and frequency beyond
200 MHz are ranked after eligibility.

## Performance

Microarchitecture is unconstrained. The functional machine may be in-order,
out-of-order, hardwired, or sequenced. The cycle targets in
`/app/input_files/contract/soc_profile.json` describe the ambitious machine;
they are design guidance, not hard gates or separately scored claims. The
release score uses only post-route measurements produced by the frozen flow.

## Acceptance

Correctness is indivisible. Every hard gate must pass. A missing instruction,
stubbed engine family, incoherent SMP outcome, unauthorized DMA, failed boot
path, or negative 200-MHz setup slack makes the submission ineligible.

RewardKit weights architectural passage at 0.50, physical eligibility at 0.20,
and measured implementation quality at 0.30. Because every hard gate must pass,
an eligible design receives full architectural and physical levels. Its quality
level is:

```text
quality = 0.40*fmax + 0.30*area + 0.30*power
reward  = 0.70 + 0.30*quality
```

`fmax = min(estimated_fmax_mhz/250, 1)`,
`area = min(100/area_mm2, 1)`, and `power = min(5/power_w, 1)`.
Ineligible designs receive zero.

The release suite uses the frozen all-instruction corpus, directed SMP and boot
programs, pin-level protocol peers, a PCIe root model, and one deterministic
GF180 implementation flow. The coverage ledger in `/tests/coverage/` states the
exact exercised scenarios.

Run `make -C /app/input_files visible OUTPUT=/app/output` for the
participant-visible interface smoke test.
