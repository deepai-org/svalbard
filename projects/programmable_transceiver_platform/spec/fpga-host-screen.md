# Pass 7: first real FPGA host frequency screen

This is a necessary-condition rejection screen, not a compatible-board declaration. ECP5 is the first examined candidate, not the required host family. Preserve the full companion and ordinary-GPIO objective.

## Exclusive-mode reassessment — 2026-09-23

The simultaneous PCIe-plus-RF bandwidth rejection below is historical: the
accepted operating policy requires only one payload engine at a time.
`screen_ecp5_host.py` now reports both the historical sum and the exclusive-mode
budget. With 59 payload slots per 64 ten-bit words and the existing +/-100 ppm
source/host allowances, a hypothetical 150 MHz DDR interface needs 54 slots
for the full 2.5 Gb/s wired lane, leaving five spare payload slots. Each other
required stream also fits independently. The arithmetic minimum DDR clock for
that wired lane is approximately 135.621 MHz.

This reopens a lower-host-clock architecture candidate without reducing the
wired line rate or RF sample formats. It requires actual exclusive slot
reallocation, clock generation, queue/latency analysis and endpoint agreement;
the current executable chip profiles remain 125/156.25 MHz. The existing
documented FPGA frequency screen alone does not qualify board timing, output
loading, jitter or receiver sampling. Do not transfer existing profile results
to the proposed 150 MHz interface or claim a compatible FPGA board from this
bandwidth calculation.

The optional `screen_ecp5_host.py --queues` check also passes each exclusive
stream through 512 frames at four source phases with the conservative host/source
offsets. It uses the current five-header-slot placement and ideal streaming
release after header acceptance. The 2.5 Gb/s case peaks at 540 ingress bits,
1,090 egress bits and 1,070 staging bits, within the planning allocations; these
are not implemented RTL FIFO depths. A 53-slot negative control overflows ingress,
while the proposed 54-slot service passes. Header decoding, CDC, host pauses,
mode changes, actual clock generation and latency acceptance remain open.

For this ideal fixed-rate queue model, the checker also derives conservative
duration-independent bounds. In host-word time, let `F=64`, sample width `s`,
source bit rate `r`, allocated service `R=10*q/F`, and arrival burst allowance
`b=s+9`. A frame-boundary snapshot server supplies rate R with at most one frame
of latency. The following-frame staging/emission adds at most two frames;
finishing a partial ten-bit word can wait one sample period because s is at
least ten bits. Thus delivery delay is bounded by `3*F + b/R + s/r` when R>=r.
Ingress is bounded by `b+r*F`, and the two staging banks by `20*q` bits.

With producer and consumer at the same constant cadence and consumer start
delayed S=256 host words, the delivery bound below S prevents starvation after
startup. Delivery cannot precede one frame of staging, giving the conservative
egress bound `r*(S-F)+2*s+10`, including packet/word rounding allowances.
Across the four streams, delivery bounds are below 230 host words. The largest
ingress/egress/staging bounds are 553/1,631/1,080 bits, within the planning
allocations. The finite tests also check their observed peaks against these
bounds. These arguments address indefinite operation only under the stated
constant, matched-rate and uninterrupted-service assumptions. They do not bound
independent sink drift, host stalls, extra CDC latency, acquisition or transitions.

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

## Next closure work (updated for exclusive operation)

Find a host with documented ordinary single-ended GPIO capability at the top profile, then specify device/package/speed grade, bank supply, forwarded-clock pins and DDR resources. Close both directions using actual driver/receiver thresholds, pad capacitance, package/PCB loading, skew and jitter, and placed host timing. Reassess the hypothetical 150 MHz exclusive profile against those same checks. Preserve every required wired and RF rate in its selected mode; simultaneous RF/wired payload is no longer required. Do not substitute FPGA serial transceivers for the ordinary-GPIO objective.
