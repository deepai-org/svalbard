# IO pads

Custom pad cells for the wired, USB, reference/clock, RF and analog debug pins, plus the pad-attached
buffers and the TLP test site. Host-link, observe, ATB, supply and strap pads are unmodified provider cells
(`gf180mcu_fd_io`). No cell is silicon-qualified: every ESD figure below is a SPICE surrogate, not an HBM/CDM/TLP rating.
`pad_hspad`, `pad_txpad` and `pad_refpad` figures use R+C extraction with the ring model; the other published families'
figures are capacitance-only and are not evidence until their option-A rebuilds are published (section 8 item 1).

Operating conditions (`scratch/reviews/MANDATE.md` section 2): performance at 22–32 °C junction and
3.15–3.35 V; per-chip supply trim up to a 3.50 V setpoint for slow dies; safety at 0–3.63 V and 0–85 °C.

## 1. Pad set

Two chips (`pt_rf`, `pt_wired`), one cell library. Bindings are in `integration/chips/{common,rf/chip,wired/chip}.conn`,
sites in the per-chip bond maps (the generator resolves them with `design.resolve(chip=...)`), tiers from MANDATE
section 6. Each pad family has `PAD_P` on its first (lower-numbered) site; families are placed unmirrored. `pad_hspad` is 492 um wide (two sites plus 70 um), so the site after it must hold a provider cell, never another custom family. Supply and
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
| `pad_aux_clk` | `pad_refpad` | west: AUX_CLK_P `inputs[5]`, AUX_CLK_N `inputs[4]` | 2 kV |
| `pad_ref` | `pad_refpad` | west: REF_IN `inputs[3]`, REF_IN_N `inputs[2]` | 2 kV |
| `pad_hs_rx` | `pad_hspad` | east: WIRE_RX_P `bidir[14]`, WIRE_RX_N `bidir[15]` | 2 kV |
| `pad_por_bypass` | provider `gf180mcu_fd_io__in_c` (strap) | east: POR_BYPASS `bidir[16]` | provider cell |
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
| `pad_hspad` | `stress-safe-families/wired-receive-hs/` | 492 × 912.91 | 449,202 bbox | 554 (404) | `DVDD VSS VDD TERM_VCM TERM_ENABLE TERM_TRIM0..3 VBIAS RX_P RX_N PAD_P PAD_N`; all top-edge pins (y 912.91, Metal4 x 418-459, PAD_P/N Metal5) except DVDD (ring landing) |
| `pad_wirepad` | `stress-safe-families/wired-receive-usb/` (`combined.gds`) | 2.78..384.18 × 0..1434.72 | 547,212 bbox | 371 | `PAD_P PAD_N VDD VSS TERM_VCM TERM_ENABLE DIFF_ENABLE DIV_ENABLE BYPASS_ENABLE RX_P RX_N HS_PBIAS HS_P HS_N FS_HIGH_P/N FS_LOW_P/N PULLUP_P/N PULLDOWN_P/N TERM_TRIM0..2 LS_SLOW DVDD` |
| `pad_txpad` | `stress-safe-families/wired-transmit/` (`combined.gds`) | 286 × 699.76 | 200,135 bbox | 409 (346) | `PAD_P PAD_N VDD VSS DVDD_P DVDD_N CASCODE MAIN_P/N MAIN_BIAS POST_P/N POST_BIAS TMDS_P/N TMDS_BIAS DETECT_ENABLE DETECT_PBIAS TERM_ENABLE TERM_TRIM0..3 TERM_VCM`; top-edge pins: TERM_VCM (Metal4 x 30.4-75), DETECT_ENABLE / DETECT_PBIAS / PAD_N / PAD_P / TERM_ENABLE (Metal4 1.2 um at x 17.2 / 20.2 / 23.2 / 26.2 / 29.2, `tx_top_pins.py`), VSS 12.5, VDD 14.5, TERM_TRIM0..3 |
| `pad_refpad` | `stress-safe-families/reference/` (`combined.gds`) | 2.78..285 × 0..912.91 | 257,636 bbox | 42 diodes (0) | `PAD_P PAD_N VSS VCM DVDD`; top-edge pins PAD_P, PAD_N, VCM, VSS |
| `pad_rf_pair` | `stress-safe-families/rf-pair/` (`pad.gds`) | 310 × 912.91 | 176,900 allocated | 404 | `PAD_P PAD_N VSS ESD_RAIL ATB_ESD_RAIL DVDD` |
| `pad_rftxpad` | `stress-safe-families/rf-tx/` (`pad.gds`) | 310 × 912.91 | 176,900 allocated | 412 | `PAD_P PAD_N VSS ESD_RAIL ATB_ESD_RAIL` (no DVDD); t8: band of 4 up (to ESD_RAIL) + 2 down diodes per leg at depth 352-389 |
| `pad_single_leg` | `stress-safe-families/single-leg/` (`pad.gds`) | 302.14 × 912.91 | 157,853 allocated | 396 | `PAD_P VSS ESD_RAIL ATB_ESD_RAIL DVDD` |
| `pad_tlp_flat` | `tlp-site/` | 68 × 124.34 | 8,455 bbox | 8 diodes | `PAD VSS VDD` |
| `tx_steering_buffer_flat` | `steering-buffer-compact/` | 54.58 × 158.98 | 8,677 bbox | 128 | `VDD VSS IN OUT` |
| `buffer_compensated_flat` | `termination-buffer-candidate/compact-array/` | 156.8 × 479.57 | 75,196 bbox | 282 | `VDD VSS REF BIAS OUT ENABLE` |

