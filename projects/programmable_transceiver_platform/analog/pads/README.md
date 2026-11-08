# Shared IO-pad foundation

One reusable protection/bond foundation with functional attachments serves
every custom pad: wired TX, wired RX/USB, differential reference, RF RX, RF TX,
the analog debug pairs and `ESD_TEST`. Generic digital/host pads, digital
observe outputs and ATB use the unchanged provider cells and are not simulated
here. **No family is production-qualified**; the readiness states below are
the tapeout-plan tests, not ESD/HBM/CDM ratings.

## Authoritative sources

| Owns | File |
| --- | --- |
| Requirements, sites, area ceilings | `spec/analog-architecture.json`, `spec/contract.json` |
| Sizing and implementation acceptance | `spec/schematic-implementation.json:io_pad_first_pass` |
| Resolved device selection | `design.build_integration_candidate()` (never copy budgets into bench defaults) |
| Shared protection recipe | `circuits.py:foundation_devices`; attachments in `circuits.py` / `wired_receive.py` |
| Canonical family layouts and coverage index | `generated/coverage.json`, `generated/selected-recipe-audit.json` |
| Selected protection and its cost | `generated/stress-safe-selection.json`, `generated/stress-safe-sweep.json` |
| Stress-safe layouts and per-family runs | `generated/stress-safe-families/families-report.json` |

## Blocks

| Block | Implemented boundary | Stress-safe layout (`generated/stress-safe-families/`) | Devices | Area used / ceiling (µm²) |
| --- | --- | --- | --- | --- |
| `txpad` (wired TX) | Protected pad, steering/TMDS drive, detection, terminations, extracted buffer and interlock | `wired-transmit/` | 1,088 | 292,666 / 300,000 |
| `wirepad` (wired RX/USB) | Protected network, discharge, divider/bypass, terminations, HS/FS drive and pulls, USB fixes | `wired-receive-usb/` | 1,170 | 335,069 / 340,000 |
| `refpad` (differential reference) | Protection/bias network; receiver is behavioral | `reference/` | 897 | 179,237 / 185,000 |
| `rfpad` = `rftxpad` (one physical pair) | Protection network, steering diodes, isolated clamp rail, MIMs, bleed; LNA and RF driver are behavioral | `rf-pair/` | — | 175,909 / 180,000 |
| Single-leg cell (WMON, `ESD_TEST`) | Native bond on `PAD_P`, `PADN` tied to VSS | `single-leg/` | — | 158,302 |

All five layouts are DRC 0, netgen LVS match and pass the independent device
audit (`extract_audit.py`).

### Protection foundation (drop-in macro v2.1, `network-shunt/`)

- Canonical isolated-rail `protection_network`: 4 + 4 steering diodes of
  22.5 µm² per pad, native-derived RC clamp 80 × 50 µm, MIMs, ~10 MΩ bleed.
- 100 kΩ clamp-gate discharge (8 × `ppolyf_u_1k` 1 × 12.5 µm); required for
  release (`stress-safe-native-clamp-check.json`: without it the clamp sticks at
  tt/27 °C, 1.06 mA, pad at 1.55 V).
- ATB tap `ATB_ESD_RAIL`: ~480 kΩ from the rail.
- Static rail shunt (`rail_shunt_v2.py`): three series banks of 240 × 50 µm
  diode-connected `nfet_06v0` (L 0.7 µm) from `ESD_RAIL` to VSS, 14 µm above the
  network. RAIL strap 30 µm metal5; VSS strap 30 µm metal4 + metal5 with a
  63 µm metal4 base. DRC 0, LVS match.
- Adds 0 pF at the pad at 1 GHz (shunt is behind the steering diodes); primary
  diode capacitance 0.169–0.181 pF per pad. About 51,500 µm² per pad pair.

### Ports and controls

Pad ports are `PAD_P`/`PAD_N`, `VDD`, `VSS`, the isolated `ESD_RAIL` and
`ATB_ESD_RAIL`, plus each attachment's active-high control ports
(`circuits.py`). USB HS bias `HS_PBIAS` is a VSS-referenced gate voltage from
the wired-TX `wtx_idac` (0–0.6 V, board-calibrated code;
`families-report.json:usb_attachment.hs_interface`). The island_support ATB
leaf for `ATB_ESD_RAIL` and its register entry do not exist yet.

## Results

### Stress (`stress-safe-sweep.json`, `wiring-resistance-check.json`)

Retained RX/USB fixture, +100 mA / 2 ns into `PAD_P` during brownout. Gate
screens: 6.0 V (06v0), 3.63 V (03v3) on observed terminals.

