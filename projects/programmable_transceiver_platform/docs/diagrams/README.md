# Programmable transceiver circuit-block schematic

**Latest design:** RF and wired payload operation are mutually exclusive. The final policy sheet shows mode ownership, switching sequence and sharing priorities; earlier separate-island drawings do not mandate duplicated resources. See [the operating decision](../../spec/exclusive-engine-policy.md).

[Focused loaded-RF SVG](transceiver-rf-loaded-detail.svg) · [PNG](transceiver-rf-loaded-detail.png) shows the shared pad/monitor/dummy network, relative-gain calibration, loaded-pad loopback and fifth-order receiver filter. The complete SVG and PNG include this sheet. Regeneration produces both SVGs; render the focused SVG with `rsvg-convert` as above. Both new sheets were rendered and visually checked; the reference route was corrected to avoid crossing a filter block. Model/RTL enforcement of exclusive modes remains pending.

![Full-chip circuit-block schematic](transceiver-block-diagram.svg)

[Open SVG](transceiver-block-diagram.svg) · [PNG preview](transceiver-block-diagram.png)

The diagram uses explicit gain stages, I/Q mixers, summing nodes, integrators, sample switches/capacitors, comparators, filters and converter symbols. PLL feedback and wired CDR paths are drawn explicitly. Analog I and Q channels and their digital buses remain separate.

It retains approximate physical neighborhoods: RF west, wired east, synthesizers north and digital transport south. All 50 terminals are grouped at the perimeter. This is an intended circuit-block schematic, not a transistor netlist, scaled floorplan or proof of implemented area. Differential pairs are bundled in the overview and expanded into separate P/N conductors in the detailed sheets; signal, clock, reference, diagnostic and host connections are drawn. Digital services remain functional blocks. Panel service ports represent bundled configuration/bias and domain supply distribution to enclosed circuits. The bundles are not single electrical nodes.

The visual abstraction follows the user's [signal-flow diagram reference](https://www.inf.u-szeged.hu/~gingl/achievements/SRDW/block.PNG), with original transceiver-specific content. Local tile configurations are representative supported intentions, not a claim of a universal analog crossbar. Filters, converter internals and local regulation still require circuit selection and qualification.

Regenerate and render from the repository root:

```sh
python3 projects/programmable_transceiver_platform/docs/diagrams/generate_block_diagram.py
rsvg-convert -w 2000 projects/programmable_transceiver_platform/docs/diagrams/transceiver-block-diagram.svg -o projects/programmable_transceiver_platform/docs/diagrams/transceiver-block-diagram.png
```

The rendered image was visually inspected for distinct I/Q wiring, CDR/PLL feedback, converter-reference and sampling connections, host return direction, service-bus junctions and readable routes. Junction dots denote connections; crossings without dots are independent. The selected diagnostic route is a proposed bounded topology, not implemented analog switching or a global crossbar.

The connection-detail section expands the repeated SAR ADC and DAC channels, clock qualification, calibration decision loop, and supply/reference distribution. Named ports connect these details to the overview; the interface connection register spells out transport, configuration and status bundles. ADC diagnostics select the I channel only. This records intended interfaces, including still-unqualified conversion clocks and analog circuits, rather than asserting a complete electrical netlist.

The expanded wiring sheets show individual receive paths into the scheduler,
H2D deframing and separate RF/wired transmit queues, asynchronous FIFO boundaries,
consumer request paths, memory playback inputs, SPI request/readback, local
configuration latches, calibration observation feedback, and the candidate RF
coarse-counter/fine-PLL acquisition loop. A local net map identifies the seven
supply/return pairs and their intended consumers. Repeated named ports refer to
the overview; they do not add package pins. Live coarse retuning remains marked
as unresolved. The drawing describes intended connectivity, not a claim that
every interface already exists in the integration RTL.

The expanded local wiring sheets separate P/N conductors and show RX offset and common-mode feedback, TX reconstruction-section feedback, wired sampling/CDR and loopback selection, and named control, clock, bias, reference and status connections. Named ports join the overview without extra package pins. Repeated I/Q circuits remain separate instances. Reconstruction biquads are a mathematical candidate, not a frozen circuit implementation.

The final wiring sheets explicitly connect the two RF mixer current outputs to separate P/N summing nodes, driver, protection and RF pads; branch a differential monitor tap into envelope detection and the diagnostic selector; show shared I/Q DAC commit timing and paired queue acknowledgements; and separate local VDD, VSS, decoupling and bias feeds. The wired RX detail includes the recovered-clock connection to the receive FIFO write side. The RF monitor readout route is proposed connectivity, not a claim of resource allocation closure.

The output-isolation and shared-ADC sheets expand the earlier simplified driver
to pad connection: separate P/N output switches, dummy-load switches, an internal
pre-switch detector tap, finite readout buffer, I-channel source selection, CDAC
reference inputs, SAR feedback, sample/step clocks, ownership/epoch tagging,
request/grant handshakes and separate RX/calibration result paths. The pre-switch
tap supersedes the earlier simplified pad-monitor drawing for this candidate,
allowing calibration with the output isolated. These are proposed circuit
connections; switch timing, detector conditioning and mux settling still need
electrical verification. The added sheets were rendered and visually inspected.

The service-wiring sheets explicitly connect local LO drivers, converter sample / SAR / DAC timing, reference-buffer feedback, local bias and common-mode feeds, reset synchronizers, output controls and fault readback. Separate output routes avoid implying that different clock phases or bias outputs are shorted. The earlier RF monitor overview now consistently taps the driver before output isolation. These additions were rendered and visually reviewed; component-level electrical connectivity remains schematic work.

The package-to-circuit sheets expand all eight analog signal conductors through
protection to their front ends, with separate ESD return routes. Host data paths
show the ten repeated data nets, domain boundaries, DDR capture/launch and
independent forwarded clocks. SPI, reset and reference terminals have individual
routes, including a distinct MISO output-enable control. These sheets retain the
50-terminal allocation. The updated SVG was rendered and visually inspected;
protection cells and any required voltage-domain translators remain design intent.

The passive-network and analog-tile sheets expand the PLL charge-pump output,
Cf/R/Cs storage nodes, capacitor returns and integer-edge feedback. The tile
shows separate P/N selection and weighted-current paths, integration capacitors
with reset-switch bypasses, output buffering and common-mode feedback. The
two-cap PLL network is shown for the wired instance; the RF instance uses the
separate three-storage-node candidate sheet. These sheets were rendered and visually inspected.
The overview retains physical neighborhoods and perimeter IO; the detailed
sheets prioritize readable connectivity over physical placement.

The RF three-storage-node sheet now draws VCP, VSLOW and VTUNE separately,
with the balanced candidate's R/C values, integer-edge divider return, coarse
count observation, bank control, pump enable and lock feedback. Three separate
switched recentering resistors return to a named centering reference; model
voltages are offsets, so physical bias and headroom remain open. An optional
local regulator sheet expands the pass device, error amplifier, resistive
feedback, reservoir capacitor and rail monitor. These are circuit candidates,
not a claim of completed transistor schematics. The added sheets were rendered
and visually inspected, including feedback routing around unrelated blocks.

The final PLL control sheet draws ratio-register commit, fractional sequence
state, integer-divider modulus and boundary feedback, separate sensing paths
for all three storage nodes, qualification inputs, acquisition outputs and the
pump/centering interlock. The overview now identifies the RF three-node filter
separately from the wired two-cap filter. Named internal nets connect the sheets;
they do not increase the package pin count. SVG XML parsing and PNG rendering
passed, and the added sheet was visually reviewed for routing and text overlap.
