# Routed event-to-lane parent

This boundary composes the selected event generator, V7 local clock fanout,
and direct-regenerative RX/capture as one namespace-safe transistor-intent
source. `compile_source.py` resolves the lane include closure, preserves only
the three public leaf tops, and deterministically namespaces every internal
subcircuit before adding parent connectivity.

This is not physical evidence yet. The next gate is to generate the three
child layouts, co-place the V7 final sampler drivers beside the corresponding
lane sense-clock gates, route the internal clock and supply nets, and require
zero DRC, unique LVS against this compiled source, full-RC PEX, then exact
TT/slow-hot replay. Only a 2/2 routed-parent result may expand to 5/5 PVT.
