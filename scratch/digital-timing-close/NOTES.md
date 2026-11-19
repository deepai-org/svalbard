# Digital macro hardening: current state (r8, 2026-11-18)

History of rounds r1-r7 (TC runs, flow experiments, per-path fixes): `NOTES-archive-r1-r7.md`. Area detail:
`macro-area.md`. Rows: DG8-1..8 in `scratch/reviews/interface-changes.md`.
Independent review dg8 (diff `scratch/reviews/dg8-review/r8.diff`, reviewer's scratch in `work/`; the report text
went to the coordinator, no file): GO-with-conditions. Conditions 1-3 (clamp pins unprotected in the flow,
pass selection by marker file, live bind mount) are fixed in the tree and were NOT re-reviewed; condition 4
(bench gaps) is partly done (payload frames, all reserved opcodes); open: DAC-pin override bench, IX-11 limits.

## Where it stands

- Outline in the tree: **1716 x 1640 um = 2.814 mm2** (`verification/digital_hardening/config.json`,
  `hio_shift.py 0`). The 1716 x 2126 experiment is abandoned (it did not route either).
- The macro **routes at 2.814 mm2**: run r8d went through the whole LibreLane flow. 79.5 % utilisation at the
  end, global routing 48 % track usage without overflow, detailed routing 0 violations (7.22 m), Magic and
  KLayout DRC 0, LVS unique match, antenna 0, XOR 0, clamp check clean at four stages. The flow ends rc = 2 on
  its timing checkers only (setup below, 3,873 slew and 1,523 capacitance limit violations in its multi-corner
  check, not analysed). NOT done on r8d: GDS re-export with the analog image, `sta_signoff.py`, GLS, evidence.
  r8d was built from the tree before the comment-only RTL edits and the register-map hash change.
- **Timing is not closed** at ss_032C_3v15 (untrimmed): routed and extracted (flow STA, max RC) the worst
  setup slack is -5.49 ns; hold at the ff corners is met except -0.02 ns on the H2D input window. The misses are
  logic depth and the D2H hand-over, not wire.
- RTL regression (`r8/regress.sh b`, the eight targets of the r7 list) is green on the committed RTL
  (`r8/regress_b.log`).

## Why it did not route before (measured on r7c, 1716 x 2126, 62.9 %)

- 5.0 m of the 8.1 m half-perimeter wire sat in buffer trees. The flow built fanout (gain) trees AFTER global
  placement (`repair_design -buffer_gain` in the post-placement step). Gain trees group sinks without regard to
  location, and only the legaliser placed the buffers. Nets of fanout 5-13 averaged 230-520 um.
- Clock nets carried a non-default rule (`CTS_APPLY_NDR half`): 82 clock nets at double width / spacing.
- Result: 16.7 m routed length, 70 % track usage, 29,774 overflows after 50 iterations at 62.9 % utilisation.
- Fix (config + `repair_design_pt.tcl`): gain buffering as a `-pre_placement` pass BEFORE the final global
  placement, the stock location-aware repair after it, no clock NDR. Same RTL at 1716 x 1860: 8.4 m, 42 % usage,
  zero overflow, one iteration.

## Flow (verification/run_digital_hardening.sh, digital_hardening/)

- `config.json` `meta.substituting_steps` inserts a second `OpenROAD.RepairDesignPostGPL` before
  `OpenROAD.GlobalPlacement`; `repair_design_pt.tcl` (snapshot in `$OUT`, bind-mounted over the stock script)
  runs pass 1 (gain only) or pass 2 (stock repair without gain) depending on the step's input database.
- Gates after `pnr` (exit 3): both pass banners present, no unresolved dont-touch name (STA-0101),
  `clamp_check.py` clean on the post-repair, post-CTS, post-route-repair and final netlists.
- Clamp pin nets with a bus index are protected by `RSZ_DONT_TOUCH_RX` (raw net-name regex). As list entries they
  never resolved: every run before r8d had input buffers in front of 100 of the 130 isolation AND2s.
- `hio_shift.py <n>`: outline 1640 + n x 7.84 um, moves the H2D capture block with the north edge and fixes
  the divider flops under their clock root buffers (`CLOCK_ROOTS`). Without the latter CTS moves a root buffer
  to its sink centroid and leaves the flop 0.5-1.1 mm away (fc0-5 went from -3.4 to +0.3 ns with it).
- The 52 FIRM launch / capture flops are dont-touch instances in the timing-repair steps (an upsized one
  overlaps a tap: DPL-0033 killed r8a and r8c after global routing); `repair_design_pt.tcl` drops them from the
  list because repair_design cannot buffer a net that loads a dont-touch instance.
- Do not raise `CTS_SINK_CLUSTERING_SIZE / MAX_DIAMETER`: 30 / 90 um gave MORE clock buffers (0.167 vs 0.132 mm2).
- The flow reaches global routing in about 20 minutes at 4 CPUs; post-CTS and post-route timing repair spend
  most of that grinding on the D2H hand-over, which they cannot fix.

## Timing, ss_032C_3v15, post-CTS + repair, 8 % clock OCV, placement RC (worst setup per group, ns)

