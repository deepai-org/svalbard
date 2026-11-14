# Chip block diagram

The programmable transceiver is one GF180MCU mixed-signal die of 3.932 × 5.122 mm on the wafer.space chip-on-board
with its one fixed 74-wire bond layout, controlled and fed by an FPGA host. It contains an RF receive and transmit
chain with an on-chip quadrature LO, a wired serial receive and transmit path (including the 2.7–3.24 Gb/s rates) with
USB, two ADCs and two DACs, two ring PLLs with a CDR, and one digital macro with the SPI and the parallel host link.
Off-chip are only passives, the FPGA and a fallback LNA.

The chip connectivity source of truth is `integration/top/pt_chip.conn` (checked by `integration/top/check_top.py`,
regression `integration/top/run.sh`). This document is a reading aid for it: where they differ, the conn decides.
Open disagreements between neighbouring blocks are the D-rows of `integration/top/decisions.md`; supplies, islands,
grid and decap are in `power-delivery.md`; registers are in `register-map.md`; risks are in `risk-register.md`.

The conn holds 241 instances (151 without the ATB tree), 57 pad nets and 216 control ports (531 bits) from the macro.

## 1. Signal chains

Names are conn instances; `[island]` is the supply island; `c_*` are decoded controls from the digital macro and
`s_*` status into it.

```
RF receive [rf_rx]
  RF_RX_P/N -> pad_rf_rx -> lna (+ lna_ind_p/n tank, lna_deg_p/n degeneration) -> rxmix_i / rxmix_q
            -> bbfilter_i / bbfilter_q -> adc_i / adc_q [conv] -> digital (rf_rx_sample, core A and core B codes)
  bbfilter obs/inj <-> bb_tap_i / bb_tap_q [debug] <-> pad_bb_i / pad_bb_q (BB_I_P/N, BB_Q_P/N)

RF transmit [rf_tx]
  digital (rf_tx_sample, rf_tx_clk_out) -> dac_i / dac_q [conv] -> bbfilter_i/q TX path [rf_rx] or direct (sel_dac)
            -> txmix_i / txmix_q -> txsum -> rfdriver -> pad_rf_tx -> RF_TX_P/N

LO [lo, lod]
  ref_clk -> lo_pfdcp -> lo_lf -> qvco (supply VDD_LO from lo_vreg) -> LOI_I/Q -> lo_ext -> LO_I/Q -> rxmix_i/q, txmix_i/q
  LOI_I -> lo_mmd -> LO_FB -> lo_pfdcp (and frequency counter);  lo_mmd_qdum, lo_obs_q = matched loads on LOI_Q
  LOI_I -> lo_obs -> CLK_OBS path
  external LO: REF_IN/REF_IN_N (I) and AUX_CLK_P/N (Q) -> lo_ext

Wired receive [wired_rx, wired_cap]
  WIRE_RX_P/N -> pad_hs_rx (termination trim from `termination`) -> ctle -> rxselect -> slicer -> wrx_cap
            -> digital (wire_rx_data 40 bit, wire_rx_edge 20 bit, clock WCLK40)
  USB_DP/DN -> pad_usb (levels from rxlevel) -> rxselect (direct), detect, wmon_sel
  sampling clocks: pll_cdr PH0..7 [pll] -> ptrim -> CKP0..7 -> slicer, wrx_cap, wordclk_rx
  CDR loop: wrx_cap UP/DN -> iso_cdr_up/dn -> cdr and pll_cdr [pll];  thresholds: vthdac -> slicer
  wmon_sel -> bb_tap_wmon [debug] -> pad_wmon (WMON)

Wired transmit and USB [wired_tx]
  digital (wire_tx_data 40 bit) -> wiredtx (phases PH0/2/4/6 of pll_tx) -> steer_0..3 -> pad_wire_tx -> WIRE_TX_P/N
  wiredtx CMD_MAIN -> usb_txdrv (HS; FS/LS and chirp levels from the macro; bias from hsbias) -> pad_usb -> USB_DP/DN
  attached_tx_interlock gates the TX pad branches; term_buffer (reference from txpad_bias) drives the TX termination
  external serial data: WTX_EXT_P/N -> pad_wtx_ext -> rx_wtx_ext [debug] -> iso_wtx_dx -> wiredtx.DX
  WIRE_TX_P/N -> detect (receiver detect on the TX pair)

Clocks [pll, core, debug]            see section 4
Host [chip]
  SPI, RESET_N, H2D[9:0] + H2D_CLK, D2H[9:0] + D2H_CLK <-> host (provider pads) <-> digital
Always-on [core]
  por, aosc, core_bias (+ bias_ext), island switches isw_*, ATB tree, outside clamps, characterization structures
```

