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

The current 20-case schematic screen is retained as a failure with no passing
case. The profile-3 path is calibrated against realized interconnect, so its
ideal-interconnect timing is not used as a substitute for PEX. Exact
extraction is screened separately and remains the authoritative electrical
checkpoint.

`generate_pulse_layout.py` flattens the parameterized circuit into 428 MOS
devices, resolves forwarded sizing parameters, aligns complementary devices as
CMOS cells, routes phase-local nets in functional bands, and stacks EVEN and
ODD vertically. The current 499.6 by 285 um candidate is zero-DRC and uniquely
pin-resolved LVS-matched. Four-micron M4 logic-supply tracks, six-micron M5
rails, centered high-current source pickup, and route-aware distributed
drain/source accesses reduce current funneling without crossing reserved gate,
supply-tap, or complementary-device columns. Dedicated `VDD_WE`/`VDD_WO`
write-source pins and `VSS_SE`/`VSS_SO` sense-source pins are tied to the same
global supplies by the parent; device bodies remain on the continuous global
well/substrate rails. Hierarchical power-grid attachment is therefore explicit
instead of assuming all pulse current enters one left-edge pin.

Its 9,344-resistor/6,103-capacitor exact nominal extraction passes the complete
contract. EVEN/ODD sense widths are 563.33/596.37 ps, write widths are
168.31/174.38 ps, write delay is 680.76 ps, non-overlap is 117.43 ps, phase
spacing is 370.16 ps, and current is 70.080 mA. Sense highs are 3.158/3.127 V
with 0.105/0.175 V lows; WRITE highs are 3.128/3.133 V with 0.171/0.182 V lows.
The full exact 20-case campaign passes only TT profile `[0,8,9]`, however:
FF/cold exceeds current or width/delay limits, hot profiles miss sense/timing
limits, and SS/cold remains too wide or over-current. This is a nominally closed
physical checkpoint with exact-PVT coverage of 1/5 environments, not a released
pulse macro.

Profile 3 no longer depends on delayed node `D06`, which stopped reaching a
valid threshold at hot corners. Parent-strapped `CLKP_H`/`CLKN_H` ports feed a
short local Metal5 clock path into the profile gate; a minimum 0.4 um route
anchor preserves deterministic D06 routing without materially loading the
delay line. The profile delay pair now sits beside that gate, uses a stronger
second stage, and has fixed route colors so unrelated edits cannot silently
recolor its timing nets. In exact PEX the EVEN profile-3 `P06S/P09S` nodes now
reach 2.649/2.622 V at FF/hot and 2.644/2.652 V at SS/hot. Both FF/hot write
outputs reach rail, while SS/hot produces a full-swing ODD write event. Sense
events and pulse widths still fail the composed contract, so this is retained
as a real downstream-boundary improvement rather than new environment
coverage.

`scripts/analyze_pex_net.py` now traces shortest extracted resistance from a
named root to device terminals selected by gate/model patterns. Counterfactual
scaling localized the former rail failure to supply delivery rather than output
routing. The dedicated write pins reduce the port-to-final-source path to
19.34 ohm; the dedicated sense grounds use legal 1.5-um M4 channels and extract
to 32.60 ohm worst path. Larger final banks and an early feed-forward pull-up
both reduced, rather than improved, delivered peak voltage. The next revision
must add realizable fast/hot and slow-corner profiles and reduce FF/cold current
while preserving the narrow nominal margins.

The local review render is `pulse_layout.png`; the documentation copy is
[clock-pulse-generator-layout.png](../../../../../docs/images/clock-pulse-generator-layout.png).
The checked failing [schematic matrix](pulse_schematic_result.json), retained
[passing nominal PEX checkpoint](pulse_pex_nominal_result.json), full
[exact-PVT matrix](pulse_pex_pvt_result.json), and
[physical checkpoint](pulse_physical_checkpoint.json) keep circuit coverage,
nominal closure, PVT failure, and physical legality as separate claims.
Run `run_pulse_generator.sh` for the schematic matrix and
`run_pulse_physical.sh` for generation, render, DRC, LVS, full-RC extraction,
the nominal electrical gate, and the full PVT matrix. Expected failing matrices
are exported as evidence after the required nominal pass; interrupted or
structurally failed runs retain their complete work directory under `scratch/`.
`run_pulse_layout.sh` is the bounded geometry-only export path for quick,
reproducible Tcl/GDS generation; it does not replace DRC, LVS, or PEX.
