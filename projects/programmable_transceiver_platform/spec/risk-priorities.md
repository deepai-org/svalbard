# Current transceiver status and priorities

## Current status

The selected design is a programmable analog/PHY companion with mutually
exclusive RF and wired payloads, FPGA-owned protocol processing and bulk
storage, and allowed external passives and clocks. The first chip retains the
full intended capability set. Neither complete mathematical verification nor a
complete transistor schematic or extracted chip exists yet.

`analog-architecture.json` owns blocks, settings and allocations; `contract.json`
owns external interfaces; `mathematical-closure.json` owns completion criteria.
The [pad implementation](../analog/pads/README.md) owns the current circuits and
physical gaps. Its generated layouts are partial implementations, not qualified
I/O cells. The [model guide](../system_model/architecture_fast/README.md) owns
commands and executable coverage.

The audited intended-chip tests resolve a shared design. Explicit numerical
examples and simplified/adverse fixtures remain valid exceptions. This establishes
configuration binding, not accurate physics, full protocol support or production
readiness. All 17 capability verdicts remain unresolved.

## Open-issue register

| Area | Current evidence | Unfinished requirement |
| --- | --- | --- |
| Pad protection and local safety | Shared foundation, specialized attachments, extracted local layouts and retained-network screens exist. | Clamp normal-signal release and protection stress do not pass together. Core-local protection, autonomous disable/brownout control, powered-peer isolation and full internal terminal limits remain open. |
| RF/reference pad-to-core interfaces | Protection/bias networks are implemented; LNA, RF TX and differential clock receiver still have behavioral boundaries. | Implement their physical input/output, bias, common-mode, power and loading requirements together with the protection network. |
| Package, power and clocks | Provider-compatible sites and common ring connectivity are checked. Differential external timing and a provisional low shared-return target are selected. | Actual wire loops, common supply impedance, host switching, CMRR, input excursions and supply-to-delay laws are unqualified. Autonomous startup/tuning and phase noise remain open. |
| Complete RF RX | Connected diagnostic packets exercise gain, filters, converters and clock impairments. Selected gain regulation improves retained-lifecycle EVM. | A common useful gain/noise/blocker envelope with actual preambles, false detections, overload recovery, sensitivity and PER. Downstream gain cannot repair upstream clipping. |
| Complete RF TX | Selected reconstruction, FPGA correction and interpolation pass scoped diagnostic waveform checks. | Loaded driver headroom, calibrated board power, complete packet EVM, spectral masks, images/harmonics and transitions. Diagnostic relative energy is not a standards mask. |
| Converters and references | Selected SAR allocation is 3 ns acquisition, 20 ns conversion, 2 ns reset and 0.2 ns guard. Finite-tone/load cases have positive modeled margins. | Rare comparator decisions, reference source/sink dynamics, kickback, mismatch and precision across uncertainty. The stressed 150 ps regeneration case has only about 1.2 ps timing margin; it is not robust qualification. |
| Wired recovery | Two acquired-state SSC/gap trajectories meet the internal 50 ppm target at 37.06 and 42.17 ppm. One cold trajectory qualifies at bit 344686 and reaches 34.70 ppm. | Broader offsets/jitter/traffic, source-loss recovery, changed SSC and stale prediction, plus physical sampler/phase-actuator performance and latency. These finite trajectories are not BER qualification. |
| Filter and resource fit | Paired RX filter allocation is 8 mA; sizing estimates include drive and capacitor area. | Simultaneous current, plate area, circuit overhead, noise and blocker swing. Whole-mode power, decoupling, routing and thermal fit are not established. |
| Protocol lifecycles | Generic services and conditional wired/RF/video exchanges execute. Independent legacy OFDM DATA covers eight rates with return ACKs. | Complete HE waveforms/router lifecycle, other radios' acquisition/hopping/emissions, both USB roles, PCIe detection/idle, SATA OOB, Ethernet negotiation, DP training, video recovery and SDI patterns. |
| Startup, calibration and host | Retained-state fault/epoch handling, bounded queues and FPGA-owned calibration services are modeled. | Physical readiness sensing, cold startup, correction deployment, real GPIO/CDC timing, modem computation and serialized recovery/response latency. |
| Reproducibility | Evidence files record configurations and source hashes. | Changed-source results require affected checks to be rerun. The pad generator's exact local Docker image is unavailable; restore its recipe and PDK identity before claiming fresh circuit reproduction. |

