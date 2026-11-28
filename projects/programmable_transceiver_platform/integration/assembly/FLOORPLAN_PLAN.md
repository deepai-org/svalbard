# Floorplan plan: pt_rf and pt_wired (connectivity-driven)

Current state, 2026-11-26. The plan is coded behind `PLAN_FP=1` (section 9). The plan sets the positions of the major blocks,
the routing channels that stay free of blocks, and the side and order of the digital macro's pins. It replaces the
packer floorplan (die-fit `fit.py`, which does not see connectivity) once it is coded behind a switch (section 9).
Files: `fp_plan/` (positions, channels, pin-order files, drawings, the planning scripts).

## 1. Summary

- **Why routing fails today.** The power grid (power-delivery G1) runs its straps across the router's preferred
  directions: Metal4 straps are horizontal while signal Metal4 is vertical, and Metal5 straps are vertical while signal
  Metal5 is horizontal (tech LEF). Every long top-level net therefore runs on Metal2 (vertical) and Metal3 (horizontal),
  plus Metal1 (horizontal) with `SIG_M1=1`. Blocks obstruct Metal1-3 over their whole outline (`kl_abstract`), so all
  long routing has to go through the gaps between blocks. The packer leaves gaps of 4-15 um, and the macro's control
  pins face away from their consumers (pt_rf: 112 `c_*` pins on the north edge and 137 on the west edge, of 279).
- **The plan:** blocks grouped by signal flow, explicit routing channels (trunks) from the macro's south edge to each
  consumer field, and every macro pin on the edge that faces its net (pt_rf: 360 S, 77 W, 59 E, 8 N; pt_wired: 510 S,
  47 W, 72 E, 14 N).
- **Rulings applied (coordinator, 2026-11-26).** The grid straps are swapped to Metal4 vertical / Metal5 horizontal,
  so they run along the tech-LEF directions (`GRID_SWAP=1`, the default; section 7.1). The host-link cluster (`h2d_*`,
  `d2h_*`, `host_word_clk`) keeps its hardened macro position for matched skew, and its bond nets are routed to the
  pads as a bundle (section 6). Decap goes into the low-use channels: 36 of 36 tiles on pt_rf, 69 of 69 on pt_wired.
- **Model result (section 7).** I ran a gcell global route at 20 um on all 1059 / 1200 nets (KH_CONN=1, `SIG_M1=1`,
  swapped grid). Against the packer floorplan on the old grid, using the same model:

| | pt_rf packer | pt_rf plan | pt_wired packer | pt_wired plan |
|---|---|---|---|---|
| Channel gcells over 70 % vertical | 1093 | 3 | 536 | 7 |
| Channel gcells over 100 % vertical | 459 | 0 | 311 | 3 (pad sliver, 7.3) |
| Worst key cut line | 0.84 | 0.27 | 1.37 | 0.18 |
| Worst named channel | - | 0.60 | - | 0.58 |
| Wire length (mm) | 2878 | 1189 | 3434 | 1592 |

- **Open (section 8).** Some items need an owner decision: the LO branch to lo_txbuf (2.8 mm, LO-ASM-6 asks for
  2.1 mm), isw_pll away from its supply bond on both chips, and adc_q 709 um from the macro (SUB-01 pessimistic case
  asks for 782 um).

## 2. Inputs and block list

My own runs: `scratch/integration/fpplan-rf` and `fpplan-wired`, made with `KH_CONN=1 run.sh <chip> abstract floorplan place`
on HEAD 0f490350 plus the shared working tree of 2026-11-26 (DG9-29/30 macros). Block outlines and pins come from
`lef/*.lef` of those runs. Pad footprints come from `pads.json` and `fp_pads.json`. Die 3932 x 5122 um, core
452-3480 x 452-4670 um.

Major blocks (w x h um, unrotated):

- **pt_rf** (8.63 mm2 major blocks, 0.28 mm2 small cells, 0.54 mm2 decap; core 12.77 mm2 minus about 0.9 mm2 of pad
  keep-out): digital 1716x1366, qvco 880x673, adc_i/q 480x936, lo_vreg 408x1094, bbfilter_i/q 586x641, lo_mmd 378x956,
  core_bias 713x314, lo_lf 403x482, pll_cdr 221x794, pll_vreg2 445x389, lo_ext 369x419, lna 294x469, dac_i/q 669x201,
  lo_pfdcp 257x483, refbuf 391x299, pll_tx 261x386, rfdriver 476x203, clk_obs 196x470, lna_ind_p/n 290x296, cdr 259x320,
  lo_vtdet 156x435, char_rffet x3 260x260, isw_wired x3 264x243, rxmix_i/q 190x301, isw_rf 232x215, lo_txbuf 162x245,
  lna_deg_p/n 170x176, txmix_i/q 235x91, and switches, taps, observers, 69 ATB leaves, 7 ATB groups, 8 isolation cells.
- **pt_wired** (5.29 mm2 major, 0.36 small, 1.25 decap): digital 1676x1593, wrx_cap 1239x261, wiredtx 744x431,
  core_bias 692x258, pll_cdr 221x794, detect 251x690, pll_vreg2 445x389, slicer 299x368, ctle 203x511, pll_tx 261x386,
  clk_obs 196x470, cdr 259x320, term_buffer 157x480, isw_wired x3 264x243, termination 141x342, tx_interlock 139x345,
  ptrim 201x236, and 63 ATB leaves, 15 isolation cells, 69 decap tiles.

## 3. Connectivity matrix (KH_CONN=1)

Net counts (hook nets excluded):

