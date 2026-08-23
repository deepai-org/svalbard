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

The complete 2.5 GT/s smoke is intentionally retained as a failing integration
result. After correcting a positional PEX port-order error, inverting the
quadrature polarity, and raising sampler bias to 1.3 V, the exact parent reaches
the following minimum boundaries under the combined channel/jitter/duty/ripple
stress:

- sampler differential margin: at least 0.73 V;
- sampler common mode: approximately 2.53--2.60 V;
- CML-to-CMOS output margin: at least 0.42 V;
- even final capture: at least 1.72 V;
- odd final capture: about 0.41 V, below the 0.50 V contract.

Timing extension peaked with a -200 ps odd-capture skew and 500 ps odd pulse;
stretching farther reduced margin. The next circuit task is therefore to
rebalance or strengthen the odd capture branch, then replay the 24-bit offset
screen and representative PVT. This milestone does not claim a passing routed
PI-to-parallel-data path.

Run `./run_physical.sh` for layout/DRC/LVS/PEX, `./run_clock_chain.sh` for the
nonlinear clock-load screen, and the lane `run_capture_2p5_rx_pi_smoke.sh` or
`run_capture_2p5_rx_pi_screen.sh` for composed transients. Generated logs and
waveforms remain in scratch; the committed JSON records bind the exact PEX.
