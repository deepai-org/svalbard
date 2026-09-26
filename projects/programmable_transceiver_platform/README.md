# Svalbard programmable transceiver

**A single-chip, programmable wired-and-wireless transceiver platform.**

Give an FPGA the analog interfaces its ordinary GPIOs are missing: gigabit serial
links, digital-video lanes, and a configurable 2.4 GHz radio. Reuse the same chip
across network interfaces, FPGA peripherals, video bridges, wireless instruments,
and custom software-defined radios by changing its configuration and FPGA logic.

The ambition is one GF180MCU chip in one wafer.space slot, using the provider’s
standard chip-on-board packaging and compatible pad ring. The selected physical
allocation retains 74 provider sites: 36 functional signals, 18 fixed power/return
sites and 20 spare signals. This supersedes the earlier approximate 50-terminal
drawing; electrical qualification of the assembly remains open.
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

The [selected baseline and decision rules](spec/block-diagram.md#remaining-architecture-choices-closed-for-implementation)
commit to one implementation. Remaining physical uncertainties are verification
obligations, not an open menu of chip architectures.

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
selected requirements for the next model revision, not claims that existing
simulations already implement or pass them all.

## Where the design stands

Architecture choices are [selected for implementation](spec/block-diagram.md#remaining-architecture-choices-closed-for-implementation):
provider-compatible common returns, external timing/regulation as the primary
qualification route, autonomous timing retained, and LO-derived RF sampling
with FPGA resampling. All application targets remain in scope. Remaining work
must establish one consistent operating envelope, rather than keep alternative
architectures open or infer completeness from passing test counts.

The fast whole-chip behavioral model exercises generic configurations, finite
host queues, RF conversion/filtering, wired recovery and selected lifecycle
behavior. Some target configurations pass their conditional screens; others
still fail. **Full mathematical verification, the complete transistor schematic,
and layout are unfinished.** Passing regression tests also verify expected
failures; they do not mean every target works.

Run `python3 verification/baseline_envelope.py` from this directory for the
selected baseline under shared power, host switching, package impedance and
delivered timing. It joins the complete mode-current allocations to causal wired
reception, wideband RF and real LE 1M packet exchange, using the selected native
10-bit converters and filters. The [joined results](spec/power-partition.md#first-selected-baseline-electrical-result)
retain failures: a package probe leaves the wired voltage-validity interval,
weak wideband reception fails under a strong blocker, and RF emissions worsen
despite clean decoding. Fixed latency calibration helps the narrowband reply,
but air timing and physical analog performance remain unqualified. A
[closed-loop converter study](spec/power-partition.md#closed-loop-converter-and-reference-load-requirements)
now connects SAR decisions, reference charge and shared-supply feedback. It
checks converter precision separately from packet decoding and selects unequal
bit timing within the existing conversion budget. The detailed converter now
joins live packet AGC, conversion availability and reference-load feedback.
Active control/timestamps use H2D clock divided by four, avoiding an unowned
independent clock source.
The corrected shared clock/input model now reaches causal converter feedback,
real narrowband packets, bounded TX wake and wired recovery/transmit tests.
It retains failures: the current package target passes five of six stressed
narrowband exchanges, while short wired TX cases can have zero bit errors yet
lose receiver readiness. A stronger external clock source is a promising
mitigation, with additional return-current and input-voltage obligations.
The report's `current_target_observations` separates numerical convergence,
packet outcomes and receiver readiness; it is not a completeness score.
The [wired recovery join](spec/power-partition.md#wired-equalization-host-delivery-and-recovery)
now includes pad/channel loading, CTLE, finite host transport and clock-loss
restart. Equalization prevents the selected-network status-queue failure; the
higher-inductance package probe remains rejected. The common package target is
now 0.25 nH return inductance after comparison across every existing joined
bench; physical assembly feasibility remains unproven. The original 0.5 nH
and adverse package cases remain explicit controls.
`verification/robustness_envelope.py` retains the earlier fixtures and mitigation
comparisons; their older current/converter/filter assumptions do not qualify the
selected baseline.

The principal unresolved analog issue is now **combined performance**: clock
noise that looks acceptable in a clean signal test can fail under a blocker,
and a low-noise receiver also needs sufficient linearity before filtering.
Wideband RF also has a converter/headroom gap when unproven close-offset
external-filter rejection is removed; narrowband packet success does not close it.
Local supply filtering and RF filter retuning help selected cases, but no
complete physical operating point is yet demonstrated. The
[current system decisions](spec/risk-priorities.md#current-system-decisions)
separate those useful mitigations from remaining failures and costs.

The immediate priority is [big-picture architecture closure](spec/risk-priorities.md#big-picture-closure-priorities):
reconcile physical/resource budgets, establish one usable analog operating
envelope, close representative full lifecycles, and assess each target against
explicit acceptance criteria. More passing local tests do not replace these
four decisions. Schematic work remains deferred.

The reference-chip investigation has been consolidated into
[explicit assumptions and uncertainty ranges](spec/risk-priorities.md#adopted-assumptions-and-uncertainty-ranges).
Active work now targets connected clock quality, complete RF conversion and
pad/package/power coexistence; further reference-chip simulation is paused.

The [keep-or-change decision](spec/risk-priorities.md#keep-or-change-decision-change-the-delivered-clock-architecture)
keeps the full chip and selects a differential external clock input plus a lower
clock supply-sensitivity requirement. It includes pin/current/area reservations.
Migration of the executable baseline and diagram is the next task; the
mathematical model and physical feasibility remain incomplete.

For the [whole-architecture assessment and keep/change decisions](spec/risk-priorities.md#architecture-assessment-one-implementation-several-ways-to-succeed),
start with the risk review. For current capability status and unresolved failures, use the
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
