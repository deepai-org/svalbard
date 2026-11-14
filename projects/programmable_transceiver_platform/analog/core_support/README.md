# Core support: POR, bandgap, master bias and bias distribution

Always-on reference chain of the chip (core rail, never switched) plus the bias cells that sit on island
rails. Vendored cells and their provenance are in [`UPSTREAM.md`](UPSTREAM.md).

Unless a row names another source, every number comes from
[`evidence/core_support_evidence.json`](evidence/core_support_evidence.json) (written by `run_core_support.sh`;
its `source_hashes_sha256` match the current files).

## Blocks

| Block | Source | Tapeout view | Size (µm) |
| --- | --- | --- | --- |
| POR | `gf180mcu_ocd_ip__por`, unmodified | `por/gds/gf180mcu_ocd_ip__por.gds.gz` | 185.61 × 82.45 |
| Bandgap, 1.2 V | `gf180mcu_ocd_ip__bandgap`, unmodified | `bandgap/gds/gf180mcu_ocd_ip__bandgap.gds.gz` | 142.01 × 66.68 |
| Master bias | `gf180mcu_ocd_ip__biasgen` + 2 local patches (`patches/`) | `biasgen_tapeout/gf180mcu_ocd_ip__biasgen.gds.gz` (not `biasgen/gds`) | 468.37 × 100.26 |
| Distribution root | `pt_bias_root` | `distribution/generated/` | 157.70 × 25.06 |
| Island banks | `pt_bias_bank3`, `bank4`, `bank5`, `bank8` | `distribution/generated/` | 154.42 × 27.26, 174.30 × 46.32, 176.38 × 50.82, 183.88 × 77.98 |
| Master voltage references | `pt_bias_vref` | `distribution/generated/` | 88.80 × 56.68 |
| Two-output trunk tap | `pt_bias_tap2` | `distribution/generated/` | 93.74 × 23.66 |
| Reference-pad common mode | `pt_refvcm` | `distribution/generated/` | 137.88 × 53.98 |
| TX-pad bias | `pt_txpad_bias` | `distribution/generated/` | 167.29 × 61.14 |

Sizes: vendored LEFs, `biasgen_tapeout/*.lef`, and `distribution/generated/<cell>-layout.json`.

Chain: VDD → biasgen self-referenced sinks → bandgap → `vbg` → biasgen sources (`idac2`, 10 µA) → `pt_bias_root`
→ five current-mode trunks → island banks → 10 µA per consumer. There is no circular start-up dependence.

## Operating conditions

| Use | Points |
| --- | --- |
| Function | tt/ss/ff × 22/32 °C × 3.15/3.35 V plus tt/27 °C/3.3 V (13 points) |
| Safety | 0 → 3.63 V ramps, brownout, repeated ramps, 0–85 °C |
| Supply trim (slow dies up to 3.50 V) | only the 3.5 V rows named below; see Open items |

## POR (`gf180mcu_ocd_ip__por`)

Pins `vdd3v3 ena por_unbuf vss porb por`. Chip binding: `ena` = VDD, `porb` → macro `por_n`.

| Check | Result |
| --- | --- |
| Magic DRC / KLayout DRC (PDK deck, density excluded) | 0 / 0 |
| LVS, Magic hierarchical and vendored GDS read back flat | match uniquely, both |
| Cross-check in the digital image (Magic 8.3.623, Netgen 1.5.316) | DRC 0, LVS match |
| HRES on `ppolyf_u_1k` bodies | 200 of 200 |
| Extraction | Magic R+C, flat |
| Function window, extracted, 13 points | one clean release 32.8–48.6 ms after VDD reaches 90 % (schematic 31.1–46.2 ms); 1.9–3.6 µA after release |
| Ramps to 3.63 V, schematic, tt/ss/ff × 0/27/85 °C × 1 µs…1 s (54 runs) | 50 clean. 1 µs–10 ms: release 34–55 ms after ramp start. 100 ms: released at VDD 1.36–3.48 V. 1 s: **no reset** at ff (0/27/85 °C) and tt/85 °C |
| Dips after a cold start (10 µs edges) | to ≥ 1.5 V: no reset. To 1.0 V: full reset in 5 of 8 cases. To ≤ 0.5 V and 0 V: reset re-issued |
| Power cycle to 0 V, off 100 µs–1 s | reset re-issued every time, hold 28–40 ms |
| Resistor × MIM corners, extracted, 1 ms ramp (`scratch/pads-core/corners/`) | release 25–73 ms; 51.0 ms at ss/32 °C/3.5 V |

