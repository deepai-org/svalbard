# Consolidation pass 4: sharing review against the first complete instance list (2026-11-14)

Analysis and proposals only. No design file was changed. Paper pass: scripts, no simulation.

Inputs that no earlier pass had: `integration/top/pt_chip.conn` (346 instances, every pin bound), `decisions.md`
(D- rows), `spec/power-delivery.md` (measured currents, 10 islands), the mode walk, and the regfile rule
`rf_wired_payload_exclusive` (`rtl/pt_regfile.sv:1082`): no RF payload block (ADC, DAC, LNA, rfdriver) can be active
while `wiredtx`, `cdr` or `usbdrive` is active. That rule is the proof of mutual exclusion used below.

Work dir `scratch/reviews/consolidation-pass-4/`: `inventory.py` (parses the conn file with the chip-top parser),
`inventory.csv` (one row per instance: class, area, current, modes, island, pins, control pins, tied pins),
`inventory.md` (by master, by class, duplicate list, partially used hardware), `review.md` (independent reviewer).

**Status of this file: sections 1-6 written before the adversarial review; section 7 holds the review result and
the final ranked list. Where they differ, section 7 wins.**

## 1. Inventory summary

346 instances, 83 masters. Areas are published outlines (`scratch/area-pass-4/util.json`), v5 abstracts for cells
without a GDS in that set, core intrusion for pads (width x (depth - 442 um)), and estimates for the 7 build
demands. Currents are the nominal column of `spec/power-delivery.md` section 1.

| Class | Instances | mm2 | Note |
|---|---:|---:|---|
| digital macro | 1 | 2.814 | 72-82 mA |
| pads, functional (rf_rx, rf_tx, ref, aux, hs_rx, usb, wire_tx) | 7 | 1.885 | core intrusion |
| converters (adc_i/q, dac_i/q) | 4 | 1.528 | repack lever AP4-4, not sharing |
| wrx_cap (published r6) | 1 | 0.956 | r7c is 0.29 (AP4-1) |
| baseband (bbfilter_i/q, ctle) | 3 | 0.817 | |
| oscillators (qvco, pll_cdr, pll_tx, aosc) | 4 | 0.798 | qvco 0.53 is spiral keep-out |
| pads, debug and fallback (bb_i, bb_q, wmon, tlp, wclk_in, wtx_ext) | 6 | 0.726 | the largest "not a payload path" item |
| bias / reference / monitor | 8 | 0.466 | core_bias 0.302 at 24 % utilisation |
| dividers (lo_mmd, qdum, prescale x3, obs_pre4 x7, wordclk) | 13 | 0.483 | lo_mmd 0.361 |
| PLL pieces (lo_lf, lo_pfdcp, cdr) | 3 | 0.401 | |
| ptrim | 1 | 0.290 | compact 0.026 exists, waits for the redesign |
| regulators (pll_vreg2, lo_vreg demand) | 2 | 0.255 | |
| wiredtx | 1 | 0.246 | |
| RF (lna, mixers, txsum, rfdriver) + LNA spirals | 11 | 0.365 | |
| island switches (5 today; 10 in PD2 = 0.427) | 5 | 0.236 | |
| **isolation cells** | **153** | **0.136** | **in no floorplan yet** |
| ATB (79 leaves, 7 groups, 2 pads) | 88 | 0.127 | 15 codes dead or waiting for char cells |
| detect, slicer, termination x2, clk_obs16, bb_tap x3, lo_obs x2, diff_clk_rx x4, the rest | 31 | 0.86 | |

Sum of the inventory: 13.74 mm2 against a 12.77 mm2 core (before the in-flight repacks).

Mechanical findings from the duplicate and tied-pin lists (`inventory.md`):

