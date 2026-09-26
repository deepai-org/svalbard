# Three whole-platform feasibility questions

## Decision sequence: several credible ways to succeed

Adopted 2026-09-26. Finish mathematical closure before new circuit/layout work.
This sequence replaces open-ended accumulation of isolated passing fixtures.
Every gate records **keep, change, or proposed scope reduction**, evidence,
remaining uncertainty and the next owner. A scope reduction requires an explicit
product decision; a failed test does not silently drop a requested capability.
No calendar estimate is a completion claim.

| Gate | Work and decision | Completion condition |
|---|---|---|
| G0: shared foundations | Operating ledger below; host electrical baseline; per-target acceptance contracts | Every conflict resolved or assigned to G1–G4. Every target has a proposed tier and numerical acceptance tuple; unknown entries keep the gate open. |
| G1: packaging, pads, power | Preserve provider COB compatibility; map bonds, board rails, pad branches and return paths; bound full host/package transfer | All critical paths meet their electrical budgets across justified bounds, including interior resonances. Otherwise change the compatible pin/pad/power plan. |
| G2: unified timing | Shared source/stage/supply spectra, reference-input loading, independent RX CDR, separate retune and turnaround state machines | One versioned timing environment consumed by RF and wired benches; choose supported clock ownership and recovery policy. |
| G3: full RF chain | Actual packets, weak signal, blockers, AGC, clipping, noise, ppm, switching and TX emissions together | Each radio has a sensitivity/selectivity/TX envelope with numerical packet-level criteria, or an explicit unresolved/experimental verdict. |
| G4: generic control coverage | Map electrical actions and command-to-pad latency; USB + PCIe lifecycle anchors; sustained Ethernet; other interfaces audited | Every required behavior has a demonstrated generic control or specified external implementation. Unsupported behaviors prevent capability closure. |

G1 geometry work and G0 host selection can proceed together. Numerical host
current injection must use a frozen host scenario before the PDN result is
interpreted. The FPGA model affects H2D drive and D2H input loading; chip output
cells, actual traffic, firmware clocks and board routing also determine the
harmonics. An FPGA family name alone does not establish those quantities.

### G0 host and operating-conditions ledger

User owns a Zynq-7000-series device; exact board is unspecified and physical
hardware is not needed at this stage. Keep it as a future bring-up candidate,
not proof that a particular connector/bank supports the link. No board purchase
or arbitrary replacement board is selected.

Freeze paper scenario H0: two ten-bit source-synchronous DDR buses, nominal
3.3 V LVCMOS electrical target; H2D forwarded clock 156.25 MHz; baseline RF D2H clock
LO/32 (75–77.625 MHz, hence 150–155.25 Mword/s DDR). LO/16 clock remains an
optional higher-switching setting. Retain 10 pF load and 7 pC
internal switching charge as assigned study points, **not measured Zynq/board
values or upper bounds**. Use quiet, random, alternating and burst traffic with
explicit edge shape, simultaneous switching and both directions. Wired D2H
ownership must be specified separately per selected rate. Final FPGA pin/bank,
I/O standard, drive/slew and connector qualification remains open.

In this ledger, 3.3 V is a modeling nominal, not a guaranteed operating window.
For every row, allowed rail ripple is unresolved in four bands: DC–10 kHz,
10 kHz–1 MHz, 1–100 MHz and >100 MHz through the relevant edge bandwidth.
Jitter tolerances require offset-dependent masks; no scalar RMS limit is yet a
whole-chip acceptance criterion. Entries marked open must be resolved, not zeroed.

