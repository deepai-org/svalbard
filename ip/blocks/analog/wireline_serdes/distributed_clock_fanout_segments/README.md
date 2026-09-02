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
