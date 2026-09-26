# Clock architecture feasibility envelope

The [coupled REF_IN edge screen](power-partition.md#ref_in-voltage-and-clock-edges-with-moving-return)
now includes board-referenced input voltage against moving analog ground and
the input capacitance's own return current. At the selected package target,
the tied baseline adds roughly 9 ps RF / 11 ps wired deterministic input-edge
RMS before other impairments. Coherent supply delay and partition alternatives
are compared explicitly. The [assigned-ENOB wideband RF bench](power-partition.md#corrected-ref_in-clock-in-the-rf-conversion-chain)
now consumes corrected event timing with retained source/input noise. Moderate
wideband SAR feedback and the narrowband packet exchange also use that input
path, including recharge-induced threshold movement and supply delay. The
corrected narrowband campaign exposes packet failures described in the
[current risk assessment](risk-priorities.md#whole-chip-risk-ranking).
Weak-wideband causal feedback, TX load transitions and wired timing consumers
still require migration; receiver numerical sensitivity remains open. Independent wired RX
CDR must not inherit an external-TX timing path by assumption.
The observed cancellation is conditional on the assigned positive 0.1 ps/mV
supply sensitivity and its 1 GHz pole. Characterization has not established
the sign, magnitude or stage distribution; migration must bracket those
quantities rather than assume the favorable correlation persists.

An exact sign-flip diagnostic can be obtained from the saved edge variances:
`var(input - delay) = 2 var(input) + 2 var(delay) - var(input + delay)`.
At 2.484 GHz and the current package target, reversing the entire assigned
downstream sensitivity gives 9.71 ps RMS for the tied baseline,
5.60 ps for the equal split and 5.72 ps for the site-weighted split,
compared with 9.25, 2.54 and 3.29 ps for the original sign. These are deductions
from [recorded deterministic edge statistics](../evidence/selected-baseline.json),
with input crossings and supply transfer held fixed; they do not bracket
arbitrary stage-specific phases, magnitude or nonlinear threshold dependence.

This is a conditional requirements envelope, not demonstrated GF180 clock quality.
[Executable calculations](../verification/clock_envelope.py) produce the
[source-hashed report](../evidence/clock-envelope.json). Values are engineering
allocations, not protocol masks. Reference-AFE measurements do not calibrate them.

The [selected baseline](block-diagram.md#provisional-first-chip-baseline) uses
the high-impedance external clock input for initial qualification, with retained
ring-based autonomous synthesis. Terminated-input studies remain controls and
possible future configurations; they are not the default. The source/input/
distribution allocations and revised whole-mode currents are owned by
[power and timing allocations](power-partition.md#timing-and-signal-quality-allocations-for-the-selected-blocks).
Existing evidence below keeps its original assumptions until the model migrates.

## Complete path boundaries

| Configuration | Required path | What remains uncertain / likely first constraint |
| --- | --- | --- |
| Autonomous | Reference ingress → PLL detector/filter/control → oscillator → phase generation/division → buffers → mixer, converters or wired TX loads. Oscillator feedback closes the PLL. Wired RX retains its own CDR. | Oscillator noise and supply pushing, monotonic tuning/startup, loop transfer, then buffer-induced timing modulation. Loaded physical performance is unproven. |
| External LO/clock | External source and board → REF_IN protection/pad → biased receiver/buffer → phase generation/division → loaded distribution. Disable/bypass unused synthesis explicitly. Wired RX still retains CDR. | Receiver bandwidth, threshold noise and common-mode/swing compatibility, quadrature quality and distribution. A low-jitter source alone cannot establish success. |

REF_IN is one existing terminal: reference and direct LO are alternate uses, not
simultaneous independent inputs. A GHz mode needs a qualified analog receiver,
not the ordinary digital input buffer. External coupling/bias/termination is
allowed but must respect protection limits; input voltage limits remain to be
specified from the selected pad circuit. No new pins are assumed.

The selected 2.4–2.484 GHz input route requires same-frequency quadrature
generation, including amplitude/phase imbalance and tuning uncertainty.
Divide-by-two from approximately 4.8 GHz remains a historical comparison,
not another baseline input requirement; it has harder bandwidth and power
requirements. Ideal
frequency division lowers phase noise in radians but does not improve source
absolute time error; divider additive error remains. Neither architecture is
qualified by this arithmetic. Static I/Q error consumes a separate EVM allocation.

## RF LO requirement

Allocate 25% of total EVM power to residual LO phase. For small phase error,
`sigma_phi = EVM/2`, `sigma_t = sigma_phi/(2*pi*2.4 GHz)`.

| Total EVM scenario | Total equivalent RMS time | Each of four equal independent variance contributions |
| --- | --- | --- |
| −20 dB | 3.316 ps | 1.658 ps |
| −25 dB | 1.865 ps | 0.932 ps |
| −30 dB | 1.049 ps | 0.524 ps |
| −35 dB | 0.590 ps | 0.295 ps |

The four contributions are source, conditioning, phase generation and distribution.
For autonomous mode, source means the residual reference/VCO contribution after
loop transfer, and conditioning includes loop additive noise. They are accounting
slots, not four physically independent blocks by default. Integrate all sources
through their transfers over the same declared offset band. Correlated rail
modulation must be summed coherently, not combined by root-sum-square.

At −30 dB, three assumed 0.5 ps independent on-chip contributions leave only
0.591 ps for the source. At −35 dB those three already exceed the allowance,
even with a perfect source. These assumptions expose a failure boundary; they
are not measured receiver/divider/distribution errors.

### Frequency-dependent source limits

The report now integrates a first-order PLL sensitivity model over offsets
1 kHz–20 MHz, with no tracking or assigned 10/100 kHz tracking poles. PLL VCO
sensitivity is `f²/(f²+B²)` and reference sensitivity is `B²/(f²+B²)` in power.
Tracking residual is `f²/(f²+T²)`. These are idealized transfers without loop
peaking, stability or acquisition claims. All phase PSDs use the same one-sided
convention, `S_phi = 2*10^(L/10)` for SSB phase noise L.

For the −30 dB scenario, reserve three independent white additive blocks at
0.3 ps RMS each over that band, before tracking. Autonomous cases additionally
assume a flat −130 dBc/Hz reference spectrum **referred to the LO output after
frequency multiplication**. This is not a crystal specification or measured
reference noise. With no tracking, the remaining source limits are:

| Source path | Largest allowed L(100 kHz), pure 1/f² spectrum | Largest allowed flat floor |
| --- | --- | --- |
| External LO | −110.25 dBc/Hz | −113.26 dBc/Hz |
| Autonomous, 10 kHz PLL pole | −101.93 dBc/Hz | −113.26 dBc/Hz |
| Autonomous, 100 kHz PLL pole | −92.18 dBc/Hz | −113.23 dBc/Hz |
| Autonomous, 1 MHz PLL pole | −82.08 dBc/Hz | −112.93 dBc/Hz |

Each column independently spends the entire remaining source variance: **the two
limits cannot be used simultaneously**. For a combined spectrum, add the colored
and white integrated powers using the report's coefficients and compare with
`remaining_source_phase_variance`. These values are conditional requirements,
not plausible-device estimates. A wider loop suppresses colored VCO noise but
admits more reference noise; its stability, spurs and tuning response still need
closure. Direct external LO lacks that suppression unless a cleanup PLL is added,
which changes its architecture and power budget.

Integration was checked against the analytic arctangent integral for untracked
VCO noise, and doubling the grid changes colored-noise integrals by less than
0.000055%. Finite integration limits, assumed tracking and unknown actual spectra
are much larger uncertainties than numerical integration. Offset-dependent
spurs, I/Q imbalance, reciprocal mixing and aliasing still require separate
analysis before comparing these limits with real source specifications.

### Joint clock budget: random phase, quadrature and spurs

The executable joint scenarios now spend the same quarter of EVM power on all
three contributions, rather than letting each independently use the full allowance.
For a proper complex input and common complex-gain correction, quadrature image
error power is `(1+g²-2g*cos(phi))/(1+g²+2g*cos(phi))`. This does not assume an
FPGA image-correction algorithm. A 0.1 dB gain imbalance and 0.5° phase error
contribute 0.722% image EVM; 0.5 dB and 2° contribute 3.365%, already above the
1.581% clock allocation in the −30 dB total-EVM scenario. Improving oscillator
noise cannot repair that allocation failure.

As an explicitly synthetic comparison, assign a source with −100 dBc/Hz at
100 kHz following 1/f² plus a −145 dBc/Hz floor, retain the existing additive
and reference assumptions, use 0.1 dB/0.5° imbalance, and add a 100 kHz output
phase spur of 0.01 rad peak. With no tracking:

| Configuration | Joint clock error RMS | Fits 1.581% allocation? |
| --- | --- | --- |
| Autonomous, 10 kHz PLL pole | 2.140% | No |
| Autonomous, 100 kHz PLL pole | 1.396% | Yes, conditionally |
| Autonomous, 1 MHz PLL pole | 1.292% | Yes, conditionally |
| External source with the same synthetic spectrum | 4.651% | No |

This is not a recommendation to prefer an internal oscillator over a real
external source: the assigned external spectrum is deliberately identical to
the free-running source spectrum, and has no cleanup loop. An external module
may have much better close-in noise; that must be compared using its actual
spectrum and the same integration band. A cleanup PLL changes the architecture.
The report also sweeps −110/−90 dBc/Hz colored-noise anchors and tracking settings.
None is labeled a GF180 or external-product performance prediction.

The spur is defined at the LO output after any PLL, so only the tracking response
is applied to it. Its variance is `peak_phase²/2` before tracking. Actual supply
or reference spurs need their own injection-point transfer, and common correlated
errors cannot simply be added in variance. These calculations omit reciprocal
mixing, cross terms and RF filtering/alias effects; they establish conditional
budget boundaries, not packet EVM or compliance.

## Supply and buffer delay

For uncorrected sinusoidal frequency pushing, phase RMS is
`K_supply * V_ripple_peak / (sqrt(2)*f_ripple)`. At the −30 dB allocation and
1 MHz ripple, 10 and 65 MHz/V sensitivity permit approximately 2.24 and 0.344 mV
peak respectively if supply pushing consumes the entire phase allowance.
These are sensitivity anchors, not bounds on achievable GF180 rejection.
Other contributors require a smaller allocation. PLL and tracking transfer can
change this result; constant sensitivity extrapolation is not a measured spectrum.

The historical 100 MHz-ripple diagnostic produces about 11.07 ps peak at the
single-ended LO and 0.419 ps at the differential node. Its load was subsequently
found underbiased. It flags conversion/buffering sensitivity, but cannot qualify
a correctly biased chain or isolate intrinsic oscillator noise. A 100 MHz spur
also cannot be equated directly with in-band demodulated EVM without filtering
and alias analysis.

For coherent sinusoidal delay disturbances shared across four stages, the
−30 dB budget permits only 0.371 ps peak per equal contribution. Independent
random stage allocations instead use the table above. Static common delay is
not jitter; changing delay and differential I/Q skew are the relevant errors.

For external sine input, `sigma_t = sigma_v / slew`. An assigned 0.5 V peak
source behind 50 Ω and 0.79–1.07 pF shunt capacitance gives approximately
5.87–6.48 V/ns zero-crossing slew at 2.4 GHz in a one-pole model. A 0.5 ps
receiver allocation then permits 2.93–3.24 mV integrated threshold noise. At
3 pF it permits 1.52 mV. Package resonance, input bandwidth, offset, bias and
protection nonlinearity remain missing; these are requirements, not receiver
performance predictions.

### Protected input with bond loading and amplitude-to-timing conversion

The same report now includes `external_loaded_input`: a 50 Ω Thevenin source,
0.2 Ω series bond resistance and an assigned effective bond/return inductance
driving total pad/protection/receiver capacitance. Die termination is either
50 Ω or high impedance. The sweep covers 2.400/2.484 GHz and a 4.8 GHz
quadrature-source comparison. KVL, real-power conservation and the zero-L RC
limit are checked. These are circuit-network hypotheses, not extracted bounds.

Source voltage is 0.5 V peak open circuit. The example receiver has an assigned
20 mV threshold offset. The following values show why capacitance alone cannot
qualify the external-clock option:

| Frequency / loading | Input peak | RMS jitter from assigned 1 mV receiver noise | Peak-to-peak timing from ±10% source AM |
|---|---:|---:|---:|
| 2.4 GHz, 0.8 pF, 5 nH, high-Z | 0.817 V | 0.081 ps | 0.328 ps |
| Same load, 50 Ω termination | 0.210 V | 0.317 ps | 1.281 ps |
| 2.4 GHz, 3 pF, 2 nH, high-Z | 0.217 V | 0.306 ps | 1.238 ps |
| 2.4 GHz, 5 pF, 5 nH, 50 Ω | 0.078 V | 0.885 ps | 3.579 ps |
| 4.8 GHz, 5 pF, 5 nH, 50 Ω | 0.021 V | 4.237 ps | Crossing lost at low amplitude |

The low-capacitance high-Z example resonates above the assigned 0.6 V peak
ceiling. Termination damps it but lowers slew. That ceiling and the noise/offset
values are engineering assignments, not device absolute ratings or performance
measurements. RMS random jitter and peak-to-peak deterministic timing are kept
separate; they cannot each spend the entire same clock budget.

For a 0.5 ps peak-to-peak AM timing allocation, the 3 pF/2 nH high-Z example
requires threshold offset below about 8.1 mV; the 5 pF/5 nH terminated example
requires about 2.9 mV. Lower source AM or better bias/threshold centering can
relax that condition. The model also reports phase sensitivity to a 1% C change:
a *fixed* C error changes static phase, not jitter. Dynamic protection/input
capacitance would need its own voltage/supply-dependent model before using this
sensitivity as a timing disturbance.

**Design decision:** keep external timing, with input amplitude, bias/threshold,
termination and total loading treated as one qualification requirement. External
matching/damping and AC coupling/bias networks are permitted, but must be
modeled with their losses and common-mode behavior. Do not grant ideal matching
or a noiseless threshold trim. The RF port has analogous loading concerns, but
its matching/noise budget must use its actual input impedance rather than
inheriting this clock-input verdict. A 4.8 GHz divide-by-two option remains a
separate, harder input contract, not an automatic cure for I/Q phase quality.

### One allowance for the source and loaded input

`external_loaded_joint_budget` connects each loaded input to the same quarter
of −30 dB EVM power used above. It **replaces**, rather than adds to, the old
input-conditioning placeholder. Two remaining 0.3 ps RMS terms represent phase
generation and distribution; assigned I/Q mismatch remains 0.1 dB/0.5 degree.
Input noise is 1 mV RMS in the 1 kHz–20 MHz offset band. The source has a fixed
−145 dBc/Hz white floor plus an unknown inverse-square colored component.
No carrier tracking is credited.

Source AM is a ±10% sinusoid at 1 MHz. Exact threshold crossing times are
computed over its cycle, mean delay removed, and harmonic power inside the
same offset band retained. Receiver random timing variance uses the varying
slew over that cycle. This avoids treating a peak-to-peak number as random RMS
or combining differently defined integration bands.

| Assigned 2.4 GHz input | Remaining colored-source requirement at 100 kHz | System consequence |
|---|---|---|
| 0.8 pF, 5 nH, high-Z | Positive timing margin, but amplitude exceeds the assigned ceiling | Source quality alone cannot qualify this operating point; amplitude/matching must change |
| 0.8 pF, 5 nH, 50 Ω | At or below approximately −113.6 dBc/Hz | Conditional margin exists if the other assignments are achievable |
| 3 pF, 2 nH, high-Z | At or below approximately −113.4 dBc/Hz | Conditional margin exists; retain as a loading/bias design requirement |
| 5 pF, 5 nH, 50 Ω | No remaining allowance | Input noise/AM and downstream assignments already exceed the allocation |

These are bounds on the **colored component** of the assigned spectrum, not a
single-point phase-noise specification that guarantees a source will work.
For 4.8 GHz divided by two, source phase variance reduces by four while input
crossing time error remains unchanged. The additive divider/phase-generation
budget remains charged. Cases without reliable crossings cannot use a
phase-noise budget at all.

**Decision:** select an external source only together with an admissible input
network, bias and delivered-clock budget. If the input consumes the allowance,
evaluate amplitude/matching, threshold centering, reduced AM or lower receiver
noise before spending effort on a cleaner oscillator. Conversely, good input
slew does not excuse excessive voltage. Shared supply correlations, reciprocal
mixing, actual receiver bandwidth and circuit power remain unjoined; no row is
a GF180 or packet-performance qualification.

### Published external-source precedent

The [ADF4351 Rev. A datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/adf4351.pdf),
Tables 1 and footnote 6, reports typical 0.27 ps jitter at 2111.28 MHz with a
60 kHz loop bandwidth, 122.88 MHz reference and 30.72 MHz PFD. This supports
sub-picosecond external timing as a practical precedent, but the integration
band is not recovered here and the carrier differs from 2.4 GHz. The executable
report explicitly excludes this number from its same-band spectral calculation.

The device covers direct 2.4 GHz operation but its 4.4 GHz output ceiling excludes
it as a 4.8 GHz source for divide-by-two quadrature. Its programmable −4 to +5 dBm
matched output range also makes our assigned input amplitude worth evaluating:
a 0.5 V peak open-circuit Thevenin source behind 50 Ω corresponds to −2.04 dBm
available power. This is a matching calculation, not a claim about the actual
board's voltage at our protected pad. External filtering, bias, receiver bandwidth
and additive noise remain on the critical path. No GF180 phase-noise performance
is inferred from this other-process synthesizer.

## Converter clock ownership under direct external LO

The selected reference-derived converter candidate consumes 40 MHz REF_IN.
Direct GHz LO repurposes that same terminal, so it cannot keep that converter
clock silently. In autonomous mode a low-frequency reference can feed both
synthesis and converter division; in direct-LO mode this is an architectural gap.

A candidate uniform divide-by-64 path gives 37.500, 38.078125 and 38.8125 MS/s
for illustrative LO frequencies 2.400, 2.437 and 2.484 GHz. All are below the
40 MS/s converter ceiling. It avoids another reference pin and fractional
sampling edges, but requires variable-rate filtering, FPGA resampling where a
fixed output rate is required, and an explicit replacement clock owner. The
first divider stages still operate at GHz rates. It now has a **numeric rate/waveform candidate**, described below; the physical
divider, live clock-edge owner and sustained host service remain unimplemented.

At 2.437 GHz, exact 40 MS/s needs a noninteger ratio of 60.925. Alternating integer
intervals produces sampling modulation, not an ideal uniform clock. A fractional
clock synthesizer would add phase-noise, power and acquisition requirements.
An independent low-frequency input instead needs a justified terminal reassignment.
Thus external LO cannot yet be called a complete selected implementation even if
its RF phase budget passes. Keep these choices explicit rather than inventing an
unbudgeted second reference or sampling PLL.

### Direct-LO mitigation in the fast waveform model

[The robustness comparison](../verification/robustness_envelope.py) and its
[source-hashed report](../evidence/robustness-envelope.json) test uniform LO
division by 64/128/256/512 across 2.400, 2.437 and 2.484 GHz. These are numeric
configuration fields, not silicon protocol profiles or a new SPI ABI. Existing
40 MHz reference-derived rates remain the default. Mixing direct-LO settings
with the reference converter clock or autonomous pulse clock is rejected.

The proposed host clock is LO/16 (150–155.25 MHz), yielding 300–310.5 million
DDR words/s on D2H. H2D uses the existing FPGA-generated 156.25 MHz clock.
The sample/D2H-word ratio is exactly 8/sample_divider, allowing a future paced
producer to count observed host edges. This rate arithmetic uses existing pins;
it does not implement the new clock route, finite pacing, clock loss or rearm.
The four decimation tiers include rates down to 4.6875 MS/s. Analog cutoffs must
still fit the actual converter Nyquist interval; they are not blindly inherited.

A critical counterexample is the HE20 BPSK fixture at LO/64: retaining the old
sample-hold rate conversion yields 34–41% EVM in the historical optimistic
impairment case. An explicit 64-tap windowed-sinc FPGA resampler on TX and RX
reduces it to 4.51–4.62%, with zero fixture symbol errors at the three frequencies.
This is a diagnostic waveform, not a standard packet or higher-MCS qualification.
The moderate 8-ENOB case gives 4.08–4.22%; the adverse 6-ENOB/noise case still
fails the unchanged 10% diagnostic criterion at 11.45–11.76%. Several narrowband
fixtures and the original near-Nyquist 20 MS/s OFDM alternative retain failures.
A generic mitigation selects a faster existing divider when sample rate is below
three times the RX filter cutoff (a tested heuristic, not a universal rule).
This moves the 8-bit wideband alternative from LO/128 to LO/64 and yields
4.72–4.77% EVM in the moderate-precision case, with zero fixture symbol errors.
It adds converter/FPGA activity rather than new converter precision or pins;
the incremental converter power remains to be quantified. Resampling is optional
and is not assumed to improve every modulation.

The resampler is **external FPGA work**, with 32 input samples of TX delay and
32 converter samples of RX lookahead. At 20 MHz waveform / 38.078125 MS/s
converter rate, an unoptimized direct implementation needs about 4.87 billion
real MAC/s TX and 2.56 billion RX, plus coefficient and control work. At an
assumed 200 MHz MAC clock, that is at least 25 and 13 parallel real MAC units.
The 64-sample I/Q history at 18 bits/component is 2,304 FPGA bits per direction;
coefficient tables, accumulators and transport storage are additional. This is
not claimed to fit every generic FPGA or MCU. No on-chip resampler or memory
allocation is introduced. Coefficient quantization and FPGA timing are open.

The separate average-current comparison charges an explicit static clock load
plus aggregate CV²f switching. At 24 mA static and 3 pF effective switched load,
the PLL domain just fits 48 mA at 2.4 GHz but exceeds it at 2.437/2.484 GHz.
External LO does not eliminate on-chip clock power. Area for added clock routes
and trims remains unestimated; no whole-chip fit is asserted from this report.

The waveform comparison uses a fixed 3.25 V RF rail and assigned IID phase noise.
Its separate clock/host/power arithmetic is not a dynamically joined clock, PDN
and conversion-chain simulation. The next integration must preserve source
phase/sample-time correlations, independent remote timing, realistic noise
spectra, finite host service and acquisition/lifecycle. The milestone remains open.

### Joined spectral clock, blocker and supply comparison

The robustness report now also contains `spectral_rf_mitigations`, a joined
**receive-waveform** comparison. It uses the same converter/filter/receiver
pipeline, but injects finite phase-noise spectra at the mixer **before** RX
filtering. Both wanted signal and blocker see conjugate LO phase, so reciprocal
mixing is present. The stimulus DAC remains independently timed; this is not a
complete local TX+RX loop or a physical oscillator simulation.

`PhaseNoise` integrates a declared SSB 1/f²-plus-floor spectrum into 96 finite
logarithmic lines over 1 kHz–8 MHz. Random phases are fixed for each realization;
chunk queries do not redraw noise or normalize short packets to a target RMS.
Three spectral seeds are retained. The autonomous comparison uses first-order
VCO/reference transfer functions, with reference noise already referred to LO
output. Additive clock stages each assume 0.3 ps over this same band. Direct-LO
ADC timestamps inherit the common source/buffer phase with the signed crossing
error −phi/(2πfLO); branch-only mixer noise does not move ADC edges. Equal-
frequency disturbances combine coherently. Reference-derived ADC timing remains
separate in autonomous mode.

The test uses the HE20 BPSK fixture, 8 ENOB, a +20 dB blocker at 12 MHz offset,
2 V envelope-compression parameter and the existing FPGA resampling candidate.
Board filtering assumes 20 dB blocker attenuation and 2 dB wanted insertion
loss. Loss increases input-referred noise; restoring wanted amplitude assumes
available gain headroom, whose power and compression costs remain unclosed.
A 1 MHz supply disturbance is assigned a post-loop residual 10 MHz/V pushing
on the common clock path. The 1/10 mV ripple values are desired board/supply
conditions, not outputs of a host/package network simulation.

| Timing assumption | With board filter and 1 mV ripple: EVM across three seeds | With board filter and 10 mV ripple |
| --- | --- | --- |
| External source: −115 dBc/Hz at 100 kHz colored component, −145 floor | 7.02–7.14% | 10.54–10.63% |
| External source: −80 colored, −125 floor | 18.00–28.29% | 19.69–29.45% |
| Autonomous: −80 colored / −145 floor VCO, 10 kHz loop pole | 17.03–23.55% | 19.25–25.83% |
| Same VCO, 1 MHz loop pole | 5.77–5.88% | 10.19–10.25% |

Autonomous reference floor is −130 dBc/Hz output-referred. Sources are assigned
scenarios, not predictions or a fair ranking of real available hardware.
Without the board filter, all these tested cases fail the 10% diagnostic gate.
Both the clean-external and wider-loop autonomous cases pass only with the
combined mitigation in this sweep. Widening a real loop still needs stable
acquisition, charge-pump/reference-spur and power checks; an external source
still needs a qualified input, divider and quadrature path.

Mixer phase/compression/filter evolution uses four substeps per ADC period.
Repeating all sixteen mitigation combinations for one seed at eight substeps
changes EVM by at most 0.00165 absolute (0.165 percentage point); all acceptance
conclusions remain unchanged. This is a numerical refinement check, not full
convergence or proof against higher-order nonlinear aliasing. Independent checks
cover the analytic SSB integral, filtered arctangent integral, coherent phase
addition, chunk invariance and the actual mixer's Bessel-function blocker-to-DC
sideband. Remaining gaps include other waveforms, protocol masks, independent
remote clock drift, full TX, physical spectra/PLL response and a joined host/PDN
and power/area ledger. No whole-chip closure is inferred.

### Host activity, board decoupling and package resonance

`host_pdn_mitigations` in the same robustness report now replaces the assigned
1 MHz ripple with a complex two-node PDN solve. Host activity draws current at
the shared board node; the victim is behind a separate package/series branch.
The board capacitor remains outside that branch, with ESR and ESL. The die has
100 pF local capacitance. KCL and independent AC power conservation are checked;
no guessed isolation multiplier is used for this particular coupling path.

Assigned network: 2 ohm / 2 nH feed; 0.1 ohm / 2 nH package branch; board
capacitor ESR 0.05 ohm and ESL 1 nH. Optional external series damping increases
the package-plus-series resistance to 2 ohms. Capacitances are effective under
bias, not uncorrected component markings. These are realizable-network
hypotheses, not measured assembly parameters.

Host data-current amplitude comes from 10 outputs, 10 pF each, 3.3 V and 0.25
rising probability per DDR word, with 50% sinusoidal activity modulation at
1 MHz. The forwarded clock's average current remains in the DC budget. External
LO mode uses its candidate 304.625 Mword/s host; the autonomous comparison uses
the existing 250 Mword/s setting. The chip does not get quiet host pins for free.
For the external-LO case, the resulting host current tone is 12.57 mA peak:

| Board network | Predicted 1 MHz die ripple | Sampled peak transimpedance over 10 kHz–1 GHz |
| --- | --- | --- |
| No board capacitor | 25.13 mV | 11.27 ohms near 251 MHz |
| 100 nF board capacitor | 15.42 mV | 21.17 ohms near 309 MHz |
| 1 uF board capacitor | 1.97 mV | 21.13 ohms near 309 MHz |
| 1 uF plus series damping | 1.97 mV | 3.18 ohms near 302 MHz |

Thus board decoupling helps low-frequency activity modulation while potentially
increasing a high-frequency resonance. The lumped scan is a sensitivity screen;
it does not prove a GHz package model or a failure at a host harmonic. Actual
current spectra and the coupling/filter/alias path still decide signal impact.

With the earlier blocker filter and the same spectral realization, the 1 uF
network gives 7.23% EVM with the clean external LO and 5.86% with the wider-loop
autonomous candidate at assigned 10 MHz/V residual pushing. Increasing that
sensitivity to 65 MHz/V makes them fail the diagnostic 10% limit (12.47% and
10.25%). A 10 uF effective board capacitor with damping rescues those stress
cases to 7.74% and 6.19%, respectively. This is a useful alternative board
population, not evidence that any external capacitor cures all coupling.
For external conditioning, the stated pushing is an effective sensitivity at
1 MHz, not a claim that a buffer has frequency-independent VCO behavior.

Costs remain explicit: 100 pF requires 0.05 mm² ideal plate area at 2 fF/um²,
to be charged inside the existing timing allocation. Under the assigned 24 mA
victim DC load, damping adds 45.6 mV drop and about 1.15 mW total series-resistor
heat at 2 ohms. Including host/shared-feed drop gives about 3.144 V at the
external-mode victim rail. These DC operating points still need acceptable
clock tuning/noise/headroom; the waveform does not silently qualify them.
No extra terminals or on-chip bulk capacitors are introduced.

This joins one host-activity coupling path to clock phase and receive quality.
Common return, substrate, actual edge spectra, victim switching, regulator
behavior, startup, thermal effects and multi-domain loading remain unresolved.
The RF rail is still the earlier fixed-voltage scenario; its gain/reference
modulation is not included in this PLL-domain network. Extra gain needed to
compensate the RF board filter still requires an explicit headroom/current
implementation. Neither whole-chip fit nor higher-MCS support is established.

### Shared return can invalidate the capacitor rescue

The `shared_return_mitigations` comparison adds a third node for the die return.
The die capacitor connects between die supply and die return, while the board
capacitor remains referenced to the board return. Host current is withdrawn
from the board supply and returned through the specified shared-return branch.
Supply and return motion are solved simultaneously. Independent checks cover
KCL, passive AC power, the ideal-return reduction to the previous model, and
the low-frequency limit in which a large board capacitor cannot remove I*R
motion of the die return.

All cases retain 10 uF board capacitance, 2 ohm series damping, 100 pF die
capacitance and the earlier RF blocker filter. The stress sensitivity remains
65 MHz/V at the 1 MHz activity tone. Full host-return sharing is a conservative
topology scenario, not a measured fraction of this package's actual current.

| Return hypothesis | External-mode differential supply ripple | External-clean EVM | Wider-loop autonomous EVM |
| --- | --- | --- | --- |
| Ideal return (previous comparison) | 0.624 mV peak | 7.74% | 6.19% |
| Shared 0.1 ohm / 2 nH return | 1.871 mV peak | 12.20% | 9.75% |
| Shared 0.02 ohm / 0.5 nH return | 0.868 mV peak | 8.36% | 6.68% |

The autonomous case uses its own 250 Mword/s host-current calculation; its
ripple therefore differs from the external-mode column. Results use one
spectral seed and the unchanged 10% diagnostic limit. The 9.75% case has little
margin and is not a robust implementation claim. Ground motion alone in the
external case is 1.266 mV for the larger return impedance, versus 0.254 mV for
the smaller one. DC rail estimates also debit the shared-return voltage drop.

This turns return routing into a concrete mitigation requirement: the existing
separate host and PLL ground connections must provide sufficiently low coupling
through bond/assembly/board paths. No extra ground pin is assumed, and the
lower-impedance values are not claimed achieved. The earlier high-frequency
resonance scan covers supply-feed coupling only; return-path resonances still
need their own treatment.

Only differential-supply-induced clock phase is propagated into this waveform.
Ground motion can also change signal common mode, clock-input threshold and
converter reference levels; those paths and substrate coupling remain open.
For first-silicon diagnosis, a local differential rail observation alone cannot
identify feed versus return coupling. The diagnostic design needs either an
independently board-referenced return observation or controlled perturbations
that separate these transfer paths, with monitor loading/reference error
budgeted. Existing probe pins and local monitors are not presumed sufficient
without that observability check. Full diagnostic implementation remains pending.

### Explicit board loss, PGA gain and analog headroom

The `explicit_gain_mitigations` comparison removes the implicit restoration of
board-filter loss. Two dB of attenuation is applied before mixer compression;
receiver noise remains fixed at the input reference plane. Restoration, when
selected, consumes the existing PGA setting 1.2589. Filtering precedes the PGA,
so this does not invent RF gain before the blocker is removed. Tests verify
linear loss/gain cancellation independently of noise and compression.

Under the existing numerical converter normalization (±1 V for each I/Q
component), the model now applies an explicit signal headroom limit before
noise injection and ADC quantization. These are assigned voltage hypotheses,
not GF180 characterized swings. The comparison uses the low-return-impedance,
10 uF damped network, 65 MHz/V stress and earlier blocker filter:

| PGA choice / signal limit | External-clean EVM | Wider-loop autonomous EVM | Headroom result |
| --- | --- | --- | --- |
| Gain 1 / 0.8 V | 8.19% | 6.53% | No signal clipping |
| Restore 2 dB, gain 1.2589 / 0.8 V | 8.15% | 6.47% | Peaks 0.740 / 0.692 V |
| Restore 2 dB / 0.35 V | 12.66% | 11.41% | PGA clips; ADC clipping count remains zero |
| Existing gain 0.5 / 0.35 V | 8.62% | 6.98% | Peaks 0.294 / 0.275 V; no signal clipping |

Thus automatic gain restoration is not necessary for this diagnostic fixture:
its small noise benefit can cost substantial headroom. The already supported
0.5 setting preserves operation under a lower-swing hypothesis without a new
analog block. This is one seed/waveform and a 10% diagnostic criterion, not an
AGC policy qualified across signal levels, blockers, MCS or packet acquisition.
The older spectral/PDN tables remain implicit-restoration comparisons; this
explicit-loss comparison is the current headroom evidence.

The gain-restored sampled slew is about 24 MV/s, implying at least 24 uA to
charge each assumed 1 pF load. This is a lower bound from sampled trajectories,
not a total PGA bias estimate or proof of bandwidth. Noise excursions are added
after the signal headroom screen; noisy clipping, reference/common-mode motion,
continuous-time peaks, actual gain-setting current and physical area remain
open. Full power/area closure is not claimed.

For observability, the injected pre-ADC clipping failure has zero ADC-clipping
flags. First-silicon diagnosis therefore needs stage-selective stimulus/bypass
and gain/amplitude sweeps, not ADC flags alone. A gain sweep can expose a
headroom-sensitive failure, but without stage isolation it does not uniquely
identify which analog stage is responsible. Those diagnostic routes and their
loading still need a coherent implementation and model test.

### Diagnostic interventions and remaining ambiguity

`diagnostic_observability` now exercises an initial bench procedure using only
external FPGA observations: known-stimulus EVM, RMS of digitized samples and
acquisition status. Internal PGA clipping counts, injected fault labels and
hidden analog nodes are deliberately excluded from the measurements. It applies
four stopped configurations: baseline gain 1, gain 0.5, gain 1.5, and replacement
of the external LO source at the same carrier/rate. Source replacement is not
assumed to eliminate on-chip distribution or supply errors in real hardware.

The declared hypotheses cover nominal behavior, excess source phase noise,
limited PGA headroom, converter-equivalent noise and pre-PGA noise. Two
severity settings and two waveform/noise seeds define intervals for each
observed EVM and intervention-induced EVM change. A pair is called separated
only when at least one interval has more than 0.01 absolute EVM clearance.
That guard is a design assumption, not a confidence interval or instrument
accuracy specification. All observations must acquire; invalid EVM measurements
cause the diagnostic screen to reject its inference.

In this bounded sweep, the interventions separate the different signal-chain
failure classes even where baseline EVM intervals overlap. Higher gain exposes
headroom loss, lower gain exposes post-gain noise sensitivity, and a cleaner
source exposes the modeled source-phase contribution. The gain sweep can itself
cause clipping; those responses are retained. No additional chip pins or
on-chip capture storage are introduced: stimulus generation, capture storage
and analysis are external FPGA/lab work through existing interfaces.

A deliberate alias control assigns equivalent post-PGA sampler noise the same
observable transfer as converter-core noise. The procedure correctly leaves
those hypotheses indistinguishable. It can identify an aggregate post-gain
noise limitation here, not uniquely diagnose a transistor, sampler or reference.
Reference-specific stimuli, stage-selective bypass and a calibrated observation
path are still needed to resolve more detailed physical causes. Mixed faults,
unknown transfer functions, monitor error, wired diagnosis, actual gain/clock
switching lifecycle and usable first-silicon procedures remain unverified.
Thus this advances observability without marking that milestone requirement
complete.

## ADC and wired timing are different budgets

For an assigned equivalent-bit SNR of `6.02*N+1.76 dB`, reserving 25% of noise
power for aperture jitter gives `sigma_t = 0.5*10^(-SNR/20)/(2*pi*f_input)`.
At a 10 MHz analog input the limits are 101.6, 25.4 and 12.7 ps for 6, 8 and
9 bits. At 20 MHz they halve. Use actual signal spectrum for broadband inputs;
these sinusoidal allocations do not include settling, nonlinear conversion or
reference errors. RF carrier frequency does not belong in this baseband formula.

A separate illustrative wired eye allocation uses 0.30 UI total timing closure,
0.10 UI bounded deterministic jitter, and Gaussian relative timing tails totaling
1e-12. The remaining random RMS allowances are 11.22/9.35/8.66/5.61 ps at
1.25/1.5/1.62/2.5 Gb/s. These are not compliance masks or proven BER. ISI,
receiver aperture/setup/hold, pattern dependence and CDR transfer still matter.
RX error is data relative to recovered sampling time, including correlations;
clean external TX timing does not recover an independently timed incoming stream.

## Power and feasibility judgment

The existing PLL/reference domain ceiling is 48 mA, or 158.4 mW at 3.3 V.
For an illustrative 24 mA static allocation, remaining full-swing switched
capacitance `sum(alpha*C)` is at most 3.03 pF at 2.4 GHz, or 1.52 pF at 4.8 GHz.
With 12–36 mA static scenarios the 2.4 GHz range is 4.55–1.52 pF. Count internal
buffer/phase-generator loads, not only endpoint gates. Different supplies/swings
require their own power calculation. Charge clocks on RF/CORE rails exactly once
in the whole-chip ledger; moving a load to another rail is not a saving.
External-source power belongs in the board budget. Disabling an oscillator saves
only its actual power; receivers/dividers/distribution still consume power.

Neither architecture is ruled out by this envelope. External timing removes one
unvalidated source, but −30/−35 dB scenarios still require sub-picosecond additive
paths. Autonomous operation has the additional unresolved oscillator, loop and
startup requirements. The first quantitative failures above are scenario failures,
not physical process limits. Unknown bandwidth/noise can fail before the power
ceiling; passing CV²f arithmetic does not prove speed.

## Comparative conclusion and design consequences

| Requirement | Autonomous configuration | Direct external configuration |
| --- | --- | --- |
| RF LO source | Plausible research candidate: historical nominal PDK oscillation near 2.5 GHz, but no qualified spectrum, monotonic loaded tuning or cold startup. Source spectrum must fall inside the PLL-weighted envelope. | Published GHz synthesizers establish a practical external-source precedent. Actual selected source spectrum, band and operating point must fit the uncleaned input envelope. |
| Conditioning and distribution | Reference receiver, loop electronics, quadrature generation and local buffers consume the additive phase/power allowance. A nominal VCO frequency alone is insufficient. | GHz pad/receiver and buffers consume the allowance even with a perfect source. Input slew/noise and I/Q error can fail before source quality becomes limiting. |
| Converter clock | Retain reference-derived converter timing independently of carrier tuning; include its branch delay/noise. | Requires an explicit replacement for the repurposed 40 MHz REF_IN: candidate uniform LO division with variable sample rate, or a separately budgeted source/synthesizer. |
| Wired timing | TX synthesis may share infrastructure, but RX CDR tracks independent data; use the relative eye budget. | Direct external TX timing still requires input conditioning and does not bypass RX CDR. GHz RF LO mode is not automatically a wired clock recipe. |
| Supply disturbance | Work backward through actual PLL and oscillator/buffer injection paths. Historical 10/65 MHz/V anchors justify sensitivity analysis, not a guaranteed range. | Source rail quality moves off chip; on-chip receiver/phase/distribution supply sensitivity remains. It cannot inherit zero pushing from the external source. |
| Power | Oscillator and loop static current compete with switched distribution load under the existing rail ceilings. | Receiver replaces oscillator/loop burden only when they are actually disabled; divider and distribution loads remain. Include external source board power separately. |
| First demonstrated budget failure | In the stated synthetic example, a 10 kHz PLL pole admits too much residual oscillator noise; 100 kHz meets the joint allocation. Physical implementation could fail earlier on startup, speed or tuning. | The same uncleaned synthetic source fails. Better external noise is plausible, but source improvement cannot fix excessive I/Q imbalance or the missing converter clock owner. |

Across both modes, 0.5 dB/2° I/Q imbalance breaks the selected −30 dB scenario's
clock allocation regardless of source quality. Three independent 0.5 ps additive
stages break the stricter −35 dB scenario before source noise is added. At 24 mA
static current, exceeding 3.03 pF equivalent full-swing load at 2.4 GHz breaks the
assigned 48 mA domain ceiling. These are different failure boundaries, not one
universal ranking. No simulation here establishes that GF180 can meet the required
sub-picosecond additive errors. Nor does any cited result establish impossibility.

**Architecture guidance:** retain autonomous synthesis and explicit external-clock
bypass as operating options. Compare same-frequency quadrature first against the
quantified imbalance allowance; keep 2×-frequency division as an alternative with
its higher bandwidth/power burden. Direct external LO must declare converter-rate
ownership before being treated as an end-to-end configuration. Do not add an
unaccounted clock pin or ideal sample clock. External support is not a replacement
for the autonomous design goal.

This completes the conditional architectural comparison, not physical qualification
or whole-chip behavioral closure. Subsequent implementation work must qualify
actual source spectra, nonlinear pad/receiver behavior, quadrature topology,
loaded distribution, power and startup. The immediate mathematical integration
question is the direct-LO converter clock owner and its variable-rate filter/host
interaction, followed by applying the same clock envelope to the connected RF
chain. Those are implementation tasks beyond deriving this feasibility envelope.

## Verification and scope audit

The generated report covers both complete path boundaries above and derives
requirements for phase noise, deterministic supply/phase modulation, buffer
noise/delay, quadrature and power. RF carrier phase, ADC input-frequency aperture
error and wired relative CDR error have independent formulas and assumptions.
Analytic inverse checks, an independent I/Q coefficient expression, spectral
quadrature refinement and positive/negative joint-budget cases are executable.
The power ceiling is checked against the current contract. Source hashes pin the
script, contract and historical clock diagnostic. Published precedent and its
unmatched measurement conditions are recorded explicitly.

No actual stage power, RF noise mask or physical startup distribution is claimed.
Mathematical limits answer what is required; declared synthetic cases show what
breaks first under those assumptions. Unknown device behavior remains unknown
rather than being converted into a fabricated confidence interval.

## Generic wired electrical and sampling-phase envelope

`verification/wired_envelope.py`, included in the consolidated robustness report,
keeps driver and pad bandwidth fixed while sweeping target line rates. It bounds
all binary histories analytically through two real poles and a peak-normalized
postcursor tap. Pad capacitance (1–3 pF), driver time constant (50–200 ps), relative
RMS jitter (2–10 ps) and emphasis (0–0.5) are assigned hypotheses. The 400 mV
differential peak and 100 mV signed threshold are generic diagnostic values; USB
and TMDS require their own electrical models. The timing allowance is 0.05 UI
plus seven RMS jitter units, sampled at 21 points, without a BER claim.

The report retains the fixed 0.5 UI result and separately selects among 0.5, 0.65
and 0.8 UI centers whose whole uncertainty window remains inside the current bit.
This prevents attributing ordinary channel delay to an irrecoverably closed eye.
At 2.5 Gb/s, 2 pF, 100 ps, 5 ps RMS and zero emphasis, phase selection changes the
minimum signed sample from −60 mV to +194 mV. At 200 ps it reaches only +31 mV;
1 pF/50 ps instead provides +228 mV even at the fixed center. These distinguish
phase-adjustment, lower loading and faster-driver mitigation paths. Phase control
needs receiver acquisition/hold proof; lower loading needs pad/package evidence;
faster switching needs transistor speed, current and headroom evidence. None is
free. Peak-normalized emphasis reduces long-run swing by (1−p)/(1+p).

A stateful channel witness independently checks the worst-history convolution.
The phase search is bounded and discrete: failure is not proof that all receiver
phases or equalizers fail, and passing is not protocol qualification. CDR, channel
reflections, actual noise, disabled-circuit loading and joint costs remain open.

The same report now includes `causal_wired_receiver`: the existing four-voltage-
observation receiver sees a two-pole voltage fixture, without transmitted labels
in its control loop. The baseline twelve cases combine three channels, ±0.35 UI initial phase
and ±100 ppm offset. Three additional impairment settings bring the total to 48. A constant integer scoreboard alignment is trained on bits
600–1199 and frozen for the separate 1200-bit evaluation interval, so the
scoreboard cannot hide slips by changing alignment. At 1 pF/50 ps and 2 pF/100 ps
all cases retain timing qualification and decode the held-out bits correctly.
At 2 pF/200 ps the bits still decode correctly, but qualification occupies only
9–20% of that interval and is false at the end. Receiver feedback is therefore
demonstrated conditionally for the faster cases, not for the complete envelope.

The baseline fixture has no injected aperture jitter or voltage noise. All cases
retain the detector's assigned 5 ps IID timestamp error, distinct from aperture
jitter. Additional cases move all four analog observation times by a sinusoidal
aperture displacement; controller timestamps retain their nominal labels. A
173 MHz sinusoidal voltage disturbance and DC offset enter before both crossing
and bit decisions. These deterministic spectra are hypotheses, not measured
noise or random-tail qualification. Actual data-sample times remain monotonic.

| Assigned aperture / voltage disturbance | 1 pF / 50 ps | 2 pF / 100 ps | 2 pF / 200 ps |
| --- | --- | --- | --- |
| 2 ps RMS at 25 MHz; 10 mV RMS tone + 20 mV offset | Continuous qualification; ≥346 mV observed margin | Continuous qualification; ≥265 mV | No held-out qualification; ≥170 mV |
| 10 ps RMS at 25 MHz; same voltage disturbance | Continuous qualification; ≥344 mV | 89–100% qualification; ≥261 mV | No held-out qualification; ≥166 mV |
| 50 ps RMS at 100 MHz; 20 mV RMS tone + 40 mV offset | No held-out qualification; ≥264 mV | No held-out qualification; ≥147 mV | No held-out qualification; about 50 mV |

All these short held-out sequences decode without errors. This does **not**
justify bypassing the qualification gate: it demonstrates that the gate and
short-sequence voltage margin answer different questions. The 100 ps channel
has two conditional mitigation paths: improve aperture quality to the assigned
2 ps case, or reduce loading and driver time constant to the 1 pF/50 ps case.
Neither a physical clock meeting that spectrum nor the faster driver's power
cost has been demonstrated. The 200 ps path remains unqualified. No lock
threshold was relaxed to obtain these outcomes.

Decisions use zero threshold; signed voltage is recorded separately against the
frozen scoreboard alignment and the 100 mV diagnostic allowance. That is observed
margin, not a bound over every history or jitter phase. Short random NRZ sequences
do not establish BER, protocol acquisition, SSC tolerance or long-run holdover.
The source fixture's boundary states and sample records are mathematical test
storage, not chip storage. Physical voltage-noise spectra and stochastic timing
tails remain open, as does integration with actual receiver power and area.

## Loaded RF transmit spectrum, interpolation and headroom

The consolidated report separates host interpolation from analog output errors.
At 20 MHz waveform sampling and a 40 MHz DAC, the historical repeated-sample
fixture introduces substantial images. The following ratios sum both signed
offset bands and divide by power inside ±10 MHz, using a Hann window:

| Host interpolation, assigned output stage | 10–30 MHz / central power | 30–50 MHz / central power |
| --- | --- | --- |
| Repeated samples, nonlinear/IQ errors retained | 7.54–7.78% | 0.287–0.296% |
| Repeated samples, ideal output stage | 7.54–7.77% | 0.288–0.296% |
| Existing 64-tap FIR, nonlinear/IQ errors retained | 0.00425–0.00695% | 0.357–0.367% |
| Existing 64-tap FIR, ideal output stage | 0.00413–0.00711% | 0.357–0.367% |

Two independent payload seeds use the same quantized DAC, one-pole analog
reconstruction, gain and load. Removing output-stage IQ imbalance, feedthrough
and cubic compression barely changes the repeated-sample result. FIR
interpolation removes most of that adjacent-band image without a new analog
filter. The remaining DAC-rate image is distinct and still needs reconstruction
filtering. Ratios are diagnostic, not emission-mask measurements; no regulatory
or protocol limit, measurement bandwidth or complete RF harmonic spectrum is
applied. The earlier 7.5–7.8% result must not be described as inherent analog
inadequacy: its dominant cause was the host interpolation fixture.

The joined `tx_spectral` comparison now uses the FIR path. Its centered analysis
implementation requires 32 input samples of lookahead, or 1.6 us at 20 MHz,
realized as delay in a streaming FPGA implementation. The existing direct-form
cost model charges 2,304 history bits and 5.12 billion real MAC/s for TX at 40 MHz,
or 26 parallel MAC units at an assumed 200 MHz. This is an unoptimized workload
allocation, not synthesized FPGA resource/timing proof; coefficient precision,
pipelines and transport scheduling remain open. No additional chip pins,
converter rate or on-chip sample memory is assumed.

At output voltage scale 4.5, the FIR cases deliver 1.066–1.068 mW and fit the
assigned 3.144 V minimum rail, 0.3 V per-leg headroom and 28 mA current limits.
The differential output has 40 ohms source resistance and a 50 ohm load. Scale
5.02 is retained as a higher-drive stress comparison. Normalized nonlinearity
is held fixed as gain varies; physical gain/bias dependence is unknown. These
two crests do not bound all OFDM payloads. Driver bias is included in the
assigned 37 mA RF bias; full current, area and the external network remain open.

Assigned independent LO spectra and 1 MHz supply modulation are applied to the
actual loaded DAC/filter/driver output. Constant-complex-fit incremental EVM
compares against that same distorted baseline, not an ideal packet. The fit uses
the entire record, so it is not implemented causal tracking. Supply ripple uses
65 MHz/V residual pushing; it is a stress input, not a joined TX-load/PDN result.
Clean external timing cannot remove this local modulation. Spectra cover only
1 kHz–8 MHz offsets: far-offset phase noise, DAC jitter, supply AM response,
higher modulation orders and standard packet EVM remain unresolved. The report
retains both phase-modulation and electrical failures explicitly.

### Existing TX cutoff tradeoff

With the FIR host interpolation retained, the same two payloads now sweep the
existing first-order TX cutoff at fixed output gain. All three settings are
within the generic configuration model; no extra filter order, sample rate,
pin or analog block is introduced.

| TX cutoff | DAC-image / central-band power, 30–50 MHz | Average load power | Analog pole gain at 9 MHz relative to DC |
| --- | --- | --- | --- |
| 5 MHz | 0.132–0.136% | 0.765–0.768 mW | −6.27 dB |
| 10 MHz | 0.357–0.367% | 1.066–1.068 mW | −2.58 dB |
| 15 MHz | 0.659–0.677% | 1.189–1.190 mW | −1.34 dB |

The narrower cutoff reduces this image ratio about 4.3 dB but loses roughly
28% of average signal power and adds 3.7 dB analog attenuation at 9 MHz. All
tested fixed-gain cases retain the assigned electrical bounds. The report also
records the linear gain/current/swing requirement to restore each case to its
10 MHz average power; this needs about 1.18× voltage gain for the 5 MHz case.
That scalar gain cannot undo frequency-dependent droop. No receiver EVM or
transmitter pre-emphasis benefit is inferred from matching average power.

This establishes a bounded configuration tradeoff, not a complete wideband
mitigation. A new analog filter should not be justified solely by the earlier
repeated-sample artifact, but neither should first-order cutoff tuning be called
emissions closure. Actual programmable-pole noise, settling, gain, current and
component tolerances remain unmodeled. Higher-order reconstruction or external
filtering remain options to compare only with their signal-quality and resource
costs; no such circuit is selected by this sweep.

## Coverage and weak-recipe controls

`capability_coverage` lists every contract protocol target with the consolidated
report's quantitative evidence and its missing closure obligations. Its RF
summary preserves individual recipes and impairment cases; carrier entries with
a diagnostic pass mean at least one tested configuration passes there, not that
every setting or intermediate frequency works. The report deliberately sets no
per-capability completion flag true. Other repository diagnostics keep their
original scopes and are not declared absent by this audit.

`weak_rf_recipe_controls` removes assigned frontend white noise, IID LO phase
noise and aperture jitter, retaining ideal 12-bit quantization, existing
preserve-tier filters, FPGA interpolation and prefix acquisition. BLE 2M EVM is
10.20%, 9.51% and 8.82% at the three tested LO settings; wideband LoRa is 9.72%,
10.02% and 9.97%. Narrower LoRa gives 6.81–7.11%. All these short fixtures decode
without errors. Residual distortion cannot be attributed entirely to transistor
noise or fixed by assuming better ENOB. This is an ablation control, not a
mathematical lower bound or a standard-specific acceptance test. Filter,
interpolation and recovery interactions need isolation before physical demands
are increased.

### Weak-recipe configuration attribution

The same moderate impairment assumptions now compare four generic choices: retain
settings, double RX cutoff, select the existing first-order RX reduction, or double
converter rate while retaining analog cutoffs. Existing configuration validation
is applied, with three LO settings per recipe. These are external configuration
recipes, not new on-chip protocol selectors.

| Fixture | Baseline diagnostic EVM | Double RX cutoff | Double converter rate |
| --- | --- | --- | --- |
| BLE 2M | 10.2–10.8% | 5.8–6.3% | 13.2–14.0% |
| Narrow LoRa | 9.2–24.3% | 16.1–36.1% | 14.4–48.5% |
| Wider LoRa | 12.2–16.4% | 6.7–16.6% | 16.9–20.2% |

BLE's wider fifth-order filter changes the cutoff from 2 to 4 MHz at unchanged
converter rate. Its ideal attenuation at 4 MHz falls from about 30.1 to 3.0 dB.
An explicit equal-power 4 MHz-offset blocker at the middle LO setting raises
the widened-filter EVM to 82.7%, with eight symbol errors and failed acquisition;
the original filter gives 11.3% and zero symbol errors with acquisition. The
first-order alternative gives about 9.1% without the blocker but fails acquisition
with it. This is a useful configurable clean-channel mode, not a universal BLE
mitigation or protocol interference test. No compression or spectral reciprocal
mixing is included in this particular comparison.

Doubling sample rate is not a demonstrated remedy here. It increases converter
and host work without consistent quality improvement; those actual power costs
remain unpriced. LoRa's large sensitivity to rate and modest random impairments,
despite much smaller idealized-control errors, keeps prefix timing/carrier
recovery high on the investigation list. This evidence does not yet isolate the
responsible estimator, and no receiver threshold is relaxed or payload-fitted
correction introduced. Next work should inspect measured prefix estimates and
held-out payload residuals, rather than assign a faster converter or wider filter
as a general solution.

### LoRa carrier-estimation attribution

The diagnostic carrier estimator now accepts a bounded known-prefix length while
retaining its 512-sample default. The longer-prefix study keeps analog settings,
converter rates and moderate impairment assumptions fixed. It compares 512 and
2,048 training samples, zero and 5 kHz injected carrier offsets, three LO settings
and two independent payload/noise seeds. Injected frequency is used only by the
scoreboard; the estimator uses settled known repeats. A payload-mutation test
checks that its estimate does not depend on unknown payload labels.

| Recipe | Prefix samples | Diagnostic EVM range | Maximum absolute frequency-estimation error |
| --- | --- | --- | --- |
| Narrow LoRa | 512 | 7.3–33.8% | 17.8 Hz |
| Narrow LoRa | 2,048 | 7.5–8.5% | 1.65 Hz |
| Wider LoRa | 512 | 10.5–23.8% | 40.1 Hz |
| Wider LoRa | 2,048 | 10.2–12.3% | 3.69 Hz |

An earlier zero-offset middle-LO narrowband control disabled carrier correction
and reduced EVM from 24.3% to 7.2%; the ordinary estimator had introduced an
11.7 Hz correction. That is causal attribution with known injected truth, not a
receiver bypass recommendation. The longer-prefix cases retain real estimation
and include nonzero offsets. Narrowband operation now has a conditional FPGA-side
mitigation; wider-band distortion remains after frequency estimation improves.
No analog noise or speed requirement is relaxed from this result.

The additional 1,536 training samples cost approximately 317–328 us in the narrow
recipe and 158–164 us in the wider recipe. A direct buffered implementation at
18 bits per I/Q component grows from 18,432 to 73,728 bits of external FPGA
training storage. Streaming statistics could use less storage, but that
implementation is unverified. No on-chip storage is added. This synthetic prefix
is not a standard LoRa preamble: the result establishes estimator sensitivity
and a diagnostic mitigation, not protocol interoperability or permission to
change an over-the-air packet. A practical modem must obtain equivalent timing
and frequency information from its actual allowed preamble/tracking structure.

### Joined wider-band LoRa configuration

The recovery study now combines the longer diagnostic prefix with the existing
RX cutoff adjustment, retaining the original settings as controls. For the
812.5 kHz chirp fixture, cutoff changes from 0.8 to 1.6 MHz while the converter
rate stays unchanged. The comparison also scales frontend noise RMS by sqrt(2):
a same-order filter integrating a fixed white input-noise density doubles noise
variance when its bandwidth doubles. This is an explicit sensitivity assumption,
not measured GF180 noise; ADC and phase-noise assumptions stay fixed. Diagnostic
prefix shaping follows the selected cutoff, so this is a joined configuration
comparison rather than an isolated analog-pole experiment.

Across both seeds, three LO settings and zero/5 kHz offsets, the 2,048-sample
prefix plus wider filter gives 6.3–7.5% diagnostic EVM with zero fixture symbol
errors. The original cutoff with the same long prefix remains at 10.2–12.3%.
Thus a conditional clean-channel mode exists without faster converters or new
analog blocks, even when the assumed extra noise bandwidth is charged. Existing
training airtime/FPGA-buffer costs still apply; physical filter tuning current,
noise, tolerance and settling remain unqualified.

Selectivity remains a separate limit. At 1.6 MHz offset, the ideal fifth-order
response changes from 30.1 to 3.0 dB attenuation. An equal-power blocker at that
offset causes failed carrier/timing acquisition and five symbol errors in the
wider-filter test; the original filter retains acquisition and zero symbol errors
at 11.2% diagnostic EVM. Neither is a standard LoRa blocker specification. Keep
both settings available; the wide setting is not a universal replacement.
Protocol-native preamble/tracking, realistic blocker/compression/phase spectra
and joint power/area still need closure.

### RF bench procedure and unresolved fault ambiguity

`rf_bench_diagnostics` derives paired observations from the recovery study, using
only known-stimulus EVM/symbol errors, frequency estimates and acquisition status.
Injected frequency error and internal ADC-clipping counters are excluded. A
regression changes those hidden quantities and verifies identical diagnostic
output. Test conditions identify pairs; no injected fault label determines a
diagnosis. This procedure needs an independent known RF stimulus and controlled
blocker, existing RF input/configuration access, and host-returned I/Q samples.
All capture/estimator storage belongs to the external FPGA or lab host.

| Intervention | Observable response in the bounded study | Interpretation limit |
| --- | --- | --- |
| Increase known training | Narrowband EVM change −25.9 to +0.6 percentage points; not every realization improves | Changes frequency, delay and gain estimation together; cannot alone identify oscillator noise |
| Widen filter after long training | Wider-band EVM falls 3.6–5.3 percentage points, with increased noise bandwidth charged | Also changes group delay and diagnostic prefix shaping; not proof of a defective filter component |
| Add equal-power blocker | Wide-filter case loses acquisition; original-filter case retains acquisition | Cannot isolate selectivity, compression or reciprocal mixing in physical silicon without further sweeps |

Start by confirming clean-stimulus acquisition and repeatability, then compare
training duration at fixed analog settings. Compare filter settings only after
recovery is stable. Finally sweep blocker frequency/power and gain while recording
acquisition and known-stimulus residuals. The current paired examples support
those interventions, not the full sweeps or a unique fault classifier. Avoid
shared-LO-only loopback as the sole clock-quality test: it can hide common phase
errors. Internal simulator state must not be represented as available telemetry.

Known-stimulus diagnostics are bench capabilities, not autonomous diagnosis of
unknown field traffic. Physical capture throughput, firmware/configuration paths,
mixed faults and stage isolation remain unverified. No new on-chip monitor or
pin is claimed by this procedure, and this does not close first-silicon
observability for the whole transceiver.


### Explicit external-source and input intersection

`external_loaded_joint_budget` now evaluates the joined model's assigned
−115 dBc/Hz at 100 kHz source directly against the loaded input budget, rather
than only reporting an inverse source requirement. It retains the −145 dBc/Hz
floor and the existing 1 kHz–20 MHz integration, input AM/threshold noise,
phase-generation/distribution allowances and I/Q mismatch. This is a separate
budget calculation: the packet model still uses a delivered-source hypothesis
with 1 kHz–8 MHz source tones; the two are not identical waveform environments.

At 2.4 GHz with 3 pF receiver/pad C and 2 nH bond L:

| Input termination | Receiver random timing | AM-induced timing | Total evaluated error power | Diagnostic allowance | Verdict |
|---|---:|---:|---:|---:|---|
| High impedance | 0.309 ps RMS | 0.437 ps RMS | 0.0002216 | 0.0002500 | Fits assigned budget |
| 50 Ω | 0.396 ps RMS | 0.561 ps RMS | 0.0002638 | 0.0002500 | Exceeds assigned budget |

The latter requires source L(100 kHz) at most −116.07 dBc/Hz with the other
hypotheses unchanged, versus −113.39 dBc/Hz for the high-impedance example.
Termination can control voltage peaking, but reduces slew and can tighten noise
requirements. Do not choose high impedance solely from this row: other loads
in the grid exceed the assumed input-amplitude ceiling. Across the finite grid,
11/24 cases at 2.4 GHz, 12/24 at 2.484 GHz and 15/24 at 4.8 GHz fit; the
4.8 GHz cases assume ideal divide-by-two and two cases lose crossings.
These counts describe sampled hypotheses, not yield or coverage of physical
corners. Required input slew/noise, power, division and amplitude tolerance
remain unimplemented.

**Decision:** preserve an input matching/termination choice and qualify it
jointly with source amplitude, threshold offset and noise. A delivered-clock
phase-noise assumption does not qualify the external source path. Supply-driven
host tones, reciprocal mixing and actual packet/serial acceptance remain separate
obligations; the internal quarter-of-−30 dB-EVM allowance is not a protocol mask.


### Loaded input propagated through receiver waveforms

`oscillator_noise.loaded_clock_input_phase()` now translates the assigned
RLC input, 20 mV threshold offset and ±10% / 1 MHz AM into a shared finite
phase realization. It adds stationary-equivalent receiver noise from 1 mV RMS
and two 0.3 ps downstream allowances. The waveform environment uses 1 kHz–8 MHz
for source and additive random noise, while retaining twenty AM harmonics.
The separate inverse budget above uses 1 kHz–20 MHz; do not compare their
integrated totals as though the bands were identical.

`operating_environment(external_input=...)` places source noise at the external
plane and adds the input phase to the same delivered realization already used
for RF mixing, converter crossings and wired sampling. Default environments
retain the prior ideal-delivered-source comparison. The paired whole-chip
screen uses 3 pF / 2 nH input hypotheses and the 500 pF / 0.5 Ω / 200 pH local
supply candidate with adverse 7 pC H2D activity:

| Clock path | Synthetic RF diagnostic EVM | Wired short-case errors |
|---|---:|---:|
| Ideal delivered source | 7.26% | 0 |
| Loaded high-impedance input | 7.40% | 0 |
| Loaded 50 Ω input | 7.47% | 0 |

The AM waveform is independently checked against the direct threshold-crossing
equation; integrated additive variance and loading/noise ordering are checked.
The same underlying path parameters apply at each mode's carrier frequency.
These comparisons establish causal model integration, not protocol acceptance.
Source PM is still passed with unity gain through the input network; sideband
dispersion, cyclostationary noise, correlated input/supply noise, circuit
bandwidth/current and startup remain unqualified. Static propagation delay is
omitted. The paired loaded-input packet comparison below now exercises reception and
conditional replies; it retains the resulting failures. Protocol timing and RF
TX qualification remain open.


### Blocking imposes a stronger spectral clock requirement

The `loaded_clock_packet_exchange` report now holds the 500 pF nonideal supply
candidate, 6 dB chip-input NF, 500 kHz filter, −90 dBm wanted and −40 dBm
2 MHz-offset blocker fixed while changing only the clock-input path. The same
six seeds are used in each case; source phase continues through any loaded reply.

| Input path | Acquired / accepted requests | Correctly decoded replies |
|---|---:|---:|
| Ideal delivered clock | 6/6 acquired, 5/6 accepted | 5 |
| Loaded high impedance | 0/6 acquired | 0 |
| Loaded 50 Ω | 0/6 acquired | 0 |

Run `verification/robustness_envelope.py --loaded-clock-exchange` for this
comparison. Failure prevents replies from being armed; absence of a transmitted
reply is not a TX decoding failure. The ideal-path uncorrected RF start marker
is 151.30–151.62 µs after source packet end, so even those replies do not close
the calibrated air-timing requirement.

A separate attribution control on the same six high-impedance cases removes
only the input/distribution random lines while retaining input AM, source noise,
host supply phase and all RF settings: 5/6 acquire and 5/6 are accepted.
Removing only the twenty input-AM harmonics while retaining the random lines
leaves 0/6 acquired. These nonphysical removals identify the added random-noise
hypothesis as the main limiting contribution in this experiment; neither is a
design option. They were evaluated from the saved environment's phase tones
using the same packet observer.

The result is consistent with reciprocal mixing from the assigned broad
additive clock noise, an effect clean-signal EVM does not constrain strongly.
At 2.426 GHz the input/distribution random time variances imply white-equivalent
SSB floors of **−113.98 dBc/Hz high impedance** and **−113.11 dBc/Hz terminated**
over 1 kHz–8 MHz. The finite-tone waveform approximates these continuous spectra;
it is not measured silicon noise. The external source's low floor does not
remove noise added by the on-chip input/distribution stages.

As an independent approximate necessary budget, the blocker reaches the chip
at −42 dBm after 2 dB loss. The 6 dB-NF input-referred noise density at 300.15 K
is −167.83 dBm/Hz. Keeping single-blocker reciprocal-mixing density below that
level requires total LO SSB noise near the relevant blocker offsets no higher
than **−125.83 dBc/Hz**. This compares one blocker sideband with one input noise
reference; it is not a standard mask or a complete in-band convolution. A flat
floor at that ceiling across 1 kHz–8 MHz corresponds to only **0.134 ps RMS**
at 2.426 GHz, versus the larger input/distribution assumptions used here. Other
source noise and spurs consume some of the same allowance. A frequency-shaped
noise spectrum must be integrated with the actual blocker and receive filter;
its permissible total RMS can differ greatly from this flat example.

**Decision:** qualify delivered LO noise at blocker offsets, in addition to
integrated timing/EVM. The external-clock route remains an option, but its
assigned 1 mV in-band receiver noise and 0.3 ps per downstream stage do not
support this weak-wanted/strong-blocker example when modeled as white-equivalent
noise. These are stress hypotheses, not evidence that GF180 cannot do better.
Do not respond merely by selecting a cleaner external oscillator: the added
receiver/distribution noise must be reduced or shaped, or pre-mixer blocker
power reduced. Additional baseband rejection cannot undo reciprocal mixing
already translated into the wanted band. None of those mitigations is free of
current, headroom, frequency coverage or control costs.


### Noise allocation with a physical implementation still required

The loaded-input helper now exposes receiver voltage noise and each downstream
stage's time noise as numeric hypotheses. Defaults remain 1 mV and 0.3 ps;
changing them does not change input amplitude, threshold offset, AM, supply
noise or RF settings. An exploratory quieter allocation is 250 µV RMS at the
receiver and 50 fs RMS for each of the two downstream stages, integrated over
1 kHz–8 MHz. Independent checks verify quadratic variance scaling while the
AM waveform stays unchanged.

| Input | White-equivalent additive floor | Accepted weak blocked requests | Decoded replies |
|---|---:|---:|---:|
| High impedance, original noise | −113.98 dBc/Hz | 0/6 | 0 |
| 50 Ω, original noise | −113.11 dBc/Hz | 0/6 | 0 |
| High impedance, quieter allocation | −127.97 dBc/Hz | 3/6 | 3 |
| 50 Ω, quieter allocation | −126.69 dBc/Hz | 3/6 | 3 |

Use the same −90/−40 dBm, 2 MHz blocker and 6 dB NF / 500 kHz settings as
above. These added-noise allocations are requirements to investigate, not GF180
measurements or completed circuit designs. In particular, the 50 fs number is
**in-band additive jitter**, not total broadband edge jitter or static phase skew.
No current or area saving is inferred from lowering the parameter.

The approximate −125.83 dBc/Hz boundary only keeps reciprocal-mixing noise
below the thermal-noise contribution, rather than making it negligible. At the
quieter high-impedance and terminated floors, simple flat-density addition
still increases that combined noise by roughly 2.1 and 2.6 dB respectively.
This explains why crossing the rough equal-noise ceiling need not recover all
packets. An illustrative tenfold margin below thermal density would require
about −135.83 dBc/Hz and limit this contribution to about 0.41 dB noise rise;
flat additive noise at that level corresponds to approximately 42 fs RMS over
1 kHz–8 MHz. Source noise and discrete spurs must share the same budget.

The report also retains a moderate-signal control: −80 dBm wanted, −40 dBm
blocker, baseline 10 dB NF and 700 kHz cutoff, using the original loaded-input
noise assumptions. High impedance acquires 5/6 and accepts 3/6; 50 Ω acquires
5/6 and accepts 2/6. Thus the loaded-input noise hypothesis affects the earlier
useful-signal point as well as the −90 dBm stress case. These controls exercise
reception only and do not qualify a reply or choose a reduced product scope.

An independent continuous-spectrum check now validates the scale of the mixing
problem. For real phase noise with SSB density `L(f)`, the first-order unwanted
power fraction from a tone at offset Δ is
`integral L(f) * (|H(Δ-f)|² + |H(Δ+f)|²) df` over positive offsets. Each finite
phase tone of peak amplitude a contributes `a²/4` to each translated sideband.
This uses consistent one-sided SSB / two-sided phase conventions.

For the original high-impedance additive-noise spectrum and 500 kHz fifth-order
filter, numerical quadrature gives a fraction 4.0704e-6, or **−95.90 dBm** from
the −42 dBm chip-input blocker. The wanted chip-input power is −92 dBm before
receive-filter distortion, only 3.90 dB above that noise contribution. The
32-tone approximation gives 4.5095e-6, 10.79% higher (+0.45 dB). Its error is
+15.92% at 475 kHz and −7.49% at 700 kHz. Thus sparse spectral sampling cannot
explain away the large failure, but can affect marginal packet outcomes.

A 512-bin quadrature matches the continuous integral within 0.002% at all three
cutoffs; the independent flat-spectrum Butterworth noise-bandwidth check agrees
within 1e-6 relative. These are expected-power checks, not proof of finite-burst
statistics or a valid physical spectrum. The executable checks reside in
`LoadedClockInputTests.test_reciprocal_mixing_quadrature_and_finite_tone_resolution`.
Keep the existing fast waveform grid for exploration, but require spectral
resolution and independent noise-realization checks before treating near-boundary
packet counts as a verified operating envelope. No default has been tuned to
make those counts pass.

**Decision:** keep the quieter allocation as an explicit, still-failing candidate.
Pursue a delivered spectral mask with margin and demonstrate where each stage's
noise lies in frequency; do not treat a chosen RMS value as proof of a flat
physical spectrum. Lower input/distribution noise, frequency shaping and reduced
pre-mixer blocker power are distinct mitigation options, each requiring a real
circuit/board path and cost. The current experiment establishes none of those
physical implementations and does not change the normative supported scope.


### Is the tighter additive-noise requirement physically absurd?

A conditional thermal/slew calculation does **not** establish a fundamental
impossibility, but also does not qualify GF180. The illustrative −135.83 dBc/Hz
flat allocation corresponds to 42.43 fs aggregate RMS over 1 kHz–8 MHz at
2.426 GHz. Dividing its variance equally between input conditioning and two
following stages gives 24.50 fs per stage. For a local threshold crossing,
`σv = slew * σt`; white-equivalent voltage density is `en = σv/sqrt(B)`.

| Local crossing slew | Allowed stage voltage noise in band | White-equivalent density | Capacitive edge current at 0.1 / 1 pF |
|---|---:|---:|---:|
| 0.5 V/ns | 12.25 µV RMS | 4.33 nV/√Hz | 0.05 / 0.5 mA |
| 1 V/ns | 24.50 µV RMS | 8.66 nV/√Hz | 0.1 / 1 mA |
| 5 V/ns | 122.48 µV RMS | 43.31 nV/√Hz | 0.5 / 5 mA |

Current is `C*dv/dt`, a charging requirement, not total bias or supply power.
Equal variance allocation is a budgeting example; the real three stages have
different loads, transfer functions and correlations. Discrete AM/supply spurs
and static skew are not included in this random-noise allocation.

As a deliberately simplified input-referred thermal screen, use
`en² = 4*k*T*γ/gm` at 300.15 K and an **assigned** effective γ range of 1–3.
The corresponding gm ranges for the three rows are 0.884–2.651 mS,
0.221–0.663 mS and 0.00884–0.02651 mS. This assumes the relevant voltage noise
can be referred through unity gain; load resistance noise, induced gate noise,
flicker conversion and periodically time-varying operation are omitted. These
numbers are not GF180 transistor parameter bounds or predicted circuit noise.

Bandwidth can be more demanding. In a separate one-pole `fp = gm/(2πC)`
hypothesis, a pole at three times the 2.426 GHz carrier requires approximately
4.57 mS for 0.1 pF or 45.7 mS for 1 pF. With the illustrative strong-inversion
relation `gm ≈ 2I/Vov` and Vov=0.2 V, those become about 0.46 / 4.57 mA per
stage before overhead. This is not a transistor design: increasing device width
also increases parasitic capacitance, and neither that pole nor a useful input
gain is established by choosing gm independently. Pad capacitance, actual
fanout and device speed must constrain the same calculation.

**Architecture implication:** keep clock loads and fanout explicit, favor only
buffering that earns its bandwidth/noise benefit, and budget the input,
phase-generation/division and distribution separately against one delivered
spectral mask. The requirements are not ruled out by this thermal arithmetic;
the high-risk unknown is their simultaneous realization with GHz gain, dynamic
noise folding, flicker/supply conversion, headroom and the common current/area
budget. Narrow voltage/temperature operation does not remove those AC effects.
Do not label the original 1 mV / 0.3 ps stress points as measured limits, or
claim the tighter allocation is proven because this lower-bound screen fits.


The [combined RF requirements point](risk-priorities.md#combined-rf-requirements-point)
now joins the input/distribution spectrum with finite frontend IIP3, rather
than borrowing a pass from the ideal-clock linearity fixture. The 75 µV / 15 fs
high-impedance allocation accepts six tested requests; its terminated counterpart
accepts five. These are bounded experiments under unqualified physical
parameters, not proof of a delivered spectral mask or a complete alternative.
