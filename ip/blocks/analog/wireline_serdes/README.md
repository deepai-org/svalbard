# Wireline SerDes

Reusable GF180 wireline PHY family anchored by PCIe Gen1 at 2.5 GT/s and staged through externally clocked 1.25 GBd operation. Protocol-specific training, receiver detection, and electrical-idle policy remain outside the reusable analog block except for explicitly versioned boundary signals.

The block is not qualified or frozen. Each named child becomes immutable only through its own reviewed release manifest and process-specific hardened macro release.

Implemented children are [`serdes_tx`](serdes_tx/README.md), a GF180
transistor-level CML transmitter with extracted simulations at 1.25 and 2.5
GT/s; [`termination`](termination/README.md), a seven-branch programmable
differential termination with calibrated schematic and full-RC PVT matrices;
[`serdes_rx`](serdes_rx/README.md), a two-stage static CML receiver core with
bias, threshold, and bandwidth controls; [`data_restorer`](data_restorer/README.md),
a dedicated extracted two-stage limiter that closes the RX-to-sampler input
contract under the combined 1.25-GBd lane matrix; [`phase_interpolator`](phase_interpolator/README.md),
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

The receive hierarchy now continues through [`lane_rx_capture`](lane_rx_capture/README.md),
a zero-DRC, unique-LVS, 7,900R/4,804C parent containing termination, RX,
restoration, dual-edge sampling, two CML-to-CMOS converters, and independently
clocked dual capture. Its exact PEX passes the five-environment 2.5 GT/s
combined-stress matrix with at least 623.576 mV final output by 750 ps.
The next [`lane_rx_pi_capture`](lane_rx_pi_capture/README.md) parent physically
integrates the phase interpolator and a two-stage clock restorer into that
hierarchy. Its retained baseline is zero-DRC, uniquely LVS-matched, and
8,625R/5,034C full-RC extracted. A versioned parent replaces both converters
with the lower-input-capacitance StrongARM-style macro and minimally reroutes
the two data trunks that collided with the child's metal-5 power mesh. The new
parent is independently zero-DRC, unique-LVS, and 8,717R/4,874C extracted. Its
24-bit combined-stress replay passes TT, FF/cold, FF/hot, and SS/passive with
685.201 mV worst passing final capture margin. SS/hot remains failed because
the two interleaves deliver the requested word at different integer data ages;
that result remains falsification evidence rather than the selected data path.
The replacement
[`lane_rx_regenerative_capture`](lane_rx_regenerative_capture/README.md)
removes the restorer and level-sensitive sampler, places two independently
clocked StrongARM cells directly on the routed RX output, and feeds the existing
static split capture. It is zero-DRC, unique-LVS, and 7,108R/4,348C full-RC
extracted. A 150 ps non-overlapping write pulse closes a common two-UI final
latency in 5/5 exact-parent environments under the full 24-bit combined-stress
matrix, and 5/5 additional SS/hot phase offsets pass. The next hierarchy must
compose this data path with the phase interpolator and clock restorer and
physically realize the non-overlapping pulse schedule.

The recovered-clock boundary now also has a physically closed
[`clock_pulse`](clock_pulse/README.md) rail converter. Its compact symmetric
dual-mirror receiver, local regenerative assist, and tapered CMOS restoration
chain are zero-DRC, uniquely LVS-matched, and 540R/267C full-RC extracted. It
passes standalone 5/5 PVT and an exact composition using the routed phase
interpolator and clock-restorer extraction. The slow/hot composition has
adjacent passing converter-bias codes, with a second passing restorer code;
the remaining clock-path task is the programmable 550 ps sense / 150 ps write
non-overlap generator and its physical composition with the regenerative
capture gates.

That composition now has a first routed-parent checkpoint in
[`event_lane_routed_parent`](event_lane_routed_parent/README.md): one
namespace-safe 390-device layout passes zero DRC and unique LVS, extracts to
14,796R/9,649C, and its single hash-bound full-RC PEX passes the established
static differential-input capture contract at TT and SS/hot. Five-corner and
dynamic-data closure remain open.

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
