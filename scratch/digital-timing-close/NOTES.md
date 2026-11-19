# Digital macro hardening: current state (r9, 2026-11-19)

History r1-r8: `NOTES-archive-r1-r7.md` and git history. Rows: DG9-1..5 in `scratch/reviews/interface-changes.md`.
Area by module (single-die r8, still the reference for levers): `macro-area.md`.

## Configurations (split, SPL-7)

One RTL, `PT_CHIP` 1 = pt_rf, 2 = pt_wired. Configs `verification/digital_hardening/{rf,wired}/config.json`.
Flow: `CHIP=<chip> verification/run_digital_hardening.sh` (wrapper `r8/go.sh <chip>`, output
`scratch/digital_hardening-<chip>/`, one kept run per chip; containers named `dig-<chip>-*`). The SDC reads the
chip from `PT_CHIP` (passed to every container by the flow); `hio_shift.py <chip>` generates the FIRM host-link and
clock-root placement from the chip's outline at every run. `r8/sdcchk.sh <chip> <netlist dir>` checks the SDC on a
synthesized netlist in seconds.

## Routed results (run on cd9b4580 RTL + f6b61a8f aligner, later reverted), ss_032C_3v15 untrimmed

| | pt_rf | pt_wired |
|---|---|---|
| outline | 1716 x 1255.84 = 2.155 mm2 | 1716 x 1553.76 = 2.666 mm2 |
| utilisation | 79.3 % | 79.2 % |
| routed wire | 5.59 m | 6.58 m |
| detailed-route DRC / Magic / KLayout / LVS / antenna | 0 / 0 / 0 / match / 0 | 0 / 0 / 0 / match / 0 |
| worst setup | -4.15 (hcore) | -5.19 (wrx, reverted change) |
| hold ff_022C_3v35 / ff_n40C_3v60 | -0.02 (h2d_cap input window) / +0.02 | -0.54 (wrx, reverted change) / +0.06 |
| slew / cap violations (flow multi-corner check) | 4,071 / 1,361 | 3,640 / 1,478 |

Worst routed setup per group:
- pt_rf: hcore -4.15 (in_rd_step -> frame_tx pre_quads), hddr -3.33 (gearbox.run -> hr), egress_wtx -2.29,
  rftx -2.26, ingress_wrx -1.93, ctw -1.72, ref -1.72, fc4 -1.71, h2d_cap -1.48, h2d -0.84, hsdr -0.64.
- pt_wired: wrx -5.19 (aligner, reverted), hcore -3.59 (h2d.rb -> frame_rx.cat), ref -3.47 (regs.wtx_state ->
  pad_seq.left), hddr -3.02 (gearbox.run -> hr), egress_wtx -2.94 (roh2), wtx -2.19, hsdr -1.72, h2d_cap -1.50,
  h2d -1.41, fc4 -1.25, ctw -1.01, ingress_wrx -0.91.
The D2H hand-over (DG8-6, -5.5 routed in r8d) is gone from both lists. Timing is NOT closed on either chip.
NOT done on these runs: export, `sta_signoff.py`, GLS, evidence JSON, slew / cap list analysis.

## Clean baseline pt_wired (b7fc8be6 RTL: aligner reverted, gearbox run per lane), routed, ss_032C_3v15

DRC 0 / LVS match / antenna 0; hold ff_022C_3v35 -0.04 (H2D input window). Worst setup per group: hcore -5.14
(host.h2d.rb -> frame_rx.cat: H2D FIFO read into the frame aligner), wrx -3.87 (lc_rx hit -> off), ref -3.28
(regs.wtx_state -> pad_seq.left), egress_wtx -2.93 (roh2), wtx -2.38 (prbs.h -> pat_word), hddr -2.34 (was -3.02),
h2d_cap -1.82, fc4 -1.79, hsdr -1.49, h2d -1.22, ctw -1.20, async -0.80, hword -0.75.
pt_rf baseline on the same RTL: still running at the time of writing (`scratch/digital_hardening-rf`).

## Open, in order

1. hddr: lp -> hr (remaining after the per-lane run copy).
3. hcore: rf in_rd_step -> frame_tx pre_quads; wired h2d.rb -> frame_rx.cat. ref (wired): regs.wtx_state ->
   pad_seq (the r9 request stage moved the path, did not remove it). egress_wtx roh2 one-hot read; wtx egress.pe ->
   wire_idle. wrx aligner: needs a real extra stage (alignment decision one word later), not the one-hot compare.
4. Switching charge per edge sent (DG9-6). Then
   bank clock gating if it closes the 150 mV ripple budget (approved on that condition); skewed second root only
   after asking the coordinator.
5. Slew / cap violations (counts above), sign-off STA, GLS, evidence.
6. Goal "remove the other chip's ports": evaluated, not done (pins are not the routing limit; would fork the port
   list). Revisit only if routing fails.
