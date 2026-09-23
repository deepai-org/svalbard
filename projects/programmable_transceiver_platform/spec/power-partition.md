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
