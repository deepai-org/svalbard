# Remaining transceiver risks

The active workflow is the [whole-chip behavioral model](../system_model/architecture_fast/README.md).
Full mathematical closure, the complete transistor schematic and layout remain
unfinished. This list supersedes earlier numbered experiment priorities.

## 1. Complete one connected system model

The largest architectural gap is uneven integration. Persistent host queues,
RF conversion, acquired waveform observers, wired recovery, USB pad behavior and
video lane coordination exist, but do not yet form one qualified lifecycle for
every required signaling class. Extend representative end-to-end paths from
external input through clocks/converters/pads and finite host transport to an
independent observer. Include startup, loss/recovery, retune and turnaround.

Acceptance requires actual payload identity and signal quality under declared
clock offsets, loading and disturbances. A fixture must not use transmitted
payload labels to acquire its receiver. Preserve expected failures and avoid
adding protocol names as a substitute for missing behavior.

## 2. Close RF quality gaps and quantify margin

The numeric sweep still contains failing BLE 2M, LoRa, gain, BR and proprietary
GFSK cases. Separate acquisition/observer failures from analog bandwidth,
noise and distortion limitations. Use realistic independent-source timing,
longer packets and blockers, with one shared live conversion/transport path.

HE20 BPSK success is limited evidence, not general Wi-Fi 6 qualification.
Multipole filter delay, frontend compression and supply-induced LO modulation
already matter in the model. Preserve bandwidth and declared quality budgets
when comparing alternatives; do not lower assumed noise just to obtain a pass.

## 3. Establish clock and electrical operating envelopes

Autonomous RF phase noise and wired PLL/CDR jitter remain major physical risks.
The behavioral CDR delivers recovered words across target rates, but uses an
idealized detector. Continuous startup fixtures now cover selected initial phase
and frequency offsets using a fixed training guard; lock qualification is still
missing. Holdover fixtures retain separate acquisition initialization. Test transition-poor
patterns, disturbances, slips and recovery with the connected payload path.
Forwarded-clock results still need complete multi-chip video alignment and
continuous service. USB requires full electrical startup/turnaround behavior.

Convert these tests into explicit required tuning, jitter, phase-noise and
settling budgets for transistor design. A fixed startup deadline or assumed
noise value does not prove GF180 can meet that requirement.

## 4. Bound whole-chip feasibility and implementation cost

RF/wired payload exclusivity reduces simultaneous activity but does not remove
host switching, reference loading or shared supply/package coupling. Average
power and allocated area are budgets, not physical evidence. Carry uncertain
regulator/package transfer, pad loading, converter linearity and host timing
through bounded sensitivity tests. Check that tunable filters, clocks, converters,
protection and digital transport still fit the die, terminal and current budgets.

Map numeric settings and feedback into a concrete generic control interface;
behavioral sidebands are not finished RTL. No validated RF/package data is
expected from the fab beyond public information and the open PDK.

## Stage gates

Finish the mathematical architecture before full transistor implementation;
finish the transistor/passive schematic and its verification before layout.
Then extract parasitics and rerun the same requirements. The
[closure inventory](mathematical-closure.json) owns the detailed gates and the
[analog workflow](analog-design-workflow.md) owns the six-family primitive approach.
Narrow supply/temperature operation is allowed, but does not resolve unknown
noise, parasitics or coupling. None of the current screens establishes physical
qualification or protocol compliance.
