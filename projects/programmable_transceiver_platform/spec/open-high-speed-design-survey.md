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
   architecture to our intended difficulty class. Check analog bandwidth and
   autonomous recovered-clock assumptions against actual files.
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

Current loaded LO candidate simulation is independent of this survey and must
continue unchanged. No layout is authorized by this reference collection.

Follow-up circuit inspection: [OpenSERDES review](openserdes-circuit-review.md)
finds its uploaded CDR PDF has a50kHz example and blank maximum-frequency field.
Do not attribute the paper's2Gb/s link result to a qualified autonomous CDR in
that repository. Its feedback element is a nonlinear two-PMOS chain, not a linear
resistor; model mapping is required before ngspice reproduction.
