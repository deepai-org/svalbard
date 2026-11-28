# Observation coverage per chip

Current state, 2026-11-20 (owner: observation / debug / bring-up). How a bring-up engineer tells each block
**alive / biased / clocked / working** from the FPGA on `pt_rf` and `pt_wired`. Sources: `integration/chips/common.conn`,
`integration/chips/{rf,wired}/chip.conn`, `spec/register-map.md`, `integration/chips/ctl_ports.txt`, `rtl/pt_digital_macro.sv`.
The bring-up order that uses these paths is [bring-up.md](bring-up.md). Risk row INT-04. Gap rows OBS-1..OBS-23 and the digital implementation OBS-IMPL-1..6 in
`scratch/reviews/interface-changes.md`.

## Paths (both chips)

| Path | Register | What the FPGA sees | Notes |
|---|---|---|---|
| SPI status | 0x00 ID, 0x08/0x09 ABI/hash (0x6EC0 at e3bfb4b2), 0x0A ISLAND_STATUS, 0x0B FAULT, 0x0D RESET_STATUS, 0xF0-0xFF status, 0xFE `status.chip.id` (1 rf, 2 wired) | register reads | works with every PLL stopped (SCLK only) |
| ATB1 sense / ATB0 force | 0x4A `debug.atb.atb1/atb0` | DC on the `ATB1`/`ATB0` pads (SMU / DMM on the test board, `tb_atb_meter`) | one code per bus; codes per chip below; a code with no leaf on this chip is **rejected at write (CONFIG_ERROR b0)** (`spec/chips.json` `atb_no_leaf`, OBS-IMPL-3); ATB0 trunk forces (14, 22, 29, 35, 56) close only with their island on and power-good (22 also with the WTX_EXT fallback active) (OBS-IMPL-5); ATB1 ungated |
| CLK_OBS | 0x4C `debug.clk_obs.source/divider_log2` | f_source / prescale / 2^N on `CLK_OBS` (FPGA clock-capable input, counted against the FPGA TCXO) | needs the debug island; fast sources /4 (`obs_pre4`) or /8 (`lo_obs`) at the source |
| DBG_OBS0/1 | 0x4D sel0/sel1 (0..52) | status levels / divided clocks | list in register-map.md "DBG_OBS" |
| Frequency counters a/b | 0xE8/0xEA source (1 tx_ring_fbck, 2 cdr_ring_fbck, 3 ring_osc, 4 vco_replica, 5 aosc, 6 lc_prescale = LO_FB, 7 dig_ring) ; result 0xF3-0xF6 | count of source edges per 256-4096 `ref_clk` cycles; **sources 3 and 7 count edges / 2** (OBS-IMPL-1/2) | **needs a clock on REF_IN** (`refinput.state` = active); ring_osc path timed at 3.6 ns (278 MHz) |
| Monitor / health | 0xF7/0xF8 `status.monitor.*`; 0xFF `status.health.switch_pg` (b0 rf_rx, b1 rf_tx, b2 lod, b3 lo, b4 wired_rx, b5 wired_cap, b6 wired_tx, b7 pll, b8 conv, b9 debug), `h2d_overflow` b10, `h2d_underflow` b11 | ref/input clock alive, lock, island and per-switch power-good, sticky H2D FIFO errors | external `fault` pin tied 0 on both chips (D-FAULT); supply window comparators do not exist |
| Pattern gen/check | 0x54/0x55, `status.pattern` 0xF0/0xF1 | PRBS error count | H2D loopback on both chips; wired line loopback on pt_wired |
| Capture/playback memory | 0x20-0x26 | 28 quads of ingress data over SPI | last-resort data path, no host clock needed |
| Island current | board supply current | per-island current by toggling `debug.island_power` | the only "alive" indicator for blocks without a tap |

## ATB codes per chip (as bound in the conns)

`.` = no leaf on this chip (the register file rejects these codes on that chip). Duplicates and dead codes are marked.

