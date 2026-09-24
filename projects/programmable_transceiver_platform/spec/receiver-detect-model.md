# Receiver detection: proposed mathematical contract

This fills a missing intended function in the wired TX island. It is a generic
impedance measurement proposal, not a PCIe compliance procedure or an implemented
model. The existing RX electrical-idle detector measures activity and cannot
substitute for this measurement. No additional package pins are allocated.

## Circuit and environment

Model each TX conductor separately, with an internal voltage-step source through
a finite source resistance Rs. The source is enabled only when the line driver
is electrically idle and its serializer has no scheduled or in-flight bits.
The source drives the actual TX terminal, not an ideal logical termination flag.
Both conductors receive the same common-mode stimulus; they need not have identical
package or remote loads.

Each conductor has local pad/package capacitance Cp, series board coupling
capacitance Cc, and a remote node with capacitance Cr and termination Rt to the
remote common-mode source. Voltages are deviations about that source for the
initial linear candidate. Board components and the remote termination are
explicit simulation inputs. An absent receiver is represented by leakage
resistance, not a missing network. Retain initial capacitor voltages across
repeated probes and aborts.

For state x = [local voltage, remote voltage] and a commanded source voltage u:

```
C = [[Cp + Cc, -Cc], [-Cc, Cc + Cr]]
G = [[1/Rs, 0], [0, 1/Rt]]
C dx/dt = [u/Rs, 0] - G x
```

Use positive finite capacitances/resistances so C is positive definite. An ideal
open limit can be checked separately against a finite high-resistance leakage
case. If the test source is disconnected, remove its conductance and injection;
do not ground the local node or reset capacitor state. Include a separately
specified local leakage conductance for the disconnected state. Test source
energy and resistor dissipation should close against capacitor energy.

The step response can use a two-state matrix exponential. Verify it against
independent numerical integration and constant-input equilibrium. Record local
and remote voltages and source current, including their peaks. Parameters are
assumptions until corresponding transistor/package behavior is available.

## Decision and timing

A command starts a bounded sequence: preflight ownership, baseline observation,
apply a bounded step, observe at two or more declared delays, remove stimulus,
wait for release settling, then publish a result. Every delay, step amplitude,
source resistance, sensor offset and threshold belongs in a versioned profile.
No result is returned before the final observation, and stopping early returns
an aborted result rather than reusing the previous decision.

Classify each leg using an explicitly declared region of measured response space.
The first candidate may use baseline-subtracted voltage at two times. Require
both legs to be inside the present region for a present result. Require both
legs inside the absent region for an absent result. Mixed, boundary, unsettled,
out-of-range or nonfinite responses are indeterminate/faulted, not evidence of a
valid receiver. Threshold regions must be derived from nonoverlapping simulated
load envelopes; if those envelopes overlap, report that the selected stimulus
cannot discriminate them. Do not tune thresholds on the same cases used as
validation without retaining an independent holdout.

## Connected ownership and lifecycle

Receiver detection exclusively owns the TX output-stage common-mode stimulus and
monitor resources. RF operation and wired RX should remain available unless a
separate shared-supply limit is exceeded. Starting detection must reject while
TX serialization, queued words or an existing detection is pending. Starting TX
must reject until the probe releases the output and satisfies its declared
settling condition. The high-speed RX slicers and RF ADCs are not required to
perform this measurement: use dedicated low-bandwidth monitor comparators in
the TX island. This avoids silently stealing RF converter ownership.

Expose start, status and result through the timed management adapter, retaining
its epoch/generation fencing. Report busy, present/absent/indeterminate, abort,
measurement time and the profile used. Reset or clock/reference loss must disable
the stimulus immediately while retaining physical capacitor state; old results
must not become valid in a new epoch. Discovery must report actual probe ownership.

## Required evidence before calling this function implemented

- One complete connected probe in each wired mode, including return to TX service.
- Independent circuit-solver agreement, equilibrium and charge/energy accounting.
- Retained capacitor state under repeated, subdivided and interrupted sequences.
- Two-leg present, absent, mixed-load and boundary/overlap cases with explicit
  classification regions and uncertainty in load, source and sensor parameters.
- Atomic rejection of conflicting TX/probe requests, timed result visibility,
  reference/reset abort and stale-result rejection.
- Simultaneous RF traffic with probe load on the shared supply model; no hidden
  converter allocation and no uncounted external terminal.

