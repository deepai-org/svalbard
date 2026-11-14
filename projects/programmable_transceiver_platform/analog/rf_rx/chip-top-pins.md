# RF RX family: pins and connections at chip top

Pin order is the `.subckt` order of the block `.spice` files in this directory (single source: `netlists.py`).
Bindings are those in `integration/top/pt_chip.conn`; register fields are those in `spec/register-map.md`.
`lna` and `rxmix_i/q` are unpublished candidates (see `README.md` section 1); `bbfilter_i/q` and `bb_tap` are
published. All `island_off` pins take the digital macro's `island_off` bit of their island (rf_rx: bit 1,
debug: bit 5).

## 1. pt_lna

```
.subckt pt_lna rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt
+ island_off atb_nbias atb_vdcm VDD VSS ct3 att0 att1 att2 att3 att4 src_p src_n tank_p tank_n lobias
```

| Pin | Connect to | Notes |
| --- | --- | --- |
| `rf_in_p`, `rf_in_n` | protected `RF_RX_P` / `RF_RX_N` pad nodes | AC-coupled inside the LNA (MIM); no DC path to the pad |
| `rf_out_p`, `rf_out_n` | `rxmix_i.rf_p/n` only | one output pair per mixer, each with its own 16 µm coupling MIM from the tank |
| `rf_outq_p`, `rf_outq_n` | `rxmix_q.rf_p/n` only | must not be left open or shorted to `rf_out_*` |
| `tank_p`, `tank_n` | one `pt_lna_ind` spiral each: terminal A = rf_rx rail, B = `tank_p` (resp. `tank_n`) | 170 µm, 3 turns, 1.35 nH; carries the LNA DC current. Abut the tank pins, keep the two spirals ≥ 1 diameter apart or orthogonal, no fill / MIM / decap over them. Without the spirals the LNA has no DC feed |
| `src_p`, `src_n` | one `pt_lna_deg` spiral each: terminal A = `src_p` (resp. `src_n`), B = `AGND_RX` | on-chip source degeneration, 140 µm, 2 turns, 0.47 nH; not pads. Abut the source pins, ground end straight onto the LNA ground strap, no fill / MIM / decap over them; carries the stage DC current |
| `ibias` | 10 µA sourced from the RF bias bank (`BIAS_lna`) | NMOS diode on the pin |
| `en` | `lna.state != off` | |
| `att0..att4`, `gain_lo` | `lna.match.att[4:0]`, `lna.match.gain_lo` | attenuator code = {`gain_lo`, `att4..att0`}; `gain_lo` is the MSB, not a fixed gain step |
| `byp` | `debug.rf_rx_bypass.lna` | pad to both mixer feeds through a series MIM; use with `en` = 0 (validator rule `lna_bypass_vs_lna`) |
| `ct0..ct3` | `lna.match.ctrim[3:0]`, reset 7 | tank tune |
| `se`, `rt` | `lna.match.se`, `lna.match.rterm`, reset 0 | single-ended input; Q-spoil |
| `lobias` | `lna.bias.lo`, reset 0 | 1 = reduced bias; validator rule `lna_reduced_bias_with_tx` requires 1 whenever the RF driver is active |
| `atb_nbias`, `atb_vdcm` | ATB1 code 16 (`lna_bias`), code 15 (`rf_vcm`) | |
| `VDD`, `VSS` | rf_rx island rail, `AGND_RX` | |

## 2. pt_rxmix_i / pt_rxmix_q

```
.subckt pt_rxmix_i rf_p rf_n lo_p lo_n bb_p bb_n ibias en ofs0 ofs1 ofs2 ofs3 ofs4 ofs_sign island_off
+ atb_vcm atb_vbp VDD VSS
```

