# IO pads

Custom pad cells for the wired, USB, reference/clock, RF and analog debug pins, plus the pad-attached
buffers and the TLP test site. Host-link, observe, ATB, supply and strap pads are unmodified provider cells
(`gf180mcu_fd_io`). No cell is silicon-qualified: every ESD figure below is a SPICE surrogate on the extracted
netlist (capacitance-only extraction), not an HBM/CDM/TLP rating.

Operating conditions (`scratch/reviews/MANDATE.md` section 2): performance at 22–32 °C junction and
3.15–3.35 V; per-chip supply trim up to a 3.50 V setpoint for slow dies; safety at 0–3.63 V and 0–85 °C.

## 1. Pad set

Bindings are from `integration/top/pt_chip.conn`, sites from `spec/contract.json`
`assembly_policy.bond_map_current`, tiers from MANDATE section 6.

| Instance | Master | Pins | Site | HBM tier |
|---|---|---|---|---|
| `pad_rf_rx` | `pad_rf_pair` | RF_RX_P/N | west `inputs[11]`/`[10]` | 2 kV |
| `pad_bb_i`, `pad_bb_q` | `pad_rf_pair` | BB_I_P/N, BB_Q_P/N | west `inputs[9..6]` | 2 kV |
| `pad_aux_clk` | `pad_refpad` | AUX_CLK_P/N (external-LO Q leg, auxiliary clock, forwarded wire clock) | west `inputs[5]`/`[4]` | 2 kV simulated (1 kV allowed) |
| `pad_ref` | `pad_refpad` | REF_IN, REF_IN_N (reference, external-LO I leg) | west `inputs[3]`/`[2]` | 2 kV simulated (1 kV allowed) |
| `pad_rf_tx` | `pad_rftxpad` | RF_TX_P/N | west `inputs[1]`/`[0]` | 1 kV |
| `pad_hs_rx` | `pad_hspad` (mirrored) | WIRE_RX_P/N | east `bidir[15]`/`[14]` | 2 kV |
| `pad_por_bypass` | provider `gf180mcu_fd_io__in_c` | POR_BYPASS strap | east `bidir[16]` | provider cell |
| spare | provider `bi_24t`, bonded | none | east `bidir[17]` | provider cell |
| `pad_usb` | `pad_wirepad` | USB_DP/DN | east `bidir[19]`/`[18]` | 2 kV |
| `pad_wire_tx` | `pad_txpad` (mirrored) | WIRE_TX_P/N | east `bidir[21]`/`[20]` | 1 kV |
| `pad_wtx_ext` | `pad_rf_pair` | WTX_EXT_P/N | east `bidir[22]`/`[23]` | 2 kV |
| `pad_wmon` | `pad_single_leg` | WMON | east `bidir[24]` | 2 kV |
| `pad_tlp` | `pad_tlp_flat` | TLP_TEST | east `bidir[25]` | test site |

CDM target is ≥ 250 V chip-wide and is not verified. Nothing is below 500 V HBM. Board TVS on the antenna and
USB connectors is mandatory (`spec/board-requirements.md` B36, B46; B47, B48 for the other connectors and
handling). `VCM` of both `pad_refpad` instances comes from `pt_refvcm` (`analog/core_support`).

There is no WCLK_IN pad pair (the forwarded wire clock uses AUX_CLK), no ESD_TEST pad, no LNA source pads and
no AGND_RX pad: the LNA ground is die VSS.

## 2. Published cells

All under `generated/`. Every cell: Magic DRC 0, netgen LVS unique, independent device audit match
(`extract_audit.py`), KLayout precheck main 0 / antenna 0 with a record whose sha matches the GDS
(`verification/check_block_kldrc.py`: CLEAN for all eight pad blocks).

