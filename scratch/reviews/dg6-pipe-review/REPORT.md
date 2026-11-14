# Independent review of commit 9211b44 (pipelining of pt_wrx_ctl, pt_usb, pt_monitor, SDC exceptions)

Verdict: **GO-with-conditions** (reviewer = separate agent, 2026-11-14; this file was written by the digital owner
from the reviewer's final reply because the reviewer's own file write was refused; benches, old/new sources, run.sh and
run.log in this directory are the reviewer's). Conditions: fix F1 before the RTL is frozen; fix F2 before the next
P&R / hold-fix run. **Both applied in r7 (see "Disposition").**

## Findings
- **F1 (medium, simulated): a restart does not cancel an FLL evaluation in flight.** rtl/pt_wrx_ctl.sv `ev_ok`, decision
  flops `d_*`, strobe delay line `evd` are not cleared by `!frun`; a strobe exactly 5 reference cycles before a
  one-cycle `kick` (or a one-cycle drop of the synchronized enable) executes its decision on the restarted loop: in
  tolerance -> `st_fll_done`, `st_freq_ok`, state 7 while re-acquiring; out of tolerance -> a full-length stale pulse.
  Probability one reference cycle per counter window. Reproducer `tb_fll.sv` (+MODE=1 +INTOL=1 / 0, +MODE=3, +MODE=2).
  Candidate fix `ev_ok = evd[4] && frun && !man_pend && !me_q` (src/pt_wrx_ctl_fixcand.sv): MODE 1/2/3 clean, random
  equivalence still passes.
- **F2 (medium-low, read + netlist names): synchronizer false paths cover the later stages.** SDC `*wrx.al_sy*`,
  `*wrx.lk_sy*`, `*wrx.fk_sy*` match every bit; only bit 0 is a first stage. Stage-to-stage paths lose setup/hold checks
  and hold fixing; a hold failure on al_sy[1] -> al_sy[2] keeps the word domain in reset.
- **F3 (low, simulated): pt_usb engine-off loses the held quad** (holding register is almost always full): 507 of 480
  engine-off events lost an accepted quad (old: 15). Nothing stale is sent after re-enable. Document for the host.
- **F4 (low, simulated): picker step period is n + hold + 7 words** (old n + hold); fastest one step per 8 words.
- **F5 (low): pt_monitor qualification completion:** a requirement armed in the q_done tick or the next qualifies
  with the others; an interruption in the q_done_q tick cancels with no cause bit (fault asserted in both).
- **F6 (info):** first bad_q seen with rdy = 1 is the reset value: st_sig_ok needs 2^lock_exp good words, not +1.
- **F7 (info, simulated):** pt_usb RX sample counter phase after reset differs by one sample until the first line change.
- **F8 (info):** debounce saturates; st_tx_underrun one clock after the request is withdrawn; FUP/FDN fall one ref cycle
  later on disable; island AND is after the last flop; USB line-state status is not delayed with rx_data (harmless).
- **Unverified observation outside the commit:** `tx_data` = {wire_high, wire_low} are re-registered copies of lane_q
  while tx_valid is aligned with lane_q (rtl/pt_core.sv:224-249): a quad taken in its first valid cycle could carry the
  previous word's upper half (same in the old block). Worth one directed macro test.

## SDC exceptions of the commit
| exception | verdict |
|---|---|
| `-to *wrx.al_sy* / lk_sy* / fk_sy*` | too wide (F2) |
| 16 por_path key flops `-through */RN`, `*/SETN` | justified (key shifts only with RESET_N low; count check; `ovr` not matched) |
| `-from *monitor.fault_m*` | justified by contract; mon_lost / arm_any legs were not cut |
| `-from *wrx.wrun*` | justified (drives exactly the two RN pins of the release synchronizer wrs) |
| multicycle 3 / hold 2 wrx.mag -> out_loss_q | justified (mag changes at cycles 2, 3 after fc_upd; consumed at cycle 6; windows >= 256) |

## Verified by simulation (old = 9211b44^, new = 9211b44; ./run.sh)
tb_fll MODE 0 (5 seeds, 246 segments: identical pulse direction / length, done / lost, err / win when stimuli are >= 16
cycles from a strobe); tb_pick (128 constant cases equal PSEL sequences, 252 closed-loop combinations never wider than
old, steps never closer than hold + 8, manual picker cycle-identical); tb_usb_tx (every taken quad on the line once,
in order; valid = 1: identical stream at old + 3 clocks); tb_usb_rx (rx_data / valid / active = old delayed 2 clocks);
tb_mon (disarm releases fault with all clocks stopped; random segments identical except the F5 tick).
## Not checked
STA, synthesis, GLS, formal; pt_usb HS branch / force / BBM / echo with TX active / st_disconnect; pt_wrx_ctl
cfg_ew_half = 1, signal detect counts, wclk stop, freq_src 1-3, closed loop against real pt_wrx_cap / pt_cdr; the
uncommitted r7 edits.

## Disposition (digital owner, r7)
- F1: fixed as proposed (rtl/pt_wrx_ctl.sv ev_ok includes frun).
- F2: fixed (SDC: only wrx.al_sy[0], lk_sy[0], fk_sy[0] are false-path endpoints, with a count check).
- The `monitor.fault_m` exception is replaced by a through-point on a kept gate that covers all three legs.
- F3, F4, F5: accepted; F3 goes to the host documentation (USB direct stream: withdraw valid and wait for
  st_tx_busy = 0 before engine-off). The pt_core tx_data / tx_valid alignment observation is OPEN (directed test owed).