This specification does not close the function. The next implementation should
establish whether a useful discrimination region exists under declared uncertain
loads before choosing an analog comparator or transistor driver topology.


## Initial standalone load screen

The first zero-initial-state, ideal-sensor experiment covers64 corners of Cp/Cr
1–10pF, Cc10–100nF, source resistance100–1000ohm and remote termination40/100ohm
or leakage100kohm/100Mohm. A0.2V step is observed at100ns and1us. Fixed normalized
regions (<0.65 at both observations for present; >0.85 at both for absent) yield
24 present, 32 absent and 8 indeterminate cases.
There are no incorrect definite decisions within these sampled corners. The
indeterminate cases are retained; this is not complete discrimination.

A100pF coupling-capacitor counterexample with a real75ohm termination is classified
absent. Thus the proposed decision is not safe without a bounded/qualified board
coupling network or a better stimulus/observation strategy. This is a detected
false-negative outside the candidate envelope, not a successful detection.

Matrix-exponential propagation agrees with independent Radau integration to
6.81e-15V, and the selected energy-accounting residual is
-1.88e-24J. Neither result establishes sensor/load uncertainty,
nonzero initial-state handling or connected lifecycle behavior.

Evidence: `evidence/receiver-detect-load-screen.json`. Its exact standalone Python
source is saved as `evidence/receiver-detect-load-screen-source.txt`, with its SHA256
in the report. Run it with Python from this workspace. It is not part of the
then-running 80-scenario aggregate and does not modify that model snapshot.

## Earlier observation with held-out load/error cases

Keeping the original classification regions and100ns first observation, changing
the second observation to200ns gives192 present and192 absent classifications
with no indeterminate or incorrect result in384 tested cases. These comprise256
new seeded interior load points plus128 original load corners with signed errors.
Initial local/remote voltages are bounded at+/-5mV; total baseline-subtracted
measurement error is bounded at+/-5mV. This error is not a bound on each of two
separate readings. Interior cases use independent sampled error signs.

The shortened observation was chosen based on the prior corner experiment, so
the new interior points are validation cases; the original corners are regression
cases. No continuous-domain proof is claimed. The100pF coupling counterexample
still falsely reports absent and remains explicitly outside the candidate10–100nF
coupling envelope. The topology/thresholds are not yet a deployable detector.

Evidence is `evidence/receiver-detect-timing-screen.json`; source and dependency
hashes are recorded. To reproduce the standalone experiment, copy the two saved
source text files into one scratch directory as `load_screen.py` and
`timing_screen.py`, then run `python3 timing_screen.py`. This preserves the running
connected-suite source snapshot. Controller integration and repeated-probe release
behavior remain the next implementation work.

## Persistent release state and two-leg sequence

The persistent two-node circuit exposes a repeated-probe failure: after a200ns
probe and1us passive disconnection, eight of sixteen selected load cases no longer
classify correctly. Capacitor state must not be erased to hide this. A candidate
active return-to-zero through the finite source resistance, followed by high
impedance, restores correct repeated decisions in these cases. Its longest
observed release is4us, with a5mV state criterion checked every1us. This is not a
worst-case release guarantee. Leakage is assumed1Mohm at the local node.

A staged two-leg controller now runs100/200ns observations, retains capacitor
states, resolves mismatched leg decisions as indeterminate, and enters an explicit
release state before publishing a result. Three nominal present/absent/mixed cases
pass twice each. TX-busy/start overlap, premature reads and stale-epoch reads reject.
Abort removes the test source without changing either capacitor voltage. Aborted
controllers cannot silently restart; rearm policy remains to be integrated.

Artifacts are `evidence/receiver-detect-release-screen.json` and
`evidence/receiver-detect-sequence-screen.json`, with saved `*-source.txt` Python
sources. Reproduce by placing them beside the earlier `load_screen.py` as
`release_screen.py` and `probe_sequence.py`. Source/dependency hashes are retained.
These standalone tests do not close receiver detection: connected scheduling,
actual queue ownership, reset/rearm, timed management, current/supply coupling and
combined uncertainty tests remain required. They leave the current aggregate
regression source snapshot unchanged.

## Probe and release current/energy accounting

The persistent-state experiment now integrates source work, source-resistor loss,
local leakage loss, remote-termination loss and capacitor energy across probing,
active baseline restoration and disconnection. All16 load cases close energy to
within1.01e-21J. Positive source charge and sink charge are tracked separately;
subtracting them would hide the release-driver requirement.

