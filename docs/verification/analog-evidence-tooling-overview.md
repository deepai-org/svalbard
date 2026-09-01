# Analog evidence tooling: current operating overview

Last reviewed: 2026-09-01

This page is the short operational companion to the longer
[product-first analog evidence plan](../roadmap/analog-evidence-compiler-spec.md).
It describes what is executable in this repository today, what it has been used
to establish or reject, and what it cannot establish. The repository is
building PCIe and Wi-Fi hardware; it is **not** currently delivering a
standalone general-purpose analog compiler.

## What exists now

| Capability | Executable source of truth | What it provides | Important boundary |
|---|---|---|---|
| Whole-product intent | [`projects/pcie_gen1_endpoint/analog/pcie_gen1_x1.aether`](../../projects/pcie_gen1_endpoint/analog/pcie_gen1_x1.aether), [`projects/wifi_nbiot_radio/analog/wifi_80211b.aether`](../../projects/wifi_nbiot_radio/analog/wifi_80211b.aether) | Reviewed top-level assumptions, guarantees, budgets, and open obligations | These files are specifications, not inputs to an implemented compiler or solver. |
| Bounded physical experiments | Per-block SPICE, layout Tcl/Python and `run_*.sh` wrappers under [`ip/blocks/analog`](../../ip/blocks/analog) | Reproducible GF180 circuit, layout, and block/parent experiments | Every block declares its own measured predicate and model boundary. A passing leaf does not prove a system. |
| Reproducible EDA host boundary | [`scripts/run_analog_flow.sh`](../../scripts/run_analog_flow.sh) | Pins the analog container image, prevents source changes during a run, bounds CPU/RAM/time, runs without network, and copies named outputs | It does not make a simulation signoff-quality or supply missing models. |
| Layout verification | Native Magic DRC/extraction and Netgen LVS invoked by physical block flows | Generated geometry, zero-DRC/unique-LVS gates, and RC extraction when a flow calls for it | It is public-PDK pre-silicon evidence, not foundry signoff, post-fill, EM/IR, package, or silicon correlation. |
| Circuit/PVT campaigns | Native ngspice decks and product-specific Python runners | Declared PVT sweeps, transient/AC/DC measurements, and failed-case capture | Not generic yield, BER confidence, phase noise, RF regulatory, or model-validation analysis. |
| Closure manifests and physical lowering | [`hclk_window_contract.json`](../../ip/blocks/analog/wireline_serdes/clock_pulse_hclk_window_probe/hclk_window_contract.json), [`event_capture_contract.json`](../../ip/blocks/analog/wireline_serdes/clock_pulse_hclk_window_probe/event_capture_contract.json), and their `compile_*_source.py` lowerings | Declares fixed variants, realizable codes, PVT environments, thresholds and semantic bindings, then resolves one selected identity into the exact schematic consumed by layout/LVS/PEX | These are product-specific thin slices, not a shared circuit/layout IR or general analog compiler. |
| Evidence integrity helpers | [`ip/blocks/analog/wireline_serdes/analog_evidence.py`](../../ip/blocks/analog/wireline_serdes/analog_evidence.py), [`scripts/test_analog_evidence.py`](../../scripts/test_analog_evidence.py), machine-readable result JSON | Environment identity checks, interval coverage helpers, SHA-256 joins, and durable pass/fail/rejection records | The helper is deliberately small; result semantics remain specific to each active circuit. |
| PEX inspection and bounded counterfactuals | [`scripts/analyze_pex_net.py`](../../scripts/analyze_pex_net.py), [`clock_pulse_hclk_window_probe/localize_selected_pex.py`](../../ip/blocks/analog/wireline_serdes/clock_pulse_hclk_window_probe/localize_selected_pex.py) | Named-net RC/path reports plus product-specific resistance/capacitance suppression on an exact PEX, with byte-identical baseline replay | Counterfactuals rank hypotheses only; modified PEX never qualifies geometry, and the localizer is not yet generic. |
| Tool artifact pinning | [`env/tool_artifacts.lock`](../../env/tool_artifacts.lock), [`scripts/tool_artifacts.py`](../../scripts/tool_artifacts.py) | Checksum-locked acquisition/verification of small auxiliary tools | The main physical flow uses the separately pinned OSIC image. |

The testable shared helpers are intentionally modest. Run them with:

```sh
python3 scripts/test_analog_evidence.py
python3 scripts/test_analyze_pex_net.py
python3 scripts/validate.py structure
python3 scripts/validate.py graph
python3 scripts/validate.py repo-audit
```

