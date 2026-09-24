# RF / wired mutual exclusion and resource sharing

User decision, 2026-09-22: the same fabricated chip must support both RF and
wired operation, but they do not need to be active at the same time. This
supersedes earlier requirements for simultaneous RF/wired payload operation.
Encourage additional physical sharing where it preserves each mode's goals.
Both functions remain required on the full first chip; this is not a smaller
feasibility chip. Existing 50-terminal / one-slot constraints remain in force.

## Operating contract

Active engine is NONE, RF, or WIRED. Never enable RF and wired payload paths
concurrently. RF mode retains the RF TX/RX functionality; wired mode retains
the full-duplex wired lane. This decision does not remove either engine's own
TX/RX requirements. Host transport, SPI, reference input, management and the
resources needed by the selected engine remain available. Inactive front ends
must be isolated and their unnecessary bias/clock activity disabled.

A mode change must stop payload acceptance, finish or explicitly cancel pending
work with accounted data loss, isolate outputs, release shared resources,
switch configuration, establish bias/reference settling and clock qualification,
then permit new traffic. Carry neither stale FIFO data nor a previous mode's
calibration-valid flag into a new mode without a defined validity check.
Break-before-make ownership applies to analog switches and clocks. Instantaneous
switching and zero reacquisition latency are not required.

## Protocol-independent configuration

User decision, 2026-09-24: the chip has no protocol profiles or protocol-ID
register. It accepts supported combinations of resource ownership, line and
sample clocks, pad topology, TX/RX enables, termination/pulls, filter/gain,
converter format, host framing and calibration settings. Validate electrical
conflicts and implemented ranges, not protocol names. RF and wired payload
ownership remains mutually exclusive.

The named entries in `spec/contract.json` and the protocol plan are external
FPGA configuration recipes and verification targets. They do not prescribe
on-chip presets or protocol controllers. Direction changes and timed line-state
sequences can be local operations; changes requiring clock/bias/route ownership
transfer must stop, isolate and requalify the affected resources.

`configure_resources` is the mathematical chip API for the currently modeled
rate/path/direction/framing combinations. `ProtocolService` and the factory's
optional `protocol=` argument remain testbench conveniences that translate names
into ordinary settings. The chip never reads their selected name or role.
The register ABI and RTL still need to encode these independent controls.

The low-level ownership selector also rejects transfer while either end drives
the shared bidirectional pad. Configuration changes advance a mathematical
resource-generation token; external saved-setting contexts must match it before
requesting a hop. This is a model validity token, not a protocol selector or a
new pin/register requirement. Rejected transfers preserve ownership and token. Successful ownership changes
isolate the bidirectional branch while retaining its capacitor voltage history.

## Sharing direction

| Resource | Design direction | Remaining condition |
| --- | --- | --- |
| Host GPIO, SPI, framing, capture/playback memory, calibration sequencer | One common physical service, owned by selected engine | Rebudget slots and buffers for exclusive modes; reconcile RTL |
| Reference input, bias master, trim storage, maintenance ADC, diagnostic mux | Share with switched observation and per-mode settings | Settle, release ownership, account load and invalidate stale calibration |
| TX synthesis | Evaluate one retunable PLL/VCO bank with mode-specific dividers and clock branches | Must cover RF and wired rates, jitter/phase noise and acquisition; not yet selected or proved |
| PLL acquisition counters, PFD/charge-pump/filter resources | Evaluate reuse with selectable loop parameters | Clock topology must still support independent wired RX CDR while wired TX runs |
| Local gm-C/filter, comparator and sampling resources | Reuse compatible instances through bounded local routing | Prove bandwidth, noise, impedance and switch parasitics in each configuration |
| RF versus wired pads, protection, LNA/mixers, termination/EQ and line drivers | Keep specialized provisionally; seek sharing only with evidence | RF matching and wired electrical requirements differ; no automatic pin or front-end merger |

A shared circuit must be a single instantiated resource with explicit ownership,
not merely two copies of the same design. Do not force a shared GHz analog path
if routing and switch loading cost more than the saved circuitry. Likewise,
retain independent wired RX timing where needed for a full-duplex wired link.

## RF-band stretch goals

User decision, 2026-09-23: include both of the following as stretch goals:

- **Lower-frequency RF operation on the chip.** Evaluate reuse of the I/Q
  converters, baseband filters, gain stages and mixers with suitable LO division
  or tuning and RF input/output configuration. Select supported bands only after
  checking the complete RX and TX paths, including quadrature generation,
  matching, noise, linearity, images, filtering and calibration. No particular
  sub-GHz band or continuous broadband tuning range is presently guaranteed.
- **Other-band operation through external frequency conversion.** Evaluate a
  board-level up/downconverter that translates an external RF band into a range
  the chip can transmit and receive. Account for external LO phase noise, images,
  spurs, conversion gain/loss, filtering and TX/RX routing in end-to-end signal
  quality. The converter and its LO are explicit board resources, not additional
  on-chip capability or an implied single-chip radio for that external band.