- 131 `iso_clamp` + 16 `iso_clamp_x4`: one 6-transistor AND gate in 906-1025 um2, 132 of them feeding the macro.
- 7 `obs_pre4`, 3 `prescale`, 4 `diff_clk_rx`, 3 `bb_tap`, 6 `pad_rf_pair`, 6 `tx_steer`, 2 `lo_obs`.
- Instanced but doing nothing as bound: `polyphase` (inputs, EN at VSS, outputs open), `steer_4/5` (IN at VSS),
  `lo_obs_q` (EN at VSS, a load dummy), `lo_mmd_qdum` (outputs open, 8 mA), the TMDS branch of `pad_txpad`,
  `wordclk` (3 of 4 outputs open), `wrx_cap.DW[19:0]` (open), `qvco.PRE` (a 2.4 GHz buffer with no load, ~3 mA),
  `core_bias` `VGEN_*` and `BIAS_lc_vco_reserved` (open), `tx_interlock` TMDS half.
- Built but not instanced: `pt_usb_txdrv` (0.031 mm2, USB-D7) and the `pt_char_*` cells (D-CHAR).

## 2. Classes examined and what came out

### 2.1 Oscillators, PLLs, dividers, regulators

| Question | Answer |
|---|---|
| One ring for wired TX and RX (loop-timed)? | No. SATA, PCIe, USB and DP need the TX on the local reference while the CDR ring tracks the partner (up to +/-350 ppm plus SSC). Loop timing removes a mode. Pass-2/3 rejection stands. Both rings are needed together in every quarter-rate and RATE8 mode. |
| Host clock and CDR on one ring? | Already done (X1). New: as bound, host_follow in RF modes cannot be enabled at all (D-HF). CM-1 (host clock straight from H2D or REF) removes the need for any ring in RF modes and costs two mux inputs that exist. Recommended on no-dead-chip grounds; it is not an area item. |
| pll_vreg2 channel as the QVCO regulator (rings and QVCO are exclusive)? | No. The channel is a native follower with 23-27 dB; the QVCO needs 49-59 dB (PD2-11). Two in series cost 0.6-1.0 V; the input is 3.19 V and the QVCO wants 2.55-2.75 V, and the supply trim only helps slow dies. The rings are on the east side, the QVCO on the west: a shared quiet rail would be 2-3 mm long. `lo_vreg` stays a separate build. |
| LO divider dummy `lo_mmd_qdum` (0.034 mm2, ~8 mA)? | Keep. It is the standard replica load and LO26 (QVCO never simulated with the real tank loads) is still open; removing it now would be a change with no evidence. But its outputs are open and the published `lo_mmd` still loads the I tank 100-170 fF more than Q, so today it costs 8 mA without achieving balance: the LO owner has to close LO26 with the repacked pair. |
| `lo_obs` + `lo_obs_q` on the tanks, `qvco.PRE` buffer unloaded | CP4-9: either drive `lo_obs` from `qvco.PRE` (removes two tank loads and `lo_obs_q`, 0.017 mm2) or gate the PRE buffer off (about 3 mA in every autonomous mode). LO owner's call after LO26. |
| Three `prescale` instances (D-CLK) | `prescale` and `prescale_conv` divide the same `WIRE_CK` by 2^a and 2^b. One ripple chain has every tap: CP4-7, one cell with two tap selects. Saves an instance that is not in the floorplan yet and makes CONV_CLK and HOST_CLK phase-related by construction (helps D-CONV). |
| Seven `obs_pre4` (D-OBS) | `obs_pre4_pll` (TXPH[1]/4) duplicates `clk_obs.IN9` = `PLL_TX_FBCK` (ring/N), which is already there; `obs_pre4_cdr` duplicates `PLL_CDR_FBCK`, which already crosses to the core as `fc_src[1]`. CP4-4 removes both and the PH1 taps (D-PHLOAD gets better). |
| `wordclk` (0.025 mm2, 2.3 mA) | Only `LDE` is used; it crosses pll -> wired through a clamp at ring rate, not benched (D-WORDCLK). CP4-8: put the /10, /20 counter inside `pt_wrx_cap` (the TX did the same). Redesign, wired RX owner. |
| `vco_replica`, `ring_osc`, `aosc` | Keep (pass-2/3). `ring_osc` is now also the speed monitor for the supply trim. |
| `polyphase` | Tied off in the top because its limiter outputs would short the QVCO tank (D-POLY). As bound it produces no data in any mode: CP4-2. |

