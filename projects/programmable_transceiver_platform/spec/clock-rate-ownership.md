# Clock ownership and sustained-rate obligations

`REF_IN` and `REF_IN_N` are one stopped-selected differential reference/LO
port. External timing is primary for qualification; autonomous paths remain
in scope. RF and wired payloads are mutually exclusive, but simultaneous wired
RX/TX, host activity and warm radio bias must be budgeted.

## Selected clocks

| Service | Clock owner and selected behavior |
| --- | --- |
| RF conversion | Actual carrier divided by 64/128/256/512; FPGA resamples the resulting rate. |
| Carrier-derived RF D2H | Physical LO/32 clock, DDR LO/16 words; H2D has 156.25 MHz physical clock and 312.5 Mword/s. |
| Warm-hop RF D2H | Host-follow /2: 78.125 MHz DDR from continuous 156.25 MHz H2D, independent of the retuned carrier. |
| Wired TX | Selected synthesizer/external timing and gear ratio, with numeric rate configuration. |
| Wired RX | Independent on-chip CDR; recovered data crosses a finite host queue. |
| Direct USB | 100 MHz SDR H2D/D2H host-follow, independent 480 MHz line clock and 240 MHz local TX FIFO consumer. |
| Scheduled actions | Physical H2D clock divided by `control_semantics.scheduler_clock_divider` (4). |
| Management/watchdog | Independent nominal 50 MHz oscillator, allocated 40–60 MHz; survives payload-clock loss. |
| Detection capture | Selected wired timing, 250–500 MHz; available before RX CDR lock. |

At H0 the action clock is 39.0625 MHz (25.6 ns ticks); at 100 MHz SDR it is
25 MHz (40 ns ticks). Derive from physical clock, not word rate. The eight-word
command plus two action cycles costs 76.8 ns at H0. Use the actual rate in other
configurations. H2D must continue through scheduled exchanges; its loss cancels
the timing contract. SPI/reset recovery is independent.

## Auxiliary clock connections

### Continuous receive and transmit acceptance

Use the same loaded clock envelope for data and queue timing. Qualify the CDR
against transition gaps, frequency offset and time-varying modulation together;
a constant residual-ppm holdover calculation does not establish SSC tracking.
Track accumulated phase through gaps using the integral of frequency error,
including loop lag, then add initial phase error and untracked jitter. An
extended quiet counter cannot repair an exceeded eye budget.

SDI acceptance includes sparse-transition and unequal-occupancy patterns,
external equalizer baseline behavior and recovery into ordinary traffic.
Electrical silence is distinct from an active signal without transitions;
continuous mode must not interpret the latter as permission to reset the CDR.
PCIe/SATA acceptance includes incoming modulation and idle/OOB handoff without
resetting analog history. Ethernet and video acceptance includes persistent
clock mismatch, finite queues and explicit fault/restart behavior, not just
short eye diagrams. Multi-chip video additionally requires physical skew
qualification; matching stream epochs alone is insufficient.

These are acceptance obligations on the selected independent CDR and timing
paths. Existing counter/state tests do not constitute analog loop evidence.

The [analog inventory](analog-architecture.json) makes three different clocks
explicit: H2D-derived scheduled-action timing above, an independent nominal
50 MHz management oscillator (40–60 MHz allocation), and a 250–500 MHz detector
capture clock. The detector clock comes from selected wired TX timing, enabling
at-most-4 ns interval capture even before RX CDR locks. None is an extra pin.
Management survives payload-clock loss; detector measurements do not imply
4 ns host-command latency. Cross-domain events require epoch tagging and CDC.

In HF REF_IN mode, the conditioner also divides the received clock by a
programmable integer1..256 to supply10–250 MHz acquisition reference to the
CDR/PLLs. The undivided high-frequency clock remains available for bypass.
There is still one differential input pair, not two independent references.

## Shared-reference lane alignment

