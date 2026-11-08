# Transceiver block diagram

[Full SVG](transceiver-block-diagram.svg) · [PNG preview](transceiver-block-diagram.png)

The diagram describes the selected architecture in
[analog-architecture.json](../../spec/analog-architecture.json). It places RF west,
wired east, clocks north and host/digital services south. The compatible 74-site
ring contains 37 functional signals, 18 fixed supply/return sites and 19 spare
signal sites. REF_IN/REF_IN_N is one differential port.

This is intended connectivity and approximate placement, not a transistor
netlist or a scaled physical layout. RF and wired payloads are exclusive per die.
Shared resources must preserve TX/RX functions within the selected engine.
Protocol names describe external uses, not chip configuration selectors.

Differential conductors and words are bundled. Named services describe separate
bias, clock, power and control connections, not one electrical node. See the
[architecture specification](../../spec/block-diagram.md) for the complete
connection inventory and implementation requirements, and the
[pad implementation](../../analog/pads/README.md) for current circuit boundaries.

## Regenerate

From the repository root:

```sh
python3 projects/programmable_transceiver_platform/docs/diagrams/generate_normative_diagram.py
rsvg-convert -w 2000 projects/programmable_transceiver_platform/docs/diagrams/transceiver-block-diagram.svg -o projects/programmable_transceiver_platform/docs/diagrams/transceiver-block-diagram.png
```

The generator reads the architecture inventory and updates the SVG and the
specification's connection table. Use `--check` to verify consistency without
rewriting files. After visual changes, inspect the rendered diagram for overlap,
clipped labels and ambiguous connections.