| Cell (top) | Folder | Outline (µm) | Area (µm²) | Devices (MOS) | Ports |
|---|---|---|---|---|---|
| `pad_hspad` | `stress-safe-families/wired-receive-hs/` | 492 × 912.91 | 449,202 bbox | 508 (404) | `VSS VDD TERM_VCM TERM_ENABLE TERM_TRIM0..3 VBIAS RX_P RX_N PAD_P PAD_N` |
| `pad_wirepad` | `stress-safe-families/wired-receive-usb/` | 2.78..524 × 0..1434.72 | 316,021 allocated (ceiling 340,000) | 739 (615) | `PAD_P PAD_N VDD VSS TERM_VCM TERM_ENABLE DIFF_ENABLE DIV_ENABLE BYPASS_ENABLE RX_P RX_N HS_PBIAS HS_P HS_N FS_HIGH_P/N FS_LOW_P/N PULLUP_P/N PULLDOWN_P/N TERM_TRIM0..2 LS_SLOW ATB_ESD_RAIL` |
| `pad_txpad` | `stress-safe-families/wired-transmit/` | 2.78..484 × 0..1226.72 | 282,862 allocated (ceiling 300,000) | 595 (536) | `PAD_P PAD_N VDD VSS CASCODE MAIN_P/N MAIN_BIAS POST_P/N POST_BIAS TMDS_P/N TMDS_BIAS DETECT_ENABLE DETECT_PBIAS TERM_ENABLE TERM_VCM ATB_ESD_RAIL` |
| `pad_refpad` | `stress-safe-families/reference/` | 2.78..404 × 0..912.91 | 176,476 allocated (ceiling 185,000) | 404 (348) | `PAD_P PAD_N VSS VCM ATB_ESD_RAIL` |
| `pad_rf_pair` | `stress-safe-families/rf-pair/` | 310 × 912.91 | 176,900 allocated | 388 (348) | `PAD_P PAD_N VSS ATB_ESD_RAIL` |
| `pad_rftxpad` | `stress-safe-families/rf-tx/` | 310 × 912.91 | 176,900 allocated | 388 | `PAD_P PAD_N VSS ATB_ESD_RAIL` |
| `pad_single_leg` | `stress-safe-families/single-leg/` | 302.14 × 912.91 | 157,853 allocated | 388 | `PAD_P VSS ATB_ESD_RAIL` |
| `pad_tlp_flat` | `tlp-site/` | 68 × 124.34 | 8,455 bbox | 8 diodes | `PAD VSS VDD` |
| `tx_steering_buffer_flat` | `steering-buffer-compact/` | 54.58 × 158.98 | 8,677 bbox | 128 | `VDD VSS IN OUT` |
| `buffer_compensated_flat` | `termination-buffer-candidate/compact-array/` | 156.8 × 479.57 | 75,196 bbox | 282 | `VDD VSS REF BIAS OUT ENABLE` |

The extracted netlists also expose the isolated `ESD_RAIL`. The published `pad_rf_pair` and `pad_rftxpad`
extracted netlists are identical (same sha256). LVS references for hspad, wirepad, txpad and refpad are
`<folder>/lvs-reference.spice` (`lvs_reference.py`; regenerate after republishing a family).

Evidence files that belong to the published netlists:

| Cell | Files |
|---|---|
| `pad_hspad` (GDS sha 5b7c598e…, model 320c43d9…) | `geometry.json`, `layout-screen.json`, `independent-device-audit.json`, `lu.json`, `pad_hspad-kldrc.json`, `pad-lvs.txt`, `ap4-hspad-*.json` |
| `pad_wirepad` (GDS sha 4e4b9d92…) | `placement-layout.json`, `layout-screen.json`, `model-audit.json`, `lu.json`, `pad_wirepad-kldrc.json`, `combined-lvs.txt`, `pd47-usb-ls-miller.json`; 1 kV HBM and CDM surrogate in `../pd48-esd-tiering.json` key `pd48c` |
| `pad_txpad`, `pad_refpad`, `pad_rf_pair` | folder layout/audit/kldrc files; safe/HBM runs in `../pd13-family-sims.json` (model sha matches); 1 kV runs for txpad and rftxpad in `../pd48-esd-tiering.json` key `family` |

