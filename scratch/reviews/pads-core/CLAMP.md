# Supply-pad clamp vs supply edge (INT6-0 confirmation) — 2026-11-14

Bench `clamp/gen.py`, `run.sh`, `collect.py` -> `results.txt` / `results.json`. PDK transistor-level netlists of the provider
`dvdd`, `dvss`, `cor` cells (refingered to the model bins, as M6 did).

Mechanism (read from the netlist): 12 x 30 kohm poly (360 kohm) + 8 x 25x10 um MOS cap, three inverters, one 4 mm 6 V NMOS per
cell. Known answer: AC corner of the trigger node = 100.5 kHz at tt -> tau = 1.58 us (hand estimate 1.66 us).

Stage A, ONE cell, ideal ramp 0 -> V, no inductance: peak clamp current.

| Corner | 0.1-1 us | 2 us | 3 us | 5 us | 10 us | 100 us |
|---|---|---|---|---|---|---|
| tt/27/3.3 | 0.92 A | 0.23 mA | 0.10 mA | 11 uA | 5 uA | 0.5 uA |
| tt/27/3.5 | 1.01 A | **0.88 A** | 0.14 mA | 19 uA | 5 uA | 0.6 uA |
| ff/85/3.63 | 1.18 A | 0.29 mA | 0.13 mA | 18 uA | 3 uA | 0.3 uA |
| ff/85/3.63, slow RC (res_ss, moscap_ss) | 1.18 A | **1.18 A** | 0.42 mA | 0.16 mA | 9 uA | 0.4 uA |
| ss/0/3.63 | 0.89 A | **0.89 A** | 0.18 mA | 36 uA | 10 uA | 0.9 uA |
| sf/85/3.63 | 0.84 A | **0.84 A** | 0.22 mA | 58 uA | 3 uA | 0.3 uA |
(`dvss` identical to `dvdd`; `cor` 1.8-2.4 A fired, same thresholds.)

- The clamp is either fully on (about 1 A per cell into a stiff source) or off (displacement current only). In this sweep
  (ramp times 1, 2, 3, 5 ... us) it fires for a full-swing ramp of 2 us or faster in the slow-RC / slow-MOS / 3.5 V cases and
  1 us or faster otherwise, and not at 3 us.
- **Correction from the independent review (`review-cs/REVIEW.md` finding 6, finer sweep, RERAN there):** the worst corner is
  not in the table above. At sf/85 C with res_ss + moscap_ss one cell fires fully at 3.0 us (0.84 A) and partly at 3.5 us
  (0.64 A); 4.0 us is clean. ff with the slow RC fires up to 2.8 us. In slew terms the fastest clean case is 0.91 V/us and
  the slowest firing case 1.04 V/us.
- **Board rule, written as a slew limit: dV/dt <= 0.3 V/us at any point of any rise of the die supply (power-up and recovery
  from a dip), i.e. 0 -> 3.63 V in >= 12 us; no hot-plug.** That is about 3x below the slowest firing slew. A plain
  "ramp >= 10 us" (0.36 V/us) has 2.5-2.9x margin as a full ramp, not the 3.3x first stated here.
- Stage S, 100 ns step on a settled rail ending at V (brownout recovery): steps of 0.2-1.5 V give <= 0.3 mA at every corner:
  the clamp does not fire (the first inverter needs the timer node about half a rail behind). So the rule concerns power-up
  from near 0 V, not ripple or dips of up to 1.5 V.
- Stage C, the ring (8 dvdd + 10 dvss + 4 cor) behind the bond loop (22.5 mohm, 2.2 nH, 1 nF die), stiff ramp source:
  1 us: 18.6 A (tt/3.3) / 23.8 A (ff/85/3.63) peak, 35-77 uJ into the die, die rail peak 3.48 / 3.77-3.88 V, above 3.63 V for
  0.13 us; 3 us: <= 12 mA; 5-50 us: <= 5 mA, no overshoot. M6's 8.7-10.3 A and 5.7-6.4 V came from a softer source with more
  series inductance (its board feed model): the firing threshold agrees (1 us fires, 10 us does not), the peak current and the
  overshoot depend on the source network, which is a board property.
- Trigger time constant by AC (known answer for the thresholds): 1.14 us (ff), 1.58 us (tt, sf, fs), 2.09 us (ss; and ff MOS with res_ss + moscap_ss).
- Negative control (timer capacitor removed, ff/85/3.63): 0.3 / 1 / 3 us ramps give 72 / 24 / 9 uA: no firing, so the firing is the RC timer.
- NOT shown: that a fired event is survivable. Hot-plug decks (contact closing in 50 ns onto a stiff carrier rail, with and without
  the 8 COB capacitors) did not converge (ngspice "timestep too small" at the edge), so there is no hot-plug waveform from this bench.
  Rule stays: no hot-plug of the mezzanine onto a live rail; regulator soft start >= 10 us (>= 100 us recommended).
- Per-chip supply trim: at a 3.5 V setpoint the 2 us ramp already fires at tt (it does not at 3.3 V); the slew rule is unchanged.
- Not run (reviewer's list): steps above 1.5 V, ramps starting from 1.0 V (a 1.5 -> 3.63 V ramp in 1 us does not fire), exponential
  rises, the ring with M6's source network, every hot-plug case. The <= 3.88 V die-rail peak is for an ideal stiff source and must not
  be quoted as chip behaviour.
