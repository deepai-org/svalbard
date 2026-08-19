# PLL / VCO work in progress

This directory starts the autonomous 2.5 GHz clock-source critical path with a
real GF180 transistor-level VCO experiment. It is not yet a PLL macro; the
delay-tile family is physically checked, but the selectable bank and PLL are
not physically integrated.

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

`layout.tcl` now generates six additional fixed geometries from the same
topology: slow (2.40 um cap / 5.25 um load), fast (0.60/5.25), ultra-fast
(0.50/4.25), high-gain (0.50/6.50), SS/fast-resistor (0.37/6.25 with
15/5 um main/latch tails), and SS/slow-resistor (0.38/4.00 with 15/6 um
tails). All six have zero Magic DRC errors, unique Netgen LVS, full-RC PEX,
and a KLayout GDS render. The slow tile covers
FF/fast-resistor at 2.447--2.542 GHz; the fast tile covers FF/slow-resistor at
2.478--2.543 GHz. The two active-tail tiles cover SS/fast-resistor at
2.458--2.508 GHz and SS/slow-resistor at 2.489--2.506 GHz. Together with the
center tile this expands extracted coverage from 1/5 to 5/5 declared
environments.

The old passive-only ultra-fast and high-gain tiles are retained because their
failure identified the loop-gain boundary: reducing load further killed
oscillation, while increasing VCTRL above the frequency peak slowed the ring.
The active-strength screen then separated main-tail and latch-tail current and
the physical generator moved every affected terminal, gate, source return, and
VCTRL route. `vco_bank_result.json` records 6/6 added physical geometries and
5/5 coverage; `layout_vco_bank.png` is the usable visual index.

This is target coverage, not robust PLL qualification. The SS/slow-resistor
tile has only 3/6 electrical controls, a 17.3 MHz valid frequency span, and no
candidate achieves the desired two-percent frequency guardband. Startup still
uses a deterministic millivolt seed. Phase noise, unseeded/noise startup,
supply pushing, mismatch, safe band selection, divider loading, and loop
dynamics remain open.

The bounded reproduction sequence is `run_active_screen.sh` for the
parasitic-preserving active-width screen, `run_cap_drc.sh` for legal cap
interpolation, `run_vco_active_physical.sh` for the two SS tiles, and
`run_vco_bank.sh` for the complete 6/6-physical, 5/5-environment bank result.

`run_schematic.sh` runs the 12-environment adversarial screen and intentionally
returns failure until every environment has a bracketing band. The next
physical milestone is to improve SS/slow-resistor margin, implement safe
selection and power gating, and run unseeded startup, tuning,
supply-pushing, and phase-noise simulations. The
divider, PFD, charge pump, loop filter, lock detector, and external-clock bypass
remain separate unimplemented boundaries.