| Pin | Connect to | Notes |
| --- | --- | --- |
| `rf_p`, `rf_n` | rxmix_i: `lna.rf_out_p/n`; rxmix_q: `lna.rf_outq_p/n` | |
| `lo_p`, `lo_n` | rxmix_i: `LO_IP` / `LO_IN`; rxmix_q: `LO_QP` / `LO_QN` | gates only; see section 5 |
| `bb_p`, `bb_n` | `bbfilter_x.rx_in_p/n` | high-Z when `en` = 0 |
| `ibias` | 10 µA per mixer from the RF bias bank | |
| `en` | `rxmix_x.state != off` | |
| `ofs0..ofs4`, `ofs_sign` | `rxmix.offset.i_code` / `q_code`: bits 4:0 magnitude, bit 5 sign | sign-magnitude offset DAC at the TIA summing node |
| `atb_vcm`, `atb_vbp` | `atb_vbp` of rxmix_i on ATB1 code 17 (`rxmix_bias`); the others unbound | |
| `VDD`, `VSS` | rf_rx island rail, `VSS` | |

`rxmix_q` may be placed mirrored; nothing in the cell depends on orientation.

## 3. pt_bbfilter_i / pt_bbfilter_q

```
.subckt pt_bbfilter_i rx_in_p rx_in_n tx_in_p tx_in_n inj_p inj_n out_rx_p out_rx_n out_tx_p out_tx_n obs_p obs_n
+ ibias en dir_tx inj rx_direct byp_s1 byp_s23 obs_sel0 obs_sel1 bw0 bw1 bw2 bw3 gain0 gain1 gain2 gain3 gain4 gain5
+ gainc0 gainc1 qt0 qt1 island_off atb_vcm atb_vbp VDD VSS qt2 qt3 fc_fine0 fc_fine1 fc_fine2
+ dcf0 dcf1 dcf2 dcf3 dcf4 dcf5 dcf6 dcf7 dcf_sign
```

| Signal pins | Connect to |
| --- | --- |
| `rx_in_p/n` | `rxmix_x.bb_p/n` |
| `tx_in_p/n` | DAC output (high-Z when not selected) |
| `out_rx_p/n` | ADC input |
| `out_tx_p/n` | `txmix_x.bb_p/n` (high-Z when not selected) |
| `obs_p/n`, `inj_p/n` | `bb_tap_x.in_p/n`, `bb_tap_x.inj_p/n` |

Every control is a static active-high level. I and Q are separate cells with separate trim fields (cutoff, Q
and offset codes are per-part trims); mode bits are shared.

| Pins | Width | Reset | Source and meaning |
| --- | --- | --- | --- |
| `en` | 1 | 0 | `consolidation.bbfilter.direction != isolated`. With `en` = 0 the cell is off regardless of every other bit |
| `dir_tx` | 1 | 0 | `direction == tx`, or `debug.bb_tap.mode == inject_tx_mixer`. 0 = RX (`rx_in` → `out_rx`), 1 = TX (`tx_in` → `out_tx`) |
| `rx_direct` | 1 | 0 | `consolidation.bbfilter.rx_direct`: filter-less RX |
| `byp_s1`, `byp_s23` | 1 each | 0 | `debug.rf_bb_bypass.pga`, `.rxfilter`: stage-1 bypass; stage-2/3 bypass |
| `inj` | 1 | 0 | `debug.bb_tap.mode` in {inject_rx, inject_tx_filter, inject_tx_mixer}; inject_tx_mixer also needs both stage bypasses |
| `obs_sel1:0` | 2 | 0 | from `debug.bb_tap.mode`: observe_rx_mixer → 01 (`rx_in`), observe_rx_pga → 10 (after PGA), observe_rx_filter / observe_tx → 11 (filter output) |
| `gain5:0` (k), `gainc1`, `gainc0` | 6 + 2 | index 2 → 0 dB | `bbfilter_x.trim.gain` is a dB index 0..16 mapped by the table below. Stage-1 gain = k/4 (**k = 0 mutes stage 1**); `gainc0`, `gainc1` add +12 dB each in stages 2 and 3 |
| `bw3:0`, `fc_fine2:0` | 4 + 3 | 8 | `bbfilter_x.trim.cut[6:0]` = cap code m = 8·bw + fine; larger = lower cutoff |
| `qt3:0` | 4 | 6 | `bbfilter_x.trim.qt`; validator: m ≤ 1 requires qt ≥ 6 |
| `dcf7:0`, `dcf_sign` | 8 + 1 | 0 | `bbfilter_x.trim.dcf[8:0]`, sign-magnitude fine DC-offset DAC |
| `ibias` | – | – | 10 µA per filter |
| `atb_vcm`, `atb_vbp` | – | – | bbfilter_i only: ATB1 code 18 (`pga_bias`), code 19 (`bbfilter_bias`) |

