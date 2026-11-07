# Clock feasibility envelope

## Complete path boundaries

`REF_IN` and `REF_IN_N` form one differential reference/LO input, configured
while stopped. Both legs require qualified analog conditioning, bias and
protection. This is not a standard GPIO input or two independent references.
The selected RF direct-LO band is 2.400–2.500 GHz; lower-frequency operation is
a separate stretch configuration defined by `analog-architecture.json`.

| Mode | Complete path | Open physical gates |
| --- | --- | --- |
| External timing, primary qualification route | Source/board → differential pads and receiver → phase generation/division → loaded distribution → RF, converters or wired TX | Source spectrum and swing, pad loading, common mode, additive noise, quadrature and supply coupling |
| Autonomous | Reference ingress → detector/filter/control → oscillator → phase generation/division → consumers, with closed feedback | Startup/tuning, loop stability, phase noise/spurs, supply pushing, loading and budget |
| Wired RX | Serial input → sampler/phase actuator → CDR tracking and qualification → receive transport | Acquisition, traffic-dependent tracking, jitter tolerance, source-loss and recovery |

Wired RX does not inherit TX clock recovery from an external source. Frequency
division reduces phase error in radians but does not improve absolute source
time error; divider additive noise remains. RF same-frequency quadrature must
include amplitude/phase error and tuning variation.

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

## Joint phase, quadrature and spur budget

Spend one clock-related error allocation across random phase, quadrature and
spurs. For a proper complex signal after common complex-gain correction,
image-error power is `(1+g²-2g*cos(phi))/(1+g²+2g*cos(phi))`.
A 0.1 dB/0.5° imbalance contributes about 0.722% image EVM; 0.5 dB/2° gives
3.365%, already above the 1.581% clock allowance for the −30 dB scenario.
Lower oscillator noise cannot repair that imbalance alone.

An output phase spur of peak amplitude `a` contributes `a²/2` variance before
tracking. Injection-point and tracking transfer matter. Correlated rail-driven
terms add coherently; random independent terms can add in variance. Reciprocal
mixing, filtering and aliasing remain part of packet acceptance.

## Supply and buffer delay

For sinusoidal uncorrected frequency pushing, phase RMS is
`K_supply * V_ripple_peak / (sqrt(2)*f_ripple)`. PLL and tracking transfer modify
that relationship. A scalar pushing coefficient is a sensitivity scenario,
not a measured wideband law.

For threshold noise, `sigma_t = sigma_v / slew`; evaluate actual loaded slew
and input common mode on both legs. Static common delay is not jitter, but
varying delay and I/Q skew are. The selected aggregate supply-delay requirement
is 0.0025 ps/mV, with physical sign, bandwidth and stage distribution unqualified.
The common ring, board/package and host-current boundary is specified in
[power allocation](power-partition.md#common-supply-and-return-network).

Input CMRR cannot protect a pin that exceeds its absolute voltage envelope,
nor remove differential noise generated by leg mismatch. Check loaded input
excursions, protection conduction, conversion from amplitude to timing, additive
noise and distribution together. A clean source is only one contributor.

## Converter clock ownership under direct external LO

RF sampling derives from the actual carrier divided by 64, 128, 256 or 512.
At 2.500 GHz the /64 rate is 39.0625 MS/s. FPGA resampling must use the actual
rate; a nominal 40 MS/s ceiling is not a fixed generated clock. Maintain stable
FPGA-facing service during warm hops using the selected epoch/retune protocol.
Cold bias startup and packet turnaround are distinct timing sequences.

Converter aperture error depends on input signal frequency and slew; LO phase
error acts at the carrier. Do not apply an RF-carrier jitter limit directly to
baseband ADC sampling or infer ADC accuracy from oscillator frequency alone.
ADC sample jitter and DAC reconstruction images need their own transfers.

## Wired and video timing

Wired acceptance includes actual loaded channel/driver behavior, physical
sampling phase, clock correlation, traffic patterns and continuous CDR
qualification. Zero errors in a short sequence cannot establish BER or jitter
tolerance. FPGA-assisted periodic prediction retains finite transport and
actuator resolution; source loss and stale coefficients must invalidate ready.

Video uses forwarded ×10 serialization, including fractional 74.25/1.001 and
148.5/1.001 MHz clocks, continuous FIFOs and multi-die alignment. A reference-loss
or queue fault requires stop, epoch/queue recovery and relaunch. Opaque-symbol
continuity alone does not qualify TMDS pad levels or board skew.

## Acceptance and execution

`verification/clock_envelope.py` calculates conditional spectral requirements;
its `evidence/clock-envelope.json` report records assumptions and source hashes.
The [model guide](../system_model/architecture_fast/README.md) identifies joined
loaded-clock, RF, CDR and lifecycle checks. Use the same environment in RF and
wired consumers. A source mask and an input mask must intersect at one real
operating point; independently favorable cases are insufficient.

No measured GF180 GHz phase-noise, aperture or package calibration qualifies
this envelope. Accept model requirements within explicit uncertainty, then test
physical realization with circuits, extraction and measurements. External timing
remains primary; autonomous timing remains in scope with open power/noise gates.
