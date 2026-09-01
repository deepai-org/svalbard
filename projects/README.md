# Projects

This directory contains product-level contracts, interfaces, risks, and status.
Reusable implementation belongs under `ip/`; compact run evidence belongs with
its owning block or under `evidence/`.

## Active product tracks

| Project | Scope | Start here |
|---|---|---|
| PCIe Gen1 x1 endpoint | Endpoint plus reusable wireline SerDes | [`pcie_gen1_endpoint/README.md`](pcie_gen1_endpoint/README.md) |
| 802.11b Wi-Fi radio path | Narrow initial Wi-Fi receiver/radio evidence path | [`wifi_nbiot_radio/README.md`](wifi_nbiot_radio/README.md) |

[`../portfolio.yaml`](../portfolio.yaml) is the machine-readable project and
dependency root. Both projects remain experimental public-PDK, pre-silicon
work; their READMEs identify the authoritative status and limitations.
