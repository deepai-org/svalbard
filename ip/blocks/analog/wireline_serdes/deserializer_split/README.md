# Independently clocked differential capture

This routed GF180 cell replaces the shared-write-clock experiment at the real
dual-edge sampler boundary. Even and odd CML decisions become valid in opposite
half cycles; each lane therefore has its own complementary write clock. The
data restorers, cross-coupled latches, output buffers, body contacts, guard
ring, and mirror-symmetric physical placement otherwise preserve the closed
dual-lane capture topology.

The generated 190 by 122 um cell has zero Magic DRC errors, one unique
pin-resolved Netgen LVS match, and a coupled full-RC extraction containing
2,202 resistors and 1,570 capacitors. `layout.tcl` is the editable geometry
source. `./run.sh` regenerates MAG/GDS, DRC, LVS, PEX, and a 1900 by 1300 PNG;
the latest usable render is copied to
`scratch/serdes-split-capture-layout-last.png`.

The extracted parent composition uses two routed CML-to-CMOS converters and
this cell after the complete TX/channel/termination/RX/sampler spine. All four
0--300 ps conversion offsets pass nominally. The selected case retains at
least 2.975 V across either converter output and 3.165/3.217 V at the even/odd
parallel outputs. The five representative environments all pass; their worst
converter and capture margins are 2.371 V and 2.363 V, respectively, with
23.05--34.49 mA total composed supply current.

The composed flow preserves its exact split-capture PEX as
`scratch/serdes-lane-capture-deserializer-last.pex.spice` and its corresponding
render as `scratch/serdes-lane-capture-layout-last.png`. The checked physical,
nominal, and PVT summaries all bind the same PEX hash; `physical_result.json`
is the physical record from that composed run rather than a separately
regenerated extraction.

This proves deterministic full-RC data transfer through the parallel CMOS
boundary under the declared provisional channel. It does not close mismatch,
metastability tails, clock jitter/duty distortion, supply/substrate aggression,
post-fill extraction, EM/IR, or the selected pad/package/channel.
