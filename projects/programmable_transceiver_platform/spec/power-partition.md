# Whole-chip power and resource allocation

The [analog inventory](analog-architecture.json) owns selected per-block
area/current ceilings, supply connections, decoupling and memory allocations.
The [normative architecture](block-diagram.md#selected-resource-allocation)
summarizes those selections and its generated connection table identifies every
power consumer. These allocations are requirements to implement, not evidence
of physical performance.

Board bulk capacitance supplements, rather than replaces, the local supply and
reference allocations. [Implementation ownership](block-diagram.md#silicon-fpga-and-board-allocation)
keeps sensitive feedback nodes local and calibration computation on the FPGA;
no speculative offloading savings are deducted from these ceilings.

## Provisional implementation allocation

### One physical operating envelope

Accept a mode only when its pad loading, source impedance, supply/return
network, clock sensitivity, converter performance and host switching describe
the same configuration. Do not combine minimum loading from one board with
maximum drive or minimum noise from another. External clocks remove source
synthesis obligations, not input-buffer, distribution or supply-induced jitter.

Retain provider-compatible bond positions and common returns. Carry package
R/L/C and coupling as explicit uncertainty ranges through rail ripple, clock
phase error and payload quality. The provisional 0.25 nH return target is not
a characterized package bound. Decoupling must include ESR/ESL and placement;
extra ideal capacitance alone cannot qualify the assembly.

Converter admission requires effective accuracy at the actual amplitude and
sample rate, with reference settling, acquisition, distortion and clock error
included. Ten-bit words do not imply ten effective bits. Area/current totals
include inactive branch loading, retained warm clocks, support circuits and
the simultaneous wired TX/RX case; RF/wired exclusivity saves active power,
not fabricated area. Check local headroom and transient current as well as
average current. A numerical allocation is a circuit requirement, not evidence
that GF180 can implement it.

Device-terminal stress is a separate constraint from nominal supply voltage.
The [GF180 operating-condition rules](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html)
require checking gate/node and drain stresses, including mixed-supply and
bidirectional pass-device operation. Consequently, a nominal 3.3 V pad or a
disabled branch does not establish safe stress when its local supply is zero.
The selected wired-pad protection/isolation must cover that state explicitly;
the PDK voltage rules do not establish an RF bandwidth or protection solution.

The next physical-feasibility decision must use a common bounded envelope for
the shared-pad, host-service, CDR and RF cases. If none fits, change the offending
branch, board loading or timing route explicitly and rerun affected cases;
do not promote independently favorable block results to a whole-chip verdict.

The design retains 2.51 mm² wired, 2.40 mm² RF, 1.30 mm² converters, 1.60 mm² timing,
1.65 mm² digital and 0.85 mm² memory. Of the 2.61 mm² support reserve,
1.30 mm² is now assigned to power distribution and 1 nF supply decoupling;
1.31 mm² remains reserve. The core ceiling remains 12.92 mm². Every fabricated
block retains its area even when inactive. The separate 100 pF reference
reservoir is charged to the 0.150 mm² reference-buffer allocation.

At the previously documented 0.9 fF/µm² planning density, 1 nF requires
1.111 mm² of capacitor plates before routing. Thus the earlier 1.00 mm²
allocation was insufficient; the design reserves 1.30 mm². No capacitor geometry or
extracted impedance is claimed by this allocation.

The current ledger is source-specific. The primary external RF clock replaces
RFPLL12mA with0.1mA using the existing source override; external input,
quadrature/distribution and all warm analog loads remain charged. Each DAC now
reserves2mA:1mA steering plus1mA provisional local support (0.25mA static,
0.75mA switching). At3.3V/40MS/s the switching allowance corresponds to5.68pF
activity-weighted capacitance; this is a design limit, not extracted capacitance.

| RF configuration | Allocated current | Margin to unchanged240mA ceiling |
|---|---|---|
| External clock, selected five-pole filters at4mA each | 240mA | 0mA |
| Autonomous clock, selected five-pole filters | 251.9mA | −11.9mA |

**Keep the external-clock route as the primary qualification path.** Its
allocation now reserves4mA per TX filter, consuming the former
6mA after the paired RX filters increased to8mA. Both RX and TX keep their
warm-path allocations. Do not fund the selected design from unqualified host-current
savings or treat zero total margin as physical closure. Autonomous synthesis remains a separate capability requiring an explicit
current saving or separately qualified envelope; its deficit is not hidden by
external-clock credit. Wired/USB totals remain272.45/252.2mA.
`architecture_fast/rf_quality_budget.py` reports these cases and per-rail loads:
external-clock allocation PLL32.3,CONV23,CORE20,RF53,WIRE1.6,HOST110.1mA.
The RF rail increases6mA while PLL savings occur on a different rail; total
margin does not prove local ripple, startup or thermal feasibility. All block
allocations, including DAC support and filter bias, remain implementation
hypotheses to carry into the joined supply model.

The retained mathematical fixtures use earlier 240/292/246 mA whole-mode
ceilings and, in some cases, older lower-current assumptions. Their CORE/PLL
converter ownership is historical. The design requires rerunning the joined supply
model with explicit branch loading before its operating envelope is qualified;
recorded waveform evidence is not silently relabeled. The old allocation table
has been replaced by the single per-block inventory to avoid competing defaults.

### Supporting-circuit audit

`architecture_fast.rf_quality_budget.support_budget_audit` recomputes the
following limits from the current inventory. These are allocation deductions,
not bottom-up transistor estimates. No block has earned its budget merely by
being assigned to it.

| Supporting circuitry | Existing allocation owner | Coupled acceptance obligation |
|---|---|---|
| RF/reference/wired protection and power-off isolation | Respective pad blocks; rxselect/rxlevel for internal selection/level conversion | Pad capacitance, inactive leakage, switch resistance, clamp window and device stress together; no separate invisible ESD area |
| Clock input, quadrature, fanout and reset release | refinput, quadrature, clocktree and source PLLs | Include every receiver gate, wire and sampling load, static bias, clock slew and additive jitter at actual carrier rate |
| Bias, reference generation/distribution and reservoirs | bias and refbuf; local reference loads remain in consumer blocks | Startup, source/sink recharge, noise, headroom, routing and common-mode feedback; shared source does not eliminate local buffer cost |
| Coarse POR, supply monitors, management oscillator and reset/isolation controls | monitor, aosc, digital; local fail-safe devices in each affected block | Startup before precision reference, partial power and asynchronous assertion; distinguish always-on bias from active switching |
| Trim banks and switched coefficients | Respective filter/PGA/clock/converter blocks; control storage in memory ledger | Switch parasitics and resistor/capacitor bank area remain in the analog owner; register bits alone are not the trim circuitry |
| ADC diagnostic selection | adc_i/adc_q; four control bits with active/shadow storage | Added input/CDAC loading, charge injection, leakage and routing must fit ADC timing and accuracy; no extra precision source assumed |
| Host pads, gearbox, CDC and diagnostics | hostio, digital and named memory allocations | Actual load/slew, per-bank current, internal word rate and continuous queue service; no free synchronous CDC |

At the assigned 0.9 fF/µm² density, the 100 pF reference reservoir consumes
0.1111 mm² of refbuf's 0.1500 mm², leaving at most **0.0389 mm²** for everything
else. The 1 nF supply plates leave **0.1889 mm²** of the 1.30 mm² power allocation
for routing/support overhead. Both exclude any unmodeled layout inefficiency.
Memory allocations now total **7,818 bits**, leaving **374 bits** under the
8,192-bit cap; this is not a placed-memory area result. The periodic controller
adds 448 coefficient bits, 256 control-state bits and two enable bits. Its
1280-byte observation history belongs to the FPGA; pending coefficient commands
reuse ingress storage. The selected 98-sampler tracking bank and encoder still
need new physical current/loading/area estimates; inherited analog allocations
are not evidence that they fit.

ADC acquisition/decision/reset allocations sum to **25 ns**: zero cycle margin
at the nominal 40 MS/s ceiling, and **0.6 ns** at 2.500 GHz /64. Include test
switch loading and clock uncertainty before accepting either point; do not
silently extend the sample period for a passing converter fixture.

The selected ADC now reserves0.2ns for cycle uncertainty not already represented
in sample-edge timestamps, leaving0.4ns at the maximum direct-LO rate. Diagnostic
selection is allocated50fF added sampling-node capacitance and100ohm added
series resistance per leg. These are acceptance requirements, not measured
switch parameters. `converter_dynamics.parameters_from_inventory` applies them
to the actual SAR acquisition equations and schedule admission. The old25ns
schedule cannot qualify40MS/s with this guard; that ceiling requires a faster
qualified schedule. No advertised direct-LO channel/sample rate is removed.

`selected_revision_check.py --common-envelope` uses the same package catalog,
selected6pF external host load and inventory currents for RF and wired. Host
capacitance propagates through both the original spectrum and partitioned
delivered-clock network; internal output-cell charge remains a separate
assumption. Current is preserved through the downstream DC network reduction.
Accepted clock cases feed paired SAR/reference-recharge feedback with diagnostic
loading, and an independently recovering wired CDR with ordinary and
transition-drought stimuli. This is a common electrical environment, not a
single integrated protocol lifecycle or full RF packet qualification.

The present converter experiment is512 samples of a9.689MHz tone at39.0625MS/s,
with256 scored samples after guards. Its fitted-fundamental effective-bit result
does not establish broadband accuracy or calibration validity. The wired
experiment scores1200 held-out bits per phase/offset case. Record timing-valid
continuity separately from decoded errors; zero errors can accompany lost
qualification. Full SSC cycles, real SDI pathological sequences, nonlinear
shared-pad operation and complete fault/recovery remain required.

For perspective only, allocating all current to full-swing switching at 3.3 V
and 2.5 GHz gives aggregate C-equivalent ceilings of **1.455 pF** for each
12 mA input/distribution block and **0.606 pF** for the 5 mA quadrature block.
Real static bias reduces this allowance; current-mode circuitry needs its own
swing/load calculation. This is a warning about fanout cost, not a transistor
capacitance prediction or proof that current-mode operation fails.

**Audit verdict:** support circuitry has owners, but sub-block implementation
costs remain unestimated. The 1.31 mm² unassigned reserve must not be counted
again inside owner ceilings; the five-pole TX candidate would consume 0.46 mm²
of it. Primary RF has 10 mA allocated margin, or only 4 mA with that candidate.
Unknown protection, reset, trim and routing costs cannot be declared zero.
The next sizing pass must break down these owners before claiming physical fit.

### Selected supply and host implementation requirements

The contract owns `power.mitigation_policy` and `physical_services.host_output`.
Keep external regulation on provider-compatible feeds with common return; no
mandatory on-chip regulator, extra power pin or independent quiet rail is assumed.
Select **6 pF maximum external D2H load per data/clock pin** for full-rate
312.5 Mword/s service. Include FPGA input and board/connector load; count die-pad
capacitance separately exactly once after resolving the characterization convention.
This requires a short point-to-point board, not arbitrary FPGA-board compatibility.
Existing 10 pF waveforms remain heavier-load controls, not evidence at 6 pF.

| Disturbance | Required treatment | Unjustified shortcut |
|---|---|---|
| Upstream source | Regulator/filter transfer, output impedance and own noise before package | Ideal quiet die supply |
| Host/converter/timing current | Full feed/return impedance, storage and any active loop | Apply upstream PSRR to locally generated ripple |
| Shared return | Common impedance and differential/common-mode conversion | Separate supply regulators eliminate ground bounce |

The fixed 1 nF host-network comparison already has zero upstream source ripple.
At native-library H2D internal charge, its separate forcing terms produce:

| Forcing term | HOST_A / RF / timing peak magnitudes |
|---|---|
| D2H external-load charging | 278.1 / 20.2 / 38.2 mV |
| D2H internal switching, assigned 7 pC | 626.2 / 45.2 / 92.3 mV |
| H2D internal switching | 67.9 / 4.12 / 9.17 mV |
| H2D external pad return | 82.2 / 30.3 / 64.3 mV |

Complex responses sum before extrema, with superposition residual below 4.5e-16 V.
Separate peaks are neither simultaneous nor single-tone limits. Assigned current
kernel, bank-scaled ESL and high-frequency lumped extrapolation remain unqualified;
converter/timing switching is absent. Do not equate these broadband peaks to the
10 MHz ripple target below. Better upstream PSRR alone cannot remove these terms;
a changed source output impedance must be modeled explicitly.

The pinned [GF180 bi_t TT 3.3 V / 25 C Liberty data](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_io/blob/2aeec51ea2824b6cc0b396acfc39f4535f40b23a/cells/bi_t/gf180mcu_fd_io__bi_t__tt_025C_3v30.lib)
gives 7.69–14.43 pC equivalent internal transition charge at 10 pF across eight
conditional PAD A-driven settings and three input slews. Sum signed rise/fall
cycle energy and divide by twice supply voltage; external charging stays separate.
The unconditional fallback is not another simultaneous contribution. Input-cell
energy cannot validate output-driver energy. The former 7 pC remains an optimistic
custom-driver hypothesis, not a conservative stock-cell bound.

Matched timing/current comparisons are:

| External load; PDRV0/PDRV1/SL | HOST_A / HOST_B, full-rate alternating | Maximum rising transition, conservative timing query |
|---|---:|---:|
| 10 pF; 0/0/0 | 41.95 / 49.94 mA | 5.16 ns |
| 10 pF; 1/0/0 | 45.47 / 54.17 mA | 2.63 ns |
| 10 pF; 1/1/0 | 52.27 / 62.33 mA | 1.40 ns |
| 6 pF; 0/1/0 | 38.59 / 45.90 mA | 1.30 ns |
| 6 pF; 1/1/0 | 41.87 / 49.85 mA | 1.03 ns |

Each HOST bank has a 55 mA ceiling. Accounting includes alternating 312.5 Mword/s
H2D using the input-library including-Y-load upper scenario, the same-setting
maximum listed output energy, external charging once and existing 2 mA other
allowance per bank. These terms occupy the HOST reservation, not add to it. The
older 1.25 screening multiplier is not applied; this is raw mean current only.
Timing queries conservatively add listed PAD capacitance 2.977816 pF because its
axis differs from the power axis; both interpretations remain in the evidence.
This ambiguity is not resolved by the calculation. Transition is not a current
pulse width or a complete FPGA capture eye; propagation delay is not a rate limit.

**Decision:** retain configurable strength/slew and full-rate host service, with
6 pF as the selected board target. At 10 pF, the fastest stock setting exceeds
the clock-bank ceiling; the lowest-energy setting has inadequate demonstrated
transition margin against a 3.2 ns word interval. Do not mix the cheapest energy
with fastest timing, substitute random-average traffic, raise budgets silently,
or assume custom-driver savings. At 6 pF, two faster settings provide credible
candidate points within mean-current ceilings without extra pins or regulators.
Final cell choice, board load, FPGA eye, PVT, peak/EM, current-pulse shape and
VDD/DVDD ownership remain open. Stop nominal table expansion; return to joint
host/package and RF/wired quality decisions.

Reproduce with `selected_revision_check.py --host-output-source-evidence` and
`--host-energy-comparison`. Their respective `host_output_library_evidence` and
`host_receiver_energy_comparison` sections in `selected-revision-check.json`
retain source tables, source hashes and scope. Public characterization is not
measured silicon or qualification of custom output circuitry.

The matched `--host-selected-load` package comparison prevents confusing that
mean-current result with a noise improvement. At fixed RF-mode D2H 150 Mword/s,
H2D 312.5 Mword/s and the historical 1 nF network, sampled absolute ripple peaks
are:

| Output hypothesis | HOST_A / RF / timing peak magnitudes |
|---|---|
| Historical 10 pF, 7 pC internal | 1.054 V / 90.6 mV / 204.0 mV |
| 6 pF, PDRV01/SL0 energy 12.27 pC | 1.531 V / 131.7 mV / 276.8 mV |
| 6 pF, PDRV11/SL0 energy 14.37 pC | 1.719 V / 145.3 mV / 304.6 mV |

**Decision:** keep 6 pF for the matched host timing/current requirement, but do
not credit it as package-noise mitigation. Higher internal energy outweighs the
external charging reduction in this fixed hypothesis. These are ripple deltas,
not absolute supply voltages or measured bounds. The 10 mA charging law, 0.5 ns
internal pulse and 100 ps smoothing remain assigned; Liberty transitions do not
validate those current shapes. Neither the selected 500 pF reservoir, full-rate
wired host forcing nor arbitrary phase is qualified by this 1 nF comparison.
Evidence: `selected-revision-check.json:selected_host_load_package_comparison`.
The architectural gate remains actual host current delivery/shared return and
analog sensitivity; do not select a driver from mean-current fit alone or keep
sweeping guessed edge times into a pass.

The bounded `--host-loop-topology` comparison identifies one dominant network
assumption. The old model scales local capacitor ESL inversely with capacitance
fraction, assigning each 60 pF host bank 3.33 nH in the 1 nF comparison. Replacing
that rule with explicit 0.2 nH per local capacitor loop, while retaining the same
capacitance, ESR, branch inductance, common return and 6 pF/PDRV01 forcing, changes
HOST_A/RF/timing peak magnitudes from 1.531 V/131.7 mV/276.8 mV to
0.613 V/81.8 mV/117.5 mV. The reduced impedance is independently checked against
an explicit nine-node circuit for both loop interpretations and external-return
forcing; that verifies the equations, not the geometry.

**Decision:** local reservoir return-loop geometry is a first-order uncertainty.
Do not treat inverse-capacitance ESL scaling as a physical law or use its rejected
waveform as evidence of architectural impossibility. Conversely, do not select
0.2 nH per loop as measured or proven achievable: it changes aggregate inductance
and requires distinct short physical return paths. Neither case qualifies the
supply envelope. Keep both recorded topologies and stop numerical ESL tuning;
price/justify a concrete local reservoir connection within provider ground sites
and area, then feed its impedance into the common RF/wired model. Evidence:
`selected-revision-check.json:host_loop_topology_comparison`.

### Timing and signal-quality allocations for the selected blocks

The connected shared-stress inverse calculation in
[risk priorities](risk-priorities.md) now constrains supply/timing requirements
jointly: at 0.1 ps/mV, a 60 mV peak 10 MHz disturbance translates a +12 MHz
blocker into the wanted band. Its illustrative 5% incremental allowance implies
about 9.62 mV peak for the conservative small-signal AM+PM sum under that case.
This is an inverse requirement, not a package-derived ripple limit or a selected
physical regulator/filter design. Keep its budget separate from total EVM until
the capability acceptance allocation is reconciled.

**Mitigation choice:** prioritize reduction of the shared disturbance reaching
both gain and timing paths. A cleaner external clock alone is insufficient for
this diagnostic: even ideal timing leaves a 5.76% translated AM sideband against
the 5% branch allocation. The unchanged AM+PM first-order bound would require
15.90 dB additional blocker rejection before mixing, rather than the 14.12 dB
PM-only estimate. That rejection is relative to wanted-signal transmission;
insertion loss and its sensitivity cost must also be included. A blocker only
12 MHz away makes narrow preselection a conditional option for wideband modes,
not a universally available external-passive fix.

Keep three implementation routes for comparison: external low-impedance supply
and return control; local isolation/regulation with priced dropout/current/area;
and configuration-dependent preselection combined with timing improvement.
None is yet selected as a physical circuit or credited as measured attenuation.
The first two must meet a common gain/timing ripple requirement, not merely
reduce source phase noise. The third must preserve wanted bandwidth and meet
sensitivity/blocker requirements together. The 9.62 mV value is a necessary
planning target within the stated first-order diagnostic, not a sufficient
whole-chain EVM or PER guarantee. Reproduce these deductions with
`selected_lifecycle.py --supply-requirement`; do not tune package guesses until
they happen to produce that voltage.

**Passive isolation budget:** the same inverse screen now checks an optimistic
one-pole RC filter for the entire 44 mA RF or 47 mA timing/reference owner.
Even granting either candidate the entire 500 pF reservoir separately, attenuation
from 60 to 9.62 mV at 10 MHz requires about 196 ohms: its constant-current DC drop
would be 8.63 or 9.21 V. This is an infeasibility calculation, not a predicted
negative operating voltage. With a favorable 3.267 V input and 2.5 V load floor,
capacitance would need at least 5.62 or 6.01 nF before parasitics. The 2.5 V floor
is borrowed from the converter model and does not qualify the clock circuitry.
Reject this whole-domain series-R/500-pF solution. This does not reject small
low-current subcircuit RC filters, external capacitors, or active regulation;
each has different load, package, dropout and stability obligations. Keep external
supply/return improvement first, and price active local isolation before adopting it.
No new capacitance, regulator or current savings is added to the baseline.

**Joined-path check of the ripple target:** `selected_lifecycle.py
--ripple-envelope` holds source offset at −33 mV, timing sensitivity at four
times the selected value, frequency at 10 MHz, and all traffic/settings fixed.
It varies only shared ripple amplitude through the seven-stage RF/wired lifecycle.

| Ripple peak | RF RX EVM over three stages | RF TX EVM before/after recovery | RX held-out errors per stage |
|---|---|---|---|
| 0 mV | 5.28–5.33% | 3.67% | 0 / 468 |
| 9.6 mV | 7.25–9.02% | 3.93–3.96% | 0 / 468 |
| 60 mV | 19.93–25.75% | 9.65–9.82% | 2 / 468 |

All cases complete the scoped lifecycle. Wired TX has zero errors in 1,300
held-out bits; wired RX has zero errors in 6,050 held-out delivered bits and only
the deliberately induced transition-drought qualification loss. This supports
shared-ripple reduction as useful without changing the signal architecture.
It does not establish 9.6 mV as sufficient for every RF modulation: residual RX
EVM exceeds the illustrative 5% *incremental branch* allocation, which is not a
total EVM limit, and the zero-ripple path itself remains near 5.3%. The comparison
uses HE20 DATA with known training and low TX amplitude, not packet acquisition,
PER, emissions or the 0 dBm output goal. Do not convert finite error-free bits into
a BER bound. No attenuation hardware, regulator cost or continuous frequency/phase
envelope is demonstrated. Stop refining this three-point diagnostic; next qualify
a physical supply alternative against the common resource ledger and target-level
quality requirements. Evidence: `selected-lifecycle.json:joined_ripple_envelope`.
Its recorded stress prose still says 60 mV in all rows; the numeric
`ripple_peak_v` is authoritative. Future runs use corrected amplitude-neutral prose.

Use one set of numerical requirements in the next model revision. These are
initial design allocations with identified owners, not measured limits or
protocol-compliance claims. Target-specific packet and electrical criteria
remain additional acceptance obligations.

| Owner / event | Initial allowance | Interpretation |
|---|---|---|
| External RF timing path | Existing −115 dBc/Hz at 100 kHz source point with −145 dBc/Hz floor; input noise 75 uV RMS and two downstream stages at 15 fs RMS each over 1 kHz–8 MHz | Reuse the combined high-impedance clock requirement point, including input loading and coherent supply effects. This is a demanding assigned spectrum, not a purchased source or GF180 noise prediction. |
| Wired sample/launch timing | 5 ps RMS random-timing study point at 2.5 Gb/s; preserve the existing 0.05 UI plus seven-sigma eye allowance as a diagnostic screen | Random jitter does not replace CDR tracking, deterministic jitter, pad/channel loss or target-specific masks. |
| ADC acquisition and decisions | At 38.8125 MS/s, 25.765 ns period: allocate 3 ns acquisition, 20 ns for ten SAR decisions, 2 ns reset/control, leaving about 0.765 ns. Allocate the ten bit intervals as 3.2/2.8/2.6/2.3/2.1/1.8/1.5/1.3/1.2/1.2 ns, including 0.7 ns comparator time each. | Spend more settling time on large DAC steps without increasing conversion time. These are circuit timing targets, not a qualified sequencer or arbitrary-resolution programmable delay. Interleaving remains the costed fallback. |
| Converter aperture | 10 ps RMS added sampling uncertainty allocation at the converter, separate from the much tighter RF LO path | At the existing 9.53125 MHz outer tone this contributes about 0.060% small-error RMS EVM. Preserve correlation with common clocks when present. |
| RX channel filtering / AGC | Existing 1 dB passband-loss investigation allocation through ±9.53125 MHz; retain 0.2 us gain-settling and 2 us command-service study points | Finite-zero group delay and real training are included in acquisition; these numbers do not authorize extra preamble symbols. |
| Same-channel RF changeover | Initial 2 us analog-readiness allowance, with clocks/reference retained and TX prefilled | Includes bias/output/filter settling actually required by the selected state transition. Overall protocol deadline also includes FPGA work, observation latency and calibrated air timing. |
| Timed generic pad action | Selected 76.8 ns H0 command service (H2D clock divided by four) plus at most one 64-word boundary wait; prearm exact launches | Some protocol events need the separate faster electrical path. SPI alone is not the selected packet-response mechanism; validate those cases through the existing short-frame bridge. |
| Host queues / clocks | 59/64 payload schedule, independent ±100 ppm study margins, bounded chip queues and explicit underflow mute | No finite queue permits unbounded rate error. Preserve source-clock-derived pacing or qualified feedback and independent recovery when clocks stop. |

These allocations deliberately expose the difficult decisions: short late SAR
steps, quiet RF phase distribution, high-Q filtering and bounded host service.
They give the next mathematical model requirements to meet; exact transistor
sizes and extracted parasitics are later work. The existing reports use their
recorded settings and are not relabeled as passing this entire table.

### First selected-baseline electrical result

Run `python3 verification/baseline_envelope.py` from the project directory. This
fast entry point reuses the existing network and timing functions but replaces
the legacy DC load with the selected 236/288 mA mode budget. It writes
[evidence/selected-baseline.json](../evidence/selected-baseline.json), separately
from historical fixture evidence. H2D internal current is charged once within
HOST, physically injected at the local node; the 40 mA timing reservation already
includes switching. No extra C·V·f term is added to it.

At a nominal 3.3 V board source, the selected 500 pF / 0.5-ohm ESR / 200 pH ESL
reservoir and 0.5 nH shared return give coherent sampled local-rail ranges of
approximately **2.882–3.052 V for RF** over the two LO endpoints and
**2.787–2.925 V for wired** at 2.5 Gb/s. The first sums of tone amplitudes were
more conservative; the report retains both and adds a derivative-based enclosure
between sample points. Nominal supply-induced delay is about 3.56–3.58 ps RMS
for RF and 3.74 ps for wired under the assigned delay transfer. These coherent
tones are not independently random jitter and must enter the actual eye/RF model.

An uncertainty probe with 2 nH return and 1 nH local-capacitor ESL produces an
actual sampled wired minimum of **2.489 V**, below the old fixture's 2.5 V
validity floor, with 9.30 ps RMS host-induced delay. This is a counterexample
within an assigned network hypothesis, not evidence of a measured package
excursion or an asserted maximum parasitic value. It prevents claiming that
local capacitance alone makes the selected architecture insensitive to assembly.

**Decision:** retain the selected network but require its effective return and
reservoir impedance to be bounded, or change damping/host activity before a
whole-chip pass. Continue integrating the selected converters, filtering and
loaded RF/wired paths; do not count this electrical screen as complete baseline
verification. Board-source ±1% cases currently vary DC only. Missing converter/
core switching spectra, current versus voltage, nonlinear input behavior and
thermal control remain explicit. The 27 °C junction target is not established by
setting a noise-model temperature.

The same baseline report now feeds the delivered source/input/supply timing
into the existing causal wired receiver at 2.5 Gb/s, with a 100 ps driver pole
and 2.7 pF effective load (including the assigned disabled-branch/mutual terms).
It evaluates the rail at each actual displaced receiver observation. An assigned
local signal-gain sensitivity proportional to rail voltage couples the voltage
variation into the samples; this is not a measured CTLE law or a claim that a
remote transmitter follows our supply.

In the earlier unequalized control, across initial phase ±0.35 UI and clock
error ±100 ppm, the selected network has zero errors in each 1,200-bit held-out interval and about 190 mV minimum
signed sample margin. The higher-inductance probe also has zero errors and
about 153 mV margin, but 149–150 receiver observations per case lie below the
legacy 2.5 V floor (minimum about 2.488 V). Those cases are **not qualified**.
Voltage-validity diagnostics persist through the receiver's forecast/consume
snapshots, so decoding cannot erase an out-of-domain observation.

The selected receiver now includes the CTLE setting and generic recovery test
below; the unequalized eye figures above remain a control. Neither establishes
PCIe/USB/SATA startup, sustained BER or complete wired qualification.
Current-steering TX compliance, physical CTLE gain,
independent remote-source impairments and protocol-specific electrical states
remain to be joined. The controller sees only observed voltage/timing; source
bits are used only for the external scoreboard and separate fixed-lag training.

### Wired equalization, host delivery and recovery

The `wired_recovery` section of the selected-baseline report connects the same
288 mA power allocation, 2.7 pF load, 100 ps driver pole, delivered timing and
rail-dependent local gain to the existing persistent CDR, ordered raw/status
transport, bounded queues and FPGA marker framing. Host and line clocks have
opposing ±100 ppm errors. Publication uses H2D clock divided by four
(nominally 39.0625 MHz), including the host ppm error, instead of the legacy
40 MHz service assumption. The fixture interrupts host/publication clocks while
CDR continues, explicitly flushes/retrains, and exercises line gaps of 0, 1,000
and 10,000 bits. All delivered frames must match source payloads in order;
source payloads are unavailable to the receiver/controller. Terminal source
level is held continuously after the finite stimulus, without resetting filters.

The corrected shared-rail version includes REF_IN loading and its returned
carrier while preserving independent RX CDR timing. At the current 0.25 nH
target, unequalized readiness transitions overflow the fixed raw/status queue
at about 3.58–3.82 us. The 0.5 and 2 nH cases fail the TX reference-clock gate
before the full-duplex lifecycle; their RX-only capability is not assessed by
that gate.
Increasing storage or relaxing readiness criteria is not the chosen remedy.

**Selected requirement:** include the already-planned tunable CTLE, starting
from unity DC gain, a 200 ps zero (about 796 MHz) and an 80 ps pole (about
1.99 GHz), giving 2.5× asymptotic gain (about 8 dB). Its transfer is evaluated
with continuous physical-time channel state, independently checked against a
state-space solution. The existing 10 mV RMS output-noise and 20 mV offset
hypotheses remain requirements **after** equalization; this is not evidence
that a GF180 equalizer provides the bandwidth, noise, swing or current together.
Its consumption must fit the existing wired allocation, with no extra free stage.

The selected retained-lifecycle adapter now explicitly uses these same settings
from `contract.json:physical_services.wired_receiver`. Its initial unequalized
adapter was a composition omission and is retained only as a control. With the
selected CTLE, the joined 2.5 Gb/s compliance-pattern case has no qualification
loss outside its injected transition drought, at the original noise/offset and
unchanged lock criterion. This aligns two model compositions; it does not add an
extra equalizer or qualify physical implementation. `risk-priorities.md` owns
the current joined result and loss/recovery boundary.

With that setting, both current-package clock corners meet the unchanged
delivery minimum through the gap/restart lifecycle. The weaker 150 ps zero /
80 ps pole control also meets it under the corrected shared environment;
retain both controls without treating either as a physical equalizer proof.

The separate `wired_transmit` campaign sends nonuniform bit boundaries from
the corrected delivered clock through the driver/channel/CTLE model to an
independent peer CDR. Channel state integrates the actual interval between
transitions; TX phase is not copied into the peer sampling clock. At the current
target, centered TX edge variation is about 11.12 ps RMS and the shortest UI is
368.3 ps at nominal 2.5 Gb/s. Four initial phase/ppm cases each produce zero
errors in 1,200 held-out bits, but readiness holds for only 29.25–53% of that
interval and all finish unqualified. With ideal TX timing and the same rail,
channel, noise and CTLE assumptions, all four remain qualified throughout.
This is a transmitter-timing/peer-readiness failure despite good sampled voltage
margin, not a statistical BER result or protocol-compliance verdict. Serializer
logic, output-current feedback, real cable behavior and pad nonlinearity remain
unverified. Focused runs establish these results; the full artifact must be
regenerated to include the new transmit campaign.

The readiness rule requires all 64 recent detected transitions to have loop
error below 0.1 UI (40 ps here); it is an assigned peer-model rule, not a
protocol mask. The baseline's final windows reach 0.116–0.120 UI. Raising the
external Thevenin source peak to 0.75 V reduces centered TX edge variation to
7.40 ps RMS and final-window maxima to 0.084–0.088 UI; all four cases remain
qualified across the held-out interval with zero errors. At 1.0 V, variation
is 5.78 ps RMS and those short cases also pass. This is the same source-swing
mitigation that helps RF, with no readiness relaxation. It is package-dependent:
at 0.5 nH, 0.75 V admits the TX clock but still fails continuous peer readiness,
while 1.0 V is rejected at the clock gate. The 2 nH probe rejects every swing.
Keep the 0.5 V baseline failure and the full source-current/loading cost; these
controls do not qualify bias/protection, serializer timing, BER or all peers.

The finite TX transport is now connected to actual word-consumption events
from that clock, using the existing exclusive 59/64 schedule, 2,048-bit queue,
1,024-bit prefill, eight-word staging and 40 MHz CDC. At both ±100 ppm host
service offsets, a 104.8576 µs focused run emits 262,140 correct bits without a
transport fault; minimum queued data is 94/84 bits. Stopping observed pacing
edges at 5 µs instead produces underflow at about 5.412 µs with a correct
emitted prefix. This tests logical underflow, not pad muting or recovery.
Chunked and uninterrupted execution agree in the focused checks.

Only the first 2,600 emitted bits are propagated through the peer channel/CDR;
do not extend its 1,200-bit scored interval to the entire transport run. The
stream starts at an absolute clock/rail phase 4 ns later than the direct-source
control, after an assumed 20 µs startup. At the current package target, the
0.5 V source then has 11–21.3% peer readiness, and **0.75 V has only 69.3–80%**,
despite zero held-out bit errors. At 1.0 V these short windows remain qualified.
A paired launch-phase check reproduces the 0.75 V difference without transport:
0 and 20 µs origins pass, while 4 ns and 20.004 µs origins give the same reduced
readiness. The earlier favorable launch window therefore does not qualify the
stronger source across host/clock phases. At 0.5 nH, the admitted 0.75 V clock
still has only 7.5–7.7% readiness in this window; rejected clocks remain rejected.

The TX amplitude placement is now corrected: NRZ drive is multiplied by the
continuous rail waveform **before** the driver pole, load pole and CTLE. Their
states persist across actual bit boundaries. Sinusoidal particular solutions
and homogeneous transitions avoid a GHz integration grid. Independent real
augmented-state calculations, a frequency-response check and the constant-rail
limit verify this implementation, including nearly coincident poles. The
rail/drive coefficient is still assigned; this does not establish nonlinear
driver behavior, output-current feedback or physical headroom.

The corrected model retains the launch-phase failure. The current package
target now exercises all eight even-bit launch phases visited by ten-bit words
against the nominal /16 host physical clock. Each has four peer phase/ppm
corners and 1,200 held-out bits:

| External source peak | Continuously qualified corners | Lowest readiness fraction | Periodic-clock controls at the same mean delay |
|---|---|---|---|
| 0.5 V baseline | 0 / 32 | 11.0% | 32 / 32 qualified |
| 0.75 V candidate | 9 / 32 | 68.6% | 32 / 32 qualified |
| 1.0 V candidate | 22 / 32 | 80.4% | 32 / 32 qualified |

All these short data observations still have zero errors. The controls retain
the same data, rail forcing, channel, noise, mean clock delay and readiness
rule, removing only varying TX edge error. Thus varying delivered timing is
necessary for these modeled readiness failures; the comparison does not isolate
source, input or downstream supply sensitivity as its unique cause. Neither
stronger source is a complete wired remedy, despite its favorable first window.
Do not relax readiness or change the baseline to hide this result.

The host ppm control still changes data service while interference harmonics
remain nominal. This discrete phase grid is not continuous or asynchronous
phase coverage. The next timing requirement must cover waveform/phase dependence
and peer recovery, not only aggregate RMS jitter or one preferred launch instant.
These focused results follow the last complete report snapshot; source hashes
identify that older snapshot until the full artifact is regenerated.

The higher-inductance probe still overflows even with the selected CTLE, and
its rail leaves the legacy validity interval. It remains rejected. The fixture
uses generic markers and synthetic reference-presence/watchdog events, not real
SATA ALIGN, PCIe LTSSM or a validated physical clock monitor. The 128-record
source queue is an existing diagnostic allocation, not closure of the complete
8,192-bit on-chip storage inventory. The next gate is to carry the same analog
conditions through protocol-specific electrical actions and duplex operation.

### USB static output voltage and return-path gate

The new `usb_static_voltage` section tests a necessary USB electrical condition
under the same loaded PDN and worst-rate host harmonic stimulus. The original
[USB 2.0 specification, §7.1.1 and Table 7-7](https://www.seriesten.org/docs/protocols/USB_2.0_Specification.pdf)
requires a driven high above 2.8 V into 15 kohm and a driven low below 0.3 V
with 1.5 kohm to 3.6 V; see also the [USB-IF specification library](https://www.usb.org/document-library/usb-20-specification).
The model uses 30-ohm voltage drivers and the existing two-node pad capacitance
(2 pF local, 0.3 pF inactive branch, 0.2 pF mutual). It solves pad voltage
relative to board return, including the **coherent die-ground motion**, rather
than treating differential die supply as the absolute output voltage.

| Condition | Lower enclosed high at 3.267 V source | Upper enclosed low | Verdict |
|---|---:|---:|---|
| Selected 0.5 nH common return, full 96 mA wired allocation | 2.701 V | 0.299 V | Fails driven-high requirement even at nominal source voltage |
| Same network, one active branch at 50 mA total WIRE allocation | 2.797 V | 0.298 V | Sampled high actually reaches about 2.7993 V; failure is not merely enclosure conservatism |
| Same 50 mA case, tighter 3.2835 V minimum source | 2.814 V | 0.298 V | High condition passes, but modeled low margin is under 2 mV; not selected as a sufficient mitigation |
| 0.25 nH common-return target, 50 mA WIRE allocation | 2.844 V | 0.194 V | Conditional voltage margin across the original ±1% source window |

The 2 nH higher-inductance probe fails by much more, including driven-low
voltage. These are static signaling states with periodic rail/ground noise;
they do not establish a USB eye, edge-rate compliance, chirp, negotiation,
disconnect or HS traffic. Signal-bond inductance, cable, switch charge and
pad-current feedback into the PDN are still missing. Fixed nominal-source AC
spectra are retained at the DC source corners. Fine time sampling is enclosed
using a derivative bound; small borderline misses are not rounded into passes.

**Decision:** USB bidirectional operation disables the unused serial branch;
reserve 48 mA for its active branch and 2 mA for the inactive branch, with
CORE/HOST/timing allowances unchanged. This is an enabled-block allocation,
not an on-chip protocol profile. Keep the 96 mA simultaneous serial budget for
configurations that actually enable both branches. Do not add the modeled pad
load a second time to its reservation.

Adopt **0.25 nH common return as the common assembly target**, retaining
provider-compatible wire bonding and existing ground sites. This target is an
uncertain equivalent-network requirement, not a proven bond geometry. The original
0.5 nH whole-chip fixture does not close USB. The lower-return candidate
now runs across the existing RF, clock, converter, wired and USB benches using
one package catalog. The report rejects missing package cases; this coverage
check does not supply missing behaviors or establish physical assembly feasibility.
The voltage pass alone cannot qualify the whole chip. The shared comparison now
preserves selected SAR precision, narrowband packet exchange and wired recovery
at 0.25 nH, while weak wideband blocking still fails. Evidence ID `selected`
remains the original 0.5 nH control; `baseline_package_case` now identifies
`lower_return_probe` as the common target. This naming preserves old evidence
identities instead of silently relabeling earlier measurements. Additional
return bonds/placement and quieter host activity are possible physical remedies,
not yet demonstrated substitutes for that test. No extra supply or signal pin
has been silently introduced.

### USB high-speed quiet-pin and common-return gate

`usb_hs_levels` adds released, P-driven and N-driven static states of the same
bidirectional branch. Host and device use these same physical primitives; this
is not a negotiation controller or an on-chip protocol profile. It consumes the
same 242 mA single-branch allocation, two host-current spectra and all three
package cases. Local 45-ohm terminations return to die ground; precision remote
45-ohm loads return to board ground. The existing pad/inactive/mutual capacitance
is retained. Separate 0.2-ohm signal bonds include a 2 nH nominal hypothesis,
a zero-inductance control, and a sensitivity probe with 1.6/2.4 nH bonds and
42.75/47.25-ohm local terminations. These are unmeasured hypotheses.

Crucially, the remote terminations create additional return paths. Their
harmonic currents feed back into the three-node supply/return network before
computing pad voltages. DC current returning through the remote loads is
redirected from the common ground bond, not added again to the WIRE budget.
An independent seven-node nodal solution checks the frequency-domain reduction;
DC KCL separately checks current ownership. Ideal current steering remains
inside the existing reservation; physical output impedance, supply sensitivity
and switched current are not yet represented.

The [USB-IF electrical test specification, EL_9 and §4.3](https://www.usb.org/sites/default/files/USB%202%200%20Electrical%20Compliance%20Specification(v1.07).pdf)
specifies ±20 mV for undriven HS pins with precision terminations. The report
separates DC, an unfiltered instantaneous guard and hypothetical measurement
bandwidth controls. No chosen observer bandwidth is claimed to be the required
compliance instrument response.

| Common return, matched 2 nH signal bonds, released state | Sampled quiet-pin absolute peak | Enclosed peak | DC result |
|---|---:|---:|---|
| Original 0.5 nH control | 129.7 mV | 130.9 mV | Within ±20 mV |
| Current 0.25 nH target | 70.7 mV | 71.3 mV | Within ±20 mV |
| 2 nH uncertainty probe | 421.3 mV | 425.2 mV | Within ±20 mV |

At the current target, matched legs cancel the host-induced differential signal
while retaining this board-referenced disturbance. The asymmetric probe instead
has a differential interval of about −2.67 to +3.82 mV and a 72.2 mV quiet-pin
enclosure. This is why a clean differential eye or DC level cannot close the
physical-interface gate. The result is not created by the new signal inductance:
the zero-signal-inductance control still reaches 69.6 mV.

For the matched current target, illustrative single-pole observer bandwidths
of 20 MHz, 200 MHz and 1 GHz produce quiet-pin enclosures of 4.63, 23.53 and
54.50 mV respectively. The large bandwidth dependence prevents relabeling this
as a formal USB compliance failure. It does establish unclosed high-frequency
common-mode behavior, with a measured instrument/channel definition still needed.

**Decision:** keep USB and the existing pad branch, but do not treat 0.25 nH as
sufficient physical-interface closure. Preserve that package target while
resolving how host return current couples into the wired termination reference
through the fixed provider ground sites. For the unchanged matched spectrum,
a uniform host-induced AC reduction to about 0.255 of its present amplitude
would suffice for the unfiltered guard; this is an inverse requirement, not
proof that slower edges, a lower host rate or return segregation achieves it.
Any remedy must also preserve host throughput and response deadlines and be
rerun through the common clock/RF environment. Do not simply tighten the assumed
common inductance until a test passes, or assume additional ground bonds.
Full USB electrical lifecycle, packet timing, cable behavior, source compliance
and dynamic pad-current feedback remain open.

### Host-rate reduction does not close the USB return/noise gate

The HS campaign now tests simultaneous D2H/H2D word rates from 62.5 to
312.5 Mword/s, including intermediate rates near the response-time boundary.
This is a counterfactual mitigation screen, not an adopted host-clock change.
Each case regenerates both host-current spectra and relocates the corresponding
H2D internal mean current inside the unchanged 110 mA HOST / 242 mA total
reservation. Pulse shapes, charge per edge and the selected package stay fixed.
Control still follows H2D physical clock divided by four.

**Preserve absolute spectral coverage when comparing rates.** The number of
harmonics grows at lower repetition rates, covering at least 1.875 GHz on D2H
and 937.5 MHz on H2D. Holding the original harmonic count would suppress fast
edge content as the clock slows and falsely suggest that the peak disturbance
had disappeared. These remain finite-band assigned current spectra, not
converged physical switching waveforms.

The same candidate rates feed the existing generic short/bulk frame timing
calculation. Eight-word frames provide three ten-bit payload words; 64-word
frames provide 59. The calculation includes frame publication, queuing, the
selected H2D control CDC, 40 ns FPGA processing, 34 ns analog allocation and
20 serial bit times of packing. D2H CDC, physical GPIO and cable margins remain
missing, so a passing timing number is insufficient for protocol qualification.

| Both host word rates, current 0.25 nH target | Enclosed quiet-pin peak | Eight-word payload capacity | Incomplete response allowance |
|---|---:|---:|---:|
| 312.5 Mword/s | 71.3 mV | 1,172 Mb/s | 358.9 ns |
| 300 Mword/s | 72.1 mV | 1,125 Mb/s | 369.0 ns |
| 267.5 Mword/s | 86.0 mV | 1,003 Mb/s | 399.8 ns |
| 250 Mword/s | 74.9 mV | 938 Mb/s | 419.7 ns |
| 156.25 Mword/s | 75.6 mV | 586 Mb/s | 602.1 ns |
| 62.5 Mword/s | 74.4 mV | 234 Mb/s | 1,331.7 ns |

The ordinary local-response comparison is 400 ns (192 HS bit times). Even
before missing margins, the eight-word expression requires at least about
267.3 Mword/s. The larger frame can carry 576 Mb/s at 62.5 Mword/s, but its
calculated response allowance is 6.71 us. Throughput alone does not establish
usability. None of the 36 package/rate combinations meets the unfiltered
quiet-pin, throughput and incomplete turnaround guards together. This does
not prove that every possible rate, transport or physical implementation fails.

**Decision:** retain the selected host rate and reject simple clock reduction
as the present remedy. Peak edge current and host-to-wired-return transfer must
be addressed, with edge shaping and physical return segregation evaluated
against actual GPIO timing and the fixed provider sites. Lower average switching
power is not equivalent to lower instantaneous ground disturbance. The observer
bandwidth caveat of the quiet-pin screen still applies; neither this rate sweep
nor a transport calculation establishes USB compliance or a full lifecycle.

### Return partitioning must close both ground and supply loops

`return_partition` replaces the single die return with host, analog and common
board-return nodes. The shared supply feed, damped analog supply, board capacitor
and total 500 pF local reservoir remain explicit. Parallel branch impedances
plus the common segment reproduce the original return R/L when the die returns
are tied; that limit is independently checked against the three-node model.
The campaign also checks DC current paths, KCL and passive power balance.

Ground separation alone leaves host input current on the analog supply and
allows the analog reservoir to carry its return current. Additional cases move
that input supply to the HOST feed and allocate 125, 250 or 375 pF of the
existing reservoir to HOST. Capacitance is conserved and ESR scales inversely
with allocated area. No independent external rail or extra ground terminal is
granted. Inter-return coupling spans assigned capacitances and a conductive
path; these are requirements to investigate, not extracted substrate/ESD values.

At the current 0.25 nH equivalent return target, with unchanged worst-rate host
activity and the 242 mA bidirectional-branch reservation:

| Hypothesis | Quiet-pin absolute enclosure | Host rail upper enclosure | Largest host/analog ground difference |
|---|---:|---:|---:|
| Tied-return control | 71.3 mV | 3.421 V | Approximately zero |
| Separate returns only | 278.8 mV | 3.901 V | 987 mV |
| Separate returns, HOST input supply, 250/250 pF split, 2 pF coupling; equal return groups | 16.4 mV | 3.492 V | 200 mV |
| Same low-coupling case, site-count-weighted groups | 10.0 mV | 3.618 V | 314 mV |

The site-count hypothesis is read from the retained provider inventory: two
north/south ground sites near the host buses and eight east/west sites. Equal
per-site impedance is only a hypothesis; neither the aggregate weights nor a
physically isolated on-die ground network is proven. All existing sites remain.
The original template's common nets do not establish this partition.

The same hypotheses also run at both RF band endpoints with the 236 mA RF
budget and inactive USB terminations. Quiet-supply motion drives reference
modulation and the existing supply-to-clock-delay model. At 2.4 GHz the
site-weighted low-coupling case increases assigned supply-induced timing RMS
from about 2.83 to 4.07 ps and weak-blocked BPSK errors from 18 to 46 of 2,340;
at 2.484 GHz the error count remains 12, while timing RMS rises from 2.81 to
4.15 ps. These short assigned-ENOB, known-DATA comparisons do not establish
packet performance. The causal SAR load-feedback network is not yet migrated.

**Decision:** do not adopt return separation from a USB-only pass. Retain the
baseline and the coupled alternatives. A credible partition must account for
host input supply ownership, local reservoir allocation, inter-domain voltage
and timing, and substrate/ESD coupling within the fixed geometry. Ground labels
alone provide no isolation.

The [coupled REF_IN screen](#ref_in-voltage-and-clock-edges-with-moving-return)
below now resolves the direct input-voltage path and input-capacitance return
current. The RF payload comparisons above retain their earlier clock model;
they must be migrated before selecting a partition or qualifying external timing.

### REF_IN voltage and clock edges with moving return

`reference_return` closes the previously omitted board-to-die voltage path.
The existing 0.5 V-peak / 50.2-ohm source, 2 nH signal bond, 3 pF input and
20 mV incremental threshold are now solved with the five-node PDN. Input
capacitance is a real return-current path: both its carrier current and its
loading of host-induced ground motion participate in the solution. This is a
linearized input about an unspecified bias; absolute common-mode, protection
and transistor receiver behavior remain unqualified.

The campaign covers three package cases, three return arrangements and RF
2.4/2.484 GHz plus wired 2.5 GHz external-clock operation. Full wired-duplex
288 mA and RF 236 mA allocations remain reserved; no USB test terminations
are enabled. Positive threshold crossings are located by bracketing roots over
one coherent nominal-rate period. All rising crossings resolved on each
32-sample/UI grid are counted, with a 64-sample/UI refinement. A source-only
control keeps the same physical loading while removing host activity.
Independent series-Thevenin, power-balance, analytic phasor-shift, edge-loss and
correlated-delay checks verify the mathematical implementation.

Downstream supply delay uses the retained assigned 0.1 ps/mV sensitivity and
1 GHz pole, evaluated at actual input crossings. The source's own returned
carrier contributes supply ripple as well. Direct input displacement and
supply delay remain coherent; their RMS values must not be added independently.
At the selected 0.25 nH equivalent package target:

| External clock / return hypothesis | Direct input-edge RMS | Combined with assigned supply delay | Combined peak-to-peak |
|---|---:|---:|---:|
| Wired 2.5 GHz, tied baseline | 11.06 ps | 11.12 ps | 46.97 ps |
| RF 2.4 GHz, tied baseline | 8.93 ps | 9.13 ps | 45.25 ps |
| RF 2.484 GHz, tied baseline | 9.05 ps | 9.25 ps | 47.27 ps |
| RF 2.484 GHz, equal split, 250/250 pF, 2 pF coupling | 3.16 ps | 2.54 ps | 13.56 ps |
| RF 2.484 GHz, site-weighted split with the same capacitances | 2.15 ps | 3.29 ps | 15.35 ps |

All nine current-package cases retain one resolved rising edge per nominal UI
and ordered output edges at both resolutions. This is a finite deterministic
clock screen, not statistical jitter or phase-noise qualification. Loaded
carrier amplitude remains around 0.20–0.21 V and the external clock returns
about 9.4–9.7 mA peak through its input capacitance. That alternating externally
supplied current is not another on-chip DC current allocation.

The original 0.5 nH tied wired case has an empty rising-edge window even in this
passive model. Several higher-inductance cases also lose windows; three have
counts that change with refinement. Exact loss counts in those cases are not
converged and must not be reported as reliable clock behavior. No clean clock
is inferred from their nominal frequency or RMS alone.

**Decision:** retain external timing as an implementation route, but withdraw
any inference that the old source/input-noise plus supply-delay budget covered
its complete clock path. Return-partition choices must be reevaluated with
this path included: the same correlation that worsened an isolated supply-delay
metric can improve the complete deterministic edge result.

The [coupled RF payload comparison](#corrected-ref_in-clock-in-the-rf-conversion-chain)
now carries these events into the assigned-ENOB wideband RX/TX path. Other
payload benches still need migration, particularly causal SAR/reference loads,
narrowband packet timing and the wired external-TX path with independently
owned RX CDR. Nominal coherent phases, unknown bias/sensitivity and unextracted
coupling still prevent whole-chip timing closure.

### Corrected REF_IN clock in the RF conversion chain

The `weak_converter_feedback` control now joins causal SAR decisions/recharge
to the corrected clock at both band endpoints and both assigned supply-delay
signs, at fixed 54 dB gain and the same −85 dBm wanted / −30 dBm blocker.
All accepted tied-return loops converge. At 0.25 nH, positive/negative cases
retain 58/60 errors at 2.4 GHz and 23/27 at 2.484 GHz; at 0.5 nH the counts
are 208/266 and 156/168. The 2 nH clocks are rejected before conversion.
The transient supply-delay sign follows its periodic counterpart; neither
rail nor input-voltage disturbance is artificially sign-flipped. The main
assigned-ENOB comparisons below remain controls. Explicit conversion dynamics
do not remove this short uncoded blocked-reception failure; known-DATA training,
numerical sensitivity and missing packet acquisition still limit interpretation.

`reference_payload` connects the solved periodic rising edges to RF LO phase
and divided ADC/DAC event timing. Phase is continuous and advances between the
ordered edges; static phase is retained, not removed using payload truth.
Missing, unordered, unresolved or out-of-envelope clock records are rejected
before running payloads. The same coupled network supplies rail/headroom and
reference modulation, including the external clock's own returned carrier.
DC current relocation and resistor losses are accounted without changing the
236 mA RF reservation. Both assigned supply-sensitivity signs are tested.

Source phase, source-AM conversion and receiver/distribution noise remain
assigned small perturbations on that clock. The input-noise calculation is
gain-normalized to the coupled carrier amplitude; the physical source remains
0.5 V peak. These perturbations are not yet solved jointly at the analog
threshold. The old host-induced supply-phase term is replaced, avoiding double
counting. Rising-edge interpolation does not specify falling edges, quadrature,
buffer waveforms or a strict phase-spectrum bandlimit.

The previous environment is rerun on the same 256× envelope grid. At the current
0.25 nH package target, the weak −85 dBm wanted / −30 dBm +12 MHz blocker fixture
and fixed 54 dB gain produce these **uncoded errors out of 2,340 held-out bits**:

| Environment | 2.4 GHz | 2.484 GHz |
|---|---:|---:|
| Previous environment, same grid | 13 | 5 |
| Corrected tied clock, positive sensitivity | 59 | 20 |
| Corrected tied clock, negative sensitivity | 56 | 24 |
| Equal low-coupling split, positive / negative sensitivity | 10 / 24 | 5 / 6 |
| Site-weighted low-coupling split, positive / negative sensitivity | 19 / 35 | 5 / 5 |

The 2 nH tied cases are rejected at the clock gate for both band endpoints;
no smooth substitute clock is supplied. Split cases are evaluated at the current
package target only. The hypotheses remain unextracted, and the receiver still
uses assigned-ENOB conversion and two known DATA training symbols rather than
real preamble acquisition, FEC or a packet-error criterion. These counts cannot
be treated as protocol sensitivity or statistical BER.

**Numerical limit:** the noiseless 2.4 GHz tied case has RX EVM 1.104, 1.206 and
1.281 at 256×, 512× and 1024× grids, with 42, 44 and 45 bit errors. The failure
persists, but its EVM is not converged; do not derive a precise silicon budget
or select a partition from that value. At 2.484 GHz the same control changes
from 0.38150 to 0.38191 EVM and retains 20 errors at 256×/512×. Faster clock-return
and interpolated phase content require numerical care even in a mathematical
model. The old lower-bandwidth simulation cannot silently stand in for it.

A focused integration control uses exact piecewise-linear forcing of the same
analog poles, independently checked against real state-space integration for
complex I/Q inputs. At 2.4 GHz its 256×/512×/1024× EVM is 1.397/1.330/1.381,
with 43/43/46 errors: changing the integrator does not establish convergence.
New observation diagnostics locate 72–82% of squared equalized error on
subcarrier +71 across both integration methods. The smallest training gain is
only 7.6–9.8% of the median data-tone gain. This identifies strong amplification
by the two-symbol channel estimate as a contributor to EVM sensitivity, not
proof of the underlying analog cause. Keep the receiver and its errors intact;
next separate training contamination from pre-equalization signal impairment.
The linear-forcing controls are now generated alongside existing resolution
controls; legacy ZOH remains the default. These focused results postdate the
retained full-report snapshot until that report is regenerated.

The paired blocker-removal control keeps the corrected clock, rails, gain and
native converter unchanged. With random noise disabled, clean RX EVM is
1.727/1.712/1.704% on the same three grids, with zero errors. Substituting only
its training interval into the blocked receiver leaves EVM 0.724/0.734/0.738
and **30 errors at every grid**, versus 42/44/45 with contaminated training.
The clean estimate is an attribution tool, not an available receiver feature;
blocked held-out data and pilots remain untouched. No payload-time PGA clipping
or ADC saturation occurs in these cases. Training contamination amplifies the
reported impairment but cannot explain away the blocked failure. Preserve that
failure and investigate blocker conversion through the delivered timing/rail
paths before tightening ADC precision or declaring the package qualified.

TX in-band EVM changes little in this fixture: about 4.00% versus 4.00% at
2.4 GHz and 3.927% versus 3.927% at 2.484 GHz for the previous and corrected
tied environments. TX grid controls are much more stable than the problematic
2.4 GHz RX case. This is not a spectral-mask, blocker, real-preamble or packet
qualification.

**Decision:** retain the corrected event-clock path and keep both tied and
partitioned cases. Receiver blocking remains the material concern; a clock-only
RMS improvement does not establish a usable RF configuration. Resolve numerical
sensitivity and migrate causal converter/load feedback and real acquisition
before accepting a common operating envelope. This bench does not silently
replace the independently recovered wired RX clock or qualify wired TX timing.

### Selected wideband RF under the same environment

The same `selected-baseline.json` now joins the fifth-order finite-zero RX
filter, native 10-bit ADC/DAC transfer and third-order TX reconstruction to the
236 mA RF mode allocation, both LO endpoints and the shared package catalog.
RF input levels are absolute, with 2 dB external loss for wanted and blocker
alike; no selective board rejection is credited. The ADC returns signed 10-bit
codes shifted left two positions in the 12-bit transport word. DAC inputs round
to 10 bits with saturation, never wrapping. Neither transfer proves a physical
SAR, converter linearity or reference settling.

The RX hypotheses are 6 dB chip-input NF, 0 dBm IIP3, 20 dB early gain, 8 ENOB,
10 ps independent aperture noise, the shared delivered-clock spectrum and
reference ripple. Early gain and PGA headroom track the instantaneous loaded
rail with assigned sensitivities. Four fixed PGA settings (42/48/54/60 dB) are
reported separately; this search is not AGC. A 12 MHz-offset blocker is −30 dBm.

| Wideband operating point | Observed result | Meaning |
|---|---|---|
| Wanted −65 dBm, PGA 42 dB | About 6.1–7.7% EVM, no errors in 2,340 held-out BPSK bits per case, no PGA clipping during the source burst | Useful conditional wideband evidence under both package hypotheses, not a packet or higher-modulation qualification. |
| Wanted −85 dBm, same blocker | Every tested gain setting has errors; best EVM is roughly 62–146% across the four environments | Finite-zero filtering is necessary here but insufficient to establish this weak-signal/blocker operating point. More gain eventually clips; it is not a general cure. |
| Fifth-order all-pole comparison at −85 dBm, 2.4 GHz | All source-burst ADC sampling instants encounter PGA clipping at every tested gain; roughly half the BPSK bits are wrong | Retain finite-zero selectivity in the baseline. A different gain range might prevent clipping but would need its converter-noise budget rechecked. |
| TX, third-order 20 MHz reconstruction, 0.12 RMS nominal DAC drive | About 3.9–4.0% EVM, zero short-fixture BPSK errors; within assigned differential port voltage/current/energy limits | The existing 28 mA driver reservation can support this modeled operating point within RF 44 mA. This is not measured TX power, an emissions pass or proof of the driver. |

The higher-inductance probe raises TX power above 50 MHz offset from about
0.31–0.33% to 1.43–1.52% of the within-10-MHz power, before external RF filtering.
This illustrates why a clean decoded waveform does not establish RF spectral
quality. These broad integrals are not standard measurement bandwidths or masks.

Two known DATA symbols train the external equalizer; fixed fixture pilots track
common phase and ten DATA symbols are held out. Ideal symbol boundaries are
provided. There is no real preamble, packet acquisition, CFO search or PER
claim. FPGA interpolation/resampling uses 64 taps with explicit lookahead;
continuous host service and timed launch are separate missing obligations.

The high-rate envelope resolves the host/LO tones before analog filtering.
TX reconstruction propagates exact nonuniform DAC edge times, avoiding artificial
jitter from snapping edges to the simulation grid. Independent state-space
checks verify both uniform analog filtering and this event-driven reconstruction.
Resolution controls at 2.56/5.12 GHz, plus a 10.24 GHz weak-RX check, retain the
loaded clock realization while removing random thermal/converter/aperture draws.
TX EVM changes by less than 0.005 percentage points; the difficult RX case has
up to about 1.3 percentage points of EVM spread, so precise weak-case EVM and bit
counts are not converged qualifications. Its failure remains at every resolution.

**Remaining joined RF work:** calibrated air-boundary timing across radio settings,
physical SAR/reference timing and broader dynamic-current coverage;
filter internal swing/noise/tuning; real FPGA control/service; output-current
feedback into the PDN; and spectral masks with explicit board filtering.
Retain the selected architecture while testing these obligations. Do not promote
the −85/−30 dBm stress point to a supported operating envelope.

### Weak wideband failure: paired impairment diagnosis

The `wideband_diagnosis` campaign keeps the −85 dBm wanted signal, −30 dBm
blocker at +12 MHz, shared package/rail realization, fixed noise seeds and fixed
gain sweep. It disables one modeled contribution at a time and retains all
package cases. These interventions identify causes; they are not cheaper or
qualified operating configurations. Source, supply-induced phase and external
input phase now have explicit provenance within the same delivered-clock model.
The input model separately records AM conversion and additive receiver/distribution
noise; its source swing, threshold offset and AM depth are explicit hypotheses.

At the current 0.25 nH target and fixed PGA 54 dB, the two LO endpoints give:

| Intervention | Uncoded errors / 2,340 evaluated bits | Interpretation |
|---|---:|---|
| All effects | 18 / 12 | Existing weak/blocker failure retained |
| Remove converter excess noise | 18 / 13 | Native quantization remains; converter noise is not the dominant remedy at this gain |
| Assume 9 ENOB instead of 8 | 18 / 13 | Does not justify spending the converter-upgrade budget to solve this failure |
| Remove frontend thermal noise | 6 / 3 | Thermal noise materially affects EVM, but does not explain all blocker errors |
| Remove input/distribution additive phase noise | 6 / 1 | Strongest individual clock-path improvement |
| Remove input AM conversion | 18 / 12 | The larger integrated AM timing number does not identify the important interference mechanism |
| Remove all delivered phase noise | 0 / 0 | Counterfactual diagnostic; rail/reference movement and other impairments remain |
| Remove blocker | 0 / 0 | Short clean-channel decoding does not establish sensitivity/PER |

The input/additive hypothesis is about −138 dBc/Hz equivalent SSB floor in
1 kHz–8 MHz, alongside a much larger coherent AM-to-phase contribution.
Centering the input threshold from 20 to 2 mV, lowering AM from 10% to 1%, or
raising source peak swing from 0.5 to 0.75 V does not resolve the blocker case.
An unpriced 25 uV receiver / 5 fs-per-downstream-stage hypothesis improves it
but still has 7 / 2 errors at this gain. No noise allocation is silently promoted
to demonstrated GF180 performance, and no extra bias current is free.

Because finite phase lines can concentrate interference on individual OFDM
subcarriers, the selected target also runs 128- and 512-bin input-noise controls
and a second 512-bin realization. Integrated additive noise power is preserved.
Errors remain (11 / 8 at 128 bins, 12 / 7 at 512, 13 / 8 for the second seed),
but exact EVM/error counts change. This supports the qualitative failure and
work priority; it does not establish statistical convergence, a unique phase-noise
mask, or packet error rate. Known two-DATA-symbol training, uncoded BPSK and the
lack of a real preamble/FEC remain explicit limitations.

**Decision:** retain the selected converter and channel-filter allocation.
Prioritize the delivered clock's far-offset additive noise and blocker reciprocal
mixing, together with the complete receiver/acquisition model. Do not spend the
ADC fallback budget or optimize only aggregate RMS jitter based on this fixture.
Any mitigation must retain power/headroom accounting and pass packet-level tests;
the +12 MHz stress alone is not a standard Wi-Fi qualification condition.

### Selected narrowband packet exchange

The same entry point now runs real LE 1M scan requests and replies at 2.426 GHz,
with the complete 236 mA allocation and the shared package catalog. It uses native
10-bit conversion in 12-bit transport, a fifth-order 500 kHz all-pole RX setting,
third-order 1.5 MHz TX reconstruction, 10 ps aperture noise and instantaneous
rail-dependent gain/headroom. The all-pole narrow setting and finite-zero
wideband setting use the same selected configurable filter boundary. The older
packet fixtures retain their explicit 12-bit/one-pole defaults as controls.

At −80 dBm wanted with two −30 dBm blockers at +2/+4 MHz, the assigned 6 dB NF,
0 dBm IIP3 and the causal paired-SAR requirements now use corrected REF_IN
events and recharge-induced input-voltage feedback. At the 0.25 nH target,
five of six held-out requests pass CRC and receive independently decoded replies;
seed 719 acquires but fails CRC. At 0.5 nH all six stressed requests fail
acquisition; the 2 nH clock is rejected before packet simulation. These results
supersede the old-clock six-of-six result. Acquisition and gain
control use received codes; no synthetic training prefix or payload oracle is
provided. Six trials do not establish PER or Bluetooth qualification.
For seed 719, the previous environment at the same 1024-substep grid passes,
as does the corrected environment with blockers removed. Both controls retain
causal conversion and their respective load-feedback paths. This ties the
failure to the combined corrected environment and blocker exposure, rather
than the grid change alone; it is not a single-impairment attribution.

Uncorrected diagnostic RF launch gaps are approximately **about 151–152 µs**
against the model's 150 µs target. A separate −60 dBm, blocker-free training
packet supplies one fixed RX timestamp correction (about 1.190 µs) and one TX
launch advance (about 0.319 µs) per package setting. Applied unchanged to all
held-out packets, the five successful current-package exchanges give
**149.964–150.179 µs** diagnostic gaps and correct peer decoding. The failed
request does not arm a reply. This establishes the usefulness of external timestamp/
launch calibration; it does not establish a standard air-boundary measurement,
physical calibration procedure, or stability across channels, filters and PVT.
No scored packet's actual source end is used to correct its launch.

The source-swing control now repeats this complete exchange at **0.75 V
external Thevenin peak**, including separate strong calibration at that setting.
At the 0.25 nH target, all six requests and replies decode correctly, all causal
reference-feedback loops converge, and calibrated diagnostic gaps span
**149.964–150.179 µs**. Replies have no DAC clipping and meet the assigned port
voltage/current/energy bounds, with about 3.145–3.150 mW active output power.
The same change yields only **one of six** successful exchanges at 0.5 nH;
the 2 nH clock is still rejected. This supersedes the earlier RX-only mitigation
check, not the failed 0.5 V baseline. Both source settings remain in the report.
Baseline-only previous-environment attribution controls are not reused as
matched-source comparisons for the stronger-clock experiment.

The stronger source is a common RF/wired mitigation candidate, not a qualified
input requirement. Its source/pad bias, nonlinear loading, stage-sensitivity
corners and broader channel coverage remain open. The reply's broad spectral
integrals remain diagnostics before external filtering, not emission-mask
measurements; TX-load feedback and physical switching transients are absent.
Six successful exchanges do not establish PER or a standard turnaround limit.

The actual event-driven reply FIFO peaks at **32 samples in a 42-sample queue**
(1,008 bits at 24 bits/sample). It retains prefill while clocks run during the
wait, then consumes on actual perturbed DAC edges. A 10 µs host-stall test exposes
underflow after 32 samples and prevents a complete decoded reply. Bulk waveform
storage remains in the FPGA; this does not close the complete 8,192-bit chip
inventory or prove the physical host interface's service guarantee.

**Decision:** retain warm clocks/bias, finite prefilling and host-owned fixed
latency calibration. The closed-loop converter study below now addresses one
reference-load path in this packet loop. Gain commands use completed codes,
20 ns conversion latency delays availability without moving the air timestamp,
and each packet supplies its own reference-current feedback trajectory.
Post-RX load relaxation is retained into the reply. No additional assigned
8-ENOB noise is added to the causal converter. Next include output-current
feedback into the PDN. The packet result still uses assigned analog
settling, NF, linearity, phase noise and drive; it does not close those physical
risks or the wideband blocker failure above.

### Driver wake under the selected shared environment

The selected-baseline report's `transmitter_wake` campaign now joins the local
PDN wake response to wideband TX clock crossings, DAC reference, RF gain and
available driver current. The response now includes REF_IN loading and direct
input-voltage movement, with threshold events solved before applying downstream
supply delay. It uses the same 236 mA maximum allocation, host
switching and package catalog at 2.484 GHz; the 2 nH clock is rejected before
payload simulation. Warm bias, a 7 mA change,
and the full 28 mA driver reservation are compared, with 20 ns ramps at waveform
launch or 2 us ahead. A 1 us full-current ramp is also tested with 2 us lead.

The accounting starts at a settled reduced load and returns to the existing
full-current DC budget. It does **not** add another 28 mA to that budget.
Restoring full bias removes about 59.36 mV of initial rail relief. At the current
target, full wake produces about 0.56 mV peak incremental REF_IN voltage and
5.94 ps peak assigned downstream supply delay. The guarded frequency-domain
response uses 0.5/0.25 ns grids and 8/16 us settling guards. Independent
state-space comparison with input loading removed agrees within 20 uV away
from the ideal ramp corners and 2 uV RMS over the record. Inductive voltage
jumps at those corners make instantaneous peaks resolution-sensitive; do not
reuse the old-network undershoot numbers as corrected bounds. Reference and clock filters retain
state. The RF source is clipped to available tail current during wake, so a
fully parked driver cannot produce the unchanged waveform before turning on.

These short, known-DATA fixtures retain about 3.93% held-out EVM at 0.25 nH
and 4.01% at 0.5 nH, with zero BPSK errors in 2,340 evaluated bits. Grid and
guard controls are retained separately from the payload score.
This is useful supply/timing evidence, **not wake or packet qualification**:
the receiver skips two known DATA training symbols, which can hide startup
corruption. The report separately counts current clipping during the source.
Bias readiness, real preambles, signal-dependent RF-cycle current, DAC glitches,
external filtering and emissions limits remain unproved.

**Decision:** keep warm/muted bias as the baseline. The modeled PDN does not
currently justify spending more area on a wake-only supply remedy. Preserve
parked bias as a conditional alternative until actual analog readiness and
acquisition are represented; prioritize host coupling and continuous output-load
behavior over further isolated wake sweeps.

### Closed-loop converter and reference-load requirements

The baseline now includes an input-driven paired SAR model. Acquisition state,
DAC output and the shared reference reservoir persist across conversions. Each
trial decision determines the next trial code and reference charge; no measured
reference trajectory or known final code is supplied. Reference recharge feeds
the same package/PDN, whose disturbance returns to RF gain/headroom, reference
voltage and LO/sample timing. Each tested loop converges in two passes under the
reported numerical criterion. This is a conditional mathematical result, not
identification of physical GF180 device parameters.

Select **unequal bit-time allocation within the selected 20 ns conversion budget**, as listed
above. The initial requirement point uses 0.5 pF per sampling leg with 200 ohm
acquisition resistance; 1 pF effective switched DAC capacitance per converter;
a 300 ps DAC settling pole; and a shared 100 pF reference reservoir driven by
50 ohms, with 1 mA source-current limit and 2 mA standing bias. Reference and DAC
resistance-related time constants scale as 3.3 V / loaded rail in this model.
Comparator noise is an assigned 1 mV RMS per decision, plus calculated sampling
kT/C noise. None of these numbers is a measured process bound. The reference
capacitor alone has a 0.111 mm² ideal plate floor at 0.9 fF/µm², inside the
selected 0.15 mm² reference/buffer allowance, leaving about0.039 mm² for
the active buffer and layout overhead. The capacitor density is a planning
hypothesis, not extracted area.

At 38.8125 MS/s and 0.65 V peak per I/Q component, independent near-1-MHz and
near-9.457-MHz sine measurements give approximately **8.60–8.67 full-scale-
normalized effective bits** across the two package hypotheses. A fundamental
and DC fit removes only gain, phase and offset; noise and harmonic distortion
remain in the residual. Each sine has its own reference-current feedback, not
the load waveform of a different RF fixture. The 0.65 V swing is deliberately
larger than the modest-signal BPSK case that could conceal converter errors.

| Same total conversion time | Converter precision result | Design implication |
|---|---|---|
| Selected unequal intervals, 300 ps DAC pole, 50 ohm / 100 pF reference | About 8.60–8.67 effective bits | Retain this requirement point and timing allocation. Physical poles, noise and comparator readiness must still be demonstrated. |
| Uniform 1.8 ns intervals with the same devices | About 8.02–8.17 bits | Little margin; unequal allocation helps without adding another ADC or increasing the period. |
| 400 ps DAC pole together with 100 ohm / 50 pF reference | About 7.99–8.05 bits | The combined uncertainty consumes the margin. Do not label this corner supported merely because its BPSK fixture decodes. |
| 800 ps DAC pole, selected unequal intervals and reference | About 5.75–5.91 bits | Clearly misses the 8-bit requirement, even though the short moderate BPSK fixture still has zero errors. |

The selected reference load adds roughly **0.014–0.016 ps RMS** of timing
disturbance in the moderate wideband run, much smaller than the existing
multi-picosecond host contribution under these assumptions. Incremental sampled
rail excursions are about −0.61 mV / +0.24 mV for the selected network and
−1.02 mV / +0.26 mV for the higher-inductance probe. Halving the PDN time grid
changes the latter minimum to about −1.14 mV while changing its RMS timing
disturbance by less than 0.001 ps; peak waveform detail is not a precision claim.
Reference-source charge is conserved, sink current gets no supply-energy credit,
and reference current is not added again to the 40 mA timing/reference budget.
The full planning DC load is retained as a conservative stress; the report
separately identifies its excess over predicted reference consumption.

**Decision:** keep the single-core SAR and improve its local timing allocation
before spending the interleaving fallback budget. The common-envelope sine bench
now also checks comparator deadlines against the actual per-bit overdrive from
the acquisition/DAC/reference trajectory. Its inverse model uses
`Vout = Vin * exp((t - launch)/tau)`, with explicitly assumed100ps launch,
200mV output threshold and25/50/75/100ps regeneration constants. A missed
0.5ns deadline invalidates the ideal-sign decision for that hypothesis; the
reported ENOB is conditional on decision completion. This screen does not
simulate metastable logic propagation or identify GF180 comparator parameters.

The common-envelope runner now executes variable comparator completion and
recomputes shared-reference recharge at each actual event time. Unequal DAC
settling intervals remain unchanged; the paired fixture waits for the slower I/Q
decision. The100ps launch assumption does not establish a physical inter-ADC
handshake or its latency. Both comparator inputs are snapshotted at evaluation
start; kickback and continuous input motion during regeneration remain open.

At the selected lower-return point,50ps regeneration gives8.56/8.76ENOB and a
maximum15.98ns conversion, leaving2.02ns inside the18ns budget. At100ps it gives
8.53/8.78ENOB and a maximum17.63ns conversion, leaving0.365ns. A150ps case is
rejected for exceeding18ns. Both accepted cases converge with their own
reference-current feedback; peak reference current including standing bias is
about2.41mA. Individual comparator decisions can exceed0.5ns without missing
the total conversion deadline. These are finite512-pair conditional results,
not tail-probability, broadband-PER or physical comparator qualification.

**Keep the selected single-core asynchronous SAR architecture.** There is a
credible conditional timing/precision region worth implementing; the fixed
0.5ns-per-decision screen alone is too restrictive for that architecture. Retain
18ns as the advertised conversion-latency ceiling and keep the cycle guard.
Do not spend the observed early-completion margin elsewhere. Independent I/Q
sequencing or a real paired completion barrier must reproduce this result with
its actual latency, load and reference forcing. Wider overdrive/noise/mismatch
coverage remain required. The combined adverse-loading asynchronous screen now
converges at 50/100 ps regeneration with minimum 8.13/8.09 ENOB and maximum
15.91/17.68 ns conversion; 150 ps misses the deadline. This includes acquisition
switch loading, weaker reference drive and doubled comparator noise together,
with delivered-clock/reference feedback. Keep the architecture conditionally;
the 100 ps stressed case has only 0.323 ns completion and 0.09 bit precision
margin. It does not bound rare decisions, diagnostic reference switching,
kickback, mismatch or physical supply-dependent regeneration.

The rounded 40 MS/s block target is not an admissible clock guarantee. The
5 ns acquisition + 18 ns conversion + 2 ns reset + 0.2 ns guard requires at
least 25.2 ns between samples (39.683 MS/s before delivered-clock variation).
The evaluated 2.5 GHz / 64 configuration is 39.0625 MS/s; its sampled cycle
margin is 0.358 ns. Numeric clock admission must use the full cycle and actual
edge-spacing bound, not the rounded block target or average frequency alone.
Early asynchronous completion does not increase the advertised rate ceiling.
The retained SAR continuation check also reserves acquisition, reset and the
cycle guard after the previous completion; splitting a sample stream across
model calls cannot omit that boundary guard. Batch/split regression covers both
a rejected 25 ns interval and an accepted 25.3 ns interval.

Do not halve the selected sample rate merely to recover timing margin: the
existing next divider setting also changes available RF bandwidth and alias
rejection. The interleaving fallback remains available if the connected
asynchronous success region cannot be physically realized.

Stop treating packet decoding
as proof of converter precision. Remaining physical gaps include comparator
regeneration/metastability within the total conversion deadline, capacitor mismatch,
reference-loop higher poles, PGA sampling drive, and realizable bit sequencing.
The causal conversion latency is 18 ns; the selected packet fixtures now join
this detailed converter state and latency to live AGC and service. Earlier
native-transfer fixtures remain controls. The reference-current study also does not substitute for
DAC/TX output-current, core switching or thermal/package closure.

### Fallbacks with explicit allocation costs

These are substitutions triggered by failed requirements, not simultaneously
selected features. Area/current deltas are rough reservations, not circuit
estimates. Recompute the complete mode whenever a fallback is used.

| Fallback | Trigger | Cost and boundary |
|---|---|---|
| Autonomous source in place of external timing | Required standalone operation and delivered spectral/timing budget passes | Source circuits already occupy the timing allowance; their active current must fit 40 mA planning / 48 mA ceiling. Saves an external source, not input/distribution or wired CDR obligations. No extra RF tank pins. |
| Two-way SAR interleaving | Single-core conversion cannot meet the selected rate and ENOB together | Reserve +0.30 mm² from the 0.72 mm² unassigned growth and +4 mA RF current (44 → 48 mA). Requires skew/offset/gain calibration and held-sample/reference state. This consumes the RF current margin; it is not combined freely with another converter upgrade. |
| Higher converter precision | The joined filter/headroom result still requires more dynamic range | Reserve +0.35 mm² growth and +4 mA RF as an alternative to the interleaving allocation; assess actual ENOB, reference load and timing. Increasing word width alone is not this upgrade. |
| Park RF bias between exchanges | Warm-path current or heat is unacceptable and the full wake/recovery sequence fits | No assumed area saving. Model enabled-instance current and startup charge explicitly; current reduction is not booked until a state inventory establishes it. Retain warm operation for deadlines it cannot meet. |
| Stronger board filtering or RF output amplification | A realizable external response closes a remaining image/emission/drive requirement | No new chip pins for inline RF parts; board area, loss, power and tuning/control belong to the FPGA/board budget. Nearby-channel rejection remains uncredited until specified. External parts cannot repair pre-existing chip clipping or internally generated interference. |
| Reduced host switching | Full-rate host activity invalidates timing/RF quality | The slower RF return clock is already baseline. Further reductions must preserve sustained payload and service bounds; they cannot silently discard HE20 or wired throughput. Board load/slew changes must still close GPIO timing. |

Do not spend the same 0.72 mm² growth or 4 mA RF headroom twice. If a combined
fallback needs both, revise owner allocations within the fixed die envelope and
rerun the whole-chip budget. A larger die, custom package, extra analog pins or
removal of requested capabilities is not an automatic fallback.

## Current whole-chip ledger

Reference supply rejection is an independent obligation from clock rejection.
The current joined receiver includes supply-modulated ADC full scale after
analog filtering; independent H2D tones can alias into baseband. Keep a low
supply-feedthrough option and a filtered/buffered reference option, with ADC
load-settling, headroom and current costs still to qualify. The risk assessment
owns the conditional numerical comparison; no physical PSRR is claimed.


Current RF/wired comparisons must use the architecture inventory and selected
common environment, with an explicit source/return map. The former robustness
comparison's fixed-current ledger is retired. The
[current joined assessment](risk-priorities.md#current-joined-host-power-and-receiver-assessment)
owns the accounting requirements and limitations. Public assembly connectivity
does not establish bond/board impedance or independent on-die rails; see the
[assembly evidence](../../../docs/roadmap/programmable-transceiver-pin-plan.md#public-run-1-assembly-evidence).

**Packaging correction (2026-09-26):** preserve provider bond positions and
power/ground assignments. The seven allocated pairs below are not yet a valid
COB bond map. Shared board/pad rails can invalidate earlier independent-feed
assumptions; rerun those studies after G1 mapping. See [decision gates](feasibility-gates.md).

`verification/check_contract.py` now emits `resource_ledger` from the contract:
a logical 51-terminal allocation with 14 supply/return terminals, separately
from the provider inventory of 56 signal and 18 fixed supply/return sites.
It also records 12.92 mm² allocated core area including
2.77 mm² explicit reserve, and 350 mA summed domain planning ceilings. The
reserve is included in the area total, not additional free area. These are
allocations; implemented area/current/storage totals remain null, not zero.
The ledger stays open until physical instances, sharing, clock trees, storage,
internal switching, inactive leakage and pad/package effects are accounted for.
The analytic feasibility screen now derives current ceilings from this same
contract instead of maintaining a second hard-coded copy.

Do not add isolated FIFO mappings to parent-core area that already contains
them. RF/wired exclusivity changes active demand, not the physical area or an
assumption that inactive blocks draw no current. External FPGA storage/logic
belongs in a separate board budget, not in the silicon total.

The selected USB bridge inventory now identifies **3,792 on-chip data-bank
bits**: two 8×84-bit CDC FIFOs, two 80-bit return frames, three 80-bit commit
frames and 2,048 playback bits. These coexist in the candidate; they are not
alternatives. This is a partial capacity subtotal, not a flip-flop count.
Capture record encoding, decoder state, playback boundary locations, counters,
reset/epoch controls and sharing with other modes remain unpriced. The external
FPGA's 1,024-byte payload buffer and eight-record ingress are accounted separately.
`resource_ledger.storage.selected_bridge` owns the itemized inventory; isolated
FIFO area does not price these additional banks or establish complete fit.

### Resource conditions for the combined RF candidate

Use `rf_quality_budget.current_allocation` with `analog-architecture.json`
for each enabled RX, TX, wired or USB composition. Converters belong to their
assigned CONV owner; they must not be hidden in the former 37 mA RF reservation.
Current totals and remaining filter feasibility are recorded in the enabled
inventory and current risk assessment. Logical supply ceilings do not establish
current capability through the actual shared bond network.

Do not increase noise, gain, linearity or clock-performance assumptions without
pricing the needed stages and updating the shared environment. Bias current and
switching current must represent distinct physical contributions. External LO
input can disable an unused oscillator branch, but retains input receiver,
phase-generation, distribution and reference costs; both fabricated branches
still occupy area.

RX/TX reuse earns no automatic budget credit. Turning stages off and on requires
startup charge, settling, disturbance and turnaround checks. Likewise, capacitor
area and routing/guard overhead consume real support area. Qualify the complete
enabled-instance inventory rather than comparing a favorable total against
summed pad ceilings.

### Enabled analog inventory and turnaround decision

Use two generic readiness levels: **warm**, with timing/reference and required
analog bias settled, and **parked**, with selected analog bias disabled and an
explicit wake interval. These are combinations of enables and readiness flags,
not protocol profiles. Select warm operation for tight same-channel responses
until the parked path demonstrates its complete wake cost. Output mute and
bias disable are distinct controls; mute does not imply a current saving.

| Circuit group / owner | RX acquisition | Same-channel transition | TX payload | Parked / retune |
|---|---|---|---|---|
| Selected LO receiver or oscillator, phase generation / PLL | Running | Keep phase/frequency and enables unchanged | Running | May change only through stop/lock/train/new-epoch sequence |
| Converter reference and master bias / PLL | Settled | Remain settled; include changing converter load | Settled | Retain or explicitly reacquire; never infer readiness from LO lock alone |
| LNA, RX mixer, RX filter/PGA / RF | Enabled; AGC active | Hold until final RX samples drain; isolate before TX exposure | Isolated from TX; warm bias retained if needed for next RX deadline | Bias may stop; DC/filter/gain settling required on wake |
| I/Q ADC / RF | Converting | Drain valid samples, then optionally gate conversion events without stopping the shared timing source | May gate conversion; reference load step must be modeled | Invalid until reference, gain and filter are ready |
| I/Q DAC, reconstruction, TX mixer / RF | Warm and output muted for fast response | Load/prefill while muted, settle, then scheduled unmute | Enabled | May disable; precharge/settling required before unmute |
| TX output driver / RF | Warm but muted in conservative fast-response configuration | Controlled unmute; include load-dependent current change | Enabled within assigned 28 mA reservation | Bias may stop; no immediate-wake assumption |
| Host, control, storage / CORE and HOST | Active service and command readiness | Continue service; preserve epoch and timing | Active service | Explicit quiesce/retrain rules; not automatically off |
| Unselected wired frontend / WIRE | Isolated, inactive leakage unpriced | Same | Same | No RF/wired overlap except separately budgeted maintenance |

The shared ownership lifecycle now has a cumulative reference-reservoir charge
ledger rather than separate per-stage power claims. Discharged startup and
represented idle/SAR loads conserve charge through modes and recovery. Its
3 mA source-plus-idle peak occupies the existing reservation. The short sequence
has only about 5.95% conversion activity; its 5.63 µA mean recharge therefore
must not be used as continuous 37.5 MS/s consumption. Reusing the observed code
statistics gives an 84.3 µA continuous SAR-draw estimate, still excluding TX DAC
reference loading and coupled package feedback. Do not silently price those
missing contributions at zero.

Reference bias qualification uses the contract's unchanged 0.98–1.02 V window
in quiet recovery, at acquisition and at actual comparator decisions. It is
not an instantaneous ban on normal CDAC charge-step excursions: those remain
in the reference recovery, DAC settling and conversion-error model. The joined
lifecycle observes startup at 100 ns steps and admits words only after valid
consumption-point observations; physical sensing and inter-observation behavior
remain implementation obligations. This policy does not substitute coarse bias
readiness for ADC accuracy, nor qualify DAC reference loading.

Filter readiness must include retained signal-path memory, not just warm bias.
For the selected linear finite-zero RX response, a unit-bounded prior input can
leave a history error bounded by `sum(U*abs(r)/(-Re(p))*exp(2*pi*fc*Re(p)*t))`.
The existing model implements this in `selected_rf.filter_settling_requirement`;
`selected-lifecycle.json:filter_startup` evaluates the current cutoff settings.
With the assigned 1/1024 normalized residual budget, sufficient settling is
91.3 us at 300 kHz, 54.8 us at 500 kHz and 27.4 us at 1 MHz. These are conditional
linear-model bounds, not process measurements or protocol turnaround budgets.
An independently solved bounded sinusoidal history demonstrates that a 20 us
wait can actually exceed this allocation at cutoffs through 1 MHz; failure of
a conservative bound alone is not treated as an observed violation.

Select longer startup qualification when filter memory is unqualified. The
wired-to-RF replay ANDs the filter certificate with reference/supply validity,
then applies the existing 20 us guard. No new pin, protocol command, analog
block or current saving is assumed. Tight same-channel turnaround instead needs
an undisturbed qualified state, a smaller demonstrated input-history bound, or
a characterized reset/precharge. Warm bias alone supplies none of these proofs.
Keep the chosen gain and filter coefficients fixed while using the certificate;
changing them, saturation, arbitrary initial capacitor charge and TX leakage
require new state/settling analysis. The certificate bounds old-history error;
it does not remove noise or blockers arriving during acquisition.

Qualify the selected transfer family as well as its cutoff. The joined BLE
fixture uses the all-pole setting; its settling time must not be inferred from
the finite-zero certificate. Both use the intended generic filter boundary.
`selected-revision-check.json:rx_filter_memory` compares them with the same
packet, blocker, package and converter feedback. Its prior tone is specified
after early gain/mixing; it does not establish a preceding RF transaction or
TX-to-RX isolation. The filter implementation now preserves modal state across
records instead of requiring every caller to begin at zero.

The finite-integrator requirement screen (`selected-revision-check.json:filter_realization`)
replaces each ideal normalized integrator `1/z` with `1/[z*(1+z/rho)]`, where
`rho` is the additional integrator pole divided by channel-filter cutoff. This
is an explicit shared-pole linear surrogate, not a universal active-RC law or
measured op-amp GBW. Unchanged finite-zero coefficients require `rho > 22.443`
for stability in this model. At the 9.53125 MHz wideband cutoff, `rho=32` means
an effective extra pole at 305 MHz, but still causes 10.40 dB passband peaking.
Faster circuitry alone is not automatically sufficient: `rho=128` still gives
1.50 dB positive peaking in this setting.

Inverse-mapping the desired poles/zeros through `q=z+z*z/rho` restores the
intended slow poles at the characterized ratio. This reuses the intended
coefficient controls; implementable weights, range, resolution and calibration
observability remain requirements. Fixed nominal compensation at `rho=32`
with actual ratio ±10% retains the tested diagnostic DATA, but exceeds the
original 1 dB passband-ripple probe. Do not replace transfer/headroom requirements
with that decoding result. Unequal stage poles, finite DC gain, additional phase
lag, slew, internal saturation and active-device noise are still absent.

For current planning only, ten independent effective `gm/C` stages (five per
I/Q branch), `C=0.5 pF` per stage and `gm/Id=10 V^-1` cost about 0.958 mA at
305 MHz or 3.833 mA at 1.220 GHz. The report also varies effective C and gm/Id.
These are illustrative costs inside the existing 16 mA RF-support remainder,
not added current and not a demonstrated fit. Real amplifiers, compensation,
mirrors, output stages, LNA/mixers and warm TX support must all fit together.
No GF180 speed/noise estimate follows from this single-pole calculation. Select
finite-bandwidth compensation as a required design study; do not assume ideal
filter poles merely because the prototype transfer function meets selectivity.

The state-variable budget screen (`selected-revision-check.json:filter_budget`)
now assigns LP/BP and bandwidth-limited drive voltages to the two biquads and
real pole. It compares twelve section/zero-pair mappings with identical external
transfer functions. Independent integrator-noise paths are integrated by a
Lyapunov solve, checked against frequency quadrature, and constrained at 401
passband frequencies. An integrated 6 dB allocation alone can conceal about
12 dB at some wanted frequencies; it is not an adequate allocation rule.

Use **higher-Q biquad → lower-Q biquad → real pole** as the provisional
low-noise mapping, with the lower-frequency zero pair on the lower-Q section.
For a 6 dB total chip-input noise target, the two assigned scenarios are:

| Scenario | Frontend NF / gamma / gm/Id / minimum effective C | Paired I/Q integrator bias | Required effective C per integrator |
|---|---|---:|---:|
| Lower-noise frontend | 3 dB / 1 / 10 V^-1 / 0.5 pF | 0.958 mA | 0.5 pF |
| Higher-noise frontend | 5 dB / 2 / 5 V^-1 / 1 pF | 7.506 mA | 1.409–2.496 pF |

These amplifier-drive-noise-only comparisons use `e_n^2=4*k*T*gamma/gm`;
the total noise allowance is partitioned between frontend and filter. Effective
pole capacitance grows with gm to retain the assumed 305 MHz extra pole. It is
not the signal-path integration capacitor.

The same screen now sizes actual integration capacitors and summing resistors,
including `4*k*T*R0*conductance_weight` drive-noise density. It reserves a
separate class-A output bank for the peak capacitor current of the −65 dBm
wanted / −30 dBm blocker tone screen. Both I/Q branches are included:

| Scenario | Input bias | Capacitive drive | Total filter current | Integration capacitance | Plate area at 0.9 / 1.8 fF/µm² |
|---|---:|---:|---:|---:|---:|
| Lower-noise frontend | 1.826 mA | 2.627 mA | 4.453 mA | 972.8 pF | 1.081 / 0.540 mm² |
| Higher-noise frontend | 12.614 mA | 8.921 mA | 21.535 mA | 3545.6 pF | 3.940 / 1.970 mm² |

A convex dual lower bound agrees with each optimized current to numerical
precision. Under this specific noise and class-A drive model, the higher-noise
case cannot fit the 16 mA support allowance, even before the other RF blocks.
The lower-noise case leaves 11.547 mA, whose sufficiency remains unproven.
This is not a universal amplifier current lower bound: changing drive topology
or gain distribution requires a new model, not subtraction of the drive reserve.

The RF area owner is 2.4 mm². These are integration-capacitor plate areas only,
at two planning densities, without routing, tuning, guards or other RF circuits.
The higher-noise current optimum exceeds that owner at the lower density and
leaves only 0.430 mm² at the higher density. This is not a minimum-area proof or
confirmation that either capacitor option is available in the assembly route.
Internal signal-path capacitors cannot become external decouplers without an
analog access and pin-budget redesign.

Explicit plate-constrained candidates show that the favorable scenario can fit
0.600 mm² of plates at 0.9 fF/µm² for 4.645 mA, versus 4.453 mA at its
1.081 mm² current optimum. At 1.8 fF/µm² the same 0.600 mm² limit does not
bind the favorable optimum. Thus the earlier area figure is not an unavoidable
cost. These limits are exploratory suballocations, not additional RF area.
The harsher scenario requires 30.950 mA in a feasible allocation at 1.200 mm²
and 0.9 fF/µm² (equivalently 0.600 mm² at 1.8 fF/µm²), or 21.869 mA at
1.200 mm² and 1.8 fF/µm². No feasible allocation was found at 0.600 mm²
and the lower density; solver failure alone is not an infeasibility proof.
The unconstrained current lower bound already rejects the harsher warm-driver
scenario, independently of these additional area constraints.

A separate resistor-drive screen now sums peak branch currents into ideal
virtual-ground summers, using the same sizes rather than reoptimizing. Reserving
an independent class-A bank for those currents adds 3.012/10.284 mA to the
preferred current-optimal candidates: totals become 7.465/31.819 mA. The compact
favorable candidate (0.600 mm² at 0.9 fF/µm²) becomes 7.560 mA, leaving
8.440 mA of support. This is a conservative reservation, not a necessary minimum
or demonstrated consumption: phase cancellation, shared drivers and class-AB
operation can alter it. Numerator-summer implementation and nonideal virtual
grounds remain absent. The candidate remains plausible under favorable assigned
noise parameters, but the unpriced remainder is materially smaller.

Keep this mapping as a conditional candidate. The always-warm 28 mA TX driver
plus the higher-noise filter already exceeds even the 48 mA planning ceiling;
the selected operating allocation remains 44 mA. Parking/reusing driver bias is
a conditional mitigation requiring wake, settling, turnaround and package-load
verification; it does not reclaim silicon area. Complete amplifier voltage-noise
gain, actual output-driver implementation, loop stability with these capacitors, mirrors,
summer noise/current, physical common mode and nonlinear waveforms remain open.

The mapping trades noise for swing. With upper-rail input-gain excitation and
lower-rail headroom kept separate, its modeled node peak is 0.248 V for the
−65 dBm wanted / −30 dBm blocker tones, but 0.747 V for a −20 dBm blocker,
exceeding the assigned 0.606 V limit. This is a separated-rail steady-tone screen,
not a time-domain rail transition or OFDM crest-factor bound. A lower-Q-first
mapping with swapped zero pairing lowers that stress peak to 0.403 V, but costs
2.837/27.525 mA in the amplifier-only comparison and 12.296/65.351 mA
with resistor noise and capacitive drive. Retain it as a conditional headroom
alternative; even the favorable case leaves only 3.704 mA for other RF support. Ordering the real pole first is not a free headroom cure: the
examined low-Q-then-high-Q mapping needs at least 64.94 mA even in the first
scenario. None of these results is a physical NF or complete RF-chain verdict.

The table defines required activity, not demonstrated instance consumption.
Per-owner current must be the sum of the enabled instances, including leakage,
converter event charge and bias retained for the next deadline. For the current warm RF
path, the 44 mA RF allocation leaves 16 mA outside the 28 mA output driver.
That remainder must cover **both** the active RX chain and retained TX support
during acquisition, and the converse during TX. The older 37 mA fixture left
9 mA; its wake results below retain that original scope. Do not fit each chain
separately into the same allowance and then overlap them during turnaround.
Do not grant ADC gating a clock/reference saving unless the actual owner stops.

#### Current block-to-rail accounting

`analog-architecture.json:blocks.*.resource_allocation` and `resource_policy`
own the current allocation. ADCs, DACs and the reference buffer are assigned to
CONV. `selected_revision_check.py --owner-current-gate` sums the selected
RF RX/TX, wired and USB configurations by block and physical supply branch;
it applies the selected clock-source override once and checks the mode ceiling.
No overlap credit or transfer of converter current to CORE/RF/PLL is assumed.
Per-bond current limits and dynamic isolation remain unqualified.

The filter sizing screen compares the paired RX filters with their own itemized
allocation, currently 4 mA total. Budgets assigned to other RF blocks are not
available to the filter. A result above that allocation requires a design change;
a result below it still needs circuit and joined signal-quality verification.
The current sizing screen's minimum paired estimate including resistor noise
and separate capacitive drive is 4.407 mA; its added separate resistor-drive
reservation raises the minimum to 7.251 mA. None of the 24 combined candidate
costs fits 4 mA. These conditional realization estimates do not rule out a
different topology, but the candidate cannot claim fit from a 16 mA aggregate
RF remainder.

The previous seven-domain converter-current redistribution sweeps represented
a superseded architecture and are available only in Git history.

For a parked TX driver, a 28 mA wake step illustrates why a settling-time label
is insufficient. With the candidate 500 pF local capacitor, an unsupported step
would initially change voltage at `I/C = 56 mV/ns`. An illustrative 50 mV
excursion uses only 25 pC, exhausted in 0.893 ns; supplying 28 mA for the assigned
2 us settling interval requires 56 nC. The capacitor therefore cannot fund wake
by itself. The selected 2 ohm branch adds 56 mV steady droop for that extra
current; its 2 nH inductance contributes 56 mV for a 1 ns linear current ramp,
or 0.56 mV for a 100 ns ramp. These are separate limiting calculations, not an
additive waveform prediction or an accepted 50 mV ripple specification. The
coupled feed/return network must supply the charge and bound ringing, timing
error and reference disturbance throughout wake.

The selected mathematical output-enable model uses a 50 ns exponential unmute
and a 20 ns linear normal-mute fall. Normal mute begins at the actual completion
or commanded stop event; RF energy may persist for those additional 20 ns, and
RX admission must account for that tail. It cannot start early using knowledge
of future payload. Underflow/fault still uses an ideal abrupt cut as a separate
stress assumption. Neither behavior qualifies physical switch isolation or
emissions. The complete waveform report records mute completion separately from
last DAC consumption. These are generic enable controls, not a protocol profile.

The waveform-dependent sensitivity uses an explicit candidate law:
`I_driver(t) = 28 mA - 7 mA * min(|V_open(t)/1.2 V|², 1)`.
It includes the modeled output-enable envelope, so mute retains 28 mA and
transmitted activity releases at most 7 mA. The fixed voltage normalization
uses no future packet peak. This explores imperfect current steering within
the existing reservation; it is not a fitted physical law or evidence that
all drivers consume less current when transmitting. Positive excess-current
hypotheses require their own allocation or a smaller standing-bias choice.

The selected differential path now propagates the original held envelope-current
samples through the passive network's finite modes and algebraic feedthrough,
including the assigned 200 ps current pole. Exact held-input state recurrences
retain initial zero incremental state and the natural relaxation tail; current
is not averaged onto a coarse grid before the frequency-dependent network.
The resulting rail, input, return, reference and delay samples are retained at
the native source midpoints and superposed with RX recharge in absolute time.
A requested coarse grid is recorded as metadata, not applied to this path.
The native response also returns a serializable state at the end of the supplied
current window. A later window can restore it and decay the same modes through
an explicitly zero-incremental-current idle gap. Forecast quiet tails are not
committed history: when later activity arrives, replace the forecast after that
boundary rather than adding a second copy of the inherited state. Overlapping
windows or incompatible network/observer parameters are rejected; a physical
network change needs an explicit state mapping. These continuation rules apply
to the modeled load perturbation and do not establish RF filter/bias readiness.

The coarse FFT algorithm remains an explicit diagnostic and single-ended legacy
path; its charge conservation alone does not establish waveform fidelity.

Native output interpolation, source-waveform sampling, floating-point modal
reconstruction and the physical current law remain uncertainties. Extending the
zero-current tail is not source-grid refinement. The reply is rerun with
perturbed reference, rail gain and threshold-event timing; RX recharge still
uses its separately scoped guarded FFT. Current-law variation, RF-cycle switching
and a causal full-state lifecycle remain requirements.

**Decision:** retain warm/muted operation as the fast-turnaround baseline and
parked bias as a power-saving alternative with a longer, measured-in-model
readiness sequence. Neither changes the constant-current evidence already
reported. The next joined transition must use the same supply state through
RX drain, DAC prefill, unmute, TX mute and RX recovery; a fresh quiet initial
condition at each phase is invalid. Require both valid timing and settled
analog conditions before asserting ready. Physical RF isolation and overload
recovery remain necessary even when RX payload is disabled during TX.

### Continuous-state wake/mute screen

`robustness_envelope.py --analog-wake` now solves the same candidate supply and
return circuit in the time domain. Feed/branch/return inductance, board and die
capacitor ESR/ESL, capacitor voltages and inductor currents persist throughout
a local load ramp up, hold and ramp down. Matrix-exponential state propagation
avoids a transistor simulation; this nine-case screen runs in about one second.
Independent nodal frequency-domain comparisons check the state-space transfer.
The consolidated report retains the results in `analog_wake`.

For the nonideal 500 pF candidate, the full 28 mA reservation ramp produces:

| Linear ramp duration | Maximum incremental droop | Assigned clock shift, peak | Recovery below 1 mV after ramp-down ends |
|---|---:|---:|---:|
| 20 ns | 59.36 mV | 5.94 ps | approximately 90 ns |
| 100 ns | 59.36 mV | 5.94 ps | approximately 50 ns |
| 1 us | 59.36 mV | 5.94 ps | already below at ramp end |

The settled drop is the independent DC result
`28 mA * (0.1 + 2 + 0.02) ohm = 59.36 mV`. Slowing the ramp does not remove that
drop. Timing uses the already assigned 0.1 ps/mV response with a 1 GHz pole;
it is a changing delay offset, not a newly measured RMS jitter specification.
The 7 mA sensitivity cases scale linearly to 14.84 mV and 1.48 ps. Ideal warm
constant-current bias gives zero *incremental* disturbance in this test, not
zero total chip ripple. The sampled damped network shows no material positive
overshoot for these ramps; that is not guaranteed across package uncertainty.

**Decision:** keep controlled parked-bias wake as a credible candidate to test
in the joined lifecycle; this passive network alone does not rule it out on a
2 us timescale. Warm operation remains the conservative fast-response baseline
until the joined test passes. The 1 mV marker is diagnostic, not an acceptance
limit. Converter/filter readiness, RX isolation/overload recovery, TX emissions
and supply-induced source retuning are not included. Host ripple, source noise
and the correct initial DC condition must be combined with this perturbation.
In particular, a parked-to-active 28 mA change goes from a hypothetical 9 mA RF
load to 37 mA; do not add it on top of an already charged 37 mA warm reservation.
Actual residual warm-bias load modulation still needs its own bound. No packet
or protocol gains a pass from this screen.

### Area ownership and fit decision

The contract's allocations sum to the full 12.92 mm² ceiling. The 2.77 mm²
reserve is the only explicit closure allowance; there is no additional free
area outside that sum. Assign support circuits to these owners before claiming
fit. The following is an accounting boundary, not a physical area estimate.

| Allocation | mm² | Must cover |
|---|---:|---|
| Wired | 2.35 | RX/TX analog frontends, termination/detection, shared USB/TMDS electrical functions, local bias and switching |
| RF | 2.40 | Both fabricated RX and TX paths, mixers, filters, gain stages, output drive, RF switching and local bias |
| Converters | 1.30 | I/Q ADC and DAC paths, sampling networks, reference generation/buffering and local reference decoupling |
| Timing | 1.60 | Autonomous sources/loops, external-clock receiver, wired CDR, phase generation, dividers and distribution |
| Digital | 1.65 | Host/control logic, generic events, clock/reset/epoch controls, diagnostics and non-storage state |
| Memory | 0.85 | All physical elastic/CDC/playback data storage; exclude it from digital totals when separately accounted |
| Closure reserve | 2.77 | As-yet unpriced shared bias/power conditioning, supply decoupling, isolation/guard spacing, routing and growth beyond owner allowances |

Provider peripheral pad-ring area lies outside the allocated core rectangle.
Custom signal-pad circuits must fit compatible sites; any circuitry extending
into the core consumes its owner's allowance or this reserve. Do not count the
space outside the core as available analog area without a geometric check.
Both RF and wired implementations consume area even when disabled. Shared
blocks count once only after their connectivity and simultaneous-use obligations
are established. Regulator/filter/decoupling alternatives consume real area and
headroom; they are not free consequences of drawing separate logical rails.

**Decision:** retain these allocation caps and the provisional subdivisions
above. Final fit remains unproven until layout; mathematical architecture work
uses the rough allocations now and revises them only for identified conflicts. An allocation sum
passing is only arithmetic consistency. It is not evidence that ADC precision,
clock isolation, pad protection and required timing can coexist in that space.

### First quantitative reserve boundary: local capacitance

The six functional allocations consume 10.15 mm², leaving 2.77 mm² for
closure. An inexpensive arithmetic screen already limits a potential supply
mitigation: large on-die capacitors. Using `A = C / density`, ideal plate area is:

| Additional local capacitance | 1 fF/µm² | 1.5 fF/µm² | 2 fF/µm² |
|---|---:|---:|---:|
| 100 pF | 0.100 mm² | 0.067 mm² | 0.050 mm² |
| 1 nF | 1.000 mm² | 0.667 mm² | 0.500 mm² |
| 2 nF | 2.000 mm² | 1.333 mm² | 1.000 mm² |
| 4 nF | 4.000 mm² | 2.667 mm² | 2.000 mm² |

These are nominal plate-only lower bounds, not placed areas. The published
[MIM specifications](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_6_4.html)
list these three process options, with only one type per process flow. They
list minimum densities of 0.9, 1.27 and 1.8 fF/µm² respectively. For example,
obtaining at least 4 nF at those minima requires 4.444, 3.150 or 2.222 mm²
of ideal plate. Available shuttle option, geometry overhead, connections and
high-frequency effectiveness still require verification. This screen does not
select an option or establish usable capacitance at GHz frequencies.

**Decision:** do not treat several nanofarads of local decoupling as a free
fallback. Even with the densest listed option, 4 nF guaranteed by the listed
minimum density would leave only 0.698 mm² of the reserve before routing,
isolation and other support. The other options exceed the reserve for that
capacitance. A 100 pF candidate is comparatively inexpensive, but its ability
to suppress the shared disturbance remains a separate electrical requirement.
Capacitance already charged to a functional owner's allocation must not be
charged again; these numbers describe additional support paid from reserve.

The decision screen for a supply mitigation is therefore joint: required
capacitance and isolation impedance, residual rail/timing disturbance, DC
headroom, and remaining area. External capacitance remains welcome but must
retain bond/board impedance; it cannot be substituted for local capacitance
at high frequency solely because its nominal value is larger.

### Joint capacitance and supply screen

A paired RF/wired calculation using the existing `operating_environment`
model gives a useful mitigation candidate. Hold the common feed/return,
2 Ω local branch, board 1 µF network and adverse 7 pC H2D charge fixed;
change only `shared_board_candidate()['network']['die_c']`. RF uses 2.437 GHz,
D2H word rate LO/16, 37 mA payload and six D2H harmonics. Wired uses 2.5 GHz,
312.5 Mword/s and 96 mA payload. All other environment arguments retain their
defaults. RF and wired run separately, as required.

| Local capacitance | RF conservative rail interval | Wired conservative rail interval | RF / wired resolved ripple RMS |
|---|---|---|---|
| 100 pF | 2.258–3.891 V | 2.127–3.765 V | 358.6 / 424.2 mV |
| 500 pF | 2.928–3.220 V | 2.822–3.069 V | 47.8 / 50.2 mV |
| 1 nF | 3.010–3.138 V | 2.891–3.000 V | 20.4 / 21.7 mV |
| 2 nF | 3.044–3.104 V | 2.920–2.971 V | 9.4 / 10.1 mV |

Intervals are DC ± sum of harmonic peak magnitudes, not observed excursions.
The 500 pF case restores containment within the fixture's 2.5–3.6 V validity
window for these assigned cases. That window is not a qualified operating
specification. At the listed minimum densities, 500 pF costs 0.278–0.556 mm²
of ideal plate, materially less than the 2.77 mm² reserve. Thus moderate local
capacitance is worth carrying forward alongside reduced host activity and
clock/reference rejection; multi-nanofarad capacitance is not yet necessary
for this particular voltage screen.

The executable `local_decoupling` screen now extends that calculation with
series capacitor resistance and connection inductance. Run
`python3 verification/robustness_envelope.py --local-decoupling` from the
project directory; the full report includes the same results. For 500 pF:

| Series R / L | RF rail interval | Wired rail interval | RF / wired supply-induced timing RMS |
|---|---|---|---|
| Ideal | 2.928–3.220 V | 2.822–3.069 V | 4.64 / 4.84 ps |
| 0.1 Ω / 50 pH | 2.948–3.200 V | 2.842–3.049 V | 4.22 / 4.36 ps |
| 0.5 Ω / 200 pH | 2.950–3.198 V | 2.836–3.055 V | 3.56 / 3.73 ps |
| 1 Ω / 1 nH | 2.837–3.311 V | 2.697–3.194 V | 6.03 / 7.14 ps |

Timing uses the existing assigned 0.1 ps/mV transfer with a 1 GHz pole;
it excludes source noise from this subtotal. The finite grid is not a physical
parasitic bound or a proof of monotonic behavior between samples. Connection
inductance can improve particular sampled harmonics before worsening others;
do not interpret the middle rows as generally beneficial inductance. All eight
500 pF and all eight 1 nF sampled mode/parasitic combinations meet the fixture
voltage window, but the maximum supply-induced timing RMS is 7.14 ps for
500 pF versus 7.57 ps for 1 nF. More capacitance is not a monotonic timing fix.
Network checks independently verify current conservation, passive power balance
including capacitor ESR loss, ideal-return reduction and capacitor-disconnection
limits. They validate the equations, not physical parameters.

**Decision:** keep 500 pF–1 nF as an unselected mitigation range and retain the
100 pF baseline as a failing control. Sampled nonideal cases preserve the
500 pF candidate's voltage benefit, but residual timing variation remains
material. Do not yet change the normative network. Distributed placement,
continuous switching spectra, carrier coverage, startup current and the
physical realization of the local 2 Ω branch remain open. Voltage containment
does not prove TX emissions, RF sensitivity, serial jitter tolerance or a narrow
regulated operating point. Propagate candidate spectra through payload-quality
observers before selecting the mitigation.

Local capacitance, ESR/ESL and branch isolation remain physical hypotheses.
Compare candidate networks using the current current inventory, delivered
clock and absolute RF signal levels. Voltage containment and clean decoding
must be reported separately; neither establishes transmitter emissions or
blocker-limited sensitivity. A quieter supply does not pay for a lower NF,
higher input IIP3 or additional gain. Retired packet and synthetic-waveform
counts from the earlier fixed-current ledger are not acceptance evidence.

### Storage placement policy

Keep packet buffers, capture history and waveform storage in the external FPGA.
On-chip storage is for bounded clock crossings, serializer/converter service and
short transport interruptions. Do not size a chip buffer to hold a whole packet
when a paced stream can meet the same requirement. Reduction requires an explicit
host service envelope, occupancy bound and underrun/overflow behavior; external
storage cannot compensate for a missed response deadline or missing wire sample.

The playback model now accepts `playback_capacity_bits` and reports peak queued
bits. Its 2,048-bit default remains a comparison allocation until the smaller
candidate has a service bound; it is not a required packet buffer size. A finite
4,096-bit paced-response screen delivered with 128 bits (peak 66 bits) at
±100 ppm across selected phases; 64 bits overflowed. The selected packet/ACK
path peaked at 36 bits and met the fast-host deadline in its sampled cases.
Exact settings are in the closure inventory’s `playback_capacity_screen`.

External decoupling and RC/LC supply filtering may use many SMD components;
external passive count is not a constraint. Compare such networks with local
on-chip reservoirs, accounting for package/board impedance, component loss and
regulator/loop stability where relevant. External capacitors do not automatically
replace local charge storage behind package inductance. The
[passive allowance](../../../docs/roadmap/programmable-transceiver-pin-plan.md#external-passive-component-allowance)
owns this design decision; added supply/filter access still consumes terminals.

## Legacy logical allocation within 50 entries

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

The public native input-cell characterization now provides an energy reference,
not a pulse-shape fit. At pinned PDK commit
`2aeec51ea2824b6cc0b396acfc39f4535f40b23a`,
[`in_c`, TT 3.3 V / 25°C](https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_io/blob/2aeec51ea2824b6cc0b396acfc39f4535f40b23a/cells/in_c/gf180mcu_fd_io__in_c__tt_025C_3v30.lib)
records PAD capacitance 3.135837 pF and signed internal-energy tables across
0.08/0.5/1 ns input slew and 0–0.5 pF Y load. Summing rise and fall gives
2.48178–2.77922 pJ per cycle, equivalent to **0.376–0.421 pC per transition**
on average. Adding the separate `Cload*V²` output switching term gives
0.376–1.246 pC across the same grid; do not count that load again if CORE already
owns it. Internal-power energy units are V²·C, not leakage-power units; this
matches `energyScale()` in the [OpenSTA reader](https://github.com/parallaxsw/OpenSTA/blob/master/liberty/LibertyReader.cc).

This is PDK characterization of a native cell, **not measured silicon**, a
custom host-receiver qualification or a bound on transient peak current. Negative
rise entries must not be clipped or turned into negative passive pulses: use
the signed full-cycle energy. Keep 7 pC as an adverse assigned input-receiver
case, not a typical value inferred from this library. The 100 ps smoothing
parameter remains unrelated to the tabulated *input voltage slew*. Rail-port
allocation, receiver implementation and current time shape remain open.
The pinned source hashes and full small tables are retained in
`evidence/selected-revision-check.json:host_input_library_evidence`; reproduce
with `selected_revision_check.py --host-source-evidence` (network required).


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

## Pinned PDNSim load-model restriction

The pinned OpenROAD commit `dcf36133a369abc8f3c5e5738cd4d82e4903c0e0` does not implement `set_pdnsim_inst_power` as a current override. In [buildNodeCurrentMap](https://github.com/The-OpenROAD-Project/OpenROAD/blob/dcf36133a369abc8f3c5e5738cd4d82e4903c0e0/src/psm/src/ir_solver.cpp#L831), automatic STA-derived current is added first; user-specified current is then added to the same node map. The separate per-instance power map is overwritten and supplies the printed total, producing a misleading apparent override.

The zero/24/48 mA control matrix confirms this behavior at all 26,438 load sources on both rails, within export rounding. Approximately 34.105 mA of automatic modeled current remains at zero user load. **That residue is not a measurement or qualified estimate of actual CORE consumption.** These runs have no qualified switching activity, clock-tree power or complete physical design.

Use PDNSim's exported resistor topology with the independent explicit-current solver for the present specified-load sensitivity screens. Do not interpret direct PDNSim voltages as belonging to the requested user-load total, or accept the printed total without auditing the exported current sources. For any future PDNSim flow, require a zero-load control and source-by-source current audit before trusting the solve. The former full-top flow is retired with its obsolete netlist. No binary patch is applied. If the tool revision changes, independently requalify this behavior; do not carry either the bug assumption or an override assumption into a new build without tests.

The independent solve still has nominal resistor models, ideal local feed locations and assumed fixed current distributions. It does not close IR/EM, package effects, process variation, dynamic noise, transistor behavior at reduced supply, or full-chip power signoff. Pass-48 explicit-current results and pass-49 conditional path bounds remain the relevant retained calculations; the diagnosis explains why the earlier direct tool results were rejected.

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

The [8 pF host screen](host-driver-selection.md#artix-load-baseline) exceeds HOST_B's planning ceiling after the existing allowances (63.54 mA versus 55 mA), even at nominal temperature and voltage. The two-segment allocation remains a candidate and is not closed for this load. Passing the earlier 5 pF executable screen does not supersede this negative evidence.

Pass 9 [native driver comparison](host-driver-selection.md): 12 mA mode reduces the same 8 pF HOST_B estimate to 55.75 mA with unchanged allowances, still above 55 mA. No driver or current ceiling is changed by this experiment.

Pass 10 [8 mA candidate](host-driver-selection.md#8-ma-candidate): the nominal 10 pF HOST_B estimate is 53.80 mA with unchanged allowances. This passes the limited planning comparison but leaves only 1.20 mA headroom; no package/bank/operating-envelope closure is implied.

## Coupled mathematical load accounting

The active `behavioral.SharedRail` accepts an explicit constant
`bias_current_a`, in addition to host/converter/FIFO charge impulses. RC/RLC
intervals solve about the loaded equilibrium (droop R·I, feed current I), and
the pulse and sampled synthesizers use the same loaded voltage integral.
Reports separate integrated bias charge from total charge and retain charge
balance. This current remains active throughout that rail object's lifetime;
mode-dependent current switching is not implied. The independent matrix-
exponential check covers the RLC affine state equations, alongside the RC
closed form. The default stays zero for historical comparisons, so callers
must explicitly declare a load to claim bias-current coverage.

The independent nonlinear TX diagnostic passes with a declared 12 mA load:
minimum rail 3.22357 V, 6.1553% EVM and zero bit errors under its unchanged
limits. This is a conditional DC-load sensitivity, not a derived driver-current
estimate or a complete mode-dependent current inventory. Output swing remains
prescribed within the accepted rail range; signal-dependent current, headroom,
impedance and efficiency still require a coupled output-stage model.

An optional `tx_electrical_budget` now checks the observed TX envelope against
declared voltage/current/energy bounds. The single-ended internal Thevenin
source is centered at VDD/2 with 0.3 V headroom to each rail and an explicitly
AC-coupled 50-ohm load through 50-ohm source impedance. A 3 mA driver allocation
is reserved within the already charged 12 mA rail load, with a 2 mA output
current limit; it is not added twice. The nonlinear live TX capture needs
0.103224 V peak source swing and 1.03224 mA peak load current, within the
declared bounds at the observed minimum 3.22357 V rail. Peak-envelope RF power
in source plus load is 53.2758 µW versus at least 9.6707 mW allocated DC power.
The 6.1553% EVM result retains the unchanged quality limit. This conservatively
compares minimum rail and peak envelope; a failed bound rejects qualification
but does not synthesize a clipped waveform. Unit controls reject low headroom,
insufficient peak current and bias allocations that exceed the live rail load.
These assumptions still need device/noise/impedance validation.

The pin contract has `RF_TX_P/N`, so the compliance helper now distinguishes
differential from the earlier single-ended sensitivity case. For differential
operation, voltages and impedances are across both pins and each leg's swing is
half the differential swing. This doubles voltage headroom for the same per-leg
rail margins; it does not double available load current or supply power.

Time-weighting the reduced-drive OFDM payload at its actual converter intervals
gives 9.93005 µW average load power and an 8.8342 peak/average power ratio.
Reaching the retained 1 mW planning value by linear scaling would require
18.7981 mA peak current and 1.87981 V peak open-circuit differential swing at
the declared 50-ohm source and load impedances. These are required capabilities,
not evidence that the original 3 mA driver allocation can supply them.

A separate candidate increases the voltage scale from 0.5 to 5.02 V per
normalized unit, reserves 20 mA for the driver, and charges 29 mA total constant
bias to the rail. With the actual synthesizer and nonlinear output assumptions,
it delivers 1.00096 mW average during the diagnostic payload at 6.3056% EVM
and zero errors. Across training plus payload, peak load current is 19.4654 mA
and peak source swing 1.94654 V; minimum rail 3.18979 V allows 2.58979 V
differential swing under the declared 0.3 V per-leg headroom. This allocation
is below the RF domain's 48 mA planning ceiling, but the full current/area
inventory is not closed. It is a revised candidate, not a passing result for
the old 12 mA rail budget. Noise, arbitrary waveform peaks, emissions, matching
loss and physical driver bandwidth/linearity remain unqualified.

The subsequent 32-seed fast OFDM crest screen rejects seven payloads at the
20 mA limit, with no DAC clipping. Seed 977 is worst: the full host/synthesizer
run demands 26.2687 mA and 2.62687 V, violating both the declared current and
voltage bounds even though in-band EVM passes. Thus the seed-953 result above
does not establish an adequate driver envelope.

A revised candidate declares 40-ohm total differential source resistance,
50-ohm load, 4.518 V/unit voltage scale, 28 mA driver allocation and 37 mA total
rail bias. Reducing scale in proportion to source-plus-load impedance preserves
delivered voltage/current; it reduces required internal source swing, not load
current. All 32 fast-screen payloads fit the revised current limit. The worst
seed's full run gives 0.998967 mW average payload power, 6.4493% EVM, zero errors,
26.2687 mA peak current and 2.36418 V source swing versus 2.57657 V allowed.
The RF planning ceiling leaves 11 mA before additional unaccounted loads.
Neither the finite seed set nor midpoint-observed peaks bound every waveform;
noise, emissions, impedance realization and a complete current/area inventory
remain necessary. Both earlier failed electrical budgets remain recorded.

Electrical qualification now uses interval-end peaks instead of only midpoint
observations. Within each held-DAC interval the one-pole envelope traces a line
segment in complex I/Q. Affine imbalance/leakage retains that line segment;
magnitude is convex, and the output model's cubic radial law is checked to be
monotonic. The maximum therefore occurs at an endpoint. Unit-magnitude LO
rotation cannot increase it. This bound follows the actual nonuniform DAC
intervals in the live model and is retained across transfer chunks.
The revised 32-seed screen still passes, with worst uniform-clock current
26.3146 mA. The full worst-seed run bounds current at 26.3096 mA and source
swing at 2.36787 V, retaining 6.4493% EVM and zero errors. These replace
midpoint maxima for qualification of this model; higher-order filters,
reactive matching, output noise and physical overshoot require their own bounds.

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

This is the intended physical partition, not the reconciled executable budget
or validated rail routing; see the logical/physical reconciliation above. Local
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

One slot means approximately 3.93 × 5.12 mm, not 1 mm². Retain the
conservative 12.92 mm² core ceiling. The logical 37-signal + 14-power/ground
allocation is not a physical bond map: the pinned provider template has 56
signal sites plus 18 fixed supply/return sites. Public Run 1 assembly has 74
die bonds and 70 numbered connector contacts. These counts describe different
boundaries and do not contradict each other. The selected assembly remains
provider-compatible COB; the selected 74-site physical allocation supersedes
the original approximate 50-total constraint.
Logical domain allocations are accounting groups, not established independent
external rails. The [pin plan](../../../docs/roadmap/programmable-transceiver-pin-plan.md)
owns provider provenance and the candidate signal assignment.

Reserve **0.80 mm² within the existing 3.72 mm² closure reserve** for expansion:
0.35 wired/USB local circuits, 0.15 timing/rate controls, 0.10 RF bandwidth/gain
controls, 0.15 digital event/streaming helpers and 0.05 configuration memory.
A further 0.15 mm² is assigned to differential clock input conditioning.
The residual reserve is 2.77 mm². These are allocation caps, not transistor area
estimates. No reduction in return pins, baseline buffers or converter performance
is assumed. If the allocation fails, revisit sharing/circuit choice and report
the conflict; do not quietly drop a requested capability or expand the die.

Power is not justified by this area reservation. Add selected-mode current and
switching loads for every new branch to the same logical-domain ledger and shared physical supply/return model. RF/wired
exclusivity can reduce active demand, but does not establish available current
on a particular physical feed or remove shared-return noise. Inactive branches still
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

The [complete numerical experiment record](https://github.com/deepai-org/svalbard/blob/32aa5622d72b53d566cd8ed5100b2a67e1818b99/projects/programmable_transceiver_platform/spec/power-partition.md#historical-quiet-rail-numerical-diagnostics)
retains decks, checkpoint tables, raw-archive locations/hashes and intermediate
interpretations. These experiments do not qualify switching or replace current
power allocations. They used quiet low inputs, native 8 mA pads, 10 pF loads,
unequal signal inductances and selected 0.25 ohm/2 nH supply/return paths.

| Check | Retained result | Reproduction / report |
| --- | --- | --- |
| One-nanosecond startup | Ideal, supply-only, return-only and both-rail runs completed; tiny terminal residuals do not establish physical noise | `verification/run_rail_startup.sh`; [report](../evidence/rail-startup-screen.json) |
| Checkpoints to 12 ns | Ideal completed; supply-only timed out after its last saved 1 ns checkpoint, return-only/both after 2 ns checkpoints | `verification/run_rail_checkpoints.sh`; [report](../evidence/rail-checkpoint-screen.json) |
| SPARSE/KLU comparison | Both solved ideal rails; shared rails timed out with SPARSE and aborted at initial DVSS with KLU | `verification/run_rail_solvers.sh`; [report](../evidence/rail-solver-screen.json) |

A last saved checkpoint is not the exact timeout point. Small saved rail motion
neither proves stability after that window nor excludes hidden-node problems.
Checkpoint pauses affect timestep history. Solver comparisons must preserve
physical decks, tolerances and initialization; changing damping merely to finish
a run would not resolve the underlying uncertainty.

After transient abort, ngspice may write single-row operating-point data under
waveform filenames and even exit zero. The corrected analyzer rejects single-row,
non-finite, non-increasing-time and wrong-endpoint traces before statistics, and
recognizes abort messages separately from normal checkpoint pauses. It rejects
all five shared-rail KLU snapshots; the corrected report is analysis of retained
runs, not a successful resimulation. Distinguish collection success from circuit
success and preserve both false-stability and false-instability concerns.

## Host-ground solver verification

`verification/host_ground_solver_check.py` compares a piecewise-linear ground
solution with the Brent solver, checks return-current conservation and compares
switched trajectories at three numerical tolerances. Both implementations must
reject a supply-floor violation without committing partial state or charge.
The explicit fixture has one resistive supply branch and eleven 10 pF loads;
it is a simplified circuit, not the selected package or GPIO model. The
candidate solver is not installed by running this check. Physical host capture
and joined supply/clock behavior remain separate qualification obligations.

## TMDS electrical and multi-die power budget

For the illustrative 8 mA / 50 ohm / 3.3 V DC sink model, one active lane draws
26.4 mW from its termination supply: 23.2 mW dissipates in the transmitter sink
and 3.2 mW in the receiver termination. Three lanes total 79.2 mW before clock,
PLL, host, bias and digital overhead. Source and sink may be on different boards;
do not charge the entire termination supply power to both chips. An external
clock-pair buffer adds separate power. This is a static hypothesis, not a complete
die budget. Preserve provider fixed supply/return sites; the earlier logical
14-terminal allocation is not the assembly map. Check common-mode,
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

## Wired mitigation requirements, before circuit sizing

The consolidated robustness report's `wired_resource_requirements` records
inverse constraints at 2.5 Gb/s. It does not claim physical implementation fit.
The 48 mA PLL allocation supports at most 4.36, 2.91 or 1.45 pF of equivalent
full-swing clock capacitance at 3.3 V when other clock circuitry consumes 12,
24 or 36 mA respectively. Equivalent capacitance includes activity/frequency
ratios; account for each load once. Low-swing clock networks require a separate
static/dynamic model. A cleaner external source still leaves input conditioning,
local distribution and independent incoming-data CDR costs.

For a hypothetical single internal driver pole, tau=C/gm implies that reducing
the time constant from 100 to 50 ps doubles required effective gm at unchanged
capacitance. At 0.5 pF internal capacitance and assumed gm/Id=10 V⁻¹, the conditional
pole bias increases from 0.5 to 1 mA. These are topology assumptions, not device
characterization or a complete driver estimate. The internal pole capacitance
is distinct from the pad load: reducing the latter from 2 to 1 pF needs an actual
ESD, pad and package solution. No area estimate follows without geometry and
parasitic information. Serializer, level shifting, RX, CDR and leakage remain
unpriced in this screen.

The modeled differential output uses one 8 mA tail total. Its 3.3 V termination
source supplies 26.4 mW, shared between termination resistors and chip dissipation.
An external termination supply moves that source power off chip but still loads
chip returns; it does not remove die dissipation. Pad charging is already supplied
by this path: do not add a separate C*V*f term to the same current-steering tail.
The report subtracts tail and conditional internal-pole bias from the aggregate
96 mA WIRE **return** allowance. That residual is not unused supply capacity or
a whole-lane estimate, and it does not prove either individual 48 mA connection
is adequate. Area, per-connection allocation and joint fit remain unresolved.

## Joined RF, clock and host planning screen

`joined_rf_resources` in the consolidated robustness report now costs the
existing hypotheses together: 37 mA RF reservation (including the 28 mA driver),
clock static bias plus equivalent switched capacitance, 20 mA assumed CORE current,
and the host's 10 pF external loads plus 7 pC internal charge per changed output.
RF output power divided by an assumed efficiency is **not** added again to the
same driver reservation. Inactive leakage and unimplemented internal loads remain
unpriced; allocation headroom is not measured spare current.

The external-LO candidate provides the host's outgoing clock at LO/16 and DDR
word rate at LO/8. Five data outputs per bank use symmetric rising probabilities
0.25 (random) or 0.5 (alternating). Internal transition probability is twice the
rising probability; the forwarded clock changes on every DDR word. At alternating
activity, HOST_B draws 44.30, 44.95 and 45.78 mA at the three tested LO settings,
including internal charge. Its 55 mA ceiling is a planning limit, not GPIO timing
or pad qualification. Host arithmetic capacity passes at the same settings;
finite transport and actual FPGA timing are still open.

| Assigned clock bias / equivalent switched load | 2.400 GHz | 2.437 GHz | 2.484 GHz |
| --- | --- | --- | --- |
| 12 mA / 1.5 pF | Allocation screen passes | Passes | Passes |
| 24 mA / 3 pF | Passes | PLL ceiling exceeded | PLL ceiling exceeded |
| 36 mA / 3 pF | PLL ceiling exceeded | PLL ceiling exceeded | PLL ceiling exceeded |

The first row at alternating host activity draws about 0.536–0.546 W from the
modeled chip supplies. This is supply-power accounting, not die heat: pad/load
energy flows and package thermal impedance are not modeled. External oscillator,
board components and FPGA power are additional. Droop uses the existing simple
2 ohm feeds and 0.1 ohm shared return; dynamic PDN and substrate effects require
their separate models. Signal-quality runs have not all been rerun at these
exact rails and activity spectra, so this table does not close joint operation.
The RF reservation also does not prove simultaneous RF TX/RX current or capability.

### DC rail fed back into signal quality

`rf_dc_quality` now reuses the joined budget's exact RF DC rail in the spectral
receiver at 2.437 GHz, for the lower-load clock hypothesis. Random and alternating
host data produce 3.21320 and 3.20962 V respectively. Both use the same explicit
board loss and configured gain restoration as the earlier receive comparison.
The test verifies that actual modeled PGA signal amplitude changes with the
rail ratio, rather than merely copying supply values into metadata.

With the assigned clean external clock, 20 dB board blocker attenuation and 1 mV
residual ripple, diagnostic EVM is about 8.54% at both rails. A noisy external
source remains around 18.5%; 10 mV ripple gives about 58% for the clean source.
Thus the modeled DC drop alone does not break this selected candidate, while
clock/supply quality still does. These are one-realization conditional results
under 65 MHz/V residual pushing, not a statistical or protocol qualification.

Only DC accounting is joined here: ripple amplitude remains an assigned stress,
not a prediction from the joined budget's switching current. Supply-dependent
ENOB, filter poles, compression, tuning and actual headroom are not modeled by
scaling RF gain. Area, physical current, thermal behavior and dynamic coexistence
remain open; this is not whole-chip resource-and-quality closure.

### Host charge propagated through the clock-supply network

`host_charge_coupling` includes the same 7 pC output-transition hypothesis in
the host data-activity tone, alongside 10 pF capacitive loads. At 2.437 GHz LO
and random host data, a 50% sinusoidal modulation of activity creates a 17.90 mA
peak 1 MHz current tone, versus 12.57 mA from capacitive loads alone. Rising
probability ranges from 0.125 to 0.375; this modulation is not applied around the
maximum alternating-data activity, which would exceed the physical bound.
Clock switching and static bank bias contribute to DC but not this data-activity
tone. Internal and capacitive activity envelopes are assumed coherent.

| Board hypothesis | Differential clock-rail ripple | Diagnostic RX EVM with board blocker filtering |
| --- | --- | --- |
| 10 uF, 50 milliohm ESR | 1.236 mV peak | 9.40% |
| 20 uF, 50 milliohm ESR | 1.231 mV peak | 9.36% |
| 10 uF, 20 milliohm ESR | 0.722 mV peak | 7.74% |

These use the existing series damping and assigned 20 milliohm / 0.5 nH shared
return. More nominal capacitance alone provides almost no improvement at this
frequency; impedance, including ESR and return paths, matters. The 10 kHz–1 GHz
network scan still peaks near 275 MHz at about 5.4 ohms; a 1 MHz improvement
does not establish broadband immunity. Capacitor values/ESR/ESL are hypotheses,
not selected characterized components, and no measured host spectrum is claimed.
Unfiltered-blocker cases still fail.

For this explicit shared clock/host feed, allocated constant host and clock
currents imply a clock-victim DC rail of 3.108 V, including damping/return drops.
The RF waveform continues to use the separate budget's 3.213 V RF rail. This is
a particular coupling topology, not a complete multi-rail package network.
The source spectra and 65 MHz/V residual pushing remain assigned; clock startup,
tuning, additive noise and bias at 3.108 V have **not** been demonstrated. Lower
ESR fixes neither that DC drop nor the missing clock operating-point evidence.
Thus the waveform result remains conditional even though current, network
phasor and RF gain assumptions are now connected more explicitly.

### Preserve clock DC voltage without removing branch damping

The same host-charge/network study now compares a 0.1 ohm shared board feed
against the earlier 2 ohm feed, retaining the clock branch's 2 ohm series damping,
inductances and return hypothesis. At the same allocated constant currents, the
clock rail rises from 3.108 to 3.243 V. Shared-feed resistor loss falls from
10.09 to 0.50 mW; clock-branch series loss remains about 1.16 mW. This is a board
impedance target, not a selected regulator or a verified source impedance model.
No signal/supply pin reassignment or additional on-chip storage is involved.

| Lower-feed-resistance board hypothesis | Clock-rail ripple at 1 MHz | Filtered diagnostic RX EVM |
| --- | --- | --- |
| 10 uF, 20 milliohm ESR | 0.674 mV peak | 7.61% |
| Adverse 5 uF, 50 milliohm ESR | 1.015 mV peak | 8.60% |

The same allocated clock current and assigned spectra are retained; the result
does not demonstrate transistor startup, tuning or additive noise at 3.243 V.
The RF rail stays at the previous separate-budget value. Blocker-filter bypass
controls still fail. The wider network scan peaks around 288 MHz at 5.65–5.69
ohms, slightly above the original approximately 5.4 ohm peak. Consequently the
DC and 1 MHz improvement is not broadband coexistence closure. Regulator output
impedance/stability, actual component parasitics and host edge-current spectra
remain required board evidence.

## Stable RF host timing allocation

The hopping configuration adds a stopped-select mux and H2D/2 branch inside the
existing clocktree: reserve15,000 µm² and0.5 mA of its RF allocation, without a
new oscillator or pin. The bounded retune/sample-epoch state reserves192bits
in the common memory ledger. Clock-distribution activity and physical timing
remain to qualify. Existing RF sample clocks still derive from the LO.
