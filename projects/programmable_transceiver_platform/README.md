# Svalbard programmable transceiver

Two GF180MCU mixed-signal chips that give an FPGA the analog interfaces its ordinary GPIOs lack: **`pt_rf`**, a
2.4 GHz I/Q radio, and **`pt_wired`**, a multi-rate wired serial lane with USB 2.0. Each chip is self-sufficient (its
own power-up, reset, SPI, host link, bias and debug) and sits on its own wafer.space slot; both are built from one
block library and one RTL source. The chips have no protocol logic and no protocol profiles: they expose clocks,
pads, gain, filters, converters and a raw transport, and the FPGA supplies coding, framing, MAC and modem. An SPI
port configures each chip; a ten-bit parallel link per direction carries payload.

This is a pre-silicon design. Nothing here is demonstrated silicon or protocol compliance.

## What the chip must do

| Use | Target interfaces | Stays in the FPGA / on the board |
| --- | --- | --- |
| Serial links (`pt_wired`) | PCIe Gen1 x1, 1000BASE-X / SGMII, 2500BASE-X and one XAUI lane (3.125 GBd), SATA Gen1 and Gen2, 100BASE-TX raw path | Coding, PCS/MAC, link management; magnetics for twisted pair |
| Video (`pt_wired`) | DisplayPort RBR and HBR (one lane), HDMI/DVI TMDS at 720p and 1080p (three chips, one per lane), HD-SDI | Encoding, lane alignment, sidebands; coax driver/equaliser for SDI |
| USB (`pt_wired`) | USB 2.0 HS / FS / LS, device and host | Packets, CRC, bit stuffing, NRZI; VBUS switching |
| Radio, 2.4–2.5 GHz (`pt_rf`) | 20 MHz Wi-Fi (HE20 waveform target), Bluetooth LE (1M, 2M, Coded, Channel Sounding), Bluetooth BR/EDR, IEEE 802.15.4, 2.4 GHz LoRa, custom I/Q | Modem, synchronisation, FEC, MAC; balun, band filter, antenna switch |
| Generic (both) | Any continuous line rate 0.48–3.24 Gb/s (lower by oversampling), capture and playback memory, pattern generator and checker | Everything protocol-specific |

Requirements with their IDs are in [`spec/interface-requirements.md`](spec/interface-requirements.md) and
[`spec/performance-requirements.md`](spec/performance-requirements.md) (each row tagged rf, wired or both).

## Scope and boundary conditions

- **Full scope across the pair.** Every interface above, including the 2.7–3.24 Gb/s wired rates, is on one of the
  two chips. Off chip are only passives, the FPGA and a fallback LNA (in addition to the on-chip LNA). A target may
  be missed only where GF180MCU makes it physically impossible.
- **Which block is on which chip:** [`spec/chips.json`](spec/chips.json) (islands, register fields) and
  `scratch/reviews/split/assignment.md` (every instance, pad, field, module and requirement row). Shared
  infrastructure (POR, SPI, host link, digital macro, core bias, island switches, ATB, reference input, TX ring) is
  instanced on both chips from the same source. No mode needs both chips. `pt_rf` is TDD with warm TX and RX; `pt_wired`
  is full duplex. Lower RF bands, on chip or through board frequency conversion, are stretch goals with no evidence yet.
- **No dead chip.** Each die must power up safely, answer SPI and be observable even if every ambitious block
  fails: default-off supply islands, isolation clamps, two analog test buses, clock and status observation pads,
  and fallback routes (external LO, external LNA, forwarded clocks, bypasses) for the risky blocks.
- **Package:** the wafer.space chip-on-board only, one per chip. Fixed die 3.932 × 5.122 mm, one fixed 74-wire bond
  layout (no custom, double or down-bonds; the free signal sites of each chip carry extra supply / ground bonds), 14 × 16 mm board with a 70-pin mezzanine connector. The nearest signal passive is
  on the carrier board, 5–6 mm of trace plus the connector away.
- **Operating window:** junction 22–32 °C, die supply 3.15–3.35 V, all process corners. The board sets each die's
  supply at bring-up from its measured speed, up to a 3.50 V setpoint for slow dies. Safety (no damage, latch-up or
  lock-up) holds over 0–3.63 V and 0–85 °C.

## Architecture in brief

- **RF (`pt_rf`):** on-chip LNA, I/Q passive mixers, one shared I/Q baseband filter bank for receive and transmit, two SAR
  ADCs, two DACs, upmixers, summer and RF driver. The LO is an on-chip quadrature LC VCO with an integer-N loop; an
  external quadrature LO on the `REF_IN` / `AUX_CLK` pad pairs is the fallback.
- **Wired (`pt_wired`):** programmable termination, CTLE, slicer, capture and CDR on receive; serializer and pad
  driver on transmit, with TMDS as a configuration of the same output stage. USB shares the wired receive path and
  has its own pad pair and line driver. A forwarded wire clock enters on the `AUX_CLK` pad pair.
- **Clocks (both):** two ring PLLs. The TX ring makes the host word clock and (on `pt_rf`) the converter clock
  (host_follow); the CDR ring recovers the wire clock on `pt_wired` and is the second host-clock route on `pt_rf`.
- **Digital:** one standard-cell macro per chip from one RTL (`rtl/pt_digital_macro.sv`, parameter `PT_CHIP`: 1 = `pt_rf`,
  2 = `pt_wired`; hardening configurations `verification/digital_hardening/{rf,wired}/`) with SPI, the generated register file, the
  control decode for every analog pin, the framed host transport, capture/playback memory, pattern
  generator/checker, frequency counters, USB FS/LS line logic and the supply/clock monitor.
