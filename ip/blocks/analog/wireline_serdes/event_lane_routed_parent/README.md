# Routed event-to-lane parent

This boundary composes the selected event generator, V7 local clock fanout,
three capture-owned local restoration bridges, and direct-regenerative
RX/capture as one namespace-safe transistor-intent source. `compile_source.py`
resolves the include closure, preserves only the public leaf tops, and
deterministically namespaces every internal subcircuit before adding parent
connectivity.

`run_physical.sh` now generates the three child layouts, co-places them, and
routes the event clocks, V7 fanout outputs, supplies, and lane clocks in one
parent.  The regenerative and sense-BOOST controls remain explicit parent
pins.  This is intentional: a later package/control layer may strap them, but
keeping them observable preserves calibration options and avoids claiming an
unrouted static connection.

## Current evidence boundary

The routed parent now has promoted physical-legality evidence:

- zero Magic DRC errors;
- unique LVS with 414/414 devices and 216/216 nets;
- distinct VDD and VSS networks;
- all six fanout-to-lane signal routes physically present; and
- full-RC extraction with 17,567 resistors and 11,458 capacitors.

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

`run_exact_pex.py` replays the single, hash-bound parent PEX.  The v2 TT and
slow/hot diagnostic both pass the established static-input contract, but their
outer harness correctly refused promotion because the source tree changed
during that long run.  They must be rerun without concurrent edits before a
new static result is promoted.  Historical v1 five-environment results are not
evidence for the v2 PEX.

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

The v1 localization is retained in `dynamic_localize_tt_result.json` and
`pex_path_localization.json`.  The event SENSE nodes still reach 39--125 mV
low and about 3.13 V high.  After the fanout and parent interconnect, the six
consumer clocks fall only to 0.51--0.77 V, so the regenerative/capture devices
do not reliably reset.  The extracted consumer networks have 236--340 ohm
worst series resistance.  Their shunt capacitance is 1.16--1.98 times the
isolated fanout value; complementary capture clocks are the largest relative
load increase.  The monolithic fanout at the left of the lane and long
parent-owned routes are therefore the first causal boundary.

The v2 parent implements that distributed repair with three local bridges and
is physically closed.  Its new TT PRBS screen still fails, but at a narrower
boundary: bridge inputs fall to 0.63--0.80 V while their same-polarity
second-stage outputs fall only to 1.00--1.80 V.  The front end remains static
and both captures remain held.  The isolated bridge's five-corner evidence
assumed full-swing 200 ps WRITE sources, so it did not qualify the bridge as a
weak-level restorer.  The next experiment should use the first inverted bridge
outputs with the complementary predriver pair, or synthesize a tapered
low-input-capacitance restorer, then re-close physical identity and TT PRBS.
