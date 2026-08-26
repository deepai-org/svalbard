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
not a behavioral delay source. Each phase starts from its dedicated full-swing
`CLKP_H`/`CLKN_H` parent clock. One physical falling-edge interval drives
SENSE/BOOST. WRITE is derived from the restored SENSE boundary through a
four-inverter receiver, a rising-edge interval detector, and a five-stage
geometric taper. Exact PEX rejected and removed the old global delay line,
pass-gate selector, and reset-dominant write latch.

The ideal-interconnect screen remains a failure and is not substituted for
PEX: extracted interconnect changes narrow-pulse behavior materially.
`run_pulse_hot_probe.sh` performs layout, DRC, unique LVS, exact full-RC
extraction, and TT plus FF/125 C and SS/125 C electrical probes with bounded
resources.

`generate_pulse_layout.py` flattens the circuit into 128 MOS devices, aligns
complementary devices as CMOS cells, routes phase-local nets in functional
bands, and stacks EVEN and ODD vertically. The current 175.4 by 285 um
candidate is zero-DRC, uniquely pin-resolved LVS-matched, and extracts to 3,408
resistors plus 2,477 capacitors. Substrate-tap columns are filtered against
complete multi-finger device spans, fixed HCLK landing intervals block the
automatic M4 allocator, and route comments make emitted nets inspectable.
Dedicated `VDD_WE`/`VDD_WO` and `VSS_SE`/`VSS_SO` pins retain explicit
parent-grid attachment.

Exact PEX produces complete dual-phase waveforms in all three focused
environments. TT sense widths are 598.30/590.88 ps and write widths are
336.47/349.55 ps at 41.172 mA. FF/125 C gives 597.39/589.16 ps sense and
336.93/349.84 ps write at 38.354 mA. SS/125 C gives 543.55/539.69 ps sense and
119.84/123.13 ps write at 23.501 mA. This is a major topology and area
improvement, but no case passes the complete contract: TT/FF write is wider
than the 100--220 ps limit and begins before the external SENSE fall; SS/hot
WRITE reaches only 1.922/1.926 V and its modulo-cycle delay is too early. The
full 20-case campaign is not promoted until those failures are corrected.

The central retained lesson is that a narrow pulse must not be transported
through a slow restoration chain. The robust write topology transports the
full-swing `WSB` step, delays that step physically, forms the interval locally,
and only then drives the output taper. A minimum-load receiver failed because
its 0.6 um device could not charge even a short extracted route; sizing must
include route/via capacitance and the parallel gate loads of both detector
branches. Attempts to mux narrow active-low pulses through transmission gates
or a three-NOR selector were rejected after exact PEX attenuated or erased the
selected event.

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
The newer compact candidate has separate, explicitly failing
[nominal](pulse_candidate_nominal_result.json) and
[hot-corner](pulse_candidate_hot_result.json) records so it cannot overwrite
the older nominally passing checkpoint.
Run `run_pulse_generator.sh` for the schematic matrix and
`run_pulse_physical.sh` for generation, render, DRC, LVS, full-RC extraction,
the nominal electrical gate, and the full PVT matrix. Expected failing matrices
are exported as evidence after the required nominal pass; interrupted or
structurally failed runs retain their complete work directory under `scratch/`.
`run_pulse_layout.sh` is the bounded geometry-only export path for quick,
reproducible Tcl/GDS generation; it does not replace DRC, LVS, or PEX.