Run a product experiment through that product block's documented `run_*.sh`
wrapper. Do not invoke a result checker alone as a substitute for regenerating
the circuit or physical evidence it checks.

## The repeatable compiler loop we are moving toward

The useful near-term meaning of "compiler" is not unrestricted topology
invention. It is a deterministic closure loop around an intended circuit and a
bounded set of legal implementation choices. One versioned **closure manifest**
should name the circuit revision, topology identity, allowed sizing and layout
degrees of freedom, realizable control codes, environments, loads, semantic
nodes, predicates, models, generators, and tool profiles. A run should then
perform the following state machine without hand-edited intermediate files:

1. **Elaborate.** Resolve the manifest to one exact transistor/passive netlist,
   testbench family, and physical constraint set. Reject ambiguous device,
   terminal, control, or model identity before simulation.
2. **Screen cheaply.** Run structural checks and the smallest schematic PVT
   campaign that can reject the candidate. Record every case, not only the
   selected code or best waveform.
3. **Lower physically.** Generate deterministic devices, matching arrays,
   placement, routes, taps, guard structures, vias, and deliberate fill. A
   topology or connectivity change creates a new circuit revision; it is not a
   hidden placement optimization.
4. **Establish physical identity.** Require DRC and unique LVS before electrical
   promotion. Join the generated layout and extracted netlist back to the exact
   circuit and manifest hashes.
5. **Escalate evidence.** Run TT extracted-RC first, then the declared PVT set,
   then routed-parent, package/EM, statistical, or unavailable-physics checks
   only when the preceding boundary passes and the product claim needs them.
6. **Localize the first failure.** Report the earliest failed semantic state,
   its quantitative margin, the responsible physical path, and ranked bounded
   counterfactuals such as removing one net's R/C, strengthening one stage, or
   changing one realizable code. Preserve the failed candidate as evidence.
7. **Generate the next bounded experiment.** Search only declared parameters
   and reviewed topology alternatives. Select candidates for information gain
   and worst-case margin, not nominal score alone. Any topology proposal goes
   back through schematic screening; any geometry proposal regenerates
   DRC/LVS/PEX.
8. **Promote or stop.** Promote only the byte-identified candidate that satisfies
   every required case. Otherwise emit a rejection record or a named model,
   package, EM, foundry, or silicon-measurement obligation rather than widening
   the claim.

This makes each iteration a reproducible transition, for example
`schematic_pass -> physical_legal -> pex_fail(BOOST_low_margin) -> circuit_revision`,
instead of a directory of waveforms plus a designer's memory. It also makes
resumption and parallel execution safe: cases are content-addressed, cached
only when all dependencies match, resource bounded, and merged into one
deterministic result independent of completion order.

There are three deliberately separate roles:

| Role | Allowed to do | Not allowed to do |
|---|---|---|
| Deterministic evidence kernel | Elaborate identities, schedule tools, evaluate typed measurements, invalidate dependencies, and promote/reject claims | Change requirements or infer that an unrun analysis passed |
| Numerical/search engine | Explore declared continuous sizes, integer fingers, control codes, placements, and reviewed topology families using measured margins and surrogate models | Bypass regeneration or use a schematic score as physical proof |
| Designer or LLM assistant | Partition budgets, choose topology families, explain mechanisms, rank experiments, and recognize when missing physics or architecture is the blocker | Be the source of truth for connectivity, measurements, or signoff |

The current pulse-path flow is the first real fixture for this loop. It has a
closure manifest, deterministic source lowering, schematic campaigns,
DRC/LVS/PEX, semantic node labels, exact replay, and RC counterfactuals. Its
three-control recovery manifest now declares causal internal paths, and the
PEX runner distinguishes midrail transition propagation from strict output
rail compliance and records both first failures per active control path. This
localized an SS/hot BOOST failure to `RB0`, then traced WRITE degradation from
`E0`/`EMUX` to the first lost odd-phase `END` transition. A baseline-checked
semantic RC campaign and eight explicit schematic revisions showed that route
R/C, taper depth, isolation, and final drive cannot close the retained timing
contract independently. The replacement full-swing tap-chain source covers
5/5 schematically and is clean DRC/unique LVS, but its 5,494R/4,069C PEX is
0/2. The localizer now resolves semantic groups and representative cases from
the active schema-v2 contract; it shows that the new event states survive and
taper capacitance dominates the remaining WRITE collapse. Compact, lean, and
simple stateful output branches are retained as explicit schematic
rejections. Candidate generation and waveform-level margin interpretation
remain manual. A first small candidate-comparison record now hash-binds eight
event/capture campaigns and summarizes their environment/code coverage. It
must be reused on the Wi-Fi IF driver before it is promoted into shared IR; it
is not yet a reason to build a new language, general router, or global topology
synthesizer.

