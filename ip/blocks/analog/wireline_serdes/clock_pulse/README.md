# RX clock level conversion and pulse generation

The recovered-clock path is CML, while the regenerative RX capture gates need
rail-to-rail CMOS clocks.  Driving those gates directly from the phase
interpolator is invalid: the extracted PI/restorer output can remain roughly
between 1.1 V and 2.6 V at slow/hot conditions.

`clock_level_converter.spice` uses two matched NMOS differential receivers with
PMOS mirror loads, a weak cross-coupled regenerative assist, and three tapered
CMOS restoration stages.  It reuses the lane's programmable bias.  The
input-swapped halves keep CML loading symmetric; the physical receiver/load
quartets are compact, edge-dummied, and mirror symmetric.

The schematic PVT screen deliberately spans CML input envelopes wider than the
present extracted clock chain.  It requires rail recovery within 250 mV,
800 ps period preservation, 35--65% output duty, no more than 400 ps absolute
edge latency, no more than 110 ps complementary crossing skew, and no more than
8 mA average supply current.  Absolute latency and its PVT shift are removed by
the CDR phase calibration; they are not silently treated as fixed delay.

The 126 by 117 um layout is zero-DRC, uniquely LVS-matched, and extracts to
540 resistors plus 267 capacitors.  Its exact full-RC standalone matrix passes
5/5 environments with a 100 fF load per output.  The exact extracted
phase-interpolator/restorer/converter chain also covers 5/5 environments.  The
four non-limiting environments use the nominal 1.15/1.15 V restorer/converter
biases.  SS/125 C has adjacent converter codes at 1.00 and 1.05 V with the
restorer at 1.30 V, plus a second restorer code at 1.15 V for converter bias
1.00 V.  That is a calibration window, not a single simulator-only code.

The next physical block is the programmable delay/non-overlap pulse network.
It must produce the separately validated 550 ps sense window and 150 ps write
pulse, then drive the actual extracted regenerative sampler clock gates.  The
remaining lane-level closure still includes mismatch/noise/metastability,
simultaneous supply/substrate aggression, EM/IR, electrothermal, fill, and
package/pad/channel effects.

## Programmable pulse-generator checkpoint

`clock_pulse_generator.spice` is the current transistor-level implementation,
not a behavioral delay source. Twelve non-inverting delay units feed four
realized one-hot sense/start/end profiles for both recovered-clock phases. The
20-case schematic screen passes with at least one profile in every declared
TT, FF/cold, FF/hot, SS/cold, and SS/hot environment under the fixed pulse,
rail, and 75 mA limits.

`generate_pulse_layout.py` flattens the parameterized circuit into 400 MOS
devices, aligns complementary devices as CMOS cells, routes phase-local nets in
functional bands, and stacks the EVEN and ODD phases vertically. The current
approximately 530 by 285 um candidate is zero-DRC and uniquely pin-resolved
LVS-matched. The start/end selector banks and restoration stages are more
compact and separately probed, and the long WSTART/WEND routes no longer run as
an adjacent coupled pair.

Its exact nominal full-RC run is deliberately retained as a failure rather than
promoted as closure. Both selected start nodes have an intermediate extracted
range of roughly 1.56--2.70 V; the first ratioed restoration nodes then reach
only 0.22--0.79 V. Consequently neither final write pulse toggles. The even and
odd sense widths are also asymmetric at 194 ps and 557 ps. This localizes the
next revision to the extracted selector/restorer boundary and phase-parasitic
symmetry rather than the final output drivers. Netgen still reports flattened
device-property warnings, so an independent device-size comparison remains
required even though topology, device count, and pins match uniquely.

The review render is [clock-pulse-generator-layout.png](../../../../../docs/images/clock-pulse-generator-layout.png).
The checked [schematic matrix](pulse_schematic_result.json), retained
[nominal PEX failure](pulse_pex_nominal_failed.json), and
[physical checkpoint](pulse_physical_checkpoint.json) keep circuit coverage,
electrical failure, and physical legality as separate claims.
Run `run_pulse_generator.sh` for the schematic matrix and
`run_pulse_physical.sh` for generation, render, DRC, LVS, full-RC extraction,
and the nominal electrical gate. A failed physical run retains its complete
work directory under `scratch/` for diagnosis.
