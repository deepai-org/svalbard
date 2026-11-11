# Shared IO-pad foundation

One reusable protection/bond foundation with functional attachments serves
every custom pad: wired TX, wired RX/USB, differential reference, RF RX, RF TX,
the analog debug pairs (the `ESD_TEST` site was dropped 2026-11-11, interface-changes PD35). Generic digital/host pads, digital
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
| Single-leg cell (WMON; `ESD_TEST` dropped, PD35) | Native bond on `PAD_P`, `PADN` tied to VSS | `single-leg/` | — | 158,302 |
| `hspad` (SATA/PCIe RX, PD21) | Protection shell on `network-gc-d2` + two `pt_hs_leg` (segmented 4-bit termination, 4.9 pF AC-coupling MIM, RX bias/clamps, rail precharge); CTLE is the wired RX block | `wired-receive-hs/` | 508 | 531,000 bbox (478 × 1111 µm) |

All five layouts are DRC 0, netgen LVS match and pass the independent device
audit (`extract_audit.py`).

### PD28 (pads owner, 2026-11-11): rf_pair compact published, core-gate HBM screen, TX termination decision, pll_vreg packed

Working dir `scratch/pads-pd28/` (`hbm_core/`, `tx/DECISION.md`, `vreg/`, `usb/`).

- **attached_tx_buffer compacted (PD38):** `termination_buffer_array_layout.py` (multi-finger strapped arrays, same 280 devices)
  + unchanged compensation → `generated/termination-buffer-candidate/compact-array/`.
  - **PD40 rework after the independent review:**
    - power straps: tall S/D bars, M3+M4 straps with via area arrays straight to the 8 µm trunks;
    - contacted top/bottom ring strips (LU ≤ 12 µm);
    - result **0.062 mm² (was 0.156)**.
  - **Steering buffer:** `steering_buffer.py --compact` → `generated/steering-buffer-compact/`, **0.0071 mm² per instance (was 0.115)**.
  - **Readiness:** `readiness-settle.json` (held enable); the pessimistic corner is ss22/3.15 V at 184 ns. Interface-changes PD40.

- **`rf-pair/` republished = the compact GC rf_pair** (`scratch/pads-pd12/v2/rf-pair`, top `pad_rf_pair`): I8 inner-edge
  pins, LU taps, gate-coupled shunt (PD13 macro). Magic DRC 0, netgen LVS unique, independent device audit 388/388,
  KLayout main 0 / antenna 0 (`pad_rf_pair-kldrc.json`). PD13 family sims on this model: 18 safe/HBM runs, 0 of 348 MOS
  over the screen, ±100 mA 2.51–2.77 V, HBM-like pad 6.18–6.91 V (was 7.9–8.6 V with the static stack, see below),
  50 Ω AC −6.338 dB at 2.45 GHz (canonical −6.344). Pad C +42/+53 fF per leg vs the old cell (inner-edge stub). Backup:
  `scratch/pads-pd28/backup-published/rf-pair-pre-pd28/`. The top cell name changes from `rf_protected_pad_pair` to
  `pad_rf_pair` (assembly). (risk: INT-21)
- **Core-gate HBM screen** (`hbm_core_screen.py`, evidence `generated/stress-safe-families/pd28-core-gate-hbm-screen.json`):
  the PD13 HBM-like bench plus every consumer block that `chip_assembly/netlist.py` attaches to a pad net, flattened
  from its published extraction, every consumer MOS observed, unchanged gate screen (3.63 V / 6.0 V). P_pos tt27 + ss0,
  P_neg ss0. Clean: **LNA on RF_RX (876 MOS, pad 6.91 V: the input gate sits behind the 2 pF MIM and the p+/n-well
  junctions on that node into the (held) rail keep it at ≤ 0.94 V; worst LNA device 1.77 V)**, wirepad RX core (ctle/rxselect/detect/wmon_sel, 517 MOS). **Fail** (3.3 V devices whose
  source/drain IS the pad net, 6.2–6.9 V): `lo_ext` EXT switches (REF_IN, AUX_CLK), `diff_clk_rx` input gate
  (`ct_rxin` LP_C) and its LP_SW switch (AUX_CLK, WCLK_IN, WTX_EXT), `bb_tap` inj/obs switches (BB_I, BB_Q, WMON),
  `detect` TX-side switches (WIRE_TX). `rfdriver` (RF_TX): 6 V cascode gate–drain 6.18 V at ss/0 °C only (tt 6.36 V pad:
  passes); the 3.3 V `in_p` hit is a bench artifact (bypass PMOS conducts to an undriven input; with the driver's drain
  junctions modelled, 0). Even network-gc-d2 (pad ≤ 5.41 V) cannot bring a 3.3 V device on a pad net under 3.63 V, so
  the fixes are in the consumer blocks (interface-changes PD29). (risk: PAD-02, ESD-06)
