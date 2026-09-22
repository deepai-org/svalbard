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

The experimental `verification/fast_exclusive_engine.py` adapter now gates payload admission and session enables. Its RF→wired→RF test passes capture/receive, overlap rejection and stopped transitions. This is not the default model or RTL: inactive bias/clock shutdown, serialized selection, full duplex and complete calibration invalidation coverage remain open. Evidence: `evidence/fast-exclusive-engine.json`.