| | pt_rf | pt_wired |
|---|---|---|
| All nets | 1059 (384 hook) | 1200 (367 hook) |
| `c_*` macro control | 279 nets, 314 receiver ends | 409 nets, 418 ends |
| ATB (leaf selects, buses) | 109 | 97 |
| Converter data (ADC codes 2 x 20, DAC samples 2 x 11 + clock) | 74 | - |
| Host link / HS data (hs) | 30 | 105 |
| RF / LO | 35 | - |
| Clocks | 28 | 49 |
| Island rails, regulator outputs | 10 | 7 |
| Macro nets in total | 504 (+65 tie-offs) | 643 (+70 tie-offs) |

**pt_rf, block pairs (nets):** macro-core_bias 75 (71 ctl), macro-bbfilter_i 37, macro-bbfilter_q 37, macro-adc_i 31
(20 code bus), macro-adc_q 31, macro-ring S 21 (D2H 11, SPI 4, reset; 61 cell ends), macro-clockmux 20, macro-ring N 16
(H2D 11, debug/obs), macro-lna 16, macro-clk_obs 14, macro-dac_i 13, macro-dac_q 13, macro-cdr 12, macro-pll_cdr 11,
macro-rxmix_i/q 9 each, bbfilter_i-bbfilter_q 9, macro-lo_mmd 8, macro-rfdriver 8, macro-qvco 7, adc_i-adc_q 7,
lo_ext-qvco 6 (LOI 4), lo_ext-ring E 4 (REF/AUX), lo_ext-lo_txbuf 4 (LO), and analog pairs of 3-4: lna-rxmix,
rxmix-bbfilter, bbfilter-txmix (BBI_TX), bbfilter-bb_tap, txmix-txsum-rfdriver, lo_txbuf-txmix, qvco-lo_mmd/obs/qdum,
cdr-pll_cdr, core_bias to each analog block (bias, enable, rail). Every island rail touches core_bias (`RAIL_*`).
**pt_rf, ring sides:** S = macro only (D2H, SPI, reset); N = macro (H2D, debug, ATB pads); W = RF_RX, BB_I/Q (taps),
RF_TX; E = REF / AUX (lo_ext, rx_ref_in, rx_aux_clk, refvcm), por bypass.

**pt_wired, block pairs:** macro-wiredtx 98 (43 hs data, 54 ctl), macro-slicer 89, macro-core_bias 62,
macro-wrx_cap 52 (43 capture data), macro-ptrim 41, macro-ring S 21, macro-vthdac 17, macro-ring N 16,
slicer-wrx_cap 16, macro-clockmux 15, macro-cdr 14, macro-ring E 13 (pad controls), macro-clk_obs 13, macro-detect 12,
macro-pll_cdr 11, ring E-termination 11, cdr-pll_cdr 11, macro-usb_txdrv/wtx_fallback/termination/hsbias 9 each,
ptrim-wrx_cap 9 (phases), pll_cdr-ptrim 8, pll_tx-wiredtx 8, ptrim-slicer 8, ring E-usb_txdrv 8, macro-ctle 8.
**pt_wired, ring sides:** E = HS RX, USB, WIRE_TX, WTX_EXT pads and their controls; W = WMON, REF, AUX, TLP.

**Macro pin sides today (DG9-29/30 LEF):** pt_rf S 166, N 123, E 26, W 254 (of 569), `c_*`: N 112, W 137, S 15, E 15.
pt_wired S 265, N 16, E 209, W 223 (of 713). For both chips the consumers lie south of the macro.

## 4. Constraints (from the spec; plan value, pass or fail)

| Constraint | Source | pt_rf plan | |
|---|---|---|---|
| LNA at RF_RX pad, RF in short | die-fit T, MANDATE 5 | LNA 46 um from pad footprint, RF_RX route about 720 um pin to pin (LNA pins all on one local edge) | marginal |
| lna_ind_p/n, lna_deg_p/n within 8 um of LNA | common.FLOW_ADJ, HARD_NEXT_TO (ASM-15) | all four at 8 um (LNA rotated W, 469 um edges carry two spirals each) | pass |
| rxmix within 100 / 150 um of LNA, 60 um of each other, 120 um of lo_ext | FLOW_ADJ | 100 / 100, 40, 120 / 120 (gaps kept at the limit for the routing spine) | pass |
| bbfilter within 100 um of rxmix, ADC within 100 um of bbfilter | FLOW_ADJ | 29 / 20, 100 / 60 | pass |
| TX: rfdriver within 150 um of RF_TX pad, txmix/txsum/lo_txbuf/DAC adjacency | FLOW_ADJ, GROUP_BOOK (lo_txbuf abuts txmix) | 43; 9 / 9 / 8 / 161-173 | pass |
| rfdriver from LNA 1000, ADC_I 839, core_bias 340 um | risk register SUB-07 | 2057 / 2684 / 1022 | pass |
| rfdriver at least 1 mm from both ring PLLs | LO-03 | 2203 (pll_tx), 2321 (pll_cdr) | pass |
| QVCO cell edge at least 1500 um from the west edge and 800 um along the edge from the RF_TX band (spirals 1.7 / 1.0 mm) | LO-01, INT23 (integration-m23 path 1) | 2580 / 2350 | pass |
| Macro to LNA 1000, QVCO 300, ADC 210, bbfilter 100, core_bias 100 um | die-fit v6 RULES, SUB-02 | 1290, 1373, 709 (adc_q) / 1916, 504 / 1614, 100 | pass |
| Macro to ADC 782 um (pessimistic substrate bound) | SUB-01 (integration-m23: "+1 dB at 782 um") | adc_q 709 | **open** |
| Macro to DAC: no number in the spec (22 um fails the pessimistic bound) | SUB-12 | 115 (dac_i) | open (no rule) |
| Macro to bbfilter at high PGA gain: not bounded | SUB-13 | 504 (bbfilter_q) | open (no rule) |
| Ring PLLs from QVCO 500, ADC_I / bbfilter_I 200 um; lo_txbuf from LNA 300 and QVCO 200; txmix from pll_cdr 300 | die-fit RULES, FLOW_KEEPAWAY | at least 1029 everywhere | pass |
| LO bundle at least 200 um from LNA, spirals, RF pad, QVCO | XT-01 | LO to the mixers: 160-390 um, between the mixers and lo_ext, inside the RX cluster (the bundle never passes the spirals); LO to lo_txbuf: about 3.4 mm pin to pin up the west trunk, at least 200 um from the LNA cluster | pass (route rule) |
| LO branch lo_ext to lo_txbuf at most 1.2 mm (pull), about 2.1 mm (LO-ASM-6) | FLOW_ADJ, LO-ASM-6 | 2.8 mm edge to edge, 3.4 mm pin to pin | **fail**: fixed by the RF_RX and RF_TX pad sites, 2.5 mm apart (section 8) |
| Island switch at its supply bond | power delivery G4 | rf_tx 4, conv 4, lod 0, lo 182, rf_rx 248, debug 314 um; isw_pll 2338 um (beside pll_vreg2) | **isw_pll open** |
| isw_pll beside pll_vreg2 | power owner (README island plan) | 10 um | pass |
| isw_rf_tx_b touching the RAIL_rf_tx bar (465 um south of isw_rf_tx) | HARD_NEXT_TO, ISLAND_BARS | touching | pass |
| No block in the macro escape rows; decap at the macro | ASM-11 (channels), power delivery 5 (bank) | escape rows free; 36 of 36 decap tiles placed (some in low-use channels, 7.4) | pass |
| Noisy digital to sensitive analog guard rings, deep n-well | MANDATE 5: only where an analysis shows a need | none drawn by the plan; distances above | - |
| ESD | MANDATE 1: basic class; no floorplan rule | - | - |

