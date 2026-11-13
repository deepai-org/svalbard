# Consolidation pass 3: cross-block area review against the v5 assembly (2026-11-11)

This is analysis only. No block, assembly or spec file was changed.

Sources:
- `scratch/chip-assembly-v5/flow/chip_assembly/inventory.py` and `netlist.py`
- `scratch/chip-assembly-v5/run2/{abstracts,floorplan}.json`, which give the measured GDS bounding boxes
- `spec/interface-requirements.md` and `spec/performance-requirements.json` (142 rows)
- `scratch/reviews/{MANDATE,risk-register,interface-changes,SESSION-STATE,consolidation-pass-2}.md`
- block evidence/layout JSON

All areas are bounding boxes in mm². Owner shrinks already in flight (wrx_cap, rings, vregs, wired TX) are **not** counted as savings here. They appear only in the fit arithmetic (section 4).

## 0. Where the 13.6 mm² goes (v5 run2, clipped to the 12.92 mm² core)

| Item | mm² | Note |
|---|---:|---|
| Placed blocks (62 masters, 154 instances) | 5.19 | Largest: adc_i/q 0.578 each, bbfilter_i/q 0.495 each, wiredtx 0.331, core_bias 0.302, dac_i/q 0.185 each, pll_cdr 0.185 |
| Digital macro (AC1_R4) | 2.50 | 1716 × 1455 |
| **Pad-family intrusion into the core** | **2.72** | 13 custom families, 913–1513 µm deep against a 442 µm core edge. Debug-only pairs alone: BB_I, BB_Q, WTX_EXT 0.154 each; ESD_TEST 0.150; WMON 0.102 |
| Reserves | 0.58 | isolation band 0.218, corridor 0.126, H2D gearbox 0.093, T-coil 0.068, LO legs 0.043, D2H 0.032 |
| Decap placed (MIM pool 0–2, isolation-band MIM, local, MOS tiles) | 0.41 | Partly overlaps the reserves |
| Unplaced blocks | 2.15 | wrx_cap 0.938, vreg_tx + vreg_cdr 0.479, cdr 0.209, pll_tx + pll_host 0.371, attached_tx_buffer 0.155 |
| Unplaced decap (pool3–5, locals pll/conv/debug) and the wired-TX worst-case growth (0.331 → 0.628) | ≈ 0.48 | |
| **Demand** | **≈ 13.6** | **Target for ≥ 10 % routing margin: ≤ 0.9 × 12.92 = 11.63 mm². Gap: ≈ 1.97 mm²** |

## 1. Status of consolidation-pass-2 items (checked in v5)

| Pass-2 item | Implemented? | Evidence / finding |
|---|---|---|
| R1: three rings become two (Ring C takes host_follow) | **No** | `PLL_RINGS` defaults to `'3'`. pll_host is still instantiated. r9 more than doubled the ring (75.8k → 187k µm², 665 devices), so R1 is now worth **0.185 mm²**, not 0.08. **New: in the v5 netlist only `pll_host.REF` is bound.** Its PH/FBCK do not reach `prescale`, so host_follow is unwired whichever ring provides it. |
| R2: one hold mechanism | **Yes in the cell, stale in assembly** | `pt_cdr` r-ac3 (AC3-W3) removed `freq_hold`/`FBCK_IN`. But `netlist.py:120` still binds `cdr.freq_hold` and `cdr.FBCK_IN`, which is a **stale binding the assembly owner must fix**. The area purpose was overtaken: cdr grew 40k → 209k µm². |
| R3: reclaim FF first | Superseded / unverified | AC-1 deleted pt_memory and pt_calibrator (S1, T13–T24). No FF headroom number was re-reported, so the ring_c fields cannot be costed. |
| R4: smaller second clk_obs | **Exceeded** | WCLK_OBS was folded into CLK_OBS (PD22) and the `wclk_obs` instance was removed. Only `clk_obs16` remains (0.092). Net −0.054 versus the two old cells. |
| R5: shared MIM pool | Partly | 6 FIB-strapped banks of 0.36 nF are designed, but **3 of 6 pool banks and 3 of 5 local decaps fail to place.** |
| F1: register map does not match the rings | **No** | `consolidation.pll` (0x53, NS16..NS128, W1..W10) is still the documented ring bank. |
| F2: wrx_cap in CDR-fallback `shares_failure_with` | Not found | Could not locate the field in `tapeout-readiness.json`. Recheck. |