## 2. Instances

Brace notation is the conn's. "demand" = the block does not exist yet; "staged" = bound to the owner's staged pin
contract, published netlist still differs.

### Chip level (always on)

| Instance | Cell | Function |
|---|---|---|
| `digital` | `pt_digital_macro` | The one digital macro (section 3) |
| `host` | `pt_host_physical` | Provider pads for RESET_N, SPI, H2D[9:0], H2D_CLK, D2H[9:0], D2H_CLK |
| `debug_pads` | `pt_debug_physical` | Provider pads CLK_OBS, DBG_OBS0, DBG_OBS1 |
| `pad_por_bypass` | `pad_strap` (demand) | POR strap pad with pull-down; output `por_bypass` to the macro |
| `atb{0,1}_io` | `atb_provider_pad` | Provider analog pads ATB0, ATB1 |
| `pad_dvdd_{0:5}`, `pad_vdd_{0:1}` | `prov_supply` | 8 supply pads, one net VDD |
| `pad_dvss_{0:7}`, `pad_vss_{0:1}` | `prov_supply` | 10 ground pads, one net VSS |

### Always-on core rail

| Instance | Cell | Function |
|---|---|---|
| `por` | `por` | Power-on reset; `porb` -> macro `por_n` |
| `aosc` | `pt_aosc` | Management oscillator -> `fc_src[4]` |
| `core_bias` | `pt_core_bias` | Bandgap, bias generator and per-block bias outputs with enables; bank rails for rf, conv, pll, wired, debug; references VREF0, VCM |
| `bias_ext` | `pt_bias_ext` (demand) | Bias outputs for `qvco`, `lo_pfdcp`, `hsbias` |
| `isw_{wired_rx,wired_cap,wired_tx,rf_rx,rf_tx,lod,lo,pll,conv,debug}` | `isw_debug`, `isw_wired`, `isw_rf`, `isw_conv` | Island switches (section 5) |
| `agnd_tie` | `pt_agnd_tie` (demand) | The one AGND_RX to VSS connection |
| `rx_ref_in` | `pt_diff_clk_rx` | REF_IN receiver -> `ref_clk`, `s_ref_present` |
| `iso_rf_rx_clk`, `iso_host_clk`, `iso_pll_tx_fbck`, `iso_clk_obs` | `iso_clamp_x4` | Outside clamps on CONV_CLK -> `rf_rx_clk`, HOST_CLK -> `host_word_clk`, TX ring FBCK -> `fc_src[0]`, CLK_OBS |
| `pd_clk_obs` | `iso_pd` | Pull-down on the CLK_OBS node while `clk_obs` is not driving |
| `pad_tlp` | `pad_tlp` | TLP/ESD test site (TLP_TEST) |
| `char_atb` | `pt_char_atb` | Two-terminal characterization devices on ATB codes 43–54 |
| `char_rffet{,_open}`, `char_rffet_short` | `pt_char_rffet*` | RF transistor with its own probe pads, plus open and short de-embedding frames; no chip connection |
| `atb{0,1}_leaf*`, `atb0_grp{0:1}`, `atb1_grp{0:4}`, `atb{0,1}_pad` | `atb_leaf_f`, `atb_leaf_s`, `atb_grp`, `atb_pad` | ATB tree (section 7) |

### RF receive (`rf_rx`), RF transmit (`rf_tx`)

| Instance | Cell | Island | Function |
|---|---|---|---|
| `pad_rf_rx` | `pad_rf_pair` | rf_rx | RF_RX_P/N pad pair, ground AGND_RX |
| `pad_agnd_rx_{0:1}` | `pad_downbond` (demand) | rf_rx | AGND_RX ground sites |
| `lna` | `pt_lna` | rf_rx | LNA with gain step, bypass, attenuator, tuning and single-ended option; I and Q outputs |
| `lna_ind_{p,n}` | `pt_lna_ind` (demand) | rf_rx | Tank load inductors |
| `lna_deg_{p,n}` | `pt_lna_deg` (demand) | rf_rx | Source degeneration inductors |
| `rxmix_{i,q}` | `pt_rxmix_i`, `pt_rxmix_q` | rf_rx | Down-conversion mixers with offset trim |
| `bbfilter_{i,q}` | `pt_bbfilter_i`, `pt_bbfilter_q` | rf_rx | Baseband filter and gain; shared between RX and TX direction, with observe and inject ports |
| `pad_rf_tx` | `pad_rftxpad` | rf_tx | RF_TX_P/N pad pair |
| `txmix_{i,q}` | `pt_txmix_i`, `pt_txmix_q` | rf_tx | Up-conversion mixers; input from the filter or directly from the DAC |
| `txsum` | `pt_txsum` | rf_tx | I/Q summer |
| `rfdriver` | `pt_rfdriver` | rf_tx | RF driver with gain steps, mute, bypass and single-ended option |