| Variant | Worst pad peak | Screen exceedances | Verdict |
| --- | --- | --- | --- |
| Canonical clamp + gate discharge, no shunt | 8.65 V (ss/85 °C) | 98 | fails |
| 2-stage 2000 µm shunt | 5.44 V | 0 | 7.6–16.8 mA per pad at 3.0–3.3 V: rejected |
| 3-stage 6000 / 9000 µm shunt | 6.37 / 6.02 V (ss/0 °C) | 18 / 18 | fails ss/0 °C |
| **3-stage 12000 µm shunt (selected)** | **5.81 V ss/0 °C, 5.15 V tt/27 °C; 5.87–5.90 V with drawn wiring R** | **0 at 7 corners** | selected |

Margin at ss/0 °C with wiring resistance: **0.105 V**. Only 88 of 1077 MOS are
fully observed in the selection fixture.

Per-family runs on the drawn layouts (`family-sims.json`):

- ±100 mA / 2 ns on both legs, tt/27 °C and ss/0 °C: pads +4.76 to −1.28 V,
  0 gate-screen exceedances (240–406 MOS observed). Single leg: +4.74 / −1.21 V.
- 0 → 3.63 V ramps: no exceedance.
- 3.63 V / 50 Ω peer, chip off: 0.87–6.7 mA per leg, supply backfeed ≤ 10 nA.
- Strap current (`strap-capacity.json`, DRM 14.2 at 85 °C): ≤ 0.12 of the limit
  at 13.4 mA (50 Ω peers), ≤ 0.50 at the 57.2 mA 3.63 V fault; 100 mA / 2 ns
  heating negligible.

### Swing and loading cost

DC load of one driven pad, function window (tt/ss/ff × 22/32 °C):

| Pad level | ≤ 1.65 V | 2.5 V | 3.0 V | 3.3 V | 3.35 V |
| --- | --- | --- | --- | --- | --- |
| Load | < 1 µA | ≤ 0.1 mA | ≤ 1.3 mA | 18 µA ss / 0.44 mA tt / 5.1 mA ff | ≤ 6.3 mA |

The 10 µA onset is 2.1 V (ff) to 3.2 V (ss). Brownout (VDD 1.5 V) load ≤ 0.70 mA,
pad 2.52–3.00 V. A 3.63 V peer draws ≤ 28.6 mA at ff/85 °C, into VSS only.

| Family | Effect | Fallback |
| --- | --- | --- |
| Wired TX | 3.3 V-referenced high levels droop up to ~0.3 V at ff | Board resistors or AC coupling instead of on-chip termination |
| USB FS | High level loaded by up to ~5–6 mA at ff | External board PHY |
| Reference | Single-ended peaks near 2.65 V compressed at ff | Source ≤ 0.55 V peak, or `AUX_CLK` |
| RF RX / TX | Unaffected below ~2.1 V; higher driver peaks clipped | LNA bypass with external LNA; mixer output to external PA |

The TX ss/3.15 V swing (0.50 / 0.81 V) is the same on the canonical layout
(`tx-swing-investigation.json`); the shunt does not cause it.

### USB on wirepad (`usb-attachment.json`, `usb-hs-gate-sweep.json`)

Attachment options in `wired_receive.build` (defaults reproduce the canonical
cell): termination `ppolyf_u` 16 × 1.3 µm per leg (39.6–53.3 Ω over resistor
corners), and a well-sourced fast-off PMOS on each FS high-side gate.

| Check | Result | Requirement |
| --- | --- | --- |
| HS amplitude, 13 points | 360–440 mV reachable with gate 0–0.54 V; ss/3.15 V tops out at 372–379 mV | 360–440 mV |
| FS high / low | 3.08–3.34 V / 0 V | — |
| FS edges | 5.8–11 ns | — |
| D+ after J→K | reaches 0 V | — |
| LS edges | 33–67 ns — **fails** | 75–300 ns (external PHY fallback) |
| Pull-up level | 2.72–2.93 V | — |
| Disabled loading | 2.34–2.35 pF | ≤ 2.7 pF |

### Debug sites (`debug-sites.json`, `shared-protection-check.json`)

Five protected pairs (BB_I, BB_Q, AUX_CLK, WCLK_IN, WTX_EXT) and two single-leg
cells (WMON, ESD_TEST): 1,196,149 µm² against a 1.2 mm² budget.

- `bb_tap`, tap off: protected pad adds ≤ 0.12 fF; isolation −101/−71/−40 dB
  (observed node) and −73/−53/−32 dB (inject node) at 10 MHz/100 MHz/1 GHz.
- `diff_clk_rx`: 345–377 fF differential input; Zin ≈ −j180 Ω at 2.45 GHz (the
  external LO needs a board match); 0.2 mVpp leakage for 0.88 Vpp when disabled.