Both extensions should reuse the selected RF engine and existing terminals where
possible, retain RF/wired payload exclusion, and respect the one-slot / 50-terminal
chip boundary. Any proposed additional chip resources require an explicit budget
assessment. Neither extension replaces the required approximately 2.4 GHz radio
or wired profiles, nor delays closure of their highest-risk gaps. Current
mathematical and circuit evidence does not qualify either stretch goal; adding
them to this plan does not expand the verified tuning range.

## Implementation and evidence status

The active behavioral model enforces exclusive payload ownership and checks
stopped RF/wired handovers, overlap rejection and epoch invalidation. Earlier
compositions may permit concurrent operation. Complete RTL/physical interlocks,
inactive-domain shutdown and settling qualification remain open.
Historical simultaneous four-path tests remain useful optional stress evidence,
but they are no longer a required product capability or a closure gate.
Qualification must cover RF-only, wired-only, prohibited overlap and transitions
in both directions, including cancellation, settling, clock qualification and
shared-resource ownership. Existing rate profiles and pin allocation are retained
pending deliberate rebudgeting; this decision does not itself authorize claims
of higher sample rates, fewer terminals or a smaller die.

The experimental `verification/fast_exclusive_engine.py` adapter now gates payload admission and session enables, including RF descriptors, wired TX queue insertion and local-playback management. Inactive-engine ingress rejects before modifying queue or descriptor state. Its RF→wired→RF test passes 32-sample simultaneous RF TX/RX in both rate profiles, wired receive, overlap rejection and stopped transitions. Each RF entry performs and commits loaded-monitor calibration using relative-gain semantics before transmission. Capture-memory contents match the resulting ADC words; this checks functional flow, not RF signal quality or absolute pad gain. Serialized engine-selection transactions have a separate passing check (`fast_exclusive_management_check.py`). This is not the default model or RTL: inactive bias/clock shutdown, pin-level selection, sustained duplex and complete calibration invalidation coverage remain open. Evidence: `evidence/fast-exclusive-engine.json`.

The loaded-traffic runner with `--exclusive` also passes both rate profiles with count-free RF TX/RX over a finite record, then timed lossy stop. It verifies DAC ordering, ADC host-return agreement, queue bounds, converter accounting, loaded-output isolation, and zero wired accepted/transmitted/returned payload. See `evidence/fast-exclusive-rf-traffic.json`. This does not qualify indefinite service, RF waveform quality, or inactive analog clock/bias shutdown.

Clock dependency is now explicit through `clock_required(engine)`: the concurrent baseline requires both PLLs; the exclusive adapter requires only the selected engine’s PLL. Acquisition still requires the shared reference and existing host/settling gates. An inactive PLL unlock must neither block acquisition nor stop payload, while selected-PLL lock loss must quiesce it. Injected lock-detector tests cover both selections in `fast_exclusive_engine_check.py`; report status and hashes are authoritative. Oscillators still advance in this intermediate implementation: actual shutdown, restart/settling, and bias-current/load transitions remain open.

An experimental `SwitchablePLL` in the exclusive adapter module now represents a stopped VCO with frozen output phase, explicit exponential loop-filter leakage, rejected off-state edge requests, and fresh lock qualification after divider rephasing on restart. Its standalone checks cover phase continuity, leakage subdivision and reacquisition. The baseline exclusive adapter does not install it. An experimental `PoweredExclusiveChip` now connects it to engine selection, stops both oscillators before enabling the selected one, isolates outputs through the existing stopped transition, and guards clock readiness and RF calibration with a configurable settling deadline. The 1 ms leakage fixture is an assumption, and bias startup, output gating and supply-current transitions still need integration and circuit evidence.

Run `verification/fast_exclusive_engine_check.py --power-gated` to check the powered composition; `evidence/fast-powered-exclusive-engine.json` is its separate result. A 20 us guard fixture was also checked with a PLL already locked at 8 us: the session remained acquiring until the guard expired. The default 2 us guard is an assumption, not measured bias settling. This composition still uses two PLL instances and does not model bias current, supply transients or a physically shared synthesizer.

Both rate profiles now pass finite count-free RF TX/RX with `PoweredExclusiveChip` and the loaded output network (`evidence/fast-powered-rf-traffic.json`). Repeated checks during the run verify the wired oscillator is off with zero frequency and fixed phase; transport, queue bounds, conversion accounting and stop isolation also pass. This extends the powered lifecycle evidence to sustained RF transport, not waveform quality, wired-only duplex or physical bias-current behavior.

The powered lifecycle test now covers RF and wired duplex in both rate profiles on the same instance. Wired-only host return starts through `wire_return_start`, independently of RF ADC capture; 32 transmitted and 64 host-received words match exactly per profile with no added ADC samples. Detection is rearmed after stop, and duplicate or RF-mode return starts reject. These are finite nominal bursts; sustained wired service and receiver/error envelopes remain open. Evidence: `evidence/fast-powered-exclusive-engine.json`.

