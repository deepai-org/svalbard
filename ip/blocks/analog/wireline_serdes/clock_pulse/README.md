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
resistors plus 2,477 capacitors in the retained earlier checkpoint. The current
delayed-step revision extracts to 3,492 resistors plus 2,531 capacitors.
Substrate-tap columns are filtered against
complete multi-finger device spans, fixed HCLK landing intervals block the
automatic M4 allocator, and route comments make emitted nets inspectable.
Dedicated `VDD_WE`/`VDD_WO` and `VSS_SE`/`VSS_SO` pins retain explicit
parent-grid attachment.

The current extracted candidate passes the complete focused TT contract:
591.87/583.98 ps SENSE, 206.87/213.84 ps WRITE, 605.54 ps write delay,
13.67 ps non-overlap, valid rails, and 40.669 mA. FF/125 C gives
592.74/583.02 ps SENSE and 202.82/207.82 ps WRITE with valid timing and SENSE
rails, but WRITE reaches only 2.687/2.692 V against a 2.72 V minimum. SS/125 C
retains valid 540.98/540.58 ps SENSE pulses, but the write restoration chain
does not propagate a complete pulse. Focused coverage is therefore 1/3, not
closure, and the full 20-case campaign is not promoted.

The central retained lesson is that a narrow pulse must not be selected or
transported through a slow restoration chain. The improved write topology
restores the full-swing `WSB` step, delays the start once, derives a separately
loaded end edge, forms the active-low interval locally, and only then drives the
output taper. This change reduced nominal write width from roughly 340 ps to
207--214 ps and produced the first exact-PEX TT pass on the compact macro. A
minimum-load receiver failed because
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
both reduced, rather than improved, delivered peak voltage. A stronger final
PMOS increased the preceding stage's gate load and lowered the short-pulse
peak; reducing final NMOS load recovered FF/hot swing but lengthened WRITE
beyond 220 ps. The next revision must apply the existing profile controls to a
full-width state before interval formation, especially for SS/hot, and recover
the remaining 28--33 mV FF/hot WRITE swing without losing nominal width margin.

The local review render is `pulse_layout.png`; the documentation copy is
[clock-pulse-generator-layout.png](../../../../../docs/images/clock-pulse-generator-layout.png).
The checked failing [schematic matrix](pulse_schematic_result.json), retained
[passing nominal PEX checkpoint](pulse_pex_nominal_result.json), full
[exact-PVT matrix](pulse_pex_pvt_result.json), and
[physical checkpoint](pulse_physical_checkpoint.json) keep circuit coverage,
nominal closure, PVT failure, and physical legality as separate claims.
The newer compact candidate has separate
[nominal](pulse_candidate_nominal_result.json) and
[hot-corner](pulse_candidate_hot_result.json) records. The former passes and
the latter explicitly fails, so neither overwrites the older checkpoint or
implies complete PVT closure.
Run `run_pulse_generator.sh` for the schematic matrix and
`run_pulse_physical.sh` for generation, render, DRC, LVS, full-RC extraction,
the nominal electrical gate, and the full PVT matrix. Expected failing matrices
are exported as evidence after the required nominal pass; interrupted or
structurally failed runs retain their complete work directory under `scratch/`.
`run_pulse_layout.sh` is the bounded geometry-only export path for quick,
reproducible Tcl/GDS generation; it does not replace DRC, LVS, or PEX.
