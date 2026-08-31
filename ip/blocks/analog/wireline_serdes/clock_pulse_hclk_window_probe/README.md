# Selectable full-swing HCLK WRITE-window probe

This is a deliberately narrow schematic prerequisite for the PCIe pulse-path
blocker.  It asks whether a static one-bit control can choose between two
**full-swing**, HCLK-derived end states before narrow-pulse formation, then
drive the existing 650-fF WRITE load through the same five-stage output taper.
The selector is a complementary transmission gate followed by two CMOS
restoring stages.  The code therefore changes a real circuit state, but no
disabled device touches the `WPN` or `WRITE` narrow-event nets.

It is not a full pulse-generator replacement and it does not reuse an ideal
delay source.  In particular it does **not** establish physical geometry,
PEX, the SENSE-to-WRITE timing relationship, the capture-clock bridge, CDR
function, calibration algorithm, or PCIe compliance.

Run the bounded PVT/code screen with:

```sh
./run_hclk_window_probe.sh
```

The screen uses the five declared public-PDK environments (TT, FF/cold,
FF/hot, SS/hot, SS/cold), two static control codes, and four realizable
START-restorer strengths around one selectable-epoch topology. It accepts an environment only when at
least one selected state has a 100--220 ps WRITE pulse, 80--650 ps delay from
the HCLK falling edge, logic rails within 250 mV of their supplies, a valid
`WPN` low, and no more than 75 mA average supply current.

## Retained rejected families

[`hclk_window_baseline_rejection.json`](hclk_window_baseline_rejection.json)
records the 40-case baseline screen.  All candidates restored `WPN` and
WRITE rails at 11.7--19.5 mA, but none covered a PVT environment.  The closest
code (`x4`, `SEL=1`) gave 278.45 ps at TT, 188.49 ps at FF/cold but one UI late,
294.41 ps at FF/hot, 307.87 ps at SS/hot, and 274.47 ps at SS/cold.  Its pulse
is already 265--299 ps at the detector/window boundary, so the excess arises
upstream of the taper.  The next candidate must retard the common START state
or otherwise shorten this **full-swing** timing separation by roughly
45--80 ps while retaining a selected code and all-corner rail recovery.

That is a necessary schematic refinement only.  A candidate that clears it
must still be laid out, DRC/LVS checked, RC extracted, and composed with the
actual capture boundary before it changes PCIe status.

## First contract-driven refinement

The probe now reads [`hclk_window_contract.json`](hclk_window_contract.json)
rather than hard-coding its candidates, environments and thresholds in the
runner.  The same contract binds the semantic instances between HCLK, the
restored `START`, selected `END`, detector `WIN`, and `WPN`.  Its focused unit
test proves that the earlier raw-`S0A` detector bypass and a selector-polarity
swap both fail before SPICE is launched.

Candidate coverage is also fail-closed: a `candidate_id` denotes one circuit
that would be fixed at fabrication, while only its static code may vary after
fabrication.  Results from different transistor choices can no longer be
combined across PVT to manufacture a false calibration pass.

The first four-candidate campaign is retained in
[`restored_start_screen_result.json`](restored_start_screen_result.json).  A
quarter-strength restored START with the x4 selected END covers four of five
environments using its real code.  At FF/cold, both codes have valid
104.19/140.81-ps widths and full rails, but arrive only 21.98/22.21 ps after
the HCLK falling edge versus the declared 80-ps minimum.  This candidate is
therefore rejected before layout.

The fixed common-epoch sweep in
[`common_epoch_delay_rejection.json`](common_epoch_delay_rejection.json) then
proved that one delay strength cannot satisfy both FF/cold's 80-ps minimum and
SS/hot's 650-ps maximum. The first coherent fast/short versus delayed/long
selector in
[`selectable_epoch_initial_result.json`](selectable_epoch_initial_result.json)
covered four environments and missed only SS/hot width by 16.46 ps. These are
falsification records, not candidate passes.

## Current result

[`selectable_epoch_qualified_result.json`](selectable_epoch_qualified_result.json)
records the resulting 40-case bounded screen. One physically fixed candidate,
`epoch_slow_1x_tg_1x_start_0p85x`, covers 5/5 environments using its realized
one-bit code. Selected WRITE widths are 108.05--192.00 ps, selected HCLK-fall
to-WRITE delays are 137.89--647.22 ps, and average currents are 12.77--17.12
mA. FF/cold and FF/hot select the delayed/long state; SS/hot selects the
fast/short state.

This is deliberately only a necessary source-level pass. SS/hot has just
2.78 ps margin to the proxy epoch ceiling, and the probe does not contain the
real SENSE path or extracted consumers. The next gate composes this exact
candidate with SENSE, checks non-overlap and actual SENSE-to-WRITE timing over
5/5 environments, and authorizes layout only if that stronger contract passes.

## Full SENSE/WRITE composition

The same command now also compiles the manifest-selected WRITE circuit with
the authoritative SENSE/BOOST path and its 350-fF/350-fF/650-fF boundaries.
[`sense_write_composition_contract.json`](sense_write_composition_contract.json)
checks SENSE and WRITE widths, SENSE-to-WRITE delay, non-overlap, rails, and
current per physically fixed joint candidate. Its structural test rejects a
bypassed SENSE-tail stage before simulation.

This stronger gate rejects the one-bit architecture before layout. The
baseline, fixed SENSE-tail, selectable SENSE-tail, upstream `SB1` assist, and
joint epoch sweeps are retained as separate falsification records. Final-edge
SENSE control repairs SS/hot and reaches 4/5 environments. A longer WRITE epoch
then repairs FF/cold, but the same setting violates FF/hot delay and dead time.
The exact final result is
[`joint_sense_write_epoch_rejection.json`](joint_sense_write_epoch_rejection.json).

The next circuit needs two orthogonal static controls: interval/edge code 1 for
both FF environments, plus a separate long/short epoch bit that distinguishes
FF/cold from FF/hot. This is a bounded architectural change, not permission for
another unconstrained sizing sweep or physical implementation.
