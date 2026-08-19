# PCIe Gen1 analog status

This is a living engineering inventory, not a compliance or tapeout claim.
“Physically closed” below means generated layout, zero Magic DRC errors, unique
Netgen LVS, and full-RC simulation against the block's declared public-model
contract. It does not include provider signoff, selected pads/package, or
measured silicon.

The current rate/delay evidence and remaining model-validity boundary are
tracked separately in [PCIe Gen1 analog speed checkpoint](pcie-analog-speed-budget.md).

| Function | Current evidence | Next boundary |
|---|---|---|
| CML transmitter | Physically closed with calibrated PVT, robustness, noise, PRBS, and bounded statistical recovery | Pad/ESD/package/channel, emphasis integration, EM/IR/post-fill |
| Differential termination | Physically closed with calibrated PVT and large-signal linearity | Pad/package/channel co-simulation and calibration circuit |
| Receiver amplifier | Physically closed with bandwidth, threshold, transient, and noise matrices | Termination/pad/channel composition and offset-calibration implementation |
| Dual-edge CDR sampler | Physically closed with PVT, aperture, stress, and supply-injection evidence | Clock-tree loading, mismatch/metastability, integrated extraction |
| Alexander boundary | Physically closed with PVT and fixed-code stress | Retiming and loop-filter interface |
| Integrated Alexander front end | Schematic 9/9; calibrated composition of extracted sampler/detector/combiner replays 36/36 across 9/9 environments | Hierarchical interconnect, valid-window retimer, acquisition/tracking loop |
| Dual-interleave phase-error combiner | Physically closed; standalone extracted 108/108 and composed extracted replay 36/36 | Vote retiming, accumulator/integrator, PI control encoding, closed-loop dynamics |
| Programmable CDR error slicer | Matching-hardened physical layout; schematic and full-RC 972/972, 9/9 calibrated with interior codes, 62.33 ps worst selected delay | Deck-driven density/fill and bias-noise study; CML-to-CMOS retiming, accumulator, composed closed-loop dynamics |
| Phase interpolator + dual 5-bit control DAC | Both physically closed; composed full-RC 2,367/2,367 and 9/9 calibrated to 31 codes with 2.80 ps worst error | Calibration controller/storage, glitch-safe updates, clock-tree/sampler composition, jitter/supply coupling |
| CML-to-CMOS boundary | Physically closed with programmable-tail PVT and timing window | Denser composed timing/jitter matrix and clock distribution |
| 1:2 deserializer | Physically closed alone and with extracted CML-to-CMOS front end | Parallel RX connection and clock/reset distribution |
| PLL/VCO/divider | The dual-edge architecture requires a 1.25 GHz oscillator. A checked minimum-subset search selects the `fast` and `gain` split-control parents from three independently 0-DRC, unique-LVS, full-RC candidates. The selected 293/400-case no-IC/no-uic union has two unique PEX identities and continuous target plus +/-2% design-band coverage in 5/5 environments; no single candidate exceeds 3/5. The limiting upper endpoints are 1.2859 GHz for slow/fast-resistor and 1.2833 GHz for slow/slow-resistor. Seven fixed-control parents and the ten-parent 610/880 aggregate remain corroborating evidence, not selected hardware. A separate twelve-parent 2.5 GHz overspeed experiment is physically clean but covers only 2/5 and is retained as falsification evidence. The existing two-input selector is the selected next boundary; the balanced sixteen-leaf tree remains physically closed but unnecessary for this bank | Realize the two VCO bias controls and calibration mapping, compose both parents with power gating and the two-input selector, then close statistical startup/mismatch, phase noise/supply sensitivity, divider and closed PLL |
| Serializer | Not implemented | Parallel-to-serial topology, clock phases, TX loading, layout, extraction |
| PCIe receiver detect/electrical idle | Not implemented | Pad-aware circuits, safe clamps, protocol-visible controls |
| Shared bias/reference/control DACs | PI control DAC physically closed; remaining biases/references not implemented as an analog top | Bandgap/reference choice, bias distribution, calibration observables and retained codes |
| Analog top, pads, PDN, package/channel | Not implemented | Hierarchical integration, selected qualified I/O, EM/IR, coupling, post-fill and provider precheck |

At this checkpoint, most reusable signal-path leaf experiments exist and are
physically extracted, but the full interface is not close to tapeout-ready.
A reasonable planning estimate is roughly 60--70% of reusable leaf-circuit
development, 35--45% of a functioning integrated PCIe analog interface, and
less than 25% of tapeout/signoff evidence. These ranges deliberately count
PLL/autonomous-CDR closure, PCIe-specific detect/idle behavior, pads/package,
and analog-top verification as major work rather than treating them as wiring.

## Critical path

1. Add valid-window retiming, a realizable accumulator/integrator, and a
   calibration controller for the closed phase-interpolator DAC; demonstrate
   reference-assisted tracking.
2. Realize both half-rate VCO bias controls and their calibration mapping;
   compose the qualified parents and startup/power controls with the closed
   two-input selector, then build the divider
   and PLL with external-clock bypass and observable divided clock/lock outputs;
   close statistical startup, tuning, jitter, and supply sensitivity.
3. Build and extract the serializer and compose it with the transmitter at
   2.5 GT/s, including emphasis and electrical-idle behavior.
4. Add receiver detect, electrical idle, shared bias/reference generation,
   control DACs, calibration state/observables, and safe reset clamps.
5. Assemble the analog top and re-run hierarchical/flattened DRC/LVS/PEX with
   clock, supply, substrate, thermal, and simultaneous-switching coupling.
6. Select pad/ESD/package/channel models and complete post-fill, EM/IR,
   reliability, provider-qualified variation, independent correlation, and
   immutable release-candidate evidence.
