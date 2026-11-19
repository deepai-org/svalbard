# Two-chip split, phase 0: assignment and cross-mode audit

Read-only audit for `SPLIT-PLAN.md` phase 0 (2026-11-19). Nothing in the tree was changed. Inputs: `integration/top/pt_chip.conn`
(parsed with `check_top.parse`), `masters.txt`, `decisions.md`, `spec/register-map.json`, `spec/contract.json` (`bond_map_current`),
`spec/performance-requirements.md`, `spec/interface-requirements.md`, `spec/risk-register.md`, `scratch/reviews/interface-changes.md`,
`mode-walk.md`, `integration/top/sim/tb_top_modes.sv` (what `verification/check_top_modes.py` runs), `rtl/`,
`scratch/reviews/die-fit/ledger.csv`, `scratch/digital-timing-close/macro-area.md`, `spec/power-delivery.md`. The light scripts that built the
tables are in the session scratchpad only (no simulation, DRC or hardening was run). Every area is a ledger number or arithmetic on ledger numbers.

Tags: **rf** = `pt_rf` only; **wired** = `pt_wired` only; **both** = instanced on both chips from the same source; **split** = one cell
whose parts go to different chips; **obsolete** = gone already or made pointless by the split.

## 0. Summary

- **Instance count.** `pt_chip.conn` expands to **238** instances today, not 241. The ledger (`ledger.csv`, conn commit 11b9f56) still holds
  `pad_agnd_rx_0`, `pad_agnd_rx_1` and `agnd_tie`, removed on 2026-11-18 (RQ-1). All 238 plus those 3 are in table 1.
  Result: 110 both, 63 rf, 64 wired, 1 split (`bias_ext`). 50 of the 79 ATB leaves are on both chips.
- **No connectivity crosses the halves except shared infrastructure.** Netlist check of the tagging: the only nets touching both an rf-only and a
  wired-only instance are the ATB local buses `ATB0_LOCAL0`, `ATB1_LOCAL0`, `ATB1_LOCAL3`, the rails `RAIL_pll`, `RAIL_debug` and `island_off[5]`.
  All of them are shared infrastructure that each chip keeps a subset of.
- **The biggest cross-mode dependency is the clock tree, not the ADC or the ATB.** The RF chip's host word clock and converter clock come from the
  TX ring (`pll_tx`) through `clockmux` / `prescale` / `prescale_conv` (host_follow baseline, D-HF, DG6-4). So the pll island (TX ring,
  `pll_vreg2`, clockmux, prescaler) has to be on **both** chips (about 0.33 mm2 on `pt_rf`, switch included). The CDR ring is the only second
  host_follow route on `pt_rf` (decision D2).
- **The AUX_CLK pair is used by both halves** (external-LO Q leg on `pt_rf`; forwarded wire clock on `pt_wired`): duplicate the pad and its receiver
  (0.195 mm2 per chip). That also removes the rule that excludes the external LO and the forwarded clock from each other on `pt_wired`.
- **No capability is lost.** No ADC or ATB path observes the other half. USB and 100BASE-TX touch no RF block. The WTX_EXT fallback is wired-only,
  which **dissolves OCP-2**: `pt_rf` has free sites for an off-chip LO loop-filter capacitor, and WTX_EXT keeps its own pads on `pt_wired`.
- **Signal pads:** `pt_rf` needs 45 of the 56 signal sites (11 free), `pt_wired` 47 (9 free). Both keep the 18 fixed supply/ground sites.
- **Registers:** 913 stored field bits: 213 both, 237 rf, 460 wired, 2 obsolete (`*.usb` island bits), 1 chip constant (`payload_iq`).
- **Digital macro estimate** (cells scaled by module from r8c/r8d, 78 % utilisation, width 1716): **`pt_rf` about 2.0 mm2 (1716 x ~1170 um),
  `pt_wired` about 2.6 mm2 (1716 x ~1510 um)**. The wired macro is **not** "well under 2.81" as the plan expects. The shared transport banks,
  host link and register file core stay in both.
- **Area with the full 5.4 nF decap plan on each chip** (section 7): `pt_rf` 9.3 mm2 demand as built, 10.3-10.8 with channels, corridors and scrap,
  so the margin is **2.0-2.5 mm2**. `pt_wired` 8.5 / 9.3-9.7, margin **3.1-3.5 mm2**. At targets the margins are 2.7-3.1 and 3.5-3.9. These are
  raw-area estimates, not packings: the `pt_rf` keep-away rules (QVCO, LNA, ADC) are checked only in phase 3.

## 1. Instances of `pt_chip.conn` (238 + 3 removed)

Island = group in the conn. As built = `ledger.csv` `asbuilt_um2` (KLayout bounding box or the ledger's estimate; 0 = provider ring
cell, no core area). A reason is given where the tag is not obvious from the island. ATB leaves are tagged by the node they reach. A leaf on
a core-bias trunk, the master bias, a rail, VSS/VDD or a characterization device is on both chips, with the same code on both.

Notes on "both" instances whose pins differ per chip (phase 1 binds these per chip; same master, no fork):
- `digital`: per-chip configuration (section 4). Inputs of the absent half are tied in the chip conn, and their macro clamps are not generated.
- `core_bias`: bank rails `RAIL_rf` / `RAIL_conv` (absent on `pt_wired`) and `RAIL_wired` (absent on `pt_rf`). The bank outputs of absent
  consumers have no load. The composite generator needs a per-chip bank list (a parameter, not a copy). Otherwise the absent banks sit on a
  rail that does not exist on that chip (decision D8).
- `bias_ext` is two `pt_bias_tap2` cells: the qvco / lo_pfdcp tap goes to `pt_rf`, the hsbias tap to `pt_wired`.
- `clockmux`: `pt_rf` ties `WSI` (CDR phase) and `HF` (if D2 is "no"). `pt_wired` ties `CONV_INT`. `CONV_CLK` is unloaded on `pt_wired`.
- `pll_vreg2`: `VOUT_CDR` is unloaded on `pt_rf` (if D2 is "no").
- `clk_obs`: absent sources are tied to VSS, as `IN0` / `IN7` are today. On `pt_rf` that is IN3 wsmp, IN14 cdr and IN15A-C char. On `pt_wired`
  it is IN1 LO and IN4 rf_rx_clk. Note: today IN13 = `host_word_clk` and IN9 = `fc_src[0]` (TX ring) on both.
- `atb0_leaf22` (TRK_WIRE): its select is `WTX_FORCE_SELECTED` from the wired fallback cell. `core_bias` still has `TRK_WIRE` on `pt_rf`. There the
  leaf (if kept) takes `atb0_sw[21]` directly.
- `rx_aux_clk` / `pad_aux_clk`: on `pt_rf`, `cdr.WCK_IN` is absent (D2 "no"), and clockmux `AUX` (and `WCK` when tied) remain.