Files in `wired-receive-hs/` named `pd21-*` and in `wired-receive-usb/` named `pd28-*` were produced on other
netlists and are not evidence for the published cells; no flow reads them.

## 3. Protection foundation

Shared by every family (`circuits.py:foundation_devices`, `protection_network_ss.py`, `rftx_shunt.py`):

- Per pad: 4 + 4 primary steering diodes to VSS and to an isolated `ESD_RAIL`; `ATB_ESD_RAIL` tap.
- Rail clamp: gate-coupled `nfet_06v0` bank from `ESD_RAIL` to VSS with two 90 × 90 µm coupling MIMs
  (`rftx_shunt.py`), plus the RC clamp with a 14 µm timing MIM (`protection_candidate.CLAMP_CAPACITORS`).
- `network-gc-d2` (hspad, wirepad): one extra pad-to-rail diode row per leg (`protection_array.py`
  `extra_up_rows=1`).
- Latch-up: `lu.json` per cell reports 0 µm² of n-diffusion farther than 15 µm from a p-tap and every
  p-diffusion inside a closed n+ ring (hspad, wirepad, steering buffer). (LU-01)

## 4. Verified numbers

Gate screens: DC 3.63 V (3.3 V devices) / 6.0 V (6 V devices); for ~150 ns events the transient limits 5.0 V /
8.0 V from `spec/design-assumptions.md`. HBM-like source: 2 kV = 1.33 A, 1 kV = 0.67 A.

### `pad_hspad` (`ap4-hspad-*.json`; model without metal resistance, see Open items 1)

| Quantity | Value |
|---|---|
| Safe / HBM 2 kV, 18 runs | 0 of 404 MOS over the screen; pad peak ≤ 5.41 V |
| HBM 1 kV | 0 of 404; pad peak ≤ 4.67 V |
| CDM-speed surrogate, 1 ns | pad 4.80 / 6.98 / 9.03 V at 1 / 2 / 3 A (over the 8.0 V limit at 3 A) |
| C per leg at the trimmed codes (tt 6 / ss32 9 / ff22 2) | 1.134–1.156 pF; P/N difference 15.3 fF |
| Die return loss 1.2–2.4 GHz at those codes | 7.85–8.37 dB minimum |
| Differential termination at those codes, 100 MHz | 94.2–105.4 Ω |
| RX path (pad to RX) | high-pass corner 0.67–1.07 MHz; loss 0.30–0.41 dB at 10 MHz |
| Pins | RX_P and RX_N on Metal5, adjacent on the side edge (x = 492), 6 µm apart; all other core pins on the same edge |

`TERM_VCM` is 0.3–0.5 V. The receiver common mode comes from `VBIAS` through the 4.9 pF coupling MIM
(2 × 35 × 35 µm per leg), not from the termination.

### `pad_wirepad` (USB; `pd47-usb-ls-miller.json`)

| Quantity | Value |
|---|---|
| Safe / HBM 2 kV | 0 of 615 MOS over the screen in pulse, HBM and peer runs; pad peak ≤ 5.41 V; 4 devices at exactly 3.63 V in the slow supply ramp |
| HS termination (trim codes tt 4 / ss 7 / ff 0) | 44.2–47.6 Ω |
| HS current delivered | 16.9–18.2 mA (target 17.78 mA) |
| LS edges (`LS_SLOW` = 1, 50 and 450 pF, HS reference ±5 %) | 94.7–201 ns |
| FS edges, 50 pF | 5.9–11.3 ns, rise/fall ratio 0.96–1.23 (USB-01) |
| Pad C, bypass on or off, with RX loads | 2.08–3.37 pF against a 5.0 pF USB budget |