### 2.2 Converters and small DACs

- ADC I/Q (4 SAR cores), DAC I/Q: no sharing. Wired capture needs 8 phases at 405-625 MHz; 100BASE-TX is 125 MBd and its decisions are in the FPGA; the conv island is off in wired modes, so the ADC cannot be the supply monitor.
- Slicer trims: 8 samplers x 10 bits + 8 `vsel` = 88 pins, `ptrim` 40, `vthdac` 16, bbfilter 2 x 36, core_bias 62: these are per-device calibration codes. A shared DAC with sample/hold per sampler was looked at and rejected: hold leakage on 1-2 mV offset steps needs refresh logic and a clock next to the samplers; not simple. What is worth doing is on the digital side (CP4-6): the fields do not exist yet (mode walk: 78 ports with no field), and when they are added they should be `live` single-rank fields, not shadow + active.
- `vthdac` (0.024 mm2) vs slicer trim: different ranges (hundreds of mV vs a few mV, IX-10). Keep.
- `hsbias`, termination trims, `ptrim`: single instances, nothing to merge.

### 2.3 Baseband and detectors

- bbfilter I/Q is already the TX reconstruction filter in TDD; in duplex the DAC goes to the mixers directly. No second filter exists, nothing to merge.
- CTLE vs RF baseband: GHz vs 20 MHz, no.
- `detect` (4 comparators, 0.173 mm2 at 20 % utilisation) already serves squelch, disconnect, OOB and receiver detect. It is a repack item (AP4-1), not a sharing item. HS-pair signal detect does not exist (MW-35) and would be a new demand.

### 2.4 Serializers, deserializers, capture

- TX: `wtx_serq8` replaces `wtx_serq4c` (the v6 reserve books only the growth). Already one core.
- Capture B / slicer B (R8-ARCH, 0.43 mm2 reserve): in RATE8 both banks run at once, so capture A cannot serve both. Capture B only ships the 40 edge samples to the macro; the CDR votes come from PD8. A burst-only alternative (multiplex bank B into capture A) would put a 2:1 mux in the S inputs of the capture, the path that only just passes at q625. Rejected: it spends risk on the one path that works. Noted for the wired RX owner: at 3.24 Gb/s the host link cannot stream data + edge words anyway, so capture B is a diagnostic at that rate; if RATE8 has to shrink later, capture B is the first candidate, by user decision.
- D2H/H2D gearboxes: no cell exists (D-D2H: the macro launches DDR itself). X6 (reserve 0.093 -> 0.031) stands.

### 2.5 Pads, ESD, termination, isolation

- Isolation cells: CP4-1 (below), the largest item of this pass.
- Debug and fallback pads take 0.73 mm2 of core. AP4-7 (BB_I/BB_Q/WMON on provider `asig_5p0` pads) removes 0.40 of that without touching a function and is the better lever where it applies. What this pass adds is pin sharing by mode, using RF/wired exclusion:
  - CP4-3: `WCLK_IN` function onto the `AUX_CLK` pad pair.
  - CP4-5: `WMON` onto a BB pad leg.
  - WTX_EXT onto BB_I was looked at and rejected (section 5).
- `steer_4/5` and the TMDS legs: already X5 / D-TMDS. Not counted again.
- `pad_rf_tx` is bound to master `pad_rf_pair` in the conn file; a separate 1 kV `pad_rftxpad` family exists in `analog/pads/generated/stress-safe-families/rf-tx/`. Same outline, so no area effect, but one of the two is wrong (CP4-R1).
- `pad_tlp` is bound to `pad_single_leg` (0.142 mm2 of intrusion if read literally); the v6 floorplan places the 124 x 68 um `pad_tlp_flat`. Record fix (CP4-R2).
- `tx_interlock`: 0.048 mm2 (v5 outline 139 x 345) for the mode interlock, with its TMDS half tied off. Not in the area-pass-4 utilisation table (no GDS in that set). Repack with X5 (CP4-R3, about 0.03).