The newer full-duty event/capture fixture caught a silent duplicate SPICE
parameter lowering before layout, proved that a compact selector reduced
parasitics but lost SS/hot rail margin, and showed that shortening a causal
route removed delay the circuit had accidentally consumed.  The selected
revision turns that wire delay into an explicit inverter-pair state, passes a
40-case five-environment schematic campaign, generates a zero-DRC/unique-LVS
4,964R/3,713C macro, and earns the first TT exact-PEX capture pass. SS/hot is
still rejected at `HSDY -> HSN`. The subsequent bounded intermediate branch
added a polarity-aware detector and isolation taper. It remained physically
legal at 204 devices and 5,200R/3,863C, but exact PEX fell to 0/8: TT paid too
much isolation delay and SS/hot produced only a roughly 1-V detector pulse.
A low-trip follow-up then covered only FF/cold schematically and was rejected
before layout. This is executable evidence for identity, staged admission,
and first-failure movement, not a generic optimizer or completed PCIe clock
path.

## Portability beyond PCIe and Wi-Fi

The repository has a portable **execution shell**, not yet a portable analog
compiler. Its maturity separates cleanly by layer:

| Layer | Current portability | Evidence |
|---|---|---|
| Resource-bounded tool execution | Demonstrated across two product families | The same pinned, source-hash-checked host runner is used by 131 wireline and 10 Wi-Fi flow wrappers. |
| Small evidence primitives | Reusable but incompletely adopted | Hash, environment-set, interval, and minimum-cover helpers are unit tested; most Wi-Fi result schemas do not yet consume the same helper layer. |
| Candidate admission loop | Demonstrated in one demanding fixture | PCIe event/capture now performs structural checks, full-cube schematic rejection, deterministic layout, DRC/LVS/PEX promotion, and semantic failure reporting without hand-editing generated geometry. Candidate proposal remains manual. |
| Circuit/performance IR | Absent | Aether contracts are reviewed documents; there is no parser/elaborator that produces the SPICE, measurements, and constraints. |
| Generic physical synthesis | Absent | Existing generators understand particular topology families and GF180 geometry. They cannot accept an arbitrary transistor/passive netlist plus constraints. |
| Cross-domain claim refinement | Absent | Leaf-to-parent and package/system claims are recorded manually, with no executable refinement proof. |

No application outside PCIe/Wi-Fi has yet exercised the flow, so generality
beyond those domains is unproven. A sensible third portability fixture would
be a small non-communications macro such as an op-amp or sensor front end, but
only after the shared manifest/evidence schema has actually been reused by the
active Wi-Fi IF-driver work. Until then, adding a third demo would test the
wrappers more than the missing compiler core.

## What this tooling has productively done

It has supported real engineering decisions rather than only produced reports.

- **PCIe:** numerous GF180 leaves and selected physical parents have generated
  layouts, passed DRC/LVS, been RC extracted, and been screened over declared
  PVT environments. The current status, including both passed and rejected
  compositions, is maintained in [PCIe Gen1 analog status](pcie-analog-status.md).
  The active blocker is the extracted full-duty event-to-bridge-to-capture
  boundary. Its exact schematic covers 5/5 environments, its generated
  event/bridge macro is physically legal, and targeted exact PEX now passes TT
  but not SS/hot. The retained history leading to it begins with a
  source-level selectable-HCLK timing probe that retained two explicit rejected
  families, then found one physically fixed one-bit candidate with
  selectable-code coverage in all five environments. This is a necessary
  HCLK-to-WRITE schematic pass, then used the same manifest identity in a full
  SENSE/WRITE composition. That stronger gate rejects every one-bit joint
  candidate: final-edge SENSE control reached 4/5 and proved that FF/cold and
  FF/hot need the same interval code with different epochs. A restored two-bit
  hierarchy now passes 5/5 in the stronger 80-case SENSE/WRITE composition.
  The selected dual-phase source has since been generated, laid out, rendered,
  and shown zero-DRC/unique-LVS with 5,780R/4,083C extraction. Replaying the
  same dual-phase contract separates abstraction failure cleanly: the exact
  schematic covers 5/5 environments but its full-RC PEX covers 0/5, dominated
  by WRITE peak loss and followed by SENSE/timing failures. Hierarchy-aware
  lowering then restores much of the WRITE amplitude while preserving
  DRC/LVS, but moves its schedule outside the composed window. Exact-PEX RC
  counterfactuals reproduce identically and show that neither WRITE-path nor
  SENSE/BOOST-path idealization closes representative TT and SS/hot cases.
  The resulting independent SENSE/interval/epoch source and direct full-width
  BOOST branch retain 5/5 schematic coverage and generate a zero-DRC,
  unique-LVS 216-device macro. Semantic PEX probes prove the earlier `RB0`
  pulse filter is gone, but the shared-state load regresses SENSE and the
  complete targeted TT/SS-hot PEX gate remains 0/2. Manifest-declared WRITE
  paths now show rail degradation at `HBASE`/`START` at TT and at `E0`/`EMUX`
  before odd-phase `END` stops crossing at SS/hot. Exact semantic R/C
  counterfactuals and eight bounded schematic revisions pass neither TT plus
  SS/hot, closing local route, taper, isolation, and final-drive work. This is useful
  physical rejection and automated failure-movement evidence, not pulse or
  integrated PCIe closure. Follow-up isolated-taper and strengthened-shared-
  state layouts are also clean/unique-LVS but remain 0/2, closing the local
  SENSE/BOOST sizing branch. The retimed full-swing source and direct-END
  bridge are now implemented; the authorized next experiment is an
  intermediate, strongly restored SENSE delay between the rejected
  adjacent/no-delay and full-pair cases, followed by regenerated PEX.
