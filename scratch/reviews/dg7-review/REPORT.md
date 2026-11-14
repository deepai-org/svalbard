# Independent review of the uncommitted r7 digital changes (2026-11-14)

Verdict: **GO-with-conditions** (separate reviewer agent; this file is written by the digital owner from the reviewer's
final reply; the reviewer's benches and logs are in this directory: tb_mon_tb.sv / mon_tb.log, tb_padseq.sv /
padseq.log, fll_cur.log, run_mon_mutants.py / mon_mutants.log). No consumer samples the asynchronous levels with an
untimed flop; check_wrx_ctl, check_monitor, check_wtx_ctl pass on the reviewed tree.

## Findings
- **F1 (low-medium, simulated): a time-base change does not restart qualification when the old clock was dead.** The
  monitor's arm_s / q / alive / fault_m flops freeze with their clock. Selecting time base 1 and arming in the same
  commit: the new clock finds arm_s = 1, q = 1: fault = 0, ready = 1 for up to one loss timeout (2008 ticks = 51 us in
  the run; worst 4095 ticks = 105 us at the full host rate, 419 us at rate /4) with H2D_CLK dead. Reproducer
  tb_mon_tb.sv +SCEN=4 / 6 (bad), +SCEN=3 / 5 (separate commits: correct). Fix: reword the rule, or clear `sa` and `q`
  asynchronously with `rst_n & req[i]`.
- **F2 (medium-low, read): the two-cycle multicycle on the picker outputs called them quasi-static, but SLIPP / SLIPM
  are one-word commands**: without a common budget PSEL and the command could land in different words.
- **F3 (process): no STA had seen the current SDC and RTL together.**
- **F4 (low, pre-existing): `*det.den_s*` false path covers the second stage** (same class as al_sy).
- **F5 (low, pre-existing): `arm_any` is a combinational OR**: swapping requirement bits while fault is asserted can
  glitch fault low for a gate delay (assertion cannot glitch).
- **F6 (low-medium, pre-existing, outside the diff): asynchronous ASSERT side.** On an abort from S_RUN `w_req` is
  cleared asynchronously while WORD_CLK40 may still give an edge; `wire_tx_request` feeds `wire_load` (40 lane_q flops,
  egress pop) as an ordinary D function: one inconsistent sample is possible. Same pattern: usb.rdy_q via t_rst_n,
  wire_rx_valid via wrun. STA never timed clear-to-Q, so the new false paths hide nothing new; needs "ENABLE is cycled
  after a fault" or a check that the egress read side tolerates it.
- **F7 (info):** bench 9b never does what the rule forbids; one directed case for F1 would pin it.

## Consumers of `fault` and `w_rst_n` (read): no class (d)
wtx.g_sync[*].meta (a: synchronized); wtx.s_ok, ser_q / de_q (b: async clear, D = 0 at release through the synchronized
abort; "at least one REF edge, normally two"); gate_w / fb_req -> c_txpad_req_*, bias_en (c: combinational pins);
usb.trs[4:0] (b: release chain re-times every USB TX flop); usb field synchronizers (a); usb_req, c_usb_*_en (c);
regs.f1 / st1_mon_fault (a); 18 fault-forced fields -> c_* pins (c); obs mux (c); pt_core: no connection;
w_rel (b), wtx.s_de (b, de_q = 0 at release), w_cnt / w_req / w_up (b, D = reset value until w_rel[1]).

## Other items
- Time base: every mon_clk flop input is a pt_sync_bit first stage or an SPI static; outputs end in regs.st1_*,
  monitor.r_hb.meta or the fault gate; fc4 / mon_host exclusivity hides no path. The 4 new mutants of
  check_top_modes.py each fail for the intended reason (8 / 8 / 1 / 13 failing checks).
- pt_tx_pad_sequence: ten parameter sets x 600k cycles incl. forced illegal states and supply_ok pulses: 0 mismatches,
  invariants hold; READY_TIMEOUT 1 / 2 cannot be instantiated.
- pt_wrx_ctl F1 of the 9211b44 review is gone (reviewer's tb_fll MODE 0-3 on the current RTL); nothing else moved.
- SDC wrx bit-0 block: Tcl correct; no other later stage wrongly covered in pt_wrx_ctl / pt_usb / pt_monitor /
  pt_wtx_ctl; no first stage between two timed asynchronous clocks without an exception (table in the reply).
- lt_eq (pt_wtx_ctl) and the reset-seen false path: read, justified.
## Not checked
STA / synthesis / CTS behaviour of the mon_host deletion / hold fixing / GLS / formal on the current tree; runt-pulse
behaviour of mon_mux; reduced host rates on time base 1; regenerated register file beyond the field's existence;
config.json, sta_signoff.py, GLS, libchar edits; F6 in simulation.

## Disposition (digital owner)
- F1: FIXED in RTL (rtl/pt_monitor.sv: `rq_rst_n = rst_n & req[i]` clears sa and q asynchronously; bench T7 now expects
  pending after a dead-clock re-arm; new mutant `rearm_keeps_qualified` is killed) AND the rule text is tightened
  (pt_monitor.sv header, pt_digital_macro.sv, field description).
- F2: resolved by WRX10-DG67 (2): the outputs are used only in full-rate mode (word >= 25 ns); the two-cycle budget at
  the 12.3 ns constraint = 22.1 ns for all five bits = inside the "settled 2 ring periods before the next strobe" rule,
  so PSEL and the command land in the same word. SDC comment rewritten.
- F3: synthesis + STA of the current tree run as syn_r7c (see NOTES).
- F4: fixed (SDC: den_s bit 0 only). F5: rule added to the pt_monitor.sv header. F6: OPEN, recorded in NOTES and the
  final report (host rule "cycle ENABLE after a fault" until the egress read side is checked). F7: not done.