- Shared macro (adopted, not drawn): neighbour pad B keeps only its steering
  diodes and uses pair A's macro through 40 µm rail/return buses: +0.035 V for
  BB_I+BB_Q, +0.022 V for WTX_EXT+WMON, inside the 0.105 V margin; saves about
  0.21 mm². The per-site cells remain the checked evidence until the shared
  cells are laid out.
- ATB0/1 on provider `asig_5p0`: forcing 3.63 V while powered draws ≤ 3.7 µA;
  unpowered it drives 54–56 mA through 50 Ω into the ring
  (`atb-provider-pad-force.json`). Force only when powered or at ≤ 1 mA
  compliance.

### Composition comparison (`generated/pad-composition-comparison.json`)

Comparison-model values at 1 GHz, worst leg (primary macro extracted;
attachments without new routing):

| Composition | Disabled / RX-bypass loading | Decision |
| --- | --- | --- |
| Separate wired TX / RX-USB | 1.802 / 1.155 pF; RX bypass 1.416 pF | Selected |
| Wired union | 2.655 / 2.917 pF | Exceeds 2.7 pF |
| Wired shared termination | 2.478 / 2.740 pF | Exceeds 2.7 pF |
| Lean RF receive + reference | 0.504 pF | Shared input structure retained |
| Universal | 2.958 / 3.220 pF | Exceeds RF 1 pF and wired 2.7 pF |

Share the foundation; merge attachments only when one populated candidate meets
loading, impedance and off-state requirements.

### Packaging and supply

`generated/packaging-assembly.gds`: 3932 × 5122 µm, 74 golden-mask openings,
native seal ring, 18 fixed power/ground sites, 211 µm pair pitch; 37 assigned
signals on the pinned board. Projected bond spans 1.797–2.665 mm, maximum angle
43.994°, no projected crossings (`packaging_audit.py`; geometric only). The
retained ring has one common supply net and one common ground net: **use one
common external supply**. The 81.6 mA powered-host backfeed
(`powered-host-backfeed.json`) enters through the 12 provider `bi_t` host pads,
not wirepad; board requirement: host lines high-Z while unpowered, an Ioff bus
switch on those lines, never a floating chip supply.

## Readiness (four tests)

| Block | safe | clean | observable | fallback |
| --- | --- | --- | --- | --- |
| `refpad`, `txpad`, `wirepad`, `rfpad`, `rftxpad` | pass | pass | open | waived_core |

`safe` rests on compact-model pulse/ramp/peer runs with a 0.105 V margin, not
HBM/CDM/TLP. `clean` covers DRC/LVS/device audit, envelope function runs and
area fit. `observable` needs the `ATB_ESD_RAIL` leaf and register entry.

## Known limitations and open items

| Item | State |
| --- | --- |
| Stress margin | 0.105 V at ss/0 °C with drawn shunt wiring, excluding network-internal routing; partial terminal observation; 2 kV HBM / 500 V CDM targets not established |
| USB | LS edge rate fails (no slew control; no room in the 4.9k µm² headroom). HS amplitude needs a board-calibrated `wtx_idac` gate code, ~0.3 mV/mV supply sensitivity, no headroom to centre at ss/3.15 V |
| Wired TX | Recorded disabled loading 2.706/2.713 pF vs 2.7 pF; asymmetric bond-to-core resistance (~8.34/11.67 Ω); static currents miss intended settings; bias/serializer readiness partly idealized |
| Wired RX/USB | Brownout controls, off-state gate stress and termination/pull handoff need connected acceptance |
| RF / reference | Real LNA, RF output stage and differential clock receiver are behavioral at the pad boundary |
| Autonomous disable | Rail supervisor candidate (`rail_supervisor.py`) trips at 2.625–2.7 V but has low-rail/overlap problems; not selected |
| Integration | Shared debug macros not drawn; full-ring LVS, integrated DRC, density, antenna, EM, package coupling and full-bank switching open |
| Distributed resistance | Not in capacitance extraction; `wire_resistance.py`, `rf_route.py`, `protected_rf_route.py` are scoped sensitivity models |
| Reproducibility | The stress fixtures (`stress_safe_clamp.py`, `shunt_wiring_check.py`, `stress_safe_native_clamp.py`) read the retained RX/USB deck from `scratch/pad-supervised-receive`; `usb-attachment.json` was run with the replica-mirror HS bias still enabled in `stress_safe_usb.py --usbfix` (HS figures above come from the gate sweep); `atb-provider-pad-force.json`, `lifecycle-active-windows.json`, `tx-swing-investigation.json` and `powered-host-backfeed.json` have no generator script in this directory; `protection_pad_ss.generate(network=..., single_leg=...)` has no CLI flags |