### 2.6 Bias, reference, monitor

- core_bias: pass-2 "do not merge banks" stands. `bias_ext` is three bank outputs (about 0.004-0.009 mm2); un-tying `lc_vco_reserved` (D-BIAS) gives one of them for nothing.
- Mid-rail references: `refvcm` (demand), `txpad_bias` (demand), `HS_TERM_VCM` / `TERM_VCM` / `HS_VBIAS` (in `pt_termination`, 107 resistors, 1.25 mA), `VCM_MASTER`. `txpad_bias` (1.65 V into a gate) can be a tap of the `pt_termination` divider on the same island: avoids one build demand (about 0.003 mm2, CP4-10). `refvcm` must stay separate (2.4 GHz LO on that node, other side of the die).
- Supply / clock monitor (D-FAULT): `monitor.config.*` asks for reference present, input clock present, RF lock, wire lock, a supply mask and two timeouts. Every input already exists at the macro: `s_ref_present`, `s_aux/wclk/wtx_ext_present`, `s_pll_tx_lock`, `s_pll_cdr_lock`, `fc_src[5]` (LO), `island_pgood[5:0]`, `por_n`. CP4-11: `fault` is made inside the macro from these; no analog monitor is built; the `fault` pin goes away. Supply levels stay observable on ATB and through `ring_osc` on the frequency counter.
- POR, aosc, refbuf: keep.

### 2.7 Digital macro

Not re-derived here (the macro is mid-rework: TOP-1..18). Points that follow from the conn file:

- 132 island -> macro clamps belong inside the macro (CP4-1).
- 80 orphan fields (397 bits) and `monitor.config` (75 bits) are stored today with no consumer; 78 control ports (most of 522 control bits) have no field. The rework should come out about even. CP4-6 keeps it from growing: calibration-only codes (slicer trims 80, vsel 8, ptrim 40, vthdac 16, hsbias 8, bandgap and biasgen trims, termination trims: about 250 bits) as `live` fields. Shadow + active buys an atomic commit and the rule check; neither applies to an offset code. Gains, filter codes, enables and states stay shadow + active (GX-4 hop-boundary switch needs them).
- `pt_clocktree_slow` launch logic models a serializer that no longer exists (D-CT): delete with the rework.
- FIFO sizing per exclusive mode and per-lane time sharing: covered by digital-sharing-plan S1-S8; nothing new found from the conn file.

### 2.8 Characterization structures

`pt_char_ro33/ro50/cmldiv/rffet/atb` are published and not placed (D-CHAR); 24 ATB leaves and `clk_obs.IN15` wait for them. `ring_osc` (58 devices, 165-255 MHz) and `pt_char_ro33` are both free-running 3.3 V rings on the debug island. If they are the same structure, `ring_osc` can sit on IN15A and `pt_char_ro33` need not be placed. Not verified (cell contents not compared): CP4-R4, question to the characterization owner.

## 3. Ranked candidates (before review)

Score = area x confidence. "Avoided" means the item is in the conn file but in no floorplan yet, so the saving is against the honest demand, not against v6.

### 3a. Free: identical or digital cells, no analog performance path touched