| # | instance | master | island | chip | as built um2 | reason / note |
|---:|---|---|---|---|---:|---|
| 1 | `host` | `pt_host_physical` | chip | **both** | 0 |  |
| 2 | `debug_pads` | `pt_debug_physical` | chip | **both** | 0 |  |
| 3 | `pad_por_bypass` | `pad_strap` | chip | **both** | 0 |  |
| 4 | `digital` | `pt_digital_macro` | chip | **both** | see section 4 | two configurations of one RTL (section 4) |
| 5 | `por` | `por` | core | **both** | 9469 |  |
| 6 | `aosc` | `pt_aosc` | core | **both** | 12864 |  |
| 7 | `core_bias` | `pt_core_bias` | core | **both** | 301799 |  |
| 8 | `bias_ext` | `pt_bias_ext` | core | **split** | 4173 | two pt_bias_tap2 cells: qvco/lo_pfdcp tap -> rf, hsbias tap -> wired |
| 9 | `isw_wired_rx` | `isw_debug` | core | **wired** | 36922 |  |
| 10 | `isw_rf_tx` | `isw_debug` | core | **rf** | 36922 |  |
| 11 | `isw_debug` | `isw_debug` | core | **both** | 36922 |  |
| 12 | `isw_wired_tx` | `isw_debug` | core | **wired** | 36922 |  |
| 13 | `isw_wired_cap` | `isw_wired` | core | **wired** | 64081 |  |
| 14 | `isw_lod` | `isw_wired` | core | **rf** | 64081 |  |
| 15 | `isw_rf_rx` | `isw_rf` | core | **rf** | 49817 |  |
| 16 | `isw_conv` | `isw_conv` | core | **rf** | 31781 |  |
| 17 | `isw_lo` | `isw_conv` | core | **rf** | 31781 |  |
| 18 | `isw_pll` | `isw_debug` | core | **both** | 36922 |  |
| 19 | `pad_dvdd_0` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 20 | `pad_dvdd_1` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 21 | `pad_dvdd_2` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 22 | `pad_dvdd_3` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 23 | `pad_dvdd_4` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 24 | `pad_dvdd_5` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 25 | `pad_vdd_0` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 26 | `pad_vdd_1` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 27 | `pad_dvss_0` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 28 | `pad_dvss_1` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 29 | `pad_dvss_2` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 30 | `pad_dvss_3` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 31 | `pad_dvss_4` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 32 | `pad_dvss_5` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 33 | `pad_dvss_6` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 34 | `pad_dvss_7` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 35 | `pad_vss_0` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 36 | `pad_vss_1` | `prov_supply` | chip | **both** | 0 | provider supply site (fixed) |
| 37 | `pad_rf_rx` | `pad_rf_pair` | rf_rx | **rf** | 146890 |  |
| 38 | `pad_rf_tx` | `pad_rftxpad` | rf_tx | **rf** | 146890 |  |
| 39 | `pad_bb_i` | `pad_rf_pair` | debug | **rf** | 146890 | baseband observe/inject pads and taps (debug island, RF chain only) |
| 40 | `pad_bb_q` | `pad_rf_pair` | debug | **rf** | 146890 | baseband observe/inject pads and taps (debug island, RF chain only) |
| 41 | `pad_wtx_ext` | `pad_rf_pair` | debug | **wired** | 146890 | WTX_EXT fallback (external serial data into the TX output stage) |
| 42 | `pad_wmon` | `pad_single_leg` | debug | **wired** | 140099 | WMON: wired RX node monitor; buffer is the rf_rx-owned pt_bb_tap master, instanced on pt_wired only |
| 43 | `pad_tlp` | `pad_tlp` | core | **wired** | 0 | TLP/ESD test site: one copy suffices (generic pad_tlp_flat); spare rf sites go to ground bonds (decision D5) |
| 44 | `pad_ref` | `pad_refpad` | pll | **both** | 171506 | reference input; on pt_rf REF_IN is also the external-LO I leg |
| 45 | `pad_aux_clk` | `pad_refpad` | pll | **both** | 171506 | pt_rf: external-LO Q leg + aux clock / external converter clock; pt_wired: forwarded wire clock + aux clock |
| 46 | `refvcm` | `pt_refvcm` | pll | **both** | 7192 | reference input; on pt_rf REF_IN is also the external-LO I leg |
| 47 | `pad_hs_rx` | `pad_hspad` | wired_rx | **wired** | 209492 |  |
| 48 | `pad_usb` | `pad_wirepad` | wired_tx | **wired** | 341926 |  |
| 49 | `pad_wire_tx` | `pad_txpad` | wired_tx | **wired** | 268476 |  |
| 50 | `lna` | `pt_lna` | rf_rx | **rf** | 42921 |  |
| 51 | `lna_ind_p` | `pt_lna_ind` | rf_rx | **rf** | 69160 |  |
| 52 | `lna_ind_n` | `pt_lna_ind` | rf_rx | **rf** | 69160 |  |
| 53 | `lna_deg_p` | `pt_lna_deg` | rf_rx | **rf** | 25200 | E (generator only) |
| 54 | `lna_deg_n` | `pt_lna_deg` | rf_rx | **rf** | 25200 | E (generator only) |
| 55 | `rxmix_i` | `pt_rxmix_i` | rf_rx | **rf** | 35442 |  |
| 56 | `rxmix_q` | `pt_rxmix_q` | rf_rx | **rf** | 35442 |  |
| 57 | `bbfilter_i` | `pt_bbfilter_i` | rf_rx | **rf** | 341901 |  |
| 58 | `bbfilter_q` | `pt_bbfilter_q` | rf_rx | **rf** | 341901 |  |
| 59 | `bb_tap_i` | `pt_bb_tap` | debug | **rf** | 19511 | baseband observe/inject pads and taps (debug island, RF chain only) |
| 60 | `bb_tap_q` | `pt_bb_tap` | debug | **rf** | 19511 | baseband observe/inject pads and taps (debug island, RF chain only) |
| 61 | `bb_tap_wmon` | `pt_bb_tap` | debug | **wired** | 19511 | WMON: wired RX node monitor; buffer is the rf_rx-owned pt_bb_tap master, instanced on pt_wired only |
| 62 | `iso_wmon` | `iso_pd` | debug | **wired** | 95 | WMON: wired RX node monitor; buffer is the rf_rx-owned pt_bb_tap master, instanced on pt_wired only |
| 63 | `adc_i` | `pt_adc_i` | conv | **rf** | 449686 |  |
| 64 | `adc_q` | `pt_adc_q` | conv | **rf** | 449686 |  |
| 65 | `iso_conv_clk` | `iso_clamp_x4` | conv | **rf** | 1025 |  |
| 66 | `dac_i` | `pt_dac_i` | conv | **rf** | 134121 |  |
| 67 | `dac_q` | `pt_dac_q` | conv | **rf** | 134121 |  |
| 68 | `refbuf` | `pt_refbuf` | conv | **rf** | 117089 |  |
| 69 | `iso_rf_rx_clk` | `iso_clamp_x4` | core | **rf** | 1025 |  |
| 70 | `txmix_i` | `pt_txmix_i` | rf_tx | **rf** | 21424 |  |
| 71 | `txmix_q` | `pt_txmix_q` | rf_tx | **rf** | 21424 |  |
| 72 | `txsum` | `pt_txsum` | rf_tx | **rf** | 3988 |  |
| 73 | `rfdriver` | `pt_rfdriver` | rf_tx | **rf** | 96812 |  |
| 74 | `lo_ext` | `pt_lo_ext` | lod | **rf** | 133006 |  |
| 75 | `lo_vreg` | `pt_lo_vreg` | lo | **rf** | 440652 |  |
| 76 | `qvco` | `pt_lc_qvco5` | lo | **rf** | 532476 |  |
| 77 | `lo_mmd` | `pt_lo_mmd` | lod | **rf** | 145031 |  |
| 78 | `lo_mmd_qdum` | `pt_lo_mmd_qdum` | lod | **rf** | 19124 |  |
| 79 | `lo_pfdcp` | `pt_lo_pfdcp` | lo | **rf** | 124110 |  |
| 80 | `lo_lf` | `pt_lo_lf` | lo | **rf** | 194122 |  |
| 81 | `lo_obs` | `pt_lo_obs` | lod | **rf** | 9022 |  |
| 82 | `lo_obs_q` | `pt_lo_obs` | lod | **rf** | 9022 |  |
| 83 | `rx_ref_in` | `pt_diff_clk_rx` | core | **both** | 22341 | reference input; on pt_rf REF_IN is also the external-LO I leg |
| 84 | `clockmux` | `pt_clockmux` | pll | **both** | 15160 | host word clock and (pt_rf) converter clock come from the TX ring via clockmux/prescale (host_follow baseline, D-HF) |
| 85 | `iso_host_clk` | `iso_clamp_x4` | core | **both** | 1025 | host word clock and (pt_rf) converter clock come from the TX ring via clockmux/prescale (host_follow baseline, D-HF) |
| 86 | `prescale` | `pt_prescale` | pll | **both** | 12600 | host word clock and (pt_rf) converter clock come from the TX ring via clockmux/prescale (host_follow baseline, D-HF) |
| 87 | `prescale_conv` | `pt_prescale` | pll | **rf** | 12600 | only consumer is CONV_CLK (converters) |
| 88 | `prescale_hf` | `pt_prescale` | pll | **wired** | 12600 | CDR ring; on pt_rf it is only the second host_follow route (HF): decision D2 |
| 89 | `pll_vreg2` | `pt_pll_vreg2` | pll | **both** | 173424 | host word clock and (pt_rf) converter clock come from the TX ring via clockmux/prescale (host_follow baseline, D-HF) |
| 90 | `pll_tx` | `pt_pll_ring_core` | pll | **both** | 86020 | host word clock and (pt_rf) converter clock come from the TX ring via clockmux/prescale (host_follow baseline, D-HF) |
| 91 | `iso_pll_tx_fbck` | `iso_clamp_x4` | core | **both** | 1025 | host word clock and (pt_rf) converter clock come from the TX ring via clockmux/prescale (host_follow baseline, D-HF) |
| 92 | `pll_cdr` | `pt_pll_ring` | pll | **wired** | 166657 | CDR ring; on pt_rf it is only the second host_follow route (HF): decision D2 |
| 93 | `cdr` | `pt_cdr` | pll | **wired** | 82901 | CDR ring; on pt_rf it is only the second host_follow route (HF): decision D2 |
| 94 | `iso_cdr_up_0` | `iso_clamp` | pll | **wired** | 906 |  |
| 95 | `iso_cdr_up_1` | `iso_clamp` | pll | **wired** | 906 |  |
| 96 | `iso_cdr_up_2` | `iso_clamp` | pll | **wired** | 906 |  |
| 97 | `iso_cdr_up_3` | `iso_clamp` | pll | **wired** | 906 |  |
| 98 | `iso_cdr_dn_0` | `iso_clamp` | pll | **wired** | 906 |  |
| 99 | `iso_cdr_dn_1` | `iso_clamp` | pll | **wired** | 906 |  |
| 100 | `iso_cdr_dn_2` | `iso_clamp` | pll | **wired** | 906 |  |
| 101 | `iso_cdr_dn_3` | `iso_clamp` | pll | **wired** | 906 |  |
| 102 | `rx_aux_clk` | `pt_diff_clk_rx` | debug | **both** | 22341 | pt_rf: external-LO Q leg + aux clock / external converter clock; pt_wired: forwarded wire clock + aux clock |
| 103 | `rx_wtx_ext` | `pt_diff_clk_rx` | debug | **wired** | 22341 | WTX_EXT fallback (external serial data into the TX output stage) |
| 104 | `iso_aux_ck` | `iso_clamp_x4` | pll | **both** | 1025 | pt_rf: external-LO Q leg + aux clock / external converter clock; pt_wired: forwarded wire clock + aux clock |
| 105 | `iso_wtx_dx` | `iso_clamp` | wired_tx | **wired** | 906 | WTX_EXT fallback (external serial data into the TX output stage) |
| 106 | `ring_osc` | `pt_ring_osc` | debug | **both** | 9522 | process-speed monitor: every die needs speed readout for per-chip supply trim (MANDATE 2) |
| 107 | `vco_replica` | `pt_vco_replica` | debug | **both** | 20941 | replica of the ring VCO; the TX ring is on both chips (decision D6: wired-only saves 0.021) |
| 108 | `obs_pre4_wire` | `pt_obs_pre4` | debug | **both** | 3667 | CLK_OBS prescalers for sources present on both chips (WIRE_CK = ring/prescaler input) |
| 109 | `obs_pre4_wsmp` | `pt_obs_pre4` | debug | **wired** | 3667 | wire sample clock / CDR ring |
| 110 | `obs_pre4_ref` | `pt_obs_pre4` | debug | **both** | 3667 | CLK_OBS prescalers for sources present on both chips (WIRE_CK = ring/prescaler input) |
| 111 | `obs_pre4_aux` | `pt_obs_pre4` | debug | **both** | 3667 | CLK_OBS prescalers for sources present on both chips (WIRE_CK = ring/prescaler input) |
| 112 | `obs_pre4_pll` | `pt_obs_pre4` | debug | **both** | 3667 | CLK_OBS prescalers for sources present on both chips (WIRE_CK = ring/prescaler input) |
| 113 | `obs_pre4_cdr` | `pt_obs_pre4` | debug | **wired** | 3667 | wire sample clock / CDR ring |
| 114 | `iso_lo_obs` | `iso_clamp_x4` | debug | **rf** | 1025 |  |
| 115 | `clk_obs` | `pt_clk_obs16` | debug | **both** | 52854 |  |
| 116 | `pd_clk_obs` | `iso_pd` | core | **both** | 95 |  |
| 117 | `iso_clk_obs` | `iso_clamp_x4` | core | **both** | 1025 |  |
| 118 | `termination` | `pt_termination` | wired_rx | **wired** | 48249 |  |
| 119 | `rxlevel` | `pt_rxlevel` | wired_rx | **wired** | 13180 |  |
| 120 | `ctle` | `pt_ctle` | wired_rx | **wired** | 68676 |  |
| 121 | `rxselect` | `pt_rxselect` | wired_rx | **wired** | 8841 |  |
| 122 | `wmon_sel` | `pt_wmon_sel` | wired_rx | **wired** | 9835 |  |
| 123 | `detect` | `pt_detect` | wired_rx | **wired** | 173480 |  |
| 124 | `wordclk_rx` | `pt_wordclk` | wired_cap | **wired** | 24822 |  |
| 125 | `vthdac` | `pt_vthdac` | wired_rx | **wired** | 23891 |  |
| 126 | `ptrim` | `pt_ptrim` | wired_cap | **wired** | 45000 |  |
| 127 | `slicer` | `pt_slicer` | wired_rx | **wired** | 109899 |  |
| 128 | `wrx_cap` | `pt_wrx_cap` | wired_cap | **wired** | 293813 |  |
| 129 | `wiredtx` | `pt_wiredtx` | wired_tx | **wired** | 82717 |  |
| 130 | `steer_0` | `tx_steer` | wired_tx | **wired** | 0 |  |
| 131 | `steer_1` | `tx_steer` | wired_tx | **wired** | 0 |  |
| 132 | `steer_2` | `tx_steer` | wired_tx | **wired** | 0 |  |
| 133 | `steer_3` | `tx_steer` | wired_tx | **wired** | 0 |  |
| 134 | `steer_4` | `tx_steer` | wired_tx | **wired** | 8677 |  |
| 135 | `steer_5` | `tx_steer` | wired_tx | **wired** | 8677 |  |
| 136 | `attached_tx_interlock` | `tx_interlock` | wired_tx | **wired** | 48100 |  |
| 137 | `term_buffer` | `term_buffer` | wired_tx | **wired** | 75196 |  |
| 138 | `txpad_bias` | `pt_txpad_bias` | wired_tx | **wired** | 9936 |  |
| 139 | `usb_txdrv` | `pt_usb_txdrv` | wired_tx | **wired** | 30481 |  |
| 140 | `hsbias` | `pt_wtx_hsbias` | wired_tx | **wired** | 9137 |  |
| 141 | `wtx_fallback_control` | `pt_wtx_fallback_control` | wired_tx | **wired** | 5861 |  |
| 142 | `char_atb` | `pt_char_atb` | core | **both** | 28239 | device replicas of both halves (LNA/mixer and sampler/driver) + matching R/MIM; ATB codes 43-54 (decision D6) |
| 143 | `char_ro33` | `pt_char_ro33` | debug | **wired** | 9698 | speed test structures (plan); ring_osc stays on both for supply trim |
| 144 | `char_ro50` | `pt_char_ro50` | debug | **wired** | 9330 | speed test structures (plan); ring_osc stays on both for supply trim |
| 145 | `char_cmldiv` | `pt_char_cmldiv` | debug | **wired** | 27841 | speed test structures (plan); ring_osc stays on both for supply trim |
| 146 | `char_rffet` | `pt_char_rffet` | core | **rf** | 67600 | RF FET with GSG probe frames |
| 147 | `char_rffet_open` | `pt_char_rffet_open` | core | **rf** | 67600 | RF FET with GSG probe frames |
| 148 | `char_rffet_short` | `pt_char_rffet_short` | core | **rf** | 67600 | RF FET with GSG probe frames |
| 149 | `atb0_leaf1` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 1: node `ATBN_master_ibias` |
| 150 | `atb0_leaf14` | `atb_leaf_f` | core | **rf** | 1086 | ATB0 code 14: node `ATBN_rf_ibias` |
| 151 | `atb0_leaf22` | `atb_leaf_f` | core | **wired** | 1086 | ATB0 code 22: node `ATBN_wire_ibias` |
| 152 | `atb0_leaf29` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 29: node `ATBN_pll_ibias` |
| 153 | `atb0_leaf35` | `atb_leaf_f` | core | **rf** | 1086 | ATB0 code 35: node `ATBN_conv_ibias` |
| 154 | `atb0_leaf36` | `atb_leaf_f` | core | **rf** | 1086 | ATB0 code 36: node `VREF_CONV` |
| 155 | `atb0_leaf55` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 55: node `ATBN_vbg` |
| 156 | `atb0_leaf56` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 56: node `ATBN_debug_ibias` |
| 157 | `atb0_leaf58` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 58: node `VCO_REPLICA_VCTRL` |
| 158 | `atb0_grp0` | `atb_grp` | core | **both** | 6145 |  |
| 159 | `atb0_leaf43` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 43: node `CHAR_RN_LNA` |
| 160 | `atb0_leaf44` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 44: node `CHAR_RP_LNA` |
| 161 | `atb0_leaf45` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 45: node `CHAR_RN_MIX` |
| 162 | `atb0_leaf46` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 46: node `CHAR_RP_MIX` |
| 163 | `atb0_leaf47` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 47: node `CHAR_RN_SMP` |
| 164 | `atb0_leaf48` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 48: node `CHAR_RP_SMP` |
| 165 | `atb0_leaf49` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 49: node `CHAR_RN_DRV` |
| 166 | `atb0_leaf50` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 50: node `CHAR_RP_DRV` |
| 167 | `atb0_leaf51` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 51: node `CHAR_RES_A` |
| 168 | `atb0_leaf52` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 52: node `CHAR_RES_B` |
| 169 | `atb0_leaf53` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 53: node `CHAR_MIM_A` |
| 170 | `atb0_leaf54` | `atb_leaf_f` | core | **both** | 1086 | ATB0 code 54: node `CHAR_MIM_B` |
| 171 | `atb0_grp1` | `atb_grp` | core | **both** | 6145 |  |
| 172 | `atb0_pad` | `atb_pad` | core | **both** | 6626 |  |
| 173 | `atb0_io` | `atb_provider_pad` | chip | **both** | 0 |  |
| 174 | `atb1_leaf1` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 1: node `ATBN_master_ibias` |
| 175 | `atb1_leaf2` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 2: node `VREF0_MASTER` |
| 176 | `atb1_leaf3` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 3: node `VCM_MASTER` |
| 177 | `atb1_leaf4` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 4: node `VSS` |
| 178 | `atb1_leaf5` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 5: node `VDD` |
| 179 | `atb1_leaf6` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 6: node `VDD` |
| 180 | `atb1_leaf7` | `atb_leaf_s` | core | **wired** | 827 | ATB1 code 7: node `RAIL_wired_rx` |
| 181 | `atb1_leaf8` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 8: node `RAIL_rf_rx` |
| 182 | `atb1_leaf9` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 9: node `RAIL_pll` |
| 183 | `atb1_leaf11` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 11: node `RAIL_conv` |
| 184 | `atb1_leaf12` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 12: node `RAIL_debug` |
| 185 | `atb1_leaf13` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 13: node `VSS` |
| 186 | `atb1_grp0` | `atb_grp` | core | **both** | 6145 |  |
| 187 | `atb1_leaf14` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 14: node `ATBN_rf_ibias` |
| 188 | `atb1_leaf15` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 15: node `ATBN_rf_vcm` |
| 189 | `atb1_leaf16` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 16: node `ATBN_lna_bias` |
| 190 | `atb1_leaf17` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 17: node `ATBN_rxmix_bias` |
| 191 | `atb1_leaf18` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 18: node `ATBN_pga_bias` |
| 192 | `atb1_leaf19` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 19: node `ATBN_bbfilter_bias` |
| 193 | `atb1_leaf20` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 20: node `ATBN_txmix_bias` |
| 194 | `atb1_leaf21` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 21: node `ATBN_rfdriver_bias` |
| 195 | `atb1_leaf33` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 33: node `ATBN_quadrature_bias` |
| 196 | `atb1_leaf43` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 43: node `CHAR_RN_LNA` |
| 197 | `atb1_leaf44` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 44: node `CHAR_RP_LNA` |
| 198 | `atb1_grp1` | `atb_grp` | core | **both** | 6145 |  |
| 199 | `atb1_leaf10` | `atb_leaf_s` | core | **wired** | 827 | ATB1 code 10: node `RAIL_wired_tx` |
| 200 | `atb1_leaf22` | `atb_leaf_s` | core | **wired** | 827 | ATB1 code 22: node `ATBN_wire_ibias` |
| 201 | `atb1_leaf23` | `atb_leaf_s` | core | **wired** | 827 | ATB1 code 23: node `HS_VBIAS` |
| 202 | `atb1_leaf24` | `atb_leaf_s` | core | **wired** | 827 | ATB1 code 24: node `ATBN_ctle_bias` |
| 203 | `atb1_leaf25` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 25: node `VSS` |
| 204 | `atb1_leaf26` | `atb_leaf_s` | core | **wired** | 827 | ATB1 code 26: node `ATBN_wiredtx_bias` |
| 205 | `atb1_leaf27` | `atb_leaf_s` | core | **wired** | 827 | ATB1 code 27: node `TERM_VCM` |
| 206 | `atb1_leaf28` | `atb_leaf_s` | core | **wired** | 827 | ATB1 code 28: node `ATBN_detect_vref` |
| 207 | `atb1_leaf40` | `atb_leaf_s` | core | **wired** | 827 | ATB1 code 40: node `BIAS_hsbias` |
| 208 | `atb1_leaf41` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 41: node `VSS` |
| 209 | `atb1_leaf58` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 58: node `VCO_REPLICA_VCTRL` |
| 210 | `atb1_grp2` | `atb_grp` | core | **both** | 6145 |  |
| 211 | `atb1_leaf29` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 29: node `ATBN_pll_ibias` |
| 212 | `atb1_leaf30` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 30: node `ATBN_pll_vctrl` |
| 213 | `atb1_leaf31` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 31: node `BIAS_pll_ring_tx` |
| 214 | `atb1_leaf32` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 32: node `REF_VCM` |
| 215 | `atb1_leaf34` | `atb_leaf_s` | core | **wired** | 827 | ATB1 code 34: node `ATBN_cdr_bias` |
| 216 | `atb1_leaf35` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 35: node `ATBN_conv_ibias` |
| 217 | `atb1_leaf36` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 36: node `VREF_CONV` |
| 218 | `atb1_leaf37` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 37: node `VCM_MASTER` |
| 219 | `atb1_leaf38` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 38: node `ATBN_adc_bias` |
| 220 | `atb1_leaf39` | `atb_leaf_s` | core | **rf** | 827 | ATB1 code 39: node `ATBN_dac_bias` |
| 221 | `atb1_leaf47` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 47: node `CHAR_RN_SMP` |
| 222 | `atb1_leaf48` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 48: node `CHAR_RP_SMP` |
| 223 | `atb1_grp3` | `atb_grp` | core | **both** | 6145 |  |
| 224 | `atb1_leaf42` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 42: node `ATBN_debug_buffer_bias` |
| 225 | `atb1_leaf45` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 45: node `CHAR_RN_MIX` |
| 226 | `atb1_leaf46` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 46: node `CHAR_RP_MIX` |
| 227 | `atb1_leaf49` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 49: node `CHAR_RN_DRV` |
| 228 | `atb1_leaf50` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 50: node `CHAR_RP_DRV` |
| 229 | `atb1_leaf51` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 51: node `CHAR_RES_A` |
| 230 | `atb1_leaf52` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 52: node `CHAR_RES_B` |
| 231 | `atb1_leaf53` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 53: node `CHAR_MIM_A` |
| 232 | `atb1_leaf54` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 54: node `CHAR_MIM_B` |
| 233 | `atb1_leaf55` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 55: node `ATBN_vbg` |
| 234 | `atb1_leaf56` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 56: node `ATBN_debug_ibias` |
| 235 | `atb1_leaf57` | `atb_leaf_s` | core | **both** | 827 | ATB1 code 57: node `ATBN_idac1` |
| 236 | `atb1_grp4` | `atb_grp` | core | **both** | 6145 |  |
| 237 | `atb1_pad` | `atb_pad` | core | **both** | 6626 |  |
| 238 | `atb1_io` | `atb_provider_pad` | chip | **both** | 0 |  |
| 239 | `pad_agnd_rx_0` | `pad_downbond` | rf_rx | **obsolete** | 0 | removed from pt_chip.conn on 2026-11-18 (RQ-1); still in ledger.csv |
| 240 | `pad_agnd_rx_1` | `pad_downbond` | rf_rx | **obsolete** | 0 | removed from pt_chip.conn on 2026-11-18 (RQ-1); still in ledger.csv |
| 241 | `agnd_tie` | `pt_agnd_tie` | core | **obsolete** | 2000 | removed from pt_chip.conn on 2026-11-18 (RQ-1); still in ledger.csv |

