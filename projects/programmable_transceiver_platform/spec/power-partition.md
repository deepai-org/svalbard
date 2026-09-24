# Power allocation revision, pass 6

## Candidate allocation within 50 terminals

Preserve all 36 signal terminals and 14 supply/ground terminals. Reassign `VDD_CORE_1` / `VSS_CORE_1` to `VDD_HOST_1` / `VSS_HOST_1`. The host now has two dedicated supply/return paths, and the core has one. This is a candidate tradeoff, not proof that the core can spare a path.

| Domain | Supply/return pairs | Planning ceiling per connection | Evidence state |
|---|---:|---:|---|
| Core/control and I/O pre-drivers | 1 | 48 mA | No implemented-core power estimate |
| Host output-driver segments | 2 | 55 mA | Limited two-pad-current extrapolation only |
| Wired analog | 2 | 48 mA | Distribution and complete lane current unclosed |
| RF analog | 1 | 48 mA | Full RF/converter current unclosed |
| PLL/reference | 1 | 48 mA | Full clock-engine current unclosed |

These ceilings are engineering targets beneath the provisional 60 mA supply-cell DC limit. They do not imply that the foundry has approved these operating conditions or that rail/package/thermal limits are met. The source of the cell limit is the [GF180 I/O library datasheet](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html); its use for the eventual selected process, pad and temperature envelope requires confirmation.

The core target is now at most 48 mA through its sole supply/return pair, including SRAM/FIFO, GPIO pre-drivers, transport and shared control. If synthesis/activity simulation and physical power analysis exceed it, revise the whole allocation before freeze. Do not claim that relocating the supply pair solved chip power.

## Host segmentation and physical requirements

### Current mathematical host-load hypothesis

The optional integrated host bank now uses explicit 10 pF output capacitors,
10/12 mA pull-up/down limits, 100/80 ohm on-resistance, and 7 pC internal
consumption per changed bit with a 0.5 ns exponential tail. These are exploratory
parameters, not the qualified native-pad fit. The HOST_A/B held background is
2 mA each; the historical 50 fC D2H impulse is disabled to avoid double counting.

For alternating bits that settle through a full 3.3 V swing, capacitor charging
alone demands `C * V * word_rate / 2` average supply current per output. Adding
the assumed internal charge gives this first-order comparison:

| Host word rate | Per-output capacitor + internal current | HOST_A, five outputs + 2 mA | HOST_B, six outputs + 2 mA |
| --- | ---: | ---: | ---: |
| 250 Mword/s | 5.875 mA | 31.375 mA | 37.250 mA |
| 312.5 Mword/s | 7.344 mA | 38.719 mA | 46.063 mA |

This arithmetic is neither a measured bank current nor an operating bound.
Incomplete output swing may lower capacitor current while failing the interface;
therefore low current cannot establish correct data transfer. Input receivers,
pad pre-drivers on CORE, clamp/leakage paths and supply dependence still need
non-overlapping accounting. The loaded traffic runner checks logical transport
and supply coupling, not external receiver sampling of these voltage waveforms.
Its pass must not close host electrical timing or the whole-chip power budget.

The subsequent `host_bank_supply.py --sampling-screen` observes output voltages
and the forwarded-clock threshold crossing rather than accepting ideal words.
With the same exploratory driver, 10 pF loads, a 3.3 V receiver and assumed
0.3/0.7 data thresholds, the synchronous alternating-pattern fixture gives:

| DDR clock | Sample delay after modeled clock crossing, including 0.2 ns per-side allowance |
| --- | --- |
| 125 MHz | 0.928–2.215 ns |
| 150 MHz candidate | 0.913–1.606 ns |
| 156.25 MHz | 0.889–1.489 ns |

All three have a nonempty sampled window, but sampling halfway after the ideal
launch fails on eight of sixteen measured words in each case. Host clock phase
selection must therefore be explicit. These finite, grid-sampled intervals are
conditional on equal ideal launch delays and the chosen receiver thresholds;
they omit actual FPGA setup/hold, delay mismatch, package/board effects and clock
jitter. They are not a qualified eye or a guarantee for arbitrary data patterns.
The faster profile's approximately 0.600 ns residual window makes those omitted
effects material. Evidence: `host-bank-sampling-screen.json`.

`HOST_A` owns D2H data 0–4 and H2D data 0–4, plus SPI/reset pad circuitry. `HOST_B` owns D2H data 5–9, D2H clock, H2D data 5–9 and H2D clock. A and B each have one dedicated supply pad and one dedicated return pad. They use the same nominal board I/O voltage, but output-driver rail segments must have explicitly routed local feeds and returns. Their electrical connection on the board does not justify assuming equal on-die current division.

The [native netlist audit](../evidence/supply-cell-audit.json) records these formal pins:

- `gf180mcu_fd_io__dvdd`: `DVDD DVSS VSS`.
- `gf180mcu_fd_io__dvss`: `DVDD DVSS VDD`.
- `gf180mcu_fd_io__brk2` and `__brk5`: `VSS`.

Digital pad output devices use `DVDD/DVSS`; pre-drivers use `VDD/VSS`. The candidate rail map connects each host output-driver segment to its own HOST feed/return and pre-driver rails to CORE. Supply-cell clamps and corner cells have cross-rail connections that must be explicitly instantiated and verified. The formal-pin audit is **not** proof of physical rail continuity or isolation: inspect LEF/GDS, breaker placement, well/substrate paths and actual metal connectivity before layout acceptance. Keep short return paths for each D2H clock/data group. Clock/data loading, rail differences and deskew must be evaluated across the segment boundary.

This revision adds neither a hidden paddle nor an uncounted supply terminal. Bond-wire peak current, inductance and ground bounce are independent of the DC ceiling and remain open.

## Limited current screen