Largest sampled current is2mA per conductor, including interval endpoints; the
same pair driven simultaneously would require4mA of test-source current. Across
these cases the largest positive charge is284pC per leg and the largest sink
charge203pC per leg. The maxima need not occur in the same case. Current extrema
are sampled at65 points per interval, not proved analytically over continuous
time. The chosen0.2V source is not a chip supply: bias current, source/sink output
stage losses, regulator conversion and sensing power are excluded.

Before connecting this to the shared supply model, choose and document a driver
power relationship rather than assuming source work divided by an arbitrary rail
is the complete supply current. Preserve separate source/sink actions and feed
the timed supply load into concurrent RF/wired oscillator tests. Evidence and
hashed source are `evidence/receiver-detect-energy-screen.json` and
`evidence/receiver-detect-energy-screen-source.txt`; it depends on the retained
`release_screen.py` and `load_screen.py` standalone experiments.

## Explicit post-abort rearm

A staged recoverable controller now requires an explicit current-epoch rearm
command after abort. Rearm drives the retained network toward baseline through
the same finite source resistance. It does not overwrite capacitor voltages.
Completion returns to idle with no detection result; a new probe is required.
Starting a probe during recovery and reading a result before a new detection
both reject. A second abort during recovery disconnects the source and advances
the epoch again, invalidating earlier commands/results.

Six cases cover present, absent and mixed loads, each interrupted during the test
pulse and during release. All preserve instantaneous capacitor state, reject
TX-busy/stale rearm, survive interrupted recovery, and perform a fresh successful
probe afterward. These are standalone controller results; chip reset/reference
callbacks and actual TX queues are not yet connected. The active rearm load must
be included in shared-supply coupling when integrated.

Evidence/source are `evidence/receiver-detect-rearm-screen.json` and
`evidence/receiver-detect-rearm-screen-source.txt`. The report records hashes of
`probe_sequence.py`, `release_screen.py` and `load_screen.py`; reproduce beside
those preserved source files. This does not change the running aggregate model.

## Staged adapter against the connected chip

A separate scratch adapter now subclasses the unchanged sampled-clock chip and
merges probe observation/release events into chip advancement. Six cases cover
both wired modes and present/absent/mixed remote loads. Each preserves64-sample
RF capture and independent wired RX completion. Queued TX words exclude a probe;
probe/release excludes TX acceptance and scheduling. After release, an actual
queued word passes through the serializer. Reference loss aborts detection while
preserving the instantaneous capacitor state and invalidating the result.

This closes a first controller-integration experiment, not the final function.
The adapter still lacks timed management, discovery, post-reset rearm and supply
loading. RF/wired coexistence here means control/transport isolation only. The
adapter is intentionally outside the source tree while the aggregate runs, and
is not one of its80 registered scenarios.

Evidence/source: `evidence/receiver-detect-chip-adapter.json` and
`evidence/receiver-detect-chip-adapter-source.txt`. Imported project/scratch Python
sources are hashed in the report. Reproduce with saved detector files in a scratch
directory and `PYTHONPATH=projects/programmable_transceiver_platform/system_model/connected`.

## Staged timed management and reset/rearm

The staged adapter now reuses actual management serialization, queue capacity,
execution-time epoch/generation fencing and delayed replies for `detect_start`,
`detect_status` and `detect_rearm`. Probe and command events are merged with chip
advancement, so observations/release are processed before later status reads.
Status provisionally packs state in the low byte and decision in bits9:8
(0 unavailable,1 present,2 absent,3 indeterminate). This is a named-model interface,
not an assigned physical register address or frozen hardware ABI.

Both initial modes pass execution-time start, premature-reply rejection, status
snapshot retention, reset invalidation of a queued start, explicit post-drain
rearm, empty result after recovery, and successful redetection after configuring
the other mode. Detection recovery never silently publishes an old measurement.
The staged adapter requires drain before rearm if the chip is draining.

Evidence/source are `evidence/receiver-detect-managed-adapter.json` and
`evidence/receiver-detect-managed-adapter-source.txt`. Dependency hashes are saved.
The existing source snapshot under aggregate regression remains untouched.
Supply-current coupling, full resource-discovery wiring, uncertainty coverage and
promotion into the main model remain pending.

## Staged resource discovery and persistent TX interlock

