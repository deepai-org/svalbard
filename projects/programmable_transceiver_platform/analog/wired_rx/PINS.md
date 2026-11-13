# Wired RX: pin list and connection intent (for chip-top integration)

Written 2026-11-13 from the sources below. No simulation was run for this file. Anything not found in a source is marked **OPEN**.

Path shorthand (all relative to `projects/programmable_transceiver_platform/` unless absolute):
`W/` = `analog/wired_rx/`, `IC:n` = `/home/ubuntu/svalbard/scratch/reviews/interface-changes.md` line n,
`MWX:n` = `/home/ubuntu/svalbard/scratch/reviews/mode-walk/part-wrx.md` line n, `NL:n` = `verification/chip_assembly/netlist.py` line n,
`SVH:n` = `rtl/pt_regmap_defs.svh` line n, `RMJ` = `spec/register-map.json`, `MAC:n` = `rtl/pt_digital_macro.sv` line n,
`CT:n` = `/home/ubuntu/svalbard/scratch/chip-top/NOTES.md` line n.

Revision state of the cells (read this first):

| Cell | Pin list used here | State |
|---|---|---|
| `pt_wrx_cap` | r7, `W/capture.py:572-575` (`TOP_PORTS`) | r7 pin list is final (row AP4-1-CAP), but the r7 GDS is NOT published: review NO-GO on ss/625 PD votes, r7b fix in extracted verification (README Resume 9 / CAPTURE). `W/generated/wrx_cap.lvs.spice:4707` and `wrx_cap.ext.spice:50259` were still r6 (with `DX0..39`, `WCLK40`) when this was written, and so is `scratch/chip-top/pins.txt:77-78`. Use r7 (W7-GEAR, `IC:1043`). |
| `pt_cdr` | both, see the cell table | `W/cdr.spice:22` = r13 (r12 + output mirror; 32 pins, adds `otr0..4 otrs`, rows AP4-1-CDR / CDR8-TRIM; staged, not published); published layout `W/generated/cdr.lvs.spice:3-4` = 26 pins (no `otr*`). **OPEN** (MW-36 `IC:1266`): bind the 26 published pins today; the six trim pins come with the r13 publish. |
| `pt_ptrim` | `W/ptrim.spice:7` | Published layout is the generic-row one, "not usable as laid out" (`W/README.md:389-390`); compact layout staged (`W/ptrim_compact.py`), on hold for the MW-14 output-stage redesign (README Resume 9 / PTRIM). Pin names unchanged; pins move to the east edge of each channel row (AP4-1-PTRIM). |
| `pt_pll_ring` (instance `pll_cdr`) | `analog/timing/pll_ring.spice:37` r9v/r9w | Published (`IC:1047`, `IC:1156`). |
| all others | their `.subckt` line | Same as `scratch/chip-top/pins.txt:61-82`. |

Instance names follow `NL` / `verification/chip_assembly/inventory.py` and the mode walk: `pad_hs_rx`, `pad_usb`, `termination`, `rxlevel`, `ctle`,
`rxselect`, `slicer`, `wrx_cap`, `ptrim`, `vthdac`, `wmon_sel`, `detect`, `cdr`, `pll_cdr`, `pll_vreg` (`pt_pll_vreg2`), `core_bias`,
`bb_tap_wmon`, `rx_wclk_in`, `clockmux`, `digital` (the macro). New instance needed: `wordclk_rx` (second `pt_wordclk`, MW-11).

Net names: existing `NL` names are kept (`CTLE_P/N`, `SL_P/N`, `WMON_IN`, `TERM_ENABLE`, `RAIL_wired`, `RAIL_pll`, `BIAS_*`, `EN_EFF_*`, `analog_cfg[n]`, `debug_cfg[n]`).
`WRX_P/N` (`NL:96-100`) is split into `HS_RX_P/N` and `USB_RX_P/N` (`W/README.md:792-793`). Macro static-config ports that do not exist yet are named
`c_<block>_<pin>` as in `CT:20`. Other new nets are named in section 3.

## 1. Signal flow

```
WIRE_RX_P/N (bond 20/21) -> pad_hs_rx (term + on-die AC coupling) --HS_RX_P/N--> ctle --CTLE_P/N--> rxselect --SL_P/N--> slicer
USB_DP/DN  (bond 24/25) -> pad_usb (term, rxlevel switches) ------USB_RX_P/N--> rxselect (direct), detect, wmon_sel
termination -> pad_usb (TERM_ENABLE, DIFF_ENABLE, TERM_VCM) and pad_hs_rx (HS_TERM_ENABLE, HS_TERM_TRIM[3:0], HS_TERM_VCM, HS_VBIAS)
rxlevel     -> pad_usb (DIV_ENABLE, BYPASS_ENABLE)
slicer D0,E0,D1,E1,D2,E2,D3,E3 --SMP[0..7]--> wrx_cap S0..S7 --wrx_dw/wrx_ew/wrx_slp/wrx_slm/wrx_wstb--> digital macro
pll_vreg.VOUT_CDR -> pll_cdr.VDD ; pll_cdr PH0..7 --RXPH[0..7]--> ptrim --CKP[0..7]--> slicer CKP0..7 and wrx_cap CKP0..7
wrx_cap UP0..3/DN0..3 --CDR_UP/CDR_DN--> cdr UP/DN (integral) and pll_cdr FU0..3/FD0..3 (proportional)
cdr.VCTRL --CDR_VCTRL--> pll_cdr.ATB_VCTRL ; cdr.REF_PLL -> pll_cdr.REF ; cdr.HOLD_PLL -> pll_cdr.HOLD ; cdr.IB_PLL -> pll_cdr.IBIAS (open, D4)
wordclk_rx (CK = CKP[0]) --RX_LDE--> wrx_cap.LDE
vthdac VTAP/VTAN/VTBP/VTBN -> slicer (edge-sampler aux pairs, IX-10)
detect: USB_RX_P/N or WIRE_TX_P/N -> DIFF_POS/DIFF_NEG/SE_P/SE_N -> digital (no consumer today)
wmon_sel: USB_RX_P/N or CTLE_P/N -> WMON_IN -> bb_tap_wmon.in_p -> WMON pad
```

Sources: `W/README.md:788-800` (HS/USB split), `W/slicer.spice:2-7`, `W/capture.py:572-575`, `W/cdr.spice:2-8`, `W/ptrim.spice:2-4`, `MWX:3-4`.

Islands: wired island rail `RAIL_wired` (cells call it `VDD_WIRE_SW`), pll island rail `RAIL_pll` (`VDD_PLL_SW`). `pll_cdr` runs on the
regulator output (`RAIL_pll_cdr` = `pll_vreg.VOUT_CDR`, ~0.9 x `RAIL_pll`, 2.69-3.015 V; `analog/timing/pll_ring.spice:4`, `IC:738`).

## 2. Cell pin tables

Type: supply / analog / fast clock / fast data / static config / bias / ATB. "3.3 V CMOS" = rail-to-rail on the named island rail.

### pad_hs_rx: `hs_protected_pad` (`analog/pads/generated/stress-safe-families/wired-receive-hs/physical.spice:1`)

Note: `scratch/chip-top/pins.txt:101-102` reports "NO SUBCKT" for this pad; the subckt is named `hs_protected_pad`, not `tx_protected_pad`.

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| VSS | - | supply | ground | `VSS` | physical.spice:1 |
| VDD | - | supply | wired island | `RAIL_wired` | PD21 `IC:800`; as wirepad `NL:131` |
| PAD_P, PAD_N | io | analog | chip pin | top `WIRE_RX_P`, `WIRE_RX_N` (bond 21/20, sites bidir[15]/[14]); **P/N-to-bond order OPEN** (`IC:801` says only "bond 20/21, WIRE_RX_N/WIRE_RX_P") | PD22 `IC:801` |
| RX_P, RX_N | out | analog | behind 4.9 pF MIM, CM = `HS_VBIAS` ~1.0 V | `HS_RX_P`, `HS_RX_N` -> `ctle.RX_P/N` only | `W/README.md:793`, `IC:800` |
| VBIAS | in | analog (DC) | 0.95-1.01 V | `HS_VBIAS` <- `termination.HS_VBIAS` | `W/termination.spice:6-7` |
| TERM_VCM | in | analog (DC) | 0.4 V (0.3-0.5) | `HS_TERM_VCM` <- `termination.HS_TERM_VCM` | `W/termination.spice:6`, PD27 `IC:806` |
| TERM_ENABLE | in | static config | 3.3 V CMOS, wired | `HS_TERM_ENABLE` <- `termination.HS_TERM_ENABLE` | `MWX:40` |
| TERM_TRIM0..3 | in | static config | 3.3 V CMOS, wired | `HS_TERM_TRIM[0..3]` <- `termination.HS_TERM_TRIM0..3` | `MWX:40`, `IC:806` |

