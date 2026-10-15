# Current transceiver status and priorities

## Shared-model integration work

The active milestone includes all five requested areas: clock-configuration
integration, cold CDR lifecycles, executable application recipes for all 17
targets, retained serial/USB/RF/video exchanges, and adverse controls that prove
acceptance rejects the intended faults. Completing clock fields alone does not
complete this milestone.

Stable RF host selection and fractional forwarded ×10 video synthesis resolve
through `ResolvedConfiguration`, including the video VCO/output divider.
The loaded differential reference now drives retained sampled-PLL detector
events through bounded edge windows, including fractional clocks. The old direct
clock adapter still rejects forwarded synthesis rather than mislabeling a pixel
clock as a serial clock. The low-frequency application source is 0.5 V peak;
1 V fails the unchanged input envelope. Three retained video clock/FIFO paths
now exercise streaming, reference loss, delayed host stop, explicit epoch/queue
recovery and relaunch, with underflow/overflow/stale-epoch controls. This is
opaque-symbol continuity under stationary input/package forcing, not video
encoding, connector-pad transient or arbitrary-board skew qualification.
A cold CDR trajectory starting from an independent nominal local clock now
qualifies at bit344686 and records34.70ppm peak held-out tracking error, zero
scored errors and no qualification losses. The observation queue peaks at80bits
of1024. This is one acquisition/traffic trajectory, not source-loss recovery.
Changed-SSC and stale-coefficient recovery, complete recipes and retained
serial/USB/RF exchanges still need implementation and verification. The full five-area milestone remains open.

## Open-issue register

This is the current issue inventory by design obligation, not a count of failing
unit tests. A test that correctly detects an unsupported operating point passes
the regression while preserving a design failure. Recorded numerical results
below keep their original scope; stale campaigns require execution again before
they qualify the current sources.