| Code | Node | pt_rf | pt_wired | Remark |
|---|---|---|---|---|
| 1 | master_ibias (ROOT_REF) | 0/1 | 0/1 | |
| 2, 3 | VREF0, VCM master | 1 | 1 | |
| 5 | core VDD | 1 | 1 | |
| 6 | (map name: host VDD) | VDD_LO via lo_vreg 1 k tap (INT-04 F2) | VREG_TX via pll_vreg2 20 k tap (INT-04 F5) | rebound 2026-11-28; map name unchanged (map hash; coordinator to rule) |
| 7 | wired_rx rail | . | 1 | |
| 8 | rf_rx rail | 1 | . | |
| 9 | pll rail | 1 | 1 | |
| 10 | wired_tx rail | . | 1 | |
| 11 | conv rail | 1 | . | |
| 12 | debug rail | 1 | 1 | |
| 13 | local VSS | 1 | 1 | |
| 14 | TRK_RF_RX | 0/1 | . | |
| 15-21 | rf_vcm, lna, rxmix, pga, bbfilter, txmix, rfdriver bias | 1 | . | pga (18) and bbfilter (19) are I-filter only; rxmix (17) I only |
| 22 | TRK_WIRED_RX | . | 0/1 | ATB0 leaf selected by the fallback control, not atb0_sw |
| 23 | HS_VBIAS (named wire_vcm) | . | 1 | name/net mismatch |
| 24, 26 | ctle, wiredtx bias | . | 1 | |
| 25 | (map name: slicer_bias) | VSS (wired-gated: dead) | TRK_WIRED_TX trunk (INT-04 F6) | rebound on pt_wired 2026-11-28 |
| 27 | TERM_VCM (USB-pad termination VCM) | . | 1 | HS pad `HS_TERM_VCM` and TX `TX_TERM_VCM` have no leaf |
| 28 | detect vref | . | 1 | |
| 29 | TRK_PLL | 0/1 | 0/1 | |
| 30 | TX ring VCTRL | 1 | 1 | CDR ring VCTRL has no leaf |
| 31 | TX ring bias (named pll_cp_bias) | 1 | 1 | RX ring bias has no leaf |
| 32 | REF_VCM | 1 | 1 | |
| 33 | LO quadrature (lo_ext) bias | 1 | . | |
| 34 | CDR bias | 1 | 1 | |
| 35, 36 | TRK_CONV, VREF_CONV | 0/1 | . | |
| 37 | (map name: conv_vcm) | VREG_TX via pll_vreg2 20 k tap (INT-04 F3; conv-island gated) | VCM_MASTER (unreachable: conv-gated) | rebound on pt_rf 2026-11-28 |
| 38, 39 | ADC / DAC bias | 1 | . | I converter only |
| 40 | HS bias (USB) | . | 1 | |
| 41 | (map name: usbfs_vref) | LO VTUNE via the QVCO gated 20 k + TG tap (INT-04 F1) | CDR_VCTRL, leaf beside cdr (INT-04 F4) | rebound 2026-11-28 |
| 42 | debug buffer bias | 1 (bb_tap_i) | 1 (bb_tap_wmon) | |
| 43-54 | characterization devices | 0/1 | 0/1 | |
| 55, 56, 57 | VBG, TRK_DEBUG, IDAC1 | 0/1, 0/1, 1 | same | |
| 58 | VCO replica VCTRL | 0/1 | 0/1 | force the replica |
| — | TRK_LO (pt_rf), TRK_WIRED_TX (pt_wired) | none | none | CB8-8 open |

## pt_rf: per-block table

A = alive, B = biased, C = clocked, W = working. "island I" = board current step on `debug.island_power`.

