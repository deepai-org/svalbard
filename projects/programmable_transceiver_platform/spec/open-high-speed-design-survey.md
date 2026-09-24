# Open high-speed analog design survey

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
