# Pass 7: first real FPGA host frequency screen

This is a necessary-condition rejection screen, not a compatible-board declaration. ECP5 is the first examined candidate, not the required host family. Preserve the full companion and ordinary-GPIO objective.

## Primary evidence

[Lattice ECP5 family datasheet](https://www.latticesemi.com/view_document?document_id=50461), FPGA-DS-02012-3.4 (September 2025), Table 3.21, printed pages 65–66: LVCMOS33 input/output clock ceilings are 200/150 MHz. DDR transfers twice per clock. These speeds are characterized, not tested on every device; fast slew is used. Table 3.44 uses a 0 pF fixture load for LVCMOS timing, so the stated frequency is not proof at our board load. Source PDF SHA-256 is retained in the report.

## Design consequences and independent arithmetic

The 156.25 MHz top profile exceeds the documented H2D output-clock ceiling. D2H is below the input ceiling, but neither direction has board timing closure. The 125 MHz profile passes this frequency-only screen. A faster FPGA internal clock specification does not override its pad limit. The accepted narrow operating envelope does not establish undocumented host speed.

Even a hypothetical 150 MHz DDR profile cannot preserve PCIe plus the declared RF stream: useful nominal bandwidth is 2.765625 Gb/s per direction versus 2.82 Gb/s demand. With the contract's provisional clock offsets and whole-slot reservations, wire needs 54 slots and I/Q needs 7, exceeding the 59 available. Neither tighter voltage/temperature nor removing clock-offset allowance fixes that nominal bandwidth deficit. No lower-rate substitute has been inserted into the contract.

Reproduce the [retained report](../evidence/ecp5-host-screen.json):

```sh
python3 projects/programmable_transceiver_platform/verification/screen_ecp5_host.py
```

The script reads the current contract and records its hash. It does not download or parse the PDF; the documented limits are manually transcribed evidence. Every profile remains explicitly unqualified.

## Next closure work

Find a host with documented ordinary single-ended GPIO capability at the top profile, then specify device/package/speed grade, bank supply, forwarded-clock pins and DDR resources. Close both directions using actual driver/receiver thresholds, pad capacitance, package/PCB loading, skew and jitter, and placed host timing. ECP5 remains a candidate for lower profiles, pending those same checks. Keep a full-rate architecture review open if no suitable host can be qualified; do not silently remove simultaneous PCIe/RF or require FPGA serial transceivers.
