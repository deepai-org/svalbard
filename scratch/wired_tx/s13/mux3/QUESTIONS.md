# Questions from the layout sub-agent (s13/mux3, 2026-11-18)

No schematic device had to be replaced by a "closest buildable" one: both layouts match their netlists with widths and lengths
compared.  The items below are design questions the layout raised.

1. **Detector wires XE k / XD k: 40-58 fF each, the bench assumes 4 fF.**  The pump chains sit in the control block (allowed by
   the brief); the 16 wires run the full block length on Metal4 (275-277 um each, equal length) and are driven by the 0.5 / 1.0 um
   inverters DA / DB at the PH pins.  By hand: 6-7 kohm x 50 fF is about 0.3 ns per inverter against a 320 ps slot at 3.125 Gb/s.
   A pump conducts while XE a and XD b are both low; XD is one inverter later than XE, so the window should widen by the DB delay
   rather than close, and the two windows of a pump then overlap.  That is reasoning, not a simulation: please run the interlock
   rows (running ring at all corners, stopped ring, stop detection time) on `generated/fast/wtx_mux8.ext.spice`.
   If RUN margin suffers, the alternative I see is the four switch chains next to their phases (wires of two slice pitches,
   about 7 fF, like the B / UP / VP ring wires).  That needs either devices placed by the top inside four of the eight slice
   outlines, or the chains made part of every slice in the schematic.  Which do you prefer?
2. **Tap: where do the loads and the skewed inverters go?**  The pair is at the MAIN load cluster as asked; its drains return
   230 um to the side cell (TD1 / TD2 37 fF, TS 41 fF).  15 kohm x 37 fF = 0.55 ns.  If that is too slow for 480 Mb/s, the loads,
   TK / TB inverters, tail and TEN gates fit one row in the free top-left corner (138 x 23 um) beside the cluster; the cell would
   then have two parts.  Say so and it is a small change of `wtx8_aux_layout.py`.
3. **Tap loading is unequal:** MAIN_P +2.8 fF, MAIN_N +0.5 fF of wire with the tap attached (the three return wires pass the
   MAIN_P side).  Acceptable, or shall the wires leave symmetrically (TD1 over RL_P, TD2 over RL_N, both then around the cluster)?
4. **Bank current for the EM table.**  The metal is sized for 26 mA with static data; zero margin is at 30.1 mA.  When you have
   the simulated ff / 3.63 V / 85 C value: `python3 wtx_mux8_layout.py em <mA>`.  Is 26 mA also the bound for the POST bank
   (I used the same)?  The poly load resistors (RL 10 um wide) carry the whole bank current with static data; I have no
   current limit for ppolyf_u in the brief.
5. **Aux position and pins.**  Left side of the mux, 1 um gap, pins as Metal3 pads over the cell (coordinates in
   `aux/pins.json`), supplies as edge bars.  The mux's control pins (ENM, ENP, EN_MAIN, EN_POST, EXT, OVP, OVN, POL, RUN) are on
   the bottom edge of the control block, 5-38 um from the mux's left edge; the aux outputs for them are 10-60 um further left.
   Is the left side right for the block top, or should the cell go to the right (then the tap pair's wires get shorter only if
   the MAIN cluster is mirrored too)?
6. **Control block width (36 um).**  Its gate list is written out by hand per row (the netlist changed while I worked) and the
   tracks are packed automatically; a hand-packed version should be narrower.  Worth doing before the schematic is frozen?
7. **R + C netlist.**  Magic extresist with the repo's recipe returns resistors for 25 nets of the mux only; the buses and phase
   nets stay C only.  If you need R on MAIN / POST (bus 276 um of Metal5, 2.5-4.55 um wide) I can add the bus resistance by a
   documented post-process from the drawn widths, or you take the lumped values: tell me which.