## 2. Per-block screen (every inventory master)

Key:
- a = share or dual-purpose with another block
- b = move to the FPGA or off-chip
- c = droppable (cites the requirement IDs it serves)
- d = oversized for its requirement

"Keep" means none of a–d yields a safe saving.

| Block (inst) | mm² | Serves (IDs) | a / b / c / d verdict |
|---|---:|---|---|
| adc_i, adc_q | 0.578 ×2 | RF-WIFI-ACR (40 MS/s, 2-way interleaved v3), RF-SDR-CAPTURE, RF-154-CCA | a: rejected (pass-2: ADC is not the wrx capture; 8 phases at 834 MHz versus 40 MS/s). d: the 2× growth (259k → 581k) is the interleave that ACR demands. **Keep.** |
| bbfilter_i/q | 0.495 ×2 | RF-*-SENS, RF-WIFI-ACR, RF-HT40-RX (GX-1) | Keep |
| dac_i/q | 0.185 ×2 (evidence 0.126) | RF-TX-*, RF-HT40-TX | The bbox is 47 % above the evidence area (M135/R90 placement bbox). Assembly to check whether the abstract carries a halo. |
| refbuf | 0.117 | ADC/DAC reference | Keep |
| lna, rxmix_i/q, txmix_i/q, txsum, rfdriver | 0.078, 0.076 ×2, 0.021 ×2, 0.004, 0.135 | RF chain | Keep. LNA growth is funded (RC-16). |
| lo_ext | 0.109 | RF-LO-JIT, RF-XLO-RANGE | Keep |
| polyphase | 0.039 | none (P3-4 learning, fails extracted) | c: candidate, but it is a learning structure (memory: full scope). **Keep**, tiny. |
| **pll_host (pll_ring r9)** | **0.185** | host_follow: RF-XLO-RANGE / RF-GNSS-RX (GX-5), warm hopping (RF-SDR-SCAN, RF-PROF-SWITCH, RF-CS-HOP via `host_follow_div2`) | **a: yes.** Ring C (pll_cdr) is idle in every RF mode → **X1** |
| pll_tx, pll_cdr (r9) | 0.185 ×2 | WR-RATE-CONT/EDGE, WR-PLL-JIT, all WR-* | a: TX and CDR rings run concurrently at different ppm (SSC). Sharing is rejected. d: pll_tx carries the CDR-only fast-tune array (N5/N10/KP/FU/FD tied to VSS in `netlist.py:118`) → **X4** |
| vreg_tx, vreg_cdr | 0.241 ×2 | PDN-04 (demanded), WR-RATE-EDGE (834 MHz regulated) | a: one shared regulator couples two free-running rings (LO-02 co-sim still open), which adds risk, so rejected. **b: an off-chip LDO on a dedicated ring-supply pad → U1** |
| cdr (pt_cdr r-ac3) | **0.209** | WR-*-JTOL/PPM/SSC | **d: yes.** 489 devices on a generic 20 × 25 grid at 18 µm pitch is 426 µm²/device. The slicer's compact rows achieve about 64 µm²/device. **Not on the owner-shrink list → X3** |
| wrx_cap | 0.938 | all WR-*-BER (capture, PD votes, 40-bit gear) | a: the RF ADC cannot sample 8 phases at 834 MHz. The macro FIFO-bank capture already sits downstream of DX[39:0]. Moving `wc_gear` (84k µm² of cells, ≤ 162 MHz) into the macro is rejected because the macro fails timing at −12 ns on the wrx path. **d: yes.** Leaf cells sum to ≈ 0.25 mm² inside a 0.938 bbox (27 % utilization). That is owner work; the number goes to the owner. |
| slicer, ctle, rxselect, rxlevel, termination, wmon_sel, detect | 0.056, 0.133, 0.009, 0.013, 0.048, 0.010, 0.097 | WR-SLICER-OFFSET, WR-100TX-RXEQ (IX-13), WR-PCIE-DETECT, WR-SATA-OOB, WR-USB-SQUELCH | ctle grew 6× (IX-13 LF cap bank plus input C); this is plausible. **Keep.** |
| wiredtx (worst case) | 0.331 → 0.628 | WR-*-TXSWING/TXJIT, WR-SER-DJ; user decision (2) CMOS + CML | Owner shrink in flight |
| attached_tx_buffer / steering ×6 / interlock | 0.155 / 0.115 / 0.048 | txpad termination VCM, MAIN/POST/TMDS pre-drive | **a: X5** (TMDS legs onto MAIN, as 100BASE-TX already does). d: the 139 × 1117 buffer is not on any shrink list. Flag to wired TX/pads. |
| hsbias, wtx_fallback_control | 0.009, 0.006 | WR-USB-HSSWING; TX fallback | Keep |
| clk_obs16 | 0.092 | debug: one observation path for 16 clocks | Keep (R4 done) |
| prescale, wordclk, clockmux | 0.013, 0.025, 0.015 | host_follow divider; word clock (WR-RATE-EDGE); ref mux | a: prescale + wordclk rejected (pass-2) |
| ring_osc, vco_replica | 0.010, 0.021 | debug (process speed; open-loop ring) | c: duplicate-debug candidates, but ≤ 0.03 total and the only open-loop ring. **Keep.** |
| diff_clk_rx ×3 | 0.015 ×3 | WCLK_IN (WR-TMDS-BER forwarded clock, CDR fallback), AUX_CLK debug, WTX_EXT fallback | Keep |
| bb_tap ×3 | 0.010 ×3 | debug/fallback for BB_I/BB_Q/WMON | See U2 |
| core_bias | 0.302 | all | Routed and passed. Pass-2: do not merge banks. **Keep.** |
| por, aosc | 0.010, 0.013 | safety / always-on | Keep |
| isw_* ×5 | 0.236 | island power gating | Keep |
| atb leaves/groups/pads | 0.112 | debug (DC observation of every critical node) | Keep. This is the debuggability floor. |
| MIM pool + locals | ≈ 0.28 standalone (placed + unplaced) | PDN-02/03 (demanded, \|Z\| ≤ 1 Ω) | **a: stack on MOS decap → X2** |
| Debug pad pairs (BB_I, BB_Q, WTX_EXT, WMON, ESD_TEST) | 0.71 intrusion | fallbacks / ESD learning | **U2, U3** |
| rsv_h2d_gearbox | 0.093 | HL-RATE (AC-1 gearbox) | **d: X6.** It is 3× the D2H reserve, and D2H needs about 0.020 (I11). |