pt_wired: wiredtx and isw_wired_tx_a/_b stay at their power-delivery 4.1c positions (`common.FIXED_PLACE`), the
RAIL_wired_tx bar and `chan_wtxdata` stay, and the 14 fixed decap tiles stay inboard of pad_hs_rx (PAD-13 CDM). Rules
that pass: ctle 45 um from pad_hs_rx (60), slicer-ctle 10 (60), ptrim-slicer 59 (60), pll_cdr-ptrim 17 (80),
cdr-pll_cdr 11, pll_tx-wiredtx 10 (150), wrx_cap-slicer 162 (200), cascode_pump-pad_wire_tx 54 (60),
termination / usb_txdrv / term_buffer / tx_interlock / rx_wtx_ext at their pads, vthdac-slicer 10, macro-core_bias
119 (100). These fail or stay open: detect-pad_hs_rx 238 (150; the decap slot holds the pad's inner side),
wrx_cap-macro 1646 (300; wrx_cap stays with the slicer it samples, and its 43 capture outputs run up trunk T),
rx_ref_in / rx_aux_clk 463 / 161 from their pads (the macro sits 27 um from pad_ref and pad_aux_clk, so the
receivers go below pad_aux_clk), isw_wired_rx 1125 um and isw_pll 4077 um from their bonds (the current packer floorplan also has both far from their bonds).

**Pads.** No pad map change is needed for this plan. Fixed: provider supply sites, D2H on the south and H2D on the
north (RTL bank directions, fpga-connection-plan, interface HL-RATE), the 74-wire bond layout. Kept on technical merit:
RF_RX / BB_I / BB_Q on the west middle (PC-26 B), RF_TX at the north-west corner (TX-RX isolation, SUB-07 needs 1 mm
from the LNA), REF / AUX on the east (moving them beside RF_RX worsens XT-08). The only pad-related lever that remains
is the LO branch length, and it would mean moving RF_TX south. That would break SUB-07, so it is not proposed.

## 5. Placement plan

Drawings: `fp_plan/pt_rf_plan.svg`, `fp_plan/pt_wired_plan.svg` (blocks, channels in blue, macro pins as dots, routing
utilisation heat of the model). Positions: `fp_plan/<chip>_place.json` (`hand` = placed by this plan, `auto` = small
cells and decap the planning script put next to their partner; the packer may do the same).

### 5.1 pt_rf

```
+--------------------------------------------------+
|                                                  |
|                                                  |
|                                                  |
|                                                  |
|############  .@@@@@@@@@@@@@@@@@@@@@@WWWWJJ       |
|############  .@@@@@@@@@@@@@@@@@@@@@@WWWWJJ       |
|#####SSSSSSS  .@@@@@@@@@@@@@@@@@@@@@@   JJJ       |
|     SSSSSSS  .@@@@@@@@@@@@@@@@@@@@@@TTTJJJ       |
|     tttthssss.@@@@@@@@@@@@@@@@@@@@@@TTTJJJ       |
|     ppphhhNNN.@@@@@@@@@@@@@@@@@@@@@@TTTw         |
|     bbbbOONNN.@@@@@@@@@@@@@@@@@@@@@@rrrw         |
|     bbbbOONNN.@@@@@@@@@@@@@@@@@@@@@@############ |
|     ...OOONNN.@@@@@@@@@@@@@@@@@@@@@@############ |
|     ...OOONNN::::HHHHHHHHH.zzzKKKKKKRRRRRq       |
|     ....QQQQQ.:::HHHHHHHHH..  KKKKKKRRRRRq       |
|     ccccQQQQQ::::::FFFFFFFFiiiKKKKKK############ |
|     cccgggvv ::::::FFFFFFFFiii:::::############# |
|############  ::::::FFFFFFFFBBBBBBBBBBBB::        |
|############  ::.:::FFFFFFFFBBBBBBBBBBBB mm       |
|############VVVVoo. FFFFFFFFBBBBBBBBBBBBdmm       |
|############VVVVoo.ffff.LLLLLLkkxxx:::: ddd       |
|############MMMMMM.eeee.LLLLLLkkAAAAAAAAAAA       |
|############UUUUnn.eeeeELLLLXX::AAAAAAAAAAA       |
|############UUUUnn..EEEEEEEEXX::AAAAAAAAAAA       |
|############UUUUCCC.EEEEEEEEXX yAAAAAAAAAAA       |
|     uu aaa::CCCCCC.EEEEEEEEXXGyGGGGGGGGGAA       |
|     uulaaa::CCCCCC.EEEEEEEE GGGGGGGGGGGGjj       |
|     lllZZZ::CCCCCC.IIIIIPPPPGGGGGGGGGGGGjj       |
|        ZZZ::CCCCCC.IIIIIPPPPDDDDDDDDDDDDDD       |
|        YYY  CCCCCC.IIIIIPPPPDDDDDDDDDDDDDD       |
|        YYY  CCCCCC.IIIIIPPPPDDDDDDDDDDDDDD       |
|                                                  |
|                                                  |
+--------------------------------------------------+
```
1 char = 80 um wide x 160 um tall; @ digital macro, # pad keep-out, . reserved routing channel, : decap.

A=qvco, B=adc_q, C=adc_i, D=lo_vreg, E=bbfilter_i, F=bbfilter_q, G=lo_mmd, H=core_bias, I=lo_lf, J=pll_cdr, K=pll_vreg2, L=lo_ext, M=lna, N=dac_i, O=dac_q, P=lo_pfdcp, Q=refbuf, R=pll_tx, S=rfdriver, T=clk_obs, U=lna_ind_p, V=lna_ind_n, W=cdr, X=lo_vtdet, Y=char_rffet, Z=char_rffet_open, a=char_rffet_short, b=isw_rf_tx, c=isw_rf_tx_b, d=isw_lod, e=rxmix_i, f=rxmix_q, g=isw_rf_rx, h=lo_txbuf, i=isw_pll, j=isw_debug, k=lo_mmd_qdum, l=isw_conv, m=isw_lo, n=lna_deg_p, o=lna_deg_n, p=char_atb, q=rx_ref_in, r=rx_aux_clk, s=txmix_i, t=txmix_q, u=bb_tap_i, v=bb_tap_q, w=vco_replica, x=lo_obs_q, y=lo_obs, z=clockmux

Regions:
- **Macro** at x 1236-2952, y 3304-4670 (north edge, as today; 41 um from the pad_aux_clk footprint).
- **TX column, north-west** (x 452-1121): rfdriver (FN) under pad_rf_tx; txmix_q, lo_txbuf, txmix_i and txsum under
  it; dac_q / dac_i vertical (E, pins top-right toward txmix and the macro's west edge); isw_rf_tx at its bond (W
  3510), its 465 um Metal5 bar south of it, then isw_rf_tx_b; refbuf, isw_rf_rx, bb_tap_q, char_atb in the rest.
- **RX cluster, west middle at RF_RX:** LNA (W, 469 um edges) with ind_p and deg_p below and ind_n and deg_n above,
  all at 8 um; rxmix_i / rxmix_q stacked 100 um east of the LNA; lo_ext (W, pins facing the mixers) 120 um east of the
  mixers; bbfilter_i below (pins bottom-left toward adc_i) and bbfilter_q above (S, pins top-right toward adc_q and the
  core_bias channel); adc_i (FN) under the LNA cluster; adc_q (FE) east of bbfilter_q.
- **core_bias** (S: 43 control pins face north) 100 um under the macro. pll_vreg2 and isw_pll are east of it.
- **LO synthesiser, south-east:** qvco (pins west, toward lo_ext), lo_mmd under it, lo_vreg along the south edge,
  lo_lf / lo_pfdcp south of bbfilter_i, lo_vtdet / obs / qdum beside qvco, isw_lod / isw_lo at their bond (E 2033).
- **PLL column, north-east** (x 2999-3480): pll_cdr, cdr, clk_obs, rx_aux_clk. pll_tx and rx_ref_in go in the pocket
  between pad_ref and pad_aux_clk.
- **South-west** (x 452-1050): char_rffet x3, isw_conv at its bond (W 978), bb_tap_i at pad_bb_i, decap.

Channels kept free of blocks and decap (die um):

| Channel | Rect | Carries |
|---|---|---|
| chan_macro_s | 1236-2952 x 3214-3304 | macro south edge escape (360 pins) |
| chan_macro_w | 1126-1236 x 3174-4670 | macro west pins to TX, DAC samples |
| chan_macro_e | 2952-2999 x 3591-4670 | macro east pins to the PLL column |
| trunk_a | 1131-1470 x 2330-3214 | macro to the RX cluster, D2H / SPI to the south ring |
| chan_rx_top | 1131-1645 x 2330-2880 | fan-out over the LNA cluster and mixers |
| chan_bbq_top | 1645-2296 x 2801-2890 | bbfilter_q / core_bias pins |
| chan_core_e | 2193-2296 x 2830-3214 | macro to adc_q, LO synthesiser, switches |
| chan_bbq_adcq | 2237-2296 x 2115-2850 | down to adc_q, lo_ext, qvco |
| spine | 1460-1554 x 1416-2180 | LNA-mixer gap: LNA pins, down to bbfilter_i / adc_i |
| spine_low | 1545-1640 x 452-1715 | bbfilter_i / adc_i, D2H to the south ring (with the XT-05 shield) |
| chan_mix_lo | 1855-1975 x 1691-2140 | LO pairs between the mixers and lo_ext |
| rf_tx_bar | 456-699 x 2935-3400 | RAIL_rf_tx bar (Metal5; no block under it) |

### 5.2 pt_wired

```
+--------------------------------------------------+
|                                                  |
|                                                  |
|                                                  |
|                                                  |
|          ::@@@@@@@@@@@@@@@@@@@@@::::             |
|       :::::@@@@@@@@@@@@@@@@@@@@@::::             |
|       :::  @@@@@@@@@@@@@@@@@@@@@:::::            |
|      :::   @@@@@@@@@@@@@@@@@@@@@:JJJ             |
|     ::::  f@@@@@@@@@@@@@@@@@@@@@:JJJXee          |
|######:::###@@@@@@@@@@@@@@@@@@@@@.JJJXee          |
|############@@@@@@@@@@@@@@@@@@@@@..               |
|############@@@@@@@@@@@@@@@@@@@@@.cc ############ |
|############@@@@@@@@@@@@@@@@@@@@@:cc ############ |
|############@@@@@@@@@@@@@@@@@@@@@::: ::           |
|     aaa    .....................::QQQQQ          |
|     bbbCCCCCCCCC::........    ::LLQQQQQ######### |
|     SSSCCCCCCCCC::....BBBWWWBBBBLLLLLLL######### |
|        :::::::::::....BBBBBBBBBB:::::            |
|          :::  ::::....BBBBBBBBBB:::NNNNOOO       |
|##       ::::TTT:::....BIIIIBVVBB:::NNNNOOO###### |
|###########ddFFFFFF.....IIII:VV################## |
|###########ddFFFFFF.....IIII VV################## |
|             FFFFFF.....::: ..:::::               |
|            YYY::::.....::: ..::::UUU             |
|            AAAAAAAAAAAAAAAA..::::   ############ |
|            AAAAAAAAAAAAAAAA..:::::::############ |
|            ..................:::::::############ |
|         KKKK             GGGGHHHHHHH############ |
|         KKKKDDDDDDDDDDRRRGGGGHHHHHHH  PPPP       |
|         KKKKDDDDDDDDDD    ZZ EEEEEEEEE MMM       |
|                           ZZ EEEEEEEEE MMM       |
|                                                  |
|                                                  |
+--------------------------------------------------+
```
1 char = 80 um wide x 160 um tall; @ digital macro, # pad keep-out, . reserved routing channel, : decap.

A=wrx_cap, B=wiredtx, C=core_bias, D=pll_cdr, E=detect, F=pll_vreg2, G=slicer, H=ctle, I=pll_tx, J=clk_obs, K=cdr, L=term_buffer, M=isw_wired_cap, N=isw_wired_tx_a, O=isw_wired_tx_b, P=termination, Q=attached_tx_interlock, R=ptrim, S=isw_debug, T=isw_pll, U=isw_wired_rx, V=usb_txdrv, W=char_atb, X=char_cmldiv, Y=wordclk_rx, Z=vthdac, a=rx_ref_in, b=rx_aux_clk, c=rx_wtx_ext, d=bb_tap_wmon, e=vco_replica, f=clockmux

Regions:
- **Macro** at x 971-2647, y 3077-4670 (DG9-11 outline, fixed between pad_ref / pad_aux_clk and pad_wtx_ext).
- **Wired TX, fixed:** wiredtx and isw_wired_tx_a/_b at their 4.1c positions, chan_wtxdata above wiredtx, the
  RAIL_wired_tx bar, term_buffer / tx_interlock / rx_wtx_ext / cascode_pump at pad_wire_tx and pad_wtx_ext, pll_tx
  under wiredtx (10 um), usb_txdrv at pad_usb.
- **HS RX row along the south edge:** termination and isw_wired_cap at the south-east corner; ctle (W) under the PAD-13
  decap slot, 45 um from pad_hs_rx; detect under ctle; slicer, ptrim (32-59 um pin channel), pll_cdr (E), cdr going
  west; vthdac under slicer. wrx_cap above the row with a 162 um channel between them, so slicer's 111 north pins and
  wrx_cap's 78 have room; wordclk_rx on wrx_cap.
- **West:** core_bias under the macro's west half (119 um), pll_vreg2 + isw_pll and bb_tap_wmon at pad_wmon,
  isw_debug at its bond (W 2666), rx_ref_in / rx_aux_clk below pad_aux_clk, decap tiles in the rest.
- **East of the macro:** a 120 um channel (`chan_macro_e`, decap allowed) for the macro supply joins, then clk_obs, rx_wtx_ext (W), small cells.

| Channel | Rect | Carries |
|---|---|---|
| chan_macro_s | 971-2647 x 2968-3077 | macro south edge escape (510 pins) |
| trunk_t | 1520-1912 x 1455-2968 | macro to the HS RX field (slicer, ptrim, wrx_cap, ctle, detect, cdr...) |
| chan_wtxdata | 1924-2134 x 2650-3017 | wire_tx data into wiredtx's top edge (ASM-11a) |
| chan_slicer_top | 1000-2453 x 1008-1170 | slicer / wrx_cap / ptrim fan-out |
| chan_wrx_e | 2250-2440 x 1008-1783 | east of wrx_cap: slicer, ctle, detect, termination |
| chan_ptrim_slicer | 2082-2131 x 640-1008 | ptrim east-edge pins (56) |
| (bar) | 2658-3320 x 2265-2640 | RAIL_wired_tx bar: reserved already by `common.ISLAND_BARS`, so not in `wired_place.json`; Metal2/3 routing under it is allowed |

## 6. Macro pin sides (re-hardening input)

`fp_plan/<chip>_macro_pin_order.cfg` lists each port by side, in order, with its planned offset from the macro's
lower-left corner. Each pin faces the centroid of its net's other ends. Pins are kept off the edge stretches that face a
pad keep-out (pt_rf east y 3290-3600; pt_wired west y 3000-3810, east y 3210-3625). Tie-off inputs are left unlisted
(any side). Minimum pitch 2.24 um.

**Host-link cluster: fixed.** `h2d_*`, `h2d_clk`, `d2h_*`, `d2h_clk_pin`, `d2h_oe` / `_sl` / `_pdrv`, `host_word_clk`
stay at their hardened positions relative to the macro (digital keeps them, matched skew). On pt_rf that is the north
edge, local x 75-198 (H2D), and the south edge, local x 454-538 (D2H and its controls). The model and the pin-order
file hold them there and place the other pins around them. Their bond nets run to the pads as one bundle:
- H2D goes straight up to the north ring.
- D2H leaves the south edge as a 22-net bundle through trunk A and spine_low to the south ring, with the XT-05 shield
  beside adc_i.

| | N | S | E | W |
|---|---|---|---|---|
| pt_rf, all macro nets (504) | 12 | 362 | 54 | 76 |
| pt_rf, `c_*` (279) | 0 | 217 | 41 | 21 |
| pt_wired, all (643) | 18 | 516 | 57 | 52 |
| pt_wired, `c_*` (409) | 0 | 343 | 25 | 41 |

Macro hardening must keep the order. It may compress pins toward each cluster, but it must not move a pin to another
side. Until the re-harden lands, the routed runs use the current macro pins (pt_rf `c_*`: N 112, W 137).

## 7. Routing demand against capacity

### 7.1 Method and the grid swap

The grid keeps its VDD / VSS strap pairs, 10.5 um wide at a 70 um pitch, its ring and its pad feeds. Only the layers
swap: vertical straps on Metal4, horizontal straps on Metal5 (`kl_place.py`, `GRID_SWAP=1`). The horizontal phase is
set so that the VDD rows lie exactly on the macro's Metal5 VDD pin rows (DG9-29/30: 5 um pins, 70 um per net, VSS
6.7 um above VDD). The VDD and VSS pairs (6.7 um apart in the macro, 35 um in the grid) cannot both line up, so I
checked the join as follows:
- There is no top-level grid over the macro.
- Each macro Metal5 pin strap is drawn at pin width out through the outline to the nearest vertical Metal4 straps of
  its net, within 100 um (reach 60-100 um), with a Via4 at each crossing.
