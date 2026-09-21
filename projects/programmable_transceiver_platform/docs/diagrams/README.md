# Programmable transceiver circuit-block schematic

![Full-chip circuit-block schematic](transceiver-block-diagram.svg)

[Open SVG](transceiver-block-diagram.svg) · [PNG preview](transceiver-block-diagram.png)

The diagram uses explicit gain stages, I/Q mixers, summing nodes, integrators, sample switches/capacitors, comparators, filters and converter symbols. PLL feedback and wired CDR paths are drawn explicitly. Analog I and Q channels and their digital buses remain separate.

It retains approximate physical neighborhoods: RF west, wired east, synthesizers north and digital transport south. All 50 terminals are grouped at the perimeter. This is an intended circuit-block schematic, not a transistor netlist, scaled floorplan or proof of implemented area. Differential pairs are represented by one line; matching signal/clock labels connect nets. Digital services remain functional blocks. Shared bias and control fanout is omitted for readability.

The visual abstraction follows the user's [signal-flow diagram reference](https://www.inf.u-szeged.hu/~gingl/achievements/SRDW/block.PNG), with original transceiver-specific content. Local tile configurations are representative supported intentions, not a claim of a universal analog crossbar. Filters, converter internals and local regulation still require circuit selection and qualification.

Regenerate and render from the repository root:

```sh
python3 projects/programmable_transceiver_platform/docs/diagrams/generate_block_diagram.py
rsvg-convert -w 2000 projects/programmable_transceiver_platform/docs/diagrams/transceiver-block-diagram.svg -o projects/programmable_transceiver_platform/docs/diagrams/transceiver-block-diagram.png
```

The rendered image was visually inspected for label fit, distinct I/Q nets, CDR feedback and separation of digital routing from reference circuitry.
