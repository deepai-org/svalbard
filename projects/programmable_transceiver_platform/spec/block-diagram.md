# Normative whole-chip architecture

[Full-chip SVG](../docs/diagrams/transceiver-block-diagram.svg) · [PNG preview](../docs/diagrams/transceiver-block-diagram.png)

![Normative architecture](../docs/diagrams/transceiver-block-diagram.svg)

This document owns the selected functional architecture. “Normative” specifies
what the design must implement, not demonstrated silicon performance or a frozen
circuit topology. The drawing places RF west, wired east, timing north and host
logic south, with terminals at the perimeter. Neighborhoods are intentional;
block areas and routes are not a physical fit result.

See the [decision gates and operating ledger](feasibility-gates.md#decision-sequence-several-credible-ways-to-succeed) for the packaging-first closure sequence.

The [whole-architecture assessment](risk-priorities.md#architecture-assessment-one-implementation-several-ways-to-succeed) records the cross-system conflicts, operating sequences and every interface family’s open gate.

## Approved next-revision change

The [keep-or-change decision](risk-priorities.md#keep-or-change-decision-change-the-delivered-clock-architecture)
selects a differential external high-speed clock input together with a
0.025 ps/mV aggregate downstream supply-delay requirement. It reserves the
adjacent `inputs[0].pad` for `REF_IN_N`, adds 4 mA of input allowance, and moves
0.15 mm² from global growth into timing. The decision record owns the exact
costs, evidence and remaining physical uncertainty.

**Migration status:** the diagram, executable contract and baseline tables below
still describe the evaluated single-ended revision. Their single-ended-default
and no-new-clock-pin decisions are superseded for the next revision by the
linked decision. Preserve those controls until model migration is complete;
do not claim that the differential diagnostic campaigns verify the whole chip.

## Provisional first-chip baseline

This is the selected architecture for the next whole-chip mathematical model,
not a silicon-performance claim. Keep all requested application targets. Prefer
externally assisted operation for initial qualification while still fabricating
the autonomous timing paths. Do not require an autonomous oscillator to pass
before evaluating the rest of the chip, or remove it merely because an external
source works.

| Boundary | Selected baseline | Alternative and its cost |
|---|---|---|
| Assembly and pins | Provider-compatible 1×1 COB geometry, all fixed supply/return sites retained; 36 functional signal assignments, analog/custom fast signal cells | No custom-package escape is assumed. The provider has 74 sites; 36 signals plus 18 fixed supply/return sites already require 54 assignments. The earlier approximate 50-total target is superseded by this provider-compatible physical allocation; the legacy 50-entry logical model is not the bond map. |
| RF chain | Differential RF input/output, two RX mixers, two channel filters/PGAs, two ADCs, two DACs and two TX reconstruction/upconversion branches; one summed output driver | RX/TX bias reuse can reduce active current, but both paths occupy area. ADC/DAC sharing that interrupts timely turnaround is not selected. |
| RF selectivity | Reserve a tunable fifth-order channel-filter realization capable of finite transmission zeros as well as the existing all-pole control response | The elliptic transfer function is a candidate setting, not a fixed topology. Q/zero tuning and internal headroom must fit the filter allocation. Higher ENOB is a costed alternative, not the default cure for blocking. |
| Wired chain | One independent RX CDR/deserializer and one TX serializer/driver; simultaneous wired RX/TX allowed | Do not replace the CDR with ordinary FPGA GPIO sampling or borrow the RF ADCs as line-rate samplers. |
| Specialized electrical branches | USB HS plus FS/LS and independent pulls/termination/sensing on WIRE_RX; idle/detection and DC TMDS capability retained on the wired frontend | Disabled-branch capacitance counts against serial bandwidth. External AUX, cable interfaces and USB VBUS support stay outside the chip. |
| RF clocks | External 2.4–2.484 GHz LO through the dedicated REF_IN analog branch is the first qualification route; autonomous RF synthesis remains fabricated | One REF_IN, selected while stopped; no simultaneous independent reference and LO inputs. A fixed sample-clock alternative needs a real extra source and CDC allocation before adoption. |
| RF conversion/host rates | LO ÷64/128/256/512 conversion; start with LO ÷32 physical D2H clock, hence LO ÷16 DDR words. H2D remains 156.25 MHz clock / 312.5 Mword/s | The faster LO ÷16 D2H clock is an optional higher-switching configuration. The selected slower return path needs bounded service gaps and FPGA resampling. |
| Wired clocks/host | TX synthesis or external timing as appropriate; RX has independent recovery. Up to 312.5 Mword/s on each ten-bit host bus | Incoming recovered data crosses a bounded queue; continuous rate matching and recovery remain required. Multi-die TMDS needs shared board timing and alignment. |
| Shared services | One control/transport owner, shared master bias with local reference buffers/reservoirs, local clock branches; RF and wired payload exclusive | Share slow sources and reusable circuit designs, not a universal RF/serial switch fabric. Inactive leakage and quiet detection remain budgeted. |
| Fast radio response | LO, sample and host clocks remain running; warm/muted TX path, scheduled DAC release/unmute, retained reference state | Parked bias is allowed after its wake transient and readiness sequence pass. Retuning stops traffic, settles/relocks, retrains and starts a new epoch. |
| Digital boundary | FPGA owns framing/modems/controllers, CRC/FEC, equalization, resampling and bulk storage; chip owns electrical actions, bounded queues and clock recovery | No assumption that arbitrary FPGA GPIOs sustain full rate, or that host memory can repair chip FIFO overflow. No on-chip protocol profiles. |

### Choices fixed for the next model revision

Use a high-impedance protected RF clock input, driven from a nominal 50-ohm
external source, rather than an on-die 50-ohm termination by default. Retain
input loading and threshold/noise effects; the high-impedance route has the
better combined packet evidence. Standard low-frequency reference conditioning
is a separate selected branch. Autonomous synthesis starts from tunable
multiphase ring-based PLLs; do not add uncharacterized on-chip RF inductors or
unallocated external tank pins. Autonomous coverage is earned per configuration;
external timing remains the selected high-performance qualification route.

For RF conversion, select paired differential **10-bit SAR ADCs targeting
8 effective bits**, transported in the existing 12-bit words, and paired
segmented 10-bit DACs with the same transport width. This is a provisional
implementation choice, not evidence that 10-bit settling or 8 ENOB at maximum
rate is achieved. Existing SAR experiments inform the choice but do not qualify
it. No time interleaving in the baseline: sampling skew/calibration and duplicated
reference loads would otherwise become new first-chip risks. Keep the full
configured sample-rate range; slower operation is diagnostic, not permission to
remove wideband capability. If single-core conversion misses the rate, evaluate
two-way interleaving within the explicit converter fallback budget before
changing scope. The selected-baseline RF model now represents native 10-bit
conversion and 12-bit transport mapping. Its initial assigned-ENOB fixtures remain
controls. A closed-loop paired-SAR requirement model now includes acquisition,
bit decisions, finite DAC/reference settling and reference-load feedback into
the shared supply/timing environment. Use unequal bit intervals within the same
18 ns decision allocation; see the [converter requirements](power-partition.md#closed-loop-converter-and-reference-load-requirements).
Device poles/noise, comparator regeneration, mismatch and physical implementation
remain unqualified. The detailed converter now drives live packet AGC from
completed codes, charges its 18 ns conversion latency to service, and feeds
reference-current disturbances back into the shared supply and timing model.

Select active-RC biquad sections with tunable R/C, Q and feedforward weights for
the channel filter, plus the fifth pole. Select a tunable third-order all-pole
TX reconstruction filter per I/Q branch (one biquad plus one pole); retain the
older single-pole TX simulations as controls. The selected-baseline wideband
model now includes the third-order TX response. The finite-zero and all-pole responses
are configurations of this boundary. Do not depend on an RF preselector to
remove nearby in-band interferers. Use local buffered references and passive
rail damping/decoupling; external regulation is the baseline, with no mandatory
on-chip regulator bank. Start the PDN model from the existing 500 pF nonideal
local reservoir and 1 uF board reservoir, then apply the revised whole-mode
loads. These are selected model values, not frozen capacitor geometries. Select 0.25 nH
common-return inductance as the assembly target after the shared RF/wired/USB
comparison; it is not measured package performance. Evidence ID
`lower_return_probe` identifies this current target; `selected` retains the
original 0.5 nH control for comparison. Provider-compatible geometry must still
be shown capable of meeting the target, with no assumed extra ground sites. The
[HS quiet-pin screen](power-partition.md#usb-high-speed-quiet-pin-and-common-return-gate)
still exposes host-induced common-mode disturbance at this target; meeting the
equivalent inductance alone does not qualify the wired termination reference.

Target initial qualification at 27 °C ±5 °C junction temperature and a board
source of 3.3 V ±1%. Use controlled board temperature/cooling as necessary;
ambient temperature alone does not establish this operating point.
Internal rail voltages follow the loaded PDN; they are not ideal copies of the
board source. Performance outside this window is not required for the first
prototype. The older 2.5–3.6 V fixture-validity interval is not a qualified
operating window. Preserve independent reset/SPI recovery when payload clocks
stop; FPGA timeout plus explicit restart is the baseline fault path, not a
promised in-band event over a stopped clock.

For the wired lane, select CTLE plus slicer/phase-sampling CDR, without a
baseline DFE or general-purpose line-rate ADC. Start the mathematical CTLE at
unity DC gain, 200 ps zero and 80 ps pole (2.5× high-frequency gain). This is a
conditional circuit requirement within the existing wired allocation, not a
validated GF180 equalizer. The [joined recovery test](power-partition.md#wired-equalization-host-delivery-and-recovery)
retains the unequalized failure and rejects the higher-inductance package probe.
Select current-steering TX with
programmable main/postcursor drive and the separately controlled USB/TMDS
branches. In single-branch bidirectional operation, disable the unused serial
branch and cap WIRE current at 50 mA (48 active plus 2 inactive). Simultaneous
serial RX/TX retains its 96 mA allocation. The [USB voltage gate](power-partition.md#usb-static-output-voltage-and-return-path-gate)
requires a lower common-return target; the current package fixture is not a
closed USB operating envelope. Use the retained 8 mA differential-tail case as the initial serial
requirement point, not as the total lane-current estimate. Protection and
common-mode circuitry are customized at compatible sites; standard foundry
GPIO circuitry is reserved for host/control. H0, not a guessed Zynq board, is
the selected host electrical scenario until actual board details are available.

These selections close architecture choices for the next revision. Numerical
noise, speed, headroom and parasitics remain uncertainties to test. Change a
selection only for a failed requirement or a quantified system advantage; do
not keep reopening it because a different circuit family might also work.

### Remaining architecture choices: closed for implementation

The following decisions complete the baseline selection. They select what to
build and model; they do not resolve unknown silicon or assembly properties by
assumption. Keep the preceding converter, filter, clock and wired selections.

| Remaining choice | Decision and consequence |
|---|---|
| Common versus separated returns | Use the provider-compatible common-return arrangement as the baseline. Do not assume isolated ground domains merely because ground pads have different names. Keep split-return calculations as sensitivity studies, not a selected implementation: their isolation and host-ground movement are unqualified. |
| Package optimism | Keep 0.25 nH as a design target, with 0.5 nH and 2 nH comparison cases. A pass at the target is conditional; it cannot certify the assembly. Derive the allowable impedance envelope and require compatible geometry to satisfy it before physical qualification. |
| External assistance versus autonomy | External regulation, board passives and external timing are the primary high-performance route. Fabricate autonomous synthesis, but qualify its usable range separately. No automatic oscillator-performance prerequisite for externally clocked operation. |
| Fixed versus LO-derived RF sampling | Keep LO-derived sampling and FPGA resampling. Same-channel RX/TX response keeps clocks running; channel retuning stops payload and starts a new capture epoch. Do not add an independent sample oscillator or pins for this revision. |
| Host selection | Freeze the H0 electrical/transport contract, not an unspecified Zynq board. Preserve full-rate wired operation and the slower RF return clock. A future board must satisfy the contract; arbitrary FPGA GPIO compatibility is not a requirement. |
| Host interference mitigation | Keep worst-case concurrent host activity in qualification. Allow scheduled quiet data intervals as an additional generic operating configuration only after an actual transport trace proves data service and response deadlines. Do not assume RF TDD makes host switching disappear. |
| Additional hardware mitigation | No new clock-input pin, regulator bank, deep FIFO, interleaved ADC or universal analog crossbar in the baseline. First test configuration, board conditioning and existing circuit budgets. A hardware addition requires a demonstrated failure mechanism and a charged pin/area/current cost. |
| Scope and verification order | Preserve all requested targets. First close shared electrical/timing feasibility, then wide/narrow RF and wired lifecycle coverage. USB and PCIe remain the DC-coupled and detection/idle lifecycle anchors; Ethernet supplies sustained-stream coverage. This order does not downgrade the other targets. |
| First fabrication | Retain the full wired-and-RF chip, with generic bypass, observability and recovery controls. No separate reduced feasibility tapeout is selected. Complete mathematical closure before new schematic or layout work. |

The implementation target is one connected baseline with configuration-dependent
operating envelopes. “Several credible ways to succeed” means external versus
autonomous timing, selectable rates/bandwidths and explicit board assistance
within that implementation—not multiple unresolved chip architectures.

### Disposition of remaining mitigation choices

These are decisions for the current implementation, not promises that every
selected requirement is physically achievable. Do not carry competing defaults
into the next connected-model revision.

| Question | Decision now | Evidence and trigger for change |
|---|---|---|
| Single-ended or differential external timing input? | Keep the single high-impedance REF_IN and current pin map. Retain the paired-input probe as a fallback, not a second default frontend. | The paired probe now improves joined RF/wired diagnostics, including 64/64 continuously ready wired corners at an assumed 0.025 ps/mV downstream sensitivity. That sensitivity is unpriced; common-mode range, protection, area and lifecycle behavior remain unqualified. Adoption must charge the extra signal and input bias separately from distribution improvements. |
| Increase clock drive until everything passes? | Expose drive amplitude as a board operating requirement; do not declare one tested amplitude universally sufficient. | The 0.75 V source-peak acquisition fixture recovers 5/6 payloads, while even the 1 V refined wired fixture retains readiness failures. Source amplitude is not the voltage at the die pad; pad limits remain binding. |
| Solve wired readiness by enlarging the loop or adding a DFE? | Keep CTLE plus the existing CDR boundary. Resolve numerical crossing error before changing its physical architecture. | Root-refined crossings improve the 1 V diagnostic from 22/32 to 30/32 continuously qualified windows, without proving the assumed detector precision or eliminating failures. Numerical root finding is not an implementation of the detector. |
| Rely on host silence to make RF work? | Require a baseline with concurrent host service. Keep quiet intervals optional and explicitly scheduled. | Samples and replies still need transport. A quiet-window proposal must include a feasible queue/service trace and must not borrow unallocated storage. |
| Add circuitry to cover uncertain performance? | Spend existing configuration and board-assistance options first; retain only costed, failure-specific hardware fallbacks. | Converter interleaving, differential timing input and active regulation introduce their own loading, area, timing and startup obligations. None is selected simply as insurance. |
| Which host should drive the model? | Keep H0 as the fixed electrical contract. Use the owned Zynq-7000 as a later integration candidate once its board and bank details are known. | The family name does not specify loading, drive, return currents or attainable GPIO service. A guessed board would add false precision. |

The next decision is whether this **one baseline has a common feasible operating
region**. Test shared loaded rails and clock spectra against blocked wideband RF,
narrowband turnaround, wired continuous readiness and USB electrical conditions.
Include previously omitted internal switching loads within the existing mean
current budgets. Retain failures and numerical-convergence controls. If no common
region exists, change the responsible boundary and charge its complete system
cost; do not silently substitute a different package, ideal clock, or larger FIFO.

### Evidence required to change a selection

“Provisional” means selected for implementation and verification, not an open
menu. Carry one baseline through the complete mathematical model. Alternatives
are fallbacks with explicit costs, not additional default implementations.

| Decision | Evidence or engineering basis | Reopen only when |
|---|---|---|
| Compatible bond geometry, custom fast/analog pad circuitry | The provider boundary fixes assembly constraints; ordinary GPIO bandwidth is not evidence for RF or serial suitability. The shared-return electrical screen already exposes sensitivity to increased inductance. | The compatible pad/feed design cannot meet a required electrical window. Do not assume a different package is available. |
| External timing first, autonomous synthesis retained | Combined loaded-clock packet cases favor the low-noise high-impedance input; autonomous source performance remains less established. Neither route eliminates distribution or supply noise. | The loaded external path fails its noise, slew or power allocation, or an autonomous implementation earns equivalent evidence. |
| Native 10-bit SAR targeting 8 ENOB | This separates transport width from useful precision and avoids interleaving skew and duplicated sampling loads. It is an engineering selection, not a measured converter result. | Acquisition, decision time, noise or reference settling cannot coexist at the highest required rate within budget. |
| Fifth-order finite-zero RX filtering | The wideband gain/headroom screen needs substantially more close-offset rejection than the existing fifth-order all-pole setting provides; the ideal finite-zero candidate preserves the wanted band. | Combined blocker, internal swing, noise and tuning errors defeat the allocated filter; assess the costed converter alternative before reducing capability. |
| Third-order TX reconstruction | A modest increase over the old one-pole fixture gives a practical reconstruction boundary without assuming a large filter bank. Joined wideband TX now provides conditional waveform evidence; emissions, physical implementation and turnaround remain open. | Image rejection, modulation fidelity or turnaround cannot be met together. |
| LO-derived RF rates and continuously running clocks during same-channel response | Reuses the allocated timing source and avoids a new independent clock input; FPGA resampling absorbs nonstandard sample rates. | Sustained host service or timed response fails after accounting for resampling, filtering and bounded queues. |
| Warm/muted RF TX and separate wired RX CDR | Fast response needs retained state; wired reception needs timing independent of TX. FPGA GPIOs do not replace either analog obligation. | Their complete current or timing cost violates the common operating window. |
| External regulation and passive local conditioning | External components are allowed, while an on-chip regulator would introduce dropout, stability, noise and area obligations. | The joined rail/timing/RF envelope cannot close using physically plausible passive conditioning. |

Keep uncertainty ranges for physical quantities even after choosing a topology.
In particular, a model pass outside its voltage-validity interval is not a
reason to accept the package, and zero errors in a short fixture is not a BER
qualification. Unknown device properties are acceptance questions, not choices
that can be settled by declaring optimistic numbers.

The selected RF return clock is deliberately distinguished from its DDR word
rate. It provides 1.383–1.431 Gb/s payload arithmetic using the existing 59/64
schedule, versus at most 0.932 Gb/s for 12-bit I and Q at LO/64. Wired host
payload arithmetic is about 2.881 Gb/s at 312.5 Mword/s, before service-gap and
clock-margin qualification. These are capacity budgets, not measured I/O timing.

**Required board support:** regulated/decoupled supplies; reference or LO source
for the external route; RF matching/balun and justified band/image filtering;
FPGA host/configuration wiring. Application-specific additions include RF
antenna switching/PA where needed, USB VBUS power/protection, DP AUX, SDI
coax driver/equalizer and multi-die video clock distribution. External support
may be extensive, but no unallocated analog loop-filter pins or magical
close-channel rejection are granted. A single die is one wired lane; the
multi-lane applications explicitly consume multiple dies and board resources.

The [rough implementation allocation](power-partition.md#provisional-implementation-allocation)
owns area/current assumptions, [capability review](feasibility-gates.md#capability-wide-evidence-gaps-and-next-decisions)
owns target-specific architectural obligations, and [risk ranking](risk-priorities.md#whole-chip-risk-ranking)
owns the next experiments. Detailed circuit studies do not silently change this
baseline. Document a change and its cross-system cost first.

## Selected boundaries

Packaging compatibility preserves bond-site geometry and fixed power/ground
connections; it does not require ordinary GPIO circuitry on RF, fast wired or
GHz clock signals. Qualify analog pads/custom frontends and their protection
within that mechanically compatible ring.


- One GF180MCU die in one wafer.space slot, using the provider-compatible
  physical boundary above. The historical 50-total drawing is a legacy logical model, not the physical budget. The 12.92 mm²
  core allocation includes 2.92 mm² reserve; neither is an implemented area.
- Both RF and wired capabilities are fabricated, but their payload operation is
  mutually exclusive. Retain specialized RF frontends and wired line-rate
  samplers. Share transport, control, slow bias/reference services and reusable
  circuit designs where loading permits. No universal GHz analog crossbar.
- Configuration selects numeric clocks, pad modes, gain, filtering, conversion
  and transport settings. Protocol recipes reside on the FPGA, not in chip
  protocol profiles. Narrow temperature and supply operation is acceptable.
- FPGA owns modem/PCS/controller logic, CRC/FEC, bulk storage, sample-rate
  conversion and TX interpolation. Chip data storage is capped provisionally at 8,192 bits for CDC, elasticity,
  staging and deadline-critical service, within the 0.85 mm² memory allowance;
  instance accounting and final area still need verification.

## Timing: two credible operating paths

Provide autonomous synthesis **and** an alternate externally supplied timing
path as first-class design requirements. Neither is yet physically qualified.
`REF_IN` is the single allocated timing input: select reference, wired timing or
RF LO operation while stopped. A GHz LO requires its own qualified input
conditioning branch; it must not pass through an assumed ordinary GPIO buffer.
There is no simultaneous separate reference and LO input on this terminal.

The RF source feeds local I/Q phase generation, mixer buffers and selectable
sample dividers. The current mathematical candidate uses LO ÷64/128/256/512 for
conversion and LO ÷32 for the baseline D2H forwarded DDR clock (÷16 remains
an optional faster setting). These sample rates track
LO tuning; they are not exact fixed 5/10/20/40 MS/s promises. FPGA resampling
must include causal delay, arithmetic, memory and sustained service cost.

Wired TX retains selectable synthesis/external timing and flexible ×10
serialization. Wired RX always retains independent clock/data recovery and
phase control. External timing does not remove additive jitter, quadrature
error, clock distribution noise, or host rate matching. Clock switching requires
stop, isolation, settling/lock qualification, retraining and a new stream epoch.
See [clock ownership](clock-rate-ownership.md) for detailed obligations.

## RF conversion chain

RX: board preselection/matching → protected differential LNA with selectable
early gain → separate I/Q mixers → channel-select LPF → main variable-gain
stage with offset/common-mode control → paired ADCs → host.
Place the main gain after blocker rejection. Distribute limited gain through
the earlier stages only as their noise/headroom budgets justify; an active
filter may itself contain gain and must expose its internal-node headroom.
This selects functional ordering, not a transistor topology or a proven noise
figure. An ADC that never clips does not prove the upstream chain stayed linear.

AGC must choose gain from an interval bounded below by converter noise and above
by wanted peaks plus residual blockers. It must not always drive the wanted
signal to a fixed ADC level. If the interval is empty, gain adjustment alone
cannot fix the case: change achievable rejection, converter performance or the
declared operating envelope. Strong-signal attenuation/low gain and a high-gain
weak-signal setting remain generic controls, with no on-chip protocol selector.
See the absolute RF and gain/headroom requirements in [risk priorities](risk-priorities.md).

The wideband filter investigation now includes finite transmission zeros within
the existing channel-filter boundary. Ideal elliptic responses can supply the
missing close-offset rejection without narrowing the wanted band or assuming
external selectivity. High Q, coefficient tuning, delay, noise and internal
swing remain unclosed; the [filter requirements](risk-priorities.md) do not yet
demonstrate the selected active-RC implementation. The retained Butterworth
waveforms are controls. The generic filter must expose pole/Q/zero configuration
rather than only a cutoff setting. The selected-baseline wideband model now
joins one finite-zero setting to loaded rails, clock noise, blockers and native
converters; it does not yet demonstrate coefficient tuning or internal-node
headroom.

TX: FPGA interpolation/resampling → host → registered paired DACs → selectable
reconstruction filtering/gain → I/Q upmixers/summation → RF driver → board
matching/filtering and optional external PA. Use proper interpolation in the
system model; sample repetition is a comparison fixture, not the selected
wideband TX implementation. The selected third-order reconstruction response replaces older one-pole or
two-biquad sketches as the implementation target; transistor sizing remains
future work.

For same-channel timed TX, keep LO/converter/host clocks running while holding
bounded prefetched samples. DAC sample consumption and RF unmute must have an
explicit scheduled start; clocks running must not drain the prefill during the
wait. Late, stale-epoch or underfilled launches stay muted. This is a required
generic stream/gate behavior, now exercised by the mathematical sample queue;
physical control and RF launch timing remain unverified.
Price reconstruction-filter delay and board-switch/PA timing at the air boundary.

Keep narrow and wide filter settings. Wider settings improve some clean-channel
fixtures but admit more blockers; narrow settings must remain available.
Longer synthetic training has helped diagnostic recovery, but does not establish
recovery from a real protocol preamble. FPGA modem work must close that gap.
Converter word width is not achieved ENOB. Driver output power, RF noise,
linearity and modulation quality must close together at actual supply/headroom.

## Wired paths and specialized pad branches

Serial RX: protected pads / selectable termination and common mode → equalizer
→ slicers / phase sampler / independent CDR → deserializer and alignment.
Serial TX: gearbox / serializer → programmable main/postcursor driver, idle and
load detection. Preserve a DC-coupled TMDS electrical branch; a generic serial
swing model alone does not qualify HDMI/DVI.

`WIRE_RX_P/N` also carries bidirectional USB D+/D− through local HS and FS/LS
receivers/drivers, squelch, pulls and switchable termination. `WIRE_TX_P/N` is
high impedance in USB operation. USB controller and VBUS circuitry remain
external. No RF routing through the USB protection network.
Pulls, terminations, active drive and receive sensing require independent generic
controls; selecting a nominal speed must not atomically conceal unavailable
intermediate electrical states. The [shared-pad control boundary](../integration/macro-contract.md#independent-shared-pad-electrical-controls)
owns live versus stopped transition semantics. FPGA logic performs negotiation;
the chip applies validated electrical states and reports timestamped observations.


HDMI/DVI uses multiple identical lane dies plus external forwarded-clock
interface/fanout. Cross-die phase alignment and continuous FIFO operation remain
requirements. DisplayPort is one RBR lane per die. HD-SDI requires external
coax circuitry. The [README](../README.md) owns the application target list;
these are conditional capabilities, not compliance claims.

## Supplies, references and board support

Retain wafer.space default-ring/COB compatibility. The existing CORE ×1, HOST
×2, WIRE ×2, RF ×1, PLL ×1 pair allocation is a logical budget awaiting a
compatible bond/board map, not seven demonstrated independent external rails.
Provide startup/trimmed bias, buffered converter references, local reservoirs
and isolation. Share reference sources only if dynamic loading permits; retain
local buffers or replicas and account for their current. External regulation is selected. On-chip regulators are not baseline blocks;
introducing one requires an explicit headroom, stability, current and area trade.

External regulation, clocks and many SMD passives are normal supported board
resources. External loop filters or observations needing additional terminals
are **not** implied by this allowance. The existing pin budget must accommodate
any eventual off-chip analog connection explicitly.

Do not freeze a particular decoupling network from the passing 1 MHz screens.
Host edge harmonics, reference/LO feed impedance, regulator stability, capacitor
ESL/derating and package/shared-return coupling remain unresolved. RF/wired
exclusivity does not stop host switching or eliminate inactive leakage.
See [power partition](power-partition.md) for budgets and conditional studies.

## Observation and implementation order

Use SPI status/configuration, existing host sample/word capture and independent
known external stimuli. FPGA/lab equipment stores captures. Shared-LO loopback
alone can hide clock defects; no unbudgeted analog test pins or universal
internal overload detector are assumed.

Finish the connected mathematical model before new schematic/layout work.
Then implement the complete transistor/passive schematic using the planned
[six-family primitive library](analog-design-workflow.md), verify it, and carry
the same requirements into extracted layout. The highest-risk gates remain
clock quality, complete RF conversion and physical supply/pad/package coupling.
Current evidence and uncertainty ranges live in [risk priorities](risk-priorities.md),
not in this architecture drawing.

## Diagram ownership

`docs/diagrams/generate_block_diagram.py` regenerates the overview and supporting
sheets; `generate_normative_diagram.py` owns the normative SVG. The PNG is a
render of that SVG. Differential conductors and words are bundled, and local
bias/clock/control fanout is named rather than drawn as individual wires.

[Detailed circuit candidates](../docs/diagrams/transceiver-circuit-candidates.svg),
[RF loaded-chain sheet](../docs/diagrams/transceiver-rf-loaded-detail.svg) and
[video assembly sheet](../docs/diagrams/transceiver-video-detail.svg) preserve
exploratory connectivity. Their specific filters, monitors, memories, regulators
and numerical assumptions are not additional normative requirements. The
selected architecture above takes precedence over those historical candidates.