## 2. Pads and bond functions

Source: `spec/contract.json` `assembly_policy.bond_map_current` (west, east, north) and `candidate_signal_sites` (south / host rows, stated
there as unchanged). 74 sites = 18 provider supply/ground sites (8 VDD/DVDD, 10 VSS/DVSS, fixed: `preserve_provider_power_ground_assignments`)
+ 56 signal sites. Today 55 signal sites are used and `bidir[17]` is a bonded spare.

| function | pads | current site(s) | chip | note |
|---|---:|---|---|---|
| RESET_N | 1 | `rst_n_pad` (south) | both | |
| SPI SCLK / CS_N / MOSI / MISO | 4 | `bidir[10..13]` (south) | both | |
| D2H data + clock | 11 | `clk_pad`, `bidir[0..9]` (south) | both | D2H strip booked on both |
| H2D data + clock | 11 | `bidir[26..36]` (north) | both | |
| POR_BYPASS strap | 1 | `bidir[16]` (east) | both | provider `in_c`, pull-down |
| ATB0, ATB1 | 2 | `analog[0]`, `analog[1]` (north) | both | |
| CLK_OBS, DBG_OBS0, DBG_OBS1 | 3 | `bidir[37..39]` (north) | both | |
| REF_IN_P/N (`pad_ref`) | 2 | `inputs[3]` / `[2]` (west) | both | `pt_rf`: also the external-LO I leg |
| AUX_CLK_P/N (`pad_aux_clk`) | 2 | `inputs[5]` / `[4]` (west) | both | `pt_rf`: external-LO Q leg, aux / external converter clock. `pt_wired`: forwarded wire clock (CP4-3), aux clock |
| RF_RX_P/N (`pad_rf_rx`) | 2 | `inputs[9]` / `[8]` | rf | |
| RF_TX_P/N (`pad_rf_tx`) | 2 | `inputs[1]` / `[0]` | rf | |
| BB_I_P/N, BB_Q_P/N (`pad_bb_i/q`) | 4 | `inputs[11]`, `[10]`, `[7]`, `[6]` | rf | baseband observe / inject |
| WIRE_RX_P/N (`pad_hs_rx`) | 2 | `bidir[15]` / `[14]` (east) | wired | |
| USB_DP/DN (`pad_usb`) | 2 | `bidir[19]` / `[18]` | wired | |
| WIRE_TX_P/N (`pad_wire_tx`) | 2 | `bidir[21]` / `[20]` | wired | |
| WTX_EXT_P/N (`pad_wtx_ext`) | 2 | `bidir[22]` / `[23]` | wired | fallback external serial data |
| WMON (`pad_wmon`) | 1 | `bidir[24]` | wired | |
| TLP_TEST (`pad_tlp`, `pad_tlp_flat`) | 1 | `bidir[25]` | wired | one TLP site suffices; decision D5 |
| spare | 1 | `bidir[17]` | — | |
| provider VDD/DVDD, VSS/DVSS | 18 | fixed | both | |

