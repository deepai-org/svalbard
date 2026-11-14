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

- The clamp is either fully on (about 1 A per cell into a stiff source) or off (displacement current only). It fires for a full-swing
  ramp of 2 us or faster in the slow-RC / slow-MOS / 3.5 V cases and 1 us or faster otherwise; it never fires at 3 us or slower.
  In slew terms: fires at >= 1.75 V/us, does not at <= 1.2 V/us.
- **Board rule "10-90 % >= 10 us" (0.36 V/us at 3.63 V) has >= 3.3x margin in ramp time on the worst simulated case.**
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
- Per-chip supply trim: at a 3.5 V setpoint the 2 us ramp already fires at tt; the 10 us rule still has 5x margin (3 us does not fire).