The extracted netlists of the older families also expose the isolated `ESD_RAIL` (`pad_hspad` and `pad_txpad` have none). The published `pad_rf_pair` and `pad_rftxpad`
extracted netlists are identical (same sha256). LVS references for hspad, wirepad, txpad and refpad are
`<folder>/lvs-reference.spice` (`lvs_reference.py`; regenerate after republishing a family).

Evidence files that belong to the published netlists:

| Cell | Files |
|---|---|
| `pad_hspad` (GDS sha 4d7fae99…, a6 + top-edge pins; hashes in `pc47-hspad-a6.json`) | `geometry.json`, `layout-screen.json`, `independent-device-audit.json`, `site-primary.json`, `lu.json`, `pad_hspad-kldrc.json`, `pad-lvs.txt`, `pc47-hspad-a6.json`, models `physical-r-{low,typ,high}[-rail].spice` |
| `pad_wirepad` b7 (hashes in `pc76-wirepad-b7.json`) | `placement-layout.json`, `layout-screen.json`, `independent-device-audit.json`, `model-audit.json`, `marker-merge.json`, `lu.json`, `pad_wirepad-kldrc.json`, `combined-lvs.txt`, models `physical.spice` (C-only), `physical-r-{typ,high}[-rail].spice` (R+C) |
| `pad_txpad` (GDS sha bded3185…, a16 + `tx_top_pins.py` 2026-11-24; hashes in `pc72-txpad-a16.json`) | `layout-info.json`, `lu.json`, `marker-merge.json`, `pad_txpad-kldrc.json`, `pad-lvs.txt`, `pc72-txpad-a16.json`, models `physical.spice` (C-only, wrapper `tx_protected_pad`), `physical-r-{typ,high}.spice` (R+C; model-only ports `DVSS_P/N`, tie to VSS) |
| `pad_refpad` (GDS sha 96dc5a02…; hashes in `pc75-refpad-a1.json`) | `placement-layout.json`, `layout-screen.json`, `independent-device-audit.json`, `model-audit.json`, `marker-merge.json`, `lu.json`, `pad_refpad-kldrc.json`, `combined-lvs.txt`, `pc75-refpad-a1.json`, models `physical.spice` (C-only, wrapper `tx_protected_pad`), `physical-r-{typ,high}[-rail].spice` (R+C) |
| `pad_rf_pair` r3, `pad_single_leg` s2, `pad_rftxpad` t8 (hashes in `pc74-rfpair-r3.json`, `pc74-singleleg-s2.json`, `pc81-rftxpad-t8.json`) | `pad.gds`, `pad-extracted.spice` (C-only, wrapper `rf_protected_pad`), `reference.spice` (LVS / chip-top master `pad_reference`), `physical-r-{typ,high}.spice` (lumped R+C), `pad-layout.json`, `pad-lvs.txt`, `lu.json`, `<cell>-kldrc.json` |

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

Core pins on the top edge (2026-11-23): the published GDS is a6 plus top-edge pins added by `scratch/pads-core/esdopt/pins/top_pins.py`
(added metal / labels only, removed area 0 on every layer, read-back LVS matches). Pins at y 912.91: Metal4 TERM_TRIM0..3, VSS, RX_P, RX_N,
VDD, TERM_ENABLE, TERM_VCM, VBIAS in x 418-459; PAD_P / PAD_N Metal5 as before; DVDD stays a ring landing. Known item: the models above
do not include the added pin-route C (RX_P / RX_N +26 fF each, PAD_N +7.5 fF). Pin list and C in `pc47-hspad-a6.json` `top_edge_pins`.

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