### LO (`lo`, `lod`)

| Instance | Cell | Island | Function |
|---|---|---|---|
| `lo_vreg` | `pt_lo_vreg` (demand) | lo | Regulator for the quiet rail VDD_LO |
| `qvco` | `pt_lc_qvco5` | lo | Quadrature LC VCO at the RF carrier; core on VDD_LO, buffer on the lod rail |
| `lo_pfdcp` | `pt_lo_pfdcp` | lo | Phase-frequency detector and charge pump |
| `lo_lf` | `pt_lo_lf` | lo | Loop filter |
| `lo_ext` | `pt_lo_ext` | lod | Selects internal (QVCO) or external LO and drives LO_I/Q to the mixers |
| `lo_mmd` | `pt_lo_mmd` | lod | Feedback divider (6-bit N) |
| `lo_mmd_qdum` | `pt_lo_mmd_qdum` | lod | Matched divider load on the Q tank |
| `lo_obs`, `lo_obs_q` | `pt_lo_obs` | lod | LO observation buffer; the Q copy is a matched load only |

### Clocks, PLLs, CDR (`pll`)

| Instance | Cell | Function |
|---|---|---|
| `pad_ref`, `pad_aux_clk` | `pad_refpad` | REF_IN/REF_IN_N and AUX_CLK_P/N pad pairs |
| `refvcm` | `pt_refvcm` (demand) | Common-mode source for the two reference pads |
| `clockmux` | `pt_clockmux` | Selects the ring reference, wire clock, sampling clock, converter clock and host clock |
| `prescale`, `prescale_conv`, `prescale_hf` | `pt_prescale` | ÷2..÷16 dividers: wire clock -> host and macro, wire clock -> converter, CDR ring -> host-follow |
| `pll_vreg2` | `pt_pll_vreg2` | Regulated supplies for both rings, each with a bypass |
| `pll_tx` | `pt_pll_ring_core` | TX ring PLL; phases to the serializer |
| `pll_cdr` | `pt_pll_ring` | CDR ring PLL; eight phases to the receive samplers |
| `cdr` | `pt_cdr` | CDR loop: steers `pll_cdr` from the capture votes, a reference or the forwarded wire clock |
| `iso_cdr_up_{0:3}`, `iso_cdr_dn_{0:3}` | `iso_clamp` | Clamps on the capture votes entering the pll island |
| `iso_aux_ck` | `iso_clamp_x4` | Clamp on the AUX clock entering the pll island |

### Wired receive (`wired_rx`, `wired_cap`)

| Instance | Cell | Island | Function |
|---|---|---|---|
| `pad_hs_rx` | `pad_hspad` | wired_rx | WIRE_RX_P/N pad pair with trimmed termination |
| `termination` | `pt_termination` | wired_rx | Termination control and common-mode for the HS and USB pads |
| `rxlevel` | `pt_rxlevel` | wired_rx | Input divider / bypass control for the USB pad |
| `ctle` | `pt_ctle` | wired_rx | Equaliser on the HS pair, with bypass |
| `rxselect` | `pt_rxselect` | wired_rx | Selects CTLE output or the USB pair for the slicer |
| `vthdac` | `pt_vthdac` | wired_rx | Two slicer threshold DACs |
| `slicer` | `pt_slicer` | wired_rx | Four data and four edge samplers with per-sampler trim |
| `detect` | `pt_detect` | wired_rx | Differential and single-ended level detectors on the USB pair or the TX pair |
| `wmon_sel` | `pt_wmon_sel` | wired_rx | Selects a wired node for the WMON pad |
| `ptrim` | `pt_ptrim` | wired_cap | Per-phase delay trim of the eight CDR ring phases |
| `wordclk_rx` | `pt_wordclk` | wired_cap | Receive word divider (load enable for the capture) |
| `wrx_cap` | `pt_wrx_cap` | wired_cap | Capture and deserialiser: 40-bit data, edge word, CDR votes, word clock |

