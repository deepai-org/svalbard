# Digital macro area for the die-fit study (digital owner; refined as runs finish)

## v2, 2026-11-14 07:52 UTC: first placement of the r7 tree (run r7a, 1716 x 1865 = 3.200 mm2, core 3.116 mm2)

**The v1 number is too LOW. Book 3.5 mm2 (range 3.3 - 3.8) until r7a has been through global routing.**

Measured on r7a (tree of 07:38, includes the monitor time base and the CP4-1 clamps):
- cells after synthesis 1.428 mm2 (flops 0.718);
- after global placement + design repair (step 28): 1.969 mm2 of logic and buffers + 0.093 mm2 of tap / endcap cells
  = 2.061 mm2 = **66.1 % of the core already, before CTS, setup repair and hold fixing** (r5 at the same step:
  1.60-1.62). Split: logic 1.555 (resized up from 1.428), gain buffers 0.270, max-cap buffers 0.077, wire repeaters
  0.030, port buffers 0.016, slew 0.011.
- still to come in this run: clock trees, post-CTS setup repair, hold buffers (pC6: +0.15 mm2 for these on r5).
  Expected 2.2 - 2.3 mm2 = 71 - 74 % at this outline; no run above 66.6 % has ever finished global routing.
- at the 64 % that is known to route: core 2.25 / 0.64 = 3.5 mm2, outline 3.6 mm2; at 68 %: outline 3.4 mm2.
The number is replaced by the routed result (or the GRT failure) of r7a as soon as it exists (v3).

## v1, 2026-11-14 07:20 UTC: FIRST ESTIMATE, no P&R of the r6 RTL yet (scaled from measured runs)

**Book 3.2 mm2 (range 3.0 - 3.45) for the digital macro, not 2.814.** Outline is free in aspect; the
host-link edge (H2D/D2H pins, south) needs >= 1716 um of width as today, so e.g. 1716 x 1865 (3.20 mm2).

Basis (all measured unless marked):
- Cell area after synthesis of the committed r6 RTL (syn_r6t): 1.404 mm2 (r5: 1.241).
- Growth synthesis -> placed/repaired/CTS/hold, measured on r5 RTL: x1.29 after post-GPL repair (1.60), x1.42 after the
  post-CTS timing resizer + hold (pC6: 1.764; 0.26 mm2 of that was setup repair on paths that are now being closed in
  RTL, 0.014 mm2 hold buffers at the 8 % OCV / foundry-ff hold flow).
  -> r6 cells after CTS/hold: 1.85 - 2.0 mm2 (estimate; lower end if the RTL closure removes the setup-repair buffers).
- Utilisation that routes: 66.6 % routed clean at 1716 x 1640 (TC7); 67-77 % did NOT finish global routing
  (TC8/10/12/13/14). pC6 (67.4 %) was never routed. So the routable ceiling is taken as 64 % (range 62 - 66 %) of the
  core area; core area = 0.93 x outline (2.617 of 2.814 mm2: rings, tap/endcap margins).
  -> core 1.9 / 0.64 = 2.97 mm2 -> outline 3.19 mm2.
- Whitespace at that point: 1.07 mm2 -> about 0.7 nF of pt_decap50 row fill (PD2-7 asked >= 0.45 nF).

What can still move the number:
- down: cheap RTL reductions ordered by the coordinator (static trims without shadow rank, duplicated per-mode logic):
  expected 0.03 - 0.08 mm2 of cells (one dffrnq_1 = 65.9 um2; about 400-1200 flops) -> -0.05 .. -0.13 mm2 of outline.
- up: clock staggering buffers (PD2-6), hold fixing at the foundry-ff corner on the routed design.
- The first routed run of the r6 RTL replaces this section with measured numbers (v2).