### `pad_wirepad` b7 BASELINE (USB; `pc76-wirepad-b7.json`)

ESD option A pad-site primaries (`DVDD`), no network (`ATB_ESD_RAIL` removed), low-R HS termination block, widened PAD trunks.
Review `scratch/pads-core/esdopt/usb/review-b7/REVIEW.md`: GO with conditions.

| Limit | b7 | Result |
|---|---|---|
| HBM 2 kV / CDM 2 A (high metal) | 5.65 / 7.66 V | PASS (CDM margin 0.34 V) |
| HS termination 23 corners, typ / high metal | in window | PASS |
| HS delivered current | 16.78–17.14 mA | PASS |
| HS eye template 1 (calibrated) | PASS all; ff outer margin 0.6 mV | PASS (thin) |
| Pad C per leg | up to 3.45 pF | judged on eye / RL (PC-50) |

Known misses: eye not run with the real `pt_usb_txdrv` edge (ff 0.6 mV outer margin, 496–498 ps edges); E2 junction check
vacuous; HS-path EM not screened; F1–F3 not independently re-read; uncalibrated HS level 362 mV (B11 must raise the bias
9–12 %); eye bench simplified (no jitter / noise / coupling / cable loss; template values unchecked against the spec).

### `pad_txpad` a16 BASELINE (`pc72-txpad-a16.json`; PC-72)

Published as the baseline (MANDATE 1): finished, with the known misses below. Generator `tx_pad_layout.py` (build
command in the json; no-option build = the older a4 cell). Native `nfet_06v0_nvt` termination switches with a
4-bit trim (`TERM_TRIM0..3`, internal `TERM_ENABLE_LOCAL`), TERM_VCM disconnect, pad-site primary diodes to the ring
(`DVDD_P/N`), 6 V cascodes on the pad (gate `CASCODE`).

| Limit | a16 | Result |
|---|---|---|
| Pad C ≤ 3.223 pF (rt, 100 MHz) | 3.214 (C-only 3.124) | PASS, 9 fF left: no metal may be added on PAD / TU nets |
| Termination ±10 %, 23 corners | worst 5.80 % (rt) / 4.42 % (rh); ff/22/3.35 only codes 2–3 | PASS |
| CM1 ≤ 5 Ω; off | 2.95 Ω; ≥ 9.98e9 Ω, leak ≤ 1e-5 mA | PASS |
| CDM 2 A, six cases ≤ 8.0 V | vss+ 6.92, pp+ 7.27, pp- 7.28 V; vdd+ 3.92 V incomplete under the PULSE source (bounded) | PASS, vdd+ bounded |
| HBM 1 kV | pp+ 4.35 V; vdd+ bounded by a DC sweep | PASS, vdd+ bounded |
| EM A / B / C; A100 (20 mA per pad average, ≤ 0.86) | 0.44 / 0.66 / 0.88; 0.84 | PASS |
| EM B100 (30 mA static in one leg) | TU_x_B 1.26, T1 1.03, PAD trunk 1.10 | MISS, termination-on only |
| KLayout / rail_site / latch-up / LVS + controls | 0 + 0 / PASS / 0.0 µm² at 15 µm / match, mismatch × 2 | PASS |

Conditions and known misses:
- 100BASE-TX amplitude needs WT53-c: `CASCODE` raised to about 4.2 V by wired TX's pump (≤ 4.6 V incl. transients,
  never ahead of VDD, 0 V unpowered). The pad delivers 35.5 / 39.5 mA (ss / tt) at 4.2 V; 26.9 / 34.5 mA with the
  gate at VDD. The 950 mV at the RJ45 is wired TX's open confirmation.
- Board rule B54: centre tap (any DC level on WIRE_TX_P/N) ≤ VDD + 0.30 V; the CT is not powered while the chip is unpowered.
- The termination must be off in 100BASE-TX (the static 30–40 mA one-leg EM overs apply only with it on), and no
  static drive on one leg (PC-65).
- `TERM_DISCHARGE` 2 × 20 µm `ppolyf_u_1k` waits for wired TX's ack.
- The EM screen does not yet cover PAD bond → resistor heads per unit (review-a16 F1).