### Wired transmit and USB (`wired_tx`)

| Instance | Cell | Function |
|---|---|---|
| `pad_wire_tx` | `pad_txpad` | WIRE_TX_P/N pad pair with main and post branches, termination and detect branch |
| `pad_usb` | `pad_wirepad` | USB_DP/DN pad pair: HS and FS/LS drive, pulls, termination, receive taps |
| `wiredtx` | `pt_wiredtx` | Serializer (40-bit words) and main/post driver commands; external-data input |
| `steer_{0:3}`, `steer_{4:5}` | `tx_steer` | Steering buffers to the TX pad branches; 4 and 5 are tied off |
| `attached_tx_interlock` | `tx_interlock` | Enables one TX pad branch at a time, qualified by the island state |
| `term_buffer` | `term_buffer` | TX termination common-mode buffer |
| `txpad_bias` | `pt_txpad_bias` (demand) | Reference and bias for `term_buffer` |
| `usb_txdrv` | `pt_usb_txdrv` | USB HS and FS/LS pre-driver |
| `hsbias` | `pt_wtx_hsbias` | Programmable bias for the USB HS driver |
| `wtx_fallback_control` | `pt_wtx_fallback_control` | Bring-up fallback: can hold the wired island on and force the wired bias ATB leaf |
| `iso_wtx_dx` | `iso_clamp` | Clamp on the external serial data entering the island |

### Converters (`conv`)

| Instance | Cell | Function |
|---|---|---|
| `adc_{i,q}` | `pt_adc_i`, `pt_adc_q` (staged) | 10-bit ADCs, two interleaved cores (codes A and B, phase output PH) |
| `dac_{i,q}` | `pt_dac_i`, `pt_dac_q` (staged) | 10-bit DACs, clocked by the macro's forwarded `rf_tx_clk_out` |
| `refbuf` | `pt_refbuf` | Converter reference buffer |
| `iso_conv_clk` | `iso_clamp_x4` | Clamp on CONV_CLK entering the island |

### Debug island (`debug`)

| Instance | Cell | Function |
|---|---|---|
| `pad_bb_{i,q}` | `pad_rf_pair` | BB_I_P/N, BB_Q_P/N pad pairs |
| `pad_wtx_ext` | `pad_rf_pair` | WTX_EXT_P/N pad pair |
| `pad_wmon` | `pad_single_leg` | WMON pad |
| `bb_tap_{i,q}`, `bb_tap_wmon` | `pt_bb_tap` | Baseband observe/inject buffers; WMON observe buffer |
| `iso_wmon` | `iso_pd` | Pull-down on the WMON node while the wired group is off |
| `rx_aux_clk` | `pt_diff_clk_rx` | AUX_CLK receiver -> AUX_CK, `s_aux_present` |
| `rx_wtx_ext` | `pt_diff_clk_rx` | WTX_EXT receiver -> external serial data, `s_wtx_ext_present` |
| `ring_osc` | `pt_ring_osc` | Process-monitor ring oscillator -> `fc_src[2]`, CLK_OBS |
| `vco_replica` | `pt_vco_replica` | Ring VCO replica -> `fc_src[3]`, CLK_OBS; control voltage on ATB |
| `obs_pre4_{wire,wsmp,ref,aux,pll,cdr}` | `pt_obs_pre4` | ÷4 prescalers in front of CLK_OBS |
| `iso_lo_obs` | `iso_clamp_x4` | Clamp on the LO observation signal |
| `clk_obs` | `pt_clk_obs16` | 16-input clock observation mux and divider -> CLK_OBS |
| `char_ro33`, `char_ro50`, `char_cmldiv` | `pt_char_ro33`, `pt_char_ro50`, `pt_char_cmldiv` | Speed characterization structures on `clk_obs` input 15 |

## 3. Digital macro

`pt_digital_macro` (`rtl/pt_digital_macro.sv`) contains:

- Reset path (`pt_por_path`): `rst_n` = RESET_N AND (POR OR the `por_bypass` strap OR the keyed, pad-free rescue
  latch). The POR state stays readable over SPI.
- SPI and the generated register file; decode (`pt_ctl_decode`) that turns register fields into one named control
  port per analog pin group (`c_*`, listed in `integration/top/ctl_ports.txt`). The decode glue is in the macro, not
  in the analog top.