PGA table (`netlists.GAIN_TABLE`; the decode in the digital macro is checked by `verification/decode_table`):

| dB | k (`gain5:0`) | gainc0 | gainc1 | | dB | k | gainc0 | gainc1 |
| ---: | ---: | :-: | :-: | --- | ---: | ---: | :-: | :-: |
| −6 | 2 | 0 | 0 | | 21 | 12 | 1 | 0 |
| −3 | 3 | 0 | 0 | | 24 | 17 | 1 | 0 |
| 0 | 4 | 0 | 0 | | 27 | 24 | 1 | 0 |
| 3 | 6 | 0 | 0 | | 30 | 35 | 1 | 0 |
| 6 | 8 | 0 | 0 | | 33 | 12 | 1 | 1 |
| 9 | 12 | 0 | 0 | | 36 | 17 | 1 | 1 |
| 12 | 17 | 0 | 0 | | 39 | 25 | 1 | 1 |
| 15 | 24 | 0 | 0 | | 42 | 36 | 1 | 1 |
| 18 | 35 | 0 | 0 | | | | | |

## 4. pt_bb_tap

```
.subckt pt_bb_tap in_p in_n pad_p pad_n inj_p inj_n ibias obs_en inj_en island_off atb_nbias VDD VSS
```

| Instance | Binding |
| --- | --- |
| `bb_tap_i`, `bb_tap_q` (debug island) | `in_p/n` = `bbfilter_x.obs_p/n`; `inj_p/n` = `bbfilter_x.inj_p/n`; `pad_p/n` = `BB_I_P/N`, `BB_Q_P/N`; `obs_en`, `inj_en` from `debug.bb_tap.mode`; `atb_nbias` of the I tap on ATB1 code 42 |
| `bb_tap_wmon` (debug island) | `in_p` = `WMON_IN`, `pad_p` = `WMON`; `in_n` = `VSS`, `pad_n`, `inj_*` open, `inj_en` = `VSS` |

## 5. LO drive

The RX mixers are passive NMOS quads at a 1.65 V common mode. Every RX number in this directory uses an ideal
0/VDD square LO. The published `pt_lo_ext` delivers 0.62–0.81 Vpp per side centred near 0.72 × VDD, which costs
3.3 dB of conversion gain at tt and 9.8 dB at ss/32 °C/3.15 V (`analog/timing/README.md`). Bench support for real
LO levels: `tb.LO_REAL`, `tb.lo_sources`, and the `lo=` argument of `tb.rxmix_tran` and `tb.chain_det` (sine
models, or `('include', deck)` for the extracted LO distribution).

## 6. Open items

- LNA and mixer cells are not published; the pin lists above are the ones bound at the top and may still change
  with the LNA stability fix.
- `pt_lna_ind` and `pt_lna_deg` have no LVS netlist and are `demand` masters (`integration/top/decisions.md` D-LNA).
- `AGND_RX` has no bond plan under the fixed bond layout; whether the mixers share it is not agreed (D-LNA).
- The unused N leg and inject path of `bb_tap_wmon` at the ties above: to be confirmed safe (D-WMON).
- `DAC*`, `ADC*` and `BB*_OBS/INJ` cross islands without isolation (D-ANA).
