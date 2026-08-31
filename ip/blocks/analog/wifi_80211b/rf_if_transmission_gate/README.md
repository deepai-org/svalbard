# Simple transmission-gate sampler — schematic rejection

This directory records the second sampling-interface topology considered after
the physically closed NMOS baseline: a matched differential transmission gate
with explicit 8 x 4-um NMOS and 16 x 4-um PMOS arrays per leg.  Complementary
clock sources are separate finite paths so their relative midpoint skew is
measured, not assumed.

The simple gate does not earn a layout.  Its five-corner schematic screen at
the frozen 100-MHz IF / 320-MS/s / 5-pF boundary fails even after a bounded
width sweep: the best screened 4x-width point has 79.206 mV worst aperture/hold
error against a 30.518-uV quarter-LSB allocation.  A deliberately easier
10-MHz IF / 80-MS/s screen reduces the 1x gate's worst tracking error to
11.986 mV, but still leaves 17.003 mV of aperture/hold error.  The clock
midpoint skew in these ideal-layout schematic screens is below 3 ps, so it is
not an explanation for the missing three orders of magnitude.

[`simple_transmission_gate_rejection.json`](simple_transmission_gate_rejection.json)
binds the two screens.  The next candidate must state an explicit
charge-injection-cancellation or bottom-plate-sampling mechanism and its timing
before any mixed-NMOS/PMOS physical layout is created.  This is not physical
transmission-gate, ADC ENOB, noise, mismatch, or Wi-Fi receiver evidence.