**Signal pads per chip** (common 37 = 1 + 4 + 11 + 11 + 1 + 2 + 3 + 2 + 2):

| | common | own | signal pads | free signal sites of 56 | intended use of the free sites (plan) |
|---|---:|---:|---:|---:|---|
| `pt_rf` | 37 | 8 (RF_RX, RF_TX, BB_I, BB_Q) | **45** | **11** | LNA / RF ground bonds, QVCO and LO supply. Optional: 2 for an off-chip LO loop-filter capacitor with Kelvin return (OCP-1). |
| `pt_wired` | 37 | 10 (WIRE_RX, WIRE_TX, USB, WTX_EXT, WMON, TLP) | **47** | **9** | ground / supply bonds for the HS drivers (wired TX, USB) |

Caveat (not re-derived here): a supply or ground bond on a signal finger has no COB 1 µF capacitor (8.1-8.7 nH to the first capacitor
against 4.0-4.6 nH on a supply finger, `bond_map_current` `bidir[17]` note). So a freed signal site is a lower-quality supply or ground than a
provider site. For an RF ground return it is still a short bond to the board ground plane. PKG-11 (COB tester diode check on every signal pad) applies
to these sites too.

## 3. Register fields

Source: `spec/register-map.json` (277 fields, 913 stored bits). The table gives one row per field group (`a.b`) where all its fields have the
same tag, and one row per field otherwise. Rules: the island list of the field, then the consumer cell in the conn. Groups of the RF chain,
converters and LO are rf. CDR, wired RX/TX, USB and the pattern generator/checker are wired. Bias core, islands, ATB, observation, monitor,
counters, host IO and the TX-ring (`ring_l`, `clockmux` ring reference and host prescaler) are both. If D2 = yes, `cdr.*`, `ring_c.*`,
`clockmux.config.hf_prescale` and `pllvreg.config.rx_bypass` are on `pt_rf` too.

**Stored bits by tag:** both 214, rf 237, wired 459, obsolete 2, chip constant 1. With fields of the absent half not stored, the stored state
of `pt_rf` is 451 bits (49 % of today) and of `pt_wired` 673 (74 %).

**Register-map recommendation (confirms SPLIT-PLAN):** one address map and one generator. A per-chip view marks the fields of the absent half
`absent`: they are not stored, read 0, and a write is accepted and ignored (so one host driver serves both chips). A new read-only `status.chip`
field holds the chip ID (`pt_rf` / `pt_wired`) and a per-chip map hash, so software can tell the chips apart before it writes anything. Rules whose
inputs are all absent on a chip drop out; rule 16 (`rf_wired_payload_exclusive`) is satisfied by construction on both. Rule 41
(`lo_pads_vs_forwarded_clock`) stays on `pt_rf` only.

| field / group | fields | bits | chip | note |
|---|---:|---:|---|---|
| `debug.island_power.wired` | 1 | 1 | wired | |
| `debug.island_power.rf` | 1 | 1 | rf | |
| `debug.island_power.pll` | 1 | 1 | both | |
| `debug.island_power.usb` | 1 | 1 | obsolete | no USB island since P2-8 (already a dead bit) |
| `debug.island_power.conv` | 1 | 1 | rf | |
| `debug.island_power.debug` | 1 | 1 | both | |
| `debug.pgood_override.wired` | 1 | 1 | wired | |
| `debug.pgood_override.rf` | 1 | 1 | rf | |
| `debug.pgood_override.pll` | 1 | 1 | both | |
| `debug.pgood_override.usb` | 1 | 1 | obsolete | as above |
| `debug.pgood_override.conv` | 1 | 1 | rf | |
| `debug.pgood_override.debug` | 1 | 1 | both | |
| `debug.clk_select.wire_line` | 1 | 3 | both | selects WIRE_CK = the TX ring into the prescalers: needed for the host clock on `pt_rf` too |
| `debug.clk_select.wire_sample` | 1 | 3 | wired | |
| `debug.clk_select.conv_sample` | 1 | 3 | rf | |
| `debug.clk_select.host_clk` | 1 | 3 | both | |
| `debug.bb_tap` | 1 | 3 | rf | |
| `debug.rf_rx_bypass` | 1 | 1 | rf | |
| `debug.rf_tx_bypass` | 1 | 1 | rf | |
| `debug.rf_bb_bypass` | 2 | 2 | rf | |
| `debug.wire_bypass` | 1 | 1 | wired | |
| `debug.wtx_ext` | 1 | 1 | wired | |
| `debug.wmon_select` | 1 | 3 | wired | |
| `debug.atb` | 2 | 12 | both | codes of absent leaves are dead per chip (section 5, X9) |
| `debug.bias_override` | 1 | 1 | rf | |
| `debug.clk_obs` | 2 | 8 | both | codes of absent sources select a VSS input |
| `debug.dbg_obs` | 2 | 12 | both | `obs_status` / `wire_status` codes of the absent half read 0 |
| `debug.replica.ringosc_enable` | 1 | 1 | both | |
| `debug.replica.vco_enable` | 1 | 1 | both | follows D6 |
| `debug.replica.ro33_enable` | 1 | 1 | wired | |
| `debug.replica.ro50_enable` | 1 | 1 | wired | |
| `debug.replica.cmldiv_enable` | 1 | 1 | wired | |
| `debug.host_link` | 2 | 4 | both | |
| `consolidation.bbfilter` | 3 | 4 | rf | |
| `consolidation.wiredtx_stage` | 2 | 3 | wired | |
| `consolidation.txmix` | 1 | 1 | rf | |
| `consolidation.detect` | 1 | 1 | wired | |
| `debug.pattern` | 8 | 21 | wired | |
| `rxmix.offset` | 2 | 12 | rf | |
| `core.biasgen` | 11 | 30 | both | |
| `core.refchain.bgap_ena` | 1 | 1 | both | |
| `core.refchain.bgap_trim` | 1 | 5 | both | |
| `core.refchain.dist_en_rf` | 1 | 1 | rf | |
| `core.refchain.dist_en_conv` | 1 | 1 | rf | |
| `core.refchain.dist_en_pll` | 1 | 1 | both | |
| `core.refchain.dist_en_wire` | 1 | 1 | wired | |
| `core.refchain.dist_en_debug` | 1 | 1 | both | |
| `debug.freq_count_a` | 5 | 26 | both | |
| `debug.freq_count_b` | 5 | 26 | both | source codes of absent sources read as stopped |
| `core.aosc` | 1 | 1 | both | |
| `debug.calibration` | 2 | 9 | both | |
| `adc_i.config` | 1 | 2 | rf | |
| `adc_i.state` | 1 | 2 | rf | |
| `adc_q.config` | 1 | 2 | rf | |
| `adc_q.state` | 1 | 2 | rf | |
| `cdr.config` | 2 | 32 | wired | |
| `cdr.state` | 1 | 2 | wired | |
| `clockmux.config.ring_ref` | 1 | 2 | both | |
| `clockmux.config.host_prescale` | 1 | 3 | both | |
| `clockmux.config.conv_prescale` | 1 | 3 | rf | |
| `clockmux.config.hf_prescale` | 1 | 3 | wired | rf too if D2 = yes |
| `ctle.config` | 2 | 6 | wired | |
| `ctle.state` | 1 | 2 | wired | |
| `dac_i.config` | 1 | 1 | rf | |
| `dac_i.state` | 1 | 2 | rf | |
| `dac_q.config` | 1 | 1 | rf | |
| `dac_q.state` | 1 | 2 | rf | |
| `detect.config` | 3 | 5 | wired | |
| `detect.state` | 1 | 2 | wired | |
| `digital.guard_config.gain_settle_ticks` | 1 | 9 | rf | |
| `digital.guard_config.rx_to_tx_ticks` | 1 | 9 | rf | |
| `digital.guard_config.tx_to_rx_ticks` | 1 | 9 | rf | |
| `digital.guard_config.wire_trim_settle_ui` | 1 | 8 | wired | |
| `digital.hop_config` | 2 | 27 | rf | |
| `digital.transport_config.payload_iq` | 1 | 1 | both (chip constant) | becomes a per-chip constant (1 on `pt_rf`, 0 on `pt_wired`); rule 16 `rf_wired_payload_exclusive` becomes vacuous |
| `digital.transport_config.direct_stream_enable` | 1 | 1 | wired | |
| `digital.transport_config.tx_interp` | 1 | 1 | rf | |
| `digital.transport_config.linecode` | 1 | 1 | wired | |
| `hostio.controls` | 4 | 5 | both | |
| `lna.state` | 1 | 2 | rf | |
| `monitor.config.require_reference` | 1 | 1 | both | |
| `monitor.config.require_input_clock` | 1 | 1 | both | |
| `monitor.config.require_rf_lock` | 1 | 1 | rf | |
| `monitor.config.require_wire_lock` | 1 | 1 | both | counter b lock; on `pt_rf` it can watch the TX (host_follow) ring |
| `monitor.config.required_supply_mask` | 1 | 6 | both | bits of absent groups must read 0 per chip |
| `monitor.config.loss_timeout_ticks` | 1 | 12 | both | |
| `monitor.config.timebase` | 1 | 1 | both | |
| `monitor.config.qualification_ticks` | 1 | 16 | both | |
| `monitor.reset` | 1 | 1 | both | |
| `refbuf.state` | 1 | 2 | rf | |
| `refinput.state` | 1 | 2 | both | |
| `rfdriver.gain` | 2 | 5 | rf | |
| `rfdriver.mute` | 1 | 1 | rf | |
| `rfdriver.state` | 1 | 2 | rf | |
| `rfpll.config` | 6 | 16 | rf | |
| `rfpll.state` | 1 | 2 | rf | |
| `rxlevel.config` | 1 | 2 | wired | |
| `rxmix_i.state` | 1 | 2 | rf | |
| `rxmix_q.state` | 1 | 2 | rf | |
| `rxselect.select` | 1 | 1 | wired | |
| `rxselect.state` | 1 | 2 | wired | |
| `slicer.offset` | 8 | 80 | wired | |
| `slicer.state` | 1 | 2 | wired | |
| `termination.config` | 5 | 9 | wired | |
| `txmix_i.state` | 1 | 2 | rf | |
| `txmix_q.state` | 1 | 2 | rf | |
| `txpad.config` | 2 | 3 | wired | |
| `txsum.state` | 1 | 2 | rf | |
| `usbdrive.select` | 1 | 2 | wired | |
| `usbdrive.state` | 1 | 2 | wired | |
| `usbfs.config` | 7 | 7 | wired | |
| `usbhs.bias` | 2 | 9 | wired | |
| `usbhs.config` | 5 | 15 | wired | |
| `wiredtx.config` | 3 | 17 | wired | |
| `wiredtx.idle` | 1 | 1 | wired | |
| `wiredtx.state` | 1 | 2 | wired | |
| `cdr.ac3` | 3 | 10 | wired | |
| `cdr.phase_trim` | 8 | 40 | wired | |
| `lna.match` | 5 | 12 | rf | |
| `pllvreg.config.tx_bypass` | 1 | 1 | both | |
| `pllvreg.config.rx_bypass` | 1 | 1 | wired | rf too if D2 = yes |
| `lna.bias` | 1 | 1 | rf | |
| `lna.agc` | 4 | 24 | rf | |
| `bbfilter_i.trim` | 4 | 25 | rf | |
| `bbfilter_q.trim` | 4 | 25 | rf | |
| `adc.config` | 2 | 3 | rf | |
| `ring_l.config` | 5 | 14 | both | |
| `ring_c.config` | 4 | 8 | wired | rf too if D2 = yes |
| `slicer.threshold` | 7 | 25 | wired | |
| `slicer.capture` | 3 | 5 | wired | |
| `usb.config` | 12 | 42 | wired | |
| `wrx.loop` | 10 | 38 | wired | |
| `wrx.picker` | 13 | 35 | wired | |

