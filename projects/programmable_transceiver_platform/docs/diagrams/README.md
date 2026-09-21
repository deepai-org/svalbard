# Programmable transceiver block diagram

![Full-chip block diagram](transceiver-block-diagram.svg)

[Open SVG](transceiver-block-diagram.svg) · [PNG preview](transceiver-block-diagram.png)

This is the intended analog/PHY companion arranged approximately as physical blocks might sit on the finished chip: RF at the west edge, wired PHY at the east, reference and PLL circuits at the north, and host I/O and digital transport at the south. I/Q converters sit between RF baseband and digital logic, beside their reference buffers. All 50 terminals are grouped at the edges.

The die and nominal core use the planned aspect ratios. Block areas, custom pad-ring fit, package pin order and isolation remain unverified. This is a placement-informed circuit-block diagram, not a completed physical layout. Solid arrows show selected data paths; dashed paths show selected clocks/references. Shared fanout is omitted for legibility.

The SVG was rendered and visually inspected. Re-render from the repository root:

```sh
rsvg-convert -w 1800 projects/programmable_transceiver_platform/docs/diagrams/transceiver-block-diagram.svg -o projects/programmable_transceiver_platform/docs/diagrams/transceiver-block-diagram.png
```
