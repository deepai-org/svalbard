# First implementation baseline

`pt_analog_physical` owns both external clock legs and exports the conditioned
`ref_clk` event interface to digital control. `pt_host_physical` owns neither
clock leg. The black boxes do not implement a differential receiver or prove
common-mode range, phase quality, or protection. GHz input must bypass ordinary
host GPIO circuitry.

Current clock interface: `REF_IN` (positive) and `REF_IN_N` (negative) form one
differential reference/LO port, selected while stopped. Both legs require analog
conditioning/protection; source frequency and protocol ownership are unchanged.
See the [normative architecture](../spec/block-diagram.md) for the selected 44 mA timing allocation
and 0.025 ps/mV aggregate supply-delay requirement. Saved single-ended studies
below are historical controls, not qualification of this revision.

This pass creates a runnable digital implementation and a whole-chip connection skeleton. It is **not an entire transistor-level transceiver implementation**. The two physical macros in `pt_chip.sv` are explicit black boxes. No resulting netlist is suitable for fabrication. The full first-silicon objective is unchanged.

## Current transport implementation (pass 28)

`pt_digital` and `pt_core` default to `STREAM_V2=1`, using protected-header streaming without payload quarantine. `STREAM_V2=0` retains v1 for comparison, not as a runtime extra protocol. The 1,280-bit declared RX frame bank and its read pipeline are eliminated; declared data arrays fall from 8,576 to 7,296 bits. TX staging and all other FIFOs/capture/playback remain. The older storage description below describes the original v1 baseline. Both rate profiles pass finite functional tests in both variants. Canonical contract version 4 reflects v2; legacy queue-model evidence is explicitly separated. Current physical results and their limitations are in the pass-28 report.

## Current generic control-surface audit

`spec/contract.json:generic_control_surface` owns the external capability-to-service
mapping; `robustness-envelope.json:control_surface_coverage` reports the gaps.
Protocol names appear only in the external requirements, never in a chip opcode.
The inspected physical skeleton and control RTL do **not** implement the entire
intended control surface.

| Generic service | Existing boundary | Required extension / qualification |
|---|---|---|
| Atomic numeric configuration | SPI enable/mode and RF/wired/clock 16-bit trims; behavioral numeric validators | Defined fields and atomic apply/ack for compatible settings; trim storage alone has no physical semantics |
| Clock readiness/loss | Clock outputs from analog macro; behavioral qualification and recovery | Source/CDR status, missing-clock event, bounded observation and recovery |
| Wired electrical controls | `wire_trim`, `wire_idle`; separate electrical models | Swing, postcursor, termination, DC mode and receiver-detection control/status |
| USB local pad state | Bidirectional `WIRE_RX`; behavioral HS/FS/LS pad model | Timed drive/termination/pull changes, squelch and disconnect observations |
| Timed actions | Mathematical event services; small current stream command set | Generic scheduled state/burst/gap actions with epoch, capacity, late policy and apply latency |
| RF direction and tuning | RF trim/mute, numeric settings and transition budget | Independent same-channel direction/gain/filter changes, settling and useful overload status |
| Continuous stream | FIFO/gearbox/transport/pacing candidates | One selected physical bridge with latency, occupancy and safe underrun behavior |
| Recovery | Candidate SPI mailbox 0x30–0x36, behavioral mailbox | Actual `pt_control` registers and live RF/wired/host reset/epoch integration |
| Board coordination | External FPGA GPIO ownership | RF switch/PA, USB VBUS, display sidebands and SDI frontend timing included in budgets |

`pt_control` currently resides in `rtl/pt_spi.sv`: write address 1 enables;
2 selects mode; 0x10–0x12 store trims; 0x20–0x26 service diagnostic memory/status.
The recovery mailbox addresses are not implemented there. The three trim words
cannot be counted as arbitrary fast reconfiguration or complete protocol control.
The fast framed reference currently permits no-op, wired idle and RF mute;
that is not a complete scheduled electrical-state service.

No worst-case serialized-command-to-pad latency is yet qualified for these
services. A behavioral callback timestamp, an SPI write edge and a pad effect
are different events. For deadline-critical operation, prearmed generic actions
need explicit lead time and local timing; asynchronous host decisions cannot be
assumed instantaneous. Keep bounded local event/CDC storage, not packet buffers.

