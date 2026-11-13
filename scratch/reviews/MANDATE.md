# Performance mandate (user, 2026-11-09)

Every performance gap in performance-review.md is to be FIXED on the primary on-chip route.
Fallbacks are backups, not the plan.

Accept a miss only if it is a physical impossibility in GF180MCU. To claim that, you must provide a
quantitative proof, for example device fT/fmax versus the required bandwidth, minimum pad/ESD capacitance
versus return loss, or the thermal/current-density limit. Write it in physical-limits.md in this
directory. "Hard", "risky" or "out of time" do not qualify.

Architectural fixes are in scope:
- wider or faster host link using spare pads
- extra pipelining
- different circuit topologies
- inductive peaking
- T-coils
- CML instead of CMOS
- interleaving

Record any change that crosses an ownership boundary in interface-changes.md.

## Operating envelope (applies to every performance check)
Functional and performance checks use only the narrow window from spec/tapeout-plan.md "Operating envelope":
- junction temperature 27 °C ±5 °C (22–32 °C)
- die supply 3.15–3.35 V

Process corners (ss/ff/sf/fs) still apply, but only at those temperatures and voltages. Do NOT require performance at 0 °C, 85 °C or 125 °C, or at wide supply.
Only SAFETY checks stay wide: 0–3.63 V supply ramps, 0–85 °C, and no damage, latch-up or lock-up.
Use the narrow window when sizing for performance, for example bias, gain margin, timing corners, and the libraries used in STA.

## Device-speed guidance (scratch/reviews/gf180-device-speed-evidence.md)
- nfet_03v3 fT is about 16 GHz at ss/32 °C (12–20); about 11–13 GHz usable in a laid-out circuit. pfet is about 5.5 GHz. 5 V/6 V devices are about 6–9 GHz.
- Models omit gate resistance (rgatemod=0). Add an explicit Rg (about 60–150 Ω per 10 µm device) in RF and high-speed sims.
- Derate pre-layout timing by 1.45×, or sign off post-extraction only.
- Use quarter-rate samplers (810 MHz is feasible but needs extracted sign-off; a 1.25 GHz half-rate sampler is marginal, so avoid it).
- The final 2:1 serializer stage is CML. CML tails at 50–80 µA/µm; keep pfets out of paths faster than about 2 GHz.
- High-speed pin ESD at about 1 pF where possible; use shunt peaking where bandwidth is tight.
- LNA: two stages for ≥20 dB. PDK noise models are suspect. PA realistic at +5–8 dBm (3.3 V) or about +10 dBm (6 V cascode).

## Off-chip passives allowed (user, 2026-11-10)
Any number of off-chip passives is allowed wherever it makes the chip's job easier or lowers risk. That includes:
- crystals / crystal oscillators, e.g. a clean PLL/CDR/LO reference or an aosc trim reference
- inductors and LC tanks: external VCO tank, LNA/PA matching, peaking
- baluns and transformers; matching networks
- AC-coupling capacitors, termination resistors, filters
- bias/reference resistors and precision references, e.g. for an external bias override
- decoupling and bulk capacitance

Constraints:
- every off-chip part costs pins: pads are limited and the 19 spare sites are booked for debug
- bond-wire and package parasitics (~1 nH/mm, pad C) must be modelled at RF and multi-Gb/s
- prefer passives that relax on-chip specs or remove risky circuits
Each use goes into spec/board-requirements.md with part class, value and tolerance, and the pin and parasitic model must be included in the sims that rely on it.

## Top-level performance gate (user, 2026-11-10)
Top-level layout must be designed for performance, not just connectivity. Apply these floorplan rules BEFORE routing:
1. Fast nets short, direct and length-matched: pad→CTLE/slicer, serializer→driver, LO→mixers, PLL phases→samplers.
2. Symmetry: mirrored I/Q (mixers, filters, ADC/DAC), matched LO and differential routes, matched PLL phase loading.
3. Isolation: digital macro and PA/VCO aggressors away from the LNA, VCO tanks, bandgap/bias and ADC inputs. Use guard rings, deep-well isolation where available, separate analog/digital supply and ground returns, and shielded LO routes.
4. Supply/ground: an extracted grid within the 117 mV supply-drop budget, with the decap pool placed near the noisy and switching loads.
5. Each block next to its pads (RF on its pad edge, wired RX/TX at their pads, digital host link at the gearbox regions).
6. Digital macro pins face their consumers. D2H/H2D go through the pad-edge gearboxes.
Gate before signoff:
- extract critical top-level nets (LO, wired data/clocks, ADC inputs, ref/bias) and resimulate each chain with that routing
- simulate substrate/supply coupling (digital, PA, ring VCOs → LNA, VCO, ADC, bandgap)
- extract the PDN IR drop and decap response