The POR is a cold-start and power-cycle reset only. It is not a brownout detector and does not cover ramps
slower than about 100 ms. Its hold-off node is a 7.2 pF MIM capacitor charged by about 0.4 nA: nothing may be
connected to `por_unbuf` or the capacitor node (ATB code 4 is reserved and tied to VSS for this reason). A leak
of 200–400 pA on that node stops release for ever (`scratch/reviews/always-on-audit.md` F1). (risk: PWR-02)

Reset path (`rtl/pt_por_path.sv`, checked by `verification/check_por_path.py`):
`rst_n = RESET_N AND (POR OR strap OR keyed override)`.

- **Board supervisor on `RESET_N`** is mandatory (board rules B1, B49).
- **`POR_BYPASS` strap:** provider input pad `gf180mcu_fd_io__in_c`, unmodified, pull-down hard-enabled, on east
  `bidir[16]`; `Y` → macro `por_bypass`. Evidence `scratch/reviews/pads-core/STRAP.md` (PDK transistor netlist):
  input threshold 0.99–1.27 V, pull-down 2.55–3.82 µA at 0.4 V, floating pad at 5–16 µV, 2.5 µA of external
  leakage needed to reach 0.4 V. With 0.2 pF on the pad `Y` glitches for ≤ 77 ns on 1–3 µs ramps and never at
  ≥ 10 µs; `RESET_N` low through power-up (B49) makes the glitch harmless.
- **Keyed override:** pad-free second path, SPI key sequence (board rule B51).
- Observation: `RESET_STATUS` (0x0D) and the live `por_n` on `DBG_OBS`.

## Master bias (`gf180mcu_ocd_ip__biasgen`, patched)

Single-supply use: `avdd = dvdd = ref_in = VDD`, `avss = dvss = VSS`.

| Patch | Why |
| --- | --- |
| `biasgen-dvdd-dvss-pin-alignment.patch` | The vendored top-level `dvdd` pin sits on the ground strap (vendored LVS fails pin matching; wired as delivered it shorts VDD to ground). |
| `biasgen-vfb-compensation.patch` | The vendored bandgap-referenced loop is unstable (−28° phase margin at tt/27 °C/3.3 V, oscillates in transient). Adds 4 × 100 × 38 µm MIM (about 30 pF) from `vfb` to `avss`, and `C3` (m = 4) in the schematic. |

| Check (patched) | Result |
| --- | --- |
| Magic DRC / KLayout DRC on the tapeout GDS | 0 / 0 |
| LVS, tapeout GDS flat | match uniquely, with and without `dvss` tied to `avss` |
| LVS, Magic hierarchical | match uniquely with `dvss` tied to `avss` (Magic joins them through the substrate; the chip binds both to VSS) |
| Cross-check in the digital image | match uniquely |
| HRES on `ppolyf_u_1k` bodies | 106 of 106 |
| Extraction | capacitance only (Magic R+C segfaults on this layout) |
| Loop gain, standard range, tt/ss/ff × 0/22/32/85 °C × 3.15/3.35 V + nominal (25 points) | phase margin 53–79°, gain margin 21–34 dB |
| Loop gain, coarse range (the range in use), function window | phase margin 79.5–94° |
| Transients, 5 ns step ceiling (fast ramps, `ena` and `ref_sel_vbg` steps, 150 mV supply step) | 23 of 23 settle |
| Start-up ramps 1 µs–100 ms, tt/ss/ff × 0/27/85 °C | 33 of 33 reach the DC point |
| `ena` = 0 | 2.1 nA supply current |

LVS is read strictly (`flow/summarize.py`; gate `lvs_qualification` in the evidence file). MIM orientation is
canonicalised in both netlists before comparison (`flow/canon_mim.py`). The assembly's reference netlists are in
`lvs_reference/` (`SHA256SUMS`, checked by `verification/core_bias_routing/device_lvs_reference.py`).

