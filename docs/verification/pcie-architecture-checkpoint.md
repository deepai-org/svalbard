# PCIe Gen1 architecture checkpoint

This checkpoint asks whether the work is converging on a useful first-silicon
PCIe endpoint, rather than merely accumulating passing analog leaf cells.  The
answer is mixed.  The half-rate experiments support a plausible GF180 signal
path, but the endpoint contract, I/O environment, power budget, clock plan and
calibration system are not frozen.  Until those are resolved, the repository
contains experimental SerDes components, not a composable PCIe macro.

The [analog-top integration floorplan proposal](../images/pcie-analog-floorplan-proposal.svg)
shows the current placement intent and, just as importantly, the missing shared
infrastructure. It is a planning render rather than a placed/routed cell:
dimensions other than the annotated pulse-generator checkpoint are schematic,
and it carries no top-level DRC, LVS, PEX, EM/IR, substrate, or package claim.

## Architecture decision

Continue toward the full Gen1 x1 endpoint, but make it a ladder instead of an
all-or-nothing result:

1. **Minimum useful silicon:** independently enabled TX and RX, raw parallel
   symbols, direct clock injection, PRBS generation/checking and direct analog
   observability.  This path must work without the PLL, CDR, protocol engine or
   automatic calibration.
2. **Primary analog milestone:** an extracted, externally clocked 2.5 GT/s lane
   over one declared pad/package/channel envelope, with measured eye and power
   margin.  The current evidence screen declares 300 fF TX pad capacitance,
   100 nF AC coupling, 2 ohm and 1 nH per package leg, 500 fF RX pad
   capacitance, 2 kohm RX bias returns, and 6 ohm/leg plus 1 pF channel stress.
   It is deliberately *not* a qualified pad/ESD, bond, package, board, or
   connector model.  Reference-assisted sampling is the preferred first
   recovery mode.
3. **Autonomous-PHY milestone:** a closed PLL and CDR acquire and track that
   same lane, with bypass, lock metrics and bounded calibration searches.
4. **Endpoint milestone:** the digital endpoint trains, enumerates and transfers
   through the proven PHY boundary.
5. **Qualification milestone:** only qualified models, provider review,
   appropriate standards evidence and measured silicon can support compliance,
   interoperability, yield, ESD or lifetime claims.

This is not a retreat from the endpoint.  It prevents one high-risk subsystem
from hiding the behavior of all the others and gives first silicon several
independently useful outcomes.

## Selected signal-path spine

```text
parallel TX data
      |
half-rate registers -> integrated clock-steered mux/driver -> pad/assembly -> channel
                                                                       |
parallel RX data <- CMOS retiming <- one CML/CMOS boundary <- sampler <- RX amp/termination
                                      ^                    ^
                                      |                    |
                                digital loop filter <- phase votes
                                                           ^
direct 1.25 GHz clock ------------------------------+------+
common reference -> PLL/VCO -> phase interpolator --+
```

The important boundaries are deliberate:

- Integrate the 2:1 selection into the TX current-steering output stage.  The
  changing-word experiment showed that a standalone CML serializer driving a
  large TX gate bank creates a slow, bias-sensitive internal node.  Eliminating
  that boundary is both faster and simpler.
- Keep analog gain and regeneration only where sensitivity and 400 ps UI timing
  require them.  Convert CML decisions to CMOS once, then perform retiming,
  vote accumulation, calibration search and protocol work digitally.
- Prefer a bang-bang phase detector plus a digital loop filter/accumulator for
  the production CDR spine.  The extracted analog combiner and error slicer are
  useful fallback experiments, but making both mandatory adds static current,
  offsets, bias rails and circular calibration dependencies.
- Preserve direct differential clock injection and reference-assisted sampling
  as first-class modes.  Autonomous clocking must sit behind a bypass, not in
  front of every diagnostic.

## Component audit

| Component | Decision | Reason and required next proof |
|---|---|---|
| Programmable TX load/driver | Keep, integrated with serializer | Extracted core speed is strong.  The real pad/ESD/package load, overshoot, current density and common-mode contract remain existential. |
| Standalone 2:1 CML serializer | Keep as a test structure; do not use as the primary TX boundary | Static data passed, but arbitrary changing words exposed recovery and fanout failures.  The integrated clock-steered TX is the selected topology if its exact PEX closes. |
| Programmable termination and RX amplifier | Keep | They provide useful range across public-model corners.  They must be recomposed with AC coupling, pad/ESD, package/channel, offset and a measurable calibration condition. |
| Dual-edge sampler | Keep | A 1.25 GHz dual-edge architecture is better supported than the failed 2.5 GHz oscillator path.  Still needs the real clock tree, RX producer, mismatch/metastability bounds and simultaneous TX stress. |
| CML-to-CMOS boundary | Keep one instance per required decision lane, followed by an explicit valid-window boundary | The externally clocked routed parent through dual CMOS capture passes 5/5 combined-stress environments. The PI-clocked low-loading replacement parent is physically closed but passes 4/5: SS/hot produces correct even and odd decisions at different integer data ages. The architecture must retime or reschedule this boundary rather than allow lane-specific score alignment. |
| Analog phase combiner and programmable error slicer | Retain as optional/risk-macro evidence | They are physically credible but are not yet shown to improve link robustness enough to justify their power, offset and calibration cost over digital vote accumulation. |
| Phase interpolator and control DAC | Keep | The extracted phase range and placement are useful.  Add glitch-safe updates, a realizable search controller, clock-tree loading and supply-jitter composition. |
| 1.25 GHz VCO bank/restorer/first divider | Keep as a clock-source candidate, not a PLL | Its routed path spans the tested environments but consumes substantial power and still lacks a frozen reference ratio, phase detector, loop filter, phase-noise proof and closed-loop acquisition. |
| PLL feedback chain | Redesign after reference freeze | Do not extend the existing divide-by-two by habit.  For a 100 MHz reference and 1.25 GHz VCO, a rational integer comparison such as VCO `/25` versus reference `/2` is a candidate; the lawful clock contract and achievable prescaler implementation must select the real plan. |
| Shared references, bias DACs and distribution | Missing system | Per-leaf voltage sources are not an implementation.  Select reference accuracy/noise/startup, distribution impedance, power sequencing, manual override and retained safe codes. |
| Receiver detect and electrical idle | Missing PCIe-specific analog | These require the selected pad and coupling network and protocol-visible controls; they cannot be inferred from the generic TX/RX cells. |
| Pads, ESD, package, board and channel | Missing existential boundary | No core-only waveform closes a PCIe lane.  If no qualified low-capacitance I/O option supports the link budget, the present design cannot honestly become a PCIe interface on this process. |
| Analog top, PDN, substrate isolation and thermal plan | Missing system | Close common supplies, return paths, simultaneous TX/RX/clock aggression, EM/IR, fill and post-fill extraction before calling any collection of leaves an interface. |
| PCS/LTSSM/endpoint RTL and firmware | Missing endpoint | Analog PRBS success is not enumeration.  Digital implementation and the checked behavioral PHY twin must advance in parallel with physical lane integration. |

