# Independently clocked differential capture

This routed GF180 cell replaces the shared-write-clock experiment at the real
dual-edge sampler boundary. Even and odd CML decisions become valid in opposite
half cycles; each lane therefore has its own complementary write clock. The
data restorers, cross-coupled latches, output buffers, body contacts, guard
ring, and mirror-symmetric physical placement otherwise preserve the closed
dual-lane capture topology.

The generated 190 by 122 um cell has zero Magic DRC errors, one unique
pin-resolved Netgen LVS match, and a coupled full-RC extraction containing
1,957 resistors and 1,400 capacitors. `layout.tcl` is the editable geometry
source. `./run.sh` regenerates MAG/GDS, DRC, LVS, PEX, and a 1900 by 1300 PNG;
the checked-in usable render is `layout.png`, and the latest regenerated render
is copied to `scratch/serdes-split-capture-layout-last.png`.

The output stage is deliberately tapered for its 50 fF boundary load rather
than maximum raw width. The prior 64/48 um final inverter overloaded its 16/8
um preceding inverter. The symmetric 32/24 um replacement reduces internal
gate and routed capacitance. The complete 1.25-GBd extracted parent still
passes five representative environments and 160/160 scored PRBS bits under
simultaneous bounded channel, clock-jitter, duty-cycle, and rail-ripple stress.
Worst converter and capture margins are 2.579 V and 2.807 V, respectively,
with 26.07--41.03 mA total composed current.

The same exact-PEX cell closes the previously failing 2.5-GT/s FF/hot final
write at the original 380 ps pulse: the limiting captured differential rises
from 0.289 V to 1.128 V. The calibrated FF/cold lane also passes at 57.07 mA
with 101.8 mV worst pin margin. `../lane/run_capture_2p5_fast_cal.sh`
regenerates one physical stack, runs both corners, and preserves its exact
capture/converter PEX and physical evidence.

The composed flow preserves its exact split-capture PEX as
`scratch/serdes-lane-capture-deserializer-last.pex.spice` and its corresponding
render as `scratch/serdes-lane-capture-layout-last.png`. The checked physical,
nominal, and PVT summaries all bind the same PEX hash; `physical_result.json`
is the physical record from that composed run rather than a separately
regenerated extraction.

This proves deterministic full-RC data transfer through the parallel CMOS
boundary under the declared provisional channel and bounded timing/supply
stress. It does not close mismatch, metastability tails, extracted parent
aggressors, post-fill extraction, EM/IR, or the selected pad/package/channel.
