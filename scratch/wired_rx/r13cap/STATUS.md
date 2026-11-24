# Wired RX / timing r13 (2026-11-24) - RESUME HERE

## Capture r8 (staged, `scratch/wired_rx/r13cap`, source analog/wired_rx/capture.py)
r7e + DF/EF registered on CK in wc_lane. Grid build (m5_keep 70), ASM-12 pins: Metal4 0.8 um at the top edge, DW/WSTB
trunks spaced (net_space 0.4). 1241.2 x 260.5 um, Magic DRC 0, KLayout 0, LVS unique. Not yet: shuttle main/antenna/DCF taps.
| case | r7e | r8 |
|---|---|---|
| full 750 MHz 6x ss/3.15 (os125) | FAIL (29 strobes/5 words) | FAIL, same (slot-enable chain, not the lane race) |
| full 500 MHz 4x ss/3.15 (100BASE-TX defined mode, TIM-32) | pass, 2 one-sample shifts | pass, 0 errors |
| quarter 625 ss/3.15 nominal (g8) | pass | pass 0/200 |
| quarter 625 ss/3.15 pessimistic (g8) | FAIL | FAIL 72/200, 35 strobe errors |
Remaining blocker for binding (coordinator criteria): the slot-enable chain hop (ELQ flop -> 3-stage buf -> route -> AOI -> flop
in one ring period) at pessimistic ss / 625 MHz and at 750 MHz full rate. Next: re-architect the chain (local INJ shift register
per slot cell with flop->flop hops, mode mux before a retimed flop), then rerun g8 pess/nominal, os125 500/750, ff hold, tt.
Binding needs W7-GEAR (digital branch worktree-agent-a03e94865d3287179) in the same commit.