- The horizontal rows give way only in that zone. Each VDD pin strap then continues straight into its full-width grid
  row; VSS stops 6 um short.

Results:
- **pt_rf:** 19 of 19 VDD and 19 of 19 VSS stripes joined at both ends; the old grid had VSS 0 at both ends and 19 at
  one end.
- **pt_wired:** VDD 22 + 1, VSS 7 + 15 (both ends + one end). The west ends face the 27 um gap to pad_ref /
  pad_aux_clk, so the east side is kept clear for the joins (`chan_macro_e`).

Grid metal on the same pt_rf floorplan, swapped against old: Metal4 VDD 1.256 / 1.298 mm2, VSS 1.207 / 1.214. Metal5
VDD 1.347 / 1.516, VSS 1.262 / 1.441. The whole Metal5 difference is over the macro, where the old flow drew a
duplicate of the macro's own pin straps. Outside the macro the two grids agree within ±0.01 mm2 per 0.33 mm2 tile.

Capacity model: per 20 um gcell, signal Metal2 (vertical) and Metal3 (horizontal) at 0.56 um pitch. With the swap
there is also Metal4 (vertical, 0.56) and Metal5 (horizontal, 0.9) at 70 % of their tracks in the channels: the
straps take 21 of every 70 um. Metal1 is added with `SIG_M1=1`. Over block outlines I count no capacity on any layer.
Decap blocks only Metal1-2. Demand: every non-hook net with its true pin positions, split into a Manhattan MST and
maze-routed with negotiated congestion (penalty above 55 %). Supply and LO nets count 3 tracks. Pin access, vias and
DRC spacing are not modelled. Calibration: the packer floorplan gives 459 / 311 over-full gcells, and there the real
router fails with 250-2400 DRT.

