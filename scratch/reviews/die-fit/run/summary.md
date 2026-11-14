| run | scenario | options | core | blocks to place mm2 | placed | unplaced n / mm2 | channels (halo) | free left | of it usable >= 60 um | relaxed | macro | trials |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|
| b | B | baseline | 12.772 | 8.273 | 211 / 6.132 | 25 / **2.141** | 0.815 | 0.347 | 0.0 | wiredtx, ptrim | 2024 x 1390 | 12 |
| c | C | baseline | 12.772 | 7.518 | 214 / 6.171 | 20 / **1.347** | 0.874 | 0.363 | 0.0 | wiredtx | 2024 x 1390 | 12 |
| cr | CR | baseline | 12.772 | 7.681 | 214 / 6.071 | 20 / **1.61** | 0.86 | 0.43 | 0.024 | wrx_cap, wiredtx, lna, ptrim | 2024 x 1390 | 6 |
| b-flow | B | flow-first order only | 12.772 | 8.273 | 225 / 5.551 | 11 / **2.722** | 0.932 | 0.81 | 0.244 | rfdriver, wrx_cap, wiredtx | 2024 x 1390 | 6 |
| c-flow | C | flow-first order only | 12.772 | 7.518 | 224 / 5.572 | 10 / **1.947** | 0.94 | 0.895 | 0.304 | rfdriver, wrx_cap, wiredtx | 2024 x 1390 | 6 |
| b-h5 | B | halo 5 | 12.772 | 8.273 | 213 / 6.551 | 23 / **1.722** | 0.453 | 0.354 | 0.0 | wiredtx, lo_mmd, lna, ptrim | 2024 x 1390 | 6 |
| c-h5 | C | halo 5 | 12.772 | 7.518 | 220 / 6.475 | 14 / **1.043** | 0.487 | 0.51 | 0.0 | wrx_cap, lo_mmd, ptrim | 2024 x 1390 | 6 |
| c-l1 | C | debug pads on provider cells | 12.772 | 7.518 | 209 / 6.506 | 25 / **1.012** | 0.907 | 0.399 | 0.0 | wiredtx, ptrim | 2024 x 1390 | 6 |
| c-l2 | C | debug pads on provider cells, no bank | 12.772 | 7.128 | 186 / 6.452 | 22 / **0.676** | 0.95 | 0.433 | 0.0 | wiredtx, rfdriver, lna, ptrim | 1716 x 1640 | 6 |
| c-l3 | C | debug pads on provider cells, no bank, ring +36 | 13.299 | 7.128 | 199 / 6.812 | 9 / **0.316** | 1.001 | 0.403 | 0.0 | wiredtx, rfdriver, ptrim | 2024 x 1390 | 6 |
| c-l4 | C | halo 6, debug pads on provider cells, no bank, ring +36 | 13.299 | 7.128 | 205 / 6.904 | 3 / **0.224** | 0.66 | 0.706 | 0.161 | wiredtx, rfdriver, ptrim | 2024 x 1390 | 6 |
| c-l5 | C | halo 6, debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out | 13.299 | 6.905 | 204 / 6.837 | 2 / **0.068** | 0.68 | 0.769 | 0.136 | wiredtx, ptrim | 1716 x 1640 | 6 |
| c-l5-flow | C | halo 6, debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out, flow-first order only | 13.299 | 6.905 | 202 / 6.003 | 4 / **0.902** | 0.657 | 1.612 | 1.108 | wrx_cap, wiredtx | 2024 x 1390 | 6 |
| cr-l5 | CR | halo 6, debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out | 13.299 | 7.068 | 202 / 6.878 | 4 / **0.19** | 0.659 | 0.749 | 0.169 | wiredtx, ptrim | 1716 x 1640 | 6 |
| b-l5 | B | halo 6, debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out | 13.299 | 7.66 | 191 / 7.171 | 17 / **0.488** | 0.595 | 0.451 | 0.0 | wrx_cap, wiredtx, lo_mmd, lna, ptrim | 1716 x 1640 | 6 |
| c-l6 | C | debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out, qdum + lo_obs in the QVCO slot | 13.299 | 6.877 | 195 / 6.686 | 9 / **0.191** | 1.033 | 0.514 | 0.0 | wiredtx, ptrim | 1716 x 1640 | 6 |
| cr-l6 | CR | debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out, qdum + lo_obs in the QVCO slot | 13.299 | 7.04 | 195 / 6.779 | 9 / **0.261** | 1.005 | 0.431 | 0.014 | wiredtx, rfdriver, ptrim | 2024 x 1390 | 6 |
| b-l6 | B | debug pads on provider cells, no bank, ring +36, OPEN/SHORT frames out, qdum + lo_obs in the QVCO slot | 13.299 | 7.632 | 178 / 6.821 | 28 / **0.81** | 0.925 | 0.422 | 0.0 | wrx_cap, wiredtx, lo_mmd, ptrim | 1716 x 1640 | 6 |
| b-g500 | B | die +500 um tall | 14.286 | 8.273 | 222 / 7.06 | 14 / **1.214** | 0.956 | 0.769 | 0.161 | wrx_cap, wiredtx, lna, ptrim | 1716 x 1640 | 6 |
| b-g700 | B | die +700 um tall | 14.892 | 8.273 | 226 / 7.656 | 10 / **0.617** | 1.048 | 0.67 | 0.061 | wrx_cap, wiredtx, rfdriver, lna, ptrim | 1716 x 1640 | 6 |
| b-g900 | B | die +900 um tall | 15.497 | 8.273 | 230 / 8.044 | 6 / **0.229** | 1.088 | 0.833 | 0.267 | wrx_cap, wiredtx, lo_mmd, rfdriver, lna, ptrim | 1716 x 1640 | 6 |
| b-g1100 | B | die +1100 um tall | 16.103 | 8.273 | 236 / 8.273 | 0 / **0.0** | 1.158 | 1.105 | 0.412 | wrx_cap, wiredtx, lo_mmd, ptrim | 2024 x 1390 | 6 |

