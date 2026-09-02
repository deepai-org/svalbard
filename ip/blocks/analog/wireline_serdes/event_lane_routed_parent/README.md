# Routed event-to-lane parent

This boundary composes the selected event generator, V7 local clock fanout,
four reference-driven non-regenerative level receivers, and direct-regenerative
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
- unique LVS against the compiled transistor intent;
- distinct VDD and VSS networks;
- all six fanout-to-lane signal routes physically present; and
- full-RC extraction with 16,172 resistors and 10,247 capacitors.

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

The v4 parent gave four independently timed weak nodes their own converter and
an explicit `LEVEL_REF`.  It is zero-DRC, uniquely LVS-matched, and full-RC
extracted to 17,042R/10,803C.  Its complete hash-bound TT PRBS run still fails:
the reused CML converters remain fixed even with a static reference because
their large regenerative input presents excessive load to the fanout.  The
replacement non-regenerative `reference_level_receiver` is zero-DRC,
uniquely LVS-matched, parameter-audited, 327R/128C full-RC extracted, and covers
5/5 PVT environments with a six-code bias set.

The v5 parent replaces all four converter instances without changing the
published footprint or pin accesses.  It is zero-DRC, uniquely LVS-matched,
and extracts to 16,172R/10,247C.  The exact ten-sample TT PRBS run at the
leaf-qualified 1.20 V bias code nevertheless fails with no common or
independent passing latency.  The event sources remain healthy (39--121 mV
lows and 3.125--3.135 V highs), and receiver inputs reach 0.556--3.247 V, but
capture-clock receiver OUTN rises only to 0.858/0.918 V and OUTP remains above
3.083 V.  Both capture outputs consequently remain fixed near 3.01 V
differential.  The retained `dynamic_tt_screen_result.json` is hash-bound v5
falsification evidence; `dynamic_tt_v5_bias1p08_result.json` retains the same
failure at the adjacent 1.08 V code, while `dynamic_tt_v4_result.json`
preserves the previous topology's result.

The next receiver contract must include the parent-observed assertion duration
and routed source impedance, then requalify leaf and parent.  Standalone
voltage-extrema coverage is not sufficient for this pulse interface.

The v5 localization measures 386.6 ps below the qualified reference on the
even capture input and 290.6--293.0 ps on the two SENSE inputs.  It also exposed
an integration error: the leaf's TT reference was 1.90 V, while the first
parent runs used VDD/2 = 1.65 V.  Correcting the realizable reference code to
1.90 V improves capture OUTN excursion to 1.17--1.21 V but still does not
restore rail-valid complements.  The updated PEX path report measures
181--187 ohm worst input-net terminal resistance, 86--187 fF input-net shunt
capacitance, and 93--189 fF receiver-output net capacitance.  A focused exact
leaf matrix proves the first coverage loss is the shortened low interval
(5/5 to 3/5); source resistance does not reduce it further, while the full
parent load reduces it to 0/5 for the original serial-output receiver.

The v6 receiver instead creates its complement internally and drives the two
external outputs with parallel buffers.  It is independently zero-DRC,
unique-LVS and full-RC closed at 28 MOS, 389R/172C.  A corrected exact envelope
matrix uses the measured asymmetric loads rather than assigning the largest
single-ended load to both outputs: nominal covers 5/5 environments, while the
short-SENSE, capture-parent and SENSE-parent profiles each cover 4/5 and miss
only SS/125 C.  Capture and SENSE have a shared TT code at 1.40 V.

The regenerated v6 parent remains zero-DRC and uniquely LVS-matched and now
extracts to 16,426R/10,423C.  Its complete ten-sample TT PRBS run still has no
passing latency.  The capture receivers improve materially—OUTN reaches
2.121/2.375 V and OUTP falls to 1.042/0.810 V—but the downstream capture state
remains fixed.  More decisively, the two SENSE receiver OUTP nodes remain above
3.072/3.128 V even though their inputs traverse 0.594--3.221 V with measured
below-reference widths of 287--290 ps.  The scalar envelope therefore omitted
a relevant waveform polarity/history/internal-state condition.  The next
bounded experiment is an exact parent-waveform replay at the leaf boundary,
followed by a polarity/timing correction before another full parent run.

The v7 structural audit found that the fanout supplies an active-low SENSE
interval while the StrongARM evaluates with `SENSE_CLK` high. The parent now
routes the receiver's complementary `OUTN` to SENSE and remains zero-DRC,
unique-LVS and 16,426R/10,423C extracted. Exact ten-sample TT PRBS still has no
passing latency: both front ends resolve once and remain fixed. A shorter
hash-bound run samples one full period every 10 ps. The corrected SENSE output
stays at 0.592--0.607 V despite a 0.657--3.149 V input. Exact leaf replay proves
the waveform itself is sufficient; exact leaf-plus-StrongARM replay reproduces
the failure. The remaining boundary is therefore nonlinear consumer loading,
not polarity, lumped RC, or input waveform shape.

The same waveform probe has now been run at SS/125 C. The routed SENSE input
spans 0.816--2.865 V but remains below its 1.825 V reference for only 218 ps,
versus 283 ps at TT. This is authoritative evidence that a TT pulse width is
not a conservative PVT envelope. The role-specific SENSE receiver and several
bounded alternatives remain failed at this corner; the next parent revision
must store/stretch the event locally or deliver a stronger producer-side pulse
before another full PRBS campaign.
