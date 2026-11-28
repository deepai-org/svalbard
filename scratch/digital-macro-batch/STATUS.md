# Digital macro batch re-harden (branch macro/reharden, worktree /home/ubuntu/svalbard-macro)

Brief: one batched re-harden of pt_digital_macro for both chips, pins and outline frozen (pt_rf DG9-29 pins =
pin_order.cfg, pt_wired DG9-30 pins = pin_order_wired.cfg), library gf180mcu_fd_sc_mcu7t5v0 unchanged.

## RTL items (status)
| Item | Change | Test |
|---|---|---|
| DIG-08a hword | host_rate FSM on 1-in-4 enable, SDC HOST_RATE_FSM multicycle 4/3 | tb_host_rate_clock (+ ce premise monitor, negative deposit) |
| DIG-08b ref | wtx reset-sync second stages / ser_q / de_q RN cut (D=0 at release); pad_down registered; timer compares on tmr | check_wtx_ctl (mutants) |
| DIG-08c wstb | gear reset second stage = 12 kept replicas of g_rn (one slice each) | check_wrx_gear (mutants) |
| CM-1 | host_clk ref_in (2) / h2d_direct (6) decode, HS_REF/HS_H2D on wired c_clockmux_cs[1:0], rf c_cdr_fup/fdn | check_top_modes (decode) |
| PRBS counter + loopback | status.pattern.words_lo / status.chip.pattern_words_hi; debug.pattern.loopback (CDC FIFO) | tb_digital_prbs cases 6-7 |
| INT-04 F7 | rf atb1 accepts 10 (CDR_VCTRL) and 22 (TRK_LO); wired atb1 accepts 11 (VTAP); conn leaves added | gen_regfile conn check, check_top |
| USB-02 | digital.transport_config.hs_repeat x4 repetition (pt_rep4_tx); rule ls_slow -> usbhs.bias.enable | tb_usb_hs A, C (negative) |
| DIG-03 | usb.config.hs_turnaround / ta_delay; pt_usb end-of-packet trigger; pt_core egress hold/release | tb_usb_hs B, tb_pt_usb case 8 |
| WTX-09 | wtx.run_force on pt_wired c_adc_i_en | (decode) |
| TIM-04 | rule host_follow_needs_line_pll | regfile rules |
| HL-06 fc2 | fc2 period 5.0 ns at ss corners (SDC) | STA |
| HL-04 | already fixed in RTL (legal_n admits 5/6); row stale | - |
| MOD-17 macro part | already in RTL (pt_bgap_interlock gates the consumers) | - |
| PDN-02 two-phase | in progress | - |

## Harden runs
(see below)