`check_power.py` uses the saved pass-5 alternating-pattern pair currents, divides by two for an identical output estimate, and scales by five or six outputs. It then applies a **provisional** 1.25 multiplier plus 2 mA per segment for unmodeled activity. These allowances are assumptions, not measurements or guaranteed guard bands.

| Corner / segment | Scaled average | With provisional allowances | Candidate ceiling |
|---|---:|---:|---:|
| TT / A (5 fast outputs) | 33.18 mA | 43.47 mA | 55 mA |
| TT / B (6 fast outputs) | 39.82 mA | 51.77 mA | 55 mA |
| SS / A | 29.38 mA | 38.72 mA | 55 mA |
| SS / B | 35.25 mA | 46.07 mA | 55 mA |

The [retained assessment](../evidence/host-power-allocation-screen.json) hashes the exact contract and input report. It marks **every domain unqualified**. Tests reject duplicated/missing supply ownership, duplicated outputs, the prior single-host-pair allocation and an increased-current counterexample. No runtime gate interprets the planning screen as physical signoff.

The next physical pass must include FF/high-voltage current, input-bank activity, clamp/rail behavior and explicit package impedances. The current TT/SS ideal-supply pair result cannot bound those cases. In parallel, actual RTL/memory selection must produce an activity-based core-power estimate; copying a pad from CORE is not a substitute for that evidence. A full-bank transistor run should then replace the linear estimate and test both in-phase and opposing group activity.

## Pass 8 limitation

The [8 pF host screen](artix-host-load-screen.md) exceeds HOST_B's planning ceiling after the existing allowances (63.54 mA versus 55 mA), even at nominal temperature and voltage. The two-segment allocation remains a candidate and is not closed for this load. Passing the earlier 5 pF executable screen does not supersede this negative evidence.

Pass 9 [native driver comparison](host-driver-selection.md): 12 mA mode reduces the same 8 pF HOST_B estimate to 55.75 mA with unchanged allowances, still above 55 mA. No driver or current ceiling is changed by this experiment.

Pass 10 [8 mA candidate](weak-drive-screen.md): the nominal 10 pF HOST_B estimate is 53.80 mA with unchanged allowances. This passes the limited planning comparison but leaves only 1.20 mA headroom; no package/bank/operating-envelope closure is implied.

## Coupled mathematical load accounting

The integrated candidate now expresses wired output load in physical units:
`Vdiff = 0.4 V * serializer.drive`, `Ptermination = Vdiff^2 / 100 ohm`, and
`Irail = 2 mA + Ptermination / (0.35 * Vrail)` while the wired engine is selected.
The voltage, termination, efficiency and bias are explicit configurable
assumptions, not transistor results. The normalized channel still assumes
regulated output swing throughout the accepted rail range. Compliance limits,
output impedance changes and gate-switching charge remain to be modeled.
The last driven level continues to draw termination power until the serializer
is reset/aborted; completing a finite word list does not erase its output state.

RF driver bias is counted only while its oscillator is enabled; wired driver
bias is counted only for the selected wired engine. Shared reference bias
remains active. Oscillator, converter, receiver and digital operating currents
are not yet a complete mode-dependent inventory. Do not interpret the resulting
few-milliampere rail current as a whole-chip current estimate.

The continuous solver integrates ideal-source energy, feed-resistor loss and
load energy. Host charge impulses record the rail capacitor's corresponding
energy decrease. The checked balance is source energy = feed loss + load energy
+ impulse energy + change in rail capacitor energy. This verifies the modeled
lumped rail's accounting, not transistor efficiency or a package power network.
The one lumped rail remains a coupling fixture; it does not replace the separate
physical supply-domain allocations above.

## Retained evidence audit: load scale and rail-model limits

The source hashes for `analog/rf_rx_candidate.spice` and
`analog/rf_candidate_bias_tb.spice` still match
`evidence/rf-candidate-bias-screen.json`. That **prebiased, seeded, nominal**
fixture reports 14.254 mA on its RF supply and 8.409 mA on its clock supply.
It has ideal external bias/sampling clocks and no complete PLL, quadrature path
or ADC; these values do not qualify the integrated candidate.

`evidence/rx-adc-partial-power.json` reports approximately 92.93–95.83 mW on
selected filter, sample-driver and reference supplies in a failed, incomplete
transient run. The reference pair alone accounts for about 42.42–45.32 mW in
those windows. Other ideal sources may deliver or absorb energy, so the report
is neither total consumption nor a guaranteed lower bound. These supplies may
overlap other historical fixtures; summing the reports would double-count or
combine incompatible circuits.

The current coupled model's 3.3 V source, 100 ohm feed and 2.5 V lower rail limit
allow only `(3.3-2.5)/100 = 8 mA` in steady state. The retained RF fixture's
14.254 mA alone exceeds that model envelope. At that current, 56.13 ohm is the
largest feed resistance consistent with the same voltage floor, before any
other load or transient margin. This arithmetic exposes a modeling gap; it is
not evidence that the silicon requires a 100 ohm feed or that the chip cannot
work. Replace the single coupling fixture with explicit domain DC feeds and
bounded transient coupling before inserting a complete current inventory.

The historical `clock-power-screen.json` also reports much larger core clock
loads than the few-milliamp analog fixture. Assuming perfect gating of just the
inactive engine's listed clock-input capacitances gives:

| Mode | Selected engine | Clock-pin charging estimate | Remaining from 48 mA core allocation |
|---|---|---:|---:|
| 0 | RF | 18.355 mA | 29.645 mA |
| 0 | Wired | 18.822 mA | 29.178 mA |
| 1 | RF | 22.525 mA | 25.475 mA |
| 1 | Wired | 24.237 mA | 23.763 mA |

These are recomputations of that saved nominal Liberty/netlist screen, not new
power measurements or proof of clock-gating implementation. Host clocks remain
active in this arithmetic. Internal cell power, clock trees, data/control
switching, leakage and GPIO pre-drivers are excluded. Mutual exclusion helps
but leaves the dominant host-clock load. Current netlist selection, domain
ownership and gate controls must be reconciled before using these estimates in
the executable full-chip current model.

