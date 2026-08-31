# Analog evidence tooling: current operating overview

Last reviewed: 2026-08-31

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
| Evidence integrity helpers | [`ip/blocks/analog/wireline_serdes/analog_evidence.py`](../../ip/blocks/analog/wireline_serdes/analog_evidence.py), [`scripts/test_analog_evidence.py`](../../scripts/test_analog_evidence.py), machine-readable result JSON | Environment identity checks, interval coverage helpers, SHA-256 joins, and durable pass/fail/rejection records | The helper is deliberately small; result semantics remain specific to each active circuit. |
| PEX inspection | [`scripts/analyze_pex_net.py`](../../scripts/analyze_pex_net.py) | Resistance/capacitance and terminal-path reports for named extracted nets | It aids localization; it is not an automatic analog optimizer or a full parasitic-signoff engine. |
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

## What this tooling has productively done

It has supported real engineering decisions rather than only produced reports.

- **PCIe:** numerous GF180 leaves and selected physical parents have generated
  layouts, passed DRC/LVS, been RC extracted, and been screened over declared
  PVT environments. The current status, including both passed and rejected
  compositions, is maintained in [PCIe Gen1 analog status](pcie-analog-status.md).
  The active blocker is the extracted pulse-to-bridge-to-capture boundary,
  which presently passes three of five declared corners; it is not an
  integrated PCIe PHY claim.
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
  the justified next work is a complete driver schematic rather than a
  switch-only layout.

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

1. **PCIe:** make the selected clock/capture control path physically effective
   and pass its five-corner extracted composed boundary.
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