No `ATB_ESD_RAIL` pin and no ATB leaf for this pad (`IC:806`).

### pad_usb: `tx_protected_pad`, wired-receive-usb (`scratch/chip-top/pins.txt:97-98`), wired-RX-relevant pins only

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| PAD_P, PAD_N | io | analog | chip pin | top `USB_DP`, `USB_DN` (bond 25/24). Not in `integration/pt_chip.sv` today | `IC:801`, `MWX:84` |
| VDD, VSS | - | supply | wired island | `RAIL_wired`, `VSS` | `NL:131` |
| RX_P, RX_N | out | analog | 0-3.3 V after rxlevel switches | `USB_RX_P`, `USB_RX_N` (today `WRX_P/N`, `NL:132`) -> rxselect, detect, wmon_sel | `W/README.md:792` |
| TERM_VCM | in | analog (DC) | 0 V (USB HS) or 1.2 V divider | `TERM_VCM` <- `termination.TERM_VCM` | `NL:102,131` |
| TERM_ENABLE, DIFF_ENABLE | in | static config | 3.3 V CMOS | `TERM_ENABLE`, `DIFF_ENABLE` <- termination | `NL:102,131` |
| DIV_ENABLE, BYPASS_ENABLE | in | static config | 3.3 V CMOS | `DIV_ENABLE`, `BYPASS_ENABLE` <- rxlevel | `NL:103,132` |
| TERM_TRIM0..2 | in | static config | 3.3 V CMOS | `analog_cfg[496..498]` (`usbhs.config.term_trim`, reset 4, AND `term_enable` [499]); unbound today | `SVH:434-437`, `MWX:89` |
| HS_PBIAS, HS_P, HS_N, FS_HIGH_P/N, FS_LOW_P/N, PULLUP_P/N, PULLDOWN_P/N, LS_SLOW, ATB_ESD_RAIL | | | | USB TX side / pads owner; not part of this file (see `MWX:90-93`, `CT:21-22`) | |

### termination: `pt_termination` (`W/termination.spice:11`), r3

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| VDD_WIRE_SW | - | supply | wired island | `RAIL_wired` | `W/README.md:165` |
| VSS | - | supply | ground | `VSS` | |
| term_en | in | static config | 3.3 V CMOS, wired | `c_termination_term_en` (NO FIELD; decode needed, D8) | `W/termination.spice:5`, `MWX:88` |
| term_mode0, term_mode1 | in | static config | 3.3 V CMOS | `c_termination_term_mode[0..1]` (decode of `termination.config.p_load` / `differential_100_enable`; raw binding is wrong) | `W/termination.spice:3-5`, `MWX:88` |
| hs_en | in | static config | 3.3 V CMOS | `c_termination_hs_en` (NO FIELD) | `W/termination.spice:6-8`, `MWX:41` |
| hs_term_en | in | static config | 3.3 V CMOS | `c_termination_hs_term_en` (NO FIELD) | same |
| hs_trim0..3 | in | static config | 3.3 V CMOS | `c_termination_hs_trim[0..3]` (NO FIELD; reset code 5) | `W/termination.spice:8-9`, `IC:806` |
| TERM_ENABLE | out | static config | 3.3 V CMOS | `TERM_ENABLE` -> `pad_usb.TERM_ENABLE` | `NL:102,131` |
| DIFF_ENABLE | out | static config | 3.3 V CMOS | `DIFF_ENABLE` -> `pad_usb.DIFF_ENABLE` | `NL:102,131` |
| TERM_VCM | out | analog (DC) | 1.2 V divider or VSS; 50k bleed | `TERM_VCM` -> `pad_usb.TERM_VCM`; ATB tap `ATBN_termination_vcm` | `W/termination.spice:4-5`, `NL:45` |
| HS_TERM_ENABLE | out | static config | 3.3 V CMOS (= hs_en & hs_term_en) | `HS_TERM_ENABLE` -> `pad_hs_rx.TERM_ENABLE` | `W/termination.spice:8` |
| HS_TERM_TRIM0..3 | out | static config | 3.3 V CMOS (= hs_trim & HS_TERM_ENABLE) | `HS_TERM_TRIM[0..3]` -> `pad_hs_rx.TERM_TRIM0..3` | `W/termination.spice:8-9` |
| HS_TERM_VCM | out | analog (DC) | 0.4 V divider (0.43-0.47 extracted), VSS when hs_en=0 | `HS_TERM_VCM` -> `pad_hs_rx.TERM_VCM` | `W/termination.spice:6`, `W/README.md:800` |
| HS_VBIAS | out | analog (DC) | 1.0 V divider (0.95-1.01), VSS when hs_en=0; load 2 x 40k | `HS_VBIAS` -> `pad_hs_rx.VBIAS` | `W/termination.spice:7`, `W/README.md:800` |

All seven HS nets and every control input are `UNBOUND_*` in the present chip netlist (`MWX:40`, `MWX:116-121`).

### rxlevel: `pt_rxlevel` (`W/rxlevel.spice:7`)

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| VDD_WIRE_SW, VSS | - | supply | wired island | `RAIL_wired`, `VSS` | |
| rxlevel_en | in | static config | 3.3 V CMOS | `c_rxlevel_en` = (`rxlevel.config.path` != 0); decode needed | `W/rxlevel.spice:4`, `MWX:97` |
| rxlevel_half | in | static config | 3.3 V CMOS | `c_rxlevel_half` = `rxlevel.config.path`[1] (`analog_cfg[415]`) | `MWX:97`, `SVH:366` |
| DIV_ENABLE | out | static config | 3.3 V CMOS, 100k bleed to VSS | `DIV_ENABLE` -> `pad_usb.DIV_ENABLE` | `W/rxlevel.spice:2-6`, `NL:103` |
| BYPASS_ENABLE | out | static config | 3.3 V CMOS, 100k bleed | `BYPASS_ENABLE` -> `pad_usb.BYPASS_ENABLE` | same |

rxlevel serves the USB pad only; the HS pad has no rxlevel network (`IC:800`).

### ctle: `pt_ctle` (`W/ctle.spice:13`), r3

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| VDD_WIRE_SW, VSS | - | supply | wired island | `RAIL_wired`, `VSS` | |
| IBIAS | in | bias | 10 uA into the pin (NMOS pass + diode) | `BIAS_ctle` <- `core_bias` wired bank | `W/ctle.spice:5`, `integration/core_bias.py:18`, `MWX:43` |
| ctle_en | in | static config | 3.3 V CMOS | `EN_EFF_ctle` (macro `en_eff[14]`) | `MAC:181` |
| wire_ctle_bypass | in | static config | 3.3 V CMOS | `debug_cfg[32]` (`debug.wire_bypass.ctle`) | `SVH:50`, `W/ctle.spice:6` |
| ctle_peak0, ctle_peak1 | in | static config | 3.3 V CMOS | `analog_cfg[182]`, `analog_cfg[183]` (`ctle.config.zero_trim`, 2 bits on the bus) | `SVH:268-269` |
| ctle_peak2 | in | static config | 3.3 V CMOS | `c_ctle_peak2` (NO FIELD; codes 4-7 unreachable) | `MWX:47` |
| lf_zero0..2 | in | static config | 3.3 V CMOS | `c_ctle_lf_zero[0..2]` (NO FIELD) | `W/ctle.spice:8-12`, `IC:785`, `CT:20` |
| RX_P, RX_N | in | analog | CM 0.8-1.4 V (tt), gate + bypass TG; ~255-264 fF/leg | `HS_RX_P`, `HS_RX_N` <- `pad_hs_rx.RX_P/N`. **Today wrongly on `WRX_P/N` = USB pad** (`NL:96`) | `W/README.md:793`, `MWX:39` (A1, MW-8) |
| CTLE_P, CTLE_N | out | analog | CM: header says ~1.0 V, README ~1.4 V, mode walk measured 1.21-1.66 V (sources disagree, D1/MW-23) | `CTLE_P`, `CTLE_N` -> `rxselect.CTLE_P/N`, `wmon_sel.CTLE_P/N` | `NL:96-100`, `W/ctle.spice:2`, `MWX:45` |
| atb_ctle_pbias | out | ATB | | `ATBN_ctle_bias` (ATB node 24) | `NL:44`, `W/README.md:181` |
| atb_ctle_src | out | ATB | | **OPEN**: not in `NL` ATB_PORTS (`NL:44-49`) | |

