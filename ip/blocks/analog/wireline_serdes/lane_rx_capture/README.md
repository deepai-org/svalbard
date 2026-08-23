# Routed RX through dual capture

This parent places the independently clocked dual CMOS capture array directly
above the routed termination/RX/restorer/sampler/converter front end. It owns
the four converter-to-capture data routes, the four shared converter/capture
clock routes, and the capture supply branches. The four data paths each use
128 um of metal4 and the same number of metal3/metal4 turns; the shorter inner
connections dogleg symmetrically so their RC does not silently beat the outer
paths. Capture-clock ports land near the electrical midpoint of each
distributed route. All front-end stage probes and the four final CMOS outputs
remain explicit parent ports.

`run_physical.sh` regenerates both children and this hierarchy in the pinned
GF180 environment, then requires zero Magic DRC errors, one unique Netgen LVS
match, coupled full-RC extraction down to 1 mOhm, and a render of the actual
GDS. The committed parent extracts to 7,900 resistors and 4,804 capacitors.
[`layout.png`](layout.png) is the exact rendered artifact bound by
`physical_result.json`; `lane_rx_capture.pex.spice` is the matching simulation
netlist.

`lane/run_capture_2p5_rx_capture.sh` replaces the termination, RX spine, both
converters, their four data routes, and the split capture leaf with this one
exact PEX. All five representative environments pass a 24-bit PRBS7 at
2.5 GT/s under simultaneous 6 ohm/leg plus 1 pF channel stress, 30 ps peak TX
jitter, 47% duty, and 20 mV peak 100 MHz rail ripple. Worst pin, raw-RX,
restored, converter, and final margins are 104.176 mV, 47.052 mV, 209.582 mV,
558.084 mV, and 623.576 mV; maximum current is 52.203 mA.

The routed capture needs up to 750 ps from its half-rate lane event to meet the
500 mV final-output contract. That leaves 50 ps before the next 800 ps
same-interleave event. This is an explicit output-validity boundary, not a
claim about an unimplemented following register or clock tree.

This remains pre-silicon public-model evidence. Real clock and bias trees,
local decoupling, mismatch/metastability tails, extracted TX/clock substrate
aggression, post-fill extraction, selected pad/ESD/package/channel models,
EM/IR, reliability, and silicon correlation remain open.
