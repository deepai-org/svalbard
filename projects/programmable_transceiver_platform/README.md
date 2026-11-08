# Svalbard programmable transceiver

**A single-chip, programmable wired-and-wireless transceiver platform.**

Give an FPGA the analog interfaces its ordinary GPIOs are missing: gigabit serial
links, digital-video lanes, and a configurable 2.4 GHz radio. Reuse the same chip
across network interfaces, FPGA peripherals, video bridges, wireless instruments,
and custom software-defined radios by changing its configuration and FPGA logic.

The ambition is one GF180MCU chip in one wafer.space slot, using the provider’s
standard chip-on-board packaging and compatible pad ring. The selected physical
allocation retains 74 provider sites: 37 functional signals, 18 fixed power/return
sites and 19 spare signals. Electrical qualification of the assembly remains open.
This is an active design: the capabilities below are targets, with partial
mathematical evidence, not demonstrated silicon or certified protocol support.

The [block and connection inventory](spec/analog-architecture.json) and
[block diagram](spec/block-diagram.md) specify the selected implementation.
[Implementation ownership](spec/block-diagram.md#silicon-fpga-and-board-allocation)
puts calibration computation and bulk state on the FPGA, and RF interface
passives on the board; sensitive feedback and sampling stay local.
The [current status and risks](spec/risk-priorities.md) distinguish demonstrated
model behavior from assumptions and open implementation gates. Complete
mathematical verification, transistor schematics and extracted layout remain
unfinished.

## What it could enable

| Application | Intended capabilities with suitable external logic | System boundary |
| --- | --- | --- |
| Gigabit networking | 1000BASE-X and SGMII interfaces | FPGA supplies coding, PCS/MAC and link management as needed; this is not a 1000BASE-T copper PHY |
| FPGA peripherals and storage | PCIe Gen1 x1 and SATA Gen1 | FPGA supplies endpoint/controller and protocol logic |
| USB peripherals and hosts | USB 2.0 High Speed, both device and host | FPGA supplies controller; host VBUS power switching/protection is external |
| Digital displays and video bridges | HDMI/DVI, initially 720p60 and 1080p60 at 8 bits/color; DisplayPort RBR, one lane | HDMI/DVI uses three identical lane chips plus an external clock interface; FPGA supplies encoding, control and lane coordination |
| Professional video | HD-SDI at 1.485 and 1.485/1.001 Gb/s | External coax driver/equalizer and FPGA framing/scrambling |
| Wi-Fi and SDR | 20 MHz 2.4 GHz Wi-Fi, including an 802.11ax/HE20 waveform target; custom I/Q radios | FPGA supplies modem, synchronization, FEC and MAC; MCS0–7 interoperability target; coded 64-QAM and ideal-MAC lifecycle evidence, not router interoperability |
| Personal-area and IoT radio | Bluetooth LE, Bluetooth Classic BR/EDR, IEEE 802.15.4 for Zigbee/Thread-class systems, and 2.4 GHz LoRa | External modem/protocol implementation; LoRa here does not imply sub-GHz coverage |
| Custom links and instruments | Proprietary GFSK, intermediate serial rates, selectable RF bandwidth/gain/sample rate, capture and waveform playback | Use generic resources within their eventual characterized operating envelope |

Fractional video clocks such as 74.25/1.001 and 148.5/1.001 MHz are part of the
numeric timing design. Narrower RF settings aim to serve low-rate radios without
forcing every application through a wide Wi-Fi channel. Lower-frequency RF and
other bands through external frequency conversion are stretch goals.

The [selected baseline and decision rules](spec/block-diagram.md#remaining-architecture-choices-closed-for-implementation)
define one current design. The immediate priority is to improve that shared
design until it meets the behavioral requirements. Physical realizability and
fabrication compatibility are subsequent implementation checks; their unresolved
costs remain recorded and are not treated as demonstrated fit.

Current modeling milestone: [one coherent, uncertainty-aware whole-chip model](spec/feasibility-gates.md#current-mathematical-model-milestone),
with explicit capability verdicts and circuit requirements. The model is partial;
individual passing fixtures do not establish whole-chip or silicon feasibility.

## One platform, configurable building blocks

The chip exposes clock, pad, direction, gain, filter, converter and transport
settings—**no on-chip protocol profiles**. Protocol names describe external FPGA
recipes. Dedicated RF and wired frontends share infrastructure where practical.
RF and wired payloads are **mutually exclusive on each die**; both remain part
of the full first-chip design.

A suitable FPGA supplies high-throughput processing and protocol logic, including
CRC/FEC, MACs and endpoints. An MCU can configure the chip and use lower-rate or
buffered functions; GPIO bandwidth determines achievable throughput. Board-level
matching, protection, reference-clock and interface circuitry remain necessary.
**Many external SMD passives are explicitly acceptable.** Matching, filtering,
decoupling and suitable timing networks may live on the board to simplify the
chip; low external component count is not a goal. See the
[external passive allowance](../../docs/roadmap/programmable-transceiver-pin-plan.md#external-passive-component-allowance)
for the pin-budget and modeling boundary.
External oscillators, clock modules and RF LO sources are also allowed operating
options. Autonomous on-chip synthesis need not serve every configuration; input
bandwidth, clock conditioning and terminal allocation must support the chosen
source. See the [clock allowance](../../docs/roadmap/programmable-transceiver-pin-plan.md#external-oscillator-and-clock-allowance).
**Operating envelope: the chip is designed to work only at 27 °C ±5 °C junction
and a 3.3 V ±1% board supply** (3.15–3.35 V at the die). Outside that window it
must stay safe but need not function. See the
[tapeout plan](spec/tapeout-plan.md#operating-envelope-user-decision-narrow-range-accepted).

The [normative architecture](spec/block-diagram.md) defines the blocks and
their connectivity. The first die is a **risk-accepted, full-scope tapeout**:
every block must be safe when off or broken, DRC/LVS clean with an extracted
simulation of its basic function, observable from the bench, and backed by a
second route. The [tapeout plan](spec/tapeout-plan.md) defines these four
tests, the must-work core, the fallback routes, the 19 debug pads and the
freeze order. Key implementation choices:

- **RF LO baseline:** passive external I/Q LO on `REF_IN`/`AUX_CLK`, AC-coupled
  straight onto the mixer gates.
- **Clocks:** one compact ring-PLL design for every PLL. Wired lanes run the
  ring at 480–810 MHz with 1, 2 or 4 bits per ring cycle.
- **Shared resources:** one I/Q baseband filter bank for RX and TX, USB on the
  wired receive path, and TMDS as a wired TX setting
  ([decisions](spec/consolidation-pass.md)).
- **Power:** five default-off island power switches behind one external supply,
  with per-island bias trunks and an analog test bus.

## Where the design stands

Per-block state against the four tests is in
[`spec/tapeout-readiness.json`](spec/tapeout-readiness.json). Run
`make transceiver-tapeout-readiness` for counts. Open issues and priorities are
in the [current issue register](spec/risk-priorities.md#open-issue-register).
Board obligations are in [`spec/board-requirements.md`](spec/board-requirements.md),
and the recommended next steps are in [`spec/path-to-tapeout.md`](spec/path-to-tapeout.md).

| Freeze stage | State |
| --- | --- |
| Control and digital | Hardened and DRC/LVS clean; timing not closed at target clocks (below) |
| Pads | All five custom families pass safe and clean |
| Blocks | All except the wired CDR have clean extracted layouts; performance shortfalls are recorded per block |
| Top-level assembly, submission | Not started |

| Directory | Blocks |
| --- | --- |
| [`analog/core_support`](analog/core_support/README.md) | POR, bandgap, biasgen, per-island bias distribution |
| [`analog/island_support`](analog/island_support/README.md) | Island power switches, isolation clamps, analog test bus |
| [`analog/pads`](analog/pads/README.md) | Stress-safe pad protection, pad families, debug-site protection, USB attachment |
| [`analog/timing`](analog/timing/README.md) | `pll_ring`, passive/internal LO path, clock mux, receivers, dividers, clock observation, oscillators |
| [`analog/rf_rx`](analog/rf_rx/README.md) | LNA, mixers, shared baseband filter, BB tap buffer |
| [`analog/rf_tx`](analog/rf_tx/README.md) | Upmixers, summer, RF driver |
| [`analog/converters`](analog/converters/README.md) | SAR ADCs, DACs, reference buffer |
| [`analog/wired_rx`](analog/wired_rx/README.md) | Termination, level, select, CTLE, slicer, detect, CDR |
| [`analog/wired_tx`](analog/wired_tx/README.md) | Serializer, TMDS configuration, USB HS bias DAC |

All 17 intended interfaces remain in the [closure inventory](spec/mathematical-closure.json)
with unresolved capability verdicts. These are pre-silicon results: no protocol
compliance, interoperability or silicon performance is claimed. Use the
[model guide](system_model/architecture_fast/README.md) for behavioral checks.

## Hardened core digital macro (freeze stage 1)

`rtl/pt_digital_macro.sv` is the control-and-digital block hardened with LibreLane
3.0.5 on gf180mcu_fd_sc_mcu7t5v0 (3.3 V libraries): register file and SPI, transport
and FIFOs, capture/playback memory, pattern generator/checker, calibrator,
`pt_clocktree_slow`, two frequency counters (`pt_freq_count`) and the clocked
half of the host link (`pt_host_link`: DDR/SDR capture, launch, forwarded clock).
Pad cells stay provider `gf180mcu_fd_io` cells (`integration/pt_chip.sv`,
`pt_host_physical`). The wired boundary is 20-bit double words.

Results, with the exact numbers, live in
[`evidence/digital-hardening-evidence.json`](evidence/digital-hardening-evidence.json);
constraints are in [`integration/pt_digital_macro.sdc`](integration/pt_digital_macro.sdc).
Summary of what that run shows:

- **Physical:** 1800 × 1800 µm macro (3.24 mm², above the 2.5 mm² digital + memory
  allocation), 71.5k standard cells, 61 % utilization. The capture/playback memory and
  every FIFO are flip-flop arrays; no SRAM macro is used, because their dual-clock reads
  do not fit single-port SRAMs. Routing uses Metal2–Metal5 with a Metal4-only power grid.
  A Metal1–Metal4 variant, which leaves Metal5 free for MIM decap, also routes but has 2
  antenna violations and worse timing.
- **Signoff:** Magic DRC, KLayout DRC and Netgen LVS all report 0 errors. Antenna
  checks (OpenROAD and KLayout) report 0. The GDS re-exported with the analog image's
  Magic 8.3.678 passes KLayout DRC with 0 violations and XORs to 0 against the LibreLane
  GDS. Hold timing is met at every corner.
- **Timing is not closed at the specification clocks.** The table gives fmax at the
  nominal corner (tt 25 °C 3.3 V) and at the worst characterized corner, which is
  ss 125 °C 3.0 V and lies outside the operating envelope; no Liberty exists inside the
  envelope.

  | Clock | Target | Nominal (tt) | Worst corner |
  | --- | --- | --- | --- |
  | Host word | 312.5 MHz | ≈65 MHz | ≈30 MHz |
  | Wired double-word | 125 MHz | ≈54 MHz | ≈25 MHz |
  | SPI SCLK | 20 MHz | ≈18.6 MHz | ≈12.7 MHz |
  | RF sample | 50 MHz | ≈41 MHz | ≈21 MHz |

  SPI still runs at its ≤ 1 MHz start rate and the 10 MHz bench rate at every corner.
- **Host link:** the provider pads alone would allow about 150–180 MHz DDR, but the
  transport logic limits the DDR pin clock to about 33 MHz (nominal) and 15 MHz (worst
  corner), so 156.25 MHz DDR is not reachable. Use the SDR or reduced-rate host-link
  fallback.
- **Gate-level simulation (post-route netlist):** 3969 SPI reads and output snapshots
  match the RTL record by record and match the register model. Every output is at its
  safe value while RESET_N or POR is asserted; island_on is 0, so every iso_clamp
  isolates. Status, reset cause and the frequency counter read back over SPI. With D2H
  looped back to H2D, the link locks in DDR, SDR and reduced-rate SDR modes.

Reproduce from the repository root (about 4 h on a loaded host; stages can run alone):

```sh
make transceiver-digital-hardening
make transceiver-digital-hardening DIGITAL_HARDENING_STAGES="sta gls report"
```

## Explore and run

![Intended full-chip block diagram](docs/diagrams/transceiver-block-diagram.svg)

| Document | Owns |
| --- | --- |
| [Architecture and diagrams](spec/block-diagram.md) | Intended blocks and connectivity |
| [Interface and physical plan](../../docs/roadmap/programmable-transceiver-pin-plan.md) | Pin allocation, interface requirements and target scope |
| [Model guide](system_model/architecture_fast/README.md) | Active commands, model coverage and limitations |
| [Risk priorities](spec/risk-priorities.md) | Remaining work in priority order |
| [Closure inventory](spec/mathematical-closure.json) | Formal completion gates and evidence scope |
| [Configuration contract](spec/contract.json) | Machine-readable settings and external test recipes |
| [Operating policy](spec/exclusive-engine-policy.md) | Resource sharing, exclusivity and band stretch goals |
| [Analog workflow](spec/analog-design-workflow.md) | Six-family primitive library, schematic and extraction workflow |
| [Macro contract](integration/macro-contract.md) | Digital/analog boundary and RTL obligations |
| [Consolidation audit](docs/consolidation.md) | Design and documentation ownership |
| [Tapeout plan](spec/tapeout-plan.md) | Four tapeout tests, must-work core, fallbacks, debug pads, freeze order |
| [Tapeout readiness](spec/tapeout-readiness.json) | Per-block test states and evidence |
| [Path to tapeout](spec/path-to-tapeout.md) | Recommended next steps to submission |
| [Shared-resource decisions](spec/consolidation-pass.md) | Merged blocks and clocking architecture |
| [Register map](spec/register-map.md) | Generated SPI register map |
| [Board requirements](spec/board-requirements.md) | Board and FPGA obligations |

From the repository root, run the active behavioral regression:

```sh
make transceiver-behavioral
```

See the model guide for optional checks. Model code lives in `system_model`,
checks in `verification`, block circuits and layouts in `analog`, digital implementation
in `rtl`, `sim` and `integration`, and reports in `evidence`.
