# SVALBARD

GF180 source repository for the **programmable transceiver**: two chips,
`pt_rf` and `pt_wired`.

Start here: [`projects/programmable_transceiver_platform/README.md`](projects/programmable_transceiver_platform/README.md)
(review state and mandate: `scratch/reviews/MANDATE.md`).

## Repository map

```text
projects/programmable_transceiver_platform/   the two chips: spec, RTL, analog, integration, signoff
ip/blocks/analog/                              reused analog blocks (wireline SerDes, RF) the transceiver builds on
flows/smoke/                                   tool/container smoke flows
processes/   env/                              process locks, pinned tool/container inputs
scripts/                                       shared analog-flow and evidence helpers
docs/                                          pin plan, layout practice, review images
scratch/                                       run output, published blocks, reviews
```

Transceiver entry points are the `transceiver-*` targets in the `Makefile`
and the per-chip scripts under `integration/`. Earlier projects (PCIe Gen1
endpoint, Wi-Fi/NB-IoT radio, portfolio plans) were removed on 2026-11-26 and
remain in git history.
