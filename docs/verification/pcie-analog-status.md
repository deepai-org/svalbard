# PCIe Gen1 analog status

This is a living engineering inventory, not a compliance or tapeout claim.
“Physically closed” below means generated layout, zero Magic DRC errors, unique
Netgen LVS, and full-RC simulation against the block's declared public-model
contract. It does not include provider signoff, selected pads/package, or
measured silicon.

The current rate/delay evidence and remaining model-validity boundary are
tracked separately in [PCIe Gen1 analog speed checkpoint](pcie-analog-speed-budget.md).
The top-down component, assumption, power and sequencing audit is recorded in
[PCIe Gen1 architecture checkpoint](pcie-architecture-checkpoint.md).

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
| CML-to-CMOS boundary | Physically closed with programmable-tail PVT and timing window. The calibrated converter is zero-DRC, uniquely LVS-matched, 2,048R/1,340C full-RC extracted, and its exact physical/PEX identity is now checked in every 2.5-GT/s capture case. | Denser composed noise/mismatch matrix, extracted clock distribution, and parent-owned routing |
| 1:2 deserializer | The original shared-clock cell remains physically closed, but full-lane composition showed that opposite-edge sampler decisions do not share a safe conversion window. Its 190 by 122 um independently clocked replacement is zero-DRC, uniquely LVS-matched, and retapered to 1,957R/1,400C. With per-lane event-relative scoring and independent sense/write timing, the revised cell now passes the representative 2.5-GT/s five-environment combined-stress composition. | Statistical hold/metastability, extracted aggressors, routed-parent extraction, and post-fill extraction |
| PLL/VCO/divider | The dual-edge architecture requires a 1.25 GHz oscillator. A checked minimum-subset search selects the `fast` and `gain` split-control parents from three independently 0-DRC, unique-LVS, full-RC candidates. The physical dual 5-bit DAC uses a 2.0 V reference and passes 160/160 DC plus 5/5 settling cases. The selected two-DAC/two-VCO/high-gain-selector parent is zero-DRC, uniquely LVS-matched, and full-RC extracted with 3,872 resistors and 1,287 capacitors. Its exact PEX passes 4/7 nominal candidates, 10/35 PVT candidates covering 5/5 environments, break-before-make handoff, and 55/55 VDD/reference-ripple cases with 8.59 ps worst cycle displacement and 0.467% worst median-frequency pushing. A symmetric static-CML divide-by-two is zero-DRC, uniquely LVS-matched, extracts to 510R/193C, and passes 19/25 standalone post-layout bias cases. Direct VCO-to-divider composition exposed the need for a two-stage CML restorer. The final routed VCO-bank/restorer/divider parent is zero-DRC, uniquely LVS-matched, extracts to 4,766R/1,580C, and passes 43/50 exact-PEX calibration candidates covering 5/5 environments, with five consecutive passing divider-bias points in every environment, at least +0.585/-0.468 V restored rails, no more than 0.509% divide-ratio error, and no more than 3.151% VCO loading shift. The 2.5 GHz overspeed experiment remains failed falsification evidence | Implement the remaining reference ratio and realizable calibration controls, then close statistical startup/mismatch, phase noise, combined PDN/aggressor stress, and the PLL loop |
| Serializer/TX | The standalone 2:1 CML mux remains a zero-DRC, unique-LVS, 267R/85C test structure, but arbitrary changing words falsified its high-capacitance TX boundary. The original clock-steered parent remains preserved and passes both rates. A separately versioned 2.5-GT/s parent uses a minimum-length tail and eight realizable nonlinear load branches per side; it is zero-DRC, uniquely LVS-matched, 1,506R/945C full-RC extracted, and supplies at least 103.180 mV pin margin in the limiting combined-stress case. | Add realizable bias/control generation, package/pad/channel EM, mismatch, and simultaneous substrate/PDN aggression |
| Externally clocked lane spine | At 1.25 GBd, the exact TX/termination/RX/restorer/sampler/converter/capture stack passes 5/5 environments and 160/160 PRBS bits under simultaneous bounded channel, jitter, duty, and rail-ripple stress. At 2.5 GT/s, the ideal-wire leaf stack passes 5/5 representative environments over 24-bit PRBS7 with 6 ohm/leg plus 1 pF loading, 30 ps peak TX jitter, 47% duty cycle, and 20 mV peak 100 MHz rail ripple. The first physical hierarchy now places and routes the RX amplifier, calibrated restorer, and sampler as one zero-DRC, unique-LVS, 1,309R/464C parent. Its exact parent PEX also passes 5/5 under the same stress. Worst pin, raw-RX, restored, converter, and final margins are 103.002 mV, 51.209 mV, 217.828 mV, 1.15809 V, and 939.439 mV; maximum current is 58.830 mA. The original 1/5 replay and intermediate 2/2 fast-corner result remain immutable falsification/progress evidence. | Absorb termination-to-RX and sampler-to-converter routing into the next parent, then add statistical mismatch/noise, package/pad/channel EM, simultaneous substrate/PDN aggression, fill, EM/IR, and provider signoff models. |
| PCIe receiver detect/electrical idle | Not implemented | Pad-aware circuits, safe clamps, protocol-visible controls |
| Shared bias/reference/control DACs | Dual 5-bit DAC physically closed for PI control and separately qualified as a VCO main/regenerative bias primitive across five environments; top-level references and distribution are not implemented | Bandgap/reference choice, two-instance VCO-bank distribution, calibration observables and retained codes |
| Analog top, pads, PDN, package/channel | Not implemented | Hierarchical integration, selected qualified I/O, EM/IR, coupling, post-fill and provider precheck |

At this checkpoint, most reusable signal-path leaf experiments exist and are
physically extracted, but the full interface is not close to tapeout-ready.
A reasonable planning estimate is roughly 70--80% of reusable leaf-circuit
development, 40--50% of a functioning integrated PCIe analog interface, and
less than 20% of tapeout/signoff evidence. These ranges deliberately count
PLL/autonomous-CDR closure, PCIe-specific detect/idle behavior, pads/package,
serializer and end-to-end lane composition, power reconciliation, and
analog-top verification as major work rather than treating them as wiring.

## Critical path

1. Extend the closed RX/restorer/sampler hierarchy downward through termination
   and upward through CML/CMOS conversion so all bandwidth-sensitive receive
   routes belong to one physical parent. Reconcile complete-path power.
2. Add provider-qualified mismatch/noise and simultaneous extracted supply and
   substrate aggression to the routed 2.5-GT/s hierarchy.
3. Add valid-window retiming, a realizable accumulator/integrator, and a
   calibration controller for the closed phase-interpolator DAC; demonstrate
   reference-assisted tracking.
4. Freeze the external reference and power budget, then close the PLL ratio,
   PFD/charge-pump/filter loop, statistical startup/mismatch, phase noise,
   combined PDN/aggressor sensitivity, bypass and lock observability.
5. Add receiver detect, electrical idle, shared bias/reference generation,
   control DACs, calibration state/observables, and safe reset clamps.
6. Assemble the analog top and re-run hierarchical/flattened DRC/LVS/PEX with
   clock, supply, substrate, thermal, and simultaneous-switching coupling.
7. Select pad/ESD/package/channel models and complete post-fill, EM/IR,
   reliability, provider-qualified variation, independent correlation, and
   immutable release-candidate evidence.
