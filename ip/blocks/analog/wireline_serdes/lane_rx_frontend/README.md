# Routed 2.5 GT/s receive front end

This physical parent integrates the programmable differential termination, RX
amplifier, calibrated two-stage data restorer, dual-edge CML sampler, and two
CML-to-CMOS converters. It absorbs the termination-to-RX and all four
sampler-to-converter differential routes while preserving raw-amplifier,
restored, sampler, and converter outputs as passive diagnostic ports.

`layout.tcl` rotates the termination below the receive spine and mirrors the
EVEN converter beside the ODD converter. The EVEN schematic swaps both input
and output differential sides, preserving logical polarity without crossed
physical routes. The termination inputs escape above its control bank on two
equal metal3/metal4 paths; placing a full via stack at the visible input label
would short through an overlying enable route.

The committed parent has zero Magic DRC errors, a unique pin-resolved Netgen
LVS match, and a full coupled-RC extraction containing 5,926 resistors and
3,405 capacitors. `physical_result.json` binds the schematic, layout source,
GDS, render, and exact `lane_rx_frontend.pex.spice` bytes. `layout.png` is the
direct raster render of that GDS.

`../lane/run_capture_2p5_rx_frontend.sh` composes the exact parent with the
physical integrated TX and split capture cell. All five representative
process/passive/supply/temperature environments pass a 24-bit PRBS7 run under
simultaneous 6-ohm-per-leg plus 1-pF channel stress, 30-ps peak TX jitter, 47%
duty cycle, and 20-mV peak 100-MHz rail ripple. Worst signed pin, raw-RX,
restored, converter, and capture margins are 104.159 mV, 47.358 mV,
211.577 mV, 579.32 mV, and 595.135 mV; maximum shared supply current is
53.581 mA. Fast/cold uses a 45-degree sampler phase. Fast/hot uses the exposed
independent interleave controls for a -50 ps ODD sense/regeneration deskew.

This is externally clocked pre-silicon public-model evidence, not PCIe
compliance or tapeout signoff. Converter-to-capture routing, realized clock and
bias trees, local decoupling, full-chip substrate/PDN coupling, selected
pad/ESD/package/channel models, density/fill, EM/IR, and reliability remain
open physical boundaries.
