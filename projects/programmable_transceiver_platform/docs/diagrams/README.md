# Transceiver circuit-block diagrams

[Full SVG](transceiver-block-diagram.svg) · [PNG preview](transceiver-block-diagram.png) ·
[Loaded RF detail](transceiver-rf-loaded-detail.svg) ·
[Multi-chip video detail](transceiver-video-detail.svg)

The overview places RF west, wired east, clocks north and host/digital services
south, with all 50 terminals grouped at the perimeter. Detailed sheets expand
amplifiers, mixers, filters, converters, reference/bias services, PLL/CDR feedback,
host queues, calibration and power connections. This is intended connectivity
and approximate placement, not a transistor netlist or a scaled physical layout.

RF and wired payloads are exclusive per die. Behavioral ownership and handovers
are tested; physical/RTL interlocks and resource-sharing implementation remain
open. Shared resources must preserve TX/RX functions within the selected engine.
Protocol names label external uses, not chip configuration selectors.

The video sheet is a board assembly of three identical single-lane chips with
external clock conversion/fanout. It includes fractional x10 video references;
it does not enlarge the single-die floorplan. HD-SDI requires an external coax
interface. See the [interface plan](../../../../docs/roadmap/programmable-transceiver-pin-plan.md)
for target scope and the [architecture specification](../../spec/block-diagram.md)
for implementation gaps.

## Reading the wiring

Differential pairs are bundled in the overview and expanded into P/N conductors
on detailed sheets. Junction dots denote connections; crossings without dots
are independent. Named nets join sheets without adding package terminals.
Service bundles represent distinct configuration, bias and supply connections,
not one electrical node. Repeated I/Q circuits are separate instances.

The loaded-RF sheet expands output isolation/dummy loading, the pre-switch
monitor, shared I-channel diagnostic ADC and fifth-order receiver filtering.
The diagnostic path temporarily owns the I-channel ADC. These are circuit
candidates; switch timing, conditioning, references and parasitics need schematic
and extracted verification. No diagram establishes physical qualification.

## Regenerate

From the repository root:

```sh
python3 projects/programmable_transceiver_platform/docs/diagrams/generate_block_diagram.py
rsvg-convert -w 2000 projects/programmable_transceiver_platform/docs/diagrams/transceiver-block-diagram.svg -o projects/programmable_transceiver_platform/docs/diagrams/transceiver-block-diagram.png
```

The generator produces the full SVG and both focused SVGs from the same drawing.
Use `rsvg-convert` on a focused SVG for a readable local preview. Inspect rendered
changed sheets for overlap, clipped labels and ambiguous junctions; XML validity
alone does not establish readable wiring.
