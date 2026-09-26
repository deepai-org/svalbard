# Measured GF180 AFE reverse analysis

The fabricated AFE demonstrates useful analog operation in GF180. Its open layout
supports detailed reconstruction, but the published measurements do **not** uniquely
identify device or parasitic parameters. Our circuit replays are conditional PDK
predictions; they have not jointly reproduced measured amplifier or ADC performance.

## Measurement validation status and next work

The [measurement audit](../../evidence/reference-afe-measurement-audit.json) is the
entry point for silicon-facing conclusions. Detailed reports below preserve the
experiments; test counts and informal completion percentages are not measures of
physical identification.

| Question | Current conclusion | Consequence |
| --- | --- | --- |
| Does the amplifier replay match silicon? | Nominal reconstruction gives 116.49 dB/20.30 MHz, versus authors' simulation 99 dB/14 MHz and measurement 92 dB/12.5 MHz. | Resolve reconstruction/bias/load differences before assigning the discrepancy to fabrication. |
| Does matching bandwidth identify missing capacitance? | Doubling compensation gives 12.49 MHz but leaves gain 24.48 dB too high. | A single matching metric is not a parasitic extraction. |
| Are ADC measurement conditions recovered? | Tone amplitude, references, calibration and analog biases are not all identified. | Keep the 20 MS/s table, near-Nyquist spectrum and sensor demonstration distinct. |
| Does the reference model explain complete conversion accuracy? | A forced transistor sequence and an autonomous mathematical SAR both retain reference memory; the latter uses ideal sampling/comparison. Neither jointly reproduces measured spectral shape and conditions. | Reference memory is demonstrated conditionally, not calibrated to silicon. |
| Can the measured spectrum identify nonlinear transfer? | Several distinct monotonic transfers fit the observed magnitudes. | Carry uncertainty into RF analysis instead of choosing one fitted coefficient. |
| Does this establish GHz/RF performance? | No measured fT/fmax, RF NF or PLL phase noise. | Those transceiver assumptions remain unvalidated. |