- Host link (`pt_host_link`): 10-bit H2D capture and 10-bit D2H launch with forwarded clocks; shared transport, FIFOs,
  capture/playback memory, pattern generator and checker, frequency counters.
- Control blocks: wired TX launch (`pt_wtx_ctl`), wired RX and CDR loop (`pt_wrx_ctl`), USB (`pt_usb`), ADC core
  merge (`pt_adc_merge`, makes the RF sample valid), detector clock (`pt_det_clk`), ring regulator sequencer
  (`pt_vreg_seq`), bandgap interlock.
- Fault monitor (`pt_monitor`), derived inside the macro. Its time base is the management oscillator or the divided
  transport clock. The external `fault` pin is tied to VSS in the conn.
- Isolation: every input that comes from a switched island is ANDed with that group's `island_on` on its first gate
  (130 inputs: wired 69, conv 51, pll 5, debug 4, rf 1; `integration/top/generated/macro_clamps.txt`). Three clock
  nets keep an outside clamp because CLK_OBS shares them: `rf_rx_clk`, `host_word_clk`, `fc_src[0]`.
- Island control: `island_en`, `island_on`, `island_off` per enable group; a group is good when all of its
  switches report power-good (`s_pg_*`).

The register file rejects RF payload blocks and wired payload blocks being active together
(`rf_wired_payload_exclusive`).

## 4. Clocks

| Clock | Source | Consumers |
|---|---|---|
| `ref_clk` | REF_IN pair -> `rx_ref_in` (always-on rail) | macro, `clockmux`, `lo_pfdcp`, `obs_pre4_ref` |
| AUX clock / forwarded wire clock | AUX_CLK pair -> `rx_aux_clk` (debug island) -> `iso_aux_ck` | `clockmux` AUX and WCK inputs, `cdr` wire-clock input, `obs_pre4_aux`. The forwarded wire clock uses this pad pair; the debug island must be on |
| Ring reference `PREF` | `clockmux` (from `ref_clk`, AUX or H2D_CLK) | `pll_tx`, `cdr` |
| TX ring phases | `pll_tx` | `wiredtx` (PH0/2/4/6), `clockmux` (PH0), `obs_pre4_pll` (PH1) |
| CDR ring phases | `pll_cdr` (reference from `cdr`) | `ptrim` -> `slicer`, `wrx_cap`, `wordclk_rx`; `prescale_hf`, `clockmux`, `obs_pre4_cdr` |
| Receive word clock WCLK40 | `wrx_cap` | macro `wire_rx_clk` |
| Transmit word clock | `wiredtx` | macro `wire_tx_clk` |
| Wire clock `WIRE_CK` | `clockmux` (TX ring, `ref_clk`, AUX or forwarded wire clock) | `prescale` -> macro `ct_wclk` and host clock option; `prescale_conv` -> converter clock option |
| Converter clock `CONV_CLK` | `clockmux` (divided wire clock, `ref_clk`, AUX or host-follow) | `adc_i/q` through `iso_conv_clk`; macro `rf_rx_clk` (outside clamp) and `rf_tx_clk` |
| DAC clock | macro `rf_tx_clk_out` | `dac_i/q` |
| Host word clock | `clockmux` HOST_CLK (divided wire clock or host-follow) -> `iso_host_clk` | macro transport and D2H launch |
| H2D_CLK | host pad | macro H2D capture; `clockmux` reference option |
| D2H_CLK | macro | host pad |
| SPI_SCLK | host pad | macro SPI; ≤ 5 MHz |
| Detector clock | macro `ct_det_clk` | `detect` |
| Management oscillator | `aosc` | macro (`fc_src[4]`), `clk_obs` |
| LO | `qvco` or external (section 1) | mixers; `lo_mmd` feedback to `lo_pfdcp` and `fc_src[5]` |

The ADC sample rate in RF modes is 39.0625 MS/s by default, with 40 MS/s selectable (`power-delivery.md` section 5.4).
Frequency-counter sources: `fc_src[0]` TX ring feedback, `[1]` CDR ring feedback, `[2]` `ring_osc`, `[3]`
`vco_replica`, `[4]` `aosc`, `[5]` LO divider output.

## 5. Supply islands

One supply net VDD and one ground net VSS feed the always-on core and ten switched islands. Each island has one
switch from the always-on rail and reports its own power-good. Islands in one enable group start together.

