# Floorplan plan: pt_rf and pt_wired (connectivity-driven)

Current state, 2026-11-26. This is a paper plan: no route was run. The plan sets the positions of the major blocks,
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
- **Model result (section 7).** I ran a gcell global route at 20 um on Metal2 (V) and Metal3 (H) with 0.56 um pitch,
  negotiated congestion, all 1059 / 1200 nets (KH_CONN=1). Compared with the current floorplan, on the same model:

| | pt_rf current | pt_rf plan | pt_wired current | pt_wired plan |
|---|---|---|---|---|
| Channel gcells over 70 % vertical (of about 5.5k / 11k) | 1093 | 74 | 536 | 104 |
| Channel gcells over 100 % vertical | 459 | 0 | 311 | 30 (one sliver, section 7.3) |
| Channel gcells over 70 % horizontal | 1019 | 28 | 501 | 13 |
| Wire length (mm) | 2878 | 1239 | 3434 | 1767 |
| Wire forced over block outlines (mm) | 199 | 53 | 407 | 55 |
| Worst key cut line | 0.84 (trunk west of core_bias) | 0.36 | 1.37 (trunk to the HS RX field) | 0.44 |

  Every key cut line is at or below 0.44. Every named channel is at or below 0.70 except three pin-cluster spots
  (0.76-0.84, section 7.2). No isolation rule fails.
- **Open (section 8).** Some items need an owner decision: the LO branch to lo_txbuf (2.8 mm, LO-ASM-6 asks for
  2.1 mm), isw_pll away from its supply bond on both chips, adc_q 709 um from the macro (SUB-01 pessimistic case
  asks for 782 um), and pt_rf decap (21 of 36 tiles placed outside the channels).

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
| No block in the macro routing channel; decap at the macro | ASM-11 (channels), power delivery 5 (bank) | channels free; 21 of 36 decap tiles placed outside channels | **decap open** (PDS-10) |
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
|     ...OOONNN....HHHHHHHHH.zzzKKKKKKRRRRRq       |
|     ....QQQQQ....HHHHHHHHH..  KKKKKKRRRRRq       |
|     ccccQQQQQ......FFFFFFFFiiiKKKKKK############ |
|     cccgggvv ......FFFFFFFFiii:::::############# |
|############  ......FFFFFFFFBBBBBBBBBBBB::        |
|############  ....::FFFFFFFFBBBBBBBBBBBB mm       |
|############VVVVoo::FFFFFFFFBBBBBBBBBBBBdmm       |
|############VVVVoo.ffff.LLLLLL::: xxxkk ddd       |
|############MMMMMM.eeee.LLLLLL::AAAAAAAAAAA       |
|############UUUUnn.eeeeELLLLXX::AAAAAAAAAAA       |
|############UUUUnn..EEEEEEEEXX::AAAAAAAAAAA       |
|############UUUUCCC.EEEEEEEEXX yAAAAAAAAAAA       |
|     uu aaa::CCCCCC.EEEEEEEEXXGyGGGGGGGGGAA       |
|     uulaaa::CCCCCC.EEEEEEEE GGGGGGGGGGGGjj       |
|     lllZZZ::CCCCCC.IIIIIPPPPGGGGGGGGGGGGjj       |
|      ::ZZZ::CCCCCC.IIIIIPPPPDDDDDDDDDDDDDD       |
|      ::YYY::CCCCCC.IIIIIPPPPDDDDDDDDDDDDDD       |
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
|        ::  @@@@@@@@@@@@@@@@@@@@@::::             |
|        ::::@@@@@@@@@@@@@@@@@@@@@::::             |
|       :::: @@@@@@@@@@@@@@@@@@@@@ :::::           |
|      :::   @@@@@@@@@@@@@@@@@@@@@JJJ              |
|      ::   f@@@@@@@@@@@@@@@@@@@@@JJJXee           |
|######:::###@@@@@@@@@@@@@@@@@@@@@JJJXee           |
|############@@@@@@@@@@@@@@@@@@@@@                 |
|############@@@@@@@@@@@@@@@@@@@@@    ############ |
|############@@@@@@@@@@@@@@@@@@@@@ccc ############ |
|############@@@@@@@@@@@@@@@@@@@@@:::              |
|     aaa    ..................::.::QQQQQ:         |
|     bbbCCCCCCCCC::........   :::LLQQQQQ######### |
|     SSSCCCCCCCCC::....BBBWWWBBBBLLLLLLL..####### |
|      :::::::::::::....BBBBBBBBBB.........        |
|      :::::::  ::::....BBBBBBBBBB...NNNNOOO       |
|##      :::::TTT:::....BIIIIBVVBB###NNNNOOO###### |
|###########ddFFFFFF.....IIII:VV################## |
|###########ddFFFFFF.....IIII VV################## |
|         ::::FFFFFF.....::: ..:::::::::           |
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
- **East of the macro:** clk_obs, char_cmldiv, vco_replica, rx_wtx_ext, decap.

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