| Block | Logical supply / voltage | Clock / range and tolerance | Pad, common mode, coupling, termination | Required concurrent activity | Conflict owner |
|---|---|---|---|---|---|
| REF input / alternate GHz branch | PLL / 3.3 V nominal | Reference or 2.4–2.484 GHz LO study; input slew/additive jitter open | Same REF_IN site; analog branch, CM/swing/termination open; ordinary Schmitt path insufficient evidence | Selected synthesis, host, control | G1/G2: unused-branch loading and shared rail |
| RF synthesis / quadrature / dividers | PLL / 3.3 V nominal | Autonomous or external LO; sample ÷64/128/256/512; noise mask open | Internal; external loop nodes not allocated | RX or TX chain, host, bias | G1/G2: shared supply and retune propagation |
| Wired TX PLL / distribution | PLL / 3.3 V nominal | Selected serial rate up to 2.5 Gb/s; fractional ×10 timing; tolerance open | REF_IN conditioning mode-dependent | Wired RX CDR, TX driver, host | G2: independent RX and TX timing |
| Wired RX equalizer / sampler / CDR | WIRE / 3.3 V nominal | Incoming serial, independently recovered | WIRE_RX pair; AC serial or USB DC branch; CM/termination by mode, numerical masks open | Wired TX, host, control | G1/G4: switch/protection capacitance |
| Wired serializer / driver / detect | WIRE / 3.3 V nominal | TX source; jitter envelope open | WIRE_TX pair; serial AC or TMDS DC; load detect/idle; TMDS external pull-up | Wired RX and host | G1/G4: bias levels, off-state and driver load |
| USB local HS and FS/LS branches | WIRE / 3.3 V nominal | HS sampling/drive and line-state timing; mode-specific masks open | Bidirectional WIRE_RX; pulls, HS termination, squelch; serial branch inactive but loaded | Host response path, control; WIRE_TX off | G1/G4: inactive capacitance and response latency |
| RF LNA / RX mixers | RF / 3.3 V nominal | Local quadrature LO | RF_RX analog pair; board match/preselection; bias/CM/termination open | PGA/filter, ADC, reference, host | G1/G3: package + blockers + reciprocal mixing |
| RX PGA / LPF / I/Q ADC | RF / 3.3 V nominal | LO-derived sample rate; aperture mask open | Internal differential CM/headroom open | RX mixer, paired converter/reference, host | G3: stage clipping/reference loading |
| I/Q DAC / TX LPF / mixers / driver | RF / 3.3 V nominal | Sample clock + quadrature LO | RF_TX analog pair; external match/filter/optional PA; headroom open | Paired DAC/reference, interpolation service, host | G3: output current, images, switching |
| Bias / reference buffers | RF/PLL/CORE allocation must be itemized / 3.3 V | Slow control plus converter impulse loads | Internal reservoirs; no extra reference pins | All selected analog blocks | G1/G3: shared loading and non-overlapping current inventory |
| Host capture/launch | HOST logical domains / 3.3 V target | H0 above; setup/hold/eye open | 20 data + 2 clocks, LVCMOS target; board/FPGA loads open | Active payload, core; remains active in RF | G0/G1/G2: rail injection and clock loss |
| Control / bounded queues | CORE / 3.3 V nominal | H2D, D2H, engine and SPI domains | SPI/reset; no new IRQ/test pins | Every operating mode | G4: CDC, bounded latency, resets and epochs |

Across all rows, RF and wired payload exclusivity remains mandatory. RF RX/TX
turnaround does not imply simultaneous same-frequency duplex. Wired RX and TX
may operate together. Shared physical rails remain active regardless of logical
domain names. The provider bond map may force rail sharing not in earlier models.

### Target tiers and acceptance contracts

Priority is not evidence status. All currently requested interfaces remain in
scope as baseline capability objectives, except the two already named stretch
paths. Investigation anchors are
1000BASE-X, PCIe Gen1 and a useful 2.4 GHz radio; USB is also a lifecycle stress
anchor. Do not downgrade SATA, SGMII, USB host/device, TMDS HDMI/DVI, DP RBR,
HD-SDI, HE20, BLE, BR/EDR, 802.15.4 or 2.4 GHz LoRa merely by calling them stretch.
Lower-frequency RF and external frequency conversion remain existing stretch goals.

Each wired acceptance tuple must name rate, coupling/termination, voltage mask,
channel loss/load, jitter spectrum, BER limit/confidence, acquisition/recovery
limit and sustained host service. Each radio tuple must name PHY/modulation,
packet length, PER limit/confidence, sensitivity reference plane, wanted level,
blocker powers/offsets, phase spectrum, TX mask/EVM and turnaround limit.
These numerical protocol contracts remain to be populated from the exact
standard/version: G0 is **not complete**. Diagnostic 10% EVM and zero errors in
short fixtures are not substitutes. For perspective, zero errors in about
3×10^12 independent bits only establishes an approximately 10^-12 one-sided
95% BER upper bound; short behavioral runs require separate analytic evidence.

### Capability-wide evidence gaps and next decisions

The coverage denominator is the 17 entries in
`generic_control_surface.external_interface_requirements`, not only the 13
legacy waveform/line-rate entries. Those entries are external application
requirements, never on-chip protocol IDs. HD-SDI, custom GFSK/SDR and the two
RF stretch paths must remain visible even without dedicated report fixtures.
USB host and device share one entry but require separate role validation.

