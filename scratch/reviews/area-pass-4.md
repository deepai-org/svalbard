# Area pass 4 (2026-11-13): closing ≥ 3.0 mm² on a FIXED die

The user has fixed the die at 3.932 × 5.122 mm. On the v6 outline floorplan (`scratch/chip-assembly-v6/run/report-v6.json`) the blocks are short by:
- **−1.421 mm² raw**
- about −2.28 mm² with a 10 % routing allowance (0.855 mm²)
- **about −2.97 mm² once 3 nF of stacked decap is added** (0.693 mm² at 4.33 fF/µm²).

The target is to recover at least 3.0 mm² with **no capability loss**. Every number below was measured from the current GDS unless it is marked as an estimate.

Work dir: `scratch/area-pass-4/`
- `padprof.json`: pad depth profiles
- `ringprof.json`, `cellprof.json`: ring band contents
- `util.json`, `util2.json`: device-area utilisation of every block
- `m45free.json`: M4/M5-free area over each block
- `ap4_floorplan.py` with `run/`: the scenario floorplans S0–S3
- `hspad-stacked/`: the completed pad compaction

## 1. What this pass found

**Pads (lever 1).** The 12 custom pad families take 2.636 mm² of the core. Their depth comes from two things, and neither is the protection itself.

- **Only bond pads and escape wires sit in the ring band.** In every family (`padprof.json`), the band from local y ≈ 100 µm to 426 µm (the provider ring band) holds nothing but the bond pads and the escape wires. That is because `layout.py` puts the active origin at `clearance + 24` = 438 µm. In the assembled chip the band under each custom bond is the provider `5LM_METAL_RAIL` cell (`cellprof.json`):
  - it covers 91 % with Metal3/4/5 rails;
  - it uses **no Metal2, 1.9 % COMP and 2.1 % Metal1**.

  So each custom bond site has about 75 × 270 µm of substrate, Metal1 and Metal2 free under the rails, and no device uses it. Only the fill cells between bond sites hold real content (50 % COMP; they are rail-to-rail capacitors and guard rings).
- **The attachment columns are almost empty.** The protection network region (302 × 470 µm) is already dense: 0.56 utilisation after a +2 µm sizing. The waste is in the attachment columns of the USB pad (`pad_wirepad`) and the wired-TX pad (`pad_txpad`):
  - COMP is 1–2 % over the 908–1434 µm band;
  - devices plus 2 µm cover 0.17 / 0.19 of the outline.

  The cause is the generator's routing scheme: at most 7 devices per 26 µm row (because of the Metal4 route rows) and one full-height trunk per net. That turns roughly 350 attachment devices into a column about 1000 µm long.
- The HS RX pair pad (`pad_hspad`) placed its two 154 µm legs **above** the 913 µm shell, while a 168–182 µm-wide strip **beside** the shell, inside the same footprint, was empty.

**Analog outlines (lever 2).** The table below lists device area (COMP ∪ poly ∪ MIM, merged, then +2 µm) against the outline. Spiral-dominated cells (`qvco`, the LC load) are excluded because their empty area is inductor keep-out.

| block | outline mm² | dev+2 µm mm² | util | repack target mm² | saving | owner |
|---|---|---|---|---|---|---|
| wrx_cap (published r6) | 0.956 | 0.284 | 0.30 | **0.290 (r7 compact exists, 1199 × 242)** | **0.67** | wired RX (running) |
| adc_i, adc_q | 0.578 each | 0.103 | 0.18 | 0.33 each | 0.50 | converters |
| lo_mmd | 0.361 | 0.049 | 0.14 | 0.16 | 0.20 | LO/timing |
| ptrim | 0.290 | 0.030 | 0.10 | 0.10 | 0.19 | wired RX (running) |
| bbfilter_i, bbfilter_q | 0.342 each | 0.089 | 0.26 | 0.23 each | 0.22 | rf_rx (not LNA files) |
| core_bias | 0.302 | 0.071 | 0.24 | 0.18 | 0.12 | bias/core_support |
| cdr (X3) | 0.174 | 0.034 | 0.20 | 0.09 | 0.08 | wired RX (running) |
| detect | 0.173 | 0.034 | 0.20 | 0.09 | 0.08 | wired RX (running) |
| dac_i, dac_q | 0.186 each | 0.056 | 0.30 | 0.13 each | 0.11 | converters |
| pll_ring (CDR) | 0.167 | 0.044 | 0.26 | 0.115 | 0.05 | wired RX (running) |
| ctle | 0.133 | 0.037 | 0.28 | 0.095 | 0.04 | wired RX (running) |
| lo_ext | 0.155 | 0.053 | 0.34 | 0.12 | 0.035 | LO/timing |
| term_buffer (pads) | 0.075 | 0.015 | 0.19 | 0.045 | 0.03 | pads |
| clk_obs16, pll_ring_core | 0.092, 0.086 | 0.031, 0.030 | 0.33, 0.34 | 0.065 each | 0.05 | timing |