Behaviour to know:

- **Fine range alone** (`ref_sel_fine` = 1, `ref_sel_coarse` = 0) has about 25° of phase margin. It is rejected at
  commit and gated in hardware.
- **Self-referenced mode** is not usable as the master reference at 3.3 V (sources 420–465 %/V supply
  sensitivity). Bandgap mode: 0.3–2.7 %/V.
- **Sink DACs are not binary:** 3-bit sinks have bit 0 = 3 units, bits 1 and 2 one unit each. Source DACs are
  5-bit binary, 1 µA unit in the coarse range.
- Output current follows the poly resistor (±20 %), not the MOS corner.

## Bandgap (`gf180mcu_ocd_ip__bandgap`)

Bias pins: `ibias2_1u` from biasgen `bandgap_sink1` (code 7), `ibias1_250n` from `bandgap_sink2` (code 3).

| Check | Result |
| --- | --- |
| KLayout DRC on the vendored GDS | 0 |
| Magic DRC | 46, all inside the PDK's fixed PNP cell (45) or Magic-only MIMTM.2 (1); KLayout passes both |
| LVS, hierarchical and vendored GDS flat | match uniquely after mapping the PNP device name (`pnp_10p00x00p42` in this PDK's Magic tech) |
| Extraction | capacitance only |
| Trim (thermometer count 0 / 8 / 16), tt/27 °C | 1.138 / 1.212 / 1.341 V; steps 4–19 mV |
| Stand-alone, ideal bias, tt/ss/ff × −40…125 °C | 1.204–1.220 V; 87–161 µA |
| Full chain (bandgap + biasgen coarse, `idac2` code 10 + distribution), function window, 14 points | all start; `vbg` 1.207–1.219 V; outputs 7.64–12.14 µA; chain supply 0.30–0.52 mA; `vbg` within 1 % 10–20 µs after VDD reaches 90 % |
| Start-up, 0 → 3.63 V in 1 µs–1 s, 0–85 °C (28 runs) | all start; peak supply ≤ 0.42 mA |
| ATB0 force of 1.2 V with `ena` = 0 | force source carries 15–34 pA; `idac2` 8.0–11.6 µA |
| ATB0 force with `ena` = 1 | 5.1 µA through the leaf, `vbg` stays 1.212 V: disable the bandgap before forcing |
| Crossed MOS × resistor corners incl. sf/fs, extracted (`scratch/pads-core/corners/`) | outputs 7.88–11.81 µA, `vbg` 1.206–1.221 V, all start |

Two properties that are not in the evidence file (`scratch/reviews/always-on-audit.md` F4, F5):

- **`ena` = 0 does not power the bandgap down.** It only tri-states the output buffer. The core draws 71 µA at
  tt/27 °C/3.3 V with `ena` = 0. Reset-state current of the whole core bias block is 91 µA (bandgap 71 µA, VCM
  divider about 20 µA, biasgen 1.2 nA); 131.9 µA at ff/85 °C/3.63 V. A faulty bandgap is bypassed with the ATB0
  force, not switched off.
- **`vbg` overshoots to the rail for about 4 µs when `ena` rises** (peak 3.18 V at tt, 3.41 V at ss/3.5 V,
  3.53 V at ff/85 °C/3.63 V). Every node that sees it is a 3.3 V gate or the passive `pt_bias_vref` divider.
  The macro enforces the order: `pt_bgap_interlock` (`rtl/pt_ctl_decode.sv`) holds `ref_sel_vbg` and every
  trunk enable at 0 until `bgap_ena` has been 1 for 256 SCLK cycles.

## Bias distribution (`distribution/`)

All devices are 3.3 V, L = 4 µm, no cascodes. Every consumer sinks 10 µA into an NMOS diode, so each output is
a switched PMOS source. Layout uses the row generator `analog/rf_tx/layoutlib.py`.

| Cell | Pins | Rail | Function |
| --- | --- | --- | --- |
| `pt_bias_root` | `VSS ROOT_REF EN_RF EN_CONV EN_PLL EN_WIRE EN_DEBUG TRK_RF TRK_CONV TRK_PLL TRK_WIRE TRK_DEBUG` | core | NMOS diode on `ROOT_REF` plus five 1:1 legs, each behind a switch |
| `pt_bias_bank<N>` | `VDD VSS TRK EN0..EN<N-1> OUT0..OUT<N-1>` | island | PMOS diode on `TRK` plus N switched 1:1 mirrors |
| `pt_bias_tap2` | `VDD VSS TRK EN0 EN1 OUT0 OUT1` | its bank's rail | two more switched outputs on an existing trunk (no diode) |
| `pt_bias_vref` | `VDD VSS VBG VREF0 VCM` | core | passive: `VREF0` = 5/6·`VBG`, `VCM` = VDD/2 |
| `pt_refvcm` | `VDD VSS EN VCM` | pll | gated VDD/2 for the reference-pad `VCM` pins |
| `pt_txpad_bias` | `VDD VSS EN BUF_REF BUF_BIAS EN_DET IBIAS_DET DETECT_PBIAS` | wired_tx | gated TX termination-buffer reference (VDD/2) and bias (3/11 VDD) dividers; ×5 mirror for the TX-pad detect PMOS bias |

| Trunk | Bank | Outputs |
| --- | --- | --- |
| rf | `pt_bias_bank8` | lna, rxmix_i, rxmix_q, bbfilter_i, bbfilter_q, txmix_i, txmix_q, rfdriver |
| conv | `pt_bias_bank5` | adc_i, adc_q, dac_i, dac_q, refbuf |
| pll | `pt_bias_bank4` | pll_ring_tx, pll_ring_rx, `pt_cdr` (the output named `pll_ring_host`), one output with `EN` tied low |
| wire | `pt_bias_bank3` | ctle, detect, wiredtx |
| debug | `pt_bias_bank3` | bb_tap_i, bb_tap_q, bb_tap_wmon |

Physical, all nine cells: Magic DRC 0, KLayout DRC 0, LVS match uniquely (`<cell>-layout.json`, `<cell>-lvs.txt`).
HRES: `pt_bias_vref` 10 of 10, `pt_refvcm` 4 of 4, `pt_txpad_bias` 13 of 13. Extraction is capacitance only.
`pt_bias_tap2`, `pt_refvcm` and `pt_txpad_bias` also have LVS on the GDS read back from disk with a failing
negative control, and precheck-deck records (`<cell>-kldrc.json`: main 0, antenna 0, sha-matched, registered in
`verification/kl_block_drc_blocks.json`). LEF abstracts exist for the root, the banks and `pt_bias_vref`
(`abstract-evidence.json`).

| Result | Value | Source |
| --- | --- | --- |
| Root + banks, ideal 10 µA reference, function window, schematic and extracted | 10.06–10.15 µA on all 23 outputs | evidence file |
| Behind the biasgen (coarse, code 10) | 7.52–12.06 µA (resistor spread; trimmed per die with `idac2`) | evidence file |
| Disabled output or trunk, 0–85 °C, 3.63 V | ≤ 47 pA | evidence file |
| Island rail at 0 V, trunk and enables high | no output current | evidence file |
| 10 µA sunk from `TRK_RF` with all trunks disabled | 10.02 µA on the 8 rf outputs, ≤ 12 pA elsewhere; `TRK_RF` at 1.98 V | evidence file |
| 0 → 3.63 V in 10 µs, enables low / high | outputs ≤ 10 nA peak / ≤ 10.21 µA peak | evidence file |
| `pt_bias_tap2`, extracted, 19 corners | 10.05–10.20 µA, tap/bank ratio 1.0000 on one rail; **3.4 % per 10 mV of rail offset** | `scratch/reviews/pads-core/CORE-SUPPORT-CELLS.md` |
| `pt_refvcm` | `VCM`/VDD 0.4984–0.4992, 15–29 µA; off: 0 V, ≤ 2.3 nA; 40 kΩ source | same |
| `pt_txpad_bias` | `BUF_REF`/VDD 0.4967–0.4984, `BUF_BIAS`/VDD 0.2714–0.2721, about 195 µA on; detect source 49.5–50.8 µA per pad leg from 10 µA into `IBIAS_DET` | same |
| `pt_bias_vref` | `VREF0` = 1.010 V at `VBG` 1.212 V; `VCM` divider about 20 µA | netlist; always-on audit F4 |

Conditions of use:

- A bank or tap must sit on the same rail as its trunk diode. A trunk whose diode rail is off turns every
  mirror on it fully on (108–160 µA into a consumer diode, `scratch/reviews/pads-core/core-support-REVIEW.md`).
- `pt_refvcm` is a 40 kΩ source: the reference pads must be AC-coupled or driven complementary about VDD/2.
- `pt_txpad_bias` gives 50 µA per detect leg; 100 µA needs a wider detect device in the TX pad.
- A bank output left enabled into a disabled consumer still delivers up to 10 µA: each output `EN` follows its
  consumer's enable.

## Register requirements

Register names as in `spec/register-map.md` (`core.biasgen` 0x57/0x58, `core.refchain` 0x59). Every reset value
is the safe state.

| Field | Width | Reset | Normal | Notes |
| --- | --- | --- | --- | --- |
| `core.biasgen.ena` | 1 | 0 | 1 | |
| `core.biasgen.ref_sel_vbg` | 1 | 0 | 1 | sources referenced to `vbg`; held 0 by the interlock until the bandgap has settled |
| `core.biasgen.ref_sel_coarse` | 1 | 0 | 1 | 1 µA unit; the distribution needs it |
| `core.biasgen.ref_sel_fine` | 1 | 0 | 0 | forbidden without `ref_sel_coarse` |
| `core.biasgen.idac2_source` | 5 | 10 | trimmed, 8–13 | reference into `ROOT_REF`, code × 1 µA |
| `core.biasgen.idac1_source` | 5 | 0 | 0 | spare source, used for the trim measurement |
| `core.biasgen.bandgap_sink1` / `bandgap_sink2` | 3 / 2 | 7 / 3 | 7 / 3 | bandgap bias |
| `core.biasgen.voltgen_*` | 5/3/3 | 0 | 0 | outputs unused (voltgen is not imported) |
| `core.refchain.bgap_ena` | 1 | 0 | 1 | must be 0 while ATB0 forces `VBG` |
| `core.refchain.bgap_trim` | 5 (count 0–16) | 8 | trimmed | decoded to the 16-bit thermometer |
| `core.refchain.dist_en_<rf,conv,pll,wire,debug>` | 1 each | 0 | 1 when the island is powered | root trunk legs |

Bring-up sequence:

1. Islands off, all fields at reset.
2. `core.biasgen.ena` = 1 and `core.refchain.bgap_ena` = 1. Wait ≥ 100 µs.
3. `ref_sel_vbg` = 1, `ref_sel_coarse` = 1.
4. Power an island, set its `dist_en`, then the block enables.

Per-die trims (host software, after every reset):

1. **Bandgap:** sense `VBG` on ATB1 and pick the `bgap_trim` count closest to 1.200 V.
2. **Distribution reference:** set `idac1_source` = 10, measure its current on ATB1 code 57 into an SMU at about
   1 V (`I_meas`), set `idac2_source` = round(100 µA / `I_meas`), set `idac1_source` back to 0. Cross-check with
   the bank's rail on and its outputs disabled: sink 10 µA from `TRK_<island>` and read one output.

ATB nodes and the core reference-chain force preconditions (commit rules 29–35 of `spec/register-map.md`,
exercised by `verification/check_regfile.py`):

| Node | ATB code | Nominal | Force on ATB0 | Precondition for force |
| --- | --- | --- | --- | --- |
| `VBG` | 55 | 1.21 V | 1.2 V | `bgap_ena` = 0 |
| `ROOT_REF` | 1 | 0.92 V | 10 µA into the node | `idac2_source` = 0 or `biasgen.ena` = 0 |
| `TRK_RF`, `TRK_WIRE`, `TRK_PLL`, `TRK_CONV`, `TRK_DEBUG` | 14, 22, 29, 35, 56 | about 2.0 V | 10 µA out of the node | that `dist_en` = 0 |
| `VREF0`, `VCM` | 2, 3 | 1.01 V, VDD/2 | sense only | |
| `idac1_source_ibias` | 57 | current into an SMU at about 1 V | sense only | `idac1_source` ≠ 0 |

## Chip binding (`integration/top/pt_chip.conn`)

| Instance | Cell | Notes |
| --- | --- | --- |
| `por` | `gf180mcu_ocd_ip__por` | core rail |
| `core_bias` | `pt_core_bias` (bandgap, biasgen, root, five banks, `pt_bias_vref`; assembled by `verification/core_bias_routing/`) | bank rails: rf_rx, conv, pll, wired_rx, debug |
| `pad_por_bypass` | provider input pad | `Y` → `por_bypass` |
| `refvcm` | `pt_refvcm` | `RAIL_pll`, `VCM` → both reference pad pairs |
| `txpad_bias` | `pt_txpad_bias` | `RAIL_wired_tx` |
| `bias_ext` | demand for three more outputs (qvco, lo_pfdcp, hsbias) | to be met with `pt_bias_tap2` instances |

## Flow

```
analog/core_support/run_core_support.sh    # steps: fetch verify clean tapeout canary dist sim summarize
```

Needs Docker with the two pinned images (`UPSTREAM.md`). `fetch` is the only step that uses the network.
Containers run with `--network none`, bounded CPU and memory, `OMP_NUM_THREADS=1`. Heavy output goes to
`scratch/core_support/`; the repo receives `evidence/`, `biasgen_tapeout/`, `lvs_reference/` and
`distribution/generated/`.

| Script | Does |
| --- | --- |
| `flow/clean_flow.sh` | DRC, LVS, extraction, tapeout export, HRES check |
| `flow/crosscheck_canary.sh` | digital-image DRC/LVS and the HRES negative control |
| `flow/sim_core_support.py`, `flow/sim_bandgap.py` | POR, biasgen, bandgap and chain simulations |
| `distribution/generate_dist.py`, `sim_dist.py` | root, banks, `pt_bias_vref`: layout, DRC, LVS, simulations |
| `distribution/generate_ext.py` (`circuits_ext.py`) | `pt_bias_tap2`, `pt_refvcm`, `pt_txpad_bias` layout |
| `flow/summarize.py` | writes the evidence file; exits non-zero on an LVS failure |

## Open items

Risks: PWR-02, MOD-17, INT-04, PDN-08 (`spec/risk-register.md`).

- Bank rails with ten islands: the five banks and `bias_ext` as bound do not keep every bank and tap on its
  trunk diode's rail (interface row PC-5; proposal: all bank rails on the core rail).
- `pt_chip.conn` still names `pt_bias_ext` and binds `txpad_bias` with an `EN_TERM` pin and no detect pins; the
  published cells are `pt_bias_tap2` and `pt_txpad_bias` with `EN`, `EN_DET`, `IBIAS_DET`, `DETECT_PBIAS`.
  `IBIAS_DET` has no source yet.
- ATB leaves on the five trunk nodes (codes 14, 22, 29, 35, 56) are not gated by the rail of the bank that owns
  the trunk: a closed leaf with that rail off drives the bank diode into the dead rail (interface row PC-10).
- The bandgap's 71 µA at `ena` = 0 and the `vbg` enable overshoot are not in the evidence file or its criteria.
- Supply-trim point 3.50 V: only the POR, chain and overshoot rows above. The loop-gain, start-up and
  distribution campaigns and the three new cells have no 3.5 V point.
- Biasgen and bandgap extraction is capacitance only; bandgap PNP corner is tied to the MOS corner.
- POR safety sweeps (ramps, dips, power cycles) are schematic only; extracted runs cover the function window
  and the resistor × MIM rows.
- No mismatch or Monte Carlo on any cell. Consumers are modelled as ideal sources or NMOS diodes; trunk wire
  RC is not modelled.
- `pt_bias_tap2`, `pt_refvcm`, `pt_txpad_bias`: no LEF abstracts; results are not in the evidence file; the ×5
  detect mirror was not re-reviewed after the rebuild.
- The layout records of the root, the banks and `pt_bias_vref` carry generator hashes
  (`rf_tx/layoutlib.py`, `rf_tx/circuits.py`, for root and banks also `circuits_dist.py`) that differ from the
  current files. The published GDS and netlists match the evidence file.
- The Avalon standard-cell revision the upstream cells were drawn against is unknown; DRC and LVS are
  consistent with the pinned revision.
