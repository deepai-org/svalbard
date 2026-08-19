# PCIe Gen1 analog speed checkpoint

The Gen1 line rate is 2.5 GT/s: one UI is 400 ps and the NRZ Nyquist frequency
is 1.25 GHz. This checkpoint records circuit-level public-model evidence; it is
not an end-to-end timing or model-validity claim.

| Path | Full-RC evidence | Present interpretation |
|---|---|---|
| TX core | 17.0--26.8 ps crossing at 2.5 GT/s; nominal stress through 3.125 GT/s; 6.03 GHz nominal bandwidth | Core switching is not the present limiter; pads/package/channel remain absent |
| RX amplifier | 108.53 ps worst crossing; 2.138--3.355 GHz selected high-mode bandwidth | Leaves about 91 ps from worst core crossing to a nominal 200 ps eye center before pad/channel/jitter allocation |
| Dual-edge sampler | 2.5 GT/s decisions; common qualified transition displacement includes -80 to +80 ps | Demonstrates a useful aperture, not metastability-tail probability |
| Phase interpolator + control DAC | 1.25 GHz PI; composed full-RC 2,367/2,367, 9/9 environments, 199.65--217.35 ps span, 2.80 ps worst calibrated error | DAC 1.21 ns worst carry settling is a slow-loop update bound; clock-tree and supply-jitter composition remain |
| CDR error slicer | Matching-hardened 62.33 ps worst selected full-RC assertion delay; 972/972 extracted cases complete and 9/9 environments calibrate with interior codes | 0.6% slower than the sparse predecessor and still far below its 300 ps local target; retiming and closed-loop dynamics remain absent |
| TX-to-parallel receive boundary | Extracted CML-to-CMOS and deserializer composition closes its 18 representative cases | Does not yet include RX amplifier, channel, recovered clock, or protocol timing |
| Autonomous clock source | Seven physical tile geometries; all six variants are DRC-clean/LVS-unique/full-RC. The bank covers 5/5 extracted environments: SS/fast-resistor spans 2.458--2.508 GHz and SS/slow-resistor 2.489--2.506 GHz at 2.97 V/125 C | SS/slow-resistor has only 3/6 electrical controls and no 2% guardband. Safe selection, unseeded startup, phase noise, supply pushing, divider and PLL remain unclosed |

The immediate speed gate is extracted composition, not a generic transistor
frequency estimate. Schematic-calibrated sampler/detector phase settings failed
four of nine environments after all three CDR cells were extracted together;
edge-phase recalibration alone closes six. Targeted sampler-bias plus phase
recalibration recovers the other three, and a separate selected-code replay
passes all 36 environment/offset cases with 151.8 mV minimum signed error. The
flow retains a failure if no legal settings cover every declared offset.

The next CDR boundary now has direct extracted speed evidence as well. Its
programmable window slicer rejects 40 mV-or-smaller errors, asserts uniquely at
150 mV and above, and selects only codes interior to both searched bias ranges.
The matching-hardened 62.33 ps worst selected delay is 15.6% of one 400 ps UI; this does not yet
include the following retimer, accumulator, or clock tree.  The PI-control DAC
is now extracted and composed with the PI: 31 retained phase codes calibrate in
all nine mixed environments with 2.80 ps worst placement error.  Its 1.21 ns
worst full-carry settling time constrains code-update cadence, not the 400 ps UI
signal path.

Before analog-top freeze, add the selected pad/ESD/package/channel, extracted
clock tree, serializer and PLL/VCO/divider; then close eye/BER, acquisition,
jitter, supply injection and simultaneous TX/RX activity. Provider confirmation
of the model's high-frequency validity remains separate from a SPICE pass.