The following are already dense, so no lever: `lo_lf` 0.95, `rxmix` 0.67, `lna` 0.70, `pll_vreg2` 0.63, `refbuf` 0.56, `lo_pfdcp` 0.51, isw_* 0.58–0.68.

The user's "DAC outline 0.185 vs 0.126" comparison is a false lead. The 0.126 figure was wrong evidence (interface-changes RFT-6: its bbox missed the logic strip), and 0.186 is the real outline. The DAC is still sparse (0.30), though, so the 0.13 target stands.

**R8-ARCH (lever 3).** The v6 `r8arch_rsv` of 0.43 mm² is already the compact basis:
- slicer B: 0.110
- capture B: 0.285–0.290, the r7 compact master
- blenders and PD8: about 0.035

So the second capture is **not** booked at the 0.96 outline. **Confirmed.**

The real problem is capture A. `generated/wrx_cap.gds` is still the 0.956 mm² r6 cell. The r7 compact cell is in `scratch/wired_rx/r7cap` at 1199 × 242 µm: Magic DRC, LVS and KLayout are clean, and extracted q625 is 0/200. It has not been published because the q834 runt-pulse fix is still in progress. **Wired RX is pushed (AP4-1) to publish r7 at the ≤ 625 MHz qualification**: SLI7-G already forbids ring > 625 MHz for every production mode, so q834 is not a gate. Capture B should also be booked on that master with its real 1199 × 242 shape, not as a 656 µm square.

**Digital (lever 4).** The macro is 2.814 mm². Cell area is 1.86 mm² (66 % utilisation, TC8). Gain/rebuffer buffers are **0.25 mm²** (13.5 % of cells), with `PL/GRT_RESIZER_SETUP_MAX_BUFFER_PCT = 80`, which `scratch/digital-timing-close/NOTES.md` itself flags as questionable. The target is 2.45 mm²: about 0.1 mm² fewer buffers (registered pops and fanout fixes instead of buffer trees) at 75 % utilisation.

FPGA offload is not a lever. `fpga-offload-audit.md` §4 finds no further large flip-flop saving without dropping a MUST item (≤ 0.02 mm²).

**Decap (lever 5).**

- **Metal4/Metal5 space over blocks.** `m45free.json` measures, inside the published analog outlines (pads excluded), **2.86 mm² of area free of Metal4, Metal5, MIM and Via4 in ≥ 20 × 20 µm tiles**. That is about 5.7 nF of potential `cap_mim_2f0_m4m5` over blocks. Exclude the spirals and keep the most sensitive nodes (ADC inputs, bbfilter, VCO) unshielded, and even 30 % of it is 1.7 nF.
- **Digital fill cells.** The macro's roughly 0.9 mm² of unused rows can take decap fill cells instead of plain fill, on the order of 1 nF.

Together the 3 nF needs no dedicated area, which removes the 0.693 mm² from the gap. Caveat: when blocks are repacked, the free M4/M5 area over them shrinks, so this has to be re-measured after the repacks.

**Sharing (lever 6).**

| item | status | saving |
|---|---|---|
| X1 (pll_host) | done | — |
| X4 (ring variant) | done | — |
| X2 (MIM on MOS) | built into the v6 decap density | — |
| X3 (cdr) | partly done, 0.209 → 0.174 | 0.08 left (in the table above) |
| X5 (TMDS legs onto MAIN) | wired TX, running | −0.04 |
| X6 (h2d gearbox reserve 0.093 → 0.031) | not done | −0.062, applied in S1 |

- Regulators: one dense `pll_vreg2` already, nothing left.
- Island switches: 0.236 mm² total, already dense (0.58–0.68). Merging the five would save about 0.03, which is not worth the isolation risk.
- core_bias: 0.24 utilisation, see the table above.

**Floorplan efficiency (lever 7).** The seeded greedy placer in v6 leaves 0.69–1.12 mm² of fragments (scenarios below), even with a positive raw margin. A real re-pack is required, not optional.

## 2. Completed this pass: stacked `pad_hspad` (−0.088 mm²)

