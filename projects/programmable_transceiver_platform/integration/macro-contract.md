# First implementation baseline

This pass creates a runnable digital implementation and a whole-chip connection skeleton. It is **not an entire transistor-level transceiver implementation**. The two physical macros in `pt_chip.sv` are explicit black boxes. No resulting netlist is suitable for fabrication. The full first-silicon objective is unchanged.

## Current transport implementation (pass 28)

`pt_digital` and `pt_core` default to `STREAM_V2=1`, using protected-header streaming without payload quarantine. `STREAM_V2=0` retains v1 for comparison, not as a runtime extra protocol. The 1,280-bit declared RX frame bank and its read pipeline are eliminated; declared data arrays fall from 8,576 to 7,296 bits. TX staging and all other FIFOs/capture/playback remain. The older storage description below describes the original v1 baseline. Both rate profiles pass finite functional tests in both variants. Canonical contract version 4 reflects v2; legacy queue-model evidence is explicitly separated. Current physical results and their limitations are in the pass-28 report.

## Physical interface

The top-level has exactly 50 terminal bits: 20 data, 2 host clocks, 4 SPI, reset, reference, 8 analog and 14 power/ground. This is a logical connection contract, not a pad placement, package assignment, ESD network or electrical qualification. `pt_host_physical` owns the GPIO pads and DDR gearbox; `pt_analog_physical` owns RF/wired pads and the analog/clock hierarchy. Supply domains must remain distinct through physical implementation.

The digital host word clocks are 250/312.5 MHz. DDR host pin clocks are 125/156.25 MHz. A host macro must produce one correctly ordered 10-bit word per internal clock without missing either DDR edge. This high internal frequency is an explicit GF180 timing risk; structural synthesis cannot establish feasibility. A two-word-wide implementation is a possible refinement if timing fails, with corresponding scheduling changes.

Wired parallel clocks are nominally 125/250 MHz; serialized order is bit 0 first. RF samples are `{Q[11:0], I[11:0]}` in signed two's complement, with 8-bit mode transporting the most significant eight bits of each channel. Clock synthesis, actual CDR, PLL lock gating, converter latency and playout clock tracking remain physical macro requirements. The host must provide source-matched playout rates; finite FIFOs cannot tolerate permanent independent producer/consumer drift.

## Circuit obligations

| Block | Candidate starting point | Work still required |
|---|---|---|
| Wired RX termination/slicer | `ip/blocks/analog/wireline_serdes/lane/rx_2p5.pex.spice`, termination and capture experiments | Select and integrate variant, CDR acquisition/tracking, sensitivity/jitter and extracted signoff |
| Wired TX | Existing wireline serializer/driver research | Full 10:1 serializer, output swing/termination, electrical idle and rate switching |
| RF LNA | `ip/blocks/analog/wifi_80211b/rf_lna/lna_cs_core.spice` | Differential integration, bias, matching, noise/linearity and RF pad parasitics |
| I/Q mixer | `ip/blocks/analog/wifi_80211b/rf_switch_mixer/mixer.spice` | Quadrature LO, differential paths, DC offsets, TX upconversion and isolation |
| Shared programmable baseband | Architecture's local sample/weight/sum resources | Transistor circuits, switches, programmable filters/gain, settling and calibration observability |
| Converters | Ideal signed ADC/DAC model in `sim/pt_afe_model.sv` | Actual ADC/DAC architecture, circuits, achievable ENOB and sample rate |
| Reference/LO/clocks | Trim and calibration interfaces implemented digitally | PLL/VCO, divider/phase network, clock mux/reset sequencing, lock monitoring |
| Host pads/DDR | Existing native-pad experiments | Real DDR gearbox, input/output phase adjustment, host timing, simultaneous switching and rail closure |

The listed circuit files are reuse candidates, not validated components of this chip. No full RF chain, RF-to-host simulation or analog hierarchical netlist has been completed in this pass. Ideal models do not establish GHz operation, Wi-Fi performance, protocol compliance or achievable ENOB.

## Digital contents and costs

Implemented RTL: streaming FIFOs with Gray pointer synchronization; I/Q reservoirs; two-bank transmit staging and receive CRC quarantine; training, sequence/count/command checks; candidate SPI register ABI; finite capture/playback; PRBS31; successive-approximation calibration sequencer. Protocol processing remains in the external FPGA.

Explicit declared array storage is 8,576 bits: wire ingress 640, RF ingress 384, packed-I/Q ingress 320, wire egress 1,280, packed-I/Q egress 320, RF egress 1,536, TX/RX frame banks 2,560, capture/playback 1,536. Reservoirs, pointers, synchronizers and other registers are additional. Synthesis can optimize unused frame-bank locations. These actual capacities supersede any inference that the earlier abstract FIFO allocations describe this implementation. Memory macro mapping, total core area and power remain open; the original 0.8 mm² memory allocation is unproven.

SPI is mode 0, MSB first, 32 clocks under CS: command/address/data = 8/8/16 bits; command 0x80 writes and 0x00 reads. This is a candidate local ABI, not demonstrated compatibility with another Svalbard control interface. Register decoding is in `rtl/pt_spi.sv`. Program while disabled, initialize all 32 playback samples before playback, then enable. Mode and trim changes while enabled are rejected. Capture/readout is finite and useful to MCU hosts; streaming requires sufficient FPGA GPIO bandwidth.

## Verification and limitations

Run `make transceiver-baseline`. Pinned Docker tools run both streaming profiles for about 60 microseconds, compare wired/IQ samples, inject a CRC error, check sticky fault/reset, exercise SPI, capture/playback, PRBS and calibration, and perform structural synthesis. An independent Python codec decodes all clean complete RTL-generated frames. The ideal converter model is compile-checked only; its analog behavior and the wire model are not yet integration-tested.

Passing these checks establishes a useful refinement baseline. It does not establish arbitrary phase/frequency behavior, CDC/STA closure, acquisition after arbitrary DDR bit slips, SSC tolerance, fast-command physical timing, FPGA protocol integration, memory placement, rail/package behavior, DRC/LVS or tapeout readiness. SPI status is a synchronized diagnostic snapshot, not an atomic event log. Trim crossings rely on programming while disabled and require implementation constraints. Reset release is synchronized in each FIFO domain; reset/enable sequencing across the entire physical clock tree remains to be qualified.

Next broad pass: implement and test the host DDR macro and full-chip functional harness, select concrete converter and clock circuits, integrate candidate RF/wired transistor hierarchies, then map/place the actual digital logic. Keep circuit failures and area/timing violations visible; do not reduce the intended first-chip capability silently.
