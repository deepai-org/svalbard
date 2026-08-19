# PLL / VCO work in progress

This directory starts the autonomous 2.5 GHz clock-source critical path with a
real GF180 transistor-level VCO experiment. It is not yet a PLL macro and it
is not physically closed.

`ring_vco.spice` is a three-stage differential CML ring followed by an
isolating CML output buffer. Each delay cell has a driven differential pair, a
weaker cross-coupled regenerative pair on a separate tail, matched p-poly
loads, and matched inversion-mode NMOS capacitors. The first unregenerated
version produced transient zero crossings and then decayed to a symmetric DC
point; the checked version requires sustained late-time oscillation.

The architecture exposes load resistance, MOS-cap geometry, and tail control
as independent tuning axes. `run_vco.py` tests stable early/late period,
differential swing, current, and seeded startup. A code is usable only with at
least 200 mV differential peak in both directions, 3--40 mA total VDD current,
less than 1% early/late frequency drift, and the tenth crossing by 10 ns. An
environment covers 2.5 GHz only when two adjacent usable control voltages in
one physical band bracket the target. The checker records local KVCO polarity
because two low-supply/hot bands tune with negative slope; a later PLL must
select matching loop polarity or exclude those bands.

The committed architecture summary records 735 completed schematic cases.
The six speed/gain bounds are covered after adding three targeted interpolated
R/C points. This is deliberately weaker than a PVT closure claim: the broad
12-environment screen must be rerun with the final bank, and the parameterized
choices must become a realizable break-before-make switch network or
independently power-gated VCO variants.

The first physical delay tile is now generated as a 54 by 56 um symmetric
cell. It has zero Magic DRC errors, a unique pin-resolved Netgen LVS match, and
full-RC extraction containing 275 resistors and 79 capacitors. Four instances
of that extracted tile form the three-stage ring plus output buffer. At the
nominal public corner all 7/7 controls sustain oscillation; the frequency range
is 2.459--2.709 GHz and 0.88--0.98 V brackets 2.5 GHz. The committed
`layout.png` is rendered from the checked GDS rather than drawn separately.

The same fixed tile covers only 1/5 extracted speed/gain environments. The
fast-MOS/fast-resistor corner is too fast, the fast-MOS/slow-resistor corner is
slightly slow, the slow-MOS/fast-resistor corner loses loop gain, and the
slow-MOS/slow-resistor corner is slow. This is retained as a failing band-bank
screen, not hidden by the nominal pass. It requires at least a slower
high-capacitance band, a faster low-capacitance band, and a higher-gain load
variant.

`run_schematic.sh` runs the 12-environment adversarial screen and intentionally
returns failure until every environment has a bracketing band. The next
physical milestone is to generate and extract the additional band tiles,
implement safe selection and power gating, and run startup, tuning,
supply-pushing, and phase-noise simulations. The
divider, PFD, charge pump, loop filter, lock detector, and external-clock bypass
remain separate unimplemented boundaries.
