# Routed event-to-lane parent

This boundary composes the selected event generator, V7 local clock fanout,
and direct-regenerative RX/capture as one namespace-safe transistor-intent
source. `compile_source.py` resolves the lane include closure, preserves only
the three public leaf tops, and deterministically namespaces every internal
subcircuit before adding parent connectivity.

`run_physical.sh` now generates the three child layouts, co-places them, and
routes the event clocks, V7 fanout outputs, supplies, and lane clocks in one
parent.  The regenerative and sense-BOOST controls remain explicit parent
pins.  This is intentional: a later package/control layer may strap them, but
keeping them observable preserves calibration options and avoids claiming an
unrouted static connection.

## Current evidence boundary

The routed parent now has promoted physical-legality evidence:

- zero Magic DRC errors;
- unique LVS with 390/390 devices and 204/204 nets;
- distinct VDD and VSS networks;
- all six fanout-to-lane signal routes physically present; and
- full-RC extraction with 14,796 resistors and 9,649 capacitors.

The immutable record is `physical_result.json`; the retained source,
`event_lane_routed_parent.pex.spice`, and the rendered layout are tied to it by
SHA-256 identities.  This proves physical legality and schematic identity, not
post-layout timing, five-environment closure, a closed CDR/link, provider
signoff, or silicon yield.

Run the bounded flow with:

```sh
ip/blocks/analog/wireline_serdes/event_lane_routed_parent/run_physical.sh
```

On hosts with less than the repository's default 32-GiB disk reserve, the
documented harness override may be used for this approximately 11-MiB
development flow, for example `SVALBARD_ANALOG_MIN_FREE_GIB=8`.

## Routed-parent lesson

Hierarchical port coordinates alone are insufficient routing data.  Several
fanout outputs are Metal4 pins directly above Metal5 supply stripes; placing a
Metal4-to-Metal5 via at the label shorts the signal even though the label is
correct.  Parent routing therefore breaks those pins out on their native layer
and changes layers only beyond the child supply geometry.  Future generated
macros should publish pin-access shapes and per-layer obstructions, and parent
route admission should check extracted connectivity after every new escape.

`run_exact_pex.sh` replays the single, hash-bound parent PEX.  The initial
TT/slow-hot result passes 2/2 against the established static-input contract:
at least 0.3 V front-end differential, 0.5 V captured differential, and no
more than 150 mA average supply current.  A deliberately tighter 250 mV
single-ended output-rail diagnostic is reported separately; TT's held-low
capture output is 315 mV and misses that optional diagnostic by about 65 mV.
This is still not dynamic-PRBS, BER, or closed-CDR evidence.

The next gate is expansion of this exact routed parent to 5/5 PVT, followed by
dynamic data and closed-loop clock-recovery checks.