## 4. RTL modules and the two macro configurations

Cell area by module from `macro-area.md` (run r8c, after CTS and repair, inserted buffers charged to the driver; r8c carries 0.044 mm2 more
clock buffers than r8d). Module rows sum to 1.966 mm2. The remaining 0.201 mm2 (decode, isolation ANDs, `pt_adc_merge`, `pt_gain_rx`,
`pt_rf_out_reg`, `pt_vreg_seq`, `pt_det_clk`, ...) is not itemised in `macro-area.md` and is counted on both (pessimistic for both chips).

| RTL file (modules) | macro-area row(s), mm2 | chip | note |
|---|---|---|---|
| `pt_digital_macro.sv` | (top) | both | per-chip parameter `PT_CHIP` selects the ports, clamps and sub-blocks below |
| `pt_regfile.sv` (`pt_regfile`, `pt_mgmt`), `pt_ctl_decode.sv` | regs 0.339, control 0.049, debug_cfg_ra 0.029, analog_cfg_r 0.029, analog_cfg 0.011 | both (per-chip field set) | regfile and cfg ranks scaled by stored bits: 49 % rf, 74 % wired |
| `pt_spi.sv` | spi 0.045 | both | |
| `pt_host_link.sv`, `pt_quad_gearbox.sv` (gearboxes) | host.h2d 0.063, host.gearbox 0.016 | both | |
| `pt_core.sv` ingress / egress banks, `pt_fifo.sv` | ingress 0.259, egress 0.236, core 0.042 | both | shared storage, also capture/playback memory (sized by the wired 28 x 40 banks; shrinking them for `pt_rf` is an RTL change, not counted) |
| `pt_quad_link.sv`, `pt_dense_header.sv` | frame_rx 0.038, frame_tx 0.036, collect 0.017 | both | |
| `pt_por_path.sv` | por_path/rst 0.025 | both | |
| `pt_monitor.sv` | monitor 0.014 | both | |
| `pt_freq_count.sv` | fca 0.046, fcb 0.046 | both | counter b on `pt_rf` watches the TX ring while a watches the LO (could drop to one counter on `pt_rf`: -0.046) |
| `pt_cells.sv`, `pt_boundary.sv` `pt_iso_and` | (in remainder) | both | |
| `pt_vreg_seq.sv` | (remainder) | both | ring regulator sequencing: TX ring is on both |
| `pt_boundary.sv` `pt_adc_merge`; `pt_core.sv` `pt_gain_rx`; `pt_digital.sv` `pt_rf_out_reg` | (remainder) | rf | |
| `pt_quad_gearbox.sv` `pt_sample_pack` / `pt_sample_unpack` | packer 0.012, unpacker 0.013 | rf | |
| `pt_interp2x.sv` | interp.lane 0.013 | rf | |
| `pt_linecode.sv` | lc_tx 0.096, lc_rx 0.078 | wired | 8b/10b offload |
| `pt_wrx_ctl.sv`, `pt_boundary.sv` `pt_wrx_lane`, `pt_det_clk` | wrx 0.060 | wired | |
| `pt_wtx_ctl.sv`, `pt_tx_pad_sequence.sv` | wtx 0.011 | wired | |
| `pt_usb.sv` | usb 0.040 | wired | |
| `pt_pattern.sv` | prbs 0.011, prbs_check 0.035 | wired | the generator and checker sit on the wire clocks only |
| `pt_helpers.sv` (`pt_calibrator`) | 0 | — | not instantiated (removed, D11) |
| `pt_clocktree_slow.sv` | 0 | — | in `VERILOG_FILES` but not instantiated (DG6-6) |
| `pt_block_*.sv`, `pt_lane_compact*.sv`, `pt_schedule.vh` | 0 | — | standalone transport candidate with its own checks (`verification/check_block_*`); not in the macro |
| CLOCKTREE 0.176, TAP/ENDCAP 0.081 | | both | scaled with cell area |

**Estimate per chip** (same module areas; clock tree and tap cells scaled with logic area; outline = cells / 0.78 x 2.814/2.736 core-to-outline,
width 1716 um fixed by the host-link blocks). Check: the same arithmetic for today's macro gives 2.80 mm2 against the routed 2.814.

| configuration | logic mm2 | cells after CTS mm2 | outline mm2 at 78 % | outline (w x h um) | with levers (gated clocks, one read tree), 80 % |
|---|---:|---:|---:|---|---:|
| today (all) | 1.910 | 2.123 | 2.80 | 1716 x 1631 | — |
| `pt_rf` | 1.371 | 1.52 | **2.01** | 1716 x ~1170 | 1.70 |
| `pt_wired` | 1.765 | 1.96 | **2.59** | 1716 x ~1510 | 2.25 |

Uncertainty: ±10 % on both. Utilisation after a reshape is not known, and the 0.201 mm2 remainder is not itemised. The transport banks are 0.49 mm2 of
both macros. `pt_wired` loses only the RF sample path and about a third of the register state, so it stays near 2.6 mm2. D2 = yes does not
change the `pt_rf` estimate. The HF route needs the `ring_c` / `cdr` register fields (pfd_mode = line PLL) and the existing decode, not the CDR
control plane `pt_wrx_ctl`. This was checked by reading only, not simulated.

## 5. Cross-mode audit

Method: (a) netlist check of the tagging in table 1: every net of the conn whose instances carry both an rf and a wired tag. (b) Each mode
family of `mode-walk.md` section 1 and each section of `tb_top_modes.sv` (what `check_top_modes.py` runs), walked through the conn from source
to sink. (c) The specific paths named in the brief. All of this is by reading; nothing was simulated.

**(a) Netlist result:** the only nets that join an rf-only and a wired-only instance are `ATB0_LOCAL0`, `ATB1_LOCAL0`, `ATB1_LOCAL3` (local ATB
buses), `RAIL_pll`, `RAIL_debug` (island rails) and `island_off[5]` (debug island isolation). Each is infrastructure that both chips keep, with
a per-chip subset of loads. No signal net crosses. That holds only because the clock blocks below are tagged both. If the TX ring were
wired-only, `WIRE_CK`, `CONV_CLK`, `PREF`, `TXPH[0]` and `host_word_clk` would cross.

### 5.1 Modes