| group | r7b 3.20 mm2 (old flow) | r8a 3.19 mm2 | r8d 2.81 mm2 | what it is |
|---|---|---|---|---|
| hddr | -3.98 | -4.73 | -3.51 | hcore -> D2H gearbox hand-over: hcore arrives ~10 ns after the hddr edge it is derived from |
| egress_wtx | -3.45 | -1.36 | -2.77 | egress read pointer (roh1 -> roh2, playback wrap compare) |
| wtx | -2.48 | -2.06 | -2.02 | lc_tx sA -> lc_q (8b/10b encoder) |
| wrx | -1.85 | -2.29 | -1.92 | lc_rx hit -> cand / prbs_check ovf -> errors |
| h2d_cap | -1.31 | -1.31 | -1.73 | H2D capture nsel -> fhh (hand-built block) |
| ref | -2.12 | -1.45 | -1.59 | wtx committed / pad_seq |
| hcore | -2.46 | -1.13 | -1.09 | ingress / frame |
| h2d | -0.67 | -0.72 | -0.88 | phase -> entry enables |
| fc4 | - | -0.58 | -0.75 | monitor qcnt -> q_done |
| hsdr | -0.19 | -0.23 | -0.62 | en_d -> en_sdr |
| fc0-5 | -0.35 | -1.77 | +0.33 | prescaler flop (fixed clock source in r8d) |
| ctw | -0.17 | -0.34 | -0.28 | detector |
| sclk | -0.54 (10 MHz) | met | met | 5 MHz constraint = the requirement |
Hold (ss view of this step): h2d_cap -1.10 (H2D input window, hand-built block), rest >= +0.29.

Routed and extracted r8d (flow STA after RCX, max RC, ss_032C_3v15; `r8/keep/r8d_routed_*.txt`): hddr -5.49,
wtx -3.96, wrx -3.45, egress_wtx -3.31, hcore -2.53, h2d_cap -2.38, ref -2.28, fc4 -1.62, hsdr -1.38, h2d -0.98,
ctw -0.94, asynchronous -0.86, hword -0.78, ingress_wrx -0.20, fc0-5 +0.95. Routed is 1-2 ns worse than the
post-CTS estimate at this density. Hold: ff_022C_3v35 worst -0.02 (h2d_cap), ff_n40C_3v60 worst +0.04.
One gate level costs 0.6-1.3 ns at this corner and a flop 2.1-2.6 ns clock-to-Q: 12.3 ns holds 7-8 levels.

## Open, in order

1. **D2H hand-over (hddr).** hcore = hddr / 2 through the divider flop, its root buffer and the 5,000-flop tree:
   9.6-11 ns later than the gearbox clock at ss, 4-5 ns at ff, against a 12.8 ns relation with four gates in the
   path. Not repairable by the tools. Options: (a) two-entry ping-pong register between `prefix` and the
   gearbox (written on alternate hcore edges, read by the gearbox one hddr period after the write: 25.6 ns
   window, valid for any skew up to ~12 ns; +40 flops, +12.8 ns D2H latency, formal file
   `verification/formal/pt_d2h_gearbox_fv.sv` to extend); (b) a replica delay line on the gearbox clock with
   its own generated clock for CTS. (a) is the conservative one. The reduced host rates were not re-timed on r8d.
2. Logic depth in egress_wtx / wtx / wrx / ref / hcore: one more register stage each (archive: worklists).
3. On a routed 2.81 mm2 run: export, `sta_signoff.py` (OCV views, D2H / H2D windows, fmax), GLS, the slew /
   capacitance violation list, evidence JSON.
4. Area levers not taken (see `macro-area.md`): write-enable muxes of the two transport banks and the register
   file (6,470 mux2_2 = 0.213 mm2) -> gated clocks; read side of the transport banks (three parallel 28:1 trees).
5. 3.5 V characterised library (`libchar.py` corner ss_032C_3v50) is still not built; the trim buys ~10 %.
6. IX-11: override at the DAC pins in a macro-level bench; latency / update-rate limits (review finding 4).

## Runs (scratch/digital-timing-close/)

| run | outline | flow | result |
|---|---|---|---|
| r7c | 1716 x 2126 | old | 62.9 %, global routing failed with congestion (kept: `r8/r7c_keep/`) |
| r8a | 1716 x 1860 | two-pass | 68.4 %, global routing clean; stopped in post-route repair (DPL-0033, FIRM flop upsized); clamp buffers present |
| r8c | 1716 x 1640 | two-pass, fixed clock roots, CTS clusters 30 / 90 | 79.1 %, global routing clean (49 %); stopped like r8a |
| r8d | 1716 x 1640 | flow as committed (1b8b44e) | complete flow: routed, DRC 0, LVS match; timing open (kept: `r8d/design/runs/R8D/final`, `r8/keep/`) |
| r8e | 1716 x 1562 (2.68 mm2) | same, density 88 | 81.4 % after CTS, global routing clean (56 %); timing clearly worse (wrx -3.6, ref -3.0, hcore -2.9 post-CTS); killed in detailed routing to free disk: detailed routability at 2.68 is unknown |
Tools in `r8/`: `go.sh <name> [stages]`, `regress.sh <tag>`, `defwl.py` / `wlroot.py` / `areamod.py` (wire and
area by module from a DEF), `pathsum.py` and `grpw.sh` (worst path per group), `exp.tcl` (buffering experiments;
it does not load the flow's layer RC, use it for relative comparisons only).