| Island | Rail | Switch (cell) | Enable group (bit) | Instances |
|---|---|---|---|---|
| wired_rx | `RAIL_wired_rx` | `isw_wired_rx` (`isw_debug`) | wired (0) | `pad_hs_rx`, `termination`, `rxlevel`, `ctle`, `rxselect`, `wmon_sel`, `detect`, `vthdac`, `slicer` |
| wired_cap | `RAIL_wired_cap` | `isw_wired_cap` (`isw_wired`) | wired (0) | `wordclk_rx`, `ptrim`, `wrx_cap` |
| wired_tx | `RAIL_wired_tx` | `isw_wired_tx` (`isw_debug`) | wired (0) | `pad_usb`, `pad_wire_tx`, `wiredtx`, `steer_*`, `attached_tx_interlock`, `term_buffer`, `txpad_bias`, `usb_txdrv`, `hsbias`, `wtx_fallback_control`, `iso_wtx_dx` |
| rf_rx | `RAIL_rf_rx` | `isw_rf_rx` (`isw_rf`) | rf (1) | `pad_rf_rx`, `pad_agnd_rx_*`, `lna`, `lna_ind_*`, `lna_deg_*`, `rxmix_*`, `bbfilter_*` |
| rf_tx | `RAIL_rf_tx` | `isw_rf_tx` (`isw_debug`) | rf (1) | `pad_rf_tx`, `txmix_*`, `txsum`, `rfdriver` |
| lod | `RAIL_lod` | `isw_lod` (`isw_wired`) | rf (1) | `lo_ext`, `lo_mmd`, `lo_mmd_qdum`, `lo_obs`, `lo_obs_q`, QVCO buffer supply |
| lo | `RAIL_lo` -> `lo_vreg` -> `VDD_LO` | `isw_lo` (`isw_conv`) | rf (1) | `lo_vreg`, `qvco`, `lo_pfdcp`, `lo_lf` |
| pll | `RAIL_pll` (rings on `VREG_TX`, `VREG_CDR`) | `isw_pll` (`isw_debug`) | pll (2) | `pad_ref`, `pad_aux_clk`, `refvcm`, `clockmux`, `prescale*`, `pll_vreg2`, `pll_tx`, `pll_cdr`, `cdr`, `iso_cdr_*`, `iso_aux_ck` |
| conv | `RAIL_conv` | `isw_conv` (`isw_conv`) | conv (4) | `adc_*`, `dac_*`, `refbuf`, `iso_conv_clk` |
| debug | `RAIL_debug` | `isw_debug` (`isw_debug`) | debug (5) | section 2 "Debug island" |

Enable bit 3 is reserved. The LNA ground is AGND_RX, joined to VSS once through `agnd_tie`. Island currents, switch
sizing, grid and decap: `power-delivery.md`.

