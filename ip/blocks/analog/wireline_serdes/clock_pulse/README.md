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