| Target | Selected architectural provision | Unique remaining proof / boundary |
|---|---|---|
| PCIe Gen1 | Keep dedicated 2.5 Gb/s TX/RX, independent CDR, receiver detection and electrical idle; FPGA endpoint/PCS. | Detection and idle are physical actions, not serial symbols. Loaded startup/recovery and command latency remain unverified. |
| 1000BASE-X | Use the wired pair at 1.25 Gb/s; FPGA owns coding, ordered sets and negotiation. | Sustained independently clocked operation and recovery; no 1000BASE-T magnetics/copper PHY is implied. |
| SGMII | Reuse the same 1.25 Gb/s electrical path with external SGMII PCS/control. | Validate SGMII control/rate adaptation separately from BASE-X; equal baud rate is not equal protocol behavior. |
| SATA Gen1 | Retain 1.5 Gb/s operation, timed OOB drive/detection and CDR handoff. | OOB burst/gap sensing and transition to aligned data must work without an ideal reset of analog/CDR state. |
| USB 2.0 HS, host and device | Use WIRE_RX as D+/D−; independent HS/FS/LS drive, pulls, termination and sensing. FPGA controller; external host VBUS. | Both roles need attach/reset/chirp, HS traffic, turnaround and disconnect. Disabled USB branches still load the fastest serial configuration. |
| DisplayPort RBR | One 1.62 Gb/s lane per die, programmable swing/pre-emphasis, FPGA training and external AUX. | Prove training levels and sustained clock tolerance. Multiple lanes multiply dies and alignment obligations. |
| Single-link DVI | Three lane dies with DC TMDS branches, external clock fanout and FPGA encoding/alignment. | DC common mode/off-state protection, fractional ×10 timing, continuous FIFO and recovery after one lane faults. |
| HDMI TMDS | Same three-die video boundary; FPGA/board owns control-period encoding and ancillary interfaces. | Retain 720p/1080p fractional-clock goals. TMDS evidence does not imply HDMI FRL, higher-rate modes or complete HDMI system functionality. |
| HD-SDI | Keep 1.485 and 1.485/1.001 Gb/s; external coax driver/equalizer and FPGA scrambling/framing. | Stress CDR with actual scrambled/pathological patterns and sustained transport; a generic NRZ eye is insufficient. |
| 2.4 GHz Wi-Fi HE20 | Keep wideband I/Q, finite-zero channel filtering, paired converters and external FPGA modem/equalization. | Joint sensitivity/blocking, actual training, modulation-dependent EVM, TX spectrum and turnaround. Narrowband success cannot close this requirement. |
| Bluetooth LE | Use selectable narrow RF settings and warm same-channel turnaround; FPGA framing/modem. | Retain LE PHY goals; current LE 1M request/reply does not cover other PHYs, hopping, masks or calibrated air timing. |
| Bluetooth Classic BR/EDR | Use the same I/Q chain with phase-preserving modulation and retune control; FPGA hopping/baseband. | Real packet acquisition, channel changes and modulation-specific phase quality/turnaround must fit the selected clock architecture. |
| IEEE 802.15.4, 2.4 GHz | Reuse narrow I/Q filtering, O-QPSK/DSSS processing on FPGA and warm RX/TX control. | Real synchronization header, blockers, gain settling and response timing; generic DSSS data is not a packet result. |
| 2.4 GHz LoRa | Use narrow bandwidth/divider settings; FPGA chirp acquisition, resampling and modem. | Actual finite preamble, CFO drift, blockers and transmit spectrum; longer diagnostic training is not the selected remedy. |
| Custom GFSK / SDR | Expose numeric rate/gain/filter/timing controls and continuous I/Q streams within the same envelope. | Publish achieved ranges and error bounds rather than arbitrary-waveform promises; host service is part of the bandwidth limit. |
| Lower-frequency RF stretch | Keep existing external timing/divider flexibility; do not allocate a second multiband LNA or a new matching network on die. | Direct coverage is earned by tuning/matching tests. Below that range, use the external-conversion boundary rather than silently claiming native operation. |
| External frequency conversion stretch | Translate another band into the qualified on-chip RF band with board mixer/LO/filter; no extra chip analog pins. | Include conversion loss/noise, images, linearity, LO coherence and board power. This is an external system, not native wideband RF coverage. |

**Work order:** after the shared analog envelope, close the USB shared-pad and
PCIe detection/recovery anchors because they can require different pad circuitry
or missing controls. In parallel in the work plan, retain the real RF exchange
as the noise/emission/turnaround anchor; remaining radio families require their
own acquisition evidence. Continuous Ethernet and video then test sustained
clock/service behavior. This is an investigation order, not permission to remove
or downgrade the remaining targets. A control mapping or borrowed rate fixture
never substitutes for the missing behavior listed here.

