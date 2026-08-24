# Direct-regenerative RX front end

This physical parent places two independently clocked StrongARM-style
CML-to-CMOS decisions directly above the programmable termination and
two-stage receiver. The compact, symmetric routing removes the prior data
restorer and level-sensitive sampler from the 2.5-GT/s acquisition path while
retaining separate even and odd sense, regeneration, boost, and capture ports.

The generated parent is zero-DRC, uniquely LVS-matched, and full-RC extracted
to 5,139 resistors and 2,949 capacitors. `physical_result.json` binds the exact
PEX and rendered layout to the layout, schematic, and physical checker. The
complete downstream held-output contract is qualified in the sibling
[`lane_rx_regenerative_capture`](../lane_rx_regenerative_capture/README.md)
parent; this directory owns the shorter physical hierarchy and its probeable
RX and decision nodes.
