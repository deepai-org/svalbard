# Experimental integrated half-rate Alexander detector

This assembly connects two transistor-level dual-edge CML samplers to two
interleaved Alexander phase-detector boundaries. The data sampler uses the
center clock. The edge sampler uses a phase-trimmed clock and supplies the
transition decisions between adjacent data decisions. Boundary zero evaluates
odd-data/odd-edge/even-data; boundary one evaluates
even-data/even-edge/next-odd-data.

The integration test consumes each boundary only after its final data decision
has settled. Averaging continuously across a clock period is invalid because
the three held decisions update at different instants. A future retimer or
loop-filter interface must preserve these two explicit valid windows.

The coordinated schematic search covers nine representative combinations of
MOS corner, unsalicided-resistor corner, 2.97--3.63 V supply, -40--125 C, and
0.60--0.80 supply-scaled input common-mode. It searches five sampler-bias codes
and seven edge-phase settings. One setting must remain fixed while alternating
2.5 GT/s transitions move by -80, -40, +40, and +80 ps. The +/-40 ps points
require at least 100 mV directional EARLY/LATE margin and the +/-80 ps
guardband points require at least 75 mV, measured in both interleaves over
three consecutive valid windows.

All 1,260 simulations complete and all 9/9 environments calibrate. Each retains
2--15 valid joint settings. Selected sampler bias spans 0.90--1.30 V, selected
edge-clock phase spans -146.25 to -101.25 degrees, and selected worst-case
directional margin is 355 mV--1.73 V. This proves coordinated static
calibration of the transistor-level front end; it does not prove acquisition,
tracking, jitter tolerance, or closed-loop stability.

Run the bounded, digest-pinned reproduction with:

```sh
make cdr-integrated-detector-schematic
```

The sampler and phase-detector primitives have independent DRC/LVS/full-RC
physical closure. This integration checkpoint is schematic-level. Hierarchical
top-level interconnect extraction, valid-window retiming, loop filtering,
closed-loop CDR behavior, statistical metastability/mismatch, clock-tree
loading, and PLL coupling remain open.