The staged management adapter now exposes detector resource6 and owner7, with
bit11 indicating TX interlock separately from active-work bit8. Probing and
release own wired TX. An aborted/faulted detector has no active stimulus but keeps
TX inhibited until explicit recovery restores baseline. Normal completion frees
wired TX while retaining a readable detection result.

Four timed cases span both wired modes and reads of the TX or detector resource.
A read executed during the probe retains its busy/owner snapshot even when the
reply arrives after release. Abort reports inactive-but-interlocked; post-drain
rearm clears the interlock. Out-of-range resource IDs reject. The main model still
advertises six resources until the staged detector is promoted; the running
aggregate does not include this seventh resource.

Evidence/source: `evidence/receiver-detect-resource-adapter.json` and
`evidence/receiver-detect-resource-adapter-source.txt`, with dependency hashes.
Supply coupling and complete detector/load uncertainty coverage remain open.


## Promoted connected variant

After verification and archiving of the80-scenario pass842 baseline, these staged
sources were promoted to `system_model/connected/receiver_detect_*.py`.
`receiver_detect_lifecycle.ReceiverDetectChip` is the connected variant. Run
`python3 projects/programmable_transceiver_platform/system_model/connected/receiver_detection_screen.py`
from the repository root to reproduce all nine component screens; the composite
report is `evidence/connected-receiver-detection.json`. This is now the81st
registered scenario. Historical source-text artifacts remain for provenance;
the promoted Python modules are the implementation entry points. Their reports
retain staged-adapter terminology where they describe the variant's limited
scope. Supply coupling and the full operating-envelope proof remain unfinished.


## Pass 844: receiver-detect load reaches shared supply and oscillators

`SupplyDetectChip` extends the connected managed detector with an explicit driver
load law: enabled100uA bias plus positive output current, plus10% of sink current.
These are assumptions, not GF180 measurements. Sinking never credits supply charge.
The load feeds the same RC rail and oscillator pulling used for host activity.
A left-endpoint charge approximation is tested at0.5ns and0.25ns intervals.

Both modes retain64 captured RF samples and the present-load detection result.
The refined nominal case draws267pC, peaks at0.951mA supply current, and reaches
84.2mV rail droop/84.2kHz RF pulling for the selected100ohm/100pF rail and1MHz/V
sensitivity. RF analog values change by0.00434; timestep refinement changes them
by about5e-6. Zero-load controls remain undisturbed. These finite cases establish
one-way shared-rail coupling, not full electrical qualification.

The0.2V probe stimulus and detector sensor remain ideal despite rail droop. Their
supply dependence is the next required feedback path.82 scenarios are registered;
the archived80-scenario baseline remains the latest complete aggregate.


## Pass 845: two-way probe stimulus and sensor rail sensitivity

The probe now supports held stimulus gain1+k*rail_delta and a sensed-voltage
additive offset proportional to rail delta. The actual driver current uses the
same held stimulus as the RC circuit, closing the load/rail/stimulus loop rather
than changing only a displayed result. Zero sensitivities retain the prior model.
Tests use signed1/V gain and0.02V/V sensor offset, both modes and the nominal
present load. Finite RF capture, detection, changed source charge and measurement
response pass. Halving the load step and splitting the caller interval137 ways
keep changes below5% of the induced measurement effect. Original one-way supply
and standalone sequence regressions pass.

An important remaining realizability gap was identified: baseline/release checks
currently inspect both simulated capacitor voltages, including the remote node.
That node is not directly observable on the chip. Replace the simulation-state
criterion with a bounded timed/local-sensing policy, then verify its uncertain-load
limits. The current tests are conditional model evidence, not a realizable final
release controller.83 scenarios are registered; the80-scenario archived aggregate
is still the latest full regression.


## Pass 846: realizable local-only release policy

Removed remote capacitor voltage from controller baseline/release decisions.
Release now requires at least4us of active restoration and a chip-side measured
voltage within5mV. The remote state remains available only to circuit validation.
Sixteen candidate load histories pass repeated detection and rearm with safe
observed hidden-state values. A stuck-high local monitor reaches the existing
1ms fault timeout, disables stimulus and publishes no result.

All nine detector circuit/control regressions and both supply/feedback screens
pass with the longer release. This is a realizable observation/timer policy,
not a full settling guarantee: arbitrary initially charged remote networks,
monitor noise/offset, clock tolerance and driver compliance remain unqualified.
84 scenarios are registered; the archived80-scenario run is the latest aggregate.