- **Infrastructure:** POR with a strap-selected bypass, bandgap and bias distribution, supply islands behind
  default-off switches (`pt_rf`: rf, pll, conv, debug groups; `pt_wired`: wired, pll, debug), custom pad families
  and provider digital pads.

[`spec/block-diagram.md`](spec/block-diagram.md) describes the chains, instances, clocks, islands, pads and modes.

## Current status

- The control plane exists in RTL: the macro presents one decoded port per analog control pin group, and every
  mode family closes in a chip-level simulation of each chip against its stub analog top.
- Nothing is hardened, routed or signed off at chip level. The digital macro does not yet meet setup timing.
- Several blocks are not built or not closed (the chip-top regression counts them as demand and staged
  instances); block state is in each `analog/<family>/README.md`.
- Open risks: [`spec/risk-register.md`](spec/risk-register.md). Open chip-top items:
  [`integration/chips/decisions.md`](integration/chips/decisions.md). Work state and standing rules:
  `scratch/reviews/SESSION-STATE.md` and `scratch/reviews/MANDATE.md`.

## Source of truth

| Subject | File |
| --- | --- |
| Chip connectivity (every instance, pin, pad, island) | [`integration/chips/rf/chip.conn`](integration/chips/rf/chip.conn) and [`integration/chips/wired/chip.conn`](integration/chips/wired/chip.conn), both including [`common.conn`](integration/chips/common.conn); checked by `integration/chips/check_top.py <chip>`; masters in `masters.txt`, macro control ports in `ctl_ports.txt` |
| Bond map of each chip | `integration/chips/<chip>/bond_map.txt` (all 74 sites) |
| Chip-level structural RTL | `integration/chips/<chip>/generated/pt_chip.sv`, generated from the conn by `integration/gen_pt_chip.py` |
| Registers | One address map, per-chip view (fields of the other chip not stored, read 0; `status.chip.id`). `rtl/gen/gen_regfile.py` generates `rtl/pt_regfile.sv`, the `pt_regmap_*` headers and [`spec/register-map.md`](spec/register-map.md) / `.json` from `spec/analog-architecture.json` and `spec/debug-controls.json`. Never edit the generated files |
| Digital/analog boundary | [`integration/macro-contract.md`](integration/macro-contract.md) |
| Host transport | [`spec/streaming-transport-v2.md`](spec/streaming-transport-v2.md) |
| Requirements | [`spec/interface-requirements.md`](spec/interface-requirements.md), [`spec/performance-requirements.md`](spec/performance-requirements.md) |
| Risks (the only risk list) | [`spec/risk-register.md`](spec/risk-register.md) |
| Ground-truth numbers and their confidence | [`spec/design-assumptions.md`](spec/design-assumptions.md) |
| Supplies, islands, grid, decap | [`spec/power-delivery.md`](spec/power-delivery.md) |
| Board, carrier and FPGA obligations | [`spec/board-requirements.md`](spec/board-requirements.md), [`spec/fpga-connection-plan.md`](spec/fpga-connection-plan.md) |
| Package channel | [`spec/package-channel.md`](spec/package-channel.md) |
| Tapeout tests and plan | [`spec/tapeout-plan.md`](spec/tapeout-plan.md), per-block state in `spec/tapeout-readiness.json` |
| Block deliverables | [`spec/block-deliverables.md`](spec/block-deliverables.md) |

## Directory map

| Path | Content |
| --- | --- |
| `rtl/` | Digital macro RTL; `rtl/gen/` holds the register generator and its outputs |
| `sim/` | RTL test benches and the FPGA-side reference transport |
| `integration/` | Chip-level netlist generator, provider pad wrapper, timing constraints, macro contract |
| `integration/chips/` | Per-chip connectivity, bond maps and `run.sh` (`rf/`, `wired/`), the shared part (`common.conn`), the checker, isolation audit, boundary and mode simulations |
| `analog/<family>/` | Schematics, layout generators, extracted netlists and evidence per block family: `core_support`, `island_support`, `pads`, `timing`, `pll_vreg`, `rf_rx`, `rf_tx`, `converters`, `wired_rx`, `wired_tx`, `decap`, `characterization` |
| `spec/` | Requirements, register map, power, package, board and tapeout documents; machine-readable inventories (`*.json`) |
| `verification/` | Check scripts, formal jobs, the digital hardening flow, chip assembly tools |
| `system_model/` | Behavioural Python model of the architecture ([guide](system_model/README.md)) |
| `evidence/` | Stored reports of checks |
| `docs/diagrams/` | Generated block diagram ([note](docs/diagrams/README.md)) |

## Running the main checks

From the repository root:

```sh
make transceiver-chip-top          # per chip (-rf / -wired): connectivity, bond map, isolation audit, boundary sim
make transceiver-top-modes         # per chip: generated pt_chip.sv is current; register map vs cell pins; per-mode chip sim
make transceiver-chip-io           # per chip: SPI and pads through the provider pad models
make transceiver-ctl-blocks        # monitor, USB, wired TX/RX control, POR path, SPI race
make transceiver-regfile           # register generator outputs are current; register file checks
make transceiver-digital-rtl-checks   # transport, FIFOs, gearboxes, frequency counters, end-to-end RTL benches
make transceiver-tapeout-readiness    # per-block tapeout test counts
make transceiver-contract          # interface contract (per-chip bond ledger) and power checks
make transceiver-block-kldrc BLOCK=<name>   # precheck-deck KLayout DRC and antenna for one block
```

`run.sh` rewrites `integration/chips/<chip>/generated/`; it exits non-zero while demand and staged instances remain.
`make transceiver-digital-hardening-rf` / `-wired` run the place-and-route flow of one chip configuration and are heavy;
`make transceiver-digital-synth-area` synthesizes both configurations for cell area.
