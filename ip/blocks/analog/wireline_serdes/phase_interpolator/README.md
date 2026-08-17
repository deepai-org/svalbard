# Experimental GF180 CML phase interpolator

This directory contains a transistor-level two-input CML phase interpolator for the reference-assisted 2.5 GT/s sampling milestone. Two adjacent 1.25 GHz differential reference phases drive matched current-steering pairs; `CTRL_A` and `CTRL_B` select their relative tail currents, and a local CML buffer isolates the summed node from the sampling-clock load.

![Generated GF180 phase-interpolator layout](layout.png)

`layout.png` is a directly usable 1600 x 1200 rendering of the generated 65 x 56 um GDS. The A/B input devices form an equal-centroid quartet at left, the programmable tail devices sit directly below them, the restoring buffer is at right, and the perimeter includes explicit substrate contacts. Signal, source, and control routes use separate upper-metal tracks where crossings require them.

The current physical checkpoint is Magic DRC-clean, matches the transistor-level schematic uniquely in Netgen LVS, and has a coupled full-RC extraction containing 356 resistors and 137 capacitors. All 15 nominal extracted control candidates simulate successfully; they span 199.44 ps, with 589--730 mV differential swing and 2.81--3.18 mA supply current. Codes 0, 4, 7, 10, and 14 place the five nominal target phases within 3.7 ps.

The analog controls provide calibration range for unknown silicon, temperature, supply, and extracted-interconnect behavior. They do not determine their own settings: integration still needs a phase detector or reference measurement, a calibration search, and retained control codes. Full schematic and extracted PVT calibration matrices are the next closure gate for this experimental checkpoint.

This is pre-silicon public-model evidence, not a PCIe-qualified clocking macro. It still needs statistical mismatch with provider-approved models, supply-noise/jitter sensitivity, clock-tree and sampler co-simulation, post-fill extraction, EM/IR and reliability review, and silicon correlation before freeze.