### rxselect: `pt_rxselect` (`W/rxselect.spice:6`)

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| VDD_WIRE_SW, VSS | - | supply | wired island | `RAIL_wired`, `VSS` | |
| rxselect_en | in | static config | 3.3 V CMOS | `EN_EFF_rxselect` (macro `en_eff[18]`) | `MAC:185` |
| rxselect_direct | in | static config | 3.3 V CMOS | `analog_cfg[420]` (`rxselect.select.branch`: 0 serial = CTLE, 1 usb_hs = direct) | `SVH:372`, `W/rxselect.spice:3-4` |
| CTLE_P, CTLE_N | in | analog | CTLE output | `CTLE_P`, `CTLE_N` | `NL:97` |
| RX_P, RX_N | in | analog | USB pad RX, 0-0.4 V in HS | `USB_RX_P`, `USB_RX_N` | `W/README.md:792` |
| SL_P, SL_N | out | analog | clamped to VSS when en=0 | `SL_P`, `SL_N` -> `slicer.SL_P/N`; ATB tap `ATBN_slicer_bias` on SL_P | `NL:98`, `NL:49` |

### slicer: `pt_slicer` (`W/slicer.spice:11`), r7 (114 pins)

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| VDD_WIRE_SW, VSS | - | supply | wired island | `RAIL_wired`, `VSS` | |
| slicer_en | in | static config | 3.3 V CMOS | `EN_EFF_slicer` (macro `en_eff[13]`). W7-SAFE asks for `slicer_en_reg & cap_en_reg`; `cap_en` does not exist (see 4) | `MAC:180`, `IC:1044` |
| SL_P, SL_N | in | analog | CM 0..~1.5 V | `SL_P`, `SL_N` <- rxselect | `W/slicer.spice:8`, `NL:98` |
| CKP0..CKP7 | in | fast clock | 3.3 V CMOS, wired, ring rate 480-810 MHz | `CKP[0..7]` <- `ptrim.CKP0..7` (same index) | `W/slicer.spice:3-5`, `W/ptrim.spice:2-4` |
| QCK | out | fast clock | 3.3 V CMOS (buffered CKP0) | no consumer (capture uses CKP0). Leave open or to `clk_obs` (`W/README.md:179`, obsolete pad after PD22): **OPEN** | `MWX:58` |
| D0, E0, D1, E1, D2, E2, D3, E3 | out | fast data | 3.3 V CMOS, valid one ring period | `SMP[0..7]` in this order -> `wrx_cap.S0..S7` | `W/slicer.spice:4`, `W/README.md:136`, `MWX:55` |
| trim_{s}_p0..2 (s = d0,e0,d1,e1,d2,e2,d3,e3; 24 pins) | in | static config | 3.3 V CMOS | `c_slicer_trim_{s}_p[0..2]` (coarse, P side). NO FIELD per sampler | `W/slicer.spice:9,11`, `MWX:74` (D6) |
| trim_{s}_n0..2 (24 pins) | in | static config | 3.3 V CMOS | `c_slicer_trim_{s}_n[0..2]` (coarse, N side). NO FIELD | same |
| trim_{s}_f0..3 (32 pins) | in | static config | 3.3 V CMOS | `c_slicer_trim_{s}_f[0..3]` (fine). NO FIELD | `W/README.md:557,972` |
| vsel_e0_0, vsel_e0_1, vsel_e1_0, vsel_e1_1, vsel_e2_0, vsel_e2_1, vsel_e3_0, vsel_e3_1 | in | static config | 3.3 V CMOS | `c_slicer_vsel_e{k}[0..1]` (00 off, 01 VTH_A, 1x VTH_B). NO FIELD | `W/slicer_compact.py:259-260`, `IC:782`, `CT:20` |
| VTAP, VTAN, VTBP, VTBN | in | analog (DC) | CM ~0.8 V, VSS when vthdac off | `VTAP`, `VTAN`, `VTBP`, `VTBN` <- vthdac | `W/vthdac.spice:5,8`, `MWX:104` |

Today's fields `slicer.offset.data/early/late` (4 b each, `analog_cfg[423..434]`, `SVH:376-381`) do not map onto the 80 trim pins.

### wrx_cap: `pt_wrx_cap` r7 (`W/capture.py:572-575`; W7-GEAR `IC:1043`)

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| S0..S7 | in | fast data | 3.3 V CMOS, wired | `SMP[0..7]` <- slicer D0,E0,D1,E1,D2,E2,D3,E3 | `W/README.md:136`, `W/capture.py:7-13` |
| CKP0..CKP7 | in | fast clock | 3.3 V CMOS, wired | `CKP[0..7]` <- `ptrim.CKP0..7` (shared with slicer) | `W/README.md:137` |
| EN | in | static config | 3.3 V CMOS | `c_wrx_cap_en` (`cap_en`; NO FIELD, NO PORT) | `IC:1044`, `MWX:59` |
| LDE | in | fast clock (one CKP0 period per 20-bit word) | 3.3 V CMOS | `RX_LDE` <- `wordclk_rx.LDE` (instance does not exist, MW-11) | `W/README.md:139`, `MWX:60` |
| RCS | in | static config | 3.3 V CMOS | `analog_cfg[36]` (`cdr.config.cap_rcsel` bit 1) | `SVH:210`, `IC:431`, `MWX:57` |
| B2, B1 | in | static config | 3.3 V CMOS | `c_wrx_cap_b2`, `c_wrx_cap_b1` (00 quarter, 10 half, 01 full). NO FIELD | `W/README.md:140`, `MWX:59` |
| PSEL0..2 | in | quasi-static (changes between words) | 3.3 V CMOS | `c_wrx_cap_psel[0..2]` from the full-rate phase picker. NO PORT | `W/README.md:141`, `MWX:87` |
| SLIPP, SLIPM | in | quasi-static (one word) | 3.3 V CMOS | `c_wrx_cap_slipp`, `c_wrx_cap_slipm`. NO PORT | `W/README.md:142` |
| DW0..DW19 | out | fast data (word rate, 20 UI) | 3.3 V CMOS, wired | `wrx_dw[0..19]` -> macro (DW0 = earliest line bit). No macro input today | `IC:1043` |
| EW0..EW19 | out | fast data (word rate) | 3.3 V CMOS, wired | `wrx_ew[0..19]` -> macro (EW[i] between data i and i+1). No macro input today | `IC:1043`, `IC:1055` |
| SLP, SLM | out | fast data (word rate) | 3.3 V CMOS | `wrx_slp`, `wrx_slm` -> macro | `W/README.md:144`, `IC:1043` |
| UP0..UP3 | out | fast data (one ring cycle per vote) | 3.3 V CMOS, wired | `CDR_UP[0..3]` -> `cdr.UP0..3` and `pll_cdr.FU0..3` | `W/cdr.spice:4`, `IC:452`, `MWX:61` |
| DN0..DN3 | out | fast data | 3.3 V CMOS, wired | `CDR_DN[0..3]` -> `cdr.DN0..3` and `pll_cdr.FD0..3` | same |
| WSTB | out | fast clock (one rising edge per 20-bit word; >= 6.0 ns period) | 3.3 V CMOS, wired | `wrx_wstb` -> macro (generated clock; register DW/EW/SLP/SLM on its rising edge only) | `IC:1043` |
| VDD, VSS | - | supply | wired island | `RAIL_wired`, `VSS` | `inventory.py:71` |

Removed in r7: `DX0..DX39`, `WCLK40`. The macro still has `wire_rx_data[39:0]` / `wire_rx_clk` / `wire_rx_valid` (`MAC:36-39`); the 20->40 gear,
the second EW flop (SLI7-M) and the CDC move into the macro (`IC:1043`, `IC:1055`). Not implemented in RTL.

