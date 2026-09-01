# SVALBARD

SVALBARD is a GF180 source monorepo for physically verified mixed-signal
experiments and product designs. The active product tracks are a PCIe Gen1 x1
endpoint and an 802.11b Wi-Fi receiver/radio path. All present electrical and
physical results are public-PDK, pre-silicon evidence—not provider signoff,
fabricated-silicon correlation, PCI-SIG compliance, or Wi-Fi interoperability.

## Start here

| Need | Authoritative entry point |
|---|---|
| Portfolio scope and repository policy | [`plan.md`](plan.md) |
| Active projects and dependency roots | [`portfolio.yaml`](portfolio.yaml) |
| Project directory index | [`projects/README.md`](projects/README.md) |
| Documentation index | [`docs/README.md`](docs/README.md) |
| Analog block directory index | [`ip/blocks/analog/README.md`](ip/blocks/analog/README.md) |
| PCIe product overview | [`projects/pcie_gen1_endpoint/README.md`](projects/pcie_gen1_endpoint/README.md) |
| PCIe analog implementation status | [`docs/verification/pcie-analog-status.md`](docs/verification/pcie-analog-status.md) |
| Wi-Fi product/evidence overview | [`projects/wifi_nbiot_radio/README.md`](projects/wifi_nbiot_radio/README.md) |
| Analog closure practice | [`docs/verification/analog-layout-closure.md`](docs/verification/analog-layout-closure.md) |
| Executable analog tooling boundary | [`docs/verification/analog-evidence-tooling-overview.md`](docs/verification/analog-evidence-tooling-overview.md) |
| Product-first compiler roadmap | [`docs/roadmap/analog-evidence-compiler-spec.md`](docs/roadmap/analog-evidence-compiler-spec.md) |

The top-level Aether files are reviewed product contracts, not inputs to a
completed compiler:
[`pcie_gen1_x1.aether`](projects/pcie_gen1_endpoint/analog/pcie_gen1_x1.aether)
and [`wifi_80211b.aether`](projects/wifi_nbiot_radio/analog/wifi_80211b.aether).

## Repository map

```text
projects/    Product contracts, risks, interfaces, and product-facing status
ip/          Reusable RTL and analog block source, physical generators, and compact evidence
flows/       Repository smoke and integration flows
processes/   Process locks, model boundaries, and fabrication-data gaps
env/         Pinned tool/container inputs and acquisition metadata
schemas/     Machine-readable contract schemas
evidence/    Compact run manifests and indexes, not raw simulation databases
docs/        Architecture decisions, roadmaps, verification status, and review images
scripts/     Shared validation, evidence, and bounded-flow helpers
scratch/     Ignored disposable/candidate run output; never an authoritative tracked claim
```

Local indexes describe the shared [`processes/`](processes/README.md),
[`schemas/`](schemas/README.md), [`evidence/`](evidence/README.md), and
[`scripts/`](scripts/README.md) directories.

Circuit-specific commands live beside their blocks. Shared entry points include:

```sh
./bootstrap.sh doctor
make graph
make repo-audit
python3 scripts/validate.py structure
python3 scripts/test_analog_evidence.py
```

`make check-fast` is broader and may invoke pinned containerized physical
flows. Use `ANALOG_FLOW_CHECK_ONLY=1` with a block's `run_*.sh` wrapper to test
its host/container preflight without launching the full experiment.

## Source and evidence discipline

- Human-authored source and compact review evidence belong in Git.
- Raw waveforms, run directories, PDK installs, and generated tool trees do not.
- A passing leaf is not a passing parent or product.
- DRC/LVS/PEX claims name their exact physical boundary and byte identities.
- Missing RF, package, reliability, statistical, or provider physics remains an
  explicit obligation rather than an inferred pass.

The current success criterion is working, physically composed PCIe and Wi-Fi
designs with bounded evidence. General topology synthesis, a new comprehensive
analog language, GUI, and cloud infrastructure are deferred unless an active
product gate requires them.
