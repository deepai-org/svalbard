# Routed PI-to-RX capture parent

This parent places the extracted phase interpolator and a two-stage CML clock
restorer beside the routed termination/RX/restorer/sampler/converter/capture
hierarchy. It owns the differential clock routes into both sampler latches.
The checked-in layout is zero-DRC, uniquely LVS-matched, and full-RC extracted
to 8,625 resistors and 5,034 capacitors. The physical checker also requires the
schematic and extracted SPICE port orders to match exactly.

The direct PI-to-sampler experiment failed because the PI's former 50 fF load
did not represent four nonlinear 8 um x m2 sampler clock gates. The extracted
PI -> two-stage restorer -> dual sampler chain passes 4/4 restorer-bias points.
At the selected 1.15 V restorer bias it produces about +2.19/-2.19 V
differential clock extrema; the measured rising edge is 312.65 ps after the A
input's rising edge for equal PI controls.

The former smoke failure was caused by observing the output while the capture
write pulse was still active. With a 550 ps event-relative opening, 380 ps
write pulse, and 1050 ps observation, the capture has 120 ps to regenerate and
300 ps before its next same-lane opening. The exact parent passes a 24-bit
PRBS7 at adjacent 200 and 300 ps conversion offsets in an eight-point nominal
screen. The selected 200 ps case retains 98.071 mV raw-RX, 367.009 mV restored,
671.376 mV sampler, 400.615 mV converter, and 1.5155 V final-capture margin at
50.815 mA. Restored-clock rise/fall times are measured directly in every case.

This does not close PVT. Corrected per-lane qualification and write-time
scoring passes 3/5 exact-parent environments: TT, FF/cold, and SS/passive.
FF/hot reaches 199/221 mV worst signed write margin on the two lanes, with one
polarity wrong, despite 932 mV/2.048 V final held outputs. SS/hot is weaker:
the even converter reaches only 57 mV at qualification and 61 mV at write,
then both final outputs remain within 10 mV of an invalid decision. Clock-edge
skew, larger sampler loads, tail boost, and independent lane delays were useful
diagnostics but did not produce a common correct window. Delaying the even
conversion by 400 ps makes its output strong only by capturing the same serial
bit as the odd lane. The physical converter's 700--900 ps useful window is
therefore structurally incompatible with a 400 ps serial UI at this boundary.

A separate StrongARM-style replacement now passes 10/10 targeted exact-PEX
contract environments with one 800 ps lane-cycle pipeline latency, a fixed
120 ps qualification point, 546.42 mV minimum logic margin, and 9.964 mA
maximum average current for 200 mV differential input and 50 fF output loading.
Its 190 x 160 um layout is zero-DRC, uniquely LVS-matched, and extracted to
2,172 resistors and 1,311 capacitors. It is not yet substituted into this
parent. The next physical task is to rebuild this exact routed hierarchy with
both fast instances before any PVT-closed PI-clocked lane is claimed.

Run `./run_physical.sh` for layout/DRC/LVS/PEX, `./run_clock_chain.sh` and
`./run_clock_chain_ss.sh` for nonlinear clock-load checks, and the lane
`run_capture_2p5_rx_pi_screen.sh` or `run_capture_2p5_rx_pi_pvt.sh` for composed
transients. Generated logs and waveforms remain in scratch; the committed JSON
records bind the exact parent PEX, physical record, testbench, and runner.