## Current architecture decisions

- Keep the complete wired/RF target set and generic controls. Protocol recipes
  live in the FPGA; RF and wired payloads do not run simultaneously on one die.
- Use differential external reference/LO timing for initial qualification;
  retain autonomous synthesis as an unqualified operating option. Wired RX
  still needs its own clock recovery.
- Retain provider-compatible bond sites and the electrically common native
  supply/return ring. Supply-site names do not create isolated rails. Use one
  external supply source; any isolation must be implemented locally.
- Keep one reusable pad foundation with lean RF/reference attachments and
  specialized wired attachments. The populated universal candidate exceeds
  loading allocations; sharing remains subject to complete disabled-branch
  loading, impedance, off-state and protection checks.
- Keep FPGA resampling/interpolation, protocol processing and bulk storage off
  chip. Sampling, sensitive feedback, protection and immediate safe controls
  require local implementation.
- Use stable FPGA-facing timing during warm RF hopping with the selected
  bounded 50 µs sample-epoch sequence. Cold startup timers must not enter the
  packet-turnaround path. RF gain feedback retains the under-3-µs allocation.

## Big-picture closure priorities

1. **Make the current analog interfaces electrically coherent.** Resolve the
   shared pad foundation's release/stress conflict, specify attached-core
   limits, and connect real local disable and bias circuits. Include all
   inactive branches and powered peers.
2. **Establish one usable supply/timing/RF envelope.** Join actual host activity,
   package uncertainty, clock conditioning, conversion, gain/filtering and TX
   output loading. Charge every mitigation to the same power/area accounting.