Rules for the controller: `LS_SLOW` must be 0 whenever the termination or HS is used; change it only with the
driver off; LS needs the HS bias enabled. `HS_PBIAS` is a VSS-referenced gate voltage from `wtx_idac`. The HS
level at ss/32 °C reaches 400 mV only from about 3.33 V upward (interface-changes row PC-13). (USB-02, PAD-03)

### `pad_txpad`, `pad_rftxpad`, `pad_refpad`, `pad_rf_pair`

| Cell | Result | File |
|---|---|---|
| `pad_refpad`, `pad_rf_pair` | HBM 2 kV: 0 of 348 MOS over the screen, pad 6.18–6.91 V; ±100 mA pulse 2.51–2.77 V | `pd13-family-sims.json` |
| `pad_rftxpad` | HBM 1 kV: 0 of 348, pad 4.52–4.70 V | `pd48-esd-tiering.json` |
| `pad_txpad` | HBM 1 kV: pad 4.52–4.70 V; 8 termination `nfet_03v3` of 536 MOS are over the 3.63 V DC screen and inside the 5.0 V transient limit. At 2 kV: 25 exceedances (ESD-05, risk-accepted) | `pd48-esd-tiering.json`, `pd13-family-sims.json` |
| Consumer gates on pad nets (`hbm_core_screen.py`) | 0 exceedances of the transient limits in all cases at the tier level; worst gate 4.72 V (LNA, 2 kV), 5.42 V (6 V devices on AUX_CLK), 4.18 V (rfdriver, 1 kV). The same screen fails at 3 kV (188–302 exceedances) | `pd48-esd-tiering.json` key `core_screen` |

### POR_BYPASS strap (`scratch/reviews/pads-core/STRAP.md`)

Provider `in_c` with `PD` hard-tied to VDD and `PU` to VSS, `Y` to `digital.por_bypass`; no custom layout.
Pull-down 105–157 kΩ; unbonded pad at 5–16 µV; input threshold 0.99–1.27 V; 2.55 µA needed to lift the pad to
0.4 V and 6.9 µA to flip `Y` (2.5× and 6.9× a 1 µA external leak). `Y` does not move on supply ramps of
10 µs or slower, also with only 0.2 pF on the pad. Setting the strap: tie the pad to the die supply (20–35 µA;
any source below about 10 kΩ). Board rules B49 and B51. (PWR-02)

### Supply-pad clamps (`scratch/reviews/pads-core/CLAMP.md`)

The provider `dvdd` / `dvss` / `cor` RC clamps (360 kΩ × MOS capacitor, time constant 1.14–2.09 µs) turn fully
on, about 1 A per cell, on a fast full-swing supply ramp: the fastest clean slew is 0.91 V/µs, the slowest
firing slew 1.04 V/µs. **Board rule: die-supply
dV/dt ≤ 0.3 V/µs at any point of any rise (0 → 3.63 V in ≥ 12 µs), no hot-plug.** Steps of up to 1.5 V in
100 ns on a settled rail do not fire the clamps.

### Pad-attached buffers

| Cell | State |
|---|---|
| `tx_steering_buffer_flat` | DRC 0, device graph match on the GDS round trip, KLayout 0 / 0, latch-up audit clean (`layout.json`, `lu.json`) |
| `buffer_compensated_flat` | DRC 0, device graph match, KLayout 0 / 0; enable-to-ready 40.8 ns (tt) to 183.6 ns (ss/22 °C/3.15 V) in `readiness-settle.json` |

Electromigration screen for both: `verification/em_check.py`, `em_strap_ladder.py`, `em_strap_post.py`.

## 5. Packaging

wafer.space chip-on-board only: 14 × 16 mm board, 74 fingers, ground paddle, 70-pin mezzanine connector. One
fixed 74-wire bond layout, one wire per template pad; 0.8 mil aluminium wire; die about 250 µm thick. The
board carries eight 1 µF capacitors, one per supply finger net, and nothing on signal pins
(`scratch/reviews/wafer-space-answers.md`).