## Assumption audit

| Assumption | Evidence | Disposition |
|---|---|---|
| GF180 can switch fast enough for a constrained 2.5 GT/s lane | Extracted TX and the externally clocked routed receive parent pass the bounded 2.5 GT/s core matrix; the PI-clocked parent currently passes 4/5 and a 2.5 GHz VCO architecture failed. | Plausible for the constrained core, not proven for autonomous timing or at the pins. Retain 1.25 GHz dual-edge operation, add the required retiming boundary, and require selected pad/ESD/package/channel and recovered-clock composition. |
| The public transistor and RC models are accurate at the required frequency and geometry | They are the only current simulation basis; provider validity, correlations and production distributions are absent. | Use bounded sweeps and silicon monitors, but do not convert model coverage into a yield or compliance claim. |
| A 3.3 V static-CML implementation is the right power/speed choice | It works locally, but the routed clock path alone reaches about 78.6 mW at its worst recorded supply/reference point, before TX, RX and CDR. | Unproven.  Freeze available device/supply and pad families, then compare the smallest viable high-speed core domain.  Reduce always-on CML before sizing the PDN. |
| More programmable controls always improve first-silicon odds | Many leaves have interior passing codes, but top-level references, observables, search logic, storage and safe reset images are absent. | False as stated.  Retain a trim only when it has an observable, bounded monotonic or tabulated search, legal-code guard bands, manual override and a safe failure state. |
| Huge worst-case margins can replace missing fabrication data | Guardbands help local bounded uncertainty, but simultaneous unrelated extrema can produce an oversized, high-capacitance, high-power circuit and still miss unmodeled pad or coupling failures. | Allocate explicit system margins.  Use topology diversity and observability for existential unknowns; use sizing margin only where a physical bound is defensible. |
| Passing leaf PEX implies a sound composition | The serializer/TX changing-word failure and VCO/divider loading failure both contradicted this. | False.  A leaf is provisional until an extracted parent includes its real producer, consumer, clocks, supply and load. |

## Decisions required before architecture freeze

These are engineering inputs, not values that should be guessed in a
testbench:

1. Lawfully sourced PCIe revision, exact electrical limits and required claim.
2. External common-reference frequency, amplitude, jitter, injection pad and
   whether direct 1.25 GHz diagnostic clocking is permitted.
3. GF180 process option, permitted device/supply families and provider-stated
   high-frequency/model-validity envelope.
4. Qualified or explicitly experimental pad/ESD cells, package/bond plan,
   board connector, AC-coupling placement and bounded channel family.
5. Active/idle power budget by supply, thermal envelope and available power and
   ground bonds.
6. Concrete eye, jitter, sensitivity, acquisition, BER-estimator and calibration
   pass/fail thresholds derived from the frozen contract.
7. Named safe reset state, manual-control map, calibration observables and code
   retention behavior.

If the pad/package/channel or power gate fails, the response is to change the
architecture or the first-silicon claim—not to run more unloaded core SPICE.

## Corrected implementation order

1. Finish exact-PEX changing-word closure of the integrated half-rate TX and
   record its current and aperture envelope.
2. Select a provisional but explicit I/O capacitance/inductance/channel envelope
   and build one externally clocked TX-to-RX lane.  Include termination, RX,
   sampler, one CML/CMOS boundary and CMOS capture/PRBS checking.
3. Measure composed timing, eye and power across one shared PVT matrix, including
   simultaneous TX clock/RX supply and substrate aggression.  Remove redundant
   restoration and static CML before expanding the autonomous loops.
4. Freeze the real pad/ESD, package, reference and power contracts.  Re-size the
   lane only after this boundary exists.
5. Implement reference-assisted phase tracking with digital vote accumulation,
   manual PI control and a bounded calibration algorithm.
6. Select and close the PLL frequency plan, then add autonomous CDR acquisition,
   bypass and lock observability.
7. Add receiver detect, electrical idle, shared bias/reference generation and
   protocol-visible safe controls.
8. Assemble the analog top and re-run hierarchical and flattened DRC/LVS/PEX,
   post-fill extraction, EM/IR, reliability and provider review.
9. Compose the checked behavioral PHY twin with the PCS/LTSSM/endpoint and prove
   training, enumeration, transfer, reset and recovery.

The present leaf work is not discarded by this order.  It becomes a library of
measured alternatives behind a much smaller selected product spine.