- **TX pad termination / SST** (`scratch/pads-pd28/tx/DECISION.md`): SST rejected for this tapeout; the 6 V-switch fix
  clears HBM but costs return loss, not published (interface-changes PD30). (risk: ESD-05)
- **Ring regulators:** PD28 packed `pt_pll_vreg` (0.241 mm²), then **PD36 `pt_pll_vreg2`, one 0.175 mm² cell for pll_tx + pll_cdr** (`analog/pll_vreg/README.md` "PD36"). Coordinator decisions: TX TERM switches risk-accepted (ESD-05), USB-01, ESD-06, ESD_TEST dropped (interface-changes PD34/PD35). (risk: ESD-05)
- **USB wirepad on 6 V pad-side devices + LS slow-edge mode: PUBLISHED** (`wired-receive-usb/`, top `pad_wirepad`;
  build `stress_safe_compact_layout.py wired_receive_usb <dir> <network-gc-d2 macro> usbfix6v2ls 14`; working dir
  `scratch/pads-pd28/usbls/`, backup of the previous cell `scratch/pads-pd28/backup-published/wired-receive-usb-pre-pd28ls/`).
  v9 (every pad-tracking device 6 V, 3-bit trim `TERM_TRIM0..2`) plus port `LS_SLOW` (`wired_receive.py ls_slow`): each FS
  high side keeps its R/drain/well, its PMOS units split 10 (always) + 14 (gated off by LS_SLOW in their control path);
  the FS low side (base shunt bank) splits 3 (own inverter) + 7 (NOR with LS_SLOW). LS_SLOW = 0 = the v9 drivers and
  termination. Trunk tracks: pad-side nets keep their v9 x, control nets share free tracks (`layout.shared_tracks`).
  Magic DRC 0, LVS + device audit match, KLayout main 0 / antenna 0. **HBM 2 kV 0 of 613 MOS** (pad 5.04–5.41 V),
  ±100 mA 2.37–2.62 V, peer 0.30/0.49 µA. USB (extracted, trim tt 4 / ss 7 / ff 0): HS term 44.2–47.8 Ω, HS 17.5–18.2 mA,
  FS 5.7–11.1 ns (ratio 0.99–1.33, as v9), **LS (LS_SLOW = 1, 450 pF) rise 101–178 / fall 104–163 ns, ratio 0.97–1.09,
  VOH ≥ 3.11 V, VOL 0** at tt27/ss22/ss32/ff22/ff32; pad C 2.644–2.699 pF (≤ 2.7, 1 fF margin at ss32/3.15).
  Outline 286 × 1720 µm base (+130 µm vs v9, +208 vs the PD13 cell). Evidence `pd28-usb-ls.json`, `pd28-family-sims.json`.
  **Independent review (PD41), open blockers:**
  - **LS at light load:** at 50 pF the LS edges are 12–21 ns, so LS is not compliant at light load. Needs a slew-controlled pre-driver.
  - **Trim gating:** `TERM_TRIM = term_trim AND TERM_ENABLE` has no owner. The raw reset code shunts the pad.
  - **No term-trim calibration path:** at reset code 4 the termination is 37–54.5 Ω.
  - **Capacitance budget:** the pad C excludes the bypass-on RX load.
  - **Area:** the outline exceeds its area ceiling.
  - **LS_SLOW must be 0 whenever termination/HS is used:** it disables 7 of 10 base termination switches.
  - **Not all pad-side devices are 6 V:** the floating-well FS/pull-up PMOS remain 3.3 V by design (HBM-screened).
  **PD43–PD45 (pads fork, 2026-11-11; work dir `scratch/pads-pd42/usb/`):**
  - **Trim gating:** closed by digital DT-7 (`gate_and` + ls_slow interlock).
  - **Term calibration (PD43, no pad change):** half-scale HS current into the termination, read V(RX_P) through the
    bypass on a new wired-RX ATB leaf, firmware picks the code. Extracted v9, 5 corners × 8 codes, HS reference ±5 %,
    ADC ±1 % / ±2 mV: **41.45–49.18 Ω after calibration (pass, thin at ss)**. `pd43-term-cal.json`.
  - **LS slew (PD44, proof of concept, not laid out):** all FS units on in LS, limiter-starved pre-drivers mirrored from
    HS_PBIAS, 1.5 pF Miller MIM per driver via a pad-side TG. Extracted v9 + schematic additions (`slew/m7b.spice`):
    **LS 108–186 ns at 50 and 450 pF, all corners; FS 5.9–11.4 ns, VCRS 1.55–1.77 V; pad C +15 fF.** Layout, LVS/DRC and
    HBM rerun open.
  - **Pad C with bypass + RX load (PD45): 2.82–3.25 pF at 1.65 V, 3.57–3.58 pF at 0.2 V: fails 2.7 pF** (budget to
    re-derive for USB alone). `padc-wired-receive-usb.json`.
  - **Area:** unchanged, 352,213 vs 340,000 µm² (fails).

