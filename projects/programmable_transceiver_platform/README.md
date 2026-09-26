# Svalbard programmable transceiver

**A single-chip, programmable wired-and-wireless transceiver platform.**

Give an FPGA the analog interfaces its ordinary GPIOs are missing: gigabit serial
links, digital-video lanes, and a configurable 2.4 GHz radio. Reuse the same chip
across network interfaces, FPGA peripherals, video bridges, wireless instruments,
and custom software-defined radios by changing its configuration and FPGA logic.

The ambition is one GF180MCU chip, one wafer.space slot, and 50 total terminals.
This is an active design: the capabilities below are targets, with partial
mathematical evidence, not demonstrated silicon or certified protocol support.

## What it could enable

| Application | Intended capabilities with suitable external logic | System boundary |
| --- | --- | --- |
| Gigabit networking | 1000BASE-X and SGMII interfaces | FPGA supplies coding, PCS/MAC and link management as needed; this is not a 1000BASE-T copper PHY |
| FPGA peripherals and storage | PCIe Gen1 x1 and SATA Gen1 | FPGA supplies endpoint/controller and protocol logic |
| USB peripherals and hosts | USB 2.0 High Speed, both device and host | FPGA supplies controller; host VBUS power switching/protection is external |
| Digital displays and video bridges | HDMI/DVI, initially 720p60 and 1080p60 at 8 bits/color; DisplayPort RBR, one lane | HDMI/DVI uses three identical lane chips plus an external clock interface; FPGA supplies encoding, control and lane coordination |
| Professional video | HD-SDI at 1.485 and 1.485/1.001 Gb/s | External coax driver/equalizer and FPGA framing/scrambling |
| Wi-Fi and SDR | 20 MHz 2.4 GHz Wi-Fi, including an 802.11ax/HE20 waveform target; custom I/Q radios | FPGA supplies modem, synchronization, FEC and MAC; current HE20 evidence is a limited BPSK fixture |
| Personal-area and IoT radio | Bluetooth LE, Bluetooth Classic BR/EDR, IEEE 802.15.4 for Zigbee/Thread-class systems, and 2.4 GHz LoRa | External modem/protocol implementation; LoRa here does not imply sub-GHz coverage |
| Custom links and instruments | Proprietary GFSK, intermediate serial rates, selectable RF bandwidth/gain/sample rate, capture and waveform playback | Use generic resources within their eventual characterized operating envelope |

Fractional video clocks such as 74.25/1.001 and 148.5/1.001 MHz are part of the
numeric timing design. Narrower RF settings aim to serve low-rate radios without
forcing every application through a wide Wi-Fi channel. Lower-frequency RF and
other bands through external frequency conversion are stretch goals.

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
Narrow temperature and supply ranges are acceptable design targets.

The [normative architecture](spec/block-diagram.md) selects both autonomous and
external timing paths, configurable narrow/wide RF filtering, and FPGA-owned
resampling, TX interpolation and bulk storage. External LO operation reuses
`REF_IN` and still needs a qualified RF input branch. Dedicated wired RX clock
recovery remains necessary. The main diagram shows these selected boundaries;
detailed circuit candidates are linked separately.

## Where the design stands

The fast whole-chip behavioral model exercises generic configurations, finite
host queues, RF conversion/filtering, wired recovery and selected lifecycle
behavior. Some target configurations pass their conditional screens; others
still fail. **Full mathematical verification, the complete transistor schematic,
and layout are unfinished.** Passing regression tests also verify expected
failures; they do not mean every target works.

The reference-chip investigation has been consolidated into
[explicit assumptions and uncertainty ranges](spec/risk-priorities.md#adopted-assumptions-and-uncertainty-ranges).
Active work now targets connected clock quality, complete RF conversion and
pad/package/power coexistence; further reference-chip simulation is paused.

For current capability status and unresolved failures, use the
[current status table](spec/risk-priorities.md#current-status). Historical
measurements and expected-rejection tests are kept separately in the closure
inventory; their number does not measure chip completeness.

The development order is a connected mathematical model, then a complete
transistor/passive schematic with simulation, then layout and extraction using
the same requirements. Device speed/noise, RF linearity, supply coupling and
package behavior remain major physical unknowns.

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
| [Consolidation audit](docs/consolidation.md) | Documentation ownership and recovery of historical evidence |

From the repository root, run the active behavioral regression:

```sh
make transceiver-behavioral
```

See the model guide for optional checks. Model code lives in `system_model`,
checks in `verification`, incomplete circuits in `analog`, digital implementation
in `rtl`, `sim` and `integration`, and reports in `evidence`.