### ptrim: `pt_ptrim` (`W/ptrim.spice:7`)

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| VDD_WIRE_SW, VSS | - | supply | wired island | `RAIL_wired`, `VSS` | |
| ptrim_en | in | static config | 3.3 V CMOS | `wire_rx_ptrim_en` (macro output = `slicer.state` == active; not connected in `integration/pt_chip.sv`). W7-SAFE wording differs (`ptrim_en_reg & wrx_rx_en_reg`); DT-9 is what the RTL does | `MAC:49,128`, `IC:1055`, `IC:1044`, `MWX:54` |
| PH0..PH7 | in | fast clock | swing = regulated ring rail (2.7-3.0 V) into 3.3 V NAND gates; crosses pll -> wired island | `RXPH[0..7]` <- `pll_cdr.PH0..7` (same index) | `W/ptrim.spice:2-3`, `IC:738`, `MWX:49-50` |
| CKP0..CKP7 | out | fast clock | 3.3 V CMOS, wired; low when ptrim_en=0 | `CKP[0..7]` -> `slicer.CKPk`, `wrx_cap.CKPk`; `CKP[0]` also -> `wordclk_rx.CK` | `W/ptrim.spice:3-4`, `MWX:51` |
| T{k}_0..T{k}_4, k = 0..7 (40 pins) | in | static config | 3.3 V CMOS | `analog_cfg[526 + 5k + b]` (`cdr.phase_trim.p{k}` bit b). Field is on the pll island, the cell on the wired island | `SVH:454-461` (+ p4..p7), `W/ptrim.spice:3`, `MWX:53` |

### vthdac: `pt_vthdac` (`W/vthdac.spice:8`)

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| VDD_WIRE_SW, VSS | - | supply | wired island | `RAIL_wired`, `VSS` | |
| vth_en | in | static config | 3.3 V CMOS | `c_vthdac_en` (NO FIELD) | `MWX:105`, `CT:20` |
| A0..A7 | in | quasi-static (fast update path IX-11 wanted) | 3.3 V CMOS | `c_vthdac_a[0..7]` (NO FIELD) | `W/vthdac.spice:3-5`, `IC:783` |
| B0..B7 | in | quasi-static | 3.3 V CMOS | `c_vthdac_b[0..7]` (NO FIELD) | same |
| VTAP, VTAN | out | analog (DC) | P+N ~1.6 V, CM ~0.8 V, 8k loads to VSS | `VTAP`, `VTAN` -> slicer | `W/vthdac.spice:4-6` |
| VTBP, VTBN | out | analog (DC) | same | `VTBP`, `VTBN` -> slicer | same |

Self-biased; no IBIAS pin (`W/vthdac.spice:2-3`). Not in `inventory.py` / `NL` (`MWX:13-14`).

### wmon_sel: `pt_wmon_sel` (`W/wmon_sel.spice:6`)

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| VDD_WIRE_SW, VSS | - | supply | wired island | `RAIL_wired`, `VSS` | |
| wmon_en | in | static config | 3.3 V CMOS | `c_wmon_en` = (`debug.wmon_select.select` != 0); decode needed | `MWX:221`, `SVH:54` |
| wmon_sel0, wmon_sel1 | in | static config | 3.3 V CMOS | `c_wmon_sel[0..1]` = select - 1 (field values off, rx_p, rx_n, ctle_p, ctle_n = `debug_cfg[34..36]`; cell 00 RX_P, 01 RX_N, 10 CTLE_P, 11 CTLE_N) | `W/wmon_sel.spice:3`, `RMJ` |
| RX_P, RX_N | in | analog | USB pad RX | `USB_RX_P`, `USB_RX_N` | `W/README.md:792` |
| CTLE_P, CTLE_N | in | analog | | `CTLE_P`, `CTLE_N` | `NL:100` |
| WMON_IN | out | analog | clamped to VSS when off | `WMON_IN` -> `bb_tap_wmon.in_p` | `NL:81,101` |

### detect: `pt_detect` (`W/detect.spice:11`)

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| VDD_WIRE_SW, VSS | - | supply | wired island | `RAIL_wired`, `VSS` | |
| IBIAS | in | bias | 10 uA into the pin | `BIAS_detect` <- `core_bias` wired bank | `integration/core_bias.py:18`, `W/README.md:165-166` |
| det_en | in | static config | 3.3 V CMOS | `EN_EFF_detect` (macro `en_eff[6]`) | `MAC:167` |
| det_clk | in | slow clock | 3.3 V CMOS | macro `ct_det_clk` (`ct_cfg_det_div` tied 0 in `integration/pt_chip.sv:82`); unbound today; rate **OPEN** | `MAC:70`, `MWX:96` |
| RX_P, RX_N | in | analog | USB pad RX | `USB_RX_P`, `USB_RX_N` | `W/README.md:792`, `NL:99` |
| TX_P, TX_N | in | analog | TX pads (NMOS-only pass) | `WIRE_TX_P`, `WIRE_TX_N` | `NL:99`, `W/detect.spice:6-7` |
| det_thr0, det_thr1 | in | static config | 3.3 V CMOS | `analog_cfg[198]`, `[199]` (`detect.config.low_threshold_code`) | `SVH:290`, `MWX:95` |
| det_se0, det_se1 | in | static config | 3.3 V CMOS | `analog_cfg[196]`, `[197]` (`detect.config.high_threshold_code`) | `SVH:288`, `MWX:95` |
| det_src_tx | in | static config | 3.3 V CMOS | `c_detect_src_tx` (NO FIELD) | `W/README.md:160` |
| det_inject | in | static config | 3.3 V CMOS | nearest field `detect.config.test_current_enable` = `analog_cfg[200]`; mapping not stated in any source: **OPEN** | `SVH:292`, `W/detect.spice:9-10` |
| DIFF_POS, DIFF_NEG | out | data (sampled on det_clk) | 3.3 V CMOS, wired | `det_diff_pos`, `det_diff_neg` -> macro (no consumer today) | `W/detect.spice:3`, `MWX:94`, `CT:22` |
| SE_P, SE_N | out | data | 3.3 V CMOS, wired | `det_se_p`, `det_se_n` -> macro (no consumer today) | `W/detect.spice:4`, `CT:22` |
| atb_det_vref | out | ATB | | `ATBN_detect_ibias` | `NL:44` |

`pt_detect` cannot take the HS pair or the CTLE output (`W/README.md:804-808`).

### cdr: `pt_cdr`

Published layout, 26 pins (`W/generated/cdr.lvs.spice:3-4`):
`VDD_PLL_SW VSS IBIAS cdr_en pfd_mode ref_sel g0 g1 g2 UP0 UP1 UP2 UP3 DN0 DN1 DN2 DN3 FUP FDN IB_PLL HOLD_PLL VCTRL REF_IN WCK_IN REF_PLL atb_cdr_pbias`

