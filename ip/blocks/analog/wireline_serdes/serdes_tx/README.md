# Experimental GF180 CML transmitter

This directory contains a real transistor-level differential transmitter cell, not a behavioral placeholder. Mirrored unsalicided p-poly load banks feed a matched 10-finger NMOS differential pair and a 10-finger NMOS tail-current device. Each side has one always-on resistor and four identical active-low, PMOS-switched trim branches. The common thermometer code changes load resistance while `VBIAS` changes tail current; the nominal four-branch, 1.20 V point is selected from extracted simulation rather than assumed from schematic-only current.

![Generated GF180 CML transmitter layout](layout.png)

`layout.png` is a directly usable raster rendering of the generated GDS: the mirrored trim banks and compact outer base resistors are above the adjacent differential pair, with the centered tail device and contacted substrate guard ring below.

`layout.tcl` generates and routes GF180 parameterized devices, places the pair banks adjacently with distributed gate contacts, puts the tail directly beneath the shared-source rail, keeps the matched output trunks on metal3 at the outer drain edges, adds redundant via transitions, explicit PMOS well taps, and a continuously contacted substrate guard ring, labels the eleven interface pins, and emits MAG/GDS into disposable scratch. The bounded flow runs bias characterization, pre-layout ngspice, Magic DRC, Netgen LVS, full coupled-RC extraction down to 1 mOhm, extracted ngspice at 1.25 and 2.5 GT/s, and an actual GDS render.

Run it with:

```sh
make serdes-tx-smoke
```

Passing nominal evidence is written to `scratch/serdes-tx-last.json`; the inspected layout image is `scratch/serdes-tx-layout-last.png`. `run_programmable_pvt.py` separately searches load code and bias over MOS, resistor, voltage, and temperature corners using either schematic or full-RC extracted netlists. These are experimental pre-silicon public-model results. They are not PCIe compliance, package/channel, reliability, or foundry qualification evidence; the pad/ESD boundary is still unmodeled.

The current full-RC matrix passes all 135 core combinations (five MOS corners, three resistor corners, three temperatures, and three supplies). Across those calibrated 2.5 GT/s cases, sampled differential magnitude is 0.522--0.621 V, threshold crossing is 17.0--26.8 ps, average supply current is 5.34--7.43 mA, and the minimum output floor is 2.045 V. The separate pad-boundary ceiling check fails all 135 cases because the standalone ideal-edge/50 fF environment has no selected pad, ESD clamp, or package model; its worst overshoot is 4.23 V. This failure is retained rather than treated as core qualification.
