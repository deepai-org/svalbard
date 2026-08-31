# Extracted PCIe pulse-to-capture boundary

This is a deliberately product-specific PCIe gate, not a generic analog-flow
framework.  It connects a freshly extracted pulse generator to the checked
extracted capture-clock bridge and the checked extracted direct-regenerative
lane.  It exists to answer one immediate question: can the real timing source
drive the real receive consumer without ideal SENSE, BOOST, WRITE, or capture
clock sources?

`run.sh` regenerates the pulse layout and full-RC PEX, checks that fresh leaf's
DRC/LVS/PEX record, then simulates all five declared public-model PVT cases.
The bridge and lane PEX leaves are byte-bound to their own passing physical
records.  The saved
[`pulse_bridge_regenerative_result.json`](pulse_bridge_regenerative_result.json)
is a failed result by design: failing evidence is retained rather than hidden.
The raw freshly generated PEX stays in the retained `scratch/` run directory;
the replay creates it again from the checked source rather than treating a
stale nominal deck as input.

## Boundary and result

The only idealized stimuli are legitimate external boundaries: the recovered
rail-clock entering the pulse generator and a static differential RX input.
The test removes ideal sources from SENSE, BOOST, WRITE, capture-clock, and
capture-clock-bar.  It is a static-input control-path screen, not PRBS/channel
or PCIe-compliance evidence.  The PEX leaves are composed through ideal parent
connections; no routed top-level parent exists yet.

The checked composition is 2/5 under a deliberately conservative rail screen
of `VDD - 250 mV`, 125 ps maximum complementary skew, at least 500 mV held
output differential magnitude, and 100 mA maximum average supply current.

| Environment | Result | Decisive observation |
|---|---:|---|
| TT, 3.30 V, 27 C | pass | WRITE 3.245/3.245 V; capture clocks 3.149/3.158 V; worst skew 83.44 ps |
| FF, 3.63 V, -40 C | fail | WRITE 41/57 mV; capture clocks 8.6/9.5 mV |
| FF, 2.97 V, 125 C | fail | WRITE 34/43 mV; capture clocks 4.1/4.6 mV |
| SS, 2.97 V, 125 C | fail | WRITE 30/38 mV; capture clocks 3.2/3.5 mV |
| SS, 3.63 V, -40 C | pass | WRITE 3.621/3.619 V; capture clocks 3.483/3.499 V; worst skew 84.83 ps |

This falsifies closure of the PCIe recovered-clock/capture boundary.  It does
not falsify the independently qualified bridge or lane screens that used an
ideal source at their upstream boundary.

## Minimal failure localization

`run_ff_cold_load_probe.sh` runs one FF/cold counterfactual on the same
realized profile (`0,8,9`) and freshly extracted pulse PEX.  It changes only
the immediate consumer and retains the output's 650 fF reference load where
needed.  Its retained
[`ff_cold_load_probe_result.json`](ff_cold_load_probe_result.json) gives:

| Consumer connected to the pulse | E/O WRITE peak | Interpretation |
|---|---:|---|
| Existing 350 fF SENSE/BOOST + 650 fF WRITE placeholders | 3.184/3.204 V | The pulse leaf already misses the 3.380 V FF/cold rail threshold. |
| Same SENSE/BOOST placeholders + extracted bridge | 3.374/3.387 V | The bridge is not the dominant loading cause; only E remains 6 mV short. |
| Extracted lane SENSE/BOOST network + 650 fF WRITE placeholder | 40/54 mV | Reproduces the composed collapse without the bridge's capture outputs. |

The next direct PCIe work is therefore circuit/layout work: isolate and size
the pulse's WRITE restoration for the actual extracted direct-regenerative
SENSE/BOOST network, then search realizable profiles over the full PVT matrix.
Only after that passes should a routed parent, PRBS/channel, and system
clock-recovery closure be attempted.  There is no justification here for a
new general compiler, router, or optimizer.

Run either command from this directory.  Both currently return nonzero because
they intentionally preserve failing evidence:

```sh
./run.sh
./run_ff_cold_load_probe.sh
```