### 7.2 Cut lines and channels (swapped grid, SIG_M1=1, host-link fixed, decap placed)

| pt_rf cut line | Nets | Tracks | Util |
|---|---|---|---|
| S1 macro south escape, y 3210 | 340 | 4047 | 0.08 |
| S2 trunk A, y 2900, x 1131-1500 | 178 | 655 | 0.27 |
| S3 middle band, full core, y 2860 | 380 | 3266 | 0.12 |
| S4 RX / LO entry, y 2200 | 249 | 1801 | 0.14 |
| S5 LNA-mixer band, y 1850 | 204 | 847 | 0.24 |
| S6 south band, y 1000 | 57 | 2705 | 0.02 |
| V1-V4 (macro west / east edges, LNA cluster east, RX / LO) | 61-138 | 5050-7954 | 0.01-0.02 |

pt_rf channel peaks (V / H): chan_macro_s 0.54 / 0.55, chan_macro_w 0.15 / 0.36, chan_macro_e 0.35 / 0.23,
trunk_a 0.60 / 0.38, chan_rx_top 0.56 / 0.41, chan_bbq_top 0.49 / 0.09, chan_core_e 0.58 / 0.32,
chan_bbq_adcq 0.59 / 0.17, spine 0.53 / 0.21, spine_low 0.38 / 0.39, chan_mix_lo 0.54 / 0.15. Channel gcells over 70 %:
3 vertical, 15 horizontal (pin cells), of 8088.

