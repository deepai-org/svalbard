# Extracted PCIe pulse-to-capture boundary

This is a product-specific PCIe gate, not an analog-flow framework.  It asks
whether a real pulse source can drive the real regenerative receive consumer
without an ideal timing source at SENSE, BOOST, WRITE, capture clock, or
capture-clock-bar.

`run.sh` regenerates the pulse layout and full-RC PEX, checks DRC/LVS/PEX for
that fresh leaf, byte-binds the checked bridge and lane PEX leaves, then runs
the five public-model PVT cases.  The only ideal sources are legitimate
external boundaries: an upstream recovered rail-clock and a static differential
RX input.  Parent interconnect is still ideal, so this is neither PRBS/channel
nor PCIe-compliance evidence.

## Current sustained result: 3/5, failed honestly

[`pulse_bridge_regenerative_sustained_result.json`](pulse_bridge_regenerative_sustained_result.json)
records the current local-replica candidate.  It scores only the settled 5--8
ns interval, requires two successive capture edges at 700--900 ps cadence, and
enforces `VDD - 250 mV` clock/write rails, 125 ps maximum complementary skew,
at least 500 mV held differential output, and 100 mA maximum average current.

| Environment | Result | Decisive observation |
|---|---:|---|
| TT, 3.30 V, 27 C | pass | WRITE 3.240/3.241 V; capture 3.138/3.151 V; 801.07/800.89 ps cadence |
| FF, 3.63 V, -40 C | fail | WRITE 3.379/3.396 V, but capture 3.311/3.296 V is below the 3.380 V rail criterion |
| FF, 2.97 V, 125 C | pass | WRITE 2.832/2.831 V; capture 2.784/2.787 V; 800.77/800.76 ps cadence |
| SS, 2.97 V, 125 C | fail | WRITE 49/60 mV; no settled periodic capture event |
| SS, 3.63 V, -40 C | pass | WRITE 3.616/3.613 V; capture 3.478/3.498 V; 801.00/800.79 ps cadence |

The candidate isolates the WRITE interval generator from the extracted
direct-regenerative SENSE consumer by deriving it from a local `SB1` replica
and recreating its calibrated MOS gate load locally.  This is real progress
over the previous 2/5 short-window record, retained as
[`pulse_bridge_regenerative_result.json`](pulse_bridge_regenerative_result.json),
but it does not close the boundary.

## What remains

The next PCIe change must create a real, observable corner-selectable timing
or drive path at a full-swing regenerated state, plus a calibration decision
proved in this exact composed screen.  `SEL0..SEL3` are currently physical
pin-load anchors, not functional timing profiles; repeated control vectors are
therefore not calibration coverage.  The FF/cold bridge rail loss and SS/hot
periodic-reset loss are separate failure mechanisms.

Only after a 5/5 result should work move to a routed parent, PRBS/channel, or
CDR/system closure.  Run the failure-preserving screen with:

```sh
./run.sh
```
