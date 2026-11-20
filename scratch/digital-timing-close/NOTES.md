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

## Routed results (33bba1e3, 2026-11-20), ss_032C_3v15 untrimmed

Both: route DRC 0, Magic / KLayout DRC 0, LVS match. Reports kept in `scratch/digital_hardening-<chip>/keep_reports/`
(full path reports included) with `final/`; step directories deleted.

| | pt_rf | pt_wired |
|---|---|---|
| outline | 1716 x 1365.6 = 2.343 mm2 (DG9-10) | 1716 x 1553.76 = 2.666 mm2 |
| utilisation | 68.8 % | 75.4 % |
| antenna violating nets | 0 | 1 (to fix) |
| hold ff_022C_3v35 / ff_n40C_3v60 | -0.013 / +0.081 | -0.064 / -0.001 |
| slew / cap violations | 2,720 / 896 | 3,125 / 979 |
| worst setup | ref -1.97 (fup_out -> c_cdr_fup port) | ref -3.35 (regs.wtx_state -> pad_seq.left) |

pt_rf: ref -1.97, h2d_cap -1.93, egress_wtx -1.51, hddr -1.41, hcore -1.37, async -0.95, fc4 -0.65, ingress -0.64,
fc2 -0.55, hsdr -0.47, ctw -0.34, h2d -0.29, hword -0.18.
pt_wired: ref -3.35, wtx -3.32 (lc_tx sA -> lc_q), wrx -3.26 (lc_rx hit -> cand), hcore -2.48 (ingress faddr -> pa),
hddr -1.67, egress_wtx -1.51, h2d_cap -1.17, async -0.72, h2d -0.51, hsdr -0.39, ingress -0.31, fc2 -0.22.
Fixed this round (routed): D2H hand-over (DG8-6), hcore H2D read (-5.1 -> ok), frame_tx compare, egress FIFO read side
(-2.9 -> -1.5, -0.07 mm2/chip), gearbox run per lane. Timing NOT closed on either chip.

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