| pt_wired cut line | Nets | Tracks | Util |
|---|---|---|---|
| S1 macro south escape, y 2990 | 518 | 5080 | 0.10 |
| S2 trunk T, y 2400 | 210 | 1154 | 0.18 |
| S3 middle band, y 2400 | 373 | 3900 | 0.10 |
| S4 above wrx_cap, y 1600 | 314 | 7072 | 0.04 |
| S5 HS RX row top, y 1050 | 292 | 6800 | 0.04 |
| V1-V4 | 38-190 | 3649-8785 | 0.01-0.05 |

pt_wired channel peaks: chan_macro_s 0.46 / 0.47, trunk_t 0.56 / 0.52, chan_wtxdata 0.28 / 0.55, chan_slicer_top
0.56 / 0.55, chan_wrx_e 0.58 / 0.47, chan_ptrim_slicer 0.56 / 0.05, chan_macro_e 0.44 / 0.16.

### 7.3 Remaining spots

- pt_wired: the 3 over-100 % gcells are in the 27 um gap between the macro's west edge and pad_ref / pad_aux_clk. The
  macro has no pins there; only the REF / AUX / ATB pad nets use it.
- The pin-cluster requests (adc_i/q, ptrim, LNA) are deferred until a route shows they matter (coordinator).

### 7.4 Decap