`analog/pads/hs_pad_compose.py --stacked` uses the same shell, the same `pt_hs_leg` master and the same reference netlist as before:

- **Legs:** stacked beside the shell (P leg at x 340, y 440; N leg at x 340, y 628).
- **Pad wiring:** PAD_P is wired under the start of the PAD_N trunk, so the pair never crosses. PAD_N is a side strap.
- **Shared nets:** use Metal4 risers over the Metal4-free half of the legs.
- **RX pins:** RX_P/RX_N leave on identical side pins at x 492.

The cell is **492 × 912.91 µm, down from 478 × 1111.25**. Core intrusion drops from 0.3276 to 0.2396 mm².

Build `scratch/area-pass-4/hspad-stacked/` (pad image `b6027809`):

- **Layout checks:** Magic DRC 0; netgen LVS unique; independent device audit match; KLayout precheck main 0 / antenna 0 (`kldrc/`); latch-up audit clean (`lu-stacked.json`). Negative control: removing the PAD_P stub makes LVS fail.
- **Safe/HBM 2 kV** (the unchanged `stress_safe_family_sims` benches, `ap4-hspad-safe-hbm.json`): 18/18 runs complete, **0 of 404 MOS over the screen**, HBM pad peak 3.28–5.41 V, peer leakage 0.15/0.34 µA. This is identical to the published PD21 evidence.
- **Termination** (`rterm-new.log`): matches the published ranges (code 0: 64.8–116 Ω; code 15: 24.4–38.7 Ω at VCM ≤ 0.5 V).
- **AC** (`scratch/pads-pd21/hs_bench.py ac`, same bench on the published and the new cell):

| metric | published | stacked | change |
|---|---|---|---|
| C per leg, tt | 1.130 pF | 1.148 pF | +18 fF |
| C per leg, ss32 | 1.170 pF | 1.189 pF | +19 fF |
| die return loss at 2.4 GHz | 8.19 dB | 8.07 dB | −0.12 dB |
| COB return loss, 1.25–2.5 GHz | 6.15 dB | 6.08 dB | −0.07 dB (package-limited) |
| RX_P / RX_N C | 58.8 / 58.8 fF | 76.4 / 75.4 fF | balanced |

The C increase comes from the side RX straps. Two earlier variants were rejected: v1 had a 38 fF P/N imbalance from a long RX_P riser, and v2 crossed the pair.

- **Final build:** GDS sha 0d24e132 (a rebuild after renaming the leg-position variables `YN`/`YP` → `YBOT`/`YTOP`; the extraction is identical to the reviewed build 32af9d31). KLayout precheck main 0 / antenna 0 on this sha (`scratch/area-pass-4/kldrc/pad_hspad/kldrc.json`), latch-up audit clean, AC/termination rerun identical, and the safe/HBM rerun on the final model is in `ap4-hspad-safe-hbm.json`.
- **Independent review** (`scratch/area-pass-4/review/REVIEW.md`): **GO with conditions.**
  - The reviewer reran Magic DRC (0), netgen LVS (unique). Swapping the RX labels makes LVS fail, so RX polarity is checked.
  - They also reran KLayout (0/0) and the latch-up audit (0), plus a geometry check. The only new ring-band shape is the M5 PAD_P strap at local y 414–418 (die depth 440–444, past the M3/M4 VDD ring). The core-ring cutter only looks at M2–M4, so it is acceptable.
  - Their RX-path bench shows −0.03 dB of loss. The P/N pad-C gap grows from 13.3 to 19.0 fF (≈ −49 dB mode conversion).
- **Conditions before publishing to `generated/`. Not published.**
  1. The KLayout/latch-up record must carry the final sha. **Done** above; the record is regenerated on publish.
  2. RX_P/RX_N side pins are 188 µm apart, at different depths. Either the chip-level routes to the CTLE are length-matched to ≤ 5 fF imbalance (assembly), or the pins are moved next to each other in the cell. Moving them costs about +20 fF on one leg to keep the in-cell balance.
  3. The PD48c 1 kV HBM / CDM-speed rows and the README pad-C/return-loss figures must be rerun on the new netlist, or get a dated supersede note.
  4. Informational: the README die return loss at 2.4 GHz should read 7.0–8.7 dB. The ss corner was already 7.14 on the published cell, not the "8.0–8.5" range the README states.

## 3. Scenario floorplans (same placer and rules as v6, `scratch/area-pass-4/run/`)