| ID | Merge | mm2 | mA | Capability check | Adds / risk | Verify | Owner | Conf. |
|---|---|---:|---:|---|---|---|---|---:|
| CP4-1 | 132 island -> macro clamps (121 `iso_clamp`, 11 `iso_clamp_x4`) become hand-instantiated standard-cell AND2 (`dont_touch`) at the macro input pins; ISO from the macro's own `island_off[k]`. The 14 clamps whose receiver is on an island rail stay. | 0.121 avoided | 0 | Same function (Y = A and not ISO, receiver domain = core VDD = macro rail). A floating A cannot draw crowbar current in a NAND-based AND with the other input low. | +132 cells (about 0.003 mm2) in the macro. Removes the custom clamp's 0.9-2.1 ns delay into 200 fF and puts the crossing inside the macro STA (D-ISO item 2). Risk: synthesis must not restructure the cells; a floating net now runs to the macro edge (gate only, same as today's clamp input). | boundary sim already exists (`sim/tb_top_boundary.sv`); add one transistor-level DC check of the AND2 with A swept and ISO = 1 | digital + chip-top | 0.8 |
| CP4-2 | `polyphase`: delete, or give it an input and an output it can drive | 0.039 | 0 (EN = 0) | As bound it has no source, no load and no enable in any mode, and it fails extracted. No capability or data is lost by deleting what is bound today. | None. Memory says learning structures are in scope: needs the user's yes. Alternative that keeps the learning: outputs to `clk_obs.IN0` through an `obs_pre4`, input from AUX_CLK. | none | timing/LO + user | 0.6 |
| CP4-4 | `obs_pre4_pll`, `obs_pre4_cdr` -> use the rings' own `FBCK` (IN9 exists; IN14 takes `fc_src[1]`) | 0.007 avoided | 2 when on | Same clock divided by N (4/8/5/10) and not by 4. FBCK runs whenever the ring runs. | Removes two gate loads from PH1 (D-PHLOAD). Frees `clk_obs.IN8`. Loss: none if FBCK is alive; if the feedback divider is dead the ring is observable only through `ATB_VCTRL`. | none | timing | 0.7 |
| CP4-6 | New calibration fields as `live` (single rank) | about 0.03 avoided in the macro (250 FF) | - | No atomic commit on offset codes. | Rule check does not see these fields (none of the 16 rules reads a trim). | regfile checker | digital | 0.6 |
| CP4-10 | `txpad_bias` = tap of the `pt_termination` divider | 0.003 avoided | 0.1 | TX termination and RX termination are on the same island and on together in wired modes. | Divider tap loaded by a gate only. | DC check | wired RX + pads | 0.5 |
| CP4-11 | `fault` made in the macro; no analog supply / clock monitor | 0.02 avoided (estimate of a block that was never sized) | - | Every `monitor.config` condition has its input at the macro already. | A supply dip shorter than the POR response is not seen (it is not seen today either). | RTL | digital + coordinator | 0.7 |

### 3b. Needs a user decision: a pin carries two functions by mode (no circuit redesign)

| ID | Merge | mm2 | mA | Capability check | Adds / risk | Verify | Owner | Conf. |
|---|---|---:|---:|---|---|---|---|---:|
| CP4-3 | Forwarded wire clock (`WCLK_IN`) enters on the `AUX_CLK` pair. Delete `pad_wclk_in`, `rx_wclk_in`, `obs_pre4_wclk`, 2 clamps. `cdr.WCK_IN` and `clockmux.WCK` take `AUX_CK_P`. | 0.174 | 3.5 + 1 (debug island) | AUX_CLK is the LO Q leg only in RF external-LO modes; WCLK_IN is used only in wired modes (TMDS clock, CDR fallback). The two never run together (`rf_wired_payload_exclusive`). `rx_aux_clk` is the same receiver cell on the same pad family that is already bound as a clock input. | Loses AUX and WCLK as two different clocks at the same time in a wired mode (REF_IN stays for the TX ring). The clock crosses the die (pad on the west, rings on the east): the AUX route does that already. Pad sees `lo_ext` (off) as a load; board AC coupling 10 pF per leg is for 2.4 GHz and must be re-chosen for a 25-340 MHz clock (B3, B16). **Frees two pad sites: the POR strap and the LNA ground split are competing for two sites today.** | bench `rx_aux_clk` at 25-340 MHz through the refpad model | user -> pads, timing, board | 0.5 |
| CP4-5 | `WMON` leaves on a BB_Q pad leg; `bb_tap_wmon` stays where it is and its output is routed to that pad. Delete `pad_wmon`. | 0.142 (0 if AP4-7 lands first: then it frees one provider site) | 0 | WMON observes the wired RX; BB_Q the RF baseband. Exclusive by the same rule. Both taps are the same cell with a high-Z off state. | 2-3 mm analog route across the die: about +0.5 pF on the BB_Q leg (pole of the 100 ohm follower stays above 1 GHz), I/Q observation asymmetry of that amount, coupling from the macro into a debug path. Board: one test point with two uses. | bb_tap bench with +0.5 pF | user -> rf_rx, pads, assembly | 0.4 |

### 3c. Needs redesign (small cells)

| ID | Merge | mm2 | mA | Capability check | Adds / risk | Verify | Owner | Conf. |
|---|---|---:|---:|---|---|---|---|---:|
| CP4-7 | `prescale` + `prescale_conv` -> one chain, two tap selects | 0.013 avoided | 2 | Both divide `WIRE_CK` by a power of two; any pair of ratios stays available. | Second tap mux on the chain; CONV_CLK jitter path gains one mux (budget 20 ps rms). | extracted rerun of one small cell | timing | 0.6 |
| CP4-8 | `wordclk` counter moves into `pt_wrx_cap` | 0.025 + 1 clamp | about 1 | LDE is its only used output; capture B takes LDE from capture A. | Touches the capture, which is in its gating runs (r7c). Do it only with the next capture revision. Removes a ring-rate island crossing that was never benched and one load from CDR PH0. | capture gating set | wired RX | 0.4 |
| CP4-9 | `lo_obs` driven from `qvco.PRE`; delete `lo_obs_q`. Or: gate the PRE buffer off. | 0.017 | 3 (PRE) | LO stays observable on CLK_OBS independent of the MMD. | Needs LO26 first. PRE load limit 30 fF. | LO owner | timing/LO | 0.3 |

Totals before review: free 0.22 mm2 (0.16 of it avoided demand), 2 mA; user decision 0.32 mm2, 4.5 mA, two or three pad sites; redesign 0.055 mm2, about 6 mA.

## 4. Assumptions of earlier passes that are now stale

| Earlier statement | Now |
|---|---|
| Pass 2: "Area is not the binding constraint", "pads are not scarce" | The die is fixed and short by 1.4-3.0 mm2; two freed pad sites have three claimants (POR strap, LNA ground split x2). Pin sharing by mode is back on the table (CP4-3, CP4-5). |
| Pass 2: sharing WCLK_IN with WTX_EXT rejected because both fallbacks run together | Still true for that pair. The exclusive partner of WCLK_IN is AUX_CLK (RF-only as LO_Q), which pass 2 did not look at. |
| Pass 2/3: `prescale` is one TSPC /16 for the autonomous LO feedback | The LO has its own `lo_mmd`; `prescale` is now three instances dividing ring clocks (D-CLK). |
| Pass 2: `wordclk` shared TX/RX | TX has its own dividers; `wordclk` serves one RX pin (D-WORDCLK). |
| Pass 2: "keep polyphase as a learning structure" | It cannot be connected: its outputs fight the QVCO tank (D-POLY). Tied off, it teaches nothing. |
| Pass 3: U1 off-chip ring regulator | Ruled out by the user (only passives, FPGA, fallback LNA off-chip); `pll_vreg2` is one dense cell now. |
| Pass 3: 5 island switches, 0.236 mm2 | PD2: 10 islands, 0.427 mm2. |
| Pass 3 / v6: isolation not counted | 153 cells, 0.136 mm2, in no floorplan. |
| Pass 3: U2 (merge BB_I and BB_Q) loses simultaneous I/Q | Still true; not re-proposed. CP4-5 shares with WMON instead, which is never simultaneous. |
| Pass 3: `vreg_tx` + `vreg_cdr` = 0.482; "one shared regulator rejected" | Done as one cell with two outputs (0.173). The same question for the QVCO has a numeric no (section 2.1). |
| Digital sharing plan S8: "wired and RF islands can be configured at the same time", so no banking of analog config | Still true for configuration, and kept. But the trims it protects mostly do not exist as fields yet; add them single-rank (CP4-6). |
| TX and RX are TDD (bbfilter shared as the TX filter) | Duplex is accepted (GX-3); in duplex the TX path is unfiltered. No area consequence, but the TX spectrum in duplex has no reconstruction filter: RF owner should state it. |
| Supply / clock monitor "to be built" (D-FAULT) | Its register fields describe a digital function whose inputs all exist (CP4-11). |
| Area pass 4: "island switches, merging saves 0.03, not worth it" | Agreed; with 10 islands the question was re-asked for exclusive pairs (rf_rx with wired_rx): a shared switch would power both and lose the isolation of a shorted block. No. |

## 5. Looked at and rejected

| Candidate | Reason |
|---|---|
| Loop-timed TX (one ring) | Removes independent TX clocking (SATA/PCIe/USB). |
| pll_vreg2 channel or a cascade as the QVCO rail | 23-27 dB against 49-59 dB; 0.6-1.0 V of dropout does not fit; opposite sides of the die. |
| Dropping `lo_mmd_qdum` or `lo_obs_q` now | No evidence either way until LO26 (QVCO with real tank loads) is run. |
| `vco_replica`, `ring_osc` removal | Unique open-loop observations; 0.03 mm2; `ring_osc` is the trim monitor. |
| ADC as wired sampler, 100BASE-TX front end or supply monitor | Rate, island (off in wired modes), and a monitor must be always-on. |
| One calibration DAC + sample/hold for slicer / ptrim / filter trims | Refresh clock at the samplers, leakage against 1-2 mV steps; not simple, and the trim DACs are a small part of the cells. |
| Serial configuration chain per island (522 control wires -> a few) | Would cut top-level routing, but contradicts the decision of 2026-11-13 (decode in the macro, one port per control) while that rework is in progress, and island state would be lost at power-down. Reopen only if top-level routing fails on control wires. |
| Capture B replaced by multiplexing bank B into capture A | Puts a mux in the q625 critical path. |
| WTX_EXT onto the BB_I pair (exclusive by mode) | WTX_EXT carries line-rate data from the FPGA to the east side; from a west pad it is a 2-3 mm route at up to 3.24 Gb/s with the bb_tap and inject switches on the pad. The fallback would not work at the rates where it is needed. |
| WMON onto WTX_EXT or WCLK_IN | All three are wired fallbacks that can be in use together. |
| Merging BB_I and BB_Q (U2) | Loses simultaneous I/Q (unchanged). |
| `bb_tap_wmon` deleted, WMON_IN muxed into `bb_tap_q` | A 0.7 GHz high-impedance node routed 2-3 mm. Keep the buffer at the source. |
| `refvcm` shared with `VCM_MASTER` or the TX buffer reference | LO on the node; other side of the die; 0.003 mm2. |
| Bias bank merge, shared outputs for exclusive consumers | Outputs are about 1.4k um2 each; current steering between two diodes is not simple. |
| Shared island switch for exclusive islands | Loses fault isolation; saves at most the master quantisation. |
| `pt_rxlevel`, `pt_termination` decode into the macro | They hold the resistor strings and drive pad-side switches on the wired rail; the logic part is small. Not examined to device level. |
| CTLE or detect shared with RF baseband | Different bandwidth by 50x. |

## 6. Record fixes found on the way (no hardware change)

- CP4-R1: `pad_rf_tx` master (`pad_rf_pair` in the conn vs the `rf-tx` family).
- CP4-R2: `pad_tlp` master (`pad_single_leg` in the conn vs `pad_tlp_flat` in the floorplan).
- CP4-R3: `tx_interlock` 0.048 mm2 is on no utilisation or repack list.
- CP4-R4: `ring_osc` vs `pt_char_ro33`: same structure?
- `pt_usb_txdrv` (USB-D7) is not in `pt_chip.conn`.
- `qvco.PRE` buffer runs unloaded in every autonomous mode.
- The inventory sum with honest pieces is 13.74 mm2 against 12.77 mm2 of core before repacks: the die-fit study should start from `inventory.csv`, not from the v6 block list.
