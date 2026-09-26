# Current transceiver status and priorities

The [normative architecture and diagram](block-diagram.md) own selected functional
boundaries. Numerical studies below are conditional evidence, not frozen circuit
topologies or qualified component specifications.

The mathematical architecture is **incomplete**. No new schematic or layout
work until the mathematical gates are met. Conditional simulation success is
not GF180, package, FPGA timing or protocol-compliance qualification.

## Architecture assessment: one implementation, several ways to succeed

Architecture selection review completed 2026-09-26: baseline, rough allocations,
costed fallbacks and all 17 capability obligations are recorded in their existing
owner documents. This completes the selection review, not mathematical or
physical qualification. This section owns the current cross-system verdict;
scoped measurements below explain it. The [normative architecture](block-diagram.md)
owns selected blocks, and [feasibility gates](feasibility-gates.md) own the
operating ledger and detailed acceptance work. Do not equate this assessment
with completed mathematical verification.

**Verdict:** retain the full programmable companion architecture. No reviewed
result establishes that the entire intended capability set is impossible, but
no complete operating envelope currently proves it feasible either. A shared power/timing environment now exposes important failures that isolated
fixtures missed. The largest remaining analog gap is a simultaneous operating
point: loaded-clock spectral noise, RF noise/linearity, pad loading and physical
current/area must fit together. A passing block cannot be combined with another
block merely because each passed a different fixture.

### Decision freeze and the next system-level verdict