| Area | Unresolved issue and evidence status | What would close it |
|---|---|---|
| Wi-Fi gain feedback | The protected status now reuses argument bit7 to report up to127 invalid pairs without increasing frame size; command bit7 remains zero. Nominal200ns settling is admitted and actual45-pair loss is preserved, and the selected diagnostic packet now decodes with a shorter FPGA coarse-correlation window and unchanged paired LTF validation. Nominal200ns analog response is retained. | Verify broader gain range, false-detection and packet/blocker statistics with complete independent HE waveforms. Diagnostic packet success is not router interoperability. |
| RX filter realization | Selected paired allocation is now8mA, charged in both warm RF directions: external-clock RF240mA after the selected TX-filter increase. The sizing rerun has candidates below8mA including the separate resistor-drive reservation (minimum7.251mA). The area-constrained0.6mm2 plate candidate at0.9fF/um2 estimates7.560mA, leaving0.26mm2 for circuitry within the paired allocation. The unconstrained lowest-current candidate needs1.024mm2 of capacitor plates at0.9fF/um2, exceeding the paired0.86mm2 filter allocation before circuitry; at1.8fF/um2 plates consume0.512mm2. | Joint current/area/noise/drive feasibility with justified capacitor density, circuit overhead and blocker-dependent swing; current fit alone does not qualify a filter. |
| Wired clock recovery | Selected finite phase bank and optional FPGA-assisted periodic prediction reach 37.06 / 42.17 ppm peak error against the unchanged 50 ppm target in two 430k-bit acquired-state SSC/gap trajectories. Each has zero scored bit errors, zero qualification losses and full scored validity. Fixed-point framed transport and finite actuator resolution are included. | One nominal-local-clock cold trajectory also passes (34.70ppm, qualification at bit344686, bounded observation queue). Extend to independent starting offsets, the complete phase/jitter envelope, source loss, changed SSC and stale-coefficient recovery; actuator latency and physical resources remain open. |
| Package, clocks and supply | No qualified package impedance, pad/clamp envelope, CMRR or supply-to-delay law. The recorded sufficient input bounds fail for selected wired and high-inductance cases; failure of an enclosure is not proof of an actual excursion. The USB feed probe records about 23.9–24.8 mV against a 20 mV guard. External timing does not eliminate input/distribution noise. Autonomous phase noise, startup and tuning remain unqualified. | A common bounded supply/timing envelope with realistic host activity, traffic-dependent current feedback and admissible pad voltages. |
| Converter/reference | Selected timing is3ns acquisition,20ns conversion and2ns reset, retaining the0.2ns cycle guard and unchanged DAC settling intervals. The six-case512-sample tone/loading screen converges with positive precision margins; assigned100ps regeneration has2.09ns selected-load and2.28ns combined-stress conversion margin. The150ps stressed case has only1.2ps margin and is not a credible tolerance guarantee. Minimum stressed precision margin is0.016bits, so robust noise/precision remains open. The refreshed narrowband adverse request/reply also passes at100ps with1.68ns conversion margin,8dB NF,-3dBm IIP3 and doubled source/input phase amplitude. The refreshed whitened wideband adverse case also passes at100ps with1.68ns conversion margin and zero clipped samples. Broader corners, rare comparator decisions, mismatch and kickback still require qualification. Retune and fault continuation now use causal held-current package propagation instead of guarded FFT. The selected full-package22us retune and subsequent clock-loss continuation converge; continuation stabilizes in two iterations with0.87uV frozen-prefix change below1uV and1030 crossings on each of three grids. This is the fixed-duration SAR timing fixture, not asynchronous comparator qualification; previous35mV and /128 variants require separate reruns. | Stable coupled continuation and useful precision/timing margin across explicit uncertainty, followed later by circuit qualification. Numerical nonconvergence is a model issue, not silicon impossibility. |
| RF RX and acquisition | The stressed retained lifecycle with required RX gain regulation gives 6.76%, 6.17% and 6.66% RX EVM versus 9.08%, 9.54% and 9.62% with the previous unregulated gain law. These pass the 10% diagnostic screen but do not establish high-order modulation quality. Sampled weak-signal/blocker successes do not establish sensitivity/PER, overload recovery or a common usable gain range. Finite-zero filter history can outlast acquisition; downstream PGA changes cannot undo upstream saturation. The earlier wideband23dB crest came from unwhitened DATA padding, not training; the normal diagnostic now whitens DATA/padding and retains the unwhitened overload control. | Valid packet acquisition with gain, history, blockers, noise and converter behavior joined; retain independent adverse controls without calling every diagnostic failure a protocol failure. |
| RF TX | Selected five-pole reconstruction, causal FPGA correction and clock/driver rejection have a retained stressed-lifecycle point at native peak170 and gain6.2941: about+1.135dBm before board loss and2.55% scalar diagnostic EVM. The corrected waveform stays below the0.35V limit; a peak200 control fails it. Full-record relative-energy screening is not a standards mask. The Wi-Fi exchange and independent legacy runners now inherit selected correction and8ENOB instead of silently using an uncorrected filter or ideal10-bit DAC. Selected span40/14-bit FPGA interpolation and received-pilot frequency refinement give1.8–2.3% scalar EVM across the eight diagnostic MCS cases, below the existing−30dB target, with about1.8us minimum prefill margin. These are prescribed-impairment diagnostic results; complete HE emissions remain open. | Join corrected power, waveform peaks, spectral masks and physical pad/driver loading; complete HE packets and interpolation rejection remain open. Circuit cost and fabrication fit follow behavioral closure. |
| Protocol coverage | All 17 capability verdicts remain unresolved. Wi-Fi lacks complete independent HE references/router lifecycle and DSSS/CCK coverage. The selected independent legacy OFDM runner now decodes all eight rates, transmits their DATA and receives return ACKs; this is conditional PHY evidence with assigned analog fixtures, not interoperability. Other radios lack their own complete acquisition/hopping/emissions evidence; generic modulation is insufficient. Wired electrical/control lifecycles and sustained links are incomplete. | The per-target proofs in [capability-wide gaps](feasibility-gates.md#capability-wide-evidence-gaps-and-next-decisions), including both USB roles, PCIe detection/idle, SATA OOB, Ethernet negotiation, DP training, video lane recovery and SDI patterns. |
| Pad protection and coexistence | Disabled branches, backfeed, powered-off external drive, internal stress, brownout isolation and clamp/package coupling lack physical qualification. USB packet timing alone does not establish attach/chirp/disconnect or electrical turnaround; preceding wired lifecycle stages do not use the complete shared electrical lane. | One retained electrical pad lifecycle with bounded parasitics, supply/protection behavior and actual sampling/control timing. |
| Startup, turnaround and calibration | Cold supply/bias startup, physical readiness sensors/acquisition, measured correction deployment and serialized recovery latency remain incomplete. Assigned observations and ideal readiness cannot prove these services. | A complete retained startup → traffic → fault → recovery trajectory using the selected controls and bounded sensing/settling. |
| FPGA service and implementation fit | Actual GPIO timing, modem/decision compute, CDC/queues, direct-stream RTL and serialized command ABI are not completely integrated. Analog/digital area, decoupling, routing, thermal and assembly fit remain allocations. | A realizable host/service and physical budget for the selected wire-bond-compatible assembly; mathematical acceptance does not establish silicon fit. |
| Model consistency and evidence | The shared-design test migration is complete for the audited suite, with explicit independent and simplified/adverse fixtures. This establishes configuration binding, not correct physics or capability acceptance. Subsequent model edits invalidate older campaign fingerprints; unexercised optional runners and physical assumptions remain unqualified. | Rerun affected campaigns against current sources, audit stimulus and acceptance logic, and retain provenance without restamping old results. |

The immediate milestone is **behavioral capability closure**: complete CDR
acquisition/tracking, a common useful RF operating envelope, and protocol
startup/recovery through the generic controls. Improve required block behavior
when a valid acceptance case fails; do not relax the case or substitute a
passing simplified fixture. Power, area, GF180 implementation and assembly fit
remain recorded obligations for a later physical feasibility pass, not vetoes
on the required mathematical design. Nominal PGA admission, converter timing,
TX correction and RX gain regulation now have scoped evidence; complete
protocol and uncertainty coverage remain open. The detailed sections below
explain evidence and limits and do not supersede this register with older runs.

The four timing/control review findings now have selected definitions in
`analog-architecture.json:timing_review_closure`: stable-host warm hopping,
frequency/SSC-aware CDR, complete RF gain feedback and consistent USB direct
streaming. Component checks support those definitions; external source settling,
physical CDR/gain recovery and whole-chip model/RTL integration remain open.
See the [current architecture](block-diagram.md#warm-rf-hopping-and-gain-feedback).

The [normative architecture and diagram](block-diagram.md) own selected functional
boundaries. Numerical studies below are conditional evidence, not frozen circuit
topologies or qualified component specifications.

The mathematical architecture is **incomplete**. No new schematic or layout
work until the mathematical gates are met. Conditional simulation success is
not GF180, package, FPGA timing or protocol-compliance qualification.

A [simulation-design consistency audit](../system_model/architecture_fast/README.md#do-the-tests-use-the-same-design)
confirms that retained tests do **not** all instantiate the selected design.
Current integration, primitive tests, adverse controls and legacy studies must
remain distinct evidence roles. `check_contract.py` now inventories construction
paths and default-parameter drift alongside source freshness; neither a shared
class name nor matching hashes proves full design alignment. Active pad/converter
wiring gaps were corrected. Retained local waveform, timing and circuit
experiments keep their explicit assumptions and qualification limits; they do
not become current whole-chip evidence merely because their unit tests pass.

The RX-filter pair now reserves8mA rather than4mA. The rerun minimum is4.407mA for noise/capacitive drive and7.251mA including a separate resistor-drive reservation. These remain conditional estimates, not universal bounds. The234mA external-clock total retains all warm loads and leaves6mA under240mA. The selected five-pole TX filters use that entire margin: the external-clock allocation is now240mA. Capacitor area, omitted circuit overhead, stronger blockers and package response to the increased RF load remain open; previous physical campaigns must be rerun.

## Architectural changes with benefits across multiple risks

Evaluate these changes before further local CDR tuning. The selected inventory
remains authoritative until a replacement has its connections, controls,
resources and capability checks updated together. These are disposition gates,
not five independently selectable hardware revisions.

1. **Host interface: retain the existing bus, 3.3 V and selected 6 pF board-load
   requirement for now.** The110mA HOST allocation is a reservation, not measured
   consumption. The refreshed `host_architecture_current_comparison` in
   `evidence/selected-revision-check.json` uses shared loads, voltage, bank
   membership and H2D rate with retained nominal library energy. Across the
   eight drive/slew settings, alternating traffic estimates37.37–48.33mA at
   150Mword/s,38.39–49.74mA at155.25Mword/s and68.89–91.72mA at312.5Mword/s.
   These include both banks and their existing other-current allowances;
   settings have not jointly passed capture timing. Do not subtract the
   difference from the whole-chip reservation. The comparison now rejects
   voltage changes without matching library characterization and loads outside
   its interpolation range. Next compare timing and package ripple at the same
   throughput and actual candidate drive setting. Lower voltage or a new bus
   requires evidence of a benefit beyond the already-selected lighter load and
   slower RF return clock. Quiet idle does not reduce worst-case active traffic.
2. **CDR: compare reference-based phase selection against the oscillator-following
   candidate before selecting another loop tweak.** Use the same input data,
   offset/SSC, phase-noise and package assumptions. Include phase quantization,
   update latency, wrap/slip handling, glitch-free selection and clock-distribution
   current. An external reference does not remove recovery of an independent
   transmitter's frequency. No alternative has been promoted or assigned free
   area/current savings. The fresh `reference_cdr_actuator_comparison` gives a
   necessary actuator check:32 phases at2.5Gb/s and6000ppm need480million
   single-step updates/s. One step per250MHz word clock tracks at most3125ppm;
   even312.5MHz updates reach only3906.25ppm. Four-UI updates have enough slew
   capacity but are625MHz and have not been priced or physically qualified.
   The12.5ps phase step also adds up to0.015625UI nearest-phase error. Continuous
   winding at the maximum offset crosses15million full phase turns/s, requiring
   correct cycle numbering and transfer to the deserializer. These are arithmetic
   requirements, not a simulated recovery loop. Reject a simple word-rate,
   one-step phase selector as the replacement; retain the existing CDR while
   evaluating multi-step or faster control only if its combined budget improves.
   The extended actuator comparison keeps the reference-based route open:
   two32-phase steps per250MHz update provide6250ppm first-order slew capacity,
   while312.5MHz updates provide7812.5ppm. Each permits a0.0625UI commanded
   phase jump. Quantization plus uncorrected drift over one update consumes
   0.075625UI at250MHz or0.063625UI at312.5MHz; one additional update of latency
   raises those figures to0.135625/0.111625UI. Thus multi-step updates clear the
   simple slew-capacity obstacle but consume substantial timing margin. These
   bounds exclude other jitter, SSC acceleration, nonlinear interpolation and
   loop dynamics. Next compare the full sampling/holdover budget and glitch-free
   update realization before committing to this architecture; single-step failure
   must not be misreported as impossibility of reference-based recovery.

   [AMD describes the reference-PLL/phase-interpolator architecture](https://docs.amd.com/r/en-US/am017-versal-gtm-transceivers/RX-CDR);
   that implementation is not GF180 performance evidence.
3. **Operating envelope: map required combinations before changing acceptance.**
   Derive transition gaps, offset/SSC and silence/restart behavior from each
   target's actual coding and lifecycle. Keep the512UI-plus-SSC experiment as an
   explicit combined stress. Do not downgrade a capability or erase its failure
   merely because an easier envelope passes. Generic controls remain numeric;
   protocol recipes and their requirement mapping belong to the FPGA/verification
   side, not on-chip profiles.
   [Intel's8b/10b encoder documentation](https://cdrdv2-public.intel.com/654541/dsed8b10b.pdf)
   specifies a maximum run length of five for valid coded traffic. Consequently,
   512UI no-transition stress must not be represented as ordinary valid8b/10b
   payload. Electrical idle, OOB, startup and malformed traffic remain separate
   required lifecycle cases, and SDI/custom long-run capability remains a retained
   target. This distinction does not yet prove any complete protocol or authorize
   reducing its jitter/SSC or recovery requirement.
4. **USB pads: retain the shared pair for now.** The fresh
   `usb_pad_separation_loading` comparison removes90/99% of the entire assigned
   0.3pF inactive-branch capacitance while preserving base pad and mutual loading.
   Even the99% case improves linear serial transfer only0.082dB at742.5MHz,
   0.203dB at1.25GHz and0.506dB at2.5GHz. This intentionally overcredits removal
   of USB: the aggregate is not identified as USB-only capacitance. It does not
   bound benefit if that assigned decomposition is wrong. Spare sites permit
   consideration of a dedicated pair, but extra protection/routing and retained
   TMDS power-off requirements have no demonstrated net benefit yet. Reopen
   separation if protection implementation fails or a justified branch loading
   estimate materially exceeds the current allocation. No pins are reassigned;
   common-return noise and USB deadlines remain open either way.
5. **RF board network: turn assistance into explicit operating requirements.**
   For each accepted RF envelope require a realizable preselector/matching/supply
   network, including wanted insertion loss, blocker-offset rejection, component
   tolerance and package effects. Preserve near-channel blocking and internal
   saturation checks; an ideal external filter cannot repair those. Evaluate an
   external PA only as an explicitly assisted output route, preserving the
   separate chip-output power requirement. External clocks and passives are
   already allowed, so their existence earns no new feasibility credit. The
   normative `rf_interoperability.external_frontend.selectivity_policy` now
   forbids unsubstantiated selective-rejection credit inside a fixed board's
   full-band passband. `rf_board_selectivity_comparison` checks both signs of
   12MHz blocker and first-image diagnostic offsets at carrier endpoints and
   midpoint:8of12 probes remain inside the declared carrier band. A passive RX
   board with maximum3.5dB loss and nominal2dB wanted loss allows at most1.5dB
   selective rejection there, not the18dB historical assistance assumption.
   Baseline selective credit is zero; outside-band rejection remains unknown.
   This is a consistency bound, not a component design. TX image locations are
   reported without treating the RX-loss allocation as a TX specification.
   Therefore broad-band board filtering does not remove the on-chip RX blocker
   or TX reconstruction obligations. Narrow switched/tuned boards need separate
   coverage and retune timing proof; existing hypothetical fixtures are retained
   with their scope, not relabeled as baseline capability evidence.

The immediate comparison order is host electrical timing/current together
and the two CDR routes under mapped operating requirements. The initial USB
loading comparison supports keeping the shared pair, subject to protection and
capacitance qualification.
RF board requirements run alongside those comparisons. No schematic work is
needed for this architectural decision stage, and none of these arithmetic or
structural checks closes a protocol capability by itself.

### Joined RF TX mitigation decision

The preferred improvement route combines sharper TX reconstruction, finite
output supply rejection and better differential-clock input/distribution
rejection. It is represented by `selected_revision_check.rf_rejection_candidate`
as one immutable alternative snapshot; selected hardware is not yet changed.
The candidate has:

- Fifth-order Butterworth TX filters,12MHz maximum cutoff,4mA per filter in both
  warm RF directions;0.46mm2 transferred from unassigned reserve, leaving0.85mm2.
  Total die allocation is conserved. External-clock RF allocation is240mA with
  zero reserve; added rejection implementation costs are not yet established.
- Input mismatch0.02, common-mode gain−0.01 and downstream clock sensitivity
  0.0025ps/mV, compared with0.2,−0.1 and0.025ps/mV in the selected parent.
  Mismatch jointly affects capacitance, bond inductance, source resistance and
  leg amplitude; transistor matching alone cannot establish this requirement.
- Output supply-to-gain response H(s)=h+(d−h)/(1+s/(2πfp)), with d=1,h=0.02 and
  fp=5MHz. Selected d=h=1 retains the original rail-proportional law exactly.
  Dynamic variants require ordered times and use causal held-input propagation
  from a settled initial state. Actual supply still controls headroom. The old
  amplitude certificate rejects nonunit variants; it cannot certify this law.

The recorded `joint_rf_rejection_tx` comparison uses the same250 RMS transport-code
request, resolved driver gain near6.294,8nH signal loop and0.538pF ideal matching:

| Metric | Selected design | Joint candidate |
|---|---|---|
|Allocated RF current|234mA|240mA before unknown rejection overhead|
|Loaded mean TX power|+0.844dBm|+0.772dBm|
|Sampled minimum local rail|2.720V|2.707V|
|Sampled conservative voltage margin|57.9mV|173.6mV|
|10–30MHz offset-band power|1.279uW|0.182uW|
|30–50MHz offset-band power|0.741uW|0.00132uW|
|Above50MHz offset-band power|2.848uW|0.0169uW|
|Known-training equalized diagnostic EVM|3.851%|3.954%|
|Common-gain/delay-only diagnostic TX error|4.730%|7.067%|

Both sampled electrical guards pass without input/driver clipping. Far-offset
power improves22.26dB. This is a joined waveform calculation: the changed clock
also controls native DAC edges, filter current enters the common supply ledger,
and output rejection does not improve the physical rail artificially. Broad
integrated bands are not a standards mask, and per-tone receiver equalization
is not raw transmitter EVM. The added scalar observer fits only one complex
gain and delay on the first two known DATA symbols, then scores ten held-out
symbols. It de-embeds only the independently known diagnostic instrument;
it has no transmitter per-tone or per-symbol correction. Its4.73%/7.07% results
expose distortion hidden by the equalized observer and strengthen the need for
causal FPGA pre-correction before selecting the sharper filter. This is still
not a standards-defined EVM measurement. An independent instrument/gain/delay
control gives near-zero error while a frequency-shaped control remains above
10%; that regression ensures the observer does not fit away this distortion.
No FPGA TX pre-equalization is included.

The retained component diagnostics explain why all three changes are needed:

- `joined_tx_filter_comparison`: sharper reconstruction reduces image-band power
  but barely changes the far-offset floor. Its historical source scope remains
  recorded; it is not relabeled current after later model changes.
- `five_pole_tx_impairment_isolation`: output-rail AM and mixer PM dominate the
  modeled far-offset power. Removing cubic distortion barely helps. Scaling
  both AM/PM amplitudes10/20dB gives approximately10/20dB lower far-offset power,
  but those interventions are inverse requirements, not physical mitigations.
- `tx_clock_component_isolation`: above50MHz, input-edge and downstream phase
  are0.01389/0.03683rad RMS; combined0.03610rad. They are correlated, not suitable
  for RSS addition. Source/input-noise tones contribute essentially none there
  under their assigned spectra. Doubling the numerical sample rate barely
  changes these values; interpolated edges still omit between-edge physics.
- `joint_clock_rejection_candidate`: explicit tighter coefficients reduce
  combined above50MHz phase to0.003624rad without improving the external source
  phase-noise spectrum. Low-offset source/input noise remains. Only the tested
  signs and nominal package values are covered; this is not a corner enclosure.
- `tx_supply_gain_response`: the hypothetical finite response agrees with the
  independent analytic50MHz transfer, with error decreasing on grid refinement.
  This checks the model, not circuit rejection, cold startup or chunk continuation.

The latest `joint_rf_tx_fpga_correction` comparison adds the existing49-tap,
12-fractional-bit FPGA FIR at the actual37.90625MS/s native rate. Coefficients
fit the assigned analog filter and DAC hold; they do not borrow the legacy
37.6875MS/s polyphase response. Filtering is causal before DAC quantization,
with no amplitude renormalization or sample advance. The resulting alignment
delay is0.6331us and48 native samples of history; the existing32-input-sample
interpolator separately needs1.6us lookahead. These are FPGA costs, not extra
on-chip packet storage. Accumulation is floating point in the model, so finite
wordlength/throughput still need proof.

| Same joint candidate | No FPGA correction | Causal FPGA correction |
|---|---|---|
|Scalar diagnostic TX error|7.067%|3.141%|
|Loaded mean power|+0.772dBm|+1.113dBm|
|Sampled conservative voltage margin|173.6mV|120.5mV|
|10–30MHz offset-band power|0.182uW|0.215uW|
|Above50MHz offset-band power|0.0169uW|0.0176uW|
|Input/driver clipped samples|0/0|0/0|

The output observation follows the physically delayed packet; the FIR delay is
not removed from scheduling. The improvement survives quantized coefficients,
native DAC noise and the loaded timing/supply model, but does not establish
measured calibration, a real packet's deadline, mask compliance or HE EVM.
Additional calibration mismatch and packet-edge cases remain required.

`joint_tx_fpga_workload` prices the actual joined64-tap windowed-sinc interpolator
plus49-tap correction at37.90625MS/s, rather than borrowing the older603/320
polyphase workload. With16-bit storage assumptions, unfused I/Q processing needs
8.567G real products/s:54 one-product/cycle lanes at200MHz and80% utilization.
History is444bytes and a straightforward1213-phase nominal coefficient table is
155362bytes. These reside on the FPGA; no additional chip storage is requested.
Asynchronous sample-rate drift needs a separate fractional-phase/table policy;
these figures exclude modem/FEC/RX and do not establish memory-port or timing fit.

Adding the shared RX pipeline, FPGA decision, TX pipeline, board settling,
uncertainty, interpolation lookahead, correction delay and16-native-pair prefill
serially charges6.055us of the diagnostic10us response gap. The remaining3.945us
must cover host transfer/frame wait, CDC, serialized controls and compute-pipeline
costs. No overlap is credited; the TX analog allocation and correction delay are
both retained conservatively. Positive remaining time is not a demonstrated
packet deadline. The small history requirement is therefore compatible with
FPGA-owned storage, while sustained compute and timely service remain separate
implementation obligations.


**Decision:** retain this combined route with causal FPGA correction as the
preferred candidate; next close its priced implementation and packet-level
emissions/timing envelope.
Do not add more reconstruction poles to solve modulation introduced after the
filter. Do not count a cleaner external oscillator as a remedy for the modeled
loaded-input/distribution disturbance. Before selection, account bias/regulation/
trim costs, actual gain-dependent distortion, matching and sign/corner uncertainty,
packet turnaround, complete HE/other-radio waveforms and applicable masks.
The assigned240mA total cannot prove that unknown additional rejection circuitry
fits. No schematic work or physical-performance claim follows from this result.

### Shared TX reconstruction integration

`tx_filter_lifecycle_integration` compares the former three-pole
filter and the now-selected five-pole design through the same seven-stage RF/wired/reference-
fault/recovery schedule. Wi-Fi filter history, BLE reply reconstruction, retained
lifecycle filter states and the sufficient amplitude calculation resolve the
prototype from the same shared snapshot. Explicit simplified BLE reconstruction
remains available but is recorded as an override; design-bound default operation
uses the selected order. A five-pole BLE reply decodes at its independent peer in
the scoped settled-TX regression.

Both lifecycle runs complete with only the deliberately injected reference fault,
no sampled amplitude exceedance and no sampled driver clipping. These runs use
native peak 50 codes and gain 4.5, not the target-power TX operating point. The
five-pole triangle-bound all-history code radius is **21**, compared with **53**
for three poles. The adapter now reports that stricter bound instead of borrowing
the three-pole certificate. The sampled waveform passing above that sufficient
bound does not prove safety for arbitrary history.

The five-pole design is now the normative filter. Its shared adapters and
provisional resource ledger have been migrated; old three-pole records do not
qualify the current sources. Combined clock/driver rejection and causal FPGA correction now have the scoped
lifecycle evidence below. Complete packet transitions, tolerance coverage and
standards power/emissions acceptance remain open. Physical realization and fabrication fit are deferred; these remaining
behavioral obligations are the reason not to label the entire improvement done.

### Retained TX supply-rejection integration

`tx_rejection_retained_lifecycle` exercises the joined five-pole filter, stronger
external-clock rejection and driver supply-gain response through the seven-stage
warm lifecycle. The gain response now has explicit persistent state. Quiet/RX/
wired intervals contribute sampled rail history before TX resumes; packet starts
and reference-fault recovery do not silently reset the gain to its settled value.
The three TX captures retain increasing state times and quiet-history counts
(33,836, 75,056 and 81,779 samples). All stages complete with only the injected
reference-loss fault, no sampled amplitude exceedance and no driver clipping.
This remains the native-peak-50, gain-4.5 case, not target output power or emissions.

The first-order response passes an independent step-response and chunk-continuity
check. Reversed time and configuration changes reject without mutating retained
state. BLE TX also applies this gain law; carrying state across separate BLE calls
requires the caller to supply intervening rail history. Empty state explicitly
means settled initialization, not cold startup or validated power gating.

Supply rejection introduces memory: after a falling rail, gain may remain high
while headroom immediately decreases. The sufficient amplitude calculation now
charges the maximum allowed past rail at each current rail, rather than borrowing
the memoryless gain/headroom correlation. Its guarantee requires both initial
state and all rail history to lie inside the declared interval. Full packet/FIR
integration, target power, emission masks and cold-start behavior remain open;
physical realization is a later milestone.

### Corrected TX power through the retained lifecycle

The promotion is verified by `normative_corrected_rf_lifecycle`: no candidate
constructor or explicit FIR-enable override is used. The shared configuration
supplies filter/rejection requirements and FPGA correction parameters. Under the
combined stress, pre/post-fault output is +1.1367/+1.1351 dBm with all recorded
power, amplitude and electrical checks passing; full-record relative energy
margins are 8.406/5.718 dB. This is the current design result. Earlier comparisons
below retain their own snapshots and are not reclassified as current evidence.

`tx_corrected_power_lifecycle` now applies the same causal 49-tap, 12-fractional-
bit FPGA correction as the joined TX bench before transport/DAC quantization.
Scale is chosen before correction; there is no post-correction normalization or
time advance. At 37.5 MS/s the 24-sample delay is 0.64 us and is included in the
power/observer interval. The prepared record has explicit zero prehistory;
STOP/fault discards FPGA preparation while chip filter and gain states persist.
Fixed-point accumulation and real FPGA deployment remain unqualified.

At requested native peak 200 and gain 6.3, the joint five-pole/clock-rejection/
driver-rejection design delivers +2.638 dBm but reaches 0.39194 V, violating the
unchanged 0.35 V reconstruction requirement at 18 sampled points. This is retained
as a failing control. Reducing only the requested FPGA amplitude to 170 gives
**+1.2329 dBm and 0.33283 V** before and after injected reference-loss recovery,
with no sampled driver clipping and passing electrical checks. Scalar-gain/delay
held-out TX error is 2.422%; this is a diagnostic, not standards EVM acceptance.

The same point also passes the existing combined stress: -33 mV source offset,
60 mV peak ripple at 10 MHz and fourfold supply-delay sensitivity. Before/after
fault output is +1.1367/+1.1351 dBm, reconstructed peak remains about 0.33283 V,
and scalar diagnostic error is 2.449%/2.545%. Power, sampled amplitude, clipping
and electrical checks all pass. This is one simultaneous adverse scenario, not
a continuous tolerance enclosure. Evidence: `tx_corrected_power_stress_lifecycle`.

**Decision:** select this filter/rejection architecture and FPGA correction in
the normative design. Use the backed-off operating point for further integrated
qualification. It jointly meets the recorded 0 dBm power, amplitude and electrical
requirements in this lifecycle. Report `tx_requirement_summary` separately from
lifecycle completion; a sequence finishing must not hide failed power or amplitude
checks. Remaining gates are complete packet waveforms, switching/emission masks,
noise/tolerance coverage, source/package fidelity and FPGA timing/arithmetic.
No physical feasibility or all-protocol capability claim follows from this point.

The `tx_corrected_full_record_spectrum` rerun adds an untapered whole-stage
finite-record spectrum, including the actual retained TX history and ideal mute
boundaries. Gaussian power-spectrum smoothing at the contract's 100 kHz RBW
places the record 8.411 dB below the relative envelope before the fault and
5.682 dB below after recovery, worst near 28.1 MHz offset. The helper is shared
with the older RF-filter experiment; it no longer has a separate measurement
implementation. FFT convolution keeps the finer spectral interpolation fast.
Independent tone/impulse controls check spur rejection, scale invariance and
that an edge impulse cannot disappear under a taper. Unresolved RBW grids cannot
return a passing energy screen.

This remains `qualification=false` and `mask_pass=null`: four DATA symbols and
ideal mute do not establish complete PPDU or switching behavior, and Gaussian
energy smoothing does not implement the required time-domain detector/VBW.
The existing 100 kHz RBW, 7.5 kHz VBW and HE20 mask offsets were rechecked against
[Rohde & Schwarz's transmitter measurement description](https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/premiumdownloads/premium_dl_brochures_and_datasheets/premium_dl_whitepaper/IEEE-802-11ax-Technology-Introduction_wp_3609-9470-52_v0100.pdf).
Absolute/regulatory limits and harmonics outside the sampled envelope remain
separate obligations; the diagnostic margin does not close them.


## Test validity: what a passing regression does and does not establish

Review both the stimulus and the acceptance criterion before treating a result
as evidence for or against a capability. Current concrete findings are:

- **Waveform artifact:** unwhitened zero-padded diagnostic DATA produced roughly
  23 dB crest and clipping. Seeded DATA whitening removes that particular
  artifact; the original remains an overload control. Neither diagnostic is an
  independent standards-valid HE packet, and a shared encoder/decoder can agree
  on the same mistake.
- **Wrong clock domain:** a nominal-time holdover deadline expired early under
  downspread. The policy now counts recovered edges, with a separate clock-fault
  input. Correcting that policy does not establish analog phase margin.
- **Stimulus boundary:** inserted zero runs could join adjacent zeros and exceed
  the intended 512 UI. The common-envelope stimulus now brackets the run with
  opposite bits. Results from the old longer run retain their adverse scope.
- **Numerical artifact:** guarded FFT continuation could perturb previously
  committed reference history. Causal propagation addresses that mechanism;
  convergence remains separate from converter accuracy and physical feasibility.
- **Optimistic TX assumption:** the current cubic distortion precedes scalar
  programmable gain. Consequently, nearly unchanged EVM in a gain sweep cannot
  establish physical gain-independent linearity or free output-power margin.
- **Insufficient acceptance evidence:** correct decoded bits do not imply CDR
  qualification; a short packet is not a BER/PER bound; expected rejection is a
  useful safety regression, not evidence that the requested capability works.

Keep simplified and deliberately adverse tests. Their assertions must validate
those stated purposes, while capability conclusions require the shared selected
design, credible stimuli, explicit uncertainty and independent reference checks.

## Closure of the five requested areas

| Requested area | Current decision and connected evidence | Remaining architectural gate |
|---|---|---|
| Common operating envelope | RF RX/TX, wired and USB share one current inventory, local/HOST package state and retained analog state. | Close traffic-dependent current feedback and demonstrate a common RF/wired success region under bounded uncertainty. |
| Converter/reference | Keep asynchronous SAR with a 20 ns publication ceiling and 3 ns acquisition. Inventory switch loading, cycle guard, diagnostic reference charge and variable decision timing run in the joined lifecycle. | Bound continuous reference/diagnostic drive, mismatch, kickback, rare decisions and actual sequencer cost. |
| Shared pads | Retain ground-primary protection plus power-off-tolerant isolation and charge reduction. Connected mode transitions and externally driven power cycles expose internal stress and reverse charge. | Resolve physical junction paths, internal stress limits, brownout isolation, clamp/package coupling and dynamic USB electrical margins. |
| Physical clock/CDR | Keep differential external timing and require joint phase/frequency/aperture holdover acceptance. The stronger 0.025 ps/mV coupling and 25 ps timestamp candidate sustains continuous qualification in the scoped SSC fixture; inserted gaps still cause losses. | Establish useful tracking and gap coverage with justified uncertainty and priced implementation; neither zero bit errors nor conservative rejection closes this gate. |
| Whole-system integration | Model-observed readiness, stopped diagnostics, finite host delivery, asynchronous conversion, fault/recovery and calibration-generation invalidation share one trajectory. | Join cold startup, physical sensing/acquisition, measured recalibration/correction deployment and serialized control/fault latency. |

The next architectural decisions are useful CDR qualification and a common
loaded RF/wired operating envelope. Pad protection and cold-start/recalibration
remain required integrations. Do not turn these into an open-ended search for
small passing cases: each result must change a requirement, a block decision or
a whole-system acceptance verdict. Separate manifests and passing component
tests do not establish completion.

**Evidence status:** the latest refresh exposed a configuration error in two
adverse wideband cases: a 2 us PGA response was passed outside the declared circuit
variant. It is now declared in both I/Q PGA blocks of that hypothetical design;
both affected cases have been rerun with verified source manifests and seven
reconstructed configuration records. The adverse converter case now rejects on
its conversion deadline; the RF-corner case fails on 13 clipped PGA samples with
no direct receiver overrides. Their earlier override-guard rejection was not
physical failure. The subsequent packet-width guard change invalidates source freshness again;
The shared-design test migration is complete, but integrated physical evidence must still be regenerated before it is cited for the current source revision. Configuration reconstruction and source freshness remain separate from
RF qualification and mathematical-model completion.

## RF-chain operating region: sampled results

The authoritative results are
`evidence/selected-revision-check.json:rf_chain_first_version`. The refreshed
matrix contains seven conditional operating points, six failed points and two
converter-deadline rejections. Failures retain their actual design and assumptions.
`verification/check_contract.py` independently rechecks configuration bindings,
converter/rail/reference margins and driver allocation. The first-version closure
flag remains false; these are sampled conditions, not a qualified RF envelope.

Older rows use the230mA inventory; the refreshed narrowband adverse row uses the selected234mA inventory and20ns conversion allocation. Recorded physical conditions are 3.3 V source, differential external
2.426 GHz clock, /64 conversion clock, 0.25 nH supply return, 0.2 nH die ESL,
6 pF host-load target and tied reference return. RX combines RF thermal noise,
input cubic nonlinearity, blockers, delivered LO phase, moving supply,
finite gain settling, PGA clipping, asynchronous SAR decisions and reference
recharge feedback. TX combines DAC noise/quantization, reconstruction, delivered
phase, moving rails, driver distortion/compliance and the RF pad/bond load.
RX and TX are separate operating directions on the same hardware budget.
The narrowband exchange uses independently settled RX and TX configurations
from the same design. It does not retain analog state or reference charge through
turnaround; reply decoding does not qualify that transition.

| Sampled regime | Working configuration and result | Boundary exposed |
|---|---|---|
| Wideband, diagnostic coded HE20 DATA with legacy acquisition | Wanted −70 and −75 dBm; CW blocker −30 dBm at +12 MHz; 36 dB PGA reached from 30 dB through a 0.2 µs pole. Payload recovered, no PGA clipping, conservative ADC headroom, approximately 1.80–1.93 ns conversion completion margin. | −85 dBm at 42 dB gain fails payload recovery. Maximum gain clips at −65/−75 dBm; 36 dB still clips at −65 dBm. |
| Narrowband LE1M request/reply | Wanted −67 and −75 dBm; modulated GFSK blocker −50 dBm at +2 MHz; received-code gain control with command latency and 0.2 µs PGA pole. Request and loaded reply decode with rail, reference and electrical margins. | −80 dBm fails request recovery. This does not locate a precise sensitivity threshold. |
| Combined narrowband RF corner | −67 dBm wanted / −50 dBm blocker; NF 8 dB, IIP3 −3 dBm, doubled source/input phase-noise amplitude and +10% external matching capacitance. Request and reply decode. | An assigned adverse combination, not a measured GF180 corner or continuous tolerance enclosure. |
| Loaded wideband TX | 250 RMS transport codes; quantized driver gain 5.72235; 8 nH signal bond loop, 0.4 Ω loop resistance, 0.5 pF differential pad capacitance and nominal 0.538 pF external series matching. About +0.041 dBm, 3.85% diagnostic EVM and zero diagnostic BPSK errors. | Only about 0.04 dB nominal margin over the 0 dBm target; arbitrary load/phase corners and spectral masks remain unqualified. |
| TX phase/matching corner | Double source/input phase-noise amplitude and +10% matching capacitance: about +0.132 dBm and 3.92% diagnostic EVM; electrical and mixer limits pass. | One signed component-tolerance change, not worst-case matching. |
| Converter timing corner | Keep assigned 50 ps regeneration, 100 ps launch and 0.2 V decision threshold within the 20 ns ceiling. | The refreshed narrowband100ps corner now decodes request/reply with1.68ns conversion margin under the20ns allocation. The refreshed whitened wideband adverse case also passes with1.68ns margin. No continuous50–100ps region is established. |

Nominal RX assumptions are 6 dB NF, 0 dBm IIP3, 2 dB external insertion loss
and 10 ps RMS converter aperture error. The source/input finite phase spectrum
has 0.00857 rad RMS; its doubled-amplitude corner has 0.01713 rad RMS.
Package-induced phase and reference-feedback timing are additional, explicitly
connected terms. These are assigned requirements, not measured noise limits.
The narrowband reply now uses the same pad/bond/matching network as wideband TX;
its roughly +6.00 dBm constant-envelope result is not an OFDM power claim.
The audit checks its 28 mA driver against the actual 43 mA RF owner allocation,
independently of the reply helper's legacy 44 mA reservation guard.

**Decision: keep the existing analog block set for this first version.** Use
existing numeric gain controls to reserve headroom; 36 dB is a tested external
host setting, not an on-chip Wi-Fi profile. Preserve the 50 ps comparator
requirement and externally adjustable matching. The refreshed wideband adverse case at−65dBm wanted /−30dBm blocker passes after DATA/padding whitening, with8dB NF,-3dBm IIP3,100ps comparator regeneration,2us PGA pole and doubled phase-noise amplitude. It has zero clipped samples and zero raw coded-bit errors. This is one conditional BPSK point, not a robust wideband uncertainty region.
Do not interpret interpolation between passing points as verified performance.

The earlier wideband record's roughly23dB crest was misattributed to training.
The large peak is in its unwhitened zero-padded final DATA symbol; training
itself peaks at about2.7 in the fixture's amplitude units. With explicit seeded
DATA/padding whitening, seed81 has8.63dB crest instead of22.79dB. The external
receiver reverses the mask; no chip block or analog limit changes. Unwhitened
DATA remains an explicit overload control. This diagnostic whitening is not the
WLAN scrambler, HE-LTF or a standards-valid PPDU; rare peaks and transmitter
clipping/emissions still need qualification. The
bench uses one seed per mode, diagnostic BPSK/FEC and known DATA training, not
full HE signaling or MCS0–7 interoperability. No PER confidence, complete blocker
mask, TX emission mask, transistor noise/mismatch/kickback, nonlinear reactive
stability, signal-dependent RF supply-current closure or cold-start/turnaround
qualification follows. Other narrowband protocols need their own waveforms.

Reproduce a point from `verification/` with
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 selected_revision_check.py --rf-chain-case NAME`.
The CLI lists the 15 maintained cases. Run `python3 check_contract.py` to audit
all current cases; its `rf_chain_first_version` result is deliberately separate
from whole-chip milestone completion. The next RF work should replace the
diagnostic training with independent HE references, extend uncertainty at an already usable gain
setting, and test emissions/current feedback—not add more isolated pass counts.


Converter readiness and transport now enforce both ends of the same declared
supply model domain, including TX reference recovery. Observations outside
2.5–3.6 V reject qualification; fresh supply cannot compensate for expired
reference observations. These are model-consistency requirements, not measured
voltage tolerance or physical monitor specifications. The complete lifecycle
uses a 200 ns observation-age limit in the selected ownership runner, with
100 ns startup observations and observations at RX completion/TX consumption.
TX now checks retained reference and supply before accepting a consumed word;
wired TX also observes the parked converter reference. This closes indefinite
reuse of startup readiness in that runner. Physical sensing cadence, coverage
during idle gaps, between-observation extrema and connected cold startup remain
open. The numeric coverage limit is not a hardware monitor allocation.

The warm RX/TX/RX lifecycle now includes independent 100 ns reference/supply
observations during mute/settling. Seven stages complete with the 200 ns age
limit; disabling that path faults at 200 ns age. Read-only idle-reference
recovery preserves the reservoir charge ledger and conversion state. Active RX
uses completed conversion observations instead of assuming an unloaded reference.
The generic observation event schedule survives split transfer calls; invalid
observations fault immediately, and missing observations do not refresh age.
This connects existing supervisor behavior mathematically, not sensor dynamics,
bias/filter settling, clock failure of the supervisor or physical monitor cost.
The wired recovery adapter also requires the independent observer when a parent
qualification monitor exists. It samples through both startup guards and wired
RX, retaining the parent reference/package state. Time spent faulted awaiting
host service does not grant readiness; rearming needs a fresh continuous guard.
The refreshed joined wired-recovery run completes all seven stages and resumes
6502 matching host words after the 20 us requalification guard. Execution
completion is not quality acceptance. Its earlier RX and TX shortfalls are
superseded by the selected gain-regulation and corrected-TX results in the
open-issue register; the old run remains scoped historical evidence. These results cover the retained
model state and assigned observer; they do not qualify sensor implementation,
serialized management transactions or target-protocol recovery.
The retained RF/wired lifecycle now has an explicit USB extension using the same
chip, reference reservoir and package trajectory. It transitions both local and
HOST-node currents to the USB inventory; independent nodal AC checks cover the
added HOST input, and settled voltage matches the DC ledger. A fresh startup
guard and live reference/supply observations gate the direct USB exchange.
The pad is retained but isolated through earlier abstract wired stages. This
does not join their electrical lanes or qualify assigned USB clocks/acquisition.
The joined lifecycle also reads SAR acquisition, sample capacitance, diagnostic
switch capacitance/resistance and cycle guard from that inventory. Converter
state is initialized with those parameters, and conversions use the chip-owned
epoch/configuration binding. The refreshed RF/wired/USB trajectory includes
50 fF diagnostic input loading, 100 ohm added resistance and a 0.2 ns guard.
It completes the existing fault/recovery sequence with conserved reference
charge. The paired asynchronous decision model now runs on this same trajectory,
using the assigned 50 ps regeneration, 100 ps launch and 200 mV output threshold.
Across 366 conversions completion ranges from 15.21 to 15.80 ns; words publish
at the unchanged 18 ns ceiling. Reference recovery uses actual completion time,
and retained state carries the comparator-model identity across STOP/restart.
The RF/wired/USB fault/recovery run completes with a 4.78e-25 C reference-charge
residual. This joins the timing hypothesis, not physical comparator tails,
kickback or sequencer implementation. Diagnostic selections are now scheduled in the joined variant below; fitted
calibration deployment/validity and continuous source behavior remain open.

The joined lifecycle now uses one inventory throughout: externally clocked RF RX/TX230mA,
wired268.45mA and USB252.2mA. Both current ports transition without resetting
package state, and settled rails match each mode ledger. Traffic-dependent
current feedback and diagnostic/calibration scheduling remain open. The USB
extension now also depresses the upstream reference target to 0.8 V through the
retained current-limited reference network. A live observation faults the chip
after six reply bits, releases the pad and invalidates the old session. Source
restoration, STOP and a fresh 20 us qualification guard permit a new 48-bit reply
on the same pad/package/reference state. Reference charge balance residual is
4.78e-25 C. This closes generic observed-reference fault/rearm in this trajectory;
physical sensing, USB protocol retry semantics and cold startup remain open.

The existing `verification/check_contract.py` report now includes
`review_evidence`: source freshness for the five selected review sections,
mapped by `mathematical-closure.json:milestone.review_evidence`. A stale section
is historical evidence until rerun against its changed dependencies; do not
replace its hashes without executing it. Source matches establish provenance
only, not acceptance or completeness. Nested report sections retain independent
manifests and are not qualified by a matching parent. This check separates the
current mathematical baseline from accumulated historical successes without
requiring another document or simulation for a status review.

The selected review sections retain their own recorded dependencies; use the
live audit for freshness after receiver changes. The recorded common preflight accepts the selected/lower-return
clock cases and rejects the higher-inductance case for both RF and wired use.
Its fixed-slot converter stress controls reach minimum 8.07–8.10 ENOB; the
separate asynchronous cross-check owns the selected timing decision. The common
wired controls decode without errors but exceed the 50 ppm residual assumption;
the integral two-cycle SSC control reaches 528 ppm. The refreshed reduced-coupling
256-UI fit still reaches 110/144 ppm in continuous/gapped cases. These reports
therefore do not establish the receiver's declared holdover uncertainty.

**Next architectural priority: make receiver clock qualification conservative
under SSC and gaps.** Keep the phase limit and target scope; do not promote a
case because it decodes or because its source hashes match. The detector/loop
must support a justified uncertainty estimate, loss/reacquisition behavior and
priced implementation. Common RF packet/TX subsections have separate manifests
and were preserved, not refreshed by this preflight. Pad clamp return coupling,
diagnostic/calibration scheduling and full cold startup remain open alongside
the CDR work.

The receiver now has an optional observation-derived holdover candidate,
`edge_time_bound_s`, restricted to the unaveraged least-squares window. If each
observed edge error is bounded by epsilon UI, the slope error is bounded by
epsilon × sqrt(n / Sxx), where Sxx is the centered sum of squared observed cycle
indices. The candidate adds the allowed frequency slew across the window,
correction saturation error and elapsed age since that estimate. It uses the
larger of this bound and the declared residual in the existing phase budget;
no qualification is granted before a finite window estimate exists. Forecasts
retain these states privately until commit. A causal gap regression verifies
that a larger timestamp uncertainty withdraws qualification earlier and allows
reacquisition after transitions return.

This is a conditional mathematical mechanism, not a selected physical estimator.
It assumes correct inferred cycle counts and a hard bound on all edge-time
errors, including channel and local-clock displacement. Gaussian RMS noise is
not such a bound. Timestamp coverage, interference/cycle-slip handling and finite arithmetic,
current and storage costs remain required before promotion.

The maintained `--cdr-observed-bound` candidate now connects the spectrum
movement bound to causal qualification, including elapsed time since the prior
transition and the known loop phase correction. It checks the incoming gap
before a returning transition can reset its state. The numerical movement table
is a behavioral representation, not an allocated on-chip lookup memory.
Timestamp uncertainty contributes to both phase and frequency budgets.

**The 50 ps/half-coupling control is not usable.** With
assigned 50 ps timestamp error and half coupling, the two-cycle SSC run qualifies
only 12.43% of continuous scored samples and 12.39% with inserted gaps. There
are 1157/1145 qualification losses and neither case ends qualified. Effective
frequency-bound violations remain zero and diagnostic bits decode, but neither
result compensates for the loss of valid traffic. Do not promote this candidate
or describe rejection as successful link support. Retain the protocol and gap
targets; the next design decision needs tighter justified detector/clock bounds
or an uncertainty formulation with evidenced correlations and useful coverage.
The independent gap audit remains diagnostic; its accumulated anchor bound must
not be confused with a measurement of absolute physical sample error.

**Select the stronger joint timing requirement for implementation:** local
supply-to-aperture sensitivity 0.025 ps/mV at the existing 1 GHz pole and 25 ps
total timestamp uncertainty. A matched rerun under those assigned values keeps
all continuous held-out traffic qualified, with zero diagnostic bit errors,
zero effective residual-bound violations and a 0.1863 UI independent peak phase
budget. The gapped case reaches 99.19% qualification and 0.1870 UI peak budget,
but has four qualification losses and a sticky transport fault. Keep long-gap
continuity, residual-frequency qualification and recovery service open.

The 25 ps envelope now allocates 10 ps to deterministic error and targets
2 ps RMS random timestamp noise, with an assigned Gaussian exceedance budget
of 1e-12 per observation. The Gaussian calculation gives approximately 6.38e-14
under those assumptions; it is neither a hard bound nor a link BER or lifetime
guarantee. The selected rerun uses 2 ps RMS; the failed 50 ps control retains
5 ps RMS. Systematic, channel and quantization errors must fit the same total
allocation. Physical tail coverage and correlations remain unqualified.

This is an explicit stronger circuit requirement, not demonstrated performance
or a cost-free model substitution. Preserve the failed control. Differential
cancellation/regulation headroom, current and area, and useful long-gap coverage
still require evidence. Only 37.81% of scored gapped traffic remains valid under
the sticky transport policy despite 99.19% receiver qualification; reacquisition
does not clear the fault. No uninterrupted gapped-link claim follows.

The clock-spectrum movement screen now supplies a phase-independent bound over
all separations up to T, not just the endpoint:
`sum(2 A sin(min(pi f T, pi/2)))`, for delay-tone peak A and frequency f.
`wired_envelope.aperture_motion_bound` implements this bound; an independent
phase/time grid verifies that a full-period endpoint cancellation cannot hide
an interior excursion. Applied to the recorded half-coupling spectrum, it gives:

| Maximum gap | Aperture movement bound | Remaining timestamp allowance after 0.1 UI initial error, before frequency drift |
|---|---:|---:|
| 1 UI | 17.3 ps | 42.7 ps |
| 3 UI | 28.8 ps | 31.2 ps |
| 16 UI and above | 36.4 ps | 23.6 ps |

At 2.5 Gb/s, the selected 0.25 UI budget is 100 ps. Thus the assigned 50 ps
edge uncertainty plus the 40 ps acquisition-error ceiling leaves only 10 ps
for phase movement, frequency drift, slew and commanded phase correction.
These independent worst-case allowances do not establish the required margin.
They do not prove physical failure: summed spectral maxima may not coincide,
and correlations require justified treatment rather than assuming independence.

**Design obligation:** qualify the sum of initial phase error, timestamp
uncertainty, bounded aperture movement, frequency/slew drift and known loop
correction over the admitted gap. The generic 512-UI counter is a programmable
ceiling, not a guaranteed valid holdover interval. Retain the intended gap and
protocol targets; resolve this joint budget through better measured/justified
clock bounds, detector precision and loop behavior before promising support.
The analytic function now feeds the optional causal qualification candidate.
It bounds only supplied tones; omitted noise, transients and physical cost stay
open. Its integration does not close the failed useful-operation gate.

`wired_envelope.holdover_phase_budget` now exposes the joint and inverse
requirement calculation. With the normative 0.0625 UI tracking allocation,
25 ps jitter reserve, 50 ppm residual and 330e6 ppm/s slew, the recorded
half-coupling spectrum gives:

| Gap | Total allocated phase bound | Remaining margin | Residual ceiling before extra correction cost |
|---|---:|---:|---:|
| 5 UI | 0.2096 UI | 0.0404 UI | 8136 ppm |
| 16 UI | 0.2167 UI | 0.0333 UI | 2128 ppm |
| 64 UI | 0.2194 UI | 0.0306 UI | 528 ppm |
| 192 UI | 0.2280 UI | 0.0220 UI | 165 ppm |
| 512 UI | 0.2588 UI | -0.0088 UI | 33 ppm |

These use tighter phase/timestamp allocations than the failed 50 ps candidate;
they are requirements, not newly demonstrated operation. The short-gap budget
is not intrinsically impossible, while 512 UI needs better combined phase,
aperture or residual performance. The normative architecture now explicitly
requires joint per-configuration acceptance and a pre-reset incoming-gap check.
Retain all gap targets; do not infer support from an independently legal counter
and residual setting. Saturation, actual error tails and any unabsorbed phase
correction consume additional margin.

The joined `--ownership-diagnostics` configuration now selects zero input in
RF epoch0, +VREF/4 and -VREF/4 in epoch3, and normal reception in epoch6. All
changes occur while stopped through the chip control surface. The FPGA receives
110 complete I/Q pairs per phase through the actual finite transport. Mean
zero codes are -0.33/-0.65 and reference-derived codes +513.09/-515.35 in the
12-bit transport representation. An assigned 0.25 pF effective reference load
per diagnostic lane draws 60.97 pC during the quarter-reference phase; the same
reservoir and package survive subsequent operation and USB reference-fault
recovery. Total reference-charge residual is 5.82e-25 C.

This closes scheduled diagnostic selection and delivery on that trajectory.
It does not establish absolute VREF, continuous diagnostic-source impedance,
calibration coefficient deployment or validity across gain/temperature/fault
changes. Keep those as explicit remaining lifecycle work. The normal-input
ownership run remains a separate configuration of the same implementation;
diagnostic stages bypass the externally driven ADC input even though the RF
frontend remains powered and charged to its inventory.

Calibration validity now has an explicit FPGA-owned analog-condition generation.
`rf_power_calibration.CalibrationValidity` rejects a missing or changed generation
when the record requires one, even when supply, temperature, configuration and
age otherwise match. The same gate is shared by the existing calibrated power,
receive, timing and I/Q consumers. A restoration/requalification regression
covers pre-fault acceptance, stale-record rejection and an explicitly renewed
record. Legacy standalone fixtures without a generation retain their narrower
scope; they do not prove fault invalidation.

The normative policy distinguishes analog-condition generations from ordinary
stream epochs. Observed clock/reference loss, reset, brownout or unqualified
condition changes invalidate affected records; restored nominal conditions or
clearing a stream fault cannot silently renew them. Generation ownership is on
the FPGA. The joined runner now advances that generation from its reported reference-loss
fault (generation1) and caught USB analog fault (generation2). Diagnostic
records from generation0 are rejected after RF recovery even though ordinary
transport resumes. The common validity gate performs this rejection; no
calibration-ready flag is injected. Serialized fault-poll latency, measured
requalification and correction deployment remain open. Raw post-fault capture
and an uncalibrated diagnostic USB reply are not calibrated operation.

## Mathematical completion versus physical validation

This milestone ends with a coherent conditional architecture, not extracted or
measured silicon. Exact reservoir-loop inductance, transistor gain/noise/current
and actual FPGA-board timing are later validation work. Their **numerical
requirements, uncertainty ranges, common resource costs and modeled consequences**
are required now. A parameter need not be physically qualified to be an explicit
hypothesis; it must not silently become a demonstrated fact.

| Must close in the mathematical model | May remain a later validation obligation |
|---|---|
| Canonical pad/transport/timing connections, independent peers and causal recovery | Transistor and RTL realization of those interfaces |
| Shared RF/wired/host uncertainty cases with credible success and adverse regions | Extracted package/metal/substrate parameter values |
| Target-level electrical, quality, power and deadline acceptance for all 17 targets | Silicon characterization and formal standards qualification |
| Consistent current/area/pin allocations for selected choices and alternatives | Final physical dimensions, routing and measured consumption |

The host-load, output-Liberty, local-loop and TX-gain studies have yielded bounded
requirements and explicit failure controls. Do not extend them merely because the
physical values remain unknown. The remaining work is to apply their requirements
consistently in the selected system, connect missing burst/pad/control paths and
issue target-level conditional verdicts. No criterion is marked complete by this
clarification, and missing functional blocks or unsupported success regions cannot
be deferred as "physical work."

## Shared-pad power-cycle requirement

The retained pad network now integrates reverse-supply charge separately from
supply work and reports sampled peak backfeed current. This distinction matters
at zero VDD: zero supply work does not imply zero injected charge. An independent
steady-state test checks charge against the external-source/clamp resistances.

With external 3.3 V/50 ohm sources retained, the connected screen starts in TMDS,
isolates the branch, then ramps VDD down, holds it off for 20 ns and ramps back
up. Assigned 5/50 ns ramps through the adverse 0.4 V/20 ohm rail clamp produce
84.2/83.0 mA sampled peak backfeed and 2.07/5.80 nC reverse charge. The selected
ground-primary hypothesis has no VDD path in this explicit topology and reports
zero backfeed. All four cycles conserve modeled energy to about1.2e-22 J.

Retain ground-referenced primary protection and power-off-tolerant secondary
isolation. These tests do not prove a real clamp implementation: rail voltage is
forced and its source can absorb current, so back-powered rail rise is not
predicted. Isolation precedes power loss; automatic brownout response, actual
junction paths, internal device stress, leakage and package coupling remain
open. Do not count endpoint safety or low average power as transition proof.

## Shared-pad transition integration

The connected four-node network now integrates finite signed break/make charge
pulses, retaining the peer drive and capacitor state. Injected control work has
its own energy ledger. An analytic RC pulse and transition tests verify charge
response and energy balance; invalid pulse specifications leave state unchanged.
The uncertainty screen uses 0/10/50 fF equivalent coupling times 3.3 V, both
polarities and 50/200 ps pulses. These are assigned probes, not extracted values.

At 50 fF the pad remains approximately 2.82..3.35 V while the unclamped 0.1 pF
divider nodes span approximately -1.46..2.73 V. At 10 fF the minimum internal
voltage is approximately -0.292 V. **Pad-terminal checks alone are insufficient.**
Require internal branch protection and controlled/cancelled switch charge with
explicit return paths, bandwidth loading and control-power accounting. More
dead time does not remove the charge applied at make. Do not treat the smaller
probe as a proven safe limit: internal clamps, transistor terminal stresses,
actual charge correlations and continuous extrema remain unqualified. The
reported negative voltages are the unclamped model's diagnostic, not predicted
silicon behavior. All tested charge-work residuals are below 8e-23 J.

A finite ground-to-divider clamp is now connected, including added node
capacitance, dissipated energy and integrated ground-return charge. The full
0.4/0.7 V knee × 20/100 ohm × 10/30 fF × polarity screen retains the 50 fF
charge-coupling and 50 ps pulse stress. Worst internal minima range from about
-0.46 to -0.96 V, versus -1.46 V unclamped; the knee is not a voltage ceiling.
Added capacitance costs 0.16..0.51 dB of divider gain at 742.5 MHz. Peak return
current reaches 3.07 mA and total returned charge reaches 0.105 pC in these
transitions. The zero-supply final-state check has no VDD backfeed because this
explicit branch returns to ground; it does not qualify missing junction paths.

Keep **charge reduction plus branch-local protection** as the design direction.
Do not choose the favorable 0.4 V knee as a proven GF180 capability or infer a
safe undershoot limit. Real diode/active-clamp behavior, upper-node protection,
leakage, substrate current and control-driver charge remain open. Feed the
recorded clamp-current pulse into the package model before claiming coexistence;
its low average energy does not eliminate transient ground disturbance.

Burst END now requires two consecutive quiet samples. If signal returns after
one quiet observation, the generic record source emits ABORT instead of dropping
the missing sample and joining the remaining data. An electrical one-UI peer
release inside DATA yields no reply; STOP/restart with the same analog pad then
completes a fresh exchange. The FPGA still owns protocol parsing. This verifies
one detected erasure and recovery, not noisy-comparator false-event probability,
full electrical-idle qualification or sampling-phase acquisition. The refreshed
common USB response remains 279.75 ns within the assigned 342.25 ns bound.

The electrical USB receive path now derives raw burst START/END and partial-byte
records from sampled pad signal/squelch observations. It no longer receives the
request length or expected end time to decide when to emit those records. The
same generic assembler handles arbitrary raw lengths; it holds one partial byte
and leaves USB SYNC/PID/CRC parsing in the external FPGA model. Tests cover
partial tails and a delayed burst followed by a second exchange with retained
host/analog state. The serializer's source schedule remains test stimulus and
latency/voltage scoring truth, not receiver control.

This removes the burst-boundary oracle, **not the sampling-phase assumption**.
The electrical fixture still samples at a prescribed 0.4 UI phase and assigns
16/9/12 UI start/data/end pipeline delays from observed events. Multiphase
acquisition, phase tracking, noisy-squelch qualification and their real control
latencies remain open. Do not describe this generic record assembly as on-chip
USB SYNC recognition or physical burst-clock acquisition.

The fast `--usb-trim-envelope` inverse screen now checks one fixed legal
**eight-bit** current code across the common 2.8391–3.0673 V rail bound and
independent ±5% local/peer 45-ohm terminations. It reads code resolution from
`usbhs.config.current_code`, retaining the existing 0.8–1.2 trim range. The
0.36–0.44 V interval remains an illustrative settled-level gate, not a standards
mask. With 1 kohm output resistance and +0.5/V supply sensitivity, even maximum
trim spans about 0.3519–0.4443 V: no code meets both limits. The corresponding
single packet's 0.3721 V minimum therefore cannot establish bounded coverage.

**Keep the trim range; target absolute low-frequency fractional supply
sensitivity no greater than 0.2/V at the current source.** Assigned ±0.2/V cases
admit codes across the tested 250-ohm, 1-kohm and 5-kohm output resistances with
roughly 10 mV or more settled-level margin. This is a provisional circuit
requirement, not characterized GF180 performance or a continuous physical
uncertainty proof. Improve reference isolation/regulation or board rail quality
if the source cannot meet it; do not assume calibration removes time-varying
supply coupling. Dynamic PSRR and transition extrema remain separate gates.

`--usb-common-packet` now derives pad-supply forcing from the USB 252.2 mA
inventory, both 100 MHz host directions and the shared five-node package model
(0.25 nH return, 0.2 nH die-capacitor ESL, selected 6 pF external host loading).
The full HOST DC allowance remains charged. Summed host-harmonic magnitudes bound
the rail at 2.8391–3.0673 V around 2.9532 V. A 72-bit request produces a physically
sampled 48-bit reply through chip-owned direct queues, with 38-bit peak staging
and a 279.75 ns scheduled port response under assigned capture/output delays.
Two integration limits, 104.17 ps and 52.08 ps, agree on packet/timing results and
voltage margins; source-work balance residual stays below 2.2e-22 J.

The same packet now compares the ideal current-source control with an explicit
finite-source hypothesis: 1 kohm output resistance, 0.5/V fractional supply
sensitivity referenced to 3.3 V and 0.4 V pad voltage. Under the common ripple,
minimum sampled TX differential voltage falls from 0.400 V to 0.3115 V without
trim. Applying the existing maximum 1.2 current trim raises it to 0.3721 V. All
three decode the diagnostic reply; that does not establish electrical compliance.
The external peer remains independent and its RX margin stays 0.400 V.

**Retain existing current trim and require calibration at the actual board rail
and load.** Its range mitigates this assigned case, but does not prove coverage
of real output resistance, supply sensitivity, termination tolerance or all
voltage extrema. These source parameters are uncertainty probes, not GF180 data;
the model assumes instantaneous sensitivity and omits reference-loop dynamics.
Independent loaded-equilibrium and energy checks cover the finite-source law.
Receiver-threshold shifts and capture/output delay remain assigned. The screen
includes host harmonics only, not core/timing switching or signal-dependent
pad-load feedback, and starts from prequalified zero-delay startup. It does not
close the complete USB lifecycle or package gate.

The chip-owned USB packet path now accepts an explicit time-dependent pad supply.
The retained four-node network integrates both capacitor state and source work
using the instantaneous rail; STOP/fault output release uses the same supply
binding. A maximum integration step is mandatory for callable rails, and forcing
discontinuities must be split at event boundaries. Tests exercise consecutive
packet exchanges with assigned 2.9532 V ±80 mV, 1 MHz ripple and retained host
credits. A separate severe 50 mV supply control prevents physical reply decode
instead of inheriting ideal serializer success; this is a failure control, not a
brownout threshold or automatic monitor qualification. State-split and energy
checks cover the dynamic solver. This supplies the connection for common PDN
trajectories; actual USB signal-dependent load feedback and supply-induced
capture/output timing remain unjoined. The packet sampling phase is still assigned.

USB now uses its own 252.2 mA inventory allocation in the common DC package
network, rather than borrowing the wired 268.45 mA operating point. The standalone
shared-pad report uses 2.9532 V for USB versus 2.9030 V for serial/TMDS under the
same lower-return package hypothesis. Its 100 MHz host setting retains the full
allocated host current; no unproved inactivity savings are taken. Per-stage rails
and the USB owner-current/power ledger are recorded. This closes a DC assumption
mismatch, not dynamic USB package feedback: the rail change is imposed and local
signal-dependent load remains within an assigned current ceiling. USB clock
qualification and integrated direct-service timing under supply ripple remain open.

The connected serial/TMDS/isolation/USB sequence now uses finite command latency
and a positive break-before-make interval. Explicit external sources and peer
passives survive; the four analog node voltages are integrated through the wait,
not reset at mode changes. Output drive stays released after the new mode connects.
The refreshed shared-pad report records each break/make boundary. Its maximum
energy-balance residual is about 1.1e-22 J in this fixture. This checks numerical
accounting, not safe transistor stress. Illustrative 2 ns command delay and 3 ns
dead time remain assigned; reset isolation uses zero command delay. Switch edges
are atomic, with injection, control skew, slew and dynamic rail feedback still
open. Legacy mode-dependent USB peer shorthand is rejected across this sequence;
explicit board sources model active remote drive without local control over it.

## Model assumption audit

Converter-derived qualification now supports independent observation-age bounds
for the reference and supply channels. It uses actual quiet-recovery, acquisition,
comparator-decision and supply observations from the SAR trace, with explicit
expiry evaluations. Fresh supply samples cannot keep an old reference reading
valid. A focused composition feeds those computed events into BehavioralChip:
readiness becomes active only after valid converter observations and traffic
faults when reference coverage expires despite continuing supply samples. Its
zero startup guard isolates this connection; it does not qualify physical startup.
The retained SAR transport entry exposes `qualification_max_age_s` for the same
logic. Calls without an age remain legacy held-event controls. A selected monitor
cadence and full lifecycle with that bound still need integration.

Analog qualification can now declare a maximum observation age. Unchanged valid
readings refresh age, but missing samples do not. Expiry blocks startup, restarts
the continuous-valid guard when observations resume, and faults active direct
traffic at the coverage boundary while releasing its output. Later good samples
cannot erase an earlier unobserved interval. Focused tests exercise these cases.
This is an observation-coverage contract, not a fabricated monitor/watchdog.
Legacy event fixtures without an age bound retain held-state semantics and must
not qualify live physical readiness. Selecting monitor cadence, thresholds and
observable quantities, then connecting those readings across the canonical
lifecycle, remains required.

The current models mix predicted trajectories, supplied envelopes and control
contracts. A passing contract does not establish the physical input it was
given. The following dependencies limit the conclusions we can draw now.

| Model / source | Predicted or checked | Supplied or idealized | Conclusion that depends on it |
|---|---|---|---|
| `architecture_fast/timing_services.py:WarmHop` | Ordered states, epoch/deadline rejection | source_qualified, gain_settled, samples_flushed, prefilled and supply_ok booleans | A50us sequence is conditional on those observations; it does not predict oscillator/filter lock or analog settling |
| `architecture_fast/receive_qualification.py` | Quiet/acquisition/holdover policy and phase-integral bounds | phase_qualified and post-tracking residual-frequency trajectory | CDR policy and holdover arithmetic do not establish physical loop acquisition or SSC tracking |
| `verification/usb_selected_timing.py` | Causal parser/reply selection, finite CDC/credit schedule, optional chip-owned lifecycle and retained shared-pad voltage sampling | Ideal FPGA capture, assigned acquisition pipeline and sampling phase, observed squelch burst boundaries, supplied pad-rail waveform, bounded output delay | 342.25ns remains an assigned-envelope response bound; voltage-derived packet decode and fault recovery do not establish USB acquisition, package or RTL timing |
| `connected/protocol_pad.py` | Lumped voltage/current/energy equations, branch capacitance and explicit finite clamps | Fixed capacitances, abrupt state application, assigned clamp thresholds; omitted nonlinear devices and distributed package | USB pad fixtures do not establish fast serial/TMDS compatibility, ESD or power-off tolerance |
| `verification/external_wifi_reference.py` | Independent legacy packet decode and finite host exchange | Assigned LO/converter noise, PA law, calibrated power mapping and recovery envelope | Legacy decode supports waveform behavior under those assumptions; the recovery admission bound is not simulated transistor overload recovery or complete HE interoperability |
| `verification/rf_power_calibration.py` | Inversion, IQ fits, sample peak checks and optional validity gate | Measured/synthetic points, context, drift/age/temperature bounds supplied externally | Fit quality does not establish instrument accuracy, held-out performance or field calibration validity |
| `architecture_fast/resource_configuration.py:validate_host_service` | Rate/latency/queue arithmetic and board-rate rejection | Guaranteed board rate, maximum service latency and recurring-stall envelope | Conditional admission is not GPIO characterization, an actual scheduling guarantee or direct-stream integration |
| `verification/recovery_mailbox.py` | Atomic request, shadow discard, retry identity and management-clock handoff | Caller delivers management edges and backend completion; CDC is a bounded-stage abstraction | Recovery does not yet prove brownout behavior, metastability, independent oscillator startup or target reset release |
| `architecture_fast/rf_quality_budget.py` | Allocation sums, sensitivity and support-budget deductions | ENOB/error allocations, current ceilings, capacitor density and recovery time constants | Budget pass is not noise, silicon current, area, dynamic headroom or yield evidence |
| `analog-architecture.json` and generated diagram | Block/net/control/storage consistency | Proposed topologies, input-test selectors, reset/protection and resource ceilings | Connectivity/diagram checks do not implement switches, observe faults or demonstrate manufacturability |

Keep distinctions in reports: **computed trajectory**, **checked control
contract**, **supplied performance envelope**, or **unimplemented requirement**.
Changing an analog parameter or source file invalidates affected evidence until
matched rerun/review; hashes of a few entry files alone do not cover transitive
dependencies. Do not label a disconnected component test a whole-chip result.
Retained package/reference-feedback trajectories are stronger than frozen-rail
fixtures, but still inherit the assigned package, current and device laws.

Highest-impact unearned assumptions are physical clock quality, RC/filter
internal headroom and settling, converter/reference accuracy, shared-pad
loading/protection, and real FPGA service. Replace their optimistic bounds with
coupled uncertainty ranges before adding more nominal packet seeds. Calibration
and readiness gates should consume independent measurements or modeled sensor
outputs, not the desired outcome of the same test.

## Common RF packet configuration

The common-envelope packet entry now obtains its PGA code set and ceiling from
the current analog inventory:−6..42dB in3dB steps, starting at39dB. Its received-code
AGC queues only supported settings; analog settling remains continuous between
them. A prior packet fixture inherited a60dB continuously programmable PGA from
an exploratory helper. That fixture is incompatible with this design and cannot
qualify it, even where its packet decoder passes. The current report replaces
that entry rather than retaining it as another normative configuration.

`selected_revision_check.py --common-rf --rf-filter ...` uses the same current,
package and host-loading catalog as `--common-envelope`, at the packet's actual
2426MHz channel. It compares the existing finite-zero and all-pole filter
settings without changing physical block count, gain range or blocker strength.
Each filter result retains its own source manifest; rerunning one component does
not silently refresh evidence for another. The all-pole setting has now acquired
and CRC-decoded the−80dBm wanted request with a−50dBm PRBS15 GFSK blocker at+2MHz,
with converged reference feedback. Applied PGA gain stays between39 and42dB;
no PGA samples clip. Maximum asynchronous conversion time is about16.00ns,
within18ns, and evaluated converter supply spans2.732..3.157V. This is one
conditional operating point, not a sensitivity or PER result. The matched finite-zero case also converges but fails acquisition.
Keep both coefficient families in the same hardware; choose the all-pole setting
for this demonstrated narrowband point. The result does not justify weakening
wideband close-offset rejection or claiming all blocker/channel combinations. The RF entry exercises acquisition,
code-driven gain, asynchronous SAR and reference-load feedback; it does not yet
close RF TX, Wi-Fi, calibrated lifecycle or sensitivity/PER acceptance.

Normal sampled-RF startup now rejects nonzero ADC diagnostic selection even
when that selection is changed after a stream is attached or resumed. Rejection
preserves stopped state, epoch and analog history; restoring normal input permits
startup. Diagnostics continue through the retained SAR adapter. This closes a
configuration-order hole that could otherwise silently sample the normal source
while diagnostic controls claimed an internal source. Automatic diagnostic
scheduling and loading remain integration work.

## Converter deadline decision

Diagnostic quarter-reference inputs now have an optional effective source-load
capacitance per lane. Their charge demand is debited from the retained reference
at acquisition end, before SAR decisions, and subsequent recovery feeds the
existing source-current trace. Normal input and internal zero do not incur this
quarter-reference load. Zero capacitance is explicitly an ideal-load control.
The stopped zero → quarter-reference → normal lifecycle test now uses 0.25 pF
per lane and retains charge through transitions.

In a 64-conversion, 3 V rail/1 V reference diagnostic control, 0/0.25/1 pF per lane
requires approximately 95/114/170 uA average recharge current, excluding the 2 mA
reference bias. Minimum reference voltage changes from 0.9785 to 0.9751 to
0.9604 V. Charge-conservation and lane-selection checks pass. These are assigned
sensitivity points, not selected physical capacitances or common-envelope closure.
The source demand is a lumped charge packet, not a continuous acquisition/source
network; source impedance, static divider/buffer current, ratio mismatch and
switch injection remain open. Ratiometric diagnostics still cannot establish
absolute VREF. Budget their load before interpreting successful calibration codes.

The shared-envelope converter now exposes actual per-bit comparator overdrive,
including acquisition error, DAC/reference state and assigned comparator noise.
An inverse exponential-regeneration screen checks whether those decisions can
finish in the allocated0.5ns, assuming100ps launch and200mV output threshold.
These are explicit test hypotheses, not GF180 parameters.

For the selected lower-return case,25ps regeneration gives no unresolved
comparisons in10,240 trials. At50ps,61 comparisons in58 of512 paired conversions
miss the deadline;75ps gives830 misses and100ps gives2,610. The combined-loading
case also misses at50ps (55 comparisons across52 paired conversions). Zero
misses in a finite fixture is not a probability bound. The ENOB result from ideal
sign decisions cannot qualify any hypothesis with unresolved comparisons.

**Keep the single-core asynchronous SAR.** The common-envelope runner now
reruns reference recharge at actual variable decision times, retaining the
unequal DAC-settling allocation and18ns conversion ceiling. With50ps regeneration,
the selected case reaches8.56/8.76ENOB and completes within15.98ns;100ps reaches
8.53/8.78ENOB within17.63ns.150ps exceeds the conversion deadline and is rejected.
This establishes a useful conditional success/failure region, not GF180 speed.
The0.5ns fixed-slot screen above is a counterfactual when asynchronous timing is
selected, not a requirement that each asynchronous decision meet that slot.

The paired fixture waits for the slower I/Q decision; real independent
sequencing or completion-handshake cost must still be resolved and included.
The snapshot-input regeneration law, launch delay and omitted kickback remain
assumptions. Retain the18ns external latency ceiling and do not reallocate the
observed timing headroom. The maintained `--converter-timing` cross-check now
combines 150 fF diagnostic input loading, 300 ohm added sampling resistance,
100 ohm reference source, 0.5 mA reference limit and 2 mV comparator noise with
actual asynchronous decisions and shared clock/reference-current feedback.
At 50 ps regeneration it reaches 8.13/8.23 ENOB and 15.91 ns maximum conversion;
at 100 ps, 8.09/8.21 ENOB and 17.68 ns. Both converge; 150 ps is rejected for
exceeding 18 ns. The fastest-rate schedule has only 0.358 ns remaining after
its existing guard and delivered-clock variation. This supports retaining the
architecture conditionally, but the stressed precision margin is only 0.09 bit
and the 100 ps completion margin only 0.323 ns. Do not spend either margin.
The two loading points are assigned hypotheses, not a continuous uncertainty
bound. Diagnostic reference-source switching, mismatch, kickback, rare near-zero
overdrive and complete RF packets still need this combined timing model.
See the [converter decision](power-partition.md) for the maintained assumptions.

## Common wideband RF decision

The maintained `--common-wideband` acquisition control uses the same RF inventory
and package catalog as the narrowband case: 230 mA, 6 pF host load, 0.25 nH return
hypothesis, 2426 MHz external carrier, selected diagnostic loading and asynchronous
SAR. PGA gain is fixed at the legal 42 dB ceiling. The RF waveform, noise,
nonlinearity, filtering, converter decisions and reference-to-clock feedback run
together. The source contains legacy training followed by diagnostic coded HE20
DATA; it is not a standards-valid HE packet. It retains fixed gain and known DATA
training, with no AGC or HE interoperability claim.

At −85 dBm wanted and −30 dBm blocker at +12 MHz, legacy training is acquired but
payload CRC fails. Reference feedback converges. The converter's maximum actual
completion time is about 16.15 ns against 18 ns, peak reference current including
bias is about 2.42 mA, and its evaluated rail spans 2.732–3.158 V. No PGA samples
clip during the source waveform; nine initial settling samples clip. Thus the
current failure is an end-to-end quality/acquisition problem, not an observed
converter deadline or reference-current failure. Timing success does not justify
increasing gain beyond the inventory or claiming the −85 dBm operating point.

At −75 dBm wanted with every other selected setting unchanged, acquisition and
exact payload/CRC recovery succeed with converged feedback. Maximum conversion
time is about 16.18 ns, still below 18 ns; one source-waveform PGA sample clips.
These two fixed-seed points establish a useful conditional path and a failed
weaker point, not a sensitivity threshold or PER curve. Keep the present block
set as a candidate; address weak-signal quality through the gain/noise/filter/
converter budget and FPGA receiver assumptions before claiming the weaker case.
Do not add hardware merely to recover the obsolete 54 dB fixture result.
Reproduce with `--common-wideband --wideband-wanted-dbm -85` or `-75`; each result
is retained under its own source manifest. The −85 dBm run predates only the
runner's wanted-level option; its physical-model sources match the comparison.

Earlier 54 dB fixed-gain packet results cannot qualify the selected PGA. Preserve
that distinction when using exploratory gain sweeps. The current model exposes
legal gain codes, inventory converter parameters and comparator timing explicitly;
unsupported requested gains are rejected when the inventory is supplied. The
shared frontend still uses assigned NF/IIP3 and ideal filter internals. Results
retain separate source manifests, including failed cases; they are conditional
operating-point evidence, not sensitivity/PER or silicon qualification.

## Common RF transmit decision

`--common-tx --tx-rms-codes 250` uses the same 230 mA RF inventory,
6 pF host load, 0.25 nH return hypothesis and 2426 MHz external source as the
common receive cases. Reconstruction uses the selected 18 MHz ceiling and
nominal driver gain 5.36. Amplitude is an explicit FPGA complex RMS 12-bit
transport-code request, not a native-code peak setting. The DAC remains a
10-bit/assigned-8-ENOB model.

The port now includes the driver's 40 ohms plus the inventory RF-pad resistance
of 2 ohms per leg, driving 50 ohms differential. At250 RMS codes it produces
**−0.351 dBm**,3.87% diagnostic EVM and0.343 V peak mixer input. Current clipping
is absent and assigned voltage/current/energy checks pass. The0 dBm target fails.
The matched bare-driver result would be+0.027 dBm: the four-ohm addition costs
20log10(90/94), approximately0.378 dB. The regression checks the corresponding
loaded-power ratio and current/compliance calculation together. Bare-port
results in older manifests do not qualify this selected physical path.

**Keep FPGA scaling and programmable driver gain, but keep0 dBm open.** Only
6.6 mV remains below the0.35 V mixer-input limit at this waveform amplitude.
The existing driver-gain range offers a possible mitigation, but increased gain
must be evaluated with current, headroom, quality and reactive RF loading together.
Do not silently absorb pad loss into driver impedance or borrow mixer swing.

Pad capacitance, signal-bond inductance and reactive matching are screened below
and included in one compensated waveform case. Signal-dependent current feedback
and physical DAC glitches also remain absent. Bias is warm and
constant. EVM uses known DATA training and ideal framing; broad spectral bands
are not protocol masks. Neither power arithmetic nor diagnostic decoding
qualifies complete HE transmission. Each amplitude result retains its own source
manifest; an older case without pad resistance is not a matched current case.

The fast `--rf-output-load` screen adds a differential source-R/pad-C/bond-RL/
50-ohm-load ladder. The1pF-per-leg inventory pad becomes0.5pF differential.
Signal-loop inductance is varied independently of supply-return inductance;
0.4ohm signal-bond loop resistance is an assigned hypothesis. It extrapolates the
recorded250-code waveform over carrier±10MHz rather than rerunning its transient.

| Signal-loop hypothesis | Approximate existing-gain power | Required8-bit gain setting | Necessary current/headroom checks |
|---|---:|---:|---|
| 0nH | −0.526dBm | 5.701 | Fit |
| 1nH | −0.434dBm | 5.638 | Fit |
| 4nH | −1.517dBm | 6.400 | Fit, little headroom |
| 8nH | −4.364dBm | 8.878 | Outside selected range; fails |
| 8nH plus ideal external series compensation | −0.538dBm | 5.722 | Fit |

The matched example uses0.538pF differential series capacitance, resonant with8nH
at2426MHz. A symmetric realization would use approximately1.076pF per leg before
including component/board parasitics. This is an illustrative electrical target,
not a selected part value or validated assembly. ESR, tolerance, self-resonance,
external voltage stress and actual bond topology remain open.

**Retain two board-level paths: a sufficiently low-inductance RF route with gain
trim, or characterized external matching with gain trim.** Do not increase the
on-chip gain range from these estimates. The4nH uncorrected case already reaches
its6.4 limit and nearly consumes modeled headroom; the8nH uncorrected case needs
a changed load network. These are several conditional ways to proceed, not proven
power closure. Gain-dependent noise/linearity, full-waveform reactive currents,
sidebands and transients must be joined before accepting any row. KCL and real
power balance are tested independently, including the compensated ladder.

The compensated8nH route now also has a full-waveform RLC result. With250 RMS
transport codes,0.538pF differential series compensation and the existing8-bit
gain setting5.72235, the common TX path produces **+0.043dBm** and3.87% diagnostic
EVM. Sampled driver current peaks at21.1mA against28mA; pad voltage peaks at0.989V
and the external matching-capacitor voltage at2.38V. Mixer input remains0.343V.
Assigned source-headroom and sampled energy/current checks pass. The resistive
precheck is stored separately from actual reactive-load current and power.

`rf_pad_waveform` evolves physical capacitor/inductor state in the rotating
complex-envelope frame, with exact updates for held envelope intervals. It
includes source startup and tail, returns retained state, and agrees with the
independent carrier-frequency circuit solution, split-call continuation and
subdivision of identical held input intervals. It is not a circular FFT replay.
Reproduce with `--common-tx --tx-rms-codes 250 --tx-signal-loop-nh 8
--tx-series-match-pf 0.5379831620795082 --tx-gain 5.72`.

**Keep external matching plus existing gain trim as a credible candidate route.**
The0.043dB power margin and6.6mV mixer margin do not establish robustness. Matching
ESR/tolerance, actual bond/pad uncertainty, driver stability/current law,
between-sample peaks and signal-dependent supply feedback remain unresolved.
Current-limit exceedance rejects the linear-network run rather than pretending
an independently clipped resistive waveform models reactive limiting. Physical
packaging, emissions and complete protocol qualification remain open.

### RF matching uncertainty decision

The fast output-load screen now compares one fixed nominal capacitor with
per-board matching adjustment across assigned 6.4–9.6 nH signal-loop inductance,
0.4–0.6 pF differential pad capacitance, 0.2–1 ohm series loss and three carrier
points spanning 2.4–2.5 GHz. Each case checks the carrier ±10 MHz. Matching is
chosen at 2.45 GHz and held fixed across channels on that board.

With ±10% capacitor error, fixed matching requires gain up to 6.845, exceeding
the selected 6.4 ceiling; its worst estimated current is 28.76 mA, above 28 mA,
and source swing also fails. Assuming measured loop inductance and ±2% residual
matching error, per-board adjustment requires gain 5.616–5.934. All sampled
points satisfy the necessary gain, source-swing and current checks; worst current
is 23.20 mA and source peak 1.948 V. This is a frozen-waveform narrowband screen,
not statistical yield, a continuous bound, a full-band coupled simulation or
proof that the required matching accuracy can be measured and achieved.

**Select board-adjustable matching provision plus existing gain calibration.**
Keep the chip gain/current allocation unchanged. Before closing output power,
run adverse matched cases through the causal waveform and shared supply model,
and qualify measurement uncertainty, reactive stability and emitted quality.
External PA support remains optional and does not satisfy the chip's 0 dBm gate.

## Causal CDR continuity decision

The selected CDR uses a 96-bin finite phase detector: 97 local boundary
samples plus DATA, with the separate gated burst-acquisition bank retained.
The encoder rejects missing brackets and nonmonotonic codes; no transmitted
labels or exact channel-crossing timestamps enter feedback. Its 128-phase
observation grid spans 0.75 UI. Feedback gains are 0.04 (phase), 0.0003
(frequency) and 5e-7 (frequency slope). Actual commands use 1 ppm period
steps and a 4096-step phase grid, including carried rounding residue.

`cdr_periodic_tracking` is an optional generic serial receive configuration,
not a protocol profile. Ordinary reception keeps a 1024 UI acquisition timeout.
Periodic acquisition permits 1,000,000 UI and reserves the existing framed
host service without changing its clock or epoch. The FPGA stores 128 local
observations (1280 bytes), fits the periodic clock using 96, and validates on
32 withheld observations. The model charges 32 us computation and bounded
framed observation/coefficient transport. Two frame intervals are reserved in
each direction; actual configured host rates determine latency. The 64-byte
fixed-point coefficient command reuses the ingress FIFO; observations reuse
egress. The command becomes active atomically, only followed by readiness
after a fresh local validation. A mismatch invalidates reception. Once prediction is active, it replaces the
ordinary slope extrapolator; retaining both integrated detector noise into an
extra frequency ramp during gaps. Phase and frequency feedback stay active.

The unchanged tracking targets are 50 ppm and 0.0625 UI. A passing acquired-state
trajectory does not establish cold acquisition, changed modulation, arbitrary
slew, actuator delay or a complete jitter mask. The 125 ppm internal holdover
allocation remains distinct. Required detector noise is 0.5 ps RMS and supply
sensitivity is 0.0025 ps/mV with a 1 GHz pole. The 96 ps CTLE pole is retained.
Sampler/encoder current, loading, area and the fine actuator are implementation
obligations; the old resource allocations do not prove this larger bank fits.
The coefficient transport is a bounded service model, not a completed wire ABI.

Selected tracking evidence is recorded under `selected_cdr_tracking` in
`evidence/selected-revision-check.json`, with per-campaign source hashes.
Earlier comparison entries describe historical designs, not the current selection. The selected run
passes both seeds 9024/9025 and SSC phases 0.217/0.317: peak frequency
residuals are 37.0561 and 42.1691 ppm, with zero scored bit errors and no
qualification losses. Each source contains 430,000 bits, 5000 ppm downspread
at 30 kHz and 512 UI transition gaps; scoring covers the final 79,800 bits.
Initial coarse frequency is assigned. Prediction becomes active after about
138 us; this is acquired-state evidence, not cold-start timing or a universal
50 ppm guarantee for arbitrary source slew. The separate deterministic-phase
and physical-jitter requirements remain broader than these sampled checks.

### Retained wired recovery integration

`--joint-wired-recovery` now completes all seven RF/wired/RF stages with wired
RX loss, host observation and rearm inside the retained chip/package/converter
composition. The helper explicitly selects the wired host rate; inheriting the
previous RF rate caused an observed FIFO overflow and was corrected. The selected
1,024-bit ingress allocation is used. The CDR retains the continuing peer through
7,664 discarded words and delivers 6,502 words after rearm; all six adjacent
converter-state boundaries match and stage times remain ordered. The later
reference-loss and RF recovery also complete. Evidence is
`selected-lifecycle.json:joined_wired_recovery`.

This is wired **RX recovery**, with conservative wired-mode power allocation;
simultaneous wired TX during recovery is not exercised. Status publication and
polling are transaction-level assumptions, recovery commands are model calls,
and host quarantine is budgeted rather than implemented. Receiver-decision
agreement is not independent BER or protocol alignment. The nested helper's
historical steady-load scope text is superseded here by its explicit
`rail_source=retained_parent_trajectory` and the parent composition.

RX DATA EVM spans 7.62–10.46% in this schedule (initial 8.72%); TX remains about
−0.081/−0.082 dBm. The different delay changes disturbance phase and converter
history, so the earlier 7.25–9.02% range is not a bound on all recovery schedules.
Keep the broader observed quality range and the unmet 0 dBm power goal visible.
This closes an important lifecycle composition gap without qualifying RF quality,
target protocols, physical fault timing or a package-derived supply envelope.

The fast `--analog-envelope-summary` command consolidates both recorded joined
schedules without rerunning them. For the matching imposed 9.6 mV envelope,
the observed union is RX EVM 7.25–10.46%, TX EVM 3.26–3.40%, and TX power
−0.08245 to −0.08096 dBm. Source traces and their original code hashes remain
attached; this is not a controlled phase sweep or a continuous bound. The worst
RX observation contains only 468 held-out bits with known DATA training and no
real preamble acquisition. Zero errors there cannot establish a packet-error or
bit-error target. `analog_operating_summary` is the numerical summary owner;
individual traces remain the evidence owners.

**Next analog decision:** define target-level quality acceptance and test the
common local-rail requirement over arrival/phase/history variation before
selecting regulation or gain. Do not pursue another nominal gain or recovery
variant while those two acceptance gaps remain. Keep the rejected package/source
combinations separate from imposed-ripple success cases: no external regulator
or passive network has yet produced this local envelope in the combined model.

## Independent wired peer configuration

`SharedWiredPad.set_peer_passives` now separates external pulls/termination from
local speed/role changes. Explicit peer branches survive local reconfiguration;
disconnecting them is an explicit peer action. They are fixture controls, not new
chip commands or pins. This removes an assumption that could hide incorrect USB
negotiation ordering: earlier convenience fixtures automatically changed the
remote termination with the local speed. Those fixtures remain convenience
controls until migrated, not independent-peer lifecycle evidence.

The existing `usb_pad_lifecycle` is now migrated for both host and device roles.
It retains explicit FS peer pulls while the local side changes to HS; the resulting
0.873/0.798 V differential is rejected against this fixture's 0.4 V target. Only
an explicit peer termination change restores the expected swing. Both directions
then decode the stuffed NRZI payload through finite pad voltage and return to
squelch. This negative control prevents synchronized convenience configuration
from masquerading as successful electrical handoff.

Reproduce with `selected_lifecycle.py --wired-peer-controls`; evidence is
`selected-lifecycle.json:independent_usb_pad_lifecycle`. Durations and 0.4 V checks
are fixture requirements, not a complete standards acceptance envelope. The peer
change is still scripted, not caused by observed chirp negotiation. Shared package,
actual command transport, independent burst CDR and host-delivered packet exchange
remain to be joined. No USB capability verdict is promoted from this component.

The same command now also runs the existing finite packet/host response model
with explicit 45 ohm peer termination and a 15 kohm negative control, for both
host/device roles. Actual pad samples feed record transport, FPGA-side packet
parsing and ACK generation, then queued playback. The eight-byte DATA stimulus
is delivered in both cases: the negative control still decodes at about 0.798 V,
so packet success cannot qualify electrical levels. A separate illustrative
0.36–0.44 V swing check accepts only the correctly terminated fixture.

At selected 312.5 Mword/s, modeled response latency is 337.5 ns against the
fixture's 400 ns budget; 250 Mword/s gives 437.5 ns and fails. This preserves a
real service constraint instead of hiding it behind successful decoding. These
are matched component/transport results, not a complete USB transaction or
selected-chip proof: acquisition uses prescribed peer-centered sample times,
clocks are warm, peer negotiation is scripted, storage/record transport needs
reconciliation with the selected implementation, and package/CDC/command errors
are absent. Keep full-rate host service and independent electrical validation;
next connect recovered sampling and selected transport rather than add payload
length variants. Results live under `independent_usb_pad_lifecycle.packet_transport_controls`.

The packet control now explicitly uses the selected 1,024-bit ingress/playback
allocation instead of the adapter's default 2,048 bits. The short ACK reaches only
36 queued playback bits at 312.5 Mword/s (30 at the failing slower rate), with
unchanged electrical/deadline results. This supports keeping bulk storage on the
FPGA for this workload; it does not bound longer bursts or total chip memory.
The evidence now identifies and hashes its `TimedRecordReturn`,
`TimedRecordPlayback`, `bit_event_codec` and block-FIFO dependencies. The adapters now use the canonical `stream_codec.Receiver` with explicit
raw-record interpretation and an ordered event interface. Their CDC/scheduling
and acquisition/STOP/epoch behavior remain separate from `BehavioralChip`.
**The next integration must close those remaining gaps, not equate a shared parser
with selected-chip lifecycle evidence.**
Other staging, CDC and metadata storage still require full resource accounting.

## Joined wired TX decision

Keep the selected serializer/channel/equalizer composition provisionally and
stop expanding nominal serial fixtures. `selected_lifecycle.py
--ownership-wired-electrical` connects 2,600 actual emitted bits, including
assumed zero prefill, to the loaded channel and an independent peer CDR.
Both nominal and `--ownership-stress` runs decode all 1,300 held-out bits,
with every held-out bit qualified. Serializer word boundaries agree with actual
consumption timestamps. The selected local RX has only the deliberately induced
transition-drought loss in both runs.

This closes a model connection, not the wired electrical gate. Driver amplitude
uses the retained rail held per bit; the stress case changes by at most 1.51 mV
between adjacent bits. That is not a continuous-noise convergence proof. Clamps,
current-steering headroom, driver current feedback, idle/detection/OOB and
protocol recovery remain outside this join. The stress variant also uses
wideband RF rather than the nominal tone: its RX EVM remains 19.9–25.8%.
Lifecycle completion therefore cannot be called whole-chip signal-quality success.

The architectural priority remains the common supply/timing envelope and useful
RF quality/power, followed by one representative pad/control lifecycle. Do not
interpret the finite serial result as a BER bound or spend the next pass extending
its passing bit count. Reproduction and per-section source hashes live in
`evidence/selected-lifecycle.json` under `ownership_wired_electrical_trace` and
`ownership_wired_electrical_stress_trace`.

## Whole-chip reassessment after the first live RF exchange

The initial evidence at this checkpoint was a causal LE 1M request/reply through actual host
words and retained analog state. The default transport-only variant does not make the wired branch equally
complete: without the wired integration options, `ownership_load_trace` supplies wired RX with deterministic
10-bit words on an independent ideal peer cadence. It bypasses the pad/channel,
CDR acquisition, loss of lock and recovered-word validity. Wired TX payload
checking similarly does not establish its electrical waveform. Keep these
transport demonstrations, but never describe them as joined wired PHY evidence.

`selected_lifecycle.py --ownership-wired-cdr` now connects the existing
`wired_envelope.physical_receiver` to the selected seven-stage lifecycle. The
loaded 100 ps driver/2.7 pF receiver sees the same retained rail/gain and aperture
delay trajectory. A causal CDR, initialized with +100 ppm error against an
independent 2.5 Gb/s peer, supplies event times and decisions; all ten bits must
qualify before a word enters the finite host queue. Invalid words still advance
the receiver. Source bits are used only for stimulus and offline scoring.

The first joined case accepts 598 words and rejects 221, with nine qualification
losses. Of the accepted words, 547 reach the host before the capture ends and
51 remain queued; the 4,560 held-out delivered bits have zero observed errors. It delivers no accepted words in the interior of the injected 400-bit
transition drought and resumes afterward. These are raw random-NRZ diagnostics,
not continuous protocol service: losses outside the deliberate drought must stay
visible. Qualification is not framing, and an offline fixed lag must never become
an alignment oracle. The next wired decision is whether actual transition-bounded
encoded traffic maintains lock/service and recovers its word boundary. Reuse this
joined path instead of creating another isolated CDR fixture. Wired TX electrical
waveform and protocol-specific pad/OOB/idle/detection remain open.

**Selected receiver composition correction:** the initial joined CDR adapter
omitted the CTLE already selected in `power-partition.md`. Its encoded/noise
results therefore characterize the **unequalized control**, not the normative
receiver. The canonical requirement is now in
`contract.json:physical_services.wired_receiver`: unity DC gain, 200 ps zero,
80 ps pole, 10 mV RMS post-equalizer disturbance, 20 mV offset and 5 ps detector
noise, inside the existing WIRE RX/timing allocations. No threshold is relaxed,
noise hypothesis reduced or new block added.

| Joined encoded case | Extra qualification losses outside injected drought | Delivered words | Held-out delivered bit errors |
| --- | --- | --- | --- |
| Unequalized control | 8 | 641 | 0 / 5,490 |
| Selected CTLE | 0 | 716 | 0 / 6,050 |

The equalized suppression-only diagnostic loses qualification once, at bit 4065
inside the 400-bit drought, and reacquires. Its host pattern still misaligns after
the loss because silent deletion is not a recovery protocol. The selected
fault-on-loss variant instead stops at word 406 (349 words delivered), rather
than word 62 in the unequalized control. This is the intended rejection; a
post-fault host flush/rearm/protocol alignment remains to be joined.

**Keep decision:** retain the already-selected equalizer and fault-on-loss.
Qualify their physical joint bandwidth/noise/headroom/current and uncertainty
margin rather than infer a new noise requirement from the bypassed equalizer.
The earlier zero/half-noise attribution remains an unequalized diagnostic only;
neither a zero-noise implementation nor a lowered qualification threshold is
selected. Reproduce with `--ownership-wired-equalized`, optionally adding
`--ownership-wired-fail-closed`; evidence sections have corresponding names.
A regression now checks that the selected joined composition has no unintended
loss in this finite trace, guarding against another omitted-block comparison.
This is not arbitrary-payload BER, electrical interoperability or a physical CTLE
proof. Stop nominal CDR tuning here and return to the common envelope and wired
TX/pad/control path.

The common physical uncertainty envelope remains priority one. The next useful
wired step is encoded traffic and explicit frame/lock recovery; further nominal
RF packet variations are paused.
A review also removed an accidental RF preparation block from the independent
wired TX helper and made the legacy RF diagnostic filter settings explicit.
A direct wired TX loss/restart regression now covers the previously broken
helper; its ideal-clock test does not validate analog timing or the full legacy
runner. Historical source hashes are not refreshed by that fix.

## Next architectural gate: join signal quality to the retained lifecycle

The lifecycle and RF-quality studies still prove different things. The
seven-stage lifecycle now transports a wanted RF tone and blocker through the
shared noisy nonlinear frontend, retained RX filter and SAR, with TX reconstruction. `selected_rf.wideband_receive` adds antenna-level
wanted/blocker power, nonlinearity, noise, LO impairment and filtering, but runs
an independent record; its gain search is not AGC and its known DATA training
is not packet acquisition. Neither result proves the other under mode changes.

The shared `receive_frontend` now accepts caller-owned time, rail, LO phase and
persistent noise RNG. The existing wideband receiver uses it. A partitioned
record check verifies identical signal/noise forcing and retained filter output
across arbitrary chunk boundaries. The lifecycle now uses this connection at −65 dBm wanted power, −50 dBm
12 MHz blocker, 42 dB fixed PGA gain, and a 1 MHz wanted tone. Filter state
decays under zero input while inactive; active forcing uses midpoint steps
at at least 320 MS/s. Package delay drives both sample timing and LO phase.
This is a connected signal-path case, not packet or sensitivity qualification. The lifecycle also reconstructs
complete signed I/Q samples from actual 10-bit host transfers, retaining the
partial-sample count and nominal FPGA timestamps. Quality observers must use
this delivered record, not the longer converter/source arrays. Interleaved I/Q noise draws change
the deterministic realization; earlier RF evidence is not refreshed by this
refactor or by regression success.

Reuse those signal-path equations in the retained lifecycle rather than add a
third independent RF bench. One representative 2.4 GHz wideband RX/TX case must
use the same configuration, timestamps, rail/reference trajectory and current
ledger before and after wired operation and reference loss. Keep filter and
converter state across the transition; decode only the words actually delivered
to the host, and drive TX only from words actually consumed. Compare quality
before and after recovery under identical signal and blocker conditions. A
failed outcome is useful if it identifies a necessary architectural change.

This gate requires explicit accounting for the following joins:

- RF waveform bandwidth versus the selected filter: the lifecycle's 1 MHz RX
  and 3 MHz TX settings cannot stand in for the wideband RF case.
- Loaded LO/sample timing versus transport timing: use one trajectory, without
  a second independently generated clock impairment in the quality observer.
- Converter/reference current versus the existing allocations: replace the
  represented load component rather than add it twice; disclose missing loads.
- Finite host queues versus RF observation: missing or stale samples must be
  visible to quality evaluation rather than repaired by an ideal array path.

**Joined wideband result:** `selected_lifecycle.py --ownership-wideband` runs
four HE20 DATA symbols through the same retained lifecycle, with −65 dBm wanted
power and a −50 dBm blocker at +12 MHz. The three RX stages deliver 2,445 complete
I/Q samples each; the first two DATA symbols train an equalizer and the final two
provide 468 held-out BPSK bits. EVM is 5.29%, 5.42% and 5.27%, with zero observed
bit errors, including post-fault recovery. Evaluation uses actual host-delivered
samples and nominal FPGA timing, not hidden analog reference/timing information.
This supports connected RX operation at the assigned point; it does not measure
PER, prove sensitivity, high-order modulation, real preamble acquisition or AGC.
The longer trace uses the same model, not a replacement independent RF fixture.

**TX connection:** the same lifecycle now evaluates actual consumed words
through its retained DAC/reconstruction and the shared mixer/output-driver/port
model. Package history drives LO phase and gain; output distortion, 40 ohm
source impedance and 50 ohm load use the existing assigned model. The 28 mA
driver remains inside the 44 mA RF allocation, not a new current charge. This
covers the active interval with ideal mute at fault/STOP. Its 3 MHz filter and
diagnostic words do not prove wideband TX, spectral masks or physical switching
transients; DAC reference draw and signal-dependent supply feedback remain absent.
The connection enables those questions to be asked of actual host data rather
than an independent ideal TX array. **Current verdict: diagnostic TX payload is
not electrically qualified.** All three TX stages hit the assigned current limit
and fail the voltage-headroom bound. Random/full-scale transport words are not
a calibrated RF waveform. Define an explicit amplitude/PAPR contract and prove
host scaling or generic gain control keeps actual samples inside it, including
reconstruction overshoot and rail uncertainty. Do not silently normalize the
waveform after transport or treat the successful digital lifecycle as TX success.

**TX amplitude decision:** use FPGA scaling before packing, with an explicit
0.35 V peak bound on the complex reconstructed waveform (not RMS or separate
I/Q limits). The shared model bounds output peak by 1.7693 V using maximum
supply gain and minimum supply headroom, versus a 1.9 V allowable peak across
2.5–3.6 V. Compression is not used to claim extra headroom. A conservative
all-history filter bound gives a sufficient native 10-bit complex code radius
of 53 at 1.02 V reference; it is intentionally not the maximum usable signal.
A waveform-specific bound may use more range if reconstruction overshoot and
retained history are included. The FPGA must check the final rounded DAC codes.
Digital backoff costs power and effective resolution; this does not establish
required TX power, EVM or spectral mask. No new hardware is selected. Retain the
full-scale overload case as a negative control instead of silently rescaling it.

**Joined bounded TX result:** wideband mode now transports the same four HE20
DATA symbols from FPGA words through FIFO prefill/alignment, native DAC,
retained reconstruction, shared mixer/driver and resistive load. The host scales
and rounds samples before packing; the native complex-code peak remains within
the conservative bound. At 37.5 MS/s it selects an 18 MHz reconstruction cutoff,
inside the existing Nyquist-limited configuration range. The standalone 20 MHz
TX setting is not silently used at this sample rate. The initial and recovered
TX captures show 3.675% diagnostic EVM, zero errors in 468 held-out BPSK bits,
no current clipping and passing assigned headroom. Reconstructed peak is about
0.09685 V. Whole-capture mean load power is about 45.8 µW (including idle lead
and tail). The scheduled 54.4 µs DATA interval now measures 55.07 µW
(−12.59 dBm) at the modeled resistive load, with 9.70 dB peak-to-mean
power, both before and after recovery. The interval is fixed by source timing,
not an amplitude threshold; no idle-padding or equalizer normalization is used
to inflate power. This remains a low-power demonstration, not a maximum-output
bound or useful-power qualification. Set the required port power and evaluate
waveform-specific backoff, distortion and emissions together before changing
the driver. Antenna/filter loss and complete-packet switching remain excluded. The fault-interrupted
record is not decoded as a complete waveform. Real preamble, emissions,
physical mute tails, DAC loading/noise and converter-current feedback remain
open. Keep the unscaled diagnostic case as an overload negative control.

**TX power decision:** the contract sets a provisional engineering goal of
0 dBm into the modeled 50 ohm RF load before external loss, for constant-envelope
and wideband operation. This is not a protocol minimum or range promise. At the
recorded 9.70 dB wideband crest factor, necessary port bounds require 19.31 mA
peak and 1.738 V differential open-circuit swing, within assigned 2.5 V/28 mA
port limits. However, the full amplitude path does **not** support inferring
success from that port result: with the existing 0.35 V reconstruction limit
and supply-dependent gain, optimistic output ceilings are −3.01 dBm at 2.5 V,
−0.60 dBm at 3.3 V and +0.15 dBm at 3.6 V. Compression is ignored in these upper
bounds; actual output can be lower. Necessary effective gain is at least 4.823,
versus assigned 3.409 at 2.5 V and 4.5 at 3.3 V.

Keep the physical driver provisionally, but require a change/qualification of
the amplitude/gain policy or a demonstrably lower-crest waveform before claiming
0 dBm wideband operation. More current alone does not solve a gain/amplitude
constraint. A new gain or waveform must recheck retained-history overshoot,
crest factor, distortion, emissions and supply headroom together; no extra gain
stage, PA or supply increase is selected here. These are necessary bounds at
fixed recorded crest factor, not a new high-power waveform demonstration.
Reproduce with `selected_lifecycle.py --tx-power-requirement`; the single
`selected-lifecycle.json:tx_port_power_requirement` section owns both port and
full-amplitude results, with the exact source-trace hash.

**FPGA-scaling alternative:** `selected_lifecycle.py --ownership-tx-range`
uses a target native code radius of 180 instead of 50 with unchanged analog
hardware/gain. Actual transported codes reach radius 179.805; the same retained
lifecycle delivers −1.503 dBm during DATA, 3.058% diagnostic EVM and zero errors
in 468 held-out BPSK bits, both before and after recovery. Sampled reconstruction
peaks at 0.348407 V, just below the 0.35 V limit, with passing assigned port
headroom and no current clipping. Thus most of the former low-power result was
conservative digital backoff, but this case still misses the 0 dBm goal by
1.50 dB. Keep this as an alternative operating point, not a new default: the
all-history radius-53 certificate fails, and the sampled peak leaves only
1.59 mV margin without a continuous-time overshoot bound. Other waveform
histories, supply uncertainty, real acquisition and emissions remain open.
Do not increase code scale further just to reach the power goal.

**Shared-stress result:** `selected_lifecycle.py --ownership-stress` applies
−33 mV source offset, a 60 mV peak 10 MHz rail tone and fourfold selected
supply-to-delay sensitivity together. One analytic disturbance drives RF gain,
converter/reference recovery rails, filtered LO phase, payload timestamps and
reference-monitor edges. The seven-stage lifecycle completes, but RX EVM rises
to 23.83%, 19.93% and 25.75%, with two errors in each 468-bit held-out record.
TX EVM rises to 9.82% and 9.65%; electrical headroom still passes. This is a
shared-path counterexample to inferring RF quality from readiness or port
headroom. It is not a protocol BER/PER estimate, a package-derived ripple bound,
or proof that delay sensitivity alone caused the degradation.

The stress is an assigned single-frequency operating disturbance, not a
regularized host-current/package model. Startup observations and idle-recovery
time steps are not a proven continuous ripple envelope; no phase/frequency or
integration-grid convergence claim is made. Existing converter-current feedback,
clock-source noise and physical rail ownership gaps remain. Do not claim the
shared uncertainty milestone complete from this run.

**Inverse requirement, not another sweep:** a 10 MHz LO disturbance translates
part of the +12 MHz blocker to +2 MHz, inside the wanted passband. For the shared
stress, sinusoidal PM produces a first sideband of 0.254 times wanted amplitude;
the selected supply-dependent gain produces an AM term of 0.0576. Their coherent
first-order range is roughly 0.197–0.312, consistent in scale with the observed
RX degradation without proving sole causation. A post-mixer channel filter cannot
remove that in-band translated term without also removing wanted content.

For an illustrative **5% incremental branch allocation**, PM alone requires
ripple below 11.79 mV peak at the stressed 0.1 ps/mV sensitivity, or about 14.12 dB
additional blocker rejection before mixing. A conservative small-signal AM+PM
sum tightens the ripple requirement to about 9.62 mV peak. This 5% branch value
is a diagnostic tradeoff, not a new protocol acceptance limit or free additional
EVM budget. AM alone is already 5.76% at 60 mV, so fixing clock sensitivity alone
does not establish success. Higher sidebands, filter response, equalization and
other noise remain outside this inverse estimate.

The resulting mitigation choices are architectural: reduce shared rail ripple
through supply isolation/regulation and bounded return paths; reduce downstream
supply-to-delay and gain sensitivity; reject the blocker before mixing where
external selectivity is physically credible; or combine smaller improvements.
An external oscillator still passes through on-chip supply-sensitive stages.
Costs belong in the existing pin/power/area/external-component ledgers before
calling any route qualified. The fast reproducible calculation is
`selected_lifecycle.py --supply-requirement`; it records the exact stress-section
hash and does not refresh that historical simulation's source hashes.

**Finite-current source contract:** host-current generators now accept an
explicit `current_edge_s` shared by D2H supply, H2D internal supply and external
capacitive-return ports. It convolves each assigned waveform with a causal,
unit-area triangular kernel of duration `2*current_edge_s`, retaining charge/DC
current and adding centroid delay `current_edge_s`. Its sinc-squared spectral
factor removes the instantaneous current-step defect: the previous O(1/f)
current tail becomes O(1/f³), so an inductive O(f) response has an absolutely
summable O(1/f²) voltage tail. This establishes a usable mathematical source
family, not a measured current shape or qualified package envelope.

Zero remains the explicit legacy negative control. No smoothing time has been
selected for silicon or silently applied to old evidence. The smoothing duration
must agree with actual GPIO drive/receiver current, capacitive load and host
setup/hold timing; it cannot be chosen solely to improve rail extrema. Next use
this bounded family in the existing common network and preserve charge and mean
power while comparing convergence. Do not restart capacitor/ESR optimization.

**Fixed-network result:** finite current edges remove the mathematical
source-step divergence, but do not qualify the former 1 nF comparison network.
At the finest sampled bandwidth, keeping topology, 100 ps kernel half-width,
D2H drive, host phase and return currents fixed gives:

| H2D receiver energy hypothesis | H2D internal mean current | Host-bank minimum AC excursion | Timing minimum AC excursion |
| --- | ---: | ---: | ---: |
| Native TT internal-energy upper value, 0.421 pC/transition | 1.448 mA | −1.054 V | −0.204 V |
| Native TT plus Y-load upper value, 1.246 pC/transition | 4.283 mA | −1.187 V | −0.222 V |
| Adverse assigned 7 pC/transition | 24.063 mA | −2.115 V | −0.347 V |

The receiver-energy correction is material but insufficient. Do not interpret
these linear excursions as measured rails or device damage. Native cycle energy
has been mapped to equal positive pulses as an explicit shape hypothesis; the
PDK signed per-transition waveform is not recovered by this mapping. HOST DC
reservation remains unchanged, so this is AC attribution rather than a claimed
power saving. D2H output-driver charge is independent of the native input-cell
characterization and remains unchanged.

The assigned inverse-capacitance ESL rule gives 3.33 nH per host bank; it is not
extracted geometry. Current temporal shape, host-output energy/drive and actual
local/return inductance need credible bounds before capacitor selection. The
last bandwidth increase changes waveforms by 13.4–27.4 mV across these cases;
no infinite-tail bound, physical high-frequency model, arbitrary-phase envelope
or ADC/core/reference forcing is qualified. Abrupt-source negative controls and
full refinement values remain in `finite_host_edge_network`; reproduce this
energy comparison with `selected_revision_check.py --host-energy-comparison`.
Keep the result as a rejected source/topology combination, not rejection of the
whole programmable-transceiver architecture.

**Host-source evidence correction:** pinned public native `in_c` Liberty data
at TT 3.3 V/25°C gives 0.376–0.421 pC equivalent *cycle-averaged internal* charge
per transition, or up to 1.246 pC including the separate Y-load switching term.
See [the power owner](power-partition.md#current-mathematical-host-load-hypothesis)
for exact source, units and exclusions. The previous 7 pC H2D receiver value is
an adverse assignment, not a native-cell measurement or a justified typical.
Do not replace it globally: custom receiver energy, rail ownership and temporal
shape remain uncertain, and D2H output-driver charge is a different quantity.
This evidence constrains energy; it does not validate local inductance or select
a smoothing time. Use distinct evidence-informed and adverse cases in the next
common-envelope comparison rather than force one guessed waveform to explain
all possible implementations.

**Stop here on waveform tuning and arbitrary stress sweeps.** The main next
architecture decision is the permissible *joint* supply-noise and clock-delay
sensitivity envelope, with credible external-clock/regulation/filtering fallback
costs. Establish it from the connected model and physically bounded sources;
then test real acquisition/turnaround and update capability verdicts. Preserve
this adverse case instead of optimizing away its errors or relaxing acceptance.

**Same-channel response requirement:** the selected 37.5 MS/s / 150 Mword/s
D2H / 312.5 Mword/s H2D composition reserves 6.085 us after the last required
RF input sample for conversion completion, receive service, resampler lookahead,
command-frame wait, command/CDC/boundary service, assigned 2 us analog direction
settling, TX interpolation lookahead and prefill. A 10 us diagnostic response
window therefore leaves **3.915 us** for FPGA processing and remaining analog
latency. The 150/192 us windows leave 143.915/185.915 us. The 512-bit TX prefill
plus bounded service backlog totals 744 bits within the 1,024-bit allocation.

These are inverse requirements, not a successful packet response. RX filter
latency, CRC/decision/generation, timestamp calibration, and actual TX air-launch
delay must fit the residual; do not assign them zero. A precomputed response can
remove some work only when the real control path proves that overlap. The clock
and stream epoch must stay active for same-channel direction changes. The
20 us STOP/rearm guard belongs to a different operation. Prove the generic
retained-clock direction switch and timing from actual received packet end to
actual TX output before promoting the tight-deadline capabilities.
Reproduce with `selected_lifecycle.py --turnaround-requirement`; the earlier
standalone transition screens use different clocks and are not this budget.

**Direction control and retained analog integration:** direct
RX-only→TX-only transfer replacement remains rejected as geometry change. The
new generic gate instead keeps paired queues alive with unchanged sample/frame
phase and epoch. `enable_rf_direction_gate` arms the initial direction;
`schedule_rf_direction` inserts a mute/settle interval and then enables the new
direction. An explicit host write schedule supplies real prefill; synthetic
initial TX prefill is forbidden in this mode. RX completions whose acquisition
preceded gating can finish using the declared conversion latency, and their
queued data continues to drain. No modem or CRC moves onto the chip.

The selected-rate control audit verifies actual emitted bits and unchanged epoch
without STOP. Regression checks cover chunk invariance, rejected late commands,
and qualification loss winning over a simultaneous scheduled TX launch. Current
support is direct host words without feedback/CDC block staging. The command
schedule assumes arrival has already occurred; real command/CDC latency remains
in the turnaround budget. The `--ownership-turnaround` variant now joins this operation to the same
SAR/DAC/filter/reference/package lifecycle. Its first RF stage receives 37 samples,
transmits 112 actual host-supplied samples, then receives 190 more, without STOP
or epoch change and with zero synthetic TX prefill. RX completion times and
resumed nominal acquisition times are preserved; TX consumption occurs only in
the enabled interval. Later wired service and reference-loss recovery still run.

This closes the missing retained-state direction operation, not physical
turnaround qualification. The 2 us mute/settle intervals are assigned; RF output
mute is ideal and RX forcing is zero while gated. No packet-end decision,
command arrival, measured analog-ready condition or calibrated air-launch is
proved. Those delays must still fit the 3.915 us residual requirement above.
Avoid another control-only refinement campaign: prioritize common source/load
uncertainty and actual packet acquisition/launch evidence.

**Configuration decision:** extend the candidate RX cutoff ceiling from
9.157407 to 9.53125 MHz (4.08%) using the existing tunable filter. The selected
fifth-order finite-zero response at the old ceiling loses 7.519 dB at the
HE20 outer tone, violating the 1 dB investigation allocation. At the new
ceiling it loses 1 dB and rejects the 12 MHz blocker by 37.798 dB in the ideal
model. The contract, numeric validator and joined lifecycle now allow this
setting. Existing all-pole fixtures keep their explicit historical cutoffs;
their results do not qualify the finite-zero implementation. No extra filter
stages or pins are selected. Physical tuning range, stability, noise, current
and area remain unqualified; widening a numeric range is not implementation
proof. Reassess packet quality and shared budgets at this same setting.

First establish packet-level quality at one declared conditional operating point;
then apply the shared uncertainty envelope and map the outcome to all 17
capabilities. Do not call it packet qualification until real acquisition and
protocol-specific acceptance are exercised. Further component sweeps are
justified only when this joined result identifies the decision they resolve.

**Joined packet acquisition:** `selected_lifecycle.py --ownership-packet` now
runs an LE 1M advertising PDU on channel 37 (2402 MHz) through the same seven-stage
retained lifecycle. RX uses the selected external LO /256 (9.3828125 MS/s),
1 MHz finite-zero filter, existing noisy nonlinear frontend/SAR/reference,
−65 dBm wanted signal, −50 dBm +12 MHz blocker and fixed 42 dB PGA gain.
Each RX stage delivers 1,535 complete I/Q samples through actual host words.
A finite FPGA resampler feeds the existing preamble/access-address timing/CFO
search and CRC observer; no start time, source payload or hidden analog clock
is passed to that observer. The expected payload is scoreboard-only.

Initial RX, post-wired RX and post-reference-fault RX all acquire and recover
the exact PDU with CRC accepted. This is connected real-packet RX evidence,
not BLE PER, sensitivity, AGC, other PHYs or request/reply qualification. The
resampler requires 3.4105 us lookahead; observer decision times are relative to
its input record, not complete host response latency. TX in this case remains
the prior diagnostic payload, not a BLE response. The reference stimulus was
extended to cover the longer final packet while preserving the injected 1 us
clock-loss event; the original shorter stimulus correctly triggered a second
reference-loss fault. Exact results: `selected-lifecycle.json:ownership_packet_trace`.

**Packet/shared-stress join:** the LE 1M RX lifecycle acquires and passes CRC
in all three stages under −33 mV source offset, 60 mV peak ripple and fourfold
supply-to-delay sensitivity, at both tested ripple frequencies:

| Ripple | +12 MHz blocker first translated sideband | Acquisition fit residual across three stages | Packet result |
| --- | --- | --- | --- |
| 10 MHz | +2 MHz, outside 1 MHz passband | 0.0156–0.0158 | All three exact PDUs/CRCs accepted |
| 11.5 MHz | +0.5 MHz, inside passband | 0.0917–0.2014 | All three exact PDUs/CRCs accepted |

The dimensionless fit residual is the observer's normalized squared frequency
fit error, not RF EVM or a probability of failure. The assigned filter magnitude
is −39.96 dB at 2 MHz versus −0.843 dB at 0.5 MHz. This supports a conditional
narrowband path even with an in-band translated blocker, with visibly degraded
acquisition. It does not bound arbitrary ripple, oscillator noise, weaker wanted
signals, other packet contents or PER. Do not transfer this success to wideband
RF or the wideband stress failure to all narrowband modes. Stop frequency sweeps
here; remaining priority is causal request/reply and a justified common envelope.

Reproduce with `--ownership-packet --ownership-stress`, adding
`--stress-ripple-hz 11500000` for the second case. Evidence sections are
`ownership_packet_stress_trace` and `ownership_packet_stress_frequency_trace`;
nominal packet evidence is retained separately.

**Causal request-service join:** `selected_lifecycle.py --ownership-request`
replaces the short advertising stimulus with an addressed LE 1M scan request.
Initial, post-wired and post-fault RX all acquire and CRC-check the exact request
through actual host delivery. The FPGA response policy checks decoded type,
length and advertiser address; source truth is not an input to that decision.
Its response budget now starts from the actual completed host record, including
FIR lookahead, rather than backdating availability to the air CRC timestamp.
Conversion/delivery/lookahead are not charged twice. Assigned 2 us FPGA work,
command service, transition settling and prefill leave 126.30 us preparation
margin to the decoded-timing-derived response target. Prefill plus service
backlog is 891/1024 bits. A late-host-record control refuses to arm even with a
valid CRC; invalid CRC also refuses to arm.

The RX-only `ownership_request_trace` remains a readiness budget, not a
transmission. Its `reply_armed` Boolean must not be called an on-air result.
`selected_lifecycle.py --ownership-reply` now executes the first exchange on the
same live chip: decoded request/address approval generates FPGA response words,
host writes wait for the assigned work/command budget, real FIFO prefill precedes
scheduled TX, and actual consumed words drive retained DAC/filter/mixer/load.
No STOP, clock rearm, epoch change or synthetic prefill occurs between request
and reply. An independent ideal peer acquires the exact response and accepts
CRC; assigned port compliance and sampled reconstruction amplitude pass. The
other RX stages still verify request reception after wired operation and fault
recovery; reply-after-fault is not exercised. Command transport remains budgeted
rather than decoded SPI, mute is ideal, and the source truth is scoreboard-only.
Current evidence: `selected-lifecycle.json:ownership_reply_trace`. The peer's
decoded bit boundary gives 150.8105 us from the source request bit end, versus
the 150 us target; the first DAC consumption is 150.5729 us after that end.
Source timing is consulted only by the final scoreboard. This is not physical
threshold/mask timing: the peer uses a 100 ns grid, and group-delay calibration,
switch tails, emissions and stressed request/reply remain open. This closes the
first modeled causal exchange; stop adding nominal radio fixtures and reassess
the remaining common-envelope and wired electrical/CDR gaps.


**Turnaround activation decision:** separate RX analog enable from sample-valid
and delivery enable. At the scheduled TX→RX action, mute TX and enable the RX
frontend; hold payload delivery muted for the assigned 2 us settle interval.
Clocks, queues and epoch are retained. `BehavioralChip.rf_rx_analog_enabled_at`
now drives the retained frontend/filter independently of the delivery gate.
This adds no storage, pin, stage or longer deadline in the model; existing warm
RF current remains reserved. Physical switch overlap, leakage and current
transients still require qualification.

The joined tone audit now gives 8.46% residual in the first 16 resumed delivered
samples and 8.40% in the following 98, compared with 94.45%/11.96% when filter
forcing stayed muted until delivery. One gain/DC fit uses the last 64 resumed
samples; these are retrospective diagnostic residuals, not packet EVM/PER or
causal acquisition. Initial pre-switch activation still shows 63.63% residual
and is not solved by the turnaround change. No continuous settled-signal or
physical readiness guarantee is implied. Exact current provenance lives in
`selected-lifecycle.json:turnaround_signal_audit`; reproduce with
`selected_lifecycle.py --ownership-turnaround` then `--turnaround-signal`.

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

### Keep-or-change decision: change the delivered-clock architecture

**Decision, 2026-09-26: keep the full companion chip; change the external
high-speed clock frontend to a differential input and require lower
supply-to-delay sensitivity in its downstream clock path.** The unchanged
single-ended baseline has not earned continued selection for high-performance
qualification. This is an architecture decision for the next model revision,
not a declaration that the revised chip has a verified operating envelope.

The decision is based on matched internal-load studies, not the number of
passing tests. Both inputs use a 1 V nominal Thevenin source amplitude (single
versus differential), the same mean-current allowance, current-pulse hypothesis,
package target, CDR and launch corners. Delivered voltage, source power and pad
loading differ and are modeled; this is not an equal-source-power comparison.

| Input / downstream sensitivity hypothesis | Continuously ready wired cases | Interpretation |
|---|---:|---|
| Single-ended / 0.1 ps/mV | 0/32 | The original sensitivity hypothesis remains inadequate. |
| Differential / 0.1 ps/mV | 0/64 | Changing the input alone is insufficient. |
| Single-ended / 0.025 ps/mV | 28/32 | Distribution improvement alone leaves tested failures. |
| Differential / 0.025 ps/mV | 64/64 | The combined change has the strongest joined evidence. |

The differential cases include two mismatch hypotheses and both supply-delay
signs; the single-ended cases include both signs. All short records have zero
bit errors, including unready cases. These are readiness comparisons, not BER
or yield estimates. Sources: [single-ended](../evidence/shared-single-internal.json)
and [differential](../evidence/shared-input-internal.json).

The change also has RF evidence. At both 2.400 and 2.484 GHz, the stressed
acquisition/coded-DATA diagnostic recovers the tested wanted payload with the
paired input and rejects its no-wanted control. The matched single-ended input
also recovers those payloads, so this is evidence against a demonstrated RF
regression, not proof of a unique RF solution. Raw errors and far-offset TX
power generally improve in the paired studies. These are limited diagnostic
waveforms, not standards-valid HE packets, PER or spectral-mask qualification.
See the existing acquisition, TX and wake sections below for exact scope.

#### Selected change and its cost

| Item | Selected next-revision requirement |
|---|---|
| Physical clock input | One differential clock port: retain `REF_IN` as its positive leg at `inputs[1].pad`; allocate `REF_IN_N` at adjacent unused `inputs[0].pad`. There are then 37 functional signals, 18 unchanged fixed power/return sites and 19 unused signals, totaling the same 74 provider sites. No new package or ground bond is assumed. |
| Clock modes | Differential external GHz timing is the primary high-performance route. Retain low-frequency reference conditioning and autonomous synthesis. A single-ended board source may use external conversion/buffering; its noise, loading and bias count. No simultaneous independent reference and LO sources on this one port. |
| Input current | Allocate an additional 4 mA to external input/phase conditioning: timing/reference 40 → 44 mA, within its existing 48 mA planning ceiling. Warm RF becomes 240 mA, duplex wired 292 mA, single-active-branch wired 246 mA. These are planning bounds; only the first two have the matched paired experiments. |
| Area reservation | Move 0.15 mm² from unassigned global growth to input/protection/conditioning: timing 1.45 → 1.60 mm²; reserve 2.92 → 2.77 mm²; unassigned growth 0.72 → 0.57 mm². Total stays 12.92 mm². This is a provisional allocation cap, not an inferred cell area or demonstrated fit. |
| Distribution requirement | Target magnitude 0.025 ps/mV in the current aggregate 1 GHz-pole supply-delay model, retaining both signs. The existing distribution allowance remains 6 mA and 0.20 mm². The input's extra 4 mA does not pay for this improvement. Stage-specific spectra, quadrature and additive noise must replace the scalar approximation before qualification. |
| Board/input requirement | Use the tested 1 V differential Thevenin-peak case as the first requirement point, with modeled per-leg loads and mismatch. It is not a guaranteed input range. Establish actual common-mode bias, protection, bandwidth, duty cycle and source-noise limits before treating the interface as realizable. |

The site inventory confirms the additional pin is adjacent and unassigned.
This does not establish compatible PCB routing, bond mutual coupling or RF
performance. The area/current arithmetic closes the planning allocation only.
0.025 ps/mV is a successful tested hypothesis, not a measured achievable bound,
a monotonic acceptance threshold or a demonstrated margin across all phases.

#### Keep, reject, and leave unqualified

- **Keep:** all requested protocol targets, RF/wired payload exclusivity,
  external regulation/passives, provider-compatible common returns, 0.25 nH
  assembly target with worse controls, 500 pF reservoir, LO-derived sampling,
  independent wired CDR, existing converters/filters, warm/muted RF turnaround,
  full-rate H0 transport, FPGA-owned protocol processing and small chip queues.
- **Reject as the primary remedy:** stronger single-ended drive, capacitance
  increases alone, favorable switching-phase cancellation, assumed host silence,
  deep buffering, or relaxed readiness criteria. None has earned joint closure.
- **USB:** keep host/device scope and the shared-pad architecture for now.
  Differential timing does not fix board-referenced pad return. The rate audit
  finds no combined pass, but the instantaneous quiet-pin screen is not a full
  compliance measurement. There is insufficient evidence to justify a specific
  pad redesign or to drop USB; receiver behavior and real response-path latency
  remain separate blocking obligations.
- **Physical feasibility:** still unqualified. A package that misses its target,
  unattainable distribution sensitivity, or incompatible pad bias could defeat
  the revised design. External clocks do not bypass these on-chip obligations.

#### Decision closure and next execution boundary

The keep-or-change question is closed: **adopt the combined clock change**.
Do not postpone this decision until every protocol passes, or describe it as
proof that all protocols will pass. The model-completion gate remains open.

The executable contract, diagram and selected payload-clock factory now encode
this revision. Single-ended helpers and saved evidence remain explicit historical
controls. Migration is not a new payload/PER qualification: next qualify the
combined input/distribution requirement across bounded package/current/phase
variations and representative RF/wired lifecycles.
A failure to fit the selected physical budgets reopens the affected clock
implementation, not the protocol list by default. No new transistor schematic
or layout work precedes mathematical closure.

### Differential-revision feedback audit

The selected narrowband converter-feedback and generic RF driver-wake campaigns
still requested the single-ended load transfer after the clock frontend migrated.
The converter path also inherited the old 0.1 ps/mV delay default. These were
model inconsistencies, not evidence against the differential architecture.

Both paths now inherit the delivered clock's input topology, delay sensitivity
and sign. Wideband converter feedback uses the same helper; driver wake selects
the environment's differential load unless a control explicitly overrides it.
Six converter/wake tests pass, including exact automatic-versus-explicit
comparisons of both input legs, effective differential input, rail and delay.
Existing independent nodal/charge checks remain in those tests. Historical packet
and wake reports were not rerun or relabeled as current qualification.

The selected differential payload factory now supplies the retained internal
current hypothesis by default: timing 10 mA at LO/16 and core 20 mA at
156.25 MHz, with 0.2 ns gamma pulses and 64 harmonics. These means remain inside
the existing owner budgets; no extra DC is added. Explicit caller load lists,
including an empty unloaded control, remain supported and are recorded. The
electrical seed and legacy single-ended helpers do not silently inherit this
change; their direct consumers remain controls.

A spectral-grid helper derives a power-of-two Nyquist floor from delivered-clock
and rail tones plus the signal/image guard. Selected wideband feedback/wake and
narrowband paths use that floor. Explicit inadequate grids continue to fail;
meeting Nyquist is not proof of waveform convergence. The retained 10 GHz
current spectrum requires 1024 × 20 MHz for the checked wideband case and
4096 subdivisions of the LO/256 sample period for the narrowband setting.
This exposes a computation cost; it is not permission to omit current harmonics.

The [selected-revision check](../evidence/selected-revision-check.json) runs the
default factory at 2.484 GHz with the full internal load and a warm TX waveform.
It exactly reproduces the prior paired, 20%-mismatch, positive-delay-sign case:
3.83665% EVM, 0/2,340 BPSK errors and 0.679243 mW modeled output power. Current
source hashes and the historical input-report hash are retained. This verifies
default-path migration for that case, not emission compliance, cold wake, full
packet acquisition or all package/phase corners. The updated narrowband packet
campaign has not been rerun at its newly required grid. Complete joined
lifecycle and capability coverage remain open.

### Selected differential package screen

The [revision check](../evidence/selected-revision-check.json) now includes all
18 combinations of the three existing package hypotheses, two RF endpoints and
2.5 GHz wired timing, with both supply-delay signs. Every case uses the default
internal-current hypothesis, 1 V differential source and 0.025 ps/mV downstream
sensitivity. Reproduce with `python3 verification/selected_revision_check.py`
from the project directory; it verifies the existing baseline source hashes
before extending the report. It does not rerun the report's earlier TX check.

| Return hypothesis | Accepted clocks / cases | Combined edge-error RMS range | Largest per-leg finite-tone voltage bound |
|---|---:|---:|---:|
| 0.25 nH target, 200 pH die-cap ESL | 6/6 | 2.563–4.138 ps | 0.413 V |
| 0.5 nH control, 200 pH die-cap ESL | 6/6 | 3.320–5.644 ps | 0.536 V |
| 2 nH control, 1 nH die-cap ESL | 0/6 | 8.890–13.402 ps | 1.311 V |

Clock acceptance requires resolved ordered edges and the assigned 0.6 V
incremental input envelopes. The larger per-leg bounds reject every 2 nH case;
these are conservative bounds, not measured overvoltage or proof of physical
impossibility. The 2 nH case changes capacitor ESL too, so it does not isolate
return inductance as the sole cause. Combined RMS includes deterministic timing
motion and is not a standards jitter-mask verdict.

The rail calculation uses a conservative sum-of-tone enclosure because an
explicit high-resolution coherent waveform exceeded the fast-screen grid cap
at one frequency. At 2.4 GHz the resulting target interval is 2.470–3.456 V;
the 0.5 nH interval is 2.443–3.483 V. A lower bound below the old 2.5 V fixture
floor does not establish an observed excursion or a device violation. Rail
headroom remains an independent gate even when clock acceptance succeeds.

The same report now contains matched downstream results (`--wired` and `--rf`
respectively). Both package points retain the selected 20% aligned input mismatch,
full internal-current hypothesis and 500 pF die capacitance:

| Return hypothesis | Wired continuously ready / cases | Wired held-out errors | RF raw errors at 2.400 / 2.484 GHz | RF decoded payloads |
|---|---:|---:|---:|---:|
| 0.25 nH target | 32/32 | 0 | 22 / 18 | 2/2 |
| 0.5 nH control | 32/32 | 0 | 20 / 17 | 2/2 |

Wired cases cover both delay signs, four launches and four independent peer
phase/ppm corners, with 1,200 held-out bits per case and unchanged readiness
criteria. Minimum signed voltage margins are 0.276 V and 0.274 V respectively.
These short windows do not establish long-link BER or physical phase-detector
precision.

These exploratory RF cases use −85 dBm wanted, −30 dBm blocker at +12 MHz, fixed 54 dB gain,
negative delay sensitivity, seed 431, unknown arrival and −120 kHz CFO.
The 54 dB gain exceeds the selected 42 dB PGA ceiling; these results cannot
qualify current RF performance. Use the common wideband inventory case instead.
Causal SAR/reference-current feedback converges in two passes in every case.
Observed sampled rail intervals span 2.709–3.139 V for the target and
2.699–3.154 V for the control; these are waveform observations, unlike the
conservative triangle bounds above. Both target acquisition diagnostics exactly
reproduce the historical paired-input results. Legacy training plus coded HE20
DATA is still a diagnostic packet, not a standards-valid HE PPDU or a PER test.
The slightly smaller raw-error counts at 0.5 nH do not imply that greater return
inductance improves RF performance.

Each section retains its own source hashes. Check them against the worktree
before reuse; these exploratory sections are not the common inventory baseline.
Old hashes are not refreshed merely to make a prior result appear current.

**Decision:** retain the 0.25 nH target and keep 0.5 nH as a package candidate
requiring matched current-inventory payload evidence. The downstream comparison no
longer justifies rejecting 0.5 nH outright. It does not establish a continuous
acceptable inductance range or qualify an assembly. Reject the 2 nH hypothesis
for the current conditional payload qualification. Shared USB pad disturbance,
physical receiver bias/CMRR and delay sensitivity, asynchronous switching phases,
startup/retune/recovery, long links and thermal/current bounds remain independent
gates. The next broad closure work must cover those gates rather than accumulate
more copies of these short passing payload cases.

### Host and internal switching phase enclosure

Keep the selected 0.25 nH package hypothesis, conditionally. Periodic
phase-independent rail bounds fit the assigned interval, but wired operation
has only about 65 mV of lower-bound margin. Doubling internal pulse activity
loses the sufficient enclosure even while fitting DC allocations. Package,
current spectrum and circuit sensitivity remain physical assumptions.

The current joined analog fixture is a warm RF retune with separate host,
internal and differential-reference ports, retained SAR state, and fixed-reserve
reference-recharge feedback. It meets numerical stopping criteria and preserves
converter words when the feedback grid is halved. It uses a short known
baseband tone and scheduled guards—not packet recovery or a ready handshake.
See [the lifecycle evidence](../evidence/selected-lifecycle.json) and
[the closure inventory](mathematical-closure.json) for exact configurations,
residuals and intermediate verification.

Source-loss detection still needs a decision. Independent host/core origins can
produce 21.86 mV at the quiet clock input, above the legacy 20 mV threshold.
The tested divided monitor eventually detects loss, but latency can grow from
100 to 200 ns. A 30 mV candidate with assigned ±5 mV offset restores the
100 ns result in that fixture; noise, chatter and physical offset remain open.
This is not a demonstrated permanent false-lock failure.

ADC activity is constrained by the existing CORE allocation: 20 mA of core
pulses plus a 3 mA reference reserve leave 17 mA for the investigated switching
hypotheses. Fixed charge per conversion preserves the tested rail and
clock-edge bounds; holding the same current at a four-times-slower sample rate
is a distinct adverse control. A selected wideband diagnostic payload also
decodes with that activity. Neither result establishes physical switching
charge, full spectral coverage or protocol PER. The 19.3 ps deterministic edge
bound must not be quoted as RMS jitter.

Lifecycle transport now uses the analog environment's actual host rates:
RF D2H is LO/16 (150 MHz at 2.4 GHz), while H2D remains 312.5 MHz.
Synthetic-payload fault/recovery and epoch checks pass at those rates. Actual
The short SAR capture still cannot deliver a fresh host frame. Its extended
22 us counterpart now carries actual converter state and iterative recharge
feedback through warm retuning, rearm, the 20 us timer/reference-presence check
and finite host delivery on one absolute timeline. It excludes 776 pre-ready
samples and delivers 112 ten-bit words from 61 eligible samples, with 344 bits
accounted for at STOP. This remains a known-tone diagnostic; readiness does not
yet check analog settling, every LO crossing, or noise/quality. Joined acceptance
now additionally rejects supply values outside the existing 2.5 V model domain
at any SAR equation evaluation; a perturbed-rail control exercises that rejection.
This is an offline sampled validity check, not hardware voltage monitoring or
a continuous-time headroom guarantee.
Historical packet reports used capture-mean current centering. Fresh packet
feedback now replaces the same fixed recharge reserve as the lifecycle model;
old report hashes and scopes are not refreshed by that implementation change.

The passive clock-loss interval now retains package state through source
shutdown and return. SAR decisions use allocated local completion timing after
an external acquisition edge; the ADC activity envelope therefore persists for
one additional 18 ns conversion interval. Physical completion/timeout behavior
and its actual current remain circuit requirements. The two grids compare
ideal monitor detection for this fixed-phase fixture. D2H replay can represent missing beats,
and its independent watchdog test faults without converter or host edges.
The converter continuation retains SAR charge/noise across the outage,
including completion after the source is fully off. Moving the fault phase for
that case exposes a one-edge coarse/fine disagreement at 20 mV, despite matching
watchdog timing; the 30 mV comparison agrees. An independent piecewise harmonic
solution now represents the finite clock ramps exactly as sidebands, preserving
passive charge/current across segment boundaries. It gives 1,031 crossings at
20 mV and 1,027 at 30 mV on all three 12.5/6.25/3.125 ps observation grids,
supporting a coarse time-stepping artifact. The converter now consumes this
analytic rail/reference/delay trajectory and bisected clock roots, retaining
its pre-fault SAR state. Root times agree within 4.8e-17 s across observation
grids; this numerical precision is not physical timing accuracy. The 16
conversions include one completion after the source is fully off, no quiet-gap
acquisitions, and maximum known-tone error of two native LSB. Sampled agreement
does not exclude every grazing crossing or qualify arbitrary phases. The
trapezoidal disagreement remains recorded as a comparison.

Full-history reference recharge now feeds back into the rail, reference target,
input threshold and supply delay during this fault interval. Each iteration
starts from the same saved SAR state and retains the earlier recharge history;
it does not add a second DC allocation. The 125 ps recharge grid settles but
fails the 1 µV frozen-prefix limit (1.10 µV). The 62.5 ps grid meets that limit
(0.62 µV) and the existing feedback stopping criteria in two iterations. Both
produce identical converter words and matching crossing counts. This supports
using the finer-grid continuation; it is still a guarded FFT approximation,
not a strictly causal event solver. The report retains the coarser failure
separately.

The coupled trajectory now continues to 45 µs through 854 additional
conversions. In three iterations it meets the feedback criteria and keeps the
frozen-prefix error at 0.62 µV. Its actual converter words and shared-phase
/16 host clock feed a single warm retune/fault/rearm transport lifecycle:
112 host words arrive before clock-loss detection at 22.10 µs; STOP accounts
for 368 queued bits and rejects stale callbacks. Rearming at 23.10 µs gives
timer/reference readiness at 43.10 µs, followed by 144 correct host words and
288 accounted bits at final STOP. No host edges are invented in the outage.
This closes the previously separate warm fault/recovery replay, within its
assigned analog and GPIO assumptions.

The SAR starts with discharged sample, DAC and reference charge. In the RF
retune case its first aperture sees about 0.271 V; charging participates in the
same feedback history and pre-READY codes are excluded. The same converter and
transport path now also consumes the wired-to-RF package transition, including
its allocated 52 mA load decrease and source/host-clock change. Reference bias
is enabled at time zero; ADC apertures begin only after RF activation. The
62.5 ps recharge-feedback run converges, with evaluated supply 2.6177–3.1522 V.
Readiness now also includes a conditional filter-history bound at the 1 MHz
RX setting: 27.4 µs settling after activation, followed by the existing 20 µs
validity guard. READY is therefore 47.8 µs on this timeline. Seventy-four eligible
converter samples deliver 1,500 bits; STOP accounts for the remaining 276 bits.
The contract's 1,024-bit queue peaks at 416 bits.
The /16 host clock and /64 sample clock now use the same observed input phase,
including in the existing extended retune replay; the previous helper's default
2,048-bit queue is no longer used. Unconverged analog feedback cannot qualify
transport. See `selected-lifecycle.json:full_package_adc_restart.converter_continuation`.

This joins a powered wired package state to RF converter startup and delivery,
not prior wired payload operation or a complete RF/wired/RF loop. Package rails
and prescribed periodic loads start powered; reference bias remains allocated
through the change. The filter certificate assumes bounded linear input history
under fixed coefficients; unknown initial capacitor charge, saturation and bias
wake are outside it. The converter still sees a known baseband tone, with the
old-history error bounded rather than injected into an RF packet. Neither full
power-up, physical filter/bias readiness, arbitrary transition phase nor a
physical READY sensor is established. The retained fault/recovery result
continues to converge.

A startup counterexample exposes the next READY obligation: stable rails and
clock presence do not reveal reference-bias age. At nominal current, only 50 ns
of bias age leaves 0.5 V and up to 102 native LSB error in the fixed-input
fixture, while 200 ns settles. Quarter-current sensitivity makes 200 ns
insufficient too; these times are model deductions, not process bounds.
Qualification must begin at actual bias enable and be invalidated by a reference
reset. The selected control replay now enforces model-observed analog validity:
the reference must be in the assigned coarse 0.98–1.02 V bias window and all
evaluated supply points must meet the 2.5 V model floor. START or the latest
invalid-to-valid transition starts the existing 20 µs guard. An invalid
transition during payload faults the stream and requires STOP/new epoch plus
requalification. Delayed qualification and active-loss controls exercise those
paths. The connected trajectory becomes analog-valid at about 105 ns and
retains its successful retune and clock-recovery payload.

Filter memory supplies a separate counterexample to timer-only readiness.
The selected finite-zero response can retain 6.17% output from a bounded
sinusoid removed 20 µs earlier at a 500 kHz cutoff. This independent real
state-space calculation exceeds the assigned 1/1024 normalized error budget;
it is an actual linear-model witness, not merely failure of a conservative
bound. Sufficient bounds over all bounded prior histories are 91.3/54.8/27.4 µs
at 300 kHz/500 kHz/1 MHz. Keep the generic bandwidth choices, but require longer
qualification or a demonstrated settled state when necessary. Warm bias alone
cannot justify fast turnaround after a disturbance. The existing [power owner](power-partition.md)
records assumptions, formula and mitigations; `selected-lifecycle.json:filter_startup`
contains the cutoff sweep. These are model requirements, not measured GF180
settling times or protocol-specific latency guarantees.

The packet model now makes the transfer family explicit and accepts retained
filter state. A matched channel-38 comparison uses the same 500 kHz cutoff,
selected 0.25 nH package, clock/internal/ADC activity, dynamic rail, native SAR,
recharge feedback, −67 dBm wanted packet and −50 dBm modulated +2 MHz blocker.
The old history is a 50 mV complex sinusoid at cutoff, specified after early
gain/mixing and removed before the record. Packet onset is 4.116 µs into each
record. Results are in `selected-revision-check.json:rx_filter_memory`:

| Filter history | All-pole | Finite-zero |
|---|---|---|
| Explicit zero-state control | Correct request | Correct request |
| Prior tone removed at record start | Correct request | Acquisition fails |
| Prior tone plus sufficient pre-record decay | Correct request, 12.26 µs wait | Correct request, 82.81 µs wait |

All six feedback solves converge and their evaluated SAR supply stays within
2.6877–3.13991 V. The waits bound old-history error to nominal 1/1024 ADC volt
after the maximum 60 dB downstream gain; they are sufficient times, not measured
minimum waits. This gain-referred allocation differs from the earlier normalized
unit-input certificate. Retained ringing also drives AGC: the finite-zero failure
reduces gain to about 12.46 dB, versus 35.93 dB in its zero-state control.

**Decision:** retain the all-pole setting as the demonstrated narrowband choice
for this case. Keep finite-zero settings for their selectivity, with explicit
history/settling qualification. These are generic configurations, not on-chip
protocol profiles. Do not assign one family's settling time to another or infer
that warm bias erases state. Saved filter modes now survive record boundaries;
changing coefficients requires an explicit mapping. The packet experiment
starts from a specified filter history, not a preceding RF/TX transaction;
physical internal swing, noise, previous clock/package history, phase sweeps,
PER and TX-to-RX isolation remain open. It does not downgrade the intended
protocol set or qualify other blocker offsets.

This observer has ideal accuracy and zero latency; the window is an assigned
bias criterion, not a derived ENOB or RF-quality limit. Physical sensing,
independent threshold generation, latency, fault-register encoding and budget
realization remain open. Full power-up and readiness of RF bias/filter and
other analog blocks are also incomplete. Next extend joint phase/package
uncertainty and RF signal-quality coverage while retaining these explicit
readiness conditions. Interrupted
conversion cancellation and leakage also remain open. The model keeps analog
activity running while payload ownership is stopped and uses prescribed host
current harmonics; it does not establish a power-saving STOP, actual FPGA word
switching currents or protocol recovery deadlines. Further isolated passing
cases must not substitute for closing those wider architectural gaps.

The current joint BLE screen (`selected_revision_check.py --ble-joint`) runs
an actual channel-38 request with a nominal PRBS15 GFSK blocker at +2 MHz,
wanted −67 dBm and blocker −50 dBm before external loss. Both the 0.25 nH
target and 0.5 nH comparison decode with dynamic rails, shared differential
clock, internal activity, 17 mA ADC switching and fixed-reserve reference
feedback. Both settle in two iterations; evaluated converter rails span
[2.688, 3.140] V and [2.673, 3.150] V respectively. The 2 nH return / 1 nH
die-ESL case exceeds the assigned incremental clock-input envelope and is
excluded from downstream qualification. Conservative envelope failure is not
proof of physical overvoltage or impossibility. The legacy case label
`selected` still denotes the 0.5 nH comparison; numeric parasitics and
`BASELINE_PACKAGE_CASE` identify the actual target.

This demonstrates a joint RF operating point using /64 sampling (about
0.910 Gb/s of raw 24-bit I/Q for the FPGA), not a PER result or a complete
BLE mode verdict. The /256 setting with its own ADC pulse cadence exposes an
integer-Hz/coherent-record limitation in the fast clock screen; it remains an
analysis implementation gap, not an established silicon limitation. Negative
blocker offsets, other phases/seeds, TX, other PHYs and the packet/lifecycle
join remain open. Packet feedback now exposes the analytical settled quiet DC
correction and uses it outside the captured rail/reference trajectory. The clock
helper resolves the corresponding quiet threshold events and downstream delay;
its out-of-record phase uses that perturbed periodic clock. Each feedback report
records the final guard's residual relative to the settled background. This fixes
the former zero-correction boundary assumption; it does not establish exact
natural-state continuity across a finite FFT tail or a joined RX/idle/TX lifecycle.
The refreshed joint packet campaign retains decoding at 0.25/0.5 nH return
inductance and conservative clock rejection at the adverse 2 nH return/1 nH
die-ESL bound. The connected lifecycle and prerequisite phase-bound reports
have also been regenerated; their scopes remain unchanged.
Uniform-grid
rail evaluation now uses an exact finite-tone FFT, and local clock-root updates use a bounded polynomial expansion followed
by direct harmonic residual checks. The selected differential path no longer
runs an unused historical single-ended clock calculation to obtain its DC ledger.

The same joint campaign now continues the accepted request through an idle gap,
finite H2D/DAC playback, loaded RF output and independent peer decode. Both the
0.25 nH target and 0.5 nH comparison decode the reply using the same absolute
clock and reference realization. A fixed 32-sample prefill initially rejected
launch: 768 bits plus the 421-bit service backlog exceeded the 1,024-bit FIFO.
The generic planner now caps prefill to the room left by that backlog and still
requires enough prefill to cover it. At /64 this selects 25 samples, or 1,021
bits including backlog. Both replies consume all 6,217 samples without a FIFO
fault; no storage was added. The default slower-rate fixture retains 32 samples.

This is conditional warm-biased exchange evidence, not a complete BLE verdict.
The uncalibrated half-envelope marker is about 151.421 microseconds after the
request, not a proven first-bit boundary or qualified 150-microsecond turnaround.
Driver voltage/current/energy checks fit their assigned bounds and active load
power is approximately 3.15 mW. Conservative all-phase rail lower enclosures
remain below 2.5 V; do not infer universal converter-domain qualification from
these waveform decodes. TX code-dependent supply current, switched bias,
physical RF switching, cold RX/idle/TX state continuity, emissions and statistical
packet error remain open. The refreshed TX report independently measures its
own waveform-grid rail interval: 2.6788–3.1722 V at the 0.25 nH target and
2.6648–3.1863 V at the 0.5 nH comparison. Both fit the assigned 2.5–3.6 V
model domain. The exchange verdict now rejects a TX-domain or declared driver
budget violation even if the independent peer decodes. These sampled extrema
are not intersample or arbitrary-phase guarantees; RX voltage flags cannot
substitute for this TX check. Fixed reserved analog bias is the tested mitigation;
no savings from powering down between request and reply are claimed.

The phase-independent screen now turns residual TX supply-current modulation
into a circuit requirement rather than assuming exactly constant bias. With the
selected 0.25 nH return/0.2 nH die ESL, host/core/timing activity and 17 mA /64 ADC
hypothesis present, it adds one zero-mean local-supply/quiet-return current tone
at a time. At each of 163 frequencies from 1 kHz to 5 GHz, including ADC and LO
frequencies, a 7 mA peak tone retains the sufficient rail, input-leg, unique-edge
and downstream monotonicity conditions at all three RF carriers. The tightest
sampled allowances are 17.09/17.54/18.53 mA at 2.400/2.426/2.484 GHz; all occur
at the 5 GHz screen endpoint and are limited by the rail condition. The endpoint
minimum is a reason to extend spectral characterization, not a proven global
worst case. Results live in `internal-phase-bound.json` under
`cases.adc_activity.tx_current_margin`.

Use 7 mA peak as an initial **single-tone characterization target** for residual
warm-driver supply modulation, not a qualified arbitrary-waveform specification.
Its mean remains inside the reserved 28 mA driver bias. Current steering,
keeping bias warm during mute, controlled unmute and external supply filtering
remain credible mitigations. Multiple tones, waveform-dependent charge, switching
transients, frequencies between/beyond the grid, reference recharge and alternate
packages must be joined before using this as a TX verdict. The screen checks
edge existence/order, not a protocol jitter, phase-noise or EVM limit.

The selected-package waveform-current sensitivity now uses **native held-input
state propagation**, not coarse current binning. It advances the finite modes
and algebraic feedthrough of the same passive descriptor used by the lifecycle
model, including the assigned 200 ps current pole. Samples remain at their native
25.76 ps spacing through the TX network response. Continuous transfer reconstruction
agrees within 8.97 nanohms in the selected case; an independent frequency-domain
sum of held-input images agrees with the short tone controls to about 1.01e-8
relative error. Future current changes leave earlier state outputs unchanged.
The native load state can now be serialized and resumed after an explicitly
zero-incremental-current gap. In the retained two-window control, a 25 ns gap
matches the uninterrupted trace within 8e-16 V on the rail; resetting instead
introduces 0.413 mV rail error, 333 ppm reference-scale error and 41.4 fs delay
error. Only supplied current is committed; forecast quiet tails must be replaced
when later activity arrives. Overlapping windows and changed network/observer
signatures are rejected. This closes a component-level state-carrying gap,
not the complete RF/wired mode-transition or bias-readiness requirement.


The selected exchange converges in three TX-feedback passes, retains all 6,217
samples and peer decode, and passes its assigned electrical limits. Sampled TX
rail is 2.678985–3.185115 V; active loaded power is about 3.179 mW. The candidate
law releases at most 7 mA from the reserved 28 mA warm driver current. A longer
natural zero-current tail agrees across all five feedback fields (13.7 nV peak
rail difference after the additional fixed-point pass). This is a tail/iteration
check, **not source-grid refinement**. Native Nyquist is tracked as sample
resolution, not invented as an additional physical clock tone; the TX observer
must not coarsen that grid. Known forcing-frequency checks remain separate.

The previous coarse-FFT packet mismatch remains in
`selected-revision-check.json:tx_legacy_fft_packet_control`. Fast analytic controls
(`--tx-load-numerics`, `sinusoidal_controls`) explain the change: a 1 ns current
grid attenuates 312.5 MHz response by 15.28% and aliases 625 MHz to 375 MHz before
applying its impedance. Charge conservation did not establish waveform fidelity.
The legacy algorithm remains an explicit diagnostic/single-ended path, not the
selected differential TX propagator. Longer guards and normal-mute slew did not
repair that representation defect; another full packet replay is not needed to
repeat those conclusions.

Remaining numerical limits are source-waveform sampling, interpolation between
native output midpoints, floating-point modal reconstruction, and the separately
scoped RX recharge FFT. The current law itself is assumed: these results do not
characterize transistor current, RF-cycle switching, positive excess-current
behavior or bias startup. RX is not rerun against a fully causal joined recharge
model; source-off monitoring, package corners and the complete analog lifecycle
remain unfinished. Normal mute retains 20 ns closure after stop, while fault mute
remains an abrupt stress assumption. The mathematical milestone is still open.

The [phase-independent input screen](../evidence/internal-phase-bound.json)
removes cancellation between D2H, H2D, timing and core current sources before
summing harmonic voltage magnitudes. It therefore bounds every relative host, timing
and core pulse origin within the retained finite-tone linear model. Multi-port
current correlations within each source remain intact. The current screen covers twelve cases: three package hypotheses at both RF
endpoints, the 2426 MHz packet-test frequency and wired timing. Reproduce with
`python3 verification/internal_phase_bound.py` from the project directory.

The largest per-leg bounds across wired timing and both RF endpoints become
0.436 V at 0.25 nH and 0.580 V at 0.5 nH, both below the assigned 0.6 V incremental
envelope. Thus that particular margin does not require favorable host or internal pulse
alignment. The 0.5 nH case leaves only 20 mV of conservative envelope margin;
retain the lower-inductance target. The 2 nH bound rises to 1.481 V and remains
unqualified; exceeding an upper bound is not an observed violation.

The same screen now bounds clock crossings analytically. Write the input as
A sin(ωt + φ) + n(t), with threshold T = 20 mV, |n| ≤ B and |n′| ≤ D.
If |T| + B < A and ω sqrt(A² − (|T| + B)²) > D, the allowed rising-crossing
interval has strictly positive slope and contains exactly one crossing per
carrier cycle; outside the rising/falling intervals no threshold crossing is
possible. The arcsine endpoints bound input edge displacement. Summing the
single-pole supply-delay amplitudes bounds added displacement, while a delay
derivative bound below one proves the output time map preserves ordering.
These are sufficient inequalities, not a linearized jitter approximation.

Both 0.25 and 0.5 nH satisfy these inequalities at both RF endpoints and wired
timing for either supply-delay sign. Their largest deterministic absolute edge
displacement bounds are 17.561 ps and 25.292 ps, respectively; these are not RMS
jitter or standards-mask results. All applicable earlier fixed-phase timing
controls lie within the resulting peak-to-peak enclosures. The 2 nH wired case
fails the amplitude condition, so this method cannot establish unique crossings
there; it remains rejected by the separate input-envelope gate regardless.

This sub-second screen closes deterministic edge uniqueness/order only within
the finite-tone assumptions. It does not close random source/input noise,
frequency drift, changed activity spectra, SAR feedback, rail headroom, nonlinear device behavior or
payload recovery under asynchronous switching. Those remain separate requirements.

### Shared rail headroom across modes

The phase-bound report combines the selected 240/292 mA DC ledger and 3.3 V
±1% source with independently shifted D2H, H2D, timing and core waveforms.
For each source, it preserves harmonic phase relationships and encloses waveform
extrema with a periodic interpolation error ≤ max|v″| Δt²/8. It then sums the
separate extrema and the returned-carrier amplitude. Source origins need not
align; summing their individual limits safely covers every relative origin.

| Return hypothesis | RF 2.400 GHz rail | RF 2.484 GHz rail | Duplex wired rail |
|---|---:|---:|---:|
| 0.25 nH target | 2.666–3.180 V | 2.671–3.179 V | 2.564–3.065 V |
| 0.5 nH control | 2.647–3.193 V | 2.653–3.193 V | 2.547–3.077 V |

These outward-rounded enclosures include source tolerance. Their summed
numerical error allowances are below 6.1 µV. Both package points satisfy the
historical 2.5–3.6 V fixture under this fixed-current linear model; minimum wired
headroom is only about 65/47 mV. The 2 nH case remains outside the fixture.

The report retains the older triangle bounds and their diagnostic supply
windows as conservative controls. Their apparent incompatible RF/wired supply
windows were an artifact of discarding phase relationships between harmonics
of the same source. They do not require a power-network change.

**Decision:** retain 3.3 V and the selected feed/decoupling network. This closes
the phase-origin rail-enclosure question for the retained switching spectra,
not device headroom qualification. SAR/TX load feedback, changing activity or
frequency, nonlinear rail-dependent current, startup and actual block minimum
voltages still require joined evidence. The historical fixture is not a proven
GF180 operating specification.

### Switching-current uncertainty within the existing budget

The phase-bound report also scales the timing/core pulse amplitudes together,
replacing steady current within their existing owner allocations. The nominal
10/20 mA pulsed means can reach 20/40 mA without increasing total chip DC current.
This is an uncertainty probe, not a new baseline or a larger power allowance.

The rail-only sufficient scale ceilings are 1.856/1.903 for the two RF endpoints
and **1.341 for duplex wired** at 0.25 nH. At 0.5 nH they are 1.776/1.825 and
**1.255**. Thus current-budget compliance alone does not establish rail margin:
a shift of only about 34% (target) or 26% (control) toward the same pulsed internal
activity exhausts the conservative wired margin. Doubling the pulses yields
wired rail lower enclosures of 2.375/2.362 V, despite unchanged mean power.
These are enclosure failures, not demonstrated waveform or device failures.

**Decision:** keep the current baseline but prioritize duplex wired load activity
and the local power-feed response over more nominal RF packet seeds. A 0.5 nH
alternative remains conditional on tighter switching-current control. The scale
ceilings do not qualify input voltage, timing or payload performance at those
scales, and changing pulse width or frequency requires a new calculation.

### Existing local-feed mitigation screen

The [local-feed comparison](../evidence/local-feed-bound.json), reproduced with
`python3 verification/internal_phase_bound.py --feed-sweep`, recomputes the same
network at 2, 1 and 0.5 Ω local series resistance. Other package, capacitor,
clock, current and source-tolerance assumptions remain fixed. This parameter is
`package_r` in the electrical model and includes assigned series damping; it is
not a claim that bond-wire resistance can be chosen arbitrarily.

At 1 Ω, both the target and 0.5 nH control enclose the doubled internal-pulse
rail case inside the historical fixture for both RF endpoints and duplex wired.
Target doubled-pulse wired rail is 2.517–3.462 V; the control is 2.512–3.479 V
(outward rounded). At nominal pulse activity the input-envelope and unique-edge
screens still pass. Reducing resistance further to 0.5 Ω is not uniformly better:
the doubled-pulse upper rail bound exceeds 3.6 V in every tested payload mode.
Reduced DC drop trades against reduced damping.

The expanded comparison now also evaluates the clock/input equations at twice
the internal pulse activity. At **0.25 nH and 1 Ω**, both RF endpoints and duplex
wired jointly satisfy the rail fixture, 0.6 V incremental input envelope, unique
rising-edge and output-ordering sufficient bounds for all source origins. The
largest per-leg bound is 0.471 V (rounded upward); deterministic edge displacement
is bounded by 28.486 ps. This is conditional model evidence, not payload or
standards jitter qualification.

At **0.5 nH and 1 Ω**, rail headroom still passes, but per-leg input bounds reach
0.6025 V at 2.400 GHz and 0.6399 V in wired mode. The 2.484 GHz bound is 0.5944 V.
Thus the candidate does not provide a joint sufficient enclosure at the larger
return inductance, even though its edge uniqueness/order inequalities pass.
These failed conservative bounds do not establish actual overvoltage.

**Decision:** retain 2 Ω as the existing comparison baseline; advance **1 Ω with
0.25 nH** as the preferred mitigation candidate for joined downstream testing.
The larger-inductance alternative cannot inherit the same robustness claim.
Causal RF feedback, wired payload recovery, USB disturbance and startup remain
open. Do not silently apply the candidate's better DC rail to old payload evidence.
Establish which portion of the modeled series resistance is externally controllable
before adopting the candidate physically.

### Candidate wired payload gate

The [candidate downstream report](../evidence/feed-candidate-check.json), run with
`python3 verification/selected_revision_check.py --wired --feed-candidate`, tests
1 Ω / 0.25 nH with doubled timing/core pulses and unchanged total DC allocations.
Both supply-delay signs use four launches and four independent receiver phase/ppm
corners. The nominal 2 Ω package evidence is retained separately.

Only **30/32 cases maintain continuous readiness**: positive delay sensitivity
passes 14/16, negative passes 16/16. The two failures share launch offset 12 UI
and initial receiver phase +0.35 UI, at either ±100 ppm. Readiness is 89.17% of
the held-out window, though both finish qualified and all cases have zero bit
errors. Minimum voltage margins in the failing cases exceed 0.278 V. Those facts
do not override the unchanged continuous-readiness requirement.

**Decision:** do not adopt the candidate as a closed solution. Rail/input/edge
bounds are necessary but insufficient; investigate the receiver tracking and
qualification excursions under the increased timing motion. Do not relax the
readiness criterion to accept these cases. This evidence also does not yet
separate the effects of feed resistance from doubled activity; a matched 2 Ω
activity control or event-level diagnosis is needed before attributing cause.

### Attribution of the candidate readiness failure

The [matched failure probe](../evidence/feed-failure-probe.json), reproduced with
`python3 verification/feed_failure_probe.py`, separates feed resistance (2/1 Ω)
and internal pulse activity (1×/2×) at the failing 12 UI launch, +0.35 UI initial
peer phase, −100 ppm and positive supply-delay sign. Both feed values maintain
100% readiness at nominal activity and fall to 89.17% at doubled activity.

Replacing only the emitted clock edges with a constant-period clock restores
100% readiness for both doubled-activity cases. Removing only driver-rail AC
modulation leaves readiness at 89.17%. The constant-clock intervention retains
mean phase, rail waveform, receiver noise and the readiness criterion.

**Decision:** this tested failure follows delivered timing under increased pulse
activity, not the reduction from 2 to 1 Ω or driver amplitude modulation. Keep
the 1 Ω candidate for rail robustness, but do not claim it solves timing robustness.
Investigate clock-path supply sensitivity and the actual receiver tracking/error
history next; physical receiver capability remains an assumption. One matched
corner does not attribute every possible failure or qualify other protocols.

The failure probe now records the receiver error history without changing its
feedback. Direct sequential execution reproduces forecast/commit readiness for
all four joined feed/activity controls. In both doubled-activity cases, one
held-out detector error at bit 2055 exceeds 0.1 UI: 0.11250 UI (45.00 ps) at
2 Ω and 0.11930 UI (47.72 ps) at 1 Ω. The retained 64-transition maximum-error
rule keeps readiness low through bit 2184, a 130-bit interval. Nominal-activity
controls have no threshold exceedances. The separate bit-zero acquisition
excursion is outside the held-out interval and does not explain this loss.

This attributes the measured 89.17% readiness to one retained error excursion,
not sustained loss of bit decoding. It is still a failure of the specified
readiness rule. The timestamp-noise contribution and clock-driven trajectory
must be separated before claiming a physical CDR limitation or improving the
clock requirement; do not infer a BER or soften the criterion from one seed.

The recorded detector-noise draw resolves the bit-2055 excursion further. At
2× activity, the 1 Ω case reaches 0.09075 UI (36.30 ps) geometric tracking error;
the assigned detector contributes +0.02855 UI (11.42 ps), yielding 47.72 ps.
At 2 Ω the corresponding geometric error is 33.58 ps and the same draw yields
45.00 ps. The 11.42 ps draw is about 2.28 times the assigned 5 ps RMS detector
noise: it is not an extraordinary tail event. Nominal-activity runs use a
different noise draw at this bit because their detected-edge histories differ.

A complete feedback rerun with detector timestamp noise disabled restores
continuous readiness in all four matched cases. This intervention changes the
subsequent loop trajectory; it is not an implementable remedy or proof that
subtracting one noise sample would suffice. The original noisy trace still
matches the unchanged forecast/commit result.

**Refined diagnosis:** increased switching-induced timing motion consumes most
of the receiver's geometric error allowance, leaving too little room for its
assumed detector noise. Preserve the 5 ps assumption and readiness criterion;
seek lower delivered timing disturbance before proposing a quieter physical
phase detector. These short runs do not establish a stochastic failure rate.

The same matched probe now sweeps downstream supply sensitivity at the failing
1 Ω / doubled-activity corner while retaining input coupling, rail modulation,
5 ps detector noise and the readiness rule. At 0.025 ps/mV readiness remains
89.17%; at 0.0125 ps/mV it is 100%, as it is in the ideal zero-sensitivity control.
The differential input disturbance alone therefore does not cause this particular
failure. Reducing supply-induced delay is an effective model intervention.

**Decision:** retain 0.025 ps/mV as the baseline assumption and treat 0.0125 ps/mV
as a mitigation requirement to evaluate, not an achieved GF180 capability. Before
adopting it, expand the matched receiver corners and assess the bias/current/area
cost or supply isolation needed. This one passing corner does not establish a
safe sensitivity threshold, monotonic behavior, or physical feasibility.

The lower-sensitivity candidate now passes the complete existing matched wired
receiver set: **32/32 continuously ready, zero held-out errors**, covering both
supply-delay signs, four launch offsets and four initial phase/ppm corners.
The [candidate report](../evidence/feed-candidate-check.json) retains the original
30/32 result separately from `package_wired_screen_lower_sensitivity`. Reproduce
with `python3 verification/selected_revision_check.py --wired --feed-candidate
--lower-sensitivity` (one command). Its frozen source hashes were verified.

**Current candidate gate:** 1 Ω feed, 0.25 nH return and 0.0125 ps/mV downstream
sensitivity survive the short wired readiness screen at doubled internal activity.
The stronger sensitivity remains an unimplemented requirement, not free margin.
No baseline contract change is justified until RF conversion/feedback and USB
shared-pad behavior are checked at the same candidate conditions. Startup,
continuous transport, variable traffic, long-run error rates and physical
feasibility remain open; these 32 cases are not whole-chip completion.

### USB quiet-pad gate with the differential clock present

The [joined USB probe](../evidence/feed-usb-probe.json), reproduced with
`python3 verification/feed_usb_probe.py`, includes differential reference input
loading and carrier return in the same linear PDN as the released USB pads.
This closes an omission in the older USB static controls, which excluded REF_IN.
Remote termination feedback is solved by its complex return impedance and
independently checked by reinjecting the resulting pad current into the nodal
network. The source frequency is an assigned 2.5 GHz reference stress condition,
not a qualified USB clock-generation configuration.

At 0.25 nH, doubled internal pulses, full-rate host activity and the 246 mA
single-active-branch budget, the enclosed released-pin peaks are:

| Local feed | Matched pads | Asymmetric pads/bonds |
|---|---:|---:|
| 2 Ω | 77.662 mV | 78.788 mV |
| 1 Ω | 76.401 mV | 77.504 mV |

**Decision:** neither feed choice resolves the existing 20 mV instantaneous
quiet-pin design guard. Lower clock supply sensitivity cannot fix this passive
pad voltage path. Keep USB's common-mode/measurement and receiver-behavior gate
open independently of the wired readiness improvement. These are fixed-phase
released-pad results, not chirp/squelch, packet turnaround or USB compliance;
the guard's relation to the specified measurement remains unresolved.

The USB probe now distinguishes board-referenced common mode from the voltage
seen relative to the receiver's own die ground. For 1 Ω with asymmetric
terminations/bonds, board common mode spans −50.590 to +76.451 mV, while board
differential disturbance spans −4.646 to +4.202 mV. At the die receiver, common
mode spans −67.730 to +39.834 mV and differential disturbance −3.870 to +6.057 mV
(outward rounded). The 2 Ω control has similar behavior. Matched-pair differential
disturbance cancels to numerical precision at both observation points.

**Interpretation:** the roughly 77 mV pin disturbance is predominantly common
mode; it must not be injected as 77 mV differential data noise. Conversely, a
remote-pin common-mode result does not prove local receiver tolerance: the local
released-pad common mode crosses below die ground. Receiver input range, clamps,
finite common-mode rejection, squelch thresholds and their bandwidth remain
unmodeled. Preserve the quiet-pin guard failure, but use the separate local
common/differential waveforms for the next receiver-level check. No protocol
threshold or compliance verdict follows from this passive decomposition alone.

### Candidate joined RF gate: mixed outcome

The [candidate report](../evidence/feed-candidate-check.json) now includes
`package_rf_screen_lower_sensitivity`, reproduced with
`python3 verification/selected_revision_check.py --rf --feed-candidate --lower-sensitivity`.
It tests 1 Ω / 0.25 nH, doubled internal pulses and negative 0.0125 ps/mV delay
sensitivity with causal SAR/reference-current feedback, −85 dBm wanted and
−30 dBm blocker at +12 MHz, fixed gain, unknown arrival and −120 kHz CFO.

At 2.400 GHz legacy training acquires, but DATA retains 53 raw errors and fails
CRC/payload recovery. At 2.484 GHz it retains 17 raw errors and recovers correctly.
Feedback converges in both cases. Observed rail intervals are approximately
2.604–3.467 V and 2.616–3.461 V, respectively; staying inside the historical rail
fixture does not ensure RF signal quality. These are diagnostic legacy-training
plus coded DATA captures, not standards-valid HE packets or PER measurements.

**Decision:** do not adopt the candidate as a whole-chip solution. Its 32/32 wired
readiness result does not close RF. Retain the baseline and failed capture;
separate the feed, pulse-activity and sensitivity changes in the 2.400 GHz RF
case before selecting a mitigation. Do not infer a band exclusion from one seed,
or dismiss the failure because acquisition and numerical feedback both succeed.

### RF candidate attribution: feed/activity interaction

The [RF reversion probe](../evidence/feed-rf-probe.json), reproduced with
`python3 verification/feed_rf_probe.py`, reverts one change at a time from the
failed 2.400 GHz candidate while preserving the acquisition seed, blocker,
unknown arrival/CFO and causal conversion feedback:

| Single reversion | Result |
|---|---|
| Restore 2 Ω feed; keep doubled pulses and 0.0125 ps/mV | Payload recovered, 21 raw errors |
| Restore nominal pulses; keep 1 Ω and 0.0125 ps/mV | Payload recovered, 22 raw errors |
| Restore 0.025 ps/mV; keep 1 Ω and doubled pulses | Preamble not acquired; no DATA error count |

All three feedback solves converge. The original candidate acquires but fails
payload CRC with 53 raw errors. Thus lower supply sensitivity is not the cause
of that failure; reverting it makes this capture worse. The stressed 1 Ω feed
and increased activity interact unfavorably in this RF bench. These local
interventions do not isolate a specific spur, filter, reference or clipping
mechanism, nor establish a failure probability.

**Decision:** keep 2 Ω as the normative baseline and stop treating 1 Ω as a
universal mitigation. Its rail benefit conflicts with this RF result. Next compare
the actual rail/reference/timing spectra against the blocker and conversion
bands, then test damping/decoupling changes against both wired and RF gates.
Do not select a new feed from rail bounds alone or infer that a single recovered
RF capture closes the 2 Ω doubled-activity headroom gap.

### RF spectral lead for the feed/activity interaction

The [pre-feedback spectral comparison](../evidence/feed-rf-spectra.json), run with
`python3 verification/feed_rf_probe.py --spectra`, shows where the 1 Ω candidate
loses damping. At doubled activity, its 156.25 MHz local-rail tone is 263.4 mV
peak versus 201.8 mV with 2 Ω; the 150 MHz tone is 153.0 versus 114.2 mV. Returning
to nominal activity at 1 Ω reduces those tones to 144.6 and 89.2 mV. The candidate
has a higher DC rail, but also larger periodic modulation. Combined edge-error
RMS is 3.212 ps versus 2.803 ps for restored feed and 2.207 ps for restored activity.

At 37.5 MS/s, 156.25 MHz folds to 6.25 MHz, while 312.5 MHz folds to 12.5 MHz.
These identify possible sampled/reference contamination near the wanted band
and the 12 MHz blocker; difference offsets of 5.75 MHz and 0.5 MHz are locations
to investigate, not proven output spurs. Harmonic phases, anti-alias filtering,
continuous-time mixing and the actual converter sequence matter. The report
therefore does not convert rail amplitudes directly into RF impairment power.

**Next discriminating check:** separately hold reference modulation and delivered
timing fixed in the failed capture, while retaining its rail waveform and causal
converter load. That can identify the dominant path before a new capacitance or
damping sweep. The spectra support a damping tradeoff but do not yet establish
the mechanism responsible for CRC failure.

### RF path intervention: timing remains the shared bottleneck

The [path controls](../evidence/feed-rf-paths.json), run with
`python3 verification/feed_rf_probe.py --paths`, preserve the failed candidate's
rail waveform and recompute causal SAR load feedback. Holding the converter
reference target constant retains 54 raw errors and fails payload recovery
(original: 53). This removes external reference-target modulation but preserves
the SAR's own reference dynamics; it is not an ideal ADC.

Removing periodic/load-induced delivered-clock phase from both LO and sampling
consumers, while retaining assigned source/input phase noise, recovers the payload
with 20 raw errors. Both feedback solves converge. The clock constructor still
computes loaded-edge diagnostics, but those edges are deliberately unused by the
intervened consumers; the report labels this distinction explicitly.

**Decision:** prioritize delivered timing rather than reference-target rejection
as the next mitigation path for this capture. Wired and blocked RF both improve
when power-coupled timing is removed, making this a shared architectural risk.
This does not yet distinguish LO reciprocal mixing from ADC sampling jitter, or
input-ground coupling from distribution delay; nor does it qualify a quieter
clock implementation. Keep the baseline and do not select more decoupling solely
from DC headroom or reference ripple. The idealized control is causal evidence
for this model, not an implementable remedy or a standards-valid packet test.

### Whole-chip risk ranking

Risks are ranked by capability reach, failure severity and usable fallback.
The decisions and checkpoint above own the current verdict; the detailed
experiments below retain their conditions and failure controls. Mathematical
closure requires bounded assumptions, joined startup/operation/recovery and a
verdict for each capability. Physical qualification remains a later obligation.

| Rank | Risk / reach | Severity and fallback | Next discriminating experiment / decision |
|---|---|---|---|
| 1 | Physical interface and shared supply: all high-speed modes | Can invalidate the entire chip. Default-compatible pads, board damping and external regulation help; a custom package is not the baseline escape. | Apply the 240/292 mA mode allocations, actual shared-return topology and bounded pin loading to one fast electrical/timing envelope. Check both host directions and GHz/serial/RF pads. Change the compatible pad/feed plan if no common window exists. |
| 2 | Delivered timing and independent RX recovery: wired and RF | Can defeat all fast modes even with a good external oscillator. External input is selected first; autonomous operation is secondary qualification, not an unpriced rescue. | Bound source → loaded input → phase/distribution and supply sensitivity together; retain independent wired CDR. Determine the allowable device/load ranges, then test acquisition and recovery at those limits. |
| 3 | Converter/filter/reference dynamic range: every radio, especially wideband | Can remove much of the radio value. Finite-zero filtering is selected; interleaving or higher precision costs explicit current/area and calibration. | Join the selected response, absolute noise, blockers, reference load, clipping and clock spectrum at the revised current. Include a narrow and a wide RF configuration so one setting cannot stand in for the entire range. |
| 4 | Generic electrical actions and recovery: USB, PCIe, SATA, video; shared pad loading affects other wired modes | A missing physical state may require redesign, not FPGA firmware. Independent controls and specialized branches are selected; external helpers cover only named board functions. | Audit command-to-pad actions, then run one DC-coupled and one detection/OOB lifecycle with finite host service. Keep the target-specific exceptions in the capability table. |
| 5 | FPGA service and continuous clock ownership: all full-rate applications | Analog may work while the companion is unusable. Selected source-synchronous host, FPGA-owned processing and bounded chip queues avoid deep on-chip buffering, but exact bank timing is unqualified. | Demonstrate uninterrupted worst-rate delivery, independent RX/TX clock drift and fault recovery with the selected H0 electrical load. No physical FPGA purchase is needed for this model. |
| 6 | Fabricated area, heat and variation: entire chip | Rough 12.92 mm² allocation is accepted for planning, with explicit growth. Thermal behavior and parasitics may force rebudgeting. | Carry the allocations into schematic planning after mathematical closure, then layout/extraction. Before that, screen gross current/heat and geometric pad conflicts; do not demand exact transistor area now. |

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
37 functional signals + 18 fixed supply/return sites = **55**, even before
counting 19 spare signal sites. Thus unused signals alone cannot reconcile a
hard 50-total limit. The selected decision is standard-compatible packaging; the earlier approximate
limit is superseded for the physical design. No functionality has been removed. Also, neither the north
nor south edge's 16 signal sites can contain both 11-wire host directions;
the functional diagram's south-host grouping is not a physical pad placement.
See the [physical inventory](../../../docs/roadmap/programmable-transceiver-pin-plan.md#executable-physical-inventory-and-immediate-consequences).

A [candidate provider-site assignment](../../../docs/roadmap/programmable-transceiver-pin-plan.md#candidate-provider-site-assignment)
now places all 37 functional signals: RF/reference west, wired east, D2H/control
south and H2D north. It preserves fixed supplies and adjacent analog pairs,
with both forwarded clocks and REF_IN next to existing ground sites. It leaves
19 unused signal sites, not 19 removed bonds. Host data returns, actual PCB
connectivity, specialized signal-cell geometry and electrical qualification
remain open; the selected provider-compatible physical allocation supersedes
the former approximate 50-total limit.

### Current system decisions

| Coupled requirement | What the model now establishes | Decision / remaining barrier |
|---|---|---|
| Shared supply and die area | Nonideal 500 pF candidates restore sampled rail containment and substantially reduce modeled far-offset TX sidebands; plate cost is bounded separately. | SELECT the normative 500 pF local / 1 uF board reservoir network with a 0.25 nH common-return assembly target in the current design; real impedance, compatible bond geometry, support area, TX-load feedback and supply sensitivity remain unproven. See [selected network](block-diagram.md#selected-implementation-choices) and [power/resource ledger](power-partition.md#joint-capacitance-and-supply-screen). |
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

Current integration uses `inventory_environment` in
[`baseline_envelope.py`](../verification/baseline_envelope.py), the delivered
clock composition and [`selected_lifecycle.py`](../verification/selected_lifecycle.py).
The architecture inventory supplies current ownership, native converter
parameters and legal gain settings. RF and wired payloads remain exclusive.
The retired robustness campaigns used different current/gain assumptions and
a superseded clock-input comparison; their numerical tables are not current
acceptance evidence. See the [model guide](../system_model/architecture_fast/README.md)
for supported commands and explicit omissions.

The following requirements remain regardless of a short decoding pass:

- Account for both host directions, chip-internal switching and externally
  supplied capacitive return separately. Preserve common feed/return coupling
  and count each current contribution once.
- Check supply headroom and the model's validity envelope alongside decoding.
  A conservative interval outside a validity range is an unresolved bound,
  not a demonstrated physical excursion. More board capacitance alone does
  not establish high-frequency isolation.
- Use absolute wanted/blocker levels and input-referred noise for sensitivity.
  Signal-proportional noise and synthetic acquisition are valid diagnostics,
  but cannot qualify weak packet reception.
- Preserve the selected ordering: limited early gain, channel filtering, then
  main variable gain before the ADC. Check noise, compression, filter internal
  headroom and gain settling together under the same current inventory.
- Apply converter-reference modulation at conversion. Input filtering cannot
  remove modulation introduced there; reference supply rejection and transient
  output drive must both fit their allocated power and headroom.
- Preserve correlations among delivered LO phase, mixer action, sample edges
  and independent host switching. Equal RMS jitter does not imply equal
  blocker tolerance or aliasing behavior.
- Observe the loaded transmitter independently. A decoded reply does not
  establish launch timing, spectral emissions or weak-peer sensitivity.

Physical clock/noise parameters, pad/package coupling and implementation cost
remain uncertain. The current status table and closure inventory—not historical
packet counts—own acceptance decisions.

### Combined RF requirements point

Evaluate NF, input linearity, filtering, legal gain, converter behavior and
delivered-clock noise together using the selected inventory and differential
clock-input path. A favorable value from an isolated sweep cannot be combined
with another bench's lower current or quieter rail.

The former six-packet requirements point is retired with its superseded
single-ended input and 37 mA combined RF/conversion ledger. Current modeled
current ownership separates RF, converter and clock resources. The
[resource conditions](power-partition.md#resource-conditions-for-the-combined-rf-candidate)
and current RF-chain closure gates apply; no support verdict is inherited from
that comparison. External source quality does not remove additive receiver,
phase-generation or distribution noise.

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

The contract checker now maps all 17 targets to the selected host-service
arithmetic. RF word and physical DDR clocks are explicitly LO/16 and LO/32;
the older double-rate alternative no longer inflates the planning envelope.
The 2.5 Gb/s selected same-frame scheduler has a conditional 587-bit queue
bound and 560-bit observed peak across the declared clock corners, within the
1,024-bit planning allocation. The older two-frame bound of 1,099 bits is a
different staging assumption. No storage increase follows from that comparison;
actual RTL/CDC and stall limits still need proof. See
[service requirements](streaming-transport-v2.md#capability-wide-service-requirements).


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

Use [the closure inventory](mathematical-closure.json) for current milestone
criteria and open requirements. Use the linked evidence reports for exact
configurations, results and negative controls. Historical entries are not automatically
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

### Adverse-package input excursion check

The current fixed-phase 2.4 GHz follow-up in
`evidence/selected-revision-check.json:fixed_phase_input_envelope` distinguishes
conservative rejection from a modeled excursion. The selected 0.25 nH return /
0.2 nH die-cap ESL case encloses both clock-input legs within ±0.381 V. The
adverse 2 nH / 1 nH case reaches −0.862 V and −0.956 V at sampled times,
exceeding the assigned ±0.6 V incremental envelope. Thus a tighter triangle
bound alone does not rescue that stimulus. Keep the lower-coupling package
requirement or qualify an input architecture with adequate bias/headroom and
isolation. These incremental voltages are not measured silicon overstress or
absolute pad-voltage ratings; other phases/carriers and nonlinear clamps remain
open. Existing clock-edge uniqueness does not qualify input voltage range.

The independent four-corner follow-up separates return inductance from die-cap
ESL (`selected_revision_check.py --input-envelope`). At 0.25 nH return,
raising ESL from 0.2 to 1 nH changes the largest sampled input excursion from
0.377 to 0.399 V; both enclosed waveforms remain within the assigned limit.
At 2 nH return, even 0.2 nH ESL reaches 0.797 V, while 1 nH ESL reaches
0.956 V. For this fixed-phase 2.4 GHz case, decoupling improvement alone does
not rescue the return-path problem. Prioritize lower shared-return coupling or
a qualified input-common-mode solution; do not spend decoupling area as if it
were an equivalent mitigation. This is a corner comparison, not a maximum
permitted-inductance specification or proof over interior resonances.

The same screen now separates common-mode and differential voltage local to
die return. With the driven carrier excluded, the selected case has approximately
90 mV common-mode and 20 mV differential peak disturbance; the adverse case
has approximately 739 mV and 201 mV respectively (sampled absolute peaks).
Therefore receiver CMRR is only one requirement: it can reduce conversion of
common-mode voltage into timing error, but it does not remove physical leg
excursions or the differential disturbance already generated by input mismatch.
Circuit requirements must separately cover input bias/headroom/clamp loading,
frequency-dependent CMRR, and matched two-leg transfer. These numbers describe
one assigned finite-tone stimulus, not universal minimum specifications.

The selected early RX gain law now requires broadband supply elasticity 0.02,
versus unity in the retained adverse control. `rx_gain_regulation_lifecycle` in
`selected-revision-check.json` compares identical 60 mV / 10 MHz ripple, fourfold
clock-delay sensitivity, blocker, noise, converter and retained-state histories.
The requirement reduces blocker modulation, without changing wanted/blocker
levels, physical rail headroom or acceptance thresholds. Both normal TX stages
continue to meet the recorded electrical, amplitude, clipping and power checks.
Known DATA training still excludes real acquisition and PER; remaining RX EVM
must not be labeled an HE high-order-modulation pass. Regulation bandwidth,
implementation power and fabrication feasibility remain future obligations.
