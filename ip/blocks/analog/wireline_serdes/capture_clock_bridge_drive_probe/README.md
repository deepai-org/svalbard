# PCIe capture-clock bridge pull-up screen

This is a narrow, schematic-only parameter screen for the current FF/cold
capture-clock rail loss. It holds the current exact extracted capture cell and
200-ps ideal WRITE boundary fixed, then sweeps only the final bridge inverter's
PMOS multiplicity. The result determines whether a larger physical bridge
output stage is worth considering; it cannot repair SS/hot's missing pulse,
substitute for the real pulse producer, or close the composed PCIe lane.

```sh
./run_probe.sh
```

The current result is bound in
[`drive_probe_result.json`](drive_probe_result.json). The baseline and 2x
final PMOS both pass all five isolated consumer cases; 3x and above regress
clock skew. In particular, baseline FF/cold reaches 3.726/3.724 V at the
capture clocks, whereas the composed parent reaches only 3.311/3.296 V.
Larger bridge pull-up is therefore rejected before layout; the active owner is
the actual pulse/WRITE waveform and producer-to-consumer composition.
