# Honest demand: instances in pt_chip.conn that are in no floorplan (for the die-fit study)

Generated 2026-11-14 from `integration/top/pt_chip.conn` against `scratch/chip-assembly-v6/run/floorplan-v6.json`.
Areas: `scratch/reviews/consolidation-pass-4/inventory.csv` where the instance or its master is listed, otherwise the
source named in the row. "not built" = build demand (estimate, not a layout). Pad families and the provider ring are
not listed (their sites are fixed). Regenerate by hand after conn changes; `check_top.py` prints the instance list
under "(instances not in the v6 floorplan)".

| Instance(s) | Master | Count | Island | State | um2 each | mm2 total | Area source |
|---|---|---:|---|---|---:|---:|---|
| bias_ext | pt_bias_ext | 1 | core | not built | 9,000 | 0.0090 | est: 3 bank outputs (bank3 = 4210-8964 um2) |
| isw_wired_rx | isw_debug | 1 | core | exists | 36,922 | 0.0369 | v5 abstract bbox |
| isw_rf_tx | isw_debug | 1 | core | exists | 36,922 | 0.0369 | v5 abstract bbox |
| isw_wired_tx | isw_debug | 1 | core | exists | 36,922 | 0.0369 | v5 abstract bbox |
| isw_lod | isw_wired | 1 | core | exists | 64,081 | 0.0641 | v5 abstract bbox |
| isw_lo | isw_conv | 1 | core | exists | 31,781 | 0.0318 | v5 abstract bbox |
| pad_agnd_rx | pad_downbond | 2 | rf_rx | not built | 0 | 0.0000 | in-ring pad site, no core area |
| agnd_tie | pt_agnd_tie | 1 | core | not built |  | ? | no estimate (pad-ring ESD structure, PD2-12) |
| refvcm | pt_refvcm | 1 | pll | not built | 3,000 | 0.0030 | est |
| lna_ind | pt_lna_ind | 2 | rf_rx | not built | 35,700 | 0.0714 | RC-16m: 170 um, 3 turns (48,400 if the 220 um coil is adopted) |
| lna_deg | pt_lna_deg | 2 | rf_rx | not built | 25,200 | 0.0504 | RC-16t: 140 um, 2 turns |
| iso_wmon | iso_pd | 1 | debug | exists | 95 | 0.0001 | iso-placement.json size_um |
| iso_conv_clk | iso_clamp_x4 | 1 | conv | exists | 1,025 | 0.0010 | iso-placement.json size_um |
| iso_rf_rx_clk | iso_clamp_x4 | 1 | core | exists | 1,025 | 0.0010 | iso-placement.json size_um |
| lo_vreg | pt_lo_vreg | 1 | lo | not built | 81,500 | 0.0815 | est: half of pll_vreg2 (one regulator, 25 mA) |
| lo_obs_q | pt_lo_obs | 1 | lod | exists | 17,428 | 0.0174 | area-pass-4 util.json outline |
| rx_ref_in | pt_diff_clk_rx | 1 | core | exists | 22,341 | 0.0223 | area-pass-4 util.json outline |
| iso_host_clk | iso_clamp_x4 | 1 | core | exists | 1,025 | 0.0010 | iso-placement.json size_um |
| prescale_conv | pt_prescale | 1 | pll | exists | 12,600 | 0.0126 | area-pass-4 util.json outline |
| prescale_hf | pt_prescale | 1 | pll | exists | 12,600 | 0.0126 | area-pass-4 util.json outline |
| iso_pll_tx_fbck | iso_clamp_x4 | 1 | core | exists | 1,025 | 0.0010 | iso-placement.json size_um |
| iso_cdr_up | iso_clamp | 4 | pll | exists | 906 | 0.0036 | iso-placement.json size_um |
| iso_cdr_dn | iso_clamp | 4 | pll | exists | 906 | 0.0036 | iso-placement.json size_um |
| iso_aux_ck | iso_clamp_x4 | 1 | pll | exists | 1,025 | 0.0010 | iso-placement.json size_um |
| iso_wtx_dx | iso_clamp | 1 | wired_tx | exists | 906 | 0.0009 | iso-placement.json size_um |
| obs_pre4_wsmp | pt_obs_pre4 | 1 | debug | exists | 3,667 | 0.0037 | area-pass-4 util.json outline |
| obs_pre4_ref | pt_obs_pre4 | 1 | debug | exists | 3,667 | 0.0037 | area-pass-4 util.json outline |
| obs_pre4_aux | pt_obs_pre4 | 1 | debug | exists | 3,667 | 0.0037 | area-pass-4 util.json outline |
| obs_pre4_pll | pt_obs_pre4 | 1 | debug | exists | 3,667 | 0.0037 | area-pass-4 util.json outline |
| obs_pre4_cdr | pt_obs_pre4 | 1 | debug | exists | 3,667 | 0.0037 | area-pass-4 util.json outline |
| iso_lo_obs | iso_clamp_x4 | 1 | debug | exists | 1,025 | 0.0010 | iso-placement.json size_um |
| pd_clk_obs | iso_pd | 1 | core | exists | 95 | 0.0001 | iso-placement.json size_um |
| iso_clk_obs | iso_clamp_x4 | 1 | core | exists | 1,025 | 0.0010 | iso-placement.json size_um |
| txpad_bias | pt_txpad_bias | 1 | wired_tx | not built | 3,000 | 0.0030 | est |
| usb_txdrv | pt_usb_txdrv | 1 | wired_tx | exists | 31,457 | 0.0315 | USB-INTEGRATION.md rev 3 layout 116.48 x 270.06 |
| char_atb | pt_char_atb | 1 | core | exists | 28,801 | 0.0288 | char_atb-physical.json |
| char_ro33 | pt_char_ro33 | 1 | debug | exists | 10,118 | 0.0101 | char_ro33-physical.json |
| char_ro50 | pt_char_ro50 | 1 | debug | exists | 9,724 | 0.0097 | char_ro50-physical.json |
| char_cmldiv | pt_char_cmldiv | 1 | debug | exists | 28,613 | 0.0286 | char_cmldiv-physical.json |
| char_rffet | pt_char_rffet | 1 | core | exists |  | ? | char_rffet-physical.json (probe frame) |
| char_rffet_open | pt_char_rffet_open | 1 | core | exists |  | ? | same frame as char_rffet (assumed) |
| char_rffet_short | pt_char_rffet_short | 1 | core | exists |  | ? | same frame as char_rffet (assumed) |
| atb0_leaf58 | atb_leaf_f | 1 | core | exists | 1,086 | 0.0011 | v5 abstract bbox |

