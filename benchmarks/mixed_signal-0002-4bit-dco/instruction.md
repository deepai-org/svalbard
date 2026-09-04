# GF180MCU 4-bit digitally controlled ring oscillator

Design and lay out `dco4`, a 4-bit digitally controlled ring oscillator with
enable control and a buffered digital output. This is a compact mixed-signal
task: deliver a real GF180MCU circuit and a layout that extracts back to it.

## Delivery

Write exactly these files under `/app/output`:

```text
analog/dco4.spice
layout/dco4.gds
integration/dco4.json
```

The SPICE top must be:

```spice
.subckt dco4 EN CTRL0 CTRL1 CTRL2 CTRL3 OUT VDD VSS
```

The GDS top cell is `dco4` with text pins `EN`, `CTRL0`, `CTRL1`, `CTRL2`,
`CTRL3`, `OUT`, `VDD`, and `VSS`. The JSON object contains exactly
`{"top":"dco4","pins":[...],"supply_v":3.3}` with pins in that order.

## Electrical contract

Use GF180MCU option D and devices or cells whose models and layout are supplied
by the PDK. Characterization uses a 20 fF load on OUT. Inputs are rail-to-rail
and held stable during each measurement.

- `EN=0`: OUT is below 0.1 V within 1 us and remains there; average supply
  current after settling is below 100 uA.
- After at least 20 ns disabled, raising `EN` starts oscillation within 5 us
  for every code.
- Every code is between 5 MHz and 110 MHz at TT, 3.3 V, 25 C.
- Code 0 is at least 50 MHz, code 15 is at most 25 MHz, and the fastest code
  is at least four times the slowest code.
- Frequency decreases strictly from code 0 through code 15. At least ten
  1-MHz-wide frequency bins contain one or more codes.
- Duty cycle is 40% through 60%; OUT low is below 0.33 V and high is above
  2.97 V.
- Average active power is below 5 mW for every code.

Functional corner checks use SS/3.0 V/125 C and FF/3.6 V/-40 C: every code must
start, remain strictly ordered, and retain a three-to-one tuning ratio;
frequencies may range from 1 MHz to 250 MHz. Changing CTRL while enabled need
not be glitchless, but the output
must settle to the new frequency within 5 us.

## Physical contract

The final GDS must have zero non-density DRC violations, be LVS-equivalent to
`dco4.spice`, contain no unresolved cells, expose all pins, and include
substrate/well ties. The whole-die density rules DCF.1b, M1.4, M2.4, M3.4,
M4.4, M5.4, and MT.3 are checked after integration fill and are the only
macro-level exclusions. Full-RC PEX must pass the TT limits, ordering, and
four-to-one span at codes 0, 7, and 15. The measured PEX netlist—not the
submitted schematic—decides physical eligibility.
Layout area is the top-cell bounding box and excludes no internal whitespace.

All electrical, interface, DRC, LVS, and extracted-TT checks are hard gates.
The verifier also reports area, tuning resolution, span, and active power.
Precomputed waveforms, behavioral oscillators, ideal delay
elements, and non-PDK device models are rejected.

Run `make visible` for public schematic characterization and interface checks.
