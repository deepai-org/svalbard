# Reference level receiver

This leaf converts one independently timed weak CMOS node into complementary
local rails by comparing it against an explicit `REF`.  It is the replacement
for applying the CML `clock_level_converter` outside that block's continuously
differential input contract.

The signal input sees one 8 µm NMOS gate.  A matched 8 µm reference device and
two-finger 12 µm programmable tail feed an 8 µm PMOS mirror.  A local gain
stage creates an internal phase, and two parallel output buffers prevent either
external load from appearing in the other output's control path.  There is no
cross-coupled regenerative state.

`run_screen.sh` checks 800 ps operation with a static midpoint reference over
five schematic PVT/input envelopes and the realizable six-code bias set 0.85,
0.90, 1.00, 1.08, 1.20, and 1.40 V.  The retained
`schematic_result.json` covers 5/5 environments.

`run_physical.sh` regenerates the compact matched layout, runs Magic DRC,
Netgen LVS, full-RC extraction, renders the cell, audits the generated-device
width/finger multiset against PEX, and repeats the calibrated screen.  Retained
evidence is zero-DRC, uniquely LVS-matched, parameter-matched, and extracts to
28 MOS devices, 389 resistors, and 172 capacitors.  `extracted_result.json`
covers 5/5 nominal environments with the same six codes.

`run_parent_envelope.sh` turns the routed-parent failure into a bounded exact-PEX
leaf matrix.  It checks eight candidate bias points against four profiles:
nominal, shortened SENSE assertion, measured capture source/load, and measured
asymmetric SENSE source/load.  Nominal covers 5/5 environments; each stressed
profile covers 4/5 and fails only SS/125 C.  At TT, capture and SENSE share a
passing 1.40 V code.  `parent_envelope_result.json` retains every profile and
case.  The v6 parent nevertheless leaves the SENSE OUTP nodes high, proving that
pulse width, lumped source resistance, and lumped output capacitance still do
not capture the relevant polarity, history, or internal-node trajectory.  The
next leaf contract must replay the measured parent waveform (or a bounded PWL
envelope), not only its scalar extrema.