| scenario | contents | pads in core | digital | demand | **raw margin** | unplaced (greedy) | scrap |
|---|---|---|---|---|---|---|---|
| S0 | v6 as published | 2.636 | 2.814 | 8.549 | **−1.421** | 14 / 3.50 mm² | 0.89 |
| S1 | + wrx_cap r7, stacked hspad, X6 | 2.548 | 2.814 | 7.883 | **−0.605** | 11 / 2.62 | 0.79 |
| S2 | + all repack targets of the table in §1 | 2.548 | 2.814 | 6.289 | **+0.989** | 4 / 1.41 (area order: 24 / 0.87) | 0.67–1.12 |
| S3 | + USB/TX pad attachment repack, digital 2.45 | 2.357 | 2.45 | 6.289 | **+1.544** | 3 / 0.88 (area order: 8 / 0.44) | 0.69–1.12 |

S3 recovers **2.965 mm²**, enough to cover routing (0.855) and dedicated decap (0.693) almost exactly. The greedy placer still cannot place it (0.44–0.88 mm² left over). That is why lever 7 (a real re-pack) and lever 5 (decap over blocks, which removes the 0.693) are both part of the plan below and not optional.

## 4. Ranked levers

Savings are core mm². Risk is to schedule and evidence, not to capability: every lever keeps the same circuits and functions.

| # | lever | saving | owner | risk | state |
|---|---|---|---|---|---|
| 1 | wrx_cap r7 compact published (q625-qualified; q834 not a gate per SLI7-G) | **0.67** | wired RX (running) | low: layout clean, extracted q625 0/200 | AP4-1 |
| 2 | decap as MIM over block outlines + decap fill in the digital macro instead of dedicated tiles | **0.69** (removes the dedicated 3 nF) | assembly + digital | med: re-measure after repacks; no MIM over spirals or sensitive nodes; PDN-02/03 \|Z\| check | AP4-9 |
| 3 | ADC I/Q repack to ≤ 0.33 each | **0.50** | converters | med: INL/ENOB re-extraction | AP4-4 |
| 4 | wired RX repacks: ptrim, cdr (X3), detect, ctle, CDR ring | **0.45** | wired RX (running) | med: extracted CDR/ptrim reruns | AP4-1 |
| 5 | floorplan re-pack (scrap 0.7–1.1 → ≤ 0.3) | **0.4–0.8** (needed to place S3) | assembly | low–med | AP4-10 |
| 6 | core power ring 2 × 25 µm → 2 × 12 µm (core edge 452 → 416 µm) | 0.37 net | assembly | med–high: EM at 85 °C and IR ≤ 117 mV must pass first | AP4-10 |
| 7 | digital 2.81 → 2.45 mm² (buffer cap, util 75 %) | 0.36 | digital (no agent) | med: timing margin | AP4-8 |
| 8 | debug pairs BB_I/BB_Q + WMON on provider `asig_5p0` (zero core intrusion, like ATB0/1) | 0.40 | pads + rf_rx (bb_tap) | med: confirm bb_tap isolation, debug bandwidth and HBM screen; the fallback is the adopted-but-undrawn shared B cell for BB_Q (−0.05) | AP4-7 |
| 9 | LO repacks: lo_mmd, lo_ext, clk_obs16, pll_ring_core | 0.30 | LO/timing | med | AP4-5 |
| 10 | bbfilter I/Q repack | 0.22 | rf_rx | med: FS-2 rerun | AP4-3 |
| 11 | USB (wirepad) + TX pad attachments repacked (2-D array, shared track bank) | 0.19 | pads | med: generator rework, full requal (HBM, USB, termination) | AP4-6 |
| 12 | ESD diode rows (and other COMP/M1/M2-only devices) moved under the `5LM_METAL_RAIL` of each custom bond (no Metal2 there) | 0.15–0.19 | pads + assembly | med–high: ring-overlap rules, pad C to the ring rails | AP4-6 |
| 13 | core_bias repack | 0.12 | bias | med | AP4-10 |
| 14 | DAC I/Q repack | 0.11 | converters | low–med | AP4-4 |
| 15 | QVCO outline corners reused for small LO cells (outside the inductor keep-out) | ≈ 0.1 | LO + assembly | med | AP4-5 |
| 16 | **stacked hspad (done)** | **0.088** | pads | low: review | §2 |
| 17 | X6 h2d gearbox reserve 0.093 → 0.031 | 0.062 | assembly + digital | low | AP4-8 |
| 18 | X5 TMDS legs onto MAIN | 0.04 | wired TX (running) | low–med | AP4-2 |
| 19 | term_buffer repack | 0.03 | pads | low | AP4-6 |
| 20 | logic to the FPGA | ≤ 0.02 | digital | — | not worth it |

