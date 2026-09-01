# Analog blocks

Analog implementation is organized by reusable subsystem rather than by run or
experiment. Each subsystem owns its circuit source, layout generators, local
verification wrappers, and compact evidence.

| Subsystem | Product use | Entry point |
|---|---|---|
| Wireline SerDes | PCIe Gen1 x1 | [`wireline_serdes/README.md`](wireline_serdes/README.md) |
| 802.11b RF/IF path | Wi-Fi radio | [`wifi_80211b/component.yaml`](wifi_80211b/component.yaml) |

Candidate outputs and raw simulation databases belong in the ignored
repository `scratch/` directory. A leaf-level DRC, LVS, or extracted simulation
result does not establish parent- or product-level closure.
