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

This does not close PVT. The full five-environment replay passes only nominal.
At FF/cold the sampler and converter retain at least 0.811 V and 2.327 V, but
post-write capture collapses below 2 mV: this is a real regeneration failure,
not an aperture setting. FF/hot passes the short diagnostic after raising
sampler bias to 1.3 V but fails the 24-bit recurrence test. Both SS cases lose
dynamic decisions even though the standalone extracted PI/restorer/sampler
clock chain passes 4/4 restorer biases at SS/passive. The next circuit task is
to strengthen and requalify held-state capture and then localize the SS dynamic
data/clock boundary; no PVT-closed lane is claimed.

Run `./run_physical.sh` for layout/DRC/LVS/PEX, `./run_clock_chain.sh` and
`./run_clock_chain_ss.sh` for nonlinear clock-load checks, and the lane
`run_capture_2p5_rx_pi_screen.sh` or `run_capture_2p5_rx_pi_pvt.sh` for composed
transients. Generated logs and waveforms remain in scratch; the committed JSON
records bind the exact parent PEX, physical record, testbench, and runner.