## 3. Ranked proposals

### 3a. Do: no capability loss, no added risk

| # | Block | Now (mm²) | Proposal | Saved (mm²) | Requirements affected | Risk note | Owner |
|---|---|---:|---|---:|---|---|---|
| X1 | pll_host | 0.185 | **Pass-2 R1, finally.** Delete pll_host. Give pll_cdr a REF select (`ref_clk` / `H2D_CLK`) and gate PH0 → `prescale.HF`. Register field `ring_c.owner {off, cdr, host_follow}`; host_follow and CDR are mutually exclusive in the validator. Wire the host_follow path, which is unbound today. | **0.18** (0.185 + halo − about 0.005 of selects) | RF-XLO-RANGE, RF-GNSS-RX, RF-SDR-SCAN, RF-PROF-SWITCH, RF-CS-HOP: served by Ring C, which is idle in RF modes. No WR row needs host_follow (interface-changes, lines 322–327). | **Lowers risk.** It removes the SUB-05 aggressor (pll_host → bbfilter_i −8.1 dB) and LO-03 injection. host_follow moves onto a regulated ring (vreg_cdr), so it has less DJ than pll_host on the raw rail (PD31). Fallback: `rf_host_source=carrier_divided` (reset default) needs no ring. Observability: fc_src[1] and ATB_VCTRL. **Precondition: `contract.json` usb_selected_service still says `host_follow100MHz SDR`, which contradicts AC-1 (host = line/8). The digital owner must retire that row.** | timing (ring REF select), digital (field, validator), assembly (instance, `PLL_RINGS=2`) |
| X2 | MIM pool banks | ≈ 0.28 standalone | Put every MIM pool bank (Metal4/Metal5 `cap_mim_2f0_m4m5`) **on top of the MOS decap regions**. `pt_decap_tile` uses only Metal1/Via1/Metal2, and the inventory states that M3–M5 are free above it. Use the pockets: mos_pocket_a 798 × 562 µm holds about 35 MIM units, against about 18 needed for 0.36 nF. Do not use the signal corridors. | **0.27** (pool0–2 0.141 placed + pool3–5 about 0.13 unplaced) | PDN-02/03 unchanged: same nF, same FIB straps | Low. Both caps are on core VDD/VSS. Keep the M5 PDN straps outside the banks. A DRC density check on M4/M5 is needed. | assembly (+ core_support decap) |
| X3 | cdr | 0.209 | Compact-row relayout (slicer/wrx_compact style) of r-ac3. Not on any owner's shrink list. | **≈ 0.13** (target ≤ 0.08; 489 devices at ≤ 160 µm²/device) | none (the CDR is not yet closed extracted, so no signed-off evidence is lost) | Must rerun the extracted CDR loop, which is already queued. Fix the stale `freq_hold`/`FBCK_IN` binding in `netlist.py` at the same time. | wired_rx |
| X4 | pll_tx (and pll_cdr if X1 is done: only 2 rings) | 0.185 | A ring variant **without the CDR fast-tune array** for pll_tx. Its N5/N10/KP/FU/FD pins are tied to VSS today. Same `ct_ring9` core and phase loading. | **≈ 0.05** (estimate: 25–30 % of 665 devices; the owner must measure) | WR-RATE-*: unchanged, same core cell | A second layout variant means one more LVS/extracted range run. Fold it into the ring shrink already in flight. | timing (ring owner) |
| X6 | rsv_h2d_gearbox | 0.093 | Right-size it to the D2H basis (I11: about 0.020 needed, 0.031 reserved). | **0.06** | HL-RATE unchanged | None until the S2/H2D gearbox layout exists. Re-grow it if digital reports more. | assembly + digital |
| X5 | steering drivers (TMDS P/N) + TMDS pad legs | ≈ 0.04–0.06 | Drive TMDS from the MAIN tail into the sink's 50 Ω pull-ups, as the 100BASE-TX map already does ("TMDS-like external pull-up configuration", MAIN at code ≈ 120 → 10 mA). Remove the TMDS leg pair. | **≈ 0.04** (investigate) | WR-TMDS-TXSWING (VH = AVcc ± 10 mV, 400–600 mV SE) | Must show the MAIN leg tolerates a 3.3 V pull-up at ff with clamp leakage. Today's TMDS row is already marginal on clamp leakage. **Do it only if wired TX confirms with an extracted bench. Otherwise drop X5.** | wired_tx + pads |
| | **Subtotal, do** | | | **≈ 0.73** | | | |

