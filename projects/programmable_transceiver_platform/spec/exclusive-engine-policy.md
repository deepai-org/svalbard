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

## Implementation and evidence status

The existing model/RTL still permits concurrent operation. It must be updated
to enforce this policy; documenting it does not implement the interlock.
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