Decap tiles block Metal1-2 only, so Metal3, Metal4 and Metal5 pass over them. They go in trunk_a, chan_rx_top,
chan_macro_w and chan_bbq_top on pt_rf, and in chan_macro_e on pt_wired. They stay out of the macro escape rows and the
pin gaps. Their positions are in `<chip>_place.json` (`decap`): pt_rf 36 of 36 (PDS-10 shortfall closed in the plan),
pt_wired 69 of 69 plus the 14 PAD-13 tiles. The channel peaks above already include them.

### 7.5 Antenna diodes

Top-level antenna diodes (`common.ANT_DIODE`, `kl_place`) are a 6 x 6 um n+/p-substrate diode (`pt_antdiode`, 36 um2)
next to every block receiver of a net. Two rules add them:
- **Explicit list:** every net that has violated antenna in some run (coordinator list, patterns such as
  `ADCI_CODE[*]`, `atb0_sw[*]`, `island_en[*]`). It applies even to nets on the exclusion list below.
- **Length rule:** every non-supply net whose pin bounding box (half perimeter) is longer than `ANT_DIODE_LEN`
  (600 um).

The length rule never applies to analog-sensitive nets (`common.ANT_LEN_EXCLUDE`; coordinator 2026-11-27). A diode is
a few fF and leaks at hot corners, and that matters on these nets:
- **RF / LO / baseband signal pairs:** `RF_*`, `BB_[IQ]_*`, `LNA_*`, `LO_*`, `LOI_*`, `TXLO_*`, `TXI_* TXQ_* TXS_*`,
  `BBI_* BBQ_*`, `DACI_* DACQ_*`, `ADCI_[NP] ADCQ_[NP]`, `HSRX_*`, `WIRE_TX_*`, `WTX_EXT_*`, `REF_IN*`, `AUX_CLK_[NP]`,
  `WMON*`, `TX_CASCODE*`, `USB_*`, LO class nets.
- **Bias and references:** `BIAS_*`, `VCM*`, `VREF*`, `REF_VCM`, `*IBIAS*`.
- **ATB measurement:** `ATB*`, `ATBN_*`, `ATBP_*`, `atb*_local*`, `CHAR_*`.
- **VCO / loop filter:** `*VTUNE*`, `LO_CP`, `VREG_*`, `LO_VTDET`.
- **CDR phases and forwarded clocks:** `CDRPH[*]`, `CKP[*]`, `CKN[*]`, `TXPH[*]`, `PREF`, `WIRE_CK`, `WSMP_CK`,
  `*FWD*`, `fwd_*`, `rf_tx_clk_out`, `rf_rx_clk`.

**Nets that are allowed diodes although they look sensitive** (an honest record of the exclusion list):
- `CDR_VCTRL` (pt_wired, coordinator 2026-11-28): the length rule gives it two 36 um2 diodes (cdr.VCTRL, pll_cdr.ATB_VCTRL).
  The node is driven by pt_cdr's OTA (pfd_mode 0) or the ring's charge pump (pfd_mode 1); 36 um2 junctions leak at the pA
  level even hot, negligible against that drive, and removing them would cost antenna. Kept.

**Minimum-size diodes on three excluded nets** (`common.ANT_SMALL`, coordinator 2026-11-28). These nets get
`pt_antdiode_s`: 0.9 x 0.9 um n+ (0.81 um2), one contact, at every gate end (each receiver including the macro pin, never
the driver). The estimated added capacitance is about 1.2 fF per diode (n+/psub junction, roughly 1 fF/um2 area plus
0.1 fF/um sidewall). That is small compared with the routed wire, which is mm-long and hundreds of fF.

| Net | Driver (no diode) | Diodes at | Added cap |
|---|---|---|---|
| `LO_FB` | lo_mmd.FB | lo_pfdcp.FB, digital.fc_src[5] | ~2.4 fF |
| `WIRE_CK` | clockmux.WIRE | prescale.CK_IN, prescale_conv.CK_IN, obs_pre4_wire.CK | ~3.6 fF |
| `LO_VTDET` | lo_vtdet.DET | digital.s_lo_vtdet | ~1.2 fF |

`LO_VTDET` is driven, so a diode is allowed. In `pt_lo_vtdet` (scratch/lo-ap4/vtdet/lo_vtdet.spice), DET is the output
of the second `pt_t_inv1` after the 5T comparator: a CMOS logic output that is low impedance at both levels. With EN = 0
it is held at 0. The high-impedance, nA-biased detector nodes (VREF divider, NB bias, comparator D1/D2) are internal to
the block and never reach top-level routing. The detector's sensitive input is VTUNE (`LO_VTUNE`), which stays excluded.
All other exclusions stay as listed.

## 8. Deviations and open items (owners)

1. **LO branch to lo_txbuf** is 2.8 mm (FLOW_ADJ 1.2, LO-ASM-6 about 2.1). The RF_RX and RF_TX pads are 2.5 mm apart,
   lo_ext must stay within 120 um of the mixers, and lo_txbuf must abut txmix. Today's routed LO pairs are 3.5-4.0 mm
   (XT-01). Timing / LO owner: accept with a shielded bundle up trunk A, or rule.
2. **isw_pll** is 2.3 mm (pt_rf) / 4.1 mm (pt_wired) from its supply bond (E 4143), beside pll_vreg2 (power owner's
   ruling). pll_vreg2 does not fit in the pt_rf north-east column beside pll_cdr. Power owner: confirm the grid path
   from the bond to the switch.
