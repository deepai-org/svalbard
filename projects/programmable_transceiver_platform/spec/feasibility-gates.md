# Three whole-platform feasibility questions

Current clock interface: `REF_IN` (positive) and `REF_IN_N` (negative) form one
differential reference/LO port, selected while stopped. Both legs require analog
conditioning/protection; source frequency and protocol ownership are unchanged.
See the [normative architecture](block-diagram.md) for the selected 44 mA timing allocation
and 0.0025 ps/mV external-clock supply-delay requirement. Saved single-ended studies
below are historical controls, not qualification of this revision.

## Current mathematical-model milestone

**Current priority: satisfy the behavioral requirements first.** Improve the
functional design and quantitative block specifications until the connected
model meets the required capability tests. Physical realizability, GF180 cell
choices, layout, area fit and fabrication compatibility are a subsequent
implementation milestone; uncertain implementation cost must not veto a needed
behavioral change now. Retain those estimates as unresolved obligations rather
than silently claiming that the improved design fits the original allocation.

This changes sequencing, not acceptance thresholds. Preserve required signal
quality, rate, blocking, timing, startup and recovery tests. Model finite noise,
latency, settling and state causally; never substitute knowledge of the transmitted
data or source timing for an observation available to the receiver. A passing
model establishes behavior conditional on its explicit component requirements,
not proven silicon performance. Promote changes to the shared normative design
when their connected behavioral checks pass; keep failed comparisons as evidence.

**Establish one coherent, uncertainty-aware whole-chip model that demonstrates
several credible ways for the transceiver to succeed.** The acceptance inventory
is `milestone` in [mathematical-closure.json](mathematical-closure.json); all six
criteria remain open. Existing G0–G4 gates below implement this milestone rather
than a separate project plan.

| Acceptance criterion | Existing gate / owner | Required result |
|---|---|---|
| Every capability has requirements in all requirement dimensions | G0, G3, G4; contract and closure inventory | Electrical, timing, signal quality, power, area and FPGA service are explicit; timing includes response/lifecycle deadlines. Unknown values remain visible. |
| One composition exercises the full lifecycle | G2, G4; selected model and transport | Startup, operation, mode changes, faults and recovery with persistent state and bounded storage |
| Shared uncertainties tested together | G1, G2, G3; operating ledger | Justified ranges and assigned hypotheses separated; adverse combinations and interior resonance checked |
| Evidence-backed capability verdicts | G0–G4; closure inventory | Conditional feasibility or required changes, with missing evidence explicit |
| Actionable circuit requirements and alternatives | G1–G3; architecture and analog workflow | Quantitative block requirements, joint budgets and costed mitigation options |
| One consolidated baseline | Closure inventory and model guide | Current sources/results distinguished from historical candidate evidence; reproducible commands |

The coverage inventory uses all 17 external interfaces mapped by the contract's
generic control surface, including HD-SDI, custom configurations and frequency
stretches. The 13 legacy waveform recipes are not the coverage denominator.
Service mapping is established; numerical acceptance and whole-capability
verdicts remain incomplete. Short wired and diagnostic RF results establish
conditional behavior only.

Avoid further precision about isolated packet failures unless it changes a
requirement, an architectural choice or coverage of a missing system behavior.
Physical uncertainty is not resolved by repeatedly simulating one assigned value.