## Wired rail-feedback scheduling contract

The coupled RF candidate can forecast only until the next load-changing event.
Wired word launch and serializer half-bit sampling currently call `edge_time`
for a future phase target immediately. A target beyond the known supply history
must remain pending; it must not be extrapolated, mistaken for an oscillator
fault, or replaced by a fixed nominal bit period.

Implement bounded phase prediction as a distinct outcome: a valid target either
has a crossing within the supplied horizon or remains pending beyond it. Invalid
phase direction, nonpositive frequency and failed integration remain errors.
Keep the pending target phase and serializer stage intact. At each new analog
forecast, resolve both pending word and bit targets and choose the earliest
crossing together with external/converter/control events. If a crossing shortens
the interval, recompute the coupled forecast to that boundary before committing.
A switching impulse at the boundary changes the next forecast while preserving
oscillator phase and the already-serviced event ordering.

The scheduler must revisit pending targets even when their temporary deadline is
infinite; otherwise a short forecast silently stalls the serializer. A target
exactly at the horizon is serviced once. Reset cancels pending phase targets with
the existing partial-word accounting. Engine changes retain the existing stopped
selection and coarse-qualification rules.

Required evidence is actual wired TX/host RX traffic under coupled supply load,
with conservation of accepted/completed/aborted words, no duplicated boundary
bits, no lost pending edges, subdivision convergence and correct retiming after
host impulses. The current RF-only feedback pass provides none of this evidence.

The integrated candidate now implements this event contract and passes finite
TX plus incoming-RX/host-return tests in both wired modes. These tests include
host return switching charge, rail-sensitive clock timing, and an assumed
regulated wired termination load with explicit efficiency and bias. RF source and mixer signals stop with the RF oscillator;
retained filter/network state decays. RF and wired driver bias now follow engine selection. Shared reference bias
remains active; oscillator, converter, receiver and digital currents are still
incomplete, so this does not establish a whole-chip power-budget saving. Evidence: `evidence/fast-coupled-wire.json`.

## Multi-chip wired assemblies

HDMI/DVI is a supported design target through three single-lane instances plus
external clock-pair circuitry. Each die independently retains mutually exclusive
RF/wired payload ownership; bonding several wired chips does not relax this rule.
Protocol encoding, group alignment and sidebands remain outside the die. Expose
only generic line rate, DC sink/termination and forwarded-word clock settings.

[HDMI/DVI board and pin plan](../../../docs/roadmap/programmable-transceiver-pin-plan.md#hdmidvi-through-multiple-instances).

The external forwarded-lane supervisor can now bind to three distinct canonical
chip instances. Launch requires matching serial rates, DC pads, forwarded word
references, 64-word framing and uniform simplex direction. It snapshots chip
resource generations, interface generations and reset epochs. Every transfer
rechecks these: a wired-to-RF change or even an interface change followed by
restoration cancels the group and requires a fresh launch. This is board/model
supervision at transfer boundaries, not instantaneous silicon fault propagation.
Analog startup/lock and physical group-monitor latency remain separate gates.

The focused canonical forwarded TX/RX lifecycle checks now continue beyond
reference-loss draining: resource changes reject before acknowledgement; drain
acknowledgement rejects until the host discards its partial return frame. Correct
acknowledgements increment the epoch and permit RF ownership on the same chip.
The wired oscillator shuts down, RF bias/clock ownership activates without
claiming readiness, stale wired traffic rejects, and existing pad state is not
erased by the resource selection itself. These are ownership/epoch checks, not
RF payload reacquisition or conserved-energy handover. Residual DC-pad return current is retained through subsequent ownership changes
as described below; physical changes to external termination remain unmodeled.

A quiesced DC pad now detaches as an immutable state/time snapshot. Zero-drive
current and voltage decay are evaluated from that origin, so RF ownership or
logical channel reconstruction cannot erase its tail current. The analog owner
continues injecting that residual into the ground solve and checking compliance.
Reconstructing the DC path transfers its evolved differential/current/common-mode
states into the new channel and clears the detached owner, avoiding double
ownership. The canonical TX lifecycle checks positive decaying residual current
under RF ownership and exact restoration on DC reconstruction. Reference remains
absent, so reconstruction must stay acquiring rather than implicitly relock.
This assumes unchanged external termination; cable removal and other electrical
family remapping still require explicit circuit topology models.

### Behavioral handover enforcement

The fast composition tests RF -> forwarded wire -> RF -> forwarded wire on one
instance. Each stop invalidates the epoch and accounts for discarded RX/TX bits;
each restart waits the full declared acquisition guard. Traffic before startup,
stale epochs, active reconfiguration and stream clocks inconsistent with numeric
configuration reject without advancing lifecycle state. RF settings are removed
on wired ownership and wired clock settings are removed on RF ownership. Numeric
RF uses configured sampling with 12-bit I/Q; numeric wired uses rate/10 with
10-bit words. This verifies logical exclusivity and service accounting, not
physical power-down, switch leakage or analog settling during handover.
