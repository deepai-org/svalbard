# Programmable analog/PHY companion: one slot, 50 connections

**Current operating decision:** RF and wired payload operation are mutually exclusive on the same chip. Both capabilities remain required; additional physical resource sharing is encouraged. See the [exclusive-engine policy](../../projects/programmable_transceiver_platform/spec/exclusive-engine-policy.md), which supersedes simultaneous-operation requirements below. Model/RTL enforcement and resource rebudgeting remain implementation work.

Implementation progress and the executable budget are tracked in the [project](../../projects/programmable_transceiver_platform/README.md). Run `make transceiver-contract` to check the current planning invariants; this does not verify physical feasibility or tapeout readiness.

## Product and boundary

Build the full `programmable_transceiver_platform` as a **generic analog/PHY companion for FPGA regular GPIOs**, with SPI-only MCU operation at lower throughput. The chip owns analog conversion, RF translation, high-speed electrical signaling, precise timing, and bounded data movement. The external FPGA owns Wi-Fi modem/MAC, Ethernet PCS/MAC as needed, PCIe link/transaction/endpoint logic, and application processing. Example configurations exercise common primitives; they do not define three independent fixed-function chips.

The first fabrication is the complete companion, not a feasibility coupon. Keep one RF RX/TX chain and one full-duplex wired lane. The former four-pair HDMI allocation and on-chip modem/MAC/PCIe endpoint are superseded. A complete HDMI source is outside this pinout. A generic FPGA means no dedicated multi-gigabit transceiver, PCIe hard block, or vendor-specific host protocol is required; it does **not** mean every FPGA can run the maximum GPIO rate or has enough logic for every protocol.

## Accepted operating envelope

The user explicitly accepts operation over relatively narrow temperature and supply-voltage ranges, including peak performance around a specific controlled operating point. Broad commercial/industrial environmental coverage is not required for this chip. Optimize the full companion for that controlled envelope rather than spending performance or area on an unrequested broad range.

Numerical limits remain to be selected from evidence: specify junction temperature (not just room temperature), each rail's voltage at the die, ripple/droop and control tolerances, warm-up/calibration conditions, and any required board regulation or thermal control. Account for self-heating in each active mode and transients when switching modes. Process variation and mismatch remain separate uncertainties; this preference does not assume a typical-process die or authorize unsafe bias. Characterize out-of-envelope behavior separately without treating every exploratory corner as a required peak-performance pass. Freeze the required operating window and process/yield claims explicitly before signoff.

## Physical envelope