Current schematic r12, 32 pins (`W/cdr.spice:22`): the same 26 followed by `otr0 otr1 otr2 otr3 otr4 otrs`. **Difference OPEN** (MW-36).

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| VDD_PLL_SW | - | supply | pll island (unregulated) | `RAIL_pll` | `W/README.md:165` |
| VSS | - | supply | | `VSS` | |
| IBIAS | in | bias | 10 uA into the pin (NMOS pass, `cdr.spice:51`) | **OPEN (D4)**: `core_bias` has no `cdr` consumer. Candidates: `BIAS_pll_ring_rx`, or the spare `BIAS_pll_ring_host` | `integration/core_bias.py:17`, `MWX:64`, `MWX:197-202` |
| cdr_en | in | static config | 3.3 V CMOS, pll | `EN_EFF_cdr` (macro `en_eff[12]`) | `MAC:179` |
| pfd_mode | in | static config | 3.3 V CMOS | `c_cdr_pfd_mode` (NO FIELD; asked `cdr.config.pfd_mode`, reset 0) | `W/cdr.spice:6-8`, `IC:430` |
| ref_sel | in | static config | 3.3 V CMOS | `c_cdr_ref_sel` (NO FIELD; nearest `cdr.ac3.fll_ref_wck` = `analog_cfg[525]`) | `IC:430`, `SVH:452`, `MWX:67` |
| g0..g2 | in | static config | 3.3 V CMOS | `analog_cfg[522..524]` (`cdr.ac3.loop_bw`) | `SVH:450`, `MWX:67` |
| UP0..UP3 | in | fast data | from 3.3 V wired island into pll island gates | `CDR_UP[0..3]` <- `wrx_cap.UP0..3` | `W/cdr.spice:4`, `IC:430` |
| DN0..DN3 | in | fast data | same | `CDR_DN[0..3]` <- `wrx_cap.DN0..3` | same |
| FUP, FDN | in | fast data (FLL pulses) | 3.3 V CMOS | `c_cdr_fup`, `c_cdr_fdn` from the digital FLL. NO PORT, no FLL in the hardened RTL (A3, MW-10) | `W/cdr.spice:6-7`, `MWX:66` |
| IB_PLL | out | bias | 10 uA sourced (PMOS, `cdr.spice:58`), clamped to VSS when off | `CDR_IB_PLL` -> `pll_cdr.IBIAS` (`W/cdr.spice:19`, `W/README.md:69-70`). `NL` instead feeds the ring from `BIAS_pll_ring_rx`: two candidate sources, **OPEN (D4)** | `MWX:64` |
| HOLD_PLL | out | static (= NAND(cdr_en, pfd_mode)) | 3.3 V CMOS on `RAIL_pll` | `CDR_HOLD_PLL` -> `pll_cdr.HOLD` | `W/cdr.spice:47-50`, `IC:430` |
| VCTRL | io | analog | 0.8-2.2 V | `CDR_VCTRL` -> `pll_cdr.ATB_VCTRL` (the ring has no VCTRL pin). `NL:122` has the net but nothing else on it | `W/cdr.spice:14`, `MWX:62` |
| REF_IN | in | clock | 3.3 V CMOS | clockmux `PREF` net. `NL:122` binds `ref_clk` directly today | `IC:968`, `NL:122` |
| WCK_IN | in | clock | 3.3 V CMOS | `WCK_EXT` <- `rx_wclk_in.OUTP` (`pt_diff_clk_rx`) | `IC:430`, `NL:91` |
| REF_PLL | out | clock | 3.3 V CMOS on `RAIL_pll` (= ref_sel ? WCK_IN : REF_IN; low when off) | `CDR_REF_PLL` -> `pll_cdr.REF` (today `pll_cdr.REF` = `ref_clk`, `NL:113`) | `W/cdr.spice:8`, `IC:968` |
| atb_cdr_pbias | out | ATB | | `ATBN_cdr_bias` | `NL:46` |
| otr0..otr4 (r12 only) | in | static config | 3.3 V CMOS | `c_cdr_otr[0..4]` (offset trim magnitude, 1/8 vote LSB). NO FIELD, not in the layout | `W/cdr.spice:15-16`, `MWX:65` |
| otrs (r12 only) | in | static config | 3.3 V CMOS | `c_cdr_otrs` (trim sign). NO FIELD, not in the layout | same |

Stale in `NL:122`: `cdr.FBCK_IN`, `cdr.freq_hold` (pins removed by AC3-W3, `IC:430`). `W/cdr.spice:16` cites an interface row "CDR8-TRIM"; no such row exists in `interface-changes.md`.

### pll_cdr: `pt_pll_ring` (`analog/timing/pll_ring.spice:37`), r9v/r9w

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| REF | in | clock | CMOS | `CDR_REF_PLL` <- `cdr.REF_PLL` (today `ref_clk`, `NL:113`) | `IC:968`, `MWX:63` |
| EN | in | static config | CMOS | `EN_EFF_pll_cdr` (macro `en_eff[10]`, includes `vreg_rx_ok`) | `MAC:177` |
| N4, N8 | in | static config | CMOS | `MWX:67` maps them to `consolidation.pll.feedback_n` (`debug_cfg[98..99]`, values 16/32/64/128); the ring divides by 16 / 8 (N8) / 4 (N4): encoding does not match, **OPEN**. Host-follow needs N4=1 (`IC:968`) | `SVH:98`, `pll_ring.spice:20-21` |
| HOLD | in | static | CMOS | `CDR_HOLD_PLL` <- `cdr.HOLD_PLL` (unbound today) | `IC:430`, `MWX:63` |
| IBIAS | in | bias | 10 uA into an NMOS diode (`pll_ring.spice:45`) | `CDR_IB_PLL` <- `cdr.IB_PLL` (intent) or `BIAS_pll_ring_rx` (`NL:24` today): **OPEN (D4)** | `MWX:64` |
| PH0..PH7 | out | fast clock | swing 0..`RAIL_pll_cdr` (2.7-3.0 V), ring rate | `RXPH[0..7]` -> `ptrim.PH0..7`. PH0 also needed by the `prescale.CK_IN` 2:1 select (host_follow; unbound, `IC:968`) | `IC:738`, `MWX:49` |
| LOCK | out | status (informative) | CMOS | **OPEN** (`pll_tx.LOCK` is `analog_status[0]`, `NL:116`; nothing for pll_cdr) | `pll_ring.spice:167-168` |
| FBCK | out | clock (<= 52 MHz; 83 MHz in /10) | CMOS | `fc_src[1]` (macro frequency counter) | `NL:115`, `MWX:68` |
| REFO | out | clock | CMOS | **OPEN** (clean reference copy for the lock checker, `pll_ring.spice:57-59`; no binding in `NL`) | |
| ATB_VCTRL | io | analog | loop node, 0.85-2.05 V | `CDR_VCTRL` <-> `cdr.VCTRL` (not an ATB leaf on this instance) | `MWX:62`, `W/README.md:182` |
| N5, N10 | in | static config | CMOS | `c_pll_cdr_n5`, `c_pll_cdr_n10` (NO FIELD; override N4/N8) | `pll_ring.spice:8-10`, `IC:452` |
| KP0..KP2 | in | static config | CMOS | `c_pll_cdr_kp[0..2]` (NO FIELD; asked `cdr.config.kp[2:0]`; 0 = proportional path off). Pins on the block bottom edge | `pll_ring.spice:14-15`, `IC:452`, `IC:1047` |
| FU0..FU3 | in | fast data | from the 3.3 V wired island | `CDR_UP[0..3]` <- `wrx_cap.UP0..3` (bottom edge) | `pll_ring.spice:11-15`, `IC:452`, `IC:1047` |
| FD0..FD3 | in | fast data | same | `CDR_DN[0..3]` <- `wrx_cap.DN0..3` (bottom edge) | same |
| BAND | in | static config | CMOS | `c_pll_cdr_band` (NO FIELD; asked `ring_c.band`, reset 1). Tied `VDD` today | `NL:121`, `IC:974` |
| VDD | - | supply | regulated, ~0.9 x `RAIL_pll` | `RAIL_pll_cdr` <- `pll_vreg.VOUT_CDR`. Today on `RAIL_pll` (`MWX:48`, D5/MW-31) | `pll_ring.spice:4`, `IC:947` |
| VSS | - | supply | | `VSS` | |

### pll_vreg: `pt_pll_vreg2` (`analog/pll_vreg/generated/pt_pll_vreg2.ext.spice:3`), shared with the TX ring

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| VIN | - | supply | pll island | `RAIL_pll` | `analog/pll_vreg/README.md:19` |
| VOUT_CDR | out | supply | 0.9 x VIN (2.57-3.01 V) | `RAIL_pll_cdr` -> `pll_cdr.VDD` | `IC:947` |
| VOUT_TX | out | supply | same | `pll_tx.VDD` (wired TX / timing; outside this file) | `IC:947` |
| VSS | - | supply | | `VSS` | |
| BYP_CDR | in | static config | 3.3 V CMOS, active high | `analog_cfg[578]` (`pllvreg.config.rx_bypass`, reset 1 = bypassed) | `SVH:480`, `MAC:175` |
| BYP_TX | in | static config | | `analog_cfg[577]` (`pllvreg.config.tx_bypass`, reset 1) | `SVH:478` |
| ATB_OUT, ATB_G | io | ATB | | **OPEN**: no ATB leaf assigned (cell not in `inventory.py`/`NL`) | `analog/pll_vreg/README.md:30,57`, `MWX:13` |

### wordclk_rx: second `pt_wordclk` (`scratch/chip-top/pins.txt:29-30`; header `analog/timing/wordclk.spice:1-20`): proposed, MW-11

Only one `pt_wordclk` exists (`inventory.py:293`), on the TX ring (`NL:114`). The capture needs LDE from a divider clocked by the RX ring (`MWX:141-147`).

