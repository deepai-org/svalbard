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
Narrow temperature and supply ranges are acceptable design targets.

The [normative architecture](spec/block-diagram.md) selects both autonomous and
external timing paths, configurable narrow/wide RF filtering, and FPGA-owned
resampling, TX interpolation and bulk storage. External LO operation reuses
`REF_IN` and still needs a qualified RF input branch. Dedicated wired RX clock
recovery remains necessary. The main diagram shows these selected boundaries;
detailed circuit candidates are linked separately.

The [provisional first-chip baseline](spec/block-diagram.md#provisional-first-chip-baseline)
now makes the implementation choices: external timing first for qualification,
autonomous paths retained, high-impedance clock input, slower RF return clock,
paired SAR/DAC conversion and a tunable finite-zero channel filter. The
[implementation allocations](spec/power-partition.md#provisional-implementation-allocation)
assign rough area and complete-mode current budgets; actual area remains a
layout result. The [capability review](spec/feasibility-gates.md#capability-wide-evidence-gaps-and-next-decisions)
records each target's required circuitry and distinct open proof. These are
current design requirements, not claims that existing
simulations already implement or pass them all.

## Where the design stands

The shared behavioral model connects clock delivery, RF conversion/filtering,
wired recovery, finite FPGA queues and selected startup/fault/recovery paths.
Intended-chip tests use one configured design; simplified numerical examples
and deliberately adverse fixtures identify their exceptions. Passing tests do
not establish full capability or silicon performance.

The [current issue register](spec/risk-priorities.md#open-issue-register) owns
unresolved failures. The main implementation risks are protection compatible
with the attached cores, local safe-state controls, real RF/reference receivers,
and the coupled package/supply/timing budget. The [pad implementation](analog/pads/README.md)
contains generated circuits and partial layouts but is not production-ready.

All 17 intended interfaces remain in the [closure inventory](spec/mathematical-closure.json).
Each still needs its complete electrical, signal-quality, timing, host-service
and lifecycle evidence. Wi-Fi diagnostic success does not establish router
interoperability; finite wired trajectories do not establish BER or compliance.

The [next priorities](spec/risk-priorities.md#big-picture-closure-priorities)
are coherent analog interfaces, one useful coupled operating envelope and full
representative lifecycles. External clocks, passives and a narrow accepted
operating range are allowed. Physical fit and fabrication qualification remain
explicit obligations.

Use the [model guide](system_model/architecture_fast/README.md) for scoped
checks and the [analog workflow](spec/analog-design-workflow.md) for the
mathematical-model → complete schematic → layout/extraction sequence. Exact
source/configuration provenance is required for every result.

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

From the repository root, run the active behavioral regression:

```sh
make transceiver-behavioral
```

See the model guide for optional checks. Model code lives in `system_model`,
checks in `verification`, incomplete circuits in `analog`, digital implementation
in `rtl`, `sim` and `integration`, and reports in `evidence`.
