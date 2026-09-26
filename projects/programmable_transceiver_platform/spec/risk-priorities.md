# Current transceiver status and priorities

The [normative architecture and diagram](block-diagram.md) own selected functional
boundaries. Numerical studies below are conditional evidence, not frozen circuit
topologies or qualified component specifications.

The mathematical architecture is **incomplete**. No new schematic or layout
work until the mathematical gates are met. Conditional simulation success is
not GF180, package, FPGA timing or protocol-compliance qualification.

## Current status

| Area | Current evidence | What remains unresolved |
| --- | --- | --- |
| Autonomous analog clocks | Counted acquisition and pulse-loop behavior demonstrated under declared tuning/noise assumptions. Historical loaded transistor tuning sweep changes slope sign. | Monotonic operating branch, cold startup, physical phase-noise spectrum, supply sensitivity and clock distribution remain unclosed. |
| Wired receiver | Detector now uses four voltage observations per receiver interval; corrections affect future samples. Causality tests cover ±3 UI, monotonic sampling and independence from future payload. Existing codec/recovery assertions pass. PCIe Gen1 compliance-pattern screen reacquires across 16 phase/frequency/interruption cases. | Physical detector, jitter/holdover envelope, arbitrary serializer restart phase and real protocol acquisition. Earlier source-indexed CDR measurements are historical. |
| Wired duplex | Independent RX/TX rates, observed-clock pacing, finite queues, timeout, explicit flush/new epoch and external framed rearm are exercised together. | Serialized management/acknowledgment, complete bridge implementation, physical idle and resource accounting. Raw unframed delayed rearm remains a negative control. |
| RF TX | Loaded host/converter/driver path with pulse synthesizer and count-acquisition interlock: 6.6362% EVM, zero errors, declared voltage/current limits pass. | Physical noise/linearity/bandwidth, output emissions, driver noise, full power/area and broader waveform envelope. |
| RF RX | Same loaded clock architecture, 12 mA bias, declared 10 dB NF/gain budget: 8.4977% EVM, zero errors; whole/split execution matches. | Sensitivity/blockers/compression, standard acquisition, higher modulation orders and radio turnaround. |
| USB | Incremental external FPGA parser, finite eight-record ingress, independent processing-clock phase and two-cycle ingress synchronization budget. Ingress-only crossing passes 324 faster-host cases; adding return command crossing fails all 12 focused exchanges (fast host 452–469 ns). | Independent parser-to-frame-builder clock architecture fails. Host-DDR-clock parser passes 108 faster-host cases; a proposed three-cycle final pipeline gives 29.167 ns margin but lacks implementation proof. Actual CDC/timing, causal receive sampling, transaction acceptance and attach/reset/chirp lifecycle. Slower host fails this sweep. |
| Chip↔FPGA bridge | Wide-block transport and CDC components have separate mathematical/RTL evidence. | One consistent selected implementation, physical GPIO timing and a usable external FPGA adapter. Old scalar implementation timing failures are not resolved by model passes. |
| Whole-chip fit | Contract-derived planning ledger: 50 terminals, 12.92 mm² including reserve and 350 mA domain ceilings; implemented totals explicitly unknown. USB bridge identifies 3,792 coexisting data-bank bits, excluding unresolved metadata/control. | One complete, non-overlapping ledger for storage, clocks, logic, analog, pads, protection, package and loads. |

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

Joined spectral/PDN evidence is concentrated in HE20. BLE, Bluetooth Classic,
802.15.4 and LoRa do not inherit its complete-chain result. Likewise, the generic
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

**Next RF priority:** map the synthetic-prefix recovery to actual allowed
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

For linearity, use **−20 to 0 dBm input IIP3 as an explicitly assigned stress
range**, with −10 dBm as a diagnostic midpoint, not a deduced process value.
For two equal blockers, input-referred IM3 ≈ 3Pblocker−2IIP3. A −30 dBm
blocker pair would then produce −50 to −90 dBm equivalent IM3. A −80 dBm
wanted signal would require IIP3 ≥ −5 dBm merely to put this IM3 below it;
additional margin is needed. Compression and LO leakage are independent checks.
This exposes the value of external filtering and gain bypass without promising
an unusually linear low-power LNA/mixer.

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
Any additional analog access must fit the 50-terminal budget.

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
   external network within 50 terminals and the wafer.space slot allocation.
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