| Pin | Dir | Type | Domain / level | Connects to | Source |
|---|---|---|---|---|---|
| CK | in | fast clock | ring rate | `CKP[0]` (post-ptrim, as the capture sees it): mode walk says "pll_cdr CKP0"; `wordclk.spice:3` says ring PH0. Which side of ptrim, and which island rail the cell sits on: **OPEN** | `MWX:147` |
| EN | in | static config | | `c_wrx_cap_en` (same as capture EN): inferred, **OPEN** | |
| D10, D20 | in | static config | | `c_wrx_cap_b2`, `c_wrx_cap_b1` (wordclk: D10 = half rate, D20 = full rate; capture: B2 = half, B1 = full). Inferred from the two encodings, not stated in a source: **OPEN** | `wordclk.spice:4-7`, `W/README.md:140` |
| LDE | out | fast clock | one CK period per word | `RX_LDE` -> `wrx_cap.LDE` | `W/README.md:139` |
| WORD_CLK, LD, LDB | out | | | not used by wired RX (the macro clocks on `wrx_wstb`): leave open | `IC:1043` |
| VDD, VSS | - | supply | | **OPEN** (`inventory.py:59` lists the master on the pll island) | |

## 3. Net list view

One row per inter-block net. "macro" = `pt_digital_macro` (through isolation where the islands differ).

### Analog signal path

| Net | Driver | Loads | Notes |
|---|---|---|---|
| `WIRE_RX_P`, `WIRE_RX_N` (top) | chip pins, bond 21/20 | `pad_hs_rx.PAD_P/N` | P/N order OPEN |
| `USB_DP`, `USB_DN` (top) | chip pins, bond 25/24 | `pad_usb.PAD_P/N` | ports missing in `pt_chip.sv` |
| `HS_RX_P`, `HS_RX_N` | `pad_hs_rx.RX_P/N` | `ctle.RX_P/N` only (<= 20 fF extra allowed) | new net (MW-8) |
| `USB_RX_P`, `USB_RX_N` | `pad_usb.RX_P/N` | `rxselect.RX_P/N`, `detect.RX_P/N`, `wmon_sel.RX_P/N` | rename of `WRX_P/N`; remove ctle from it |
| `CTLE_P`, `CTLE_N` | `ctle.CTLE_P/N` | `rxselect.CTLE_P/N`, `wmon_sel.CTLE_P/N` | |
| `SL_P`, `SL_N` | `rxselect.SL_P/N` | `slicer.SL_P/N` (+ ATB tap `slicer_bias` on SL_P) | ~0.66 pF per leg at the slicer (`MWX:25`) |
| `WMON_IN` | `wmon_sel.WMON_IN` | `bb_tap_wmon.in_p` | |
| `WIRE_TX_P`, `WIRE_TX_N` | TX pads | `detect.TX_P/N` | |
| `VTAP`, `VTAN`, `VTBP`, `VTBN` | `vthdac` | `slicer` | new |

### Pad control

| Net | Driver | Loads |
|---|---|---|
| `TERM_ENABLE`, `DIFF_ENABLE`, `TERM_VCM` | `termination` | `pad_usb` |
| `DIV_ENABLE`, `BYPASS_ENABLE` | `rxlevel` | `pad_usb` |
| `HS_TERM_ENABLE` | `termination.HS_TERM_ENABLE` | `pad_hs_rx.TERM_ENABLE` |
| `HS_TERM_TRIM[0..3]` | `termination.HS_TERM_TRIM0..3` | `pad_hs_rx.TERM_TRIM0..3` |
| `HS_TERM_VCM` | `termination.HS_TERM_VCM` | `pad_hs_rx.TERM_VCM` |
| `HS_VBIAS` | `termination.HS_VBIAS` | `pad_hs_rx.VBIAS` |

### Clocks, samples, votes (bit order is the binding)

| Net | Driver | Loads |
|---|---|---|
| `RXPH[k]`, k = 0..7 | `pll_cdr.PHk` | `ptrim.PHk` (and PH0 to the host-follow prescale select, `IC:968`) |
| `CKP[k]`, k = 0..7 | `ptrim.CKPk` | `slicer.CKPk`, `wrx_cap.CKPk`; `CKP[0]` also `wordclk_rx.CK` |
| `SMP[0]` | `slicer.D0` | `wrx_cap.S0` |
| `SMP[1]` | `slicer.E0` | `wrx_cap.S1` |
| `SMP[2]` | `slicer.D1` | `wrx_cap.S2` |
| `SMP[3]` | `slicer.E1` | `wrx_cap.S3` |
| `SMP[4]` | `slicer.D2` | `wrx_cap.S4` |
| `SMP[5]` | `slicer.E2` | `wrx_cap.S5` |
| `SMP[6]` | `slicer.D3` | `wrx_cap.S6` |
| `SMP[7]` | `slicer.E3` | `wrx_cap.S7` |
| `CDR_UP[k]`, k = 0..3 | `wrx_cap.UPk` | `cdr.UPk`, `pll_cdr.FUk` |
| `CDR_DN[k]`, k = 0..3 | `wrx_cap.DNk` | `cdr.DNk`, `pll_cdr.FDk` |
| `RX_LDE` | `wordclk_rx.LDE` | `wrx_cap.LDE` |
| `wrx_dw[0..19]`, `wrx_ew[0..19]`, `wrx_slp`, `wrx_slm` | `wrx_cap` | macro (new inputs) |
| `wrx_wstb` | `wrx_cap.WSTB` | macro (new clock input; replaces `wire_rx_clk` <- WCLK40) |

Sampler order sources: `W/slicer.spice:4`, `W/README.md:136`, `MWX:55`. Phase load per `CKP[k]` (estimate): CKP0 ~1.0 pF, CKP1..7 ~0.45-0.6 pF, against a
150 fF bench load (`MWX:25-26`, MW-14).

### CDR loop