| Item | Value | Source |
|---|---|---|
| Assembly | `generated/packaging-assembly.gds`, 3932 × 5122 µm, 74 bond openings on the provider template sites, native seal ring | `generated/packaging-audit.json` |
| Supplies | 8 supply and 10 ground bonds; the ring joins all supply bonds into one net and all ground bonds into another: use one common external supply | `spec/contract.json` `packaging_gate` |
| Bond plan length, finger-centre landing | 2.197–2.991 mm (limit < 3 mm), maximum angle 38.7° (limit 45°), no crossing | `scratch/reviews/pads-core/BOND-AUDIT.md` |
| Near-end landing | maximum 2.665 mm, 44.0° | same |
| Wire resistance, inductance per bond | 0.21–0.28 Ω (aluminium); per-bond values in `spec/package-channel.json` | `scratch/reviews/pads-core/wire-table.md` |
| Ring rails through custom pads | DVDD, DVSS, VDD, VSS continuous at full width on Metal3–5 through every custom family | `scratch/reviews/pads-core/RAIL-CONTINUITY.md` |

`generated/packaging-audit.json` (`packaging_audit.py`) carries the signal names of an earlier bond map; its
geometry is the current one.

## 6. TLP site and measurement plan

`pad_tlp_flat` (`tlp_site.py --output-dir <dir>`): one native bond pad with one leg's primary steering diodes
(4 × `nd2ps` PAD→VSS, 4 × `pd2nw` PAD→VDD). The pad riser is Metal2 only, so the cell sits over the provider
rail cell without touching the ring (no Metal3–5 in the rail band). Read-back LVS 8/8 unique.

Assembly: strap the left VSS bar (the diode anodes; it carries the VSS port), preferably both bars, to ring
DVSS. The VDD bar leaves on Metal2 at x 69–75; its strap resistance enters the "VDD grounded" measurements.

Measurement plan:

1. TLP 100 ns / 10 ns rise, PAD against a ring-VSS probe pad, both polarities, with VDD grounded and with VDD
   floating, in 0.05 A steps to It2. Failure criterion: leakage at 3.3 V above 10× the pre-stress value or
   above 1 µA.
2. VF-TLP 1–5 ns (CDM speed) to 3 A.
3. Extract on-resistance and turn-on voltage per diode string, to calibrate the pad-to-rail and diode models
   behind every HBM surrogate here. The riser adds about 0.2 Ω (nominal sheet resistance) to the measured
   on-resistance.

## 7. Flow

```sh
# family layouts (compact flow); <macro> = generated/stress-safe-families/network-gc or network-gc-d2
python3 stress_safe_compact_layout.py {reference_clock|wired_transmit|wired_receive_usb} <work> <macro> [usbfix6v2lsm 14]
python3 hs_leg_layout.py <work dir>                            # pt_hs_leg master
python3 hs_pad_compose.py <work> <shell dir> <leg dir> <network dir> --stacked
python3 tlp_site.py --output-dir <dir>
python3 steering_buffer.py --compact --output-dir <dir>
python3 termination_buffer_array_layout.py --output-dir <d>/core
python3 termination_compensation_layout.py --output-dir <d>/comp --core-dir <d>/core --mim-dir generated/termination-buffer-compensation-mim
python3 lvs_reference.py                                       # LVS references after a republish

# simulations (image svalbard/transceiver-pad-sim:ngspice47-corrected, env/build_sim_image.sh)
python3 stress_safe_family_sims.py --output-dir <dir> --report <json>     # HBM_KV=1 for the 1 kV tier
python3 hbm_core_screen.py <case> ...                                     # consumer gates on pad nets

# checks
python3 ../../verification/check_block_kldrc.py                           # precheck records against GDS sha
python3 -m unittest discover -s . -p test_design.py
```