| Block | Alive / biased | Clocked / frequency | Working | Grade |
|---|---|---|---|---|
| POR, reset, SPI, macro | RESET_STATUS 0x0D, ID 0x00, chip id 0xFE, MAP_HASH | aosc: CLK_OBS 12, fc 5, DBG_OBS 35; macro cell speed: fc 7 (`pt_dig_ring`) | commit counter 0x06, DBG_OBS 3 | full |
| core_bias (bandgap, trunks) | ATB 55 VBG, 1, 2, 3, 57, trunks 14/29/35/56; DBG_OBS 12 bandgap_ok | — | ATB values vs README | full except TRK_LO (OBS-1) |
| island switches | 0x0A pgood + effective-on; ATB1 8/9/11/12 rails | — | — | rf_tx, lod, lo rails have no ATB tap; each switch's power-good is now `status.health.switch_pg` b0-b3 (OBS-IMPL-4); leaves funded (OBS-3) |
| rx_ref_in / REF_IN pad | DBG_OBS 11 ref_present; ATB 32 REF_VCM | CLK_OBS 5 (ref /4) | fc counts need it | full |
| rx_aux_clk / AUX pad | DBG_OBS 28 aux_present | CLK_OBS 6 | — | full |
| clockmux, prescalers | — | CLK_OBS 2/3/4 (WIRE, WSMP, CONV_CLK), 13 host word clock | host link runs | full (by clock) |
| pll_vreg2 (ring regulators) | none | — | rings lock | **VREG_TX / VREG_CDR unobserved** (OBS-4) |
| pll_tx (TX ring) | ATB 30 vctrl, 31 bias | CLK_OBS 8 (/4), 9 fbck; fc 1; DBG_OBS 10 lock | lock + count = target | full |
| pll_cdr, cdr | ATB 34 cdr bias | CLK_OBS 14 (/4); fc 2; DBG_OBS 48 lock | lock | CDR VCTRL no leaf (OBS-5) |
| lo_vreg | none | — | QVCO runs | **VDD_LO unobserved** (OBS-4) |
| qvco, lo_mmd, lo_pfdcp, lo_lf | `c_qvco_atb_en` exists but **ATB_VTUNE / ATB_ITAIL unbound** | CLK_OBS 1 (LO/8 via lo_obs, I tank only); fc 6 = LO_FB (f_VCO/2N) | count = f_ref when locked; no lock bit | **VTUNE unobserved: a railed loop cannot be told from a wrong band** (OBS-7) |
| lo_ext (external LO) | ATB 33 | — (LO_OBS taps the tank side: external LO not on CLK_OBS) | RX tone at BB taps / ADC | ambiguous: no level detector (OBS-8) |
| LNA | ATB 16 lna bias, 15 rf_vcm; island I | — | BB tap tone (observe_rx_mixer), ADC capture | **only the bias mirror is sensed; LNA tail/tank current only as island I** (OBS-9) |
| rxmix I/Q | ATB 17 (I only) | — | BB tap observe_rx_mixer I/Q | Q bias unobserved |
| bbfilter I/Q (PGA, filters) | ATB 18, 19 (I only) | — | BB tap observe_rx_filter/pga; ADC | Q bias unobserved |
| ADC I/Q | ATB 38 (I only), 36 VREF_CONV, 11 rail | CLK_OBS 4 (CONV_CLK) | DBG_OBS 18-21 done/overload; D2H codes; MEMORY capture | full |
| DAC I/Q, refbuf | ATB 39 (I only), DBG_OBS 13 refbuf_ready | DAC clock not observed (macro output) | DAC -> bbfilter rx_direct -> ADC loopback; BB tap observe_tx | full |
| txmix, txsum, rfdriver | ATB 20, 21 | — | RF_TX on a spectrum analyser only | **no on-chip RF power/level detector**; txsum has no tap (OBS-10) |
| bb_tap I/Q, pads BB | ATB 42 | — | BB_I/Q pads | full |
| ring_osc, vco_replica, char_atb, char_rffet | — | CLK_OBS 10/11, fc 3 (edges / 2) / 4 | ATB 43-54, 58 | full (char_rffet by probe) |

## pt_wired: per-block table

| Block | Alive / biased | Clocked / frequency | Working | Grade |
|---|---|---|---|---|
| POR, reset, SPI, macro, core_bias | as pt_rf (TRK_WIRED_RX 22, no TRK_WIRED_TX) | aosc | | TRK_WIRED_TX open (OBS-1) |
| island switches | 0x0A; ATB1 7, 10, 9, 12 | | | wired_cap rail has no tap; switch power-good in `status.health.switch_pg` b4-b6 (`isw_wired_tx_b`: CB8-6); leaves funded (OBS-3) |
| REF/AUX receivers, clockmux, rings, cdr, pll_vreg2 | as pt_rf | CLK_OBS 2/3/5/6/8/9/14; fc 1/2 | ring/CDR lock, `status.wired.rx_*` | VREG_TX/CDR unobserved (OBS-4) |
| termination, pad_hs_rx | ATB 27 TERM_VCM (USB pad side), 23 HS_VBIAS | — | WMON rx_p swing halves with termination on | **HS_TERM_VCM and the termination resistance are not sensed**; resistance only by board SMU (OBS-11) |
| ctle | ATB 24 | — | WMON ctle_p/n | full |
| rxselect, rxlevel | none | — | slicer data only | indirect |
| slicer, vthdac | **ATB 25 dead** | — | `status.wired.rx_*`, pattern errors | bias unobserved (OBS-12) |
| ptrim, wordclk_rx, wrx_cap | none (wired_cap rail untapped) | `rx_flags.wclk_alive`; WRX_WCLK40 not on CLK_OBS | rx_state, violations, pattern checker | clock only as a flag (OBS-13) |
| detect | ATB 28 | — | DBG_OBS 46, `status.usb` | full |
| wiredtx, steer, interlock, txpad | ATB 26 | WTX_WCLK40 not on CLK_OBS | `status.wired.tx_*`; WIRE_TX on a scope; detect `src_tx` senses the TX pads | **TX driver output not observable without an external scope/loop cable except via detect** (OBS-13) |
| term_buffer, txpad_bias | none | — | TX common mode only on the scope | TX_TERM_VCM unobserved (OBS-11) |
| usb_txdrv, hsbias, pad_usb | ATB 40 | — | `status.usb`, scope on USB_DP/DN | full by scope |
| wtx_fallback_control, WTX_EXT rx | DBG_OBS 29 present, 52 data | — | fallback route data | full |
| WMON tap | ATB 42 | — | WMON pad | full |
| ring_osc, vco_replica, char_ro33/50/cmldiv, char_atb, TLP | — | CLK_OBS 10, 11, 15-17; fc 3/4 | | char_cmldiv BIAS sense has no code |