| Net | Driver | Loads | Notes |
|---|---|---|---|
| `CDR_VCTRL` | `cdr.VCTRL` (and the ring's own pump/filter) | `pll_cdr.ATB_VCTRL` | keep short and quiet; ~7 pF node (`W/cdr.spice:18`) |
| `CDR_REF_PLL` | `cdr.REF_PLL` | `pll_cdr.REF` | replaces `ref_clk` on the ring (`NL:113`) |
| `CDR_HOLD_PLL` | `cdr.HOLD_PLL` | `pll_cdr.HOLD` | |
| `CDR_IB_PLL` | `cdr.IB_PLL` | `pll_cdr.IBIAS` | OPEN vs `BIAS_pll_ring_rx` (D4) |
| clockmux `PREF` | `clockmux.PREF` | `cdr.REF_IN` | today `ref_clk` (`NL:122`) |
| `WCK_EXT` | `rx_wclk_in.OUTP` | `cdr.WCK_IN` (existing loads unchanged) | |
| `fc_src[1]` | `pll_cdr.FBCK` | macro frequency counter | exists (`NL:115`) |
| `RAIL_pll_cdr` | `pll_vreg.VOUT_CDR` | `pll_cdr.VDD` | new (D5) |

### Bias (`integration/core_bias.py:14-20`, bank output `BIAS_<consumer>`, enable `EN_<consumer>`)

| Consumer pin | core_bias output today | Intent |
|---|---|---|
| `ctle.IBIAS` | `BIAS_ctle` (wired bank, `EN_ctle` = `EN_EFF_ctle`) | OK (`MWX:43`) |
| `detect.IBIAS` | `BIAS_detect` (wired bank) | OK |
| `pll_cdr.IBIAS` | `BIAS_pll_ring_rx` (pll bank, `NL:24`) | wired RX intent: from `cdr.IB_PLL`. OPEN |
| `cdr.IBIAS` | none (no `cdr` consumer) | OPEN: `BIAS_pll_ring_rx` if the ring takes `IB_PLL`, else the spare `BIAS_pll_ring_host` (pll_host deleted, `IC:968`) |
| `vthdac`, `slicer`, `ptrim`, `wrx_cap`, `termination`, `rxlevel`, `rxselect`, `wmon_sel` | none | no IBIAS pin (self-biased or digital) |

### Island and level crossings

No isolation or level cell is instanced for any of these today (`MWX:78`, `MWX:248`). Each is gate-only at the receiver.

| Net | From | To | Concern |
|---|---|---|---|
| `RXPH[0..7]` | pll island, regulated rail (2.7-3.0 V swing) | wired island, 3.3 V NAND in ptrim | reduced swing accepted at tt (+20 ps, `MWX:50`); corners not simulated |
| `CDR_UP/DN[0..3]` | wired island 3.3 V | `cdr` on `RAIL_pll` and `pll_cdr` FT macro on `RAIL_pll_cdr` | must be low when the wired island is off and the pll island on (host_follow, `pfd_mode`=1, KP=0, `IC:968`): clamp **OPEN** |
| `wrx_dw/ew/slp/slm/wstb`, `det_*` | wired island | core (macro) | iso to 0 when the island is off |
| `T{k}_{b}` (`cdr.phase_trim`) | core, gated by the pll island (`RMJ` `islands: ['pll']`) | ptrim on the wired island | field island list should include wired: **OPEN** |
| `fc_src[1]`, `LOCK`, `REFO` | pll island | core | exists for FBCK |
| static config from the macro | core | wired / pll island cells | macro clamps outputs to 0 when the listed island is off (`RMJ` gating_rule) |

## 4. Controls needed from the digital macro / register map

"Bus bit" = index into the macro output `analog_cfg[]` / `debug_cfg[]`. Reset values from `spec/register-map.json` (`default`). Every listed field is
clamped to 0 while its island is off. "NO FIELD" = demand on digital (new register field and macro port); "NO PORT" = dynamic signal with no macro port.

### Static configuration

| Cell pin(s) | Field today (bus bit) | Reset | Safe state | Status / what is needed |
|---|---|---|---|---|
| `termination.term_en` | none | - | 0 (off) | NO FIELD. Decode from `termination.config.p_load` != off or `differential_100_enable` (D8) |
| `termination.term_mode[1:0]` | `termination.config.p_load` (`analog_cfg[438..439]`: off / 45_to_ground / 50_to_vcm), `differential_100_enable` (`[437]`) | 0 | 00 | Decode needed: 45_to_ground -> 11, 50_to_vcm -> 01, diff 100 -> 10. Raw binding selects the wrong mode (`MWX:88`). No owner |
| `termination.hs_en` | none | - | 0 (HS_VBIAS, HS_TERM_VCM grounded) | NO FIELD (MW-9). With 0 the CTLE input CM is 0 V |
| `termination.hs_term_en` | none | - | 0 | NO FIELD (MW-9) |
| `termination.hs_trim[3:0]` | none | asked: 5 | any | NO FIELD (PD27 `IC:806`: `termination.config.trim[3:0]`, reset 5) |
| `pad_usb.TERM_TRIM[2:0]` | `usbhs.config.term_trim` (`analog_cfg[496..498]`) AND `term_enable` (`[499]`) | 4 / 0 | 0 | exists, unbound |
| `rxlevel.rxlevel_en`, `rxlevel_half` | `rxlevel.config.path` (`analog_cfg[414..415]`: off / bypass / half) | 0 | 0, 0 | Decode needed: en = path != 0, half = path[1] (`MWX:97`) |
| `ctle.ctle_en` | `ctle.state.state` -> `EN_EFF_ctle` | 0 | 0 | exists |
| `ctle.wire_ctle_bypass` | `debug.wire_bypass.ctle` (`debug_cfg[32]`) | 0 | 0 | exists |
| `ctle.ctle_peak[2:0]` | `ctle.config.zero_trim` (`analog_cfg[182..183]`), 2 bits on the bus | 0 | 0 | third bit NO FIELD (peak width 3 bits) |
| `ctle.lf_zero[2:0]` | none | asked: 0 | 0 | NO FIELD (`ctle.config.lf_zero[2:0]`, IX-13 `IC:785`) |
| `rxselect.rxselect_en` | `rxselect.state.state` -> `EN_EFF_rxselect` | 0 | 0 | exists |
| `rxselect.rxselect_direct` | `rxselect.select.branch` (`analog_cfg[420]`) | 0 | 0 | exists, unbound |
| `slicer.slicer_en` | `slicer.state.state` -> `EN_EFF_slicer` | 0 | 0 | exists; W7-SAFE AND with `cap_en` not implemented |
| `slicer.trim_{s}_{p,n}[2:0]`, `trim_{s}_f[3:0]` (80 bits) | `slicer.offset.data/early/late`, 4 b each (`analog_cfg[423..434]`) | 0 | all 0 | NO FIELD per sampler: need 8 x (3 + 3 + 4) bits. Bit map owed by wired RX (D6) |
| `slicer.vsel_e{0..3}[1:0]` | none | - | 00 (aux pairs off) | NO FIELD (`cdr.vth_sel_e0..e3`, `MWX:105`) |
| `vthdac.vth_en`, `A[7:0]`, `B[7:0]` | none | - | 0 | NO FIELD (`cdr.vth_en`, `cdr.vth_a/b[7:0]`) + IX-11 fast update opcode |
| `ptrim.ptrim_en` | none; macro output `wire_rx_ptrim_en` = (`slicer.state` == active) | 0 | 0 (CKP low) | exists in RTL (DT-9), not connected in `pt_chip.sv` |
| `ptrim.T{k}[4:0]` | `cdr.phase_trim.p{k}` (`analog_cfg[526 + 5k ..]`) | 0 (AC3-W6 `IC:449` asked 16 = mid-range) | any | exists; reset value disagrees with the request; island list pll vs cell on wired |
| `wrx_cap.EN` | none | - | 0 | NO FIELD / NO PORT (`cap_en`, W7-SAFE) |
| `wrx_cap.RCS` | `cdr.config.cap_rcsel`[1] (`analog_cfg[36]`) | field 1 -> RCS 0 | 0 | exists, unbound |
| `wrx_cap.B2`, `B1` (+ `wordclk_rx.D10`, `D20`) | none | - | 00 (quarter) | NO FIELD (rate mode) |
| `wmon_sel.wmon_en`, `wmon_sel[1:0]` | `debug.wmon_select.select` (`debug_cfg[34..36]`, 5 values) | 0 | 0 | Decode needed (en = sel != 0, code = sel - 1) |
| `detect.det_en` | `detect.state.state` -> `EN_EFF_detect` | 0 | 0 | exists |
| `detect.det_thr[1:0]` | `detect.config.low_threshold_code` (`analog_cfg[198..199]`) | 0 | 0 | exists, unbound |
| `detect.det_se[1:0]` | `detect.config.high_threshold_code` (`analog_cfg[196..197]`) | 0 | 0 | exists, unbound |
| `detect.det_src_tx` | none | - | 0 | NO FIELD |
| `detect.det_inject` | `detect.config.test_current_enable` (`analog_cfg[200]`)? | 0 | 0 | mapping OPEN |
| `cdr.cdr_en` | `cdr.state.state` -> `EN_EFF_cdr` | 0 | 0 | exists |
| `cdr.pfd_mode` | none | asked: 0 | 0 | NO FIELD |
| `cdr.ref_sel` | none (`cdr.ac3.fll_ref_wck` `analog_cfg[525]` is the nearest) | 0 | 0 | NO FIELD or re-purpose |
| `cdr.g[2:0]` | `cdr.ac3.loop_bw` (`analog_cfg[522..524]`) | 2 (`RMJ`); `IC:430` asked 3; `IC:739` says reset TBD (meaning now exponential integral gain) | any | exists; reset value OPEN |
| `cdr.otr[4:0]`, `otrs` (r12) | none | - | 0 | NO FIELD; only if r12 is laid out |
| `pll_cdr.EN` | `cdr.state.state` + `vreg_rx_ok` -> `EN_EFF_pll_cdr` | 0 | 0 | exists |
| `pll_cdr.N4`, `N8` | `consolidation.pll.feedback_n` (`debug_cfg[98..99]`) per `MWX:67` | 0 | 0 (N = 16) | encoding OPEN |
| `pll_cdr.N5`, `N10` | none | asked: 0 | 0 | NO FIELD (2 bits) |
| `pll_cdr.KP[2:0]` | none | TBD | 0 = P path off (loop cannot track) | NO FIELD (`cdr.config.kp[2:0]`), per-die calibrated (CDR7-KP) |
| `pll_cdr.BAND` | none; tied `VDD` | asked: 1 | 1 | NO FIELD (`ring_c.band`) |
| `pll_vreg.BYP_CDR` | `pllvreg.config.rx_bypass` (`analog_cfg[578]`) | 1 | 1 | exists; cell not instanced |

### Dynamic signals and status

| Signal | Needed by | Today | Needed |
|---|---|---|---|
| `FUP`, `FDN` (FLL pulses) | `cdr.FUP/FDN` | no driver. `W/rtl/pt_wrx_cdr_loop.sv` is not instantiated and targets retired pins (`freq_hold`, `bb_up/dn`); macro only has level `cdr_freq_locked` (`MAC:50`) | FLL in the macro (or elsewhere, coordinator), two outputs to the pll island. Loop cannot acquire without it (A3) |
| `PSEL[2:0]`, `SLIPP`, `SLIPM` | `wrx_cap` (full rate: 480-786 Mb/s, USB HS, 100BASE-TX) | no driver, no port | phase picker in the macro; `cdr.config.psel_force` + `cfg_raw` for IX-12 |
| `LDE` | `wrx_cap.LDE` | no source | `wordclk_rx` on the RX ring (MW-11) with `D10/D20` rate bits |
| FU/FD force for KP calibration | CDR7-KP (`IC:1038`) | `FUk/FDk` are driven by the capture directly; no force path exists | **OPEN**: where the force is injected (mux in front of FU/FD, or a capture test mode) |
| `wrx_dw[19:0]`, `wrx_ew[19:0]`, `wrx_slp`, `wrx_slm`, `wrx_wstb` | macro | macro has `wire_rx_data[39:0]`, `wire_rx_clk` (r6 DX/WCLK40) | WSTB-domain register, second flop on EW (SLI7-M), 20->40 gear with toggle reset by `cap_en`/LDE, CDC, generated-clock STA. Hold at the macro flop < 0.75 ns (`IC:1043`) |
| `wire_rx_valid` | `rtl/pt_core.sv:87` gates ingress on it | no producer | produce in the new macro front end, or tie (D9, MW-12) |
| `wire_analog_status` (cdr_qualified, cdr_loss, rx_state, slicer_data/early/late, electrical_quiet, usb_squelch, detect_event) | `rtl/pt_digital.sv:41-46` | no producer | derive in the macro from votes / detect outputs, or tie (MW-12) |
| `det_diff_pos/neg`, `det_se_p/n` | USB FS/LS receive, SE0, squelch, disconnect | no macro input | macro inputs (`CT:22`) |
| `det_clk` | `detect.det_clk` | macro `ct_det_clk` exists; divider strapped 0 | bind; rate field |
| `EN_EFF_*` decodes | ctle, rxselect, slicer, detect, cdr, pll_cdr | macro `en_eff[]` (`MAC:161-186`) | none for termination, rxlevel, wmon_sel, vthdac, ptrim (uses `wire_rx_ptrim_en`), wrx_cap |

Safe-state rule (W6-SAFE `IC:983`, W7-SAFE `IC:1044`, SLI7-R `IC:1029`): `wrx_cap.EN` = 0 requires `slicer_en` = 0 and, with the wired RX off,
`ptrim_en` = 0. Hardware interlock asked in the macro; only the `ptrim_en` part exists (DT-9).

## 5. Open / not yet decided

| ID | Item | Owner |
|---|---|---|
| MW-36, D7 | `pt_cdr`: schematic r12 (32 pins, `otr0..4`, `otrs`) vs published layout (26 pins). Bind 26 until the layout is republished; cdr.spice is being edited. `cdr.spice:16` cites "CDR8-TRIM", which is not in interface-changes.md | wired RX |
| W7-GEAR `IC:1043` | `pt_wrx_cap` r7 publication in progress; q834 fails; macro WSTB front end does not exist. `generated/wrx_cap.*` and `pins.txt` were r6 at the time of writing | wired RX, digital, coordinator |
| W7-SAFE / W6-SAFE / DT-9 | Interlock: W7-SAFE wording (`slicer_en & cap_en`, `ptrim_en_reg & wrx_rx_en_reg`) vs DT-9 implementation (`ptrim_en` = slicer active); `cap_en` has no field | digital |
| SLI7-R `IC:1029` | Published slicer passes only 625 MHz at the pessimistic values; safe-off outputs 0.22 V with clocks running, hence the ptrim gate | wired RX, coordinator |
| SLI7-M `IC:1041` | E0..E3 re-time stage: in the capture or the macro (W7-GEAR puts a second EW flop in the macro) | capture, digital |
| MW-8 (A1) | HS pair unbound; CTLE on the USB pad net. Add `pad_hs_rx` family and `HS_RX_P/N`; split `WRX_P/N` | assembly |
| MW-9 (A2), PD27 | `hs_en`, `hs_term_en`, `hs_trim[3:0]`, `term_en` fields | digital |
| MW-10 (A3) | CDR control plane: FUP/FDN, pfd_mode, ref_sel, KP, N5/N10, B2/B1, PSEL, SLIP; where the FLL and phase picker live | digital, wired RX, coordinator |
| MW-11 (A4) | `wordclk_rx`: instance, CK tap (PH0 vs CKP0), supply island, D10/D20 source | timing, assembly |
| MW-12 (D9) | `wire_rx_valid` and wired status bits producer | digital, assembly |
| MW-13 (D2) | CTLE with its real load: -8 dB at 1.25 GHz. May change the CTLE/rxselect cells | wired RX |
| MW-14 (A5) | ptrim real load (CKP0 ~1.0 pF); ptrim layout not usable; possible CKP0 buffer split changes capture/ptrim pins | wired RX |
| MW-23 (D1, D3) | CTLE output CM 1.2-1.66 V vs slicer qualified at 1.0 V (header says 1.0, README 1.4); RX top rate statement | wired RX, coordinator |
| MW-31 (D5), INT1-8 | `pt_pll_vreg2` not instanced; `pll_cdr.VDD` on `RAIL_pll`; bypass policy; ATB leaves for ATB_OUT/ATB_G | assembly, pads, timing |
| D4 (`MWX:197`) | `cdr.IBIAS` source and `pll_cdr.IBIAS` source (`cdr.IB_PLL` vs `BIAS_pll_ring_rx`); stale `NL:122` bindings (`FBCK_IN`, `freq_hold`); `pll_cdr.REF/HOLD/ATB_VCTRL` | assembly, wired RX, bias |
| D6 | Slicer per-sampler trim fields (80 bits) and bit map; `vsel` (8 bits) | digital, wired RX |
| D8 | Decodes for termination, rxlevel, wmon_sel, ctle peak: owner | assembly or digital |
| CDR7-KP `IC:1038` | KP field, per-die calibration sequence, FU/FD force path | digital, wired RX |
| AC3-W (`IC:430`, `452`, `739`, `968`, `974`) | `cdr.g` reset value (2 vs 3 vs TBD); N4/N8 field encoding; `ring_c.band`; `ring_c.owner`; `cdr.REF_IN` from clockmux PREF; PH0 select to prescale | digital, timing, assembly |
| AC3-W6 `IC:449` | `cdr.phase_trim` reset 0 vs requested 16; field island pll vs cell on wired | digital |
| RING-ECO `IC:1047` | KP/FU/FD pins on the ring bottom edge; block 210 x 792.6 um: route `CDR_UP/DN` there | assembly |
| RING-ASYM `IC:1156` | r9w published; cold start from VCTRL = 0 and slow EN ramp not shown; no pin change | wired RX |
| R8-ARCH `IC:1054`, R8-PD8 `IC:1130` | Eighth-rate mode (proposed): would add slicer B, capture B, PD8 cell, 16-channel ptrim, RATE8 bit, +40 EW + WSTB_B into the macro. Not in the tables above | coordinator, wired RX |
| IX-10 / IX-11 / IX-12 / IX-13 | vthdac + vsel fields, fast threshold update opcode, raw dual-lane (EW to the host, `psel_force`), `lf_zero` field | digital |
| D10 | No signal detect on the HS pair (detect cannot take it) | wired RX, digital |
| crossings | Clamp on `CDR_UP/DN` when the wired island is off; iso cells on wired -> core outputs; `RXPH` swing at corners | assembly |
| minor | `slicer.QCK`, `ctle.atb_ctle_src`, `pll_cdr.LOCK`, `pll_cdr.REFO`, `detect.det_inject` mapping, `det_clk` rate, `WIRE_RX` P/N-to-bond order, external-clock fallback (CKP0..3 = CK, CKP4..7 = !CK, `W/README.md:137`) has no mux | assembly, wired RX |
