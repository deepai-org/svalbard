# Reference level receiver

This leaf converts one independently timed weak CMOS node into complementary
local rails by comparing it against an explicit `REF`.  It is the replacement
for applying the CML `clock_level_converter` outside that block's continuously
differential input contract.

The signal input sees one 8 µm NMOS gate.  A matched 8 µm reference device and
two-finger 12 µm programmable tail feed an 8 µm PMOS mirror.  A local taper
drives complementary 100 fF loads; its final PMOS devices use two 8 µm fingers
to retain drive at the slow/hot boundary.  There is no cross-coupled
regenerative state.

`run_screen.sh` checks 800 ps operation with a static midpoint reference over
five schematic PVT/input envelopes and the realizable six-code bias set 0.85,
0.90, 1.00, 1.08, 1.20, and 1.40 V.  The retained
`schematic_result.json` covers 5/5 environments.

`run_physical.sh` regenerates the compact matched layout, runs Magic DRC,
Netgen LVS, full-RC extraction, renders the cell, audits the generated-device
width/finger multiset against PEX, and repeats the calibrated screen.  Retained
evidence is zero-DRC, uniquely LVS-matched, parameter-matched, and extracts to
20 MOS devices, 327 resistors, and 128 capacitors.  `extracted_result.json`
covers 5/5 environments with the same six codes.  The limiting SS/125 C case
passes at 1.08 V with 50.13% duty, 181.58/183.31 ps complementary edge skew,
2.742 V highs, 0.202 V lows, and 2.03 mA average supply current.

The next boundary is substitution of four physical instances into the routed
event parent, followed by parent DRC/LVS/PEX and exact TT PRBS qualification.