3. **SUB-01**: adc_q is 709 um from the macro against the 782 um pessimistic figure (210 um nominal passes).
   Converters / substrate owner.
4. **Island trunks** are long where signal flow wins. pt_rf: RAIL_conv 3.6 mm, RAIL_debug 4.1 mm, RAIL_rf_rx 2.4 mm.
   pt_wired: RAIL_wired_rx 4.6 mm. This follows the coordinator ruling of 2026-11-24. Island-trunk agent.
5. **D2H bundle**: XT-05 shield beside adc_i (assembly).
6. **pt_wired detect** is 238 um from pad_hs_rx (150), and **wrx_cap** is 1.6 mm from the macro (300). Coordinator:
   accept.
7. **pll_tx** (the only `GRID_SNAP` block, built with Metal5 channels on the old vertical grid phase) is plan-placed
   rotated, with no snap. With the swap, the grid crossing it is vertical Metal4. The timing owner should confirm its
   ties.
8. **pt_wired TXPH** (pll_tx to wiredtx, 8 TX clock phases): routed path lengths on fpw-2 are PH0 1053, PH1 1313,
   PH2 1181, PH3 1224, PH4 1304, PH5 1184, PH6 1177, PH7 1195 um. The spread is 260 um (about 2 ps); about 210 um of
   it comes from the pin geometry (Manhattan 582-791 um). Coordinator, 2026-11-27: accepted without fixed matched
   wiring. Phase calibration and eye margin absorb the static skew, against a ring phase-error range of 100 ps
   (`scratch/wired_tx/s13/LIMITS.md`) and the block's own 15 ps systematic skew. Revisit only if the phase-error budget
   falls under 3 ps.
9. **pt_wired macro** is at x 1111, 140 um east of the old plan (fp-wired). The DG9-30 macro keeps its old pins
   (W 324 / E 209), so the plan model routes with `REAL_MPINS=1`. The side channels chan_macro_w (946-1111) and
   chan_macro_e (2787-2986) carry no decap. Host-link per-bit routed lengths before / after are within the coordinator's
   100 um limit.
10. **INT-04 F4, CDR_VCTRL on ATB1 code 41 (pt_wired, coordinator 2026-11-28):** pll_cdr.ATB_VCTRL is the loop node
    itself (shared with pt_cdr's OTA output), not a gated tap; the only gate is the leaf's own switch, the same as code 30
    on the TX ring. Off load from `atb_leaf_s` (extracted): 3.17 fF and 17 pA at 22-32 C (0.32 nA at 85 C), against an
    OTA- or pump-driven node: accepted. atb1_leaf41 sits beside cdr so the stub on CDR_VCTRL stays short (aim < 100 um,
    measured after placement); the long run is on the switched ATB1_LOCAL2 bus side.

## 9. Code (branch fp-plan-code)

1. **`floorplan.py`, `PLAN_FP=1` (off by default):**
   - Every `hand` and `auto` instance of `fp_plan/<chip>_place.json` is fixed at its lower-left with its DEF
     orientation and no packer margin.
   - Each `decap` tile goes to its planned spot.
   - The plan `channels` are packer reserves.
   - The macro x comes from the plan.
   - GROUP_BOOK and GRID_SNAP leave plan-fixed blocks alone.
   - The packer and pass 2 place only what the plan does not list.
2. **`kl_place.py`:**
   - Any DEF orientation for a real cell (`orient` in floorplan.json).
   - `GRID_SWAP=1` (default): the swapped grid and the macro-strap join of 7.1.
   - The VSS tab ties of staged blocks run on Metal5 up their channel to the nearest horizontal VSS row.
   - Drawn ties for provider tie pins deep inside a pad cell (`common.PAD_DIRECT_TIE`: the POR_BYPASS in_c cell's
     PU / PD), counted as wired by `check_conn.py`.
   - Antenna diodes per 7.5.
   - GRID_STITCH (packer floorplan only) follows the horizontal layer.
3. **Worktree runs:** `ASM_DATA=<main checkout>` makes the tool image mount that checkout as `/repo`, with this tree's
   `integration/` mounted over it (`tool.sh`, `signoff/kl.sh`, `signoff/env.sh`, `common.py`).
4. **Macro pin order:** the files of section 6, for the re-harden that is in progress.
5. **Pad map:** no change.
6. **Run:** `KH_CONN=1 PLAN_FP=1 SIG_M1=1 ASM_RUN=... ASM_DATA=... run.sh <chip>`, then `drc`, `lvs` (which includes
   the check stage).

## 10. Reproduce

```
export OMP_NUM_THREADS=1
KH_CONN=1 ASM_RUN=$PWD/scratch/integration/fpplan-rf ./run.sh rf abstract floorplan place          # same for wired
cd projects/programmable_transceiver_platform/integration/assembly/fp_plan
python3 extract.py <run> <run>/plan_extract.json                    # block rects, pins in die um, nets with classes
python3 matrix.py <run>/plan_extract.json                           # block list, pair matrix, macro pin sides
CHIP=rf python3 evalp.py cfg.py rf_place.json rf 20                 # checks, small cells, macro pins, global route (about 80 s)
python3 cuts.py use_rf.npy 20 rf_cuts.json eval_rf.json             # cut-line table, channel peaks
python3 draw.py eval_rf.json use_rf.npy pt_rf_plan.svg 20; python3 ascii.py eval_rf.json 80
python3 pinorder.py eval_rf.json <run>/plan_extract.json rf_macro_pin_order.cfg
python3 stats.py eval_rf.json <run>/plan_extract.json <run>         # rule distances, island trunks, key net lengths
```
The route model is stochastic only through ordering; repeated runs agree within about 0.05 on the channel peaks.