The joined packet model now holds a bounded DAC prefill
until a timestamped stream-consumption start, while converter clocks keep
running. An RF-mute bit alone does not provide that behavior: draining samples
while muted would empty the buffer before launch. Treat sample consumption,
output unmute and late/underflow cancellation as explicit generic apply events;
a finite mathematical queue now exercises them, but the present physical
control boundary has not demonstrated them.

All original targets plus HD-SDI, custom GFSK/SDR and the two existing RF stretch
goals are mapped. USB and PCIe remain lifecycle anchors; this prioritization does
not drop SATA OOB, TMDS multi-chip alignment or any other target. Continue the
mathematical interface work before new RTL/schematic implementation.

## Physical interface

The top-level has exactly 50 terminal bits: 20 data, 2 host clocks, 4 SPI, reset, reference, 8 analog and 14 power/ground. This is a logical connection contract, not a pad placement, package assignment, ESD network or electrical qualification. `pt_host_physical` owns the GPIO pads and DDR gearbox; `pt_analog_physical` owns RF/wired pads and the analog/clock hierarchy. Domain names are logical load groups, not proven independent external rails. Provider-compatible fixed power/ground connections take precedence; qualify any local isolation behind that boundary.

The digital host word clocks are 250/312.5 MHz. DDR host pin clocks are 125/156.25 MHz. A host macro must produce one correctly ordered 10-bit word per internal clock without missing either DDR edge. This high internal frequency is an explicit GF180 timing risk; structural synthesis cannot establish feasibility. A two-word-wide implementation is a possible refinement if timing fails, with corresponding scheduling changes.

Wired parallel clocks are nominally 125/250 MHz; serialized order is bit 0 first. RF samples are `{Q[11:0], I[11:0]}` in signed two's complement, with 8-bit mode transporting the most significant eight bits of each channel. Clock synthesis, actual CDR, PLL lock gating, converter latency and playout clock tracking remain physical macro requirements. The host must provide source-matched playout rates; finite FIFOs cannot tolerate permanent independent producer/consumer drift.

## Configuration and physical-macro boundary

Candidate mathematical command payload (`resource_configuration.py`):

| Bits | Meaning |
|---|---|
| 1:0 | Resource owner: 0 none, 1 wired, 2 RF; 3 reserved |
| 4:2 | Line-rate target: 0 legacy/default, 1 480 Mb/s, 2 1.25 Gb/s, 3 1.5 Gb/s, 4 1.62 Gb/s, 5 2.5 Gb/s, 6 742.5 Mb/s, 7 1.485 Gb/s |
| 5 | Host frame length: 0 64 words, 1 8 words |
| 6 / 7 | Independent wired TX / RX enables |
| 8 | Pad path: 0 serial, 1 bidirectional |
| 31:9 | Reserved, must be zero |

This mathematical payload is not yet a registered RTL command. Non-wired
ownership rejects non-default wired rate/framing/path fields; reserved encodings
and invalid types reject. Exhaustive codec tests accept 136 of 512 words.
`ResourceConfigurationCommands` dispatches through the existing serialized queue;
stopped-state, pad isolation and resource constraints are checked at application.
No protocol IDs are encoded.

In isolated canonical copies, a 1.62 Gb/s RX-only write applies at 6.45 us and
replies at 12.85 us. Reserved/stale writes preserve resources, active writes
reject, and eight causal RX words return after normal acquisition. Reference and
RF-disabled optimized implementations report matching functional outcomes.
Source-checked reports are `evidence/resource-command-reference.json` and
`evidence/resource-command-optimized.json`. Synthetic framing and ideal host-word
observation do not establish peer interoperability or electrical capture.
Main-model integration is installed after the reference control test passed;
fresh regression is running.

The isolated raw-event return candidate adds `record_return_configure` to the
same management queue: payload 0 disables the alternate return interpretation,
1 enables it, and all other bits reject. Selection is stopped-only; enabling
requires short-frame wired ownership with RX enabled. It selects a generic
transport format, not a USB or other protocol mode. Six recording-callback queue
checks pass apply timing, enable/disable, reserved payload, changed permissions
and stale epochs. The corrected coupled serialized-selection-to-pad-return experiment passes
normal acquisition, ordered delivery and lifecycle guards; its source-checked
report is `evidence/record-return-serialized.json`. RTL address allocation and
main-model requalification remain open. The ordinary host-input interpretation remains unchanged.


The physical ABI must support the configuration combinations exercised by the
external recipes in `spec/contract.json`. There is no protocol-ID or profile
selector. Expose resource ownership, separate serial rate and host-clock controls,
local output-enable/termination states, timestamped events and bounded ready/fault
handshakes. The current `mode8` and trim ports do not encode that ABI; adding
USB pin direction alone does not implement USB or the other new modes.