## Mitigation tricks are demand-driven (user, 2026-11-10)
Every layout/isolation trick is on the table: guard rings, substrate taps, deep n-well/triple well, shielded and coplanar routes, patterned ground shields under inductors, separate supply/ground domains and pads, spacing, differential signalling, decap placement, dummy/matching structures, slew control.

Use each one only where an analysis shows a need: a quantified aggressor→victim coupling, margin, or risk. Not "for fun". Each mitigation cites the risk-register entry and the analysis that demanded it.

The risk register (projects/programmable_transceiver_platform/spec/risk-register.md) aims to enumerate as many possibilities and risks as can be thought of, each analyzed (quantified where possible).

## Packaging / board interface (user, 2026-11-10)
The die is wire-bonded onto the wafer.space "70-pin mezzanine COB" board (GF180MCU Run 1, version TT01):
- a 16 × 14 mm PCB
- a 74-pin pad ring on the die, bonded to a fixed finger ring around a die-attach paddle (with vias)
- fixed traces fanning out to ONE 70-pin board-to-board mezzanine connector
- only two small strips "allocated for passives" (top/bottom edges)
Image: scratch/reviews/wafer-space-cob.png.

Consequences:
- bond wires and finger-to-connector traces (several mm) plus the mezzanine connector are FIXED and in series with every pin
- only 70 of 74 pads can reach the connector
- off-chip passives either fit in the small passive strips (fixed trace positions) or sit on the user's carrier board beyond the connector
- every RF / multi-Gb/s / LO / clock path must be qualified through this whole channel
Clarification (user): the package mostly changes performance; it rarely makes things impossible. Do NOT write off off-chip passives. Design the chip to TOLERATE passives at varying distances from the die (in the COB passive strip, or on a carrier board a few cm away):
- programmable on-chip termination, matching and trim to absorb unknown trace and connector parasitics
- wide-range CTLE/de-emphasis
- LO input tolerant of amplitude and phase spread
- on-chip fallbacks (on-chip AC coupling, balun or termination options) when the user has no passive close by
Qualify across a range of passive distances rather than one assumed placement.

## Concentrate risk where it counts (user, 2026-11-10)
Use the silicon-proven gf180mcu_fd_sc (5 V-device) standard cells wherever possible. The online 3.3 V library is NOT silicon-proven, so don't adopt it wholesale. Close digital timing with architecture first (AC-1, pipelining, retiming).

Use non-proven or custom fast cells only where a specific path truly cannot close otherwise. Keep that usage small, contained and observable, and give it a fallback (e.g. the reduced-rate mode). In general, don't spend novelty or risk on anything that isn't the point of the chip.
Refinement (user): spend risk only where something ambitious is happening AND there is no low-risk alternative. Everywhere else, choose the conventional, proven or simplest option, even if it costs some area, power or elegance. When proposing anything novel, state the low-risk alternative and why it's insufficient.

## Shared digital datapath (user, 2026-11-10)
The digital capabilities should be highly shared between wired and radio. That means one transport and framing path, one set of FIFOs/gearboxes, pattern generator/checker, capture/playback memories, frequency counters, threshold/gain fast-command path, timestamping/latency and calibration sequencer, each serving whichever mode is active. Mode-specific logic is allowed only where the function truly differs, e.g. the 8b/10b codec vs the IQ interpolator. This reduces flip-flops and area and keeps both modes tested by the same logic.

## One risk register (coordinator, 2026-11-11)
All new risks go into projects/programmable_transceiver_platform/spec/risk-register.md, as a row in its table (ID, risk, block, status, mitigation/owner, evidence pointer), and nowhere else. Status changes are made in place there. READMEs, reviews and interface-changes.md may cite a risk ID but must not keep their own risk lists. scratch/reviews/risk-register.md/.json are superseded pointers.

