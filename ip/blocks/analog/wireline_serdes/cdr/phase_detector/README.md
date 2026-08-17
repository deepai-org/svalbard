# Experimental GF180 half-rate Alexander phase-detector boundary

This block implements one Alexander boundary from three differential sampler
decisions. Two stacked CML XOR cells produce `EARLY = PREV xor EDGE` and
`LATE = EDGE xor CUR`. A complete half-rate CDR uses the corresponding
interleaved boundaries and consumes these raw outputs in the loop filter; this
cell is the transistor-level phase-comparison primitive, not a complete CDR.

Each XOR uses a differential lower selector, crossed upper differential pairs,
matched unsalicided p-poly loads, and a programmable shared tail-bias voltage.
The 0.45--1.15 V search range uses 50 mV candidate spacing in simulation. The
eventual bias generator and calibration controller must implement and retain
the selected setting; programmability does not make calibration automatic.

The schematic evidence matrix checks both Boolean equations at 2.5 GT/s with
20 ps input edges, 280 mV differential inputs, 25 fF on each output, three MOS
corners, three resistor corners, 2.97/3.30/3.63 V supplies, -40/27/125 C, and
0.60/0.70/0.80 supply-scaled input common-mode. All 3,645 simulations complete
and all 243 environments calibrate. Every environment retains 4--8 passing
bias codes; selected-code worst signed output margin is 146 mV, current is
0.797--1.830 mA for both XORs, and EARLY/LATE selected-margin mismatch is at
most 39 uV in the symmetric schematic.

Run the bounded, digest-pinned reproduction with:

```sh
make cdr-phase-detector-schematic
```

This is schematic-level public-model evidence. Compact matched layout,
DRC/LVS, full-RC extraction, sampler loading, phase/jitter behavior, supply
injection, mismatch, loop dynamics, and independent-simulator correlation are
still open and no PCIe compliance or silicon-performance claim is made.