`WIRE_RX_P/N` is now `inout` at both the chip and analog black-box boundaries,
aliasing USB D+/D−. Serial modes use it as input; USB mode connects the local
HS/FS/LS branch, disables serial termination/detection, and leaves WIRE_TX high
impedance. Reset and unpowered behavior must release both branches safely.
Mode selection requires stopped operation and break-before-make controls.
Serial TX/RX remain independently timed for full-duplex links.

The analog macro owes USB single-ended line observation, squelch/disconnect,
HS termination/current drive and FS/LS drive/pulls. A bounded local sequence
engine emits timed states and reports events to FPGA; it does not own protocol
CRC, USB transactions, SATA link logic, DP training policy or RF modems.
The host macro reuses its existing queues, header codec and staging banks with
a configurable eight-word frame counter and slot mask for response-critical traffic. No constant-zero tied control may be presented as
working support. Reject unsupported control combinations until their required controls
and data paths are implemented.

### Independent shared-pad electrical controls

This is the normative required macro boundary, not a claim that current RTL
ports or `SharedWiredPad.configure()` implement it. Preserve one generic pad
state vector; the FPGA supplies protocol sequences. A speed/role convenience
function may construct vectors in a testbench, but must not hide unavailable
hardware actions.

| Resource | Independent configuration / action | Required observation |
|---|---|---|
| Weak bias on each leg | Enable/disable pull-up and pull-down independently; select supported resistance and pull-up source | Applied state, pad level; source and voltage limits declared |
| Termination | Enable each supported termination path independently of driver enable and weak pulls; trim resistance and bias while stopped | Applied state and settling qualification |
| Active drive | High impedance, voltage drive or current steering; output enable, polarity/level and numeric strength | Applied state, electrical fault where detectable; no inferred protocol state |
| Receive sensing | Differential receiver, both single-ended comparators, squelch and detection thresholds independently enabled | Timestamped raw/qualified levels with explicit threshold, filtering and latency |
| Capture/playback | Start/stop sample or bit delivery independently of passive pad state | Epoch, alignment, overflow/underrun and stopped status |

Only physically realizable combinations are accepted. Examples needing explicit
validation include weak pull plus a peer-driven reset state, current drive
with the selected passive load during negotiation, and passive termination
changes while the remote transmitter remains active. Required ranges and
current-source compliance remain circuit-feasibility gates; exposing a field
does not prove its range. The peer's state is a bench stimulus or observation,
never a command the chip can enforce.

Distinguish two kinds of transition:

1. **Topology or trim change:** stop local active drive and capture/publication
   as required, apply break-before-make, wait the declared settling interval,
   then qualify and acknowledge the applied vector. Switching serial/DC branch
   ownership belongs here. A peer can still be electrically active; the selected
   pad topology must tolerate that state or the operation must reject it.
2. **Prevalidated live electrical action:** apply only its allowed mask of
   output enable, level, weak-pull or termination bits at a scheduled boundary.
   Preserve unrelated receive sensing and clock state. Local output release
   must not imply removal of every pull or termination. Do not require a remote
   driver to release merely because the local FPGA changes a passive state.

Each accepted action needs an epoch, apply timestamp or bounded immediate
latency, and applied-state acknowledgement distinct from command receipt.
Unsupported combinations and missed deadlines leave the prior valid state or
enter an explicitly specified released-drive fault state; never silently apply
a partial new vector. Fault policy specifies which passive loads remain so
that 'safe' is not an ambiguous blanket disconnection. Device-off leakage and
externally driven voltage tolerance must hold independently of software.

**Architecture decision:** extend the generic electrical-state boundary rather
than add a USB negotiation engine or protocol profile. No extra package pins
or packet buffers are allocated by this decision. The event storage, command
fields, state interlocks, comparator delays, switch charge injection and
settling cost still require implementation and joint lifecycle verification.
The existing probe sequence that jumps from FS to HS remains partial evidence.

The mathematical pad now exposes `set_local_passives()` with independent
per-leg pull-up, pull-down and termination resistance (or disconnected state).
It changes only the local passive network, preserving the remote drive/load and
existing capacitor voltage. This is an instantaneous equation-level apply, not
a serialized command implementation. Its resistor/supply energy accounting and
legacy-state equivalence are checked in `verification/test_shared_pad_controls.py`.
`set_local_drive()` now independently selects released, voltage or current drive
with numeric strength and physical leg/levels. A bounded local current source
can operate against a remote voltage drive; competing voltage drives are
rejected. `sense()` exposes ideal single-ended high/low, differential polarity
and squelch at supplied numeric thresholds. These functions preserve the peer's
configuration and do not infer protocol states.

