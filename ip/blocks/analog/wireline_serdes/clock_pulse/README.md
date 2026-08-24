# RX clock level conversion and pulse generation

The recovered-clock path is CML, while the regenerative RX capture gates need
rail-to-rail CMOS clocks.  Driving those gates directly from the phase
interpolator is invalid: the extracted PI/restorer output can remain roughly
between 1.1 V and 2.6 V at slow/hot conditions.

`clock_level_converter.spice` is the first closure step.  It uses two matched
NMOS differential receivers with PMOS mirror loads, followed by small isolation
inverters and local output drivers.  It reuses the lane's 1.15 V bias.  The
duplicated, input-swapped halves keep loading and routing symmetric.

The schematic PVT screen deliberately spans CML input envelopes wider than the
present extracted clock chain.  It requires rail recovery within 250 mV,
800 ps period preservation, 40--60% output duty, no more than 375 ps absolute
edge latency, no more than 60 ps complementary crossing skew, and no more than
8 mA average supply current.  Absolute latency and its PVT shift are removed by
the CDR phase calibration; they are not silently treated as fixed delay.

This is not yet a physical signoff claim.  The next required steps are compact
symmetric layout, DRC/LVS, full-RC extraction, then an exact extracted
PI/restorer + converter + real sampler-clock-load simulation.  A programmable
delay/pulse network must produce the separately validated capture window
(500 ps worked at SS/hot; 550 ps is the conservative target).  Final confidence
also requires mismatch, supply/substrate injection, EM/IR, and electrothermal
checks at the composed lane level.