## Supply ownership for exclusive operation

Use the following physical ownership when connecting the domain model. Engine
selection controls loads inside a domain; it does not disconnect the entire
supply pad. In particular, the RF pad name does not imply that shared converters
are unavailable in wired maintenance mode.

| Circuit group | Physical supply owner | Activity rule |
|---|---|---|
| Transport, memory, control, clock-tree cells, GPIO pre-drivers | CORE | Management/retention plus actual host and selected-engine activity |
| Host output devices and pad receivers | HOST_A / HOST_B, per pad map above | Actual traffic and input activity; clocks and idle patterns count |
| Wired TX driver and termination control | WIRE_A | Wired selected; held output level continues drawing power |
| Wired RX front end, equalizer, slicer and local recovery circuitry | WIRE_B | Wired RX/detection activity; account any required quiet detection bias separately |
| RF LNA, mixers, RX filters, TX reconstruction and output driver | RF | RF acquisition/calibration/payload as required; isolate inactive front end |
| Shared sample converters and diagnostic analog mux | RF | RF payload or explicit maintenance ownership, including wired maintenance |
| Reference input, master bias, converter reference and analog clock engines | PLL/reference | Shared services remain available; only inactive clock-engine branches may stop |

This is the selected modeling partition, not validated rail routing. Local
buffers belong to their consuming domain unless their explicit circuit supply
says otherwise. Distinguish CORE digital clock-tree current from PLL/reference
analog oscillator/divider current to avoid double counting. A future physically
shared synthesizer must replace the two branch inventories, not add a third.

For each row, the executable load inventory must include idle bias, enabled
bias, switching charge or power, startup charge, and off-state leakage (zero
only as an explicit hypothesis). Unknown quantities remain unknown, not zero.
Count shared converter and reference instances once, even when both ADC and DAC
operate in RF mode. Their conversion events and load-dependent reference output
power remain separate contributions. Host supply current and the existing
host-coupling impulse are not two independent copies of pad switching power;
replace the impulse fixture with the physical-domain event when integrating.

WIRE_A/B have separate connection limits; their aggregate 96 mA allocation is
not permission for either connection to carry 96 mA. Likewise, shared converters
continue to consume the RF connection's allocation during wired maintenance.
Full-chip budget closure needs these loads and mode transitions on the same
supply owner. The current seven-domain RC primitive is still isolated and does
not establish this integration or any package parameters.

The domain candidate now routes H2D/D2H word-event charge by the physical 5/5
host data split, with the clock charged to HOST_B. The same event replaces the
scalar impulse; it is not added a second time. RF/PLL capacitor voltages remain
continuous at a host impulse, then respond through the common return network.
Per-transition charge is still an assumption, not a measured pad-energy law;
CORE pre-driver switching and SPI/reset events still need their own inventory.
A short RF/wired startup check verifies segment voltage steps, energy balance
and unchanged oscillator phase at the event. Sustained traffic remains open.

## Current integrated fixture is not a feasibility load envelope

The finite-charge screen in `evidence/host-charge-domain-screen.json` exposes a
second important limitation. The integrated host event assumes 50 fC per bit
transition. Charging an external 5–10 pF output through 3.3 V demands 16.5–33 pC
per rising output, 330–660 times that event charge. The small event remains a
coupling fixture; moving it onto the HOST rail did not turn it into a complete
physical pad-energy model. Constant background current cannot qualify its
missing edge-time voltage behavior.

`verification/host_charge_domain_screen.py` applies that charge as a finite
rectangular current pulse to the existing seven-domain RC primitive. It replaces
the 20 mA host backgrounds with assumed 2 mA idle loads and adds no 50 fC impulse,
avoiding duplicate charging in this experiment. Five HOST_A and six HOST_B
outputs rise together. Other backgrounds, 2 ohm feeds, 100 pF local capacitance
and 0.1 ohm common return remain explicit hypotheses.

| Output load | Assumed rise duration | Minimum HOST_B | Above 2.5 V model floor |
|---|---:|---:|---|
| 5 pF | 0.25 ns | 2.705 V | Yes |
| 10 pF | 0.25 ns | 2.119 V | No |
| 10 pF | 0.5 ns | 2.519 V | Yes, little margin |
| 10 pF | 1 ns | 2.865 V | Yes |
| 10 pF | 2 ns | 3.075 V | Yes |

The uncoupled scalar analytic check agrees within 4.5e-16 V; doubling the
minimum-search sampling changes minima by less than 55 uV. Exact interval energy
accounting also passes. These are prescribed **charge demands**, not proven
driver waveforms: a real output may instead slow or lose swing. Longer edges
must still meet host timing. This isolated rising-edge screen omits sustained
traffic, input activity, falling-edge ground current, inductance and substrate
coupling, so even its passing cases do not qualify the supply network. No
connection's DC planning ceiling is used as an instantaneous pulse-current limit.

The same script verifies retained 8 mA native-pad deck, waveform and log hashes
from `scratch/transceiver-weak-drive-waveforms.tar.gz` and reproduces their
settled current measurements. The 8/10 pF alternating cases consume respectively
40.32/44.20 pC of total supply charge per counted output rise. This includes
internal current, bias and the intervening falling activity; it is not an
isolated rising-edge law. It nevertheless confirms that the full-chip 50 fC
disturbance has the wrong scale for physical pad loading.

Replaying those ideal-supply pair-current waveforms, scaled by 2.5/3 for the two
segments, gives HOST_B minima of 3.150/3.131 V with the same assumed RC network.
These finite native waveforms are much less severe than the prescribed 0.25 ns
charge-demand case. Their replay is encouraging but does not close the gap:
the trace cannot respond to rail droop, fractional pair replication is not
five/six-pin simultaneous switching, and return/substrate/inductive paths remain
incomplete. Use native bank simulation with nonideal rails to supply a bounded
reduced current model rather than copying these traces as a qualified load law.

