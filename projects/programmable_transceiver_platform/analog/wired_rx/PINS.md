# Wired RX: pin list and connection at chip top

Pins of the published wired RX cells and the nets they are bound to. The binding itself lives in
`integration/top/pt_chip.conn` (the one connectivity source; `integration/top/check_top.py` reads each
cell's pin list from its published `generated/<block>.ext.spice`). This file restates it per cell; where the
two differ, the conn file is right. Control-port widths, resets, encodings and register fields are in
`integration/top/ctl_ports.txt`; open disagreements between owners are the `D-` rows of
`integration/top/decisions.md`.

Net prefixes: `c_*` control from `pt_digital_macro`, `s_*` status into it, `RAIL_<island>` switched supply of
an island, `BIAS_*` a 10 µA output of the bias bank, `ATBN_*` an analog test-bus node.

## 1. Signal flow

```
WIRE_RX_P/N -> pad_hs_rx -> HSRX_P/N -> ctle -> CTLE_P/N -+-> rxselect -> SL_P/N -> slicer -> SLS[0..7] -> wrx_cap -> macro
USB_DP/DN   -> pad_usb   -> URX_P/N ----------------------+      |                    ^                     |
                                 +-> detect, wmon_sel            vthdac ->------------+                     |
pll_cdr PH0..7 -> CDRPH[0..7] -> ptrim -> CKP[0..7] -> slicer, wrx_cap; CKP[0] -> wordclk_rx -> WRX_LDE     |
wrx_cap UP/DN -> WRX_UP/DN -> iso clamps -> CDR_UP/DN -> pll_cdr FU/FD and cdr UP/DN; cdr VCTRL -> pll_cdr <-+
```

| Instance | Cell | Island | Supply net |
|---|---|---|---|
| `pad_hs_rx` | `pad_hspad` | wired_rx | `RAIL_wired_rx` |
| `pad_usb` | `pad_wirepad` | wired_tx | `RAIL_wired_tx` |
| `termination`, `rxlevel`, `ctle`, `rxselect`, `wmon_sel`, `detect`, `vthdac`, `slicer` | `pt_<name>` | wired_rx | `RAIL_wired_rx` |
| `ptrim`, `wrx_cap` | `pt_ptrim`, `pt_wrx_cap` | wired_cap | `RAIL_wired_cap` |
| `wordclk_rx` | `pt_wordclk` (timing) | wired_cap | `RAIL_wired_cap` |
| `cdr` | `pt_cdr` | pll | `RAIL_pll` |
| `pll_cdr` | `pt_pll_ring` (timing) | pll | `VREG_CDR` from `pll_vreg2.VOUT_CDR` |

## 2. Cell pin tables

Direction: in = load, out = the one driver, an = analog, supply or passive. Every cell also has its supply
pin (table above) and `VSS`.

### `termination` (`pt_termination`)

| Pin | Dir | Net |
|---|---|---|
| `term_en`, `term_mode0..1` | in | `c_term_en`, `c_term_mode[0..1]` |
| `hs_en`, `hs_term_en`, `hs_trim0..3` | in | `c_term_hs_en`, `c_term_hs_term_en`, `c_term_hs_trim[0..3]` |
| `TERM_ENABLE`, `DIFF_ENABLE` | out | `TERM_ENABLE`, `DIFF_ENABLE` → `pad_usb` |
| `TERM_VCM` | an | `TERM_VCM` → `pad_usb.TERM_VCM`, ATB |
| `HS_TERM_ENABLE`, `HS_TERM_TRIM0..3` | out | `HS_TERM_ENABLE`, `HS_TERM_TRIM[0..3]` → `pad_hs_rx.TERM_ENABLE`, `TERM_TRIM0..3` |
| `HS_TERM_VCM`, `HS_VBIAS` | an | `HS_TERM_VCM` → `pad_hs_rx.TERM_VCM`; `HS_VBIAS` → `pad_hs_rx.VBIAS`, ATB |

### `rxlevel` (`pt_rxlevel`)

| Pin | Dir | Net |
|---|---|---|
| `rxlevel_en`, `rxlevel_half` | in | `c_rxlevel_en`, `c_rxlevel_half` |
| `DIV_ENABLE`, `BYPASS_ENABLE` | out | `DIV_ENABLE`, `BYPASS_ENABLE` → `pad_usb` |

### `ctle` (`pt_ctle`)

| Pin | Dir | Net |
|---|---|---|
| `IBIAS` | an | `BIAS_ctle` |
| `ctle_en`, `wire_ctle_bypass` | in | `c_ctle_en`, `c_ctle_bypass` |
| `ctle_peak0..2`, `lf_zero0..2` | in | `c_ctle_peak[0..2]`, `c_ctle_lf_zero[0..2]` |
| `RX_P`, `RX_N` | an | `HSRX_P`, `HSRX_N` from `pad_hs_rx.RX_P/N` (no other load) |
| `CTLE_P`, `CTLE_N` | an | `CTLE_P`, `CTLE_N` → `rxselect`, `wmon_sel` |
| `atb_ctle_pbias` | an | `ATBN_ctle_bias` |
| `atb_ctle_src` | an | not connected |

### `rxselect` (`pt_rxselect`)

| Pin | Dir | Net |
|---|---|---|
| `rxselect_en`, `rxselect_direct` | in | `c_rxselect_en`, `c_rxselect_direct` |
| `CTLE_P`, `CTLE_N` | an | `CTLE_P`, `CTLE_N` |
| `RX_P`, `RX_N` | an | `URX_P`, `URX_N` from `pad_usb.RX_P/N` |
| `SL_P`, `SL_N` | an | `SL_P`, `SL_N` → `slicer` |

### `wmon_sel` (`pt_wmon_sel`)

| Pin | Dir | Net |
|---|---|---|
| `wmon_en`, `wmon_sel0..1` | in | `c_wmon_en`, `c_wmon_sel[0..1]` |
| `RX_P`, `RX_N`, `CTLE_P`, `CTLE_N` | an | `URX_P`, `URX_N`, `CTLE_P`, `CTLE_N` |
| `WMON_IN` | an | `WMON_IN` → `bb_tap_wmon.in_p`; pulled down by `iso_wmon` when the wired_rx island is off |

### `detect` (`pt_detect`)

| Pin | Dir | Net |
|---|---|---|
| `IBIAS` | an | `BIAS_detect` |
| `det_en`, `det_clk` | in | `c_detect_en`, `ct_det_clk` (macro output) |
| `RX_P`, `RX_N` | an | `URX_P`, `URX_N` |
| `TX_P`, `TX_N` | an | `WIRE_TX_P`, `WIRE_TX_N` (bond pads) |
| `det_thr0..1`, `det_se0..1` | in | `c_detect_thr[0..1]`, `c_detect_se[0..1]` |
| `det_src_tx`, `det_inject` | in | `c_detect_src_tx`, `c_detect_inject` |
| `DIFF_POS`, `DIFF_NEG`, `SE_P`, `SE_N` | out | `DET_DIFF_POS`, `DET_DIFF_NEG`, `DET_SE_P`, `DET_SE_N` → macro `s_detect_*` |
| `atb_det_vref` | an | `ATBN_detect_vref` |

### `vthdac` (`pt_vthdac`)

| Pin | Dir | Net |
|---|---|---|
| `vth_en`, `A0..7`, `B0..7` | in | `c_vthdac_en`, `c_vthdac_a[0..7]`, `c_vthdac_b[0..7]` |
| `VTAP`, `VTAN`, `VTBP`, `VTBN` | an | same names → `slicer` |

### `slicer` (`pt_slicer`)

| Pin | Dir | Net |
|---|---|---|
| `slicer_en` | in | `c_slicer_en` |
| `SL_P`, `SL_N` | an | `SL_P`, `SL_N` |
| `CKP0..7` | in | `CKP[0..7]` |
| `QCK` | out | not connected |
| `D0`, `E0`, `D1`, `E1`, `D2`, `E2`, `D3`, `E3` | out | `SLS[0]` … `SLS[7]` in that order (`D_i` → `SLS[2i]`, `E_i` → `SLS[2i+1]`) |
| `trim_<s>_{p0,p1,p2,n0,n1,n2,f0,f1,f2,f3}`, s = d0..d3, e0..e3 | in | `c_slicer_trim_<s>[0..9]` in that order |
| `vsel_e<k>_0..1`, k = 0..3 | in | `c_slicer_vsel_e<k>[0..1]` |
| `VTAP`, `VTAN`, `VTBP`, `VTBN` | an | from `vthdac` |

### `ptrim` (`pt_ptrim`)

| Pin | Dir | Net |
|---|---|---|
| `ptrim_en` | in | `wire_rx_ptrim_en` (macro output) |
| `PH0..7` | in | `CDRPH[0..7]` from `pll_cdr.PH0..7` (crosses pll → wired_cap without a clamp; waived: the input is a NAND with `ptrim_en`) |
| `CKP0..7` | out | `CKP[0..7]` → `slicer`, `wrx_cap`; `CKP[0]` also → `wordclk_rx.CK` |
| `T<k>_0..4`, k = 0..7 | in | `c_ptrim_t<k>[0..4]` |

### `wrx_cap` (`pt_wrx_cap` r6)

| Pin | Dir | Net |
|---|---|---|
| `S0..7` | in | `SLS[0..7]` |
| `CKP0..7` | in | `CKP[0..7]` |
| `EN`, `RCS`, `B2`, `B1` | in | `c_wrx_cap_en`, `c_wrx_cap_rcs`, `c_wrx_cap_b2`, `c_wrx_cap_b1` |
| `LDE` | in | `WRX_LDE` from `wordclk_rx.LDE` |
| `PSEL0..2`, `SLIPP`, `SLIPM` | in | `c_wrx_cap_psel[0..2]`, `c_wrx_cap_slipp`, `c_wrx_cap_slipm` (dynamic, from `pt_wrx_ctl`) |
| `DW0..19` | out | not connected |
| `EW0..19` | out | `WRX_EW[0..19]` → macro `wire_rx_edge` |
| `SLP`, `SLM` | out | `WRX_SLP`, `WRX_SLM` → macro `s_wrx_slp`, `s_wrx_slm` |
| `UP0..3`, `DN0..3` | out | `WRX_UP[0..3]`, `WRX_DN[0..3]` → `iso_cdr_up_*`, `iso_cdr_dn_*` |
| `DX0..39` | out | `WRX_DX[0..39]` → macro `wire_rx_data` |
| `WCLK40` | out | `WRX_WCLK40` → macro `wire_rx_clk` |

### `wordclk_rx` (`pt_wordclk`, owned by timing)

| Pin | Dir | Net |
|---|---|---|
| `CK` | in | `CKP[0]` |
| `EN`, `D10`, `D20` | in | `c_wordclk_en`, `c_wordclk_d10`, `c_wordclk_d20` |
| `LDE` | out | `WRX_LDE` |
| `WORD_CLK`, `LD`, `LDB` | out | not connected |

### `cdr` (`pt_cdr` r13)

| Pin | Dir | Net |
|---|---|---|
| `IBIAS` | an | `BIAS_cdr` (bank output `BIAS_pll_ring_host`, enabled by `c_cdr_en`) |
| `cdr_en`, `pfd_mode`, `ref_sel` | in | `c_cdr_en`, `c_cdr_pfd_mode`, `c_cdr_ref_sel` |
| `g0..2` | in | `c_cdr_g[0..2]` |
| `UP0..3`, `DN0..3` | in | `CDR_UP[0..3]`, `CDR_DN[0..3]` (clamped copies of `WRX_UP/DN`) |
| `FUP`, `FDN` | in | `c_cdr_fup`, `c_cdr_fdn` (dynamic, from `pt_wrx_ctl`) |
| `IB_PLL` | an | not connected |
| `HOLD_PLL` | out | `CDR_HOLD` → `pll_cdr.HOLD` |
| `VCTRL` | an | `CDR_VCTRL` ↔ `pll_cdr.ATB_VCTRL` |
| `REF_IN` | in | `PREF` from `clockmux.PREF` |
| `WCK_IN` | in | `AUX_CK_P` (forwarded clock from the AUX_CLK pair through `rx_aux_clk` and `iso_aux_ck`) |
| `REF_PLL` | out | `CDR_REF` → `pll_cdr.REF` |
| `atb_cdr_pbias` | an | `ATBN_cdr_bias` |
| `otr0..4`, `otrs` | in | `c_cdr_otr[0..4]`, `c_cdr_otr[5]` |

### `pll_cdr` (`pt_pll_ring`, owned by timing)

| Pin | Dir | Net |
|---|---|---|
| `REF`, `HOLD` | in | `CDR_REF`, `CDR_HOLD` |
| `EN`, `N4`, `N8`, `N5`, `N10`, `BAND` | in | `c_pll_cdr_en`, `c_pll_cdr_n4`, `_n8`, `_n5`, `_n10`, `c_pll_cdr_band` |
| `KP0..2` | in | `c_pll_cdr_kp[0..2]` |
| `FU0..3`, `FD0..3` | in | `CDR_UP[0..3]`, `CDR_DN[0..3]` |
| `IBIAS` | an | `BIAS_pll_ring_rx` |
| `PH0..7` | out | `CDRPH[0..7]` → `ptrim`; `CDRPH[0]` also → `clockmux.WSI`, `prescale_hf.CK_IN`; `CDRPH[1]` → `obs_pre4_cdr.CK` |
| `LOCK`, `FBCK` | out | `PLL_CDR_LOCK` → macro `s_pll_cdr_lock`; `PLL_CDR_FBCK` → macro `fc_src[1]` |
| `REFO` | out | not connected |
| `ATB_VCTRL` | an | `CDR_VCTRL` |
| `VDD` | an | `VREG_CDR` (`pll_vreg2.VOUT_CDR`, bypass `c_pllvreg_byp_cdr`) |

## 3. Net list view

| Net | Driver | Loads |
|---|---|---|
| `HSRX_P/N` | `pad_hs_rx.RX_P/N` | `ctle.RX_P/N` only |
| `URX_P/N` | `pad_usb.RX_P/N` | `rxselect.RX_P/N`, `detect.RX_P/N`, `wmon_sel.RX_P/N` |
| `CTLE_P/N` | `ctle` | `rxselect`, `wmon_sel` |
| `SL_P/N` | `rxselect` | `slicer` |
| `VTAP/VTAN/VTBP/VTBN` | `vthdac` | `slicer` |
| `WMON_IN` | `wmon_sel` | `bb_tap_wmon.in_p` |
| `CDRPH[0..7]` | `pll_cdr.PH0..7` | `ptrim.PH0..7` (+ clock mux, prescaler, observation taps above) |
| `CKP[0..7]` | `ptrim` | `slicer`, `wrx_cap`, `wordclk_rx` (`CKP[0]`) |
| `SLS[0..7]` | `slicer` D0, E0, D1, E1, D2, E2, D3, E3 | `wrx_cap.S0..7` |
| `WRX_LDE` | `wordclk_rx.LDE` | `wrx_cap.LDE` |
| `WRX_UP/DN[0..3]` | `wrx_cap` | `iso_cdr_up_*`, `iso_cdr_dn_*` (`iso_clamp` on `RAIL_pll`, `ISO = island_off[0]`) |
| `CDR_UP/DN[0..3]` | the clamps | `cdr.UP/DN`, `pll_cdr.FU/FD` |
| `CDR_VCTRL` | `cdr.VCTRL` | `pll_cdr.ATB_VCTRL` |
| `CDR_REF`, `CDR_HOLD` | `cdr` | `pll_cdr.REF`, `HOLD` |
| `WRX_DX[0..39]`, `WRX_WCLK40`, `WRX_EW[0..19]`, `WRX_SLP/SLM` | `wrx_cap` | macro (clamped inside the macro) |
| `DET_DIFF_POS/NEG`, `DET_SE_P/N` | `detect` | macro (clamped inside the macro) |
| `AUX_CK_P` | `iso_aux_ck` (from `rx_aux_clk.OUTP`) | `cdr.WCK_IN`, `clockmux.AUX`, `clockmux.WCK` |

Bias: `BIAS_ctle`, `BIAS_detect`, `BIAS_cdr`, `BIAS_pll_ring_rx`. No other wired RX cell has a bias pin.
ATB: `HS_VBIAS`, `ATBN_ctle_bias`, `TERM_VCM`, `ATBN_detect_vref`, `ATBN_cdr_bias`.

## 4. Controls from the digital macro

All are static (change only while the consumer is stopped) except the ones marked dynamic. Reset value is the
cell's safe state. A port of a switched island reads 0 while that island is off.

| Port | Width | Reset | Source |
|---|---|---|---|
| `c_term_en`, `c_term_mode` | 1, 2 | 0 | decoded from `termination.config.p_load` and `differential_100_enable` |
| `c_term_hs_en`, `c_term_hs_term_en`, `c_term_hs_trim` | 1, 1, 4 | 0, 0, 5 | `termination.config.hs_enable`, `hs_term_enable`, `hs_trim` |
| `c_rxlevel_en`, `c_rxlevel_half` | 1, 1 | 0 | decoded from `rxlevel.config.path` |
| `c_ctle_en` | 1 | 0 | `ctle.state.state` |
| `c_ctle_bypass`, `c_ctle_peak`, `c_ctle_lf_zero` | 1, 3, 3 | 0 | `debug.wire_bypass.ctle`, `ctle.config.peak`, `ctle.config.lf_zero` |
| `c_rxselect_en`, `c_rxselect_direct` | 1, 1 | 0 | `rxselect.state.state`, `rxselect.select.branch` |
| `c_wmon_en`, `c_wmon_sel` | 1, 2 | 0 | decoded from `debug.wmon_select.select` |
| `c_detect_en`, `c_detect_thr`, `c_detect_se` | 1, 2, 2 | 0 | `detect.state.state`, `detect.config.low_threshold_code`, `high_threshold_code` |
| `c_detect_src_tx`, `c_detect_inject` | 1, 1 | 0 | `consolidation.detect.src_tx`, `detect.config.test_current_enable` |
| `c_vthdac_en`, `c_vthdac_a`, `c_vthdac_b` | 1, 8, 8 | 0, 128, 128 | `slicer.threshold.vth_enable`, `vth_a`, `vth_b` |
| `c_slicer_en` | 1 | 0 | `slicer.state.state` |
| `c_slicer_trim_<s>` (8 ports) | 10 | 0 | `slicer.offset.trim_<s>` |
| `c_slicer_vsel_e<k>` (4 ports) | 2 | 0 | `slicer.threshold.vsel_e<k>` |
| `c_ptrim_t<k>` (8 ports) | 5 | 0 | `cdr.phase_trim.p<k>` |
| `wire_rx_ptrim_en` | 1 | 0 | macro; must be 0 while the pll island is off |
| `c_wrx_cap_en`, `c_wordclk_en` | 1 | 0 | `slicer.state.state` |
| `c_wrx_cap_rcs` | 1 | 0 | `slicer.capture.rcsel` |
| `c_wrx_cap_b2`, `c_wrx_cap_b1`, `c_wordclk_d10`, `c_wordclk_d20` | 1 | 0 | decoded from `slicer.capture.rate_mode` (half → `b2`, `d10`; full → `b1`, `d20`) |
| `c_wrx_cap_psel`, `c_wrx_cap_slipp`, `c_wrx_cap_slipm` | 3, 1, 1 | 0 | dynamic: phase picker in `rtl/pt_wrx_ctl.sv` |
| `c_cdr_en` | 1 | 0 | `cdr.state.state` or `ring_c.config.line_pll` |
| `c_cdr_pfd_mode`, `c_cdr_ref_sel` | 1, 1 | 0 | `ring_c.config.line_pll`, `cdr.ac3.fll_ref_wck` |
| `c_cdr_g` | 3 | 2 | `cdr.ac3.loop_bw` |
| `c_cdr_otr` | 6 | 0 | `cdr.ac3.otr` (bit 5 = sign) |
| `c_cdr_fup`, `c_cdr_fdn` | 1, 1 | 0 | dynamic: frequency loop in `rtl/pt_wrx_ctl.sv` |
| `c_pll_cdr_en` | 1 | 0 | as `c_cdr_en`, and the ring regulator ready |
| `c_pll_cdr_n4/n8/n5/n10`, `c_pll_cdr_kp`, `c_pll_cdr_band` | 1 each, 3, 1 | 0, 0, 1 | `ring_c.config.modulus`, `kp`, `band` |
| `c_pllvreg_byp_cdr` | 1 | 1 | `pllvreg.config.rx_bypass` |
| `ct_det_clk` | 1 | – | detect clock from the macro |

Status into the macro: `s_detect_diff_pos/neg`, `s_detect_se_p/n`, `s_wrx_slp`, `s_wrx_slm`,
`s_pll_cdr_lock`, frequency-counter source `fc_src[1]` (ring `FBCK`). `wire_rx_valid` is made inside the
macro.

## 5. Open

1. **Capture pins change when a compact capture is published** (D-CAP): the committed `capture.py` has one
   word strobe `WSTB` in place of `DX0..39` and `WCLK40`; the macro then needs a strobe-domain front end and
   the 20→40 gear. The chip top binds the published r6.
2. **`CKP[0]` load** (D-PTRIM, D-WORDCLK): `wordclk_rx.CK` adds to the most heavily loaded phase; whether it
   should tap `CDRPH[0]` instead is undecided.
3. **Ring phases cross pll → wired_cap at the regulated swing** (about 0.9 × rail) into 3.3 V logic in
   `ptrim`; checked at tt only.
4. **Vote clamps** `iso_cdr_up/dn_*`: delay and pulse fidelity for one-ring-cycle pulses are not benched
   (D-ISO).
5. **`cdr.IB_PLL` open**: the ring takes `BIAS_pll_ring_rx`; that an open `IB_PLL` is safe is not confirmed
   (D-BIAS).
6. **Island of the trim fields** (D-TRIMISL): `cdr.phase_trim` and the word-divider controls are listed
   under the pll island in the register map but drive cells on wired_cap; `wordclk_rx` is not in that
   island's current budget.
7. **`c_cdr_g` reset value** (2 or 3) is undecided.
8. **Forwarded clock** (D-AUXWCK): needs the debug island on; receiver bench, route check and pad-exclusion
   rule are not done. `clockmux.AUX` and `clockmux.WCK` are the same net.
9. **No force path for KP calibration**: `FU/FD` are driven by the capture only.
10. **External-clock capture fallback** (D-EXTCLK): `clockmux` wire-clock outputs reach only prescalers and
    observation, not `CKP[0..7]`.
11. **P/N order at the bond pads** for `WIRE_RX_P/N` and `USB_DP/DN` is not checked against the bond map.
