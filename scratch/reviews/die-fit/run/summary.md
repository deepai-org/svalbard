| run | scenario | options | core | blocks to place mm2 | placed | unplaced n / mm2 | channels (halo) | free left | of it usable >= 60 um | relaxed | macro | trials |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|
| s | S | macro 3.65 | 12.772 | 8.241 | 199 / 5.442 | 36 / **2.799** | 0.76 | 0.334 | 0.0 | qvco, ptrim, wtx_mux8 | 2024 x 1802 | 12 |
| t | T | macro 3.20 | 12.772 | 7.284 | 212 / 5.826 | 21 / **1.459** | 0.882 | 0.375 | 0.0 | qvco, rfdriver, ptrim, wtx_mux8 | 1716 x 1865 | 12 |
| lb | LB | macro 2.81 | 12.772 | 5.942 | 200 / 5.942 | 0 / **0.0** | 1.066 | 0.97 | 0.473 | qvco, wrx_cap, ptrim, wtx_mux8 | 1716 x 1640 | 12 |
| s-flow | S | macro 3.65, flow-first order only | 12.772 | 8.241 | 221 / 4.774 | 14 / **3.467** | 0.908 | 0.884 | 0.35 | qvco | 1716 x 2126 | 6 |
| t-flow | T | macro 3.20, flow-first order only | 12.772 | 7.284 | 222 / 5.284 | 11 / **2.001** | 0.97 | 0.782 | 0.323 | qvco, rfdriver, wrx_cap | 2024 x 1581 | 6 |
| lb-flow | LB | macro 2.81, flow-first order only | 12.772 | 5.942 | 198 / 5.525 | 2 / **0.418** | 1.025 | 1.43 | 0.953 | qvco, wrx_cap | 1716 x 1640 | 6 |
| s-m28 | S | macro 2.81 | 12.772 | 8.241 | 203 / 6.126 | 32 / **2.115** | 0.842 | 0.331 | 0.0 | qvco, lo_mmd, wtx_mux8, lna | 2024 x 1390 | 6 |
| s-m32 | S | macro 3.20 | 12.772 | 8.241 | 203 / 5.808 | 32 / **2.433** | 0.82 | 0.296 | 0.0 | qvco, wtx_mux8 | 2024 x 1581 | 6 |
| t-m36 | T | macro 3.65 | 12.772 | 7.284 | 186 / 5.483 | 47 / **1.802** | 0.836 | 0.321 | 0.0 | qvco, ptrim | 2024 x 1802 | 6 |
| t-m28 | T | macro 2.81 | 12.772 | 7.284 | 211 / 6.166 | 22 / **1.118** | 0.925 | 0.317 | 0.0 | qvco, ptrim, wtx_mux8 | 2024 x 1390 | 6 |
| t-l1 | T | macro 3.20, debug pads on provider cells | 12.772 | 7.284 | 208 / 6.231 | 25 / **1.053** | 0.913 | 0.342 | 0.0 | qvco, wtx_mux8 | 1716 x 1865 | 6 |
| t-l2 | T | macro 3.20, debug pads on provider cells, no bank | 12.772 | 6.894 | 188 / 6.194 | 19 / **0.7** | 0.961 | 0.333 | 0.0 | qvco, rfdriver, ptrim, wtx_mux8 | 1716 x 1865 | 6 |
| t-l3 | T | macro 3.20, debug pads on provider cells, no bank, ring +36 | 13.299 | 6.894 | 185 / 6.458 | 22 / **0.436** | 1.017 | 0.412 | 0.0 | qvco, lo_mmd, rfdriver, ptrim, wtx_mux8 | 1716 x 1865 | 6 |
| t-l4 | T | macro 3.20, debug pads on provider cells, no bank, ring +36, qdum + lo_obs in the QVCO slot | 13.299 | 6.866 | 186 / 6.458 | 19 / **0.409** | 1.02 | 0.41 | 0.0 | qvco, lo_mmd, rfdriver, ptrim, wtx_mux8 | 1716 x 1865 | 6 |
| t-l4-m28 | T | macro 2.81, debug pads on provider cells, no bank, ring +36, qdum + lo_obs in the QVCO slot | 13.299 | 6.866 | 199 / 6.699 | 6 / **0.168** | 1.089 | 0.43 | 0.0 | qvco, ptrim | 2024 x 1390 | 6 |
| t-l4-flow | T | macro 3.20, debug pads on provider cells, no bank, ring +36, qdum + lo_obs in the QVCO slot, flow-first order only | 13.299 | 6.866 | 199 / 5.697 | 6 / **1.169** | 1.047 | 1.1 | 0.672 | qvco, wrx_cap | 2024 x 1581 | 6 |
| s-l4 | S | macro 3.65, debug pads on provider cells, no bank, ring +36, qdum + lo_obs in the QVCO slot | 13.299 | 7.823 | 174 / 6.25 | 33 / **1.573** | 0.897 | 0.271 | 0.0 | qvco, wrx_cap, rfdriver, ptrim, wtx_mux8, lna | 1716 x 2126 | 6 |
| lb-l3 | LB | macro 2.81, no bank, ring +36 | 13.299 | 5.942 | 200 / 5.942 | 0 / **0.0** | 1.066 | 1.366 | 0.796 | qvco, wrx_cap, ptrim | 2024 x 1390 | 6 |
| lb-l3-flow | LB | macro 2.81, no bank, ring +36, flow-first order only | 13.299 | 5.942 | 199 / 5.747 | 1 / **0.196** | 1.047 | 1.58 | 1.066 | qvco, wrx_cap | 2024 x 1390 | 6 |
| lb-m32 | LB | macro 3.20 | 12.772 | 5.942 | 199 / 5.917 | 1 / **0.025** | 1.047 | 0.667 | 0.133 | qvco, wrx_cap, ptrim, wtx_mux8 | 1716 x 1865 | 6 |
| lb-m36 | LB | macro 3.65 | 12.772 | 5.942 | 196 / 5.783 | 4 / **0.159** | 0.992 | 0.427 | 0.013 | qvco, wrx_cap, rfdriver, ptrim, wtx_mux8 | 1716 x 2126 | 6 |

