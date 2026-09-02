# Consumer-local clock-fanout segments

This v3 physical IR preserves the selected sampler `6x -> 16x -> 32x` and
capture `4x -> 8x` chains while cutting each at the final-driver input. Only
the 32x sampler or 8x capture final must occupy the consumer gate corridor;
predrivers may be placed in peripheral whitespace. The inter-segment net is a
gate-drive net and remains a routed timing object, not an ideal connection.

Each generated cell contains an explicit tied-off 1x dummy phase required by
the current two-phase placer. Simulation and parameter-free aggregate-width
LVS views derive from the same stage tuple. Physical legality of all four
segments is only the first gate; exact extracted recomposition must match the
compact whole-branch reference before routed-parent placement is authorized.

`combine_pex.py` verifies all four extracted identities and constructs six
complete predriver/final paths behind the established fanout interface.
`run_composed_screen.sh` then reuses the exact event/lane TT and SS/hot gate.
Its isolated inter-segment connection is deliberately not routed-RC evidence;
a pass only admits the hierarchy cut to parent placement.

`floorplan_contract.json` captures the generated final-stage output pin
coordinates, the six exact lane consumer landings, and the inherited 19.2 ps
output-route budget. It intentionally contains no selected placement yet: a
placement becomes admissible only after obstruction-aware overlap checks and
one parent DRC/LVS/PEX, not from coordinate alignment alone.
