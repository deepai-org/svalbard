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

`run_exact_pex.py` replays the single, hash-bound parent PEX.  The initial
TT/slow-hot campaign and a disjoint three-corner continuation are composed by
`combine_exact_pex.py`, which fails closed on PEX/physical identity, duplicate
cases, failed inputs, or an incomplete environment set.  The promoted result
passes 5/5 against the established static-input contract: at least 0.3 V
front-end differential, 0.5 V captured differential, and no more than 150 mA
average supply current.  Observed worst cases are 2.384 V at the front end,
2.408 V captured differential, and 103.18 mA.

A deliberately tighter 250 mV single-ended output-rail diagnostic is reported
separately and passes only SS/hot; it was never part of the differential
contract and is not used to relabel the result.  The next gate is dynamic data
and closed-loop recovered-clock checks.  The current evidence is not
dynamic-PRBS, BER, or closed-CDR evidence.

## Dynamic-data checkpoint

`run_dynamic_tt.sh` replaces the static receiver input with 2.5-GT/s PRBS7
and scores ten event-relative samples per interleave.  A passing result requires
one unique common integer-UI latency for both phases at 0.5 V differential
margin; independently fitting the two phases is diagnostic only.  The first
exact-parent TT screen completes but fails: EVEN_Q−EVEN_QB remains between
−2.789 and −2.798 V and ODD_Q−ODD_QB between −2.702 and −2.713 V throughout
the scored PRBS interval.  Neither phase has a passing latency.  The retained
`dynamic_tt_screen_result.json` is therefore falsification evidence, not a
dynamic capture claim.

The next localization must measure the dynamic top-level front-end
differentials and representative extracted event/sense/capture-clock nodes.
That separates a receiver/front-end tracking failure from a clock-event or
capture-reset failure before any sizing or routing change is attempted.