The first native eleven-output bank comparison is retained in
`evidence/native-host-bank-rc-screen.json`. All five/six output instances share
the same switching stimulus for an electrical simultaneous-switching stress.
The ideal-supply case completes 32 ns in 12 seconds, with every output reaching
about 0.057–3.069 V. The 2 ohm feed / 0.1 ohm common-return / 100 pF-per-segment
case times out after 90 seconds at reported simulation time 0.861 ns, before
the 4 ns stimulus begins. Deck, log and completed-waveform hashes are verified.
This is an unresolved numerical/initial-state problem, not measured supply
collapse or a bank-current pass. Reproduce with `verification/run_host_bank.sh`;
wrapper completion only means artifacts were retained. Isolate feed versus
return impedance before fitting a current model from nonideal-rail waveforms.

That isolation is now recorded in `evidence/native-host-bank-isolation-screen.json`
(`run_host_bank.sh --isolate`). With only the 0.1 ohm return impedance, the complete
bank runs to 32 ns and both local supply spans remain above 3.273 V in the
measurement window; the return reaches 26.75 mV above board ground. With only
the two 2 ohm feed impedances, simulation again times out before stimulus.
The common return alone therefore does not reproduce the numerical failure.
Next distinguish fixed DVDD/core-supply offsets from dynamic supply-feed
feedback using short startup observations. Do not turn timeout evidence into
electrical impossibility or use the successful return-only case to qualify the
full supply network. Both isolation cases retain 100 pF per segment.

The fixed-offset control (`run_host_bank.sh --offset`,
`evidence/native-host-bank-offset-screen.json`) holds both driver rails at
3.296 V with the core at 3.3 V and ideal ground. This reproduces the assumed
2 mA × 2 ohm idle drop without dynamic feed feedback. The full bank completes
32 ns in 12.24 seconds and all outputs span approximately 0.057–3.064 V.
That fixed offset alone does not reproduce the timeout. Dynamic feed feedback
and its numerical treatment remain unresolved; this does not identify a
physical instability.

## Explicit host capacitor/return model candidate

`verification/host_bank_supply.py` now models the eleven output capacitors to
board ground, separate pull-up/down paths, seven local supply capacitors, feed
resistors and the common return. It retains local supply spans and output
voltages as continuous states and solves the return potential algebraically.
The governing charge relation is
`sum(feed currents) - return current = sum(Coutput * dVoutput/dt)`.
Consequently, output charging and discharging cannot both be represented by
the same positive two-terminal supply impulse. The earlier lumped charge-demand
screens do not establish the true ground-return waveform.

For each held digital pattern and background load, the candidate propagates the
affine circuit exactly and independently integrates source energy, resistor
loss, background-load energy and stored capacitor energy. Controls in
`evidence/host-bank-supply-controls.json` compare with a separate nodal ODE for
both edges, check interval subdivision and KCL, and recover the existing
seven-domain model when output capacitors are absent. Maximum ODE discrepancy
is below 4e-14 V and energy residual below 1e-21 J in these controls. The
exploratory simultaneous-edge fixture produces an initial ground movement of
−13.4 mV on rising and +30.0 mV on falling; these are model examples, not chip
predictions.

This is **not integrated into the full-chip candidate**. Its 150/100 ohm
pull-up/down resistances are provisional, and its ideal switches omit delay,
overlap current and internal switching charge. Fit and bound those terms against
native pad evidence, then connect actual D2H bit events and rail/clock histories.
H2D receiver switching requires its own load model; external input capacitance
is charged by the FPGA, not by the transceiver's output drivers. Package
inductance, distributed grounds and substrate coupling remain outside this
candidate. Preserve the current noisy-RF run before replacing its supply owner.

The first native-waveform fit is retained in `evidence/host-driver-fit.json`
and reproducible with `verification/fit_host_driver.py`. A delayed linear RC
driver fitted to early 10 pF bank cycles gives approximately 127/89 ohm
pull-up/down resistance and 2.37/2.52 ns rise/fall transport delay. Held-out
later cycles have 0.132 V RMS / 0.336 V peak voltage error; the unused 8 pF
pair data has 0.138 V RMS / 0.372 V peak error. Supply current is not fitted.
These parameters are therefore not installed as a validated driver law.
Bound nonlinear current, gate slew/delay and internal switching energy before
using this reduced circuit to qualify whole-chip timing or rail margin.

Adding bounded output current improves the voltage model without closing its
power accounting. `fit_host_driver.py --current-limited` fits an approximately
13.27/16.13 mA pull-up/down limit and retains separate transport delays. In
`evidence/host-driver-current-limited-fit.json`, held-out 10 pF voltage error
falls to 0.040 V RMS / 0.158 V peak; unused 8 pF data gives 0.086 V RMS /
0.180 V peak. A separate capacitor-current ODE agrees with the piecewise
analytic model within 1.5e-9 V. The older resistor-only result is preserved.

Over two held-out periods, measured driver-supply charge is 88.38 pC per pad,
whereas predicted external-capacitor charging accounts for 61.44 pC. Positive
charge computed directly from the native output waveform is 60.18 pC, so the
gap is not primarily the fitted output-voltage error. The model leaves about
2.11 mA per pad unaccounted for in this window. This residual includes internal
pad switching, bias, coupling and model error; it is not a uniquely identified
current law. It is already included in the native measured-current budgets and
must not be added to them again. Core pre-driver current is a separate rail.

Next carry bounded nonlinear drive and internal switching-energy terms into the
explicit capacitor/return model and the actual full-chip host events. Do not
spend more passes polishing nominal voltage fits while those power terms remain
absent. Current-limited fit parameters are still not installed as qualified
full-chip behavior.