- **Wi-Fi:** the routed LNA/mixer parent has DRC/LVS/full-RC PEX evidence, but
  its two-tone result exposed an unfiltered nearby blocker. This selected a
  real-IF ADC/DSP architecture rather than pretending a broad RF preselector
  provides 25-MHz adjacent-channel rejection. The 5-pF, 12-bit sampled-input
  boundary was then rejected by 125-C thermal noise before a new sampler
  layout. The NMOS-only sampler, simple transmission gate, and bare CMOS
  push-pull output stage have all been retained as explicit negative evidence.
  The latest output-stage coupon is
  [`ip/blocks/analog/wifi_80211b/rf_if_output_stage_probe`](../../ip/blocks/analog/wifi_80211b/rf_if_output_stage_probe):
  all 45 small-signal PVT cases complete but none meet its 0.379-ohm,
  100-MHz target. It motivates a closed-loop multistage IF driver; it is not
  a completed driver, sampler, ADC, or receiver. A subsequent raw-device
  compact-model speed screen does pass its limited necessary gate (8.037 GHz
  worst current-gain crossing versus a 989.056-MHz settling requirement), so
  a complete driver schematic was justified rather than a switch-only layout.
  That first feedback topology was promptly rejected in all five PVT cases for
  settling, common-mode error, and multi-ampere static draw; the next real
  circuit must use explicit CMFB and a compensated, current-limited output
  architecture. A separately biased source-follower primitive can achieve the
  output-impedance target, but only at up to 0.99 A/output and with substantial
  common-mode error, so it is evidence for an output-stage family rather than
  a complete receiver-driver claim.

These findings are useful precisely because a negative result blocks an
unjustified layout branch early. They are not evidence of PCI-SIG compliance,
Wi-Fi interoperability, production yield, ESD robustness, or fabricated
silicon behavior.

## What does not exist yet

There is no `aec` executable, shared circuit/layout/calibration IR, automatic
budget partitioner, topology synthesizer, placer/router, generic PEX failure
localizer, calibration synthesizer, statistical BER/yield engine, RF/EM
orchestrator, or contract-refinement checker. The Aether syntax and the
long-range semantic design in the roadmap are architecture references, not
implemented capabilities.

OpenADA, Cascode, CACE, OpenFASoC/gLayout, and ALIGN are recorded as preferred
integration candidates in the roadmap, but none is currently a required or
qualified backend for either product. Native GF180 flows remain authoritative
until a pinned upstream integration reproduces their relevant passing **and**
failing cases.

## Current priorities and rule for adding tooling

1. **PCIe:** the bounded intermediate-delay and low-trip-isolator branches are
   now closed as negative evidence. Co-design the detector and restored-state
   timing while preserving full-duty START/END, the direct-END bridge, three
   controls, and exact capture load; require regenerated DRC/LVS and
   five-environment PEX before routed-parent replay.
2. **Wi-Fi:** design and screen the closed-loop differential IF driver and
   thermal-floor hold-capacitor boundary before authorizing a new sampler
   layout.
3. **Shared tooling:** extract only a helper that removes an already observed
   repeated cost in both tracks, or twice in one track. It must be used
   immediately in the blocked product experiment and preserve native source
   and artifacts as the authority.

The longer roadmap defines the desired end state and claim discipline. This
overview should be updated whenever an executable shared helper, qualified
upstream adapter, active product gate, or model boundary changes.
