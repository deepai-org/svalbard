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
