# Reference level receiver

This leaf converts one independently timed weak CMOS node into complementary
local rails by comparing it against an explicit `REF`.  It is the replacement
for applying the CML `clock_level_converter` outside that block's continuously
differential input contract.

The signal input sees one 4 µm NMOS gate.  A matched 4 µm reference device and
12 µm programmable tail feed a PMOS mirror; a minimum-load isolation inverter
then drives a local taper.  There is no cross-coupled regenerative state.

`run_screen.sh` checks 800 ps operation with a static midpoint reference over
five schematic PVT/input envelopes.  The retained `schematic_result.json`
passes 5/5 at 1.15 V bias: duty spans 36.02--55.18%, cyclic complementary skew
is at most 161.58 ps against a declared 200 ps capture-boundary limit, and
average supply current is 1.46--2.15 mA.  This is schematic evidence only.

The next mandatory gate is a compact matched layout with dummies/taps, zero
DRC, unique LVS, full-RC PEX, and the same five-case screen.  Only then may the
four instances replace the physically closed but dynamically failed v4 parent
experiment.
