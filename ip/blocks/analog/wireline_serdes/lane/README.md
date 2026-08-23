# Externally clocked wireline lane composition

This is the first explicit composition of the selected integrated half-rate TX
with an AC-coupled package boundary, receiver common-mode return, programmable
differential termination, limiting amplifier, and dual-edge sampler.  The
initial rate is 1.25 GBd.  This is a bounded integration experiment, not a PCIe
pad, channel, compliance, or tapeout claim.

The provisional low-loss boundary deliberately names every currently modeled
element: 300 fF TX and 500 fF RX capacitance per pin, 100 nF external AC
coupling, 2 ohm and 1 nH package series parasitics per leg, 2 kohm receiver bias
returns, and the transistor-level programmable differential termination.  A
selected pad/ESD model and measured channel family must replace this boundary
before architecture freeze.

`run_lane.py` drives a changing 24-bit pattern, sweeps external sampler phase,
and independently measures signed TX, receiver-pin, amplifier, and held-sampler
margins.  A pass therefore cannot be created by checking only the final node.

Run `./run_schematic.sh` for the nominal transistor-level phase sweep. Run
`./run_extracted.sh` to regenerate and check the termination, amplifier, and
sampler layouts, perform full-RC extraction, and compose those fresh netlists
with the selected full-RC integrated serializer/TX.

## Current extracted evidence

The nominal full-RC-leaf composition completes all 16 phase cases and passes
13. The best 135 degree phase retains 259.8 mV signed pin margin, 300.4 mV
amplifier margin, and 1.345 V held-sampler margin at 12.46 mA shared supply
current. The three failing phases from 180 through 225 degrees are retained as
the observed wrong-aperture region rather than discarded.

The same 135 degree phase passes all five representative MOS/resistor/supply/
temperature environments using the already selected per-environment TX bias
and fixed RX bias, sampler bias, and interior termination code. Across that
matrix, minimum pin, amplifier, and held-sampler margins are respectively
225.8 mV, 124.0 mV, and 305.0 mV; shared supply current is 9.82--16.13 mA.

Fresh geometry evidence is bound to the composed netlists: the termination,
amplifier, and sampler each have zero Magic DRC errors, one unique pin-resolved
LVS match, and respectively 545R/276C, 442R/169C, and 480R/193C full-RC
extractions. The serializer/TX uses its selected committed full-RC extraction.

The sampler boundary is now extended through two exact-PEX CML-to-CMOS
converters and the independently clocked exact-PEX dual capture cell. All four
0--300 ps conversion offsets pass nominally, and the selected offset passes all
five representative environments. Worst converter/capture signed margins are
2.371/2.363 V and total composed current is 23.05--34.49 mA.
The physical, nominal, and PVT records bind the same exact split-capture PEX;
the preserved deck and matching image are
`scratch/serdes-lane-capture-deserializer-last.pex.spice` and
`scratch/serdes-lane-capture-layout-last.png`.

This closes deterministic changing-word transfer to stable parallel CMOS under
the provisional external clock and channel.

`./run_capture_stress.sh` reuses one freshly checked extraction stack for four
64-bit PRBS7-prefix cases, scoring 28 even/odd pairs (56 serial bits) after
startup in each case. All four exact-PEX cases pass: baseline; a symmetric
two-section channel proxy with 6 ohms series resistance per leg and 1 pF total
differential shunt capacitance; 40 ps peak deterministic TX-edge jitter with a
47% TX-clock duty cycle; and the channel proxy combined with 30 ps peak jitter
and 47% duty. Across 224 scored serial bits, the worst converter and retained
CMOS margins are 2.975 V and 3.165 V, and current is 27.11--27.14 mA.

`capture_stack.sh` is the shared container-side primitive for both capture
flows. It regenerates the termination, RX, sampler, converter, and split-capture
views once, runs physical checks on the exact split-capture PEX, and exports one
canonical argument vector so nominal, PVT, and stress flows cannot quietly use
different leaf paths.

For a matched 100-ohm differential reference, the declared RC proxy's ABCD
network evaluates to approximately 0.68 dB insertion loss at the 625 MHz
Nyquist frequency and 1.16 dB at 1.25 GHz. This is an explicit bounded lumped
stress, not a transmission-line, return-loss, or selected-channel claim. A
denser impairment/PVT matrix, simultaneous-supply aggression, and selected
pad/ESD/package/S-parameter models remain next.

## Combined extracted stress and data restoration

The denser matrix now measures every scored TX, receiver pin, receiver output,
sampler input, CML-to-CMOS output, and retained CMOS output. An initial 5-case
run with 7 ohms/leg and 1.25 pF localized the failure to receiver dynamic
margin. A one-factor screen showed that 30 ps peak jitter, 47% duty cycle, and
20 mV peak 100 MHz supply ripple each passed at the limiting slow/passive
environment; the provisional RC channel was the controlling mechanism. The
6-ohm/leg plus 1-pF point is the selected bounded proxy. The observed
7-ohm/leg plus 1.25-pF failure preceded the data-restorer redesign, so it is
mechanism evidence, not a post-redesign channel limit or guardband claim.

The original receiver output could still produce correct final data but fell
below the sampler's independently qualified 200 mV input contract. Reusing the
physical 7.5-um-load clock restorer failed arbitrary PRBS settling, so a new
two-stage 4.5-um-load `data_restorer` was laid out, checked, and extracted. Its
exact PEX passes at adjacent 67.5 and 90 degree sampler phases in the limiting
environment; 78.75 degrees is selected between them. Mixed process/passive
corners use restorer bias codes supported by adjacent-code screens rather than
waiving the interface floor.

The permanent calibration targets are `run_capture_restorer_sweep.sh` for the
final-geometry phase window, `run_capture_restorer_ff_bias.sh` for the
fast-device/slow-passive corner, and `run_capture_restorer_ss_bias.sh` for the
slow-device/fast-passive corner. They share the exact extraction stack,
stimulus runner, and parameterized fail-closed evidence merger.

`./run_capture_stress_pvt.sh` now passes 5/5 representative environments and
160/160 scored serial bits with one exact extraction stack under simultaneous
6-ohm/leg plus 1-pF channel stress, 30-ps peak deterministic TX jitter, 47%
duty cycle, and 20-mV peak 100-MHz rail ripple. Worst signed margins at the TX,
pin, raw RX, restored sampler input, converter, and final capture are
78.681/147.603/50.674/230.118/2578.62/2733.72 mV. Total composed current is
26.383--41.442 mA. This closes the bounded low-loss proxy matrix; it does not
close mismatch, substrate/PDN coupling, 2.5 GT/s, or the selected physical I/O
and channel.
