# Analog evidence tooling: current operating overview

Last reviewed: 2026-09-02

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
| Programmable leaf calibration and envelope replay | [`reference_level_receiver/run_bias_sweep.py`](../../ip/blocks/analog/wireline_serdes/reference_level_receiver/run_bias_sweep.py), [`run_envelope_matrix.py`](../../ip/blocks/analog/wireline_serdes/reference_level_receiver/run_envelope_matrix.py), and the physical checker | Reuses one schematic/PEX estimator across realizable bias codes, requires union coverage of every declared PVT environment, hashes runner/DUT identity, audits generated layout device widths/fingers against PEX, and introduces parent pulse/source/load dimensions one at a time | Code coverage does not transfer to a parent whose pulse width, slew, source impedance, history, reference code, or load falls outside the leaf campaign; the current PCIe v5 parent is retained proof of that boundary. |
| Measured-waveform and exact-consumer replay | [`reference_level_receiver/run_parent_waveform_replay.py`](../../ip/blocks/analog/wireline_serdes/reference_level_receiver/run_parent_waveform_replay.py) and [`run_output_sizing.py`](../../ip/blocks/analog/wireline_serdes/reference_level_receiver/run_output_sizing.py) | Samples an exact routed-parent boundary, replays its PWL trajectory against a leaf, replaces lumped load with the exact consumer PEX, and screens a bounded taper family in seconds | Presently TT and product-specific. Candidate passes still require physical lowering and full PVT requalification; two enlarged receiver candidates were correctly rejected there. |
| Role-specific variant lowering | [`reference_level_receiver/compile_variant.py`](../../ip/blocks/analog/wireline_serdes/reference_level_receiver/compile_variant.py) and [`sense_level_receiver`](../../ip/blocks/analog/wireline_serdes/sense_level_receiver) | Deterministically derives circuit and coded-layout variants from one template, emits an identity manifest, and keeps physical legality separate from a role-specific functional promotion gate | This is fixed-family lowering, not topology synthesis. The first SENSE variant is physically legal but correctly remains unpromoted at 4/5 functional environments. |
| Exact-consumer dynamic-node probes | [`reference_level_receiver/run_single_output_sweep.py`](../../ip/blocks/analog/wireline_serdes/reference_level_receiver/run_single_output_sweep.py) | Separates output-rail appearance from actual regenerative-consumer precharge/evaluation, and accepts explicit internal diagnostic nodes for bounded failure localization | Hierarchical node names are estimator-specific; these probes diagnose a known exact PEX and are not a portable block contract. |
| Physical-partition lowering | [`distributed_clock_fanout`](../../ip/blocks/analog/wireline_serdes/distributed_clock_fanout) | Preserves a screened circuit topology while mechanically splitting it into independently placeable physical leaves; derives simulation and parameter-free LVS views from one stage tuple and rejects device-property errors | The leaves are physically legal, but placement intent becomes evidence only after one routed-parent extraction and composed replay. |
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
remain manual. A first small candidate-comparison record now hash-binds nine
event/capture campaigns and summarizes their environment/code coverage. It
must be reused on the Wi-Fi IF driver before it is promoted into shared IR; it
is not yet a reason to build a new language, general router, or global topology
synthesizer.

The newer full-duty event/capture fixture caught a silent duplicate SPICE
parameter lowering before layout, proved that a compact selector reduced
parasitics but lost SS/hot rail margin, and showed that shortening a causal
route removed delay the circuit had accidentally consumed. An explicit
inverter-pair checkpoint earned the first TT exact-PEX capture pass but lost
SS/hot before `HSN`; its intermediate NOR/isolation and low-trip derivatives
were rejected. The selected active-low NAND state now removes two restoration
stages, passes 15/40 schematic cases covering 5/5 environments, and generates
a 192-device zero-DRC/unique-LVS 4,886R/3,577C macro. It retains one TT PEX
pass and advances the SS/hot failure to loaded `SB1`, which peaks at
1.100--1.195 V after `HSN` makes a real transition. Contract-declared semantic
probes also prevented removed nodes from manufacturing a false incomplete
result. Two bounded drive/load followups improved neither extracted coverage
nor schematic SS/hot admission. A subsequent cross-coupled NAND state covers
5/5 environments schematically and generates a 208-device zero-DRC,
unique-LVS 5,610R/4,170C macro, but exact PEX is 0/8. At SS/hot feedback leaves
`SB1` below 0.961 V; at TT `SB1` restores but BOOST misses high rail. The
contention-free dynamic-state followup is also physically legal and covers
5/5 schematically, but is 0/8 exact PEX because SS/hot `SB1` reaches only
0.665--0.689 V. Exact candidate replay now accepts an explicitly named
schematic/revision while verifying it against the physical record, and an
exact composition into the routed regenerative lane distinguishes static Q
initialization from a real generated capture event. The smaller 1/8 active-low
state therefore remains selected. This is executable
evidence for identity,
staged admission, and first-failure movement, not a generic optimizer or
completed PCIe clock path.