3. **Close representative full lifecycles.** Exercise startup, sustained traffic,
   fault and recovery for DC-coupled/USB, AC-coupled/OOB, video and radio paths.
   Then apply per-target criteria from the [capability gates](feasibility-gates.md#capability-wide-evidence-gaps-and-next-decisions).
4. **Separate model acceptance from implementation qualification.** A good
   stopping point records failed and missing gates honestly. Production still
   requires complete schematics, extracted layout checks, buildable assembly
   and silicon qualification. External support and narrow operating conditions
   reduce requirements but do not establish physical feasibility.

## Evidence rules

A capability result must identify the configuration, stimulus, criterion,
outcome, source fingerprint and excluded coverage. Passing expected-rejection
tests are valuable but do not demonstrate the rejected capability. Source hashes
establish provenance; they do not establish performance. Preserve numerical
nonconvergence as a model problem, not a physical impossibility claim.

The [closure inventory](mathematical-closure.json) owns per-capability obligations;
[schematic implementation](schematic-implementation.json) owns circuit coverage.
Measured silicon, extracted simulation, schematic simulation and assigned
behavioral performance are different evidence classes. Missing RF data is
uncertainty, not proof that GF180 cannot meet a target.

## Adopted assumptions and uncertainty ranges

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
| Clock quality and device speed | No measured GHz fT/fmax, oscillator phase-noise mask or aperture-jitter calibration recovered. Circuit-specific supply pushing around 65 MHz/V versus model assumption 10 MHz/V; neither bounds achievable rejection. | Retain both as sensitivity anchors, seek the permissible pushing/noise boundary, and compare autonomous versus supported external LO/clock operation. Do not substitute clean reference frequency for low output phase noise. |
| Complete RF chain | Receiver NF 6–15 dB and converter 6–9 ENOB at 20–40 MS/s are design scenarios, not measured GF180 ranges. Reference ADC's 4.27 ENOB is a cautionary result, not a process ceiling. | Sweep noise, gain, linearity and headroom jointly at declared signal levels; expose how much improvement each intended configuration requires. |
| Assembly and coexistence | 1–5 nH assembly examples are exploratory; actual package/substrate transfer and resonances remain unidentified. | Sweep complete return/matching/PDN networks, retaining active host switching in either RF or wired mode. External support and RF/wired exclusivity do not remove this coupling. |

Source conditions and limitations: [reference analysis](../verification/reference_afe/README.md).
No transceiver default is promoted to a measured value by these deductions.

## Open GF180 implementation reuse decisions


These are implementation candidates and external
simulation evidence, not replacements for the selected shared design or silicon
qualification. Prefer reuse of small circuits with explicit interfaces; do not
import another project's whole harness, pad ring or historical test campaigns.

| Unfinished function | Reusable source and decision | Remaining acceptance boundary |
| --- | --- | --- |
| Startup reset and local safe controls | Evaluate Edwards's [3.3 V POR](https://github.com/RTimothyEdwards/gf180mcu_ocd_ip__por/tree/a6f16be7c509820f2bd50f7ac517edb58cf8a3f2) before designing another startup timer. Schematics and layout netlists exist. Its documented nominal delay is 40 ms; very slow ramps can release near 1.5 V. | Cold-start holdoff only. It does not establish fast brownout response, safe pad disable, clock readiness or protocol turnaround. Qualify falling rails, repeated ramps, powered peers and actual disable loading separately. |
| Physical bias and common-mode sources | Evaluate the [biasgen, bandgap, voltage generator and class-AB buffers](https://github.com/RTimothyEdwards/gf180mcu_ocd_ip__biasgen/tree/96a93f811a10c0b63111a5bd862e3173300802d4) as support-circuit starting points. | Voltage-generator schematic reports include 1 kHz PSRR/noise checks; the inspected bandgap RCX summary marks its numerical checks skipped. Neither establishes GHz isolation, converter-reference settling, startup or safe absorption of powered-peer current. |
| Local power switching / analog control | Reuse topology and layout references from [analog_switches](https://github.com/RTimothyEdwards/gf180mcu_ocd_ip__analog_switches/tree/c21d8c0fdd0ee3ca42f8cd496a55ed5afc3d88d1). | The 3.3 V power stage has a single high-side PMOS bank with body tied to its input supply. By topology, it is not bidirectional off-state isolation: an externally raised output can forward-bias its body diode. Check inrush, reverse current, discharge, voltage drop and dead-supply control. Do not substitute it for powered-peer isolation or a low-noise regulator. |
| High-speed protection and pad foundation | Keep the existing reuse of native bond/clamp geometry; use [OCD I/O](https://github.com/RTimothyEdwards/gf180mcu_ocd_io/tree/6e0e354a78793339a4a004a6d9c08990d0eee3e4) as a comparison baseline. The [pad implementation decision](../analog/pads/README.md#upstream-reuse-boundary) records the circuit comparison. | The upstream clamp is not a new cure for our low-rail release problem. Core-local protection, retained disabled branches, RF loading and powered-peer behavior remain unresolved. Preserve provider bond positions and the extracted common supply topology. |
| Autonomous RF timing | Use the [A01 RFIC circuits and extraction experiments](https://github.com/Zachnad0/AUS-NZ-Track-A-RFIC-Workspace/tree/3b74fd559badf6729d5576458abdc528d4f0afa5) as comparison fixtures, not the selected clock chain. | Their VCO report gives nominal extracted oscillation near 4.37 GHz with 83 ns startup, but uses a separately supplied inductance model; it is not measured silicon or validated RF EM extraction. Their complete PLL cannot lock with its present divider/PFD relationship. Output-converter PEX reports severe swing/duty degradation. No phase-noise or jitter requirement is closed. |
| Converter implementation | Use [gf180-sar-adc](https://github.com/2AMLogic/gf180-sar-adc/tree/54c206134ac047af27b49bd41763c94c39577848) for comparator/sampling/CDAC circuit and testbench references. | Its 1 MS/s target is not our RF sampling rate. Current extracted results miss its own ENOB/SFDR goals; no silicon. Do not scale its speed or adopt its passing test count as evidence for our conversion chain. |
| USB HS / RF input attachments | Monitor the [Chipalooza GF180 entries](https://opencircuitdesign.com/chipalooza/leaderboard-3.html): USB HS TX, ESD-compensated LNA and differential pin buffers are particularly relevant. | The inspected leaderboard has repository placeholders. These entries do not yet supply reviewed reusable implementations for our missing interfaces. |

The inspected OCD I/O, analog-switch and A01 repositories declare Apache-2.0;
preserve upstream notices and check each selected source's license/dependencies
when importing. This review imports no circuit source and changes no performance
allowance. Exact revisions above keep the review reproducible without vendoring
large repositories. The POR and bias source licenses must also be checked before
an implementation import.

**Work order:** restore the pinned pad build environment; evaluate the POR/bias
support circuits against the existing local safety interfaces; then compare a
coordinated protection/receiver circuit with every attached branch present.
The startup timer must not sit in the per-packet TX/RX switching path. Keep the
external differential-clock option while the autonomous oscillator remains an
unqualified alternative. A borrowed support block must pass our connected
loading, supply, startup and off-state cases before replacing a behavioral source.