`fp_plan/rf_macro_pin_order.cfg` and `fp_plan/wired_macro_pin_order.cfg` list each port by side, in order, with its
planned offset. Each pin faces the centroid of its net's other ends. Pins are kept off the edge stretches that face a
pad keep-out (pt_rf east y 3290-3600; pt_wired west y 3000-3810, east y 3210-3625). Tie-off inputs are left unlisted
(any side). Minimum pitch 2.24 um.

| | N | S | E | W |
|---|---|---|---|---|
| pt_rf, all macro nets (504) | 8 (H2D 11 share the N ring; obs) | 360 | 59 | 77 |
| pt_rf, `c_*` (279) | 0 | 216 | 42 | 21 |
| pt_wired, all (643) | 14 | 510 | 72 | 47 |
| pt_wired, `c_*` (409) | 0 | 335 | 41 | 33 |

On pt_rf the south edge, 1716 um long, holds 360 pins at an average pitch of 4.8 um. Clusters (x of the 10th-90th percentile pin):
core_bias 1670-2120, RX chain 1460-2200, adc_q and LO synthesiser 2130-2590, host link and debug 1330-2950. On pt_wired the south edge holds 510 pins at an average pitch of 3.3 um. Macro hardening must keep the
order. It may compress pins toward each cluster, but it must not move a pin to another side.

## 7. Routing demand against capacity

### 7.1 Method

Capacity per 20 um gcell: Metal2 tracks (vertical) and Metal3 tracks (horizontal) at 0.56 um pitch (tech LEF), times
the cell's fraction free of block outlines, pad footprints and the core-ring band. Over blocks the capacity is zero,
and so is Metal4/5 everywhere: the G1 straps cross their preferred direction every 70 um. Decap blocks only Metal2.
`SIG_M1=1` adds Metal1 to the horizontal capacity. Demand: every non-hook net (KH_CONN=1, with its true pin positions
after orientation; macro pins as planned), split into a Manhattan MST, maze-routed with negotiated congestion (penalty
above 55 % utilisation, 5 passes). Supply and LO nets count 3 tracks (WIDE / LOSH rules). The 384 / 367 hook nets
are left out: they are short, from a block's supply pin to the nearest strap. This is a capacity estimate, not a
detailed route: pin access inside 15 um pin clusters, vias and DRC spacing are not modelled. For calibration, the
same model applied to the current packer floorplan gives 459 / 311 over-full channel gcells, and the real router
fails there with 250-2400 DRT.

### 7.2 Cut lines and channels

Utilisation = demand / capacity across the whole cut (the router may use any free gcell on the line).

| pt_rf cut line | Nets crossing | Tracks | Plan | Current floorplan |
|---|---|---|---|---|
| S1 macro south escape, y 3210, x 1236-2952 | 352 | 2554 | 0.14 | 0.31 |
| S2 trunk A, y 2900, x 1131-1500 | 200 | 643 | 0.31 | 0.84 |
| S3 middle band, full core, y 2860 | 410 | 2310 | 0.18 | 0.51 |
| S4 RX / LO entry, full core, y 2200 | 249 | 900 | 0.28 | 0.77 |
| S5 LNA-mixer band, full core, y 1850 | 202 | 565 | 0.36 | 0.41 |
| S6 south band, full core, y 1000 | 72 | 1508 | 0.05 | 0.47 |
| V1 macro west edge, x 1230, y 2560-4670 | 131 | 3266 | 0.04 | 0.72 |
| V2 macro east edge, x 2970, y 2560-4670 | 93 | 2189 | 0.04 | 0.10 |
| V3 LNA cluster east, x 1500, y 452-2560 | 130 | 2092 | 0.06 | 0.26 |
| V4 RX / LO, x 2260, y 452-2900 | 133 | 2073 | 0.06 | 0.06 |

