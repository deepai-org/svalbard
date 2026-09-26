# Open high-speed analog design survey

The ongoing [measured GF180 AFE reverse analysis](../verification/reference_afe/README.md)
reconstructs the submitted circuits and pad paths, tests bootstrap and loading mechanisms,
and distinguishes measured constraints from conditional physical estimates. Its findings
now inform finite-acquisition, noise and distortion scenarios in the transceiver model.

## Process specifications and performance estimates

This assessment includes the permitted external clocks/LOs and generous SMD
passives. Evidence classes must stay distinct: **published GF180 specification**,
**same-process simulation**, **measured other-process precedent**, and **engineering
sweep assumption**. Node name alone does not equate devices or RF passives.

| Quantity / source | Verified information | Use in this design |
| --- | --- | --- |
| [GF180 3.3 V device specs](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_1.html) | At W/L=10/0.28 and absolute VGS=VDS=3.3 V: NMOS Idsat 430/510/590 µA/µm; PMOS magnitude 210/250/290 µA/µm. Typical threshold 0.63 V NMOS, −0.73 V PMOS. | Quantitative device/bias anchors. Saturation current at this bias is not linear RF drive current, gm, fT or a speed guarantee. |
| [GF180 I/O electrical specs](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/electrical.html) | Listed 4–24 mA digital drive strengths are specified at DVDD=4.5–5.5 V under stated output-level conditions. | Do not import these current guarantees into the 3.3 V host model; use relevant library/circuit evidence. |
| [Same-process open PLL](https://github.com/2AMLogic/gf180-pll) | Pre-layout/pre-silicon; 150 MHz deterministic period-jitter study, random/noise-driven jitter explicitly missing, and unresolved closed-loop corner failures. | Useful methodology and circuits, not a GHz RF phase-noise bound. Proposal-only GHz PLL targets are excluded as achieved evidence. |
| [Same-process SAR](https://github.com/2AMLogic/gf180-sar-adc) | 10-bit, 1 MS/s target, 2 MS/s stretch; no silicon and retained distortion failures. | Comparator/reference/switch lessons, not a 40 MS/s ceiling or proof. |
| [Measured TSMC 180 nm LNAs, thesis abstract](https://ethesys.lis.nsysu.edu.tw/ETD-db/ETD-search-c/view_etd?URN=etd-0919123-233952) | At 2.4 GHz: one circuit reports 9.6 dB gain, 4.9 dB NF, about 10 mW; another 12 dB gain, 7.9 dB NF, 3.2 mW and −4.5 dBm IIP3. | Concrete modest-performance RF precedents, not best-case ideal simulations. GF180 devices, matching, bias and loading still need evaluation. |
| [Measured 180 nm SAR, conference author abstract S01.5](https://vlsicad2025.conf.tw/site/userdata/1639/file/session/Oral_1.pdf) | 40 MS/s, 9.21 ENOB, peak SNDR 57.2 dB, 1.7 mW; process is not identified as GF180. | Tens-of-MS/s conversion is plausible in this node class. Neither power nor peak ENOB is a GF180 prediction or guaranteed Nyquist performance. |

### Working estimates, not process guarantees

Use the following **initial engineering sweep ranges**, informed by these
precedents but deliberately not called measured GF180 limits or statistical
confidence intervals. Values outside them remain possible; update from our PDK
circuits rather than declaring failure at a range endpoint.

- 2.4 GHz LNA: investigate 8–15 dB gain, 4–8 dB NF and 5–20 mW as a first
  design region. Gain, noise, linearity and power are coupled, not independently
  selectable knobs. Include worse cases and matching/filter insertion loss.
- Complete receiver: retain 10 dB NF as a working scenario and sweep roughly
  6–15 dB. Derive it from stage gains/noise and passive loss, rather than assigning
  the LNA's NF to the whole receiver. The measured other-process LNA examples
  combined with an assumed 15 dB downstream NF and 2 dB pre-LNA loss provide
  explicit cascade scenarios in `feasibility-bounds.json`.
- Converter: sweep 6–9 effective bits at the required 20–40 MS/s operating
  points before relying on 9 ENOB. This is a useful sensitivity study, not a
  GF180 achievable range or a reduction of the intended capability. Budget
  reference/driver/clock/logic overhead separately from a published ADC core.
- External clock path: retain 0.5–10 ps added-jitter scenarios as **requirements
  exploration only**, not literature-derived GF180 performance estimates. Use a
  common integration band and distinguish source noise from receiver/buffer and
  distribution noise. A scalar jitter value does not replace a phase-noise mask.
- No defensible GF180 RF fT/fmax, 2.4 GHz oscillator phase-noise mask, or
  package-specific parasitic interval was established by this search. Their
  absence is not a negative performance result. The next estimation step is
  PDK operating-point/AC/noise characterization with explicit geometry, bias,
  finger/gate resistance and load, plus board/package uncertainty sweeps.

The UMC 180 nm sub-mW LNA paper encountered in this search is post-layout
simulation and states that certain inductor parasitic resistances were ignored;
its optimistic noise/power figures are not used as GF180 expectations.
[Paper](https://link.springer.com/article/10.1007/s42452-021-04402-0).


Searched online 2026-09-20 at user request. Primary repositories and papers
inspected; no design has been ported or independently reproduced in this survey.
These are reference candidates, not evidence that our GF180 chip meets its goals.

| Design and source | Published scope/evidence | Potential use and caveat |
|---|---|---|
| Stanford DragonPHY family: https://github.com/StanfordVLSI/dragonphy2 ; paper https://arxiv.org/pdf/2009.09077 | Measured16nm prototype:20GS/s interleaved ADC,5GHz phase interpolator; ADC5.6ENOB low-frequency falling to2.7 at Nyquist;175mW total ADC including four PIs | Time-domain conversion, timing calibration, interleaving and package lessons. Public v2 repository is related work, not a verified exact source release of the measured2020 prototype; original paper's dragonphy URL returned404. Closed foundry dependencies and enormous process difference prevent direct performance transfer. |
| OpenSERDES: https://github.com/SparcLab/OpenSERDES ; paper https://arxiv.org/abs/2105.13256 | SKY130; published post-layout2Gb/s,34dB channel-loss case,438mW. Repository has SPICE/GDS/netlists, inverter-based front end and oversampling CDR; GPL-3.0 | Strong wired-lane architecture reference, particularly resistively biased inverters and CDR. Simulation evidence, not a measured silicon claim or proof of PCIe compliance. |
| LC fractional-N PLL: https://github.com/Manimohan05/SG13G2_2.4GHz_LC_VCO_FPLL ; https://arxiv.org/html/2607.08852v1 | IHP SG13G2; paper reports post-layout2.4–2.48GHz,12.73mW,0.619mm²,estimated phase noise−100.8dBc/Hz at1MHz | LC alternative and OpenEMS inductor workflow. Repository says work in progress; paper versus README targets differ. Phase-noise extraction method needs scrutiny, not acceptance from a spectrum figure. GF180 metal/passive/device feasibility must be re-established. |
| Mabrains PLL: https://github.com/mabrains/PLL_design | SKY130 Bluetooth PLL; schematics, layout and integration files; explicitly experimental/in progress; AGPL-3.0 | Inspect divider, pump, loop and output-buffer topologies. No measured performance established in inspected landing page. |
| SPARX: https://github.com/iic-jku/SG13CMOS_SPARX | IHP CMOS six-port receiver generated for160GHz, with60–300GHz layout generation examples; EM fitting to circuit models and detector simulations | Valuable RF passive/EM-to-SPICE workflow for later physical work. Not evidence of measured160GHz receiver performance; passive six-port/detector architecture, not a160GHz CMOS gain chain. Top-level LVS listed WIP. |
| IHP AnalogAcademy: https://github.com/IHP-GmbH/IHP-AnalogAcademy |50GHz medium-power amplifier teaching module, plus analog/ADC examples | RF bias/S-parameter workflow. Educational design, measured amplifier results not established here; IHP SiGe HBT performance cannot be transferred to GF180 MOS. |
| JKU SAR: https://github.com/iic-jku/SKY130_SAR-ADC1 |12bit asynchronous non-binary SAR,about1.2MS/s repository maximum, post-layout capacitive-extraction characterization; Apache-2.0 | Self-timing, redundant decisions, integrated common-mode generator, segmented arrays. Useful but below our radio sample-rate class; oversampling increases output width while reducing bandwidth. |
| GF180 SAR: https://github.com/2AMLogic/gf180-sar-adc |10bit1MS/s target with2MS/s stretch, simulation/extraction work and explicitly recorded unresolved failures | Same-process comparator/switch/reference-load evidence to audit. Not a high-speed qualified solution; README reports post-resize SFDR failure. No silicon measurement established. |
| TinyWhisper: https://github.com/iic-jku/TinyWhisper | Open short-wave IQ transmitter;56MHz core clock,400kHz analog filter; source/measurement directories | Connected modulated TX, LO duty generation and diagnostic injection points. Lower RF/bandwidth class; repository presence of measurements does not establish a specific measured specification. |
| FASoC: https://github.com/idea-fasoc/fasoc | PLL and other analog generators; published65nm SoC silicon work | Architecture/generator reference. Full macro flow explicitly requires commercial tools, proprietary PDK/cells and private NDA files. Public code is not a fully public reproducible transistor implementation. |

## Next review priorities

1. OpenSERDES receiver/CDR and resistive-feedback inverter: nearest open wired
   architecture to our intended difficulty class. The inspection below identifies
   unresolved bandwidth and autonomous recovered-clock evidence; follow those
   specific limits before attempting reuse.
2. Mabrains and IHP PLL circuits: compare bias, divider, pump and LO buffer topology;
   evaluate LC feasibility separately from ring-loop repair. Do not import claimed
   phase noise without validating stochastic/periodic-noise methodology.
3. JKU SAR and the user-supplied Ricardo Nunes ADC: compare switching demand,
   self-timing and calibration while preserving our actual throughput requirement.
4. Stanford time-domain conversion as an architectural alternative, not a shortcut
   around GF180 timing noise, calibration, area and clock-distribution costs.

Search exclusions: open PCB SDRs using proprietary converter/RFIC chips, software
repositories for commercial SerDes, and papers without accessible implementation
are not counted as reusable open analog silicon. A GF180 ring-PLL proposal with
1.2GHz targets was found, but aspirational verification language does not establish
completed circuits or measured performance, so it is not a priority reference.

Circuit selection and the schematic-before-layout gate remain governed by the
[analog workflow](analog-design-workflow.md). The detailed inspections below are
reference evidence, not implemented GF180 substitutions.

## OpenSERDES circuit inspection

Inspected SparcLab/OpenSERDES commit a0b98f0d9fd9937a479d5e39a194a26b8d6dfb14
on2026-09-20. Local read-only reference checkout:/tmp/svalbard-openserdes-review.
No third-party circuit imported or simulated. Repository license GPL-3.0.

### Useful actual circuitry

Resistive_FB_inverter/Resist_FB_INV.src.net exposes a CMOS inverter with three
parallel5um NMOS and six parallel5um PMOS, nominal0.15um lengths. Feedback uses
two series diode-connected long-channel PMOS (W0.55,L8 in the netlist's units),
not a literal linear resistor. This is relevant to compact biasing of a sensitive
inverter, but its asymmetric nonlinear leakage/conduction cannot be equated to
our100kohm feedback. Body ties are to VDD. Recreate and measure its signed I–V,
bias equilibrium, small-signal impedance and loaded dynamics with GF180 devices
before considering substitution. Do not assume dimensions transfer across PDKs.
The accompanying PDF shows700mVpp input and1.8Vpp output; this does not qualify
our roughly190mVpp LO input or establish a frequency/bandwidth result.

### Critical clock-recovery evidence limit

OverSampling_CDR/README.pdf describes external-reference oversampling, multiple
samplers, FIFO/decision logic and boundary detection. Its maximum-frequency field
is blank. The results plot is labeled CDR clk(50kHz). PLL-based MM-CDR is listed
as future work. CLK_RECOVERY.lvs.v exposes CLK_IN, not an independently qualified
autonomous high-speed oscillator. Consequently the published2Gb/s link simulation
must not be attributed to this uploaded CDR without tracing its exact test setup.
The repository also contains Receiver_Bypassing_CDR, making this distinction
particularly important; its existence alone does not prove which path the paper
used. Current review does not resolve the paper-to-artifact correspondence.

### Reproduction issues

The .sp files begin with empty primitive subcircuits. The schematic CDL includes
$PDK_HOME/LVS/Calibre/source.cdl and nshort/pshort models with tool-specific
parameters. These are not standalone ngspice-ready open-PDK simulations without
mapping/dependency work. GDS/netlist availability is not runnable qualification.

Decision: retain as a circuit and architectural reference, downgrade any inference
of a ready2Gb/s recovered-clock implementation. No replacement for our wired
CDR verification or RF LO experiment. Potential follow-up is a small GF180
signed-I–V test of nonlinear feedback, only if current linear-feedback diagnosis
provides a reason to try it; do not blindly replace our self-bias resistor.

Sources:

- https://github.com/SparcLab/OpenSERDES/tree/a0b98f0d9fd9937a479d5e39a194a26b8d6dfb14/Resistive_FB_inverter
- https://github.com/SparcLab/OpenSERDES/blob/a0b98f0d9fd9937a479d5e39a194a26b8d6dfb14/OverSampling_CDR/README.pdf
- https://github.com/SparcLab/OpenSERDES/blob/a0b98f0d9fd9937a479d5e39a194a26b8d6dfb14/OverSampling_CDR/CLK_RECOVERY.lvs.v

## Ricardo Nunes TT07 SAR ADC inspection

Reviewed 2026-09-20 at the user's request. This is a design-reference review,
not a simulated GF180 port or a change to the retained ADC.

Sources inspected:

- https://tinytapeout.com/chips/tt07/tt_um_rnunes2311_12bit_sar_adc
- Wrapper repository https://github.com/rnunes2311/tt07-12bit_SAR_ADC at
  8552c5feec6dc6641e0f6fefb52748b432064b98.
- Its pinned core submodule https://github.com/rnunes2311/SAR_ADC_12bit at
  e830a7501b718e00acdbaa7f620a72dc49c078cd (also retrieved core HEAD).
- Core README, layout/SAR_ADC_12bit_sch.spice, state_machine.v,
  simulations/DNL_INL_extractor.py and schematic hierarchy inspected locally.
  Repositories declare Apache-2.0. No third-party circuit source copied into our
  implementation. Review checkouts are under /tmp/svalbard-*-review.

### Useful experiments for our design

1. Compare its IMCS/common-mode-based DAC switching sequence against our actual
   switching schedule. Our reference-driver failures make load reduction worth
   testing, not merely stronger regulation. Use our resolution, GF180 capacitors,
   conversion deadline and real reference drivers; measure signed charge on every
   reference including common mode, peak demand, decision error and acquisition.
   Reduced demand is a hypothesis, not a finding from this review. Moving current
   demand to VCM is not eliminating it.
2. Inspect its preamplifier and analog comparator-offset storage/update circuit
   when implementing calibration. Test range, polarity, convergence, residual
   offset, leakage and timing under our GF180 models. This cannot correct our
   code-dependent reference droop or replace noise/linearity verification.
3. Adapt its explicit switch sequencing and break-before-make concept to actual
   transistor-generated controls. Our selected ideal phase separation is not a
   physical timing implementation. Include adverse skew and real gate loads.
4. Retain the extracted-capacitance-to-DNL/INL analysis idea for the layout stage.
   Before layout, equivalent charge-domain sweeps can examine assumed mismatch
   and parasitic scenarios. These do not replace full transistor settling/noise
   tests or establish bounds on undisclosed mismatch.

### Why it is not a drop-in solution

The documented 20MHz clock gives1.25MS/s at16cycles/conversion, below our radio
converter throughput objective. Twelve output bits do not demonstrate12ENOB.
TinyTapeout feedback reports operation but also noise, distorted output and
missing codes under some tests. The core README's11.8ENOB is explicitly without
noise; its verification table includes unresolved RC-extracted and corner cases.
Its older submission-status checklist is not current silicon status.

VREF, VREF_GND and VCM are external inputs: this design does not demonstrate an
integrated reference driver solving our current reference problem. Its tiny
metal capacitor geometry and1.8V Sky130 device choices require new GF180 design
and verification. The preamplifier uses several threshold/device variants;
renaming models or scaling dimensions is insufficient. The schematic netlist has
an empty CDAC subcircuit and local include paths: extracted capacitor content and
hierarchical dependencies must be resolved before attempting reproduction.

A particularly useful failure lesson in the core README is the sampling/MSB
node excursion approximately2*VCM-VIN: below-ground excursions can lose stored
charge. Audit absolute switch-terminal voltages across the whole sequence, not
only comparator differential voltage. This is directly relevant to our uncertain
common-mode and switching-load scenarios even with narrow supply/temperature.

Decision: retain as a concrete reference for a future controlled ADC switching
comparison and calibration work. Do not replace our ADC or infer a speed/power
benefit without matched GF180 experiments. Current implementation priorities are maintained in [risk priorities](risk-priorities.md).

## Silicon-unknowns research refresh — 2026-09-26

Architecture selection remains open. This pass searched specifically for measured
GF180/GF180MCU device, oscillator, converter, mixer and wafer.space characterization,
then inspected primary project and PDK pages. It does not establish absence of
unindexed/private results. No new measured GHz performance bound was recovered.

| Unknown that can change our architecture | Evidence needed | What this search resolves |
| --- | --- | --- |
| Loaded transistor speed at 2.4–5 GHz | De-embedded S-parameters, fT/fmax versus bias/geometry, or measured loaded RF blocks with current and voltage stated | Still open. DC current and simulated gm/C are not measured RF power gain. |
| Autonomous and buffer-added phase noise | Silicon phase-noise spectra, supply pushing, output loading and integration limits | Still open. A directly relevant new RF test-chip project exists, but does not provide measured noise or a functioning closed PLL. |
| Mixer/LNA noise and linearity | Measured conversion gain, NF, compression/IIP3 versus LO drive, bias and load | Still open. Located mixer work shows simulations and planned measurements, not a measured RF receiver. |
| Converter precision versus sample rate | Measured SNDR/SFDR versus input frequency/amplitude with reference, bias and power conditions | Existing sensor AFE remains useful but incomplete; newer SAR repository explicitly has no silicon. |
| Pad, protection, package and substrate coupling | Biased RF S-parameters, package model or measured aggressor/victim transfer | Still open. New GF180 I/O testing is a lead; digital functionality does not establish RF transparency or isolation. |
| Device variation, matching and low-frequency noise | Multi-die distributions, DC/CV/mismatch and noise data tied to geometry | Partially grounded by public PDK characterization; no new GHz statistical validation located. |

### Primary-source leads and exclusions

- [2026 RFIC characterization project](https://github.com/sscs-ose/sscs-chipathon-2026/issues/143):
  directly relevant LC-VCO and CML quadrature-divider work. Current scope is
  open-loop characterization; the authors explicitly explain why the feedback
  divider/PFD combination cannot demonstrate closed-loop lock. Treat it as a
  design/test opportunity, not a silicon-proven PLL.
- Its [layout review](https://github.com/Zachnad0/AUS-NZ-Track-A-RFIC-Workspace/blob/main/docs/layout-review-sep01.md)
  reports simulated GHz operation, but no oscillator phase-noise result. Inductor
  EM validation and full tank/varactor extraction remain incomplete. It also
  records extracted output-converter degradation and later corrections. This is
  useful independent evidence that clock conversion and parasitics deserve
  attention, not a quantitative measured GF180 limit. Do not adopt its simulated
  GHz values as a hardware guarantee.
- [ORConf 2026 primary program](https://fossi-foundation.org/orconf/2026) announces
  returned silicon and characterization in Tim Edwards' talk. The abstract mixes
  Sky130 Chipalooza analog work with GF180 3.3 V SRAM/I/O support. No numerical
  GF180 RF dataset or slides were recovered from the inspected program links.
  Follow the GF180-specific measurements, not the broad “all circuits functional”
  wording, before changing our analog assumptions.
- [ICELab wafer.space Run 2 listing](https://github.com/wafer-space/ws-run2)
  includes NFET/PFET characterization cells and transconductance amplifiers;
  [ASHES-GF180nm](https://github.com/GTIceLab/ASHES-GF180nm) is the source repository.
  The inspected landing page establishes design availability, not measurement
  results. This is a promising device-characterization lead, not a recovered dataset.
- [2025 Gilbert mixer project](https://www.landflier.com/projects/chip-design/gilbert-cell/)
  shows 100 MHz LO / 89.3 MHz RF simulation, including protection/loading work;
  the testing section describes future equipment use and unfilled measured
  metrics. It does not establish measured 2.4 GHz conversion gain or noise figure.
- [2AMLogic SAR ADC](https://github.com/2AMLogic/gf180-sar-adc) explicitly reports
  pre-tapeout status and no silicon. Its detailed “measured” characterization is
  simulation, including documented extraction limitations; do not count it as
  independent silicon validation of our converter assumptions.

### What the primary PDK actually supports

The [MOS extraction table](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_2_2.html)
separates measured extraction geometries from pseudo devices, including measured
3.3 V devices at 0.28 µm length. The
[noise page](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_2_3.html)
records median-die fitting from 10 Hz–100 kHz measurements, including 10/0.28 µm
3.3 V devices at specified biases. This grounds low-frequency device modeling;
it does not validate RF gate noise, oscillator upconversion or a phase-noise mask.

Search summaries can mislabel the documentation: a third-party result called
LV_6 an RF-NMOS/S-parameter section, whereas the
[actual LV_6 page](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_6.html)
is MOSCAP models. No RF characterization claim is accepted from that summary.

Decision: do not select external LO/divide-by-64 based on an assumed autonomous
silicon failure, and do not select autonomous operation based on simulated GHz
frequency alone. Highest-value evidence follow-ups are measured RFIC VCO/divider
results, GF180-specific wafer.space I/O data, and actual ICELab transistor data.
Until those yield numbers, retain bounded design scenarios and mark RF device
speed/noise and package coupling as unresolved. This research pass does not
restart the reference-AFE simulation campaign or change performance defaults.