s best unplaced by ordering strategy (area / giants+flow / flow): {0: 2.799, 1: 3.0025, 2: 3.4668} | biggest unplaced: [('wrx_cap', 0.294), ('r8arch_capture_b', 0.294), ('wtx_ser8d', 0.234), ('detect', 0.173), ('pll_vreg2', 0.173), ('pll_cdr', 0.167)]
t best unplaced by ordering strategy (area / giants+flow / flow): {0: 1.4586, 1: 1.7319, 2: 2.0005} | biggest unplaced: [('bbfilter_q', 0.23), ('pll_vreg2', 0.173), ('pll_cdr', 0.127), ('slicer', 0.11), ('r8arch_slicer_b', 0.11), ('lna_ind_p', 0.069)]
lb best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.0, 1: 0.1631, 2: 0.4176} | biggest unplaced: []
s-flow best unplaced by ordering strategy (area / giants+flow / flow): {0: None, 1: None, 2: 3.4668} | biggest unplaced: [('adc_i', 0.45), ('adc_q', 0.45), ('bbfilter_i', 0.342), ('bbfilter_q', 0.342), ('core_bias', 0.302), ('wrx_cap', 0.294)]
t-flow best unplaced by ordering strategy (area / giants+flow / flow): {0: None, 1: None, 2: 2.0005} | biggest unplaced: [('adc_i', 0.33), ('adc_q', 0.33), ('bbfilter_i', 0.23), ('bbfilter_q', 0.23), ('lo_lf', 0.194), ('core_bias', 0.18)]
lb-flow best unplaced by ordering strategy (area / giants+flow / flow): {0: None, 1: None, 2: 0.4176} | biggest unplaced: [('adc_q', 0.254), ('core_bias', 0.163)]
s-m28 best unplaced by ordering strategy (area / giants+flow / flow): {0: 2.1148, 1: 2.3808, 2: 2.8013} | biggest unplaced: [('core_bias', 0.302), ('wrx_cap', 0.294), ('r8arch_capture_b', 0.294), ('pll_cdr', 0.167), ('dac_q', 0.134), ('r8arch_slicer_b', 0.11)]
s-m32 best unplaced by ordering strategy (area / giants+flow / flow): {0: 2.4331, 1: 2.6473, 2: 3.0215} | biggest unplaced: [('core_bias', 0.302), ('wrx_cap', 0.294), ('r8arch_capture_b', 0.294), ('pll_vreg2', 0.173), ('pll_cdr', 0.167), ('lo_mmd', 0.145)]
t-m36 best unplaced by ordering strategy (area / giants+flow / flow): {0: 1.7996, 1: 1.9309, 2: 2.5302} | biggest unplaced: [('bbfilter_q', 0.23), ('pll_vreg2', 0.173), ('dac_i', 0.13), ('dac_q', 0.13), ('pll_cdr', 0.127), ('refbuf', 0.117)]
t-m28 best unplaced by ordering strategy (area / giants+flow / flow): {0: 1.1181, 1: 1.4075, 2: 1.8205} | biggest unplaced: [('dac_q', 0.13), ('pll_cdr', 0.127), ('slicer', 0.11), ('r8arch_slicer_b', 0.11), ('rfdriver', 0.097), ('lna_ind_n', 0.069)]
t-l1 best unplaced by ordering strategy (area / giants+flow / flow): {0: 1.0531, 1: 1.3944, 2: 1.6482} | biggest unplaced: [('pll_vreg2', 0.173), ('refbuf', 0.117), ('slicer', 0.11), ('r8arch_slicer_b', 0.11), ('lna_ind_p', 0.069), ('lna_ind_n', 0.069)]
t-l2 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.7001, 1: 1.0492, 2: 1.3676} | biggest unplaced: [('pll_cdr', 0.127), ('lo_ext', 0.12), ('lna_ind_p', 0.069), ('lna_ind_n', 0.069), ('pll_tx', 0.065), ('lna', 0.043)]
t-l3 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.4361, 1: 0.7922, 2: 1.1688} | biggest unplaced: [('char_rffet_open', 0.068), ('char_rffet_short', 0.068), ('lna', 0.043), ('usb_txdrv', 0.03), ('attached_tx_interlock', 0.03), ('lna_deg_p', 0.025)]
t-l4 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.4086, 1: 0.7922, 2: 1.1688} | biggest unplaced: [('char_rffet_open', 0.068), ('char_rffet_short', 0.068), ('lna', 0.043), ('usb_txdrv', 0.03), ('attached_tx_interlock', 0.03), ('lna_deg_p', 0.025)]
t-l4-m28 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.1676, 1: 0.6186, 2: 1.2312} | biggest unplaced: [('wtx_mux8', 0.043), ('lna', 0.043), ('lna_deg_p', 0.025), ('lna_deg_n', 0.025), ('vco_replica', 0.021), ('lna_additions', 0.01)]
t-l4-flow best unplaced by ordering strategy (area / giants+flow / flow): {0: None, 1: None, 2: 1.1688} | biggest unplaced: [('adc_q', 0.33), ('bbfilter_i', 0.23), ('bbfilter_q', 0.23), ('lo_lf', 0.194), ('refbuf', 0.117), ('char_rffet_short', 0.068)]
s-l4 best unplaced by ordering strategy (area / giants+flow / flow): {0: 1.5732, 1: 1.8454, 2: 2.522} | biggest unplaced: [('r8arch_capture_b', 0.294), ('pll_cdr', 0.167), ('lo_mmd', 0.145), ('lo_ext', 0.133), ('lo_pfdcp', 0.124), ('r8arch_slicer_b', 0.11)]
lb-l3 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.0, 1: 0.0, 2: 0.1956} | biggest unplaced: []
lb-l3-flow best unplaced by ordering strategy (area / giants+flow / flow): {0: None, 1: None, 2: 0.1956} | biggest unplaced: [('bbfilter_q', 0.196)]
lb-m32 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.0252, 1: 0.3543, 2: 0.5648} | biggest unplaced: [('lna_deg_n', 0.025)]
lb-m36 best unplaced by ordering strategy (area / giants+flow / flow): {0: 0.1589, 1: 0.5344, 2: 0.9} | biggest unplaced: [('lna_ind_n', 0.069), ('lna', 0.039), ('lna_deg_p', 0.025), ('lna_deg_n', 0.025)]
