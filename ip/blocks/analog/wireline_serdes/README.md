# Wireline SerDes

Reusable GF180 wireline PHY family anchored by PCIe Gen1 at 2.5 GT/s and staged through externally clocked 1.25 GBd operation. Protocol-specific training, receiver detection, and electrical-idle policy remain outside the reusable analog block except for explicitly versioned boundary signals.

The block is not qualified or frozen. Each named child becomes immutable only through its own reviewed release manifest and process-specific hardened macro release.

Implemented children are [`serdes_tx`](serdes_tx/README.md), a GF180 transistor-level CML transmitter with extracted simulations at 1.25 and 2.5 GT/s; [`termination`](termination/README.md), a seven-branch programmable differential termination with calibrated schematic and full-RC PVT matrices; and [`serdes_rx`](serdes_rx/README.md), a two-stage static CML receiver core with bias, threshold, and bandwidth controls. Their layouts are code-generated, DRC-clean, LVS-matched, and explicitly experimental pre-silicon evidence.