### PD21 (pads owner): low-C SATA/PCIe RX pad pair `pad_hspad`, network-gc-d2, HBM pad-side devices

User decision: SATA/PCIe get their own low-capacitance pad pair; USB FS/HS stay on `wirepad` (moved to the
WCLK_OBS/WDBG_OBS sites). Working notes: `scratch/pads-pd21/NOTES.md`.

- **`network-gc-d2`** (`generated/stress-safe-families/network-gc-d2/`): the GC network/shunt macro with one extra
  4-finger pad→rail diode row per leg (`protection_array.py --extra-up-rows 1`; default 0 = canonical). HBM-like
  2 kV pad peak 6.18–6.91 → **5.04–5.41 V** (rail unchanged 3.9–4.6 V), so every 6 V device on a pad node stays
  under its 6.0 V screen; +0.14 pF/leg (+0.12 with the rail precharged).
- **`pad_hspad`** (`wired-receive-hs/`, top `pad_hspad`, ports `PAD_P PAD_N RX_P RX_N VBIAS TERM_VCM TERM_ENABLE
  TERM_TRIM0..3 VDD VSS`): `shell/` = `protection_pad_ss` pair on network-gc-d2 (escape 8 µm, 12 µm trunks);
  `leg/` = `pt_hs_leg` (`hs_leg_layout.py`, convkit): 10 base units (ppolyf_u 2×3.05 + nfet_06v0 20/0.7) on
  TERM_ENABLE and 15 trim units (2×2.0 + 12/0.7) on TERM_TRIM0..3 (1/2/4/8) to TERM_VCM; MIM 2×35×35 µm (4.9 pF,
  bottom plate on PAD) to RX; 40 kΩ RX→VBIAS; 4 µm 6 V drain-diode clamps RX→VDD/VSS; a pfet_06v0 drain diode
  VDD→ATB_ESD_RAIL tap precharges the protection rail (2.4–2.75 V, 0.2–0.35 µA). Composed by `hs_pad_compose.py`.
  Magic DRC 0, netgen LVS unique, independent device audit 508/508, KLayout precheck main 0 / antenna 0, LU audit 0.
- **Qualification (extracted, `wired-receive-hs/pd21-*.json`):** safe/HBM with the unchanged
  `stress_safe_family_sims` benches: 18 runs, 404 MOS fully observed, **0 exceedances**; HBM pad 5.04–5.41 V; ±100 mA
  2.37–2.62 V; unpowered 3.63 V peer 0.15–0.34 µA; RX node −1.0…+1.0 V during HBM. Termination: code 0 64.8–116 Ω,
  code 15 24.4–38.7 Ω (VCM 0.3–0.5 V), 2–3.5 Ω/LSB near 50 Ω. AC (CTLE 120 fF/leg assumed, VCM 0.4 V, trimmed to
  ≈50 Ω): **1.11–1.14 pF/leg**, die RL at 2.4 GHz 8.0–8.5 dB; COB RL 13.0–16.7 dB (0.1–1.25 GHz), 5.7–6.5 dB
  (1.25–2.5 GHz, package-limited). RX path: HPF 0.67–1.07 MHz, 0.27–0.33 dB MIM loss, flat to 2.4 GHz.
  Power-up 10 ns/1 µs: no shunt trigger, VDD ≤ 80 µA peak. (risk: WRX-04)
- **TERM_VCM 0.3–0.5 V** (6 V NMOS switches; at 0.8 V the 40 Ω end moves to 44 Ω at ss). The CTLE CM comes from
  VBIAS through the MIM, not from the termination.

### 2026-11-10 changes (pads owner): LU-01 tap stripes, RF_TX pad, isolation clamps, ring regulator

