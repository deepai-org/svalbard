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
write event is stored by a reset-dominant cross-coupled-NOR interval latch and
then driven by a four-stage geometric taper. The two phases have explicit
physical sizing parameters: EVEN has a direct profile-2 reset branch, while
ODD uses a stronger local delayed-end stage. Programmability provides
calibration choices; it does not make a failing code acceptable.

The current 20-case schematic screen is retained as a failure. None of the
four profiles covers all limits in any declared environment: nominal profiles
miss non-overlap or the 75 mA limit, FF/cold reaches roughly 83--87 mA, and the
present slow-corner interval choices either lose the event or miss width and
delay. This supersedes the earlier schematic-coverage claim and must be fixed
before a full extracted PVT campaign is meaningful.

`generate_pulse_layout.py` flattens the parameterized circuit into 422 MOS
devices, resolves forwarded sizing parameters, aligns complementary devices as
CMOS cells, routes phase-local nets in functional bands, and stacks EVEN and
ODD vertically. The current 499.6 by 285 um candidate is zero-DRC and uniquely
pin-resolved LVS-matched. Four-micron M4 supply tracks, full-width M5 rails,
local M4/M5 via arrays, five source accesses, and route-aware distributed drain
accesses reduce final-bank current funneling without crossing reserved gate,
supply-tap, or complementary-device columns.

Its 9,045-resistor/6,110-capacitor exact nominal extraction passes every timing
limit: EVEN/ODD sense widths are 574.57/602.71 ps, write widths are
215.74/198.40 ps, write delay is 677.64 ps, non-overlap is 103.07 ps, and phase
spacing is 380.72 ps at 68.61 mA. It is still an electrical failure. EVEN/ODD
WRITE peaks are 3.002/2.906 V rather than at least 3.05 V; sense lows are
0.253/0.313 V rather than at most 0.25 V. The evidence is therefore a timing-
closed nominal physical checkpoint, not a closed pulse macro.

`scripts/analyze_pex_net.py` now traces shortest extracted resistance from a
named root to device terminals selected by gate/model patterns. On this exact
PEX the worst final-PMOS source path is 27.98 ohm; the preceding two-access
layout was 32.15 ohm. The retained resistance experiment and larger-final-bank
experiments show that blindly adding width increases gate capacitance and can
lower the output peak. The next revision must remove the remaining dominant
source/output access segments or add a genuinely local rail-restoring topology,
then rebuild profile coverage and re-run full schematic and extracted PVT.

The local review render is `pulse_layout.png`; the documentation copy is
[clock-pulse-generator-layout.png](../../../../../docs/images/clock-pulse-generator-layout.png).
The checked failing [schematic matrix](pulse_schematic_result.json), retained
[nominal PEX checkpoint](pulse_pex_nominal_failed.json), and
[physical checkpoint](pulse_physical_checkpoint.json) keep circuit coverage,
electrical failure, and physical legality as separate claims.
Run `run_pulse_generator.sh` for the schematic matrix and
`run_pulse_physical.sh` for generation, render, DRC, LVS, full-RC extraction,
and the nominal electrical gate. A failed physical run retains its complete
work directory under `scratch/` for diagnosis.