### 3b. Needs a user decision (capability, pins or learning scope)

| # | Block | Now (mm²) | Proposal | Saved (mm²) | Requirements / capability affected | Risk note | Owner |
|---|---|---:|---|---:|---|---|---|
| U1 | vreg_tx + vreg_cdr | 0.482 | **Off-chip ring supply.** A board LDO feeds a dedicated VDD_RING pad (provider supply cell, 350 µm deep, about 0 core intrusion) plus a local on-die MOS decap (about 0.05 mm²). It could also run the rings at 3.0–3.3 V, which gives more top margin than the 2.71 V regulated rail. | **≈ 0.43** | PDN-04 (PSRR ≥ 20 dB, 10–160 MHz) must be re-proved: a bond-L/on-die-C filter alone gives a corner at about 250–350 MHz, so the isolation has to come from a separate rail and not from filtering. WR-RATE-EDGE improves. | Costs 1–2 pad sites, and the 19 spare sites are booked for debug. It adds an A2/A3 re-analysis. **Not risk-neutral until that analysis exists.** | user → pads, timing, board |
| U2 | BB_I + BB_Q pads (2 rf_pair) + bb_tap_q | 0.308 + 0.01 | Merge them into one BB pad pair with an I/Q select in bb_tap. | **0.16** | Loses *simultaneous* off-chip I and Q (external-ADC fallback and off-chip I/Q cal). No interface-requirements row cites the BB pads; they are fallback/debug. | Fallback capability loss. One observation path per baseband node is kept (sequential). | user → rf_rx, pads |
| U3 | ESD_TEST pad | 0.150 | Drop it, or move the clamp variant under test into an existing debug family. | **0.15** | none (tier-3 ESD learning) | It is a learning loss; memory says full scope. Not recommended unless needed. | user → pads |
| U4 | Shared ESD rail clamp per edge | ≈ 0.25–0.4 | Replace the per-family gate-coupled shunt (W 12,006 µm + 32 pF, about 0.05 mm² each, 13 families) with one clamp per edge on an ESD bus. | 0.25–0.4 (estimate) | none functionally | **Requalifies every family (HBM, LU-01, PD13/16)**: added risk, against MANDATE. **Recommend: no, not this tapeout.** | pads |