- **LU-01 (shunt v2.2, `rail_shunt_v2.py`).** Each shunt bank is built from 14 guarded
  16-finger sub-banks whose shared guard columns are p+ tap stripes (20.96 µm pitch,
  farthest NCOMP 10.3 µm from a tap; DRM LU.3 asks ≤ 15 µm). Fingers 53.6 µm × 224 per
  stage = 12,006 µm (≥ the selected 12,000 µm). LU audit of the five rebuilt compact
  families: 0 µm² of n-diffusion beyond 15 µm (was 7,193 µm²). `run_first_pass.lvs` now
  also fails on netgen property errors (a W/L/m mismatch used to pass as a match).
  Rebuild: `scratch/pads-lu01/` (`build.sh`, `kl.sh`, `sims.sh`, `lu_audit.py`). (risk: LU-01, ESD-04)
- **RF_TX (`rftx_shunt.py`, cell `pad_rftxpad`, ESD-04).** The RF_TX pads rest at 3.3 V and
  peak at ~4.1 V, so the static shunt conducted. The RF_TX macro replaces the stack with one
  gate-coupled nfet_06v0 bank (Cc 32 pF MIM, Rg 6 kΩ). It has no 10 µA onset up to 5.4 V,
  the clamp averages ≤ 3.3 µA under the TX swing, HD3 ≤ −43 dBc, and stress and HBM-like
  peaks are below the rf_pair at every corner. Build: `scratch/pads-esd04/` (`esd04.py`,
  `layout/build_rftx.sh`).
- **Isolation clamps:** see `analog/island_support/README.md` §2a.
- **Ring-PLL regulator `pt_pll_vreg`:** see `analog/pll_vreg/README.md` (laid out, PD15) and interface-changes PD9.

### 2026-11-10 PD13: gate-coupled shunt on every family, RC-trigger fixes (pads owner)

- **All families now use the gate-coupled shunt** (`rftx_shunt.py` macro: one nfet_06v0 bank W 12,006 µm,
  gate GC, Cc 2 × 90² µm MIM ≈ 32 pF from `ESD_RAIL`, Rg 6 kΩ to VSS) instead of the static three-stage
  diode-connected stack: txpad, wirepad, refpad, single_leg and rftxpad (the rf_pair layout on the same macro;
  `rf_pair` itself stays held for P2). Pad C is unchanged (the shunt sits behind the steering diodes; the
  1.25 GHz pad C changes by < 1 fF). Published macro copy: `generated/stress-safe-families/network-gc/`.
- **RC-clamp trigger time constant** (`protection_candidate.CLAMP_CAPACITORS`): timing MIM 31.6 → 14 µm
  (≈ 2.0 → 0.4 pF; R 360 kΩ; τ ≈ 0.72 → 0.14 µs). The clamp no longer fires on µs feed ramps (1 µs TX feed ramp:
  36–48 → < 1 mA per leg); the HBM-like peak is unchanged because the GC shunt carries the event.
  `clamp_layout.py` now builds one MIM master per side (`clamp_mim`, `clamp_mim_t`).
- **Trigger-PMOS n+ ring closed** (`clamp_layout.close_trigger_ring`): the native U-shaped n-tap around the RC
  trigger PMOS row (X0/X1/X2, 84 µm² p-diffusion) is closed by an n-tap bar under the row; the three poly gate
  combs, their contact row and gate pads move up 0.27 µm, the drain-comb bars 0.12 µm, nwell and DUALGATE are
  extended. Devices and nets unchanged (clamp LVS unique, Magic DRC 0, KLayout precheck clean). LU audit: every
  p-diffusion of every family now sits inside a closed n+ ring (`pmos_to_ntap_diff_in_ring_frac` 1.0, was
  0.68–0.96).
- **Stress screen extended** (`stress_safe_family_sims.py`): every internal MOS terminal of the inner pad subckt
  (RC trigger chain, clamp gate, GC gate, attachment internals) and the core-side ports are saved and screened, so
  all MOS are fully observed (the RC clamp and trigger devices were never observed before). New `hbm` part: the
  esd04 HBM-like waveform (2 kV, 1.33 A, 2 ns / 150 ns) into every family. Extracted node names ending in `#` are
  renamed `_h` for this.
