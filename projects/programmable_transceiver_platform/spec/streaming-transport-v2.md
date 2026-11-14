# Host streaming transport

The payload link between the chip and the FPGA: ten data pins plus a forwarded clock in each direction (`H2D[9:0]`,
`H2D_CLK`, `D2H[9:0]`, `D2H_CLK`), carrying one framed stream of ten-bit words. SPI is the separate configuration
and recovery port. Protocol parsing, CRC/FEC and bulk storage are in the FPGA; payload has no transport CRC.

Implemented in `rtl/pt_host_link.sv` (pad-edge capture, launch and gearboxes), `rtl/pt_quad_link.sv` (frame
engines, training) and `rtl/pt_core.sv` (storage, commands, sample packing). The word-at-a-time FPGA-side reference
is `sim/reference/pt_dense_transport.sv`; the Python reference codec is `verification/stream_codec.py`.

## Ownership and capacity

The stopped-only field `digital.transport_config.payload_iq` selects the one owner of all payload slots: wired (0)
or I/Q (1). `MODE8` selects the I/Q sample width. A frame carries 59 payload words in 64 ten-bit words, so the
framed capacity is 10 × 59/64 bits per word clock:

| Host word rate | Framed capacity |
| --- | --- |
| 312.5 Mword/s (line rate / 8 at 2.5 Gb/s) | 2.881 Gb/s |
| 250 Mword/s | 2.305 Gb/s |

For framed wired rates the host word clock is the line rate / 8, which gives 1.152 × the line rate. 40 MS/s complex
samples at 12 bits need 0.96 Gb/s. With the stopped-only `digital.transport_config.linecode` the chip does the
8b/10b decode and encode at the wired boundary and the host carries 9-bit symbols (0.9 × line rate).

`debug.host_link.rate` runs the word side and the whole transport core at the host word clock /1, /2 or /4;
`debug.host_link.mode` selects DDR at full rate or SDR at the reduced rates. Both change only while `ENABLE` = 0.

## Clocks and pin timing

The macro receives the host DDR clock `host_word_clk` (156.25 MHz at 312.5 Mword/s): one ten-bit word per pin per
clock edge. No macro logic runs at the word rate. `pt_host_link` divides it by two for the 78.125 MHz core clock;
the transport core handles four chronological words (a 40-bit quad, word 0 in bits [9:0]) per core clock.

- **D2H.** Each pin is the XOR of a rising-edge and a falling-edge flop that hold consecutive running-XOR
  prefixes of the word stream, so a pin changes once per word by one flop toggling. `D2H_CLK` is produced the same
  way and is edge-aligned with the data; the FPGA centres it by input delay or phase training. In SDR the forwarded
  clock is the inverted word clock.
- **H2D.** Capture on both edges of `H2D_CLK` (rising only in SDR), quad assembly in that clock domain, then an
  eight-quad Gray-pointer FIFO into the core clock. The FPGA derives H2D from D2H, so the FIFO absorbs phase only.
  The H2D receive path is not reset by `ENABLE`.

## Frame

A frame is 64 words = 16 quads. Quad 0 is the protected header (words 0–3), quad 1 is {w7, w6, w5, guard `0x2d3`},
quads 2–15 carry payload words 8–63.

The header carries 30 metadata bits: wired count [5:0], I/Q count [11:6], sequence [17:12], opcode [21:18],
argument [29:22]. They are protected by a shortened extended Hamming code used for detection only: positions 1–36
with parity at 1, 2, 4, 8, 16, 32, data in the other positions in ascending order, bit 36 overall even parity,
bits 37–39 the tag `101`. The four header words are sent least-significant ten bits first.

The receiver checks syndrome, tag, guard, sequence, that the inactive owner's count is zero, that the count is at
most 59, and command legality before any effect of the frame. It never corrects. Payload is released as its words
arrive, up to three in the guard beat and four per payload beat. A destination that cannot accept a word raises a
fault instead of applying back-pressure. A detected error latches the fault until the link is disabled and
retrained. Counts describe complete words; unadvertised slots are padding.

Limits of the code: every one-, two- and three-bit header change is detected, some four-bit changes are not; the
six-bit sequence cannot see the loss of exactly 64 frames.

## Start-up

