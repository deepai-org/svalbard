# PCIe Gen1 analog speed checkpoint

The Gen1 line rate is 2.5 GT/s: one UI is 400 ps and the NRZ Nyquist frequency
is 1.25 GHz. This checkpoint records circuit-level public-model evidence; it is
not an end-to-end timing or model-validity claim.

| Path | Full-RC evidence | Present interpretation |
|---|---|---|
| TX core | 17.0--26.8 ps crossing at 2.5 GT/s; nominal stress through 3.125 GT/s; 6.03 GHz nominal bandwidth | Core switching is not the present limiter; pads/package/channel remain absent |
| RX amplifier | 108.53 ps worst crossing; 2.138--3.355 GHz selected high-mode bandwidth | Leaves about 91 ps from worst core crossing to a nominal 200 ps eye center before pad/channel/jitter allocation |
| Dual-edge sampler | 2.5 GT/s decisions; common qualified transition displacement includes -80 to +80 ps | Demonstrates a useful aperture, not metastability-tail probability |
| Phase interpolator | 1.25 GHz target; extracted stress through 1.5 GHz; at most 7.50 ps calibrated phase error | Provides phase trim, subject to clock-tree and supply-jitter composition |
| CDR error slicer | 61.96 ps worst selected full-RC assertion delay; 972/972 extracted cases complete and 9/9 environments calibrate with interior codes | Leaves substantial margin to its 300 ps local target; retiming and closed-loop dynamics remain absent |
| TX-to-parallel receive boundary | Extracted CML-to-CMOS and deserializer composition closes its 18 representative cases | Does not yet include RX amplifier, channel, recovered clock, or protocol timing |
| Autonomous clock source | PLL/VCO/divider not implemented | Principal unclosed transistor-speed and jitter risk |

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
The 61.96 ps worst selected delay is 15.5% of one 400 ps UI; this does not yet
include the following retimer, accumulator, PI-control DAC, or clock tree.

Before analog-top freeze, add the selected pad/ESD/package/channel, extracted
clock tree, serializer and PLL/VCO/divider; then close eye/BER, acquisition,
jitter, supply injection and simultaneous TX/RX activity. Provider confirmation
of the model's high-frequency validity remains separate from a SPICE pass.