- Evidence and rebuild: `scratch/pads-pd12/` (`NOTES.md`, `v2/build.sh`, `sims4.sh`/`sims5.sh`,
  `compare.py`); backup of the previous published tree: `scratch/pads-pd12/backup-published/`.
  Results: see interface-changes PD13–PD17.

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
leaf for `ATB_ESD_RAIL` and its register entry do not exist yet. (risk: INT-04)

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
fully observed in the selection fixture. (risk: ESD-02)

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
| Reference | As a reference clock into `diff_clk_rx`: single-ended peaks near 2.65 V compressed at ff | Source ≤ 0.55 V peak, or `AUX_CLK`. This limit is for the clock-reference use only. As the external LO (`pt_lo_ext`, board B3: 3.0–4.0 Vpp open-circuit from 50 Ω, 10 pF coupling, 1.5 nH bond wire) the pad peaks stay ≤ 1.95 V in the simulated window and 13/13 envelope points pass at 3.0 Vpp in steady state (`analog/timing/generated/lo_ext-pad-evidence.json`, refpad on `REF_IN`, rf pair on `AUX_CLK`). The pad DC is still rising slowly at 300 ns (VCM bias through the 10 pF board coupling), so the steady-state peak is not simulated directly. (risk: PKG-05) |
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
| LS edges | 33–67 ns — **fails** | 75–300 ns (external PHY fallback) (risk: USB-02) |
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
  compliance. (risk: PAD-04)

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
switch on those lines, never a floating chip supply. (risk: PAD-04)

## Readiness (four tests)

| Block | safe | clean | observable | fallback |
| --- | --- | --- | --- | --- |
| `refpad`, `txpad`, `wirepad`, `rfpad`, `rftxpad` | pass | pass | open | waived_core |

`safe` rests on compact-model pulse/ramp/peer runs with a 0.105 V margin, not
HBM/CDM/TLP. `clean` covers DRC/LVS/device audit, envelope function runs and
area fit. `observable` needs the `ATB_ESD_RAIL` leaf and register entry. (risk: INT-04)

## Known limitations and open items

| Item | State |
| --- | --- |
| Stress margin | 0.105 V at ss/0 °C with drawn shunt wiring, excluding network-internal routing; partial terminal observation; 2 kV HBM / 500 V CDM targets not established (risk: ESD-02) |
| USB | LS edge rate fails (no slew control; no room in the 4.9k µm² headroom). HS amplitude needs a board-calibrated `wtx_idac` gate code, ~0.3 mV/mV supply sensitivity, no headroom to centre at ss/3.15 V (risk: USB-02) |
| Wired TX | Recorded disabled loading 2.706/2.713 pF vs 2.7 pF; asymmetric bond-to-core resistance (~8.34/11.67 Ω); static currents miss intended settings; bias/serializer readiness partly idealized (risk: PAD-05) |
| Wired RX/USB | Brownout controls, off-state gate stress and termination/pull handoff need connected acceptance |
| RF / reference | Real LNA, RF output stage and differential clock receiver are behavioral at the pad boundary |
| Autonomous disable | Rail supervisor candidate (`rail_supervisor.py`) trips at 2.625–2.7 V but has low-rail/overlap problems; not selected (risk: PAD-08) |
| Integration | Shared debug macros not drawn; full-ring LVS, integrated DRC, density, antenna, EM, package coupling and full-bank switching open (risk: INT-20) |
| Distributed resistance | Not in capacitance extraction; `wire_resistance.py`, `rf_route.py`, `protected_rf_route.py` are scoped sensitivity models |
| Reproducibility | The stress fixtures (`stress_safe_clamp.py`, `shunt_wiring_check.py`, `stress_safe_native_clamp.py`) read the retained RX/USB deck from `scratch/pad-supervised-receive`; `usb-attachment.json` was run with the replica-mirror HS bias still enabled in `stress_safe_usb.py --usbfix` (HS figures above come from the gate sweep); `atb-provider-pad-force.json`, `lifecycle-active-windows.json`, `tx-swing-investigation.json` and `powered-host-backfeed.json` have no generator script in this directory; `protection_pad_ss.generate(network=..., single_leg=...)` has no CLI flags (risk: INT-20) |

**Evidence currency.** `usb-attachment.json` and `families-report.json` predate
the current `stress_safe_usb.py`; `shunt-v2/shunt-layout.json` and
`families-report.json` predate the current `rail_shunt_v2.py` and
`strap_capacity.py` (wiring and device output unchanged; `reference()` moved in);
`stress-safe-native-clamp-check.json` predates `stress_safe_clamp.py`;
`stress-safe-selection.json` predates `layout.py` and `run_first_pass.py`;
`rail-supervisor-screen.json` and `pad-composition-comparison.json` predate the
opt-in `wired_receive.py` options (defaults unchanged);
`rf-receive-extraction.json` / `rf-transmit-extraction.json` record older
`circuits.py` and `physical.spice` hashes. `strap-capacity.json` is current. (risk: MOD-05)

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
