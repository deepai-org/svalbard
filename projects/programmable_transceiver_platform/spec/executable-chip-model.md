# Executable transistor-level chip schematic

Use the [analog design workflow](analog-design-workflow.md) for experiment selection, diagnostic ordering, reproducibility and accumulation of reusable lessons.

**User-required gate:** achieve a working integrated transistor-level schematic
of the whole analog chip before new layout/recreation work. Existing layouts
remain reference material. Include actual digital circuits where they determine
analog timing/loading/control; larger digital behavior may use existing RTL.

**Deferred to layout:** on-chip transmission-line geometry, twisted-pair or
coax-like routing, and physical shielding. Current work remains on connected
transistor-level circuits and their verification. Use explicit loading and
coupling scenarios where needed without designing these physical structures yet.

The primary design is a coherent hierarchical SPICE schematic using GF180 PDK
FETs and passives, before layout. This follows the user's clarification: actual
ADCs, PLLs and other circuits, not behavioral stand-ins as the implementation.
Build schematic circuits, verify connected behavior, then lay them out and repeat
the same checks using extracted parasitics. Layout constraints inform schematic
choices throughout; schematic success is not extracted or silicon qualification.

Follow block-diagram.md and preserve the full first-chip scope. Missing circuits
remain visibly missing. Behavioral stimulus, reference models and test fixtures
may support development, but cannot satisfy an implementation or feasibility gate.
The exploratory system_model envelope scaffold is not the requested chip design.

Use hierarchical subsystem tests for long startup/PLL/converter characterization
and shorter connected transistor tests for loading, clock and supply interactions.
Do not rely on a single enormous transient to answer all questions. Assemble a
whole-chip netlist as actual blocks become available; do not fill missing ADCs,
PLLs or CDRs with ideal sources and label that a complete chip.

Mandatory checks before scoring signal quality:

- Bias/common mode at every connected analog boundary, including internal nodes.
- Startup, precharge and the settling times of all bias networks.
- Separate prebiased characterization from cold-start evidence.
- Actual loading, clock swing/duty/phase and observation windows.
- Power, current, area and host-throughput budgets; list omitted contributions.
- Process/mismatch and uncertainty sensitivity in both directions, with no
  unsupported claims that assumed ranges bound silicon behavior.

Pass 124 is a required regression: a 1 Mohm/20 pF gate-bias path has a nominal
20 us charging timescale. UIC with a 301 ns observation left the LNA off. The
harness must reject invalid bias before reporting useful receiver performance.

## First assembled candidate

`analog/rf_rx_candidate.spice` connects actual GF180 oscillator, LO buffers,
LNA, mixer, active filter and sampling-switch subcircuits. Bias/control/sample
clocks are explicit external ports; PLL, quadrature and ADC are still absent.
Lumped passive values have not been mapped to complete physical structures.
`rf_candidate_op.spice` checks elaboration/DC bias; `rf_candidate_bias_tb.spice`
checks seeded/prebiased dynamic bias and clock activity. These benches do not
establish cold startup, full-chain gain or intrinsic noise.


## Completion gate and current gaps

`schematic-implementation.json` is the explicit implementation inventory. Source
presence does not prove operation. The gate remains closed until the complete
connected analog schematic demonstrates bias, startup, intended signal paths,
clocking, conversion, programmable modes, timing, variation and uncertain loading
within declared budgets. Document unresolved noise/model limits honestly; do not
replace absent circuitry with ideal sources to open the gate.

Audit finding: `pll_clock_path.spice` is a VCO/restorer/divider path, not a closed
PLL. `phase_control_dac.spice` controls timing and is not a radio converter.
That finding describes the earlier baseline, not the current next action. Actual
PFD/pump/filter circuits and converter candidates now exist, but are unqualified.
Use schematic-implementation.json and risk-priorities.md for current gaps and
priorities; historical pass notes must not override newer measured failures.
