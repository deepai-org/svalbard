# Wired RX + timing r12 (2026-11-19/20) - RESUME HERE

## Done
- netgen_lvs rejects property errors (aa07c7e2). pt_cdr / pt_diff_clk_rx: precheck main deck 0 standalone, read-back LVS clean (TIM-13; skeleton overlap is the floorplan's).
- DCF.1a: analog/timing/dcf_taps.py (ruled accepted). Tapped GDS in scratch/timing/drc12/*_taps.gds, main deck 0. Read-back LVS clean: slicer, vco_replica, new pll_ring_core (taps add no nets: 242 = 242). NOT yet: wrx_cap r7e tapped, pll_ring (re-layout pending).
- ct_phbuf8x (duty pairs) built; pt_pll_ring_core r12 staged (scratch/timing/pll_ring_core/stage, 202.1 x 442.0, committed ct_ring9 = TIM-12), DRC 0, precheck clean.
- Old r* scratch removed (10 GB); kept the dirs evidence points at.
- Bench decks updated for pad_hspad a6 (DVDD first port): r10ctle/ch10.py name map, r10detect/hssd.py positional. rc11 already loads physical-r-{typ,low,high}.spice (now a6).

## Ring numbers (C-only extraction: NOT R-aware, not publishable under the RCOV rule)
pt_pll_ring_core r12 staged, 30 ohm + 117 fF per phase, 405 MHz: duty 0.484-0.511 at ss315/tt/ss350/ff/sf; phase position -34..+35 ps, slots -31..+51 ps (ff worst). Fails the +-20 ps the coordinator accepted. fs_405 and 340 MHz rows were still running (scratch/timing/ring12/res/).

## Open, in order
1. pt_pll_ring: in-place phbuf swap shorts 6 nets (block landings over the new columns); needs the r9v ECO redone (scratch/wired_rx/r8ring asm.py on a re-routed r9d core with ct_phbuf8x) or an M_k-port phbuf + separate pair cell in the free area above phbuf8.
2. Spacing +-34 ps: decide with coordinator (accepted +-20).
3. Full-coverage R+C (extresist simplify off, tolerance 0, declared thresholds per scratch/wired_tx/s14/rcov/RCOV.md) for rings, ptrim, CTLE, capture before any publish. r11 ctle.rc.ext.spice: R on ~84 of 156 nets (rough count) - recheck coverage.
4. Goal 4 not started: CTLE tracking bias / regulated output CM (fold in r11/rc_ctle: -0.3..-1.1 dB, 5-7 mV offset, ss-pess 3.24 Gb/s eye 52.8 < 60 mV, load-return vias over per-cut limit), capture full-rate race, detect trunks + pessimistic fail, rate x corner table with a6 pad, review, publish.