A tested intermediate sequence removes a local pull, applies 18 mA to N while
the peer continues driving SE0, then releases local current. The observed
voltage matches the explicit parallel resistance and instantaneous power
balance. This proves representability of an electrical intermediate state,
not valid USB chirp amplitude or timing. Seven focused tests plus both legacy
role probes pass. Scheduled apply, sensing delays/hysteresis, physical range
qualification, switch charge injection and complete negotiation remain open.
The affine step refuses active-current operation outside its compliance region;
the nonlinear electrical primitive is required there.


DisplayPort AUX/HPD and USB VBUS switch/sense connect externally to FPGA GPIOs.
Their clocks, levels and response latency belong in peer tests, even though
they consume no transceiver terminals. The chip does not drive 5 V VBUS.
RF control includes channel contexts, timed gain/bandwidth settings and local
RX/TX direction changes while the oscillator remains warm. Carrier retuning,
ADC sample rate, sample format and transport profile are independent controls.

## Circuit obligations

| Block | Candidate starting point | Work still required |
|---|---|---|
| USB local branch / shared-pad isolation | Architecture requirement; no transistor implementation | HS/FS/LS electrical states, finite driver/termination and off-state capacitance; retain 2.5 Gb/s serial RX margin |
| Timed state/event service | Architecture requirement; no fast-path ABI implemented | SATA OOB, USB line transitions, RF bursts, FPGA response deadlines and reset-safe ownership |
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

Explicit declared array storage is 8,576 bits: wire ingress 640, RF ingress 384, packed-I/Q ingress 320, wire egress 1,280, packed-I/Q egress 320, RF egress 1,536, TX/RX frame banks 2,560, capture/playback 1,536. Reservoirs, pointers, synchronizers and other registers are additional. Synthesis can optimize unused frame-bank locations. These actual capacities supersede any inference that the earlier abstract FIFO allocations describe this implementation. Memory macro mapping, total core area and power remain open; the current 0.85 mm² memory allocation is unproven.

SPI is mode 0, MSB first, 32 clocks under CS: command/address/data = 8/8/16 bits; command 0x80 writes and 0x00 reads. This is a candidate local ABI, not demonstrated compatibility with another Svalbard control interface. Register decoding is in `rtl/pt_spi.sv`. Program while disabled, initialize all 32 playback samples before playback, then enable. Mode and trim changes while enabled are rejected. Capture/readout is finite and useful to MCU hosts; streaming requires sufficient FPGA GPIO bandwidth.

## Verification and limitations

Run `make transceiver-baseline`. Pinned Docker tools run both streaming profiles for about 60 microseconds, compare wired/IQ samples, inject a CRC error, check sticky fault/reset, exercise SPI, capture/playback, PRBS and calibration, and perform structural synthesis. An independent Python codec decodes all clean complete RTL-generated frames. The ideal converter model is compile-checked only; its analog behavior and the wire model are not yet integration-tested.

Passing these checks establishes a useful refinement baseline. It does not establish arbitrary phase/frequency behavior, CDC/STA closure, acquisition after arbitrary DDR bit slips, SSC tolerance, fast-command physical timing, FPGA protocol integration, memory placement, rail/package behavior, DRC/LVS or tapeout readiness. SPI status is a synchronized diagnostic snapshot, not an atomic event log. Trim crossings rely on programming while disabled and require implementation constraints. Reset release is synchronized in each FIFO domain; reset/enable sequencing across the entire physical clock tree remains to be qualified.

Next broad pass: implement and test the host DDR macro and full-chip functional harness, select concrete converter and clock circuits, integrate candidate RF/wired transistor hierarchies, then map/place the actual digital logic. Keep circuit failures and area/timing violations visible; do not reduce the intended first-chip capability silently.


## USB reuse order

Extend the wired island before adding specialized hardware:

| USB function | First implementation choice | Unresolved requirement |
| --- | --- | --- |
| 480 Mb/s timing | Existing wired synthesizer/divider services; evaluate 2.4 GHz divided by five | Jitter and divider phase; no additional PLL selected |
| HS receive | Existing slicer, multiphase sampler and CDR/phase-selection circuitry | Keep frequency reference warm; acquire each burst during SYNC, not a microsecond PLL restart |
| HS transmit | Reconfigure segmented wired current-source cells into the local bidirectional pad branch | USB current, termination, slew, disconnect behavior and disabled loading |
| Squelch/line detection | Existing envelope/threshold detector designs with mode-specific thresholds | Fast burst detection plus slow FS/LS single-ended observations |
| FS/LS drive and pulls | Existing GF180 switch/resistor/output-device primitive families | Additional local single-ended circuits are needed; they cannot be inferred from a differential slicer |
| FPGA transport | Existing framing, parity/guard, queues and two staging banks, shortened to eight words | Canonical/RTL frame-counter and event-ordering integration |
| Chirp/reset/idle sequencing | Existing generic timed-pattern/line-state controls | Actual peer state machine and acceptance timing still need modeling |
| Calibration/bias | Existing shared reference, trim and sequencer | Mode-specific current/termination trim and settling |

Physical current-source/slicer sharing is a proposed topology, not proof that
remote TX cells can reach RX pads without unacceptable parasitics. Prefer a short
local branch over a die-wide mux. No additional radio chain, PLL, protocol CPU,
CRC engine, GPIO interface or package pin is selected by this USB work.

USB-IF EL_18 requires HS detection, timing acquisition and SYNC recognition within
12 bit times (25 ns). Treat warm sampling/phase acquisition as a separate major
gate: the passing 340 ns response-budget calculation does not prove it.

## Generic multi-instance video PHY requirements

`configure_wire_interface` specifies stopped electrical (`ac_differential` or
`dc_current_sink`) and clock (`embedded` or `forwarded_word`) modes, without a
protocol ID. Forwarded-word mode requires line rate = 10 * REF_IN rate. The
mathematical configuration has a management-dispatch payload (below); RTL register
address allocation, PLL divider reset/phase control and pad circuitry remain
unimplemented obligations.
Generic resource rate codes 6/7 now select 742.5 Mb/s and 1.485 Gb/s; prior codes
are unchanged. Each chip transports one opaque ten-bit lane using existing frames.
No on-chip TMDS encoder, lane bonding, packet engine or new pins are introduced.
FPGA/board logic owns three-lane launch/deskew and clock-pair electrical conversion.
See the [physical/pin plan](../../../docs/roadmap/programmable-transceiver-pin-plan.md#hdmidvi-through-multiple-instances).

The generic `configure_wire_interface` mathematical management command uses bit 0
for AC differential (0) / DC current sink (1), and bit 1 for embedded timing (0) /
forwarded word reference (1). Bits 31:2 are reserved and reject. Forwarded mode
derives its reference from the selected serial rate divided by ten; currently
only 742.5 Mb/s and 1.485 Gb/s selections are admitted. Application checks stopped
wired ownership through the existing interface method. Resource changes restore
the default AC/embedded interface, so configure resources first and interface
second. This is a generic combination of settings, not a protocol command.

Recording-callback queue tests cover delayed application, replies, reserved bits,
changed permission and stale epochs at both rates. Canonical dispatcher checks
cover switching interface modes and rejected-write preservation without analog
time advancement. End-to-end acquired operation through the coupled management
queue remains unqualified; these tests do not establish pad or PLL implementation.

### Generic tuning extension target

Expose reference ratio/divider, filter-bank selection, converter clock divisor
and PGA trim independently of protocol names. The behavioral numeric configuration
is not yet an RTL/register ABI. Keep the existing legacy resource-word encoding
stable until a versioned mapping is defined. Reuse existing blocks and retain the
provider-compatible 74-site, single-slot allocation; added switches/dividers and calibration need
an area/power estimate before accepting the cost. HD-SDI requires external coax
analog circuitry. RF and wired payload remain mutually exclusive per die.


## Selected converter width boundary

The provisional first-chip choice is native 10-bit ADC/DAC conversion targeting
8 ENOB, with existing 12-bit signed I/Q transport words. Do not treat transport
width as physical precision or instantiate separate converters for each word
format. For the 12-bit format, sign-convert the native ADC result and left-align
it by two bits; the low two bits are zero before any external processing. DAC
input rounds to the nearest native 10-bit code and saturates at its rails rather
than wrapping. Existing narrower transport settings are quantized representations
of the same converter, not extra ADC/DAC instances. The current mathematical
quantizer/word-width coupling is a legacy abstraction to migrate; it does not
prove this selected converter implementation or its effective resolution.