Sum of the rows with a number: **0.634 mm2**.

Not in the table, same study:
- Island switches: the floorplan has 5 (`isw_wired`, `isw_rf`, `isw_pll`, `isw_conv`, `isw_debug`); the conn has 10 on the same
  masters (rows above list the ones the floorplan lacks). `spec/power-delivery.md` section 2: 0.427 mm2 total, +0.191 mm2.
- Decap bank 0.39 mm2 (power-delivery section 4.2) and the M4/M5 grid: not instances of the conn.
- Isolation that moved into the digital macro (CP4-1): 130 AND2 cells inside the macro, no analog-core area.
- Removed since v6 (area returned): `polyphase` (CP4-2, 0.039 mm2), `rx_wclk_in` + `pad_wclk_in` + one `obs_pre4` (CP4-3, 0.174 mm2
  with the pad), the four `iso_pd` on LO_*.
- Outline changes of placed blocks (not instance-count changes): staged converters (adc 0.450, dac 0.134 mm2), `pt_cdr` r13
  0.083 mm2, capture r7c 1212 x 242 um, LNA core 42.9k um2, `wtx_serq8` if adopted (0.352 mm2 vs the 450 x 445 booking),
  `tx_cml_predriver` x2 if adopted, QVCO regulator (estimate only; LO22 says a two-stage design).
