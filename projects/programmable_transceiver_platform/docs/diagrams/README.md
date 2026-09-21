# Programmable transceiver circuit-block schematic

![Full-chip circuit-block schematic](transceiver-block-diagram.svg)

[Open SVG](transceiver-block-diagram.svg) · [PNG preview](transceiver-block-diagram.png)

The diagram uses explicit gain stages, I/Q mixers, summing nodes, integrators, sample switches/capacitors, comparators, filters and converter symbols. PLL feedback and wired CDR paths are drawn explicitly. Analog I and Q channels and their digital buses remain separate.

It retains approximate physical neighborhoods: RF west, wired east, synthesizers north and digital transport south. All 50 terminals are grouped at the perimeter. This is an intended circuit-block schematic, not a transistor netlist, scaled floorplan or proof of implemented area. Differential pairs are represented by one line; signal, clock, reference, diagnostic and host connections are drawn. Digital services remain functional blocks. Panel service ports represent bundled configuration/bias and domain supply distribution to enclosed circuits. The bundles are not single electrical nodes.

The visual abstraction follows the user's [signal-flow diagram reference](https://www.inf.u-szeged.hu/~gingl/achievements/SRDW/block.PNG), with original transceiver-specific content. Local tile configurations are representative supported intentions, not a claim of a universal analog crossbar. Filters, converter internals and local regulation still require circuit selection and qualification.

Regenerate and render from the repository root:

```sh
python3 projects/programmable_transceiver_platform/docs/diagrams/generate_block_diagram.py
rsvg-convert -w 2000 projects/programmable_transceiver_platform/docs/diagrams/transceiver-block-diagram.svg -o projects/programmable_transceiver_platform/docs/diagrams/transceiver-block-diagram.png
```

The rendered image was visually inspected for distinct I/Q wiring, CDR/PLL feedback, converter-reference and sampling connections, host return direction, service-bus junctions and readable routes. Junction dots denote connections; crossings without dots are independent. The selected diagnostic route is a proposed bounded topology, not implemented analog switching or a global crossbar.
