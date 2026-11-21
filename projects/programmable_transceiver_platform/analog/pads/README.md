# IO pads

Custom pad cells for the wired, USB, reference/clock, RF and analog debug pins, plus the pad-attached
buffers and the TLP test site. Host-link, observe, ATB, supply and strap pads are unmodified provider cells
(`gf180mcu_fd_io`). No cell is silicon-qualified: every ESD figure below is a SPICE surrogate, not an HBM/CDM/TLP rating.
`pad_hspad` figures use R+C extraction with the ring model; the other published families' figures are
capacitance-only and are not evidence until their option-A rebuilds (section 8 item 1).

Operating conditions (`scratch/reviews/MANDATE.md` section 2): performance at 22–32 °C junction and
3.15–3.35 V; per-chip supply trim up to a 3.50 V setpoint for slow dies; safety at 0–3.63 V and 0–85 °C.

## 1. Pad set

Two chips (`pt_rf`, `pt_wired`), one cell library. Bindings are in `integration/chips/{common,rf/chip,wired/chip}.conn`,
sites in the per-chip bond maps (the generator resolves them with `design.resolve(chip=...)`), tiers from MANDATE
section 6. Each pad family has `PAD_P` on its first (lower-numbered) site; families are placed unmirrored. Supply and
ground bonds on signal sites are provider `dvdd` / `dvss` cells (`pad_xvdd_*`, `pad_xvss_*`; PC-35).

**`pt_rf`** (`integration/chips/rf/bond_map.txt`):

| Instance | Master | Pins and sites | HBM tier |
|---|---|---|---|
| `pad_bb_i` | `pad_rf_pair` | west: BB_I_P `inputs[11]`, BB_I_N `inputs[10]` | 2 kV |
| `pad_rf_rx` | `pad_rf_pair` | west: RF_RX_P `inputs[9]`, RF_RX_N `inputs[8]` | 2 kV |
| `pad_bb_q` | `pad_rf_pair` | west: BB_Q_P `inputs[7]`, BB_Q_N `inputs[6]` | 2 kV |
| `pad_rf_tx` | `pad_rftxpad` | west: RF_TX_P `inputs[1]`, RF_TX_N `inputs[0]` | 1 kV |
| `pad_por_bypass` | provider `gf180mcu_fd_io__in_c` (strap) | east: POR_BYPASS `bidir[16]` | provider cell |
| `pad_ref` | `pad_refpad` | east: REF_IN `bidir[20]`, REF_IN_N `bidir[21]` | 2 kV |
| `pad_aux_clk` | `pad_refpad` | east: AUX_CLK_P `bidir[23]`, AUX_CLK_N `bidir[24]` | 2 kV |

**`pt_wired`** (`integration/chips/wired/bond_map.txt`):

| Instance | Master | Pins and sites | HBM tier |
|---|---|---|---|
| `pad_wmon` | `pad_single_leg` | west: WMON `inputs[9]` | 2 kV |
| `pad_tlp` | `pad_tlp_flat` | west: TLP_TEST `inputs[7]` | test site |
| `pad_por_bypass` | provider `gf180mcu_fd_io__in_c` (strap) | west: POR_BYPASS `inputs[5]` | provider cell |
| `pad_ref` | `pad_refpad` | west: REF_IN `inputs[3]`, REF_IN_N `inputs[2]` | 2 kV |
| `pad_hs_rx` | `pad_hspad` | east: WIRE_RX_P `bidir[14]`, WIRE_RX_N `bidir[15]` | 2 kV |
| `pad_aux_clk` | `pad_refpad` | east: AUX_CLK_P `bidir[16]`, AUX_CLK_N `bidir[17]` | 2 kV |
| `pad_usb` | `pad_wirepad` | east: USB_DP `bidir[18]`, USB_DN `bidir[19]` | 2 kV |
| `pad_wire_tx` | `pad_txpad` | east: WIRE_TX_P `bidir[20]`, WIRE_TX_N `bidir[21]` | 1 kV |
| `pad_wtx_ext` | `pad_rf_pair` | east: WTX_EXT_P `bidir[23]`, WTX_EXT_N `bidir[24]` | 2 kV |

CDM requirement: 2 A surrogate with the east-edge ring decap (PC-37, PC-45); 250 V on silicon is not verified. Nothing is below 500 V HBM. Board TVS on the antenna and
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
| `pad_hspad` | `stress-safe-families/wired-receive-hs/` | 492 × 912.91 | 449,202 bbox | 554 (404) | `DVDD VSS VDD TERM_VCM TERM_ENABLE TERM_TRIM0..3 VBIAS RX_P RX_N PAD_P PAD_N` |
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
| `pad_hspad` (GDS sha 07b6800d…; hashes in `pc47-hspad-a6.json`) | `geometry.json`, `layout-screen.json`, `independent-device-audit.json`, `site-primary.json`, `lu.json`, `pad_hspad-kldrc.json`, `pad-lvs.txt`, `pc47-hspad-a6.json`, models `physical-r-{low,typ,high}[-rail].spice` |
| `pad_wirepad` (GDS sha 4e4b9d92…) | `placement-layout.json`, `layout-screen.json`, `model-audit.json`, `lu.json`, `pad_wirepad-kldrc.json`, `combined-lvs.txt`, `pd47-usb-ls-miller.json`; 1 kV HBM and CDM surrogate in `../pd48-esd-tiering.json` key `pd48c` |
| `pad_txpad`, `pad_refpad`, `pad_rf_pair` | folder layout/audit/kldrc files; safe/HBM runs in `../pd13-family-sims.json` (model sha matches); 1 kV runs for txpad and rftxpad in `../pd48-esd-tiering.json` key `family` |