`LimitedHostBankSupply` in `verification/host_bank_supply.py` now supplies the
missing accounting mechanism: separate current-limited pull-up/down branches
and finite internal consumption pulses, assigned to each output's physical
supply. An edge adds pending internal charge; that charge is consumed through
an explicit time constant and its instantaneous rail voltage determines energy.
It is not stored capacitor energy and is not a second copy of output charging.
Repeated unchanged data does not inject another pulse. Background loads remain
separate and must exclude the internal switching term they replace.

`evidence/host-bank-limited-supply-controls.json` records linear-limit comparison,
interval refinement, per-domain charge conservation, complete energy balance,
repeated-word behavior and atomic rejection of an overload. In its declared
fixture, two edges inject 70/84 pC into HOST_A/B; charge residual is below
8e-27 C and energy residual below 2e-23 J. The tested 7 pC per changed output,
0.5 ns pulse duration and output-current limits are hypotheses, not validated
native-pad bounds. The model remains outside the full-chip composition.

The next integration must preserve these continuous output-capacitor states and
charge tails inside the same analog owner as RF/reference/PLL supplies. Actual
D2H bit and clock events should replace the legacy output charge impulse, while
H2D receiver activity remains separately accounted. Do not replay independently
advanced rail histories or retain the old output impulse on top of the new load.

The noisy independent RF test has now completed with source-verified RX/TX
waveform passes, so its snapshot is preserved. It still uses the 50 fC host
disturbance and does not validate the explicit host capacitor/return candidate.

Next replace the full-chip host disturbance fixture with finite, load-dependent
pad supply/return currents, retaining per-segment ownership and energy accounting.
Test those currents together with autonomous timing and RF conversion; do not
select feed/decoupling values solely to repair this screen. Current noisy-RF
tests still use the original 50 fC fixture and must retain that limitation.

The new domain RF/wired tests use 20 mA CORE background. Against the retained
clock-pin estimate above, RF mode 0 leaves only 1.645 mA of that fixture for all
non-clock-pin core activity; RF mode 1 clock-pin charging alone exceeds it by
2.525 mA. These comparisons are historical estimates, not current RTL power,
but the 20 mA fixture cannot be presented as an established whole-core bound.

At an assumed 3.3 V, the partial reference-pair power windows correspond to
12.85–13.73 mA, versus the coupled reference's 0.1 mA fixed bias placeholder.
The model additionally charges finite reference output power; that does not
establish coverage of the measured candidate's internal bias. The partial
report is from an incomplete, failed transient and must not be summed with
other candidate reports or substituted as a validated total current.

After functional domain integration, prioritize a complete, non-overlapping
mode-dependent current inventory and a declared load envelope up to the
connection budgets. Do not tune the domain feed resistance merely to make an
optimistic current fixture pass. The running RF diagnostic intentionally retains
its recorded assumptions so it can expose integration defects; its eventual
result cannot close power feasibility.


## Additional protocol resource budgets

One slot means 3.93 × 5.12 mm, not 1 mm². Retain the conservative 12.92 mm² core
ceiling and the 36-signal + 14-power/ground terminal allocation. Provider page
checked 2026-09-23 lists 56 default I/O pads; the old 74-pad template statement
in earlier planning must not be treated as the current offering. Our custom
mixed-signal ring/assembly still requires independent fit and return analysis.

Reserve **0.80 mm² within the existing 3.72 mm² closure reserve** for expansion:
0.35 wired/USB local circuits, 0.15 timing/rate controls, 0.10 RF bandwidth/gain
controls, 0.15 digital event/streaming helpers and 0.05 configuration memory.
The residual reserve is 2.92 mm². These are allocation caps, not transistor area
estimates. No reduction in return pins, baseline buffers or converter performance
is assumed. If the allocation fails, revisit sharing/circuit choice and report
the conflict; do not quietly drop a requested capability or expand the die.

Power is not justified by this area reservation. Add selected-mode current and
switching loads for every new branch to the same seven-domain model. USB cannot
borrow RF current headroom across unrelated supply pins. Inactive branches still
contribute capacitance, leakage and substrate coupling. Budget DC and transient
current against the existing per-domain limits; actual transistor current and
thermal closure remain unknown. No additional regulator or supply is assumed.

The largest new wired rate is 1.62 Gb/s, below the existing 2.5 Gb/s target.
At 40 MS/s and 12 bits each for I and Q, RF payload is 960 Mb/s per direction;
at 20 MS/s and 8 bits it is 320 Mb/s. Existing exclusive bandwidth arithmetic
therefore provides room in principle. It does not prove USB turnaround, packet
jitter, continuous host timing, or ADC ENOB. Bound queues and transport latency
separately for every profile and clock tolerance. Converter precision/sample
rate increases and FFT/FEC/modem hardware on this die are not part of this pass.


## Coupled shared-pad state

The optional USB branch is now owned by `LimitedCoupledDriver`. Its two node
voltages and local-source/external-source/dissipation energy integrals advance
transactionally with the original RF/filter/reference/host/supply states.
Forecast copies include the branch; committing a forecast preserves its object
identity. Existing host-bank regressions cover the no-branch case. The default
2 pF node, 0.2 pF mutual and 0.3 pF disabled-branch capacitances are assumptions.

In the finite HS fixture, the wired rail reaches about 3.260 V and independent
pad energy residual is below 1e-18 J. This is not a power estimate for a complete
USB PHY. Disabled-branch capacitance is represented in the pad circuit but has
not yet been integrated into the independent serial receiver channel/CDR model;
that remains a critical 2.5 Gb/s coexistence gate.

## Historical quiet-rail numerical diagnostics

These bounded experiments preserve numerical failures as well as successes.
They do not qualify switching behavior or replace the current power allocation.

### Pass 13: isolate quiet-input rail startup