**Investigation paused; findings consolidated.** The active transceiver work now
uses the [adopted assumptions and uncertainty ranges](../../spec/risk-priorities.md#adopted-assumptions-and-uncertainty-ranges).
No additional reference-chip sweep is queued. Resume for new measurement evidence
or a bounded question whose answer would change the transceiver architecture.
The unexecuted consecutive-decision common-mode experiment is deferred, not a result.

An eventual ADC explanation would need spectral shape, noise, transfer range and
functional timing under compatible conditions. Amplifier inversion would need to
respect unknown biases and loading. Those remain unresolved; the records below
are conditional mechanism studies, not a completed silicon calibration.

### Which physical characteristics are actually constrained?

| Quantity | Evidence and remaining uncertainty | Use in the transceiver |
| --- | --- | --- |
| Device sizes and circuit connectivity | Recovered geometry, with selected author/submission cells cross-checked; not full-chip LVS. | Concrete implementation examples, not measured transistor speed. |
| Absolute capacitance and switch charge | Geometry plus PDK/field calculations; conditional on density, omitted coupling and operating point. | Sweep acquisition and reference loading; do not label the values silicon-calibrated. |
| Amplifier transconductance, output conductance and compensation | Gain/bandwidth constrain combinations. The effective two-observable model has a scale ambiguity, and the reconstructed circuit does not jointly match measurements. | No independently measured gm, ro or missing-C correction can be transferred. |
| ADC nonlinear transfer | Published harmonic magnitudes constrain spectral shape at an incompletely specified operating point; phase and input normalization are unknown. | Retain multiple nonlinear scenarios and amplitude dependence. |
| Sampling common mode and comparator interaction | Conditional sampler replay predicts motion in both differential and common-mode outputs; no matching measured internal waveform. | A differential-only impairment cannot bound this interaction. |
| GHz speed, RF noise and clock phase noise | Not measured by this AFE publication. | Keep explicit unvalidated assumptions; do not narrow them from these low-frequency results. |

Further reference-chip simulation earns priority only if it discriminates between
measurement explanations or changes a transceiver budget. Better numerical
agreement between two PDK-based models alone does neither. Missing bench conditions
limit identification even when a simulation is precise.

The measurement audit also quantifies why the reported 41 dB SNR does not usefully
calibrate sampling capacitance or clock quality. With independent thermal noise
in two equal sampling capacitors, differential variance is `2kT/C`. At 300 K,
assuming differential tone peaks of 0.3, 1.53 or 3 V gives necessary per-leg
capacitance lower bounds of only 2.32, 0.089 or 0.023 fF. These are far below the
geometry-based approximately 666 fF array estimate; the SNR cannot select its
actual capacitance. Tone amplitude is unknown, so none is an unconditional bound.

Similarly, assigning the entire noise allowance to independent aperture jitter
gives `sigma_t <= 10^(-SNR/20)/(2*pi*f)`: about 284 ps at an assumed 5 MHz tone or
142 ps at 10 MHz. The table's tone frequency is not recovered, and these loose
scenario limits do not establish oscillator phase noise or GHz timing quality.
Other noise sources consume the same allowance. Filtering, correlated noise or
a different SNR definition require a different decomposition. Thus neither a
capacitance calibration nor a tighter transceiver clock budget follows from this
measurement alone.

## Provenance and evidence boundaries

- [Author release](https://github.com/idea-fasoc/openfasoc-tapeouts/tree/5a6040bfe6735d6898d926b5b01a6d7650d50106/mpw18h1), Apache-2.0; `gds/TOP_v4.tgz`.
- [Shuttle submission](https://foss-eda-tools.googlesource.com/third_party/shuttle/gf180mcu/mpw-18h1/slot-004/); `gds/user_project_wrapper.gds`, blob `a7a49d03132b75a7d51bc742c0edd747bfb2fd5e`.
- [Measured paper](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957346), Tables 1–2 and Figure 7, printed page 54; circuit/conditions on pages 52–53 and sensor setup in Figure 9.
- [Pinned transistor models](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_pr/tree/9f992d5a9186d1f7820c58f039c484ad35b2edea/models/ngspice).
- [Pinned analog pad](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_io/tree/ac11a2506a6657e5674048ba2be44224c74b9e9e/cells/asig_5p0).

[Provenance checks](../../evidence/reference-afe-analysis.json) establish flattened
polygon equality for nine key analog cells between author and shuttle layouts,
not full-chip LVS. Pad geometry matches the public pad except layer 63/63. Reports
pin source/model hashes. Generic extraction is not foundry signoff.

Use four evidence classes: **measured** chip-level results; **reconstructed**
geometry/connectivity; **conditional** PDK/mathematical scenarios; and
**unidentified** physical quantities. None is interchangeable with another.

The [release audit](../../evidence/reference-afe-release-audit.json) found:

- Released comparator netlist: 12 instances/L=0.40 µm; submitted comparator: 97 fingers/L=0.28 µm. The testbench is not the recovered fabricated circuit's bench setup.
- Released amplifier testbench: separate two-stage design, not the measured folded-cascode amplifier. No matching folded-cascode testbench was found in the pinned tree.
- Parent metal trace confirms external VBIASN/VBIASP in addition to VPROG. Published Vprog=1 V does not specify all biases.
- FET notebook derives gm/gds/capacitances/fT from simulator internals, not measured RF devices.
- The alternate NIST publication title links the same paper, not independent corroboration.

This is a targeted public-source audit, not proof that no other material exists.

## What the measurements constrain

| Published observation | Defensible implication | Not uniquely identified |
| --- | --- | --- |
| ADC >30 MS/s functional; 4.27 ENOB at 20 MS/s | Functionality and precision are different observations; conventional ENOB implies 27.47 dB SNDR. | Precision at maximum rate; internal decision timing |
| SNR 41 dB; SFDR 33.7 dB | Under compatible definitions/conditions, noise is 0.891% and aggregate distortion 4.139% of signal RMS. | Absolute error without tone amplitude; individual capacitor/noise/jitter contributions |
| Amplifier 92 dB gain, 12.5 MHz GBW | Combined gain/pole constraints | gm, output conductance and compensation separately |
| CMRR 58 dB; PSRR 81.5 dB | Input-equivalent response 1.259 mV/V and 84.14 µV/V | Device mismatch distribution or RF rejection |
| Offset 5–20 mV; power <10 mW | Reported circuit range and shared-rail upper estimate | Statistical sigma or isolated branch currents |

The simple equivalent `A=gm/go`, `fu=gm/(2πC)` has an unobservable common scaling
of gm, go and C even with exact gain/bandwidth measurements. Real topology and
missing bench conditions add uncertainty. No global measured/simulated correction
factor for GF180 follows from this chip.

A jitter-only reading of 41 dB SNR at 5 MHz permits about 284 ps RMS: far too weak
to qualify GHz clocks. The full-range voltage is not the confirmed FFT amplitude.
The paper attributes ADC distortion to MOM extraction, especially small cells;
that is a candidate explanation, not a uniquely recovered capacitance matrix.

**Do not combine incompatible setups.** Figure 9 uses 2.5/0.8 V sensor-board
references. The reconstructed direct-sampled monotonic CDAC then has at most
±1.7 V differential correction (about 3.4 Vpp coverage), verified by charge
redistribution. The table's 6 Vpp range would require different references or
input transfer. A hypothetical 6 Vpp sine at the sensor references clips 61.7%
of samples and gives about 13.93 dB SNDR in an ideal limiter. This inconsistency
does not show the fabricated ADC clipped; the setups are not established as equal.

### Measured spectrum and inverse ambiguity

[Figure 7 digitization](../../evidence/reference-afe-figure7-screen.json) uses the
native embedded raster, not upscaled pixels. Three prominent inset peaks are
about 36/45/45 dB below the tone (roughly 1 dB reading precision), regularly spaced
in a way compatible with aliased odd harmonics of the annotated 4.99023 MHz tone
at an assumed 10 MS/s. Modulation can also produce a comb. Inset peaks do not
establish full-band SFDR, integrated noise, absolute input voltage or FFT scaling.

Under the third/fifth/seventh interpretation, matching the first peak with
symmetric clipping predicts the next two at −37.56/−40.52 dBc; tanh compression
predicts −69.86/−103.85 dBc. Neither restricted family jointly fits the figure.
This does not exclude combinations of mechanisms. Eight different monotonic
Chebyshev transfers reproduce all three magnitudes exactly while differing in
unobserved harmonic phase. Their derivative extrema confirm monotonicity.
Magnitude-only observations therefore do not uniquely identify transfer curvature.

Constant offset alone contributes DC, not harmonic distortion. The
[converter screen](../../evidence/reference-afe-converter-screen.json) distinguishes
that from clipping/nonuniform threshold error. A single cubic plus white noise
matching table SFDR/SNR yields about 5.18 ENOB, not 4.27, **if** those metrics share
conditions. Neither exercise identifies the measured ADC's physical cause.

## ADC geometry and loading

[Device inventory](../../evidence/reference-afe-device-geometry.json),
[preamp extraction](../../evidence/reference-afe-preamp.txt) and
[capacitor geometry](../../evidence/reference-afe-cap-geometry.json) establish:

| Reconstructed item | Result | Interpretation |
| --- | --- | --- |
| ADC bounds | 972.92 × 309.64 µm; 0.3013 mm² | Includes routing/decoupling, not transistor-only area |
| Two CDAC array rectangles | Combined 0.1005 mm² | Not a complete passive-area budget |
| Preamp input/tail devices | W/L=24/0.28 µm; 12 × 2 µm fingers | Actual drawn devices, not a generic “180 nm” estimate |
| Preamp output resistors | Ten parallel 10 × 1 µm high-poly per side | About 1 kΩ assuming 1 kΩ/square |
| Comparator input devices | W/L=16/0.28 µm; complete comparator 97 fingers | No measured fT or regeneration bound |
| Sampling switches | W/L=48/0.28 µm, 3.3 V class | Driver also contains 6 V-class/L=0.6 µm devices |
| Bootstrap capacitors | Two 12 × 24 µm MIM plates | 576 fF each only at assumed 2 fF/µm² |
| Area-only CDAC per side | 0.666 pF nominal; 0.569–0.797 pF density scenarios | Fringe/full matrix omitted; not a calibrated statistical interval |

### Comparator connectivity and conditional decision time

[Standalone/coupled comparator reports](../../evidence/reference-afe-comparator-sim.json)
([coupled](../../evidence/reference-afe-comparator-coupled.json)) identify sensitivity
to preamp impedance and operating point. Nominal ideal-source decisions take
roughly 0.3–0.5 ns; finite input networks produce common-mode kickback of tens to
hundreds of millivolts. A ±10% source-impedance imbalance can reverse a 1 mV
standalone decision. Actual preamp coupling with asymmetric loads can already
create the wrong DC polarity before the clock: it is not isolated kickback.

[Topology tracing](../../evidence/reference-afe-comparator-trace.json) supports
externally set preamp bias and disabled calibration when offcal_en=0. Actual
measurement settings, mismatch, noise and regeneration tails remain unidentified.
A wrong near-zero decision is not by itself evidence explaining spectral ENOB.

### Capacitor ratios and electrostatic uncertainty

The [ratio screen](../../evidence/reference-afe-ratio-screen.json) gives area/perimeter
endpoint errors far smaller than the large-tone distortion implied by the table,
**if** that DAC-error envelope also bounds the ADC transfer. It does not test every
capacitance error or disprove the authors' explanation. kT/C scenarios are also
conditional on actual sampling capacitance and tone amplitude.

[Parent routing](../../evidence/reference-afe-parent-routing.json) adds cross-bit
paths absent from isolated cells. A [2-D field screen](../../evidence/reference-afe-fringe-screen.json)
for one B0–B2 run gives 2.65–2.86 fF, with mesh/boundary sensitivity and missing
shielding/finite-end effects. This is not converged 3-D PEX. In the
[charge matrix](../../evidence/reference-afe-cap-matrix-screen.json), that path adds
about 1.6–1.7% to B0 reference charge without changing ideal-driven final top voltage.
Capacitance location matters; an arbitrary scalar “extra C” can change the wrong
physical behavior. A full matrix, small-cell ratios and substrate/well RC remain open.

### Dynamic differential sampling narrows the bootstrap hypothesis

[Recovered bootstrap replay](../../evidence/reference-afe-bootstrap.json) shows
amplitude-dependent gate-overdrive loss with the fabricated body connections.
At 20 MS/s and a near-5 MHz tone, large-swing/load scenarios give SFDR roughly
37–43 dB, whereas a smaller swing gives about 75 dB. A counterfactual well
connection improves the large-swing result, identifying sensitivity rather than
a proven fabrication fix. These are sampler waveforms, not ADC codes or a match
to Figure 7's conditions. Source impedance, full loading, reference behavior and
code conversion are not combined in that test.

A shorter near-Nyquist replay at 10 MS/s and 4.9609375 MHz gives third/fifth/seventh
harmonics of −68.6/−92.1/−97.6 dBc at 0.765 V per-leg peak. At 1.5 V per-leg peak
and 0.666 pF loading they become −42.5/−42.8/−45.8 dBc. The digitized figure gives
approximately −35.8/−45.2/−45.2 dBc, with about 1 dB reading precision: neither
scenario jointly matches it. Halving the timestep changes these large-swing
harmonics by less than 0.005 dB, establishing numerical stability for that
refinement, not physical accuracy. The 256-sample replay is about 0.59% below
the figure's annotated tone; longer exact-frequency attempts timed out without
spectral results.

The large-swing case also moves held common mode by about 68 mV. Its retained
two-leg samples permit later conditional preamp/comparator analysis without
repeating the sampler simulation. This approximately 6 Vpp differential stress
case cannot be combined with the sensor demonstration's 2.5/0.8 V references
as an unclipped full-ADC benchmark. Unknown measurement amplitude prevents using
these results to identify actual sampler distortion or a unique parasitic load.

The [autonomous SAR report](../../evidence/reference-afe-sar-transfer.json) now also
retains a one-way connection of the lower-swing sampler's two held legs into the
capacitor/reference model. At 1.53 Vpp per input leg (3.06 Vpp differential), the
waveform stays within the assigned 2.5/0.8 V reference range. Ideal references
give third/fifth/seventh harmonics of −69.1/−103.9/−89.4 dBc; adding 1 kΩ reference
sources, 100 pF reservoirs and span-dependent switch charge gives
−54.6/−78.2/−86.0 dBc. This combined scenario still does not explain the measured
higher harmonics. Its ideal-reference decisions independently match a scalar SAR
recurrence exactly. Both held voltages are preserved, but ideal acquisition and
comparison omit bidirectional sampler/CDAC loading and real comparator common-mode
sensitivity. The retained input JSON text and hash permit replay without another
transistor run; pass its restored filename as the optional fifth script argument.

**The conversion's common-mode trajectory is a larger untested interaction than
sampler ripple alone.** In this lower-swing replay, held common mode is already
about 1.582–1.587 V. Monotonic switching lowers it to 0.732–0.737 V by the last
ideal-reference decision, or 0.766–0.770 V with the finite-reference scenario.
The ideal trajectory independently satisfies
`VCM(bit) = VCM(sample) - reference_span * sum(previous_weights)/2` for normalized
weights, regardless of decision polarity. Earlier coupled preamp/comparator
experiments applied a fixed 1.65 V at the preamp input; their successful decisions
do not establish operation across this trajectory. The comparator itself sees
the preamp output, so these voltages must not be assigned directly to its inputs.
Preamp gain, tail-current compliance and resulting comparator operating point
through the late decisions are now a higher-value check than another isolated
reference-impedance sweep. This is a coverage gap, not proof that silicon fails.

The subsequent [coupled common-mode screen](../../evidence/reference-afe-comparator-coupled.json)
tests static preamp input common modes 0.735, 0.770, 1.16, 1.585 and 1.65 V at
three bias settings, both ±1 mV polarities, matched loads and nominal PDK conditions.
All 30 cases resolve correctly in approximately 0.50–0.57 ns after the clock edge.
There is no hard cutoff in these scenarios. However, lowering input common mode
from 1.65 to 0.735 V reduces preamp differential gain from 1.24 to 0.89 at 0.8 V
bias, 2.26 to 1.29 at 1.0 V bias, and 2.83 to 1.45 at 1.2 V bias. Thus static
gain falls about 29–49%; an input-referred comparator-noise or offset budget cannot
use the initial gain throughout the conversion. No actual noise increase is
measured or simulated here. Consecutive common-mode steps, small residuals,
mismatch, calibration and dynamic recovery remain outside these static snapshots.

### Controller connectivity toward a full conversion sequence

[Controller trace](../../evidence/reference-afe-controller-trace.json) and
[logic reconstruction](../../evidence/reference-afe-controller-logic.json) establish
14 sequence stages, decision storage and 13 controlled capacitors per side.
Comparator-valid OR logic advances the sequence; an externally biased pulse chain
sets reset timing. [Register](../../evidence/reference-afe-register-sim.json) and
[pulse-generator](../../evidence/reference-afe-pulsegen-sim.json) replays check local
behavior, not setup/hold, metastability or measured timing.

The [closed loop](../../evidence/reference-afe-controller-loop.json) completes
14 fixed-input decisions in about 34.6 ns after reset release. With
[CDAC feedback](../../evidence/reference-afe-controller-feedback.json), it takes
about 35.8 ns. These nominal cases **do not reproduce >30 MS/s including acquisition**.
A coordinated ramp enables startup in the tested setup; this is not a startup
qualification. Area-only capacitance, ideal sampling and assigned bias remain
material assumptions. One correct word is not a transfer curve or ENOB result.

### Reference drivers and switched-charge budget

[Parent driver extraction](../../evidence/reference-afe-reference-drivers.json)
finds Wn/Wp=32/64 µm for B0–B1, 16/32 for B2–B4 and 8/16 for B5–B12, all L=0.28 µm.
[Transient replays](../../evidence/reference-afe-reference-transient.json) require
both sourcing and sinking; high-rail droop alone misses low-rail uplift.

| Conditional finding | Model consequence |
| --- | --- |
| Floating 0.75+0.75 pF load and 100 pF reservoir: ideal sharing gives 6.35 mV uplift versus about 8.95 mV transistor peak. | Ideal capacitors omit device switching charge. |
| Summed reference overhead is about 0.424 pC at 1.7 V span; nominal terminal balance is about 87.5% gate and 12.5% body charge. | The apparent 249 fF is not a grounded output capacitor; preserve multi-terminal charge. |
| Across 0.5–2.3 V spans, overhead is approximately `0.177 pC + 0.146 pF × span`; withheld nominal case differs about 0.25%. | Conditional reduced law, not universal capacitance, zero-span extrapolation or PVT fit. |
| Edge speed changes rail partition and peak disturbance despite nearly unchanged summed charge. | Endpoint charge alone is not a transient model. |
| Actual small driver overhead is about 0.106 pC for B5/B12. | Reference demand does not decay with binary capacitor weight. |
| B12 overhead is about 521× its area-only plate charge. | This is reference/control overhead, **not** direct top-plate injection or a count of lost ADC bits. |

The [finite-reference controller](../../evidence/reference-afe-controller-references.json)
retains two 100 pF reservoirs with assigned bidirectional ±150 µA feedback.
A 1 kΩ source changes the decision word; a second conversion retains the same word
but further shifts the rails, with about 2.44% reference-span loss at its last
decision. Timing success, peak droop, final error and accuracy are distinct.
No measured reference impedance or supply budget follows from those chosen values.

The [fast forced-sequence model](../../evidence/reference-afe-reference-sequence.json)
reduces reference-voltage error versus the transistor replay from about 9.3 mV RMS
to 1.0–1.3 mV by adding independently derived charge overhead. It includes both
arrays, reset and reference memory, but imports decision times/words. Linear RC
recovery and instantaneous charge transfer omit nonlinear buffer dynamics. This
is useful simulation-to-simulation reduction, not silicon validation.

The [autonomous mathematical SAR screen](../../evidence/reference-afe-sar-transfer.json)
now chooses all fourteen signs from its own capacitor state and emits binary codes.
At an assumed 10 MS/s, 4.990234 MHz tone and 90% of its modeled 3.4 Vpp range:

| Reference scenario | Noiseless SNDR | Third/fifth/seventh harmonic levels |
| --- | --- | --- |
| Ideal references, area-only weights | 70.00 dB | −99.6 / −99.2 / −103.3 dBc |
| 1 kΩ/100 pF, plate charge only | 52.99 dB | −53.2 / −95.9 / −88.5 dBc |
| Same, with large-driver charge partition | 52.63 dB | −53.0 / −100.8 / −84.0 dBc |
| Same, with small-driver charge partition | 52.56 dB | −52.8 / −85.1 / −96.3 dBc |

These differ substantially from Figure 7's approximate −36/−45/−45 dBc peaks.
Thus this particular reference-memory scenario does not explain the measured
spectral shape, despite substantial rail movement. The ideal case agrees exactly
with an independent scalar SAR recurrence; doubling warmup from 128 to 256 samples
leaves the selected finite-reference spectrum unchanged. Sampling and comparators
are ideal, timing is fixed, and source amplitude/references are assumed. Real
bootstrap behavior, preamp loading/kickback and full capacitor matrix are still
missing. This is a complete mathematical *conversion sequence*, not a complete
physical ADC or a measurement-calibrated model.

A 2–10 kΩ source-resistance sensitivity at fixed 100 pF reveals an overload
transition. At 6 kΩ, the third harmonic is −35.59 dBc (near the figure), but
fifth/seventh are −56.26/−55.36 dBc, roughly 10–11 dB too weak. At 7 kΩ, they
become −32.39/−45.58/−46.35 dBc: higher harmonics nearly match while the third is
3.37 dB too strong. The reference span then ranges about 1.384–1.482 V and final
comparator residual reaches 48 mV. Doubling warmup leaves those harmonics unchanged.
This makes reference-induced overload a plausible contributor, **not an inferred
6–7 kΩ silicon impedance**. None of the sampled settings jointly fits all three
peaks within the approximate reading precision. Untested impedances, R/C pairs,
amplitudes and other mechanisms are not excluded. Applying the independently
characterized span-dependent charge law changes the 7 kΩ harmonics to
−33.58/−48.52/−48.64 dBc, removing the earlier near-match of the higher harmonics.
All charge evaluations remain inside the tested 0.5–2.3 V span interval; midpoint
shifts up to 16 mV and rail-partition changes remain uncharacterized. Nominal-law
regression and doubled warmup agree exactly. An apparent one-point spectral fit
is therefore not robust enough to identify the physical source impedance.

## Amplifier reconstruction and inverse constraints

[Amplifier inventory](../../evidence/reference-afe-amplifiers.json) identifies
opamp2 as structurally consistent with the reported complementary-input folded
cascode. Each input device totals W/L=400/0.3 µm; output N/P devices total
100/0.3 and 150/0.3 µm. Two nominal 5 pF compensation branches connect output to
**different gate nodes**, not 10 pF to ground. MIM option, bias and effective
compensation are not uniquely determined by GBW.

[DC/AC replay](../../evidence/reference-afe-amplifier-sim.json) shows that cascode
headroom can change gain dramatically with little GBW change. The nominal
116.49 dB/20.30 MHz point uses about 5.81 mW, but its biases/load are not recovered
measurement settings. Changing VBN from 1.5 to 1.8 V reduces gain to about 75.6 dB
while GBW stays near 20.2 MHz. This is circuit-specific sensitivity, not a process
variation distribution. DC convergence assistance and ideal DC feedback do not
establish physical startup or closed-loop stability.

### External routing and the output-switch penalty

[Pad routing](../../evidence/reference-afe-pad-routing.json) confirms that external
VOUT is after a transmission gate, while the internal vout node is not directly
pad-connected. Its nominal incremental resistance is about 199 Ω. Moving an
assigned 20 pF load from internal output to the external side changes simulated
phase margin from about 37.8° to 18.2°. Load placement matters, not just total C.
Inverse-width switch scaling trades resistance against gate/junction loading;
no RF switch qualification follows from this low-frequency operating point.

## Analog-pad loading and distortion

[Pad reconstruction/replay](../../evidence/reference-afe-pad-constraints.json)
gives about 0.874 pF nominal junction capacitance, with 0.787–1.073 pF bias/corner
scenarios before metal/package capacitance. These are PDK estimates, not measured
RF S-parameters. At 2.4 GHz, reactance is significant, but an isolated reactance
is not a complete insertion-loss or matching prediction.

A 5 MHz, large-swing pad scenario gives roughly 77.8/63.9/47.1 dB SFDR for
200 Ω/1 kΩ/10 kΩ sources. It does not alone explain the table's 33.7 dB SFDR under
those scenarios. Actual package/board impedance, source waveform and protection
operating point remain unknown.

## Transceiver model changes and limits

`ADCImpairments` now carries optional finite acquisition, static nonlinear transfer
and sample noise before quantization. Explicit R/C/acquisition time controls
persistent analog held state; it is not additional digital FIFO storage. The RC
update is exact for a constant target per window, not arbitrary waveform motion
or signal-dependent switch resistance. Default conversion remains linear,
noiseless and instantaneous before the existing quantizer.

The cubic and optional third/fifth/seventh Chebyshev transfers are **scenarios**.
The latter enforce a sufficient monotonicity bound and tangent continuation beyond
normalized full scale; quantizer clipping remains separate. The
[transfer-ambiguity experiment](../../evidence/reference-afe-transfer-ambiguity.json)
propagates eight equally tone-compatible curves through RF projections without
mutating live analog/RNG state. On an HE20 waveform at normalized axis peak 0.6,
gain-corrected unquantized differences range from 0.28% to 2.31%; at 0.9 they range
from 0.93% to 3.24%. **These are neither exhaustive uncertainty bounds nor measured
transceiver EVM.** Higher orders, dynamics, noise and the unknown input normalization
permit other behavior. Whole-chain cases separately include 12-bit quantization.

The same experiment separately propagates the table's 41 dB SNR through a
noise-only ADC scenario. At HE20 axis peak 0.6, assuming the characterization
sine occupied 0.1, 0.5 or 1.0 of converter axis full scale predicts RMS noise
of 0.38%, 1.91% or 3.82% of the RF waveform RMS. Thus unknown characterization
amplitude alone permits a tenfold difference across these assigned scenarios.
This assumes independent white I/Q noise and unchanged integrated noise at the
RF fixture sampling rate; it does not identify actual noise bandwidth or density.
No clipping/quantization is applied to this isolated comparison. Table noise and
figure harmonics are deliberately separate experiments because their measurement
conditions are not established as identical. These are sensitivity results,
not a measured RF noise budget or packet EVM.

Existing converter regression results are unchanged. No new packet-compliance,
autonomous-clock or tapeout qualification is implied. The practical design lessons
are to budget acquisition/headroom jointly, retain signed per-decision reference
charge and state, include external switch/pad loading, and evaluate multiple
nonlinear scenarios. [Risk priorities](../../spec/risk-priorities.md) keep physical
clock quality, the complete RF chain and coexistence unclosed.

## Reproduction and remaining identifiability limits

Dependencies: Python, NumPy/SciPy, KLayout and ngspice (replays used ngspice 42).
Keep downloaded GDS/model files and intermediate extractions outside the repo.
Scripts print JSON/text; retained reports contain source/model hashes. From this
directory, representative commands are:

```sh
python analyze.py AUTHOR.gds SUBMITTED.gds
python cap_geometry.py SUBMITTED.gds adc_top_async_wdac_offcal 0
python cap_geometry.py SUBMITTED.gds adc_top_async_wdac_offcal 1
python preamp_extract.py SUBMITTED.gds opamp2_to_fix --json --raw --bulk > /tmp/amp.json
python amplifier_sim.py /tmp/amp.json MODEL_DIRECTORY
python preamp_extract.py SUBMITTED.gds adc_bootsw_debug5 --json --raw --bulk --voltage-classes > /tmp/boot.json
python bootstrap_sim.py /tmp/boot.json MODEL_DIRECTORY
python comparator_trace.py SUBMITTED.gds
python preamp_extract.py SUBMITTED.gds adc_comp_miyahara_offcal --json --raw --bulk --voltage-classes > /tmp/comp.json
python comparator_sim.py /tmp/comp.json MODEL_DIRECTORY
python preamp_extract.py SUBMITTED.gds adc_preamp_v2 --json --raw --bulk --voltage-classes > /tmp/preamp.json
python comparator_sim.py /tmp/comp.json MODEL_DIRECTORY /tmp/preamp.json
python reference_drivers.py SUBMITTED.gds
python controller_trace.py SUBMITTED.gds
python preamp_extract.py SUBMITTED.gds adc_top_final_deliver --json --bulk --voltage-classes > /tmp/adc-full.json
python controller_logic.py /tmp/adc-full.json
python preamp_extract.py SUBMITTED.gds lib_dff --json --raw --bulk --voltage-classes > /tmp/dff.json
python preamp_extract.py SUBMITTED.gds lib_dff_wreset --json --raw --bulk --voltage-classes > /tmp/dff-reset.json
python register_sim.py /tmp/dff.json /tmp/dff-reset.json MODEL_DIRECTORY
python pulsegen_trace.py SUBMITTED.gds > /tmp/pulse-map.json
python preamp_extract.py SUBMITTED.gds lib_pulsegen --json --raw --bulk --voltage-classes > /tmp/pulse.json
python pulsegen_sim.py /tmp/pulse.json /tmp/pulse-map.json MODEL_DIRECTORY
python pulsegen_trace.py SUBMITTED.gds adc_preamp_comp_controller_probe_offcal > /tmp/controller-map.json
python preamp_extract.py SUBMITTED.gds adc_preamp_comp_controller_probe_offcal --json --raw --bulk --voltage-classes > /tmp/controller.json
python controller_sim.py /tmp/controller.json /tmp/controller-map.json MODEL_DIRECTORY .1 180 ramp
python controller_sim.py /tmp/controller.json /tmp/controller-map.json MODEL_DIRECTORY .05 120 ramp 50 cdac
python controller_sim.py /tmp/controller.json /tmp/controller-map.json MODEL_DIRECTORY .05 120 ramp 50 cdac finite 1000
python controller_sim.py /tmp/controller.json /tmp/controller-map.json MODEL_DIRECTORY .1 150 ramp 100 cdac finite 1000
python preamp_extract.py SUBMITTED.gds lib_dac_sw_msb --json --raw --bulk --voltage-classes > /tmp/ref-msb.json
python reference_transient.py /tmp/ref-msb.json MODEL_DIRECTORY
python reference_transient.py /tmp/ref-msb.json MODEL_DIRECTORY falling
python pad_trace.py SUBMITTED.gds
python pad_constraints.py SUBMITTED.gds RELEASED_PAD.gds PAD.cdl MODEL_DIRECTORY
python fringe_screen.py SUBMITTED.gds
python fringe_screen.py SUBMITTED.gds --lateral-only
python cap_matrix_screen.py
python converter_screen.py
python reference_sequence.py
python sar_transfer.py large_partition
python sar_transfer.py large_partition 256 7000 span
python measurement_audit.py
python figure7_screen.py PAPER.pdf
python transfer_ambiguity.py
```

`device_geometry.py`, `preamp_bounds.py`, `ratio_screen.py`, `physical_constraints.py`
and `amplifier_constraints.py` document their remaining report inputs in their
headers. Generic extraction preserves disconnected label islands rather than
implicitly shorting names. MIM Option B requires splitting Via4 over FuseTop;
hierarchical extraction avoids expanding millions of repeated pad-ring vias.
Raw fingers avoid changing MOS model bins through width regrouping.

Unresolved quantities are explicit rather than fitted away: exact MIM option,
full 3-D capacitance matrix, well/substrate RC, reference/source impedances,
conversion timing, comparator noise/regeneration, measurement-chain noise,
package/board parasitics and statistical device mismatch. The existing aggregate
measurements cannot uniquely distinguish these. Complete extracted ADC replay,
raw measured spectra versus amplitude/rate, or independently characterized
structures would be needed to separate their contributions. No claim here
establishes RF, SerDes, autonomous-clock or transceiver tapeout feasibility.

Additional supporting reports retained from the detailed analysis:

- [Preamp RC scenarios](../../evidence/reference-afe-preamp-bounds.json).
- [Physical constraints](../../evidence/reference-afe-physical-constraints.json).
- [parent-restored supply/body joins](../../evidence/reference-afe-pulsegen-map.json).