| # | mode / path (source) | blocks used | uses both halves? | resolution | capability lost |
|---|---|---|---|---|---|
| M1 | reset / safe state, always-on bias chain, aosc (tb §0-1) | por, core_bias, aosc, strap, macro | no (infrastructure) | both | none |
| M2 | **RF receive, die-1 baseline: external LO, host_follow clocks** (tb §2; MW 1.2) | REF_IN + AUX_CLK pads, `lo_ext`, LNA → bbfilter → ADC, **`clockmux` PREF = H2D → `pll_tx` (TX ring) → `prescale` (HOST_INT) and `prescale_conv` (CONV_INT)**, `pll_vreg2` | **yes: the TX ring and its prescalers are "rings" in the plan's wired list** | **X1: the pll island minus the CDR ring goes on both** (`clockmux`, `prescale`, `pll_vreg2`, `pll_tx`, `iso_host_clk`, `iso_pll_tx_fbck`, `isw_pll`, `obs_pre4_pll` / `_wire`): 0.33 mm2 on `pt_rf` as built | none |
| M2b | second host_follow route HF: `pll_cdr` → `prescale_hf` → clockmux HF (D-HF "remains bound as the second route") | CDR ring + `cdr` (line-PLL mode) | yes | **D2**: duplicate on `pt_rf` (+0.27 mm2: `pll_cdr` 0.167, `cdr` 0.083, `prescale_hf` 0.013, `obs_pre4_cdr` 0.004), or accept the TX ring as the only host clock source on `pt_rf` | if not duplicated: `pt_rf` loses its only on-chip spare host / converter clock route. A dead TX ring then leaves SPI and SPI memory access only. Today D-CLK (direct H2D_CLK / REF_IN host clock without a ring) is not built |
| M3 | RF transmit / duplex (tb §3) | DAC, txmix, txsum, rfdriver, LO, clocks as M2 | as M2 | as X1 | none. SP-03 (one CONV_CLK for ADC and DAC) is unchanged |
| M4 | on-chip LO synthesizer (tb §4) | QVCO, `lo_vreg`, `lo_mmd`, `lo_pfdcp` (REF = `ref_clk` from `rx_ref_in`), `lo_lf`, `fc_src[5]` | no (`rx_ref_in` is both) | rf | none |
| M5 | wired receive, low and top rate (tb §5; MW 6.2) | HS pad, CTLE, slicer, ptrim, capture, `wordclk_rx`, CDR ring + `cdr` (REF = PREF from clockmux), `vthdac` | no (the clockmux is both) | wired. The ownership rule "LNA vs CDR" (tb §5 negative control) becomes vacuous: the LNA does not exist on `pt_wired` | none |
| M5b | 100BASE-TX raw (tb §5; IX-9..13) | vthdac, slicer vsel, CTLE lf_zero, capture full rate, wiredtx POST_POL | no | wired | none |
| M6 | wired TX, CMOS and CML paths, TMDS (tb §6; MW 6.3) | TX ring, `pt_wiredtx` / `wtx_ser8d` + `wtx_mux8`, pad, interlock, term buffer | no | wired; TX ring is both | none |
| M7 | USB FS/LS/HS (tb §7) | `pad_usb`, `usb_txdrv` (HS data = `wiredtx.CMD_MAIN`), `termination`, `rxselect`, `detect`, `pt_usb`; USB logic runs on the TX word clock (`WTX_WCLK40`) | **no RF block** | wired | none |
| M8 | observation: CLK_OBS, WMON, BB tap (tb §8) | `clk_obs` + `obs_pre4_*`; WMON = `wmon_sel` (wired RX) → `bb_tap_wmon` → `pad_wmon`; BB tap = bbfilter obs/inj ↔ `bb_tap_i/q` ↔ BB pads | CLK_OBS mixes sources of both halves; WMON uses the rf_rx-owned `pt_bb_tap` **master** but no rf instance | CLK_OBS both, absent inputs to VSS; WMON wired (same master, instanced on `pt_wired`); BB tap rf | none. Note: CP4-5 (WMON on a BB_Q pad leg) is no longer possible and is obsolete |
| M9 | monitor / fault, time base (tb §9, 9b) | `pt_monitor`, counters, aosc, island PGs, H2D_CLK | requirement bits of both halves | both. `require_rf_lock` (counter a on LO_FB) is meaningful on `pt_rf`. On `pt_rf` counter b watches the TX ring. The RF rule "aosc off during RF payload, time base 1" applies only to `pt_rf` | none |
| M10 | host link D2H / H2D (MW 6.4) | provider host pads, macro, `host_word_clk` from TX ring / HF | X1 | both | none |
| M11 | SPI-only bring-up, POR / strap / keyed second path | SPI pads, strap, `pt_por_path` | no | both | none |
| M12 | ATB (MW 6.4 §4) | 79 leaves, 7 groups, 2 pads | buses shared | X9 | none |
| M13 | MEMORY capture / playback (host-link fallback) | transport banks over SPI | no | both | none |
| M14 | **WTX_EXT fallback** | `pad_wtx_ext` → `rx_wtx_ext` (debug island) → `iso_wtx_dx` → `wiredtx.DX`; `wtx_fallback_control` | no | wired | none. **OCP-2 dissolves**: there is no reason any more to move WTX_EXT onto the USB pads. USB HS transmit from external serial data is kept. |
| M15 | external converter clock via REF / AUX (clockmux CS_REF / CS_AUX, `debug.clk_select.conv_sample`) | REF / AUX pads, `rx_ref_in` / `rx_aux_clk`, clockmux | no | rf (AUX duplicated, X3) | none |
| M16 | **forwarded wire clock on AUX_CLK** (CP4-3, D-AUXWCK) | `pad_aux_clk` → `rx_aux_clk` → `iso_aux_ck` → `cdr.WCK_IN`, clockmux WCK | **yes: the same pad pair is the external-LO Q leg on the RF side** | **X3: duplicate `pad_aux_clk` + `rx_aux_clk` + `iso_aux_ck`** (0.171 + 0.022 + 0.001 = 0.195 mm2 per chip; both already counted) | none. Gain: the rule `lo_pads_vs_forwarded_clock` no longer constrains `pt_wired`. The ~3.1 mm forwarded-clock route (TIM-08, INT23-13) can be short because the pad can sit next to the CDR |
| M17 | external LO (lo_mode 1 / 3) | REF_IN (I) + AUX_CLK (Q) → `lo_ext` | no | rf | none. The worry "external-LO pads near wired pads" disappears (no wired pads on `pt_rf`). INT23-1 / XT-08 (LO bond leakage into RF_RX) stays and is re-planned on the `pt_rf` ring with free sites |
| M18 | per-chip supply trim (MANDATE 2): ring-monitor readout | `ring_osc` → `fc_src[2]` / CLK_OBS | needs a speed monitor on every die | `ring_osc` both (0.0095 mm2) | none |
| M19 | characterization | `char_atb` (device replicas of LNA, mixer, sampler, driver; R / MIM matching) on ATB 43-54; `char_ro33/ro50/cmldiv` → CLK_OBS IN15; `char_rffet*` (GSG probe frames) | `char_atb` replicates devices of both halves | **D6**: `char_atb` both (0.028); speed cells wired; probe frames rf; `vco_replica` both (0.021) | none if D6 is taken as proposed |

### 5.2 Specific checks from the brief