The [mitigation dispositions](block-diagram.md#disposition-of-remaining-mitigation-choices)
close the remaining architecture alternatives. Preserve uncertainty bounds as
acceptance tests; do not describe an unmeasured physical property as a pending
architecture choice.

Proceed with the selected full-chip architecture in the normative document.
External timing, external regulation/passives, common returns in compatible COB
geometry, LO-derived RF sampling, warm same-channel radio turnaround, independent
wired RX recovery, and FPGA-owned protocol processing are implementation decisions.
The H0 host contract is selected; choosing a specific development board is deferred
until board integration and is not a prerequisite for mathematical closure.

Retain the single-ended high-impedance REF_IN baseline for this checkpoint.
The differential fallback now has joined RF/wired evidence: with the assigned
0.025 ps/mV downstream sensitivity it maintains readiness in 64/64 tested wired
corners, and the blocked RF acquisition diagnostic recovers its tested payloads.
That is a reason to prioritize it, not physical qualification: the reduced
sensitivity is unpriced, and input common-mode range, protection, area and the
extra signal assignment remain unqualified. The additional 4 mA input allowance
does not buy the assumed improvement in downstream clock distribution.

### Checkpoint: what the latest combined evidence changes

| System question | Current evidence | Decision at this checkpoint |
|---|---|---|
| Can the selected clock path tolerate internal switching? | Added budgeted current pulses break wired readiness and worsen blocked RF. Increasing capacitance alone does not close both. | Keep failed controls; prioritize a feasible clock-input/distribution requirement envelope. |
| Does a credible mitigation exist? | Differential input plus reduced downstream sensitivity improves both RF and wired diagnostics. Physical attainability remains assumed. | Retain one costed fallback; do not expand the hardware option list. |
| Is RF packet success sufficient? | Acquisition/coding diagnostics recover tested packets, but are not complete standards-valid HE packets or PER evidence. Cold TX wake damages the onset even when later bits decode. | Keep warm/muted TX selected; require complete acquisition and switching behavior. |
| Can slowing the host rescue USB? | The rate audit below finds no joint pass; slower rates reduce response margin and leave the instantaneous pad guard failing. | Keep full-rate transport; resolve measurement/receiver meaning and actual CDC latency before adding hardware. |
| Is the chip mathematically complete? | No shared envelope covers all lifecycle and capability obligations. | Stop exploratory sweeps here; close the common envelope and representative lifecycles next. |

Reports retain the source hashes from their original runs. Older reports are
historical comparisons, not fresh executions of the current tree. Focused test
counts verify model mechanics; they are not a measure of chip completeness.

The next milestone is a **baseline keep-or-change verdict**, not another expansion
of the protocol list. Evaluate one consistent operating envelope across weak
blocked RF reception, wired continuous readiness and USB shared-return conditions.
Keep existing failed controls. Prefer board conditioning and configuration changes;
change on-chip hardware when an identified failure survives those remedies and the
replacement closes more of the system within the pin/current/area allocations.
After that verdict, finish startup, sustained operation and recovery using the
same envelope, followed by capability-wide acceptance. No new schematic or layout
work precedes mathematical closure.

Unknown device noise, pad capacitance, assembly inductance and thermal resistance
remain bounded requirements to verify. Decisiveness selects an implementation;
it cannot select the physical answer to an unknown. In particular, retain 0.25 nH
as an assembly target, not a claim that compatible packaging achieves it.

### Whole-chip risk ranking

Risks are ranked by capability reach, failure severity and usable fallback.
The decisions and checkpoint above own the current verdict; the detailed
experiments below retain their conditions and failure controls. Mathematical
closure requires bounded assumptions, joined startup/operation/recovery and a
verdict for each capability. Physical qualification remains a later obligation.

| Rank | Risk / reach | Severity and fallback | Next discriminating experiment / decision |
|---|---|---|---|
| 1 | Physical interface and shared supply: all high-speed modes | Can invalidate the entire chip. Default-compatible pads, board damping and external regulation help; a custom package is not the baseline escape. | Apply the 236/288 mA mode allocations, actual shared-return topology and bounded pin loading to one fast electrical/timing envelope. Check both host directions and GHz/serial/RF pads. Change the compatible pad/feed plan if no common window exists. |
| 2 | Delivered timing and independent RX recovery: wired and RF | Can defeat all fast modes even with a good external oscillator. External input is selected first; autonomous operation is secondary qualification, not an unpriced rescue. | Bound source → loaded input → phase/distribution and supply sensitivity together; retain independent wired CDR. Determine the allowable device/load ranges, then test acquisition and recovery at those limits. |
| 3 | Converter/filter/reference dynamic range: every radio, especially wideband | Can remove much of the radio value. Finite-zero filtering is selected; interleaving or higher precision costs explicit current/area and calibration. | Join the selected response, absolute noise, blockers, reference load, clipping and clock spectrum at the revised current. Include a narrow and a wide RF configuration so one setting cannot stand in for the entire range. |
| 4 | Generic electrical actions and recovery: USB, PCIe, SATA, video; shared pad loading affects other wired modes | A missing physical state may require redesign, not FPGA firmware. Independent controls and specialized branches are selected; external helpers cover only named board functions. | Audit command-to-pad actions, then run one DC-coupled and one detection/OOB lifecycle with finite host service. Keep the target-specific exceptions in the capability table. |
| 5 | FPGA service and continuous clock ownership: all full-rate applications | Analog may work while the companion is unusable. Selected source-synchronous host, FPGA-owned processing and bounded chip queues avoid deep on-chip buffering, but exact bank timing is unqualified. | Demonstrate uninterrupted worst-rate delivery, independent RX/TX clock drift and fault recovery with the selected H0 electrical load. No physical FPGA purchase is needed for this model. |
| 6 | Fabricated area, heat and variation: entire chip | Rough 12.92 mm² allocation is accepted for planning, with explicit growth. Thermal behavior and parasitics may force rebudgeting. | Carry the allocations into schematic planning after mathematical closure, then layout/extraction. Before that, screen gross current/heat and geometric pad conflicts; do not demand exact transistor area now. |

### Current shared-environment verdict

Use `current_target_observations` in the
[selected-baseline report](../evidence/selected-baseline.json) for the current
package target with the original 0.5 V external Thevenin clock peak. It separates
numerical convergence, observed signal errors and receiver readiness. Neither
its bench count nor the legacy controls measure chip completeness. The report
identifies the 0.25 nH target as `lower_return_probe`; the historical `selected`
label denotes the original 0.5 nH comparison, not the selected assembly target.

| Joined path | Current target result | What the result decides |
|---|---|---|
| Weak wideband RX, causal SAR and input/rail feedback | At −85 dBm wanted / −30 dBm blocker, both assigned supply-delay signs converge but retain 58/60 errors at 2.4 GHz and 23/27 at 2.484 GHz, each over 2,340 uncoded held-out bits. | The present operating point fails this fixture. Explicit SAR dynamics do not remove the failure. Known DATA training is not packet acquisition, sensitivity or BER qualification. |
| Coded wideband DATA under the same causal analog model | At the current package target, the 0.5 V source recovers 4/6 payloads; 0.75 V recovers 6/6 across two LO endpoints and three payload seeds. | Coding can repair some observed raw errors. These are fixed-training DATA controls, not acquired HE packets or a PER qualification. |
| Wideband legacy-training acquisition plus coded DATA | Unknown arrival/CFO: 0.5 V acquires 4/6 wanted captures and recovers 3/6 payloads; 0.75 V acquires 6/6 and recovers 5/6. The single no-wanted control is rejected. | Known-start decoding was optimistic. Preserve the failed cases; this exercises legacy training, not complete HE packet acquisition or PER. |
| Narrowband request/reply with the corrected clock and causal conversion | All six stressed requests acquire; five requests and replies decode correctly. Seed 719 fails request CRC. Previous-environment and no-blocker paired controls pass. | Retain the blocked failure. The previous six-of-six result is superseded; six packets cannot establish PER. |
| Wired TX into independent peer CDR | All four short fixtures have zero held-out errors, but readiness is only 29.25–53% and all end unqualified. The ideal-TX-clock controls remain qualified. | Delivered timing still fails the unchanged readiness requirement. Do not equate zero bit errors with a usable continuous link. |
| Wired RX and generic recovery | Selected 200 ps / 80 ps CTLE completes both opposing 100 ppm corners and existing gap/restart cases; unequalized controls overflow the bounded event stream. | Keep independent RX clock recovery and the selected CTLE. This does not establish protocol electrical lifecycles or actual serializer/FIFO operation. |
| Bounded RF driver wake | Warm, partial and full wake retain zero known-DATA errors at 2.484 GHz; current-target EVM is about 3.93%. | Keep warm/muted TX for fast response. The result bounds the modeled current ramp, not bias readiness, real preamble acquisition or RF-cycle load variation. |
| USB static and quiet-pin conditions | Lower return inductance restores conditional static margin, but an HS quiet-pin experiment still exposes about 71 mV board-referenced disturbance. | Static voltage margin does not close common-mode coupling or host/device electrical lifecycles. |

The 0.5 nH comparison retains substantially worse weak-wideband errors and
fails all six stressed narrowband acquisitions. Its 2.5 GHz TX clock fails the
baseline gate, so rejected full-duplex cases do not establish RX-only behavior.
The 2 nH comparison is rejected before these RF/wired payload observations.
None of these values establishes what the actual compatible package will do.

**Common mitigation to qualify:** increasing external clock peak to 0.75 V at
the current package target restores all four modeled wired TX readiness corners
without relaxing the criterion in the original launch window. The corrected
driver/channel model passes only 9 of 32 nominal launch/peer corners at 0.75 V,
and 22 of 32 at 1.0 V. Periodic clocks with the same mean delay pass every
paired control; varying delivered timing is necessary for these modeled failures.
Neither stronger source is a robust wired remedy yet. The detector-resolution
comparison below shows that these coarse failure counts overstate lock loss;
refined crossing estimates improve them but retain failures.
The complete narrowband exchange now correctly
decodes all six requests and replies with independent fixed calibration, no DAC
clipping and diagnostic gaps of 149.964–150.179 µs. At 0.5 nH only one of six
exchanges succeeds; the 2 nH clock remains rejected. Wideband assigned-ENOB controls improve
but still fail: 59→33 errors at 2.4 GHz and 20→7 at 2.484 GHz. These use a
different converter model from the causal results above and must not be compared
as identical fixtures. Larger drive increases return current and rail coupling;
it is not a package-independent remedy. Keep the 0.5 V reference baseline and
its failures while source/pad bias, physical headroom, sensitivity corners,
TX-load feedback and broader channel coverage remain unqualified. The joined
reply result does not supply those missing proofs. No new filter, ADC, pin or regulator
bank is justified by these observations alone.

### Wired readiness: numerical detector error is material

The [wired lock probe](../verification/wired_lock_probe.py) preserves the existing
source waveforms, independent peer feedback gains, 5 ps IID timestamp-noise
hypothesis and 64-edge / 0.1 UI readiness rule. Offline voltage roots show up to
6–7 ps error in the four-observation linear crossing estimates in the inspected
failed windows. Instrumented runs reproduce the original decisions/readiness;
root values are not supplied to those original runs.

A separate controlled refinement reruns the feedback loop with finer voltage
subdivision or roots solved inside its detected brackets:

| Source peak, current 0.25 nH target | Original four-point interpolation | 16-point interpolation | Within-bracket roots |
|---|---:|---:|---:|
| 0.5 V | 0/32 continuously qualified | 0/32 | 0/32 |
| 0.75 V | 9/32 | 20/32 | 22/32 |
| 1.0 V | 22/32 | 27/32 | 30/32 |

Each column uses eight nominal launch phases and four peer phase/ppm corners.
All short held-out records have zero bit errors, including the unqualified ones.
The full feedback refinement matters: offline root errors on the original
sampling trajectory cannot predict a retimed loop. Detected-edge counts can also
change during acquisition, so equal seeded IID-noise generators do not guarantee
noise attached to identical physical transitions in every variant.

**Decision:** the coarse readiness counts are not numerically converged evidence
for rejecting an input architecture. Preserve them as controls, alongside the
refined failures. Do not relax the readiness limit or infer that stronger drive
has closed the wired envelope: even the root-based comparison loses readiness.
The refinement changes numerical crossing localization, not the selected chip's
phase count or hardware budget; a physical phase detector still has to earn the
assigned timestamp precision. Extra crossings outside detected brackets,
asynchronous launch phases, sustained BER and protocol-specific jitter masks
remain unproved. The [report](../evidence/wired-lock-probe.json) owns the trace
attribution and all three resolution controls; regenerate it with
`python3 verification/wired_lock_probe.py` from the project directory.

### Internal switching changes the shared timing budget

The [internal switching screen](../evidence/internal-switching-screen.json) adds
positive periodic pulse hypotheses within the existing 40 mA CORE and 40 mA
timing allocations. At full probe load, 20 mA CORE and 10 mA timing are switching
means; the remaining owner current stays steady. Total RF/wired mean allocations
remain 236/288 mA. Each event has a three-pole gamma pulse with 0.2 ns time
constant. Timing events occur at carrier/16; core events at 156.25 MHz.
These are assigned stress hypotheses, not measured or inferred device currents.

At the current 0.25 nH package target, 0.75 V external source peak, nominal
coherent phases and positive supply-delay sensitivity:

| Carrier / mode | Host-only deterministic edge RMS | Added half-load pulses, 64 harmonics | Added full-load pulses, 64 harmonics |
|---|---:|---:|---:|
| 2.400 GHz RF | 6.330 ps | 8.526 ps | 11.340 ps |
| 2.484 GHz RF | 6.399 ps | 8.554 ps | 11.321 ps |
| 2.500 GHz wired | 7.402 ps | 10.492 ps | 14.367 ps |

All 15 clock screens retain ordered, uniquely detected edges and satisfy the
assigned incremental input-voltage bound. This is permission to evaluate payloads,
not a jitter-mask, CDR-readiness or packet pass. The largest 32-to-64-harmonic
RMS change is 0.022 ps; this comparison does not bound the remaining infinite
spectral tail or omitted physical loads. Independent time-domain integration
checks pulse charge and Fourier coefficients, and current-port sums conserve
charge. The 45 focused baseline tests pass.

**Consequence:** host and converter-current feedback alone do not enclose the
shared-power disturbance. Carry these internal loads into joined payload tests
before interpreting marginal successes as robust. Phase, pulse width and switched
fraction still need bounds; full-rate timing activity and coupling of load events
to the delivered clock are missing. High-frequency tones require appropriate RF
simulation bandwidth; do not alias them into an existing lower-rate fixture.
The screen does not yet include simultaneous causal converter-load feedback.

The [joined wired load campaign](../evidence/wired-internal-load.json) now carries
these same internal-current ports through the reference-input clock solution and
TX rail modulation before channel filtering. It retains the independent CTLE/CDR
receiver, 5 ps timestamp-noise hypothesis and 64-edge/0.1 UI readiness criterion.
At 2.5 Gb/s and 0.75 V source peak, four nominal launch phases times four initial
receiver phase/ppm corners give:

| Internal switching load | Continuously qualified held-out windows | Worst readiness fraction | Held-out bit errors |
|---|---:|---:|---:|
| No added internal pulses | 14/16 | 80.42% | 0 |
| Half probe load: timing 5 mA, core 10 mA | 5/16 | 78.50% | 0 |
| Full probe load: timing 10 mA, core 20 mA | 0/16 | 23.17% | 0 |

The mean chip current remains 288 mA. Within-bracket roots are used throughout;
three selected controls repeat with 16 rather than four voltage subdivisions.
They reproduce edge counts, bit errors and readiness, including the full-load
failure (42% readiness at that particular corner). This rules out the earlier
linear-interpolation artifact for that failed control, not every possible
numerical or physical error. Each held-out record contains only 1,200 bits;
zero errors is not a BER result, and the assigned readiness rule is not a
protocol jitter mask. All currents remain nominally phase-coherent; no
asynchronous-current or process-corner coverage is implied.

**Current verdict:** continuous wired readiness has not closed under the added
internal-load hypothesis. Preserve this failure rather than relaxing the
criterion. Next distinguish sensitivity to pulse shape/phase and switching
fraction from a need for physical rail/timing mitigation, and carry the same
loads into RF with adequate numerical bandwidth. Reproduce this campaign with
`python3 verification/wired_lock_probe.py --internal-loads` from the project
folder. Its source hashes identify this run; older reports are historical until
regenerated against their changed sources.

### Internal-load decoupling mitigation screen

The [decoupling screen](../evidence/internal-decoupling.json) holds the package,
mean current, full internal switching hypothesis and external source unchanged.
It varies local capacitance alone, retaining 0.5 Ω ESR and 200 pH ESL. All nine
clock cases retain valid ordered edges and the assigned input-voltage bound.

| Local capacitance | 2.400 GHz RF edge RMS | 2.484 GHz RF edge RMS | 2.500 GHz wired edge RMS |
|---|---:|---:|---:|
| 500 pF baseline | 11.340 ps | 11.321 ps | 14.367 ps |
| 1 nF candidate | 7.620 ps | 7.654 ps | 9.510 ps |
| 2 nF sensitivity control | 6.442 ps | 6.495 ps | 7.902 ps |

At 2.4 GHz the local-rail AC RMS falls from 103.7 to 57.0 to 49.1 mV;
wired falls from 129.8 to 71.6 to 62.0 mV. The report also provides conservative
amplitude-sum bounds; those are not actual sampled extrema and must not be
compared as such with the preceding RF waveform intervals. No packet, readiness
or lifecycle result is supplied by this clock-only screen.

Using the already documented 0.9–1.8 fF/µm² minimum-density options, the extra
500 pF for a 1 nF total requires approximately 0.278–0.556 mm² of ideal plate;
a 2 nF total adds approximately 0.833–1.667 mm² over baseline. Routing, guard and
connection overhead are additional, and the available shuttle capacitor option
is not established here. Holding ESR/ESL fixed while changing C is a sensitivity
experiment, not a layout realization. See the existing capacitor-area discussion
in [power partition](power-partition.md).

The [joined payload comparison](../evidence/decoupling-payload.json) now tests
1 nF against fresh 500 pF controls under the full internal switching load. All
16 wired baseline results and both RF baseline feedback records reproduce their
preceding reports exactly. Current source hashes match this run.

| Observation | 500 pF | 1 nF |
|---|---:|---:|
| Wired continuously qualified windows | 0/16 | 5/16 |
| Worst wired readiness fraction | 23.17% | 78.50% |
| Wired held-out bit errors | 0 | 0 |
| 2.400 GHz RF uncoded errors / 2,340 bits | 137 | 56 |
| 2.484 GHz RF uncoded errors / 2,340 bits | 15 | 15 |
| 2.400 GHz RF RMS EVM | 114.8% | 86.9% |
| 2.484 GHz RF RMS EVM | 61.5% | 60.5% |

All four RF feedback calculations converge in two passes. However, RF minimum
rail voltage gets slightly worse: 2.7194 → 2.7158 V at 2.4 GHz and
2.7222 → 2.7192 V at 2.484 GHz, despite improved RMS disturbance and lower
positive peaks. More capacitance does not monotonically improve every waveform
extremum. Pulse phases, damping and resonant behavior matter; attributing this
minimum change to a specific resonance requires further analysis.

**Decision:** retain 1 nF as a mitigation candidate, not a selected fix. It
improves both domains but leaves wired readiness and weak blocked RF failures.
Before spending area reserve, compare realizable damping/ESL and internal pulse
phase/shape sensitivity. Do not keep increasing capacitance solely because the
clock RMS improves. These short known-training/CTLE fixtures still do not qualify
packet acquisition, BER, protocol timing or physical devices. Reproduce the
screen with `python3 verification/baseline_envelope.py --internal-decoupling`
and the joined comparison with
`python3 verification/wired_lock_probe.py --decoupling-payload` from the project
directory. The latter runs both RF and wired tests using the same capacitor cases.

### Damping and connection-inductance sensitivity

The [18-case damping screen](../evidence/internal-damping.json) keeps 1 nF,
mean current, full internal pulses, 0.75 V source and package target fixed. It
varies the local capacitor ESR at 200 pH ESL, then ESL at 0.5 Ω ESR. All cases
retain valid clock edges; this does not establish a payload pass.

| ESR / ESL | RF edge RMS, 2.400 / 2.484 GHz | Wired edge RMS | RF rail AC RMS at 2.400 GHz | Wired rail AC RMS |
|---|---:|---:|---:|---:|
| 0.25 Ω / 200 pH | 7.630 / 7.666 ps | 9.339 ps | 48.9 mV | 61.2 mV |
| 0.50 Ω / 200 pH control | 7.620 / 7.654 ps | 9.510 ps | 57.0 mV | 71.6 mV |
| 1.00 Ω / 200 pH | 8.242 / 8.265 ps | 10.606 ps | 81.0 mV | 102.2 mV |
| 2.00 Ω / 200 pH | 10.785 / 10.778 ps | 14.150 ps | 133.0 mV | 168.3 mV |
| 0.50 Ω / 100 pH | 8.038 / 8.074 ps | 10.220 ps | 56.5 mV | 70.9 mV |
| 0.50 Ω / 400 pH | 7.438 / 7.465 ps | 8.741 ps | 74.6 mV | 94.0 mV |

**Decision:** do not add capacitor-series resistance as the selected mitigation.
At these nominal pulse phases, increased ESR worsens both observables. Lower ESR
helps rail ripple but barely changes RF timing. Increasing ESL improves the
clock RMS while worsening rail RMS, so it is not a system-level improvement.
The table does not identify the underlying resonance or prove behavior over a
continuous parasitic range; no physical ESR/ESL realization is demonstrated.

Keep the baseline and 1 nF candidate distinct. Before another hardware change,
bound sensitivity to internal pulse timing/width and trace the separate
input-return, downstream-delay and rail/headroom contributions. Favor a mitigation
that improves the joined envelope, not one scalar jitter number. Mean budgets
and pin/package geometry remain unchanged. Reproduce with
`python3 verification/baseline_envelope.py --internal-damping` from the project
directory; source hashes identify this run. Earlier reports retain their original
hashes and are not silently relabeled as current-source executions.

### Internal pulse uncertainty and timing-path attribution

The [21-case pulse screen](../evidence/internal-pulses.json) retains the 500 pF
baseline and varies core-current origin over four quarter-period phases relative
to fixed timing/host activity. Both pulse time constants are also tested at
0.1/0.2/0.4 ns at zero relative phase, with unchanged 10/20 mA timing/core means.
This is an assigned sensitivity set, not measured current bounds or a complete
joint phase/width sweep. All clock cases retain ordered valid edges.

| Carrier | Total RMS across tested phases at 0.2 ns | Zero-phase input-threshold RMS | Zero-phase downstream-delay RMS |
|---|---:|---:|---:|
| 2.400 GHz RF | 7.723–11.340 ps | 6.213 ps | 10.026 ps |
| 2.484 GHz RF | 7.670–11.321 ps | 6.289 ps | 9.937 ps |
| 2.500 GHz wired | 8.639–14.367 ps | 7.234 ps | 12.479 ps |

The two contributions are correlated, not independent noise sources. At the
three-quarter core phase, RF correlation is approximately −0.52: partial
cancellation lowers total RMS below the downstream component alone. The report
computes covariance from the same edge observations. These quantities already
form the combined clock; adding them again would double-count impairment.

At zero phase, changing the pulse constant alone yields 10.792–11.340 ps RF at
2.4 GHz, 10.791–11.321 ps at 2.484 GHz, and 13.280–14.367 ps wired in the
64-harmonic cases. Sharper pulses do not monotonically increase combined RMS
because waveform phase/correlation changes too. The 128-harmonic controls at
0.1 ns change total RMS by at most 0.023 ps; that is a finite refinement check,
not proof of an infinite tail bound or missed-crossing completeness.

**Decision:** do not adopt a favorable switching phase as a guaranteed cure.
Nor does this attribution justify treating a differential input as a complete
solution: downstream supply-delay sensitivity remains a material contributor.
The assigned 0.1 ps/mV, 1 GHz-pole downstream model needs an explicit achievable
sensitivity envelope and joint phase/sign coverage. Prioritize that requirement
and mitigation against loaded rails, while retaining input-return noise and
physical pad limits. None of these clock-only cases supplies a new packet or
wired-readiness verdict. Reproduce with
`python3 verification/baseline_envelope.py --internal-pulses` from the project
directory. The full common operating envelope remains open.

### Downstream supply-sensitivity requirement screen

The [sensitivity report](../evidence/internal-sensitivity.json) rescales the
stored same-edge input and downstream terms without treating them as independent:
`variance = input_variance + k² * downstream_variance + 2k * covariance`, where
`k` is signed sensitivity divided by 0.1 ps/mV. Input roots/current waveforms and
the assigned 1 GHz downstream pole remain fixed. Three actual negative-sign
clock replays agree with this identity within 1e-8 ps; their clocks remain valid.
This checks the model calculation, not achievable transistor sensitivity.

| Sensitivity magnitude | Largest RF RMS at 2.400 GHz | At 2.484 GHz | Largest wired RMS |
|---|---:|---:|---:|
| 0, diagnostic downstream immunity | 6.576 ps | 6.655 ps | 7.641 ps |
| 0.025 ps/mV | 7.930 ps | 7.990 ps | 8.727 ps |
| 0.050 ps/mV | 9.593 ps | 9.627 ps | 10.169 ps |
| 0.100 ps/mV, existing hypothesis | 13.372 ps | 13.348 ps | 14.481 ps |
| 0.200 ps/mV | 21.595 ps | 21.458 ps | 26.048 ps |

Each maximum covers only four nominal coherent core phases and both sensitivity
signs at 0.2 ns pulse width, 500 pF and the current package target. These are not
continuous uncertainty bounds or protocol jitter limits. Except for the replayed
−0.1 cases and existing +0.1 cases, the table is variance-only: it does not
revalidate edge ordering, packet performance or receiver readiness. Additive
random/source-noise terms are outside this deterministic table.

**Decision:** prioritize lower downstream supply sensitivity as a joint RF/wired
mitigation hypothesis, alongside input-return improvement. A fourfold reduction
to 0.025 ps/mV is a useful next stress-test setting, not an adopted circuit spec
or evidence that the current timing allocation achieves it. Even zero downstream
sensitivity leaves input error, so neither perfect downstream immunity nor a
quieter input alone establishes closure. Keep the 0.1 ps/mV baseline and its
failures. Any implementation claiming reduced sensitivity must price bias,
headroom, bandwidth and distribution stages and pass the joined payload tests.
Reproduce with `python3 verification/baseline_envelope.py --internal-sensitivity`.
The report hashes both current source files and the input pulse evidence it uses.

### Reduced-sensitivity joined payload result

The [sensitivity payload report](../evidence/sensitivity-payload.json) now carries
0.1 versus 0.025 ps/mV through clock construction and causal SAR-current feedback,
with the same 1 GHz pole, positive sign, 500 pF, package, full internal pulse loads
and mean currents. The model also applies the selected coefficient to RF driver
wake delay; that path is not exercised by this receive campaign. Focused tests
verify that scaling delay does not quietly change rail, input or reference
waveforms; all 45 tests pass. Zero and invalid sensitivity values are checked.

| Observation | 0.1 ps/mV control | 0.025 ps/mV hypothesis |
|---|---:|---:|
| Wired continuously qualified windows | 0/16 | 0/16 |
| Worst wired readiness fraction | 23.17% | 59.00% |
| Wired short held-out bit errors | 0 | 0 |
| 2.400 GHz RF errors / 2,340 uncoded bits | 137 | 31 |
| 2.484 GHz RF errors / 2,340 uncoded bits | 15 | 6 |
| 2.400 GHz RMS EVM | 114.8% | 85.8% |
| 2.484 GHz RMS EVM | 61.5% | 58.3% |

All four RF feedback calculations converge in two passes. Fresh baseline wired
results and RF observations reproduce the previous loaded controls exactly.
The rail extrema change only by small feedback-induced amounts: both sensitivity
settings still expose approximately 2.719–3.151 V at 2.4 GHz and 2.722–3.150 V
at 2.484 GHz. No quiet supply has been substituted for the existing disturbance.

**Decision:** reduced downstream sensitivity is a useful RF mitigation but is
insufficient to qualify the wired path or the full operating envelope. Keep the
0.1 ps/mV baseline; 0.025 ps/mV remains an unpriced circuit-performance hypothesis.
The next joint mitigation must address input-return coupling as well as
supply-sensitive distribution, with current, pin and area costs included.
Do not infer closure from lower clock RMS or zero short-record bit errors.
Opposite-sign and internal phase sweeps, real RF acquisition, TX behavior and
physical sensitivity remain open. Reproduce with
`python3 verification/wired_lock_probe.py --sensitivity-payload` from the project
directory. The same campaign implementation also owns the capacitor comparison,
so electrical/receiver conditions do not drift between mitigation scripts.

### Paired input plus reduced sensitivity: first joined wired success

The [shared input/internal-load report](../evidence/shared-input-internal.json)
uses the costed differential REF_IN fallback with both pad loads, mutual bond
inductance, finite common-mode rejection and the existing two mismatch cases.
The additional signal remains a pin-plan cost; 4 mA input bias is charged,
raising RF/wired budgets to 240/292 mA. Internal timing/core switching means stay
10/20 mA. The baseline 500 pF and package target remain unchanged.

| Differential input setting | Wired continuously qualified windows | Wired held-out bit errors |
|---|---:|---:|
| 0.1 ps/mV downstream sensitivity, both mismatch cases and signs | 0/64 | 0 |
| 0.025 ps/mV, same conditions | 64/64 | 0 |

Each mismatch/sign combination uses four launch offsets and four independent
receiver initial phase/ppm corners, with the existing CTLE/CDR, within-bracket
roots, 5 ps timestamp-noise hypothesis and 64-edge/0.1 UI rule. Each held-out
record is only 1,200 bits, so these are finite readiness results, not BER or
protocol qualification. The internal switching phase is still fixed.

The RF portions are clock screens only. At 0.025 ps/mV, deterministic RMS spans
2.377–3.066 ps at 2.4 GHz and 2.355–3.052 ps at 2.484 GHz across mismatch/sign
cases; at 0.1 ps/mV the corresponding spans are 9.831–10.372 ps and
9.739–10.288 ps. All 24 clock cases have accepted edges and meet the assigned
incremental bounds; largest RF per-leg conservative voltage bounds are about
0.409/0.402 V. Physical input bias, common-mode range and protection are unproven.

**Decision:** prioritize this combination for a full shared-envelope comparison.
It is the first tested combination here to retain wired readiness under the
assigned internal switching stress across both sensitivity signs and mismatches.
Do not select the extra input pin yet. The
[matched single-ended control](../evidence/shared-single-internal.json) now uses
1 V source peak and the same 240/292 mA budgets:

| Sensitivity | Single-ended, each sign | Paired, each sign and mismatch |
|---|---:|---:|
| 0.1 ps/mV | 0/16 continuously qualified | 0/16 |
| 0.025 ps/mV | 14/16 continuously qualified | 16/16 |

The single-ended reduced-sensitivity failures reach only 80.42% readiness in
their worst held-out windows despite zero bit errors. All 12 single-ended clock
cases meet their assigned edge/input limits. At reduced sensitivity its RF
clock RMS is 5.092–5.461 ps at 2.4 GHz and 5.140–5.492 ps at 2.484 GHz,
versus approximately 2.36–3.07 ps across the paired cases. Thus stronger drive
explains part of the earlier improvement, but does not reproduce paired readiness
in this fixture. The source peak and DC allowance are matched, not external
source power, pad loading or delivered voltage; those topology differences are
part of the comparison. The RF entries remain clock-only evidence.

The reduced-sensitivity circuit is not proven or priced by the 4 mA input allowance. The matched RF payload comparison below now includes causal load feedback.
Real acquisition, internal phase sweeps, sustained traffic, physical pad coupling
and implementation costs remain open. Earlier paired RF payloads omitted these
internal switching loads and must remain separate controls.

The differential model now supplies either payload engine from one reusable
builder. Its independent network checks cover 459 source-port and 1,404 load-port
points. A historical RF control retains its earlier 12 errors and EVM within
1e-12 after refactoring. Report serialization now normalizes NumPy scalars and
writes atomically; the completed report's source hashes match. Reproduce with
`python3 verification/reference_input_probe.py --shared-internal`.
Run `python3 verification/reference_input_probe.py --shared-single` for the
matched controls; both use the same campaign and wired receiver construction.

### Matched paired-input RF payload comparison

The [2.400 GHz report](../evidence/shared-input-rf-2400.json) and
[2.484 GHz report](../evidence/shared-input-rf-2484.json) now test the paired
fallback through the complete existing receive fixture with internal switching
and causal SAR/reference-load feedback. All cases use 0.025 ps/mV downstream
sensitivity, 500 pF, the current package target, 240 mA RF budget, 1 V nominal
source amplitude, −85 dBm wanted, −30 dBm blocker at +12 MHz and fixed 54 dB
gain. Both topologies use the same numerical bandwidth and waveform/noise seeds.

| Input | 2.400 GHz errors, + / − sensitivity sign | 2.484 GHz errors, + / − sign |
|---|---:|---:|
| Single-ended matched control | 20 / 22 | 5 / 11 |
| Paired, 10% opposed mismatch | 13 / 14 | 3 / 10 |
| Paired, 20% aligned mismatch | 14 / 18 | 5 / 7 |

Each count is out of 2,340 uncoded held-out bits after two known DATA training
symbols. All 12 feedback calculations converge in two passes. The paired
incremental per-leg bound including converter-load perturbation stays below
0.409 V at 2.4 GHz and 0.402 V at 2.484 GHz, against the assigned 0.6 V limit.
These bounds do not establish DC input bias/common-mode or protection safety.

Paired-input RMS EVM spans 58.6–62.1% at 2.4 GHz, compared with single-ended
67.4–68.6%. At 2.484 GHz it spans 55.1–59.3%, compared with 56.1–58.6%; the
10%-mismatch negative-sign case has slightly worse EVM despite one fewer bit
error. Thus this is not a uniform improvement in every signal metric.

**System verdict:** the combination has conditional evidence of benefit in both
RF and wired paths with input pin/bias costs visible. It is no longer supported
only by isolated clock RMS, but it is not yet a selected implementation. The
0.025 ps/mV distribution performance remains an unpriced physical requirement.
The acquisition extension below now tests one unknown-arrival/CFO coded case
under the same impairment set. Expand acquisition and internal-current
phase/variation coverage before claiming an operating envelope. Uncoded errors neither prove
that FEC will rescue a packet nor by themselves prove an encoded protocol fails.
No AGC, real HE preamble, PER, TX spectrum/turnaround, sustained wired BER or
physical pad/device qualification is supplied here. Both source amplitude and
bias allowance are matched; source power, delivered voltage and pad loading
remain topology-dependent.

Each frequency report saves completed cases atomically and marks campaign
completion only after all six cases and source-hash checks pass. This completion
flag applies solely to that campaign, not the chip. Reproduce with
`python3 verification/reference_input_probe.py --shared-rf-mhz 2400` or `2484`.

### Combined mitigation: acquisition and coded payload

The [2.400 GHz acquisition report](../evidence/shared-input-acquisition-2400.json)
and [2.484 GHz report](../evidence/shared-input-acquisition-2484.json) use the
same internal-current/SAR-feedback environment as the matched payload comparison.
This targeted extension fixes negative 0.025 ps/mV sensitivity, 240 mA, 1 V
nominal source and the 20% aligned-mismatch paired fallback. Receiver arrival
and CFO are unknown: the preselected source case is payload seed 431, arrival
137 samples and −120 kHz offset. The existing legacy preamble detector and
coded DATA receiver are unchanged; numerical bandwidth is raised to resolve the
retained internal-current tones.

| LO / input | Raw coded-bit errors / 2,340 | Correct diagnostic payload and CRC |
|---|---:|---|
| 2.400 GHz single-ended | 27 | Yes |
| 2.400 GHz paired | 22 | Yes |
| 2.484 GHz single-ended | 25 | Yes |
| 2.484 GHz paired | 18 | Yes |

Both paired no-wanted-signal controls reject acquisition. All six analog feedback
calculations converge in two passes, paired leg limits remain satisfied, and
completed report source hashes match. Eight focused acquisition/codec tests pass.
The waveform and coding differ from the uncoded DATA fixture; compare topologies
within this table, not absolute error counts across those different fixtures.

**Interpretation:** the shared disturbance does not prevent this legacy-training
plus coded-DATA example from working. Single-ended and paired both pass; the
stronger reason to continue the paired fallback is its wired readiness advantage
and lower RF raw-error counts, not exclusive ability to decode these captures.
Four successful wanted captures and two rejections do not establish PER or false
alarm probability. The detector's decision arrives 3.25–3.95 µs after the true
DATA boundary in these records, requiring retained FPGA samples. Full-record
Viterbi decoding here is not a hardware response-latency demonstration.

This remains a diagnostic waveform, not a valid HE PPDU: two known DATA symbols
replace HE channel training; HE signaling, normal scrambling/pilots, AGC,
sample-rate ppm and actual FPGA turnaround are absent. Additional seeds/CFOs,
internal-current phases, positive sensitivity and the other mismatch case remain
untested in this acquisition extension. Keep those gaps explicit before treating
the conditional hardware combination as a complete RF solution. Reproduce with
`python3 verification/reference_input_probe.py --shared-acquisition-mhz 2400`
or `2484`. Numerical feedback, acquisition success, protocol coverage and physical
qualification are separate gates.

### Combined mitigation: transmit-chain screen

The [2.400 GHz TX report](../evidence/shared-input-tx-2400.json) and
[2.484 GHz report](../evidence/shared-input-tx-2484.json) extend the same matched
input comparison to the existing DAC → third-order reconstruction → upconversion
→ resistive driver/load model. All 12 cases retain full internal switching,
240 mA mode budget, 500 pF, current package target and 0.025 ps/mV sensitivity.
Both signs and paired mismatch settings are exercised at the same numerical
bandwidth. No external RF filter is silently credited.

| LO / input | Diagnostic RMS EVM | Average load power | Power above 50 MHz offset / within ±10 MHz |
|---|---:|---:|---:|
| 2.400 GHz single-ended | 3.907–3.915% | 0.677 mW | −22.19 to −21.70 dB |
| 2.400 GHz paired | 3.887–3.913% | 0.677 mW | −26.13 to −25.11 dB |
| 2.484 GHz single-ended | 3.836–3.842% | 0.679 mW | −21.88 to −21.40 dB |
| 2.484 GHz paired | 3.837–3.842% | 0.679 mW | −26.05 to −24.97 dB |

All cases give zero diagnostic BPSK errors, no source-active driver-current
clipping, and satisfy the declared voltage/current/energy port inequalities.
Spectral-band sums agree with time-domain windowed power within 2.2e-19 W.
These are broad integrals over the simulated spectrum, not standard measurement
bandwidths or a TX mask. The independent observer still uses ideal framing and
known DATA channel training. Low EVM after that observer does not prove spectral
compliance, higher-modulation performance or a complete packet transmitter.

**Bird's-eye assessment:** the combination now has conditional observations
across wired recovery, weak blocked RF receive, diagnostic acquisition/coding,
and RF transmit under shared internal-current assumptions. TX is not an obvious
failure in this warm-driver fixture, and paired timing reduces high-offset power.
The remaining major integration gaps include actual TX signal-dependent current
and DAC glitches, driver wake/switching, emissions with specified external filters,
internal-current phase/physical variation, protocol lifecycle/response timing,
and realizable input/distribution circuitry. The receive SAR-feedback result is
not a substitute for a DAC/driver current model. Keep the fixed 28 mA warm driver
and assigned distortion/ENOB limitations visible; do not read these passing
records as a whole-chip pass or change the baseline solely from them.

Reproduce with `python3 verification/reference_input_probe.py --shared-tx-mhz 2400`
or `2484`. Both reports completed all six cases with matching source hashes.

### Driver wake: late decoding hides early waveform damage

The [2.400 GHz wake report](../evidence/shared-input-wake-2400.json) and
[2.484 GHz report](../evidence/shared-input-wake-2484.json) compare a warm driver
with a ramp from zero to its already-budgeted 28 mA beginning at nominal source
start. Single-ended and 20%-aligned-mismatch paired input retain the same full
internal-current environment, 240 mA planning budget and negative 0.025 ps/mV
sensitivity. The current change propagates through the coupled supply, input,
reference and downstream-delay paths, and output current is limited by the
instantaneously available tail. No extra 28 mA is added to the planning budget.

| Driver start | First-µs waveform difference from matched warm case | Source-active clipped samples at 20.48 GHz | Later diagnostic bit errors |
|---|---:|---:|---:|
| Already warm | 0 | 0 | 0 |
| 20 ns current ramp | 1.54–1.58% RMS | 49–51 | 0 |
| 1 µs current ramp | 16.55–17.02% RMS | 3,143–3,671 | 0 |

The early metric compares complex emitted waveforms without fitting away phase,
amplitude or delay; it is not standard EVM. Clipped-sample counts are aggregate,
not necessarily a contiguous interval. All four warm controls reproduce the
preceding TX records exactly. Paired per-leg incremental bounds including wake
remain satisfied. The clock solver retains ordered local root continuations;
extra crossings outside those brackets remain an explicit limitation. Forty-five
focused baseline tests pass. All 12 report cases complete with matching hashes.

**Decision:** retain warm/muted TX for fast same-channel response. Do not infer
that cold bias can start at the first symbol merely because later DATA decodes.
These captures use known DATA training after the disturbed onset, which can hide
startup damage. Improving clock-input rejection does not remove distortion from
insufficient output current during the ramp. If power parking is used, its lead
time must include current/bias settling before unmute and be tested with the
actual preamble and external switch/PA sequence.

This tests a hypothetical bias-current trajectory, not transistor startup or
full RF mute/unmute behavior. Signal-dependent RF-cycle/DAC currents, physical
bias readiness, LO feedthrough, external switching and a burst spectral mask
remain open. The selected warm-driver path still needs those mute/launch tests;
this cold-start comparison does not qualify it by contrast. Reproduce with
`python3 verification/reference_input_probe.py --shared-wake-mhz 2400` or `2484`.

### USB shared-pad return remains a separate failure screen

The [USB internal-current report](../evidence/usb-internal.json) adds the same
budgeted timing/core pulse family to the existing static HS pad model, including
signal bonds, both local/remote terminations and pad-return feedback. Mean current
stays at 242 mA for one active wired branch; host rate/activity remain unchanged.
The 156.25 MHz internal event frequency is a stress hypothesis, not a selected
USB clock tree. No extra REF_IN current is included in this pad-only screen.

| Internal pulse scale | Matched pads: released quiet-pin bound | Asymmetric pads: released quiet-pin bound | Asymmetric released differential interval |
|---|---:|---:|---:|
| None | 71.32 mV | 72.16 mV | −2.67 to +3.82 mV |
| Half | 70.52 mV | 71.36 mV | −2.73 to +3.78 mV |
| Full | 70.21 mV | 71.07 mV | −2.82 to +3.78 mV |

All 18 released/P-driven/N-driven states miss the existing instantaneous 20 mV
quiet-pin design guard. Six no-added-current states reproduce the earlier
baseline exactly. An independent three-node nodal solution verifies the new
internal-current injection path; all 46 focused tests pass. Source hashes match,
and the current budget is unchanged.

**Bird's-eye consequence:** neither the differential clock input nor reduced
clock supply sensitivity solves this board-referenced pad obligation. Most
released-pad motion is common-mode, with a much smaller differential component
under the assigned asymmetry. Small improvements after adding internal pulses
are phase-dependent cancellation, not evidence that extra switching is beneficial.
These guard failures are not a complete USB compliance verdict: actual receiver
bandwidth, common-mode tolerance, signaling transitions and required measurement
conditions must be included before making that claim.

The [host-rate audit](../evidence/usb-rate-audit.json) reuses the historical
host-only sweep with explicit provenance. None of its 12 rates and two frame
sizes passes all listed screens. At 312.5 Mword/s with eight-word frames,
adding a hypothetical three-cycle D2H crossing gives 368.47 ns at the word-rate
destination but 435.67 ns at the control-rate destination, against the assigned
400 ns bound. The former leaves only 31.53 ns before omitted cable and physical
margins. Neither is a demonstrated FPGA/CDC implementation latency.

For the retained internal pulse family, the sum of pad-tone amplitudes is
17.617 mV. Subtracting that from each observed host-only peak leaves a lower
bound of at least 53.043 mV across the scanned rates, independent of internal
pulse phase. Phase cancellation therefore cannot meet the instantaneous 20 mV
guard within this finite-tone hypothesis; it says nothing about arbitrary new
current waveforms or changed topology.

Measurement meaning remains open. The [USB-IF electrical specification v1.07,
EL_9 and section 4.3](https://www.usb.org/sites/default/files/USB%202%200%20Electrical%20Compliance%20Specification%28v1.07%29.pdf)
describes the undriven voltage requirement and terminated test states, but that
high-level procedure does not specify the measurement bandwidth or averaging.
Do not equate this broadband instantaneous screen with a compliance verdict,
or insert an arbitrary observer filter to manufacture a pass. Actual receiver
common-mode tolerance, FS/LS/HS negotiation, squelch, edges and signal-dependent
driver current remain outside this static test.

**Decision:** retain USB host/device scope and full-rate transport. The next USB
work must join pad/receiver behavior with an explicitly owned CDC and response
path; repeating host-rate sweeps is not useful. Reproduce the two bounded screens
with `python3 verification/baseline_envelope.py --usb-internal` and
`python3 verification/baseline_envelope.py --usb-rate-audit`.

### Shared internal-load RF result

The [RF internal switching report](../evidence/internal-switching-rf.json) joins
the same full-load pulse hypothesis to weak blocked reception and causal paired
SAR/reference-current feedback. The 236 mA mean current, current package target,
0.75 V external source, positive supply sensitivity and 54 dB gain are unchanged.
Wanted power is −85 dBm with a −30 dBm CW blocker at +12 MHz. Both loaded and
unloaded controls use a 20.48 GHz numerical mixer rate, sufficient for the
retained current harmonics through 10 GHz plus the signal offset. This is a
matched comparison, not a claim of infinite-bandwidth convergence.

| LO | No internal pulses: errors / 2,340 bits | Full internal pulses: errors / 2,340 bits | EVM RMS, unloaded → loaded |
|---|---:|---:|---:|
| 2.400 GHz | 27 | 137 | 69.6% → 114.8% |
| 2.484 GHz | 6 | 15 | 57.3% → 61.5% |

All four converter/rail/input feedback calculations converge in two passes.
Observed local-rail intervals widen from approximately 2.901–3.046 V to
2.719–3.151 V at 2.4 GHz, and 2.901–3.046 V to 2.722–3.150 V at 2.484 GHz.
The physical blocks still have to earn operation throughout these intervals.
Two known DATA symbols supply training; there is no real preamble acquisition,
AGC, FEC or packet/PER claim. Source waveform and seeded numerical noise are
matched within this campaign; older results on different grids are not identical
controls. Pulse width/phase/current fractions and device behavior remain assigned.

**System implication:** the internal switching hypothesis worsens both wired
readiness and RF fidelity, with unchanged mean power. A shared power/timing
margin problem is now visible across both payload engines. Prioritize bounding
internal activity spectra and effective rail/return impedance, then evaluate
costed mitigation across both engines; do not separately tune receivers around
an assumed quiet supply. This does not yet isolate how much RF degradation comes
from timing versus gain/headroom/reference modulation. Reproduce with
`python3 verification/baseline_envelope.py --internal-switching-rf` from the
project directory. The complete baseline remains unverified.

### RF timing mitigation and receiver evidence

**Current decision:** keep the single-ended input and qualify stronger external
RF drive before adding a pin. The 0.75 V route now supports conditional coded
reception, but acquisition exposes a remaining failure. Differential input remains
the leading costed timing fallback; no complete shared RF/wired operating envelope
has passed. A simple receiver failure is not by itself evidence for more analog
hardware, and zero uncoded errors is not the Wi-Fi acceptance criterion.

Use these separate evidence levels; their different waveforms and receiver aids
must not be merged into one apparent pass:

| Current 0.25 nH package target | 0.5 V single-ended peak | 0.75 V single-ended peak | Scope |
|---|---|---|---|
| Coded HE20 DATA with known start | 4/6 correct payloads | 6/6 correct payloads | Two LO endpoints, three payload seeds, fixed known DATA training; no acquisition. |
| Legacy training plus coded DATA, unknown arrival/CFO | 4/6 acquisitions, 3/6 correct payloads | 6/6 acquisitions, 5/6 correct payloads | At 2.4 GHz, correct-payload counts are 0/3 and 2/3 respectively; both drives yield 3/3 at 2.484 GHz. |

These use the selected 236 mA RF budget, −85 dBm wanted / −30 dBm CW blocker
at +12 MHz, fixed 54 dB gain and positive assigned supply-delay sign. Every
claimed correct payload passes CRC and matches all 128 transmitted bytes.
Coding can recover captures containing raw bit errors. All feedback loops in
these controls converge, but the sparse payload/arrival cases are not independent
PER trials. Source/pad bias, physical headroom, real analog variation and broader
package bounds remain unqualified.

The [coded receiver bench](../verification/wideband_packet.py) carries rate-1/2,
constraint-length-7 convolutional coding, 26-column BPSK interleaving and soft
Viterbi decoding on the FPGA side. Polynomial-convolution and exhaustive-path
checks validate its coding algorithms. The convention agrees with the reversed
polynomial representation in the [gr-ieee802-11 encoder](https://github.com/bastibl/gr-ieee802-11/blob/maint-3.10/lib/utils.cc#L159).
The receiver never receives payload truth; the scoreboard does.

In acquisition mode, actual [L-STF](https://www.mathworks.com/help/wlan/ref/wlanlstf.html)
and [L-LTF](https://www.mathworks.com/help/wlan/ref/wlanlltf.html) sequences precede
the diagnostic DATA. The generated long-training waveform agrees with the
independently published rounded [matched-filter taps](https://github.com/bastibl/gr-ieee802-11/blob/maint-3.10/lib/sync_long.cc#L237).
Arrival and CFO are estimated from the continuous capture. The three paired
payload/arrival/CFO cases use arrivals of 137, 411 and 73 samples and offsets of
−120, 0 and +120 kHz; those values are available only to the scoreboard.
A no-wanted-signal control at 2.484 GHz / 0.75 V is rejected.

The receiver's original 0.6 squared-coherence trigger misses observable training
in the inspected 2.4 GHz capture (coherence about 0.38–0.46). The selected control
uses 0.25, a 32-window plateau, repeated bounded searches and a separate 0.3
paired-long-training match. The 0.25 value corresponds to 0 dB SNR only in an
ideal independent-noise approximation; it is a receiver setting, not a protocol
mask or measured sensitivity. Independent noisy captures and noise/tone rejection
checks support it; the stricter trigger remains a same-capture control.
The 0.75 V / 2.4 GHz / −120 kHz case still fails CRC with 28 raw DATA errors and
about −4.6 kHz CFO-estimation error. Preserve that failure; the CFO error is an
observation, not an established sole cause.

**Still missing:** HE signaling/HE-LTF, standard scrambling and pilot polarity,
AGC, sampling-rate ppm, unknown packet length, frequency-aware soft metrics and
FPGA response timing. Two known DATA symbols still provide channel training.
This combination of legacy training and diagnostic DATA is **not a valid HE
PPDU**; compare the [HE packet structure](https://www.mathworks.com/help/wlan/gs/he-ppdu-structure.html).
The [coded report](../evidence/wideband-coded-control.json) and
[acquisition report](../evidence/wideband-acquisition-control.json) own the raw
observations and source hashes. Run `python3 verification/wideband_packet.py`
with or without `--acquisition` from the project directory to regenerate them.

**Differential-input fallback:** the [paired-input probe](../verification/reference_input_probe.py)
charges both pad loads, mismatch, finite common-mode rejection, one additional
signal site and 4 mA additional timing bias. Its matched RF controls charge that
current to both topologies. At the current target, eight paired and four 1 V
single-ended causal-SAR cases converge. Paired input retains 7–13 uncoded errors
at 2.4 GHz and 4–5 at 2.484 GHz, versus 17–21 and 4–5 for single-ended input.
These use different training from the coded controls; they are not packet results.
At 0.5 nH, assigned-ENOB differential controls retain errors as well.

The paired passive and converter-load transfers agree with independent seven-node
solutions. Converter recharge produces about 3–7.7 µV effective differential-input
perturbation across the checked grids, versus about 30 µV single-ended, with
roughly 0.54–0.57 mV rail perturbation. This supports common-mode rejection rather
than removal of supply noise. The most mismatched peaks are grid-sensitive; one
matched 512× RF / 0.25-versus-0.125 ns feedback comparison converges with nine
errors in both cases and little EVM change. This is not complete bandwidth or
physical-receiver qualification. The [probe report](../evidence/reference-input-probe.json)
owns the primary comparisons; use `--check` for network validation and `--causal`
for its current-package feedback campaign. Sustained wired readiness, actual
receiver CMRR/headroom and charged physical costs still precede a pin-map change.

**Model limits that still matter:** corrected threshold events now feed weak
and moderate wideband conversion, narrowband packets, bounded TX wake and wired
TX timing. Local monotonic brackets preserve the tracked root order, but extra
crossings outside those brackets remain unexcluded in the production model.
Stage-specific supply sensitivity, source AM, signal-dependent TX/pad current
and actual device noise/linearity are still assumptions or omissions. Wideband
EVM is sensitive to integration and training conditioning; use its persistent
failure, not an unconverged exact value, to guide architecture decisions.

Actual wired TX word events now drive the existing finite transport and its
emitted bits feed a peer window. Focused checks preserve data identity over
104.9 µs and expose underflow when observed pacing stops. This uses the selected
59/64 allocation, not the reusable model's legacy default. It does not establish
full-duration peer readiness, physical CDC, pad muting or recovery. Supply
modulation now propagates from the TX driver through persistent channel/CTLE
state, independently checked against real state-space evolution. The corrected
model retains the phase failures above. Next bound the delivered timing waveform
and peer response across phase, including asynchronous host-harmonic drift;
nominal AC frequencies and a single RMS value are insufficient. The
selected-baseline report includes this integration and the nominal launch-phase
controls. Its recorded source hashes identify the evaluated implementation;
a regeneration is required after model-source changes.

Numerical details and controls have one owner in [power and joined evidence](power-partition.md):
[weak RF diagnosis](power-partition.md#weak-wideband-failure-paired-impairment-diagnosis),
[conversion feedback](power-partition.md#closed-loop-converter-and-reference-load-requirements),
[narrowband exchange](power-partition.md#selected-narrowband-packet-exchange),
[driver wake](power-partition.md#driver-wake-under-the-selected-shared-environment),
[wired timing/recovery](power-partition.md#wired-equalization-host-delivery-and-recovery),
and [USB common return](power-partition.md#usb-high-speed-quiet-pin-and-common-return-gate).
Older detailed assessments below retain their stated assumptions; they do not
supersede this corrected-environment verdict.

### Big-picture closure priorities

The architecture choices are closed for implementation. The remaining work is
to establish an operating envelope for that architecture, not to select another
menu of blocks. This is the authoritative work order; component studies below
do not create competing queues.

| Priority | Required outcome | Decision it must support |
|---|---|---|
| 1. One usable analog envelope | Shared package/host activity, delivered clock, RF noise/linearity, converter dynamics and pad loading meet their requirements together. Bound the clock-input mitigation using the same full mode currents. | Keep or change the chosen operating point with explicit external-component, current and headroom costs. Do not hide failed baseline cases. |
| 2. Complete operation | Blocked RF request/reply, sustained wired TX/RX with recovery, and USB/PCIe generic electrical lifecycles run with finite host service and storage. | Determine which generic controls and timing guarantees are sufficient; add hardware only for an identified missing behavior. |
| 3. Physical and resource fit | Reconcile the 74 compatible sites, rough 12.92 mm² allocation, complete mode currents, returns, external parts and heat. | State the allowable assembly and cooling requirements. Do not assume isolated grounds, a different package or unallocated storage. |
| 4. Capability-wide acceptance | Each retained target has electrical, acquisition, interference, emissions and timing criteria against the same environment. | Separate demonstrated behavior, assigned requirements and missing proof. A representative pass never silently qualifies related protocols. |

**Thermal boundary:** nominal planning ledgers deliver about 0.727 W in RF
and 0.859 W in full-duplex wired mode. Treating all delivered electrical power
as die heat gives a conservative requirement: the 32 °C junction ceiling at
25 °C ambient needs effective junction-to-ambient resistance below 9.63 and
8.15 °C/W, respectively. At 20 °C ambient the limits are 16.50 and 13.97 °C/W.
These are budget-derived requirements, not measured package resistance or a
validated maximum dissipation. External clock input power and uncertain device
currents still need accounting; exported signal power can reduce die heating.
Specify cooling/stage temperature or a demonstrated thermal path. Controlled
ambient alone does not fix junction temperature.

“Several credible ways to succeed” means complete operating configurations
within the selected chip: external versus autonomous timing, configurable rates
and bandwidth, and explicit board assistance. Reduced host switching is useful
only with proven data service; external filtering and clocks are useful only
when loading, current, frequency coverage and recovery also fit. Additional
sweeps must answer a decision or close an acceptance gap.

Public Run 1 connectivity constrains assembly planning to 74 bond sites,
70 numbered connector contacts, common ground and eight separate board supply
feeds. It does not establish on-die isolation, GHz performance or applicability
to a future run. The [pin-plan evidence](../../../docs/roadmap/programmable-transceiver-pin-plan.md#public-run-1-assembly-evidence)
owns those findings. Preserve the provider-compatible assembly boundary.

### Decisions applying to the whole chip

The priority table above owns the work order. The decisions below constrain
all model and physical alternatives; they do not establish a second work queue.
Completion requires agreement between the architecture, contract and executable
model. Schematic work remains deferred until those gates close, and any proposed
scope reduction must be explicit rather than silently dropping a target.

| Boundary | Decision now | Consequence / unresolved condition |
|---|---|---|
| Assembly | KEEP wafer.space-provided COB and compatible bond geometry | Analog signal cells/custom frontends are permitted design choices; ordinary GPIO is not the RF/serial architecture. Fixed power/ground wiring constrains isolation. |
| Size and terminal budget | KEEP one full slot; SELECT the provider-compatible 74-site physical allocation; retain the 50-entry drawing only as a legacy logical model | The pinned default 1×1 template has 56 signal sites and 18 supply/return sites, 74 total listed sites. Our 36+14 allocation is not its bond map. Do not remove provider sites or claim 50 physical bonds by leaving signals unused. |
| Power | KEEP CORE/HOST/WIRE/RF/PLL as accounting groups; CHANGE independent-rail assumption | Shared external feeds and returns are the conservative baseline until a compatible map demonstrates separation. Local filtering/regulation costs headroom, current and area. |
| Functional sharing | KEEP RF/wired payload exclusivity, specialized frontends, common host/control | Clock distribution, bias and host switching remain active with either payload. No power/area credit for imaginary removal of inactive circuits. |
| Host | KEEP two 10-bit DDR buses and paper scenario H0; Zynq-7000 eventual bring-up candidate | FPGA hardware is not required now. Exact board/bank compatibility is open; input loading and both directions' edge currents belong in the common environment. |
| Timing | KEEP autonomous and external sources, plus on-chip wired RX CDR | Source selection alone does not establish a low-noise delivered clock. Qualify the full source → input → phase generation → distribution path. |
| Radio clocks | KEEP LO-derived conversion/D2H as the evaluated candidate, not the only allowed architecture | Explicit retune recovery required. Fixed conversion/host timing remains an alternative requiring a real source and CDC budget, not just an FPGA resampler. |
| Radio duplex | KEEP scheduled same-channel TX/RX with clocks running | Radio TDD switching should not restart the LO or retrain the host. Retuning is a separate lifecycle. Full same-frequency duplex is not assumed. |
| Processing and storage | KEEP modem/controllers, interpolation/resampling and bulk storage on FPGA | Chip must still meet unavoidable sample/word and electrical-response deadlines. No unspecified FPGA algorithm or deep buffer may hide lost samples. |
| Protocol genericity | KEEP all requested targets as investigations; no chip protocol IDs | Each capability needs electrical actions, timing and observability. No target has earned a complete-support verdict. Tier proposals do not authorize dropping features. |

The template counts come from `librelane/slots/slot_1x1.yaml` and
`src/slot_defines.svh` at provider commit
`0de7e394337a1f7f5303ac7a3681bf2481b58176`, not from an assumed delivered PCB.
The foundry-pad branch of `src/chip_top.sv` also ties core and I/O supplies.
These facts supersede the old logical pin count; they do not establish final
bond-wire geometry, board-net isolation or pad electrical performance.
[Provider source](https://github.com/wafer-space/gf180mcu-project-template/tree/0de7e394337a1f7f5303ac7a3681bf2481b58176).

The executable resource ledger now separates provider sites from logical pins:
36 functional signals + 18 fixed supply/return sites = **54**, even before
counting 20 spare signal sites. Thus unused signals alone cannot reconcile a
hard 50-total limit. The selected decision is standard-compatible packaging; the earlier approximate
limit is superseded for the physical design. No functionality has been removed. Also, neither the north
nor south edge's 16 signal sites can contain both 11-wire host directions;
the functional diagram's south-host grouping is not a physical pad placement.
See the [physical inventory](../../../docs/roadmap/programmable-transceiver-pin-plan.md#executable-physical-inventory-and-immediate-consequences).

A [candidate provider-site assignment](../../../docs/roadmap/programmable-transceiver-pin-plan.md#candidate-provider-site-assignment)
now places all 36 functional signals: RF/reference west, wired east, D2H/control
south and H2D north. It preserves fixed supplies and adjacent analog pairs,
with both forwarded clocks and REF_IN next to existing ground sites. It leaves
20 unused signal sites, not 20 removed bonds. Host data returns, actual PCB
connectivity, specialized signal-cell geometry and electrical qualification
remain open; the selected provider-compatible physical allocation supersedes
the former approximate 50-total limit.

### Current system decisions

| Coupled requirement | What the model now establishes | Decision / remaining barrier |
|---|---|---|
| Shared supply and die area | Nonideal 500 pF candidates restore sampled rail containment and substantially reduce modeled far-offset TX sidebands; plate cost is bounded separately. | SELECT the normative 500 pF local / 1 uF board reservoir network with a 0.25 nH common-return assembly target for the next model revision. This supersedes the earlier candidate-only status; real impedance, compatible bond geometry, support area, TX-load feedback and supply sensitivity remain unproven. See [selected network](block-diagram.md#choices-fixed-for-the-next-model-revision) and [power/resource ledger](power-partition.md#joint-capacitance-and-supply-screen). |
| Delivered LO spectrum | Loaded-input noise can destroy blocked packet acquisition despite small clean-signal EVM changes. Independent spectral integration supports the scale of the effect. | CHANGE clock acceptance from RMS-only reasoning to a delivered spectral mask at blocker offsets, including source, input, phase generation and distribution. Quieter tested allocations still fail some packets. See [clock requirement](clock-feasibility-envelope.md#blocking-imposes-a-stronger-spectral-clock-requirement). |
| RF noise and selectivity | Lower assigned NF plus retuning the existing filter improves weak blocked reception, but additional seeds/cutoff variation retain failures. | KEEP configurable filter/gain, but do not select a robust setting yet. Preserve real-preamble and interference checks; improved ADC precision alone did not solve this case. Detailed evidence is below. |
| RF linearity before filtering | An assumed −10 dBm IIP3 fails a two-blocker test that passes with 0 dBm IIP3 and an ideal delivered clock. | REQUIRE a joint NF/gain/IIP3/headroom/current allocation. A passing linearity fixture cannot be combined with a separately passing clock fixture by assertion. See [RF-chain budget](#rf-chain-and-converters). |
| Shared wired/DC pads | Disabled capacitance consumes fastest-lane margin; independent passive/drive/sensing primitives now exist mathematically. | KEEP sharing with an explicit capacitance budget. Negotiation, timed control application and physical switch behavior remain open. See [pad gate](feasibility-gates.md#shared-usbserial-pad-inactive-loading-decision). |
| Whole-chip implementation | Resource ownership is defined, but budgets are allocations rather than instance estimates. No target has a complete accepted envelope. | KEEP all requested capabilities in scope and defer schematic work. Close physical fit, common conditions, lifecycle and per-target acceptance; no silent scope reduction. |

**No complete fallback is yet demonstrated. A [conditional combined RF point](#combined-rf-requirements-point)
now passes six tested requests with finite linearity and loaded timing, but
its physical costs and tolerance envelope remain open.** External clocks, local decoupling,
filter retuning and lower-noise/more-linear stages are candidate routes with
measured-in-model benefits and unpriced physical costs. The task is to combine
compatible requirements into costed operating alternatives, not declare success
by selecting the best result from each row. Thermal/slew estimates do not rule
out the tighter clock target, but simultaneous GHz speed/noise/power remains
high risk rather than proven impossible.

The [continuous-state wake/mute screen](power-partition.md#continuous-state-wakemute-screen)
now narrows one transition uncertainty: the assigned passive network tolerates
a controlled 28 mA load ramp with 59.36 mV incremental droop and sub-0.1 us
post-ramp recovery to a diagnostic 1 mV residual. This keeps parked-bias wake
worth evaluating, but does not establish RF/clock readiness or packet turnaround.
Warm bias remains the fast-response baseline; neither alternative has a complete
instance/current inventory or a joined transition qualification.

### One environment, not one identical clock for every interface

The [whole-chip clock ledger](clock-rate-ownership.md#whole-chip-clock-configurations-and-a-lower-switching-rf-candidate)
now separates four source configurations and checks rate capacity across the
numeric envelope. It identifies a practical candidate: halve RF D2H frequency
while retaining fast H2D and all 12-bit I/Q payload. Bulk capacity passes, and
a paired DC/spectral receiver study shows a 21.5 mA assigned current saving
and improved EVM in the harsher H2D case, retaining equal spectral bandwidth.
Keep this mitigation candidate. A conservative continuous-service bound puts
half-rate RF outstanding data at about 0.84–0.86 kbit, leaving only 0.17–0.20 µs
of additional service interruption against the 1 kbit planning allocation.
Live scheduling and complete packet turnaround remain unverified; larger FPGA
storage does not cover chip-link stalls. Large rail ripple and unknown physical coupling still
prevent qualification. Independent fixed conversion
during external-LO retuning remains unallocated; it cannot be assumed as a
cost-free alternative.

External timing also depends on the protected input, not only source phase
noise. The [loaded-input envelope](clock-feasibility-envelope.md#protected-input-with-bond-loading-and-amplitude-to-timing-conversion)
now includes bond/return inductance, termination, receiver threshold offset and
source amplitude variation. Assigned cases include both resonant voltage
peaking and inadequate slew; 4.8 GHz can lose threshold crossings under an
adverse load. Keep the external-source route, with matching/damping, bias and
noise requirements evaluated jointly. None of these passive sweeps demonstrates
GHz receiver/transistor speed or establishes the provider package parameters.
The input now also shares a single clock allowance with source phase noise,
I/Q mismatch and downstream stages: some assigned loads leave a source-noise
budget, while others consume it before source noise is added. The latter need
an input/bias/amplitude change; a cleaner external oscillator alone cannot
rescue that assigned operating point. A positive inverse budget remains a
requirement to implement, not evidence that the input circuitry meets it.
The [explicit source/input comparison](clock-feasibility-envelope.md#explicit-external-source-and-input-intersection)
now tests −115 dBc/Hz at 100 kHz at the external plane: the assigned 3 pF,
2 nH, 2.4 GHz high-impedance input fits the diagnostic allowance, while 50 Ω
termination needs a cleaner source (at most −116.07 dBc/Hz) or improved input
noise/offset. The loaded path now reaches the paired synthetic RF/wired receiver comparison:
RF EVM is 7.40% high impedance / 7.47% terminated versus 7.26% with the ideal
delivered source, and the short wired cases retain zero errors. The loaded-input packet path is now connected and fails weak blocked
acquisition under the assigned additive-noise spectra. Loaded-input calibrated
air timing, TX, circuit current/startup and correlated noise remain open.


Every joined test must reference the same versioned environment containing:
assembly/pad network; physical rail connectivity; host drive/load/activity;
clock source and stage noise/transfer functions; temperature/DC operating point;
converter/reference and RF/wired path parameters; external components; and
finite host service/storage. Mode-specific settings are permitted and necessary.
Different RF/wired carriers use the same underlying noise model evaluated at
their actual frequencies, rather than blindly copying one RMS jitter number.

The causal chain is bidirectional: the selected host **and chip pad drivers**
set switching current; the package/board network produces rail disturbances;
clock and analog transfer functions produce jitter, spurs, gain/reference errors;
those impairments affect acquisition, payload and host service. RF/TX loading
also perturbs supplies. Include deterministic phase correlation and shared
reference noise, rather than treating every disturbance as independent.

Current 60–124 mV harmonic peaks are assigned-network stress results, not
measured bounds. The next whole-system calculation must sweep frequency-dependent
supply-to-delay/phase and analog coupling, and report the maximum tolerable
transfer functions. Until those tolerances overlap evidence-backed circuit
ranges, physical feasibility remains open. A nominal external source does not
remove downstream supply sensitivity.

### End-to-end capability assessment

These rows cover the intended families without conflating signaling rate with
protocol support. `Open` means no complete joined acceptance contract has passed;
it is not a claim that no useful component tests exist.

| Family / targets | Complete path that must work | Main architectural gap | Decision |
|---|---|---|---|
| PCIe Gen1 | Detection/idle → training → independent RX/TX clocks → continuous encoded words → error/recovery | CDR tolerance + physical detector/idle controls + bounded host service in one environment | KEEP; lifecycle anchor; open |
| 1000BASE-X / SGMII | External PCS negotiation → persistent full-duplex stream → rate compensation → loss/reacquisition | Sustained clock-rate matching and protocol-specific control semantics, beyond NRZ eye | KEEP; sustained-service anchor; open |
| SATA Gen1 | OOB bursts/gaps → detection → clock acquisition → payload → reset/recovery | Generic burst/detect scheduling and handoff have no complete physical/latency envelope | KEEP; explicit OOB closure; open |
| USB HS device and host | Attach/reset/chirp → line states/termination → packets → bounded response → disconnect/recovery | Shared-pad loading and host round-trip latency must pass together; lower-rate host cases already fail | KEEP; DC/shared-pad lifecycle anchor; open |
| HDMI / DVI TMDS | Common clock → three lane chips → word/phase alignment → continuous video → resynchronization | DC pad loads and coordinated FIFO/clock recovery across independently controlled chips | KEEP multiple-die construction; open |
| DisplayPort RBR | External AUX/training controller → requested swing/equalization → one lane → recovery | Electrical training controls and continuous lane delivery; no claim of full multi-lane display system | KEEP one lane per die; open |
| HD-SDI | External coax equalizer/driver → recovered/forwarded serial stream → continuous framing | Channel/CDR interaction and sustained service at integer/fractional rates | KEEP external coax support; open |
| HE20 Wi-Fi / custom OFDM SDR | Real acquisition → AGC/blocked RX → FPGA modem → scheduled turnaround → spectrally acceptable TX | BPSK diagnostic success does not cover full packet acquisition, higher MCS, sensitivity or emissions | KEEP HE20 target; declare achieved modulation subset only after qualification; open |
| BLE / proprietary 2.4 GHz GFSK | Actual preamble/access detection → blocked RX → scheduled reply/hop → reacquisition | Loaded-clock reciprocal mixing, pre-filter linearity, filter-selectivity tradeoff and radio/host transitions | KEEP; require one joint operating point and separate same-channel exchange from hopping; open |
| Bluetooth Classic BR/EDR | Acquisition/hopping → GFSK/phase-modulated payload → TDD recovery | Complete hopping timing, phase quality and mode changes in one chain | KEEP; open |
| IEEE 802.15.4 | SHR acquisition → O-QPSK packet → turnaround/response under blockers | Real synchronization, packet/error acceptance and RF switching | KEEP; open |
| 2.4 GHz LoRa | Configured actual preamble → frequency/timing recovery → chirp payload under interference | Synthetic-prefix gain cannot be counted as standard-compatible acquisition | KEEP; real-preamble decision required; open |
| Lower-frequency RF / external conversion | Specified external frequency plan → existing baseband/RF limits → packet/stream | Matching/tuning coverage, external conversion images/noise and support boundary | Existing STRETCH goals; not baseline closure substitutes |

No row can inherit a pass from a faster line rate or a wider RF bandwidth alone.
High-speed bandwidth does not prove DC electrical compatibility, burst detection,
weak-signal sensitivity or narrowband oscillator stability. External FPGA work
can supply protocol semantics; it cannot fix clipped analog signals, missing
observations or an electrical action whose command arrives too late.

### Generic control-surface verdict

The [current macro-boundary audit](../integration/macro-contract.md#current-generic-control-surface-audit)
and contract now map 17 interface targets, including HD-SDI, custom GFSK/SDR and
both RF stretch goals, onto nine shared generic services. Every target still
has unresolved implementation/latency obligations. This is a requirements
inventory, not a claim that a generic trim word implements the actions.

The largest shared gaps are atomic numeric configuration, clock/status events,
timed pad/direction changes and live epoch recovery. Current SPI stores coarse
trims; candidate recovery addresses and many behavioral operations do not reach
the physical macro. Extending these generic services can serve multiple targets
without protocol IDs, on-chip modems or packet buffers. First prove their
semantics and bounded application/observation timing in the mathematical model.

### Required operating sequences and ownership

| Sequence | Chip responsibility | FPGA/board responsibility | Evidence needed before acceptance |
|---|---|---|---|
| Cold start | Safe pads; bias/reference settle; source selection and lock; converter reset; link training; publish ready epoch | Stable supplies/clock; train capture; prepare paced data; authorize run | Worst allowed startup conditions and no premature pad/sample activity |
| Same-channel RF turnaround | Preserve timing; scheduled mute/bias/path changes; bound settling and first valid sample | Prepare reply in advance; coordinate board RF switch/PA and FPGA processing | End-of-RX to valid TX (and reverse), including AGC/DC transients and real protocol deadline |
| Channel retune | Stop old publication; safely gate affected clocks; change source; settle/lock; reset converter phase; train and publish new epoch | Discard stale data; reacquire source-synchronous capture; reconfigure resampler; pace new stream | No malformed clock pulses reaching active capture; bounded outage and stale-data exclusion |
| Wired startup and recovery | Detect electrical state; acquire CDR; word boundary/idle control; expose readiness and faults | Protocol training/coding; manage queue rates; rearm current epoch | Full required control sequence, clock offsets and traffic patterns with finite queues |
| Continuous video | Preserve stream/clock phase; account for fixed pipeline and elastic occupancy | Common clock/fanout and cross-chip alignment; uninterrupted source/sink | Long-run occupancy bound, bounded skew; explicit behavior after one lane faults |
| Underflow, overrun or clock loss | Immediate defined electrical fallback; invalidate publication; keep independent SPI/reset path | Stop/recover protocol, drain or discard by epoch, retrain and reauthorize | Finite detection/reaction latency; no replayed stale packet and no uncontrolled RF/line output |
| RF ↔ wired reconfiguration | Stop payload; isolate old path; configure services; settle; train fresh epoch | Select external recipe, change board support as needed, authorize new mode | Exclusive payload invariant through all transitions, not just steady state |

The [executable transition service contract](clock-rate-ownership.md#executable-transition-service-contract) now rejects clock-changing turnaround and prices retune/training/recovery with explicit assigned durations. It does not yet execute analog transitions or enforce epochs in the persistent payload path.

These are architectural requirements. Existing fixtures implement subsets;
there is not yet one executable lifecycle proving every row. A list of desired
controls in a diagram is not a proven command-to-pad interface.

### Current joined host, power and receiver assessment

The consolidated [robustness report](../evidence/robustness-envelope.json),
`whole_chip_operating_envelopes`, now pairs RF and wired operation using one
explicit network, host pulse shape, delivered-source spectrum and stage-delay
model. Both consume an itemized DC ledger and frequency-resolved disturbances.
RF includes reference modulation; wired amplitude uses an explicitly assumed
rail-proportional stress. The modes have different rates and active loads, never
simultaneous payloads. This is a consistent comparison, **not physically bounded
whole-chip closure**. Older isolated studies below retain their stated scopes.

| Paired environment | RF current / nominal local rail | Wired current / nominal local rail | Conservative RF / wired rail interval | Receiver diagnostic |
|---|---|---|---|---|
| 1 µF board hypothesis, 0.3 pC H2D internal charge | 107.6 mA / 3.123 V | 189.5 mA / 2.994 V | 2.85–3.39 V / 2.73–3.25 V | RF 7.30% EVM; wired zero errors in 12 short channel cases |
| Same board, 7 pC H2D internal charge | 130.6 mA / 3.074 V | 212.5 mA / 2.946 V | 2.24–3.91 V / 2.13–3.76 V | RF 8.35% EVM; wired zero errors in 12 short channel cases |

**Architectural consequence:** passing receiver diagnostics do not establish a
usable operating point. The adverse case cannot guarantee even the assigned
2.5–3.6 V linear-fixture range; the interval is a conservative sum-of-tones
bound, not a measured excursion. Increasing the modeled board capacitor to
10 µF barely changes this high-frequency result. Resolve input switching charge,
shared return and local isolation requirements before crediting those passes.
Board capacitance alone is not the demonstrated mitigation.

These are hypotheses: RF uses its 37 mA reservation, while wired deliberately
uses its full 96 mA WIRE allocation as a stress, including locally supplied
drive. Neither is a current measurement. Externally supplied TMDS termination
returns need a separate current port. The 1 µF value matches a Run 1 footprint
label, not measured populated impedance. Package inductance, the 2 Ω local
branch, 100 pF die decoupling, source noise and delay sensitivity remain assigned.
The delivered-source spectrum is a requirement on either clock route, not proof
of autonomous synthesis or the external-input chain. RF acquisition is synthetic
here; the separate joined packet study below adds physical noise and actual
acquisition and a loaded reply observed by an independent peer; physical
launch timing and emission limits remain unqualified.

Use `python3 verification/robustness_envelope.py --whole-chip` from the project
directory for this approximately six-second comparison. It prints JSON without
refreshing the broader evidence report; no full campaign is needed for this
architecture feedback loop.

| Boundary | What is now joined | Remaining qualification |
|---|---|---|
| Host currents | D2H output charging/internal current; H2D chip-internal current and separately powered signed capacitive return | Actual charge/edge waveforms, stochastic data spectrum, compatible topology and complete current inventory |
| Power | Common feed, shared return, local branch; CORE/PLL/RF/HOST are loads rather than independently powered rails | Fixed provider bond/board map; local isolation realization; supply-dependent current, leakage and self-heating |
| Clock disturbance | Complex rail phasors through coherent frequency-dependent stage-delay responses | GF180 stage sensitivity, oscillator pushing, true source/loop spectra and correlated paths |
| RF RX | Resolved mixer harmonics, analog filtering, implicit high-offset ADC crossings, converter and diagnostic acquisition | Real packets/preambles, sensitivity/blocker masks, higher modulations, physical reference/gain coupling and TX/RX transitions |
| Wired RX | Disturbance moves all four analog observations of existing causal recovery loop | Long-run BER, protocol traffic/acquisition, physical timing detector, host service and pad constraints |

**Absolute RF levels change the verdict.** Earlier joined fixtures assign
frontend noise as 4% of signal amplitude. They do not demonstrate sensitivity:
weakening a signal while retaining that ratio preserves SNR. The new
`absolute_rf_input` comparison uses the existing matched-input thermal-noise
budget with assigned 300.15 K, 20 MHz ENBW and 10 dB receiver noise figure.
It retains the half-rate D2H mitigation, host/clock/reference disturbances,
8 ENOB and a blocker 20 dB above wanted at 12 MHz offset. External preselection
attenuates wanted by 2 dB and blocker by 20 dB. The noise figure is an assumption,
not GF180 evidence; passive loss contributes to the antenna-referred budget.

| Antenna wanted power | Required conversion voltage gain at assigned output scale | Diagnostic EVM across assigned host/feed cases | Acquisition |
|---|---:|---:|---|
| −65 dBm | 63 dB | 8.32–10.81% | Acquired in these fixtures |
| −75 dBm | 73 dB | 20.83–24.41% | Acquired; not a packet sensitivity result |
| −85 dBm | 83 dB | 70.75–90.20% | Failed in these fixtures |

The gain figures assume 1 V per normalized complex-envelope unit and reset
gain per case to preserve the current signal scale. Physical gain range,
gain-dependent noise/current, early-stage blocker compression and AGC settling
are **not demonstrated**. Integrated noise is still approximated as white at
the filter output, and training remains synthetic. None of these levels is a
new accepted protocol sensitivity specification.

**Decision:** retain the radio targets, but prioritize an absolute sensitivity,
gain/headroom and real-acquisition envelope over further optimizing normalized
strong-signal EVM. Source-clock mitigation alone does not resolve this gap.
Narrower selectable bandwidth can lower integrated noise for narrowband modes;
it cannot be credited to a 20 MHz signal without preserving that signal's
occupied bandwidth and acquisition. The RF current allocation has not earned
the assumed 63–83 dB gain or 10 dB noise figure.

**Real packets now consume the shared environment.** The
`shared_packet_lifecycle` section uses LE 1M scan requests on channel 38 with
actual preamble/access address, whitening and CRC. Framing remains checked
against the independent [Bluetooth packet vector](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/low-energy-controller/sample-data.html).
The FPGA observer acquires from the known prefix alone and accepts a response
request only after CRC and advertiser-address checks. No chip packet engine is
introduced. A valid scannable-advertising receive window is a precondition;
the preceding advertisement is not simulated.

The same board/host/rail/source hypotheses now drive downconversion, thermal
noise before filtering, divided-LO sample crossings and ADC-reference ripple.
The 2.426 GHz LO produces 9.4765625 MS/s; FPGA resampling supplies the 10 MS/s
observer and charges its 32-input-sample lookahead. The assigned 20 dB early
gain precedes the 0.7 MHz fifth-order filter; the main PGA starts at 40 dB and
is bounded to 0–60 dB. ADC-only gain feedback includes derived sample delivery,
FPGA decision and command/CDC delay (about 1.80 µs), one pending update and
0.2 µs settling. NF remains 10 dB and converter performance 8 ENOB hypotheses.

Unlike the older isolated packet comparison, this joined case gives **both
wanted and adjacent blocker 2 dB external insertion loss**. It does not grant
20 dB external rejection at only 2 MHz separation. With a −40 dBm blocker,
three of three −80 dBm requests decode; zero of three −90 dBm requests decode.
Without that blocker, the three −90 dBm packets acquire but fail CRC. Removing
thermal/ADC noise and independent aperture noise lets the selected weak control
decode while retaining the shared spectral clock: the assigned noise/gain/
receiver combination remains a limitation, not just clock quality. These tiny
samples establish neither PER nor sensitivity. The large-H2D-charge environment
still cannot guarantee the voltage-model range, regardless of packet outcome.

A successful request enters a same-channel response-readiness timeline: last
sample delivery → FPGA reconstruction/decision → command framing/CDC → safe
boundary → assigned analog settling → bounded sample prefill → scheduled launch.
The [Bluetooth advertising exchange](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/low-energy-controller/link-layer-specification.html)
uses fixed 150 µs inter-frame spacing. About 140 µs remains after modeled
preparation with 2 µs FPGA work and 2 µs analog settling. The 768-bit prefill plus
124-bit service backlog comparison fits the 1,024-bit per-source allocation;
this is not a complete physical FIFO inventory or measured occupancy. A 160 µs
FPGA-work control misses the deadline and does not arm a reply. LO, ADC and
host clocks keep running; stream epoch stays unchanged.

The reply now continues through a finite generic sample FIFO, actual divided-LO
DAC edges, quantization/reference variation, reconstruction filter and the
existing IQ/driver model into a 40 Ω source / 50 Ω load. A separately clocked
strong-signal peer decodes all three nominal successful replies. FPGA memory
holds the prepared response; the chip queue peaks at 32 I/Q samples (768 bits)
and consumes nothing during the clocked wait. A 10 µs host-service interruption
exhausts that prefill, latches mute and prevents peer decoding. This is supplied
arrival timing with finite queue behavior, not a simulated serialized bridge.

| Reply observation, nominal valid-range hypothesis | Result | Meaning |
|---|---|---|
| Uncorrected RF half-amplitude start after request end | 151.02–151.19 µs | Packet readiness alone does not align the emitted waveform |
| Same marker with fixed 0.8 µs RX correction and 0.15 µs TX advance | 150.07–150.24 µs | Candidate calibration requirement; values are assigned and unchanged across packets |
| Average active power into declared differential 50 Ω load | About 3.41 mW | Conditional loaded output; matching/antenna performance is unqualified |
| Model voltage/current/energy checks | Within assigned bounds | 28 mA driver reservation is already included in the 37 mA RF reservation |

The marker is an envelope threshold, **not the standard's first-bit timing
measurement**. Peer acquisition contains its own receive delay. Doubling TX
mixer resolution preserves decoding and changes the selected marker by about
0.21 ns; numerical convergence does not calibrate silicon. High-H2D-charge cases
also decode but still cannot guarantee the voltage-model range.

**TX spectral energy changes the priority.** Hann-weighted integration of the
loaded reply, before any external RF filter, puts about 39 µW beyond ±40 MHz
in the nominal case: 1.15% of resolved total power, or −19.33 dB relative to the
central ±1 MHz band. The adverse H2D-charge case puts about 802 µW there, roughly
24.4%, despite peer decoding; that case also lacks a guaranteed valid rail range.
Power normalization is checked against known RF envelopes and Parseval energy.
These broad band integrals are not standard measurement-bandwidth emission
limits. RF harmonics and physical switching splatter remain outside the model.

The `tx_clock_spurs` sweep now locates this risk across 2.400–2.484 GHz in
2 MHz steps. It applies the shared supply-derived phase to a unit carrier,
including nonlinear mixing between tones, then projects through an **ideal**
fixed full-band filter. It is an optimistic limit on external filtering, not a
chosen component or emission mask. Equal modeled harmonic bandwidth and the
same fixed host-current/phase hypotheses are used for each divider.

| Forwarded D2H clock | Assigned nominal current | Worst surviving unwanted/carrier ratio, small H2D charge | Same ratio, adverse H2D charge |
|---|---:|---:|---:|
| LO/16, existing full rate | 128.2–130.1 mA | −55.0 dBc | −27.6 dBc |
| LO/24, exploratory intermediate rate | 114.1–115.5 mA | −51.9 dBc | −49.1 dBc |
| LO/32, existing reduced rate | 107.1–108.2 mA | −49.9 dBc | −33.5 dBc |

These are aggregate surviving phase-sideband powers relative to the carrier,
not power in a standard measurement bandwidth. Every adverse-charge row still
fails to guarantee the voltage-model range. LO/24 is an analysis candidate;
it is **not** supported by the present operating contract, physical divider or
transition API. Its extra divider implementation/noise has not been priced.

The reduced-rate case puts a 75.25 MHz-offset line at 2.48325 GHz when tuned to
2.408 GHz, inside the ideal filter passband. Full-rate clock harmonics lie
farther away, but nonlinear phase mixing still produces close-in difference
spurs: the adverse LO/16 case's strongest retained line is 2.5 MHz below a
2.480 GHz carrier. Improving only the filter stopband cannot remove these.
An illustrative −40 dBc aggregate retained-power allocation would require
roughly ≤0.050 or ≤0.070 ps/mV aggregate supply-delay sensitivity at the selected
adverse LO/16 or LO/32 worst carriers, respectively, versus the assigned
0.1 ps/mV. Those are inverse requirements at fixed parameters, not measured
GF180 limits or a fix for the invalid voltage envelope. Nominal rows already
meet that illustrative allocation; no looser sensitivity limit was searched.

**Clock/filter decision:** retain the full and reduced clock choices. Keep
LO/24 as a possible tradeoff, pending actual divider, transport and noise costs;
do not adopt it merely for a favorable assigned spur result. External output
filtering needs frequency-dependent rejection/insertion-loss bounds across all
carriers. A fixed full-band filter cannot remove lines within its passband.
Actual modulation broadens the lines; source noise, random host spectra,
relative host-phase variation and TX-load feedback remain outside this periodic
attribution. Use `verification/robustness_envelope.py --clock-spurs` for the
focused comparison.

**Decision:** retain generic timed same-channel turnaround and explicit delay
calibration. A connected request/reply now works under assigned conditions, so
prioritize supply-induced TX emissions, shared-rail validity and weak-signal
noise/gain/acquisition over additional clean packet fixtures. The model still lacks physical early-stage
compression, NF versus gain, gain-change phase error, driver/load feedback into
the PDN, measured output-enable behavior, TX emission limits and actual control/
bridge timing. Keep these open rather than equating CRC success with radio
qualification.

Use `verification/robustness_envelope.py --packet-lifecycle` for this short joined
comparison. `--ble-only` refreshes acquisition, lifecycle and loaded-clock packet sections only when all
other recorded model-source hashes are unchanged. Older ideal-gain/10 MS/s
packet cases remain diagnostic controls with their own assumptions, not the
current joined operating envelope.

**Gain placement and blocker headroom.** The `rf_gain_headroom` inverse screen
uses a ±1 V/component ADC, 0.8 V component peak limit, wanted peak/RMS bound of
three and a 5% ADC-noise EVM allocation. The assigned fifth-order 9.157 MHz
Butterworth filter rejects a 12 MHz tone by only 12.02 dB. In the historical
assisted case with 20 dB external blocker attenuation, a fixed −30 dBm blocker yields these necessary
gain intervals (gain measured after 2 dB wanted insertion loss):

| Wanted input | 8-ENOB permitted conversion gain | Verdict under assigned conditions |
|---|---|---|
| −65 dBm | 53.1–61.5 dB | Nonempty interval; not full receiver qualification |
| −75 dBm | 63.1–66.4 dB | Narrow interval; AGC cannot simply target constant ADC amplitude |
| −85 dBm | Minimum 73.1 dB, maximum 68.7 dB | No interval; gain changes alone cannot meet both constraints |

At −85 dBm, about 5.39 dB additional blocker rejection opens the assigned
8-ENOB interval; assigning 10 ENOB also opens it (61.1–68.7 dB). Neither option
fixes the independently observed thermal-noise/acquisition failure or proves
early-stage linearity. These two improvements are conditional on the historical 20 dB external
attenuation. Required external selectivity must be realizable at the specified
frequency separation; it is not a free filter parameter.

The screen now also retains **no selective external rejection**: both wanted
and blocker lose 2 dB before the chip. This is the architectural baseline until
a filter at the actual blocker offset is justified. The historical 20 dB case
therefore assumes 18 dB of selective rejection beyond insertion loss, not a
capability established by permitting external SMD passives.

| Wanted input, fixed −30 dBm blocker | 8-ENOB gain bounds | 10-ENOB gain bounds | Missing rejection at 8 / 10 ENOB |
|---|---|---|---|
| −65 dBm | 53.09 minimum > 50.41 dB maximum | 41.05–50.41 dB | 3.39 / 0 dB |
| −75 dBm | 63.09 minimum > 51.52 dB maximum | 51.05–51.52 dB | 13.39 / 0 dB |
| −85 dBm | 73.09 minimum > 51.90 dB maximum | 61.05 minimum > 51.90 dB maximum | 23.39 / 9.51 dB |

**Consequence for wideband RF:** even 10 ENOB does not open the weakest-signal
interval without more selective rejection. The narrowband packet result cannot
close this gap: its 500 kHz filter is a different configuration, and narrowing
a wideband filter until it discards wanted content is not a mitigation. Keep
three alternatives explicit: stronger channel-selective analog rejection at
unchanged useful passband, demonstrably realizable external selectivity, or
rebalanced converter/headroom requirements with current and area costs. The
5% ADC-noise EVM allocation is a design assumption; relaxing it must consume the
same total EVM/noise budget, not create a separate easier acceptance criterion.
No requested radio capability is removed by this finding. These are necessary
headroom bounds, not standards blocker limits or packet-error predictions.

**Bandwidth-preserving filter alternative.** The fast
`robustness_envelope.py --wideband-filter` inverse screen preserves the existing
HE20 fixture's outer tone at `122 * 20 MHz / 256 = 9.53125 MHz`. It assigns at
most 1 dB passband loss and includes that loss in the conservative desired-tone
headroom bound. With the same −85/−30 dBm wanted/blocker pair and no selective
external rejection, the necessary analog filter requirements are:

| Converter | Required rejection at 12 MHz | Minimum Butterworth order | Ideal elliptic order | Maximum pole Q |
|---|---:|---:|---:|---:|
| 8 ENOB | 36.41 dB | 22 | 5 | 11.24 |
| 10 ENOB | 22.53 dB | 15 | 4 | 8.34 |

The elliptic candidates use finite transmission zeros; this is a potential
extension of the existing tunable filter, not 22 newly allocated stages. Nominal
ideal magnitude responses meet the investigation bounds. Their passband group
delay ranges are approximately 45–418 ns and 27–301 ns respectively. Uniform
−2% frequency scaling breaks both passband and headroom bounds; +2% passes this
limited magnitude screen. Independent pole/zero/Q errors are not covered, so
these observations do not establish a trim tolerance. The current fifth-order
9.157 MHz Butterworth setting attenuates the fixture's outer tone by about
3.97 dB, an additional reason its flat-wanted headroom screen is optimistic.

A persistent-state waveform comparison now follows the magnitude screen
(`wideband_filter_waveform`, also printed by `--wideband-filter`). It drives the
same 24-symbol HE20 BPSK DATA sequence through the existing fifth-order
Butterworth control and the fifth-order finite-zero candidate. Analog modal
states continue across symbols. One known first DATA symbol trains an external
per-tone equalizer; boundaries are ideal and this is **not** a standard preamble.
At the shortest tested 0.8 us guard, the candidate gives approximately 0.74%
filter-only EVM and zero BPSK errors across the following 5,382 data bits.
The Butterworth control is effectively error-free after the same equalization.
Doubling envelope resolution from 8× to 16× changes EVM by less than 0.02
percentage points. Longer 1.6/3.2 us guards reduce the candidate's residual,
but are not substituted for the shortest-guard requirement. Common complex
gain correction alone leaves over 50% EVM for both filters: frequency-selective
external equalization is essential in this fixture.

This narrows the concern about filter delay, but it excludes blockers, ADC
noise/clipping, absolute RF noise, loaded clocks and coefficient mismatch.
The chosen filter is still a transfer function, not a transistor circuit. Keep
its tuning and internal swing requirements open; next join its actual response
to the RF/converter budget rather than treating clean BPSK decoding as a radio
verdict. The waveform comparison does not yet evaluate the fourth-order
10-ENOB alternative or its nonzero high-frequency feedthrough.

**Decision:** investigate finite-zero channel filtering before simply adding
poles or adopting a higher-precision converter. Preserve the full wanted
bandwidth and charge resonator Q, tuning, internal swing, noise and current to
the existing filter budget. A realizable response must also pass real-preamble
acquisition and waveform equalization/settling; a frequency-response pass is
not a radio pass. Keep the current Butterworth cases as controls. The 1 dB
allocation and per-tone worst-case bound are design probes, not standards
limits or an integrated OFDM EVM prediction. No schematic topology is frozen.

**Architecture decision:** use selectable limited early gain, channel filtering,
then the main variable gain before the ADC. The normative diagram now shows
this ordering. Active-filter internal nodes, LNA/mixer compression, NF versus
gain and settling remain explicit requirements. Do not select higher ENOB or
add an external amplifier merely to turn this necessary-condition screen green.

**Current common-feed RF result.** Assigned 2.437 GHz carrier, 8 ENOB, frontend
noise, +20 dB blocker at 12 MHz, external 20 dB blocker rejection/2 dB wanted
loss, 0.1 ps/mV aggregate clock sensitivity with 1 GHz pole. H2D alternates ten
data lines with its independent 156.25 MHz clock; D2H uses the existing
random-mean LO/8 word-rate model. RF 37 mA includes its driver reservation;
CORE 20 mA excludes explicitly itemized host switching by allocation definition.

| H2D internal charge | Common feed resistance | Total assigned chip supply current | Shared RF/clock/core DC rail | Diagnostic RF EVM |
|---|---|---|---|---|
| 0.3 pC/transition | 0.1 Ω | 129.05 mA | 3.120 V | 7.289% |
| 0.3 pC/transition | 2 Ω | 129.05 mA | 2.875 V | 7.328% |
| 7 pC/transition | 0.1 Ω | 152.08 mA | 3.071 V | 10.986% |
| 7 pC/transition | 2 Ω | 152.08 mA | 2.783 V | 10.278% |

The 10% threshold is diagnostic, not a standard mask. Every short fixture still
decodes without symbol errors. The calculation retains a 2 Ω local victim
branch and 20 mΩ shared return; it is a topology hypothesis, not permission to
change provider power pads. CORE/PLL/RF and H2D-internal loads share that branch;
D2H loads enter at the host/feed node. RF gain/noise scaling and assigned PGA
headroom use the calculated rail. Clock startup/tuning/noise, filter poles and
ENOB versus that rail remain unqualified. Large-ripple cases may invalidate
linear transfer assumptions before any nominal EVM conclusion applies.

**ADC reference is a separate coupling path.** `reference_supply` now applies
supply-derived reference modulation at actual conversion times, after RX
filtering. Quantization/clipping use the changing full scale; the FPGA observer
receives nominally decoded codes without an oracle reference correction. With
clock sensitivity reduced to 0.01 ps/mV, the 7 pC H2D cases give:

| Assigned reference transfer | Diagnostic EVM over the two common feed resistances |
|---|---|
| No supply feedthrough | 7.260–7.292% |
| 1 fractional-reference-unit/V, 1 GHz response pole | 37.38–39.73% |
| Same DC feedthrough, 10 MHz response pole | 7.363–7.405% |
| 0.1 fractional-reference-unit/V, 1 GHz response pole | 7.979–8.009% |

These are sensitivity hypotheses, not measured reference PSRR. For example,
156.25 MHz H2D modulation aliases to 3.9375 MHz at LO/64 = 38.078125 MS/s.
An RF input filter cannot remove reference modulation introduced at conversion.
The benign coherent D2H result therefore cannot establish converter immunity.
Keep both low-feedthrough and high-frequency-rejection options in the reference
architecture. A 10 MHz supply-response pole does **not** imply a reference driver
with sufficient ADC transient response: supply rejection and output impedance/
settling must be qualified together, including their area/current costs. DAC
reference and PGA gain modulation, real packets and physical bounds remain open.

**Decisions:** keep common-feed accounting and separate host current ports.
Lower feed resistance improves DC headroom but is not a sufficient harmonic
mitigation. Retain clock supply rejection/local isolation as independent design
obligations. FPGA charging power stays outside the chip supply ledger; chip
input/internal charge is counted once. Source power equals delivered electrical
power plus modeled resistive loss; delivered power is not all on-die heat.

The wired screen reinforces the timing concern: with assigned 2 pF/100 ps
channel, stronger host disturbance can lose clock qualification while all 1,200
held-out bits decode. Broad-response 1 ps/mV D2H-only stress produces bit errors;
0.1 ps/mV with a 100 MHz response pole restores the tested qualification.
Both-direction studies retain sensitivity to relative host phase. No short
error-free run establishes a protocol BER target.

The RF result cannot be inferred from the same RMS jitter alone. Coherent D2H
harmonics are integer multiples of the LO-derived conversion rate, and analog
filtering rejects much of their far-out modulation. Independent H2D timing
changes this relationship. Explicit 64/128 mixer-step comparisons converge
within 0.012 EVM percentage points in the prior D2H-only fixture, and implicit
ADC crossings are checked against independent root finding. Keep these
correlations in the model; do not replace them with independent phase-noise RSS.

Detailed inverse limits and scoped comparisons remain in report sections
`shared_timing_requirements`, `host_driven_wired_receiver`,
`host_driven_rf_receiver`, `bidirectional_host_receiver`, `common_feed_rf` and
`reference_supply`.
For example, the assigned 1 GHz stage-response case needs aggregate DC
sensitivity below 0.0235–0.0481 ps/mV for the earlier 2 ps diagnostic allocation;
this is a tolerable requirement, not a measured device bound.

### Combined RF requirements point

The `loaded_clock_packet_exchange.combined_frontend` comparison now combines
finite 0 dBm input IIP3, loaded clock input, 6 dB chip-input NF, 500 kHz
five-stage filtering, 8 ENOB, the nonideal 500 pF supply candidate and adverse
7 pC H2D activity. Wanted is −80 dBm and the two blockers are −30 dBm each at
+2/+4 MHz before 2 dB external loss. Six fixed packet seeds are compared.

| Clock-input requirements | Accepted requests |
|---|---:|
| Ideal delivered-clock control | 6/6 |
| High impedance: 250 µV input noise, 50 fs per downstream stage | 5/6 |
| 50 Ω: same noise allocation | 4/6 |
| High impedance: 75 µV input noise, 15 fs per downstream stage | 6/6 |
| 50 Ω: same lower-noise allocation | 5/6 |

Every accepted request in this comparison also produces a loaded reply decoded
by the independent strong-signal peer; calibrated air timing and TX masks remain
unqualified. Input voltage-noise and stage-jitter allocations refer to the same
1 kHz–8 MHz random-noise band used by the waveform model. The lower-noise cases give additive floors of −138.43 dBc/Hz
(high impedance) and −137.14 dBc/Hz (terminated), with source noise, 20 mV
threshold offset, ±10% input AM, host-induced phase and reference ripple still
present. Current reservation, stage count, converter precision and host service
are held fixed; they are not newly proven by changing noise parameters.

**Decision:** retain the lower-noise high-impedance case as a conditional joint
requirements point. It shows that the chosen mathematical functions need not
conflict at nominal conditions, but does not establish PER, process tolerance,
a validated noise spectrum or a current/area implementation. The original and
intermediate failures remain controls. Do not call the terminated case robust
or combine independently favorable values from other fixtures. The next
physical plausibility check must realize these noise, gain, IIP3, bandwidth and
load requirements in the same stage inventory and resource allowance. The
[resource conditions](power-partition.md#resource-conditions-for-the-combined-rf-candidate)
make the immediate constraint explicit: only 9 mA remains inside the modeled RF
load after the TX-drive reservation, and the quieter clock must fit the existing
12 mA static allowance plus separately accounted switching. RX/TX bias reuse
requires transition modeling before it earns a budget credit. No target has
gained a complete-support verdict from these six packets.

### Packet noise and filter evidence

A one-factor packet study now separates the remaining −90 dBm receiver
limitations under that same mitigated environment. Three seeds per condition:

| Change from 10 dB NF / 8 ENOB / 40 dB initial PGA | Quiet: accepted requests | −40 dBm blocker at 2 MHz: accepted requests |
|---|---:|---:|
| Baseline | 0/3 (all acquire, fail integrity) | 0/3 (no acquisition) |
| Remove thermal noise, attribution control only | 3/3 | 0/3 |
| Remove ADC equivalent noise, attribution control only | 0/3 | 0/3 |
| Require 6 dB NF | 3/3 | 0/3 |
| Require 10 ENOB | 0/3 | 0/3 |
| Start PGA at 60 dB | 0/3 | 0/3 |

**Decision:** prioritize input-referred noise and selectivity before spending
converter area/current or increasing initial gain for this diagnostic point.
The 6 dB NF case is a candidate requirement, not measured GF180 performance or
a qualified sensitivity claim. Its current, gain-dependent noise and linearity
costs remain unpriced. Noise-free controls are attribution, never design options.
For the blocker, the assigned fifth-order 0.7 MHz filter gives about 45.6 dB
rejection at 2 MHz. After equal 2 dB external loss, its residual is about 4.4 dB
stronger than the −90 dBm wanted input. Requiring a residual 10 dB below wanted
would need roughly 14.4 dB additional rejection, an illustrative design target
rather than a protocol limit. Filter changes must preserve real preamble
acquisition and account for delay, noise, headroom and retuning. The observer
may also contribute to the limit; this experiment does not prove an optimal
receiver cannot decode the baseline.

A subsequent filter-reuse experiment keeps five stages, the 6 dB NF hypothesis,
8 ENOB and the nonideal 500 pF supply candidate. Retuning the cutoff from
700 kHz to 500 kHz recovers the original three −90 dBm packets with the
−40 dBm blocker. Six additional seeds, not used to select that cutoff, expose
remaining margin limits:

| RX cutoff | Accepted blocked requests / additional seeds |
|---|---:|
| 475 kHz (−5%) | 6/6 |
| 500 kHz | 5/6 |
| 525 kHz (+5%) | 4/6 |

Arrival phase, packet contents and source CFO vary by seed; tested CFO includes
−80, 0 and +80 kHz. Accepted packets also meet the existing assigned reply
preparation budget. These small counts do not establish PER, a worst-case CFO
bound or production tolerance. In particular, do not select 475 kHz as a
qualified answer merely because it wins this additional set. The failed 500
and 525 kHz cases remain in the report. The 500 kHz failure acquires but fails
CRC; at 525 kHz one fails acquisition and another fails CRC. Better FPGA
detection/equalization might change these boundaries, so they are limits of
this complete modeled receiver, not proof of an analog impossibility.

**Decision:** retain filter retuning before adding stages, but do not adopt a
robust narrowband setting yet. The existing resource range can express the
candidate; physical RC tuning, settling, noise/current and packet-acquisition
margin remain requirements. This is now a joint noise/selectivity/timing problem,
not an argument for greater ADC resolution. The normative baseline and complete
support status remain unchanged.

### Scope of the next model integration

Follow the [big-picture closure priorities](#big-picture-closure-priorities).
The shared environment and connected RF exchange are now useful foundations;
the next integration must turn their assigned parameters into a consistent
operating envelope and explicit physical requirements. Further isolated passes
are not milestone progress unless they close one of those requirements.

No schematic-readiness claim until the five milestone requirements below are
verified. Detailed bond optimization and transistor experiments follow the
architectural decisions, rather than substituting for them.

### Milestone completion audit

| Objective requirement | Authoritative evidence now | Verdict |
|---|---|---|
| Consistent operating/power/pin/clock budget for every block | G0 ledger + contract + provider source show unresolved rail/terminal mapping and numeric tolerances | NOT COMPLETE; incompatible independent-rail assumptions identified |
| Package/host effects propagate into RF and wired performance | Robustness report includes host ripple and selected RF/serial screens; assigned harmonic stage-transfer/inverse budgets now exist, but wired causal receiver now consumes assigned host-derived timing; both directional host paths now feed RF/wired observers and an assigned common-feed DC ledger; ADC reference modulation now also reaches quantization; real LE 1M packet reception now joins these effects; DAC reference and loaded replies now reach an independent peer; physical bounds, PGA gain coupling, TX-load feedback and complete serialized service remain absent | NOT COMPLETE; joined causal chain incomplete |
| Feasible retune, turnaround and recovery | Architectural sequences plus connected same-channel RF packet/reply under assigned conditions; retune/fault recovery and physical timing not closed | NOT COMPLETE |
| Every target maps to controls and passes meaningful end-to-end criteria | Capability coverage in robustness report marks complete envelopes false; diagnostic acceptance explicitly not standard masks | NOT COMPLETE |
| Quantified uncertainty tolerances, mitigations and explicit decisions | Keep/change decisions above; some inverse resource bounds and conditional mitigations; common tolerances still open | PARTIAL; no complete robustness envelope |

## Current status

**Next decision sequence:** [G0–G4 and operating ledger](feasibility-gates.md#decision-sequence-several-credible-ways-to-succeed).
Default-ring/provider-COB compatibility is now mandatory. First resolve the
logical power-domain/terminal plan against the fixed bond and board map; prior
independent-rail studies do not establish compatibility. User owns a Zynq-7000;
physical host hardware is not required for this paper-model stage.

| Area | Current evidence | What remains unresolved |
| --- | --- | --- |
| Autonomous analog clocks | Counted acquisition and pulse-loop behavior demonstrated under declared tuning/noise assumptions. Historical loaded transistor tuning sweep changes slope sign. | Monotonic operating branch, cold startup, physical phase-noise spectrum, supply sensitivity and clock distribution remain unclosed. |
| Wired receiver | Detector now uses four voltage observations per receiver interval; corrections affect future samples. Causality tests cover ±3 UI, monotonic sampling and independence from future payload. Existing codec/recovery assertions pass. PCIe Gen1 compliance-pattern screen reacquires across 16 phase/frequency/interruption cases. | Physical detector, jitter/holdover envelope, arbitrary serializer restart phase and real protocol acquisition. Earlier source-indexed CDR measurements are historical. |
| Wired duplex | Independent RX/TX rates, observed-clock pacing, finite queues, timeout, explicit flush/new epoch and external framed rearm are exercised together. | Serialized management/acknowledgment, complete bridge implementation, physical idle and resource accounting. Raw unframed delayed rearm remains a negative control. |
| RF TX | Loaded host/converter/driver path with pulse synthesizer and count-acquisition interlock: 6.6362% EVM, zero errors, declared voltage/current limits pass. | Physical noise/linearity/bandwidth, output emissions, driver noise, full power/area and broader waveform envelope. |
| RF RX | Same loaded clock architecture, 12 mA bias, declared 10 dB NF/gain budget: 8.4977% EVM, zero errors; whole/split execution matches. | Sensitivity/blockers/compression, standard acquisition, higher modulation orders and radio turnaround. |
| USB | Incremental external FPGA parser, finite eight-record ingress, independent processing-clock phase and two-cycle ingress synchronization budget. Ingress-only crossing passes 324 faster-host cases; adding return command crossing fails all 12 focused exchanges (fast host 452–469 ns). | Independent parser-to-frame-builder clock architecture fails. Host-DDR-clock parser passes 108 faster-host cases; a proposed three-cycle final pipeline gives 29.167 ns margin but lacks implementation proof. Actual CDC/timing, causal receive sampling, transaction acceptance and attach/reset/chirp lifecycle. Slower host fails this sweep. |
| Chip↔FPGA bridge | Wide-block transport and CDC components have separate mathematical/RTL evidence. | One consistent selected implementation, physical GPIO timing and a usable external FPGA adapter. Old scalar implementation timing failures are not resolved by model passes. |
| Whole-chip fit | Legacy contract ledger: 50 logical entries, distinct from the selected 74 physical sites; 12.92 mm² including reserve and 350 mA domain ceilings; implemented totals explicitly unknown. USB bridge identifies 3,792 coexisting data-bank bits, excluding unresolved metadata/control. | One complete, non-overlapping ledger for storage, clocks, logic, analog, pads, protection, package and loads. |

RF results above are diagnostic HE20 BPSK fixtures with declared parameters,
not standard Wi-Fi packets or demonstrated silicon. TX uses 37 mA rail bias,
28 mA driver/current allocation, 40-ohm differential source into 50 ohms and an
external receiver anti-alias filter. RX uses the retained −56.86 dBm input
reference plane. Both observe count acquisition at 1.000025 ms and start
transport at 1.000050 ms; RX's independent +100 ppm source launches at 1.001 ms.
Counts establish average-frequency acquisition, not phase-noise quality.

The generic wired envelope now separates fixed-phase failure from recoverable
sampling offset. At 2.5 Gb/s, assigned 2 pF load, 100 ps driver time constant and
5 ps relative RMS jitter produce −60 mV minimum signed sample at a 0.5 UI center,
but +194 mV at a selected 0.8 UI center (100 mV diagnostic threshold). Increasing
the driver time constant to 200 ps leaves only +31 mV even after this bounded
phase adjustment. These are all-history two-pole channel calculations with
sampled timing windows, not PCIe compliance or demonstrated CDR acquisition.
The existing causal four-observation receiver now runs against these physical-time
channels at ±0.35 UI initial phase and ±100 ppm frequency error. The 100 ps cases
have zero held-out errors and continuous timing qualification; the 200 ps cases
have zero short-sequence errors but only 9–20% qualification and finish unqualified.
The screen now also moves actual analog sampling times and injects a voltage
disturbance/offset. At 100 ps, 10 ps RMS sinusoidal aperture jitter plus 10 mV RMS
voltage tone and 20 mV offset leaves ≥261 mV observed margin, but qualification
falls to 89% in some cases. Reducing aperture jitter to 2 ps restores continuous
qualification; 1 pF/50 ps also retains qualification at 10 ps. These conditional
mitigations need physical clock/driver costs. Stochastic tails, broader spectra,
protocol patterns and joint resource closure remain unresolved.

The [power allocation](power-partition.md#wired-mitigation-requirements-before-circuit-sizing)
now prices wired mitigations as inverse constraints: at 24 mA other clock current,
the PLL allocation permits 2.91 pF equivalent 3.3 V/2.5 GHz clock loading. Faster
driver gm/current remains conditional on internal capacitance and topology.
Termination-source current is charged to returns where appropriate, without
counting pad charging twice. This is not a complete power or area estimate.

The remaining TX DAC image now has a measured configuration tradeoff: narrowing
the assigned first-order cutoff from 10 to 5 MHz reduces its diagnostic ratio
from about 0.36% to 0.13%, but average output drops about 28% and 9 MHz analog
attenuation grows from 2.6 to 6.3 dB. Cutoff tuning alone therefore does not close
wideband signal quality or emissions; gain restoration cannot undo the droop.

The TX attribution comparison identifies repeated host samples as the dominant
cause of the earlier 7.5–7.8% adjacent-band ratio. Existing FPGA FIR interpolation
reduces that diagnostic ratio to 0.004–0.007% without new analog circuitry; the
separate DAC-rate image remains about 0.36%. The joined TX spectral comparison
now uses FIR interpolation and charges its FPGA workload/delay. Assigned output
gain 4.5 fits the two tested crests at about 1.067 mW. Reconstruction filtering,
phase/supply modulation, total packet EVM and proper emission measurements remain
open. Neither this diagnostic nor receive-side results establish Wi-Fi compliance.

## Capability coverage audit

The consolidated report now classifies every contract protocol target and
summarizes external-clock RF evidence by recipe and impairment assumptions.
No major capability has a complete operating envelope yet. This audit covers
the consolidated report; earlier packet, pad and transport diagnostics elsewhere
in the repository retain their narrower scope.

Joined spectral/PDN evidence now covers diagnostic HE20 and actual LE 1M
packet reception. Bluetooth Classic, 802.15.4, LoRa and other BLE modes do not
inherit those results. Likewise, the generic
NRZ sweep does not qualify USB/TMDS pad behavior, protocol startup or host service.
An observed pass at one carrier or recipe is not an operating range.

In the moderate external-clock/FIR slice, BLE 2M has no diagnostic 10% EVM pass;
LoRa has only some passing configurations. Both still decode the short fixtures.
Removing assigned frontend noise, IID LO phase and aperture jitter while retaining
12-bit quantization leaves BLE 2M at 8.8–10.2% and wideband LoRa at about 9.7–10.0%
EVM under preserve-tier settings. These controls point to deterministic recipe,
filter or acquisition limits before invoking more demanding silicon performance.
They are not proven noise floors, and 10% EVM is not a BLE/LoRa specification.

The configuration attribution now shows a BLE 2M clean-channel option: doubling
RX cutoff lowers diagnostic EVM to 5.8–6.3% at unchanged sample rate. But its
4 MHz blocker rejection falls sharply, and an equal-power blocker causes failed
acquisition and symbol errors. LoRa does not improve consistently with wider
filters; doubling converter rate worsens several cases.

The LoRa attribution now identifies prefix carrier-estimation error as a major
narrowband limitation. A 2,048-sample diagnostic prefix reduces narrowband EVM to
7.5–8.5% across tested seeds/carriers/offsets without analog changes. At the original cutoff the wider
recipe remains at 10.2–12.3%. Combining the long prefix with doubled RX cutoff
reduces it to 6.3–7.5%, including a sqrt(2) frontend-noise increase. But an
equal-power 1.6 MHz blocker causes acquisition failure and symbol errors, so
this is a clean-channel option. This costs training airtime and external FPGA work;
the synthetic prefix is not a standard LoRa preamble.

**Remaining waveform-specific gap:** map the synthetic-prefix recovery to actual allowed
preamble/tracking information and qualify the clean-channel/selectivity choices
with waveform-specific quality and blocker requirements. Then join them with
physical clock/filter/noise and resource budgets. Do not
extend HE20-only evidence by counting generic waveform passes. Whole-chip fit,
complete TX/RX operation and first-silicon fault isolation remain open.

The RF bench procedure now pairs longer-training, filter and blocker changes
using only known-stimulus residuals, carrier estimates and acquisition status.
It excludes injected frequency truth and simulator clipping counters. These
responses support controlled bench investigation, but do not uniquely distinguish
oscillator, filter, compression or reciprocal-mixing faults. Independent RF
stimulus and verified host capture remain dependencies; observability is partial.

The joined RF/clock/host allocation screen now includes the 37 mA TX RF
reservation and the host's internal transition charge without charging the TX
driver twice. The 24 mA/3 pF clock hypothesis passes at 2.4 GHz but exceeds the
PLL allocation at 2.437/2.484 GHz. The 12 mA/1.5 pF hypothesis fits the assigned
rail ceilings, drawing about 0.54 W at alternating host activity. This is not
thermal qualification or joint signal-quality closure at those exact rails.
The selected spectral RX comparison now uses those exact RF DC rails at
2.437 GHz: the clean-clock/1 mV-ripple case remains near 8.54% diagnostic EVM,
while noisy-clock and 10 mV-ripple cases fail. Ripple is still assigned rather
than generated by that current ledger. Actual current, area, inactive loads,
supply-dependent device behavior and physical host timing remain open.

The host-charge coupling screen now includes internal output-transition charge
in the 1 MHz activity tone. The selected network produces 1.24 mV clock ripple;
doubling board capacitance barely changes it, while lower assumed ESR reduces
it to 0.72 mV and improves diagnostic RX EVM from 9.4% to 7.7%. Its shared-feed
DC clock rail is only 3.108 V. Clock startup/noise/tuning at that operating point
is unverified, and a roughly 5.4 ohm high-frequency network peak remains. This
is a bounded coupling example, not complete dynamic coexistence closure.
A lower shared-feed resistance, with branch damping retained, raises that clock
rail to 3.243 V. Nominal and adverse capacitor cases give 7.6% and 8.6% diagnostic
RX EVM, respectively. The network's higher-frequency peak rises slightly; source
impedance and broadband host-current evidence remain open.

## Active milestone: several credible ways to succeed

The next deliverable is one coherent mathematical architecture with quantified
operating envelopes, costed mitigation/bypass paths, joint die/pin/power/FPGA
budgets, and first-silicon fault observability. It remains **incomplete**; no
new schematic work starts from isolated waveform passes.

The [robustness report](../evidence/robustness-envelope.json) now compares the
existing RF waveform families under three simultaneous impairment assumptions,
reference sampling and direct-LO integer division, with/without an explicitly
costed FPGA resampler. Its [clock integration assessment](clock-feasibility-envelope.md#direct-lo-mitigation-in-the-fast-waveform-model)
records the wideband rescue and desired failures. The raw variable-rate OFDM
path fails; resampling rescues the 8-ENOB comparison but not the adverse
6-ENOB/noise case. Narrowband/acquisition failures remain visible. The fixed
10% criterion is diagnostic, not a universal protocol requirement.

A joined receive-waveform comparison now injects source spectra before the
filter, including reciprocal mixing of a blocker, common clock supply modulation
and correlated direct-LO ADC timing. With assigned board filtering and 1 mV
residual ripple, clean-external and wider-loop autonomous scenarios give
7.02–7.14% and 5.77–5.88% diagnostic EVM across three spectral seeds. The noisy
source, narrow loop, unfiltered blocker and 10 mV ripple comparisons fail.
These are conditional combinations; actual source/PLL/PDN behavior is unproven.

One host-to-clock PDN path is now joined: board/package RLC and host activity
predict ripple, which drives the spectral receive model. A 1 uF board capacitor
rescues the 10 MHz/V scenario; 65 MHz/V needs the tested 10 uF alternative.
Series damping reduces a predicted high-frequency resonance but costs rail
headroom. Shared return/substrate, real switching spectra and full rail loading
remain open; the source and component values are assumptions.

A joined three-node supply/return screen now shows that shared return can
invalidate the capacitor rescue: the external-LO stress case rises from 7.74%
to 12.20% EVM with an assigned 0.1 ohm / 2 nH shared return. A lower-impedance
return hypothesis restores 8.36%; achieving it with existing pins is unproven.
Ground-to-signal/reference coupling and substrate effects remain excluded.
Differential rail observation alone cannot distinguish feed and return causes.

Explicit filter-loss/PGA-headroom modeling now removes the assumed free gain
restoration. Existing gain 0.5 preserves the tested external/autonomous waveform
at a 0.35 V component limit (8.62%/6.98% EVM), whereas restoring 2 dB clips before
the ADC and fails. ADC clipping flags remain zero in that failure, exposing an
observability gap. PGA bias/bandwidth, noisy headroom and stage-isolation routes
remain unclosed; this is not a complete power estimate or AGC implementation.

An initial diagnostic intervention screen now uses only digitized EVM/RMS and
acquisition, with existing PGA settings and stopped external-source replacement.
It separates the tested clock/headroom/pre-gain/post-gain noise classes but
correctly leaves equivalent sampler versus converter-core noise ambiguous.
This is bounded identifiability evidence, not an implemented or statistically
qualified first-silicon diagnosis system; mixed faults and stage isolation remain
open.

Next priorities: close ground-to-signal/reference and victim-switching effects,
extra RF gain/reference/headroom costs and diagnostic observability; separate
remaining acquisition/resampling artifacts from analog limitations;
test gain and calibration costs with realistic headroom; close finite host
pacing and its clock owner; extend envelopes to wired electrical modes. Area/current and diagnostic
observability still require a coherent implementation ledger. The current report
explicitly does not prove whole-chip fit or completion.

## GF180 evidence and interpretation

Missing RF characterization is **uncertainty, not impossibility**. None of the
reviewed evidence establishes a process-wide prohibition on the target clocks,
RF chain or coexistence. A failing topology or an optimistic model assumption
must not be promoted to a GF180 physical limit.

| Evidence class | What is actually known | Design consequence |
| --- | --- | --- |
| Published process data | The 3.3 V MOS model table includes measured extraction geometries down to 0.28 µm length; other table entries are identified as pseudo devices. | Use the actual device models and supported geometry, not a generic “180 nm” speed estimate. The table does not specify RF gain or maximum circuit frequency. |
| Published noise characterization | BSIM flicker-noise fitting used median die data over 10 Hz–100 kHz and specified biases/geometries. | This is useful input for noise analysis. It neither validates this oscillator's phase-noise spectrum nor says RF operation is impossible. |
| Published passive data | MIM options are 1, 1.5 and 2 fF/µm², with electrical limits; only one option is allowed in a process flow. | At 2 fF/µm², ideal 1 nF plate area is 0.5 mm². Filter/decoupling area can be budgeted; option selection, overhead and ESR/ESL still matter. |
| Our historical PDK circuit simulations | One nominal loaded candidate oscillates around 2.5 GHz; its four-point tuning sweep changes slope sign. | Positive simulated speed evidence and a circuit-specific control problem coexist. Isolate loading or select a monotonic coarse/fine branch; do not label GF180 incapable. Seeded/prebiased 41 ns runs do not prove cold startup or low jitter. |
| Our model assumptions | 10 MHz/V supply sensitivity, 10 dB NF, 46.86 dB conversion voltage gain and chosen driver limits are scenario inputs. | Ground each in a circuit/reference plane and sweep uncertainty. They are neither foundry guarantees nor process limits. |
| Exploratory package scenarios | The 1 pF pad and 1–5 nH inductance examples are assumed component values. | Their reactance shows potential significance, not actual loss or unavoidable failure. Evaluate the complete matching/protection/return network. |

Primary sources: [MOS extraction geometries](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_2_2.html),
[noise measurement conditions](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_2_3.html),
[MIM electrical specifications](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_6_4.html).
Historical circuit evidence: `vco-capture-tuning.json`, `vco-supply-screen.json`.

The 65 MHz/V historical slope is not a lower bound on achievable supply
rejection. Buffering, bias topology, regulation and coarse/fine tuning are
engineering options to evaluate, not assumed cures. Likewise, 20% thermal-only
EVM in one weak-signal, 20 MHz-bandwidth scenario rules out stricter EVM there,
not every modulation, narrower bandwidth or RF operation. Narrow accepted
voltage/temperature helps operating-point selection but does not erase noise,
loading, mismatch or process uncertainty.

Reserve “impossible” for a demonstrated contradiction with a stated requirement
and fixed constraints. Otherwise label a result circuit-specific failure,
conditional feasibility, or unresolved characterization. No missing foundry
RF/package dataset is treated as an acquisition prerequisite; work with the
open PDK, published data and explicit uncertainty, then eventual prototype data.

## Adopted assumptions and uncertainty ranges

The reference-AFE investigation is **paused at a useful evidence boundary**.
Its [measurement audit](../verification/reference_afe/README.md#measurement-validation-status-and-next-work)
and retained circuit reports remain available; reproducing its unexplained
spectrum is no longer the active transceiver task. Resume only for new measured
information or a specific architecture decision that the experiment can resolve.

The ranges below are conditional engineering scenarios, **not confidence intervals,
foundry guarantees or process-wide bounds**. Do not automatically assign a reference
circuit's component values to a different transceiver topology. Unknown means
unknown; no finite physical uncertainty interval has been established for those entries.

| Quantity | Evidence / range to retain | Adopted modeling consequence |
| --- | --- | --- |
| Proven AFE performance | Measured amplifier 92 dB gain / 12.5 MHz bandwidth; ADC >30 MS/s functional, 4.27 ENOB and 41 dB SNR at 20 MS/s. These are separate observations with incomplete conditions. | Anchor achievable low-frequency analog operation. Do not promise precision at maximum rate or use this as GHz qualification. |
| Sampling capacitance | Reference overlap-only array 0.569–0.797 pF, nominal 0.666 pF; 1.5–3 pF were assigned loading stress cases. Fringe, coupling and real dynamic load are not bounded by that density interval. | Keep explicit acquisition R, C and time. Select transceiver component sizes separately; include loading beyond plate area. |
| Reference charge | Conditional nominal large/small switch overhead approximately 0.424/0.106 pC at 1.7 V reference span; large-switch extra charge approximately 0.250–0.513 pC across 0.5–2.3 V spans. | Model signed high/low reservoir charge, gate/body exchange, reset and persistence. Do not scale all demand by binary capacitor weight or fit it as grounded capacitance. |
| Reference delivery | Existing 10–1000 pF reservoir and 1–10 kΩ source cases are assigned stresses, not inferred silicon impedances. | Determine required source/sink current and impedance from the actual switching schedule. External decoupling does not bypass local package impedance. |
| Comparator/preamp interaction | Reference static gain falls 29–49% across 1.65 to 0.735 V input common mode at the tested biases. Nominal ±1 mV decisions succeed; noise/mismatch statistics remain unidentified. | Include common-mode trajectory and late-decision gain in converter budgets. Do not apply the percentage universally or treat successful decisions as ENOB. |
| ADC distortion and noise | Optional harmonic-compatible transfer ensemble; at HE20 axis peak 0.6, unquantized gain-corrected differences 0.28–2.31%. Separate 41 dB-SNR normalization scenarios predict 0.38–3.82% noise/signal RMS. | Preserve input normalization, noise bandwidth and nonlinear shape as independent assumptions. These examples are neither exhaustive bounds nor measured RF EVM; do not combine table noise and figure harmonics as one calibrated converter. |
| Analog pad capacitance | Public diode-model scenarios approximately 0.79–1.07 pF before routing/package; not measured RF S-parameters. | Include voltage-dependent protection plus routing and assembly networks. A zero Liberty capacitance is not an analog model. |
| Shared analog switch | Reference output switch approximately 199 Ω at one nominal operating point; no general resistance range established. | Budget switch R and node C together using the selected transceiver topology; this reference value is a sensitivity example only. |
| Clock quality and device speed | No measured GHz fT/fmax, oscillator phase-noise mask or aperture-jitter calibration recovered. Historical candidate supply pushing around 65 MHz/V versus model assumption 10 MHz/V; neither bounds achievable rejection. | Retain both as sensitivity anchors, seek the permissible pushing/noise boundary, and compare autonomous versus supported external LO/clock operation. Do not substitute clean reference frequency for low output phase noise. |
| Complete RF chain | Receiver NF 6–15 dB and converter 6–9 ENOB at 20–40 MS/s are design scenarios, not measured GF180 ranges. Reference ADC's 4.27 ENOB is a cautionary result, not a process ceiling. | Sweep noise, gain, linearity and headroom jointly at declared signal levels; expose how much improvement each intended configuration requires. |
| Assembly and coexistence | 1–5 nH assembly examples are exploratory; actual package/substrate transfer and resonances remain unidentified. | Sweep complete return/matching/PDN networks, retaining active host switching in either RF or wired mode. External support and RF/wired exclusivity do not remove this coupling. |

Detailed provenance and limitations belong in the
[reference analysis](../verification/reference_afe/README.md), not repeated experiment
histories here. The amplifier mismatch has not yielded a transferable gm, ro or
capacitance correction. No transceiver default is silently promoted to a measured value.

## Deduced feasibility ranges — 2026-09-26

These are **conditional estimates**, not measured GF180 RF specifications,
statistical confidence intervals, or limits on every possible design. They
supplement the adopted scenarios above; they do not silently change executable
model defaults or select a clock architecture. Favorable endpoints cannot all
be assumed simultaneously. Failure to start, severe distortion and inadequate
isolation remain possible outside these working envelopes.

### Device speed: a useful order-of-magnitude deduction

The [3.3 V device specification](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_1.html)
gives NMOS Idsat = 0.43–0.59 mA/µm and Vt = 0.53–0.73 V for
10/0.28 µm devices at VGS=VDS=3.3 V. The
[oxide specification](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_5_3.html)
gives Cox = 3.4–5.4 fF/µm².

A deliberately rough alpha-power law, Id ∝ (VGS−Vt)^alpha with **assumed**
alpha=1–2, gives gm/W ≈ 0.155–0.459 mS/µm at that bias. Saturation channel
gate capacitance (2/3)Cox L is 0.635–1.008 fF/µm. Adding **assumed**
0.3–0.8 fF/µm for overlap/fringe gives 0.935–1.808 fF/µm. Thus
fT ≈ gm/[2π(Cgs+Cgd)] gives **14–78 GHz**, rounded to **10–80 GHz as a
working intrinsic-NMOS speed hypothesis**. These independently combined extrema
are not foundry corners. Alpha-law slope, actual RF bias, resistance, non-quasi-
static effects and capacitance partitioning can invalidate the approximation.
This is not a measured fT interval and not a loaded circuit clock range.

At 2.4 GHz that would correspond to first-order current-gain magnitude fT/f
of roughly 4–33, enough to keep RF work plausible. It does not prove power gain,
noise figure, full-swing logic speed, or 4.8 GHz quadrature generation. Do not
assign a numerical fmax from these data: gate/substrate resistance, feedback
capacitance and output conductance are not identified by Idsat and Cox.
Width increases current and capacitance together; it is not a free speed gain.

### Clock noise: topology-dependent, not a process constant

For an **unselected LC-oscillator candidate**, use the explicit Leeson screening
model L(f)=F kT/(2 Ps) · [1+(f0/(2 Q f))²] · (1+fc/f), linear SSB noise.
Here f0=2.4 GHz, T=300 K, Ps is effective tank signal power (not DC supply
power), Q is loaded tank Q, F is effective oscillator noise factor, and fc is
an assumed upconverted flicker corner. All four circuit inputs below are
hypotheses, not recovered GF180 measurements. Package and external components
must be included in loaded Q if an external resonator is considered.

| Conditional case | Q / Ps / F / fc | L(1 MHz), dBc/Hz | Free-running equivalent RMS jitter, 10 kHz–10 MHz |
| --- | --- | --- | --- |
| Favorable tank | 10 / 2 mW / 3 / 100 kHz | −133.1 | 0.49 ps |
| Intermediate tank | 5 / 1 mW / 5 / 300 kHz | −121.1 | 2.90 ps |
| Adverse tank | 3 / 0.2 mW / 10 / 1 MHz | −104.8 | 27.3 ps |

Jitter is sqrt(2∫L(f)df)/(2πf0), integrated over the stated limits. These are
analytic screens, not RF simulator results. A PLL changes the spectrum; ring
oscillators require a different model. No number in this table predicts the
retained oscillator's actual noise. Nevertheless the ~0.5–30 ps spread shows
why “oscillates at GHz” is insufficient against the existing ~1 ps allocation.
Supply spurs, reference/divider/charge-pump noise and distribution are additional.

Use **10–100 MHz/V** as a supply-pushing stress interval around our existing
10 MHz/V assumption and historical ~65 MHz/V circuit result, not as physical
limits. With sinusoidal 1 mV-peak ripple at 100 kHz, an uncorrected oscillator
has σt=Kv·Vripple/[sqrt(2)·2π·f0·fripple] = **4.7–46.9 ps RMS**.
Loop rejection and supply filtering can change this substantially. Narrow
operating temperature/supply tolerances do not remove AC ripple.

A clock receiver with assumed 0.1–2 mV RMS threshold-referred noise and
1–10 V/ns crossing slew has **0.01–2 ps** noise-induced timing error, σt=σv/slew.
This conditional local-buffer estimate excludes source noise, slow slew,
correlated supply modulation and duty-cycle/quadrature errors. External LO is
therefore a useful option, not automatic clock-budget closure.

### RF chain and converters

Use Friis with matched available-power gains at a common reference temperature:
Ftotal=Linput·[Flna+(Fdownstream−1)/Glna]. Three assumed tuples
(input loss, LNA NF, LNA gain, downstream equivalent NF), all in dB, are:
(1,3,15,10), (2,5,12,15), (3,8,8,20). They give complete analog-front-end
NF **4.58, 9.07 and 16.42 dB**, respectively. Adopt **5–17 dB as the broader
exploratory receiver envelope**, retaining the existing 6–15 dB default sweep
as its central subset. This is circuit-level inference, not measured GF180 NF.
Mixer noise must use a consistent SSB/DSB convention; converter noise needs
separate gain/full-scale accounting. Published other-process LNA precedents
in the survey support scale only, not GF180 transferability.

The packet candidate's 6 dB NF is **after** the external filter; at the assigned
300.15 K physical/reference temperature, 2 dB matched passive insertion loss
makes the antenna-referred NF **8 dB**. The baseline's 10 dB similarly means
12 dB at the antenna. Keep these planes distinct from the broader complete-AFE
NF envelope above. The model adds equivalent noise at the chip input and
attenuates the external signal; this already accounts for the loss in total
antenna SNR, so do not add the same passive noise a second time.

For a chip-input target of 6 dB, the inverse two-stage requirement is
`Fdownstream <= 1 + Gearly * (10^(6/10) - Fearly)`. Illustrative combinations:

| Early-stage NF | Early available-power gain | Maximum downstream equivalent NF |
|---|---:|---:|
| 3 dB | 10 dB | 13.19 dB |
| 3 dB | 15 dB | 18.05 dB |
| 5 dB | 10 dB | 9.63 dB |
| 5 dB | 15 dB | 14.30 dB |
| 6 dB | 20 dB | 0 dB: no added-noise allowance |

These are requirement allocations, not demonstrated circuits. The packet
fixture's 20 dB early **voltage** gain is not automatically 20 dB available-power
gain; establish impedances and conversion/noise conventions before applying
this table to a mixer or LNA. Include later analog/filter noise in the
input-referred total and keep converter quantization/noise explicitly separate.
A lower-NF first stage and more early gain are different options with different
current, headroom and blocker-compression costs. More gain before the channel
filter exposes those stages to the full blocker and cannot be credited for free.

A useful independent check is the assigned fifth-order complex low-pass noise
bandwidth: `B_RF = 2*fc*pi/(10*sin(pi/10))`. Both baseband sidebands contribute.
At 500 kHz cutoff this is 1.017 MHz; at 700 kHz it is 1.423 MHz. With 8 dB
antenna-referred NF and 300.15 K, the input-referred integrated noise is
−105.75 / −104.29 dBm respectively, giving only 15.75 / 14.29 dB thermal SNR
for a −90 dBm wanted signal before other errors. Narrowing the filter improves
thermal SNR by 1.46 dB and adjacent-tone rejection much more strongly, but also
changes signal distortion/delay. These noise-only numbers are not packet-error
predictions and do not override the observed acquisition/CRC failures.

**Budget decision:** the promising packet setting requires a complete 6 dB
chip-input analog NF at its gain setting, not merely a 6 dB LNA. Keep its
current/area cost unclosed until a staged noise/gain/headroom allocation fits
the shared RF reservation. Do not fund it implicitly by assuming the TX driver
or other inactive circuitry has zero current during reception.

For linearity, use **−20 to 0 dBm input IIP3 as an assigned exploratory
range**, not a deduced process limit. The packet receiver now includes an
optional input-referred memoryless cubic *before* channel filtering. For
complex RF peak envelope z, `y = z*(1-|z|²/(2*R*PIIP3))`. An independent
two-tone test verifies the extrapolated relation `PIM3 = 3*Pblocker - 2*IIP3`
and its slope, using matched 50 Ω power conventions. The model flags peak cubic
gain reduction above 10% as outside its assigned small-compression validity
range; it is not a large-signal saturation or device-noise model.

The joined stress fixture uses −80 dBm wanted and two blockers of **−30 dBm
each** at +2/+4 MHz, all before 2 dB external loss. Thus the blockers reach the
chip at −32 dBm each (−29 dBm combined), and their IM3 lands at the wanted
carrier. Retain 6 dB NF, 500 kHz five-stage filter, 8 ENOB and the 500 pF
nonideal supply candidate. This comparison uses the delivered-clock hypothesis
to isolate linearity; it does not hide or close the separate loaded-input failure.

| Input-referred IIP3 | Accepted requests | Peak cubic gain reduction | Interpretation |
|---|---:|---:|---|
| Ideal-linear control | 3/3 | 0 | No front-end nonlinearity |
| −20 dBm | 0/3 | 25.3% | Outside polynomial validity; no qualified circuit verdict |
| −10 dBm | 0/3 | 2.53% | In-band distortion defeats this modeled receiver despite small compression |
| 0 dBm | 3/3 | 0.253% | Conditional candidate, not a PER or physical qualification |

The −10 dBm case predicts −76 dBm input-equivalent IM3, above the −82 dBm
wanted chip-input signal; 0 dBm predicts −96 dBm. Later channel filtering cannot
remove an intermodulation product already generated in the wanted band. This
is an engineering two-tone stress, not a claim that every targeted standard
requires this exact test. Early LNA/mixer gain, bias and bypass need a joint
noise/linearity/headroom allocation. Constant NF, gain and current while changing
IIP3 are deliberately unpriced hypotheses, not evidence that 6 dB NF and 0 dBm
IIP3 coexist in the present RF reservation. Retain pre-mixer filtering as a
possible mitigation only where its actual offset rejection is realizable.

The [measured GF180 AFE](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957346)
reports 4.27 ENOB at 20 MS/s and separately >30 MS/s functionality. A useful
first-implementation sweep is **4–8 ENOB at 20–40 MS/s**, with **6–8 ENOB the
engineering target and 9 ENOB a stretch**, not a measured achievable range.
Eight ENOB requires ~22.5 dB SNDR improvement over that 4.27-ENOB observation;
that improvement is not demonstrated by correcting just one suspected error.

Sampling thermal noise alone does not rule it out: two independent sampling
capacitors of 0.5–2 pF per leg at 300 K give sqrt(2kT/C)=129–64 µV differential
RMS. For a 1 Vpp differential full-scale sine this is a **thermal-noise-only
11.1–12.1 equivalent-bit ceiling**. Comparator/reference noise, distortion,
settling, quantization and mismatch reduce performance. At 40 MS/s the complete
conversion gets 25 ns; ten serial decisions would average only 2.5 ns each
before allowing acquisition and control. Faster multi-stage/interleaved
architectures trade this problem for area, power and calibration.

For TX, a 50-ohm load with assumed 0.5–1 V peak sinusoidal voltage receives
**+4 to +10 dBm CW** and requires 10–20 mA peak. With 6–10 dB signal PAPR,
the same peak constraint permits roughly **−3 to +7 dBm average modulated
power** (Pavg=Vpeak²/[R·PAPRlinear]). These are load-line ceilings, not
linear-output promises; output impedance, compression backoff, matching loss,
pad rating and the retained driver's small current margin all reduce them.
An external PA may remain necessary for useful higher-power radio operation.

### Pads, assembly, coexistence and variation

The existing protection-model result (~0.79–1.07 pF before routing/package)
supports exploring **1–3 pF total port capacitance** for that protection class.
Retain **0.5–5 nH effective series/return inductance** as an assembly stress
range, not a measured package estimate. At 2.4 GHz these correspond to
22–66 ohms capacitive and 7.5–75 ohms inductive reactance; undamped LC
resonances span approximately **1.3–7.1 GHz**. The actual distributed return
and matching topology decides loss and ringing. One shunt C in a matched
50-ohm through path gives |S21|=2/sqrt(4+(ωCZ0)²), or ~0.58–3.58 dB loss
at 2.4 GHz for 1–3 pF before deliberate matching. RF matching can help one
band; wired broadband edges need a different configuration.

Substrate isolation cannot be inferred from those scalar parasitics. For scale,
a −80 dBm wanted signal is 22.4 µV RMS into 50 ohms. Holding a direct in-band
spur below 10% of that amplitude, with a 0.1–1 V RMS aggressor spectral
component, requires about **93–113 dB voltage isolation** along that path.
This is a required transfer limit, not a claim that the layout provides it;
actual aggressor spectra, frequency translation, differential rejection and
filtering must be modeled. RF/wired exclusivity still leaves the FPGA active.

The published NMOS drive range is about ±16% around typical and threshold
±100 mV. These are specification extrema at stated conditions, not sigma,
local pair mismatch, or an oscillator tuning distribution. Keep published
corner/mismatch models for what they cover; neither these numbers nor the AFE
measurements identify RF noise spread. Startup/tuning yield therefore remains
an explicit failure branch, even with narrow accepted temperature and voltage.

**Consequence:** continue treating 2.4 GHz RF and 1.25–2.5 Gb/s wired operation
as credible research targets, not proven capabilities. The key threat is the
joint noise/linearity/clock/isolation budget rather than an established raw-speed
contradiction. First evaluate the complete chain over the ranges above with
coupled power/loading assumptions. This analysis does not select autonomous
versus external timing and does not authorize starting a new schematic campaign.

## Work order and exit evidence

Generous external SMD passive networks are allowed by the
[design boundary](../../../docs/roadmap/programmable-transceiver-pin-plan.md#external-passive-component-allowance).
Compare external matching/filtering/decoupling and feasible timing networks
before treating on-chip passive area or an unfiltered rail as fixed constraints.
Any additional analog access must fit the selected provider-compatible site
allocation without displacing required functions or fixed supply/return sites.

Analog feasibility is the active priority. Digital bridge work is retained but
paused except where its load or timing constrains an analog result. Finish the
mathematical architecture before new schematic/layout work.

1. **Clock feasibility, autonomous and externally assisted.** Use the
   [clock feasibility envelope](clock-feasibility-envelope.md) and its executable
   budgets as the current comparison. Spectral/loop-transfer closure remains open.
   First compare the
   existing loaded oscillator/supply results against the
   [RF phase-error budgets](feasibility-gates.md) (“First numerical constraint”).
   The retained [supply-ripple diagnostic](../evidence/rf-supply-ripple-screen.json)
   reports about 11.07 ps peak at the single-ended LO versus 0.419 ps at the
   differential node for 10 mV peak / 100 MHz ripple. Its later audit identifies
   an underbiased RF load; neither number qualifies the correctly biased chain
   or isolates intrinsic oscillator phase noise. Keep that operating-point
   correction and conversion-to-single-ended sensitivity in the model boundary.
   Fix the intended LO/quadrature/divider and clock-ingress paths, loads and terminal
   allocation. Report permissible integrated phase noise, deterministic spurs,
   supply pushing and distribution error separately; identify the first failure
   boundary. A direct external LO may bypass the VCO only through a supported path;
   a clean PLL reference does not. Autonomous operation additionally needs a monotonic
   tuning branch, startup and acquisition over the accepted narrow operating range.
   Exit evidence: a connected clock budget for each retained architecture with
   explicit unresolved physical assumptions, not another ideal-clock pass.
2. **Complete RF conversion chain.** Carry the same clock assumptions through
   RX and TX, including external filter/matching losses, pad loading, LNA/mixer
   noise and compression, gain distribution, converter acquisition/reference
   behavior, and TX current/headroom. Find joint sensitivity/blocker/EVM boundaries
   rather than independently optimizing each stage. Selectable narrowband operation
   remains part of the envelope. Exit evidence: which generic configurations meet
   their declared signal-quality budgets, which fail, and the parameter improvements
   needed, within one non-overlapping power/area ledger. Current BPSK fixtures do
   not demonstrate higher modulation orders or standard packets.
3. **Physical coexistence.** Apply host/clock aggressors and shared rail/return
   impedances to those same RF and wired configurations. Budget protection,
   pad capacitance, package inductance, external decoupling and local charge storage
   together. Exit evidence: maximum tolerable coupling/PDN impedance and a plausible
   external network within the selected compatible site map and wafer.space slot.
   RF/wired exclusivity removes their simultaneous payload activity, not host noise.

Keep wired CDR/electrical feasibility in the same clock and pad budget; external
TX timing cannot recover an independently timed incoming stream. Resume digital
work only when it constrains these analog budgets. No new transceiver schematic
or layout work precedes mathematical architecture closure.

The [process specifications and performance estimates](open-high-speed-design-survey.md#process-specifications-and-performance-estimates)
now identify published GF180 bias/current data, same-process evidence gaps and
measured other-process LNA/ADC precedents. Initial sweeps use 6–15 dB complete
receiver NF and 6–9 converter ENOB at 20–40 MS/s as engineering scenarios, not
promised GF180 ranges. Two explicit receiver cascades give about 10.1/11.1 dB
NF under their declared downstream loss/noise assumptions.

## Effect of the newly allowed board support

| Risk | External support can change | What remains on the chip |
| --- | --- | --- |
| Oscillator startup/tuning/noise | Direct external LO/clock injection may bypass the oscillator; a reference-only input still uses synthesis | Input receiver, switching, division/quadrature, distribution and any remaining PLL/CDR |
| RF selectivity and matching | SMD LC/filter/balun networks can reduce blockers and transform impedances | LNA/mixer noise and linearity, converter dynamic range, driver current/swing; external loss must be included |
| Large passive area / supply filtering | External capacitors and RC/LC networks can move much of this burden off die | Local charge storage and high-frequency return paths behind pad/package inductance |
| Wired timing and equalization | External references, coupling and termination can assist | Independent incoming data still needs CDR/sampling and electrical receive/transmit performance |

The published standard `gf180mcu_fd_io__asig_5p0` has double-diode protection
and a **10 mA DC** current rating; supply cells list 60 mA DC. This is useful
pad-specific information, not a universal process-current limit. Do not compare
10 mA DC directly to the retained 26.31 mA RF waveform peak and declare failure;
check topology, DC/RMS/peak currents, reliability rules and the chosen protection
path. Do not assume the standard pad is a qualified GHz clock input either.
[GF180 I/O cell list](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html).

External support changes the implementation opportunity, not the evidence status:
no full external-LO conversion-chain demonstration is claimed. Positive process
and circuit evidence supports continued design investigation; unavailable RF or
package characterization stays an uncertainty, not an impossibility verdict.

The fast [analytic bounds](../evidence/feasibility-bounds.json) now expose the
following specific risks:

| Finding | Implication |
| --- | --- |
| Historical VCO supply slope reaches 64.78 MHz/V; coupled RF default is 10 MHz/V | The default is about 6.48× less sensitive. This historical DC slope is not a validated RF transfer function, but warrants an adverse scenario. |
| Loaded tuning secants change sign | Cannot assume one positive-gain PLL over that control range. Coarse branch selection and loading matter. |
| RX at 20 MHz bandwidth, 10 dB NF: thermal-only EVM ≈2.0% at −56.86 dBm, ≈20.1% at −76.86 dBm | Gain cannot recover lost input SNR. The retained stronger-signal pass does not establish sensitivity. |
| Retained TX fixture has only 1.69 mA peak-current and 0.201 V differential-headroom margin | Supply, load and crest-factor variation can consume the margin; no robust driver envelope yet. |
| At 2.437 GHz, 1 pF has 65.3 Ω reactance | Pad/protection loading is comparable to the assumed 50 Ω port; a purely resistive load is incomplete. |

A new pulse-loop susceptibility screen adds prescribed frequency tones to the
existing noise realization. A 10 mV-peak, 5 MHz ripple equivalent at 65 MHz/V
raises affine-detrended phase RMS from 0.0571 to 0.1377 rad in the sampled
unloaded-clock case. This is neither closed-chain EVM nor calibrated silicon
noise. Exact settings/results live in the closure inventory's `analog_risk_audit`.

The public PDK describes flicker-noise fitting from median measurements over
10 Hz–100 kHz. That supports device-noise modeling, but does not by itself
validate oscillator phase noise, broadband RF noise or this package.
[GF180 noise measurement conditions](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_2_3.html).

## Failures and limits that must remain visible

- Unframed wired rearm can recover timing while losing word alignment. External
  diagnostic markers demonstrate a possible framing service, not PCIe/SATA/PCS
  recovery. The former source-indexed CDR could use future transitions outside
  its nominal phase envelope; its historical numbers are not fresh evidence for
  the replacement detector.
- Raw playback pacing now follows the FPGA clock instead of ideal chip time.
  Independent-clock continuous traffic still needs rate tracking or feedback;
  finite-buffer and finite-burst passes do not solve sustained drift.
- USB packet correctness does not imply a timely response. Slow host, insufficient
  FPGA throughput and additional processing delay produce deadline failures;
  ingress overflow suppresses ACK. Prior token/endpoint acceptance is assumed.
- A 20,000-edge acquisition window at 120 MHz cannot satisfy the retained count
  uncertainty/frequency tolerance. The corrected window preserves 500 µs per
  observation and two good windows. Previous fixed-guard RF passes do not prove
  startup; the gated results above supersede them for these specific cases.
- Earlier RF TX driver/current candidates fail OFDM crest requirements. The
  revised candidate passes finite screens only. Receiver anti-alias filtering
  does not suppress emitted interference or establish a transmit mask.
- RF noise-seed, input-level and clock/filter alternatives include failures.
  Equal RMS oscillator noise does not imply equal performance; spectrum and loop
  response matter. Do not transfer a result between sampled-loop and pulse-loop
  configurations or treat a BPSK quality limit as universal radio qualification.
- Narrow temperature/supply acceptance does not remove process variation,
  mismatch, parasitics, self-heating, supply ripple or uncertain RF models.
- RF/wired exclusivity permits sharing but does not eliminate simultaneous wired
  TX/RX, host switching or the complete conversion chain in its selected mode.

## Evidence rules and ownership

Use [the closure inventory](mathematical-closure.json), especially
`active_workflow.three_demonstrations`, for exact configurations, retained
measurements and negative controls. Historical entries are not automatically
revalidated after source changes. A passing regression can mean a failure was
correctly detected; test counts are not a completion percentage.

Every capability claim must identify its entry point, assumptions, acceptance
criteria, result and excluded coverage. Distinguish **conditional demonstration**,
**expected rejection**, **known failure**, **historical result**, and **not tested**.
The aggregate behavioral report does not include every focused demonstration.
Do not call the project verified because its assertions pass.

- [Model guide](../system_model/architecture_fast/README.md): commands and model boundaries.
- [Bridge/clock ownership](clock-rate-ownership.md), [transport](streaming-transport-v2.md), [wide datapath](parallel-datapath-candidate.md): implementation contracts.
- [Power partition](power-partition.md), [FPGA electrical screen](fpga-host-screen.md): physical budgets and evidence.
- [Pin plan](../../../docs/roadmap/programmable-transceiver-pin-plan.md): scope, terminals and physical envelope.

A wafer.space 1×1 slot is not 1 mm²: the provider lists 3.93 × 5.12 mm die and
12.92 mm² inside the default ring. The standard chip-on-board offer requires the
default ring; custom ring freedom does not qualify a custom package.
[Provider specifications](https://wafer.space/price.html), checked 2026-09-25.