## RX ring r12 + ptrim r12c R+C (`scratch/timing/ringrc`)
Full-coverage extraction (RCOV recipe, supplies not resisted): ring 291/355 nets resisted, 8/8 phases, C ratio 1.000; ptrim
157/173, 116/116 clock nets. **Ring R+C at ss/32/3.15 V tops out at 740 MHz (VCTRL at the 2.64 V limit); C-only reached 810 at
1.74 V.** tt 810 MHz at 1.335 V; ss/3.50 V 810 MHz at 2.08 V. Chain 3.24 Gb/s T3 with R+C ring + ptrim: ss/3.50 V 0/112, eye
100.2 mV, margin 0.125 UI. So 3.24 (and 3.125, ring 781 MHz) at slow dies need the 3.50 V trim. Why R+C costs ~15 % at ss
only is not yet understood (check the ring's VCTRL->current path R and the regulated rail R).

## Update (end of session 2026-11-24): r8 better than bound r6 in every case run -> ready to bind (TIM-35)
Handoff master `scratch/timing/handoff/wrx_cap_r8.gds` (taps, main/antenna/DCF.1a 0). r8 vs r6 at ss/3.15: q625 0/200 vs 7/200; pess
q625 72/200 vs dead; f500 0/100 vs 29/120; bench B 2.5 Gb/s RCS=1 0/200 (r6 misses). Binding waits on digital (W7-GEAR rebase +
conn hunk in TIM-35 + MANIFEST switch, one commit). Next revision: slot-enable chain (pess q625, full 750).

## Slot-enable chain attempts (2026-11-24)
- r8 pessimistic ss 625 at 3.50 V: 23/200 (3.15 V: 72/200) -> the trim does not rescue it; re-architecture required.
- r9 try (scratch/wired_rx/r14cap, NOT kept, capture.py reverted to r8): in-cell hops from the flop output (no export buffer).
  WORSE: nominal ss q625 15/200 (r8 0/200), pess ss 72/180, pess 3.50 V 23/200. Faster hops alone break the chain (likely the
  TSPC hold / CKN-gated GCK timing relies on that delay). Next: two-period-wide enables or even/odd interleaved chains, with a
  hold check at ff in the same step.

## r10 probe + r10a try (2026-11-24, NOT kept; capture.py stays r8)
Probe of r8 extracted (5 words, ss/32/3.15, times after the slot-0 local clock CKL0 rise, period 1.6 ns), nominal / pessimistic:
| node | nom | pess |
|---|---|---|
| CKL1 vs CKL0 skew | +0.02 | +0.02 |
| ELQ4q (flop out) | 0.38 | 0.48 |
| ELQ4 (export bufx) | 0.67 | 0.83 |
| E8 (in-cell AOI out, slot0) | 1.03 | 1.27 |
| E12 (cross SL0 -> SL1) | 1.14 | 1.41 |
| ELQ15 (bufx) / E19C at wc_ctl | 0.74 / 1.15 | 0.88 / 1.39 |
So clock skew is NOT the r9 cause (CKL0/CKL1 within 20 ps). The slowest hops are the long ones: SL0 -> SL1 (E12) and
SL1 -> wc_ctl (E19C, then ctl's ELQ19 -> GW = the strobe errors).
**r10a** (in-cell successors from a local 2/4 -> 4/8 buffer ELQ<i>L, bufx only on exported 6..9/15/17/18, AOI NAND2 4/4,
NAND3 6/4; cells DRC 0 / LVS unique, top 1241.2 x 262.5, DRC 0, LVS unique): q625 ss nominal **7/200 (r8 0)**, pess ss 77/200
(r8 72), pess 3.50 V 23/200 (r8 23). Probe: E8 only 0.08 ns earlier (the "local" net still spans the 480 um slot row: ELQ4L
0.81 pess), while E12 1.45 and E19C 1.47 (pess) / 1.23 (nom) got LATER (extra load on ELQq, re-route) -> nominal broke on the
ctl word path. Lesson (also explains r9): in-cell hop speed is not the limiter; the cross-macro hops are, and any change that
adds load to ELQq or reroutes CK-tree-adjacent nets moves E19C past the edge.
**Next (r10b, recommended): two-period cross hops.** The chain is a pure shift register (INJ-seeded, no wrap), so
ELQ_i(s) = ELQ_(i-2k)(s-2). Replace each long hop by a hop from TWO slots back plus one extra local flop at the destination:
wc_ctl: E19C' = BQ&ELQ11 | BH&ELQ15 | BF&ELQ17 -> ff -> ff -> ELQ19; slot1 pairs fed from slot0 (quarter 10..13, half 10/11,
full 10): predecessor i-8 / i-4 / i-2 (all >= 2, exist) -> local ff -> chain ff. Gives 3.2 ns for the route + AOI, adds ~6 flops,
new ports ELQ2..5/ELQ11 (exports), no change to ELQq load if the extra exports use their own bufx. Hold: flop->flop, fine.
Untouched: in-cell hops (E8 1.19-1.27 pess) may then be the limit; if so, also fold the slot rows (pairs per slot adjacent).

## Plan for r10 (slot-enable re-architecture), handed to the next session
1. Probe first (r10cap/probe_top.py pattern on the r8 extraction, pessimistic ss 625): per hop, ELQ(i-k)q clk-to-q, export
   buffer, route, AOI, setup at ELQ_i; and the CKL0/CKL1/CNL skew. r9 (direct in-cell hops) broke NOMINAL ss (15/200): check
   hold against CKL0/CKL1 skew and the extra load on ELQ..q slowing GCK before choosing the fix.
2. Candidates: (a) even/odd interleaved chains clocked on alternate... no: a shift register cannot skip cycles, so a
   two-period path needs two-period-wide enables W_i (high for slots s, s+1; GCK_i = CKN & W_i & !W_next or a local
   one-period re-time) so the route + mode AOI becomes a two-cycle path; (b) keep one-period hops but make every hop local
   (chain flops abutted in slot order per mode, mode mux only at the start), exporting ELQ to the pairs through a separate
   buffer off the chain path, with a hold delay sized from the probe.
3. Gates for r10: q625 nominal ss/tt/ff, pessimistic ss 3.15 and 3.50 V, ff hold (C x0.9), full rate 500 MHz ss, bench B
   2.5 Gb/s RCS=1, then grid/pins/taps/readback LVS as for r8.