| pt_wired cut line | Nets crossing | Tracks | Plan | Current floorplan |
|---|---|---|---|---|
| S1 macro south escape, y 2990, x 971-2647 | 545 | 2988 | 0.18 | 0.61 |
| S2 trunk T, y 2400, x 1520-1912 | 298 | 679 | 0.44 | 1.37 |
| S3 middle band, full core, y 2400 | 375 | 1686 | 0.22 | 0.30 |
| S4 above wrx_cap, full core, y 1600 | 316 | 3517 | 0.09 | 0.24 |
| S5 HS RX row top, full core, y 1050 | 295 | 3632 | 0.08 | 0.21 |
| V1 macro west edge, x 960, y 2000-4670 | 144 | 2470 | 0.06 | 0.38 |
| V2 macro east edge, x 2660, y 2650-4670 | 199 | 2145 | 0.09 | 0.13 |
| V3 trunk T east edge, x 1915, y 1110-2209 | 255 | 1498 | 0.17 | 0.15 |
| V4 slicer / ctle, x 2435, y 452-1783 | 63 | 2050 | 0.03 | 0.09 |

Peak gcell utilisation inside each channel (vertical / horizontal):

- **pt_rf:**
  - At or below 0.70: chan_macro_s 0.56 / 0.59, chan_macro_w 0.48 / 0.56, chan_macro_e 0.56 / 0.31,
    trunk_a 0.56 / 0.53, chan_rx_top 0.53 / 0.53, chan_bbq_top 0.53 / 0.53, chan_core_e 0.67 / 0.48,
    spine_low 0.53 / 0.53, chan_mix_lo 0.53 / 0.28.
  - Over 0.70: **spine 0.78** (the LNA's 32 pins and rxmix pins sit on the 100 um LNA-mixer gap, which FLOW_ADJ
    caps at 100 um) and **chan_bbq_adcq 0.84** (adc_q's 31 pins sit in one 15 um corner; with the macro pins facing
    them this is a pin-access hotspot, not a channel shortage).