After enable, the D2H side sends the eight-word prefix `3A5 05A 2D3 12C 369 096 21E 1E1` (two quads) and then
frame 0. The receiver searches for the prefix only while unlocked, in any of the four word rotations of the quad
stream, with a 255 core-clock timeout that latches an acquisition fault. Once locked it never scans payload for
the prefix. Arm the receiver before the peer transmits; a missed prefix needs a coordinated restart.

## Storage

One ingress bank and one egress bank serve whichever owner is selected, each behind a stopped-only clock mux:

| Bank | Depth | Content | Start threshold |
| --- | --- | --- | --- |
| Ingress | 28 quads | Wired RX quads, or I/Q samples packed into quads in the RF sample-clock domain | — |
| Egress | 24 quads | Wired TX quads, or I/Q quads unpacked to one sample per request | Wired 8 quads; RF 5 quads plus prefetch |

Disable flushes both banks and the sample packing state even with stopped clocks. Changing the owner requires
disable. Capture and playback memory (registers 0x20–0x26) uses the same banks.

At the wired boundary the macro exchanges 40-bit quads per edge of the capture clock (RX) and the serializer word
clock (TX), line rate / 40, word 0 earliest on the line. At the RF boundary it exchanges one 24-bit I/Q sample per
converter clock.

## Commands

The opcode and argument of an H2D header are a command. Reserved or context-illegal commands fault.

| Opcode | Owner | Argument | Effect |
| --- | --- | --- | --- |
| 0 | any | 0 | No operation |
| 1 | any | 0 or 1 | Wired idle |
| 2 | any | 0 or 1 | RF mute |
| 4 | I/Q | bit 7 = 0, bits 6:5 LNA gain index, bits 4:0 PGA gain index 0–16 | Fast gain change; the frame carries no payload |
| 5 | wired | threshold DAC code | Load slicer threshold A; overrides the register field until disable |
| 6 | wired | threshold DAC code | Load slicer threshold B; overrides the register field until disable |

Fast gain: one update may be pending; a second command before the status frame is rejected without changing the
gain (sticky status bit). The new gain is applied in the RF receive sample domain, which discards the partly packed
sample and the next 20 samples and restarts packing at a quad boundary. The D2H side first completes the samples
taken at the old gain, then sends a gain-status frame: opcode 4, argument = {gap bit 6, gain}, wired count = gap
bits 5:0 (complex sample pairs invalid or discarded), I/Q count = new-gain payload words in that frame. The FPGA
drops any partial pair and advances its sample index by the gap.

Open: `pt_core` decodes opcodes 5 and 6, but the header legality check in the frame receiver
(`pt_quad_link.sv`, `legal_n`) admits only opcodes 0, 1, 2 and 4, so a header with opcode 5 or 6 faults the link
in the committed RTL. Not confirmed by simulation.

## USB

USB uses the same framed transport with wired ownership. Full and low speed: `rtl/pt_usb.sv` carries line symbols
of two bits {D−, D+}, 20 per quad, transmitted at a divided clock and received by oversampling the detect
comparators. High speed runs through the wired serializer and capture path at 480 Mb/s. Packets, CRC, bit stuffing
and NRZI are in the FPGA.

## Status

Legacy register 0x03 `STATUS`, bit 0 upward: enable; any underflow; wired ingress overflow; RF ingress overflow;
two owner bits (I/Q: fast gain rejected, fast gain pending; wired: 8b/10b code error, 8b/10b aligned); wired egress
overflow; RF egress overflow; receive fault; locked; command fault; wired starved; RF starved.

## Not implemented

Registers 0x30–0x3F are reserved for a recovery mailbox and reject writes. There is no direct byte-stream mode,
no 256-word frame (requirement HL-FRAME), no fault-status frame, no sample-time (timed launch, sample snapshot) or sample-epoch metadata, and no independent
watchdog for a stopped host clock in the transport itself.

## Checks

`make transceiver-stream-codec`, `transceiver-dense-pair` (quad engines against the ten-bit codec),
`transceiver-dense-pair-link` (both pad-edge gearboxes in loopback, DDR and SDR, all four word rotations),
`transceiver-pair-gearbox` and `-formal`, `transceiver-pair-word-formal` (word order on the pin),
`transceiver-dense-service` (2.5 Gb/s wired both directions), `transceiver-dense-rf-service` and
`transceiver-dense-rf-burst` (40 MS/s), `transceiver-shared-egress-lifecycle` (owner change), and the FIFO and
end-to-end benches in `transceiver-digital-rtl-checks`. These are functional RTL checks; pin timing is budgeted in
`interface-requirements.md` section 3.