Four fresh, bounded one-nanosecond runs compare ideal rails, supply-only impedance, return-only impedance and both. Each active rail uses the same selected 0.25 ohm/2 nH series path from pass 12. The native 8 mA pads, unequal signal inductances and 10 pF loads remain. Data and clock inputs are held low, matching the prior stimulus before its 20 ns start. Core supply/return remains ideal.

All four DC operating points and short transients complete with default integration and a 10 ps maximum step. Reported VDD is 3.3 V; quiet source current is approximately 0.71 nA. The both-rails case has VSS between −0.024 and +0.395 nV, and low output voltage around 3.35 nV. These tiny model residuals do not establish physical noise accuracy.

| Case | Saved transient rows | Completed simulated time |
|---|---:|---:|
| Ideal | 108 | 1 ns |
| Supply only | 329 | 1 ns |
| Return only | 287 | 1 ns |
| Both | 391 | 1 ns |

This rules out an obvious large startup rail excursion **in the captured interval**. It does not explain the later slowdown, prove stability beyond 1 ns, or test switching. More adaptive points with R/L are observed, but their count alone is not a diagnosis. Prior full-interval timeouts remain unresolved, including those using Gear.

Run `verification/run_rail_startup.sh` from this project. Each probe has a 30-second subprocess limit and records completion separately from waveform availability. The [retained report](../evidence/rail-startup-screen.json) includes deck/log/operating-point/waveform hashes. The raw archive is `scratch/transceiver-rail-startup-artifacts.tar.gz`.

Next preserve intermediate waveforms as simulated time approaches the slowdown, inspect timestep and rail/internal-node behavior, and compare the supply-only/return-only cases over that same interval. Do not infer that more damping is the correct physical fix before distinguishing numerical behavior from circuit behavior. Follow the [two-sided uncertainty requirement](uncertainty-envelope.md): both apparent stability and apparent instability need scrutiny.

Archive SHA-256: `1327697b4462f4ae991e1670b4fbd06aa5fcb6e3ed91b8b88bb87d0ed8633b6e`.

### Pass 14: intermediate quiet-rail traces

The startup harness now saves checkpoints at 1, 2, 4 and 8 ns before a requested 12 ns endpoint. The [ngspice stop/resume commands](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf) preserve transient state; the circuit is not restarted at each checkpoint. Saved endpoint times are checked against the requested times, and 16-digit output preserves small rail changes. The ideal case exercises all checkpoints successfully.

Physical conditions match pass 13: quiet low inputs, native 8 mA pads, 10 pF loads, unequal signal inductances, and zero or selected 0.25 ohm/2 nH paths on supply/return. Integration is default trapezoidal, maximum step 10 ps. Each case has a 60-second wall-time bound.

| Case | Execution | Last saved checkpoint | Saved rows at that point | Median / minimum saved timestep |
|---|---|---:|---:|---:|
| Ideal rails | Completed | 12 ns | 1,220 | 10 ps / 100 fs |
| Supply only | Timeout | 1 ns | 329 | 1.25 ps / 9.77 fs |
| Return only | Timeout | 2 ns | 590 | 2.5 ps / 78.1 fs |
| Both | Timeout | 2 ns | 753 | 1.25 ps / 9.77 fs |

The last saved checkpoint is not the exact point at which the run timed out. Logs continued to report progress after those checkpoints. Intermediate traces are retained despite the timeout.

Supply-only VDD varies by approximately 0.062 nV in the saved interval. Return-only VSS varies by approximately 0.000367 nV. With both paths, VDD and VSS variations remain below 0.5 nV. These are model residuals, not predictions of physical noise. They show no large rail excursion in the captured intervals; later behavior is not available.

#### Interpretation and next test

The slowdown is not unique to the interaction of two moving rails: either rail impedance can expose it. Tiny timestep selection while terminal voltages remain nearly constant is consistent with numerical sensitivity, but does not identify the cause or rule out hidden internal-node behavior. The checkpoint interruptions also affect timestep history, so elapsed progress is not directly comparable with uninterrupted runs.

Next compare the installed simulator's linear solvers on the same circuit and timestep controls, retaining both successful and unsuccessful outcomes. Inspect internal-node behavior or tolerance sensitivity if solver choice does not resolve it. Do not change circuit damping or relax electrical requirements merely to obtain a completed run. Both false stability and false instability remain possible until the numerical result is cross-checked.

Reproduce with `verification/run_rail_checkpoints.sh`. The [report](../evidence/rail-checkpoint-screen.json) records execution state and hashes. Raw decks, logs and snapshots are in `scratch/transceiver-rail-checkpoint-artifacts.tar.gz`. The wrapper reports completion of the diagnostic collection; only the ideal electrical simulation reached its requested endpoint. No switching, bank-current or FPGA timing claim is established.

Archive SHA-256: `9da1c7c81542d60c5239a5922c1d4a247fc9c1ded50ffd883c96a10995138329`.

### Pass 15: linear solver comparison and invalid snapshot rejection

