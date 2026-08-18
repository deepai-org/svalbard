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

`run_schematic.sh` runs the 12-environment adversarial screen and intentionally
returns failure until every environment has a bracketing band. The next
physical milestone is to prune the bank, implement safe selection and power
gating, generate a symmetric three-stage layout, and run DRC, LVS, full-RC
extraction, startup, tuning, supply-pushing, and phase-noise simulations. The
divider, PFD, charge pump, loop filter, lock detector, and external-clock bypass
remain separate unimplemented boundaries.