**Evidence currency.** `usb-attachment.json` and `families-report.json` predate
the current `stress_safe_usb.py`; `shunt-v2/shunt-layout.json` and
`families-report.json` predate the current `rail_shunt_v2.py` and
`strap_capacity.py` (wiring and device output unchanged; `reference()` moved in);
`stress-safe-native-clamp-check.json` predates `stress_safe_clamp.py`;
`stress-safe-selection.json` predates `layout.py` and `run_first_pass.py`;
`rail-supervisor-screen.json` and `pad-composition-comparison.json` predate the
opt-in `wired_receive.py` options (defaults unchanged);
`rf-receive-extraction.json` / `rf-transmit-extraction.json` record older
`circuits.py` and `physical.spice` hashes. `strap-capacity.json` is current.

## Reproduction

Environment (`env/pad-environment.json`):

- Layout image: `layout.py` uses the locked `sha256:9253a51f…` unless
  `SVALBARD_PAD_IMAGE` selects the rebuild from the same recipe
  (`sha256:b6027809…`, not byte-identical; clamp macro regenerates with an empty
  28-layer XOR, identical devices/capacitances, DRC 0, LVS match).
- Simulation image: `env/build_sim_image.sh <ngspice-47.tar.gz>` builds
  `svalbard/transceiver-pad-sim:ngspice47-corrected` offline with
  `ngspice-cap-multiplier.patch` and `ngspice-diode-charge.patch`
  (`diode_model_check.py` documents the regression). Recorded pulse decks
  reproduce byte-identical waveforms.
- PDK models: `scratch/transceiver-pad-pdk/ngspice` (identical to the pinned
  image's ciel f6eeac7 copy).

Stress-safe flow, from this directory, with new empty output directories:

```sh
export SVALBARD_PAD_IMAGE=sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43
python3 stress_safe_clamp.py --output-dir <dir> --report <json> --variants released_baseline stack2_w2000 stack3_w6000 stack3_w9000 stack3_w12000 stack3_w12000_extracted --corners typical:27 typical:0 typical:85 ss:0 ss:85 ff:0 ff:85 --dc stack3_w12000@typical:27,ff:32,ss:22,ff:85 --loading <variant>@typical:27,typical:22,typical:32,ss:22,ss:32,ff:22,ff:32,ff:85,typical:85,ss:0 --capacitance --jobs 4
python3 stress_safe_native_clamp.py --output-dir <dir> --report <json>
python3 protection_network_ss.py --output-dir <net>               # network + discharge + ATB tap
python3 rail_shunt_v2.py --output-dir <shunt>                      # v2 shunt
python3 rail_shunt_v2.py --macro --network-dir <net> --shunt-dir <shunt> --output-dir <macro>
python3 stress_safe_wired_layout.py {reference_clock|wired_transmit|wired_receive_usb} <work> <macro> [usbfix]
python3 shunt_wiring_check.py --macro-dir <macro> --shunt-dir <shunt> --output-dir <dir> --report <json>
python3 strap_capacity.py --macro-json <macro>/network-layout.json --report generated/stress-safe-families/strap-capacity.json
python3 stress_safe_family_sims.py --drawn-v4 --output-dir <dir> --report generated/stress-safe-families/family-sims.json
python3 stress_safe_usb.py --usbfix --output-dir <dir> --report <json> [--only hs_vsweep]
python3 stress_safe_debug.py --output-dir <dir> --report generated/stress-safe-families/debug-sites.json
python3 shared_protection_check.py --output-dir <dir> --report generated/stress-safe-families/shared-protection-check.json
python3 stress_safe_families_report.py --sims generated/stress-safe-families/family-sims.json
```

RF pair and single-leg cells come from
`protection_pad_ss.generate(work, generated, network=<macro>, single_leg=…)`.

Canonical family flow (repository root):

```sh
python3 projects/programmable_transceiver_platform/analog/pads/design.py --output scratch/transceiver-pad-inputs.json
python3 -m unittest discover -s projects/programmable_transceiver_platform/analog/pads -p test_design.py
python3 projects/programmable_transceiver_platform/analog/pads/run_first_pass.py --output-dir scratch/pad-pass --pdk-model-dir scratch/transceiver-pad-pdk/ngspice --publish-dir projects/programmable_transceiver_platform/analog/pads/generated
python3 projects/programmable_transceiver_platform/analog/pads/assembly.py --template scratch/pad-provider-template --output-dir scratch/pad-assembly --generated projects/programmable_transceiver_platform/analog/pads/generated --publish-dir projects/programmable_transceiver_platform/analog/pads/generated
```

`run_first_pass.py` refuses to publish on a failed GDS round trip
(`gds_roundtrip.py`). `gds_markers.py` restores HRES/DUALGATE enclosures;
`rail_connectivity.py` treats VIA4 inside CAPM as a MIM top-plate contact;
`extract_audit.py` reads device/body connectivity independently of the stock
converter. Do not add budget-sized ideal capacitors on top of extracted
capacitance.