Isolation between islands and the always-on logic: macro inputs are clamped inside the macro (section 3); 16 clamp
cells and 2 pull-downs stay outside (`iso_*`, `pd_clk_obs`). Three crossings have no clamp and rely on a control rule
instead (the conn's `waive` lines): the `obs_pre4` clock inputs, the `ptrim` phase inputs and the `wiredtx` phase
inputs, each gated by an enable the macro holds at 0 while the pll island is off. Analog nets that cross islands
without isolation (ADC inputs, DAC outputs, baseband observe/inject) are decision D-ANA.

## 6. Pads

57 pad nets: 55 signals, VDD and VSS. The conn does not state pad sides or bond sites; the bond map is in
`spec/contract.json` and `package-channel.md`.

| Pad nets | Pad instance (family) | Island | Function |
|---|---|---|---|
| RESET_N | `host` (provider) | chip | Reset input |
| SPI_SCLK, SPI_CS_N, SPI_MOSI, SPI_MISO | `host` (provider) | chip | SPI |
| H2D[0:9], H2D_CLK | `host` (provider) | chip | Host-to-device data and clock |
| D2H[0:9], D2H_CLK | `host` (provider) | chip | Device-to-host data and clock |
| POR_BYPASS | `pad_por_bypass` (`pad_strap`) | chip | POR strap, pull-down |
| CLK_OBS, DBG_OBS0, DBG_OBS1 | `debug_pads` (provider) | chip | Clock and digital observation outputs |
| ATB0, ATB1 | `atb0_io`, `atb1_io` (provider analog) | chip | Analog test buses |
| TLP_TEST | `pad_tlp` | core | TLP/ESD test site |
| REF_IN, REF_IN_N | `pad_ref` (`pad_refpad`) | pll | Reference clock; external LO I input |
| AUX_CLK_P, AUX_CLK_N | `pad_aux_clk` (`pad_refpad`) | pll | Auxiliary clock, forwarded wire clock; external LO Q input |
| RF_RX_P, RF_RX_N | `pad_rf_rx` (`pad_rf_pair`) | rf_rx | RF input |
| RF_TX_P, RF_TX_N | `pad_rf_tx` (`pad_rftxpad`) | rf_tx | RF output |
| BB_I_P, BB_I_N, BB_Q_P, BB_Q_N | `pad_bb_i`, `pad_bb_q` (`pad_rf_pair`) | debug | Baseband observe / inject |
| WIRE_RX_P, WIRE_RX_N | `pad_hs_rx` (`pad_hspad`) | wired_rx | High-speed serial input |
| WIRE_TX_P, WIRE_TX_N | `pad_wire_tx` (`pad_txpad`) | wired_tx | High-speed serial output |
| USB_DP, USB_DN | `pad_usb` (`pad_wirepad`) | wired_tx | USB; the pair also feeds `rxselect` directly, `detect` and `wmon_sel` |
| WTX_EXT_P, WTX_EXT_N | `pad_wtx_ext` (`pad_rf_pair`) | debug | External serial data for the TX pad |
| WMON | `pad_wmon` (`pad_single_leg`) | debug | Wired monitor output |
| VDD | `pad_dvdd_{0:5}`, `pad_vdd_{0:1}` | chip | Supply, 8 pads |
| VSS | `pad_dvss_{0:7}`, `pad_vss_{0:1}` | chip | Ground, 10 pads |

AGND_RX is not a pad net of the conn; it is bound to two `pad_downbond` sites (section 9).

## 7. Modes

A mode is a set of enable groups and block states written through the register file; the conn defines no mode table.
Supply-current ceilings per mode family (`spec/budgets/power_budget.py` `PD2_CEILING_MA`, `power-delivery.md`
section 1):

| Mode family | Enable groups needed (from the conn's connectivity) | Ceiling (mA) |
|---|---|---:|
| Wired and USB | wired, pll | 360 |
| RF receive, transmit or duplex with external LO | rf, conv, pll | 260 |
| RF receive, transmit or duplex with the on-chip LO | rf, conv, pll | 340 |

The debug group is added when an observation or fallback path on the debug island is used (AUX clock, forwarded wire
clock, external serial data, baseband taps, CLK_OBS), with at most 40 mA of debug loads enabled at once.

## 8. Fallbacks and observation

| Hook | Path in the conn |
|---|---|
| External LO | REF_IN pair (I) and AUX_CLK pair (Q) -> `lo_ext` (`c_lo_ext`, `c_lo_int`, `c_lo_cmlsel`) |
| LNA bypass (fallback LNA on the board) | `lna.byp` (`c_lna_byp`) |
| External reference / clocks | `clockmux` selects `ref_clk`, AUX, forwarded wire clock or H2D_CLK in place of a ring |
| External serial TX data | WTX_EXT pair -> `rx_wtx_ext` -> `wiredtx.DX` (`c_wiredtx_ext`) |
| Wired TX bring-up fallback | `wtx_fallback_control` |
| Ring regulator bypass | `pll_vreg2` `BYP_TX`, `BYP_CDR` |
| Baseband observe / inject, filter bypass | `bb_tap_i/q` on BB_I, BB_Q; `bbfilter` `byp_s1`, `byp_s23`, `rx_direct`, `inj`; `txmix.sel_dac` |
| CTLE bypass, direct USB-pair receive | `ctle.wire_ctle_bypass`, `rxselect.rxselect_direct` |
| RF driver bypass and mute | `rfdriver.bypass`, `rfdriver.mute` |
| POR bypass | POR_BYPASS strap, and the keyed second path in the macro |
| Wired node monitor | `wmon_sel` -> `bb_tap_wmon` -> WMON |
| Clock observation | `clk_obs` (16 inputs: LO, wire and sampling clocks, converter clock, reference, AUX, both rings, ring feedback, `ring_osc`, `vco_replica`, `aosc`, host word clock, characterization oscillators) -> CLK_OBS |
| Frequency counters | `fc_src[0:5]` in the macro (section 4) |
| Digital observation | DBG_OBS0, DBG_OBS1 from the macro |
| Analog test buses | ATB0 (`atb_leaf_f` leaves), ATB1 (`atb_leaf_s` leaves), table below |
| Characterization | `char_atb`, `char_ro33`, `char_ro50`, `char_cmldiv`, `char_rffet*` |
| TLP site | `pad_tlp` |

ATB codes (leaf instance `atb<bus>_leaf<code>`; ATB1 carries every code, ATB0 only those marked):

| Code | Node | On ATB0 |
|---:|---|---|
| 1 | `ATBN_master_ibias` | yes |
| 2 | `VREF0_MASTER` |  |
| 3 | `VCM_MASTER` |  |
| 4 | `VSS` |  |
| 5 | `VDD` |  |
| 6 | `VDD` |  |
| 7 | `RAIL_wired_rx` |  |
| 8 | `RAIL_rf_rx` |  |
| 9 | `RAIL_pll` |  |
| 10 | `RAIL_wired_tx` |  |
| 11 | `RAIL_conv` |  |
| 12 | `RAIL_debug` |  |
| 13 | `VSS` |  |
| 14 | `ATBN_rf_ibias` | yes |
| 15 | `ATBN_rf_vcm` |  |
| 16 | `ATBN_lna_bias` |  |
| 17 | `ATBN_rxmix_bias` |  |
| 18 | `ATBN_pga_bias` |  |
| 19 | `ATBN_bbfilter_bias` |  |
| 20 | `ATBN_txmix_bias` |  |
| 21 | `ATBN_rfdriver_bias` |  |
| 22 | `ATBN_wire_ibias` | yes |
| 23 | `HS_VBIAS` |  |
| 24 | `ATBN_ctle_bias` |  |
| 25 | `VSS` |  |
| 26 | `ATBN_wiredtx_bias` |  |
| 27 | `TERM_VCM` |  |
| 28 | `ATBN_detect_vref` |  |
| 29 | `ATBN_pll_ibias` | yes |
| 30 | `ATBN_pll_vctrl` |  |
| 31 | `BIAS_pll_ring_tx` |  |
| 32 | `REF_VCM` |  |
| 33 | `ATBN_quadrature_bias` |  |
| 34 | `ATBN_cdr_bias` |  |
| 35 | `ATBN_conv_ibias` | yes |
| 36 | `VREF_CONV` | yes |
| 37 | `VCM_MASTER` |  |
| 38 | `ATBN_adc_bias` |  |
| 39 | `ATBN_dac_bias` |  |
| 40 | `BIAS_hsbias` |  |
| 41 | `VSS` |  |
| 42 | `ATBN_debug_buffer_bias` |  |
| 43 | `CHAR_RN_LNA` | yes |
| 44 | `CHAR_RP_LNA` | yes |
| 45 | `CHAR_RN_MIX` | yes |
| 46 | `CHAR_RP_MIX` | yes |
| 47 | `CHAR_RN_SMP` | yes |
| 48 | `CHAR_RP_SMP` | yes |
| 49 | `CHAR_RN_DRV` | yes |
| 50 | `CHAR_RP_DRV` | yes |
| 51 | `CHAR_RES_A` | yes |
| 52 | `CHAR_RES_B` | yes |
| 53 | `CHAR_MIM_A` | yes |
| 54 | `CHAR_MIM_B` | yes |
| 55 | `ATBN_vbg` | yes |
| 56 | `ATBN_debug_ibias` | yes |
| 57 | `ATBN_idac1` |  |
| 58 | `VCO_REPLICA_VCTRL` | yes |

Codes 4, 13, 25 and 41 are tied to VSS; codes 5 and 6 read VDD.

## 9. Not yet built

From the `check_top.py` regression (`demand=12 staged=4`; every other check is at zero):

- No cell exists for 12 instances: `pad_por_bypass`, `bias_ext`, `pad_agnd_rx_0`, `pad_agnd_rx_1`, `agnd_tie`,
  `refvcm`, `lna_ind_p`, `lna_ind_n`, `lna_deg_p`, `lna_deg_n`, `lo_vreg`, `txpad_bias`.
- `adc_i`, `adc_q`, `dac_i`, `dac_q` are bound to the converters owner's staged pin contract; the published
  netlists still differ.
- The AGND_RX sites are bound as `pad_downbond`, which the fixed bond layout does not offer; the LNA ground has to be
  re-planned on standard bond fingers.
- TLP_TEST is a conn pad net that is not in the bond map.
