# Ordinary-GPIO host feasibility

The FPGA frequency screen is a necessary-condition check, not a compatible-board
declaration. ECP5 and Artix-7 are scoped candidates, not mandated host families.
The goal remains full selected-engine throughput through ordinary FPGA GPIO.

## Primary evidence

[Lattice ECP5 family datasheet](https://www.latticesemi.com/view_document?document_id=50461), FPGA-DS-02012-3.4 (September 2025), Table 3.21, printed pages 65–66: LVCMOS33 input/output clock ceilings are 200/150 MHz. DDR transfers twice per clock. These speeds are characterized, not tested on every device; fast slew is used. Table 3.44 uses a 0 pF fixture load for LVCMOS timing, so the stated frequency is not proof at our board load. Source PDF SHA-256 is retained in the report.

At 156.25 MHz forwarded clock, the documented ECP5 LVCMOS33 output limit is
exceeded. The 125 MHz case passes this frequency-only check. Neither establishes
board timing; a faster internal FPGA clock rating cannot override pad limits.

RF and wired payloads are exclusive. A hypothetical 150 MHz DDR framed link can
allocate 54 of 59 payload slots to the 2.5 Gb/s lane under the screen's ±100 ppm
allowances. The arithmetic minimum is approximately 135.621 MHz. This is a
bandwidth bound, not a selected clock configuration or electrical qualification.

The [ECP5 report](../evidence/ecp5-host-screen.json) is reproduced with
`verification/screen_ecp5_host.py --queues`. Its framed queue fixtures assume
constant matched rates, ideal header release and uninterrupted service; they do
not qualify the selected direct byte stream, CDC, host stalls or transitions.
The command records its design/contract provenance. Datasheet limits are manually
transcribed; it does not fetch or parse the PDF.

## Native GF180 GPIO evidence

The [Liberty screen](../evidence/gpio-liberty-screen.json) evaluates native pad
arcs at declared corners, 0.5 ns input slew and 5/10/15 pF table coordinates.
Load-coordinate convention must be resolved before treating these as external
capacitances. The nominal 24 mA fast-slew 10 pF rise/fall transitions are
0.938/0.762 ns; the selected slow corner gives 1.721/1.397 ns against a 3.2 ns UI.
These are transition estimates, not a DDR eye or setup/hold proof. Absolute
propagation above a UI is not by itself a source-synchronous failure.

Reproduce with `make transceiver-gpio-screen`. Source fingerprints identify the
actual library/image; they do not establish provider-qualified fabrication inputs.
[Host driver selection](host-driver-selection.md) owns transistor loading and
current comparisons, including the unresolved supply-impedance simulation.
The [power owner](power-partition.md) owns supply/return allocation and limits.

## Required closure

1. Choose a concrete host device/package/speed grade and GPIO bank, then establish
   both directions' receiver thresholds, slew, phase training, skew and placed
   timing with the actual forwarded clocks.
2. Compose pad, bond, board and receiver capacitance once at explicit reference
   planes. Include all active outputs, current return paths and clock coupling.
3. Demonstrate payload throughput and response latency through the selected
   transport, not only average bandwidth or ideal constant-rate queue bounds.
4. Close supply-cell, metal/via and bond current limits using the compatible ring.
   A pair of ideally supplied pads cannot establish complete-bank qualification.

These screens do not qualify RF, SerDes, protocol behavior or whole-chip layout.