Files in `wired-receive-usb/` named `pd28-*` were produced on other
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

### `pad_hspad` (`pc47-hspad-a6.json`; resistance-aware models `physical-r-{low,typ,high}[-rail].spice`)

Pad-site primary diodes at the bond pad to the ring rails (`pad_site_primary.py`: 5 down to VSS, 5 up to `DVDD` per
leg), secondary diodes at the termination / receiver node (1 × 1 µm, outer p-sub ring contacted to VSS), no core
protection array. New port `DVDD` (first port of `hs_protected_pad`): the ring supply of the pad-site up-diodes and
the secondaries; it must be connected to the provider ring supply at the site. `physical.spice` is the
capacitance-only extraction and is NOT valid for termination, receive loss or ESD: simulate with
`physical-r-typ.spice` and bound with `-low` / `-high`; the `-rail` variants add the provider rail cell above the
cell (206 fF per leg PAD to VSS) and are the ones for return loss and pad capacitance. Corners: tt / ss / ff / sf / fs,
22 and 32 °C, 3.15 and 3.35 V, ss also at 3.50 V (23 corners).

| Quantity | Typical metal | High-resistance metal | Limit |
|---|---|---|---|
| Code giving 100 Ω differential | 5.0 (ff) … 10.0 (ss); tt 7.1 | 6.3 … 11.6; tt 8.7 | code 2 … 13 |
| Termination at the best code, all corners | 96.3–103.0 Ω | 97.2–103.1 Ω | 95–105 Ω |
| Per-leg P − N at that code | 0.36 Ω | 0.33 Ω | ≤ 1.0 Ω |
| One code for all in-window corners | code 8: 81.1–113.1 Ω | code 9: 85.1–114.9 Ω | 80–120 Ω (low metal code 7: 80.2–114.7 Ω) |
| Receive path loss, bond pad to `RX_P/N` | 1.23–1.32 dB | 1.75–1.88 dB | (0.9–1.0 dB low metal) |
| Pad capacitance per leg, with rail | 1.331–1.355 pF | 1.288–1.306 pF | 1.15 pF budget: MISS (low metal 1.37–1.40 pF) |
| P / N imbalance | 5.5 fF | | ≤ 20 fF |
| Die return loss at 2.4 GHz, with rail | 6.91–7.22 dB | 7.23–7.49 dB | WR-SATA2-RL: recorded fail |
| Die return loss minimum, 0.1–1.25 GHz, with rail | 11.7–12.1 dB | 12.1–12.4 dB | |
| Return loss through the chip-on-board channel, 1.25–2.5 GHz, with rail | 5.34–5.37 dB | 5.49–5.56 dB | package-limited |
| HBM 2 kV, switch gates | 5.12 V | 5.26 V | 8.0 V transient |
| CDM 2 A with 1 nF at the far ring node, gates | 6.72 V | 7.31 V | 8.0 V |
| Receiver input (`RX`, 6 V oxide), HBM / CDM 2 A | 4.69 / 4.11 V | | 8.0 V (5.0 V at the 3.3 V requirement points: PASS) |
| Worst reverse junction, CDM 2 A high metal | 10.73 V (site nd2ps) | | bv 11 V |
| MIM; pad to rail HBM | 5.18 V; 5.90 / 6.79 V | | 6.0 V; 8.0 V |

CDM with the PC-45 site decap (1 nF at 0.7 Ω on each rail from the site, ring resistance at the stated bound, high metal;
`scratch/pads-core/esdopt/ring/REPORT.md`): CDM 2 A all ten cases gate ≤ 6.52 V, RX ≤ 4.52 V, MIM ≤ 4.77 V, primary
reverse ≤ 9.96 V, primary diode 7.2 mA/µm forward / 0.05 mA/µm avalanche: PASS. CDM 1 A pad-to-pad 4.45 V gate, HBM 2 kV
pad-to-pad 4.90 V gate: PASS. CDM 3 A pad-to-pad (beyond the 2 A requirement) misses on RX 5.42 V, MIM 6.62 V and diode
current density 10.5 / 1.12 mA/µm.

Conditions of the publication (independent review `scratch/pads-core/esdopt/hs/review-a6b/REVIEW.md`, GO with conditions):
1. **PC-45:** ≥ 1 nF of decap within 0.7 Ω (including its ESR) of each east wired site, on `DVDD` / VSS. The CDM
   evidence is void without it; verify on the assembled GDS before tapeout.
2. TLP / vf-TLP of the primary site diodes (the current-density rating is a literature figure).
3. CDM headroom is thin: 2 A is the requirement, 3 A misses.
4. WR-SATA2-RL: die return loss stays a recorded fail.