### 3c. Rejected (checked, no safe saving)
- TX/CDR ring sharing: they run concurrently with an SSC offset.
- One shared vreg: ring-to-ring pulling through the regulator; LO-02 is open.
- ADC/DAC as wired capture.
- wc_gear into the macro: macro timing is −12 ns.
- Merging bias banks (pass-2).
- ring_osc/vco_replica removal: ≤ 0.03 and they are unique observation paths.
- Shrinking the digital macro: its 36 % free sites carry the about 3 nF fillcap that PDN-02/03 rely on.
- WCLK_IN or WTX_EXT removal: WR-TMDS-BER uses WCLK_IN.

## 4. Does it fit?

| Step | Demand (mm²) | Free / core |
|---|---:|---:|
| v5 today | 13.60 | −5.3 % (over-full) |
| + cross-block "do" X1–X6 (−0.73) | 12.87 | 0.4 % |
| + owner shrinks in flight, at plausible targets: wrx_cap to 60 % utilization (−0.52), wired TX worst case back to ≈ 0.40 (−0.23) | 12.12 | 6.2 % |
| + U1 (off-chip ring supply, −0.43) | 11.69 | 9.5 % (just short of 10 %) |
| + U1 + U2 (−0.16) | 11.53 | **10.8 % → fits** |
| alternatively + U2 + U3 without U1 (−0.31) | 11.81 | 8.6 % |

**Conclusion:** the cross-block items alone (≈ 0.73 mm²) close only about a third of the 1.97 mm² gap. Even with the owner shrinks, the chip reaches about 6 % margin, not 10 %. **Reaching ≥ 10 % needs at least one user decision.** The best single option is U1 (off-chip ring supply, which needs pads and a PDN-04 re-proof); with U2 it fits at 10.8 %.

If the user declines all U-items, the remaining levers are:
- deeper owner shrinks: wrx_cap toward 70 % utilization (about −0.1 more), and the attached_tx_buffer, which is on no list;
- accepting about 6 % routing margin, which is risky given that the v5 placer already fails from fragmentation at nominal −2.15.

## 5. Flags for the coordinator
1. **User decisions:**
   - U1: ring supply off-chip, with the pin cost;
   - U2: lose simultaneous off-chip I/Q;
   - U3: ESD_TEST learning structure.
   - U4: recommend no.
2. **Stale/incorrect records found:**
   - `netlist.py` binds the removed `cdr.freq_hold`/`cdr.FBCK_IN`.
   - pll_host outputs are unbound, so host_follow does not exist in the v5 netlist at all.
   - `contract.json` USB `host_follow100MHz SDR` contradicts AC-1.
   - Register-map F1 is still open.
3. **Not on any shrink list but oversized:** cdr (0.209, X3), attached_tx_buffer (0.155), and the dac abstract bbox (0.185 versus 0.126 evidence).
4. **Owner input:** wrx_cap leaf-cell area is about 0.25 mm² in a 0.938 bbox (27 %).
