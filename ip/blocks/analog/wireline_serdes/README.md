# Wireline SerDes

Reusable GF180 wireline PHY family anchored by PCIe Gen1 at 2.5 GT/s and staged through externally clocked 1.25 GBd operation. Protocol-specific training, receiver detection, and electrical-idle policy remain outside the reusable analog block except for explicitly versioned boundary signals.

The block is not qualified or frozen. Each named child becomes immutable only through its own reviewed release manifest and process-specific hardened macro release.

Implemented children are [`serdes_tx`](serdes_tx/README.md), a GF180
transistor-level CML transmitter with extracted simulations at 1.25 and 2.5
GT/s; [`termination`](termination/README.md), a seven-branch programmable
differential termination with calibrated schematic and full-RC PVT matrices;
[`serdes_rx`](serdes_rx/README.md), a two-stage static CML receiver core with
bias, threshold, and bandwidth controls; [`phase_interpolator`](phase_interpolator/README.md),
a programmable two-input CML phase interpolator for reference-assisted
sampling; and [`cdr`](cdr/README.md), which contains both a dual-edge CML
sampler and a half-rate Alexander phase-detector boundary with extracted PVT
and bounded stress evidence, plus a physically extracted dual-interleave
phase-error combiner. The [`deserializer`](deserializer/README.md) is a
routed differential push-pull capture stage with local input restoration. It
is DRC-clean, uniquely LVS-matched, and full-RC verified both alone and in the
CML-to-CMOS-to-parallel-data composition across representative PVT. The routed
children are code-generated and remain explicitly experimental pre-silicon
evidence rather than qualified PCIe macros.

The repeatable method used to take these cells from an executable electrical
contract through generated layout and full-RC evidence is documented in the
[analog layout closure workflow](../../../../docs/verification/analog-layout-closure.md).
All bounded host flows share `scripts/run_analog_flow.sh`; use
`make analog-flow-preflight` to validate their pinned image, paths, and resource
declarations without starting simulation.
The current completion inventory and analog-top critical path are tracked in
the [PCIe analog status](../../../../docs/verification/pcie-analog-status.md).

The [`pll`](pll/README.md) directory contains the first transistor-level
autonomous-clock experiment: a regenerative differential CML ring VCO with a
physically extracted twelve-layout R/C/active-strength bank and a matched
deterministic startup-assist cell. The sampled composed full-RC bank starts
without initial conditions in 42/42 commanded cases and brackets 2.5 GHz in
5/5 declared environments. The physically closed phase interpolator is reused
as a calibrated two-input break-before-make selector and passes direct
two-VCO isolation/handoff composition. A balanced physical selector hierarchy
for all twelve bands plus four quiet spares now passes 0-DRC, unique LVS,
full-RC all-leaf/PVT testing, and a full-depth nonoverlap handoff. Composition
of the twelve extracted oscillators, their power/start controls, and the
closed-loop PLL remains unfinished.
