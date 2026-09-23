# Programmable analog/PHY companion

One GF180 chip supporting a programmable RF transceiver and a full-duplex wired
lane, with an external FPGA supplying modem, MAC and protocol/endpoint logic.
SPI-only MCU use is supported at lower throughput. The target remains the full
first chip, one wafer.space slot and 50 total terminals.

**RF and wired payload operation are mutually exclusive.** Additional physical
sharing is encouraged. See the [operating policy](spec/exclusive-engine-policy.md).
Narrow temperature and supply ranges are acceptable; actual limits and physical
feasibility remain unqualified.

## Current state

A functional mathematical prototype exists. Mathematical closure, the complete
transistor schematic, and layout are **not complete**. The common baseline has
38 acceptance cases. Later experimental adapters add a finite TX pad/monitor
network and RF/wired ownership interlocks. Their passing checks do not establish
whole-chip closure or transfer automatically to a different composition.

| Start here | Purpose |
| --- | --- |
| [Architecture and block diagrams](spec/block-diagram.md) | Intended connectivity, not completed circuitry |
| [Pin / physical plan](../../docs/roadmap/programmable-transceiver-pin-plan.md) | Interface and die constraints |
| [Fast model documentation](system_model/architecture_fast/README.md) | Executable baseline, assumptions and experiment results |
| [Closure inventory](spec/mathematical-closure.json) | Requirements and outstanding integration work; includes historical notes |
| [Schematic inventory](spec/schematic-implementation.json) | Transistor-level implementation gaps |
| [Analog workflow](spec/analog-design-workflow.md) | Six-family primitive library, transistor composition, then layout/extraction |
| [Feasibility gates](spec/feasibility-gates.md) | Clocks, RF/converters, die/package risks |
| [RTL / macro boundary](integration/macro-contract.md) | Digital implementation and analog black-box obligations |

## Run the checks

From the repository root:

```sh
make transceiver-contract
make transceiver-math-fast
OPENBLAS_NUM_THREADS=1 python3 projects/programmable_transceiver_platform/verification/fast_exclusive_engine_check.py
OPENBLAS_NUM_THREADS=1 python3 projects/programmable_transceiver_platform/verification/fast_exclusive_management_check.py
```

The fast aggregate still exercises historical simultaneous traffic as stress
coverage. The exclusive-engine adapter is experimental; inactive analog clock
and bias shutdown, full mode-transition coverage and RTL agreement remain open.
Full loaded-network traffic can take several minutes. Detailed transistor and
physical-node clock runs can take considerably longer.

## Repository organization

- `system_model/architecture_fast`: common functional model and its acceptance entry point.
- `system_model/connected`: detailed blocks and earlier model compositions; many remain imported by the fast model.
- `verification`: test runners, circuit checks and experimental adapters. These are not all independent supported products.
- `analog`: transistor/passive circuits and simulation fixtures; incomplete and not fabrication-ready.
- `rtl`, `sim`, `integration`: digital logic, testbenches and physical-macro interfaces.
- `spec`: requirements, contracts, decisions and closure inventories.
- `evidence`: selected reports and a consolidated historical index.
- `docs/diagrams`: editable generator, SVG diagrams and rendered previews.

## Historical evidence and consolidation

The former README was a 1.2 MB chronological experiment log. Its complete text
and all original artifacts are preserved in commit
[`53f84a7`](https://github.com/deepai-org/svalbard/commit/53f84a7).
The [history index](evidence/history-index.json) records paths, hashes and available
outcomes for reports removed from the active tree. Retrieve an original with:

```sh
git show 53f84a7:projects/programmable_transceiver_platform/evidence/REPORT.json
```

Failures remain failures; moving a report out of the active tree does not resolve
its design issue. Source code and explicitly referenced reports are retained
pending dependency review. See the [consolidation audit](docs/consolidation.md).