The subsequent capture-integrated checkpoint demonstrates the same staged
loop on a topology that removes a contract-declared internal node. Its exact
source covers 5/5 schematically and its generated 208-device parent passes
DRC/LVS/full-RC extraction, but targeted exact PEX is 0/4. A candidate-specific
probe manifest localizes slow/hot failure to `ESTATE` (about 0.7--2.4 V) and
the local tapers rather than manufacturing an incomplete result for deleted
`SB1`. The shared host runner can now require `result == pass` in a copied JSON
artifact, so a completed container that intentionally records negative
evidence no longer prints an overall pass. This is a small but important
compiler-style property: physical legality, simulation completion, and
contract admission are distinct machine-checked states.

The next compiler-style iteration used those probes to change structure rather
than sweep device ratios: two identical capture-local predrivers were merged
ahead of fanout. Structural tests caught an invalid default placement order
before layout. The admitted v2 covers 5/5 schematically, remains DRC/LVS clean,
and removes 8 devices, 330 extracted resistors, and 259 extracted capacitors.
Exact PEX remains 0/4, but semantic probes show the first major SS/hot rail
collapse moved from `ESTATE` to the combined `LSTATE` fanout. Two obvious
driver-sizing repairs were rejected at focused schematic admission. This is a
repeatable propose → admit → lower → extract → localize loop; topology proposal
is still human/LLM-guided rather than synthesized.

That loop then closed the remaining local fanout family rather than stopping
at its first negative layout. Split restoration, a four-stage geometric taper,
and localized final restoration were each admitted or rejected at the proper
stage. Terminal v7 is DRC/LVS clean and full-RC extracted; it clears the prior
TT BOOST rail failure, but an expanded exact gate over every TT-admitted
epoch-1 code plus the only SS/hot-admitted code remains 0/8. Semantic probes
move the SS/hot first failure through `LCB`, `LSTATE`, and finally `SDRV`, while
TT ends at SENSE width/timing. This is automatic PEX failure movement and
bounded branch closure—the tool does not yet synthesize the different capture
primitive now required.

Large composed-PEX decks now derive an explicit `.save` set from their
measures instead of retaining every internal RC node. The event-to-lane V8
screen exposed why this belongs in the evidence compiler: two parallel
ngspice workers each reached roughly 1.39 GB of waveform vectors and terminated
before measurement, which the result schema records as incomplete. The
corrected wrapper serializes these cases and retains only contract-observable
voltages plus supply current. That reduced live ngspice memory from a failed
roughly 1.39 GB per worker to about 75--83 MB for exact V8--V10 PEX. It enabled
complete results: V8 and V9 narrowly regress the selected V7 low interval, and
V10's extra taper stages regress both intervals decisively.

Routed-parent lowering also has an explicit semantic prerequisite.
The event, fanout, and lane leaf sources reuse generic internal subcircuit
names such as `cp_inv`; textual inclusion can therefore bind a parent's LVS
source to the wrong leaf definition. Parent compilation must namespace every
internal definition and call while preserving each public top name and its
physical identity. This is a concrete circuit/layout-IR identity obligation,
not a cosmetic naming cleanup; routing the parent before it is satisfied would
produce ambiguous evidence. The generic `spice_namespace.py` lowerer now
resolves a confined include closure, rejects cycles/escapes/duplicate
definitions, preserves declared public tops, and deterministically namespaces
internal definitions and calls. The retained PCIe event/fanout/lane parent
source is self-contained and instance-closure checked. Physical co-placement,
routing, DRC/LVS/PEX, and replay remain outstanding.

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
  bridge are implemented. Subsequent explicit-delay and intermediate branches
  led to the selected active-low NAND state; its exact PEX retains TT and moves
  SS/hot failure to loaded `SB1`. Local strength and BOOST-load partitioning
  are now closed. A physically legal cross-coupled NAND replacement then
  regressed to 0/8 exact PEX, closing its reset/strength/SENSE-edge branch; the
  authorized next experiment merges state into the capture cell or changes the
  state device family.
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

1. **PCIe:** the active-low detector state advances SS/hot failure to loaded
   `SB1`; local strength, BOOST-load splitting, cross-coupled NAND, and a
   contention-free dynamic-state replacement are now closed as negative
   evidence. Merge the state into the capture cell while preserving
   full-duty START/END, the
   direct-END bridge, three controls, and exact capture load; require
   regenerated DRC/LVS and five-environment PEX before routed-parent replay.
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
