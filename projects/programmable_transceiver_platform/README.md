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
| Gigabit networking | 1000BASE-X and SGMII interfaces; 2500BASE-X and one XAUI lane at 3.125 GBd | FPGA supplies coding, PCS/MAC and link management as needed; this is not a 1000BASE-T copper PHY |
| FPGA peripherals and storage | PCIe Gen1 x1, SATA Gen1 and SATA Gen2 (3.0 Gb/s) | FPGA supplies endpoint/controller and protocol logic |
| USB peripherals and hosts | USB 2.0 High Speed, both device and host | FPGA supplies controller; host VBUS power switching/protection is external |
| Digital displays and video bridges | HDMI/DVI, initially 720p60 and 1080p60 at 8 bits/color; DisplayPort RBR and HBR (2.7 Gb/s), one lane | HDMI/DVI uses three identical lane chips plus an external clock interface; FPGA supplies encoding, control and lane coordination |
| Professional video | HD-SDI at 1.485 and 1.485/1.001 Gb/s | External coax driver/equalizer and FPGA framing/scrambling |
| Wi-Fi and SDR | 20 MHz 2.4 GHz Wi-Fi, including an 802.11ax/HE20 waveform target; custom I/Q radios | FPGA supplies modem, synchronization, FEC and MAC; MCS0–7 interoperability target; coded 64-QAM and ideal-MAC lifecycle evidence, not router interoperability |
| Personal-area and IoT radio | Bluetooth LE (1M, 2M, LE Coded S=2/S=8) including Bluetooth 6.0 Channel Sounding (phase-based ranging and RTT), Bluetooth Classic BR/EDR, IEEE 802.15.4 with Thread, Zigbee and Matter profiles, and 2.4 GHz LoRa | External modem/protocol implementation; LoRa here does not imply sub-GHz coverage |
| Custom links and instruments | Proprietary GFSK, continuous serial line rates 0.48–3.24 Gb/s (lower by oversampling), selectable RF bandwidth/gain/sample rate, capture and waveform playback | Use generic resources within their eventual characterized operating envelope |

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
and the submission gates and their current gaps are in [`spec/tapeout-plan.md`](spec/tapeout-plan.md#before-submission).

| Freeze stage | State |
| --- | --- |
| Control and digital | Current RTL passes functional checks and reaches CTS; target timing and current-source physical signoff remain open |
| Pads | All five custom families pass safe and clean |
| Blocks | All except the wired CDR have clean extracted layouts; performance shortfalls are recorded per block |
| Top-level assembly | Core-bias placement and pad-level bring-up fixtures exist; full-chip floorplan, binding and routing remain open |
| Submission | Open |

| Directory | Blocks |
| --- | --- |
| [`analog/core_support`](analog/core_support/README.md) | POR, bandgap, biasgen, per-island bias distribution |
| [`analog/island_support`](analog/island_support/README.md) | Island power switches, isolation clamps, analog test bus |
| [`analog/characterization`](analog/characterization/README.md) | Device replicas and resistor/MIM matching pairs on the ATB; LEF/evidence check of the VCO replica and ESD_TEST |
| [`analog/pads`](analog/pads/README.md) | Stress-safe pad protection, pad families, debug-site protection, USB attachment |
| [`analog/timing`](analog/timing/README.md) | `pll_ring`, passive/internal LO path, clock mux, receivers, dividers, clock observation, oscillators |
| [`analog/rf_rx`](analog/rf_rx/README.md) | LNA, mixers, shared baseband filter, BB tap buffer |
| [`analog/rf_tx`](analog/rf_tx/README.md) | Upmixers, summer, RF driver |
| [`analog/converters`](analog/converters/README.md) | SAR ADCs, DACs, reference buffer |
| [`analog/wired_rx`](analog/wired_rx/README.md) | Termination, level, select, CTLE, slicer, detect, CDR |
| [`analog/wired_tx`](analog/wired_tx/README.md) | Serializer, TMDS configuration, USB HS bias DAC |

All 17 intended interfaces remain in the [closure inventory](spec/mathematical-closure.json)
with unresolved capability verdicts. Interfaces added 2026-11-10 (SATA Gen2, DP HBR, 2500BASE-X/XAUI,
LE Coded, Channel Sounding, Thread/Zigbee/Matter profiles, continuous line-rate coverage) are specified in
[interface requirements](spec/interface-requirements.md) §1.9–1.13 and §2.1 and traced in
[performance requirements](spec/performance-requirements.md); they are not yet in the closure inventory. These are pre-silicon results: no protocol
compliance, interoperability or silicon performance is claimed. Use the
[model guide](system_model/architecture_fast/README.md) for behavioral checks.

## Core digital implementation

`rtl/pt_digital_macro.sv` contains SPI/register control, paired dense transport,
FIFOs, capture/playback memory, pattern generation/checking, calibration,
clock supervision, frequency counters and DDR/SDR host-link logic. Provider
pad cells are bound separately by `integration/pt_provider_io.sv`.

The selected clocks are 312.5 MHz at the ten-bit host boundary, 156.25 MHz in
the paired engines and 125 MHz at the twenty-bit wired boundary. Functional
checks pass 2.5 Gb/s wired and 40 MS/s I/Q service. The physical implementation
fits an intermediate 1580 × 1580 µm placement and passes CTS; setup timing and
current-source physical signoff remain open. The published
[digital hardening evidence](evidence/digital-hardening-evidence.json) records
its own source snapshot and must not be transferred to changed RTL.

The [tapeout plan](spec/tapeout-plan.md#before-submission) lists the remaining gates. Constraints are in
[integration/pt_digital_macro.sdc](integration/pt_digital_macro.sdc).

```sh
make transceiver-digital-rtl-checks
make transceiver-digital-hardening
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
| [Tapeout plan](spec/tapeout-plan.md) | Operating envelope, four tapeout tests, must-work core, fallbacks, debug pads, submission gates and current gap |
| [Tapeout readiness](spec/tapeout-readiness.json) | Per-block test states and evidence |
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
