# Three whole-platform feasibility questions

**Current operating decision:** RF and wired payload operation are mutually exclusive on the same chip. Both capabilities remain required; additional physical resource sharing is encouraged. See the [exclusive-engine policy](exclusive-engine-policy.md), which supersedes simultaneous-operation requirements below. Model/RTL enforcement and resource rebudgeting remain implementation work.

This is the active feasibility work program following the user's explicit
request to account for unknowns that an open PDK does not resolve and the fab
may never disclose. Preserve the full first-fabrication companion scope, the
50-terminal limit, one slot, RF and wired functions, ordinary compatible FPGA
GPIO interface, and narrow temperature/supply allowance. No smaller substitute
chip is authorized by this program.

Current answer to all three questions: **not established**. Separate a design
that fails its current simulation, one that conditionally works under stated
models, and one whose relevant model validity is unknown. None means the
entire GF180 capability has been proved impossible; none licenses a guaranteed
silicon-success claim.

## Evidence and unknowns

Public documentation checked 2026-09-20:

- [PDK repository](https://github.com/google/gf180mcu-pdk) describes the open
  release as an experimental preview. This is the published repository status,
  not a statement that the underlying commercial process is experimental.
- [Model/hardware correlation contents](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_8.html)
  include MOS IV, CV and flicker-noise characterization. These inspected pages
  do not establish calibrated GHz oscillator phase noise, frequency-dependent
  substrate coupling, a package model or the accuracy of our simulator port.
- [Low-voltage statistical-model usage](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_9_2.html)
  has unfinished invocation/switch instructions. This is not evidence that the
  installed files lack statistical parameters: our
  [file inventory](../evidence/model-inventory.json) finds mismatch/noise-related
  terms. Existence, activation, correct simulator behavior, and correlation to
  the relevant fabricated devices are separate questions.

Use four evidence categories for each critical parameter:

1. **Specified and applicable:** exact process option, device, geometry,
   temperature, voltage, tool/deck and documented range are identified.
2. **Model-supported but uncorrelated here:** simulate and retain limitations;
   do not turn a nominal waveform into a yield claim.
3. **Assumed:** publish the assumption and sensitivity to changes in both
   directions, including correlated combinations. Arbitrary 0.5x/2x scenarios
   are stress experiments, not statistical limits or guaranteed worst cases.
4. **Unbounded or unavailable:** expose the maximum uncertainty the architecture
   can tolerate. If no justified bound fits, keep the answer unresolved and
   provide observability/configuration or an alternative implementation path.

Do not assume an undisclosed quantity is zero, that a standard corner covers
it, that it can be calibrated, or that asking the fab will produce the answer.
Calibration can correct measurable systematic error within its range; it
cannot recover information destroyed by noise, clipping, aliasing or inadequate
bandwidth. Fine trim must come with sufficient range, resolution, monotonicity,
observability and a tested search procedure.

## 1. Autonomous wired and RF timing

**Present evidence:** GHz oscillation exists in compact-model tests, but the
RF CML-to-CMOS path failed under actual mixer-clock loading. The wired receive
path has real pulse/capture experiments, but still uses an ideal upstream clock.
Its latest independent 80-bit pattern, with frozen sampling/alignment, loses
2 of 65 scored outputs. No autonomous CDR or RF synthesizer is established.

**Required demonstrations:**

- RF oscillator -> real level conversion -> quadrature -> loaded mixers,
  without ideal GHz sources. Establish unassisted startup, tuning coverage,
  bias/current, phase balance, output slew and load sensitivity. A seeded ring
  and complementary outputs are not startup or quadrature evidence.
- Actual RF frequency-control loop, reference interface, lock monitoring,
  divider/phase generator and supply distribution. Measure modulation of clock
  phase by supply/bias noise and by simultaneous digital/wired activity.
- Wired oscillator/reference/division, independently recovered RX timing,
  detector/controller actuation and TX serialization. Exercise acquisition,
  offset, missing transitions, phase excursions, jitter and reset using a
  declared stimulus family. Do not substitute a fixed retrospectively fitted
  phase or an ideal recovered clock.
- Use device-noise predictions only after checking the simulator's activated
  noise features and method for periodic/time-varying circuits. A deterministic
  transient cannot establish random phase noise. A linear .noise analysis of
  an LNA cannot establish a switching receiver's folded noise.

**First numerical constraint:** the analytic scenario report allocates 25% of
EVM power to small residual LO phase error. At 2.4 GHz it permits approximately
3.32/1.86/1.05/0.59 ps equivalent RMS time error for total EVM scenarios of
-20/-25/-30/-35 dB. These are illustrative system budgets, not selected Wi-Fi
standard limits and not complete PLL phase-noise masks. Integration bandwidth,
reference tracking, close-in versus far-out noise and spurs must be specified.
Baseband ADC aperture jitter must instead be evaluated at its analog input
frequency; applying the 2.4 GHz number to a 10 MHz baseband ADC is a category
error.

**Unknowns needing explicit tolerance:** high-frequency device/gate/substrate
parasitics, noise upconversion and correlation, supply pushing, reference noise,
clock-route coupling, mismatch and temperature gradients. Build sensitivity
surfaces and identify failure boundaries, not only nominal optima.

**Next decisive work:** fix the RF loaded clock interface and select an actual
quadrature architecture; assess oscillator noise methodology and supply
sensitivity. Preserve the remaining wired independent-pattern failures without
letting repeated receiver trimming consume the entire feasibility program.

## 2. Useful RF signal quality and actual converters

**Present evidence:** transistor LNA/mixer/baseband/sampler experiments do not
constitute a radio. Full receiver noise/dynamic range, actual ADC/DAC conversion,
TX modulation quality, references and independent calibration are not closed.
The single-pole sampled-filter experiment rejected a 30 MHz alias by only about
6 dB relative to 10 MHz; retain this failure when designing the real filter.

**Required demonstrations:**

- Explicit waveform, occupied bandwidth, required SNR/EVM, input range,
  blockers, gain allocation, target converter SINAD/SFDR and delivered TX level.
  Explore multiple performance scenarios until a credible envelope is found;
  do not silently redefine useful Wi-Fi as the easiest passing waveform.
- LNA/mixer/filter/ADC loaded chain: noise, offset, gain/IQ mismatch, compression,
  two-tone intermodulation, alias blockers and reference/supply sensitivity.
  Noise, linearity and gain settings must be compatible, not separate optima.
- Actual ADC architecture with reference and clock load, comparator offset,
  capacitor/resistor mismatch, incomplete settling and digital switching.
  8/12-bit transport labels are not ENOB. Implement a DAC/reconstruction/mixer/
  driver chain and measure spurs, image leakage and EVM at a specified load.
- Include the switches and routing that make the resources programmable.
  Qualification of a permanently wired isolated cell does not qualify every
  topology available to a user.

**Analytic limits already computed:** at 300.15 K, kTB for 20 MHz is about
-100.82 dBm before receiver noise figure. NF=10 dB and required SNR=20 dB yield
-70.82 dBm in that simple scenario, before other losses/interference. This is
not a sensitivity specification or a measured radio result.

For 1 Vpp differential full scale, ideal quantization and a two-leg kT/C model,
keeping sampling thermal RMS below half quantization RMS requires about
0.026/0.417/6.674 pF **per leg** at 8/10/12 bits respectively. These are ideal
thermal lower bounds only: mismatch, parasitics, comparator noise, reference
noise and settling can require much more. This illustrates why actual desired
resolution must be budgeted instead of inherited from the stream format.

**Unknowns needing explicit tolerance:** RF noise-model accuracy, device/passive
matching and gradients, passive Q/nonlinearity, ESD leakage/capacitance, switching
noise folding and reference contamination. Gaussian Monte Carlo numbers cannot
substitute for missing validated distributions.

**Next decisive work:** establish converter noise/settling/current envelopes and
choose a real ADC/DAC candidate; test receiver noise/blocker budgets jointly
with gain and filtering. Do not spend another long run merely increasing
nominal mixer gain.

## 3. Coexistence on this die and package

**Present evidence:** custom ring/package are unselected and actual mixed-signal
coexistence is unproved. Logical area/current allocations are not physical fit.
The latest 80-bit receiver/pulse/capture diagnostic consumes 78.36 mA, without
TX, CDR and host processing. Its clock and receiver currents share one bench
supply; do not silently charge them to or exclude them from the PLL budget.

Planning ceilings total 350 mA (CORE 48, HOST 110, WIRE 96, RF 48, PLL 48).
At an illustrative common 3.3 V this is 1.155 W, not measured consumption or
safe pad/package capacity. Thermal resistances of 10/30/60/100 K/W would imply
11.55/34.65/69.3/115.5 K rises at that power; these are sensitivity scenarios,
not properties of an actual package. Narrow ambient temperature does not imply
narrow junction temperature or low local gradients.

A bare L di/dt illustration gives 200 mV for 1 nH and a 20 mA step in 100 ps.
Actual local decoupling and distributed paths alter this substantially. An ideal
reservoir supplying 20 mA for 0.5 ns with 20 mV droop requires 500 pF, before
ESR/ESL and recharge effects. These examples explain why DC pin current limits
alone cannot establish clean RF/clock supplies.

**Required demonstrations:**

- An actual candidate 50-terminal ring/bond map, stack and package geometry,
  with all grounds counted and routing/ESD/guard-ring/isolation area included.
  Confirm assembly compatibility rather than assuming the standard provider
  package accepts the custom ring. Do not add hidden supplies or a paddle.
- Separate actual domain currents, peak spectra and operating modes; allocate
  clock/bias current once. Simultaneous RF RX/TX (as applicable), wired full
  duplex and host switching must be covered by the promised mode profiles.
- PDN/package/board impedance with component tolerances and resonances, supply
  noise injected into sensitive blocks, substrate/metal coupling and thermal
  gradients. Examine mutual inductance and coherent aggressors, not just
  independent random noise sources.
- Whole-chip area and timing closure, including host DDR. RF blocks are not
  useful if data cannot cross a feasible GPIO transport at the selected rate.

**Unknowns needing explicit tolerance:** substrate transfer versus frequency,
package/bond geometry and inductance, ESD RF parasitics, thermal boundary and
cross-domain coupling. Where no validated substrate model exists, report the
maximum tolerable coupling versus frequency/aggressor rather than a fabricated
isolation figure. Absence of a substrate extractor is not infinite isolation.

**Next decisive work:** produce a physical floorplan/pad/package candidate and
an impedance/thermal budget; inject common supply and coupled aggressors into
both clock and radio candidates. Reject a candidate if its required isolation
or heat removal cannot be supported, even if all isolated benches pass.

## Surviving undisclosed information on the full first chip

Reserve and price observability/adjustment within the real 50-pin, area and power
budgets: per-island enable, bias/tuning banks, meaningful lock/status counters,
loopback, known-tone generation, converter capture, local slow monitors and
safe clock test paths. SPI can report slow quantities; appropriate RF outputs
or divided clocks can support external characterization only after their
loading and accuracy are designed. Monitoring must not destroy the measured
signal or silently consume extra pins. Replicas do not prove the actual path.

Preserve independently selectable implementations where their cost is justified
by a specific uncertain mechanism. Do not assume an unlimited analog crossbar
or rescue by an external LO/converter is equivalent to the normal autonomous
single-chip capability. Diagnostic injection remains a diagnostic mode.

For information unavailable from the fab, use electromagnetic calculations,
independent simulator/model cross-checks, applicable public measured silicon
and characterization on the complete chip where possible. Do not promise that
arbitrary undisclosed behavior can be bounded before fabrication. The full
first chip can remain the home-run attempt while exposing honest residual
risks and enough controls to identify/calibrate what is actually calibratable.

## Execution order and evidence

1. Preserve the independent-pattern wired failure; no more alignment fitting.
2. RF loaded autonomous clock/quadrature plus noise/supply-sensitivity method.
3. Actual converter and RX/TX signal-quality budgets/candidates.
4. Physical floorplan/package/PDN/thermal feasibility, revisited as currents and
   loads become measured. This constrains steps 2 and 3 from the outset.
5. Return to end-to-end autonomous wired recovery and physical host transport.

Each work packet must improve one of these answers, state the assumptions it
removes, and leave failures visible. A model uncertainty is closed only by an
applicable bound or evidence; arbitrary guardbands and more nominal simulations
cannot close it.

Reproduce the analytic scenarios with `verification/feasibility_bounds.py`.
See `evidence/feasibility-bounds.json`, `evidence/model-inventory.json`, and
`evidence/wired-frozen-pattern-screen.json`. The analytic scenarios do not
substitute for any transistor, layout, package or silicon qualification.


### Additional evidence: model activation and LNA noise (pass 118)

[Model behavior](../evidence/model-behavior-screen.json) verifies global and
local statistical activation/repeatability on a two-NFET fixture. Actual installed
switch assignments are off despite default-on comments. Three seeds do not
validate distributions, coverage or silicon accuracy. The flicker corner raises
low-frequency fixture noise by about 10.2 dB; its much smaller direct RF-frequency
change does not bound upconverted oscillator/mixer noise.

[Standalone schematic LNA](../evidence/lna-noise-feasibility.json) predicts
8.87--9.80 dB bench-relative noise figure and 2.00--3.02 dB voltage gain over six
TT/FF/SS and flicker cases. This includes bench resistor noise, lacks the actual
mixer load and physical parasitics, and cannot establish a cascaded receiver NF.
Do not use this voltage gain as Friis power gain. The next signal-quality test
must include actual loading and periodically time-varying mixer noise, not
extrapolate a complete receiver from standalone AC/noise success.

### Connected clock and sampled receive evidence (passes 119--120)

An AC-coupled self-biased buffer now switches under actual mixer load near
2.50 GHz. However, 10 mV peak/100 MHz VCO-supply ripple produces 11.07 ps peak
CMOS LO timing modulation versus only 0.419 ps at the differential CML output.
A fourfold timestep reduction preserves these amplitudes. The clock-restoring
boundary is therefore an observed interference-sensitivity risk; intrinsic
phase noise, PLL and quadrature remain unproved.
[Clock evidence](../evidence/rf-supply-ripple-screen.json).

The autonomous-LO LNA/mixer/active-filter/sampling-switch chain propagates a
10 MHz tone but gives only 0.0264 V/V source-to-held gain. Mixer-output gain is
already 0.00321 V/V. This is a concrete loss problem before the active filter,
not evidence of a useful complete receiver. Sampling clock remains ideal;
there is no ADC, second quadrature branch or stochastic noise measurement.
[Chain evidence](../evidence/rf-autonomous-chain-screen.json).

Prioritize differential clock restoration/common-mode rejection and controlled
experiments separating LO-waveform loss from RF/baseband loading. Continue
requiring appropriate time-varying noise analysis: clean deterministic traces
and small tone-fit residuals cannot establish intrinsic jitter or receiver SNR.
