# Routed 2.5 GT/s receive spine

This parent places and routes the receive amplifier, calibrated two-stage data
restorer, and dual-edge CML sampler. The parent owns both bandwidth-critical
differential boundaries and exposes diagnostic copies of the raw-amplifier and
restored nodes so composed simulations can score every stage without replacing
the physical interconnect.

`layout.tcl` produces the hierarchy shown in `layout.png`. The release is zero
DRC, uniquely LVS-matched, and full-RC extracted to 1,309 resistors and 464
capacitors. `physical_result.json` binds the layout and schematic sources, GDS,
render, and exact `lane_rx_spine.pex.spice` bytes.

The sampler bias escapes below the sampler on a separate M4 track. Moving it
off the original clock-overlapped route reduced explicit clock-to-bias coupling
from 5.70 fF to 3.52 fF while preserving DRC/LVS and the five-environment lane
contract. A later parent must replace the present low-impedance ideal bias
fixture with the extracted bias tree and local decoupling.

`run_physical.sh` regenerates the physical proof with a two-CPU, 8-GiB bound.
The lane-level `../lane/run_capture_2p5_routed_rx.sh` composes this parent with
the exact TX, termination, CML/CMOS converters, and split capture PEX. Its five
representative environments retain the established PRBS7, 6-ohm-per-leg plus
1-pF channel, 30-ps peak jitter, 47% duty cycle, and 20-mV rail-ripple stress.

This parent closes routing only from the RX amplifier through the sampler. The
next `../lane_rx_frontend` hierarchy now absorbs termination-to-RX and
sampler-to-converter routing while retaining this cell and its evidence as a
reproducible child milestone. Clocks, bias, pad, package, and substrate/PDN
closure remain later integration boundaries.
