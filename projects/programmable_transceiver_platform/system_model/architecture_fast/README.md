# Whole-chip behavioral model

This guide owns execution and model boundaries. The
[current status table](../../spec/risk-priorities.md#current-status) owns current
conclusions. Completion criteria belong to
[the closure inventory](../../spec/mathematical-closure.json), under `milestone`
and `requirements`. Exact configurations and results belong to the scoped
evidence reports linked from the risk assessment. Do not append experiment history here.

Coverage is checked against all 17 entries in
`contract.generic_control_surface.external_interface_requirements`. The report
must include every target exactly once; adding a contract target without coverage
is an error. Custom GFSK/SDR and frequency-extension stretches explicitly report
missing evidence rather than inheriting HE20 results. Existing pad/transport
lifecycle fixtures are partial: `lifecycle_on_selected_shared_environment` remains
`not_demonstrated` until a matched selected-composition run establishes it.

## Do the tests use the same design?

`design_definition.load_design()` loads `spec/contract.json` and
`spec/analog-architecture.json` into an immutable, validated snapshot. Its
canonical-content fingerprint follows configured electrical environments and
migrated results. Missing required inputs and nonfinite values fail explicitly.
A loader call alone does not prove an entire bench uses that snapshot. Convenience entry points accept a
contract without a snapshot only when it exactly matches the current shared
contract. Modified or historical contracts require an explicit snapshot; the
factory no longer silently combines them with today's architecture. Independent
contract-only mathematical tests remain valid outside these integrated factories.

From `verification/`, the implemented RF packet adapter can be used as follows:

```python
from baseline_envelope import build_model
from design_definition import load_design, Scenario

design = load_design()
config = design.configure(engine="rf", direction="rx", reference_hz=2.426e9,
                          sample_divider=64, pga_gain_db=39)
scenario = Scenario(wanted_dbm=-80, blocker_dbm=-40, reference_peak_v=0.5,
                    assumptions={"temperature_c": 25})
result = build_model(config, scenario).receive(b"diagnostic payload")
```

The constructed adapter retains read-only configuration/scenario properties.
Its `seed`, `environment` and `clock` inspection properties return detached
snapshots; changing an inspection result cannot silently alter the constructed
chip or relabel its evidence. Use a new configuration/scenario to build another
model. The example above has been run through the actual chain: its conditional
clock admission and diagnostic payload decode succeed, with the reported
configuration independently reconstructed.

This adapter runs the existing coded wideband diagnostic with known training
and ideal packet boundaries. It rejects unusable clocks before decoding; it is
not a valid HE PPDU or a universal protocol receiver. Temperature affects RF
and converter thermal noise only, within the selected operating window; gain,
delay, phase-noise, leakage and current temperature coefficients are unmodeled.

Keep three kinds of inputs distinct:

- `design.configure(...)` validates hardware settings against the snapshot.
  The implemented topology is direct external high-frequency timing for RF
  RX/TX and wired operation. Derived rates and legal I/Q gain settings are
  checked; configuration validity does not establish performance.
- `scenario.override(reason=..., ...)` records package return inductance,
  die-decoupling ESL or host-load uncertainty. Unknown overrides fail.
- `design.hypothetical(reason=..., changes={...})` creates a separate circuit
  snapshot with a parent fingerprint and recorded block/device-model changes.
  It cannot silently expand the baseline PGA range. Design-backed RF paths
  require resolved settings; removing configuration cannot restore a default
  sample divider or permit a gain sweep outside the selected circuit. A 54 dB
  requirement experiment therefore owns a hypothetical design with that gain
  explicitly added, while primitive mathematical fixtures stay independent.

The shared-design migration of the current test suite is **complete**. Intended-chip
tests use the immutable shared design; independent numerical examples and
declared simplified/adverse fixtures retain their separate scope. Parameter
binding, numerical convergence and physical feasibility remain separate claims.
This test audit does not qualify unexercised optional runner branches.

| Adapter | Design binding and limits |
| --- | --- |
| Coded-wideband, narrowband request/reply, converter-feedback and driver-wake campaigns | Resolved configurations and recorded scenarios/circuit variants. TX converter requires native 10-bit / transport 12-bit precision. |
| Wired transmit/recovery | Resolved 2.5 Gb/s, divide-by-eight forwarding; mismatched configurations fail. |
| Ideal-FPGA Wi-Fi client fixture | One supplied snapshot per diagnostic campaign; startup, host rates, legal initial PGA, LNA/NF/IIP3, temperature, ADC ENOB and PGA headroom are bound. Packet results and diagnostic rows record current configuration and explicit DAC/filter/normalized-TX assumptions. Gain history remains an external controller model. Prescribed rail/phase, TX nonlinearity and independent primitive examples remain simplified; this is not complete-chip RF evidence. |
| Retained RF/wired ownership lifecycle | One supplied snapshot, per-mode configurations and stimuli, shared frontend/driver/converter parameters. Chip construction and every stage use snapshot-derived transport assumptions; a changed startup guard is tested through the retained lifecycle and its USB extension. Loaded wired recovery requires a stopped injected chip before rebinding transport assumptions and records both the prior and applied assumption sets. External rail-voltage and delay trajectories must be supplied as a callable pair; incomplete stimuli fail before state changes. Comparator law is owned by `paired_sar_comparator`; diagnostic loading is hypothetical. |
| USB exchange and supply | Bidirectional 480 Mb/s with independent 100 MHz SDR host-follow. Shared timing allocations, explicit FPGA response-time stimuli, rejection of unsupported pipelines and conflicting documents. Supply screen is DC only. The packet pad bench uses matching chip/exchange host rates and records its DDR-shaped harmonic surrogate; SDR switching harmonics and GPIO waveforms remain unqualified. |
| Common BLE/wideband RX, TX and combined RF-chain screens | Shared RX/TX factories, legal gain settings, package defaults, converter/comparator assumptions and stimulus records. Shared RF entry points reject wired configurations even when their document fingerprints agree. Adverse frontend/comparator corners own hypothetical snapshots; source-noise scaling remains an explicit probe assumption. TX records quantized drive gain, cutoff and external load hypothesis before clock admission. |
| Converter timing/loading and common RF/wired envelope | Each reference, switch-loading, noise or regeneration variant owns its snapshot, electrical environment and clock result. Package comparisons use recorded uncertainty overrides. Rejected clocks retain variant identity; fixed-duration SAR controls are explicitly simplified. |
| Wired readiness, feed-failure and CDR comparisons | Shared wired configuration/package. Decoupling/feed changes are hypothetical snapshots; loop, noise, coupling and switching-pulse alternatives are explicit candidate assumptions. Constant-clock/rail and noiseless-detector controls remain diagnostic interventions. |
| Direction-control audit and turnaround requirement budget | Resolved RX/TX settings, host rates, shared startup/settling and converter-completion bounds. Synthetic payload and FPGA lookahead/prefill remain explicit assumptions; no analog turnaround qualification. |
| TX current numerical probes | Shared TX inventory, package and differential-input model. Imposed current and delay sensitivity are explicit diagnostic inputs; analytical tone and serialized-state comparisons remain independent checks. |
| Phase-bound load-only handover | Shared package catalog and explicit corner overrides for both endpoints; joined phase evidence must match the supplied design identity as well as source hashes. The former fixed 52 mA assertion is removed; current difference comes from endpoint inventories. Full joined campaign awaits regenerated phase evidence. |
| Switching-load and full-package handovers | One snapshot resolves both endpoints; current pulses are checked against each owner allocation. Results and captured continuation state carry configuration/provenance. Prescribed transition envelopes and passive input fixtures remain explicit assumptions. |
| Wideband diagnosis | Shared RX configuration and package corners. Removed impairments and clock-input model overrides are recorded as explicit counterfactuals; they are not selectable controls or revised circuit specifications. Full diagnostic sweep not rerun. |
| Baseline assembly | Summary cases resolve shared package corners; RF RX and TX own separate configurations/current inventories. Resolution comparisons use legal gain. Wired RX now shares pad capacitance, CTLE gain/poles and CDR noise/holdover with recovery, including the local RX supply-delay law rather than TX reference phase. Reduced remote-source/noise fixtures are recorded explicitly. Supplied packet/converter/diagnostic campaign roots must match the snapshot before assembly starts; missing or foreign identity fails. Explicit whole-campaign hypothetical snapshots remain admissible. The baseline source manifest includes the shared loader and RF inventory adapter. The full runner compares declared dependencies before and after all campaigns and rejects changes; direct assembly labels its hashes as assembly-time only. This guards the declared list, not a proven exhaustive dependency closure. Complete report regeneration and nested campaign provenance review remain outstanding. |
| Monitor/recovery command fixture | Shared RF /256 configuration matches its synthetic payload rate; wired RX/TX use a duplex configuration. Clock-gap, monitor and independent peer assumptions are recorded per result. Carrier and sample rates derive from the resolved configuration. The complete two-engine monitor-recovery campaign has been rerun: payload prefixes, fault/recovery and stale-epoch rejection pass; observations remain synthetic. |
| Package clock loss | Shared snapshot, final RF configuration and capture provenance are carried into the fault result and retained state. Foreign captures fail before computation; unbound numerical inputs are explicit. |
| Retained SAR retune | Shared endpoint configurations and converter parameters reach the actual SAR solver. Package identity conflicts fail; result and captured state preserve provenance. Independent numerical captures without chip configuration markers are labeled fixtures; chip captures require provenance. Clock-loss continuation validates all input capture identities and passes shared converter parameters to SAR; full coupled refinement/recovery has been rerun in `shared_design_continuation_verification`. |
| Extended/recovery transport replay | Supplied design controls startup, host rates and converter completion; explicit filter settings replace undefined variables. Capture provenance conflicts fail before replay; independent numerical inputs remain labeled unbound fixtures, while chip configuration markers require provenance. Analog SAR retune and finite, extended and fault-recovery replay share endpoint-record reconstruction and typed captured-scenario loading. Finite replay records each endpoint's actual overrides and operating assumptions; these do not imply that its digital-only replay simulates analog loading. A design-bound retune or replay requires both endpoint records; missing records cannot silently select nominal settings. Extended and fault-recovery replay resolve and record their endpoint/scenario before numerical or supply rejection, so early failures retain the same configuration validation as payload runs. Independent word fixtures retain their explicit unbound path. Recovery configuration follows captured carrier/divider values; a boundary test checks actual initial configuration at 2.426 GHz `/128`, but complete fault/recovery at that setting remains unverified. Extended replay configures both sides of rearm from captured settings; independent-word checks cover `/64` and `/128` with explicit compatible filters and bit conservation. Extended independent-word rearm/conservation is exercised; the retained SAR recovery trajectory has also been rerun for this migration. |
| Finite SAR transport replay | Shared converter completion timing, startup and verified captured endpoint rates; explicit filter settings. Before/after labels select endpoints, including a destination-only wired-to-RF capture; replay no longer assumes positional stages or divide-by-64 sampling. A divide-by-128 destination with explicit 5 MHz filters preserves independently checked bit conservation. Mismatched capture provenance is rejected. Unbound independent words remain labeled transport-only fixtures. |
| Reference startup | Shared startup guard, sample rate and converter parameters. Quarter-current reference is a hypothetical circuit; discharged state, constant rail/input and noiseless operation are explicit stimuli. |
| Reference-input requirement and passive numerical probes | 54 dB requires a distinct hypothetical PGA snapshot; baseline configuration rejects it. Package sweeps use recorded uncertainty overrides. Independent nodal, conservation, transient-refinement and continuation comparisons remain numerical checks. |
| Reference-input internal-current, RF and wake campaigns | Shared RF/wired settings, legal configured RX gain and owned TX driver bias. Current spectra and passive clock-input fixtures remain explicit hypotheses; single-ended input is a diagnostic substitution. Wake clock rejection retains every case and its design context. |
| Internal decoupling screen | Capacitance/ESR changes own hypothetical circuit snapshots; ESL uncertainty is a Scenario override. Area multipliers use the shared baseline capacitance. No physical realizability or full campaign rerun claimed. |
| Return-routing and reference-return comparisons | Shared inventory, legal RF gain and explicit package overrides. Reference-return records its single-ended input substitution, source amplitude and downstream sensitivity separately. Alternative return/supply routing and USB-like passive loads remain labeled topology fixtures, not selectable settings. Full campaign awaits rerun. |
| Internal sensitivity rescaling | One snapshot follows pulse results and negative-sign replays. Independent covariance identity is preserved; missing edge covariance is reported as unavailable. Full physical campaign remains conditional. |
| Internal switching/pulse and RF payload screens | Shared resolved RF/wired RX operating points and owner current limits; RF payload uses the resolved gain and records wanted/blocker stimuli. Rejected clocks retain case identity and skip receiver execution. Per-case pulse shape, phase, scale and source amplitude remain explicit stimuli; full campaigns await rerun. |
| Internal phase bounds | Shared RF/wired configurations; feed variants, package overrides and current/source hypotheses are separately recorded. Over-budget pulses are rejected without relaxing owner allocations. |
| Historical USB rate audit | Retains source artifact hash and available source/case provenance. Current internal-current diagnostic uses the shared USB configuration but is not combined with historical host-only peaks; no cross-design cancellation bound is claimed. |
| USB HS pad/rate comparison | Pad cases use shared USB inventory and host-follow settings. Spectral-rate/legacy framed-timing sweeps are explicit diagnostic interventions, not legal configurations; their base design identity stays visible. |
| USB static-voltage comparison | Shared USB settings/current owners and package overrides. Nominal current is included alongside explicitly labeled DC load substitutions; voltage corners retain nominal AC spectra. |
| USB internal-current pad campaign | Shared USB current inventory and host-follow rates; explicit pulse scales and termination/bond fixtures. Host spectra remain a DDR-shaped surrogate. Independent passive pad-feedback checks are retained. |
| USB feed probe | Shared 480 Mb/s USB inventory and 100 MHz host-follow; feed variants own hypothetical snapshots. Released-pad termination/bond fixtures and DDR-shaped host harmonic surrogate are explicit. No assigned internal switching spectrum; not a worst-case supply bound. |
| Reference payload campaign | Shared snapshot and package overrides; legal resolved RX gain and separately configured TX inventory/clock acceptance. Split-return and single-ended source-swing comparisons are explicit counterfactual input fixtures. Rejection-path binding checked; full payload sweep awaits rerun. |
| Calibration observation budget | Shared native ADC precision and comparator noise, with an explicit diagnostic residual-tolerance argument. Unity positive quantizer span, Gaussian independence, confidence/sample-count grid and historical comparison bound are reported assumptions, not calibration approval or legal chip settings. Changed-noise propagation is checked independently. Shared comparator RMS noise must be finite and nonnegative (not boolean); an explicit zero-noise case still requires at least one observation when the quantization allowance permits the target. |
| RF feed probes | Shared RX factory; feed-resistance changes are hypothetical snapshots. Assigned current and sensitivity probes retain rejected load/clock cases without forcing packet execution. Phase-path removals remain diagnostic interventions. All four CLI modes use the shared current-source manifest, check freshness before every save (including rejection), and retain design identity. Runtime checks across all modes cover 36 project modules and four data inputs; the former historical-evidence manifest dependency is removed. |
| RF memory/filter probes | Shared RX configuration, frontend/converter parameters and package defaults. Assigned history, switching pulses and finite-integrator candidates are recorded; cost accounting uses the same snapshot. |
| TX amplifier current requirement | Optional supplied snapshot owns the candidate branch ceiling and is recorded in the result. Fixed temperature, noise, bandwidth and reserve are explicit simplified assumptions; this is not amplifier feasibility evidence. |
| RF pre-emphasis | One snapshot for DAC ENOB, TX error allocation and spectral measurement. Different ENOB is hypothetical; unsupported converter formats fail. Filter candidates and simplified rail/phase/nonlinearity remain diagnostic assumptions. |

Parameter ownership and behavior:

| Parameters | Authoritative owner | Integrated consumers and validation |
|---|---|---|
| Reference rejection gain/pole | `refbuf.parameters` | Electrical seed, reference-input, converter native/FFT feedback, driver wake and retained lifecycle; changed-law analytical checks and missing-parameter rejection |
| Clock supply sensitivity/delay pole | `contract.physical_services.external_clock_input` | Bound clock/converter/lifecycle paths; `refinput.shared_parameter_sources` references these fields without copying their values |
| Differential reference source amplitude | `contract.physical_services.external_clock_input.source_differential_peak_v` | `refpad.shared_parameter_sources` names the owner; duplicate numeric pad values are rejected; a 0.75 V variant reaches the delivered-clock path and direct paired-input helpers; explicit source stimuli are recorded, and missing bound source configuration fails even with an override |
| Reference capacitance | `refpad` | Paired input, converter feedback and package lifecycle; conflicting bound capacitance is rejected |
| Signal bond/source/mutual parameters | `model_assumptions.reference_input_package` | Shared passive resolver and reduced/full nodal/descriptor comparisons; distinct from power-network package assumptions |
| Local USB pad current, termination, pulls, FS output resistance and squelch | `usbhs.parameters` and `usbfs.parameters` | `SharedWiredPad.from_architecture` binds all six values; missing/invalid fields fail. Changed-value steady-state nodal checks distinguish the local chip from the independent peer. Primitive examples retain their own defaults. |
| Converter parameters | SAR inventory adapter | Every `SARParameters` field is required exactly once; bound partial dictionaries cannot inherit primitive defaults |
| RX/TX filter settings | Paired filter inventory | Cutoffs use the intersection of paired ranges; unsupported orders, shapes and settings fail explicitly |
| PGA gain codes/response pole | Paired receiver inventory | Retained SAR, BLE and Wi-Fi gain feedback; host observation windows and policies remain separate assumptions |

Additional shared ownership includes the reduced PDN network, both host
transition charges, startup guard, transport rates, direction-appropriate queue
allocations, LNA selection, converter formats and paired RF distortion targets.
Each hypothetical circuit change retains its parent fingerprint. Assigned
package, device, noise and current values remain unmeasured. Temperature affects
RF/converter thermal noise within the supported window; other temperature
coefficients remain unmodeled. LNA gain selection does not yet change NF, IIP3 or
current allocation. Unsupported paired formats, headroom, filter orders or
coefficient changes fail instead of silently selecting another implementation.

Reference acceptance is owned by
`model_assumptions.reference_input_acceptance`: threshold, effective-input peak
and individual-leg peak are distinct assigned limits, not protection ratings.
The seed, clock acceptance/noise conversion, converter feedback and retained
lifecycle consume them. The differential source amplitude is contract-owned;
direct helpers resolve it unless given an explicit stimulus and record the
actual value even when rejecting a clock. Source leg skew is separately owned by
`contract.physical_services.external_clock_input.source_leg_skew_s`; driven
input and retained package-lifecycle source phasors consume it independently
of component mismatch. Primitive mismatch examples retain their own 5 ps probe.
The internal phase-bound and USB feed probes use the same environment-bound
passive adapter, including capacitance/package/skew. The feed probe supplies its
owned wired-pad capacitance explicitly, avoiding a later disk reload. The
passive `hs_pad_transfer` helper no longer reloads a design when capacitance
is omitted: that path is an independent primitive example. Intended-chip
callers pass their environment-owned matrix explicitly. Phase-bound
main/ADC/current calculations use the shared clock sensitivity and delay pole;
the main input screen uses shared acceptance limits. The labeled 20/35 mV ADC,
35 mV added-current and source-loss threshold sweeps remain explicit comparison
fixtures. A changed sensitivity/pole test checks the analytical delay transfer.
Full host forcing, D2H/H2D separation and retained package clock-off forcing
share `partitioned_d2h_sources`, including transition charge and harmonic count.
Changed-charge Fourier checks verify the D2H current law; full handover checks
verify that D2H changes affect clock-on forcing but not persistent H2D/core
forcing after clock-off. Primitive clock/passive examples
retain their independent defaults. The reduced/full/descriptor comparison
explicitly records its independent source amplitude, phase, skew probes and
random seed; shared package ownership does not make those source stimuli nominal. Bound paths reject incomplete inputs.

The shared loader validates positive finite USB pad parameters, complete pad
network values and odd-mode capacitance accounting before constructing a model.
Malformed/missing values cannot defer failure until an integrated pad is used.

`SharedWiredPad.from_architecture` binds the pad network and local USB current,
termination, pulls, output resistance and squelch. Local driver leakage,
reference, supply sensitivity, conductance, trim and compliance headroom come
from `model_assumptions.wired_pad_driver`; instantaneous single-ended sensing
comes from `wired_pad_sensing`. Nominal zero output conductance/supply sensitivity
are ideal assumptions, not demonstrated silicon. Missing clamp branches mean
omitted protection, not fail-safe qualification. Explicit probes override the
shared baseline and keep their construction records. The independent peer does
not inherit local-chip parameter changes. Changed-value checks compare actual
pad voltages with independent nodal equations.

Pads retain a copied construction context with canonical architecture hash and
probe overrides. Configured USB exchanges reject foreign pad architecture
before advancing state and retain that context in results, including rejected
packets. Primitive pads are labeled independent fixtures. This checks origin;
USB exchange results additionally capture live local/peer controls, explicit per-leg board Thevenin sources and initial pad/divider voltages. Accepted and rejected-packet results retain request/response payloads, event-grid phases, request delay/dropout/corruption, host stalls and observer cadence as scenario stimuli. All 53 USB/pad tests passed after this recording change (53.228 seconds); this is result-context verification, not new electrical qualification. Admission requires both ordinary drivers and any numeric local drive override to be released; conflicting overrides fail before exchange state advances. Explicit passive and drive overrides remain mathematical probes, not newly granted silicon settings. This observation is not a restart checkpoint and does not fully audit later mutations or every injected digital model.
Drive commands with omitted values use the constructed pad's allocations.
Raw sensing permits explicit diagnostic thresholds. Integrated mode-sequence
and USB lifecycle callers use the configured local termination. The static USB
output adapter also resolves current and default local termination from the
shared environment, while its remote 45 ohm load remains a fixture. It records
explicit termination overrides and retains an ideal constant-current assumption;
this is not a finite-compliance driver qualification. Independent DC nodal and
current-conservation checks cover the shared parameter binding. Static results
copy design/configuration/scenario metadata and the supplied DC ledger; the
ideal current source, 20 mV guard and remote load are recorded diagnostic
assumptions rather than implicit physical guarantees. The USB campaign
centers local termination probes on the shared value (including an explicit
±5% asymmetry), and spectral-rate substitutions carry their intervention
metadata through the static result. The trim-envelope inverse
screen likewise reads local current, termination, reference/compliance and leakage
from the supplied architecture; source-resistance/sensitivity sweeps and remote
load uncertainty are explicit probes. A packet with conflicting architecture
provenance is rejected before combining its rail bounds with those values.
The inverse result copies the available input configuration, scenario, operating
conditions and source manifest; absent input metadata stays absent.

`usb_supply_environment` is the shared USB electrical factory. Host-follow sets
both directional spectral rates; H2D/D2H internal transition charges come from
`model_assumptions.host_switching`. Independent Fourier checks cover charge
propagation through initial spectra, partitioned sources and pad-ground tones.
The host waveform remains a DDR-shaped surrogate, not SDR electrical evidence.
USB response-budget and exchange adapters require bidirectional 480 Mb/s,
duplex host-follow. Retained host state binds its first resolved configuration (or independent fixture scope); a later exchange cannot change that identity without a fresh transport epoch. Injected chip engine and rates must agree; differing startup
guards are recorded diagnostic overrides. Accepted and rejected exchanges retain a detached snapshot of all injected behavioral assumptions and identify constant versus callback-driven pad supply. Those extra scalar assumptions are caller fixtures, not proof of shared analog behavior; callback waveform provenance remains the calling bench’s responsibility. FPGA response time is a stimulus. The common USB
packet campaign resolves transport assumptions through the shared factory and
then explicitly replaces startup with zero for its prequalified harness. Its
local termination comes from the constructed pad, and baseline driver cases
retain shared laws rather than claiming ideal behavior for every supplied design.
Construction checks cover changed current/termination. The four-case nominal
packet campaign has also been rerun: all cases delivered 48 reply bits, with
matching baseline timing at both resolution settings. Five configuration
records, pad architecture identities and 55 declared source hashes verified.
The finite untrimmed driver decoded at about 318 mV TX minimum, below the
separate illustrative 360 mV trim gate; decoding does not close that budget.
This remains a prequalified, host-only forcing fixture, not a startup, full-PDN
or USB compliance result. Later source edits require another freshness check.

Transport binding follows the selected encoding: direct bytes for
response-critical bursts and exclusive dense framing for sustained wired/RF
traffic. Shared ingress/egress numbers are planning budgets, not verified RTL
storage depths. Half-queue prefill and fixed-record alignment examples are
bench policies. Applying byte streaming indiscriminately would change the
architecture rather than complete this migration.

RF packet, wideband and lifecycle adapters use direction-specific inventories,
legal LNA/PGA settings, converter/reference laws and filter ranges. Filters use
the intersection of paired ranges; wider experimental filters and 54 dB PGA
requirements own hypothetical snapshots. Supply/current references and selected
RF output distortion are shared assumptions. RX/TX and response-budget adapters
reject conflicting contract/configuration identities before processing.
Separately settled narrowband RX/TX configurations do not constitute a retained
analog turnaround simulation.

Wired recovery resolves balanced pad capacitance, CTLE poles/gain and CDR
noise/holdover/supply sensitivity. RX delay sensitivity is separate from TX
reference timing. Equalizer bypass, reduced remote-source models, prescribed
rails/clocks and noiseless detectors remain explicit diagnostics. The fixed
2.5 Gb/s readiness peer requires matching TX/duplex configuration and provenance.
Its pre-source observations explicitly record zero signal for causal replay.

Snapshot and evidence rules:

- Integrated factories accept an independent contract without a supplied
  snapshot only when it matches the current shared contract; historical or
  modified documents require an explicit snapshot. Package catalogs resolve
  from that snapshot, not import-time disk state.
- Design-bound converter/receiver/transport environments cannot lose required
  fields and fall back to primitive defaults. Every SAR parameter is resolved;
  the independent primitive remains available for mathematical examples.
- Results copy design/configuration, scenario, operating-condition and diagnostic
  metadata. Direct clock reports, packet factories, feedback wrappers and Wi-Fi
  contexts have isolation checks. This is reviewed coverage, not proof for all
  remaining result paths.
- Capture replay and continuation preserve each input's own context. Foreign
  fingerprints fail; absent metadata remains an unbound numerical fixture.
  Frozen-waveform TX inverse audits require provenance except their explicitly
  reasoned primitive control. Matching fingerprints do not imply matching
  schedules or one continuous operating envelope.
- Saved hypothetical variants are reconstructed independently from parent and
  before/after changes. Resolved rates and allocations are recomputed against
  that variant. Missing configurations remain unverified. Matching a variant
  does not count as nominal acceptance.
- Source manifests describe execution-time inputs. The full baseline runner
  checks declared sources before/after execution; direct assembly distinguishes
  assembly-time hashes. Subsequent source/schema changes make old runs
  historical. Never refresh a saved hash without rerunning its computation.
  Declared/static dependency coverage is not exhaustive runtime/data closure. The USB
  feed and internal phase-bound runners use the shared probe manifest plus
  their own script, record root design identity and reject source drift before
  saving. A real four-case USB feed run covered all 33 observed project Python
  modules with 56 verified hashes. The USB feed runner has one CLI path;
  runtime file-read observation also confirms all four data inputs are covered.
  The matched wired feed-failure runner similarly covers all 35 observed project
  modules and four data inputs. Its accepted and rejected nested configurations
  were independently reconstructed before regenerating the evidence. These
  audits preserve USB guard failures and wired load rejections.
  For the phase-bound runner, both the default 12-case branch and optional
  72-case feed sweep were executed under runtime import/file-read observation.
  Their manifests cover all 33 observed project modules and four data inputs;
  every reported configuration and all 56 source hashes were independently
  verified. Both evidence files were regenerated without suppressing rejected
  loads or failed sufficient bounds. This coverage is specific to those two
  executed branches, not other runners or arbitrary programmatic inputs.

Reviewed test roles:

| Test modules | Role and boundary |
| --- | --- |
| `test_gpio_screen`, `test_gpio_transient`, `test_host_margin`, `test_rail_checkpoint` | Parser, pin mapping and trace utilities checked with independent tables/waveforms; no pad performance claim. |
| `test_burst_acquisition`, `test_counted_acquisition`, `test_receive_qualification` | Synthetic edge/observation and qualification examples; no measured sampler or oscillator capability. |
| `test_fractional_divider` | Exact arithmetic for an experimental divider; independent numerical control. |
| `test_direct_stream` | Byte framing, credits and sampled-record state machines; synthetic times do not qualify physical latency or queue allocation. |
| `test_stream_codec` | Framed-stream metadata fault tests. Fixed simultaneous wire/IQ schedules are fixtures, not current chip configurations. |
| `test_he64_packet` | Independent diagnostic OFDM peer and error-measurement examples; not a complete HE compliance waveform or analog qualification. |
| `test_rf_power_calibration` | Synthetic calibration fits and validity checks; assigned operating bounds do not establish physical accuracy. |
| `test_timing_services`, `test_video_alignment` | Analytical timing/alignment and prescribed-readiness state machines; no shared-chip settling/skew claim. |
| `test_wideband_packet` | Mixed independent codecs and indirect shared-campaign boundary checks. Coded/acquisition adapters validate identity before waveform generation and copy design/configuration/conditions with actual signal levels, payload length and digest into results. Eleven wideband and five packet-factory checks pass; mocked analog boundaries remain explicit exceptions, not RF evidence. |
| `test_rf_gain_command` | Mixed command-codec fixtures and indirect `ClientBench` integration. The constructor audit now tracks this shared-design wrapper. |
| `test_bit_event_codec` | Three chip TX tests use shared startup/host timing and queue capacity with deliberate clock skew. Twelve USB tests retain one snapshot through the imported shared-pad helper, reject reloads and check result identity; their legacy framed transport is explicit. Packing, trained-return, prescribed recovered-source/CDC, and bare passive-pad observation examples remain independent fixtures; their fixed times/capacities are not current-chip timing or storage evidence. |
| `test_wifi_client_exchange` | Shared-design client/transport and receiver allocations; standalone normalized RF examples remain explicit fixtures. Direct RF-path construction honors configured gain. Nominal gain-feedback rejection and the distinct faster-PGA hypothetical control are both tested. Gain-command timing now reads sample/H2D/D2H rates from the supplied environment and records them; missing transport values fail instead of taking primitive defaults. Result context now captures the actual finite LO and converter phase-tone realizations, including direct replacements; mixing and timing use the same phase model. Helper observation/settling allocations remain illustrative and do not certify actual analog readiness. |
| `test_rf_quality_budget` | Shared error/current allocations, independent covariance and timing arithmetic, and one-snapshot waveform pre-emphasis comparisons. Mutated budgets are accounting controls; converter alternatives carry hypothetical-design identity. The standalone command defaults to the validated shared snapshot and reports its fingerprint; explicit `--inventory` inputs are independently hashed accounting fixtures. |
| `test_resource_configuration` | Independent candidate command words and service arithmetic; lifecycle admission uses shared startup/host timing and legal stopped RF/wired settings. No serialized ABI or post-switch analog qualification. |
| `test_live_control` | Shared architecture supplies live-field permissions and guards; prescribed readiness, epochs and a changed cold-start guard isolate planner behavior. No analog settling qualification. |
| `test_rf_air_timing` | Independent counter/codec examples plus shared-design launch/snapshot integration. Startup, host rates, legal RF dividers and direction-appropriate legacy queue depths come from the snapshot. Ideal clocks, prescribed readiness and explicit filter settings isolate logical scheduling; these checks do not qualify analog timing. |
| `test_contract`, `test_design_definition` | Shared snapshot/schema, configuration, provenance and parameter-propagation checks, plus malformed independent fixtures. Static constructor inventory is a review aid, not proof of every transitive calculation. |
| `test_power` | Shared contract and snapshot for current budget extrapolation; historical current evidence has its own content digest. Results copy the actual multiplier, allowances, domain budgets and segment allocation. Independent arithmetic and post-run mutation checks cover this record; mutated ownership/current examples remain independent negative controls. |
| `test_shared_pad_controls` | Shared architecture-to-pad adapter checks use the specification and an independent nodal-capacitance equation, without requiring primitive defaults to match the chip. Passive-network, clamp and conservation fixtures remain independent. Matching the baseline capacitance is not pad qualification. |
| `test_usb_selected_timing` | Resolved shared-design USB timing/host-follow and retained-lifecycle checks use the same 480 Mb/s configuration and normal pad inventory. Independent credit, epoch and packet checks remain. Short-startup timeout, low rail and excessive load remain deliberate fault fixtures; unconfigured arithmetic examples remain independent. Assigned readiness does not establish electrical turnaround. |
| `test_ble_packet` | Independent published packet vector, blind decoder, gain-law and playback controls; joined packet tests now use one shared snapshot with separate RX/TX configurations and explicit wanted/blocker stimuli. Assigned-ENOB conversion and seed clock spectra are simplified; no loaded differential-input, retained-SAR or physical turnaround qualification. |
| `test_rf_mixer_phase` | Independent mixer, filter, replay and historical rail fixtures. Its synthetic 10 MS/s / 12-bit stream and 5 nH package are not current-chip allocations. |
| `test_baseline_envelope` | Shared readiness/recovery, supply and converter integration plus independent analytical/adverse controls. Current wired composition and recovery preserve the caller snapshot; TX headroom checks use shared output parameters and resolved gain. Bare SAR, nodal-network, prescribed-monitor and state-continuity examples isolate mathematical laws rather than chip operating points. |
| `test_robustness_envelope` | Mixed shared contract checks and independent diagnostic studies. Contract-only `weak_rf_recipe_controls`, `lora_recovery_suite` and `diagnostic_observability_suite` use explicitly assigned impairments, training and waveform alternatives. `wired_operating_envelopes` sweeps hypothetical channel/pad values; `wired_resource_requirements` computes inverse budgets. These are not selected-chip configuration factories. Legacy resource/PDN bridges likewise cannot establish a joined current-chip operating point. |

These classifications preserve simplified and adverse exceptions. Independent
expected answers remain analytical equations, decoders, conservation laws,
known vectors and fault injection—not values computed by the same path under
test. Expected-failure counts do not measure nominal chip success.

The AST inventory in `verification/check_contract.py` reports construction
sites and reads literal `TEST_DESIGN_ROLES` declarations beside the tests.
Declarations name `shared_design` or `independent_fixture` with a reason;
method entries override class entries. Unknown roles, empty reasons and stale
entries are reported. Declared intent is separate from verified binding.
All 805 tests in 31 modules now have reviewed declarations: 386 shared-design
and 419 independent fixtures, with no unclassified tests, stale declarations or
parse errors. The contract audit regression requires complete declarations so
new or renamed tests cannot silently escape this accounting. These are intent
counts, not a verified-binding percentage. The completed review also traced shared test entry points and imported helpers,
fixed downstream ownership gaps and checked actual result records. Declarations
alone remain insufficient evidence of binding.

The audit also reports construction
sites, selected/default converter differences and untracked files. Its local
helper tracing does not prove imported-wrapper, dynamic-dispatch or transitive
parameter ownership. SPICE/PDK characterization remains a separate evidence
layer. `make transceiver-rtl-primitives` and retained `run_block_rx*.sh` checks
exercise independent digital implementation candidates; they do not establish
whole-chip SPI ABI, pad timing, analog behavior or fit.

Preserved model limitations and failures:

- The nominal 200 ns PGA response can reject fast Wi-Fi gain updates because
  settling/status buffering does not admit them. A faster 100 ns passing
  control is a hypothetical paired-PGA design. Do not restore hidden faster
  assumptions to make this test pass. Diagnostic packet outcomes are not PER.
- A changed 35 mV reference-threshold package/retune/source-loss run propagated
  the threshold into independently checked crossing roots and converged through
  retune. Its subsequent 16-sample converter continuation did not converge.
  Parameter binding therefore does not establish stable recovery there.
- Short wired payload success does not remove residual-frequency-bound failures
  or establish BER. Over-budget feed/pulse cases are load rejections, not CDR
  passes; allocations cannot be increased silently.
- The default phase-bound campaign uses the shared SAR schedule for ADC
  switching harmonics as well as event bookkeeping. Its regenerated evidence
  reconstructs all 12 configurations and verifies all 56 source hashes. Seven cases meet the sufficient per-leg
  enclosure; selected wired and all four high-inductance cases do not. Failed
  triangle bounds do not prove actual excursions or physical impossibility.
- Historical assigned-value bridges (including `joined_rf_resource_screen`,
  `rf_dc_quality_bridge`, `host_charge_pdn_bridge`,
  `bidirectional_host_receiver_screen`, `common_feed_rf_screen`,
  `local_decoupling_envelope` and `tx_clock_spur_envelope`) retain explicit
  `frozen_numerical_fixture` roles. Their fixed currents and older framing are
  not current-chip acceptance.
- Protection, source/pad/device parameters, GPIO harmonics and complete RF
  turnaround remain unqualified. Connected numerical results cannot remove
  those physical uncertainties.

Current CDR validation (2026-10-01): 224 shared-design/timing tests and 320
affected regression tests pass after phase-bank selection; after the final
active-predictor slew correction, all 17 focused CDR/timing tests pass. These
sets overlap. The earlier 842-test full-suite run predates this CDR change.
Run `python3 selected_revision_check.py --cdr-selected` from `verification`
for the separate two-trajectory acquired-state tracking gate.
Run `python3 selected_revision_check.py --cdr-cold` for the independent nominal
local-clock acquisition gate. Its430k-bit trajectory qualifies at bit344686,
with34.70ppm peak held-out tracking error, zero scored errors and an80-bit peak
observation queue against1024bits capacity. Acceptance requires acquisition
within the configured timeout and fault-free bounded observation transport.
A focused acceptance test rejects missing/late acquisition and queue faults
even when tracking metrics pass. This does not yet prove source-loss or changed
SSC recovery, arbitrary initial oscillator offset, or physical implementation.


Uniform and
explicit-timestamp RF paths now use the same causal DAC-edge rule: the newly
latched code cannot drive the preceding interval. The recovery fixture injects
a transition gap beyond the shared holdover setting. Clock sensitivity, area
reserve and RF branch-current checks follow the shared configuration instead of
superseded constants; dangling test-role metadata is removed. The independent
0.9 V reference-target and fractional-ripple checks are included in this suite.

Regression success does not establish complete capability or physical
feasibility. Expected adverse-case rejection is still a passing test, and
`make transceiver-behavioral` is a separate executable scenario campaign. Its
nominal combined-clock HE20 diagnostic now requires successful decoding at
−48, 0, +48 kHz offset rather than retaining an obsolete expected-failure assertion;
its 10% EVM limit and damaged-source rejection checks remain unchanged.
The recorded complete behavioral campaign predates phase-bank selection and
must not be presented as a current full-chip rerun. Its original hashes remain
intact; the selected CDR campaign records its own sources and scope.

Runtime construction is a review aid: intended-chip tests must construct or
inherit a shared snapshot, while independent mathematical examples, codecs,
fault fixtures and structural guards may legitimately have none. A snapshot's
presence does not prove downstream parameter ownership; mocked, inherited and
subprocess construction paths require the role review above.
A refreshed static audit finds 805 methods in 31 modules. All four direct
`operating_environment` call sites were inspected: `common_feed_rf_screen`,
`local_decoupling_envelope` and `tx_clock_spur_envelope` explicitly report
`frozen_numerical_fixture` and `current_chip_evidence=False`; the remaining
site is the internal electrical seed used by the inventory adapter, which
replaces the legacy current ledger with the shared block allocation. This
classifies those construction sites only; it does not prove every downstream
parameter or caller is correctly bound. Wired composition, encoded lifecycle
and recovery tests now retain their original snapshot and fail if their helpers
try to reload it. The two contract-based TX headroom sweeps use the selected
driver/output parameters, quantized gain and RF current allocation. Their angular
sweeps and resistive voltage-division checks remain independent numerical checks;
the explicitly out-of-range gain example remains an independent counterexample. Current review evidence and the RF
chain acceptance audit remain incomplete.

The selected framed H2D rate is now derived from
`contract.transport.profiles.ddr156.clock_hz × edges` and recorded as
`resolved_configuration.h2d_word_hz`. Host-follow uses its resolved input rate.
The electrical seed, transport adapter and Wi-Fi gain command consume this
value; missing/invalid profile inputs fail during snapshot construction. The
changed-profile regression checks an independent command-arrival calculation as
well as actual supply-spectrum and transport inputs. This binds the existing
selected service; it does not qualify another FPGA I/O rate or physical timing.
Older saved configurations lacking the derived field require regeneration.
The common host-source boundary also requires finite, nonnegative loading and
charge values and positive host rates/pulse time constants for design-bound
records. Missing fields, booleans, negative values and nonfinite numbers fail
before pad-return or partitioned-current calculations. Fault-injection checks
exercise all three source consumers; independent numerical fixtures retain
separate input semantics. This validates supplied values, not their physical
accuracy or complete reconstruction from provenance.

Shared pad construction now records its circuit parameters as well as its
architecture identity and declared probes. Before reporting, advancing either
pad solver, or computing small-signal transfer, it rejects unrecorded changes
to those parameters. This covers scalar current/termination/sensing values,
current-source dictionaries and capacitance matrices; a detached report cannot
mutate the live circuit. Runtime mode, drive, local/peer passive controls and
charge state remain separate. Independent primitive pads retain editable
numerical examples. This protects construction consistency, not physical pad
qualification or a complete restart-state record.

Delivered clocks retain a detached snapshot of the inputs they consume,
including periodic edges, finite load trajectories and supplied design context.
Their inspection property also returns a copy. Prepared rail/reference samplers
own their coefficient, time and response arrays even when the caller supplies
contiguous NumPy storage. Rebuild these objects after changing a feedback
trajectory; modifying the input dictionary cannot partially change an existing
clock or sampler. Regression checks cover both periodic edges and an independent
constant-delay example, plus unchanged rail/reference sampling after mutation.
These checks are included in the full-suite checkpoint above.

The common `validate_transport_binding` boundary is used by the digital
transport adapter and shared RF entry points. It rejects missing, nonfinite,
nonpositive or boolean transport inputs, missing/empty provenance, and rate
mismatches against the resolved configuration before RF processing. Unbound
primitive fixtures retain independent rates. This comparison establishes
internal consistency of the supplied record, not independent reconstruction of
an arbitrary caller-mutated record from its source files.

The wired TX helper's `frames` argument uses the behavioral scheduler's nominal
mode-1 duration; it does not select the H2D service clock. The shared H2D rate
independently controls host event timing and capacity. A changed-contract probe
at 300 Mword/s checks the analytical capacity and actual captured-bit response.
Its deliberately reduced 1536-bit queue underflows at both nominal and changed
rates before the first CDC block commits; this is an ownership regression, not
successful-link evidence. The separate nominal queue/chunking test verifies the
passing transport case.

Package-handover continuation reuses the RF endpoint's complete ADC switching
inputs, including its resolved sampling rate, rather than reconstructing a
separate divide-by-64 load. The captured endpoint context records those ADC
inputs alongside the resolved configuration. Wired endpoints carry no ADC
forcing. The shared
reference-supply regression also exercises a legal divide-by-128 endpoint and
checks the retained ADC fundamental against the independently calculated rate.
This closes an input-ownership mismatch; it does not qualify the assigned ADC
current waveform or handover readiness.

Retained-state context validation rejects empty/null design identity and captures
that carry resolved configurations or endpoint conditions without provenance.
Removing a fingerprint therefore cannot silently downgrade a chip capture to an
independent numerical fixture. Captures containing only independent numerical
inputs remain valid fixtures. Foreign design identities are rejected before
recovery replay accesses or advances retained state.

### Test pruning

The current inventory is **805 tests across 31 modules**: the 822-test review
led to removal of 20 approved retirement candidates, followed by a gain-command
rate-binding regression, a packet supply-law propagation regression and a TX
input/provenance regression. Verification is recorded above.

| Removed coverage | Count |
|---|---:|
| `test_frame_codec.CodecTests`: legacy full-frame CRC codec | 6 |
| `test_transport.TransportTests`: historical scheduling matrix | 7 |
| `test_robustness_envelope.ResourceJoinTests`: frozen resource/rail experiments | 3 |
| Historical host-driven wired/RF and common-feed RF scenarios in `test_robustness_envelope` | 3 |
| Historical FIFO/load/package mapping check in `test_rf_mixer_phase` | 1 |

The two retired test files and their `transceiver-contract` Makefile entries
are removed. This is test pruning, not retirement of every underlying legacy
implementation: scheduler and numerical helper callers remain. Their historical
results do not qualify the current chip.

Independent mathematical examples, adverse fixtures, conservation laws,
retained-state checks, current stream/event/direct codecs and shared-design
parameter guards remain. No acceptance threshold or chip parameter changed.
The [open-issue register](../../spec/risk-priorities.md#open-issue-register)
continues to distinguish model regressions from unresolved design requirements.

The completed task is **test binding to the shared configured design**.
Analog-performance qualification remains separate. The current inventory contains 805
tests in 31 modules. Local shared-entry tracing and explicit test-role declarations
are separate review aids; neither alone proves that all downstream parameters
come from the selected configuration.
The robustness review removed implicit primitive queue capacities from the
shared analog-readiness and missing-clock tests: they now use the contract
ingress allocation. Qualification events, payload widths and injected missing
edges remain explicit transport stimuli. Seven affected shared-path and audit
checks pass; the separate 55-test bit-event suite also passes after its retained
snapshot migration. In the baseline module, packet TX now resolves native DAC
width from its retained design instead of supplying a duplicate value. Direction
gating comparisons retain one snapshot and use its resolved sample rate. Two
USB pad tests explicitly forward a snapshot through their imported helpers and
check returned identity. The 29 affected baseline checks and four USB pad checks
pass. The final regression checkpoint and subsequent affected checks are listed below.

The per-test role review and shared-path migration are complete for the 805-test
suite. New intended-chip tests must start from the same loader and retain the
configuration and declared deviations through their results. The declaration
guard catches missing accounting; parameter propagation still needs meaningful
checks whenever a factory or circuit model changes.

The full 805-test regression passed in 564.796 seconds after the role review
and ownership fixes. A subsequent USB FS result-metadata change passed seven
affected checks; it does not change the voltage equations. The host-load intervention now uses a reasoned `Scenario` override, and
the differential-network test forwards and verifies its retained snapshot.

The USB full-speed static voltage screen now consumes
`blocks.usbfs.parameters.effective_output_r_ohm` (45 ohms in the current
design), replacing its independent 30-ohm constant. Its environment retains
the shared FS parameters and missing, nonpositive or nonfinite resistance
fails before calculation. A reasoned 60-ohm snapshot changes the actual DC
result, checked against an independent resistor-divider equation. Saved USB
voltage evidence from the old 30-ohm screen is stale and must be recomputed
before being used as current-design evidence.

Standalone `usb_static_output` results now retain design identity, resolved
configuration, scenario, operating conditions, evaluated DC ledger and explicit
load/driver assumptions, matching the HS result boundary. The changed-resistance
regression checks these fields and mutates the returned nested records to prove
they cannot modify the source environment or ledger. A test-source read audit
found no independent design-JSON reads in intended-chip tests; remaining reads
are temporary audit files, explicit frozen numerical examples and the power
test's declared historical-current extrapolation input.

Shared transport now requires a nonempty resolved configuration whenever
design provenance is present. Missing, null and malformed configurations fail;
explicitly unbound numerical fixtures retain their separate path. All 45 affected
transport, USB selected-timing, resource and RF air-timing checks pass.

Legacy USB burst results now retain the actual pad construction and initial/
final controls in every success, playback-fault, packet-rejection and malformed-
frame result. The role lifecycle also records its FS and HS controls. These
use `SharedWiredPad.construction_context()` and `control_context()`; historical
host-rate fixtures remain explicitly simplified and are not relabeled as legal
whole-chip configurations. All 59 affected bit-event and USB pad checks pass
in 94.960 seconds, including successful, rejected and faulted result contexts.

The completion audit covers the current intended-chip tests and their shared
configuration paths. Independent equations, primitive defaults and explicitly
scoped counterfactual experiments remain supported. Recorded adverse or
nonconverged outcomes satisfy consistency without becoming nominal passes.
Physical qualification and protocol success remain separate obligations.

Reference voltage now consumes `blocks.refbuf.parameters.target_v` in the shared
RF samplers and package-handover, clock-loss and retained-SAR paths. Fractional
feedback is multiplied by the target before addition to volts. The configured
environment records that target with its coupling and pole parameters; missing
or invalid targets fail. ADC reference providers return volts; DAC transfers use
a dimensionless reference ratio with their separately owned full-scale voltage.
Independent normalized primitive examples retain a 1 V default. The changed-target
sampler regression checks an independent cosine/interpolation equation and
snapshot isolation. Executed 1.0 V and 0.9 V package-handover and clock-loss
trajectories confirm reference-waveform scaling by 0.9 with unchanged rail
waveforms (2e-14 V absolute comparison tolerance). This verifies the linear
reference observer. The retained-SAR regression also uses a declared 0.9 V
target and independently checks every iteration's target-scaled recharge
feedback at the actual sample times, continuity of reference state across the
transition, and charge accounting. Its sinusoidal clock/constant-rail fixture
is explicit; this does not qualify full-package recovery or physical readiness.
The earlier evidence refresh was deliberately stopped before these source edits.
Saved physical-campaign evidence predating these changes remains stale. Rerun
a campaign before citing its results for the current source revision; frozen
mathematical fixtures remain explicitly identified as such.

| Requirement | Completion evidence | Boundary |
| --- | --- | --- |
| One authoritative design | Frozen `DesignDefinition` loads the architecture and contract; configurations retain their snapshot. All 805 tests were reviewed, including setup and imported helpers. No intended-chip test independently reads either design JSON. | 386 shared-design checks; 419 independent fixtures. Counts are accounting, not proof of physical completeness. |
| Settings, uncertainty and hypothetical circuits remain distinct | `ResolvedConfiguration` rejects unsupported settings; typed `Scenario` requires reasons and known uncertainty fields; hypothetical snapshots preserve parent identity and changes. Gain-range and scenario propagation regressions exercise these boundaries. | Malformed-document and synthetic observation tests intentionally bypass normal construction to verify rejection or independent mathematics. |
| Parameters reach the calculations | Changed voltage, reference target, gain, converter width, aperture, host load/rate, startup, queue, USB resistance and control-divider tests check resulting waveforms, codes, timing or conservation. Reviewed shared entry points forward retained snapshots. | Diagnostic stimuli and simplified clocks/topologies are recorded separately; their performance is assumed. |
| Required inputs cannot fall back to primitive defaults | Bound RF, SAR, reference, filter, pad and transport paths reject missing/conflicting inputs. Shared transport now also rejects absent, null or malformed resolved configurations. | Deliberately unbound primitive tests retain defaults. All 45 affected transport/USB/RF timing checks pass after the final guard change. |
| Results retain actual identity and conditions | Packet, wired, USB, clock and retained-state adapters preserve fingerprints, configuration and deviations. FS/HS results include evaluated DC ledgers; legacy USB rows include actual pad construction and controls, including failure paths. Mutation tests verify detached records. | A historical transport fixture records its actual pad and fixture controls rather than falsely claiming a legal whole-chip configuration. |
| Expected answers remain independent | Existing analytical transfer laws, Fourier integrals, root solvers, independent decoders, KCL/charge/power conservation and fault injection are retained. | Snapshot identity assertions supplement these checks; they do not replace numerical oracles. |
| Validation matches executed sources | Full 805-test suite passed in 564.796 s before the final small boundary fixes; afterward 7 USB metadata checks, 45 transport/timing checks and 59 pad/bit-event checks passed. Role audit reports no omissions, stale entries or parse errors. | This checkpoint does not refresh stale physical-campaign evidence or claim all optional standalone runner branches were executed. |

The following numeric owners are used by the migrated paths. Characterization
reference voltages are distinct from the actual board supply.

| Quantity | Shared owner |
| --- | --- |
| Board supply | `blocks.board.parameters.analog_supply_v` and `digital_supply_v` |
| Wired gain reference | `model_assumptions.wired_supply_gain.parameters.reference_voltage_v` |
| RF RX gain/headroom references | `model_assumptions.rf_receive_supply.parameters` |
| RF TX gain/bound reference | `blocks.rfdriver.parameters.gain_reference_v` |
| D2H charging voltage | `contract.physical_services.host_output.voltage_v` |
| ADC aperture jitter | `model_assumptions.paired_adc.parameters.aperture_rms_s` |
| Active control-clock divider | `control_semantics.scheduler_clock_divider` |

Inventory, partitioned DC, return-routing and USB diagnostic rate sweeps retain
the board voltage; the common-feed reduction rejects unequal analog/digital
supplies. Gain/reference propagation has been exercised through packet and
joined lifecycle calculations. D2H voltage variation is checked against an
independent pulse Fourier integral; external FPGA drive remains a separate
assumption. These assigned laws are not measured device behavior.

Configurations record physical H2D and control frequencies. The selected ÷4
control divider yields 39.0625 MHz for framed DDR and 25 MHz for 100 MHz SDR
host-follow. A declared ÷8 circuit variant reaches the environment and turnaround
budget. Packet entry points reject missing/invalid counter rates before processing
and record the rate used. A legal RF ÷128 packet exchange checks actual converter
edge arrays against 128/2.426 GHz and decodes request/reply under assigned ENOB
and seed clock/reference spectra; this is not loaded-reference or SAR qualification.

Handover capture and replay preserve and validate endpoint configurations,
physical/scenario conditions, board/gain references, host source parameters,
control-clock and transport parameters. Altered or missing derived fields fail;
differing retained physical networks are unsupported. Independent sinusoidal
fixtures check converter times, and a 2 nH scenario reaches the recharge solver.
Baseline and RF packet converter/receiver helpers, wired gain/delay, recharge
feedback, reference passives/source settings and host-source helpers reject
missing owned parameters when any design marker remains, including a resolved
configuration alone. Converter tone aperture jitter uses the shared ADC noise
allocation for every bound environment. Converter tone runs validate RF identity
and both ENOB targets before waveform generation and copy their result context.
The integrated screen compares each lane against its own target; an independent
10/8.5-bit observation fails a hypothetical 8/9-bit allocation by 0.5 bits.
Nine focused converter ownership/screen checks pass. Independent primitive
examples retain their defaults.
The shared capture boundary independently reconstructs every supplied single or
endpoint configuration before continuation, replay or summary work. Both ordered
endpoint lists and named configurations used by multi-mode lifecycle reports
are validated; neither representation bypasses reconstruction. Altered
derived rates and empty endpoint lists fail; 18 affected retained-state checks
pass. Captures without chip identity/settings remain independent fixtures.
Wired TX recovery validates transport before simulation and copies configuration,
scenario and operating conditions separately into each stage. Four monitor/wired
entry checks pass, including post-run input and sibling-stage mutation probes.
Older captures lacking required fields must be regenerated. Broader retained-state
and injected-model compatibility remains open.

The common manifest covers a checked static closure of 51 local modules.
Runtime audits cover the exercised turnaround, ownership, USB and diagnostic
branches; this does not prove coverage of every dynamic import or data input.
Selected-review commands and migrated lifecycle commands reject source drift
before writing, including with Python assertions disabled. USB trim and RF
output-load consumers additionally verify their saved parent records. Fixed-network
host energy/topology/load comparisons preserve every consumed Liberty-record digest
and pinned source; they explicitly exclude themselves from current-chip evidence.

Keep numerical verdicts separate from execution and identity. In particular,
`completed_scoped_lifecycle` only means the prescribed stages executed. The
[central risk register](../../spec/risk-priorities.md) owns current issues and the
scope of recorded observations, including RF EVM/power shortfalls and retained
converter nonconvergence. Earlier successful executions whose hashes or schemas
no longer match are checkpoints, not current-design acceptance. Do not restamp them.
Current evidence checkpoint: the most recent RF refresh was deliberately stopped
before fixing reference-target ownership. Earlier RF, pad, converter, CDR,
common-envelope and joined-lifecycle records therefore require source/schema
verification and regeneration after implementation stabilizes. Do not treat the
805-test checkpoint or old reconstructed configurations as current integrated
acceptance. The corrected adverse wideband design explicitly owns both 2 us PGA
time constants; its prior converter-deadline rejection and 13-clipped-sample
RF-corner result were actual model outcomes, not configuration-guard failures.

Direct receiver overrides of noise figure, linearity, assigned ADC precision,
aperture jitter or PGA settling require an explicit diagnostic reason when bound
to the shared design. Results retain selected and imposed values plus that reason.
TX results record noise enables and oversampling, and validate inputs before
waveform generation. Independent mathematical fixtures remain valid exceptions. Retained SAR states
are checked for matching circuit/comparator identity, valid time and charge state,
and a usable random-generator state before either reference or rail provider is
called. Missing comparator identity no longer implies a legacy default. This avoids
consuming stateful forcing on a rejected continuation; valid split runs still
preserve exact code, charge-segment and random-state histories. All 18 converter,
comparator-deadline and diagnostic-lifecycle checks passed after this change.
The Wi-Fi fixture's common context also records its actual LO and converter phase-tone lists and sharing
mode. Mixing, edge timing and those records now use one phase-model construction.
An independent cosine-sum crossing check and detached-record mutation check pass;
prescribed clock realizations remain fixture assumptions, not silicon evidence.
All 33 Wi-Fi client tests passed in 20.814 seconds after this consolidation.

TX driver gain is selected through `design.configure(..., tx_gain=...)`. The shared
driver range and bit count resolve a nearest code (ties to even); configurations
record requested gain, code and applied gain. Wideband TX, packet TX and the joined
ownership lifecycle use it and reject conflicting adapter arguments or records.
Independent primitive output-stage experiments may still use arbitrary gains. Packet
ADC/DAC native width is likewise a circuit property, not a legal run-time setting:
a bound packet adapter rejects a conflicting width argument. An explicitly changed
DAC snapshot can select a supported alternative width and keeps its own fingerprint;
unbound mathematical fixtures retain independently chosen widths. Eleven focused
converter/binding checks passed, including rejection before waveform generation
and a rejected packet reply retaining the hypothetical DAC identity. All 22 packet
codec, acquisition, reply-timing and underflow tests also passed in 55.274 seconds.
Prior TX records without these fields cannot establish current configuration
reconstruction. The completed refresh verified 67 nested RF configuration records
and six lifecycle records before the subsequent PGA-variant fix; counts include
repeated records and are not capability counts or final migration acceptance.

Finish by auditing the remaining callers, then running the affected integrated
paths and independently reconstructing their configurations and variants.
The regression checkpoint above has its own scope; later changes need relevant
verification. This migration cannot be declared complete from test counts or a
small set of passing factory examples.

`make transceiver-math-fast` is a bounded interface/model-binding regression,
not joined-system acceptance. Current-design conclusions require the recorded
configuration, explicit deviations, relevant joined path and physical budgets;
numerical convergence and physical qualification remain separate obligations.

## Direct transport integration

`BehavioralChip.configure_transport('direct')` selects chip-owned RX/TX FIFOs,
raw-record decoding and 128-bit playback. `usb_selected_timing.reply_trace(chip=...)`
uses that state and advances the chip's reference/analog monitors during traffic.
The external FPGA model owns packet parsing, CRC and reply selection. Transport
errors latch a chip fault; STOP invalidates queued output and old session handles.
Explicit restart creates a fresh session. Dense transport cannot run concurrently.

`test_usb_selected_timing.ChipLifecycleTests` exercises a complete exchange,
parity failure, partial-output discard, reference timeout during traffic and
explicit fresh-epoch recovery. This is an integration check, not electrical USB
qualification: acquisition and output timing remain assigned. An optional
`attach_wired_pad(SharedWiredPad(...))` connects retained pad and divider voltages
to the received bit stream and checks the reply through that same network.
STOP and direct-path faults release the local driver without erasing capacitor
state or remote drive. The pad uses the chip's fixed declared rail; the common
dynamic supply/clock environment is not yet attached. Sampling at 0.4 UI, burst
boundaries and the acquisition tail remain assigned; package transmission effects
and comparator delay/noise are not represented. Excessive capacitance produces
squelch rejection rather than inheriting the ideal packet decode.

For repeated traffic, create `host = DirectHostState(chip)` after startup and pass
`host_state=host` to every `reply_trace`. This external FPGA object retains the
RX decoder, cumulative credit state, delayed credit returns and capture pipeline.
The chip retains both FIFOs, TX decoder and playback. Host/FIFO-read clock phases
are referenced to the first exchange rather than restarted per call; FIFO reset
release consumes actual scheduled clock edges. The discrete bench requires packet
starts on its 2.4 GHz simulation grid. Inter-packet idle is explicit in chip time.
Twenty exchanges exercise credit-counter wrap without STOP; bad packet CRC drops
only that reply, while transport/reference faults require explicit recovery.
New host credits cannot be created for an already-used chip epoch, and old host
state cannot survive STOP. Interrupted traces remain in flight and cannot be
silently reused. Two consecutive exchanges also traverse the retained electrical
pad. Packet-local sampling/burst boundaries remain assigned. Startup without an
attached physical qualification monitor still uses the declared startup delay.

## Active workflow

Finish the mathematical architecture before new schematic work. The active
priority is analog clocks, complete RF conversion and physical coexistence;
digital transport refinement is paused except where it constrains those paths.
Start with `python3 projects/programmable_transceiver_platform/verification/feasibility_bounds.py`
for the fast assumption audit. `fractional_pulse_screen.clock_filter_tradeoff_screen`
accepts `extra_frequency_tones` as `(offset_hz, frequency_deviation_peak_hz,
phase_rad)` triples for supply/noise susceptibility. These are declared stimuli,
not calibrated device spectra. Current conclusions and exact audit cases live
in the status owner and closure inventory.

Use focused checks for the current question; run the aggregate when integration
changes justify its cost. Supporting regression commands from the repository root:

```sh
make transceiver-behavioral
python3 -m unittest discover -s projects/programmable_transceiver_platform/verification -p test_bit_event_codec.py
python3 -m unittest discover -s projects/programmable_transceiver_platform/verification -p test_rf_mixer_phase.py
python3 -m unittest discover -s projects/programmable_transceiver_platform/verification -p test_counted_acquisition.py
```

The aggregate writes `evidence/behavioral-system.json`, with source hashes,
assumptions and excluded coverage. It does **not** automatically include every
focused demonstration below. A report generated before a source change remains
historical until rerun; the latest unit suite is not a substitute for it.

The active mitigation comparison is:

```sh
python3 projects/programmable_transceiver_platform/verification/robustness_envelope.py
python3 -m unittest discover -s projects/programmable_transceiver_platform/verification -p test_robustness_envelope.py
```

It reuses RF fixtures and converter/filter models, adds explicit external-LO
integer-divider settings, and optionally models finite FPGA resampling with
charged latency/storage. Desired failures are retained. This fast report does
not replace connected acquisition, dynamic supply or bridge recovery tests;
its clock/host/power checks are separate conditional budgets. The same report
also includes joined spectral receive-mixer/blocker/filter scenarios: phase
noise enters before filtering and common direct-LO phase perturbs ADC timestamps.
The host-PDN subsection now derives one supply-disturbance path from host
activity and a board/package network, including damping cost. A three-node
extension includes shared-return feedback; ground-to-signal/reference coupling,
substrate and complete multi-domain PDN closure remain open.

The report also includes a bounded diagnostic-intervention screen. Existing PGA
settings and stopped external-source replacement are compared using digitized
EVM/RMS and acquisition only. Equivalent post-gain sampler/converter noise is
retained as an ambiguous pair; no hidden model state is a diagnostic observable.
This does not qualify mixed faults, stage isolation or first-silicon procedures.

## How to read evidence

| Category | Meaning |
| --- | --- |
| Conditional demonstration | Declared configuration meets its specific acceptance criteria. |
| Expected rejection | The model correctly detects an injected fault or invalid input. |
| Known failure | A desired configuration misses a requirement. |
| Historical result | Retained result from another version or assumption set. |
| Not tested | No applicable evidence; absence of failure is not a pass. |

`status: passed` on a regression means its assertions passed, including expected
failures. Read per-case quality/deadline/flow results and coverage. Test counts
are not a completeness measure. Synthetic BPSK OFDM is not full Wi-Fi support;
raw NRZI/CRC packets are not a complete USB controller; diagnostic markers are
not standard wired startup. Do not transfer results between different clock,
noise, loading, transport or receiver assumptions.

## Choosing the next check

Choose a check because it resolves an architectural uncertainty or protects a
changed contract, not because it adds another passing case. Before running it,
state the requirement, selected configuration, assumed parameters and failure
criterion. Prefer one connected scenario with finite resources and recovery
over several isolated happy paths when it answers the same question.

Report desired-operation failures separately from successful fault detection.
Keep alternative assumptions separate; do not union their passes into one
claimed chip configuration. A local pass advances only its stated requirement.
Run broader integration when shared state, timing or interfaces change; avoid
repeating costly sweeps without a new question. Update current conclusions in
the status owner and exact evidence in the closure inventory, not in a new log.

## What is connected

`behavioral.py` joins event-driven transport and sampled/envelope analog models.
Persistent state, finite queues and chunk equivalence are important invariants.
Analog parameters and noise spectra remain declared assumptions.

- Host: directional framing/packing, staging, CDC candidates, pacing and epochs.
  Connected RF defaults to exclusive owner allocation and explicit host mode 0;
  low-level helpers and RTL retain legacy comparisons pending reconciliation.
- Wired: `RecoveredWordSource` observes voltages on its own receiver timeline.
  Four observations per interval estimate crossings; correction affects future
  samples. It no longer queries crossings by transmitted bit index. This is an
  ideal sampled detector, not qualified GF180 CDR hardware.
- RF: held DAC, filters, mixers, ADC, shared rail and optional actual pulse-loop
  history; independent external TX/RX observers and known-training recovery.
- USB: generic pad/events and record transports, with an incremental external
  FPGA parser. Protocol decisions and CRC remain external to the chip.
- Lifecycle: stopped configuration, explicit startup/stop, faults and epochs.
  Fixed guards and optional count qualification have different evidence scope.

## Focused wired demonstration

Import `behavioral` from this directory. Use:

```python
staged_wired_duplex(remote_clock_ppm=100., host_clock_ppm=-100.)
staged_wired_duplex(return_clock_gap=True)  # Retained TX-underflow control.
staged_wired_duplex(return_clock_gap=True, recover_tx=True,
                   rearm_delay_s=20e-6, framed_rearm=True)
```

The framed option explicitly changes resumed external source data to training
and diagnostic markers. Acceptance uses received bits and timing qualification;
expected payload is used only for scoring. `tx_word_errors` retains raw grouping
errors; `recovery.framed_payload_errors` scores released frames. Unframed delayed
rearm remains a distinct failure control. Serializer restart is phase-aligned;
serialized management and physical timing are not established.

`causal_compliance_cdr_screen()` adds the four-symbol PCIe Gen1 compliance
pattern from [PCI Express Base Specification 2.1, section 4.2.8](https://www.intel.com/content/dam/support/us/en/programmable/support-resources/fpga-wiki/asset03/pci-express-base-r2.1.pdf).
It tests ±100 ppm, four initial phases through ±3 UI, and an invalid constant-level
interruption. Readiness comes from causal recovered bits and pattern recognition.
It excludes host transport, SSC, link training and endpoint functionality; this
is a targeted receiver screen, not protocol compliance.

## Focused RF demonstration

`connected_tx_port(waveform='he20', ...)` drives an independent voltage observer.
`connected_tx_gfsk_port()` retains the historical GFSK comparison load.
Generic TX defaults to `complete_rail_load=True`, sharing the RX recipe's rail,
host activity and mapped FIFO clock-pin loads with mode-specific bias.

The selected TX configuration is:

```python
from behavioral import connected_tx_port
from tx_output_candidate import PARAMETERS
result = connected_tx_port(
    waveform='he20', payload_seed=977, tx_amplitude=.15,
    tx_voltage_scale=4.518, tx_substeps=16, bias_current_a=.037,
    observer_filter=dict(sample_hz=640e6, cutoff_hz=10e6, order=5),
    tx_output_parameters=PARAMETERS, wait_for_acquisition=True,
    tx_electrical_budget=dict(source_resistance_ohm=40.,
        load_resistance_ohm=50., driver_bias_current_a=.028,
        peak_current_limit_a=.028, headroom_per_rail_v=.3,
        differential=True))
```

Count acquisition preserves 500 µs per observation across reference rates and
requires two good windows. It measures average frequency, not phase quality.
Coupled startup runs can take minutes; do not repeat them for unrelated edits.

`connected_he20_payload` accepts independent remote timing, an input-referred
electrical budget, `pulse_bias_current_a`, and the same pulse-clock acquisition
flags. Its `pulse_complete_load` case is the selected RX composition. Exact RX
settings and launch time are retained under `rf_rx_continuous_bias` in the
inventory; source launch is not silently moved to follow receiver readiness.

`SampledRFStream(receive_source=callable)` uses physical-time envelopes with
retained converter timestamps. The local DAC continues independently. Optional
`capture_cache` dictionaries allow receiver-only reanalysis without rerunning
clock/host state; captures are analysis storage, not on-chip memory. Receiver
fitting must not consume expected payload. The external anti-alias filter does
not qualify the chip's emitted spectrum. Transport bit precision is not ENOB.

## Focused USB demonstration

```python
usb_observed_response(
    request_lengths=(8, 64, 512), usb_data_packet=True,
    host_pacing=True, coalesce_return=True,
    fpga_ingress=dict(clock_hz=100e6, bits_per_cycle=16,
        capacity_records=8, phase_cycles=.37, synchronizer_cycles=2))
usb_ingress_work_screen(processing_phases=(0., .37, .99),
                       service_widths=(16,), synchronizer_cycles=2)
```

Lengths are payload bits. `fpga_processing_s` is the final decision delay
(default 40 ns), additional to ingress work. Capacity includes queued and
in-service data records; overflow suppresses ACK. Synchronization charges
pointer/control visibility, including the boundary event, while payload is held.
Omitted synchronization/capacity options retain historical comparisons, not a
qualified implementation. `command_sync_cycles=2` adds clock-aligned publication into the eight-word
frame-builder domain. The independent-clock candidate fails the focused
exchange with that crossing; zero remains a historical comparison, not proof
of implementable synchronization.

The candidate `fpga_ingress=dict(clock_source='host_ddr', bits_per_cycle=16,
capacity_records=8, synchronizer_cycles=2)` derives processing frequency from
H2D DDR, including its ppm error. Response/frame construction shares this clock
with synchronous block enables; independent phase/frequency and nonzero
`command_sync_cycles` are rejected. Processing is rounded to complete clock
cycles. See [clock ownership](../../spec/clock-rate-ownership.md#selected-clocks)
for implementation and recovery obligations. With the historical 40 ns final budget its faster-host margin is 4.167 ns.
Adding `decision_cycles=3` explicitly selects the proposed validate/select/publish
pipeline budget instead (29.167 ns finite margin); this is not implemented FPGA
timing or complete USB latency closure. The unused time budget reports null.

A late correct reply fails `meets_budget`. Parser framing/CRC checks do not
establish token/endpoint acceptance, transaction state, attach/reset/chirp,
causal USB CDR, metastability protection or placed FPGA timing.

## Optional supporting checks

```sh
# Longer, multi-seed RF robustness; outside the default iteration loop
python3 projects/programmable_transceiver_platform/system_model/architecture_fast/behavioral.py --burst-stress

# Bounded supporting numerical/architecture checks
make transceiver-math-fast

```

Current coupled electrical and lifecycle checks are in
[`baseline_envelope.py`](../../verification/baseline_envelope.py) and
[`selected_lifecycle.py`](../../verification/selected_lifecycle.py).
The old dual-synthesizer full-chip constructor and integration runners are
removed. `host_ground_solver_check.py` retains standalone numerical checks under
explicit circuit assumptions. Remaining shared modules and standalone benches
still require consistency review; primitive correctness does not establish
current full-chip operation.

## Requirements and ownership

- [Contract](../../spec/contract.json): configurations and external recipes.
- [Transport](../../spec/streaming-transport-v2.md): framing and service obligations.
- [Clock ownership](../../spec/clock-rate-ownership.md): timing conventions.
- [RF coordinates](../../spec/rf-frequency-coordinates.md): signal conventions.
- [Risk priorities](../../spec/risk-priorities.md): what to address next.
- [Closure inventory](../../spec/mathematical-closure.json): completion gates.

Keep experimental measurements in evidence reports and current conclusions in
these owners. Do not append chronological progress logs to this guide.


The consolidated robustness report also includes `shared_timing_requirements`:
coherent host-rail harmonics propagate through assigned frequency-dependent
buffer/phase/distribution delay responses into RF, sample-time and wired timing
metrics. This yields tolerable sensitivity ceilings, not physical qualification
or packet-level RF EVM. See the current risk assessment for the numerical scope.


The same report's `host_driven_rf_receiver` and `host_driven_wired_receiver`
propagate assigned host rail harmonics into actual RF filtering/acquisition and
causal wired sampling. RF uses 64/128 mixer substeps for high-offset tones and
implicit LO-derived ADC crossings; default lower-band fixtures retain their
existing first-order timing. This is still diagnostic waveform evidence, with
physical bounds and real packet acceptance open. The later `bidirectional_host_receiver` section adds separate H2D internal-load and external-capacitive-return ports; complete DC/reference/gain coupling remains open.

The existing `python3 verification/check_contract.py` command (from the project
root) now reports `milestone_coverage` alongside planning arithmetic: all 17
capability verdicts, acceptance-dimension status and open milestone criteria.
Structural validation rejects missing targets, missing dimensions and a declared
completion that contradicts open entries. A successful command does not qualify
the chip; its coverage section currently records unresolved performance.

To refresh just the selected package/clock screen, run
`python3 verification/selected_revision_check.py` from the project root.
`--wired` and `--rf` refresh their respective payload sections separately.
Each section owns its source hashes; rerunning one section does not refresh
older RF, wired, BLE or transmitter results. The runner accepts changed source
versions and can start without a prior report, while checking that its listed
sources remain unchanged during the run.

For the common inventory, use `--common-envelope` for converter/wired cases,
`--common-rf --rf-filter rx_all_pole_control` for the narrowband packet and
`--common-wideband --wideband-wanted-dbm -85` (or `-75`) for the wideband acquisition control. The latter uses legal
42 dB PGA gain, inventory SAR diagnostic loading and asynchronous comparator
completion, with the same RF current/package catalog and reference-feedback
model. It retains legacy training and diagnostic coded HE20 data; it does not
supply HE signaling, HE-LTF, AGC or interoperability evidence. Legacy `--rf`
fixtures using 54 dB gain do not qualify the selected PGA. Each common section
retains its own source manifest; a newer wideband run does not refresh the
converter/wired or narrowband results.

`--common-tx --tx-rms-codes 180` (or `250`) checks transmitted power, diagnostic
quality and mixer swing using the common inventory, 18 MHz reconstruction and
selected driver gain. The amplitude is complex RMS in 12-bit transport codes,
not a native-code peak. The common TX port now includes the inventory RF-pad series resistance. Without explicit RF-load options it omits reactive pad/bond loading;
signal-dependent current feedback remains absent in both paths; it cannot close
physical output-power or emission requirements.

`--rf-output-load` is a fast lumped RF pad/bond/matching screen using the recorded
250-code common TX result. It keeps that record's manifest and digest separately
from the new calculation's sources. Reported powers and required gain settings
are narrowband extrapolations, not a new reactive waveform simulation. It compares
unmatched signal-loop hypotheses with ideal external series compensation; the
selected gain range is unchanged. Its `tolerance_screen` compares fixed
matching (±10% capacitance error) with per-board adjustment (±2% residual error)
using one capacitor across the band. It holds the recorded TX waveform, rail and
clock fixed. Admission is only a necessary gain/current/headroom screen; the
assumed adjustment accuracy is not a measured calibration capability.

For causal waveform loading, add `--tx-signal-loop-nh 8
--tx-series-match-pf 0.5379831620795082 --tx-gain 5.72` to the250-code common TX
command. Gain is quantized within the selected8-bit range. `rf_pad_waveform`
propagates pad capacitance, signal-bond current and optional series-capacitor
voltage, returning state for continuation. It rejects incompatible continuation
configuration and does not use circular convolution. Driver-current exceedance
rejects a case requiring nonlinear re-solution. Numerical step subdivision and
carrier response are tested; component tolerance and physical drive stability
are not qualified. Reactive compliance fields replace fictitious resistive load
currents, while the original resistive precheck is retained for attribution.

`--shared-pad` refreshes the retained serial/TMDS/reset/USB sequence and explicit
rail-versus-ground protection hypotheses against the wired inventory's DC rail.
It records backfeed, divider/isolated-branch voltages and energy balance. Mode changes now
use `SharedWiredPad.transition_mode`: assigned command latency, local isolation,
positive dead time and connection with released output. Break/make snapshots
retain external sources and analog state. Optional `edge_charge_c` supplies
break/make four-node charge packets over `injection_duration_s`; finite current
pulses integrate signed work separately in `injection_energy_j`. The report
includes assigned 0/10/50 fF-equivalent charge probes at two pulse widths and
both polarities. Internal divider excursions can greatly exceed pad excursions.
Reported extrema are solver-sampled; physical charge, internal clamps, control
skew and transistor switch slew remain unqualified. USB stages use their own inventory-derived DC rail and record the separate
owner-current ledger. The change between rails is imposed; no coupled dynamic
USB package, ESD or transistor stress claim follows.
The optional `divider_ground_clamp` is a finite knee/resistance law, with
`divider_clamp_cap_f` explicitly added to each internal node. Clamp dissipation
enters the energy ledger and `divider_clamp_charge_c` integrates current returned
from ground. The shared-pad report compares clamp/loading hypotheses under the
same charge pulses; it does not ideal-clip voltage or qualify a physical device.

### Converter continuation interface

`BehavioralChip.configure_converter_input_test(i, q)` accepts the existing numeric
0..3 selections only while stopped. After startup, `bind_sar_converter` binds
those controls to the active RF epoch and the actual `paired_sar` recurrence.
The caller owns timestamps, reference/rail forcing and retained `final_state`;
this adapter does not synthesize sample clocks or automatically make converter
results part of the host stream. Old callbacks fail after STOP/restart. Tests
exercise zero, opposite quarter-reference inputs and normal input without clearing
analog state, and demonstrate that ratiometric codes cannot detect an absolute
reference scaling error. Extra diagnostic-source loading and charge injection
remain absent, so this is functional integration rather than a qualified BIST.


`verification/converter_dynamics.py:paired_sar` accepts `initial_state` from
the previous trace’s `final_state`. The JSON-compatible state retains analog
voltage state and RNG position at completed-conversion boundaries, checks
parameter compatibility, and rejects a restart without acquisition/reset time.
External gain-control state remains caller-owned. Optional `idle_step_s`
subdivides reference/DAC recovery through changing forcing across long idle
gaps; omitting it retains the earlier midpoint approximation. The
`selected_lifecycle.py` retune fixture connects this state to package-derived
clock, rail and reference forcing. SAR reference-recharge current now feeds
back through fixed-reserve waveform relaxation; other ADC activity remains
prescribed. Mid-bit interruption, powered-down leakage and payload recovery
remain unmodeled in this fixture.


Finite converter captures can use `BehavioralChip.transfer(until_s=...)`, with
an observation horizon relative to the persistent stream origin. The usual frame
limit still applies. RX-only replay without a live converter clock may return
`None` from `rx_event_time` after its last observed conversion; this ends the
capture source, not the physical clock. Subsequent replay calls require an
explicit horizon. Partial frame position and queued bits survive bounded calls;
STOP still discards queued bits. Do not extend a horizon beyond the analog
observation to manufacture a successful drain. Converter words become available
at conversion completion, not at the sampling aperture.

The selected lifecycle runner replays the retained SAR capture through this
interface. Its two separately qualified warm segments produce 144 and 336 bits,
but deliver no payload before their observation boundaries when starting fresh
host frames. This is a bounded integration diagnostic, not a passing end-to-end
lifecycle. The sub-microsecond capture does not cover the 20 us readiness floor.


For long intervals of unchanged periodic package forcing,
`PeriodicPackageContinuation` evaluates the forced response and retained natural
modes directly at requested times. It preserves the descriptor's stored
charge/flux (`E*x`) and rejects incompatible initial states. Algebraic voltages
can adjust when switching from polygonal source interpolation to analytic tones;
the handover evidence reports that adjustment separately. Its ten-mode separation
is specific to the current passive network and checked across the three package
cases; it is not a general DAE solver. Source transitions still use explicit
integration. The retained-retune runner also uses scalar modal observers for rail, input and
retained one-pole reference/delay filtering. Its extended 22 us branch includes
SAR continuation and iterative reference-recharge feedback, then exercises
rearm, timer/reference-presence readiness and actual host delivery on the same
absolute timestamps. The short bounded capture is retained as the insufficient
observation control. This does not qualify cold startup, analog readiness,
protocol packets or fault recovery; divided-clock root searches do not check
every intervening LO crossing.


The extended SAR lifecycle also reports `transport.analog_acceptance`. Every
supply value used by the converter equations must meet the existing 2.5 V model
floor before this run counts as accepted transport evidence. The negative control
reruns the converter with a -300 mV local DC perturbation and the assigned
reference/delay sensitivities; its codes are outside the qualified model domain
and cannot establish payload success. This acceptance check neither implements
a hardware READY monitor nor proves the rail stays valid between evaluations.


For bounded RX replay, `transfer(d2h_event_time=...)` accepts actual host-word
clock event times relative to stream origin. Missing beats are represented by
gaps in those times; `None` ends the observed edge capture. This requires an
explicit horizon and currently excludes duplex/feedback operation. Slot counters
advance only on observed edges, while the independent reference monitor can
fault during an interval with neither source samples nor host beats. Reported
capacity remains the nominal configured rate, not measured service during gaps.

`retained_sar_retune.clock_loss_package` carries the base passive state through
source outage and return. The selected solve uses half-cosine sidebands and
retained natural modes; it preserves filtered reference and delay state. The
older trapezoidal comparison remains visible: one coarse-grid 20 mV crossing
is missing, whereas three analytic observation grids agree. Refined sampled
roots do not prove that every grazing crossing has been found.

`extended_lifecycle.clock_loss_converter_continuation` joins full-history
reference-recharge feedback to those inputs. Its 125 ps recharge grid fails the
1 µV frozen-prefix limit; the nested 62.5 ps refinement passes. Do not combine
their verdicts or read stable converter words as proof of prefix continuity.

`extended_lifecycle.clock_loss_recovery` extends the finer-grid trajectory to
45 µs with retained SAR charge/noise and package/filter state. The attached
`transport` result uses actual converter words and /16 host clocks sharing the
/64 sample phase. It delivers payload, detects missing clocks, discards the
bounded queue, rejects stale callbacks, rearms and delivers correct payload
again. Supply validity and feedback convergence are prerequisites for accepting
this replay. Post-fault readiness requires the assigned 20 µs guard,
reference presence and ideal model-observed analog qualification; the analog
model continues while payload ownership is stopped. Host current harmonics remain prescribed, not derived from these words.
This is a known-tone lifecycle with discharged converter charge in a powered
package and guarded FFT feedback. It does not establish full power-up, physical
READY sensing, arbitrary-phase clock immunity or protocol compliance.
The settled extension brackets required divided-clock roots instead of sampling
every LO cycle through the long recovery interval.

The retained-SAR lifecycle now begins with `discharged_sar_state()` rather than
precharging its reference to the target. Initial charging current enters the
same recharge feedback history; package rails and periodic loads are still
already powered. `reference_startup` shows why this distinction matters: a
nominal READY timer with only 50 ns of actual bias age gives 0.5 V at the first
aperture and a large code error. The sensitivity rows vary available recharge
current; they do not establish GF180 bounds. `sar_timing.startup` owns the
required readiness epoch and the remaining analog qualification obligations.

`BehavioralChip.attach_analog_qualification()` accepts model-observed validity
transitions before startup. The selected recovery runner derives them from the
retained reference trace and evaluated rail, using the contract's coarse bias
window. Invalid startup postpones READY; later loss faults both active idle and
streaming, without treating old callbacks as a valid new epoch. This optional
hook is not a new external protocol command or a qualified sensor circuit.
Legacy fixtures without the hook retain their explicitly assumed readiness.

For the matched packet/package check, run
`python3 verification/selected_revision_check.py --ble-joint` from the project
root. `package_ble_joint_screen` in `evidence/selected-revision-check.json` owns
its fresh source hashes and verdicts. This uses /64 sampling, a modulated
+2 MHz blocker, budgeted ADC activity and fixed-reserve recharge feedback over
three package hypotheses. A rejected clock prevents downstream RF qualification;
a decoded packet outside the evaluated supply domain is also rejected. This
single-packet screen does not replace PER, other offsets/PHYs or lifecycle proof.
The slower /256 clock/current configuration still needs a more general coherent
clock screen. Old packet reports retain their original current-centering scope.

For the matched filter-history comparison, run
`python3 verification/selected_revision_check.py --rx-memory`. The
`rx_filter_memory` section compares the all-pole and finite-zero settings at the
same cutoff, package, packet and blocker, with explicit zero, prior-tone and
decayed-history states. Each case includes native SAR/recharge feedback. The
prior tone is specified at the filter input, not derived from a preceding full
RF transaction. Results cannot establish a general protocol or warm-turnaround
verdict. Do not run this concurrently with another revision-report writer.

`selected_rf.analog_filter` can retain normalized modal state across records.
Use `state_capture` and `initial_state` with identical family/cutoff settings.
For ZOH, the state commits the last held interval's end; for linear forcing it
commits the last input timestamp, which must be repeated at continuation.
Coefficient changes require explicit state mapping; no implicit reset is a
settling proof. Absolute source/LO time and any quiet interval remain the
caller's responsibility.

`python3 verification/selected_revision_check.py --filter-realization` checks
an explicit finite-integrator surrogate, its coefficient-retuning candidate,
and bandwidth drift through the coupled wideband receiver. The
`filter_realization` report separates unstable configurations, transfer-function
changes, diagnostic DATA observations and illustrative current costs. Its
extra integrator pole is not a measured op-amp GBW or a universal active-RC law;
zero BPSK errors do not qualify the filter or a complete Wi-Fi mode. This command
also writes the revision report and must run separately from its other writers.

`python3 verification/selected_revision_check.py --filter-budget` is a fast
analytic screen for section ordering, voltage-scaled internal states and joint
noise/bandwidth bias allocation. It updates `filter_budget` in the same report.
The passband noise constraints prevent an integrated average from hiding bad
frequencies. Upper-gain excitation and lower-rail headroom are screened separately;
this does not simulate a supply transition. Effective pole capacitance, integrating
capacitance, amplifier overhead and omitted noise sources must not be conflated.
The nested `rc_noise_and_capacitive_drive` allocation includes summing-resistor
noise, integration capacitors, a separate class-A drive hypothesis, plate-area
scenarios and a convex dual current bound. The outer bias fields remain an
amplifier-drive-noise-only comparison. See the power partition for the
provisional mapping, remaining omissions and conditional alternatives.

For the unresolved TX-current transient precision, the short diagnostic
`python3 verification/selected_revision_check.py --tx-load-numerics` (from the
project directory) varies current-grid resolution and FFT guards independently
and compares hard versus finite mute slew. It updates only the scoped
`tx_load_numerics` section of the revision report. It does not rerun or refresh
packet/lifecycle evidence and cannot qualify the full exchange by itself.

The fast `python3 verification/selected_lifecycle.py --ownership` command updates
only `selected-lifecycle.json:ownership_load_trace` and its own source hashes.
The default RF rate is the selected 2.4 GHz /64 = 37.5 MS/s, with 24-bit
complex samples (900 Mbit/s raw), not the earlier /256 diagnostic rate.
It runs RF RX → RF TX → wired duplex → RF RX → RF TX with clock loss →
recovered RF TX → recovered RF RX through one chip and
retained incremental package trajectory, with the contract's 1024-bit queues.
RX prefixes and TX data beyond prefill are checked bit-for-bit; explicit TX
consumption times now support RF TX-only as well as wired service. RF direction
changes use STOP/rearm. This is control/data continuity with assigned clocks
and loads. A package-delayed /64 presence monitor detects a prescribed clock
gap during final RF TX; faulted service and stale epochs are rejected, package
state is retained, and payload resumes after return/rearm. Earlier stages use
timer readiness. RF RX now supplies native paired-SAR words from a known
baseband tone, retaining reference/sample/DAC/RNG state across TX, wired and
fault recovery. Acquisition follows package-delayed sample edges; transport
waits for the allocated 18 ns conversion latency. Idle reference recovery uses
saved package histories at 1 us midpoint steps. Charge balance and evaluated
supply validity are checked. TX consumption now feeds the native DAC transfer and third-order 3 MHz
reconstruction filter. Held-code/filter history persists across STOP/mode changes
and fault recovery; both converter directions use the retained reference state.
Native DAC settling/reference loading, RF front-end filtering/mixing and output
port/mute behavior, analog READY, converter-current feedback, fast TDD and cold
startup remain outside this sequence. Other report sections retain their original
evidence provenance.

The ownership runner attaches **live model-observed analog qualification**.
Startup uses 100 ns reference/supply observations and the existing guard.
The selected ownership runner now expires observations after 200 ns. Each
consumed TX word observes the retained reference and current supply before
acceptance, including wired TX while the converter is parked. RF RX continues
to observe completed conversions. The age is a numerical coverage assumption,
not a specified hardware sensor or a bound on voltage between observations.
An explicit `qualification_max_age_s=None` is only a held-observation control.
Idle intervals without observations must fault rather than inherit readiness.
Independent 100 ns observation events now bridge muted settling intervals;
their schedule persists across transfer calls and is independent of payload
enables. Idle reference recovery is read-only and does not advance or recharge
the converter twice. Active RX leaves observations to completed conversions.
Warm RX/TX/RX completes with this path and fails at 200 ns observation age when
it is disabled. A callback returning `None` is a missing observation, not valid
readiness. This is ideal model observation, not a physical sensor implementation.
During conversion, the unchanged reference window applies at acquisition and
actual comparator decision points; normal intervening charge steps remain in
settling, charge balance and code-error calculations. RX completion rejects
invalid consumption-point reference or evaluated supply before word delivery,
while retaining the completed analog state. The seven-stage trace completes
under this policy at 37.5 MS/s (366 RX conversions across three stages). The earlier whole-excursion interpretation falsely treated
a 0.978447 V charge step as bias loss despite valid decision-point reference.
Negative controls retain rejection for bad decision reference and low supply.
This ideal observer is not a hardware sensor, and completion-time observation
does not imply detection during an earlier bit decision or ENOB qualification.

`ownership_load_trace.reference_charge_accounting` now conserves the represented
reference-reservoir charge across the entire sequence, including startup and
idle/TX observations. It separates whole-trace mean recharge from converter
activity fraction and the same-code continuous-SAR estimate. The latter is an
extrapolation, not sustained-operation evidence. Source plus idle peak stays
inside the existing 3 mA reservation; no current is added to the chip budget.
Native TX DAC reference draw and feedback into package loading remain absent.

The selected retained lifecycle also has a wideband mode:
`OPENBLAS_NUM_THREADS=1 python3 verification/selected_lifecycle.py --ownership-wideband`
(from the project directory). It updates only `ownership_wideband_trace` in
`evidence/selected-lifecycle.json`, with its own source hashes. Four HE20 DATA
symbols replace the RX tone and TX diagnostic words. RX quality uses complete
host-delivered I/Q samples; TX quality uses actual consumed words with FPGA
scaling before packing and an independent RF observer. The default short
`--ownership` run retains the unscaled TX overload negative control. This uses known DATA training and ideal boundaries, not packet
acquisition or PER qualification. See `spec/risk-priorities.md` for the current
interpretation and next architectural gates.

`--ownership-packet` replaces RX tone forcing with an LE 1M advertising packet
at 2402 MHz and LO/256 sampling, using the same retained lifecycle, filter/SAR
and actual host delivery. It writes `ownership_packet_trace`. The FPGA observer
searches timing/CFO from the preamble/access address and checks CRC; source truth
is used only by the scoreboard. This covers fixed-gain RX acquisition/recovery,
not BLE response TX, PER or sensitivity. Add `--ownership-stress` to apply the
same common supply/timing disturbance, writing `ownership_packet_stress_trace`
without replacing the nominal packet result. Add `--stress-ripple-hz 11500000`
for the in-band translated-blocker case; this writes a separate
`ownership_packet_stress_frequency_trace` section. It is separate from the fast direction
turnaround case; neither is evidence for their untested combination.

`--ownership-request` sends an addressed LE 1M scan request through the same
RX lifecycle and feeds the decoded packet plus actual host-record availability
to the response-service budget. It writes `ownership_request_trace`. No TX reply
is executed by this mode; `reply_armed` is the external budget/policy outcome,
not proof of a chip action or air launch.

`--ownership-reply` extends the first addressed scan-request stage with a live
response on the same chip/clock/epoch and finite TX FIFO. FPGA-generated words
enter only after the assigned work/command budget; an independent peer decodes
the actual modeled RF output. It writes `ownership_reply_trace`. Later lifecycle
stages still cover wired operation and fault recovery, but do not transmit another
reply. Command transport and physical switching remain assigned boundaries.

`--ownership-wired-cdr` connects loaded voltage sampling and causal CDR to
actual wired RX host delivery in the selected lifecycle. Shared retained rail
and delay callbacks drive receiver gain/aperture. A deliberate transition drought
checks suppression/recovery; random bits are not encoded protocol qualification.
It writes `ownership_wired_cdr_trace`, retaining the ideal-word diagnostic cases.

`--ownership-wired-encoded` substitutes the existing PCIe compliance pattern
and checks framing from actual host bits. It writes `ownership_wired_encoded_trace`.
Current qualification losses and silent word suppression disrupt the pattern;
zero errors among accepted bits do not establish continuous protocol service.
No general 8b/10b decoder, host gap notification or PCIe link training is implied.

`--ownership-wired-fail-closed` applies the explicit post-acquisition RX loss
fault policy to the loaded encoded case. It currently stops at the first loss
and writes `ownership_wired_fail_closed_trace`. This is correct rejection of an
unqualified continuous stream, not a successful link or full recovery trace.

`--wired-noise-attribution` runs six matched joined encoded cases, removing or
halving assigned detector/receiver disturbance without changing the lock
criterion. It updates `wired_noise_attribution`. Zero-noise controls are diagnostic;
the finite half-noise cases still contain unintended losses and are not qualified
circuit requirements.

`--ownership-wired-equalized` joins the canonical CTLE from
`physical_services.wired_receiver` to encoded RX; add
`--ownership-wired-fail-closed` to stop on post-acquisition loss. These write
`ownership_wired_equalized_trace` and `ownership_wired_equalized_fail_closed_trace`.
The older `--ownership-wired-encoded` and noise-attribution cases bypass the
selected CTLE and are explicitly unequalized controls.

`--ownership-wired-electrical` extends the selected equalized case with actual
emitted TX bits, retained rail-dependent driver amplitude and serializer timing,
a loaded channel and an independent peer CDR. Add `--ownership-stress` for the
existing joint disturbance (and wideband RF stages). Evidence sections are
`ownership_wired_electrical_trace` and `ownership_wired_electrical_stress_trace`.
Each decodes 1,300 held-out TX bits without error; stressed RF quality still fails
to establish whole-chip success. Bit-held supply amplitude, assumed prefill and
linear channel propagation do not qualify pad clamps/headroom, current feedback,
protocol electrical controls or a continuous uncertainty envelope.

`--ownership-tx-range` runs the same joined wideband lifecycle with FPGA-side
native peak target 180 instead of 50 and unchanged analog gain. Its separate
`ownership_tx_range_trace` evidence reports active DATA power and marks that
sampled amplitude checks do not replace the conservative all-history bound.
Wideband lifecycle TX also records `spectral_diagnostic` on the actual emitted
complex envelope before receiver filtering. A Hann-windowed DATA capture compares
±10 MHz wanted-band energy with adjacent 20 MHz bands. This exposes a spectral
cost that EVM after receiver filtering can hide. It is not a protocol mask or
absolute-power measurement, and excludes packet switching and RF harmonics.

`--ownership-tx-gain` repeats the 180-code lifecycle with candidate nominal gain
5.36 instead of 4.5, recording `ownership_tx_gain_candidate`. It recomputes the
amplitude/headroom bound at that gain and observes actual power, EVM and spectrum.
The distortion law and 28 mA reservation remain hypotheses; this does not prove
that the higher gain is available at unchanged bandwidth, noise, current or area.
The candidate does not change the selected baseline gain.

`--tx-power-requirement` calculates necessary port and amplitude/gain bounds
for the selected engineering power goal from the recorded nominal crest factor.
Neither command qualifies emissions or silicon.

`--ownership-stress` runs that same wideband lifecycle with one explicitly
assigned joint supply/timing disturbance and writes `ownership_stress_trace`.
It is an adverse integration case, not a package-derived uncertainty bound.
Lifecycle completion and signal-quality acceptance must be read separately.

`--ripple-envelope` compares the same joined wideband RF and equalized wired
RX/TX lifecycle at 0, 9.6 and 60 mV peak shared ripple. Source offset (-33 mV),
fourfold delay sensitivity, 10 MHz frequency and traffic remain fixed. It writes
compact per-stage quality/CDR results to `joined_ripple_envelope`, preserving
failure evidence. This is a supply requirement probe, not a demonstrated external
filter/regulator or a continuous uncertainty bound.

`--joint-tx-envelope` combines the 180-code, 5.36-gain TX candidate with the
9.6 mV reduced-ripple shared RF/wired lifecycle, retaining −33 mV source offset
and fourfold timing sensitivity. It records `joined_tx_operating_envelope`.
The current result is a near-miss on 0 dBm output power, not a successful supply
implementation or protocol verdict. Read host continuity separately from
accepted-bit correctness across the injected wired loss.

Add `--ownership-wired-fail-closed` to `--joint-tx-envelope` to exercise the
selected stop-on-loss policy. `joined_tx_fail_closed` must stop at the deliberate
wired drought (word 406), rather than claim seven-stage completion. The default
joined command is a continue-across-loss diagnostic; post-fault host recovery
must be integrated before calling either case a complete selected lifecycle.

`--wired-recovery` runs the reusable loaded-CDR recovery sequence with an 80 us
continuing peer waveform, shared imposed rail/timing disturbance, sticky fault
publication, scheduled status polling and a full restart. It records
`loaded_wired_recovery` with source hashes, elapsed times, discarded words and
resumed transport checks. The regression calls this same implementation. This
is a steady wired-load composition; the joined command below supplies retained
RF/wired power transitions. Serialized recovery commands remain open.

`--joint-wired-recovery` embeds that recovery in the seven-stage retained RF
lifecycle, using the same chip, package trajectory and converter reservoir.
It records `joined_wired_recovery`. The wired branch exercises RX recovery;
wired TX during recovery is not covered. It corrects host rate ownership on entry
and uses the selected FIFO allocation. The longer schedule changes RF impairment
phase: use this run's quality measurements, not the earlier nominal bounds.
With a parent analog-qualification monitor attached, recovery now requires an
independent reference/supply observer. Initial arming and post-fault restart
collect 100 ns observations through the continuous-validity startup guard;
wired RX uses the independent observation events while the converter is parked.
The faulted polling interval does not refresh readiness. Fresh observations
must requalify it after STOP instead of reviving the old startup flag.
The shared runner reads the retained reference recovery and package trajectory;
standalone observer-free recovery remains a narrower control fixture.
`selected_lifecycle.py --ownership-usb` appends a direct USB exchange to the
seven-stage RF/wired lifecycle on the same chip, retained converter reservoir,
pad and package state. The pad is isolated during the earlier abstract wired
stages; this is not shared electrical-lane proof. USB uses its 252.2 mA inventory
and a 100 ns assigned transition of both local and HOST-node currents. The
optional HOST input in `LocalLoadTransient` shares feed/return impedance and
bypasses the package supply branch; independent nodal AC and ledger DC checks
cover both ports. Omitting the HOST transition caused a 0.96 mV ledger mismatch.

The joined SAR uses inventory acquisition/loading/guard parameters and the
chip-owned converter binding. Paired asynchronous decisions use the assigned
50ps regeneration/100ps launch/200mV threshold model with actual reference
recovery; host publication remains at the18ns ceiling. Scheduled diagnostic
calibration and physical comparator/sequencer behavior remain open.
USB now arms through the existing 20 us guard with fresh reference/supply
observations. `reply_trace(analog_observer=...)` schedules observations every
100 ns; missing samples do not refresh validity and invalid samples fault the
chip. The recorded exchange decodes 48 reply bits with five observations and
settles at the USB ledger's 2.953211 V. Direct host clocks, USB acquisition phase,
pipeline delays and ideal current source remain assigned. All preceding RF RX,
RF TX and wired stages now use the same architecture inventory (externally clocked RF230/230mA, wired268.45mA;
USB252.2 mA), with local and HOST load transitions and per-stage DC checks. Warm
RX/TX sequences currently have identical allocated rail currents; the runner
rejects such sequences if those inventories diverge without a load schedule.
The same trajectory now includes a reference-target dip to 0.8 V: a live
observation interrupts the second reply after six bits and releases the pad.
The old session remains invalid after STOP/rearm; fresh observations through a
20 us guard admit a new 48-bit reply. The reservoir and package retain state.
This is generic fault recovery, not USB retry qualification or physical sensor
validation. Traffic-dependent current feedback and diagnostics/calibration
still need joining.
For this matrix-heavy case, `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` avoids
multithread overhead without changing the model.

`--analog-envelope-summary` reads the two recorded joined schedules and emits
`analog_operating_summary`, preserving their hashes and separating observations
from uncertainty bounds. It runs without another waveform simulation. Use it
for current cross-schedule RX/TX ranges; it does not qualify protocols or refresh
historical evidence to the current source revision.

`--supply-requirement` derives the single-sideband AM/PM inverse requirement
from the recorded shared-stress inputs without rerunning the lifecycle. It
records the source/stress-section hashes separately; it does not promote old
simulation evidence to current qualification.

`--ownership-turnaround` exercises RX→TX→RX inside the first RF stage of the
same retained analog lifecycle, without STOP or epoch change. It uses real
host-written prefill and records acquisition/completion/consumption accounting
under `ownership_turnaround_trace`. Assigned settling and ideal RF mute are
explicit assumptions; it is not a real packet response or physical launch proof.

`selected_lifecycle.py --turnaround-signal` audits recorded turnaround using only
complete host-delivered tone samples and nominal timestamps. Its late-record
fit is diagnostic, not causal acquisition; early residuals expose that direction
readiness does not yet imply signal readiness. It preserves original trace hashes.

### Response-critical direct stream

The current USB transport selection is the generic 100 MHz SDR direct stream
in `direct_stream.py`. Run `python3 -m unittest test_direct_stream
test_usb_selected_timing -q` from `verification/`. `BehavioralChip` owns the
modeled direct transport and lifecycle state; the external FPGA model owns
packet parsing, CRC and reply selection. The authoritative service record in
`contract.physical_services.usb_selected_service` supplies response allowances.
Finite CDC/credit behavior and packet replay are modeled; physical GPIO,
complete loaded electrical lifecycle and synthesizable RTL remain unqualified.
Framed-service controls do not qualify the selected direct-stream path.

### Warm hopping, CDR tracking and gain feedback

`timing_services.py` specifies bounded warm-hop readiness/epoch sequencing,
complete FPGA gain-loop latency and acquired type-II SSC tracking/holdover
screens. `verification/rf_gain_command.py` defines protected atomic gain and
sample-epoch messages. Run `python3 -m unittest test_timing_services
test_rf_gain_command -q` from `verification/`. Neither model predicts analog
settling or supplies a complete modem; those delays are qualification inputs.
Keep framed USB pad/record controls separate from the selected direct-stream
bench; the retired ProtocolService adapter is no longer an implementation.

The maintained `selected_revision_check.py --cdr-tuning` entry is a short
shared-supply loop/noise comparison: two local frequency ramps and one transition
gap per setting, with independent frequency and phase scoring. Model-only
`phase_gain`, `frequency_gain`, `detector_noise_rms_s` and
`holdover_frequency_slew_ppm_s` settings propagate through the physical receiver.
Defaults preserve the existing loop. These parameters do not create a chip ABI
or qualify their physical realization; the current comparison selects no new
default and does not replace full-cycle SSC/recovery testing.

`selected_revision_check.py --cdr-full-cycle` compares the integral loop with
the 256 UI least-squares candidate over two nominal 30 kHz, 5000 ppm downspread
cycles. Both use the same inventory/package/channel and 5 ps detector noise.
Each is run with continuous data and with 192/512 UI transition gaps in both
ramp directions. Independent scoring retains the existing phase and residual
limits; source timing never drives loop feedback. The `cdr_full_cycle` evidence
section has its own manifest. This is a finite diagnostic, not a jitter mask,
BER confidence bound or proof of physical estimator cost.
The phase audit records the worst sample and separates signed nominal-clock
drift, aperture change and source-phase movement. It reports both the entire
trace and the scored interval beginning at bit 1200. These components sum to
the measured drift; they are algebraic attribution, not independent noise powers
or proof of which circuit change will fix it. Short-gap and long-gap violation
counts help distinguish tracking failures from extended holdover problems.

`selected_revision_check.py --cdr-aperture-screen` reuses the full-cycle source
and gap cases with the 256 UI candidate at half/quarter of the assigned local
supply-to-delay sensitivity (0.05/0.025 ps/mV, same 1 GHz pole). It changes only
the aperture-delay tones; supply amplitude, voltage disturbance, detector noise
and resource allocations remain unchanged. Channel observations and feedback
are recomputed, so this is a coupled intervention rather than frozen-state
subtraction. The separate `cdr_aperture_screen` evidence does not establish the
physical cost or attainability of the reduced coupling.

The same CDR comparison includes optional `frequency_window_ui` interval
estimation (`0` retains integral feedback) and `frequency_average_gain`.
Only noisy observed edge timestamps and the receiver's period infer elapsed
cycles. Estimator state is speculative during forecast, committed with the word,
and cleared after excessive transition absence. Interval settings are candidate
math, with unresolved timestamp/counter precision and physical cost. Their
measurement window is not a holdover guarantee; no new default is selected.

`BehavioralChip.attach_wired_pad(pad, rail_source=..., max_step_s=...)` binds an
absolute-time supply waveform to the retained pad, direct USB exchange and output
release on STOP/fault. Omit the source to retain constant `Assumptions.supply_v`.
Callable rails require a positive integration step bound; split discontinuities
at call boundaries and verify step convergence for the forcing bandwidth. This
integrates instantaneous source work but does not itself solve PDN feedback or
supply-dependent clock/capture delay. Packet sampling remains an assigned phase.

`selected_revision_check.py --usb-common-packet` derives host-driven pad-rail
harmonics from the common package and USB inventory, with both host directions
at 100 MHz. It compares two integration step bounds through the actual direct
transport and electrical pad. Startup is prequalified for this experiment.
The packet screen compares an ideal current source with assigned finite output
resistance and supply sensitivity, then applies the existing maximum current trim.
`SharedWiredPad(current_source=...)` configures that local-source hypothesis; the
remote peer is independent. Dynamic reference-loop PSRR, threshold/delay
sensitivity, internal switching and pad-load feedback remain omitted. Neither
packet decoding nor current trim establishes electrical compliance.

`--usb-trim-envelope` is a fast settled-level inverse screen using the recorded
common USB rail interval and the architecture's current-code resolution. It keeps
the input report manifest/digest separate from new calculation sources. One fixed
code must cover both rail endpoints and independent ±5% termination intervals;
this is not a transient mask or proof of physical source-parameter bounds.

`SARParameters.diagnostic_reference_effective_cap_per_lane_f` models effective
reference-source charge for each selected ±VREF/4 diagnostic lane. Demand is
lumped at acquisition end and included in reference droop, recharge current and
charge balance. Zero is the ideal-load control; no value is physically qualified.
The retained diagnostic lifecycle check uses 0.25 pF per lane. Continuous source
impedance/bias, mismatch and switch injection are not modeled by this parameter.

With `frequency_fit='least_squares'`, the same optional CDR frequency window
accumulates five scalar sums of observed transition time versus inferred cycle
count. No source truth enters the fit, and speculative state is committed only
with the receiver word. `interval` retains the endpoint comparison control.
The current 256 UI fit improves short-ramp residual but does not meet 50 ppm;
finite-width implementation, full SSC/recovery and rare-error bounds remain open.

`SampledBurstRecords` converts sampled bits/quiet into generic START, data,
partial-byte and END records without protocol syntax or a supplied burst length.
The electrical USB trace uses it; expected source times only drive the peer and
score results. It holds one partial byte with assigned event-to-record delays.
A delayed request is tested. Fixed sampling phase and physical squelch performance remain
assumptions, so this is not burst CDR or on-chip USB SYNC recognition.

The generic burst assembler qualifies END after two quiet samples. A signal
return after a single quiet observation emits ABORT rather than silently losing
a bit. The electrical USB test injects a one-UI peer-drive dropout, checks that
no reply is emitted and recovers through STOP/restart with retained pad state.
This does not qualify comparator noise or phase acquisition.

`attach_analog_qualification(events, max_age_s=...)` bounds the freshness of
model observations. Repeated unchanged valid samples refresh coverage; a gap
longer than the bound resets the startup guard and faults active traffic.
`observe(time, valid)` must represent an actual modeled measurement, not desired
readiness. Omitting age retains legacy held-event semantics, not demonstrated
physical readiness. Physical sensor cadence/thresholds and hardware realization
remain unqualified; this mechanism is not itself sensor simulation.

`converter_qualification_events(..., max_observation_age_s=...)` derives validity
from SAR reference/supply observations and expires the two channels independently.
Expiry evaluations are not new measurements. The retained SAR transport exposes
this as `qualification_max_age_s`; omitted age preserves legacy held events.
Tests feed the computed events into chip readiness and show reference expiry
faulting traffic despite continuing good supply observations. Physical sensing
and the selected full-lifecycle monitor cadence remain unqualified.

Converter supply acceptance uses both bounds of
`contract.json:physical_services.sar_timing.startup.model_supply_window_v`
for readiness, retained transport, fault recovery and TX reference recovery.
The current 2.5–3.6 V interval is the assigned model domain, not a process
absolute maximum, sensor specification or ENOB guarantee. Reference validity
and observation freshness remain separate requirements; good supply alone
cannot qualify the converter.

`selected_revision_check.py --converter-timing` refreshes only the coupled
converter timing/loading section in the existing selected-revision report. It
crosses selected and adverse acquisition/reference/noise loading with 50/100/150 ps
assigned comparator regeneration, retaining delivered clock and reference-current
feedback. Use single-thread BLAS as above. The six cases are conditional tone
screens, not converter yield or packet-error qualification; see the current
converter decision in `spec/power-partition.md`.

`selected_revision_check.py --cdr-observed-bound` exercises the observation-derived
least-squares qualification candidate over the existing two-cycle SSC and gap
stimuli. It keeps the 0.25 UI criterion and supplies an explicit 50 ps total
edge-time error hypothesis and the phase-independent movement bound of the
supplied delay spectrum, compared with a25ps/quarter-coupling improvement.
The50ps control qualifies only about12.4percent; the stronger candidate sustains
continuous scored qualification but still loses qualification on inserted gaps.
Those stronger requirements are selected for implementation, not physically
qualified. Inspect effective residual-bound violations together
with qualified fraction and transport faults; zero errors or conservative
rejection alone do not establish the intended link capability.

`selected_lifecycle.py --ownership-diagnostics` runs the same retained RF/wired/USB
composition with stopped zero, +/-VREF/4 and normal ADC selections in its three
RF receive epochs. It records host-delivered samples and charges the retained
reference for an assigned 0.25 pF effective source load per diagnostic lane.
Reported reference-loss and USB analog faults advance an FPGA-owned condition
generation; the shared calibration gate rejects pre-fault diagnostic records
after recovery. This verifies selection/delivery and invalidation, not fitted
correction deployment, absolute reference accuracy, serialized fault-poll latency
or measured requalification.

The retained retune and fault-continuation paths now select causal held-current
modal propagation for reference recharge. Run `selected_lifecycle.py --causal-recharge`
from `verification/` to refresh `selected-lifecycle.json:causal_reference_continuation`.
The selected retune and continuation converge with stable words and clock counts;
this fixed-duration SAR fixture does not qualify asynchronous comparator deadlines.
The prefix gate remains mandatory because current-grid boundary cells and coupled
clock iteration are still approximations. Older FFT campaigns retain their original scope.
