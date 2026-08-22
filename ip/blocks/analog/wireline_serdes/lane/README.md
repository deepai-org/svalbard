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
the provisional external clock and channel. A longer PRBS scoreboard,
channel-loss/jitter sweeps, simultaneous-supply aggression, and a selected
pad/ESD/package/channel remain next.