### G1/G2 coupling and timing decisions

Use the provider-compatible ring and breakout as the assembly baseline. Pin
neighbor rules are preferences within fixed bond positions, not permission to
move supply pads. Enumerate pad/protection/switch C, bond/return L, mutual terms
and PCB impedance with provenance and justified ranges. No claimed worst case
from arbitrary multipliers. Use the selected 74-site provider allocation; the legacy 50-entry logical plan
is not a physical limit. Map board connections before assigning physical rails.

Convert injected supply spectra with stage-specific complex transfer functions
H_delay(f), in ps/mV, including input buffer, oscillator, divider, quadrature
and distribution. A sinusoidal rail tone Vpk gives delay amplitude |H|Vpk;
phase amplitude is 2π f_carrier times delay in seconds. Preserve coherent phase
and cross-spectra for common supplies; do not RSS correlated disturbances.
Oscillator frequency pushing, PLL suppression and sample-clock timing require
their own transfer functions. A static sensitivity or the 1 MHz model cannot
qualify the 60–124 mV high-frequency harmonic stress result. Small-phase spur
approximations fail when phase modulation is large.

The paired `whole_chip_operating_envelopes` study now holds the board and host
pulse hypotheses fixed while changing payload mode, rate and reserved current.
Its conservative rail interval must remain inside its declared model-validity
range before clean decoding contributes to a feasibility argument. An interval
extending outside the range means validity is not guaranteed; it is not proof
of an actual excursion. A receiver diagnostic pass never overrides this gate.
The assigned 2.5–3.6 V comparison range is not the product's accepted operating
window or a demonstrated device limit. See the [current joined assessment](risk-priorities.md#current-joined-host-power-and-receiver-assessment).

Mitigations to price: permitted existing supply/return paths, local isolation
and decoupling, board damping, reduced host swing/rate where compatible, and
chosen clock/pattern relationships. Extra bonds require provider compatibility.
The periodic TX sweep now confirms both direct clock sidebands near RF band
edges and nonlinear difference-frequency products inside a full-band filter.
Price host-rate changes against current, divider noise and spectral placement
together. An ideal-filter projection or a favorable exploratory divider is not
an implemented mitigation; require actual filter/load and clock-transfer bounds.
Host spread spectrum is only an experiment: it spreads energy, introduces
clock modulation and may worsen RF/CDR/CDC; it is not a default mitigation.

Separate **same-channel turnaround** (LO/sample/host timing stays running;
change RX/TX bias, gain, external switch/PA and scheduled payload) from **channel
retune** (stop publication → safe clock gate → retune/lock → sample reset → host
capture training → flush/new epoch → ready). Account for each duration and
clock-loss behavior. Do not charge a full retune to every packet response or
assume a truncated clock edge is harmless to FPGA clocking.

Compare variable LO-derived conversion/D2H with independently fixed conversion
and host timing. Resampling in the FPGA alone cannot keep a clock physically
fixed when its source is still LO/N; the fixed option needs a real clock source,
routing, CDC and power/pin budget. Retain on-chip independent wired RX CDR;
FPGA ordinary GPIO sampling does not replace it at full line rate.

Protocol timing constants are version/PHY-specific. The familiar BLE 150 µs
IFS is not a generic channel-retune deadline, and newer Bluetooth versions
allow additional spacing choices. Uncoded 1M/2M preambles are 8/16 bits,
respectively; coded PHY differs. 802.15.4 turnaround and Wi-Fi SIFS must be tied
to selected PHY/exchange. LoRa preamble configuration is not universally eight
symbols, and Wi-Fi acquisition must include the actual selected packet fields.
Use primary specifications rather than copying generic durations into tests.

### G3/G4 integrated campaigns and decisions

RF: combine sensitivity+3 dB wanted signal, specified blocker matrix, shared
timing spectra, reference error, AGC, converter/reference limits and RX/TX
switching; use actual preambles and payloads. Evaluate TX emissions and higher
modulations independently of RX decoding. Keep the sensitivity/blocker Pareto
frontier: a setting may be useful for a clean channel while another is needed
for selectivity; discard it only if no declared operating envelope benefits.
Publish required external filtering and interferers it cannot remove.

Sensitivity sweeps must use fixed physical input-referred noise at a stated
temperature, equivalent noise bandwidth and gain setting. A fixed frontend-EVM
percentage that scales noise with wanted amplitude cannot qualify sensitivity.
If AGC changes gain, price its realizable range, noise figure, current,
compression/headroom and settling; do not grant ideal constant ADC amplitude
for free. The current absolute-input diagnostic exposes this distinction but
still assigns NF/ENBW/gain and uses synthetic training. Its failures must remain
visible alongside strong-signal passes.

The LE 1M joined packet bench now connects actual acquisition/CRC, shared
supply/timing/reference disturbances, input-referred thermal noise and timed
loaded TX through an independent strong-signal peer. A finite sample queue
holds its prefill until launch and fails muted on underrun. Host arrival timing
and control application are still supplied bounds, not the real bridge. RF
half-amplitude onset is a diagnostic marker, not qualified first-bit timing;
require calibrated launch bounds, TX-load feedback and emission limits before
closing this gate. The joined TX result already shows that clean peer decoding
can coexist with substantial far-offset output power; external filtering must
be evaluated across carriers, including spurs inside its passband. Weak input
levels still fail without a blocker; the older
ideal-gain packet results cannot replace those failures.

Controls: for every target, record electrical state, timing, generic register/
event action, host-to-pad latency including queue/clock phase, observation and
external assistance. First lifecycle benches are **USB HS** (shared DC pads,
attach/reset/chirp, host and device response) and **PCIe Gen1** (AC coupling,
receiver detection, idle, training/error/recovery). SATA OOB gets a separate
burst/gap/handoff check; TMDS gets DC load and cross-die clock/FIFO checks.
DP training/swing/pre-emphasis and external AUX, SDI external coax interfaces,
and sustained 1000BASE-X/SGMII negotiation/recovery remain explicit obligations.
Use the existing fast connected model first; co-simulation is for actual RTL
boundaries, not a reason to replace fast mathematical work with long runs.

Sources checked 2026-09-26: [provider template](https://github.com/wafer-space/gf180mcu-project-template/tree/0de7e394337a1f7f5303ac7a3681bf2481b58176),
[provider packaging](https://wafer.space/price.html),
[Bluetooth link layer](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-60/out/en/low-energy-controller/link-layer-specification.html).


**Current operating decision:** RF and wired payload operation are mutually exclusive on the same chip. Both capabilities remain required; additional physical resource sharing is encouraged. See the [exclusive-engine policy](exclusive-engine-policy.md), which supersedes simultaneous-operation requirements below. Behavioral payload exclusivity is enforced; complete RTL/physical enforcement and resource rebudgeting remain open.

This is the active feasibility work program following the user's explicit
request to account for unknowns that an open PDK does not resolve and the fab
may never disclose. Preserve the full first-fabrication companion scope, the
provider-compatible site allocation, one slot, RF and wired functions, ordinary compatible FPGA
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

## Required treatment of unknowns

User requirement: assume adverse behavior in both directions and ensure the full companion can tolerate it. This applies to analog performance, host timing, power, package, models and numerical results. A favorable nominal case is insufficient.

For each uncertain quantity, distinguish physical lower/upper bounds from selected stress points. Challenge both extremes, adverse correlated combinations and interior resonances/non-monotonic behavior. Tolerance may come from design margin, isolation, verified trim range or another design choice that retains the full required capability. Narrow temperature/voltage operation is allowed, but the actual controlled window, self-heating and ripple must fit the stated bounds.

If bounds are unknown, do not invent a distribution or call the chosen simulation range worst case. Keep the affected requirement open until evidence establishes a range, physical controls bound it, or a verified architecture makes performance insensitive over the necessary range. Configuration or calibration is only mitigation after its range, resolution and convergence are demonstrated. A fallback that drops a required capability is not full-goal closure.

The table records the earlier pad/rail experiment set, including its incomplete
runs; those statuses are historical, not claims about live processes. Use
[risk priorities](risk-priorities.md) for current work and
[power partition](power-partition.md) for later coupled-load evidence.

| Quantity | Historical evidence/stress points | Adverse directions and next evidence |
|---|---|---|
| Host loading | Native simulations at 5, 8 and 10 pF; Artix specification provides a die-capacitance maximum, not a complete board load | Small loads can worsen ringing; large loads can worsen edge time/current. Establish actual package/PCB bounds and exercise both. |
| Signal-path R/L | Selected 1 ohm, 1/2 nH signal-path cases | Low damping and high loss/delay both matter. Sweep correlated clock/data mismatch and interior resonances after package selection. |
| Output-rail R/L | Zero versus selected 0.25 ohm/2 nH startup isolation; long shared-rail simulations incomplete | Low damping and large drop/bounce both matter. Capture the unresolved numerical behavior before treating any rail sweep as evidence. |
| Process/mismatch | Native typical runs and limited earlier SS experiments | Fast/high-current and slow/low-drive behavior both matter even at controlled temperature/voltage. Bound process/mismatch and calibration coverage. |
| Operating window | Narrow range accepted; numerical temperature and voltage limits not frozen | Low/high voltage, cold/hot junction and local ripple/self-heating must be included. Select feasible limits from evidence. |
| Numerical error | Default and Gear full-interval runs incomplete; four short default-integration diagnostics complete | Artificial damping can conceal instability; numerical ringing can invent it. Require trace inspection and convergence/cross-check evidence. |

None of these selected stress sets constitutes a proven complete uncertainty envelope. This policy does not expand the required environmental range; it requires honest closure within the range eventually specified for the full chip.

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
  phase by supply/bias noise and active host/digital circuitry. RF and wired
  payloads are exclusive; inactive-domain leakage and switching during handover
  still require bounds.
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

The normalized RF model's 4% frontend-noise allocation corresponds to about
27.96 dB signal/noise ratio at its reference plane, not the 20 dB example above.
An explicit illustrative mapping now lives in the same analytic report: at
300.15 K, 20 MHz equivalent noise bandwidth and 10 dB cascaded NF, the required
input is −62.86 dBm to allocate only 4% EVM to frontend noise. Mapping normalized
complex RMS 0.2 to 0.1 V RMS complex differential I/Q envelope (1 Vpp range per
branch) requires 52.86 dB conversion **voltage** gain from a 50-ohm RF input.
The convention is `v_RF(t)=Re{z exp(jωt)}`, so `P_RF=E|z|²/(2R)`.
This is not power gain into a stated baseband load, a sensitivity specification,
or evidence that the present LNA/mixer/filter provide that gain/NF together.
The live chain still lacks a calibrated antenna-to-converter normalization.

At normalized signal RMS 0.2, the illustrative 9-ENOB/12-bit excess converter
noise contributes 0.791% EVM at RX gain 1 and 0.396% at gain 2, while frontend
noise stays at 4%. Their quadrature total changes only from 4.077% to 4.020%.
The historical post-gain frontend-noise model instead predicted 2.039% at gain 2.
These isolated reference-plane calculations exclude ideal quantization, filter
attenuation, clock errors, blockers and receiver estimation. They explain why
raising gain cannot substitute for a full frontend noise/gain/dynamic-range budget.

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

**Next decisive work:** establish noise/settling/current envelopes for the
selected paired 10-bit SAR ADCs and segmented DACs; test receiver noise/blocker budgets jointly
with gain and filtering. Do not spend another long run merely increasing
nominal mixer gain.

## 3. Coexistence on this die and package

**Present evidence:** provider-compatible bond geometry with custom analog/fast
signal circuitry is selected; actual mixed-signal coexistence is unproved.
Logical area/current allocations are not physical fit.
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

- An actual provider-compatible 74-site ring/bond map, stack and package geometry,
  with all grounds counted and routing/ESD/guard-ring/isolation area included.
  Confirm assembly compatibility rather than assuming the standard provider
  package accepts the custom ring. Do not add hidden supplies or a paddle.
- Separate actual domain currents, peak spectra and operating modes; allocate
  clock/bias current once. RF RX/TX (as applicable) with host switching, and separately wired full
  duplex with host switching, must be covered by the supported configurations.
  Simultaneous RF/wired payload is not a required capability.
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


## Protocol-dependent closure gates

All additions must eventually run on the canonical full-chip composition,
not independent ideal protocol models that bypass its supplies, clocks, queues
or loaded pads. No current model result is relabeled as a new protocol pass.

1. **USB electrical branch plus serial loading** is the first new feasibility
   gate. Model differential AND single-ended pad states, termination changes,
   FS/LS attach, HS chirp, reset, suspend/resume, host disconnect, both directions,
   contention and power-off leakage. Sweep pad/package load including the disabled
   USB branch; rerun 2.5 Gb/s RX. Quantify the required branch capacitance ceiling
   from channel margin before transistor sizing. A scalar differential-only
   serial model cannot answer this question.
2. **Response deadlines through the actual FPGA boundary** are the next gate.
   Model peer packet end → chip RX → host transfer → bounded FPGA decoding and
   CRC decision → return transfer → TX enable/first symbol. Sweep phase, FIFO
   occupancy and control contention. For USB use the applicable host/device
   response windows from the USB timing tables; for Wi-Fi use the selected
   PHY's SIFS/trigger timing. Initial RF circuit targets are ≤2 µs same-channel
   direction settling and ≤50 µs warm-hop readiness, both exploratory internal
   budgets, not standards limits. Test legacy BLE 150 µs inter-frame spacing;
   newest shorter negotiated spacings require separate qualification. Budget
   all other delays explicitly; passing either internal budget alone is no pass.
3. **Autonomous clocks at every new rate and RF hop.** Check startup, independent
   RX CDR acquisition, SATA OOB followed by data, DP training/SSC, 480 Mb/s burst
   recovery, worst RF hops, reference loss, supply pulling and bank transitions.
   Cheap divider arithmetic cannot qualify jitter, lock time or RF phase noise.
4. **Independent complete RF waveforms.** Add HE20, LE 1M/2M/coded, BR/EDR,
   O-QPSK/DSSS and long LoRa packet stimuli with independent reference decoders.
   Measure waveform-appropriate EVM/frequency error, PER versus input level/CFO,
   blockers, TX spectral mask, IQ images and LO leakage. Keep held-out training
   and validation. Previous short-tone ~2% errors and a generic 10% threshold
   are not Wi-Fi or Bluetooth qualification. Qualify maximum supported MCS from
   results; do not claim 1024-QAM from nominal converter bits.
5. **Whole-chip resource closure.** Exercise prohibited profile overlaps,
   safe role/engine changes, stale contexts, missed deadlines, overload, queue
   recovery and sideband failure. Update current/area inventories and repeat
   baseline PCIe/Ethernet/RF tests. Physical qualification still needs the open
   PDK, transistor simulations and later extraction; no validated fab RF/package
   data is assumed available.


### Shared USB/serial pad: inactive-loading decision

The current `SharedWiredPad` has a two-node capacitance matrix with nominal
2 pF pad-to-return, 0.3 pF inactive-branch capacitance and 0.2 pF mutual
capacitance. Under balanced differential drive, the per-leg effective
capacitance is `Cpad + Coff + 2*Cmutual`: **2.7 pF**, not 2.3 pF. Its
common-mode effective value is instead `Cpad + Coff`. Neither may silently be
replaced by the serial screen's standalone 2 pF case.

An inverse calculation using the existing `wired_envelope.history_margin`
provides an initial inactive-loading requirement. Use 2.5 Gb/s, 400 mV
nominal differential peak, 50 Ω equivalent leg resistance, no pre-emphasis,
5 ps assigned random RMS jitter, and a timing half-window of 0.05 UI + 7σ.
Select the best of 0.5/0.65/0.8 UI sample centers, sample 21 timing positions
per window, and require at least 100 mV signed margin for the bounded binary
history. Bisect total effective capacitance over 0.001–10 pF for 40 iterations.
These are internal diagnostic assumptions, not a PCIe voltage/jitter mask.

| Driver time constant | Largest sampled passing effective capacitance | Remaining Coff after 2 pF pad + 0.4 pF mutual contribution | Signed margin with current 2.7 pF assumption |
|---|---:|---:|---:|
| 50 ps | 4.259 pF | 1.859 pF | 224 mV |
| 100 ps | 3.036 pF | 0.636 pF | 128 mV |
| 200 ps | 1.204 pF | None: base load already exceeds limit | −21 mV |

**Decision:** retain shared pads, but require an explicit total differential
capacitance budget. At the middle driver assumption the nominal 0.3 pF disabled
branch leaves only about 0.336 pF of additional effective loading before this
diagnostic boundary. Protection, switch drains, routing and mutual coupling
must share that allowance unless already included in the 2 pF pad assumption.
At 200 ps, eliminating the USB branch alone cannot rescue the modeled lane;
driver bandwidth, receiver equalization or base pad loading must change.
This is a circuit requirement to investigate, not evidence of achievable GF180
bandwidth or capacitance. Optimistic phase selection, lumped RC, omitted bond
inductance and the finite timing grid prevent qualification.

The existing `usb_pad_lifecycle` is also explicitly a probe sequence: FS idle,
reset-like SE0, an immediate configuration jump to HS, then NRZI data. It does
not implement chirp negotiation. `SharedWiredPad.configure()` jointly selects
pulls, terminations and drive style from speed/role and requires both drivers
released. A true negotiation model must allow independent generic pull,
termination, sensing and drive controls, including switching local state while
a peer is driving when required. The helper's speed switch must not be mistaken
for implemented chip negotiation or proof that the required controls exist.
Preserve the current probe as a component check; it cannot close G4.
The [normative macro boundary](../integration/macro-contract.md#independent-shared-pad-electrical-controls)
now requires that independence and distinguishes live passive-state actions
from stopped topology/trim changes. The mathematical `set_local_passives()` subset now permits independent local
pull/termination changes with a peer still driving. Four focused circuit tests
check remote reset with local pull removal, remote termination retention,
instantaneous power conservation, invalid-update preservation and equivalence
to default FS/LS/HS passive states. Existing host/device probe sequences still
pass. Independent numeric local drive and raw sensing now also exist, including a
bounded current-drive probe against peer-held SE0 without a speed change.
Physical switches, valid drive/comparator ranges, command timing and actual
negotiation are still required before this becomes a negotiation lifecycle.


## Protocol and physical specification sources

These sources define protocol/technology context; the sharing, budgets and
capability choices in the architecture are our engineering proposals, not vendor endorsements.

- [wafer.space slot dimensions, core area and packaging](https://wafer.space/price.html)
- [GF180 device and reliability rules](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_man.html)
- [USB 2.0 specification](https://www.usb.org/document-library/usb-20-specification)
- [USB electrical compliance tests](https://www.usb.org/sites/default/files/USB%202%200%20Electrical%20Compliance%20Specification%28v1.07%29.pdf)
- [Intel PIPE architecture, including SATA and DisplayPort](https://www.intel.com/content/www/us/en/content-details/643108/phy-interface-for-the-pci-express-sata-usb-3-2-displayport-and-usb4-architectures-specification.html) (context, not our FPGA pin protocol)
- [VESA RBR rate and AUX context](https://vesa.org/wp-content/uploads/2024/10/VESA-Taipei-Workshop_October-2024.pdf)
- [NXP Wi-Fi mode/bandwidth matrix](https://mcuxpresso.nxp.com/mcuxsdk/25.03.00-pvw2/html/middleware/wireless/WiFi-Bluetooth-802.15.4/topics/features.html)
- [Bluetooth PHY overview](https://www.bluetooth.com/learn-about-bluetooth/tech-overview/) and [LE timing evolution](https://www.bluetooth.com/core-specification-6-feature-overview/)
- [Thread's 2.4 GHz IEEE 802.15.4 foundation](https://threadgroup.org/What-is-Thread/Thread-Benefits)
- [Semtech SX1280 modulation family](https://www.semtech.com/products/wireless-rf/lora-connect/sx1280)

### Causal OOB observation evidence

`BurstEnvelopeReceiver` in `system_model/connected/protocol_pad.py` is shared
RC/comparator/timer math with profile-supplied windows. The SATA wrapper retains
candidate ±15% burst/gap windows; those are not a claim to cover the complete
standard acceptance envelope. It reports a completed pattern only after the
observed trailing quiet interval, using 525 ns for reset/init and 175 ns for
wake from [SATA 1.0 section 6.7.4](https://www.seagate.com/support/disc/manuals/sata/sata_im.pdf).
Reset and init remain electrically indistinguishable; the peer role supplies
meaning. The canonical service exposes this as a reduced observer, without
modifying PLL lock, acquisition or packet admission.

The protocol report checks 2/10 ns detector constants and retains the failure
at 25 ns. Inputs are rectified-envelope levels, not RF carrier samples. Next
connect the detector to actual idle/burst sources and ordered peer startup,
then qualify loaded electrical behavior and the transition into data recovery.

`SataOobStartup` now exercises two external peer controllers through those
observers. A timestamp-ordered scheduler drives only rectified line-envelope
levels between peers, processes comparator/release deadlines, and prevents
responses from being scheduled retroactively. Normal cases reach
`await_alignment`, but retain the overall startup deadline: without implemented
alignment they then fault. Weak/slow detection or a dropped wake also causes
timeout. Unexpected OOB during alignment faults, and subsequent traffic cannot
clear that fault. OOB completion is historical evidence, not link readiness.
The model never asserts PHY ready. Its 100 ns reaction and 100 us timeout
are candidate test budgets. Calibration, ALIGN/D10.2, retry/power-management
behavior and integration with the canonical analog chip remain unimplemented.

## HDMI/DVI multi-instance gates

Initial targets: single-link DVI / HDMI TMDS, 720p60 and 1080p60 at 8 bits/color,
three data-lane dies. Required gates are DC TMDS drive and receiver termination,
3.3 V common-mode/power-off tolerance, REF_IN 74.25/1.001–148.5 MHz (including fractional video references) and x10 clocking,
inter-chip phase/word alignment, bounded host FIFO/CDC, external clock-pair/DDC/HPD,
and independent pixel/control/packet validation. Reduced opaque-word and static
load checks are executable; no compliance or fabricated support is claimed.
The original die size and terminal budget apply separately to every instance.

[HDMI/DVI board and pin plan](../../../docs/roadmap/programmable-transceiver-pin-plan.md#hdmidvi-through-multiple-instances).