Environment: `env/pad-environment.json`. `extract_audit.py` reads device and body connectivity independently
of the stock converter. Read-back LVS uses `scratch/integration/signoff-gap/lvs/rb_lvs.py`. Do not add
budget-sized ideal capacitors on top of extracted capacitance.

## 8. Open items

1. **`pad_hspad` termination resistance.** The extraction is capacitance-only, so no bench sees the `TERM_VCM`
   metal between the two legs' termination common points (1 µm Metal4 trunk, single Via3 cuts). Estimated
   34–44 Ω typical, 60–70 Ω at the high-resistance corner: differential termination about 142 Ω at tt code 5
   instead of 100 Ω, and 100 Ω is out of trim range at ss. Every termination and return-loss number in
   section 4 is therefore without metal resistance. A leg fix (uncommitted edits in `hs_leg_layout.py`,
   `hs_pad_compose.py`; `scratch/pads-core/hsfix/STATUS.md`) and a resistance-aware rerun are in flight, not
   reviewed, not published. (WRX-04)
2. **Pad-to-diode metal resistance in the shared shell.** The same in-flight tool reports 16–17 Ω typical
   between the bond pad and the termination heads, most of it in the shell (single Via4). Unconfirmed; if
   confirmed it affects the HBM evidence of every family. Resistance-aware extraction is needed for all pad
   families.
3. **CDM.** 250 V is a target only; die capacitance and CDM current are estimates.
4. **Supply-clamp events.** Survivability of a fired clamp and the hot-plug waveform are not shown. The slew
   rule is in MANDATE section 6 and interface-changes row PC-16; it is not yet a row of
   `spec/board-requirements.md`.
5. **ESD implant layer 24/0.** It may not be in the wafer.space mask set. No custom or provider cell draws it
   (census in `scratch/reviews/pads-core/wafer-space-consequences.md` section 6), so its absence changes
   nothing as drawn; written confirmation is outstanding.
6. **Bond plan.** A 0.1 mm die placement shift breaks the 3 mm rule (centre landing) or the 45° rule
   (near-end landing) on the corner-adjacent bonds; the 3-D wire length for a 250 µm die is about 3.05 mm on
   bonds 18/37/55/74. The landing rule is not chosen.
7. **Bond tester.** A positive-current continuity test would read open on the custom pads that steer into the
   isolated rail; the tester polarity is not known.
8. **LNA ground.** No AGND_RX pad exists. `integration/top/pt_chip.conn` still instantiates
   `pad_agnd_rx_{0:1}` (`pad_downbond`). The runner-up (ground site 71 on its own net, untracked
   `agnd_pad.py`) is unreviewed and unpublished.
9. **Consumer-gate HBM screen is stale.** `pd48-esd-tiering.json` `core_screen` was run on consumer netlists
   of its date, including an unpublished LNA and the deleted forwarded-clock receiver; rerun after the
   consumers settle. (ESD-02, ESD-06)
10. **3.5 V trim point.** HS/USB termination tables, USB FS/LS crossover and TX pad compliance are not rerun
    at 3.50 V.
11. **AUX_CLK on `pad_refpad`.** The 25–810 MHz forwarded-clock receiver bench and the external-LO Q leg on
    the refpad are not run. (PKG-05, IQ-03)
12. **Not built:** `ATB_ESD_RAIL` observation leaves (the port is unconnected at the top); LEF abstracts;
    the ESD-row and debug-pad area items; back-drive checks of consumer pins with the pad's island off.
13. **`pad_rf_pair` area.** `rf-pair/pad-layout.json` records `fits_assigned_area: false` against a
    130,000 µm² ceiling.
14. **Flow.** The pads layout image `sha256:9253a51f…` is absent from the build machine, so
    `run_first_pass.py` LVS cannot run there; `packaging-audit.json` predates the current bond map;
    `termination_buffer_array_layout.py` has an uncommitted edit of unknown origin. Buffer electromigration
    ratios have no published evidence file. (MOD-05)
