# Digital/analog integration contract

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

The normative design is `spec/analog-architecture.json` with `spec/contract.json`.
The existing RTL and `pt_chip.sv` are incomplete implementation scaffolding,
not the selected complete chip. Their old top-level synthesis, placement and
regression flows have been retired. Retained component checks establish only
their stated local behavior; no resulting netlist is ready for fabrication.

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

The normative startup/fault/recovery sequence is
`analog-architecture.json:system_lifecycle`. Management must survive loss of
REF_IN and both payload clocks while DVDD is valid. `RecoveryMailbox` now advances
on `management_edge()`, not a reference edge; COMMIT=0 abandons only uncommitted
shadow fields. These semantics remain requirements for the control RTL.

The selected bond map has 74 provider sites: 37 functional signals, 18 fixed
supply/return sites and 19 spare signals. The older logical RTL power-port count
is not the assembly pin count. `pt_host_physical` owns the GPIO pads and gearbox;
`pt_analog_physical` owns RF/wired pads and the analog/clock hierarchy. Domain
names are logical load groups, not independent external rails. Provider fixed
power/ground connections take precedence; qualify local isolation behind them.

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

#### Disabled branches remain electrical loads

Use branch-local isolation rather than one switch in series with every fast
signal. Keep the serial path short; isolate USB drivers, pulls and termination
at their branch roots, and bypass/isolate the TMDS input divider in serial/USB
modes. A disabled enable does not remove drain capacitance or protection clamps.

| Pad owner | Enabled path | Required inactive state |
|---|---|---|
| Serial RX | Serial termination, divider bypass, CTLE/CDR | USB loads off; TMDS divider disconnected |
| TMDS RX | External pullups, level divider, CTLE/CDR | Serial shunts and USB loads off |
| USB | Independent HS/FS/LS drive, sensing and passive state | TMDS divider isolated; serial termination off; unused TX pair released |
| Serial TX | Main/postcursor driver or detection injection | TMDS off; detection source disconnected outside detection |
| TMDS TX | Current-steering branch | Serial drive and detection injection off |
| Reset/unpowered | Released active drive | Specified leakage/voltage tolerance without software or powered isolation gates |

Budget pad/protection capacitance plus every inactive branch's residual
admittance, including mutual terms, voltage dependence and powered-off clamps.
Include switch resistance and charge injection during transitions. The model's
aggregate `off_cap_f` is an assumption, not extracted proof of this inventory.
`SharedWiredPad(off_branches_f=...)` now accepts named P/N branch capacitances
instead of that aggregate, preserving mismatch in its electrical and energy
equations. Explicit branches replace the aggregate without double-counting.
Optional `rail_clamp` and `ground_clamp` parameters add finite threshold/resistance
currents to the coupled electrical equations, including rail backfeed and
dissipation while branches are isolated. They are supplied hypotheses, not PDK
extractions. The affine standalone solver rejects these nonlinear configurations.
Omitting clamps means protection is unmodeled, not proven power-off tolerant.
Board coupling and TMDS pullups are application-specific population choices.

Reject any implementation whose inactive branches violate voltage tolerance
or active-path loading. Resize/isolate the offending branch and recheck its
own settling and resistance; never rescue a case by removing its parasitics.
Protection and isolation must satisfy powered, reset and unpowered states.

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
| Converters | Selected inventory parameters and `verification/converter_dynamics.py` | Transistor realization, achievable ENOB and sample rate; transported width is not native precision |
| Reference/LO/clocks | Trim and calibration interfaces implemented digitally | PLL/VCO, divider/phase network, clock mux/reset sequencing, lock monitoring |
| Host pads/DDR | Existing native-pad experiments | Real DDR gearbox, input/output phase adjustment, host timing, simultaneous switching and rail closure |

The listed circuit files are reuse candidates, not validated components of this chip. No full RF chain, RF-to-host simulation or analog hierarchical netlist has been completed in this pass. Ideal models do not establish GHz operation, Wi-Fi performance, protocol compliance or achievable ENOB.