## Blocks that cannot be observed, or only ambiguously

| Gap | Chip | Fix | Owner / row | Area |
|---|---|---|---|---|
| TRK_LO, TRK_WIRED_TX trunks | both | make codes 22 (rf) / 14 (wired) present per chip, add the leaves | digital + core_support (CB8-8, OBS-1) | 2 x atb_leaf_s |
| Ring-osc on the counter above 156.25 MHz (166-260 MHz) | both | **done**: /2 flop before the counters, timed at 3.6 ns (OBS-IMPL-1) | digital | 0 |
| rf_tx, lod, lo, wired_cap rails | rf, wired | switch power-good **done** (OBS-IMPL-4); sense leaves funded, not yet bound | bias/power owner + chip top (OBS-3) | 3-4 leaves |
| VREG_TX, VREG_CDR, VDD_LO | both / rf | bind `pll_vreg2.ATB_OUT` and a VDD_LO tap | timing + chip top (OBS-4) | 2-3 leaves |
| CDR ring VCTRL, RX ring bias | both | leaf on CDR_VCTRL | chip top (OBS-5) | 1 leaf |
| Code with no leaf on this chip | both | **done**: rejected at write per chip (OBS-IMPL-3); dead 25 / 41 and duplicate 37 still accepted (OBS-12) | digital | 0 |
| QVCO VTUNE / ITAIL | rf | bind `qvco.ATB_VTUNE` (gated by `c_qvco_atb_en`) to an ATB1 leaf | LO + chip top (OBS-7) | 1-2 leaves |
| External-LO level at the pads | rf | B31 procedure uses the RX tone; no detector | LO (OBS-8) | — |
| LNA core current | rf | island current step is the reference; optional tail-replica tap | RF RX (OBS-9) | 1 leaf |
| TX RF level | rf | spectrum analyser only (B17 board) | RF TX (OBS-10) | — |
| HS RX / TX termination VCM and resistance | wired | leaves on HS_TERM_VCM, TX_TERM_VCM; board SMU method in bring-up.md | pads (OBS-11) | 2 leaves |
| Slicer bias (code 25 dead), usbfs_vref (41 dead) | wired | bind or retire the codes | wired RX + digital (OBS-12) | 0-1 leaf |
| Word clocks WRX/WTX_WCLK40 | wired | clk_obs IN4 and IN1 are VSS on pt_wired: bind them through a debug-island clamp | chip top (OBS-13) | 2 iso cells |
| Duplicates 5=6, 3=37 | both | document; retire 37 on both | digital (OBS-6) | 0 |
| Digital (5 V-cell) speed | both | **done**: `pt_dig_ring` (41 mcu7t5v0 inversions) on source 7, `debug.replica.dig_ring_enable` (OBS-IMPL-2) | digital | 0.00036 mm² |
| Stale `block_observation` catalog | both | **done**: per-chip `chips`, entries added (OBS-IMPL-3) | digital | 0 |

An atb_leaf_s is 827 µm² (`analog/island_support/README.md`), so the about eight leaves above are 0.007 mm² per chip,
plus the local bus wire.
