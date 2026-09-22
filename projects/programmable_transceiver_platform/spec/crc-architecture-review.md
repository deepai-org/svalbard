# CRC architecture review

The user asked whether CRC needs to be on the chip. **Mandatory whole-payload transport CRC and quarantine are not inherent requirements of this analog/PHY companion.** They were introduced by the custom host-transport design in pass 3, not by a protocol requirement or a demonstrated host-link error budget. Further CRC optimization should not be prioritized until this architectural choice is resolved.

## Evidence and boundary

The existing CRC16 covers the local 64-word chip/FPGA transport frame, including its counts and commands. It is not Ethernet FCS, PCIe packet CRC, or a Wi-Fi MAC FCS. Those protocol functions belong to the external protocol implementation in the intended companion partition.

[Intel's PIPE specification](https://www.intel.com/content/dam/doc/white-paper/usb3-phy-interface-pci-express-paper.pdf), sections 5 and 6.14, describes data/control/status interfaces and explicitly identifies CRC as a higher-level Data Link function. That is evidence for an external-PHY partition, not proof our custom 50-pin interface is PIPE-compliant. [Analog Devices AN-1441](https://www.analog.com/en/resources/app-notes/an-1441.html) describes AD9361 sample-interface timing and PRBS-based interface calibration. This supports a calibrated streaming sample interface as a precedent, not equivalent GF180 electrical performance or a universal statement about all transceivers.

## Recommended revision

Use a deterministic streaming payload path without mandatory per-frame payload CRC or full-frame quarantine. Preserve explicit alignment/training, validity, FIFO underflow/overflow detection, sticky link-fault status, PRBS/loopback and measured timing margins. Protect the small scheduling metadata and fast-control messages separately; define the code/distance, invalid-message behavior and timing before implementation. Keep bulk configuration on the existing separate control path, with readback/appropriate transaction protection. Fast PHY controls still need a bounded hardware path.

Payload bit errors are then part of the host-link BER budget, as on many conventional raw PHY/sample interfaces. Higher-layer checks may detect resulting packet errors, but do not cover every raw sample, control action or ordered set. Raw SDR data can contain undetected errors. That tradeoff must be explicit, backed by host-link characterization and acceptable application error rates. PRBS training does not guarantee error-free operation after training. A CRC placed only in the FPGA cannot reconstruct a checksum of the original D2H data and detect all intervening link errors without some chip-originated redundancy.

A CRC may still be useful for diagnostics or protected low-rate transactions, but it should not dictate the full-speed datapath or require frame retention by default. Streaming CRC with retrospective error reporting would also avoid quarantine, but still costs fast-path logic and cannot retract a waveform already transmitted; it is a separate option, not the assumed solution.

## Original migration obligations (historical)

Do not simply delete the CRC comparison from current RTL: valid counts decide how raw bits are unpacked, and corrupted commands can change hardware behavior. Specify the replacement metadata protection and acquisition/error recovery first. Build a new codec/RTL path, update FPGA adapter/reference models, inject metadata/payload/control errors, and prove ordering, throughput, latency, reset and buffer bounds. Then measure area, timing and power again. Retain the current checked implementation as a comparison until the replacement works.

No measured savings are claimed. Removing CRC quarantine can eliminate receive frame retention and associated mux/control costs; transmit staging is separately required by the current count-snapshot format and does not automatically disappear. CDC/elastic buffering remains necessary. The 1,280 declared receive-bank bits are only a candidate saving, not all 8,576 declared memory bits. Whether CRC-free streaming satisfies every application is unresolved until an explicit error budget exists.

Current status (rechecked): streaming v2 is the default in `pt_core` and `pt_digital` (`STREAM_V2=1`), and contract version 4 describes it. Payload CRC/quarantine is absent from this path; a detection-only extended-Hamming header protects scheduling metadata and fast commands. Legacy CRC v1 remains a compile-time comparison, not mandatory hardware in the default build. Pass 28 in the project README records integration tests and measured savings; the migration estimates above describe the original recommendation, not current implementation status. Host-link BER qualification and physical timing closure remain open. The full RF/wired rates, 50 terminals and one-slot target remain unchanged.