## Digital contents and costs

Use `check_contract.resource_ledger` and the selected bridge/storage inventory
for current allocations. Do not price the intended chip using the retired
concurrent RF/wired top level or its capture/playback and frame-bank totals.
Independent FIFO and codec mappings are component evidence; parent/child
instances must not be double counted. Complete digital area, switching power,
CDC and physical timing remain implementation obligations.

## Verification and limitations

`make transceiver-math-fast` checks current behavioral interfaces and inventory
bindings. Current electrical/lifecycle commands are in the
[model guide](../system_model/architecture_fast/README.md). Retained RTL FIFO
and codec controls are separate from whole-chip conformance. No obsolete
`transceiver-baseline` result qualifies the selected control ABI or macro boundary.

Finish mathematical closure before schematic/layout implementation. A callback
timestamp does not prove command-to-pad latency; a structural netlist check
does not prove the physical clock tree, analog startup, CDC or package behavior.

## USB reuse order

Extend the wired island before adding specialized hardware:

| USB function | First implementation choice | Unresolved requirement |
| --- | --- | --- |
| 480 Mb/s timing | Existing wired synthesizer/divider services; evaluate 2.4 GHz divided by five | Jitter and divider phase; no additional PLL selected |
| HS receive | Existing slicer, multiphase sampler and CDR/phase-selection circuitry | Keep frequency reference warm; acquire each burst during SYNC, not a microsecond PLL restart |
| HS transmit | Reconfigure segmented wired current-source cells into the local bidirectional pad branch | USB current, termination, slew, disconnect behavior and disabled loading |
| Squelch/line detection | Existing envelope/threshold detector designs with mode-specific thresholds | Fast burst detection plus slow FS/LS single-ended observations |
| FS/LS drive and pulls | Existing GF180 switch/resistor/output-device primitive families | Additional local single-ended circuits are needed; they cannot be inferred from a differential slicer |
| FPGA transport | Selected 100 MHz SDR direct byte/control stream with finite CDC/credit queues | Complete loaded electrical lifecycle, RTL and physical I/O timing |
| Chirp/reset/idle sequencing | Existing generic timed-pattern/line-state controls | Actual peer state machine and acceptance timing still need modeling |
| Calibration/bias | Existing shared reference, trim and sequencer | Mode-specific current/termination trim and settling |

Physical current-source/slicer sharing is a proposed topology, not proof that
remote TX cells can reach RX pads without unacceptable parasitics. Prefer a short
local branch over a die-wide mux. No additional radio chain, PLL, protocol CPU,
CRC engine, GPIO interface or package pin is selected by this USB work.

USB-IF EL_18 requires HS detection, timing acquisition and SYNC recognition within
12 bit times (25 ns). Treat warm sampling/phase acquisition as a separate major
gate: a passing response-budget calculation does not prove it.

## Generic multi-instance video PHY requirements

Expose numeric electrical mode and embedded/forwarded timing settings without
a protocol ID. Forwarded TMDS timing requires the line rate to be ten times
the word-reference rate, including supported fractional video clocks. Each
chip carries one opaque lane; the external FPGA owns TMDS encoding, multi-lane
coordination and protocol state. Use `resource_configuration.py`,
`video_alignment.py` and the selected wired benches for current behavior.
The retired mathematical dispatcher and its bit-field command are not an ABI.

Cross-chip reset/phase alignment, continuous queue service, electrical pad
limits and reference-path qualification remain separate requirements. Frozen
clock or recording-callback controls cannot prove acquired operation through
a coupled command, clock and pad path. See the
[physical/pin plan](../../../docs/roadmap/programmable-transceiver-pin-plan.md#hdmidvi-through-multiple-instances).

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
of the same converter, not extra ADC/DAC instances. Selected converter benches must obtain native precision and timing from the
architecture inventory; explicit alternative quantizers remain local controls.
Neither transported width nor a mathematical conversion proves effective
resolution or physical implementation.
