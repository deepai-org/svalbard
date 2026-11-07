# Feasibility and capability acceptance gates

## Current mathematical-model milestone

Complete one configured whole-chip behavioral model covering all 17 intended
interfaces, with explicit uncertainty, useful signal quality, host service and
startup/traffic/fault/recovery. `mathematical-closure.json` is the completion
inventory. All capability verdicts remain unresolved. The [current issue register](risk-priorities.md#open-issue-register)
identifies known failures separately from missing evidence.

A passing test may validate an expected rejection or numerical method. Neither
test count nor an isolated decoded packet establishes capability. Each accepted
result needs its configuration, independent stimulus, numerical criterion,
source fingerprint, uncertainty coverage and excluded effects.

## Decision sequence: several credible ways to succeed

| Gate | Required work | Exit evidence |
| --- | --- | --- |
| G0: operating conditions and host | One block ledger for voltage/ripple, clocks/jitter, pads/common mode/coupling/termination, simultaneous activity and host service. | Resolve conflicts in the shared architecture; numerical per-target acceptance criteria. |
| G1: package, pads and power | Provider-compatible bonds, complete attachments including disabled branches, common supply/return, host switching and package uncertainty. | Electrical budgets and device stress met across justified bounds, including resonances; buildable assembly. |
| G2: timing | Shared source/stage/supply spectra, differential reference loading, independent wired CDR and separate retune/turnaround sequences. | The same timing environment drives RF and wired acceptance; acquisition, loss and recovery are covered. |
| G3: RF chain | Wanted signal, blockers, real preamble, AGC, converters, noise, ppm, switching and TX emissions joined. | Each radio meets numerical sensitivity/selectivity/quality/turnaround criteria in an explicit envelope. |
| G4: controls and lifecycles | Generic electrical actions, host-to-pad latency, full startup/operation/fault/recovery, sustained transport. | USB both roles, PCIe detection/idle, SATA OOB and other target-specific behaviors have connected evidence. |

The user has a Zynq-7000-series FPGA; exact board and physical GPIO service are
not qualified. Select concrete load/slew/current/activity assumptions per host
scenario. A family name alone does not establish switching spectra or response
latency. Keep external protocol logic and bulk storage on the FPGA.

The full first-chip scope is retained. External clocks, extensive passives and
narrow accepted supply/temperature conditions are allowed. They do not remove
process variation, mismatch, package coupling or device-terminal exposure.
Unqualified physical information remains bounded assumptions or explicit gaps;
there is no requirement to obtain unavailable private foundry RF/package data.

## Wi-Fi HE20 capability gate


Target: **one spatial stream, 2.4 GHz HE20, MCS 0–7**, legacy discovery and
association, bidirectional HE traffic, ACK/Block ACK and router-triggered uplink.
**Interoperability and robust combined analog margin are not demonstrated.**
The sole normative numeric inventory is `rf_interoperability` in
[analog-architecture.json](analog-architecture.json). Protocol implementation,
calibration tables, correction FIRs and bulk storage stay in the FPGA.

### Selected requirements

| Area | Current decision | Evidence still required |
|---|---|---|
| Clock | Clean differential external LO is primary; autonomous synthesis remains separately qualified. Keep LO/sample/host clocks warm across direction changes. | Joint phase-noise, divider/distribution, supply and converter-aperture envelope; triggered TX frequency statistics. |
| RX filter | Retain sharp 9.53125 MHz maximum and narrowband options. A wider independently selectable setting remains under evaluation. | Complete HE and DSSS/CCK tuning-headroom/blocker tests before choosing the additional width. |
| TX filter | Selected five-pole Butterworth, up to12MHz, with49-tap FPGA correction using12fractional coefficient bits. No three-pole bypass is selected. | Complete HE emissions, interpolation rejection, measured calibration and amplifier behavior remain open. Area/current estimates remain recorded; fabrication fit is deferred until behavioral closure. |
| DAC operating point | Native10-bit code width is retained; effective noise must be qualified at actual corrected-waveform amplitude. | Prefer8ENOB at0.24 amplitude with7.6042dB external TX-only attenuation into the fixed PA hypothesis. Retain9.5ENOB/0.10 as the lower-swing alternative. Complete HE crest, RF drive/pad load, filter current, DNL/spurs and calibrated power can still reject either route. |
| Calibration | External equipment and context-specific FPGA tables; no added detectors, pins or on-chip table storage. | Frequency-dependent correction, held-out measurement accuracy, drift, analog peaks and PA spectrum. |
| Frontend | External matching/preselection/switch and optional linear PA; 2 dB nominal/3.5 dB maximum allocated RX loss. | Board isolation, PA distortion, switching and receiver recovery together. |
| Timing | Schedule a defined antenna marker using bounded delay and actual finite queues; retain warm bias. | Physical bounds and protocol-specific deadlines. Preamble alignment is not first RF energy. |


Preferred TX operating point: 8 ENOB at normalized amplitude 0.24 with
7.6042 dB external TX-only attenuation into the stated PA hypothesis. The
lower-swing 9.5 ENOB/0.10 case is a comparison, not an independently selected
design. Actual drive, peaks, current and emitted spectrum can reject the
preferred point. Do not reduce amplitude without recalculating noise and power.

The independent legacy OFDM runner supplies conditional DATA/ACK evidence at
all eight rates. Diagnostic HE DATA does not supply complete HE preambles,
association, trigger-based uplink or router interoperability. Complete independent
HE references remain missing; `he_reference_vectors.m` is not executed evidence.

Complete packets must meet the combined TX −30 dB design target, spectral masks,
unused-tone/carrier emissions and antenna-level timing under the same analog
assumptions. RX uses its own sensitivity/PER and blocking criteria, not the TX
EVM limit. RSS applies only to justified independent noise; bounded residuals
cannot assume cancellation. Calibration lives in FPGA tables and needs held-out
measurement-error/drift checks. Physical board characterization follows model
and circuit qualification; it is not a prerequisite for evaluating explicit
behavioral uncertainty ranges.

## Bluetooth LE acceptance versus stress probes

A finite LE1M request/reply is scoped evidence, not qualification of every LE
PHY, hopping schedule or spectrum. Check actual preamble/access-address
acquisition, CFO, blockers, gain settling, warm turnaround and antenna timing.
Keep deliberately harsher diagnostics distinguishable from required acceptance
cases, and do not infer PER from one seed/channel or a decoded packet.

## Capability-wide evidence gaps and next decisions


The coverage denominator is the 17 entries in
`generic_control_surface.external_interface_requirements`, not a subset of waveform/line-rate entries. Those entries are external application
requirements, never on-chip protocol IDs. HD-SDI, custom GFSK/SDR and the two
RF stretch paths must remain visible even without dedicated report fixtures.
USB host and device share one entry but require separate role validation.

| Target | Selected architectural provision | Unique remaining proof / boundary |
|---|---|---|
| PCIe Gen1 | Keep dedicated 2.5 Gb/s TX/RX, independent CDR, receiver detection and electrical idle; FPGA endpoint/PCS. | Detection and idle are physical actions, not serial symbols. Loaded startup/recovery and command latency remain unverified. |
| 1000BASE-X | Use the wired pair at 1.25 Gb/s; FPGA owns coding, ordered sets and negotiation. | Sustained independently clocked operation and recovery; no 1000BASE-T magnetics/copper PHY is implied. |
| SGMII | Reuse the same 1.25 Gb/s electrical path with external SGMII PCS/control. | Validate SGMII control/rate adaptation separately from BASE-X; equal baud rate is not equal protocol behavior. |
| SATA Gen1 | Retain 1.5 Gb/s operation, timed OOB drive/detection and CDR handoff. | OOB burst/gap sensing and transition to aligned data must work without an ideal reset of analog/CDR state. |
| USB 2.0 HS, host and device | Use WIRE_RX as D+/D−; independent HS/FS/LS drive, pulls, termination and sensing. FPGA controller; external host VBUS. | Both roles need attach/reset/chirp, HS traffic, turnaround and disconnect. Disabled USB branches still load the fastest serial configuration. |
| DisplayPort RBR | One 1.62 Gb/s lane per die, programmable swing/pre-emphasis, FPGA training and external AUX. | Prove training levels and sustained clock tolerance. Multiple lanes multiply dies and alignment obligations. |
| Single-link DVI | Three lane dies with DC TMDS branches, external clock fanout and FPGA encoding/alignment. | DC common mode/off-state protection, fractional ×10 timing, continuous FIFO and recovery after one lane faults. |
| HDMI TMDS | Same three-die video boundary; FPGA/board owns control-period encoding and ancillary interfaces. | Retain 720p/1080p fractional-clock goals. TMDS evidence does not imply HDMI FRL, higher-rate modes or complete HDMI system functionality. |
| HD-SDI | Keep 1.485 and 1.485/1.001 Gb/s; external coax driver/equalizer and FPGA scrambling/framing. | Stress CDR with actual scrambled/pathological patterns and sustained transport; a generic NRZ eye is insufficient. |
| 2.4 GHz Wi-Fi HE20 | Keep wideband I/Q, finite-zero channel filtering, paired converters and external FPGA modem/equalization. | Joint sensitivity/blocking, actual training, modulation-dependent EVM, TX spectrum and turnaround. Narrowband success cannot close this requirement. |
| Bluetooth LE | Use selectable narrow RF settings and warm same-channel turnaround; FPGA framing/modem. | Retain LE PHY goals; current LE 1M request/reply does not cover other PHYs, hopping, masks or calibrated air timing. |
| Bluetooth Classic BR/EDR | Use the same I/Q chain with phase-preserving modulation and retune control; FPGA hopping/baseband. | Real packet acquisition, channel changes and modulation-specific phase quality/turnaround must fit the selected clock architecture. |
| IEEE 802.15.4, 2.4 GHz | Reuse narrow I/Q filtering, O-QPSK/DSSS processing on FPGA and warm RX/TX control. | Real synchronization header, blockers, gain settling and response timing; generic DSSS data is not a packet result. |
| 2.4 GHz LoRa | Use narrow bandwidth/divider settings; FPGA chirp acquisition, resampling and modem. | Actual finite preamble, CFO drift, blockers and transmit spectrum; longer diagnostic training is not the selected remedy. |
| Custom GFSK / SDR | Expose numeric rate/gain/filter/timing controls and continuous I/Q streams within the same envelope. | Publish achieved ranges and error bounds rather than arbitrary-waveform promises; host service is part of the bandwidth limit. |
| Lower-frequency RF stretch | Selected dual-edge divide-by-two quadrature reuses the RF chain for 240–1250 MHz carriers from 480–2500 MHz external input; board matching/filtering is band-specific. | Phase error, frontend tuning and useful signal quality remain unqualified. Native 1250–2400 MHz is not selected; other bands retain external conversion. |
| External frequency conversion stretch | Translate another band into the qualified on-chip RF band with board mixer/LO/filter; no extra chip analog pins. | Include conversion loss/noise, images, linearity, LO coherence and board power. This is an external system, not native wideband RF coverage. |
RF recipe sample-rate ceilings are allocation limits, not selected clock points.
The external-LO path samples at carrier divided by 64, 128, 256 or 512;
its maximum over the selected 2.400–2.500 GHz band is 39.0625 MS/s. FPGA
resampling must use that actual rate. Configuration admission does not prove
that every divider/filter combination serves every waveform.

Direct-LO operation extends through 2.500 GHz as a requirement. Frontend,
quadrature and clock-quality qualification must cover the endpoint.

**Work order:** after the shared analog envelope, close the USB shared-pad and
PCIe detection/recovery anchors because they can require different pad circuitry
or missing controls. In parallel in the work plan, retain the real RF exchange
as the noise/emission/turnaround anchor; remaining radio families require their
own acquisition evidence. Continuous Ethernet and video then test sustained
clock/service behavior. This is an investigation order, not permission to remove
or downgrade the remaining targets. A control mapping or borrowed rate fixture
never substitutes for the missing behavior listed here.

## Physical qualification

Behavioral closure is followed by a complete connected transistor/passive
schematic, then layout/extraction using the same requirements. The scoped pad
implementation can proceed under its existing authorization. Physical gates:

- Autonomous clocks: startup, monotonic tuning, noise/spurs, supply pushing,
  quadrature and loaded distribution over the accepted operating envelope.
- RF and converters: noise/gain/linearity, blockers, acquisition, reference
  settling, rare decisions, clipping, TX power/EVM/emissions and circuit current.
- Pads/package: normal/off-state loading and stress, complete protection and
  local safety, common returns, full host activity, routed parasitics and assembly.
- Manufacturing: compatible process/stack, complete DRC/LVS, density/antenna,
  current capacity, IDs and package signoff; silicon and reliability qualification.

A candidate is not accepted by widening a budget without system accounting,
removing a required target, resetting away retained state or changing stimulus
to avoid an implementation failure. Change the circuit or declare the gap.
