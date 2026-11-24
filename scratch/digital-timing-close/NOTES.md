# Digital macro hardening: current state (2026-11-24)

History r1-r8: `NOTES-archive-r1-r7.md` and git history. Rows: DG9-1..5 in `scratch/reviews/interface-changes.md`.
Area by module (single-die r8, still the reference for levers): `macro-area.md`.

## Configurations (split, SPL-7)

One RTL, `PT_CHIP` 1 = pt_rf, 2 = pt_wired. Configs `verification/digital_hardening/{rf,wired}/config.json`.
Flow: `CHIP=<chip> verification/run_digital_hardening.sh` (wrapper `r8/go.sh <chip>`, output
`scratch/digital_hardening-<chip>/`, one kept run per chip; containers named `dig-<chip>-*`). The SDC reads the
chip from `PT_CHIP` (passed to every container by the flow); `hio_shift.py <chip>` generates the FIRM host-link and
clock-root placement from the chip's outline at every run. `r8/sdcchk.sh <chip> <netlist dir>` checks the SDC on a
synthesized netlist in seconds.

## State 2026-11-24 (successor of the stopped digital agent)

Delivered macros = DG9-16 (RTL 4a603f3c) in `scratch/digital-macro-baseline/<chip>/`. HEAD RTL is ahead of them
(timing batch fe6ab2fe..390100b6, DG9-17: no rerun beat DG9-16) plus CB8-6 (`s_pg_wired_tx_b`) and WT58/WT59
(`c_wiredtx_cascode_boost`): the next pt_wired (and pt_rf, same RTL) hardening must carry those ports.
pin_order_wired.cfg must be regenerated after `synth_area.sh 2` (ports_of_macro reads that synth netlist; it was stale).

Routed STA on DG9-16 (`trim/`: OpenRCX max SPEF re-extracted from the delivered DEF, characterized ss_032C_3v15 lib;
known answer reproduces DG9-16 WNS exactly: rf -1.663, wired -2.059 ns):
- untrimmed 3.15 V: rf -1.66 (h2d_cap, d2h_fwd -1.50, hcore -1.49, ref -1.31, d2h_oddr -1.30), wired -2.06 (fc4 -2.06,
  hcore reset -1.90, d2h_fwd -1.63, h2d_cap -1.31, d2h_oddr -1.28, ref -1.24, wtx -1.19, wrx -1.18, egress_wtx -1.11).
- 3.50 V trim (MANDATE 2), estimated as a uniform cell-delay factor 0.90 on the 3.15 V library (libchar of 6 cells at
  ss_032C 3.50 / 3.15 V, scratch/digital-libchar/trim, `ratio.py`: medians dffrnq_2 0.889, mux2_2 0.887, aoi21_2 0.896,
  buf_4 0.898, nand2_2 0.898, clkbuf_8 0.912), clock OCV kept, wires not scaled:
  rf WNS -1.29 (d2h_fwd -1.29, h2d_cap -0.93, d2h_oddr -0.63, ref -0.20, hcore -0.16, hddr -0.11);
  wired WNS -1.41 (d2h_fwd -1.41, d2h_oddr -0.62, h2d_cap -0.61, hcore -0.45, fc4 -0.37, wtx -0.29, ref -0.22, hddr -0.14).
  So with the trim the host-link pin windows (hand-placed D2H ODDR / H2D capture) dominate; the rest is <= 0.45 ns and
  fc4 / hcore reset are already fixed in HEAD RTL (aa737acc, dfc47642). A full 3.50 V library (libchar.py run --cells used)
  is still to be built for sign-off.
GLS: the 5 h job was hung (zero-delay loop of the OBS-14 ring pt_dig_ring in FUNCTIONAL cell models once
dig_ring_enable is written); fixed in tb_digital_gl.sv (loop broken at dring.n[0], driven by the behavioural model);
RTL reference failed to compile (pt_linecode hit used before declaration, fixed) and was elaborated as PT_CHIP 3 instead
of the netlist's chip (fixed: gls.sh -P, gls_commands --chip). Rerun: r8/gls916.sh (DG9-16 netlists vs their own RTL in
the worktree scratch/dg916-gls-src = 4a603f3c + these bench fixes).

## Open, in order
1. Host-link windows d2h_fwd / d2h_oddr / h2d_cap (hand placement in hio_placement; or FPGA-side training argument as DG9-18).
2. Re-harden both chips on HEAD RTL (timing batch + CB8-6 + WT58 ports); STA untrimmed and trimmed; GLS; deliver LEFs.
3. W7-GEAR: waits wired RX r7e B1 race (WR11-4).
4. CB8-15 items 2 (register rule: wired/debug islands only with pll on) and 4 (audit fact for rf_tx_sample gating).

