# Experimental GF180 CML transmitter

This directory contains a real transistor-level differential transmitter cell, not a behavioral placeholder. Two salicided p-poly load resistors feed a matched 10-finger NMOS differential pair and a 10-finger NMOS tail-current device. `VBIAS` is an external analog control; 1.07 V selects about 4.14 mA in the public GF180 typical model used here.

`layout.tcl` generates and routes GF180 parameterized devices, creates the common p-well and substrate tap, labels the seven interface pins, and emits MAG/GDS into disposable scratch. The bounded flow runs bias characterization, pre-layout ngspice, Magic DRC, Netgen LVS, coupling-capacitance extraction, extracted ngspice at 1.25 and 2.5 GT/s, and an actual GDS render.

Run it with:

```sh
make serdes-tx-smoke
```

Passing evidence is written to `scratch/serdes-tx-last.json`; the inspected layout image is `scratch/serdes-tx-layout-last.png`. These are experimental pre-silicon public-model results. They are not PCIe compliance, PVT, package/channel, reliability, or foundry qualification evidence.
