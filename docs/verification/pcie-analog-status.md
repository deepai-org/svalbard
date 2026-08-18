# PCIe Gen1 analog status

This is a living engineering inventory, not a compliance or tapeout claim.
“Physically closed” below means generated layout, zero Magic DRC errors, unique
Netgen LVS, and full-RC simulation against the block's declared public-model
contract. It does not include provider signoff, selected pads/package, or
measured silicon.

| Function | Current evidence | Next boundary |
|---|---|---|
| CML transmitter | Physically closed with calibrated PVT, robustness, noise, PRBS, and bounded statistical recovery | Pad/ESD/package/channel, emphasis integration, EM/IR/post-fill |
| Differential termination | Physically closed with calibrated PVT and large-signal linearity | Pad/package/channel co-simulation and calibration circuit |
| Receiver amplifier | Physically closed with bandwidth, threshold, transient, and noise matrices | Termination/pad/channel composition and offset-calibration implementation |
| Dual-edge CDR sampler | Physically closed with PVT, aperture, stress, and supply-injection evidence | Clock-tree loading, mismatch/metastability, integrated extraction |
| Alexander boundary | Physically closed with PVT and fixed-code stress | Retiming and loop-filter interface |
| Integrated Alexander front end | Representative schematic PVT closes 9/9 environments | Hierarchical layout/PEX, valid-window retimer, acquisition/tracking loop |
| Dual-interleave phase-error combiner | Physically closed; extracted 108/108 cases and 9/9 calibrated environments | Vote retiming, accumulator/integrator, PI control encoding, closed-loop dynamics |
| Phase interpolator | Physically closed with phase-code PVT and stress | Control DAC, clock-tree/sampler composition, jitter/supply coupling |
| CML-to-CMOS boundary | Physically closed with programmable-tail PVT and timing window | Denser composed timing/jitter matrix and clock distribution |
| 1:2 deserializer | Physically closed alone and with extracted CML-to-CMOS front end | Parallel RX connection and clock/reset distribution |
| PLL/VCO/divider | Not implemented | Architecture, tuning bands, startup/lock, jitter, layout, extraction |
| Serializer | Not implemented | Parallel-to-serial topology, clock phases, TX loading, layout, extraction |
| PCIe receiver detect/electrical idle | Not implemented | Pad-aware circuits, safe clamps, protocol-visible controls |
| Shared bias/reference/control DACs | Not implemented as an analog top | Bandgap/reference choice, bias distribution, calibration observables and retained codes |
| Analog top, pads, PDN, package/channel | Not implemented | Hierarchical integration, selected qualified I/O, EM/IR, coupling, post-fill and provider precheck |

At this checkpoint, most reusable signal-path leaf experiments exist and are
physically extracted, but the full interface is not close to tapeout-ready.
A reasonable planning estimate is roughly 60--70% of reusable leaf-circuit
development, 35--45% of a functioning integrated PCIe analog interface, and
less than 25% of tapeout/signoff evidence. These ranges deliberately count
PLL/autonomous-CDR closure, PCIe-specific detect/idle behavior, pads/package,
and analog-top verification as major work rather than treating them as wiring.

## Critical path

1. Add valid-window retiming and a realizable accumulator/integrator and
   phase-interpolator control encoding after the closed phase-error combiner;
   demonstrate reference-assisted tracking.
2. Build the PLL/VCO/divider with external-clock bypass and observable divided
   clock/lock outputs, then close startup, tuning range, jitter, and supply
   sensitivity through extraction.
3. Build and extract the serializer and compose it with the transmitter at
   2.5 GT/s, including emphasis and electrical-idle behavior.
4. Add receiver detect, electrical idle, shared bias/reference generation,
   control DACs, calibration state/observables, and safe reset clamps.
5. Assemble the analog top and re-run hierarchical/flattened DRC/LVS/PEX with
   clock, supply, substrate, thermal, and simultaneous-switching coupling.
6. Select pad/ESD/package/channel models and complete post-fill, EM/IR,
   reliability, provider-qualified variation, independent correlation, and
   immutable release-candidate evidence.