Pins and outline are unchanged apart from `DVDD`: RX_P and RX_N on Metal5, adjacent on the side edge (x = 492),
6 µm apart. Trim reset code: not fixed by the a6 evidence (single-code rows: 7 / 8 / 9 for low / typical / high
metal). The receiver common mode comes from `VBIAS` through the coupling MIM. Termination units: 10 base (2 × 2.6 µm poly + 20/0.7 switch) and 15 trim (2 × 1.0 µm +
12/0.7) per leg. Not in any model: ss / ff / hot ESD, low-metal ESD, per-finger current density outside the primary
diodes, ring resistance beyond the stated bound.

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
| Wire resistance, inductance per bond | 0.21–0.28 Ω (aluminium); per-bond values in `spec/package-channel-{rf,wired}.json` | `scratch/reviews/pads-core/wire-table.md` |
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
3. Failure current per um of perimeter of the site diode (It2 at 100 ns and VF-TLP at 1-5 ns): it replaces the literature
   assumption (10 mA/um forward, 1 mA/um avalanche, `spec/design-assumptions.md`) that judges every pad's primary diodes.
4. Extract on-resistance and turn-on voltage per diode string, to calibrate the pad-to-rail and diode models
   behind every HBM surrogate here. The riser adds about 0.2 Ω (nominal sheet resistance) to the measured
   on-resistance.

## 7. Flow

```sh
# family layouts (compact flow); <macro> = generated/stress-safe-families/network-gc or network-gc-d2
python3 stress_safe_compact_layout.py {reference_clock|wired_transmit|wired_receive_usb} <work> <macro> [usbfix6v2lsm 14]
python3 hs_leg_layout.py <work dir>                            # pt_hs_leg master (--legacy: the first published leg)
python3 rextract/netres.py --gds <gds> --top <cell> --spec <spec.json> --out <json>   # metal / via resistance; then rextract/make_rmodel.py
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
python3 rail_site_check.py --family all                                # family ON the provider rail cell at its mask-snapped site: precheck main + antenna (--selftest must pass)
python3 -m unittest discover -s . -p test_design.py
```

Environment: `env/pad-environment.json`. `extract_audit.py` reads device and body connectivity independently
of the stock converter. Read-back LVS uses `scratch/integration/signoff-gap/lvs/rb_lvs.py`. Do not add
budget-sized ideal capacitors on top of extracted capacitance.

## 8. Open items

1. **ESD paths of every custom pad family (`scratch/reviews/pads-core/ESD-METAL.md`).** With metal and via resistance
   extracted there are 23–32 Ω (typical) between each bond pad and its primary diodes and 56–85 Ω around the
   discharge loop, confirmed by hand calculation, Magic `extresist` and a separate solver on all seven families. No
   family meets its HBM tier; every HBM / CDM number in section 4 except the `pad_hspad` rows is capacitance-only and
   is not evidence. Decided fix (PC-27): primary diodes at the bond pad tied to the ring rails, all families; back-feed is
   accepted and sequenced by the board (`spec/board-requirements.md` B53). `pad_hspad` is published with it (a6, PC-47,
   conditions in section 4); `pad_txpad` a4 in evidence under `scratch/pads-core/esdopt/`; the other five families not started.
   `RF_TX` gets no diode to the supply (it swings above it). (PAD-11)
2. **`pad_txpad` and `pad_wirepad` signal paths.** `pad_txpad` termination is 287 Ω differential at tt with metal
   resistance (92 Ω without), 16–19 Ω sit between the bond pad and the output cascodes, and the termination is
   untrimmed (152 / 58 Ω at ss / ff even without metal): `scratch/pads-core/txr/STATUS.md`. `pad_wirepad` has about
   81 Ω of metal in series with its 45 Ω HS termination (survey only). Neither is fixed. Resistance-aware extraction
   is mandatory for all pad evidence from now on (`rextract/`).
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
8. **LNA ground and RF input.** The LNA ground is die VSS on the standard fingers; there is no AGND_RX pad and no
   ground-pad generator. RF_RX sits on bonds 68/67 and BB_I on 70/69 (PC-26 decided, PC-29): bond model and numbers
   in `scratch/reviews/pads-core/LNA-GROUND.md`.
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
14. **Pad on the provider rail cell (SO-1).** `rail_site_check.py`: every published family except `pad_tlp` fails the
    precheck main deck on the rail cell, 66 Via3 / Via4 items per bond site (V3.1, V3.2a, V4.1, V4.2a), all at the shell's
    own VSS ring stacks; the families' bond openings sit exactly on the template frame (no offset at site level). The
    pad-site-diode rebuilds delete those stacks and pass (antenna 0 everywhere).
15. **Flow.** The pads layout image `sha256:9253a51f…` is absent from the build machine, so
    `run_first_pass.py` LVS cannot run there; `packaging-audit.json` predates the current bond map;
    `termination_buffer_array_layout.py` has an uncommitted edit of unknown origin. Buffer electromigration
    ratios have no published evidence file. (MOD-05)
