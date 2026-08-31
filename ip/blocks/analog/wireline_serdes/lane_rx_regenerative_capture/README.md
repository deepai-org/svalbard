# Direct-regenerative RX capture parent

This physical parent contains the programmable differential termination, the
two-stage CML receiver, two independently clocked StrongARM-style decisions,
and independently clocked static differential capture. It deliberately removes
the separate data restorer and level-sensitive CML sampler that consumed the
timing budget in the earlier PI/RX hierarchy.

`layout.tcl` composes the real children and routes the bandwidth-critical RX
outputs directly into the adjacent converter input banks. The generated parent
is zero-DRC, uniquely LVS-matched, and full-RC extracted to 7,108 resistors and
4,348 capacitors. `lane_rx_regenerative_capture.pex.spice` is the exact PEX used
by the retained electrical evidence; `physical_result.json` binds it to the
layout, schematic, checker, and rendered image.

At 2.5 GT/s, a 150 ps static-capture pulse beginning 200 ps after the sense
event preserves a common two-UI held-output latency. The exact parent passes
5/5 representative environments over a 24-bit PRBS7 under 6 ohm/leg plus 1 pF
channel stress, 30 ps deterministic clock jitter, 47% duty cycle, and 20 mV
rail ripple. The external boundary is explicitly a **screen assumption**:
300 fF TX pad capacitance, 100 nF AC coupling, 2 ohm and 1 nH per package leg,
500 fF RX pad capacitance, and 2 kohm RX bias returns. It is not a qualified
pad/ESD, bond, package, board, or connector model. The worst five-environment
values are 104.038 mV at the pin,
92.541 mV at the actual sampler input, 2.37717 V at the write point, 2.54706 V
at the held output, and 44.6612 mA maximum testbench supply current. A separate
SS/125 C aperture run passes all five offsets from 0 through 200 ps.

Run `./run_physical.sh` to regenerate DRC/LVS/PEX. Run the lane-level
`run_capture_2p5_regenerative_pvt.sh` and
`run_capture_2p5_regenerative_ss_aperture.sh` for electrical replay, then run
`./check_evidence.py` to bind the promoted evidence. This is pre-silicon public-
model evidence, not PCIe compliance or provider signoff. The pulse generator,
PI/clock-restorer composition, statistical noise/mismatch/metastability,
pad/package/channel EM, substrate/PDN coupling, post-fill extraction, and
reliability remain open.
