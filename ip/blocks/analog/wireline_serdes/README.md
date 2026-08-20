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
[`serializer`](serializer/README.md) is a half-rate CML 2:1 mux core that is
zero-DRC, uniquely LVS-matched, full-RC extracted, and composed with the actual
TX input devices across five environments at both 1.25 GBd and 2.5 GT/s. Its
static alternating-word result is retained as a test-structure milestone, but
arbitrary changing words exposed a slow high-capacitance boundary.  The
selected replacement integrates the half-rate mux into the programmable TX:
its routed parent is zero-DRC, uniquely LVS-matched, extracts to 1,081R/614C,
and passes 35/35 exact-PEX changing-word aperture cases in 5/5 environments at
both 1.25 and 2.5 GT/s. The routed
children are code-generated and remain explicitly experimental pre-silicon
evidence rather than qualified PCIe macros.

The repeatable method used to take these cells from an executable electrical
contract through generated layout and full-RC evidence is documented in the
[analog layout closure workflow](../../../../docs/verification/analog-layout-closure.md).
All bounded host flows share `scripts/run_analog_flow.sh`; use
`make analog-flow-preflight` to validate their pinned image, paths, and resource
declarations without starting simulation.
Analog evidence combiners share [`analog_evidence.py`](analog_evidence.py), a
dependency-free fail-closed kernel for file identity, environment-set equality,
unique physical-member hashes, connected interval unions, and point/band
coverage. `make check-fast` runs its unit tests. Block-specific simulators keep
their own electrical measurements and acceptance gates; they pass numeric
evidence into this common composition layer.
The current completion inventory and analog-top critical path are tracked in
the [PCIe analog status](../../../../docs/verification/pcie-analog-status.md).

The [`pll`](pll/README.md) directory contains a regenerative differential CML
ring VCO with a matched deterministic startup assist. The dual-edge receiver
requires a 1.25 GHz oscillator. A minimum-subset proof selects two complete
split-control folded parents from three physical candidates. Their 293/400
valid no-initial-condition cases continuously cover the target plus the +/-2%
design band in 5/5 public-model environments; no single candidate covers more
than 3/5. The older seven fixed-control half-rate parents remain corroborating
evidence, while the
twelve-parent 2.5 GHz bank is retained as a physically legal failed overspeed
experiment because it covers only 2/5 environments. The phase interpolator is
also qualified as a two-input break-before-make selector, and a balanced
sixteen-leaf selector hierarchy is physically closed at its prior full-rate
stress but is no longer needed for the selected bank. The exact physical dual
5-bit R-2R DAC is now extracted and qualified in the VCO-bias role across five
environments; two instances provide independent main/regenerative controls for
the two selected parents. The routed two-DAC/two-VCO/selector parent is now
zero-DRC, uniquely LVS-matched, and full-RC extracted. Its exact parent PEX now
passes realizable-code nominal calibration, 5/5 deterministic PVT calibration,
break-before-make handoff, inactive isolation, and old-parent shutdown with
three selected DAC codes of rail headroom. A 55/55-case exact-parent ripple
matrix bounds isolated VDD/reference sensitivity to 8.59 ps worst cycle
displacement and 0.467% worst median-frequency pushing. A symmetric static-CML
divide-by-two is also zero-DRC, uniquely LVS-matched, and full-RC qualified at
1.25 GHz input across 5/5 environments, producing 625 MHz. The actual routed
VCO-bank/two-stage-restorer/divider parent is zero-DRC, uniquely LVS-matched,
extracts to 4,766R/1,580C, and passes exact-parent calibration in 5/5
environments with five adjacent passing divider settings each. The remaining
feedback ratio, statistical startup/mismatch, phase noise, combined
PDN/aggressor sensitivity, realizable calibration control, and the closed PLL
remain unfinished.
