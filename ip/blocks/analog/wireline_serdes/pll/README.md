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

`layout.tcl` now generates eleven additional fixed geometries from the same
topology: slow (2.40 um cap / 5.25 um load), fast (0.60/5.25), ultra-fast
(0.50/4.25), high-gain (0.50/6.50), SS/fast-resistor (0.37/6.25 with
15/5 um main/latch tails), and SS/slow-resistor (0.38/4.00 with 15/6 um
tails). Two SS/slow-resistor margin tiles retain the 15/6 um tails and 4.00 um
load while using a 4.0 by 0.50 um low-end cap and a 3.2 by 0.37 um high-end
cap. A 4.0 by 0.85 um center-tail tile adds typical low margin; 4.0 by 0.40 um
and 3.2 by 0.37 um long-load tiles add the SS/fast-resistor low and high
endpoints. All eleven have zero Magic DRC errors, unique Netgen LVS, full-RC PEX,
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
VCTRL route. A later cap-loading screen preserved active-device gain and made
cap width a true geometry parameter: the PCell, terminal straps, gate contact,
and both VSS returns move together. The legality sweep records 0.37 by 3.2 um
as DRC clean and 0.37 by 2.8 um as the first rejected point with 18 errors.

The two regenerated margin tiles close the desired SS/slow-resistor endpoint
range at 2.97 V and 125 C. The low tile has two valid controls spanning
2.432--2.444 GHz; the high tile has three spanning 2.545--2.567 GHz. Each
extracted tile contains 274 resistors and 82 capacitors. This is an aggregate
bank guardband, not one member with an excessively broad analog control.
The final three physical endpoint tiles also preserve their screened margins:
typical-low spans 2.432--2.681 GHz with 11 valid controls, SS/fast-resistor-low
spans 2.430--2.489 GHz with 7, and SS/fast-resistor-high spans
2.499--2.562 GHz with 7. `vco_bank_result.json` records 11/11 added physical
geometries, 5/5 required target environments, and 5/5 environments with full
aggregate +/-2% bank guardband. `layout_vco_bank.png` is the generated
twelve-layout visual index.

This is target coverage, not robust PLL qualification. The SS/slow-resistor
corner has physical endpoint margin, those members also close the
FF/slow-resistor high endpoint, and the three final tiles close typical and
SS/fast-resistor. The tuning-bank sweep still uses a deterministic millivolt
seed to isolate steady-state range from startup behavior.

Startup now has a separate physical mechanism and proof. A matched pair of
1 um NMOS devices can briefly pull either side of one internal differential
node and is off after acquisition. `startup_assist_layout.tcl` generates the
guarded symmetric cell; it has zero Magic DRC errors, a unique Netgen LVS
match, and full-RC PEX with 86 resistors and 12 capacitors. The first 4 um
version started every case but its off-state drain capacitance reduced four of
five sampled target brackets, so it was rejected rather than accepted as a
startup-only result. The regenerated 1 um pair restores all five brackets.

`run_startup_composed.sh` freshly regenerates the assist and seven relevant VCO
tiles, closes DRC/LVS/PEX on all eight cells, and composes four instances of
each selected tile with the extracted assist. With a 500 ps supply/control
ramp, no `.ic`, no `uic`, and a released 270 ps kick, all 42/42 commanded cases
pass across five process/passive/supply/temperature environments and both kick
polarities. All 5/5 environments bracket 2.5 GHz; worst commanded startup is
0.410 ns after release, worst early/late period drift is 0.086%, minimum
differential peak is 429 mV, and worst opposite-kick frequency mismatch is
0.012%. The five no-kick controls are diagnostic only because deterministic
numerical asymmetry is not a statistical noise-startup model.
`startup_composed_result.json` binds these cases to the assist and tile PEX
hashes and records the physical checks.

Phase noise, statistical noise/mismatch startup, supply pushing, safe band
selection, inactive member loading, divider loading, and loop dynamics remain
open.

The bounded reproduction sequence is `run_active_screen.sh` for the
parasitic-preserving active-width screen, `run_cap_drc.sh` for legal cap
length/width boundaries, `run_vco_active_physical.sh` for the four active-tail
tiles and endpoint checker, `run_guardband_screen.sh` and
`run_guardband_physical.sh` for the remaining endpoints, and `run_vco_bank.sh`
for the complete 11/11-physical, 5/5-target, 5/5-guardband result and generated
visual index. `run_startup_assist_physical.sh` closes the assist alone and
`run_startup_composed.sh` reproduces the eight-cell physical and 42-case
commanded-start proof. `layout_startup_assist.png` is the KLayout render of the
checked startup cell.

`run_schematic.sh` runs the 12-environment adversarial screen and intentionally
returns failure until every environment has a bracketing band. The next
physical milestone is to implement safe selection, power gating, and inactive
isolation, then run mismatch/statistical startup, supply-pushing, and phase-noise
simulations. The divider, PFD, charge pump, loop filter, lock detector, and
external-clock bypass remain separate unimplemented boundaries.