### `pad_refpad` a1 BASELINE (`pc75-refpad-a1.json`; PC-75)

Published as the baseline (MANDATE 1). ESD option A: pad-site primary diodes to the ring (`DVDD`), no protection
network (`ATB_ESD_RAIL` removed). Generator `stress_safe_compact_layout.py reference_clock` with `--esd-a` (command in the json).
R+C models with the ring model; consumers judged against their 6 V devices.

| Limit | a1 | Result |
|---|---|---|
| HBM 2 kV pad − local VSS (≤ 8.0 V), high / typ metal | 6.32 / 5.69 V | PASS |
| CDM 2 A + 1 nF site decap, pad − local VSS, high / typ | 8.73 / 7.78 V | MISS at high metal |
| Site fingers fwd ≤ 10 / aval ≤ 1 mA/µm | CDM 2 A 7.77 / 0.066 | PASS |
| Pad C per leg at 1 GHz ≤ old + 0.3 pF (R+C + rail) | 0.870–0.938 pF (+0.148..+0.177) | PASS |
| At 2.45 GHz (external LO) | 0.867–0.936 pF, 0.32–0.47 Ω series | report |
| KLayout / rail_site / latch-up / LVS + 2 controls | 0 + 0 / PASS / 0.0 µm² at 15 µm / match, mismatch × 2 | PASS |

Known misses: CDM 2 A at high metal (8.73 V on the 6 V nfet drains of `pt_diff_clk_rx` / `pt_lo_ext`); consumer MIM
over 6 V if its far plate stays at VSS (upper bound, consumers not in the bench). Not run: consumer cells in the
ESD bench, device corners, P–N differential stress, external-LO amplitude with the new pad.

### `pad_rf_pair` r3, `pad_single_leg` s2, `pad_rftxpad` t2 BASELINE (`pc74-*.json`; PC-74)

ESD option A: pad-site primaries (4 down + 4 up per leg; rftxpad 4 down, no up-diode) on the published shell, whose old
network stays as the core-side secondary. All layout checks pass (DRC, read-back LVS + 2 controls, KLayout, rail_site, latch-up).

| Cell | ESD (lumped R+C, ring model, 1 nF site decap) | Result |
|---|---|---|
| `pad_rf_pair` | HBM 2 kV gates ≤ 1.71 V; CDM 2 A site reverse 10.69 V high / 9.14 typ (bv 11) | PASS, 0.31 V margin |
| `pad_rftxpad` t8 (PC-81b, `rftx_band.py` n_up 4) | local positive path (band up-diodes to ESD_RAIL + low-R clamp VSS / ESD_RAIL straps): HBM 1 kV worst reverse 6.84 V, CDM 1 A 9.67 V (t2: 13.3 / 14.0); pad C +0.39/+0.40 pF per leg (cbench) | PASS at the project ESD class (MANDATE 1: HBM 1 kV / CDM 1 A); pad C over +0.3 pF (RF TX checks match) |
| `pad_single_leg` | single-leg cases (2026-11-24): HBM 2 kV 7.49 V, CDM 1 A 6.49 V, CDM 2 A 10.63 V worst reverse high metal; gates <= 1.49 V | PASS |

Pad C (cbench, 2.4 GHz, typ, fixed 2026-11-24; +100 fF control reads back +100.0 fF), per leg vs the pre-option-A published shell: rf_pair r3 0.951 / 0.923 pF vs 0.670 / 0.642 (+0.28, limit +0.3 PASS, +0.1 wanted MISS); single_leg s2 0.932 vs 0.653 (+0.28 PASS); rftxpad t8 +0.39 / +0.40 vs t2 (accepted, PC-81b). Known misses: rebuild drift 17.4 um2/site; old network generator cannot be rerun; independent review of rftxpad only (light, review-t7).

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
   conditions in section 4), and so are `pad_txpad` (a16, PC-72), `pad_refpad` (a1, PC-75), `pad_wirepad` (b7) and the rf-shell families (r3 / s2 / t2, PC-74).
   `RF_TX` gets no diode to the supply (it swings above it). (PAD-11)
2. **`pad_wirepad` signal path.** Fixed in b7 (low-R termination block, section 4); open: eye with the real
   `pt_usb_txdrv` edge and the B11 calibration range. Resistance-aware extraction is mandatory for all pad evidence (`rextract/`).
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