The [first combined RF-chain assessment](risk-priorities.md#open-issue-register)
now identifies sampled wideband and narrowband operating points on the selected
power/package inventory, with clipping and comparator-deadline failures retained.
This closes the first-version assessment, not G3: protocol waveforms, uncertainty
coverage, emissions, dynamic current closure and physical realizability remain open.

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

### Wi-Fi HE20 capability gate

Target: **one spatial stream, 2.4 GHz HE20, MCS 0–7**, legacy discovery and
association, bidirectional HE traffic, ACK/Block ACK and router-triggered uplink.
**Interoperability and robust combined analog margin are not demonstrated.**
The sole normative numeric inventory is `rf_interoperability` in
[analog-architecture.json](analog-architecture.json). Protocol implementation,
calibration tables, correction FIRs and bulk storage stay in the FPGA.

#### Decisions and unresolved architecture

| Area | Current decision | Evidence still required |
|---|---|---|
| Clock | Clean differential external LO is primary; autonomous synthesis remains separately qualified. Keep LO/sample/host clocks warm across direction changes. | Joint phase-noise, divider/distribution, supply and converter-aperture envelope; triggered TX frequency statistics. |
| RX filter | Retain sharp 9.53125 MHz maximum and narrowband options. A wider independently selectable setting remains under evaluation. | Complete HE and DSSS/CCK tuning-headroom/blocker tests before choosing the additional width. |
| TX filter | Selected five-pole Butterworth, up to12MHz, with49-tap FPGA correction using12fractional coefficient bits. No three-pole bypass is selected. | Complete HE emissions, interpolation rejection, measured calibration and amplifier behavior remain open. Area/current estimates remain recorded; fabrication fit is deferred until behavioral closure. |
| DAC operating point | Native10-bit code width is retained; effective noise must be qualified at actual corrected-waveform amplitude. | Prefer8ENOB at0.24 amplitude with7.6042dB external TX-only attenuation into the fixed PA hypothesis. Retain9.5ENOB/0.10 as the lower-swing alternative. Complete HE crest, RF drive/pad load, filter current, DNL/spurs and calibrated power can still reject either route. |
| Calibration | External equipment and context-specific FPGA tables; no added detectors, pins or on-chip table storage. | Frequency-dependent correction, held-out measurement accuracy, drift, analog peaks and PA spectrum. |
| Frontend | External matching/preselection/switch and optional linear PA; 2 dB nominal/3.5 dB maximum allocated RX loss. | Board isolation, PA distortion, switching and receiver recovery together. |
| Timing | Schedule a defined antenna marker using bounded delay and actual finite queues; retain warm bias. | Physical bounds and protocol-specific deadlines. Preamble alignment is not first RF energy. |

**Operating-point decision:** prioritize the8ENOB/higher-swing/external-pad
route for the next joined model. It reduces the required DAC accuracy without
adding chip storage, converters or protocol-specific controls. Its sampled
filter swing and fixed-PA distortion are within their assigned screens; actual
RF drive and packet crest remain gates. Change to the lower-swing route if
complete packets exceed digital/internal peaks or current, if RF pad loading
prevents the required drive, or if the assembled TX path cannot meet the
combined error/spectrum budget after attenuation. Do not silently decrease
amplitude without recomputing converter noise and antenna power. No broader
RX filter or new on-chip PA/observation hardware is selected by this decision.
The [current compact joined report](../evidence/wifi-preferred-joined.json)
records this preferred route with the independent legacy generator, seeds831
and834,−65dBm wanted signal,−40dBm/+12MHz CW blocker,42dB fixed PGA,
0.31623 effective TX leakage,1degree assigned PA AM/PM at input P1dB,
20ps converter timing and the explicit0.3us
recovery-time-constant envelope below. All eight DATA-TX/return-ACK cases
pass per seed, with zero ADC clipping. It records exact settings, source
revision, model hashes, queue/deadline margins and remaining scope limits.
This closes an assumption-combination check; it does not promote the modeled
recovery, PA or complete HE lifecycle to qualified performance.


The combined TX target is −30 dB against the MCS7 −27 dB limit. Independently
justified noise may combine by RSS; bounded residual norms add without assumed
cancellation. TX spectrum, unused-tone emissions, carrier leakage and RX PER
are separate obligations. Never apply the TX EVM limit as an RX criterion.

The readiness milestone is still **incomplete** against the requested work:

| Required outcome | Current boundary | Next decisive behavioral evidence |
|---|---|---|
| MCS0–7 combined margin | Conditional converter/filter/chip/PA budget and diagnostic exchanges; external LO primary | Same complete HE packets must meet the error and spectral budgets across the declared operating envelope. |
| Wider RX headroom without losing blocker rejection | Both widths decode legacy OFDM; wider setting clips more under stronger blockers | Complete HE and DSSS/CCK width/tuning/blocker comparison; keep sharp and narrow settings. |
| Antenna-level timing | Finite queues, FIR lookahead and calibrated markers; legacy ACKs in both directions | Explicit bounded delay and overload/recovery hypotheses through the same timed path; reject settings whose uncertainty exceeds the deadline. |
| Practical external calibration | FPGA tables, power inversion and I/Q corrections exist | Held-out forward-model power/CFO/correction checks with measurement error and drift, using externally measurable quantities; retain actual board characterization as a later gate. |
| Qualified external frontend | Published module evidence plus assigned AM/AM and leakage screens | A consistent assigned voltage-to-power scale and bounded AM/PM/memory, loss and overload/recovery in the joined model; published parts inform assumptions, not qualification. |
| Complete interoperability scenario | Independent legacy PHY packets; diagnostic HE DATA geometry | Discovery/association, bidirectional HE, ACK/BA and triggered uplink through one impaired path. Missing full HE references do not qualify substitute diagnostics. |

Schematic work remains deferred until the behavioral milestone is complete.
Do not make unavailable chip or assembled-board measurements a circular
prerequisite for that milestone: before schematics, accept or reject explicit
parameter ranges and control sequences using the joined model, and record what
would invalidate them. Transistor simulation then tests whether those ranges
are plausible, extraction tests their physical implementation, and measurement
tests the fabricated result. Physical qualification remains a later gate,
never a claim inferred from behavioral decoding. Complete HE waveforms and the
specified protocol lifecycle are needed at the behavioral stage; they cannot
be deferred by calling a diagnostic packet equivalent.

**Next evidence dependency:** the current joined legacy report matches the
model-file hashes, but the workspace has no complete independent HE vectors
and no MATLAB executable. `he_reference_vectors.m` remains unexecuted.
The next substantial readiness step is to obtain independently generated,
configuration-labeled HE-SU MCS0–7 and HE-TB RU26/52/106/242 packets with known
PSDUs, sample rates and generator provenance, then implement and cross-check
their acquisition/decoding in the shared path. Random-PSDU vectors alone still
do not complete discovery/association or triggered MAC exchanges. Do not
close the milestone with more legacy seeds, the known-mask DATA control or
unspecified physical assumptions. Preserve the current conditional operating
point until full-packet evidence can resolve its crest, spectrum and width
tradeoffs. The prepared exporter is a starting point, not a verified reference.

#### What the runnable evidence establishes

Commands below live in `verification/` unless another path is given. They are
fast behavioral screens; none is transistor, layout or fabricated evidence.

| Evidence | Current result | Boundary |
|---|---|---|
| `wifi_client_exchange.py` | 13 ideal-MAC intents through retained RF state and 1024-bit queues; RX/TX high-water 420/868 bits, four ADC clipped pairs. Also decodes at 3.5 dB RX loss. | Diagnostic DATA, not real association/HE/TB packets or sensitivity qualification. |
| `test_wifi_client_exchange.py` | MCS0–7 DATA modulation/rates, causal scheduled replies, power correction, rejected requests leaving queues intact. | Known geometry/training; finite chosen cases, not interoperability. |
| `external_wifi_reference.py --reference-tools /path/to/tools` | Independently generated legacy OFDM DATA decodes and passes CRC at all eight 6–54 Mb/s rates. Every DATA case gets a complete 6 Mb/s ACK; selected TX queue maximum 878 bits. | Ideal MAC decisions; not HE or DSSS/CCK. |
| Same runner with `--rx-cutoff-hz` | All nine DATA/ACK cases pass at 8.578125, 9.53125, 10.484375 and 10.5 MHz; no ADC clipping. | −50 dBm wanted, −50 dBm/+12 MHz CW, 2 dB loss; not prescribed rejection/sensitivity tests. |
| Same runner with `--tx-candidate --tx-cutoff-scale 0.99` (also 1 and 1.01) | All eight timed replies pass; candidate queue maximum 876 bits. At nominal cutoff, the 6 Mb/s case has 9.99710 µs alignment gap and 8.96028 µs DAC-launch gap. | Nominal correction with cutoff mismatch only; board delay still assigned. |
| Independent complete legacy runner, −65dBm wanted /42dB PGA /+12MHz CW | Both9.53125 and10.5MHz decode all nine DATA/ACK cases at−40/−35/−30dBm blocker. Aggregate ADC clipped-pair counts are0/18/70 versus0/54/117. | Wider RX worsens overload margin; CRC success does not admit clipped operation or prove PER. Fixed gain, not the acquisition AGC policy. Reproduce with `--wanted-dbm -65 --pga-db 42 --blocker-dbm` and `--rx-cutoff-hz`; TX uses the candidate DAC/filter/PA settings below. |
| `wifi_client_exchange.py --modulated-blocker-screen` | Selected RX cutoff decodes a −45 dBm/+20 MHz independent OFDM blocker but fails at −40 dBm; 10.5 MHz cutoff fails already at −45 dBm. | Diagnostic interferer has no qualified spectral mask. Wider is not automatically better. |
| `wifi_client_exchange.py --blocker-screen` | −50 dBm wanted decodes through −12 dBm/+12 MHz CW despite 13 clipped pairs. | Not a WLAN adjacent-channel rejection threshold or PER result. |

The independent source is [GR-WiFi v1.0](https://github.com/cloud9477/gr-ieee80211/tree/dc93c8f30de46082690d5768d6ad03ea2c11e2cb),
kept outside this repo under its upstream AGPL-3.0 license. The runner checks
that revision, uses received L-SIG rate/length, L-LTF channel estimates, pilots,
deinterleaving, depuncturing, SERVICE/scrambler recovery and CRC. Payload truth
is used only after decoding. It also cross-checks the diagnostic's RU242 BCC
interleaver against VHT80's matching 234-tone geometry; that is not full HE proof.

Reproduce the independent checks from `verification/` using a separate checkout
and virtual environment. The executed environment was Python3.12.3,
NumPy2.5.1, SciPy1.18.0 and Matplotlib3.11.2; these are recorded versions,
not a claim of minimum supported versions. Upstream imports Matplotlib even
for headless waveform generation. No RF hardware or GNU Radio runtime was
used for these Python transmitter checks.

```sh
git clone https://github.com/cloud9477/gr-ieee80211.git /tmp/svalbard-reference
git -C /tmp/svalbard-reference checkout --detach dc93c8f30de46082690d5768d6ad03ea2c11e2cb
python3 -m venv /tmp/svalbard-reference-env
/tmp/svalbard-reference-env/bin/python -m pip install numpy==2.5.1 scipy==1.18.0 matplotlib==3.11.2
OPENBLAS_NUM_THREADS=1 /tmp/svalbard-reference-env/bin/python external_wifi_reference.py --reference-tools /tmp/svalbard-reference/tools --tx-candidate --resampler-span 40 --resampler-fraction-bits 14 --dac-enob 9.5 --integrator-ratio 10 --amplitude .1 --pa-input-p1db-envelope .3965020773807595
```

Use an unused temporary path or reuse a checkout only after verifying its
revision; do not overwrite unrelated work. Add `--tx-data-check` for the
independent all-rate DATA TX and returning ACK path. The runner reports its
configuration, source revision and limited PHY scope; its `completed` flag
means decoded packet checks, not analog/compliance admission. ADC clipping,
nonlinearity allocations and physical headroom remain separate gates.


The retained exchange bench now inherits the selected correction and DAC ENOB,
span40/14-bit rational interpolation and received-pilot reply-frequency update.
The latter uses successfully decoded receive pilots, never injected clock truth.
All MCS0..7 diagnostic warm responses exercise actual finite queues with the
correction delay charged. Its normal DATA generator whitens DATA and padding
with a fixed seeded diagnostic mask; this is not a standard WLAN scrambler.
The unwhitened overload case remains a separate rejection control. The optional
external reference runner also inherits these defaults and uses one frozen
shared design. Explicit overrides are reported as diagnostic settings.
Reproduce current selected exchanges and independent legacy DATA/return-ACK:

```sh
OPENBLAS_NUM_THREADS=1 /tmp/svalbard-reference-env/bin/python selected_revision_check.py --wifi-exchanges --reference-tools /tmp/svalbard-reference/tools
```

The older HE-tone diagnostic omits HE signaling/scrambling, uses known training,
constant pilots and configured length. Its zero-filled final DATA symbol can
produce artificial peaks even with random payload. At amplitude 0.08, the
structured MCS0 case peaks at 1.173 FS before and 1.282 FS after correction.
Keep this adversarial test, but use actual scrambled HE packets to decide
normal backoff (`rf_filter_tradeoff.py --tx-headroom`). Native 10-bit quantization
and extra ADC noise are applied at 37.6875 MS/s before conversion to 20 MS/s.

For peers with a shared LO/sample oscillator, the model corrects sample rate
on the native converter grid using 129-tap/8× interpolation and fractional
interpolation. The ±37 ppm, 4096-octet diagnostic passes with 0.478 µs charged
RX+TX lookahead. Independent clocks/Doppler need their own estimator. This is
not an FPGA throughput or packet-boundary qualification.

#### TX reconstruction and calibration decision

At 37.6875 MS/s, the 9.53125 MHz outer tone's nearest DAC image is at
28.15625 MHz. The earlier three-pole/18 MHz comparison gives −21.26 dB image
relative to that tone; three-pole/10 MHz gives −33.96 dB; five-pole all-pole/12 MHz
gives −46.04 dB (`rf_filter_tradeoff.py --tx-images`). These are not packet mask
measurements. A broad 2.4–2.5 GHz preselector cannot generally reject in-band
DAC images, so the present reconstruction path remains an architectural risk. The executable frontend policy in
`analog-architecture.json` likewise grants no unsupported in-passband selective
rejection to a fixed full-band board. The current board-selectivity screen in
`evidence/selected-revision-check.json` distinguishes in-band diagnostic blockers
and image locations from out-of-band probes. Switching or tuning a narrower
external filter remains allowed, with explicit coverage, insertion loss,
settling and tolerance; it is not an ideal channel-following filter.

The selected topology uses two biquads plus one real pole and a 49-tap FPGA
FIR with12fractional coefficient bits. Earlier held-DAC diagnostic evidence
below motivated that choice; these numbers retain their original scope:

| Quantity | Conditional result |
|---|---|
| Scalar-only observer EVM | −40.90 dB; observer band-selects before sampling and learns no per-tone correction |
| Image-band PSD peak | −46.35 dBr, raw-output Hann/Welch measurement, not a standard mask |
| Native component peak | 0.579 FS for the selected waveform/amplitude |
| FIR alignment delay | 0.637 µs, charged by earlier DAC launch; includes a small emitted precursor |
| Stale correction, ±1% common cutoff shift | −33.69/−33.79 dB scalar-only EVM |
| Planning cost | +0.46 mm² and +6 mA warm RF current; transfer area from reserve, leaving 0.85 mm² unassigned; external-clock subtotal240mA leaves no current reserve |

Reproduce: `rf_filter_tradeoff.py --tx-preeq --filter-family rx_all_pole_control
--cutoff-hz 12000000 --taps 49 --coefficient-fraction-bits 12`.
The allocation is selected in the shared inventory, **not a demonstrated
transistor fit**. The normative resource ledger supersedes historical reserve
figures in individual experiments.
`rf_filter_tradeoff.py --tx-radio-compatibility` compares the selected
three-pole/18 MHz and candidate five-pole/12 MHz linear filters without FPGA
pre-emphasis on nine existing modulation fixtures: GFSK 1/2 Msymbol/s,
EDR 4/8-phase, 802.15.4 OQPSK chips and SF7 LoRa at all four supported
bandwidths. Both produce zero decision errors (512 bits per GFSK case,
256 symbols per EDR case, 1024 OQPSK chips and 16 symbols per LoRa case).
Candidate interior waveform residual is 0.06–0.62% after nominal DC group-delay
alignment from the independent filter response, with no DATA response fitting.
These residuals include finite-grid interpolation and are not transmitter EVM
qualification or proof the candidate improves signal quality. This rules out an
obvious wide-setting modulation incompatibility in the linear fixture only.
The same54 wide/narrow/headroom cases now also run with
`--integrator-ratio 10`, matching the Wi-Fi candidate's finite-bandwidth
integrator hypothesis. All have zero decision errors; maximum interior
waveform residual across both filters and all settings is5.61%. Delay comes
from the finite-bandwidth transfer function, not a fitted DATA correction.
This removes the earlier ideal-integrator mismatch in the compatibility
screen. It still excludes actual Q/order control range, bypass parasitics,
DAC images, nonlinear/noise budgets and complete radio packets; those cannot
be replaced by the short-sequence decision count.

The same screen also compares both topologies at exploratory cutoff equal to
GFSK symbol rate, EDR 1 MHz, OQPSK chip rate or LoRa bandwidth, and twice those
values. All 36 added narrow-setting cases have zero decision errors. Candidate
waveform residual spans 1.99–5.61% at the tighter setting and 0.22–2.22% with
twice the cutoff; the tighter OQPSK case rises from 4.47% (three-pole) to 5.61%
(five-pole). Thus a drop-in cutoff-code substitution is not justified merely by
correct decisions. Keep independent TX bandwidth selection and calibrate each
filter state; evaluate spectrum versus distortion before selecting recipes.
The observer subdivides the same piecewise-linear input into 32 steps per
source sample; comparison with 16 steps changes reported residuals by at most
0.072 percentage points, with zero decision errors at both resolutions. Do not
interpret smaller residual differences as filter superiority. These exploratory settings are not normative protocol profiles. DAC images,
startup/transients, noise/current and complete packet behavior remain open.

The normative `rf_interoperability.tx_spectral_measurement` contract now owns
mask offsets and observer requirements. [Rohde & Schwarz, §5.1.1/Table 12](https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/premiumdownloads/premium_dl_brochures_and_datasheets/premium_dl_whitepaper/IEEE-802-11ax-Technology-Introduction_wp_3609-9470-52_v0100.pdf)
gives HE20 offsets 9.75/10.25/20/30 MHz, relative levels 0/−20/−28/−40 dBr,
100 kHz RBW and 7.5 kHz VBW. [Keysight's measurement documentation](https://helpfiles.keysight.com/csg/89600B/Webhelp/Subsystems/wlan-mimo/content/trc_spectral_emission_mask.htm)
confirms bandwidths, short-burst measurement limitations and combined
relative/absolute limits. A full-band energy ratio is not this measurement.
No current screen implements the complete analyzer procedure; short synthetic
bursts and unknown antenna power cannot establish compliance. Keep that gate
open instead of treating −20 dBc integrated energy as a mask failure or pass.

The corrected-filter screen also captures a 2 µs analog tail after the last
DAC transition and FFTs the complete unwindowed burst. With
`--tx-preeq --filter-family rx_all_pole_control --cutoff-hz 12000000 --taps 49
--coefficient-fraction-bits 12`, compare `--payload-bytes 128` and `4092`.
Integrated both-sideband energy relative to |f|≤10 MHz is −19.76/−20.01 dBc
in 10–20 MHz, −52.64/−52.73 dBc in 20–28 MHz and −49.41/−49.75 dBc in
28–39 MHz. Both decode; captured post-DAC tail energy is about 1.3e−9 of burst
energy. This includes intrinsic unwindowed OFDM sidelobes, not just packet edges;
it is not a PSD mask, ACLR qualification, PA-switch transient or full HE PPDU.
The modeled idle tail also omits TX active noise. Low far-out images therefore
do not close near-channel emissions; evaluate actual packet windowing and PA
switching before qualifying the selected filter.

`relative_mask_screen` now smooths the full-burst energy spectrum with a
Gaussian power response having 100 kHz FWHM and compares its peak-normalized
trace to the normative relative mask over 9.75–39 MHz offsets. The nominal
five-pole/49-tap/4092-byte case shows a worst +13.70 dB relative excess near
−10.52 MHz. Four/eight-sample window variants remain +13.66/+13.70 dB.
The source is materially affected by digital interpolation: `--resampler-span
40` replaces the default 10-span 20 MHz→37.6875 MHz kernel and refits correction
to the same kernel. Relative excess becomes −7.65 dB (7.65 dB screening margin),
with worst offset moving to +28.48 MHz; scalar EVM is −40.60 dB, native peak
0.568 and decoding passes. Span 80 gives essentially no additional mask margin
(7.66 dB). Thus the 10.52 MHz failure is mitigable in the FPGA without requiring
a sharper analog filter. The selected rational-rate FPGA interpolator now uses span40 and14fractional
coefficient bits. Its linear-phase lookahead is2us versus0.5us for span10,
charged in the retained exchange; FPGA computation and storage still require
implementation. Windowed-sinc runners remain explicit interpolation approximations.
The integrated timed bench accepts the same `--resampler-span 40`, fits
matching correction and charges the full 2 µs lookahead after the assumed
2 µs FPGA decision, before descriptor transport and prefill. RX waits for
actual delivery of every captured ADC pair through the finite host queue;
there is no additional fixed drain delay. Capture tail, TX interpolation,
correction-FIR delay, board delay and prefill remain charged.

`external_wifi_reference.py --tx-candidate --resampler-span 40` passes independent
legacy DATA→ACK exchanges at all eight OFDM rates. With the full 1.6 µs RX
capture tail retained, measured queue drain is 0.307–0.429 µs and remaining
margin before the prefill deadline is 0.954–1.076 µs. ACK antenna-marker gaps
are 9.990–10.010 µs; TX queue high-water is at most 876/1024 bits. Thus this
candidate does not presently require a shorter interpolation kernel or a
relaxed antenna deadline. This is a conditional behavioral timing result:
FPGA decision/arithmetic throughput, actual board delay and physical settling
are still assumptions, and the independent packets are legacy OFDM, not HE.
The diagnostic phase-noise exchange uses the same delivery and launch path.
No centered offline interpolation may silently supply future samples. The
spectral result remains a relative screen, lacking detector/VBW, absolute
limits and complete HE PPDUs.

`rf_filter_tradeoff.py --tx-fpga-workload --resampler-span 40 --taps 49`
prices a straightforward unfused I/Q implementation: 9.7235 billion real
products/s, up to 260 products per output pair, 96,580 coefficient bytes and
512 history bytes at assumed 16-bit coefficients/samples. Sharing coefficients
between I/Q does not share products. At 200 MHz with 80% usable throughput,
the arithmetic lower bound is 61 one-product-per-cycle lanes, excluding modem,
FEC, RX, RAM-port scheduling and routing. All storage belongs to the FPGA;
no chip FIFO increase follows. This is a substantial host requirement, not
proof of timing closure or an assertion that every DSP block supplies one lane.
Fixed-point error and accumulator widths still need qualification; polyphase
fusion or coefficient generation may reduce costs but are not credited here.

Coefficient rounding is exercised with `--resampler-fraction-bits 14` on the
span-40 candidate (correction FIR remains at 12 fractional bits). Quantization
applies to the actual gain-603 polyphase coefficients, not the unscaled API
prototype. At 14 fractional bits the relative-mask screening margin is 7.65 dB,
scalar error −40.58 dB and native peak 0.568, with decoding preserved; 12 bits
also decode at −40.56 dB. This supports the provisional 16-bit coefficient
storage estimate for this case, not a fixed-point datapath qualification.
Sample quantization, accumulator range/rounding/saturation and integrated
clock/timing behavior with rounded coefficients remain separate checks.

A matched topology comparison uses span-40 interpolation rounded to 14
fractional bits, 49-tap correction at 12 fractional bits, identical 4092-byte
DATA and 0.08 amplitude. All cases decode with scalar error around −40.5 to
−41.3 dB; spectrum and headroom, not clean decoding, distinguish them:

| Analog filter | Relative-mask screening margin | Native component peak |
|---|---|---|
| Three-pole, 18 MHz | −15.64 dB | 0.559 |
| Three-pole, 12 MHz | −6.14 dB | 0.620 |
| Three-pole, 10 MHz | −2.89 dB | 0.627 |
| Three-pole, 8 MHz | −0.49 dB | 0.655 |
| Three-pole, 7 MHz | +0.15 dB | 0.797 |
| Three-pole, 6 MHz | +0.53 dB | 0.994 |
| Five-pole, 12 MHz | +7.65 dB | 0.568 |

The table above uses ideal10-bit DAC quantization, not an8ENOB electrical DAC.
`--dac-enob` now adds equivalent excess code-output noise on actual held DAC
updates before reconstruction. At amplitude0.08 the native complex RMS is0.07564,
corresponding to22.43dB sine-referenced backoff, not the allocation's illustrative
10dB. Scalar diagnostic error is−40.07/−35.68/−33.04/−30.24/−27.35dB for
10/9/8.5/8/7.5ENOB; all CRCs pass. These are not standard transmitter EVM results.
Paired paths with identical RF/noise realizations isolate DAC rounding and added
noise, integrated over±9.53125MHz. Substituting only that converter fraction in
the normative budget, with all other terms still allocated, gives:

| DAC hypothesis / normalized amplitude | Native peak | Converter in-band error | Combined allocation | Decision |
|---|---|---|---|---|
| 8ENOB /0.08 | 0.523 | 3.006% | −26.68dB | Fails target and−27dB limit in this conditional budget |
| 8ENOB /0.14 | 0.915 | 1.711% | −29.14dB | Fails−30dB design target and converter allocation |
| 9ENOB /0.12 | 0.784 | 0.998% | −30.57dB | Conditional route; greater analog swing/current |
| 9.5ENOB /0.10 | 0.653 | 0.851% | −30.84dB | Lower-swing alternative;12/12 timed diagnostic exchanges decode |
| 9.75ENOB /0.08 | 0.523 | 0.901% | −30.75dB | Conditional route; more demanding DAC accuracy |

An optional `--whitening-seed 91` DATA control removes constant padding before
BCC encoding while keeping the final six termination bits zero. It uses a
known diagnostic mask, **not the WLAN scrambler or autonomous seed recovery**;
the unwhitened overload case remains the default. This distinguishes crest
artifacts from converter requirements without claiming a complete HE packet.
At4092bytes, ratio10, rounded span40 interpolation and the same12dB PA
hypothesis, the whitened control gives:

| ENOB /amplitude | Native peak | Converter error | Combined allocated EVM | Chip+PA nonlinear bound |
|---|---|---|---|---|
| 9.5 /0.10 | 0.289 | 0.842% | −30.85dB | 0.395% |
| 9 /0.12 | 0.347 | 0.994% | −30.58dB | 0.404% |
| 8 /0.24 | 0.694 | 0.985% | −30.60dB | 0.495% |

All three decode and clear this relative-mask screen by at least9.17dB.
**Do not infer a universal9.5ENOB DAC requirement from the padded low-amplitude
fixture.** Eight ENOB with more analog swing is another conditional route.
It needs internal filter/DAC headroom, slew/current, timed peak admission,
fixed-PA power calibration and more payload/seed/complete-waveform evidence.
The PA backoff in this comparison is relative to each packet's RMS: increasing
amplitude also increases the assigned PA threshold. It is not proof that a
fixed physical PA tolerates the higher drive. The lower-swing operating point remains an alternative; the fixed-PA and
headroom results below support preferring higher DAC utilization for further
integration, with the full-waveform and RF-drive gates still open.
The internal-state screen now accepts the same `--whitening-seed` rather than
applying unwhitened padding peaks to this alternate operating point.
`--tx-packet-internal-state --amplitude .24 --whitening-seed 91` requires
0.707V peak differential internal swing (0.353V symmetric per leg),36.3V/us
integrator slew,72.6uA capacitor current and208.6uA conservative summer-resistor
current at2pF in the equivalent state model. These sampled requirements do not
prove amplifier drive, CMFB or bias current, but do not rule out the8ENOB route.
Independent complete legacy TX DATA and returning ACKs also decode at all
eight rates with8ENOB/amplitude0.24, the five-pole candidate and clock seed831
with20ps added converter timing, for fixed PA envelope thresholds0.396502 and
0.951605. No leakage was enabled in this comparison. Both CRC results remain
separate from PA allocation: the lower threshold is driven much closer to
compression. The larger threshold represents a different PA operating point
or changed interstage scaling; it is not free improvement of the same board.
Keep the higher-swing route as an explicit alternative pending its fixed-PA
error/spectrum and complete HE tests, not as a newly qualified default.
A fixed-PA comparison now implements an explicit external TX-only attenuator,
with no automatic output renormalization. At8ENOB/amplitude0.24 and whitening
seed91, fixed PA input-P1dB envelope0.396502 gives a6.221% chip-plus-PA
nonlinear bound without attenuation (reject), versus0.4924% with7.6042dB
attenuation (within0.6%). The latter scalar diagnostic error is−38.15dB and
relative-mask margin9.94dB. Add `--pa-input-p1db-envelope .3965020773807595
--pa-input-loss-db 7.60422483423212` instead of relative PA backoff to reproduce.
The loss is20log10(0.24/0.10), preserving approximately the lower-swing PA
input level while using more DAC range; it is not a higher-compression-point PA.
All eight independent legacy TX DATA and return ACK cases also decode with
this attenuation,8ENOB, clock seed831 and20ps added converter timing.
The shared path now puts assigned chip TX noise before the external attenuator
and PA, consistently with the spectral screen. The passive-loss model omits
attenuator thermal noise and impedance/loading: reserve those in the analog
noise and matching budgets before adoption. Place it in the TX branch only;
it must not consume RX sensitivity or alter wired operation. This is a
credible external-passive mitigation, not yet a qualified board or HE route.
The same PA transfer now accepts `--pa-phase-deg-at-p1db`: an explicit
memoryless AM/PM hypothesis whose phase scales with input envelope power and
equals the given degrees at input P1dB. It is not a fitted device law.
At the preferred8ENOB/0.24/7.6042dB-attenuation point, the whitened seed91
chip-plus-PA nonlinear bounds are0.5122%,0.6432% and0.8358% for1,3 and5degrees
respectively. All still clear the relative-mask screen by approximately9.93dB;
the3/5degree cases nevertheless fail the0.6% nonlinear allocation. Use1degree
as the present bounded integration hypothesis, with no assertion that a
particular PA achieves it. Both clock seeds in the compact joined report now
include this1degree AM/PM and retain all legacy DATA/return ACKs. Memory,
frequency dependence and complete HE crest remain separate uncertainty gates.

`matched_attenuator_budget` now prices the ideal matched50ohm pad. A7.6042dB
pi attenuator uses49.58ohm series and121.43ohm shunts in the ideal resistor
network. At300.15K over20MHz, its internally generated output noise is
6.849e-14W. With−11dBm delivered to the PA, this contributes0.00294% RMS,
small compared with the0.8% analog-noise allocation. The source's attenuated
noise must still be included; thermal-equilibrium and port-matching tests
check that accounting. Resistor parasitics, tolerances and unmatched ports
remain outside this calculation; these values are not a qualified GHz PCB.
Supplying−11dBm after the pad requires−3.396dBm at its input before further
losses. This is an inverse drive requirement, not demonstrated GF180 power
at the8ENOB/0.24 operating point. It must be joined to the voltage-to-power
calibration and distortion envelope before claiming useful radiated power.
The existing waveform attenuator omits this small thermal term; include it
in the aggregate noise allocation rather than claiming a noise-free passive.
The inverse `rf_drive_requirement` makes the RF terminal cost explicit.
At−3.396dBm mean delivered power and10dB crest into50ohm, envelope peak is
0.676V. With the inventory's40ohm differential source resistance, the required
source differential peak/current are1.218V/13.53mA with zero shunt capacitance,
1.285V/16.97mA with1pF and1.731V/33.60mA with3pF at2.412GHz. Capacitances
are differential equivalents, not individual pad values. Thus a large pad can
consume the apparent current margin even at modest average RF power. The28mA
RF-driver bias allocation is not a guaranteed peak-current capability; the3pF
case cannot be admitted on that allocation alone. This carrier-frequency
phasor screen excludes package inductance, matching resonance, nonlinear
output impedance and broadband waveform distortion. It supports retaining a
low-capacitance RF pad and external matching/lower-output alternatives, not
claiming that the normalized DAC waveform already delivers the required watts.





**Do not carry the8ENOB/10dB-backoff estimate into this TX operating point.**
Neither route is selected silicon performance. The higher-amplitude route scales
linear internal swing/slew/load by1.5 relative to the0.08 packet screen and must
retain PA distortion/power margin. The lower-amplitude route needs near-native
DAC accuracy. Increasing nominal code width, applying more backoff or relying
on CRC cannot silently close this gap. The injection assumes white equivalent
noise; DNL, coherent spurs, reference modulation, correlation and measured DAC
noise still need their own bounds. Quantizer-only results elsewhere are not
8ENOB qualification, and the scalar waveform error is not added again to this
allocation (which would double-count its converter contribution).

The intermediate9.5ENOB/amplitude0.10 setting is the lower-swing
integration alternative: it meets the converter allocation and−30dB combined
target in the4092-byte screen and decodes all12 timed diagnostic cases without
peak rejection. Its whole-burst relative-mask screen has9.09dB margin under
assigned impairments, before a qualified external PA. This is not an adopted
silicon specification: the margin is conditional on the other allocated errors,
and near-native DAC accuracy remains unproven. The joint TX operating envelope
must include external PA distortion, calibrated output power and recovery.

**External hardware evidence, not a selected BOM.** Qorvo's
[QPF4288A product page](https://www.qorvo.com/products/p/QPF4288A), checked
2026-09-28, lists a production2.4GHz PA/switch/bypassable-LNA/coupler FEM,
5V supply,33dB TX gain and+22dBm HE40 MCS11 output at−43dB dynamic EVM.
It also lists14dB RX gain,1.9dB NF and5dB bypass loss. These support an
external gain/observation route; they do not qualify our board or transient
model. The linked PDF was unavailable during this check, so switching time,
control thresholds, current and full test conditions remain unverified.

Deduction from the listed TX gain: approximately−11dBm FEM input could produce
+22dBm output before further board losses, subject to gain compression and
calibration. Thus useful board power need not require a0dBm GF180 output.
However,−43dB EVM is0.708% RMS, greater than our0.6% total nonlinearity
allocation. Dynamic EVM is not pure nonlinear residual, so neither equate it
to our Rapp coefficient nor claim that headline operating point meets our
allocation. Qualify a lower-output operating point and its full error spectrum.
External RX gain must enter the overload/AGC model; bypass incurs the listed
loss and cannot silently preserve the present2dB frontend-loss assumption.
Keep FEM supply/current outside the die budget and include its board coupling
in the rail model. FPGA-owned FEM controls and external coupler measurements
preserve the generic chip interface and require no on-chip Wi-Fi profiles.

The optional `--pa-p1db-backoff-db` screen applies a memoryless, unity
small-signal-gain AM/AM compression hypothesis after the chip TX path, including
its filter tail. It defines the input envelope at exactly1dB gain compression;
the threshold is fixed from the active-burst RMS and is not recomputed for the
tail. At the intermediate9.5ENOB/0.10 operating point:

| Average input backoff below input P1dB | Scalar diagnostic error | Relative-mask margin |
|---|---|---|
| PA bypassed | −39.46dB | 9.09dB |
| 12dB | −25.88dB | 8.22dB |
| 9dB | −23.50dB | 7.44dB |
| 6dB | −21.22dB | 5.16dB |

Attribution is essential here: the4092-byte diagnostic has19.95dB input crest,
and98.37% of the12dB-backoff compression-error energy belongs to its final
symbol, dominated by unscrambled zero padding. It is an overload stress case,
not a basis for selecting realistic HE PA backoff. A3944-byte diagnostic has
no extra pad bits after the encoder tail and9.65dB crest. With all analog,
resampler and DAC assumptions unchanged, it gives:

| PA input backoff,3944-byte control | Scalar diagnostic error | Relative-mask margin |
|---|---|---|
| PA bypassed | −39.74dB | 9.20dB |
| 12dB | −39.11dB | 9.20dB |
| 9dB | −35.06dB | 8.89dB |

Reproduce with the same `--tx-preeq` configuration and `--payload-bytes 3944`.
Retain both payload cases; do not silently clip or normalize the padded one.
The no-padding control supports further frontend integration, but neither
synthetic packet substitutes for scrambled complete HE waveform qualification.
The reported `pa_screen` attributes crest, fraction above input P1dB, and final
symbol compression-error share so this artifact cannot be mistaken for a
process or PA limitation.

The PA screen now also compares its in-band residual, after one fitted complex
scalar, against the existing0.6% **total chip-plus-PA nonlinearity allowance**.
For the3944-byte control,12dB backoff consumes0.419% and leaves0.181% for chip
nonlinearity;9dB consumes1.464% and therefore fails the allocation despite its
−35.06dB scalar diagnostic error. The padded4092-byte stress consumes4.570%
at12dB. These residuals use the active-burst±9.53125MHz band and are hypotheses,
not standard TX EVM. Do not replace the total nonlinearity allocation with PA
error alone or RSS together deterministic errors to manufacture margin.
A paired shared-path run now disables only the assigned chip cubic term
(default0.02 in normalized envelope units), retaining identical DAC samples,
clock, supply and noise realizations. Its fitted-scalar residual is0.0239%
for the3944-byte control. Adding chip and PA residual norms on a common
cascaded reference gives0.4431% at12dB PA backoff, within the0.6% allocation;
9dB gives1.4878% and remains rejected. The residual-norm calculation credits
no cancellation. Thus the current **behavioral** chip-plus-PA assumptions fit
at12dB in this control, with0.1569% remaining nonlinear margin. This does not
identify the physical GF180 cubic coefficient, PA AM/PM or memory, nor cure the
padded-waveform stress failure or establish complete HE performance.

The converter-only combined allocation remains separate; its passing status
cannot admit a PA configuration with negative remaining nonlinear allowance.

**Do not select a PA using the relative-mask result alone.** These cases pass
that screen while waveform fidelity degrades severely. The diagnostic's
training/padding amplitude distribution and scalar observer are not standard
HE TX EVM, so these numbers do not specify the backoff a real HE packet needs.
The separate combined allocation still substitutes only converter error before
the PA; it does not certify the compressed result. This PA hypothesis adds no
AM/PM, memory, noise, absolute output-power calibration or switch recovery.
Those remain part of the external-frontend gate. The shared timed RF path now
supports a fixed `pa_input_p1db_envelope`, applied to TX reconstruction and its
idle tail before optional TX-to-RX coupling. It never renormalizes each packet.
With threshold0.396502 in model envelope units (the3944-byte control's12dB
hypothesis),9.5ENOB/amplitude0.10, ratio10 and rounded span40 interpolation,
all eight independent legacy DATA-to-ACK exchanges decode. Antenna response
intervals are9.990–10.010us and minimum queue-prefill margin is0.954us.
Reproduce using `external_wifi_reference.py --tx-candidate --resampler-span 40
--resampler-fraction-bits 14 --dac-enob 9.5 --integrator-ratio 10
--amplitude .1 --pa-input-p1db-envelope .3965020773807595` plus the existing
independent reference-tools path. This checks timed legacy operation with
assigned AM/AM; it does not establish watts, PA memory, HE interoperability,
physical switching transients or calibrated antenna delay under compression.
Adding `--tx-data-check` exercises independently generated128-byte DATA on
TX at every legacy OFDM rate, instead of only the6Mbps ACK. With the same
fixed PA threshold and DAC/filter settings above, all eight TX DATA packets
pass peer L-SIG, exact payload and CRC checks; peak TX queue occupancy is876
of1024bits. The ordinary DATA-to-ACK run remains the MAC-response check.
The DATA-TX option then receives an independently generated6Mbps ACK,
scheduled10us after the transmitted antenna packet-end marker, through the
same retained RF/filter state and finite RX queues. All eight return ACKs pass
header, exact payload and CRC checks, with420bit peak RX queue occupancy.
This nominal return path retains the assigned500ns direction settling and
zero effective TX-to-RX leakage; it does not demonstrate physical overload or
switch recovery. The initial DATA-to-DATA stimulus remains a scheduled PHY
test, not a valid MAC exchange. Antenna packet end is the calibrated preamble
marker plus waveform duration, not the end of the DAC/FIR tail. HE,
long-packet behavior and physical leakage/recovery remain unqualified.
The runner also accepts `--tx-rx-coupling`, using the same retained RX filter
state during TX, idle and the returning ACK. Ratios0.31623 and3.16228 both
retain all eight return ACKs in the linear-state model. Their maximum injected
RX-filter envelope peaks are0.0944V and0.9439V respectively. These ratios follow
`tx_rx_filter_coupling` for an assigned+20dBm output at0.1 model-envelope RMS,
20dB early RX gain and60/40dB isolation; they are calibration hypotheses, not
measured output power or isolation. In particular, the larger case cannot be
admitted from CRC success: nearly1V filter-input forcing may invalidate the
linear state model, and internal state swing/clamp recovery is unbounded here.
The report exposes the peak requirement instead of claiming the ten-microsecond
ACK gap proves physical overload recovery. Gain-invalid samples are rejected
in the return ACK just as in the initial received packet.
The independent runner can now use `--clock-seed` and `--converter-jitter-ps`
through the same shared clock setup as the diagnostic exchange, eliminating a
separate clock-assumption implementation. With seeds831/834,−115dBc/Hz colored
noise at100kHz,−155dBc/Hz floor integrated over1kHz–8MHz,48 spectral bins,
and20ps RMS in four persistent converter-clock lines, all eight DATA-TX/return
ACK cases pass for both seeds with the candidate DAC/filter/PA and0.31623
leakage ratio together. Largest sampled clock displacement is56.53ps.
This is sampled finite-spectrum evidence, not a worst-case jitter bound,
statistical PER, independent ADC/DAC branch-noise qualification or HE proof.
Reproduce by adding `--clock-seed 831 --converter-jitter-ps 20
--tx-rx-coupling .3162277660168379 --tx-data-check` to the independent command,
and repeat with seed834. Preserve the same realization through RX, TX and idle;
do not reset phase at direction changes or pass phase truth to the receiver.
The optional `--recovery-bounds` JSON joins the existing exponential residual
budget to this return-ACK path. It subtracts tail, switch, RX pipeline and
reserve once, then rejects excessive residual recovery before attempting ACK
reception. With `initial_residual_dbm=-20`, `steady_residual_dbm=-100`,
`allowed_residual_dbm=-80`, `tx_tail_s=0.5e-6`, `switch_s=0.5e-6`,
`receive_pipeline_s=0.15e-6`, `reserve_s=2e-6`, the10us gap leaves6.85us
for recovery and limits the amplitude-decay time constant to0.977us.
`recovery_tau_s=0.3e-6` admits all eight candidate/PA/leakage/seed831 exchanges;
`2e-6` rejects every case regardless of potential CRC success. Every bound
must be supplied explicitly; omitted bounds leave recovery unqualified.
This is a conservative envelope gate, not injected nonlinear recovery or a
GF180 prediction. Initial residual need not equal instantaneous TX leakage;
charge storage can make it worse. The peer preamble is never borrowed as
extra recovery time. All parameters are hypothetical until circuit/model
refinement and eventual characterization support them.




The timed exchange now uses the same finite-integrator ratio10, rounded14-bit
span40 resampler and effective DAC noise assumptions. At9ENOB/amplitude0.12,
7 of12 diagnostic MCS7 exchanges reject the waveform at native DAC peak
admission, before queue mutation. The separate4092-byte allocation above does
not establish a universal amplitude limit. At9.75ENOB/amplitude0.08, all12
diagnostic exchanges decode and retain the scheduled approximately10us response.
This is a conditional low-swing route, not proof of physical DAC accuracy or
standard TX EVM: the decoder corrects errors that a transmitter measurement
must still count, and the harsher LO spectra exceed the assigned phase budget.
The diagnostic has synthetic padding and incomplete HE signaling, so its crest
failures also cannot establish the crest distribution of real HE packets.
Independent complete legacy DATA-to-ACK exchanges at all eight OFDM rates pass
with the9ENOB/0.12 configuration; that does not override the diagnostic failures.

Reproduce the joined comparison with `verification/wifi_client_exchange.py
--phase-noise-screen --tx-candidate --resampler-span 40
--resampler-fraction-bits 14 --integrator-ratio 10 --converter-jitter-ps 20`,
using `--dac-enob 9 --amplitude .12`,
`--dac-enob 9.5 --amplitude .1` and `--dac-enob 9.75 --amplitude .08`. Keep peak admission on the actual corrected,
resampled waveform; do not silently normalize it, since normalization changes
the converter noise and calibrated transmit-power budget.

**Keep the five-pole candidate as the preferred Wi-Fi improvement:** stronger
FPGA interpolation fixes the near-channel image but does not eliminate the
analog DAC-image requirement. Reconfiguring the existing three-pole filter
barely clears this screen at lower cutoffs while consuming headroom, with no
credible allowance for PA/board effects. This rejects a nominally simpler
substitution under these assumptions, not all possible external filtering or
transmitter implementations. Hardware selection still requires the candidate's
current/headroom/area feasibility and full-packet emissions qualification.

The same TX screen accepts `--mcs 0..7`, `--payload-bytes` and
`--amplitude`; modulation-specific decoding and spectral scoring share the
same corrected DAC/analog path. Across MCS0–7 and 14/128/1024-byte diagnostic
payloads, using span40/14-bit interpolation, 49-tap/12-bit correction and
ratio10 integrators, 23 of 24 cases at amplitude0.08 pass peak admission and
CRC, with relative-mask screening margins5.95–8.98dB. The128-byte MCS0 case
exceeds the DAC peak allowance; amplitude0.04 admits it at peak0.534, CRCpass,
scalar error−35.31dB and screening margin4.87dB. **Keep per-waveform native
peak admission and calibrated power selection; do not assign one universal
amplitude from the MCS7 result.** Unscrambled diagnostic padding exaggerates
some crests, so this is neither a required6dB real-packet backoff nor HE crest
statistics. Backoff must also satisfy the absolute output-power/noise budget;
positive relative-mask margin alone cannot admit a power setting.

Finite-integrator waveform checks now use the same modal surrogate in exact
held-DAC reconstruction and calibration fitting (`--integrator-ratio 5`, `10`
or `20` with the span-40/14-bit resampler and five-pole/49-tap candidate).
All three decode. Relative-mask screening margins are 10.54/8.61/7.79 dB,
scalar errors −39.58/−40.07/−40.31 dB and native peaks 0.483/0.523/0.545.
The extra high-frequency poles can improve image rejection while worsening
occupied-band phase response; calibration accounts for the latter. Keep the
existing provisional ratio≥10 planning target: passing this waveform screen
at ratio 5 does not remove its longer settling/internal-state concerns. The
ratio denotes an effective integrator pole, not op-amp GBW. Slew, extra poles,
noise/current, loading and actual calibration accuracy remain unproven.

`rf_filter_tradeoff.py --tx-packet-internal-state` now drives the explicit
real-pole→low-Q→high-Q state realization with the same corrected 4092-byte
OFDM packet, quantized DAC, span-40/14-bit interpolation and ratio-10
integrators. At the inventory’s1V differential per normalized DAC unit, input
differential component peak is
0.523 V, largest internal component 0.587 V and integrator slew 22.94 V/µs.
With 2 pF integration capacitors, maximum capacitor current is 45.88 µA and
conservative single-summer resistor-load current is 163.47 µA. Doubling time
substeps from 8 to 16 leaves swing/slew unchanged at reported precision and
raises the load maximum to 163.73 µA. These are sampled linear requirements,
not continuous peak bounds or amplifier supply current. They strengthen the
headroom/load specification beyond the 0.25 V single-tone screen; the assumed
voltage scale, summing amplifiers/CMFB, noise, slew distortion and 4 mA branch
candidate ceiling still require a coherent physical feasibility argument.

For the9ENOB/higher-amplitude route, `--tx-packet-internal-state --amplitude
0.12` gives0.785V native differential peak,0.880V maximum internal differential
swing (0.440V per leg only under symmetric common-mode operation),34.42V/µs
equivalent slew,68.83µA capacitor current and245.12µA conservative resistor-load
current at the model's2pF equivalent capacitance. Input peak is checked before
quantization; an overrange waveform cannot be silently clipped into this screen.
The voltage is compatible with a plausible differential swing hypothesis, but
CMFB, physical per-leg RC mapping and amplifier drive remain unresolved.

**Current decision:** charge2mA per DAC (1mA steering plus1mA provisional
local support) and apply the existing source override explicitly. The primary
external-clock RF subtotal is234mA; reserving4mA per five-pole TX-filter branch
makes240mA, leaving0mA under the unchanged240mA ceiling. The input conditioner,
quadrature, distribution and other warm circuits remain charged; only the unused
RFPLL changes from12mA to0.1mA. Autonomous totals are245.9/251.9mA without/with
the filter candidate and remain outside this envelope. Preserve autonomous
capability for separate qualification, without claiming external-source savings
for it. Per-rail effects and DAC support assumptions are owned by the
[power allocation](power-partition.md). This closes an allocation contradiction,
not the physical filter/DAC or power-distribution qualification.

`rf_filter_tradeoff.py --tx-amplifier-current` provides an explicit conditional
bias screen for five effective single-pole amplifiers per branch: assumed
120 MHz closed-loop target, 6 nV/√Hz white noise, gamma=2/3, effective
capacitance 0.25/0.5/1 pF, noise gain 2/4 and gm/Id 5/10 V⁻¹. Required gm is
the larger of the bandwidth and thermal-noise bounds. With 0.5 pF, noise gain
4 and gm/Id=10, input-bank bias plus an assigned 0.8 mA support reserve totals
1.55 mA; 1 pF makes it 2.31 mA, and gm/Id=5 raises that to 3.82 mA.
Do not interpret the support reserve as demonstrated driver/summer/CMFB current,
or identify this effective capacitance with the 2 pF integration capacitor.
Mapping the surrogate pole to amplifier closed-loop bandwidth is itself an
assumption. **The4mA candidate ceiling covers these scenarios, not all possible physical
implementations.** Topology-dependent noise gain, compensation, loading and
support current must still be reconciled before selection. No noise requirement
is relaxed and the additional current is explicitly charged to the RF rail.

An FPGA-only cyclic-suffix overlap window is available in that screen as
`--tx-window-samples 4` or `8`, before the correction FIR. Useful FFT samples
remain unchanged; the suffix is included in emitted duration. For the 4092-byte
case, eight samples improve integrated 10–20 MHz energy only from −20.01 to
−20.23 dBc, while raising native component peak from 0.579 to 0.616 and reducing
unmodified prefix protection from 0.8 to 0.4 µs. Scalar-only diagnostic EVM
remains about −40.9 dB and decoding passes. **Keep this option disabled by
default:** the demonstrated benefit does not justify the guard/headroom cost.
This window only understands uniform diagnostic 256+16 rows, not actual HE
field transitions; it is not a qualified general packet formatter or a cure
for the unresolved near-channel mask.

Do not assume physical RX/TX filter sharing. An elliptic candidate has greater
dispersion and substantially worse stale-calibration sensitivity. A constrained
65-tap alternative improves the diagnostic peak only 1.7% and image peak 0.24 dB
while adding 0.212 µs delay; retain the 49-tap candidate for now. The fitter's
optional stopband penalty remains available for measured-response work.

Calibration and compatibility screens resolve different questions:

| Screen (`rf_filter_tradeoff.py`) | Finding / decision |
|---|---|
| `--tx-tolerance` | Across 32 pole-frequency/Q sign corners, ±1% mismatch gives 2.619% worst linear error with stale correction, or 1.158% after one delay refit. Nominal coefficients plus a cutoff trim are insufficient. |
| `--tx-recalibration` | At ±5% stage mismatch plus an illustrative 100 MHz lag, 129 synthetic response measurements and 49-tap refitting give ≤0.1341% held-out RMS error with 0.1% coherent measurement error. At 0.3% measurement error some cases exceed the 0.3% filter allocation. |
| `--tx-bypass` | To preserve the old three-pole response, bypass one biquad **and** retune the retained stage to Q=1. Leaving Q=0.618/1.618 gives −4.18/+4.18 dB cutoff error. Switch loading, trim range and bypass cost remain unpriced. No bypass hardware/order control is selected. |

The finite-integrator screen `--tx-integrator` adds a stability requirement.
In the existing 1/[s·(1+s/rho)] surrogate, rho=2 is unstable; rho=3 is stable
but has about17 µs dominant-mode decay to0.1% and2.87× occupied-band gain.
A fitted FIR still reports only0.061% held-out error there, demonstrating that
corrected frequency response cannot establish analog readiness. At rho=10,
the corresponding decay scale is0.426 µs and gain1.30×. Use rho≥10 as a
provisional planning target at12MHz; its120MHz effective model pole is **not**
an op-amp GBW requirement. Dominant-mode decay is not a certified step-settling
bound: residue weights, internal state swing, noise gain, slew, extra amplifier
poles and loading still require the chosen topology. Digital correction cannot
rescue an unstable or internally saturated circuit. Price these requirements
against the candidate current/area allocation before selection.

`--tx-internal-state` extends the existing explicit LP/BP/drive state model
to the all-pole candidate and checks its transfer against modal evaluation for
all six section orders. The preferred order is real pole → Q=0.618 → Q=1.618.
At rho=10,0.25V equivalent differential input peak and1pF integrators, it requires
up to0.326V observed state swing,19.5V/µs integrator slew,19.5µA single-capacitor
current and49.3µA conservative single-summer resistor current across the occupied
band. These are single-tone requirements, not OFDM headroom or total bias power.
Capacitance/current scale together; smaller capacitors increase resistor/noise
constraints. Summers, CMFB, transistor noise, slew distortion and amplifier
loading remain unpriced. The4mA per-branch ceiling remains a physical qualification target.

`--tx-noise-current` prices independent resistor and assigned integrator
amplifier noise in that state model. At300.15K and6nV/√Hz amplifier density,
1pF capacitors yield0.304mV RMS output noise:0.381% at80mV signal RMS, but0.761%
at40mV. The latter nearly consumes the entire0.8% analog-noise allocation;
this filter contribution belongs **inside** that allocation, not on top of it.
2pF reduces per-branch noise to0.225mV (0.281%/0.561% when80/40mV is
also a per-branch signal reference) while doubling the0.25V-tone load
requirements to39µA capacitor/99µA summer-resistor peak current. Retain1–2pF
as sizing hypotheses until actual voltage scale, PA backoff and remaining-chain
noise are joined. Amplifier density/power, summer/CMFB noise, flicker and
additional finite-bandwidth-state noise are still assumptions or omissions.

I/Q reference conventions are explicit in `--tx-noise-current`: two equal
2pF/6nV/√Hz branches produce0.318mV complex RMS over all frequencies, or
0.397%/0.794% of80/40mV **complex-envelope** signal RMS. Integrating the same
state-model noise only over the observer's±10MHz band gives0.215mV complex RMS,
or0.268%/0.537%. Within the0.8% total analog-noise allocation that leaves at
most0.754%/0.593% for independently justified remaining-chain noise. This is a
conditional filter-noise allocation, not a second full analog-noise budget or
proof of amplifier bias feasibility; correlation requires a tighter allowance.

Use actual per-device complex-response calibration, not a sub-percent absolute
fabrication-matching assumption. The provisional measurement-error target is
0.1%; timing/reference-plane uncertainty and subsequent drift are additional.
Fit on one grid and validate on independent captures/frequencies. Maximum FIR
gain reaches 3.449 in the corner screen, so fit quality alone cannot admit a
coefficient table: also check native/analog peaks, spectrum and fixed-point
arithmetic. These linear screens do not establish packet EVM or real equipment
accuracy. Run recalibration with `OPENBLAS_NUM_THREADS=1` (about six seconds).

`IQCalibration` additionally fits flat gain/image/DC from aligned complex
captures; it rejects unidentifiable stimuli, ill-conditioned inverses and wrong
contexts. Its inverse runs before DAC peak admission. This does not replace
frequency-dependent correction or separate instrument DC from LO leakage.
Power tables use measured antenna power, no extrapolation, waveform crest
allowance and measurement uncertainty; RX tables map observed power through
known gain/context. The three-level RSSI-to-TX test is not fading/blocker proof.

#### Joint clocks, timing and frontend envelope

**Decision:** retain clean differential external LO as primary, external
characterization and FPGA correction tables. The five-pole TX candidate remains
unselected pending amplifier, resource, packet-edge and other-radio gates.
Successful decoding does not close the clock or TX-quality gate.

`wifi_client_exchange.py --phase-noise-screen` retains one 48-line LO realization
from 1 kHz–8 MHz across RX, idle and TX, with the existing common supply tone.
LO/64 preserves time jitter. Optional `--converter-jitter-ps 20` adds 20 ps RMS
at the converter carrier using four equal-variance persistent lines at
73 kHz, 611 kHz, 2.3 MHz and 7.1 MHz; it is an assigned spectrum, not a physical
jitter ceiling. ADC interpolation uses an 80 MS/s grid; DAC edges are continuous
in time. Separate ADC/DAC branch noise, broadband aperture noise and host edge
jitter remain absent.

| Assigned LO: density at 100 kHz / floor (dBc/Hz) | Phase RMS (rad) | Maximum LO-derived edge error | Maximum peer CFO: acquisition only / pilot tracking |
|---|---|---|---|
| Clean: −115 / −155 | 0.00795 | 1.48 ps | 232 / 45 Hz |
| Middle: −105 / −150 | 0.02515 | 4.39 ps | 320 / 86 Hz |
| Weak: −95 / −140 | 0.07952 | 13.60 ps | 1236 / 240 Hz |

Four seeds per spectrum all decode. `--track-pilots` updates the estimate from
up to eight final received DATA-pilot phases after valid CRC, without LO or
payload truth. Insufficient symbols retain acquisition. The update must fit
2 µs FPGA decision time (assumed, not RTL-proven). Real HE polarity/RU geometry,
short triggers, interference/fading confidence and 350 Hz/10% CCDF qualification
remain open. Adding 20 ps converter jitter leaves maximum peer CFO about
45/86/240 Hz and increases total maximum edge errors to 57/59/66 ps.

Cross-check with `external_wifi_reference.py --track-pilots` uses independent
complete legacy OFDM DATA at all eight rates and actual ACK waveforms. Both
acquisition-only and pilot-update runs decode all nine incoming packets and
eight replies, with 878-bit TX queue high-water. For these short DATA records,
the largest injected-reference estimate error worsens from 147.88 to 316.45 Hz
with the tail update; largest peer-measured ACK error also worsens from
891.46 to 1053.27 Hz. The short ACK measurement includes its own estimation
error and is not the emitted carrier truth. This contradicts blanket promotion
of the longer diagnostic-packet mitigation: keep tracking opt-in until a
confidence/observation-length rule demonstrates benefit under interference.
Legacy polarity is handled modulo pi (requiring less than pi/2 rotation per
symbol); no expected payload or injected CFO enters the estimate. This is
independent legacy evidence, not HE trigger qualification.

Two metrics deliberately expose different effects:

- `reference_evm` scores transmitted DATA truth after training equalization and
  received-pilot tracking. Truth enters scoring only; wrong decisions count.
  With pilot tracking and 20 ps converter jitter, worst RX values are
  −25.77/−25.45/−23.75 dB and peer-observed TX −39.00/−37.31/−31.72 dB.
  Equalization can conceal static TX distortion; TX limits do not apply to RX.
- `tx_scalar_observer_evm` removes only one training-derived complex gain,
  retaining delay error and carrier drift. The normative three-pole path lacks
  calibrated observer alignment and scores roughly +4.24 dB, which is neither
  a hardware verdict nor a usable jitter limit. The corrected candidate below
  includes its declared FIR delay in observation and actual TX scheduling.

Use `--tx-candidate --track-pilots --converter-jitter-ps 20`. Physical cutoff
and correction-fit cutoff are independently controlled by `--tx-cutoff-scale`
and `--tx-calibration-scale`, both relative to 12 MHz. Correction uses 49 taps.

| Physical / calibration scale | Clean LO scalar error | Middle LO scalar error | Weak LO scalar error |
|---|---|---|---|
| 0.99 / 1.00 | −30.95 dB | −26.48 dB | −19.28 dB |
| 1.00 / 1.00 | −33.50 dB | −27.25 dB | −19.44 dB |
| 1.01 / 1.00 | −31.14 dB | −26.58 dB | −19.33 dB |
| 0.99 / 0.99 | −33.40 dB | −27.23 dB | −19.48 dB |
| 1.01 / 1.01 | −33.29 dB | −27.19 dB | −19.45 dB |

Each row covers twelve exchanges, all decoding; numbers are worst across four
seeds at each LO spectrum. Nominal and recalibrated TX queue high-water is
824/1024 bits. Nominal candidate receiver-equalized TX scores are
−39.61/−37.85/−32.81 dB, illustrating what the receiver hides.

**Implication:** stale ±1% cutoff drift costs about 2.5 dB in the clean case;
exactly known drift is recoverable with FPGA coefficients, but filter correction
does not repair LO error. These synthetic DATA results retain residual CFO and
are not standard antenna EVM measurements. Keep measurement uncertainty and
drift acceptance separate from exact-calibration results; do not promote the
candidate or relax clock specifications on decoding success. Physical spectra,
PA/board distortion, statistical PER and full HE measurements remain required.

The fast module `system_model/architecture_fast/rf_quality_budget.py` screens
ENOB/correlation and frontend recovery. The selected −30 dB allocation has only
0.51 dB independent-noise margin; a common positive pair correlation above
0.0905 consumes it. At an 8-ENOB sine-based estimate, correlation 0.25 gives
−29.30 dB; at 7.5 ENOB, independence gives −29.72 dB and full correlation gives
−26.33 dB. These are sensitivity bounds, not physical covariance estimates.
Retain all bounded residual allocations, including calibration drift. Do not
relax bookkeeping to obtain a pass: identify shared clock/supply sources without
double-counting, then improve actual noise/distortion or converter utilization.

`AntennaTimingCalibration` admits a scheduled DAC edge only when both ends of
the calibrated antenna-marker delay interval fit the requested tolerance,
before changing queues. The default 0.4 µs zero-width interval is still an
assumption. The response arithmetic totals 6.31024 µs against a supplied 10 µs
stress gap; each protocol's actual deadline controls admission. FPGA FIR delay,
transport, final decoding/FCS decision, prefill and board readiness all count.
An accurate timestamp does not prove the analog path has settled.

The shared RF path can now inject reconstructed TX leakage into the warm RX
filter and retain that history through TX, idle and RX. The optional
`tx_to_rx_filter_coupling` is an effective post-mixer voltage ratio, including
unspecified board coupling and RX conversion gain; it is **not** a switch
isolation number. Default zero preserves the explicitly isolated comparison.
A held-burst test shows nonzero residue after changing to RX and subsequent
filter decay, without packet-local state reset. This connects linear filter
memory only: LNA/mixer overload, clamp charge, PA shutdown, off-state loading
and a measured coupling-to-isolation mapping remain absent. Do not equate a
quiet decoded packet after padding with qualified 500 ns receiver recovery.

`rf_power_calibration.tx_rx_filter_coupling` maps calibrated antenna TX power,
total isolation to the chip RX input, early gain and TX reference envelope to
that voltage ratio, using P=mean(|z|²)/(2R), consistent with `receive_frontend`.
For +10 dBm TX, 20 dB early gain and an 0.08 reference envelope, isolation
22/40/60 dB gives RX-input −12/−30/−50 dBm, filter-input RMS
0.794/0.100/0.010 V and effective coupling 9.93/1.25/0.125. These ratios are
not all safely linear. A 150-native-sample constant burst through retained TX
and RX filters leaves peak residue 16.42/2.07/0.207 mV over 0.5–1 µs after
the sampled burst boundary, measured before PGA by subtracting the matched
no-leakage capture. It is a linear stress probe, not an OFDM recovery limit;
nonlinear overload can make recovery worse. A 22 dB switch rating alone cannot
justify the 500 ns acceptance target. Require greater assembled-path isolation
or explicitly qualified receiver isolation/muting and recovery, without assuming
that keeping clocks/bias warm automatically keeps signal-path state clean.

The normative TX→RX sequence is driver mute and external PA disable, external
break-before-make switching, then RX acceptance after characterized overload/
charge recovery; clocks and required bias remain warm. In the recovery screen,
+10 dBm TX minus assumed 22/40/60 dB isolation is the initial equivalent residue,
with −100 dBm steady leakage, −90 dBm allowed residue and 100 ns switch delay.
A 500 ns total allowance requires recovery constants ≤42.7/54.9/80.2 ns.
Saturation can make initial stored residue worse; steady leakage above the
allowance fails regardless of waiting. These are illustrative requirements,
not measured protection/recovery or a universal RX sensitivity threshold.

The 500 ns switch allocation must not be confused with a universal total
receiver-recovery deadline. `rf_quality_budget.receiver_recovery_admission`
compares sequential TX tail, switch, recovery, RX pipeline and reserve against
the earliest peer RF arrival at the antenna reference plane. For an illustrative
10 µs peer gap, 0.5 µs TX tail, 0.5 µs switch, 0.15 µs pipeline and 2 µs reserve,
6.85 µs remains for receiver recovery. The 2.454 µs linear-history bound fits;
a 7 µs recovery does not. These are supplied assumptions, not a qualified board
or universal protocol interval. This preserves a credible slower-recovery route
without changing silicon or borrowing peer preamble time; the earlier 500 ns
combined recovery screen remains a stricter stress case, not the sole success
criterion. Nonlinear overload still needs a bound before this route is admitted.

For board screening, [SKY13351-378LF](https://www.skyworksinc.com/-/media/SkyWorks/Documents/Products/401-500/SKY13351_378LF_201132I.pdf)
has 0.50 dB maximum insertion loss and 22 dB minimum common-to-off isolation
below 3 GHz; its 100 ns switching figure is typical at the stated conditions.
[Johanson 2450BP15H0100001E](https://www.johansontechnology.com/products/integrated-passives/band-pass-filters/2450bp15h0100001e/)
lists 1.5 dB loss. Thus 2 dB leaves no matching/PCB margin; 3.5 dB remains the
acceptance allocation. Datasheet isolation is not board TX-to-RX isolation.
Extra isolation or separate antennas are allowed with their loss priced.
[PHA-1+](https://www.minicircuits.com/WebStore/dashboard.html?model=PHA-1%2B)
is an unqualified PA candidate: broadband/IP3 data do not prove OFDM EVM,
emissions or shutdown timing. None of these is an assembled-board endorsement.

Integrated Wi-Fi FEMs are a credible application-board alternative but are not
transparent replacements. For example, [Qorvo QPF7219](https://www.qorvo.com/products/p/QPF7219)
reports +20 dBm HE40 MCS11 at −43 dB dynamic EVM, integrated PA/switch/bypassable
LNA and bandedge filtering. It is discontinued, specifies 2.402–2.472 GHz and
6.5 dB RX bypass loss, so it is rejected as a universal reference-board choice.
Its −43 dB EVM corresponds to about 0.71%, already larger than the current
0.6% allocation for combined nonlinear residuals; vendor data at that output
point cannot be inserted as a budget pass. Lower-power operation might help,
but needs corresponding evidence. Other FEMs remain possible; admit each by
band coverage, receive loss/gain/noise, overload, TX error, supply and transition
requirements. Keep module controls on the FPGA and declare any application-board
band subset explicitly; do not narrow the transceiver's capability inventory.


`wifi_client_exchange.py --sensitivity-screen` uses actual supported fixed PGA
settings (27/42 dB), MCS0/7, a 512-byte diagnostic record and wanted levels
−50/−65/−75/−85 dBm, with no blocker or −40 dBm CW at +12 MHz. It retains the
assigned 6 dB NF, 2 dB board loss, default LO/supply and converter model.
MCS7 decodes at −65 dBm without the blocker at both gains, but with the blocker
only at 42 dB. Conversely, 42 dB clips and fails MCS7 at −50 dBm; 27 dB passes.
Neither setting decodes MCS7 at −75/−85 dBm. MCS0 reaches −85 dBm only at
42 dB in these cases. MCS0 strong-signal decoding can survive substantial ADC
clipping, so CRC alone does not establish an acceptable gain setting; its
synthetic zero-filled DATA padding also has atypical peaks.
This is one realization per condition, not sensitivity/PER or an AGC design.
It identifies a required gain/headroom tradeoff without selecting gain from
payload truth. Pre-ADC stage overload and realistic blocker spectra remain
unmodeled here. Next RX work must join causal gain settling with weak-signal
quality and acquisition, rather than infer useful range from −50 dBm success.

The existing `selected_rf.filter_settling_requirement` and
`timing_services.acquisition_admission` expose an upstream-gain limitation:
for `rx_finite_zero`, unit bounded linear history and 0.003 allowed residual,
the sufficient recovery bounds are 2.454/23.386/233.865 µs at
9.53125/1/0.1 MHz cutoff. At the widest setting, two feedback rounds need
10.077 µs including transport, exceeding an 8 µs window even before the
2 µs synchronization reserve. This conservative arbitrary-history bound does
not prove actual packet-driven settling takes that long, but cannot certify
the provisional 400 ns upstream guard. Prefer preloaded LNA and downstream
PGA-only corrections; qualify PGA settling separately. PGA reduction cannot
repair earlier-stage overload. Admit an LNA change only with its own retained-
state recovery bound and available training, or reject the operating envelope.
The fast gain-status count is a second constraint: at 37.5 MS/s,
2.454 µs settling plus 24 stale pairs needs 117 invalid-pair slots, fitting
the extended 127-pair status field when training time is available. `acquisition_admission`
now rejects either deadline overflow or count overflow instead of admitting a
gain action based on time alone. Longer recovery requires explicit capture
discontinuity, not silent count truncation. The receiver preserves sample time,
propagates invalid intervals through the default resampler's full FIR support,
excludes affected STF/LTF windows and rejects discontinuities inside DATA.

The gain-feedback bench connects native ADC events, finite queue service,
serialized six-fragment snapshots/gain status and downstream analog PGA state.
The FPGA receiver reconstructs timestamps and gaps exclusively from received
words; no internal validity mask or wanted-signal level selects its gain.
The fixed upstream RF/filter response is precomputed, but PGA/ADC sampling and
host observation execute causally. A100ns FPGA decision and worst-case H2D/CDC
bound are charged. The nominal200ns paired-PGA pole now supports the selected diagnostic cases:127-pair status admits the correction, and FPGA coarse acquisition uses32-sample correlation with a16-sample plateau. Both complete64-sample LTF checks remain required. The actual45-pair gap remains invalid through resampling. This is host algorithm selection, not a faster analog assumption; full HE interoperability and false-detection statistics remain unqualified.
See the [current issue register](risk-priorities.md#open-issue-register).

The FPGA diagnostic controller now gates one peak-based correction with a
sliding60-native-sample L-STF correlation (normalized score≥0.6), then freezes
gain. It uses a0.3 component-peak target and checks that any change settled
before the measured L-LTF boundary. This avoids treating persistent blocker
energy as a packet. With27dB initial PGA, MCS7 at−50/−65dBm wanted and no
blocker/−40dBm CW at+12MHz decodes without ADC clipping; the controller retains
27dB for the strong signal and selects42dB for the weak one. A blocker-only
capture produces no gain command. Delayed packets with±90kHz carrier offset
also decode and meet the settling check. Correlation arithmetic still needs
FPGA implementation within the assigned100ns decision allowance.

The32-case screen compares27/42dB initial gains, MCS0/7, wanted
−50/−65/−75/−85dBm and no blocker/−40dBm CW. **Keep both preloaded-gain choices;
do not claim one universally safe setting.** Starting at42dB recovers the
−85dBm MCS0 diagnostic, including the case where no gain decision is detected;
strong MCS7 packets then clip26pairs during acquisition before correction,
though none clip after settling and decoding passes. Real overload recovery
must qualify that route. Starting at27dB avoids that strong-signal acquisition
clipping but misses the weakest packets. MCS7 at−75/−85dBm remains unsuccessful.
Some MCS0 records clip their atypical unscrambled padding even after settling;
CRC success alone does not admit their gain/power setting. This is not PER,
complete HE training or AGC qualification across fading/modulated blockers.
Gain changes combined with peer-clock resampling remain unqualified. The
first-order PGA excludes offset injection, overshoot and physical noise.
PGA readiness is now calculated from initial/target linear gain and the supplied
relative residual limit. At 100 ns time constant and 0.003 relative error,
27→42 dB needs 561 ns and 42→27 dB needs 734 ns; the latter is slower because
error is relative to the smaller final signal. Corresponding gain-status counts
are 46/52 pairs with 24 stale pairs reserved, but two feedback rounds require
6.293/6.638 µs, exceeding the 6 µs acquisition allowance after reserving 2 µs
of an 8 µs window. Thus successful diagnostic decoding does not validate the400ns guard. For these step sizes that target would require time constants
no greater than about 71/54 ns respectively, before offset/overshoot recovery.
Use one admitted correction or preload gain unless the faster bound is justified.
No extra on-chip AGC policy or detector is implied.

#### Remaining closure work

1. Select and propagate the TX filter implementation only after compatibility,
   amplifier/loading, resource, calibration and packet-edge assessments. Keep
   wired and narrowband capabilities intact.
2. Establish the joint clock/converter/calibration operating envelope and board
   recovery limits; qualify triggered frequency/power corrections under
   interference, fading and drift using emitted-signal measurements.
3. Evaluate the wider RX setting with complete HE and DSSS/CCK packets and a
   qualified blocker spectrum, retaining sharp/narrowband options. The
   [RX reference](https://www.mathworks.com/help/wlan/ug/modeling-and-testing-an-802-11ax-rf-receiver-with-5g-interference.html)
   uses 4096-octet PSDUs, 10% PER and wanted level 3 dB above rate-dependent
   sensitivity. Exact per-MCS sensitivity/rejection thresholds remain open.
4. Complete independent HE SU/MU/TB signaling/payload/RU validation and compose
   real discovery/association → bidirectional HE → ACK/Block ACK → triggered
   uplink without resetting analog state or bypassing queues. Include required
   legacy basic rates. Diagnostic intents do not satisfy this milestone.
5. Close combined TX EVM, mask, unused-tone emissions and board timing before
   schematics. The [TX reference](https://www.mathworks.com/help/wlan/ug/modeling-and-testing-an-802-11ax-rf-transmitter.html)
   illustrates rate-specific limits; its MCS3 −16 dB limit cannot qualify MCS7.
   Then replace device/package assumptions with circuit and extracted evidence.

Independent HE references remain unavailable locally. A renewed source check
found an [MIT-licensed EHT generator](https://github.com/zonelincosmos/wifi7-eht-waveform-generator-python),
but its documented output is Wi-Fi 7 EHT SU, not HE SU/TB; it is not admitted as
an HE reference. The [512-sample classification dataset](https://github.com/RalucaNelega/IEEE-802.11-signal-dataset)
contains random DATA excerpts, not complete packet references. The Texas
Dataverse metadata API was retried and still returned HTTP 403. `he_reference_vectors.m`
is an **unexecuted** MATLAB/WLAN Toolbox exporter, not test evidence. The
[Texas HE-SU dataset](https://doi.org/10.18738/T8/1XMHZD) describes MATLAB R2021b,
20 MS/s complex vectors and paired configurations (CC0); downloads return 403.
The [MathWorks packet analyzer](https://www.mathworks.com/help/wlan/ug/recover-and-analyze-packets-in-802-11-waveform.html)
provides another reference route but is not executed here. Obtain IQ plus
configuration/payload truth, preserve normalization, and document interpolation;
20 MS/s samples do not contain trustworthy analog out-of-channel images.
PicoScenes is not a ready-to-run local dependency. Missing reference packets
block interoperability proof, **not** the analog readiness work above.

### Bluetooth LE acceptance versus stress probes

The contract now records partial numerical requirements from
[Bluetooth Core 6.2, Vol 6 Part A §4](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-62/out/en/low-energy-controller/radio-physical-layer-specification.html).
Keep ambitious sensitivity/blocker probes separately. The joined scan-request
fixture defaults to −80 dBm wanted and −40 dBm at 2 MHz offset; its waveform,
gain and loading assumptions do not constitute the standard interference test.
Failures there are not automatically protocol failures, and one clean packet
is not a PER qualification. BER selection depends on maximum **supported**
payload length, not merely the short packet used by a fixture. Match receiver
reference plane, prescribed PER procedure and all PHY conditions before claiming
support. This clarification does not relax or delete the existing stress goals.

The joined packet source now offers `blocker_modulation="gfsk_prbs15"`
as well as its retained CW default. The nominal external interferer reuses
the GFSK shaper; sequence and envelope checks pass. The selected-baseline
comparison (`selected_revision_check.py --ble`, report section
`package_ble_interferer_screen`) decodes all four packets: both blocker
waveforms and both supply-delay signs at −67/−50 dBm, +2 MHz offset. It
uses the selected RF ledger, differential input, internal switching pulses,
dynamic rail and causal 10-bit SAR. The original triangle rail guards remain
false. A separate coherent-period screen (`--rail`, section
`package_ble_rail_screen`) encloses the current 0.25 nH target in
2.684–3.167 V and the 0.5 nH comparison in 2.674–3.182 V, including
between-sample error over the complete 16 µs period. Both fit the assigned
2.5–3.6 V fixture interval at these fixed harmonic phases. Keep the selected
network hypothesis; the triangle warning alone does not require a change.
The adverse package still fails input qualification. The source-wise
phase-independent screen (`internal_phase_bound.py`) also encloses the
2426 MHz target in 2.668–3.180 V for any independent host/timing/core origin,
including ±1% board supply. This covers only the declared periodic spectra;
changed activity and transients remain unqualified. The base screen omits converter-current feedback. Its `--feedback` variant
now joins SAR reference-recharge current through the package, reference and
differential-input response: all four packets decode and converge in two
passes, with approximately 0.707 mV added peak droop and at most 2.776 µV
final rail-waveform change. This covers the recharge port, not all ADC
switch/comparator/clock current or live lifecycle feedback. One seed and channel do not establish
PER, package-corner robustness or protocol qualification.

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
| Lower-frequency RF stretch | Selected dual-edge divide-by-two quadrature reuses the RF chain for 240–1250 MHz carriers from 480–2500 MHz external input; board matching/filtering is band-specific. | Phase error, frontend tuning and useful signal quality remain unqualified. Native 1250–2400 MHz is not selected; other bands retain external conversion. |
| External frequency conversion stretch | Translate another band into the qualified on-chip RF band with board mixer/LO/filter; no extra chip analog pins. | Include conversion loss/noise, images, linearity, LO coherence and board power. This is an external system, not native wideband RF coverage. |
RF recipe sample-rate ceilings are allocation limits, not selected clock points.
The external-LO path samples at carrier divided by 64, 128, 256 or 512;
its maximum over the selected 2.400–2.500 GHz band is 39.0625 MS/s. FPGA
resampling must use that actual rate. Configuration admission does not prove
that every divider/filter combination serves every waveform.

The selected direct-LO range now includes the LoRa target through 2.500 GHz.
This closes the architectural tuning-range decision, not physical tuning or
packet qualification. Historical evidence ending at 2.484 GHz does not prove
the newly selected endpoint; frontend, quadrature and clock quality remain gates.

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

The selected common environment must hold the board/host assumptions fixed
while using the actual inventory for each exclusive payload mode. Check rail
headroom and model validity alongside decoding; an unbounded interval is not
a measured excursion, and a short receiver pass cannot override it. The older
paired robustness campaign is retired. See the
[current joined assessment](risk-priorities.md#open-issue-register)
for current ownership and evidence requirements.

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