| check | finding (from the conn unless stated) | resolution |
|---|---|---|
| ADC observing wired-side nodes or eye scan | `ADCI_P/N` and `ADCQ_P/N` connect only `bbfilter_*.out_rx` and the ADC. The eye scan is the capture's edge words `WRX_EW` into the macro, not the ADC | no hit |
| ATB through the ADC or shared monitors | The ATB goes only to `atb0/1_pad` → `ATB0/1` pads. No ATB node feeds the ADC. Leaves by node: 50 on both, 18 rf-only (RF biases, conv trunk/VREF/VCM-ADC biases, `RAIL_rf_rx`, `RAIL_conv`), 11 wired-only (wire trunk, HS_VBIAS, CTLE, wired TX, TERM_VCM, detect, hsbias, CDR bias, `RAIL_wired_rx/tx`) | X9: one ATB code table on both chips; leaves of the absent half are not instanced, and their codes are dead per chip (the same treatment as today's dead codes 4, 25, 41). Group vectors unchanged. On `pt_wired` the rf local bus `ATB1_LOCAL1` keeps 2 leaves (codes 43, 44). On `pt_rf` the wired local bus `ATB1_LOCAL2` keeps codes 58 and the dead 25 and 41 |
| AUX clock pair shared with the forwarded wire clock | yes (M16) | X3 duplicate |
| WTX_EXT fallback | wired-only (M14) | OCP-2 obsolete |
| external LO | rf-only (M17) | — |
| USB or 100BASE-TX touching RF blocks | none (M7, M5b). The only shared item is the `pt_bb_tap` master behind WMON | — |
| frequency counters / monitors measuring rings of the other half | `fc_src`: [0] TX ring (both), [1] CDR ring (wired, or both with D2), [2] `ring_osc` (both), [3] `vco_replica` (both with D6), [4] aosc (both), [5] `LO_FB` (rf) | per-chip tie of absent sources (the macro clamp still sees a 0). Counter codes stay; an absent source reads stopped |
| reference / clock distribution | `rx_ref_in` on the core rail on both. `ref_clk` feeds the macro, clockmux, `lo_pfdcp` (rf) and `obs_pre4_ref`. Host and converter clocks come from the TX ring (X1). D-TXREF: `pll_tx.REF` = PREF (REF, AUX or H2D) on both | X1 |
| characterization cells | M19 | D6 |
| spec rows verified with both halves | `PWR-MODE-CEIL` (ceilings per primary mode, now per chip); `PWR-DROP`, `PWR-THERM` (per die); `HL-LATENCY` (host link on both, gated by USB HS turnaround = wired); `WR-HL-LINECODE` sits in the host-link section but is wired-only. **No row needs both chips in one measurement.** `RF-DUPLEX`, `RF-SELFTEST` (loopback) and `RF-MULTICHIP` (several `pt_rf` dies) are within `pt_rf` | restate the power rows per chip (phase 1) |
| register rules spanning halves | rule 16 `rf_wired_payload_exclusive`; the ownership rule LNA vs CDR (tb §5); rule 41 `lo_pads_vs_forwarded_clock` | 16 and the ownership rule become vacuous; 41 stays on `pt_rf` (AUX as clock vs external LO) |
| island enable groups | wired (0), rf (1), pll (2), conv (4), debug (5) | `pt_rf`: rf, pll, conv, debug. `pt_wired`: wired, pll, debug. The `usb` bit (3) is already dead |
| decap / supply-bond plan | RQ-3 / RQ-3a (rf_rx island: ≥ 3 nF die decap, Q ≤ 3, ≤ 0.5 nH per rail) conflicted with dropping the decap bank on the single die | `pt_rf` can carry the full plan (section 7); dedicated ground bonds from the free sites (RFR-12, PC-25) |
| substrate keep-aways that involved the other half | SUB-08 (wired TX close to the I ADC), INT23-7 (CDR ring and wired front end next to the ADCs) | obsolete; the rule "TX ring to ADC" stays on `pt_rf` (the TX ring is there) |
| ring-to-ring injection (LO-02, INT23-12) | two rings on one `pt_pll_vreg2` | `pt_wired` only, unless D2 = yes |

## 6. Spec rows, open interface rows, risks

### 6.1 `spec/performance-requirements.md` (142 rows)

| tag | n | IDs |
|---|---:|---|
| both | 9 | HL-RATE HL-CORE HL-D2H-MARGIN HL-H2D-MARGIN HL-SSO HL-LATENCY PWR-MODE-CEIL PWR-DROP PWR-THERM |
| rf | 66 | PWR-DIG-RF PWR-HOST-RF RF-WIFI-SENS RF-WIFI-ACR RF-WIFI-EVM RF-WIFI-MASK RF-TX-ACLR RF-TX-HARM RF-TX-POUT RF-BLE-SENS RF-BLE-IBE RF-154-SENS RF-154-EVM RF-BT-EDR RF-RX-IIP3 RF-TX-IRR RF-RX-IRR RF-TX-MUTE RF-WIFI-LOLEAK RF-LO-JIT RF-BLE-CODED-SENS RF-BLE-CODED-CI RF-BLE-CODED-PKT RF-CS-HOP RF-CS-TIP RF-CS-PHASE RF-CS-IQ RF-CS-RTT RF-CS-ANT RF-CS-RANGE RF-154-TURN RF-154-CCA RF-154-FTOL RF-THREAD-CSL RF-PROF-ZIGBEE RF-PROF-MATTER RF-RX-MAXIN RF-RX-AGC RF-RX-OVLD RF-RX-RECOV RF-RX-DCOC RF-RX-IIP2 RF-RX-FLICK RF-RX-LOPN RF-RX-FREF RF-RX-LOLEAK RF-RX-SPUR RF-RX-COEX RF-RX-NFSYS RF-RX-ESD RF-RX-PSRR RF-COEX-PTA RF-HT40-TX RF-HT40-RX RF-XLO-RANGE RF-QVCO-RANGE RF-SUBG-PROF RF-GNSS-RX RF-DUPLEX RF-RADAR RF-BLE-CTE RF-SDR-CAPTURE RF-SDR-SCAN RF-SELFTEST RF-PROF-SWITCH RF-MULTICHIP |
| wired | 67 | PWR-DIG-WIRED WR-PCIE-BER WR-PCIE-JTOL WR-PCIE-PPM WR-SATA-BER WR-SATA-JTOL WR-SATA-PPM WR-DP-BER WR-DP-JTOL WR-DP-PPM WR-SDI-BER WR-SDI-JTOL WR-SDI-PPM WR-GBE-BER WR-GBE-JTOL WR-GBE-PPM WR-PCIE-SSC WR-SATA-SSC WR-DP-SSC WR-PCIE-TXSWING WR-PCIE-TXJIT WR-PCIE-RL WR-PAD-C WR-SATA-TXSWING WR-SATA-OOB WR-PCIE-DETECT WR-GBE-TXSWING WR-TMDS-TXSWING WR-TMDS-BER WR-SDI-TXSWING WR-USB-HSSWING WR-USB-TURN WR-USB-FSLS WR-PLL-JIT WR-SER-DJ WR-SLICER-OFFSET WR-SATA2-BER WR-SATA2-TXSWING WR-SATA2-TXJIT WR-SATA2-JTOL WR-SATA2-RXSENS WR-SATA2-RL WR-DPHBR-TXJIT WR-DPHBR-JTOL WR-DPHBR-RL WR-3G1-BER WR-3G1-TXSWING WR-3G1-TXJIT WR-3G1-JTOL WR-3G1-PPM WR-3G1-RL WR-RATE-CONT WR-RATE-EDGE WR-RATE-LOW WR-HL-LINECODE WR-100TX-TXLVL WR-100TX-TXSHAPE WR-100TX-TXJIT WR-100TX-RL WR-100TX-RXEQ WR-100TX-RXTH WR-100TX-BLW WR-100TX-CDR WR-100TX-SD WR-100TX-BER WR-100TX-HOST WR-100TX-ANEG |

Notes: `PWR-MODE-CEIL` becomes one ceiling table per chip. `PWR-DROP` / `PWR-THERM` apply per die. `HL-LATENCY` is a host-link row on both, but its
gate (USB HS turnaround) is a `pt_wired` need. `WR-HL-LINECODE` is a host-link fit for wired rates: wired. `RF-MULTICHIP` means several `pt_rf` dies. None is obsolete.

### 6.2 `spec/interface-requirements.md`

| section | tag | n | IDs |
|---|---|---:|---|
| 0 BER / confidence | wired | 3 | WR-BER-SIGNOFF WR-BER-PRESCREEN WR-BER-SIM |
| 1 wired interfaces | wired | 89 | all `WR-*` rows of section 1 (PCIe, GbE, SATA 1/2, DP RBR/HBR, TMDS, SDI, USB, 3.125 GBd, rate coverage, 100BASE-TX) |
| 2 radio | rf | 68 | all `RF-*` rows of section 2 |
| 3 host link | both | 27 | HL-UI HL-D2H-SKEW HL-D2H-DCD HL-D2H-JIT HL-D2H-SSO HL-D2H-ISI HL-D2H-BOARD HL-FPGA-WIN HL-D2H-MARGIN HL-H2D-PADIN HL-H2D-CAP HL-H2D-FPGASKEW HL-H2D-JIT/SSO/ISI/BOARD HL-H2D-PADEDGE HL-H2D-MARGIN HL-RATE HL-CORE HL-SSO HL-TRAIN HL-LATENCY HL-DIR HL-RTL HL-FRAME HL-MARGIN HL-RATE-DIR HL-STRETCH HL-MARK |
| 3 host link | wired | 1 | WR-HL-LINECODE |

Note: the host-link budget (section 3) is per die. Pad placement of the D2H/H2D banks is unchanged on both (the macro edge needs it). `HL-DIR`
(reversible banks) and `HL-STRETCH` apply to both.

### 6.3 `scratch/reviews/interface-changes.md`: rows treated as open

The file has no status column. **Definition used:** every row in the sections written since the 2026-11-14 consolidation (line 1447 onward,
168 rows). Rows marked `*` contain a done / applied / published / closed / withdrawn / confirmed word and are probably closed; they are
tagged anyway. Older rows (lines 1-1446, 554 rows) are not tagged. Most are superseded, and some may still be open. That is a gap the
coordinator should accept or close.

| tag | n | IDs |
|---|---:|---|
| both | 71 | CP4-1 CP4-4 CP4-6 CP4-11 CP4-R4 INT23-9 INT23-11 TOP-19 TOP-20* TOP-21 TOP-22* TOP-24 TOP-25 DG6-1* DG6-2 DG6-3 DG6-9* DG6-10 DG6-11 DG6-13 PC-1 PC-2 PC-5 PC-6 PC-7* PC-8* DG6-14 DG6-16* PC-9 PC-10* PC-11 PC-13 PC-16* PC-17* PC-20 DG7-2 DG7-3* DG7-5 DG7-6 OCP-7 PC-21* DG7-11 DG7-12 DF-2 DF-6 DF-10 DF-11 DF-12 EA-1 EA-3* EA-9* EA-10* EA-11 DG8-1* DG8-2* DG8-3 DG8-4 DG8-6 DG8-7* DG8-8* PC-23* PC-27 PC-31 SO-1 SO-2 SO-3 SO-4 SO-5 SO-6 SO-7 WR11-7 |
| rf | 43 | CP4-7 CP4-9 CP4-12 CP4-R1 INT23-1 INT23-2 INT23-3 INT23-4 INT23-5 INT23-6 INT23-8 INT23-10 DG6-4 DG6-5 PC-4 WRX10-DG64* DG7-1 DG7-4 OCP-1* OCP-3 DF-3 DF-5 DF-8* DF-9 EA-2 EA-4 EA-5 EA-6 RQ-1 RQ-2 RQ-3 RQ-3a RQ-4 PC-25 PC-26 RQ-5 PC-29* PC-30 RQ-6 RQ-7* RQ-8 RQ-9 RQ-10 |
| wired | 44 | CP4-3 CP4-8 CP4-10 CP4-R2 CP4-R3 INT23-12* INT23-13 TOP-23 DG6-6 DG6-7 DG6-8* DG6-12* DG6-15* PC-12 PC-14* PC-15 WRX10-DG67* DG7-8* DG7-9 DG7-10 WT32 WT33 WT34 WT35 WT36 WT37* DF-4 DF-7 EA-7 EA-8 WT38 DG8-5* PC-22* PC-24 PC-28* WT39* WT40 WR11-1 WR11-2 WR11-3 WR11-4 WR11-5 WR11-6 WR11-8 |
| obsolete-after-split | 10 | CP4-2 CP4-5 INT23-7 PC-3 PC-18 PC-19 DG7-7 OCP-2* DF-1 DF-13 |

Notes on non-obvious tags:
- obsolete-after-split: CP4-2 (polyphase, already deleted); CP4-5 (WMON on a BB_Q leg: BB_Q is not on `pt_wired`); INT23-7 (CDR ring and wired
  front end next to the ADCs: they are no longer on the same die; the remaining TX-ring-to-ADC rule moves to `pt_rf` floorplan rules); PC-3, PC-18
  (single-chip free-site and bond-map decisions: redone per chip); PC-19 (AGND_RX pad: removed); DG7-7, DF-1, DF-13 (single-die macro booking,
  die fit and skeleton: replaced per chip); OCP-2 (WTX_EXT onto the USB pads: no longer needed, section 5 M14).
- CP4-4 and CP4-R4 are both: `obs_pre4_pll` and `ring_osc` are on both chips; `obs_pre4_cdr` and `char_ro33` are wired.
- CP4-7 (merge `prescale` and `prescale_conv`) is rf: only `pt_rf` has both.
- DG6-4, DG7-4, WRX10-DG64 (host_follow on the TX ring) are rf: they are the `pt_rf` clock baseline.
- DG7-1 (monitor second time base) is rf: the field is both, but the need (aosc off in RF payload) is `pt_rf`'s.
- WT33 / WT38 (TX ring phase spacing) are wired: the ring is on both, but only the serializer needs the spacing.
- WR11-7 (LVS wrapper in `layout_engine`) is both: it is the shared timing layout engine.
- PC-26 / PC-29 (RF_RX to bonds 67/68): rf, to be re-planned on the `pt_rf` ring with dedicated grounds; the bond numbers are obsolete.

### 6.4 `spec/risk-register.md` (221 rows)

| tag | n | IDs |
|---|---:|---|
| both | 91 | DIG-01 HL-06 MOD-00 INT-04 INT-13 MOD-05 MOD-06 MT-03 HL-03 INT-05 PAD-02 PDN-02 PDN-09 PKG-06 PKG-07 PKG-08 PWR-12 PWR-13 DIG-07 INT-14 MOD-18 AN-01 AON-01 BRD-02 DIG-04 ESD-02 HL-01 INT-10 INT-29 ISL-01 LU-03 MOD-01 MOD-02 MOD-07 MOD-08 MOD-11 MOD-17 MOD-20 PAD-04 PAD-11 PDN-03 PDN-11 PKG-09 PWR-02 PWR-06 PWR-11 TIM-12 VER-KL1 INT-30 AON-03 DBG-03 HL-05 HL-07 HL-09 INT-20 ISL-04 MOD-15 MOD-19 PAD-07 PDN-01 PDN-06 PKG-01 PKG-02 PKG-11 SP-02 SUB-10 SUB-11 TIM-04 TIM-05 TIM-10 XT-03 CSP-01 DIG-05 TIM-03 AON-02 ESD-07 OTH-01 PAD-08 TIM-11 PDN-08 TIM-09 ISL-03 PKG-10 ISL-02 SUB-02 LU-01 LU-02 TIM-02 OTH-03 DBG-01 SUB-09 |
| rf | 87 | LO-01 LO-04 LO-05 RFR-01 RFR-12 RFR-14 LO-11 PKG-05 RFR-11 RFR-13 RFT-01 RFT-03 RXR-01 SUB-01 XT-01 XT-08 BRD-01 CNV-05 DBG-02 IQ-03 LO-10 LO-13 LO-15 MOD-16 PKG-03 PKG-04 RFR-03 RFR-05 RFR-06 RFR-10 RFR-15 RFT-06 RXR-02 RXR-04 RXR-07 SP-01 TIM-07 XT-02 XT-04 XT-05 CNV-02 CNV-03 CNV-06 CNV-08 CNV-09 EMI-01 ESD-06 LO-06 LO-07 LO-12 LO-14 MOD-03 MOD-04 MOD-13 PWR-10 RFR-07 RFT-04 RFT-05 RXR-05 RXR-08 RXR-09 RXR-10 RXR-11 RXR-14 RXR-ESD-1 SP-03 SP-04 SUB-03 SUB-12 SUB-13 RXR-06 CDC-02 CNV-07 PAD-10 RXR-12 PAD-06 RFT-02 INT-17 CNV-04 RFR-09 CNV-01 RFR-02 SUB-04 PWR-09 SUB-07 LO-03 TH-01 |
| wired | 40 | WRX-01 WRX-06 WRX-20 WRX-02 WRX-21 WTX-07 WTX-08 DIG-03 MT-01 PAD-09 WRX-08 WRX-19 WRX-22 WTX-03 PWR-01 USB-02 WRX-04 PAD-03 TIM-01 TIM-08 WRX-23 WTX-02 HL-02 HL-04 INT-16 LO-02 TH-04 USB-03 WRX-03 WTX-05 XT-07 WRX-07 PWR-05 WRX-05 WRX-13 PAD-05 ESD-05 USB-01 HL-08 WRX-10 |
| split | 1 | RFR-04 |
| obsolete | 2 | INT-03 SUB-08 |

Notes:
- obsolete: INT-03 (the single die does not fit) is replaced by a per-chip fit row each. SUB-08 (wired TX next to the I ADC) is gone.
- split: RFR-04 covers HT40 receive (rf) and 10BASE-T (wired). Split it into two rows.
- LO-02 (injection between the two rings on one regulator) is wired, or both if D2 = yes. LO-03 (PA / LO into the ring PLLs, closed) is rf
  because the TX ring is on `pt_rf`.
- PKG-03 (RF_TX next to AUX_CLK) is rf until the `pt_rf` ring is re-planned. XT-08 / INT23-1 (external-LO bond leakage) is rf.
- TIM-08 (forwarded clock on AUX_CLK) is wired. Its pad-exclusion part (vs the external LO) is obsolete on `pt_wired`.
- Rows likely relieved by the split, to be re-scored by the owners (not obsolete): RFR-12, RFR-14 (LNA ground and stability with dedicated
  ground bonds), PDN-02, PDN-09, PKG-10 (per-chip currents and bonds), PWR-10, TH-04 (per-chip ceilings), SUB-01, SUB-12, SUB-13 (smaller
  macro, more room on `pt_rf`), INT-13 (per-chip tops).

## 7. Area per chip

Built from table 1 and the ledger (`ledger.csv`: as built / target / lower bound), core 3028 x 4218 um = **12.772 mm2** per chip (same slot).
"both" rows are counted on both chips. The ledger's own digital macro and decap-bank rows are replaced by the per-chip numbers below.

**Ledger items per chip, mm2** (as built / target / lower bound):

| | custom pads (core intrusion) | analog blocks in the conn | booked items | sum |
|---|---|---|---|---|
| `pt_rf` | 0.931 / 0.931 / 0.637 | 5.482 / 4.715 / 4.020 | 0.049 / 0.049 / 0.049 (LNA additions, VCM buffer, D2H strip, RF time base) | **6.463 / 5.695 / 4.706** |
| `pt_wired` | 1.450 / 1.347 / 1.100 | 2.586 / 2.254 / 1.960 | 0.834 / 0.834 / 0.771 (new TX path, second slicer / capture / blender, CTLE followers, T-coil, D2H strip, repeaters, time base) | **4.870 / 4.435 / 3.831** |
| single die today (check) | 2.037 / 1.934 / 1.394 | 7.097 / 6.140 / 5.251 | 0.847 (bank excluded) | 9.98 |

"both" infrastructure inside these sums (counted twice across the pair): core_bias 0.302, island switches pll + debug 0.074, the pll-island
clock blocks 0.29, REF / AUX pads 0.343 and receivers 0.045, `refvcm`, `clk_obs` + four prescalers 0.07, ATB tree up to 0.13, `char_atb` 0.028,
`ring_osc` + `vco_replica` 0.030, por / aosc 0.022, D2H strip 0.031, about 1.38 mm2 in total.

**Decap, full 5.4 nF plan on each chip** (`spec/power-delivery.md` 4.2: bank 1.5 nF + grid MIM 3.0 nF target + macro row fill 0.45 + bond-site tiles 0.45):
- macro-edge bank 1.5 nF = **0.39 mm2** on each chip;
- grid MIM over block outlines: the single-die figure (2.0 / 1.4 / 0.8 nF as built / targets / lower bounds, die-fit section 3) split by
  each chip's share of block area: `pt_rf` 1.55 / 1.07 / 0.61 nF, `pt_wired` 0.73 / 0.51 / 0.30 nF (estimate, no per-block M4/M5 survey per chip);
- row fill scaled with the macro: `pt_rf` 0.32 nF, `pt_wired` 0.41 nF. Bond-site tiles: about 0.22 nF per chip (the 0.45 nF was computed for
  24 custom sites; each chip has about half of them);
- the rest up to 5.4 nF as stacked MOS + MIM tiles (`pt_decap_tile` + MIM, about 4 fF/um2 = 0.25 mm2 per nF): `pt_rf` 1.81 / 2.29 / 2.75 nF
  = **0.45 / 0.57 / 0.69 mm2**, `pt_wired` 2.54 / 2.76 / 2.97 nF = **0.64 / 0.69 / 0.74 mm2**. Tiles may sit in free core that would otherwise
  be scrap, so this is a pessimistic charge.

**Channels and overheads** (die-fit 1.2, apportioned by each chip's share of non-macro block area, 65 % rf / 49 % wired): halo channels
`pt_rf` 0.49-0.70, `pt_wired` 0.37-0.52 mm2. Fixed corridors: `pt_rf` 0.172 (D2H / ADC data / SPI 0.129 + external-LO legs 0.043),
`pt_wired` 0.129. Packing scrap 0.30-0.57 each (not scaled down: fragmentation does not shrink with block count). Routing beyond the channels at
realistic pitch (single die 0.7-1.0 short, die-fit section 3), apportioned: `pt_rf` 0.45-0.65, `pt_wired` 0.34-0.49 (listed separately).

| chip / case | blocks + pads + booked | macro | decap bank + tiles | **demand** | + channels, corridors, scrap | **margin vs 12.772** | margin after routing beyond channels |
|---|---:|---:|---:|---:|---:|---:|---:|
| `pt_rf` as built | 6.46 | 2.01 | 0.84 | **9.32** | 10.28-10.76 | **+2.0 to +2.5** | +1.4 to +2.0 |
| `pt_rf` targets | 5.70 | 2.01 | 0.96 | **8.67** | 9.63-10.11 | **+2.7 to +3.1** | +2.0 to +2.7 |
| `pt_rf` lower bounds | 4.71 | 1.70 | 1.08 | **7.48** | 8.45-8.93 | **+3.8 to +4.3** | +3.2 to +3.9 |
| `pt_rf` as built, D2 = yes (+CDR ring) | 6.73 | 2.01 | 0.83 | **9.57** | 10.55-11.04 | **+1.7 to +2.2** | +1.1 to +1.8 |
| `pt_wired` as built | 4.87 | 2.59 | 1.03 | **8.48** | 9.28-9.70 | **+3.1 to +3.5** | +2.6 to +3.2 |
| `pt_wired` targets | 4.44 | 2.59 | 1.08 | **8.10** | 8.90-9.32 | **+3.5 to +3.9** | +3.0 to +3.5 |
| `pt_wired` lower bounds | 3.83 | 2.25 | 1.13 | **7.21** | 8.01-8.43 | **+4.3 to +4.8** | +3.9 to +4.4 |

Readings and caveats:
- Both chips fit as built with the full 5.4 nF, with about 1.4-3.5 mm2 to spare. The SESSION-STATE estimate (9.4 rf / 8.8 wired) is the same
  order. These numbers are higher on `pt_rf` and lower on `pt_wired` mainly because of the macro estimate (2.0 / 2.6 instead of 2.81 each) and
  the decap tiles.
- `pt_rf` is the tighter one: it carries the large analog blocks (QVCO 0.53, ADC pair 0.90, bbfilter pair 0.68, `lo_vreg` 0.44, probe
  frames 0.20). Its INT23 QVCO placement rule (spirals ≥ 1.7 mm from the west edge, ≥ 1.0 mm from the RF pads) and the keep-aways (macro to
  LNA 1000 um, rings to QVCO 500 um) are the real test. The die-fit noted that the QVCO rule and the `lo` switch position cannot both hold. Only
  the phase-3 packer can say whether they hold on `pt_rf`.
- Estimates (E) that dominate: macro ±10 %; the ledger's E rows on `pt_wired` (second slicer / capture / blender 0.44 not designed, wired TX
  remainder, T-coil, CTLE); grid-MIM split.
- With this margin most die-fit area levers become optional (SPLIT-PLAN phase 4). The decap-vs-area conflict (DF-11) and the RQ-3 decap demand
  for the LNA rail can both be met on `pt_rf`.

## 8. Decisions before phase 1 (coordinator), with recommendations

| # | decision | recommendation | why / cost |
|---|---|---|---|
| D1 | The pll island (TX ring `pll_tx`, `pll_vreg2`, `clockmux`, `prescale`, `iso_host_clk`, `iso_pll_tx_fbck`, `isw_pll`) on **both** chips, against the plan's "rings → `pt_wired`" | **Yes, both.** | `pt_rf`'s host word clock and converter clock come from the TX ring (host_follow baseline, DG6-4 / DG7-4). There is no other built clock source for them (D-CLK not built). +0.33 mm2 on `pt_rf`. |
| D2 | CDR ring (`pll_cdr`, `cdr`, `prescale_hf`, `obs_pre4_cdr`) on `pt_rf` too, as the second host_follow route (HF) | **Yes, unless D-CLK (direct H2D_CLK → host clock) is built.** | It is `pt_rf`'s only spare host / converter clock route ("no dead chip first", fallback-first). +0.27 mm2. It brings LO-02 (ring injection) to `pt_rf`. If D-CLK is built instead (two clockmux selects, a timing-block change), drop D2. |
| D3 | AUX_CLK pair: duplicate `pad_aux_clk` + `rx_aux_clk` + `iso_aux_ck` on both chips | **Yes.** | external-LO Q leg on `pt_rf`, forwarded wire clock on `pt_wired`. 0.195 mm2 each. The external-LO / forwarded-clock exclusion is removed on `pt_wired`. |
| D4 | Register map | **One address map, one generator, per-chip view.** Fields of the absent half are not stored, read 0 and ignore writes. New read-only `status.chip` (ID + per-chip map hash). The obsolete `*.usb` island bits are removed in the same pass. | One host driver serves both chips. `pt_rf` stores 451 bits, `pt_wired` 673 (of 913). |
| D5 | TLP / ESD test site (`pad_tlp`) on one chip only | **`pt_wired` only.** | It is a generic test site. Free `pt_rf` sites are worth more as RF ground bonds. Duplicating it costs one signal site on `pt_rf`, no core area. |
| D6 | Characterization split | **`char_atb` both (0.028), `ring_osc` both (0.0095, needed for per-chip supply trim), `vco_replica` both (0.021, the TX ring is on both), `char_ro33/ro50/cmldiv` `pt_wired`, `char_rffet*` `pt_rf`.** | All the speed cells on both would add 0.047 mm2 to `pt_rf`. Answer CP4-R4 (`ring_osc` vs `char_ro33`) in the same step. |
| D7 | OCP-2 and OCP-1 after the split | **Close OCP-2 as obsolete.** Keep the LO loop-filter capacitor on chip (OCP-1 not taken) now that `pt_rf` has area, but reserve two `pt_rf` sites for it as a fallback option in the bond plan. | WTX_EXT and USB stay on separate pads on `pt_wired`, so USB HS from external serial data is kept. |
| D8 | `core_bias` per chip | **The same generator, a per-chip bank list (parameter), one published composite per chip.** | The bank rails of absent islands do not exist on the other chip. A shared composite would leave banks on floating or tied rails. DF-10 (26 % empty) can be addressed in the same step. |
| D9 | Decap | **Full 5.4 nF plan on both chips: bank + tiles as needed (section 7).** | It fits on both. It closes RQ-3 / RQ-3a on `pt_rf` and the DF-11 conflict. The power-delivery model (PD2) must be rerun per chip, with each chip's macro current. |
| D10 | Macro hardening outlines | **`pt_rf` about 1716 x 1170 um (2.0 mm2), `pt_wired` about 1716 x 1510 um (2.6 mm2), both from one RTL with a `PT_CHIP` parameter.** | The plan expects "both well under 2.81". That holds for `pt_rf`; `pt_wired` is only about 8 % smaller. DG8-6 (D2H hand-over) applies to both. |
| D11 | Bookkeeping baseline | **Phase 1 starts from the 238-instance conn; drop the three AGND rows from the ledger.** Treat the open interface rows as those since line 1447 (section 6.3). | The plan's 241 is the ledger count from before RQ-1. |
| D12 | Pad ring on technical merit | **Use the free sites (`pt_rf` 11, `pt_wired` 9) for RF / LNA ground and QVCO supply on `pt_rf`, and HS-driver grounds on `pt_wired`, as the plan says.** Record per chip that such bonds have no COB capacitor. | User leaves pin assignment to the coordinator. |

## 9. What was not done or remains uncertain

- No packer run: per-chip margins are raw-area arithmetic plus apportioned overheads, not placements.
- The macro numbers scale module areas. No synthesis of either configuration was run.
- The grid-MIM split and the routing / channel apportioning are by area share, not by per-chip wire demand.
- Interface-changes rows before line 1447 are not tagged (section 6.3).
- The HF route's needs on `pt_rf` (D2) and the `atb0_leaf22` select on `pt_rf` were checked by reading only.
- Spec rows in `spec/interface-requirements.md` are tagged by section. Within each section every row is of one half, except
  `WR-HL-LINECODE`.
