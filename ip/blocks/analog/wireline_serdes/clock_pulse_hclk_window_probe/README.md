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
two-inverter extra-delay strengths.  It accepts an environment only when at
least one selected state has a 100--220 ps WRITE pulse, 80--650 ps delay from
the HCLK falling edge, logic rails within 250 mV of their supplies, a valid
`WPN` low, and no more than 75 mA average supply current.

## Current result

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