b best unplaced by ordering strategy (area / giants+flow / flow): {0: 2.1409, 1: 2.3118, 2: 2.722} | biggest unplaced: [('wrx_cap', 0.294), ('r8arch_capture_b', 0.294), ('pll_vreg2', 0.173), ('pll_cdr', 0.167), ('lo_mmd', 0.145), ('dac_q', 0.134)]
c best unplaced by ordering strategy (area / giants+flow / flow): {0: 1.3471, 1: 1.536, 2: 1.9466} | biggest unplaced: [('dac_q', 0.13), ('pll_cdr', 0.127), ('refbuf', 0.117), ('char_rffet', 0.112), ('char_rffet_open', 0.112), ('char_rffet_short', 0.112)]
cr best unplaced by ordering strategy (area / giants+flow / flow): {0: 1.6103, 1: 1.9891, 2: 2.0118} | biggest unplaced: [('tx8_rsv', 0.222), ('pll_cdr', 0.167), ('dac_q', 0.13), ('lo_pfdcp', 0.124), ('char_rffet', 0.112), ('char_rffet_open', 0.112)]
b-flow best unplaced by ordering strategy (area / giants+flow / flow): {0: None, 1: None, 2: 2.722} | biggest unplaced: [('adc_i', 0.45), ('adc_q', 0.45), ('bbfilter_i', 0.342), ('bbfilter_q', 0.342), ('core_bias', 0.302), ('lo_lf', 0.194)]
c-flow best unplaced by ordering strategy (area / giants+flow / flow): {0: None, 1: None, 2: 1.9466} | biggest unplaced: [('adc_i', 0.33), ('adc_q', 0.33), ('bbfilter_i', 0.23), ('bbfilter_q', 0.23), ('lo_lf', 0.194), ('core_bias', 0.18)]
b-h5 best unplaced by ordering strategy (area / giants+flow / flow): {0: 1.7219, 1: 2.193, 2: 2.4855} | biggest unplaced: [('wrx_cap', 0.294), ('r8arch_capture_b', 0.294), ('lo_lf', 0.194), ('pll_vreg2', 0.173), ('pll_cdr', 0.167), ('char_rffet_short', 0.112)]
c-h5 best unplaced by ordering strategy (area / giants+flow / flow): {0: 1.0434, 1: 1.465, 2: 1.7077} | biggest unplaced: [('pll_cdr', 0.127), ('lo_ext', 0.12), ('char_rffet_open', 0.112), ('char_rffet_short', 0.112), ('slicer', 0.11), ('r8arch_slicer_b', 0.11)]
c-l1 best unplaced by ordering strategy (area / giants+flow / flow): {0: 1.0113, 1: 1.2729, 2: 1.7636} | biggest unplaced: [('pll_cdr', 0.127), ('refbuf', 0.117), ('char_rffet_open', 0.112), ('char_rffet_short', 0.112), ('slicer', 0.11), ('r8arch_slicer_b', 0.11)]
c-l2 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.676, 1: 0.9611, 2: 1.5377} | biggest unplaced: [('refbuf', 0.117), ('slicer', 0.11), ('r8arch_slicer_b', 0.11), ('detect', 0.09), ('lna_ind_p', 0.057), ('lna_ind_n', 0.057)]
c-l3 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.3164, 1: 0.7252, 2: 1.0554} | biggest unplaced: [('pll_cdr', 0.127), ('lna_ind_p', 0.057), ('lna_ind_n', 0.057), ('lna_deg_p', 0.025), ('lna_deg_n', 0.025), ('atb1_grp1', 0.006)]
c-l4 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.2243, 1: 0.7625, 2: 1.1254} | biggest unplaced: [('r8arch_slicer_b', 0.11), ('lna_ind_p', 0.057), ('lna_ind_n', 0.057)]
c-l5 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.0681, 1: 0.5389, 2: 0.9018} | biggest unplaced: [('lna', 0.043), ('lna_deg_n', 0.025)]
c-l5-flow best unplaced by ordering strategy (area / giants+flow / flow): {0: None, 1: None, 2: 0.9018} | biggest unplaced: [('adc_q', 0.33), ('bbfilter_i', 0.23), ('bbfilter_q', 0.23), ('char_rffet', 0.112)]
cr-l5 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.1901, 1: 0.7253, 2: 1.1435} | biggest unplaced: [('rfdriver', 0.097), ('lna', 0.043), ('lna_deg_p', 0.025), ('lna_deg_n', 0.025)]
b-l5 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.4882, 1: 0.9681, 2: 1.695} | biggest unplaced: [('char_rffet', 0.112), ('rfdriver', 0.097), ('cdr', 0.083), ('lna_ind_p', 0.036), ('lna_ind_n', 0.036), ('lna_deg_p', 0.025)]
c-l6 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.1907, 1: 0.5823, 2: 0.8318} | biggest unplaced: [('detect', 0.09), ('lna', 0.043), ('vco_replica', 0.021), ('atb0_grp1', 0.006), ('atb1_grp0', 0.006), ('atb1_grp1', 0.006)]
cr-l6 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.2612, 1: 0.7123, 2: 1.0741} | biggest unplaced: [('r8arch_slicer_b', 0.11), ('lna_ind_p', 0.057), ('lna_ind_n', 0.057), ('atb0_grp1', 0.006), ('atb1_grp0', 0.006), ('atb1_grp1', 0.006)]
b-l6 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.8102, 1: 1.1378, 2: 1.7003} | biggest unplaced: [('r8arch_capture_b', 0.294), ('r8arch_slicer_b', 0.11), ('rfdriver', 0.097), ('pll_tx', 0.086), ('lna_deg_p', 0.025), ('lna_deg_n', 0.025)]
b-g500 best unplaced by ordering strategy (area / giants+flow / flow): {0: 1.2138, 1: 1.5123, 2: 1.8068} | biggest unplaced: [('pll_vreg2', 0.173), ('lo_mmd', 0.145), ('lo_ext', 0.133), ('refbuf', 0.117), ('char_rffet_short', 0.112), ('slicer', 0.11)]
b-g700 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.6175, 1: 1.3248, 2: 1.3531} | biggest unplaced: [('lo_mmd', 0.145), ('slicer', 0.11), ('r8arch_slicer_b', 0.11), ('pll_tx', 0.086), ('term_buffer', 0.075), ('lna_deg_n', 0.025)]
b-g900 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.2289, 1: 0.7207, 2: 1.1335} | biggest unplaced: [('r8arch_slicer_b', 0.11), ('lna_deg_p', 0.025), ('lna_deg_n', 0.025), ('vthdac', 0.024), ('rx_aux_clk', 0.022), ('rx_wtx_ext', 0.022)]
b-g1100 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.0, 1: 0.2236, 2: 0.7916} | biggest unplaced: []