`analog-architecture.json:video_alignment` and
[deterministic launch](block-diagram.md#deterministic-multi-chip-launch) define
one alignment service. Shared frequency is insufficient: phase-qualified divider
reset, an existing-SPI-clock epoch marker and fixed serializer pipeline establish
launch identity. Per-lane compensation is limited to 39 line UIs; board clock
distribution owns sub-UI correction. RX-CDR deskew is a separate service.

## SAR acquisition and local completion

The selected sample edge closes the acquisition aperture and launches bit
conversion; the track interval precedes it. A local completion sequencer
owns the nonuniform SAR bit intervals; it must not require another external LO
edge to finish an already launched conversion. The model allocates 20 ns for
those decisions. Local supply/reference validity is still required. LO loss
therefore stops future sampling edges but does not, by itself, reset held charge
or force an in-flight conversion to disappear. Explicit STOP, invalid supply,
or missed completion may require cancellation and retain separate obligations.

This is `contract.json:physical_services.sar_timing`, a circuit requirement within
the existing converter/control budget. It does not allocate another independent
sampling oscillator or validate local delay/handshake circuitry. Late results
must not be delivered as valid or overlap the next acquisition. The physical
busy/timeout implementation, delay variation and minimum comparator resolution
remain open. The package outage screen retains ADC switching activity for an
additional maximum conversion interval; its periodic current envelope is still
a hypothesis, not the current of an actual interrupted decision sequence.

Reference startup follows `sar_timing.startup`: the qualification interval
starts no earlier than actual reference-bias enable. Reinitializing or
discharging that reference invalidates readiness. The existing 20 µs guard
must be combined with clock, supply and reference/bias qualification; merely
receiving clock edges for 20 µs is insufficient. Warm payload STOP may retain
reference charge, as in the selected recovery model. The selected mathematical
replay enforces a fresh 20 µs interval after START or the latest invalid-to-valid
analog transition, whichever is later. Loss during payload faults the stream;
STOP/new epoch and requalification are required. It uses ideal model-observed
validity: reference within the assigned coarse 0.98–1.02 V window and evaluated
local supply within 2.5–3.6 V. This is bias qualification, not an ENOB guarantee.
Physical thresholds, sensing latency/accuracy, independent threshold source,
bias-enable observability and register-level fault encoding remain open.

## Turnaround is distinct from retuning

Same-channel RX→TX→RX retains LO, converter, host, reference/filter state and
stream epoch. Local timed direction gates use real prefill and analog readiness;
muted bias remains charged to both RF directions. Parking bias requires an
explicit longer wake path. An assigned settling time is not a physical result.

Retuning changes sample ownership behind isolation and an epoch handshake.
It must not glitch an active FPGA capture clock or silently reinterpret queued
samples. `resource_configuration.rf_transition_budget` computes supplied
service/settling timelines; it does not implement analog switching or prove
protocol deadlines. Prearming removes command arrival only when submitted early
enough; it does not remove CDC, queue or analog-settling costs.

## Serial rate and RF channel services

Numeric wire targets include 480 Mb/s, 1.25, 1.5, 1.62 and 2.5 Gb/s plus video
rates. Select synthesis/dividers/gears independently of host service. A single
fixed oscillator does not divide to every desired rate. FS/LS use slow line
states; SATA/PCIe/Ethernet retain independent RX recovery and required SSC.
USB reuses warm timing and burst phase acquisition; it cannot relock a PLL for
every packet. Prescribed-bit-time tests do not prove a physical burst CDR.

RF contexts hold bounded divider/bank, gain, DC/IQ trim and filter settings.
Preload and atomically commit a new context; readiness is time-stamped. Full
coarse search on every hop is not acceptable. Stale trims or failed lock block
TX. Physical tuning/trim retention across the accepted environment remains open.

## Forwarded word-clock configurations for multi-chip video

Support 74.25 and 148.5 MHz references and their /1.001 fractional forms, with
×10 serialization. HD-SDI includes 1.485 and 1.485/1.001 Gb/s. Reconfigure while
stopped; phase alignment, continuous queues and loss/recovery must be explicit.
Three TMDS lane dies share external fanout and FPGA coordination. Integer-word
misalignment rejects readiness even if analog phase error is small.

The sampled PLL and finite-deskew models provide scoped acquisition/continuity
checks. Prescribed noise, ideal detectors and short observations do not qualify
phase noise, cycle-slip probability, arbitrary board skew or physical lock
sensors. Reference reuse must match both rate and divider; a shared ratio alone
cannot justify keeping an oscillator at the wrong frequency.

## Converter-clock primitive and selected ownership

`connected/reference_sample_clock.py` supplies bounded edge-time and
forecast/commit numerical checks. Integrated converter evidence uses the
selected differential-clock/divider and retained SAR lifecycle; an isolated
reference primitive is not a substitute. Preserve oscillator phase, held analog
charge, filter memory and pending queues through loss and explicit cancellation.
A timed path that lacks modeled recovery must reject restart rather than
silently reset its history.

## Response-critical clock ownership

`FAST_HOST_CLOCK` carries 100 MHz H2D timing for direct-stream SDR capture and
control. D2H follows that trained clock; the line PLL runs independently at
480 MHz. A small local TX divide-by-two supplies 240 MHz FIFO consumption and
gearbox control. Neither the general 39.0625 MHz scheduler nor management
startup clock is on the reply path. RX FIFO visibility costs three host edges;
TX visibility costs three 240 MHz edges. Physical CDC/clock closure remains
unqualified. USB's minimum gap uses line UI; RF guards do not apply. Host loss
cancels output. See the [current budget](block-diagram.md#selected-response-critical-host-service).

## Warm hopping uses stable host timing

Select `clocktree.config.rf_host_source=host_follow_div2` before arming a hopping
RF session. H2D is 156.25 MHz and D2H is 78.125 MHz DDR throughout retuning.
Carrier-derived sample clocks may stop/change only behind converter isolation
and an explicit sample-epoch FIFO reset handshake. Host frame alignment remains
valid; FPGA resampling uses the new carrier/divider after epoch acknowledgment.
Carrier-derived host timing remains a supported nonhopping configuration; it
is not the selected Bluetooth hopping path. No new oscillator or pin is added.
The [warm sequence](block-diagram.md#warm-rf-hopping-and-gain-feedback) owns the
50 µs allocation and current qualification gaps.

## Verification boundary

Continuous service must pass finite-queue admission, acquisition/tracking,
validity, source loss and recovery with the same timing environment. Use the
[model guide](../system_model/architecture_fast/README.md) and
[clock envelope](clock-feasibility-envelope.md) for scoped commands and physical
requirements. Ideal timing providers and fixed-frequency holdover examples do
not establish jitter/SSC tolerance, calibrated sensing or actual GPIO timing.