## 5. Plan to ≥ 3.0 mm²

| tier | levers | saving | running total |
|---|---|---|---|
| A (in hand, low risk) | 1 + 16 + 17 + 19 | 0.85 | 0.85 |
| B (assigned repacks) | 3 + 4 + 9 + 10 + 14 | 1.58 | 2.43 |
| C | 7 (digital) + 11 (pads) | 0.55 | **2.98** (= S3) |
| D | 2: decap over blocks / in the macro | removes the 0.69 dedicated decap from the requirement | 3.0 requirement met with ≈ 0.7 slack |
| E (re-pack, required to place S3) | 5 | — | — |

Contingency if any target misses: levers 6, 8, 12, 13, 15 add up to about 1.1–1.2 mm².

Order:
1. Publish wrx_cap r7 now.
2. Start the converter, LO and RF repacks in parallel; their owners are idle.
3. Start the digital buffer/util round.
4. Re-run the floorplan with a real packer once ≥ 60 % of the tier-B outlines exist.
5. Measure the M4/M5-free decap area on the repacked blocks.
6. Gate the core-ring narrowing on an EM/IR run.

Nothing in this plan removes a function, a mode or a pad.

## 6. Stale items fixed in this pass

- **LO-03** (risk register): it named `pll_host`, which X1 deleted. It is restated for `pll_cdr` (host_follow / GX-5) and `pll_tx`, with the PA subharmonics 343–833 MHz that fall inside the ring band and the v6 distances. It stays open, pending integration-plan check 3.
- **SUB-07**: it was closed on "TX and RX are TDD". That is stale, because GX-3 duplex is accepted and RF-PWR-1(c) runs the PA with the LNA and ADCs on. It is **reopened** (score 6) with the v6 keep-away audit (all met) and the RFT-5 analytic isolation (48.8 dB worst).
- **TH-01**: re-analysed for duplex. Pessimistically, 0.207 W of PA heat with k = 130 W/m·K gives +0.14 K and 0.079 K/mm at the ADC, and 0.024 K/mm at core_bias, all ≪ 1 LSB. It stays closed, conditional on the SUB-07 distances.
- **INT-03**: points here. The register totals were updated (open 103, closed 15).
- **`spec/contract.json` pin order**:
  - **What was stale:** `candidate_signal_sites` still had the pre-PD22 map. WIRE_RX_P sat on bidir[14], but the mirrored hspad bonds P on [15]; WIRE_TX P/N were likewise swapped against the mirrored txpad. RF_TX and REF_IN were on their old west sites (inputs[4/5], inputs[1/0]). There were no USB_DP/USB_DN pins, and the `usb2` aliases sat on WIRE_RX.
  - **What changed:** an authoritative `assembly_policy.bond_map_current` was added (west/east/north maps, retired pins, sources).
  - **What was left alone:** `candidate_signal_sites` itself drives `analog/pads/design.py` and `test_contract.py`, so it was not rewritten. Re-baselining it is a pads + test change.
  - **Checks:** `check_contract.py` passes, and `test_contract` passes 30/30.

## 7. Questionable prior choices

1. The pad generator reserves the whole 426 µm provider ring band for the bond and escape. Yet the provider rail cell under each custom bond has no Metal2 and almost no COMP or Metal1. No earlier pass looked under the rails.
2. In the attachment generator, the one-track-per-net, 7-devices-per-row scheme gives 1–2 % COMP over half a millimetre of the USB and TX pads. Earlier area passes treated the pad outline as fixed and shrank everything else.
3. The hspad legs were stacked above the shell while a strip of the same footprint beside the shell was empty: 0.088 mm² for free.
4. Several prior shrink rounds reported "−x mm²" against outlines that were never measured for utilisation. ADC (0.18), lo_mmd (0.14) and ptrim (0.10) are the least dense non-spiral cells on the chip, yet none of them was on a shrink list.
5. v6 books decap at a stacked MOS+MIM density but places it only in leftover 120 µm cells (0 nF placed). Meanwhile 2.9 mm² of M4/M5 over the blocks goes unused.
6. The v6 placer is seed-based greedy. Its "does not fit" list partly reflects fragmentation (0.89 mm² of scrap), not only a lack of area.
7. `contract.json` was left with a pre-PD22 bond map for 3 days while the assembly flows used `inventory.py`.