- **pt_wired:**
  - At or below 0.70: chan_macro_s 0.53 / 0.70, trunk_t 0.59 / 0.53, chan_wtxdata 0.53 / 0.59,
    chan_slicer_top 0.56 / 0.56, chan_wrx_e 0.59 / 0.53, bar_wired_tx 0.56 / 0.31.
  - Over 0.70: **chan_ptrim_slicer 0.78** (ptrim's 56 east-edge pins; FLOW_ADJ caps the gap at 60 um).

### 7.3 What is left and how to close it

- The three pin-cluster spots above go below 0.70 without floorplan changes if the owner spreads the pins along the
  edge (MANDATE 4a: block pins on the cell edge). Requests: adc_i/q (39 pins within 15 um at one corner), ptrim (56
  pins on one 236 um edge), LNA (32 pins on one edge with RF in and out). The other way is `SIG_M1=1`: at the 0.70
  penalty knee it cut the pt_rf over-70 % channel gcells from 334 to 289.
- **Grid direction (largest lever).** If Metal4 could carry vertical signal and Metal5 horizontal signal between the
  straps, vertical capacity in the channels would rise about 1.7x. That needs either G1's strap layers swapped
  (Metal4 vertical, Metal5 horizontal) or the top-level tech-LEF preferred directions swapped. Modelled: pt_rf
  over-70 % vertical gcells drop from 289 to 79, and every cut line halves. This is a power-delivery G1 decision
  (power owner), not part of this plan.
- pt_wired's 30 over-100 % gcells all sit in the 27 um sliver between the macro's west edge and pad_ref / pad_aux_clk
  (x 944-971). The router should treat it as blocked: the macro has no pins there (pin-order file), and only the REF /
  AUX / ATB pad nets need it.

## 8. Deviations and open items (owners)

1. **LO branch to lo_txbuf** is 2.8 mm (FLOW_ADJ 1.2, LO-ASM-6 about 2.1). The RF_RX and RF_TX pads are 2.5 mm apart,
   lo_ext must stay within 120 um of the mixers, and lo_txbuf must abut txmix. Today's routed LO pairs are 3.5-4.0 mm
   (XT-01). Timing / LO owner: accept with a shielded bundle up trunk A, or rule.
2. **isw_pll** is 2.3 mm (pt_rf) / 4.1 mm (pt_wired) from its supply bond (E 4143). The power owner's ruling puts it
   beside pll_vreg2, and pll_vreg2 does not fit in the north-east column beside pll_cdr (needs 666 um, the column has
   481). Power owner: confirm the grid path from the bond to the switch, or give pll_vreg2 / isw_pll the area east of
   the macro (pt_wired has room there; pt_rf needs the macro moved 136 um west, which puts dac_i inside the macro
   outline, so no).
3. **SUB-01**: adc_q is 709 um from the macro against the 782 um pessimistic figure (210 um nominal passes). Moving it
   further needs adc_q under the LO synthesiser. Converters / substrate owner.
4. **Decap, pt_rf**: 21 of 36 tiles fit outside the channels (pt_wired: 69 of 69). Tiles block only Metal2, so they may
   sit in the horizontal channels (chan_bbq_top, chan_rx_top) at the cost of vertical tracks, or go to the grid MIM
   plates of power-delivery 5.1b. PDS-10 owner.
5. **Island trunks** become long where signal flow wins. pt_rf: RAIL_conv from isw_conv (W 978) to adc_q 3.6 mm,
   RAIL_debug 4.1 mm, RAIL_rf_rx 2.4 mm. pt_wired: RAIL_wired_rx 4.6 mm. This follows the coordinator ruling of
   2026-11-24 (signal flow first, drawn trunks carry the loads). Island-trunk agent: size per README.
6. **D2H / SPI** (21 nets) leave the macro's south edge and reach the south ring through trunk A and spine_low, next
   to adc_i. XT-05 asks for a shield under the lanes. Assembly: draw it.
7. **pt_wired detect** is 238 um from pad_hs_rx (150), because the PAD-13 decap slot holds the pad's inner side.
   **wrx_cap** is 1.6 mm from the macro (300), because it stays with the slicer. Coordinator: accept or swap with the
   decap slot.
8. **Pin clusters**: owner requests in 7.3.

## 9. Translating the plan into code

1. **floorplan.py, behind `PLAN_FP=1` (off by default):** read `fp_plan/<chip>_place.json`. Every `hand` instance goes
   into `FIXED` (same mechanism as `common.FIXED_PLACE`: the packer books its slot and drops it from the ledger
   placement), with its orientation. Every `channels` rect goes into the packer reserves (as `common.ROUTE_CHANNELS`
   does), so no block or decap tile lands in them. Then pass 2 places the small cells and the decap next to their
   partners, outside the channels. The `auto` positions are a guide only. FLOW_ADJ / keep-away checks stay as they
   are; `relaxed` should list only section 8 items. `kl_place.py` needs the orientation passed through for fixed
   blocks (today FIXED_PLACE is R0 only). Nothing else in the flow changes.
2. **Macro pin order (digital re-hardening, DG owner):** `fp_plan/<chip>_macro_pin_order.cfg` (OpenLane
   pin_order.cfg form; side headers `#N #S #E #W`, order left to right / bottom to top, planned offsets). The pin
   order is tied to the macro position in the plan (pt_rf x0 1236, y0 3304.4; pt_wired x0 971, y0 3077). If either
   moves by more than about 50 um, regenerate the file (`pinorder.py`). Until the macro is re-hardened, KH_CONN routing
   still sees the old sides (pt_rf `c_*`: N 112, W 137).
3. **Pad map:** no change (section 4).
4. **Route flow (not floorplan):** `SIG_M1=1`. Pass the G1 grid-direction question (7.3) to the power owner. Treat the
   pt_wired west sliver as a routing blockage.
5. **Verification after coding:** run `KH_CONN=1 PLAN_FP=1 run.sh <chip> abstract floorplan place`, then
   `fp_plan/extract.py` and `evalp.py` on the new run: the cut lines and channel peaks above should come back within
   about 0.05. Then route.

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