Use one wafer.space **1×1 slot** and **50 total external connections: 36 signals plus 14 provisional supply/ground connections**. Provider information checked 2026-09-19: [wafer.space](https://wafer.space/price.html) lists a 3.93 × 5.12 mm full die and 12.92 mm² default-ring core. The [slot template](https://mith.ro/gf180mcu-project-template/) specifies a 3.05 × 4.24 mm core and 74 default pads, including only two analog signals. This design needs a custom mixed-signal pad ring and custom bare-die assembly or an explicitly accepted equivalent; the standard chip-on-board offer requires the default ring.

Retain a conservative **12.92 mm² core ceiling** until placed pads, ESD, seal ring, and isolation establish the actual usable envelope. This is an area budget, not demonstrated fit. Count every electrically connected package terminal, including any exposed ground paddle; do not hide additional supplies, loop-filter terminals, or references outside the 50 budget.

## Exact signal budget

Logical IDs are allocation labels, not package numbering. Final ordering follows pad placement, return paths, and bond-wire extraction.

| IDs | Signals | Count | Function |
|---|---|---:|---|
| S01–S02 | `WIRE_TX_P/N` | 2 | Programmable differential output driver and serializer |
| S03–S04 | `WIRE_RX_P/N` | 2 | Differential termination/equalizer/slicer/CDR input |
| S05–S06 | `RF_RX_P/N` | 2 | Differential RF receiver input |
| S07–S08 | `RF_TX_P/N` | 2 | Differential RF transmitter output |
| S09 | `REF_IN` | 1 | External reference oscillator; separately qualified external-LO injection mode |
| S10–S13 | `HOST_CS_N`, `HOST_SCLK`, `HOST_MOSI`, `HOST_MISO` | 4 | Dedicated four-wire SPI control, FIFO access, calibration, and recovery |
| S14 | `RESET_N` | 1 | Whole-chip reset; individual engine resets are registers/fast-link commands |
| S15–S24 | `D2H_D[9:0]` | 10 | Chip-to-FPGA words |
| S25 | `D2H_CLK` | 1 | Forwarded chip-to-FPGA clock |
| S26–S35 | `H2D_D[9:0]` | 10 | FPGA-to-chip words |
| S36 | `H2D_CLK` | 1 | Forwarded FPGA-to-chip clock |
| | **Signals** | **36** | |

There is no dedicated interrupt, crystal pair, general GPIO bank, external-memory interface, or wide analog monitor bus. Poll status over SPI or receive events in the fast link. The host FPGA directly drives board PA enable, RF switch, and other connector sidebands; deterministic scheduled TX and timestamped status support that coordination. An MCU can drive those board controls too. External PA, baluns/matching, RF filtering, reference oscillator, and antenna remain board components.

`REF_IN` normally accepts a qualified single-ended clock. PCIe's differential common reference needs a suitable external clock receiver/buffer; its jitter contribution belongs in the budget. Do not route an arbitrary fabric-generated FPGA clock into the RF PLL and assume adequate phase noise. External LO injection is an alternate local RF input mode that requires separate pad/loading qualification, not permission to put GHz signals through an ordinary digital buffer. Normal operation uses on-chip synthesizers. No claim of simultaneous reference and external LO use on this one pin.

## Power/ground: provisional 14

| Domain | Supply connections | Ground connections | Total |
|---|---:|---:|---:|
| Digital core/control | 1 | 1 | 2 |
| Host GPIO bank (two local segments) | 2 | 2 | 4 |
| Wired analog | 2 | 2 | 4 |
| RF analog | 1 | 1 | 2 |
| PLL/reference | 1 | 1 | 2 |
| **Total** | **7** | **7** | **14** |

Use qualified device/pad voltages; 3.3 V is the initial digital compatibility baseline. A separately supplied host I/O domain enables characterization of additional voltages but is not itself evidence of 1.8/2.5 V support. GPIO compatibility requires matching thresholds, drive, supply sequencing, and absolute limits. Level translation is acceptable at low speed; the full-speed path needs its own timing-qualified solution.

Fourteen is not a calculated minimum. The [pass-6 power partition](../../projects/programmable_transceiver_platform/spec/power-partition.md) replaces the insufficient single host supply/return pair with two local segments of five and six fast outputs, taking one pair from CORE. The core now has an explicit unmeasured 48 mA ceiling; the two host paths each target at most 55 mA. The limited current extrapolation fits those host ceilings but does not qualify any domain. Distribute physical grounds for short RF, clock, and wired returns; provide board filtering and local decoupling. Freeze this count only after current, ground-bounce, bond-wire inductance, ESD, substrate, and thermal analysis. If it fails, redesign within 50 terminals and republish affected budgets; do not quietly remove host bits or add a hidden paddle. Do not fabricate a smaller substitute chip.

## Generic resources

Physical-interface evidence is tracked in the [GPIO pad screen](../../projects/programmable_transceiver_platform/spec/gpio-physical-screen.md). The installed output tables do not qualify 312.5 Mbit/s operation, and one plausible capacitive-load case exceeds the documented single supply-cell DC limit before internal losses. The provisional host supply/ground allocation must remain open until clock/data and simultaneous-switching analysis closes it.

- **RF/analog island:** tunable transconductors, programmable RC networks, quadrature commutating mixers, gain stages, sample/hold resources, I/Q ADCs and DACs, and segmented current outputs. Target one 2.4 GHz chain with approximately 20 MHz channel bandwidth. Start the converter budget around 20–40 MS/s per I/Q component and 8–12-bit transport formats; nominal resolution is not ENOB or an EVM guarantee. Freeze real analog performance from evidence. Same-frequency full-duplex radio is not promised.
- **Wired island:** programmable differential termination and common mode, continuous-time equalization, limiting/slicing, multiphase sampling, CDR/phase interpolation, serializer/deserializer, segmented TX swing/pre-emphasis, electrical-idle control/detection, receiver detection, and local loopbacks. Targets include 1.25 GBd and 2.5 GT/s NRZ. Rate, channel loss, and swing ranges are bounded, not universal.
- **Shared timing:** share the external frequency reference, timestamp/control infrastructure, and reusable divider/phase-control designs. Provide independently controlled RF synthesis and wired clock recovery/generation; one oscillator must not be required to serve simultaneously as RF LO and recovered wired clock. Preserve per-engine resets and local clock observation.
- **Small digital primitives:** gearboxes, optional bypassable 8b/10b coding, comma alignment, programmable pattern/ordered-set matching, small elastic FIFOs, sample packing, optional bounded decimation/interpolation, PRBS generation/checking, capture/playback, calibration sequencers, and the host transport. Digital connections between islands may be flexible; high-frequency analog routes remain short and local.
- **External FPGA:** FFTs, modulation/coding, packet processing, Ethernet negotiation/PCS functions not explicitly implemented on-chip, PCIe LTSSM and link/transaction behavior, endpoint configuration, and application logic. Supply reusable HDL adapters; do not require the FPGA to own an inaccessible internal hard-PCIe PHY interface.

Programmability means an exposed resource graph, documented routing and clock constraints, atomic configuration groups, and capability discovery. Provide raw/bypass paths so convenience blocks never force a protocol. Only claim applications within measured bandwidth, dynamic range, timing, and electrical envelopes.

## Sharing between RF and wired resources

Use **two specialized electrical front ends feeding related programmable local tiles, backed by shared digital services**. Distinguish reusable circuit designs instantiated in both islands from a single physical resource arbitrated between them. Local duplication is appropriate when required for continuous simultaneous operation; sharing is justified by measured area/power benefit after routing, isolation, and arbitration costs.

| Resource | Sharing policy | Concurrency requirement |
|---|---|---|
| SPI, configuration, GPIO transport | One common implementation | Reserve transport capacity per active engine; recovery remains independent of high-speed clocks |
| Capture/playback and configuration memory | Shared banked memory with separate queues and ownership | Guaranteed service for continuous RX/TX; account for aggregate reads, writes, and bank conflicts |
| Pattern engines, PRBS, packing, optional coding/filtering helpers | Common programmable digital resources | Allocate sufficient instances or scheduled throughput for declared simultaneous modes |
| Calibration sequencing | Shared controller with local trim storage and correction circuits | Calibrating one island must not disturb the other's active settings; disruptive calibration requires an explicit quiet window |
| Voltage/current references | Shared master references with locally filtered/buffered distribution | Bound supply/substrate coupling, settling, and common-reference failure effects |
| Clocking | Shared frequency reference and control; independent RF and wired clock engines | Preserve RF LO quality and wired CDR tracking simultaneously |
| Samplers, comparators, transconductors, current-source cells | Reuse circuit designs in a family of locally instantiated tiles | Size variants for their noise, loading, linearity, and speed envelopes |
| RF matching/input gain and wired termination/equalization | Specialized local interfaces | Do not join sensitive RF input nodes to wired termination networks |
| RF output and wired line driver | Specialized output stages using reusable cell designs where suitable | Preserve independent load, swing, linearity, and termination requirements |

**Local tile family:** combine clocked switches/sample capacitors, programmable transconductance or current weighting, a local summing node, optional integration/comparison, and selectable sampling phases. Supported local configurations can implement mixing, baseband filtering, wired sampling/equalization, or measurement functions. Specify a small set of validated topologies and sized variants rather than one universal cell. Do not imply that one physical sampler can service unrelated RF and wired clocks simultaneously.

**Converter access:** keep the I/Q converters physically near the RF/baseband island. Add selected buffered, bandwidth-limited diagnostic paths from wired monitor nodes, with local isolation and explicit loading budgets. These support slow amplitude/threshold monitoring and, where separately designed and verified, equivalent-time eye measurements using local sampling/phase sweeps. The 20–40 MS/s converters do not become real-time multi-GS/s wired ADCs. DAC resources may supply bounded diagnostic stimulus through buffered local paths; they do not replace the line-rate serializer/driver.

Converter ownership is exclusive unless the exact sampling schedule, settling, and bandwidth support multiplexing. A diagnostic allocation may pause RF conversion only in an explicitly requested mode. Simultaneous RF and wired service retains the wired lane's dedicated slicers and local monitors; shared diagnostic conversion is not on its mandatory data path.

**Bounded analog reuse:** expose selected local filter, gain, summing, and sampling connections for repurposing an idle island. Route only buffered lower-bandwidth observations between islands. No chip-wide high-frequency analog crossbar. Configuration metadata declares occupied tiles, converters, clock domains, memory banks, and incompatible modes; resource conflicts are rejected before atomic application. Quiesce and isolate affected paths during reassignment.

Include the switches, monitor buffers, arbitration, local reference distribution, and isolation in the existing area and noise budgets. Validate both active-island aggressor cases, bank/transport contention, calibration activity, and disconnected-path loading. Keep only sharing paths whose extracted behavior preserves the declared RF/wired envelopes; maintain generic local programmability even where physical pooling is not worthwhile.

## GPIO transport: streaming v2 (legacy `svalbard_phy_gpio_v1` retained for comparison)

This is a **new** transport, not a reinterpretation of `svalbard_stream8_sdr_v1`. Two independent fixed-direction 10-bit buses avoid turnaround and allow continuous RX and TX. Ordinary single-ended GPIO data pins plus clock-capable GPIO inputs are required. An FPGA wrapper uses standard input/output registers or DDR I/O primitives; it does not use multi-gigabit transceivers. Portable core RTL is separated from small device-specific clock/DDR wrappers and constraints.

Each 64-word frame now has five protected header words followed by 59 scheduled payload words. Header fields carry counts, sequence and commands with detection-only extended-Hamming protection; payload streams without mandatory CRC/quarantine. The [v2 specification](../../projects/programmable_transceiver_platform/spec/streaming-transport-v2.md) defines the default integrated RTL. Legacy CRC v1 remains a compile-time comparison. Word-aligned startup is implemented; DDR alignment, hardware command latency and clock-domain qualification remain open.

| Host profile | Word rate per direction | Raw bit rate per direction | Payload budget after 59/64 allocation |
|---|---:|---:|---:|
| 25 MHz SDR | 25 Mword/s | 250 Mb/s | 230.46875 Mb/s |
| 50 MHz SDR | 50 Mword/s | 500 Mb/s | 460.9375 Mb/s |
| 125 MHz DDR | 250 Mword/s | 2.5 Gb/s | 2.3046875 Gb/s |
| **156.25 MHz DDR** | **312.5 Mword/s** | **3.125 Gb/s** | **2.880859375 Gb/s** |

All rates are design targets requiring GF180 pad/package/board and FPGA closure. At the top profile, each GPIO carries 312.5 Mbit/s, not 2.5 Gbit/s. Frames recur every 204.8 ns at the top profile; TX staging, header acceptance, command scheduling and CDC add latency. Explicitly bound latency/jitter for PHY control events. Do not service timing-critical operations through software SPI transactions.

D2H uses its forwarded clock. In synchronous wired profiles, the FPGA derives H2D timing from D2H using clocking resources and returns a phase-adjusted forwarded clock; the ASIC must not require a global board trace phase relationship. Qualify center-aligned capture, deskew, reset sequencing, DDR edge order, and clock loss. An independently clocked host mode requires proven elastic-buffer and frequency-offset management. Buffers cannot absorb a permanent source/sink frequency difference.

Transport capacity is shared by active engines in each direction. Static bandwidth reservations and credits protect continuous sources; stopped RF sampling is not a valid way to hide overflow. Count and timestamp dropped samples. Wired TX underflow follows a declared idle/fault policy and may terminate a link; it must not silently repeat data. A line-rate PHY must consume/produce continuous traffic, including training and idle sequences.

## Example configurations and budgets

| Configuration | Companion role | External FPGA role / limit |
|---|---|---|
| Custom SDR / Wi-Fi RF | RF conversion, I/Q sampling and playback, timing and gain | DSP/modem/MAC; 40 MS/s × I/Q × 12 bits = 960 Mb/s per active direction before transport metadata |
| 1000BASE-X | 1.25 GBd electrical lane, CDR, raw 10-bit words or optional coding/alignment | PCS/MAC and optical module/appropriate board medium; raw line traffic fits 125 MHz DDR host profile |
| PCIe Gen1 x1 system | 2.5 GT/s PHY, raw symbols or decoded data/flags, electrical-idle and receiver-detect primitives | Soft controller plus verified transport-to-PHY adapter; full raw line traffic fits the 156.25 MHz DDR profile |
| Generic serial protocol | Configurable NRZ lane and optional coding/framing helpers | Arbitrary protocol within declared electrical and timing limits |
| Measurement/capture/playback | PRBS, loops, timing sweeps, sample memory, calibration | FPGA analysis at speed or MCU reading captures over SPI |

For PCIe, optional decoded words can carry eight data bits, a control-character flag, and an aggregate decode-error flag; detailed errors remain observable in raw mode/counters. Keep line coding and generic alignment bypassable. Raw 10-bit mode transports every line bit without assuming a specific encoding. Control/status overhead is already reserved in the table; additional metadata must fit the remaining headroom.

At the top host profile, one raw 2.5 Gb/s lane leaves about 380.9 Mb/s per direction before further metadata. A concurrent 20 MS/s, 8-bit I/Q stream needs 320 Mb/s and is a plausible allocation; 40 MS/s, 12-bit I/Q at 960 Mb/s does not fit alongside it. Do not promise every engine's maximum rate simultaneously. A first coexistence target is 1000BASE-X-rate raw traffic plus 40 MS/s, 12-bit I/Q (2.21 Gb/s total before extra metadata), leaving more transport margin.

PCIe feasibility requires more than the bandwidth sum: verify reference/SSC handling, receiver detection, electrical idle, polarity, alignment, elastic buffering, ordered sets, reset/recovery, control latency, and the exact PHY/controller boundary. The physical host link is not pin-compatible PIPE. Provide a cycle-accurate FPGA adapter to a specified soft-controller interface and prove end-to-end enumeration and transfers. [Intel's PIPE specification](https://cdrdv2-public.intel.com/643108/643108_PIPE_Arch_Spec_Rev_7_1.pdf) and the [TI XIO1100](https://www.ti.com/product/XIO1100) establish the external-PHY partition as a precedent, not proof of this design. Some FPGA hard controllers cannot expose the required interface and are not supported merely because they advertise PCIe.

## MCU and generic-FPGA usability

SPI remains the repository's dedicated `svalbard_host_v1` Mode-0 control path, starting at or below 1 MHz. It works with the high-speed PLLs stopped and can configure resources, read status, transfer sample buffers, launch finite waveforms, and run autonomous PRBS/loopback measurements. A generic MCU cannot continuously process these interfaces at full rate. Capable MCUs may use slower parallel SDR with suitable capture/DMA hardware; that is optional, not a universal peripheral assumption.

No external FPGA is needed to preserve SPI recovery. Reset makes digital outputs high impedance and analog TX inactive, then the host explicitly arms clocks and engines. Minimal control uses hardware sequencers/registers rather than a mandatory on-chip CPU, OS, or external boot flash. Chip reset is separate from protocol-engine reset; FPGA-side PCIe PERST handling must not reset an independently running radio.

Ship an FPGA reference design with GPIO training, clock wrappers, FIFO interfaces, timing constraints, raw RF and serial demos, and the specific soft-PCIe adapter. Qualify at least two FPGA families with ordinary GPIO and one SPI MCU. Publish a compatibility matrix of bank voltage, clock pins, DDR capability, speed grade, measured link rate, and resource use. Slow hosts remain useful at slower functions; PCIe cannot become a lower-line-rate protocol just because GPIO timing fails.

## Floorplan, area and closure

Place wired and RF islands on opposite sides, host parallel pins adjacent to digital gearboxes/FIFOs, and the reference near quiet clock circuitry. Route clock/data groups compactly with nearby returns and controlled slew. RF and line pads get dedicated low-loading ESD; no generic analog crossbar or ordinary GPIO buffer in the GHz signal path.

| Core allocation, including local routing/keepouts | Budget (mm²) |
|---|---:|
| One full-duplex wired PHY | 2.0 |
| RF RX/TX and programmable analog baseband | 2.3 |
| I/Q converters and analog calibration | 1.3 |
| Synthesizers, timing, references | 1.3 |
| GPIO transport, generic digital helpers and control | 1.5 |
| FIFO/capture/playback/configuration memory | 0.8 |
| Top-level isolation, routing, decoupling and closure reserve | 3.72 |
| **Core ceiling** | **12.92** |

These are ceilings, not measured areas or promised buffer capacities. Determine memory depth from actual macro availability, host stalls, and protocol latency; do not assume a dense SRAM exists. Close the fast GPIO pad/return budget and representative analog layouts before expanding programmability. Area pressure is addressed by resource sharing and bounded buffering, preserving the full companion target.

Before fabrication, publish the 50-terminal bond map, actual placed area, rail/current/thermal budget, extracted die/package/board timing and RF models, host training/transport specification, and mode/resource conflict table. Demonstrate raw serial and RF transport with external FPGA logic in hardware-in-the-loop, then prove the exact PCIe and Ethernet adapters against peers. Exercise transport corruption, clock loss, flow-control failure, receiver errors, and every reset state. Carry all pre-silicon uncertainty into O1–O4 claims; one-slot fit, maximum GPIO rate, RF performance, and standards interoperability remain separate gates.

Host evidence: the [first FPGA screen](../../projects/programmable_transceiver_platform/spec/fpga-host-screen.md) rejects ECP5 as a documented full-rate LVCMOS host for the current top profile. Lower profiles remain candidates; full-rate host selection and electrical closure remain required.