Four fresh runs compare SPARSE 1.3 and KLU with ideal and shared R/L rails. Physical decks, integration method, tolerances and checkpoint times are identical after normalizing output paths; the comparison checks that equality. KLU is selected through `.spiceinit` using the [documented option](https://ngspice.sourceforge.io/applic.html). Each log confirms the actual solver. No compatibility flags, device parameters or circuit damping are changed.

| Circuit | SPARSE | KLU |
|---|---|---|
| Ideal rails | Completes 12 ns | Completes 12 ns |
| Shared 0.25 ohm/2 nH per rail | Times out; last saved checkpoint 2 ns | Aborts at initial time point, identifying DVSS |

Solver choice does not resolve the shared-rail problem. KLU's initial-step failure and SPARSE's tiny-step progression are numerical outcomes; neither proves physical instability. The ideal control succeeds under both solvers. The full chip and dynamic rail behavior remain unqualified.

#### Analyzer defect found and corrected

After KLU's transient abort, subsequent `wrdata` commands wrote single-row operating-point data into the checkpoint filenames. The old parser attempted a timestep minimum on an empty difference array and raised an exception. It did not produce a successful comparison report, and no such artifact is accepted as a transient result.

The parser now rejects single-row, non-finite, non-increasing-time and wrong-endpoint traces before computing statistics. Explicit transient-abort messages mark simulator failure even if ngspice exits with code zero. Normal checkpoint `pause requested` messages are not failures. Four new tests cover valid traces and malformed snapshots. Saved ideal runs exercise normal pause handling; all five shared-rail KLU snapshots are rejected.

The [retained report](../evidence/rail-solver-screen.json) is corrected analysis of the saved run, not a new simulation. Replay checks exact deck and initialization content; the original SPARSE timeout is retained explicitly. Raw files are archived in `scratch/transceiver-rail-solver-artifacts.tar.gz`, with its hash in the report. The initial diagnostic run directory is `scratch/transceiver-rail-solvers.u6A18iuO`.

Reproduce the current experiment with `verification/run_rail_solvers.sh`. It now retains simulator and invalid-snapshot failures instead of crashing during extraction. Diagnostic collection success does not mean all simulations completed.

Next isolate resistive versus inductive rail elements and inspect the native MOS-capacitor/ESD model contributions. Keep the physical model unchanged for solver comparisons; any later simplification must be explicitly a diagnostic and must not become evidence for the complete chip. Both artificially stable and artificially unstable numerical behavior remain concerns.

## Candidate algebraic host-ground acceleration

`verification/host_capture_check.py --ground-solver-check` compares an exact
piecewise-linear ground solution against the current Brent root. It enumerates
current-limit breakpoints and interpolates the root only within one affine
segment; branch resistances and bidirectional current limits remain unchanged.
Two thousand randomized rail/output/drive cases agree within 1.69e-15 numerical
units and satisfy return-current balance. One local timing comparison measured
1.67x faster branch evaluation, not whole-chip speedup.

An eight-interval switched standalone-bank comparison at existing integration
tolerances reaches 5.18e-9 V state difference, exceeding the provisional 1e-9 V
comparison gate. Maximum reported final energy difference is 4.08e-19 J. Retain
this failed strict comparison: tighter integration tolerance/refinement must
separate solver-equation error from adaptive ODE trajectory differences before
installation. The running canonical RF model still uses its original solver.
Refinement at `(rtol,atol)=(1e-10,1e-13)` and `(1e-11,1e-14)` reduces the
maximum difference to 9.93e-11 V and 7.81e-11 V respectively, passing the unchanged
1e-9 V comparison gate. Final energy differences are below 8e-21 J. These results
support adaptive integration error as the coarse discrepancy; the consolidated
check retains all three tolerance levels. Full coupled-driver/RF trajectory
comparison and floor-rejection equivalence remain required before promotion.

The companion `--coupled-ground-solver-check` retains a short canonical comparison:
four host launches over 16 ns with RF off/on. Maximum host/reference state
differences are 2.25e-11/1.992e-10 V and the powered RF phase difference is
3.56e-15 cycles, below unchanged 1e-9 V/cycle gates. Both original and candidate
standalone banks reject a deliberate floor violation with time, capacitor states,
charge ledgers, drive state and energy ledgers unchanged. This supports a longer
candidate run after the current source-frozen RF test, not a full-chip speed or
quality claim; no acquired payload was used in these 16 ns comparisons.

## TMDS electrical and multi-die power budget

For the illustrative 8 mA / 50 ohm / 3.3 V DC sink model, one active lane draws
26.4 mW from its termination supply: 23.2 mW dissipates in the transmitter sink
and 3.2 mW in the receiver termination. Three lanes total 79.2 mW before clock,
PLL, host, bias and digital overhead. Source and sink may be on different boards;
do not charge the entire termination supply power to both chips. An external
clock-pair buffer adds separate power. This is a static hypothesis, not a complete
die budget. Preserve per-die 14 power/ground terminals and check common-mode,
current-source compliance, simultaneous switching and disabled termination loads.

[HDMI/DVI board and pin plan](../../../docs/roadmap/programmable-transceiver-pin-plan.md#hdmidvi-through-multiple-instances).

The video lane model now solves both 50-ohm terminated pad legs with exact RC
updates under complementary ideal 8 mA current sinks. A 2 pF per-leg candidate
passes the illustrative 100 mV signed sample-eye threshold with the declared
60 ps forwarded timing budget at both initial rates; a 30 pF load fails the
alternating-bit control. These are load-envelope assumptions, not validated
circuit parameters. Finite transistor output resistance, compliance, current
switching bandwidth, ESD and distributed cable/package effects remain absent.

The pad now optionally includes a first-order current-switch response before the
terminated RC load. Exact cascaded-exponential updates retain both leg voltages
and currents across bits, including the equal-pole limit. The independent
repeated-pole step response checks that limit. With 100 ps current settling,
2 pF per leg, 50 ohms and the fixed 60 ps early-sampling budget, alternating-bit
minimum signed samples are approximately 388 mV at 742.5 Mb/s and 211 mV at
1.485 Gb/s. A 1 ns switch time constant fails at both rates. The disturbed-PLL
pad check now uses the 100 ps candidate too; earlier ideal-switch amplitudes are
baseline comparisons, not its current results. Switching bandwidth is therefore
an explicit schematic target, not silently infinite. These time constants are
unvalidated hypotheses; transistor output resistance, current compliance,
parasitic feedthrough and voltage-dependent switching remain open.

Canonical DC-current-sink configuration now selects `CurrentSwitchChannel` in
place of the generic one-pole serial channel. The event-driven serializer advances
its two stored differential states (current and load voltage) with exact updates.
Unit drive means the assumed 8 mA / 50 ohm / 0.4 V differential output; default
switch and load time constants are both 100 ps. A ten-bit event-driven waveform
matches the independent two-leg pad calculation to numerical tolerance at both
video rates. Same-family reconfiguration preserves stored current and voltage.
This integrates differential settling only: legacy analog power bookkeeping is
not yet a DC TMDS termination/source-energy model, and mode-crossing common-mode
charge, compliance and supply coupling remain unqualified. Normalized state
continuity across different electrical families is not physical charge proof.

The canonical current-switch channel now retains tail-current and common-mode
load state alongside differential state. `pin_state()` exposes both pad voltages,
both sink currents, external termination-source power, resistor loss and sink
power. The nominal DC control converges to 3.3/2.9 V, 3.1 V common mode and
26.4 mW external source power, split into 3.2 mW termination loss and 23.2 mW
sink dissipation. A 0.4 V minimum sink-voltage hypothesis flags out-of-compliance
solutions; a lowered 0.5 V termination-supply control fails this check. This flag
does not implement transistor saturation or a hardware fault response.
Same-family local reconfiguration retains common and differential states.

Reported powers distinguish the external receiver termination supply from local
transmitter rails. Transient source-minus-loss power also changes pad capacitance
energy; only the settled DC conservation control is currently checked. Canonical
domain power bookkeeping is still the legacy approximation and must not be
mistaken for connected TMDS board/ground/thermal accounting. Receiver common-mode
input tolerance, hot-plug/ESD and nonlinear transistor compliance remain open.

Canonical TX power ownership now distinguishes DC current-sink mode from the
legacy voltage driver: it no longer debits remote termination power, divided by
a voltage-driver efficiency, from the local WIRE rail. The declared 2 mA local
bias remains; output sink dissipation is reported as externally supplied heat.
`wired_power_accounting()` separately exposes local bias power, remote termination
power, sink return current and termination/sink heat. Its coupling flags distinguish the installed return-node/compliance guard from
missing thermal and local RX termination supply integration. Internal switching charge is not characterized by the bias
placeholder. This correction removes a wrong supply attribution; it does not
establish total power or eliminate the external current's ground disturbance.

External TX sink return current is now an input to the existing linear and
current-limited host-bank ground-node solvers. The coupled analog owner evaluates
the held-command tail-current response during each interval, adds the return
current to ground KCL, and includes ground-voltage times injected current in its
source-energy ledger. This is power entering the modeled ground terminal, not
the remote termination's full source power or the transmitter's sink heat.
The canonical DC mode installs this callback; other electrical modes clear it.
A known 8 mA input satisfies independent KCL and raises the solved ground voltage;
a short paired analog-owner integration checks that domain rails respond.

This current-to-ground/rail coupling now rejects loss of pad compliance (below);
nonlinear current response and a joined termination-source/ground/sink transient
energy audit remain open. Thermal and RX termination supply coupling remain
open. Short owner windows do not establish acquired canonical video traffic.

Transient energy controls now cover both sides separately. Paired 1 ns analog
owner windows, with zero and 8 mA external return current, check nominal-feed plus
ground-terminal input energy against resistor/load losses and host/domain stored
energy (absolute residual below 1 aJ). The independent pad control integrates
termination-source, resistor and sink powers by 24-point Gauss quadrature over
turn-on, alternating symbols and turn-off. It compares each interval and the
whole sequence against explicit two-capacitor energy changes, with residuals
below 1e-22 J and a detectable stored-energy excursion. These verify bookkeeping
inside each reduced circuit; they do not yet join the remote termination,
voltage-dependent pad compliance and moving local ground into one closed system.

The shared-ground solve now checks predicted pad sink headroom at every analog
RHS evaluation. `pin_state(ground_v)` references compliance and sink heat to local
ground, and splits terminal power into local sink heat plus power transferred to
the return node. Loss of the assumed 0.4 V compliance aborts the analog step
without committing rail state/time. Tests cover nominal/raised-ground headroom,
terminal-power splitting and rejected-step preservation. This closes feedback
as a validity guard only: outside compliance, nonlinear sink saturation and
recovery are not modeled. Joined acquired traffic and transistor-derived voltage
limits remain open; a mathematical guard is not a hardware protection circuit.

### Dynamic RF supply sensitivity screen

The fast RF waveform path can apply sinusoidal rail ripple to receive gain and
integrate an effective LO supply-to-frequency sensitivity into mixer phase before
RX filtering. For ripple A*sin(2*pi*f*t), phase is K*A/f*(1-cos(2*pi*f*t)).
K is residual sensitivity at the disturbance frequency after any PLL/regulator
rejection, not raw VCO Kvco. A 50 mV peak, 1 MHz ripple gives HE20 fixture EVM
about 8.5/9.6/45.9% at K=0/1/10 MHz/V under current assumptions. Zero ripple
reproduces baseline exactly. These are probes, not measured GF180 sensitivities
or a validated PDN; actual coupling, rejection transfer functions and converter
reference modulation remain open. Common-phase pilot correction does not remove
fast within-symbol phase modulation.

### Host activity to RF disturbance

A fast coupling screen now uses the HOST switched-capacitance current law
(10 data outputs plus clock activity) to set a sinusoidal activity-envelope
current amplitude. An assumed shared-path fraction of 0.1 or 1 drives a series
R/L feed with local shunt C, whose load impedance is
`Z=(R+j*w*L)/(1+j*w*C*(R+j*w*L))`. The example R=2 ohm, L=5 nH, C=1 nF
is an uncertainty probe, not an extracted package or allocated on-die capacitor.
At 1 MHz the two coupling fractions give about 5/50 mV peak ripple and roughly
9.6/45% HE20 EVM with assumed residual LO sensitivity 10 MHz/V.
The sinusoidal envelope is not a measured host switching spectrum. Separate
rails do not alone prove isolation; shared return, regulator transfer and
board/package impedance must ultimately constrain the effective coupling.