## Two risk buckets (user 2026-11-11)
1. **Ground-truth data is guessed or wrong** (models, passives, package, board, specs). Make the data as accurate as possible, using the best evidence available. Design against deliberately pessimistic ranges so the design is conservative wherever that's possible. Every ground-truth number we rely on goes in `projects/programmable_transceiver_platform/spec/design-assumptions.md`, with its value, source, confidence and the pessimistic design value. Blocks must pass at the pessimistic value.
2. **We designed badly.** Check everything carefully before calling it done: extracted results at every in-window corner and at the pessimistic data values, checks that can actually fail, no limits relaxed after seeing the result, and an independent review (a different agent) before a block is marked done.

## Electromigration sign-off temperature (coordinator 2026-11-11)
EM and IR sign-off is done at 85 °C junction, the top of the wide safety window. Performance still targets 22–32 °C.

## Uncertain values are bounded in both directions (user 2026-11-11)
Any PDK or ground-truth value that isn't known exactly gets a pessimistic LOW and a pessimistic HIGH bound. Blocks must pass at whichever end hurts them, and check both ends where it isn't obvious. Examples:
- more capacitance slows a path, but less can break hold, oscillator range or stability;
- higher fT helps speed but can cause ringing or overshoot and races.
"Pessimistic" means worst for the specific check, not a fixed direction.

## Prove the bench small before running it big (user 2026-11-11)
Before any long or large simulation, validate the bench and method on a small, simple circuit whose answer is known analytically. Examples:
- an ideal-VCO + ideal-divider PLL with a textbook lock time and phase margin;
- an RC/LC tank with a known frequency and Q;
- a single inverter-chain delay;
- a resistor's noise;
- a simple amplifier with a hand-calculated NF.
The bench must reproduce the known answer, and must FAIL a deliberately broken case (dead oscillator, wrong ratio, missing load). Then build up in steps: swap in one real or extracted block at a time, with a short run each time. Run the full extracted case only after every step agrees.

## RF input matching (user 2026-11-12)
Board trimmer capacitors (tuned once at build) and/or on-chip trims are acceptable for absorbing board-part and bond tolerances. Prefer board trimmers over on-chip trims that cost NF.

## ESD tiering (user-approved 2026-11-12; see scratch/reviews/esd-tiering.md)
- 2 kV HBM: supplies, host-link LVCMOS, debug/ATB, RF_RX. 1 kV HBM: RF_TX, WIRE_TX, and clocks/REF/AUX optionally. HS RX pair and USB stay at 2 kV with the diode row restored, for CDM (PD48c, coordinator 2026-11-12). CDM ≥250 V chip-wide. Nothing below 500 V HBM.
- Remove only the extra diode rows; keep the main diodes and the local secondary clamps.
- Board TVS on the antenna and USB connectors is mandatory, along with ESD handling rules in the board/bring-up docs.
- Replace the 3.63 V DC limit for ~150 ns ESD events with a transient oxide limit derived from PDK data (document the derivation, and use the pessimistic value).
- Restore a small TLP/ESD test site (area-tight; keep it minimal).

## Fallbacks recover partial success (user 2026-11-13)
On-chip implementations are the design. Off-chip fallbacks (e.g. an external board LNA in a do-not-populate footprint) exist only to recover a partially working die on the bench. The chip must keep the hooks for them (bypass paths, observation pins), but they are not the plan.

## User direction 2026-11-13 (big-picture risks)
- Scope and AI-driven design are intentional. Counter AI blind spots with many varied checks and cross-references against public data.
- Models: every uncertain value has a range. Designs must work across the WHOLE range and be optimized for best performance at the most-likely value (not just pass at the corners).
- No dead chip: the top priority is that die 1 powers up safely, talks to the FPGA, and is observable/debuggable even if ambitious blocks fail. Shared infrastructure (supplies, bias, reference, pads, digital, host link, debug) gets the most conservative design, isolation and bypasses.
- Consolidate early and often: frequent consistency passes over interface rows, risks, the inventory and the published views.
- Tapeout readiness: the user is the gauge. Keep checking.
- Integration: chip-level verification is a first-class workstream (see the integration plan).
