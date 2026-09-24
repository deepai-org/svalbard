# GPIO transport scheduling and integrity, pass 3

**Architecture review:** [CRC necessity review](streaming-transport-v2.md#crc-partition-rationale-and-migration-history) recommends streaming payload without mandatory whole-frame CRC/quarantine and separate metadata/control protection. This document describes legacy v1. Default RTL and the current contract now use [streaming v2](streaming-transport-v2.md); the v1 finite queue model remains a historical comparison.

The 64-word frame replaces the insufficient two-control-word/32-word proposal. Parameters live in `contract.json`; `transport_model.py` models error-free queues and `frame_codec.py` defines the aligned frame codec. Neither is hardware qualification.

## Frame layout

Each direction independently sends 64 ten-bit words:

| Words | Meaning |
|---|---|
| 0–2 | 30-bit header, least-significant 10-bit chunk first |
| 3–61 | 59 scheduled payload words |
| 62–63 | 20-bit trailer, least-significant 10-bit chunk first |

Header bit fields: wired count [5:0], I/Q count [11:6], sequence [17:12], opcode [21:18], argument [29:22]. The six-bit sequence increments modulo 64 after each accepted frame. The trailer contains CRC16 [15:0] and fixed marker 0xA [19:16]. CRC uses polynomial 0x1021, initial 0xFFFF, no reflection/final XOR, over words 0–61 in wire order and bits 9 down to 0 within each word. The byte-vector `123456789` yields 0x29B1 under the same bit recurrence. The marker is checked independently; it is not a proof of frame alignment.

Receiver buffers the complete frame, verifies CRC, marker, expected sequence and counts, then releases data and the command together. The first detected error latches FAULT; that frame has no payload or command effect. Do not scan arbitrary live payload for a marker and resume: arbitrary payload can mimic markers. Restart requires explicit training/re-arming, which is not yet implemented. CRC16 is error detection, not authentication or a guarantee against all multi-bit errors. A six-bit counter cannot distinguish loss of exactly 64 frames. Epoch/timeout behavior remains to be specified.

The opcode/argument field is a transport allocation, not a completed PHY command protocol. Directional opcode meanings, execution timestamps/latencies, acknowledgement, one-shot behavior, idle/fault response and clock-domain application need explicit design before RTL. No unsupported opcode may drive hardware merely because the frame CRC passed.

## Deterministic slots, packing and validity

Source quotas are derived with the conservative rate checker. The current Ethernet/RF profile uses 33 wired slots, 25 RF slots, and one unallocated idle slot; PCIe/RF uses 52 wired and seven RF slots. Distribute these 59 positions using smooth weighted round robin: zero initial weights; add each quota at each payload position, select greatest weight with alphabetical tie break, subtract 59 from the selected source. An unused slot participates as `__idle__`. Restart the schedule per frame.

At a frame boundary snapshot up to each quota of complete 10-bit words from its ingress queue, retaining residual bits. Send the snapshot in the following frame. Two transmit staging banks hold up to 1,180 payload bits per direction, plus headers. A receiver needs its own integrity quarantine storage before commit; that is separate from the egress FIFO.

For each source emit valid words in the first `count` of its assigned positions. Later positions are padding, ignored regardless of value. Counts must not exceed source quotas. A padding value is never an idle symbol to be inserted into an external serial stream.

Source items are packed least-significant bit first without per-item padding: ten bits for a raw wired symbol, I then Q at 12 bits/component or eight bits/component for RF. Residual bits span words and frames. RF signed values are two's-complement bit patterns. Frame CRC order is separately defined above and need not match sample packing order.

## Buffering, timing and current evidence

The finite model now withholds a received frame until its final word (ideal successful CRC check). It starts source-matched consumption after 256 host word-times: 819.2 ns at the top nominal host rate. This is a modeling prefill choice, not an accepted PCIe PHY latency. Independently bound both data and command latency through staging, quarantine, CDC and the external controller before claiming protocol interoperability.

Provisional per-source queues are 1,024 ingress bits and 2,048 egress bits. ASIC D2H owns ingress; ASIC H2D owns egress; the FPGA owns the opposite ends. Separate staging and integrity quarantine banks must be included in actual area. This allocation is not a claim of SRAM availability or infinite host-stall tolerance.

The 48-case matrix covers two modes, two sources, host/source offsets -100/+100, 0/0, +100/-100 ppm, four fractional source phases, and 512 frames each. Observed peaks:

| Mode/source | Ingress bits | Egress bits | Maximum cyclic slot gap |
|---|---:|---:|---:|
| Ethernet/RF wired | 330 | 650 | 6 words |
| Ethernet/RF I/Q | 272 | 504 | 8 words |
| PCIe/RF wired | 520 | 1,040 | 6 words |
| PCIe/RF I/Q | 88 | 144 | 14 words |

These are finite observations, not worst-case proofs. The consumer has the producer's exact cadence; independent drift, SSC, CDC delay, errors, stalls and reacquisition are excluded. The aligned codec separately tests all 640 single-bit frame corruptions, valid count combinations, malformed counts, sequence loss/wrap and word loss. Queue simulation assumes successful CRC and does not yet integrate the codec or fault recovery. These evidence boundaries prevent a green reference model from being presented as a verified PHY.

## Architectural audit and next gate

The pass-2 design omitted sufficient integrity/control overhead; pass 3 corrects that without removing any declared traffic. New payload capacity is 59/64 of raw GPIO capacity: 2.880859375 Gb/s per direction at 156.25 MHz DDR. The top coexistence profile has no spare scheduled payload slot; adding timestamps, credits or reliable-command fields must be paid for explicitly.

Before hardware: define training/acquisition, directional fast controls, failure behavior and epoch handling; derive clock/CDC/latency requirements from actual FPGA/controller candidates; then qualify GF180 host pads and return paths. Do not optimize the codec indefinitely while assuming the unverified GPIO electrical interface will work.
